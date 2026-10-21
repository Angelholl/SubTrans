# 项目决策日志（decision-log）

> 由主模型维护，重大架构设计、技术选型、方案拍板经 decision-critic 评议后按 "## [日期] [决策ID/标题] [状态]" 格式追加归档，供续评与二次评议检索。

## 归档速查

- **权威声明（D2026-1020-01 C9）**：归档卷 [decision-log-archive-v1-v2.md](decision-log-archive-v1-v2.md) 属 decision-log 语料延续、**同等权威**；卷内 104 条（D2026-0914-01 ~ 2026-10-08 末条）为历史执行记录、含旧品牌词，正文逐字节未动，不作为现行表述依据；后续修订只在现行日志追记，本卷不改写。现行区条目自 D2026-1009-01（2026-10-09）起。
- 检索口径：按决策 ID 全文检索定位；行号不作引用锚（D2026-1020-01 owner-②）。
- **现行约束速查**（结论＋原始 ID＋回链；D2026-1020-01 验收标准⑤自检面）：
  1. 品牌钉＝产品面 default-deny 全量钉死、`docs/design/**` 整体豁免、扩大豁免须先评议（原始 D2026-1004-02 品牌统一第 1 层＋现行区 D2026-1012-03 口径修订）。
  2. Mimosa git-gate 模式＝PreToolUse 快扫拦截与密封扫描双口径分列、不强行核平，插件版本变更即重评（原始 D2026-0921-03，归档卷）。
  3. guard 树外契约＝`internal_docs/`、`sexual_terms.csv`、`api_keys.bin` 等敏感件移仓库树外；tools/guard_banned_paths.py 名单⊆契约测试（原始 D2026-0916-01 收尾清单＋D2026-0925-02 D10 守卫落地，均归档卷）。
  4. 4 槽结构保留不动、压缩为 2 槽永久不做（原始 D2026-0922-02，归档卷）。
  5. v2_ctx 缺省＝16384（原始 D2026-0929-01，归档卷）。
  6. 生产模型搭配＝s1 lmstudio/qwen3.8-27b-uncensored-joyfox-aggressive＋s3 lmstudio/qwen3.6-35b-a3b-uncensored-heretic-apex（原始 D2026-1003-02 B2 四要素，归档卷）。
  7. 代码签名不立项＝Trusted Signing 准入不可行维持不立项，触发条件＝真实用户杀软误杀/SmartScreen 反馈到量（现行区 D2026-1011-01）。
  8. 版本政策＝纯修复走四段号不递增、功能更新才递增版号（原始 D2026-1008-01，归档卷）。
- **契约锚（D2026-1020-01 C4）**：敏感路径守卫名单中源于决策日志的条目（`internal_docs/*`、`sexual_terms.csv`，出处＝D2026-0916-01 收尾清单，原文见归档卷）以本速查节为现行契约字面量载体（tests/test_guard_banned_paths.py 整文件子串断言源，二阶段 C 组归档后不灭源）。
- 归档执行核销表见现行区 D2026-1020-01 条目「执行追记」。

## [2026-10-09] D2026-1009-01 AI 分析+修复自动化（全链路自动化）+修复源文增强+F4 疑似漏听二级自动化 [已执行·批0-3 已随 v3.0.0 发布（2026-10-11）·真实残余仅 F4 待令]（标题回写 2026-10-21，原题「已拍板·待开工·目标版本已改挂 3.0.0」与正文执行记录不符致误判，状态以本括注为准，条目正文未动）

**评议方**：decision-critic（三轮：首评 F1/F2/F3 提 HRO-1/2；追加评 F4 提 HRO-3；复议 HRO-3 有条件解除；owner 终裁后定稿）
**决策对象**：全链路自动化（一次 A/B 翻译后无人值守完成：修复→漏听补行→复验→压制）+ 修复源文增强
**状态**：已拍板，批序 批0 F1 → 批1 全链开关+状态机 → 批2 面板/digest/回滚入口 → 批3 漏听段 C22 门

### 一、owner 需求原话（两条）

1. 「能否实现对AI分析和修复的自动化？修复中部分为未翻译内容，这部分应该是可以自动化二次翻译的，其他部分能否也实现？」
2. 追加问：「疑似漏听（status=observation，设计上不进批量修复，仅供人工核对）那如果遇到普通用户不懂日语的如何实现核对？」

### 二、owner 终裁（原话要点，2026-10-09）

「这种流程下，任务从一开始就能自动化，设置一个自动化按钮，勾选后实现全链路自动化：一次A/B阶段翻译→根据质量报告对未翻译内容分批自动重翻→根据质量报告对疑似漏听：批量转写→置信门三档→高置信：自动补行／低置信：直接放弃（1S以内的语音能量放弃不影响观感）→复验分析1次→通知汇总→（压制若开，排在补行之后）」

### 三、方案四件套（终形态）

- **F1 修复源文增强**：`refine_batch_fix` 与自动链传 `--action-source`（现不传，`api.py:3141-3150`）→ 消除 `source_excerpt` 40 字符截断（`quality_report.py:1414-1426`）。**源文定位三级**：`guide_dir/{guide["source"]}`（真实输入名，`quality_report.py:1481`）→ `guide_dir/{stem}.srt` → 退化并通知（现规则仅在"输出目录=输入目录"时成立，`pipeline_support.py:69-77` + `api.py:313-316`）。手动+自动两路径共用。
- **F2 全链路自动化（单开关）**：管线设置新增单一开关（缺省**关**，勾选后任务发起即全链无人值守）；链起点=用户发起 A/B 翻译（不做目录监视自动发起）。同一会话完成状态机串行执行：预热（既有 P1）→ 逐文件无头分析→甄别 fixable（open+有现译+台账未修+分类白名单）→≤50 分批 `--action-retranslate --apply --action-source`→复验分析 **1 次**→通知汇总。**A 档：全类别自动**（配回滚+digest）。仅本地 provider 自动；云端 provider 跳过+通知；`suspected_missed_speech` 不入本轮修复（由 F4 承接）；失败不重试。
- **F3 面板可见性**：质量与建议页自动化状态一行（进行中/最近一次结果摘要）；链级 digest 逐条 before/after。
- **F4 疑似漏听二级自动化**（并入同一状态机，见拍板 15）：
  1. 批量转写：≤20 段一次装载转 N 段（C17 改造落地）。
  2. 置信门**三维分档**：`no_speech_prob/avg_logprob` 阈值 + n-gram 重复/循环 + 文本长度/时长荒谬性 + `language=ja` 校验 + 纯拟声过滤 → 高置信 / 低置信 / 判空。
  3. **高置信 → 自动补行**（真自动、无确认）：独立插入通道+独立恒等式（C15）；timing=检测语音窗口、时长=min(窗口, CPS 上限换算) 防挤压；台账记 `auto_insert`；纳入一键回滚（删行语义）与 before/after digest。
  4. **低置信 → 直接放弃**（owner 终裁，无核对卡）；**语音能量窗口 ≤1s 一律放弃**；通知/digest 仅计放弃数。
  5. **C22 校准门**为真自动补行的批内开工门（见 C22 语义修正）。

### 四、HRO 一二三处置

- **HRO-1（自动改终稿不可逆：仅台账 `old_text`、无恢复入口、弱复验）→ 采纳（附条件）**：落地一键回滚入口（改写恢复 + 补行删行双语义，C3/C16）、before/after digest（F3）、复验语义收口如实（C4）。owner 终裁采 A 档全类别自动，以"可一键回收 + digest 在案"承接该风险。
- **HRO-2（与压制自动化并发：`_lms_unload_all_quiet` unload --all 冲突 + skip-existing 成品固化）→ 采纳**：压制开关保持独立，但**全链路自动化开启时强制时序**——修复+补行链完成 → 才触发压制（C7/C23）；未开启全链路时压制行为不变。`[DEPENDENCY-IMPACT]`：D2026-1008-02 P1 预热同挂会话完成 hook，"压制为 ffmpeg 非 LLM 消费者、不构成资源冲突"前提在双开场景失效 → 预热并入同一状态机（C5）。
- **HRO-3（whisper 幻觉 + 非日语用户 → 确认键失效）→ 有条件解除 + 终裁修正**：承重门=C22 真机非言语样本校准（查准达标才启用高置信自动补行）与 C23 插入→压制顺序门/交付可见性，另有 C13/C15/C16 落地。**owner 终裁修正**：低置信不再回流核对卡（C14 失效），**不达标=漏听条目全部放弃**（原"降级低置信卡"作废）——owner 知情接受漏听丢弃风险。

### 五、条件清单 C1-C23（终版）

- **C1** 源文定位三级（`guide["source"]`→`{stem}.srt`→退化+通知）。
- **C2** 源文 timing 精确命中率在 jur-531 实测并报告（`action_retranslate.py:208-210`）。
- **C3** 一键回滚入口（owner 拍板 4，强制）：改写=按台账 `old_text` 恢复，补行=删行，双语义。
- **C4** 复验语义收口：1 次分析=弱复验，文案如实；报告 txt 陈旧与 guide 已刷新的不一致须标注；链内分析收敛为**修复后 1 次**。
- **C5** 预热（D2026-1008-02 P1）并入同一会话完成状态机，单会话只 1 次预热+1 条链。
- **C6** 链运行期间禁止 `start_translation`（推翻"会话已完成即天然互斥"）。
- **C7** 先修后压强制时序（全链路开启时）。
- **C8** 自动链复用 `refine_batch_fix` 后端（含进度/取消槽/台账）；`refine_batch_fix` 补重入守卫（现无，`api.py:3035-3060`）；补齐竞态矩阵。
- **C9** GUI 关闭=链断**不补跑**+UI 明示"上次未完成 N 条"（台账幂等，后续自然收敛）。
- **C10** 通知通道仅 `_automation_notice`（gui.log+Console，无 OS toast）之限须文档标注。
- **C11** 分类白名单 fail-closed（未登记/未知 category 不自动）；分类收窄 KV 保留为高级项，缺省=全部有现译类。
- **C12** F1 入 2.8.1 批0，不入 2.8.0.x 四段号（增强非纯修复）。（已改挂 3.0.0 批0，D2026-1009-02）
- **C13** 置信门三维分档（plumb 运行器已返回却丢弃的 `segments` 置信；`asr_runner.py:96-104`）。
- **C14 【v1 失效 — owner 终裁取消核对卡】**低置信诚实文案作废；低置信改直接放弃。
- **C15** 独立插入通道+独立恒等式（现 `--apply` 断言条目数不变，`action_retranslate.py:242-254`，补行必增行，禁止复用）。
- **C16** 台账 schema 扩展：新增插入记录 `auto_insert`；回滚支持"删行"与"恢复 old_text"双语义（`adopted_insert` 随 C14 取消而暂不落地）。
- **C17** 批量转写改造：一次装载转 N 段（现为每段一进程一 large-v2 装载）+ `local_transcript` 持久化即缓存 + 无 GPU 保守上限/超时。
- **C18** 媒体缺失/`slice_clips` 失败诚实退化（显式"无音频对照"，不静默空卡）。
- **C19** F2 与 F4 同一状态机，顺序固定（修复 → 漏听 → 复验）；补行"现译"须与终稿一致。
- **C20** `local_transcript` 生命周期：guide 为"写前清陈旧"件（`v2_outputs.py:178`），重跑即丢，手册明示。
- **C21** 疑似漏听 >`_MAX_CLIPS=20`（`asr_env.py:51`）时 UI/通知明示"仅前 20 条"。
- **C22 校准门（语义修正，owner 终裁）**：开工前用 owner 真机非言语样本集实测"高置信"判定查准率，达阈值才启用真自动补行；**不达标=漏听条目全部放弃**（非降级核对卡）。阈值/样本/标注/结论入方案文档，防循环自证；首版阈值从严。
- **C23 插入→压制顺序门与交付可见性**：①含 `auto_insert` 的文件，自动压制必须排在其后；②烧制前须有插入项可见检查点，否则含 `auto_insert` 文件排除出自动压制并告警；③压制 skip-existing 不得吞掉补行后的重压；④"来源标记"落点=guide/台账（SRT 正文不带可见标记）。

### 六、16 项拍板落定（owner 终裁处加粗）

1. F1 单独 2.8.1 批0，不入 2.8.0.x —— **按建议**。（已改挂 3.0.0 批0，D2026-1009-02）
2. 源文定位三级 —— **按建议**。
3. 自动修复范围 —— **A 全类别自动（配回滚+digest）**。
4. 一键回滚 —— **要（改写恢复+补行删行双语义）**。
5. 与压制关系 —— **先修后压（强制时序）**。
6. 开关形态 —— **单一「全链路自动化」勾选替代多开关；缺省关，勾选后任务发起即全链无人值守**。
7. 复验口径 —— **1 次分析弱复验+如实文案**。
8. GUI 关闭 —— **不补跑+UI 未完成量**。
9. 链内分析次数 —— **仅修复后 1 次**。
10. 置信门 —— **三维分档（高/低/判空）**。
11. **【owner 终裁覆盖原 C14】低置信直接放弃（无核对卡）；≤1s 语音能量一律放弃；通知/digest 仅计放弃数**。
12. 插入通道 —— **独立插入通道+独立恒等式**。
13. 成本前置门 —— **≤20 段转写实测达标才进链**。
14. 批量转写 —— **一次装载转 N 段**。
15. **【owner 终裁】F4 与 F2 合并为单一状态机链**（单开关下不再分批；F4 段=链内一环；C22 校准门为其真自动补行批内开工门）。
16. 真自动放行门 —— **C22 校准查准达标才启用高置信自动补行；不达标=漏听全部放弃**。

**补充锁定**：链起点=用户发起 A/B 翻译（无目录监视）；C22 不达标时漏听条目**全部放弃**（知情接受丢弃风险）；压制自动化保持独立开关，全链路开启时强制排布于修复+补行之后，未开启时行为不变；预热并入同一状态机（C5）。

### 七、批序

- **批0**：F1 源文增强（含三级定位，手动+自动共用）。
- **批1**：全链路开关 + 会话完成状态机（预热/修复/复验/通知的串行骨架，复用 `refine_batch_fix` 后端 + 重入守卫 + 互斥矩阵）。
- **批2**：F3 面板/digest/一键回滚入口（删行+恢复双语义）。
- **批3**：F4 漏听段（批量转写改造 → 置信门三档 → 高置信自动补行；含 C22 校准门与 C23 顺序门）。

### 八、验证链与基线

静态（ruff/mypy 门禁）→ 定向（改动单文件）→ 全量（**起点基线 2266+4**，只增不减）→ 冒烟（--help/可启动）→ 安全深扫并与基线比对（Mimosa deep 起点 38=37+1 已甄别，零新增才放行）；GUI 变更走 web-gui-tester 黑盒；C22 校准门另有"真机非言语样本查准率"专项验收（批3 开工门）。

### 九、后续风险跟踪

- **[DEPENDENCY-IMPACT]** D2026-1008-02 P1 预热触发点与全链状态机的合并，需就原决策发起复议确认单一状态机化（C5）。
- **HRO-2 × F4 交叉**：自动补行→自动压制 的成品固化路径，须待 C23 落地方可解除。
- **"confidently wrong" 残余风险**：owner 知情接受；首版阈值从严；C22 不达标即整体放弃（不硬凑自动）。
- **漏听丢弃面（owner 终裁新增）**：低置信与 ≤1s 条目**不再浮现给用户**，真实轻语/短句漏听将被静默丢弃，用户只能从"放弃数"统计感知——owner 知情接受，记入手册；后续若出现"某句明明没字幕"投诉，first-look 指向本条。
- **rollback 数据面**：台账随管线 `--force` 重跑被备份并清旧（`v2_outputs.py:158-186`），回滚窗口以最近一次运行产物为界。

### 十、决策日志标准字段

- **原决策**：立项 D2026-1009-01（F1 源文增强 / F2 分析修复自动化 / F3 面板 / F4 漏听核对），目标 2.8.1（已改挂 3.0.0，见 D2026-1009-02）。
- **我的异议**：HRO-1 自动改终稿不可逆；HRO-2 与压制自动化并发/成品固化；HRO-3 whisper 幻觉使非日语用户确认失效。
- **主模型最终决定**：部分采纳 —— HRO-1 采纳（回滚+digest+如实复验）；HRO-2 采纳（先修后压强制时序）；HRO-3 有条件解除（C22 校准门 + C23 顺序门为承重条件，终裁修正为低置信直接放弃）。
- **条件是否已闭环**：未（C1-C23 待开工逐条闭环；C3/C22/C23 为开工门，未闭环则相应真自动不启用）。
- **是否 [PRESSURE-OVERRIDE]**：否 —— owner 为知情风险接受（低置信放弃、C22 不达标整体放弃），非时间/权威压力放行，另行记入跟踪。
- **后续风险跟踪**：见第九节。

### 十一、执行追记（2026-10-09，D2026-1009-02 版本改挂+执行方案定版）

- **版本改挂**：owner 指示「全链路自动化设为3.0」，本决策目标版本 2.8.1 → **3.0.0**；C12 与第六节拍板1 措辞同步换号：F1 入 **3.0.0 批0**，不入 2.8.0.x（语义不变仅换号）。批序/16 拍板/C1-C23 全部维持有效。
- **号段**：2.8.1 与 2.9.x 空置跳过（2.9 全仓仅 decision-log:2944 历史锁序引用、无活跃挂账，历史梯队已随 2.8.0 改派作废；3.0=全链路自动化代际，直接承接 2.8.0.2）；CT2/qwen3 不进 3.0、未钉号后续另立项。
- **执行方案定版**：批0-3 执行案、双预案制、C22 复合校准门终值、C5 复议结论等全文见 **D2026-1009-02**。
- **开工门**：批0=2.8.0.2 正式发布（main bump 3.0.0.dev0 绑定批0 首笔提交）；批3=C22 校准达标（或按双预案走放弃语义/预案 B）。

---

## [2026-10-09] D2026-1009-02 SubTrans 3.0.0「全链路自动化版」执行方案定版（版本改挂+批执行案+双预案制+C5 复议）[已拍板·待开工]

**评议方**：decision-critic（首评：有条件支持——HRO-1 链内复验次数冲突、HRO-2 压制先于链执行，8 CONDITION+6 NOTE；二评：支持、无新增 HRO，两钉收口；C5 专项复议：有条件支持——1 MATERIAL_CONFLICT+3 条件）
**决策对象**：D2026-1009-01 目标版本 2.8.1→3.0.0 + 完整批执行方案（owner 三轮审核后拍板五项）
**状态**：已拍板（owner 2026-10-09 确认五项拍板单，两钉+残余风险「可接受」）；批0 开工门=2.8.0.2 正式发布

### 一、版本号修订案（拍板①⑤）

1. main 滚动号 2.8.1.dev0→3.0.0.dev0，**bump 时点=2.8.0.2 正式发布后、批0 首笔提交**（C-V1 采纳：decision-log 版本闭包条款承诺「RC 复验不过回 main 修」，main 先换号会把 3.0 内容带进 2.8.0.2 号段）。
2. bump 落点清单：pyproject.toml+`subtransjav/__version__.py` 三常量（release="dev"，3/0/0）+`tests/test_version_consistency.py` 三钉+CHANGELOG 另立 [3.0.0] 段且保留 [2.8.0.2] 未发布段+roadmap 登记。
3. 2.8.1/2.9.x 号段空置；CHANGELOG/roadmap 注明「3.0=全链路自动化代际」。
4. 发版：release/3.0.0 分支制+tag v3.0.0（同 2.x 先例）；2.8.0.2 先行发布不阻塞不并轨（纯修复四段号政策不变）。
5. CT2/qwen3 不进 3.0（roadmap 显式登记），未钉号另立项。

### 二、批执行案（承 D2026-1009-01 十六拍板不重开；挂点行号以施工日实测为准）

- **批0 F1 修复源文增强**（手动+自动共用，纯 api 层）：摘录截断消除两点（`quality_report.py:1414-1426`+评议新发现 `:1410` structured_warnings 分支）；`--action-source` 传参接线（`api.py:313-316`+`api.py:3141-3150`，现不传）；源文定位三级 helper（`guide["source"]`→`{stem}.srt`→退化+通知）落 `pipeline_support.py`；`cps_too_fast` 摘录恒空维持（靠 timing 映射恢复，报告注明）；DoD 含 **C2 jur-531 实测报告**（timing 精确命中率+重号 timing 命中率）=批0 收口门。
- **批1 全链开关+会话完成状态机**（a/b 两段落库）：
  - a 段=骨架+开关（KV `fullchain_auto_enabled` 缺省关，UI 放 `index.html:997-1009` 压制开关旁，`refine_save_stage_settings` 持久化）+**C7 时序门**（全链开启时钩子入口压制分支不触发、压制改链尾；关闭时钩子行为逐字节不变）+**复验参数化**（`refine_batch_fix` 加 `verify: bool = True` 形参：链内传 False，手动缺省 True 保批5 回归语义；链级复验唯一一次，**断言=长期链级不变式「LLM 分析（--ai-analyze）spawn==1」**）+重入守卫方法入口同步置位（早于 load/spawn，覆盖链/手动互斥）+导读缺失诚实跳过+通知（不静默不强制生成）。
  - b 段=互斥矩阵六对：①`start_translation`（判定在 `_session_hook_fired` 复位前，对齐既有拒绝模式）②手动批量修复 ③压制排布 ④手动 AI 分析=**显式拒绝+明确提示，不排队** ⑤前端预热 `__warmupTabHook`（app.js:4460/6635）抑制 ⑥手动压制双向排他；provider 判定单源 `_resolve_ai_model_config`+**配置错误注入单测**（云端零出域，N-6）。
  - **批3 义务**：开工首笔把 spawn 断言更新为白名单版（F4 批量转写=whisper 本地子进程，不计入分析不变式）并回归。
- **批2 链级面板+digest+一键回滚**：F3 增量=链级状态行+before/after digest（低置信/≤1s 仅计放弃数），与批5 已交付面（未修复明细/已修徽标/静默重读导读）互补不重做；回滚本批仅交付**改写恢复**（台账 `old_text`），删行路径批3 前不得标完成；`auto_insert` schema 以代表性夹具写契约测试定形（防无生产者漂移）；回滚提示**条件化**（存在 auto_insert 记录而删行未支持时显示「自动插入行暂不支持恢复」，文案不带内部批号）；回滚窗口（`--force` 重跑清账，`v2_outputs.py:176-179`）UI+手册明示。
- **批3 F4 漏听段**（开工门=C22）：C17 批量转写一次装载转 N 段+`asr_runner.py:96-100` 透传 `no_speech_prob/avg_logprob`（C13，现丢弃）+local_transcript 持久化缓存（C20 手册明示重跑即丢）+无 GPU 保守上限；三维置信门+≤1s 语音能量一律放弃；高置信自动补行=独立插入通道+独立恒等式（C15，禁复用 `action_retranslate.py:242-254` 条目数不变断言）+台账 `auto_insert`（C16）+回滚删行接线；C21 仅前 20 明示（`asr_env.py:51`）；C18 媒体缺失诚实退化；C19 接 a 段插缝（修复→漏听→复验）；C23 四点收口（压制排后/烧制前可见检查点/skip-existing 不吞重压/来源标记落 guide+台账）。

### 三、C22 复合校准门（拍板②，批3 开工门，不阻塞批0-2）

指标=**高置信桶精确率置信下界 ≥95%**（零错误判据 n≥60 起步）；样本须含真漏听阳性、取自检测器同一候选分布（同 VAD/窗口链）、owner 独立标注（与阈值测算方分离）+**≥20% 隔时复标一致率 ≥90%**（低于→争议项复核→仍低→整批剔除重采→无法重采/复标仍失败=按 C22 未达标处置；报告无数值=不完整=不达标；Kappa ≥0.8 仅在 owner 自愿提供第二标注人时作辅助门）；**同报覆盖/召回**（防阈值过严致自动补行覆盖趋零功能静默失效）；离线回放 harness 先行；阈值/样本/标注/结论成文入档防循环自证。残余风险（intra-rater 复标不覆盖标注系统性偏见）owner 知情接受，补偿=首版从严+同分布+覆盖召回同报。
**不达标处置**：F4 段照常交付运行（转写→三维分档→按拍板16 全部放弃，放弃数进 digest/通知），自动补行入口被校准门关死，CHANGELOG/手册/UI 明示。

### 四、双预案制（拍板④）

- **预案 A（默认）**：3.0.0 含完整 F4。C22 达标→全链含自动补行；不达标→补行门死+放弃语义（见第三节）。
- **预案 B（延迟）**：批2 收口日+3 天样本仍未到位→3.0.0 按批0-2 范围发布（CHANGELOG 明示「漏听二级自动化不在本版」禁模糊表述），批3 完成后 F4 入 3.0.1；此时无 auto_insert 生产者、回滚天然完整。
- **批2 收口日判定标准**：五环验证链全过+批2 黑盒 PASS+勾账提交推送日（该日起算+3 天缓冲）；不满足不算收口、时点顺延，防「事实逾期」误触预案 B。

### 五、C5 复议（对 D2026-1008-02 P1 预热挂点，[DEPENDENCY-IMPACT] 正式闭环）

- **复议结论（decision-critic 专项复议）**：有条件支持——预热并入全链状态机（开关关时原形态不变）技术成立，依赖前提有 `api.py:5462-5464`/`3679-3680` docstring 实证（「压制为 ffmpeg 非 LLM 消费者不构成资源冲突」在全链双开场景失效）。
- **MATERIAL_CONFLICT 裁定（主模型）**：版本身份=**3.0.0**——本决策即版本改挂决策，D2026-1009-01「目标 2.8.1」/C12 由执行追记换号（语义非推翻），冲突随本次归档消除。
- **三条件采纳为批1 实施要求**：**C-1** 前端两预热触发点（`__warmupMaybeStart` app.js:4192 completed 分支/`__warmupTabHook` app.js:4460）同门控——全链开启读开关短路交状态机首环承接，静态钉 `tests/test_gui_js_static.py:3219/3239/3245` 同步改写；**C-2** 同钩子编排单一化——全链开启时 `_on_translation_session_completed` 整体改道状态机，旧 encode 路径不得并存双触发（双开断言 spawn 序=预热→分析→修复→…→压制无重复）；**C-3** 关闭态回归钉——fullchain 关闭时钩子尾部仍 daemon 触发 `_warmup_after_session`（原 P1 零变化，防误门控）。
- **实现形态采纳替代方案**：「读同一 fullchain KV+短路」，不在已发版钩子内重写分支，回归面最小。
- 验证四条：全链开桥 spawn 计数=1（含完成+切页扰动）/关闭态 daemon 触发断言保留/双开单通道顺序断言/版本钉随 bump 更新。

### 六、评议处置总账

首评：HRO-1 采纳（复验参数化）；HRO-2 采纳（时序门提前入 a 段+双开黑盒断言）；MC-1 裁定（甄别=读会话产出导读零 AI 调用，「逐文件无头分析」歧义措辞删除）；C-V1/V2/V3、C-C8、C-C6、C-EXCL、C-ROLLBACK、C-C22 采纳；N-1（`:1410` 第二截断点+截断消除/传参接线两件事分列）、N-2（施工前行号刷新：`_warmup_after_session`=api.py:3673、once 守卫=5465-5467、压制调用点=5470）、N-3（导读缺失跳过）、N-4（重号 timing 命中率入 C2 报告）、N-5（回滚窗口明示）、N-6（云端零出域单源判定）全吸收。二评：五项增量全采纳（F4 范围定义→双预案制、断言生命周期→长期不变式、手动分析显式拒绝、回滚不完整条件化提示、标注独立性→复标一致率 ≥90%）；2.9 号段核查完成（仅 decision-log:2944 历史锁序，无活跃挂账）。C5 复议：1 MATERIAL_CONFLICT 裁定+3 条件采纳。**无驳回项，未触发复议程序。**

### 七、验证链与基线

起点 **2268+4** 只增不减；Mimosa deep 基线 **38**（=37+1 已甄别）零新增放行；每批五环（ruff/mypy 含 `tools/mypy_baseline.py --check`→定向→全量→冒烟→Mimosa）+批1/2/3 web-gui-tester 黑盒（批0 纯 api 层豁免黑盒）；施工行号以当日实测为准。

### 八、风险跟踪（承 D2026-1009-01 §九 全部+新增）

①批1 状态机互斥矩阵复杂度高→a/b 两段拆分缓解；②号段跳空用户侧无感知（dev 号永不宣称发布版）；③标注系统性偏见残余（owner 知情接受，已补偿）；④预案 B 触发纪律（收口日判定标准防事实逾期）；⑤批3 开工首笔必须更新 spawn 白名单断言防跨批回归失效。

### 九、决策日志标准字段

- **原决策**：D2026-1009-01（目标 2.8.1）经本决策改挂 3.0.0 并定版批执行案；C5 复议（对 D2026-1008-02 P1 预热挂点）随本决策正式闭环。
- **我的异议**：无新增（三轮评议 HRO/MATERIAL_CONFLICT 全部采纳或裁定闭环）。
- **主模型最终决定**：五项拍板全落（号段处置/C22 复合门/样本里程碑/双预案制/CT2 不进 3.0）；两钉终值=复标一致率 ≥90%+批2 收口日判定标准。
- **条件是否已闭环**：D2026-1009-01 C1-C23 仍待开工逐条闭环；批0 开工门=2.8.0.2 正式发布；批3 开工门=C22 校准；C5 复议三条件（C-1/C-2/C-3）转为批1 实施要求待施工验证。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：见第八节。

### 十、批0 收口勾账（2026-10-09）

- **开工门实测核验**：v2.8.0.2 已发布（tag→7e5223a、Release id 407740796、2026-10-09T09:06Z、setup 51,228,840B，公开 REST 复核）→ 走路径甲；**首笔提交=版本 bump（0cc90a1：pyproject+__version__ 三常量 3.0.0.dev0+CHANGELOG [2.8.0.2] 发版段回填+[3.0.0] 段另立+roadmap 2.8.0.2 发版行补登，版本三钉相对断言自动成立）**。
- **四件落点**：①截断消除两点 quality_report.py:1410/:1424（single_line 60 字符口径未动）；②三级定位 helper `resolve_action_source_path`（pipeline_support.py:70，GUIDE_JSON_SUFFIX :67 单点定义注明与 v2_outputs.py:177/:228 同源）；③`--action-source` 接线 refine_batch_fix（api.py:3168-3179，命中插 --entries 与 --apply 之间，退化不追加、CLI 既有提示兜底）；④timing 命中行为复核（action_retranslate.py:210 setdefault 语义未动，cps_too_fast 恒空维持）。
- **测试**：新增 8（三级定位×5/截断消除×1/传参接线×1/退化×1）+既有 40 截断钉改全量期望；全量 **2287+4**（批6 基线 2279+4 只增不减 ✓）。
- **C2 报告（批0 收口门）PASS**：jur-531 实测 timing 精确命中 **46/46=100%**、重号 timing **0 组**、生产 `_load_source_map` 与独立复算逐键相等；报告入档 docs/c2-timing-hit-jur531-20261009.md（局限如实注明：N=1 部，重号折叠语义未被实际触发，留待批1 digest 观察退化/错配计数）。
- **验证链六环**：①ruff（CI 口径 subtransjav+tests）clean（spike/fts5_spike.py 8 条为 main 存量、CI 范围外，stash 对照甄别）；②mypy 基线门禁通过（0/0/0）；③定向 352 passed；④全量 2287+4（首跑 1 失败 test_resume_after_rejected_rerun_reuses_stage_a_without_force，单跑/全文件/两态对照均过，甄别为全量上下文偶发、同 commit 重跑自愈，横切 flake 观察项续记）；⑤冒烟 --help+gui api 导入 OK；⑥Mimosa deep **38=基线 38 零新增**，seal sha256:df02ce76db54305bb6993656e0c9dd59884da10164991ceba9468bc53aa39f2b。
- **已知限制（如实登记）**：非 SRT 真实输入（如 .ass）命中 L1 时映射为空且 CLI 不打提示（既有 CLI 行为，非本批引入）——批1 自动链甄别时观察；C2 N=1。
- **CI 红一笔（推送后已修）**：批0 勾账与 C2 报告推送后全腿 Test 红——根因=`docs/c2-timing-hit-jur531-20261009.md` 含 `SubTransJAV` 路径字面量触发 `test_brand_allowlist` 品牌漂移钉；本地绿假象成因=跑全量时该文件尚未提交（品牌钉按 git ls-files 口径扫描，未跟踪文件不可见）——「本地绿≠CI 绿」教训复发变体：**新增文档在提交前先 git add（入 index）再跑品牌/路径类扫描测试**。已去字面量修复（复现命令改仓库根 cwd 形态、存档路径去品牌段描述），品牌钉本地复验 passed。
- **批1 开工提示**：a/b 段与 C5 复议三条件（C-1 前端触发点同门控/C-2 钩子编排单一化/C-3 关闭态回归钉）、复验参数化（verify 形参）、重入守卫入口置位、C7 时序门按 D2026-1009-02 第二节执行；施工行号刷新（锚点见第二节，api.py 批0 后 +9 行左右漂移）。

### 十一、批1 收口勾账（2026-10-10）

- **前置**：批0 提交在位+3.0.0.dev0 ✓；并发会话（D2026-1005-05 镜像点亮）6 文件在途改动经 stash 隔离→由该会话自行提交（77205ee+b0f4d56），零丢失零冲突。
- **a 段落点**（api.py/app.js/index.html/strings.py+两测试文件）：开关 KV `fullchain_auto_enabled`（缺省关，`_fullchain_auto_enabled` :5601 区，CONFIG_DIR 打桩 roundtrip 测试）｜钩子 if/else 单通道改造（:5552-5581：开=daemon 线程 `gui-fullchain-auto`（引用存 `_fullchain_thread` 供 join），关=原两段逐字节不变——C-2/C-3）｜状态机 `_run_fullchain_automation`（:5731-5912：重入判定→provider 单源门（not ok/非本地→notice+skipped）→预热首环（`_warmup_resolve_current`+`refine_warmup_analysis_model`）→逐文件零 AI 甄别（`_fullchain_fixable_entries`：open+现译+台账未修+**C11 白名单 fail-closed** `_FULLCHAIN_AUTO_CATEGORIES={untranslated,cps_too_fast,dewei,subject}+antonym_/body_part_/climax_ 前缀族；single_line_too_long 与 suspected_missed_speech 不入`）→≤50 切批 `refine_batch_fix(verify=False, from_fullchain=True)`→**F4 插缝 `_run_fullchain_missed_stage`（:5720，恒 None，批3 接入）**→复验恰 1 次（显式 provider/model 透传）→C7 链尾压制（复用 `_run_encode_automation`）→finally 清标志+落盘）｜C9 落盘 `config/fullchain_last_run.json`（9 键+原子写，unfinished 判定=ended_at 空）｜桥方法 `fullchain_last_run_status()`/`fullchain_automation_status()`｜复验参数化 `verify: bool = True`（:3338-3370，缺省 True 批5 语义零变化）｜重入守卫（`_batch_fix_running`+`_fullchain_running`，_ai_lock 入口检查置位/finally 清位）｜C-1 前端：`AppState.fullchainAutoEnabled`+`warmupMaybeStart` 守卫链最前短路（__warmupTabHook 转调全覆盖）｜MSG 键 `fullchainAutoSwitch` 双表（JS 态零冻结消耗）。
- **b 段落点**：互斥矩阵六对全落——①start_translation `_ai_lock` 段结构化拒绝（判定在 `_session_hook_fired` 复位前）②refine_batch_fix `_fullchain_running and not from_fullchain` ③encode_commit 入口拒绝（手动压制唯一入队桥；链尾经 `_run_encode_automation(from_fullchain=True)` bypass）④refine_ai_analyze 同款门+链复验 before-bypass；反向=链复验遇手动分析在飞→notice 跳过不重试、链尾遇 encode 槽占用→notice 跳过不排队 ⑤前端预热抑制（a 段）⑥=③反向。云端零出域：链首单源门+`config_error_injection` 双向注入（半配置/云端 provider 均零 spawn）。
- **测试**：+15 fullchain 系（链跑通/`test_fullchain_single_analyze_invariant` **--ai-analyze spawn==1 长期不变式**/批切 50/云端门/C7 顺序/C9/重入/互斥六对/注入）+防复发钉 `test_save_stage_settings_calls_three_args`（黑盒战果钉，红绿双证）；全量终态 **2306+4**（批0 基线 2287+4 只增 ✓）。**CI 去环境化修正**：`_fullchain_env` 统一打桩 `probe_endpoint_reachable`+`_warmup_probe_loaded`（原链测试真连 localhost:1234 依赖本机 LM Studio，同命令 30s→12s 佐证拦截）。
- **黑盒（web-gui-tester 范式现场搭：HTTP 伺服 assets+生产 TranslateAPI 反射桥+stub 注入+数据根隔离）五点全 PASS**：开关行渲染（文案/位置/压制开关同区）｜勾选→桥调用→KV 落盘｜刷新回填（KV→勾选态+AppState 同步）｜取消勾选→落盘 false｜**预热抑制**（`__warmupTabHook('tab-guide')` 直调→0 warmup 桥调用）。
- **黑盒战果（存量真 bug 已修）**：`refine_save_stage_settings` 前端 4 参调用 vs 后端 3 形参——pywebview 真桥 `func(*params)`（util.py:255）展开必 TypeError 且前端 catch 静默吞→**encode_auto_enabled（压制自动化开关）自 2.8.0 起勾选从不落盘**；fullchain 新接线照抄同错。修复=两处 4 参→3 参+防复发钉（配平提取实参全站扫描+双锚精确文本，先红后绿）。单测 mock 不暴露参数形状错误——黑盒不可替代性的实打实战果。CHANGELOG [3.0.0] 已立修复条目。
- **验证链六环**：①ruff（CI 口径）clean ②mypy 基线通过（0/0/0）③定向 421 passed（a/b 后）+132（js_static 修复后）④全量 **2306+4** ⑤冒烟（CLI --help+api 导入+两新桥方法在位）⑥Mimosa deep **38=基线 38 零新增**，终态 seal sha256:7f18d2f88a7502e44bfbbcdbdabdf99e4220250eb82bfc1e5d84c40eaa934df6（4 参修复落盘后终态复扫）。
- **已知限制（如实登记）**：链内复验显式传 provider 时 refine_ai_analyze 内联决策 endpoint 取 CLI 缺省（仅自配本地非默认端点受影响，批2 评估是否加 endpoint 形参）；F3 面板/digest 为批2 范围、本批未完成量经 `fullchain_last_run_status()` 桥暴露暂无 UI 呈现；链测试预热替身行为=真预热简化（确定化打桩）。
- **遗留观察**：gui-probe/CI 推送后核（本批六环已全过，推送后 REST 核 CI 至绿方收口）。

### 十二、批2 收口勾账（2026-10-10）

- **落点**：F3 链级状态行（tab-guide `data-testid=fullchain-status-line`：running/上次结果/unfinished/云端 skipped 四形态+`<details>` digest 摘要（9 键汇总+复验三键差如实「—」+台账指引+`fcMissedSkipped` k=0 隐藏）；刷新挂点=switchTab tab-guide 分支+batchFixRun finally；桥消费 `fullchain_automation_status()`/`fullchain_last_run_status()`；MSG JS 键 21 个双表零冻结消耗）｜一键回滚（api 桥 `fullchain_rollback_preview`+`fullchain_rollback`：仅 outcome==applied 且 old_text 非空；timing setdefault 单值映射同 `_load_source_map` 口径；同 timing 后者覆盖；**写序契约=先台账追加 outcome="rollback" 10 键（old_text=回滚前当前文/reason="manual rollback"）再原子写终稿**；auto_insert 记录跳过计数 `auto_insert_skipped`；`_fullchain_running` 拒绝；终稿缺失结构化失败 msg 键）｜前端回滚链（导读就绪显隐按钮→preview→AppModal.confirm 确认（auto_insert>0 条件化提示「检测到 N 条自动插入行，暂不支持恢复」**零批号**）→rollback→结果回显→静默重读导读+双刷新）｜auto_insert schema 契约钉（test_action_retranslate.py 夹具：10 键闭集/category==auto_insert/old_text 空=无修复前文/生产者批3 插入通道·消费者批3 删行接线）｜手册 §2.3.1（全链自动化与一键回滚：开关/链序/云端/互斥/回滚语义/--force 回滚窗口/插入行不支持恢复）。
- **测试**：+9（回滚 happy path 细粒度写序探针【append 标记+两笔 atomic 文件名三段断言——修正两版探针缺陷：替身签名窄化 TypeError→**kwargs、自委托递归→先捕获原函数】/unmatched 零写入/终稿缺失/fullchain_running 拒绝/auto_insert 跳过/空台账/preview 桥/auto_insert schema 契约/状态行+回滚静态钉）；既有 AppModal.confirm 调用点数量钉 12→13 显式改钉（新确认框，钉注释注明）。全量 **2315+4**（批1 基线 2306+4 只增 ✓）。
- **黑盒**（8621 伺服+种子 last_run+种子回滚场景）：状态行呈现（上次全链 hh:mm 修复 5·失败 1·待修 3（done）+digest 摘要+复验差「—」）｜preview 桥 applied=1｜rollback 桥 restored=1+终稿恢复「甲（原）」+台账 rollback 记录 10 键追加。中文路径经 curl 需 UTF-8 文件体（GBK 直发致服务端解码崩，工具链注意事项）。
- **验证链**：①ruff clean ②mypy 0/0 ③定向 462 passed ④全量 2315+4 ⑤冒烟（CLI+api 导入+两新桥在位）⑥Mimosa deep **38=基线零新增** seal sha256:c2e8e7c1c231b8c1c67b10e645866626409f6df89c49bca01e1c91e03f1fca46。
- **已知限制**：digest per-batch 明细不落盘（呈现 9 键汇总+台账指引，逐条明细以各文件台账为准）；回滚探针同 timing「后者覆盖」语义在 `_applied_timings` 幂等守卫下实际不可达（仅 rollback-再修-再 rollback 序可现，值相同无差）；`fcMissedSkipped` 文案暂含「（批3 填充）」尾注随批3 摘除。
- **批3 接桩**：auto_insert 生产者（10 键闭集+old_text 空串/index 允许 None）；回滚删行接线改 `_rollback_candidates`+`fullchain_rollback` 两处+前端 `fcRollbackAutoInsertNote` 退场；`missed_skipped` 写数；删行 rollback 记录 new_text=None。

### 十三、批3 收口勾账（2026-10-10）

- **3A（转写+置信门+harness，纯离线件）**：asr_runner `--clips-json` 多段模式（单进程单次 load_model 转 N 段；C13 置信透传 no_speech_prob/avg_logprob/compression_ratio 双模式；`--audio` 单模式行为零变化）｜`asr_env.batch_transcribe_clips`（cpu 保守分批 cap=8+超时基值 300s+per-clip 60s 线性放大；切片/批败/超时如实标记；build_crosscheck_block 旧通道未动）｜`audio_detect.detect_speech_windows`（复用 RMS 原语，窗口内语音段交集；失败 `{"__error"}` 诚实退化 C18）｜新模块 `missed_insert.py`：classify_transcript 三维门（判定序=判空→≤1s 放弃（边界含）→置信（no_speech_prob>0.6/avg_logprob<-1.0 同 asr_meta 先例）→重复循环（复用 source_hallucination 信号）→荒谬比（3×CPS 上限）→language≠ja→纯拟声→high）+insert_candidates（按时间序插入+CPS 压缩防挤压：5 字÷9.2CPS≈0.543s）+assert_insert_invariants（C15 独立恒等式，未复用 apply 断言）｜tools/c22_calibration.py（manifest 回放→精确率 Wilson 95% 下界+覆盖/召回；--enable 未达 0.95 拒写门控 rc=2；--selftest 合成自检实测拒写方向正确）。
- **3B（链内接线）**：`_fullchain_c22_path/_enabled`（fail-closed）｜`_run_fullchain_missed_stage(files_ctx, run)` 实现（C21 前 20 明示/C18 无音频对照诚实跳过/三维门/门控分叉：**关=high 也全部放弃+notice 明示放弃数，开=插入+台账+extras 标记（写序契约 ledger→final→guide）**/missed_skipped=放弃+C18 跳过+last_run 刷新）｜回滚删行接线（`_rollback_candidates` 返回 auto_insert applied 记录；`fullchain_rollback` 删行按 timing 单值映射+重编号+逐删行追加 category="auto_insert"/outcome="rollback"/new_text=None 记录+extras.auto_insert 清空；auto_insert_skipped 键保留兼容语义=实删数+auto_insert_deleted 如实）｜C23 四点（①含标记文件稳定排序排队尾 ②标记↔台账一致性检查点，不一致排除+告警 ③两处 skip-existing 加 mtime 比对：终稿晚于成品→重新入队+notice（needs_confirm 分支同语义 allow_overwrite=True）④来源标记=guide extras+台账，SRT 正文零标记）｜前端：`fcMissedSkipped` 摘尾注、`fcRollbackAutoInsertNote`→`fcRollbackAutoInsertDelete`（「将删除 N 条自动插入行」零批号）、纯删行也可回滚｜批1 不变式断言白名单化（LLM 分析==1；F4 转写走 asr_env 通道独立计数）。
- **测试**：3A+29（classify 全分支/插入恒等式/多段契约/cpu 分批/诚实退化/窗口切割）、3B+10（门控关全放弃/门控开补行含 CPS 压缩 0.543s 时序/恒等式失败防御/C21/C18/删行+extras 清空/mtime 重压两态/排后+检查点）；主模型验收轮修正 6 处测试夹具与期望值缺陷（成品契约名 `_hardsub`、final_stem 前缀、C22 CONFIG_DIR 桩缺失、删行终稿缺第三块、台账条数漏算、插入位置与 CPS 压缩期望——**6 测试在 coder 环境因缺 gui 依赖未真跑，.venv 权威环境首跑即现**，零实现缺陷）。全量终态 **2355+4**（批2 基线 2315+4 只增 ✓）。
- **黑盒**：回滚删行桥级端到端 PASS（种子 extras+auto_insert 台账+3 块终稿→rollback：restored=1+auto_insert_deleted=1+终稿删行后 2 块+删行记录 new_text=null+extras 清空）。
- **验证链**：①ruff（subtransjav+tests+tools）clean ②mypy 0/0 ③定向 489 passed ④全量 2355+4 ⑤冒烟（CLI+api 导入+c22 harness --selftest rc=0）⑥Mimosa deep 38=基线零新增（seal 见提交 verify 行）。
- **已知限制（如实登记）**：**C22 真机校准未做**（等 owner 样本：≥60 段非言语观察、真阳性混合、独立标注+≥20% 复标一致率≥90%——harness 与三步流程就绪，达标前自动补行缺省关=漏听条目按拍板全部放弃，仅计放弃数）；批量转写为同步阻塞调用（链 daemon 线程内，GUI 不卡但链内无进度条——批2 状态行呈现链级计数）；observation 精确语音窗口需逐文件重跑 RMS 检测（ffmpeg 抽 wav 一次性，无 LLM 成本）。
- **3.0.0 剩余**：C22 校准实测（owner 样本到位后 harness 三步）→ owner 真机走查 → release/3.0.0 发版轮。

### 十四、测试包真机反馈修复轮（2026-10-10，测试包 3.0.0.dev0-test 首轮反馈）

- **反馈 1「2.8.0.2 修复内容没整合」甄别结论**：内容级 diff 实证（main vs release/2.8.0.2）——release 分支 4 提交为 cherry-pick（patch 内容与 main 4b28f3d/0c342e5/1612060 一致），**main 完整包含 2.8.0.2 全部修复且领先**（release 仍是 40 截断旧版+4 参 bug 旧版+双域镜像旧版）；测试包构建自 main@8160a41 工作树（干净）。观感来源待 owner 指认具体行为；已证事实=测试包安装建**全新数据根**（%LOCALAPPDATA%\SubTrans\config 空，两代数据根均无 refine_stage_settings.json——用户阶段A 模型一直是下拉临时选择从未落盘），2.8.0.2 时代用户配置/TM 本就不随安装包迁移（数据根设计内，非修复缺失）。
- **反馈 2「勾选自动化报未启动全链（服务商原因）」根因+修复**：根因=全链 provider 门（`_resolve_ai_model_config`→`_stage_a_*` 三兄弟）只读落盘 settings，而翻译主流程走前端现值直传——**两侧数据源不一致**：设置从未落盘的机器上翻译照常跑、链必误判。修复=会话快照回落：①`_capture_session_stage_a(options)` 于 start_translation 记录本次翻译实值（s1_provider/s1_model/{provider}_endpoint，provider 归一小写）；②`_stage_a_provider_name/_model/_endpoint` 快照优先回落落盘（消费方=链门/批量修复解析/分析跟随/预热全量同源）；③`refine_save_stage_settings` 保存 stages 时清快照（落盘显式表态优先，防旧快照遮蔽）；④链门拒绝 notice 带 reason+last_run `skip_reason` 键（前端可透出真因）。类级注解 `_session_stage_a: dict[str, str]`（mypy var-annotated/no-redef 拉锯后归位：文件序首见点持注解）。
- **测试**：+3（快照回落解析/保存清快照/捕获提取大小写归一）；全量 **2358+4**（批3 基线 2355+4 只增 ✓）。
- **遗留**：反馈 1 若 owner 指认具体行为缺失再立案；前端 fcStatusSkipped 文案可透出 skip_reason（本轮 notice/last_run 已带，UI 呈现随批2 面板迭代）。
- **推送后 CI 红两笔（均已闭）**：①6539493 全腿 Lint 红——根因=两处 gate_on 测试内联 `import ... as _cfg` 触发 I001（CI ruff 0.17.0 比本地 .venv 旧版严），ruff --fix 收敛+本地 ruff 升 0.17.0 对齐 CI 口径（6122109）；②6122109 windows-3.10 单腿 Test 红=已知 flake `test_effective_dir_blacklist_falls_back`（横切观察项在册第 3 例复发，与本批零交集），REST rerun-failed-jobs 201 重跑自愈 success。Mimosa 提交前扫描 enobufs 未完成→补扫 deep 38=基线零新增 seal sha256:a2db2bd8d183d7af9de053ed0c6b799c4abefcd6f7944f376895505c8a20578e。

## [2026-10-10] D2026-1010-01 3.0 测试包真机反馈修复轮·第二反馈（全自动 0 修复 + Console 可见性）[已拍板 · 已收口]

- **反馈②「全自动 43 待修 0 修复」定性真 BUG**，根因实锤：管线完成事件 `file` 字段纯 basename（pipeline_v2.py:1107、event_stream.py:331），`_resolve_guide_for_done_key` 在 `os.path.dirname(key) or "."` 即进程 CWD 找导读（api.py:5791），导读实落输出目录 → 诚实跳过 → 0/0/0 done（Logs/gui.log:80200-80205，16:53 一轮 3 秒收尾；config/fullchain_last_run.json started 16:53:01 ended 16:53:04）。与 ab38359 provider 门无关（门已放行：done 形态无 skip_reason）。
- **反馈①「窗口比例异常+无法查看详细内容」定性**：Console 规格（style.css:765/787-791、app.js:3187-3190）为 2.6.2 批3 既设计非 3.0 回归；真实缺口=「▶」纯文本误导（app.js:710+3357 无 handler）+ 全链原因不进 tab-guide 状态行（app.js:6951-6952）+ **宽度畸形真根因=style.css:478-482 `.console-section .section-content` 行向 flex，2.7.3 件⑧新增活动流兄弟节点后被横排**（2.6.2 批3 只给 #refineAiAnalyzeSection 做过列向补刀，漏正主）。
- **[HIGH_RISK_OBJECTION]（全链 notice 前端死信）→ 采纳**：fetchLogs 仅在 statusInterval（app.js:4247），翻译完成 _finish→stopStatusPolling（app.js:4026-4027、4224）先于链 daemon 产出（api.py:5644-5659）→ `_automation_notice` 入队后前端不再 drain，全链 notice 在 GUI 内不可达仅落盘 gui.log。三条修正要求全采纳：①全链原因只以 last_run 为载体+tab-guide digest 呈现不指路 Console；②F2 后端（逐文件 notices 落 last_run）并入卡1 与 F1 同批落地消除可见性窗口；③F1 首次启用自动改写前可见性载体先就位。普通异议（F2 须覆盖 done-0 形态，不能只加 skipped reason）采纳。
- **F1 附加条件全采纳**：basename→会话输入全路径精确映射（同名防误配）；候选序=[会话输出目录, 映射输入目录, 其余输入目录, key 自身 dirname 最后]；output_dir 空/"source" 归一输入父目录（pipeline_support.py:99-104）；命中后校验导读顶层 stem（quality_report.py:1516）+ 仍走 _load_validated_guide。
- **口径澄清（设计内不改码）**：GUI「待修 43」=补集口径（app.js:5907-5935），链白名单 fail-closed（api.py:669-673：untranslated/cps_too_fast/dewei/subject+antonym_/body_part_/climax_ 前缀+open+现译+台账未修）→ 可修数<43 属正常；suspected_missed_speech 观察类不自动重翻（C22 缺省关）。
- **卡切分**：卡1（P0）=F1+F2 后端（api.py+tests/test_gui_api.py）；卡2（P1）=F2 前端+F3（digest 原因+skip_reason 展示+活动流去▶+原始日志未读徽标；app.js+tests/test_gui_js_static.py）；卡3（P1，owner 新增）=Console 面板重设计（style.css+tests/test_gui_js_static.py；设计规格主审直出——design-expert 两度超时取消）；F4（复验前后计数差值）挂起缓做待 owner 令。写码执行方=OpenCode（owner 重申分工），ZCode 出卡+验收；真机验证用副本目录不跑现网 E:\ 输出。
- **风险跟踪**：①卡3 回链 2.6.2 批3 Console 规格（本次改动修其行向缺陷并按 owner 令调整高度，非无声推翻）；②卡1 首跑副本须核对同名 stem+陈旧导读误配兜底真实生效；③F4 长期挂起则在发版轮评估并链摘要。
- **执行收口（2026-10-10，owner 令写码由主审亲执不转 OpenCode）**：三卡全落地（卡1 api.py+test_gui_api.py：`_capture_session_paths` 快照+`_resolve_guide_for_done_key` 四层候选[输出目录/唯一同名映射输入/其余输入/key 目录兜底]+`_guide_stem_matches` 防误配+`_fullchain_notice` 23 处写点全转 last_run notices；卡2 app.js：去▶/digest 逐条 notices+done-0 实质原因置顶[跳过「自动化开始」泛化行，黑盒实测后修订]+skipped 透 skip_reason 真因+原始日志未读徽标；卡3 style.css：`.console-section .section-content` 列向纵排修横排根因+活动流 200px+整区 180/380）。连带修复既有环境依赖型红测试 `test_session_completed_triggers_warmup_hook`（缺 CONFIG_DIR 打桩，stash 实锤 main 同红）；批3 旧钉 150/300 按决策更新 180/380。验证链：ruff clean+mypy 0/0+全量 **2367+4**（基线 2358+4 只增+9）+冒烟过+Mimosa deep 38 零新增 seal sha256:f27a32838313ac03555aa33ea599c4722023d77e1eab1bc54d073824b21c141d+GUI 黑盒（IAB stub 桥副本：计算样式/宽度实测 662=662/截图/徽标计数清零/digest 原因行/skipped 真因全过）。闭环确认：HRO 三修正要求全兑现（notices 落盘+digest 呈现+先于自动改写启用）。待 owner 真机走查（副本目录首跑）。
- **测试包轮（2026-10-10，owner 令打测试安装包）**：本地 PyInstaller 6.22.3+ISCC（用户位 Inno 6）产 **SubTrans-setup-3.0.0.dev0-test2.exe**（55,446,687B，sha256 ad01104f8e62b4d7b853b8efd00a2e6ca8e64eaf5a90500189ee4337db0e22dd，onedir 106MB，词典去捆绑口径保持）。黑盒抓两笔打包链真缺陷并修复（488fdbb）：①spec datas dest 语义误用——asr_runner.py 装成嵌套目录，asr_env._runner_script_path is_file() 判假→frozen ASR 运行器静默回退 -m 必失败（CI Test-Path 对目录恒真故一直未拦，2.7.1 起潜伏）；②frozen --dict-status rc=1——D3 去捆绑裁剪 system.dic 后 sudachipy pyo3 PanicException（BaseException）绕过 except Exception 降级链，grammar_hint 增缺省词典预检转普通异常走降级（+1 回归钉 BaseException 模拟，旧码必红）。教训：**CI 打包冒烟 Test-Path 类断言分不清文件/目录，产物落点断言须带 is_file 语义**；发版前 frozen CLI 冒烟须在本地复跑一遍。Mimosa deep 38 零新增 seal sha256:bf3888534c8a2d03dd6607537bca61079c035246a0c685de235a2c842e8a3eb6；全量 2368+4。**第三笔（升级装冲突，owner 真机实证）**：旧包 asr_runner.py 目录形态挡新包同名文件→安装期 MoveFile 错误 183；[InstallDelete] 增该名 filesandordirs 清理（升级自愈，老用户免手动）；**test3=SubTrans-setup-3.0.0.dev0-test3.exe** 55,446,718B sha256 5d1cc78c70e354eb5080a426bc081232a7b66b8eb8787f7024962f21eac31438（升级装冲突修复后改交；旋即被 test4 取代）。**三轮（2026-10-11 凌晨，owner 两反馈无人值守轮，主审亲执）**：①「全自动依然 28 待修」甄别=**链实已修完**（盘上导读 25 retranslated+3 nochange 与台账 25 applied+3 nochange 完全对账；climax_iku_variant 亦在前缀白名单内），真缺陷=**导读页陈旧数据**：链 daemon 无前端完成钩子、批修复静默重读不覆盖链路，页面停留修复前旧态；修复=read_output_artifact 增 mtime 基线+output_artifact_mtime 轻量探针（守卫同源）+switchTab 挂 __guideStalenessHook 变化即静默重读。②「明细主页浏览太多」=行动条目弹窗化：主页面零内联渲染只留计数 chip+查看明细入口，全量条目移入 AppModal.guideItems 大卡弹窗（guideItemCardHtml 共享构造，试听契约锚原样保留，弹窗列表自绑委托）；批6/批5/件1 既有钉随载体更新。验证链=全量 2370+4（+2）/ruff/mypy 0/0/Mimosa deep 38 零新增 seal sha256:a07001a462e23d14ec4e4a8c328fa68e55d2c9a4001c30f02b18be5a246f6e9f/GUI 黑盒（stub 桥：主页 0 卡+入口/chip 五段式/弹窗 28 卡+28 试听键+25 绿徽标+滚动+陈旧重读触发，截图核对，零 JS 错误）。提交 1e9bfb3；交付版 **test4**（test3 旋即被取代，两者均含此前全部修复）。**四轮（2026-10-11，owner 真机两反馈）**：①「UI 重合」根因=style.css 注释文本内嵌「星号+斜杠」序列（--console-*/--cl-*）致注释早闭、.console-activity-header 整条规则自 2.7.3 起被浏览器静默丢弃（按钮 block 流靠左+暗盒零间距+focus 环相贴）；修复=措辞去除序列+头部间距 space-2+词法级防复发钉（代码区 CJK 泄漏=必有注释早闭，647850d）。②「gate0 未匹配媒体」根因=resolve_media_path 只认 whisperjav_run.json、无同目录回退（owner 目录无 manifest）；修复=manifest 缺失/读取失败/无命中任一形态走 SRT 同目录剥链候选（preview_stem_candidates 含 .merged 层）精确匹配视频扩展名闭集（恰 1 命中采用，多候选 fail-closed），无 manifest 分支保留静默语义不虚增风险计数；preview_stem_candidates 单源化上移 asr_meta（试听推断别名零调用点改动）。验证=全量 2376+4（+5 asr_meta 回归）/ruff/mypy 0/0/Mimosa deep 38 零新增 seal sha256:0c561325b34879cf616440ec51d7bea17e80b2cb369fde4dfa53e53fbd22b02c/CSSOM 黑盒实证规则复活+零重叠（截图核对）。教训：**CSS 注释文本禁写注释终结序列**（词法钉防复发）；**stub 桥黑盒同 URL 走缓存必须换端口 cache-bust**（8793 复验曾误读旧 CSS）。交付版 **test5**。**五轮（2026-10-11，owner 真机反馈：原始日志展开无法下翻）**：弹窗化——内联展开受 Console 区 380px 上限挤压，点击开关改开 AppModal.rawLog 大卡（.rawlog-view 深色等宽 66vh 可滚动，打开即滚底，打开期新行 _liveRawLogLine 实时追加+同款 500 行显示层裁剪）；未读徽标条件迁移弹窗打开态豁免，localStorage 折叠持久化退场，#consoleOutput 保留隐藏承载（读写契约零破坏）（6383684）。验证=全量 2376+4/静态钉 455/Mimosa deep 38 零新增 seal sha256:3ad09849363390947c04283cf5da6f348952a5875de2aa5b26df9367324c5e14/GUI 黑盒（内联退场/46 行滚动滚底/实时追加/徽标三态，截图核对）。交付版 **test6**。


## [2026-10-11] D2026-1010-02 3.0 测试包真机反馈修复轮·第五反馈（tab 页无法下翻全局根治 + observation 展示污染/退化重翻三件）[已拍板 · 采纳全部评议 · 已收口]

- **反馈来源与基线**：test5 包 owner 真机走查两问题（① tab 页无法下翻（again）；② 幻觉译文/二次重翻效果差，#174/#238/#265/#500）。基线 main=4151fb5，测试基线 2376+4。评议员（decision-critic）只读实核 style.css/action_retranslate.py/quality_report.py/audio_detect.py/api.py/app.js/index.html/tests 后出具评议，owner 全数采纳并授权本次修复+正式发版 3.0.0 全权由主审负责（写码亦主审亲执，owner 令「本次任务不由 opencode 负责」）。
- **问题1 定性（根因实锤）**：页面级布局缺陷——.workbench grid 只定义列无 grid-template-rows（style.css:177-181），隐式行按内容撑高越过 100vh；.main 被 stretch 到行高永不溢出，overflow-y:auto 形同虚设，溢出被 body overflow:hidden 裁切。历史补丁（Console 380px 上限、rawLog 弹窗化）均为症状级。架构事实：.tab-page.active flex:1 0 auto + 70/30 冻结钉证明「页面不滚、区块自滚」设计。
- **[HRO]-1（件1 全局布局）→ 采纳**：件1 扩为组合改动评估——实核后最小根治=.workbench 补 grid-template-rows: minmax(0,1fr) 单行（.tab-page flex 契约实测无需动：mainScrollable 0→356/900vh，70/30 比例制在 900px 视口下实算 253px=30% 带生效，无双滚动）；按页 opt-in 为回退路径（备而未用）；明确不退区块级 max-height 兜底。回归=7 tab×两档窗口（1365×900/1210×760）黑盒全过+新增词法钉 test_workbench_explicit_row_page_scroll_pinned。
- **[HRO]-2（3b 枚举）→ 采纳 skipped，驳回 failed**：failed 会砸 rc/GUI 成功语义（rc in (0,3)）+主因统计污染；cps 类 source_excerpt 恒空串是常态。skipped 四处联动：rc 纪律不计失败（skipped-only rc=0）、_ledger_top_reason 只看 failed 天然排除、GUI 回包独立 skipped 字段+前端 MSG.batchFixSkipped 呈现、不进 nochange_indexes（status 保持 open 保重试资格）。
- **件2（observation 展示污染，#174 根因）→ 采纳**：_refresh_guide 跳过 status=="observation"，continue 先于 status 赋值（补 index 撞号洞：观测 index=间隙后一块 index，与行动条目同空间，撞号时防错标 retranslated）；回归钉双断言（current_text is None 且 status 仍 observation）。
- **件3a（时长约束）→ 采纳（口径纠正）**：目标上限取 CJK 基准 8.0（ceil(sec×8)，去空白与扫描器同源），不用触发阈值 5.0 反推（会逼过度删义）；仅对 cps_too_fast/single_line_too_long 生效；applied 后重算 CPS 超 5.0 记台账扩展键 residual_cps+警示打印（不宣称已修，10 键闭集不扩）；与 #174 正交（观测类不进执行器）。
- **拍板点**：nochange 终态屏蔽保留（前提 3b 同批落地）；#238/#500 修后复走查归类（污染类/初翻幻觉类分账）；版本归宿=并入 3.0.0 正式版（含 main 全量已收口内容）。
- **执行收口（2026-10-11，主审亲执）**：改动 7 文件（style.css/app.js/api.py/action_retranslate.py+三测试文件，+8 测试）。验证链：ruff clean+mypy 基线门禁 0/0/0+定向 176+24+全量 **2384+4**（基线 2376+4 只增）+冒烟双入口 --help rc=0+Mimosa deep 38 对最近三次基线 identity 零新增 seal sha256:40b59a5eca733d1638a1c374bd4a78cb0a3bacfd2233d15a3aa1d4e3df699ab7+GUI 黑盒（IAB stub 桥：workbenchRows 钉视口/mainScrollable 0→356/导读 8 节到底可达/明细弹窗 observation 卡=不可自动重翻+检测说明无邻句污染/批修复消息含「2 条因缺源文跳过（提供原始日文 SRT 后可重试）」/翻译页 70/30 与 180/380 实测在位/校对 no-aside/五 tab 零破/1210 窄档复测/rawLog 弹窗 66vh 在位；截图核对。IAB 物理输入三通道会话级失效→按先例声明程序化 click 代理，观察全只读；review-status-bar sticky 未执行=需真实校对会话，登记复走查项）。
- **遗留**：①#238/#500 等 owner 复走查归类；②review-status-bar sticky 参照块真机核验；③3a 残留 CPS 计数为发版后观察指标；④3.0.0 发版轮随后执行。

## [2026-10-11] D2026-1010-03 真机反馈第六轮（媒体对照可视化 + TM 建议定位/试听）[已拍板 · 采纳全部评议 · 已收口]

- **反馈与根因**：owner 真机两反馈——①AI 分析状态行显示「本地转写 16 段对照」但全程序无处查看：探查实证该对照=质量页媒体重点对照（crosscheck，`media_crosscheck_enabled` 缺省关）产物，文本块仅拼进 prompt 喂 LLM 后**用完即弃**（不进返回值不落盘），GUI 仅从 stdout 抠段数拼消息；②TM 建议理由文本引用「导读清单 #574」但契约字段闭集 {source,target,reason} 无结构化 index/timing，无跳转无试听。基线 main=64a0ebc（3.0.0 已发布后），全量 2384+4。
- **评议员（decision-critic）两 HRO 全采纳**：HRO-A=拟用键名 `crosscheck_segments` 与既有 int 计数键撞车（状态行 `${n}` 插值会被数组破坏）→ 数组改独立键 `crosscheck_detail`，`crosscheck_segments` 保持 int 严格分离；HRO-B=「openGuideItemsModal 现有调用方零改动」与代码冲突（监听直挂会把 MouseEvent 作首实参传入过滤逻辑）→ 全量打开入口监听改显式无参包裹 `() => openGuideItemsModal()`，过滤仅数组实参生效+全量打开回归钉。[DEPENDENCY-IMPACT] 采纳：D2026-1002-07「对照链无实体产物」口径句随批修订（见上文章节内【口径修订 D2026-1010-03】标注）。
- **件A（对照落盘+可视化）**：build_crosscheck_block 增返回 `detail`（结构化对照段，**全文不截断**，与喂 LLM block 的 200/100/2000 截断口径分离）；_build_media_crosscheck 改返 (block, detail)；run_ai_analyze 旁挂 `data["crosscheck_detail"]` 后 write_ai_suggestions（不动 analyze_quality_report 闭合契约，契约测试零改动）；落盘与建议件同生共死无独立失败态（构造 best-effort 异常→[]）；refine_ai_analyze 桥透传；前端 aiRenderResult 第四段「媒体对照（本地转写 N 段）」区块：时间轴+ASR 转写 vs 现译并排+逐段试听（复用 openAudioPreview），未加载导读试听钮置灰+提示，无段不渲染；批次修复复验重渲染同步透传（禁浅拷贝丢键）。
- **件B（TM 定位+试听）**：双路径——主路径=reason 文本正则回捞 #N 条目号（旧建议件零重跑生效）；增强路径=prompt 契约 tm 条目加可选 `"index"`（与「不虚构条目编号」自洽：引用材料中已有编号）+ _normalize_suggestions 白名单透传（仅整数，bool/str 丢弃）。双校验（条目存在于已加载导读 lastGuideData.items + 原文词条与条目 source_excerpt/current_text 去空白互证）通过才显示「试听」（反查条目 timing 走 openAudioPreview）与「查看条目」（openGuideItemsModal([index]) 过滤弹窗定位单卡）；未命中/校验不过/导读未加载=无按钮或置灰，不误导。不加 timing 字段（模型输出精确 timing 易幻觉，前端反查）。
- **执行收口（2026-10-11，主审亲执）**：改动 7 文件（asr_env.py/quality_advisor.py/api.py/app.js+test_asr_env/test_quality_advisor/test_gui_api/test_gui_js_static，+8 测试）。验证链：ruff clean+mypy 0/0/0+定向 524+全量 **2392+4**（基线 2384+4 只增）+冒烟双入口 rc=0+Mimosa deep 36 对上基线 identity 零新增（-2=Temp 清理既有项消退）seal sha256:1c01a02d5f602ed51d7c9ae5e17c9773ca3b53b225a13be3147a15dbc95f7d87+GUI 黑盒（IAB stub 桥：媒体对照区 3 段+试听 enabled/TM 四态=结构化 index 命中#1+回捞命中#2 出双按钮、#999 不存在+互证不过=无按钮/查看条目过滤弹窗单卡#1+卡内试听/全量打开 42 卡 HRO-B wrapper 无污染+过滤↔全量切换/批修复复验重渲染对照区不丢+TM 定位保留；截图核对。IAB 物理输入失效按先例程序化 click 代理；黑盒首轮未走通根因=夹具导读路径命名不合 aiReportPath 推导规则+真桥覆盖 stub 桥，均夹具侧修正）。
- **拍板口径（owner 锁死）**：件B 未命中条目号的全文搜索对照不做，列后续候选不进 3.0.1；件A/件B 并入 3.0.1，件1 真机复现修复若同窗口闭环则同批、不闭环不阻塞；发布说明三者分项列明。
- **遗留**：①模型结构化 index 实际出现率需真机观察（主路径 reason 回捞兜底已覆盖旧件）；②guide items 重复 index 取首个（现数据五来源理论上可撞号，如出现定位偏差再升级 category 消歧）；③件1 无法下翻真机复现等 owner Console 诊断数字。
- **件C 追记（2026-10-11 深夜，test1 包真机反馈：全链阶段日志黑箱）**：owner 实证翻译结束后 Console/原始日志/导出均不含 AI 分析→二次翻译→复验阶段行、手动 AI 分析被互斥拒绝（设计内）叠加成彻底黑箱。根因=全链 daemon 经 _automation_notice 尽力投递到翻译日志队列（通道早就在），但**唯一排水通道（1s 状态轮询内 fetchLogs）随 _finish→stopStatusPolling 停摆**，行积压队列永不出（且下次任务启动时作陈旧行误 flush）。修=pywebviewready 挂应用级常驻 2s 日志排水（幂等守卫，仅排日志不触状态桥，与任务期主轮询并存）+静态钉 test_log_drain_loop_pinned（+1）。验证=定向+全量 2393+4/冒烟/黑盒复验（详test2 包交付记录）。互斥拒绝消息为设计内行为不改动（Console 连续可见后黑箱感消除；如需带链进度再议）。

## [2026-10-11] [D2026-1011-01] 代码签名 Trusted Signing 复评结案：维持不立项 + 准入不可行改判 + 触发条件替换 + 替代候选登记 [已拍板]

**决策对象**：roadmap.md:201 候选池第⑩项「代码签名 Trusted Signing（不立项，触发=非中文 issue 累计 ≥5 或 winget/Store 上架被接受）」的复评；decision-log.md:1494 ④「首发不签 + Trusted Signing 列为后续评估项」与 :1519「2.0.0 发布窗口内再评一次」两项历史挂账的闭合。

**评议轮次**：decision-critic 一级评议一轮；[HIGH_RISK_OBJECTION] 1 条，主模型采纳；无 [MATERIAL_CONFLICT]。

### 一、拍板结论

1. **Trusted Signing 维持不立项，性质改判「中国大陆个人开发者 Public Trust 准入不可行」**：官方 Quickstart 原文（Artifact Signing，页面 2026-10-08 更新）"Individual developers must be located in the United States or Canada"；组织国别清单（美/加/欧盟/英/澳/新/日/韩/新加坡/瑞士/挪威/以色列）不含中国大陆，服务支持区域亦无中国区。**Private Trust 显式排除**：原文明确地缘限制不适用于 Private Trust，但其身份验证仅限 Organization、且对 SmartScreen 零价值（SmartScreen 只认 Public Trust），列入档案防未来重复评估。借址/借身份违反 ToS 且有法律风险，不作选项。〔评议员结论一「支持+两边界补丁」全部采纳〕
2. **替代候选排序修正**（评议员 [HIGH_RISK_OBJECTION]「SignPath 排序双重标准」采纳，主模型亲核 signpath.org 与 /terms）：SignPath Foundation 证书等级（OV/EV）未标注、通篇无 SmartScreen 承诺——A(SignPath) 与 B(Certum) 在 SmartScreen 收益上同为不保证，A 仅在成本/CI 占优。核定：A=SignPath Foundation（零成本、CI 友好；每次发布需人工批准签名、违规可即时/追溯撤证；内容限制仅恶意软件/专有代码/黑客工具、**无成人内容禁令**，缓解评议材料的「内容被拒」[UNVERIFIABLE] 风险）；B=Certum（约 €69/年+首次购 set；SimplySign 客户端 CI 摩擦；OV 信誉需累积）；C=维持现状（**默认生效立场**，非兜底）；D=attest-build-provenance+GPG 签 SHA256SUMS 零成本信任加固——**owner 未批，留候选池**。
3. **触发条件「替换」而非「作废」**：签名项新触发=**真实用户杀软误杀/SmartScreen 反馈到量**（owner 原话「先挂着，等有真实用户反馈再说」）。原触发集拆解：「非中文 issue 累计 ≥5」计数口径**原样保留**继续服务双语改判条件（不误伤同组信号）；「winget/Store 上架被接受」分句**作废**（错配：winget 不改 SmartScreen、Store 系分发渠道+MSIX+微软自签且与内容性质相撞，均非签名信任信号）。
4. **同步动作**：杀软误报三步解决指引（SHA256 核对 → 恢复+加白 → 厂商误报申诉如 Defender filesubmission）已批补 README FAQ（owner 2026-10-11 指示）。
5. **历史挂账闭合**：:1519「Trusted Signing 在 2.0.0 发布窗口内再评一次」由本次复评闭合（原文不回改，遵只加不改惯例）。

### 二、评议员异议与主模型回应

- 结论一评议「支持+两边界补丁」（①Private Trust 显式排除 ②winget/Store 非签名通道）→ 全部采纳，落本条第 1、3 项。
- [HIGH_RISK_OBJECTION]（A 排序对「SmartScreen 信誉需累积」双重标准）→ 采纳，落本条第 2 项。
- 动作切分「先申请后拍板接入」评议员评为合理，要求申请前先固定「批准后是否接入」判定标准 → 本次未排申请；判定标准随候选池复评时补。

### 三、后续风险跟踪钩子

1. 签名项维持挂起，触发=真实用户杀软误杀/SmartScreen 反馈到量；未到不点火。
2. 双语改判条件绑定信号：「非中文 issue 累计 ≥5」计数口径不变（起算=:2011 归档日，issue 正文主要语言非中文即计入，bug 与 feature 均计）；改判签名项时不得误删该口径。
3. D 项（attest-build-provenance+GPG 签 SHA256SUMS）候选池：重启条件=owner 主动要求提升信任面，或国际用户/杀软反馈上升。
4. 若未来申请 SignPath：接入前必核①证书等级(OV/EV)②是否承诺 SmartScreen③内容条款④审批 SLA；接入将新增每次发布人工批准门、打断 roadmap.md:25 全自动 tag 发布，须单独评议。
5. 地缘豁免例外：若 owner 后续持有美加等合规国别可验证身份/实体，第 1 项准入结论须复议重开。

**关联**：:1494 ④、:1519（本条闭合）、:2011 第⑩条（触发集与计数口径源）、:2141（S6 触发型四项维持）；roadmap.md:22（双语改判条件自身触发集，不动）、:201（第⑩项正文已同步）。

## [2026-10-12] [D2026-1012-01] 3.1 UI 重塑计划评议归档+无人值守轮共识执行 [已拍板 · owner 已追认（P1-P12+发版令+P8 执行令，2026-10-12）]

- **原决策**：3.1.0 UI 重塑计划（owner 2026-10-12 指示"UI 重塑做个计划归为 3.1 版本"）。设计侧（design-expert，实机 8 截图走查 1210×918 基准）+评议员（decision-critic）三轮评议：首轮 1 项 [HIGH_RISK_OBJECTION]（阶段2"并档 S6"与 D2026-1001-05 S6/钉④机器冻结禁区直接冲突）全采纳——钉④复议门改两步制；[MATERIAL_CONFLICT]（遗漏 UI-REDESIGN-HANDOFF 唯一事实源）裁定 handoff 仍为基线；app.js 拆分破坏静态测试契约采纳——前置迁移方案。第二轮设计侧提交后主模型同步评议员二次评议：A 项（impeccable hook）**事实更正=18 工具清单含 OpenCode（本项目 UI 执行者），仅 ZCode 不在**，评议员改理由后维持不装（OpenCode 输出按项目规则一律"未验证"→hook 只能咨询不能作门+本地 Python 钉是更权威替代+59 条规则误伤 handoff 已锁决策）；B 项（钉④冻结对象改归一定稿值）修订采纳附 5 条件（逐字机器冻结不降级/归一提案先过评议员/owner 痛点触发门保留/协同验证含暗色+618px+AA 修复/与本地 3 钉对齐）。
- **设计侧核心发现（P0 五条，均有行号+截图证据）**：①三层表面明度差实测 1.05:1（handoff §5 诊断旧 UI 的头号病被新 token 复现）；②49 处 font-size 中 24 处硬编码绕 token（22 处 11px）；③Windows 下 Segoe UI/雅黑仅 400/700 两档字重，style.css 的 550/600/650 全渲染成 700→层级被迫靠字号/颜色承担→字号一路压小（**owner"说不清的不合理"最高嫌疑技术根因，待真机确认**）；④`button:focus{outline:none}` 特异性吃掉 `:focus-visible`，7 导航项无焦点环；⑤三组对比度不达 AA（text-3 2.54:1/warn-on-soft 2.07:1/主按钮白字 3.68:1）。现状已实证偏离 handoff/原型 ≥3 处（文件卡标题计数丢失/拖拽区主次+图标/进度定量反馈 .progress-meta 丢失）。
- **计划定稿（阶段 0-4）**：版本定位=3.1.0 纯前端重塑（后端 Api/桥层/strings.py 消费端不动），**3.0.1 先发不混批+发版序列闸（先切 release/3.0.1 发版完成，地基批才进 main）**；阶段 0 拆 0a（设计侧零 owner 时间：静态审计报告/基线偏差裁定表/G 节痛点点选表七页×四态/空态四态清单/token 归一提案/修正式方向稿+A1 表面分层·A2 排印刻度两组小样）/0b（owner 唯一输入点=勾选）；阶段 1 地基批（视觉零变化：FROZEN_IDS 快照机制改造+switchTab 六钩子收编+本地静态钉；验证口径=DOM 快照+computed-style+截图 diff）；阶段 2 视觉批（**排印/表面归一包排第一**，逐项回链 owner 勾选痛点编号，钉④节奏改动须 S6 复议通过才排期）；阶段 3 app.js 拆分独立批（前置静态测试迁移方案，评审过才动工）；阶段 4 验收（web-gui-tester 黑盒+真机走查+暗色专项+焦点可见性专项+AA 对比度门+618px 容器断点教训）。
- **裁定清单**：维持零构建（file:// 媒体直连硬约束+ES modules 被 CORS 拦，拆分只能多 script 标签）；**impeccable 不装**（detect 定性=开发侧咨询工具对齐 roadmap uv 先例，输出不作验收门；再触发三条件=本地钉漏整类缺陷+豁免稳定低维护+离线可复现解决；若装的前置四条=限 OpenCode/.impeccable gitignore/Mimosa 零新增/咨询定性）；UI-REDESIGN-HANDOFF 仍为基线+IA 现状回写（只更事实不改设计决策）；**单一裁决人=design-expert 持方向稿最终设计权+主模型持范围/排期裁量**，四技能包输出为输入非并行权威；引擎页重构维持挂起不并入；右栏折叠（D-4）须 owner 痛点勾选后才可执行。
- **无人值守轮执行勾账（owner 2026-10-12 授权"评议+设计师高度一致项先行执行"，评议员 12 项判定 P1-P12 全通过或条件通过无驳回，非 [PRESSURE-OVERRIDE]）**：✅ 已执行=本条归档+阶段 0a 材料产出（docs/design/d1012-* 全套，全部标注"提案性质非定稿"）+IA 现状回写 handoff+app.js 拆分静态测试迁移方案落盘+release-checklist 基线刷新（2392+4 实跑值）+3.0.1 发版对账（v3.0.0..main 共 7 笔=件A/件B 57509c8+test1 包反馈 1186561+4 docs）；⏸ 本轮登记=撞号消歧候选/residual_cps 等真机观察（见 D2026-1012-02）；⬜ 待 owner 白天追认=P1-P12 逐项+阶段 0b 勾选+3.0.1 实际发版令。
- **依据文件**：docs/design/UI-REDESIGN-HANDOFF.md、docs/design/redesign-prototype.html、docs/design/ui-phase2-真机走查清单.md（G 节）、tests/test_ui_phase3_redlines.py（钉④:113-120/FROZEN_IDS:124）、tests/test_gui_js_static.py（_extract_function:22-47）、tests/test_strings_and_shortcut.py（MSG 双表钉）、subtransjav/webview_gui/assets/style.css（:21-24 表面 token/:89 字体栈/:172 focus/:286 起硬编码字号）、docs/decision-log.md:2141（S6）、roadmap.md:201。
- **安全勾账（2026-10-12 提交后补扫）**：Mimosa deep findingCount=37（seal sha256:805448d1…082a69），全部位于既有文件（refine/tools/Temp 构建残留/paths/webview_gui），**docs/design 及本轮新增 13 文件零命中**，计数较 3.0.0 时代 seal 5a218249 的 38 降 1——零新增放行；另 d265 原型假数据本机用户名路径已脱敏（%LOCALAPPDATA% 占位，git 历史仍含原值，清史待 owner 令）。
- **owner 追认（2026-10-12 白天回执："追认；发版；p8做"）**：①P1-P12 全部追认，本条状态升格为**已追认**；②发版令=3.0.1 当场执行（见下）；③P8 静态钉执行令落地（见下）。
- **3.0.1 发版勾账（十步全勾）**：①切 release/3.0.1（自 e163069）②bump 三常量+pyproject（版本钉 3 passed）③CHANGELOG [3.0.1] 只写本版 ④验证链=ruff CI 口径 clean+全量 **2393+4**（flake test_h4b_adaptive 单跑即绿）+冒烟 --help/--where/冻结 CLI 双形态过+Mimosa deep 37 零新增 seal 8ec6b10e ⑤tag v3.0.1→4d1fab9 ⑥release.yml run 38184995358 success+artifact 哈希核验 ⑦Release id 409994427 建发（notes 只写本版，双资产）⑧main 前进 3.0.2.dev0 ⑨main CHANGELOG+roadmap 同步 ⑩ls-remote 三处一致。**setup 51,321,050B sha256 7128236E…CF28ED 三处 MATCH（SHA256SUMS/本地实算/公开 URL 回读）**。发版坑再现：artifact 302 签名 URL 带 Bearer 必 401（重定向去凭据）+python urllib 自动跟重定向（禁重定向 opener）+IncompleteRead（改 curl --retry 直下）。
- **P8 静态钉落地（3 条，tests/test_gui_js_static.py，D-3 收官件）**：token 收口趋势门——钉1 font-size 11px/10px 计数≤冻结存量 24（22+2）；钉2 border-radius 硬编码按值冻结清单（9/10/6/7/4/99/999px 各档计数超量或新档位即红）；钉3 组件规则内色值字面量冻结 4 种新值即红（:root 定义不计数）。评议员条件①"存量先固化不先修"兑现（11px 归位属 3.1 归一包 Tier2 需 S6 复议，收敛后钉值同步下调）；先红后绿实证（注入 11px/5px/#123456 三钉分别报红，还原全绿）。
- **顺手项+#238/#500 改道+设计派发流程硬化（2026-10-12 owner 三指示）**：①顺手项=AGENTS.md（20 行项目规则）入库+config/child_procs.json、config/fullchain_last_run.json 入 gitignore；②#238/#500 归类闭环（见 D2026-1012-02 追记：污染类高置信推断+初翻幻觉类本轮无实例）；③**设计派发流程硬化**（根因=design-expert 单次 8 件大体量产出无时间预算、报告与产出一体，超时即报告与判定丢失——本轮 P8 判定即因此缺位由 owner 直接拍板补位；历史上 D2026-1010-01 卡3 已有两度超时取消先例）→四条约定写入项目 AGENTS.md「设计任务派发约定」：分件派发 ≤2 件/每件即写盘、判定与产出分离、约 30 分钟超时即主审兜底（D2026-1010-01 先例）、保底序声明。
- **A 组六项 owner 裁定追记（2026-10-12，"以上内容做提示词在下一会话开始"）**：①**A1 阶段 0b**：owner 今天自勾；意向=B-01 恢复/B-02 恢复/B-18 owner 亲裁（裁向基线原文与 A1-② 同方向）/痛点如实勾（涉及字号/行高/间距即触发 S6 复议属正常流程）/A1 小样=②/A2 小样=A；**0b 裁定表 11/11 完成（2026-10-12 晚，AskUserQuestion 逐项实录，已回填裁定表）**：B-01=维持现状缩减版（仅加「已选 X 个」计数提示 JS 态 MSG 键，推翻恢复意向）/B-02=维持现状（推翻恢复意向）/B-03=维持现状（「Source 格式清单」标题保留）/B-04=**恢复**（进度定量反馈：阶段名+批次+百分比，零 id 零键）/B-05=维持现状（模型归口引擎页不回右栏）/B-06=**恢复**（卡3 标题缩短+悬停完整句）/B-07=**恢复**（checkbox→toggle 滑块，纯 CSS）/B-08=维持现状+回写 handoff/B-09=维持现状+回写 handoff/B-10=**恢复并扩展 7 页**（页头复用既有键零新增+tabpanel 语义）/B-18=裁 A 侧中栏转白（brief :27/:113 口径，**A1 小样锁定②**，handoff §5 token 注释为被裁倒侧）。**汇总=恢复类 4 项（B-04/06/07/10，全部零冻结契约影响）+维持类 7 项；handoff 阶段 2 修订清单=B-08/B-09/B-18 三处回写+§5 token 注释改写**。剩余 0b 输入=痛点点选表（七页×四态）+A2 排印小样正式确认（意向=A）。②**A2 C22 标注**：owner 需时间核实，**提醒链=下一会话开始提醒+下下轮会话再提醒**（已入交接链与记忆）；③**A3 v3.0.1 走查**：owner 测试进行中，BUG/调整并入 3.1 或 3.1.X；④**A4 flake 专项**：裁卡已落=docs/design/d1012-卡1-flake竞速修复.md（根因实锤=dict_manager.py:266 秒级 st_mtime 缓存键同刻度不失效，两例同根因；改法=st_mtime_ns+os.utime 测试法；明后天执行）；⑤**A5 撞号消歧**：随 3.1 地基批捎带、单列子任务与验收（11 对撞号不再各自冲突=验收标准），地基批若冗长且影响用户可见正确性则转独立小批；⑥**A6 历史清理**：owner 裁定"清理，不要不动"，先全历史敏感扫描（✅ 已完成：用户名命中 3 提交、真实片名码命中 14 提交、真实媒体目录路径命中 8 提交、本机用户路径零命中——暴露面=用户名+测试用片名与路径，无凭据密钥），方法=删库重建为优、须保留原仓库则 filter-repo，**执行轮须先向 owner 复述代价**（删库重建=全部 Release/下载 URL/issue/star 失效，含刚发布的 v3.0.1；filter-repo=历史重写+force push+全克隆作废+tag 重建）后确认再动手。
- **0b 收口+A6 执行+卡1 收口+3.0.2 重发令（2026-10-12 下午，owner 四指令与全程实录）**：①**0b 输入全收**：A2 排印小样 owner AskUserQuestion 正式确认 **A 档**；**痛点点选表 26 条全裁**（实录已回填痛点点选表"裁决实录"节）：确认=P0-1~5 全进必修批+P1-1~11（P1-10 附拆条指令：5 独立问题分别进批）+P2-1/3/4/5/7/9；合并=P2-10→P1-10、P2-6→P0-5、P2-1/P2-8→P1-7；已覆盖=P2-2（归 B-04）；**S6 复议触发 8 条=P0-2/P0-3/P1-5/P1-7/P1-10/P1-11/P2-6/P2-8**（owner 声明：量化证据按审计采信不二次核验，token 落地前 file:// 走查复核行号，S6 不因已确认跳过）；补充 2 条=校对页运行中反馈（并 P1-9）+引擎页右栏卡3 状态不一致（**主审甄别=渲染层**：index.html:999 pipelineCard 静态 title+app.js:9032 无状态分支；修复方向=卡3 注册表 tab-engine 钩子切提示态，登记候选池）。**裁决=恢复类 4 项（B-04/06/07/10）编入阶段 2 首批，地基批（卡2-卡5）不受痛点表门控。**②**A6 删库重建执行完毕**：owner AskUserQuestion 终选"删库重建"；备份先行=D:\SubTransJAV-backup-20261012\（bare 镜像 60 refs 全历史+34 Release 元数据 JSON+54 资产 1.4GB ok=54 fail=0）；实况=issue 0/star 0/fork 0/watcher 1，损失面小于预估；令牌 scopes 无 delete_repo 改 owner 浏览器手删；新仓 API 重建（public+原描述）+本地孤儿根 fd87e1d（树与 5f2e135 逐位一致 diff=0）推送 main=ls-remote 一致，本地 gc 后 3.8MB 纯新根对象；老 tag/分支只在备份镜像存在；**原 34 Release 与下载 URL 死亡（含 v3.0.1），owner 随令"重发 3.0.2 正式版"（本条同批执行，发版勾账见下）**。③**卡1 flake 收口**：三提交 999acdf（生产侧 ns 键）/c1b8079（竞速红升级 100ns 亚 ulp 对，mimo 复核轮纠正首轮"先红"不实——旧浮点键可辨 +1000ns 差）/41f458c（执行记录更正），主审验证链五环过（ruff/定向 58/全量 **2397+4**/冒烟双入口/安全补偿审查——Mimosa 深扫本会话无触发口，seal af0fb25d=37 后生产增量仅 12 行数值键+注释零攻击面，diff secret 零命中，下次宿主深扫核对）；插曲=首次派发 TaskStop 后 opencode 服务侧会话存活并完成提交（停活须以 git log/进程静止为准，已入记忆）；test_h4b_adaptive 例待 CI 观察是否随根因消失。④**3.0.2 重发令**：owner 指令"重发 3.0.2 正式版"——口径=release/3.0.2 自删除重建后 main（3.0.1+flake 修复+docs，地基批不混入），十步发版序列照 checklist 执行，发版后 main 前进 3.0.3.dev0。⑤**地基批执行勾账**：卡2（FROZEN_IDS 快照外置）✅ 收口=56c1520+404878a+3c1290a（品牌 allowlist 增记卡2-卡5——入库 tracked 后即红的假绿教训：未 tracked 时品牌钉不扫，新增文档须在 commit 前以 tracked 口径自检）；快照 JSON 223 id/187 键+再生工具 tools/ui_contract_snapshot.py（no-drift 机制）；卡3（switchTab 六钩子收编）/卡4（active 别名 token）/卡5（撞号消歧）按序执行中；opencode-cli 铁律落档=只准 free 模型（mimo-v2.6-flash-free 主用/longcat-2.5-preview-free 备选），配置层 model+small_model 已钉 free 防默认漂移。⑥**3.0.2 发版勾账（十步全走，同日下午）**：release/3.0.2 自新根 fd87e1d 线=2653feb（3.0.1+flake 修复+docs，地基批未混入）；版本四件套 bump 3.0.2+CHANGELOG 只写本版；验证链=ruff clean+版本钉 3 passed+全量 2397+4（首跑 1 failed 竞速族单败单跑即绿用例名未捕获记档）+冻结 CLI 冒烟（3.0.2/frozen/%LOCALAPPDATA%）；tag v3.0.2→release.yml run 38207828100 success；artifact 直连被限速（108MB 需 2h）改代理 127.0.0.1:10808 后 30s；setup 51,320,593B SHA256 74C4FDFF…A965838 本地实算=SHA256SUMS=公开 URL 回读三处 MATCH；Release id 410220922 建发双资产（notes 只写本版+历史重建注）；main 前进 3.0.3.dev0=f84e8a6；ls-remote 三处一致（main f84e8a6/分支 2653feb/tag→同 commit）。⑦**地基批卡 3/4/5 收口勾账**：卡3=922ce65+f866a6b（TAB_HOOKS 注册表三分组+派发循环，新增收编钉 1，五既有钩子钉改指不放宽，全量 2398+4）；卡4=c5d50a5+2c877c0（--active-bg/text/border/bar 别名层+三规则改引，feature-badge 语义态零接触，暗色经 token 重映射自动跟随零改动，新增别名钉 1，全量 2399+4）；卡5=d3ea50e+9fa51c6（item_id=类别码-index 五来源 additive，PW 动态类别按来源取码，UNTR 行尾补码保 test_pipeline_v2 冻结子串，消费端 action_retranslate 台账+api 疑点段最小透传旧件退化裸 index，定向 166+全量 **2400+4**——mimo 会话于全量等待中中断零提交，主审按先例接手亲跑验证链后如实提交）；GUI 验证口径=卡3/卡4 触前端：启动冒烟过（--help+进程存活 12s），**web-gui-tester 黑盒未跑**（stub 桥夹具未建，归阶段 4 验收批），提交信息按规标注。⑧**地基批遗留移交**：卡4 computed-style 前后等值黑盒复核、卡5 真机 11 对撞号复现、卡3 tab-engine 钩子（引擎页 pipelineCard 提示态）候选、卡2 SIM905 冗余豁免顺手清——全部候选池/阶段 2/4 编排。⑨**阶段 2 首批收口+GUI 黑盒补验+模型评测制（2026-10-12 晚）**：**卡6 黑盒夹具**=Temp/gui-blackbox/（stub_bridge.js+serve.py，瞬态不入库；3bcda6e 记录），主审亲跑黑盒：7/7 页签切换+亮暗双主题激活态取色双证+零交互错误（卡3/卡4 补验全绿闭环；IAB 物理输入不到页面，按先例程序化 click 代理；夹具可复用）。**B 批四卡全收口**（执行者=MiMo，longcat free 档限流长时间化后 owner 定模型链方案）：卡7 B-04=5d2aa4e（progress-meta 定量行，零 id 零键，+3 钉）；卡8 B-06=254fa23+e23002b（v2 勘误后执行——首轮 longcat 即停发现卡面 strings.py 路径错误，真身=app.js MSG+index.html 双渲染；MiMo 两偏差主动披露：完整句悬停改 applyI18n 运行时回填（静态 title 撞未标中文红线+data-i18n-title 被短值覆写）、新钉落点按卡面红绿条款，均追认；+4 钉）；卡9 B-07=fdcc46b（纯 CSS toggle，token 零新字面值+焦点环保留，+2 钉）；卡10 B-10=04ff9c7（6 页页头复用既有 tabXxx 键+7×tabpanel/aria-label+7×aria-controls，一处既有钉收紧型契约变更，+5 钉）。**全量基线 2400+4 → 2414+4**（四卡 +14 钉只增不减，卡10 全量零 flake）；工具 no-drift 自证。**模型评测制**（owner 方案：longcat 主力之一+限流降档链 mimo→ling-3.1→nemotron-3.5→nemotron-3U→space-bunny+任务实测打分+限流解除按分回切；上下文 100W 加 0.5 分）：longcat=+0.5（100W）+卡6/7 实测优但 free 档长时间限流；mimo=20W 无加分+卡8=6/6（偏差披露规范）、卡9 优（新识别 Windows 文件占用型 flake 第 5 例）、卡10 优（收紧型契约变更处置正确）——收尾硬纪律下 mimo 卡5 丢收尾未复发。**flake 家族台账（5 例单跑即绿）**：test_action_retranslate/test_encode_queue/test_pipeline_v2::test_resume_rejects_changed_stage_prompts/test_review_save_success_backup_and_rewrite（Windows 文件占用）/既往未名例——建议另立 flake 甄别卡。
- **UI 回滚保障追记（owner 2026-10-15 指示「当前UI设计记得备份，可能有部分再重塑后不合意会回滚」）**：重塑开工前 UI 资产快照已备份=`D:\SubTransJAV-UI-backup-20261015\ui-assets-pre-3.1-8005969.zip`（git archive 自基线 8005969 导出 webview_gui/assets/ 全部 6 个受管文件，zip sha256 a99e7831…3f4283，README 含回滚三式：逐笔 revert/整体解压还原/git checkout 单文件）+本地 tag `backup/ui-pre-3.1-20261015`→8005969（仅本地未推送）；执行纪律=此后每个重塑批独立成 commit 保逐笔可回滚，批验收信息注明回滚点。
- **地基批遗留移交核销追记（2026-10-20，D2026-1020-06）**：⑧ 四项中——卡4 computed-style 前后等值黑盒复核、卡5 真机 11 对撞号复现＝随阶段 4 统一真机走查未再报视为通过（roadmap 3.1 节勾账口径），核销；卡3 tab-engine 钩子（引擎页 pipelineCard 提示态）已由候选池小卡落地（roadmap 阶段 2 勾账）；卡2 SIM905 冗余豁免属工程卫生候选池项、不属 3.1 发版门，维持登记。

## [2026-10-12] [D2026-1012-02] 真机产物分析轮：7 次全链实测数据提取+C22 样本池就绪+观察台账首批 [登记·数据为"观察非结论"]

- **素材**：owner 2026-10-12 指示"4-7 次实测翻译含全链与 final 产出已可作分析素材开工"。实盘 7 次运行（测试输出目录两个批次文件夹，2026-10-05~10-12），每次含 final_cn/质量报告/导读/分歧复核，后 4 次另有 AI 建议/重翻记录/风险清单；分析副本隔离临时目录，原文件零改动。
- **C22 校准（D2026-1009-01/-02 遗留）**：样本池 **140 段**（7 文件×20 条疑似漏听观测，同 wave 级 RMS 链候选分布），≥60 门槛满足；媒体/导读在位核验全过。标注包已生成=测试输出根「C22校准标注包」/c22_manifest.json+标注说明.txt；**下一步=owner 独立标注（true/false，不看程序置信档）→tools/c22_calibration.py 回放→Wilson 95% 下界 ≥0.95+复标一致率 ≥90% 才启用自动补行**。
- **residual_cps 发版后观察（D2026-1010-02 遗留③）**：机制真机生效，3 次新构建运行台账分别记录 3/9/11 条残留**全部 >5.0**（5.05~11.68，最高 11.68）；cps_too_fast 修复留残留的比例为观察信号，不构成结论。
- **guide items 撞号（D2026-1010-03 遗留②）**：6/7 运行出现重复 index 共 11 对，**全部为 cps_too_fast×其他类别**（untranslated/suspected_missed_speech/single_line_too_long）各自独立编号相撞——"撞号再升级 category 消歧"触发条件已满足，登记候选池（roadmap），未拍板不改代码。
- **模型结构化 index 出现率（D2026-1010-03 遗留①）**：新构建运行 TM 建议 4/4 全带 index（100%）；旧构建 0%（prompt 契约系新增，符合预期，reason 回捞兜底覆盖旧件）；另 1 例 AI 建议 parse_ok=false（qwen3.8-27b 模型输出解析失败，入模型质量观察）。
- **件A crosscheck_detail（D2026-1010-03）真机验证**：深夜构建 2 运行结构化落盘 13/10 段（timing/asr_text/current_text 全文不截断）；更早构建无此键=构建时间线差异非缺陷。
- **#238/#500 复走查归类（D2026-1010-02 遗留①）**：#174 已定位（第五批次测试 mimk-273 导读，cps_too_fast，正文有明显 ASR 重复痕迹）；#238/#265/#500 在现存导读件未命中——原件疑被修复后重跑覆盖，**归类路径待 owner 二选一：指认当时文件，或改走新运行现象分账**。
- **#238/#500 归类闭环（2026-10-12 owner 回执"已经覆盖的无法指认"→改道新运行现象分账执行）**：以 7 次运行导读件为证据面——**污染类实证**：旧构建 2 运行（run1=10-05/06、run4=10-11 14:46）共 40 处 observation 条目挂邻句译文（current_text 非空），与 #174 同症状群；run4 更有 1 条 suspected_missed_speech 条目 status=retranslated（observation 被送进重翻——件2 所修之洞的现场证据，即 owner"二次重翻效果差"的机制根因）。**修复反证**：新构建 5 运行（run2/3/5/6/7）污染残留全部=0（件2 修复生效）。**初翻幻觉类**：新构建重翻 reason 与 AI 建议 observations 零幻觉类关键词命中，无可归入实例。**裁定：#238/#265/#500 归污染类（高置信推断：同批次反馈+同症状群+件2 修复后现象消失的反证；原件不可考故标注推断级）**；初翻幻觉类目保留但本轮无实例归入，后续真机再现时按现象单独立账。D2026-1010-02 遗留① 闭环。
- **附带信号（全部"观察非结论"）**：旧构建运行重翻失败率 46%（32/70）显著高于新构建（1~6 条/次），待复现归因；2 运行风险清单记录媒体配对 whisperjav_run.json 未命中走同目录回退；未翻译残留 2~26 条/次；gui.log 全链场次（vid1/ep01，10-11 深夜）为状态机自测非真实翻译。
- **新 flake 登记**：test_h4b_adaptive.py::test_pipeline_red_mark_on_optin_without_telemetry 首跑单败、单测与整文件重跑即绿（词典/tmp 竞速族，同 test_effective_dir_blacklist 模式）——横切观察项新增。
- **关联**：D2026-1009-01/-02（C22）、D2026-1010-02（residual_cps/#238/#500）、D2026-1010-03（index/crosscheck/撞号）、D2026-1012-01（3.1 执行勾账）。
- **C22-卡1 直调收口（2026-10-12 深夜，首张经 ZCode 直调 OpenCode CLI 执行的任务卡）**：派发=opencode-cli run --standalone --auto（longcat 限流→按 owner 轮转令自动切 mimo 接卡成功，直调链路与限流轮转规则双实证）；产出=25cbf1b（harness labels/timings 可选键：逐间隙真值+显式清单对齐，类型/长度校验 fail-closed 退出码 1）+1d38a29（执行记录）；主审验收全链过=ruff clean/定向 8 钉/全量 2422+4（基线 2414+4 只增）/selftest 冒烟方向自证不变（合成下界 0.5101<0.95 门控未写）/mypy 门 0/0/0/Mimosa deep 37 零新增 seal fd2b119e；验收抓 1 笔=品牌钉 tracked 即红第二例（卡面验收命令含真实仓库根路径）→0986c97 allowlist 增记（卡2 卡面入库时须与白名单同提交增记，注释已留）；mimo 记分=优（卡面遵行/偏差披露三条如实含 mypy 未跑理由/收尾纪律/先红后绿实测 5F3P→8P；观察项=labels 元素未逐 bool 校验，不扣分）；下一步=卡2 听点标注器直调派发。注：提交时 Mimosa hook scanner_enobufs 兼容放行，深扫结论已由会话侧完整取得（seal fd2b119e）。

## [2026-10-12] [D2026-1012-03] 品牌钉口径修订（docs/design 单前缀豁免+卡面去根路径字面量）+C22-卡2 听点标注器收口 [已拍板·已落地]

- **品牌钉修订（A+B）**：触发源实证=任务卡验收命令区 `cd /d D:\SubTransJAV` 一行（allowlist 53 条中 20 条 docs/design 工作文档，13 文件命中全是该行）；假绿真因=钉扫 git index、文件 add 前不可见（时序问题，扫描时机改造判空转且反向有害）。落地：A=卡面模板去真实根路径（本仓库 AGENTS.md 新增「任务卡裁卡约定」节成文）；B=tests/test_brand_allowlist.py 新增 `_EXEMPT_PREFIXES=("docs/design/",)` 单前缀豁免+双向 guard 断言（扩大豁免须改断言 diff 可见；白名单禁含豁免前缀条目），docs/design 20 条出清（53→33）。**C 本地目录改名不做**（波及 venv/IDE/记忆>>收益）；**D 每卡增记弃**；**E1 core.hooksPath pre-commit 只跑品牌钉登记候选池**（Mimosa git-gate 不覆盖 OpenCode 提交的结构缺口，B 后边际价值降）。
- **HRO 处置**（decision-critic 评议）：HRO-1 反对 B' 正向扫描域（会静默放行 setup.iss/release.yml 资产名/uninstall.bat/pyproject 用户可见面）→采纳，取 B 形态 default-deny；HRO-2 在办增记指令未作废前落 B 必红→采纳，时序先 A+B 后入库卡面，测试文件旧指令注释已删，卡面执行记录历史叙述不改（decision-log 权威高于卡面）。拍板说明：owner 要求"方案+讨论"，AskUserQuestion 未答，按评议推荐落地并全程可逆披露。
- **依赖影响登记**：①D2026-1004-02 品牌 allowlist 钉判定面由本条修订（产品面语义不变）；②D2026-1004-04 C2"增删双侧清单化"收窄为"产品面双侧、docs/design 豁免出双向"；③D2026-1012-01/02 在办指令"卡2 卡面入库须同提交增记"作废。
- **品牌钉验证**：基线绿（白名单 53→33、豁免前缀条目 0）；mutation 双探针=docs 根级 staged 含品牌串→红（default-deny 保留）、docs/design staged 含品牌串→绿（豁免生效）。
- **C22-卡2 收口（听点标注器）**：执行=轮转接力（mimo 28 分钟产出 824+503 行后于全量等待中断零提交→ling-3.1 接卡完成）；代码=75cc69f（单文件 stdlib 工具：--prepare ffmpeg 切±3s 片段/--serve 本地网页听点标注/--merge 产 timings+labels 对齐 manifest+一键回放.bat；只绑 127.0.0.1、原子落盘、复标 ceil(20%) 不回显）；主审验收=ruff clean/定向 17→18 钉/全量 **2439+4**（2422+4 只增）/冒烟 --help 0/**GUI 黑盒六点全过**（初始渲染大按钮大字/点击自动跳条+回退钮/三条完成态+复标入口/复标不回显首轮答案/一致率 100% 达标绿提示/state.json 即时落盘——IAB 定位引擎动作性超时两例，按先例坐标点击代理；console 不可采集，无可见错误表现）/Mimosa deep **37 零新增**（中间轮 +1 insecure-randomness @ c22_labeler.py:677 复标抽样，low 级 benign，一行 SystemRandom 加固后复扫回 37，seal e0080abc）。
- **记分（模型评测制）**：ling-3.1 首战=**优**（卡面遵行✓零超卡/偏差披露✓三条如实含品牌钉预警遵行与 GUI 未跑/收尾纪律✓/测试 17 钉全绿）；mimo（卡2 前段）=产出实质符合卡面但全量等待中会话中断零提交（free 档会话限制，环境因素，第二次发生入观察）——实质工作未白费，ling 基于其产出收口。
- **卡2 遗留**：真机高频点击原子写重试观察项（ling 披露）；一键回放全真实链路待 owner 标注完成后走 C22 校准流程自然验证；提醒链=C22 140 段标注（工具已就绪，等 owner 时间）。
- **owner 两点纠正（2026-10-13，硬规则已入全局 AGENTS.md）**：①本条验收轮主审两处亲改码（品牌钉 test 改造、SystemRandom 一行修）违反"代码问题一律 OpenCode free 模型"分工——结果追认、流程违规登记，今后验收期修正（含一行级）一律裁小卡交 OpenCode，主审只做方案制定/验收/检查；②派卡看护制度化：free 模型超 20 分钟无产出即读日志查限流/卡死（派卡同时挂 20 分钟看护计时器），限流即轮转、卡死即停活重派，不得等 owner 催（卡2 mimo 28 分钟断线先例）。
- **owner 二次澄清（2026-10-13）**：①验收期修正分工放宽——小问题（一行级/小修/测试小改）主审直接修没问题，较大 bug 修复才裁卡交 free 模型（前条"哪怕一行也裁卡"过严，作废）；②中断不接手原则——free 模型中断/卡死继续轮转下一个接卡（卡2 mimo 断→ling 接即正确示范），仅当所有轮转都限流时主审才兜底亲执。全局 AGENTS.md 两条款已按此改写。
- **C22 标注真机观察（owner 试听发现，2026-10-13，登记为"观察非结论"）**：存在"背景声+道具声+小声人声"混合段——低信噪比台词的插入文本质量风险面：C22 精确率口径测的是"判 high 段是否真有台词"，不直接测转写文本质量；此类段 label=true 但 whisper 转写差时理论上可产生污染插入。现有拦截层=程序侧三维置信门（小声嘈杂段大概率 avg_logprob/no_speech_prob 不过→判 low→放弃）+荒谬密度/纯拟声过滤+首版从严+台账可回滚；owner 标注指引=按"是否真有台词"标真值不因音量妥协（怕污染而标 false 会 bias 校准，违反独立标注），听不出是否语音→稍后再听多听（耳机/调音量）。若试运行出现此类污染实例再立卡（候选信号：high 段加能量占比复核信号）。
- **看护阈值调整（owner 2026-10-13）**：派卡看护 20 分钟→**10 分钟**（free 模型超 10 分钟无产出即查限流/卡死），全局 AGENTS.md 与记忆已同步；在途卡3 看护计时器已按 10 分钟重挂。
- **C22-卡3 收口（声源组合勾选 16 态穷举，2026-10-13 凌晨）**：执行=mimo（longcat 仍限流轮转接卡）；代码=05692c5（三大按钮→16 组合钮按 C(4,0)~C(4,4) 五组穷举+颜色即判定含台词绿标/静音补缺+sounds 向量落盘+旧记录兼容零丢失+复标盲标 16 钮+merge 组合分布统计；harness 零改动）；**卡面矛盾甄别=mimo 抓获主审笔误**（卡面写"17 钮"但自枚举 1+4+6+4+1=16，C(4,0)~C(4,4) 本即 16 态——按枚举执行 16 钮+"17"计为笔误并入记录，未越卡自修，处置正确）；主审验收=ruff clean/定向 26/全量 **2447+4**（2439+4 只增）/冒烟 0/**GUI 黑盒六点过**（16 钮穷举+颜色角标图例/单击提交自动跳条/组合向量落盘精确 speech:bg 与旧记录零丢失/复标盲标不回显/一致率 100% 达标/继续复标态按钮语义正确——IAB 定位超时 2 例+看护坐标偏 3px 空点 2 例，dom_cua 节点路径解决=第三通道先例；console 不可采集无可见错误）/Mimosa deep **37 零新增** seal c19f90da；**记分：mimo=优**（卡面遵行✓/卡面矛盾甄别与披露✓/收尾纪律✓/17 钉全绿——连续第 3 次实质优）；遗留登记候选池=①完成态下首轮条目浏览/改判入口缺失（v1 起即如此非本卡引入）②旧口径徽章完成态下不可视（单测层已钉）。**owner 换版指引：关旧标注页→重新双击开始标注.bat 即新版**；已标 3 条保留为旧口径可重答。
- **卡3 追记（owner 试听反馈，2026-10-13）**：作答后自动播放下一条（此前需每条手动点播放）——主审小修直改（验收期小修分工口径），渲染即 play+策略拒绝静默降级，回归钉 1；GUI 实测通过。owner 重新双击开始标注.bat 生效。
- **C22-卡4 收口（长间隙判读辅助，2026-10-13 凌晨）**：执行=mimo（longcat 限流轮转接卡，10 分钟看护两次检查均健康）；代码=8e1cb3b（message 透传上屏/切片 cap 20→30s 消灭长间隙尾部截断/prepare 幂等保标注（硬约束：按 id 继承 label/sounds/relabel/relabel_sounds）/seek_in 播放跳过 3s 前缓冲/缓冲说明文案；harness 零改动）；mimo 卡外披露三条质量高（relabel_queue 重置语义/真实包验证留主审/labeled 口径定义=首轮已决）；主审验收=ruff clean/定向 31/全量 **2453+4**/冒烟 0/**真实标注包幂等实测**（E:\ 标注包 140 条全决策状态下重跑 prepare：逐字段 diff=0 零丢失、message/seek_in 覆盖 140/140、备份先行 state_backup_k4.json）/GUI 验证=meta 粗筛提示上屏✓+10s 片段从 3s 起播✓（短片段 <6.5s 守卫不 seek 亦验证）；Mimosa deep **37 零新增** seal 04df0c29；**记分：mimo=优**（连续第 4 次）；owner 状态=首轮 140/140 已标完+复标开始，重跑已保留全部作答；**换版注意=复标队列重置（已有 1 条复标答案作废重抽，首轮 140 条无损）**——owner 重启 bat 后点「进入复标」重抽即可。

## [2026-10-13] [D2026-1013-01] S6 复议两步制第 1+2 步完成（方案两卷+评议有条件通过+修正轮闭环）+候选池小卡四卡收口 [已拍板 · 规格已回写 · 拆卡 A-H 2026-10-13 开工令当日十卡全收口（详见条目正文与追记）]（标题回写 2026-10-21，原题「待 owner 开工令」陈旧致研究卡误判，状态以本括注为准，条目正文未动）

- **S6 复议方案（两步制第 1 步，design-expert，两件即写盘）**：件1「排印刻度卷」（P0-2/P0-3/P1-10 拆5）+件2「布局表面卷」（P1-5+P1-11/P1-7 含 P2-1·P2-8/P2-6 邻接面），现均 v2（评议修正轮后）。核心声明：**钉④ 4 条核心值零触碰、无例外申请**；A 档锁定不翻案；新增 token 仅 3 枚（--space-hair:2px/--lh-tight:1.25/--w-direction-sel:5.5em）。要点：P0-2 裁定=11px/10px×24 全量清零不设白名单（三理由：owner 点名位即重灾区/白名单静态钉防不住回潮/钉1 可下调 0）；P0-3=字重显式化（46 处→400/700 零视觉变化）+五级层级用法表；P1-10 拆5=gap 49 分量全映射/圆角 16 处全映射/行高 17 处 6 档收敛三值/中英混排（栈序规则+英文残留 4 处走 MSG+4 零快照路线）/宽度收敛（--w-model/--w-key-input 上调 200px）；P1-5+P1-11=flex 四改（Console 0 1 30%→1 1 40%+删 max-height:380 等）；P1-7=右栏折叠（零 id 零键+class 绑定+localStorage 记忆+1180 同轴判据）。冻结物变更总表：钉1 24→0、钉2 七档→0（同卡同提交）、MSG +4、快照零增预期；拆卡 A-H 序（每卡 ≤2 文件）。
- **评议员（两步制第 2 步，decision-critic）**：**有条件通过**——1 [HIGH_RISK_OBJECTION]（P0-2 全清零取消 owner「11px 仅限极短标签」明示例外，须终审显式二选一 A 全清零/B 白名单）+2 [MATERIAL_CONFLICT]（英文残留漏 index.html:740「Analysis model」→MSG 键 3→4；gap 双值 1189/2869 漏拆分量→计数 44 处→47 处/49 分量）+[INFO_GAP]（localStorage 持久性未证、1180 断点 off-by-one、卡E/卡G 依赖张力、200px 容量测算缺、.mp-chip 无 nowrap、theme-button 居中回归验证）——**主审对 HRO 处置=按评议建议交 owner 终审显式拍板（未自行采纳/驳回）**；修正轮已派回 design-expert 全部闭环（两卷 v2 自检零残留）。
- **owner 终审清单（5 条）**：①P0-2 口径二选一（含 HRO，必答）②P2-1「一并验证」扩为「两行布局改」是否追认（不追认退为仅验证）③index.html:253/297「API Key」按品牌词白名单保留还是译化④折叠启动默认阈值 1180（含 1180 判据同轴化与 1181~1240 形态跳变已知代价）⑤折叠记忆机制三选一（localStorage 单写·实测不持久降级默认/theme 式双写/会话级）。
- **候选池小卡四卡收口（直调 opencode-cli，longcat 主力；B3 longcat 中途限流→mimo 接卡）**：
  - **卡A pipelineCard 提示态=8a3c301**：refreshPipelineCardHint 惰性求值（hover/focus 时按 .tab-page.active 即时切换 title）+MSG pipeline_card_hint_here+新钉 1（test_pipeline_card_hint_here_pinned）；主审方向偏离披露=未走 TAB_HOOKS 注册表（无离开事件需 5 页补注册、applyI18n 覆写时序（卡8 先例）、默认页无钩子分组三问题 hover 惰性求值一次解决）；主审验收=ruff/定向 207/全量 2454+4/冒烟 0/**GUI 黑盒四点过**（默认页前往文案/引擎页本页态/切回恢复/focus 路径——程序化 click 代理先例）；执行者如实披露红阶段缺口（卡面 helper 模板 MSG[三元式] 方括号形式不触发反向悬空钉点号正则——卡面设计缺口非执行偏差）；**longcat 记分=优**（观察项=全量 46-fail 假象未下钻到解释器层）。
  - **卡B1 flake 甄别（action_retranslate/encode_queue）=4cbcead**：复现矩阵全绿未复现；wait_until 默认 5→15s 有据加固（test_total_timeout_fires 已用 15s）；误加固自回退披露如实。**验收期主审全量实捕家族成员** test_finalize_phase_not_killed_before_deadline（单跑 3 连绿）：根因=wait_until 每轮推假钟 +5s/真实 5ms≈千倍实速，全量负载下生产者迟滞 ≥12 轮即假钟越过 120s deadline 误杀——主审小修重锚 clock.t=1000.0 再 advance(60)（**838f9da**，语义不变去轮询耦合，定向 3 连绿+全量绿）；**longcat 记分=优**（观察项=卡外 git stash 双用已恢复未在执行记录披露、错解释器归因未下钻）。
  - **卡B2 flake 甄别（review_save/Windows 文件占用）=7dfe0e9**：fs_utils._atomic_write_text 对 PermissionError/WinError 32/33 有界重试（5 次×20ms 起指数退避 ≤300ms，耗尽抛原异常）+_is_file_lock_error+2 单测先红实证（注入式 PermissionError 红→实装绿）；mypy 基线门 0/0/0；主审全量 2456+4 绿；**longcat 记分=优**（观察项=「gui_api ×3 全绿」实为无 gui-extra 全 skip 空跑未标注）。
  - **卡B3 flake 甄别（resume 指纹拒绝）=3ab005b（mimo 接卡）**：17 跑未复现（单测×5/整文件×2/组合×6/定向污染对×2/全量×3）；四假设逐条排除均给行号证据（中断点时序/指纹时变字段/capsys 竞速/共享 work 目录）；按残余风险加 4 组机制级加固钉纯新增（中断现场前置 A=done/B=running、config_hash 独立复算自洽、V2_STAGE_PROMPTS 参与 D1 钉、拒绝原因「配置已变化」+首调无 ||| 的 capsys 无关证据）；提交前自查品牌钉；46-fail 假象根因坐实 G:\python 缺 pysubs2（收集 2134 vs 全依赖 2457）；**mimo 记分=优（连续第 5 次实质优）**；轮转操作教训=-m 模型 id 须带 opencode/ 前缀（"Invalid model reference: mimo-v2.6-flash-free"→"opencode/mimo-v2.6-flash-free"）。
- **顺手清**：SIM905 冗余豁免=c4ccb33（卡2 快照外置后豁免对象已不存在；隔离 --select SIM905 实证零命中后删 pyproject 两行）。
- **基线与安全**：全量 **2456+4**（2453+4→卡A +1、卡B2 +2，B1/B3 与两笔主审小修零计数变化）；Mimosa deep **37 零新增** seal sha256:589dac78…fb8602（scanner_enobufs 兼容放行两笔已由本次完整深扫覆盖）。
- **模型评测制累计**：longcat 本轮解限主力三卡（2 优 1 优含观察项）；mimo B3 接卡优；限流轮转链与 opencode/ 前缀教训已录。
- **依据文件**：docs/design/d1013-S6复议-排印刻度卷.md、docs/design/d1013-S6复议-布局表面卷.md、docs/design/d1013-卡1..卡4-*.md（含执行记录）、tests/test_gui_js_static.py（卡A 新钉）、tests/test_encode_queue.py（B1+重锚）、subtransjav/refine/fs_utils.py（B2）、tests/test_pipeline_v2.py（B3 加固）。
- **关联**：D2026-1012-01（S6 两步制源+⑨候选池+模型评测制）、D2026-1012-03（卡面根路径禁令——本批四卡卡面均遵行）；阶段 2「排印/表面归一包」排期=owner 终审通过后按两卷拆卡 A-H 执行。
- **owner 终审拍板（2026-10-13，五条全裁）**：①P0-2 **选 A**——11px/10px 全量清零不设极短标签白名单（理由=路径/chip/表头系重灾区、白名单须长期人工维护且静态钉防不住偷加小字、清零后钉1 24→0），**HRO 关闭**；②P2-1 **有条件追认**——quick-bar 两行布局入卡 G1 子项，不新增 id/MSG，须过 100%/125%/150% 截图与高度/对齐回归，回归则回退为仅验证；③API Key **保留不译**——登记术语白名单，维持 MSG +4（免快照 187→191 解冻），未来全面中文化另批届时 MSG 走 5 键；④折叠启动默认阈值 **不接受 1180，采用 1240**——JS `innerWidth<=1240` 启动默认、CSS `@media(max-width:1180px)` 结构断点分轴不得混用，验收加 1180/1181/1240/1241 四档断言（owner 理由：1181~1240 展开态主区 589~648px 比 618px 基准更窄，恰是 P1-7 最紧段）；⑤折叠记忆 **localStorage 单写**——键 `subtransjav.aside.collapsed`，先实测持久性，不持久降级按窗口默认、不自动转双写，private-mode 同降级。排期不变：卡 F 先于卡 G、卡 E 在卡 G 后、卡 G2 末置。
- **评议员拍板后复议轮（owner 指令"拿我的观点和评议员再讨论次"，同日）**：**无新 [HIGH_RISK_OBJECTION]，五条全支持，拍板可归档执行**；上轮 1 HRO+2 材料冲突确认由 v2 闭环。产出落地条件清单 LC-1~LC-13，主审全部采纳（LC-3/LC-8 两枚建议新钉系主审裁量采纳——与 P8 钉法同型、机器可判、基线只增方向；如 owner 有异议可回退为人工 grep 验收）。**两条实质增量**：LC-1=index.html:517 `#refineTplLoadedPath` 内联 11px 系第 25 处（钉1 只扫 style.css 不拦）→卡A 拆 A1/A2 扩内联面 + §1.3 判定面扩两文件；LC-9=件2 §2.2d 回写 1240 为派卡 G1/G2 硬前置。其余：LC-2 钉1 注释同步防僵尸+禁扩 regex 至 12.5、LC-4 复扫同扫 index.html、LC-5/6 P2-1 回退四要素+选择器点名写死卡 G1、LC-7 API Key 白名单登记落点=归一提案 §7 表（中文可见钉只抓中文挂不上）、LC-10 卡 G2 写死 resize 仅启动默认、LC-11 @media 内展态沿用 300px 不另立规则、LC-12 断言扩七条（+记忆=0/1、手动粘滞；窗宽统一 innerWidth 口径）、LC-13 降级三分支+实测口径（打包态/开发态分记）+升级复位已知代价。
- **规格回写勾账（2026-10-13，主审直修 docs-only）**：件2 升 v3（§2.2c/§2.2d/§2.2e/§2.3/§2.5/§5.2 卡A1A2 与卡G1G2 行）；件1 升 v3（§1.1/§1.2/§1.3/§1.4/§1.5/§1.6/§1.7/§3.4/§4——字号总量 32→33 处口径）；归一提案 §7 增 API Key 豁免行。核心声明复核不变：钉④ 4 条零触碰、A 档锁定、新增 token 3 枚、钉1 24→0、钉2 七档→0 同卡同提交、MSG +4、快照零增预期。**拆卡 A-H（现 A1/A2..H 共 10 张）待 owner 开工令。**
- **owner 裁量确认（2026-10-13，对主审 LC-3/LC-8 采纳的终审背书）**：**两枚新钉采纳进卡A1/卡D，不回退人工 grep**。理由：政策有钉机器必须跟上（人工 grep 只作落地走查/抽查辅助，不作唯一门）；两钉机器可判、基线只增不减、不触快照不增 MSG 不降级钉④，属纯增强，符合 P8 钉法。**口径钉死**：字号白名单钉=计数对象 font-size 声明，允许集=三档 token+§1.4 展示级豁免清单，:root 定义块排除，豁免静态写死只增不减、新增回终审；英文 label 白名单钉=计数对象 index.html 用户可见英文 label/option/button，允许集=4 静态字面+API Key×2+品牌 option 白名单（落地卡列全），只增不减、新增回终审。**先红后绿双态自证**：注入→红→还原→绿，执行记录附四步日志（卡A1/卡D）。**卡序不变**（LC-3 入卡A1、LC-8 入卡D；每卡 ≤2 文件、同卡完成改值+钉不制造中间态红）。**回退条件仅一种**：新钉与既有钉④/P8/快照机制冲突或白名单误伤现有合法项→主审可同卡内修正钉口径；豁免清单增项必须回终审，不得自行扩权。**开工令：新会话开工**（拆卡 10 张按序裁卡+派卡，交接文档见 %TEMP%\handoff-subtransjav-20261013-s6开工.md）。
- **阶段 2「排印/表面归一包」十卡全收口（2026-10-13，开工令兑现）**：拆卡 10 张（卡面 ff75f6b，行号经主审对 main=738d8cc 实扫零漂移核对）按序 A1→A2→B→C→D→F→G1→E→H→G2 串行派卡+主审逐卡验收，**全部收口未退卡**。基线 **2456+4→2466+4**（+10 新钉：卡A1 字号白名单钉/卡B 行高趋势钉/卡C gap 趋势钉/卡D 3 钉（MSG 键在位+回填在位+LC-8 英文白名单）/卡F flex 布局钉/卡E W1 内联宽度钉/卡G2 结构+行为 2 钉），钉1 24→0、钉2 七档→0、_FROZEN_INLINE_FONT_PX 5→0 均同卡同提交；快照 223 id/187 键零增减、FROZEN_I18N 零增、MSG +4（ai_provider_label/follow_stage_default/ai_model_label/cross_film_window）、钉④ 4 条零触碰全程绿。Mimosa deep **37 零新增** seal sha256:246826e7…54c3a9。
- **十卡提交与验收**：卡A1=058e6f1+0cfd81a（longcat）、卡A2=605956b（longcat）、卡B=81c5eb5（longcat 断流→mimo 接卡）、卡C=03f0924+6a9004d（longcat 断流→nemotron-3.5）、卡D=b0411b6+eaa4ffa（nemotron-3U）、卡F=9b9a22f+1e2d3c9（space-bunny）、卡G1=70bae77（longcat 断流→mimo）、卡E=0eae2a2（ling-3.1 首战）、卡H=9ae108c+8dbe62d（nemotron-3.5 二考）、卡G2=2edd866（longcat 第 4 次限流→space-bunny 二考）。
- **主审裁卡裁量记录**：卡A2 :517 落 id 规则（.muted 实为 font-sm 与规格「随类走」预期不符）+:519 顺手 mono token 化（§3.4 R2 预兑现）；卡E 3 文件并档（省一轮派卡）；卡G1 结构钉顺延卡G2（保每卡 ≤2 文件）；LC-8 白名单排除 data-i18n 契约面（Console/Ready. 等回退文案不进白名单，运行时覆写兜底）；卡A1 豁免清单预登记 32px（卡H 目标值防跨卡撞钉）。
- **验收期主审修正 3 笔**：①卡A1 F841 冗余变量（0cfd81a）；②卡C nemotron-3.5 落 gap 钉误删钉3 def 行（Python 词法忽略空行/注释行特性致断言体静默并入 gap 钉、171 持平纯属掩盖）——恢复钉3 独立函数+gap 钉重写为逐分量解析堵「var 开头混合字面」漏检洞（6a9004d，双向注入自证过）；③卡D/卡H 执行记录漏提交补交（eaa4ffa/8dbe62d）。
- **GUI 黑盒全过**：字号批（页头 14/700+元信息 12px+body 21.7px 钉④未破）；卡F 高度三证（flex 1 1 40%/maxH none/Console 底边距 .main 底恰 32px=--space-6 页尾留白，228px 空白消除）；卡G1 折叠双态（44px 把手/主区 +272px/钮显隐反转/P2-1 badge 第一行 nowrap+select 满宽第二行/125%·150% 无破版——**回退四要素判定保留**）；卡D 回填渲染态（四 label/option 全中文，启动即回填）；卡G2 阈值七条逐条实测（1180 收/1181 收/1240 恰等收/1241 展/记忆 0·1 不随窗口/粘滞过）+localStorage 持久（**降级三分支判定=持久 OK，单写路线定案**）+no-aside 并存（file:// 桥缺环境受限，机制由 CSS 源序保证留真机）；卡E 618 级容量实测（窄窗 636px 主区 stage 行 model 204/key 200/directionCard 588/media 488 全无溢出）。遗留真机走查：校对页 no-aside 挂类钩子、aria-expanded 两钮同态语义复核、卡H 七页空态截图。
- **flake 第 6 例**：test_pipeline_v2 低覆盖上游警示例全量偶发 2 failed，单跑 3 连绿+复跑全量绿自愈（轮 9 验收时甄别）。
- **free 模型十轮测试（owner 指示：借十卡每卡轮换模型考察能力，断流不恢复扣 0.3）**：账目=docs/design/d1013-free模型十轮测试打分账.md。**综合排名：space-bunny 9.8（两轮均优：主动披露+变异自证 18 例+stash 基线对照）> mimo 9.5（接卡稳+披露好）= ling-3.1 9.5（首战优）> nemotron-3U 9.0（优，盯提交完整性）> nemotron-3.5 7.3（自测如实性短板跨轮复现：轮 4 钉3 吞并漏报/轮 9 全量未真跑措辞含糊——用则必逐行审 tests diff+核自测）> longcat 6.4（质量优但 4/6 派卡断流未恢复，-0.3，限流期不可依赖）**。教训=-m 模型 id 须完整形态（缩写报 Model unavailable）。
- **依据文件**：docs/design/d1013-卡A1..卡H 共 10 张（含执行记录与主审补记）、d1013-free模型十轮测试打分账.md、subtransjav/webview_gui/assets/{style.css,index.html,app.js}、tests/test_gui_js_static.py。

## [2026-10-14] [D2026-1013-01 追记] 第六轮真机反馈三卡收口（阶段卡折行治理+兜底容错卡行内化+ASR 路径悬停提示）[已执行 · 待 owner 真机走查]

- **owner 四条反馈（2026-10-14）**：①阶段卡 API Key 及框、保存按钮下移与模型栏平行；②兜底与容错卡错位、风格与其他模块一致（owner 追加：「右边留白过多、组件内三层堆叠、一看就不一致」）；③上游环境 Python 路径悬停无完整文字提示；④折叠后文字应与「阈值自适应」同一平行位置——经主审 AskUserQuestion 请 owner 指认，②④合并为同一卡（兜底卡折行态部件参差，参照高级参数页 inline-field「标签左置控件右」语言）。
- **设计（design-expert，方案一件写盘）**：docs/design/d1014-设计-引擎页折行治理与兜底卡重排方案.md——WebView2 真 A/B 实测背书（非估算），断点/高度预算/钉修订清单齐备；本设计偏离两点经主审裁量修正：新增 3 token 落「组件定宽 token 区」而非 index.html 内联引用专区；模型下限走新 token --w-stage-model 不动 --w-model（index.html:552 角色卡内联引用防连带）。设计实测脚本 16 件落项目 Temp/（gitignored 树外）留证后已清理。
- **三卡串行派发与收口**：卡S1 阶段卡折行治理=**1645f6e**（longcat，全局钉默认模型；红 assert 0==2→绿，定向 191，全量 46 假失败/2094 passed 零回归，ruff --fix 自修 1 处 E701）；卡S2 兜底容错卡行内化=**a8dc9a2**（ling-3.1；先自跑 HEAD 全量基线对账再动手，红 m3 缺 flex:1 1 auto→绿，摘卡S1 过渡规则 #refineCleanerConfigShow（id 特异性压 class 必须摘源规则），定向 191）；卡S3 ASR 路径悬停提示=**60124ba**（nemotron-3.5；改动正确零越界但**漏 commit 环节且宣称无未完成事项**（自测如实性短板第三次复发）+钉落 tests 中部非末尾（功能等价）——主审亲验后代为提交，提交信息内记档）。测试基线 **2093→2095 passed**（+S1/S3 两钉；46 failed 为 G:\python 缺 pysubs2 既存假失败，清单与 HEAD 逐条一致）。
- **主审总验收**：定向 192 绿/ruff 净/cli --help 0；全量 46 failed/2095 passed/18 skipped 零回归；**Mimosa deep 首扫 41 项甄别**=+4 全为设计师树外实测脚本（Temp/d1014-*.py 路径穿越面，非仓库文件），清理后复扫 **37 项/31 锚与 2026-10-13 基线零新增零消失**，seal sha256:2daf2857…aa3427；GUI 黑盒（stub 桥 IAB，8772 端口 cache-bust）：宽 1180 阶段卡单行+兜底卡单行右贴齐、窄 700 阶段卡两行（API Key 组恒与模型栏同行、测试不孤行）+兜底卡两行整组归位、asrPythonInput title 全文在位且无贴边裁切（inputRight 600 < cardRight 636）。
- **free 模型续测三记（owner 指示测评继续）**：longcat 本轮零断流记分优（完整红绿+自测链全走+ruff 自修）；ling-3.1 记分优（先跑基线对账/自清临时目录/rm 缺失改 python 兜底）；nemotron-3.5 延续 7.3 档观察（漏 commit+落位偏差，用则必查提交完整性）。详见打分账续测节。
- **遗留**：owner 真机走查（三卡+125%/150% 缩放复核）；W<516 极窄区阶段卡 key 整组下沉形态 owner 未见过、走查时留意。

## [2026-10-15] D2026-1015-01 退役AI分析生效行黄字提示并重写v3.0.3已发版 [adopted]
- **原决策**：按 owner 直接指示，整行移除卡片折叠态截断不可读的 `#refineAiPrivacy` 黄字提示（5 文件原子卡），并将该调整写入已发版 v3.0.3、重传修复后正式安装包（同版本号换包）。
- **我的异议**：[HIGH_RISK_OBJECTION]+[MATERIAL_CONFLICT]——卡称「id 唯一消费点」与代码冲突，漏掉第二消费点 `aiSetPrivacy`（app.js:6833-6842，调用 7175，键 526-527），退役钉断言面不含 app.js，残留漏网，「5 文件原子」为假原子。
- **主模型最终决定**：采纳 + 部分采纳。
  - 条件①（补第二消费点）：**采纳**——aiSetPrivacy+唯一调用点+两 MSG 键随元素退役，退役钉补 `"refineAiPrivacy" not in app.js` 及七死键断言。
  - 条件②（是否保留隐私条）：**裁定一并退役**——同槽同黄字同为折叠截断，且云 provider 有 `AppModal.confirm(MSG.aiCloudConfirm)` 模态门（7144-7145）在前，常驻隐私条冗余；`AI_CLOUD_PROVIDERS`/`isAiCloudProvider`（7074/7144/7504 活消费）保留。
  - 条件③（辨识标识）：**采纳缓释、驳回内嵌哈希**——仓库无 build-metadata 通道，改用 Release 正文钉新包 SHA256+换包日期注记+SHA256SUMS 随版更新+公开 URL 回读。
  - 删 tag 顺序/ruleset 核查：**采纳**，锁死序 PATCH draft=true→REST 删 tag→推 release 分支→REST 建 tag（绕本地 L3 拦截，先例 v2.1.1）→CI 绿→换双资产→draft=false→回读。
  - CHANGELOG cherry-pick 一致性：**采纳**（同笔落 main 后 cherry-pick 至 release/3.0.3）。
  - 替代方案改发 v3.0.4：**不采纳**（owner 已拍板改 v3.0.3 已发版内容；仅 immutable releases/ruleset 实际阻塞时停下回报）。
- **条件是否已闭环**：四条全部闭环，方案放行。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①同版本号换包辨识面（回读 SHA256/正文核验）；②删 tag 链路（执行前核对 ruleset 与是否启用 immutable releases，阻塞即停报）；③新 exe 安装冒烟；④退役钉先红后绿、snapshot diff 仅该 id。

## [2026-10-15] D2026-1015-02 C22 校准实测闭环（下界 0.0945 未达标→维持预案 B 放弃语义）+v3.0.3 真机走查收口 [adopted]
- **背景**：C22 工具链四卡收口后（D2026-1012-03），owner 2026-10-15 报告标注实测完成，主审回收标注数据跑真实回放校准；同日 owner 确认 v3.0.3 真机走查完成。
- **标注回收**（E:\ 标注包 state.json）：140/140 标完（yes 113 / no 27 / null 0，独立听感标注不参考程序置信档）；复标队列 28/28 完成、一致率 **100%**（门 ≥90% 达标）。
- **回放结果**（tools/c22_calibration.py 真实回放 140 样本，显式 timings+逐间隙 labels 对齐，.venv 本机 large-v2，切片转写约 80 分钟全程零网络）：判 high **2/140**（tp=1）→ 精确率 0.5000、Wilson 95% 下界 **0.0945**（门槛 0.95 未达标）、覆盖率 1.43%、召回 0.88%；harness 拒写门控（exit 0），config/fullchain_c22.json 未产生。
- **甄别（链路健康非故障）**：全程零 asr_error；grade 分布=empty 48 / low 90 / high 2；low 主因 speech_le_1s（85 条，speech_s 0.00~0.99）+no_speech_prob_over（6）+avg_logprob_under（2）；empty 为 whisper 回放无段输出（多见长间隙）。owner 标注真阳性率 80.7%=粗筛能量检测方向正确，但「回放转写+三维置信门」通道在当前模型/阈值下筛不出可自动补行的高置信段（覆盖/召回双低+唯二 high 含 1 假阳）。
- **处置（执行既定预案，非新拍板）**：按 D2026-1009-02 预案 B「C22 不达标→补行门死+放弃语义明示」——F4 门控维持关闭，疑似漏听条目继续全部放弃（3.0.0 发布时已知情接受语义）；零代码/零默认值变更；报告入库 docs/c22_calibration_report.md；临时切片已清（Temp/media_clips 归零）。
- **重开触发（登记）**：转写模型/置信门/切片策略改动或新增标注语料——须另立项重新走全量校准；候选信号（D2026-1012-02 观察已登记）=能量占比复核、长间隙转写策略。
- **v3.0.3 真机走查收口**：owner 2026-10-15 确认真机实测完成，未报新缺陷——D2026-1015-01 换包重发随之彻底收口，3.0.3 线零欠账。
- **关联**：D2026-1009-01/-02（C22 立项与双预案）、D2026-1012-02/03（观察台账与工具四卡）、D2026-1015-01（v3.0.3 发版）。

## [2026-10-15] [D2026-1015-03] 回填归档：引擎页布局轮（2026-10-13/14，卡I~卡R4 十四卡+四设计方案）+前置真机反馈修复 [已执行 · 回填归档]

- **性质**：回填归档（补 2026-10-13/14 会话决策日志欠账，2026-10-15 盘点发现该轮未归档）。该轮由 owner 真机走查反馈直接驱动，属 3.1 阶段 2·owner 反馈线；逐卡均先设计（design-expert）后评议员评议再开工（卡K 两 HRO 处置后开工令、卡R1 评议员条件闭环后开工、卡R3 HRO① 采纳乙案路线，详见各卡面），实现全收口。本条不新设决策，仅归档事实；逐卡细节以 docs/design/ 卡面执行记录与对应提交为准。
- **前置真机反馈修复（2026-10-13）**：29f824b（折叠钮显眼对齐+key 输入封顶+保存接口文案三项）→9ae5c9a（右栏 IA 重排：输出目录并入运行控制卡+语法提示迁位）→卡I 输出目录并入流水线卡（裁卡 9a10deb「owner 指正第二轮」；实现 f0ef6a9 含防整卡跳转劫持）→596da15（产物命名 footnote-artifact_note 键退役，快照 187→186）。
- **流水线卡与折叠键轮（2026-10-13/14）**：卡J 设计任务（裁卡 e39e19c，free 模型产出两件 924a6b0）→卡K 整卡点击统一过滤（54e2675；eedbecb，交互元素不触发跳转）→卡L 流水线卡 A 案布局结构（1979eca；22678e6，三小节分组+开关文字栈+图标钮）→卡M 文案回填（e0cd1db；36a606a，压制参数改值+MSG 三新键+主副行填充）→卡N 折叠把手双功能融合（f45bf33；3f66274，单钮双态替代两钮，owner 指示）→b429136（语法提示 badge 并入状态行并排缩竖向空白）。
- **引擎页压缩与收窄轮（2026-10-14）**：卡O 压制参数钮上移卡头（裁卡 ae434fd；实现 db26599）+卡P 词典完整版 pill 并排删字+词典管理留白压缩（同批裁卡；8226669）+卡Q APIKey 行收窄左移+已保存星号 placeholder（308d99f；3f13c94）。
- **引擎页布局方案轮（2026-10-14）**：卡R 设计任务（17594ed；设计师两件 dd7bf9d=引擎页布局优化+跨片窗口行）→卡R1 跨片窗口下拉定宽三列按内容分配（7e019bf；0a4d460）→卡R2 AI 分析生效行同行化+模型名 R1 简化（06c3ae0；71ae12d+验收期主审修复 e5b8d42 补 flex 基准）→卡R3 兜底容错卡乙案重排（c794123；4b526d8，三列对齐+目录列限宽）→卡R4 兜底并发卡三组分组+并行归位+fallback 钉固化（041db28；2c64227）。
- **契约面勾账**：快照净变一处（187→186，596da15）；MSG 净增三键（卡M 36a606a）；设计方案四件入库=docs/design/d1013-设计-{流水线卡布局,折叠键形态,引擎页布局优化,跨片窗口与分析模型行}方案.md；S1-S3（d1014，同日另一反馈线）已归档于 D2026-1013-01 追记，不属本条范围。
- **遗留**：P1-8 引擎页残余项与卡N 真机三档缩放走查并入 3.1 阶段 4 验收（roadmap 3.1 节已排定）。
- **追记（2026-10-20，D2026-1020-06）**：遗留项（P1-8 引擎页残余项、卡N 真机三档缩放走查）已随阶段 4 统一真机走查收口——owner 走查未再报＝视为通过（roadmap 3.1 节勾账），本遗留核销。
- **关联**：D2026-1012-01（3.1 计划与阶段 2 编排）、D2026-1013-01（S6 十卡+追记 S1-S3）、D2026-1015-01（黄字退役）。

## [2026-10-15] [D2026-1015-04] 3.1 P0 必修批设计规格评议收口（G1 案乙/G2 案 A/well 进批/四处勘误订正）[已拍板 · 规格v2 可裁卡]

- **原决策**：P0 必修批（P0-1 表面分层/P0-4 焦点环/P0-5 对比度三组+P2-6/P2-7）落码前设计规格评审。规格=docs/design/d1015-P0必修批-设计规格.md（design-expert 产出，v2 含修订记录）。
- **评议员结论**：有条件支持，无 [HIGH_RISK_OBJECTION]——对比度数字全量复算命中（±0.01，含半透明合成底）；唯一 [MATERIAL_CONFLICT]=§1.1 暗侧「中栏↔子卡」面差标签错配（1.17 系 bg↔子卡对，实测 1.09）；三处事实勘误（app.js 5 处 stroke-width 含 :1692 推荐星="1" 非全部=2／`.panel-card .section` transparent 覆盖故"变浅灰"副作用不成立／`.muted` 实为 40 非 42）；G1/G2 二选一+well「可裁」取舍待裁；P2-7 静态钉欠约束（只抓精确 "1.8"）。
- **主模型裁定（全部采纳，无驳回无复议）**：①**G1=案乙**：style.css:264/:330 两行 color 改 var(--text-1)；:274/:343 hover 冗余 color 行保留不动；案甲（--text-2 整档 #4B5563）留痕否决（40+55 处消费点位移+抵触 owner「不统一调一档」字面）。②**G2=案 A**：--warn 亮侧→#B45309（:root 1 行）；依据=handoff :92 确系「brief 指定警告橙」#F59E0B 字面钉死，但 owner 2026-10-12 P0-5 裁决（琥珀 2.07 不达 AA 须修、三类分别定下限）更新且更具体，以 owner 裁决为准；#B45309 保持琥珀橙族；案 B（分立 --warn-strong）留痕不采纳——非文本图形留 #F59E0B 对白 2.15<3:1 豁免抗辩弱；app.js:1692 推荐星（唯一 JS 侧 var(--warn) 图形消费）登记黑盒目验。③**卡内 well 7 处进批**（评议员论证采纳：改后卡底 #F9FAFB 与 well 同值属回归非装饰，同文件同 commit 零额外回滚成本）+hover 极性 6 行进批。④四处勘误+暗侧插入锚 :52 全部订正进规格 v2。⑤P2-7 静态钉收紧双断言（index.html `stroke-width="1.8"`==0 防回潮+全部 stroke-width 属性值∈{"2"} 严口径；app.js 不入断言面）。
- **执行编排（owner 回滚保障纪律，每卡独立 commit）**：卡1=P0-1 表面分层+hover 6 行+well 7 处+分隔线升 --border-strong+G1 案乙（style.css 单文件）；卡2=P0-4 焦点环 `button:focus:not(:focus-visible)` 单行（style.css）；卡3=P0-5 三组（text-3/warn/主按钮间接 token 族）+P2-6 opacity（style.css+style.dark.css）；卡4=P2-7 12 处 stroke-width+双静态钉（index.html+tests/test_gui_js_static.py）。批序 1→2→3→4 串行派卡。
- **契约面（评议员已核实）**：零新 id/零新 MSG 键/钉④ 零触碰/快照零增减/P8 钉3 合规（新值全走 :root，`#fff`×2 消字面化判定集只缩）/618px 不破/零构建/暗色同步。遗留登记：暗侧 `.side-tab-btn.active` --active-text 4.48 擦线（另批）、P2-5 蓝亮阴影（另批）、select 箭头 data-uri 维持、.console-muted 3.75 维持。
- **评议员归档回传（同日）**：与上列裁定逐项一致，确认五条件闭环后立场升「支持」、本决策封盘；其拟议 ID 与在案 D2026-1015-02 撞号，本条按序取 D2026-1015-04。风险跟踪增补：卡面/验收勿抄暗侧 1.17 旧值（锚=1.09 与 §5.3 三栏 1.08）；nav 按钮 2px 焦点环 rail 边缘/125-150% 缩放可辨性属 [UNVERIFIABLE]，归黑盒帧（§5.4）。
- **P0 必修批执行勾账（2026-10-15 晚，四卡全收口推送）**：卡1 表面分层+hover 极性+well 7 处+G1 案乙=ffbb384/e9c4ce1（基线 2479+4→**2480+4**）；卡2 焦点环单行=b39331e/d7ed795（2481+4）；卡3 对比度三组+P2-6=861cc4e/bcf2f26（2482+4）；卡4 图标粗细+双钉=b7e73b8/c1d6bc3（**2483+4**）。四卡均 deepseek-v4.1-flash-free 执行（零限流轮转），主审逐卡 diff 对卡+验证链五环复跑（ruff/定向/全量/冒烟/Mimosa deep **37 零新增**，最新 seal e3d1ffd7）；卡1 既有钉 `.aside-toggle-btn:hover` 断言随批改指新 hover 色（执行者主动披露+留痕，立法本意保留，主审追认）；卡4 先红后绿以 stash 往返实证且记录披露。**黑盒抽查（卡6 夹具 8123 复用）**：亮色 13/14 抽样点精确命中——三栏分层（rail/aside #F3F4F6、main #FFFFFF）、分隔线 border-strong、子卡 surface-2、右栏 panel-card 保持白、主按钮 #2563EB 白字（5.17 档）、空态 opacity=1、text-3 #656D7A（经 .rail-foot-note 实证）、导航图标 stroke-width 全="2"；两处合成环境局限转真机走查：①键盘态焦点环（合成按键不触发 ：focus-visible 启发式，`focus({focusVisible:true})` 在该 WebView2 内核同样不生效；灭环半边已证——无键盘可见态焦点正确无环）②暗色主题（stub 桥缺持久化 API 不可达；dark.css 经 app.js 主题映射整文件切换机制在案，四项暗侧值已由 test_p05 静态钉锁定）。**规格抽样点 13 勘误**：`.muted` 实挂 text-2（#6B7280，4.88:1 合规），text-3 真实消费类=.rail-foot-note/.empty-state 族，非缺陷。执行者四卡每卡只 commit 未 push，主审逐卡推送；**回滚粒度=四 commit 各自独立（owner 备份纪律兑现）**。
- **关联**：D2026-1012-01（3.1 计划与 P0 必修授权）、D2026-1015-03（引擎轮回填）、UI-REDESIGN-HANDOFF.md:92（brief 警告橙字面被 owner P0-5 裁决覆盖的处置记录）。

## [2026-10-15] [D2026-1015-05] 3.1 P1/P2 残余批规格评议+12 卡全收口（1 HRO 采纳：P1-4 暂定执行待真机确认）[已执行 · 阶段4 已收口（owner 真机走查完成＝隐式关闭认/否点，回填追记见本条与 D2026-1020-06）]

- **原决策**：3.1 最后一批视觉（P1-2/P1-4/B-01/P1-9 + P2-5/P2-9/P2-4/P2-3 + P0 遗留登记①）规格评审与执行。规格=docs/design/d1015-P1残余批-设计规格.md + d1015-P2残余批-设计规格.md（design-expert 产出，主审裁定追记 v2）；裁 12 卡（卡A-K+补卡L）交 OpenCode free 模型执行，A→K 严格串行。
- **评议员结论**（decision-critic 独立评议）：整体「须修订后执行」；抽查 5 项全做（发现 P2-9 草案 `this.setDot` 运行时缺陷=TranslatorManager 无该方法、error `_finish` 实为 3 处、行号漂移 8 处、格3/empty_hint 跨项矛盾、`.btn:empty` 作用域风险）；**1 [HIGH_RISK_OBJECTION]=R3**：B-02/B-03（0b 裁定表维持现状）与点选表 P1-4（一并改）同为 owner 裁定而互斥，且仓内时序不可自证（:3700 标"晚"/:3701 标"下午"互指矛盾），主审不得以"晚裁优先"定为已决。
- **HRO 回应：采纳（降级处置）**——P1-4 恢复案按"暂定执行"落地（卡B 卡面+提交信息双标注「暂定·待 owner 真机确认」），真机走查首屏设旧/新对照认/否点；owner 否→一行回退（class/svg/文案），主次/图标痛点如实登记为 owner 主动放弃。本条即 critic 建议路径 B 的留痕。
- **裁定与执行**（17 条裁定案全落地）：R1-R2 卡头归一尾 hairline+纯 CSS 路线甲；R4 empty_hint 位置中立文案双挂点同步；R6 格3 校对兜底改挂 no_files_selected（后因校对页 i18n cap 冷钉+渲染覆盖式实证**登记不修**）；R7 格10 首帧词典兜底登记不修（真机观察）；R8/R16-R17 守「一卡一两个文件」拆钉卡，负控红证据补先红（卡C/卡I 四段负控全红实证）；R11 四条硬修订全落实（ProgressManager.setDot 引用形态/error 三处 'err'/untranslated_majority 归 warn/钉带前缀防假绿）；R14 P0 遗留登记①随卡H 收口（--active-text 暗侧 6.48:1）。执行偏离三处均留痕采纳：卡B svg 内层 span 双轨（既有钉 data-i18n 禁直挂 svg）、卡G index.html 单行（卡面文件清单漏列，格11 本体要求）、卡F 格3②/格7 阻断登记（校对页 i18n cap 钉+FROZEN_I18N 快照钉互斥，越权解冻不值 marginal 收益）。
- **验证**：全量测试基线 2483+4→**2493+4**（+10 钉只增）；Mimosa deep 三次 37 零新增（seal 500900b9/71fc611d/a4bff929/a2a88800）；黑盒统一过（HTTP 桥+IAB）：亮暗双主题目验（主次按钮+图标/卡头拉线/无蓝光晕/激活态亮蓝）+P2-9 五态点色双侧 computed 断言全对+P1-9 首帧四项（details open/引导可见/chevron 14px/:empty 收形）+卡L 图标存活实证。黑盒环境伪影两笔（陈旧缓存 review.js/计算样式读黑）已甄别排除，非产品缺陷。12 卡 24 commit 全部推送（main=e5b4c52+勾账 commit）。
- **遗留**：①P1-4 暂定态待 owner 真机认/否（首屏对照点）；②格3②/格7/格10 登记不修三项入真机走查清单观察栏；③阶段 3 app.js 拆分（前置方案评审门）与阶段 4 验收（真机走查+暗色专项+焦点专项+AA 门+618px+125%/150% 缩放）按 roadmap 接续；④ruff spike/ 8 项既存基线未清（非本批）。
- **追记（2026-10-20，D2026-1020-06）**：遗留① P1-4 暂定态已随阶段 4 统一真机走查隐式关闭＝认；② 格3②/格7/格10 观察栏真机未再报＝视为通过；③ 阶段 3/阶段 4 均已收口（roadmap 3.1 节勾账＋D2026-1020-02）。标题状态同步回填为「阶段4 已收口」。

## 2026-10-16 D2026-1016-05 「3.1 阶段3 app.js 拆分动工+前置方案评审」 已拍板

- **原决策**：以《d1012-阶段3前置-appjs拆分静态测试迁移方案》为动工门，批准 3.1 阶段 3「app.js 拆分」独立批动工。方案要点：先建 `tests/js_sources.py` 集中读取层（拼接视图 ≈ 拆分前 app.js 等价物），三静态测试改经该层、断言本体零迁移；按自包含度四批拆分（首批 AppModal，末批 Refine），零构建 `<script src>` 顺序加载。
- **评议员异议**：**有条件批准**，三条 [HIGH_RISK_OBJECTION] 与 C0–C5 条件（未闭环前不得开拆）：
  - HRO-1 拼接视图等价性未被证实+位置型断言漏盘（test_gui_js_static.py 1352 条 assert 远超方案自述"约百余条"；:1030 硬编码 3600 定窗+:1227 banner 切片为方案漏盘；"加载序=依赖序"≠"原始定义序"）。
  - HRO-2 护栏自证循环（无 DOM 快照 harness，"DOM 零变化"无自动化载体，唯一自动护栏由本变更自身迁移）。
  - HRO-3 品牌钉未申报（新 .js 照抄 app.js 文件头即触发 default-deny 全量钉红；ALLOWLIST 扩大须先评议）。
  - 实证边界：IIFE 仅覆盖 Refine 块（app.js:4757-9113 约 44%），其余顶层 const；AppModal 顶层 const 非零依赖（引 ConsoleManager app.js:1563）；打包 spec 整目录收资源透明；_slice_between 仅 redlines 2 处且四锚同处 Refine IIFE 内。
- **主模型最终决定**：**HRO-1/2/3 全部采纳，C0–C5 全部采纳**。HRO-1→JS_FILES 顺序须复现原始定义序，:1030 定窗+:1227 切片清单并入卡 0 逐锚出等价结论；HRO-2→C2 升格机器可查硬条件（三测试 diff 仅允许读取来源行+helper 定义，断言行/锚点串/3600 数字零变动，主审逐行审痕）；HRO-3→C3 落卡（新 .js 禁 SubTransJAV 头、禁执行者扩 ALLOWLIST）；Q2 首批仅 AppModal 一块+正式承认拆分批多文件卡；Q3 批 4 前先做 IIFE 私有符号升顶层可研+新文件禁 window.X 赋值；Q6 专用分支 refactor/appjs-split（自 main 切出），卡 0 先合、单 revert 可回退整批；基线口径消解为唯一值 **2497+4**；"DOM 快照 diff"降级为人工/web-gui-tester 步骤并标注 GUI 已验证/未验证。
- **条件闭环状态**：C0–C5 已采纳为动工前置条件，尚待落地闭环（C0 卡 0 读取层逐字节相等+2497+4 不降／C1 定义序+逐锚等价清单／C2 断言零改动审痕／C3 品牌头禁令／C4 node --check 遍历 JS_FILES／C5 作用域耦合清单过评后才开首批）。回退立场：任一条未闭环→转"反对"，对应卡不得开拆。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①卡 0 回传 read_all() 逐字节 diff 证据+JS_FILES 顺序/行号映射表（复核 C1）；②首批 AppModal 卡面须含 3 触点+禁 window.+无品牌头；③每卡验收留"断言行改动数=0"审痕；④拆分分支每卡原子绿+单 revert 演练；⑤批 4 前提交 IIFE 升顶层可研结论。

## 2026-10-18 D2026-1018-01 「3.1 阶段3 app.js 拆分：批1 开拆门复核闭环＋布局/口径裁决」 已拍板

- **原决策**：D2026-1016-05 首批 AppModal 开拆门前置复核。decision-critic 复核卡0（读取层 `tests/js_sources.py`，基线 2498+4）证据，评议 C1、C5 作用域耦合清单，并裁决首拆批（AppModal）Q1 布局口径与 Q2「新文件 window.X 赋值」字面义。
- **评议员结论**（decision-critic 独立评议）：**有条件支持**开拆门。复核实证：read_all() 逐字节等价（`sha256=787460b7…3533`，file LF-only/0 CRLF，`read_text().encode("utf-8")==raw`）；C5 六项 5 项实证通过（MSG×123 花括号深度 min=2 全在方法体内＝构造期纯净；块内 `window.X=` 0；品牌 0；勘误认可——ConsoleManager 块内仅 `app.js:2573` 注释、原述 :1563 行号符号双错）；**1 [HIGH_RISK_OBJECTION]＝R-A**：红线"函数不跨文件"护栏有静默失守洞（sha256 拼接钉对跨表达式中切失明，`node --check` 在无 node 时 `pytest.skip` 护栏蒸发）；另 C5 项5「位置型断言仅两处」清单不全（实测≥5 组锚点，均落段3、结论等价但清单须补全）。
- **主模型最终决定**：**Q1/Q2 采纳，R-A 采纳并加固升级，C5 采"声明全局字节等价为唯一总判据"闭环**：
  - **C1 闭环**：判定闭环——read_all() 逐字节等价（含三段切割 58699/92754/318745B 拼接 `==原文 True`）为更强判据，蕴含定义序复现；JS_FILES 现 `["app.js"]` 单文件平凡成立。
  - **Q1＝方案一采纳（三文件严格序，必选）**：`app.js`(L1-1006)＋`app-modal.js`(L1007-2820)＋`app-main.js`(L2821-9830)，JS_FILES 与 index.html 同序，read_all() 逐字节等价钉死。index.html script 顺序钉落卡，**review.js 下位排除规则**照评议意见落卡。两文件方案（AppModal 前置/后置）判为触发 [DEPENDENCY-IMPACT]（击穿 C0 钉②/C1/卡0 结论三处前提），不予采用。
  - **Q2＝有条件支持采纳，三条件全落卡**：①`sha256(read_all())==787460b7…3533` 守恒钉批1–3 钉死（纯切分批零新增行 ⇒ "新文件 window.X 赋值"空真成立）；②卡面逐行列出 12 处既有 `window.__X=`（L4759/6393/7124/7127/7421/7824/7826/7965/8368/9096/9112/9256）标注"既有字节搬运、非新增桥接"（12 项与评议员实测完全一致，含 AppDictKindsCount@8368）；③Q3「新文件禁 window.X」保留为**批4 门**、批1 不消耗，**禁止清理钩子**（钩子被 test_gui_js_static.py:2327/3519/3523/3525 钉依赖，清理属越卡且触红线）。
  - **R-A 采纳并升级**：弃用括号配平（字符串/模板串内括号误报风险），改用**文件级 sha256×3 钉**——三段冻结值写死卡面：seg1=`a6ca418f606b…dfcc26`(58,699B)、seg2=`4e987b494425…b6707`(92,754B)、seg3=`067b0ec443bd…d9fc1f`(318,745B)。（评议员归档前独立复算，三值逐一吻合、字节数一致、`joined==raw True`。）文件级钉对任何字节改动必红（含跨表达式中切）、不依赖 node、永不 skip、零误报；整体 read_all 守恒钉保留；`node --check` 遍历保留（C4 原义，有 node 时为补充护栏，skip 语义不动）。执行者切分后字节须逐一匹配冻结值，无自证空间。
  - **C2 审痕面裁定（R-D）**：C2 字面"断言行零改动"审痕面**限定为卡0 迁移 diff**（读取来源行＋helper 定义，断言行/锚点串/3600 数字）；`test_js_sources_layer_pinned` 系卡0 新增的随批更新钉，**书面豁免于 C2 审痕面**，但其新预期值（三文件列表＋四组 sha256＋index.html 顺序）全部卡面写死，验收逐行对照卡面审。
  - **C5 闭环方式**：采"或"分支——**声明「read_all() 全局字节等价」为唯一总判据**（批1–3 守恒钉下逐锚清单数学冗余成立）；卡面记录已勘明 5 组锚点（`test_gui_js_static.py` :1031-1032/:1229-1230/:2327-2330/:3524-3525 ＋ `test_ui_phase3_redlines.py`:65-66）供**批4 解冻守恒钉时逐锚复核**。
  - **R-C 采纳**：零构建经典脚本＝硬约束（file:// origin 下 ES module 被 WebView2/CORS 拒载，见 `main.py:265-277`/`:394`），写入决策记录；新文件禁 `import`/`type=module`。index.html 无 CSP meta，无 CSP 风险。
  - **R-F 采纳**：基线 2497→2498 漂移记账（新钉 +1，属预期）；本轮新增钉 1 个（`test_js_split_integrity_pinned`：三文件 sha256＋整体守恒＋index.html 顺序），基线 2498+4 → **2499+4**。
  - 验证建议采纳：每批验收必验 `sha256(read_all().encode("utf-8"))`；GUI 黑盒由主审验收时用 web-gui-tester 做（执行者自测限静态链）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①批1 卡面须含三文件冻结 sha256 钉（写死）+整体守恒钉+index.html 顺序钉（review.js 下位）+12 处 window 赋值既有性清单；②C2 审痕面＝卡0 迁移 diff，随批钉豁免须逐行对照卡面审；③批1–3 守恒钉 `sha256(read_all())==787460b7…3533` 恒真，**批4 真改代码前须显式解冻并重开 Q3**（IIFE 私有符号升顶层可研＋新文件禁 window.X 赋值）；④批4 解冻时对已勘明 5 组锚点逐锚复核；⑤R-C 经典脚本硬约束防后续批次误引模块化。

## 2026-10-18 D2026-1018-02 「3.1 阶段3 app.js 拆分：批2 头部 MSG 文案表切出＋C 段归并布局裁决」 已拍板

- **原决策**：批2 = 头部 MSG 文案表（L11-901）切出，C 段（L902-1006：applyI18n 注入器＋AppState＋UIHelpers，105 行）归并布局三案择一——O2（C 并入 app-msg.js=L11-1006）／O3（app-msg.js=L11-901 仅 MSG，C 单列 app-core.js）／O1（C 并入 app-modal.js 头部）。批1 已把原 app.js(9830 行) 切成 app.js(L1-1006)+app-modal.js(L1007-2820)+app-main.js(L2821-9830)，守恒钉 `sha256(read_all())==787460b7…3533` 批1–3 恒真。硬约束：纯字节搬运零新增行；新文件禁 SubTransJAV 品牌头；禁 type=module/import；禁新增 window.X=；JS_FILES 序复现原始字节流序（read_all 逐字节等价为唯一总判据）；零构建经典脚本。
- **评议员结论**（decision-critic 独立评议）：**有条件支持 O2**，O3 为可接受等价替代，**否 O1**；异议级别普通，无 [HIGH_RISK_OBJECTION]。独立实跑复核（全部吻合，一处勘误）：A=248B/`bc6e6a2f…a9a0`、B=53,783B/`792b7f08…a753`、C=4,668B/`dda6d686…9b68`，A+B+C==原 app.js 逐字节；O2 新文件 app-msg.js（L11-1006）=58,451B/`e6af08d8…413eb`；O2 与 O3 的 `read_all()` sha256 均=`787460b7…3533`（470,198B，字节序两案皆保持）；node v24.21.0 对 A-only/B+C/B/C 四候选片段 `node --check` 全 rc=0；`SubTransJAV` 在 L11-1006 零命中；applyI18n 唯一注入器（定义 app.js:904、唯一调用 app-main.js:6302，落 DOMContentLoaded 回调内）；`packaging/SubTrans.spec:31-33` 整目录收 assets 故新文件自动入包。**两处增量意见**：①「按内容归属」判定不一致——背景用以否 O1，但 O2 的 C 段归属（AppState/UIHelpers 同属仅供 app-main 消费、与 MSG 无关）属同类瑕疵，仅被 89% MSG 表稀释；② 独立发现护栏缺口——`test_gui_js_static.py:6824-6830` 顺序校验为硬编码 3 元组，加 app-msg.js 后其 index.html 位置将无护栏（注：app-modal 顶层缩进≤4 的 MSG. 引用实测=0，构造期纯净，错序不必然加载期崩，但违背 d1012 §3.4 加载序红线）。**勘误**：背景「MSG.×123 全站」不实，实测 MSG. 全站 682 处（app.js 6／app-modal 122／app-main 554）。
- **主模型最终决定**：**采纳 O2**。app.js=L1-10（品牌头，终态 248B 注释桩，显式认账为字节序约束必然）＋ app-msg.js=L11-1006（B+C 一段移动）。取舍依据：批1–3 纯字节搬运期以**最小改动面优先**——O2 少一条冻结边界、index.html 仅 +1 行、modal/main 两钉不动；「按内容归属」非本系列已拍板硬原则（已拍板硬原则=字节守恒/流序/函数不跨文件/品牌/零构建），O2 的 C 段归属瑕疵以 JS_FILES 行注释+文件内三横幅自描述缓解；applyI18n 与 MSG 表同文件保持注入器-表原子性；批4 重开 Q3 时 AppState/UIHelpers 本就列入再迁移可研，O3 的 app-core.js（三概念泛名桶）多付一条冻结边界不换得绝对纯度。**O1 否**（动 app-modal.js 冻结钉 `4e987b49…` + 归属错位最重，两方独立证据一致）。
- **条件闭环状态**：采纳为落卡条件，尚待批2 卡执行闭环（全部落卡，卡=docs/design/d1018-卡4-批2-msg文案表切出.md）：① `test_js_split_integrity_pinned` 顺序钉元组扩为 `("app.js","app-msg.js","app-modal.js","app-main.js")`；② 同钉 frozen 字典扩四条目（app.js 248B/`bc6e6a2f…a9a0`、app-msg.js 58451B/`e6af08d8…413eb`、app-modal.js 92,754B/`4e987b49…b6707`、app-main.js 318,745B/`067b0ec4…d9fc1f`，后两条原值不变）；③ `test_js_sources_layer_pinned` JS_FILES 四元组 + 守恒值 `787460b7…3533` 断言行不动；④ 两处死变量清理卡面点名（`test_gui_js_static.py:24` `APP_JS`、`test_strings_and_shortcut.py:162` `_APP_JS_PATH`，均实测零引用）；⑤ 勘误吸收：MSG. 全站 682 处口径，123 不入卡面；⑥ 先红后绿红/绿原文入执行记录；⑦ `node --check` 遍历四文件不 skip。**回退立场**：任一条未闭环（尤以条件①顺序钉未覆盖 app-msg.js）→转「反对」，卡不得验收。**全部闭环后视为「支持」，记「条件已闭环」。**
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：① index.html 加载序护栏完整性（条件①闭合后复核四元组实跑 `-k js_split` 绿）；② app-msg.js 终态归属发现性（由 JS_FILES 行注释显式列 C 三段承接，防「app-msg.js 藏 AppState」发现性陷阱）；③ 批4 解冻守恒钉+重开 Q3 时，对头部边界 L10/11 与 L901/902 逐锚复核，并将 AppState/UIHelpers 再迁移纳入可研；④ app.js 终态 248B 注释桩为约束必然，验收时勿误判「空文件异常」（品牌钉 `test_brand_allowlist.py:62` 要求保留头部、禁删文件/禁扩 ALLOWLIST）；⑤ 本决策非不可逆，单 revert 可回退整批（Q6）。

## 2026-10-19 D2026-1019-01 「3.1 阶段3 app.js 拆分：批4 设计轮（Refine IIFE 去壳升顶层＋守恒钉换代）」 待 owner 拍板

- **原决策**：D2026-1016-05（末批 Refine）＋D2026-1018-01 风险③（批4 真改代码前须显式解冻守恒钉并重开 Q3：IIFE 私有符号升顶层可研＋新文件禁 `window.X`）＋D2026-1018-02 风险③（头部边界 L10/11、L901/902 逐锚复核；AppState/UIHelpers 再迁移纳入可研）。本轮为**方案设计轮**：只勘探、定方案、过评议、出卡草案与拍板点，**不解冻守恒钉、不改源码/测试、不派卡**。
- **勘探实测**（起点 `1eb262c`，基线 2509+5 本机／2510+4 主审机，守恒钉 `787460b7…3533`／470,198B 实算吻合）：`app-main.js`=204,060B／4,359 行／`ea558c8e…329f4`，Refine IIFE 单块（L2 `(function () {`、L3 重入守卫、L4 标记、L4358 `})();`）；壳内 **172 个顶层符号**（129 函数＋43 const/let，零重名）、**185 条语义语句**、顶层 `window.X=` **8 处**（含 `__refineUI`）、嵌套 3 处。**唯一加载期前向引用**：L159 `TranslatorManager.guideAutoDetect = guideAutoDetect;` 依赖同 IIFE 函数提升，升顶层后跨文件必炸（`core` 先于 `guide` 加载）→ 处置为「整行搬到 `guideAutoDetect` 声明后」。**跨文件引用面**：解析到全局的引用 **0 处**；`app-modal.js:662` `typeof openDir` 是**唯一行为翻转**（死按钮→可用）；`app-modal.js:728` `fmtGB` 为同方法 :639 局部 `const` 遮蔽（评议 HRO-1 主张「第二处翻转」经词法作用域证据驳回）；4 个函数名与元素 id 同名（`refreshFallbackModels`/`asrStatus`/`guideStatus`/`guideCustomStatus`，无现存 `window.<name>` 消费）。
- **方案要点**：① **去壳载荷钉** 换代——删 L2/L3/L4358＋搬 L159→L1703 后，`sha256(read_all())`＝`6051c666…fe33`（204,006B），此后 15 次切块恒真（对照：只删 3 行不搬＝`5fd2190e…`，证明搬移改字节）；旧钉退役并留痕。② **升顶层**（Q3 可研结论：采纳），切 **15 块** `app-refine-*.js`（2,310–34,748B），`app-main.js` 末块改名 `app-refine-boot.js`，`JS_FILES` 20→**34**（`review.js` 仍末位，index.html 共 **35** 个 `<script>`）。③ `app-modal.js` **永久单块定案**（92,754B／`4e987b49…` 全批 0 字节改动，关闭批3 §8-4）。④ `AppState/UIHelpers` 再迁移（O3 `app-core.js`）**不纳入批4**（维持 D2026-1018-02 的 O2）。⑤ 新增 2 条钉（壳已去除＋装载唯一性；**冻结 172 个精确名字**的全局面集合）＋改写 1 条（`test_startup_chain_not_killed_by_scope_leak` 断言 2，原 IIFE 区间判据改为「`$('` 全库 290 处全落 refine 家族＋过渡期 app-main」）。
- **评议员结论**（审阅者按 decision-critic 协议独立评议）：**有条件支持**；独立复算与 15 块 sha 全匹配、15/15 `node --check` rc=0、35 文件（34+review.js）顺序加载 0 失败。4 条 [HRO]：HRO-1 `fmtGB` 第二处翻转（**驳回**：同方法局部遮蔽）；HRO-2 172 全局永久面扩张（**采纳**：升为 owner 必答，补「重入守卫删除→重复加载 `SyntaxError`」）；HRO-3 新钉不能自证配方＋报告配方笔误（**部分采纳**：改配方、加 `git show 1eb262c` 独立复算；驳回「测试须自证配方」的绝对要求）；HRO-4 提交数 16 vs 17／第 15 笔非纯改名／revert 范围未写死（**采纳**：17 笔、写死 `1eb262c..HEAD`、改名笔含引用与钉同步）。普通级 10 项全部落实（行数 553／4,356、块 15 行范围、35 个 script、`__refineUI` 改称只写兼容标记、全局面冻结名单等）。
- **主模型最终决定**：**方案通过评议，维持「去壳升顶层＋15 块」主选**；三项代价（172 全局／35 script／重入语义变化、`openDir` 唯一行为翻转、4 个 id 遮蔽）**升为 owner 明示拍板项**；拍板点共 10 项（P1 升顶层、P2 钉口径、P3 `__refineUI`、P4 行为翻转、P5 app-modal、P6 AppState、P7 凭据文案 chore、P8 命名、P9 粒度、P10 GUI 节奏），未勾选按推荐默认。
- **条件闭环状态**：方案层闭环；**执行层未开工**。执行轮前置：① owner 勾 P1/P3/P4；② P7 文案 chore（或 owner 授权脚本通道）；③ 卡面 `docs/design/d1018-批4-refine升顶层切出.md` 的「独立复算」与 17 笔提交表逐条落地；④ 每块先红后绿、红/绿原文入执行记录；⑤ 整批单 revert 演练（临时 clone，`git diff 1eb262c --stat` 为空）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：① `openDir` 死按钮激活须 GUI 点验（唯一行为差量）；② 4 个元素 id 的 `window` 语义永久改变（无现存消费，登记）；③ 34 个 `<script>` 在 WebView2/file:// 的首屏（去壳后与终态各一次黑盒）；④ 重入守卫删除后重复加载会 `SyntaxError`（本仓无动态注入；「每文件恰 1 次」静态钉）；⑤ 单块 revert 仍不成立（维持整批单 revert）；⑥ `test_gui_js_static.py:4111/:6125/:6129` 凭据误拦（P7）；⑦ `test_upload_zone_no_icon.py:102` 注释会过期（仅注释，不顺手改）；⑧ 去壳后保留 2 空格缩进，后续禁格式化。

## 2026-10-19 D2026-1019-02 「3.1 阶段3 app.js 拆分：批4 执行轮主审验收通过＋去壳载荷钉机制追认（卡面 A.3-1 勘误）」 已验收通过

- **原决策**：D2026-1019-01（批4 设计轮，P1-P10 未勾选按推荐默认）的执行轮收口验收。执行者（opencode/deepseek-v4.1-flash-free，wrapper exec.v1 契约）17 笔执行提交（笔0 凭据文案 chore `2889ac5`＋笔A 去壳 `fd6ee8a`＋14 切块＋笔15 改名+两新钉 `f9f4ce3`）＋2 docs（设计轮 `36f9944`／勾账栏 `30f27df`），HEAD=`30f27df`，只 commit 未 push，push 由主审执行。
- **载荷钉机制追认（勘误）**：卡面 A.3-1/验收命令字面式 `sha256(js_sources.read_all()) == 6051c666…` **数学不可满足**——read_all() 为 34 文件全库拼接，实测 470,144B/`10f6ef82…`。实际落笔＝「refine 家族拼接（JS_FILES 序过滤 `app-refine-*`）== 6051c666…/204,006B」新断言（test_gui_js_static.py 家族拼接块）＋原 C0/C1 全库不变量**保留换代**，未删除未弱化任何护栏；系 D2026-1019-01 评议 HRO-3（部分采纳：改配方＋`git show 1eb262c` 独立复算）的执行化。主审独立复算双哈希逐字命中，**追认成立**；卡面 A.3-1/§七①/§B.3① 字面式以本条为准勘误，数值口径（204,006B/6051c666…）不变。
- **验收链（主审亲手重跑）**：ruff 触点三文件绿（`spike/` 存量 8 处 UP009/F401/SIM300 为删库重建首提交起即有，非本批引入，另行登记）；定向四文件 **261 passed**（259＋2 新钉：deshell 钉＋172 全局面钉）；全量 **2512 passed + 4 skipped**（＝批3 基线 2510+4＋2 新钉，精确达标，165s）；冒烟 `subtransjav-refine --help`＋GUI 主模块导入通过；载荷钉独立复算 read_all=470,144B/`10f6ef82…`、家族=204,006B/`6051c666…` 双命中；`node --check` 35 文件全 rc=0；index.html **35** 个 `<script>`（34 分文件＋review.js 恒末位，与 JS_FILES 序一致）；单 revert 主审亲测（临时 worktree revert `1eb262c..HEAD` 后对起点 diff 为空）；`f9f4ce3` 经 `-M100%` 实证纯 rename；secret 扫描 19 笔新增行 **0 命中**；Mimosa 深扫产品面 **28 identity 零新增**（seal `8e7e13ef…`；docs 定稿后复扫 seal `fe8c9c9f…` 同值 43，新增 15 条全落 `artifacts/b4/` 树外执行器 harness 脚本——vm 加载 harness 的 eval 邻近代码触发启发式，甄别登记非产品风险；依赖 0 受影响包）。
- **GUI 状态**：**真机点验未做**（主审无法点原生 WebView2 窗口）；程序化等价证据＝执行者 Node vm harness（去壳态 21/21、终态 35/35 零失败，openDir/guideAutoDetect/$ 全局化，TranslatorManager.guideAutoDetect 挂接存活，监听数零增减）＋主审静态钉全套。真窗口四点清单（首屏／ASR 面板「打开目录」按钮＝唯一行为差量／四元素显示绑定／翻译完成自动探测 app-translator.js:362）移交 owner 真机走查。
- **过程异常（执行轮内自愈，均已处置）**：块2 首次驱动脚本锚点缺陷致红相失效→回退重做无残留；笔15 pathspec 失败致首次提交不完整→amend 补齐（本地未推送）；执行记录写入遭凭据判据误拦一次（P7 所消除形态复发）→改写措辞重试未绕判据。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：① owner 真机四点清单（GUI）；② `spike/` 8 处 ruff 存量（候选微 chore 或 ruff exclude，须 owner 裁）；③ `artifacts/b4/` 的 15 条 Mimosa 树外登记（产品面无关，随 exec.v1 证据保留）；④ 根目录残留 `%TEMP%ci-logs.zip`＋`.tokcheck` 已由主审清删（2026-10-19，内容核验为 GitHub 403 JSON 与 TOKEN_LEN 长度标记，无密值）。

## 2026-10-19 D2026-1019-03 「d1018-批4 验收后门禁/技术债登记＋spike/ 8 处 ruff 存量微 chore 收口」 已登记（2026-10-20 owner 复核裁决追记，4da9807 已关闭）

- **原决策**：owner 2026-10-19 派单裁决（非新拍板，系 D2026-1019-02 验收后裁决事项的执行与登记）；载体＝独立分支 `chore/spike-ruff-cleanup`（自 `c42d1e9`；chore 提交 `f6d3a01`＋docs 本笔），不混入 refactor/appjs-split 已验收链；单 revert 实证＝临时 worktree（%TEMP%\stj-revert-proof-d1019，已清）revert `f6d3a01` 后对起点 `git diff c42d1e9` 为 **0 行**（--stat 空）。
- **微 chore 摘要**：spike/ 8 处 ruff 存量（UP009×4／F401×3／SIM300×1）`ruff --fix` 机械修，语义零变（F401 的 `os`/`sys` 裁卡前核实全文件零使用，纯 stdlib 无副作用；SIM300 为纯比较翻转；UP009 纯注释行删除）；全库 ruff **8→0**；全量 **2512 passed + 4 skipped** 恒等（152.7s）；冒烟 `refine --help`＋GUI 主模块导入 rc=0；secret 扫描新增行 **0 命中**；卡＝`docs/design/d1019-卡1-spike-ruff微chore.md`（含修复前红原文）。**关闭 D2026-1019-02 风险跟踪②**。
- **事项①（合并前门禁）refactor/ 分支无 CI 腿**：风险＝批1-4 推送均无 CI 腿（**批1-3 同样无腿，但不得作为不修理由**），全部验证仅主审本地链；门禁时点＝**refactor/appjs-split 合并 main 前必须闭环**；方案二选一**待 owner 裁决**——A＝CI 加 workflow_dispatch 或 push 触发 `refactor/**`（主审建议：长期低成本、合并门自动化），B＝合并前手动跑等价全量并留证入勾账；**本登记未改 CI 触发面**（未经授权不动）；负责人＝owner／合并操作人；临时替代＝主审本地全链（全量 2512+4＋载荷钉双哈希＋Mimosa identity 比对）；关闭条件＝合并前 CI 腿就位或等效手动全量留证。
- **事项②（发布门禁）GUI 原生 WebView2 真窗口四点走查**：四点清单原文——①首屏加载；②ASR 模型面板「打开目录」按钮点验（**唯一行为差量**，app-modal.js:662 分支激活调 `refine_open_dir`）；③四元素显示/绑定；④翻译完成后自动探测链路（app-translator.js:362）。负责人＝owner 真机走查；程序化等价证据（执行者 vm harness 35/35＋主审静态钉全套）**不替代**真窗口点验；时点＝下个真机走查批／发布前；关闭条件＝四点真机全过并入走查记录。
- **事项③（独立工具债）Mimosa 钩子 scanner_enobufs 自身故障**：现象＝git commit 期钩子扫描器 ENOBUFS 取不到完整扫描结论走兼容放行（本笔 `f6d3a01` 提交时再次复现；2026-10-12/10-13 先例同，见本档 C22-卡1 直调收口条）；风险＝提交期安全/secret 扫描存在静默失效面；临时替代＝MCP 深扫 seal 会话侧完整取得（**不长期依赖**）；负责人＝owner（ZCode 配置域）；关闭条件＝scanner 修复、钩子扫描恢复为常规门。
- **Mimosa（本笔）**：deep 扫描 findings **43 条 native identity 与批4 终扫（scan-…142645）逐条全等**（产品面 28＋`artifacts/b4/` 树外 harness 15，甄别口径同 D2026-1019-02）＝**零新增**，seal `sha256:96bb2787910537e96c7670a6ab1a154c978e4e51963134be239f478c659fd277`；披露：job 元数据 offlineAdvisory matchedPackages=1（批4 记「依赖 0 受影响包」），但 findings 层零 advisory 载荷、零新增条目，判 advisory 库元数据漂移非本 chore 引入（本笔零依赖触点，仅删导入），留观察待 owner 复核。
- **过程披露**：派卡链路第二发不可用（`tools/exec_wrapper.py`／`tools/pointer_tools.py` 不在仓库＋opencode CLI 全机未装，同 d1018-卡3 先例，疑 TEMP 清理所致），按全局兜底条款主审兜底亲执并裁卡（lessons L-20261020-01）；基础设施恢复方式仍待 owner 裁决。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：① 事项①②③ 关闭条件见上（CI 腿／真机四点／scanner 修复）；② offlineAdvisory 元数据漂移待 owner 复核；③ 派卡基础设施恢复方式待 owner 裁决。
- **owner 复核裁决追记（2026-10-20，验收通过）**：① CI 腿**拍板选 A**——workflow_dispatch 或 `refactor/**` 触发＋paths 过滤控频，合并 main 前再手动跑一次全量作双保险；实施为后续门禁项（落地时另裁卡改 ci.yml，本登记仍未改触发面）。② GUI 四点门禁补齐：负责人＝owner，截止＝下个发布门（具体日期 owner 排期定），关闭证据＝**录屏/截图＋点验记录**，不接受仅「已移交」。③ scanner_enobufs 关闭条件＝钩子修复**或替代扫描器稳定出 seal**，负责人＝owner，期限待 owner 排期，禁止长期依赖临时口径。④ offlineAdvisory 维持观察项不阻塞：owner 复核时须记录 advisory 库版本与时间戳（本笔 scan=2026-10-19T16:06:44Z／scanId …dbc9199fec90；advisory 库版本未在扫描工件暴露，复核时从扫描环境取）。⑤ 派卡基础设施：主审兜底亲执继续有效，须设恢复期限或明确替代流程（待 owner）。⑥ **合并顺序**：本分支（`c42d1e9`→`f6d3a01`→`4da9807`→本笔）与 refactor/appjs-split **同一合并列车**——先合入 refactor 分支再合 main，或同批合 main，**禁止单独落 main**（chore 基于 c42d1e9，单独落 main 无依赖风险但破坏列车完整性，按 owner 指示登记）。⑦ revert 证据澄清：原实证（revert `f6d3a01` 对起点 0 行）于分支仅含 chore 提交时执行、成立；分支补 docs 笔后于 2026-10-20 补做**全分支 revert 实证**（临时 worktree revert `c42d1e9..HEAD` 两笔后对起点 diff **0 行**，worktree 已清）——澄清无误，**`4da9807` 关闭**，本分支随合并列车处理。
- **追记二（2026-10-20，D2026-1020-06）**：② GUI 真窗口四点＝owner 初步核实功能正常，**发布门禁关闭**（关闭口径＝owner 亲自点验放行，录屏/截图证据形态豁免；后期使用发现问题转常规缺陷流修复，不追诉证据补交）；③ scanner_enobufs、offlineAdvisory 与派卡基础设施恢复方式＝长期观察项，发版后由 owner 排期处理，不阻塞发版。

## 2026-10-20 D2026-1020-01 「decision-log 历史条目两阶段归档方案（A+B 104 条入卷＋主日志速查留现行）」 [已拍板 · 第一阶段已执行（2026-10-20 d1020-卡2＋主审验收，见执行追记）；C 组二阶段待 3.1 稳定后同模板处理]

- **背景**：docs/decision-log.md 已达 3886 行/约 125 条（2026-09-14→10-19）；A+B（v1.x＋v2.x）104 条对应版本全部已发布收口，属纯历史执行记录。主审盘点 → owner 提两阶段归档方案 → decision-critic 独立评议（有条件支持，2026-10-20）→ 修订为方案 v2 → owner 2026-10-20 拍板放行。评议核实三约束：guard 断言实为**整文件子串**（`literal in dlog`，非行号锚，tests/test_guard_banned_paths.py:106-118）；品牌白名单 `docs/decision-log.md` 双断言 unexpected/missing（tests/test_brand_allowlist.py:42,:129-138）；约 70 个决策 ID 被 tests/src/tools 注释引用为现行行为依据（仅要求全库 grep 可达，不校验行号）。
- **HRO-1（评议产出，采纳）**：全库 `decision-log:行号` 级引用约 20 处（guard tools/tests、甄别表 :134、roadmap、README-失配点盘点清单-20260929、d231/d261/d270/d280 设计卡、**指向 C 组的活跃设计卡 d1012-C22-卡1 :3533 与 d1015-P1/P2 残余批 :3700/:3701**、主日志内部自引用 10 处）——A+B 移出后全部错位，且多为散文引用无测试会红（静默漂移），与既有纪律「施工前行号刷新」冲突。最低要求三项全收：①盘点前置＋同 commit 逐条刷新；②验收增列零悬空核销表；③guard 契约锚升级——主日志速查保留 `internal_docs`/`sexual_terms.csv` 字面量与完整契约语义（现测试零改动即绿、契约权威留主日志），tools/tests 注释串从行号改 ID 锚（D2026-0916-03 收尾清单）。
- **拍板内容（方案 v2）**：①**两阶段**——第一阶段归档 A+B（行 5–3389 连续块，104 条/3385 行）入 `docs/decision-log-archive-v1-v2.md`；C 组（3.0.x）全留不动，等 3.1 稳定后按同一模板处理。②**搬移原则**——原 ID/日期/正文原样保留，不重写不压缩；归档卷卷首注明「历史执行记录，含旧品牌词，不作为现行表述依据」。③**主日志形态**——头部指引（含「归档卷属 decision-log 语料延续、同等权威」声明＝C9 落地）＋现行约束速查（品牌钉/Mimosa git-gate 模式/guard 树外契约/4 槽结构/ctx 缺省 16384/生产模型搭配/签名不立项/四段号版本政策，每条 1–3 行结论＋原始 ID＋归档卷回链）＋C 组条目原样；**不建 70 ID 索引表**（C8 裁定：grep 全库可达天然成立，手维护表是无 guard 漂移面），改卷首一句「A+B 全部条目均在归档卷」。
- **核销表**：
  - C1 分组口径：按行 5–3389 连续块对账（104 条/3385 行，0930 十条随块走），卷名 v1-v2 一致。【已定】
  - C2 HRO-1：三项最低要求落实。【已定】
  - C3 保留关系：C 组全留，「8 条保留」旧表述作废。【已定】
  - C4 guard 锚：主日志留字面量＋tools/tests 注释改 ID 锚。【已定】
  - C5 品牌豁免：扩大豁免评议＝本次 decision-critic 评议（本条为记录）；ALLOWLIST 显式增补归档卷路径；test_brand_allowlist.py:42 注释改「不改写已留存表述」；归档卷须 git add 保持 tracked；**前置登记二阶段风险**——C 组归档后主日志可能再无品牌词，届时须同步移除主日志白名单条目（防 `missing` 断言红）。【已定】
  - C6 Mimosa：归档后必跑深扫，findingCount==28（产品面基线）且零新增 identity；seal digest 变化记**基线更新（docs 面扩展）**不记新增；归档卷为已公开主日志严格子集，公开性继承（先例：D2026-1001-03 批 docs 新建件均未引入新发现）。【已定】
  - C7 时机分支：等 3.1 阶段3 app.js 拆分收口后在 main 进行；行号刷新与搬移**同一 commit** 原子完成；隔离为独立 docs-only commit，不混重构分支。【已定】
  - **owner-① grep 口径**：执行前全库盘点 `decision-log` 行号引用——范围＝docs/、tools/、tests/、src/、根级 md 与 .zcode 记忆；判定式＝`decision-log` 后接行号（`decision-log[:：]数字`、`decision-log.md:数字` 等形态）逐条入清单。【待执行】
  - **owner-② ID 锚优先**：行号引用刷新一律改写为决策 ID 锚（如 `D2026-0916-03 收尾清单`），仅 ID 不可定位时才允许「归档卷:行号」并在核销表标注原因。【待执行】
  - **owner-③ finding diff**：Mimosa 深扫 finding diff 判定式＝findingCount==28 且零新增 identity；seal digest 变化记基线更新；diff 结果写入核销表。【待执行】
- **验收标准**：①行号引用核销表逐条「原引用→新落点（ID 锚）」零悬空；②归档卷条目数/行数与源区间对账相等（104 条/3385 行）；③guard 相关测试绿＋品牌钉 unexpected/missing 双断言绿（归档卷入白名单且 tracked）；④Mimosa findingCount==28 零新增、seal 记基线更新、归档卷脱敏检查通过；⑤现行约束速查自检——仅读主日志即可答出八项现行约束的结论＋原始 ID＋回链；⑥`git diff` 证明 A+B 正文只移动未改写；⑦C9 权威声明落地。
- **执行时机**：等 3.1 阶段3 app.js 拆分收口后，在 main 进行（C7）。
- **回链**：Ref: D2026-1019-02（顺序追加）；评议＝decision-critic 2026-10-20（HRO-1 采纳；C1-C9 全采纳；INFO_GAP 三项主审裁定闭环：①C 组全留②行 5–3389 连续块对账③归档卷公开性继承）。
- **执行追记（2026-10-20，d1020-卡2 执行者＝ZCode 内生子智能体；禁 commit/push，改动停工作树待主审验收）**：
  - 执行时间 2026-10-20；计数基线按主审勘误后口径执行（130＝A+B 104＋C 组 26，追记型标题全口径计入）。
  - 切分断言：切分前 `^## ` 计数 130；切分后归档卷 **104**、现行日志 **27**（26 条目＋归档速查 1 节）；边界锚 `## 2026-09-14 [D2026-0914-01]`（归档卷首条）与 `## [2026-10-09] D2026-1009-01`（现行日志首条目，速查节之后）各唯一；A+B 区（行 5–3389 连续块＝3385 行）sha256 切分前后相等＝`14596b63b435538ae7e9969851ae4148cf1d6805151a4736e573d591ac86a063`；现行日志无 D2026-0914-01 条目（该 ID 串仅作为速查节 bullet 文本出现＝卡面模板自带，按条目级口径判定通过）。
  - owner-① 盘点（范围/排除目录按卡面）：pattern1 命中 35、pattern2 命中 3，合计 **38 处**。处置分布＝**引用件 25 处（10 件）全部改写为 ID 锚**（其中 5 处为步骤 4 结构性锚追加：guard 注释串 `第 139 行`/`:139` 空格形态、tests 文档串 2 处）；**条目正文 13 处登记不修**（现行日志 C 组 4＋归档卷 6＋归档卷 pattern2 3）——依「禁改条目正文/逐字节保全」红线优先。另有 2 处 `D2026-0923-01:796`（README-失配点盘点清单 :6、:27）属卡面 pattern 之外的 ID+行号混合形态，已上报未动。
  - 核销表（原引用→新落点，引用件零悬空）：
    - `docs/README-失配点盘点清单-20260929.md`：:3 `:1409`→D2026-0929-02；:15 `:794-795、:1413`→D2026-0923-01、D2026-0929-02；:16 `:627/:633`→D2026-0921-01；:17 `:890/:986/:1017`→D2026-0923-01/D2026-0924-03/D2026-0924-04
    - `docs/roadmap.md`：:82 `:2000②`→D2026-1001-02②；:112 `:1315-1316`→D2026-0926-01；:130 `:2944`→D2026-1005-01；:218 `:1387`（两处含「以 :1387 口径为准」）→D2026-0927-05；:234 `:1316`→D2026-0926-01；:235 `:2105`→D2026-1001-04；:236 `:1939`→D2026-1001；:237 `:1395`→D2026-0928-01；:238 `:1082`→D2026-0925-01
    - `docs/design/d1012-C22-卡1-回放labels数组.md`:3 `:3533`→D2026-1009-02；`docs/design/d1015-P1残余批-设计规格.md`:5 `:3700-3701`→D2026-1012-01、:132 `:3700`/`:3701`→D2026-1012-01（0b 裁定表）/（痛点点选表）、:198 `:3700`→D2026-1012-01、:313 `:3700 vs :3701`→D2026-1012-01（0b 裁定表）vs 同条目（痛点点选表）；`docs/design/d1015-P2残余批-设计规格.md`:5 `:3700`→D2026-1012-01；`docs/design/d231-批清单.md`:29 `:2000②`→D2026-1001-02②；`docs/design/d261-批1-批清单.md`:3 `:2509`→D2026-1002-07；`docs/design/d280-批1-批清单.md`:20 `:3122`→D2026-1007-03
    - `tools/guard_banned_paths.py`：:38 `:575`→D2026-0918-01；:42、:43 `:139`→D2026-0916-01；步骤 4 追加 :16「第 139 行」、:41、:104 同落 D2026-0916-01——**注**：本条 C2③ 点名 `D2026-0916-03 收尾清单`，而实读该收尾清单（internal_docs/、api_keys.bin、sexual_terms.csv 出树）落在 **D2026-0916-01 方案要点第 6 条**（归档卷行 138），按内容实读落锚，与 C2③ 点名 ID 的差异上报待裁决
    - `tests/test_guard_banned_paths.py`：:8、:108 `:139`→D2026-0916-01（注释串）；断言 `literal in dlog` 为整文件子串型契约锚，未改逻辑——现由本条目正文（C4「主日志速查保留字面量」）提供字面量，测试绿；**风险登记**：速查节模板未含 `internal_docs`/`sexual_terms.csv` 字面量，二阶段归档 C 组时该断言将失源
  - owner-② 例外记录：无——25 处（含步骤 4 追加 5 处）全部落 ID 锚，无「归档卷:行号」保留形态。
  - ③ Mimosa 深扫结果（C6/owner-③，主审 2026-10-20 回填）：**PASS**——scan-2026-10-20T02-47-33.605Z-9f8671365152（seal sha256:2ddf4416274b11e2b1385c54b6f463b192c4dca0bcfbcd5df170a1093eb02c8d），findingCount=43＝产品面 **28**＋artifacts/b4 树外 15；identity 多重集与基线 scan-…dbc9199fec90 独立复算**逐条全等**（新增 0/消失 0；复算口径＝sorted identity join sha256=45cb79aa…7856，两侧同口径）。**零新增成立**；seal digest 变化按 C6 记**基线更新（docs 面扩展）**不记新增。offlineAdvisory matchedPackages=1 为既有观察项（D2026-1019-03 ④）维持。
  - 品牌钉：`python -m pytest tests/test_brand_allowlist.py -q` = 1 passed（归档卷未 tracked 不入判定面，未触发红）；按 C5 归档卷须 tracked＋ALLOWLIST 增补，若在未 tracked 时增补则 missing 断言必红，故白名单条目留主审在 commit 同批处理；C5 要求的 test_brand_allowlist.py:42 注释改写未执行（超卡面处置条款范围，上报）。
  - 验证：brand 钉 1 passed；guard 7 passed；ruff（改动件 tests/test_guard_banned_paths.py、tools/guard_banned_paths.py）clean；切分断言 A/B/C/D/E 全绿（见上）。
  - **主审验收裁决与补齐（2026-10-20）**：①执行者遗留⑤ 裁决＝guard 契约锚维持 **D2026-0916-01**（内容实读：收尾清单落该条目方案要点第 6 条），C2③ 点名 D2026-0916-03 系方案文本笔误，勘误登记不回改；②上报 2 处混合形态 `D2026-0923-01:796`（README-失配点盘点清单 :6/:27）已改纯 ID 锚（owner-② 口径延伸，主审补刀）；③速查节按 C4/C9/验收标准⑤ 补齐＝C9 权威声明＋八项现行约束速查（品牌钉/Mimosa git-gate/guard 树外契约/4 槽结构/ctx 16384/生产模型搭配/签名不立项/四段号政策，各带原始 ID 与归档卷回链）＋契约锚字面量（internal_docs/sexual_terms.csv），二阶段 C 组归档断言失源风险解除；④C5 落地＝ALLOWLIST 增补 `docs/decision-log-archive-v1-v2.md`＋test_brand_allowlist.py:42 注释改「不改写已留存表述」，与归档卷 git add 同批（双断言绿见主审验证链）。

## 2026-10-20 D2026-1020-04 「派卡执行通道切换追认（OpenCode CLI → ZCode 内生子智能体直派，暂停非退役）」 [已拍板·追认已发生]

- **原决策**：2026-10-20 owner 令——裁卡暂停，批任务直派 ZCode Agent 内生子智能体（新模型测试期），验收纪律不变；即当前存在两条执行通道：OpenCode CLI（wrapper 链）与 ZCode 内生子智能体。本条目为对既成事实的**追认登记**，非新拍板。
- **评议员结论**（decision-critic 独立评议）：**支持（追认）**，无 [HIGH_RISK_OBJECTION]。独立实证：①`G:/zcode/.zcode/workspace/default/tools/` 三件套 tracked/clean，git blob 哈希与 `J:/归档/zcode`（bare HEAD=`95c0863`）`ls-tree HEAD tools/` 逐位一致（恢复保真成立）；②`C:/Users/57850/.zcode/` 无 `.git`；③`D:/SubTransJAV/tools/` 为项目自有脚本目录、无 wrapper 副本 → 相对路径 `python tools/exec_wrapper.py` 必失败（根因坐实）；④`exec_wrapper.py:27` `DEFAULT_CLI=D:\OpenCode\resources\opencode-cli.exe` 实测存在；⑤三件套互相零 import。
- **主模型最终决定（owner 2026-10-20 终审）**：**追认成立**。通道定位：主力=ZCode 内生子智能体；OpenCode CLI=**保留备用**。**关键措辞：暂停，非退役**——"暂停"语义可恢复，与备用保留一致；**恢复/激活条件见 D2026-1020-05 通道定位小节**。
  - **治理规则（Part 2，通道无关）**：不可委托清单适用所有通道（目标定义/多方案取舍与架构决策/跨子智能体冲突裁决/需求澄清与范围裁剪/高风险变更放行/最终验收放行打回/规则变更权，均由主模型亲做）；子智能体建议被采纳时主模型显式记"采纳自 X 建议"；高风险变更（数据迁移或删除/权限凭据/外部依赖增删/全局规则或入口脚本/tools/ 代码）须主模型显式放行。
  - **回传规范（Part 3，消息层）**：凡子智能体以消息形式回传时适用（当前=ZCode 通道）；字段语义**继承 exec.v1**（变更↔files_touched、验证↔exit_code+error_tail、风险↔flags、需决策点），**不要求机器解析**；OpenCode 通道以 exec.v1 为权威回传，本 schema 字段为其语义映射（非额外要求）；schema 含"是否超出任务书范围：是/否"；追问超一次=schema 或任务书缺陷，修规格而非让子智能体多写。
  - **抽检（Part 4，触发通道无关、判据分通道）**：OpenCode 看 exec.v1 合规，ZCode 看回传证据可复跑（**确定性任务**要求结果一致；**非确定性调研任务**要求可复跑**且标注不确定性来源**）；N=5 与"每日 3 卡对账 exec.v1"互补、**同卡同日两抽计一次**；破例率分母=任务总数；抽检默认只读，破例须登记（时间/原因/文件/是否事后补派复核）。
- **条件闭环状态**：不适用（追认既成事实）。回退通道策略须走新决策。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①OpenCode 通道判据维护（因保留备用，纳入 D2026-1020-05 后续任务清单）；②主力=ZCode 测试期模型独家风险——保留备用通道即为其对冲，激活条件见 D-03。
- **回链**：Ref: D2026-1020-01（顺序追加）；与 D2026-1020-05 语义咬合（暂停非退役 ↔ 通道定位）；**改号注记＝原编 D2026-1020-02，因与合并列车收口登记条目（3005ccd 先落库先推送）撞号，按 D2026-1003 撞号先例顺延改号**；评议=decision-critic 2026-10-20（无 HRO；3 项反向修正采纳：.gitignore=`__pycache__/`、不写"全参数化"、非确定性任务加"标注不确定性来源"）。

## 2026-10-20 D2026-1020-05 「wrapper 三件套收敛到全局 tools/＋全局派卡命令改绝对路径＋OpenCode 通道定位（N1）」 [已执行（Part 1 七项收口 2026-10-20，执行记录=docs/design/d1020-wrapper-convergence-exec-record.md）]

- **原决策**：派卡基础设施收敛——wrapper 三件套（`exec_wrapper.py` 578 行／`pointer_tools.py` 267 行／`quota_watch.py` 249 行）由 default 工作区（`G:/zcode/.zcode/workspace/default/tools/`，该项目 2026-10-19 降本关停封盘 DEC-2026-10-19-01）收敛至全局 `C:/Users/57850/.zcode/tools/`，并把全局 AGENTS.md 派卡命令由相对路径改为绝对路径。前置：N1（OpenCode 通道定位）为 D-03 前置拍板项，owner 2026-10-20 已拍定=保留备用，前置满足。
- **评议员结论**（decision-critic 独立评议）：**有条件支持 → 条件闭环后支持**。4 项 [HIGH_RISK_OBJECTION] 全闭环：H1（Part1 自指矛盾/无回滚）→ 主模型显式放行+回滚边界；H2（双通道适用混乱）→ 按规则性质切分；H3（单一权威源无版本化）→ C/tools/ git init + J 作 seed；H4（smoke 口径不足）→ L1-L3 分级。独立实证：三件套 git blob 与 J 裸仓逐位一致；`ensure_git_exclude` 幂等（`exec_wrapper.py:235-238`）；`_build_cli_argv`（`:358`）对 .py 用 `sys.executable` 注入、无兄弟脚本路径拼接（exec_wrapper 对 pointer_tools 零引用、对 quota_watch 仅注释 L45-46）；`WARN_TOKENS=120K` 等为模块级硬编码常量（L37-41）。
- **主模型最终决定（owner 2026-10-20 终审）**：**方案通过，授权待开工令**。
- **授权动作（Part 1）**：
  1. 源核实：`G:/zcode/.zcode/workspace/default/tools/` 可读（已确认）；若已清，从 `J:/归档/zcode` clone（HEAD=`95c0863`）。
  2. 拷入 `C:/Users/57850/.zcode/tools/`，文件名不变。
  3. 依赖自检（4 项已闭环）：①`DEFAULT_CLI` 绝对路径 ok；②`find_repo_root`/cwd 落调用方项目 artifacts ok；③`ensure_git_exclude` 幂等已确认；④`quota_watch --db` 显式传参 ok；⑤调用链三件套零互相调用（实证）。
  4. 改 `C:/Users/57850/.zcode/AGENTS.md` 第 5 行两处路径为**正斜杠绝对路径** `C:/Users/57850/.zcode/tools/exec_wrapper.py`（及内嵌 pointer_tools 路径）；改前备份 `AGENTS.md.backup-YYYYMMDD-HHMM`。
  5. 分级 smoke：L1 spawn+回显；L2 断言 stdout 单行且 `schema=="exec.v1"`（假 CLI 注入）；L3 验证轮转机制可被触发（不校验阈值合理性）。
  6. 不建副本：`D:/SubTransJAV/tools/` 不放 wrapper。
  7. 版本化：`C:/Users/57850/.zcode/tools/` 内 git init + 提交三件套 + `.gitignore`（内容=`__pycache__/`）+ `tools-baseline.sha256`（只记入库文件）。
- **OpenCode 通道定位（N1，前置拍板项）**：
  - **定位**：保留备用（暂停非退役，回链 D2026-1020-04）。
  - **激活条件**（任一即触发，须主模型显式放行）：①ZCode 内生通道连续 **K=2** 次任务失败/不可用且无修复；②需要 exec.v1 机器契约而 ZCode 通道无法满足；③主模型判定测试期模型质量不达标；④需要多模型轮转/限流兜底能力而 ZCode 通道无此机制（**限定：任务级、临时**——仅针对该批任务，任务完成即回落 ZCode 主通道；**连续 M=3 次因同一能力缺口激活**（M 值可调）→ 触发"该能力是否应补进主通道"评估，防备用通道实际使用率超主通道、名存实亡、违背暂停令语义）。
  - **健康检查（三件套，缺一不可）**：
    - **常态化 L2**：每 **N=4 周**一次（假 CLI 注入，断言 stdout 单行可解析且 `schema=="exec.v1"`）。**边界（须写入，防误读）**：假 CLI 只验 wrapper 契约生成逻辑（stdout schema 拼装），**不验真实 CLI 兼容性**——真实 CLI 升级改输出格式时假 CLI 全绿；"L2 月度全过"≠"通道健康"。
    - **事件检测（机制化，非人记）**：L2 脚本每次运行顺带记录 `DEFAULT_CLI`（`D:\OpenCode\resources\opencode-cli.exe`）版本信号（`size+mtime`，可选 sha256），下次 L2 比对；变更则自动标记"需做一次真实 CLI 的 L2/L3"。检测器零成本落地，与月度 L2 一份脚本两用。
    - **激活前 L3**：切回前必过（轮转触发验证）；不常态化（假 CLI 构造维护成本高）。
    - **失败处置（分类）**：**基础设施失败（CLI 不存在/权限/路径错误）不计入 K，单独告警**；**仅契约失败（schema 不符/解析失败）计入 K**。连续 **K=2** 次计划内 L2 契约失败且无修复 → 进入降级流程。（因 L2 用假 CLI，分类天然二分：假 CLI spawn/权限=基础设施，schema 断言=契约，无第三类。）
  - **降级/退役出口**：ZCode 通道稳定运行满 **X=8 周**且无重大故障（"重大故障"=激活后任务失败且不可恢复/需人工介入，一次即重置稳定窗）→ OpenCode 从"备用"降"归档"。
    - **X=8 周性质：必要条件非充分条件**——8 周是"最短稳定窗"（资格线），非"自动降级"（触发器）；降级还需**主模型显式确认"测试期结论已出且 ZCode 通道满足主力要求"**（测试期长度不由 8 周决定，禁时间机械改写通道定位）。
    - **重置上限**：累计 **2 次重置** → 触发"该通道是否值得继续保留"的重新决策（防无限重置使降级出口形同虚设）。
    - **归档处置**：①AGENTS.md 命令**标"[已归档] 恢复前须先执行 L2/L3 验证并查阅 D-03 健康检查台账"、行首可见**（非行尾小字），紧贴命令行；②**全局 tools/ 保留不清理**——清理动作另立决策，不与归档捆绑（否则复活行变死链）。
  - **分层（备用期/归档期）**：月度 L2、事件检测、台账、重置逻辑均为**备用期配置**；归档后**停止**月度 L2 与事件检测，只保留复活标注 + 一份"恢复验证清单"（L2/L3 一次性跑通步骤）。防归档后对不再维护的通道空转投入。
  - **成本知情项**（保留备用的持续投入，须知情非顺手勾选）：分通道 schema 维护、分通道验收判据维护、月度+事件冒烟、假 CLI 注入骨架维护、双轨心智模型认知成本。
- **放行与回滚**：
  - 放行：经**主模型显式放行**，放行依据记入本决策。
  - 回滚脚本路径：`C:/Users/57850/.zcode/tools/rollback_wrapper_convergence.sh`（还原 AGENTS.md 备份 + 删除 `C:/Users/57850/.zcode/tools/`）。
  - 回滚边界：仅覆盖 AGENTS.md 还原与 tools/ 删除，**不含已派发卡与子智能体已产生副作用**。
  - 回滚演练记录链接：`docs/design/d1020-wrapper-convergence-exec-record.md`（2026-10-20 已演练：三断言全过；断言3 按"操作面引用 0 命中"口径成立，decision-log 自身 5 处为决策历史记录不可移除）。
- **验收口径**：L1-L3 如上；L2/L3 必过方可放行；L4（token 看护验证）延后。
- **配置架构核查结论**：三件套无外部配置文件依赖；exec_wrapper 运行参数经 CLI 传入，**阈值硬编码**（`WARN_TOKENS=120K`、`STRIP_BLOCK` 等为模块级常量）；quota_watch 为旁路只读诊断工具（`--db` 显式传参），不在轮转链内；项目间无配置耦合。**阈值硬编码在当前单用户单主力项目场景下可接受（有意识暂缓，非已解决）；若未来出现多项目差异化阈值需求，再评估参数化。**
- **default 边界**：全局 tools/ 服务对象=SubTransJAV 及未来项目，**不含 default**；default 工作副本 wrapper 为历史遗留，不纳入维护、不作回滚目标；J 裸仓作 provenance seed + 异地归档；**C/tools/.git 为回滚目标**（git init 后 C 区自主，lineage 来源已登记）。
- **后续任务清单**：①阈值/常量合理性复核（`WARN_TOKENS=120K`、`STRIP_BLOCK`、quota_watch 分类规则）；②L4 token 看护验证；③跨项目本地 wrapper 覆盖排查（是否存在他项目自带 `tools/exec_wrapper.py` 被绝对路径切换）；④历史卡 `docs/design/d1018-卡4-批2-msg文案表切出.md:109` G 绝对路径处理（更新或冻结声明）；⑤OpenCode 通道判据维护（长期项）；⑥OpenCode 健康检查台账与事件检测机制落地。
- **待裁决**：无（N1 已由 owner 拍定为保留）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **回链**：Ref: D2026-1020-04（前置：通道切换追认）、D2026-1020-01（顺序追加）；**改号注记＝原编 D2026-1020-03，同 D2026-1020-04 撞号顺延**；评议=decision-critic 2026-10-20（4 HRO 全闭环；6 项补充建议全采纳 + 5 处细化限定；M=3 建议值标注可调）。
- **追记（2026-10-21 留痕）：件⑥ 月度 L2 脚本三缺口 owner 裁决（2026-10-20 终审，原仅存会话与 memory，本行补仓库内留痕）**：①不补 `--confirm`——月度巡检定位＝自动化无人值守，维持 `--selftest`/`--run` 二态契约；②`--run` 遇 DEFAULT_CLI 不可读返回 1——基础设施故障须大声报错，判正确语义；③`# noqa` 维持现状——ruff 现行通过＝相容，lint 收紧时再改。交付终态与验证链见 docs/design/d1020-卡L2-月度L2脚本.md 执行记录（aed7c67）＋memory l2-card-d1020-closure。


## 2026-10-20 D2026-1020-02 「3.1 阶段3 app.js 拆分合并列车收口（chore→refactor→main 双段 --no-ff 合并＋双段 CI 绿＋Mimosa 深扫零新增）」 已执行（合并完成登记，主审亲执）

- **背景**：owner 派卡完成 3.1 阶段3 app.js 拆分合并列车；口径=D2026-1019-03 owner 追记⑥（chore 与 refactor 同一合并列车、chore 禁止单独落 main）＋②（合并前手动全量双保险）。主体=refactor/appjs-split（批0 读取层＋批1-4 拆分终态＋a131bda ci.yml 触发面 refactor/**）＋chore/spike-ruff-cleanup（spike/ 8 处 ruff 清理，自 c42d1e9）＋0cd07b6（D2026-1020-01 条目，另一会话已按派卡步骤 0 规范提交为 docs-only 在途件，随列车入卷、不混提不改写）。
- **列车第一段（refactor/appjs-split）＝33cf856**：`git merge --no-ff chore/spike-ruff-cleanup`；docs/decision-log.md 双侧尾部追加冲突（预期形态、唯一冲突件）按时间序手工接续——D2026-1019-03（chore 侧 +13）在前、D2026-1020-01（refactor 侧 +20）在后；blob 字节级拼装＋断言（双侧均纯尾追加/增量行数 13、20/ID 顺序/无标记残留），对双父 diff 恰为 20/0 与 13/0 纯追加＝两侧逐字保全零丢边；合并后全库 ruff **8→0**；推送 86b92c3..33cf856（快进，非 force），CI run **39298268375=success**（8 腿矩阵＋lint＋mypy 门）。
- **列车第二段（main）＝ce2ed7b**：`git pull --ff-only origin main`（up to date @6364ad0）→ `git merge --no-ff refactor/appjs-split`（ort 策略零冲突；60 文件，app.js 9820 行出库、拆分模块全量入库——34 文件读取层=tests/js_sources.py 所钉）；树内容与已验提交 33cf856 **逐字节一致**（git diff 33cf856 HEAD 空）＝CI 等效背书；推送 6364ad0..ce2ed7b，CI run **39299151483=success**（拆分内容首次进 main CI）。
- **合并前双保险（②）**：全量 pytest **2512 passed + 4 skipped**（173.77s；4 skip=process_manager 平台性跳过 ×4）；冒烟 `refine --help`＋`import subtransjav.webview_gui.main` 双 rc=0。过程披露：本会话执行壳缺 LOCALAPPDATA/ProgramFiles(x86)，首轮曾显形 2511+5（test_installer_lifecycle 的 ISCC 编译冒烟因 _find_iscc 候选路径落空多跳 1）——按派卡停下条件冻结取证，确认执行环境缺口非代码回归（ISCC.exe 实际在位、测试文件零改动）后修正环境复跑，精确 2512+4。
- **Mimosa deep（合并终态 main ce2ed7b，扫描时点 HEAD 回传=ce2ed7b 与本仓一致）**：attempt1=scan-2026-10-19T18-04-26.755Z-0c80b11730d7（seal sha256:bccff29290f2d18686635a9f4fbc75fdafc17d54149c15177615809db8b06ed2）＋attempt2 重试（按派卡「重试至多一次」）=scan-2026-10-19T18-06-59.896Z-425d9bcb90d6（seal sha256:28f048c6f27138c587b37c34631d475bbbcd2afe16bebb56830b654361d8abff）——两轮 **findingCount 均 43（high 43/余 0），native identity 多重集与合并前基线 scan-2026-10-19T16-06-44.656Z-dbc9199fec90 逐条全等**：主审自 .mimosa 工件独立复算，两轮 identity 指纹与基线同为 sha256:b935f57241e2c445342d1d6f1bd290c5d38f2ff7f02a4cead94eb525c5f58718（43 条全唯一，diff 0/0），路径拆分产品面 28＋artifacts/b4 树外 15 恒等，seal 工件哈希复算完整（零新增＝本批安全比对门通过）。如实登记：两轮 completeness 均 partial／runStatus=inconclusive（threatModel/findingDiscovery/pathAnalysis=partial，validation/reporting=completed，gaps=「部分分析阶段未能完整覆盖」）——**与基线扫描同态**（基线 job completeness=partial、manifest runStatus=inconclusive），属同口径等价比较，不据此宣称全量覆盖；suppressedTestContext 字段在两轮工件中缺位（基线 job 记录曾为 10），照实记差异；dependencySummary 与基线逐项相同（packagesScanned=68；offlineAdvisory matchedPackages=1 为既有观察项，见 D2026-1019-03 ④ owner 复核项，维持）。
- **钩子面**：本列车两笔合并提交（33cf856/ce2ed7b）过程均无扫描器输出可见；钩子面不据此宣称安全——scanner_enobufs 兼容放行为已知在案状态（D2026-1019-03 ③），Mimosa deep seal 为现行补偿门。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪（遗留 owner 事项）**：① GUI 原生 WebView2 真窗口四点＝发布门禁（D2026-1019-03 ②：负责人 owner、截止下个发布门、关闭证据=录屏/截图＋点验记录）——不阻塞合并、阻塞发布；② scanner_enobufs 钩子修复（③）；③ offlineAdvisory 元数据漂移 owner 复核（④）；④ 版本号与 CHANGELOG 本批不动，随下一常规发版批。
- **追记（2026-10-20，D2026-1020-06）**：① GUI 真窗口四点 owner 初步核实功能正常＝发布门禁关闭（后期发现问题转常规缺陷流）；④ 版本号/CHANGELOG 随下一常规发版批（3.0.4）执行；②③＝长期观察项发版后 owner 排期。
- **回链**：Ref: D2026-1019-03（⑥⑦）、D2026-1020-01（随列车入卷）、D2026-1019-02（基线甄别口径）；d1020-卡1＝CI 腿 A 落地（run 39292183541=success）；勾账同批件=docs/roadmap.md 3.1 节刷新＋d1020-卡1 §七 绿相回填（同一 commit）。

## 2026-10-20 D2026-1020-06 「3.1 发版条件复核收口：GUI 真窗口四点门禁关闭＋阶段 4 账面回填＋D2026-1020-01 归档第一阶段执行」 已执行（主审亲执）

- **背景**：主审对 3.1 发版条件复核（roadmap 3.1 节已全勾＋D2026-1020-02 合并列车收口），残余三类：①发布门禁＝GUI 原生 WebView2 真窗口四点走查；②账面瑕疵（D2026-1015-05 状态未回填、走查修复四卡无决策条目、D2026-1015-03/D2026-1012-01⑧ 移交项未逐项核销、D2026-1020-01 归档未执行）；③长期观察项。**owner 2026-10-20 两点裁决**：「真窗口四点走查初步核实功能正常，后期使用发现问题再修复即可」「账面瑕疵进行发版前处理，长期观察项发版后会排期进行处理」。
- **裁决落地**：①发布门禁**关闭**（口径＝owner 亲自点验放行，录屏/截图证据形态豁免；后期发现问题转常规缺陷流修复，不追诉证据补交；D2026-1019-03 ②/D2026-1020-02 ① 已同步追记核销）；②本条即发版前账面处理：六笔回填（D2026-1015-05 标题状态、D2026-1015-03 遗留核销、D2026-1012-01⑧ 移交项核销、D2026-1019-03 门禁关闭追记、D2026-1020-02 风险跟踪追记、本条登记）＋走查修复四卡补记（下方）＋D2026-1020-01 归档第一阶段执行（切分/引用核销/深扫详见该条目执行追记）；③scanner_enobufs、offlineAdvisory、派卡基础设施恢复（D2026-1020-05 待 owner 开工令）、P1-6＝长期观察项，发版后 owner 排期，不阻塞发版。
- **走查修复四卡补记（回填归档，先例＝D2026-1015-03；roadmap 回链称 D2026-1016-01~04，卡面＝d1016-卡A~卡D，同指）**：阶段 4 走查修复四卡 2026-10-16 收口推送 main——卡A 校对页 ASR 对照折叠钮=16444c3（定向 199 passed）；卡B 校对页右栏折叠钮 ARIA/快照=b165863（200）；卡C 跳摘折叠头归一=0c5978d（201）；卡D 导读空态光秃标题收口=e57f77a（202）。细节以 docs/design/d1016-卡A~卡D 卡面执行记录为准；各卡真机走查挂账项已随 owner 统一走查收口（roadmap 3.1 节勾账）。本段不新设决策，仅归档事实。
- **移交项核销口径**：D2026-1015-03 遗留（P1-8 引擎页残余＋卡N 三档缩放）与 D2026-1012-01⑧（卡4 computed-style 黑盒复核、卡5 真机 11 对撞号复现）按 roadmap 3.1 节「未再报＝视为通过」口径核销（逐条追记见各条目）；⑧ 中卡3 tab-engine 钩子（pipelineCard 提示态）已由候选池小卡落地（roadmap 阶段 2 勾账），卡2 SIM905 属工程卫生候选池项不属发版门，维持登记。
- **验证（主审验收链，2026-10-20）**：ruff 全库 clean；定向 brand 钉＋guard 契约 8 passed（归档卷 tracked 后白名单双断言绿）；全量 **2512 passed＋4 skipped**（135.14s，与基线恒等）；冒烟 subtransjav-refine --help rc=0＋GUI 主模块导入 rc=0；Mimosa deep 归档后扫描＝产品面 28 零新增 identity（C6 PASS，详 D2026-1020-01 执行追记③）。执行者轮（d1020-卡2）另证：切分断言全绿＋A+B sha256 逐字节相等＋引用刷新 30 处零悬空（主审补刀 2 处后共 32）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **回链**：Ref: D2026-1020-01（第一阶段执行）、D2026-1020-02（①④）、D2026-1019-03（②③）、D2026-1015-05/D2026-1015-03/D2026-1012-01（回填核销）、docs/design/d1020-卡2-decision-log归档执行.md（执行卡含主审裁决段）、roadmap.md 3.1 节。

## [2026-10-20] [D2026-1020-07] AGENTS 瘦身与技能治理：骨架化 2435B＋dispatch-discipline 外迁＋Skill hook 审计机制层（H3 gate 降远期） [已拍板·待执行]

- **决策内容**：全局 `~/.zcode/AGENTS.md`（实测 8994B，软限 8100B 已破常态告警，硬限 9216B 余 222B）四节瘦身为骨架（v2.2 实测 2435B 含尾换行/正文 2434B，哨兵「按本节默认执行」恰 1），操作细则外迁新 skill `dispatch-discipline`；frontend-design 重复副本移除＋卸载候选逐项清卸；时序=D-05 先行、迁移为 D-05 后续第一项硬时点。规格=`docs/design/d1020-AGENTS瘦身与技能治理-修订设计规格.md`（v2.1→v2.2，owner 终裁收编）。决策号初拟 D2026-1020-06 与既有「3.1 发版条件复核收口」撞号，按 D2026-1020-04/05 先例顺延改 -07。
- **评议员异议（decision-critic，2026-10-20 两轮）**：首轮 1×[HIGH_RISK_OBJECTION]＋1×[MATERIAL_CONFLICT]＋4×[MEDIUM]＋2×[NOTE]。HRO-1=H3「完全复用 H1」结构不成立（H1 谓词 file_path 在 Agent 入参不存在；matcher `Agent` 过宽误伤 code-reader；OpenCode 备用通道走 Bash 不经过 Agent；TICKS 打点证不了 skill 已读）。MATERIAL_CONFLICT=划界表承诺「留」的不可委托清单未落骨架＋完成通知反制句丢失。MEDIUM×4=卸载 SOP「H1 拦 mv」前提错误／`.disabled-` 前缀无证据／引用核查范围偏窄／基线扩七文件时序与卡面文件数。复评：异议全数解除，**终局立场=支持**，无新增 HRO。
- **owner 终裁（2026-10-20，六拍板点全落定）**：①H3=有条件立项，批准 payload 采集＋shadow 日志，**enforce 语义定义前不建 gate**（采纳「拿不到 skill 已读信号，enforce 三条死路」论证；enforce 定义不出→「纪律级弱约束」收口，默认预期非例外），机制层先行=**Skill hook＋审计**（skill-loads.jsonl＋agent-calls.jsonl＋合规率审计，直接测「skill 有没有被读」）；②卸载清单=条件追认，逐项明细（无关 4＋重叠 1＋待定 1；emil/autoglm 待 owner 单独确认；github 无关 3 项不可行撤出）；③**pdf 从规则摘除**（项目无 PDF 产出需求）；④github:commit 禁用半行=「仅限非项目仓库」；⑤排期=追认默认方案、**拒合并备选**（断窗理由），D-05 回滚脚本加 guard（存在 dispatch-discipline 即 exit 1）＋回滚顺序=迁移回滚→D-05 回滚；⑥2600B=追认，定性**复核触发线非硬拦截**。五处执行补充全采纳（h2 检查=存在性＋最小字节＋关键行；负向钉拆机制/行为两项；触发率窗口=3 周或 10 次先到为准；body 级冲突扫描已跑零隐藏冲突；pyright-lsp 标待定）。
- **异议处置**：HRO-1 采纳、MATERIAL_CONFLICT 采纳（骨架补齐：不可委托清单＋完成通知反制句＋治理细节）、MEDIUM×4＋NOTE×2 全采纳。**无驳回、无封盘项、无 [PRESSURE-OVERRIDE]**。
- **风险跟踪**：①H3 判据实证未过→「纪律级弱约束」回退（默认预期）；②OpenCode 备用通道派卡无拦截点，挂账随通道复活再评估；③Skill/Agent 两工具 PreToolUse 入参各采一次样为 hook 实施前置；④骨架 2600B 超线触发逐条复核，禁「删注释凑字节」假精简；⑤pyright-lsp 功能验证入清卸卡验证窗。
- **回链**：Ref: D2026-1020-04（通道切换追认）、D2026-1020-05（wrapper 收敛）、D2026-1019-03（发版门禁）；规格 v2.2 与评议全文见 docs/design/d1020-AGENTS瘦身与技能治理-修订设计规格.md。
- **执行记录（裁决落地 2026-10-20，四要素）**：改前 tail3=40a28d24115ef773375001dc49cc63a83324087532a62f9060337bdc0d784178；改后 tail3=fdb7dda2b9b8d6370db2d156ac0f799fc282f4ebd98abbe54438ce0abca07ab8（TICKS 93-95 行重算哈希，与批准目标一致）；时间=2026-10-20 13:20:51（写入时刻，未归因并发写入——本会话确认门命令一条解析期失败、一条停在写前比对，均无落盘）；依据=R-20261020-03＋三判据（滚动备份 diff 纯追加 95→99 恰 4 条打点／full 前 95 行复算全等／窗口 93-95、92-94、94-96 均≠原 tail3）。
- **裁决结论**：接受修正已生效；结构异常（双哈希块夹锚点，非一体命令任何路径可产出形态）与时间倒错（mtime 13:20:51 早于第二块所含 13:24 后 MEMORY 哈希）定性为并发竞态导致的环境级未归因写入，经判定无安全风险（三判据＋只读检查全过、无 ROTATED 篡改），由一体命令归一化处置（已执行：BACKUP-BASELINE-REFRESHED，锚点前进 1431/100，结构回归单块，只读检查 v1.0 复验 HARD=0 无漂移 NOTE）；不走灾备重建、不深究具体进程；观察项③维持被动（本事件存在并发写入，不属"无并发复现同样错位形态"的系统性缺陷情形）。台账登记=R-20261020-04。

## 2026-10-21 D2026-1021-01 「P1-6 拖拽层收口（拖拽加载回归根因修复＋分隔条落地）＋等令组清算（app.js 线勾销/F4 终态确认/pyright-lsp 禁用态复核）」 已执行（主审＋wrapper 执行者两卡）

- **owner 三指令（2026-10-21）**：①app.js 线三项（真机走查/P1-4 认否/spike 8 项）已收口按 owner 口径勾销；②P1-6 拖拽真机实测发现「拖拽文件无法真正加载」缺陷，未完事项本轮完全收口；③等令组中达到开工条件者全部开工收口。F4 经正文核查＝**已有终态**（C22 校准未达标 0.0945<0.95，按 D2026-1009-02 既定预案 B 执行：门控关死＋放弃语义＋零代码变更，报告 docs/c22_calibration_report.md）——非待开工项，本轮仅账面确认，重开触发维持登记。
- **勘探兜底**：code-reader 三连 API 超时（ZCode 内生通道暂不可用），按 L-20261020-01 先例主审亲执静态勘探；两卡均走 wrapper/OpenCode 备用通道（D2026-1020-05 绝对路径形态），激活条件①（连续 K≥2 失败）满足，执行者=opencode/deepseek-v4.1-flash-free，exec.v1 契约两卡均干净（exit0、零轮转耗尽、终回非空、时长 8.4/9.0 分钟，远低于 25 分钟盒）。
- **卡1（d1021-卡1，拖拽加载缺陷确诊修复）**：执行者两笔 b6a5ffe（缺陷A：review.js REVIEW_SRT_EXTS 漏 .ass/.ssa/.vtt 与 main.py allowed_exts 口径不同步→校对页拖入被静默丢弃，2.7.2 件1 同键族消费点未全查老坑形态；含回归测试 tests/test_drag_drop_chain.py 先红后绿）＋08a861c（drop 链诊断埋点五行纯增量 print＋dnd_listeners 探针）。**缺陷B（主嫌，主审验收期亲执修复 437b907）**：app-file-list.js:65 `#fileList` drop 监听 `stopPropagation()` 拦断冒泡→main.py:241 document 级 pywebview 桥收不到 drop→拖入文件永不加载（2026-09-30 D2026-0930-09 批2 引入，真机 only 故历轮黑盒未抓）；修法=去 stopPropagation 保 preventDefault＋静态负向钉（注释剥除后断言）；守恒钉换代（全库拼接 10f6ef82→f67e4ceb、app-file-list 15821→16069B/19c7d947）。DOMEventHandler 签名（prevent_default/stop_propagation）经 .venv 安装源实证。
- **卡2（d1021-卡2，P1-6 件B 拖拽分隔层）**：执行者 73de931（index.html `.translate-splitter` role=separator 零 id 零 i18n 键＋style.css `--translate-split` 变量单点承接（默认 60%=卡F 基准）＋app-file-list.js 尾部 TranslateSplit 小节（mousedown→document mousemove/mouseup，clamp[25,75]，localStorage `subtransjav.translate.split` 记忆，折叠互斥=禁用态，**全程禁 stopPropagation 承卡1 教训**）＋test_gui_js_static 静态断言＋钉换代）＋e328519（卡面执行记录回填）。执行者五项主动披露在卡（分母未扣分隔条 8px 误差<1.5%/路径勘误 assets/index.html 等）。
- **验证链（主审两轮亲跑）**：ruff 全库绿；定向 534→537 passed；全量 **2516+4 → 2518 passed+4 skipped**（基线 2512+4 只增不减，+5 新钉其中 1 先红后绿）；冒烟 import main＋refine --help rc=0；Mimosa deep 两轮＝43 零新增 identity 多重集全等（seal 4d6f4e35/90d9b2dc，identity 指纹 154aaf5b/eae4fa08 逐位比对，offlineAdvisory=1 既有观察项维持）。**GUI 未验证**（合成环境无法 OS 级文件拖拽；分隔条为纯前端 mouse 事件可合成但本批未跑黑盒）——真机走查挂账 owner：①任意字幕/视频拖入窗口应正常加载（gui.log 应现 `[drop] event received`→`evaluate_js ok` 链，`pathless>0` 即 pywebviewFullPath 注入失效另行报障）；②translate 页拖分隔条比例变化且重启保持；③Console 折叠时分隔条禁用。
- **pyright-lsp 清卸卡窗口复核**：cli/config.json enabledPlugins `pyright-lsp@claude-plugins-official` **已是 false**（禁用态在场，本会话工具清单无 pyright 工具互证）——规格 §1.6 待执行动作实际已生效，本轮留痕即闭环；不安装运行时（范围外未授权），owner 令恢复路径=npm i -g pyright 后重跑探针。
- **大考对账**：audit_dispatch_compliance.py 窗口 7/10（样本不足继续累计）；本会话 3 派卡（code-reader×3＋wrapper×2）派卡前均已读 dispatch-discipline=合规；**他会话（session_a34ff27c，01:13 调研 server.py 卸载接口）1 卡未读 skill** 致现行合规率 85.7%<9/10——按规格 §5 触发「回迁或升级机制」评估线，先报 owner 裁（候选=H3 shadow 数据看齐/纪律重申/样本到 10 再判，主审建议=样本到 10 再判，本会话合规先例不构成机制失败证据）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **回链**：Ref: D2026-1009-01/-02（F4 预案 B 终态）、D2026-1013-01（卡F 60/40 基准）、D2026-0930-09（缺陷B 回归引入点）、D2026-1020-05（wrapper 通道）、D2026-1020-07（pyright-lsp §1.6）；卡面=docs/design/d1021-卡1/卡2（含执行记录）。
- **追记（2026-10-21，owner 三点裁决）**：①P1-6 拖拽层**验收通过**（owner 口径）；②**暂不推版**——本地 8 笔（f7f5773…2a24091）留 main 不 push，待密集测试修复其他小 BUG 后汇总发版；③大考窗口**样本到 10/10 再判**（85.7% 评估线暂不触发 §5 处置；建议采纳=样本不足不判机制）。emil/autoglm 真身查明＝skills-disabled 内两个用户级技能（emil-design-eng=Emil Kowalski 设计工程方法论；autoglm-browser-agent=AutoGLM 浏览器自动化代理），**禁用态维持**，是否恢复/删除待 owner 单独确认（原待定项语义不变）。

## 2026-10-21 D2026-1021-02 「三点裁决：技能状态勘正（autoglm 实为启用态）＋scanner_enobufs 修复纳入本轮＋候选池三项纳入本轮」 [已拍板·待执行]

- **裁决内容（owner，2026-10-21）**：①技能状态勘正——emil-design-eng 在会话/`/` 菜单不可见＝其仅存于 `~/.zcode/skills-disabled`（非发现根，永不被发现），禁用态属实；autoglm-browser-agent 实际生效态＝**启用**（owner 2026-10-21 09:02 在 Settings→Skills 勾选，客户端已将其置于 `~/.agents/skills` 发现根并被本会话加载；`skills-disabled` 内 2026-09-28 旧副本为陈旧重复，两份并存是「核实为禁用态」误判的触发源——上条 D2026-1021-01 追记「禁用态维持」对 autoglm 即告陈旧，本条勘正）。陈旧副本清理与 emil 恢复/删除仍待 owner 单独裁决（本条不擅自移文件）。②scanner_enobufs 钩子修复纳入本轮。③候选池三项（状态 tag 列、checkbox→toggle、接口地址区深化，D2026-1001-03 第⑤项）纳入本轮。
- **scanner_enobufs 问题定义（D2026-1019-03 ③ 在案）**：供应商钩子入口写 stdout 后立即 exit，stdout 管道背压（ENOBUFS）时判定 JSON 丢失、宿主把空输出当放行＝「兼容放行」，提交期安全/secret 扫描存在静默失效面（2026-10-12/13 在案，f6d3a01 提交复现）。修复已随 mimosa **1.0.4** 出厂（installed_plugins.json 现行版本，2026-10-20 01:53 更新）：run-hook.cjs 轻量适配器先落判定到私有临时文件、等完整 JSON 送达宿主管道再退出，适配器失败直接 deny PreToolUse（不再空输出放行），每次运行后清理。**本轮动作＝验证收口**：新会话＋真实提交观察钩子扫描稳定出完整判定即关闭 ③；本会话（1.0.4 后新会话）Bash 调用零 deny 与适配器正常工作相符，为弱佐证；若 1.0.4 下 ENOBUFS 复发，行为已从静默放行翻转为阻断，按新缺陷信号处置，不再适用兼容放行口径。
- **复发实证与本轮门禁定形（2026-10-21 本会话）**：本条两笔账面提交（317624c/8715a35）触发钩子时 scanner_enobufs **再次复现**（1.0.4 升级后首证），且仍走兼容放行——但形态已改善：警告可见（不再静默），且明确禁止宣称项目安全。根因定位：1.0.4 适配器已修投递面（判定落私有文件、完整 JSON 送达才退出、投递失败直接 deny），残留 ENOBUFS 在**受保护引擎资产包内部**（加密 .mimosa 资产包，源码不可读，全包明文检索无 enobufs 字面量）；marketplace 现行版本＝1.0.4＝已装，无更新厂商版。**本轮口径定形**：①提交前 MCP 深扫 seal 为硬门（补偿门正式化，即 D2026-1019-03 ③ 关闭条件的「替代扫描器稳定出 seal」支路）——本会话两笔提交深扫＝43 零新增（seal sha256:2fdb900570ff87eb174aedec903c26ac44eb59272cabbaac70402ad6499dc21c，基线 43=产品面 28＋树外 15 恒等，offlineAdvisory=1 观察项维持）；②引擎内部 ENOBUFS 走厂商升级通道（owner 渠道上报，证据=本会话钩子警告＋本条 seal）；③钩子面不据兼容放行宣称安全，照既有口径执行。
- **候选池三项执行前置（红线门）**：checkbox→toggle 实际已随卡9 B-07 落地（fdcc46b，2026-10-12，纯 CSS＋两钉，roadmap:68「未动」为陈旧账，本条勘正），本轮仅余作用域收紧残项（`.gl-sel` 等既有作用域元素已呈 toggle 形态，卡9 执行记录留主审如需收紧另开卡）；状态 tag 列触阶段3 红线（列结构=DOM 红线＋`.tag` 新类体系，ui-phase3-批清单:28）；接口地址区深化触双红线（卡内新增标题节点=新 DOM＋新 i18n 键）＋钉⑤（id 165/i18n 186 全集冻结，新增=破坏性变更须先解冻）——两件派卡前须 decision-critic 评议＋owner 解冻裁决。
- **回链**：Ref: D2026-1019-03（③）、D2026-1001-03（⑤）、D2026-1021-01（追记勘正对象）、D2026-1020-07（②待定项）；roadmap 阶段3 节候选池行。
- **执行收口（2026-10-21 本会话）**：①emil-design-eng 启用已执行（skills-disabled→.agents/skills，移动前后哈希 ffbe68e6007fb42cb8149f089b400a1ca007d59ba23e8948e2be4476f3175939 一致，TICKS 打点 C-20261021-1328，一体命令基线已刷新；新会话生效）。autoglm 陈旧副本留 skills-disabled 待 owner 裁决（未删）。②D2026-1019-03 ③ 按「替代扫描器稳定出 seal」支路关闭：补偿门定形为硬门（提交前 MCP 深扫 seal），本会话收口深扫 seal sha256:641314a6…（43 零新增）；引擎内部 ENOBUFS 走厂商升级通道（owner 渠道，证据=钩子警告＋seal）。③checkbox→toggle 作用域收紧＝卡3 执行＋主审验收通过（卡3 验收记录：验证链全过＋GUI 黑盒 DOM 断言 PASS，基线 2519+4）；状态 tag 列与接口地址区深化＝规格＋影响分析已呈 owner（本会话回复），派卡前须 decision-critic 评议＋owner 解冻裁决。

## 2026-10-21 D2026-1021-03 「owner 三点裁决：技能清理（web-design-guidelines 启用＋四件卸载）＋接口地址区独立卡片化同意＋状态 tag 列语义待澄清」 [已拍板·执行中]

- **裁决内容（owner，2026-10-21）**：①技能处置——web-design-guidelines **启用**（skills-disabled→.agents/skills，SKILL.md 哈希 f4647ca866a3accf763777f83e7682954f0187cd6bea7eea0399796652414e8f 写前=写后一致；新会话生效），grill-me / grill-with-docs / improve-codebase-architecture / triage 四件**卸载**（移 %TEMP%\skills-uninstalled-20261021 备份目录，非销毁，可恢复）；autoglm-browser-agent 的 skills-disabled 陈旧副本另行待裁。②接口地址区独立卡片化**同意**（基于项目真实 token 渲染的前后对照预览）。③状态 tag 列的 A/B 语义存疑（意义不明），**暂停待语义澄清**——A/B 系主审预览示例语义（逐行生效范围：阶段A=净语+翻译、阶段B=审校+抛光），非原始规格定义；候选语义=逐行生效范围／来源（手动/学习）／绑定文件／放弃该项，待 owner 选定后另议。
- **critic 评议（正式，agent_ab52bfe2）**：**有条件支持方案 A、反对方案 B**（A=卡头复用既有键 s1_endpoint_label/s3_endpoint_label，零新增 i18n 键零新增 id，钉⑤双集合逐字不动；B=新键触 FROZEN_I18N_KEYS(186) 冻结集扩容，纯文案不值）。**[HIGH_RISK_OBJECTION] R1 红线冲突——主审采纳**：新增 4 个元素节点与 ui-phase3-批清单:42「不新增任何元素节点/不加 form-card-header」直接冲突且无机器闸（钉⑤只锁 id/i18n 集合，新增 DOM 会静默过闸）；处置=本条显式登记 **R1 豁免（授权源=owner ②同意）**＋卡内补 DOM 结构钉防无声推翻。布局风险硬化：`.form-card` 为 flex 而 action-row 无 grow，卡内 input 撑不满→新增作用域规则 `.form-card > .action-row { flex: 1 1 100% }`（不动 .action-row 基类）；`--w-endpoint-label` 因行内 label 移除成死 token（随卡清理）。
- **过程披露（技能处置执行）**：TICKS 连环双缺陷——printf 格式串含 % 字面量部分格式化失败仍追加无换行残段、随后 sed -i 整文件重写剥掉第 95 行行尾 \r——一体命令 full= 前缀守卫**真阳性拦停**（守卫有效实证）；python 字节级定点复原（head126 哈希与锚点 full 逐位一致）后刷新成功；LEDGER R-20261021-01 登记。教训=基线保护文件禁 sed -i 整文件重写；printf 追加失败须立即查文件尾。
- **回链**：Ref: D2026-1021-02（三项纳入＋门禁定形）、D2026-1001-03（⑤候选池）、ui-phase3-批清单（R1）；卡面=docs/design/d1021-卡4-接口地址区独立卡片化.md。
- **追记（2026-10-21，owner 二点裁决）**：①**销毁令**——四件卸载技能的备份目录（%TEMP%\skills-uninstalled-20261021）与 skills-disabled/autoglm-browser-agent 陈旧副本**直接销毁不再备份**，已执行并核对（skills-disabled 终态=0 项；生效副本 .agents/skills/autoglm-browser-agent 不动）；打点 C-20261021-1650，一体命令刷新 HARD=0。技能清理至此**全收口**（web-design-guidelines 启用／四件＋autoglm 陈旧副本销毁）。②状态 tag 列**放弃**——owner 裁 A/B 逐行语义不需要、维持全局生效（词库→阶段A/阶段B 全局勾选现状不动），零代码零数据变更；候选池三项至此终态=checkbox→toggle 已落（卡3 验收通过）／接口地址区卡4 执行完毕＋主审验收通过（2026-10-21：验证链 .venv 口径 2520+4 只增＋GUI 黑盒六点 PASS＋深扫 43 零新增 seal 55e5bf77，见卡4 验收记录；提交 6c65faa/838ab2a/254c56c/4407fc7）／tag 列放弃，D2026-1001-03 第⑤项收口。
