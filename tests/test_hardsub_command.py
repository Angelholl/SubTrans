"""hardsub 命令构建单测（2.8.0 批1 件4 测试，D2026-1007-03）。

覆盖批清单验收门 2：命令矩阵钉（3 格式×3 档×tier/VBR×分辨率挡）、
faithful 链（A6）、yuv420p 链尾钉、10bit 零残留钉、黑名单三层契约
（25 件 canonical 逐件+每别名+pix_fmt/filter 守卫）、parse 词法
（C7：引号/含#值/反斜杠路径）、gpu 显式拒绝（A9）、音频 copy 白名单
回落（C6）、码率表锚（A8）、faststart 常量、注册制自洽。

纯函数直测，零 ffmpeg/网络依赖。
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from subtransjav.refine.hardsub import (  # noqa: E402
    BannedFlagError,
    EncodeParams,
    assert_generators_consistent,
    build_ffmpeg_args,
    escape_subtitles_path,
    parse_custom_params,
    reference_bitrate_kbps,
    speed_factor,
    validate_params,
)

_FORMAT_CODECS = {"h264": "libx264", "h265": "libx265", "av1": "libsvtav1"}


def _params(**kw) -> EncodeParams:
    base = dict(out_path="D:/out/a_hardsub.mp4")
    base.update(kw)
    return EncodeParams(**base)


def _build(**kw):
    args, fall = build_ffmpeg_args(_params(**kw), "D:/vid/a.mp4", "D:/sub/a.srt",
                                   100.0, True, "aac")
    return args, fall


def _vf(args) -> str:
    return args[args.index("-vf") + 1]


# ---------------------------------------------------------------------------
# 命令矩阵：画质三档（quality_tier）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fmt,quality,crf,preset", [
    ("h264", "compress", "28", "slower"),
    ("h264", "balanced", "23", "medium"),
    ("h264", "quality", "20", "slow"),
    ("h265", "compress", "30", "slower"),
    ("h265", "balanced", "26", "medium"),
    ("h265", "quality", "22", "slow"),
    ("av1", "compress", "55", "6"),
    ("av1", "balanced", "45", "8"),
    ("av1", "quality", "35", "10"),
])
def test_tier_matrix(fmt, quality, crf, preset):
    args, fall = _build(video_format=fmt, quality=quality, rate_mode="quality_tier")
    assert fall == ""
    assert args[args.index("-c:v") + 1] == _FORMAT_CODECS[fmt]
    assert args[args.index("-crf") + 1] == crf
    assert args[args.index("-preset") + 1] == preset
    assert "-b:v" not in args


# ---------------------------------------------------------------------------
# 命令矩阵：target_vbr（b:v/maxrate/bufsize + 均衡档 preset）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fmt", ["h264", "h265", "av1"])
@pytest.mark.parametrize("quality,factor", [("compress", 0.75), ("balanced", 1.0), ("quality", 1.35)])
def test_vbr_matrix(fmt, quality, factor):
    kbps = reference_bitrate_kbps(fmt, "1080p", quality)
    args, _ = _build(video_format=fmt, quality=quality, resolution="1080p",
                     rate_mode="target_vbr")
    assert args[args.index("-b:v") + 1] == f"{kbps}k"
    assert args[args.index("-maxrate") + 1] == f"{int(kbps * 1.45)}k"
    assert args[args.index("-bufsize") + 1] == f"{int(kbps * 2.9)}k"
    assert args[args.index("-preset") + 1] == {"h264": "medium", "h265": "medium", "av1": "8"}[fmt]
    assert "-crf" not in args


def test_vbr_manual_target_bitrate_overrides():
    """手改只动 b:v（maxrate/bufsize 仍按比例派生）。"""
    args, _ = _build(rate_mode="target_vbr", target_bitrate_kbps=8000)
    assert args[args.index("-b:v") + 1] == "8000k"
    assert args[args.index("-maxrate") + 1] == f"{int(8000 * 1.45)}k"


# ---------------------------------------------------------------------------
# 分辨率挡：scale/pad/setsar
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("res,w,h", [
    ("720p", 1280, 720), ("1080p", 1920, 1080),
    ("1440p", 2560, 1440), ("2160p", 3840, 2160),
])
def test_resolution_scale_pad_setsar(res, w, h):
    vf = _vf(_build(resolution=res)[0])
    assert f"scale={w}:{h}:flags=lanczos" in vf
    assert f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black" in vf
    assert "setsar=1/1" in vf


def test_original_no_scale():
    vf = _vf(_build(resolution="original")[0])
    assert "scale=" not in vf and "pad=" not in vf
    assert "colormatrix=bt470bg:bt709" in vf  # 增强链开时 colormatrix 在


# ---------------------------------------------------------------------------
# 忠实源出口（enhance_on=False）与 A6
# ---------------------------------------------------------------------------
def test_faithful_original_no_enhance_chain():
    vf = _vf(_build(enhance_on=False, resolution="original")[0])
    for banned in ("colormatrix", "hqdn3d", "deblock", "unsharp", "setsar"):
        assert banned not in vf
    assert vf.startswith("subtitles=")
    assert vf.endswith("format=yuv420p")


def test_faithful_keeps_setsar_when_scaling():  # A6 裁定
    vf = _vf(_build(enhance_on=False, resolution="1080p")[0])
    assert "setsar=1/1" in vf
    assert "scale=1920:1080:flags=lanczos" in vf
    assert "hqdn3d" not in vf and "colormatrix" not in vf


# ---------------------------------------------------------------------------
# yuv420p 链尾钉 + 10bit 零残留钉
# ---------------------------------------------------------------------------
def test_yuv420p_chain_tail():
    vf = _vf(_build()[0])
    assert vf.endswith("format=yuv420p")


def test_10bit_zero_residue():
    """全参数空间下 argv 不出现任何 pix_fmt 痕迹（10bit 整体删除，决策八-1）。"""
    for fmt in ("h264", "h265", "av1"):
        for rate_mode in ("quality_tier", "target_vbr"):
            for enhance in (True, False):
                args, _ = _build(video_format=fmt, rate_mode=rate_mode, enhance_on=enhance)
                joined = " ".join(args)
                assert "pix_fmt" not in joined
                assert "10le" not in joined and "yuv420p10le" not in joined


# ---------------------------------------------------------------------------
# 黑名单三层契约
# ---------------------------------------------------------------------------
_BANNED_25 = [
    "-i", "-f", "-c:v", "-c:a", "-c:s", "-vf", "-filter:v", "-map",
    "-ss", "-t", "-to", "-y", "-n", "-metadata", "-map_metadata",
    "-preset", "-rc", "-cq", "-qp", "-b:v", "-b:a",
    "-an", "-sn", "-dn", "-af",
]


@pytest.mark.parametrize("flag", _BANNED_25)
def test_banned_canonical_rejected(flag):
    with pytest.raises(BannedFlagError) as ei:
        parse_custom_params(f"{flag} v")
    assert flag in str(ei.value)


@pytest.mark.parametrize("alias,canonical", [
    ("-codec:v", "-c:v"), ("-vcodec", "-c:v"), ("-acodec", "-c:a"),
    ("-codec:a", "-c:a"), ("-codec:s", "-c:s"), ("-filter:v", "-vf"),
    ("-pix_fmts", "-pix_fmt"),
])
def test_alias_normalized_then_rejected(alias, canonical):
    with pytest.raises(BannedFlagError) as ei:
        parse_custom_params(f"{alias} v")
    assert canonical in str(ei.value)


@pytest.mark.parametrize("s", [
    "-pix_fmt yuv420p10le",
    "-pix_fmt yuv420p",       # 任何值即拒：8bit 特例也不放行
    "-pix_fmts gray",
])
def test_pix_fmt_guard_any_value_rejected(s):
    with pytest.raises(BannedFlagError) as ei:
        parse_custom_params(s)
    assert "pix_fmt" in str(ei.value)


def test_filter_complex_guard_rejected():
    with pytest.raises(BannedFlagError) as ei:
        parse_custom_params('-filter_complex "[0:v]scale=100:100"')
    assert "-filter_complex" in str(ei.value)


def test_banned_flag_error_is_value_error():
    assert issubclass(BannedFlagError, ValueError)


def test_build_rejects_banned_custom_params():
    with pytest.raises(BannedFlagError):
        build_ffmpeg_args(_params(custom_params="-preset veryfast"),
                          "D:/vid/a.mp4", "D:/sub/a.srt", 10.0, True, "aac")


# ---------------------------------------------------------------------------
# parse 词法（C7）
# ---------------------------------------------------------------------------
def test_parse_hash_not_comment():
    assert parse_custom_params("-crf 18 # not comment") == ["-crf", "18", "#", "not", "comment"]


def test_parse_dequotes_wrapped_tokens():
    assert parse_custom_params("'-crf' \"18\"") == ["-crf", "18"]


def test_parse_backslash_path_untouched():
    toks = parse_custom_params(r'-tune "D:\dir a\b.mp4"')
    assert toks == ["-tune", r"D:\dir a\b.mp4"]


def test_custom_params_appended_before_output():
    args, _ = _build(custom_params="-crf 18")
    assert args[-6:-4] == ["-crf", "18"]
    assert args[-2:] == ["-y", "D:/out/a_hardsub.mp4"]


# ---------------------------------------------------------------------------
# backend=gpu 显式拒绝（A9）
# ---------------------------------------------------------------------------
def test_gpu_rejected_not_silent():
    with pytest.raises(ValueError) as ei:
        validate_params(_params(backend="gpu"))
    assert "GPU 后端将在 2.8.0 批2 提供" in str(ei.value)
    with pytest.raises(ValueError, match="GPU"):
        build_ffmpeg_args(_params(backend="gpu"), "D:/vid/a.mp4", "D:/sub/a.srt",
                          1.0, True, "aac")


def test_font_size_range():
    validate_params(_params(font_size=12))
    validate_params(_params(font_size=72))
    with pytest.raises(ValueError, match="12~72"):
        validate_params(_params(font_size=11))
    with pytest.raises(ValueError, match="12~72"):
        validate_params(_params(font_size=73))


# ---------------------------------------------------------------------------
# 音频：copy 白名单 / 回落 / 档位 / 无音轨（C6）
# ---------------------------------------------------------------------------
def test_audio_copy_whitelisted():
    args, fall = build_ffmpeg_args(_params(), "D:/v.mp4", "D:/s.srt", 10.0, True, "ac3")
    assert args[args.index("-c:a") + 1] == "copy"
    assert fall == ""


def test_audio_copy_fallback_to_aac():
    args, fall = build_ffmpeg_args(_params(), "D:/v.mp4", "D:/s.srt", 10.0, True, "opus")
    assert args[args.index("-c:a") + 1] == "aac"
    assert args[args.index("-b:a") + 1] == "128k"
    assert "opus" in fall  # 回落原因随返回值透出


def test_audio_bitrate_tiers():
    for mode in ("96k", "128k", "192k"):
        args, fall = build_ffmpeg_args(_params(audio_mode=mode), "D:/v.mp4", "D:/s.srt",
                                       10.0, True, "aac")
        assert args[args.index("-b:a") + 1] == mode
        assert fall == ""


def test_no_audio_stream_omits_audio_args():
    args, fall = build_ffmpeg_args(_params(), "D:/v.mp4", "D:/s.srt", 10.0, False, "")
    assert "0:a:0" not in args
    assert "-c:a" not in args
    assert fall == ""


# ---------------------------------------------------------------------------
# 固定注入与字幕样式
# ---------------------------------------------------------------------------
def test_fixed_injection_and_faststart():
    args, _ = _build()
    assert args[:2] == ["-i", "D:/vid/a.mp4"]
    assert args[args.index("-f") + 1] == "mp4"
    assert args[args.index("-movflags") + 1] == "+faststart"
    assert "-sn" in args
    assert args.count("-map") == 2
    assert "0:v:0" in args and "0:a:0" in args
    assert args[args.index("-progress") + 1] == "pipe:1"
    assert args[-2:] == ["-y", "D:/out/a_hardsub.mp4"]


def test_subtitle_force_style_and_escape():
    vf = _vf(_build(font_size=30)[0])
    assert "subtitles='D\\:/sub/a.srt':" in vf
    assert "Fontname=Microsoft YaHei,Bold=1,Fontsize=30" in vf
    assert "Outline=2.5,Shadow=2.5,Alignment=2" in vf
    assert "MarginL=10,MarginR=10,MarginV=20,Encoding=1" in vf
    assert escape_subtitles_path(r"D:\v\a b.srt") == "D\\:/v/a b.srt"


# ---------------------------------------------------------------------------
# 冻结表钉
# ---------------------------------------------------------------------------
def test_reference_bitrate_anchor_1080p_av1_balanced():  # A8
    assert abs(reference_bitrate_kbps("av1", "1080p", "balanced") - 3113) <= 1


def test_reference_bitrate_scaling():
    assert reference_bitrate_kbps("h264", "1080p", "balanced") == 5500
    assert reference_bitrate_kbps("h264", "720p", "balanced") == \
        int(round(5500 * (1280 * 720) / (1920 * 1080)))
    assert reference_bitrate_kbps("av1", "1080p", "compress") == int(round(3113 * 0.75))
    assert reference_bitrate_kbps("av1", "1080p", "quality") == int(round(3113 * 1.35))


def test_speed_factor_frozen_table():  # spike 实测冻结值
    assert speed_factor("h264", "compress") == 0.51
    assert speed_factor("h264", "balanced") == 0.39
    assert speed_factor("h264", "quality") == 1.0
    assert speed_factor("h265", "compress") == 3.93
    assert speed_factor("h265", "balanced") == 0.57
    assert speed_factor("h265", "quality") == 1.14
    assert speed_factor("av1", "compress") == 0.54
    assert speed_factor("av1", "balanced") == 0.45
    assert speed_factor("av1", "quality") == 0.37


# ---------------------------------------------------------------------------
# 注册制自洽钉
# ---------------------------------------------------------------------------
def test_generator_registry_consistent():
    assert_generators_consistent()  # 多产出未注册旗标/注册未知类别即 AssertionError
