"""硬字幕压制参数模型与 ffmpeg 命令构建（2.8.0 批1 件1，D2026-1007-03）。

纯函数模块：零 GUI 依赖、零子进程调用，只做参数校验与 argv 组装，可独立单测。

设计冻结约束（决策八 + 开工门裁定 0b，改动须回评议）：
- 8bit 固定：滤镜链尾恒 ``format=yuv420p`` 收口；10bit 已整体删除、零残留
  （不设开关、不留参数位；用户 custom_params 注入任何 pix_fmt 一律拒绝）。
- 2-pass 未实现（挂候选，本版本不做）。
- 滤镜链不随档变：compress/balanced/quality 三档只调码控（crf/preset 或
  b:v/maxrate/bufsize）与速度系数，滤镜链恒定（决策八-3）。
- custom_params 是唯一用户逃生门，受三层黑名单契约约束（canonical 归一集 +
  别名展开 + 不变式守卫，HRO-2；不以件数做门）；程序自身产出的旗标经
  ``_GENERATOR_REGISTRY`` 注册并由 ``assert_generators_consistent`` 自洽钉。
- backend=gpu 在批1 显式拒绝（A9：不静默降级 CPU）。

音频 copy 回落透出约定：``build_ffmpeg_args`` 返回 ``(args, audio_fall_back)``
二元组——``audio_fall_back`` 为空串表示未回落；非空即回落原因（人话，
C6），由调用方（encode_queue / api 层）透出 UI。
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field

__all__ = [
    "DEFAULT_ENHANCE_PARAMS",
    "BannedFlagError",
    "EncodeParams",
    "assert_generators_consistent",
    "build_ffmpeg_args",
    "escape_subtitles_path",
    "parse_custom_params",
    "reference_bitrate_kbps",
    "speed_factor",
    "validate_params",
]

# ---------------------------------------------------------------------------
# 冻结表（spike 2026-10-07 实测定值，批清单执行记录；调优不改结构）
# ---------------------------------------------------------------------------

_VIDEO_CODECS = {"h264": "libx264", "h265": "libx265", "av1": "libsvtav1"}

# 画质三档码控（crf, preset）；x265 的 -crf 即 RF；svtav1 preset 为数字串
_RATE_CONTROL: dict[str, dict[str, tuple[int, str]]] = {
    "h264": {"compress": (28, "slower"), "balanced": (23, "medium"), "quality": (20, "slow")},
    "h265": {"compress": (30, "slower"), "balanced": (26, "medium"), "quality": (22, "slow")},
    "av1": {"compress": (55, "6"), "balanced": (45, "8"), "quality": (35, "10")},
}

# GPU 码控映射（批2，决策 MVP：NVENC p6/p7+tune hq+b:v 派生 1.45×/2.9×；
# QSV global_quality+slower（owner HQ.xml 实锚 24@1080p）；AMF 未实测占位）。
# {family: {fmt: {tier: (preset_value, quality_value)}}}——nvenc 两值=(p 档, None
# 走 VBR 派生)；qsv/amf=(preset 名, global_quality/-quality 值)
_GPU_FAMILIES = {
    "nvenc": {
        "h264": {"compress": ("p6", None), "balanced": ("p6", None), "quality": ("p7", None)},
        "h265": {"compress": ("p6", None), "balanced": ("p6", None), "quality": ("p7", None)},
        "av1": {"compress": ("p6", None), "balanced": ("p6", None), "quality": ("p7", None)},
    },
    "qsv": {
        "h264": {"compress": ("slower", 26), "balanced": ("slower", 24), "quality": ("slower", 22)},
        "h265": {"compress": ("slower", 26), "balanced": ("slower", 24), "quality": ("slower", 22)},
        "av1": {"compress": ("slower", 26), "balanced": ("slower", 24), "quality": ("slower", 22)},
    },
    "amf": {
        "h264": {"compress": ("speed", None), "balanced": ("balanced", None), "quality": ("quality", None)},
        "h265": {"compress": ("speed", None), "balanced": ("balanced", None), "quality": ("quality", None)},
        "av1": None,   # AMF 无 AV1 编码器（占位标注，决策 MVP）
    },
}

# GPU 后端编码耗时系数（决策 ETA 分档 GPU≈1/5-8，取保守 0.25 供超时预算）
_GPU_SPEED_FACTOR = 0.25

# GPU 编码器候选链（决策 MVP：nvenc→qsv→amf，逐格式；amf 无 av1）
_GPU_ENCODER_CHAIN: dict[str, list[tuple[str, str]]] = {
    "h264": [("h264_nvenc", "nvenc"), ("h264_qsv", "qsv"), ("h264_amf", "amf")],
    "h265": [("hevc_nvenc", "nvenc"), ("hevc_qsv", "qsv"), ("hevc_amf", "amf")],
    "av1": [("av1_nvenc", "nvenc"), ("av1_qsv", "qsv")],
}

# VBR 模式 preset 恒取格式均衡档（批清单件1）
_BALANCED_PRESET = {"h264": "medium", "h265": "medium", "av1": "8"}

# 速度系数（编码耗时 ≈ k × 媒体时长，spike 实测冻结；超时表与 ETA 派生用）
_SPEED_FACTOR: dict[str, dict[str, float]] = {
    "h264": {"compress": 0.51, "balanced": 0.39, "quality": 1.0},
    "h265": {"compress": 3.93, "balanced": 0.57, "quality": 1.14},
    "av1": {"compress": 0.54, "balanced": 0.45, "quality": 0.37},
}

# VBR 码率参考表 1080p 基准（kbps，A8 锚点）；按像素数线性缩放 + 档位系数
_REFERENCE_BITRATE_1080P = {"av1": 3113, "h265": 4200, "h264": 5500}
_TIER_FACTOR = {"compress": 0.75, "balanced": 1.0, "quality": 1.35}
_1080P_PIXELS = 1920 * 1080

_RESOLUTION_SIZES = {
    "720p": (1280, 720),
    "1080p": (1920, 1080),
    "1440p": (2560, 1440),
    "2160p": (3840, 2160),
}

# owner AV1.xml 冻结缺省（决策八-2）：滤镜链不随档变，批1 仅整体开关
DEFAULT_ENHANCE_PARAMS = {
    "hqdn3d": "0.8:0.6:0.7:0.6",
    "deblock": "alpha=0.07:beta=0.07",
    "unsharp": "5:5:0.5:3:3:0.3",
}

_AUDIO_COPY_WHITELIST = frozenset({"aac", "mp3", "ac3", "eac3"})  # C6

_VBR_MAXRATE_RATIO = 1.45
_VBR_BUFSIZE_RATIO = 2.9

# 字幕 force_style 冻结串（HRO-3：钉系统 CJK 字体；底端居中，决策十-②）
_FORCE_STYLE_TEMPLATE = (
    "Fontname=Microsoft YaHei,Bold=1,Fontsize={font_size},"
    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,BorderStyle=1,"
    "Outline=2.5,Shadow=2.5,Alignment=2,MarginL=10,MarginR=10,MarginV=20,Encoding=1"
)

_FONT_SIZE_MIN, _FONT_SIZE_MAX = 12, 72


# ---------------------------------------------------------------------------
# 参数模型
# ---------------------------------------------------------------------------


@dataclass
class EncodeParams:
    """压制参数（批1 全 CPU；backend=gpu 仅枚举占位、校验显式拒绝）。"""

    video_format: str = "h264"          # h264 / h265 / av1
    backend: str = "auto"               # auto / cpu / gpu（批1 auto 恒解析 CPU）
    quality: str = "balanced"           # compress / balanced / quality
    resolution: str = "original"        # original / 720p / 1080p / 1440p / 2160p
    enhance_on: bool = True             # False=忠实源出口（去增强链）
    enhance_params: dict = field(default_factory=lambda: dict(DEFAULT_ENHANCE_PARAMS))
    font_size: int = 22                 # 受控 12~72
    audio_mode: str = "copy"            # copy / 96k / 128k / 192k
    rate_mode: str = "quality_tier"     # quality_tier / target_vbr
    target_bitrate_kbps: int | None = None  # VBR 手改值；None=按参考表派生
    out_path: str = ""                  # 成品路径（队列层改写为 .part 后传入）
    custom_params: str = ""             # 逃生门，黑名单三层契约约束
    volume_db: float = 0.0              # 批3 音量增益（受控 ±12dB；≠0 强制 aac）
    auto: bool = False                  # 批3 自动化入队标记（跳过覆盖=跳过语义）


def validate_params(params: EncodeParams) -> None:
    """参数全量校验（枚举/范围），违规抛 ValueError。

    backend=gpu 批2 解禁：结构校验放行，实际可用性由供给层双检解析
    （resolve_gpu_encoder），不可用显因拒绝（不静默降级，A9 语义延续）。"""
    if params.backend not in ("auto", "cpu", "gpu"):
        raise ValueError(f"未知 backend: {params.backend}")
    if params.video_format not in _VIDEO_CODECS:
        raise ValueError(f"未知视频格式: {params.video_format}")
    if params.quality not in _TIER_FACTOR:
        raise ValueError(f"未知画质档: {params.quality}")
    if params.resolution not in ("original", *_RESOLUTION_SIZES):
        raise ValueError(f"未知分辨率挡: {params.resolution}")
    if params.audio_mode not in ("copy", "96k", "128k", "192k"):
        raise ValueError(f"未知音频模式: {params.audio_mode}")
    if params.rate_mode not in ("quality_tier", "target_vbr"):
        raise ValueError(f"未知码控模式: {params.rate_mode}")
    if not isinstance(params.font_size, int) or not _FONT_SIZE_MIN <= params.font_size <= _FONT_SIZE_MAX:
        raise ValueError(f"字号须在 {_FONT_SIZE_MIN}~{_FONT_SIZE_MAX} 之间: {params.font_size}")
    if (params.rate_mode == "target_vbr" and params.target_bitrate_kbps is not None
            and (not isinstance(params.target_bitrate_kbps, int)
                 or params.target_bitrate_kbps <= 0)):
        raise ValueError(f"目标码率须为正整数 kbps: {params.target_bitrate_kbps}")
    if params.enhance_on:
        missing = [k for k in DEFAULT_ENHANCE_PARAMS if k not in params.enhance_params]
        if missing:
            raise ValueError(f"enhance_params 缺键: {missing}")
        _validate_enhance_params(params.enhance_params)
    if not -12.0 <= float(params.volume_db) <= 12.0:
        raise ValueError(f"音量增益须在 ±12dB 内: {params.volume_db}")


def _validate_enhance_params(ep: dict) -> None:
    """增强链参数受控范围（批3 旋钮化，决策九-1：各带受控范围校验）。

    - hqdn3d=「luma_sp:chroma_sp:luma_tmp:chroma_tmp」四数值，各 0~10；
    - deblock=「alpha=X:beta=Y」，X/Y 各 0~1；
    - unsharp=「lx:ly:la:cx:cy:ca」六数值，luma/croma amount 各 0~2。
    超范围 ValueError（人话含滤镜名）。"""
    def _floats(s: str, n: int) -> list[float]:
        parts = str(s).split(":")
        if len(parts) != n:
            raise ValueError(f"参数段数应为 {n}: {s!r}")
        vals = []
        for p in parts:
            key, _, v = p.partition("=") if "=" in p else ("", "", p)
            try:
                vals.append((key, float(v)))
            except ValueError:
                raise ValueError(f"参数非数值: {s!r}") from None
        return vals

    hq_vals = _floats(ep.get("hqdn3d", ""), 4)
    for i, (_k, v) in enumerate(hq_vals):
        if not 0 <= v <= 10:
            raise ValueError(f"hqdn3d 参数超范围（0~10）: [{i}]={v}")
    deb = _floats(ep.get("deblock", ""), 2)
    for k, v in deb:
        if not 0 <= v <= 1:
            raise ValueError(f"deblock {k} 超范围（0~1）: {v}")
    us = _floats(ep.get("unsharp", ""), 6)
    for i, (_k, v) in enumerate(us):
        if i in (2, 5) and not 0 <= v <= 2:
            raise ValueError(f"unsharp amount 超范围（0~2）: {v}")
        if i in (2, 5):
            continue
        if not 1 <= v <= 32:
            raise ValueError(f"unsharp 尺寸超范围（1~32）: {v}")


def reference_bitrate_kbps(video_format: str, resolution: str, quality: str) -> int:
    """VBR 码率参考表（kbps）：1080p 基准 × 像素比例 × 档位系数，取整。

    resolution=original 无源尺寸可依，回落 1080p 比例 1.0（磁盘估算口径一致）。
    """
    base = int(_REFERENCE_BITRATE_1080P[video_format])
    width, height = _RESOLUTION_SIZES.get(resolution, (1920, 1080))
    tier = _TIER_FACTOR.get(quality, 1.0)
    return int(round(base * (width * height) / _1080P_PIXELS * tier))


def speed_factor(video_format: str, quality: str, backend: str = "auto") -> float:
    """编码耗时系数（编码耗时 ≈ k × 时长，spike 冻结表）；未知组合回落均衡档。

    backend=gpu 走 GPU 系数（决策 ETA 分档 GPU≈1/5-8，保守 0.25）。"""
    if backend == "gpu":
        return _GPU_SPEED_FACTOR
    return _SPEED_FACTOR.get(video_format, {}).get(quality, _SPEED_FACTOR[video_format]["balanced"])


def gpu_encoder_chain(video_format: str) -> list[tuple[str, str]]:
    """GPU 编码器候选链（nvenc→qsv→amf，amf 无 av1；决策 MVP）。"""
    return _GPU_ENCODER_CHAIN[video_format]


def gpu_family(encoder_name: str) -> str:
    """由编码器名判族（nvenc/qsv/amf），未知名回空。"""
    if encoder_name.endswith("_nvenc"):
        return "nvenc"
    if encoder_name.endswith("_qsv"):
        return "qsv"
    if encoder_name.endswith("_amf"):
        return "amf"
    return ""


def escape_subtitles_path(path: str) -> str:
    """subtitles 滤镜的 Windows 路径转义：``\\``→``/``、``:``→``\\:``。

    spike 实测可用（批清单执行记录 2）；配单引号包裹喂 ffmpeg 滤镜解析器。
    """
    return path.replace("\\", "/").replace(":", "\\:")


def _build_filter_chain(params: EncodeParams, subtitle_path: str) -> str:
    """滤镜链组装（顺序固定，链尾 yuv420p 收口；顺序即契约，测试钉）。"""
    parts: list[str] = []
    faithful = not params.enhance_on
    need_resize = params.resolution != "original"
    if not faithful:
        parts.append("colormatrix=bt470bg:bt709")
    if need_resize:
        width, height = _RESOLUTION_SIZES[params.resolution]
        parts.append(f"scale={width}:{height}:flags=lanczos")
        parts.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black")
        # A6 裁定：setsar 属缩放链不是增强链——faithful 但 scale/pad 生效时保留
        parts.append("setsar=1/1")
    if not faithful:
        ep = params.enhance_params
        parts.append(f"hqdn3d={ep['hqdn3d']}")
        parts.append(f"deblock={ep['deblock']}")
        parts.append(f"unsharp={ep['unsharp']}")
    style = _FORCE_STYLE_TEMPLATE.format(font_size=int(params.font_size))
    parts.append(f"subtitles='{escape_subtitles_path(subtitle_path)}':force_style='{style}'")
    parts.append("format=yuv420p")  # 8bit 链尾收口（决策八-1，常量+钉）
    return ",".join(parts)


def build_ffmpeg_args(
    params: EncodeParams,
    media_path: str,
    subtitle_path: str,
    duration_s: float,
    has_audio: bool,
    audio_codec: str,
    gpu_encoder: str = "",
) -> tuple[list[str], str]:
    """组装 ffmpeg argv（不含 exe 本体；队列层在前拼接 ffmpeg 路径）。

    返回 ``(args, audio_fall_back)``：``audio_fall_back`` 为空串=音频 copy
    未回落；非空=回落原因（人话，C6），调用方透出 UI。

    ``duration_s`` 当前不进 argv（码控不随时长变），保留签名供批3 音量/
    2-pass 候选与队列层统一入口；ffmpeg 直写 ``params.out_path``（队列层
    传 .part 路径实现原子成片）。``-progress pipe:1`` 固定注入（队列解析
    out_time_ms 实为微秒，api._transcode_sync 先例）。

    ``gpu_encoder``：backend=gpu 时必填（供给层双检解析产物，如
    hevc_nvenc）；backend=auto/cpu 传空。GPU 码控映射见 ``_GPU_FAMILIES``
    （nvenc=VBR 派生+p6/p7+tune hq，owner AV1.xml 实锚；qsv=global_quality+
    slower，owner HQ.xml 实锚；amf=quality 三挡占位未实测）。
    """
    validate_params(params)
    if not params.out_path:
        raise ValueError("缺少输出路径 out_path")
    if params.backend == "gpu" and gpu_family(gpu_encoder) not in ("nvenc", "qsv", "amf"):
        raise ValueError(f"GPU 后端需要供给层解析的编码器名，得到: {gpu_encoder!r}")

    args: list[str] = ["-i", media_path]
    # 固定注入（生成者=core）：容器/快启/去字幕流/主视频轨
    args += ["-f", "mp4", "-movflags", "+faststart", "-sn", "-map", "0:v:0"]

    audio_fall_back = ""
    if has_audio:
        args += ["-map", "0:a:0"]
        want_volume = abs(float(params.volume_db or 0.0)) > 1e-9
        if params.audio_mode == "copy" and not want_volume:
            if (audio_codec or "").lower() in _AUDIO_COPY_WHITELIST:
                args += ["-c:a", "copy"]
            else:
                args += ["-c:a", "aac", "-b:a", "128k"]
                audio_fall_back = (
                    f"源音频编码 {audio_codec or '未知'} 不在 copy 白名单"
                    f"（{'/'.join(sorted(_AUDIO_COPY_WHITELIST))}），已回落 AAC 128k"
                )
        elif params.audio_mode == "copy" and want_volume:
            # 音量增益需重编码（copy 流不可挂滤镜）；增益归 aac 128k 档
            args += ["-c:a", "aac", "-b:a", "128k"]
            audio_fall_back = (
                f"已设置音量增益 {params.volume_db:+g}dB，音频需重编码"
                "（AAC 128k，直接复制与音量调整不可兼得）")
        else:
            args += ["-c:a", "aac", "-b:a", params.audio_mode]
        if want_volume:
            # 批3 音量旋钮（生成者=volume；±12dB 受控旋钮，决策 MVP）
            args += ["-af", f"volume={float(params.volume_db):g}dB"]

    if params.backend == "gpu":
        family = gpu_family(gpu_encoder)
        args += ["-c:v", gpu_encoder]
        table = _GPU_FAMILIES[family].get(params.video_format)
        if table is None:
            raise ValueError(f"{family} 无 {params.video_format} 编码器（该组合不可用）")
        preset_v, quality_v = table[params.quality]
        if family == "nvenc":
            # owner AV1.xml 实锚形态：VBR b:v 派生 + maxrate/bufsize 1.45×/2.9×
            kbps = params.target_bitrate_kbps or reference_bitrate_kbps(
                params.video_format, params.resolution, params.quality)
            args += ["-preset", preset_v, "-tune", "hq", "-rc", "vbr",
                     "-b:v", f"{kbps}k",
                     "-maxrate", f"{int(kbps * _VBR_MAXRATE_RATIO)}k",
                     "-bufsize", f"{int(kbps * _VBR_BUFSIZE_RATIO)}k"]
        elif family == "qsv":
            args += ["-preset", preset_v, "-global_quality", str(quality_v)]
        else:   # amf（占位，未实测——决策 MVP 标注）
            args += ["-quality", preset_v]
            kbps = params.target_bitrate_kbps or reference_bitrate_kbps(
                params.video_format, params.resolution, params.quality)
            args += ["-rc", "vbr_peak", "-b:v", f"{kbps}k",
                     "-maxrate", f"{int(kbps * _VBR_MAXRATE_RATIO)}k",
                     "-bufsize", f"{int(kbps * _VBR_BUFSIZE_RATIO)}k"]
    elif params.rate_mode == "target_vbr":
        kbps = params.target_bitrate_kbps or reference_bitrate_kbps(
            params.video_format, params.resolution, params.quality)
        args += [
            "-c:v", _VIDEO_CODECS[params.video_format],
            "-b:v", f"{kbps}k",
            "-maxrate", f"{int(kbps * _VBR_MAXRATE_RATIO)}k",
            "-bufsize", f"{int(kbps * _VBR_BUFSIZE_RATIO)}k",
            "-preset", _BALANCED_PRESET[params.video_format],
        ]
    else:
        crf, preset = _RATE_CONTROL[params.video_format][params.quality]
        args += ["-c:v", _VIDEO_CODECS[params.video_format],
                 "-crf", str(crf), "-preset", preset]

    args += ["-vf", _build_filter_chain(params, subtitle_path)]
    # 逃生门：三层黑名单校验通过才 append（命中抛 BannedFlagError）
    args += parse_custom_params(params.custom_params)
    args += ["-progress", "pipe:1", "-y", params.out_path]
    return args, audio_fall_back


# ---------------------------------------------------------------------------
# 黑名单三层契约（HRO-2）：仅约束用户 custom_params，程序生成者不受限
# ---------------------------------------------------------------------------


class BannedFlagError(ValueError):
    """custom_params 命中黑名单/别名/守卫（消息含旗标名）。"""


# canonical 归一集：原十五件套 + 轮4 六件 + 本轮四件 + HRO-2 补充 + 批2 GPU
# 程序特权旗标（41 件）；黑名单只约束用户逃生门，程序侧不受限
_BANNED_CANONICAL = frozenset({
    "-i", "-f", "-c:v", "-c:a", "-c:s", "-vf", "-filter:v", "-map",
    "-ss", "-t", "-to", "-y", "-n", "-metadata", "-map_metadata",
    "-preset", "-rc", "-cq", "-qp", "-b:v", "-b:a",
    "-an", "-sn", "-dn", "-af",
    "-pix_fmt", "-filter_complex", "-c", "-vcodec", "-acodec",
    "-profile:v", "-x264-params", "-x265-params", "-svtav1-params",
    "-movflags", "-r", "-fps_mode", "-codec",
    # 批2 GPU 码控映射程序特权旗标（用户覆盖会破坏 nvenc/qsv/amf 映射契约）
    "-tune", "-global_quality", "-quality",
})

# 别名归一表：别名 → canonical，归一后查 canonical 集
_FLAG_ALIASES = {
    "-codec:v": "-c:v",
    "-vcodec": "-c:v",
    "-acodec": "-c:a",
    "-codec:a": "-c:a",
    "-codec:s": "-c:s",
    "-filter:v": "-vf",
    "-pix_fmts": "-pix_fmt",
}

# 不变式守卫（独立于名单，守恒式而非枚举）：
# - pix_fmt 系任何值即拒（10bit 零残留钉，不认可接受的 8bit 值特例）；
# - filter 系只认注册生成者，用户注入滤镜一律拒。
_GUARD_PIX_FMT_FLAGS = frozenset({"-pix_fmt"})
_GUARD_FILTER_FLAGS = frozenset({"-vf", "-filter_complex"})

# 取值型旗标（消费其值再继续，防值以 - 开头被误判为下一旗标）
_VALUE_FLAGS = frozenset({
    *_BANNED_CANONICAL - {"-y", "-n", "-an", "-sn", "-dn"},
    *_FLAG_ALIASES,
    "-crf", "-tune", "-threads", "-loglevel", "-level", "-flags",
    "-tag:v", "-tag:a",
})


def parse_custom_params(s: str) -> list[str]:
    """解析逃生门字符串为 argv 片段；命中黑名单整单拒绝（BannedFlagError）。

    词法（C7）：shlex(posix=False) + ``commenters=''``（``#`` 不作注释，防
    参数值被静默截断）+ whitespace_split；逐 token 去成对首尾包裹引号。
    """
    lexer = shlex.shlex(s, posix=False)
    lexer.commenters = ""
    lexer.whitespace_split = True
    tokens = list(lexer)
    result: list[str] = []
    i = 0
    while i < len(tokens):
        tok = tokens[i]
        if len(tok) >= 2 and tok[0] == tok[-1] and tok[0] in "\"'":
            tok = tok[1:-1]
        if tok.startswith("-") and tok != "-":
            canonical = _FLAG_ALIASES.get(tok, tok)
            if canonical in _GUARD_PIX_FMT_FLAGS:
                raise BannedFlagError(
                    f"自定义参数包含 {tok}（归一为 {canonical}；"
                    "像素格式已冻结 8bit yuv420p，10bit 零残留）")
            if canonical in _GUARD_FILTER_FLAGS:
                raise BannedFlagError(
                    f"自定义参数包含滤镜旗标 {tok}（归一为 {canonical}；"
                    "滤镜链只认程序注册生成者）")
            if canonical in _BANNED_CANONICAL:
                if canonical != tok:
                    raise BannedFlagError(
                        f"自定义参数包含被禁旗标 {tok}（归一为 {canonical}）")
                raise BannedFlagError(f"自定义参数包含被禁旗标 {tok}")
            # 取值型旗标：消费其值（值不参与旗标校验）
            if canonical in _VALUE_FLAGS and i + 1 < len(tokens):
                value = tokens[i + 1]
                if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                    value = value[1:-1]
                result.append(tok)
                result.append(value)
                i += 2
                continue
        result.append(tok)
        i += 1
    return result


# 生成者注册表（程序侧旗标声明；自洽钉见 assert_generators_consistent）。
# - core：核心构建（容器/映射/码控/音频）
# - subtitles / enhance：均只产出 -vf 滤镜串内容（串内内容非旗标）
# - gpu：批2 硬件后端（nvenc/qsv/amf 码控映射；程序特权旗标含黑名单成员
#   ——黑名单只约束用户逃生门，程序侧不受限）
# - 批3 预留：音量增益（-af 生成者）届时注册
_GENERATOR_REGISTRY: dict[str, frozenset] = {
    "core": frozenset({
        "-f", "-movflags", "-sn", "-map", "-c:v", "-crf", "-preset",
        "-b:v", "-maxrate", "-bufsize", "-c:a", "-b:a",
    }),
    "subtitles": frozenset({"-vf"}),
    "enhance": frozenset({"-vf"}),
    "gpu": frozenset({
        "-c:v", "-preset", "-tune", "-rc", "-b:v", "-maxrate", "-bufsize",
        "-global_quality", "-quality",
    }),
}

# 非受限旗标：不进注册表的结构性 IO 项（-i/-y/-progress）与程序 VBR 三元组
# 伴生项（-maxrate/-bufsize，canonic 黑名单有意不收）与用户可自由覆写的
# 自由项（-crf，黑名单有意不收）；生成者声明 ⊆ banned ∪ 非受限。
_UNRESTRICTED_FLAGS = frozenset({"-i", "-y", "-progress", "-crf", "-maxrate", "-bufsize"})


def assert_generators_consistent() -> None:
    """注册制自洽钉（测试调用）：声明旗标 ⊆ banned ∪ 非受限，且全参数
    空间（3 格式 × 2 码控 × 有无音轨）下 build 实际产出的旗标均被某生成者
    声明或属非受限——程序侧多产出未注册旗标即 AssertionError。"""
    declared: set[str] = set()
    for flags in _GENERATOR_REGISTRY.values():
        declared |= flags
    unknown = declared - _BANNED_CANONICAL - _UNRESTRICTED_FLAGS
    if unknown:
        raise AssertionError(f"生成者注册了未知类别旗标: {sorted(unknown)}")

    emitted: set[str] = set()
    for video_format in _VIDEO_CODECS:
        for rate_mode in ("quality_tier", "target_vbr"):
            for has_audio in (True, False):
                params = EncodeParams(video_format=video_format, rate_mode=rate_mode,
                                      out_path="D:/out/x_hardsub.mp4")
                args, _ = build_ffmpeg_args(params, "D:/in/x.mp4", "D:/in/x.srt",
                                            60.0, has_audio, "aac")
                emitted |= {a for a in args if a.startswith("-") and a != "-"}
    # GPU 空间（批2）：逐族逐格式逐档——amf/av1 组合不可用（映射表 None）
    for chain_name, _family in (("h264_nvenc", "nvenc"), ("h264_qsv", "qsv"),
                                ("h264_amf", "amf")):
        for quality in ("compress", "balanced", "quality"):
            for rate_mode in ("quality_tier", "target_vbr"):
                params = EncodeParams(video_format="h264", rate_mode=rate_mode,
                                      backend="gpu", quality=quality,
                                      out_path="D:/out/x_hardsub.mp4")
                args, _ = build_ffmpeg_args(params, "D:/in/x.mp4", "D:/in/x.srt",
                                            60.0, True, "aac", gpu_encoder=chain_name)
                emitted |= {a for a in args if a.startswith("-") and a != "-"}
    unregistered = emitted - declared - _UNRESTRICTED_FLAGS
    if unregistered:
        raise AssertionError(f"构建产出未注册旗标: {sorted(unregistered)}")
