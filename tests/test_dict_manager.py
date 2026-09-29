"""dict_manager 词典管理单元测试（2.1 基建，D2026-0930-03 ②④）。

零真实网络：urlopen 一律 monkeypatch；哈希用当次构造内容现算。
"""
import hashlib
import io
import sys
import types
import zipfile
from pathlib import Path

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
                        lambda url, dest: Path(dest).write_bytes(wheel))
    target = dm.download_dict("sudachi")
    assert Path(target) == tmp_path / "dict" / "sudachi" / "system_core.dic"
    assert Path(target).read_bytes() == b"DICDATA"


def test_download_dict_checksum_error_no_fallback(monkeypatch, tmp_path):
    """SHA256 不符：拒绝落位且不轮换下一源（防串改文件换源洗白）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    wheel = _fake_wheel()
    calls = []

    def _fake_get(url, dest):
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

    def _fake_get(url, dest):
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

    def _always_down(url, dest):
        raise dm.DictDownloadError("网络不可达")

    monkeypatch.setattr(dm, "_http_get", _always_down)
    import pytest
    with pytest.raises(dm.DictDownloadError):
        dm.download_dict("sudachi")


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
    assert set(st["dicts"]) == {"sudachi", "jieba", "english_rules"}
    assert st["dicts"]["english_rules"]["available"] is True
    assert isinstance(st["dicts"]["jieba"]["available"], bool)
    assert st["dicts"]["sudachi"]["custom_path"] == ""


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
