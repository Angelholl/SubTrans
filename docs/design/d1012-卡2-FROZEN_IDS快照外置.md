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

## 执行记录（2026-10-12，OpenCode 执行，commit 56c1520）

**改动文件（恰三件，未越卡）**

1. `tests/test_ui_phase3_redlines.py`：模块 docstring 内 FROZEN_IDS 解冻史块（原 :8-61）全量迁出、指向 JSON；`FROZEN_IDS`/`FROZEN_I18N_KEYS` 由多行内联字符串改为 `json.loads(tests/ui_contract_snapshot.json)` 构造 frozenset（提取正则 `_current_ids()`/`_current_i18n_keys()` 逐字符不动）；钉⑤a/⑤b 断言语义与 docstring 一字不动，仅错误消息追加指引「合法变更须跑 tools/ui_contract_snapshot.py --update 重生成快照 tests/ui_contract_snapshot.json，并人工审 diff + 二级评议」；新增 `import json`。
2. `tools/ui_contract_snapshot.py`（新增，stdlib-only）：与测试逐字符同正则（模块常量 `ID_PATTERN`/`I18N_PATTERN`，与测试侧互注）提取两集合；与现有快照 diff 逐条打印 `+/-`；**仅 `--update` 写盘**（数组排序序列化，`_meta` 由人工维护不代写）；无漂移打印 `no drift`（exit 0），有漂移未带 `--update` 打清单 exit 1，快照缺失且未带 `--update` 报错 exit 2。
3. `tests/ui_contract_snapshot.json`（生成物）：`ids` 223 / `i18n_keys` 187 排序序列化（生成前经引导脚本「当前内联集合 == index.html 提取结果」双源互证相等后落盘，集合零增减）；`_meta.frozen_at=2026-10-12`；`_meta.history` 16 条 = 原文件头解冻史 14 笔全量迁入（初始 190/192 → 2.7.3 217，逐笔含决策号）+ 补记仓库他处有据而原 docstring 漏记的 2 笔（2.7.4 件C 217→218，D2026-1007-02，配记 index.html:676-677；2.8.0 批1 218→223，D2026-1007-03，配记 index.html:1142 / test_gui_js_static.py 计数钉 223）+ 本卡外置记档 1 笔。

（一次性引导/红验证脚本置于系统 Temp 目录，未入仓库；index.html/app.js/style.css 零改动。）

**自测结果**

- 先红：向 index.html 临时注入 `<div id="zzzCard2FakeId">`（卡片允许的红构造；验毕 `git checkout` 还原并核字节已变回）→ `test_r3_id_fullset_frozen` 必红，消息含漂移清单「新增=['zzzCard2FakeId'] 删除=[]」；再生工具同步打印 `ids 漂移：+ zzzCard2FakeId` 且 exit 1、未写盘。还原后复绿。
- 定向：`pytest tests/test_ui_phase3_redlines.py tests/test_brand_allowlist.py tests/test_gui_js_static.py -q` → 152 passed + 1 failed（唯一红=遗留问题①，非本卡所致）。
- 全量：`pytest -q` → **1 failed, 2396 passed, 4 skipped**；与本卡开工前同命令实测基线（1 failed, 2396 passed, 4 skipped）逐数一致，基线不降。
- 工具：无参运行输出 `no drift`（exit 0）。
- ruff：`ruff check subtransjav tests tools` → All checks passed。
- 品牌钉：本卡三产出物 grep 旧品牌词零命中；提交入库（tracked）后品牌钉命中集合仍恰为既有 4 份卡文档，未新增。

**遗留问题**

1. 【卡外既有红，待主审裁决】`tests/test_brand_allowlist.py` 在 HEAD（fd87e1d）即红：4 份已 tracked 任务卡文档各含 1 处旧品牌词（均为其验收命令的 `cd /d <仓库根路径>` 行）未入 allowlist——`docs/design/d1012-卡2-…`（本卡）/`卡3-switchTab六钩子收编`/`卡4-active指示token归一`/`卡5-撞号消歧`；卡1 已按「验收命令含项目根路径」先例入册。修复需改 `tests/test_brand_allowlist.py`（本卡纪律①点名清单之外，故未动）；本卡未恶化（命中集合改动前后完全一致）。建议：按卡1 先例一次性补 4 条 allowlist 条目+理由，另卡授权执行。附注：本卡绿判据「品牌钉全绿 / 全量基线 2397+4」隐含该红已处置，与仓库事实（HEAD 上即红，实为 2396+4+1）冲突，口径以主审裁决为准。
2. `pyproject.toml` per-file-ignores 仍留 `tests/test_ui_phase3_redlines.py = ["SIM905"]`（原为内联字符串 `.split()` 豁免，本卡后已无该形态）；纪律①禁改该文件故未清理——无害冗余豁免，建议随下一次触碰 pyproject 的批次顺手移除。
3. 契约提取正则现为两处字面量（测试侧 `_current_ids()`/`_current_i18n_keys()` 与工具侧 `ID_PATTERN`/`I18N_PATTERN`），按卡片「逐字符一致」各持一份并互注；一致性靠人工 + 本工具 no drift 核验，未另立机器钉（本卡不新增钉）。
