"""ffmpeg 供给层单测（2.8.0 批1 件2 测试，D2026-1007-03）。

零真实网络/零真二进制：能力探测经 ``runner`` 注入 fake、下载经 ``fetch``/
``opener_factory`` 注入 fake，磁盘经 monkeypatch。覆盖：URL 白名单+重定向
守卫、候选序与能力探测、(path, mtime) 缓存、probe_media 解析与错误、
download_full_variant 的 sha256 pin 失败/坏 zip（缺 EOCD 口径）/stop_event
清残件/磁盘预检 fail-closed/成功落位。
"""
import hashlib
import io
import json
import os
import sys
import threading
import time
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from subtransjav.refine import ffmpeg_supply as fs  # noqa: E402

PINNED_URL = ("https://github.com/BtbN/FFmpeg-Builds/releases/download/"
              "autobuild-2026-10-06-13-06/ffmpeg-N-127222-g151814650f-win64-gpl.zip")
PINNED_SHA256 = "8428c7e0d3c5faf21714a8fa7c9663b78a74fc1ee166777771daee03753f4929"
HOST_ALLOW = {"github.com", "release-assets.githubusercontent.com"}


# ---------------------------------------------------------------------------
# 固定值钉（防 pin 漂移）
# ---------------------------------------------------------------------------
def test_pinned_supply_constants():
    assert fs._PINNED_URL == PINNED_URL
    assert fs._PINNED_SHA256 == PINNED_SHA256
    assert fs._PINNED_BYTES == 200217553
    assert fs._URL_HOST_ALLOW == HOST_ALLOW


# ---------------------------------------------------------------------------
# _validate_url + 重定向守卫
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("url", [
    "http://github.com/a/b.zip",          # 非 https
    "https://evil.example/a.zip",         # 白名单外
    "ftp://github.com/a.zip",
    "https://objects.githubusercontent.com/x",  # 旧白名单域名（实测定集已修）
])
def test_validate_url_rejects(url):
    with pytest.raises(fs.SupplyDownloadError):
        fs._validate_url(url)


@pytest.mark.parametrize("url", [
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/x/y.zip",
    "https://release-assets.githubusercontent.com/github-production-release-asset/x",
])
def test_validate_url_accepts_allowlist(url):
    assert fs._validate_url(url) == url


def test_redirect_handler_guard_closes_fp():
    """重定向目标出白名单：关 fp 后抛 SupplyDownloadError（防半开连接泄漏）。"""
    closed = []

    class FakeFp:
        def close(self):
            closed.append(True)

    handler = fs._SupplyGuardedRedirectHandler()
    with pytest.raises(fs.SupplyDownloadError):
        handler.redirect_request(None, FakeFp(), 302, "", {}, "https://evil.example/x")
    assert closed


# ---------------------------------------------------------------------------
# 能力探测（fake runner）
# ---------------------------------------------------------------------------
_VERSION_FULL = ("ffmpeg version 7.1.1 Copyright\nbuilt with gcc\n"
                 "--enable-libass --enable-libfreetype --enable-libsvtav1")
_VERSION_NO_LIBASS = "ffmpeg version 7.1.1 Copyright\n--enable-libfreetype"
_ENCODERS_FULL = ("Encoders:\n V..... = Video\n V....D libx264  libx264 H.264\n"
                  " V....D libx265  libx265 HEVC\n V....D libsvtav1  SVT-AV1\n"
                  " A....D aac  AAC encoder")
_FILTERS_FULL = ("Filters:\n  ..C = transform\n  T.C subtitles  V->V  Render text\n"
                 "  T.C hqdn3d  V->V  denoiser\n  T.C deblock  V->V  deblocker\n"
                 "  T.C unsharp  V->V  sharpener")


def _full_runner(cmd):
    if "-version" in cmd:
        return 0, _VERSION_FULL, ""
    if "-encoders" in cmd:
        return 0, _ENCODERS_FULL, ""
    if "-filters" in cmd:
        return 0, _FILTERS_FULL, ""
    return 1, "", "boom"


def _no_libass_runner(cmd):
    if "-version" in cmd:
        return 0, _VERSION_NO_LIBASS, ""
    return _full_runner(cmd)


def test_probe_capability_parses():
    cap = fs._probe_capability("ffmpeg.exe", runner=_full_runner)
    assert cap["version_ok"] is True
    assert cap["libass"] is True
    assert {"libx264", "libx265", "libsvtav1", "aac"} <= cap["encoders"]
    assert {"subtitles", "hqdn3d", "deblock", "unsharp"} <= cap["filters"]


def test_capability_cache_by_path_mtime(tmp_path):
    """同 (path, mtime) 只探一次；二进制 mtime 变化后缓存失效重探。"""
    exe = tmp_path / "ffmpeg.exe"
    exe.write_text("x")
    fs._CAPABILITY_CACHE.clear()
    calls = []

    def counting(cmd):
        calls.append(cmd)
        return _full_runner(cmd)

    fs._probe_capability_cached(str(exe), counting)
    fs._probe_capability_cached(str(exe), counting)
    assert len([c for c in calls if "-version" in c]) == 1
    stamp = time.time() + 10
    os.utime(str(exe), (stamp, stamp))
    fs._probe_capability_cached(str(exe), counting)
    assert len([c for c in calls if "-version" in c]) == 2


# ---------------------------------------------------------------------------
# resolve_hardsub_ffmpeg：候选序与缺口清单
# ---------------------------------------------------------------------------
def _patch_candidates(monkeypatch, tmp_path, asr_path=""):
    monkeypatch.setattr(fs.paths, "data_root", lambda: tmp_path / "data")
    monkeypatch.setattr(fs.asr_env, "resolve_ffmpeg", lambda *a, **k: asr_path)
    fs._CAPABILITY_CACHE.clear()


def test_resolve_prefers_downloaded_candidate(monkeypatch, tmp_path):
    """下载位优先且满足时，PATH/env 候选不再探测（防无 libass 版抢占）。"""
    dl_bin = tmp_path / "data" / "ffmpeg" / "bin"
    dl_bin.mkdir(parents=True)
    (dl_bin / "ffmpeg.exe").write_text("x")
    (dl_bin / "ffprobe.exe").write_text("x")
    asr_dir = tmp_path / "asr"
    asr_dir.mkdir()
    (asr_dir / "ffmpeg.exe").write_text("y")
    _patch_candidates(monkeypatch, tmp_path, str(asr_dir / "ffmpeg.exe"))

    calls = []

    def counting(cmd):
        calls.append(cmd)
        return _full_runner(cmd)

    res = fs.resolve_hardsub_ffmpeg(runner=counting)
    assert res.ffmpeg_path == str(dl_bin / "ffmpeg.exe")
    assert res.ffprobe_path == str(dl_bin / "ffprobe.exe")  # 同目录配对优先
    assert res.missing == []
    assert res.capability["libass"] is True
    # 第二候选（asr 位）未被探测
    assert str(asr_dir / "ffmpeg.exe") not in {c[0] for c in calls}


def test_resolve_falls_back_to_asr_candidate(monkeypatch, tmp_path):
    asr_dir = tmp_path / "asr"
    asr_dir.mkdir()
    (asr_dir / "ffmpeg.exe").write_text("y")
    _patch_candidates(monkeypatch, tmp_path, str(asr_dir / "ffmpeg.exe"))
    res = fs.resolve_hardsub_ffmpeg(runner=_full_runner)
    assert res.ffmpeg_path == str(asr_dir / "ffmpeg.exe")
    assert res.missing == []


def test_resolve_reports_missing(monkeypatch, tmp_path):
    asr_dir = tmp_path / "asr"
    asr_dir.mkdir()
    (asr_dir / "ffmpeg.exe").write_text("y")
    _patch_candidates(monkeypatch, tmp_path, str(asr_dir / "ffmpeg.exe"))
    res = fs.resolve_hardsub_ffmpeg(runner=_no_libass_runner)
    assert res.ffmpeg_path == ""
    assert any("libass" in m for m in res.missing)


def test_resolve_requires_encoders(monkeypatch, tmp_path):
    """libass 齐但缺所需编码器：同样不点亮，missing 报具体编码器。"""
    asr_dir = tmp_path / "asr"
    asr_dir.mkdir()
    (asr_dir / "ffmpeg.exe").write_text("y")
    _patch_candidates(monkeypatch, tmp_path, str(asr_dir / "ffmpeg.exe"))

    def no_svt_runner(cmd):
        if "-encoders" in cmd:
            return 0, "Encoders:\n V....D libx264  libx264 H.264\n A....D aac  AAC", ""
        return _full_runner(cmd)

    res = fs.resolve_hardsub_ffmpeg(
        required_encoders=("libx264", "libsvtav1"), runner=no_svt_runner)
    assert res.ffmpeg_path == ""
    assert any("libsvtav1" in m for m in res.missing)


def test_resolve_ffprobe_falls_back_to_which(monkeypatch, tmp_path):
    asr_dir = tmp_path / "asr"
    asr_dir.mkdir()
    (asr_dir / "ffmpeg.exe").write_text("y")  # 同目录无 ffprobe.exe
    _patch_candidates(monkeypatch, tmp_path, str(asr_dir / "ffmpeg.exe"))
    monkeypatch.setattr(fs.shutil, "which", lambda name: "C:/PATH/ffprobe.exe")
    res = fs.resolve_hardsub_ffmpeg(runner=_full_runner)
    assert res.ffprobe_path == "C:/PATH/ffprobe.exe"


# ---------------------------------------------------------------------------
# probe_media（fake runner）
# ---------------------------------------------------------------------------
_FIXTURE = {
    "format": {"duration": "12.5", "bit_rate": "5000000"},
    "streams": [
        {"codec_type": "video", "codec_name": "h264", "width": 1920, "height": 1080,
         "bit_rate": "4500000"},
        {"codec_type": "audio", "codec_name": "aac", "bit_rate": "128000"},
    ],
}


def _json_runner(payload, rc=0, err=""):
    text = json.dumps(payload)

    def runner(cmd):
        return rc, text, err
    return runner


def test_probe_media_parses():
    info = fs.probe_media("ffprobe.exe", "m.mp4", runner=_json_runner(_FIXTURE))
    assert info.duration_s == 12.5
    assert (info.width, info.height) == (1920, 1080)
    assert info.bit_rate_bps == 5000000
    assert info.has_audio is True
    assert info.audio_codec == "aac"


def test_probe_media_bit_rate_falls_back_to_stream():
    payload = json.loads(json.dumps(_FIXTURE))
    del payload["format"]["bit_rate"]
    info = fs.probe_media("ffprobe.exe", "m.mp4", runner=_json_runner(payload))
    assert info.bit_rate_bps == 4500000


@pytest.mark.parametrize("payload,rc", [
    (_FIXTURE, 1),                                     # ffprobe 非零退出
    ({"format": {"duration": "N/A"}, "streams": []}, 0),   # 无视频流
    ({"format": {"duration": "N/A"},
      "streams": [{"codec_type": "video"}]}, 0),        # 时长不可解析
])
def test_probe_media_errors(payload, rc):
    with pytest.raises(fs.FfprobeError):
        fs.probe_media("ffprobe.exe", "m.mp4", runner=_json_runner(payload, rc=rc))


def test_probe_media_non_json_output():
    def runner(cmd):
        return 0, "<html>not json</html>", ""
    with pytest.raises(fs.FfprobeError):
        fs.probe_media("ffprobe.exe", "m.mp4", runner=runner)


def test_probe_media_requires_ffprobe():
    with pytest.raises(fs.FfprobeError):
        fs.probe_media("", "m.mp4")


# ---------------------------------------------------------------------------
# download_full_variant（fake fetch / fake opener）
# ---------------------------------------------------------------------------
def _make_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED) as zf:
        zf.writestr("ffmpeg-N-127222/bin/ffmpeg.exe", b"FFMPEG-BIN")
        zf.writestr("ffmpeg-N-127222/bin/ffprobe.exe", b"FFPROBE-BIN")
        zf.writestr("ffmpeg-N-127222/README.txt", b"readme")
    return buf.getvalue()


def _fake_fetch(payload: bytes):
    def fetch(url, dest, *, progress_cb=None, stop_event=None):
        with open(dest, "wb") as f:
            f.write(payload)
        if progress_cb is not None:
            progress_cb(len(payload), len(payload))
        return len(payload)
    return fetch


def test_download_success_lands_bin(tmp_path, monkeypatch):
    payload = _make_zip()
    monkeypatch.setattr(fs, "_PINNED_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(fs, "_PINNED_BYTES", len(payload))
    out = fs.download_full_variant(str(tmp_path), fetch=_fake_fetch(payload))
    assert out == str(tmp_path / "ffmpeg" / "bin" / "ffmpeg.exe")
    assert (tmp_path / "ffmpeg" / "bin" / "ffmpeg.exe").read_bytes() == b"FFMPEG-BIN"
    assert (tmp_path / "ffmpeg" / "bin" / "ffprobe.exe").read_bytes() == b"FFPROBE-BIN"
    assert not (tmp_path / "ffmpeg-full.zip.downloading").exists()  # zip 清理


def test_download_checksum_mismatch(tmp_path):
    """sha256 与 pin 不符：删件并抛 SupplyChecksumError（TOFU，B3）。"""
    with pytest.raises(fs.SupplyChecksumError) as ei:
        fs.download_full_variant(str(tmp_path), fetch=_fake_fetch(_make_zip()))
    assert "sha256" in str(ei.value)
    assert not (tmp_path / "ffmpeg-full.zip.downloading").exists()
    assert not (tmp_path / "ffmpeg" / "bin" / "ffmpeg.exe").exists()


def test_download_bad_zip_no_eocd(tmp_path, monkeypatch):
    """spike 教训：上游出过整包缺 EOCD 的截断坏件——zipfile 试读必须拦。"""
    payload = b"truncated zip without EOCD" * 100
    monkeypatch.setattr(fs, "_PINNED_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(fs, "_PINNED_BYTES", len(payload))
    with pytest.raises(fs.SupplyDownloadError):
        fs.download_full_variant(str(tmp_path), fetch=_fake_fetch(payload))
    assert not (tmp_path / "ffmpeg-full.zip.downloading").exists()


def test_download_zip_without_ffmpeg_exe(tmp_path, monkeypatch):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("x/README.txt", b"no exe here")
    payload = buf.getvalue()
    monkeypatch.setattr(fs, "_PINNED_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(fs, "_PINNED_BYTES", len(payload))
    with pytest.raises(fs.SupplyDownloadError):
        fs.download_full_variant(str(tmp_path), fetch=_fake_fetch(payload))


def test_download_disk_preflight_fail_closed(tmp_path, monkeypatch):
    monkeypatch.setattr(fs.shutil, "disk_usage",
                        lambda p: SimpleNamespace(free=1024))
    with pytest.raises(fs.SupplyDiskError):
        fs.download_full_variant(str(tmp_path), fetch=_fake_fetch(b"x"))


def test_download_disk_preflight_oserror_rejects(tmp_path, monkeypatch):
    def boom(p):
        raise OSError("no such volume")
    monkeypatch.setattr(fs.shutil, "disk_usage", boom)
    with pytest.raises(fs.SupplyDiskError):
        fs.download_full_variant(str(tmp_path), fetch=_fake_fetch(b"x"))


def test_download_stop_event_cleans(tmp_path, monkeypatch):
    payload = _make_zip()
    monkeypatch.setattr(fs, "_PINNED_SHA256", hashlib.sha256(payload).hexdigest())
    monkeypatch.setattr(fs, "_PINNED_BYTES", len(payload))
    ev = threading.Event()
    ev.set()

    def fetch(url, dest, *, progress_cb=None, stop_event=None):
        raise fs.SupplyStopped("stopped")
    with pytest.raises(fs.SupplyStopped):
        fs.download_full_variant(str(tmp_path), stop_event=ev, fetch=fetch)
    assert not (tmp_path / "ffmpeg-full.zip.downloading").exists()


# ---------------------------------------------------------------------------
# _fetch 分块语义（fake opener）
# ---------------------------------------------------------------------------
class FakeResp:
    def __init__(self, chunks, headers=None):
        self._chunks = list(chunks)
        self.headers = headers if headers is not None else {}

    def read(self, n=-1):
        return self._chunks.pop(0) if self._chunks else b""

    def close(self):
        pass


class FakeOpener:
    def __init__(self, resp):
        self._resp = resp

    def open(self, req, timeout=None):
        return self._resp


def test_fetch_content_length_mismatch_cleans(tmp_path):
    dest = tmp_path / "x.downloading"
    resp = FakeResp([b"a" * 10], {"Content-Length": "100"})
    with pytest.raises(fs.SupplyDownloadError) as ei:
        fs._fetch("https://github.com/x.zip", str(dest),
                  opener_factory=lambda: FakeOpener(resp))
    assert "预期 100 字节/实收 10 字节" in str(ei.value)
    assert not dest.exists()


def test_fetch_stop_event_mid_stream(tmp_path):
    dest = tmp_path / "x.downloading"
    ev = threading.Event()
    resp = FakeResp([b"a" * 10, b"b" * 10], {})
    progressed = []

    def cb(received, total):
        progressed.append(received)
        ev.set()  # 收到第一块后停止

    with pytest.raises(fs.SupplyStopped):
        fs._fetch("https://github.com/x.zip", str(dest), progress_cb=cb,
                  stop_event=ev, opener_factory=lambda: FakeOpener(resp))
    assert progressed == [10]
    assert not dest.exists()  # 协作停止清残件


def test_fetch_completes_without_content_length(tmp_path):
    dest = tmp_path / "x.downloading"
    resp = FakeResp([b"a" * 10, b"b" * 5], {})
    received = fs._fetch("https://github.com/x.zip", str(dest),
                         opener_factory=lambda: FakeOpener(resp))
    assert received == 15
    assert dest.read_bytes() == b"a" * 10 + b"b" * 5


# ---------------------------------------------------------------------------
# GPU 后端解析（批2：nvenc→qsv→amf 双检链）
# ---------------------------------------------------------------------------
def _fake_tool_runner(encoders_text, fail_encoders=()):
    def runner(cmd):
        if cmd[-1] == "-encoders":
            return 0, encoders_text, ""
        for enc in fail_encoders:
            if enc in cmd:
                return 1, "", f"Cannot load {enc}"
        return 0, "", ""
    return runner


def test_resolve_gpu_encoder_picks_first_working(tmp_path):
    exe = tmp_path / "f1.exe"
    exe.write_bytes(b"x")
    runner = _fake_tool_runner(" V....D h264_nvenc Encoding\n V....D h264_qsv Encoding\n")
    picked, reasons = fs.resolve_gpu_encoder(str(exe), "h264", runner=runner)
    assert picked == "h264_nvenc" and reasons == []


def test_resolve_gpu_encoder_falls_to_next_on_run_fail(tmp_path):
    exe = tmp_path / "f2.exe"
    exe.write_bytes(b"x")
    runner = _fake_tool_runner(" V....D h264_nvenc \n V....D h264_qsv \n",
                               fail_encoders=("h264_nvenc",))
    picked, reasons = fs.resolve_gpu_encoder(str(exe), "h264", runner=runner)
    assert picked == "h264_qsv"
    assert any("nvenc" in r and "试编码失败" in r for r in reasons)


def test_resolve_gpu_encoder_all_fail_reasons(tmp_path):
    exe = tmp_path / "f3.exe"
    exe.write_bytes(b"x")
    runner = _fake_tool_runner("")
    picked, reasons = fs.resolve_gpu_encoder(str(exe), "h264", runner=runner)
    assert picked == "" and len(reasons) == 3   # 三候选全显因
    assert all("未编译" in r for r in reasons)


def test_resolve_gpu_encoder_av1_chain_no_amf(tmp_path):
    exe = tmp_path / "f4.exe"
    exe.write_bytes(b"x")
    runner = _fake_tool_runner(" V....D av1_nvenc \n")
    picked, _ = fs.resolve_gpu_encoder(str(exe), "av1", runner=runner)
    assert picked == "av1_nvenc"
    # amf 不在 av1 链：全败显因只有 2 条
    runner2 = _fake_tool_runner("")
    exe2 = tmp_path / "f5.exe"
    exe2.write_bytes(b"x")
    _picked2, reasons2 = fs.resolve_gpu_encoder(str(exe2), "av1", runner=runner2)
    assert len(reasons2) == 2


def test_resolve_gpu_encoder_cached(tmp_path):
    exe = tmp_path / "f6.exe"
    exe.write_bytes(b"x")
    calls = []

    def runner(cmd):
        calls.append(1)
        return 0, " V....D h264_nvenc \n", ""

    fs.resolve_gpu_encoder(str(exe), "h264", runner=runner)
    n = len(calls)
    fs.resolve_gpu_encoder(str(exe), "h264", runner=runner)
    assert len(calls) == n   # 缓存命中不再探测
