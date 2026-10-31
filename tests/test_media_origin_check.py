"""main.bind_media_origin_check 单测（C1 卡A 件3，D2026-1031-05）。

2.7.5 件A 启动自检原为零单测函数：loaded 后经 evaluate_js 校验页面
origin，非 ``file:`` 时记 error 并插固定红色横幅。本文件三钉：
- file: → 零横幅插入、零 error；
- 非 file:（http:）→ 插入串含固定 id 与常量文案（常量从 main 导入比对）；
- evaluate_js 抛异常 → 不崩（容错路径）。
"""
import json
import logging

import pytest

pytest.importorskip("webview", reason="pywebview 为可选 gui extra，未安装时跳过 GUI 测试")

from subtransjav.webview_gui import main as gui_main  # noqa: E402

_LOGGER_NAME = "subtransjav.gui"
_BANNER_ID = "stj-media-origin-banner"


class _FakeLoaded:
    """pywebview ``window.events.loaded`` 的最小可累加替身。"""

    def __init__(self):
        self.callbacks = []

    def __iadd__(self, callback):
        self.callbacks.append(callback)
        return self

    def fire(self):
        for callback in list(self.callbacks):
            callback()


class _FakeEvents:
    def __init__(self):
        self.loaded = _FakeLoaded()


class _FakeWindow:
    """记录 evaluate_js 调用；protocol 为 location.protocol 预设回值。"""

    def __init__(self, protocol="file:", exc=None):
        self.events = _FakeEvents()
        self.protocol = protocol
        self.exc = exc
        self.calls = []

    def evaluate_js(self, script):
        self.calls.append(script)
        if self.exc is not None:
            raise self.exc
        if script == "location.protocol":
            return self.protocol
        return None

    def fire_loaded(self):
        self.events.loaded.fire()

    def insert_calls(self):
        return [c for c in self.calls if "insertAdjacentHTML" in c]


def _errors(caplog):
    return [r for r in caplog.records if r.levelno >= logging.ERROR]


def test_origin_check_file_protocol_silent(caplog):
    """file: → 只问 protocol，零横幅插入、零 error。"""
    caplog.set_level(logging.ERROR, logger=_LOGGER_NAME)
    window = _FakeWindow(protocol="file:")
    gui_main.bind_media_origin_check(window)

    assert len(window.events.loaded.callbacks) == 1
    window.fire_loaded()

    assert window.calls == ["location.protocol"]
    assert window.insert_calls() == []
    assert _errors(caplog) == []


def test_origin_check_non_file_inserts_banner(caplog):
    """非 file: → 插入串含固定 id 与常量文案，并记一条 error。"""
    caplog.set_level(logging.ERROR, logger=_LOGGER_NAME)
    window = _FakeWindow(protocol="http:")
    gui_main.bind_media_origin_check(window)
    window.fire_loaded()

    assert window.calls[0] == "location.protocol"
    inserts = window.insert_calls()
    assert len(inserts) == 1
    script = inserts[0]
    # 插入串第二参为 json.dumps 转义串（非 ASCII 走 \uXXXX），解回后比常量
    prefix = "document.body.insertAdjacentHTML('afterbegin', "
    assert script.startswith(prefix) and script.endswith(");")
    payload = json.loads(script[len(prefix):-2])
    assert _BANNER_ID in payload
    assert gui_main.MEDIA_ORIGIN_BANNER_TEXT in payload
    errors = _errors(caplog)
    assert len(errors) == 1 and "http:" in errors[0].getMessage()


def test_origin_check_evaluate_js_exception_tolerated():
    """evaluate_js 抛异常 → 全容错，不向调用方抛出。"""
    window = _FakeWindow(exc=RuntimeError("js bridge down"))
    gui_main.bind_media_origin_check(window)

    window.fire_loaded()  # 不抛异常即通过

    assert window.insert_calls() == []
