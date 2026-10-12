"""疑似漏听检测（音频能量粗筛，2.0.0-beta 头牌第一阶段，D2026-0929-09）

======================================================================
wave 级 VAD 降级（RMS 能量代理，非神经 VAD）
======================================================================
本模块的"有声/静音"判定是**纯标准库能量粗筛**：以 ffmpeg 抽取的
16kHz 单声道 WAV 为输入，按 10ms hop 计算 RMS 能量序列，取文件内
相对分位（默认 P85）作为有声阈值。它**不是**神经 VAD，无法区分
语音/音乐/噪声，产出仅为"疑似（粗筛）"级别的观测候选，只进质量
报告与导读 json 的观测类别（suspected_missed_speech），绝不进入
可定点重翻的行动条目，也绝不阻断翻译主流程。

媒体来源契约（C-5 收窄语义）：ffmpeg 输入仅限调用方传入的
media_path——即 pipeline 已解析的契约路径（resolve_media_path 结果）
或 cfg.media_path 显式覆盖值，绝不接受用户可控任意串直接进命令行
（subprocess 一律 list-args，禁 shell=True）。

性能策略：分块求和（每块约 1 秒音频，sum(map(mul, a, a)) 纯标准库，
无 numpy/audioop）；2 小时片目标 <30s，超标时降采样率到 8000 重测
一次并在 metrics.downsampled_to_8000 注明（报告随之显示）。

依赖注入：_find_ffmpeg 与 _extract_wav 为模块级函数，测试可
monkeypatch 替换（不触网、不依赖真实 ffmpeg）。
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import time
from array import array
from datetime import datetime, timedelta
from operator import mul
from pathlib import Path

from subtransjav.utils.subprocess_flags import CREATE_NO_WINDOW  # windowed 防黑框单一来源（批0）

# 音频检测临时子目录（TEMP_DIR 下），管线结束 finally 清理 +
# 启动时清扫超龄 stale 文件
AUDIO_DETECT_SUBDIR = "audio_detect"

# 2 小时片性能目标（秒）；首次分析超标则降采样率到 8000 重测一次
PERF_TARGET_S = 30.0
PERF_FALLBACK_RATE = 8000

# stale 文件清扫时限（小时）
STALE_MAX_AGE_HOURS = 24

_FFPROBE_TIMEOUT_S = 15
_FFMPEG_EXTRACT_TIMEOUT_S = 600


# ---------------------------------------------------------------------------
# ffmpeg 探测（可 monkeypatch）
# ---------------------------------------------------------------------------

def _find_ffmpeg() -> str | None:
    """探测系统 ffmpeg：shutil.which 命中后跑一次 `ffmpeg -version`
    冒烟（list-args，禁 shell），防 PATH 残桩/损坏安装。未装或冒烟
    失败一律返回 None（功能静默跳过，绝不报错阻断）。"""
    ff = shutil.which("ffmpeg")
    if not ff:
        return None
    try:
        r = subprocess.run([ff, "-version"], capture_output=True,
                           timeout=_FFPROBE_TIMEOUT_S,
                           creationflags=CREATE_NO_WINDOW)  # GUI 试听/转码路径触达本函数（api.py ad._find_ffmpeg），windowed 防黑框（批0）
    except (OSError, subprocess.SubprocessError):
        return None
    if r.returncode != 0:
        return None
    return ff


def _extract_wav(ffmpeg_path: str, media_path: str, out_path: str,
                 sample_rate: int) -> None:
    """抽取 16kHz（可降 8k）单声道 PCM WAV。list-args 禁 shell；
    media_path 必须是调用方传入的契约路径（见模块 docstring）。"""
    r = subprocess.run(
        [ffmpeg_path, "-y", "-i", media_path, "-vn", "-ac", "1",
         "-ar", str(sample_rate), "-f", "wav", out_path],
        capture_output=True, timeout=_FFMPEG_EXTRACT_TIMEOUT_S,
        creationflags=CREATE_NO_WINDOW)  # CLI 侧调用（console 进程无感）；POSIX=0，补齐为模块级统一钉测（批0）
    if r.returncode != 0 or not os.path.isfile(out_path):
        raise RuntimeError(
            f"ffmpeg 抽取音频失败 (rc={r.returncode}): "
            f"{(r.stderr or b'')[-200:]!r}")


# ---------------------------------------------------------------------------
# 临时目录管理
# ---------------------------------------------------------------------------

def audio_detect_dir(temp_root: str) -> str:
    return str(Path(temp_root) / AUDIO_DETECT_SUBDIR)


def cleanup_stale_audio_files(temp_root: str,
                              max_age_hours: float = STALE_MAX_AGE_HOURS
                              ) -> int:
    """清扫 audio_detect 临时目录中超龄 stale 文件（启动时调用）。
    目录不存在/清扫失败静默返回 0，绝不阻断主流程。"""
    d = audio_detect_dir(temp_root)
    if not os.path.isdir(d):
        return 0
    cutoff = datetime.now() - timedelta(hours=max_age_hours)
    removed = 0
    try:
        names = os.listdir(d)
    except OSError:
        return 0
    for name in names:
        p = Path(d) / name
        try:
            mtime = datetime.fromtimestamp(p.stat().st_mtime)
        except OSError:
            continue
        if mtime < cutoff:
            try:
                p.unlink()
                removed += 1
            except OSError:
                pass
    return removed


def _wav_tmp_path(temp_root: str, media_path: str) -> str:
    """临时 wav 落点：TEMP_DIR/audio_detect/ 下，命名带输入哈希
    （路径+大小+mtime），同输入重跑可复用/覆盖，不同输入不互撞。"""
    d = audio_detect_dir(temp_root)
    os.makedirs(d, exist_ok=True)
    try:
        st = os.stat(media_path)
        identity = f"{media_path}|{st.st_size}|{st.st_mtime_ns}"
    except OSError:
        identity = f"{media_path}|no-stat"
    h = hashlib.sha1(identity.encode("utf-8", "replace")).hexdigest()[:12]
    return str(Path(d) / f"ad_{h}.wav")


# ---------------------------------------------------------------------------
# 能量分析（纯标准库）
# ---------------------------------------------------------------------------

def _hop_rms_series(wav_path: str, hop_ms: int = 10
                    ) -> tuple[int, list[float], float]:
    """wave 分块读 → 10ms hop RMS 序列。返回 (rate, rms 序列, 时长 s)。

    纯标准库（wave + array/memoryview），无 numpy/audioop。每块约
    1 秒音频，sum(map(mul, a, a)) 分块求平方和——2 小时片单遍约
    1.2 亿次乘加，CPython 实测 10-20s 量级（<30s 目标内），超标由
    detect_audio_insights 降采样率重测兜底。损坏 wav 抛 wave.Error/
    OSError，由调用方降级。"""
    import wave

    with wave.open(wav_path, "rb") as w:
        nch = w.getnchannels()
        sampwidth = w.getsampwidth()
        rate = w.getframerate()
        nframes = w.getnframes()
        if rate <= 0 or nframes <= 0:
            raise ValueError("空音频流")
        frames_per_hop = max(1, int(rate * hop_ms / 1000))
        # 每块约 1 秒音频（chunk 内逐 hop 切分），控内存峰值
        chunk_frames = max(frames_per_hop, rate)
        rms: list[float] = []
        remaining = nframes
        while remaining > 0:
            take = min(chunk_frames, remaining)
            raw = w.readframes(take)
            got = len(raw) // (nch * sampwidth)
            if got <= 0:
                break
            remaining -= got
            if sampwidth == 2:
                a = array("h")
                a.frombytes(raw[: len(raw) - len(raw) % 2])
                if nch > 1:
                    a = a[::nch]           # 取首通道
            elif sampwidth == 1:
                # 8-bit PCM 无符号，居中去偏置
                b = array("B")
                b.frombytes(raw[: len(raw) - len(raw) % nch or nch])
                if nch > 1:
                    b = b[::nch]
                a = array("h", [x - 128 for x in b])
            else:
                raise ValueError(f"不支持位宽: {sampwidth}")
            for i in range(0, len(a), frames_per_hop):
                arr = a[i:i + frames_per_hop]
                n = len(arr)
                if not n:
                    continue
                rms.append((sum(map(mul, arr, arr)) / n) ** 0.5)
        duration = nframes / rate
    return rate, rms, duration


def _percentile(values: list[float], pct: int) -> float:
    """最近秩分位（纯函数；空表返回 0.0）。"""
    if not values:
        return 0.0
    s = sorted(values)
    idx = min(len(s) - 1, max(0, round((pct / 100.0) * (len(s) - 1))))
    return s[idx]


def _speech_segments(rms: list[float], threshold: float, hop_s: float
                     ) -> list[tuple[float, float]]:
    """RMS 序列 → 有声段 [(start_s, end_s), ...]（相邻超阈 hop 合并）。"""
    segs: list[tuple[float, float]] = []
    start = None
    for i, v in enumerate(rms):
        if v > threshold:
            if start is None:
                start = i * hop_s
            end = (i + 1) * hop_s
        else:
            if start is not None:
                segs.append((start, end))
                start = None
    if start is not None:
        segs.append((start, len(rms) * hop_s))
    return segs


def _fmt_ms(ms: int) -> str:
    """毫秒 → SRT 时间戳 HH:MM:SS,mmm（与导读条目 timing 同形态）。"""
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3600_000)
    m, rem = divmod(rem, 60_000)
    s, msec = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{msec:03d}"


def _gaps_from_entries(entries: list, min_gap_ms: int
                       ) -> list[dict]:
    """字幕时间轴 gap 提取（相邻条目间隙 ≥ min_gap_ms）。

    timing 解析复用 v2_premerge._timing_span（与全链路同源口径）；
    无法解析起点的条目跳过。"""
    from .v2_premerge import _timing_span

    spans: list[tuple[float, float, object]] = []
    for e in entries:
        s0, e0 = _timing_span(e.get("timing") or "")
        if s0 < 0:
            continue
        spans.append((s0, e0, e.get("index")))
    spans.sort(key=lambda x: (x[0], x[1]))
    gaps: list[dict] = []
    for prev, cur in zip(spans, spans[1:], strict=False):
        gap_ms = int(round((cur[0] - prev[1]) * 1000))
        if gap_ms >= min_gap_ms:
            gaps.append({"start_ms": int(round(prev[1] * 1000)),
                         "end_ms": int(round(cur[0] * 1000)),
                         "gap_ms": gap_ms,
                         "index": cur[2]})
    return gaps


# ---------------------------------------------------------------------------
# 主入口
# ---------------------------------------------------------------------------

def detect_audio_insights(media_path: str, entries: list, *,
                          temp_root: str,
                          threshold_pct: int = 85,
                          min_gap_ms: int = 300,
                          max_candidates: int = 20,
                          hop_ms: int = 10) -> dict:
    """疑似漏听检测主入口（全容错，异常由调用方再兜一层）。

    返回 {"available": bool, "reason": str, "candidates": [...],
    "metrics": {...}}。流程：ffmpeg 探测/冒烟 → 抽 wav → wave 分块
    读 → RMS hop 序列 → 相对分位阈值 → 静音/有声段 → 与字幕 gap
    对照 → 候选列表（截断 max_candidates，超限注明）。任何一步失败
    都降级为 available=False + reason，绝不抛出。"""
    result: dict = {"available": False, "reason": "",
                    "candidates": [], "metrics": {}}
    ff = _find_ffmpeg()
    if ff is None:
        result["reason"] = "未检测到 ffmpeg"
        return result
    if not media_path or not os.path.isfile(media_path):
        result["reason"] = "无媒体文件"
        return result

    tmp_wav = _wav_tmp_path(temp_root, media_path)
    try:
        t0 = time.monotonic()
        _extract_wav(ff, media_path, tmp_wav, 16000)
        rate, rms, duration = _hop_rms_series(tmp_wav, hop_ms)
        elapsed = time.monotonic() - t0
        metrics: dict = {
            "sample_rate": rate,
            "duration_s": round(duration, 2),
            "analyze_s": round(elapsed, 2),
            "threshold_pct": threshold_pct,
        }
        # 性能目标：2 小时片 <30s；超标降采样率到 8000 重测一次并注明
        if elapsed > PERF_TARGET_S:
            _extract_wav(ff, media_path, tmp_wav, PERF_FALLBACK_RATE)
            rate, rms, duration = _hop_rms_series(tmp_wav, hop_ms)
            metrics["sample_rate"] = rate
            metrics["duration_s"] = round(duration, 2)
            metrics["analyze_s"] = round(time.monotonic() - t0, 2)
            metrics["downsampled_to_8000"] = True

        threshold = _percentile(rms, threshold_pct)
        segs = _speech_segments(rms, threshold, hop_ms / 1000.0)
        metrics["speech_ratio_pct"] = round(
            100.0 * sum(e - s for s, e in segs) / duration, 1) \
            if duration > 0 else 0.0

        candidates: list[dict] = []
        truncated = False
        for gap in _gaps_from_entries(entries, min_gap_ms):
            gs, ge = gap["start_ms"] / 1000.0, gap["end_ms"] / 1000.0
            overlap = sum(max(0.0, min(ge, e) - max(gs, s))
                          for s, e in segs)
            if overlap <= 0:
                continue
            if len(candidates) >= max_candidates:
                truncated = True
                break
            candidates.append({
                "index": gap["index"],
                "timing": f"{_fmt_ms(gap['start_ms'])} --> "
                          f"{_fmt_ms(gap['end_ms'])}",
                "gap_ms": gap["gap_ms"],
                "speech_overlap_s": round(overlap, 2),
                "message": f"字幕间隙 {gap['gap_ms']}ms 内检测到语音能量"
                           f"约 {overlap:.2f}s（疑似漏听，粗筛）",
            })
        metrics["truncated"] = truncated
        metrics["total_candidates"] = len(candidates) + (
            1 if truncated else 0)
        result.update(available=True, candidates=candidates, metrics=metrics)
        return result
    except Exception as e:      # noqa: BLE001 音频检测永不阻断主流程
        result["reason"] = f"音频检测失败，本次跳过: {e}"
        result["metrics"] = {}
        return result
    finally:
        # 管线结束 finally 清理本次临时 wav
        try:
            if os.path.isfile(tmp_wav):
                os.unlink(tmp_wav)
        except OSError:
            pass


def detect_speech_windows(media_path: str,
                          gap_timings: list[str],
                          ) -> dict:
    """语音窗口提取（3.0 批3 3A，漏听置信门 ≤1s 放弃判定数据源）。

    抽一次 wav → RMS hop 序列 → 相对分位阈值 → 有声段，再对每个间隙
    窗口（"HH:MM:SS,mmm --> HH:MM:SS,mmm"）取交集，返回
    {timing: [(start_s, end_s), ...]}（窗口内语音段，窗口相对时间轴的
    绝对秒）。检测原语与 detect_audio_insights 同源（_hop_rms_series/
    _speech_segments/_percentile；timing 解析复用 v2_premerge._timing_span，
    与全链路同口径）。

    诚实退化（C18）：ffmpeg 缺失/媒体缺失/检测失败 → 仅返回
    {"__error": reason}（各窗口键缺省），调用方据此跳过 ≤1s 能量门，
    绝不静默当全静音。"""
    try:
        from .v2_premerge import _timing_span
        ff = _find_ffmpeg()
        if ff is None:
            return {"__error": "未检测到 ffmpeg"}
        if not media_path or not os.path.isfile(media_path):
            return {"__error": "无媒体文件"}
        tmp_wav = _wav_tmp_path(_detect_temp_root(), media_path)
        try:
            _extract_wav(ff, media_path, tmp_wav, 16000)
            _rate, rms, _duration = _hop_rms_series(tmp_wav, 10)
            threshold = _percentile(rms, 85)
            segs = _speech_segments(rms, threshold, 10 / 1000.0)
        finally:
            try:
                if os.path.isfile(tmp_wav):
                    os.unlink(tmp_wav)
            except OSError:
                pass
        out: dict[str, list[tuple[float, float]]] = {}
        for timing in gap_timings:
            s0, e0 = _timing_span(timing)
            if s0 < 0:
                # 无法解析的窗口如实缺省（不当全静音、不抛）
                continue
            out[timing] = [(round(max(s0, s), 3), round(min(e0, e), 3))
                           for s, e in segs if min(e0, e) > max(s0, s)]
        return out
    except Exception as e:      # noqa: BLE001 语音窗口检测永不阻断主流程
        return {"__error": f"语音窗口检测失败: {e}"}


def _detect_temp_root() -> str:
    """detect_speech_windows 的临时 wav 落点根（数据根 Temp，与切片
    临时面同语义）。函数化便于测试 monkeypatch。"""
    from subtransjav import paths
    return paths.data_subdir("Temp")
