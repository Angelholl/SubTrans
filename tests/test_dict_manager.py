"""dict_manager 词典管理单元测试（2.1 基建，D2026-0930-03 ②④）。

零真实网络：D2026-1004-01 候选B 后下载链走显式 build_opener（不再用裸
urlopen），网络桩统一 monkeypatch ``urllib.request.build_opener``；
模块级 ``_REAL_BUILD_OPENER`` 兜底 identity 断言防补丁泄漏走真实网络
（单次时序 flake 头号嫌疑）。哈希用当次构造内容现算。
"""
import hashlib
import io
import sys
import threading
import types
import urllib.error
import urllib.request
import zipfile
from pathlib import Path

import pytest

from subtransjav.refine import dict_manager as dm

# 打补丁前的真身（模块导入期捕获；测试内断言 build_opener 已被替换）
_REAL_BUILD_OPENER = urllib.request.build_opener


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------
def _fake_wheel(member: str = "sudachidict_core/resources/system.dic",
                payload: bytes = b"DICDATA") -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr(member, payload)
    return buf.getvalue()


def _manifest_with_downloads(monkeypatch, downloads, target="system_core.dic",
                             member="sudachidict_core/resources/system.dic"):
    """把源清单 sudachi downloads 替换为测试用条目。"""
    base = dm.load_source_manifest()
    sudachi = {**base["dicts"]["sudachi"], "downloads": downloads,
               "target_name": target, "archive_member": member}
    monkeypatch.setattr(dm, "load_source_manifest", lambda: {
        **base, "dicts": {**base["dicts"], "sudachi": sudachi}})


class _FakeResponse:
    def __init__(self, payload: bytes):
        self._p = payload

    def read(self, *a):
        return self._p

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# ---------------------------------------------------------------------------
# 布局与清单
# ---------------------------------------------------------------------------
def test_dict_dir_under_data_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    assert Path(dm.dict_dir()) == tmp_path / "dict"


def test_source_manifest_parses_three_kinds():
    m = dm.load_source_manifest()
    assert set(m["dicts"]) >= {"sudachi", "jieba", "english_rules"}
    dls = m["dicts"]["sudachi"]["downloads"]
    assert dls, "sudachi 必须有下载源"
    assert all(d["sha256"] and d["url"] for d in dls)
    assert any(d["source"] == "pypi" for d in dls), "主源必须是 PyPI 官方"
    assert m["dicts"]["jieba"]["downloads"] == []
    assert m["dicts"]["english_rules"]["downloads"] == []


def test_kind_dir_under_dict_root(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    assert Path(dm.kind_dir("sudachi")) == tmp_path / "dict" / "sudachi"


def test_unknown_kind_rejected():
    import pytest
    with pytest.raises(ValueError):
        dm.kind_dir("nope")
    with pytest.raises(ValueError):
        dm.download_dict("nope")


# ---------------------------------------------------------------------------
# 下载链路（monkeypatch 网络）
# ---------------------------------------------------------------------------
def test_download_dict_success(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/x.whl",
         "sha256": sha, "sha256_verified": True}])
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None, stop_event=None:
                        Path(dest).write_bytes(wheel))
    target = dm.download_dict("sudachi")
    assert Path(target) == tmp_path / "dict" / "sudachi" / "system_core.dic"
    assert Path(target).read_bytes() == b"DICDATA"


def test_download_dict_checksum_error_no_fallback(monkeypatch, tmp_path):
    """SHA256 不符：拒绝落位且不轮换下一源（防串改文件换源洗白）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    calls = []

    def _fake_get(url, dest, progress=None, stop_event=None):
        calls.append(url)
        Path(dest).write_bytes(wheel)

    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": "0" * 64, "sha256_verified": True},
        {"source": "tuna", "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": "0" * 64, "sha256_verified": True}])
    monkeypatch.setattr(dm, "_http_get", _fake_get)
    import pytest
    with pytest.raises(dm.DictChecksumError):
        dm.download_dict("sudachi")
    assert len(calls) == 1, "校验失败不得轮换下一源"
    assert not any((tmp_path / "dict" / "sudachi").glob("system_core.dic*"))


def test_download_dict_network_fallback(monkeypatch, tmp_path):
    """主源网络失败 → 镜像 fallback 成功。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": sha, "sha256_verified": True},
        {"source": "tuna", "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": sha, "sha256_verified": True}])

    def _fake_get(url, dest, progress=None, stop_event=None):
        if "tuna" not in url:
            raise dm.DictDownloadError("连接超时")
        Path(dest).write_bytes(wheel)

    monkeypatch.setattr(dm, "_http_get", _fake_get)
    target = dm.download_dict("sudachi")
    assert Path(target).read_bytes() == b"DICDATA"


def test_download_dict_all_sources_down(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": "1" * 64, "sha256_verified": True}])

    def _always_down(url, dest, progress=None, stop_event=None):
        raise dm.DictDownloadError("网络不可达")

    monkeypatch.setattr(dm, "_http_get", _always_down)
    import pytest
    with pytest.raises(dm.DictDownloadError):
        dm.download_dict("sudachi")


# ---------------------------------------------------------------------------
# 下载进度（第四批 owner 验收反馈：分块回调 + 阶段状态）
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_download_progress(monkeypatch):
    """每例隔离模块级进度表（换引用，测试后自动还原）。"""
    monkeypatch.setattr(dm, "_DOWNLOAD_PROGRESS", {})
    yield


class _StreamResponse:
    """流式假响应：read(n) 分块返回；headers.get 模拟 Content-Length。"""

    def __init__(self, payload: bytes, chunk: int = 4, total=None):
        self._payload = payload
        self._chunk = chunk
        self._off = 0
        self.headers = types.SimpleNamespace(
            get=lambda k: "" if total is None else str(total))

    def read(self, n=-1):
        if self._off >= len(self._payload):
            return b""
        # 模拟慢速流：单次至多交付 chunk 字节（请求量再大也分批到货）
        step = len(self._payload) if n is None or n < 0 \
            else min(n, self._chunk)
        end = min(self._off + step, len(self._payload))
        out = self._payload[self._off:end]
        self._off = end
        return out

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _patch_build_opener(monkeypatch, responder, poison_proxies=False):
    """统一新 seam（D2026-1004-01 候选B C8）：下载链已弃裸 urlopen 改显式
    build_opener，流式测试统一打桩 build_opener。

    返回 ``(handlers_seen, open_calls)``：前者按序记录每次 build_opener
    收到的 handlers（供两跳状态机断言），后者记录真正发起的 open 请求
    （供"恰 N 次 fetch"断言）。

    桩工厂模拟真实 build_opener 的代理语义：未显式传 ProxyHandler 的
    attempt 视为系统代理跳（poison_proxies=True 时经 getproxies() 取毒
    代理——测试需另行 monkeypatch getproxies）；显式 ProxyHandler 则取
    其 proxies。代理非空的 attempt open 即抛 URLError（模拟代理坏损）。
    """
    handlers_seen = []
    open_calls = []

    def _factory(*handlers):
        handlers_seen.append(handlers)
        explicit = next((h for h in handlers
                         if isinstance(h, urllib.request.ProxyHandler)),
                        None)
        if explicit is not None:
            proxies = explicit.proxies
        elif poison_proxies:
            proxies = urllib.request.getproxies()
        else:
            proxies = {}

        def _open(req, timeout=10):
            open_calls.append(req)
            if proxies:
                raise urllib.error.URLError(f"代理不可达: {proxies}")
            return responder(req)

        return types.SimpleNamespace(open=_open)

    monkeypatch.setattr(urllib.request, "build_opener", _factory)
    return handlers_seen, open_calls


def test_http_get_progress_callback_chunks(monkeypatch, tmp_path):
    """分块 read + Content-Length → progress 回调精确序列 (n, total)。

    D2026-1004-01 候选B：seam 由 urlopen 迁移至显式 build_opener；开头
    identity 断言确认补丁生效（防补丁泄漏走真实网络）。"""
    payload = b"abcdefgh" * 2                       # 16 字节，chunk 4 → 4 块
    seen = []
    _patch_build_opener(
        monkeypatch,
        lambda req: _StreamResponse(payload, chunk=4, total=len(payload)))
    assert urllib.request.build_opener is not _REAL_BUILD_OPENER, \
        "build_opener 补丁未生效（会走真实网络）"
    dest = str(tmp_path / "x.whl")
    dm._http_get("https://files.pythonhosted.org/x.whl", dest,
                 progress=lambda n, t: seen.append((n, t)))
    assert Path(dest).read_bytes() == payload
    assert seen == [(4, 16), (8, 16), (12, 16), (16, 16)]


def test_http_get_progress_total_unknown(monkeypatch, tmp_path):
    """无 Content-Length：total=None 仍逐块回调（候选B 后改不变量断言：
    单调递增 + 终态 (N, None) + 落盘字节完整）。"""
    payload = b"0123456789"
    seen = []
    _patch_build_opener(
        monkeypatch,
        lambda req: _StreamResponse(payload, chunk=5, total=None))
    dest = str(tmp_path / "x.whl")
    dm._http_get("https://files.pythonhosted.org/x.whl", dest,
                 progress=lambda n, t: seen.append((n, t)))
    assert Path(dest).read_bytes() == payload
    ns = [n for n, _ in seen]
    assert ns == sorted(ns) and len(set(ns)) == len(ns), \
        "downloaded 计数必须严格单调递增"
    assert seen[-1] == (len(payload), None), "终态不变量 (N, total)"
    assert all(t is None for _, t in seen)


def test_http_get_default_progress_none_streaming(tmp_path, monkeypatch):
    """2.5.0 修复A：progress 缺省 None 也统一流式落盘（1MB 分块直写盘、
    不全量进内存），仅不上报进度；落位字节完整、无 .part 残留。"""
    payload = b"abcdefgh" * 2
    _patch_build_opener(
        monkeypatch,
        lambda req: _StreamResponse(payload, chunk=5, total=len(payload)))
    dest = str(tmp_path / "x.whl")
    dm._http_get("https://files.pythonhosted.org/x.whl", dest)
    assert Path(dest).read_bytes() == payload
    assert not Path(dest + ".part").exists()


def test_http_get_sends_accept_encoding_identity(monkeypatch, tmp_path):
    """D2026-1004-01 C1：请求头带 Accept-Encoding: identity（防代理/gzip
    注入，pin 校验按落盘字节）。"""
    captured = {}

    def _responder(req):
        # urllib 对 header 键做首词归一（如 Accept-encoding），
        # 侧写时保留原始键、断言时统一小写比对
        captured["headers"] = dict(req.headers)
        return _StreamResponse(b"ok", chunk=64, total=2)

    _patch_build_opener(monkeypatch, _responder)
    dest = str(tmp_path / "x.whl")
    dm._http_get("https://files.pythonhosted.org/x.whl", dest)
    hdrs = {k.lower(): v for k, v in captured["headers"].items()}
    assert hdrs.get("accept-encoding") == "identity"


def test_http_get_content_length_mismatch_is_network_error(monkeypatch,
                                                           tmp_path):
    """D2026-1004-01：声明 Content-Length 与实收不符=网络层失败——
    DictDownloadError 且消息含「预期/实收」字样；.part 已清、dest 未落位。"""
    payload = b"x" * 50
    _patch_build_opener(
        monkeypatch,
        lambda req: _StreamResponse(payload, chunk=64, total=100))
    dest = str(tmp_path / "x.whl")
    with pytest.raises(dm.DictDownloadError) as ei:
        dm._http_get("https://files.pythonhosted.org/x.whl", dest)
    assert "预期 100 字节" in str(ei.value)
    assert "实收 50 字节" in str(ei.value)
    assert not Path(dest).exists()
    assert not Path(dest + ".part").exists()


def test_http_get_poison_proxy_falls_back_direct(monkeypatch, tmp_path):
    """D2026-1004-01 候选B C8：毒代理坏损 → attempt#1（系统代理，语义
    仅指首发）失败、attempt#2 强制直连成功——build_opener 恰 2 次，第 2
    次 handlers 含空 ProxyHandler，两跳均含 _DictGuardedRedirectHandler。"""
    payload = b"PROXY-FALLBACK"
    monkeypatch.setattr(urllib.request, "getproxies",
                        lambda: {"https": "http://127.0.0.1:1"})
    handlers_seen, open_calls = _patch_build_opener(
        monkeypatch,
        lambda req: _StreamResponse(payload, chunk=64, total=len(payload)),
        poison_proxies=True)
    dest = str(tmp_path / "x.whl")
    dm._http_get("https://files.pythonhosted.org/x.whl", dest)
    assert Path(dest).read_bytes() == payload
    assert len(handlers_seen) == 2, "build_opener 恰调 2 次（两跳）"
    assert len(open_calls) == 2
    first, second = handlers_seen
    # attempt#1 不显式装 ProxyHandler（系统代理经默认处理器挂载）
    assert not any(isinstance(h, urllib.request.ProxyHandler)
                   for h in first)
    # attempt#2 显式空 ProxyHandler（proxies=={}）= 强制直连
    ph2 = [h for h in second if isinstance(h, urllib.request.ProxyHandler)]
    assert len(ph2) == 1 and ph2[0].proxies == {}
    # 两跳均挂逐跳守卫 handler（C6 集成面）
    for handlers in (first, second):
        assert any(isinstance(h, dm._DictGuardedRedirectHandler)
                   for h in handlers)


def test_checksum_mismatch_never_retried(monkeypatch, tmp_path):
    """D2026-1004-01 C2（防洗白，D2026-1003-06 边界）：清单 pin 错 →
    DictChecksumError 且底层 fetch 恰 1 次——无直连重试、无换源轮换；
    双源变体：第 1 源校验失败后第 2 源零请求、异常上抛不被吞。"""
    wheel = _fake_wheel()
    # 单源清单：fetch 恰 1 次（attempt#1 成功即止，无直连重试跳）
    handlers_seen, open_calls = _patch_build_opener(
        monkeypatch,
        lambda req: _StreamResponse(wheel, chunk=64, total=len(wheel)))
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": "0" * 64, "sha256_verified": True}])
    with pytest.raises(dm.DictChecksumError):
        dm.download_dict("sudachi")
    assert len(open_calls) == 1
    assert len(handlers_seen) == 1

    # 双源变体：第 1 源校验失败 → 换新桩重新计数，仍恰 1 次 fetch
    handlers_seen, open_calls = _patch_build_opener(
        monkeypatch,
        lambda req: _StreamResponse(wheel, chunk=64, total=len(wheel)))
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": "0" * 64, "sha256_verified": True},
        {"source": "tuna", "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": "0" * 64, "sha256_verified": True}])
    with pytest.raises(dm.DictChecksumError):
        dm.download_dict("sudachi")
    assert len(open_calls) == 1, "校验失败不得换源再 fetch"
    assert len(handlers_seen) == 1, "校验失败不得触发直连重试跳"


def test_dict_redirect_guard_blocks_nonwhitelist():
    """D2026-1004-01 C6：_DictGuardedRedirectHandler 逐跳守卫——302 目标
    非 https 或域名不在白名单 → DictDownloadError（fp 先关闭）；白名单内
    目标放行。（集成面由 poison-proxy 测试的两跳 handlers 断言覆盖）"""
    handler = dm._DictGuardedRedirectHandler()

    class _FP:
        def __init__(self):
            self.closed = False

        def close(self):
            self.closed = True

    req = urllib.request.Request("https://files.pythonhosted.org/a.whl")
    for bad in ("http://files.pythonhosted.org/a.whl",        # 降级 http
                "https://evil.example/a.whl"):                # 非白名单 host
        fp = _FP()
        with pytest.raises(dm.DictDownloadError):
            handler.redirect_request(req, fp, 302, "Found", {}, bad)
        assert fp.closed, "拒绝前必须先关闭半开连接"
    good = handler.redirect_request(req, _FP(), 302, "Found", {},
                                    "https://pypi.org/b.whl")
    assert isinstance(good, urllib.request.Request)
    assert good.full_url == "https://pypi.org/b.whl"


def test_failed_snapshot_carries_diag(monkeypatch, tmp_path):
    """D2026-1004-01 C3：CL 不符走完 download_dict → phase=failed 且快照
    带 diag（_DIAG_FIELDS 七键齐全；proxy ∈ {system, direct}、attempts
    ∈ {1, 2}）；.part 残留已清。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": "1" * 64, "sha256_verified": True}])
    _patch_build_opener(
        monkeypatch,
        lambda req: _StreamResponse(b"x" * 50, chunk=64, total=100))
    with pytest.raises(dm.DictDownloadError):
        dm.download_dict("sudachi")
    snap = dm.download_progress("sudachi")
    assert snap["phase"] == "failed"
    diag = snap["diag"]
    assert set(diag) == set(dm._DIAG_FIELDS)
    assert diag["expected_bytes"] == 100
    assert diag["actual_bytes"] == 50
    assert diag["proxy"] in {"system", "direct"}
    assert diag["attempts"] in {1, 2}
    assert "pythonhosted" in diag["url"]
    assert not list((tmp_path / "dict" / "sudachi").glob("*.part"))


def test_download_dict_progress_phase_chain(monkeypatch, tmp_path):
    """网络成功全链：download→verify→extract→done（done 带最终字节数）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/x.whl",
         "sha256": sha, "sha256_verified": True}])
    phases = []
    real_set = dm._set_download_progress

    def _spy(kind, phase, downloaded=0, total=None, error=None):
        phases.append(phase)
        real_set(kind, phase, downloaded, total, error)

    monkeypatch.setattr(dm, "_set_download_progress", _spy)
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None, stop_event=None:
                        Path(dest).write_bytes(wheel))
    target = dm.download_dict("sudachi")
    assert Path(target).is_file()
    assert phases[0] == "download"
    assert phases.index("verify") > phases.index("download")
    assert phases.index("extract") > phases.index("verify")
    assert phases[-1] == "done"
    assert dm.download_progress("sudachi") == {
        "kind": "sudachi", "phase": "done",
        "downloaded": 7, "total": 7, "error": None}   # b"DICDATA"=7 字节


def test_download_dict_progress_reset_per_source(monkeypatch, tmp_path):
    """跨源 fallback：每源重置 downloaded=0/total=None，计数不跨源残留。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": sha, "sha256_verified": True},
        {"source": "tuna", "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": sha, "sha256_verified": True}])
    writes = []
    real_set = dm._set_download_progress

    def _spy(kind, phase, downloaded=0, total=None, error=None):
        writes.append((phase, downloaded, total))
        real_set(kind, phase, downloaded, total, error)

    monkeypatch.setattr(dm, "_set_download_progress", _spy)

    def _flaky(url, dest, progress=None, stop_event=None):
        if "tuna" not in url:
            progress(8, 100)          # 主源推进计数后网络断
            raise dm.DictDownloadError("连接超时")
        Path(dest).write_bytes(wheel)

    monkeypatch.setattr(dm, "_http_get", _flaky)
    assert Path(dm.download_dict("sudachi")).is_file()
    resets = [w for w in writes if w == ("download", 0, None)]
    assert len(resets) == 2           # 初始 + 镜像源各重置一次
    assert dm.download_progress("sudachi")["phase"] == "done"


def test_download_dict_progress_failed_phase(monkeypatch, tmp_path):
    """全源失败：phase=failed + error 文案，异常照旧向上抛（api 语义不变）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": "1" * 64, "sha256_verified": True}])

    def _down(url, dest, progress=None, stop_event=None):
        raise dm.DictDownloadError("网络不可达")

    monkeypatch.setattr(dm, "_http_get", _down)
    with pytest.raises(dm.DictDownloadError):
        dm.download_dict("sudachi")
    snap = dm.download_progress("sudachi")
    assert snap["phase"] == "failed"
    assert "网络不可达" in snap["error"]


def test_download_progress_no_record_returns_empty(monkeypatch):
    """无下载记录：download_progress 返回空 dict（只读零副作用）。"""
    assert dm.download_progress("sudachi") == {}
    assert dm.download_progress("nope") == {}


def test_local_wheel_import_verifies_hash(monkeypatch, tmp_path):
    """离线导入：wheel 哈希相符落位，不符拒绝。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": sha, "sha256_verified": True}])
    local = tmp_path / "manual.whl"
    local.write_bytes(wheel)
    target = dm.download_dict("sudachi", local_file=str(local))
    assert Path(target).read_bytes() == b"DICDATA"
    bad = tmp_path / "bad.whl"
    bad.write_bytes(_fake_wheel(payload=b"TAMPERED"))
    import pytest
    with pytest.raises(dm.DictChecksumError):
        dm.download_dict("sudachi", local_file=str(bad))


def test_url_allowlist_blocks_non_https_and_unknown_host():
    import pytest
    with pytest.raises(dm.DictDownloadError):
        dm._validate_url("http://files.pythonhosted.org/a.whl")
    with pytest.raises(dm.DictDownloadError):
        dm._validate_url("https://internal.example/a.whl")
    assert dm._validate_url(
        "https://files.pythonhosted.org/a.whl") == \
        "https://files.pythonhosted.org/a.whl"


# ---------------------------------------------------------------------------
# 状态与 grammar_hint 接线
# ---------------------------------------------------------------------------
def test_dict_status_structure(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    st = dm.dict_status()
    # 2.5.0 修复A：kind 架构增 sudachi_full（core 零迁移，full=文件存在判定）
    assert set(st["dicts"]) == {"sudachi", "sudachi_full", "jieba",
                                "english_rules"}
    assert st["dicts"]["english_rules"]["available"] is True
    assert isinstance(st["dicts"]["jieba"]["available"], bool)
    assert st["dicts"]["sudachi"]["custom_path"] == ""
    # 全新数据根：full 未下载 → available=False（防恒 True 错报）
    assert st["dicts"]["sudachi_full"]["available"] is False


def test_sudachi_custom_dict_path_when_present(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    dic = tmp_path / "dict" / "sudachi" / "system_core.dic"
    dic.parent.mkdir(parents=True)
    dic.write_bytes(b"dic")
    assert dm.sudachi_custom_dict_path() == str(dic)


def test_get_tokenizer_prefers_custom_dict(monkeypatch, tmp_path):
    """grammar_hint 单例：存在用户下载词典时按路径构造。"""
    from subtransjav.refine import grammar_hint as gh
    fake_dic = tmp_path / "system_core.dic"
    fake_dic.write_bytes(b"dic")
    monkeypatch.setattr(dm, "sudachi_custom_dict_path",
                        lambda: str(fake_dic))
    seen: dict = {}

    class _FakeTok:
        pass

    class _FakeDict:
        def __init__(self, dict=None, **kw):  # noqa: A002 - 上游参数名
            seen["dict"] = dict

        def create(self):
            return _FakeTok()

    monkeypatch.setitem(sys.modules, "sudachipy",
                        types.SimpleNamespace(Dictionary=_FakeDict))
    monkeypatch.setattr(gh, "_tokenizer_instance", None)
    monkeypatch.setattr(gh, "_sudachi_available", None)
    tok = gh._get_tokenizer()
    assert isinstance(tok, _FakeTok)
    assert seen["dict"] == str(fake_dic)


# ---------------------------------------------------------------------------
# CLI 冒烟
# ---------------------------------------------------------------------------
def test_cli_dict_status_smoke(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    from subtransjav.refine import cli
    assert cli.main(["--dict-status"]) == 0
    out = capsys.readouterr().out
    assert "sudachi" in out and "jieba" in out and "english_rules" in out


def test_cli_dict_download_local_missing_file(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    from subtransjav.refine import cli
    rc = cli.main(["--dict-download", "sudachi",
                   "--dict-from-file", str(tmp_path / "nope.whl")])
    assert rc == 1
    assert "下载失败" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 2.6.3 批B（D2026-1003-06 条件②①）：download_dict source 三态 + note 回退提示
# ---------------------------------------------------------------------------
def _manifest_full(monkeypatch, sha: str) -> None:
    """把源清单 sudachi_full downloads 替换为测试用条目。"""
    base = dm.load_source_manifest()
    full = {**base["dicts"]["sudachi_full"], "downloads": [
        {"source": "cloudfront-cdn",
         "url": "https://d2ej7fkh96fzlu.cloudfront.net/full.zip",
         "sha256": sha, "sha256_verified": True}]}
    monkeypatch.setattr(dm, "load_source_manifest", lambda: {
        **base, "dicts": {**base["dicts"], "sudachi_full": full}})


def test_download_dict_source_official_keeps_cloudfront(monkeypatch, tmp_path):
    """评议员条件②核心用例：official=排除镜像而非只留 pypi——sudachi_full
    官方源就是 cloudfront-cdn，official 模式不得空集。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    zbuf = _fake_wheel(member="system_full.dic")
    sha = hashlib.sha256(zbuf).hexdigest()
    _manifest_full(monkeypatch, sha)
    calls = []
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None, stop_event=None:
                        (calls.append(url), Path(dest).write_bytes(zbuf)))
    target = dm.download_dict("sudachi_full", source="official")
    assert Path(target).is_file()
    assert calls == ["https://d2ej7fkh96fzlu.cloudfront.net/full.zip"]


def test_download_dict_source_mirror_full_no_mirror(monkeypatch, tmp_path):
    """真实清单事实（2.7.3 件②只接线不点亮）：sudachi_full 的 hf-mirror
    条目 sha256_verified=false 未点亮，不入镜像池——mirror 模式显式报错。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    with pytest.raises(dm.DictDownloadError, match="无镜像源"):
        dm.download_dict("sudachi_full", source="mirror")


def test_mirror_pool_excludes_empty_url_placeholder(monkeypatch):
    """code-review 触碰式修复③钉：镜像占位条目（url=""）即使 verified 被
    翻 true 且开 allow_unverified 双保险也不入池——空 URL 入池必下载失败
    并打「镜像源不可达，已回退」假 note，与未点亮同门排除（报「无镜像源」
    而非发起注定失败的请求）。"""
    base = dm.load_source_manifest()
    full = {**base["dicts"]["sudachi_full"], "downloads": [
        {"source": "hf-mirror", "role": "mirror", "url": "",
         "sha256": "a" * 64, "sha256_verified": True},
        {"source": "cloudfront-cdn",
         "url": "https://d2ej7fkh96fzlu.cloudfront.net/full.zip",
         "sha256": "b" * 64, "sha256_verified": True}]}
    monkeypatch.setattr(dm, "load_source_manifest", lambda: {
        **base, "dicts": {**base["dicts"], "sudachi_full": full}})
    with pytest.raises(dm.DictDownloadError, match="无镜像源"):
        dm.download_dict("sudachi_full", source="mirror",
                         allow_unverified=True)


def test_download_dict_source_official_and_mirror_split(monkeypatch, tmp_path):
    """sudachi 双源分流：official 只走 pypi（排除 role=mirror 的 tuna）；
    mirror 只走 tuna。（2.7.3 件② role 旗标泛化：fixture 随清单语义补
    role=mirror——verified 镜像不因角色混入 official 池。）"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": sha, "sha256_verified": True},
        {"source": "tuna", "role": "mirror",
         "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": sha, "sha256_verified": True}])
    calls = []
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None, stop_event=None:
                        (calls.append(url), Path(dest).write_bytes(wheel)))
    assert Path(dm.download_dict("sudachi", source="official")).is_file()
    assert calls == ["https://files.pythonhosted.org/a.whl"]
    calls.clear()
    assert Path(dm.download_dict("sudachi", source="mirror")).is_file()
    assert calls == ["https://pypi.tuna.tsinghua.edu.cn/b.whl"]


def test_download_dict_fallback_note_visible(monkeypatch, tmp_path):
    """评议员条件①：auto 轮换由静默升级为可见——镜像源下载期间快照带
    粘滞 note（1s 轮询必能采样）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": sha, "sha256_verified": True},
        {"source": "tuna", "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": sha, "sha256_verified": True}])
    seen = {}

    def _flaky(url, dest, progress=None, stop_event=None):
        if "tuna" not in url:
            raise dm.DictDownloadError("连接超时")

        def _p(n, t):
            progress(n, t)
            seen["snap"] = dm.download_progress("sudachi")

        _p(5, 7)
        Path(dest).write_bytes(wheel)

    monkeypatch.setattr(dm, "_http_get", _flaky)
    assert Path(dm.download_dict("sudachi")).is_file()
    assert seen["snap"].get("note") == "官方源不可达，已回退镜像源"


def test_download_dict_invalid_source_falls_back_auto(monkeypatch, tmp_path):
    """非法 source 按 auto（顺序全取：pypi 失败轮换 tuna 成功）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": sha, "sha256_verified": True},
        {"source": "tuna", "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": sha, "sha256_verified": True}])
    calls = []

    def _flaky(url, dest, progress=None, stop_event=None):
        calls.append(url)
        if "tuna" not in url:
            raise dm.DictDownloadError("连接超时")
        Path(dest).write_bytes(wheel)

    monkeypatch.setattr(dm, "_http_get", _flaky)
    assert Path(dm.download_dict("sudachi", source="bogus")).is_file()
    assert calls == ["https://files.pythonhosted.org/a.whl",
                     "https://pypi.tuna.tsinghua.edu.cn/b.whl"]


def test_dict_status_sources_summary(monkeypatch, tmp_path):
    """sources 摘要键：从清单推导，仅 target_name 非空 kind（追加式，不删
    既有断言——test_dict_status_structure 不受扰）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    st = dm.dict_status()
    s = st["sources"]
    assert s["sudachi"] == {"has_official": True, "has_mirror": True}
    assert s["sudachi_full"] == {"has_official": True, "has_mirror": False}
    assert "jieba" not in s and "english_rules" not in s


# ---------------------------------------------------------------------------
# 2.7.3 件②（D2026-1005-05）：下载镜像提速接线——role 旗标泛化 + hf-mirror
#（只接线不点亮：未点亮镜像不入任何下载池、GUI 不虚亮；点亮=owner 上传
# 后另走生产路径核验转 verified）
# ---------------------------------------------------------------------------
def _manifest_full_with_mirror(monkeypatch, sha: str,
                               mirror_verified: bool) -> None:
    """sudachi_full downloads 替换为真实形状 [hf-mirror, cloudfront]
    （镜像在前=JSON 列表序；点亮态由 mirror_verified 控制）。"""
    mirror_url = ("https://hf-mirror.com/resolve/abc/full.zip"
                  if mirror_verified else "")
    base = dm.load_source_manifest()
    full = {**base["dicts"]["sudachi_full"], "downloads": [
        {"source": "hf-mirror", "role": "mirror",
         "url": mirror_url, "sha256": sha,
         "sha256_verified": mirror_verified},
        {"source": "cloudfront-cdn",
         "url": "https://d2ej7fkh96fzlu.cloudfront.net/full.zip",
         "sha256": sha, "sha256_verified": True}]}
    monkeypatch.setattr(dm, "load_source_manifest", lambda: {
        **base, "dicts": {**base["dicts"], "sudachi_full": full}})


def test_source_manifest_mirror_role_pinned():
    """清单钉：core 的 tuna 带 role=mirror（pypi 无 role=官方）；sudachi_full
    在 cloudfront 之前有未点亮 hf-mirror 条目（url 待填、sha256 同 pin——
    列表序=点亮后 auto 链镜像优先的实现机制）。"""
    m = dm.load_source_manifest()
    core = m["dicts"]["sudachi"]["downloads"]
    assert core[0].get("role") is None, "pypi 官方条目不得带 mirror role"
    assert core[1].get("role") == "mirror"
    full = m["dicts"]["sudachi_full"]["downloads"]
    assert [d["source"] for d in full] == ["hf-mirror", "cloudfront-cdn"]
    mirror = full[0]
    assert mirror.get("role") == "mirror"
    assert mirror["url"] == "", "未点亮镜像 url 必须为空（待 owner 上传后填）"
    assert mirror["sha256_verified"] is False
    assert mirror["sha256"] == full[1]["sha256"], "镜像须与官方源同 pin"
    assert mirror["sha256"] == \
        "eb6d02206e93f1b62508c9f2d4d4940d6f82c7f63c630bc0c1c4f9c50b7e871e"


def test_url_host_allow_mirror_domains_pinned():
    """白名单钉（2026-10-05 生产形态 GET 直连路由 4/4 采样实测两域）：
    hf-mirror.com 与 cas-bridge.xethub.hf.co 放行；被墙源站 huggingface.co
    保持拒绝（经代理 308 回源站，观测不入围）。"""
    assert {"hf-mirror.com", "cas-bridge.xethub.hf.co"} \
        <= dm._URL_HOST_ALLOW
    assert dm._validate_url(
        "https://hf-mirror.com/resolve/abc/sudachi-full.zip")
    assert dm._validate_url(
        "https://cas-bridge.xethub.hf.co/cas/xethub/sudachi-full.zip")
    with pytest.raises(dm.DictDownloadError):
        dm._validate_url("https://huggingface.co/resolve/main/a.zip")


def test_download_dict_unlit_mirror_not_in_any_pool(monkeypatch, tmp_path):
    """未点亮行为钉（只接线不点亮）：sha256_verified=false 的镜像条目不
    入 auto 池（实际只走 cloudfront）；mirror 请求显式报「无镜像源」；
    official 池仍走 cloudfront；GUI 数据面 has_mirror=false（mirBtn
    disabled 的数据源，不虚亮）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    zbuf = _fake_wheel(member="system_full.dic")
    sha = hashlib.sha256(zbuf).hexdigest()
    _manifest_full_with_mirror(monkeypatch, sha, mirror_verified=False)
    calls = []
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None, stop_event=None:
                        (calls.append(url), Path(dest).write_bytes(zbuf)))
    assert Path(dm.download_dict("sudachi_full", source="auto")).is_file()
    assert calls == ["https://d2ej7fkh96fzlu.cloudfront.net/full.zip"]
    with pytest.raises(dm.DictDownloadError, match="无镜像源"):
        dm.download_dict("sudachi_full", source="mirror")
    calls.clear()
    assert Path(dm.download_dict("sudachi_full", source="official")).is_file()
    assert calls == ["https://d2ej7fkh96fzlu.cloudfront.net/full.zip"]
    st = dm.dict_status()["sources"]["sudachi_full"]
    assert st == {"has_official": True, "has_mirror": False}


def test_download_dict_lit_mirror_auto_order_and_fallback_note(
        monkeypatch, tmp_path):
    """点亮模拟钉（fixture 翻转 sha256_verified=true）：auto 链按 JSON 列表
    序 [hf-mirror, cloudfront] 镜像优先；镜像段网络失败自动轮换回
    cloudfront，快照 note 方向感知=「镜像源不可达，已回退官方源」。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    zbuf = _fake_wheel(member="system_full.dic")
    sha = hashlib.sha256(zbuf).hexdigest()
    _manifest_full_with_mirror(monkeypatch, sha, mirror_verified=True)
    calls = []
    seen = {}

    def _flaky(url, dest, progress=None, stop_event=None):
        calls.append(url)
        if "hf-mirror" in url:
            raise dm.DictDownloadError("连接超时")

        def _p(n, t):
            progress(n, t)
            seen["snap"] = dm.download_progress("sudachi_full")

        _p(5, 7)
        Path(dest).write_bytes(zbuf)

    monkeypatch.setattr(dm, "_http_get", _flaky)
    assert Path(dm.download_dict("sudachi_full", source="auto")).is_file()
    assert calls == ["https://hf-mirror.com/resolve/abc/full.zip",
                     "https://d2ej7fkh96fzlu.cloudfront.net/full.zip"]
    assert seen["snap"].get("note") == "镜像源不可达，已回退官方源"


def test_download_dict_lit_mirror_and_official_split(monkeypatch, tmp_path):
    """点亮模拟钉：mirror 请求走 hf-mirror 直链；role 隔离（HRO-2 最严重
    项）——镜像条目即使 sha256_verified=true 也不入 official 池，official
    仍只走 cloudfront（防官方语义被镜像击穿的回归钉）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    zbuf = _fake_wheel(member="system_full.dic")
    sha = hashlib.sha256(zbuf).hexdigest()
    _manifest_full_with_mirror(monkeypatch, sha, mirror_verified=True)
    calls = []
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None, stop_event=None:
                        (calls.append(url), Path(dest).write_bytes(zbuf)))
    assert Path(dm.download_dict("sudachi_full", source="mirror")).is_file()
    assert calls == ["https://hf-mirror.com/resolve/abc/full.zip"]
    calls.clear()
    assert Path(dm.download_dict("sudachi_full", source="official")).is_file()
    assert calls == ["https://d2ej7fkh96fzlu.cloudfront.net/full.zip"]


# ---------------------------------------------------------------------------
# 2.7.3 件①：词典替换 WinError 5 自锁修复（release_tokenizer + 窄域异常）
# ---------------------------------------------------------------------------
def test_replace_locked_release_then_retry_succeeds(monkeypatch, tmp_path):
    """os.replace 首抛 PermissionError → 释放分词器（侦确认被调）→
    重试成功 → done 快照且词典落位。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": sha, "sha256_verified": True}])
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None, stop_event=None:
                        Path(dest).write_bytes(wheel))
    real_replace = dm.os.replace
    state = {"first": True}

    def _flaky_replace(src, dst):
        if str(src).endswith(".extracting") and state["first"]:
            state["first"] = False
            raise PermissionError(5, "拒绝访问。")
        return real_replace(src, dst)

    monkeypatch.setattr(dm.os, "replace", _flaky_replace)

    import subtransjav.refine.grammar_hint as gh
    released = []

    def _fake_release(after_release=None):
        released.append(True)
        if after_release is not None:
            after_release()

    monkeypatch.setattr(gh, "release_tokenizer", _fake_release)

    target = dm.download_dict("sudachi")
    assert Path(target).read_bytes() == b"DICDATA"
    assert released == [True], "替换被锁必须经 release_tokenizer 释放后重试"
    assert dm.download_progress("sudachi")["phase"] == "done"
    assert not any((tmp_path / "dict" / "sudachi").glob("*.extracting"))


def test_replace_locked_persists_raises_narrow_error(monkeypatch, tmp_path):
    """重试仍被锁 → 窄域异常（不继承 DictDownloadError，不轮换、无回退
    note）+ failed 快照人话消息 + .downloading/.extracting 残件清理。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": sha, "sha256_verified": True},
        {"source": "tuna", "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": sha, "sha256_verified": True}])
    calls = []

    def _fake_get(url, dest, progress=None, stop_event=None):
        calls.append(url)
        Path(dest).write_bytes(wheel)

    monkeypatch.setattr(dm, "_http_get", _fake_get)

    def _always_locked(src, dst):
        raise PermissionError(5, "拒绝访问。")

    monkeypatch.setattr(dm.os, "replace", _always_locked)

    import subtransjav.refine.grammar_hint as gh

    def _fake_release(after_release=None):
        # 模拟真实契约：重试闭包必被调（仍抛 PermissionError → 窄域异常）
        if after_release is not None:
            after_release()

    monkeypatch.setattr(gh, "release_tokenizer", _fake_release)

    with pytest.raises(dm.DictReplaceLockedError) as ei:
        dm.download_dict("sudachi")
    msg = str(ei.value)
    assert "重启" in msg, "人话消息须含「重启」对冲指引"
    # 窄域异常不得是 DictDownloadError 子类（防误触跨源轮换）
    assert not isinstance(ei.value, dm.DictDownloadError)
    assert len(calls) == 1, "替换被锁不得轮换下一源"
    snap = dm.download_progress("sudachi")
    assert snap["phase"] == "failed"
    assert "重启" in snap["error"]
    assert "note" not in snap, "替换被锁不得打「已回退镜像源」note"
    d = tmp_path / "dict" / "sudachi"
    assert not any(d.glob("system_core.dic.downloading*"))
    assert not any(d.glob("*.extracting"))


def test_extracting_tmp_cleaned_on_mid_extract_error(monkeypatch, tmp_path):
    """解压中途 IO 异常 → DictChecksumError 且 .extracting 残件清理
    （补断言：_extract_dic 内 :555-561 清理覆盖解压循环抛错路径）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    out = tmp_path / "out.dic"

    class _BrokenSrc:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, n):
            raise OSError("simulated mid-extract IO failure")

    class _FakeZipInfo:
        file_size = 100

    class _FakeZip:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def namelist(self):
            return ["sudachidict_core/resources/system.dic"]

        def getinfo(self, name):
            return _FakeZipInfo()

        def open(self, name):
            return _BrokenSrc()

    monkeypatch.setattr(dm.zipfile, "ZipFile", lambda *a, **k: _FakeZip())
    archive = tmp_path / "fake.whl"
    archive.write_bytes(b"not-a-real-zip")
    with pytest.raises(dm.DictChecksumError):
        dm._extract_dic(str(archive),
                        "sudachidict_core/resources/system.dic", str(out))
    assert not out.exists()
    assert not (tmp_path / "out.dic.extracting").exists()


# ---------------------------------------------------------------------------
# 2.7.3 件⑤：词典下载协作式停止（DictDownloadStopped 三处显式透传 +
# stopped 快照收口；检查点=attempt 循环头/1MB 分块循环每拍/4MB 解压循环
# 每拍/源循环头）
# ---------------------------------------------------------------------------
def test_dict_download_stopped_not_download_error_subclass():
    """钉：DictDownloadStopped 不得继承 DictDownloadError（防误触直连
    重试/跨源轮换/假回退 note——与 DictReplaceLockedError 同裁定）。"""
    assert not issubclass(dm.DictDownloadStopped, dm.DictDownloadError)


def test_http_get_stop_in_chunk_loop_no_attempt2(monkeypatch, tmp_path):
    """分块循环中置位 stop → DictDownloadStopped 透传：不被通用包裹吞成
    DictDownloadError、不触发 attempt#2 直连重试（断言仅一次源访问）；
    .part 残件清理。"""
    payload = b"abcdefgh" * 2                   # 16 字节，chunk 4 → 多拍
    stop = threading.Event()
    seen = []

    def _progress(n, t):
        seen.append(n)
        stop.set()                              # 首拍置位 → 下拍循环头抛出

    _, open_calls = _patch_build_opener(
        monkeypatch,
        lambda req: _StreamResponse(payload, chunk=4, total=len(payload)))
    dest = str(tmp_path / "x.whl")
    with pytest.raises(dm.DictDownloadStopped) as ei:
        dm._http_get("https://files.pythonhosted.org/x.whl", dest,
                     progress=_progress, stop_event=stop)
    assert not isinstance(ei.value, dm.DictDownloadError), \
        "停止异常不得被通用包裹转成 DictDownloadError"
    assert len(open_calls) == 1, "停止不得触发 attempt#2 直连重试"
    assert seen == [4], "置位后须在下一拍循环头停止（不多读分块）"
    assert not Path(dest + ".part").exists(), "停止路径须清理 .part 残件"


def test_download_dict_stop_at_source_loop_head(monkeypatch, tmp_path):
    """源循环头置位 → 首源未访问、第二源未尝试；收口 stopped 快照
    （note 带重下指引、不写 error/diag）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": "1" * 64, "sha256_verified": True},
        {"source": "tuna", "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": "2" * 64, "sha256_verified": True}])
    calls = []

    def _fake_get(url, dest, progress=None, stop_event=None):
        calls.append(url)

    monkeypatch.setattr(dm, "_http_get", _fake_get)
    stop = threading.Event()
    stop.set()
    with pytest.raises(dm.DictDownloadStopped):
        dm.download_dict("sudachi", stop_event=stop)
    assert calls == [], "源循环头检查点须先于任何源访问（双源均未尝试）"
    snap = dm.download_progress("sudachi")
    assert snap["phase"] == "stopped"
    assert "已停止下载" in snap["note"]
    assert snap["error"] is None and "diag" not in snap


def test_download_dict_stop_not_swallowed_by_rotation(monkeypatch, tmp_path):
    """源#1 下载中置位 → 源轮换捕获不得吞掉 DictDownloadStopped：第二源
    未尝试、不打「已回退」假 note，收口 stopped 快照。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": "1" * 64, "sha256_verified": True},
        {"source": "tuna", "url": "https://pypi.tuna.tsinghua.edu.cn/b.whl",
         "sha256": "2" * 64, "sha256_verified": True}])
    calls = []

    def _fake_get(url, dest, progress=None, stop_event=None):
        calls.append(url)
        if stop_event is not None:
            stop_event.set()
        raise dm.DictDownloadStopped("词典下载已被用户停止")

    monkeypatch.setattr(dm, "_http_get", _fake_get)
    stop = threading.Event()
    with pytest.raises(dm.DictDownloadStopped):
        dm.download_dict("sudachi", stop_event=stop)
    assert calls == ["https://files.pythonhosted.org/a.whl"], \
        "停止不得轮换第二源"
    snap = dm.download_progress("sudachi")
    assert snap["phase"] == "stopped"
    assert "已回退" not in snap.get("note", ""), "停止不得打「已回退」假 note"


def test_download_dict_stop_in_extract_loop_cleanup(monkeypatch, tmp_path):
    """解压循环置位 → stopped 快照（note 指引）+ .downloading/.extracting
    残件清理（复用件①清理链）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    sha = hashlib.sha256(wheel).hexdigest()
    _manifest_with_downloads(monkeypatch, [
        {"source": "pypi", "url": "https://files.pythonhosted.org/a.whl",
         "sha256": sha, "sha256_verified": True}])
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None, stop_event=None:
                        Path(dest).write_bytes(wheel))
    stop = threading.Event()
    real_sha = dm._sha256_of

    def _sha_then_stop(path):
        out = real_sha(path)
        stop.set()                  # 校验通过后、解压前置位 → 解压循环首拍停止
        return out

    monkeypatch.setattr(dm, "_sha256_of", _sha_then_stop)
    with pytest.raises(dm.DictDownloadStopped):
        dm.download_dict("sudachi", stop_event=stop)
    snap = dm.download_progress("sudachi")
    assert snap["phase"] == "stopped"
    assert "可切换网络代理后重新下载" in snap["note"]
    assert snap["error"] is None and "diag" not in snap
    d = tmp_path / "dict" / "sudachi"
    assert not any(d.glob("system_core.dic.downloading*"))
    assert not any(d.glob("*.extracting"))
