"""疑似听错规则型检测器（garble_detect，D2026-1025-01 批4）单元测试。

样例口径（卡面要求以实测为准）：sudachipy 0.7.0 + dict/sudachi/
system_full.dic 实证——
- ゔ 系非常见组合（ゔぁれんじゃ/ゔぉるじゃん）与异常片假名串
  （ヴェテャミョ）分词 OOV 占比 1.0，稳定命中；
- なんでるじゃんよー/見てくだひゃ 等真实 ASR 错音串被 MeCab OOV 兜底
  判为已知词（OOV 占比 0，漏报）——按卡面「判为已知即换样例并注明」
  处理，并以钉测试记录该保守行为，防未来阈值/词典变动时无声漂移；
- 正常句（今日はいい天気ですね 等）OOV 占比 0，不命中。
"""

import pytest

from subtransjav.refine import garble_detect
from subtransjav.refine import grammar_hint as _gh
from subtransjav.refine.garble_detect import (
    MIN_CORE_CHARS,
    OOV_RATIO_THRESHOLD,
    judge_garble_text,
    scan_garble_suspects,
)

# sudachi 可用性实测样例测试的前置（不可用环境跳过，降级路径另测）
_HAS_SUDACHI = garble_detect._sudachi_ready()

_T = "00:00:01,000 --> 00:00:02,000"


@pytest.fixture(autouse=True)
def _clear_gh_tokenize_cache():
    """隔离 grammar_hint 分词缓存：防跨用例串味（尤其降级 monkeypatch）。"""
    _gh._tokenize_cached.cache_clear()
    yield
    _gh._tokenize_cached.cache_clear()


# ----------------------------------------------------------------------
# 实测样例（真实 sudachi；不可用环境跳过）
# ----------------------------------------------------------------------

@pytest.mark.skipif(not _HAS_SUDACHI, reason="sudachi 不可用环境跳过实测样例")
def test_garble_samples_hit_with_real_sudachi():
    """乱串句命中：ゔ 系组合/异常片假名串 OOV 占比 1.0（实测）。"""
    for s in ("ゔぁれんじゃ", "ゔぉるじゃん", "ヴェテャミョ"):
        hit, ratio = judge_garble_text(s)
        assert hit, f"{s!r} 应命中"
        assert ratio >= OOV_RATIO_THRESHOLD


@pytest.mark.skipif(not _HAS_SUDACHI, reason="sudachi 不可用环境跳过实测样例")
def test_normal_sentences_not_flagged_with_real_sudachi():
    """正常句不命中：实义句/寒暄句 OOV 占比 0（实测）。"""
    for s in ("今日はいい天気ですね", "ありがとうございます",
              "ダメだよお願いだから", "ちょっと待ってくださいよ"):
        hit, ratio = judge_garble_text(s)
        assert not hit, f"{s!r} 不应命中"
        assert ratio == 0.0


@pytest.mark.skipif(not _HAS_SUDACHI, reason="sudachi 不可用环境跳过实测样例")
def test_real_asr_garble_known_words_pinned_conservative():
    """卡面原始样例 なんでるじゃんよー/見てくだひゃ 被 MeCab OOV 兜底判为
    已知词（漏报）——保守取向（宁漏勿滥）的实测注记钉：词典/阈值变动
    导致此处翻转时，应显式评审而非无声漂移。"""
    for s in ("なんでるじゃんよー", "見てくだひゃ"):
        hit, _ratio = judge_garble_text(s)
        assert not hit, f"{s!r} 当前词典口径判为已知，若翻转须重新评审样例"


@pytest.mark.skipif(not _HAS_SUDACHI, reason="sudachi 不可用环境跳过实测样例")
def test_scan_garble_suspects_shape_with_real_sudachi():
    """扫描产物形状：命中项含 index/timing/text/oov_ratio，短句与非日文行跳过。"""
    entries = [
        {"index": 1, "timing": _T, "text": "ゔぁれんじゃ"},
        {"index": 2, "timing": _T, "text": "今日はいい天気ですね"},
        {"index": 3, "timing": _T, "text": "ああ"},          # 短于 4 字不判
        {"index": 4, "timing": _T, "text": "hello world!"},  # 无假名不消费
        "not-a-dict",                                        # 非 dict 条目跳过
        {"index": 6, "timing": _T, "text": None},            # 空文本跳过
    ]
    res = scan_garble_suspects(entries)
    assert res["available"] is True
    assert len(res["items"]) == 1
    item = res["items"][0]
    assert item["index"] == 1
    assert item["timing"] == _T
    assert item["text"] == "ゔぁれんじゃ"
    assert item["oov_ratio"] >= OOV_RATIO_THRESHOLD


# ----------------------------------------------------------------------
# 不依赖 sudachi 的门控与阈值（假分词器注入）
# ----------------------------------------------------------------------

class _FakeMorpheme:
    """morpheme 鸭子型：surface()/is_oov() 接口与 sudachipy 对齐。"""

    def __init__(self, surface: str, oov: bool = False):
        self._surface = surface
        self._oov = oov

    def surface(self) -> str:
        return self._surface

    def is_oov(self) -> bool:
        return self._oov


def test_short_core_not_judged_even_all_oov():
    """短于 MIN_CORE_CHARS 的核心一律不判（即使全 OOV）。"""
    assert MIN_CORE_CHARS == 4
    assert judge_garble_text("ああ") == (False, 0.0)
    assert judge_garble_text("ゔぁれ") == (False, 0.0)   # 3 字全 OOV 也不判


def test_non_japanese_entries_not_consumed():
    """无假名的行不消费（语言门）：拉丁/纯标点/纯汉字数字。"""
    assert judge_garble_text("hello world!") == (False, 0.0)
    assert judge_garble_text("！！！？？？") == (False, 0.0)
    # 无假名行不触发分词：分词器缺席也应 (False, 0.0)（门在分词之前）
    assert judge_garble_text("漢字表記統一協会") == (False, 0.0)


def test_threshold_boundary_exactly_at_ratio_hits(monkeypatch):
    """阈值边界：OOV 占比恰等于阈值（0.4）判命中（≥ 口径）。"""
    monkeypatch.setattr(
        garble_detect, "_tokenize_ja",
        lambda _text: [_FakeMorpheme("あいうえお"),        # 已知 5 字
                       _FakeMorpheme("かきくけ", oov=True),  # OOV 4 字
                       _FakeMorpheme("こ")])               # 已知 1 字
    hit, ratio = judge_garble_text("あいうえおかきくけこ")
    assert ratio == pytest.approx(4 / 10)
    assert hit


def test_threshold_boundary_below_ratio_misses(monkeypatch):
    """阈值边界：OOV 占比低于阈值（0.3）不判（保守宁漏勿滥）。"""
    monkeypatch.setattr(
        garble_detect, "_tokenize_ja",
        lambda _text: [_FakeMorpheme("あいうえお"),
                       _FakeMorpheme("かき", oov=True),
                       _FakeMorpheme("くけこ")])
    hit, ratio = judge_garble_text("あいうえおかきくけこ")
    assert ratio == pytest.approx(2 / 10)
    assert not hit


def test_tokenize_exception_degrades_per_entry(monkeypatch):
    """单次分词异常按不可用降级：不抛错，返回 (False, 0.0)。"""

    def _boom(_text):
        raise RuntimeError("tokenize exploded")

    monkeypatch.setattr(garble_detect, "_tokenize_ja", _boom)
    assert judge_garble_text("ゔぁれんじゃ") == (False, 0.0)


# ----------------------------------------------------------------------
# 降级路径（sudachi 不可用，monkeypatch 初始化链）
# ----------------------------------------------------------------------

def test_degradation_tokenizer_none(monkeypatch):
    """分词器初始化返回 None → judge/scan 双降级：available=False、不抛错。"""
    monkeypatch.setattr(_gh, "_get_tokenizer", lambda: None)
    assert garble_detect._sudachi_ready() is False
    assert judge_garble_text("ゔぁれんじゃ") == (False, 0.0)
    res = scan_garble_suspects(
        [{"index": 1, "timing": _T, "text": "ゔぁれんじゃ"}])
    assert res == {"available": False, "items": []}


def test_degradation_init_raises(monkeypatch):
    """分词器初始化抛错（ImportError/词典缺失等）→ 同样优雅降级。"""

    def _boom():
        raise ImportError("no sudachipy")

    monkeypatch.setattr(_gh, "_get_tokenizer", _boom)
    assert garble_detect._sudachi_ready() is False
    res = scan_garble_suspects(
        [{"index": 1, "timing": _T, "text": "ゔぁれんじゃ"}])
    assert res == {"available": False, "items": []}


def test_scan_never_raises_on_degenerate_inputs(monkeypatch):
    """退化解构输入（None/非 dict/空列表）不抛错；降级态优先于内容。"""
    monkeypatch.setattr(garble_detect, "_sudachi_ready", lambda: False)
    assert scan_garble_suspects(None) == {"available": False, "items": []}
    monkeypatch.setattr(garble_detect, "_sudachi_ready", lambda: True)
    res = scan_garble_suspects(None)
    assert res == {"available": True, "items": []}
    assert scan_garble_suspects([]) == {"available": True, "items": []}
    assert scan_garble_suspects(["junk", 42, None]) == {
        "available": True, "items": []}


def test_constants_single_source():
    """常量单一来源钉：阈值 0.4 / 核心长下限 4（卡面建议值落定）。"""
    assert OOV_RATIO_THRESHOLD == 0.4
    assert MIN_CORE_CHARS == 4
