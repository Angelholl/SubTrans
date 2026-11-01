"""C22 校准门迁移 seeding 回归钉（D2026-1101-01，卡 d1101-C22迁移seeding-单卡）。

覆盖卡 §三 六条验收判据的可钉部分：
- 幂等反覆盖：缺行才补；存量显式 ``enabled:false`` 零扰动（字节不变）；
- 原子写入：写失败不落半态、fail-closed 且记日志；
- dev metrics 不随包下发：seeding 缺省行只含 enabled+指纹，不带
  measured_at/precision_lb/coverage/n；
- 指纹 fail-closed：rules_sha1+app_version 缺失/不匹配一律关门
  （含读取侧 API 集成）；
- 三条升级路径：全新安装（无文件）、3.1.1 实装（存量五字段行）、
  3.0 连跳（无中间版本行，重复 seeding 幂等）均钉。

隔离：所有落盘都在 tmp_path（显式 config_dir 或 CONFIG_DIR 打桩），
不读写仓库真实 config/。
"""
import json
import logging
import sys
from pathlib import Path

import pytest

from subtransjav import data_migration as dm

_DEV_METRIC_KEYS = {"measured_at", "precision_lb", "coverage", "n"}


def _gate(config_dir: Path) -> Path:
    return config_dir / "fullchain_c22.json"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 白名单（迁移侧「配置行到达用户机」）
# ---------------------------------------------------------------------------
def test_gate_relpath_in_migration_whitelist():
    """老根已有门控文件（显式 false 等用户意志）必须随迁移到达新根。"""
    assert dm.C22_GATE_RELPATH == "config/fullchain_c22.json"
    assert dm.C22_GATE_RELPATH in dm._BASE_FILES


# ---------------------------------------------------------------------------
# 缺行→补行（全新安装 / 缺行升级）
# ---------------------------------------------------------------------------
def test_missing_row_seeds_enabled_true_with_fingerprint(tmp_path):
    cfg = tmp_path / "config"
    assert dm.seed_c22_gate(cfg) == "seeded"
    data = _read(_gate(cfg))
    rules_sha1, app_version = dm.c22_gate_fingerprint()
    assert data["enabled"] is True
    assert data["rules_sha1"] == rules_sha1
    assert data["app_version"] == app_version
    assert not (_DEV_METRIC_KEYS & set(data)), "dev 实测字段不得冒充用户读数下发"


def test_missing_row_creates_parent_dir(tmp_path):
    cfg = tmp_path / "not-yet" / "config"
    assert dm.seed_c22_gate(cfg) == "seeded"
    assert _gate(cfg).is_file()


# ---------------------------------------------------------------------------
# 反覆盖钉：存量显式 false / 存量测量行零扰动
# ---------------------------------------------------------------------------
def test_existing_explicit_false_zero_disturbance(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    gate = _gate(cfg)
    original = json.dumps({"enabled": False, "measured_at": "2026-10-01 00:00:00",
                           "precision_lb": 0.96, "coverage": 0.55, "n": 83})
    gate.write_text(original, encoding="utf-8")
    before = gate.read_bytes()

    assert dm.seed_c22_gate(cfg) == "kept-existing"
    assert gate.read_bytes() == before, "用户显式关闭的意志不得被覆盖"


def test_existing_legacy_measurement_row_zero_disturbance(tmp_path):
    """3.1.1 实装路径：五字段行（enabled=true，无指纹）迁移后原样保留；
    读取侧按指纹缺失关门并要求重校准（旧测量依据不得静默复用）。"""
    cfg = tmp_path / "config"
    cfg.mkdir()
    gate = _gate(cfg)
    gate.write_text(json.dumps({"enabled": True, "measured_at":
                                "2026-10-31 12:30:12", "precision_lb": 0.9558,
                                "coverage": 0.5461, "n": 83}), encoding="utf-8")
    before = gate.read_bytes()

    assert dm.seed_c22_gate(cfg) == "kept-existing"
    assert gate.read_bytes() == before
    ok, reason = dm.evaluate_c22_gate(gate)
    assert ok is False and reason == "fingerprint-missing"


# ---------------------------------------------------------------------------
# 损坏/半态 → fail-closed 不崩＋日志
# ---------------------------------------------------------------------------
def test_corrupt_file_fail_closed_keeps_bytes_and_logs(tmp_path, caplog):
    cfg = tmp_path / "config"
    cfg.mkdir()
    gate = _gate(cfg)
    gate.write_text('{"enabled": tr', encoding="utf-8")
    before = gate.read_bytes()

    with caplog.at_level(logging.WARNING, logger="subtransjav.data_migration"):
        assert dm.seed_c22_gate(cfg) == "skipped-invalid"
    assert gate.read_bytes() == before, "损坏文件不得被静默改写"
    assert any("C22" in r.message for r in caplog.records)


def test_non_dict_json_fail_closed(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    gate = _gate(cfg)
    gate.write_text("[]", encoding="utf-8")
    before = gate.read_bytes()
    assert dm.seed_c22_gate(cfg) == "skipped-invalid"
    assert gate.read_bytes() == before


# ---------------------------------------------------------------------------
# 原子写入：失败不落半态
# ---------------------------------------------------------------------------
def test_atomic_write_failure_fail_closed(tmp_path, monkeypatch, caplog):
    from subtransjav.refine import fs_utils

    cfg = tmp_path / "config"

    def _boom(path, text, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(fs_utils, "_atomic_write_text", _boom)
    with caplog.at_level(logging.WARNING, logger="subtransjav.data_migration"):
        assert dm.seed_c22_gate(cfg) == "failed:OSError"
    assert not _gate(cfg).exists(), "写失败必须零残留（不得留半态文件）"
    if cfg.is_dir():
        assert list(cfg.glob("*.tmp")) == []
    assert any("C22" in r.message for r in caplog.records)


def test_seed_without_rules_fingerprint_refuses_to_write(tmp_path, monkeypatch):
    monkeypatch.setattr(dm, "c22_gate_fingerprint", lambda *a, **k: (None, "9.9.9"))
    cfg = tmp_path / "config"
    assert dm.seed_c22_gate(cfg).startswith("failed:")
    assert not _gate(cfg).exists(), "无规则指纹=无锁，宁可不补行（fail-closed）"


# ---------------------------------------------------------------------------
# 连跳路径幂等（3.0→3.1.2：整条链从未出现过门控行）
# ---------------------------------------------------------------------------
def test_seeding_twice_is_idempotent(tmp_path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "user_settings.json").write_text('{"v2_ctx_local": 16384}',
                                            encoding="utf-8")
    assert dm.seed_c22_gate(cfg) == "seeded"
    first = _gate(cfg).read_bytes()
    assert dm.seed_c22_gate(cfg) == "kept-existing"
    assert _gate(cfg).read_bytes() == first


# ---------------------------------------------------------------------------
# 首启插桩：frozen 首启（全新安装与升级共用）触发 seeding；pip 形态零写入
# ---------------------------------------------------------------------------
@pytest.fixture
def frozen_root(monkeypatch, tmp_path):
    lac = tmp_path / "localappdata"
    lac.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.delenv(dm.LEGACY_ROOT_ENV, raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(lac))
    return lac / "SubTrans"


def test_fresh_install_startup_seeds_gate(frozen_root):
    assert dm.ensure_migrated(verbose=False) == "not-applicable:no-legacy-data"
    gate = frozen_root / "config" / "fullchain_c22.json"
    assert _read(gate)["enabled"] is True


# ---------------------------------------------------------------------------
# 升级路径端到端（D2026-1101-01 §三⑥：真实升级/多版本连跳/迁移失败防顶替）
# ---------------------------------------------------------------------------
def _make_upgrade_roots(monkeypatch, tmp_path):
    """frozen + 显式旧根（含最小白名单源文件），返回 (旧根, 新根)。"""
    legacy = tmp_path / "legacy"
    lac = tmp_path / "localappdata"
    (legacy / "config").mkdir(parents=True)
    lac.mkdir()
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(lac))
    monkeypatch.setenv(dm.LEGACY_ROOT_ENV, str(legacy))
    (legacy / "config" / "user_settings.json").write_text(
        '{"v2_ctx_local": 16384}', encoding="utf-8")
    return legacy, lac / "SubTrans"


def test_upgrade_legacy_gate_row_reaches_new_root(monkeypatch, tmp_path):
    """真实升级路径（3.1.1→3.1.2）：旧根显式 enabled:false 测量行随白名单
    原样到达新根，seeding 零扰动、读取侧按 disabled 关门。"""
    legacy, new_root = _make_upgrade_roots(monkeypatch, tmp_path)
    (legacy / "config" / "fullchain_c22.json").write_text(
        json.dumps({"enabled": False, "measured_at": "2026-10-30 09:00:00",
                    "precision_lb": 0.9, "coverage": 0.5, "n": 40}),
        encoding="utf-8")
    assert dm.ensure_migrated(verbose=False) == "migrated"
    arrived = _read(new_root / "config" / "fullchain_c22.json")
    assert arrived["enabled"] is False and arrived["n"] == 40


def test_upgrade_without_gate_row_seeds(monkeypatch, tmp_path):
    """多版本连跳（3.0→3.1.2，旧根从未含门控行）：迁移成功后 seeding
    照常补行（enabled=true＋现行指纹）。"""
    legacy, new_root = _make_upgrade_roots(monkeypatch, tmp_path)
    assert dm.ensure_migrated(verbose=False) == "migrated"
    seeded = _read(new_root / "config" / "fullchain_c22.json")
    rules_sha1, app_version = dm.c22_gate_fingerprint()
    assert seeded == {"enabled": True, "rules_sha1": rules_sha1,
                      "app_version": app_version}


def test_migration_failure_skips_seeding(monkeypatch, tmp_path):
    """迁移未完成（failed/skipped-locked/retry-wal）→ 本轮跳过 seeding，
    新根不落 enabled=true 行（防缺省意志顶替旧根显式意志，fail-closed）。"""
    _, new_root = _make_upgrade_roots(monkeypatch, tmp_path)
    monkeypatch.setattr(dm, "_ensure_migrated_inner",
                        lambda verbose: "skipped-locked")
    assert dm.ensure_migrated(verbose=False) == "skipped-locked"
    assert not _gate(new_root).exists()
    monkeypatch.setattr(dm, "_ensure_migrated_inner",
                        lambda verbose: "failed:validate")
    assert dm.ensure_migrated(verbose=False) == "failed:validate"
    assert not _gate(new_root).exists()


def test_pip_form_never_seeds(monkeypatch, tmp_path):
    from subtransjav.refine import config as cfg_mod

    monkeypatch.setattr(sys, "frozen", False, raising=False)
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    monkeypatch.delenv(dm.LEGACY_ROOT_ENV, raising=False)
    cfg_dir = tmp_path / "config"
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(cfg_dir))
    assert dm.ensure_migrated(verbose=False) == "not-applicable:pip"
    assert not _gate(cfg_dir).exists(), "源码/pip 形态零感知零写入"


# ---------------------------------------------------------------------------
# 读取侧指纹校验（fail-closed）
# ---------------------------------------------------------------------------
def _write_gate(cfg_dir: Path, **overrides) -> Path:
    cfg_dir.mkdir(parents=True, exist_ok=True)
    rules_sha1, app_version = dm.c22_gate_fingerprint()
    payload = {"enabled": True, "rules_sha1": rules_sha1,
               "app_version": app_version}
    payload.update(overrides)
    gate = _gate(cfg_dir)
    gate.write_text(json.dumps(payload), encoding="utf-8")
    return gate


def test_evaluate_gate_ok_only_with_matching_fingerprint(tmp_path):
    gate = _write_gate(tmp_path / "config")
    assert dm.evaluate_c22_gate(gate) == (True, "ok")


@pytest.mark.parametrize("field", ["rules_sha1", "app_version"])
def test_evaluate_gate_closes_on_fingerprint_mismatch(tmp_path, field):
    gate = _write_gate(tmp_path / "config", **{field: "deadbeef"})
    ok, reason = dm.evaluate_c22_gate(gate)
    assert ok is False and reason == "fingerprint-mismatch"


@pytest.mark.parametrize("field", ["rules_sha1", "app_version"])
def test_evaluate_gate_closes_on_missing_fingerprint(tmp_path, field):
    gate = _write_gate(tmp_path / "config")
    data = _read(gate)
    del data[field]
    gate.write_text(json.dumps(data), encoding="utf-8")
    ok, reason = dm.evaluate_c22_gate(gate)
    assert ok is False and reason == "fingerprint-missing"


def test_evaluate_gate_missing_corrupt_disabled(tmp_path):
    gate = _gate(tmp_path / "config")
    assert dm.evaluate_c22_gate(gate) == (False, "missing")
    gate.parent.mkdir(parents=True, exist_ok=True)
    gate.write_text("{broken", encoding="utf-8")
    assert dm.evaluate_c22_gate(gate) == (False, "invalid")
    gate.write_text(json.dumps({"enabled": False}), encoding="utf-8")
    assert dm.evaluate_c22_gate(gate) == (False, "disabled")


def test_gui_gate_reader_closes_on_stale_fingerprint(tmp_path, monkeypatch):
    from subtransjav.refine import config as cfg_mod
    from subtransjav.webview_gui.api import TranslateAPI

    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(tmp_path))
    gui = object.__new__(TranslateAPI)
    _write_gate(tmp_path, rules_sha1="stale")
    assert gui._fullchain_c22_enabled() is False


def test_gui_gate_reader_opens_with_matching_fingerprint(tmp_path, monkeypatch):
    from subtransjav.refine import config as cfg_mod
    from subtransjav.webview_gui.api import TranslateAPI

    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(tmp_path))
    gui = object.__new__(TranslateAPI)
    _write_gate(tmp_path)
    assert gui._fullchain_c22_enabled() is True
