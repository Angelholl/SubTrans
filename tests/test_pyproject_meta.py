"""pyproject 元数据钉（D2026-1001 批2 D3 词典去捆绑防复发）。

D3 推翻 D2026-0930-01 ⑧ + D2026-0930-03 ② 双决议：sudachidict_core
（system.dic ~208MB）不再随 pip 主依赖/EXE 安装器分发，改 ja-dict
可选 extra（pip 用户按需）+ GUI 引擎页下载（EXE 用户）。本钉防
"捆绑口径"复活（双决议回潮）。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_text() -> str:
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_sudachidict_core_not_in_main_dependencies():
    """sudachidict_core 不得出现在 [project] dependencies（仅允许 ja-dict extra）。"""
    text = _pyproject_text()
    m = re.search(r"^dependencies\s*=\s*\[(.*?)^\]", text, re.S | re.M)
    assert m, "pyproject.toml 缺少 [project] dependencies"
    assert "sudachidict_core" not in m.group(1), (
        "sudachidict_core 回流主依赖（D3 去捆绑口径被破坏）；"
        "仅允许 ja-dict extra 或用户经引擎页下载"
    )


def test_ja_dict_extra_carries_sudachidict():
    """ja-dict extra 在位且承载 sudachidict_core（pip 用户按需安装）。"""
    text = _pyproject_text()
    m = re.search(r"^ja-dict\s*=\s*\[(.*?)^\]", text, re.S | re.M)
    assert m, "pyproject.toml 缺少 ja-dict extra"
    assert "sudachidict_core" in m.group(1), "ja-dict extra 未承载 sudachidict_core"
