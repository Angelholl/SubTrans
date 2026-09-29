"""中/英分词提示测试（2.1，D2026-0930-05）：生成、分派与缓存隔离。

假 jieba 一律 monkeypatch token_hint._get_jieba（不碰 sys.modules/
find_spec，评议员 R2 裁定）；真 jieba 用例单独 skipif（未安装即跳）。
全文件不依赖真 jieba 可跑（skipif 那枚除外）。
"""
import importlib.util
from types import SimpleNamespace

import pytest

import subtransjav.refine.grammar_hint as gh
import subtransjav.refine.pipeline_v2 as pv
import subtransjav.refine.token_hint as token_hint
from subtransjav.refine.pipeline_v2 import (
    _collect_grammar_hints,
    _direction_key,
)


# ---------------------------------------------------------------------------
# Fixtures 与最小替身
# ---------------------------------------------------------------------------
def _entries(*texts):
    """最小条目列表（parse_srt 同款键：index/timing/text）。"""
    return [{"index": i,
             "timing": f"00:00:{i:02d},000 --> 00:00:{i + 1:02d},000",
             "text": t} for i, t in enumerate(texts, 1)]


class FakeJieba:
    """最小 jieba 替身：cut 返回预设 token 序列（可注入异常）。"""

    def __init__(self, tokens=None, error=None):
        self.tokens = tokens or []
        self.error = error
        self.calls = []

    def cut(self, text, **kwargs):
        self.calls.append(text)
        if self.error is not None:
            raise self.error
        return list(self.tokens)


@pytest.fixture(autouse=True)
def _reset_singletons(monkeypatch):
    """每例重置 jieba 单例状态与文法缓存，保证用例间互不污染。"""
    monkeypatch.setattr(token_hint, "_jieba_instance", None)
    monkeypatch.setattr(token_hint, "_zh_available", None)
    pv._GRAMMAR_CACHE.clear()
    yield
    pv._GRAMMAR_CACHE.clear()


# ---------------------------------------------------------------------------
# generate_zh_hints（①-⑤、⑨ + srt 解析路径）
# ---------------------------------------------------------------------------
def test_zh_hints_normal_line(monkeypatch):
    """①含 CJK 长行且分词 ≥2 token：产出【语法提示】头+分词参考+token 串。"""
    fake = FakeJieba(["乒乓球", "拍卖", "完了"])
    monkeypatch.setattr(token_hint, "_get_jieba", lambda: fake)
    out = token_hint.generate_zh_hints("", 1,
                                       entries=_entries("乒乓球拍卖完了的价钱是多少"))
    assert out.startswith("【语法提示】")
    assert "分词参考：" in out
    assert "乒乓球 | 拍卖 | 完了" in out


def test_zh_hints_short_line(monkeypatch):
    """②短行（<6 字符）：门槛不满足返回空串，且不触发分词。"""
    fake = FakeJieba(["你", "好"])
    monkeypatch.setattr(token_hint, "_get_jieba", lambda: fake)
    out = token_hint.generate_zh_hints("", 1, entries=_entries("你好呀"))
    assert out == ""
    assert fake.calls == []


def test_zh_hints_single_token(monkeypatch):
    """③剔除标点后仅剩单 token：无切分价值，返回空串。"""
    fake = FakeJieba(["莫名其妙"])
    monkeypatch.setattr(token_hint, "_get_jieba", lambda: fake)
    out = token_hint.generate_zh_hints("", 1, entries=_entries("莫名其妙呀呀"))
    assert out == ""


def test_zh_hints_pure_latin(monkeypatch):
    """④纯拉丁文本：不含 CJK 短路返回空串，不触发分词。"""
    fake = FakeJieba(["hello", "world"])
    monkeypatch.setattr(token_hint, "_get_jieba", lambda: fake)
    out = token_hint.generate_zh_hints("", 1, entries=_entries("hello world foo"))
    assert out == ""
    assert fake.calls == []


def test_zh_hints_punct_tokens_stripped(monkeypatch):
    """⑤纯标点/空白 token 被剔除：剩余有效 token 过门槛且不进提示串。"""
    fake = FakeJieba(["真的", "吗", "？？", "，", " "])
    monkeypatch.setattr(token_hint, "_get_jieba", lambda: fake)
    out = token_hint.generate_zh_hints("", 1, entries=_entries("真的吗真的吗"))
    assert "真的 | 吗" in out
    assert "？？" not in out


def test_zh_hints_exception_returns_empty(monkeypatch):
    """⑨分词异常：吞掉返回空串（宁缺毋滥，不阻塞管线）。"""
    fake = FakeJieba(error=RuntimeError("boom"))
    monkeypatch.setattr(token_hint, "_get_jieba", lambda: fake)
    out = token_hint.generate_zh_hints("", 1, entries=_entries("这是七个字的句子"))
    assert out == ""


def test_zh_hints_via_srt_parsing(monkeypatch):
    """entries=None 时走 parse_srt 解析路径（filters 联动）。"""
    fake = FakeJieba(["今天", "天气", "不错"])
    monkeypatch.setattr(token_hint, "_get_jieba", lambda: fake)
    srt = "1\n00:00:01,000 --> 00:00:02,000\n今天的天气真不错呀\n"
    out = token_hint.generate_zh_hints(srt, 1)
    assert "今天 | 天气 | 不错" in out


# ---------------------------------------------------------------------------
# generate_en_hints（⑥⑦，纯规则零依赖）
# ---------------------------------------------------------------------------
def test_en_hints_abbreviation():
    """⑥全大写缩写：提示含该缩写与保留原文建议。"""
    out = token_hint.generate_en_hints("", 1, entries=_entries("FBI open up now"))
    assert out.startswith("【语法提示】")
    assert "缩写『FBI』" in out
    assert "保留原文不译" in out


def test_en_hints_no_abbreviation():
    """⑦无 2+ 连续大写：返回空串。"""
    out = token_hint.generate_en_hints("", 1, entries=_entries("What is that thing"))
    assert out == ""


# ---------------------------------------------------------------------------
# 可用性探测（⑧）
# ---------------------------------------------------------------------------
def test_zh_unavailable_when_get_jieba_none(monkeypatch):
    """⑧_get_jieba 返回 None（[zh] 组件缺失）：可用性为 False。"""
    monkeypatch.setattr(token_hint, "_get_jieba", lambda: None)
    assert token_hint.is_zh_hint_available() is False


@pytest.mark.skipif(importlib.util.find_spec("jieba") is None,
                    reason="jieba（[zh] 可选组件）未安装")
def test_zh_hints_real_jieba_ambiguous():
    """真 jieba：经典歧义串能产出提示（宽松断言，切法不定）。"""
    out = token_hint.generate_zh_hints("", 1, entries=_entries("乒乓球拍卖完了"))
    assert out.startswith("【语法提示】")
    assert "分词参考：" in out


# ---------------------------------------------------------------------------
# pipeline_v2 分派与缓存（⑩-⑭，R4 字符串契约钉）
# ---------------------------------------------------------------------------
def test_dispatch_by_source_language(monkeypatch):
    """⑩源语言分派（R4）：zh→en 调 zh 分词；ja→zh 调 sudachi 路径。"""
    zh_calls, ja_calls = [], []
    entries = _entries("这个句子足够长可以分词", "これはテストです")

    def fake_zh(srt, idx, entries=None):
        zh_calls.append(idx)
        return "【语法提示】\n- 分词参考：假"

    def fake_ja(srt, idx, entries=None):
        ja_calls.append(idx)
        return "【语法提示】\n- 测试"

    monkeypatch.setattr(token_hint, "is_zh_hint_available", lambda: True)
    monkeypatch.setattr(token_hint, "generate_zh_hints", fake_zh)
    monkeypatch.setattr(gh, "is_grammar_hint_available", lambda: True)
    monkeypatch.setattr(gh, "generate_grammar_hints", fake_ja)

    _collect_grammar_hints(entries, entries, verbose=False,
                           tag="A", profile="p", direction="zh→en")
    assert len(zh_calls) == 2 and ja_calls == []

    _collect_grammar_hints(entries, entries, verbose=False,
                           tag="A", profile="p", direction="ja→zh")
    assert len(ja_calls) == 2
    assert len(zh_calls) == 2          # ja 路径不回调 zh 分词


def test_zh_backend_unavailable_returns_empty_dict(monkeypatch):
    """⑪zh 后端不可用：返回空 dict 不抛（静默降级）。"""
    monkeypatch.setattr(token_hint, "is_zh_hint_available", lambda: False)
    entries = _entries("这个句子足够长可以分词")
    out = _collect_grammar_hints(entries, entries, verbose=False,
                                 tag="A", profile="p", direction="zh→en")
    assert out == {}


def test_directions_do_not_cross_contaminate(monkeypatch):
    """⑫同文本双方向键不串：zh→en 注入假提示后，ja→zh 同文本走 ja 路径。"""
    entries = _entries("これはテストです")

    def fake_zh(srt, idx, entries=None):
        return "【语法提示】\n- 分词参考：假"

    def fake_ja(srt, idx, entries=None):
        return "【语法提示】\n- 日语句法"

    monkeypatch.setattr(token_hint, "is_zh_hint_available", lambda: True)
    monkeypatch.setattr(token_hint, "generate_zh_hints", fake_zh)
    monkeypatch.setattr(gh, "is_grammar_hint_available", lambda: True)
    monkeypatch.setattr(gh, "generate_grammar_hints", fake_ja)

    h_zh = _collect_grammar_hints(entries, entries, verbose=False,
                                  tag="A", profile="p", direction="zh→en")
    assert h_zh == {1: "【语法提示】\n- 分词参考：假"}

    h_ja = _collect_grammar_hints(entries, entries, verbose=False,
                                  tag="A", profile="p", direction="ja→zh")
    assert h_ja == {1: "【语法提示】\n- 日语句法"}


def test_cache_key_default_direction_byte_equal():
    """⑬字节等价钉：缺省 direction 与显式 "ja→zh" 缓存键逐字节一致。"""
    t = "テスト"
    assert pv._grammar_cache_key(t, "A", "local") == \
        pv._grammar_cache_key(t, "A", "local", "ja→zh")
    # _direction_key 缺省/缺席字段均产出 "ja→zh"（缺省方向字节不变自证）
    assert _direction_key(SimpleNamespace()) == "ja→zh"
    assert _direction_key(SimpleNamespace(
        source_lang="ja", target_lang="zh")) == "ja→zh"
    assert _direction_key(SimpleNamespace(
        source_lang="zh", target_lang="en")) == "zh→en"


def test_direction_passthrough_to_cache_key(monkeypatch):
    """⑭direction 透传钉：缓存键实参捕获到调用方传入的方向串。"""
    captured = []
    real_key = pv._grammar_cache_key

    def spy(text, tag, profile, direction="ja→zh"):
        captured.append(direction)
        return real_key(text, tag, profile, direction)

    monkeypatch.setattr(pv, "_grammar_cache_key", spy)
    monkeypatch.setattr(token_hint, "is_zh_hint_available", lambda: True)
    monkeypatch.setattr(token_hint, "generate_zh_hints",
                        lambda srt, idx, entries=None: "【语法提示】\n- 分词参考：假")
    entries = _entries("这个句子足够长可以分词")
    _collect_grammar_hints(entries, entries, verbose=False,
                           tag="A", profile="p", direction="zh→en")
    assert captured and all(d == "zh→en" for d in captured)


# ---------------------------------------------------------------------------
# 残留清理钉（方向无关，cleaner_rules 现状兜底）
# ---------------------------------------------------------------------------
def test_grammar_hint_residue_cleaner():
    """残留清理钉：【语法提示】块 + " ||| " 回显兜底保留译文侧。"""
    from subtransjav.refine.cleaner_rules import clean_grammar_hint_residue
    dirty = "【语法提示】\n- 分词参考：X | Y\n原文：中文 ||| English line"
    assert clean_grammar_hint_residue(dirty) == "English line"


# ---------------------------------------------------------------------------
# en 方向英文回显清理（D2026-0930-05 批内缺陷修复：zh→en 冒烟实测形态）
# ---------------------------------------------------------------------------
_EN_ECHO_DIRTY = (
    "[Grammar Tip]\n"
    "- Word segmentation reference: Pingpong ball | auction | finished\n"
    "Original: The pingpong ball auction is over, "
    "let's practice again next week.\n"
    "**Final:**\n"
    "[Grammar Tip]\n"
    "Word segmentation: Pingpong ball | auction | finished\n"
    "Source: The pingpong ball auction is over, "
    "let's practice again next week.\n"
    "English: The pingpong ball auction is over; \n"
    "let's practice again next week.")


def test_clean_residue_en_mode_strips_english_echo():
    """②en 方向：真实污染形态多行样例清理后只剩裸译文。"""
    from subtransjav.refine.cleaner_rules import clean_grammar_hint_residue
    out = clean_grammar_hint_residue(_EN_ECHO_DIRTY, "en")
    assert out == ("The pingpong ball auction is over; \n"
                   "let's practice again next week.")
    # 未注入提示的短条目被带偏的形态（"好的。"→ Okay.）同样收拾
    short = clean_grammar_hint_residue(
        "Okay.\n**Final:**\nEnglish: Okay.", "en")
    assert short == "Okay.\n\nOkay."


def test_clean_residue_default_ignores_english_echo():
    """③缺省行为钉：不传/传 zh 均不激活英文模式（缺省零感知）。"""
    from subtransjav.refine.cleaner_rules import clean_grammar_hint_residue
    for cleaned in (clean_grammar_hint_residue(_EN_ECHO_DIRTY),
                    clean_grammar_hint_residue(_EN_ECHO_DIRTY, "zh")):
        assert cleaned == _EN_ECHO_DIRTY.strip()
        assert "[Grammar Tip]" in cleaned
        assert "English: " in cleaned
