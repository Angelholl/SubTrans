"""subtransjav.paths 数据路径单一来源测试（打包地基批）"""
import datetime
import sys
from pathlib import Path

import pytest

from subtransjav import paths

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
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    assert paths.data_root() == Path(tmp_path)
    assert paths.data_root_source() == "env"


def test_data_root_env_blank_ignored(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", "   ")
    assert paths.data_root() == Path(tmp_path) / "SubTransJAV"


def test_data_root_frozen_uses_localappdata(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    assert paths.data_root() == Path(tmp_path) / "SubTransJAV"
    assert paths.data_root_source() == "frozen-default"


def test_data_root_frozen_localappdata_missing_falls_back_home(monkeypatch):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    # LOCALAPPDATA 缺失回退家目录，不抛异常
    assert paths.data_root() == Path.home() / "SubTransJAV"


def test_data_root_source_form_is_repo_root(monkeypatch):
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert paths.data_root() == REPO_ROOT
    assert paths.data_root_source() == "legacy"


# ---------------------------------------------------------------------------
# data_root_source 三值
# ---------------------------------------------------------------------------
def test_data_root_source_three_values(monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    assert paths.data_root_source() == "env"
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert paths.data_root_source() == "frozen-default"
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert paths.data_root_source() == "legacy"


# ---------------------------------------------------------------------------
# data_subdir
# ---------------------------------------------------------------------------
def test_data_subdir_source_form_relative_structure(monkeypatch):
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert paths.data_subdir("Temp", "translation_memory").endswith(
        str(Path("Temp") / "translation_memory"))
    assert paths.data_subdir("config").endswith("config")
    assert paths.data_subdir("Errors").endswith("Errors")


# ---------------------------------------------------------------------------
# 迁移状态存根
# ---------------------------------------------------------------------------
def test_migration_state_not_migrated_by_default(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    assert paths.migration_state() == "not-migrated"


def test_migration_state_migrated_with_sentinel(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path))
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    (tmp_path / "SubTransJAV").mkdir()
    (tmp_path / "SubTransJAV" / paths.MIGRATION_SENTINEL).write_text("", encoding="utf-8")
    assert paths.migration_state() == "migrated"


# ---------------------------------------------------------------------------
# 旧位保留 EOL 常量钉（D2026-0930-03 ⑤：定版值，防误改与文档漂移）
# ---------------------------------------------------------------------------
def test_legacy_retention_eol_pinned():
    assert paths.LEGACY_RETENTION_EOL == "2027-06-30"
    d = datetime.date.fromisoformat(paths.LEGACY_RETENTION_EOL)
    assert (d.year, d.month, d.day) == (2027, 6, 30)
    # 迁移模块文档与常量口径同步（防文档漂移）
    from subtransjav import data_migration as dm
    assert "LEGACY_RETENTION_EOL" in (dm.__doc__ or "")


# ---------------------------------------------------------------------------
# 锚点路径钉（D2026-0924-04：源码形态逐字节一致，回归基线只增不减）
# ---------------------------------------------------------------------------
def test_pin_config_dir_is_repo_config():
    from subtransjav.refine import config as rc
    assert str(REPO_ROOT / "config") == rc.CONFIG_DIR


def test_pin_temp_dir_is_repo_temp():
    from subtransjav.refine import config as rc
    assert str(REPO_ROOT / "Temp") == rc.TEMP_DIR


def test_pin_tm_default_dir_is_repo_temp_translation_memory():
    from subtransjav.refine import tm
    assert str(REPO_ROOT / "Temp" / "translation_memory") == tm._DEFAULT_TM_DIR


def test_pin_glossary_conflict_watch_path():
    from subtransjav.refine import glossary_conflict as gc
    assert gc.default_watch_path() == str(
        REPO_ROOT / "Temp" / "translation_memory" / "glossary_conflict_watch.json")


def test_pin_secrets_config_store_is_repo_config():
    from subtransjav.refine import secrets as sec
    assert str(REPO_ROOT / "config" / "api_keys.bin") == sec._CONFIG_STORE


def test_pin_learned_glossary_path_is_repo_config():
    from subtransjav.refine import pipeline_support as ps
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
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
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
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(env_dir))
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
    exe = tmp_path / "SubTransJAV.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
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
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert paths.data_root() == REPO_ROOT
    assert paths.data_root_source() == "legacy"
    assert paths.get_data_root_pointer() == ""
