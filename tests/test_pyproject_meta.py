"""pyproject 元数据钉（2.5.0 修复A 重写，D2026-1001-06）。

词典数据政策=**一律下载式**（D3 去捆绑 + 修复A 显式复议采纳）：
- D2026-1001-03 D3 的"ja-dict extra 保留"支柱因新实证失效——sudachidict_core
  20260723.1 wheel requires_dist=null 无 resolver 冲突，且 0.6.x 引擎实证
  无法加载新版 v1 词典（Invalid header 静默失败）；
- 词典数据经 GUI 引擎页 / CLI --dict-download 下载式补齐，任何声明入口
  不得携带词典数据。
本钉防"声明式捆绑口径"复活。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _pyproject_text() -> str:
    return (ROOT / "pyproject.toml").read_text(encoding="utf-8")


def test_no_dict_data_declaration_entry():
    """词典数据一律下载式：pyproject 不得出现任何词典数据声明入口。"""
    text = _pyproject_text()
    assert "sudachidict" not in text, (
        "sudachidict 回流 pyproject（词典数据一律下载式，"
        "D2026-1001-06 修复A）；词典经引擎页/--dict-download 补齐"
    )
    assert "ja-dict" not in text, (
        "ja-dict extra 复活（0.6.x 无法加载 v1 词典，统一下载式口径；"
        "D2026-1001-06 修复A 显式复议采纳）"
    )


def test_sudachipy_pinned_to_0_7():
    """sudachipy 主依赖（引擎包，非词典数据）钉 0.7 下限——0.6.x 加载
    新版 v1 词典 Invalid header 静默失败（20260723 实证）。"""
    text = _pyproject_text()
    m = re.search(r'"sudachipy([^"]*)"', text)
    assert m, "pyproject 缺少 sudachipy 主依赖"
    assert "0.7.0" in m.group(1), (
        "sudachipy 版本下限须 >=0.7.0（0.6.x + v1 词典 = Invalid header）"
    )
