"""疑似漏听检测（音频能量粗筛）测试：合成 wav 单测 / ffmpeg 探测降级 /
报告与导读集成 / stale 清扫。全程不依赖真实 ffmpeg（monkeypatch 注入）。
"""

import json
import math
import struct
import wave
from pathlib import Path

from subtransjav.refine import audio_detect as ad
from subtransjav.refine.audio_detect import (
    cleanup_stale_audio_files,
    detect_audio_insights,
)

RATE = 16000


# ---------------------------------------------------------------------------
# 工具：合成 wav（wave 模块写 16kHz 正弦 + 静音段）
# ---------------------------------------------------------------------------

def _write_wav(path, segments, rate=RATE):
    """segments: [(start_s, dur_s, amplitude)]，未覆盖区间为静音。
    amplitude=0 即静音；>0 写正弦（16-bit 单声道）。"""
    total = max(0.0, max(s + d for s, d, _ in segments)) if segments else 1.0
    n = int(total * rate)
    buf = [0.0] * n
    for start, dur, amp in segments:
        i0, i1 = int(start * rate), int((start + dur) * rate)
        for i in range(i0, min(i1, n)):
            buf[i] = amp * math.sin(2 * math.pi * 220 * i / rate)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        w.writeframes(struct.pack(f"<{n}h",
                                  *(max(-32767, min(32767, int(x * 32767)))
                                    for x in buf)))


def _install_fake_ffmpeg(monkeypatch, wav_src: str | None):
    """注入假 ffmpeg：探测命中；抽取 = 复制合成 wav（或写坏文件）。"""
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: "C:/fake/ffmpeg.exe")

    def _extract(ff, media, out, sr):
        if wav_src is None:
            Path(out).write_bytes(b"not a wav")   # 损坏 wav 场景
        else:
            Path(out).write_bytes(Path(wav_src).read_bytes())
    monkeypatch.setattr(ad, "_extract_wav", _extract)


def _mk_media(tmp_path) -> str:
    """假媒体文件（存在性检查用；内容不参与——ffmpeg 为假注入）。"""
    p = tmp_path / "media.mp4"
    p.write_bytes(b"fake media")
    return str(p)


def _entries(*spans):
    """spans: [(start_s, end_s)] → 导读同形态条目。"""
    def fmt(s):
        ms = int(round(s * 1000))
        h, rem = divmod(ms, 3600_000)
        m, rem = divmod(rem, 60_000)
        sec, msec = divmod(rem, 1000)
        return f"{h:02d}:{m:02d}:{sec:02d},{msec:03d}"
    return [{"index": i + 1,
             "timing": f"{fmt(s)} --> {fmt(e)}", "text": "x"}
            for i, (s, e) in enumerate(spans)]


# ---------------------------------------------------------------------------
# 合成 wav 单测
# ---------------------------------------------------------------------------

def test_silence_gap_with_speech_hits_candidate(tmp_path, monkeypatch):
    """字幕 gap（1.0s-2.0s）内插高能量段 → 疑似漏听候选命中。"""
    wav = tmp_path / "a.wav"
    _write_wav(wav, [(1.05, 0.9, 0.9)])
    _install_fake_ffmpeg(monkeypatch, str(wav))
    entries = _entries((0.0, 1.0), (2.0, 3.0))
    r = detect_audio_insights(_mk_media(tmp_path), entries, temp_root=str(tmp_path))
    assert r["available"] is True
    assert len(r["candidates"]) == 1
    c = r["candidates"][0]
    assert c["timing"] == "00:00:01,000 --> 00:00:02,000"
    assert c["index"] == 2
    assert c["speech_overlap_s"] > 0.15
    assert r["metrics"]["truncated"] is False


def test_all_silence_zero_candidates(tmp_path, monkeypatch):
    """全静音 → 零候选。"""
    wav = tmp_path / "sil.wav"
    _write_wav(wav, [(0.0, 3.0, 0.0)])
    _install_fake_ffmpeg(monkeypatch, str(wav))
    r = detect_audio_insights(_mk_media(tmp_path), _entries((0.0, 1.0), (2.0, 3.0)),
                              temp_root=str(tmp_path))
    assert r["available"] is True
    assert r["candidates"] == []


def test_no_gap_full_coverage_zero_candidates(tmp_path, monkeypatch):
    """无 gap（字幕全覆盖）→ 零候选（即使全片有声）。"""
    wav = tmp_path / "loud.wav"
    _write_wav(wav, [(0.0, 3.0, 0.9)])
    _install_fake_ffmpeg(monkeypatch, str(wav))
    r = detect_audio_insights(_mk_media(tmp_path), _entries((0.0, 1.0), (1.1, 3.0)),
                              temp_root=str(tmp_path))
    assert r["available"] is True
    assert r["candidates"] == []


def test_truncation_limit(tmp_path, monkeypatch):
    """截断上限生效：5 个含能量 gap，max_candidates=2 → 2 条+注明。"""
    wav = tmp_path / "multi.wav"
    segs = [(1.0 + 2.0 * i, 0.4, 0.9) for i in range(5)]
    _write_wav(wav, segs)
    _install_fake_ffmpeg(monkeypatch, str(wav))
    spans = [(float(i), float(i) + 1.0) for i in range(0, 10, 2)]  # gap 5 处
    r = detect_audio_insights(_mk_media(tmp_path), _entries(*spans),
                              temp_root=str(tmp_path), max_candidates=2)
    assert r["available"] is True
    assert len(r["candidates"]) == 2
    assert r["metrics"]["truncated"] is True


def test_default_max_candidates_20(tmp_path, monkeypatch):
    """默认截断上限 20：25 个含能量 gap → 20 条+注明。"""
    wav = tmp_path / "many.wav"
    segs = [(1.0 + 2.0 * i, 0.3, 0.9) for i in range(25)]
    _write_wav(wav, segs)
    _install_fake_ffmpeg(monkeypatch, str(wav))
    spans = [(float(i), float(i) + 1.0) for i in range(0, 50, 2)]
    r = detect_audio_insights(_mk_media(tmp_path), _entries(*spans),
                              temp_root=str(tmp_path))
    assert len(r["candidates"]) == 20
    assert r["metrics"]["truncated"] is True


# ---------------------------------------------------------------------------
# ffmpeg 探测降级 / 容错
# ---------------------------------------------------------------------------

def test_no_ffmpeg_degrades(monkeypatch, tmp_path):
    """ffmpeg 未装（which→None）→ available=False + reason 提示。"""
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: None)
    r = detect_audio_insights(_mk_media(tmp_path), _entries((0.0, 1.0)),
                              temp_root=str(tmp_path))
    assert r["available"] is False
    assert "未检测到 ffmpeg" in r["reason"]
    assert r["candidates"] == []


def test_missing_media_degrades(tmp_path):
    """媒体路径不存在 → available=False。"""
    r = detect_audio_insights("", _entries((0.0, 1.0)),
                              temp_root=str(tmp_path))
    assert r["available"] is False
    r2 = detect_audio_insights(str(tmp_path / "no.mp4"),
                               _entries((0.0, 1.0)),
                               temp_root=str(tmp_path))
    assert r2["available"] is False


def test_corrupt_wav_degrades_without_raise(tmp_path, monkeypatch):
    """损坏 wav → 降级为 available=False，绝不抛。"""
    _install_fake_ffmpeg(monkeypatch, None)   # 抽取写出非 wav 字节
    r = detect_audio_insights(_mk_media(tmp_path), _entries((0.0, 1.0)),
                              temp_root=str(tmp_path))
    assert r["available"] is False
    assert "音频检测失败" in r["reason"]


def test_extract_raises_degrades(tmp_path, monkeypatch):
    """抽取失败（假 ffmpeg 抛错）→ 降级不抛。"""
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: "ff")

    def _boom(ff, media, out, sr):
        raise RuntimeError("boom")
    monkeypatch.setattr(ad, "_extract_wav", _boom)
    r = detect_audio_insights(_mk_media(tmp_path), _entries((0.0, 1.0)),
                              temp_root=str(tmp_path))
    assert r["available"] is False


def test_finally_cleans_tmp_wav(tmp_path, monkeypatch):
    """管线 finally 清理：检测结束后 temp_root/audio_detect/ 无残留。"""
    wav = tmp_path / "a.wav"
    _write_wav(wav, [(1.1, 0.6, 0.9)])
    _install_fake_ffmpeg(monkeypatch, str(wav))
    r = detect_audio_insights(_mk_media(tmp_path), _entries((0.0, 1.0), (2.0, 3.0)),
                              temp_root=str(tmp_path))
    assert r["available"] is True
    d = tmp_path / "audio_detect"
    assert d.is_dir()
    assert list(d.iterdir()) == []


def test_stale_cleanup(tmp_path):
    """stale 清扫：超 24h 文件删除，新鲜文件保留；目录缺失返回 0。"""
    d = tmp_path / "audio_detect"
    d.mkdir()
    old = d / "ad_old.wav"
    old.write_bytes(b"x")
    import os
    past = old.stat().st_mtime - 25 * 3600
    os.utime(old, (past, past))
    fresh = d / "ad_new.wav"
    fresh.write_bytes(b"x")
    removed = cleanup_stale_audio_files(str(tmp_path))
    assert removed == 1
    assert not old.exists() and fresh.exists()
    # 目录缺失：静默 0
    assert cleanup_stale_audio_files(str(tmp_path / "none")) == 0


# ---------------------------------------------------------------------------
# 报告与导读集成（build_quality_report / guide_sink）
# ---------------------------------------------------------------------------

def _report_and_guide(audio_insights):
    from subtransjav.refine.quality_report import build_quality_report
    orig = [{"index": 1, "timing": "00:00:00,000 --> 00:00:01,000",
             "text": "あ"}]
    final = [{"index": 1, "timing": "00:00:00,000 --> 00:00:01,000",
              "text": "啊"}]
    guide: dict = {}
    report = build_quality_report(orig, final, "demo", guide_sink=guide,
                                  audio_insights=audio_insights)
    return report, guide


def test_report_section_and_guide_category():
    ins = {"available": True, "reason": "",
           "candidates": [{"index": 2,
                           "timing": "00:00:01,000 --> 00:00:02,000",
                           "gap_ms": 1000, "speech_overlap_s": 0.6,
                           "message": "字幕间隙 1000ms 内检测到语音能量"}],
           "metrics": {"threshold_pct": 85, "duration_s": 10.0,
                       "truncated": False, "total_candidates": 1}}
    report, guide = _report_and_guide(ins)
    assert "【疑似漏听观测（音频能量粗筛）】" in report
    assert "疑似（粗筛）" in report
    assert "RMS 能量代理，非神经 VAD" in report
    cats = [it for it in guide["items"]
            if it["category"] == "suspected_missed_speech"]
    assert len(cats) == 1
    assert cats[0]["timing"] == "00:00:01,000 --> 00:00:02,000"
    # 仅报告不重翻：current_text 恒为 None（不可自动重翻语义）
    assert cats[0]["current_text"] is None
    assert cats[0]["status"] == "observation"


def test_report_section_unavailable_one_line():
    ins = {"available": False, "reason": "未检测到 ffmpeg",
           "candidates": [], "metrics": {}}
    report, guide = _report_and_guide(ins)
    assert "音频检测不可用：未检测到 ffmpeg" in report
    assert all(it["category"] != "suspected_missed_speech"
               for it in guide.get("items", []))


def test_report_section_absent_when_none():
    report, guide = _report_and_guide(None)
    assert "疑似漏听观测" not in report
    assert all(it["category"] != "suspected_missed_speech"
               for it in guide.get("items", []))


def test_report_section_zero_candidates():
    ins = {"available": True, "reason": "", "candidates": [],
           "metrics": {"threshold_pct": 85, "duration_s": 3.0,
                       "truncated": False}}
    report, _ = _report_and_guide(ins)
    assert "未发现疑似漏听段" in report


def test_report_truncated_note():
    ins = {"available": True, "reason": "",
           "candidates": [{"index": 2,
                           "timing": "00:00:01,000 --> 00:00:02,000",
                           "gap_ms": 1000, "speech_overlap_s": 0.5,
                           "message": "m"}],
           "metrics": {"threshold_pct": 85, "duration_s": 3.0,
                       "truncated": True, "total_candidates": 21}}
    report, _ = _report_and_guide(ins)
    assert "已达截断上限" in report


# ---------------------------------------------------------------------------
# 管线集成（参照 test_pipeline_v2 既有 report 测试模式）
# ---------------------------------------------------------------------------

def _make_pipeline_cfg(tmp_path, **kw):
    from subtransjav.refine.config import RefineConfig, StageConfig
    cfg = RefineConfig(inputs=[], tm_enabled=False, v2_profile="cloud", **kw)
    cfg.stages = [
        StageConfig(0, True, "lmstudio", "fake-model"),
        StageConfig(1, False, "deepseek", ""),
        StageConfig(2, True, "lmstudio", "fake-model"),
        StageConfig(3, False, "lmstudio", ""),
    ]
    return cfg


class _FakeClient:
    """假 LLM 客户端（与 test_pipeline_v2.FakeClient 同款最小口径）。"""

    def __init__(self):
        self.calls = []

    def translate_entries(self, entries, *, system_text, user_prompt,
                          max_batch_size=30, allow_empty_deletions=False,
                          scene_threshold=60.0, progress=None):
        from subtransjav.translate.llm_client import BatchResult
        self.calls.append([e["index"] for e in entries])
        is_stage_b = any("|||" in e["text"] for e in entries)
        translations = {
            e["index"]: (f"审{e['index']}" if is_stage_b
                         else f"译{e['index']}")
            for e in entries}
        return BatchResult(translations=translations, deleted=set(),
                           failed=[])


def _wire_pipeline(tmp_path, monkeypatch):
    """复用 test_pipeline_v2 的 e2e 接线模式（假 LLM / 假 TM / 隔离 Errors）。"""
    from subtransjav.refine import pipeline_v2 as pv

    def _fake_tmp(p, s):
        d = tmp_path / "work"
        d.mkdir(exist_ok=True)
        return str(d)
    monkeypatch.setattr(pv, "refine_tmp_dir", _fake_tmp)
    monkeypatch.setattr(pv, "_make_client", lambda cfg, tag: _FakeClient())
    monkeypatch.setattr(pv, "_init_tm", lambda c: None)
    import subtransjav.refine.source_hallucination as gate0
    monkeypatch.setattr(gate0, "_default_errors_dir",
                        lambda: str(tmp_path / "Errors"))


def _write_input_srt(tmp_path):
    in_srt = tmp_path / "demo.srt"
    rows = []
    for i, text in enumerate(["こんにちは", "さようなら", "また明日"]):
        s = 4 * i
        rows.append(f"{i + 1}\n00:00:{s:02d},000 --> 00:00:{s + 1:02d},000\n"
                    f"{text}\n")
    in_srt.write_text("\n".join(rows), encoding="utf-8")
    return in_srt


def test_pipeline_integrates_audio_insights(tmp_path, monkeypatch):
    """管线集成：media_path 非空 + 开关开 → 报告含新节、导读含新类别且
    仅观测（current_text=None，不进行动条目）。"""
    from subtransjav.refine import audio_detect as admod
    from subtransjav.refine import pipeline_v2 as pv

    fake_result = {"available": True, "reason": "",
                   "candidates": [{"index": 3,
                                   "timing": "00:00:05,000 --> 00:00:06,000",
                                   "gap_ms": 2000, "speech_overlap_s": 0.8,
                                   "message": "疑似漏听（粗筛）"}],
                   "metrics": {"threshold_pct": 85, "duration_s": 12.0,
                               "truncated": False}}
    monkeypatch.setattr(admod, "detect_audio_insights",
                        lambda *a, **k: dict(fake_result))
    _wire_pipeline(tmp_path, monkeypatch)
    cfg = _make_pipeline_cfg(tmp_path, media_path=str(tmp_path / "m.mp4"))
    in_srt = _write_input_srt(tmp_path)
    out = pv._run_single_v2(cfg, str(in_srt))
    assert out.endswith("demo_final_cn.srt")
    report = (tmp_path / "demo_质量报告.txt").read_text(encoding="utf-8")
    assert "【疑似漏听观测（音频能量粗筛）】" in report
    guide = json.loads(
        (tmp_path / "demo_质量报告导读.json").read_text(encoding="utf-8"))
    cats = [it for it in guide["items"]
            if it["category"] == "suspected_missed_speech"]
    assert len(cats) == 1
    assert cats[0]["current_text"] is None
    assert cats[0]["status"] == "observation"


def test_pipeline_disabled_omits_section(tmp_path, monkeypatch):
    """关闭开关 → 报告无新节、导读无新类别。"""
    from subtransjav.refine import audio_detect as admod
    from subtransjav.refine import pipeline_v2 as pv

    called = []
    monkeypatch.setattr(admod, "detect_audio_insights",
                        lambda *a, **k: called.append(1) or {})
    _wire_pipeline(tmp_path, monkeypatch)
    cfg = _make_pipeline_cfg(tmp_path, media_path=str(tmp_path / "m.mp4"),
                             audio_detect_enabled=False)
    in_srt = _write_input_srt(tmp_path)
    pv._run_single_v2(cfg, str(in_srt))
    assert called == []
    report = (tmp_path / "demo_质量报告.txt").read_text(encoding="utf-8")
    assert "疑似漏听观测" not in report
    guide = json.loads(
        (tmp_path / "demo_质量报告导读.json").read_text(encoding="utf-8"))
    assert all(it["category"] != "suspected_missed_speech"
               for it in guide["items"])


def test_pipeline_no_media_omits_section(tmp_path, monkeypatch):
    """无 media_path（契约路径为空）→ 检测不执行、章节缺席。"""
    from subtransjav.refine import audio_detect as admod
    from subtransjav.refine import pipeline_v2 as pv

    called = []
    monkeypatch.setattr(admod, "detect_audio_insights",
                        lambda *a, **k: called.append(1) or {})
    _wire_pipeline(tmp_path, monkeypatch)
    cfg = _make_pipeline_cfg(tmp_path)
    in_srt = _write_input_srt(tmp_path)
    pv._run_single_v2(cfg, str(in_srt))
    assert called == []
    report = (tmp_path / "demo_质量报告.txt").read_text(encoding="utf-8")
    assert "疑似漏听观测" not in report


def test_pipeline_detect_crash_degrades(tmp_path, monkeypatch):
    """检测函数抛异常 → 降级为 available=False 一行说明，不阻断管线。"""
    from subtransjav.refine import audio_detect as admod
    from subtransjav.refine import pipeline_v2 as pv

    def _boom(*a, **k):
        raise RuntimeError("kaboom")
    monkeypatch.setattr(admod, "detect_audio_insights", _boom)
    _wire_pipeline(tmp_path, monkeypatch)
    cfg = _make_pipeline_cfg(tmp_path, media_path=str(tmp_path / "m.mp4"))
    in_srt = _write_input_srt(tmp_path)
    out = pv._run_single_v2(cfg, str(in_srt))
    assert out.endswith("demo_final_cn.srt")
    report = (tmp_path / "demo_质量报告.txt").read_text(encoding="utf-8")
    assert "音频检测不可用" in report


# ---------------------------------------------------------------------------
# 配置分层（TUNABLE 注册）
# ---------------------------------------------------------------------------

def test_audio_detect_tunable_fields_registered(monkeypatch):
    """4 个 audio_detect 字段进 TUNABLE 表，env 覆盖生效（bool 白名单）。"""
    from subtransjav.refine.config import TUNABLE_FIELD_TYPES
    for name in ("audio_detect_enabled", "audio_detect_threshold_pct",
                 "audio_detect_min_gap_ms", "audio_detect_max_candidates"):
        assert name in TUNABLE_FIELD_TYPES
    monkeypatch.setenv("SUBTRANSJAV_AUDIO_DETECT_ENABLED", "0")
    monkeypatch.setenv("SUBTRANSJAV_AUDIO_DETECT_THRESHOLD_PCT", "90")
    from subtransjav.refine.config import RefineConfig
    cfg = RefineConfig(inputs=[])
    assert cfg.audio_detect_enabled is False
    assert cfg.audio_detect_threshold_pct == 90
    assert cfg.audio_detect_min_gap_ms == 300
    assert cfg.audio_detect_max_candidates == 20


def test_media_without_ffmpeg_reports_one_line(tmp_path, monkeypatch):
    """端到端（模块级假 ffmpeg 缺失）：有媒体但无 ffmpeg → 报告一行说明。"""
    media = tmp_path / "m.mp4"
    media.write_bytes(b"fake")
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: None)
    r = detect_audio_insights(str(media), _entries((0.0, 1.0)),
                              temp_root=str(tmp_path))
    assert r["available"] is False
    assert "未检测到 ffmpeg" in r["reason"]
    report, _ = _report_and_guide(r)
    assert "（音频检测不可用：未检测到 ffmpeg）" in report


def test_percentile_bounds():
    vals = [float(i) for i in range(100)]
    assert ad._percentile(vals, 0) == 0.0
    assert ad._percentile(vals, 100) == 99.0
    assert ad._percentile([], 85) == 0.0


# ---------------------------------------------------------------------------
# 3.0 批3 3A：detect_speech_windows（漏听置信门 ≤1s 判定数据源）
# ---------------------------------------------------------------------------

def test_detect_speech_windows_cuts_by_window(tmp_path, monkeypatch):
    """窗口切割：抽一次 wav，语音段按间隙窗口取交集返回。"""
    wav = tmp_path / "sp.wav"
    _write_wav(wav, [(0.0, 1.0, 1.0), (5.0, 1.0, 1.0)])   # 两处语音
    media = _mk_media(tmp_path)
    _install_fake_ffmpeg(monkeypatch, str(wav))
    monkeypatch.setattr(ad, "_detect_temp_root", lambda: str(tmp_path))
    r = ad.detect_speech_windows(
        media, ["00:00:00,000 --> 00:00:02,000",
                "00:00:04,500 --> 00:00:07,000"])
    assert "__error" not in r
    w0 = r["00:00:00,000 --> 00:00:02,000"]
    w1 = r["00:00:04,500 --> 00:00:07,000"]
    assert w0 and w0[0][0] < 1.0                          # 0-1s 语音命中
    assert w1 and any(4.5 <= s < 6.0 for s, _e in w1)     # 5-6s 语音命中
    assert all(e <= 7.0 for _s, e in w1)                  # 交集不越窗


def test_detect_speech_windows_no_speech_window_empty(tmp_path, monkeypatch):
    wav = tmp_path / "sil.wav"
    _write_wav(wav, [])                                   # 全静音
    media = _mk_media(tmp_path)
    _install_fake_ffmpeg(monkeypatch, str(wav))
    monkeypatch.setattr(ad, "_detect_temp_root", lambda: str(tmp_path))
    r = ad.detect_speech_windows(media, ["00:00:00,000 --> 00:00:02,000"])
    assert "__error" not in r
    assert r["00:00:00,000 --> 00:00:02,000"] == []


def test_detect_speech_windows_error_degrades_honestly(tmp_path, monkeypatch):
    """诚实退化（C18）：ffmpeg 缺失/媒体缺失 → 仅 {"__error": reason}。"""
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: None)
    r = ad.detect_speech_windows("m.mp4", ["00:00:00,000 --> 00:00:01,000"])
    assert set(r) == {"__error"} and r["__error"]
    r = ad.detect_speech_windows("", ["00:00:00,000 --> 00:00:01,000"])
    assert set(r) == {"__error"} and r["__error"]


def test_detect_speech_windows_unparseable_timing_skipped(tmp_path,
                                                          monkeypatch):
    """无法解析的窗口如实缺省（不当全静音、不抛）。"""
    wav = tmp_path / "sp.wav"
    _write_wav(wav, [(0.0, 1.0, 1.0)])
    media = _mk_media(tmp_path)
    _install_fake_ffmpeg(monkeypatch, str(wav))
    monkeypatch.setattr(ad, "_detect_temp_root", lambda: str(tmp_path))
    r = ad.detect_speech_windows(media, ["garbage"])
    assert "__error" not in r and r == {}
