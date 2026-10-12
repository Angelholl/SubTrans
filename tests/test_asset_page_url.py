"""asset_page_url 单元钉（2.7.5 件A / D2026-1007-02，F1 媒体通道 origin 修复）。

钉四件事：
- 正常绝对路径 → file:/// 开头（scheme 钉，C6）；
- as_uri() 会抛 ValueError 的输入（实测=相对路径）→ 不抛、回退 str(path)；
- UNC 输入按 pathlib 实测行为断言（实测不抛 ValueError，评议员预设不成立）；
- pywebview 版本下限钉 >=6.2（gui-probe/本地 venv 与生产 gui extra 一致）。
"""
import os

import pytest

pytestmark = [pytest.mark.gui]

pytest.importorskip("webview", reason="pywebview 为可选 gui extra，未安装时跳过",
                    exc_type=ImportError)

from subtransjav.webview_gui.main import (  # noqa: E402  须在 importorskip 之后
    asset_page_url,
)


def test_absolute_path_returns_file_uri():
    """正常绝对路径 → file:/// 开头（C6 scheme 钉）；中文/空格正确转义。"""
    url = asset_page_url("D:/some/dir/index.html")
    assert url.startswith("file:///")
    assert url.endswith("index.html")

    url2 = asset_page_url("D:/some dir/中文/index.html")
    assert url2.startswith("file:///D:/some%20dir/")
    assert "中文" not in url2  # as_uri 百分号转义


def test_relative_path_valueerror_falls_back_to_str():
    """实测（Python 3.12 pathlib）：相对路径 as_uri() 抛
    ValueError("relative path can't be expressed as a file URI") →
    本函数不得外抛，回退 str(path)。"""
    fallback = asset_page_url("relative/index.html")
    assert fallback == "relative/index.html"


def test_unc_path_does_not_raise():
    """实测（Python 3.12.10 pathlib）：UNC //srv/share/x.html 不抛 ValueError，
    得 file://srv/share/x.html（保留主机段，无 localhost 前缀）——评议员
    预设「UNC 抛 ValueError」不成立，以实测为准钉行为。"""
    url = asset_page_url("//srv/share/index.html")
    assert url.startswith("file://")
    assert "srv" in url and "index.html" in url


def test_pathlib_unc_baseline_documented():
    """pathlib 基线自证：按平台钉 as_uri 对 UNC 的实测形态，防未来 Python
    升级悄悄改行为时本文件两条 UNC 断言失真仍无人察觉。
    实测：Windows（PureWindowsPath）→ file://srv/share/index.html（2 斜杠，
    主机段即 authority）；POSIX（PurePosixPath）→ file:////srv/...（4 斜杠，
    RFC 8089 双斜杠 authority 保留）。"""
    from pathlib import Path, PurePosixPath
    if os.name == "nt":
        assert Path("//srv/share/index.html").as_uri() == "file://srv/share/index.html"
    else:
        assert PurePosixPath("//srv/share/index.html").as_uri() == "file:////srv/share/index.html"


def test_pywebview_version_floor():
    """pywebview 版本下限钉 >=6.2（与 pyproject gui extra ">=6.2,<7" 对齐）。"""
    from importlib.metadata import version
    raw = version("pywebview")
    major, minor = (int(x) for x in raw.split(".")[:2])
    assert (major, minor) >= (6, 2), f"pywebview {raw} 低于媒体通道口径下限 6.2"
