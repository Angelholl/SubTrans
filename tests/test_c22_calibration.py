"""tests for tools/c22_calibration.py（C22 离线回放 harness，逐间隙 labels 数组，C22-卡1）。

五钉（D2026-1009-02 §三逐间隙口径；d1012-C22-卡1）：
  1. 逐间隙 labels：sample 带 labels=[True, False] → 两行 label 分别 True/False；
  2. 旧行为回归：无 labels 键（或 null）→ 全行用 sample 的 label；
  3. 长度不匹配：_replay_sample raise 中文 ValueError；main 层退出码 1；
  4. 门控语义不回归：全 labels=true 走 main（不打 --enable）→ 退出码 0 且门控文件不产生；
  5. timings 显式清单：取代导读派生、labels 逐条对齐；timings/labels 不等长 → 退出码 1。

全程离线：monkeypatch 模块级 detect_speech_windows / batch_transcribe_clips
（不切片不装载 whisper），cleanup_clips 打桩避免碰真实数据根临时切片目录。
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "c22_calibration.py"
_spec = importlib.util.spec_from_file_location("c22_calibration_under_test",
                                               _TOOL_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

T1 = "00:00:01,000 --> 00:00:03,000"
T2 = "00:00:04,000 --> 00:00:06,000"
T3 = "00:00:07,000 --> 00:00:09,000"

# 合成转写：good 段 + 无拟声文本 → classify 三维全过 = high（与 --selftest 同谱）
_GOOD_SEG = {"start": 0.0, "end": 2.0, "text": "本当にすみません",
             "no_speech_prob": 0.02, "avg_logprob": -0.25,
             "compression_ratio": 1.2}


def _fake_batch(media: str, timings: list[str], **kwargs) -> list[dict]:
    """batch_transcribe_clips 打桩：逐 timing 返回同一条合成转写。"""
    return [{"segments": [_GOOD_SEG], "text": "本当にすみません",
             "error": ""} for _ in timings]


@pytest.fixture
def c22(monkeypatch):
    """回放打桩：能量窗口空、转写合成、切片清理 no-op（只钉 label 分发）。"""
    monkeypatch.setattr(mod, "detect_speech_windows",
                        lambda media, timings: {})
    monkeypatch.setattr(mod, "batch_transcribe_clips", _fake_batch)
    monkeypatch.setattr(mod, "cleanup_clips", lambda *a, **k: 0)
    return mod


def _write_guide(tmp_path: Path, timings: list[str],
                 name: str = "guide.json") -> Path:
    """导读 json：目标 timings 各夹一条非目标类别条目（派生须按类别过滤）。"""
    items: list[dict] = []
    for i, t in enumerate(timings):
        items.append({"category": "suspected_missed_speech", "timing": t})
        if i == 0:
            items.append({"category": "other",
                          "timing": "00:00:50,000 --> 00:00:51,000"})
    p = tmp_path / name
    p.write_text(json.dumps({"items": items}, ensure_ascii=False),
                 encoding="utf-8")
    return p


def _write_manifest(tmp_path: Path, samples: list[dict],
                    name: str = "manifest.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(samples, ensure_ascii=False), encoding="utf-8")
    return p


def _has_chinese(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text))


# ------------------------------------------------------------------ 钉1 逐间隙

def test_pin1_labels_per_gap(c22, tmp_path):
    guide = _write_guide(tmp_path, [T1, T2])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": True, "labels": [True, False]})
    assert [r["timing"] for r in rows] == [T1, T2]
    assert [r["label"] for r in rows] == [True, False]


# ------------------------------------------------------ 钉2 旧行为回归（零外溢）

def test_pin2_legacy_single_label_without_key(c22, tmp_path):
    guide = _write_guide(tmp_path, [T1, T2])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": False})
    assert [r["label"] for r in rows] == [False, False]


def test_pin2_legacy_label_null_keeps_old_behavior(c22, tmp_path):
    """labels=null 与缺省同义：仍走单 label 旧行为。"""
    guide = _write_guide(tmp_path, [T1, T2])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": True, "labels": None})
    assert [r["label"] for r in rows] == [True, True]


# ------------------------------------------------------- 钉3 长度不匹配 fail-closed

def test_pin3_mismatch_raises_chinese_value_error(c22, tmp_path):
    guide = _write_guide(tmp_path, [T1, T2])
    with pytest.raises(ValueError) as exc:
        c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                            "label": True, "labels": [True]})
    assert _has_chinese(str(exc.value))


def test_pin3_mismatch_main_exit_1(c22, tmp_path, capsys):
    guide = _write_guide(tmp_path, [T1, T2])
    manifest = _write_manifest(tmp_path, [
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "labels": [True]}])
    rc = c22.main(["--manifest", str(manifest),
                   "--out", str(tmp_path / "report.md")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "❌" in out and _has_chinese(out)


# ------------------------------------------------- 钉4 门控语义不回归（防外溢）

def test_pin4_gate_not_written_without_enable(c22, tmp_path, monkeypatch):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    guide = _write_guide(tmp_path, [T1, T2])
    manifest = _write_manifest(tmp_path, [
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "labels": [True, True]}])
    out = tmp_path / "report.md"
    rc = c22.main(["--manifest", str(manifest), "--out", str(out)])
    assert rc == 0
    assert out.is_file()
    assert not (tmp_path / "config" / "fullchain_c22.json").exists()


# ------------------------------------------------------ 钉5 timings 显式清单

def test_pin5_explicit_timings_align_labels(c22, tmp_path):
    """导读实际 3 条 > 显式 2 条：按显式 timing 出行且 label 逐条对齐。"""
    guide = _write_guide(tmp_path, [T1, T2, T3])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": False, "timings": [T3, T1],
                               "labels": [True, False]})
    assert [r["timing"] for r in rows] == [T3, T1]
    assert [r["label"] for r in rows] == [True, False]


def test_pin5_timings_labels_mismatch_main_exit_1(c22, tmp_path, capsys):
    guide = _write_guide(tmp_path, [T1, T2])
    manifest = _write_manifest(tmp_path, [
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "timings": [T1, T2], "labels": [True]}])
    rc = c22.main(["--manifest", str(manifest),
                   "--out", str(tmp_path / "report.md")])
    assert rc == 1
    assert "❌" in capsys.readouterr().out
