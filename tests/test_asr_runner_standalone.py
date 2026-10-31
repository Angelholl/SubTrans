"""asr_runner 独立脚本直调形态回归钉（3.2.1 前置件①，D2026-1029-01 发现登记）。

runner 在 ct2 运行时解释器下以脚本直调执行（asr_env._runner_script_path 形态），
无包上下文——`from .line_breaker import` 相对导入必 ImportError，断行器在产品
路径恒静默降级。本钉模拟该形态（spec_from_file_location 无包装载）断言断行器
可解析；并钉包形态装载结果与 subtransjav.refine.line_breaker.break_segments 同源。
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import subprocess
import sys
import types

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


def test_runner_standalone_loads_pass_merge(tmp_path):
    """独立脚本直调形态下双 pass 合并件可装载（卡C §七 勘误裁决 a）。

    子进程 ``-I`` 隔离＋cwd=临时目录：仓库根不入 sys.path，等价运行时
    venv 脚本直调形态（无包上下文、项目包不可导入）——此时只允许同目录
    路径回退装载 pass_merge.py；回退缺件=双 pass 在 frozen/直调形态恒
    不可用（明示报错，不静默）。
    """
    code = (
        "import importlib.util, pathlib, sys\n"
        "p = pathlib.Path(sys.argv[1])\n"
        "s = importlib.util.spec_from_file_location('_ct2_runner_probe', p)\n"
        "m = importlib.util.module_from_spec(s)\n"
        "s.loader.exec_module(m)\n"
        "assert 'subtransjav' not in sys.modules, '包上下文泄漏'\n"
        "pm = m._load_pass_merge()\n"
        "assert 'subtransjav' not in sys.modules, '包上下文泄漏'\n"
        "assert callable(getattr(pm, 'merge_passes', None)), 'merge_passes 缺失'\n"
        "assert getattr(pm, 'DUALPASS_SCHEMA', '') == "
        "'subtransjav.ct2.dualpass/1'\n"
        "assert pathlib.Path(pm.__file__).name == 'pass_merge.py'\n"
    )
    subprocess.run([sys.executable, "-I", "-c", code, str(_RUNNER)],
                   cwd=str(tmp_path), check=True, capture_output=True,
                   text=True, timeout=60)


def test_runner_package_form_pass_merge_same_module():
    """包形态装载结果=包内 pass_merge（同源不漂移，仍走相对导入）。"""
    from subtransjav.refine import asr_runner, pass_merge
    assert asr_runner._load_pass_merge() is pass_merge


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


def test_packaging_spec_bundles_pass_merge_alongside_runner():
    """随包钉（卡C §七 勘误）：spec 随包 asr_runner.py 时必须同目录随包
    pass_merge.py——直调形态按同目录路径回退装载，缺件=frozen 双 pass
    不可用（明示报错，不静默）。"""
    spec = (pathlib.Path(__file__).resolve().parent.parent
            / "packaging" / "SubTrans.spec").read_text(encoding="utf-8")
    assert "pass_merge.py" in spec, \
        "SubTrans.spec 未随包 pass_merge.py——frozen 双 pass 不可用复发"


def test_line_break_failure_falls_back_with_stderr_note(capsys):
    """回退留痕钉（2026-10-29 遗留清零）：断行器故障→原段回退＋stderr
    人话登记（不进 stdout 机器契约；静默降级缺陷不复发）。"""
    mod = _load_runner_standalone()
    def _boom():
        raise RuntimeError("line_breaker missing (injected)")
    mod._load_break_segments = _boom
    segs = [{"start": 0.0, "end": 2.0, "text": "あ" * 20,
             "words": [{"start": 0.0, "end": 1.0, "word": "あ"},
                        {"start": 1.0, "end": 2.0, "word": "あ"}]}]
    out = mod._apply_line_break(segs, True)
    assert out == segs, "故障回退必须返回原始段"
    err = capsys.readouterr().err
    assert "断行器失败" in err and "line_breaker missing" in err
    # 开关关/无词级：完全不触碰断行器（零行为面）
    assert mod._apply_line_break(segs, False) == segs


def test_wordless_segments_line_break_skipped_with_stderr_note(capsys):
    """词级缺失钉（3.2.1 卡A，先红后绿）：全段无 words 时断行跳过必须
    stderr 留痕（ct2 词级输出异常用户可见），并返回原始段。负向钉内含：
    --no-line-break 显式关闭是用户意图非降级，零提示（防每次主动关断行
    刷提示）。"""
    mod = _load_runner_standalone()
    segs = [{"start": 0.0, "end": 2.0, "text": "あ" * 20, "words": []},
            {"start": 2.0, "end": 4.0, "text": "い" * 20}]
    out = mod._apply_line_break(segs, True)
    assert out == segs, "词级缺失必须返回原始段"
    err = capsys.readouterr().err
    assert "断行跳过" in err and "词级" in err, \
        "词级缺失静默跳过——用户不知情（可见性缺口）"
    # 负向钉：显式关闭不得提示（用户意图，非降级）
    assert mod._apply_line_break(segs, False) == segs
    assert capsys.readouterr().err == "", \
        "显式关闭断行不得提示——主动关断行不应刷提示"


def test_three_face_contract_srt_break_stdout_sidecar_raw(
        tmp_path, monkeypatch, capsys):
    """三面契约防漂移钉（现状即绿，非 TDD 件）：SRT 落盘=断行段；stdout
    JSON `segments` 与 sidecar `segments` 恒为原始段。段级消费面（漏听插
    缝 classify_transcript／C22 判档 tr.get("segments")／媒体对照）依赖
    原始段语义——改 stdout 契约须新决策 ID（D2026-1030-06 卡A）。"""
    mod = _load_runner_standalone()
    raw_words = [types.SimpleNamespace(start=0.0, end=1.0, word="あ",
                                       probability=0.9),
                 types.SimpleNamespace(start=1.0, end=2.0, word="あ",
                                       probability=0.8)]
    raw_seg = types.SimpleNamespace(
        start=0.0, end=2.0, text="あ" * 20, words=raw_words,
        no_speech_prob=0.1, avg_logprob=-0.2, compression_ratio=1.0)
    raw = [{"start": 0.0, "end": 2.0, "text": "あ" * 20,
            "words": [{"start": 0.0, "end": 1.0, "word": "あ",
                       "probability": 0.9},
                      {"start": 1.0, "end": 2.0, "word": "あ",
                       "probability": 0.8}],
            "no_speech_prob": 0.1, "avg_logprob": -0.2,
            "compression_ratio": 1.0}]

    class _Info:
        language = "ja"
        duration = 2.0

    class _Model:
        def transcribe(self, media, **kw):
            return iter([raw_seg]), _Info()

    monkeypatch.setitem(sys.modules, "faster_whisper",
                        types.SimpleNamespace())
    monkeypatch.setattr(mod, "_load_model",
                        lambda *a, **kw: (_Model(), "cpu", "int8"))

    def _fake_break(segs):
        return [{**s, "text": s["text"] + "◇"} for s in segs]

    monkeypatch.setattr(mod, "_load_break_segments", lambda: _fake_break)

    media = tmp_path / "a.wav"
    media.write_bytes(b"RIFF")
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    srt_out = tmp_path / "out" / "a.srt"
    rc = mod._run_transcribe_media_ct2(
        str(media), str(model_dir), "ja", str(srt_out),
        beam_size=1, vad_filter=False, condition_previous=False)
    assert rc == 0
    # 面①：SRT 落盘=断行段（可辨识变换生效）
    assert "◇" in srt_out.read_text(encoding="utf-8"), \
        "SRT 未使用断行段——断行接入断裂"
    # 面②：stdout 机器契约 segments=原始段
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["segments"] == raw, \
        "stdout segments 漂移为断行段——段级消费面（漏听插缝/C22）受污染"
    # 面③：sidecar 原始词级=原始段
    sidecar = json.loads(
        (srt_out.parent / "a.srt.words.json").read_text(encoding="utf-8"))
    assert sidecar["segments"] == raw, \
        "sidecar segments 漂移——断行器回放输入断裂"


def test_runner_standalone_secrets_hijack_guard_intact():
    """装载后脚本目录不回注 sys.path（refine/secrets.py 劫持守卫不劣化）。"""
    import os
    import sys
    _load_runner_standalone()
    here = os.path.dirname(os.path.abspath(_RUNNER))
    assert all(os.path.abspath(p) != here for p in sys.path if p), \
        "脚本目录被回注 sys.path——secrets.py 标准库劫持风险回潮"
