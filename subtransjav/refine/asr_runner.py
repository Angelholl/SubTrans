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
  定案（评议员修正项）。
"""

import argparse
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
    parser.add_argument("--no-line-break", action="store_true",
                        help="ct2 关闭确定性断行（缺省开=长行自动切分）")
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
        line_break=not args.no_line_break)


if __name__ == "__main__":
    sys.exit(main())
