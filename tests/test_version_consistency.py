"""版本号单一事实源一致性校验（D2026-1001 owner 拍板：回填防复发）。

main 分支曾滞留 2.0.0（发版 bump 落在 release/2.1.1 分支未回填），
导致用户 CMD 显示 v2.0.0 被误判为旧安装。本钉保证 pyproject 与
__version__.py 永远同步；下一次 bump 时两处一起改，测试即守护。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_version() -> str:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.M)
    assert m, "pyproject.toml 缺少 [project] version"
    return m.group(1)


def test_pyproject_version_matches_dunder_version():
    from subtransjav.__version__ import __version__

    assert _pyproject_version() == __version__, (
        "pyproject.toml version 与 subtransjav/__version__.py __version__ 不一致；"
        "bump 版本时两处必须同批修改"
    )


def test_display_version_tracks_pep440_version():
    from subtransjav.__version__ import __version__, __version_display__

    assert __version_display__ == __version__, (
        "__version_display__（UI About/CMD 显示）必须与 __version__ 一致"
    )


def test_version_info_tracks_pep440_version():
    from subtransjav.__version__ import __version__, __version_info__

    # main 常驻滚动 dev 号（D2026-1001-03 第⑧项）：__version__ 形如 "2.3.0.dev0"，
    # 仅取前三段数字段校验；发布版无 dev 后缀时同样兼容，断言语义不变
    major, minor, patch = (int(x) for x in __version__.split(".")[:3])
    assert __version_info__["major"] == major
    assert __version_info__["minor"] == minor
    assert __version_info__["patch"] == patch
