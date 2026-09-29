"""windowed（PyInstaller console=False）加固钉测试（2.0.0 双 EXE）。

GUI 主程序改 windowed 子系统后，sys.stdout/stderr 可能为：
- None（无控制台 attached）；
- PyInstaller 的 NullWriter（无 buffer / 无 encoding / 无 reconfigure）。
本文件钉死：console 工具链在此形态下绝不炸（容错跳过，原样保流）。
"""
import sys

from subtransjav.utils.console import (
    _fix_stream_encoding,
    safe_print,
    setup_console,
)


class _NullWriter:
    """模拟 PyInstaller windowed bootloader 提供的 NullWriter。"""

    def write(self, *args):  # noqa: ANN002, ANN003
        pass

    def flush(self):
        pass


def test_setup_console_with_none_streams(monkeypatch):
    """sys.stdout/stderr 均为 None 时 setup_console 不炸。"""
    monkeypatch.setattr(sys, "stdout", None)
    monkeypatch.setattr(sys, "stderr", None)
    setup_console()  # 不应抛任何异常


def test_fix_stream_encoding_nullwriter_untouched(monkeypatch):
    """NullWriter（无 buffer/reconfigure）→ 原样保留，不重建、不炸。"""
    nw_out, nw_err = _NullWriter(), _NullWriter()
    monkeypatch.setattr(sys, "stdout", nw_out)
    monkeypatch.setattr(sys, "stderr", nw_err)
    _fix_stream_encoding(nw_out, 1)
    _fix_stream_encoding(nw_err, 2)
    assert sys.stdout is nw_out
    assert sys.stderr is nw_err


def test_safe_print_nullwriter_no_encoding(monkeypatch):
    """stdout 无 encoding 属性时 safe_print 编码降级路径不 AttributeError。"""
    calls = {"n": 0}

    def fake_print(*args, **kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise UnicodeEncodeError("gbk", "日本語", 0, 1, "charmap")
        return None

    monkeypatch.setattr("builtins.print", fake_print)
    monkeypatch.setattr(sys, "stdout", _NullWriter())
    safe_print("日本語テスト")
    assert calls["n"] >= 2
