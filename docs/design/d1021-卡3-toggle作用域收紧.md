# 单件卡 d1021-卡3：toggle 作用域收紧——.gl-sel 行选择器回归原生 checkbox 形态

## 背景与根因

B-07（fdcc46b，2026-10-12）把 checkbox 升为全局 toggle 视觉语言（style.css:1105-1144，纯 CSS token 化，两钉 test_gui_js_static.py:4686/4729）。但词库表行选择复选框 `.gl-sel`（JS 生成，app-refine-glossary.js:31）与设置开关共用同一形态——选择语义≠设置语义，表格行视觉失真。收口裁决（主审，D2026-1021-02）：**作用域收紧**——`.gl-sel` 回归原生 checkbox 形态，设置类 toggle 不动。

## 改动文件（2 个，禁超卡）

1. `subtransjav/webview_gui/assets/style.css`：在既有 `.gl-sel` 规则（:1746）处扩写覆盖块：`input[type="checkbox"].gl-sel { appearance: auto; width: 14px; height: 14px; cursor: pointer; }`（可与 :1746 合并为一块）。禁字面色值、禁 rgba、禁新圆角档；基础 toggle 块（1105-1144）零改动。
2. `tests/test_gui_js_static.py`：B-07 两钉之后追加第三钉 `test_b07_glsel_native_override_pinned`：断言 `.gl-sel` 覆盖块存在且含 `appearance: auto` 与 `14px`；断言基础 toggle 块仍含 `appearance: none` 与 `var(--radius-pill)`（即设置类形态未回退）；断言覆盖块无字面色值。

## 先红后绿

先加钉（红）→ 加 CSS（绿）。

## 验收命令（以下命令均在项目根目录执行）

- `ruff check subtransjav tests`
- `pytest tests/test_gui_js_static.py -q`
- `pytest -q`（基线只增不减，现行基线 2518+4，本卡预期 2519+4）

## 约束

- 只改上述 2 文件；零新 i18n 键、零新 id；零字面色值/新圆角档（B-07 零字面量钉口径）。
- GUI 黑盒由主审执行（DOM 断言：`.gl-sel` computed `appearance`≠none、设置类 checkbox 仍为 toggle 形态）。
- 执行者只 commit 不 push；卡外问题即停待裁决。
- 执行完毕在本卡末尾追加执行记录（改动文件/自测结果/遗留问题）。

## 执行记录（2026-10-21，执行者：executor）

### 改动文件（2，未超卡）

1. `subtransjav/webview_gui/assets/style.css`（1 行改写）：既有 `.gl-sel` 规则（:1746）扩写为覆盖块
   `input[type="checkbox"].gl-sel { appearance: auto; width: 14px; height: 14px; cursor: pointer; }`
   （与 :1746 合并为同一块，单行形态与相邻 :1745 词库行内输入规则同风格）。零字面色值、零 rgba、
   零新圆角档；基础 toggle 块（1105-1144）零改动。
2. `tests/test_gui_js_static.py`（B-07 两钉之后追加第三钉 + 常量 `_B07_GLSSEL_OVERRIDE`）：
   `test_b07_glsel_native_override_pinned` —— 断言覆盖块存在且含 `appearance: auto` 与 `14px`
   （并锁定既有 `cursor: pointer` 不丢）、基础 toggle 块仍含 `appearance: none` 与
   `var(--radius-pill)`（设置类形态未回退）、覆盖块无字面色值。

### 先红后绿

- 先加钉跑红：`AssertionError: .gl-sel 覆盖块必须 appearance:auto`（`assert 'appearance: auto' in ' cursor: pointer; '`，tests/test_gui_js_static.py:4771）。
- 加 CSS 后转绿。

### 自测结果

- `ruff check subtransjav tests` = All checks passed
- `pytest tests/test_gui_js_static.py -q` = 208 passed（含本卡新钉）
- `pytest -q` 全量 = 2519 passed / 4 skipped（基线 2518+4 → 2519+4，+1＝本卡新钉，只增不减）
- 零新 i18n 键、零新 id；style.css 无哈希钉受影响（全量绿即证）

### 遗留问题

1. GUI 黑盒未由执行者执行（卡面归主审）——DOM 断言待主审：`.gl-sel` computed `appearance`≠none、
   设置类 checkbox 仍为 toggle 形态。冒烟与安全深扫比基线亦未由执行者执行（卡面验收命令未含）。
2. 覆盖块生效依赖选择器特异性（`input[type="checkbox"].gl-sel` 0,1,1 > `input[type="checkbox"]` 0,1,0），
   与规则书写先后无关；若后续 JS 生成模板（app-refine-glossary.js:31）去掉 `gl-sel` 类，本钉与覆盖块须同步换代——本卡未改 JS。
3. 暗色主题下 `.gl-sel` 回归原生形态后，勾选框颜色由 UA 默认渲染决定（B-07 已删 `accent-color`，
   `style.dark.css` 零改动）。若主审黑盒发现暗色下对比度不足，需另行裁决——本卡禁字面色值，执行者未自行加 token。
