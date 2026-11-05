"""env 双前缀兼容层行为钉（D2026-1106-02 ①）。

SUBTRANS_* 优先、SUBTRANSJAV_* 共享件兜底＋paths.py 内联镜像兜底：
包名 subtransjav→subtrans 改名后的存量用户脚本/CI 雴破坏面。
四读取面全钉：共享 helper 三态、data_root 双前缀优先序、旧根发现双前缀、
CT2 落位解析与可调字段 env 覆盖双前缀。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from subtrans import paths
from subtrans.utils import env_compat

_ENV_VARS = (
    "SUBTRANS_DATA_ROOT", "SUBTRANSJAV_DATA_ROOT",
    "SUBTRANS_CT2_RUNTIME_DIR", "SUBTRANSJAV_CT2_RUNTIME_DIR",
    "SUBTRANS_LEGACY_ROOT", "SUBTRANSJAV_LEGACY_ROOT",
    "SUBTRANS_TIMEOUT_PROBE", "SUBTRANSJAV_TIMEOUT_PROBE",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """清空相关 env，保证各用例独立零污染。"""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_env_get_precedence_fallback_unset(monkeypatch):
    """共享 helper 三态：新前缀优先 > 旧前缀兜底 > 两空返 None。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", r"C:\legacy")
    assert env_compat.env_get("DATA_ROOT") == r"C:\legacy"
    monkeypatch.setenv("SUBTRANS_DATA_ROOT", r"C:\new")
    assert env_compat.env_get("DATA_ROOT") == r"C:\new"
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    assert env_compat.env_get("DATA_ROOT") == r"C:\new"
    monkeypatch.delenv("SUBTRANS_DATA_ROOT", raising=False)
    assert env_compat.env_get("DATA_ROOT") is None


def test_data_root_dual_prefix(monkeypatch):
    """data_root() 内联镜像与共享件同构：新前缀优先、旧前缀兜底。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", r"C:\legacy-root")
    assert paths.data_root() == Path(r"C:\legacy-root")
    monkeypatch.setenv("SUBTRANS_DATA_ROOT", r"C:\new-root")
    assert paths.data_root() == Path(r"C:\new-root")
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    # 仅新前缀：env 面生效（不 assert pointer/frozen 分支值）
    assert paths.data_root_source() == "env"


def test_discover_legacy_root_dual_prefix(monkeypatch):
    """旧根发现双前缀：新前缀优先、旧前缀兜底。"""
    from subtrans.data_migration import _discover_legacy_root

    monkeypatch.setenv("SUBTRANSJAV_LEGACY_ROOT", r"C:\legacy")
    assert _discover_legacy_root() == Path(r"C:\legacy")
    monkeypatch.setenv("SUBTRANS_LEGACY_ROOT", r"C:\new")
    assert _discover_legacy_root() == Path(r"C:\new")


def test_ct2_runtime_dir_dual_prefix(monkeypatch):
    """CT2 落位解析双前缀：env 面优先级最高（source=env）。"""
    from subtrans.refine import asr_runtime

    monkeypatch.setenv("SUBTRANSJAV_CT2_RUNTIME_DIR", r"C:\rt-legacy")
    info = asr_runtime.runtime_dir_info()
    assert info["source"] == "env"
    assert info["dir"] == r"C:\rt-legacy"
    monkeypatch.setenv("SUBTRANS_CT2_RUNTIME_DIR", r"C:\rt-new")
    assert asr_runtime.runtime_dir_info()["dir"] == r"C:\rt-new"


def test_resolve_tunable_dual_prefix(monkeypatch):
    """可调字段 env 覆盖双前缀：新前缀优先、旧前缀兜底。"""
    from subtrans.refine.config import resolve_tunable

    monkeypatch.setenv("SUBTRANSJAV_TIMEOUT_PROBE", "8")
    assert resolve_tunable("timeout_probe") == 8.0
    monkeypatch.setenv("SUBTRANS_TIMEOUT_PROBE", "2")
    assert resolve_tunable("timeout_probe") == 2.0
    monkeypatch.delenv("SUBTRANSJAV_TIMEOUT_PROBE", raising=False)
    assert resolve_tunable("timeout_probe") == 2.0
    monkeypatch.delenv("SUBTRANS_TIMEOUT_PROBE", raising=False)
    # 两前缀均未设 → 回落 user_settings/默认值链（不 assert 具体值）
    resolve_tunable("timeout_probe")
