"""批1b（D2026-1002-12）测试：词典目录设置 + 一键迁移 + 首启数据目录引导。

覆盖五块（不依赖真实 C:/D: 盘，全部 monkeypatch 模拟路径）：
1. effective_dict_dir 解析：未设置=数据根/dict；设置后覆盖（kind_dir/
   download 落位/状态全跟随）；清除恢复；
1b. 三级优先级（规划员追补裁定）：user_dirs.json dict_dir 键直读
   （跨进程单源）——JSON 键生效/损坏跳过/空键跳过/优先级覆盖>JSON>默认/
   mtime 缓存命中与失效/换数据根不串值；
1c. 系统目录黑名单净化守卫（追补②）：四根根本身/子路径/大小写变体拦截、
   旁系不误伤、①②消费流命中均静默回退、扩展前缀还原；
2. migrate_dicts：正常复制+哈希；同名同 size 跳过（可续传）；size 不符
   重拷；哈希损坏报错不标记（目标无半截产物）；源文件保留断言；
3. API 面：refine_pick_dict_dir / refine_clear_dict_dir /
   refine_dict_migrate 返回契约；未设置自定义目录时 migrate 拒绝；
4. 引导哨兵：should_show 首真后假；frozen 门（源码形态恒否不落地）。

隔离口径：数据根经 ``SUBTRANSJAV_DATA_ROOT`` 指向 tmp；frozen 哨兵经
``sys.executable`` 指向 tmp（绝不写真实 exe/python 同目录）；dict_manager
进程内自定义目录态、进度表与 JSON 直读缓存每例复位。webview 缺席时仅
API 面用例软跳过。
"""
import hashlib
import json
import os
import sys
from pathlib import Path

import pytest

from subtransjav import paths
from subtransjav.refine import dict_manager as dm


def _norm(path: str | Path) -> str:
    """测试比较口径：resolve + normcase（与 user_dirs 存储语义一致）。"""
    return os.path.normcase(str(Path(path).resolve()))


@pytest.fixture(autouse=True)
def _isolated_dict_state(tmp_path, monkeypatch):
    """每例隔离：数据根指向 tmp + 进程内自定义目录态复位 + 进度表清空
    + user_dirs.json 直读缓存复位（追补裁定后 effective 走三级解析）。"""
    root = tmp_path / "dataroot"
    root.mkdir()
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(root))
    monkeypatch.setattr(dm, "_CUSTOM_DICT_DIR", None)
    monkeypatch.setattr(dm, "_DOWNLOAD_PROGRESS", {})
    monkeypatch.setattr(dm, "_USER_DIRS_CACHE", {"key": None, "value": None})
    yield root


# ---------------------------------------------------------------------------
# 1. effective_dict_dir 解析（件1 单源）
# ---------------------------------------------------------------------------

def test_effective_dict_dir_defaults_to_data_root(_isolated_dict_state):
    """未设置自定义目录 → 数据根/dict（与历史 dict_dir 逐字节一致）。"""
    root = _isolated_dict_state
    assert _norm(dm.effective_dict_dir()) == _norm(root / "dict")
    assert _norm(dm.dict_dir()) == _norm(root / "dict")


def test_set_custom_dir_overrides_and_clear_restores(_isolated_dict_state):
    """设置后全链路覆盖（kind_dir/状态），清除后恢复数据根默认。"""
    root = _isolated_dict_state
    custom = root.parent / "custom_dict"
    custom.mkdir()
    dm.set_custom_dir(str(custom))
    assert dm.get_custom_dir() == str(custom)
    assert _norm(dm.effective_dict_dir()) == _norm(custom)
    assert _norm(dm.kind_dir("sudachi")) == _norm(custom / "sudachi")
    # 清除恢复默认
    dm.set_custom_dir(None)
    assert dm.get_custom_dir() is None
    assert _norm(dm.effective_dict_dir()) == _norm(root / "dict")


def test_kind_dir_and_download_follow_effective_dir(
        _isolated_dict_state, monkeypatch):
    """下载落位走生效目录：自定义目录设置后新下载落到 custom/dict。"""
    import io
    import zipfile
    root = _isolated_dict_state
    custom = root.parent / "custom_dict_dl"
    custom.mkdir()
    dm.set_custom_dir(str(custom))
    assert _norm(dm.kind_dir("sudachi")) == _norm(custom / "sudachi")

    # 走一遍 download_dict（_http_get 打桩，零网络）验证落位
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("sudachidict_core/resources/system.dic", b"DICDATA")
    wheel = buf.getvalue()
    base = dm.load_source_manifest()
    sudachi = {**base["dicts"]["sudachi"],
               "downloads": [{"source": "pypi",
                              "url": "https://files.pythonhosted.org/x.whl",
                              "sha256": hashlib.sha256(wheel).hexdigest(),
                              "sha256_verified": True}]}
    monkeypatch.setattr(dm, "load_source_manifest", lambda: {
        **base, "dicts": {**base["dicts"], "sudachi": sudachi}})
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None, stop_event=None:
                        Path(dest).write_bytes(wheel))
    target = dm.download_dict("sudachi")
    assert Path(target) == custom / "sudachi" / "system_core.dic"


def test_dict_status_reports_custom_and_effective(_isolated_dict_state):
    """dict_status 返回体补 custom_dir（设置值|null）+ effective_dir。"""
    root = _isolated_dict_state
    st = dm.dict_status()
    assert st["custom_dir"] is None
    assert _norm(st["effective_dir"]) == _norm(root / "dict")
    assert _norm(st["dict_dir"]) == _norm(root / "dict")
    custom = root.parent / "custom_status"
    custom.mkdir()
    dm.set_custom_dir(str(custom))
    st2 = dm.dict_status()
    assert st2["custom_dir"] == str(custom)
    assert _norm(st2["effective_dir"]) == _norm(custom)


def test_count_dict_files_two_levels(_isolated_dict_state):
    """count_dict_files：两层级常规文件计数；目录缺失返回 0。"""
    root = _isolated_dict_state
    assert dm.count_dict_files(str(root / "nope")) == 0
    d = root / "olddict" / "sudachi"
    d.mkdir(parents=True)
    (d / "a.dic").write_bytes(b"a")
    (d / "b.dic").write_bytes(b"b")
    (d / "sub").mkdir()                 # 子目录不计
    (d / "sub" / "x").write_bytes(b"x")
    assert dm.count_dict_files(str(root / "olddict")) == 2


# ---------------------------------------------------------------------------
# 1b. effective_dict_dir 三级优先级（规划员追补裁定：JSON 直读跨进程单源）
# ---------------------------------------------------------------------------

def _write_user_dirs_json(root: Path, payload) -> Path:
    """在数据根写 config/user_dirs.json（payload 为 dict 或坏字符串）。"""
    cfg = root / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    p = cfg / "user_dirs.json"
    if isinstance(payload, str):
        p.write_text(payload, encoding="utf-8")
    else:
        p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


def test_effective_dir_reads_user_dirs_json_key(_isolated_dict_state):
    """②JSON 键生效：无进程内覆盖时直读 user_dirs.json dict_dir 键。"""
    root = _isolated_dict_state
    target = root.parent / "json_dict_dir"
    target.mkdir()
    _write_user_dirs_json(root, {"registered_dirs": [], "templates_dir": None,
                                 "dict_dir": str(target)})
    assert _norm(dm.effective_dict_dir()) == _norm(target)
    assert _norm(dm.kind_dir("sudachi")) == _norm(target / "sudachi")
    # 状态返回体同步跟随
    st = dm.dict_status()
    assert _norm(st["effective_dir"]) == _norm(target)
    assert st["custom_dir"] is None     # 进程内未注入≠未生效（JSON 单源）


def test_effective_dir_corrupt_or_empty_json_skipped(_isolated_dict_state):
    """容错：损坏 JSON / 非 dict 形态 / 键空 / 键缺失 → 跳过回默认。"""
    root = _isolated_dict_state
    default = _norm(root / "dict")
    for payload in ("{not-json", "[1,2]", {},
                    {"dict_dir": None}, {"dict_dir": ""},
                    {"dict_dir": "   "}, {"templates_dir": "/x"}):
        _write_user_dirs_json(root, payload)
        assert _norm(dm.effective_dict_dir()) == default, f"payload={payload!r}"
    # 文件缺失同样回默认（夹具初始态即缺失，已由其余用例覆盖，此处显式锁）
    (root / "config" / "user_dirs.json").unlink()
    assert _norm(dm.effective_dict_dir()) == default


def test_effective_dir_priority_custom_over_json_over_default(
        _isolated_dict_state):
    """优先级：进程内覆盖 > JSON 键 > 数据根默认；逐级回退正确。"""
    root = _isolated_dict_state
    json_dir = root.parent / "prio_json"
    json_dir.mkdir()
    custom_dir = root.parent / "prio_custom"
    custom_dir.mkdir()
    _write_user_dirs_json(root, {"dict_dir": str(json_dir)})
    # 无覆盖 → JSON 生效
    assert _norm(dm.effective_dict_dir()) == _norm(json_dir)
    # 覆盖压过 JSON
    dm.set_custom_dir(str(custom_dir))
    assert _norm(dm.effective_dict_dir()) == _norm(custom_dir)
    # 清覆盖 → JSON 回归生效
    dm.set_custom_dir(None)
    assert _norm(dm.effective_dict_dir()) == _norm(json_dir)
    # 删 JSON → 默认
    (root / "config" / "user_dirs.json").unlink()
    assert _norm(dm.effective_dict_dir()) == _norm(root / "dict")


def test_user_dirs_json_mtime_cache(_isolated_dict_state):
    """mtime 缓存：stat 未变即复用旧解析值（不重读）；mtime 变化即重读。

    用 os.utime 回拨 mtime 确定性模拟"文件被改但 stat 未变"（缓存命中
    路径），再真实触碰（新 mtime）验证失效重读。
    """
    root = _isolated_dict_state
    a = root.parent / "cache_a"
    a.mkdir()
    p = _write_user_dirs_json(root, {"dict_dir": str(a)})
    assert _norm(dm.effective_dict_dir()) == _norm(a)   # 首读建缓存
    # 同内容重写 + mtime 回拨 → 缓存命中，仍返回旧值
    b = root.parent / "cache_b"
    b.mkdir()
    old_mtime = p.stat().st_mtime
    _write_user_dirs_json(root, {"dict_dir": str(b)})
    os.utime(p, (old_mtime, old_mtime))
    assert _norm(dm.effective_dict_dir()) == _norm(a), \
        "stat 未变必须复用缓存（不重读 JSON）"
    # mtime 真实前进 → 缓存失效重读
    p.touch()
    assert p.stat().st_mtime > old_mtime or p.stat().st_mtime != old_mtime
    assert _norm(dm.effective_dict_dir()) == _norm(b), \
        "mtime 变化必须重读 JSON"


def test_user_dirs_json_cache_key_includes_path(
        _isolated_dict_state, monkeypatch):
    """缓存 key 含完整路径：换数据根（env）后不串值（测试隔离保障）。"""
    root = _isolated_dict_state
    a = root.parent / "cache_path_a"
    a.mkdir()
    _write_user_dirs_json(root, {"dict_dir": str(a)})
    assert _norm(dm.effective_dict_dir()) == _norm(a)
    # 换新数据根（同名文件、不同根）
    root2 = root.parent / "dataroot2"
    root2.mkdir()
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(root2))
    b = root2.parent / "cache_path_b"
    b.mkdir()
    _write_user_dirs_json(root2, {"dict_dir": str(b)})
    assert _norm(dm.effective_dict_dir()) == _norm(b), \
        "换数据根后不得命中旧根缓存"


# ---------------------------------------------------------------------------
# 1c. 系统目录黑名单净化守卫（批1b 追补②，Mimosa finding:b50deb…）
# ---------------------------------------------------------------------------

def _enable_fake_system_roots(monkeypatch, base: Path) -> list[Path]:
    """把黑名单四根替换为 tmp 内模拟路径（不依赖真实 C 盘，跨平台稳）。"""
    roots = [base / "Windows", base / "Program Files",
             base / "Program Files (x86)", base / "ProgramData"]
    monkeypatch.setattr(dm, "_system_dir_roots",
                        lambda: [str(r) for r in roots])
    return roots


def test_ensure_safe_dict_dir_blocks_system_roots(monkeypatch, tmp_path):
    """黑名单四根逐根拦截：根本身与任意深度子路径均返回 None。"""
    roots = _enable_fake_system_roots(monkeypatch, tmp_path / "sysroot")
    for root in roots:
        assert dm._ensure_safe_dict_dir(str(root)) is None, f"根本身: {root}"
        assert dm._ensure_safe_dict_dir(str(root / "Sub" / "dicts")) is None, \
            f"子路径: {root}"
    # 大小写变体同样拦截（normcase + casefold 前缀判定）
    variant = tmp_path / "sysroot" / "WINDOWS" / "x"
    assert dm._ensure_safe_dict_dir(str(variant)) is None


def test_ensure_safe_dict_dir_allows_arbitrary_dirs(monkeypatch, tmp_path):
    """黑名单外任意目录放行（resolve 后返回）；前缀边界不误伤旁系目录。"""
    _enable_fake_system_roots(monkeypatch, tmp_path / "sysroot")
    ok = tmp_path / "anydisk" / "dicts"
    ok.mkdir(parents=True)
    got = dm._ensure_safe_dict_dir(str(ok))
    assert got is not None
    assert os.path.normcase(str(Path(got).resolve())) == \
        os.path.normcase(str(ok.resolve()))
    # 旁系不误伤：'Program Files2' 不在 'Program Files' 前缀内
    sibling = tmp_path / "sysroot" / "Program Files2"
    sibling.mkdir(parents=True)
    assert dm._ensure_safe_dict_dir(str(sibling)) is not None


def test_effective_dir_blacklist_falls_back(monkeypatch, _isolated_dict_state):
    """消费面接线：①②流命中黑名单均视为无效静默回退（防御纵深一致）。"""
    root = _isolated_dict_state
    roots = _enable_fake_system_roots(monkeypatch, root / "sysroot")
    good = root / "gooddict"
    good.mkdir()
    # ②JSON 指向黑名单 → 回数据根默认（与损坏 JSON 同待遇）
    _write_user_dirs_json(root, {"dict_dir": str(roots[0] / "dict")})
    assert _norm(dm.effective_dict_dir()) == _norm(root / "dict")
    # ①注入黑名单 + ②JSON 合法 → ①无效继续向下，②生效
    _write_user_dirs_json(root, {"dict_dir": str(good)})
    dm.set_custom_dir(str(roots[1]))
    assert _norm(dm.effective_dict_dir()) == _norm(good)
    # ①合法压过 ②（守卫只施加于被消费的流，优先级不变）
    dm.set_custom_dir(str(good))
    assert _norm(dm.effective_dict_dir()) == _norm(good)
    # ①②均黑名单 → 默认
    dm.set_custom_dir(str(roots[2]))
    _write_user_dirs_json(root, {"dict_dir": str(roots[3] / "dict")})
    assert _norm(dm.effective_dict_dir()) == _norm(root / "dict")
    # 守卫不改变 _user_dirs_json_dict_dir 读值本身（净化只发生在消费面）
    assert _norm(dm._user_dirs_json_dict_dir()) == \
        _norm(roots[3] / "dict")


def test_strip_extended_prefix_variants():
    """扩展前缀还原与 security.py 同口径（防 ``\\\\?\\`` 变体绕过黑名单）。"""
    assert dm._strip_extended_prefix(r"\\?\C:\x\d") == r"C:\x\d"
    assert dm._strip_extended_prefix(r"\\?\UNC\server\share") == \
        r"\\server\share"
    assert dm._strip_extended_prefix(r"C:\x\d") == r"C:\x\d"
    assert dm._strip_extended_prefix("") == ""


# ---------------------------------------------------------------------------
# 2. migrate_dicts（件2 迁移引擎）
# ---------------------------------------------------------------------------

def _make_old_dict(root: Path, files: dict[str, bytes]) -> Path:
    """构造旧词典目录：``<root>/<install>/<name>``。"""
    for rel, payload in files.items():
        p = root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(payload)
    return root


def _enable_custom(target: Path) -> None:
    dm.set_custom_dir(str(target))


def test_migrate_copies_verifies_and_keeps_source(_isolated_dict_state):
    """正常迁移：复制+哈希落位；源文件一律保留；进度终态 done。"""
    root = _isolated_dict_state
    old = _make_old_dict(root / "old", {
        "sudachi/system_core.dic": b"DICDATA",
        "english_rules/rules.json": b"{}"})
    new = root / "newdict"
    new.mkdir()
    _enable_custom(new)
    r = dm.migrate_dicts(str(old))
    assert sorted(Path(p).name for p in r["migrated"]) == \
        ["rules.json", "system_core.dic"]
    assert (new / "sudachi" / "system_core.dic").read_bytes() == b"DICDATA"
    assert (new / "english_rules" / "rules.json").read_bytes() == b"{}"
    # 源保留
    assert (old / "sudachi" / "system_core.dic").read_bytes() == b"DICDATA"
    assert (old / "english_rules" / "rules.json").read_bytes() == b"{}"
    # 进度终态（伪 kind 通道）
    snap = dm.download_progress(dm.MIGRATE_PROGRESS_KIND)
    assert snap["phase"] == "done"
    assert snap["downloaded"] == snap["total"] == \
        len(b"DICDATA") + len(b"{}")


def test_migrate_skips_same_size_and_recopies_size_mismatch(
        _isolated_dict_state):
    """可续传：同名同 size 跳过；size 不符重拷覆盖。"""
    root = _isolated_dict_state
    old = _make_old_dict(root / "old", {"sudachi/a.dic": b"AAAA"})
    new = root / "newdict"
    (new / "sudachi").mkdir(parents=True)
    (new / "sudachi" / "a.dic").write_bytes(b"AAAA")   # 同 size → skip
    _enable_custom(new)
    r1 = dm.migrate_dicts(str(old))
    assert r1["migrated"] == [] and len(r1["skipped"]) == 1
    # size 不符 → 重拷覆盖（内容以源为准）
    (old / "sudachi" / "a.dic").write_bytes(b"AAAA-BBBB")
    r2 = dm.migrate_dicts(str(old))
    assert len(r2["migrated"]) == 1
    assert (new / "sudachi" / "a.dic").read_bytes() == b"AAAA-BBBB"
    # 同 size 再跑仍跳过（可续传契约，跳过只看 size 不做哈希预检）
    r3 = dm.migrate_dicts(str(old))
    assert r3["migrated"] == []


def test_migrate_hash_corruption_aborts_no_partial_marker(
        _isolated_dict_state, monkeypatch):
    """哈希损坏：报错中止；目标无半截产物、无残留临时件；源保留；
    进度 phase=failed（不标记已迁移）。"""
    root = _isolated_dict_state
    old = _make_old_dict(root / "old", {
        "sudachi/bad.dic": b"BADDATA",
        "sudachi/good.dic": b"GOOD"})
    new = root / "newdict"
    new.mkdir()
    _enable_custom(new)

    def _corrupt_copy(src_file, dest, done_bytes, total_bytes,
                      file_index, file_count):
        # 模拟"复制通道写坏字节"：坏产物落临时名后校验必然失败，
        # 复刻引擎的"删临时→上抛"语义（重试在引擎内，桩直接失败中止）
        tmp = Path(str(dest) + ".migrating")
        tmp.write_bytes(b"CORRUPTED!!")
        try:
            if tmp.stat().st_size != src_file.stat().st_size or \
                    dm._sha256_file(str(tmp)) != \
                    dm._sha256_file(str(src_file)):
                raise ValueError(f"复制后校验不符: {src_file.name}")
            os.replace(str(tmp), str(dest))
        except (OSError, ValueError) as exc:
            tmp.unlink(missing_ok=True)
            raise RuntimeError(f"词典文件迁移失败（已重试一次）: "
                               f"{src_file} -> {dest}") from exc

    monkeypatch.setattr(dm, "_copy_verified", _corrupt_copy)
    with pytest.raises(RuntimeError, match="bad.dic"):
        dm.migrate_dicts(str(old))
    # 无半截产物/临时残件；任一失败即中止（bad 字母序在前，good 未及拷贝）
    assert not list(new.rglob("*.migrating"))
    assert not (new / "sudachi" / "bad.dic").exists()
    assert not (new / "sudachi" / "good.dic").exists()
    # 源全部保留
    assert (old / "sudachi" / "bad.dic").read_bytes() == b"BADDATA"
    assert (old / "sudachi" / "good.dic").read_bytes() == b"GOOD"
    # 进度 phase=failed（不标记已迁移）
    assert dm.download_progress(
        dm.MIGRATE_PROGRESS_KIND)["phase"] == "failed"


def test_migrate_retry_once_then_success(_isolated_dict_state, monkeypatch):
    """首次原子改名失败（瞬时写失败）→ 删临时重试一次后成功。"""
    root = _isolated_dict_state
    old = _make_old_dict(root / "old", {"sudachi/a.dic": b"DATA"})
    new = root / "newdict"
    new.mkdir()
    _enable_custom(new)
    calls = {"n": 0}
    real_replace = os.replace

    def _flaky_replace(src, dst):
        if str(src).endswith(".migrating") and calls["n"] == 0:
            calls["n"] += 1
            raise OSError("模拟瞬时写失败")
        return real_replace(src, dst)

    monkeypatch.setattr(os, "replace", _flaky_replace)
    r = dm.migrate_dicts(str(old))
    assert calls["n"] == 1, "首次失败后必须重试一次"
    assert len(r["migrated"]) == 1
    assert (new / "sudachi" / "a.dic").read_bytes() == b"DATA"
    assert not list(new.rglob("*.migrating"))


def test_migrate_rejects_same_dir_and_missing_source(_isolated_dict_state):
    """源=生效目录（normcase）拒绝；源目录不存在拒绝。"""
    root = _isolated_dict_state
    new = root / "newdict"
    new.mkdir()
    _enable_custom(new)
    with pytest.raises(ValueError, match="相同"):
        dm.migrate_dicts(str(new))
    with pytest.raises(ValueError, match="不存在"):
        dm.migrate_dicts(str(root / "nope"))


def test_migrate_skips_temp_leftovers(_isolated_dict_state):
    """临时残件（.part/.downloading/.extracting/.migrating）不迁移。"""
    root = _isolated_dict_state
    old = _make_old_dict(root / "old", {
        "sudachi/a.dic": b"A",
        "sudachi/a.dic.part": b"p",
        "sudachi/b.dic.downloading": b"d"})
    new = root / "newdict"
    new.mkdir()
    _enable_custom(new)
    r = dm.migrate_dicts(str(old))
    assert [Path(p).name for p in r["migrated"]] == ["a.dic"]
    assert not list(new.rglob("*.part"))


# ---------------------------------------------------------------------------
# 3. API 面（webview-free 构造实例，仿 test_gui_api.py；缺席软跳过）
# ---------------------------------------------------------------------------

def _api_cls():
    pytest.importorskip("webview", reason="pywebview 未安装时跳过 API 面用例",
                        exc_type=ImportError)
    from subtransjav.webview_gui.api import TranslateAPI
    return TranslateAPI


@pytest.fixture()
def gui_api():
    return object.__new__(_api_cls())


def _fake_window(monkeypatch, picked: Path | None) -> None:
    """打桩原生目录对话框（picked=None 模拟取消）。"""
    import subtransjav.webview_gui.api as api_mod

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(picked)] if picked else []

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])


def test_api_migrate_rejects_without_custom_dir(gui_api, _isolated_dict_state):
    """未设置自定义目录：migrate 拒绝（无可迁移目标）。"""
    r = gui_api.refine_dict_migrate(str(_isolated_dict_state / "old"))
    assert r["success"] is False
    assert "尚未设置" in r["error"]


def test_api_migrate_rejects_missing_source(gui_api, _isolated_dict_state):
    """已设置目录但缺 source_dir：拒绝并带文案。"""
    dm.set_custom_dir(str(_isolated_dict_state / "newdict"))
    r = gui_api.refine_dict_migrate("")
    assert r["success"] is False
    assert "旧词典目录" in r["error"]


def test_api_migrate_success_contract(gui_api, _isolated_dict_state):
    """迁移成功返回契约：migrated/skipped/total_bytes。"""
    root = _isolated_dict_state
    old = _make_old_dict(root / "old", {"sudachi/a.dic": b"OK"})
    new = root / "newdict"
    new.mkdir()
    dm.set_custom_dir(str(new))
    r = gui_api.refine_dict_migrate(str(old))
    assert r["success"] is True
    assert len(r["migrated"]) == 1
    assert _norm(r["migrated"][0]) == _norm(new / "sudachi" / "a.dic")
    assert r["skipped"] == [] and r["total_bytes"] == 2


def test_api_clear_dict_dir_contract(gui_api, _isolated_dict_state):
    """恢复默认契约：had_custom/effective_dir/old_files；持久值清除。"""
    root = _isolated_dict_state
    from subtransjav.webview_gui import user_dirs as ud
    custom = root / "custom"
    custom.mkdir()
    ud.set_dict_dir(str(custom))
    dm.set_custom_dir(str(custom))
    r = gui_api.refine_clear_dict_dir()
    assert r["success"] is True
    assert r["had_custom"] is True
    assert _norm(r["effective_dir"]) == _norm(root / "dict")
    assert ud.get_dict_dir() is None
    assert dm.get_custom_dir() is None


def test_api_pick_dict_dir_flow(gui_api, monkeypatch, _isolated_dict_state):
    """pick 收口 e2e：对话框 → 持久登记 + dict_dir 持久化 + 进程注入 +
    needs_migration 标记（旧目录有词典文件时）；取消原样透传不注入。"""
    from subtransjav.webview_gui import user_dirs as ud
    root = _isolated_dict_state
    (root / "dict" / "sudachi").mkdir(parents=True)
    (root / "dict" / "sudachi" / "old.dic").write_bytes(b"OLD")
    picked = root / "picked"
    picked.mkdir()

    _fake_window(monkeypatch, picked)
    r = gui_api.refine_pick_dict_dir()
    assert r["success"] is True
    assert r["needs_migration"] is True
    assert r["old_files"] == 1
    assert _norm(r["old_dir"]) == _norm(root / "dict")
    assert _norm(r["effective_dir"]) == _norm(picked)
    assert dm.get_custom_dir() is not None
    assert ud.get_dict_dir() == ud.normalize_key(str(picked))
    assert ud.normalize_key(str(picked)) in ud.load()["registered_dirs"]
    # 取消（对话框返回空）：原样透传失败结果，不注入不持久化
    dm.set_custom_dir(None)
    _fake_window(monkeypatch, None)
    r2 = gui_api.refine_pick_dict_dir()
    assert r2.get("success") is False
    assert dm.get_custom_dir() is None


def test_api_pick_folder_purpose_dict_persists(
        gui_api, monkeypatch, _isolated_dict_state):
    """refine_pick_folder('dict')：持久写 user_dirs.dict_dir（不含注入）。"""
    from subtransjav.webview_gui import user_dirs as ud
    picked = _isolated_dict_state / "picked2"
    picked.mkdir()
    _fake_window(monkeypatch, picked)
    r = gui_api.refine_pick_folder("dict")
    assert r["success"] is True
    assert ud.get_dict_dir() == ud.normalize_key(str(picked))


def test_api_init_loads_persisted_dict_dir(
        monkeypatch, _isolated_dict_state):
    """启动注入（_load_dict_dir_override）：持久值 → 进程内生效。

    CI 热修：本用例直接 import webview_gui.api 但不经 gui_api 夹具，
    须自带 importorskip 闸（与 _api_cls 口径对齐），否则 Ubuntu 腿
    （不装 pywebview）collection 后 ModuleNotFoundError 致红。
    """
    pytest.importorskip("webview", reason="pywebview 未安装时跳过 API 面用例",
                        exc_type=ImportError)
    from subtransjav.webview_gui import user_dirs as ud
    root = _isolated_dict_state
    custom = root / "startup"
    custom.mkdir()
    ud.set_dict_dir(str(custom))
    dm.set_custom_dir(None)
    import subtransjav.webview_gui.api as api_mod
    api_mod._load_dict_dir_override()
    assert _norm(dm.effective_dict_dir()) == _norm(custom)


# ---------------------------------------------------------------------------
# 4. 首启数据目录引导（件4 哨兵）
# ---------------------------------------------------------------------------

def test_data_guide_sentinel_path_source_form_is_repo_root():
    """源码形态：哨兵与 .data-root 指针同位（仓库根），不随数据根。"""
    p = paths.data_guide_sentinel_path()
    assert p == Path(paths.__file__).resolve().parents[1] / \
        paths.GUIDE_SENTINEL_FILENAME
    assert p.name == ".data-guide-done"


def test_data_guide_sentinel_path_frozen_is_exe_dir(monkeypatch, tmp_path):
    """frozen 形态：哨兵落 exe 同目录（与数据根解耦，防改根后再弹）。"""
    exe = tmp_path / "app" / "SubTrans.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", str(exe))
    assert paths.data_guide_sentinel_path() == exe.parent / ".data-guide-done"


def test_should_show_data_guide_frozen_gate(
        gui_api, monkeypatch, tmp_path):
    """frozen 门：源码形态恒否（reason=not-frozen）；frozen 首真后假。

    frozen 分支的哨兵位置经 sys.executable 指向 tmp（绝不写真实目录）。
    """
    # 源码形态：恒否（不读哨兵、不落地）
    r = gui_api.should_show_data_guide()
    assert r["success"] is True and r["show"] is False
    assert r["reason"] == "not-frozen"
    # frozen + 无哨兵 → show=True
    exe = tmp_path / "app" / "SubTrans.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    monkeypatch.setattr(sys, "executable", str(exe))
    sentinel = exe.parent / ".data-guide-done"
    r2 = gui_api.should_show_data_guide()
    assert r2["show"] is True
    assert r2["data_root"]              # 返回当前数据根供弹窗展示
    # 标记后 → show=False（哨兵真实落盘于 exe 同目录）
    w = gui_api.mark_data_guide_done()
    assert w["success"] is True and w["written"] is True
    assert sentinel.is_file()
    assert gui_api.should_show_data_guide()["show"] is False


def test_mark_data_guide_done_source_form_noop(gui_api):
    """源码形态 mark：no-op（哨兵不落地防脏工作树，与 template_seed 同口径）。"""
    r = gui_api.mark_data_guide_done()
    assert r["success"] is True and r["written"] is False
    assert r["reason"] == "not-frozen"
    assert not paths.data_guide_sentinel_path().exists()


def test_should_show_survives_sentinel_read_error(gui_api, monkeypatch):
    """哨兵读取异常折算为 success=False（全容错，不阻塞前端流程）。"""
    def _boom():
        raise OSError("boom")
    monkeypatch.setattr(paths, "is_frozen", lambda: True)   # 越过 frozen 短路
    monkeypatch.setattr(paths, "data_guide_sentinel_path", _boom)
    r = gui_api.should_show_data_guide()
    assert r["success"] is False and "error" in r
