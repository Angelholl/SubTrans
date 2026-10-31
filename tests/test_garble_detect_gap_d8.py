"""garble_detect 分词降级链与扫描过滤补测（R1v3 卡D8，纯测试新增）。

全部以 monkeypatch 伪分词注入，**不依赖真实 sudachi/.dic 资产**——干净
环境（无 sudachipy/词典）亦全绿。覆盖缺口：

- ``_tokenize_ja`` 分词底层异常 → None（不外抛）；
- ``judge_garble_text`` 三条降级支：分词不可用 / morpheme ``is_oov()``
  异常 / ``total == 0`` 防御守卫，恒返回 ``(False, 0.0)``；
- ``scan_garble_suspects`` 可用性门（``_sudachi_ready`` False）与条目级
  预过滤（非 dict / 短句 / 无假名 / 空文本），以及外层异常兜底
  （``available=False``）；
- 命中条目字段形状（index/timing/text/oov_ratio 四位四舍五入）。
"""

from subtransjav.refine import garble_detect
from subtransjav.refine import grammar_hint as _gh
from subtransjav.refine.garble_detect import judge_garble_text, scan_garble_suspects

_T = "00:00:01,000 --> 00:00:02,000"


class _FakeMorpheme:
    """morpheme 鸭子型：surface()/is_oov() 与 sudachipy 接口对齐。"""

    def __init__(self, surface: str, oov: bool = False) -> None:
        self._surface = surface
        self._oov = oov

    def surface(self) -> str:
        return self._surface

    def is_oov(self) -> bool:
        return self._oov


class _BoomMorpheme:
    """``is_oov()`` 抛错的鸭子型 morpheme（钉 morpheme 接口异常降级支）。"""

    def surface(self) -> str:
        return "あ"

    def is_oov(self) -> bool:
        raise RuntimeError("morpheme exploded")


class _LenToggleCore(str):
    """len 可切换的 str 子类：首次 ``len()`` 走真值，其后恒 0。

    正常 str 下 ``len(core) < MIN_CORE_CHARS`` 门与 ``total = len(core)``
    取同值，``total == 0`` 守卫不可达；仅靠 len 可切换子类才能触达该
    防御分支（防未来重构时守卫被无声删除）。
    """

    def __new__(cls, value: str) -> "_LenToggleCore":
        obj = super().__new__(cls, value)
        obj._len_calls = 0
        return obj

    def __len__(self) -> int:
        self._len_calls += 1
        return super().__len__() if self._len_calls == 1 else 0


def test_tokenize_ja_exception_returns_none(monkeypatch):
    """``_tokenize_ja`` 底层分词抛错不外抛（返回 None），正常则原样透传。"""
    sentinel = [_FakeMorpheme("あ")]
    monkeypatch.setattr(_gh, "_tokenize_cached", lambda _text: sentinel)
    assert garble_detect._tokenize_ja("あいうえ") is sentinel

    def _boom(_text):
        raise RuntimeError("tokenizer exploded")

    monkeypatch.setattr(_gh, "_tokenize_cached", _boom)
    assert garble_detect._tokenize_ja("あいうえ") is None


def test_judge_degrades_on_tokenize_and_oov_failure(monkeypatch):
    """分词链抛错 / morpheme ``is_oov()`` 抛错 → 双支降级 (False, 0.0)。"""

    def _boom(_text):
        raise RuntimeError("tokenize exploded")

    monkeypatch.setattr(garble_detect, "_tokenize_ja", _boom)
    assert judge_garble_text("あいうえおかきくけこ") == (False, 0.0)

    monkeypatch.setattr(garble_detect, "_tokenize_ja", lambda _text: [_BoomMorpheme()])
    assert judge_garble_text("あいうえおかきくけこ") == (False, 0.0)


def test_judge_zero_total_guard(monkeypatch):
    """``total == 0`` 防御守卫：即使全 OOV 也返回 (False, 0.0)，不触发除零。"""
    monkeypatch.setattr(garble_detect, "_core_chars", lambda _text: _LenToggleCore("あいうえお"))
    monkeypatch.setattr(garble_detect, "_tokenize_ja", lambda _text: [_FakeMorpheme("あいうえお", oov=True)])
    assert judge_garble_text("あいうえお") == (False, 0.0)


def test_scan_unavailable_gate_and_entry_filters(monkeypatch):
    """可用性门优先于内容；就绪时非 dict/短句/无假名/空文本条目一律跳过。"""
    entries = [
        {"index": 1, "timing": _T, "text": "あいうえおかきくけこ"},   # 合格条目
        {"index": 2, "timing": _T, "text": "ああ"},                   # 短于 MIN_CORE_CHARS
        {"index": 3, "timing": _T, "text": "hello world!"},           # 无假名
        {"index": 4, "timing": _T, "text": "漢字表記統一協会"},        # 无假名
        {"index": 5, "timing": _T, "text": None},                     # 空文本
        "not-a-dict",                                                 # 非 dict
        42,                                                           # 非 dict
    ]

    # 门一：sudachi 未就绪 → 整体降级，不进入条目循环
    monkeypatch.setattr(garble_detect, "_sudachi_ready", lambda: False)
    assert scan_garble_suspects(entries) == {"available": False, "items": []}

    # 门二：就绪但伪分词全为已知词 → 仅合格条目进入判定且不命中
    monkeypatch.setattr(garble_detect, "_sudachi_ready", lambda: True)
    monkeypatch.setattr(garble_detect, "_tokenize_ja", lambda text: [_FakeMorpheme(text)])
    assert scan_garble_suspects(entries) == {"available": True, "items": []}


def test_scan_hit_item_fields_and_outer_exception_degrades(monkeypatch):
    """命中条目四字段齐备（oov_ratio 四位四舍五入）；外层异常 → 报告面缺席。"""
    core = "あいうえおかきくけこさし"   # 12 字：5 字 OOV + 7 字已知
    monkeypatch.setattr(garble_detect, "_sudachi_ready", lambda: True)
    monkeypatch.setattr(
        garble_detect,
        "_tokenize_ja",
        lambda _text: [_FakeMorpheme("あいうえお", oov=True), _FakeMorpheme("かきくけこさし")],
    )
    res = scan_garble_suspects([{"index": 3, "timing": _T, "text": core}, {"text": core}])
    assert res["available"] is True
    first, second = res["items"]
    assert set(first) == {"index", "timing", "text", "oov_ratio"}
    assert first["index"] == 3
    assert first["timing"] == _T
    assert first["text"] == core
    assert first["oov_ratio"] == round(5 / 12, 4) == 0.4167

    # 缺省字段：index=None、timing=""（不因取缺省而漏项）
    assert second["index"] is None
    assert second["timing"] == ""
    assert second["oov_ratio"] == 0.4167

    # 外层异常兜底：扫描链任何异常 = available=False（绝不抛错阻断报告）
    def _boom(_text):
        raise RuntimeError("core exploded")

    monkeypatch.setattr(garble_detect, "_core_chars", _boom)
    assert scan_garble_suspects([{"index": 1, "timing": _T, "text": core}]) == {"available": False, "items": []}
