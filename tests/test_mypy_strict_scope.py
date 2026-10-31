"""mypy strict 模块面防回退钉（D2026-1030-07 补卡池第 5 类）。

pyproject 的 ``[[tool.mypy.overrides]]`` 必须持续把两个纯逻辑模块圈进
strict 等价旗标面；旗标被静默删减或模块被移出即红，防止严格度扩面无声
退回普通档。

背景：mypy 2.3.1 把 ``strict = true`` 写在 overrides 内会触发全局
set_strict_flags()，strict 泄漏到全包（实测 954 条噪声），故 pyproject
按 ``--strict`` 等价旗标显式展开；本钉同口径锁死该旗标集合。
"""
from pathlib import Path

import pytest

try:
    import tomllib

    _HAS_TOMLIB = True
except ImportError:  # Python 3.10
    _HAS_TOMLIB = False

REPO_ROOT = Path(__file__).resolve().parents[1]

# ``--strict`` 在 per-module 面可用的旗标集合（warn_redundant_casts 不在
# 本版 PER_MODULE_OPTIONS 内，warn_unused_configs 为全局项，均不在此列）。
_STRICT_FLAGS = {
    "disallow_any_generics",
    "disallow_subclassing_any",
    "disallow_untyped_calls",
    "disallow_untyped_defs",
    "disallow_incomplete_defs",
    "check_untyped_defs",
    "disallow_untyped_decorators",
    "no_implicit_optional",
    "warn_unused_ignores",
    "warn_return_any",
    "no_implicit_reexport",
    "strict_equality",
    "extra_checks",
}
_STRICT_MODULES = {
    "subtransjav.refine.pass_merge",
    "subtransjav.refine.pass_disagreement",
}


def _module_overrides() -> dict[str, dict]:
    """pyproject 的 overrides 展开为 module -> 该条 overrides 段。"""
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    result: dict[str, dict] = {}
    for section in data["tool"]["mypy"].get("overrides", []):
        modules = section.get("module", [])
        if isinstance(modules, str):
            modules = [modules]
        for module in modules:
            result[module] = section
    return result


@pytest.mark.skipif(not _HAS_TOMLIB, reason="tomllib requires 3.11+")
def test_strict_scope_modules_present():
    overrides = _module_overrides()
    missing = sorted(_STRICT_MODULES - set(overrides))
    assert not missing, f"pyproject [[tool.mypy.overrides]] 缺 strict 模块面: {missing}"


@pytest.mark.skipif(not _HAS_TOMLIB, reason="tomllib requires 3.11+")
def test_strict_scope_flags_complete():
    overrides = _module_overrides()
    for module in sorted(_STRICT_MODULES):
        section = overrides.get(module, {})
        # strict = true 亦视为等效（该形态若泄漏会被 mypy 基线门当场拦下）
        if section.get("strict") is True:
            continue
        enabled = {key for key, value in section.items() if value is True}
        missing = sorted(_STRICT_FLAGS - enabled)
        assert not missing, f"{module} 的 strict 等价旗标被删减: {missing}"


# 补卡6（D2026-1030-07 第 5 类二轮）：line_breaker 纳入 strict 面。
# 独立断言，既有模块面 _STRICT_MODULES 与上述两条断言保持零改动。
_LINE_BREAKER_MODULE = "subtransjav.refine.line_breaker"


@pytest.mark.skipif(not _HAS_TOMLIB, reason="tomllib requires 3.11+")
def test_line_breaker_in_strict_scope():
    overrides = _module_overrides()
    assert _LINE_BREAKER_MODULE in overrides, (
        f"pyproject [[tool.mypy.overrides]] 缺 {_LINE_BREAKER_MODULE} strict 面")
    section = overrides[_LINE_BREAKER_MODULE]
    if section.get("strict") is True:
        return
    enabled = {key for key, value in section.items() if value is True}
    missing = sorted(_STRICT_FLAGS - enabled)
    assert not missing, f"{_LINE_BREAKER_MODULE} 的 strict 等价旗标被删减: {missing}"
