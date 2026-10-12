"""UI 契约快照再生工具（3.1 阶段 1 地基批卡2，D2026-1012-01）。

从 ``subtransjav/webview_gui/assets/index.html`` 提取 id 全集与 data-i18n 键
全集（正则与 ``tests/test_ui_phase3_redlines.py`` 的 ``_current_ids()`` /
``_current_i18n_keys()`` 逐字符一致），与 ``tests/ui_contract_snapshot.json``
现有快照 diff 并逐条打印新增/删除；**仅带 ``--update`` 才写盘**。stdlib-only。

合法契约变更流程：跑本工具 ``--update`` 再生快照 → 人工审 diff → 二级评议
（R1/R3 契约恒空口径与解冻史记在快照 ``_meta``，本工具不代写 history）。

无漂移打印 ``no drift``（exit 0）；有漂移未带 ``--update`` 打印清单（exit 1）；
快照文件缺失且未带 ``--update`` 报错（exit 2）。
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HTML_PATH = ROOT / "subtransjav" / "webview_gui" / "assets" / "index.html"
SNAPSHOT_PATH = ROOT / "tests" / "ui_contract_snapshot.json"

# 与 tests/test_ui_phase3_redlines.py::_current_ids/_current_i18n_keys 逐字符一致
# （契约提取真源在测试侧，改任一侧须同步另一侧并跑本工具核 no drift）。
ID_PATTERN = r'(?<![\w-])id="([^"]+)"'
I18N_PATTERN = r'data-i18n(?:-title|-placeholder)?="([^"]+)"'

_EMPTY_SNAPSHOT = {"ids": [], "i18n_keys": [], "_meta": {"frozen_at": "", "history": []}}


def extract(html: str, pattern: str) -> set[str]:
    """按契约正则提取全集（与测试同正则，去重成集合）。"""
    return set(re.findall(pattern, html))


def report_drift(name: str, current: set[str], frozen: set[str]) -> bool:
    """打印单集合漂移清单（新增/删除逐条）；有漂移返回 True。"""
    added = sorted(current - frozen)
    removed = sorted(frozen - current)
    if not added and not removed:
        return False
    print(f"{name} 漂移：")
    for item in added:
        print(f"  + {item}")
    for item in removed:
        print(f"  - {item}")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="UI 契约快照（ids / i18n_keys）diff 与再生")
    parser.add_argument(
        "--update", action="store_true",
        help="把当前 index.html 提取结果写回 tests/ui_contract_snapshot.json（不带则只 diff 不写盘）",
    )
    args = parser.parse_args(argv)

    if SNAPSHOT_PATH.is_file():
        snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    elif args.update:
        snapshot = json.loads(json.dumps(_EMPTY_SNAPSHOT))  # 深拷贝，避免污染模块常量
        print(f"快照缺失，--update 将新建 {SNAPSHOT_PATH.relative_to(ROOT)}（_meta 须人工补全解冻史）")
    else:
        print(f"快照缺失：{SNAPSHOT_PATH.relative_to(ROOT)}——先人工建档或跑 --update")
        return 2

    html = HTML_PATH.read_text(encoding="utf-8")
    drifted = report_drift("ids", extract(html, ID_PATTERN), set(snapshot["ids"]))
    drifted = report_drift("i18n_keys", extract(html, I18N_PATTERN), set(snapshot["i18n_keys"])) or drifted

    if not drifted:
        print("no drift")
        return 0
    if not args.update:
        print("（未带 --update，不写盘；合法变更须人工审 diff + 二级评议后再生）")
        return 1

    snapshot["ids"] = sorted(extract(html, ID_PATTERN))
    snapshot["i18n_keys"] = sorted(extract(html, I18N_PATTERN))
    SNAPSHOT_PATH.write_text(
        json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
    )
    print(f"已写回 {SNAPSHOT_PATH.relative_to(ROOT)}（数组排序序列化；_meta 由人工维护未改动）")
    return 0


if __name__ == "__main__":
    sys.exit(main())
