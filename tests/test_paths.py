"""subtrans.paths 数据路径单一来源测试（打包地基批）"""
import datetime
import os
import re
import sys
from pathlib import Path

import pytest

from subtrans import paths

REPO_ROOT = Path(paths.__file__).resolve().parents[1]


# ---------------------------------------------------------------------------
# is_frozen
# ---------------------------------------------------------------------------
def test_is_frozen_false_by_default():
    # 测试进程恒为源码形态（sys 无 frozen 属性或为 False）
    assert paths.is_frozen() is (getattr(sys, "frozen", False))


def test_is_frozen_true_when_patched(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert paths.is_frozen() is True


# ---------------------------------------------------------------------------
# data_root 三级优先级
# ---------------------------------------------------------------------------
def test_data_root_env_priority(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANS_DATA_ROOT", str(tmp_path))
    assert paths.data_root() == Path(tmp_path)
    assert paths.data_root_source() == "env"


def _patch_frozen_install(monkeypatch, tmp_path, install_name="install"):
    """frozen 形态夹具：把「安装目录」钉到 tmp/<install_name>。

    落点 A（D2026-1103-05 项②）下新默认＝安装目录旁路，即
    tmp/<install_name>-data。
    """
    install = tmp_path / install_name
    install.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(install / "SubTrans.exe"))
    monkeypatch.delenv("SUBTRANS_DATA_ROOT", raising=False)
    return install


def _write_anchor(root: Path) -> Path:
    """在 root 内落一个最小数据锚点（config/user_settings.json）。"""
    cfg = root / "config"
    cfg.mkdir(parents=True, exist_ok=True)
    (cfg / "user_settings.json").write_text('{"v2_ctx_local": 16384}',
                                            encoding="utf-8")
    return root


def test_data_root_env_blank_ignored(monkeypatch, tmp_path):
    _patch_frozen_install(monkeypatch, tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("SUBTRANS_DATA_ROOT", "   ")
    assert paths.data_root() == tmp_path / "install-data"


def test_data_root_frozen_default_is_install_dir_sibling(monkeypatch, tmp_path):
    """frozen 无 env 无 pointer → 落点 A 安装目录旁路，不再 %LOCALAPPDATA%
    （D2026-1103-05 项②，显式取代 D2026-1002-12 点 4）。"""
    _patch_frozen_install(monkeypatch, tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    assert paths.data_root() == tmp_path / "install-data"
    assert paths.data_root_source() == "frozen-default"


def test_data_root_frozen_adopts_legacy_default(monkeypatch, tmp_path):
    """护栏 6 收养：新默认无锚点＋旧 %LOCALAPPDATA%\\SubTrans 有锚点 →
    仍用旧根，来源标签独立，不静默迁移。"""
    _patch_frozen_install(monkeypatch, tmp_path)
    lac = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(lac))
    _write_anchor(lac / "SubTrans")
    assert paths.data_root() == lac / "SubTrans"
    assert paths.data_root_source() == "frozen-legacy-default"


def test_data_root_frozen_prefers_new_root_when_it_has_anchors(monkeypatch, tmp_path):
    """新默认已有数据 → 即便旧默认位也有数据，仍用新默认（不回头收养）。"""
    _patch_frozen_install(monkeypatch, tmp_path)
    lac = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(lac))
    _write_anchor(tmp_path / "install-data")
    _write_anchor(lac / "SubTrans")
    assert paths.data_root() == tmp_path / "install-data"
    assert paths.data_root_source() == "frozen-default"


def test_data_root_frozen_no_anchors_anywhere_uses_new_default(monkeypatch, tmp_path):
    """全新安装（两根皆空/不存在）→ 用新默认，不抛异常。"""
    _patch_frozen_install(monkeypatch, tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    assert paths.data_root() == tmp_path / "install-data"
    assert paths.data_root_source() == "frozen-default"


def test_data_root_frozen_localappdata_missing_no_home_fallback(monkeypatch, tmp_path):
    """LOCALAPPDATA 缺失不再决定数据根（新默认由安装目录推导），不抛异常。"""
    _patch_frozen_install(monkeypatch, tmp_path)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    assert paths.data_root() == tmp_path / "install-data"
    # 旧默认位回退家目录（legacy_default_data_root 语义），供收养判定使用
    monkeypatch.setattr(paths.Path, "home", classmethod(lambda cls: tmp_path / "home"))
    _write_anchor(tmp_path / "home" / "SubTrans")
    assert paths.legacy_default_data_root() == tmp_path / "home" / "SubTrans"
    assert paths.data_root() == tmp_path / "home" / "SubTrans"
    assert paths.data_root_source() == "frozen-legacy-default"


def test_data_root_source_form_is_repo_root(monkeypatch):
    monkeypatch.delenv("SUBTRANS_DATA_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert paths.data_root() == REPO_ROOT
    assert paths.data_root_source() == "legacy"


# ---------------------------------------------------------------------------
# 落点 A 推导规格对照表（与 packaging/setup.iss _DefaultDataRootFor 同规格）
# ---------------------------------------------------------------------------
@pytest.mark.skipif(os.name != "nt",
                    reason="frozen 数据根旁路命名属 Windows 安装面语义（Path 语义随 OS，非 nt 形态对照无意义）")
@pytest.mark.parametrize("install_dir,expected", [
    pytest.param(r"D:\SubTrans", r"D:\SubTrans-data"),
    pytest.param(r"C:\Program Files\SubTrans", r"C:\Program Files\SubTrans-data"),
    pytest.param("D:\\SubTrans\\", r"D:\SubTrans-data"),        # 尾斜杠
    pytest.param(r"D:\SubTrans-data", r"D:\SubTrans-data-data"),  # 名字已带 -data
    pytest.param(r"D:\a\b\c\d\e\f\g\h\i\j\k\l\m\n\o\p\q\r\s\t\u\v\w\x\y\z\SubTrans",
                 r"D:\a\b\c\d\e\f\g\h\i\j\k\l\m\n\o\p\q\r\s\t\u\v\w\x\y\z\SubTrans-data"),  # 长路径
    pytest.param(r"\\server\share\SubTrans", r"\\server\share\SubTrans-data",
                 marks=pytest.mark.skipif(sys.version_info < (3, 12),
                                          reason="pathlib UNC .parent 语义 3.12 才对齐（win<3.12 腿 skip）")),
    pytest.param("D:\\", r"D:\SubTrans-data"),                  # 盘根
    pytest.param(r"D:", r"D:\SubTrans-data"),                   # 盘根无斜杠
    pytest.param(r"\\server", r"\\server\SubTrans-data",
                 marks=pytest.mark.skipif(sys.version_info < (3, 12),
                                          reason="pathlib UNC 语义版本差（win<3.12 腿 skip）")),
    pytest.param(r"\\server\share", r"\\server\share\SubTrans-data",
                 marks=pytest.mark.skipif(sys.version_info < (3, 12),
                                          reason="pathlib UNC 语义版本差（win<3.12 腿 skip）")),
    pytest.param("\\", r"\SubTrans-data"),                      # 单根（无盘符无 UNC）
    pytest.param("D:/SubTrans", r"D:\SubTrans-data"),            # 正斜杠形态
])
def test_default_data_root_for_forms(install_dir, expected):
    """形态对照表钉死推导规格：普通/Program Files/尾斜杠/-data 结尾/长路径/
    UNC 三形态/盘根/单根/正斜杠（iss 侧同形态钉见 test_installer_lifecycle）。"""
    assert paths.default_data_root_for(Path(install_dir)) == Path(expected)


@pytest.mark.parametrize("install_dir", [
    r"D:\SubTrans", r"D:\SubTrans-data", r"D:\SubTrans-DATA", "D:\\",
    r"C:\Program Files\SubTrans", r"\\server\share\SubTrans",
])
def test_default_data_root_never_equals_install_dir(install_dir):
    """硬不变量：推导结果恒不等于安装目录本身（数据根落安装目录内＝10-30 事故前提）。"""
    got = paths.default_data_root_for(Path(install_dir))
    assert paths.normalize_path_case(str(got)) != paths.normalize_path_case(
        str(Path(install_dir)))


def test_paths_anchors_align_with_iss_gate():
    """paths.DATA_ANCHORS 与 setup.iss HasAnyAnchor 十锚逐条对齐（护栏 7 同口径）。"""
    iss = (REPO_ROOT / "packaging" / "setup.iss").read_text(encoding="utf-8")
    m = re.search(r"function HasAnyAnchor\(const root: String\): Boolean;\n"
                  r"begin(.*?)end;", iss, re.S)
    assert m, "setup.iss 未找到 HasAnyAnchor"
    iss_anchors = {
        mm.group(1).lstrip("\\").replace("\\", "/")
        for mm in re.finditer(r"FileOrDirExists\(root \+ '([^']+)'", m.group(1))
    }
    assert iss_anchors == set(paths.DATA_ANCHORS), (
        f"iss 锚点与 paths.DATA_ANCHORS 漂移: {iss_anchors ^ set(paths.DATA_ANCHORS)}")


# ---------------------------------------------------------------------------
# data_root_source 标签面（env/pointer/frozen-default/frozen-legacy-default/legacy）
# ---------------------------------------------------------------------------
def test_data_root_source_five_values(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANS_DATA_ROOT", str(tmp_path))
    assert paths.data_root_source() == "env"
    monkeypatch.delenv("SUBTRANS_DATA_ROOT")
    _patch_frozen_install(monkeypatch, tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    assert paths.data_root_source() == "frozen-default"
    _write_anchor(tmp_path / "localappdata" / "SubTrans")
    assert paths.data_root_source() == "frozen-legacy-default"
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert paths.data_root_source() == "legacy"


def test_cli_where_source_map_covers_all_labels():
    """护栏 10：cli --where 的中文映射须覆盖 data_root_source 全部标签。"""
    import inspect

    from subtrans.refine import cli as cli_mod
    src = inspect.getsource(cli_mod._print_where)
    for label in ("env", "pointer", "frozen-default",
                  "frozen-legacy-default", "legacy"):
        assert f'"{label}"' in src, f"--where source_map 缺标签 {label}"


# ---------------------------------------------------------------------------
# data_subdir
# ---------------------------------------------------------------------------
def test_data_subdir_source_form_relative_structure(monkeypatch):
    monkeypatch.delenv("SUBTRANS_DATA_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert paths.data_subdir("Temp", "translation_memory").endswith(
        str(Path("Temp") / "translation_memory"))
    assert paths.data_subdir("config").endswith("config")
    assert paths.data_subdir("Errors").endswith("Errors")


# ---------------------------------------------------------------------------
# 迁移状态存根
# ---------------------------------------------------------------------------
def test_migration_state_not_migrated_by_default(monkeypatch, tmp_path):
    _patch_frozen_install(monkeypatch, tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    assert paths.migration_state() == "not-migrated"


def test_migration_state_migrated_with_sentinel(monkeypatch, tmp_path):
    _patch_frozen_install(monkeypatch, tmp_path)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    new_root = tmp_path / "install-data"
    new_root.mkdir()
    (new_root / paths.MIGRATION_SENTINEL).write_text("", encoding="utf-8")
    assert paths.migration_state() == "migrated"


# ---------------------------------------------------------------------------
# 旧位保留 EOL 常量钉（D2026-0930-03 ⑤：定版值，防误改与文档漂移）
# ---------------------------------------------------------------------------
def test_legacy_retention_eol_pinned():
    assert paths.LEGACY_RETENTION_EOL == "2027-06-30"
    d = datetime.date.fromisoformat(paths.LEGACY_RETENTION_EOL)
    assert (d.year, d.month, d.day) == (2027, 6, 30)
    # 迁移模块文档与常量口径同步（防文档漂移）
    from subtrans import data_migration as dm
    assert "LEGACY_RETENTION_EOL" in (dm.__doc__ or "")


# ---------------------------------------------------------------------------
# 锚点路径钉（D2026-0924-04：源码形态逐字节一致，回归基线只增不减）
# ---------------------------------------------------------------------------
def test_pin_config_dir_is_repo_config():
    from subtrans.refine import config as rc
    assert str(REPO_ROOT / "config") == rc.CONFIG_DIR


def test_pin_temp_dir_is_repo_temp():
    from subtrans.refine import config as rc
    assert str(REPO_ROOT / "Temp") == rc.TEMP_DIR


def test_pin_tm_default_dir_is_repo_temp_translation_memory():
    from subtrans.refine import tm
    assert str(REPO_ROOT / "Temp" / "translation_memory") == tm._DEFAULT_TM_DIR


def test_pin_glossary_conflict_watch_path():
    from subtrans.refine import glossary_conflict as gc
    assert gc.default_watch_path() == str(
        REPO_ROOT / "Temp" / "translation_memory" / "glossary_conflict_watch.json")


def test_pin_secrets_config_store_is_repo_config():
    from subtrans.refine import secrets as sec
    assert str(REPO_ROOT / "config" / "api_keys.bin") == sec._CONFIG_STORE


def test_pin_learned_glossary_path_is_repo_config():
    from subtrans.refine import pipeline_support as ps
    assert ps.learned_glossary_path() == str(
        REPO_ROOT / "config" / "glossary_learned.csv")


# ---------------------------------------------------------------------------
# pointer 层（.data-root，owner 反馈②：数据保存目录用户自选）
# ---------------------------------------------------------------------------
@pytest.fixture()
def pointer_tmp(monkeypatch, tmp_path):
    """把 pointer 文件指到 tmp，隔离仓库根真实 .data-root。"""
    p = tmp_path / ".data-root"
    monkeypatch.setattr(paths, "_data_root_pointer_path", lambda: p)
    monkeypatch.delenv("SUBTRANS_DATA_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    return p


def test_pointer_file_directs_data_root(pointer_tmp):
    target = pointer_tmp.parent / "mydata"
    target.mkdir()
    pointer_tmp.write_text(str(target) + "\n", encoding="utf-8")
    assert paths.data_root() == target
    assert paths.data_root_source() == "pointer"
    assert paths.get_data_root_pointer() == str(target)


def test_env_wins_over_pointer(pointer_tmp, monkeypatch):
    target = pointer_tmp.parent / "mydata"
    target.mkdir()
    pointer_tmp.write_text(str(target), encoding="utf-8")
    env_dir = pointer_tmp.parent / "envroot"
    env_dir.mkdir()
    monkeypatch.setenv("SUBTRANS_DATA_ROOT", str(env_dir))
    assert paths.data_root() == env_dir
    assert paths.data_root_source() == "env"


@pytest.mark.parametrize("content", ["", "   ", "relative/dir", "\n\n"])
def test_broken_pointer_ignored_falls_back_default(pointer_tmp, content):
    pointer_tmp.write_text(content, encoding="utf-8")
    assert paths.get_data_root_pointer() == ""
    assert paths.data_root() == REPO_ROOT
    assert paths.data_root_source() == "legacy"


def test_set_pointer_then_clear(pointer_tmp):
    target = pointer_tmp.parent / "custom"
    target.mkdir()
    ok, new_root = paths.set_data_root_pointer(str(target))
    assert ok is True
    assert Path(new_root) == target
    assert paths.data_root() == target
    # 清除（空串）→ pointer 删除，回默认
    ok2, default_root = paths.set_data_root_pointer("")
    assert ok2 is True
    assert not pointer_tmp.exists()
    assert Path(default_root) == REPO_ROOT


def test_set_pointer_relative_rejected(pointer_tmp):
    ok, err = paths.set_data_root_pointer("relative/dir")
    assert ok is False
    assert err
    assert not pointer_tmp.exists()


def test_set_pointer_write_failure(pointer_tmp):
    # pointer 位置本身是目录 → 写入 OSError，返回 (False, 错误)
    pointer_tmp.mkdir()
    ok, err = paths.set_data_root_pointer(
        str(pointer_tmp.parent / "elsewhere"))
    assert ok is False
    assert err


def test_frozen_pointer_lives_next_to_executable(monkeypatch, tmp_path):
    exe = tmp_path / "SubTrans.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.delenv("SUBTRANS_DATA_ROOT", raising=False)
    target = tmp_path / "data"
    target.mkdir()
    ok, new_root = paths.set_data_root_pointer(str(target))
    assert ok is True
    assert Path(new_root) == target
    assert (tmp_path / ".data-root").is_file()
    assert paths.get_data_root_pointer() == str(target)
    assert paths.data_root() == target
    assert paths.data_root_source() == "pointer"


def test_no_pointer_file_behavior_unchanged(monkeypatch, tmp_path):
    """pointer 不存在时行为与现状逐字节一致（回归钉）。"""
    monkeypatch.setattr(paths, "_data_root_pointer_path",
                        lambda: tmp_path / ".data-root")
    monkeypatch.delenv("SUBTRANS_DATA_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert paths.data_root() == REPO_ROOT
    assert paths.data_root_source() == "legacy"
    assert paths.get_data_root_pointer() == ""


# ---------------------------------------------------------------------------
# 行动层修复源文三级定位（F1 批0，D2026-1009-01 条件 C1）
# ---------------------------------------------------------------------------
def test_resolve_action_source_path_l1_source_name_hit(tmp_path):
    """L1：guide["source"] 指名文件存在于导读目录 → 原样返回该 Path。"""
    from subtrans.refine import pipeline_support as ps
    src = tmp_path / "ep01.japanese.srt"
    src.write_text("1\n00:00:01,000 --> 00:00:02,000\n甲\n", encoding="utf-8")
    guide = tmp_path / "ep01_质量报告导读.json"
    guide.write_text("{}", encoding="utf-8")
    assert ps.resolve_action_source_path(str(guide), src.name) == src


def test_resolve_action_source_path_l2_stem_srt_fallback(tmp_path):
    """L2：source 指名文件不存在 → 兜底 {stem}.srt（导读文件名剥
    _质量报告导读.json 后缀），str|Path 入参均可。"""
    from subtrans.refine import pipeline_support as ps
    (tmp_path / "ep01.srt").write_text("", encoding="utf-8")
    guide = tmp_path / "ep01_质量报告导读.json"
    guide.write_text("{}", encoding="utf-8")
    assert ps.resolve_action_source_path(guide, "missing.srt") == \
        tmp_path / "ep01.srt"
    assert ps.resolve_action_source_path(str(guide), "") == \
        tmp_path / "ep01.srt"


def test_resolve_action_source_path_empty_source_skips_l1(tmp_path):
    """source_name 空串/空白：跳过 L1 直接走 L2（不拼 guide_dir/"" 目录）。"""
    from subtrans.refine import pipeline_support as ps
    (tmp_path / "ep01.srt").write_text("", encoding="utf-8")
    guide = tmp_path / "ep01_质量报告导读.json"
    guide.write_text("{}", encoding="utf-8")
    assert ps.resolve_action_source_path(guide, "   ") == \
        tmp_path / "ep01.srt"


def test_resolve_action_source_path_l1_wins_over_l2(tmp_path):
    """L1 与 L2 同时可得 → L1（真实输入名）优先。"""
    from subtrans.refine import pipeline_support as ps
    real_src = tmp_path / "movie_v2.srt"
    real_src.write_text("", encoding="utf-8")
    (tmp_path / "ep01.srt").write_text("", encoding="utf-8")
    guide = tmp_path / "ep01_质量报告导读.json"
    guide.write_text("{}", encoding="utf-8")
    assert ps.resolve_action_source_path(guide, real_src.name) == real_src


def test_resolve_action_source_path_none_when_unresolved(tmp_path):
    """L3：两处皆无 → None（退化，调用方不传 --action-source）。"""
    from subtrans.refine import pipeline_support as ps
    guide = tmp_path / "ep01_质量报告导读.json"
    guide.write_text("{}", encoding="utf-8")
    assert ps.resolve_action_source_path(guide, "missing.srt") is None
    assert ps.resolve_action_source_path(guide, "") is None


# ---------------------------------------------------------------------------
# 旧品牌前缀 env 探测（D2026-1106-06 全拍件1：升级首启提示数据源）
# ---------------------------------------------------------------------------
def test_legacy_env_hints_detects_and_maps(monkeypatch):
    """仍设着的旧前缀 env 逐个回报 (旧名, 同后缀新名)；空值不报；动态键族通用。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", "E:/legacy-root")
    monkeypatch.setenv("SUBTRANSJAV_NO_ICON", "1")
    monkeypatch.setenv("SUBTRANSJAV_EMPTY", "  ")
    hints = dict(paths.legacy_env_hints())
    assert hints == {
        "SUBTRANSJAV_DATA_ROOT": "SUBTRANS_DATA_ROOT",
        "SUBTRANSJAV_NO_ICON": "SUBTRANS_NO_ICON",
    }


def test_legacy_env_hints_absent(monkeypatch):
    """无旧前缀 env 时返回空列表（正常机器零噪声）。"""
    for k in list(os.environ):
        if k.startswith("SUBTRANSJAV_"):
            monkeypatch.delenv(k, raising=False)
    assert paths.legacy_env_hints() == []
