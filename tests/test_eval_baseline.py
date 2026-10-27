# 3.1.0 测量地基·评测 harness 钉（D2026-1028-03 骨架批）。
# 纯合成夹具：零网络、零模型、零 ffmpeg 依赖（窗口一律外注入）。
import json
import pathlib

import pytest

from subtransjav.refine.eval_baseline import (
    _safe_stem,
    agreement,
    cps_stats,
    evaluate,
    hallucination_proxy,
    omission_proxy,
    report_markdown,
    wilson_lower_bound,
    write_report,
)


def make_srt(tmp_path, name, entries):
    from subtransjav.refine.filters import build_srt
    p = tmp_path / name
    p.write_text(build_srt(entries), encoding="utf-8")
    return str(p)


def _ent(idx: int, start: float, end: float, text: str) -> dict:
    def fmt(t: float) -> str:
        h = int(t // 3600)
        m = int((t % 3600) // 60)
        s = t % 60
        return f"{h:02d}:{m:02d}:{int(s):02d},{int(round((s - int(s)) * 1000)):03d}"

    return {"index": idx, "timing": f"{fmt(start)} --> {fmt(end)}", "text": text}


WIN = [(1.0, 5.0), (6.0, 9.0)]


class TestWilson:
    def test_known_value(self):
        # 1/2 → 下界 0.0945（C22 校准实测同款数字；z=1.96）
        assert wilson_lower_bound(1, 2) == pytest.approx(0.0945, abs=1e-3)

    def test_bounds_and_zero_n(self):
        assert wilson_lower_bound(0, 0) == 0.0
        assert wilson_lower_bound(0, 100) == 0.0
        assert wilson_lower_bound(100, 100) == pytest.approx(0.963, abs=1e-2)
        assert 0.0 <= wilson_lower_bound(3, 7) <= 1.0


class TestHallucinationProxy:
    def test_fully_covered_line_not_suspect(self):
        entries = [_ent(1, 1.5, 4.0, "あ")]
        r = hallucination_proxy(entries, WIN)
        assert r == {"lines": 1, "suspect": 0, "ratio": 0.0}

    def test_silent_span_line_is_suspect(self):
        # 5.0-6.0 落在两窗口之间的静音带（重叠 0）
        entries = [_ent(1, 5.0, 6.0, "あ")]
        r = hallucination_proxy(entries, WIN)
        assert r["suspect"] == 1
        assert r["ratio"] == 1.0

    def test_partial_overlap_below_threshold(self):
        # 行 4.8-6.2（时长 1.4s），仅跨窗口边缘 0.4s=28.6% < 30% → 可疑
        entries = [_ent(1, 4.8, 6.2, "あ")]
        assert hallucination_proxy(entries, WIN)["suspect"] == 1

    def test_none_on_missing_windows(self):
        assert hallucination_proxy([_ent(1, 0, 1, "あ")], None) is None

    def test_no_valid_spans(self):
        assert hallucination_proxy([{"timing": "bad", "text": "x"}], WIN) == {
            "lines": 0, "suspect": 0, "ratio": None}


class TestOmissionProxy:
    def test_full_coverage(self):
        entries = [_ent(1, 1.0, 5.0, "あ"), _ent(2, 6.0, 9.0, "い")]
        r = omission_proxy(entries, WIN)
        assert r["ratio"] == 0.0
        assert r["speech_s"] == pytest.approx(7.0)

    def test_uncovered_speech(self):
        # 只盖住第一窗口一半：1.0-3.0；窗口 1(1-5) 缺 2s，窗口 2(6-9) 全缺 3s
        entries = [_ent(1, 1.0, 3.0, "あ")]
        r = omission_proxy(entries, WIN)
        assert r["uncovered_s"] == pytest.approx(5.0)
        assert r["ratio"] == pytest.approx(5.0 / 7.0, abs=1e-3)

    def test_none_on_missing_windows(self):
        assert omission_proxy([], None) is None


class TestAgreement:
    def test_identical_srts_full_agreement(self):
        entries = [_ent(1, 1.0, 3.0, "こんにちは"), _ent(2, 6.0, 8.0, "さようなら")]
        r = agreement(entries, entries)
        assert r["matched"] == 2
        assert r["rate_a"] == 1.0 and r["rate_b"] == 1.0

    def test_text_mismatch_not_matched(self):
        a = [_ent(1, 1.0, 3.0, "こんにちは")]
        b = [_ent(1, 1.0, 3.0, "まったく別の文章です")]
        r = agreement(a, b)
        assert r["matched"] == 0

    def test_greedy_matching_no_double_use(self):
        # A 两行对 B 一行：贪婪配 IoU 最高者，另一行落空
        a = [_ent(1, 1.0, 2.0, "あ"), _ent(2, 2.2, 3.0, "い")]
        b = [_ent(1, 1.0, 2.0, "あ")]
        r = agreement(a, b)
        assert r["matched"] == 1
        assert r["rate_a"] == 0.5 and r["rate_b"] == 1.0


class TestCps:
    def test_values_and_percentiles(self):
        entries = [_ent(1, 0.0, 2.0, "あ" * 10), _ent(2, 10.0, 12.0, "い" * 4)]
        r = cps_stats(entries)
        assert r["lines"] == 2
        assert r["cps_p50"] == pytest.approx(2.0)   # 最近秩 p50（n=2 取下秩）
        assert r["cps_p90"] == pytest.approx(5.0)
        assert r["cps_max"] == 5.0
        assert r["avg_dur_s"] == 2.0

    def test_empty(self):
        r = cps_stats([])
        assert r["lines"] == 0 and r["cps_p50"] is None


class TestEvaluateAndReport:
    def test_report_shape_and_degradation(self, tmp_path):
        entries = [_ent(1, 1.0, 3.0, "こんにちは")]
        pa = make_srt(tmp_path, "a.srt", entries)
        pb = make_srt(tmp_path, "b.srt", entries)
        # media 指向不存在文件 → 窗口诚实退化，窗口类指标 null
        rep = evaluate(str(tmp_path / "missing.mp4"), {"upstream": pa, "ct2": pb})
        assert rep["windows_error"]
        assert rep["engines"]["upstream"]["hallucination_proxy"] is None
        assert rep["engines"]["ct2"]["omission_proxy"] is None
        assert rep["pairs"]["ct2+upstream"]["matched"] == 1
        assert rep["schema"] == "subtransjav.eval_baseline/1"

    def test_report_with_injected_windows(self, tmp_path):
        entries = [_ent(1, 1.0, 3.0, "こんにちは")]
        pa = make_srt(tmp_path, "a.srt", entries)
        rep = evaluate("x.mp4", {"upstream": pa}, windows=[(1.0, 3.0)])
        assert rep["windows_error"] is None
        assert rep["engines"]["upstream"]["omission_proxy"]["ratio"] == 0.0
        md = report_markdown(rep)
        assert "幻听代理" in md and "漏听代理" in md and "双引擎一致率" not in md

    def test_write_report_roundtrip(self, tmp_path):
        entries = [_ent(1, 1.0, 3.0, "あ")]
        pa = make_srt(tmp_path, "a.srt", entries)
        rep = evaluate("", {"upstream": pa}, windows=[(1.0, 3.0)])
        out = tmp_path / "out"
        json_path, md_path = write_report(rep, str(out), "movie/..\\bad name")
        # stem 白名单净化：分隔符与点线全替 _
        assert json_path.endswith("bad_name-baseline.json")
        data = json.loads(pathlib.Path(json_path).read_text(encoding="utf-8"))
        assert data["schema"] == "subtransjav.eval_baseline/1"
        assert md_path.endswith("-baseline.md")

    def test_safe_stem(self):
        assert _safe_stem("abc.def-1") == "abc.def-1"
        assert _safe_stem("a/b\\c") == "a_b_c"
        assert _safe_stem("") == "eval"
        assert _safe_stem("x" * 200).startswith("x") and len(_safe_stem("x" * 200)) == 80


class TestCli:
    def test_main_happy_and_bad_input(self, tmp_path, capsys):
        from subtransjav.refine.eval_baseline import main
        entries = [_ent(1, 1.0, 3.0, "あ")]
        pa = make_srt(tmp_path, "a.srt", entries)
        out = str(tmp_path / "r")
        rc = main(["--media", "", "--srt", "upstream=" + pa, "--out", out, "--stem", "t1"])
        assert rc == 0
        assert (tmp_path / "r" / "t1-baseline.json").exists()
        rc2 = main(["--media", "", "--srt", "noequals", "--out", out])
        assert rc2 == 2
        assert "ENGINE=PATH" in capsys.readouterr().out
        rc3 = main(["--media", "", "--srt", "upstream=" + str(tmp_path / "gone.srt"),
                    "--out", out])
        assert rc3 == 2
