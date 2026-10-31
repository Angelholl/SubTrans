# 3.1.0 测量地基·评测 harness 钉（D2026-1028-03 骨架批）。
# 纯合成夹具：零网络、零模型、零 ffmpeg 依赖（窗口一律外注入）。
import json
import pathlib

import pytest

from subtransjav.refine.eval_baseline import (
    WILSON_Z_95,
    _safe_stem,
    _timing_span,
    agreement,
    cps_stats,
    evaluate,
    hallucination_proxy,
    omission_proxy,
    report_markdown,
    run_engine,
    speech_windows_full,
    wilson_interval,
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
        # p=0 理论下界 0；z 统一为高精度值后浮点路径残差 ~1e-18 级
        # （z=1.96 时代恰好舍入 0），放宽到 1e-12 量级断言
        assert wilson_lower_bound(0, 100) == pytest.approx(0.0, abs=1e-12)
        assert wilson_lower_bound(100, 100) == pytest.approx(0.963, abs=1e-2)
        assert 0.0 <= wilson_lower_bound(3, 7) <= 1.0


class TestHallucinationProxy:
    def test_fully_covered_line_not_suspect(self):
        entries = [_ent(1, 1.5, 4.0, "あ")]
        r = hallucination_proxy(entries, WIN)
        assert r == {"lines": 1, "suspect": 0, "ratio": 0.0,
                     "wilson": wilson_interval(0, 1)}

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
            "lines": 0, "suspect": 0, "ratio": None, "wilson": None}


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


# ------------------------------------------------ 3.1.1 件B B1（D2026-1030-02）
# Wilson 区间增补＋z 统一＋CLI 缺省 --out（D2026-1029-11 ④ 联动）。

def test_wilson_z_unified_across_modules():
    """z 统一钉：eval_baseline 与 tools/c22_calibration 两处 z 同值
    1.959963984540054（D2026-1029-11 ④；防漂移物理钉）。"""
    import importlib.util
    tool_path = (pathlib.Path(__file__).resolve().parents[1] / "tools"
                 / "c22_calibration.py")
    spec = importlib.util.spec_from_file_location("c22_cal_z_pin", tool_path)
    assert spec is not None and spec.loader is not None
    c22 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(c22)
    assert WILSON_Z_95 == 1.959963984540054
    assert c22._WILSON_Z == WILSON_Z_95


class TestWilsonInterval:
    def test_symmetry_and_endpoints(self):
        assert wilson_interval(0, 0) == {"lo": 0.0, "hi": 0.0}
        iv = wilson_interval(72, 72)
        assert iv["lo"] == pytest.approx(0.9493, abs=1e-3)
        assert 0.0 < iv["lo"] < iv["hi"] <= 1.0
        assert iv["hi"] == pytest.approx(
            1.0 - wilson_lower_bound(0, 72), abs=1e-9)
        iv2 = wilson_interval(3, 10)
        assert iv2["lo"] <= 0.3 <= iv2["hi"]

    def test_lo_hi_rounded(self):
        iv = wilson_interval(1, 3)
        for v in iv.values():
            assert round(v, 4) == v


class TestEvaluateWilsonFields:
    def test_hallucination_has_wilson_window_missing_none(self):
        entries = [_ent(1, 1.5, 4.0, "あ")]
        r = hallucination_proxy(entries, WIN)
        assert r["wilson"]["lo"] <= r["wilson"]["hi"]
        # 窗口缺失＝整个 proxy 为 None（诚实退化），非 wilson 键 None
        assert hallucination_proxy(entries, None) is None

    def test_agreement_rate_wilson_fields(self):
        a = [_ent(1, 1.0, 3.0, "あ"), _ent(2, 6.0, 8.0, "い")]
        b = [_ent(1, 1.0, 3.0, "あ")]
        r = agreement(a, b)
        assert r["rate_a_wilson"] is not None
        assert r["rate_a_wilson"]["lo"] <= r["rate_a_wilson"]["hi"]
        assert r["rate_b_wilson"] is not None

    def test_omission_and_cps_carry_no_wilson(self):
        entries = [_ent(1, 1.5, 4.0, "ありがとう ございます")]
        om = omission_proxy(entries, WIN)
        assert "wilson" not in om
        cp = cps_stats(entries)
        assert "wilson" not in cp


def test_default_out_dir_is_data_root_reports_eval(monkeypatch, tmp_path):
    """CLI 缺省 --out＝数据根 reports/eval/（D2026-1030-02 B1 定案）。"""
    import subtransjav.refine.eval_baseline as eb
    monkeypatch.setattr(eb.paths, "data_subdir",
                        lambda *parts: str(tmp_path.joinpath(*parts)))
    assert eb.default_out_dir() == str(tmp_path / "reports" / "eval")


# ------------------------------------------------ 补卡1 边界扩补（D2026-1030-07 白名单第 1 类）
# 只增不改：下列新钉逐条对齐实码分支（subtransjav/refine/eval_baseline.py），
# 合成夹具零 ffmpeg/网络/模型；I/O 分支一律 monkeypatch，不真跑子进程。


class TestTimingSpanBoundaries:
    def test_zero_duration_returns_none(self):
        # eval_baseline.py:92-101：end <= start → None（零时长行丢弃）
        assert _timing_span("00:00:01,000 --> 00:00:01,000") is None

    def test_reversed_range_returns_none(self):
        # 同上：乱序行（end < start）→ None；正常行返回 (start, end) 元组
        assert _timing_span("00:00:05,000 --> 00:00:02,000") is None
        assert _timing_span("00:00:00,000 --> 00:00:02,500") == (0.0, 2.5)

    def test_unparsable_returns_none(self):
        # :92-95：正则不匹配 → None
        assert _timing_span("") is None
        assert _timing_span("1 --> 2") is None


class TestOmissionProxyBoundaries:
    def test_empty_window_list_total_zero(self):
        # :167-169：windows=[] → total<=0 退化分支（ratio=None，不当成 0 报告）
        assert omission_proxy([_ent(1, 1.0, 3.0, "あ")], []) == {
            "speech_s": 0.0, "uncovered_s": 0.0, "ratio": None}

    def test_ratio_capped_at_one(self):
        # :177-178：min(1.0, uncovered/total) 上限。实码里 gap 逐窗截到窗长、
        # uncovered<=total 恒成立（窗口自身重叠时同样成立），故 clamp 为结构性
        # 保险而非法可达路径；此钉锁「无行覆盖时 ratio 恰为 1.0、绝不越界」。
        windows = [(0.0, 4.0), (2.0, 6.0)]
        r = omission_proxy([], windows)
        assert r["speech_s"] == pytest.approx(8.0)
        assert r["uncovered_s"] == pytest.approx(8.0)
        assert r["ratio"] == 1.0


class TestHallucinationMinOverlapBoundary:
    def test_exact_threshold_not_suspect(self):
        # :140/:152-155：covered/dur < min_overlap 为严格小于（无等号）；
        # 行 0-1s 与窗口 0-0.5s 恰重叠 50%，min_overlap=0.5 时不算可疑。
        entries = [_ent(1, 0.0, 1.0, "あ")]
        r = hallucination_proxy(entries, [(0.0, 0.5)], min_overlap=0.5)
        assert r["suspect"] == 0 and r["ratio"] == 0.0
        # 阈值略高于实际覆盖率即翻为可疑，锁严格小于口径
        r2 = hallucination_proxy(entries, [(0.0, 0.5)], min_overlap=0.51)
        assert r2["suspect"] == 1 and r2["ratio"] == 1.0


class TestAgreementBoundaries:
    def test_empty_inputs_rate_none(self):
        # :226-229：n_a==0 / n_b==0 → rate_* 与 wilson 均 None
        r = agreement([], [])
        assert r["matched"] == 0 and r["lines_a"] == 0 and r["lines_b"] == 0
        assert r["rate_a"] is None and r["rate_b"] is None
        assert r["rate_a_wilson"] is None and r["rate_b_wilson"] is None
        # 仅一侧为空：另一侧分母非 0，rate 为 0.0 而非 None
        r2 = agreement([_ent(1, 1.0, 3.0, "あ")], [])
        assert r2["rate_a"] == 0.0 and r2["rate_b"] is None

    def test_iou_exactly_threshold_matched(self):
        # :204：iou >= iou_threshold 含等号。A(0,2)∩B(0,1)=1，并集 2 → IoU 恰 0.5
        a = [_ent(1, 0.0, 2.0, "あ")]
        b = [_ent(1, 0.0, 1.0, "あ")]
        assert agreement(a, b)["matched"] == 1

    def test_text_sim_exactly_threshold_matched(self):
        # :216：sim >= sim_threshold 含等号；"abcde"/"abcxy" 匹配块 3 字、
        # 总长 10 → ratio 恰 0.6，算匹配。
        a = [_ent(1, 1.0, 3.0, "abcde")]
        b = [_ent(1, 1.0, 3.0, "abcxy")]
        assert agreement(a, b)["matched"] == 1
        # 低于阈值（"ab" 两块 /10 = 0.4）不匹配，锁边界不放水
        c = [_ent(1, 1.0, 3.0, "abxyz")]
        assert agreement(a, c)["matched"] == 0

    def test_touching_intervals_zero_overlap(self):
        # :198：inter==0（区间首尾相接）→ continue，不产候选对；
        # 两侧行数照计，rate 为 0.0（非 None）
        a = [_ent(1, 1.0, 2.0, "あ")]
        b = [_ent(1, 2.0, 3.0, "あ")]
        r = agreement(a, b)
        assert r["matched"] == 0
        assert r["lines_a"] == 1 and r["lines_b"] == 1
        assert r["rate_a"] == 0.0 and r["rate_b"] == 0.0


class TestCpsMixedRows:
    def test_bad_timing_rows_skipped(self):
        # :237-248：非法 timing 行 continue（不进 durs/values）；lines 取合法行数。
        # 合法 1 行（10 字 / 2s = 5.0）+ 零时长行 + 坏 timing 行 → lines=1
        entries = [
            _ent(1, 0.0, 2.0, "あ" * 10),
            {"index": 2, "timing": "00:00:03,000 --> 00:00:03,000", "text": "い"},
            {"index": 3, "timing": "garbage", "text": "う"},
        ]
        r = cps_stats(entries)
        assert r["lines"] == 1
        assert r["cps_p50"] == 5.0 and r["cps_p90"] == 5.0 and r["cps_max"] == 5.0
        assert r["avg_dur_s"] == 2.0
        # 全非法 → 空分支 lines=0
        assert cps_stats([{"timing": "bad", "text": "x"}])["lines"] == 0


class TestSpeechWindowsDegradation:
    def test_ffmpeg_missing_returns_error(self, monkeypatch):
        # :109-113：_find_ffmpeg() is None → {"__error": "未检测到 ffmpeg"}（禁真跑）
        from subtransjav.refine import audio_detect
        monkeypatch.setattr(audio_detect, "_find_ffmpeg", lambda: None)
        assert speech_windows_full("whatever.mp4") == {"__error": "未检测到 ffmpeg"}

    def test_missing_media_returns_error(self, monkeypatch, tmp_path):
        # :114-115：ffmpeg 在但媒体不存在/为空 → {"__error": "无媒体文件"}
        from subtransjav.refine import audio_detect
        monkeypatch.setattr(audio_detect, "_find_ffmpeg", lambda: "ffmpeg-stub")
        assert speech_windows_full(str(tmp_path / "gone.mp4")) == {"__error": "无媒体文件"}
        assert speech_windows_full("") == {"__error": "无媒体文件"}

    def test_detection_exception_returns_error(self, monkeypatch):
        # :135：任一步抛异常 → 兜底 {"__error": "语音窗口检测失败: ..."}，绝不外抛
        from subtransjav.refine import audio_detect

        def _boom():
            raise RuntimeError("boom")

        monkeypatch.setattr(audio_detect, "_find_ffmpeg", _boom)
        assert speech_windows_full("whatever.mp4") == {"__error": "语音窗口检测失败: boom"}


class TestRunEngineUnregistered:
    def test_unregistered_engine_raises(self):
        # :269-276：未注册引擎 → RuntimeError，消息带引擎 id 与安装链提示
        with pytest.raises(RuntimeError) as ei:
            run_engine("ct2", "a.mp4", "work")
        assert "ct2" in str(ei.value)
        assert "未注册" in str(ei.value)


class TestWriteReportEscapeGuard:
    def test_escape_stem_raises_value_error(self, monkeypatch, tmp_path):
        # :379-380：os.pardir in parts / parent != base 越界守卫（双保险）。
        # 正常路径 stem 已被白名单净化不可越界，此处 monkeypatch 净化函数注入
        # 越界前缀以触达守卫，验证仍抛 ValueError 且不落盘。
        import subtransjav.refine.eval_baseline as eb
        monkeypatch.setattr(eb, "_safe_stem", lambda _s: "../evil")
        out = tmp_path / "out"
        with pytest.raises(ValueError) as ei:
            eb.write_report({"schema": "x"}, str(out), "any")
        assert "越界" in str(ei.value)
        assert not (tmp_path / "evil-baseline.json").exists()


def test_safe_stem_all_illegal_falls_back_to_eval():
    # :364-366：全非法字符 → 净化后 strip("._") 为空 → "eval"；纯点号同样
    assert _safe_stem("///") == "eval"
    assert _safe_stem("..") == "eval"


def test_report_markdown_windows_error_degradation(monkeypatch, tmp_path):
    # :328-330：windows_error 非空 → 退化提示行 + 窗口类指标 null（窗口缺失）。
    # 窗口检测 monkeypatch 隔断，避免环境 ffmpeg 差异影响判定。
    import subtransjav.refine.eval_baseline as eb
    monkeypatch.setattr(eb, "speech_windows_full", lambda _p: {"__error": "无媒体文件"})
    entries = [_ent(1, 1.0, 3.0, "あ")]
    pa = make_srt(tmp_path, "a.srt", entries)
    rep = eb.evaluate(str(tmp_path / "gone.mp4"), {"upstream": pa})
    assert rep["windows_error"] == "无媒体文件"
    assert rep["engines"]["upstream"]["omission_proxy"] is None
    md = eb.report_markdown(rep)
    assert "> 语音窗口检测退化：无媒体文件" in md
    assert "幻听代理（低重叠行占比，越低越好）：null（窗口缺失）" in md
    assert "漏听代理（语音未覆盖占比，越低越好）：null（窗口缺失）" in md


def test_main_derives_stem_from_media_name(monkeypatch, tmp_path):
    # :416-417：media 非空且未给 --stem → stem=媒体名去扩展名；窗口检测 monkeypatch 隔断
    import subtransjav.refine.eval_baseline as eb
    monkeypatch.setattr(eb, "speech_windows_full", lambda _p: {"__error": "无媒体文件"})
    entries = [_ent(1, 1.0, 3.0, "あ")]
    pa = make_srt(tmp_path, "a.srt", entries)
    out = str(tmp_path / "r")
    rc = eb.main(["--media", str(tmp_path / "clip.mp4"),
                  "--srt", "upstream=" + pa, "--out", out])
    assert rc == 0
    assert (tmp_path / "r" / "clip-baseline.json").exists()
    assert (tmp_path / "r" / "clip-baseline.md").exists()
