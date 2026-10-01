"""dict_manager 词典管理单元测试（2.1 基建，D2026-0930-03 ②④）。

零真实网络：urlopen 一律 monkeypatch；哈希用当次构造内容现算。
"""
import hashlib
import io
import sys
import types
import zipfile
from pathlib import Path

import pytest

from subtransjav.refine import dict_manager as dm


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
                        lambda url, dest, progress=None:
                        Path(dest).write_bytes(wheel))
    target = dm.download_dict("sudachi")
    assert Path(target) == tmp_path / "dict" / "sudachi" / "system_core.dic"
    assert Path(target).read_bytes() == b"DICDATA"


def test_download_dict_checksum_error_no_fallback(monkeypatch, tmp_path):
    """SHA256 不符：拒绝落位且不轮换下一源（防串改文件换源洗白）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    calls = []

    def _fake_get(url, dest, progress=None):
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

    def _fake_get(url, dest, progress=None):
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

    def _always_down(url, dest, progress=None):
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


def test_http_get_progress_callback_chunks(monkeypatch, tmp_path):
    """分块 read + Content-Length → progress 回调序列 (n, total) 单调递增。"""
    payload = b"abcdefgh" * 2                       # 16 字节，chunk 4 → 4 块
    seen = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=10: _StreamResponse(payload, chunk=4,
                                                total=len(payload)))
    dest = str(tmp_path / "x.whl")
    dm._http_get("https://files.pythonhosted.org/x.whl", dest,
                 progress=lambda n, t: seen.append((n, t)))
    assert Path(dest).read_bytes() == payload
    assert seen == [(4, 16), (8, 16), (12, 16), (16, 16)]


def test_http_get_progress_total_unknown(monkeypatch, tmp_path):
    """无 Content-Length：total=None 仍逐块回调，落位字节完整。"""
    payload = b"0123456789"
    seen = []
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=10: _StreamResponse(payload, chunk=5, total=None))
    dest = str(tmp_path / "x.whl")
    dm._http_get("https://files.pythonhosted.org/x.whl", dest,
                 progress=lambda n, t: seen.append((n, t)))
    assert Path(dest).read_bytes() == payload
    assert seen == [(5, None), (10, None)]


def test_http_get_default_progress_none_streaming(tmp_path, monkeypatch):
    """2.5.0 修复A：progress 缺省 None 也统一流式落盘（1MB 分块直写盘、
    不全量进内存），仅不上报进度；落位字节完整、无 .part 残留。"""
    payload = b"abcdefgh" * 2
    monkeypatch.setattr(
        "urllib.request.urlopen",
        lambda req, timeout=10: _StreamResponse(payload, chunk=5, total=16))
    dest = str(tmp_path / "x.whl")
    dm._http_get("https://files.pythonhosted.org/x.whl", dest)
    assert Path(dest).read_bytes() == payload
    assert not Path(dest + ".part").exists()


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
                        lambda url, dest, progress=None:
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

    def _flaky(url, dest, progress=None):
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

    def _down(url, dest, progress=None):
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
