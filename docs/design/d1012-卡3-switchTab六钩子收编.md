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
