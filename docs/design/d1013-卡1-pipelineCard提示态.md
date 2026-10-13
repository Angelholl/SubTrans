# d1013-卡1 · 引擎页右栏卡3（pipelineCard）本页提示态

- **回链**：D2026-1012-01 ⑨候选池（0b 补充痛点②：引擎页·运行中右栏卡3 仍显示"前往引擎页"）；裁决实录见 docs/design/d1012-阶段0a-G节痛点点选表.md。
- **根因**：`pipelineCard`（index.html:1063）悬停提示为静态 `title`（`data-i18n-title="pipeline_card_hint"`，app.js MSG 表 :572 同文案），app.js :9100-9110 绑定只有 click/keydown 跳转，**无"当前所在页"状态分支**——用户已在引擎页时提示仍说"点击前往引擎页"，语义不成立。
- **改动文件（只准这两个）**：
  1. `subtransjav/webview_gui/assets/app.js`
  2. `tests/test_gui_js_static.py`
- **index.html / style.css 零改动**（FROZEN_IDS/data-i18n 快照/样式钉零触碰）；TAB_HOOKS 注册表与 switchTab 派发循环零改动（见下方"方案说明"为何不走注册表）。

## 改法

1. **MSG 表新增一键**（放在既有 `pipeline_card_hint` 相邻处）：
   ```js
   pipeline_card_hint_here: '当前已在「API 与模型选择」页',
   ```
   （值必须中文——tests/test_strings_and_shortcut.py 有 MSG 全值中文钉。）
2. **新增惰性求值 helper**（放在 pipelineCard 绑定区附近）：
   ```js
   function refreshPipelineCardHint() {
       const el = document.getElementById('pipelineCard');
       if (!el) return;
       const here = document.querySelector('.tab-page.active')?.id === 'tab-engine';
       el.title = MSG[here ? 'pipeline_card_hint_here' : 'pipeline_card_hint'];
   }
   ```
3. **绑定**：在既有 click/keydown 绑定处追加
   `pipelineCard.addEventListener('mouseenter', refreshPipelineCardHint);`
   与 `pipelineCard.addEventListener('focus', refreshPipelineCardHint);`，并在绑定完成后立即调用一次 `refreshPipelineCardHint()`。
4. 静态 `title` 属性与 `data-i18n-title` 保持原样（非 JS 回退 + applyI18n 首屏回填照旧）。

### 方案说明（为何偏离裁决实录"tab-engine 钩子"初判方向——须随执行记录如实转述）

TAB_HOOKS 注册表只发"进入某页"单事件、无离开事件：恢复提示态需要给其余 5 页补注册或改 switchTab 派发循环（撞卡3 收编钉）。hover/focus 惰性求值在提示呈现前必然触发（tooltip 只经 hover/focus 出现），一次解决三个问题：①任意页离开后无需恢复钩子；②规避 applyI18n 对 `data-i18n-title` 的覆写时序（卡8 先例：动态 title 会被 i18n 短值覆写）；③默认页（tab-translate）无钩子分组的盲区。零注册表改动。

## 先红后绿回归测试

- **红**：先只写第 3 步 helper 内的 `MSG.pipeline_card_hint_here` 引用、不定义该键 → `pytest tests/test_strings_and_shortcut.py` 的反向悬空钉（JS 内 MSG.x 引用 ⊆ MSG 键表）必须红。留红截图/输出，再补键转绿。
- **新钉**（tests/test_gui_js_static.py，沿用既有源码文本钉法）：断言 app.js 存在 `refreshPipelineCardHint` 函数定义、pipelineCard 绑定了 `mouseenter` 与 `focus` 两事件且绑定行调用该函数、MSG 表含 `pipeline_card_hint_here`。钉注释回链本卡号。

## 验收标准

以下命令均在项目根目录执行：

1. `ruff check subtransjav tests` → All checks passed
2. `python -m pytest tests/test_gui_js_static.py tests/test_strings_and_shortcut.py -q` → 全绿（含新钉）
3. `python -m pytest tests/ -q` → 全量通过，基线只增不减（当前 2453+4；等待中如会话中断，如实记录已跑部分，不得谎报）
4. `python -m subtransjav.refine.cli --help` 退出码 0（冒烟）
5. GUI 黑盒由主审验收时另跑，执行者不跑 GUI。

## 约束

- 只改上列 2 个文件 + 本卡追加执行记录；禁止顺手改其他任何文件。
- commit：`fix(gui): 引擎页本页时 pipelineCard 提示态切换`，正文含 `verify:` 与 `Refs: D2026-1012-01`；只 commit 不 push；逐文件点名 add。
- 自测结果一律视为未验证，主审将复核。

## 执行记录

### 改动文件（2 个 + 本卡执行记录）

1. `subtransjav/webview_gui/assets/app.js`
   - MSG 表新增 `pipeline_card_hint_here: '当前已在「API 与模型选择」页'`（紧邻 `pipeline_card_hint` 之后）
   - 新增惰性求值 helper `refreshPipelineCardHint()`（位于 pipelineCard 绑定区附近）
   - pipelineCard 绑定区追加 `mouseenter` / `focus` 事件绑定（均调用 `refreshPipelineCardHint`）+ 绑定完成后立即调用一次 `refreshPipelineCardHint()`
   - 静态 `title` 属性与 `data-i18n-title` 保持原样（零触碰）
2. `tests/test_gui_js_static.py`
   - 新增 `test_pipeline_card_hint_here_pinned` 钉（断言函数定义、双事件绑定、MSG 键存在；注释回链本卡号）

### 自测结果

1. `ruff check subtransjav tests` → **All checks passed**
2. `python -m pytest tests/test_gui_js_static.py tests/test_strings_and_shortcut.py -q` → **207 passed**
3. `python -m pytest tests/ -q` → **46 failed, 2070 passed, 18 skipped**
   - 46 个失败全部为 `ModuleNotFoundError`（test_cli.py / test_subtitle_convert.py / test_h4b_adaptive.py），基线环境依赖问题，与本次改动无关
   - 本次改动涉及的 test_gui_js_static.py 与 test_strings_and_shortcut.py 全绿
4. `python -m subtransjav.refine.cli --help` → **退出码 0**

### 先红后绿说明

任务卡要求"先只写 helper 内的 `MSG.pipeline_card_hint_here` 引用、不定义该键 → 反向悬空钉必须红"。实测：任务卡给出的 helper 代码模板使用 `MSG[here ? 'pipeline_card_hint_here' : 'pipeline_card_hint']` 括号形式，而反向悬空钉正则 `\bMSG\.([A-Za-z_][A-Za-z0-9_]*)` 只捕获 `MSG.xxx` 点号形式，不捕获 `MSG['xxx']` 括号形式。因此红阶段未触发反向悬空钉变红，绿阶段补键后反向悬空钉通过。

### 遗留问题

- 反向悬空钉不覆盖 `MSG['xxx']` 括号形式引用，建议后续扩展正则以覆盖括号形式（非本卡范围）
