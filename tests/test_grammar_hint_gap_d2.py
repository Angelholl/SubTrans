"""D2 补测：grammar_hint 初始化降级链与规则 1–8。

全部以 monkeypatch 伪对象＋伪 token 流驱动，不依赖真实 sudachi 词典资产
（``.dic`` 属本地面，干净环境不存在）：通过 ``sys.modules`` 注入伪
``sudachipy``／伪 ``sudachidict_core``，规则检测则用带 ``surface()``／
``part_of_speech()`` 的伪 token 覆盖 Sudachi 路径与 fallback 正则路径。
"""

from __future__ import annotations

import sys
import types
from collections.abc import Iterator
from typing import Any

import pytest

# ---------------------------------------------------------------------------
# 伪对象
# ---------------------------------------------------------------------------

class _Tok:
    """Sudachi Morpheme 的最小伪对象。"""

    def __init__(self, surface: str, pos: tuple[str, ...]) -> None:
        self._surface = surface
        self._pos = pos

    def surface(self) -> str:
        return self._surface

    def part_of_speech(self) -> tuple[str, ...]:
        return self._pos


def _noun(surface: str) -> _Tok:
    return _Tok(surface, ("名詞", "普通名詞", "一般", "*", "*", "*"))


def _pronoun(surface: str) -> _Tok:
    return _Tok(surface, ("代名詞", "*", "*", "*", "*", "*"))


def _suffix(surface: str) -> _Tok:
    return _Tok(surface, ("接尾辞", "名詞的", "*", "*", "*", "*"))


def _particle(surface: str, kind: str = "格助詞") -> _Tok:
    return _Tok(surface, ("助詞", kind, "*", "*", "*", "*"))


def _verb(surface: str) -> _Tok:
    return _Tok(surface, ("動詞", "一般", "*", "*", "*", "*"))


def _aux_de() -> _Tok:
    return _Tok("で", ("助動詞", "*", "*", "*", "助動詞-ダ", "連用形-一般"))


def _punct(surface: str = "。") -> _Tok:
    return _Tok(surface, ("補助記号", "句点", "*", "*", "*", "*"))


class _StubTokenizer:
    def __init__(self, tokens: list[Any]) -> None:
        self._tokens = tokens

    def tokenize(self, text: str) -> list[Any]:
        return list(self._tokens)


def _install_fake_sudachipy(monkeypatch, dictionary_cls: type) -> None:
    fake = types.ModuleType("sudachipy")
    fake.Dictionary = dictionary_cls  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "sudachipy", fake)


def _install_fake_core(monkeypatch, tmp_path, *, with_dic: bool) -> None:
    base = tmp_path / "sudachidict_core"
    base.mkdir()
    init_file = base / "__init__.py"
    init_file.write_text("", encoding="utf-8")
    if with_dic:
        resources = base / "resources"
        resources.mkdir()
        (resources / "system.dic").write_bytes(b"")
    fake = types.ModuleType("sudachidict_core")
    fake.__file__ = str(init_file)
    monkeypatch.setitem(sys.modules, "sudachidict_core", fake)


def _runtime_errors_during(func) -> list[RuntimeError]:
    """用 sys.settrace 捕获 ``func`` 执行期间被内部 ``except`` 吞掉的 RuntimeError。"""
    captured: list[RuntimeError] = []

    def _trace(frame: Any, event: str, arg: tuple[Any, Any, Any]) -> Any:
        if event == "exception" and isinstance(arg[1], RuntimeError):
            captured.append(arg[1])
        return _trace

    previous = sys.gettrace()
    sys.settrace(_trace)
    try:
        func()
    finally:
        sys.settrace(previous)
    return captured


def _detect_with_tokens(
    monkeypatch,
    tokens: list[Any],
    *,
    text: str,
    context_before: list[dict] | None = None,
) -> list[str]:
    from subtransjav.refine import grammar_hint as gh

    monkeypatch.setattr(gh, "_get_tokenizer", lambda: _StubTokenizer(tokens))
    return gh._detect_rules(text, list(context_before or []), [])


# ---------------------------------------------------------------------------
# 状态隔离：每个用例都从冷单例 + 空缓存起跑
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _isolated_grammar_hint(monkeypatch) -> Iterator[None]:
    from subtransjav.refine import dict_manager
    from subtransjav.refine import grammar_hint as gh

    monkeypatch.setattr(gh, "_tokenizer_instance", None)
    monkeypatch.setattr(gh, "_sudachi_available", None)
    # 不依赖本机 dict/sudachi/*.dic 的探测结果
    monkeypatch.setattr(dict_manager, "sudachi_custom_dict_path", lambda: "")
    clear_cache = gh._tokenize_cached.cache_clear
    clear_cache()
    yield
    clear_cache()


# ---------------------------------------------------------------------------
# 1) _bundled_dict_missing
# ---------------------------------------------------------------------------

def test_bundled_dict_missing_import_error_returns_false(monkeypatch) -> None:
    from subtransjav.refine import grammar_hint as gh

    # sys.modules 置 None → import 抛 ImportError（模块整体缺席口径）
    monkeypatch.setitem(sys.modules, "sudachidict_core", None)
    assert gh._bundled_dict_missing() is False


def test_bundled_dict_missing_without_system_dic_returns_true(
    monkeypatch, tmp_path
) -> None:
    from subtransjav.refine import grammar_hint as gh

    _install_fake_core(monkeypatch, tmp_path, with_dic=False)
    assert gh._bundled_dict_missing() is True


def test_bundled_dict_missing_with_system_dic_returns_false(
    monkeypatch, tmp_path
) -> None:
    from subtransjav.refine import grammar_hint as gh

    _install_fake_core(monkeypatch, tmp_path, with_dic=True)
    assert gh._bundled_dict_missing() is False


# ---------------------------------------------------------------------------
# 2) Dictionary 初始化降级链
# ---------------------------------------------------------------------------

def test_custom_dict_failure_with_bundled_missing_raises_and_degrades(
    monkeypatch,
) -> None:
    from subtransjav.refine import dict_manager
    from subtransjav.refine import grammar_hint as gh

    constructed: list[str] = []

    class _FakeDictionary:
        def __init__(self, dict: str = "") -> None:  # noqa: A002 - 对齐真实签名
            self._path = dict
            constructed.append(dict)

        def create(self):
            if self._path:
                raise ValueError("bad custom dic")
            raise AssertionError("缺省词典缺失时不得尝试 create()")

    monkeypatch.setattr(gh, "_bundled_dict_missing", lambda: True)
    monkeypatch.setattr(
        dict_manager, "sudachi_custom_dict_path", lambda: "custom.dic"
    )
    _install_fake_sudachipy(monkeypatch, _FakeDictionary)

    captured = _runtime_errors_during(gh._get_tokenizer)

    assert constructed == ["custom.dic"]
    assert any("缺省" in str(exc) and "缺失" in str(exc) for exc in captured)
    assert gh._tokenizer_instance is None
    assert gh._sudachi_available is False


def test_custom_dict_failure_with_bundled_present_falls_back_and_warns(
    monkeypatch, capsys
) -> None:
    from subtransjav.refine import dict_manager
    from subtransjav.refine import grammar_hint as gh

    created: list[str] = []
    tokenizer = _Tok("猫", ("名詞",))

    class _FakeDictionary:
        def __init__(self, dict: str = "") -> None:  # noqa: A002
            self._path = dict
            created.append(dict)

        def create(self):
            if self._path:
                raise ValueError("bad custom dic")
            return tokenizer

    monkeypatch.setattr(gh, "_bundled_dict_missing", lambda: False)
    monkeypatch.setattr(
        dict_manager, "sudachi_custom_dict_path", lambda: "custom.dic"
    )
    _install_fake_sudachipy(monkeypatch, _FakeDictionary)

    assert gh._get_tokenizer() is tokenizer
    out = capsys.readouterr().out
    assert created == ["custom.dic", ""]
    assert "回退缺省加载" in out
    assert gh._sudachi_available is True

    # 双检锁命中：二次调用不再构造 Dictionary
    assert gh._get_tokenizer() is tokenizer
    assert created == ["custom.dic", ""]


def test_bundled_missing_without_custom_raises_and_degrades(monkeypatch) -> None:
    from subtransjav.refine import grammar_hint as gh

    constructed: list[str] = []

    class _FakeDictionary:
        def __init__(self, dict: str = "") -> None:  # noqa: A002
            constructed.append(dict)

        def create(self):
            raise AssertionError("缺省词典缺失时不得尝试 create()")

    monkeypatch.setattr(gh, "_bundled_dict_missing", lambda: True)
    _install_fake_sudachipy(monkeypatch, _FakeDictionary)

    captured = _runtime_errors_during(gh._get_tokenizer)

    assert constructed == []
    assert any("缺省" in str(exc) and "缺失" in str(exc) for exc in captured)
    assert gh._tokenizer_instance is None
    assert gh._sudachi_available is False


def test_custom_dict_loaded_by_path_when_available(monkeypatch) -> None:
    from subtransjav.refine import dict_manager
    from subtransjav.refine import grammar_hint as gh

    created: list[str] = []
    tokenizer = _Tok("犬", ("名詞",))

    class _FakeDictionary:
        def __init__(self, dict: str = "") -> None:  # noqa: A002
            self._path = dict
            created.append(dict)

        def create(self):
            return tokenizer

    monkeypatch.setattr(gh, "_bundled_dict_missing", lambda: False)
    monkeypatch.setattr(
        dict_manager, "sudachi_custom_dict_path", lambda: "custom.dic"
    )
    _install_fake_sudachipy(monkeypatch, _FakeDictionary)

    assert gh._get_tokenizer() is tokenizer
    assert created == ["custom.dic"]
    assert gh._sudachi_available is True


# ---------------------------------------------------------------------------
# 3) 双检锁与初始化异常降级
# ---------------------------------------------------------------------------

def test_double_checked_lock_initializes_singleton_once(monkeypatch) -> None:
    from subtransjav.refine import grammar_hint as gh

    inits: list[int] = []
    tokenizer = _Tok("空", ("名詞",))

    class _FakeDictionary:
        def __init__(self) -> None:
            inits.append(1)

        def create(self):
            return tokenizer

    monkeypatch.setattr(gh, "_bundled_dict_missing", lambda: False)
    _install_fake_sudachipy(monkeypatch, _FakeDictionary)

    first = gh._get_tokenizer()
    second = gh._get_tokenizer()
    assert first is second is tokenizer
    assert len(inits) == 1
    assert gh._sudachi_available is True


def test_initialization_exception_marks_unavailable_and_routes_fallback(
    monkeypatch,
) -> None:
    from subtransjav.refine import grammar_hint as gh

    class _BoomDictionary:
        def __init__(self, dict: str = "") -> None:  # noqa: A002
            pass

        def create(self):
            raise RuntimeError("sudachi init boom")

    monkeypatch.setattr(gh, "_bundled_dict_missing", lambda: False)
    _install_fake_sudachipy(monkeypatch, _BoomDictionary)

    assert gh._get_tokenizer() is None
    assert gh._tokenizer_instance is None
    assert gh._sudachi_available is False
    assert gh.is_grammar_hint_available() is False
    assert gh._tokenize_cached("初始化失败文本") is None

    calls: list[str] = []

    def _fake_fallback(text, context_before, context_after):
        calls.append(text)
        return ["FB-SENTINEL"]

    monkeypatch.setattr(gh, "_detect_rules_fallback", _fake_fallback)
    assert gh._detect_rules("初始化失败文本", [], []) == ["FB-SENTINEL"]
    assert calls == ["初始化失败文本"]


# ---------------------------------------------------------------------------
# 4) 规则 1–8（伪 token 流）
# ---------------------------------------------------------------------------

def test_rule1_sentential_copula_without_predicate(monkeypatch) -> None:
    hints = _detect_with_tokens(
        monkeypatch,
        [_noun("猫"), _particle("は", "係助詞"), _noun("犬"), _punct()],
        text="猫は犬。",
    )
    assert any("补出" in hint for hint in hints)


def test_rule1_not_fired_when_predicate_exists(monkeypatch) -> None:
    hints = _detect_with_tokens(
        monkeypatch,
        [_noun("猫"), _particle("は", "係助詞"), _verb("走る")],
        text="猫は走る",
    )
    assert not any("补出" in hint for hint in hints)


def test_rule2_topic_marker_wa(monkeypatch) -> None:
    hints = _detect_with_tokens(
        monkeypatch,
        [_noun("猫"), _particle("は", "係助詞"), _verb("走る")],
        text="猫は走る",
    )
    assert any("「猫は」" in hint and "主题" in hint for hint in hints)


def test_rule3_subject_marker_ga(monkeypatch) -> None:
    hints = _detect_with_tokens(
        monkeypatch,
        [_noun("猫"), _particle("が", "格助詞"), _verb("走る")],
        text="猫が走る",
    )
    assert any("「猫が」" in hint and "主语" in hint for hint in hints)
    assert not any("转折" in hint for hint in hints)


def test_rule4_connective_particle(monkeypatch) -> None:
    ga_hints = _detect_with_tokens(
        monkeypatch,
        [_noun("雨"), _particle("が", "接続助詞"), _verb("降る")],
        text="雨が降るが",
    )
    assert any("「が」" in hint and "转折" in hint for hint in ga_hints)

    kedo_hints = _detect_with_tokens(
        monkeypatch,
        [_verb("降る"), _particle("けど", "接続助詞"), _verb("行く")],
        text="降るけど行く",
    )
    assert any("「けど」" in hint and "转折" in hint for hint in kedo_hints)


def test_rule5_possessive_no(monkeypatch) -> None:
    hints = _detect_with_tokens(
        monkeypatch,
        [_noun("水泳部"), _particle("の"), _noun("部長")],
        text="水泳部の部長",
    )
    assert any("水泳部の部長" in hint and "修饰关系" in hint for hint in hints)


def test_rule6_context_ellipsis(monkeypatch) -> None:
    # 无 は/が、无格助词，句末「で」不完整收尾
    tokens = [_noun("部長"), _aux_de()]
    hints = _detect_with_tokens(
        monkeypatch,
        tokens,
        text="部長で",
        context_before=[{"text": "先輩は優しい"}],
    )
    assert any("省略" in hint for hint in hints)

    # 上下文无 は/が 可推断 → 不触发省略提示
    no_ctx_hints = _detect_with_tokens(
        monkeypatch,
        tokens,
        text="部長で…",
        context_before=[{"text": "今日も暑い"}],
    )
    assert not any("省略" in hint for hint in no_ctx_hints)


def test_rule7_plural_pronoun_adnominal(monkeypatch) -> None:
    from subtransjav.refine import grammar_hint as gh

    # 拆分形态：ボク(代名詞) + たち(接尾辞) + 名词 + で(格助詞 句末)
    split_hints = _detect_with_tokens(
        monkeypatch,
        [
            _pronoun("ボク"),
            _suffix("たち"),
            _noun("水泳部"),
            _particle("の"),
            _noun("部長"),
            _particle("で", "格助詞"),
            _punct("…"),
        ],
        text="ボクたち、水泳部の部長で…",
    )
    assert gh._HINT_PLURAL_ADNOMINAL in split_hints
    assert gh._HINT_DE_RENTOU not in split_hints

    # 整体形态：僕たち 单个 token + で(助動詞)
    merged_hints = _detect_with_tokens(
        monkeypatch,
        [_pronoun("僕たち"), _noun("水泳部"), _aux_de()],
        text="僕たち水泳部で",
    )
    assert gh._HINT_PLURAL_ADNOMINAL in merged_hints


def test_rule8_da_renyokei_de(monkeypatch) -> None:
    from subtransjav.refine import grammar_hint as gh

    hints = _detect_with_tokens(
        monkeypatch,
        [_noun("部長"), _aux_de(), _noun("エース")],
        text="部長でエース",
    )
    assert gh._HINT_DE_RENTOU in hints
    assert any("判断助动词" in hint for hint in hints)


# ---------------------------------------------------------------------------
# 5) fallback：路由与正则路径
# ---------------------------------------------------------------------------

def test_detect_rules_routes_to_fallback_when_tokenize_returns_none(
    monkeypatch,
) -> None:
    from subtransjav.refine import grammar_hint as gh

    monkeypatch.setattr(gh, "_get_tokenizer", lambda: None)
    monkeypatch.setattr(
        gh,
        "_detect_rules_fallback",
        lambda text, context_before, context_after: ["FB-SENTINEL"],
    )
    assert gh._detect_rules("fallback 路由", [], []) == ["FB-SENTINEL"]


def test_fallback_regex_covers_connective_possessive_ellipsis_plural() -> None:
    from subtransjav.refine import grammar_hint as gh

    connective = gh._detect_rules_fallback("先輩は優しいけど、厳しいです。", [], [])
    assert any("けど" in hint and "转折" in hint for hint in connective)

    possessive = gh._detect_rules_fallback("水泳部の部長", [], [])
    assert any("水泳部の部長" in hint for hint in possessive)

    ellipsis = gh._detect_rules_fallback(
        "水泳部の部長で…", [{"text": "先輩は優しい"}], []
    )
    assert any("省略" in hint for hint in ellipsis)

    plural = gh._detect_rules_fallback("ボクたち、水泳部の部長で…", [], [])
    assert gh._HINT_PLURAL_ADNOMINAL in plural
    # 纯正则无法区分 格助詞/助動詞 的 で，规则⑧在 fallback 跳过
    assert gh._HINT_DE_RENTOU not in plural


def test_fallback_plural_not_fired_for_wa_ga_subject() -> None:
    from subtransjav.refine import grammar_hint as gh

    for text in ("僕たちは部長だ", "僕たちが公園で遊ぶ"):
        assert gh._HINT_PLURAL_ADNOMINAL not in gh._detect_rules_fallback(
            text, [], []
        )
