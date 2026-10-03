"""asr_downloader 单元测试（2.6.3 批B，D2026-1003-01 ② + D2026-1003-05 五条件）。

零真实网络：``_http_get_asr`` / ``socket.getaddrinfo`` / ``shutil.disk_usage``
一律 monkeypatch。URL 信任三层+两硬化、候选源集、单实例锁、磁盘预检
fail-closed、符号链接守卫、回退可见提示（note）全覆盖。
"""
import hashlib
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

from subtransjav import paths
from subtransjav.refine import asr_downloader as ad
from subtransjav.refine import asr_env

SHA_OK = hashlib.sha256(b"MODELPT").hexdigest()
PAYLOAD = b"MODELPT"
OFFICIAL_URL = ("https://openaipublic.azureedge.net/main/whisper/models/"
                "81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56effd0b6a"
                "73e524/large-v2.pt")
MIRROR_URL = "https://hf-mirror.com/mirror/large-v2.pt"


def _entry(sha: str = SHA_OK, mirror_verified: bool = False) -> dict:
    """受控清单条目（bytes=7 小文件，官方在前；mirror 默认 PENDING）。"""
    return {
        "name": "whisper-large-v2", "model": "large-v2",
        "title": "t", "bytes": len(PAYLOAD), "sha256": sha,
        "url": OFFICIAL_URL, "support": "available",
        "license": "MIT（openai/whisper 上游模型卡口径）",
        "sources": [
            {"source": "official", "label": "官方源", "url": OFFICIAL_URL,
             "sha256": sha, "verified": True},
            {"source": "mirror", "label": "国内加速源", "url": MIRROR_URL,
             "sha256": sha, "verified": mirror_verified,
             "note": "需实测下载比对验证后才能启用，当前版本不可用"},
        ],
    }


def _addrinfos(ip: str):
    return [(2, 1, 6, "", (ip, 443))]


@pytest.fixture(autouse=True)
def _clean_state():
    ad._ASR_DOWNLOAD_PROGRESS.clear()
    ad._ACTIVE_DOWNLOADS.clear()
    yield
    ad._ASR_DOWNLOAD_PROGRESS.clear()
    ad._ACTIVE_DOWNLOADS.clear()


# ---------------------------------------------------------------------------
# URL 信任三层：层1+2（_validate_url）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("url", [
    "", "   ",                                        # 空 URL（镜像 PENDING 必硬拒）
    "http://openaipublic.azureedge.net/x.pt",         # 非 https
    "ftp://openaipublic.azureedge.net/x.pt",          # 非 https 协议
    "https://evil.example.com/large-v2.pt",           # 非清单 host
    "https://openaipublic.azureedge.net/other.pt",    # 同 host 不同 path（精确匹配拒）
    "https://127.0.0.1/large-v2.pt",                  # 环回（非清单 URL 先拒）
    "https://openaipublic.azureedge.net/x.pt?fake=1", # query 变体（精确匹配拒）
])
def test_validate_url_rejects(url):
    with pytest.raises(ad.AsrDownloadError):
        ad._validate_url(url)


@pytest.mark.parametrize("variant", [
    OFFICIAL_URL,
    OFFICIAL_URL.replace("openaipublic.azureedge.net",
                         "OpenAipublic.AzureEdge.Net"),       # 大小写 host
    OFFICIAL_URL.replace("azureedge.net/", "azureedge.net:443/", 1),   # 默认端口
    OFFICIAL_URL.replace("azureedge.net/", "azureedge.net./", 1),      # 尾点 FQDN
    OFFICIAL_URL + "#frag",                                            # fragment
])
def test_validate_url_normalization_equivalence(variant):
    """归一化匹配仅用于「清单 URL 等值」判定：大小写 host/默认端口/尾点/
    fragment 变体归一化后与清单 URL 全等 → 放行（防御校验用原始值）。"""
    ad._validate_url(variant)


# ---------------------------------------------------------------------------
# 层3：host 小名单 + 解析 IP 全量判定（护栏⑥）
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("ip", [
    "127.0.0.1",      # 环回
    "10.1.2.3",       # 私网
    "192.168.1.5",    # 私网
    "169.254.3.4",    # link-local
    "240.1.2.3",      # 保留
    "224.0.0.5",      # 多播
])
def test_host_ip_guard_rejects_restricted_ips(monkeypatch, ip):
    monkeypatch.setattr(ad.socket, "getaddrinfo",
                        lambda h, p, proto=0: _addrinfos(ip))
    with pytest.raises(ad.AsrDownloadError):
        ad._validate_host_ips("openaipublic.azureedge.net")


def test_host_ip_guard_public_ip_ok(monkeypatch):
    monkeypatch.setattr(ad.socket, "getaddrinfo",
                        lambda h, p, proto=0: _addrinfos("93.184.216.34"))
    ad._validate_host_ips("openaipublic.azureedge.net")


def test_host_ip_guard_dns_failure_fail_closed(monkeypatch):
    def _boom(*a, **k):
        raise OSError("dns down")
    monkeypatch.setattr(ad.socket, "getaddrinfo", _boom)
    with pytest.raises(ad.AsrDownloadError, match="解析失败"):
        ad._validate_host_ips("openaipublic.azureedge.net")


def test_host_ip_guard_allowlist_rejects(monkeypatch):
    monkeypatch.setattr(ad.socket, "getaddrinfo",
                        lambda *a, **k: _addrinfos("93.184.216.34"))
    with pytest.raises(ad.AsrDownloadError, match="白名单"):
        ad._validate_host_ips("evil.example.com")


# ---------------------------------------------------------------------------
# 两硬化：重定向逐跳校验
# ---------------------------------------------------------------------------
class _FakeFP:
    def __init__(self):
        self.closed = False

    def close(self):
        self.closed = True


def test_redirect_max_hops_pinned():
    assert ad._GuardedRedirectHandler.max_redirections == 5


def test_redirect_allows_https_allowlisted_target(monkeypatch):
    """合格跟随：https + host 在小名单 + 公网 IP。"""
    monkeypatch.setattr(ad.socket, "getaddrinfo",
                        lambda *a, **k: _addrinfos("93.184.216.34"))
    h = ad._GuardedRedirectHandler()
    fp = _FakeFP()
    new = h.redirect_request(
        urllib.request.Request(OFFICIAL_URL), fp, 302, "Found", {},
        "https://openaipublic.azureedge.net/cdn/large-v2.pt")
    assert new is not None
    assert new.full_url == "https://openaipublic.azureedge.net/cdn/large-v2.pt"


def test_redirect_rejects_non_allowlisted_host(monkeypatch):
    monkeypatch.setattr(ad.socket, "getaddrinfo",
                        lambda *a, **k: _addrinfos("93.184.216.34"))
    h = ad._GuardedRedirectHandler()
    fp = _FakeFP()
    with pytest.raises(ad.AsrDownloadError):
        h.redirect_request(urllib.request.Request(OFFICIAL_URL), fp, 302,
                           "Found", {}, "https://evil.example.com/x.pt")
    assert fp.closed, "拒绝时必须关闭上游响应句柄"


def test_redirect_rejects_http_target(monkeypatch):
    monkeypatch.setattr(ad.socket, "getaddrinfo",
                        lambda *a, **k: _addrinfos("93.184.216.34"))
    with pytest.raises(ad.AsrDownloadError):
        ad._validate_redirect_target("http://openaipublic.azureedge.net/x.pt")


# ---------------------------------------------------------------------------
# download_asr_model 主流程
# ---------------------------------------------------------------------------
def test_download_official_success(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS", [_entry()])
    calls = []
    monkeypatch.setattr(ad, "_http_get_asr",
                        lambda url, dest, progress=None:
                        (calls.append(url), Path(dest).write_bytes(PAYLOAD),
                         progress(len(PAYLOAD), len(PAYLOAD))))
    target = ad.download_asr_model("whisper-large-v2", "auto")
    assert Path(target) == Path(paths.data_subdir("models", "asr")) / "large-v2.pt"
    assert Path(target).read_bytes() == PAYLOAD
    assert calls == [OFFICIAL_URL]      # 镜像 PENDING 未上候选
    snap = ad.asr_download_progress("whisper-large-v2")
    assert snap["phase"] == "done"
    assert snap["downloaded"] == snap["total"] == len(PAYLOAD)


def test_progress_phase_chain(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS", [_entry()])
    phases = []
    real_set = ad._set_progress

    def _spy(model, phase, downloaded=0, total=None, error=None, note=None):
        phases.append(phase)
        real_set(model, phase, downloaded, total, error, note)

    monkeypatch.setattr(ad, "_set_progress", _spy)
    monkeypatch.setattr(ad, "_http_get_asr",
                        lambda url, dest, progress=None:
                        Path(dest).write_bytes(PAYLOAD))
    assert Path(ad.download_asr_model("whisper-large-v2")).is_file()
    assert phases[0] == "download"
    assert phases.index("verify") > phases.index("download")
    assert phases[-1] == "done"


def test_official_failure_falls_back_with_visible_note(monkeypatch, tmp_path):
    """评议员条件①：官方网络失败 → note="官方源不可达，已回退国内镜像"，
    已 verified 的镜像接续成功。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS",
                        [_entry(mirror_verified=True)])
    calls = []
    notes = []
    real_set = ad._set_progress

    def _spy(model, phase, downloaded=0, total=None, error=None, note=None):
        if note:
            notes.append((phase, note))
        real_set(model, phase, downloaded, total, error, note)

    monkeypatch.setattr(ad, "_set_progress", _spy)

    def _fake_get(url, dest, progress=None):
        calls.append(url)
        if url == OFFICIAL_URL:
            raise ad.AsrDownloadError("连接超时")
        Path(dest).write_bytes(PAYLOAD)
        progress(len(PAYLOAD), len(PAYLOAD))

    monkeypatch.setattr(ad, "_http_get_asr", _fake_get)
    assert Path(ad.download_asr_model("whisper-large-v2", "auto")).is_file()
    assert calls == [OFFICIAL_URL, MIRROR_URL]
    assert any(n == "官方源不可达，已回退国内镜像" for _p, n in notes)


def test_pending_mirror_never_candidate(monkeypatch, tmp_path):
    """评议员条件③/⑤：mirror 未 verified → 永不上候选（官方挂了也不试）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS",
                        [_entry(mirror_verified=False)])
    calls = []

    def _down(url, dest, progress=None):
        calls.append(url)
        raise ad.AsrDownloadError("连接超时")

    monkeypatch.setattr(ad, "_http_get_asr", _down)
    with pytest.raises(ad.AsrDownloadError, match="连接超时"):
        ad.download_asr_model("whisper-large-v2", "auto")
    assert calls == [OFFICIAL_URL]


def test_mirror_source_without_verified_mirror_explicit_error(monkeypatch,
                                                              tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS",
                        [_entry(mirror_verified=False)])
    calls = []
    monkeypatch.setattr(ad, "_http_get_asr",
                        lambda url, dest, progress=None:
                        calls.append(url))
    with pytest.raises(ad.AsrDownloadError, match="暂无可用镜像源"):
        ad.download_asr_model("whisper-large-v2", "mirror")
    assert calls == []


def test_checksum_mismatch_deletes_part_no_rotation(monkeypatch, tmp_path):
    """校验失败：删 .part + 抛不轮换（对齐 dict 语义，防换源洗白）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS",
                        [_entry(sha="9" * 64, mirror_verified=True)])
    calls = []

    def _fake_get(url, dest, progress=None):
        calls.append(url)
        Path(dest).write_bytes(PAYLOAD)

    monkeypatch.setattr(ad, "_http_get_asr", _fake_get)
    with pytest.raises(ad.AsrChecksumError):
        ad.download_asr_model("whisper-large-v2", "auto")
    assert calls == [OFFICIAL_URL]
    part = Path(paths.data_subdir("models", "asr")) / "large-v2.pt.part"
    assert not part.exists()


def test_single_instance_lock_busy_and_release(monkeypatch, tmp_path):
    """单实例锁：已在下 → 报繁忙；成功后 finally 释放（可再下）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS", [_entry()])
    monkeypatch.setattr(ad, "_http_get_asr",
                        lambda url, dest, progress=None:
                        Path(dest).write_bytes(PAYLOAD))
    ad._ACTIVE_DOWNLOADS.add("whisper-large-v2")
    with pytest.raises(ad.AsrDownloadError, match="已有下载进行中"):
        ad.download_asr_model("whisper-large-v2")
    ad._ACTIVE_DOWNLOADS.discard("whisper-large-v2")
    # 锁释放后可正常下载，且下载完成后锁归零
    assert Path(ad.download_asr_model("whisper-large-v2")).is_file()
    assert "whisper-large-v2" not in ad._ACTIVE_DOWNLOADS


def test_disk_preflight_fail_closed_on_oserror(monkeypatch, tmp_path):
    """评议员条件⑥：disk_usage 不可得 → 拒绝下载（fail-closed，与 dict
    的 fail-open 有意不同）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS", [_entry()])

    def _boom(p):
        raise OSError("volume info unavailable")

    monkeypatch.setattr(ad.shutil, "disk_usage", _boom)
    calls = []
    monkeypatch.setattr(ad, "_http_get_asr",
                        lambda url, dest, progress=None: calls.append(url))
    with pytest.raises(ad.AsrDownloadError, match="磁盘空间预检不可得"):
        ad.download_asr_model("whisper-large-v2")
    assert calls == []


def test_disk_preflight_insufficient_space(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS", [_entry()])
    monkeypatch.setattr(ad.shutil, "disk_usage",
                        lambda p: SimpleNamespace(free=1))
    with pytest.raises(ad.AsrDownloadError, match="磁盘可用空间不足"):
        ad.download_asr_model("whisper-large-v2")


def test_disk_write_error_failed_phase_no_rotation(monkeypatch, tmp_path):
    """评议员条件⑥：中途 OSError/ENOSPC → 删 .part + failed 相位 + note，
    不伪装成网络失败轮换。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS",
                        [_entry(mirror_verified=True)])
    calls = []

    def _enospc(url, dest, progress=None):
        calls.append(url)
        raise ad.AsrDiskWriteError("磁盘空间不足或写入失败: ENOSPC")

    monkeypatch.setattr(ad, "_http_get_asr", _enospc)
    with pytest.raises(ad.AsrDownloadError, match="磁盘空间不足或写入失败"):
        ad.download_asr_model("whisper-large-v2", "auto")
    assert calls == [OFFICIAL_URL]      # 不轮换
    snap = ad.asr_download_progress("whisper-large-v2")
    assert snap["phase"] == "failed"
    assert snap["note"] == "磁盘空间不足或写入失败"


def test_symlink_guard_rejects_write(monkeypatch, tmp_path):
    """评议员条件⑥：目标/临时件是符号链接 → 拒写。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS", [_entry()])
    monkeypatch.setattr(ad.os.path, "islink",
                        lambda p: str(p).endswith((".pt", ".part")))
    calls = []
    monkeypatch.setattr(ad, "_http_get_asr",
                        lambda url, dest, progress=None: calls.append(url))
    with pytest.raises(ad.AsrDownloadError, match="符号链接"):
        ad.download_asr_model("whisper-large-v2")
    assert calls == []
    assert not (Path(paths.data_subdir("models", "asr"))
                / "large-v2.pt.part").exists()


def test_model_whitelist_rejects_unknown_and_injection(monkeypatch):
    """model 白名单=support=="available" 的 name（路径注入面封死）。"""
    monkeypatch.setattr(asr_env, "ASR_RECOMMENDED_MODELS",
                        [_entry(), {"name": "qwen3-asr-1.7b",
                                    "model": "qwen3-asr-1.7b",
                                    "support": "planned"}])
    for bad in ("nope", "qwen3-asr-1.7b", "../../evil", ""):
        with pytest.raises(ad.AsrDownloadError, match="未知或不可下载"):
            ad.download_asr_model(bad)
    with pytest.raises(ad.AsrDownloadError, match="非法下载源"):
        ad.download_asr_model("whisper-large-v2", "bogus")
