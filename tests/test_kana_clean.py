"""
源文假名清洗（D2026-1025-01 批3a）纯函数层测试。
覆盖：分类器（实义/喘息/短句/保留）、并入前条/链式合并/前向挂接、
孤立喘息删除（开关默认关、默认不删）、实义词零连坐、拉丁/汉字不动；
批6 a 项（D2026-1025-01 规格 v3）：豁免成员表/归一 core/三向守卫/
豁免台账与计数、模拟器-模块等价（v3 参数定死）。
"""

from subtransjav.refine.kana_clean import (
    CLASS_CONTENT,
    CLASS_KEEP,
    CLASS_MOAN,
    CLASS_SHORT,
    classify_kana_entry,
    clean_entries,
    is_exempt_entry,
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
    """改钉（规格 v3 §1/§2/§6）：うん 现入豁免表永不并——改用集外叠词
    うんうん 钉短句类合并主路径，间隙恰 200ms ≤ FRAGMENT_GAP_MS 并入。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2200, 2400, "うんうん"),      # 间隙 200ms ≤ 200 → 并入前条
    ]
    out, stats = clean_entries(entries)
    assert len(out) == 1
    assert out[0]["text"] == "好きだうんうん"
    assert out[0]["timing"] == "00:00:01,000 --> 00:00:02,400"
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
    """改钉（规格 v3 §1/§6）：そう 现入豁免表永不 carry——改用集外短句
    カメラ 钉前向挂接主路径，后侧间隙 200ms ≤ FRAGMENT_GAP_MS。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 3500, 3700, "カメラ"),        # 与前条间隙 1500 > 200
        _e(3, 3900, 5000, "やめて"),        # 与前条（カメラ）间隙 200 ≤ 200
    ]
    out, stats = clean_entries(entries)
    assert len(out) == 2
    assert out[1]["text"] == "カメラやめて"
    assert out[1]["timing"] == "00:00:03,500 --> 00:00:05,000"
    assert stats["kana_merged"] == 1


def test_forward_buffer_then_prev_merge():
    """前向缓冲条目再遇「并入前条」决策：缓冲条目吸收后条后落定（链式）。
    改钉（规格 v3 §1/§6）：そう/ん 均现入豁免表——改用カメラ/んっ 钉
    同一链式路径，缓冲体后侧间隙 200ms ≤ FRAGMENT_GAP_MS。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 3500, 3700, "カメラ"),        # 前向缓冲
        _e(3, 3900, 4200, "んっ"),          # 并入缓冲体（喘息 800 档）
        _e(4, 5000, 5800, "止めて"),        # 含汉字实义类：不参与合并
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["好きだ", "カメラんっ", "止めて"]
    assert out[1]["timing"] == "00:00:03,500 --> 00:00:04,200"
    assert stats["kana_merged"] == 1
    assert stats["kana_kept"] == 0


def test_merge_gap_boundary():
    """改钉（规格 v3 §6）：短句类间隙恰 200ms 并入、201ms 不并入
    （うん 现入豁免表，改用集外短句 カメラ 钉边界）。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2200, 3000, "カメラ"),        # 间隙恰 200 → 并入
    ]
    out, _ = clean_entries(entries)
    assert len(out) == 1

    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2201, 3000, "カメラ"),        # 间隙 201 → 保留
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
    """首/尾孤立喘息（单侧无邻居视为孤立侧）在删除开关开时可删。
    改钉（规格 v3 §1/§4）：ん 现入豁免表先于删除判定永不删——
    改用非成员喘息 あ 钉同一孤立删除路径。"""
    entries = [
        _e(1, 0, 200, "あぁ"),
        _e(2, 2000, 3000, "好きだ"),
        _e(3, 5000, 5200, "あ"),
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
    # 改钉（规格 v3 §7）：stats 新增 kana_exempted/kana_exempted_ledger 键
    assert stats == {"kana_merged": 0, "kana_moan_deleted": 0,
                     "kana_moan_deleted_timings": [], "kana_kept": 0,
                     "kana_exempted": 0, "kana_exempted_ledger": []}


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


# ---------------------------------------------------------------------------
# 豁免成员表与归一 core（D2026-1025-01 规格 v3 §1/§2）
# ---------------------------------------------------------------------------

def _to_kata(s: str) -> str:
    """平假名→片假名（ァ-ヺ 偏移 +0x60 的逆映射），测试辅助。"""
    return "".join(
        chr(ord(c) + 0x60) if "ぁ" <= c <= "ゖ" else c for c in s)


def test_exempt_member_table_hits():
    """归一形 13 项成员逐一命中（表内写归一形：えっ→えつ、わかった→
    わかつた、マジで→まじで；规格 v3 §1）。"""
    for t in ("はい", "うん", "そう", "そうね", "そうか", "ね", "えっ",
              "ええ", "ん", "まじで", "なるほど", "わかった", "うそ",
              "マジで"):
        assert is_exempt_entry(t), t


def test_exempt_new_members():
    """三新入成员定向（卡面 3）：なるほど/わかった/うそ。"""
    for t in ("なるほど", "わかった", "うそ"):
        assert is_exempt_entry(t), t


def test_exempt_variant_matrix():
    """变体矩阵（规格 §9）：每成员×片假名化/尾长音变体逐一命中；
    含促音成员按实构造（えっ/わかった 原形走折叠路径，不硬凑）。"""
    cores = ["はい", "うん", "そう", "そうね", "そうか", "ね", "えつ",
             "ええ", "ん", "まじで", "なるほど", "わかつた", "うそ"]
    for core in cores:
        assert is_exempt_entry(core), core
        assert is_exempt_entry(_to_kata(core)), core       # 片假名化折叠
        assert is_exempt_entry(core + "ー"), core          # 尾长音剥离
    # 含促音成员原形（っ 经折叠=つ 后命中表）
    assert is_exempt_entry("えっ")
    assert is_exempt_entry("わかった")


def test_exempt_set_gap_words_not_exempt():
    """集外缺口（规格 v3 §2/§3）：叠词/礼貌形/汉字实义词不触豁免。"""
    for t in ("うんうん", "はいです", "本当", "ごめん", "えっとね", "えー"):
        assert not is_exempt_entry(t), t


# ---------------------------------------------------------------------------
# 豁免语义（规格 v3 §4）：先于短句/喘息分类合并与孤立删除判定
# ---------------------------------------------------------------------------

def test_exempt_member_never_merges_even_tight_gap():
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2100, 2200, "はい"),          # 间隙 100ms：若不豁免即并入
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["好きだ", "はい"]
    assert stats["kana_merged"] == 0
    assert stats["kana_kept"] == 1       # はい（豁免计 kept）；好きだ 实义不计
    assert stats["kana_exempted"] == 1


def test_exempt_before_delete_isolated_opt_in():
    """ん？（规格 v3 §4/§1）：豁免先于孤立删除——delete_enabled=True 且
    孤立（前后间隙均 3000ms）仍保留，防 opt-in 删除丢数据。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 5000, 5100, "ん？"),
        _e(3, 8100, 9000, "やめて"),
    ]
    out, stats = clean_entries(entries, delete_enabled=True)
    assert [e["text"] for e in out] == ["好きだ", "ん？", "やめて"]
    assert stats["kana_moan_deleted"] == 0
    assert stats["kana_exempted"] == 1


def test_exempt_ne_long_vowel_hits():
    """ねー（卡面 3）：剥长音=ね 命中豁免表。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2100, 2200, "ねー"),
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["好きだ", "ねー"]
    assert stats["kana_merged"] == 0
    assert stats["kana_exempted"] == 1


def test_untangled_overlap_still_short_mergeable():
    """うんうん（卡面 3，规格 v3 §2 集外缺口钉）：叠词不入表→照旧按
    短句类可并（gap≤200），豁免计数不含它。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2100, 2200, "うんうん"),
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["好きだうんうん"]
    assert stats["kana_merged"] == 1
    assert stats["kana_exempted"] == 0


def test_katakana_variants_hit_behavioral():
    """片假名变体（卡面 3）：ハイ/ネー 命中表，行为层永不并。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2100, 2200, "ハイ"),
        _e(3, 2300, 2400, "ネー"),
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["好きだ", "ハイ", "ネー"]
    assert stats["kana_merged"] == 0
    assert stats["kana_exempted"] == 2


def test_kanji_word_never_exempt():
    """本当（卡面 3，规格 v3 §1）：汉字永不触，照旧实义类零连坐。"""
    assert not is_exempt_entry("本当")
    entries = [
        _e(1, 1000, 2000, "本当？"),
        _e(2, 2100, 2200, "カメラ"),
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["本当？カメラ"]
    assert stats["kana_exempted"] == 0


# ---------------------------------------------------------------------------
# gap 分档边界（卡面 2，规格 v3 §6）：短句 200 / 喘息 800 档
# ---------------------------------------------------------------------------

def test_short_gap_boundary_0_1_200_201():
    for gap, merged in ((0, True), (1, True), (200, True), (201, False)):
        entries = [
            _e(1, 1000, 2000, "好きだ"),
            _e(2, 2000 + gap, 2000 + gap + 100, "カメラ"),
        ]
        out, stats = clean_entries(entries)
        assert len(out) == (1 if merged else 2), gap
        assert stats["kana_merged"] == (1 if merged else 0), gap
        assert stats["kana_kept"] == (0 if merged else 1), gap


def test_moan_gap_boundary_799_800_801():
    for gap, merged in ((799, True), (800, True), (801, False)):
        entries = [
            _e(1, 1000, 2000, "好きだ"),
            _e(2, 2000 + gap, 2000 + gap + 100, "あぁ"),
        ]
        out, stats = clean_entries(entries)
        assert len(out) == (1 if merged else 2), gap
        assert stats["kana_merged"] == (1 if merged else 0), gap
        assert stats["kana_kept"] == (0 if merged else 1), gap


# ---------------------------------------------------------------------------
# 三向守卫（规格 v3 §5，卡面 5 四路径）
# ---------------------------------------------------------------------------

def test_host_guard_short_fragment_after_exempt():
    """①豁免条后随短句碎片 gap≤200 → 宿主守卫：碎片独立成行（计 kept）。"""
    entries = [
        _e(1, 1000, 1200, "はい"),
        _e(2, 1400, 1600, "カメラ"),        # gap 200 → merge_prev 决策
        _e(3, 6000, 7000, "やめて"),
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["はい", "カメラ", "やめて"]
    assert stats["kana_merged"] == 0
    assert stats["kana_exempted"] == 1
    assert stats["kana_kept"] == 3      # はい（豁免）+ カメラ（守卫保留）+ やめて


def test_host_guard_moan_fragment_after_exempt():
    """③豁免条为 out[-1] 时后条 merge_prev 决策（喘息类）→ 后条独立。"""
    entries = [
        _e(1, 1000, 1200, "はい"),
        _e(2, 1500, 1600, "あぁ"),          # gap 300 ≤ 800 → merge_prev 决策
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["はい", "あぁ"]
    assert stats["kana_merged"] == 0
    assert stats["kana_kept"] == 2


def test_front_guard_carry_meets_exempt():
    """②carry 缓冲紧邻豁免条 → 前端守卫：缓冲原样落定（kept）、豁免条
    独立成行，不挂接。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 3500, 3700, "カメラ"),        # g_prev 1500>200、g_next 100≤200 → carry
        _e(3, 3800, 3900, "はい"),          # 豁免条紧邻缓冲
        _e(4, 6000, 7000, "やめて"),
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["好きだ", "カメラ", "はい", "やめて"]
    assert stats["kana_merged"] == 0
    assert stats["kana_exempted"] == 1
    assert stats["kana_kept"] == 3      # カメラ + はい + やめて


def test_exempt_delete_path_guard():
    """④豁免条遇 delete_enabled=True 孤立 → 不删（ん？ 见
    test_exempt_before_delete_isolated_opt_in）；本用例补 首条孤立形：
    首条豁免 うん 保留，非成员孤立喘息 あぁ 照删（豁免/删除分径）。"""
    entries = [
        _e(1, 1000, 1100, "うん"),          # 首条豁免孤立（g_next 3000）
        _e(2, 4100, 4200, "あぁ"),          # 非成员孤立喘息 → opt-in 删除
        _e(3, 7200, 7300, "やめて"),
    ]
    out, stats = clean_entries(entries, delete_enabled=True)
    assert [e["text"] for e in out] == ["うん", "やめて"]
    assert stats["kana_moan_deleted"] == 1
    assert stats["kana_exempted"] == 1
    assert stats["kana_kept"] == 2       # うん（豁免计 kept）+ やめて（短句保留）


def test_exempt_row_never_absorbs_chain():
    """链式语义（卡面 4 docstring 要求显式封闭）：守卫全开下豁免行永不
    吸收任何条目——豁免宿主被挡后，后条仍可与「非豁免落定行」续并。"""
    entries = [
        _e(1, 1000, 1200, "はい"),
        _e(2, 1300, 1500, "カメラ"),        # merge_prev 被宿主守卫挡下 → 独立
        _e(3, 1600, 1700, "あぁ"),          # merge_prev 并入カメラ（非豁免）
    ]
    out, stats = clean_entries(entries)
    assert [e["text"] for e in out] == ["はい", "カメラあぁ"]
    assert stats["kana_merged"] == 1
    assert stats["kana_exempted"] == 1


def test_exempt_flag_never_leaks_into_output():
    """豁免标记用内部字段（卡面 4）：输出前清除，不泄漏进产物 dict。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2100, 2200, "うん"),
        _e(3, 2300, 2400, "あぁ"),
    ]
    out, _ = clean_entries(entries)
    for e in out:
        assert all(not k.startswith("_") for k in e), e


# ---------------------------------------------------------------------------
# 豁免台账与计数（卡面 6，规格 v3 §7）
# ---------------------------------------------------------------------------

def test_exempt_ledger_fields_prev_neighbor_preferred():
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2600, 2700, "はい"),          # g_prev 600 / g_next 6300
        _e(3, 9000, 9100, "やめて"),
    ]
    out, stats = clean_entries(entries)
    assert stats["kana_exempted"] == 1
    assert stats["kana_exempted_ledger"] == [
        {"timing": "00:00:02,600 --> 00:00:02,700", "text": "はい",
         "core": "はい", "gap": 600, "neighbor_text": "好きだ"}]


def test_exempt_ledger_next_neighbor_when_no_prev():
    entries = [
        _e(1, 1000, 1100, "はい"),          # 首条无前邻 → 取后侧
        _e(2, 2000, 3000, "好きだ"),
    ]
    out, stats = clean_entries(entries)
    assert stats["kana_exempted_ledger"] == [
        {"timing": "00:00:01,000 --> 00:00:01,100", "text": "はい",
         "core": "はい", "gap": 900, "neighbor_text": "好きだ"}]


def test_exempt_ledger_no_neighbor_null():
    entries = [_e(1, 1000, 1100, "はい")]
    out, stats = clean_entries(entries)
    assert stats["kana_exempted"] == 1
    assert stats["kana_exempted_ledger"] == [
        {"timing": "00:00:01,000 --> 00:00:01,100", "text": "はい",
         "core": "はい", "gap": None, "neighbor_text": None}]


def test_exempt_ledger_core_normalized_value():
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2100, 2200, "マジで"),        # 片假名折叠 → まじで
    ]
    _, stats = clean_entries(entries)
    assert stats["kana_exempted_ledger"][0]["core"] == "まじで"


def test_exempt_ledger_invalid_timing_gap_null():
    entries = [
        {"index": 1, "timing": "broken", "text": "はい"},
        _e(2, 2000, 3000, "好きだ"),
    ]
    _, stats = clean_entries(entries)
    assert stats["kana_exempted_ledger"][0]["gap"] is None
    assert stats["kana_exempted_ledger"][0]["neighbor_text"] is None


def test_exempt_ledger_neighbor_text_truncated_40():
    entries = [
        _e(1, 1000, 2000, "あ" * 50),
        _e(2, 2100, 2200, "はい"),
    ]
    _, stats = clean_entries(entries)
    assert stats["kana_exempted_ledger"][0]["neighbor_text"] == "あ" * 40


def test_exempt_counted_in_kept_and_excluded_from_merged():
    """豁免条同时计 kept（对齐模拟器口径），绝不入 kana_merged。"""
    entries = [
        _e(1, 1000, 2000, "好きだ"),
        _e(2, 2100, 2200, "うん"),
        _e(3, 2300, 2400, "そう"),
        _e(4, 6100, 6200, "カメラ"),
    ]
    out, stats = clean_entries(entries)
    assert stats["kana_exempted"] == 2
    assert stats["kana_kept"] == 3      # うん + そう（豁免）+ カメラ（201 保留）
    assert stats["kana_merged"] == 0


# ---------------------------------------------------------------------------
# 模拟器-模块等价测试（卡面 7，复拍要求①③；等值结论限 merge=True 配置）
# 参考模拟器自 docs/design/d1025-批6-补证归档/zero.py engine() 逐字移植，
# v3 参数定死（frag=200/moan=800/豁免/守卫全开），复拍 glm D3/mimo 缺陷5：
# 逐条 text＋timing＋index 全等，只比计数不够。
# ---------------------------------------------------------------------------

_SIM_SMALL_FOLD = {"ぁ": "あ", "ぃ": "い", "ぅ": "う", "ぇ": "え", "ぉ": "お",
                   "っ": "つ", "ゃ": "や", "ゅ": "ゆ", "ょ": "よ", "ゎ": "わ",
                   "ゐ": "い", "ゑ": "え"}
_SIM_MEMBER_TABLE = {"はい", "うん", "そう", "そうね", "そうか", "ね", "えつ",
                     "ええ", "ん", "まじで", "なるほど", "わかつた", "うそ"}


def _sim_norm_core(core: str) -> str:
    out = []
    for ch in core:
        if "ァ" <= ch <= "ヺ":
            ch = chr(ord(ch) - 0x60)
        out.append(_SIM_SMALL_FOLD.get(ch, ch))
    return "".join(out)


def _sim_is_exempt(text: str) -> bool:
    from subtransjav.refine.kana_clean import _STRIP_PUNCT_RE
    return _sim_norm_core(_STRIP_PUNCT_RE.sub("", text or "")) in _SIM_MEMBER_TABLE


def _sim_engine(entries, *, delete_enabled=False):
    """zero.py engine() 的 v3 定参移植（frag=200/moan=800/守卫全开），
    只保留与输出等价性相关的结构（追踪性遥测不在等值断言面）。"""
    from subtransjav.refine.kana_clean import (
        CLASS_MOAN,
        CLASS_SHORT,
        ISOLATED_GAP_MS,
        _merge_pair,
        _timing_span,
        classify_kana_entry,
    )
    n = len(entries)
    classes = [classify_kana_entry(e.get("text") or "") for e in entries]
    exempt_flag = [bool(_sim_is_exempt(e.get("text") or "")) for e in entries]
    spans = [_timing_span(e.get("timing") or "") for e in entries]
    inf = float("inf")

    def side_gap(i, j):
        if i < 0 or j >= n:
            return inf
        if spans[i][0] < 0 or spans[j][0] < 0:
            return None
        return round((spans[j][0] - spans[i][1]) * 1000)

    # ---- 决策（豁免显式先于全部判定，含删除）----
    actions = []
    for i in range(n):
        if exempt_flag[i]:
            actions.append("keep")          # 退出整个 action 决策
            continue
        c = classes[i]
        if c not in (CLASS_SHORT, CLASS_MOAN):
            actions.append(None)
            continue
        gap = 800 if c == CLASS_MOAN else 200
        g_prev, g_next = side_gap(i - 1, i), side_gap(i, i + 1)
        if g_prev is not None and g_prev <= gap:
            actions.append("merge_prev")
        elif g_next is not None and g_next <= gap:
            actions.append("carry_next")
        elif (c == CLASS_MOAN and delete_enabled
                and g_prev is not None and g_next is not None
                and g_prev > ISOLATED_GAP_MS and g_next > ISOLATED_GAP_MS):
            actions.append("delete")
        else:
            actions.append("keep")

    # ---- 执行（含宿主/前端守卫）----
    out = []
    carry = None
    st = {"merged": 0, "kept": 0, "deleted": 0, "exempted": sum(exempt_flag)}
    for i in range(n):
        e, act = entries[i], actions[i]
        if carry is not None:
            if exempt_flag[i]:
                # 前端显式守卫：缓冲原样落定，豁免条独立成行
                out.append(carry)
                st["kept"] += 1
                carry = None
            elif act is None or act == "merge_prev":
                out.append(_merge_pair(carry, e))
                st["merged"] += 1
                carry = None
                continue                    # 与模块一致：成对消耗后跳过后条
            else:
                out.append(carry)
                st["kept"] += 1
                carry = None
        if act is None:
            out.append(dict(e))
        elif act == "merge_prev":
            if not out:
                out.append(dict(e))
                st["kept"] += 1
            elif out[-1].get("_exempt_origin"):
                out.append(dict(e))         # 宿主守卫：后条独立保留
                st["kept"] += 1
            else:
                out[-1] = _merge_pair(out[-1], e)
                out[-1]["_exempt_origin"] = False
                st["merged"] += 1
        elif act == "carry_next":
            if carry is not None:           # 与模块一致：旧缓冲先落定
                out.append(carry)
                st["kept"] += 1
                carry = None
            carry = dict(e)
        elif act == "delete":
            st["deleted"] += 1
        else:                               # keep
            m = dict(e)
            if exempt_flag[i]:
                m["_exempt_origin"] = True
            out.append(m)
            st["kept"] += 1
    if carry is not None:
        out.append(carry)
        st["kept"] += 1
    for m in out:
        m.pop("_exempt_origin", None)
    return out, st


def _equivalence_fixtures():
    """不少于 12 组合成夹具（卡面 7），覆盖：纯豁免序列、carry 链式续并、
    carry 成对消耗、宿主守卫触发、前端守卫触发、删除开关交互等。"""
    fixtures = []
    # 1 纯豁免序列（紧邻间隙全 0，豁免永不并）
    fixtures.append(([_e(1, 0, 200, "はい"), _e(2, 200, 400, "うん"),
                      _e(3, 400, 600, "ね"), _e(4, 600, 800, "ええ"),
                      _e(5, 800, 1000, "ん")], False))
    # 2 宿主守卫触发（短句碎片 merge_prev 被挡）
    fixtures.append(([_e(1, 1000, 1200, "はい"),
                      _e(2, 1400, 1600, "カメラ"),
                      _e(3, 6000, 7000, "やめて")], False))
    # 3 前端守卫触发（carry 缓冲紧邻豁免条）
    fixtures.append(([_e(1, 1000, 2000, "好きだ"),
                      _e(2, 3500, 3700, "カメラ"),
                      _e(3, 3800, 3900, "はい"),
                      _e(4, 6000, 7000, "やめて")], False))
    # 4 carry 链式续并（缓冲吸收 merge_prev 后续并非豁免落定行）
    fixtures.append(([_e(1, 1000, 2000, "好きだ"),
                      _e(2, 3500, 3700, "カメラ"),
                      _e(3, 3800, 4000, "んっ"),
                      _e(4, 4100, 4200, "あぁ"),
                      _e(5, 8000, 8800, "止めて")], False))
    # 5 carry 成对消耗（缓冲与后随 merge_prev 条同吞落定）
    fixtures.append(([_e(1, 1000, 2000, "好きだ"),
                      _e(2, 3500, 3700, "カメラ"),
                      _e(3, 3900, 4000, "あぁ")], False))
    # 6 宿主守卫触发（喘息类 merge_prev 被挡，含孤立 keep）
    fixtures.append(([_e(1, 1000, 1200, "うん"),
                      _e(2, 1500, 1600, "あぁ"),
                      _e(3, 5000, 5100, "あぁ")], False))
    # 7 删除开关交互（孤立喘息删除＋豁免 ん？ 保留）
    fixtures.append(([_e(1, 1000, 2000, "好きだ"),
                      _e(2, 5000, 5100, "あぁ"),
                      _e(3, 9000, 9100, "ん？"),
                      _e(4, 13000, 14000, "やめて")], True))
    # 8 短句链式合并（全 merge_prev 级联）
    fixtures.append(([_e(1, 1000, 2000, "好きだ"),
                      _e(2, 2100, 2200, "カメラ"),
                      _e(3, 2300, 2400, "やめて"),
                      _e(4, 2500, 2600, "うんうん")], False))
    # 9 豁免宿主连续挡下＋中间续并（卡面用例组合复用）
    fixtures.append(([_e(1, 1000, 1100, "ん"),
                      _e(2, 1200, 1300, "あぁ"),
                      _e(3, 1400, 1500, "カメラ"),
                      _e(4, 1600, 1700, "はい"),
                      _e(5, 1800, 1900, "うんうん")], False))
    # 10 时间轴非法保守（豁免 ledger gap null 同源场景）
    fixtures.append(([{"index": 1, "timing": "broken", "text": "はい"},
                      _e(2, 2000, 3000, "好きだ"),
                      _e(3, 3100, 3200, "あぁ")], False))
    # 11 首/尾豁免＋孤立喘息删除开
    fixtures.append(([_e(1, 0, 100, "はい"),
                      _e(2, 3000, 3100, "あぁ"),
                      _e(3, 7000, 7100, "ね")], True))
    # 12 carry 与短句档/喘息档混排（800 档 carry、201 短句保留）
    fixtures.append(([_e(1, 1000, 2000, "好きだ"),
                      _e(2, 2900, 3000, "あぁ"),
                      _e(3, 3100, 3200, "うんうん"),
                      _e(4, 4000, 4800, "カメラ")], False))
    # 13 实义书挡＋豁免/喘息/短句混合（守卫连挡）
    fixtures.append(([_e(1, 1000, 2000, "Camera"),
                      _e(2, 2100, 2200, "はい"),
                      _e(3, 2300, 2400, "あぁ"),
                      _e(4, 2500, 2600, "うん"),
                      _e(5, 2700, 2800, "やめて"),
                      _e(6, 3000, 4000, "OK")], False))
    # 14 尾部全 keep 落定（豁免在首、两短句均双超限独立保留）
    fixtures.append(([_e(1, 0, 100, "ね"),
                      _e(2, 2000, 2200, "カメラ"),
                      _e(3, 3500, 3600, "やめて")], False))
    return fixtures


def test_simulator_module_equivalence_v3():
    """模拟器-模块等价（规格 §9）：14 组合夹具逐条 text＋timing＋index
    全等＋四计数全等；等值结论限 merge=True 配置（复拍 mimo 备注6）。"""
    for idx, (entries, delete_on) in enumerate(_equivalence_fixtures(), 1):
        mod_out, mod_st = clean_entries(list(entries),
                                        delete_enabled=delete_on)
        sim_out, sim_st = _sim_engine([dict(e) for e in entries],
                                      delete_enabled=delete_on)
        assert len(mod_out) == len(sim_out), idx
        for a, b in zip(mod_out, sim_out, strict=True):
            assert a["text"] == b["text"], (idx, a, b)
            assert a["timing"] == b["timing"], (idx, a, b)
            assert a["index"] == b["index"], (idx, a, b)
        assert mod_st["kana_merged"] == sim_st["merged"], idx
        assert mod_st["kana_kept"] == sim_st["kept"], idx
        assert mod_st["kana_moan_deleted"] == sim_st["deleted"], idx
        assert mod_st["kana_exempted"] == sim_st["exempted"], idx

