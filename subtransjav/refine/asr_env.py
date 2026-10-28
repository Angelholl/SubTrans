"""转写引擎编排（CT2 唯一引擎，3.2 起唯一引擎；D2026-1029-01 退役批）。

引擎分派（3.2 退役批起 ct2 唯一）：转写＝ct2 自管运行时（数据根按需
安装，asr_runtime 安装链）子进程 stdout JSON 契约；未安装运行时时
如实报错导向安装（「唯一引擎，首次使用需安装」），不影响翻译主链路。
legacy whisper 后端与其上游环境链已硬删（输入兼容面在 asr_meta：
历史产物 SRT/run.json/遥测旁车照常可读）。

2.7.1（D2026-1005-01 承接批）：运行器脚本路径直调（_runner_script_path
随包定位 + spec datas 单文件；asr_runtime ct2 链消费）；ffmpeg 探测
（resolve_ffmpeg，PATH 解析，抽片 subprocess 显式传绝对路径）。
对照块（C6）：≤2000 截断＋ASR 非真值信度声明；纯材料零自动改写。
ct2 置信透传（D2026-1029-01 批1）：runner stdout segments 含三维置信
键（no_speech_prob/avg_logprob/compression_ratio），中转层优先读
stdout 段（SRT 解析降级兜底）——漏听二级三维置信门恢复生效。

零出域声明：本模块无任何网络上传面；转写全程本地。
"""

import contextlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from subtransjav import paths
from subtransjav.utils.subprocess_flags import CREATE_NO_WINDOW  # windowed 防黑框单一来源（批0）

# 引擎分派（3.2 退役批 ct2 唯一）：legacy whisper 候选链（env/settings）
# 已硬删，转写唯一出口=ct2 自管运行时（_ct2_ready 分派）。
_CT2_DEFAULT_MODEL = "large-v2"
_CLIPS_SUBDIR = "media_clips"
_MAX_CLIPS = 20


def _runner_script_path() -> str:
    """asr_runner.py 随包定位（2.7.1 件1：脚本直调形态单一来源）。

    frozen→<exe 目录>/_internal/subtransjav/refine/asr_runner.py
    （spec datas 单文件落点；存在性检查，回退 exe 同目录）；
    dev→包内同目录 asr_runner.py（仓库/安装源码形态）。找不到返回
    ""（调用方回退 -m 形态，dev-only）。"""
    if getattr(sys, "frozen", False):
        cand = (Path(sys.executable).parent / "_internal" / "subtransjav"
                / "refine" / "asr_runner.py")
        if cand.is_file():
            return str(cand)
        fb = Path(sys.executable).parent / "asr_runner.py"
        return str(fb) if fb.is_file() else ""
    dev = Path(__file__).resolve().parent / "asr_runner.py"
    return str(dev) if dev.is_file() else ""


def resolve_ffmpeg() -> str:
    """ffmpeg 绝对路径解析（PATH which）。

    返回可执行文件绝对路径或 ""（不可用）；抽片 subprocess 显式传该
    路径，不依赖 app 进程 PATH 解析行为。3.2 退役批起上游 python 相对
    候选目录语义随 whisper 链删除（D2026-1029-01），仅余 PATH。"""
    return shutil.which("ffmpeg") or ""


def _ct2_status() -> dict:
    """ct2 运行时状态（退役批起唯一引擎状态单一来源，GUI 状态面数据源）。"""
    try:
        from . import asr_runtime
        installed = asr_runtime.is_installed()
        model_present = bool(asr_runtime.resolve_ct2_model_dir(_CT2_DEFAULT_MODEL))
        ok = False
        if installed:
            ok, _detail = asr_runtime.selfcheck()
        return {"installed": installed, "selfcheck_ok": ok,
                "model_present": model_present,
                "model": _CT2_DEFAULT_MODEL,
                "models": asr_runtime.CT2_MODELS}
    except Exception as e:      # noqa: BLE001 probe 永不阻断
        return {"installed": False, "selfcheck_ok": False,
                "model_present": False, "model": _CT2_DEFAULT_MODEL,
                "models": [], "error": str(e)}


# ---------------------------------------------------------------------------
# 重转写与对照块
# ---------------------------------------------------------------------------

def _ct2_ready() -> bool:
    """ct2 引擎就绪判定（运行时已装 ∧ 缺省模型已落位）；探测永不抛。"""
    try:
        from . import asr_runtime
        return (asr_runtime.is_installed()
                and bool(asr_runtime.resolve_ct2_model_dir(_CT2_DEFAULT_MODEL)))
    except Exception:      # noqa: BLE001
        return False


def _srt_file_to_contract(srt_path: str) -> dict:
    """ct2 产出的 SRT → 运行器 JSON 契约形态（text+segments；置信键缺省
    由消费方按存在性读取，C13 口径）。"""
    from .filters import parse_srt
    with open(srt_path, encoding="utf-8") as f:
        entries = parse_srt(f.read())
    segments = []
    texts = []
    for e in entries:
        timing = str(e.get("timing") or "")
        text = str(e.get("text") or "").strip()
        if not text:
            continue
        m = _TIMING_SPAN_RE.search(timing)
        if m:
            g = [int(x) for x in m.groups()]
            start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
            end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
            segments.append({"start": start, "end": end, "text": text})
        texts.append(text)
    return {"ok": True, "text": "".join(texts), "segments": segments}


_TIMING_SPAN_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")


def _run_transcription_ct2(clip_path: str, language: str,
                           timeout: int = 300) -> dict:
    """ct2 引擎单片段重转写（自管运行时子进程）。

    契约回读优先级（D2026-1029-01 批1 置信透传）：runner stdout segments
    数组（含置信三键）优先；无段数组时回退 SRT 解析（老 runner 兼容）。
    SRT 由 runner 照常写出（整片形态即成品件，此处临时件仅作兜底源）。"""
    import tempfile

    from . import asr_runtime
    model_dir = asr_runtime.resolve_ct2_model_dir(_CT2_DEFAULT_MODEL)
    if not model_dir:
        return {"ok": False, "text": "",
                "error": "ct2 模型未落位（先经引擎页/CLI 下载模型件）"}
    fd, tmp_srt = tempfile.mkstemp(suffix=".srt", prefix="ct2clip_")
    os.close(fd)
    try:
        cmd = asr_runtime.ct2_runner_command(str(clip_path), tmp_srt,
                                             model_dir=model_dir,
                                             model=_CT2_DEFAULT_MODEL)
        proc = subprocess.run(
            cmd, capture_output=True, encoding="utf-8", errors="replace",
            timeout=timeout, cwd=str(paths.app_root()),
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            creationflags=CREATE_NO_WINDOW)
        for line in (proc.stdout or "").splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    payload = json.loads(line)
                except ValueError:
                    continue
                if payload.get("ok"):
                    segs = payload.get("segments")
                    if isinstance(segs, list):
                        text = "".join(
                            str((s or {}).get("text") or "").strip()
                            for s in segs if isinstance(s, dict))
                        return {"ok": True, "text": text,
                                "segments": segs, "engine": "ct2"}
                    if os.path.isfile(tmp_srt):
                        out = _srt_file_to_contract(tmp_srt)
                        out["engine"] = "ct2"
                        return out
                if not payload.get("ok"):
                    return {"ok": False, "text": "",
                            "error": str(payload.get("error") or "ct2 转写失败")}
        return {"ok": False, "text": "",
                "error": f"ct2 运行器无有效输出（rc={proc.returncode}）"}
    except (OSError, subprocess.TimeoutExpired) as e:
        return {"ok": False, "text": "", "error": f"ct2 子进程失败: {e}"}
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp_srt)


def run_transcription(clip_path: str, asr_python: str = "",
                      model: str = "large-v2", language: str = "ja",
                      timeout: int = 300) -> dict:
    """单片段重转写（ct2 唯一引擎分派；JSON 契约解析；失败降级 dict）。

    asr_python/model 参数保留（签名稳定/废弃壳口径）：legacy whisper
    链已删（D2026-1029-01），传入不再旁路 ct2，仅由 CLI 层出退役警告。

    返回 {"ok": bool, "text": str, "error": str}。"""
    if _ct2_ready():
        return _run_transcription_ct2(clip_path, language, timeout)
    return {"ok": False, "text": "",
            "error": "转写引擎未安装（CT2 唯一引擎，首次使用需安装）——"
                     "python -m subtransjav.refine.asr_runtime install，"
                     "或在引擎页操作"}


def batch_transcribe_clips(media_path: str, timings: list[str], *,
                           model: str | None = None,
                           model_dir: str | None = None,
                           max_clips: int = _MAX_CLIPS,
                           progress=None) -> list[dict]:
    """批量转写（ct2 唯一引擎，D2026-1029-01 退役批收敛单路）：
    slice_clips 切片→逐 clip ct2 转写（_run_transcription_ct2，每片独立
    子进程；stdout segments 含三维置信键）→按 timing 对齐返回。

    - model/model_dir 参数保留（签名稳定/废弃壳口径）：legacy whisper
      批量链已删，传入仅由 CLI 层出退役警告；
    - 超时/失败该段如实标记 ok=False（不静默）；
    - progress：可选回调 progress(done, total)（切片后可用数口径）；
    - 切片失败/被 max_clips 截断的 timing 如实标记 ok=False；
    - cleanup_clips 交调用方（保持现惯例）。

    返回：与 timings 等长的 list[dict]，每项 {"timing", "ok", "text",
    "segments", "error"}（segments 为含置信字段的段级数组，C13）。"""
    failed = lambda timing, err: {"timing": timing, "ok": False,  # noqa: E731
                                  "text": "", "segments": [], "error": err}
    sliced = slice_clips(media_path, timings, max_clips=max_clips)
    clips = sliced.get("clips") or []
    by_timing: dict[str, dict] = {}
    for t in timings:
        by_timing[t] = failed(t, "")      # 占位，成功后被覆盖
    if not clips:
        err = sliced.get("error") or "无可用切片"
        for t in timings:
            by_timing[t] = failed(t, f"切片失败: {err}")
        return [by_timing[t] for t in timings]
    # 切片成功但部分跳过（超 max_clips 截断/ffmpeg 单段失败）→ 如实标记
    done_timings = {c["timing"] for c in clips}
    skipped_note = (f"切片跳过 {sliced.get('skipped', 0)} 段"
                    f"（超上限 {_MAX_CLIPS} 或 ffmpeg 失败）"
                    if sliced.get("skipped") else "切片失败")
    total_ct2 = len(clips)
    for done_ct2, c in enumerate(clips, 1):
        r = _run_transcription_ct2(c["path"], "ja")
        if r.get("ok"):
            by_timing[c["timing"]] = {
                "timing": c["timing"], "ok": True,
                "text": str(r.get("text") or ""),
                "segments": r.get("segments") or [], "error": ""}
        else:
            by_timing[c["timing"]] = failed(
                c["timing"], str(r.get("error") or "ct2 转写失败"))
        if progress is not None:
            with contextlib.suppress(Exception):
                progress(done_ct2, total_ct2)
    for t in timings:
        if t not in done_timings and not by_timing[t]["error"]:
            by_timing[t] = failed(t, skipped_note)
    return [by_timing[t] for t in timings]


def build_crosscheck_block(clips: list[dict], asr_python: str = "",
                           model: str = "large-v2",
                           char_limit: int = 2000) -> dict:
    """切片批量重转写并聚合对照块（C6：≤2000 截断+非真值声明）。

    clips 元素＝{path, timing, current}。返回 {"block": str, "segments": n,
    "failed": n, "detail": [...]}；无可用片段 block=""。
    detail＝结构化对照段 [{"timing", "asr_text", "current_text"}]（全文
    不截断，D2026-1010-03 件A：随 _AI质量建议.json 落盘供 GUI 媒体对照
    区展示；喂 LLM 的 block 截断口径维持不变）。"""
    lines: list[str] = [
        "信度声明：以下 ASR 转写文本为本机语音识别输出，非真值（转写可能"
        "自带错误），仅作漏听/误听对照参考；不改变任何默认阈值。"]
    segments = 0
    failed = 0
    detail: list[dict] = []
    for clip in clips:
        r = run_transcription(clip.get("path") or "", asr_python, model)
        if not r["ok"] or not r["text"].strip():
            failed += 1
            lines.append(f"- 段 {clip.get('timing') or clip.get('start')}"
                         f"：ASR 失败（{r['error'][:60]}）")
            continue
        segments += 1
        detail.append({"timing": str(clip.get("timing")
                                     or clip.get("start") or ""),
                       "asr_text": r["text"].strip(),
                       "current_text": str(clip.get("current") or "")})
        lines.append(f"- 段 {clip.get('timing') or clip.get('start')}："
                     f"ASR 转写：{r['text'].strip()[:200]}"
                     + (f"（现译：{str(clip.get('current'))[:100]}）"
                        if clip.get("current") else ""))
    if not segments:
        return {"block": "", "segments": 0, "failed": failed, "detail": []}
    block = "\n".join(lines)
    if len(block) > char_limit:
        block = block[:char_limit] + "\n（对照块超长已截断）"
    return {"block": block, "segments": segments, "failed": failed,
            "detail": detail}


def slice_clips(media_path: str, timings: list[str],
                max_clips: int = _MAX_CLIPS) -> dict:
    """按 SRT timing 列表抽 16k 单声道 wav 片段（ffmpeg list-args，无 shell）。

    timings：["HH:MM:SS,mmm --> HH:MM:SS,mmm", ...]（疑似漏听段等），超
    max_clips 截断。落数据根 Temp/media_clips/（sha1 指纹命名，复用
    audio_detect 临时面语义）。返回 {"ok", "clips": [{path, timing}],
    "error", "skipped"}；ffmpeg 缺失/失败逐段降级。ffmpeg 路径经
    resolve_ffmpeg 解析（PATH），subprocess 显式传绝对路径。"""
    ffmpeg = resolve_ffmpeg()
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
