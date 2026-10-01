"""ASR 重转写运行器（2.6.0 批 3 路线 B）：由上游环境 Python 执行。

调用形态（本仓 GUI/CLI 侧 asr_env 组装）：
  {上游 python} -m subtransjav.refine.asr_runner --audio <wav> \
      --model large-v2 --language ja
  {上游 python} -m subtransjav.refine.asr_runner --selfcheck --model large-v2

- 本模块由上游环境（如 D:\\whisperJAV，Python 3.10）以 -m 方式执行：
  **顶部仅标准库导入**（D2026-1002-04-批3 C3 导入图钉，测试静态钉），
  whisper 在转写/自检函数内懒加载——本仓包 requires-python>=3.10 与
  上游 3.10 自洽，导入链全部标准库；
- stdout 输出单行 JSON（唯一机器契约）：
  {"ok": true, "text": ..., "segments": [{start,end,text}...]} /
  {"ok": false, "error": ...} / {"ok": true, "info": {...}}（selfcheck）；
  诊断信息走 stderr，不进机器契约；
- --selfcheck（C2）：导入链 + whisper 可导入 + 模型缓存定位（不实际加载
  模型）——探测假阳性防线：import whisper 成功 ≠ 运行器可导入 ≠ 模型在位。
"""

import argparse
import json
import os
import sys


def _selfcheck(model: str) -> int:
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
    info["model_path"] = os.path.join(cache, f"{model}.pt")
    info["model_present"] = os.path.isfile(info["model_path"])
    print(json.dumps({"ok": True, "info": info}, ensure_ascii=False))
    return 0


def _run_transcribe(audio: str, model: str, language: str) -> int:
    try:
        import whisper
    except Exception as e:   # noqa: BLE001
        print(json.dumps({"ok": False,
                          "error": f"whisper 导入失败: {e}"},
                         ensure_ascii=False))
        return 1
    try:
        result = whisper.transcribe(audio, model=model, language=language,
                                    verbose=False)
    except Exception as e:   # noqa: BLE001 转写失败按段降级
        print(json.dumps({"ok": False, "error": f"转写失败: {e}"},
                         ensure_ascii=False))
        return 1
    segments = [{"start": float(s.get("start") or 0.0),
                 "end": float(s.get("end") or 0.0),
                 "text": str(s.get("text") or "")}
                for s in (result.get("segments") or [])
                if isinstance(s, dict)]
    print(json.dumps({"ok": True, "text": str(result.get("text") or ""),
                      "segments": segments}, ensure_ascii=False))
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="asr_runner",
        description="本地 ASR 重转写运行器（上游环境 Python 执行）")
    parser.add_argument("--audio", default="", help="待转写音频片段路径")
    parser.add_argument("--model", default="large-v2",
                        help="whisper 模型名（~/.cache/whisper/<name>.pt）")
    parser.add_argument("--language", default="ja")
    parser.add_argument("--selfcheck", action="store_true",
                        help="自检：导入链+whisper 可导入+模型缓存定位")
    args = parser.parse_args(argv)
    if args.selfcheck:
        return _selfcheck(args.model)
    if not args.audio or not os.path.isfile(args.audio):
        print(json.dumps({"ok": False,
                          "error": f"音频不存在: {args.audio}"},
                         ensure_ascii=False))
        return 2
    return _run_transcribe(args.audio, args.model, args.language)


if __name__ == "__main__":
    sys.exit(main())
