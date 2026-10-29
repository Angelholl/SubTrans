"""asr_runner device 选择与 cpu 回退钉（件B GPU DLL 补丁包，D2026-1029-02 拍板③）。

零行为变化承诺：未装补丁包/无 GPU＝cpu int8 逐字节同路径（缺省 auto）。
半套 DLL 失败注入钉钉住回退分支可达性（否则回退分支硬崩场景不可达）。
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

_RUNNER = (pathlib.Path(__file__).resolve().parent.parent
           / "subtransjav" / "refine" / "asr_runner.py")


def _load_runner_standalone():
    spec = importlib.util.spec_from_file_location("_ct2_runner_device", _RUNNER)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _make_dll_dir(tmp_path, missing: tuple[str, ...] = ()):
    """构造 gpu-dll 目录：默认全 10 件齐全，missing 指定缺件（半套注入）。"""
    from subtransjav.refine.asr_runner import GPU_DLL_REQUIRED
    d = tmp_path / "gpu-dll"
    d.mkdir()
    for name in GPU_DLL_REQUIRED:
        if name not in missing:
            (d / name).write_bytes(b"x")
    return str(d)


def test_resolve_auto_without_patch_is_cpu_int8(tmp_path):
    """缺省 auto 无补丁包＝cpu int8（零行为变化承诺钉）。"""
    mod = _load_runner_standalone()
    dev, ct, _ = mod.resolve_device("auto", "", 0, None)
    assert (dev, ct) == ("cpu", "int8")
    dev, ct, _ = mod.resolve_device("auto", "", 2, None)
    assert (dev, ct) == ("cpu", "int8"), "无补丁目录即使 CUDA 可见也不得走 gpu"


def test_resolve_auto_full_patch_with_cuda_is_gpu(tmp_path):
    """补丁齐全∧CUDA 可见→gpu(int8_float16)（拍板③正路径）。"""
    mod = _load_runner_standalone()
    d = _make_dll_dir(tmp_path)
    dev, ct, note = mod.resolve_device("auto", d, 1, None)
    assert (dev, ct) == ("gpu", "int8_float16")
    assert "双检通过" in note


def test_resolve_half_dll_falls_back_cpu(tmp_path):
    """半套 DLL 失败注入钉：缺任一子件→cpu 回退（分支可达性）。"""
    mod = _load_runner_standalone()
    d = _make_dll_dir(tmp_path, missing=("cudnn_ops64_9.dll",))
    dev, ct, note = mod.resolve_device("auto", d, 4, None)
    assert (dev, ct) == ("cpu", "int8")
    assert "cudnn_ops64_9.dll" in note
    d2 = tmp_path / "gpu-dll2"
    d2.mkdir()
    from subtransjav.refine.asr_runner import GPU_DLL_REQUIRED as _req
    for name in _req:
        if name not in ("cublas64_12.dll", "cublasLt64_12.dll"):
            (d2 / name).write_bytes(b"x")
    dev, ct, note = mod.resolve_device("auto", str(d2), 4, None)
    assert (dev, ct) == ("cpu", "int8")
    assert "cublas" in note


def test_resolve_no_cuda_device_falls_back_cpu(tmp_path):
    """补丁齐全但无 CUDA 设备→cpu 回退。"""
    mod = _load_runner_standalone()
    d = _make_dll_dir(tmp_path)
    dev, ct, _ = mod.resolve_device("auto", d, 0, None)
    assert (dev, ct) == ("cpu", "int8")


def test_resolve_explicit_cpu_and_compute_type_respected(tmp_path):
    """显式 cpu 恒 cpu；显式 compute_type 不被改写（含 gpu 正路径）。"""
    mod = _load_runner_standalone()
    d = _make_dll_dir(tmp_path)
    assert mod.resolve_device("cpu", d, 2, "float16")[:2] == ("cpu", "float16")
    assert mod.resolve_device("auto", d, 2, "int8")[:2] == ("gpu", "int8")
    assert mod.resolve_device("cpu", "", 0, "int8")[:2] == ("cpu", "int8")


def test_resolve_forced_gpu_with_incomplete_patch_falls_back(tmp_path):
    """显式 gpu 但检测不过也回退 cpu（拍板③：失败→cpu 回退）。"""
    mod = _load_runner_standalone()
    dev, ct, _ = mod.resolve_device("gpu", "", 8, None)
    assert (dev, ct) == ("cpu", "int8")


def test_load_model_gpu_failure_falls_back_cpu(tmp_path, monkeypatch):
    """双检③真用检：gpu 装载抛异常→cpu int8 回退（半套/驱动炸场景）。"""
    mod = _load_runner_standalone()

    class FakeModel:
        def __init__(self, model_dir, device, compute_type):
            self.device = device
            self.compute_type = compute_type
            if device == "cuda":
                raise RuntimeError("cuda DLL load failure (injected)")

    fake = types.ModuleType("faster_whisper")
    fake.WhisperModel = FakeModel
    monkeypatch.setitem(sys.modules, "faster_whisper", fake)
    model, dev, ct = mod._load_model(str(tmp_path), "gpu", "int8_float16")
    assert dev == "cpu" and ct == "int8"
    assert model.device == "cpu"

    model, dev, ct = mod._load_model(str(tmp_path), "cpu", "int8")
    assert dev == "cpu" and ct == "int8" and model.device == "cpu"


def test_gpu_dll_required_list_shape():
    """必需清单形状钉：cublas 两件＋cudnn 主八子，防清单漂移。"""
    from subtransjav.refine.asr_runner import GPU_DLL_REQUIRED
    assert len(GPU_DLL_REQUIRED) == 10
    assert "cublas64_12.dll" in GPU_DLL_REQUIRED
    assert "cudnn_ops64_9.dll" in GPU_DLL_REQUIRED
