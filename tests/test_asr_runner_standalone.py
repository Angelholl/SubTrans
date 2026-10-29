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


def test_runner_wiring_line_break_default_on():
    """接线钉（3.2.1 件①）：缺省 main→写盘链传 line_break=True（断行缺省开）。"""
    mod = _load_runner_standalone()
    captured = {}

    def fake_run(media, model_dir, language, srt_out, **kw):
        captured.update(kw)
        return 0

    mod._run_transcribe_media_ct2 = fake_run
    assert mod.main(["--media", "a.wav", "--srt-out", "a.srt"]) == 0
    assert captured.get("line_break") is True, \
        "缺省未传 line_break=True——断行缺省开语义断裂"


def test_runner_wiring_no_line_break_flag_off():
    """接线钉（3.2.1 件①）：--no-line-break 时 line_break=False（开关可回退）。"""
    mod = _load_runner_standalone()
    captured = {}

    def fake_run(media, model_dir, language, srt_out, **kw):
        captured.update(kw)
        return 0

    mod._run_transcribe_media_ct2 = fake_run
    assert mod.main(["--media", "a.wav", "--srt-out", "a.srt",
                     "--no-line-break"]) == 0
    assert captured.get("line_break") is False, \
        "--no-line-break 未关断行——开关回退路径断裂"


def test_packaging_spec_bundles_line_breaker_alongside_runner():
    """回归钉（3.2.1 件①冒烟拦获缺陷）：spec 随包 asr_runner.py 时必须
    同目录随包 line_breaker.py——直调形态断行器按同目录路径回退装载，
    缺件=frozen 形态断行静默降级（2026-10-29 测试包双路径冒烟实证）。"""
    spec = (pathlib.Path(__file__).resolve().parent.parent
            / "packaging" / "SubTrans.spec").read_text(encoding="utf-8")
    assert "line_breaker.py" in spec, \
        "SubTrans.spec 未随包 line_breaker.py——frozen 断行静默失效复发"


def test_runner_standalone_secrets_hijack_guard_intact():
    """装载后脚本目录不回注 sys.path（refine/secrets.py 劫持守卫不劣化）。"""
    import os
    import sys
    _load_runner_standalone()
    here = os.path.dirname(os.path.abspath(_RUNNER))
    assert all(os.path.abspath(p) != here for p in sys.path if p), \
        "脚本目录被回注 sys.path——secrets.py 标准库劫持风险回潮"
