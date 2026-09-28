"""EXE 首发数据迁移测试（D2026-0929-07 验收②：双源夹具 + 故障注入）。

夹具：
- "pip 旧根"  tmp/legacy：tm.db（数行）+ conflict watch json(.bak) +
  api_keys.bin（secrets 真实加密一笔测试密钥）+ user_settings.json；
- "frozen 新根" tmp/localappdata/SubTransJAV：monkeypatch LOCALAPPDATA +
  sys.frozen（沿 tests/test_paths.py 口径）。

旧根发现经 SUBTRANSJAV_LEGACY_ROOT 显式指定（data_migration._discover_legacy_root
的 env 优先级即诊断/测试通道）。
"""
import json
import sqlite3
import sys
import zipfile
from pathlib import Path

import pytest

from subtransjav import data_migration as dm
from subtransjav import paths
from subtransjav.refine import secrets as sec


# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------
@pytest.fixture
def roots(monkeypatch, tmp_path):
    """双源夹具：返回 (legacy_root, new_root)。"""
    legacy = tmp_path / "legacy"
    lac = tmp_path / "localappdata"
    legacy.mkdir()
    lac.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(lac))
    monkeypatch.setenv(dm.LEGACY_ROOT_ENV, str(legacy))
    return legacy, lac / "SubTransJAV"


def _make_legacy(legacy: Path) -> None:
    tm_dir = legacy / "Temp" / "translation_memory"
    cfg = legacy / "config"
    tm_dir.mkdir(parents=True)
    cfg.mkdir(parents=True)
    conn = sqlite3.connect(str(tm_dir / "tm.db"))
    conn.execute("CREATE TABLE tm_entries "
                 "(source_text TEXT, target_text TEXT, stage INTEGER)")
    conn.executemany("INSERT INTO tm_entries VALUES (?, ?, ?)",
                     [(f"src{i}", f"dst{i}", 1) for i in range(5)])
    conn.commit()
    conn.close()
    (tm_dir / "glossary_conflict_watch.json").write_text(
        json.dumps([{"term": "x"}]), encoding="utf-8")
    (tm_dir / "glossary_conflict_watch.json.bak").write_text("[]", encoding="utf-8")
    sec.store_secret("deepseek", "sk-test-123",
                     store_path=str(cfg / "api_keys.bin"))
    (cfg / "user_settings.json").write_text('{"v2_ctx_local": 16384}',
                                            encoding="utf-8")


def _rows(db: Path) -> int:
    conn = sqlite3.connect(str(db))
    try:
        return conn.execute("SELECT COUNT(*) FROM tm_entries").fetchone()[0]
    finally:
        conn.close()


def _backup_zips(new_root: Path) -> list[Path]:
    b = new_root / "backups"
    return sorted(b.glob(f"{dm.BACKUP_PREFIX}*.zip")) if b.is_dir() else []


# ---------------------------------------------------------------------------
# 正常迁移
# ---------------------------------------------------------------------------
def test_full_migration(roots):
    legacy, new_root = roots
    _make_legacy(legacy)
    assert dm.ensure_migrated(verbose=True) == "migrated"

    # 三文件齐迁 + integrity 过
    assert _rows(new_root / "Temp" / "translation_memory" / "tm.db") == 5
    watch = json.loads((new_root / "Temp" / "translation_memory" /
                        "glossary_conflict_watch.json").read_text(encoding="utf-8"))
    assert watch == [{"term": "x"}]
    assert sec.read_secret("deepseek", store_path=str(
        new_root / "config" / "api_keys.bin")) == "sk-test-123"
    assert (new_root / "config" / "user_settings.json").is_file()

    # 数据根 manifest 存在，哨兵内容含 manifest sha256（哨兵最后写）
    manifest = json.loads((new_root / dm.MANIFEST_NAME).read_text(encoding="utf-8"))
    sha = dm._manifest_sha256(manifest)
    sentinel = (new_root / paths.MIGRATION_SENTINEL).read_text(encoding="utf-8")
    assert sha in sentinel
    assert manifest["files"][0]["tm_rows"] == 5

    # 备份 zip：内含 manifest + tm.db；manifest sha 与哨兵一致
    zips = _backup_zips(new_root)
    assert len(zips) == 1
    with zipfile.ZipFile(zips[0]) as zf:
        names = zf.namelist()
        assert dm.MANIFEST_NAME in names
        assert "Temp/translation_memory/tm.db" in names
        zm = json.loads(zf.read(dm.MANIFEST_NAME).decode("utf-8"))
    assert dm._manifest_sha256(zm) == sha

    # 旧位原样保留
    assert _rows(legacy / "Temp" / "translation_memory" / "tm.db") == 5
    assert (legacy / "Temp" / "translation_memory" /
            "glossary_conflict_watch.json.bak").is_file()

    assert paths.migration_state() == "migrated"


def test_idempotent_second_call_no_side_effect(roots):
    legacy, new_root = roots
    _make_legacy(legacy)
    assert dm.ensure_migrated(verbose=False) == "migrated"
    zips_before = _backup_zips(new_root)
    rows_before = _rows(new_root / "Temp" / "translation_memory" / "tm.db")
    sentinel_before = (new_root / paths.MIGRATION_SENTINEL).read_text(encoding="utf-8")

    assert dm.ensure_migrated(verbose=False) == "already-migrated"
    assert _backup_zips(new_root) == zips_before
    assert _rows(new_root / "Temp" / "translation_memory" / "tm.db") == rows_before
    assert (new_root / paths.MIGRATION_SENTINEL
            ).read_text(encoding="utf-8") == sentinel_before


# ---------------------------------------------------------------------------
# 故障注入
# ---------------------------------------------------------------------------
def test_disk_insufficient_aborts_zero_write(roots, monkeypatch):
    legacy, new_root = roots
    _make_legacy(legacy)
    monkeypatch.setattr(dm, "_disk_free_bytes", lambda _p: 0)
    assert dm.ensure_migrated(verbose=False).startswith("failed")
    assert not (new_root / paths.MIGRATION_SENTINEL).exists()
    assert not (new_root / "Temp" / "translation_memory" / "tm.db").exists()
    assert _backup_zips(new_root) == []
    assert not (new_root / dm.MANIFEST_NAME).exists()


def test_checkpoint_failure_abort_retry_later(roots, monkeypatch):
    legacy, new_root = roots
    _make_legacy(legacy)
    with monkeypatch.context() as ctx:
        ctx.setattr(dm, "_checkpoint_wal",
                    lambda _p: (_ for _ in ()).throw(
                        sqlite3.OperationalError("database is locked")))
        assert dm.ensure_migrated(verbose=False) == "retry-wal"
    # 下次启动（不再注入）重试成功
    assert not (new_root / paths.MIGRATION_SENTINEL).exists()
    assert _backup_zips(new_root) == []          # checkpoint 在备份前，零写入
    assert _rows(legacy / "Temp" / "translation_memory" / "tm.db") == 5

    # 下次启动（不再注入）重试成功
    assert dm.ensure_migrated(verbose=False) == "migrated"


def test_corrupt_tm_db_validation_failure_cleans_residuals(roots):
    legacy, new_root = roots
    _make_legacy(legacy)
    db = legacy / "Temp" / "translation_memory" / "tm.db"
    original = db.read_bytes()
    db.write_bytes(original[:32])                # 截断损坏
    assert dm.ensure_migrated(verbose=False).startswith("failed")
    # 新根仅 manifest 清单匹配的残留被清（此处未落位即失败）
    assert not (new_root / "Temp" / "translation_memory" / "tm.db").exists()
    assert not (new_root / paths.MIGRATION_SENTINEL).exists()
    assert not (new_root / dm.MANIFEST_NAME).exists()
    # 旧位完好
    assert db.read_bytes() == original[:32]


# ---------------------------------------------------------------------------
# 半迁移自愈
# ---------------------------------------------------------------------------
def test_invalid_sentinel_walks_old_root(roots, capsys):
    legacy, new_root = roots
    _make_legacy(legacy)
    new_root.mkdir(parents=True)
    (new_root / paths.MIGRATION_SENTINEL).write_text("bogus", encoding="utf-8")
    assert dm.ensure_migrated(verbose=True) == "migrated"   # 无效哨兵按未迁移重走
    assert "无效哨兵" in capsys.readouterr().out
    assert _rows(new_root / "Temp" / "translation_memory" / "tm.db") == 5


def test_half_migration_cleanup_respects_whitelist(roots):
    legacy, new_root = roots
    _make_legacy(legacy)
    # 先完整迁一次生成真实备份 zip
    assert dm.ensure_migrated(verbose=False) == "migrated"
    # 伪造半迁移：删哨兵+manifest+部分新根文件，另放白名单外用户文件
    (new_root / paths.MIGRATION_SENTINEL).unlink()
    (new_root / dm.MANIFEST_NAME).unlink()
    (new_root / "Temp" / "translation_memory" / "glossary_conflict_watch.json").unlink()
    foreign = new_root / "config" / "my_precious_notes.txt"
    foreign.write_text("user data", encoding="utf-8")

    assert dm.ensure_migrated(verbose=False) == "migrated"
    assert foreign.read_text(encoding="utf-8") == "user data"   # 白名单外不误删
    assert _rows(new_root / "Temp" / "translation_memory" / "tm.db") == 5


# ---------------------------------------------------------------------------
# 多实例锁 / 幂等边界
# ---------------------------------------------------------------------------
def test_lock_conflict_skips(roots, monkeypatch):
    from subtransjav.refine.artifact_lock import ArtifactLockConflict

    legacy, new_root = roots
    _make_legacy(legacy)

    def _conflict(_root):
        raise ArtifactLockConflict("locked")

    monkeypatch.setattr(dm, "_acquire_lock", _conflict)
    assert dm.ensure_migrated(verbose=False) == "skipped-locked"
    assert not (new_root / paths.MIGRATION_SENTINEL).exists()


# ---------------------------------------------------------------------------
# 触发条件硬闸
# ---------------------------------------------------------------------------
def test_pip_form_never_migrates(monkeypatch, tmp_path):
    legacy = tmp_path / "legacy"
    _make_legacy(legacy)
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.setenv(dm.LEGACY_ROOT_ENV, str(legacy))
    repo_root = Path(paths.__file__).resolve().parents[1]
    assert dm.ensure_migrated(verbose=False) == "not-applicable:pip"
    # 仓库根零写入
    assert not (repo_root / paths.MIGRATION_SENTINEL).exists()
    assert not (repo_root / "backups").exists()


def test_env_specified_root_skips(roots, monkeypatch, tmp_path):
    legacy, _new_root = roots
    _make_legacy(legacy)
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path / "custom"))
    assert dm.ensure_migrated(verbose=False) == "not-applicable:env-root"
    assert not (tmp_path / "custom" / paths.MIGRATION_SENTINEL).exists()


def test_no_legacy_data_skips(roots):
    legacy, new_root = roots          # 空旧根
    assert dm.ensure_migrated(verbose=False) == "not-applicable:no-legacy-data"
    assert not new_root.exists() or not (new_root / paths.MIGRATION_SENTINEL).exists()


# ---------------------------------------------------------------------------
# 桩点
# ---------------------------------------------------------------------------
def test_cli_stub_where_early_exit_not_counted(monkeypatch, tmp_path, capsys):
    from subtransjav.refine import cli

    calls = []
    monkeypatch.setattr(dm, "ensure_migrated",
                        lambda verbose=False: calls.append(verbose) or "not-applicable:pip")
    assert cli.main(["--where"]) == 0
    assert calls == []                       # --where 只读早退不触发迁移


def test_cli_stub_normal_path_counted_once(monkeypatch, tmp_path):
    from subtransjav.refine import cli

    calls = []
    monkeypatch.setattr(dm, "ensure_migrated",
                        lambda verbose=False: calls.append(verbose) or "not-applicable:pip")
    tmdb = tmp_path / "tmstats.db"
    cli.main(["--tm-stats", "--tm-db", str(tmdb)])
    assert calls == [True]                   # 普通路径计数一次（verbose=True 透传）


def test_gui_stub_present_source_level():
    src = (Path(paths.__file__).parent / "webview_gui" / "main.py").read_text(
        encoding="utf-8")
    main_body = src[src.index("def main():"):]
    i_freeze = main_body.index("freeze_support()")
    i_stub = main_body.index("ensure_migrated(")
    i_setup = main_body.index("_auto_setup()")
    assert i_freeze < i_stub < i_setup       # freeze_support 后、_auto_setup 前
    stub = main_body[i_stub - 400:i_stub + 200]
    assert "try:" in stub and "except Exception" in stub   # 全容错包裹
