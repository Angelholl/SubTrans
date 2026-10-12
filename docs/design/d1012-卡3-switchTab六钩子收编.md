# 单件卡：switchTab 六钩子收编（内联 if 链 → 声明式注册表）

> 决策依据：D2026-1012-01 阶段 1 地基批（地基批三件套之二，视觉零变化、行为零变化）。
> 执行者：OpenCode。只 commit 不 push；超卡即停待裁决。

## 根因（为什么要改）

`subtransjav/webview_gui/assets/app.js:4606` switchTab 体内散落 **6 个切页钩子**，均为"if (tabId===X && typeof window.__yHook==='function') { try{…}catch{} }"同构内联块：
①`__refineTplTabHook`(tab-glossary) ②`TmSearch.ensure`(tab-glossary) ③`__asrTabHook`(tab-asrdict) ④`__warmupTabHook`(tab-guide) ⑤`__fullchainStatusHook`(tab-guide) ⑥`__guideStalenessHook`(tab-guide)。
新增钩子=再抄一段同构代码，函数体线性膨胀且钩子清单无单一视图。

## 改动文件（一卡两文件）

1. `subtransjav/webview_gui/assets/app.js`（只动 switchTab 函数体；六个钩子的注册方零改动）
2. `tests/test_gui_js_static.py`（switchTab 静态钉随签名微调；断言语义不放宽）

## 改法

1. **注册表**：switchTab 前新增 `const TAB_HOOKS = { 'tab-glossary': [hook函数…], 'tab-asrdict': […], 'tab-guide': […] }`；每项为保留原 try/catch 吞错语义的具名包装（注释保留各钩子的决策出处行，如 D2026-0930-07/D2026-1008-02/D2026-1010-01）。
2. **派发循环**：`const hooks = TAB_HOOKS[tabId]; if (hooks) for (const h of hooks) h();`——替换六段内联 if。副作用顺序与现状逐字对齐（①②→③→④⑤⑥ 即注册数组顺序）。
3. **静态钉适配**：`test_gui_js_static.py` switchTab 钉（:243-252）现断言函数体内含 `querySelectorAll('.side-tab-btn')`/`querySelectorAll('.tab-page')`/`classList.toggle`/`dataset.tab`——这四条断言的是选中态切换段，注册表化后**应原样存活**；新增一条钉：switchTab 函数体内 `TAB_HOOKS` 派发循环在位且六个钩子名在 TAB_HOOKS 字面量中各恰好出现一次（防收编回归为散落 if）。
4. 行为零变化：钩子守卫（typeof 检查/对象存在性）、吞错注释、触发时机全部原样。

## 先红后绿

- 红：临时删除 TAB_HOOKS 中任一钩子（或把某钩子改回内联 if 而注册表少一项），新增静态钉必红；还原后绿。
- 绿：定向 `tests/test_gui_js_static.py`+`tests/test_ui_phase3_redlines.py` 全绿 + 全量基线不降（当前 2397+4）。

## 验收命令

```
cd /d D:\SubTransJAV
.venv\Scripts\python -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q --basetemp=.pytest_card
.venv\Scripts\python -m pytest -q --basetemp=.pytest_card
.venv\Scripts\python -m ruff check subtransjav tests
```

## 约束

- 只动上列两文件；index.html/style.css 零改动；
- 不改钩子本体（__refineTplTabHook 等注册方实现零接触）；
- 不新增全局符号（TAB_HOOKS 限于 switchTab 所在作用域既有形态）；
- 执行记录追加本卡末尾（改动/自测/遗留）。

## 执行记录（2026-10-12，OpenCode 执行，commit 922ce65）

**改动文件（恰两件，未越卡）**

1. `subtransjav/webview_gui/assets/app.js`（只动 switchTab 区块，app.js:4606-4681）
   - switchTab 前新增同作用域顶层 `const TAB_HOOKS`（app.js:4611-4665，与邻既有 `const TmSearch = {…}` 等同形态；脚本/IIFE 作用域内、未挂 window，零新增全局符号），三分组：`'tab-glossary'`〔①`__refineTplTabHook` ②`TmSearch.ensure`〕/`'tab-asrdict'`〔③`__asrTabHook`〕/`'tab-guide'`〔④`__warmupTabHook` ⑤`__fullchainStatusHook` ⑥`__guideStalenessHook`〕——分组序与组内数组序=原内联执行序 ①②→③→④⑤⑥；
   - 每项为箭头包装，保留原 typeof 守卫 + try/catch 吞错注释（三句注释逐字原样：`/* 初始化失败不阻断切页 */`、`/* 触发失败不阻断切页 */`、`/* 失败不阻断切页 */`），六条决策出处注释原样迁入（D2026-0930-07-追加1 必要⑧ / 2.6.4 批1 / 2.7.1 D2026-1005-01 / D2026-1008-02 批3 / D2026-1009-02 批2 / D2026-1010-01 三轮）；
   - switchTab 体内六段内联 if 替换为卡片指定派发式 `const hooks = TAB_HOOKS[tabId]; if (hooks) for (const h of hooks) h();`（app.js:4678-4679）；选中态切换段（`.side-tab-btn`/`.tab-page`/`classList.toggle`/`dataset.tab`/`aria-selected`）逐字未动，:243-252 四条断言原样存活；
   - 钩子本体（`window.__xxxTabHook` 等注册方实现）零接触；index.html/style.css 零改动。
2. `tests/test_gui_js_static.py`
   - 新增卡片第 3 条新钉 `test_switch_tab_hooks_registry_dispatch_pinned`（:297-315，常量 `_TAB_HOOK_NAMES` :292-294）：switchTab 体内派发循环在位（`const hooks = TAB_HOOKS[tabId]` + `if (hooks) for (const h of hooks) h();`）+ 禁回退 `if (tabId ===` 散落 if + 六钩子名在 TAB_HOOKS 字面量中各恰出现一次 + 注册序与原执行序一致；
   - 新增提取辅助 `_tab_hooks_literal()`（:50-65，花括号配平，口径同 `_extract_function`）、`_tab_hooks_group(tab_id)`（:67-83，方括号配平；分组键缺失即断言失败）；
   - 五处 switchTab 钩子钉随「钩子移出函数体」改指（卡片括注授权「switchTab 静态钉随签名微调；断言语义不放宽」）：原 :753（tab-glossary/__refineTplTabHook）→:816、:1800（TmSearch.ensure）→:1862-1865、:3336-3337（'tab-guide'/__warmupTabHook）→:3401-3402、:3757（__fullchainStatusHook）→:3823-3824、:3854（__guideStalenessHook）→:3921-3922——每处改为「switchTab 体内 `TAB_HOOKS[tabId]` 派发在位」+「`_tab_hooks_group(...)` 对应分组含该钩子」双断言（均补了原缺的派发断言，错误消息逐字保留，非放宽）。

**卡片内口径裁量（两处，如实记档，未越卡）**

- 「六个钩子名各恰好出现一次」与 window 钩子原式 `typeof window.X` + `window.X()`（同名 2 次提及）在字面计数上互斥：落地取局部别名 `const hook = window.__xxxTabHook; if (typeof hook === 'function') { try { hook(); } … }`——typeof 守卫、吞错注释、触发时机语义原样，属性求值由两次收敛为一次（同步执行窗口内与原式等价）；`TmSearch.ensure` 保持原式（该名恰 1 次提及，且 `typeof TmSearch === 'object'` 守卫逐字未动）。
- 注册表按卡片「switchTab 前新增」置于函数体外、同作用域顶层，钩子名因此移出 switchTab 函数体，除 :243-252 外另五处 switchTab 钩子钉必然转红，须同步改指——按卡片「switchTab 静态钉随签名微调」执行；非 switchTab 钉（如 :1674 `__asrTabHook in src`、:3338 `window.__warmupTabHook = ` in src）零改动。

**自测结果**

- 先红：临时删除 TAB_HOOKS 中 `__guideStalenessHook` 整项（卡片允许的红构造）→ `2 failed`（新钉 `test_switch_tab_hooks_registry_dispatch_pinned` + 既有钉 `test_guide_staleness_reread_and_items_modal_pins`）；改前 SHA256=6CE6DF926E551AA512C9E0BCB46E05A41D39C5FA7F0730535E8C9C55311B1D0E，还原后复算逐字一致（字节级复原）→ 复绿。
- 定向：`pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q --basetemp=.pytest_card` → **153 passed**（卡前同命令基线 152，+1=本卡新增钉）。
- 全量：`pytest -q --basetemp=.pytest_card` → **2398 passed, 4 skipped**；开工前同命令实测基线 **2397 passed, 4 skipped**，+1=本卡新增钉，基线不降（卡2 遗留①品牌 allowlist 红已由 3c1290a 处置，本轮无红）。
- ruff：`ruff check subtransjav tests` → All checks passed。
- JS 语法：`node --check app.js`（`test_app_js_syntax_node_check`）随定向与全量绿。
- 提交：922ce65（代码+钉，逐文件点名 `git add`，只 commit 未 push）。

**遗留问题**

1. D2026-1012-01① 登记的「卡3 状态行 tab-engine 钩子切提示态」候选，现只差在 `TAB_HOOKS` 增加一个 `'tab-engine'` 分组——属卡4/后续批范围，本卡不越卡。
2. `TAB_HOOKS` 与 switchTab 同处 app.js 顶层作用域：阶段 3 app.js 拆分若迁移 switchTab，注册表须随迁（拆分方案文档不在本卡点名清单，未动）。
3. 本卡按卡片只加静态钉，未新增运行时冒烟；六钩子实际触发时机仍由既有注册方实现与阶段 4 黑盒验收覆盖。
