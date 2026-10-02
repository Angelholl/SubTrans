"""ASR 环境探测与重转写（2.6.0 批 3 路线 B，D2026-1002-04-批3）。

探测（零写路径，C9 优先级成文）：env ``SUBTRANSJAV_ASR_PYTHON`` >
settings ``asr_python``（调用方传入）> 实测默认
``D:\\whisperJAV\\python.exe``（维护点：owner 机事实，他机经 env/settings
覆盖）> 不可用。探测＝上游 python 子进程 ``--selfcheck``（导入链+whisper
可导入+模型缓存定位，不实际加载模型，C2），超时即杀；模型缓存枚举
``~/.cache/whisper/*.pt``＋数据根 models/asr/*.pt（≥1GB 防半截）。

重转写＝上游 env 子进程（-m asr_runner，stdout JSON 契约），失败逐段降级。
对照块（C6）：≤2000 截断＋ASR 非真值信度声明；纯材料零自动改写。
模型推荐制（2.6.1 修订 D2026-1002-06）：项目不内置下载链；推荐清单
（ASR_RECOMMENDED_MODELS）只给 url/bytes/sha256 等元信息由用户自备；
resolve_model_dir 保证"探测枚举"与"运行加载"同序（缓存 ~/.cache/whisper
原生加载点优先，其次数据根 models/asr/ 经 --model-dir 传入）。

零出域声明：本模块无任何网络上传面；转写全程本地。
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from subtransjav import paths
from subtransjav.utils.subprocess_flags import CREATE_NO_WINDOW  # windowed 防黑框单一来源（批0）

# C9：探测优先级 env > settings（调用方传入）> 实测默认 > 不可用
_UPSTREAM_DEFAULT_PYTHON = r"D:\whisperJAV\python.exe"   # 维护点：owner 机事实
_ASR_PYTHON_ENV = "SUBTRANSJAV_ASR_PYTHON"
_SELFCHECK_TIMEOUT_S = 60
_MODEL_MIN_BYTES = 1024 * 1024 * 1024        # 1GB：防半截下载
_CLIPS_SUBDIR = "media_clips"
_MAX_CLIPS = 20
# 数据根模型目录（原 dict_manager._ASR_MODELS_ROOT 迁入：2.6.1 修订
# D2026-1002-06 删下载链后，模型落位常量归探测/解析侧所有）
ASR_MODELS_ROOT = os.path.normpath(str(paths.data_subdir("models", "asr")))
# 推荐缓存目录（whisper 原生加载点；~/.cache/whisper）
ASR_CACHE_DIR = os.path.normpath(
    os.path.join(os.path.expanduser("~"), ".cache", "whisper"))

# 推荐模型清单（2.6.1 修订 D2026-1002-06：模型推荐制——项目不内置下载链，
# 只给自备元信息。whisper-large-v2 字面量自 dict_manager._ASR_DOWNLOADS
# 迁移（url/bytes/sha256 实测核算值原样保留）；qwen3-asr-1.7b=规划中
# （HF 多文件目录布局，启动前置=HF 布局核实+加载 smoke+二级评议）。
ASR_RECOMMENDED_MODELS: list[dict] = [
    {
        "name": "whisper-large-v2",
        "model": "large-v2",        # whisper 模型名/.pt 文件名主干
        "title": "openai-whisper large-v2（上游同款）",
        "bytes": 3086999982,
        "sha256": ("81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56effd"
                   "0b6a73e524"),
        "url": ("https://openaipublic.azureedge.net/main/whisper/models/"
                "81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18e56effd0b6a"
                "73e524/large-v2.pt"),
        "support": "available",
    },
    {
        "name": "qwen3-asr-1.7b",
        "model": "qwen3-asr-1.7b",
        "title": "Qwen3-ASR-1.7B（HF 多文件目录，规划中）",
        "support": "planned",       # 规划中：无下载字段，用户自备
    },
]


def resolve_model_dir(model_name: str) -> str | None:
    """解析模型加载目录（探测与运行同序；2.6.1 修订 D2026-1002-06）。

    顺序：~/.cache/whisper/<name>.pt 命中→None（原生加载点优先，不传
    旗标）；数据根 models/asr/<name>.pt 命中→返回该目录字符串（运行器
    --model-dir）；都没有→None。"""
    fname = f"{model_name}.pt"
    if (Path(ASR_CACHE_DIR) / fname).is_file():
        return None
    if (Path(ASR_MODELS_ROOT) / fname).is_file():
        return ASR_MODELS_ROOT
    return None


def default_tm_cache_models() -> list[dict]:
    """枚举 ~/.cache/whisper/*.pt＋数据根 models/asr/*.pt（≥1GB 防半截）。"""
    out: list[dict] = []
    seen: set[str] = set()
    homes = [Path(ASR_CACHE_DIR), Path(ASR_MODELS_ROOT)]
    for home in homes:
        if not home.is_dir():
            continue
        for p in sorted(home.glob("*.pt")):
            try:
                size = p.stat().st_size
            except OSError:
                continue
            if size < _MODEL_MIN_BYTES or p.name in seen:
                continue
            seen.add(p.name)
            out.append({"name": p.stem, "path": str(p), "bytes": size})
    return out


def _candidate_pythons(asr_python_setting: str = "") -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    env_p = os.environ.get(_ASR_PYTHON_ENV, "").strip()
    if env_p:
        out.append(("env", env_p))
    setting = (asr_python_setting or "").strip()
    if setting:
        out.append(("settings", setting))
    out.append(("default", _UPSTREAM_DEFAULT_PYTHON))
    return out


def _run_selfcheck(python: str, model: str, model_dir: str = "",
                   timeout: int = _SELFCHECK_TIMEOUT_S) -> tuple[bool, dict]:
    """上游 python 子进程 --selfcheck（C2 真实契约探测）。失败返回 (False, {})."""
    cmd = [python, "-m", "subtransjav.refine.asr_runner",
           "--selfcheck", "--model", model]
    if model_dir:
        cmd.extend(["--model-dir", model_dir])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(paths.app_root()),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=CREATE_NO_WINDOW)  # GUI windowed 防黑框（批0；POSIX=0 无操作）
    except (OSError, subprocess.TimeoutExpired):
        return False, {}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if payload.get("ok"):
            return True, payload.get("info") or {}
        return False, {}
    return False, {}


def probe_asr_env(asr_python_setting: str = "",
                  model: str = "large-v2") -> dict:
    """零写路径探测（available/reason 形态，audio_detect 先例）。

    返回 {available, reason, python, python_source, whisper_version,
    model_present, models, ffmpeg}。"""
    ffmpeg = bool(shutil.which("ffmpeg"))
    models = default_tm_cache_models()
    model_present = any(m["name"] == model for m in models)
    # 探测与加载同序（2.6.1 修订 D2026-1002-06）：selfcheck 也带
    # --model-dir，防"枚举两处/加载一处"假阳性。
    model_dir = resolve_model_dir(model) or ""
    last_err = "无候选上游 Python"
    for source, py in _candidate_pythons(asr_python_setting):
        if not os.path.isfile(py):
            last_err = f"{source}:{py} 不存在"
            continue
        ok, info = _run_selfcheck(py, model, model_dir)
        if ok:
            reason = ("whisper " + str(info.get("whisper_version") or "?")
                      + "｜模型缓存"
                      + ("在位" if info.get("model_present") else "缺失")
                      + "｜ffmpeg " + ("可用" if ffmpeg else "缺失"))
            return {"available": bool(ffmpeg and model_present),
                    "reason": reason,
                    "python": py,
                    "python_source": source,
                    "whisper_version": str(info.get("whisper_version") or ""),
                    "model_present": bool(info.get("model_present")),
                    "models": models,
                    "ffmpeg": ffmpeg}
        last_err = f"{source}:{py} selfcheck 未通过"
    return {"available": False, "reason": last_err, "python": "",
            "python_source": "", "whisper_version": "",
            "model_present": model_present, "models": models,
            "ffmpeg": ffmpeg}


# ---------------------------------------------------------------------------
# 重转写与对照块
# ---------------------------------------------------------------------------

def run_transcription(clip_path: str, asr_python: str = "",
                      model: str = "large-v2", language: str = "ja",
                      timeout: int = 300) -> dict:
    """单片段重转写（上游 env 子进程；JSON 契约解析；失败降级 dict）。

    返回 {"ok": bool, "text": str, "error": str}。"""
    python = ""
    for _src, cand in _candidate_pythons(asr_python):
        if os.path.isfile(cand):
            python = cand
            break
    if not python:
        return {"ok": False, "text": "",
                "error": "上游 ASR Python 不可用（探测降级）"}
    cmd = [python, "-m", "subtransjav.refine.asr_runner",
           "--audio", str(clip_path), "--model", model,
           "--language", language]
    # 探测与加载同序（2.6.1 修订 D2026-1002-06）：数据根落位时显式传
    # --model-dir；缓存命中/都无 → 不传（原生 ~/.cache/whisper 行为）。
    model_dir = resolve_model_dir(model)
    if model_dir:
        cmd.extend(["--model-dir", model_dir])
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(paths.app_root()),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=CREATE_NO_WINDOW)  # GUI windowed 防黑框（批0；POSIX=0 无操作）
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "text": "", "error": f"ASR 子进程失败: {e}"}
    for line in (proc.stdout or "").splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if payload.get("ok"):
            return {"ok": True, "text": str(payload.get("text") or ""),
                    "error": ""}
        return {"ok": False, "text": "",
                "error": str(payload.get("error") or "ASR 失败")}
    return {"ok": False, "text": "",
            "error": f"ASR 运行器无有效输出（rc={proc.returncode}）"}


def build_crosscheck_block(clips: list[dict], asr_python: str = "",
                           model: str = "large-v2",
                           char_limit: int = 2000) -> dict:
    """切片批量重转写并聚合对照块（C6：≤2000 截断+非真值声明）。

    clips 元素＝{path, timing, current}。返回 {"block": str, "segments": n,
    "failed": n}；无可用片段 block=""。"""
    lines: list[str] = [
        "信度声明：以下 ASR 转写文本为本机语音识别输出，非真值（转写可能"
        "自带错误），仅作漏听/误听对照参考；不改变任何默认阈值。"]
    segments = 0
    failed = 0
    for clip in clips:
        r = run_transcription(clip.get("path") or "", asr_python, model)
        if not r["ok"] or not r["text"].strip():
            failed += 1
            lines.append(f"- 段 {clip.get('timing') or clip.get('start')}"
                         f"：ASR 失败（{r['error'][:60]}）")
            continue
        segments += 1
        lines.append(f"- 段 {clip.get('timing') or clip.get('start')}："
                     f"ASR 转写：{r['text'].strip()[:200]}"
                     + (f"（现译：{str(clip.get('current'))[:100]}）"
                        if clip.get("current") else ""))
    if not segments:
        return {"block": "", "segments": 0, "failed": failed}
    block = "\n".join(lines)
    if len(block) > char_limit:
        block = block[:char_limit] + "\n（对照块超长已截断）"
    return {"block": block, "segments": segments, "failed": failed}


def slice_clips(media_path: str, timings: list[str],
                max_clips: int = _MAX_CLIPS) -> dict:
    """按 SRT timing 列表抽 16k 单声道 wav 片段（ffmpeg list-args，无 shell）。

    timings：["HH:MM:SS,mmm --> HH:MM:SS,mmm", ...]（疑似漏听段等），超
    max_clips 截断。落数据根 Temp/media_clips/（sha1 指纹命名，复用
    audio_detect 临时面语义）。返回 {"ok", "clips": [{path, timing}],
    "error", "skipped"}；ffmpeg 缺失/失败逐段降级。"""
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        return {"ok": False, "clips": [], "error": "ffmpeg 不可用",
                "skipped": len(timings)}
    if not os.path.isfile(media_path):
        return {"ok": False, "clips": [], "error": "媒体文件不存在",
                "skipped": len(timings)}
    d = Path(paths.data_subdir("Temp", _CLIPS_SUBDIR))
    d.mkdir(parents=True, exist_ok=True)
    import hashlib
    fingerprint = hashlib.sha256(        # 非加密用途：切片缓存名（Mimosa 建议 sha256）
        f"{media_path}|{sorted(timings)[:max_clips]}".encode()
    ).hexdigest()[:12]

    def _sec(ts: str) -> float:
        hh, mm, rest = ts.split(":")
        ss, ms = rest.split(",")
        return int(hh) * 3600 + int(mm) * 60 + int(ss) + int(ms) / 1000

    clips: list[dict] = []
    skipped = 0
    for timing in timings[:max_clips]:
        try:
            start_s, end_s = timing.split("-->")
            start = _sec(start_s.strip())
            dur = max(0.5, _sec(end_s.strip()) - start)
        except (ValueError, AttributeError):
            skipped += 1
            continue
        out = d / f"clip_{fingerprint}_{len(clips)}.wav"
        try:
            proc = subprocess.run(
                [ffmpeg, "-y", "-ss", f"{start:.3f}", "-t", f"{dur:.3f}",
                 "-i", media_path, "-vn", "-ac", "1", "-ar", "16000",
                 str(out)],
                capture_output=True, encoding="utf-8", errors="replace",
                timeout=120,
                creationflags=CREATE_NO_WINDOW)  # GUI windowed 防黑框（批0；POSIX=0 无操作）
        except (OSError, subprocess.TimeoutExpired):
            skipped += 1
            continue
        if proc.returncode == 0 and out.is_file() \
                and out.stat().st_size > 0:
            clips.append({"path": str(out), "timing": timing})
        else:
            skipped += 1
    return {"ok": bool(clips), "clips": clips,
            "error": "" if clips else "无可用切片", "skipped": skipped}


def cleanup_clips(max_age_s: int = 0) -> int:
    """切片临时目录清理（C8 best-effort，不抛）。"""
    d = Path(paths.data_subdir("Temp", _CLIPS_SUBDIR))
    removed = 0
    if not d.is_dir():
        return 0
    now = time.time()
    for p in d.iterdir():
        try:
            if max_age_s and now - p.stat().st_mtime < max_age_s:
                continue
            p.unlink()
            removed += 1
        except OSError:
            continue
    return removed
