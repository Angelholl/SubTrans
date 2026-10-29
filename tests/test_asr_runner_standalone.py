"""asr_runner 独立脚本直调形态回归钉（3.2.1 前置件①，D2026-1029-01 发现登记）。

runner 在 ct2 运行时解释器下以脚本直调执行（asr_env._runner_script_path 形态），
无包上下文——`from .line_breaker import` 相对导入必 ImportError，断行器在产品
路径恒静默降级。本钉模拟该形态（spec_from_file_location 无包装载）断言断行器
可解析；并钉包形态装载结果与 subtransjav.refine.line_breaker.break_segments 同源。
"""
from __future__ import annotations

import importlib.util
import pathlib

_RUNNER = (pathlib.Path(__file__).resolve().parent.parent
           / "subtransjav" / "refine" / "asr_runner.py")


def _load_runner_standalone():
    """以无包上下文装载 asr_runner（模拟运行时 venv 脚本直调形态）。"""
    spec = importlib.util.spec_from_file_location("_ct2_runner_standalone", _RUNNER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_runner_standalone_loads_break_segments():
    """独立脚本直调形态下断行器可装载（修前：相对导入 ImportError→红）。"""
    mod = _load_runner_standalone()
    loader = getattr(mod, "_load_break_segments", None)
    assert loader is not None, "runner 缺 _load_break_segments 装载入口"
    break_segments = loader()
    assert callable(break_segments)


def test_runner_package_form_same_function():
    """包形态装载结果=包内 line_breaker.break_segments（同源不漂移）。"""
    from subtransjav.refine import asr_runner, line_breaker
    assert asr_runner._load_break_segments() is line_breaker.break_segments


def test_runner_standalone_secrets_hijack_guard_intact():
    """装载后脚本目录不回注 sys.path（refine/secrets.py 劫持守卫不劣化）。"""
    import os
    import sys
    _load_runner_standalone()
    here = os.path.dirname(os.path.abspath(_RUNNER))
    assert all(os.path.abspath(p) != here for p in sys.path if p), \
        "脚本目录被回注 sys.path——secrets.py 标准库劫持风险回潮"
