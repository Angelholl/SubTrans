"""tests for tools/cps_distribution.py（CPS 分布观测脚本，v1.4 批次 1b-C4）。

只读工具：小 SRT fixture 断言 per-file 统计与 --json 结构；
--telemetry 指向不存在路径不炸（stderr 提示后照常输出分布）。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from cps_distribution import (  # noqa: E402
    CPS_CJK_BASE,
    CPS_MIN_DURATION_S,
    CPS_OTHER_BASE,
    CPS_TOLERANCE,
    aggregate_by_scene,
    entry_stats,
    main,
    summarize_stats,
)

T1 = "00:00:01,000 --> 00:00:02,000"          # 时长恰 1.0s，CPS 数值可手算


def _write_srt(tmp_path: Path, name: str = "demo.srt") -> Path:
    """3 条已知 CPS：8.0（CJK，不超 9.2）/ 20.0（ascii，不超 23）/ 30.0（超）。"""
    p = tmp_path / name
    p.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\n一二三四五六七八\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\nabcdefghijklmnopqrst\n\n"
        "3\n00:00:05,000 --> 00:00:06,000\n" + "九" * 30 + "\n",
        encoding="utf-8")
    return p


def test_tool_thresholds_same_as_quality_report():
    """同口径钉：工具常量与 quality_report 观测阈值逐值相等（防漂移）。"""
    from subtransjav.refine import quality_report as qr
    assert CPS_CJK_BASE == qr._CPS_CJK_BASE
    assert CPS_OTHER_BASE == qr._CPS_OTHER_BASE
    assert CPS_TOLERANCE == qr._CPS_TOLERANCE
    assert CPS_MIN_DURATION_S == qr._CPS_MIN_DURATION_S == 0.5


def test_entry_stats_min_duration_gate():
    """D5c：时长 <0.5s 的超短条目跳过返回 None（即使 CPS 爆表）；
    0.5s 恰达门槛（dur<0.5 才跳）。"""
    short = "00:00:05,000 --> 00:00:05,400"   # 0.4s
    assert entry_stats("九" * 30, short) is None          # CPS 75 爆表仍跳
    boundary = "00:00:05,000 --> 00:00:05,500"            # 0.5s
    assert entry_stats("九" * 15, boundary) == (30.0, 9.2)


def test_main_skipped_short_counted(tmp_path, capsys):
    """D5c：短条目进 skipped_short 计数、不进分布与超阈计数。"""
    p = tmp_path / "short.srt"
    p.write_text(
        "1\n00:00:01,000 --> 00:00:01,400\n" + "九" * 30 + "\n\n"   # 0.4s 爆表
        "2\n00:00:03,000 --> 00:00:04,000\n一二三四五六七八\n\n",   # 正常 8.0
        encoding="utf-8")
    assert main([str(p), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    f = data["files"][0]
    assert f["count"] == 1 and f["over_threshold"] == 0
    assert f["skipped"] == 0 and f["skipped_short"] == 1
    assert f["max"] == 8.0
    assert data["global"]["skipped_short"] == 1


def test_entry_stats_known_values_and_skip_rules():
    """口径钉：CPS=去空白字符数/时长；CJK 基准 8 / 其他 20，容差 ×1.15；
    空文本/非法时间轴/时长 ≤0 跳过返回 None。"""
    assert entry_stats("一二三四五六七八", T1) == (8.0, pytest.approx(9.2))
    assert entry_stats("abcdefghijklmnopqrst", T1)[0] == pytest.approx(20.0)
    assert entry_stats("abcdefghijklmnopqrst", T1)[1] == pytest.approx(23.0)
    assert entry_stats("九" * 30, T1)[0] == 30.0
    assert entry_stats("九" * 30 + "  ", T1)[0] == 30.0       # 空白不计
    assert entry_stats("", T1) is None
    assert entry_stats("九" * 30, "非法时间轴") is None
    assert entry_stats("九" * 30, "00:00:05,000 --> 00:00:05,000") is None


def test_summarize_stats_known():
    """分布摘要：count/mean/p50/p90/p95/max（最近秩百分位）；空样本全 None。"""
    s = summarize_stats([8.0, 20.0, 30.0])
    assert s["count"] == 3
    assert s["mean"] == pytest.approx(58 / 3)
    assert s["p50"] == 20.0
    assert s["p90"] == 30.0 and s["p95"] == 30.0
    assert s["max"] == 30.0
    empty = summarize_stats([])
    assert empty["count"] == 0 and empty["mean"] is None
    assert empty["p95"] is None and empty["max"] is None


def test_main_human_and_json(tmp_path, capsys):
    """双输出：human 模式含 per-file 与全局分布行；--json 结构可解析。"""
    p = _write_srt(tmp_path)
    assert main([str(p)]) == 0
    out = capsys.readouterr().out
    assert "demo.srt" in out
    assert "超 CPS 1 条" in out
    assert "max=30.00" in out

    assert main([str(p), "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    f = data["files"][0]
    assert f["file"] == "demo.srt"
    assert f["count"] == 3 and f["over_threshold"] == 1 and f["skipped"] == 0
    assert f["mean"] == pytest.approx(58 / 3)
    assert f["p50"] == 20.0 and f["max"] == 30.0
    assert data["global"]["count"] == 3
    assert data["global"]["over_threshold"] == 1
    assert data["scenes"] is None                      # 未接遥测


def test_main_telemetry_scene_aggregation(tmp_path, capsys):
    """--telemetry 场景聚合：按 audio_duration_s 累计窗口归属条目中点。"""
    p = tmp_path / "scene.srt"
    p.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\n一二三四五六七八\n\n"
        "2\n00:00:02,800 --> 00:00:03,800\nabcdefghijklmnopqrst\n",
        encoding="utf-8")
    tel = tmp_path / "demo.asr_telemetry.jsonl"
    tel.write_text(
        '{"scene": 1, "audio_duration_s": 2.5}\n'
        '{"scene": 2, "audio_duration_s": 2.0}\n', encoding="utf-8")
    assert main([str(p), "--json", "--telemetry", str(tel)]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["scenes"]["1"] == {"count": 1, "mean": 8.0}
    assert data["scenes"]["2"] == {"count": 1, "mean": 20.0}


def test_aggregate_by_scene_unmapped_entries_dropped():
    """场景窗口外条目不入表；时长非法/≤0 的场景不建窗口。"""
    scenes = {1: {"audio_duration_s": 1.0}, 2: {"audio_duration_s": 0.0},
              "bad": {"audio_duration_s": "x"}}
    rows = [(0.5, 8.0), (5.0, 20.0)]
    out = aggregate_by_scene(scenes, rows)
    assert out == {1: {"count": 1, "mean": 8.0}}


def test_main_missing_telemetry_no_crash(tmp_path, capsys):
    """--telemetry 路径不存在：不炸、stderr 提示、分布照常输出、退出码 0。"""
    p = _write_srt(tmp_path)
    rc = main([str(p), "--telemetry", str(tmp_path / "no.jsonl")])
    assert rc == 0
    captured = capsys.readouterr()                 # 一次性取回，防二次取空
    assert "telemetry" in captured.err.lower()
    assert "demo.srt" in captured.out


def test_main_missing_srt_file_stderr_exit2(tmp_path, capsys):
    """输入文件不存在：stderr 报错并退出码 2（沿 e3_benchmark 惯例）。"""
    rc = main([str(tmp_path / "missing.srt")])
    assert rc == 2
    assert "missing.srt" in capsys.readouterr().err
