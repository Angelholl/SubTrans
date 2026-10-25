"""
替2 确定性对话行检测器测试（D2026-1025-01 批6 b 项）。

信号①（应答词形态）：句末标点后尾段剥标点后为纯假名且核心 ≤4 字；
信号②（单 cue 双句末标点）：剥除引号/括号后句末标点 ≥2 次。
整条 ≤4 字纯假名豁免（a 项独立成行面）。纯函数、确定性。
"""

from subtransjav.refine.dialogue_detect import (
    DIALOGUE_TAIL_MAX,
    SENT_END_PUNCTS,
    build_injection_block,
    detect_dialogue_rows,
)


def _e(i, text):
    return {"index": i, "timing": "", "text": text}


# ---------------------------------------------------------------------------
# 信号①：应答词形态（句末标点后尾段）
# ---------------------------------------------------------------------------

def test_signal1_tail_four_kana_triggers():
    """尾段 4 字纯假名 → 触发（边界内）。"""
    assert detect_dialogue_rows([_e(1, "そうだな。うんうん")]) == {1}


def test_signal1_tail_five_kana_not_trigger():
    """尾段 5 字纯假名 → 不触（边界外）。"""
    assert detect_dialogue_rows(
        [_e(1, "そうだな。うんうんうん")]) == set()


def test_signal1_tail_with_kanji_not_trigger():
    """尾段含汉字（非纯假名）→ 如实判定不触。"""
    assert detect_dialogue_rows([_e(1, "そうだ。行くよ")]) == set()


def test_signal1_tail_katakana_long_vowel_triggers():
    """尾段含片假名长音「ー」仍属纯假名 → 触发。"""
    assert detect_dialogue_rows([_e(1, "ええと。サービス")]) == {1}


def test_signal1_no_sentence_end_punct_not_trigger():
    """无句末标点 → 不触。"""
    assert detect_dialogue_rows([_e(1, "こんにちは")]) == set()


def test_signal1_punct_at_end_empty_tail_not_trigger():
    """句末标点在行尾（尾段为空）→ 不触。"""
    assert detect_dialogue_rows([_e(1, "そうですね。")]) == set()


def test_signal1_tail_with_kaiten_punct_still_counts():
    """尾段内含逗号等标点：剥标点后核心纯假名 ≤4 → 触发。"""
    assert detect_dialogue_rows([_e(1, "わかった。うん、そう")]) == {1}


# ---------------------------------------------------------------------------
# 整条 ≤4 字纯假名豁免（a 项独立成行面）
# ---------------------------------------------------------------------------

def test_whole_short_pure_kana_exempt():
    """整条剥标点后 ≤4 字纯假名 → 不触（含双标点也不触）。"""
    assert detect_dialogue_rows([_e(1, "うん。はい")]) == set()
    assert detect_dialogue_rows([_e(2, "はい。")]) == set()


def test_whole_five_kana_with_double_punct_triggers():
    """整条 5 字纯假名不豁免，双句末标点按信号② 触发。"""
    assert detect_dialogue_rows([_e(1, "うん。はい。えっ")]) == {1}


# ---------------------------------------------------------------------------
# 信号②：单 cue 双句末标点
# ---------------------------------------------------------------------------

def test_signal2_double_punct_triggers():
    """双句末标点且尾段非纯假名短尾 → 仅信号② 触发。"""
    assert detect_dialogue_rows(
        [_e(1, "えっと。行きます。よろしくお願いします")]) == {1}


def test_signal2_single_punct_not_trigger():
    """单句末标点（尾段非纯假名短尾）→ 不触。"""
    assert detect_dialogue_rows(
        [_e(1, "今日はいい天気ですね。お弁当を持って")]) == set()


def test_signal2_quotes_stripped_before_counting():
    """引号内句末标点按剥除口径参与计数：内 1＋外 1 = 2 → 触发。"""
    assert detect_dialogue_rows(
        [_e(1, "彼は「はい。」と言った。ええ")]) == {1}
    # 引号内仅 1 个句末标点（剥引号后仍 1）→ 不触
    assert detect_dialogue_rows([_e(2, "「はい。」と言った")]) == set()


# ---------------------------------------------------------------------------
# 确定性
# ---------------------------------------------------------------------------

def test_deterministic_same_input_same_result():
    """同输入两次检测结果一致（确定性契约）。"""
    entries = [_e(1, "そうだな。うん"), _e(2, "こんにちは"),
               _e(3, "えっ。そう。知らなかった"), _e(4, "部長で、エースで。")]
    assert detect_dialogue_rows(entries) == detect_dialogue_rows(entries)
    assert detect_dialogue_rows(entries) == {1, 3}


def test_constants_single_source():
    """常量单一来源：尾段上限 4、标点集含全半角。"""
    assert DIALOGUE_TAIL_MAX == 4
    assert set(SENT_END_PUNCTS) == {"。", "？", "！", "?", "!"}


# ---------------------------------------------------------------------------
# 注入文案
# ---------------------------------------------------------------------------

def test_injection_block_none_when_no_flagged():
    """无 flagged → 返回 None。"""
    entries = [_e(1, "こんにちは"), _e(2, "そうですね。")]
    assert build_injection_block(entries, set()) is None
    assert build_injection_block(entries, {9}) is None


def test_injection_block_contains_line_contract_and_line_numbers():
    """flagged 批文案含行数契约句＋行号清单（行号取条目 index）。"""
    entries = [_e(1, "こんにちは"), _e(2, "はい。そうです"),
               _e(3, "えっ。そう。知らなかった")]
    block = build_injection_block(entries, {2, 3})
    assert block is not None
    # 两句顺序固定：行数契约句在前，标注句在后
    assert block.index("禁止新增换行") < block.index("应按句读分开表达")
    assert "输出行数必须与输入条数一一对应" in block
    assert "禁止合并或拆分行" in block
    assert "禁止添加说话人前缀" in block
    assert "第 2、3 行" in block


def test_injection_block_deterministic_ordering():
    """flagged 乱序传入 → 行号清单仍升序确定。"""
    entries = [_e(1, "x"), _e(2, "はい。そうです"),
               _e(3, "y"), _e(4, "うん。そうだね")]
    assert build_injection_block(entries, {4, 2}) == \
        build_injection_block(entries, {2, 4})
    block = build_injection_block(entries, {4, 2})
    assert "第 2、4 行" in block
