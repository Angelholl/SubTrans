# 单件卡：FROZEN_IDS 快照外置（内联字符串 → JSON 快照文件+再生工具）

> 决策依据：D2026-1012-01 阶段 1 地基批（owner 2026-10-12 追认"3.1 地基批"计划；本卡=地基批三件套之一，视觉零变化）。
> 执行者：OpenCode。只 commit 不 push；超卡即停待裁决。

## 根因（为什么要改）

`tests/test_ui_phase3_redlines.py:124`（FROZEN_IDS，id 全集≈200）与同文件 FROZEN_I18N_KEYS（data-i18n 键全集 192）以**多行内联字符串**形态冻结契约。历史上 2.6.x 系列每批都要手工增删内联字符串（191→200→206→210→213，文件头注释逐条记档），阶段 2 视觉批将有数十次合法契约变更，手工改字符串易错、diff 不可机读、解冻记录与冻结体耦合。

## 改动文件（一卡两文件）

1. `tests/test_ui_phase3_redlines.py`（只动 FROZEN_IDS/FROZEN_I18N_KEYS 定义与相关断言的错误消息；钉⑤a/⑤b 测试语义不变）
2. `tools/ui_contract_snapshot.py`（新增，再生工具）

（生成物 `tests/ui_contract_snapshot.json` 由工具产出后一并提交。）

## 改法

1. **快照外置**：id 全集与 data-i18n 键全集迁入 `tests/ui_contract_snapshot.json`（结构：`{"ids": [...], "i18n_keys": [...], "_meta": {"frozen_at": "2026-10-12", "history": ["2.7.4 件C 新增 batchFixEffectiveLine(D2026-1007-02)", …既有解冻记录全量迁入…]}}`，数组排序序列化保证 diff 稳定）。
2. **测试改造**：钉⑤a/⑤b 从模块常量改为读 JSON；断言语义一字不动（`cur == snapshot 集合`，漂移时报新增/删除清单）；错误消息追加指引"合法变更须跑再生工具并人工审 diff + 二级评议"。
3. **再生工具**：`tools/ui_contract_snapshot.py`——从 `subtransjav/webview_gui/assets/index.html` 用与测试完全相同的正则提取两集合，与现有快照 diff 打印（新增/删除逐条）；`--update` 才写盘。无第三方依赖（stdlib）。
4. **冻结语义不降级**：R1/R3 契约恒空口径、二级评议前置，全部原样保留在错误消息与 JSON `_meta`。

## 先红后绿

- 红：临时向 index.html 注入一个假 id（或临时从 JSON 删一个既有 id），钉⑤a 必红且消息列出漂移清单；还原后绿。
- 绿：定向 `tests/test_ui_phase3_redlines.py` 全绿 + `tests/test_brand_allowlist.py` 全绿（新增 JSON/tools 文件须过品牌 allowlist 时显式增记）+ 全量基线不降（当前 2397+4）。

## 验收命令

```
cd /d D:\SubTransJAV
.venv\Scripts\python -m pytest tests/test_ui_phase3_redlines.py tests/test_brand_allowlist.py tests/test_gui_js_static.py -q --basetemp=.pytest_card
.venv\Scripts\python tools\ui_contract_snapshot.py   （无 --update 应打印 "no drift"）
.venv\Scripts\python -m pytest -q --basetemp=.pytest_card
.venv\Scripts\python -m ruff check subtransjav tests tools
```

## 约束

- 只动上列两文件+生成 JSON；index.html、app.js、style.css 零改动（视觉零变化）；
- 提取正则与既有 `_current_ids()`/`_current_i18n_keys()` 逐字符一致；
- 不改任何其他钉（钉①-④、钉⑤a/⑤b 语义层）；
- 执行记录追加本卡末尾（改动/自测/遗留）。
