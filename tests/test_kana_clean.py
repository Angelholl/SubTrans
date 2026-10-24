"""
源文假名清洗（D2026-1025-01 批3a）纯函数层测试。
覆盖：分类器（实义/喘息/短句/保留）、并入前条/链式合并/前向挂接、
孤立喘息删除（开关默认关、默认不删）、实义词零连坐、拉丁/汉字不动。
"""

from subtransjav.refine.kana_clean import (
    CLASS_CONTENT,
    CLASS_KEEP,
    CLASS_MOAN,
    CLASS_SHORT,
    classify_kana_entry,
    clean_entries,
)


def _fmt_ms(ms: int) -> str:
    h, rem = divmod(ms, 3600000)
    m, rem = divmod(rem, 60000)
    s, ms2 = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms2:03d}"


def _e(idx, start_ms, end_ms, text):
    return {"index": idx, "timing": f"{_fmt_ms(start_ms)} --> {_fmt_ms(end_ms)}",
            "text": text}


# ---------------------------------------------------------------------------
# 分类器
# ---------------------------------------------------------------------------

def test_classify_content():
    for t in ("好き", "部長で、エースで。", "Camera", "OK1", "3人が"):
        assert classify_kana_entry(t) == CLASS_CONTENT, t


def test_classify_moan():
    for t in ("あ", "あぁ", "んっ", "アン", "ヴ", "っ", "…", "♪", "", "  ",
              "あー", "、。！", "あぁっ……"):
        assert classify_kana_entry(t) == CLASS_MOAN, t


def test_classify_short():
    for t in ("うん", "はい", "そう", "カメラ", "えっとね", "うん？"):
        assert classify_kana_entry(t) == CLASS_SHORT, t


def test_classify_keep():
    for t in ("ううううううう", "えっとですねえっと", "★うん★"):
        assert classify_kana_entry(t) == CLASS_KEEP, t


# ---------------------------------------------------------------------------
# 合并（默认开）
# ---------------------------------------------------------------------------

def test_short_merges_into_prev():
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2500, 2700, "うん"),          # 间隙 500ms ≤ 800 → 并入前条
    ]
    out, stats = clean_entries(entries)
    assert len(out) == 1
    assert out[0]["text"] == "好きだうん"
    assert out[0]["timing"] == "00:00:01,000 --> 00:00:02,700"
    assert stats["kana_merged"] == 1
    assert stats["kana_kept"] == 0
    assert stats["kana_moan_deleted"] == 0


def test_merge_chain():
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2300, 2400, "あ"),            # 间隙 300 → 并入前条
        _e(3, 2700, 2800, "んっ"),          # 间隙 300 → 续并入合并体
    ]
    out, stats = clean_entries(entries)
    assert len(out) == 1
    assert out[0]["text"] == "好きだあんっ"
    assert out[0]["timing"] == "00:00:01,000 --> 00:00:02,800"
    assert stats["kana_merged"] == 2


def test_forward_attach_to_next():
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 3500, 3700, "そう"),          # 与前条间隙 1500 > 800
        _e(3, 4200, 5000, "やめて"),        # 与前条（そう）间隙 500 ≤ 800
    ]
    out, stats = clean_entries(entries)
    assert len(out) == 2
    assert out[1]["text"] == "そうやめて"
    assert out[1]["timing"] == "00:00:03,500 --> 00:00:05,000"
    assert stats["kana_merged"] == 1


def test_forward_buffer_then_prev_merge():
    """前向缓冲条目再遇「并入前条」决策：缓冲条目吸收后条后落定（链式）。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 3500, 3700, "そう"),          # 前向缓冲
        _e(3, 4000, 4200, "ん"),            # 并入缓冲体
        _e(4, 5000, 5800, "止めて"),        # 含汉字实义类：不参与合并
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["好きだ", "そうん", "止めて"]
    assert out[1]["timing"] == "00:00:03,500 --> 00:00:04,200"
    assert stats["kana_merged"] == 1
    assert stats["kana_kept"] == 0


def test_merge_gap_boundary():
    """间隙恰 800ms 并入、801ms 不并入。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2800, 3000, "うん"),          # 间隙恰 800 → 并入
    ]
    out, _ = clean_entries(entries)
    assert len(out) == 1

    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2801, 3000, "うん"),          # 间隙 801 → 保留
    ]
    out, stats = clean_entries(entries)
    assert len(out) == 2
    assert stats["kana_kept"] == 1


# ---------------------------------------------------------------------------
# 孤立喘息删除（默认关）
# ---------------------------------------------------------------------------

def test_isolated_moan_default_kept():
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 5000, 5100, "あぁ"),          # 前后间隙均 3000ms → 孤立
        _e(3, 8100, 9000, "やめて"),        # 纯假名短句类
    ]
    out, stats = clean_entries(entries)
    assert len(out) == 3
    assert out[1]["text"] == "あぁ"
    assert stats["kana_kept"] == 2
    assert stats["kana_moan_deleted"] == 0


def test_isolated_moan_deleted_with_opt_in():
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 5000, 5100, "あぁ"),
        _e(3, 8100, 9000, "やめて"),
    ]
    out, stats = clean_entries(entries, delete_enabled=True)
    assert [e["text"] for e in out] == ["好きだ", "やめて"]
    assert stats["kana_moan_deleted"] == 1
    assert stats["kana_moan_deleted_timings"] == [
        {"timing": "00:00:05,000 --> 00:00:05,100", "text": "あぁ"}]
    assert stats["kana_kept"] == 1          # やめて 为短句类保留


def test_moan_isolated_boundary_1200_kept():
    """前后间隙恰 1200ms 不算孤立（规格：均 >1200ms 才删）。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 3200, 3300, "あぁ"),          # 前间隙 1200 / 后间隙 1200
        _e(3, 4500, 5000, "やめて"),
    ]
    out, stats = clean_entries(entries, delete_enabled=True)
    assert len(out) == 3
    assert stats["kana_moan_deleted"] == 0


def test_moan_non_isolated_not_deleted_even_opt_in():
    """非孤立且不可合并（间隙 801~1200）的喘息保留，即使删除开关开。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 3000, 3100, "あぁ"),          # 前间隙 1000：非孤立、不可并
        _e(3, 6100, 7000, "やめて"),        # 后间隙 3000
    ]
    out, stats = clean_entries(entries, delete_enabled=True)
    assert len(out) == 3
    assert stats["kana_moan_deleted"] == 0
    assert stats["kana_kept"] == 2          # あぁ（非孤立）+ やめて（短句）


def test_adjacent_moan_merges_even_with_delete_on():
    """删除开关开但喘息相邻（可合并）：并入前条而非删除。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2500, 2600, "んっ"),          # 间隙 500 → 并入前条
        _e(3, 6000, 7000, "やめて"),
    ]
    out, stats = clean_entries(entries, delete_enabled=True)
    assert [e["text"] for e in out] == ["好きだんっ", "やめて"]
    assert stats["kana_merged"] == 1
    assert stats["kana_moan_deleted"] == 0


def test_merge_disabled_keeps_shorts():
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2500, 2700, "うん"),          # 可合并但开关关
    ]
    out, stats = clean_entries(entries, merge_enabled=False)
    assert len(out) == 2
    assert stats["kana_merged"] == 0
    assert stats["kana_kept"] == 1


def test_head_tail_isolated_moan_deleted():
    """首/尾孤立喘息（单侧无邻居视为孤立侧）在删除开关开时可删。"""
    entries = [
        _e(1, 0, 200, "あぁ"),
        _e(2, 2000, 3000, "好きだ"),
        _e(3, 5000, 5200, "ん"),
    ]
    out, stats = clean_entries(entries, delete_enabled=True)
    assert [e["text"] for e in out] == ["好きだ"]
    assert stats["kana_moan_deleted"] == 2


# ---------------------------------------------------------------------------
# 零连坐与防御
# ---------------------------------------------------------------------------

def test_real_words_zero_collateral():
    """实义词/常用应答词零连坐：大间隙下原样保留（含纯假名实义词）。"""
    entries = [
        _e(1, 1000, 2000, "好き"),
        _e(2, 4000, 4600, "ごめん"),
        _e(3, 7600, 7900, "うん"),
        _e(4, 10900, 11100, "はい"),
        _e(5, 14100, 14300, "そう"),
        _e(6, 17300, 18100, "カメラ"),
    ]
    out, stats = clean_entries(entries, delete_enabled=True)
    assert [e["text"] for e in out] == [
        "好き", "ごめん", "うん", "はい", "そう", "カメラ"]
    assert stats["kana_merged"] == 0
    assert stats["kana_moan_deleted"] == 0
    assert stats["kana_kept"] == 5          # 除好き（实义类）外均为短句类


def test_latin_and_kanji_never_merged():
    """实义类永不触：即使间隙极小也不并入/不吸走。"""
    entries = [
        _e(1, 1000, 2000, "Camera"),
        _e(2, 2100, 2200, "OK"),            # 间隙 100：实义类互不合并
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["Camera", "OK"]
    assert stats["kana_merged"] == 0


def test_invalid_timing_conservative_keep():
    """时间轴非法：不合并不删除，防御性保留。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        {"index": 2, "timing": "broken", "text": "うん"},
    ]
    out, stats = clean_entries(entries)
    assert len(out) == 2
    assert stats["kana_merged"] == 0


def test_empty_entries():
    out, stats = clean_entries([])
    assert out == []
    assert stats == {"kana_merged": 0, "kana_moan_deleted": 0,
                     "kana_moan_deleted_timings": [], "kana_kept": 0}


def test_moan_absorbed_by_content_neighbor_stays_content_intact():
    """喘息并入实义前条：前条文本在前（时间序），实义条目自身不被吸走。"""
    entries = [
        _e(1, 1000, 2000, "好き"),
        _e(2, 2400, 2500, "あぁ"),
        _e(3, 6000, 7000, "やめて"),
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["好きあぁ", "やめて"]
    assert out[0]["index"] == 1
    assert stats["kana_merged"] == 1
