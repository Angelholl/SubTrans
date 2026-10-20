# d1020-AGENTS 瘦身与技能治理·修订设计规格（v2.2，收编 owner 批评＋2026-10-20 终裁六点）

状态：**已拍板**（owner 终裁 2026-10-20；决策号 **D2026-1020-07**——初拟 -06 与既有「3.1 发版条件复核收口」撞号，按 D2026-1020-04/05 撞号顺延先例改号）。本文替换前一会话的问题一/问题二回答，逐条落实批评：完整清单、实测收益、frontend-design 确认方法、版本健康、卸载后验证、先例降级、逐条划界、时序裁决、失败可见性、OpenCode 主模型确认。

## 0. 实测数据汇总（2026-10-20，全部为当日实测非估算）

| 项 | 值 | 来源 |
|---|---|---|
| 全局 AGENTS.md | 8994B | wc -c |
| 硬限 / 软限 | 9216B / 8100B（软限**已突破**，一体命令常态告警） | config-write SKILL.md 一体命令原文 |
| D-05 预检后 | ~9057B（余 159B，不超限） | D-05 预检（memory）+ 本次复核 |
| 四节体量 | 任务委派 4175B／技能使用 1817B／提交与验证 1280B／完成通知 1609B | 分节实测 |
| 加载技能 | 44 条（本会话清单），描述合计 ≈15,551B≈15.2KB/会话常驻 | 逐 SKILL.md 实测 |
| 落盘 SKILL.md | 93 个（含插件多版本缓存），描述合计 37,031B | 遍历实测 |
| 瘦身骨架实测 | 2013B（草案全文见 §4.3） | python 实测 |
| skill 长度约束 | description 常驻（官方要求 keep short）；body 软目标 <500 行，**无字节硬限**（bundled dynamic-workflows 92KB 正常加载） | skill-creator SKILL.md + 实证 |
| 插件启停 | 全局禁 mimosa/watch-positions，启 github/pyright-lsp；工作区禁 pdf/watch-positions、启 mimosa；suppressed 内建=ios/android 模拟器 | 两级 config.json |
| H1 hook | PreToolUse `Edit|Write|MultiEdit` → gate 脚本，**当前 enforce** | config.json + H1-MODE |
| hooks 能力 | 事件恰 7 种；PreToolUse matcher=工具名正则，**`Agent` 可匹配**（别名 Task↔Agent） | zcode-guide diagnosing-hooks 0.3.0 |
| 技能发现顺序 | ①显式 roots→②~/.zcode/skills→③~/.agents/skills→④工作区 .zcode→⑤工作区 .agents→⑥插件；同级 .zcode 先于 .agents；同名全部发现、首个加载、其余被遮蔽 | zcode-configuration-guide 0.3.0 |

## 1. 问题一：技能/插件完整盘点（44 项加载 + 缓存注记）

四分类口径：**必需**=被 AGENTS.md 触发行/hook/验证链引用或治理刚需；**重叠**=与在役工具功能重叠；**无关**=无引用且无本项目用途；**待定**=owner 个人用途或用途不明，不代决。

### 1.1 用户级 ~/.zcode/skills（13）

| 技能 | 描述字节 | 分类 | 依据/处置 |
|---|---|---|---|
| lessons | 320 | 必需 | 4 处强制触发行+H1 hook 配套 |
| config-write | 738 | 必需 | ~/.zcode 编辑强制防线，六文件基线覆盖本体 |
| code-review | 421 | 必需 | 推送前审查触发行 |
| find-skills | 303 | 必需 | 技能缺口触发行 |
| handoff | 174 | 必需 | 会话交接触发行 |
| tdd | 149 | 必需 | 红绿流程触发行 |
| frontend-design | 204 | 必需 | UI 设计规格在役（UI 重塑线） |
| web-design-guidelines | 184 | 重叠 | UI 审查与 web-gui-tester 走查重叠，低频。卸载候选 |
| emil-design-eng | 155 | 待定 | UI 品味指导，无引用；设计期或有用 |
| grill-me | 82 | 无关 | 方案拷问与 decision-critic 职能重叠。卸载候选 |
| grill-with-docs | 137 | 无关 | 同上。卸载候选 |
| triage | 167 | 无关 | issue 分诊，项目无 issue 流。卸载候选 |
| improve-codebase-architecture | 156 | 无关 | 诱导全库重构提议，与"只改卡面点名文件"纪律相抵。卸载候选 |

### 1.2 用户级 ~/.agents/skills（3）

| 技能 | 描述字节 | 分类 | 依据/处置 |
|---|---|---|---|
| frontend-design | 204 | 重叠 | **与 .zcode 副本 sha256 完全相同**；发现顺序 .zcode 先于 .agents → .zcode 胜出加载，本份恒被遮蔽。零风险处置=删本份（胜者保留，行为零变化；官方 diagnosing-skills pitfall 9 同处方） |
| autoglm-browser-agent | 514 | 待定 | 与 browser-use/control-browser+web-gui-tester 重叠，且系第三方来源（.agents 目录非官方市场）→ 有供应链面。owner 裁 |
| setting-adapt | 411 | 待定 | owner 个人设定迁移用途，非本项目。不动 |

### 1.3 内建/插件（29 条 · 11 源=10 插件＋bundled 1；终裁核对更正，原"28 条·14 插件"计数有误）

| 来源 | 技能（描述字节） | 分类 | 处置 |
|---|---|---|---|
| dynamic-workflows（bundled） | 486 | 必需 | CreateWorkflow 前置加载 |
| browser-use 0.5.1 | control-browser 437；web-gui-tester 683 | 必需 | GUI 验证链触发行 |
| documents 0.2.0 | docx 612；docx-viewer 290 | 必需低频 | 产物即触发 |
| presentations 0.2.0 | pptx 711；pptx-viewer 301 | 必需低频 | 同上 |
| spreadsheets 0.2.0 | xlsx 769；xlsx-viewer 301 | 必需低频 | 同上 |
| github 0.1.2 | workflow-run 200；pr 201；release 190 | 必需低频 | CI 查验/发版 |
| | issue 235；repo 265；secret 223 | 待定 | 低频备用 |
| | codespace 188；gist 208；setup 239 | 无关 | 卸载候选（整插件粒度才可禁，见下） |
| | **commit 213** | **重叠+隐性冲突** | 描述诱导"从暂存区直接建提交"，绕开提交五步/验证链——本次盘点抓出的唯一隐性冲突实锤。不能整插件禁（同插件含必需技能），处置=全局 AGENTS.md 骨架加半行「项目提交一律走提交五步，禁走 github:commit 快捷通道」 |
| mimosa 1.0.4 | mimosa-security-scan 193 | 必需 | 安全深扫；全局禁/本工作区启（config 实证） |
| skill-creator 0.1.0 | 240 | 必需低频 | 流程固化触发行 |
| plugin-creator 0.1.1 | 234 | 无关 | 规则只引用 skill-creator。低优先候选 |
| visualize 0.1.0 | 311 | 待定 | Gen UI 可视化，可辅 GUI 测试 |
| zcode-guide 0.3.0 | diagnosing-commands/hooks/mcp/plugins/skills 610/617/515/657/538；configuration-guide 565 | 必需低频 | 配置诊断真值源（本次盘点多处引用即证） |

### 1.4 缓存存在但未注入本会话（不占上下文，只占磁盘）

computer-use 0.6.5、document-skills 0.1.5（被 documents/presentations/spreadsheets 分件取代=废弃缓存）、pdf 0.2.1（**技能被工作区 config 禁用**）、restore-legacy-sessions 0.1.0、watch-positions 0.1.1（两端均禁）、android/ios 模拟器（suppressed）、image-search/node-repl-host（MCP 工具在用、无技能注入）。多版本缓存目录=磁盘清理候选，与上下文成本无关。

### 1.5 实测结论（修正原"1-2KB"拍脑袋估算）

- 卸载候选**逐项明细**（终裁拍板点2：原"无关 6 项 881B"标签与 §1 分类不一致，已更正——实为无关 4＋重叠 1＋待定 1）：

  | 技能 | 分类 | 描述字节 | 零引用核查 | 卸载理由 |
  |---|---|---|---|---|
  | grill-me | 无关 | 82 | ✓ 全零命中 | 与 decision-critic 职能重叠，双评审通道 |
  | grill-with-docs | 无关 | 137 | ✓ | 同上 |
  | triage | 无关 | 167 | ✓ | issue 分诊，项目无 issue 流 |
  | improve-codebase-architecture | 无关 | 156 | ✓ | 诱导全库重构提议，与"只改卡面点名文件"相抵 |
  | web-design-guidelines | **重叠** | 184 | ✓ | 与 web-gui-tester 走查重叠（非"无关"） |
  | emil-design-eng | **待定** | 155 | ✓ | 设计期或有用，owner 追认后方可卸（与无关性质不同） |

  另：frontend-design .agents 副本（重叠，sha256 与胜者全同，零风险移除）；autoglm 514B（待定，第三方供应链面，owner 单独裁）。github 无关 3 项（codespace/gist/setup 635B）须整插件禁才生效而同插件含必需技能→**不可行，撤出候选**。合计现实可回收 ≈0.9–1.4KB/会话（每卸一个省其 description 常驻字节）。
- **body 级冲突扫描（终裁补充④，2026-10-20 已跑）**：44 项在役技能 body grep `add -A|no-verify|--force|git push`——仅 2 处命中且均属正常语境（github:pr 的 push 指令=PR 职能本体，由"执行者只 commit 不 push"红线兜住；plugin-creator 的 `--force` 系教人**不要**用）；`add -A`/`--no-verify` 零命中。**无 body 级隐藏冲突**。
- 对照：任务委派节迁移一项净省 ≈6.7KB/会话（§4）。**优先级排序：迁移 >> 卸载**；卸载只做零引用候选+frontend-design 重复副本。
- 隐性冲突 4 例：github:commit（实锤，上述）；autoglm（供应链面）；grill 双件（与 decision-critic 双评审通道）；improve-codebase-architecture（诱导超卡重构）。

### 1.6 版本健康度

- 市场装 4 插件（installed_plugins.json）：mimosa 1.0.4 / github 0.1.2 / watch-positions 0.1.1 均=官方市场最新（marketplace.json 2026-10-20 拉取比对）；pyright-lsp 1.0.0 系 2026-10-20 新装（claude-plugins-official，该市场索引 09-13 后未刷新——**终裁补充⑤处置：标"待定"而非必需**，功能验证待最近一次 Python 会话以 LSP 诊断探针一次确认，不可用或来源存疑则禁用；验证窗口=清卸卡验证窗，风险窗口最小期处置）。
  - **探针已执行（2026-10-20，D-05 执行批内，owner 令顺跑）**：`pyright-langserver` 二进制全机缺席——npm 全局（G:\nodejs\node_modules）空、PATH 无、ZCode 应用无内嵌副本（D:\zcode\resources 检索零命中）、插件数据目录（plugins\data\pyright-lsp@claude-plugins-official）空；插件本体仅声明 `lspServers.pyright.command=pyright-langserver --stdio`，无自带运行时。LSP 诊断通道无法建立（spawn 即失败，属基础设施缺失非契约失败）→ 按 §1.6 处置规则判**不可用**。禁用动作（全局启停行 pyright-lsp 启→禁）待清卸卡窗口执行；不安装运行时（安装属范围外，未授权）。Node v24.21.0 在场，若日后 owner 令恢复，`npm i -g pyright` 后重跑探针即可翻绿。
- 内建插件（browser-use/zcode-guide/documents 等）随 ZCode 应用分发，无独立升级面，无过期风险；缓存内多版本旧目录仅磁盘卫生问题。
- 用户级技能无版本机制（纯 markdown）：lessons/config-write 2026-10-16 刚维护=健康；其余 09-23/09-28 装入，无弃用标记机制，以引用与使用频度管理。

### 1.7 卸载 SOP（问题一第 5 点，卸载前引用核查已预跑）

- **卸载前**：① 引用核查（评议员 MEDIUM 采纳后已扩面）：两级 AGENTS.md＋hooks 注册快照＋全部 SKILL.md 互引＋decision-log.md＋roadmap.md＋README-失配点盘点清单＋MEMORY.md＋lessons LEDGER/TICKS——**补跑原始输出=全零命中（EXIT=1）**，零外部引用结论成立；② TICKS 打点（**纪律性**：H1 matcher 仅 `Edit|Write|MultiEdit`，拦不住 mv/目录移动，评议员指正采纳——打点靠纪律不靠机制，如实登记）。
- **卸载方式（评议员替代方案 2 采纳）**：技能=**整目录移出 skills 根至兄弟目录**（`~/.zcode/skills-disabled/`，对 `*/SKILL.md` 发现面结构性不可见，优于无证据的 `.disabled-` 前缀改名）；插件=enabledPlugins 置 false（不删缓存）。
- **卸载后**：① 新会话确认 Skill 清单条目消失、无同名残影；② 跑一次验证链抽检（GUI 链走 web-gui-tester、派卡链走一次真实看护）确认触发链无断；③ config-write 一体命令只读检查（六文件基线漂移 NOTE 应零）；④ TICKS 留痕。

## 2. 问题二修订之一：先例强度降级与三层架构

**接受批评**：lessons（H1 hook 机制兜底）、config-write（一体命令流程兜底）与 dispatch-discipline 不在一个量级；原方案"靠触发行"确为弱约束，不能假定与先例同样可靠。

**修复=补机制级兜底，且证据支持可行**：zcode-guide 0.3.0 实证 PreToolUse matcher 匹配工具名且 `Agent` 在列（Task↔Agent 别名）。因此立 **H3 派卡门提案**：`PreToolUse matcher "Agent"` → `h3-dispatch-gate.sh`，复用 H1 的**机制模式**（TICKS 分钟窗打点代理、shadow/enforce 模式文件、逃生阀、fail-closed、hooks-log）——**但谓词须重新实证**：H1 核心谓词是 file_path，Agent 入参无此字段，结构性不可照抄。

**HRO-1 回应：采纳（评议轮 2026-10-20）**。评议员证实 H1 核心谓词 file_path 在 Agent 入参中不存在，"完全复用"不成立；且 matcher `Agent` 会同时命中 code-reader 委派（误伤面），OpenCode wrapper 派卡走 Bash 根本不经过 Agent（覆盖缺口）。据此 H3 **降级为试点**：
- 立项前置实证：构造一次真实 Agent 调用采集 PreToolUse stdin 原始 payload，确认存在稳定判据（候选=`subagent_type` 取值域区分派卡/检索）；判据不可得→放弃 H3，采纳评议员替代方案：触发行+shadow 实测触发率（§5 的 ≥9/10 窗口），决策记录明写"纪律级弱约束，接受触发失败风险"。
- shadow 期产出三列日志（Agent 调用总数/判定为派卡数/误伤 code-reader 数），据此才谈 enforce；enforce 翻转走确认门。
- 覆盖面如实入决策记录：H3 即使成立也只护 ZCode 直派通道；OpenCode 备用通道的派卡无对应拦截点（wrapper 模板注入仅保卡面格式，不保"派卡前调 skill"），缺口挂账随通道复活再评估。
- **不宣称"先例强度与 lessons 对齐"**——H3 谓词强度天然弱于 H1（打点代理证不了 skill 已读），该句从本规格删除。

**owner 终裁（2026-10-20，拍板点1）**：H3 **有条件立项**——批准前置证据采集（构造真实 Agent 调用采集 PreToolUse payload，确认 subagent_type 可区分派卡/检索）＋shadow 日志（看清 Agent 调用中派卡与 code-reader 比例）；**不批准在 enforce 语义定义前建 gate**。终裁理由采纳：PreToolUse 拿不到"skill 已读"信号（无 Skill hook、无 marker、无可验证谓词），enforce 只剩三条死路——拦全部派卡（误伤 code-reader）／仅记日志告警（非 enforcement）／marker 文件（模型写 marker 不可靠）；若 enforce 最终无法定义，按上文回退走"纪律级弱约束"（**默认预期，非例外**），不用工程成本换验证不了的"门"。

**机制层先行路径（owner 替代建议采纳，替代 H3 gate）＝Skill hook＋审计**：PreToolUse 挂 `Skill` 记 {时间, session, skill 名} 入 `hooks-log/skill-loads.jsonl`；PreToolUse 挂 `Agent` 记 {时间, session, subagent_type} 入 `hooks-log/agent-calls.jsonl`（即 shadow 日志，但无需 gate 逻辑）；审计脚本对每次派卡类 Agent 调用查同 session 之前有无 dispatch-discipline 加载记录，算合规率并输出"哪几次派卡前没读"。优点：不拦任何调用、无 fail-closed/escape valve/enforce 语义争议；直接测"skill 有没有被读"而非"Agent 有没有被调"；Skill 日志可复用于其他合规检查（如 GUI 验证前查 lessons）。gate 若最终要 enforce，在此日志之上加规则即可，不必先建 gate。实施前置实证：Skill/Agent 两工具的 PreToolUse 入参字段各采一次样（与 payload 采集同批）。

三层定稿（终版）：**dispatch-discipline skill（细则真值源）＋ AGENTS.md 触发行（指针）＋ Skill hook＋审计（机制层，先行）**；H3 gate 降为"enforce 语义可执行化之后"的远期选项，非本批交付物。

## 3. 问题二修订之二：逐条划界（不按节打包）

| 条目 | 性质 | 归属 |
|---|---|---|
| 主模型直做分工／code-reader 委派／勿亲 grep | 治理·决策权 | **留**（骨架行） |
| 重大决策先 decision-critic＋HRO 回应＋归档 decision-log | 治理 | **留**（骨架行） |
| 同工作树≤1卡／只 commit 不 push／超卡即退／卡面自足 | 治理·硬红线 | **留**（骨架行） |
| token 三档（15/18/20 万） | 治理·每轮水位 | **留**（骨架行） |
| 完成通知标记场景清单 | 治理·静默失败不可检 | **留**（压缩骨架，不外迁——理由：通知丢失无从发现，懒加载失效=静默） |
| 不可委托边界、可派/不可派判断 | 治理 | **留**（用户表格同判） |
| exec_wrapper 命令形态／卡面四条+指针令模板 | 操作细则 | **迁** |
| 轮转兜底／exec.v1 契约／CHIAN_EXHAUSTED 处置／逃生阀 | 操作细则 | **迁** |
| 放量期并行细则（抽查对账/双模型钉/端口纪律） | 细则 | **迁**（并行度=2 与白名单卡型留骨架半行） |
| 10 分钟看护／验收全流程／修正分工 | 细则 | **迁**（留半行触发行） |
| 技能使用各条细则 | 细则（本体已各在其 skill） | **迁**（节压成 2 行索引） |
| 验证链顺序／提交五步／两禁令／哨兵行 | 硬红线 | **留**（哨兵「按本节默认执行」必须原样保留恰 1 次，否则一体命令 HARD） |

## 4. 问题二修订之三：体量数学（全部实测）

- 现状 8994B（硬限余 222B，软限已破常态告警）。
- 骨架 v2.2 实测 **2435B**（§4.3 全文；相对 v2.1 的 2466B：终裁摘除 pdf −12B、github:commit 范围注记改写 −19B；相对 v2.0 的 2013B 净 +422B=评议裁定补齐的不可委托清单/完成通知反制句/治理细节/github:commit 半行），新 skill description 常驻约 +300B → 常驻成本 8994→≈2735B，**净省 ≈6.3KB/会话（−70%）**；AGENTS.md 回到软限内，常态告警消除。
- 迁出细则 ≈8881−2434≈6.4KB，加卡面模板成 dispatch-discipline SKILL.md 约 8–9KB ≈200 行，低于 500 行软目标；skill 本体无字节硬限（92KB 实证）。
- 触发行累积已计入骨架（每节首行的指针即触发行，共 4 条，未另加行）。

### 4.3 骨架 v2.2 全文（实测 2435B 含尾换行/正文 2434B，复核触发线 ≤2600B；终裁调整：摘 pdf＋github:commit 范围注记）

# 任务委派规则（细则真值源=dispatch-discipline skill：派卡/看护/验收前必调；skill 不可用即停报，不得凭记忆执行）
- 分工：需求分析/方案设计/架构规划/多步推理主模型直做；查代码库派 code-reader，勿亲 grep；重大架构/选型/拍板（含排期/取舍/风险接受）先 decision-critic 评议，[HIGH_RISK_OBJECTION] 须采纳/驳回/复议回应，拍板后归档 docs/decision-log.md。
- 不可委托（须 owner 决或主模型亲持，不得派卡）：目标定义、方案取舍拍板、跨执行者冲突裁决、需求澄清、高风险与最终验收放行、规则变更。
- 派卡硬红线：同工作树 ≤1 卡；执行者只 commit 不 push；超卡即退回；卡面自足（模板见 skill）。
- 主会话 token 三档：15 万软预警仅写 digest 骨架、18 万硬预写结构化收口、20 万强制收口即停（模板 docs/design/manual-rollover-template.md）。

# 技能使用规则（触发行索引）
- 产物即触发：xlsx/pptx/docx 必调对应技能；推送前 commit ≥3 文件或 ≥100 行调 code-review（docs-only 及 ≤2 文件且 ≤60 行豁免）；修 bug/改默认值必带回归测试且测试基线只增不减（新功能可 tdd 走红绿）；GUI 变更提交前 web-gui-tester 黑盒验证（目验前先调 lessons），提交信息注明 GUI 已验证/未验证。
- 会话交接/收尾走 handoff+lessons；同类脚本第 3 例提议 skill-creator 固化（经我同意）；清单无匹配先 find-skills。

# 提交与验证规则
- 验证链硬序：静态检查→定向测试→全量测试→冒烟→安全深扫比基线（零新增才放行）；任一环失败即停；工具链取项目配置。
- 提交五步：secret 扫描→提交（Conventional 前缀+中文描述，正文 verify: 验证结果+Refs: 决策 ID）→三查→push 前远程核对→push 后 ls-remote 复核；github:commit 仅限非项目仓库。两禁令：永不 --no-verify；永不 git add -A。
- 项目特有参数以项目 docs/ 或项目级 AGENTS.md 为准；若两者皆无，按本节默认执行，并在完成通知里标注。

# 完成通知规则
- [任务完成] 标记仅在整体收口+无后台任务+回复后即空闲时于首行输出一次，正文他处不得出现该标记字样；中间进度/纯问答/仍有任务在跑一律禁用；Stop hook 自动推送，勿自发通知命令。

## 5. 失败可见性设计（四失败模式全数对策）

| 失败模式 | 对策 |
|---|---|
| skill 文件损坏/被删 | 触发行内建语义「skill 不可用即停报」；**负向钉拆两项**（终裁补充②）：①机制负向钉（可自动化）=移出 skill 目录→跑 h2 只读检查→断言报缺失→复原→断言检查通过，写进迁移卡验收命令；②模型行为抽检（人工）=一次真实派卡演练记录"预期停报/实际行为"，仅观察不入门 |
| ZCode 升级改加载机制 | dispatch-discipline 落地后**不扩六文件基线**，h2 只读检查段按终裁补充①改为「**存在性＋最小字节下限＋关键行包含**」（关键行="派卡前必调"与"skill 不可用即停报"）——覆盖删除/截断/关键内容丢失三类失效，且**免全文件 sha256 的维护负担**（否则每次编辑 skill 都要改 h2→触发 hooks-files 刷新，改一次 skill 走一轮仪式）；h2 变更随 hooks-files 清单刷新走一体命令常规路径；ZCode 升级后 lessons 复检点加一条：跑一次 skill 可用性自检 |
| 触发行语义漂移（模型不认场景） | 触发行=精确动词+精确 skill 名（Skill 工具按名匹配，无正则面）；触发可靠性窗口（终裁补充③）=**3 周或 10 次真实派卡，先到为准**；不足 10 次则延长窗口并在审计报告注明"样本不足"；合规率数据由 Skill hook＋审计机制（§2）产出，≥9/10 视为可靠，不达标→回迁或升级机制 |
| hook matcher 失配 | Skill/Agent matcher 用精确工具名（大小写敏感，文档实证）；shadow 日志先行看命中率；两工具 PreToolUse 入参字段各采一次样后才写 hook（与 payload 采集同批） |

## 6. 跨执行者一致性（OpenCode 主模型之问，已实证）

- **skills 是 ZCode 客户端功能**（六层发现顺序均为 ZCode 配置面）；OpenCode 是独立 CLI（opencode-cli.exe），不加载 ZCode skills。
- **派卡决策只发生在 ZCode 主会话**：wrapper `--standalone` 单发卡，OpenCode 实例不自派卡；2026-10-20 起批任务直派 ZCode 智能体，OpenCode 转备用。实证：exec_wrapper.py 源码 grep AGENTS/skill 零引用（只透传卡面）。
- 因此 dispatch-discipline 只需对 ZCode 主会话可用；执行者（OpenCode 或 ZCode Agent）只消费卡面实例。**"卡面必填字段"的消费者是写卡方（ZCode 主会话），非执行者**——卡模板放 skill 内即可，无须为 OpenCode 另留；跨通道一致性由已留骨架的"卡面自足"硬红线保证。
- 残余如实登记：OpenCode 是否读项目级 AGENTS.md 未实测；因执行者无需派卡纪律且项目规则经卡面传递，不影响本迁移正确性。

## 7. 时序裁决（D-05 vs 迁移，已实测）

- 实测：8994B＋D-05 增量 ≈9057B＜9216B，**D-05 不超限，先行不动摇**（已批开工令，改动极小且预检过）。
- "带病默认接受"风险已有机制兜底：若执行前意外增长越 9216B，一体命令 HARD 自动拒绝刷新基线（fail-safe 已在生产）——D-05 卡执行约束加一条「执行前跑一体命令确认 HARD=0」。
- 迁移给**硬时点**：D-05 验收收口后**立即裁卡**，为 D-05 后续第一项；且迁移本身是把 AGENTS.md 拉回软限内的唯一路径，不得再挂"之后再说"。
- **次生问题处置（评议员 NOTE 采纳＋终裁拍板点5 强化）**：①迁移整文件换骨架将吸收 D-05 对 AGENTS.md 的路径修正项——该修正成果随 exec_wrapper 命令迁入 skill 时以**绝对路径**落卡，不丢失；②**不取"合并到迁移卡"备选**（终裁裁定：合并备选有断窗——D-05 完成到迁移完成之间 wrapper 已在绝对路径而 AGENTS.md 仍指相对路径，窗口内派卡即失败；默认方案多一次 H1 打点＋一次基线刷新，成本小换零断窗）；③回滚防护从"卡内声明"升级为**脚本 guard**（终裁：声明人可能不读，guard 跑就拦）——D-05 回滚脚本开头加：

  ```bash
  if [ -f ~/.zcode/skills/dispatch-discipline/SKILL.md ]; then
    echo "ERROR: dispatch-discipline migration has occurred. Rollback migration first."
    exit 1
  fi
  ```

  ④回滚顺序写死：**迁移回滚 → D-05 回滚**，反向不成立。

## 8. 排期建议（拍板后）

1. **D-05 执行批**（已批，先行）：照开工令执行，卡内加"执行前一体命令 HARD=0"约束。
2. **迁移卡**（D-05 收口后立即）：件A=dispatch-discipline skill 新建＋AGENTS.md 换骨架（恰 2 文件；先 TICKS 打点，H1=enforce 在场，走 config-write 协议全流程：写前比对→一体命令→基线刷新）；件B=Skill hook＋审计机制层（skill-loads.jsonl＋agent-calls.jsonl 两 hook 注册＋审计脚本，hooks 变更随 hooks-files 刷新走一体命令路径）＋Skill/Agent PreToolUse 入参加样采集。卡数=2–3，卡面文件数均 ≤2。**H3 gate 不在本批交付**（终裁拍板点1：enforce 语义定义前不建）。
3. **清卸卡**：frontend-design .agents 副本移除＋无关 6 候选移出根目录至 skills-disabled＋github:commit 禁用半行（已并入骨架一次写死，无需另改）。
4. **验证窗**：迁移后 10 次派卡统计触发率（≥9/10）；H3 shadow 三列日志观察 1–2 周后议 enforce。

## 9. 拍板点裁决记录（owner 终裁 2026-10-20，全部落定）

1. **H3 试点＝有条件立项**：批准前置证据采集＋shadow 日志；**enforce 语义定义前不建 gate**；机制层先行=Skill hook＋审计（§2）；enforce 定义不出→"纪律级弱约束"收口（默认预期非例外）。
2. **卸载清单＝条件追认**：按 §1.5 逐项明细表执行（无关 4＋重叠 1＋待定 1 逐项列明，emil-design-eng 待 owner 单独确认，autoglm 单独裁）；github 无关 3 项不可行已撤出候选。
3. **pdf 不一致＝必须解决，默认摘除**：项目当前无 PDF 产出需求，规则摘除 pdf（骨架 v2.2 已落："xlsx/pptx/docx 必调对应技能"）；确有需求时后期再议启用插件。
4. **github:commit 半行＝追认＋范围注记**："github:commit 仅限非项目仓库"（骨架 v2.2 已落）。
5. **排期＝追认默认，不取合并备选**（断窗理由）；D-05 回滚脚本加 guard（§7 代码）＋回滚顺序=迁移回滚→D-05 回滚。
6. **2600B 线＝追认，定性为"复核触发线"非"硬拦截"**：超线触发复核（是删是留逐条过），不机械拒绝写入，防"删注释凑字节"假精简。

五处执行补充全采纳：①h2 检查=存在性＋最小字节＋关键行包含（免 sha256 维护负担）；②负向钉拆机制负向钉（自动化）＋模型行为抽检（人工）两项；③触发率窗口=3 周或 10 次派卡先到为准、不足注明样本不足；④body 级冲突扫描已跑（§1.5，无隐藏冲突）；⑤pyright-lsp 标"待定"，功能验证入清卸卡验证窗（§1.6）。计数勘误：§1.3 更正为 29 条·11 源。

## 10. 评议记录（decision-critic，2026-10-20）

- 结论：**有条件支持**。1×[HIGH_RISK_OBJECTION]＋1×[MATERIAL_CONFLICT]＋4×[MEDIUM]＋2×[NOTE]。
- **HRO-1（H3 复用不成立+matcher 过宽+覆盖缺口+打点代理弱于 H1）→ 采纳**：H3 降级试点、判据实证前置、覆盖缺口挂账、"与 lessons 对齐"表述删除（见 §2）。
- **MATERIAL_CONFLICT（§3 承诺留的不可委托清单未落骨架；完成通知反制句丢失）→ 采纳，裁定=骨架补齐**：v2.1 新增不可委托行＋"正文他处不得出现标记字样"反制句＋四处治理细节（测试基线只增不减/code-review 豁免口径/GUI 已验证注明/工具链取项目配置），终版 2466B（见 §4.3）。
- MEDIUM×4 全采纳：卸载 SOP 删"H1 拦 mv"错误前提、禁用改移出根目录、引用核查扩面补跑（原始输出全零命中入 §1.7）、基线方案改 H2 只读检查段＋迁移卡文件数澄清（件A=2 文件）。
- NOTE×2 采纳：D-05 回滚点失效声明＋wrapper 绝对路径随迁落 skill（见 §7）；自陈风险无增量确认。
- **复评（裁定回传后）：终局立场=支持**。HRO-1 与 MATERIAL_CONFLICT 实质解除，无新增 HRO；放行前机械修正三项（§2 旧句"完全复用/与 lessons 对齐"删除、字节数 2400→2466 校准、§10 占位残留清理）已全部执行，闭环。
- 后续风险跟踪（入决策记录）：①H3 试点判据实证未过→走"纪律级弱约束"回退；②OpenCode 备用通道派卡无拦截点，挂账随通道复活再评估。

## 11. owner 终裁（2026-10-20，本规格定稿轮）

owner 对 v2.1 六拍板点逐条裁定（1 有条件批准／2 条件追认／3 必须定·默认摘 pdf／4 追认·加范围注记／5 追认默认·拒合并备选·加脚本 guard／6 追认·定性复核触发线），另补五处执行细节与"Skill hook＋审计"替代路径——**全部采纳落盘，规格升 v2.2**。骨架终版 2435B（摘 pdf＋范围注记），复核触发线 ≤2600B。owner 总评："v2.1 是对批评的实质性回应，不是修辞性回应……这些都能被独立复核"，原则追认。本规格达到裁卡条件，排期按 §8 执行（D-05 先行不变）。
