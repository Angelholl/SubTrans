"""missed_insert 单测（3.0 批3 3A）：三维置信门全分支 + 插入通道恒等式。

全程离线纯函数，零网络零 whisper；置信阈值同源断言（asr_meta/quality_
report 常量复用不复制）也在此钉住（防口径漂移）。
"""
import pytest
from pytest import approx

from subtransjav.refine import missed_insert as mi
from subtransjav.refine.asr_meta import (
    _TRUST_MAX_COMPRESSION_RATIO,
    _TRUST_MIN_MEAN_LOGPROB,
    _TRUST_NO_SPEECH_PROB,
)
from subtransjav.refine.quality_report import _CPS_CJK_BASE, _CPS_TOLERANCE

T_WINDOW = "00:00:05,000 --> 00:00:07,000"   # 2s 间隙窗口


def _good_segment(**overrides):
    seg = {"start": 0.0, "end": 2.0, "text": "本当にすみません",
           "no_speech_prob": 0.02, "avg_logprob": -0.25,
           "compression_ratio": 1.2}
    seg.update(overrides)
    return seg


def _good_windows():
    """窗口内 1.5s 语音能量（>1s，不触发 ≤1s 放弃）。"""
    return {T_WINDOW: [(5.0, 6.5)]}


# ---------------------------------------------------------------------------
# classify_transcript：判定序＝判空 → ≤1s → 三维 → 重复 → 荒谬 → language
# → 拟声 → high
# ---------------------------------------------------------------------------

def test_classify_empty_transcript():
    v = mi.classify_transcript(T_WINDOW, [], "", _good_windows())
    assert v == {"grade": "empty", "reasons": ["empty_transcript"]}
    v = mi.classify_transcript(T_WINDOW, [_good_segment()], "   ",
                               _good_windows())
    assert v["grade"] == "empty"


def test_classify_speech_le_1s_boundary_exact_rejected():
    """边界钉：语音能量恰 =1.0s 一律放弃（owner 终裁措辞「≤1s」）。"""
    v = mi.classify_transcript(T_WINDOW, [_good_segment()],
                               "本当にすみません", _good_windows(),
                               overlap_s=1.0)
    assert v["grade"] == "low"
    assert v["reasons"][0] == "speech_le_1s"


def test_classify_speech_above_1s_passes_gate():
    v = mi.classify_transcript(T_WINDOW, [_good_segment()],
                               "本当にすみません", _good_windows(),
                               overlap_s=1.01)
    assert v["grade"] == "high"


def test_classify_speech_windows_intersection_used():
    """无 overlap_s 时由 speech_windows 与窗口交集计算。"""
    windows = {T_WINDOW: [(5.0, 5.8)]}          # 交集 0.8s ≤1s
    v = mi.classify_transcript(T_WINDOW, [_good_segment()],
                               "本当にすみません", windows)
    assert v["grade"] == "low" and v["reasons"][0] == "speech_le_1s"


def test_classify_energy_gate_skipped_on_error_or_missing():
    """C18：能量数据缺失（__error/键缺省）跳过 ≤1s 门，不静默判死。"""
    v = mi.classify_transcript(T_WINDOW, [_good_segment()],
                               "本当にすみません", {"__error": "无媒体"})
    assert v["grade"] == "high"
    v = mi.classify_transcript(T_WINDOW, [_good_segment()],
                               "本当にすみません", {})
    assert v["grade"] == "high"


def test_classify_confidence_three_dimensions():
    """三维置信（阈值同源 asr_meta._TRUST_*；nsp=max、logprob=mean）。"""
    base = dict(text="本当にすみません")
    v = mi.classify_transcript(
        T_WINDOW, [_good_segment(no_speech_prob=0.61)], base["text"],
        _good_windows(), overlap_s=1.5)
    assert v["reasons"] == ["no_speech_prob_over"]
    v = mi.classify_transcript(
        T_WINDOW, [_good_segment(avg_logprob=-1.01)], base["text"],
        _good_windows(), overlap_s=1.5)
    assert v["reasons"] == ["avg_logprob_under"]
    v = mi.classify_transcript(
        T_WINDOW, [_good_segment(compression_ratio=2.41)], base["text"],
        _good_windows(), overlap_s=1.5)
    assert v["reasons"] == ["compression_ratio_over"]
    # 边界内不触发（恰在阈值上不判低：判定条件为严格大于/小于）
    v = mi.classify_transcript(
        T_WINDOW, [_good_segment(no_speech_prob=0.6, avg_logprob=-1.0,
                                 compression_ratio=2.4)], base["text"],
        _good_windows(), overlap_s=1.5)
    assert v["grade"] == "high"


def test_classify_repeat_loop_signal():
    """假名单元平铺（source_hallucination 同源信号）→ low。"""
    v = mi.classify_transcript(T_WINDOW, [_good_segment()],
                               "あいうあいうあいう", _good_windows(),
                               overlap_s=1.5)
    assert v["grade"] == "low" and "repeat_loop" in v["reasons"]


def test_classify_absurd_single_char_and_density():
    v = mi.classify_transcript(T_WINDOW, [_good_segment()],
                               "あ" * 8, _good_windows(), overlap_s=1.5)
    assert v["grade"] == "low" and "absurd_single_char" in v["reasons"]
    # 密度：30 个互异字符 / 1.05s ≈ 28.6 chars/s > 3×CPS 上限（≈27.6）
    dense = "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほ"
    v = mi.classify_transcript(T_WINDOW, [_good_segment()], dense,
                               _good_windows(), overlap_s=1.05)
    assert v["grade"] == "low" and "absurd_density" in v["reasons"]


def test_classify_language_not_ja():
    v = mi.classify_transcript(T_WINDOW, [_good_segment()], "Hello there",
                               _good_windows(), overlap_s=1.5,
                               language="en")
    assert v["grade"] == "low" and v["reasons"] == ["language_not_ja"]


def test_classify_nonsense_syllables():
    """纯拟声（source_hallucination nonsense_syllables 同源）→ low。

    文本构造避开 repeat_loop（3-gram 主导占比恰 0.5 不超阈）只命中
    假名内连 repeats ≥6 的 nonsense 信号。"""
    v = mi.classify_transcript(T_WINDOW, [_good_segment()],
                               "ああああああいうえお", _good_windows(),
                               overlap_s=1.5)
    assert v["grade"] == "low" and v["reasons"] == ["nonsense_syllables"]


def test_classify_high_pass_all_gates():
    v = mi.classify_transcript(T_WINDOW, [_good_segment()],
                               "本当にすみません", _good_windows(),
                               overlap_s=1.5)
    assert v == {"grade": "high", "reasons": []}


def test_thresholds_same_source_pins():
    """同源钉：missed_insert 阈值＝asr_meta/quality_report 常量本身
    （防复制漂移）。"""
    assert mi._TRUST_NO_SPEECH_PROB == _TRUST_NO_SPEECH_PROB
    assert mi._TRUST_MIN_MEAN_LOGPROB == _TRUST_MIN_MEAN_LOGPROB
    assert mi._TRUST_MAX_COMPRESSION_RATIO == _TRUST_MAX_COMPRESSION_RATIO
    assert approx(_CPS_CJK_BASE * _CPS_TOLERANCE) == mi.INSERT_CPS_CAP
    assert approx(_CPS_CJK_BASE * _CPS_TOLERANCE * 3.0) \
        == mi.ABSURD_CHARS_PER_SEC


# ---------------------------------------------------------------------------
# insert_candidates + assert_insert_invariants（C15 独立恒等式）
# ---------------------------------------------------------------------------

def _entries():
    return [
        {"index": 1, "timing": "00:00:00,000 --> 00:00:04,000",
         "text": "先輩、お疲れ様です"},
        {"index": 2, "timing": "00:00:10,000 --> 00:00:14,000",
         "text": "次の撮影に行きましょう"},
    ]


def test_insert_candidates_order_and_timing():
    picks = [{"timing": T_WINDOW, "text": "本当にすみません"}]
    new = mi.insert_candidates(_entries(), picks)
    assert len(new) == 3
    assert [e["text"] for e in new] == ["先輩、お疲れ様です",
                                        "本当にすみません",
                                        "次の撮影に行きましょう"]
    # 时长＝min(窗口 4s, max(8 字/9.2≈0.87, 0.5))＝0.87s
    assert new[1]["timing"] == "00:00:05,000 --> 00:00:05,870"
    # 重编号收尾（与 build_srt 输出编号一致）
    assert [e["index"] for e in new] == [1, 2, 3]
    # 入参不被改动（纯函数）
    assert len(_entries()) == 2


def test_insert_candidates_dur_compression_and_floor():
    # 长文本：换算时长超窗口（2s）→ 受限于窗口（end=窗口终点）
    long_text = "こ" * 92
    new = mi.insert_candidates(_entries(), [{"timing": T_WINDOW,
                                             "text": long_text}])
    assert new[1]["timing"] == "00:00:05,000 --> 00:00:07,000"
    # 短文本：换算时长低于 0.5s 下限 → 时长=0.5s
    new = mi.insert_candidates(_entries(), [{"timing": T_WINDOW,
                                             "text": "あ"}])
    assert new[1]["timing"] == "00:00:05,000 --> 00:00:05,500"


def test_insert_candidates_unparseable_pick_skipped():
    new = mi.insert_candidates(_entries(), [{"timing": "garbage",
                                             "text": "あ"}])
    assert len(new) == 2


def test_assert_insert_invariants_pass_and_tamper():
    picks = [{"timing": T_WINDOW, "text": "本当にすみません"}]
    orig = _entries()
    new = mi.insert_candidates(orig, picks)
    mi.assert_insert_invariants(orig, new, picks)   # 不抛
    # 恒等式失败面 1：条目数
    with pytest.raises(AssertionError):
        mi.assert_insert_invariants(orig, new[:2], picks)
    # 恒等式失败面 2：原块文本被改动
    tampered = [dict(e) for e in new]
    tampered[0]["text"] = "被改了"
    with pytest.raises(AssertionError):
        mi.assert_insert_invariants(orig, tampered, picks)
    # 恒等式失败面 3：新块越窗（timing 挪出窗口）
    moved = [dict(e) for e in new]
    moved[1]["timing"] = "00:00:20,000 --> 00:00:20,870"
    with pytest.raises(AssertionError):
        mi.assert_insert_invariants(orig, moved, picks)


def test_insert_candidates_multiple_picks_chronological():
    picks = [
        {"timing": "00:00:10,500 --> 00:00:12,000", "text": "後でね"},
        {"timing": T_WINDOW, "text": "本当にすみません"},
    ]
    new = mi.insert_candidates(_entries(), picks)
    assert [e["text"] for e in new] == ["先輩、お疲れ様です",
                                        "本当にすみません",
                                        "次の撮影に行きましょう",
                                        "後でね"]
    mi.assert_insert_invariants(_entries(), new, picks)
