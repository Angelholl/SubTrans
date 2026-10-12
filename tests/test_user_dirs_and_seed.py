"""批1a（D2026-1002-12）测试：用户目录持久登记 + 白名单改革 + 首启 seed。

覆盖四块（不依赖真实 E:\\ 等外部盘符，全部 monkeypatch 模拟）：
1. user_dirs：持久化读写/去重/损坏容错/templates_dir 语义；
2. security._resolve_safe_path：动态数据根现读 / extra_roots 生效 /
   锚点逃逸仍拦 / 纯函数边界（不 import 持久化模块）；
3. template_seed：frozen 门 / 幂等（二次零拷贝）/ 不覆盖已存在文件 /
   版本哨兵升级补新文件；
4. 数据根隔离：一律经 ``SUBTRANSJAV_DATA_ROOT`` 环境变量把数据根指向
   tmp，绝不写仓库真实 ``config/user_dirs.json``。
"""
import json
import os
import re
from pathlib import Path

import pytest

from subtransjav import paths
from subtransjav.refine import template_seed
from subtransjav.webview_gui import security, user_dirs


@pytest.fixture()
def fake_data_root(tmp_path, monkeypatch):
    """把数据根指向 tmp（env 通道现读），隔离真实仓库 config。"""
    root = tmp_path / "dataroot"
    root.mkdir()
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(root))
    return root


@pytest.fixture()
def isolated_roots(tmp_path, monkeypatch):
    """白名单三根全部指向 tmp 下假目录，隔离真实 home/数据根/仓库根。

    注意：basetemp 若在仓库内，tmp_path 天然落入真实 REPO_ROOT 白名单，
    会破坏"白名单外拒绝"前提——本夹具同屏换掉三根，任何 basetemp 位置
    下语义一致。
    """
    fake_home = tmp_path / "home"
    fake_repo = tmp_path / "repo"
    fake_data = tmp_path / "dataroot"
    for d in (fake_home, fake_repo, fake_data):
        d.mkdir()
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: fake_home))
    monkeypatch.setattr(security, "REPO_ROOT", fake_repo)
    monkeypatch.setattr(paths, "data_root", lambda: fake_data)
    return {"home": fake_home, "repo": fake_repo, "data_root": fake_data}


# ---------------------------------------------------------------------------
# 1. user_dirs 持久登记
# ---------------------------------------------------------------------------

def test_user_dirs_store_path_follows_env_data_root(fake_data_root):
    """数据根现读：store_path 随 env 数据根走（非导入期快照）。"""
    assert user_dirs.store_path() == os.path.join(
        str(fake_data_root), "config", "user_dirs.json")


def test_user_dirs_load_missing_returns_defaults(fake_data_root):
    data = user_dirs.load()
    assert data["registered_dirs"] == []
    assert data["templates_dir"] is None
    assert data["dict_dir"] is None, "批1b 预留键必须存在"


def test_user_dirs_register_dir_persists_and_dedupes(fake_data_root):
    d = fake_data_root / "cards"
    d.mkdir()
    key = user_dirs.register_dir(str(d))
    assert key == user_dirs.normalize_key(str(d))
    # 去重：重复登记不产生第二行
    user_dirs.register_dir(str(d))
    data = user_dirs.load()
    assert data["registered_dirs"] == [key]
    on_disk = json.loads(
        (fake_data_root / "config" / "user_dirs.json").read_text("utf-8"))
    assert on_disk["registered_dirs"] == [key], "必须真实落盘"


def test_user_dirs_templates_dir_roundtrip_and_clear(fake_data_root):
    d = fake_data_root / "tpl"
    d.mkdir()
    assert user_dirs.get_templates_dir() is None
    user_dirs.set_templates_dir(str(d))
    assert user_dirs.get_templates_dir() == user_dirs.normalize_key(str(d))
    user_dirs.set_templates_dir(None)
    assert user_dirs.get_templates_dir() is None


def test_user_dirs_corrupted_file_falls_back_to_defaults(fake_data_root):
    p = fake_data_root / "config" / "user_dirs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("{not-json", encoding="utf-8")
    data = user_dirs.load()
    assert data["registered_dirs"] == []
    # 顶层非 dict 同样容错
    p.write_text("[1,2]", encoding="utf-8")
    assert user_dirs.load()["templates_dir"] is None


def test_user_dirs_keeps_unknown_keys_forward_compatible(fake_data_root):
    p = fake_data_root / "config" / "user_dirs.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({
        "registered_dirs": [], "templates_dir": None, "dict_dir": None,
        "future_key": {"a": 1}}), encoding="utf-8")
    data = user_dirs.load()
    assert data["future_key"] == {"a": 1}, "未知键必须原样保留（前向兼容）"
    user_dirs.register_dir(str(fake_data_root / "x"))
    on_disk = json.loads(p.read_text("utf-8"))
    assert on_disk["future_key"] == {"a": 1}, "回写不得丢失未知键"


# ---------------------------------------------------------------------------
# 2. security._resolve_safe_path 白名单改革
# ---------------------------------------------------------------------------

def test_resolve_safe_path_dynamic_data_root(isolated_roots):
    """动态根：monkeypatch paths.data_root 后，新根下路径立即放行
    （无需重启/重导入——导入期快照问题已消灭）。"""
    fake_root = isolated_roots["data_root"]
    (fake_root / "sub").mkdir()
    target = fake_root / "sub" / "x.csv"
    assert security._resolve_safe_path(str(target)) == target.resolve()


def test_resolve_safe_path_rejects_outside_all_roots():
    """白名单外（假盘符 Q:，不依赖真实磁盘）拒绝；POSIX 走盘符分支同样拒绝。"""
    with pytest.raises(ValueError):
        security._resolve_safe_path("Q:/somewhere/out/a.txt")


def test_resolve_safe_path_extra_roots_effective(tmp_path, isolated_roots):
    """extra_roots 生效：持久登记目录在三根之外时，仅凭 extra_roots 放行。"""
    reg = tmp_path / "registered"
    reg.mkdir()
    target = reg / "a.txt"
    # 未传 extra_roots：目录不在 home/数据根/仓库根任一根下 → 拒绝
    with pytest.raises(ValueError):
        security._resolve_safe_path(str(target))
    # 传入持久登记根 → 放行
    got = security._resolve_safe_path(str(target), extra_roots=[str(reg)])
    assert got == target.resolve()


def test_resolve_safe_path_extra_roots_subpath_ok_and_sibling_rejected(
        tmp_path, isolated_roots):
    """extra_roots 锚定目录下子路径放行；旁系目录仍拒绝（前缀边界）。"""
    reg = tmp_path / "reg"
    (reg / "sub").mkdir(parents=True)
    sibling = tmp_path / "regx"
    sibling.mkdir()
    assert security._resolve_safe_path(str(reg / "sub" / "f.txt"),
                                       extra_roots=[str(reg)])
    with pytest.raises(ValueError):
        security._resolve_safe_path(str(sibling / "f.txt"),
                                    extra_roots=[str(reg)])


def test_resolve_safe_path_anchored_escape_still_blocked():
    """锚点逃逸判定保留：仓库根字面锚 + .. 折叠逃出 → 拒绝。"""
    raw = str(Path(security.REPO_ROOT) / ".." / "escape.txt")
    with pytest.raises(ValueError):
        security._resolve_safe_path(raw)


def test_security_module_stays_pure():
    """security.py 保持纯函数：不得 import user_dirs（由 api.py 装载传入）。"""
    src = Path(security.__file__).read_text(encoding="utf-8")
    assert not re.search(r"^\s*(?:from|import)\s+\S*user_dirs", src, re.M), \
        "security.py 不得 import user_dirs（纯函数边界）"


# ---------------------------------------------------------------------------
# 3. template_seed 首启 seed
# ---------------------------------------------------------------------------

def test_seed_noop_when_not_frozen(fake_data_root):
    """frozen 门：源码形态 no-op（防脏工作树），且不建任何目录。"""
    r = template_seed.seed_default_templates()
    assert r == {"seeded": False, "reason": "not-frozen"}
    assert not (fake_data_root / "config").exists()


def _make_fake_pkg(tmp_path: Path, files: dict[str, str]) -> Path:
    pkg = tmp_path / "pkg_templates"
    pkg.mkdir(exist_ok=True)
    for name, text in files.items():
        (pkg / name).write_text(text, encoding="utf-8")
    return pkg


def _enable_frozen(monkeypatch):
    monkeypatch.setattr(paths, "is_frozen", lambda: True)


def test_seed_copies_missing_only_and_writes_sentinel(
        tmp_path, monkeypatch, fake_data_root):
    """frozen 首跑：包内 .txt 补拷到数据根 config/templates + 版本哨兵落盘。"""
    _enable_frozen(monkeypatch)
    pkg = _make_fake_pkg(tmp_path, {"角色-净语翻译.txt": "A卡",
                                    "角色-审校抛光.txt": "B卡",
                                    "README-模板说明.txt": "说明",
                                    "ignore.yaml": "x"})
    monkeypatch.setattr(template_seed, "_pkg_templates_dir", lambda: pkg)
    r = template_seed.seed_default_templates()
    assert r["seeded"] is True
    assert sorted(r["copied"]) == ["README-模板说明.txt", "角色-净语翻译.txt",
                                   "角色-审校抛光.txt"], "非 .txt 不拷"
    tpl_dir = fake_data_root / "config" / "templates"
    assert (tpl_dir / "角色-净语翻译.txt").read_text("utf-8") == "A卡"
    sentinel = tpl_dir / f".seed-{template_seed._current_version()}"
    assert sentinel.is_file(), "必须写当前版本哨兵"


def test_seed_idempotent_second_run_zero_copy(
        tmp_path, monkeypatch, fake_data_root):
    """幂等：哨兵存在且版本相同 → 整个扫描跳过（零拷贝）。"""
    _enable_frozen(monkeypatch)
    pkg = _make_fake_pkg(tmp_path, {"角色-净语翻译.txt": "A卡"})
    monkeypatch.setattr(template_seed, "_pkg_templates_dir", lambda: pkg)
    assert template_seed.seed_default_templates()["seeded"] is True
    # 用户改动卡内容后，二次跑也不得触碰
    tpl_dir = fake_data_root / "config" / "templates"
    (tpl_dir / "角色-净语翻译.txt").write_text("用户改卡", encoding="utf-8")
    r2 = template_seed.seed_default_templates()
    assert r2 == {"seeded": False, "reason": "already-seeded"}
    assert (tpl_dir / "角色-净语翻译.txt").read_text("utf-8") == "用户改卡"


def test_seed_never_overwrites_existing_card(
        tmp_path, monkeypatch, fake_data_root):
    """不覆盖：目标已存在的卡（用户已改）原样保留，缺失文件照常补拷。"""
    _enable_frozen(monkeypatch)
    pkg = _make_fake_pkg(tmp_path, {"角色-净语翻译.txt": "新A卡",
                                    "角色-审校抛光.txt": "B卡"})
    monkeypatch.setattr(template_seed, "_pkg_templates_dir", lambda: pkg)
    tpl_dir = fake_data_root / "config" / "templates"
    tpl_dir.mkdir(parents=True)
    (tpl_dir / "角色-净语翻译.txt").write_text("用户已改", encoding="utf-8")
    r = template_seed.seed_default_templates()
    assert r["seeded"] is True
    assert r["copied"] == ["角色-审校抛光.txt"], "已存在文件绝不覆盖"
    assert (tpl_dir / "角色-净语翻译.txt").read_text("utf-8") == "用户已改"


def test_seed_version_upgrade_copies_new_files_only(
        tmp_path, monkeypatch, fake_data_root):
    """版本哨兵升级：包升级带新卡（哨兵版本≠当前版本）→ 仅补拷新文件名，
    已存在文件（含用户改动）不覆盖，旧哨兵清理。"""
    _enable_frozen(monkeypatch)
    pkg = _make_fake_pkg(tmp_path, {"a.txt": "A1", "b.txt": "B1"})
    monkeypatch.setattr(template_seed, "_pkg_templates_dir", lambda: pkg)
    monkeypatch.setattr(template_seed, "_current_version",
                        lambda: "9.9.0")
    assert template_seed.seed_default_templates()["seeded"] is True
    tpl_dir = fake_data_root / "config" / "templates"
    (tpl_dir / "a.txt").write_text("用户改A", encoding="utf-8")
    # 包升级：新卡 c.txt；版本号前进
    (pkg / "c.txt").write_text("C1", encoding="utf-8")
    monkeypatch.setattr(template_seed, "_current_version",
                        lambda: "9.9.1")
    r = template_seed.seed_default_templates()
    assert r["seeded"] is True and r["copied"] == ["c.txt"]
    assert (tpl_dir / "a.txt").read_text("utf-8") == "用户改A"
    assert (tpl_dir / "c.txt").read_text("utf-8") == "C1"
    assert (tpl_dir / ".seed-9.9.1").is_file()
    assert not (tpl_dir / ".seed-9.9.0").exists(), "旧版本哨兵必须清理"
