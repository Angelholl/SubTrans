"""env 前缀读取面行为钉（D2026-1106-02 ①；兼容层已随 owner 二次拍板下线）。

包名 subtransjav→subtrans 后 env 前缀统一 ``SUBTRANS_*`` 单前缀；
旧名 ``SUBTRANSJAV_*`` 已移除、不再生效（数据根旧名静默回默认位语义，
钉死防止回归复活兼容路径或误加双读）。
四读取面：data_root 单前缀、旧根发现、CT2 落位、可调字段 env 覆盖。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from subtrans import paths

_ENV_VARS = (
    "SUBTRANS_DATA_ROOT",
    "SUBTRANS_CT2_RUNTIME_DIR",
    "SUBTRANS_LEGACY_ROOT",
    "SUBTRANS_TIMEOUT_PROBE",
)


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch):
    """清空相关 env，保证各用例独立零污染。"""
    for var in _ENV_VARS:
        monkeypatch.delenv(var, raising=False)


def test_data_root_single_prefix(monkeypatch):
    """data_root() 单前缀：SUBTRANS_DATA_ROOT 生效、来源标签 env。"""
    monkeypatch.setenv("SUBTRANS_DATA_ROOT", r"C:\new-root")
    assert paths.data_root() == Path(r"C:\new-root")
    assert paths.data_root_source() == "env"


def test_data_root_legacy_prefix_retired(monkeypatch):
    """旧前缀 SUBTRANSJAV_DATA_ROOT 已下线：不再被读取（数据根回默认解析）。

    静默回默认位是本钉的语义核心——旧名若被误复活（双读回归）此钉变红。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", r"C:\legacy-root")
    assert paths.data_root() != Path(r"C:\legacy-root")
    assert paths.data_root_source() != "env"


def test_discover_legacy_root_single_prefix(monkeypatch):
    """旧根发现单前缀：SUBTRANS_LEGACY_ROOT 生效。"""
    from subtrans.data_migration import _discover_legacy_root

    monkeypatch.setenv("SUBTRANS_LEGACY_ROOT", r"C:\legacy")
    assert _discover_legacy_root() == Path(r"C:\legacy")


def test_ct2_runtime_dir_single_prefix(monkeypatch):
    """CT2 落位解析单前缀：env 面优先级最高（source=env）。"""
    from subtrans.refine import asr_runtime

    monkeypatch.setenv("SUBTRANS_CT2_RUNTIME_DIR", r"C:\rt-new")
    info = asr_runtime.runtime_dir_info()
    assert info["source"] == "env"
    assert info["dir"] == r"C:\rt-new"


def test_resolve_tunable_single_prefix(monkeypatch):
    """可调字段 env 覆盖单前缀：SUBTRANS_TIMEOUT_PROBE 生效。"""
    from subtrans.refine.config import resolve_tunable

    monkeypatch.setenv("SUBTRANS_TIMEOUT_PROBE", "2")
    assert resolve_tunable("timeout_probe") == 2.0
    monkeypatch.delenv("SUBTRANS_TIMEOUT_PROBE", raising=False)
    # 未设 → 回落 user_settings/默认值链（不 assert 具体值）
    resolve_tunable("timeout_probe")
