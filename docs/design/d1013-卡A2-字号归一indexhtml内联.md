# d1013-卡A2 · 字号归一（index.html 内联 5 处删键移类）

- **回链**：D2026-1013-01；规格=docs/design/d1013-S6复议-排印刻度卷.md §1.2/§1.4（内联 5 处，LC-1 评议增量）+§1.6（LC-4：index.html 必须同扫）。前置=卡A1 已落字号白名单钉（test_font_size_scale_allowlist，index.html 段冻结计数 5）。
- **根因**：index.html 内联 font-size 5 处离刻度（11px×1 / 12px×2 / 12.5px×2），钉1 只扫 style.css 漏内联面；白名单钉 index.html 段以冻结计数 5 承接现状，本卡回收后归零路径已铺。
- **行号口径**：主审 2026-10-13 实扫 main=738d8cc 零漂移。
- **改动文件（只准这两个）**：
  1. `subtransjav/webview_gui/assets/index.html`
  2. `subtransjav/webview_gui/assets/style.css`

## 改法

1. **:517** `<div id="refineTplLoadedPath" class="muted" style="font-size:11px; word-break:break-all;">`：删内联 `font-size:11px; `（word-break 保留）。style.css 新增规则：
   ```css
   #refineTplLoadedPath { font-size: var(--font-xs); }
   ```
   **落点裁量（主审已裁，执行记录注明）**：规格写「删内联键随类走 var(--font-xs)」，但该元素类 `.muted` 实为 `font-size: var(--font-sm)`（style.css:1024），随类落 13px 与规格渲染声明「+1px 放大」（即 12px）不符——改落 id 级规则兑现 12px（件1 §2.2 表⑤ 元信息 12px 口径）。`.muted` 全局类禁止改动。
2. **:519** `<textarea id="refineTemplateText" ... style="width:var(--w-full); font-family:Consolas,monospace; font-size:12px;">`：删内联 `font-size:12px; `；**同元素顺手项（主审裁量并入，执行记录注明）**：`font-family:Consolas,monospace` → `var(--font-mono)`（件1 §3.4 R2「组件禁止自定义 font-family，仅两 token 可引用」预兑现；--font-mono 栈含 Consolas，等宽形不变、族内回退序微变，零布局影响）。style.css 新增：
   ```css
   #refineTemplateText { font-size: var(--font-xs); }
   ```
   `width:var(--w-full)` 合法引用保留。落 id 级规则理由同上（`.form-input` 全局类禁止改动）。
3. **:647** `<div class="fullchain-status-line" ... style="padding:4px 12px; line-height:1.6; font-size:12px; color:var(--muted, #888);">`：仅删内联 `font-size:12px; `（**line-height:1.6 / padding / color 内联键不动**——行高钉判定面=style.css，内联 1.6 为已知留存边界；颜色面归 P0-5 批）。style.css 新建类规则（该类现无任何规则）：
   ```css
   .fullchain-status-line { font-size: var(--font-xs); }
   ```
4. **:1071 / :1080** `<label class="encode-auto-row" style="...font-size:12.5px;...">` 与 `<label class="fullchain-auto-row" style="...font-size:12.5px;...">`：各删内联 `font-size:12.5px; `（**gap:6px / margin-top:6px 等其余内联键不动**——gap 钉判定面=style.css，内联 gap 为已知留存边界）。style.css 新建两类规则：
   ```css
   .encode-auto-row { font-size: var(--font-xs); }
   .fullchain-auto-row { font-size: var(--font-xs); }
   ```
5. **tests 零改动**：白名单钉 index.html 段冻结计数 `_FROZEN_INLINE_FONT_PX = 5→0` 的收紧由**卡B 顺带**（卡B 文件含 tests；本卡改值后现状=0≤5，钉保持绿）。

## 先红后绿回归测试

卡A1 白名单钉已用冻结计数承接现状（当前绿），本卡红相以**注入法双态自证**（四步日志入执行记录）：

1. 开工前：临时在 index.html 任意元素内联加 `font-size:11px;`（与既有 5 处并存，总计 6 > 冻结 5）→ 跑 `test_font_size_scale_allowlist` 断言红；
2. 还原注入；
3. 完成改法 1-4 → 跑钉断言绿（0 ≤ 5）。
四步输出全部粘贴进执行记录。

## 验收标准

以下命令均在项目根目录执行：

1. `ruff check subtransjav tests` → All checks passed
2. `grep -c "font-size: *[0-9.]*px" subtransjav/webview_gui/assets/index.html` → 0
3. `grep -c "font-family: *Consolas" subtransjav/webview_gui/assets/index.html` → 0
4. `python -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q --basetemp=.pytest_card` → 全绿
5. `python -m pytest tests/ -q --basetemp=.pytest_card` → 全量；ModuleNotFoundError 类假失败如实记录（主审 .venv 复核）
6. `python -m subtransjav.refine.cli --help` → 退出码 0
7. GUI 黑盒由主审验收时另跑，执行者不跑 GUI。

## 约束

- 只改上列 2 个文件 + 本卡追加执行记录；禁止顺手改其他任何文件（含 tests）。
- FROZEN_IDS 零涉（只新增样式规则，不增删 id 属性）；data-i18n / FROZEN_I18N / ui_contract_snapshot 零涉；内联其余键（word-break/width/padding/line-height/gap/margin-top/color）零改动。
- commit：`refactor(gui): 字号归一 index.html 内联五处删键移类`，正文含 `verify:` 与 `Refs: D2026-1013-01`；只 commit 不 push；逐文件点名 add。
- 自测结果一律视为未验证，主审将复核。

## 执行记录

（执行者追加）

### 2026-10-13 执行记录

**改动文件（仅卡片点名的 2 个）**：
1. `subtransjav/webview_gui/assets/index.html` — 删内联 font-size 5 处（:517 `11px`、:519 `12px`、:647 `12px`、:1071 `12.5px`、:1080 `12.5px`）；:519 顺手项 `font-family:Consolas,monospace` → `var(--font-mono)`
2. `subtransjav/webview_gui/assets/style.css` — 末尾追加 5 条规则：`#refineTplLoadedPath` / `#refineTemplateText` / `.fullchain-status-line` / `.encode-auto-row` / `.fullchain-auto-row` 均 `font-size: var(--font-xs)`

**落点裁量注明**：
- 件1（:517）：规格写「删内联键随类走 var(--font-xs)」，但 `.muted` 实为 `var(--font-sm)`（13px），随类落与渲染声明「+1px 放大」（12px）不符——按主审裁量落 id 级规则 `#refineTplLoadedPath { font-size: var(--font-xs); }` 兑现 12px。
- 件2（:519）：`.form-input` 全局类禁止改动，落 id 级规则 `#refineTemplateText { font-size: var(--font-xs); }`。

**先红后绿回归测试（四步日志）**：

步骤1（注入法红相）：临时在 `<summary style="cursor:pointer; ...">` 注入 `font-size:11px;`，跑 `test_font_size_scale_allowlist`：
```
FAILED tests/test_gui_js_static.py::test_font_size_scale_allowlist
AssertionError: index.html 内联 font-size 非豁免 px 计数超冻结存量（6>5）：新增内联 px 字号须回终审下调冻结值
assert 6 <= 5
```

步骤2：还原注入（删除注入的 `font-size:11px;`）。

步骤3：完成改法 1-4 → 跑钉断言绿：
```
python -m pytest tests/test_gui_js_static.py::test_font_size_scale_allowlist -q → 1 passed
```

**验收标准结果**：

1. `ruff check subtransjav tests` → **All checks passed!** ✓
2. `grep -c "font-size: *[0-9.]*px" subtransjav/webview_gui/assets/index.html` → **0** ✓
3. `grep -c "font-family: *Consolas" subtransjav/webview_gui/assets/index.html` → **0** ✓
4. `python -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q --basetemp=.pytest_card` → **170 passed** ✓
5. `python -m pytest tests/ -q --basetemp=.pytest_card` → **2073 passed, 46 failed, 18 skipped**；46 failed 全部为 `ModuleNotFoundError: No module named 'pysubs2'`（假失败，主审 .venv 复核）
6. `python -m subtransjav.refine.cli --help` → **退出码 0** ✓
7. GUI 黑盒由主审验收时另跑，执行者不跑。

**遗留问题**：无。白名单钉 index.html 段冻结计数 5→0 的收紧由卡B 顺带（本卡未改 tests）。
