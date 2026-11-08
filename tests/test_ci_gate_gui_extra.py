"""CI 门腿 gui extra 对齐守卫。

背景（be07258 CI 红实证）：mypy 基线门只跑 ubuntu-3.12 腿，pywebview 在
gui extra；若 CI 安装行漏装 gui，``webview`` 经 ignore_missing_imports
落 Any，``subtrans.webview_gui.main``（strict 名单内）三处靶向
``type: ignore[arg-type]``（pywebview ``Event.__iadd__`` 实收
DOMEventHandler）被判 unused-ignore，基线恒空硬门即红。
单变量复现：本地卸 pywebview 复现同 3 条红，装回即绿（mypy 版本无关，
2.3.1/2.4.1 双绿）。守卫双断言：pywebview 确在 gui extra（前提锁死，
防守卫因 extra 迁移而空转）＋ CI 安装行 extras 覆盖 gui。
"""
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
CI_YML = REPO / ".github" / "workflows" / "ci.yml"
PYPROJECT = REPO / "pyproject.toml"


def _ci_install_extras() -> set[str]:
    """从 ci.yml 安装行解析 ``pip install -e ".[...]"`` 的 extras 集合。"""
    text = CI_YML.read_text(encoding="utf-8")
    hits = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("run:") and "pip install -e" in stripped:
            start = stripped.find(".[")
            end = stripped.find("]", start)
            if start != -1 and end != -1:
                hits.append(stripped[start + 2 : end])
    if not hits:
        pytest.fail("ci.yml 未找到 pip install -e 安装行（工作流形态变更，守卫须同步）")
    # 多条安装行时取并集：任一条漏 gui 都会让门腿盲区复发
    extras: set[str] = set()
    for raw in hits:
        extras |= {item.strip() for item in raw.split(",") if item.strip()}
    return extras


def test_pywebview_lives_in_gui_extra() -> None:
    """前提锁死：pywebview 必须仍在 gui extra；迁移 extra 须同步改守卫与 ci.yml。"""
    text = PYPROJECT.read_text(encoding="utf-8")
    in_opt_deps = False
    in_gui_block = False
    found = False
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            in_opt_deps = stripped == "[project.optional-dependencies]"
            in_gui_block = False
            continue
        if not in_opt_deps:
            continue
        if stripped.startswith("gui") and stripped.rstrip().endswith("["):
            in_gui_block = True
            continue
        if in_gui_block:
            if stripped.startswith("]"):
                in_gui_block = False
            elif stripped.startswith('"pywebview'):
                found = True
                break
    assert found, "pywebview 不在 [project.optional-dependencies] 的 gui 块，守卫前提失效"


def test_ci_install_extras_cover_gui() -> None:
    """CI 安装行 extras 须覆盖 gui（门腿 pywebview 盲区回归钉）。"""
    extras = _ci_install_extras()
    assert "gui" in extras, (
        "CI 安装 extras 缺 gui：门腿缺 pywebview 时 webview_gui 靶向 ignore "
        "被判 unused-ignore（be07258 CI 红实证），基线门必红"
    )
