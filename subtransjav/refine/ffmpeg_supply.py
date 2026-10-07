"""ffmpeg 供给与能力探测（2.8.0 批1 件2，D2026-1007-03）。

背景事实（spike 实测，批清单执行记录 1）：上游环境自带的 ffmpeg 常不带
libass——「已有 ffmpeg」≠「能烧字幕」。因此能力探测（libass / subtitles
滤镜 / 编码器齐套）是硬字幕主路径保障而非低频兜底；缺口时从 BtbN/
FFmpeg-Builds 固定制品下载 full 变体落位数据根（HRO-1 裁定：gyan full 仅
.7z 且无 7z 依赖，弃；BtbN .zip stdlib zipfile 可解，零新依赖）。

sha256 pin 为 TOFU（Trust On First Use，B3）：首下即钉、记档于批清单执行
记录；此后每次下载比对 pin，不符即拒（SupplyChecksumError），不静默放行。

约束：错误类型全部本模块自定义（SupplyError 基类，不 import dict_manager
异常）；subprocess 一律 list-args + CREATE_NO_WINDOW（单一来源
utils.subprocess_flags）+ 30s 超时（run_with_timeout_tree 树杀）；下载走
https + 域白名单逐跳校验（dict_manager._validate_url :378 /
_DictGuardedRedirectHandler :416 同构独立实现，勿 import 复用）。
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import os
import shutil
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass, field

from subtransjav import paths
from subtransjav.refine import asr_env
from subtransjav.utils.process_manager import run_with_timeout_tree

__all__ = [
    "FfprobeError",
    "MediaInfo",
    "SupplyChecksumError",
    "SupplyDiskError",
    "SupplyDownloadError",
    "SupplyError",
    "SupplyResult",
    "SupplyStopped",
    "download_full_variant",
    "probe_media",
    "resolve_hardsub_ffmpeg",
]

# ---------------------------------------------------------------------------
# 供给 pin（TOFU，spike 2026-10-07 实测冻结；换 tag 须重新实测并回写批清单）
# ---------------------------------------------------------------------------

_PINNED_URL = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/"
               "autobuild-2026-10-06-13-06/ffmpeg-N-127222-g151814650f-win64-gpl.zip")
_PINNED_SHA256 = "8428c7e0d3c5faf21714a8fa7c9663b78a74fc1ee166777771daee03753f4929"
_PINNED_BYTES = 200217553

# 白名单实测跳转链定集（spike：302 落 release-assets，非 objects.githubusercontent.com）；
# 扩面须回评议（风险跟踪）
_URL_HOST_ALLOW = {"github.com", "release-assets.githubusercontent.com"}

_DOWNLOAD_CHUNK = 1024 * 1024
_TOOL_TIMEOUT_S = 30.0

_ZIP_NAME = "ffmpeg-full.zip.downloading"


class SupplyError(Exception):
    """ffmpeg 供给层错误基类（本模块自定义，不复用词典/模型下载异常）。"""


class SupplyDiskError(SupplyError):
    """磁盘空间预检失败（fail-closed）。"""


class SupplyDownloadError(SupplyError):
    """网络层/下载完整性/zip 结构错误。"""


class SupplyChecksumError(SupplyError):
    """sha256 与 pin 不符（TOFU 校验失败）。"""


class SupplyStopped(SupplyError):
    """协作式停止（stop_event 置位）。"""


class FfprobeError(ValueError):
    """ffprobe 探测失败（不可用/非 JSON/关键字段缺失）。"""


@dataclass
class SupplyResult:
    """能力解析结果：missing 非空即无候选满足（不抛，由调用方引导下载）。"""

    ffmpeg_path: str
    ffprobe_path: str
    capability: dict = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)


@dataclass
class MediaInfo:
    """媒体探测结果（供超时预估/磁盘预检/码率表派生/音轨判定）。"""

    duration_s: float
    width: int
    height: int
    bit_rate_bps: int
    has_audio: bool
    audio_codec: str


# ---------------------------------------------------------------------------
# 工具执行与能力探测
# ---------------------------------------------------------------------------


def _run_tool(cmd: list[str]) -> tuple[int, str, str]:
    """探测用子进程统一入口：list-args + CREATE_NO_WINDOW + 30s 树杀超时。

    返回 (returncode, stdout, stderr)；run_with_timeout_tree 超时不抛，
    击杀后的 returncode 可能为 None，归一为 -1。
    """
    res = run_with_timeout_tree(cmd, _TOOL_TIMEOUT_S, text=True,
                                encoding="utf-8", errors="replace")
    rc = res.returncode if res.returncode is not None else -1
    return rc, res.stdout or "", res.stderr or ""


def _parse_tool_names(text: str, skip_prefixes: tuple[str, ...]) -> set[str]:
    """-encoders / -filters 输出解析：跳过表头/图例行，取第二列为名字。"""
    names: set[str] = set()
    for line in text.splitlines():
        s = line.strip()
        if not s or any(s.startswith(p) for p in skip_prefixes):
            continue
        if set(s) <= {"-", " ", ".", "─"}:  # 分隔线
            continue
        parts = s.split()
        if len(parts) >= 2 and parts[1] != "=":  # "=" 为图例行（" A..... = Audio"）
            names.add(parts[1])
    return names


def _probe_capability(exe: str, runner=None) -> dict:
    """能力探测：-version（libass）+ -encoders + -filters（滤镜齐套）。

    ``runner`` 可注入（测试用 fake runner 返回文本）；签名
    ``runner(cmd) -> (rc, stdout, stderr)``。
    """
    run = runner or _run_tool
    rc_v, out_v, _ = run([exe, "-version"])
    rc_e, out_e, _ = run([exe, "-encoders"])
    rc_f, out_f, _ = run([exe, "-filters"])
    return {
        "version_ok": rc_v == 0,
        "libass": "enable-libass" in out_v,
        "encoders": _parse_tool_names(out_e, ("Encoders:",)),
        "filters": _parse_tool_names(out_f, ("Filters:",)),
    }


# 探测结果缓存：按 (normcase 绝对路径, mtime)——二进制被下载覆盖后 mtime
# 变化自动失效；进程内 dict 即可，无持久化需求
_CAPABILITY_CACHE: dict[tuple[str, float], dict] = {}


def _probe_capability_cached(exe: str, runner=None) -> dict:
    try:
        mtime = os.path.getmtime(exe)
    except OSError:
        mtime = -1.0
    key = (os.path.normcase(os.path.abspath(exe)), mtime)
    hit = _CAPABILITY_CACHE.get(key)
    if hit is not None:
        return hit
    cap = _probe_capability(exe, runner)
    _CAPABILITY_CACHE[key] = cap
    return cap


def _resolve_ffprobe(ffmpeg_path: str) -> str:
    """ffprobe 定位：所选 ffmpeg 同目录优先（保证版本配对），缺则 PATH。"""
    if ffmpeg_path:
        cand = os.path.join(os.path.dirname(ffmpeg_path), "ffprobe.exe")
        if os.path.isfile(cand):
            return cand
    return shutil.which("ffprobe") or ""


def resolve_hardsub_ffmpeg(
    required_encoders: tuple[str, ...] = ("libx264",),
    need_subtitles: bool = True,
    runner=None,
) -> SupplyResult:
    """按候选序解析满足硬字幕能力的 ffmpeg；无候选满足返回 missing 清单（不抛）。

    候选序=[数据根已下载位 ``data_root()/ffmpeg/bin/ffmpeg.exe``（优先——
    防 PATH 上无 libass 的上游版抢占，spike 事实）, ``asr_env.resolve_ffmpeg()``]。
    ``runner`` 参数仅供测试注入，签名同 _probe_capability。
    """
    candidates = [str(paths.data_root() / "ffmpeg" / "bin" / "ffmpeg.exe")]
    asr = asr_env.resolve_ffmpeg()
    if asr:
        candidates.append(asr)

    seen: set[str] = set()
    missing: list[str] = []
    for exe in candidates:
        if not exe or os.path.normcase(exe) in seen:
            continue
        seen.add(os.path.normcase(exe))
        if not os.path.isfile(exe):
            missing.append(f"候选不存在: {exe}")
            continue
        cap = _probe_capability_cached(exe, runner)
        lack: list[str] = []
        if not cap["version_ok"]:
            lack.append(f"ffmpeg 不可执行（-version 失败）: {exe}")
        for enc in required_encoders:
            if enc not in cap["encoders"]:
                lack.append(f"缺编码器 {enc}")
        if need_subtitles:
            if not cap["libass"]:
                lack.append("缺 libass（无法烧字幕）")
            if "subtitles" not in cap["filters"]:
                lack.append("缺 subtitles 滤镜")
        if not lack:
            return SupplyResult(exe, _resolve_ffprobe(exe), cap, [])
        missing.extend(lack)
    if not missing:
        missing = ["未找到 ffmpeg（数据根下载位与 PATH/env 候选均无）"]
    return SupplyResult("", _resolve_ffprobe(""), {}, missing)


# ---------------------------------------------------------------------------
# 媒体探测
# ---------------------------------------------------------------------------


def probe_media(ffprobe_path: str, media_path: str, runner=None) -> MediaInfo:
    """ffprobe JSON 探测：时长/宽高/码率/音轨；异常一律 FfprobeError。

    bit_rate 口径：format.bit_rate 缺失时回落视频流 bit_rate（仍缺则 0，
    调用方按码率参考表估算兜底）。``runner`` 注入同 _probe_capability。
    """
    if not ffprobe_path:
        raise FfprobeError("ffprobe 不可用")
    run = runner or _run_tool
    cmd = [ffprobe_path, "-v", "error", "-print_format", "json",
           "-show_format", "-show_streams", media_path]
    rc, out, err = run(cmd)
    if rc != 0:
        raise FfprobeError(f"ffprobe 探测失败(rc={rc}): {(err or '').strip()[:200]}")
    try:
        payload = json.loads(out)
    except ValueError as e:
        raise FfprobeError(f"ffprobe 输出非 JSON: {e}") from e
    fmt = payload.get("format") or {}
    streams = payload.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if video is None:
        raise FfprobeError("未找到视频流")
    try:
        duration = float(fmt.get("duration") or video.get("duration"))
    except (TypeError, ValueError) as e:
        raise FfprobeError("媒体时长缺失或不可解析") from e
    bit_rate = 0
    for src in (fmt.get("bit_rate"), video.get("bit_rate")):
        try:
            bit_rate = int(src)
            break
        except (TypeError, ValueError):
            continue
    return MediaInfo(
        duration_s=duration,
        width=int(video.get("width") or 0),
        height=int(video.get("height") or 0),
        bit_rate_bps=bit_rate,
        has_audio=audio is not None,
        audio_codec=str(audio.get("codec_name") or "") if audio else "",
    )


# ---------------------------------------------------------------------------
# 按需下载（BtbN 固定制品）
# ---------------------------------------------------------------------------


def _validate_url(url: str) -> str:
    """仅允许 https + 域名白名单（防重定向被引到内网/云元数据）。"""
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or not parts.hostname:
        raise SupplyDownloadError(f"仅允许 https 下载源: {url}")
    if parts.hostname.lower() not in _URL_HOST_ALLOW:
        raise SupplyDownloadError(f"下载源域名不在白名单: {parts.hostname}")
    return url


class _SupplyGuardedRedirectHandler(urllib.request.HTTPRedirectHandler):
    """逐跳校验的重定向处理器（dict_manager._DictGuardedRedirectHandler :416
    同构独立实现：错误类型必须为 SupplyDownloadError，白名单用本模块
    _URL_HOST_ALLOW）；非 https 或域名不在白名单即拒（先关 fp 防半开连接）。"""

    max_redirections = 5

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: N802
        try:
            _validate_url(str(newurl))
        except SupplyDownloadError:
            fp.close()
            raise
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _default_opener() -> urllib.request.OpenerDirector:
    return urllib.request.build_opener(_SupplyGuardedRedirectHandler)


def _remove_quiet(path: str) -> None:
    with contextlib.suppress(OSError):
        os.unlink(path)


def _fetch(
    url: str,
    dest: str,
    *,
    progress_cb=None,
    stop_event=None,
    opener_factory=None,
) -> int:
    """流式下载到 dest（1MB 分块；返回实收字节数）。

    - opener_factory 可注入（测试用 fake opener）；默认经
      _SupplyGuardedRedirectHandler 逐跳 https+白名单校验，沿用系统代理；
    - stop_event 每块检查（协作停止：清残件抛 SupplyStopped）；
    - Content-Length 存在且实收不符=完整性失败（清残件抛 SupplyDownloadError；
      spike 教训：上游曾出过截断坏件）。
    """
    factory = opener_factory or _default_opener
    req = urllib.request.Request(url, headers={"Accept-Encoding": "identity"})
    try:
        resp = factory().open(req, timeout=_TOOL_TIMEOUT_S)  # noqa: S310
    except SupplyError:
        raise
    except Exception as e:  # noqa: BLE001  网络层失败统一包装为供给错误
        raise SupplyDownloadError(f"下载失败: {e}") from e
    total_hdr = resp.headers.get("Content-Length") if resp.headers is not None else None
    # CL 缺席时不假定 pin 字节数（完整性交由 sha256 pin 兜底）；已知则强校验
    total = int(total_hdr) if total_hdr and str(total_hdr).isdigit() else None
    received = 0
    try:
        with open(dest, "wb") as f:
            while True:
                if stop_event is not None and stop_event.is_set():
                    raise SupplyStopped("下载已被用户停止")
                chunk = resp.read(_DOWNLOAD_CHUNK)
                if not chunk:
                    break
                f.write(chunk)
                received += len(chunk)
                if progress_cb is not None:
                    progress_cb(received, total)
    except SupplyStopped:
        _remove_quiet(dest)
        raise
    except OSError as e:
        _remove_quiet(dest)
        raise SupplyDownloadError(f"下载写盘失败: {e}") from e
    finally:
        with contextlib.suppress(Exception):
            resp.close()
    if total is not None and received != total:
        _remove_quiet(dest)
        raise SupplyDownloadError(
            f"下载不完整：预期 {total} 字节/实收 {received} 字节")
    return received


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(_DOWNLOAD_CHUNK), b""):
            h.update(block)
    return h.hexdigest()


def download_full_variant(
    dest_dir: str,
    progress_cb=None,
    stop_event=None,
    fetch=None,
) -> str:
    """下载 pinned BtbN full 变体并解压落位 ``dest_dir/ffmpeg/bin/``。

    返回 ffmpeg.exe 落位绝对路径。流程：磁盘预检（fail-closed，need=2×
    包体积）→ 分块下载（.downloading 暂存）→ sha256 比对 pin（TOFU，B3）
    → zipfile 试读（EOCD/条目校验——上游曾出过缺 EOCD 的截断坏件，spike
    执行记录 1）→ 按 basename 提取 ffmpeg.exe/ffprobe.exe（不限 zip 内顶层
    目录名）→ .part 落位后 os.replace → 清 zip。``fetch`` 参数仅供测试注入。
    """
    need = _PINNED_BYTES * 2  # zip + 解压产物并存的最坏情况
    try:
        free = shutil.disk_usage(dest_dir).free
    except OSError as e:
        raise SupplyDiskError(f"磁盘空间不可得（fail-closed）: {e}") from e
    if free < need:
        raise SupplyDiskError(
            f"磁盘可用空间不足：本次约需 {need // (1024 * 1024)}MB，"
            f"当前仅剩 {free // (1024 * 1024)}MB")

    os.makedirs(dest_dir, exist_ok=True)
    tmp = os.path.join(dest_dir, _ZIP_NAME)
    do_fetch = fetch or _fetch
    do_fetch(_PINNED_URL, tmp, progress_cb=progress_cb, stop_event=stop_event)

    try:
        sha = _sha256_file(tmp)
    except OSError as e:
        raise SupplyDownloadError(f"读取下载件失败: {e}") from e
    if sha != _PINNED_SHA256:
        _remove_quiet(tmp)
        raise SupplyChecksumError(
            f"sha256 与 pin 不符（TOFU）：期望 {_PINNED_SHA256}，实得 {sha}")

    # zipfile 试读：EOCD 缺失/条目 CRC 损坏一律视为坏件（换 tag 重试为标准动作）
    try:
        zf = zipfile.ZipFile(tmp)
        with zf:
            if zf.testzip() is not None:
                raise zipfile.BadZipFile("存在 CRC 校验失败的条目")
            targets: dict[str, str] = {}
            for name in zf.namelist():
                base = name.rsplit("/", 1)[-1]
                if base in ("ffmpeg.exe", "ffprobe.exe"):
                    targets[base] = name
            if "ffmpeg.exe" not in targets:
                raise zipfile.BadZipFile("zip 内未找到 ffmpeg.exe")
            out_bin = os.path.join(dest_dir, "ffmpeg", "bin")
            os.makedirs(out_bin, exist_ok=True)
            for base, member in targets.items():
                if stop_event is not None and stop_event.is_set():
                    raise SupplyStopped("下载已被用户停止")
                part = os.path.join(out_bin, base + ".part")
                with zf.open(member) as src, open(part, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                os.replace(part, os.path.join(out_bin, base))
    except SupplyStopped:
        _remove_quiet(tmp)
        raise
    except SupplyError:
        raise
    except Exception as e:  # noqa: BLE001  zip 结构错误统一包装
        _remove_quiet(tmp)
        raise SupplyDownloadError(f"zip 包损坏或解压落位失败: {e}") from e

    _remove_quiet(tmp)
    return os.path.join(dest_dir, "ffmpeg", "bin", "ffmpeg.exe")
