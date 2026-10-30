"""本地 ASR 重转写运行器（CT2 引擎，3.2.0；唯一引擎，D2026-1029-01 退役批）。

调用形态（本仓 GUI/CLI 侧 asr_env/asr_runtime 组装；CT2 自管运行时
解释器执行）：
  {运行时 python} <asr_runner.py> --engine ct2 --media <媒体> \
      --srt-out <srt> --model-dir <模型目录> [--language ja] [旋钮...]

- 本模块在 CT2 运行时解释器下以脚本直调执行：**顶部仅标准库导入**
  （D2026-1002-04-批3 C3 导入图钉，测试静态钉），faster_whisper 在转写
  函数内懒加载——导入链全部标准库；
- stdout 输出单行 JSON（唯一机器契约）：
  {"ok": true, "srt": ..., "segments": [{start, end, text, words,
  no_speech_prob, avg_logprob, compression_ratio}...], "duration": ...,
  "words_sidecar": ...} / {"ok": false, "error": ...}。
  segments 为完整段数组（D2026-1029-01 批1 置信透传：三维置信键
  None 安全，消费方按存在性读取）；诊断信息走 stderr，不进机器契约；
- 词级 sidecar（schema subtransjav.ct2.words/1）始终保留原始词级数据
  （断行器 3.2.1 的消费输入与回放源）；
- 四旋钮缺省全部 PROVISIONAL，最终缺省组合待金标逐一 A/B 后预注册
  定案（评议员修正项）；
- ``--passes {1,2}``（3.2.0 件A，D2026-1029-02 拍板①）：缺省 1=单 pass
  现状零行为变化；2=pass1 精准档＋pass2 召回档双 pass 覆盖合并，另留
  pass1/pass2 中间件与 dualpass sidecar（缺省翻转归评测门后拍板，本处
  不翻）。
"""

import argparse
import contextlib
import json
import os
import sys

# 2.7.1 热修（本机实测复现）：脚本直调形态下 sys.path[0]=脚本所在目录
# （refine/），目录内 secrets.py 与标准库 secrets 同名——第三方导入链的
# `import secrets` 被劫持（refine/secrets.py 顶部 `from subtransjav
# import paths` 在运行时解释器无包必炸 → "No module named 'subtransjav'"）。
# runner 自包含、不依赖其自身所在目录任何内容，把该目录从 sys.path 移除
# （仅用 os/sys，C3 顶部标准库导入图钉不变）。
_here = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path
               if os.path.abspath(p or os.getcwd()) != _here]

# CI win runner（cp1252 缺省）print 中文 JSON 崩 UnicodeEncodeError：
# runner 的 stdout/stderr 契约是纯 ASCII 安全的 JSON+可读文本，强制
# UTF-8 重裹（仅用 sys，标准库导入图钉不变）。错误文本（含中文注释引用）
# 也经此通道安全输出。
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name)
    if (hasattr(_stream, "reconfigure")
            and getattr(_stream, "encoding", "").lower() not in ("utf-8", "utf8")):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _opt_float(v) -> float | None:
    """可选浮点规整（None 安全；非数值保守取 None，消费方按存在性读取）。"""
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _segments_to_srt(segments: list) -> str:
    """ct2 segment list → SRT 文本（纯函数；时间戳钳非负）。"""

    def fmt(t: float) -> str:
        if t < 0:
            t = 0.0
        ms = int(round(t * 1000))
        h, rem = divmod(ms, 3600000)
        m, rem = divmod(rem, 60000)
        s, ms2 = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{s:02d},{ms2:03d}"

    out = []
    for i, seg in enumerate(segments, 1):
        out.append(str(i))
        out.append(f"{fmt(float(seg['start']))} --> {fmt(float(seg['end']))}")
        out.append(str(seg.get("text") or "").strip())
        out.append("")
    return "\n".join(out)


# GPU DLL 补丁包必需清单（D2026-1029-02 拍板③；勘探卡
# d1029-件B-GPU补丁包-勘探卡.md §2）：cublas 两件（CT2 wheel 不带）＋
# cudnn 主件与八子件（CT2 wheel 只带主分发器）。缺任一=补丁不完整→
# cpu 回退（半套 DLL 注入钉钉住该分支可达性）。
GPU_DLL_REQUIRED = (
    "cublas64_12.dll", "cublasLt64_12.dll",
    "cudnn64_9.dll", "cudnn_adv64_9.dll", "cudnn_cnn64_9.dll",
    "cudnn_engines_precompiled64_9.dll",
    "cudnn_engines_runtime_compiled64_9.dll",
    "cudnn_graph64_9.dll", "cudnn_heuristic64_9.dll",
    "cudnn_ops64_9.dll",
)
GPU_COMPUTE_TYPE = "int8_float16"   # 拍板③：可用→gpu(int8_float16)
CPU_COMPUTE_TYPE = "int8"           # 现状缺省，零行为变化

# 双 pass 召回档（预注册常量，D2026-1029-02 拍板①；数值出处＝内部追记
# d1028-40-追记-件A-pass2预注册，禁临时调参）：pass2=vad_filter 关＋
# beam_size 8，其余同 pass1（condition_on_previous_text 随 pass1、
# word_timestamps 恒开）。
PASS2_BEAM_SIZE = 8
PASS2_VAD_FILTER = False


def gpu_dll_missing(gpu_dll_dir: str) -> list[str]:
    """补丁包 DLL 完整性检查（双检①）：返回缺失清单（空=齐全）。"""
    if not gpu_dll_dir or not os.path.isdir(gpu_dll_dir):
        return list(GPU_DLL_REQUIRED)
    return [d for d in GPU_DLL_REQUIRED
            if not os.path.isfile(os.path.join(gpu_dll_dir, d))]


def resolve_device(device: str, gpu_dll_dir: str, cuda_count: int,
                   compute_type: str | None) -> tuple[str, str, str]:
    """device 解析（纯函数，双检②在调用方注入 cuda_count）。

    返回 (device, compute_type, note)。auto：DLL 齐全∧cuda_count>0 →
    gpu(int8_float16)；否则 cpu(int8)。显式 cpu 恒 cpu。显式 gpu 但检测
    不过也回退 cpu（拍板③：失败→cpu 回退）。compute_type 显式传入则
    尊重用户值不改写。note=解析说明（stderr 诊断用，不进机器契约）。"""
    missing = gpu_dll_missing(gpu_dll_dir)
    explicit_ct = compute_type
    if device == "cpu":
        return ("cpu", explicit_ct or CPU_COMPUTE_TYPE, "device=cpu 显式指定")
    if missing:
        head = "、".join(missing[:3])
        tail = f" 等 {len(missing)} 件" if len(missing) > 3 else ""
        return ("cpu", explicit_ct or CPU_COMPUTE_TYPE,
                "gpu 补丁不完整（缺 " + head + tail + "）→cpu 回退")
    if cuda_count <= 0:
        return ("cpu", explicit_ct or CPU_COMPUTE_TYPE,
                "无可用 CUDA 设备→cpu 回退")
    return ("gpu", explicit_ct or GPU_COMPUTE_TYPE, "gpu 双检通过")


def _load_model(model_dir: str, device: str, compute_type: str,
                gpu_dll_dir: str = ""):
    """装载 WhisperModel：gpu 装载失败→cpu 回退（拍板③，双检③真用检）。

    回退时 stderr 明示（诊断不进 stdout 机器契约）。返回 (model, device,
    compute_type)——回退后 device/compute_type 为实际生效值。"""
    from faster_whisper import WhisperModel
    if device != "gpu":
        return (WhisperModel(model_dir, device="cpu",
                             compute_type=compute_type), "cpu", compute_type)
    # DLL 目录自行注册（双检①之外的装载保险）：父链（asr_env PATH 注入）
    # 缺席的直调形态也能解析补丁 DLL；两通道均失败则走下方 cpu 回退。
    if gpu_dll_dir and os.path.isdir(gpu_dll_dir):
        with contextlib.suppress(OSError):
            os.add_dll_directory(gpu_dll_dir)
        os.environ["PATH"] = gpu_dll_dir + os.pathsep + os.environ.get("PATH", "")
    try:
        return (WhisperModel(model_dir, device="cuda",
                             compute_type=compute_type), "gpu", compute_type)
    except Exception as e:   # noqa: BLE001 半套 DLL/驱动异常等一律回退
        with contextlib.suppress(Exception):
            print("[asr_runner] gpu 装载失败→cpu 回退: " + str(e),
                  file=sys.stderr)
        return (WhisperModel(model_dir, device="cpu",
                             compute_type=CPU_COMPUTE_TYPE),
                "cpu", CPU_COMPUTE_TYPE)


def _transcribe_segments(model_obj, media: str, language: str, *,
                         beam_size: int, vad_filter: bool,
                         condition_previous: bool):
    """单 pass 转写→(段数组, info)；段含词级＋置信三键（D2026-1029-01）。

    stdout 契约（D2026-1029-01 批1 置信透传）：segments=完整段数组（含
    faster_whisper 原生置信三键 no_speech_prob/avg_logprob/compression_
    ratio，None 安全；此前仅回计数导致消费侧三维置信门静默失效）。"""
    segments_iter, info = model_obj.transcribe(
        media, language=language, beam_size=beam_size,
        vad_filter=vad_filter, condition_on_previous_text=condition_previous,
        word_timestamps=True)
    segs = []
    for s in segments_iter:
        words = []
        for w in (s.words or []):
            if w.start is None or w.end is None:
                continue
            words.append({"start": float(w.start), "end": float(w.end),
                          "word": w.word, "probability": float(w.probability)})
        # 置信三键透传（D2026-1029-01 批1）：faster_whisper segment 原生
        # 属性，None 安全（消费方按存在性读取；getattr 兜底防异常 fork
        # 缺属性）。
        segs.append({"start": float(s.start), "end": float(s.end),
                     "text": s.text, "words": words,
                     "no_speech_prob": _opt_float(
                         getattr(s, "no_speech_prob", None)),
                     "avg_logprob": _opt_float(
                         getattr(s, "avg_logprob", None)),
                     "compression_ratio": _opt_float(
                         getattr(s, "compression_ratio", None))})
    return segs, info


def _load_pass_merge():
    """双 pass 合并纯函数装载（常规包导入，PyInstaller 静态分析随包）。

    包形态（-m/GUI/测试）相对导入直接可用；无包上下文形态回退绝对包名
    导入。不做文件路径装载、不改 packaging/SubTrans.spec。"""
    try:
        from . import pass_merge
    except ImportError:
        from subtransjav.refine import pass_merge
    return pass_merge


def _write_words_sidecar(path, segs: list, info, model_dir: str, *,
                         beam_size: int, vad_filter: bool,
                         condition_previous: bool) -> str:
    """词级 sidecar（schema subtransjav.ct2.words/1）写盘，返回路径。"""
    sidecar = {"schema": "subtransjav.ct2.words/1", "language": info.language,
               "duration": float(info.duration), "model_dir": model_dir,
               "beam_size": beam_size, "vad_filter": vad_filter,
               "condition_on_previous_text": condition_previous,
               "segments": segs}
    path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=1),
                    encoding="utf-8")
    return str(path)


def _pass_artifact_paths(out_path):
    """双 pass 中间件命名（.pass1.srt/.pass2.srt 族，与分歧采集同源）。"""
    p1 = out_path.with_name(out_path.stem + ".pass1" + out_path.suffix)
    p2 = out_path.with_name(out_path.stem + ".pass2" + out_path.suffix)
    return p1, p2


def _write_dualpass_output(out_path, srt_out: str, segs: list, info,
                           pass2_segs: list, model_dir: str, pm, *,
                           beam_size: int, vad_filter: bool,
                           condition_previous: bool, line_break: bool) -> int:
    """双 pass 产物面（D2026-1029-02 拍板①）。

    主输出=覆盖合并结果（断行器链照常生效）；同目录留痕 pass1/pass2 原生
    段 SRT＋各自词级 sidecar＋``<srt_out>.dualpass.json``（两 pass 原始段
    与词级、各自参数、采纳映射——可回放可审计）。"""
    import pathlib

    merged = pm.merge_passes(segs, pass2_segs, duration=float(info.duration))
    p1_path, p2_path = _pass_artifact_paths(out_path)
    # 中间件保持原生段（留痕/回放源；断行只作用于成品主输出）
    p1_path.write_text(_segments_to_srt(segs), encoding="utf-8", newline="\n")
    p2_path.write_text(_segments_to_srt(pass2_segs), encoding="utf-8",
                       newline="\n")
    p1_side = _write_words_sidecar(
        p1_path.with_suffix(p1_path.suffix + ".words.json"), segs, info,
        model_dir, beam_size=beam_size, vad_filter=vad_filter,
        condition_previous=condition_previous)
    p2_side = _write_words_sidecar(
        p2_path.with_suffix(p2_path.suffix + ".words.json"), pass2_segs, info,
        model_dir, beam_size=PASS2_BEAM_SIZE, vad_filter=PASS2_VAD_FILTER,
        condition_previous=condition_previous)
    srt_segments = _apply_line_break(merged, line_break)
    out_path.write_text(_segments_to_srt(srt_segments), encoding="utf-8",
                        newline="\n")
    main_side = _write_words_sidecar(
        out_path.with_suffix(out_path.suffix + ".words.json"), merged, info,
        model_dir, beam_size=beam_size, vad_filter=vad_filter,
        condition_previous=condition_previous)
    adopted = [{"pass2_index": i,
                "start": float(pass2_segs[i]["start"]),
                "end": float(pass2_segs[i]["end"])}
               for i in pm.adopted_pass2_indices(segs, pass2_segs, merged)]
    dual = {"schema": pm.DUALPASS_SCHEMA, "language": info.language,
            "duration": float(info.duration), "model_dir": model_dir,
            "gap_threshold_s": pm.GAP_THRESHOLD_S, "passes": 2,
            "pass1": {"srt": str(p1_path), "words_sidecar": p1_side,
                      "params": {"beam_size": beam_size,
                                 "vad_filter": vad_filter,
                                 "condition_on_previous_text":
                                     condition_previous,
                                 "word_timestamps": True},
                      "segments": segs},
            "pass2": {"srt": str(p2_path), "words_sidecar": p2_side,
                      "params": {"beam_size": PASS2_BEAM_SIZE,
                                 "vad_filter": PASS2_VAD_FILTER,
                                 "condition_on_previous_text":
                                     condition_previous,
                                 "word_timestamps": True},
                      "segments": pass2_segs},
            "adopted": adopted}
    dual_path = pathlib.Path(str(out_path) + ".dualpass.json")
    dual_path.write_text(json.dumps(dual, ensure_ascii=False, indent=1),
                         encoding="utf-8")
    print(json.dumps({"ok": True, "srt": srt_out, "segments": merged,
                      "duration": float(info.duration),
                      "words_sidecar": main_side,
                      "dualpass_sidecar": str(dual_path), "passes": 2},
                     ensure_ascii=False))
    return 0


def _run_transcribe_media_ct2(media: str, model_dir: str, language: str,
                              srt_out: str, *, beam_size: int,
                              vad_filter: bool, condition_previous: bool,
                              compute_type: str = "int8",
                              line_break: bool = True,
                              device: str = "auto",
                              gpu_dll_dir: str = "",
                              passes: int = 1) -> int:
    """ct2 整片转写：SRT＋词级 sidecar（断行器 3.2.1 的消费输入）。

    ``passes=1``（缺省）=单 pass 现状零行为变化；``passes=2``=双 pass 覆盖
    合并（D2026-1029-02 拍板①，产物面见 ``_write_dualpass_output``）。

    stdout 契约（D2026-1029-01 批1 置信透传）：segments=完整段数组（含
    faster_whisper 原生置信三键 no_speech_prob/avg_logprob/compression_
    ratio，None 安全；此前仅回计数导致消费侧三维置信门静默失效）。"""
    if not model_dir or not os.path.isdir(model_dir):
        print(json.dumps({"ok": False,
                          "error": "ct2 模型目录无效: " + str(model_dir)
                                   + "（调用方经 asr_runtime."
                                     "resolve_ct2_model_dir 解析后传 "
                                     "--model-dir）"},
                         ensure_ascii=False))
        return 2
    if not os.path.isfile(media):
        print(json.dumps({"ok": False,
                          "error": "媒体不存在: " + str(media)},
                         ensure_ascii=False))
        return 2
    try:
        import faster_whisper  # noqa: F401 可用性预检（人话报错先行）
    except Exception as e:   # noqa: BLE001
        print(json.dumps({"ok": False,
                          "error": "faster_whisper 导入失败（CT2 运行时未安装"
                                   "或损坏，先运行 python -m "
                                   "subtransjav.refine.asr_runtime install）: "
                                   + str(e)},
                         ensure_ascii=False))
        return 1
    try:
        # device 选择（件B，D2026-1029-02 拍板③）：auto=双检（补丁 DLL 齐全
        # ∧CUDA 设备可见）→gpu(int8_float16)，否则 cpu 回退；gpu 装载再败
        # →cpu（_load_model 真用检）。未装补丁包/无 GPU＝与现状逐字节同
        # 路径（cpu int8，零行为变化承诺）。
        cuda_count = 0
        if device in ("auto", "gpu"):
            try:
                import ctranslate2
                cuda_count = ctranslate2.get_cuda_device_count()
            except Exception:   # noqa: BLE001 无 ct2/探测失败=无 GPU
                cuda_count = 0
        dev, eff_ct, note = resolve_device(device, gpu_dll_dir, cuda_count,
                                           compute_type)
        if note and note != "device=cpu 显式指定":
            print("[asr_runner] " + note, file=sys.stderr)
        model_obj, dev, eff_ct = _load_model(model_dir, dev, eff_ct,
                                             gpu_dll_dir)
        segs, info = _transcribe_segments(
            model_obj, media, language, beam_size=beam_size,
            vad_filter=vad_filter, condition_previous=condition_previous)
        pass2_segs: list | None = None
        if passes == 2:
            # 双 pass（D2026-1029-02 拍板①）：pass2=召回档预注册常量，其余
            # 同 pass1；缺省单 pass 不触本分支（零行为变化）。
            pass2_segs, _pass2_info = _transcribe_segments(
                model_obj, media, language, beam_size=PASS2_BEAM_SIZE,
                vad_filter=PASS2_VAD_FILTER,
                condition_previous=condition_previous)
    except Exception as e:   # noqa: BLE001 转写失败按契约返回
        print(json.dumps({"ok": False,
                          "error": "ct2 转写失败: " + str(e)},
                         ensure_ascii=False))
        return 1
    import pathlib
    out_path = pathlib.Path(srt_out)
    if out_path.parent and str(out_path.parent):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    if pass2_segs is not None:
        try:
            pm = _load_pass_merge()
        except ImportError as e:   # 无包上下文形态如实报错（不静默降级）
            print(json.dumps({"ok": False,
                              "error": "双 pass 合并件不可用（当前形态无包"
                                       "上下文）: " + str(e)},
                             ensure_ascii=False))
            return 1
        return _write_dualpass_output(
            out_path, srt_out, segs, info, pass2_segs, model_dir, pm,
            beam_size=beam_size, vad_filter=vad_filter,
            condition_previous=condition_previous, line_break=line_break)
    # 断行器接入（3.2.1，D2026-1028-03）：词级时间戳+CPS+停顿确定性切分，
    # 缺省开（社区实证 CT2 长行问题）；--no-line-break 关闭走原生段。
    # sidecar 始终保留原始词级数据（断行器输入可回放）。
    srt_segments = _apply_line_break(segs, line_break)
    out_path.write_text(_segments_to_srt(srt_segments), encoding="utf-8", newline="\n")
    sidecar = {"schema": "subtransjav.ct2.words/1", "language": info.language,
               "duration": float(info.duration), "model_dir": model_dir,
               "beam_size": beam_size, "vad_filter": vad_filter,
               "condition_on_previous_text": condition_previous,
               "segments": segs}
    out_path.with_suffix(out_path.suffix + ".words.json").write_text(
        json.dumps(sidecar, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"ok": True, "srt": srt_out, "segments": segs,
                      "duration": float(info.duration),
                      "words_sidecar": str(out_path) + ".words.json"},
                     ensure_ascii=False))
    return 0


def _apply_line_break(segs: list, line_break: bool) -> list:
    """断行应用＋故障留痕回退（stderr 人话登记，不进机器契约）。"""
    if not line_break or not any(len(s.get("words") or []) >= 2 for s in segs):
        return segs
    try:
        return _load_break_segments()(segs)
    except Exception as e:   # noqa: BLE001 断行故障不阻断转写产出
        # 回退必须留痕：静默降级曾致打包形态缺件缺陷直到冒烟双路径才
        # 拦获（2026-10-29），此处人话登记成因。
        with contextlib.suppress(Exception):
            print("[asr_runner] 断行器失败→SRT 回退原生长行: " + str(e),
                  file=sys.stderr)
        return segs


def _load_break_segments():
    """断行器装载（3.2.1 前置件①，D2026-1029-01 发现登记修复）。

    包上下文（-m/测试形态）走相对导入；脚本直调形态无包上下文必
    ImportError，回退按文件路径装载 line_breaker.py——该件零第三方
    依赖零相对导入，可独立解析。不走 sys.path 注入（refine/ 内
    secrets.py 劫持标准库，见模块顶部热修守卫）。"""
    try:
        from .line_breaker import break_segments
        return break_segments
    except ImportError:
        import importlib.util
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "line_breaker.py")
        spec = importlib.util.spec_from_file_location("_ct2_line_breaker", path)
        if spec is None or spec.loader is None:
            raise
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod.break_segments


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="asr_runner",
        description="本地 ASR 重转写运行器（CT2 运行时解释器执行）")
    # 3.2 退役批（D2026-1029-01）：ct2 唯一引擎；--engine 旗标保留=命令
    # 契约稳定（legacy whisper 后端已硬删）。
    parser.add_argument("--engine", default="ct2", choices=["ct2"],
                        help="转写引擎（ct2 唯一引擎；旗标保留=命令契约稳定）")
    parser.add_argument("--media", default="",
                        help="整片模式：媒体路径")
    parser.add_argument("--srt-out", default="",
                        help="SRT 输出路径（同时产 .words.json sidecar）")
    parser.add_argument("--model-dir", default="",
                        help="ct2 模型目录（asr_runtime.resolve_ct2_model_dir"
                             " 解析后传入）")
    parser.add_argument("--language", default="ja")
    parser.add_argument("--beam-size", type=int, default=5,
                        help="ct2 束宽（PROVISIONAL，待金标 A/B 定案）")
    parser.add_argument("--no-vad-filter", action="store_true",
                        help="ct2 关闭 Silero VAD（PROVISIONAL；缺省开）")
    parser.add_argument("--condition-previous", action="store_true",
                        help="ct2 开启 condition_on_previous_text"
                             "（PROVISIONAL；缺省关=幻听缓解）")
    parser.add_argument("--compute-type", default="int8",
                        help="ct2 量化形态（PROVISIONAL；CPU int8/GPU float16）")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "gpu"],
                        help="计算设备（件B：auto=补丁 DLL 齐全且 CUDA 可见"
                             "→gpu(int8_float16)，否则 cpu；gpu 装载失败自动"
                             "回退 cpu；未装补丁包=cpu 零行为变化）")
    parser.add_argument("--gpu-dll-dir", default="",
                        help="GPU DLL 补丁包目录（gpu-dll；缺省空=未装补丁"
                             "→cpu）")
    parser.add_argument("--no-line-break", action="store_true",
                        help="ct2 关闭确定性断行（缺省开=长行自动切分）")
    parser.add_argument("--passes", type=int, choices=[1, 2], default=1,
                        help="转写遍数（3.2.0 件A：1=单 pass 现状缺省；"
                             "2=pass1 精准档＋pass2 召回档覆盖合并，另留"
                             "中间件与 dualpass sidecar；缺省翻转待评测门）")
    args = parser.parse_args(argv)
    if not args.media:
        print(json.dumps({"ok": False,
                          "error": "--engine ct2 需要 --media"},
                         ensure_ascii=False))
        return 2
    if not args.srt_out:
        print(json.dumps({"ok": False,
                          "error": "--engine ct2 需要 --srt-out"},
                         ensure_ascii=False))
        return 2
    return _run_transcribe_media_ct2(
        args.media, args.model_dir, args.language, args.srt_out,
        beam_size=args.beam_size, vad_filter=not args.no_vad_filter,
        condition_previous=args.condition_previous,
        compute_type=args.compute_type,
        line_break=not args.no_line_break,
        device=args.device, gpu_dll_dir=args.gpu_dll_dir,
        passes=args.passes)


if __name__ == "__main__":
    sys.exit(main())
