"""ASR 重转写运行器（2.6.0 批 3 路线 B）：由上游环境 Python 执行。

调用形态（本仓 GUI/CLI 侧 asr_env 组装）：
  {上游 python} -m subtransjav.refine.asr_runner --audio <wav> \
      --model large-v2 --language ja [--model-dir <dir>]
  {上游 python} -m subtransjav.refine.asr_runner --clips-json <json> \
      --model large-v2 --language ja [--model-dir <dir>]
  {上游 python} -m subtransjav.refine.asr_runner --selfcheck --model large-v2 \
      [--model-dir <dir>]

- 本模块由上游环境（如 D:\\whisperJAV，Python 3.10）以 -m 方式执行：
  **顶部仅标准库导入**（D2026-1002-04-批3 C3 导入图钉，测试静态钉），
  whisper 在转写/自检函数内懒加载——本仓包 requires-python>=3.10 与
  上游 3.10 自洽，导入链全部标准库；
- stdout 输出单行 JSON（唯一机器契约）：
  {"ok": true, "text": ..., "segments": [{start,end,text}...]} /
  {"ok": false, "error": ...} / {"ok": true, "info": {...}}（selfcheck）；
  3.0 批3（D2026-1009-02 批3 3A）：单模式 segments 追加透传置信字段
  no_speech_prob/avg_logprob/compression_ratio（C13，此前丢弃；仅增键
  不改既有键，消费方按存在性读取不受影响）；新增 --clips-json 多段模式
  （C17 批量转写：单次进程 load_model 一次→逐 clip transcribe），输出
  {"ok": true, "language": ..., "device": "cuda|cpu", "clips": [
    {"timing": ..., "segments": [{start,end,text,no_speech_prob,
    avg_logprob,compression_ratio}...], "text_all": ...}]}；clips 为空
  列表时**不加载模型**直接返回 device（调用侧的零成本设备探测通道）；
  诊断信息走 stderr，不进机器契约；
- --selfcheck（C2）：导入链 + whisper 可导入 + 模型缓存定位（不实际加载
  模型）——探测假阳性防线：import whisper 成功 ≠ 运行器可导入 ≠ 模型在位。
- --model-dir（2.6.1 修订 D2026-1002-06，可选）：自定义模型目录（数据根
  models/asr/ 等）。给了则 model_present 判定与转写加载都指向该目录；
  不给则维持 ~/.cache/whisper 原生行为——探测与加载同序（评议员指出的
  契约错位修正：探测枚举两处、加载只认一处=假阳性源头）。
"""

import argparse
import json
import os
import sys

# 2.7.1 热修（本机实测复现）：脚本直调形态下 sys.path[0]=脚本所在目录
# （refine/），目录内 secrets.py 与标准库 secrets 同名——上游 whisper 导入
# 链的 `import secrets` 被劫持（refine/secrets.py 顶部 `from subtransjav
# import paths` 在上游 env 无包必炸 → "No module named 'subtransjav'"）。
# runner 自包含、不依赖其自身所在目录任何内容，把该目录从 sys.path 移除
# （仅用 os/sys，C3 顶部标准库导入图钉不变）；-m/包形态导入时该目录本就
# 不在 sys.path（或移除无害），行为不变。
_here = os.path.dirname(os.path.abspath(__file__))
sys.path[:] = [p for p in sys.path
               if os.path.abspath(p or os.getcwd()) != _here]

# CI win runner（cp1252 缺省）print 中文 JSON 崩 UnicodeEncodeError：
# runner 的 stdout/stderr 契约是纯 ASCII 安全的 JSON+上游可读文本，强制
# UTF-8 重裹（仅用 sys，标准库导入图钉不变）。错误文本（含中文注释引用）
# 也经此通道安全输出。
for _stream_name in ("stdout", "stderr"):
    _stream = getattr(sys, _stream_name)
    if (hasattr(_stream, "reconfigure")
            and getattr(_stream, "encoding", "").lower() not in ("utf-8", "utf8")):
        _stream.reconfigure(encoding="utf-8", errors="replace")


def _selfcheck(model: str, model_dir: str = "") -> int:
    info: dict = {"python": sys.version.split()[0], "cwd": os.getcwd()}
    try:
        import whisper  # noqa: F401 懒加载：仅上游环境可导入
        info["whisper_version"] = str(getattr(whisper, "__version__", "")
                                      or "unknown")
    except Exception as e:   # noqa: BLE001 探测降级
        print(json.dumps({"ok": False,
                          "error": f"whisper 导入失败: {e}"},
                         ensure_ascii=False))
        return 1
    cache = os.path.join(os.path.expanduser("~"), ".cache", "whisper")
    # 2.6.1 修订（D2026-1002-06）：给了 model_dir 则查 <model_dir>/<model>.pt
    # （与转写加载同序）；否则维持 ~/.cache/whisper 原生行为。
    info["model_dir"] = model_dir
    info["model_path"] = (os.path.join(model_dir, f"{model}.pt")
                          if model_dir
                          else os.path.join(cache, f"{model}.pt"))
    info["model_present"] = os.path.isfile(info["model_path"])
    print(json.dumps({"ok": True, "info": info}, ensure_ascii=False))
    return 0


def _detect_device() -> str:
    """探测推理设备（cuda|cpu）：torch 可导入且 CUDA 可用→cuda。

    torch 缺失/探测失败一律保守回退 cpu（调用侧据此做无 GPU 分批上限，
    探测失败按 cpu 处理不会更激进，方向安全）。仅标准库导入图钉不变：
    torch 在本函数内懒加载。"""
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:   # noqa: BLE001 设备探测降级
        return "cpu"


# 单段 segment 透传字段（C13）：start/end/text 既有三键 + 置信三维键。
# openai-whisper segment dict 自带下列置信键（缺键保守取 None，消费方
# 按存在性读取——老 fork 无键时不误判）。
_SEGMENT_KEYS = ("start", "end", "text", "no_speech_prob", "avg_logprob",
                 "compression_ratio")
_SEGMENT_FLOAT_KEYS = ("start", "end", "no_speech_prob", "avg_logprob",
                       "compression_ratio")


def _dump_segment(s: dict) -> dict:
    """openai-whisper segment dict → 契约 segment dict（C13 置信透传）。"""
    out: dict = {"text": str(s.get("text") or "")}
    for k in _SEGMENT_FLOAT_KEYS:
        v = s.get(k)
        try:
            out[k] = float(v) if v is not None else None
        except (TypeError, ValueError):
            out[k] = None
    return out


def _run_transcribe(audio: str, model: str, language: str,
                    model_dir: str = "") -> int:
    try:
        import whisper
    except Exception as e:   # noqa: BLE001
        print(json.dumps({"ok": False,
                          "error": f"whisper 导入失败: {e}"},
                         ensure_ascii=False))
        return 1
    try:
        # 2.6.1 修订（D2026-1002-06）：显式 load_model（download_root 仅在
        # 自定义目录时传；缺省 None=原生 ~/.cache/whisper 行为不变）——
        # 比 transcribe 透传 kwarg 对 fork 版本差异更稳（评议员建议）。
        model_obj = whisper.load_model(
            model, download_root=model_dir or None)
        result = model_obj.transcribe(audio, language=language,
                                      verbose=False)
    except Exception as e:   # noqa: BLE001 转写失败按段降级
        print(json.dumps({"ok": False, "error": f"转写失败: {e}"},
                         ensure_ascii=False))
        return 1
    # 3.0 批3（C13）：segments 追加透传置信字段（同款键，多段模式一致）
    segments = [_dump_segment(s)
                for s in (result.get("segments") or [])
                if isinstance(s, dict)]
    print(json.dumps({"ok": True, "text": str(result.get("text") or ""),
                      "segments": segments}, ensure_ascii=False))
    return 0


def _run_transcribe_clips(clips_json: str, model: str, language: str,
                          model_dir: str = "") -> int:
    """多段模式（C17 批量转写）：单次进程 load_model 一次→逐 clip 转写。

    clips-json 文件内容＝[{"clip": path, "timing": str}, ...]。空列表
    时不加载模型直接返回 device（调用侧零成本设备探测通道）。逐 clip
    失败如实标记（该 clip segments=[]/text_all="" + error），不静默。"""
    try:
        with open(clips_json, encoding="utf-8") as f:
            items = json.load(f)
    except (OSError, ValueError) as e:
        print(json.dumps({"ok": False,
                          "error": f"clips-json 读取失败: {e}"},
                         ensure_ascii=False))
        return 2
    if not isinstance(items, list):
        print(json.dumps({"ok": False,
                          "error": "clips-json 内容须为数组"},
                         ensure_ascii=False))
        return 2
    device = _detect_device()
    out_clips: list[dict] = []
    model_obj = None       # C17：load_model 提到循环只执行一次（首个
    loaded_model = False   # 有效 clip 触发），空列表/全坏列表不装载。
    for it in items:
        if not isinstance(it, dict):
            out_clips.append({"timing": "", "segments": [], "text_all": "",
                              "error": "clips-json 条目须为对象"})
            continue
        clip_path = str(it.get("clip") or "")
        timing = str(it.get("timing") or "")
        if not clip_path or not os.path.isfile(clip_path):
            out_clips.append({"timing": timing, "segments": [],
                              "text_all": "",
                              "error": f"音频不存在: {clip_path}"})
            continue
        try:
            import whisper
            if not loaded_model:
                model_obj = whisper.load_model(
                    model, download_root=model_dir or None)
                loaded_model = True
            result = model_obj.transcribe(
                clip_path, language=language, verbose=False)
        except Exception as e:   # noqa: BLE001 逐 clip 降级不静默
            out_clips.append({"timing": timing, "segments": [],
                              "text_all": "",
                              "error": f"转写失败: {e}"})
            continue
        segs = [_dump_segment(s)
                for s in (result.get("segments") or [])
                if isinstance(s, dict)]
        out_clips.append({"timing": timing, "segments": segs,
                          "text_all": str(result.get("text") or ""),
                          "error": ""})
    print(json.dumps({"ok": True, "language": language, "device": device,
                      "clips": out_clips}, ensure_ascii=False))
    return 0


# ===================== ct2 后端（3.2.0，D2026-1028-03） =====================
# 运行环境=自管 CT2 运行时（asr_runtime 安装链），本文件在该解释器下以脚本
# 直调执行（自包含、不依赖 subtransjav 包）。四旋钮缺省全部 PROVISIONAL，
# 最终缺省组合待金标逐一 A/B 后预注册定案（评议员修正项）。

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


def _run_transcribe_media_ct2(media: str, model_dir: str, language: str,
                              srt_out: str, *, beam_size: int,
                              vad_filter: bool, condition_previous: bool,
                              compute_type: str = "int8",
                              line_break: bool = True) -> int:
    """ct2 整片转写：SRT＋词级 sidecar（断行器 3.2.1 的消费输入）。

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
        from faster_whisper import WhisperModel
    except Exception as e:   # noqa: BLE001
        print(json.dumps({"ok": False,
                          "error": "faster_whisper 导入失败（CT2 运行时未安装"
                                   "或损坏，先运行 python -m "
                                   "subtransjav.refine.asr_runtime install）: "
                                   + str(e)},
                         ensure_ascii=False))
        return 1
    try:
        # device 钉 cpu（骨架期）：ct2 wheel 对半套 CUDA DLL（如系统 PATH 残留
        # cublas）会 auto 探测后加载失败——GPU 通道归后续批（DLL 集齐+双检，
        # 沿 NVENC 双检先例），CPU int8 RTF≈0.98x 已实测可用。
        model_obj = WhisperModel(model_dir, device="cpu", compute_type=compute_type)
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
    except Exception as e:   # noqa: BLE001 转写失败按契约返回
        print(json.dumps({"ok": False,
                          "error": "ct2 转写失败: " + str(e)},
                         ensure_ascii=False))
        return 1
    import pathlib
    out_path = pathlib.Path(srt_out)
    if out_path.parent and str(out_path.parent):
        out_path.parent.mkdir(parents=True, exist_ok=True)
    # 断行器接入（3.2.1，D2026-1028-03）：词级时间戳+CPS+停顿确定性切分，
    # 缺省开（社区实证 CT2 长行问题）；--no-line-break 关闭走原生段。
    # sidecar 始终保留原始词级数据（断行器输入可回放）。
    srt_segments = segs
    if line_break and any(len(s.get("words") or []) >= 2 for s in segs):
        try:
            from .line_breaker import break_segments
            srt_segments = break_segments(segs)
        except Exception:   # noqa: BLE001 断行故障不阻断转写产出
            srt_segments = segs
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


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="asr_runner",
        description="本地 ASR 重转写运行器（上游环境 Python 执行）")
    parser.add_argument("--audio", default="", help="待转写音频片段路径")
    # 3.0 批3（C17）：多段模式入口，与 --audio 互斥（clips-json=[
    # {"clip": path, "timing": str}, ...]）。
    parser.add_argument("--clips-json", default="",
                        help="多段模式：clip 清单 json 路径（与 --audio 互斥）")
    parser.add_argument("--model", default="large-v2",
                        help="whisper 模型名（~/.cache/whisper/<name>.pt）")
    parser.add_argument("--model-dir", default="",
                        help="自定义模型目录（给了则探测/加载均指向该目录；"
                             "缺省=原生 ~/.cache/whisper）")
    parser.add_argument("--language", default="ja")
    parser.add_argument("--selfcheck", action="store_true",
                        help="自检：导入链+whisper 可导入+模型缓存定位")
    # ---- 3.2.0 ct2 后端（缺省 whisper=零行为变化）----
    parser.add_argument("--engine", default="whisper", choices=["whisper", "ct2"],
                        help="转写引擎（缺省 whisper=既有链零变化）")
    parser.add_argument("--media", default="",
                        help="ct2 整片模式：媒体路径（与 --audio/--clips-json 互斥）")
    parser.add_argument("--srt-out", default="",
                        help="ct2 整片模式：SRT 输出路径（同时产 .words.json sidecar）")
    parser.add_argument("--beam-size", type=int, default=5,
                        help="ct2 束宽（PROVISIONAL，待金标 A/B 定案）")
    parser.add_argument("--no-vad-filter", action="store_true",
                        help="ct2 关闭 Silero VAD（PROVISIONAL；缺省开）")
    parser.add_argument("--condition-previous", action="store_true",
                        help="ct2 开启 condition_on_previous_text"
                             "（PROVISIONAL；缺省关=幻听缓解）")
    parser.add_argument("--compute-type", default="int8",
                        help="ct2 量化形态（PROVISIONAL；CPU int8/GPU float16）")
    parser.add_argument("--no-line-break", action="store_true",
                        help="ct2 关闭确定性断行（缺省开=长行自动切分）")
    args = parser.parse_args(argv)
    if args.selfcheck:
        return _selfcheck(args.model, args.model_dir)
    if args.engine == "ct2":
        if args.audio or args.clips_json:
            print(json.dumps({"ok": False,
                              "error": "--engine ct2 整片模式与 "
                                       "--audio/--clips-json 互斥"},
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
            line_break=not args.no_line_break)
    if args.media or args.srt_out:
        print(json.dumps({"ok": False,
                          "error": "--media/--srt-out 仅在 --engine ct2 下可用"},
                         ensure_ascii=False))
        return 2
    if args.clips_json:
        if args.audio:
            print(json.dumps({"ok": False,
                              "error": "--audio 与 --clips-json 互斥"},
                             ensure_ascii=False))
            return 2
        if not os.path.isfile(args.clips_json):
            print(json.dumps({"ok": False,
                              "error": f"clips-json 不存在: "
                                       f"{args.clips_json}"},
                             ensure_ascii=False))
            return 2
        return _run_transcribe_clips(args.clips_json, args.model,
                                     args.language, args.model_dir)
    if not args.audio or not os.path.isfile(args.audio):
        print(json.dumps({"ok": False,
                          "error": f"音频不存在: {args.audio}"},
                         ensure_ascii=False))
        return 2
    return _run_transcribe(args.audio, args.model, args.language,
                           args.model_dir)


if __name__ == "__main__":
    sys.exit(main())
