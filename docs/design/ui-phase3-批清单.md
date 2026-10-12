# UI 阶段3（2.2.1）逐页套规范·细化批清单

> 依据：D2026-1001-02 立项四条件（roadmap 2.2.1 节）；底账实测 2026-10-01（行号为当日工作区快照）。
> 本文件是二级评议对象；**评议通过前不动任何阶段3 代码**。执行中行号漂移以元素 id/类名为准。

## 一、范围与批拆分（三批三提交）

### 批1 引擎与模型页（样式层精修，零 DOM 节点增删）

| # | 改动 | 位置 | 方式 |
|---|---|---|---|
| 1a | 阶段A/B 卡内联宽度收编：`style="min-width:var(--w-…)"` 移入 CSS 规则（按既有 id 选择器），style 属性移除 | index.html:175-234（A 卡/B 卡对称 8 处内联） | 删 style 属性+style.css 增 `#refineS1Provider{min-width:var(--w-provider)}` 型规则 |
| 1b | 第三卡（237-261）同款内联收编 | index.html:237-261 | 同上 |
| 1c | 接口地址区（264-280）与兜底并发组（283-312）现有 stack 容器**加挂 `form-card` 类**（不加节点），其 .block-title/.group-title 经 CSS 获得卡头样式 | index.html:264/283 | 纯 class 追加+CSS |
| 1d | stage-row/alt-row 间距对齐精修（纯 CSS，不改值域禁区） | style.css:1007-1031 | 纯 CSS |

不做：卡片不加 `.form-card-header` 标题节点（卡内无标题元素，新增=新 DOM+新 i18n 键，双重违反红线）；checkbox→toggle 视觉改造（涉控件结构，出局项挂候选池）。

### 批2 词库与模板页表格套 .gl-table

| # | 改动 | 位置 | 方式 |
|---|---|---|---|
| 2a | `#refineGlossTable` 加挂 `gl-table` 类，删表级/ th 内联 style | index.html:366-371 | class 追加+style 属性移除（CSS 1039-1057 已并集支持，挂类即生效） |
| 2b | `#glLearnedTable` 追加 `gl-table`（保留 gl-collapsible-content 不动） | index.html:403 | 同上；**动前先 grep 测试对 `gl-collapsible-content` 的字面引用** |
| 2c | `glRender`（app.js:1954-1971）行模板内联样式清到类：行边框/单元格 padding 由 .gl-table 规则承载，别名 font-size/color 改 `.gl-alias` 新类（字号值复用现值） | app.js:1954-1971 | JS 模板字符串改类 |
| 2d | `glLearnedLoad`（app.js:2019-2025）行模板同款清理 | app.js:2019-2025 | 同上 |

不做：状态列/状态 tag 新增（涉列结构=DOM 红线）；`.tag` 新类体系（复用既有 .pill 已覆盖，无现状诉求）。`refineGlCount` 悬空引用为既有软失败，本批不修（修=新增 id，违反 R3）。

### 批3 质量页与高级参数页卡片分组

| # | 改动 | 位置 | 方式 |
|---|---|---|---|
| 3a | 三个 `.adv-group` 的 `.group-title` 经 CSS 升级为卡头样式（底色/分隔/内边距，对齐 .form-card-header 视觉）；组1 双标题（500/526）**保留两个节点**：首标题=卡头、次标题=卡内分隔小节样式（纯 CSS 区分，不移除不移位） | style.css 新增规则（index.html:499-611 零改动） | 纯 CSS |
| 3b | 质量页来源组（419-441）现有 stack 容器加挂 `form-card` 类，group-title 420 经 CSS 获卡头样式 | index.html:419 | class 追加+CSS |
| 3c | AI 分析结果两张裸表（app.js:2861-2871/2874-2885）模板加挂 `gl-table` 类、删内联 width/border | app.js:2861-2885 | JS 模板字符串 |

不做：导读详情（444-467）与 AI 分析 section 容器（471-482）**禁触**（closest 锚 .console-section，app.js:967）；dataRootBar（组外）不动。

## 二、三面红线（固化，违者当批回退）

- **R1 DOM 恒定**：不新增/删除/移动任何元素节点与文本节点。允许的改动面仅限：①既有元素 class 属性追加/修改 ②style 属性整体移除 ③style.css/style.dark.css 规则增改 ④app.js 模板字符串内的 class/style 字面量。id 属性零改动；closest 锚点（app.js:553/555/561/967/3135，.file-item/.console-section/.btn-audio-preview）禁触。
- **R2 节奏禁区**：`:root` 的 `--font/--font-sm/--font-xs/--font-mono/--font-sans/--space-1` 定义与 `html`/`body`/控制台/`.form-input` 等既有 font-size/line-height 声明一律不改；新增类不得引入新字号/间距节奏值（只复用既有值）；`--w-*` 宽度 token 允许照用。
- **R3 契约恒空**：index.html id 全集 diff=空（现 165 唯一）；data-i18n 键全集 diff=空（现 186 键，白名单仅 theme_google/carbon/primer 三删除键）；JS MSG 键表不动；测试字面钉不碰（test_gui_js_static.py:281/331 的 `'refineS' + n + 'Provider'`、`for (const n of [1, 3])`，:594 的 `stack gl-collapsible` count==2 等）。

## 三、验收面（每批+收口）

1. **契约闸**：动工前 `%TEMP%\stj_gate\gate.py baseline` 重打基线（现 baseline.json 154 ids 与工作区 165 已漂移，2026-09-30 后未重打）；每批后 `gate.py check` 零拦截（id/i18n 键/JS 引用 diff 恒空）。
2. **静态钉随批**（tests/test_ui_phase3_redlines.py 新文件，只增不改既有）：①阶段A/B 区无残留 `style="min-width` 内联 ②两词库表挂 gl-table ③glRender/glLearnedLoad 行模板无 `style=` 字面量 ④`:root` 节奏禁区变量值逐字钉（防 R2 漂移）。
3. **全量测试**：基线 1593+4 只增；ruff 零告警。
4. **GUI 黑盒**（web-gui-tester）：静态伺服+桥双路；五页亮暗抽查+词库表桥渲染+provider 双向联动回放+引擎页测试/保存按钮 SVG 完好（innerHTML 旧伤回归点）。
5. **四档截图**（1210/1000/1440/1500）：engine/advanced 前后对比；glossary/guide 补建档。存 `%TEMP%\stj_gate\baseline\phase3\`。
6. **提交**：三批三提交（Conventional 中文+verify 行+Refs: D2026-1001-02），提交信息注明"GUI 已验证/未验证"。

## 四、止损线

任一批违反 R1-R3 任一条、或截图/黑盒出现布局破版与对比度回归 → 当批整体回退，砍掉项转普通跟踪项；不为赶批带病合并。批间独立可分别放行。

## 五、已知边界（记录在案，不在本批）

- `refineGlCount` 悬空（app.js:1967/2063 引用 id 不存在，软失败）——修=新增 id 违 R3，挂跟踪项。
- 状态 tag 列、checkbox→toggle、接口地址区独立卡片化深化——候选池。
- 全局字号/行高/间距节奏 token 化——候选池禁区（等 owner 痛点清单）。

## 六、二级评议闭环（2026-10-01，critic 有条件放行→条件全部并入）

评议员裁定：三批方向正确可执行，1 [HIGH_RISK_OBJECTION]（**采纳**）+九项条件（C1-C9）全部并入生效，勘误三处：

- **HRO-1（采纳）**：gate.check 只比对丢失方向（old−new），**新增 id/i18n 键静默放行**，R1/R3 此前无机器闸——补**钉⑤全集钉**：冻结现 165 id+186 i18n 键全集快照逐字断言（tests/test_ui_phase3_redlines.py 内），R1/R3 就此机器化。
- **C1**：style.css 补 `.stack.form-card{align-items:stretch}` 中和规则（.stack 纵列 + .form-card 的 align-items:center 级联会把加挂容器子项改居中收缩）。
- **C2**：style.css:994-1005 两条 label:has 规则加 `.form-card:not(.stack)` 守卫（防兜底并发组 4 个 inline-field label 被强制列排+!important 覆盖既有内联宽度）。
- **C3**：钉①断言域限定 A/B 两卡区间（175-203/206-234）——引擎页其他区域 min-width 内联合法存在。
- **C4/C8**：补 `.gl-table{width:var(--w-full);border-collapse:collapse}` 表级基础规则+#refineGlossTable 首末列宽规则（复用 --w-gl-source/--w-th-action）；批2/批3 挂类以它为前提，否则删内联后表宽收缩。
- **C5**：2c 复选框单元格 text-align:center 以 `.gl-sel-cell` 类承载。
- **C6/C9**：glossary/guide 各补一档（1210）前后对比截图（批2/批3 漂移风险最高页不留目检盲区）。
- **C7**：组1 双标题用 `.adv-group > .group-title:first-child`（卡头）与 `:not(:first-child)`（卡内小节分隔）双选择器区分（:first-child 成立性已核：500/526 同父且 500 为首子）；3b 来源组同受 C1 约束。
- **勘误**：折叠钉=test_gui_js_static.py:605、provider 联动钉=:339/:341（原清单误标 test_strings_and_shortcut.py）；阶段A/B label 的 min-width:var(--w-stage-label)（177/208，无 id）用位置选择器承载；.gl-alias 的 margin-top:1px 系既有内联现值迁移非新增节奏值（R2 显式豁免）；截图回归口径=同视口像素级比对（hash/色差阈值），不采"目视无碍"。
- 评议员核实：baseline 154→165 的 11 id+6 键全部可溯源 D2026-0930-08/-09/D2026-1001 三轮，重打基线合法非掩盖；glLearnedTable 追加类对折叠机制与折叠钉零牵连；#id 收编宽度与 .grow/.compact 等价复刻（.form-select 本无宽度规则）。
