"""polish 清洗层单测：白名单语义、时间轴顺序、出口不变量、幂等、纯函数。"""

import copy
import unicodedata

from subtransjav.refine.polish import POLICY_DEFAULTS, polish_entries

STATS_KEYS = {
    "whitespace_collapsed",
    "music_fixed",
    "italic_tags_reported",
    "i_tags_repaired",
    "gt_removed",
    "periods_stripped",
    "quotes_normalized",
    "lines_rewrapped",
    "long_clamped",
    "short_reported",
    "overlaps_resolved",
    "gaps_enforced",
    "dropped_empty",
}


def _ts(ms):
    h, rem = divmod(int(ms), 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, milli = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{milli:03d}"


def _parse(value):
    h, m, rest = value.split(":")
    s, milli = rest.split(",")
    return int(h) * 3_600_000 + int(m) * 60_000 + int(s) * 1000 + int(milli)


def _entry(index, start, end, text):
    return {"index": index, "timing": f"{_ts(start)} --> {_ts(end)}", "text": text}


def _span(entry):
    left, right = entry["timing"].split("-->")
    return _parse(left.strip()), _parse(right.strip())


def _width(text):
    return sum(1.0 if unicodedata.east_asian_width(c) in ("W", "F") else 0.5 for c in text)


def _one(text, options=None):
    out, stats = polish_entries([_entry(1, 0, 2000, text)], options)
    assert len(out) == 1
    return out[0]["text"], stats


# --- 常量表与 stats 键（单一真值源） -----------------------------------------


def test_policy_defaults_single_source():
    assert POLICY_DEFAULTS == {
        "strip_final_period": True,
        "quote_style": "corner",
        "max_line_chars": 16,
        "max_lines": 2,
        "min_duration_ms": 833,
        "max_duration_ms": 7000,
        "min_gap_ms": 83.416,
        "remove_dialogue_gt": False,
        "extend_short_into_gap": False,
    }


def test_stats_keys_pinned():
    _, stats = polish_entries([_entry(1, 0, 2000, "甲")])
    assert set(stats) == STATS_KEYS
    assert all(isinstance(v, int) for v in stats.values())


# --- 规则 1：空白折叠（保留行首对话破折号） ---------------------------------


def test_whitespace_collapsed_and_dash_kept():
    text, stats = _one("   - 你好   世界\t啊 ")
    assert text == "- 你好 世界 啊"
    assert stats["whitespace_collapsed"] == 1


def test_whitespace_already_clean_is_noop():
    text, stats = _one("你好 世界")
    assert text == "你好 世界"
    assert stats["whitespace_collapsed"] == 0


# --- 规则 2：♪ 乱码修复（绝不删除 ♪） ---------------------------------------


def test_music_mojibake_fixed():
    text, stats = _one("â™ª 啦啦啦")
    assert text == "♪ 啦啦啦"
    assert stats["music_fixed"] == 1


def test_music_note_never_removed():
    text, stats = _one("♪♪ 啦啦 ♪")
    assert text == "♪♪ 啦啦 ♪"
    assert stats["music_fixed"] == 0


# --- 规则 3：<i> 只修残缺，成对不动只报告 -----------------------------------


def test_italic_open_only_repaired():
    text, stats = _one("<i>别走")
    assert text == "<i>别走</i>"
    assert stats["i_tags_repaired"] == 1


def test_italic_orphan_close_removed():
    text, stats = _one("别走</i>")
    assert text == "别走"
    assert stats["i_tags_repaired"] == 1


def test_italic_paired_untouched_and_reported():
    text, stats = _one("<i>别走</i>")
    assert text == "<i>别走</i>"
    assert stats["i_tags_repaired"] == 0
    assert stats["italic_tags_reported"] == 1


# --- 规则 4：>> 默认不动，显式开才删 ----------------------------------------


def test_gt_default_kept():
    text, stats = _one(">> 喂，醒醒")
    assert text == ">> 喂，醒醒"
    assert stats["gt_removed"] == 0


def test_gt_option_removes():
    text, stats = _one(">> 喂，醒醒", {"remove_dialogue_gt": True})
    assert text == "喂，醒醒"
    assert stats["gt_removed"] == 1


# --- 规则 5：句末句号去除，？！保留 -----------------------------------------


def test_period_stripped():
    text, stats = _one("我回来了。")
    assert text == "我回来了"
    assert stats["periods_stripped"] == 1


def test_question_and_exclamation_kept():
    text, stats = _one("真的？！")
    assert text == "真的？！"
    assert stats["periods_stripped"] == 0


def test_period_after_question_mark_stripped():
    text, _ = _one("为什么？！。")
    assert text == "为什么？！"


# --- 规则 6：引号派系统一 ---------------------------------------------------


def test_quotes_straight_to_corner():
    text, stats = _one('"你好"')
    assert text == "「你好」"
    assert stats["quotes_normalized"] == 2


def test_quotes_curly_to_corner():
    text, _ = _one("“你好”")
    assert text == "「你好」"


def test_quotes_keep_style_noop():
    text, stats = _one('"你好"', {"quote_style": "keep"})
    assert text == '"你好"'
    assert stats["quotes_normalized"] == 0


def test_quotes_corner_to_curly():
    text, _ = _one("「你好」", {"quote_style": "curly"})
    assert text == "“你好”"


def test_quotes_already_corner_not_counted():
    text, stats = _one("「你好」")
    assert text == "「你好」"
    assert stats["quotes_normalized"] == 0


def test_quotes_unbalanced_untouched():
    text, stats = _one('"你好')
    assert text == '"你好'
    assert stats["quotes_normalized"] == 0


# --- 规则 7：拆行重排 -------------------------------------------------------


def test_long_line_rewrapped_within_limits():
    source = "一" * 20
    text, stats = _one(source)
    lines = text.split("\n")
    assert len(lines) == 2
    assert all(_width(line) <= 16 for line in lines)
    assert "".join(lines) == source
    assert stats["lines_rewrapped"] == 1


def test_wrap_prefers_punctuation_break():
    source = "一二三四五六七八九十十一，二三四五六七八九十"
    text, _ = _one(source)
    lines = text.split("\n")
    assert lines[0] == "一二三四五六七八九十十一，"
    assert "".join(lines) == source


def test_wrap_merges_excess_lines():
    text, stats = _one("甲\n乙\n丙")
    assert text == "甲乙丙"
    assert stats["lines_rewrapped"] == 1


def test_wrap_forced_when_unfittable():
    source = "一" * 30
    text, stats = _one(source, {"max_line_chars": 5, "max_lines": 2})
    lines = text.split("\n")
    assert len(lines) == 2
    assert "".join(lines) == source
    assert stats["lines_rewrapped"] == 1


# --- 时间轴：顺序 ①重叠消解 → ②时长钳制 → ③最小间隔 ------------------------


def test_timing_order_overlap_then_clamp_then_gap():
    entries = [
        _entry(1, 0, 9000, "甲"),        # 超长 + 与乙重叠
        _entry(2, 6000, 7000, "乙"),
        _entry(3, 10000, 20000, "丙"),   # 超长，后接宽间隔
        _entry(4, 25000, 25300, "丁"),   # 300ms 过短
        _entry(5, 25350, 26500, "戊"),   # 与丁间隔 50ms 过小
    ]
    out, stats = polish_entries(entries)

    # ① 重叠：甲 end 回拉到乙 start − min_gap（floor）
    assert _span(out[0]) == (0, 5916)
    # ② 超长：丙缩短到 7000ms；丁 300ms 只报告不延长
    assert _span(out[2]) == (10000, 17000)
    assert _span(out[4]) == (25350, 26500)  # 后条 start 未被前推
    # ③ 小间隔：丁 end 回拉到戊 start − min_gap
    assert _span(out[3]) == (25000, 25266)
    assert stats["overlaps_resolved"] == 1
    assert stats["long_clamped"] == 1
    assert stats["short_reported"] == 1
    assert stats["gaps_enforced"] == 1


def test_short_duration_reported_not_extended():
    entries = [_entry(1, 0, 300, "短"), _entry(2, 5000, 6000, "后")]
    out, stats = polish_entries(entries)
    assert _span(out[0]) == (0, 300)
    assert stats["short_reported"] == 1
    assert stats["long_clamped"] == 0


def test_overlap_zero_duration_defense_pushes_later_start():
    entries = [_entry(1, 0, 100, "甲"), _entry(2, 0, 1000, "乙")]
    out, stats = polish_entries(entries)
    assert _span(out[0]) == (0, 100)
    assert _span(out[1])[0] == 184  # ceil(100 + 83.416)
    assert stats["overlaps_resolved"] == 1
    assert _span(out[1])[0] < _span(out[1])[1]


def test_unchanged_timing_string_is_preserved():
    entry = {
        "index": 1,
        "timing": "00:00:01.000 --> 00:00:02.500",
        "text": "你好",
    }
    out, _ = polish_entries([entry])
    assert out[0]["timing"] == "00:00:01.000 --> 00:00:02.500"


# --- 幂等 / 不变量 / 纯函数 -------------------------------------------------


def _pathological():
    return [
        _entry(1, 0, 9000, "  你好   世界。 "),
        _entry(2, 0, 400, "â™ª 啦啦"),
        _entry(3, 8500, 8600, "  "),
        _entry(4, 9000, 30000, "一" * 40),
        _entry(5, 29000, 31000, ">> 喂"),
        _entry(6, 31000, 32000, "为什么？！。"),
    ]


def test_idempotent():
    once, _ = polish_entries(_pathological())
    twice, _ = polish_entries(once)
    assert twice == once


def test_exit_invariants_on_pathological_input():
    out, stats = polish_entries(_pathological())
    assert stats["dropped_empty"] >= 1
    for entry in out:
        assert entry["text"].strip()
        start, end = _span(entry)
        assert end > start
        assert len(entry["text"].split("\n")) <= POLICY_DEFAULTS["max_lines"]
    for prev, cur in zip(out, out[1:], strict=False):
        assert _span(prev)[1] <= _span(cur)[0]


def test_pure_function_input_not_mutated():
    entries = _pathological()
    snapshot = copy.deepcopy(entries)
    polish_entries(entries)
    assert entries == snapshot


def test_options_override_effective():
    text, stats = _one("一二三四五六", {"max_line_chars": 3})
    assert text == "一二三\n四五六"
    assert stats["lines_rewrapped"] == 1
    assert "index" in _entry(1, 0, 1000, "甲")


def test_extend_short_into_gap_is_placeholder():
    entries = [_entry(1, 0, 200, "短"), _entry(2, 2000, 3000, "后")]
    out, stats = polish_entries(entries, {"extend_short_into_gap": True})
    assert _span(out[0]) == (0, 200)
    assert _span(out[1]) == (2000, 3000)
    assert stats["short_reported"] == 1


def test_dropped_empty_entry():
    out, stats = polish_entries([_entry(1, 0, 1000, "。"), _entry(2, 2000, 3000, "甲")])
    assert len(out) == 1
    assert out[0]["text"] == "甲"
    assert stats["dropped_empty"] == 1
