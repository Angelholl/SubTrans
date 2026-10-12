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
    args = parser.parse_args(argv)
    if args.selfcheck:
        return _selfcheck(args.model, args.model_dir)
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
