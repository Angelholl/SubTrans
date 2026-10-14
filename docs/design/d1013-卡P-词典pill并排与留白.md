# d1013-卡P · 词典 pill 并排+模块留白压缩（真机反馈）

- **回链**：D2026-1013-01 追记；owner 2026-10-14 指示：①「日语词典完整版 (sudachi full)」pill 并入首行 pill 排，放不下则删文字（例如删「词典」两字，且不限于）；②「词典管理（日/中/英）」模块竖向留白过多需压缩（下载源/仅官方/仅镜像/重新下载行区域）。
- **改动文件（实况定，预期 2-3 个）**：
  1. `subtransjav/webview_gui/assets/app.js`（MSG dict_sudachi_full_label 改值+pill 生成处如需）
  2. `subtransjav/webview_gui/assets/style.css`（模块间距/留白）
  3. `tests/`（若既有钉锁值则同步；无则零改）

## 改法（意图+约束，实现细节执行者实况裁量）

1. **pill 并排**：词典 kind pills（日语/中文/英语+完整版第二行）改单行排布。手段裁量：a) `dict_sudachi_full_label` 改值删「词典」两字（如「日语完整版 (sudachi full)」，B-06 改值不改键先例；**先查该值有无测试钉锁值**）+b) pills 容器 flex-wrap 保留（放不下自然换行，目标=删字后能并排）；若主区宽度下删字仍放不下，允许进一步缩短（如「完整版 (sudachi full)」），**语义底线=保留「完整版」与来源标注**（与 core 版二选一的区分信息不可丢）。
2. **留白压缩**：词典管理模块（kind pills 与下载源行/重新下载钮之间）竖向间距压缩——检查该模块 margin/padding 字面与 token 用法，压到紧凑但仍可读（改动走 token，零 px 字面 gap——gap 钉只认 var(--space-hair)/--space-1..6；间距压缩用更小 token 档替换大档，不新造字面）。
3. **回归**：改后词典管理模块功能零变（pill 点击切换 kind、下载源选择、重新下载钮）。

## 先红后绿

本卡以视觉/文案为主，无新钉硬要求；若 dict_sudachi_full_label 有既有值锁钉则先跑其红证。执行记录如实记录验证过程（grep 钉→定向→全量）。

## 验收标准

以下命令均在项目根目录执行：

1. `ruff check subtransjav tests` → All checks passed
2. `python -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py tests/test_strings_and_shortcut.py -q --basetemp=.pytest_card` → 全绿
3. `python -m pytest tests/ -q --basetemp=.pytest_card` → 全量（假失败如实记录）
4. `python -m subtransjav.refine.cli --help` → 退出码 0
5. GUI 由主审另跑。

## 约束

- 只改上列文件+本卡执行记录；FROZEN_IDS/data-i18n 键集零增减（改值不改键）；词库页功能零变。
- commit：`refactor(gui): 词典完整版 pill 并排删字+词典管理模块留白压缩`，verify:+Refs: D2026-1013-01；只 commit 不 push；逐文件点名 add（含本卡）。
- 自测视为未验证。

## 执行记录

### 2026-10-14 执行记录

**改动文件（仅卡片点名的 2 个 + 本卡；tests 零改）**：

1. `subtransjav/webview_gui/assets/app.js`（:745）
   - `MSG.dict_sudachi_full_label` 改值：「日语词典·完整版（sudachi full）」→「日语完整版（sudachi full）」（删「词典」两字及间隔号；**改值不改键**；语义底线保留：「完整版」+ 来源标注（sudachi full），与 core 版二选一的区分信息未丢）
   - pill 生成处零改：DICT_KINDS（:8335）仍引用 `MSG.dict_sudachi_full_label`，chip 文本走 `item.label`；`.dict-kind-row` 容器 `flex-wrap: wrap` 保留（放不下自然换行，卡面允许态）
2. `subtransjav/webview_gui/assets/style.css`（词典管理模块竖向留白压缩，token 档替换，零新增字面）
   - `#dictRows .dict-detail` gap：`var(--space-2)` → `var(--space-1)`（8px→4px；详情区纵向节奏压缩，即 kind pills 与下载源行/重新下载钮之间的竖向留白主体）
   - `.dict-action-row` margin-top：`4px` → `var(--space-1)`（等值纯 token 化，卡C 同款收编；下载源/仅官方/仅镜像/重新下载行区域间距走 token）
3. `tests/`：**零改**（先查钉：`grep dict_sudachi_full_label` 于 tests/ 零命中、`grep 日语词典|完整版` 于 tests/ 零命中 → 无既有值锁钉，卡面「先红后绿」节无需红证；gap 趋势钉允许集含 `var(--space-1)`，改后绿）

**自测结果**（以下命令均在项目根目录执行）：

1. `ruff check subtransjav tests` → **All checks passed!** ✓
2. `python -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py tests/test_strings_and_shortcut.py -q --basetemp=.pytest_card` → **230 passed** ✓（含 gap 趋势钉 `test_gap_scale_allowlist` 绿；词典三钉 `test_dict_source_buttons_pinned` / `test_dict_stop_button_pinned` / `test_dict_load_failure_not_swallowed_pinned` 单独复跑 3 passed）
3. `python -m pytest tests/ -q --basetemp=.pytest_card` → **2087 passed, 46 failed, 18 skipped**；46 failed **全部**为 `ModuleNotFoundError: No module named 'pysubs2'`（`subtransjav/refine/subtitle_convert.py:25` 导入失败——本机 Python 环境缺依赖的假失败，与卡A2 执行记录同口径；本次 diff 零 Python 文件触改，与失败无因果）
4. `python -m subtransjav.refine.cli --help` → **退出码 0** ✓
5. （附加）`node --check subtransjav/webview_gui/assets/app.js` → 语法 OK ✓
6. GUI 黑盒（pill 单行并排实测）由主审另跑；删字后四 pill 估算总宽 ~540px，主区宽度不足时 flex-wrap 自然换行（卡面允许态）

**遗留问题**：

- `#dictRows` 内联 `style="display:flex; flex-direction:column; gap:8px;"`（index.html:432）是 pills↔详情区间剩余竖向间距来源之一；index.html 不在本卡文件范围（卡A2 先例：index.html 内联样式回收须单列卡片），如需进一步压缩建议另立卡片按卡A2 模式（删内联 gap 键 + style.css 落 `#dictRows` 规则），本卡未越界处理。
- 无其他遗留。
