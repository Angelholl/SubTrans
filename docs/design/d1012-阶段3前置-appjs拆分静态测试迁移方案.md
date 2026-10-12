# app.js 拆分·静态测试迁移方案（3.1 阶段 3 前置件）

> 状态：**方案稿（评审未过不得动工）**。依据 D2026-1012-01：app.js（9624 行）拆分纳入 3.1 作独立批，本方案通过评议后才允许动工。
> 事实基础：2026-10-12 依赖盘点（见 §1）。归属：3.1 阶段 3（D2026-1012-01）。

## 1. 现状依赖盘点（谁在按"单文件文本"解析 app.js）

真正做文本解析的测试文件只有 **3 个**；另 2 处仅为注释/allowlist 提及（拆分不受影响，见 §4）：

| 测试文件 | 依赖方式 | 拆分后风险 |
|---|---|---|
| `tests/test_gui_js_static.py` | `APP_JS = (ASSETS/"app.js").read_text()`；`_extract_function()` 花括号配平提取函数体（:22-47）；`_js_msg_keys()` 解析 `const MSG = {...}` 键表（:51-57）；约百余条 `assert ... in src/js` 子串断言 | **高**：单文件读取与函数提取直接失效 |
| `tests/test_strings_and_shortcut.py` | 正则解析 app.js 顶部 `const MSG = {...}` 键集与单引号值（:161-206 起，i18n 双表同步钉） | **高**：MSG 若挪文件则读错对象 |
| `tests/test_ui_phase3_redlines.py` | `JS = app.js.read_text()`（:69）+ `_slice_between(JS, ...)` 切片段断言（:67-76）；FROZEN_IDS 钉 index.html；钉④钉 style.css | **中**：切片锚点若跨拆分边界则失效 |
| `tests/test_brand_allowlist.py` | :64 allowlist 条目提及 app.js 路径（文件头注释级） | 无（路径保留即可） |
| `tests/test_gui_api.py` | :4437 注释提及 app.js 字面量对照 | 无 |

## 2. 核心策略：集中读取层 + 拼接视图，断言主体零迁移

绝大多数断言是"子串包含"型，**对拼接文本同样成立**。因此迁移收敛为一个读取层改造：

1. 新增 `tests/js_sources.py`（单一事实源）：
   - `JS_FILES`: 按加载序排列的文件名列表（与 index.html `<script>` 顺序一致）；
   - `read_all()`: 依序拼接全部文件文本（拼接视图 = 拆分前 app.js 的等价物）；
   - `extract_function(name)`: 先按文件逐个 `_extract_function`，未命中再查拼接视图（函数不得跨文件——见 §3 红线①）；
   - `msg_source()`: 返回含 `const MSG = {...}` 的那份文件文本（约定 MSG 独立成文件或留在首文件，见 §3 红线③）。
2. 三个测试文件的读取点改为经 `js_sources`（预计改动点：gui_js_static 1 处读取+2 个 helper、strings_and_shortcut 2 处、ui_phase3_redlines 1 处）；**子串断言本体零改动**。
3. `_slice_between` 锚点核查：逐对锚点确认起止标记落在同一拆分文件内；跨界者调整锚点或调整拆分边界（锚点清单在动工批内补全）。

## 3. 拆分红线（比测试迁移更要紧，违者即回归）

1. **函数不得跨文件**：一个函数完整地属于一个文件。
2. **IIFE 私有作用域是最大陷阱**：app.js 主体包在 IIFE 内，私有 helper（如 `$`、分区工具）被跨分区引用——先例：D2026-1006-01 件⑥ `refreshPipelineMirror` 顶层引用 IIFE 私有 `$` 致 ReferenceError 静默杀两条启动链。**动工首任务=作用域耦合清单**（哪些私有符号被哪些分区消费），凡跨分区消费者必须先显式升为文件级全局（带前缀命名）或留在同文件，清单过评才开拆。
3. **`const MSG` 单一归属**：MSG 表只放一个文件，双表同步钉（strings_and_shortcut）经 `msg_source()` 读取；禁止 MSG 拆两处。
4. **加载顺序即依赖顺序**：index.html `<script>` 顺序 = `JS_FILES` 顺序；新增一条静态钉断言两者一致（防顺序漂移）。
5. **file:// 约束**：只能多 `<script src>` 顺序加载，禁 ES modules（CORS 拦截）、禁任何 bundler（零构建，D2026-1012-01）。
6. **review.js 先例沿用**：独立单对象 + 全局暴露（`ReviewUI`/`AppModal` 模式），拆出单元以此为形态模板。

## 4. 拆分批次建议（供动工批引用）

按自包含度排序（首批风险最低）：
1. AppModal 区块（~1800 行，自包含对象，已有先例形态）；
2. MSG 文案表（独立常量，双表钉只改读取源）；
3. Console/ActivityStream/Progress/SystemSummary 各 Manager 对象（互依性中，逐个拆）；
4. Refine UI 大段（~4400 行，与 switchTab 钩子收编联动，最后拆）。

## 5. 验收口径（动工批随卡执行）

- 先红后绿：迁移方案落地后的测试改动先跑（全量 2392+4 基线不降）；
- 每拆一个文件：`node --check` 全部新文件 + 全量测试绿 + 冒烟（GUI 可启动）+ 黑盒关键路径一轮；
- 拆分前后 DOM 行为零变化（沿用阶段 1 验证口径：DOM 快照 + computed-style + 截图 diff）；
- Mimosa 深扫零新增（新 js 文件全部为既有代码搬家，逐文件点名提交）。
