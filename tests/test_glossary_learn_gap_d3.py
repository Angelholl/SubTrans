"""D3 补测：glossary_learn 提取容错与锁内写回。

覆盖 LLM 提取容错链（模型探测/异常降级）、CSV 解析边界、原子写失败清理、
锁超时/陈旧锁清除，以及学习保存的损坏词库与幻觉词过滤。

全部以 monkeypatch 伪 ``openai``／``requests`` 模块与 ``tmp_path`` 驱动，
不发起真实网络调用、不触真实词库文件。
"""

from __future__ import annotations

import logging
import os
import sys
import types
from typing import Any

import pytest

from subtransjav.refine import glossary_learn as gl
from subtransjav.refine.glossary_learn import (
    _acquire_glossary_lock,
    _parse_csv_pairs,
    _release_glossary_lock,
    extract_glossary_from_pair,
    load_learned_glossary,
    save_learned_glossary,
)

LOGGER_NAME = "subtransjav.refine.glossary_learn"


# ---------------------------------------------------------------------------
# 伪模块
# ---------------------------------------------------------------------------

def _install_fake_openai(
    monkeypatch: pytest.MonkeyPatch,
    *,
    content: str = "",
    error: BaseException | None = None,
) -> dict[str, list[Any]]:
    """注入伪 ``openai``，记录客户端初始化与 chat 调用参数。"""
    calls: dict[str, list[Any]] = {"init": [], "create": []}

    class _Completions:
        def create(self, **kwargs: Any) -> Any:
            calls["create"].append(kwargs)
            if error is not None:
                raise error
            message = types.SimpleNamespace(content=content)
            return types.SimpleNamespace(
                choices=[types.SimpleNamespace(message=message)])

    class _OpenAI:
        def __init__(self, **kwargs: Any) -> None:
            calls["init"].append(kwargs)
            self.chat = types.SimpleNamespace(completions=_Completions())

    fake = types.ModuleType("openai")
    fake.OpenAI = _OpenAI  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "openai", fake)
    return calls


def _install_fake_requests(
    monkeypatch: pytest.MonkeyPatch,
    *,
    payload: dict[str, Any] | None = None,
    error: BaseException | None = None,
) -> list[tuple[str, Any]]:
    """注入伪 ``requests``，记录探测 GET 的 URL 与超时。"""
    calls: list[tuple[str, Any]] = []

    class _Response:
        def json(self) -> dict[str, Any]:
            return payload or {}

    def get(url: str, timeout: Any = None) -> _Response:
        calls.append((url, timeout))
        if error is not None:
            raise error
        return _Response()

    fake = types.ModuleType("requests")
    fake.get = get  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "requests", fake)
    return calls


# ---------------------------------------------------------------------------
# 1. 空输入 / 模型探测 / 异常降级
# ---------------------------------------------------------------------------

def test_extract_empty_inputs_return_empty() -> None:
    assert extract_glossary_from_pair("", "译文") == []
    assert extract_glossary_from_pair("   ", "译文") == []
    assert extract_glossary_from_pair("原文", "") == []
    assert extract_glossary_from_pair("原文", " \t\n") == []


def test_extract_probe_uses_first_model_id(monkeypatch) -> None:
    openai_calls = _install_fake_openai(monkeypatch, content="先生,老师")
    request_calls = _install_fake_requests(
        monkeypatch,
        payload={"data": [{"id": "model-one"}, {"id": "model-two"}]},
    )

    pairs = extract_glossary_from_pair(
        "先生が来た", "老师来了", endpoint="http://localhost:1234/v1")

    assert pairs == [("先生", "老师")]
    assert request_calls == [("http://localhost:1234/v1/models", 5.0)]
    assert openai_calls["create"][0]["model"] == "model-one"


def test_extract_probe_exception_is_silent(monkeypatch, caplog) -> None:
    _install_fake_openai(monkeypatch, content="先生,老师")
    _install_fake_requests(monkeypatch, error=RuntimeError("probe down"))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        pairs = extract_glossary_from_pair("先生が来た", "老师来了")

    assert pairs == []
    assert "无法确定本地模型" in caplog.text
    assert "词库提取失败" not in caplog.text  # 探测异常被静默吞掉


def test_extract_no_model_warns_and_returns_empty(monkeypatch, caplog) -> None:
    openai_calls = _install_fake_openai(monkeypatch, content="先生,老师")
    _install_fake_requests(monkeypatch, payload={"data": []})

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        pairs = extract_glossary_from_pair("先生が来た", "老师来了")

    assert pairs == []
    assert "无法确定本地模型" in caplog.text
    assert openai_calls["create"] == []


def test_extract_chat_exception_warns_and_returns_empty(monkeypatch, caplog) -> None:
    _install_fake_openai(monkeypatch, error=RuntimeError("chat down"))

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        pairs = extract_glossary_from_pair(
            "先生が来た", "老师来了", model="model-one")

    assert pairs == []
    assert "词库提取失败" in caplog.text


# ---------------------------------------------------------------------------
# 2. _parse_csv_pairs：分隔符 / 注释空行 / 同词丢弃 / 上限
# ---------------------------------------------------------------------------

def test_parse_csv_pairs_supports_three_separators() -> None:
    text = "先生,老师\n部屋\t房间\n東京，东京"
    assert _parse_csv_pairs(text) == [
        ("先生", "老师"), ("部屋", "房间"), ("東京", "东京")]


def test_parse_csv_pairs_skips_comments_and_blank_lines() -> None:
    text = "# 注释行\n\n先生,老师\n   \n# 另一条注释\n部屋,房间"
    assert _parse_csv_pairs(text) == [("先生", "老师"), ("部屋", "房间")]


def test_parse_csv_pairs_drops_identical_src_dst() -> None:
    text = "IKU,IKU\n先生,老师\nです,です"
    assert _parse_csv_pairs(text) == [("先生", "老师")]


def test_parse_csv_pairs_caps_at_20_entries() -> None:
    text = "\n".join(f"词{i},译{i}" for i in range(25))
    pairs = _parse_csv_pairs(text)
    assert len(pairs) == 20
    assert pairs[0] == ("词0", "译0")
    assert pairs[-1] == ("词19", "译19")


# ---------------------------------------------------------------------------
# 3. save_learned_glossary：ASCII 小写去重 / 原子写失败清理
# ---------------------------------------------------------------------------

def test_save_dedup_ascii_src_lowercase(tmp_path) -> None:
    p = str(tmp_path / "learned.csv")
    save_learned_glossary(p, [
        ("IKU", "去了"),
        ("iku", "去了"),
        ("Mura", "村"),
        ("mura", "另一个译法"),
    ])
    assert load_learned_glossary(p) == [
        ("IKU", "去了"), ("Mura", "村"), ("mura", "另一个译法")]


def test_save_replace_failure_cleans_temp_file(tmp_path, monkeypatch) -> None:
    p = tmp_path / "learned.csv"

    def _boom(src: str, dst: str) -> None:
        raise KeyboardInterrupt("replace interrupted")

    monkeypatch.setattr(gl.os, "replace", _boom)

    with pytest.raises(KeyboardInterrupt):
        save_learned_glossary(str(p), [("先生", "老师")])

    assert not p.exists()
    assert os.listdir(tmp_path) == [], "原子写失败后不应残留临时文件"


# ---------------------------------------------------------------------------
# 4. 锁：陈旧清除 / 超时 / 学习保存降级
# ---------------------------------------------------------------------------

def test_lock_stale_by_mtime_is_cleared(tmp_path) -> None:
    p = str(tmp_path / "learned.csv")
    lock_path = p + ".lock"
    with open(lock_path, "w", encoding="utf-8") as f:
        f.write("99999")
    os.utime(lock_path, (0, 0))  # 模拟崩溃残留的陈旧锁

    lock = _acquire_glossary_lock(p, timeout=1.0, stale_after=60.0)
    assert lock == lock_path
    assert os.path.isfile(lock)
    _release_glossary_lock(lock)
    assert not os.path.isfile(lock_path)


def test_lock_timeout_returns_none(tmp_path) -> None:
    p = str(tmp_path / "learned.csv")
    lock_path = p + ".lock"
    with open(lock_path, "w", encoding="utf-8") as f:
        f.write("99999")

    try:
        assert _acquire_glossary_lock(p, timeout=0.2) is None
        assert os.path.isfile(lock_path), "超时不应删除他人持有的新鲜锁"
    finally:
        os.remove(lock_path)


def _s2_files(tmp_path, src: str, dst: str) -> tuple[str, str]:
    in_f = tmp_path / "s2_in.txt"
    in_f.write_text(src, encoding="utf-8")
    out_f = tmp_path / "s2_out.txt"
    out_f.write_text(dst, encoding="utf-8")
    return str(in_f), str(out_f)


def test_learn_lock_timeout_returns_zero(tmp_path, monkeypatch, caplog) -> None:
    p = tmp_path / "learned.csv"
    p.write_text("旧词,旧译\n", encoding="utf-8-sig")
    before = p.read_bytes()
    in_f, out_f = _s2_files(tmp_path, "新词", "新译")
    monkeypatch.setattr(gl, "extract_glossary_from_pair",
                        lambda *a, **k: [("新词", "新译")])
    monkeypatch.setattr(gl, "_acquire_glossary_lock", lambda *a, **k: None)

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        n = gl.learn_from_s2_output(in_f, out_f, str(p))

    assert n == 0
    assert p.read_bytes() == before
    assert "锁" in caplog.text


def test_learn_corrupt_strict_read_returns_zero(tmp_path, monkeypatch, caplog) -> None:
    p = tmp_path / "learned.csv"
    p.write_bytes(b"\xff\xfe\x00bad-bytes")
    before = p.read_bytes()
    in_f, out_f = _s2_files(tmp_path, "新しい", "術語")
    monkeypatch.setattr(gl, "extract_glossary_from_pair",
                        lambda *a, **k: [("新しい", "術語")])

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        n = gl.learn_from_s2_output(in_f, out_f, str(p))

    assert n == 0
    assert p.read_bytes() == before
    assert "损坏" in caplog.text


def test_learn_filters_hallucinated_pairs(tmp_path, monkeypatch, caplog) -> None:
    p = tmp_path / "learned.csv"
    in_f, out_f = _s2_files(tmp_path, "新词と新語", "新译与新訳")
    monkeypatch.setattr(gl, "extract_glossary_from_pair", lambda *a, **k: [
        ("新词", "新译"),
        ("幻觉词", "新译"),
        ("新語", "幻觉译"),
    ])

    with caplog.at_level(logging.WARNING, logger=LOGGER_NAME):
        n = gl.learn_from_s2_output(in_f, out_f, str(p))

    assert n == 1
    assert load_learned_glossary(str(p)) == [("新词", "新译")]
    assert "过滤 2 条" in caplog.text
