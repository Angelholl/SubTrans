"""ASR 重转写运行器（2.6.0 批 3 路线 B）：由上游环境 Python 执行。

调用形态（本仓 GUI/CLI 侧 asr_env 组装）：
  {上游 python} -m subtransjav.refine.asr_runner --audio <wav> \
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
    parser.add_argument("--model-dir", default="",
                        help="自定义模型目录（给了则探测/加载均指向该目录；"
                             "缺省=原生 ~/.cache/whisper）")
    parser.add_argument("--language", default="ja")
    parser.add_argument("--selfcheck", action="store_true",
                        help="自检：导入链+whisper 可导入+模型缓存定位")
    args = parser.parse_args(argv)
    if args.selfcheck:
        return _selfcheck(args.model, args.model_dir)
    if not args.audio or not os.path.isfile(args.audio):
        print(json.dumps({"ok": False,
                          "error": f"音频不存在: {args.audio}"},
                         ensure_ascii=False))
        return 2
    return _run_transcribe(args.audio, args.model, args.language,
                           args.model_dir)


if __name__ == "__main__":
    sys.exit(main())
