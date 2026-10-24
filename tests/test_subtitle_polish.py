"""polish 清洗层单测：白名单语义、时间轴顺序、出口不变量、幂等、纯函数。"""

import copy
import unicodedata
from pathlib import Path
from types import SimpleNamespace

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
        "rewrap_enabled": True,
        "clamp_long_enabled": True,
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


def test_rewrap_disabled_skips_rewrap():
    """rewrap_enabled=False：需拆行长条不拆，行结构原样，lines_rewrapped 恒 0。"""
    source = "一" * 20
    text, stats = _one(source, {"rewrap_enabled": False})
    assert text == source
    assert stats["lines_rewrapped"] == 0


def test_invariants_with_rewrap_off():
    """rewrap 关时出口不变量按开关裁剪：3 行长条保持 3 行（行数不变量豁免）、幂等保持。"""
    entries = [_entry(1, 0, 2000, "甲\n乙\n丙")]
    once, stats = polish_entries(entries, {"rewrap_enabled": False})
    assert len(once) == 1
    assert once[0]["text"].split("\n") == ["甲", "乙", "丙"]
    assert stats["lines_rewrapped"] == 0
    twice, _ = polish_entries(once, {"rewrap_enabled": False})
    assert twice == once


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


def test_clamp_disabled_skips_clamp():
    """clamp_long_enabled=False：超长条目时长不变、long_clamped 恒 0；过短报告不受影响。"""
    entries = [
        _entry(1, 0, 9000, "甲"),       # 超 7000ms 上限
        _entry(2, 25000, 25300, "乙"),  # 300ms 过短
    ]
    out, stats = polish_entries(entries, {"clamp_long_enabled": False})
    assert _span(out[0]) == (0, 9000)
    assert stats["long_clamped"] == 0
    assert stats["short_reported"] == 1


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


# --- 批2：主链接线 / 配置面 / 指纹条件键 -------------------------------------


def _pipeline_cfg(**kw):
    from subtransjav.refine.config import RefineConfig, StageConfig
    options = dict(inputs=[], templates_dir="", tm_enabled=False,
                   v2_profile="cloud", quality_report=False)
    options.update(kw)
    cfg = RefineConfig(**options)
    cfg.stages = [
        StageConfig(0, True, "lmstudio", "fake-model"),
        StageConfig(1, False, "deepseek", ""),
        StageConfig(2, True, "lmstudio", "fake-model"),
        StageConfig(3, False, "lmstudio", ""),
    ]
    return cfg


class _FakeClient:
    """终稿文本带句号，用于验证 polish 默认关/开的可见差异。"""

    def __init__(self):
        self.calls = []

    def translate_entries(self, entries, *, system_text, user_prompt, **kwargs):
        from subtransjav.translate.llm_client import BatchResult
        self.calls.append([e["index"] for e in entries])
        stage_b = any("|||" in e.get("text", "") for e in entries)
        translations = {
            e["index"]: (f"审{e['index']}。" if stage_b else f"译{e['index']}。")
            for e in entries}
        return BatchResult(translations=translations, deleted=set(), failed=[])


def _run_pipeline(tmp_path, monkeypatch, **kw):
    from subtransjav.refine import pipeline_v2 as pv
    cfg = _pipeline_cfg(**kw)
    in_srt = tmp_path / "demo.srt"
    in_srt.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nこんにちは\n\n"
        "2\n00:00:10,000 --> 00:00:11,000\nさようなら\n", encoding="utf-8")

    def _fake_tmp(_path, _stem):
        work = tmp_path / "work"
        work.mkdir(exist_ok=True)
        return str(work)

    monkeypatch.setattr(pv, "refine_tmp_dir", _fake_tmp)
    monkeypatch.setattr(pv, "_make_client", lambda cfg, tag: _FakeClient())
    monkeypatch.setattr(pv, "_init_tm", lambda cfg: None)
    return pv._run_single_v2(cfg, str(in_srt))


def test_pipeline_polish_default_off_is_zero_change(tmp_path, monkeypatch):
    """默认关：polish_entries 零调用，终稿逐字保留句号。"""
    from subtransjav.refine import pipeline_v2 as pv
    calls = []
    monkeypatch.setattr(pv, "polish_entries",
                        lambda *a, **k: calls.append(1))
    out = _run_pipeline(tmp_path, monkeypatch)
    assert calls == []
    content = Path(out).read_text(encoding="utf-8")
    assert "审1。" in content and "审2。" in content


def test_pipeline_polish_enabled_applies_and_links_stats(tmp_path, monkeypatch):
    """开：终稿句号消失，stats 挂进质量报告 merge_stats 数据链路。"""
    from subtransjav.refine import quality_report as qr
    captured = {}

    def _fake_build(*args, **kwargs):
        captured["merge_stats"] = dict(kwargs.get("merge_stats") or {})
        return "polish 报告占位\n第二行\n第三行"

    monkeypatch.setattr(qr, "build_quality_report", _fake_build)
    out = _run_pipeline(tmp_path, monkeypatch, polish_enabled=True,
                        quality_report=True)
    content = Path(out).read_text(encoding="utf-8")
    assert "审1。" not in content and "审2。" not in content
    assert "审1" in content and "审2" in content
    stats = captured["merge_stats"]["polish"]
    assert stats["periods_stripped"] == 2


def _legacy_cfg(cfg):
    """旧配置形态：不含任何 polish_* 属性的简易 cfg 对象。"""
    return SimpleNamespace(**{key: value for key, value in cfg.__dict__.items()
                              if not key.startswith("polish_")})


def test_config_hash_off_matches_legacy_config_shape():
    """默认关：指纹与不含 polish_* 属性的旧配置逐字节一致。"""
    from subtransjav.refine.config import RefineConfig
    from subtransjav.refine.manifest import compute_config_hash
    cfg = RefineConfig(inputs=[], templates_dir="", tm_enabled=False)
    assert compute_config_hash(cfg) == compute_config_hash(_legacy_cfg(cfg))


def test_config_hash_polish_three_states():
    """指纹三态：H_off ≠ H_on_default ≠ H_on_changed；关时改参不影响。"""
    from subtransjav.refine.config import RefineConfig
    from subtransjav.refine.manifest import compute_config_hash

    def _hash(**kw):
        return compute_config_hash(RefineConfig(
            inputs=[], templates_dir="", tm_enabled=False, **kw))

    h_off = _hash(polish_enabled=False)
    h_off_changed = _hash(polish_enabled=False, polish_max_line_chars=12)
    h_on_default = _hash(polish_enabled=True)
    h_on_changed = _hash(polish_enabled=True, polish_max_line_chars=12,
                         polish_quote_style="curly")
    h_on_rewrap_off = _hash(polish_enabled=True, polish_rewrap_enabled=False)
    assert h_off == h_off_changed
    assert len({h_off, h_on_default, h_on_changed}) == 3
    assert h_on_default != h_on_rewrap_off  # 开-默认 ≠ 开-rewrap 关


def test_config_policy_bool_switches():
    """config 折算：默认两开关 True；显式 False 走 _POLISH_BOOL_FIELDS 映射生效。"""
    from subtransjav.refine.config import RefineConfig, polish_policy_from_config

    def _policy(**kw):
        return polish_policy_from_config(RefineConfig(
            inputs=[], templates_dir="", tm_enabled=False, **kw))

    policy = _policy()
    assert policy["rewrap_enabled"] is True
    assert policy["clamp_long_enabled"] is True
    policy_off = _policy(polish_rewrap_enabled=False,
                         polish_clamp_long_enabled=False)
    assert policy_off["rewrap_enabled"] is False
    assert policy_off["clamp_long_enabled"] is False


def test_cli_new_switch_flags():
    """CLI：--polish-no-rewrap / --polish-no-clamp-long → cfg False；缺省 True。"""
    from subtransjav.refine.cli import build_parser, config_from_args

    args = build_parser().parse_args(["-i", "x.srt"])
    cfg = config_from_args(args)
    assert cfg.polish_rewrap_enabled is True
    assert cfg.polish_clamp_long_enabled is True

    args_off = build_parser().parse_args(
        ["-i", "x.srt", "--polish-no-rewrap", "--polish-no-clamp-long"])
    cfg_off = config_from_args(args_off)
    assert cfg_off.polish_rewrap_enabled is False
    assert cfg_off.polish_clamp_long_enabled is False


def test_cli_keep_final_period_flag():
    """CLI：--polish-keep-final-period → cfg.polish_strip_final_period=False；缺省 True。"""
    from subtransjav.refine.cli import build_parser, config_from_args

    args = build_parser().parse_args(["-i", "x.srt"])
    cfg = config_from_args(args)
    assert cfg.polish_strip_final_period is True

    args_keep = build_parser().parse_args(
        ["-i", "x.srt", "--polish-keep-final-period"])
    cfg_keep = config_from_args(args_keep)
    assert cfg_keep.polish_strip_final_period is False
