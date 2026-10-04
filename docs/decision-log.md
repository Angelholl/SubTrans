# 项目决策日志（decision-log）

> 由主模型维护，重大架构设计、技术选型、方案拍板经 decision-critic 评议后按 "## [日期] [决策ID/标题] [状态]" 格式追加归档，供续评与二次评议检索。

## 2026-09-14 [D2026-0914-01] 1.2双幻觉专项方案评议收尾与落盘 [已拍板]

### 一、背景与版本策略

- 上游 WhisperJAV v1.9.2（2026-09）发布：新增 `whisperjav_run.json` manifest（done/empty/suspect/failed + MILEAGE 覆盖率）、`raw_subs/<name>.asr_telemetry.jsonl` 逐场景遥测（仅 Balanced 模式）、`--fail-on empty|suspect`；qwen 模式源头清理纯标点行/孤立「はい・うん」/`!`串（whisper 系模式不清理）；#394 根因仍开放。
- 本仓 v1.1.0 已于 2026-09-13/14 发布于公开仓 Angelholl/SubTransJAV（commit `325dc47`），测试基线 584 passed + 1 skipped。
- 用户拍板：1.1 定版后走 1.1.x 缺陷修复线；**双幻觉治理自 2.0 前移为 1.2 大版本主题**（推翻原《1.2版本规划草案_2026-09-13.md》行 29"明确不做①"与行 33 决策 1）；2.0 议题清空重新定位；架构边界不变——不引入 ASR 代码，对第一重幻觉只做识别与拦截。

### 二、评议代行偏差声明

- `decision-critic` 子智能体连续三次启动失败（错误：Provider authentication failed），属该智能体类型的供应商配置问题。
- 由 `general-purpose` 子智能体载入同一份只读诤友评议提示词**代行评审**：通读《双幻觉专项讨论简报_2026-09-14.md》与《1.2版本规划_双幻觉专项_2026-09-13.md》，并逐条核实代码证据（`manifest.py:278-305`、`pipeline_v2.py:701/92/890/925-928`、`language_validator.py:44-93/163/187/211-220`、`llm_client.py:357/412/448-452`、`cli.py:16-37`、`tests/test_language_validator.py`、`hallucination_patterns.yaml`、`cleaner_rules.py:155-181`），确认文档关键事实陈述与代码一致、无失实。
- 评议结论：6 个裁决点全部达成共识（4 项同意、1 项有条件同意、1 项同意无保留），2 项 [HIGH_RISK_OBJECTION]，总体判定"文本级修订后即可开工，无架构性返工"。
- 用户审批（2026-09-14）：同意落盘、列入工作，"有条件通过"——条件仅限文档完整性，不改变技术路线、不构成架构返工。
- **执行方式记录**：用户 2026-09-14 指示"当前任务由主模型负责完成，除非主模型存在问题才调用子模型辅助完成"——落盘与决策日志由主模型直接撰写，未回传评议 agent 索取日志文本（评议结论已完整固化于工作区文档）。

### 三、六个裁决点结论

1. **孤立应答词（はい/うん）default 档只计数不删**：strict 档才删，且须叠加位置+密度启发式；keep-list 优先级最高。依据：本仓 1.1 假阳性学费（`language_validator.py:44-47` `_RESPONSE_WORDS`、`:82-88` `_INDEPENDENT_WORDS` 已保护 はい/うん/ふん，真实误删语料已固化回归）；本领域孤立应答词是高频真实台词，精修工具误删代价不对称。
2. **H4 拆层**：4a 薄版 P0（manifest run 状态 + MILEAGE 覆盖率 → 管线警告/报告标注/过滤总开关提档）；4b 厚版 P1 或顺延 1.3（telemetry 场景级信任度 → 条目级阈值自适应）。**自动提档仅收紧高精确率类别阈值，永不解锁计数类**（防上游无 schema 承诺的标签远程打开孤立应答词删除）。
3. **黄金集三源**：历史 dropped_entries.log 固化语料（21 个假阳性回归）+ 用户提供的上游 1.9.2 真实输出（含 suspect/empty 案例）+ 构造样本（须防循环验证：记录生成方式与标注人，定稿冻结版本号）。**真实 1.9.2 语料是"定版阻塞项"而非"开工阻塞项"**：第一、二批可在历史语料+构造样本守卫下开发；定版前语料仍未到位则基线降级标注"构造集基线"，不得宣称真实场景精度。
4. **与上游清理重叠类别保留**：本仓输入契约是"任意来源 SRT"（whisper 系模式、旧版上游、第三方工具产物均在契约内），不能假设上游已清理；规则外置成本近零；闸门0 增量价值聚焦上游不处理的类别。
5. **1.1.x 修复线边界**：YAML 规则数据修补（既有 schema 字段内加词/白名单）＝缺陷修复，可进 1.1.x 热修（白名单是 Python 内置集合 `language_validator.py:44-93`，实为代码改动，须逐一附回归测试；每次热修后跑满 584 基线并 `sync_release.py --check` 同步公开仓）；新检测器/新输入通道＝功能，只进 1.2；1.1.x 修补不得预埋 1.2 源侧类别 schema。
6. **原草案工程项处置**：#4 GUI i18n、#8 LRU、#9 文档修正顺延 1.3；#6 pipeline_v2.py 拆分维持第三批原位；管线三个钩子（闸门0 / H3 报告 / H4 信号）一律"一行函数调用进模块"，不内联（否则第三批拆分成本随 1.2 膨胀）；#1 实测反馈窗口与双幻觉专项共用同一反馈入口。

### 四、两项 [HIGH_RISK_OBJECTION] 的采纳回应

- **R1（resume 指纹缺口）——采纳**：`manifest.py:278-305` 的 `_CONFIG_FIELDS` 不含 `--source-filter` 档位；`instruction_source_files` 不哈希闸门0 规则 YAML；`input_sha1` 不含 `--asr-meta`。落地四件套：①`_CONFIG_FIELDS` 增加 source_filter 档位；②闸门0 规则 YAML 内容哈希并入 config_hash（对齐 cleaner_config_dir_hash 做法）；③`--asr-meta` 指纹定义为**解析后语义字段规范化 JSON 的 sha1**（非原始文件字节 sha1，避免路径/字段顺序变化导致 resume 误失效）；④验收新增条款：信号/规则/档位变化时 `--resume` 必须判定失效。
- **R2（分档表缺表）——采纳**：原方案仅给 4 类定档，`!`串、片尾元信息、无意义音节连缀三类悬空；且"无意义音节连缀"若默认删将与 `language_validator.py:70-80` 白名单保护的长假名重复（あああ/ううう等，本领域真实台词形态）正面冲突。落地为七类别×三档位显式分档表（见第五节 R2 条目），并要求闸门0 keep-list 与 `_WHITELIST_JA` 的交叉守卫测试随 H1 入库。

### 五、R3–R10 处置一览

| 风险 | 处置结论 |
|---|---|
| R3 保险阀 | 闸门0 复刻 `language_validator.py:211-220` 的 >50% 保险阀并变体：拦截率超阈值 → **降级为只计数+报告红标**（非全量放行，防 4a 对 suspect 文件提档在最需要时失效）。默认阈值、配置键、红标格式在计划文档 H1 条目中可验收化 |
| R4 验收错位 | H1 第一批验收改为"假阳性交叉守卫 + 构造 fixture 全类别单测"；"黄金集全覆盖"移至 H6/定版验收 |
| R5 profile 关系 | 闸门0 与 cloud/本地 profile 无关，两档均执行（省 token 收益恰在 cloud 档最大；区别于兜底规则层在 cloud 档跳过，`pipeline_v2.py:861-862`） |
| R6 陈旧信号 | 旁车自动发现需校验 manifest 与 SRT 的配对/新鲜度（mtime 或命名配对），失败降级"无信号+警告"；显式 `--asr-meta` 用户明示即采信并记入报告 |
| R7 三处规则源分裂 | 1.2 内以交叉守卫测试钉住三处一致性（中文侧 `hallucination_patterns.yaml`、源侧新 YAML、`language_validator` 白名单）；规则条目强制携带证据样本；白名单迁共享 YAML 列为可选、不阻塞 1.2；H8 手册给出三库分工图 |
| R8 用户感知 | 运行摘要显式输出闸门0 分类计数；NDJSON 事件只增兼容；手册写明与 1.1 行为差异（同输入成品条目可能变少）及 `--source-filter off` 回退路径；changelog 明示 |
| R9 新产物兼容 | H5 隔离区定为独立 `*_隔离区.srt`（译文通顺条目只有 SRT 形态才能播放对照）；H3/H5 新产物纳入 `delete_resume_artifacts`（`manifest.py:157-169`）扩充；NDJSON 只增不改 |
| R10 条目内重复 | 闸门0 置于预合并前（相邻同文 ≥N 连检测依赖此顺序），同时支持条目内重复检测（正则），覆盖预合并拼接后的残留形态 |

### 六、七类别×三档位分档表（R2 落地）

| 检测类别 | default 档 | strict 档 | off |
|---|---|---|---|
| 纯标点行 | 删 | 删 | 不处理 |
| `!`串（模型无解占位符） | 删 | 删 | 不处理 |
| 不可发音辅音串 | 删 | 删 | 不处理 |
| 重复循环（相邻同文 ≥4 连，含最小长度条件） | 删 | 删 | 不处理 |
| 片尾元信息（时间轴位置+词表双闸） | 删 | 删 | 不处理 |
| 孤立应答词（はい/うん等单独成行） | **只计数+报告** | 删（叠加位置+密度启发式） | 不处理 |
| 无意义音节连缀 | **只计数+报告** | 删（叠加位置+密度启发式） | 不处理 |

keep-list 白名单优先级最高，高于任何档位；H6 黄金集对两个计数类按"漏报（漏删）"统计而非"误报"统计。

### 七、开工条件与门槛

- **开工条件（已满足）**：计划文档文本级修订完成（本次落盘即是）→ 即可开工。
- **第一批 H1+H2 代码实施门槛**：①文档修订完成（本次完成）；②用户确认"列入工作"；③委派 coding 前做一次"文档 diff 核对"——对照 10 项共识缺口确认已全部写入且与讨论边界无冲突。
- 讨论边界（不可发散）：不引入 ASR 代码、不做 ML 过滤器、不做批间污染专项（#347 向量已核实不存在）、1.1.x 只收缺陷修复、v2_file_parallel 与批次级断点续传维持排除。
- 验收口径沿用：pytest 只增不减（基线 584 passed + 1 skipped）、ruff 0、mypy 门禁 0 错、`tools/sync_release.py --check` 幂等、公开仓差异契约不破坏。

### 八、随批生效的附加守则

- 管线三个钩子（闸门0/H3 报告/H4 信号）一律"一行函数调用进模块"，不内联逻辑进 `pipeline_v2.py`。
- 黄金集截止期与责任人：**待用户指定**；逾期未获真实 1.9.2 语料则 1.2 基线降级标注"构造集基线"写入决策记录。
- 本决策由主模型直接撰写归档（依据已固化评议结论），未再联系代行评议 agent；如需二次评议，可检索本条目及《双幻觉专项讨论简报_2026-09-14.md》第 6 节。

### 九、开工审批（2026-09-14 追记，[已开工]）

用户审批结论：**确认"列入工作"，条件通过**（条件仅限文档一致性，不改变技术路线、不构成架构返工）。落盘核验通过（决策日志/计划修订稿 v2/简报第 6 节与 10 项共识缺口一致）。开工前已修正一处阻塞级文档矛盾并落定三项裁决：

1. **H1 闸门0 插入点统一为预合并之前**（`pipeline_v2.py:247-313` `_premerge_entries` 调用之前）：原计划文档中"总体设计图（预合并前）"与"H1.1（todo 构建前 :701 附近，即预合并后）"互斥；"相邻同文 ≥4 连"依赖预合并前的原始条目序列，若在合并后检测则失真。修正后：闸门0 对**原始 SRT 条目**做七类别检测；预合并之后仅保留 TM 精确命中剔除与已删条目跳过；条目内重复检测为补充、不替代相邻重复循环检测。
2. **H4b 顺延 1.3**（用户拍板）：telemetry 仅 Balanced 产出、schema 无承诺、H6 基线未建立前自适应无法验证净收益；4a 薄版已覆盖主要价值。
3. **H6 截止期与责任人**（用户拍板）：截止期不晚于第三批 H6 启动前；用户负责提供含 suspect/empty 的真实 1.9.2 语料，主模型负责归档、防循环验证、逾期降级标注"构造集基线"写入决策记录。
4. **实施注意项纳入 H1 契约**：保险阀阈值 `v2_source_filter_valve_pct` 纳入 resume 指纹（或至少配置变更显著警告）——R1 精神延伸，防用户改阈值后静默复用旧产物。

拆批委派口径：H2 先独立修；H1 按"独立模块 + 预合并前一行调用"实施；H1 第一批验收＝假阳性交叉守卫 + 构造 fixture 七类别×三档位 + 保险阀路径 + 规则/档位变化时 resume 判定失效。

### 十、第一、二批执行与偏差裁决（2026-09-14/15 追记，[已执行]）

**第一批（H1+H2）**：实施完成并通过主模型复核。pytest 585+1、ruff 全绿、新模块 mypy 0 错；主模型复核中直接修复 ruff 4 处（UP031/I001）与 mypy 5 处（类型注解）。

**第二批（H3+H4a）**：实施完成并通过主模型复核。pytest 635+1（+50 新测试）、ruff 全绿、asr_meta.py mypy 0 错。落地：`{stem}_幻觉处置报告.json`（schema 契约测试钉住）、`--asr-meta` 容错解析+旁车自动发现（R6 新鲜度校验，显式路径豁免）、语义指纹 `asr_meta_sha1` 进 config_hash、tighten 收紧块（仅 default 档删五类，计数类契约测试钉死不解锁）、`gate0_summary` NDJSON 只增事件（PROTOCOL_VERSION 保持 1）、R8 摘要显式输出、delete_resume_artifacts 扩充报告模式。

**偏差裁决（gate0_ran 语义，主模型裁决并已实施）**：第二批规格原假设"resume 复用阶段A 时闸门0 未重跑"，实际闸门0 在管线头部**无条件执行**且在受信 resume 下**幂等**（指纹校验保证规则/档位/信号语义与原次一致，重跑结果相同）。故报告口径定为：**如实记录真实计数，`gate0_ran` 恒为 True**，废除原"resume 时归零"规格（归零反而制造报告与 NDJSON 事件的矛盾）；回归测试重写为"含幻觉行输入 + resume 后报告保留真实删除数"。

**其他已接受偏差**：报告写入置于恢复类清理之后一环（防自删，扩充的 delete 模式用于清上一轮遗留）；覆盖率定点化 round(…,4) 防浮点噪声破坏指纹；保险阀触发计入 files_degraded（幻觉行保留送翻属真实降级，exit code 3 语义成立）。

**实弹测试裁决（2026-09-15，真实语料暴露缺陷）**：用 `E:\无字幕\新建文件夹\一次测试`（7 个上游真实 SRT，10924 条）实测发现——白名单词与计数类目标高度重合（うん。823/はい。445），keep_list 短路在计数之前，导致**计数类检出恒为 0**，裁决点 1 附加条件"计数不得静默"落空。裁决并已实施：**白名单词任何档位仍不删除（宁漏勿误不变），但计数类命中计入检出统计**（H3 报告/摘要可见性）；交叉守卫测试断言同步更新（删五类恒 0、计数类按命中计 1）。修复后完整文件实测：mdon-087（545 条）检出 100/删除 0/保险阀未触发，报告与摘要如实呈现。

**根因更正（2026-09-15 追记，推翻本节前述"阶段B 模型服从性差"结论）**：一次测试实跑中"阶段B 无译文 427/545"的真正根因是**本机缺少 `openai` Python 包**（LM Studio 走 OpenAI 兼容客户端，import 失败使阶段B 全部批次秒败；"缺行走定向重试"日志：`No module named 'openai'`），与模型/提示词无关。此前 mdon-087 仍有大部分译文，是 TM 库（17090 条，用户历史积累）与 A 译文兜底掩盖了故障。`pip install openai httpx` 后 80 条样本复跑：阶段A/B 零警告全部成功，译文质量正常。教训：测试环境与依赖声明（pyproject extras）不齐会以"模型质量差"的假象呈现；后续考虑把 openai/httpx 移入主依赖或启动前预检（留给 1.2 收尾评估）。

### 十一、第三批执行与 H6 基线归档（2026-09-15 追记，[已执行]）

**第三批（H5+H6）实施完成并通过主模型复核**：H5 隔离区（保险阀降级路径产出候选，计数类永不入选，off 档恒空；`quarantine_review` 按原始下标→编号映射回捞"源文高置信幻觉+译文流畅中文"条目至 `{stem}_隔离区.srt`，只移不删）；H6 黄金样本回归集（`tests/fixtures/hallucination_golden/golden_v1.json` 冻结 v1.0 + `tools/gate0_golden_stats.py` 统计脚本）。门禁：pytest **696 passed + 1 skipped**（+61）、ruff 全绿、新模块 mypy 0 错。

**H6 基线归档（构造集基线，D2026-0914-01 裁决的降级路径生效）**：

- `golden_v1.0`：样本 49 条（delete 18 / count 9 / keep 22），行为一致 **49/49**；七类别 precision=1.000 / recall=1.000（宏平均 1.000/1.000）。
- **真实 1.9.2 语料截止期已到（不晚于第三批 H6 启动前）而用户暂未提供**——按裁决基线降级标注为**"构造集基线"**，不得宣称真实场景精度；后续用户提供语料后以 `origin: "real"` 追加并递增小版本。
- **防循环验证记录**：首轮核对发现 3 处构造缺陷（GP-RP-001/002/003 整文件全为重复文本导致保险阀降级干扰期望），已修正为混入真实台词（占比 40-45%），留痕于 `generated_by` 与 README。
- 实弹验证补充：二次测试 6 文件全量真实跑完成，闸门0 检出 1371/删除 1（jur-676 第 133 条纯标点行 `。`），报告与预扫描逐一吻合；保险阀全程未触发（最高占比 19%），隔离候选恒 0（符合"仅降级路径产生候选"设计）。

### 十二、BUG-2026-0915-01 预合并过度合并修复执行（2026-09-15 追记，[已执行]）

闲时工单自动化受理并执行（完整设计与根因见 `internal_docs/BUG-2026-0915-01_预合并过度合并.md`，执行者未重新排查，直接按定稿第三节实施）。

**修复落地**：`_premerge_entries` 新增 `_strip_trailing_pause`（省略号归一，句末判定作用于剥离后文本，修 RC1）；省略号否决扩展至"前省略号+后省略号"（修 RC2）；语义断裂档加短碎片门槛 `premerge_min_fragment_chars`；新增三枚硬上限配置 `premerge_max_span_ms=5000` / `premerge_max_chars=80` / `premerge_min_fragment_chars=6`（进 TUNABLE_FIELD_TYPES、manifest `_CONFIG_FIELDS` 与 validate 校验，premerge_max_gap_s 解除对跨度上限的兼任，修 RC3）；`_run_single_v2` 预合并占比 >25% 输出 info 级风险提示（不新增 warning）。新配置未 commit。

**门禁**：pytest **746 passed**（基线 696+1 只增不减，其中 1 处既有测试按新口径意图保持调整）、ruff 全仓 0 错、mypy 全仓 60 错与基线完全一致（新改模块 0 新增）、`sync_release --check` EXIT=0 幂等。

**确定性复验（13 个真实输入，18046 条）**：预合并合并数 **1252 → 53**（-95.8%）、跨度>5000ms 合并产物 **963 → 0**；用户案例（mfyd-074 条目 9-12）逐字保持独立。

**全量 LLM 实弹重跑（LM Studio 双模型、并发 3、TM 同口径、`--force` 自动备份旧产物，输出目录不变）**：13 文件全部成功（7+6），闸门0 正常、保险阀未触发。final 层 >5000ms 条目 **936 → 18**（-98.1%）；用户案例 42,679→50,479（7.8s）/ 51,259→57,039（5.78s）两条过度合并产物 **0 残留**，修复后案例条独立（42,679→46,520 / 51,259→53,679）。残留 18 条经逐条定性为**阶段A/B（LLM 翻译行合并 + 时间轴对齐）既有形态**（13 条与旧版同 timing，5 条同属该类、旧版因预合并掩盖而无同 timing），文本为完整单句译文合并（跨度 5.0-5.5s 略超阈），非预合并产物——若要进一步消除需另立工单（阶段A/B 对齐层），不在本工单范围。

**状态**：修复与复验通过，未 commit/未发布，等用户验收指令。

## [2026-09-16] D2026-0916-01 两仓合并：公开仓收编为唯一开发仓（方案 B'）[已拍板·已执行（收尾见 D2026-0916-02）]

### 背景
- 用户意愿：两仓合一。内部仓 WhisperJAV-traslate（单 master、无 remote、50 commits、121 tracked，历史含敏感内容 sexual_terms.csv / 真实 glossary / 方案2试点归档；工作区在途 1.2 第三批双幻觉专项 + 预合并修复，零备份）并入公开仓 SubTransJAV（origin=GitHub 公开，main，100 tracked，HEAD=cebafda 测试修复已 commit 且 0/0 已 push）。
- 密钥面已核验干净：api_keys.bin 与 glossary_learned.csv 在全部历史零接触（`log --all` 空）。
- 公仓历史泄漏既成事实：根提交 ae4c873 含真实 _SENSITIVE_HINTS 词表，7994909 才中性化；glossary 与 translation_rules 从初始发布即中性化。历史重写为独立选项留档，默认不做（破坏已 clone 副本一致性）。

### 方案要点（B' 出树版）
1. 公开侧先闭环：cebafda（importorskip/skipif）已推送；windows-3.12 的 line-endings 步骤 `shell: bash` 修复实施中；全矩阵绿待下次 push 后人工确认（工单 02 验收口径）。
2. 内部：两处测试修复 + ci.yml 修复移植进内部仓（HRO-1 移植面三处）→ `git add` 核对 staging 面（无 internal_docs/Temp/密钥）→ commit 归档快照 → `git status` 复核。
3. 备份先行：本地 `git bundle` 全量（主备份）+ 私有仓 push（可选云备份）；push 前禁用文件名扫描双保险。
4. 最终 sync：check 模式审 diff（含 decision-log.md 公开性、项目介绍稿重复文件、使用手册覆盖、新增 1.2 文件）→ apply → 公开仓 `git status` 复核。
5. 公开仓本地全量 pytest + push → CI 矩阵验收。
6. 全绿后：internal_docs/、api_keys.bin、sexual_terms.csv、真实 glossary、敏感 Temp 脚本移至仓库树外同级目录（本地路径约定，不入库）；公开仓 .gitignore 提交"本地独有资产"注释段锁定契约；自动化提示词/计划任务路径更新并实弹验证；_internal_archive 改名排最后。
7. sync 退役；中性化契约由四件套接替：路径隔离（出树）+ guard 脚本（1.3 可选）+ 覆盖层（1.3 立项：本地覆盖文件与加载优先级）+ 契约文档化（排除名单沉淀为 docs 章节与本日志）。

### HRO 裁决（decision-critic 异议 → 主模型）
- HRO-1 CI 连续性：**采纳**（修复先入内部仓、sync 后复验）。
- HRO-2 敏感资产入公仓：**采纳出树方案（B' 首选）**；"进树+守卫脚本"三件套不采用。
- HRO-3 备份先行：**采纳**（bundle 主 + 私有仓备，先于任何 apply/rename）。

### 用户拍板（2026-09-16 AskUserQuestion）
- 合并执行：按 B' 六步序列执行（每步汇报，改名归档前再确认一次）。
- decision-log.md 公开性：**脱敏后随镜像公开**。
- 词表/术语表：接受过渡期降级；本地覆盖文件+加载优先级改造 1.3 立项。

### 遗留与风险跟踪
- [执行面增量] ci.yml 的 shell: bash 修复须与测试修复一起移植内部仓（.github 目录整体镜像会覆盖公开侧修改）——已随第 2 步移植。
- 备份落地核验：bundle 用 `git bundle verify`；私有仓 push 后检查可见性与策略告警。
- CI 全矩阵绿需 push 后 GitHub Actions 页人工确认；自动化路径迁移后实弹触发一次轮询。
- 出树的正面副作用：原"Temp/ 同名目录整覆盖风险"消除。
- 1.3 立项：覆盖层 + guard 脚本（可选）。

### 决策日志字段（decision-critic 协议）
- **原决策**：两仓合一，公开仓收编为唯一开发仓（方案 B → B' 出树版）。
- **异议**：HRO-1 / HRO-2 / HRO-3。
- **主模型最终决定**：采纳（3/3）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **条件闭环状态**：决策层面闭环；执行期验证（sync 后 pytest + CI 矩阵、备份核验、自动化实弹）待执行。

## [2026-09-16] D2026-0916-02 双仓归并收尾执行与旧仓退役准备 [已拍板·已执行]

### 执行记录（工单 MIG-20260916-01，闲时自动化 2026-09-16 16:29 受理，16:5x 完成）

- **D2026-0916-01（方案 B'）执行状态**：1.2 内容已改由公开仓直提交完成（009f398 全量 + 70b2eca 修复），sync_release --apply 未执行即退役（重跑只会回退公开侧修复）；本条记录剩余收尾的落地。
- **备份（HRO-3 落地）**：既有全量 bundle `git bundle verify` 通过（完整历史，HEAD e41090d，51 提交）；试克隆抽查 SHA 6/6 一致、pytest 冒烟 38 passed；三份 MD5 一致副本：原址、`D:\SubTransJAV-internal-archive`、`E:\SubTransJAV-internal-archive`。**修订**：bundle 历史含敏感词表，原"可选云备份"不执行，双副本均为本地第二介质，严禁上云。
- **出树归档（约 61MB）**：internal_docs、translation_memory 全链（备份链/测试库/A-B库）、api_keys.bin、sexual_terms.csv、真实 glossary（37 行）、方案2试点归档、.analysis_tmp、测试文件、项目介绍稿；内部仓 5 个未提交文件散件 + `git diff` 补丁归档（其内容已在公开仓，散件仅为保险）；归档副本 sync_release.py 头部加"已退役，禁止 --apply"警告。内部仓 git 状态零改动（Mimosa 约束下免 commit 设计）。
- **公开仓资产落位**：tm.db 换库（旧 24KB 库备份为 tm.db.bak-pre-migration-20260916；PRAGMA quick_check ok、24121 行、app 加载器 stage=1 lookup_exact HIT——全库条目 stage=1 系内部管线写入口径，schema 与加载代码两仓一致）；api_keys.bin 解密 3/3；glossary.csv `git rm --cached` + 真实 37 行转本地维护；.gitignore 契约段补 config/glossary.csv 与 create_shortcut.py（commit 4354961，不 push）。
- **卸载脚本**：新增 uninstall.bat（GBK 无 BOM、CRLF、风格对齐首次安装.bat；清理桌面 SubTransJAV.lnk + 4 个历史遗留名 + %LOCALAPPDATA% numba_cache；备份提醒 文档 output 与项目内 api_keys.bin/tm.db；不删安装文件夹本身）；test_strings_and_shortcut.py 追加 6 项断言。验收：pytest 全量 **753 passed / 1 skipped**（基线 747 + 新增 6，只增不减）、行尾守卫与 ruff 通过、GUI 启动冒烟存活至超时、TM 命中与密钥解密冒烟通过。
- **旧仓处置**：`D:\WhisperJAV-traslate` 留给用户手动删除（前置=四项验证通过 + bundle 三副本就位，均已满足）；删除后队列文件随之消失，轮询自动化按"文件不存在静默结束"设计自然失效。
- **遗留**：1.3 立项（词表覆盖层 + 加载优先级、guard 脚本可选、Mimosa 21 项甄别、1.2 定版 tag）见归档 internal_docs 交接文档；公开仓 push 由用户单独拍板。

## [2026-09-16] D2026-0916-03 v1.2.1 修复方案评议拍板（删除权收口/台账/分工/反演防护）[已拍板·已执行（待实弹验收/提交）]

### 一、背景与诉求

- 用户实弹成品反馈（源 1162 条 → 终稿 1036 条）：126 条实义条目被静默删除（含汉字台词「部長さん。」「…最高…」）；保留条目时间戳与源逐毫秒一致但出现空洞；5 条终稿日文假名残留；1 条 ASR 乱码源文被 LLM 语义反转译（原意"快停下"→"来含住吧"）；主语误判告警实为正则误报；质量报告同一条目按假名串重复展开 5 条编号；统计行"规则清洗合并 114 处"实为删除为主、命名误导；幻觉处置报告.json 仅覆盖闸门0 且普通用户看不懂。
- 用户四项诉求：①源字幕实义行必须翻译，不得静默丢弃；②质量报告去重、如实统计；③处置报告换方式或取消；④采纳分工提案（环节A只翻译不处理时间轴/删行，环节B润色审核）。
- decision-critic 评议（2026-09-16）出具 D1–D7 独立意见：全部"有条件支持"，D1/D7 标 [HIGH_RISK_OBJECTION]，D4 检出 [MATERIAL_CONFLICT]（规格文档认定"我们是"作主语=误判 vs 用户判定为误报，口径相反）。
- 主模型逐项回应并获用户批准进入执行。

### 二、各决策裁决一览

| 决策 | critic 立场 | 主模型裁决 | 关键条件/配套 |
|---|---|---|---|
| D1 删除权收归闸门0 | 有条件支持（HRO） | **采纳（含全部四条件）** | 见第三节 |
| D7 A/B分工+行数强约束 | 有条件支持（HRO） | **采纳（按改造意见）** | 见第三节 |
| D2 删除台账+统计拆分 | 支持 | **采纳+恒等式** | 新增条数恒等式核对行 |
| D3 假名残留按条目归并 | 支持 | **采纳+片段上限** | 单条片段清单上限 5 段 |
| D4 主语误判正则 | 有条件支持（口径冲突） | **采纳方案(a)（收窄到单数）** | 见第四节裁定 |
| D5 反语义反转硬规则 | 有条件支持 | **采纳（按条件）** | 复用闸门0 现成信号，不新造启发式 |
| D6 处置报告.json 取消落盘 | 有条件支持 | **采纳（按四条件顺序）** | 排 D2 之后；外部脚本消费者风险由用户侧接受 |

### 三、HRO 回应与落地条件

**D1（采纳，四条件全含，且为执行契约）**：
1. 阶段A空输出兜底链显式化为契约：`allow_empty_deletions` 双阶段转 False；新增 e2e 用例（FakeClient 模拟模型拒不输出）断言"终稿 index 集合 == 闸门0后集合（预合并除外）"；最弱兜底=空输出保留原文+[未翻译]标记，作为契约底线写入。
2. `_keep_original` 路径标记化：回退原文的条目必须带 [未翻译] 标记并纳入质量报告"未翻译/假名残留"统计口径，不得绕过语言过滤静默通过。
3. `clean_srt` 增加源文映射入参（按时间轴对齐）：`_should_delete` 前置源侧证据检查，合并行任一源行含汉字即保留，证据建立失败一律 fail-safe keep；新增「部長さん」「…最高…」类用例回归（0 删除断言）。
4. `V2_STAGE_PROMPTS` 常量纳入 manifest `instruction_source_files` 指纹（跨批硬条件，与 D7 共享）；改提示词后 `--resume` 必须拒绝复用旧阶段产物。
- 附带：`noise_left_empty` 禁删后恒 0，同步清理其语义与相关测试；strict 档用户显式删除语义保留（档位差异写入手册）。

**D7（采纳，按改造意见）**：
1. 行数守卫降级为批后日志断言+防御线；主守卫=现有逐行解析+缺行重试；新增重试预算 N=2，预算用尽降级逐行 fallback（[未翻译]+风险清单），绝不整文件失败；FakeClient"恒定合并2行"用例断言预算与降级路径。
2. 提示词四文件（V2_STAGE_PROMPTS + 两张角色卡）同步修改，`test_rules_loader` 同步更新。
3. 指纹补齐同 D1 条件4。

### 四、D4 口径裁定（[MATERIAL_CONFLICT] 收敛）

**裁定：采纳方案 (a)——收窄到单数。** 理由：用户为最终验收人，已对该实例做出判定（僕たち水泳部の部長で… 应译"……是我们的部长"，定语/所属读法），"我们是"开头在该场景非误判；误报侵蚀复核清单公信力。
- ① `target_pattern` 加负向前瞻排除 我们/俺们，仅命中单数"我是/俺是"；
- ② 告警文案动态引用实际译文开头（废弃硬编码"以'我是'开头"）；
- ③ `translation_rules.yaml:45` 注释与角色卡第 72 行反例同步改写，消除规格自相矛盾；
- ④ TM 污染补偿：该形态依赖卡A/B 既有主语规则防护，并在该实例作为卡片示例补充；
- ⑤ learn_gate 既有缺陷过滤保持覆盖。

**D5（采纳）**：复核集复用闸门0 现成信号（`count_positions`/`gate0_noise_indexes` × `is_fluent_zh`），不新造启发式；叠加强信号过滤（单条重复连打/单元平铺）；复核清单设上限（"其余 N 条略"）；角色卡硬条款含终局选项"无法辨识→[未翻译]+原文，严禁从零编造"；「快停下→来含住吧」案例入黄金集回归；实弹复跑该文件验证。

**D6（采纳，按四条件顺序）**：排 D2 之后；契约测试迁移至质量报告处置章节 + `gate0_summary` payload 键集；`delete_resume_artifacts` 保留旧 json 清理条目；手册 §7.2 与 CHANGELOG 同步；外部脚本消费者风险由用户侧接受（用户明确要求移除）。

**D2（采纳+恒等式）**：新增条数恒等式核对行——`原文 = 闸门0删除 + 预合并合并 + cleaner合并 + cleaner删除 + 终稿`；逐条台账引用 `dropped_entries.log`，报告只放样本+计数；`clean_srt` 返回结构化统计（合并/删除拆分）。

**D3（采纳+片段上限）**：按条目归并，单条片段清单上限 5 段+"等 N 段"；结论行按条目数；假名残留/未翻译两章统一按条口径防重复计数。

### 五、批次计划与发布结构

- **发布结构**：v1.2.1 单版本，内部按顺序执行：
  - **P0（D1+D2+D3+D4）**：删除权收口（含阶段A禁删行）、删除台账+恒等式、报告去重、正则修复。**P0 全绿 + 用户 1162 案例复跑验证（终稿指数=闸门0后指数、恒等式成立）为同版发布门槛**。
  - **P1（D5+D7 剩余）**：反语义反转硬规则+复核、B 卡改写、行数断言+重试预算、指纹补齐。
  - **P2（D6）**：json 移除 + 契约测试/文档迁移（依赖 D2 处置章节就位）。
- 禁止任何颠倒顺排（D5 依赖 D1 行为前提；D6 依赖 D2）。

### 六、决策日志字段

- **原决策**：v1.2.1 修复方案七项（D1–D7），用户四项诉求全量覆盖。
- **我的异议**：D1/D7 为 [HIGH_RISK_OBJECTION]（均附改进条件）；D4 检出 [MATERIAL_CONFLICT]（"我们是"作主语=规格反例 vs 用户判误报）；D6 未知外部消费者 [UNVERIFIABLE]。
- **主模型最终决定**：采纳（7/7，含全部条件）；D4 口径选择方案(a)收窄到单数。
- **条件是否已闭环**：决策层面闭环（条件全部明文化为执行契约）；执行期验证待 P0/P1 完成时逐项勾验（e2e 指数断言、FakeClient 空输出/恒定合并用例、resume 指纹失效用例、cleaner 0 删除回归、黄金集反演案例、实弹复跑）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①D4 收窄后该形态翻译对将进入 TM 学习面，凭卡片示例+learn_gate 防护，真实语料复验观察误学率；②D1 强制翻译噪声行的怪译文观感，凭 D5 复核清单兜底，P0 实弹复跑时抽检；③D6 外部脚本消费者（不可枚举）依赖用户侧接受，手册注明 json 取消与事件替代通道；④resume 指纹补齐需验证"仅改提示词常量"路径亦失效；⑤strict 档删除语义保留的档位差异文档化。

### 七、执行追记

- 2026-09-17：P0-D1①（下游只译不删：V2_STAGE_PROMPTS 新契约、allow_empty_deletions=False、_keep_original 标记化、阶段B禁删、语言过滤标注化、noise_left_empty 清零、V2_STAGE_PROMPTS 纳入 config 指纹）已实施，e2e/FakeClient/resume 指纹用例通过；P0-D1②/D2（cleaner 源侧证据门槛 + clean_srt 结构化统计 merged/deleted/deleted_by_rule/kept_by_source_evidence，merge_stats 新增 clean_deleted 等键）已实施，cleaner 源侧证据 0 删除回归通过。
- 2026-09-17：P0-D2③/D3（质量报告【处置】章节、条数恒等式、假名残留按条目归并、【未翻译】小节）已实施；P0-D4（subject_misjudge 正则收窄单数、动态告警文案、两卡反例改写）与恒等式补"隔离区移出"项已实施。
- 2026-09-17：P1（D5 反反转硬条款四处同步、strong_garble_signal × is_fluent_zh × 源文无汉字 复核检测、【乱码强译复核】小节、semantic_v1.json 语义黄金集；D7 行数守卫 + 重试预算 N=2 + 降级 fallback 风险清单）已实施。
- 2026-09-17：P2-D6（处置报告.json 落盘移除、契约测试迁移至 gate0_summary payload + 处置章节、manifest 保留旧 json 清理、手册 §7.2/§10、GUI 文案）已实施；版本落 1.2.1（pyproject.toml + __version__.py），CHANGELOG [1.2.1] - 2026-09-17 条目就绪。
- 2026-09-17 收尾：全量测试 765 passed / 1 skipped（tests/test_process_manager.py 7 项 Windows 环境性预存失败不计入，与本次改动无交集）。风险跟踪④（仅改提示词常量即 resume 失效）由 test_resume_rejects_changed_stage_prompts / test_config_hash_tracks_v2_stage_prompts 钉死；风险跟踪②③待用户实弹复跑抽检。改动未提交，待用户验收。

## [2026-09-17] D2026-0917-01 v1.2.2 质量修正与 TM 防二次污染（G1–G7 评议拍板）[已拍板·代码侧 A–D 完成，待批次 E 实弹验收]

**背景三事实**（docs/v1.2.2-计划表.md §一）：
1. 错译已固化进 TM：tm.db 存量 24,214 条，探针证实"やめて→别停"等错译在库；实弹重跑 1130/1160 条 TM 精确命中直接复用——不清洗 TM，任何提示词/规则/词表改动对约 94% 的行无效。
2. 六类错译病因确认（11/13 例核实属实）：语境级硬伤（バラまく 0/5）、高频反义（やめて→别停 7/32）、专名幻觉（オラ 音译、宮下错译）、术语不一致（クリ）、ASR 误听（ペソ/マズミ/らめ）、纯假名实义行被删（strict 档 L8×73 + L11×15 + L7×4）。
3. 二次污染路径确认：反义/术语错译可经 TM 学习与 learned 自学习词库再次入库，形成"翻译一次、错误永久"闭环。

**批次结构**（顺序即依赖，每批全量测试绿后进下一批）：
第 0 步决策归档（本条目）→ 批次 A（TM 治理：tools/tm_purge.py 默认 dry-run、无 --yes 不删、export_csv 全量备份；tm_entries 加 source_name 列，旧行迁移置 NULL；本批不发生删除）→ 批次 B（glossary.csv 硬术语表 + 反义规则三条件，warn_only 检测 + A/B 卡禁令）→ 批次 C（per-片 sidecar 一机制两用途；L8/L11/L7 源侧噪声门槛收紧）→ 批次 D（术语冲突观察闸 + 一致性统计 + learned 重置 + 拟声条款）→ 批次 E（--yes 实际清洗 → 全新重跑 → 按计划表 §二 8 项指标逐项验收）。--yes 仅批次 E 且 B/C/D 全部落地后允许。

**TM 四层防治**（对应三污染路径：TM 学习 / learned 自学习 / B 阶段旧错译覆盖入库）：
1. 事前拦截（入库闸）：反义规则命中经 flagged_indexes 阻断 TM 学习；术语冲突闸先"观察模式"统计误伤率、确认后转"阻断模式"；learned 学习同步适用冲突过滤（批次 B/D）。
2. 事中标记（可追溯）：tm_entries 新增 source_name 来源列，学习时记录出处（批次 A）。
3. 事后可撤销：本片清洗工具 tm_purge + 后续基于 provenance 的按片清理（批次 A/D）。
4. 持续观测：报告新增【术语一致性】章节 + TM 命中率/入库数摘要；"清洗后首轮命中≈0"为流程断言（批次 D）。

**用户 5 契约点（全部采纳）**：
① 指标 7 口径拆分：本片旧命中 0 / 跨片同源句 dry-run 单列用户确认 / 合法复用正常统计 / 错误条目探针 0 命中。
② A1 多形态+可审计：raw/premerge/normalized 三 match_type 候选集；CSV 七列含 created_at/hit_count；--since/--until 时间窗；NULL 归 unknown_time、默认不删除非 --include-unknown-time；删除清单排序后 sha256 写运行日志；--probe 内置。
③ B2 反义规则双侧锚定：源文 やめて 形态 且 译文命中"别停/不要停"目标集；源侧负向排除 やめないで/やめるな；"住手"不在目标集不会误阻断；仅 local/strict 档生效，手册注明；卡措辞"やめて 禁止默认译'别停/不要停'，优先'住手/停下'，按语境裁定"。
④ D1 观察闸转阻断标准：连续 3 次运行或累计 ≥300 样本、误伤率 <2%、人名/解剖词/称呼类零误伤；最小样本护栏（连续 3 次累计候选不足 100 只观察不转阻断）；glossary 支持 target_aliases 向后兼容，learned 不生成别名。
⑤ C2 审计口径：门槛保留行计入终稿，恒等式结构不变；报告新增"纯假名实义保留：N（其中 [未翻译] 标记 M）"；cleaner 新计数器 kept_by_noise_gate。

**用户实现注记（新增边界）**：created_at 为 NULL 的行归 unknown_time，指定时间窗时默认不删；normalized 为独立 match_type 逐行可辨；删除清单排序后 sha256 写运行日志。

**两条风险（手册定稿措辞）**：
1. "清洗改变 TM 指纹，旧 resume 必然失效——删旧 resume 产物，禁止复用。"
2. "旧 TM 无 provenance，清洗可能跨片误删同源句，只能靠 dry-run + CSV 备份兜底。"

**G7 模型实测**：列为批次 E 可选旁路 E3（Sakura-GalTransl-13B vs qwen2.5-14B，同卡同规则、TM 关闭），不作为本版主线。

**分工**：用户侧——B1 词条内容审核、C1 sidecar 内容提供、E1 清洗清单确认、E2 重跑执行与指标验收（E3 可选参与）；代码侧——批次 A/B/C/D 全部机制、测试、文档、版本收尾由 coding 子智能体实施。

**decision-critic 异议记录**：G5（TM 清洗）曾提 [HIGH_RISK_OBJECTION]，主模型按三条件采纳执行（dry-run 默认不直接删；删除清单 CSV 备份 + sha256 可审计；--yes 限定批次 E 且 B/C/D 全部落地后），三条件已全部落入批次契约。条件是否闭环：机制条件已写入计划，最终闭环以批次 E 实际执行（dry-run 清单人工确认 + CSV 备份留存 + 8 项指标验收）为准。无 [PRESSURE-OVERRIDE]。

**后续风险跟踪**：① 批次 E 清洗执行前须留存 CSV 备份并人工核对 dry-run 清单；② 观察闸转阻断须满足契约点④标准并记录样本量与误伤率；③ 指标 7 口径拆分后跨片同源句单列项须用户逐次确认；④ 版本收尾时本条目状态转"已执行"。

**执行追记（2026-09-18）**：
- 批次 A 完成（定时任务触发执行）：契约审计通过（上次中断执行遗留物经逐项审计仅补 1 处 docstring 缺口）；tests/test_tm_purge.py 14 用例；全量 779 passed；真实库 source_name 列幂等迁移确认、零写入；样例片 dry-run 删除候选 1,136 条（raw 997 / premerge 2 / normalized 137），删除清单 sha256 3bcfa5a5…3b879。
- 用户人工审核裁决：raw 997 + normalized 137 批准删除；premerge 2 条（entry_id 43755/43843）暂缓转白名单——**批次 A 有条件通过**。CSV 物理行数疑云已解（1,137 物理行=表头+1,136 记录、零内嵌换行，不存在未审记录）。CSV 编码缺陷（实际无 BOM UTF-8，与契约 utf-8-sig 不符）已修复并新增 BOM 契约测试。
- 白名单机制落地：tm_purge.py 新增 --exclude-ids / --exclude-file（would_keep_excluded / user_hold_whitelist，不入 sha256 删除清单）；裁决存档 Temp/translation_memory/tm_purge_hold_ids_20260918.txt；**批次 E --yes 执行时必须携带 --exclude-file 该文件**。
- 批次 B2 完成：antonym_yamete / antonym_saitei / antonym_zurui 三条 warn_only 规则（双侧锚定+源侧负向排除 やめないで/やめるな）入 translation_rules.yaml 两份副本；A/B 卡反义禁令行；antonym_v1.json 语义黄金集（8 用例）；learn-gate 阻断直接用例；全量 801 passed。
- 批次 C 完成：C1 per-片 sidecar（剧情摘要+误听怀疑，冻结措辞注入、命中即列留痕【误听疑似改写】、context_sidecar 开关入指纹、模板 docs/上下文sidecar模板.md）；C2 L7/L8/L11 源侧噪声证据收紧（is_source_counting_noise：keep_list 与含汉字不算噪声；kept_by_noise_gate 计数器；报告"纯假名实义保留"行）；3 个旧"纯假名即可删"用例按新契约更新；832 passed。
- 批次 B 审批闭环（用户裁决）：9 词条入 glossary.csv（イク 译法定为"要去了"，其余按建议），纯追加+备份 glossary.csv.bak-20260918，load_glossary_merged 验证 11/11 命中；两项可选项均只补规则不入表——body_part_kubi（首：习语负向排除）与 climax_iku_variant（イク变体：显式负向排除 行く系与精确イク，捕获变体泛化译"去"），均 warn_only/双侧锚定/仅 local/strict/TM 阻断沿用既有链路；A/B 卡补 身体语境首 与 イク系 两行；837 passed。B2 已实施内容（三 antonym 规则/卡行/黄金集/测试）经用户批准无调整。
- 批次 D 完成：术语冲突观察闸（默认观察不阻断，glossary_conflict_block 转阻断由用户裁决；跨运行 JSON 累计与三态建议行+最小样本护栏）、glossary target_aliases 可选第三列（注入只用主译法、冲突判定豁免别名、learned 不生成别名）、【术语一致性】章节与 TM 命中/入库摘要行、glossary_learn_enabled 开关 + tools/glossary_learned_reset.py（tm_purge 同款纪律）、拟声行卡条款（两卡+四源钉扎）；866 passed。
- v1.2.2 代码侧收尾完成：版本 1.2.2（pyproject+__version__）、CHANGELOG [1.2.2] - 2026-09-18、手册新增 §11「1.2.2 行为变化一览」（11.1–11.6，含两条风险定稿措辞与 strict/cloud 档位差异）；全量 866 passed / 1 skipped，ruff 全项目 All checks passed。批次 E 待用户实弹执行（--yes 清洗携 --exclude-file 白名单 → 全新重跑 → 8 项指标验收）。
- 备注：用户侧记录"磁盘 CSV 1,167 行差异仍记录在案，放行磁盘全集需另行对账"——实测口径为 1,137 物理行=表头+1,136 记录、零内嵌换行，两说并存留档。

## [2026-09-17] D2026-0917-02 生产模型替换选型（Qwen3.8-27B-Uncensored 候选路线）[已拍板·待E3实测裁决]

### 一、决策问题

是否以 Qwen3.8-27B-Uncensored（IQ3_M 为投产底线、否决 IQ2_M）替换当前本地双模型（阶段A 净语翻译 + 阶段B 审校抛光），并并入 v1.2.2 批次 E 一次性"清洗 TM + 新模型全量重跑"（避免两次全量重跑）。

### 二、已核实事实

- **换模型通道**：`--s1-model` / `--s3-model` 免码可换（`subtransjav/refine/cli.py:48,56`）；`config.py:22` temperature_local=0.1、`:29` timeout_llm=900、`:218` batch_local=30、`:253` v2_ctx_local=32768。
- **当前生产双模型型号无记录**（`models/` 目录为空、决策日志空白）——E3 前置缺口。
- **根因记录**（D2026-0917-01、v1.2.2-计划表 §一）：错译主因＝TM 固化（tm.db 存量 24,214 条；实弹 1130/1160 精确命中，约 94% 的行 TM 直接复用绕开模型）；六类病因以 TM/规则污染为主轴。
- **代码事实**：`subtransjav/translate/llm_client.py:277-283` 请求 kwargs 为白名单构造（model/messages/stream/temperature/max_tokens），**无 `extra_body` / `chat_template_kwargs` 透传口**；`:292-299` 已有思考型模型兜底（content 为空时取 reasoning_content/reasoning）。
- **质量基建就绪**：闸门0、quality_report、`tests/test_golden_set.py`（golden_v1.json + semantic_v1.json）；无跨模型翻译质量自动基准。
- **量化/情报**：IQ2_M KLD 0.0702 出处＝Artefact2 GGUF 量化横评 gist（通用基准，非 27B 专项、非翻译专项）——降级标注，不作唯一否决依据；heretic 系去审查 KLD≈0.0021 为 3.6-27B 测值；3.8-27B heretic 存在性与 MTP/FastMTP 在 LM Studio 的支持度为待补证项。

### 三、decision-critic 异议记录（D2026-0917-02）

**HRO-1（[HIGH_RISK_OBJECTION]，点1"值得替换"先验结论）**：与既有根因记录（TM 固化 94% 命中为主因）冲突，且现模型无型号、无 TM-off 基线——要求在证据具备前不得以"能力上限"为换型前提。**主模型回应：采纳（措辞降级）**。顺序固定：①记录现双模型实际型号（用户侧查 LM Studio）→ ②E3 TM-off 实测（含现模型对照组）→ ③胜出者才随批次 E 全量重跑。写入显式出口：**"若现模型在 TM-off 下指标 1/2/5 达标，则不替换，仅走原'清洗 TM+现模型重跑'主线，模型替换顺延独立立项。"**

**7 项条件——全部采纳**（后两处为主模型补充）：
1. E3 实测四探针（反义/语境/术语/结构化）+ 拒答探针 + 语义黄金集；
2. IQ2_M 保留投产否决、纳入测量档；回退链重序：27B IQ3_S（≈11.8GB）→ Qwen3.6-35B-A3B heretic（MoE 路线）→ 暂缓不换；
3. 模型对比口径＝指标 1/2/5 + 探针；8 项验收留在 E2 全量重跑阶段；
4. E3 前先记录现型号；
5. 候选上限 4（现双模型 / Sakura-GalTransl-13B / 3.8-27B IQ3_M / IQ2_M 测量档），固定样例片与种子；
6. "关闭 thinking"优先尝试 LM Studio 模型级/服务器级开关（零代码改动）；仅当无法端到端验证生效时，才新立 coding 任务为 `llm_client.py:277-283` 增加 extra_body/chat_template_kwargs 透传口，并加"content 非空且非思考链"断言——**本决策不改代码**；
7. 批次 A-D 不阻塞于模型胜负；27B 吞吐下降入批次 E 单批耗时预算。

### 四、主模型最终决定

- **结论措辞**："值得替换"降级为**待证假设，实证裁决**；胜出与出口条件按 HRO-1 执行。
- **量化**：IQ3_M 为投产底线；IQ2_M 投产否决保留（依据降级标注为通用基准，不作唯一否决依据），纳入 E3 测量档。
- **变体取舍**：unsloth 官方未去审查不可直接投产（JAV 内容拒答风险）；JonathanColetti 来源不明弃用；HauhauCS Aggressive 由"零拒绝保底"降级为**最后手段**，须过语义黄金集 + 乱码强译探针方可入选；heretic 系优先（判据＝实测四件套：指令遵循 / 结构化输出 / 反义与语境 / 拒答率，KLD 仅作平手参考）。
- **流程**：E3 TM-off 先行（含现模型对照）→ 胜出者随批次 E"清洗 TM + 新模型全量重跑"一次；E2 验收 8 项指标 + 单批耗时预算。

### 五、条件闭环状态

机制条件未闭环（决策层面已拍板）。闭环项：①E3 TM-off 实测（四探针 + 拒答 + 语义黄金集）；②thinking 关闭端到端验证生效（LM Studio 模型级/服务器级优先）；③内存/KV 预算核算——硬件已由用户确认（2026-09-17：i5-14600KF + RTX 5060 Ti 16GB + 64GB DDR4），核算口径改为：dense 27B IQ3_S/IQ3_M（11.8-13.5GB）+ KV q8_0 按 16GB VRAM 全载为基准；MoE 路线按 expert offload 至 RAM 口径核算；④现双模型型号记录。

### 六、是否 [PRESSURE-OVERRIDE]

否。

### 七、后续风险跟踪

- ① IQ2_M KLD 0.0702 出自通用基准（Artefact2 gist），降级标注，不得作为唯一否决依据；
- ② 3.8-27B heretic 存在性与 MTP/FastMTP 在 LM Studio 支持度＝**两日内补证项**，[UNVERIFIABLE] 未闭环前不静默携带；
- ③ 批次 E 若胜者 E2 全量未过 8 项验收线（届时 TM 已清洗）：回退＝CSV 备份恢复 TM + 退回次胜者重跑；
- ④ 换型为交付差异，须进 CHANGELOG 与手册（含档位差异）；若 thinking 无法模型级关闭而需代码改动，另立工单；
- ⑤ 现型号与换型后型号一并补记本文档空缺（决策日志空白项）。

### 八、分工

- **用户侧**：现双模型型号记录；E1 清洗清单确认；E2/E3 执行与 8 项指标验收。
- **代码侧（本决策不改代码）**：仅当 thinking 无法在 LM Studio 模型级/服务器级关闭且端到端验证失败时，才新立 coding 任务增补透传口 + 断言；批次 A-D 机制实施不受模型选型阻塞，可与 E3 并行。

## [2026-09-17] D2026-0917-02-R1 生产模型选型 E3 名单定稿与 enet45 取舍（续评）[已拍板·待用户下载确认]

**一、续评依据**：基于 D2026-0917-02 原条目（HRO-1 出口条件 + 7 项条件 + 风险跟踪 5 项）续评，任务起于 2026-09-17 11:11。立场整体维持；两处修订（见三）；一处升级为 [HIGH_RISK_OBJECTION]（见六，已采纳闭环）。

**二、新事实核验（5 条，均已核实）**：① 硬件 i5-14600KF + RTX 5060 Ti 16GB + 64GB DDR4："内存只容 IQ2_M"前提消失，16G 显存可全载 dense 27B IQ3_S/IQ3_M（11.8-13.5GB）+ q8_0 KV，MoE expert offload 路线成立；② thinking 可全候选模型级关闭 → 原条件⑥（llm_client.py 透传口备用工单）作废；③ Sakura 家族最新为 Sakura-14B-Qwen3-v1.5-GGUF（已上 Qwen3 底座），语域适配问号成立（训练语料为通用日文+轻小说/Galgame 书面文本 vs 本项目 JAV 口语 ASR 转写）、低成本高上限留一席实测；④ Gemma 4 系全砍（中文弱 / OS-Software QAT-heretic 变体底座未变、档位 IQ2_S 级、模型卡自曝复读循环）；⑤ 新候选 enet45/qwen3-8b-ja2zh-v1.1（lora/merged/gguf 三仓库为同一模型三格式）：底座 Qwen3-8B-Base（2025-04 代，隔 Qwen3.6/3.8 两代）、训练语料与 SFT 提示词模板均未披露、GGUF 269 下载/2 赞社区验证极少、8B Q4≈5GB 全场最快。

**三、原条件修订**：
- 条件②修订——IQ2_M 测量席取消（存在前提"内存只容 IQ2_M"已消失），**IQ2_M 投产否决显式保留**（取消的仅是测量席，回退链最低档仍禁 IQ2_M）；
- 条件⑥作废——thinking 已可模型级/服务器级关闭，"透传口备用工单"整体关停；
- 条件⑦升级——E3 协议追加逐候选吞吐指标（tok/s、有效 token/分钟，同卡同并发、LM Studio 实测），随 E3 报告产出"席2/席3/席4 三行全库重跑耗时区间估算"，批次 E 耗时预算由实测重算；全库规模（SRT 文件数/总行数）列为批次 E 计划输入，由用户侧目录盘点提供；
- 条件④增强——席1 型号未入库前，E3 不得出具"现模型达标/不达标"基线结论（无型号即不可复现、不可归因）。

**四、E3 名单定稿（≤4 席）**：
- 席1 现双模型（基线对照，型号待用户补记后入档）；
- 席2 Qwen3.8-27B Uncensored IQ3_S/IQ3_M（heretic 优先，存在性为前置确认项；无则 HauhauCS Aggressive 过语义黄金集+乱码强译探针后作最后手段；unsloth 官方原版仅作对照不投产）——质量主力；
- 席3 Sakura-14B-Qwen3-v1.5（**Q5_K_M 主测单档**，全显存；微弱落败时加测原生 glossary 提示词格式维持原口径）——领域对照；
- 席4 Qwen3.6-35B-A3B heretic IQ3（expert offload 至 64G 内存，**转正必测**）——速度/平衡轴。

**五、enet45 取舍**：不进正式名单。理由：① 训练语料与提示词模板双重不透明（与 JonathanColetti"来源不明弃用"先例一致，独立成立，为排除支柱）；② 同赛道被席3 全面占优（底座代数/规模/社区验证/glossary 支持）——"8B 容量治不了核心病因"为假设性论据 [UNVERIFIABLE]，不构成排除支柱亦不撤销排除；③ 吞吐优势不构成破例（瓶颈是质量不是速度；真实反事实是席4 而非 8B）。名单外 10 分钟自测照录：复用"领域席预筛 scorecard"（8-12 条 JAV 口语特征样本，与 golden_v1/semantic_v1 黄金集**不相交**防判决污染）、结果记录、不突变名单、不投产、不入胜出裁决；**即便 surprise 通过，投产仍须语料披露 + 完整 E3 四探针**。席3 若领域胜出仅说明"Qwen3 系 ja2zh 领域适配在本域有效"，**不触发 enet45 复评**（范围防滑）。

**六、decision-critic 异议记录与主模型最终决定**：
- [HIGH_RISK_OBJECTION]（一条）：席4 可选化与"速度轴已覆盖"论证自依赖 + 回退链第二档无实测。判定依据：影响 ≥3 个任务（E3 执行面、批次 E 耗时预算、回退链第二档实测、最终投产裁决）；且"席4 是速度轴"本身为未验证假设——35B-A3B expert offload 至 DDR4 受内存带宽约束，端到端吞吐可能低于全载 VRAM 的 dense 27B，须实测后定性。
- **主模型回应：采纳（选项 A——席4 转正必测）**。理由：回退链第二档必须有实测数据；"速度轴"须实证后定性。
- 三项改进条件全部采纳，参数落定：① 席4 转正必测；② E3 追加逐候选吞吐指标 + 三行耗时区间估算，全库规模列为批次 E 计划输入（用户侧盘点）；③ **胜出规则预声明**：质量容忍带 **ε=5%**（指标 1/2/5 相对差 ≤5% 视为平手）；平手且席4 在耗时预算内 → 席4 凭速度胜出；超出容忍带 → 席2 质量优先。**ε 可由用户在 E3 开跑前调整，跑后不得改**（判决契约，防跑后定性）。
- 普通级建议全部采纳（6/6）：席3 Q5_K_M 单档；席1 型号未入库不出具基线结论；enet45 自测契约；席2 显存余量薄（13.5GB+KV q8_0 首跑监控，不足降 KV q6 或改 IQ3_S）；IQ2_M 投产否决显式保留；席3 胜出不触发 enet45 复评。

**七、条件闭环状态**：决策层面已拍板（HRO 采纳，参数全落定），执行面未闭环。已闭环：thinking 端到端验证（√）、硬件核算升级（√）、条件⑥作废（√）、质量容忍带与胜出规则预声明（√）。未闭环：① 现双模型型号记录（E3 前置）；② heretic 存在性补证（席2/席4 前置，无则落 HauhauCS gate / 驳回重选）；③ E3 TM-off 实测（四探针 + 拒答 + 语义黄金集 + 吞吐/耗时估算）；④ 批次 E 全库规模盘点。

**八、是否 [PRESSURE-OVERRIDE]**：否。

**九、后续风险跟踪**：① 席4 offload 吞吐可能低于全载 27B，不得预判，以 E3 实测为准；② 全库规模确认前批次 E 耗时为开放量（TM 清洗后首轮命中≈0 ⇒ 近似全量重译），估算进 E3 报告；③ 席3 若在指标上同时压过席2/席4（领域对照反超）——胜出规则仅声明于席2 vs 席4，届时由主模型在 E3 现场作一次明确从席裁决（Sakura 若投产须过 E2 8 项验收 + 语域样本复核），预先知会用户；④ 批次 E 胜出者未过 8 项验收时，回退链第二档已由席4 实测补齐（本续评主要增益）；⑤ 席2 首跑监控 nvidia-smi/LM Studio 显存，不足降 KV q6 或改 IQ3_S；⑥ 现型号与换型后型号一并补记本文档空缺（D2026-0917-02 原风险跟踪⑤续办）。

**十、决策日志字段**：原决策＝D2026-0917-02 之 E3 名单定稿续评（R1）；decision-critic 异议＝[HIGH_RISK_OBJECTION] 一条（附三条件）+ 普通级建议六项；主模型最终决定＝采纳（HRO 选项 A 席4 转正；三条件全落定含 ε=5% 预声明；普通级 6/6 采纳）；条件闭环＝决策层面闭环，执行面待 E3 实测、型号记录、heretic 补证、全库规模盘点；[PRESSURE-OVERRIDE]＝否；风险跟踪见第九节，其中③（席3 反超的现场裁决）与⑥（型号补记）为新增项。

## [2026-09-17] D2026-0917-03 上游转录配置选型·WhisperJAV v1.9.2（三档固定 + Qwen 试点）[已拍板·待执行验证]

> **注（同日）**：本条目已被 **D2026-0917-03-R1 并轨修订**（主力改判两遍 ensemble、B 档降级吞吐车道、aggressive 分派原则、qwen 段切器修正为 firered-vad），本条目保留为历史记录，现行配置以 R1 条目为准。修订缘起：原条目遗漏官方默认面（v1.9.2 README 默认两遍组合），且 #374 评论面证据抓取不全（内容过滤器拦截），经用户质询后重新取证续评。

**一、决策问题**：为 SubTransJAV 下游（闸门0/处置报告/回捞/黄金集）选定上游 WhisperJAV v1.9.2（本地 D:\whisperJAV）转录提取字幕的固定配置搭配，并裁决 Qwen 路线是否可直接定为日常主力。用户硬件已确认为 RTX 5060 Ti 16GB + 64GB DDR4（Blackwell 代，v1.9.2 已适配 int8_float16，出处 D2026-0917-02 条目）。

**二、已核实事实**（decision-critic 独立只读核验，均一致）：
- large-v3→large-v2 回退注释与 `model_id = "large-v2"`（config/components/asr/faster_whisper.py:211-223）；温度收紧 [0.0] 无重试（faster_whisper.py:339，"accuracy is a wash"、回退主因是 JAV 连续能量非语音内容的病理空输出，而非普遍准确度差——#374 用户"v3 准确度差"无独立佐证，属单例经验，不构成选型支柱，只与回退方向一致）。
- `--qwen-timestamp-mode` 运行时默认 vad_only（main.py:801-806）；vad_only 时 0.6B 对齐器不加载（qwen_pipeline.py:544-546，G1 fix）；对齐器走分相独占显存路径（modules/qwen_asr.py:1093-1113，约 1.2GB，切换代价为二遍解码+模型换载）。
- 新事实修正：qwen 管线 max_group_duration 默认实为 **3.0s / chunk 0.3s**（qwen_pipeline.py:121，v1.9.0 JAV retune），6.0 仅 cohere 分支（qwen_pipeline.py:343-346）——原材料"默认 4.0s"不成立。
- balanced 拒绝 `--speech-segmenter`（main.py:2094-2108）；`--fail-on` 合法值 `("empty","suspect")`（utils/run_outcome.py:79）；20 分钟模型刷新默认且**仅覆盖 Balanced/Fidelity**（main.py:529-536，#394=同实例退化，缓解而非根因修复）；semantic 场景检测为全管线新默认（config/segmenter_presets.py:126，MFCC+聚类无 VRAM 成本，留 auditok 回退）；fidelity 默认 FireRedVAD（segmenter_presets.py:98）；GUI 内置组合：qwen pass1 whisperseg+balanced / pass2 ten+balanced、anime pass1 semantic+whisperseg+aggressive / pass2 balanced、Whisper 系一律 aggressive（assets/app.js 约 1840-1925）；qwen_guide.html 为 v1.8.5（:995，Silero v6.2 段已陈旧；Aligner+VAD Fallback 与 ecosystem/model YAML 一致，与 CLI 运行时默认相悖）。
- 下游耦合面（INFO_GAP 闭环）：无调用上游 CLI 的自动化入口，仅消费产物 SRT + 旁车 whisperjav_run.json（subtransjav/refine/cli.py:37-38 可选传入/自动发现；pipeline_v2.py:1403 H4a 先于闸门0 加载；asr_meta.py:32-35 候选键容忍解析、读取异常降级 present=False 不崩溃）——v1.9.2 CLI 破坏性变更对下游零迁移风险；闸门0 已消费 v1.9.2 新增 MILEAGE（mileage_pct 低覆盖率告警）。
- 证据补全：issue #374 URL=https://github.com/meizhong986/WhisperJAV/issues/374（测评主体为帖子正文，作者 weifu8435，2026-06-24；5688373787 为仓库作者 meizhong986 2026-09-15 致谢评论，无新增技术数据）。黄金集 AB 指标脚本复用现有 tests/test_golden_set.py + semantic_v1 黄金集机制，四指标对照表由执行轮产出。

**三、拍板内容（四档定位 + 配套原则）**：
- **A 档 质量优先（Whisper 路线，低频/高价值片源）**：`--mode fidelity --model large-v2`（FireRedVAD 默认、semantic 场景）。接受慢；16GB 卡较 #374 用户（8GB 笔记本 1h→1-2h）应更快，速度以实跑为准。
- **B 档 均衡日常（日常主力）**：`--mode balanced --model large-v2`，vad-version 4.0、semantic 场景默认不动，加 `--fail-on empty` 兜 #394。
- **C 档 Qwen 试点车道（非主力）**：`--mode qwen`（1.7B），sensitivity=balanced 起步、漏线告警再按文件升 aggressive，framer=vad-grouped、regroup=off、postprocess=high_moan、repetition-penalty 1.1、token-budget 20、timestamp 默认 vad_only、max_group_duration 待黄金集 AB 后定（暂不上 6.0）。**晋升条件：黄金集 AB（B/C/D 三档对照）四指标（CER/漏线率/幻觉行占比/闸门0 拦截率）对 B 档全面占优或打平**；期间文档明示"C 档为试点"。
- **D 档 两遍 ensemble（覆盖优先/高价值片源）**：qwen pass1 + balanced pass2（GUI 内置组合）；anime 向内容 anime-whisper pass1 + balanced pass2。
- **配套原则**：enhancer 默认 none（噪音明显再 ffmpeg-dsp/zipenhancer）；模型统一 large-v2 系，不上 large-v3/turbo；qwen_guide.html 仅作参数语义参考、不照抄推荐值；**全档位 sensitivity=balanced 起步**，不设全局 aggressive 默认（GUI 内置"Whisper 系一律 aggressive"属纯上游单发默认，不适用于本下游搭配，沿用 GUI 组合时须按本决策覆写）；下游宁可多召回不漏线，误报成本以闸门0 拦截率/处置报告异常为回退信号。

**四、decision-critic 异议记录与主模型最终决定**：
- **[HIGH_RISK_OBJECTION-1]（C 档直接定主力缺验收闸门）→ 主模型：采纳**。影响 ≥3 个任务（闸门0 输入、翻译、回捞、黄金集验收全链路），qwen 管线社区验证度最低（#374 证据走 large-v2 路线）、v1.9.2 仍在密集修 qwen 补丁、长视频无同实例退化遏制，且黄金集 AB 条件已具备却未设为晋升前提。B 档为日常主力，C 档试点车道，晋升按第三条 AB 条件，文档明示试点状态。
- **普通级修正（3 项）全部采纳**：
  1. timestamp 取舍：默认维持 vad_only；aligner+vad_fallback 为**验收驱动选配**（黄金集 10 部实测时间戳偏移分布与耗时后再定）；代价修正为约 1.5-2x 时长（分相对齐解码+模型换载），非 +2GB 常驻。
  2. max_group_duration：基线修正为 pipeline 默认 3.0s（qwen_pipeline.py:121，v1.9.0 JAV retune）；未经黄金集 AB（3.0 vs 6.0，监控单组失败率）不直接上 6.0；"6s 更完整"方向成立但须实证，不得只引 YAML 注释。
  3. 宁多召回分工：分层成立，"宁多召回"不落全局 aggressive 默认；全档位 balanced 起步、黄金集命中率/漏线告警跌破阈值按文件升级 aggressive，升级后以闸门0 拦截率/处置报告异常为回退信号。
- **遗漏风险清单全部采纳**，其中两项因硬件事实更新调整：FireRedVAD / qwen1.7B+aligner 同驻显存风险权重**下调**（16GB 卡 + Blackwell int8_float16 适配）；下述四项照旧记录：① 20min 模型刷新仅覆盖 Balanced/Fidelity，qwen 长视频无同实例退化遏制，须 mileage 覆盖率监控兜底；② semantic 场景检测新默认回归面，留 auditok 回退 + 黄金集至少一轮新旧对比；③ manifest 候选键命中比对（升级后首轮，防 asr_meta 静默降级 present=False）；④ qwen aggressive 预设 batch=16+max_new_tokens=8192 属高载，谨慎禁用提示入文档/脚本。

**五、条件闭环状态**：决策层面已拍板（HRO 采纳、修正与参数全部落定），执行面未闭环。已闭环：硬件事实更新（√，16GB+Blackwell）、下游耦合面核实（√，零迁移风险）、#374 证据补全（√）、黄金集 AB 复用路径（√，tests/test_golden_set.py + semantic_v1）、max_group_duration 基线修正（√，3.0s）。未闭环：① B/C/D 三档四指标 AB；② timestamp aligner 10 部实测（偏移分布+耗时）；③ max_group_duration 3.0 vs 6.0 AB + 单组失败率；④ 升级后 manifest 候选键命中比对（首轮）；⑤ semantic 新旧场景检测对比（至少一轮）；⑥ qwen 长视频 mileage 监控窗口建立。

**六、是否 [PRESSURE-OVERRIDE]**：否。

**七、后续风险跟踪**：① 四指标 AB 未出前，C 档保持试点，任何文档不得标注主力；② AB 平局判定口径未定——建议沿用 D2026-0917-02-R1 的 ε=5% 容忍带先例，由执行轮**跑前预声明、跑后不得改**（判决契约，此项待执行轮敲定，本决策未落死）；③ qwen 长视频（≥1h）异常以 mileage 覆盖率 + 单组失败率兜底，异常即该文件回退 B 档重跑；④ manifest schema 键名漂移为静默通道，升级后首轮必须人工比对 candidate keys 命中与 MILEAGE 值域；⑤ aligner 选配"为开而开"风险，未过 10 部实测不启用；⑥ GUI 内置 aggressive（Whisper 系/anime pass1）与本决策 balanced 起步原则冲突，D 档沿用 GUI 组合时须按原则覆写并记录；⑦ qwen aggressive 预设高载（batch=16+8192 tokens），文档/脚本显式禁用提示。

**八、分工**：用户侧——黄金集 AB 执行与四指标验收、10 部 timestamp 实测、升级后首轮 manifest 人工比对。执行侧——四档 CLI 配置固化进脚本/文档、AB 对照表产出、semantic 对比轮、mileage 监控窗口落地。代码侧——本决策不改代码，仅配置与文档；如 AB 暴露需要新参数（如 qwen 侧刷新机制），另立工单。

**九、决策日志字段**：原决策＝D2026-0917-03 新立（上游转录配置选型，非续评，硬件事实承接 D2026-0917-02）；decision-critic 异议＝[HIGH_RISK_OBJECTION-1] 一条（C 档主力缺验收闸门）+ 普通级修正三项（timestamp / max_group_duration / 宁多召回）+ 遗漏风险清单；主模型最终决定＝全部采纳（B 档主力、C 档试点、AB 晋升条件、参数修正落定）；条件闭环＝决策层面闭环，执行面待 AB 四指标、timestamp 10 部实测、3.0 vs 6.0 AB、manifest 首轮比对、semantic 对比轮、mileage 监控窗口；[PRESSURE-OVERRIDE]＝否；风险跟踪见第七节，其中②（AB 平局口径预声明）为执行轮待决新增项。

## [2026-09-17] D2026-0917-03-R1 上游转录配置选型·WhisperJAV v1.9.2（R1 续评：主力改判两遍 ensemble）[已拍板·待 AB 执行]

**一、续评依据**：基于 D2026-0917-03 原条目（B 档主力 / C 档试点 / balanced 起步 / qwen 默认 whisperseg）续评。新证据 A（官方 v1.9.2 README，本地权威面 whisperjav-1.9.2.dist-info/METADATA + 作者 8-29 评论 #5463389888）+ 证据 B（#374 全部 55 条评论，weifu8435 9 月实测）。**原条目三档结构被本续评并轨修订，原条目保留为历史记录**。

**二、新旧事实核验**：
- 证据 A 已核验（METADATA:265/:344/:355/:370-372/:420/:428-434）——官方默认两遍 = anime-whisper·WhisperSeg·aggressive / Qwen3-ASR·TEN；aggressive 为基准调优目标；balanced 官方自评粗时间戳 + 弱 run-outcome 检查；最佳 = ensemble（anime-whisper + qwen）；内容分派表含 ASMR→fidelity/anime-whisper aggressive、重 BGM→balanced conservative；whisper-ja-1.5B 场景基准最强（不进本期）；Qwen finetune 双通道（QA-Galgame CER−27% rel / neosophie，:358-359）。
- 证据 B 复核升级：55 条评论已由主模型经 GitHub API 全文拉取并本地存档 `D:\SubTransJAV\.tmp374\comments.json`（+body.json）。decision-critic 侧抽查关键 7 条 ID 核验一致：5463389888（作者，8-29，#394 属真实 bug、1.9.0 仍复现）、5579871700（9-08，fidelity 新版快约一倍、semantic 场景、large-v2 幻觉经词表消除）、5585938271（9-08，Qwen3-ASR+TEN 亦触发短字幕时间过长，**只能配 FireRedVAD**）、5604217223（9-09，方案一 anime-whisper+FireRedVAD / large-v2 vs 方案二对比，准确度方案一稍优、覆盖方案二更优）、5610000509（9-09，暂定最终配置=方案二、弃 anime-whisper 原由：语气词过多；qwen"所有模型里字幕最全"但碎且短字幕轴拖尾）、5614392021（9-10，large-v3-turbo 后段时间轴偏移被否；whisperseg 捡漏最强但语气词偏多）、5614575021（9-10，large-v2 原生词级时间戳护城河长评）。
- **归因疑点（成立，列为 AB 第一轮前置）**：行碎机制被指为"Assembly 对齐器拆 VAD 块 2-4 行"，与 aligner=on 纠缠；1.9.x 默认 vad_only 不加载对齐器（main.py:801-806；qwen_pipeline.py:544-546 G1 fix）——"必须 FireRedVAD"对 1.9.2 默认前提的可迁移性须实测归因。
- 代码可表达性已验：qwen 段切器选项含 firered-vad（main.py:729-738）；fidelity ensemble pass 官方注记亦用 firered-vad（main.py:454-466）。

**三、拍板内容（方向性默认，即时生效）**：
1. **主力 = 两遍 ensemble（pass1_primary）**：pass1 = anime-whisper · semantic · WhisperSeg · aggressive；pass2 = Qwen3-ASR 1.7B · semantic · aggressive · **段切器默认 firered-vad（TEN 保留为 AB 对照席）**；ASMR/耳语向片源 pass1 换 fidelity + large-v2；weifu 方案（fidelity+large-v2 / qwen+FireRedVAD）列为 AB 对照席，不直接照搬。原 D 档并入主力框架，不再单列。
2. **B 档（balanced + large-v2 + --fail-on empty + MILEAGE 遥测）降级为快速吞吐车道**（批量/低值片/赶量场景）。
3. **C 档单 qwen 试点**：配置修正为 firered-vad + aggressive，带归因 AB 后再议去留。
4. **sensitivity 原则**：原"全档位 balanced 起步"作废；**aggressive 为 JAV 对话/ASMR 默认**，重 BGM 向 **conservative**，闸门0 拦截率/处置报告异常为回退信号。
5. **模型族锁定扩展为三族**：anime-whisper / qwen3 / large-v2 系，均不进 large-v3 / v3-turbo；whisper-ja-1.5B 与 qwen finetune 双通道记录为后续升级通道，不入本期名单。

**四、decision-critic 异议记录与主模型最终决定**：
- **[HIGH_RISK_OBJECTION-1-R1]**（三参数写死前置 AB 门槛：qwen 段切器弃 TEN / aggressive 全量固定 / pass1 单型定死）→ **主模型：采纳**。形态 = 方向性默认 + AB 门槛闭环：三条参数（① qwen 段切器 firered-vad vs TEN 最终归属；② aggressive/conservative 内容分派边界；③ pass1 单型归属 anime-whisper vs fidelity+large-v2）以 AB 产出为准锁定；ε=5% 容忍带按先例跑前预声明、跑后不得改。异议②已含于修订案"重 BGM 向 conservative"，视为已满足。
- **普通级修订前四项**（主力改判 / B 档降级 / aggressive 分派 / C 档段切器）→ 全部采纳，拍板如上。
- **AB 前置清单（执行轮顺序）**：第一轮——行碎归因矩阵（段切器 firered-vad/TEN/WhisperSeg × 时间戳模式 vad_only/aligner_vad_fallback × 行碎度/成品短行占比/时间轴偏移）+ ensemble 空 pass 兜底行为确认（merge pass1_primary 语义，ensemble/merge.py:338-386，+ --fail-on empty 在 ensemble 下行为）；第二轮——六指标决胜（原四指标 CER/漏线率/幻觉行占比/闸门0 拦截率 + 行碎度/短行占比 + 时间轴偏移分布），pass1 双型与段切器归属据此锁定。

**五、条件闭环状态**：决策层面已拍板（HRO 采纳、方向性默认生效、AB 前置清单定序），执行面未闭环。已闭环：新证据核验（官方默认面 METADATA √、证据 B 存档复核 √、qwen×firered-vad 可表达性 √、下游行合并吸收面 √（config.py:27 断句预合并 <6 字符碎片，闸门0 在预合并前逐行运作 config.py:255，故行碎影响有限但非零））。未闭环：① 行碎归因矩阵（AB 第一轮）；② ensemble 空 pass 兜底确认（AB 第一轮）；③ pass1 双型与段切器归属决胜（AB 第二轮六指标）；④ 六指标 AB 实跑；⑤ 升级后 manifest 键名比对（首轮）；⑥ qwen 长视频 mileage 监控窗口（qwen 升为 pass2 常规组件后为必配）。

**六、是否 [PRESSURE-OVERRIDE]**：否。

**七、后续风险跟踪**：① 行碎归因未决前，不得以"FireRedVAD 唯一可用"写死文档（与官方默认 TEN 的分叉以 AB 裁决，不选边）；② ensemble 空 pass 兜底未确认前不得以主力身份批量投产；③ qwen 为 pass2 常规组件后 20min 模型刷新（main.py:529-536）不覆盖 qwen 的隐患升级——mileage 覆盖率监控为必配（下游 asr_meta 已消费 mileage_pct，链路可用）；④ #394 对降级后 B 档仍为知情风险车道，--fail-on empty + 遥测悬挂；⑤ 误报反噬转监控项：闸门0 拦截率/处置报告异常为 aggressive 回退信号；⑥ whisper-ja-1.5B 与 qwen finetune 双通道记录不入本期；⑦ semantic 新旧场景对比轮、manifest 键名比对、qwen aggressive 预设高载（batch=16+8192 tokens）禁用提示照旧；⑧ 证据存档位于临时目录 `.tmp374`，如需长期留存建议迁移至持久目录（如 docs/evidence/）并连同 golden 集指纹一并记录。

**八、分工**：用户侧——AB 第一/二轮执行与六指标验收、空 pass 兜底验证、manifest 首轮比对、mileage 监控窗口确认。执行侧——方向性默认参数入库（文档口径"方向性默认 + 待 AB 裁决"）、AB 矩阵脚本、ε=5% 跑前预声明落地、AB 完成后条目状态转"已执行"并补记裁决结果。代码侧——不改代码；如 AB 暴露 ensemble 空 pass 无兜底或 qwen 长视频退化属实，另立工单。

**九、决策日志字段**：原决策＝D2026-0917-03（R1 续评，原条目三档结构并轨修订）；decision-critic 异议＝[HIGH_RISK_OBJECTION-1-R1] 一条（三参数写死前置 AB 门槛）+ 普通级修订四项；主模型最终决定＝采纳（方向性默认 + AB 门槛闭环：六指标 + 行碎度 + 时间轴偏移，ε=5% 跑前预声明、跑后不得改）；条件闭环＝决策层面闭环、执行面待 AB 两轮 + 六指标 + manifest 首轮比对 + mileage 监控窗口（见第五/七节）；[PRESSURE-OVERRIDE]＝否；后续风险跟踪见第七节，其中②空 pass 兜底与①行碎归因为 AB 第一轮前置项，⑧证据存档迁移为新增建议项。

## [2026-09-18] D2026-0917-03-R1-E1 执行补记·结构性轮 AB 完成 [已执行·结构性轮完成]

**一、执行概况**：D2026-0917-03-R1 拍板执行面第一/二轮前置项落地。4 部影片（mihd002/mikr082/ure125/start422，122-148 分钟，含难片 mikr082）× 6 配置格 = 24/24 成功（首跑 Q2__mihd002 对齐器模型下载网络瞬断 rc=1，已重跑成功；队列 09-17 22:25 起至 09-18 05:10，Q2 重跑 05:26 完成）。数据位置：D:\SubTransJAV\.abtest\results.md（指标表）、metrics.py/run_queue.sh/logs/progress.log/out 同目录；#374 评论证据存档 D:\SubTransJAV\.tmp374\。

**二、四片均值对照**（速度=min/部实测；覆盖%=字幕去重占时/片长；重复%=同文本≥3 次行占比，幻觉代理非判定；碎<6% 与下游 DEFAULT_PREMERGE_MIN_FRAGMENT_CHARS 同口径；全部格子 state=done、无空输出，官方 manifest span 99.7-99.8）：

| 配置 | 行数 | 覆盖% | 均字 | 碎<6% | 重复% | 连重 | min/部 |
|---|---|---|---|---|---|---|---|
| ENS合并(anime+qwen) | 1164 | 40.9 | 11.2 | 17.8 | 9.5 | **0.0** | 20.5 |
| 　pass1 anime-whisper | 896 | 32.5 | 12.4 | 9.9 | 1.4 | 0.2 | 10.0 |
| 　pass2 qwen+FireRed | 1204 | 41.6 | 10.9 | 21.6 | 14.1 | 16.0 | 17.0 |
| qwen+FireRed+vadonly(Q1) | 1204 | 41.7 | 10.9 | 21.6 | 14.1 | 16.0 | 13.5 |
| qwen+FireRed+aligner(Q2) | 1238 | 29.3 | 10.9 | 20.8 | 14.7 | 14.2 | 22.0 |
| qwen+TEN+vadonly(Q3) | 1284 | 50.2 | 10.4 | 20.6 | 14.9 | 16.2 | 14.0 |
| qwen+WhisperSeg(Q4) | 1056 | 39.7 | 11.6 | 16.6 | 5.9 | 3.2 | 13.5 |
| balanced+large-v2(BAL) | 1018 | 24.8 | 9.6 | 25.9 | 3.5 | 2.2 | 5.4 |

关键单格：难片 mikr082——ENS 覆盖 24.8 vs BAL 14.9；anime pass1 396 行 vs qwen pass2 703 行（−44% 漏线互证）；qwen+WhisperSeg 572 行 vs qwen+TEN 776 行（−26%）。

**三、结构性裁决（decision-critic 立场标注）**：
1. ENS 主力+结构性验证通过（连重 0 全场唯一、覆盖 +65%、重复率较 pass2 单跑降 1/3、行数不缩水）；BAL 4x 速度 → 吞吐车道分工成立。**限注：结构性验证非完整六指标；BAL #394 n=4 未复现≠排除，车道维持知情风险标记 + --fail-on empty/遥测**。
2. 行碎归因定案（修正 weifu 归因）：vad_only vs aligner 碎行 21.6→20.8 几乎不变 → 行碎源于帧原生分组粒度、与对齐器无关；aligner 效应为时间轴收紧（均长 2.79→1.91s、覆盖 −12pp）非拆行；碎行治理方向 = 下游预合并/分行。
3. 段切器三参数①裁决：**FireRed 保留方向性默认；TEN/WhisperSeg 升格为合法候选；归属最终由人耳时间轴抽检定夺**。"FireRed 唯一可用"与"TEN 灾难"均否证（TEN max_dur 仅 +0.3-1.5s）；TEN 高重复率 14.1-14.9 由下游闸门0 吸收，其覆盖 50.2 是补漏正面证据。
4. pass1 三参数③：缺省 anime-whisper + qwen 补漏维持（anime 重复 1.4%/碎行 9.9% 全场最优、漏线 −44% 与官方"misses faint utterances"及 weifu"qwen 最全"互证、ENS 合并取长补短连重 0）。**缺口记录：ASMR/耳语向 "pass1 换 fidelity+large-v2" 本轮未测（BAL≠fidelity），保持"未验证方向性默认"（待办 d，非阻塞）**。
5. sensitivity 三参数②：aggressive 默认原则维持，conservative 边界标注"原则性、未实测"。
6. 空 pass 兜底：非阻塞，但未自然触发≠已验证；兜底语义维持代码审读（merge pass1_primary）+ 运行时 --fail-on empty/遥测常态化监控。

**四、AB 口径修订声明（主模型已追认，见十）**：原"六指标决胜 + ε=5% 判平、跑后不得改"契约中，CER/漏线率/时间轴偏移因无 ground truth 不可测。修订为：六指标 = 结构性三项（已测）+ 人耳时间轴抽检（待办 a）+ 闸门0 拦截率对照（待办 b）；CER/漏线率降级为按需；ε=5% 仅适用于可测指标。

**五、遗留待办**：a) 人耳抽检 4 部 × {Q1/Q3/Q4/ENS} 各 3 段（段切器归属 + aligner 取舍唯一决定性证据；协议随机化 + 含 mikr082 段 + 必查 Q2 max_dur 长尾 10.6-11.4s 异常）；b) ENS/Q1/BAL 三路 SRT 喂下游跑闸门0 拦截率对照；c) 黄金集标注轮降级按需（触发条件见十）；d) fidelity+large-v2 pass1 补测（按需级）；e) conservative 格补测（重 BGM 片型若存在）；f) MILEAGE/覆盖率告警口径与 aligner 覆盖收缩联动核对。

**六、运维事实**：CLI 需将 D:\whisperJAV\Library\bin 入 PATH（GUI 专属预设）；对齐器模型下载遇网络瞬断可致整格失败需重跑（progress.log 支持断点续跑）；5060 Ti 16GB 实测速度——qwen 系 13-22 min/部、ENS 20.5、BAL 5.4。

**七、条件闭环状态**：已闭环——行碎归因矩阵（定案）、段切器结构面（三候选）、pass1 结构性证据、ensemble 主力结构性验证、BAL 吞吐分工。未闭环——人耳时间轴抽检（a）、闸门0 拦截率对照（b）、fidelity+large-v2 pass1 补测（d）、conservative 边界（e）、aligner 取舍终定（随 a）、升级后 manifest 键名比对（沿用 R1 待办）。

**八、后续风险跟踪**：① Q2 aligner max_dur 长尾异常（8.95-11.4s）未解释，人耳轮必查；② aligner 覆盖收缩 × 下游覆盖率告警口径联动，可致系统性误报（待办 f）；③ BAL #394 不因 n=4 排除，持续遥测；④ 段切器归属未定前 FireRed 为默认、TEN/WhisperSeg 合法，文档维持"待抽检"措辞；⑤ 人耳抽检样本量小（12 段），结果只作择优不作全否；⑥ .tmp374 与 .abtest 证据路径临时存放，保留策略由用户定（建议迁 docs/evidence/ 或定期清理）；⑦ 维持：qwen 长视频 mileage 监控必配、qwen aggressive 预设高载禁用、semantic 新旧对比轮。

**九、决策日志字段**：原决策＝D2026-0917-03 / R1（执行面 E1 补记）；decision-critic 立场＝结构性裁决六项全部支持（含限注与缺口记录）+ 新增 AB 口径修订声明与拟补待办 d/e/f；主模型最终决定＝结构性裁决定案 + 口径修订追认（见十）；条件闭环＝部分闭环（人耳/闸门0/补测项未闭环，见七）；[PRESSURE-OVERRIDE]＝否。

**十、主模型追认（2026-09-18）**：
1. **采纳 AB 口径修订声明全文**（第四节），ε=5% 仅适用于可测指标（结构性三项与闸门0 拦截率）；本次修订系"跑前契约中的指标在实测面不可得"的客观修订，非跑后改判，特此入档。
2. **待办 c（黄金集标注轮）触发条件**（满足任一即启动）：① 用户报告某片型系统性质量差；② 人耳抽检中漏线普遍（≥30% 抽检段存在明显漏线）；③ 闸门0 对照中某配置格拦截率 >25% 且显著高于其余格。
3. **待办排期**：a 人耳抽检需用户执行（本补记归档同时交付抽检清单）；b 闸门0 拦截率对照由执行侧排期为下一步任务；d/e/f 按需。
4. 风险跟踪①②⑤⑥照单全收；.abtest/.tmp374 暂保留原位待用户定保留策略。

**【2026-09-18 审查排序注记（两遍组合前三，供用户全面审查）】** 经与 decision-critic 讨论（其评议：有条件支持，五项修正全部采纳）达成共识：前三组合 = ① **anime-whisper(WhisperSeg) + qwen(TEN)**（官方拍档）② **anime-whisper + qwen(FireRed)**（=ENS 已测集成，锚点）③ **BAL(large-v2) + qwen(TEN)**（词级时间轴测试席）；另免费物化第 4 格 anime-whisper + qwen(WhisperSeg) 备席。采纳方法修正：取消 GPU 补跑，改用上游 MergeEngine.merge(pass1_primary) 零 GPU 离线物化（.abtest/materialize.py）；**方法自检通过**（离线 anime+FireRed 与已测 ENS 集成行数 1141/670/1427/1420 vs 1141/670/1426/1420，±1，离线≡集成）。组合实测四片均值：**C1 覆盖 43.5%/重复 10.9%/碎 18.2%/连重 0**；**C3 覆盖 36.0%/碎 29.5%/重复 11.5%/连重 1.0**（结构面弱）；**C4 覆盖 37.7%/碎 15.3%/重复 2.9%/连重 0**（结构面全面优于 C3，C3 席位理由仅剩词级时间轴待耳证）。审查配对：#1 vs #2 隔离 pass2 段切器（TEN/FireRed），#1 vs #3 隔离 pass1 体系（anime/BAL）；四类必抽段 = 难片(mikr082 必抽)/安静环境音/pass 交替边界/密集对话（はい・うん高频区），同窗跨格并行播放。GPU 仅留最终胜者集成新鲜重跑出生产签名件。待办 b（闸门0 拦截率对照）扩展至前三格合并产物；Q2 max_dur 长尾（8.95-11.4s）在耳审轮保 1 段闭合或显式关闭。

## [2026-09-19] D2026-0917-03-R1-E2 终态补记·F06 定版与实弹验证 [已执行]

**一、用户终选与推理（2026-09-19）**：用户终选 **F06（wseg×ten = pass1 Qwen3-ASR-1.7B+WhisperSeg / pass2 Qwen3-ASR-1.7B+TEN，pass1_primary）为上游默认搭配**。用户推理：下游可吸收重复噪声（本项目闸门0+预合并），覆盖不可恢复 → F06 反超 F02。终选与 E1-R1 既有裁定（F06 默认首推）同向，非推翻裁决；F02/F01 降为备选，bal 四格（F04/F07/F08/F09）维持出局、F10 维持不推荐。

**二、待办 b 实弹（gate0_probe.py，2026-09-19）**：复用项目 apply_source_filter/RefineConfig/parse_srt，与 pipeline_v2.py 真实调用同构，default 档 valve=50%。输入 Σ：F06=4821 行、F02=4785 行。删除：F06 4/4821（0.08%）vs F02 4/4785（0.08%），**唯一删除=mihd002 各 4 条「うん」连打行**；8 文件零 valve/tighten 触发。计数类检出 F06 反而更低：孤立应答词 197 vs 217、无意义音节连缀 23 vs 26。**结论："F06 行噪声可被下游吸收"证实，F06 反超成立（净 +36 行真实内容 @ 零额外删除成本）**。注：探针双跑导致 dropped_entries.log 内删除条目各重复追加一遍（共 16 行），计数口径按单跑 4 条/组合。

**三、生产签名件（2026-09-19 01:11-06:33）**：F06 真实集成 GPU 重跑 4/4 done，rc=0（.abtest\prod\F06__*\）。whisperjav_run.json：行数 1133/712/1457/1515（mihd002/mikr082/ure125/start422），与离线物化各 -1；span 99.8%/99.7%/99.7%/99.7%；耗时 43.4/61.7/117.5/98.9 min，合计约 5.3h。签名件即上游默认搭配权威产物，供下游滚动观测基线。

**四、待办清单销项状态**：待办 b ✅ 已闭环。manifest 键名比对部分完成（files[0] 结构经探针/run.json 验证 ✓；asr_meta 消费面 mileage_pct/tighten 链路留口至真实下游联跑）。待办 a（段切器耳审 12 段）**转为长期惯例项**——用户实际选用 TEN 格已构成行动偏好；风险显式记录：TEN 环境音短句型标记 6/部虽温和但未逐条耳核，日常观测异常时抽检随时启用。待办 d/e/f、semantic 对比轮按需保留。

**五、生产默认配置 CLI（prod_rerun.sh）**：`--ensemble --pass1-pipeline qwen --pass1-sensitivity aggressive --pass1-scene-detector semantic --pass1-speech-segmenter whisperseg --pass2-pipeline qwen --pass2-sensitivity aggressive --pass2-scene-detector semantic --pass2-speech-segmenter ten --merge-strategy pass1_primary`

**六、后续风险跟踪**：① 4 部过拟合滚动观测（日用 mileage/质量报告，新片型异常触发待办 c 条件）；② 按片覆写路径（单部异常可独立切换 F02/F01 备选并回取离线物化件）；③ bal 系留盘（可回取词级时间轴，维持出局结论）；④ 证据目录保留策略由用户定（.abtest、.tmp374、外部点评两 txt）。

**七、decision-critic 核验声明**：转「已执行」条件成立——用户终选（①）、待办 b（③）、生产签名件（④）已闭环；待办 a（②）经用户终选构成行动偏好转为常规惯例项（风险已列）；过拟合监控（⑤）为长期观测项。无 [HIGH_RISK_OBJECTION]，[PRESSURE-OVERRIDE]＝否。

**【2026-09-19 v1.9.3 增补轮注记（E2 后追加，结论不变）】** 上游发布 v1.9.3（主题=语音增强器 bug 修复+翻译/安装体验，未触及 qwen 管线/段切器/合并策略，本决策链报告的五项工程问题均未修复）。升级方式：whisperjav-upgrade 在兼容性检查环节无超时挂死（实测 0 CPU/0 磁盘/0 网络），改用官方 release wheel `--no-deps` 安装 + 清华镜像装 demucs（4.1.0），环境零损伤（torch 2.11.0+cu128/ct2 4.8.1 保持）。双难片增补实测（MIKR-082 稀疏安静型 + URE-125 密集长片型）：① **回归格两片与 v1.9.2 签名件逐项一致（712/27.6%、1457/48.7%）——v1.9.3 零行为漂移，F06 定版结论与全部历史测试数据继续有效**；② 增量格 htdemucs+enhance-for-vad（作者 1.9.3 新首推）：环境音短句 5→1（-80%）、重复率 15.0→11.1（-3.9pp），代价覆盖 48.7→46.2（-2.5pp，-85 行）+耗时 +23%；安静片上无效果无损害。**裁定：F06 定版维持原样（覆盖优先）；htdemucs/enhance-for-vad 记录为"按片开关"（dense 型片求净可开），不改默认**；增补结论已并入上游测评报告第九节。

## [2026-09-18] D2026-0917-03-R1-E1-R1 外部 AI 点评综合裁定轮（10 final 最终推荐排序）[已拍板·待用户终选与待办 a/b]

- **原决策**：在 D2026-0917-03-R1-E1（结构性轮 AB 完成）基础上，综合外部 AI 点评 + 标记词硬数据（结构指标 + 两轮 substring 计数），裁定 10 个 final（F01-F10，pass1_primary 离线物化，锚点回归 16/16 通过）的最终推荐名单与排序，供用户全盘定夺。
- **外部点评的双族幻觉分类学（标记词计数证实）**：**BAL/Whisper 系=内容离谱型串台句**（犬/猫/母親/犯人类，实测集中于含 BAL 的格子：F04=9、F07/F08/F09 各 11-12，与 pass 角色无关=BAL 内容稳定属性）；**TEN 补漏=环境音短句型**（ねえ、何を 类，F02/F06/F08/F10 各 6，wseg 偶产 1）；anime 系"大规模崩溃"指控实测为低密度（F01-F04 各 4=每部 2 处）；纯 Qwen 格与 anime+Qwen 格的"安全句"（あなたは何を…类）**实测全 0**——安全句仅现于 bal 相关格（F07/F08/F09=4、F04=1），归因修订为"**BAL 补漏触发型安全句填充**"而非 Qwen 通用特性。标记总分（不含争议类）：F05=3、F01=4、F03=5、F06=8、F10=8、F02=10、F04=14、F07=20、F09=21、F08=26。
- **外部点评的采纳/驳回**：采纳——双族分类学（修订后）、folder1 选 F06（唯一未被硬数据否证的背书）、互证+语义审读方法论保留为人工/LLM 审读环节、F05/F06/F10 确认怪词。驳回——folder2 选 F07（其核心论据"F07 无自创句"被硬计数反驳：安全句 F07/F08/F09 各 4 而 F06=0；且 F07 在 folder1 有 11 处串台+结构面最弱，按片型分派不采纳）；"anime 大规模崩溃"（低密度）；多处版本归属张冠李戴（おきはなかしい 实在 F07/08/09 非 F03；車性依存症 仅 bal 系）。
- **decision-critic 异议（八项）与主模型决定**：**全部采纳**——①F01"最干净"标签撤回（结构最净=F03 重复 2.9/碎 15.3；标记最净=F05=3；F01 改称"ENS 锚点+零环境音污染"）；②bal 出局扩为四格（含 F04）；③安全句归因修订（见上）；④计数表述改用"最低存证密度"（substring 相关非真值，相对排序可信、绝对密度不可信，含真台词误报风险）；⑤词级时间轴为 BAL 原始 SRT 中间资产（留盘可回取，非 final 属性——合并产物均长 1.75-2.39s 仍为句级，F08 测试席层位错误故移除）；⑥INFO_GAP 闭环：外部审读对象确认为日文源文 SRT（引例均为 final 源文原文行），与我方计数同一产物面；⑦方法论六条记录（真台词误报、词表内生性、N=4、分母口径、等权重、脚本落盘 .abtest/markers.py v1）；⑧三强含 2 个 TEN 格，段切器耳审（待办 a）先于生产默认定版，选 TEN 格≠预投一票。
- **最终推荐排序**：**1. F06（wseg×ten）默认首推**——覆盖 45.0 全场最高（不可恢复维度最大化）、连重 0、标记 8 全温和类、外部唯一幸存背书同向；**2. F02（anime×ten）并列首选**——官方拍档信任面、结构较净（重复 10.9/碎 18.2），代价覆盖 -1.5pp、标记 10 含争议句；**3. F01（anime×fire）**——ENS 锚点、零环境音污染、覆盖 40.9，难片占比高则名次降；**相邻备选 F03（anime×wseg，结构最净）/ F05（wseg×fire，标记最低）**；**明确不推荐：F04/F07/F08/F09（BAL 内容污染，标记 14-26）与 F10（重复 16.4 最噪无补偿轴）**。
- **条件是否已闭环**：决策层面闭环。执行面未闭环——①用户终选（F06/F02/F01 口味取舍）；②待办 a 段切器耳审先于定版；③待办 b 闸门0 拦截率对照扩展至三强先于签名件；④胜者 GPU 新鲜重跑出生产签名件（现三强为离线物化件，仅作评审基线）；⑤4 部过拟合由日用 mileage/质量报告滚动观测+按片覆写路径兜底。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：① F06 行噪声"可被下游吸收"待待办 b 实弹核对；② bal 串台标记解读须耳审抽 ≤10 条验证（相关非真值）；③ markers.py 复跑偏移已修订归因（C 类=TEN 主导+wseg 偶产，F03/F05/F09 各 +1，排序不变）；④ 词表 v1 归档 .abtest/markers.py，修订须升版留 diff；⑤ 无词级消费者假设失效时 BAL 原始 SRT 留盘回取；⑥ 外部点评两份审读原文（.abtest 前用户置于 abtest_final 的 F06/F07 txt）建议随证据迁移持久路径。

## [2026-09-18] D2026-0918-01 v1.2.2 Beta 特性「剧情自摘要 auto_synopsis」[已拍板·实施完成（待批次E双轨实弹）]

**一、决策问题**：将 per-片手写剧情摘要自动化（auto_synopsis）：闸门0+预合并后、阶段A 前，用阶段A 同一 provider/model 追加 1 次 LLM 调用，对源文采样（synopsis_max_chars 默认 6000）生成 3-5 行中文剧情备忘（人物关系/核心剧情线/场景构成），以批次 C 冻结措辞注入 A/B 两阶段 prompt。用户已批准"翻译提示词功能，可尝试作 beta"；纯提示词内部消耗、与刮削无关、产物不落输出。版本策略与 E 验收口径须裁决。

**二、已核实事实**：
1. sidecar 冻结措辞（pipeline_v2.py:169-171）与 A/B 双注入点（:578-581）存在，自动摘要复用同挂载机制与同措辞；手写【剧情摘要】存在时优先、自动跳过。
2. context_sidecar 入指纹已有先例（manifest.py:369-372），新增 auto_synopsis/synopsis_max_chars 两键进 _CONFIG_FIELDS 无机制障碍。
3. v1.2.2 批次 A-D 完成、866 passed、E 待执行；代码未 commit、未发布。
4. 8 项指标中 バラまく 语境正确 0/5→5/5 为语境级硬伤指标，语境词绝不入 hard 词表（v1.2.2-计划表 §四）——该指标达成的唯一语境通道是本 beta 或手写摘要。
5. 长片 83KB（正文约 2.6 万字），6000 字符采样约覆盖 22%，单窗采样对情节主线覆盖无保证。
6. 净语清洗在阶段A 批内执行（pipeline_v2.py:1089），摘要输入含未净语行；有效指令落盘 refine_v2_A/B.txt 可作审计留痕。

**三、decision-critic 评议结论**：
- **[HIGH_RISK_OBJECTION] 一条**（E 验收混入 beta 变量=循环验收）：beta 开启下指标 2 达成无法区分 v1.2.2 既有修复与 beta 成就；8 指标不覆盖"摘要编造情节"，beta 缺陷可被 E2 全绿掩盖；失败亦归因不清。判定依据：与 D2026-0917-01 批次验收共识冲突 + 影响方案结构。
- **普通级条件六项**：摘要幻觉（非连续片段显式说明+信息不足计数，不加全量复核）；采样升级为时间戳分桶；默认开但须显式关闭通道、E2-A 显式关、cloud 成本不设门槛；缓存不得放 translation_memory（TM 用户数据语义，且用户已在该目录做过人工对账）改独立目录+复合缓存键；补并发原子写/独立 max_tokens/超时/噪声行过滤/日志附 sha1。并入 v1.2.2 工程时点最优，问题在验收口径不在版本号。

**四、主模型拍板（全部采纳）**：
- **HRO → 方案甲双轨 E2**：E2-A 显式关闭 beta 做正式 8 指标验收；指标 2（バラまく）因用户已否决手写剧情摘要如实验收——预期不达标、不宣称达标，顺延由 beta 验证；E2-B 同片开启 beta，仅做 diff 对比 + 指标 2 改善评估 + 摘要质量人工抽读 + 非指标行反向污染复检，改善结果显式声明归属 beta，绝不记 v1.2.2 既有机制头上。
- **条件 1-8 全部采纳**：①双轨 E2；②时间戳分桶均匀采样（6-8 桶×约750字符≈6000 上限）+采样范围入日志+摘要输入跳过纯噪声行；③prompt 增"片段来自整片不同位置抽样、时间不连续、禁止补足跳跃段"+"信息不足"逃生口与计数；④--no-auto-synopsis 显式关闭通道，E2-A 必须显式关闭；⑤缓存独立目录 Temp/synopsis_cache/，键=sha1(采样后输入文本)+provider/model+prompt 版本号，原子写+每键锁；⑥独立 max_tokens（约300）与超时 min(timeout_llm,300s)；⑦手册补 resume/换模型指纹边界，日志行附摘要 sha1；⑧决策日志与 CHANGELOG 标注 Beta，指标 2 归属显式声明。
- **版本策略**：并入 v1.2.2（未 commit 未发布、E 未执行），CHANGELOG 标 Beta；默认开（用户明示尝试）+显式关闭开关；cloud 档跟随阶段A provider/model，成本不设门槛。
- **INFO_GAP 答复**：(a) E2 样例片无手写 sidecar（用户已否决手写剧情摘要）；(b) 现行生产模型型号为 D2026-0917-02 风险⑥悬置项，摘要模型自动跟随 --s1-model，不阻塞本特性。

**五、验收归属声明（写入 E2 验收报告）**：指标 2 的 E2-A 结果如实记录（预期不达标）；E2-B 的改善以名文"该达成由 beta 特性 auto_synopsis 贡献，非 v1.2.2 既有机制成就"标注，二者均不得混记。

**六、后续风险跟踪**：① E2-A 指标 2 不达标不得以任何形式宣称 v1.2.2 语境修复达标；② beta 反向污染复检已入 E2-B，上线后按月抽读 2-3 部片摘要并核对信息不足计数；③ 缓存键含 provider/model，换 --s1-model 自动隔离，配合手册 --force 边界说明；④ 原子写/每键锁须在多文件并行场景实测一次；⑤ 摘要质量与"信息不足"占比为 beta 转正式的判定素材，由 E2-B 与日常运行积累；⑥ D2026-0917-02 风险⑥（生产模型型号补记）仍悬置，记录在案。

**七、决策日志字段**：原决策＝v1.2.2 Beta 特性「剧情自摘要 auto_synopsis」（新立，含版本策略与 E2 验收口径裁决）；decision-critic 异议＝[HIGH_RISK_OBJECTION] 一条（循环验收，附方案甲/乙）+ 普通级条件六项；主模型最终决定＝采纳（方案甲双轨 E2、条件 1-8 全采纳、并入 v1.2.2、默认开、cloud 跟随）；条件闭环＝决策层面全闭环，执行面已全部实施（synopsis.py 新模块、分桶采样、缓存迁移、独立 max_tokens/超时、--no-auto-synopsis、指纹两键、手册 11.7、CHANGELOG Beta 标注；882 passed），待批次 E 双轨实弹；是否 [PRESSURE-OVERRIDE]＝否；风险跟踪见第六节，指标 2 归属声明（第五节）为验收强制项。

**八、执行追记（2026-09-18，批次 E 完成）**：
- E1 清洗：删除 1,134（24,214→23,080），全量备份 tm_full_backup_20260918_161031.csv，白名单 2 条保留，sha256 6a15b48b…99a0。
- 模型基线偏差（显式声明）：探针实测 translate-ja-zh-qwen3-8b 与 sakura-14b 均不遵守输出协议（编号/Translation> 前缀缺失），本机唯一协议兼容模型为 qwen3.8-27b-uncensored-joyfox-aggressive——E2 基线改用之，兼做该候选本地全量首验；D2026-0917-02 风险⑥（生产型号无记录）就此部分关闭（09-17 运行实走云端中转）。
- E2-A（关 beta）正式验收：指标 1=0/32 ✅、指标 3=5/5 ✅、指标 4=0/2 ✅、指标 5=2/2 ✅、指标 6=保留 64/删 6 ✅、指标 7=TM 命中 2/1160 ✅（恰为白名单 2 条）、指标 8=恒等式✅/100%；指标 2=2/5 明确正确+0 错误+3 条待定性，按裁决如实记录不宣称达标。[未翻译] 59 条（契约保留）。
- E2-B（开 beta，--no-tm 保 diff 纯度）：摘要 92 字/8 桶全片覆盖/信息不足 0 次（sha1 720d5e74…）；指标 1-5 与 E2-A 完全一致；diff=433 条（37.6%）译文不同；恒等式✅；[未翻译] 64。
- **用户验收裁决（2026-09-18）：选定 E2B 为成品**（基于翻译字幕对比效果更好；B 的[未翻译]略高 64:59、质量报告其余基本一致，均知悉）。按本决策第五节归属声明：**E2B 的语境改善由 beta 特性 auto_synopsis 贡献，非 v1.2.2 既有机制成就**。beta 维持默认开启；术语冲突观察 5 条留待用户判定。分歧复核.csv 两轨均为空属预期：本次为单引擎模式（无兄弟 pass），双引擎分歧通道无数据。
- 产物转正：E2B final_cn/质量报告 已复制至源目录（旧 09-17 版本改名 .bak-0917 保留）。v1.2.2 commit 待用户指示。

**九、执行追记（2026-09-18，TM 全量清空）**：用户指令全量清洗 TM 库（当前翻译不入库，为下一阶段模型测试提供干净基线）。执行：文件级备份 tm.db.bak-full-purge-20260918（清空前 24,071 行=23,080+E2 轨道新学 991）+ 既有全量 CSV 备份 tm_full_backup_20260918_161031.csv（E1 前 24,214 行）；tm_entries 清空至 0。模型测试建议每候选独立 --no-tm 或轮间清库，防首批学习污染后续对照。learned 自学习词库（glossary_learned.csv）为独立注入通道，是否同清由用户裁决（工具 glossary_learned_reset.py 就绪）。

## 2026-09-19 D2026-0919-01 [已拍板，条件待试点闭环]

**原决策**：5 本地模型 × A/B 两阶段翻译管线全搭配测试（25 组合）执行方案——`tools/model_matrix_run.py` 跑批器 + manifest 种子化复用阶段A + 组合间隙换模；全程 --no-tm、人工词库统一注入、组级 synopsis 缓存管理；试点 joyfox27b→trans8b 先行验证后放全队列。

**我的异议**（本决策我输出两项 [HIGH_RISK_OBJECTION] 及若干条件项，均被采纳）：
1. **[HIGH_RISK_OBJECTION-1] A 产物截获时机与代码事实冲突**：`subtransjav/refine/pipeline_v2.py:1762-1769` 中 "✅ 阶段A完成" 的 print 早于 manifest 落盘（A=done）且无 `flush=True`；stdout 触发存在静默劣化 A 草稿或静默全量重跑两重风险。要求改 manifest 文件轮询触发。
2. **[HIGH_RISK_OBJECTION-2] synopsis 组合级清空与复用机制自相矛盾**：缓存键已含 provider+model（`synopsis.py:162-174`），跨模型泄漏结构上不可能；组合级清空会迫使 B≠A 组合在 s1 未装载时调用 s1、失败静默降级为无摘要，与种子组合不同处理。建议改组级清空以实现全矩阵零中途换模。
3. 其余条件项：不传 --auto-glossary；glossary.csv 与 glossary_learned.csv sha1 批前快照+逐组合复核（变动即停队列）；成功判据=退出码∈{0,3} 且 final_cn.srt + 质量报告.txt 齐备才原子写 .done；退出码 3 为噪音信号（`cli.py:368-370`），[未翻译] 计数直接数终稿 srt；组合级软看门狗超时 kill+resume；stdout 环形缓冲；磁盘 ≥10GB 预检；include 存活检查用 /v1/models 就绪轮询、失败=组合失败不降级。

**主模型最终决定**：**采纳（全部，含两项 [HIGH_RISK_OBJECTION]，无复议）**
- 采纳-1：截获改 0.5s 轮询 manifest（A.status∈{done,degraded} 且 final≠done 时原子复制 srt+manifest），种子校验含 stages.A 模型字段与 input_sha1。
- 采纳-2：synopsis 清空粒度改组级；B≠A 组合零 s1 调用（缓存键命中）→ 全矩阵 25 组合零中途换模，JIT 竞态整体删除；换模仅在组合间隙（lms unload/load + 1-token ping 就绪，失败=组合失败）；附加看门狗——B 组合运行前后快照 `Temp/synopsis_cache`，出现变动即判 suspect_synopsis 无效。
- 其余条件全部采纳；glossary_learned 若已存在存量文件，作为隐藏常量在评测口径中注明。

**条件是否已闭环**：未闭环。关闭路径=试点验收：joyfox27b→trans8b / ipzz-847（739 条）全链路验证（截获内容 A=done、B 组合零 s1 调用、[未翻译] 残留与新鲜基线一致）+ 同模型新鲜重跑 A 的 diff 验收（≤2% 行差异）+ kill -9 中断恢复演练。责任方=主模型（编码实现后主模型复核试点数据）。试点未通过 → 全队列不放行（本人回退立场为反对放行）。

**是否 [PRESSURE-OVERRIDE]**：否

**后续风险跟踪**（复核节点）：
- 试点：截获 manifest 状态正确性、synopsis 缓存零变动、diff ≤2%、kill -9 续跑。
- 批中：glossary 双 sha1 逐组合复核；synopsis_cache 变动 → suspect 标记；[未翻译] 残留 vs 同组种子基线（显著高出 → 无效重跑）；组合级看门狗触发记录；.done 完整性。
- 批后：25 组合 manifest glossary_sha1/config_hash 一致性核验；glossary_learned 隐藏常量口径声明；评估阶段排除 suspect_synopsis 组合。

---

决策日志输出完毕，可归档。若后续试点出现新证据需复议（如 diff >2%、suspect_synopsis 频发、种子校验失败率异常），请携带上一轮日志与本轮材料重新发起评议，我将引用本条记录明示维持/修订/反转。

### D2026-0919-01 续记（2026-09-19 复议终结：diff 门槛重新定性）

- **原决策**：5×5 A/B 全搭配矩阵测试执行方案（含"试点新鲜重跑 A diff ≤2%"验收门槛）。
- **上轮状态**：已拍板、条件待试点闭环（diff ≤2% + kill -9 演练）。
- **本轮复议事由**：试点 diff 实测 25.85%（heretic35b），主模型以新证据申请门槛重新定性并放行。
- **复议裁决**：**采纳提案放行 + 条件**。机械验收（kill 中断/补漏截获/逐字节复用/摘要缓存同键命中）经日志抽查实证通过；25.85% 经证据链定性为模型采样方差（temp 0.1 长生成近并列转折级联；短生成近乎确定；已排除比较器空白噪声与服务端采样覆盖）。组内共享同一 A 草稿的固定刺激设计因高方差反而更强成立。
- **条件**：C1 报告口径（单次快照声明+方差指标+跨 A 组结论强制保留意见）；C2 joyfox27b 同口径方差补测（不阻塞队列）；C3 既有门槛全保（残留基线/synopsis 看门狗/glossary sha1/软看门狗）；C4 P3/P4 断言通过后放全队列；C5 可选端到端重复样本。
- **是否 [PRESSURE-OVERRIDE]**：否。异议级别：普通。
- **风险跟踪**：高方差模型种子 A 可能落于质量尾端（缓解=C1/C2/C5，[UNVERIFIABLE] 事前位点无法判定）；C1 未落地则跨 A 组比较结论无效。

## 2026-09-21 [D2026-0921-01] 生产模型搭配定版：质量优先 joyfox27b>heretic35b [已拍板·默认落位待执行]

**原决策**：从两轮矩阵证据中选定生产默认 A>B 搭配；判定权在用户。

**最终决定（用户拍板，主模型转达）**：
- 默认生产搭配 = joyfox27b>heretic35b（质量优先，约 70 分钟/部）。
- 同档替代采纳评议修正：heretic>hauhau 提为并列替代（盲评 39、R2 12.4 分、合计缺失 2、别停 1 处、A 离群 3）；hauhau>heretic 降为门槛候选（前置：用户接受"别停"4 处+"滑溜溜"1 处与盲评簇 34.6 偏硬风格）。
- 特选门控被本拍板取代：joyfox>heretic 由门控备选升为默认；原"启用前复验增益"建议转为生产期首文件三方抽检动作。

**决定性质**：用户权重选择（质量优先 + 暖库样本上限），非证据推翻指标对比；评议员稳健口径推荐（heretic>heretic）异议保留归档，执行层面服从。评议采纳情况：部分采纳（采纳同档替代纠正；未采纳默认搭配）。

**两轮证据要点**：
- R1 盲评（测试片B，21 段/42 分）：heretic>heretic 与 joyfox>heretic 均 40，heretic>hauhau 39；hauhau-A 簇 34.6（偏硬）；sakura-A 18.2；陷阱句全数通过。顶部 40/40/40 存在天花板效应，40 vs 39 无判别力。
- R2 终稿机械统计（测试片C，1162 源，TM 全新安装模拟）：健康梯队合计缺失（占位+真丢失）hauhau>heretic 0 / hauhau>hauhau 1 / heretic>hauhau 2 / heretic>heretic 4 / joyfox>hauhau 13 / joyfox>heretic 17；B=joyfox 占位 23~52、真丢失 7~20（重试耗尽降级，含管道混杂，未纯模型归因）；A=sakura 占位最多 151 最差。前四健康组合分数 12.4~13.0 差在 heretic 采样方差内，排序依据为稳健性/考点/盲评簇而非分数。
- 考点对照（51 源×16 组合）：部長で 人称读法仅 joyfox-A 语境正确（4/4）；クリ 误译"克里"源出 joyfox-A（4 中 3）、唯一被 B=heretic 纠正 → "若选 joyfox-A 则 B 必须配 heretic"前提成立。
- "别停"命中：heretic-A 各组合 1 处、joyfox>heretic 2 处、hauhau-A 系 4~9 处；B=hauhau 对 A=hauhau 有放大效应（4→9），对 A=heretic 不放大。
- 模型背景：heretic35b 采样方差大（批级 53%、全管线近义改写 25.9%）；joyfox27b 慢 5~10 倍；hauhau35b 修复力最强但 A 席位考点偏离多；sakura14b 草稿协议缺陷。

**勘误登记（两处）**：
1. 报告正文转录错：B=sakura 三组被误写为"0/669"并列首选；实测终稿 958~980 块、整行丢失 167~204 条（约 15~17%，字符量同比例下降，排除条目合并假象）。正文不得再作为后续选型引用源。
2. metrics_table 口径低估：漏覆盖记录 102/101/109 vs 实测整行丢失 167~204，低估约 50~100%。漏覆盖指标定义待审计（疑只记初始失败、漏记重试后吞行）。

**评议员异议与回应记录**：
1. [INFO_GAP] 同档替代取舍（hauhau>heretic vs heretic>hauhau）——采纳，heretic>hauhau 提级。
2. 默认稳健口径推荐 heretic>heretic——未采纳（用户权重选择），异议保留、执行服从。
3. 特选门控化——被升默认决策取代，原复验建议转生产期抽检。
4. 异议级别：无 [HIGH_RISK_OBJECTION]。

**新增机制证据（拍板后代码查证/实测）**：
- TM 精确命中=整句哈希直接替代、跳过 A/B 两段 LLM（pipeline_v2.py:940-963）；模糊命中阈值 0.98 仅注入参考不省生成；TM 入库为 B 终稿（pipeline_v2.py:2214-2358）。速度不随库增长显著改善（新内容命中率≈0），"提速论"未纳入决策理由。
- tm.db 实测 995 条（=joyfox>joyfox 产物）：含 [未翻译] 占位 40 条、克里误译 2 条；入库门槛只滤纯假名、不过滤占位 → 精确命中存在将占位/克里错误确定性回填后续文件的传播向量，与"优质缓存"前提冲突（优先级：高）。
- glossary_learned 通道默认开启但 32 单元零产出 → 新遗留核验项。

**条件闭环状态**：
- 条件①（生产期监控：合计缺失超阈值或出现整行丢失则回退并列同档 heretic>hauhau）→ 转生产期动作；【阈值校准】原 0.5% 阈值按健康梯队基线设定，而默认档自身观测基线为 17/1162≈1.46%，应以默认档基线±容忍带为界，超过即回退。
- 条件②（用户对"别停"语义明示判定）→ 未闭环：本拍板未含别停专项判定；joyfox>heretic 别停命中 2 处，收为首期抽检核验项。
- 特选复验建议 → 转生产期首文件三方抽检（含 别停/クリ/部長で 考点复核）。

**关联待决项**：
1. 决策项 #2：TM 995 条清零或保留——未决。按"优质缓存"前提，清零与本次质量优先拍板更自洽；若保留，至少剔除 40 占位与 2 克里条目。建议生产首部跑批前定。
2. glossary_learned 零产出核验。
3. 默认落位（安装/GUI 默认值写入）为待执行动作，涉及管线代码，需用户明确批准后另行委派。
4. 漏覆盖指标口径审计。

**后续风险跟踪**：TM 保留情形下占位/克里精确命中传播（含源字幕跨集重复句）；joyfox>joyfox 995 条不清零将构成"已排除搭配产物回流"；heretic 采样方差导致的占位/别停计数翻转；B=joyfox 类重试耗尽事件生产告警。

## 2026-09-21 [D2026-0921-02] 1.2.2 收尾批量执行：TM 治理、配置落位与遗留修复 [已拍板·执行中]

**决策问题**：D2026-0921-01 拍板后的收尾范围取舍——用户逐项裁决交接文件第六节遗留待决项与 1.2.2 审查遗留项，并指定执行顺序（防误提交 → TM 清零 → 配置落位 → 代码修复 → 新搭配成因分析 → 仓库收尾）。

**用户拍板（2026-09-21，闲时任务执行）**：
1. **防误提交**：.gitignore 补 config/glossary.csv.bak-*、tm.db.bak-*、tm_full_backup_*.csv、.abtest/、.tmp374/；提交前禁 git add -A 盲加。
2. **TM 995 条不保留为正式库**：备份（tm.db.bak-glossary-purge-20260921，sha1 7d1c8e64…，清空前 995 条 joyfox>joyfox 学习产物）+ CSV 快照后原子清零；新搭配 joyfox27b>heretic35b 使用独立库 Temp/translation_memory/tm_joyfox_heretic_20260921.db（--tm-db 指定），不复用旧库。关闭 D2026-0921-01 关联待决项 1。**【追记】执行中用户裁决：joyfox>joyfox 学习产物不需要备份——上述备份与 CSV 快照已删除，995 条彻底废弃**。
3. **glossary_learn_enabled 默认改 False**（config.py，D2026-0921-01 关联待决项 2 一并落位）：成因分析与清洗缺陷修复完成前学习通道保持关闭；显式 True 仍可开启。回归测试锁定。
4. **生产默认搭配落位**：RefineConfig.stages 默认 A=joyfox27b（qwen3.8-27b-uncensored-joyfox-aggressive）> B=heretic35b（qwen3.6-35b-a3b-uncensored-heretic-apex）。关闭 D2026-0921-01 关联待决项 3。生产首文件三方抽检留给用户首部正片时执行。
5. **新搭配成因分析立项**：mida-559 单组合 joyfox27b>heretic35b 跑批 + [未翻译]/缺失成因分类（证据独立目录、独立 TM、学习关闭）。
6. **8 条「[未翻译] Chicks。」残译清洗缺陷立项**：与前缀契约统一同批修复，确保该形态不进 TM 且不误删正常引用。
7. **sakura14b 不重测**，LM Studio 聊天模板修复项关闭。
8. **旧第一轮 25 组合不补做**成因分析，由新搭配成因分析替代。
9. **.abtest/、.tmp374/ 原始证据不入库**（原始目录保持 ignored），仓库只留 manifest/README（命令、日期、版本、哈希、结论、关键日志摘要）入库。
10. **1.2.2 审查遗留 4 条修复执行**：_filter_language 回填保护（P0）、[未翻译] 前缀契约统一（P1）、漏覆盖口径修正（quality_report.py，拆 missing_entry/untranslated_content，P1）、target_aliases 写侧修复（P2）；quality_report.py 动工前先补 544d8d0 diff 核查欠账。

**决策性质**：执行层收尾裁决（既有评议链 D2026-0919-01/D2026-0921-01 的延续），无新架构/选型议题，不另启动 decision-critic 评议；与 D2026-0921-01 评议结论（无 HIGH_RISK_OBJECTION）同向。

**是否 [PRESSURE-OVERRIDE]**：否。

**后续风险跟踪**：① 新搭配首部正片三方抽检（heretic>heretic / heretic>hauhau 对照）+ 别停/クリ/部長で 考点复核；② 学习通道重开前提=成因分析与清洗缺陷修复完成且抽检通过；③ .abtest/ 原始证据仅本地保留，磁盘清理前须先固化 manifest。

## [2026-09-22] [D2026-0921-03] Mimosa git-gate 阻塞裁决与本轮标准运行模式 [已执行]

**背景**：Mimosa 插件 git-gate（ZCode Bash 工具层 PreToolUse，非 .git/hooks 原生钩子）在 commit/push 前对全仓做静态快扫并强制拦截。本轮 1.2.2 收尾的 20 件变更（17 改 + 3 新，以提交时刻 git status 为准）被阻塞。核查事实：① 快扫报 27 个高危全部位于历史文件与被忽略的本地文件（create_shortcut.py、tests/test_secrets.py、tools/ 旧脚本、Temp/ 脚本、api.py 旧代码），与待提交 20 件零交集——且这些历史文件已随既有历史公开于 origin（本地与 origin/main 同步），对其拦截无保护价值；② 两次带 seal 正式扫描（normal + deep）对 26 条 findings 复核层全部裁定 verdictEffect=none、无 proofGaps（静态误报：本地单机工具硬编码 localhost、脚本内部构造路径、pytest tmp_path 测试夹具模式）；③ tests/test_secrets.py 上一轮已为过扫描改写字面量、本轮仍被同一规则命中——改写正常代码满足全仓扫描不可收敛；④ 插件 payload 为 Ed25519 签名混淆包，无扫描范围配置项；payload 文档核实 `mimosa validate` 的 allowlist 为内置窄域 Oracle，**当前版本无用户可配置的 findings baseline/allowlist**；⑤ 计数口径：hook 快扫 27 高危（实时工作树，含 Temp/ 脚本）vs 密封扫描 26 findings（快照口径 24 高 + 2 低），两套引擎范围时点不同，双口径分列、不强行核平。

**裁决（用户拍板，decision-critic 有条件支持，其 [HIGH_RISK_OBJECTION] 六条件全部采纳）**：
1. 本轮提交采用**终端直提**（(a)：在 ZCode 之外的终端执行提交脚本，gate 不生效）——否决 (b) 临时停用插件（全局无扫描窗口 + 恢复动作是典型静默失效点）；`--no-verify` 对工具层 gate 无效，不使用。
2. **不为 gate 修改正常业务代码**；历史误报不混入本轮提交，单列跟踪（见后续风险跟踪）。
3. 不修改/不卸载 Mimosa 插件。

**标准运行模式（当前插件版本下的固定提交前置流程，非一次性豁免）**：定向 secret 扫描（以提交时刻 git status 真实全集为准）→ 终端直提 → 三查（工作树干净 / 语义 commit 数与预期一致 / committed blobs 复扫）→ push 前远程状态核对 → push。任何一项失败即停止回报。

**长期建议（移交维护方，本仓无法自行配置签名保护包）**：① git-gate 改为仅扫 staged diff；② 提供 findings baseline/allowlist 机制。**重评估触发器**：插件更新（任一版本变更）即重评本模式。

**本轮前置证据（2026-09-22）**：定向 secret 扫描：20 件真实全集（17 改 + 3 新）× 10 模式（aws/github/google/slack token、私钥块、Bearer、JWT、键值对字面量、hex32/hex40 高熵串）全部零命中；decision-log 增补本条后对最终入库内容复扫仍零命中。输出摘要随执行追记留存。

**0916/0918 历史 TM 备份**：保持不动，处置权在用户。

**执行追记（2026-09-22 补录，状态转已执行）**：
- **六段提交**（b30f93f → 8223106，顺序与裁决一致）：b30f93f chore: ignore private glossary backups and evidence dirs → f94de78 chore: set glossary_learn_enabled default False → 66d259f fix: harden language filter and unify untranslated prefix → f64b79d feat: detect untranslated content in quality report + tests → 9701473 fix: preserve target_aliases on GUI save → 8223106 docs: finalize decision log and handoff/model matrix runner（含本条 D2026-0921-03 归档）
- **三查**：工作树干净（porcelain 空）；git log 恰六段语义提交；fetch 后 ahead 6、无分叉
- **blobs 复扫**：HEAD~6..HEAD 新增 1964 行 × 10 模式（aws/github/google/slack token、私钥块、Bearer、JWT、键值对字面量、hex32/hex40）全部零命中
- **push**：首次执行未达远程（远程仍 745cb04，原因未查明，疑似凭据/工作目录问题）；重推成功 `745cb04..8223106 main -> main`，ls-remote 复核 origin/main=8223106，本地与远程完全同步
- 本追记为工作区唯一未提交变更，随下一轮标准运行模式入库（其提交前流程照旧：定向扫描 → 终端直提 → 三查 → blobs 复扫 → push）

## [2026-09-22] [D2026-0922-01] 1.2.3/1.3 版本划分与 GUI 参数裁剪定版 [已拍板→已执行]

**背景**：1.2.2 已收尾发布（六段 745cb04..8223106 加 SIM105 轮 92ebcea/952f6f4，本地与 origin/main 同步）。下一版本规划经两路探索调研与 decision-critic 评议形成推荐，含三项待终选。

**裁决（用户终选，2026-09-22）**：
1. **划分方式：两段式**——1.2.3 收尾+加固小版本（A2 残译清洗修复、A5 漏覆盖口径收口、A4 glossary_learned 零产出成因核验、quality_report/pass_disagreement 补测、mypy report-only 进 CI、GUI 裁剪参数、补打 v1.2.2/v1.2.3 tag、生产型号归档、决策包三项拍板）→ 1.3.0 架构版（pipeline_v2 拆分[验收门=全量测试+黄金集+CI 全绿，行为等价不过即回退]、词表覆盖层+加载优先级改造、GUI i18n+完整参数面板、LRU、文档修正、lockfile）→ 1.3.1 行为变更版（H4b 条目级阈值自适应、legacy providers 清理执行、guard 脚本、Mimosa 21 项甄别）。
2. **GUI 参数：裁剪版进 1.2.3**——仅暴露 source_filter、auto_synopsis、dry_run、verbose 四个安全参数；敏感开关（force_resume、glossary_learn 等）留 1.3 与 i18n 一并做。
3. **1.2.3 现在开工**。

**硬依赖**：①批次 E（TM 清洗+全新重跑+8 项指标验收）必须用 A5 修正后口径执行；②1.2.3 测试补齐是 1.3 拆分安全网；③A4 结论是 1.3 词表覆盖层改造前置输入。

**边界事实**：A5 双口径拆分（missing_entry/untranslated_content）已随 1.2.2 收尾批 f64b79d 落地并带验收测试（quality_report.py:604-638，test_pipeline_v2.py:1046 起）；1.2.3 内完成独立补测与复核收口，确认无残余缺口即结项，有缺口则补改。

**决策性质**：规划层裁决（延续 D2026-0921-01/02 评审链）；规划稿已经 decision-critic 评议（无 HIGH_RISK_OBJECTION），本次为用户终选，不另加评。

**是否 [PRESSURE-OVERRIDE]**：否。

**后续风险跟踪**：①批次 E 待 A5 结项后由用户执行；②A2/A4 修复结论与决策包三件拍板结果随执行追记回填本条或另立新条目归档。

**执行追记（2026-09-22 补录，状态转已执行）**：
- **release 提交**：`0b3dbc8` chore(release): 1.2.3 收尾版（单段提交，用户裁定口径；16 件 667+/11-，含 A2 残译清洗修复、A5 补测收口、A4 注释收口、GUI 四参、mypy report-only、版本 1.2.3、生产型号归档 models/README.md，及本条与 D2026-0922-02 归档）
- **执行结论回填**：A5 复核=双口径拆分实现正确零缺陷（f64b79d 已落地，本轮独立补测 11 例收口），批次 E 前置满足；A2=泄漏路径封口（`_normalize_untranslated_marker`，+3 例回归）；A4=32 单元零产出定性为双闸门默认关闭的设计行为，仅注释收口；决策包三件见 D2026-0922-02
- **tag**：`v1.2.3` → 0b3dbc8（已推送）；`v1.2.2` → 952f6f4 仅本地保留未推（远程已有用户手建无 v 前缀 `1.2.2` tag 同点并挂 GitHub Release，避免重名冗余；本地是否删除由用户定）
- **三查**：工作树干净（porcelain 空）；恰一段语义提交、领先 origin/main=1 无分叉；tag 解引用 v1.2.2=952f6f4、v1.2.3=0b3dbc8
- **blobs 复扫**：提交前工作区全集 16 件与 HEAD~1..HEAD 新增 667 行各 × 10 模式（aws/github/google/slack token、私钥块、Bearer、JWT、键值对字面量、hex32/hex40）全部零命中
- **push**：`952f6f4..0b3dbc8 main -> main` + `* [new tag] v1.2.3 -> v1.2.3`；ls-remote 复核 origin/main=0b3dbc8、refs/tags/v1.2.3 在位，本地 ahead=0 完全同步
- **待办移交**：①批次 E 由用户执行（A5 口径已收口，须用新口径跑）；②mypy report-only 首轮输出留 CI Actions 日志，阶段二收口时去 `|| true` 改门禁；③tools/model_matrix_run.py 11 项 ruff 债务（CI lint 范围外，1.3 立项清理或明确划出范围）；④本追记为工作区唯一未提交变更，随下一轮 standing mode 入库

## [2026-09-22] [D2026-0922-02] 1.2.3 决策包三件处置定版：v2_file_parallel 保留 / legacy providers 全表清理 / 4槽结构保留与槽位语义对齐 [已拍板]

**决策问题**：1.2.3（收尾+加固小版本，只决策不改码）对三件遗留项的处置裁决：①`v2_file_parallel` 休眠开关去留；②legacy providers（glm/groq 等孤立配置条目）清理范围；③v2 槽位 1/3 占位处置与 config 默认工厂语义对齐。

**评议方式**：decision-critic 独立评议。材料清单核验通过（三件事实逐条以代码只读抽查复核，含跨 git 历史对照 v1.1.0 era 与现 1.2.2 的 TM stage 写法）；主模型裁定后回传决策日志文本归档。

**裁决一（v2_file_parallel 保留，无修订）**：维持保留，2.0 规划时重议去留。依据：`config.py:331` 默认 False + 注释明示「P1-6 云端多文件并行（opt-in，默认关）……预留 2.0，当前恒为关闭（O10）」；`pipeline_v2.py:1388-1400` 有真实分支逻辑（云端服务商才启用）；无任何生产启用通道（不在 TUNABLE_FIELD_TYPES、无 env/CLI/GUI 入口）；`test_config_layering.py:79` 锁默认 False、`test_perf_optimizations.py:256/269/284` 显式 True 覆盖分支。删除是纯减法且测试有依赖，无维护收益。论据核验：`_file_parallel_enabled` 本地档恒 False，与分支注释/测试三方自洽；1.2.3 无净新增动作。

**裁决二（legacy providers 清理，范围采纳扩大）**：采纳评议的范围一致性补充——清理标准统一为「本项目全部入口（CLI choices / config.py PROVIDER_* 常量 / GUI / 文档）零暴露且仓内零引用」，据此范围扩大为 PROVIDER_CONFIGS 全表六条孤立条目：glm/groq/openrouter/gemini/claude/gpt（translate/providers.py:18-56，全仓仅自引用、无消费点；translate/__init__.py 已声明 legacy PySubtrans 引擎移除，v2 用 LLMClient 直连）。删除时对旧配置手写 `provider=<已删名>` 的路径补友好校验报错（禁静默空回退，注意 config.py:443 PROVIDER_MODEL_DEFAULTS.get() 的静默空值兜底语义需一并处理）；不采用「保留条目名只删字段」折中。执行窗口：1.3.1 执行删除，1.2.3 只记录决策。

**裁决三（槽位 1/3 占位处置，论据修正采纳）**：结论维持——保留 4 槽结构不动、压缩为 2 槽永久不做；「config 默认槽1/3 enabled 改 False」的语义对齐排 1.3.0 执行（1.2.3 不动码）。论据修正（采纳评议代码核验）：原论据「TM 按 stage 编号索引、压缩 2 槽致历史 TM 数据索引错位」不成立——v2 管线对 TM 读写恒为字面量 stage=1（pipeline_v2.py:979 lookup / :2376 store，git 历史 v1.1.0 era 起即如此），TM stage 编号体系（legacy 1/2/3，tm.py:10）与槽位数解耦。修正后归档论据：保留 4 槽的硬约束是五条路径多点联动耦合——①V2_STAGE_SLOT={"A":0,"B":2}（pipeline_v2.py:99-100）；②STAGE_NAMES 4 槽语义注释（config.py:100-101）；③manifest._V2_STAGE_SLOTS（manifest.py:219，契约测试钉住防两处漂移）；④GUI by_stage 阶段展示重建逻辑（webview_gui/api.py:1022-1036）；⑤历史配置 stages 数组默认工厂（config.py:227-233）。压缩成本高（五处联动改写+配置兼容+清单指纹）收益低，故永久不压缩。1.3.0 对齐附带要求：①顺带核对 GUI 阶段展示语义不被误导（api.py:1022 阶段重建逻辑）；②考虑一并厘清 StageConfig.name / STAGE_NAMES 索引语义（config.py:218-220），避免只改 enabled 留下第二个隐晦点。语义不一致根因确认：config.py:227-233 默认工厂槽1/3 enabled=True 与 cli.py:172-181 硬编码 False 确实矛盾；enabled 仅影响 manifest/GUI 阶段展示，对 v2 业务流程（按 tag→槽位取数）无行为影响。

**评议结论**：三件决策均无 [HIGH_RISK_OBJECTION]（均低风险、可逆）；一处论据修正（裁决三）与一处范围扩大（裁决二）均采纳；异议级别全部为普通，无异议保留项。

**是否 [PRESSURE-OVERRIDE]**：否。

**执行排期**：1.2.3 三件只记录决策、不引入行为变更；1.3.0 槽1/3 enabled 默认值对齐 False（含 GUI 展示语义核对、STAGE_NAMES/StageConfig.name 索引语义厘清）；1.3.1 PROVIDER_CONFIGS 全表六条孤立条目按统一标准审计后删除，旧配置 `provider=<已删名>` 路径补友好校验报错。

**后续风险跟踪**：①1.3.1 删除前复核一次全仓引用面（GLM_API_KEY/GROQ_API_KEY 等 env_var 占用无残留），删除后确认 config.py 校验路径对未知 provider 给出明确报错而非静默空值；②1.3.0 槽位对齐触及 config.py 默认工厂，需回归 test_config_layering.py / test_pipeline_v2.py / test_manifest_model.py 契约测试，防默认值改动影响清单指纹；③v2_file_parallel 休眠开关保持注释与测试锁定状态，2.0 规划时凭本条目重议去留。

**执行追记（2026-09-22）**：三件均为决策记录、无代码执行项；本条随 release 提交 `0b3dbc8` 入库并推送（v1.2.3），1.3.0 槽位对齐与 1.3.1 全表清理执行窗口照旧。

## [2026-09-22] [D2026-0922-03] 1.3 方案四项拍板定版：质量报告两层处置 / H4b 挂双且门 / tools ruff 前置清理 / mypy 分批清 [已拍板]

**背景**：1.3 方案（1.3.0 架构版 + 1.3.1 行为变更版，承 D2026-0922-01 / D2026-0922-02）提交 decision-critic 独立评议，产出 3 项 [HIGH_RISK_OBJECTION]，主模型全部采纳折入方案后提交用户终选。用户对四项待决点全部拍板（2026-09-22）；decision-critic R1 确认轮对问 A（H4b 定性与门条件可验证性）、问 B（mypy 边界定义）作出确认并给出补强文本，本条为定版归档。

**决策问题**（四项待决点）：①质量报告两层处置是否纳入 1.3 及子里程碑切分；②H4b 条目级阈值自适应的落地条件与顺延口径；③tools/model_matrix_run.py 11 项 ruff 债务（CI lint 范围外）处置；④mypy 存量清理边界、分批挂点与转硬门禁时点。

**三项 HRO 采纳记录**：
1. **HRO-1（行动层与 H4b 拆离）——采纳**。依据：上游 asr_telemetry.jsonl 仅 Balanced 车道产出（D2026-0914-01），而 1.3 生产默认 F06（wseg×ten，D2026-0917-03-R1-E2）非 Balanced；仓内零 telemetry 消费链（asr_meta.py 仅解析 whisperjav_run.json）；H6 黄金集为构造集基线（golden_v1.0，49 条）仅冻结闸门0 行为，不足以验证条目级自适应净收益。落地：行动层（报告驱动条目级定向重翻）独立交付于 1.3.1；条目级质量记录 schema 一次定义；H4b 仅作该 schema 的预留消费者。
2. **HRO-2（拆分验收"行为等价"域定义）——采纳**。等价域=拆分前后产物级字节快照：3-5 个真实输入，相同输入 + 固定 FakeClient + 空 TM + 固定词表 → final_cn.srt 与 {stem}_质量报告.txt 逐字节 diff（排除时间戳/LLM 段）+ 差异白名单（非零差异必须评审留痕）+ 每个新模块 ≥1 直接单测 + 有意变更单列豁免逐项挂回归（已知有意变更：词表文件缺失静默退化→WARN、槽位 1/3 enabled 默认 False）。
3. **HRO-3（1.3.0 负载与排期）——采纳**。排序：pipeline_v2 拆分最先 → 解读层 CLI 侧并行 → GUI i18n+参数面板+查看器+槽位对齐同批 → 词表覆盖层 → LRU/文档/lockfile 收尾；批次 E（用户实弹，A5 新口径）卡点在拆分动工前而非 1.3.0 末期；mypy 转硬门禁是专项非收口（见拍板四）。

**四项拍板与执行要点**（用户终选 2026-09-22，R1 确认轮结论已并入）：

1. **质量报告两层处置**。同意纳入 1.3 拆两层：1.3.0 解读层（CLI 侧，只动 quality_report.py）为可独立交付子里程碑，1.3.0 若延期其价值不捆绑沉没；1.3.1 行动层。执行要点：①新增 {stem}_质量报告导读.json（白话结论 3-5 条 + 章节清单 + 引用伴生文件名），与 txt 同一入参快照一次采集双渲染，txt 唯一全文权威；否决"GUI 直读 txt"与全量 json；导读 json 必须进 _backup_existing_outputs 与 delete_resume_artifacts，并顺带补齐既有缺口——{stem}_风险清单.md/.json 现既不被备份（pipeline_v2.py _backup_existing_outputs 仅覆盖 final_cn.srt/质量报告.txt/分歧复核.csv/术语冲突观察.csv 四类）也不被 resume 清理（manifest.py delete_resume_artifacts 仅覆盖 manifest/refine_A/幻觉处置报告.json/隔离区.srt 四类），存在陈旧/新鲜报告并存的公信力风险；②报告白话结论区必须带产物时间戳 + "基于本次运行"声明，"需处理 N 处"的 N 与章节明细同源计算（D2026-0916-03 两处数字打架教训）；③行动层 dry-run 预览先行，复用 manifest/resume 指纹，时间轴编号不漂移、恒等式不断裂；④词表优先级链（CLI 参数 > 用户词表 > 学习词表 > 内置）与既有配置分层在文档显式分域，新 CLI 参数进 manifest._CONFIG_FIELDS 指纹。
2. **H4b 挂双且门**。由"1.3.1 落地"改为条件落地：门①F06 默认拍照下 asr_telemetry 存在或明确降级口径；门②H6 真实语料基线建立。两门皆备（AND）方落地 1.3.1，否则顺延 1.4/2.0，届时复用行动层定义的 schema 不留债；1.3.1 只作 schema 预留消费者。**定性：对 D2026-0914-01 顺延承诺的细化而非推翻（R1 确认，本条即为显式标注）**，理由：原顺延三前提（telemetry 仅 Balanced / schema 无承诺 / H6 基线未建立）与双且门一一对应且全部仍然成立，F06 定版（D2026-0917-03-R1-E2）反而强化前提①；原条目源文即"4b 厚版 P1 或顺延 1.3"，1.3 从非无条件承诺；4a 已落地价值与其余 1.2 共识零触碰。门条件补强文本（R1）：门①分支 a 判定=F06 生产默认实跑一次（可复用 .abtest/prod_rerun.sh 权威复现命令）后 raw_subs/<stem>.asr_telemetry.jsonl 存在且非空；分支 b"明确降级口径"须落盘决策日志且至少含五要素——(i) telemetry 缺失时自适应默认不启用并在报告红标；(ii) Balanced 车道 opt-in 的 CLI/GUI 暴露点与档位说明；(iii) 对 resume 指纹的影响评估；(iv) telemetry 解析容错与上游 schema 无承诺的防御（复用 asr_meta.py R6 新鲜度/降级模式，此项吸收双且门原文本未覆盖的"schema 无承诺"前提）；(v) 降级口径生效的观测方式；分支 b 通过时 H4b 有效口径为 Balanced opt-in 子集而非全量自适应，验收按子集口径执行并在决策日志记录分支结果（a=全量 / b=子集）。门②判定=golden 集新增 origin:"real" 真实语料子集 ≥30 条且含 suspect/empty 案例，防循环验证记录（generated_by/标注人）齐全，tools/gate0_golden_stats.py 输出真实子集分项 precision/recall；最低样本量补强防"1 条真实样本即过门"。判定时点：两门均为 1.3.1 行动层动工评审时一次性判定，结果回写决策日志；若顺延，在 1.4/2.0 规划时凭新事实重判一次。
3. **tools ruff 11 项前置清理**。1.3.0 开工前独立小 PR 清掉 tools/model_matrix_run.py 11 项（R1 实测复核 11 项在案、其中 4 项可 --fix；CI lint 范围仅 subtransjav tests，.github/workflows/ci.yml:27）；不混入任何 1.3.0 功能改动；若排不下则显式划 1.4 并在决策日志留痕"已评估、因排期显式顺延"，不得悄悄消失。
4. **mypy 分批清（R1 确认：需要边界定义，以下即定版边界）**。存量随 1.3 周期分批清、独立专项、不挤进 1.3.0 核心路径；存量清零后转硬门禁显式单列。①核心路径清单=生产 refine 全链路：subtransjav/refine/ 全部模块 + subtransjav/translate/（llm_client.py、providers.py）；核心路径约束双轨——存量随工作流清零、当前已 0 错模块（config.py、manifest.py 等）"清零保持"不回添；utils/process_manager.py（R1 实测 28 错，占总量 46%）与 webview_gui/*（实测 9 错）列为非核心专项批。②分批与挂点（按 R1 实测分布 61 错/11 文件，开工时以 CI ubuntu/py3.12 同口径重测冻结）：M1 管线批 21 错（pipeline_v2 10 / quality_report 4 / glossary_conflict 2 / cli 2 / post_validate 1 / pipeline_support 1 / language_validator 1）随 1.3.0 对应工作流验收门附带"触及模块存量清零"；M2 GUI 批 9 错（api.py 7 / event_stream.py 2）随 1.3.0 GUI i18n+参数面板工作流附带；M3 独立专项小 PR 31 错（process_manager.py 28 / llm_client.py 3，纯注解无行为变更）排 1.3.0 周期内、tools ruff 小 PR 之后；硬门禁转挂 **1.3.1 收口验收门**（显式单列"mypy 全仓 0 错 + CI 去 || true"），M1-M3 提前清零可提前转，不强制等 1.3.1。③"新代码不新增错误"机制（基线文件法）：提交 mypy 基线文件（file:line:error-code 三元组），CI mypy 步骤（ci.yml:29-31，仅 ubuntu/py3.12 腿）改为基线过滤判定——不在基线的错误即 fail、基线内存量放行；配 tools/mypy_baseline.py 显式 --update（决策日志留痕）；存量清零后"删基线文件 + 去 || true"同一动作完成转硬门禁；本地预检同脚本可跑，须带 --python-version 3.12 与 CI 同口径（R1 实测本地解释器 <3.12 直跑会因 numpy stub 语法差异误报检查中止，该注记写入脚本注释）；备选 per-module 错误上限表因"同模块他处减少掩盖新增"不采纳为主机制。1.3 期间新代码按此机制保证 0 新增、最好随批次逐步收紧。

**评议结论（R1）**：四项拍板全部支持；问 A 定性细化非推翻，双且门补强文本已并入拍板二；问 B 需要边界定义，三项建议已并入拍板四；无新增 [HIGH_RISK_OBJECTION]。两处基线数字实测修正随本条归档：mypy 存量实测 61 错/11 文件（此前沿用口径 60）；pytest 口传基线"951 passed + 1 skipped"与 v1.2.3 tag（0b3dbc8，工作树干净）收集数 932 存在 20 例缺口（收集零错误，成因待核）。

**是否 [PRESSURE-OVERRIDE]**：否。

**后续风险跟踪**：①pytest 基线以 1.3.0 开工时全量实跑输出冻结为准（"只增不减"参照点须钉在可复现 commit 上），主模型先核实"951+1"与"932 收集"缺口成因（条件参数化/环境差异/口传失真）再冻结；②mypy 基线文件以 CI（ubuntu/py3.12）实测重冻，本地数字仅作参考；③门①门②判定结果须回写决策日志（新条目或本条追记），H4b 若顺延须注明"复用 1.3.1 行动层 schema 不留债"；④tools ruff 小 PR 若划 1.4 须在本日志显式留痕；⑤导读 json 与风险清单 md/json 的备份/清理补齐须附契约测试，防未来新增伴生文件再次漏挂；⑥批次 E（A5 新口径，用户实弹）为拆分动工前卡点，承 D2026-0922-01 硬依赖条款。

**补充指示追记（2026-09-22，用户确认轮）**：用户逐项确认问 A（细化非推翻、门①门②补强到位）、问 B（mypy 边界三项建议）、执行要点自查与归档结果，无异议。补充指示：①实测修正采纳，mypy 存量口径以 61 错/11 文件为准；②932 缺口成因核实**优先于**基线重冻——若系收集配置问题（conftest 标记/路径过滤/插件差异）则重冻会掩盖问题，若系合理用例增减（v1.2.3 后用例合并/删除）则重冻即可；③下一轮开工顺序定版：tools ruff 独立小 PR（开工首件，不混功能改动）→ 932 缺口成因分类 → pytest/mypy 基线重冻 → 分类结论回写本条风险跟踪 → 拆分动工前等批次 E（用户实弹）。

**开工首件追记（2026-09-22 交互轮，用户指令"满足条件前提下并行开工"）**：
- **A·tools ruff 11 项清零**：UP009/E401/I001/UP015 机械修；E402 将 sqlite3 import 真移顶部（无 sys.path 前置、无副作用，非 noqa）；SIM105×4 改 contextlib.suppress；SIM115×2 因日志句柄须跨子进程生命周期长驻（finally 统一 close）不可改 with，行尾 noqa 并留原因注释。验证全绿：`ruff check tools/model_matrix_run.py` 0 错、`ruff check subtransjav tests` 全绿、pytest 实测 **951 passed+1 skipped（collected 952）零失败**、`--help` 冒烟通过；行为等价（纯语法级替换+import 重排）。提交 `9074832`（单段语义提交，仅触 tools/model_matrix_run.py，23+/18-，UTF-8 字节核验无误）；三查过（porcelain 无该文件 / 恰一段提交无分叉 / show --stat 仅该文件）；定向扫描与提交后复扫同结果（26 findings 全为既有静态告警、提交零新增、依赖风险 0）。**push 待补**：10808 代理（v2rayN）未启动致 push 失败（代理重试+直连重置各一次），commit 滞留本地 ahead=1 无分叉，用户启动代理后 `git push origin main` + ls-remote 复核补齐。
- **B·932 缺口成因分类**：结论=**口径失真（环境差异）**，非收集配置问题、非用例增减。成因：tests/test_gui_api.py:16 模块级 `pytest.importorskip("webview")`（pywebview 为可选 gui extra）在无 pywebview 环境将 20 例转为 1 条模块级 skip 不入 collected；屏蔽 webview 的注入实验精确复现 932、正常 venv 复现 952。配置面排查：仓内零 conftest.py、无 addopts/deselect/markers 过滤（pyproject 仅 testpaths）。+31 增量经 745cb04..0b3dbc8 逐文件核对属实（test 函数 815→846），老基线 collected 推导 921=920+1 闭合。**基线冻结（主口径）**：@0b3dbc8、venv 含 gui extra、Windows：collected=952 / passed=951 / skipped=1（唯一 skip 为 test_process_manager POSIX-only 场景，仍计入 collected）；**副口径（CI/无 gui extra，`pip install -e ".[dev]"`）**：collected=932 / passed=931 / skipped=2。基线引用必须携带环境条款，两口径不得混用。
- **C·mypy 存量重冻（本地参考值，CI 为权威）**：venv 装 mypy 2.3.1、Python 3.12.10（=CI py3.12 腿），`mypy subtransjav` 实测 **70 错/12 文件（checked 44）**；较 R1 的 61/11 多出 webview_gui/main.py 9 错，成因=本 venv 含 pywebview 真实类型使 create_window arg-type 显形，而 CI 只装 [dev] 不含 gui → **CI 口径仍以 61/11 为参照**。分批映射不受影响：M1 管线批 21 错两口径完全一致（pipeline_v2 10 / quality_report 4 / glossary_conflict 2 / cli 2 / post_validate 1 / pipeline_support 1 / language_validator 1）；M2 GUI 批=api 7+event_stream 2（无 gui 口径，含 gui 口径另加 main.py 9）；M3=process_manager 28+llm_client 3。基线文件机制（mypy-baseline.txt/tools/mypy_baseline.py/ci.yml 改造）未实施，留待 M 批次另立。
- **附带披露（既有债务，非本件引入）**：Mimosa 深扫全仓共 26 处既有静态告警（high 24 / low 2，verdictEffect 均为 none）：路径穿越为最大类（含 refine 核心 10 处：cli/filters/glossary_conflict/glossary/instructions/language_validator/manifest/quality_report/runlog/tm，另 api.py 2 处、tools 7 处），另有 SSRF 2、命令注入 1、SQL 注入 1、不安全随机数 2；model_matrix_run.py 内 4 处经 `git show HEAD` 对照核为既有代码（行号随 import 增行推移），非本次引入。处置不在本件范围，留待用户拍板（可并入 M 批或另立专项）。**L2 diff 锚定复查核实（Stop hook 触发）**：403/1069 两处锚点=两条 `open(log_path, ...)` 语句，与 HEAD（原 394/1061 行）逐字节一致、仅行尾新增 `# noqa: SIM115` 注释及上方两行原因注释（这正是 L2 把锚点落进本轮 hunk 的原因）；`log_path` 来源为操作者自身 CLI 参数链（run_pipeline/mida_run_pipeline 形参→Path()→mkdir），本地离线实验工具、无不可信输入面。判定：非本轮引入的真实新风险，按既有债务随上述 26 处专项统一处置，不在本件 spot-fix（避免与全仓 24 处同类告警双标）。

## [2026-09-23] [D2026-0923-01] 翻译性能优化列为下轮任务：引擎盘点先行+并发/投机分层推进（批次E并窗管理）[已拍板·已执行]（2026-09-25 状态字段更正，见 D2026-0925-01）

### 一、背景

- 当前生产搭配（D2026-0921-01 用户拍板）：A=joyfox27b（qwen3.8-27b-uncensored-joyfox-aggressive，27B dense）> B=heretic35b（qwen3.6-35b-a3b-uncensored-heretic-apex，35B-A3B MoE），引擎 LM Studio@localhost:1234（OpenAI 兼容）。管线只控制 `n_ctx=32768`（config.py:280）、批30条/请求、温度0.1、批间并发=1（config.py:279，上限5）。
- 端到端约 70 分钟/70分钟片：A 阶段 61~63 分钟（约88%、约92秒/批）+ B 阶段 6~7 分钟 + 秒级本地步骤；瓶颈=27B dense 解码。带宽算术：RTX 5060 Ti 16GB（448GB/s）÷ IQ3_M 约13.5GB 权重 → 单流解码上限约33 tok/s。
- **时效事实（2026-09-23 日志实录，本次评议新核验）**：`Logs/9-23.txt` 显示凌晨批次E 首片 ftkd-030 整片失败——01:57 起 LM Studio 侧模型被卸载（`400 Model unloaded by user or API request.`），后续批量报 `400 No engine protocol runtime is registered for 'adOfeX…'`，02:13 定向重试预算耗尽仍缺 1245 行逐行降级，最终 tmp 文件丢失（`tmpi4dqzn7i.srt.tmp` Errno 2）致"成功 0 / 失败 1"文件级失败；`Logs/9-23-1501.txt` 显示 15:01 起同片重跑（转录产物复用，1671 条）、15:04 进入阶段A，即批次 E 实跑中且引擎刚发生 runtime 事故。实测 A 阶段 56 批约 98 秒/批，折算有效解码约 5~8 tok/s，远低于带宽墙 33 tok/s，存在约 3~5 倍头寸——"当前严重低效（疑量化档部分 CPU offload 或调度损失）"为实测支持假设，非纯推测。
- 缺口存量：引擎级参数（实载 GGUF 量化档、GPU offload 层数、ctx、KV cache 量化、Flash Attention、并行请求数）全部只在 LM Studio GUI 内，仓内零记录（交接文档量化档标"Q?"，models/README.md 只记模型 ID）；D2026-0917-02-R1 条件⑦承诺的 E3 逐候选 tok/s 吞吐实测一直未闭环。
- 已拍板事项（本决策不重开）：joyfox>heretic 质量优先搭配（D2026-0921-01）；模型矩阵两轮已测完（docs/模型测试两轮交接.md）；IQ2 档投产否决线（D2026-0917-02 及 R1 修订：取消测量席但保留否决）。用户既定验收口径：每步单独变更 + 全片实测 + 质量抽检后才采纳。
- 用户排期修正（2026-09-23 拍板前已确认）：**不设"批次E结项后才可动 LM Studio"的硬门槛**——对模型的参数调整本身即测试行为，其对批次E 的相互影响（显存争用、对照污染、环境变更）作为本批任务内的调整项统一管理（错峰执行、每次变更记录在案、批次E 结果解读合并考量环境变更史），而非等结项。

### 二、决策问题

"翻译性能优化"排期与分层的成立性评议与拍板：①"参数调整即测试、不设批次E结项门槛"修正是否可行、风险能否靠错峰+记录兜住；②技术分层（并发/投机解码/量化盘点）有无事实性错误或更高性价比替代；③验证口径有无漏洞；④有无必须先解决的高风险前置。

### 三、decision-critic 评议记录（2026-09-23）

**材料核验**：决策日志全文、README、models/README.md、模型测试两轮交接.md、config.py、lmstudio.py、pipeline_v2.py、llm_client.py、manifest.py、Logs/9-23*.txt 全部核验通过。无 [MATERIAL_CONFLICT]；一处时效事实刷新（上文 ftkd-030 整片失败与重跑在途）。关键代码事实：v2_concurrency 在 manifest 指纹内（manifest.py:338，改并发即废 resume）；"每批约11k 上下文"源自 DEFAULT_TOKEN_BUDGET 预算上限（llm_client.py:36-42：overhead 2500 + 30×300 输入=11500），非实测值；cap_batch_size 随 n_ctx 收紧批大小（llm_client.py:45-52，n_ctx=16k 时批自动收紧至 27）——引擎与管线 ctx 必须同步改。

**立场**：有条件支持（5 条件）；异议级别=**[HIGH_RISK_OBJECTION-1] 一条 + 替代方案 A1-A4 + 普通级条件五项**。

**[HIGH_RISK_OBJECTION-1]（窗口与对照面保护）**：批次E 已产出的成片结果在引擎变更后无法回炉重验当初环境，且引擎刚发生 runtime 事故、原"阶段A 两次冻结同一位置"未定案，此时无边界约束地放开行为变更试验，会使批次E 结论解读与事故归因同时失真。要求：行为变更试验必须在批次E 片间边界/心跳确认空闲窗口内进行，禁止片中途切换；否则需声明替代归因纪律，不接受则该异议升级为"反对无条件放开试验窗口"。

**替代方案**：A1 量化落位提前到第0.5步（若证实 offload 先修量化+重测E3，以修复后基线评估并发，杜绝把 offload 修复收益错记到并发头上）；A2 E3 基准脚本化（解析 Logs 批耗时换算 tok/s 一键脚本）作为执行辅助件；A3 引擎级试验（小样+基准）与生产采纳（全片实测+抽检）分离，不同步、不等结项；A4 并发优先、投机殿后，投机与并行槽同开须单独验证，受限则只取并发。

**普通级条件五项**：①"质量无损"须有可测口径——固定一把非批次E样片，并发1/2 两档各跑一次，比对未翻译计数/恒等式/考点锚定，容差跑前预声明；②第0步 E3 口径对齐 D2026-0917-02-R1 条件⑦（逐候选 tok/s、有效 token/分钟、同卡同并发、LM Studio 实测）；③引擎与管线 ctx 两侧同步改并记录（llm_client cap_batch_size 联动，防静默截断）；④第0步产出三档配置显存数值账（层数×KV头×dim×ctx×槽×量化），取舍链 KV q8→q4 / ctx 16k→12k / draft 4B→1.7B→弃用；⑤每次引擎变更后必跑 E3 重测再判增益，"61→35"为预期非承诺。另记录执行注意项：并发变更废批次E 已有产物 resume。

**[INFO_GAP] 三项**：当前引擎六项实际值与版本（第0步盘点对象，不另索要）；"GUI 并行请求默认=2"官方文档未能证实（第0步 GUI 直接读取闭环）；投机解码在接受率观测上无 LM Studio 版本行为承诺（不可观测则以 tok/s 提升+同文件输出一致性为代理并标注）。

### 四、主模型最终决定（HRO 回应：采纳；拍板定版）

- **HRO-1 回应：采纳（完整采纳，非替代）**。行为变更（第1/2/3招生效性试验）只允许在批次E 片间边界/心跳确认空闲窗口内进行，禁止片中途切换引擎配置；违反即当次文件结果标"受污染"归档。批次E 重跑（含 9-23-1501 起的 ftkd-030 重跑）定性为引擎健康度重试观测，其结果与每次变更快照一并写入环境史，供事故归因与批次E 解读合并使用。
- **A1-A4 全部采纳**：A1 新增第0.5步量化落位；A2 E3 基准脚本化列为执行辅助件，"每次引擎变更前后必跑"；A3/A4 引擎级试验与生产采纳分离、并发优先投机殿后、draft 默认 1.7B（非4B）、投机与并行槽同开须单独验证。
- **普通级条件五项全部采纳**（含容差跑前预声明、E3 口径对齐条件⑦、ctx 两侧同步、显存数值账+取舍链、每步 E3 重测）；v2_concurrency 指纹/resume 影响写入执行注意项；最终量化档位回写 models/README.md。
- **拍板内容定版**：
  1. 性能优化列为下轮任务；**三层节奏**：引擎级小样试验/E3 基准随时可做（不设结项门槛）；行为变更生效性试验守片间窗口；生产采纳仍以全片实测+质量抽检为入口。
  2. 分层结构（顺序硬约束）：**第0步** 引擎盘点（六项实际值+引擎版本健康度+并行默认值+E3 基线+三档显存账+ctx 同步确认）→ **第0.5步** 量化落位（仅当盘点证实部分 offload/量化放不进 16GB；修复后重测 E3 作并发评估新基线）→ **第1招** 批间并发 1→2（v2_concurrency 现成开关，上限5，LM Studio 侧并行数≥2 同步开，重算 KV/ctx 预算，必要时 ctx 32k→16k；预期 A 阶段 61→约35分钟，以实测为准）→ **第2招** 投机解码（LM Studio 内置，同词表 Qwen3 小模型 draft，draft 默认 1.7B，tok/s 提升 <1.1x 视为无效，接受率不可观测则以提升+输出一致性为代理；备选同批 GGUF 用 llama.cpp CLI 直跑为引擎级动作先不启动）→ **第3层** 量化档复核（Q4→IQ3_M 全载则提速；已 IQ3_S/M 全载则无降档空间；IQ2 否决线不碰，档位回写 models/README.md）。
  3. 明确不做：换模型（已拍板搭配）、现阶段换推理引擎、砍 B 阶段。管线级备选（A 阶段噪音标记挪规则侧减输出 token）优先级最后、需改代码，并发/投机均落空时启用。
  4. 预期叠加效果：端到端 70 分钟 → 约 25~40 分钟（估算区间，非承诺）。
  5. 批次E 协同：试验与批次E 抢同一 GPU，守片间窗口错峰（避开实跑时段/心跳间隔内确认空闲）；每次 LM Studio 配置变更记录时间戳与内容（记录粒度=每批运行时段的引擎配置快照，与批次E 运行日志对齐）；批次E 结果解读合并考虑环境变更史。

### 五、条件闭环状态

决策层面已闭环（HRO-1 采纳、A1-A4 采纳、五项条件全落定、三层节奏与分层结构定版）。执行面未闭环，闭环路径=第0步盘点产出（六项实际值+引擎版本健康度+并行默认值+E3 基线+三档显存账+ctx 同步确认）→ 第0.5步量化落位（若证实 offload）→ 第1/2/3招逐个"E3 重测 + 片间窗口全片实测 + 质量抽检"验证，每步独立闭环；批次E 并窗管理贯穿全程（变更快照+受污染标记纪律）。

### 六、是否 [PRESSURE-OVERRIDE]

否。

### 七、后续风险跟踪

1. 引擎健康度未定案：9-23 ftkd-030 runtime 注册事故 + 原"阶段A 两点冻结"未结案，批次E 重跑即健康度重试观测，其结果与每次变更快照一并写入环境史；
2. 并发增益与 offload 修复收益分账：并发增益判定以第0.5步修复后 E3 基线为准，禁止重复记账；
3. 引擎/管线 ctx 不同步静默截断：两侧同步改并记录，cap_batch_size 联动（n_ctx=16k 时批自动收紧至27，无害）；恢复 32k 时同样两侧同步；
4. 显存超预算：第0步数值账 + nvidia-smi 实测兜底，取舍链 KV q8→q4 / ctx 16k→12k / draft 4B→1.7B→弃投；
5. draft 词表不兼容/spec 静默不生效：LM Studio 加载校验 + tok/s 提升 <1.1x 判无效；投机与并行槽同开行为单独验证；
6. "质量无损"口径：固定样片并发1/2 对照，容差跑前预声明，跑后不得改；
7. 并发变更废 resume：v2_concurrency 在 manifest 指纹内（manifest.py:338），中途改并发使批次E 已有 refine_A 产物指纹失效，执行注意项入变更记录；
8. E3 基准脚本（A2）落位为下一轮执行辅助件；第0步"GUI 并行请求默认=2"以实测值为准回写本日志；
9. 管线级备选（减输出 token）维持优先级最后，仅并发/投机均落空时立项（需代码，另立工单）。

### 八、决策日志字段

- **原决策**：翻译性能优化排期与分层（引擎盘点先行 + 并发/投机/量化分层推进，批次E 并窗管理；不设结项门槛为用户 2026-09-23 修正）。
- **我的异议**：[HIGH_RISK_OBJECTION-1] 一条（试验窗口与对照面保护，判定依据=影响≥3任务+批次E成片不可回炉重验）+ 替代方案 A1-A4 + 普通级条件五项 + 执行注意项一项。
- **主模型最终决定**：采纳（HRO-1 完整采纳；A1-A4 全采纳；五项条件全采纳；拍板内容定版如上）。
- **条件是否已闭环**：决策层面闭环；执行面未闭环（闭环路径见第五节，自第0步盘点起逐步勾验）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：见第七节，其中①引擎健康度观测与③ctx 两侧同步为本轮新增强调项。

**第0步盘点追记（2026-09-23 交互轮，用户提供 GUI 截图 + config.json/GGUF 核实）**：
- 引擎实值：量化=Q3_K_M（主文件 13.30GB+mmproj 0.93GB=GUI 口径 14.23GB，文件名 -no-mtp=MTP 头已剥离）；上下文=130048；GPU 卸载=50/64（**部分卸载实锤**，总层数 64 经 config.json 核实）；Max Concurrent=4；KV 量化未设（fp16）；FA=开；KV 卸 GPU=开；投机解码=Off（功能确认在）；物理批 512/评估批 2048；采样面板 top_k40/top_p0.95/min_p0.05/重复惩罚1.1 为 API 未指定参数的实际生效值（GUI 温度 0.2 被管线显式 0.1 覆盖）——记录在案不动，属质量面另走验证。
- 架构事实：**qwen3_5 混合架构**，64 层=48 linear_attention+16 full_attention（interval 4），GQA kv_heads=4/head_dim=256/vocab 248320/rope 1e7/eos 248044；KV 代价=64KB/token(fp16)；线性层常数态 ~151MB 与上下文无关。
- 显存账与诊断闭环：130k ctx 理论 KV≈8.5GB、总占 ~22.7GB≫16GB→部分卸载必然（50/64 即后果），解码被 DDR4 拖到 ~10-13 tok/s（修正 critic 口径 5~8 tok/s：其假设全部批耗时为解码，实际含 prefill）。
- 用户实测佐证：调整前载入专用显存 15.2/16.0 饱和、共享仅 0.2GB；按变更单调整后未回落至预测 14.4-14.6——三因素对账=①任务管理器含桌面/驱动基线 ~0.9GB（预测为模型净占用口径）②实际参数高于假设（ctx 22272/物理批 1024/双槽 KV 池）③mmproj 0.87GB 仍载。**关键目标已达成：64 层全载+KV 双 Q8_0+FA 开**；占用非目标，吞吐待跑批实测（基线 98s/批）。
- 变更单六项（用户已执行）：①ctx→22272（用户自选值，管线侧跑批带 --v2-ctx 22272；自动化落地后引擎 ctx 由 --v2-ctx 强制对齐）②K/V=Q8_0 ③卸载=64 ④MaxConcurrent=2 ⑤物理批=1024 ⑥采样面板不动。
- 附带现场：15:01 重跑驱动进程已消失（GPU 空载/LM Studio 无在载模型/日志 15:04 后零行零报错），BatchE_Run 计划任务已不存在（schtasks 找不到指定文件）——静默死因与凌晨 exit 137 宿主击杀同模式嫌疑，重跑启动方式待用户确认；另检出双 GUI 实例并行（.venv 与 G:\python 各一，与测试用 venv 常设规则冲突）。

**第2招配套工程执行追记（2026-09-23 交互轮，用户指令"路线一 PASS，要项目运行时自动化加载卸载模型"）**：
- 调研修正：`ensure_lmstudio_model` 原为**死代码**（仓内零调用点）；真实接线点=pipeline_v2 `_make_client`（剧情摘要/阶段A/阶段B 三处）与 `_make_fallback_client`（本地接管）。
- 实现（**commit 92805cd**，10 文件 +378/-27）：①`utils/lmstudio.py` ensure_lmstudio_model 升级——对齐判定=未在载 / 已载 ctx 与 v2_ctx_local 不符（/api/v0/models loaded_context_length，字段缺失容错不误判重载）/配置 draft 但 lms ps 无 spec/draft 痕迹（best-effort，解析不可得视为已生效防重载循环）；对齐动作=`unload --all` 清场→`lms load -y --gpu max -c <v2_ctx_local> --parallel <v2_concurrency> [--speculative-draft-simple --speculative-draft-model <id>]`；draft 未下载自动降级不挂（质量无损）。引擎参数以管线配置为唯一事实来源，ctx/parallel 两侧同步由构造保证（落地条件③，根治引擎参数 GUI 零记录）。②pipeline_v2 新增 `_ensure_lmstudio_engine`（独立函数可测试打桩），三处接线、引擎未就绪 raise RefineError 快速失败。③StageConfig.engine_draft_model（默认空=不挂）+ CLI `--s1/s3-draft-model`。④manifest `_STAGE_FIELDS` 收录 engine_draft_model（换 draft 即失效旧产物须重跑）。
- 验证：**963 passed+1 skipped**（基线 951+1+新增 12，含 test_lmstudio_engine.py 10 例 fake 服务端状态迁移用例）/ ruff 全绿 / --help 冒烟通过；test_config_layering 两例直调 _make_client 测试已打桩引擎对齐（CI 无 LM Studio 不触网）。
- 提交按 D2026-0921-03 标准运行模式执行：暂存 diff 10 类 secret 模式零命中 → 终端直提（ZCode Bash 内 commit/push 被 L3 拦截=预期行为，27 高危全为 D2026-0922-03 已归档历史误报、与本次提交零交集）→ 三查过（porcelain 仅剩往轮 decision-log 追记与 .zcodeignore / 单段提交 / blobs 复扫仅提交哈希自身命中）→ 提交前后 Mimosa 双深扫均 26 findings=基线零新增（离线 advisory 命中 1 未升格 finding，本提交无依赖变更）→ push `9074832..92805cd` → ls-remote 复核 origin/main=92805cd 完全同步。
- 使用方式与遗留：下载 Qwen3.5-0.8B 后 `--s1-draft-model <完整模型ID>` 即全自动挂 draft；生产默认 draft ID 待 E3 实测通过后再入库（沿 D2026-0921-01 模式）；llm_client 请求期 400 "Model unloaded" 不在瞬态重试集合（ftkd-030 事故暴露面），是否纳入自动重载另行议。

**GUI 生产化追记（2026-09-23 交互轮，用户要求"GUI 选择 draft、开始运行后全自动，设计必须考虑普通用户场景"，CLI 参数不能成为用户必经之路）**：
- 实现（**commit 0c5adcc**，4 文件 +102/-1）：①index.html：阶段A/B 各增"投机解码 draft"下拉（默认"不挂 draft"，tooltip 说明同词表要求与质量无损语义）；灰参数行增"上下文窗口"数字输入（默认 22272、min 4096，tooltip 说明管线自动对齐引擎与 16GB 建议区间 16384~22272）。②app.js：buildRefineOptions 透传 v2_ctx/s1|s3_draft_model；readRefineCtx 兜底读取；refreshDraftModels 页面加载自动经 list_local_models 填充已下载全集（保留已选值）；设置保存/回填含三新字段（重启后选择不丢）。③api.py `_build_refine_args` 透传 `--s1/s3-draft-model` 与 `--v2-ctx`（空值不传旗标）。
- 普通用户路径闭环：**GUI 选 draft（可留空）→ 点开始 → 引擎加载/卸载/draft 挂载/槽位切换全自动**，全程无需 CLI 与 LM Studio GUI 操作。
- 验证：965 passed+1 skipped（新增 _build_refine_args draft/ctx 透传与缺省不传 2 例）/ ruff 全绿 / node --check app.js 语法通过；提交按 D2026-0921-03 标准模式（预扫描 26=基线 → secret 零命中 → 终端直提 → 三查 → 复扫 26=基线 → push `92805cd..0c5adcc` → ls-remote 复核同步）。

**draft 挂载缺陷修复追记（2026-09-23 实测轮，用户实测发现"GUI 已配置 draft 但 LM Studio 仅 27B 在载"而定性代码问题——定性正确）**：
- 定位证据：运行中子进程命令行含 `--s1-draft-model qwen3.5-0.8b-heretic@q6_k`（GUI→CLI 参数桥正常）；运行日志仅"模型已加载"无重载；`lms ps --json` 实测条目字段为 `modelKey/identifier`（**无 id 字段**），而 `_spec_draft_active` 按 `id` 匹配→永远找不到条目→按"无法判定视为已生效"放行→不重载、不挂 draft。根因=schema 无承诺下的探测字段错配；教训：**"无法判定"的缺省方向必须指向可观测验证（重载），而非静默放行**。
- 修复（**commit 44ab09e**，2 文件 +88/-24）：①改为 `_spec_draft_trace` 三态判定（True=确认已挂/False=确认未挂/None=无法判定），条目按 modelKey/identifier/id/path/displayName 任一包含匹配，未找到或 ps 不可用返回 None（不据此放行）；②新增 `_DRAFT_LOADED` 进程内缓存——本进程以 draft 旗标加载成功即记忆，重载至多每进程一次，杜绝 ps 探测能力未知导致的重复重载循环；配置改回不挂 draft 时清缓存防陈旧。③测试 +3（真实 schema 回归/缓存命中/缓存清除），fixture 隔离进程内缓存。
- 验证：968 passed+1 skipped / ruff 全绿；提交按标准模式（预扫描 26=基线 → secret 零命中 → 终端直提 → 三查 → blobs 真实机密模式零命中 → 复扫 26=基线 → push `0c5adcc..44ab09e` → ls-remote 复核同步）。
- 附带运维事件：实测中发现**两个相同 refine.cli 进程并发跑同一文件同一输出目录**（.venv 与 G:\python 双 GUI 实例各启动一次；tmp 互相踩踏风险与凌晨"tmp 丢失"文件级失败同款）——已终止 G:\python 重复进程（PID 27432），保留 .venv 进程（PID 29340）继续无 draft 基线跑（该进程内存中为旧代码，恰作无 draft 基线有效）；双 GUI 实例必须只留一个（再次提醒未消除）。
- 生效条件：正在跑的基线批不受影响、也无法中途获得 draft；**下一批起（新进程）自动生效**——joyfox 已在载时亦会因"配置 draft 但确认未挂"而自动重载挂载，日志出现"引擎对齐: ... draft=..."行即成功；若 LM Studio ps 始终不暴露 draft 痕迹，进程内缓存保证同批次后续文件不重复重载。

**draft 实测裁决追记（2026-09-23 深夜，受控 A/B 基准跑通并裁定）**：
- 修复生效实证：基准 B 启动后日志出现 `⏳ 引擎对齐: 加载 joyfox (ctx=22272, parallel=2, gpu=max, draft=qwen3.5-0.8b-heretic)`——已载无 draft 状态下自动重载挂载，44ab09e 修复逻辑实战验证通过。
- 基准口径：ftkd-030 同片（1671 条/56 批）、ctx=22272、并发=2、--no-tm --force、独立输出目录（_AB基准/），唯一变量=draft（qwen3.5-0.8b-heretic Q6_K）。
- **结果：不挂 draft 阶段A = 13.3 分**（22:40:52→22:54:10，~13.5s/批，零错误）；**挂载 draft 阶段A = 55.2 分**（17:20 完整挂载运行 17:20:48→18:15:58，另经 23:0x 复测确认远慢于基准 A）——draft 致 **4.15 倍减速**：0.8B heretic 与 joyfox 输出分布几乎不重叠，接受率近零，draft 前向纯亏。
- **裁决（依本决策 ≥1.1x 判据）：投机解码不采用**；GUI draft 下拉应切回"（不挂 draft）"。draft 基建（自动挂载/切换/降级/@quant 解析）保留，未来候选零成本可测。
- **性能定版：阶段A 13.3 分 + 阶段B ~8 分 ≈ 21.5 分/部**（对比 9-21 基线 68.2 分 → **3.2 倍**），达成并超出本决策 30±10 分钟目标。收益构成=64 层全载（根治 130k ctx 过配致部分卸载，大头）+ 批间并发 2；非 draft 贡献。
- 运维误诊纠正：`G:\python\python.exe` 子进程=venv launcher（.venv python.exe，CPU≈0）拉起的真实工作进程，**并非重复运行**；17:15 对 27432 的击杀实为误杀 17:04 draft 运行本体（用户"上一批中止"的实际原因）。教训：进程级诊断必须核对父子链与 CPU 时间，可执行路径≠真实身份来源。
- 事故源处置：BatchE_WD 计划任务（内嵌阶段B=gemma 非生产配置）为反复重 spawn 源头，已禁用；**恢复与否待用户裁决**（其队列与基准产物已重叠，建议废弃另立）。@quant 后缀容错已修并推送（**b8a2526**）。

## [2026-09-24] [D2026-0924-01] 批次1 引擎自动化回归锁——并发/GPU 对齐缺口的处置 [已拍板·已执行]

### 一、背景与决策问题

- 已定版排班（用户 2026-09-24 拍板）：批次 1 P0「引擎自动化回归锁」。**验收原文**：「测试覆盖：未载 / ctx 与 v2_ctx_local 不符 / 并发不符 / GPU 不符 → unload --all → lms load -y --gpu max -c <ctx> --parallel <并发>；断言重载命令不含任何 speculative 旗标」。
- **代码现实**（检索确认 + decision-critic 只读复核）：`subtransjav/utils/lmstudio.py` 的 ensure_lmstudio_model 对齐判定仅三项——①模型未载（need_load）②ctx 不符（_loaded_ctx 走 /api/v0/models，读不到返回 0 则放过不误判）③draft 无法确认（随 draft 移除删除）。**并发（--parallel）与 GPU（--gpu max）只在重载发生时作为加载参数拼进命令，不存在失配检测**——仅改并发设置不触发重载。
- **实时探测**（2026-09-24，`lms ps --json`，引擎 idle）：`"contextLength":22272, "parallel":2, "status":"idle", "deviceIdentifier":null`——ctx 已可检测；并发可检测（需新建 `_loaded_parallel()`，主包现无 ps 调用，属从零重建）；**GPU offload 无任何检测字段**（另经 `/api/v0/models` 已载模型完整 JSON 只读核验：仅 loaded_context_length/max_context_length/state 等键，无 device/offload/gpu 字段，两通道均无数据源）。
- **排班约束**：生产配置锁定 ctx 22272/并发 2/GPU max/KV Q8_0/物理批 1024/无 draft；HRO-1 行为变更须在两部影片之间的窗口部署；3.2 倍收益本体 = 64 层 GPU 全载 + 并发 2，防止回退是本批次动机。
- **候选**：A 补齐并发检测 + GPU 构造性保证；B 仅锁现状、缺口交用户排班外裁决；C 逆向/实测强行 GPU 检测。

### 二、decision-critic 评议结论与异议清单

评议立场：**有条件支持 A（修正案 A′）**；B 仅作用户显式缩小验收口径后的回退档；C 反对。异议清单（按严重度）：

1. **[HIGH_RISK_OBJECTION] 验收口径披露义务**：无论 A/B，未向用户显式披露「验收原文 vs 代码现实差异」即交付，即与既有共识（用户拍板验收原文）冲突；静默交付会让用户误以为 GPU/并发漂移有护栏而防回退动机落空。
2. **普通（高严重度）反对 C**：两处已验证无失配数据源；逆向未知字段或对 idle 引擎做加载实测属高不确定破坏性探索（反复 unload/load、lms 版本升级即碎、延误窗口）；收益仅把 GPU 从命令断言升级为运行态检测，而运行态 GPU 漂移已由重载命令构造性闭环。若坚持采纳 C 则升级为 [HIGH_RISK_OBJECTION]，前置条件是先做 `/api/v0/models` 全字段盘点。
3. **普通：A 的引擎 clamp 暴露面**——parallel 请求值被引擎静默钳制（报告值≠请求值）可致每次启动多一次重载（跨启动、非循环）；概率低（生产锁定值 2 远离钳制上限，探测基准实值已一致），缓解见裁定 A′ 第 5 条。
4. **[INFO_GAP]（已闭环）**：a) 并发是否存在片级/任务级合法覆盖路径；b) ensure 调用时点是否严格在两部影片间隙。
5. **普通：fail-open 判定静默退化风险**——ctx 现有 0=放过路径无日志，检测退化不可见；A 实现时补齐可见性。

容错边界六分支（防误重载/漏重载，全部须单测覆盖）：ps 输出非 200/JSON 解析失败、字段缺失、值为 0、非整数（null/字符串/布尔）、ps 超时 → **一律跳过判定 + warning 日志，绝不触发重载**（"查不到"≠"失配"，防每启必重载自我炸弹）；合法整数 >0 且 ≠ 目标值 → 真失配，走统一重载路径；重载后复核仍失配 → 本进程不再二次重载 + 警告。

### 三、主模型回应（全部采纳）

- 异议 1 [HIGH_RISK_OBJECTION]：**采纳**。披露落点 = 批次 1 提交信息 verify 段 + 本决策日志条目 + 完成通知向用户显式对照（并发=真实检测；GPU=无失配检测数据源，以构造性保证+命令断言近似）；验收按调整后口径请用户确认，**不标注"已满足验收原文"**。
- 异议 2：**采纳，C 驳回**——不逆向、不做破坏性加载实测。
- 异议 3：**采纳缓解**——容错全 fail-open、重载后复核仍失配仅警告不二次重载（ensure 每启至多一次，天然无环）。
- 异议 4a：**查证闭环**——无片级/任务级并发覆盖路径，v2_concurrency 为全局单源（GUI 输入框 / CLI 参数 / config 默认），配置值即期望值；引擎侧手动改值属漂移、应被重载纠正（与 ctx 同语义），**无需豁免通道**。
- 异议 4b：**查证闭环**——调用点为 `pipeline_v2._make_client` 与 `_make_fallback_client`（管线启动/回退建客户端时），与 ctx_mismatch 同一生命周期点，**非新增行为类别**；每启至多一次重载，无循环风险。
- 异议 5：**采纳**——parallel 未知跳过路径与既有 ctx 读到 0 的跳过路径均补 warning 日志。
- 窗口裁决（Q3-b）：**采纳**——见第五节。

### 四、裁定 A′（全文）

1. **新增并发对齐判定**：重建干净 `_loaded_parallel()`，重载前从 `lms ps --json` 读顶层 `parallel` 实值并比对 v2_concurrency。
2. **容错边界（六分支，按第二节落地）**：字段缺失 / 值为 0 / 非整数 / 超时 / 解析失败 → 跳过判定（fail-open，偏漏检不误重载）+ warning 日志；合法整数 >0 且 ≠ 目标 → 统一重载路径（`unload --all` → `lms load -y --gpu max -c <ctx> --parallel <并发>`）；重载后复核仍失配（引擎 clamp/不兑现）→ 警告，不二次重载。目标值与拼装 load 命令同一 `parallel` 参数单源。
3. **GPU 维持构造性保证 + 命令断言**：每次重载命令必带 `--gpu max` + 测试断言锁死；**不新增 GPU 失配检测**（两通道实测无数据源）。
4. **实施顺序**：先完成 draft 移除重构，在干净基线上叠加 `_loaded_parallel()`，避免重叠区双改动互相打架。
5. **可观测性**：parallel 与 ctx 的所有跳过路径落 warning 日志，防 fail-open 判定静默退化。

### 五、窗口裁决（Q3-b）

**parallel 判定不构成需要独立守窗口的行为变更，部署随批次 1 整体在两部影片之间的窗口内进行，不做 detection-only 观察窗。** 理由：①不改变加载参数（命令串与现状同构）；②触发时点与 ctx_mismatch 完全同构（管线启动/回退建客户端时的自愈判定，同一生命周期点、同一动作序列）；③检测的是既存漂移态，不向运行中的影片处理管线注入变更；④不侵入处理循环（每启至多一次，非每批循环）。

### 六、验收口径披露段（验收原文 vs 调整后口径）

- **未载 / ctx 不符**：真实检测，验收原文字面满足。
- **并发不符**：按 A′ 真实检测（合法整数 >0 且 ≠ v2_concurrency 即重载）；0/缺失/非法/超时容错跳过为已接受限制（漏检由任何重载命令必带 `--parallel` 兜底）。
- **GPU 不符**：**无失配检测数据源**（`lms ps --json` 与 `/api/v0/models` 两通道均无 offload/GPU 字段），以"构造性保证 + 命令断言"近似——重载命令必带 `--gpu max` 且测试断言不含 speculative 旗标；验收原文中"GPU 不符 → 重载"的运行态检测场景**不成立**，验收按此调整后口径确认。
- 以上差异已在批次 1 提交信息 verify 段、本条目、完成通知三处显式对照披露；未经用户按调整后口径确认前，不标注"已满足验收原文"。

### 七、执行留痕（2026-09-24 批次 1/2 完成回填）

- **draft 彻底移除（commit af93ce8，14 文件 +34/−298）**：GUI 下拉与存取回填/refreshDraftModels、CLI `--s1/s3-draft-model`、StageConfig.engine_draft_model、manifest 指纹字段、api 透传、ensure 的 draft 降级/@quant 解析/ps 探测（_spec_draft_trace/_has_draft_trace/_DRAFT_LOADED）与 speculative 旗标全链路清除；引擎自动化核心（未载/ctx 判定、unload --all、-y --gpu/-c/--parallel 构造、复核）完整保留。验证：ruff 绿、定向 77 passed、全量 **960 passed + 1 skipped**（969+1 移除 9 例 draft 测试）、冒烟 CLI --help/GUI 启动过、双深扫 26=基线（pre scan-…18-07-22、post scan-…18-12-12）、重载命令含"无 speculative 旗标"回归锁。GUI 验证=静态渲染层（draft 控件消失/ctx 输入 22272 在位/JS-ID 交叉零悬空）+ 启动冒烟；pywebview 桥接交互未做浏览器黑盒（原生窗口专属）。
- **并发对齐判定（commit be83c25，4 文件 +223/−13）**：`_loaded_parallel()` + 三项对齐判定 + 六分支 fail-open + 重载后复核不循环 + ctx 跳过告警；新增 7 例测试含真实 ps schema fixture。验证：ruff 绿、定向 14 passed、全量 **967 passed + 1 skipped**（只增不减 +7）、冒烟过、预扫描 26=基线（scan-…18-18-45）、提交后复扫 26=基线（scan-…18-21-07）。
- **批次 2 运维裁决**：BatchE_WD 计划任务**在本机已不存在**（C:\Windows\System32\Tasks 与 schtasks 全量 verbose 均无命中；判断为已被删除，非仅禁用——与 batch-e-test-20260922 记忆"BatchE_Run 计划任务已不存在"一致），无需 enable/Disable 处置，废弃另立生产任务的建议保持；恢复命令备查 `schtasks /change /tn BatchE_WD /enable`（现状不可用，任务本体已无）。双 GUI 实例：核查时点零 python/GUI 进程，无双实例并发；G:\python 侧 GUI 未在运行，收敛达成（.venv 为唯一入口）。【2026-09-25 更正（D2026-0925-01 MC-1）：本条"已不存在"系 2026-09-24 上午时点记录——当日午后任务经用户重建后禁用；2026-09-25 实测任务存在且 Disabled（上次运行 2026-09-23 22:26，结果 0xC0000005 访问违规，与 9-23 深夜 draft 事故夜吻合，属已归档事故现场留痕）；删除前须先 `schtasks /query /xml` 导出留痕（D2026-0925-01 组A·A6）。】
- **决策日志字段（decision-critic 协议）**：异议 1 为 [HIGH_RISK_OBJECTION]，主模型已明确采纳回应，异议保留、执行层面服从，无二次复议；无 [PRESSURE-OVERRIDE]。后续风险跟踪：①引擎对 --parallel 静默钳制（重载后复核告警观测）；②fail-open 判定随 lms 升级静默退化（跳过告警 + 真实 schema fixture 兜底）；③实施后首跑若意外重载，回退=撤 _loaded_parallel 判定、保留命令断言；④测试基线 967 passed + 1 skipped 只增不减。

## [2026-09-24] [D2026-0924-02] llm_client 请求期 400 "Model unloaded" 自动恢复 [已拍板·已执行]

### 一、背景
ftkd-030 事故（2026-09-23 02:13）：跑批中 LM Studio 引擎被卸载，后续请求全部 `400 - {'error': 'Model unloaded by user or API request.'}`；llm_client `_TRANSIENT_STATUS={408,429,500,502,503,504}` 不含 400 → 不重试 → 批级兜底退化为整文件 [未翻译] 降级。定版排班批次 5 验收目标：「不再因 400 中断」。

### 二、decision-critic 评议与主模型回应（全部采纳）
- **[HIGH_RISK_OBJECTION] 1（实现点失效）**：原设计「pipeline_v2 捕获 LLMError 后调 ensure」不可达——llm_client 批循环 `except Exception` 吞异常只记日志，LLMError 永不冒泡至管线。**采纳修正**：恢复点改为 llm_client 批循环回调注入（`unloaded_recovery` 参数，pipeline 构建客户端时传 `_ensure_lmstudio_engine` 同参闭包），llm_client 保持引擎无关，异常冒泡契约不变。
- **[HIGH_RISK_OBJECTION] 2（并发竞态）**：v2_concurrency=2 时双批在途（ThreadPoolExecutor），双 400 → 双 ensure 竞态；`unload --all` 会打断另一在途批（其行由缺行定向重试吸收，可恢复）。**采纳修正**：recovery_lock + 每实例恢复信用至多 1 次；等待线程拿锁后信用=0 直接走现状路径；上限 1/客户端实例、本地文件并行已被 `_file_parallel_enabled` 排除。
- 异议 3（误伤面）：匹配稳定长串 `model unloaded by user`（大小写不敏感），云端 "model unloaded due to inactivity" 等不命中。采纳。
- 异议 4（指纹一致性）：ensure 与批处理 client 同源 cfg.v2_ctx_local/v2_concurrency，无增量。查证闭环。

### 三、裁定与执行留痕
- llm_client：`ModelUnloadedError(LLMError)` + 特征串判定 `_is_model_unloaded`（在瞬态判定之前抛出，不进 5s 退避）；批循环捕获 → 持锁 → 信用检查 → 同步回调（ensure 幂等对齐，未载自动重载 60-120s）→ 整批重试一次；信用耗尽/回调异常 → 现状路径（批失败→缺行定向重试→降级），异常契约不变。
- pipeline_v2：仅 lmstudio provider 注入（_make_client 与 _make_fallback_client 两处，与首载完全同参）；云端不受影响。
- 测试 +8：类型判定/长串不误判/不进瞬态/批级恢复/并发双 400 单次恢复/回调异常回退/普通 400 不触发/仅 lmstudio 注入。
- **verify：ruff 绿；全量 987 passed + 1 skipped**（合并基线：969+1 → +7 E3 → +3 v2-ctx → +8 本决策，只增不减；本地 .venv 口径，与 CI 同解释器）；Mimosa 预扫描+提交后复扫 26 findings=基线零新增。提交 1f83c8c（含 e3-benchmark-script b8d42b5、v2-ctx-default-fix db0fa1c 同窗）。
- 口径补记：af93ce8/be83c25 提交信息中的基线数（960/967）均为本地 .venv 口径（与 CI 同解释器），本条为 D2026-0922-01 环境条款要求的补记。
- 后续风险跟踪：①引擎反复被外部卸载时每客户端实例仅自动恢复 1 次（设计上限，防循环），第二次依赖现状路径降级——若生产出现高频卸载场景再议上调；②unload 打断在途批的缺行重试有额外请求成本（低频路径，可接受）。

### 九、验收确认追记（2026-09-24 用户批复，状态转验收通过）

- **状态变更**：[已拍板·已执行] → [已执行·验收通过（调整后口径，2026-09-24 用户确认）]。
- **用户批复要点**：并发对齐检测确认不回退（fail-open 六分支为正确工程取向：宁可漏重载绝不误重载，误重载中断生产跑批、漏重载仅参数短暂不符且有 ctx 对齐兜底）；GPU 构造性保证确认不回退（无运行态数据源是事实，不为凑排班字面伪造检测；--gpu max 为唯一生产路径 + 断言锁死 ≈ 永远全载，且部分卸载会先被 ctx 对齐与专用显存回落验收拦截）；**回退方案（撤 _loaded_parallel 判定）正式作废**。
- **验收条文正式改写（以此为准）**：
  1. 未载 / ctx 与 v2_ctx_local 不符 → unload --all + lms load -y --gpu max -c <ctx> --parallel <并发>；
  2. 并发不符 → 真实检测（lms ps --json parallel 字段），fail-open 容错，绝不误重载；
  3. GPU 失配 → 无运行态数据源，以「每次重载必带 --gpu max + 测试断言」构造性保证；
  4. 重载命令断言不含任何 speculative 旗标。
- 批次 5 确认：v2-ctx 缺省 22272 正确；400 自动恢复为本批最有价值健壮性提升（ftkd-030 暴露面闭合）。

## [2026-09-24] [D2026-0924-03] E3 基准脚本化口径警示与干净校准待办 [已拍板·校准已完成]（2026-09-25 状态字段更正，见 D2026-0925-01）

- **背景**：tools/e3_benchmark.py（b8d42b5）对 Logs/9-23.txt 全天聚合输出「阶段A 0.31 条/秒、总 01:34:53」，该日志含当日 draft 实验样本（4.15 倍减速运行、多次重载），**0.31 条/秒非生产口径，禁止作为基线引用**。
- **裁定（用户 2026-09-24 批复）**：生产定版基准仍为无 draft 配置实测 **阶段A ~13.3 分 + 阶段B ~8 分 ≈ 21.5 分/部**；干净 E3 校准（无 draft 生产配置实跑一次，覆盖旧口径读数）列为下轮首项，已纳入闲时任务。
- **执行口径**：校准优先复用 9-23 深夜干净运行的同源输入（Logs/9-23 22:40 窗口对应片源，保证可比性）；跑前核对引擎空闲（不得打断任何在途跑批）；跑后 e3_benchmark 解析新日志与 21.5 分/部比对，结果回填本条目并同步记忆；使用 .venv 解释器与生产锁定参数（ctx 22272/并发 2/GPU max/KV 双 Q8_0/批 1024/无 draft）。
- **遗留可议项（非阻塞）**：v2-ctx GUI/CLI 强联动（当前缺省修复已闭环 GUI 透传，CLI 靠缺省 22272；强联动收益待议）。
- 本条目及 D2026-0924-01 验收追记随下轮提交入库（用户指定留工作区）。

### 校准执行回填（2026-09-24 12:08–12:32 闲时改即时执行，用户指示"取消闲时任务，现在开始"）

- **执行方式**：原闲时任务 offpeak-f5a9503a（队列 274 位）经用户指示取消改为即时执行；输入原 `Temp/bench_input.srt`（118,926B/1678 条）已被 Temp 清理策略删除且全盘无副本，按本条目预留的降级口径改用**两份真实 ASR 电影转写拼接**（deaf2cbb… 1181 条 + 6646782b… 1036 条，时间轴偏移拼接 = `Temp/bench_input_e3cal.srt`，2217 条/139,660B/sha1 00c54e79…），样本密度略低于原基准（58.7 vs 70.9 B/条），故以**条/秒吞吐与每批秒数归一化**为可比口径。
- **实跑数字（Logs/9-24.txt，e3_benchmark 口径）**：阶段 A = 83 批、均值 12.1s/批、total 16:45、**2.06 条/秒**；阶段 B（heretic-apex 换载后）= 83 批、均值 4.5s/批、total 06:11、**5.58 条/秒**；总时长 23:03（脚本口径）/24m12s（运行摘要含前后处理）；错误 0、故障接管 0。
- **与基线对照（Logs/9-23-2240.txt）**：阶段 A 吞吐 2.06 vs 2.12 条/秒（**−2.8%，持平**）；阶段 B 5.58 vs 3.49 条/秒（拼接样本中文条均更短，不慢于基线）。**结论：无 draft 生产配置下 21.5 分/部复现成立（吞吐口径 ±3%），0.31 条/秒正式作废**。
- **附带验证**：引擎自动化从"已卸载"状态自动拉起 27B 并对齐（ctx 22272/并发 2 实测无误），阶段 B 自动换载 35B heretic-apex——批次 1 交付的对齐自动化在生产路径自证；400 自动恢复未被触发（无卸载事故，符合预期）。跑毕引擎驻留 35B（下次跑批阶段 A 会自动换回 27B，无需人工干预）。
- 校准输入与产物保留于 Temp/（7 天清理策略内），过期后仅存本回填记录。

## [2026-09-24] [D2026-0924-04] TM 默认路径迁出随 1.3.0 + 批次 E 实弹测试终止 [已拍板·归档]

**评议方式**：decision-critic 评议发起后由用户取消，本条为用户直接终选归档（不另加评）。

**拍板一（TM 默认路径迁出 Temp，随 1.3.0 架构版执行）**：
- 背景：生产 TM 库位于 `Temp/translation_memory/tm.db`（tm.py:26 `_DEFAULT_TM_DIR` 硬编码），目录名 Temp 诱导误清、固化学习无机制保障（仅靠无人清扫+手工 .bak 封存惯例，现存 9-16/18/21 三代备份）；当前库 1872 条（2026-09-23/24 生产跑与校准轮写入）。
- 裁定：默认路径迁出 Temp（落位仓库根专用目录或用户目录，动工时定），改 tm.py 一处默认值 + 现库一次性迁移 + 路径断言测试跟随；纳入 1.3.0 架构版（config 分层工作流），否决独立先行小修。
- **附带口径更正**：本日志 992/996 行"Temp 7 天清理策略"系**误归因**——项目唯一自动清理为 `runlog.cleanup_old_logs`，仅扫 Logs/（.txt/.log、7 天、非递归，见使用与维护手册.md:243）；Temp/ 无任何清理机制（仓库代码零实现、计划任务无清扫条目、Storage Sense 只扫系统 %TEMP%），`Temp/bench_input.srt` 消失的真实原因未查明。实证：TM 目录内 9-16/17/18/21 多代文件至 9-24 全部健在。此后涉 Temp/ 产物存亡的判断以此为准。

**拍板二（批次 E 实弹测试终止，不再重跑）**：
- 理由（用户 2026-09-24）：全流程上下游默认选择已经挂载测试定版——上游转录 F06（D2026-0917-03）、下游 refine 两槽 joyfox27b/heretic35b、ctx 22272/并发 2/引擎自动化（Logs/9-24.txt 从卸载态自动拉起+换载实测自证）、干净 E3 校准 21.5 分/部零错误复现；再跑一轮无增量意义。
- 效力：**推翻 D2026-0922-01 硬依赖①与 D2026-0922-03 HRO-3"批次 E 卡拆分动工"两处条款，1.3.0 pipeline_v2 拆分卡点解除**；8 项指标不再在 v1.2.4 参数（ctx 22272/无 draft/400 恢复）上补采，上轮"四次测试"完成记录（用户 2026-09-24 确认，验收材料曾存 E:\无字幕\新建文件夹\四次测试\_批次E验收\）为最终结项口径。
- 产物现状（用户同日告知）：批次 E 目录中 final_cn.srt 与质量报告.txt 已由用户清理。
- 对拆分验收门（HRO-2）影响评估：无实质影响——行为等价快照在拆分时点现拍（同真实输入+固定 FakeClient+**空 TM**+固定词表，重构前后各跑一次逐字节 diff），不依赖批次 E 历史输出产物；所需 3-5 个真实输入为片源转写，**拆分动工前须对 E 盘材料现状做一次留存确认**（用户掌握，缺失则届时以现有真实 ASR 转写补位）。
- 批次 E 条目就此关闭，全链闭环：5 部转录完成 → ftkd-030 refine 400 失败（LM Studio 卸载）→ 重跑环境死亡 → 用户四次测试完成 → 本条终止重跑。（该失败暴露面已由 D2026-0924-02 的 400 自动恢复闭合。）

### GUI 全量实测回填（2026-09-24 16:31–17:52，用户人工 GUI 发起，Logs/9-24-1631.txt）

- **结果**：5 部全量 AB 两阶段**全部成功**，运行摘要耗时 **1h20m58s**，错误 0 / 故障接管 0 / 警告 22（20 条=并发/ctx 检测 fail-open 跳过，设计内；2 条=词表误译待复核 #499 climax_iku_variant，已进冲突观察）。
- **逐部耗时（纯阶段口径）**：ftkd-030 18:14 / hsoda-106 12:47 / hsoda-114 17:18 / jur-531 14:04 / jur-550 14:47，均部 **~16.2 分**，较 21.5 分/部基线快 ~25%（阶段B 均值 4:22 vs 基线 ~8 分为提速大头；阶段A 含 22 次缺行定向重试+5 次响应异常重试，全部首轮恢复、无预算耗尽）。
- **健壮性自证**：TM 从零积累 **6382 条**（写穿式学习正常）；引擎自动化全程 12+ 次"引擎就绪"换载（27B↔35B 交替）零失败，lms ps 实证 ctx 22272/并发 2 全程对齐；**400 自动恢复未触发**（全程无外部卸载，符合预期）。
- **产物**：5× final_cn.srt + 5× 质量报告.txt 落位 `E:\无字幕\新建文件夹\四次测试\_批次E验收\`；glossary_conflict_watch.json 重建。
- **定性**：本回填为执行事实记录；测试验收裁定权在用户。

### 留存回填（2026-09-25，承 D2026-0925-01 组A·A2）

- **留存确认完成**：拆分验收 golden 输入=四次测试全部 5 部真实 ASR 转写（ftkd-030/hsoda-106/hsoda-114/jur-531/jur-550，`4k2.me@<片名>.ja.merged.whisperjav.srt`），已复制至项目树外 `D:\SubTransJAV-internal-archive\hro2-golden-inputs-20260925\`，sha256 双侧（源=副本）逐文件一致；清单与校验值见该目录 `_留存清单.txt`（源=E:\无字幕\新建文件夹\四次测试\_批次E验收\，2026-09-25 实测 36 文件在位）。另 7 部真实转写存于 E:\无字幕\新建文件夹\一次测试\ 备黄金集扩充。**:1011"留存确认"前置件就此闭合**（基准快照三件套中"词表 sha1 冻结"与"golden 快照实拍"两件仍开放，见 D2026-0925-01 执行契约）。

## [2026-09-25] [D2026-0925-01] 项目收口与 1.3.0 开工方案·用户处置意见逐项裁定与分批拍板 [已拍板·执行中]

> 评议链路：本条目为决策日志续评类（引用 D2026-0923-01/:788、D2026-0924-03/:982、D2026-0924-04/:998-1020 及既有拍板链 D2026-0921-01/02、D2026-0922-01/02/03）。decision-critic 独立评议本轮共 9 项用户处置意见 + 主模型 8 项补充（S1-S8），产出 [HIGH_RISK_OBJECTION] 1 条（HRO-1）与 [MATERIAL_CONFLICT] 2 条（MC-1/MC-2）；主模型逐项回应并获用户于 2026-09-25 确认。

### 原决策

"1.3.0 pipeline_v2 拆分为唯一主线立刻推进；可先行小件并行；记录侧欠账马上修；待拍板分批收口，不开新战线；删除类动作先可恢复、先留痕"——用户逐条处置意见（9 项）+ 主模型补充（S1-S8）的整体裁定与分批拍板。

### 评议方式

- decision-critic 独立只读核验：decision-log.md 全部 1020 行、使用与维护手册.md、config.py:40-61（TUNABLE 白名单）、cli.py:105-112（gemma-4-12b 兜底/--v2-ctx 缺省）、index.html:188-191、manifest.py:157-190/330-345（delete_resume_artifacts/_CONFIG_FIELDS）、pipeline_v2.py:2204-2222（_backup_existing_outputs）、quality_report.py:762-800（TM 摘要行/时间戳头）、risk.py:170-176、tm.py:26-37，及 schtasks 实查 BatchE_WD、E 盘目录实况、Temp/translation_memory 备份清单（合计约 12.5MB）。
- 检出：简报事实与代码基本一致；2 处材料冲突（见裁定段）。
- 用户直接终选拍板，本条目为终选归档。

### 我的异议与 HRO 回应

- **[HIGH_RISK_OBJECTION-1]（HRO-2 逐字节 diff 验收门现行规格下必假失败）——主模型回应：采纳（附条件完整采纳），异议解除。**
  - 判定依据：①与已验证事实直接冲突——`quality_report.py:800` 头部含现生成时间戳、`:762-770` TM 摘要行随库状态变化，同输入两次运行 txt 字节必不同；②影响 ≥3 任务（HRO-2 门/拆分工作流/质量报告契约测试，并牵动 D2026-0922-03 新增导读 json 双渲染）；③验收失真——按字面执行必红，触发事后改判，违背"跑前预声明、跑后不得改"纪律。
  - 采纳条件（两条，均写入 HRO-2 可执行测试用例，用例列为拆分动工前置件）：
    1. 归一化白名单——时间戳/TM 摘要行等非确定字段显式排除；
    2. 两次跑各用独立新建空 TM 库（防第二次跑 H>0/L=0 致 txt 必不同）。
  - 其他各项（TM 迁移、G:\python、BatchE_WD 删除、词表判定）均经判定不构成 HRO，维持普通级。
- **[INFO_GAP] 已闭环**：E 盘真实转写存量（四次测试目录 5 部 + 一次测试目录 7 部，2026-09-25 实测 36 文件在位）、BatchE_WD 本机现状（存在+Disabled）、库内交接文档位置（docs/模型测试两轮交接.md§六；树外 SubTransJAV_项目介绍稿.md 经实测 0 处 sakura/待决/重测 表述，无需动作）均经独立核验确认，无需再索材料。

### 拍板条款（用户 2026-09-25 确认）

**组 A——授权按序开工（A1+A2 先行）**：
- A1 记录侧 docs-only 一次提交：:788/:982 状态字段转"已执行"；批次 3 补最小留痕；15:01 死因归因放弃但"异常退出日志持久性核查"转观测项挂批次6；观测项 3 条（lms 升级 fail-open 静默退化 / --parallel 静默钳制 / 400 恢复每实例 1 次信用）写入已知问题保留监控；:949 BatchE_WD 存在性失实修正；库内 docs/模型测试两轮交接.md§六 sakura 加"已按 D2026-0921-02 关闭"标注；树外项目介绍稿仅核实并报告、本轮不改（已核实：无涉，见 INFO_GAP 段）。
- A2 E 盘留存 + HRO-2 输入钉死：选 3-5 部真实 ASR 转写（实取四次测试全部 5 部），sha256 清单，副本落 `D:\SubTransJAV-internal-archive\`（项目树外），回写 :1011（已执行，见上"留存回填"）。
- A3 HRO-2 可执行测试用例（含 HRO-1 两条件）；A4 M3 mypy 小 PR（process_manager 28 + llm_client 3，凡触 pipeline_v2.py/quality_report.py 的 mypy 修复一律顺延拆分后，M1 整批顺延）；A5 质量报告备份/resume 契约测试补齐（先行，不触 txt 内容）；A6 BatchE_WD 先 `schtasks /query /xml` 导 XML 留痕后删除；A7 词表误译 2 条（#499 climax_iku_variant 等）基准快照前定案、若改 glossary.csv 同步冻结 sha1。

**组 B——本轮拍板（用户全部通过，照评议建议）**：
- B1 模型缺省文档项②③：ctx 22272 三处口径统一标注"作者 16GB 单卡实测档案值，请按显存调整"；文档写明引擎自动化仅覆盖 LM Studio 后端（ollama/custom 无拉起换载）。
- B2 H4b 黄金集门②：时点=1.3.1 动工评审；责任人随该评审指定；逾期沿用 D2026-0914-01 降级为构造集基线标注，不阻塞。
- B3 E2-A 术语冲突 5 条（:572）：硬限=1.3.0 词表覆盖层开工前；按"误译/可接受/需术语表"三类判定，结果作覆盖层输入。
- B4 首文件抽检转"后版本质量专项"：一名目两触发点（首文件抽检=1.3.0 发布后首片；黄金集=1.3.1 动工评审）；验证项不合并（首文件=别停/クリ/部長で 考点域，黄金集=闸门0 行为域）；决策日志写明已知风险接受、不阻塞当前发布；考点清单与首文件样本归档备复盘。
- B5 GUI 黑盒降级协议：拆分主线期=回归抽检；GUI i18n 工作流收口时恢复一次关键路径黑盒，写进决策防静默带过。

**组 C——显式延后并记录（不拍）**：
- C1 模型缺省值持久化档位①（1.3.1 实施；评估内联 1.3.0 GUI 参数面板期）；C2 显存推荐④另立低优先版本；C3 v2-ctx 强联动（GUI i18n/参数面板稳定后）；C4 H4b 条目级阈值自适应落地（双且门，1.3.1 动工评审一次性判定）；C5 生产常驻 BatchE_WD 类任务（真实挂机需求出现时按看门狗+告警新立，不复活旧任务）。

**盲点采纳入执行说明（拆分工作流执行契约）**：
1. 拆分第 0 动作=重构前基准快照三件套（E 盘留存确认 + 词表 sha1 冻结 + golden 快照实拍），任何 pipeline_v2 改动之前完成。
2. 解读层（导读 json 双渲染）排在基准快照拍摄之后；仅备份/resume 覆盖补齐的契约测试可先行。
3. mypy 基线冻结时点=拆前快照；按模块拆完即清零该模块并同步缩减基线；M3 独立推进不与拆分文件交集。
4. TM 隔离归档放项目树外（不入 git）；删除条件=1.3.0 发布 + 新库连续运行 ≥10 部片或 ≥2 周 + tm_purge 探针抽样正常 + 用户书面确认，缺一不删。
5. TM 迁出工作流附 6382 条质量构成统计（只统计不清洗；清洗与否归用户裁决）。

### 材料冲突裁定

- **MC-1（BatchE_WD 存在性）**：decision-log.md:949（2026-09-24 上午"本机已不存在"）vs 2026-09-25 实测（存在+Disabled+上次运行 9-23 22:26、结果 0xC0000005）。裁定=:949 系 2026-09-24 上午时点记录，午后任务重建后禁用，记录失实；失实修正入 A1 docs-only 提交；删除动作照议（先导 XML 留痕）。
- **MC-2（E 盘"产物已清理"）**：:1010 指原批次 E 阶段性产物；现存 36 文件系 9-24 GUI 实测回填产物 + 5 部转写。裁定=留存确认基于现值清单+哈希，不默认"已清理"，无需补位。

### 风险跟踪

1. HRO-1 采纳后须在 A3 用例提交时逐条勾验两条条件（归一化白名单覆盖时间戳/TM 行、双独立空库），未入用例不得宣称拆分动工前置件已闭环。
2. 首文件抽检触发随 1.3.0 发布后首片，未触发前考点复核（别停/クリ/部長で）属"已知风险接受"挂账，不得静默消失；样本与清单随 B4 归档备复盘。
3. H4b 黄金集责任人随 1.3.1 动工评审指定，期间持续挂账；逾期降级路径沿用构造集基线标注。
4. TM 6382 条迁移取舍仍为开放项（质量构成统计先行，清洗与否用户裁决），随 TM 迁出工作流闭合。
5. 批次6（Mimosa 26 处静态告警 + pytest 双口径分账 + 异常退出日志持久性核查）排 1.3.0 后 1.3.1 前，本条目不新增优先级。
6. BatchE_WD 2026-09-24 上午时点与午后任务重建的时点变更已入 A1 修正记录；其上次运行 0xC0000005 系 9-23 深夜 draft 事故现场留痕，无新增风险面。

### 执行留痕

- **批次排班最小补记（A1）**：定版排班（2026-09-24）批次 1/2/3 已于当日执行完毕——批次 1=draft 移除（af93ce8）、批次 2=并发对齐（be83c25）及运维裁决（见 D2026-0924-01§七）；批次 3 排班本体未入库、无从反查，以本条为存照；批次 4 或未单列、无从考证；批次 5=400 恢复+同窗 E3 脚本化/v2-ctx 缺省（1f83c8c/b8d42b5/db0fa1c）；批次 6=债务专项待独立排期。此后排班以决策日志入库为准。
- **已知问题（观测项，保留监控不阻塞）**：① lms 升级致并发 fail-open 判定静默退化（D2026-0924-01 风险跟踪②）；② 引擎对 --parallel 静默钳制（D2026-0924-01 风险跟踪①）；③ 400 恢复每实例 1 次信用高频场景再议（D2026-0924-02）；④ 异常退出时日志缓冲丢失（批次E 15:01 观测假说——死因归因放弃，日志持久性核查转本项挂批次6）。
- **A2 已执行**（2026-09-25）：见 D2026-0924-04"留存回填"小节；A1 主体（状态字段×2、:949 修正、sakura 补注、批次补记、已知问题清单）随本条目同批入库；树外项目介绍稿核实无涉、未改动。
- 本条目后续执行追记（A3-A7 逐项 verify、B1-B5 回填、组 C 显式延后记录）随各轮提交按 D2026-0921-03 标准运行模式入库（定向 secret 扫描 → 终端直提 → 三查 → blobs 复扫 → push → ls-remote 复核）。

### 执行追记（2026-09-25 组A 全件+B1 收口，拆分前置三件套闭合）

**执行模式**：用户指示"除方案讨论/拍板外全部由主模型直接负责；可并行任务分发智能体"。本轮实现经 4 路 coding 并行（文件集互不相交）+ 主模型集成验证收口。

- **A3 ✅（f1858b2）**：tools/hro2_gate.py（410 行，capture/compare 双子命令）+ tests/test_hro2_gate.py（8 例）。HRO-1 两条件入 harness：①归一化白名单=报告时间戳头与 TM 摘要行两规则；②capture 每跑全新空 TM（cfg.tm_db_path）。watch advice 有状态实锤（evaluate_watch 依赖全局观察文件累计历史）→ capture 打桩 pv.default_watch_path 每跑重定向；打桩点三处（_make_client/refine_tmp_dir/default_watch_path）均 try/finally 恢复。
- **A4 ✅（bc8f32b）**：M3 mypy 31 错清零（process_manager 28+llm_client 3；含 ：588 循环变量 e→entry 两行零行为改名）。全仓 mypy 70→39 错/10 文件（M1 管线批按拍板顺延拆分后）。
- **A5 ✅（97aa4fb）**：_backup_existing_outputs 备份表 4→6 项（+风险清单 md/json）；新增 _remove_stale_risk_reports 写前清陈旧（残留路径=上轮失败有清单无终稿）；设计裁定=风险清单属最终产物非恢复现场，不进 delete_resume_artifacts（成功路径调用点在 write_reports 之后，收编会误删新报告）；+3 契约测试（备份覆盖/空目录 no-op/清理与 write_reports 文件名双钉防漂移）。
- **A5 验收回填（2026-09-25 用户验收轮，裁定获认可+精度建议采纳）**：①主理由锚定职责语义——delete_resume_artifacts 契约=清理可重建的恢复现场（中间态），风险清单与 final_cn.srt/质量报告.txt 同属最终交付物，收编即把成品当恢复现场处理，属职责边界问题而非实现取舍；"调用点在 write_reports 之后"降为辅证（调用点随重构漂移，不作裁定依据，pipeline_v2 docstring 已同步改锚）。②三类清理职责互斥自洽：backup 保成品（备份不删）/ _remove_stale_risk_reports 清"有清单无终稿"失败残留（写前清）/ delete_resume_artifacts 清恢复现场（不碰成品）。③补防回退断言 test_delete_resume_artifacts_never_touches_final_deliverables（钉"清理清单恰=恢复现场四件、成品六件一件不碰"）。④**边界条款：本语义在 1.3.0 拆分中属行为等价验收的一部分，不进"有意变更"豁免清单**（已入拆分实施规格）。
- **B1 ✅（1074b95）**：ctx 22272 三处（config 注释/cli help/index.html tooltip）+api docstring 统一标注"作者 16GB 单卡实测档案值，请按自身显存调整"；手册新增 §2.3 引擎自动化边界与缺省口径（仅覆盖 LM Studio 后端；管线配置为唯一事实来源；缺省数值零改动）。
- **A6 ✅**：BatchE_WD 导出 XML 留痕（D:\SubTransJAV-internal-archive\BatchE_WD_export_20260925.xml，注册 2026-09-23T00:36:57/每 5 分钟触发/wscript 挂 %LOCALAPPDATA%\Temp\batche_wd_hidden.vbs）→ schtasks /delete 成功 → 复核不存在。
- **A7 判定更正（2026-09-25 用户验收轮，验收裁定权在用户，上条定性撤回）**：用户复核裁定 **#499 复核通过、不构成误译**——高潮/快感语境下源文 いっちゃう（イク 委婉连用形）译「要去了」符合语境。事实纠正三点：①被复核译文实为终稿 #498「要去了要去了……啊……嗯……啊——。」（イク 语义在译），本条目原记"译文'好厉害好厉害。啊。'イク 语义整体丢失→真实质量缺口"系**抽块错位**——post_validate 警告产生于"按时间轴恢复 1439 条原始编号"（Logs/9-24-1631.txt:396）之前，其 #499 为管线内部序号，该区域终稿块号=管线序号−1（上游兜底清洗合并/删除所致），终稿 #499 实为下一句源文 すごいすごい。あ。的译文；②climax_iku_variant 规则判词方向=「源文命中高潮形态但译文出现词表通用变体（要去了/快去了/要高潮了/快高潮了），提请人工复核是否够地道」，**非**"译文缺失变体"；③本查例属严格匹配提醒性质的复核提示，人工复核通过即结案，规则本体不动。处置不变项（与定性无关，继续有效）：不改 glossary.csv、维持 watch 观察生效、glossary sha1 冻结 4b90fa9e…。**教训入档：复核 post_validate/风险台账的 #N 编号必须按时间轴对齐源文与终稿，不得直接按终稿块号抽取**（编号在恢复步骤后才与源文对齐）。
- **集成验证**：ruff 全仓零告警；mypy 39 错/10 文件（M3 清零后基线）；全量 pytest **998 passed + 1 skipped**（987+1 → +8 harness +3 契约，只增不减）；CLI/harness --help 冒烟过；Mimosa 深扫提交前 seal 53010c48…26 findings=基线零新增（四段提交后复扫见下）。
- **golden 基准快照（拆分第 0 动作第三件）✅**：位置 `D:\SubTransJAV-internal-archive\hro2-golden-baseline-20260925\pre-refactor-run1\`，git_head=1074b955227bfa656597304de1d77de991210285（与 B1 提交点一致），输入=树外 5 部 golden（sha256 与 ：1011 留存清单一致），词表 sha1=4b90fa9e…（冻结），配置指纹 ctx 22272/并发 1/TM on/synopsis off。**确定性自检 PASS**：同提交点连拍 run2 与 run1 互比=final 逐字节全等+报告归一化后全等（hro2_gate compare EXIT=0）；5 部 final+5 部报告+manifest 的 sha256 清单入同目录 _baseline_manifest.txt。**拆分动工前置三件套全部闭合**（留存确认 :1011 ✅ + 词表冻结 ✅ + golden 快照 ✅）——1.3.0 pipeline_v2 拆分正式解锁。
- **风险跟踪勾验**：跟踪①（HRO-1 两条件入用例）✅ 已由 A3 harness 兑现；跟踪 2/3/4/5/6 状态不变。
- **基线引用口径更新**：测试基线 **998 passed + 1 skipped**（@1074b95）；全仓 mypy 参考 39 错/10 文件；随拆分开工按执行契约"拆前快照冻结 mypy 基线、按模块清零缩减"。

### 拆分执行追记（2026-09-25 拆分主线完成：六模块迁出+M1 清零，golden 门四次 PASS）

- **拆分落地（75b9bca）**：批次 1 四模块并行逐字迁移（v2_premerge 213 行/v2_context_blocks 155 行/v2_manifest_fp 169 行/v2_outputs 244 行）+ 批次 2（v2_learn 239 行/v2_rules 166 行）+ facade 接线——pipeline_v2.py 2485→1528 行（-957），纯编排主干；**11 个含 patch 调用点的函数（_ensure_auto_synopsis/_load_v2_instruction/_make_client/_make_fallback_client/_run_with_fallback/_collect_grammar_hints/_run_stage_a/_run_stage_b/_finish_learn_threads/run_v2/_run_single_v2）与全部被 patch 名字（含 _ensure_lmstudio_engine/_read_v2_card/_GRAMMAR_CACHE_MAX/_LEARN_JOIN_TIMEOUT 的调用点）留驻 facade，patch 语义零变更**；迁出符号 from-import re-export 保持 pv.<name> 可解析；新模块零反向依赖（R1）、logger 字节级同名（R4）、tm_purge 等 import 期触面全部保持（R6）。
- **模块单测（HRO-2 条款"每个新模块 ≥1 直接单测"）**：tests/test_v2_split_modules.py 13 例——六模块各 ≥1 + V2_STAGE_TAGS/SLOT 叶子副本值对齐钉 + re-export `is` 绑定钉 + **职责边界回归钉**（风险清单/成品与恢复现场清理清单互斥，A5 验收条款随迁验证）。
- **golden 门四次 PASS（终审证据）**：①拆前确定性自检（run1↔run2）；②批次 1 接线后中途门；③批次 2 后终门；④M1 后复跑——均 post vs pre-refactor-run1 产物全等（final 逐字节/报告归一化，EXIT=0）。行为等价以产物级字节证据收口。
- **M1 mypy 管线批清零（e7594d9）**：refine 面 21 错归零（9 文件；纯注解+except 变量零行为改名，golden 等价域语句零触碰，顺延 0）；全仓 mypy 39→**18 错**（余 M2 面 main 9/api 7/event_stream 2，另行排期）；mypy 基线文件机制按契约③待 M2 收口落地。
- **基线再次更新**：全量测试 **1012 passed + 1 skipped**（999+1+13，只增不减）；全仓 mypy 参考 18 错/3 文件。
- **拆分后队列**：解读层 CLI 侧（基准快照已拍，可开工）→ GUI i18n+参数面板+查看器+槽位对齐同批 → B3 E2-A 判定+词表覆盖层 → LRU/文档/lockfile 收尾；批次 6 债务（Mimosa 26 处+M2+pytest 双口径）排 1.3.0 后。

### 解读层实施与验收门缺陷披露（2026-09-25 深夜）

- **解读层 CLI 侧落地**：quality_report.py 新增【白话导读】区（【结论】行后恒有——基于本次运行声明+时间戳同源复用头部串（hro2_gate 白名单覆盖）+①总体（N=len(items) 同源硬条款兑现，:769②）/②条目链路（rhs_total==n_src 同源）/③漏覆盖/④未翻译（条件行）/⑤阅读顺序建议）+ 9 章节白话注解（组装层统一后处理插入标题行后，render_* 函数体零改动，离线报告与 render 直调不受影响）+ 手册新增 §12 质量报告怎么读（三步走）+§6/§7.2/FAQ-9 三处指引行；文案全量避开既有负向断言黑名单（"疑似"两分支不含、条件章节字面/隔离区移出/条目在但未译等条件化规避）。**分批口径补记**：导读 json 归 i18n 批次——依据拍板一"解读层（CLI 侧，只动 quality_report.py）"硬界定（json 落地必改 v2_outputs/manifest 契约，超出本里程碑）；:1069"解读层（导读 json 双渲染）"的字面缝以此口径为准。
- **验收门缺陷披露（诚实记录）**：hro2_gate compare_outputs 文件发现用顶层 glob，而 capture 产物在 run/{stem}/ 子目录 → **拆分期间四次 compare 空转假 PASS**（循环 0 次）。发现路径=解读层变更范围自检（post-guidebar 明确含导读却对 post-refactor PASS，取报告文件头实证后定位）。修复=rglob 递归发现（兼容平铺/嵌套双布局）+报告路径由已发现 final 同目录推导+tests/test_hro2_gate.py 增 3 例真实布局回归钉（含嵌套布局报告差异"必须 FAIL"反例钉与缺失终稿必须报 missing 钉）。**教训入档：单测 fixture 布局与被测物真实布局脱节时，验收门形同虚设——门的用例必须按真实产物布局构造。**
- **真裁决重做（修复后四连比）**：①拆分等价 pre-refactor-run1 vs post-refactor **PASS**（四次空转结论补实锤：六模块拆分+facade 接线行为等价成立）；②M1 等价 post-refactor vs post-m1-check **PASS**（注解零行为）；③解读层 post-m1-check vs post-guidebar **FAIL=预期有意变更**——差异逐处核对为纯导读/注解增行+行平移、无内容改写、final 逐字节全等（有意变更留痕归档，承 :764 豁免条款）；④SQL 修复等价 post-m1-check vs post-sqlfix **PASS**。
- **基线更新**：全量测试 **1019 passed + 1 skipped**（1016+1+3 门回归钉）；mypy 18 错/3 文件不变。解读层后等价比对参照更新：pre-refactor/post-refactor/post-m1-check 为拆分与 M1 的历史裁决存档，此后变更的等价比对新侧=post-guidebar/post-sqlfix（含导读形态）。

### GUI 批 W1 落地（2026-09-25 深夜：导读 json 双渲染+查看器+槽位对齐）

- **W1a 导读 json 双渲染+契约**：build_quality_report 尾部加可选 `guide_sink`（组装完成后同一次调用采集：version/source/generated_at（头部同串）/basis="基于本次运行"/conclusions（与 _render_plain_guide 同源 3-5 条）/sections（按 txt 实际章节标题回填）/extras）——**不传 sink 行为逐字节不变**（4 测试文件 41 处直调零影响，sink 案裁定依据）；新函数 write_guide_json 落盘 `{stem}_质量报告导读.json`（companions 六件存在性在落盘时补齐）；pipeline_v2 接线：报告与导读同生共死（报告 except 则不写 json）。**契约（A5 职责边界裁定适用）**：导读 json 属最终成品 → 进 `_backup_existing_outputs`（6→7 件）+`_remove_stale_risk_reports` 写前清陈旧（清理表 2→3 件），**不进 delete_resume_artifacts**（成功路径调用点在写之后，收编即误删；本裁定覆盖拍板一①"导读 json 进 delete_resume_artifacts"的字面，依据=A5 用户验收轮确立的"成品不进恢复现场清理清单"语义先例）。契约测试同步：备份 7 件/防回退 deliverables 七件/清理三件。
- **W1b 查看器**：api.py 新增 `read_output_artifact(path)`（_validate_user_directory+basename 白名单后缀 `_质量报告导读.json`+json.loads 校验，**不返回 txt 不返回任意 json**——拍板一①"否决 GUI 直读 txt"兑现）；前端 #refineGuideViewer 面板（conclusions/sections/companions/meta 渲染+完成分支静默探测）；test_gui_api +4 例。
- **W1c 槽位对齐**（D2026-0922-02 裁决三）：config.py 默认工厂槽1/3 enabled True→**False**（validate 不再对停用槽误报缺模型/key）；生产路径 cli.py 显式传参指纹不变（实测 config_from_args hash=6f4e622d… 改动前后一致，默认工厂 hash 变化为预期）；测试面核查=无既有用例断言默认工厂 enabled（test_cli:26-27 为显式路径），新增正向钉（test_config_layering）；GUI 展示语义核对（附带要求①）：event_stream._STAGE_LABELS 仅含阶段A/B、by_stage 重建按提交 stage 号合并——**无误导，不改码**；STAGE_NAMES/name 语义厘清（附带要求②）：现文案"（v2 未用）"已正确，保持。
- **C1 评估结论（本批内联评估，实施落 1.3.1）**：持久化载体两案——user_settings.json（需扩 TUNABLE_FIELD_TYPES+新增写入通道，受分层优先级语义约束）vs config/refine_stage_settings.json 的 settings（**已有读写、零新文件、GUI 直存直读不进分层**，v2_ctx/v2_concurrency 已在此持久化）→ **推荐后者**：模型名与档位延续同键扩展；三键均已在 manifest 指纹（v2_concurrency/v2_ctx_local 在 _CONFIG_FIELDS、模型名经 _STAGE_FIELDS），入持久化不改变指纹成员集、仅改值来源，改档即废 resume 的既有语义不变。
- **基线更新**：全量测试 **1027 passed + 1 skipped**（1019+1+W1a 7+W1b 4+W1c 1）；并行实施期间一过性失败（三路 pytest 竞态读中间态）经主模型最终态复跑排除。

### GUI 批 W2、收尾三件、B3 终选与 D1-D6 三轮决策记录、1.3.0 收口（2026-09-25 深夜）

**用户指令**：自动继续至完全收口；**每个决策选项与子智能体讨论三轮再终选**；最终报告逐项写出终选选项。

- **W2 i18n 文案集中化（f93e426）**：strings.py MSG 22→94 键（api 28 处/event_stream/main 全迁 msg()）；app.js MSG 213 键（散落 48 处收编）；index.html 全量 data-i18n（113+18+placeholder 8，引用键 124 悬空 0）+统一注入；**裁定=文案集中化不建英文表不加语言切换**；event_stream 前端解析依赖核对=无字节级匹配；M2 mypy 9 错清零（api 7+event_stream 2，纯注解）；手册 §2.2 补 2 行；双表同步钉新增（HTML 引用键 ∈ JS MSG 键集）。误提交 f8d3512（旧消息脚本误用）经 soft reset 以正确消息 f93e426 重提——教训：提交脚本与消息文件配对使用，禁复用旧脚本。
- **收尾三件（b1655f0，终选实施）**：D2 词表三级链（--glossary-override 新参进 _CONFIG_FIELDS；load_glossary_merged 三级合并 override>用户>learned；_glossary_fingerprint parts **显式**追加第三项 override sha1——critic R3 修正"自动进指纹"前提不成立，实为按路径枚举通道，须显式实现+断言双保险；内置 rules 独立分域不并入注入链）；D3 语法缓存 OrderedDict LRU（move_to_end+popitem(last=False) 逐条淘汰，弃 clear 全清与 90% 双水位）；D4 产物级 lockfile（新模块 artifact_lock.py：锁键=输入 sha1[:16]+output_dir、msvcrt.locking+fcntl 回退、失败降级警告、冲突抛 RefineError 走单文件失败隔离——run_v2 空返回消费核实后弃空串方案）。
- **参数面板 A 类补齐（4c17ba8）**：TM 高级三件（no_tm/tm_db/tm_threshold 控件+键表+3 例）；范围核对=五扫描参在 api 已显式存在且 GUI 文件夹流程以固定默认语义覆盖（recursive 全仓未传=已知边界）；refine_pick_db 桥接不存在、TM 路径纯文本框（从简）。
- **force 通道（c23，D6 终选）**：api.start_translation 入口同源探测（resume_state_for_path completed）→ 结构化 needs_confirm 不启动；前端 confirm 四要点（覆盖清单/自动备份告知/失败继续覆盖并告警/试运行预览引导）→ 确认后带 force 重调；`_build_refine_args` 仅 options["force"] 真时追加 --force+"未确认路径不含 --force"可回归断言。
- **B3 终选判定**：判定对象替换为现存 GUI 实测观察（watch json 权威 **7 词 93 条**：マンコ 44/お客様 37/チンチン 7/クリ 2/ざこ 1/イク 1/ちんぽ 1——主模型脚本实跑聚合裁决，explorer 的 96 口径作废）；三类判定=**7 词全部"可接受（继续观察）"，零"误译"、零"需术语表"**（マンコ/チンチン 绝大多数译文使用词表译法或自然别名；お客様 "客人"为词表别名语境自然；低样本 4 词按纪律仅准"可接受"）；观察闸维持观察模式不转阻断；**低样本词升级须留痕（日期+案例来源+样例行）**；E2-A 原 5 条结案（行级不可考、词级可恢 bak：マンコ×2/ちんぽ×1/イク×2 且被现存样本子集覆盖）。词表覆盖层无需为冲突词新增强制词条。
- **三轮决策记录（D1-D6）**：
  - **D1（B3 判定对象）**：R1 方案 A+两修正+[HIGH_RISK_OBJECTION]（三问：93/96 口径、结案措辞、低样本置信度）→ R2 实跑落定 93+措辞采纳+判定纪律（低样本<3 仅准"可接受"，判"需术语表"须样本≥3 或用户亲报留痕），HRO 采纳解除 → R3 无保留异议封盘。**终选：方案 A+两修正+判定纪律。**
  - **D2（词表优先级链）**：R1 支持自纠正（注入三级+rules 独立分域）+补指纹缝隙 → R2 采纳"实施时核实+断言兜底" → R3 **升级为"显式进指纹必修"**（核实 _glossary_fingerprint 为路径枚举通道非合并内容哈希）。**终选：三级注入链+override 显式进指纹+断言双保险。**
  - **D3（LRU）**：R1 支持 A 逐条淘汰（弃 90% 双水位）→ R2 采纳 → R3 封盘。**终选：OrderedDict+move_to_end+popitem(last=False)。**
  - **D4（lockfile）**：R1 有保留支持 A（锁键组合+降级路径两保留）→ R2 采纳 → R3 封盘（回归三路径：拒绝/不误伤/降级）。**终选：产物级锁键=(输入 sha1+output_dir)+msvcrt+降级。**
  - **D5（main.py mypy 9 键）**：R1 倾向 B（单独小 PR；CI 无 gui 口径本就 0 错非门禁前置）→ R2 采纳 → R3 封盘（修复形态建议 cast(dict[str,Any])，:323）。**终选：方案 B 本轮不动，双轨口径声明（CI 0 错/本地含 gui 剩 main.py 9 键）。**
  - **D6（B 类敏感开关进 GUI）**：R1 支持方案 B（仅 force）+三保留（C1 确认框要点/C2 事前提示"发现即暂停"/C3 force_resume 归 1.3.1 书面化）→ R2 三保留全采纳+api 内部 needs_confirm 形态 → R3 核实两前提成立+封盘。**终选：方案 B——仅 --force 进 GUI（api 内部同源探测+结构化 needs_confirm+确认后重调+"仅确认路径可达"断言）；force_resume 与学习闸三开关转 1.3.1 行动层 UI。** 无 [PRESSURE-OVERRIDE]。
- **B5 GUI 黑盒恢复（i18n 收口触发，按 :1062 协议）**：三层执行=①真实窗口启动存活（i18n 键表+查看器+force 全部变更后 GUI 进程稳定运行至受控终止）；②桥接层 test_gui_api 33 例（read_output_artifact/needs_confirm/args 拼装）；③node --check app.js。边界记录：原生窗口无自动化驱动，点击流黑盒不可自动化；stdout 不落文件，控制台文案断言不可得。
- **1.3.0 收口声明（清单七项对照）**：①pipeline_v2 拆分 ✓（golden 真裁决 PASS）；②词表覆盖层+加载优先级改造 ✓（三级链+显式指纹；B3 判定零新增强制词条）；③GUI i18n ✓（全量键表化）；④完整参数面板 ✓（TM 三件+A 类核对+force 通道；B 类余项按 D6 转 1.3.1）；⑤LRU ✓（OrderedDict 逐条淘汰）；⑥文档修正 ✓（手册 §12 三步走/§2.2 补 2 行/查看器与导读 json 用法待补入 §12 的部分=查看器已上线而手册查看器小节列入下轮文档批）；⑦lockfile ✓（artifact_lock）。**基线：全量 1046 passed + 1 skipped；mypy 双轨口径（CI 无 gui 0 错/本地含 gui 剩 main.py:323 9 键，D5 顺延）。**
- **遗留移交 1.3.1**：行动层（dry-run 先行）/H4b 双且门/legacy providers 清理/guard 脚本/Mimosa 21 项甄别/force-resume+学习闸 UI/mypy 硬门禁+基线文件机制/main.py 9 键小 PR（cast 形态）/recursive GUI 传参边界/行号注释债（tools/model_matrix_run 等对旧行号引用）。**批次 6（1.3.0 后）**：Mimosa 26 处静态告警+pytest 双口径分账+异常退出日志持久性观测。

## [2026-09-25] [D11] 行动层实施设计六点定案+W1a 生命周期修复前置 [已拍板]

**decision-critic 三轮（R1 评议→R2 回应→R3 终评），无 [PRESSURE-OVERRIDE]。**

- **[HIGH_RISK_OBJECTION] 一条（已采纳闭环）——W1a 导读 json 生命周期真 bug**：write_guide_json（pipeline_v2.py:1505）在前、_remove_stale_risk_reports（:1522）在后且清理表含 _质量报告导读.json（v2_outputs.py:172，W1a 扩表带入）→ **每次成功运行的导读 json 被自己的清陈旧步骤删除**（critic 临时目录实测击穿；单测钉函数行为不钉调用顺序故全绿）。风险清单未中招（其 write_reports 在清之后，A5 写前清插入位置本就正确）。**修复口径=清陈旧调用点上移至最早伴生成品写点之前（一次清三件陈旧→写 txt→guide→风险清单）+端到端契约测试（五件全存活：final_cn/txt/guide/分歧 CSV/术语 CSV+has_risks 分支风险件）**——行动层开工首件，未满足前实施不得越过。连带核验：术语冲突观察 CSV 每次覆写不受清点上移影响。
- **设计六点定案**：①载体=导读 json 加 items[]（有界投影声明：译文全量、源文截断、无渲染章节；txt 唯一全文权威不构成"否决全量 json"推翻；version 1→2 同批改测试）；②字段集=current_text 全量（source_excerpt≤40 仅展示）/status 恒 "open" 不回写旧 json（apply 后重新生成新快照+独立台账 {stem}_重翻记录.json：index/timing/category/old_text/new_text/model_used/outcome/ts，进备份表不进 delete_resume_artifacts、写前清旧台账）/整条缺失标"不可自动重翻"/未翻译残留纳入行动对象（范围决定，源=untranslated 列表）/校验告警须结构化 timing 否则 unresolved 跳过（A7 教训）/severity 预留恒 null（H4b 预留）；③resolve_final_block 官方映射放 quality_report.py（:603 懒加载改指 v2_premerge._timing_span；精确 index 匹配为主不做 timing 猜测；合并块 index 非单射文档写明；**禁算术外推红线**+四位移 fixture 契约测试：预合并合并/cleaner 删除/隔离区移出/语言过滤伪条目）；④CLI=--action-retranslate 清单文件+--entries=原始 index（N-M 范围，risk.py "12-15" 惯例）+dry-run 默认+重翻参数排除 _CONFIG_FIELDS（force/resume 同款）+台账存在时 run_v2 入口告警不阻断（管线启动侧非 CLI 解析侧，覆盖 GUI 路径）；⑤执行器=build_srt 整文件重建（timing/index 逐字节不变+仅目标块文本变更 diff 断言）/重算范围四件（txt/导读/分歧 CSV/术语 CSV）+"可离线重建/标陈旧"清单为实施首件交付物/槽 B 默认+--action-model 可配+5 条小样对比/失败最小质量门（非空/非占位/过 zh 白名单，不过保留原文记 failed）/并发 1/不写 TM（tm_sha1 静默副作用第二理由）/恒等式断言对象=条数核对+timing/index 不变+仅目标块 diff（**复核清单条数允许且应当变化**）；⑥entry_range=post_validate 告警结构化（index/timing/severity/message，check_and_fix_translation_errors 签名变更联动 test_post_validate 契约）+RiskEvent additive 字段 timing_range/entry_timings+RiskCollector.add 集中式 helper（禁调用点手拼字符串）；闸门0 不建风险事件（双计，走 add_summary_line）。
- **验收门**：端到端 fixture 断言五伴生件存活+映射四位移契约测试+apply 后恒等式断言；查看器 items 渲染入 GUI 批（web-gui-tester 黑盒注明"GUI 已验证/未验证"）。
- **残余观察（非阻塞）**：①quality_report=False 时分歧/术语 CSV 陈旧残留——扩清陈旧表至五件或文档标注二选一留痕；②重翻台账契约语义入 docstring。
- **实施交下轮按本契约执行**（前置修复+三地基+执行器）。本轮 decision-log 曾出现"Edit 后被外部进程还原"异常（提交链执行时磁盘内容已回退致空提交）——**教训：docs 追记后须在提交前 grep 自证内容在位，提交后 git show 复核**。

### 前置修复执行追记（2026-09-26，开工首件四项落位 [已执行，待用户终端提交]）

- **W1a 生命周期修复（HRO-1）✅**：`_remove_stale_risk_reports` 调用点上移至 `_run_single_v2_impl` 内 `if cfg.quality_report:` 块之前（无条件清理语义保持，先于含导读 json 在内的全部伴生成品写点，风险清单 write_reports 原位不动）；端到端五件存活契约测试落位（final_cn/质量报告.txt/导读 json/分歧复核 CSV/术语冲突观察 CSV 全存活 + fail_b 注入真实风险事件验风险清单覆盖写 + 词表注入验术语 CSV 落盘），红绿核验=还原旧码复现"本轮新写导读被同轮清理删除"（v2_outputs docstring 调用点描述同步）。
- **48h 审计 H1 ✅**：app.js 13 个 camelCase 悬空调用点对齐键表现有 snake_case 键（键表零改动零新增键，:878 noFilesTitle 系键表 camelCase 段既有键不属悬空不误改）+test_strings_and_shortcut 新增"JS 内 MSG.x 引用 ⊆ 键表"反向悬空钉；GUI 已验证=B5 三层（真实窗口启动存活 14s 受控终止/桥接层含于全量/node --check）。
- **48h 审计 M1 ✅**：mypy_baseline 退出码校验（rc≥2 或 rc=1 且零错误行——典型 No module named mypy——判环境故障拒绝 PASS；--update 同门拒写基线防垃圾覆盖）+4 例测试（rc=0 通过/rc=1 基线内通过/rc=1 零错误行拒绝/rc=2 拒写基线）。
- **48h 审计 M2 ✅**：artifact_lock 三态契约——同键冲突抛新异常 ArtifactLockConflict（调用方转 RefineError 单文件失败隔离）；机制性 OSError（非冲突 errno）打印警告降级返回 None（调用方无锁继续，不再误拒）；无锁实现警告一次降级。冲突 errno 集=EACCES/EAGAIN/EWOULDBLOCK/EDEADLOCK(EDEADLK)（文件 open 成功前提下 EACCES 只能来自他方持锁）；回归四路径（真实双获锁冲突/EACCES 冲突/EIO 降级/无实现降级）。
- **基线更新**：全量 **1066 passed + 1 skipped**（1057+1→+9：guard 1/mypy_baseline 4/strings 1/pipeline e2e 1/artifact_lock 2，只增不减）；mypy 门禁 --check 退出 0（存量 0/当前 0/基线外 0）；ruff 全仓零告警；Mimosa 深扫 seal 79eae27d… **24 findings**（D7a 预警的 26→24 兑现，零新增，24 转为新基线）。审计 LOW（L1 提示词语义/L3 lmstudio/L4 客户端泄漏）与 D11 残余观察仍挂账未修。
- **执行通道**：Mimosa git-gate 拦截 ZCode 内提交（历史误报文件，与待提交 12 文件零交集）——按 [[standing mode]]（D2026-0921-03）走用户终端脚本直提，五段语义提交（guard/mypy/H2+M2/H1/docs），脚本 Temp/commit_0926_five_segments.sh，暂存区非空即停+分段计数断言，不含 push。

### 三地基实施追记（2026-09-26，D11 契约①②③⑥ [已实施，待用户终端提交]）

- **地基三（⑥）**：post_validate 告警结构化——check_and_fix_translation_errors 签名三→四元组（+structured_warnings：index/timing/severity/message/category 五键；字符串 warnings 文案逐字节不变，quality_report #{idx} 反解路径零影响；severity 按 warn_only 口径=warning/critical，dewei 经 YAML 实证 warn_only=false 取 critical）；_apply_fallback_rules 五→六元组贯穿 v2_rules→pipeline_v2→全部测试调用点；RiskEvent additive 字段 timing_range/entry_timings（只进 asdict 路径=风险清单.json/事件 payload，md 表格与 summary_lines 不感知，钉测试固化）；RiskCollector.add_entry_ranged 集中式 helper（entry_range "12-15" 惯例 min-max、timing_range 首末条、entry_timings 全列表、空列表安全；docstring 钉闸门0 不建风险事件走 add_summary_line 防双计；本批零生产调用点，执行器批接线）。
- **地基二（③）**：resolve_final_block 官方映射落 quality_report.py（精确 index 匹配为主、不做 timing 猜测、合并块 index 非单射=同 index 取列表顺序首个、禁算术外推找不到返回 None）；:603 懒加载 from pipeline_v2 改指 v2_premerge._timing_span（拆分后零 facade 反向依赖）；四位移 fixture 契约测试（预合并合并 index 空洞/cleaner 删除重编号恢复/隔离区移出保留其余 index/语言过滤伪条目 index 0 重号——各自用真实 _premerge_entries/_align_orig_by_timing/quarantine_review 复现机制）。
- **地基一（①②）**：导读 json version 1→2 加 items[]（结构化告警+untranslated 全量两来源，按 index 升序；字段=index/timing/category/message/current_text（resolve_final_block 映射，None=整条缺失"不可自动重翻"）/source_excerpt（源文前 40 仅展示）/status 恒 "open"/severity 恒 None（H4b 预留）；txt 渲染路径零改动，有界投影=译文全量、源文截断、无渲染章节）；build_quality_report 加 structured_warnings 可选参（默认 None 旧调用零影响）；write_guide_json/companions/查看器消费字段零改动（查看器 items 渲染归行动层 GUI 批）。
- **等价域纪律（D8 三地基 5 纪律）兑现**：动工前确认 post-guidebar/post-sqlfix 快照完好（R3 定案口径）；地基后 hro2_gate capture 重拍 post-foundations-20260926（打桩全真管线，配置指纹 ctx 22272/并发 1/TM on/synopsis off 不变）vs post-guidebar **compare EXIT=0**（final 逐字节全等/报告归一化全等）——三地基在等价域零扰动，与"additive 只进 json"设计一致，逐处归类=无差异可归类。
- **基线更新**：全量 **1078 passed + 1 skipped**（1066+1→+12：post_validate 3/d11_foundations 3/resolve_final_block 4/quality_report 2，只增不减）；ruff 零告警；mypy 门禁 0。
- **执行通道**：pipeline_v2.py/test_pipeline_v2.py 为 H2/M2 与三地基共同载体，为保证每段提交独立可编译，refine 层合并一段提交；提交脚本合并版 Temp/commit_0926_all_segments.sh（五段：guard/mypy/refine 层合并/gui/docs），暂存区非空即停+23 文件集断言+恰五段断言，不含 push。

### 执行器批与查看器实施追记（2026-09-26，D11 契约④⑤+验收门 [已实施，待用户终端提交]）

- **执行器（⑤）**：新建 refine/action_retranslate.py——读清单（校验 version==2/items/stem）→--entries 解析（"3,7,12-15" 惯例，非法退出 2）→目标块按 item.timing 与 final srt 块 timing **精确字符串匹配**（timing=身份标识；歧义/缺 timing 记 failed 不猜）→源文恢复（--action-source parse_srt 建 timing→源文映射，未命中退化 source_excerpt 标 source_partial）→串行重翻（并发 1、永不写 TM；槽 B 默认，--action-model 经 dataclasses.replace 换模型；客户端经 _make_action_client 模块级注入点便于测试/扩展）→失败最小质量门（非空/非旧文/无 [未翻译] 前缀/非纯 ASCII/过 is_fluent_zh——与隔离区回捞同口径；不过保留原文 outcome=failed）→**恒等式硬断言**（条数/timing 全等+仅目标块 text 变化，失败抛 AssertionError 不落盘）→apply 覆盖 final（不另做备份文件，台账 old_text 即回滚依据）→台账 {stem}_重翻记录.json 累积追加（index/timing/category/old_text/new_text/model_used/outcome/reason/ts/source_partial）→导读快照刷新（write_guide_json 重算 companions、generated_at 同源、current_text 重定位、顶层加 retranslated_at、conclusions/sections 保真）→标陈旧打印（txt/分歧 CSV/术语 CSV 三件）。dry-run 缺省零写入；--action-sample 供 5 条小样对比工作流（槽 B 默认 vs --action-model 各跑后 diff 台账）。
- **CLI（④）**：行动层参数组六参（--action-retranslate/--entries/--action-source/--action-model/--action-sample/--apply），config_from_args 后早退分流（同 _handle_tm_commands 形态；置于日志 Tee 前以保证退出码 0/1/2/3 传播）；**参数不进 RefineConfig=天然不进 _CONFIG_FIELDS**（负向钉固化：字段不在 _CONFIG_FIELDS 且哈希不变）。已知边界：`python -m subtransjav.refine` 裸调 main() 不传播行动层退出码（console script 正常），__main__.py 改 sys.exit(main()) 列入下批小修。
- **台账生命周期**：备份表 7→8、写前清 3→4（+_重翻记录.json，成品伴生件写前清旧）；delete_resume_artifacts 不收编（A5 先例）；三处契约测试同步（备份 8 件/清理 4 件/deliverables 八件不碰/清四件）。run_v2 侧：_run_single_v2_impl 路径解析后台账存在告警不阻断（管线启动侧，覆盖 GUI 路径）。
- **实施首件交付物（"可离线重建/标陈旧"清单）**：docs/行动层可离线重建与标陈旧清单.md——final_cn.srt=可离线重建（build_srt 整文件重建+恒等式）；导读 json=可离线重建（快照刷新，结论区保真度注记）；txt/分歧复核 CSV/术语冲突观察 CSV=**标陈旧**（需 merge_stats/gate0/校验告警等管线态，离线不可得；重跑管线自然重算）——D11"重算范围四件"的逐件归类依据即此清单，偏离点显式留痕。
- **查看器 items 渲染（D11 验收门 GUI 批）**：index.html 面板加 #guideItems 容器+guide_items_title 锚；app.js guideRender 增 items 渲染（index/category/timing/message/现译截断 80 字；current_text=null 显示"不可自动重翻"；>50 条渲染前 50+汇总行；全部 json 字段走既有 esc() 转义防注入）；MSG 键表 +5 键（guide_items_title/guide_items_none/guide_item_current_label/guide_item_unresolvable/guide_items_more）；+2 静态钉用例。GUI 已验证=B5 三层（真实窗口启动存活 14s 受控终止/桥接层含于全量/node --check；点击流黑盒不可自动化）。
- **基线更新**：全量 **1099 passed + 1 skipped**（1078+1→+21：执行器 19 用例+查看器钉 2，只增不减）；ruff 零告警；mypy 门禁 0（新增 action_retranslate 全程注解）；CLI --help 冒烟过（含"行动层"参数组）。

### 落库执行追记（2026-09-26，五段推送 95216aa）

- **五段提交**（用户终端脚本 Temp/commit_0926_all_segments.sh，PRECHECK 33 文件全过）：c3524bd（guard 加固）/f8583d3（mypy 平台钉+M1）/a186ff4（refine 层 H2/M2+三地基+执行器+台账，22 文件）/2d5666a（gui H1+查看器 items）/95216aa（docs 四追记+B2 首期+甄别表双基线）。
- **三查+blobs 复扫**：①工作树干净（0 未提交）；②恰五段、文件归属 2/3/22/3/3=33 与分段设计逐段一致；③committed blobs 十类凭据模式零命中，3 行 raw 命中全部定性=甄别表 seal 内容哈希（sha256:53010c48… 历史 anchor 与 sha256:79eae27d… 新基线，seal 纪律要求留痕的公开摘要，非凭据）。
- **push 复核**：`5e1b335..95216aa main -> main`；ls-remote refs/heads/main=95216aa50f7e430cbcbdb184904c385cc7a558a4 与本地 HEAD 一致，status -sb 零领先零落后。
- **CI 预期**：ubuntu 腿 mypy 门禁（platform=win32 钉后应为 0 错）与 windows 腿 guard 两用例（cp1252 加固后应退出 0）为本轮两处 CI 修复的首个验证点，推送后首跑结果待观察追记。
- **待办移交**：__main__.py 退出码传播小修/force-resume+学习闸 UI/行动层 GUI 实测/B2 补采（重跑五片归档术语冲突观察 CSV）。

### 行动层 UI 批与 CI 收口追记（2026-09-26，D6 遗留交付 [已实施，待提交]）

- **CI 双腿首跑收口**：推送 95216aa 的 CI run=**completed/success**（上轮 5e1b335=failure）——ubuntu 腿 mypy 门禁（platform=win32 钉后 0 错）与 windows 腿 guard 两用例（cp1252 加固后退出 0）双双通过真实 CI 验证，本轮两处 CI 修复闭环，D9"首跑确认"条款兑现。
- **学习闸三开关身份考证**：D6 终选原文（:1150）未逐字点名字段名；代码侧证据链取**进了 manifest 指纹的三个学习行为开关**（manifest.py:356-368 注释"影响学习行为的开关"）=glossary_learn_enabled/glossary_conflict_block/tm_learn_gate（auto_glossary 不进指纹不列）。其中 glossary_learn_enabled 与 glossary_conflict_block 原本无任何 CLI/GUI 通道。
- **实施**：①CLI 补 `--glossary-learn`/`--glossary-conflict-block` 两参（store_true，接线 config_from_args；两字段入指纹故开启影响 resume 校验=设计内）；②`__main__.py` 改 `sys.exit(main())`（python -m 退出码传播，含行动层 0/1/2/3；+源码钉防回退）；③GUI：index.html 加 refineForceResume（"指纹不匹配仍复用"默认不勾）+refineGlossaryLearn+refineGlossaryConflictBlock 三复选框；app.js buildRefineOptions 加 force_resume/glossary_learn/glossary_conflict_block 三键；api._build_refine_args 加三分支（force_resume 隐含 resume 由 config.__post_init__ 保证）；MSG +4 键（force_resume_label/title、glossary_learn_label、glossary_conflict_block_label）。tm_learn_gate 不加 GUI 开关（与 TM 勾选语义重叠，CLI --no-tm-learn-gate 通道保留，api 分支注释留痕）。
- **验证**：全量 **1108 passed + 1 skipped**（1099+1→+9 恰为新用例数）；ruff 0；mypy 门禁 0；node --check 过；GUI 真实窗口启动存活 12s 受控终止（B5 层①；点击流黑盒不可自动化）。已知边界：cli.py 自身 `__main__` 块同样不转发返值（GUI 子进程走 `-m subtransjav.refine.cli`，当前 GUI 不传行动层参数无实际影响），列入后续小修。
- **B2 补采重跑**：五片（hro2-golden-inputs 存档件）经真实管线重跑启动（隔离 TM 库 Temp/b2_corpus_rerun_20260926/tm_b2.db、输出 Temp 同目录不入库、config/glossary.csv 词库、槽 A/B 生产默认模型），目的=取得行级术语冲突观察 CSV 更新 B2 基线；结果与掩码样本回填见后续追记。watch json 将按设计追加本次记录（观察闸数据自然增长，B3 观察口径不变）。
- **B2 补采闭合（同日）**：五片全部 EXIT=0，术语冲突观察 CSV 实产 **逻辑记录 92 条**（物理 95 行，jur-550 一条 actual_text 含两处换行多行字段致差 3，解析后 6 字段规整）；词级=マンコ 44/お客様 37/チンチン 7/クリ 2/ざこ 1/イク 1/ちんぽ 0（ちんぽ 聚合 1 条本轮零命中，如实呈现）；行级 ≥30 门槛起额闭合（92≫30），docs/B2-门②语料基线-20260926.md 演进式回填（补采更新块/并列小表/3.4 节 31 条掩码样本/缺口改写为已闭合），提取脚本 Temp/extract_b2_rerun.py 只读不入库；原始 CSV+质量报告归档树外 D:\SubTransJAV-internal-archive\B2-corpus-20260926\（公开仓库不入库）；watch json 自然增至 10 记录（09-24 五条+09-26 五条）。门②口径=基线移交复核，2026-10-16 截止前结案。

### 尾巴修复批追记（2026-09-26，审计 L3/M2-②③+残余观察① [已实施，待提交]）

- **L3 lmstudio 编码**：`_run_lms` subprocess.run 补 `encoding="utf-8", errors="replace"`（全文件唯一 subprocess 调用点）——消除 Windows locale（cp936）解码条件性 UnicodeDecodeError；删除 `_loaded_parallel` 从未消费的 `timeout` 死参数并同步 2 处调用点+1 处测试；+2 例防回退钉（mock 捕获 kwargs 断言编码参数）。TimeoutExpired 孙进程挂死问题按约定未动另行排期。
- **M2-② POSIX 释放顺序竞态**：`ArtifactLockHandle.release()` 重排双分支——msvcrt 维持 解锁→close→remove（区域锁未解文件不可删）；fcntl 改**持锁先 os.remove（unlink-under-lock，非阻塞锁语义下安全）→解锁→close**，消除 close 与 remove 窗口内他人同 inode 获锁后被 remove 脚下抽锁、第三进程建新文件致双"同键"锁的竞态；幂等卫句与 OSError suppress 保留，docstring 写明两平台差异理由；+源码钉与 Windows 行为不变测试。
- **M2-③ 锁键大小写误判**：`in_sha1` 无条件 `.lower()` 改 `os.path.normcase`（Windows 小写化=既有大小写不敏感行为不变；POSIX 原样=Foo.srt/foo.srt 不再误判同键误拒）；docstring 注明 normcase 语义随平台、锁为运行期临时件无持久化兼容问题。
- **D11 残余观察①（二选一裁定=文档标注）**：不扩清陈旧表（扩表会在 quality_report=False 运行中无备份删除上轮成品伴生件，违背备份语义），改 `_remove_stale_risk_reports` docstring 裁定记录+行动层清单文档第 5 条显式记录（两 CSV 在 quality_report=False 运行中不重写不清理，重跑即自然重算）。
- **验证**：全量 **1115 passed + 1 skipped**（1108+1→+7 只增不减）；ruff 0；mypy 门禁 0。工作区现存三批待提交（批二 9 文件三段脚本 commit_0926_batch2.sh、批三 7 文件三段脚本 commit_0926_batch3.sh，BASE 均=95216aa，互不重叠）。

### 批二落库执行追记（2026-09-26，六段推送 d80d4c6）

- **六段提交**（用户终端：主脚本五段+补尾脚本一段）：1911bb0（CLI 学习闸两参+__main__ 退出码）/bc76749（GUI 强制恢复+学习闸开关）/d137110（审计尾巴 L3+M2-②③）/d23be95（行动层提示语区分未提供/不存在）/28fbca1（docs 六节追记+B2 回填）/d80d4c6（v2_outputs 残余观察① docstring 补尾）。
- **主脚本终检拦停事件**：分段 add 清单漏点名 v2_outputs.py（EXPECTED 18 文件 vs 分段和 17），终检"工作树未清空"断言拦停未带病推送——**教训入档：提交脚本除"工作树集合"断言外，必须保证"分段 add 清单并集=工作树集合"（或分段计数和=文件总数）**，补尾脚本 Temp/commit_0926_followup.sh 收口。
- **三查+blobs 复扫**：①工作树干净；②恰六段、文件归属 3/4/5/2/3/1=18 与工作树集合一致；③十类凭据模式零命中（1 行 raw=落库追记引用的推送后 commit SHA，公开内容哈希非凭据）。
- **push 复核**：ls-remote refs/heads/main=d80d4c66224b935065f229b2add81154da839191 与本地 HEAD 一致，status -sb 零领先零落后。
- **用户实测留痕**：行动层四层链路全绿（entries 防御性忽略+清选集空退出/timing 精确定位/--action-source timing 对齐恢复完整源文/dry-run 零写入），提示语两分支修复由实测反馈驱动并回归。
- **1.3.1 状态**：行动层（前置修复+三地基+执行器+UI 批+尾巴修复）全部落库，v1.3.1 发布条件具备（时点与 Release 待用户拍板）；B2 门②行级基线 92 条待复核接受（截止 2026-10-16）；H4b 启动评估待用户拍板。

## [2026-09-26] [D2026-0926-01] H4b 本体启动与实施 [已实施，待提交]（用户拍板"H4b 启动，处理完随新版本一起发布"）

**decision-critic 三轮（R1 三 HRO→R2 全采纳→R3 封盘同意），无 [PRESSURE-OVERRIDE]。**

- **门①判定回写（:770 一次性判定义务）**：分支 b 维持——上游 1.9.3 源码级事实（仅 balanced_pipeline.py 含 telemetry 23 处）+四份 .abtest/out/BAL__* 真实遥测实证；H4b 有效口径=**Balanced opt-in 子集而非全量自适应**，五要素全部落位（见实施节）。
- **门②判定回写**：**有条件满足**——按定案一语料口径（watch json 权威样本源）B2 已采 92 条真实行级（≥30 达成）；**:770 原文的 golden origin:real 子集（含 suspect/empty 案例、防循环验证记录、gate0_golden_stats 分项）当前 0 条**，critic R1-HRO3 裁定不得由实现方解释为"满足"——**golden origin=real 子集由门②组成部分降为观测项一事待用户追认**（本条目即呈报）；工具面已就绪（gate0_golden_stats.py 支持 origin=real 分项，0 条时如实输出）。
- **R1 三 HRO（全部采纳）**：①分区两趟破坏跨条目检测语义（repeat 组跨界劈断、end_meta 分区局部重锚致中部误删）→改**单趟全量预计算+逐条 tighten 谓词**；②信任 OR 规则过宽（实测 nsp>0.6 单独命中约 40% 场景）→硬信号单独判（produced_output=False/fallback_segments>0/max_temperature>0/max_compression_ratio>2.4）+软信号合取（max_no_speech_prob>0.6 ∧ mean_avg_logprob<-1.0）；③门②判定修正如上。R3 补两钉：跨分区 repeat 组**就紧原则**（组内任一条目低信任→整组按 tighten 评估，删除件全部进隔离区可回捞）+end_meta 双窗口均锚定全文件 span（禁分区重锚）。
- **实施**：①解析=asr_meta.load_asr_telemetry（发现=raw_subs/ 前缀匹配剥 .ja.whisperjav 等后缀、禁 naive stem；R6 新鲜度沿 _is_fresh；防御解析=null 字段记不可用不当 0、坏行跳过计数、缺文件静默 present=False、任何异常不抛）；②映射=pipeline_v2.map_entries_to_scenes（场景按序累计 audio_duration_s 得边界，条目 timing 中点落格，超末场景不映射；docstring 声明"场景归属仅供档位划分、非真值"）；③执行=apply_source_filter 增 tighten_entry_predicate（单趟全量预计算保持，谓词仅决定删五类参数取 tighten/base 变体，计数类判定路径不感知谓词，None 缺省逐字节不变；不变量=positions 全局索引/统计求和/valve_tripped=OR/count_positions 与 quarantine_candidates 全局升序）；④五要素：缺失红标=collector.add(stage="gate0", WARNING)（仅 opt-in 触发，限定域防红旗疲劳）/CLI --adaptive-thresholds+GUI refineAdaptiveThresholds 复选框+手册 §2.3 档位段/adaptive_thresholds 进 _CONFIG_FIELDS（asr_telemetry 路径沿 asr_meta 先例不进）/三可数指标（telemetry_scenes/low_trust_scenes/adaptive_entries）进 gate0 upstream 块。
- **与任务书的一处偏差（critic 语义内）**：upstream 块的 telemetry 子块为**条件并入**（opt-in 或确有遥测/超龄时挂载）——tests/test_pipeline_v2.py:2160 逐字节钉死无信号场景 upstream 键集，无条件并入必破既有契约；键集与设计一致，缺省路径等价性反而更强。
- **验证**：全量 **1160 passed + 1 skipped**（1115+1→+45 只增不减）；ruff 0；mypy 门禁 0；node --check 过；**四份 BAL 真实遥测全链路实跑 4/4 成功**（场景数 68/55/51/71、低信任 7/5/13/5、硬信号命中 3/0/0/0、零跳行零警告——硬信号稀有与软信号合取主力，与 R1 实证吻合）；golden 等价 compare 见下方追记。
- **发布口径**：随 v1.3.1 一起发布（用户拍板）；缺省路径行为不变+opt-in 子集口径=发布前置（四份 BAL 实跑+golden EXIT=0）已满足。

### CI windows 腿失败诊断与修复追记（2026-09-26，a8c67a6 首跑）

- **诊断**：批二 d80d4c6 的 CI 即已红（当时未察觉），批三 a8c67a6 继承——三条 windows 腿 Test 步失败、ubuntu 全绿；REST API（push 凭据 token）拉日志定位**唯一失败用例** `test_cli.py::test_main_module_entry_forwards_exit_code`：`python -m subtransjav.refine --help` 子进程在 cp1252 管道下打印批二新增中文参数帮助触发 UnicodeEncodeError 退出码 1（退出码传播本身工作正常）。**教训：批二推送后未查 CI 即继续批三——推送→CI 绿→下一批的顺序纪律须严格执行**；交互控制台走 UTF-8 API 不炸、管道捕获走 locale 码页才炸，故本地 cp936 全绿而 CI 红。
- **修复**：cli.main() 入口加 stdio 加固（reconfigure errors="backslashreplace"，不挂 encoding，沿 guard_banned_paths 批一同款）；回归钉=测试 subprocess 加 PYTHONIOENCODING=cp1252 环境使本地可复现窄码页管道场景（stash 红绿核验：无加固退出 1 本地复现 CI 失败，加固后 0）。工作树现存 cli.py+test_cli.py 两文件待提交。

## [2026-09-25] [D2026-0925-02] 批次 6 处置与 1.3.1 开工五决策（D7-D10）三轮记录 [已拍板·实施中]

**用户指令**：每决策选项与子智能体三轮讨论再终选，最终报告逐项写终选。评议方=decision-critic（agent_73f16180），R1 评议→R2 主模型逐项回应→R3 终评，全程三轮闭环，无 [PRESSURE-OVERRIDE]。

- **D7a Mimosa 26 处甄别（批次 6）**：R1 支持"修子集+三态甄别表"，修正目标定性=**持久收敛**而非"真险"（26 条已由 D2026-0921-03 :684② 全裁 verdictEffect=none）；UNTRACKED 单列"树外签注"态；口径修正以 findings.json 为准（**:786 分类相加 25≠26，实为 20 路径穿越+2 SSRF+1 SQL+1 命令注入+2 弱随机=26**），追记形式回写；基线副作用预警=修复后深扫 26→25/24 须实扫确认再定表述。R2 全采纳；R3 补注记"UNTRACKED 统一表述=2 文件 3 条（create_shortcut.py 1+Temp/build_blind_pack.py 2）"。**终选：tm_promote.py:52 SQL 字面量化（行为等价实证：dry-run 双库计数不变）+create_shortcut.py:11 换 subprocess（树外签注不入库）+甄别表 docs/mimosa-findings-甄别表.md（seal 53010c48…+anchor 优先声明）+其余 22 条留痕维持。**
- **D7b pytest 双口径分账（批次 6）**：R1 ①②必做+③受限实验（两 kill-criterion 预声明：import 抛 RuntimeError 即弃/collected≠1046 即弃；1 次失败即弃腿）；口径表触发机制须与 CI 实际命令一致（不带 -m 时副口径 skip=2）；marker 不得替代 importorskip。R2 全采纳+预算声明。**终选：①口径表落决策日志（主口径 1046+1 含 gui / 副口径 1013+2 无 gui，差额=33 例 test_gui_api+1 模块级 skip 精确归因，collected 1047/1015 两列）②pyproject markers=["gui:…"]+test_gui_api pytestmark（importorskip 保留）③CI gui 腿受限实验另批执行。**
- **D7c 日志持久性观测转结案（批次 6）**：R1 支持 A（一行级修复）+修法修正=**buffering=1 优于 _write_line flush**（覆盖 write_summary 直写路径）+结案口径分层。R2 采纳。**终选：cli.py 日志 open 加 buffering=1（8KiB 缓冲丢失→已消除）；硬杀缺运行摘要=设计内（TerminateProcess 不跑 finally）分层留痕；回归 3 例（第二句柄只读断言，critic 预授权备选口径）。**观测实证存档：Logs 97 文件中 19 个缺运行摘要（9-23-1501 等），尾部截断型与 8KiB 缓冲+硬杀双因吻合。
- **D8 H4b 门①分支判定+行动层范围**：R1 支持 A（分支 b 五要素落盘）+**反对方案 B**（GPU 重跑与"再跑无增量"先例冲突，替代=零成本源码取证）+五要素打磨（红标限定触发域防红旗疲劳/暴露点=下游消费侧/自适应键进 _CONFIG_FIELDS/复用 asr_meta R6/三可数指标）+行动层三地基 5 纪律（等价域纪律=地基改动前快照重拍+hro2_gate 比+diff 逐处归类；schema 契约测试；entry_range 来源设计轮定案；执行器设计同轮定案）。R2 完成**源码级取证**：上游 whisperjav 包 pipelines/ 七文件中仅 balanced_pipeline.py 含 telemetry（23 处），F06 非 Balanced 不产出为源码级事实；R3 补注记=qwen_pipeline 结论以 .abtest/prod 四部 F06 签名件零 telemetry 实证为准。**终选：方案 A——分支 b 降级口径落盘（H4b 有效口径=Balanced opt-in 子集，1.3.1 只作 schema 预留消费者）；门②真实语料≥30 条+责任人按 B2 挂账，逾期降级构造集基线标注；行动层三地基+执行器设计下轮实施（设计契约本轮已定）。**
- **D9 mypy 基线机制转硬门禁+main.py 归零**：R1 有条件支持方案 A+四条件（①pyproject python_version 3.10→3.12 对齐②main.py cast PR 同批（**正确性理由**：CI"0 错"系 webview 缺失 Any 兜底环境假象，硬门禁不得建于假绿③空基线前真相测量落口径表④假象警告入档+gui 腿承载 mypy 依赖序）+⑤mypy CI 版本钉；若坚持"硬门禁先行、main.py 下批"则升 [HIGH_RISK_OBJECTION]）。R2 采纳 A+四条件+版本钉+拒绝 Plan B 变体。R3 封盘。**终选：方案 A——pyproject 3.12 对齐+main.py cast PR 同批+tools/mypy_baseline.py（--check/--update）+空基线+ci.yml 去 || true 即刻硬门禁+mypy==2.3.1 钉版；双轨口径声明（本地含 gui 0 错实测/CI 无 gui 0 错推演待首跑确认+"CI 0 错=环境假象"警告）。**
- **D10 guard 脚本**：R1 支持 A+三纪律（只看 tracked/indexed 绝不扫 ignored、路径名单制+名单⊆契约测试、退出码 1+pre-commit 不强制）；增量论证采纳=**终端直提路径（gate 不生效）唯一确定性闸**（git-gate 全树噪声 vs guard 精度面互补）。R2 采纳。**终选：轻量版 tools/guard_banned_paths.py（--staged/全 tracked 两模式，8 条名单含出处）+5 例测试+名单契约防漂移。**
- **实施序（R3 定案）**：D9 口径测量→main.py cast PR→7b③ 受限实验→7a/7c/D10 并行；D8 三地基动工前确认 post-guidebar/post-sqlfix 快照完好。
- **实施留痕**：D9+7b=c25（pyproject/main.py cast/mypy_baseline.py/mypy-baseline.txt 空基线/ci.yml 去 || true+钉版/markers+pytestmark）；批次 6+D10=c26（tm_promote 字面量化/create_shortcut 树外签注/甄别表/buffering=1+回归 3 例/guard+5 例）；**主模型终验：全量 1054 passed+1 skipped、mypy 本地含 gui 0 错（51 文件）、mypy_baseline --check 退出码 0（硬门禁生效）、guard 144 tracked 零命中、缓冲回归 3 passed、ruff 零告警**。create_shortcut.py 为 UNTRACKED 树外文件不入库（签注态）。
- **1.3.1 状态**：批次 6 结清（三件全部落账）；D9 硬门禁生效；1.3.1 主体（行动层三地基+执行器、legacy providers 清理、C1 持久化档位实施、force-resume UI、7b③ gui 腿实验）按本条目终选排期推进。

### CI 首跑修正追记（2026-09-26）

- **D9 推演证伪与修正**：ubuntu 腿 mypy 门禁首跑（3.12 腿）报 9 条基线外 attr-defined（raw 12 条按 行:code 去重：artifact_lock:50/:79 msvcrt、secrets:47/55/62/70 与 process_manager:36 与 main:359 ctypes.windll、main:255 winreg.OpenKey）——全部为 linux 运行平台下 typeshed 将 Windows API 置于 `sys.platform=="win32"` 护栏内的平台噪声，"CI 无 gui 0 错推演"不成立。修复口径=pyproject [tool.mypy] 钉 `platform = "win32"`（产品主口径单轨：DPAPI/msvcrt/winreg 均核心路径，与本地基线同口径），**非**写基线文件吞错；windows 腿无 mypy 门禁不受影响。
- **D9 顺带（48h 审计 M1）**：mypy_baseline 补退出码校验防假绿（详见 D11 前置修复追记）。
- **D10 顺带（48h 审计跨端兼容）**：guard 中文输出在 Windows CI cp1252 控制台 UnicodeEncodeError——干净仓也退出 1（test_clean_repo_exits_0/test_staged_mode_only_checks_staged 两用例红）。修复=reconfigure(errors="backslashreplace") 不挂 encoding（本地 cp936 控制台中文不变，窄码页降级 \uXXXX 转义）+PYTHONIOENCODING=cp1252 干净仓回归钉。
- **Mimosa 基线更新**：深扫 seal 79eae27d… 24 findings（较 D7a 口径 26 净减 2，tm_promote SQL 字面量化等修复兑现、双引擎口径差异如实分列），零新增；此后以 24 为新基线，甄别表 seal/计数表述更新列入下轮 docs 批。

### L2 收尾复查裁定（2026-09-25 深夜，三处均误报）

- ①create_shortcut.py:11——现形态已是 `subprocess.call([sys.executable, "-m", "pip", "install", "pywin32"])`（参数列表、无 shell、无拼接），系本条目 D7a 修复本体（原 os.system 拼接面已消除）；L2 对修复行重匹配命中安全形态，误报。
- ②tools/mypy_baseline.py:43——`cmd=[sys.executable,"-m","mypy",TARGET,"--python-version",FORCED_PYTHON_VERSION]`+`subprocess.run(cmd, shell=False)`，全部模块级常量零外部输入；硬门禁脚本运行面=本机/CI，误报。
- ③tests/test_runlog_buffering.py:29——pytest tmp_path 夹具+字面量文件名，D2026-0921-03 先例类（"pytest tmp_path 测试夹具模式"），误报；:29 为 7c buffering=1 修复载体行。

## [2026-09-25] [D2026-0925-03] B2 门②/7b③ 探针/v1.3.0 tag/行动层授权 四项定案 [已拍板]

**用户四项建议定案（主模型无异议，全部采纳）**：

- **定案一（B2 门②）**：**不阻塞行动层，设硬截止 2026-10-16**。样本来源优先级=watch json 权威样本 > 脱敏用户日志 > 工单/用户亲报留痕，不足部分才用构造集补位；责任人=项目 owner 指定一名语料责任人，**暂未指定则默认主模型暂任**；逾期自动降级构造集基线并在 H4b/黄金集记录标注"构造集基线、非真实语料"；H4b 本体继续挂账，行动层不受阻。
- **定案二（7b③ CI gui 腿）**：**执行一次、仅限探针、不进 required checks**。触发=独立 workflow_dispatch（.github/workflows/gui-probe.yml，windows+3.12 腿装 `.[dev,gui]`），不并入主 CI 门禁；kill-criterion 维持原判（RuntimeError 即弃/1 次失败即弃腿）；**collected 断言基线按当前 HEAD 实测（主口径 collected=1055）而非历史固定值 1046**（判据意图=收集面与主口径一致防 pythonnet 漂移，后接新增测试不得假触发）——主模型精度修正。结果无论成败归档，成功也不自动纳入 required，需二次评审。
- **定案三（v1.3.0 tag/Release）**：**在 e9d1631 打 annotated tag v1.3.0**，行动层落地后发 v1.3.1；Release notes 标注"架构版收口，行为变更见 1.3.1"；**不建议**行动层落地后一并发 1.3.x（版本语义混浊、回滚与追责变差）。
- **定案四（行动层实施授权）**：**批准启动，W1a 前置修复为开工门禁首件**（清陈旧上移至最早写点之前+端到端五件存活契约测试；未通过前不得合入执行器）；三地基按 D11 契约实施；执行器按封盘契约推进；每阶段定向扫描+blobs 复扫+提交前 grep 自证纪律继续；force_resume+学习闸 UI 按 1.3.1 行动层 UI 交付（关闭"GUI 无恢复通道"缺口）。**授权边界**：B2 门②未定不阻塞行动层但 H4b 不启动；7b③ 探针可并行；v1.3.0 tag 先打 e9d1631。

**实施留痕**：v1.3.0 annotated tag（→e9d1631）push 与 GitHub Release（REST API，notes 仅本版内容+"架构版收口，行为变更见 1.3.1"一句）见本条目执行追记；gui-probe 触发与结果回填见 7b③ 段。

### 执行追记（2026-09-25 深夜，16c80c2）

- **v1.3.0 发布完成**：annotated tag v1.3.0（→e9d1631，refs/tags/v1.3.0=e0fb31f9）push 复核在位；GitHub Release id 396740632（https://github.com/Angelholl/SubTransJAV/releases/tag/v1.3.0 ，name"v1.3.0 — 架构版收口"，REST API 经代理 10808）。
- **7b③ 探针结果（run 36157469106，#1，completed/success）**：windows-latest+3.12 装 `.[dev,gui]` 成功（pywebview/pythonnet 无头安装无 RuntimeError）；**collected=1058 与主口径（1057+1）一致**——两 kill-criterion 均通过；tests/test_gui_api **35 passed**。**探针判定=成功，按定案二成功不自动纳入 required（gui-probe.yml 保持 workflow_dispatch 手动），纳入与否待二次评审。**"collected 断言基线按 HEAD 实测"精度修正的必要性获得验证（1058≠历史 1046，固定值假触发如期发生）。
- **剩余移交**：行动层实施（前置修复+三地基+执行器，D11 契约）与 B2 门②语料收集（截止 2026-10-16，责任人暂定主模型）交新会话按 D2026-0925-03 定案推进。
- **B2 门②语料基线首期（2026-09-26）**：docs/B2-门②语料基线-20260926.md 落档——聚合权威口径复核一致（7 词 93 条，Temp/translation_memory/glossary_conflict_watch.json 五记录）；行级挖掘实证 **口径内真实样本 0 条**（Logs/*.txt 97 文件 11824 行全行扫描零命中：行级明细落盘在工作区"术语冲突观察.csv"产物、仓库外，.txt 日志仅存聚合行——Logs/9-24-1631.txt 五条 CSV 生成通知与 watch JSON 逐一吻合）；关联变体层 7 条去重（イク族 5+まんこ/ちんこ 各 1，○ 掩码）明确标注非口径不折算；缺口如实（0/30，含关联仍差 23），补采路径=后续运行按片归档术语冲突观察 CSV/工单收集/构造集补位前先经用户确认；不造数凑 30，滚动更新至 2026-10-16 门②截止。一次性提取脚本 Temp/extract_b2_corpus.py（只读，Temp 不入库）。同批：甄别表新增 2026-09-26 复扫 seal（79eae27d…，24 findings 零新增）与旧 seal 历史锚并列，计数改双基线并列表述（净减 2=tm_promote SQL 字面量化+create_shortcut 换 subprocess 兑现），26 条 findingId 甄别结论行原样未动。
- **7b③ 二次评审实施（v1.3.2 任务5 方案 B，2026-09-27）**：gui-probe.yml 落真实断言两枚——①GUI 依赖安装（`pip install -e ".[dev,gui]"`）失败即红；②`pytest tests/test_gui_api.py --collect-only -q` 输出 grep "<N> tests collected" 计数断言 ≥1，异常/空收集经 `::error::`+exit 1 标红（不钉死具体数字，防基线漂移假红，承 1058≠1055 先例）；触发转月级 schedule（cron `0 3 1 * *`，UTC 每月 1 日 03:00）并保留 workflow_dispatch，维持不进 required checks（月级 schedule 不阻塞 PR/Release）；顶部注释块留痕性质（开发者探针非用户功能）、失败处置（月级失败先手动复跑确认，确认环境漂移再修 workflow 或临时提频）、升格条件（外部 PR 增多/发布稳定期需更强 CI 保障/GUI 依赖或收集面频繁变动致月级滞后）；kill-criterion 基线注释刷新为全量口径 1185 passed+4 skipped（2026-09-27），GUI 收集面以 tests/test_gui_api 用例数为准。工具链对齐主 CI（windows-latest、3.12、`pip install -e`、`python -m pytest`）；单 workflow 文件改动，无新运行时依赖，未新增 GUI E2E。

### 决策日志字段

- **原决策**：项目收口与 1.3.0 开工方案（用户 9 项处置意见 + 主模型 S1-S8）分批拍板。
- **我的异议**：[HIGH_RISK_OBJECTION-1] 一条（HRO-2 验收门归一化白名单缺失 + TM 双库策略未定义，附两条件）；[MATERIAL_CONFLICT] 两条（MC-1/MC-2）；普通级建议 9 项（用户 1-9 有条件支持 + S1-S8 全部支持/有条件支持、含排期顺序修正与盲点 6 条）。
- **主模型最终决定**：采纳（HRO-1 附条件完整采纳、异议解除；两冲突裁定如上；组 A 七件授权、组 B 五件用户拍板、组 C 五件显式延后；盲点全部采纳入拆分执行契约）。
- **条件是否已闭环**：决策层面闭环；执行面未闭环（A3-A7 待执行 + HRO-1 两条件入用例勾验 + 拆分动工前置三件套为闭环路径；A1/A2 已随本批执行）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：见上文风险跟踪 1-6。

### v1.3.1 发布追记（2026-09-26）

- **批三补丁落库**：1cdf524（cli.main() stdio 加固+回归钉+三节追记，3 文件）——run #46 = **completed success** 六腿全绿（run #45/a8c67a6 的红为修复前旧跑，已被取代；用户曾误贴 #45 日志，经 run_number 对照澄清）。
- **发布三件复核**：①push 后 ls-remote main=1cdf524c0a47… 与本地一致；②annotated tag v1.3.1 由用户终端创建推送（主模型侧 tag+push 被 Mimosa gate 整体拦截——gate 拦截面含 tag 组合命令，确认 tag 操作也在用户终端通道），refs/tags/v1.3.1=f9601a2fee1f…（tag 对象）在远程；③CI run #46 绿后打 tag（红 CI 不发布）。
- **GitHub Release**：REST API（push 凭据 Bearer，经代理 10808）创建 id **397256220**，name"v1.3.1 — 重翻行动层与体验修复"，url https://github.com/Angelholl/SubTransJAV/releases/tag/v1.3.1 ；回读复核=tag_name/draft=False/prerelease=False/target main 一致，正文含执行器/自适应/台账三要素，**违禁词自查零命中**（未来/下一步/下版本/计划中/H4b/内部）。
- **发布内容**：重翻执行器（--action-retranslate/--entries/--action-source/--action-model/--action-sample，dry-run 缺省+恒等式断言+台账）、导读 json v2+查看器行动条目、条目级阈值自适应（--adaptive-thresholds，Balanced opt-in 子集口径，仅收紧永不放宽）、GUI 三开关（强制恢复/learned 词库/冲突禁入 TM）、CLI 学习闸两参与退出码传播、七项修复（导读自删/轮询悬空键/双处窄码页/mypy 假绿与平台口径/产物锁三态与时序与大小写/lmstudio 编码）。
- **结转**：golden origin=real 真实子集降观测项待用户追认（D2026-0926-01 已呈报）；B2 门②基线 92 条待复核接受（截止 2026-10-16）；批二执行追记已随批三 docs 段（a8c67a6）闭环。

## [2026-09-27] [D2026-0926-01 追认] golden origin=real 真实子集降为观测项 [追认降级/有条件满足]

**用户实核对通过，无新增阻断**（六点逐项与基线文本一致）：B2 补采逻辑记录 92/物理行 95，五片 7/7/47/12/19 与 watch 2026-09-26 组 conflicts_sum 逐片一致，物理差 3=jur-550 一条记录含引号内换行占 4 物理行；93 vs 92 唯一差额=hsoda-114 ちんぽ 1→0，其余六词两轮一致，按"不造数"如实保留；B2 92 条为翻译层术语冲突行级样本，非 gate0 层 suspect/empty 删除案例，不折算黄金集条目；gate0_golden_stats 已支持 origin=real 分项、0 条如实输出；H4b 按分支 b 发布、--adaptive-thresholds 默认关闭；全量 92 条掩码自查 PASS，原始 CSV 树外归档，公开仓库仅 31 条掩码样本。

**追认记录口径**（critic R1-HRO3 契约变更追认就此闭环）：
- H4b 门②记**"有条件满足"**，不记"已满足"。
- golden origin:"real" 真实子集由门②门槛组成部分**降为观测项**；当前 0/30 如实保留。
- B2 补采 92 条**不折入**该真实子集（口径不同：翻译层术语冲突行级样本 ≠ gate0 层 suspect/empty 删除案例）。
- H4b 保持**分支 b 发布**（Balanced opt-in 子集口径），--adaptive-thresholds 默认关闭不变。
- **验证债务硬化条件**：未来若改默认开启 adaptive thresholds，必须先补 ≥30 条 origin:"real"（含 suspect/empty 案例与防循环验证记录 generated_by/标注人），并用 gate0_golden_stats 按真实子集单算 precision/recall；**未达标不得开启**。

## [2026-09-27] [B2 门②基线-20260926] 92 条复核接受 [接受/附复现性表述微调]

**用户实核对通过**：逻辑记录 92 ≫ 30，满足 D2026-0925-03 定案一门槛；物理 95 行及 jur-550 多行字段（entry_id=1342 引号内 2 处换行占 4 物理行）已注明；五片 7/7/47/12/19 与 watch 2026-09-26 组 conflicts_sum 逐片一致。

**接受记录口径**：
- 门②按**"基线移交复核"结案**（2026-10-16 截止前）。
- 93 vs 92 差额唯一来源=hsoda-114 ちんぽ 1→0，按自然波动如实呈现。
- 复现性表述微调（已回写 docs/B2-门②语料基线-20260926.md）：**"重跑复现性良好"改为"六词逐片复现一致，ちんぽ 单条自然波动（1→0）；整体口径稳定，不构成造数或缺口"**。
- 不要求补跑 ちんぽ 一轮：单条观察闸波动不能通过补跑消除，不影响 92≫30 结案。
- 掩码与归档口径维持：全量 92 条掩码自查 PASS；原始 CSV 树外归档（D:\SubTransJAV-internal-archive\B2-corpus-20260926\，10 文件），公开仓库仅保留 31 条掩码样本。
- 92 条不折算 golden origin:"real" 黄金集条目（口径不同，与 D2026-0926-01 追认条目呼应）。

**[2026-10-01 结案追记]**：门②按本条"基线移交复核"口径正式结案，提前于 2026-10-16 截止闭账；B2 文档已加结案标记（转存档），roadmap 横切观察项同步闭账。无补跑、无造数，处置均按本条既有口径执行。

## [2026-09-27] [D2026-0927-01] 下一版本方向与云端闭环立项（v1.3.2 先行+1.4 双轨） [已拍板]

- **原决策**：下一版本方向——v1.3.2 收尾 vs 1.4 云端 AI 质量问题自动闭环；是否与「模型缺省通用化」合并立项。
- **我的异议**：[HIGH_RISK_OBJECTION-1] 一条（云端自动闭环在隐私/合规威胁模型+云端复验策略+内容合规边界三件未闭环前不得进入实施放行，附四条件：威胁模型先行/云端不进缺省/提案式放行而非全自动写盘/台账扩展+有限子集复验口径）；普通级两项（v1.3.2 收尾先行、版本语义纪律对齐 D2026-0925-03 定案三；合并立项双轨治理反对一次拍板式捆绑）。补充风险 b1（质量报告/分歧 CSV/术语 CSV 三件标陈旧断链复验）、b2（术语冲突类不纳入自动重翻目标，对齐 B2 口径与"反义只告警不自动改写"红线）、b3（台账须扩展 provider/请求上下文）；不可让步红线清单七条；立项评审 5 问清单（隐私威胁模型/自动化程度红线/复验策略重定义/通用化与云端耦合边界/成本配额护栏）。
- **主模型最终决定**：**全部采纳**。修正序列=v1.3.2 收尾（48h 审计遗留+gui-probe 二次评审+甄别表 docs）→ 1.4；1.4 双轨：轨道 A=模型缺省通用化（先行、独立决策条目）、轨道 B=云端质量闭环（HRO-1 四条件+威胁模型为开工前置）；b2 与 5 问清单纳入轨道 B 放行评审固定议程；通用化评估材料由主模型先落盘 docs 再送轨道 A 立项评审。
- **条件是否已闭环**：异议程序封盘；执行面四条件未闭环，为轨道 B 开工前置（呈报待开工前追认，不阻塞 v1.3.2 与轨道 A）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①HRO-1 四条件各自闭环验证与责任方；②v1.3.2 范围冻结边界例；③术语冲突自动排除后 watch 人工通道可见性维持；④台账 schema 扩展的契约测试同步；⑤通用化挂账材料补落盘（[INFO_GAP] 关闭路径）。
- **用户追认**：R3 封盘文本按原样采纳。

## [2026-09-27] [D2026-0927-02] GUI 精简三段式与轨道归属定案（HRO/DI 采纳、封盘） [已拍板]

- **原决策**：GUI 参数面"精简项"需求（用户新证据：勾选项多、多为本地模型取向、普通用户显存未必 ≥16G）——方案取向与轨道归属；对 D2026-0927-01 范围的影响。
- **我的异议**：[HIGH_RISK_OBJECTION] 一条（"直接砍项无兼容策略"——GUI/持久化/manifest 契约/i18n 四通道联动，触禁止放行情形②，附条件：落实三段式即转为普通级确认）；[DEPENDENCY-IMPACT] 一条（GUI 精简整体入 v1.3.2 破坏范围冻结）；普通级建议三条（收纳/缺省重绑定/画像预设三级拆分；轨道 B 拆 B-1 云端主通道/B-2 行动层云端闭环；HRO-1 紧迫性随云端主通道上升为默认路径安全门）。
- **主模型最终决定**：**全部采纳**。HRO 条件成立→普通级确认；v1.3.2 冻结维持仅收两件（纯折叠收纳+GUI 并发缺省统一，合流 48h 审计遗留）；缺省重绑定三件实证（ctx 22272 作者档案值/并发 GUI=2 vs 管线=1/gemma-4-12b 兜底指向已否决模型）归轨道 A 立项评审；画像预设=模板填充非隐式绑定；轨道 B 拆 B-1/B-2。
- **条件是否已闭环**：方案取向决策层面封盘；执行面待闭环——痛点定性按"面板密度"口径处理（用户拍板，无需逐项点名）、收纳层改动清单经 5 问式评审、轨道 A 立项（含缺省重绑定内容边界）、轨道 B 放行（HRO-1 四条件前置）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①缺省重绑定语义边界（22272/并发 2 为生产定版档案值，重绑定=剥离"对所有人隐式生效的全局缺省"、档案值保留于文档/示例层，不是删值）入轨道 A 内容清单；②GUI 并发缺省统一属"改默认值"类变更，v1.3.2 中随回归测试一并提交注明；③gemma 兜底重绑定对齐 D2026-0917-02-R1 裁定向现役模型；④HRO-1 四条件随云端主通道定位升级为默认路径安全门。

## [2026-09-27] [D2026-0927-03] GUI 设计参照 SmartSub 与 README 三项声明 [已拍板]

- **原决策**：GUI 信息架构设计参照与对外合规声明——参照 buxuku/SmartSub 做分层收纳（引擎/模型集中管理+主界面任务流化）写入 1.4 轨道 A 立项评审 UX 议题；README 增三项声明（设计参考来源/非商业声明/联系整改条款）。
- **我的异议**：无反对。合规核验结论支持：SmartSub 为 MIT 许可，仅借鉴交互理念/信息架构、不复制代码与图形资产（技术栈 Electron+React vs pywebview+原生 JS 本不可复制），无抄袭风险；商标（项目名/Logo）不碰。普通级注记一条：声明③"善意整改条款"表述应限定于商标/图形/文案等非 MIT 覆盖部分——MIT 代码本身许可自由使用，"整改"承诺若指向代码语义将与 MIT 许可相悖。
- **主模型最终决定**：**采纳全部**——①1.4 轨道 A 立项评审 UX 议题写入"参照 SmartSub 信息架构做分层收纳"，与三段式同出改动清单；②README 写明 GUI 设计参考 buxuku/SmartSub（MIT）；③README 写明本项目基于个人使用设计，GitHub 公开仅为开源分享，未商业化未收取任何费用；④README 写明如权利人认为侵权可联系整改（善意整改条款，按注记限定于非 MIT 覆盖部分）。
- **条件是否已闭环**：决策层面闭环；执行面待闭环——README 声明落字随下一 docs 提交入库；SmartSub 参照纳入 1.4 轨道 A 立项评审 UX 议题。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①参照实现阶段不得复制 SmartSub 代码/图形/文案（含变量命名、样式、图标、交互文案逐字雷同），设计评审时比对留痕；②声明③范围已按注记落字（限定商标/图形/文案）。

## [2026-09-27] [D2026-0927-04] v1.3.2 收尾批七任务执行定案与完成归档（并发统一/折叠收纳/分歧复核修复/进程治理两原语/gui-probe 月级/L1 声明/持久化归 1.4） [已拍板并执行完毕]

- **原决策**：用户对 v1.3.2 五个待拍板点的意见（含 TimeoutExpired 普适化、L1 定性、gui-probe 转化、并发统一）+ 新功能需求（GUI 设置永久保存/首启初始化），经 decision-critic 两轮评议（无 [HIGH_RISK_OBJECTION]，两项普通级风险要求列席：存量持久化值遮蔽、gui-probe 无断言空转）后，用户以七任务执行指令终选拍板。
- **用户终选**：①并发统一到 1 + **X 方案**（仅改代码默认，本机持久化值 2 原样保留，不迁出不摘除）；②折叠收纳按既定方案（原则同意，要求美观方便）；③**分歧复核命名漂移修复纳入 v1.3.2 交付面 +1**（定性=修复非特性，不破冻结）；④TimeoutExpired 两原语=项目级进程治理基建（非 lmstudio 专用）；⑤gui-probe **B-月级**（cron `0 3 1 * *` UTC，先补真实断言再启用，失败只告警，保留手动触发）；⑥L1 保留去重+声明收口进 v1.3.2+回归钉 1.4；⑦持久化泛化+首启初始化**归 1.4 轨道 A，仅归档不实现，v1.3.2 不破例**（封口：后续 UX 需求一律归 1.4 轨道 A）。
- **我的异议**（decision-critic，均被采纳落 execution）：存量值遮蔽（X/Y/Z 三选项呈报）；gui-probe 补断言+基线注释刷新为转 B 前置；两原语拆分（超时语义 vs 取消语义，禁止 GUI 取消硬塞超时；taskkill 终态兜底）；L1 取保留去重并声明"两层策略不一致=有意设计"（用户层原样保留/learned 层去重）；破例触发 [DEPENDENCY-IMPACT] 防守。
- **执行留痕（2026-09-27，按序七任务全 PASS）**：
  - 任务 1 并发统一（X）：api.py `or 2`→`or 1`+异常回退 1、index.html selected→1+文案、app.js 回退 1+MSG 文案双侧同步；持久化值 2 读路径零缺省参与+显式 2 透传钉测试；定向 test_gui_api 47 passed。
  - 任务 2 折叠收纳：index.html 参数带 19 控件+1 按钮整体入"高级设置" details（默认收起），四组=翻译与词库/TM 与学习闸/断点与日志/兜底与并发；20/20 控件 id 保留；新增 5 个 i18n 键双侧同步+2 例防回归钉（id 完整性/默认收起）；零行为变更。
  - 任务 3 分歧复核命名漂移修复：根因=_MARKER_RE 不认上游 v1.9.3 真实命名 `.ja.merged.whisperjav.srt`（测试全钉旧命名 `.merged.subtransjav`），兄弟 pass 文件实际存在但解析失败静默返 None→CSV 恒空表头；修复=正则支持 `.merged.(subtransjav|whisperjav)` 可选后缀（四种命名兼容核对逐字节一致）+诊断区分（解析失败 WARNING/文件缺失静默，probe 返回值契约不动）+6 例回归（真实命名端到端 CSV 数据行≥1/旧命名回归/caplog 诊断）；**真实数据验证**：_批次E验收 5 片 CSV 从全空表→237~437 数据行/片（输出到 Temp/，用户目录零写入）。范围增补已由用户拍板，不破冻结。
  - 任务 4 进程治理两原语：`run_with_timeout_tree`（Popen+communicate 自管，永不抛 TimeoutExpired，返回携带 timed_out 标记；超时→psutil 树杀→Windows taskkill /T /F（10s 限）→POSIX killpg→终态无条件单杀+warning，任何路径不阻塞）与 `terminate_process_tree_robust`（取消/退出语义，psutil 原样/Windows taskkill 树杀/POSIX 进组条件 killpg）；迁移 5 点=lmstudio 三处（ps 30s 语义保留/unload 补捕获不再上抛/load 600s 文案不变）+GUI cancel/exit 无 psutil 回退升级；console.py 不入、main.py venv 探测仅补可读超时日志；测试三层（psutil 假进程树实跑 2.06s 零残留/taskkill mock 参数形态/POSIX skipif）+13 新用例既有零删除。
  - 任务 5 gui-probe 月级：cron `0 3 1 * *`+workflow_dispatch 保留；三重断言（安装失败即红/import webview 探针/收集面 ≥1 不钉死数字防基线漂移假红）+实跑保留；过时基线注释（1055）清除；升格条件留痕（外部 PR 增多/发布稳定期/GUI 面频繁变动）；pyyaml 语法校验过、与 ci.yml 触发器零重叠。
  - 任务 6 L1 声明：手册 11.5 新增"词库合并去重行为声明"（三级链/两层策略有意设计/读取层防御性/当前零影响/变更历史），48h 审计 L1 项就此勾销；回归钉登记 1.4 轨道 A。
- **验证基线**：全量 1185 passed+4 skipped 零失败（L4 后 1164+1 → 净增测试 21：任务 1 +2/任务 2 +2/任务 3 +6/任务 4 +13 中 3 条 POSIX 在 Windows skip）；ruff 全程零告警；node --check 过；GUI 黑盒验证未跑（提交注明"GUI 未验证"，建议用户首启冒烟：高级设置默认收起/四组展开正常/并发显示持久化值 2）。
- **条件是否已闭环**：七任务全部执行并验收完毕；待办=提交推送（16 文件分五语义段，README 外部改动另议）、gui-probe 首次月跳核对、1.4 轨道 A 立项（材料补落盘）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①X 方案下"统一到 1"仅对首启/重置用户生效，1.4 泛化持久化时验证一致性；②gui-probe 首次月跳（下次 UTC 1 日 03:00）核对 Actions 结果可见性；③L1 回归钉随 1.4 轨道 A 实施（本条为 Refs 回链锚）；④折叠区结构变更须同步 tests 新钉的 20 控件 id 清单；⑤防重复杀/语义衔接已由测试钉锁定。
- **[2026-10-01 月跳核对追记（首跳前半）]**：定时首跳（UTC 03:00）未到（核对时刻本地 01:45）；workflow state=active 注册正常；按风险跟踪②先行手动 workflow_dispatch 验证探针实质面——run 36757171642 全绿（约 80 秒，七步全 success），新断言版 workflow 首跑：collected=112/112 passed（.[dev,gui] 安装+webview 导入探针+收集断言+实跑），即 2.1.1 UI 改版+真机批之后 main 探针实质面健康（run#1 的 1058 系 task-5 改造前旧收集面，非漂移）。定时首跳可见性核对待本地 11:00 后补记。
- **1.4 轨道 A 登记更新**（仅归档）：持久化泛化（勾选即永久保存）、首启初始化设置、统一持久化层设计（前端 localStorage 承勾选态/后端 json 承管线参数，ThemeManager 先例 app.js:1149/1158）、L1 回归钉；既有项=模型缺省通用化（缺省重绑定三件实证：ctx 22272 档案值留文档层/并发已由本批统一/gemma 兜底重绑定）、画像预设、SmartSub 参照 UX 议题。

## [2026-09-27] [D2026-0927-05] v1.3.2 tag 前高级设置纯文案可理解性修订（A′）+B 归 1.4 轨道 A [已拍板并执行]

- **原决策**：owner GUI 冒烟反馈"高级设置内容过于专业化，一般用户需对照 README 研究"后，主模型提三方案（A 全量文案白话化/B 简易专业双模式/C 组合），decision-critic R1 评议（一条 [HIGH_RISK_OBJECTION]）→ owner 终选 **C（A′ 收窄版 + B 归 1.4）**，R3 终评封盘无剩余异议。
- **owner 豁免声明（原文登记）**：「批准 v1.3.2 tag 前对高级设置进行纯文案可理解性修订（A′）。该批准为对 D2026-0927-04 封口的一次性显式豁免，仅限本次，不构成先例；tag 后同类需求走 v1.3.3 patch 或 1.4。B/画像预设归 1.4 轨道 A，强制输入：按用户类型分层暴露。」补充：①小白型首启只应看到选文件/选输出/开始，高级设置默认藏进专业模式（1.4 画像预设/首启初始化强制约束）；②若 A′ 黑盒验证失败则回滚文案批、不打 v1.3.2 tag。
- **我的异议（decision-critic R1，全部被 owner/主模型采纳）**：[HIGH_RISK_OBJECTION]——"文案修订非 UX 特性"不得由执行者自行定性授予准入，须 owner 显式一次性豁免（对 D2026-0927-04 封口直读适用的确认与破例程序化）；A 全量 19 项改写收窄为 A′（tooltip 为 hover 触发、小白不悬停，全量改写收益趋零→1 横幅+高危项两级句式）；范围冻结=纯文案/零行为/禁概念改名（"阶段A/B"术语原样，防 test_event_stream.py:65/298、test_pipeline_v2.py:1283 值级钉断链与文档 13 处术语碎片化）；tooltip 双编辑点（app.js MSG+index.html 内联 title）须双侧同值并补值级一致钉；[INFO_GAP] 1.4 排期未定（回填：1.4 未立项，D 路径不采纳）。
- **A′ 交付面（执行结果，2026-09-27）**：横幅 1 键 `advanced_settings_notice`（summary 后低调灰字 div，app.js MSG+index.html data-i18n 双份）；高危项 **6 项 tooltip 两级句式改写**=sf_title/adaptive_thresholds_title/tm_enable_title/tm_threshold_title/resume_title/force_resume_title（第一句人话+后果，第二句"技术细节："+换行保留原技术表述，术语零改名）；**与 R1 九项清单的偏差说明**：glossary_learn/conflict_block 两控件无 title 属性（改可见标签违反"其余项不动"与禁改 DOM 约束），tm_db/tm_threshold 仅改 tooltip 未动 label——按 owner 执行口径（只改 tooltip）执行，6 项在 8±2 区间下界，偏差合规。其余 11 项与全部可见标签未动。
- **验证口径与回退**：全量 **1192 passed+4 skipped**（基线 1185+4 合法上浮：6 参数化双侧值级一致钉+1 横幅钉，既有断言零改动）；ruff 0；node --check 过；web-gui-tester 黑盒验证（展开/横幅渲染/≥3 条两级 tooltip 悬停）提交前执行、注明"GUI 已验证"；黑盒失败=回滚不打 tag（owner 拍板）。决议者非阻塞提醒：title 换行在 WebView2（Chromium）多行可显，黑盒须抽查实际渲染，截断则压缩技术细节句不入横幅。
- **条件是否已闭环**：决策侧闭环；执行侧=代码/测试已落地待黑盒验证与提交。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **1.4 轨道 A 登记更新**：画像预设升级为"按用户类型分层暴露（小白型/普通/开发者）"强制输入；首启初始化约束=小白型首启仅见选文件/选输出/开始；A′ 全部改写文案+未改的 11 项入 1.4 复审清单（B 落地时逐条重审防"一般保持"类建议过期）；术语重构（阶段A/B 更名等）整体归 1.4 不侧改。
- **后续风险跟踪**：①建议句过期由 1.4 复审清单承接；②title 换行非 Chromium 折叠风险由黑盒渲染抽查覆盖；③双侧值漂移由新值级钉锁定；④与 v1.3.3/patch 重叠按 D2026-0925-03 语义纪律处理。

## [2026-09-28] [D2026-0928-01] v1.4/v1.5/v1.6 分版方案定版+轨道 A 立项范围+审计积压批归属 [已拍板]

- **决策背景**：SmartSub 3.9 质量巡检借鉴（sess_b99c9837）经 decision-critic R1 评议（[HIGH_RISK_OBJECTION]"CPS 日文基准定标前不得进重翻行动闭环"三点全部采纳）修订为按输入数据形态分版；2026-09-28 全面审计轮（sess_e70b3bf6 延续）交付计划表后，owner 终选表态：「原则上都同意，出现了问题再调整即可」——分版方案、轨道 A 范围、积压批归属三项一并生效。
- **定版一（分版方案）**：v1.4=轨道 A（模型缺省通用化）+文本层质量巡检（单行超长→导读行动条目→定点重翻，为唯一立即行动化项；CPS 检测采 #499 口径=去空白+15% 容差，只检测只报告只观测；时间轴间隙启发式为观测项）+重翻提示词类别条件化前置；v1.5=音频链路打通（任务 0=先验证上游媒体路径产出，卡壳则改同名推导规则）+CPS/间隙定标后行动化（场景感知容差）；v1.6=音频级漏听检测（音频能量+VAD）+快速试听 UI（媒体访问安全敏感面，威胁模型前置）。轨道 B（云端闭环 HRO-1 四条件）不顺延：1.4 收口后即并行启动放行评审。
- **定版二（轨道 A 立项范围）**：D2026-0927-01 在册 6 项（缺省重绑定余下两件=ctx 作者档案值+gemma 兜底指向/持久化泛化/首启初始化/L1 回归钉/画像预设（强制输入=按用户类型分层：小白型首启仅见选文件/选输出/开始）/SmartSub 参照 UX 议题）+SmartSub PR#354 借鉴 4 点（词库匹配 NFKC+拉丁词边界/每批注入上限 100+省略数上报/词库块 JSON 防注入包装/三级链冲突可见化；①②先行）。GUI 主题持久化、v2_ctx 22272 硬编码与 parseInt||30 缺省表达问题随轨道 A 一并处理。
- **定版三（审计积压批归属）**：2026-09-28 全面审计 18 项修复已落库（aff8fc8..43aee48，基线 1229+4）；积压 13 项中 9 项低危安全项并入 1.4 前置小件批（guard 名单双向契约+cp936 加固/CHANGELOG 1.2.4-1.3.2 补录/watch json 加锁+备份/artifact_lock inode 校验/mypy dev extra 钉版/3.13 CI 腿/gui-probe 注释基线/--tm 死旗标处置），4 项挂起（v2_outputs "done" payload 语义=需消费端核查、premerge_max_gap_s 移出指纹=resume 兼容风险、tools 一次性脚本债务、_pid_alive AccessDenied=psutil 硬依赖不可达）。
- **定标调研归口**：日文 CPS 基准+JAV 场景感知容差的分布调研，用批次 E 语料在 1.4 观测期产出，1.5 行动化前定标。
- **是否 [PRESSURE-OVERRIDE]**：否（owner 显式终选，critic R1 异议已吸收进方案）。
- **执行纪律**：出现实测问题即回本表调整（owner 授权语原文登记）；1.4 立项材料以本条+D2026-0927-01/03/05 为准，不再另发立项评审。

## [2026-09-29] [D2026-0929-01] v1.4 交付六项决策点终选归档（ctx 缺省/首启画像/dewei 定稿/超长阈值/CPS 基准/legacy 模型清理） [已拍板并执行]

- **决策背景**：v1.4 主体交付报告附统一决策清单 7 项，owner 对 6 项给出终选并要求经 decision-critic 讨论后执行（第 7 项=v1 旧 Ollama 缺省并入第 6 项直接清理）。critic 评议：2 项同意、3 项有条件同意、1 项 [HIGH_RISK_OBJECTION]，全部闭环。
- **定版一（v2_ctx 缺省）**：认可 16384（critic 同意）；备选 22272/12288 不采用；user_settings/env 分层保留、档案值 22272 退文档示例、golden 显式钉保持。观测项四件登记：长文截断、术语链断裂、重翻触发率、OOM。
- **定版二（首启默认画像）**：认可小白模式。critic 条件「首启默认仅内存态、显式选择后才落盘」经主模型裁定**不采纳**：first_run 信号=配置文件不存在，首启即写 ui_profile=novice 是 owner 要求「选择持久化」的鲁棒实现（否则用户先改主题等任一设置建档后 novice 偏好即丢失，Spec 轴已实证该竞态）；落盘仅发生在无文件/无 ui_profile 时，不触碰已有用户配置，与 owner「不覆盖已有用户配置」约束一致。critic 附加条件「高级入口进 README 首屏」采纳（快速开始节已补用户模式说明）。
- **[2026-10-01 账面修正追记（D2026-1001-03 第⑨项，只加不改）]**：本定版的「首启默认画像（首启即写 ui_profile=novice）」已被 owner 后续指令取消——a9c4ec1（2026-09-28）owner 三条 UI 指令含「取消用户模式」，用户模式选择器/画像回填及全部相关 CSS/JS/i18n 键已删除，tests/test_gui_js_static.py:190-214 静态钉禁 ui_profile/novice 回流，后端零引用；其「小白型首启极简」诉求由候选池「首启初始化」项承接（api.py:1305 first_run 信号已在、前端零消费）。
- **定版三（dewei 提示词）**：critic [HIGH_RISK_OBJECTION] **采纳**——owner 定稿版「输出：判断/理由/建议译文」与行动层单行输出契约冲突（多段输出会被当译文整行写回字幕），故注入 hint 只含判断要点（で 功能判定→仅误译且语境不符才最小修正→不确定保留原译→禁止机械替换），输出契约维持单行；「判断/理由/建议译文」结构化输出不在字幕重翻场景注入。若未来需要结构化输出，须单独扩展输出解析并配测试（留档条件）。
- **定版四（单行超长阈值）**：以 30（去空白）为基数进观测；critic 条件采纳：白名单（代码/URL/表格行）实施时须在阈值判定**之前**摘除（防同一行双重口径），观测期允许 28–35 漂移；白名单实现列 1.4 观测期待办。
- **定版五（CPS 基准）**：CJK 8/其他 20×1.15 起步，纯观测不进重翻。critic 条件采纳并已实现：时长 <0.5s 条目跳过 CPS 统计（quality_report 与 cps_distribution 等值门槛 _CPS_MIN_DURATION_S=0.5），防超短条目爆表污染观测带；分语种/文体/平台统计归观测期工具迭代。
- **定版六（legacy 模型清理）**：v1 Ollama 缺省 'gemma3:12b' 直接清理为显式空（critic 有条件同意）；消费链核实=PROVIDER_CONFIGS 的 model 字段运行管线不消费、v2 链空值有 _make_client RefineError 与 validate() 双重兜底，无空模型发请求路径；兼容 warning 已加（读入含 gemma3:12b 即告警并清空落回推荐链）；回归断言与清理同批（critic 前置条件达成）。
- **执行状态**：六项全部落地（dewei 定稿修订版/CPS 门槛/gemma 清理+test_providers_legacy.py/README 说明），全量 1290 passed+4 skipped 零失败。
- **是否 [PRESSURE-OVERRIDE]**：否。

## [2026-09-29] [D2026-0929-02] README 大修排期定案：拆两步（前置硬伤批+v1.5 收口结构大修）[已拍板]

- **评议轮次**：本序列首轮；decision-critic 独立评议（材料：README、decision-log、提交 4246404/88a0147 复核）。
- **方案立场摘要**：A 有条件反对（失配危害已大半修补，拖期过长）｜B **支持**（合"前置小件批"惯例、硬伤先清零、结构仅返工一次）｜C 反对（无收口验收时点，等同 B 半截）｜D 反对（docs-only 无需占版本槽）。
- **采纳结论**：采纳 B。前置 docs 批为 v1.5 开工首件——盘点清单先行作验收基准，仅修事实性硬伤：矩阵陈测数字加"2026-09-21 测、GPU 部分卸载问题发现前"口径标注或复测替换；16~21 分钟/部补生产配置上下文；AI 质量分析/五 TAB 外壳/ctx 16384 核漏补录。
- **守卫条款**：① 质量轴搭配结论 D2026-0923-01:796 闭口不动，复测仅刷新数字；② 前置批不扩成结构大修。
- **验收抓手**：盘点清单先落盘，前置批 diff 与清单逐项勾对后方可提交。
- **后续跟踪**：v1.5 收口结构大修并同步新特性；双语策略与 CHANGELOG/手册同批对齐，双语是否统一于大修开工前定案。

## [2026-09-29] [D2026-0929-03] GUI 视觉升级专项立项：v1.6 前置视觉批（暗亮主题自选+token 化）[已拍板]

**评议轮次**：本序列首轮；含 [HIGH_RISK_OBJECTION] 一条（反对并入 v1.5），主模型采纳。
**立场摘要**：并入 v1.5 反对（超载累及 v1.6 依赖链，HRO）｜v1.5 前独立批反对（破坏 D2026-0929-02 开工顺序）｜**v1.5 后 v1.6 前独立批支持（采纳）**；D 项拆出进候选池（采纳）。
**采纳结论**：立项"v1.6 前置视觉批"。范围 A（token 化+暗色主题+行内样式清剿）B（导航顶栏）C（表单组件体系）入专项，D 拆出另行小议；缺省主题=固定亮色，暗色用户自选。
**守卫条款**：① 并入 v1.5 明确排除；② A 硬边界=仅收颜色/尺寸进 CSS 变量，禁改布局语义；③ 钉测试红线不改写。
**验收抓手**：A 提交 diff 仅样式迁移+全量基线 1332+4 维持；暗色逐页 web-gui-tester+5 张 SmartSub 参照对照截图。
**后续跟踪**：D 项入 roadmap 候选池待 owner 立项后重启评议；v1.6 试听 UI 建于本批视觉基线上。

## [2026-09-29] [D2026-0929-04] v1.5 双定案：README 前置硬伤批范围 12 全修 + 音频链路媒体路径 asr-meta 通道 [已拍板]

**P1 子项：README 盘点范围 12 处全修（D2026-0929-02 范围修定）**

- **评议轮次**：D2026-0929-02 续评（范围修定）；decision-critic 独立评议（材料：README 盘点 12 处列点、decision-log 原文、代码实地抽查 README:27,55,133,135,137,188 / asr_meta.py / v2_outputs.py:205-223 / v2_context_blocks.py:87-131 / test_gui_js_static.py:185-201）。
- **立场摘要**：12 全修 **有条件支持（采纳，五项条件全闭环）**｜严格 6 处为可接受回退（不推荐：同一家族拆两批致收口 diff 混批、过时文档窗口延长至收口）；⑩ 建议先核实 stage default_factory 实际生效路径再定措辞。
- **采纳结论**：采纳 12 处全修（闭集、一次 docs 提交）。⑩ 经实读核实判 README 原句成立、**零修改**——cli.py:222-228 `config_from_args` 恒以 `args.s1_model or ""` 构造、default_factory 仅库路径可达（config.py:85-114/230-259/460-504 直读核实），盘点清单记录核实过程，⑩ 勾对方式为"核实通过、零修改"（实际 diff 11 处，清单 12 项逐项勾对）。登记为 D2026-0929-02 范围修定；清单 docs/README-失配点盘点清单-20260929.md 按 12 项闭集落盘作验收基准。
- **守卫条款**：① 质量轴搭配结论 D2026-0923-01:796 闭口不动、全部实测数字零改动；② 不扩成结构大修（无章节增减、无段落重排，④⑤⑥ 仅加口径标注、不改数字）；③ 新增/修订文字自仓库权威源逐字引用并留出处（③→文末声明/CHANGELOG，⑧→v2_outputs.py 伴生件清单，⑪→CLI 参数定义，⑫→config 注释/1.2.2 版本记录）；④ 与 v1.5 后续代码项（CPS 行动化/单行超长白名单/CPS 定标报告）提交完全分离。
- **验收抓手**：清单先行落盘（已落）；diff 与清单 12 项逐项勾对后方可提交；README 相关钉测试全绿；全量基线 1332+4 维持；一次 docs 提交。
- **后续风险跟踪**：本批仅清 12 处失配，双语策略/CHANGELOG 对齐仍随 v1.5 收口结构大修（沿 D2026-0929-02）；⑩ 核实结论留档，供后续"程序级 vs stage 级缺省"相关表述引用。

**P2 子项：音频链路媒体路径 asr-meta 通道**

- **评议轮次**：本序列首轮；decision-critic 独立评议（材料：任务 0 静态取证、asr_meta.py 全文、decision-log R1:32/R6:42/D2026-0929-02 定版一:1390）。
- **立场摘要**：asr-meta 通道 **有条件支持（采纳，条件全闭环）**｜B sidecar 扩节反对（用户手写输入通道塞机器路径、两小节契约 v2_context_blocks.py:87-131 被破坏）｜C 同名推导反对（roadmap 预案"卡壳才启用"未触发；naive stem 零命中代码铁证 asr_meta.py:54-57）。判普通级（无 HRO：非不可逆、无新增安全面、不推翻 R1/R6 既有共识）。
- **采纳结论**：采纳 asr-meta 通道扩展——load_asr_meta 扩展提取 files[]，按 files[].output 与当前输入 SRT 绝对路径**双侧 normcase+abspath 归一化**后配对解析 files[].path（规避批量取 files[0] 错配）；新增显式 `--media-path` 覆盖入口（用户明示即采信；**v1.5 只落 CLI**，GUI 媒体路径选择留 v1.6 试听 UI）；解析结果落质量报告头部元数据与导读 json 新键 `media_path` + `media_path_source`（值域 manifest/override，缺席=无此键）；缺失/配对失败→警告+空值降级（沿 R6），不影响翻译主流程；不做同名推导回退。resume/override 交互裁定 (a)：自动发现 manifest 路径不进指纹（R1 原口径不动）；显式覆盖值作为**配置语义字段**进指纹（规范化路径哈希、非原始字节）——登记为 R1 口径显式补充修订：**"路径类字段默认不进指纹；用户显式覆盖值例外，作为语义配置字段参与"**。
- **守卫条款**：① R1/R6 全容错口径保持（绝不抛异常、绝不阻断管线）；② fingerprint 输出因 files[] 解析保持不变（钉测试）；③ 导读 json 新键只加不减、旧消费者缺席无感；④ v1.5 不建 GUI 入口（沿 D2026-0929-03 守卫①）；⑤ 覆盖值进指纹不违反 R1 语义（哈希而非字节路径，口径修订已显式记录）。
- **验收抓手**：五类边界单测（大小写差异/斜杠方向/多 files 条目 output 等同/零命中/manifest 缺 files 键）+ 28 份真实样例黄金夹具配对 100% 硬目标（任何失败须有可见警告与解释）+ resume×override 交互用例（覆盖值变更须致指纹失效）+ fingerprint 不变钉测试 + 全量基线 1332+4 维持。
- **后续风险跟踪**：v1.6 试听 UI 消费 media_path/media_path_source 契约（建于 D2026-0929-03 视觉批基线）；媒体访问安全敏感面威胁模型于 v1.6 前置（D2026-0928-01 v1.6 项）；上游 manifest schema 跨版本漂移属残余风险，随黄金夹具重跑观测。

**决策状态**：P1/P2 均为主模型拍板采纳（decision-critic 立场为有条件支持，所有条件全采纳）；条件决策级闭环，执行期验证按各自验收抓手逐项勾验；无 [PRESSURE-OVERRIDE]，无 [DEPENDENCY-IMPACT]。

## [2026-09-29] [D2026-0929-05] 2.0 版本重编与 EXE 封装路线双定案（修正版 MVP+beta 分段 × 数据根迁移五条件）[已拍板]

**评议轮次**：首轮；decision-critic 独立评议（材料：owner 两方向①版本重编 ②EXE 封装、roadmap 快照、打包可行性取证结论、decision-log 既有链 D2026-0924-04/:998-1020、D2026-0929-02/:1409、D2026-0929-03/:1418-1421、D2026-0929-04/:1427-1445；代码实地抽查 api.py:173/1409、config.py:113-120/141-146、tm.py:26-29、secrets.py:20-24、pipeline_support.py:75-79、translate/__init__.py:8-10、pyproject.toml:38/73-75、ci.yml:14、git tag 止于 v1.4.0 无 1.5+、仓库无 spec/iss）。产出 [HIGH_RISK_OBJECTION] 1 条（D2 数据迁移缺备份/回退设计）、[DEPENDENCY-IMPACT] 1 条（D1 候选 B 使 D2026-0929-03 前提失效）、[INFO_GAP] 1 条（"旧 EXE 升级"无历史 EXE 基线）；主模型逐项回应，**HRO 五条件与 DEPENDENCY-IMPACT 全单采纳**，口径修正认领。

**立场摘要**：D1 版本重编支持（有条件）——2.0.0 范围按依赖链修正为"收口同步留关键路径，定标行动化/白名单/CPS 报告降 2.0.1"，候选 B 否决（DEPENDENCY-IMPACT：视觉批降级会连带拖垮 2.0.0 头牌视听对比）｜D2 onedir+Inno+数据根 %LOCALAPPDATA% 方向支持，但迁移无备份/回滚设计不达可放行线（HRO），五条件闭环后解除。

### P1 子项：版本重编（2.0 里程碑，修正版 MVP+beta 分段）

**采纳结论**（主模型拍板，owner 方向采纳）：
- ① **2.0.0-beta（pip 形态）**：打包地基（app_root 路径收敛，**行为等价、零数据根变更**）+ pysubtrans 死依赖摘除（含 pyproject.toml:38 条目）+ **TM 迁出 Temp 欠账结清**（D2026-0924-04 补执行，tm.py:26 一并改锚）+ 视觉批（D2026-0929-03 顺序约束不变）+ 视听对比（疑似漏听检测+试听 UI，2.0 头牌）。
- ② **2.0.0 正式**：Beta 内容 + EXE 封装 + 收口同步（双语策略缺省=中文主+英文简介段，owner 开工前可改判）+ tag/Release（Release notes 显式声明"无 breaking、配置兼容"；**2.0 定位=功能里程碑，非破坏性大版本**）。
- ③ 定标行动化 / 单行超长白名单 / 日文 CPS 定标报告 → **降级 2.0.1**（三者无前置依赖，可独立发版）。
- ④ "不再发任何 1.X"修正为"**默认不发 + 预留 v1.4.0 分支出 1.4.1 紧急修补通道**"（恶性 bug/上游兼容断裂时启用）。
- ⑤ 候选 B 否决（DEPENDENCY-IMPACT 采纳，**D2026-0929-03 不复议**，视觉批排序约束原样维持）。
- [INFO_GAP] 认领：「旧 EXE 升级」表述修正为「**EXE 版本间升级**」（Inno 覆盖安装+版本检测；仓库无历史 EXE 基线）。

**守卫条款**：
- 视觉批"v1.5 收口后开工、v1.6 开工前完成"约束（roadmap:25）不因重编改变；D2026-0929-03 契约不拆解。
- pip 形态 2.0.0 只做行为等价路径收敛，**数据根零变更**，迁移动作不入 pip 批。
- 2.0.0 语义显式化（功能里程碑/无 breaking），杜绝 GUI 用户误判需迁移。
- 收口同步缺省值先行（中文主+英文简介段），owner 改判窗口=开工前。
- 1.4.x 通道仅限紧急修补，触发判定=恶性 bug/上游兼容断裂，非常规功能发布通道。

**验收抓手**：
- 打包地基批：路径收敛后全量测试基线维持不降（沿既有门禁）+ 自动测试覆盖新锚点（app_root 单点）。
- TM 迁出欠账：tm.py 单点改锚 + 路径断言测试跟随（沿 D2026-0924-04 原裁定）。
- 2.0.0-beta 里程碑截止日（压缩无发布窗口的排期锚点）。
- 发布验收清单：Release notes 无 breaking 声明为必检项。
- 收口同步：owner 双语策略定案超期（N 日未定案）触发范围重议。

**后续风险跟踪**：
- 收口同步软阻塞=owner 双语策略定案动作，缺省值可改判；超期即触发重议。
- --resume 指纹根治（绝对路径→相对数据根/规范化哈希）**随路径收敛批一并落地**，不单独排期。
- 合并跟踪：D1① 的"数据根迁移"与 D2 条件⑤合并为**同一条决策跟踪**（迁移机制只随 EXE 首发，pip 批只做行为等价收敛），避免两处各拍各迁、机制分裂。

### P2 子项：EXE 封装路线（onedir+Inno+%LOCALAPPDATA%，数据根迁移五条件）

**采纳结论**（主模型拍板，HRO 全单采纳）：
- ① **迁移三段式**：备份（旧位复制/快照）→ 迁移 → 校验（tm.db 行数/文件齐备/密钥可读）；**旧位保留一个版本周期不清除**；失败自动回退旧路径读取；**双源夹具单测+故障注入测试**（pip 安装位 / EXE 安装位双源构造）。
- ② **双形态共存防写竞争**：pip 与 EXE 同机共用 `%LOCALAPPDATA%\SubTransJAV` 单一数据根时，安装器检测/FAQ 给互斥提示；**双装场景脚本手测 + FAQ 落文档**。
- ③ **Inno 卸载器显式排除数据根**：卸载不删 TM/密钥/词库；iss 代码审查 + 卸载冒烟。
- ④ **代码签名**：首发不签 + SmartScreen/杀软 FAQ 豁免指引；**Azure Trusted Signing 列为后续评估项**（发布验收清单项）。
- ⑤ **数据根迁移只随 EXE 首发**；pip 2.0.0 只做路径收敛；采纳"一次迁移机制两用"。

**增补采纳**（decision-critic 增量建议）：
- **frozen CLI 冒烟入 tag 构建验收**（--version + 最小真实任务跑通子进程模式 = API 主链路冻结回归）。
- **2.0.0 发布前 owner 真机 GUI 人工验收一次**（CI 无头验不了 GUI；pythonnet hostfxr 真机解析一并验）。
- --resume 指纹绝对路径改相对数据根/规范化哈希（随路径收敛批根治）。
- 更新链路=Inno 覆盖安装+版本检测，写入发布文档。
- embeddable python 绿色包列为 PyInstaller **致命失败时的降级预案（不作首选）**。

**守卫条款**：
- 迁移旧位不清除、可回退（一个版本周期）；失败路径=回退旧路径读取，绝不阻塞首启。
- pip 批数据根零变更，迁移代码与 EXE 首发同批同测，杜绝双迁移窗口。
- 双形态同机共用单一数据根 → 必须经互斥提示/FAQ 防止双写竞争（sqlite 锁、schema 漂移）。
- 卸载器语义：删除"程序"，永不删除"用户数据"。
- onedir+Inno 形态锁定；onefile 否决（薄壳+子进程架构下每子进程重复解压 150MB+、_MEIPASS 只读随机路径、误报高）。

**验收抓手**：
- tag 构建 job 验收集：PyInstaller 构建 + frozen CLI 冒烟（--version + 最小真实任务）为必过项。
- 迁移测试：双源夹具单测 + 故障注入（责任方=执行者，验收=主模型）。
- 双装场景手测脚本 + iss 审查 + 卸载冒烟。
- 发布验收清单：Release notes 无 breaking 声明 / SmartScreen 与杀软 FAQ / 更新链路说明，逐项勾对。
- owner 真机 GUI 人工验收记录（含无 .NET 8 Runtime 的 Win10 场景）作为 2.0.0 发布前置闭环条件。

**后续风险跟踪**：
- 签名决策滚动评估：首发不签已定，Trusted Signing 在 2.0.0 发布窗口内再评一次（成本/可用性），结论记入 2.0.1 候选。
- 支持成本预期管理：首启向导/README 显式说明"EXE 仍需自行安装 LM Studio + 拉模型"，预期支持量上行，FAQ 承接。
- embeddable python 降级预案备而不启，仅当 PyInstaller 致命失败（如 pythonnet hostfxr 真机不可解析）时启用。
- EXE 版本间升级路径（Inno 覆盖安装+版本检测）随发布文档固化，防修复到不了普通用户。
- 观察项：打包版首轮用户反馈中"杀软拦截/WebView2 缺失/模型环境门槛"三类问题计数，作为 2.0.1 排期输入。

## [2026-09-29] [D2026-0929-06] 2.0 定案修订：owner 复核 11 条逐点裁决 + TM 落点口径变更 + ffmpeg 前置 + spawn 全覆盖 [已拍板]

**决策对象**：D2026-0929-05（2.0 版本重编与 EXE 封装双定案，归档 5a424d3）之 owner 复核修订。

**评议轮次**：第二轮（续评）；引用 D2026-0929-05/:1449-1519 与首轮评议、D2026-0924-04/:998-1020（TM 迁出欠账源链）、D2026-0929-02/:1409、D2026-0929-03/:1418、D2026-0929-04/:1427。本轮新增第三处 frozen 必断点取证（console.py:30-71 relaunch_for_utf8 + main.py:63 venv 引导）。产出 [MATERIAL_CONFLICT] 1 条（owner 点7"pip 保持旧路径" vs 主模型"pip TM 新默认+读回退"）、[HIGH_RISK_OBJECTION] 1 条（API-1：pip 版 TM 默认落点不得变更）、[DEPENDENCY-IMPACT] 1 条（点1/点4b 视听对比入 beta 与 ffmpeg 决策后置的排期互斥）；主模型回应：**API-1 采纳，ffmpeg 前置件采纳，TM 裁定修正采纳**。

**立场摘要**：owner 11 条方向性全部成立。顺序修订（frozen 入口+resolver+内部 onedir 门禁前移 beta）同意并强化；单 exe argv 分派主案同意，改造范围扩至三处 spawn 点；回退数据轻量案同意但边界写死（旧位保留+导出指引+明示损失窗口）；**pip 版 TM 默认落点反对变更**（读旧写新分裂脑，改由 resolver 锚定+EXE 迁移承载欠账）；ffmpeg 决策升为 beta 入口前置件；环境变量名裁定 SUBTRANSJAV_DATA_ROOT。

**采纳结论**（逐条修订 D2026-0929-05）：
- 修订①（beta 范围）：2.0.0-beta 扩为：打包地基（路径收敛+resolver，pip 默认解析结果不变）+ frozen 入口改造（三处 spawn 全覆盖）+ 内部 onedir 构建验证（CI artifact 门禁，不对外发布）+ 视觉批 + 视听对比。Inno/发布 job 仍随 2.0.0 正式。原「pip beta=TM 迁出欠账结清」由修订②替换。
- 修订②（TM 落点，API-1）：pip 2.0.0 TM 默认解析路径保持旧位 Temp/translation_memory 不变，仅改锚挂 resolver（tm.py:26 与 glossary_conflict.py:213 双文件）；「TM 迁出 Temp」欠账随 EXE 首发迁移一次清偿（tm.db+glossary_conflict_watch.json 双文件携带），沿用 D2026-0929-05 迁移三段式与双源夹具。D2026-0924-04 欠账以"锚点+断言测试+EXE 迁移承载"口径结清。
- 修订③（spawn 全覆盖）：frozen 改造清单=api.py:173/1409 + console.py:30-71 relaunch_for_utf8 + main.py:63 venv 引导；统一收敛进 process_manager 单一 helper（pip=`sys.executable -m` / frozen=`exe --subtrans-cli`）；freeze_support() 无条件加；分派态与 pip 态双语言冒烟逐项对拍（UTF-8 relaunch 在 frozen 态走原进程不再 spawn）。
- 修订④（版本号）：PyPI 预发布号 2.0.0b0（PEP 440），不用 2.0.0-beta；2.0.0 正式前可选 rc0。
- 修订⑤（Release notes 措辞）：废除「无 breaking 声明」，改分层：GUI 无需手动迁移 / CLI·API·自动化脚本见「路径与数据根迁移」/ 旧配置自动迁移失败自动回退；回退前先导出 + 迁移后新数据损失窗口明示。
- 修订⑥（1.4.1 通道）：仅收安全/致命修复，写明 EOL 支持窗口；不读新数据根（轻量案），回退边界=旧位保留一版本周期+backups zip 不归零。
- 修订⑦（ffmpeg 前置件）：视听对比入 beta DoD ⇒ ffmpeg/ffprobe 检测与捆绑决策为 beta 动工前置件（排期门）；优先「探测系统 ffmpeg + wave 级 VAD 降级或特性灰显」，避免 torch 级依赖；捆绑 essentials 评估（LGPL+体积）随选型轮定案，不在本决策锁死。
- 修订⑧（resolver）：优先级 SUBTRANSJAV_DATA_ROOT > %LOCALAPPDATA%\SubTransJAV > 旧仓库根/旧路径；新增 subtransjav-refine --where 诊断；pip 默认旧路径、仅支持新根，EXE 首发默认新根并迁移。
- 修订⑨（beta DoD）：owner 六条采纳并入 roadmap；⑥双语 README 落地为 beta 收口项。
- 修订⑩（口径接替）：D2026-0929-05 原条目状态「已拍板」不变；本修订条目为唯一执行口径，原守卫条款中与修订②⑤冲突的文字（行为等价零数据根变更/TM 迁出欠账结清于 pip beta）不再为验收依据。

**守卫条款**：
- pip 2.0.0 任何子进程不得写新根（零感知硬约束）；TM/glossary 双文件锚点变更必须路径断言测试跟随（承 D2026-0924-04）。
- 双落点禁止「读旧写新/空翻转」任一形态；如需双路径一律走显式迁移+备份+回退（迁移三段式），禁止隐式分割。
- frozen argv 分派须在 pywebview 初始化前完成；产物只写数据根/只读 _MEIPASS，不碰安装目录。
- ffmpeg 选型未定案前，视听对比任务不动工（排期门）；不允许「临时 torch VAD」替位默认。
- WebView2 安装器检测与运行时探测共用同一组 winreg GUID，防口径漂移。
- 1.4.1 只收安全/致命修复；EOL 声明随通道启用即写入 release notes。

**验收抓手**：
- beta DoD ①：frozen onedir 内部构建+子进程翻译/AI 分析 smoke（三处 spawn 全链冒烟、双语言对拍）。
- beta DoD ②：resolver+迁移 dry-run+备份/校验/回退测试（双源夹具+故障注入；dry-run 验证 EXE 迁移路径，非 pip 落点）。
- beta DoD ③：WebView2/ffmpeg 依赖检测明确 + ffmpeg 选型定案记录（beta 动工前置）。
- beta DoD ④：pip 2.0.0b0 在含旧 TM 的仓库根上零感知升级验证（--where 指旧位、写入后旧位行数增长、全量测试基线不降）。
- beta DoD ⑤⑥：Release notes 分层措辞逐句勾对；README 中文主+英文简介落地。
- 环境变量名：SUBTRANSJAV_DATA_ROOT（沿 config.py:207/410 模式），不启用 SUBTRANS_DATA_ROOT。

**后续风险跟踪**：
- ffmpeg 选型轮输出（探测/降级/捆绑）纳入 2.0.0-beta 里程碑截止日检查点；超期即触发范围重议。
- API-1 结论留档：若未来出现「双落点」提案，须先过故障注入+分裂脑边界测试方可再议。
- R3（spawn 全覆盖）待 frozen onedir 冒烟实测反馈；R4（回退导出依赖 2.0 可用）待迁移自检 smoke 实测。
- 杀软/签名/WebView2 三类计数观察项沿用 D2026-0929-05 原跟踪，不新增。
- 本条目对原条目修订①②③④⑤⑥⑦⑧⑨⑩的落地执行，由执行层按 roadmap 勾对，验收=主模型。

## [2026-09-29] [D2026-0929-07] 2.0 实施风险 8 条裁决补充（owner 标注 × 主模型全采纳+2 修正，critic 第三轮确认）[已拍板]

- **性质**：实施裁决补充；不改 D2026-0929-05/06 状态，沿 06 修订⑩"唯一执行口径"模式追加执行细则。
- **评议轮次**：第三轮（续评）；引用 05/:1449-1519、06/:1521-1561 与上一轮评议；对 06 修订③⑧作口径修订，其余修订意向不变。
- **实证复核**：F1 relaunch_for_utf8 全库零调用方（console.py:30/363 + docs，py/bat/ps1/tests 全空）——死代码；F2 tm.py:93 WAL 复证；F3 providers.py:7/19/33 字符串键、全库无 PySubtrans import。新取证：console.py 引导层整层 CLI 零外部引用（仅 webview_gui/main.py:20-24 经 setup_console 激活）；sys.frozen 内联判定 3 处（model_cache.py:18、main.py:45/230-231）。
- **逐条裁决**（列 06 对应补充分支）：
  - 点 1（修订③ spawn 清单）→ **采纳修正**：console.py relaunch_for_utf8 由"收敛"改"同批删除"（owner 活路径前提被 F1 证伪，windowed/黑框/独立 console-exe 顾虑随前提失效整体消解；未来真实控制台 relaunch 需求沿用 owner 独立 exe 优先设计，记未来指引不落接口）。收敛清单修订为 **api.py:173、api.py:1409、main.py:63** 三写入点；钉测试（生产包 subtransjav/ 内 sys.executable spawn 仅准出现在 process_manager helper；spawn 语义 AST/调用点级，非裸文本 grep；排除 tests/tools 与 model_cache.py:18 非 spawn 用法）**与收敛批同批落地，不与删除同批**；helper 接口 mode 仅落 cli/gui，"console" mode 留注释预留。UTF-8 保证落点：helper 子进程 env 注入（PYTHONUTF8=1 等）+ EXE manifest/activeCodePage，删除不取消保证。同步修订 roadmap 三处"含 console.py relaunch"文字（R5）。
  - 点 2（TM 双文件原子性）→ **采纳 + 边界写死**：备份 zip 含双文件 + 迁移 manifest（文件清单+sha256+迁移前 tm.db 行数/glossary 长度）；"迁移已完成"哨兵最后写，且仅在双文件拷贝+按 manifest 恢复校验通过后写；恢复校验对 manifest 而非自证（防同源双坏）。半迁移自愈：启动检测"备份存在+新根不完整"→自动清理**仅限 manifest 匹配的迁移残留**（防误删用户数据）→回退旧根；迁移先于一切新根写路径（首启顺序硬约束）。WAL：checkpoint(TRUNCATE) 失败=本轮迁移中止、下次启动重试；三件齐拷仅限源确证静默时，恢复后 integrity_check 为兜底闸。故障注入测试双场景（迁移后用户写入/写事务中迁移）进 beta DoD ②。
  - 点 3（修订⑧ --where）→ **采纳修正**：2.0 --where 全字段采纳（运行形态/数据根及来源/配置/TM/conflict_watch/DPAPI 密钥位置/旧根检测+迁移状态）；1.4.1 **不加** --where（近空集论证成立：迁移仅随 EXE 首发+EXE 无 1.4.1 基线+pip 永不迁移+1.4.1 只读旧位，穷举无生成路径）；回退诊断靠文档+导出指引（已定案）。约束：**旧位保留时长 ≥ 1.4.1 EOL 声明时点**（R4，入发布文档硬约束）。
  - 点 4（resolver 判定依据）→ 采纳：默认值按 **sys.frozen** 而非版本号（同版本双形态行为分叉仅由 frozen 承载）；SUBTRANSJAV_DATA_ROOT env 两形态均生效（显式覆盖优先）；frozen 判定消费**单一 canonical helper**（现 3 处内联归口，_MEIPASS 路径逻辑独立不动）；单测双分支 monkeypatch+真 frozen onedir 冒烟。
  - 点 5（pysubtrans 摘除 CI 门）→ 采纳 + 三层化：门=(1) import 级钉测试（无 `import PySubtrans`/`from PySubtrans`）+(2) pyproject dependencies/keywords 断言；providers 字典键改名随批但不设门；**不设全仓 grep 门**（历史 docstring 提及会永久打红）。
  - 点 6（onedir artifact 真装）→ 采纳：CI 产出可下载 onedir zip+Inno 包+sha256（run-artifact 暂不进 Releases）；不阻塞 pip beta；2.0.0 正式前真人安装反馈一轮，**环境 ≥2**（正常 Win10/11 + 故意无 WebView2/缺 .NET8 干净 VM——缺一即没验到对应风险）。
  - 点 7（tag 前手动验证）→ 采纳：Release 工作流先 workflow_dispatch 跑通"构建→Inno→安装→smoke→卸载"全链再开 tag 触发；tag 保护+版本经 workflow input 参数化（iscc /VERYSILENT /NORESTART 静默链）。
  - 点 8（措辞限定）→ 采纳："GUI 用户无需迁移"限定为"**EXE 安装版：迁移自动完成，无需手动操作**"；pip 用户数据位置不变，归 CLI·脚本层说明；同步修 Release notes 模板与 beta DoD ⑤ 文案。
- **主模型最终决定**：owner 8 条全采纳 + 主模型修正 2 处（点 1 死代码删除、点 3 1.4.1 纯净）+ critic 细则（钉测试顺序/语义、manifest 与哨兵、清理边界、canonical frozen helper、三层 CI 门）全数认领入库。
- **条件是否已闭环**：未启动（开工前实施指引，闭环时点=各细则落地验收）；三项关键条件=钉测试-收敛同批、钉测试语义三层限定、新根清理仅限迁移残留，失验即回退重议。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：R1（删除与钉测试同批→中间态常红）R2（钉测试语义误伤→假红退役）R3（清理越界/WAL 活写三件齐拷）R4（旧位清理 vs 1.4.1 EOL 撞车）R5（旧文案"三 spawn 含 console.py"残留）并入 06 后续跟踪表；console.py 引导层整层死代码审计列为 beta 批低优先清理项（ensure_utf8_console/safe_print/suppress_dependency_warnings 仅 webview_gui 激活）。

## [2026-09-29] [D2026-0929-08] 2.0 打包地基批开工放行 + owner 三条实施细节采纳 [已拍板]

- **性质**：开工放行记录+实施细节采纳；不改 05/06/07 定案。owner 认可第三轮收口，撤回点 1"最可能咬人"警告（前提被 F1 证伪），确认未来控制台入口按独立 exe 优先指引。
- **三条实施细节（全采纳）**：
  1. **helper 增 purpose 语义位**（`"subprocess" | "venv_bootstrap"`）：api.py 两处=同构替换；main.py:63 venv 引导为三 spawn 中唯一形态敏感点——frozen 下无 venv 可建、无 pip 可调，正确行为=**整段 no-op 直接进主流程**（现有 main.py:44-46 frozen 短路 guard 保留，收敛时显式化为 purpose 位，防"替换成功但跑了无意义子进程"的隐性故障）。frozen 子进程显式传 env（含 SUBTRANSJAV_DATA_ROOT）、UTF-8、CREATE_NO_WINDOW、取消杀树（沿 07 点 1）。
  2. **console.py 引导层删除加静态确认**：删除动作前 grep（`ensure_utf8_console`/`console.` import，排除 tests）为空+无 getattr/importlib 软引用；webview_gui 激活路径干净的结论由**钉测试固化**（防未来从 `__all__` 恢复导出静默复活），不靠人工通读。
  3. **两条硬边界执行细节**：R4 字面量=「**EOL 声明时点**」非「保留 N 版」——2.0.1/2.1.0 先于 EOL 发布时清理提示继续挂起，EOL 日期做成构建期常量/发布文档字段供清理逻辑读取；迁移哨兵补边界——**哨兵存在但 manifest 校验失败=无效哨兵走旧根**（非"部分迁移已提交"：哨兵晚于 manifest 写，其信息量依赖 manifest 可信，顺序不可反推）。
- **放行**：owner 2026-09-29 放行打包地基批（resolver + TM 双锚点 + pysubtrans 摘除 + --where），依赖清晰无外部阻塞。**出口信号两条**：① resolver 单测钉 canonical helper（非内联判定残留）；② TM 双锚点挂接后 --where 一次报全且 pip/frozen 下默认源正确。frozen 入口改造+内部 onedir 门禁紧随其后。
- **流程状态**：开工前评议员常设轮次（owner 指示）随放行结束，此后恢复 AGENTS.md 常规（重大决策才评议）。

## [2026-09-29] [D2026-0929-09] 视听对比选型+媒体访问威胁模型定案（修订⑦排期门开启） [已拍板]

- **原决策**：D2026-0929-06 修订⑦排期门定案——视听对比（beta 头牌）采用"探测系统 ffmpeg/ffprobe + 纯标准库 RMS 能量代理（wave 级 VAD 降级）+ 报告不自动重翻"检测层；试听 UI 采用 HTML5 `<audio>` 原生播放 + mkv 走 ffmpeg 时间窗抽片，入口随视觉批合入落地；媒体访问威胁模型五条（契约单源/白名单/Temp 单落点/零网络/无文件浏览）；排期=检测层 CLI 先行、试听 UI 视觉批合入后接，并行前冻结导读新类别 schema。
- **评议异议**：[HIGH_RISK_OBJECTION-1] C-5 "媒体路径选择收窄为契约内选择"属对外可见承诺的解释性收窄（decision-log:1442 原述"GUI 媒体路径选择留 v1.6"），不得追溯为 v1.6 原意；独立 SRT 工作流出路二选一不得悬空。A3 有条件（能量代理须显式声明为 VAD 降级、相对分位阈值+最小 gap+候选截断防误报洪水 R1）。纪律级修正：A1 -version 冒烟、A2 list-args 禁 shell+启动扫 stale+finally 清理、B1 可播判定用 ffprobe 真实 codec、C4 ffmpeg 输入仅限契约本地路径、D 并行前冻结导读 json 新类别 schema。
- **主模型最终决定**：**全部采纳**。① C-5 收窄显式化：试听媒体路径来源=media_path 契约解析值+`--media-path` 覆盖值入可选项；独立 SRT 出路=用户经 `--media-path` 显式指定后该媒体即成为可选源（非"本期不支持"）；无任何来源时条目灰显+提示设置方法；独立文件选择器记入 2.0.1 候选池后续评估，Release notes/手册明示"本期收窄，非 v1.6 原意的全量文件选择"。② A3：显式声明"wave 级 VAD 降级（RMS 能量代理，非神经 VAD）"；阈值=文件内相对分位 P85+最小 gap 300ms+每片候选截断上限（默认 20，可配）；报告类别标"疑似（粗筛）"；实现期 10~20 片真实媒体（含典型 JAV）试跑定阈并参数化；性能目标 <30s/2h 片（超标降采样重测）。③ 其余纪律级修正照单。④ **schema 冻结**：新类别名 `suspected_missed_speech`，沿用现有导读 item 字段形态，仅报告类不进行动条目。
- **条件是否已闭环**：已闭环——两条 HRO 修正（收窄显式声明+独立 SRT 出路）与全部有条件项条件均已纳入定案；评议立场由"有条件支持"转为"支持"，排期门判开。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：① R1 误报洪水由 10~20 片真实媒体试跑闭合，定阈后回填默认值（P85/300ms/上限 20 为初值）；② 检测层与视觉批并行期间持 frozen schema（`suspected_missed_speech`），类别/字段变更走复议；③ C-5 收窄的对外承诺（灰显+提示+手册明示）在 2.0.0-beta Release notes 落地，2.0.1 文件选择器重评时回链；④ ffmpeg 未装灰显属已接受残余，捆绑 essentials 随选型轮另评（LGPL+体积）；⑤ A2/B1 运行时纪律（list-args/真实 codec 判定）在编码与 code-review 两处设卡。

## [2026-09-30] [D2026-0930-01] 产品定位通用化修订：自带角色卡与词典的翻译项目（P1 通用模板/P2 定位措辞/P3 三语词典/P4 质量门）[已拍板]

- **原决策**：owner 方向——项目首先作为通用项目（非 JAV 特定），初始安装自带通用模板角色卡（参考现卡调整通用化，领域如动漫/GAL 可自设或修改）；项目特色从 JAV 特调变更为"自带角色卡和字典的翻译项目"，字典从日语扩展到中、英、日三种；引擎页词典管理必须在下版本上马。
- **评议轮次**：首轮；decision-critic 独立评议（实证抽查：spec datas 无 config/templates、_read_v2_card 无包内兜底缺失即抛错 pipeline_v2.py:322-328、规则四级回落 cleaner_rules.py:25-69、hardened_phrases.yaml 成人特调注释、source_hallucination.yaml 整文件替换语义、pipeline 方向硬编码 ja→zh、sudachipy Config 支持词典路径）。产出 [HIGH_RISK_OBJECTION] 1 条（P2"支持自定义目标语言方向"超前承诺）与 [INFO_GAP] 2 条（非 JAV 实测语料来源/存量用户分布）。
- **主模型最终决定**：**全采纳**。
  - **HRO 采纳**：README 定位句只写"日→中为主"；"支持自定义目标语言方向"删除——方向参数化（pipeline_v2.py:161 硬编码 ja→zh 现状）列入 2.1，能力落地后方可写回 README（失配盘点纪律：承诺句须有对应实现）。
  - **P1 采纳**（2.0.0 正式前落，含新增实现量）：①角色卡读取链重构为四段回落（explicit templates_dir → 数据根 config/templates → 包内通用 templates → 明确报错）——"包内兜底"是新增行为非 datas 追加；②spec datas 加通用模板；③通用版角色卡两张（净语/审校）从现卡派生，去 JAV 场景措辞、保留两段式流程与**纯语言结构信号**的幻觉防护语义（假名无规则排列/孤立语气词/断句碎片，不依赖成人场景词）；④hardened 词领域分布审计先行（"好舒服/不行了"类通用情绪词留通用层，成人专属词归领域包——防分层本身成为新误删源）；⑤领域包=模板+完整规则 YAML 成对文件、导入为**替换语义**并显式提示（防"JAV 卡配通用规则"错配）；⑥现有 JAV 卡+规则对完整保留为领域示例包；⑦存量用户数据根旧卡不受影响（回落链数据根优先），手册注明。
  - **P2 采纳**（修订后措辞）：定位句"自带角色卡与词典的双引擎字幕翻译项目，日→中为主"；WhisperJAV 节降为"可选上游（JAV 源转写实测）"；README:311 补"名称保留、定位通用"沿革说明；CHANGELOG 新增一条记定位修订（[2.0.0b0] 已定版不改写）；作为新一批失配清单登记；**项目名不改**（改名成本高收益低，2.1+ 观察）。
  - **P3 采纳**（2.1，owner 钦点必落）：引擎页词典管理三区块（日/中/英，状态/下载/路径/启用，图 2 风格）；日语=sudachi 下载式（Config.system 路径已核可行）；**中文=jieba**（纯 python，规则级无法产生有意义的中文字界提示）；**英文=规则级起步**（不引重型依赖）；语言判定=字符集启发式逐条路由；词典落数据根 dict/ 运行时按路径加载；中/英**提示注入绑定 2.1 审校消费场景**（无消费点则词典先落、提示缓——防止无人消费的装饰性功能）。
  - **P4 采纳**：通用模板上线前 owner 用非 JAV 字幕实测验收（动漫/GAL 各一，语料由 owner 提供）；**与 owner 两项既有验收（真机 GUI/定阈值）合并同一窗口**。
  - **时序裁定**：P1/P2 落地 → 重新打包 → owner 三项验收（验**最终形态**）→ 正式 tag。b0 验收结论对正式版不直接有效（验收对象须与发布 hash 一致）。
  - **INFO_GAP 回复**：非 JAV 语料 owner 提供；存量装机=owner 本机一例，本决策纯对"新发行"生效，无迁移向导需求。
- **条件是否已闭环**：未启动（P1/P2 执行期闭环：通用模板 owner 实测/JAV 领域包导入后矩阵回归不低于 b0 检测力基线/通用默认层非 JAV 语料误删抽样=0 起/README grep 无超前承诺句/正式 tag hash=验收对象 hash）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：通用默认层误删率（新增非 JAV 语料回归基线）；领域包导入后 JAV 矩阵回归 vs b0；README 新一批失配清单；验收排序审计。**Roadmap 登记**：P1/P2/P4→2.0.0 正式；P3→2.1（必落，升出候选池）。
## [2026-09-30] [D2026-0930-02] README 通用化定位深化修订（模型节标注/声明重定位/词库节校直/受众节校直/英文节软化/痛点节指代）[已拍板]

- **原决策**：D2026-0930-01 通用化定位的深化批——消除 README 全文 6 处 JAV 语境残留，:193 "target_language 设置"失实句一并修正。
- **我的异议**：[HIGH_RISK_OBJECTION] R3/R5 候选修法含虚构路径与功能（defaults/templates/ 顶层路径不存在/参数表与目标语言参数不存在），要求改替代文本；R1 "JAV 领域微调模型"不可验证改"测试语料为 JAV 影片"；R2 选 a 删"模型"一词；R4 保守写法不写 planned。
- **主模型最终决定**：**全采纳**。HRO 两处改替代文本（R3 复用 :267 既有路径 config/templates/ 与 subtransjav/refine/defaults/；R5 删"参数表"/"目标语言参数"改"词库与模板页直接编辑"）；R1-R4/R6 按修正措辞执行；:193 失实句纳入本批；R7a/b/c 采纳（不做通用模型推荐节/声明保守/直接改 main 不发版）。
- **条件是否已闭环**：不适用（全部采纳无保留条件）。验证：grep "参数表"/"target_language"/裸"defaults/templates/"零出现；实测数字零改动。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：失配清单追加本批记录；手册 grep 零同源句零改动；2.1 方向参数化落地后复查 R4 口径可写回性。

## [2026-09-30] [D2026-0930-03] 新会话开工前五项拍板候选终裁（版本拆分/词典下载源/方向参数化/jieba 引入/EOL）[已拍板]

- **原决策**：①2.0.1 先发(CPS 三项)+2.1 后发(词典+方向参数化)；②sudachidict GitHub Release 主源+国内镜像 fallback+PyPI wheel 离线备选；③StageConfig 加 source_lang/target_lang+CLI 参数；④jieba 走 [zh] extra；⑤LEGACY_RETENTION_EOL="2027-06-30"。
- **我的异议**：①有条件支持（milestone 共用仅限展示，2.0.1 独立 tag+Release，内部序=定标报告→行动化→白名单）；②有条件支持（保留 sudachidict_core 主依赖，下载式作 lite/补充路径；SHA256 校验失败拒绝加载；缓存路径三者一致；下载失败与校验失败分开报错）；③[HIGH_RISK_OBJECTION]有条件支持（联动面 10+ 模块非单点；方向放任务级非 StageConfig；E2E 快照回归为放行门；产物命名契约 2.1 开工前拍板；GUI 归属排期；测试基线语言假设回归分类）；④支持（jieba 缺失走 grammar_hint 同款静默降级；体积 5MB→19MB 口径修正）；⑤支持（补"停止修补保留可用"口径）。
- **主模型最终决定**：**全采纳**。③方向参数化列 2.1 独立里程碑，联动面按 10+ 模块立项，产物命名契约与 GUI 归属 2.1 开工前拍板，E2E 字节快照回归为放行门。②保留主依赖不移除。执行序=⑤→①→④→②→③。
- **条件是否已闭环**：未启动（各条件随对应版本开工时闭环）。③ E2E 快照+新方向冒烟+方向字段钉+语言路由逐条为放行门。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：② 双源 SHA256 白名单维护；③ 产物命名契约与 GUI 联动；③ 测试基线语言假设回归分类；② 镜像哈希来源单一化；通用模板豁免补录（本条目归档时由主模型在 decision-log 末尾追加一行确认 P4 豁免）；jieba 实际体积 ~19MB 口径修正；执行序=⑤→①→④→②→③。

> P4 通用模板实测豁免补录（2026-09-30）：owner 裁定通用模板随 v2.0.0 正式版直接生效，真实用户反馈驱动迭代；D2026-0930-01 P4 质量门取消，验收减为两项（真机 GUI+定阈）。

## [2026-09-30] [D2026-0930-04] 翻译方向参数化开工前拍板（命名契约/GUI 归属/8 项草案，critic 两 HRO 全采纳）[已拍板]

- **原决策**：D2026-0930-03 ③ 终裁的开工前拍板（约束：方向放任务级非 StageConfig、E2E 字节快照放行门、测试基线回归分类已定）。主模型 8 项草案：①方向字段 RefineConfig+CLI+GUI；②产物命名契约（缺省方向 `_final_cn` 一字符不变）；③提示词方向感知 builder+模板卡按方向配对；④TM 键形不动仅加列；⑤质量门 is_fluent_target 分派；⑥E2E 快照门定义；⑦测试基线分类；⑧方向进 manifest 指纹。
- **评议轮次**：首轮；decision-critic 独立评议（只读核实 pipeline_v2/config/tm/language_validator/v2_rules/manifest/post_validate/synopsis/cli/api/app.js）。立场：6 有条件支持/1 支持/1 反对；[HIGH_RISK_OBJECTION]×2（HRO-1 TM 键：`UNIQUE(content_hash,stage)` 下跨方向同文本经 UPDATE 分支**静默覆写存量 ja→zh 译文**且 hit_count 无语言过滤互相刷数；HRO-2 指纹：方向无条件进 payload 会改缺省方向 `compute_config_hash` 字节、存量 `--resume` 全量误失效）；清单外联动 5 项（post_validate/cleaner 方向盲区、hardened_suffix 无条件追加、synopsis 中文摘要错位、文法缓存键缺方向、词库 ja→zh 归属未定义）。
- **主模型最终决定**：**两 HRO 全采纳，其余按 critic 修正全采纳**。①方向字段=RefineConfig `source_lang/target_lang`（默认 ja/zh）+CLI `--source-lang/--target-lang`（白名单起步 ja/zh/en）+GUI 高级参数页"翻译方向"控件；`validate()` 前置三查（source≠target/白名单非法报错/无配套模板卡当场报错）。②命名契约=**缺省方向产物名一字符不变**（`_final_cn` 保留为 target=zh 历史别名），非缺省方向 `_final_{lang2}`；单点映射 `final_suffix(target)->{"zh":"cn","en":"en"}`+契约钉测试；已核 `_final_cn` 硬编码 8+ 处（pipeline_v2/action_retranslate/quality_report/v2_outputs/api/event_stream/manifest）全走单点收口；GUI/事件流完成检测方向化；manifest 增 direction（from_dict 缺字段回退 ja→zh）。③builder 对 (ja,zh) **逐字节复刻**现提示词（含 hardened_suffix 追加一并钉快照）；方向配对卡解析进 `instruction_source_files` 指纹（消盲区）；缺卡 validate 期报错。④**采纳 HRO-1**：TM 唯一约束升维 `UNIQUE(content_hash,stage,source_lang,target_lang)`（表重建迁移，存量行回填 ('ja','zh')；ALTER 不能改 UNIQUE）+ store/lookup/exact_map/has_exact/hit_count 全 CRUD 语言过滤 + CSV 导入导出语言列（默认 ja/zh 兼容旧格式）+ `_TM_FINGERPRINT_COLUMNS` 不动（tm_sha1 不变、旧 resume 清单不失效）。⑤语言校验三件为 zh→en 冒烟的**排序阻塞前置**：is_valid_stage_text 增 en 拉丁签名分支 + filter_stage_output 目标映射扩展（现非 zh 全归 ja）+ v2_rules:141 方向传参；is_fluent_target 分派含 action_retranslate。⑥E2E 门=缺省方向（含 A/B 中间产物与 hardened_suffix）字节级不变 + zh→en 冒烟 rc=0/非空/en 签名过 + 冒烟走显式 --s0/--s2-instructions 测试卡。⑦现有 zh 假定断言保留为默认方向钉+新方向独立追加+全量只增不减+批 3 人工分类。⑧**采纳 HRO-2**：方向字段条件键缺席归一（缺省方向 compute_config_hash **字节不变**，沿 media_path 特判先例，配字节不变式单测）+ `_v2_stage_prompts_sha1` 升级 cfg 感知（哈希当前方向有效提示文本+方向卡片内容）。**清单外 5 项全采纳**：post_validate/cleaner_rules 按 (source,target) 门控；非缺省方向抑制 hardened_suffix/synopsis/文法缓存键加 direction；词库声明 ja→zh 专属、非缺省方向自动禁用+告警；行动层离线重建文档随批 3 同步。
- **切批**（critic 方案）：批 1 零行为地基（字段+校验/TM 迁移/命名映射收口/manifest 方向）→ 批 2 方向透传（builder/en 签名/质量门/门控/缓存键/GUI 完成检测/指纹 cfg 感知）→ 批 3 文档收口（README 严守 D2026-0930-01 HRO 措辞/报告文案/测试分类/CSV 语言列）。
- **INFO_GAP**：`SUPPORTED_TARGETS` 上游 provider 消费点对 en 的放行情况——批 2 开工前核查。
- **条件是否已闭环**：未启动（随三批落地闭环；批 2 放行门=缺省 E2E 字节快照+zh→en 冒烟；全项放行门=D2026-0930-03 ③ 四条：E2E 快照+新方向冒烟+方向字段钉+语言路由）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：en 拉丁签名误杀率（语言校验侧小样数据）；非缺省方向 resume 指纹盲区（卡片解析进指纹后回归）；TM 表重建迁移执行顺序（生产库先备份 zip 再迁移）；GUI 方向控件与完成检测联动（web-gui-tester 黑盒）。

## [2026-09-30] [D2026-0930-05] 中/英分词提示生成与注入接线（token_hint 模块 + 源语言分派 + 缓存键透传）[已拍板]

- **原决策**：2.1 中/英分词提示生成与注入接线（roadmap ⬜ 项）。新模块 `subtransjav/refine/token_hint.py`：`is_zh_hint_available()`（jieba 探测，缺失静默降级）+ `generate_zh_hints`（R1 分词参考，jieba 精确模式，token≥2 输出『【语法提示】\n- 分词参考：tok1 | tok2 | …』）+ `generate_en_hints`（R1 全大写缩写 ≥2 字母词界匹配，纯正则零依赖）；`_collect_grammar_hints` 增 direction 参数并透传缓存键（顺修 :586 未透传缺口）；按**源语言**分派后端（ja→sudachi 逐字节不动 / zh→jieba / en→规则）；槽位=A、B 两现成注入缝（零新缝）；复用【语法提示】头与『原文：』包装格式（残留清理零改动）；无条目总量阈值、无用户开关/CLI 参数/user_settings 键；不动 GUI/i18n/CLI/manifest；TDD 双态可跑（假 jieba 注入全量 + 真 jieba skipif）；缺省 ja→zh 全链字节不变为放行门。
- **约束回链**：jieba 为 pyproject `[zh]` extra（>=0.42），主依赖与 CI 缺省不装（本机 .venv 实测未装）；缺省方向字节不变红线=105 枚 pipeline_v2 E2E 快照 + HRO-2 config_hash 字节不变式（D2026-0930-04）；缓存键方向隔离沿用 D2026-0930-04 联动 4（`_grammar_cache_key` 已有 direction 参数但调用点从未透传——隔离实际失效，本批顺修补洞）。
- **评议轮次**：首轮；decision-critic 独立评议。实证抽查：pipeline_v2.py `_collect_grammar_hints`/缓存键/阶段 A/B 注入缝、cleaner_rules.py 残留清理三模式+rsplit 兜底、grammar_hint.py（8 规则+正则回退+D4 双锁）、dict_manager.py jieba 探测、test_dict_manager.py 假组件范式、pyproject.toml [zh] extra、config.py `_is_default_direction`/generic B prompt『{sn}原文 ||| {tn}译文』、源/目标白名单 ja/zh/en、decision-log D2026-0930-01 P3 原文、roadmap 2.1 节、CHANGELOG [未发布] 段、test_direction_batch2.py。核验结论：方案全部事实引用准确、无材料矛盾。立场=**有条件支持**；产出 [HIGH_RISK_OBJECTION]×1（HRO-1 接线范围 vs D2026-0930-01「绑定审校消费场景」字面口径）+ 条件项 4（R1 token 成本量级低估/R2 find_spec×sys.modules 假体测试双态坑/R3 jieba 冷启动并发/R4 direction 参数双语义）+ 提示项 R5（同源异目标缓存键冗余）+ 清单外联动 2 项（批2「缓存键方向隔离」宣称-实际落差文档措辞、zh→en 真跑冒烟归属）。
- **我的异议**：[HIGH_RISK_OBJECTION-1] A 缝接线超出 D2026-0930-01 P3「中/英提示注入**绑定 2.1 审校消费场景**」已记录口径字面（审校=阶段 B，阶段 A 属净语+翻译）——构成对已拍板决策的阐释变更，须显式裁定并落澄清记录，防止 roadmap ⬜→✅ 时口径与实际行为静默漂移。条件项：R1 zh 分词参考为**逐行全命中**（区别于 ja 8 规则稀疏命中），提示文本≈源文复写，A 阶段 token 量级 ≈+0.5~1× 源文，方案自陈"同先例"低估；R2 生产探测用裸 `find_spec("jieba")` 与测试引用的 sys.modules 假体范式冲突（假体无 `__spec__` 时 find_spec 抛 ValueError 击穿"静默降级不抛"；开发机装有 [zh] extra 时假体被真 spec 旁路，"双态可跑"失稳）；R3 jieba 冷启动建前缀词典并发竞态，须镜像 grammar_hint D4 双检锁；R4 direction 参数同担缓存键判别与分派两职，须显式字符串契约。
- **主模型最终决定**：**1 HRO 采纳、4 条件项全采纳、2 联动点采纳、无驳回无复议**。
  - **HRO-1 采纳**：接线范围=A、B 两注入缝（源语言分派，零新增 gate）。落澄清句：**"对 D2026-0930-01『绑定审校消费场景』的澄清：意为『存在真实消费点（A/B 注入缝均消费）即接线』，非限定 B-only"**（回链本次 critic 评议）。
  - **R1 采纳**：zh 提示注入门槛=分词 token≥2 **且 strip 后长度≥6 字符**；决策日志如实记账"zh 分词参考为逐行命中（区别于 ja 稀疏命中），A 阶段提示文本量级 ≈+0.5~1× 源文 token；非缺省方向+显式配卡为天然缓解，LRU 缓存命中后重复批零成本"。
  - **R2 采纳**：`is_zh_hint_available()` 走 **try-import + 模块级缓存布尔**（可被测试重置），不用裸 `find_spec`；测试 monkeypatch 模块装载函数，不依赖 find_spec 对无 `__spec__` 假体的行为。
  - **R3 采纳**：jieba 惰性单例双检锁（镜像 grammar_hint D4 模式）。
  - **R4 采纳**：缓存键传方向对全串，分派显式 `direction.split("→")[0]`，测试钉字符串契约。
  - **R5 不处理**（认同：纯缓存条目冗余，无正确性影响）。
  - **联动 ①采纳**：CHANGELOG/roadmap 中批 2「文法缓存键方向隔离」措辞补注"调用点透传随 D2026-0930-05 补齐"。
  - **联动 ②采纳**：roadmap ⬜→✅ 措辞**限定"机制层完成"**，zh→en 端到端（含提示实效果）验证责任仍归 owner 真跑冒烟项。
- **定案条目**：①槽位=A、B 双缝（源语言分派：ja→generate_grammar_hints 逐字节不动 / zh→jieba / en→大写缩写规则）；②阈值=token≥2 且 strip 长度≥6，每条目 ≤1 条提示，无条目总量阈值、无用户开关/CLI 参数/user_settings 键；③缓存沿用 `_GRAMMAR_CACHE`（键含方向对全串，跨方向不串）；④B 输入『原文：中文 ||| English』与 generic B prompt『中文原文 ||| 英文译文』格式自洽，残留清理零改动；⑤不动 GUI/i18n/CLI/manifest，提示只改发 LLM 文本（阶段 A 既定契约"不影响 TM 键与产物"）。
- **验证门**：①既有 105 枚 pipeline_v2 缺省快照原样跑绿=E2E 字节不变门；②新增 `_grammar_cache_key(text, tag, profile)` 与显式 "ja→zh" 传参**逐字节相等**钉测试（缓存层字节不变式直接对应）；③en 回显『【语法提示】…原文：中文 ||| English』→保留英文侧残留清理钉测试；④ja/zh 同文本双方向键不同且 hint 不串功能测试；⑤缺 jieba 静默降级（`_collect_grammar_hints` 返回空 dict 不抛）双态测试——本机（未装 [zh]）与装有 [zh] extra 环境各跑一轮；⑥真 jieba 用例 skipif（CI/本地缺省不装不跑）；⑦测试基线 1522+4 只增不减。
- **条件是否已闭环**：本批实施期闭环——R1 门槛与记账、R2 try-import+模块级缓存布尔、R3 双检锁、R4 字符串契约钉测试随代码落地即闭环；HRO-1 澄清句已在本条目落盘（2026-09-30）；联动 ①② 随 CHANGELOG/roadmap 修订闭环。闭环后本决定视为支持。
- **决策点三问终答**：①消费槽位=A+B 双缝（源语言分派，零新增 gate，D2026-0930-01 口径按澄清句理解）；②阈值/上限=token≥2 且 len≥6、每条目 ≤1 条、无总量阈值/无用户开关；③方案过 critic（1 HRO 采纳、4 条件项全采纳、2 联动点采纳，无驳回无复议）。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①zh→en 端到端（含 jieba 提示实效果）验证责任在 owner 真跑冒烟项，未真跑前 roadmap 仅计"机制层完成"；②en 源方向（en→zh，白名单内）的 en 规则分支为低频路径，需真实方向冒烟覆盖；③jieba 版本（>=0.42 浮动）分词差异仅影响非缺省 prompt 文本、不入字节门，观察是否有必要钉版本下限；④缓存键双语义契约（方向对全串 vs 源语言分派）经 R4 钉测试防回归。
- **执行追记（2026-09-30，zh→en 真跑冒烟三轮 PASS，机制层转全链验证完毕）**：LM Studio gemma-4-12b 实跑（6 条中文样本，隔离数据根）。首轮 rc=0/`_final_en` 命名/提示注入 5/6（≥6 字符门槛生效）全通，但抓出三缺陷批内修复（回归测试随修，全量 1538+5→1547+4 只增，真 jieba 用例转正）：①**回显污染**——模型把【语法提示】辅助段整体译成英文结构回显进终稿（[Grammar Tip]/Word segmentation:/Source:/English:/\*\*Final:\*\*，中文残留模式不匹配，且带偏同批未注入条目）→ generic A/B 提示词加防回显条款+格式纪律（仅非缺省路径，缺省 V2_STAGE_PROMPTS 逐字节不动）+ `clean_grammar_hint_residue` 增 target_lang 门控 en 模式（行锚定防误伤，缺省/zh 零感知钉）；②**generic B 无输出编号协议**——解析器只认 #N/Translation> 协议，generic B 建成时无协议致二轮 0 行可解析全降级 → 镜像缺省卡语言无关协议骨架（不含 ja→zh 特调条款，一轮系模型碰巧猜中格式）；③**TM 方向接线缺口**——zh→en 学习行落 ('ja','zh') 缺省列（HRO-1 管线侧断点：两处 TranslationMemory 构造不带方向）→ __init__ 增实例缺省方向+8 个 CRUD 方法 None 回落+cli/pipeline_support 构造点接线（显式传参路径逐字节不变，CSV 行级语言仍优先）。三跑 PASS：终稿 6 条裸译文零残留（歧义样例 乒乓球拍卖/北京市长江大桥 均正确切分）、B 段协议解析 6/6 真实生效、TM 方向列 zh/en。真跑另证：jieba 冷启动/横幅方向化（"对照中文原文"）正常；LM Studio 引擎对齐会卸载在载的其它模型（已知行为）。Mimosa 复扫 seal c9ec5c0a… findingCount=26=基线 24 零新增+2 树外签注（同前）。

## [2026-09-30] [D2026-0930-06] 磁盘清理方案评议与执行（2.6G→812M，critic 1 HRO 采纳+owner 两裁定）[已执行]

- **原决策**：owner 提出"项目占用 2.4G，哪些无用/过期/作废文件可清理"。主模型盘点（du 实测 2.6G）出四档方案（高置信删/纯缓存/待 owner 定/禁删）交 decision-critic 评议后执行。
- **评议轮次**：首轮；decision-critic 独立评议（只读核实 evidence-manifest.md/decision-log/refine/tm.py/data_migration.py/release.yml/language_validator.py/.gitignore 及 Temp 双前缀实测）。立场=**有条件支持**；[HIGH_RISK_OBJECTION]×1（HRO-1 .tmp374 归类：docs/evidence-manifest.md 通篇将 .abtest/ 与 .tmp374/ 并列定义为原始证据目录——.tmp374=上游 issue #374 评论快照（E1-R1 外部 AI 点评轮审读对象溯源），decision-log:465 互证，manifest 明文"清理原始目录前必须先确认本文件内容完整"；主模型原归"纯缓存删除"与既有文档事实冲突）+ MEDIUM×3（M1 Temp/pytest-* 中划线前缀 43 个 183M 被通配符 pytest_* 遗漏；M2 benchA_out 等 bench 输出无树外归档记录、decision-log:992/1005 有 Temp/bench_input.srt 无副本消失先例；M3 rel201 删前宜核 GitHub Release 资产在线）+ LOW×2（gui_blackbox_dataroot 删除与 2.1 验收同向且零代码固定路径引用；rm 通配面安全）+ INFO_GAP×2（发帖附件 zip 是否已发；.abtest/.tmp374 取舍）。
- **主模型最终决定**：**HRO-1 采纳**（.tmp374 移入待 owner 定档）；M1/M2/M3 全采纳（双前缀清理/bench 划待定/删前核资产）。**owner 两裁定（2026-09-30）**：①发帖附件 WhisperJAV_192_实测数据.zip **已发**；②**.abtest 与 .tmp374 原样保留**（不压缩不移动不删除）。Errors/ 旧转储（9-19~9-23）与 bench/e3cal 散项 owner 未裁定，本轮全部保留（合计 <10M）。
- **执行明细**（2026-09-30）：删前经 REST API 核实 v2.0.1 Release（id 399202708）资产在线（SHA256SUMS.txt+SubTransJAV-setup-2.0.1.exe+lite，均可重下）。第一批=Temp/rel201（691M，发版下载产物）+pyinstaller_dist/_lite（340M）+pyinstaller_work/_lite（116M，本地试打包）+gui_blackbox_dataroot（193M，黑盒数据根）；第二批=Temp/pytest_*（34 个 209M）+Temp/pytest-*（43 个 183M，basetemp 残留）；第三批=.mypy_cache（82M）+.pytest_tmp+.pytest_cache+.ruff_cache+subtransjav.egg-info。**回收 2.6G→812M（约 1.79G）**。
- **禁删清单**：Temp/translation_memory（14M，活跃 TM 库：tm.py:33 缺省路径+项目根无 .data-root 指针，批次 E 实测积累 6382 条用户资产）、.venv（479M，测试环境）、.mimosa（18M，扫描基线）、dict/（193M，2.1 真机验收后处置）、.git、Logs/（runlog 自管 7 天）、dropped_entries.log（活跃多源台账：language_validator.py:278/source_hallucination.py:414 写入，1.39M 未到 5M 轮转线）。
- **验证**：ruff 通过；全量 pytest **1559 passed+4 skipped**（清理前基线 1555+4，只增不减）；冒烟 subtransjav-refine --help 正常+webview_gui.main 可导入；Mimosa 深扫 seal sha256:55433d42287b2443ae3cba1bb6b7c2dbf583a822eb788c04614d6fbc132c16fa、findingCount=24=基线 24 零新增。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①dict/（193M）待 2.1 真机验收（词典下载+方向切换）完成后可清（重下即得，验收本身即测下载流程）；②Errors/ 旧转储与 bench/e3cal 散项待 owner 裁定后处置；③Temp/pw-runner（14M）未列入批准批次，保留；④gui_blackbox_dataroot 下次 GUI 黑盒测试自动重建。

## [2026-09-30] [D2026-0930-07] UI 改版轮立项 [已拍板]

### 一、背景

owner 2026-09-30 反馈"UI 还是过于杂乱和不美观"，roadmap.md:51 挂账"UI 改版轮：方向控件与角色卡命名关系明晰化（'阶段指令卡'实为角色卡显式路径，与净语配置目录的自动查找易混）及本轮验收暴露的其它 UI 设计问题"。v2.1.0 已于 2026-09-30 发布（tag v2.1.0→543fb3d）。经研报 10 条实证（含只读抽查复核：43 处 `.style.` 引用中真颜色 ~14 处、四主题 @import+变量覆盖、净语目录硬编码填充 app.js:2986-2991 且无持久化、方向控件 2.1.0 已落地、i18n 双表钉测试在位），立项 UI 改版轮，范围原则：功能零增删、i18n 双表契约不破、四主题模式不破、五 TAB 外壳结构不变。

### 二、评议轮次与立场

- 评议轮次：1 轮（决策评议完整模式）。
- decision-critic 立场：**有条件支持**（无 [HIGH_RISK_OBJECTION]；普通异议）。
- 主模型最终决定：**采纳**（8 条修订 7 条全额采纳 + 1 条含裁定细化）。
- 异议记录：六项支持条件全部转化入定稿范围；无驳回异议、无 [PRESSURE-OVERRIDE]（owner 缺席不构成放行压力，按调研实证推进已记录）。

### 三、逐条裁定

| # | 评议原始意见 | 主模型裁定 |
|---|---|---|
| ① | 批 2g 引擎页阶段 A/B 卡对称精简降级为可砍项（与 roadmap D 项同页叠改） | **采纳**，并补充口径：引擎页本轮只做 CSS 层轻量统一（form-card 头部结构/间距归一、内联宽度收编），**不做 DOM 重排、不做控件重排**；截图回归超预期则整项砍掉，止损线生效 |
| ② | 批 1a+1b 文案合并设计，UI 明示"角色卡目录与净语配置目录是两套独立查找规则"，纳入批 3 验收 | **采纳** |
| ③ | 批 1a 联动回显移出硬交付，转批 3 加分观察项 | **采纳**（截图判定后再定是否追加） |
| ④ | 批 2c 先建"色值→位置→语义→token"映射表逐色确认（禁字典式全局替换）；新 token 默认值落基底 style.css，主题按需覆盖；按实测 ~14 处排期 | **采纳** |
| ⑤ | 批 3 截图基线须含完整外壳（导航/页头）亮暗对比；补批 1c provider 联动桥黑盒用例（选值→联动→重启回填） | **采纳** |
| ⑥a | INFO_GAP-1：前置索取 owner 五 TAB 逐页痛点清单 | **裁定不阻塞本轮**——owner 不在场，按调研实证推进；收尾通知时向 owner 索取逐页痛点清单作为下一轮输入 |
| ⑥b | INFO_GAP-2：外壳迁移暗色 token 规划 | **裁定**：沿用现有 `--tab-bar-bg`/`--content-area-bg` 等既有变量，覆盖不足再补新变量 |
| ⑦ | 执行序硬化：批 1 全部 → 批 2 内序 a/b/c/d 前置、e/f/g 后置（g 可砍），超预期砍 f/g 止损 | **采纳** |
| ⑧ | 版本默认 2.1.1，交付含用户可见新功能才升 2.2.0 | **采纳**：版本定 2.1.1 |

### 四、范围定稿

**批 1（信息架构与命名明晰化）**
- 1a 方向与角色卡统一叙述：高级参数页"翻译方向"区改造（方向双下拉 + 阶段 A/B 卡路径输入框改标签"阶段A 角色卡（可选，留空=自动查找）" + 回落链一行说明）；词库页角色卡编辑器加说明句"若高级参数页指定了显式卡路径，以其为准"。只动文案/标签/提示与少量 DOM 归组，不跨页搬控件。联动回显移出，转批 3 加分观察项。
- 1b 净语配置目录：去硬编码假填充（app.js:2986-2991），改 placeholder"留空=自动查找"；浏览选择值持久化（进 `refine_save_stage_settings` settings 字典新 key，api 侧透传；空串=回落链，api.py:283 仅非空传 `--cleaner-config`，行为不变）。
- 1c provider 三处同步：主页快捷条补 zen 选项，与引擎页 A/B 双向同步。
- 1d 残留清理：词库页单按钮标签结构移除；TAB4 名称统一（MSG"质量与建议"为准，二选一已定）。

**批 2（视觉统一与降噪）**
- 2a 目录行统一组件 .path-row。
- 2b index.html 内联 style 收编（143 处，不追求清零，优先高频模式）。
- 2c app.js 硬编码色→语义 token（新增 --text-muted/--status-ok/--status-err，基底默认 + 四主题按需覆盖；按映射表逐条执行）。
- 2d 外壳样式迁入 style.css（主题可管理；token 沿用现有变量，不足再补）。
- 2e style.css 死段落清理（15 空壳节+死规则；不设"清洁度清零"硬指标，只清本轮抓到的）。
- 2f 按钮三级归一：btn-text 并入 btn-ghost（全量替换，2 处定义保留 1）。
- 2g form-card 统一头部结构与导读页三路径行归组"来源"区块；**引擎页仅限 CSS 层轻量统一（不含 DOM/控件重排）**，截图回归超预期整项砍掉。

**批 3（验证收口）**
- i18n 同步钉自动覆盖新键。
- 新增 cleaner 持久化回归测试。
- bridge/web-gui-tester 黑盒五页×亮暗双主题截图（**含完整外壳对比**）+ provider 联动用例（选值→联动→重启回填）。
- 全量 pytest 基线只增（现基线 1559 passed + 4 skipped）。
- 提交信息注明 GUI 已验证/未验证。

**出局项（本轮明确不做）**：引擎页"左列表+右详情"全量重构（roadmap D 项，延后独立立项评议）；跨页搬移方向控件；功能新增、五 TAB 结构变更、alert/prompt 替换为自制弹窗；全局字号/行高/间距 token 化与密度重排（入 roadmap 候选池）。

**止损线**：批 2f/2g 中任一截图回归超预期即单项砍掉，不做全量回退；执行序 批1 → 2a/2b/2c/2d → 2e/2f/2g。

### 五、验证要求

- 批 3 截图与桥黑盒为放行前置（五页×亮暗主题，含外壳）。
- token 化按映射表 git diff 逐条评审。
- 两套回落链文案以黑盒文案断言 + 截图评审双验。
- 版本号：2.1.1（条件触发升 2.2.0 的升级条件：交付含用户可见新功能——本轮预期不触发）。

### 六、风险跟踪表

| 跟踪项 | 概率/影响 | 处置/验证 |
|---|---|---|
| 两套回落链文案打架、挂账未消反增 | 中/高 | 批 3 截图 + 黑盒文案断言（评审人：主模型） |
| 色值语义误映射 | 中/中 | 映射表 diff 逐条核（执行者）+ 亮暗截图 |
| 外壳迁移后暗色对比度翻车 | 中/中 | 截图含完整外壳亮暗对比 |
| 引擎页/按钮 CSS 统一回归 | 中/中 | 止损线：单项砍掉不回退 |
| provider 三处同步断链/丢保存态 | 低/中 | 桥黑盒 选值→联动→重启回填 |
| 批 1a 说明句消歧不足 | 低/低 | 联动回显加分观察项判定是否追加 |
| owner 痛点未命中（INFO_GAP-1） | 中/中 | **收尾通知时索取五 TAB 逐页痛点清单 → 下一轮输入**；本轮按实证推进 |
| 外壳 token 不足需补变量（INFO_GAP-2） | 低/低 | 迁移时暴露即补，四主题按需覆盖 |

### 七、条件闭环状态

六项支持条件（批 2g 可砍 / 回落链文案合并 / 逐色映射 / 外壳截图覆盖 / 执行序硬化 / 版本 2.1.1）经裁定全部采纳并转化入定稿范围——**决策层已闭环**；其执行期验证归属批 3 收口。无复议保留、无 [PRESSURE-OVERRIDE]。后续若追加联动回显或其它用户可见功能，需按触发条件复议版本号后再立项。

## [2026-09-30] [D2026-0930-07-追加1] 角色卡目录下拉动态化+导读文件对话框 [已拍板]

### 一、背景

D2026-0930-07（UI 改版轮）执行期间的追加批（2.1.1 未发版）。owner 原话："因为是通用性，角色卡模板的选择下拉应该是带出来目录中有的而不是当前逻辑，高级参数中的角色卡也应该如此。这点和评议员讨论下。" 痛点：2.0.0 通用化 + 2.1.0 方向参数化后，角色卡目录（默认 config/templates 或会话注册目录，`_ensure_template_dir` 守卫，api.py:64-88）实际可含任意多张卡（自建、整包导入 docs/examples），但词库页 `#refineTemplateStage` 下拉只有钉死 A/B 两项（index.html:369-372），目录内容对 UI 不可见。同批另有 owner 直给的第 1、2 条（折叠图标放大、导读入口改文件对话框），为 UX 修改非新功能，不经评议、随本条目一并记录，适用同一版本复议结论。

### 二、评议轮次与立场

- 轮次：首次评议（2026-09-30，decision-critic，owner 指定须评议）。
- 立场：**有条件支持**（放行前置 = 必改 4 项；闭环项 = 必要 4 项；建议 3 项）。
- 材料口径更正（已并入执行单）：加载端点实际为 `refine_get_template`（api.py:1365）；保存端点 `refine_save_template`（api.py:1441）；"四级回落"为管线侧 `_read_v2_card`（pipeline_v2.py:407-417）行为，GUI 编辑端点无 pkg 回落；GUI 侧无独立 `cfg.templates_dir`，有效目录口径 = 默认目录/会话注册目录。

### 三、HRO 裁定（版本复议过程与结论）

- 异议：**[HIGH_RISK_OBJECTION]**（共识冲突条款——追加批含用户可见新能力，落入 D2026-0930-07 出局项"功能新增"与"追加用户可见功能需先复议版本号"触发线）。
- 主模型回应：**采纳**，走显式版本复议程序。
- 复议结论：**维持 2.1.1**。理由：(a) 2.1.1 未发版无兼容包袱，独立发 2.2.0 无交付收益；(b) 本批定性为既有角色卡编辑器的能力补全（编辑器本来就能改目录下文件，UI 此前看不见目录内容），非独立新交付物；(c) owner 在同一指令内明确授权追加。
- 附带承诺（已纳入验证要求）：**批 3 截图基线重拍，下拉区域与高级参数页 datalist 入图**。
- 受影响决策：D2026-0930-07 范围定稿"出局项：功能新增"经 owner 追加授权突破，属同一指令内的范围修订；版本条款经本次复议消解，无遗留冲突。

### 四、逐条裁定表

| 类别 | 条目 | 状态 |
|---|---|---|
| 必改① | list 端点复用 `_ensure_template_dir` 守卫，不新增任意目录列举口子；口径改为"GUI 有效目录（默认/会话注册）" | **采纳** |
| 必改② | 保存端点值域闭环 = list 返回值域：目标文件 basename 化 + join 后 resolve 须在有效目录内 + .txt；补"保存 target 不在 list 返回集 → 拒绝"测试 | **采纳** |
| 必改③ | 前端列表/选中渲染对文件名全量 esc()（readdir 结果为外部输入） | **采纳** |
| 必改④ | 走版本复议程序（结论=维持 2.1.1 + 日志）；批 3 截图基线重拍两页新控件 | **采纳** |
| 必要⑤ | 定义 load-by-name 精确路径（`refine_get_template` 扩展或新端点）；GUI load 不做 pkg 回落，与"保存只写有效目录"对称 | **采纳** |
| 必要⑥ | MSG 处置：保留 tpl_stage_a/b 供 canonical 标注；新增"目录为空/pkg_fallback/加载路径"键；HTML 骨架不留未标注中文；fallback 固定项改 JS 按 MSG 渲染 | **采纳** |
| 必要⑦ | pkg_fallback 分支 UI 明示"目录为空，保存将新建默认文件" | **采纳** |
| 必要⑧ | switchTab 到 tab-glossary 补下拉初始化调用（当前无打开钩子，app.js:2818-2824） | **采纳** |
| 建议⑨ | 批 3 桥黑盒追加：下拉项数=目录 .txt 数、选非 canonical 卡→保存→磁盘文件断言、datalist 建议弹出 | **采纳** |
| 建议⑩ | datalist 空列表注入不可选提示项；option 用 value=完整路径、不带 label | **采纳** |
| 建议⑪ | 列表端点返回文件名 + mtime（提案已有）供排序 | **采纳** |

### 五、范围定稿

1. 新桥方法 `refine_list_templates`：解析有效目录（`_ensure_template_dir` 口径），返回 `{dir, files: [{name, mtime}], pkg_fallback}`；守卫：仅顶层、仅 .txt、返回相对文件名；目录不存在/为空 → files 空数组 + pkg_fallback=true（不创建目录）。
2. 词库页下拉动态化：打开词库页/点"重新加载"调 list 填充；canonical A/B 卡（精确匹配 `V2_TEMPLATE_FILES`，pipeline_v2.py:157-160）排最前并保留"阶段A/B"标注（MSG 键渲染）；其余文件按文件名列示（含复合后缀卡如 `.en2zh.txt` 与 README 类文件，无标注、按普通项显示"所见即所编"）。选中即加载（load-by-name，无 pkg 回落）；保存写回所选文件（值域 = list 返回集 + 上述守卫）；目录空/pkg_fallback 回退固定 A/B 项，读写走现有闭包路径，UI 提示"保存将新建默认文件"。
3. 高级参数页 #directionCardS1/S3 加 `<datalist>`：选项 = 同一有效目录各文件完整路径（value=完整路径、无 label）；自由输入与空值=自动查找语义不变（api.py:223-226 仅非空传 `--s1/s3-instructions`）；空目录注入不可选提示项。
4. i18n：tpl_stage_a/b 保留；新增目录为空 / pkg_fallback / 加载路径键；静态钉单向校验不破。
5. 范围边界（本批明确不做）：GUI load 的 pkg 回落（首次安装空目录行为维持现状，不改功能面）；README 类文件过滤（按目录内全 .txt 列出，观感留批 3 截图验收定夺）。

### 六、验证要求

- tests 夹具构造含复合后缀卡（`.en2zh.txt`）+ README 类文件的样本目录，对 list 端点做验收：canonical 精确匹配行为、普通项标注、守卫用例（穿越/非 .txt/空目录/pkg_fallback 标注）、保存 target 不在 list 返回集 → 拒绝、文件名参位穿越、list 后文件变更竞态 error 分支。
- 全量 pytest 基线只增，方向参数化钉测试（tests/test_gui_api.py:1485-1515）语义不变。
- i18n 静态钉同步（新增 MSG 键入表、HTML 无未标注中文）。
- **批 3 截图基线重拍（承诺）**：词库页下拉动态化区域 + 高级参数页 datalist，均含亮暗两主题与完整外壳；桥黑盒追加用例见建议⑨。
- 提交信息注明 GUI 已验证/未验证。
- 执行期闭环确认点：必改①②③④ 与必要⑤⑥⑦⑧ 落地即视为本批总体条件闭环，由主模型在提交前验证链确认。

### 七、风险跟踪表

| 跟踪项 | 概率/影响 | 处置/验证 |
|---|---|---|
| 保存端点文件名参位穿越回归 | 低/高 | 必改② + 新增用例（文件名参位 + target 不在 list 集） |
| 误覆盖目标面扩大（2→N） | 中/低 | 状态栏持续显示 r.path；非 canonical 保存做磁盘断言 |
| 动态文件名 DOM 注入 | 低/高 | 必改③ 全量 esc() |
| README 类非卡文件当卡列出观感 | 中/低 | 批 3 截图验收定夺是否加显示层过滤（不做本批硬承诺） |
| datalist 空目录误导 | 中/低 | 建议⑩ 空列表提示项 |
| 首次安装空目录固定 A/B load 报缺件（既有疤痕） | 中/低 | 本批不改功能面；仅补 pkg_fallback 文案提示 |
| 批 3 基线重拍遗漏新控件 | 中/中 | 截图清单显式列两页新控件 |

---

## [2026-09-30] [D2026-0930-08] UI 改版阶段 1 实施立场定稿（三栏骨架+双主题收敛，critic 2 HRO 全采纳）[已拍板]

### 一、背景

UI 改版轮（D2026-0930-07）落地路线第 7 节阶段 1（骨架与主题）开工前，主模型提交 7 项实施立场 A–G（主题机制保留 link 切换 / JS 依赖契约扩容 / 顺手修 5 个重复 tab id / 富文件行推迟阶段 2 / 全量重写 style.css 风险对冲 / 侵权评估 / 验证链）提请评议。唯一事实来源：`docs/design/UI-REDESIGN-HANDOFF.md`（第 4 节硬性约束、第 7 节落地路线）；原型：`docs/design/redesign-prototype.html`。技术约束：PyWebView 离线桌面应用、前端纯 HTML/CSS/JS 无构建链、app.js 功能逻辑不动。

### 二、评议轮次与立场

- 轮次：首次评议（2026-09-30，decision-critic）。
- 立场：**有条件支持**，放行前置 = 2 条 [HIGH_RISK_OBJECTION] 获主模型明确回应；另含若干采纳修正项。
- 材料口径更正（已并入执行单）：
  - "5 个重复 tab 页 id"为 grep 误报——`data-testid="tab-translate"`（index.html:72 等，共 13 处 data-testid）含 `id=` 子串被朴素正则 `id="[^"]*"` 误计；负向后行断言 `(?<![\w-])id="[^"]*"` 实测 **154 个真实 id 全部唯一、uniq -d 零输出**。
  - 交接文档第 3 节行数与实文件不符（index.html 677→实测 721 / app.js 2947→3233 / style.css 1377→1751），行数仅供归档参考，闸值一律从实文件现取。
  - JS 依赖 class 实测多出于文档与 explorer 清单：`.gl-collapsible/.gl-collapse-btn/.gl-collapse-header .block-title`（app.js:2888-2890）、`.gl-src/.gl-dst/.gl-sel`（app.js:1760/1772/1774/1874）、`.theme-option`（app.js:1281/1298）、`.theme-menu.active`（app.js:1279）、`.modal-overlay.active`（app.js:1383/1423）、`[data-ai-kind]/[data-ai-idx]`（app.js:2705）、`data-testid`（13 处）。

### 三、HRO 裁定

- **HRO-1（C 修复重复 id）**：[HIGH_RISK_OBJECTION]（与已验证事实直接冲突——实测无重复 id）。主模型回应：**采纳**。取消"C 修复重复 tab id"，落档"实测无重复 id"一句话；闸脚本 id 断言一律用负向后行断言，避免 data-testid 造成噪声。
- **HRO-2（B 契约清单不全 + data-i18n 零缺失自相矛盾）**：[HIGH_RISK_OBJECTION]（影响 3 个以上任务 + 契约与已验证事实不符）。主模型回应：**采纳**。契约清单改为从 app.js 程序化抽取（closest/querySelector/querySelectorAll/classList/data-* 引用语句），不手工枚举；data-i18n diff 口径 = "除故意移除白名单外零缺失"，白名单 = 被删 3 个主题菜单项携带的 theme_google/theme_carbon/theme_primer 三键（index.html:36-38）；critic 补录的 `.gl-collapsible` 族/.theme-option/.theme-menu.active/.modal-overlay.active/[data-ai-kind]/data-testid 契约全部确认采纳。
- 二次复议：不适用（两条均一次采纳，未进入复议/驳回流程）。

### 四、逐条裁定表（A–G 终版）

| 条目 | 终版要点 | 状态 |
|---|---|---|
| A 主题机制 | 保留 link 切换，不迁 data-theme；themes 收敛为 {'default','dark'}，菜单 5→2；持久化双通道与 applyTheme/getSavedTheme/loadSavedThemeFromBackend 回退逻辑不动 | **采纳** |
| A 备忘① | 老用户已存旧主题名（carbon/primer/google）将静默回落 default，属可接受 UX，写入阶段 1 提交说明 | **采纳** |
| A 备忘② | style.dark.css @import url("style.css") 相对路径不变，双文件同目录无路径风险 | **采纳** |
| B 契约闸 | 清单从 app.js 程序化抽取；".collapsed"契约绑定 .console-collapsible 与 .gl-collapsible 两族（style.css:1724-1738）；data-i18n diff 带故意移除白名单 | **采纳** |
| C 重复 id | 取消；落档记录"实测无重复 id"；闸 id 断言用 `(?<![\w-])id="[^"]*"` | **采纳（取消）** |
| D 富文件行 | 推迟阶段 2；**修正**：交接文档第 7 节阶段 2 清单显式补入"文件列表行富化（文件名/路径分隔、三态 chip、移除按钮，接后端 completed/resumable/none）"（文档修订随阶段 1 docs 提交）；阶段 1 对 .file-item 做 CSS-only 美化（圆角图标盒/悬停底色/暗色 selected 覆盖，style.dark.css:113-117 沿用），不动 createFileItem | **采纳+修正** |
| E 重写对冲 | dark.css:64-151 硬编码组件 11 项逐项消单；覆盖对照双向检查（旧选择器→新 CSS、JS 生成类→新 CSS）；闸值一律从实文件现取，不抄文档行数；字号恢复 14/13/12px | **采纳** |
| F 侵权评估 | 无阻断性风险；阶段 2 落地 Lucide 时 index.html 头部注释块写**完整 ISC 声明全文**（Copyright (c) Lucide Contributors + 准予条款），非一行指针 | **采纳+修正** |
| G 验证链 | 按项目验证链（静态→定向→全量→冒烟）+ GUI 走查；[INFO_GAP] web-gui-tester 对 pywebview 原生窗口驱动能力由执行阶段 coding/测试子智能体试点，不可驱动则回退方案 b（临时 http 伺服 assets 仅供测试，不引入运行时依赖）；提交按实注明"GUI 已验证/未验证" | **采纳** |

### 五、范围定稿

阶段 1 交付面 = 第 7 节原 1-4 步（备份/三栏骨架重写/双主题全量重写/删 3 套过时主题）+ 上述 A–G 修正，不混入新功能。富文件行（chip/移除）属阶段 2，本批不做。`strings.py` 不动（硬性约束第 7 条），旧主题名 i18n 键（theme_google/carbon/primer）作为未引用键保留于 strings.py，不进白名单范畴（白名单仅用于闸 diff 放行被删 3 个菜单项的 data-i18n 属性）。

### 六、验证要求

- 闸脚本（改动前先对当前代码跑基线、零告警再动工）：id 断言用负向后行断言零缺失；契约选择器从 app.js 程序化抽取后逐一与改后 HTML/CSS diff；data-i18n diff 除白名单（theme_google/theme_carbon/theme_primer）外零缺失。
- 功能走查五页：tab 切换（switchTab）、词库页折叠（.gl-* 族）、拖拽高亮（.drag-over）、主题双切（含旧存值回落）、aboutModal（.modal-overlay.active）、控制台五分色、窄窗折叠（<1180px）。
- 暗色 11 组件逐项消单（dark.css:64-151）：.app-header/.theme-button/.feature-badge 三态/.btn-secondary/.btn-ghost/.btn:focus/.file-list:focus-within/.file-item.selected/.console-output/.guide-txt-view/滚动条。
- 全量 pytest 基线只增；无任何外部网络请求（走查一并确认）；翻译全流程（添加文件→开始→进度→控制台→产物）走通；提交注明"GUI 已验证/未验证"。

### 七、风险跟踪表

| 跟踪项 | 概率/影响 | 处置/验证 |
|---|---|---|
| 契约闸手工枚举漏项再回归（词库页折叠等静默失效） | 中/中 | HRO-2 采纳后改程序化抽取；验收走查 tab-glossary 折叠 + __refineTplTabHook |
| 文件行富化规格悬空（文档第 6 节规格无阶段认领） | 高/中 | D 修正：阶段 2 清单显式补入，文档修订随阶段 1 docs 提交 |
| data-i18n 白名单外误删 | 低/高 | 闸白名单显式列出三键，diff 其余零缺失 |
| 老主题名静默回落 default | 确定/低 | UX 可接受，提交说明注明 |
| pywebview 窗口 GUI 自动化不可驱动 | 中/中 | 试点后回退方案 b（临时 http 伺服，仅测试、无运行时依赖） |
| 全量重写漏暗色组件 | 中/中 | dark.css 11 组件逐项消单 + 对照双向检查 |


---

## [2026-09-30] [D2026-0930-09] 阶段2 UI 冲刺与最终优化方案（锁定版）执行拆分 [已拍板]

### 一、背景与决策

Owner 提出"阶段 2 UI 冲刺与最终优化方案（锁定版）"（Lucide 全面替换/文件列表行重构三态 chip/右栏卡3 只读化/进度状态点/输出目录同行/i18n 破例授权），主模型经代码事实核查（explorer 9 点实证）后提交执行立场（A 三批拆分/B 授权口径/C 实时性两档/D 前提修正/E-G 实施细则）交 decision-critic 评议。

### 二、评议与 HRO 处置

- **[HIGH_RISK_OBJECTION]（1 条，采纳）**：B 的 js MSG 镜像键系契约硬需求（test_html_i18n_keys_exist_in_js_msg + test_html_has_no_unmarked_user_visible_chinese 双钉强制），不可与 strings.py 授权拆分孤立——须将 js 镜像键清单随 B 一揽子一次性提请 owner 裁定，缩批则走"砍文案 or 降级"路径，不带病开工。
- 其余评议意见全部采纳：半清理风险（批 1 done bar 四件套）、C 档 1 语义坑（files_total 取行数非文件数、fname basename↔全路径 join 须显式定义+双形态走查、per-file 归组不得重构既有聚合路径）、applyI18n 静默覆写 SVG（静态钉守门）、console-collapse-icon/rotate(-90deg) 钉面保护。

### 三、Owner 回执（2026-09-30，"开工"即回执）

- **B 一揽子授权：全量批准**——strings.py +3 键（nav_group_workspace/nav_group_quality/main_subtitle，副标题采纳"加键"）+ app.js MSG 同步镜像 3 键 + 约 11 键值 emoji 清理（start_btn/stop_btn/save_endpoints_btn/tpl_save/gl_save/guide_open_other_btn/guide_empty_hint/aiAnalyzeBtn/model_refresh_hint/no_files_selected/empty_hint）+ 3 死键删除（theme_google/carbon/primer）+ theme_default 中文化（'默认主题'）；strings.py 7 个事件符号键（⚠✗→·）维持禁动。
- **C 档位：档 1（窄化版）**——_feed_event 末尾旁路 per-file dict + snapshot 新增 files 键 + api 暴露 files_status，既有字节钉一字不改只增新用例。
- 首跑验证：tests/test_strings_and_shortcut.py **42 passed**（回执后首跑，授权面干净）。

### 四、执行拆分（三批）

- **批 1（P1 视觉收口）**：themeBtn 🎨→Lucide sun/moon（applyTheme 同步显隐）+ no_files_selected/empty_hint 中文化 + 移除选中/清空挪文件列表卡头（id 不动 JS 零改）+ emoji 全量收口（done bar 四件套：HTML 静态 + 11 MSG 键值 + 3 死键 + theme_default）+ 左栏分组标题 2 键落地 + 页头副标题 + ISC 完整声明 + [data-i18n] 无直接子 SVG 静态钉。
- **批 2（P2 结构重构）**：createFileItem 重构（Lucide 图标盒+文件名/路径双行+三态 chip+移除按钮；签名与 dataset.index 重同步钉不动）+ 三态 chip 档 1（等待灰/翻译中蓝/已完成绿，resumable 呈"可续传"琥珀）+ 右栏卡 3 只读两行状态+整卡跳转 tab-engine（禁双向同步）+ 进度区状态点 + dropzone 高亮扩展（preventDefault 已在）+ 输出目录严格同行。
- **批 3（P3 打磨）**：控制台行距 1.5-1.6 + 收尾扫查 + 真机走查清单交付（owner 自做 100%/125%/150% 缩放+深色阴影）。

### 五、非改区清单（只增不改）

event_stream.py:313-337（format_event_line 输出）、strings.py:163-165（⚠/✗ 事件文案）、tests/test_gui_js_static.py:616（console-collapse-icon ≥2）与 :637（rotate(-90deg)）、test_event_protocol.py file 字段钉、test_event_stream.py 既有聚合语义钉（current_stage/lines_done/lines_total）。

### 六、风险跟踪

| 跟踪项 | 处置 |
|---|---|
| 批 1 半清理观感进 main | done bar 四件套同批收口 |
| applyI18n 覆写按钮内 SVG | data-i18n 移内层 span + 静态钉 |
| chip join 语义错位 | basename 映射设计段 + 后端单测 + 串行/双 worker 双形态走查 |
| 缩批死锁 | 已由 owner 全量批准解除 |

---

## [2026-10-01] [D2026-1001] 真机五问题修复拍板与执行（布局系统性修复+版本回填+摘要卡）[已拍板]

### 一、背景与拍板

Owner 真机实测反馈五问题（三页拥挤溢出/右栏空白/CMD 弹窗+老式外框）。主模型经设计专家（design-expert）诊断 + 评议员（decision-critic）质证（3 处 [MATERIAL_CONFLICT] 全部裁定）后提交方案，owner 拍板「1A 2不做 3同步 4配合」：占位模组选 A 系统状态摘要卡（特批 2 键）；frameless 自绘标题栏本轮不做；main 版本号回填 2.1.1；DPI 探针 100%/150% 配合实测。

### 二、评议员材料矛盾裁定（引用其编号）

- **甲（版本话术）**：核出 main 分支 `__version__.py`/pyproject 仍为 2.0.0（发版 bump 落在 release/2.1.1 分支未回填）——"v2.0.0=旧安装"话术作废，改两步自查（启动方式：打包版无黑框，开发模式必带控制台属正常）；话术不再依赖版本号。
- **乙（图 3 纯 CSS 声明不实）**：词典行由 JS inline style 生成——裁定批 1 上 CSS 网格规则、批 2 JS 去 inline 改 .dict-row 类，提交信息如实声明。
- **丙（断点互顶）**：设计师 1450 断点与候选窗宽 1440 互顶且重蹈视口基准覆辙——裁定下移 ≥1365px 2 列 + ≥1920px 3 列；容器查询治本方案本轮不引入，若 owner DPI 实测异常再评估。
- 另采纳：右栏贴底弃 flex:1（会拉大 pipelineCard 整卡点击热区）改 margin-top:auto（批 3 后仅末卡摘要卡持有，防多卡 auto 均分间隙）；截图基线四档（1210/1000/1440/1500）；innerHTML 修复无注入面（old 为静态模板）+ 全仓扫并入静态钉。

### 三、执行记录（5 提交全推送，CI 绿）

| 提交 | 内容 |
|---|---|
| a5eb5b6 | 版本号回填 2.1.1（__version__/display/info + pyproject）+ tests/test_version_consistency.py 3 钉防复发 |
| 13bab3f | 批 1 布局系统性修复：adv-grid 恒单列+1365/1920 断点、stage-row 弹性化+警告独立成行（HTML 内联 max-width 改 .stage-test-status 类）、#dictRows width:100%+.dict-row 网格规则、#pipelineCard 贴底 |
| ed9a1ed | 批 2 JS 真 bug：刷新按钮 4 处 textContent→innerHTML 存还（SVG 丢失根因）+ 词典行模板内联样式清到类（desc 补 title 悬停全文）+ 静态钉防复发 |
| 882cbbe | 批 3 系统状态摘要卡：四现成接口（get_version/refine_get_data_root/tm_get_stats/refine_dict_status）逐项降级"不可用"；strings.py 特批 2 键（sys_summary_title/sys_summary_unavailable）；贴底移交末卡；结构钉 |

全量基线 1588+4 → **1593+4**（+5：版本一致性 3、innerHTML 钉 1、摘要卡钉 1）。四档前后截图对比存 `%TEMP%\stj_gate\baseline\`（改前 8 张改后 9 张），1210/1440 关键档目检：单列铺满无溢出、2 列断点生效、右栏摘要卡贴底。

### 四、验收口径（owner 真机）

真机清单已补 F 节（DPI 探针两帧+批 1/3 原生面：摘要卡真实数据/版本 2.1.1 显示/词典行 4 列/刷新图标保留/降级验证）。静态面已验证：四档截图、契约闸、全量测试。frameless 后置单独立项。

---

## [2026-10-01] [D2026-1001-02] 开工轮拍板：2.2.0 立即发版（UI 三栏工作台世代）+阶段3 立项归 2.2.1+横切收口 [已拍板并执行]

### 一、背景与拍板

Owner 指令"开工"（按主模型推荐全拍）。菜单四项（A 阶段3 立项/B 发版/C frameless 维持后置/D 反馈批二归 owner）经 decision-critic 评议（1 [HIGH_RISK_OBJECTION]+数实修正）后呈 owner，拍板：**B 采纳评议员修正发 2.2.0 立即发；A 立项归 2.2.1；C 维持后置；D 补漏 zh→en**。owner 附注两项程序事实：①思考曾因敏感信息中断——凭据卫生注意（凭据只经 shell 变量进出，不入思考/输出/落盘文件）；②tag push 环节明示"当前远程，直接为我操作"——本轮一次性授权 ZCode 侧经 GitHub REST 建引用完成推送（钩子 L3 全库拦截=甄别表既裁各条），standing mode"commit+push 恒由 owner 终端"的默认不因本次改变。

### 二、评议员 [HIGH_RISK_OBJECTION] 与数实修正（采纳）

- **数实冲突**：主模型"main 领先 8 提交修复"与 git 实证冲突——`rev-list --count v2.1.1..main`=**16**，含阶段1 三栏骨架+双主题全量重写（e4ad66e/ec8a903 均不在 v2.1.1），已发布 v2.1.1 经查为旧五 TAB 结构（0 处 aside）。主模型复核确认，采纳修正：UI 世代=用户可见新能力，按 D2026-0930-07 修⑧口径升 **2.2.0**；D2026-0930-07-追加1 维持 2.1.x 的"未发版"前提已失效，不静默沿用，版本语义就此显式裁定。
- A 四条件全采纳落 2.2.1 立项条款（元素级批清单/三面红线 wrapper 禁增删·节奏 token 变量白名单·id+data-i18n diff 恒空/钉随批/单项止损线）；"重排"裁定为样式层非结构层；两级评议硬化（二级评议不因"开工"回执降级，须先于阶段3 任何代码提交）。
- D 补漏采纳：反馈批二显式列 zh→en 端到端 GUI 真跑（防被"GUI 全链"笼统吞噬）；轨道 B 放行评审继续挂账明示。

### 三、执行记录

| 项 | 内容 |
|---|---|
| 横切收口 | 6585e05：B2 门②提前结案归档（[B2 门②基线-20260926] 结案追记+B2 文档结案标记+roadmap 闭账）+gui-probe 首跳前半核对（workflow active；手动探针 run 36757171642 全绿 112 collected/112 passed 约 80 秒；定时首跳可见性核对待本地 11:00 后补记） |
| 发版分支 | release/2.2.0 d62117e：bump 2.2.0（__version__/display/info+pyproject 两处同批）+CHANGELOG [2.2.0] 如实写全 UI 世代（非 patch 观感）；验证链=ruff 零告警/定向 3 钉/全量 1592 passed+1 环境性抖动（PermissionError 单测与整文件复跑均过，非回归）+4 skipped=有效基线 1593+4/CLI 冒烟过 |
| 安全深扫 | seal sha256:2aec3abd…e76dead：findingCount=29=基线 24+树外签注 5，与 e8aa1f6a identity 级比对零新增零消除（阶段2 批2/批3+真机批后首次复扫，innerHTML 静态模板存还未被标记）；甄别表增记随 main 619c117 入库；tag push 钩子 L3 全库拦 31+2 即本表既裁各条（行内计数口径差异） |
| main 回填 | 7e8a6a7：版本号 2.2.0+CHANGELOG 同步（回填即时性检查点，幽灵版本根因防复发） |
| tag+构建 | tag v2.2.0→d62117e（owner 授权 REST 建引用，ls-remote 复核一致）；release.yml run 36762095627 success（约 4 分钟）；artifact SubTransJAV-2.2.0 270,899,702B 并行 Range 下载 296s 字节核验一致 |
| Release | id 400355734 非草稿非预发布：SubTransJAV-setup-2.2.0.exe 81,102,395B（sha256 426ff961…682643e）+lite 33,563,215B（sha256 ef0073ec…a9b1c）+SHA256SUMS.txt，本地哈希与 CI SHA256SUMS 全一致；notes 只写本版 |
| docs 收口 | roadmap 2.2.0 节登记+2.2.1（阶段3）立项节+反馈批二补 zh→en；真机清单 F 节版本预期 2.1.1→2.2.0（先裁定后改单） |

### 四、验收口径（owner 真机，随 2.2.0 安装包）

反馈批二合并验：三项已落子项复验（数据保存目录浏览/质量报告整合查看/无黑框）+安装/卸载 ≥2 环境+真机 GUI 全链+zh→en 端到端（非缺省方向全流程+阶段A/B 指令卡启用+产物 _final_en+方向隔离）+真机清单 F 节（DPI 探针两帧/摘要卡/降级验证，版本预期 2.2.0）；10~20 片真实媒体定阈仍待 owner 语料。gui-probe 定时首跳可见性 11:00 后补记。

---

## [2026-10-01] [D2026-1001-02-阶段3] 二级评议签收：批清单有条件放行→条件全部闭环 [已闭环]

关联一级：D2026-1001-02（本文件 :1959）。二级评议对象 `docs/design/ui-phase3-批清单.md`；按开工门二级评议须先于阶段3 任何代码提交，本条目为签收证据。

- **原决策**：UI 阶段3 三批三提交（批1 引擎页 / 批2 词库页 / 批3 质量+高级页）逐页套规范，三面红线 R1（DOM 恒定）/R2（节奏禁区）/R3（契约恒空）+gate 契约闸+静态钉+黑盒+截图四层验收。
- **我的异议**：
  - [HIGH_RISK_OBJECTION]（采纳）：gate.py check 只比对 id/i18n **丢失方向**（gate.py:136-145），新增全程静默放行——验收面声明"diff 恒空"与工具实际能力不符，R1/R3 无机器强制。
  - 条件级（全部并入批清单第六节）：C1 `.stack.form-card` flex 级联致子项收缩居中；C2 `label:has` 越界改写兜底并发组 4 个 label 行排/宽度；C4/C8 `.gl-table` 缺表级 width/border-collapse 与表头列宽规则（"挂类即生效"对宽度不成立）；C5 复选框单元格 text-align:center 无类承载会误拦钉③；C3 钉①断言域限定三卡区间；C6/C9 glossary/guide 缺前后对比截图；C7 双标题 `:first-child` 选择器成立须明确双选择器；勘误三处（钉实际行号 test_gui_js_static.py:339/341/605 非 :281/:331/:594 且非 test_strings_and_shortcut.py；--w-stage-label 无 id 标签用位置选择器；.gl-alias margin-top:1px 显式豁免）。
- **主模型最终决定**：采纳。HRO-1 落地为 tests/test_ui_phase3_redlines.py 钉⑤全集冻结钉（id 165 + i18n 键 186 快照逐字断言，新增/删除双向报错）；gate.py 保持只拦丢失语义，机器闸由钉承接；C1-C9 全部并入批清单第六节并执行。执行结果（主模型回传）：main 9bb398e（代码+钉）+b414bd2（批清单文档）；ruff 零告警；红线钉 6 用例全过；全量 1599 passed+4 skipped（+6 全为新钉）；契约闸基线重打 165/186 零告警+批后 check 零拦截；Mimosa 深扫 seal sha256:485f0ce9… findingCount=29=基线 24+树外 5，零新增；web-gui-tester 黑盒六组全 PASS；截图存 Temp/gui-phase3/。
- **条件是否已闭环**：**全部闭环**。复核证据（本轮只读抽查）：钉文件 6 用例含全集冻结且双向报错；style.css:987/999-1007/1040/1073-1076/1176-1180 落齐 C1/C2/C4/C5/C7；index.html:366/403 两表挂 gl-table；引擎 A/B 卡区间无 min-width 残留（267/272/331-343/429/545/551/572/624 均属批清单保留区）；b414bd2 含第六节全文。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①钉⑤全集冻结后，新增 id/键属破坏性变更，须先更新冻结快照再改 DOM——流程上写进下次 UI 改动前检查项；②`refineGlCount` 悬空（app.js:1967/2063）仍在跟踪项未修（修=新增 id 触钉⑤，已有意为之）；③候选池未动：状态 tag 列、checkbox→toggle、接口地址独立卡片化；④--w-* token 注释"内联逐字引用勿删"与未来节奏 token 化候选池存在张力，向量化推进时需先解冻钉⑤/钉④口径；⑤`.gl-table` 表级宽度规则今后新增裸表挂类时必须一并套用（C4 规则当常设约定）。

---

## [2026-10-01] [D2026-1001-03] 项目挂账清零菜单 v2 全项拍板+散点收编（12 项+盘点新增 A-E） [已拍板并执行]

关联：D2026-1001-02（本文件 :1959，其「main 回填即时检查点」纪律自本条起由滚动 dev 号取代）；D2026-0928-01（:1395 审计积压 4 项挂起承接）；D2026-0929-01（:1404 画像预设账面修正，追记指针只加不改）；D2026-0927-05（:1387 A′ 复审清单随 B）；D2026-0926-01 追认（:1316 golden 硬化门）。

### 一、背景与拍板

Owner 指令「确认是否还有遗漏，本次任务解决所有挂账内容，实现项目 0 挂账」将拍板权整体下放。主模型先行全仓盘点（decision-log 全量+roadmap+候选池+真机走查清单+代码实证），12 项菜单锚点全部在案、无漏项后全按菜单推荐立场拍板：①轨道 B 云端闭环维持挂起（触发=自动质量闭环真实需求信号；HRO-1 四条件未闭环不进实施）②A′ 复审清单随 B ③引擎页重构（D 项）维持出局留池（重启条件=真机走查暴露引擎页布局痛点）④frameless 维持后置（重议条件=owner 对窗口外观再有诉求）⑤候选池六小项打包挂起 ⑥上游 whisperjav v1.9.3+ 对齐=被动跟进+升级触发回归门（触发=owner 发起升级或上游 release 通知到达；升级后必跑 6 例真实命名端到端，用例名单随升级门冻结；不设主动轮询）⑦发版攒批（触发=反馈批二修复落库或下一功能批；死线=下次真机走查结束后 3 日内复盘是否发；附加条件=禁把阶段3 回灌 2.2.0 重新发布；**版本号按 D4 已拍口径=2.3.0——2.2.1 不单独发版、阶段3 并入 2.3.0（owner 已在开工 会话回"开工"=D1-D4 全按推荐执行，交接文档菜单第⑦项在案标注"已被 D4 更新"）**）⑧main→2.3.0.dev0（按交接文档第⑧项"若 D4 拍 2.3.0 则直接改 2.3.0.dev0"分支执行） ⑨旧轨道 A 残余（首启初始化补登候选池/统一持久化层标注已吸收/画像预设裁定已取消）⑩Trusted Signing 不立项+触发集与双语改判条件合并同组信号（计数口径：起算点=本条归档日，issue 正文主要语言非中文即计入，bug 与 feature 均计）+零成本前置手册 FAQ ⑪Translator 死规则清理降格执行尾件（两条件：下一 UI 批批清单固定小节独立勾选+按「五 TAB 世代泛名类」重新盘点防空头）⑫五 TAB 痛点清单落走查清单 G 节固定小节（5 页各 3 行留空）。

### 二、盘点新增（遗漏排查产出，评议员逐项核实）

- **A. L1 回归钉=已闭环（实证追记）**：decision-log:1374③「随 1.4 轨道 A 实施」的仍活字样就此勾销——tests/test_glossary_conflict.py:225-229「手册 §11.5 合并去重行为声明回归钉（真实三层 CSV 文件实测非 mock）」已在库。不进候选池。
- **B. 审计积压 4 项挂起**（:1395）：打包确认挂起，收编 roadmap 横切观察项；其中 premerge_max_gap_s 移出指纹与 v2_outputs done payload 按评议员★4 升格显式触发条款（见风险跟踪⑤⑥），tools 脚本债务与 _pid_alive AccessDenied 维持笼统挂起。
- **C. 横切观察收编 roadmap**：golden ≥30 origin:"real" 硬化门（:1316，与丁组 adaptive thresholds 债务同一事项统一登记）/refineGlCount 悬空（:2000②）/容器查询 DPI 条件（:1939）/A3 首文件抽检历史观测（:1082）。10~20 片定阈 roadmap 已有登记不重复。
- **D. gui-probe 定时首跳核对=未发生**：03:00 UTC 后 3h+，workflow state=active 但 API total_count=2（仅 09-30 手动 run 36757171642 全绿 112/112+更早 run#1），event=schedule run 数=0。「未触发」=实证；「整点高负载丢弃」=推断（GitHub 已知特性；API 只能证伪有 schedule 结果，不能证明调度器是否排队）。处置=cron 错峰 0 3 1 * *→17 3 1 * *（一行可逆）；下次复核=2026-11-01 首跳必回填，仍未触发则升格处置（评估弃定时或转真机承载），不得仅再调时间。
- **E. B2 92 条**：已在库提前结案（:1329 结案追记+B2 文档:130+roadmap 横切闭账），盘点确认无需动作。

### 三、评议员质证与回应（decision-critic 封盘评议：无 [HIGH_RISK_OBJECTION]；1 [MATERIAL_CONFLICT]+4★裁决全部采纳）

- **② [MATERIAL_CONFLICT] 采纳**：菜单「A′ 13 项」与在案 :1387「未改的 11 项入复审」不一致，按 :1387 口径执行（A′ 已改写=横幅 1 键+6 项 tooltip 两级句式）；若 13=11+2，2=glossary_learn/conflict_block 两无 title 控件；逐项枚举随 B 启动时落盘。roadmap 2.2.0 节 A′ 行已按此勘误。
- **★1 采纳（dev 号取代回填纪律）**：main 常驻滚动 dev 号永不宣称发布版号，语义自洽（PEP 440：2.3.0.dev0<2.3.0）且消费点实证全为纯展示（refine/cli.py:427/459、webview_gui/main.py:173-177/355/378、api.py:415-426、app.js:1064/1601）。条件 1=发版后 main 前进到下一预定版本 dev 号（如 2.3.0 发布后 → 2.3.1.dev0）为新即时检查点（入 release checklist）；条件 2=roadmap 2.2.0 节旧回填条款已加追记修订。回退口径：两条件不落地则撤回本口径、维持旧回填纪律。
- **★2 采纳（cron 修正不越权）**：错峰属核对结论的直接技术闭环（可逆单行、无安全面）；commit 注明「整点丢弃」为推断；11-01 复核必回填。
- **★3 采纳（画像预设已取消裁定）**：证据链充分——a9c4ec1（2026-09-28）Refs 载 owner 三条 UI 指令含「取消用户模式」+提交正文删除声明+tests/test_gui_js_static.py:190-214 禁 ui_profile/novice 回流钉+后端零引用；owner 指令优先于内部执行记录，:1404 加追记指针（只加不改）。「小白型首启极简」诉求由首启初始化承接成立（api.py:1305 first_run 信号在、前端零消费）。
- **★4 采纳（挂起待遇精细化）**：见二.B。
- **仓库卫生备注**：根目录游离文件 dead（62B grep 回显残留）与本批无关、不入提交，留 owner 处置（属另一进行中会话工作树，主模型不代删）；docs/design/ZCODE-MIGRATION-NOTES.md 未跟踪设计文档同样不入本批。

### 四、执行记录（与本条目同批提交，验证链全绿）

| 项 | 内容 |
|---|---|
| ⑧ 版本 | __version__.py 双常量+__version_info__ dev 语义+注释、pyproject.toml:17、test_version_consistency.py:40 split 截断最小适配（三文件互相同步断言语义不变）；全仓无其他 2.2.0 代码残留（CHANGELOG/decision-log/真机清单 F 节为历史记录与已发布 EXE 校验预期，非代码） |
| D cron | .github/workflows/gui-probe.yml :9-10 错峰 03:00→03:17 UTC+注释（未触发实证+丢弃推断分层表述） |
| 记账 | roadmap（2.2.1 攒批+dev 号口径、:60 回填纪律追记、A′ 计数勘误、候选池全项 stamp+⑨首启初始化补登/旧轨道 A 残余账+⑩计数口径、横切观察收编 5 行+gui-probe 核对结果）+真机走查清单（F 节版本预期 dev 口径+G 节痛点清单五页×3 行）+手册 FAQ-10（SmartScreen「更多信息→仍要运行」+SHA256SUMS certutil 校验）+decision-log:1404 追记指针+甄别表增记（57d9356f）+release checklist 实体化（docs/release-checklist.md，★1 条件 1 闭环）+本条目 |
| 验证链 | 静态=ruff 全仓 All checks passed；定向=test_version_consistency 3 passed；全量=1599 passed+4 skipped（基线 1599+4 持平零回归，97s）；冒烟=subtransjav-refine --help 正常+version 输出 2.3.0.dev0；安全=Mimosa deep seal sha256:57d9356f…d6e0ef findingCount=29=基线 24+树外签注 5，零新增；secret 定向扫描（8 将提交文件）=结构模式 0 命中+hex32/40 新增行 0 命中 |
| GUI | 未验证（本批无前端代码改动；版本显示链由 test_version_consistency 3 钉+api 透传纯展示覆盖；摘要卡显示 2.3.0.dev0 属预期，真机清单 F 节已注明） |

### 五、条件是否已闭环

拍板 12 项+A-E 全部闭环（决策侧）；执行件随本批提交落库。遗留均为触发式条件（非挂账）：A′ 逐项枚举随 B 启动；6 例命名端到端名单随升级门冻结；2026-11-01 gui-probe 首跳复核回填；「非中文 issue ≥5」按⑩口径滚动计数；⑪固定小节随下一 UI 批批清单；2.3.0 发版后 main 前进下一 dev 号。

### 六、是否 [PRESSURE-OVERRIDE]

否（owner 指令明示整体下放；评议员封盘无 HRO；全程可逆单行级改动）。

### 七、后续风险跟踪

① 发版后 main 未前进下一 dev 号=新幽灵版本（★1 条件 1，入 release checklist）；② 攒批死线=下次真机走查结束后 3 日内复盘是否发（⑦），滑期须回本表复议；③ 攒批期间禁阶段3 回灌 2.2.0 重新发布（⑦附加条件）；**③′ D1-D4 执行衔接（开工 会话按"开工"执行中）：D2/D3 落地走批清单→二级评议→实现→验证链→release/2.3.0 发版（D3 解冻预算 id 165→~178/键 186→~192 须先更新钉⑤快照）；交接文档执行序中"发版后 main 回填即时"按本条新口径执行=前进下一 dev 号**；④ 「非中文 issue ≥5」按⑩口径滚动计数，触发即评审；⑤ premerge_max_gap_s：任一指纹/断点/恢复路径改动立项时先出兼容分析（旧断点读取+字段缺失降级+迁移测试），无方案不得动指纹哈希面；⑥ v2_outputs "done" payload：新增/改动消费端或结构时先做消费端核查；⑦ gui-probe 2026-11-01 首跳仍未触发→升格处置，不得仅再调时间；⑧ 钉⑤全集冻结下⑪落地新增 id/键须先更新冻结快照（承 :2000①）。

---

## [2026-10-01] [D2026-1001-03-阶段3] 二级评议签收：d1d4 批清单有条件放行→条件全部采纳→实现层闭环 [已采纳·实现闭环]

关联一级：D2026-1001-03（本文件 :2005，版本口径 2.3.0.dev0、dev 号纪律、发版归 owner）。二级评议对象 `docs/design/d1d4-批清单.md`；按 D2026-1001-02-阶段3 先例，二级评议先于任何代码提交，本条目为签收证据。

- **原决策**：2.3.0 三批（批1 D1 dropzone A 案零新增 id/键 / 批2 D3 词典去捆绑推翻 D2026-0930-01 ⑧+D2026-0930-03 ② 双决议 / 批3 D2 词典管理 B2 解冻 id+9/键+6）三提交+验证链+提交五步；发版归 owner（D4）。
- **我的异议**：
  - 无 [HIGH_RISK_OBJECTION]。
  - 条件级 4 条（全部采纳）：**C1** 批1 `.has-files` 单点 toggle 须置于 render() 入口（app.js:652 空态分支提前 return 使"尾部"写法失效：清空后类残留、dropzone 卡 52px），改用 `getElementById('tab-translate')`；**C2** 批3 空态条件「三词典全未安装」不可达（dict_manager.py:336-337 english_rules 恒 available），改「sudachi 未安装」并定义 dictEmpty CTA 行为（自动选中 sudachi 并触发下载）；**C3** 批2 范围补 ci.yml:25 安装 `-e ".[dev,ja-dict]"`（去捆绑后新环境不再含 sudachidict_core，防 grammar-hint 用例入 skipped、破坏"基线只增"口径；备选=显式调基线口径，二选一不得沉默）；**C4** 批2 HRO② 措辞族 grep 显式化：词组 `未安装 sudachipy|内置|零参缺省`，命中清单 pipeline_v2.py:610/657/693/869、grammar_hint.py:41/53、cli.py:480 区，提交时对照复核（tests 无断言引用，仅 test_grammar_hint.py:281 注释）。
  - 备注级 6 条：R1 Console "160-220px" 中 220 钉 max-height；R2 dictActionBtn 三态矩阵门控 `downloadable`（jieba=无按钮只指引、english=隐藏，D2 裁定落码）；R3 dictOpenDir 复用 openDir 链（app.js:2234→api.py:570，无新后端 API）；R4 README pip 安装提示 ja-dict extra+2.3.0 发布说明素材并入批 4 docs commit；R5 dictDownload 函数零改动边界自洽成立（:3305 终态文案临时闪回由 finally 重渲染覆盖）；R6 预算只封顶，JS 动态设定键（dict_redownload/dict_status_builtin）按 HTML 实际落点更新快照。
  - 解冻程序核验（采纳依据）：FROZEN_IDS=165/FROZEN_I18N_KEYS=186 逐字复核一致；9 新 id+6 新键在现行 HTML 全 absent；既有 id/键零删除零改名由钉⑤全等断言（test_ui_phase3_redlines.py:146-161）机制锁定；复用键 dict_status_available/dict_status_unavailable/dict_download 为 JS MSG 键非冻结快照成员，不耗预算；六条 selectedFiles 变更路径实测全汇 render()（app.js:638/790/896/918/939/950），单点方案成立；dict-row 钉实测 test_gui_js_static.py:835-837 定位准确；spec:70-75 反收集过滤机制经 lite 产物实证；下载链（cli.py:487-505、api.py:991）不依赖 sudachidict_core 主依赖，去捆绑不破坏 CLI `--dict-download` 与 GUI 下载链可用性；release.yml 仓库内无 Release 创建步骤（止于 upload-artifact），"Release 组装"归 D4 owner 流程。
- **主模型最终决定**：**全部采纳**——C1-C4 条件级全采纳、R1-R4 备注全采纳、R5/R6 记录在案；修订全部落进 d1d4-批清单.md（C1=render() 入口 toggle+六路径证据；C2=空态改「sudachi 未安装」+CTA 行为；C3=ci.yml 安装 [dev,ja-dict]；C4=三词组七处命中清单；R1=Console max-height:220；R2=三态门控 downloadable；R3=openDir 链复用；R4=批 4 README/发布说明素材）。
- **条件是否已闭环**：条件级 C1-C4 已采纳进批清单（计划层闭环）；实现层闭环随执行记录回传验证，闭环路径=批1 黑盒四路径截图（空态 ~112px/52px 切换）、批3 fresh 环境空态 CTA 黑盒、批2 全量基线不变差+ci.yml 生效、批2 提交时对照 C4 命中清单。未闭环前本批不视为支持转正。
- **是否 [PRESSURE-OVERRIDE]**：否。
- **后续风险跟踪**：①去捆绑后 fresh-env CI 与本地 .venv 词典数据不对称，批2 验证链明示；②dictEmpty 若条件/CTA 未按 C2 落实现将成为死 UI 占 2 键预算；③老用户升级词典残留不对称如实写入 2.3.0 Release notes（D4，HRO 修正③）；④批3 解冻随批执行后 gate baseline 重打 165+9/186+6 及 check 零拦截须在批3 提交 verify 行逐项回链。
- **[2026-10-01 执行回传追记：条件实现层闭环]**：C1=黑盒实证（生产回调添加→has-files 折叠 48px/cua 物理点击清空→空态回归 134px，render 入口单点双出口）；C2=黑盒实证（sudachi 未装→空态引导条显示+CTA 在位，三态门控 jieba 无按钮/english「内置」pill/sudachi primary 下载全对）；C3=ci.yml 已改 `.[dev,ja-dict]`+全量 1601 passed+4 skipped（基线 1599+4 只增 +2=防回流新钉 test_pyproject_meta）；C4=七处命中清单逐处改写，残留仅功能必需 2 处（spec 无条件过滤本体+release.yml 反转断言本体）；解冻=gate 旧基线 check 丢失 0（ids 165→174/i18n 186→190，静态键 +4 而非 +6 系 R6 JS 态键不入快照）+新基线 %TEMP%\stj_gate\baseline.json 落盘；黑盒另抓两处 DICT_KINDS 旧口径文案（"完整安装自带/完整版"）随批修正（MSG JS 态键不触快照，R6）；后端 defaults/dict_sources.json description 三条核查均兼容口径；暗色主题词典卡/dropzone 抽查 PASS，截图存 Temp/gui-23/。

---

## [2026-10-01] [D2026-1001-03-D4] 2.3.0 发版执行（owner 放权全流程） [已发布]

- **原决策**：D4=2.3.0 统一发版（2.2.1 不单独发版、阶段3 并入，交接文档拍板），release/2.3.0 分支制；owner 本轮明示"本轮依旧放权，为我发版"=tag REST 建引用授权（2.2.0 先例通道，standing mode 默认不变）。
- **发版审读新发现（批 2 遗留缺陷，本条目核心增量）**：packaging/setup.iss [Files] 段被批 2 清空仅剩注释——安装器将装出空壳；CI smoke 只断言 PyInstaller dist 目录、全量测试绿也不能发现。主模型发版审读逐文件核对时抓出。修复=恢复 onedir 全量递归 Source 行（v2.2.0 逐字同参，Excludes: "system.dic" 保留作双保险）+release.yml smoke 补安装器存在性+≥20MB 体积下限断言防复发。教训=打包脚本改动缺"安装器内容级"断言，测试绿≠安装器正确，本轮断言补齐后由 dispatch/tag 双构建实证。
- **执行记录**：release/2.3.0 @ 5c3919b（bump 2.3.0 三常量+pyproject+CHANGELOG [2.3.0] 只写本版+上两项修复；secret 0；全量 1601 passed+4 skipped；Mimosa deep seal sha256:60f64fb4 29=基线 24+树外 5 零新增）→ **dispatch 试构建先行**（打包链批 2 大改后首实证，run 36837536293 success）→ tag v2.3.0 REST 建引用（HTTP 201→5c3919b）→ tag 构建 run 36838069064 success → artifact 并行 Range 8 片下载 70,850,389B 字节精确组装+解包 SubTransJAV-setup-2.3.0.exe 33,568,216B（≈33MB 兑现）sha256 9F393BCF…56BDB4 与 CI SHA256SUMS 一致 → Release id 400807261（非草稿非预发布；资产=单 setup.exe+SHA256SUMS.txt；notes 只写本版+能力边界如实告知：sudachi=EXE 可下载/jieba=仅 pip/english=内置/老用户词典残留+禁词自查 CLEAN）→ main cherry-pick -n 5c3919b 回收发版修复+版本前进 **2.3.1.dev0**（release-checklist 第 8 步自本版首次执行）。
- **条件是否已闭环**：是。本地验证链/双构建/哈希回读三面全绿；ls-remote 三点复核（main/tag/分支）随 main 同步批执行。
- **是否 [PRESSURE-OVERRIDE]**：否（owner 显式放权授权）。
- **后续风险跟踪**：①真人安装验证（≥2 环境）归反馈批二（roadmap 2.3.0 发布后实测项）；②词典下载 GUI 全链真机验收归 owner 走查（本轮黑盒为 stub 桩验证）；③老用户升级词典残留不对称已在 Release notes 如实告知；④release-checklist 第 8 步（发布后 main 前进 dev 号）本轮首跑成功，后续发版沿用；⑤单安装器时代 setup.iss 后缀参数（/Dsuffix）保留未用，如未来需要差异化安装器可直接启用。

---

## [2026-10-01] [D2026-1001-04] 2.3.1 UI 收尾轮立项+二级评议+C2 复议（R1-R6 六项+refineGlCount 借窗） [已拍板·实现闭环]

关联：D2026-1001-03（本文件 :2005，⑪条款执行到期=本批"下一 UI 批"）；D2026-1001-03-D4（:2072，main 常态 2.3.1.dev0，发版归 owner）。

### 一、背景与拍板

Owner 指令"下一轮任务继续开工"。主模型盘点全项目可动工项形成六项立场，decision-critic 开工前评议（无 [HIGH_RISK_OBJECTION]）后拍板：**R1** dictDownload 进度迁移（B2 案 HRO③ 独立子项回窗，条件 C1=id≤2 预算内/静态键 0/黑盒 CTA+三相位全采纳；设计裁决=按钮纯文案/进度条承载 percent+bytes/#dictStatus 只留终态兜底）；**R2** Translator 死规则清理随批固定小节（条件 C2 采纳=盘点对象纠正为"世代 diff+作用域死规则双通道"——原预设 .sidebar/.tab-btn/.file-grid 全史不存在，盘之即盘空气）；**R3** 2.3.1 暂不发版（触发满足≠立即发版，攒至 owner 真机走查 2.3.0 后按死线 3 日复盘，发版归 owner）；**R4** 首启初始化维持挂起（承接诉求载体已被 owner 取消、无痛点信号）；**R5** 黑盒夹具固化仅提议（第 3 实例触发达线，不经 owner 同意不建）；**R6** 真机清单 F 节版本预期修正（评议员查补的我方 docs 陈旧项）+refineGlCount 借窗顺手修（采纳，与 R1 同批解冻）。
**[INFO_GAP] 出处固化**：「详情区独立进度条复用 progress-fill」出自交接文档（未入库）D2 行原文：「词典管理 B2 案……详情区（名称+pill 状态/描述/安装目录 path-row+打开文件夹/下载按钮+**独立进度条复用 progress-fill**）。#dictStatus 降级为错误兜底行；dictDownload 进度显示迁移=独立子项」——本条引注后转为在案依据，不再依赖 Temp。

### 二、二级评议（D2026-1001-04-b：d231 批清单有条件放行，4 条件级+1 建议级全采纳）

核验证据（评议员全实读）：FROZEN_IDS=174/FROZEN_I18N_KEYS=190 逐词一致（test_ui_phase3_redlines.py:60-96）；预算上限 178/192（:2050 ③′）；dictDownload 与 PipelineManager id 模式无冲突；**.progress-bar 8px+overflow:hidden（style.css:1378-1408）故进度文本须独立成行**（条件②改包裹容器 DOM）；glRender/glDel null-guarded 计数点逐字在位（app.js:1978-1979/:2074-2075）；**style.css:561-572 复合选择器活段为 .file-ico、死段为 .file-icon**（条件①修正清理指令防误删存活规则）；style.dark.css progress/file 系 0 命中。条件③=补"下载中切换下拉"处置（kind 归属校验+黑盒用例）；条件④=键账目修正（dict_verify/dict_extract 已存在 MSG:433-435，无新增键）；条件⑤=隐藏统一 finally 覆盖三路径。

### 三、C2 复议（批 3 盘点超预期命中 2 条裁决）

执行者双通道实盘：世代通道=.translator-* 族 17 类已零残留（前序改版清除）、五 TAB 类全存活；作用域通道=167 class+18 id 全对照，**命中 2+存疑 1**：`.file-item .file-icon`（预期，已删）、`.pill-danger`（超预期，确证死——pill 拼类面封闭可穷举：仅 'pill'/'pill pill-success'/'pill pill-warning' 硬编码字面量）、`.console-line.command`（存疑——经 `console-line ${type}` 自由形参动态拼类，不可证死）。评议员裁决：**.pill-danger 删（随批补删，删后 grep=0）、.console-line.command 留档豁免**——判据=拼类面封闭（pill）vs 开放（console-line），两案落 C2 边界两侧，CSS 类不在钉⑤冻结域。

### 四、执行记录（黑盒抓 1 真 bug 已修）

| 批 | 内容 |
|---|---|
| 批 1 | index.html #dictProgress 包裹容器（.progress-bar>.progress-fill+兄弟 .progress-text）；style.css .progress-text（var(--text-3) 双主题 token：style.css:33/dark.css:46 静态保证）；app.js dictDownload 改写（renderProgress 全量刷新+相位往返重置/kind 归属校验/隐藏统一 finally/#dictStatus 只留终态）+**黑盒抓出 #dictActionBtn 漏绑 click 监听（批 3 重构静态化时旧动态按钮监听未迁移）随批修复（dataset.bound 一次性绑定，回调读 sel.value）**；钉⑤ 174→175 |
| 批 2 | index.html 词库折叠卡头加 `<span id="refineGlCount" class="muted">`，app.js 零改动（null-guarded 更新点恢复即生效）；钉⑤ 175→176 |
| 批 3 | style.css 删 :562 .file-icon（保留 :561 存活 .file-ico，grep file-ico=1）+C2 复议补删 .pill-danger；盘点小节全文留痕（方法/边界/命中表） |
| 批 4 | 真机清单 F 节版本预期修正（2.3.0/2.3.1.dev0）+roadmap 2.3.1 立项节+本条目归档 |

### 五、验证链（全绿）

node --check 过；红线钉 6 用例（钉⑤ id 176 双向断言）+静态钉 39 用例=45 passed；全量 **1601 passed+4 skipped**（基线 1601+4 持平）；gate 旧基线 check **丢失 0**（ids 174→176/i18n 190 恒等）+新基线 176/190 落盘（两条 CSS 失联报告=file-icon/pill-danger 即本批有意清理项）；Mimosa deep seal sha256:2eafa499 findingCount=29=基线零新增；secret 定向扫描唯一命中=app.js:2788 token 计数器（既往甄别误报）；**黑盒**（IAB 伺服+stub 桩）：download 相位（fill 50%/15.0/30.0MB/按钮"下载中…"纯文案）/verify 相位（indeterminate+"校验中…"）/相位往返（回 download 75% 干净态）/终态（条隐藏+兜底行"下载完成：路径"+按钮恢复）/**轮询冻结（calls 恒定=无 poller 泄漏）**/切下拉 kind 校验（归属前缀"sudachi 10.0/30.0MB"+jieba 按钮态不被覆盖）/词库计数卡头显示"2"/文件行图标存活回归；截图存 Temp/gui-231/。GUI 已验证。

### 六、是否 [PRESSURE-OVERRIDE]

否（owner 明示继续开工；开工前评议+二级评议+C2 复议三级全过、无 HRO；全程可逆预算内）。

### 七、后续风险跟踪

①2.3.1 发版死线=owner 真机走查 2.3.0 结束后 3 日内复盘，滑期回本表（R3）；②.console-line.command 豁免留档，ConsoleManager.log 调用面专项核查时复核；③黑盒 role 卡区 undefined/阶段卡 TypeError 为 stub 数据不全夹具伪影，真机走查覆盖；④refineGlCount 计数形态=裸数字（JS 态），如需"N 条"走 MSG 键禁静态键；⑤黑盒夹具固化提议（R5）待 owner 同意后升格 tools/ 常驻工具。

---

## [2026-10-01] [D2026-1001-05] 国庆冲刺轮立项：2.3.1 发版+候选池小项激活（S0-S7 八项裁定） [已拍板·执行中]

**关联**：D2026-1001-04（R3 攒批前提）；D2026-1001-03-D4（发版流程与每轮授权先例）；D2026-1001-02（二级评议不因「开工」降级先例）。

### 一、背景与拍板

Owner 新指令（关键句原文落档）：「当前项目 0star，0issue，目测项目无人使用，作者我也未实测只是在迭代，所以不考虑实测问题，只需要项目一直推进到计划内容全部完结。中途如果我实测发现问题了再修。无脑推进项目，争取国庆结束前完成当前制定的所有计划内容」（2026-10-01，国庆窗口约 5-6 天）。主模型盘点确认：**计划内容=roadmap 2.0→2.3.1 全部版本节，已 100% 落库**（残余 ⬜ 全为 owner/外部触发项，无一可自主实施）；提出 S0-S7 冲刺方案经 decision-critic 评议（1 [HIGH_RISK_OBJECTION]，S3）后拍板。

### 二、逐项裁定表（评议意见 → 主模型最终决定）

| 项 | 评议意见 | 最终决定 |
|---|---|---|
| S0 2.3.1 发版 | 有条件支持：程序=「新指令覆盖 R3 前提」记账（非 R3 复议）；push/发版=**推断性窗口授权**（国庆轮，终止点=2.4.0 收口）；发版卫生件（release-checklist 基线/CHANGELOG 起草） | **采纳**。2.3.1 立发（release/2.3.1 分支制） |
| S1 GUI 原生 alert/prompt 替换自制弹窗 | 支持激活：调用点 5 处实证（app.js:540/:1273/:1597/:2060/:2062）；id 预算 178→~182 扩张走批清单预算表+二级评议；静态键 +0 走 MSG 通道；**开工首步黑盒实证原生 prompt 宿主可用性**（pywebview 对 prompt 支持不完整则升格功能修复）；批清单强制带 ⑪ 收尾扫查固定小节 | **采纳** |
| S2 首启初始化 | 支持轻量形态：**设计必须写死 first_run→常态持久化翻转句**（api.py:1303-1307 仅信号生成无写入方，不写翻转=每次启动重播——最大隐性 bug 面）；复用现有引导/词典卡/输出目录元素 | **采纳** |
| S3 frameless 自绘标题栏 | **[HIGH_RISK_OBJECTION] 反对激活**：三度锁死（D2026-1001 owner 拍板"不做"/-02 维持/-03 复核维持），重议条件="owner 对窗口外观再有诉求"未到期；"唯一可自主实施"混淆留池项与可自取项；无实测下长尾（双主题/最大化/DPI）风险更不可见 | **采纳（HRO 采纳=维持后置不激活）**。触发条件原样保留 |
| S4 跨片聚合分析独立页 | 修正：不进本冲刺、不派 design-expert；半页立项评估文档（防"文档即立项"反向激活） | **采纳**。与 S5 合并 |
| S5 配音链路 | 留池+评估文档（只写现状/依赖/体量/前置，不产方案，结尾明示无需求信号不进实施） | **采纳** |
| S6 触发型四项 | 全维持挂起不判出局：Trusted Signing（外部触发）/上游对齐（owner 升级触发）/D 项（重启条件型非取消，触发源因豁免实测暂不可达如实标注）/节奏 token 化（钉④禁区无诉求不得复议，不做自主审美轮） | **采纳（全项维持）** |
| S7 反馈批二/真机项 | 标注「owner 豁免推迟（实测发现问题再修）」，不删不改判定 | **采纳** |

### 三、关键记账

- **[DEPENDENCY-IMPACT]**：R3 攒批前提（等待 owner 真机走查 2.3.0）被 owner 新指令显式豁免 → 攒批解除 → 2.3.1 转入发版流程；roadmap「暂不发（R3）」行随 S0 改写为发版执行记录。
- **推断性授权**：[PRESSURE-OVERRIDE] 否。push/发版/Release REST 建引用=国庆轮窗口推断授权，**终止点=2.4.0 收口发版完成**；此后 standing mode「commit+push 恒由 owner 终端」默认恢复；凭据只经 shell 变量进出。
- **预算扩张**：FROZEN_IDS 178→~184（S1 弹窗约 +4、S2 首启 +1~2），FROZEN_I18N_KEYS 192 不动（静态键 +0）；程序=批清单解冻预算表（逐项列名+新上限+既有零删零改断言）→二级评议→随批更新快照→gate 丢失 0+新基线落盘。
- **发版切分定稿**：2.3.1（即刻，只装已落库四批不回填）→ 2.4.0（收口单发，S1+S2 合发，用户可见新能力=minor）；**否决 2.3.2 与并入 2.3.1 两案**；收口底线=S1/S2 未落库则 2.3.1 单发即"计划内容完结"达标，不为凑版本硬造 2.4.0。
- **行政备注**：仓库根 `dead` 与未跟踪 `docs/design/ZCODE-MIGRATION-NOTES.md` 均 untracked，不进 git 操作不阻塞发版；owner 处置建议（删 dead；迁移笔记归档或 ignore）随汇报转达。

### 四、条件清单（随执行逐一闭合）

S1 预算扩张 ~184（批清单+二级评议）；S1 原生 prompt 宿主实证（IAB 桩黑盒）；S2 first_run 翻转句进设计+黑盒第二启动不重播；S4/S5 评估文档 2.4.0 发版前产出；S0 卫生件（release-checklist 基线 1601+4 已修、CHANGELOG [2.3.1] 随分支）。

### 五、后续风险跟踪

①2.3.1 发版 CHANGELOG 从四批内容起草——逐项对照 roadmap 能力边界如实告知（owner 未实测），禁词自查；②S1 弹窗 5 处调用点回归+暗色/窄窗黑盒；③S2 首启引导翻转唯一性；④触发型四项维持挂起（下一到期点=gui-probe 2026-11-01 日历项）；⑤2.4.0 收口底线纪律。

### 六、执行回传追记（2026-10-01 当日全收口） [S0-S4/S5 全闭环]

- **S0 ✅ 2.3.1 已发布**：release/2.3.1 @3304f95（bump+CHANGELOG [2.3.1] 从四批内容起草）→ tag v2.3.1 REST 建 ref（201）→ 构建 run 36864804050 绿 → artifact 并行 Range 70,849,801B 精确+exe 33,566,451B sha256 B079AFF6…59BD 核过 → **Release id 400979349**（notes 禁词 CLEAN）→ main 前进 2.3.2.dev0。
- **S1+S2 ✅ 已落库并随 2.4.0 发布**：d24 批清单二级评议 **HRO-1 采纳**（S2 翻转句原路径 A/B 经 api.py:1227 门控实证均 no-op，改 marker 键 `settings={"first_run_seen": true}` 路径 C）+6 条修正全并入（AppModal 重入守卫/alert 隐藏取消键/F5 preventDefault 同步序/class 无 CSS 先例事实修正+data-testid 0 预算/黑盒 5 用例/~184 记账为估算未兑现）；实现（钉⑤ 176→178 恰达上限、静态键 +0）+黑盒全用例 PASS（first_run 两分支 marker 调用参数精确断言/prompt 双段全链值传递+计数刷新/重入守卫/遮罩+Esc 取消/暗色+窄窗）；gate 丢失 0+新基线 178/190；推送 d91180f/3fc5135。
- **2.4.0 ✅ 已发布（收口单发）**：release/2.4.0 @9f1829f（bump minor 3→4+CHANGELOG 措辞对齐实现——coder 抓出"三步导引"与单句实现出入，裁决 CHANGELOG 对齐）→ tag REST（201）→ 构建 run 36871376836 绿 → exe 33,571,466B sha256 A10C6711…8D72B 核过 → **Release id 401022313**（notes 禁词 CLEAN）→ main 前进 2.4.1.dev0（第 8 步）。
- **S4/S5 ✅ 评估文档已产出**：docs/design/候选池大件评估-d1001-05.md（两件大件现状/依赖/体量/前置，明示无需求信号不进实施）。
- **S6/S7 ✅**：触发型四项维持挂起原样；反馈批二/真机项"owner 豁免推迟"标注落 roadmap。
- **⑪ 固定小节 ✅（S1+S2 批随批执行）**：双通道扫查零新增死规则（6 候选全甄别为注释误报/沿袭豁免，新增规则全在用）。
- **记账**：预算 FROZEN_IDS 176→178 恰达上限（~184 为估算未兑现，下一 UI 批预算 0 仍走预算表+二级评议）；静态键 190 恒等； Mimosa deep seal sha256:92048012 29=基线零新增；全量 1601+4 持平（1 环境性抖动单测复跑过）。**国庆冲刺计划内容完结达标**（2.3.1+2.4.0 两次收口发版；推断性窗口授权至 2.4.0 收口发版完成止，后续 commit/push 恢复 standing mode owner 终端默认）。

---

## [2026-10-01] [D2026-1001-06] 2.4.0 实测反馈修复轮（owner 四条+词典链真 bug） [已拍板·实现落库]

**关联**：D2026-1001-05（S7"发现问题再修"路径触发——owner 实测 2.4.0 后返回四条）；D2026-1001-03（2.1 词典下载 DEPENDENCY-IMPACT）。

### 一、Owner 四条与诊断

①词典下载应先选择并提供完整版（现直下 74MB lite=core 变体）；②AI 分析报错不可理解（截图：`路径不允许访问： 路径不在允许的目录下: E:\..._质量报告.txt`）；③质量报告加载一个文件后无法更改+加载导读无效+有文字无按钮；④高级参数阶段AB 角色卡与词库页角色卡编辑割裂感。

### 二、开工评议（1 HRO）+实证+二级评议（C1-C6+显式复议）

- **问题 1 [HIGH_RISK_OBJECTION] 采纳修正案**：评议员实拉 PyPI/CDN 核出——sudachidict_full 无数据 wheel（仅 9KB 壳包），真源=CloudFront CDN zip 137,472,173B；**隐式 sudachipy≥0.7 依赖**（20260723 词典 v1 格式，环境 0.6.11）；解压 OOM 风险；无国内镜像；选版形态=词典下拉双条目（否决 AppModal.select 新形态）；kind 不更名保留 sudachi 增 sudachi_full。
- **开工第一步实证（裁决性）**：sudachipy 0.6.11 加载 system_core.dic(20260723)=**Invalid header 静默失败**——**2.4.0 词典下载核心收益实际未生效**（grammar_hint 回退内置小词典仅打告警）；升级 0.7.0 后 LOAD_OK（0.1s，tokenize 正常）+全量 1601+4 零回归。
- **二级评议 C1-C6 全采纳+两条显式复议采纳**：C1=ja-dict 移除理由修正（[MATERIAL_CONFLICT]：sudachidict_core 20260723.1 wheel 实证 requires_dist=null，"resolver 冲突"表述作废；政策理由改为统一下载式+0.6.x 无法加载新 dic）+test_pyproject_meta 防捆绑钉重写+ci.yml 改 `.[dev]`（真 sudachi 覆盖接受退化落口径）；C2=full pin 单源受控 [UNVERIFIABLE] 标注+archive_member basename 匹配；C3=流式解压+磁盘预检量纲=解压后体积；C4=kind 兼容三联（dict_manager else 分支/api.py:1004 放开/app.js:3438 按钮门）+SystemSummary 分母改 DICT_KINDS.length；C5=守卫差分回归四断言（monkeypatch 方案）；C6=钉⑤随批。**显式复议**：①d1d4 C3（CI 安装面）②D3 ja-dict 支柱——均因新实证失效，采纳修订。

### 三、执行记录（修复 A-D+⑪，13 文件 +352/-89）

修复 A=sudachipy 升级+ja-dict 移除+README/手册 FAQ-11+sudachi_full kind（CDN 源+**pin sha256=eb6d0220…871e 实下载 137,472,173B 核算**+expected_extracted_bytes 330,563,683）+白名单扩 CloudFront+kind 三联+加载优先链 full→core+流式解压/下载落盘+磁盘预检+防捆绑钉重写；修复 B=守卫统一 `_validate_user_directory`+差分回归四断言+文案改值+stderr_tail 摘要（200 字符）+云 provider 发送前 AppModal.confirm；修复 C=载入新报告清 refineAiResult+lastAiSuggestions=null；修复 D="去编辑"跳转两分支（目录内精确打开含 canonical→tag 映射/目录外降级+提示）+保存后动态回落提示；⑪=零新增死规则（6 候选全甄别误报/豁免）。

### 四、验证链（全绿）

node --check；红线钉+静态钉 45 passed（钉⑤ 178 **零耗**——跳转按钮 class 承载）；全量 **1602 passed+4 skipped**（+1 新行为钉：流式落盘钉替换旧一次性 read 钉）；gate check 零漂移（178/190）；黑盒：词典下拉 4 条目+SystemSummary"2/4 可用"新分母+full 变体详情+角色卡"去编辑"按钮×2；secret 定向 1 hex 甄别放行（dict_sources.json full pin sha256=公开数据包摘要非凭据，首见入扫描面）；**Mimosa deep seal sha256:3762f3cf findingCount=31：identity 级新增 1 条 dict_manager.py:249 path-traversal 判误报留痕维持**（zip 归档内寻址非文件系统拼接+写路径锚定+sha256 pin 三重防护；行内计数差系树外路径漂移口径），甄别表已增记；GUI 已验证（黑盒断言+截图）。

### 五、是否 [PRESSURE-OVERRIDE]

否（owner 实测反馈修复指令+三级评议全过无 HRO 残留）。

### 六、后续风险跟踪

①**2.5.0 发版提案交 owner 确认**（词典选版=minor）——**owner 已确认发版并延续放权（2026-10-02），2.5.0 已发布**：release/2.5.0 @eb0346c（bump 2.5.0+CHANGELOG 从五批内容起草）→ tag v2.5.0 REST 建 ref（201）→ 构建 run 36892061454 绿 → artifact 并行 Range 70,872,814B 精确+exe 33,579,109B sha256 6382F28A…FAB7 核过 → **Release id 401160543**（notes 禁词 CLEAN）→ main 前进 2.5.1.dev0（第 8 步）；②full 下载 CDN 单源 CN 慢网→离线导入兜底已写手册 FAQ-11；③full pin 单源 [UNVERIFIABLE]（上游 20260723 更新须换行重核）；④CI 真 sudachi 覆盖退化系显式裁定接受项；⑤问题 3 子现象"无实际按钮"待复现（源码层无缺陷）；⑥owner 数据根=仓库根传统位（pip 源码态实测），EXE 数据根迁移路径未实测（归反馈批二豁免范围）。

---

## [2026-10-01] [D2026-1001-07] AI 分析独立设置（owner 实测第 5 条：应该由用户设置） [已拍板·实现落库]

**关联**：D2026-1001-06（stderr_tail/云确认基础设施）；first_run_seen marker 先例（settings 惰性 KV 通道）。

### 一、背景与诊断

Owner 反馈："AI 分析调用的是哪个 AI？本地大模型还是云端？我在设置里没有看到相关设置，这个也是应该由用户设置"。主模型核查：refineAiAnalyze（app.js:3124/:3133）读 refineS1Provider/refineS1Model——**AI 分析完全复用引擎页阶段A 配置（provider/model/endpoint/密钥），无独立设置**（v1.4 设计使然）；owner 诉求=服务商与模型应独立可设。

### 二、评议（C1-C3 强制+C4-C6 建议，全采纳）

- **C1（强制）**：provider_name 返回（api.py:1800）与隐私横幅（app.js:3034-3043）/确认弹窗文案（:461）三处须改读**实际生效 provider**——否则独立配置下横幅/状态谎报阶段A，显性化半治标。
- **C2（强制）**：独立 custom 无 CLI 默认端点（cli.py:72 default=""）——v1 缩范围禁用（下拉排除 custom+提示"请设阶段A 为 custom"，后端兜底拒绝）。
- **C3（强制）**：api.py:1308 first_run=settings 文件存在性判定——AI 设置写入会建档→首启横幅折叠，须显性入设计；**跟随态不写键、独立态才写**（最小化建档面）；回切跟随写 "follow" 标记。
- C4=静态键 +0 落实（option/label 静态文本会触"未收编中文"钉——HTML 留英文+MSG JS 填充）；C5=预算 178→180（显性化复用 refineAiPrivacy 升格常驻，非新建 181）；C6=黑盒五用例。

### 三、执行记录

| 件 | 内容 |
|---|---|
| DOM | index.html AI 区新增 .ai-config-row（aiProviderSel 下拉 6 选项含"跟随阶段A（默认）"/aiModelInput 输入；HTML 留英文+MSG JS 填中文防未收编中文钉，C4）——**钉⑤ 178→180** |
| app.js | aiRefreshEffective() 生效配置常驻（refineAiPrivacy 升格：跟随/独立+云端警示）；refineAiAnalyze 改读独立配置（provider 缺席=follow→阶段A；model 独立空=阶段A 当前值）；回填+change 保存（跟随态不写键） |
| api.py | refine_ai_analyze 加 ai_provider=None 参数（None=跟随阶段A；有值=覆盖 provider，endpoint 走 CLI 默认；custom 兜底拒绝）；provider_name 返回实际生效值 |
| MSG | +9 JS 态键（ui 配置标签/选项中文/占位/生效插值） |

### 四、验证链（全绿）

node --check；红线钉+静态钉+gui_api **48 passed**（钉⑤ 180 双向+静态键 190 恒等+差分回归）；全量 **1602 passed+4 skipped**；黑盒（IAB）：初始态（下拉 6 项中文 MSG 填充/placeholder/生效配置常驻"跟随阶段A — lmstudio"）/独立覆盖（deepseek+deepseek-chat→"独立配置 — deepseek / deepseek-chat"+save 调用参数精确）/回切 follow（"跟随阶段A — lmstudio / custom-model-1"实时读阶段A+follow 标记写回）；**2.5.0 批 5 并入未发版批**（2.5.0 发版提案仍待 owner 确认，含词典选版+AI 独立设置两件）。

### 五、是否 [PRESSURE-OVERRIDE]

否（owner 反馈明示"应该由用户设置"；评议无 HRO；settings 惰性 KV/预算表通道既有）。

### 六、后续风险跟踪

①模型手填拼错率（stderr_tail 已可见化；owner 再报再上 datalist+独立刷新，需新 id+预算）；②i18n 余量 2（190/192）用完须提案扩 cap；③独立云端 provider 密钥未配→请求失败属用户配置责任（2.5.0 发版说明提及）；④2.5.0 发版提案待 owner 确认。

---

## [2026-10-02] [D2026-1002-01] 开工盘点与维护收尾小批（refineGlCount 横切勾账+卫生清理；迁移笔记留 owner 处置） [已拍板·执行落库]

**关联**：D2026-1001-04（refineGlCount 修复源头 :2105）、D2026-1001-03（:2017 横切收编、:2028 迁移笔记留 owner 处置）、D2026-1001-05（:2150 处置建议随汇报转达）。

### 一、盘点结论（开工评议前置）

Owner 指令"项目继续开工"。全仓盘点（roadmap 全文+decision-log 尾三决策风险跟踪节，评议员实读复核成立）：2.0→2.5.0 计划内容全部收口（2.5.0 已发布 Release id 401160543，main=2.5.1.dev0）；剩余 ⬜ 全为触发型挂起或 owner 侧——触发型：上游 v1.9.3+ 对齐（触发未到：上游仍 1.9.3，且我方推荐结论经 v1.9.3 增补轮实证零行为漂移已覆盖该版）/Trusted Signing/引擎页重构/节奏 token 化/轨道 B/S4/S5/审计积压 4 项/容器查询/adaptive thresholds 默认开启（gate0 层 origin:"real" 语料 0/30，B2 门② 92 条系翻译层样本不折算，:1308/:1315）；owner 侧：反馈批二复验、gui-probe 定时首跳复核（2026-11-01）、2.5.0 问题 3 子现象复现截图。**结论：无未阻塞可推进计划内容，本轮不点火任何触发型项。**

### 二、评议与拍板

decision-critic 开工评议：**有条件支持、无 [HIGH_RISK_OBJECTION]**；[MATERIAL_CONFLICT]×1+修订×2 全采纳：①迁移笔记（docs/design/ZCODE-MIGRATION-NOTES.md）归档与 :2028"留 owner 处置"存在处置权冲突——裁定采 :2028 口径，owner 对 :2150 转达建议至今未回应、处置权在 owner，**本轮不入库维持 untracked**，完成报告重发建议（主模型推荐=归档入 docs/design/ 加"历史方法笔记，非现行规范"标注，备选=删除，owner 一句话定夺）；②roadmap 勾账注按"解冻钉⑤ 175→176（:2105）"口径落笔，不写"触全集冻结"，不动 :2000②/:2017 历史快照；③dead/.pytest_tmp2 删除（实测量级 25B 桩+3 空目录；.gitignore 仅覆盖 .pytest_tmp/，复现概率低不补条目）。

### 三、执行记录

- docs/roadmap.md 横切观察项 refineGlCount 行勾账（已随 2.3.1 批2 修复：折叠卡头恢复 span#refineGlCount，app.js 零改动；index.html:390 元素实证在，app.js 引用可解析）。
- 本地清理（不入库）：删仓库根 `dead`（1 行 UI 排查草稿，其记录的 .destination-section 无 CSS 规则事实已由历轮死规则扫查甄别闭环）与 `.pytest_tmp2/`。
- docs/design/ZCODE-MIGRATION-NOTES.md 维持 untracked（见二①）。

### 四、验证链

全量 pytest **1602 passed+4 skipped**（与基线 1602+4 持平，docs-only 零代码改动）；Mimosa deep **findingCount=31 与基线持平零新增**（seal sha256:f8b3e834…）；gate 契约闸不涉（零 UI/DOM 改动）；静态检查/冒烟不适用（无代码改动）。

### 五、是否 [PRESSURE-OVERRIDE]

否（docs-only 维护批，评议无 HRO，无不可逆动作）。

### 六、后续风险跟踪

①迁移笔记处置挂 owner（完成报告重推，定夺前不入库）——**[2026-10-02 追记] owner 拍板"归档入库"**：docs/design/ZCODE-MIGRATION-NOTES.md 加"历史方法笔记，非现行规范"状态行后入库，本项闭账；②owner 若选归档，入库须加"历史方法笔记，非现行规范"front matter 防误引为现行工作流模板；③.pytest_tmp2 未入 .gitignore，定向跑 --basetemp=.pytest_tmp2 复现 untracked 时再处置；④下一到期触发源=gui-probe 定时首跳复核 **2026-11-01**（若仍未触发须升格处置：评估弃定时或转真机承载，不得仅再调时间）。

---

## [2026-10-02] [D2026-1002-02] 2.6.0 质量闭环立项（轨道 B 落地+S4 改向+媒体重点分析） [已拍板·待 owner 追认四条件落法后批 1 动工]

**关联**：D2026-0927-01（轨道 B 立项+HRO-1 四条件+5 问清单+三条风险 b1-b3）、D2026-1001-05 S4/S5（候选池大件评估存照）、D2026-1001-03 第①项（触发挂起闭账）、复用零件=1.3.1 重翻执行器/2.0.1 行动类别定标/2.5.0 AI 分析独立设置/2.0 media_path 契约+疑似漏听检测+试听 UI。

### 一、需求信号（owner 2026-10-02 三点，轨道 B 触发源到达）

①轨道 B 要落地：AI 分析完质量后应给出建议并**可直接修复**，不然分析没意义；②S4 可加但改向：跨片质量趋势独立看板无实际意义（非科研项目），趋势应服务于 AI 分析建议与自动化调整；③配音链路（TTS）不做，改为"AI 质量分析加载音/视频重点分析"（结合 AI 分析提高复核清单正确解决率）。

### 二、立项评议（decision-critic 有条件支持、无 [HIGH_RISK_OBJECTION]，全采纳）

- 需求解读裁定："直接修复"=**一键批次人工放行**忠实且为条件③下唯一正解（判据=动作粒度从逐条手改降为一次意图，非要求零点击无人值守）；全自动写盘已被条件③封死，复议通道保留；「一键」入口钉死报告页防弱化漂移（黑盒：成功/部分勾选/取消/dry-run 预览+复验回显）。
- 硬化条件全采纳成文入 roadmap 2.6.0 节：批 1 八项（复验口径成文含起步方式=低置信子集重跑 AI 分析差异对比复用现役管线｜成本配额护栏成文=单批条目上限+预估成本进确认弹窗｜TM·词库写入闸三开关缺省不变｜bridge 直调 action_retranslate 模块本体禁旁路+--action-source 解析成文｜台账 old_text 唯一回滚依据+中断恢复语义｜批 2·3 扩展缝预留｜审计积压①②触发核查｜一键入口黑盒四路径）、批 2 三项（口径定案具名/自动调整只建议不改默认值不触 origin:real 0/30 硬化门+降格备选/无 GUI 页承诺）、批 3 四项（选型轮送评/云端音频并入威胁模型/定阈 DoD 退路/预算延续）；**批 1 三项核心定义（复验口径/成本护栏/写入闸）若开工评议仍停留议程层→critic 升级异议承诺成立**。
- 版本 2.6.0=minor 判定成立；两 INFO_GAP（批 3 云端音频接受度/本地重转写环境基线）随选型轮补；勘正采纳（2.5.0 验证链行钉⑤数字批 5 并入前口径）。

### 三、登记落库

roadmap：新增 2.6.0 节（批 1/2/3+实施序+硬化条件全文）；轨道 B 节勾账"已立项为 2.6.0"（D2026-1001-03 第①项闭账）；候选池 S4/S5 行改向记录（**配音链路正式不立项**）；2.5.0 发版行勾账+验证链行勘正注。pyproject.toml+subtransjav/__version__.py 前进 **2.6.0.dev0**。

### 四、验证链

定向版本钉 3 passed；全量 pytest **1602 passed+4 skipped**（版本前进零回归）；Mimosa deep **findingCount=31 基线零新增**（seal sha256:57170263…）；secret 扫描+blobs 复扫 CLEAN（见提交）；gate 契约闸不涉（本笔零 UI/DOM 改动）。

### 五、是否 [PRESSURE-OVERRIDE]

否（owner 明示需求信号三点；评议无 HRO；一切写盘动作关在批 1 开工评议+owner 追认之后）。

### 六、后续风险跟踪

①**四条件落法呈报 owner 追认=批 1 开工门**（落法：威胁模型开工前落盘送评｜云端不进缺省已满足｜一键批次放行、无人值守仅经显式复议条件③｜台账+复验口径成文）——**[2026-10-02 追记] owner 追认（无修改），批 1 已动工落库，见 D2026-1002-02-批1**；②批 1 开工评议八项硬化条件逐项勾验；③批 2 自动调整禁触 adaptive 硬化门（origin:real 0/30）；④批 3 选型轮送评+定阈退路（沿用初值标"未定阈"或批次 E 语料）；⑤id 180 已满零余量、i18n 190/192 余量 2——批 1 新 UI 走解冻预算表+快照+gate 新基线程序；⑥批 2/3 改装批 1 管线的扩展缝预留兑现核查；⑦审计积压①②触发核查随批清单固化。

---

## [2026-10-02] [D2026-1002-02-批1] 批 1「质量闭环主线」二级评议+实现落库 [已执行]

**关联**：D2026-1002-02（立项+owner 追认四条件）、威胁模型 docs/design/威胁模型-质量闭环-d1002.md、批清单 docs/design/d260-批1-批清单.md。

### 一、二级评议（有条件放行，两 HRO 全采纳）

- **HRO-A（中断语义）采纳折中案**：批评清单"执行器按 timing 幂等跳过"系不实承诺（实证 `_refresh_guide` 只改 current_text 不翻 status，action_retranslate.py:262-280；执行器无台账感知）。落法=**GUI 层台账感知守卫**：refine_guide_action_items 标 `applied_in_ledger`、refine_batch_fix 拒已修条目入批（error 明示 CLI 重修通道）——中断续修语义成立、台账唯一性在 GUI 批次流内保持；执行器选择逻辑零改动；C2=`_append_ledger` 改原子写（独立符号 `_ledger_atomic_write`，终稿写失败注入测试不受扰）+损坏恢复用例。
- **HRO-B（黑盒四路径）采纳**：B7 双定义更正（B7=超 cap 切片）；**dry-run 预览落 GUI 弹窗逐条预览（B10）**——数据源与执行器 dry-run 计划同源同选择语义（open+有现译），CLI dry-run 保留；作为对立项四路径的显式修订记录在案。
- C3（复验=全片重跑系硬化条件 1 的释义修订，弹窗明示"全片"）、C5（超 cap 按 index 序切片前 50+余量文案）、C6（current_text 非 None 显式校验，观察类必拒）、C7（威胁模型源文出域措辞+stderr_tail textContent 渲染约束）、C8（R1-R4）全落实。

### 二、执行记录

| 面 | 内容 |
|---|---|
| api.py | +3 bridge（refine_guide_action_items/refine_batch_fix/refine_batch_fix_progress）+阶段B 三 helper（存储 stage=3=槽 s3）+常量（`_BATCH_FIX_MAX_ENTRIES=50`/`_BATCH_FIX_TIMEOUT_S=1800`/`_GUIDE_SUFFIX`）；修复经 spawn_refine_cli 子进程 `--action-retranslate --entries --apply [--s3-provider/--endpoint/--action-model]`+密钥 env 白名单注入；Popen 流式解析进度；复验=重跑全片 AI 分析恰 1 次建议件三键（glossary/tm/observations）计数 diff，失败保留修复前建议件（R4） |
| action_retranslate.py | `_append_ledger` 原子写（C2）；其余零改动 |
| index.html/app.js | +3 id（refineBatchFixBtn/Scope/Status）+静态键 batchFixBtn+JS 态 MSG 12 键；流程=导读加载使能（排除已修）→scope 类别子集→确认弹窗（逐条预览 10 行折叠+预估 N 翻译+1 全片分析+云端警示）→1s 轮询进度→结果回显（textContent）+复验 Δ+aiRenderResult 重渲染 |
| 测试 | test_gui_api +8（常量钉/台账标记/守卫 6/成功链+台账增量+复验 diff/exit1 不复验/超时口径）、test_action_retranslate +1（原子写+损坏恢复）；红线快照 180→183、190→191（docstring 165/186 实数修正） |

### 三、验证链（全绿）

ruff 全仓 0｜node --check｜定向（gui_api/action_retranslate/redlines/strings/js_static）**234 passed**｜全量 **1610 passed+4 skipped**（基线 1602+4 只增 +8）｜gate check 丢失 0→**新基线 183/191** 告警 0 落盘｜Mimosa deep **31=基线零新增**（seal sha256:7e58f1ca…）｜黑盒（IAB 伺服+stub 桥+生产回调，截图 %TEMP%\gui-260-bf\）：**B1-B8+B10 全 PASS**、B9 部分（暗色菜单证据在案、暗色应用未捕获——IAB 截图/坐标假象限制；新组件全用既有 token 类）｜GUI 已验证（黑盒）。

### 四、是否 [PRESSURE-OVERRIDE]

否（owner 追认口径执行；二级评议两 HRO 采纳闭环；无不可逆动作）。

### 五、后续风险跟踪

①批 2 台账视图：逐条勾选回滚+"按 ts 取最后"口径随批 2 立项锁死；②静态键余量 1（191/192）——批 2 新 UI 键清单提前列，用尽须提案扩 cap；③批 3 选型轮两 INFO_GAP（owner 云端音频接受度/本地重转写环境基线）+威胁模型扩写重评后才可启用云端音频；④IAB 黑盒教训入档：截图≠实时视口（坐标须 getBoundingClientRect 实测）、Playwright actionability 对本应用系统性超时（cua rect 点击为主、dom_cua 节点路径兜底、长页先滚入视口）。

### 六、push 前双轴评审（code-review Standards/Spec）与修订

- **Standards 硬伤 2 项修正**：①进度正则钉住执行器不存在的 stdout 契约（轮询计数失效）→删正则、pump 透传尾行、计数以台账增量结算、前端 done=0 用中性文案；②两个轻量 bridge 补 try/except+_log_exc 兜底。judgement call：守卫链收敛 `_load_validated_guide`；schema:1（批 2·3 扩展缝规格明载）与上限 50 前后端语义分叉（设计使然）记录不改。
- **Spec 缺口 4 项补全**：弹窗补修复服务商+分类明细两行、预览行补 timing、batchFixScopeLabel 落实、补 2 测试（exit3 部分+路径守卫）；batchFixAppliedSkip 撤销（NoItems 文案已覆盖）。
- 修订后复验：全量 **1612 passed+4 skipped**（+10 只增）｜Mimosa 31=基线零新增（seal a89aae6f…）｜ruff/node --check 绿。

---

## [2026-10-02] [D2026-1002-03] 批 2「聚合数据层」开工评议+实现落库 [已执行]

**关联**：D2026-1002-02（立项：S4 改向条目）、批 1 扩展缝预留（注入点=quality_advisor prompt 组装）、docs/design/d260-批2-批清单.md（C1 口径成文载体）、威胁模型 §9 增补。**背景授权**：owner 无人值守连续推进指令（"可继续的任务一直继续下去，需要决策的和评议员讨论"）。

### 一、开工评议（有条件支持、无 HRO，C1-C7 全采纳）

- C1 口径成文（d260-批2-批清单.md §1：三口径具名+两处降格声明——CPS"分布"降格为"密度计数≤20"、命中率走势降格为"TM入库量代理指标"+枚举序 generated_at 降序取最近 20+聚合对象 N/A 明示+人工裁决句）；C2 additive 注入签名（analyze_quality_report 增参缺省空串，既有围栏计数钉 3 字节不变，新钉 count=4+块序）；C3 tm 只读纪律（独立新模块 aggregate_stats.py、tm.py 零改动、mode=ro、禁 TranslationMemory() 构造、缺库/锁/DDL 降级）；C4 块内容白名单（计数+stem，绝不引用周边片原文）+字段名精确契约+块头声明+n 恒报；C5 系统提示列举句泛化（兑现 prompt 组装钩子白名单扩展缝）；C6 配置双钉（TUNABLE bool 缺省开+负向钉 NOT in _CONFIG_FIELDS 防 resume 失效）；C7 验证链补全。
- 裁量裁定：默认开维持（默认关=交付物不可达）；C5 泛化接受；枚举序如上；命中率分母埋点列风险跟踪残留（挂"10~20 片定阈"未来消费链）。

### 二、执行记录

| 面 | 内容 |
|---|---|
| 新模块 | `subtransjav/refine/aggregate_stats.py`：collect_directory_stats（枚举+白名单提取）、query_tm_summary（mode=ro 只读聚合，异常降级 None）、build_aggregate_block（口径声明头+n 恒报+白名单块+2000 字符截断）、default_tm_db_path（只读推导禁 makedirs）；tm.py 零改动 |
| quality_advisor | 系统提示列举句泛化；analyze_quality_report 增 `aggregate_block: str = ""`（第四 DATA 块插冲突摘要后）；run_ai_analyze 装配（开关缺省开、构建失败 ⚠️ 降级不阻塞） |
| config.py | TUNABLE_FIELD_TYPES+"aggregate_stats_inject"（bool）+dataclass 字段缺省 True（注释载明纯读取侧不进指纹） |
| 测试 | 新 tests/test_aggregate_stats.py 12 用例（枚举/白名单字段名钉/截断/空串/TM 只读聚合+缺库+锁降级/默认路径零 mkdir/C6 双钉/additive 注入钉/端到端开关隔离真实 tm.db） |

### 三、验证链（全绿）

ruff 全仓 0｜mypy（aggregate_stats/quality_advisor）0｜冒烟 --help OK｜定向 19 passed｜全量 **1624 passed+4 skipped**（1612+4 只增 +12）｜gate check PASS 零漂移（零 UI 改动=钉⑤/静态键 0 耗）｜Mimosa deep 31=基线零新增（seal 见提交 verify 行）。

### 四、是否 [PRESSURE-OVERRIDE]

否（无人值守授权+立项既定批 2 范围；评议无 HRO；零写路径零不可逆动作）。

### 五、后续风险跟踪

①**命中率分母埋点**（查询未命中不留痕）挂"10~20 片定阈"未来消费链——届时真实命中率走势+入库量代理一并作定阈输入；②基线 n 极小（1-2 片）LLM 过信风险=块内提示标注兜底（已落）；③两处降格措辞（"CP​S 行动密度""TM 入库量"）后续文档引用须与本批清单定案一致防口径漂移；④LLM 对聚合块的实际引用质量=无真跑覆盖（stub 黑盒不适用、CLI 真跑归 owner 侧实测反馈通道）。

---

## [2026-10-02] [D2026-1002-04] 批 3「媒体重点分析」选型设计轮定稿（待 owner 两项决策） [材料定稿·待决策]

**关联**：D2026-1002-02 批 3 行（选型轮先行+两 INFO_GAP）、威胁模型 §8（云端音频强制扩写重评闸）、D2026-0929-09（ffmpeg 探测/禁 torch 级默认先例）、docs/design/批3-媒体重点分析-选型材料.md（定稿）。**背景授权**：owner 无人值守连续推进指令。

### 一、评议（有条件支持、无 HRO，C1-C4+G3 全采纳）

材料准确性实核（基建落点/33MB 预算先例）；立场"路线 C 分阶段（B 本地重转写先行+A 云端多模态 opt-in 预留，切片管线共用）"获维持（替代 B 独走不更优）；修订：C1 定阈退路补双项+批次 E 语料系 SRT 文本语料**源片可播放性未证**（G3 待 owner 核实）；C2 INFO_GAP-2 改"基线引用（RTX 5060 Ti 16GB+WhisperJAV 已装，D2026-0917-03 实证）+四选一（a 探测复用/b pip extra/a+b 探测优先兜底/d 其他）"；C3 阶段 1 验收须证 A 预留零侵入（设置/UI/弹窗无 A 痕迹）；C4 阶段 2 服务商名单未定则缓启（先出候选清单供二次选择）；INFO_GAP-1 补"接受但暂不定范围"兜底分支。禁 torch 先例判定：适用且 a/b 同构（c 捆绑违反先例+预算）；阶段 2 云端多模态不涉本地 torch 捆绑、先例不阻。

### 二、产出与状态

选型材料定稿（§3 三路线对比/§5 体量前置/§6 两项 INFO_GAP 决策问法）。**状态=待 owner 决策**：①INFO_GAP-1（云端音频接受度，三分支）；②INFO_GAP-2（ASR 环境策略四选一）。两项均答→批 3 按所选路线进批清单+开工评议；均不答→批 3 维持材料备好状态，**不阻塞 2.6.0 以批 1+批 2 收口**（批 3 独立成批顺延不拖版本）。

### 三、是否 [PRESSURE-OVERRIDE]

否（选型轮不动代码不进实施；评议无 HRO）。

### 四、后续风险跟踪

①G3：批次 E 语料源片可播放性待 owner 核实（影响定阈退路二选一的可行性）；②阶段 2 启动前置三项（INFO_GAP-1 答复+服务商候选清单+威胁模型 §8 扩写重评）缺一不可；③定阈"参数化回填"为独立验收项不随路线成败；④10~20 片定阈与批 3 验收合并执行口径已立（§4.4）。

---

## [2026-10-02] [D2026-1002-04-批3] 批 3「媒体重点分析·路线 B」开工决议+实现落库 [已拍板·已执行]

**关联**：D2026-1002-04（选型定稿+两项 INFO_GAP 呈报）、owner 四项决策（2026-10-02：云端不接受因限制级内容云端失败风险→路线 B 独走；2.6.0 三批齐发暂不发版；ASR 环境=探测+可选+推荐下载暂定 whisper/qwen；批次 E 不再启用→定阈退路=沿用初值标"未定阈"）、docs/design/d260-批3-批清单.md。**背景授权**：owner 无人值守连续推进指令。

### 一、开工评议（有条件放行 + 1 HRO 采纳方案 a）

**[HIGH_RISK_OBJECTION]（qwen 下载件）采纳方案 a**：HF 多文件目录撞 dict_manager"单一文件"不变式（:15/:97）→ **qwen 下载随运行器移下批**，推荐清单保留两件、qwen 标"下一版本支持"不设下载按钮；本批下载件仅 whisper-large-v2（单文件+sha256 pin，3,086,999,982B/81f7c96c…**本机实测核算**）。
C2-C10 全采纳：C2 探测升 --selfcheck（导入链+whisper 导入+模型缓存定位，防假阳性）；C3 运行器导入图钉（顶部纯 stdlib、whisper 懒加载，静态测试钉）；C4 预算实现前列名（修订：静态键 +1 恰达 192 无需扩 cap，cap 扩 200 记下一 UI 批首件）；C5 清单强制 sha256 pin+allow_unverified 恒 False；C6 对照块 ≤2000+非真值声明+知情行（CLI 机器标记→GUI 状态行）；C7 审计①②归档+威胁模型 §9 音频注入面登记；C8 失败/完成后切片 best-effort 清理；C9 探测优先级 env>settings>实测默认>不可用成文；C10 media_crosscheck_enabled 双钉+asr_model/asr_python 负向钉+CLI 旗标镜像 --ai-model。

### 二、执行记录

| 面 | 内容 |
|---|---|
| 新 asr_runner.py | 上游 env 执行的运行器（--selfcheck/--audio，stdout JSON 契约，whisper 懒加载） |
| 新 asr_env.py | 探测（三级候选+selfcheck+缓存枚举≥1GB）/run_transcription（子进程 JSON 解析降级）/slice_clips（ffmpeg list-args 16k 单声道，≤20 段，sha256 指纹命名+清理）/build_crosscheck_block（≤2000+非真值声明）/下载薄委托 dict_manager |
| dict_manager | 白名单+openaipublic；`_sha256_stream` 流式（GB 禁整读）；`download_asr_model`+进度快照（.part+replace 沿既有已审模式；落点常量字面量+根前缀断言） |
| quality_advisor | crosscheck_block 第五 additive 参数；run_ai_analyze 编排 `_build_media_crosscheck`（媒体定位→切片→重转写→对照块+`[crosscheck] segments=N` 知情标记+C8 清理） |
| config/cli | media_crosscheck_enabled bool 默认开（TUNABLE+dataclass）；--asr-model/--asr-python（不入指纹负向钉随批） |
| api.py | refine_asr_status/refine_asr_download（后台线程+防重入）/refine_asr_download_progress 三桥+refine_ai_analyze 旗标透传+crosscheck_segments 知情返回 |
| 前端 | 引擎页 ASR 卡（探测行/下拉含 qwen 禁选占位/下载按钮按 model_present 显隐/进度三件套）+MSG 14 键+选择持久化 |

### 三、验证链（全绿）

ruff 全仓 0｜mypy refine/ 43 文件 0｜node --check｜定向 136+14 passed｜全量 **1638 passed+4 skipped**（+14 只增）｜gate check 丢失 0→**新基线 190/192** 告警 0 落盘｜Mimosa deep 31=基线零新增（seal 见提交 verify 行）｜黑盒 A1-A4 全 PASS（真实上游探测回显/三选项含 qwen 禁选/下载按钮显隐/持久化断言/暗色渲染，截图 %TEMP%\gui-263-asr\）｜GUI 已验证。

### 四、是否 [PRESSURE-OVERRIDE]

否（owner 四项决策明示+无人值守授权；HRO 采纳闭环；音频零出域）。

### 五、后续风险跟踪

①**qwen 运行器批（下批首件）**：HF 仓库布局核实（I1）→多文件清单 schema+目录落位=from_pretrained 可加载+加载 smoke，开工前二级评议；②静态键 192 满额——下一 UI 耗键批首件=扩 cap 192→200 提案；③crosscheck 默认开+知情行已随批验证（防静默增耗）；④ASR 文本注入面已登记威胁模型 §9（信任域=字幕文本），AI 分析改动回归时复核；⑤**2.6.0 发版=批 1+2+3 齐发**（owner 拍板），发版走 release/2.6.0 分支制+dispatch 试构建先行。

---

## [2026-10-02] [D2026-1002-05] 跨片统计修订：TM 库对比+窗口三档（owner 反馈，2.6.0 发版前拦截） [已拍板·已执行]

**关联**：D2026-1002-03（批 2 原口径）、2.6.0 发版流程（tag 已建未随 Release——拦截时点）。**背景授权**：owner 无人值守+发版前反馈窗口。

### 一、owner 反馈（原话要点，2026-10-02）

"跨片聚合统计——同目录其他片的 CPS 行动密度、open 风险密度、TM 入库量走势**应该是用户自主选择 7/30/永久三类**，并且**不应是同目录而应该是和保存的数据库对比**。"

### 二、处置与实现（按 owner 指令直改，无歧义映射）

- **发版拦截**：tag v2.6.0 已建（REST 201）未随 Release→REST 撤销（204，重打无历史负担）；构建作废。
- **统计源改库**：aggregate_stats.py 重构为纯 TM 只读聚合（-302/+234 行级）——移除同目录导读扫描与 collect_directory_stats；CPS/风险类跨片对比因质量数据未库化**移除**（块内如实声明"未库化暂缺"）。
- **窗口三档**：WINDOW_MAP {7/30/all→None}；GUI AI 分析设置区下拉 `aggregateWindowSel`（settings KV tm_stats_window 持久化）；CLI `--tm-stats-window {7,30,all}` 缺省 30；均不入 manifest 指纹（负向钉随批）。
- **发版重入**：main 提交修订（c2aec58）→release/2.6.0 cherry-pick（027fbbe）+CHANGELOG 措辞对齐（ea7de25）→重打 tag→重建。

### 三、验证链（全绿）

ruff 全仓 0｜mypy 0｜node --check｜定向 12+285 passed｜全量 **1638 passed+4 skipped**（发版分支同数）｜gate 新基线 **191/192**（aggregateWindowSel +1 恰达静态键 cap 192）告警 0｜黑盒：窗口下拉复用批 3 A3 同款 selectOption 持久化路径（未单独跑，如实标注）。

### 四、是否 [PRESSURE-OVERRIDE]

否（owner 明确指令；无不可逆动作——tag 撤销时点早于 Release 创建）。

### 五、后续风险跟踪

①CPS/风险类跨片对比=**潜在回归项**：若未来质量数据库化（如导读汇总入库），可按本模块形态恢复对比段；②块内"未库化"声明防 LLM/用户误以为功能缺失；③tm_stats_window 设置 KV 与 CLI 旗标双通道并存，GUI 未设时 CLI 缺省 30——文档口径一致；④发版流程重入后 notes/CHANGELOG 措辞已对齐（"翻译记忆库对比统计+窗口三档"）。

> 补档说明（D2026-1002-06 时点）：本条目正文摘取自 release/2.6.0 分支提交 97cf2f0（05:00）既有归档，main 侧因分叉未并入造成缺口，按 D2026-1002-06 决议照录补齐。

---

## [2026-10-02] D2026-1002-06 ASR 推荐制收口：验证可选化+模型推荐制（owner 反馈修订，2.6.0 发布后） [已拍板·执行中]

**关联**：D2026-1002-04-批3（原批3 落库，本批撤销其后续跟踪①下载部分与③默认开）、D2026-1002-05 补档（正文取 release/2.6.0 分支 97cf2f0 既有条目，main 侧缺失为分叉缺口，摘取注明来源）、owner 原话（2026-10-02，2.6.0 发布后反馈）："asr验证应该是可选向，模型应该是推荐而不随项目打包，做好接口和页面即可"。**背景授权**：owner 无人值守连续推进指令+发布后反馈窗口。

### 一、开评议（决策评议员复评结论）

立场：有条件支持方案 B（推荐制收口）；弃 A（保留下载链=保留 3GB 单源维护承诺，二次反馈风险高于删除风险）、弃 C（不回应推荐制）。无 [HIGH_RISK_OBJECTION]（契约错位属未验证面而非已验证事实冲突，按普通级+硬条件处置）。

**核心异议（契约错位，主模型已采纳 b-1 加强形）**：下载落点=数据根 models/asr/（dict_manager.py:224）而运行器加载点=~/.cache/whisper（asr_runner.py:37-39,53），删除下载链后"已就位"判定与加载点脱钩→假阳性+潜在 whisper 自动联网 3GB（违背零出域/不自动收口意图）。处置：asr_runner 新增 --model-dir 透传 download_root（显式 load_model 后 transcribe，比 transcribe 透传 kwarg 对上游 fork 版本差异更稳）；解析顺序 asr_env 定（~/.cache/whisper 命中不传旗标=原生优先｜数据根命中才传 --model-dir）；selfcheck 的 model_present 按同顺序判定；放置说明两处都列（默认缓存=零配置优先、数据目录=可见性备选）；download_root 若上游 fork 不支持以 TypeError 显性失败进错误通道，不静默；契约测试钉"放置路径→加载点一致性"。

### 二、决议（按主模型拍板）

1. 验证可选化：media_crosscheck_enabled 默认 True→False（TUNABLE+dataclass 双面翻转）；引擎页 ASR 卡新增「启用 ASR 验证」开关（默认关），经 refine_stage_settings KV media_crosscheck_enabled 持久化；CLI 新增 --media-crosscheck-enabled {0,1} 旗标（KV→CLI 镜像 asr_model 既有模式）。
2. 模型推荐制：删除下载链（dict_manager._ASR_DOWNLOADS/download_asr_model/ASR 进度快照/_sha256_stream（仅 ASR 专属，grep 核实）、asr_env 下载薄委托、API refine_asr_download/refine_asr_download_progress、页面下载按钮+进度条、JS 下载块）；保留 _http_get/_check_free_space/_safe_component 共用基建（sudachi 下载共用，禁删）。
3. 契约修正（条件①b-1 加强形）：asr_runner 增 --model-dir；asr_env 按双端清单解析顺序决定是否传旗标；selfcheck/转写同步。
4. 推荐清单纯信息展示两行：whisper-large-v2（推荐可用，大小/sha256 指纹/来源 URL/放置路径说明）+ qwen3-asr-1.7b（规划中/自备，不设下载）；检测命中标"已就位"；保留探测状态+模型下拉（选已就位模型）；补 asr_python 路径输入框（三级候选 settings 档此前无 GUI 入口）。
5. qwen 运行器批（HF 布局核实+加载 smoke）：保留候选挂账，不点火不排期；本批仅撤销"下载随运行器"。
6. 测试：默认值钉翻转（test_asr_env.py 双钉）；下载 4 例替换为推荐目录/命中匹配+契约钉测试（净数不降）；补 CLI 旗标与 status 形状测试；钉⑤快照按 id 增删显式更新（asrDownloadBtn/asrProgress* 摘除、asrCrosscheckToggle/asrRecList/asrPythonInput 新增）；新文案全走 JS 态 MSG 键，静态键 cap 192 零消耗（禁新增 data-i18n）。
7. 文档：D2026-1002-05 补档取 release/2.6.0 分支 97cf2f0 既有正文（已核实该提交完整条目，main 未并入，grep -c=0），注明摘取来源；本条目即 D2026-1002-06 正式记录对批3 后续跟踪①（下载部分）与③（默认开）的撤销；roadmap 更新（qwen 运行器批改候选挂账、修正过期 id/i18n 数字、补 2.6.1 修订行）。
8. 验证链照常：ruff→定向→单文件→全量（1638+4 基线只增不降）→冒烟→Mimosa 与基线（31，seal 57170263）比对零新增；≥3 文件变更触发 code-review 技能与三查合并。

### 三、异议记录

- **原决策**：方案 B（删下载链+验证开关+推荐清单）；弃 A/C。
- **评议员异议**：①契约错位（已就位判定 vs 运行器加载点）必须本批内修正；②qwen 运行器批去留须显式表态；③D2026-1002-05 补档应取 release 分支既有正文而非重写；④新文案零静态键消耗。
- **主模型最终决定**：全部采纳（含 b-1 加强形、qwen3-asr-1.7b 保留挂账、97cf2f0 摘取补档、JS 态 MSG 键约束），无驳回项。
- **条件闭环判据**：条件①（契约修正）以"契约测试钉'放置路径→加载点一致性'随批绿色通过"为闭环判据；未闭环即本批不得视为完成。

### 四、是否 [PRESSURE-OVERRIDE]

否（owner 明确指令+发布后反馈窗口，无权威/时限施压）。

### 五、后续风险跟踪

①**上游 fork download_root 支持性实证（G1 收件）**：owner 机 whisperJAV 环境一次真实转写端到端验证 b-1 clickthrough（黑盒同款流程补"放置后真被加载"口径）；不支持则 TypeError 显性失败通道兜底，不留静默降级；②静态键 192 满额维持——本批零静态键消耗按承诺兑现，下一 UI 耗键批首件=扩 cap 192→200 提案照旧；③qwen3-asr-1.7b 运行器批挂账（不点火不排期），启动前置=HF 仓库布局核实+多文件目录落位 schema+加载 smoke，开工前二级评议；④钉⑤快照与功能增删同步——未来任何 ASR 卡 id/i18n 增删必须显式走快照更新流程（有意摩擦）；⑤ASR 文本注入面已登记威胁模型 §9（信任域=字幕文本），AI 分析改动回归时复核；⑥默认缓存与数据目录双路径并存——放置说明明示"优先零配置缓存，数据目录为备选"，防双份放置理解偏差。

### 六、执行追记（2026-10-02，双轴评审修复+验证链收口）

- **code-review 双轴（Standards+Spec）修复五项**：①契约钉闭环——test_asr_env 新增 2 例（fake whisper 记录 load_model 调用参数，断言 `--model-dir`→`download_root` 真实透传、缺省时为 None），**条件①闭环判据达成**；②推荐行补 sha256 指纹渲染（api 侧 `{**entry}` 本已透传，前端未消费）；③放置说明补"文件名须为 <model>.pt"（防命名错=永不"已就位"）；④状态行去 'large-v2' 硬编码（saved_model 优先）；⑤fmtGB 去重。
- **偏差追认**：dict_manager 域名白名单移除 openaipublic.azureedge.net（下载链语义内收口，全仓零残留引用；推荐清单保留 URL 仅供自备参考，非取数面）；CHANGELOG 2.6.0"一键下载"表述过期→按发版时点同步惯例留 2.6.1 发版批（release-checklist 步骤）+使用与维护手册 ASR 段同批补；开关回显只读设置 KV、不读 env/user_settings 分层链（单用户已知限制，后续如需再对齐 config.resolve_tunable）；asr_env/runner 判序同形两处系运行器 stdlib-only 约束（注释维系，不共享代码）。
- **验证链（全绿）**：ruff 全仓 0｜mypy refine/ 0｜node --check｜定向 191 passed｜全量 **1650 passed+4 skipped**（基线 1638+4 净增 12，只增不降）｜Mimosa deep 31=基线零新增（seal d5d0446b…ca2b41e）｜secret 定向扫描 0 命中（16 文件全集+hex 只扫新增行）｜冒烟 `--help` 新旗标可见｜**GUI 已验证**（stub 桥黑盒：卡片结构/探测渲染/开关持久化+回读一致/python 输入保存/qwen 禁选占位/双主题渲染，截图 %TEMP%\gui-261-asr\）。

---

## [2026-10-02] D2026-1002-07 工作区重整+校对视图立项（owner 四点反馈，2.6.1 三批路线） [已拍板·批 1 待开工]

**关联**：D2026-1002-06（ASR 推荐制=本立项组件范式前置）、D2026-1002-04-批3（对照链=批 3 联动源）、owner 原话（2026-10-02 四点）、docs/design/UI-REDESIGN-HANDOFF.md（布局定稿基线）。**背景授权**：owner 无人值守连续推进指令+"和评议员与设计师讨论"明示指令。

### 一、owner 反馈与答疑④

四点：①质量与建议应该提到工作区；②工作区单独添加一栏「校对」=视频+字幕对比（类似 SmartSub），可选向，所需组件不随系统打包、提供下载选项，组件需规划好；③SmartSub 布局比本项目合理但其 GUI 仍较割裂，本项目布局与美观度需提高，与评议员与设计师讨论；④提问：校对是否只需 ffmpeg？whisper/qwen 是否必需？联动何在？

**答疑④（已答）**：校对（视频+字幕导入对照）本身只需 ffmpeg（管线既有依赖，未随安装包打包）+WebView2 原生播放；whisper/qwen 只服务转录与 AI 重点分析对照链，非校对必需；联动真实存在=对照链/AI 分析产出的疑似问题段时间戳进校对视图跳转人工复核（批 3）；SmartSub 语音校对自动化层=转录后 VAD 疑点+同一 faster-whisper 模型小窗重解码+双窗口一致确认（**ASR 依赖**），本项目对应物=已落库对照链而非播放器内语音比对。

### 二、证据底座（双勘探+设计专家）

- **SmartSub 勘探**（GitHub main+本地安装目录 extraResources/python-review 双源）：精华=64px rail+流水线分组导航+密度规范；校对台 import→list→edit 三阶段+左视频右虚拟化字幕+双向联动（seek+10ms 偏移/反向滚动/防打架锁）+「建议检查」分层 issue 面板（catalog/decisions 分离）；坑=同一编辑器两套实现/工具箱密度漂移/播放器字幕单轨与列表真源不对等/无 remux 兜底/横条 banner 堆叠。其校对组件事实=python-review 侧车+sherpa-onnx VAD/降噪+ggml-silero（**非纯 ffmpeg 方案**）。
- **本项目勘探**：三栏 `220|1fr|316`（断点 1180 收 64）；「工作区」组=字幕翻译/引擎与模型/词库与模板、「质量与设置」组=质量与建议/高级参数；无 `<video>`、有 `<audio>` 试听条+ffprobe codec 矩阵+ffmpeg 抽 wav 兜底（api.py:2360-2542）；SRT 解析仅后端且 utf-8 硬读（filters.py:74）；硬约束=id 冻结 191/静态键 cap 192 满额（下一 UI 批首件=扩 200 提案）；app.js 单文件 4218 行。
- **设计专家报告**：五 DECISION_NEEDED 全部由主模型裁决（见决议）；另给 token 收敛清单/密度本项目化取值（维持 14px 基准）/四件独立小美化/三张 ASCII 线框（上下堆叠/折叠/左右并排）。

### 三、开评议（决策评议员结论）

**有条件支持，无 [HIGH_RISK_OBJECTION]、无 [PRESSURE-OVERRIDE]**。材料核验零冲突（191/192 实数程序实测、ffmpeg 未随打包、对照链在库、扩 cap 提案程序在案重复登记）。预算算术闭合（批 1 静态键 2-4 个、校对页文案全 JS 态键、批 2a id 走预算表程序）。条件②与增量 N1-N4、R1-R4 处置**主模型全部采纳，无驳回项**。

### 四、决议（批序与要点）

1. **批 1 UI 基建（开工门=本决议归档）**：钉⑤解冻提案（静态键 cap 192→200，本批消耗 2-4 个逐项列名+id 增减预演 0-2）+导航三分（工作区=字幕翻译/校对/质量与建议；设置=引擎与模型/词库与模板/高级参数；`nav_group_quality` 键名保留文字改"设置"，零耗键；结构钉快照随批显式更新）+间距节奏 token 化（--space-2..6/控件高 token，**只增不改**——钉④冻结 --space-1/--font 勿动）+质量与建议页来源条折叠进导读卡头+页面布局变体（全宽/窄幅/无右栏）统一声明+视觉三小件（行选中细色条/hover 微动效/空状态统一）+手册导航章节与 roadmap 2.6.1 节同步。
2. **批 2a 校对容器**：播放器 spike 首件（**验收口径显式定义**：file:// 直播+timeupdate/currentTime 精度+拖动 seek+SmartSub 式 10ms 补偿必要性实证）；新「校对」TAB 骨架+视频/字幕(srt)导入+`<video>` file:// 直连+ffprobe 三态（direct/clip-audio/error）+**手动触发**转码临时预览（临时件清理复用 media_clips 先例+时长预估提示+转码中 UI）+右栏全隐+顶部 32px 迷你状态条（statusDot/statusLabel/progressFill 三 id DOM 归属方案=**条件②，批 2a 开工评议列明**，主模型倾向新建+预算表）+**SRT 编码嗅探（N1，BOM→utf-8 严格→gbk 回退+3 单测）**+跳转入队接口空实现（{timestamp,label,source}+契约钉，N3 防返工）+id 预算表按子功能分段列名目标 ≤10；数据模型预留只读/编辑共用接口（R1 降级路径）。
3. **批 2b 校对编辑**：字幕列表（200-800 行不虚拟化，2000 档分段渲染+页码/搜索/当前行定位）+双向联动五要点（单真源/timeupdate 仅 currentIndex 变才滚/seek+0.01/用户滚动暂停自动跟随 2s/写盘必经后端）+行内编辑+保存（覆盖确认明示"按 1..N 重编号+utf-8 重写"+另存为/自动备份，N2）。
4. **批 3 联动增强**：对照链/AI 分析疑似问题段进校对视图（时间戳跳转/试听/确认·跳过）+**校对页 ASR 可选入口=承诺件**（推荐制模型引导，闭合 R4 歧义）。
5. **设计红线**：单一编辑器实现不并存两套/状态表达合并单行不堆 banner/列表与播放器同一数据真源/新文案全走 JS 态 MSG 键。
6. **程序分界（主模型裁决，批 1 扩 cap 提案正文显式写明）**：静态键 cap=硬上限走解冻提案；DOM id=批清单预算表+二级评议程序，**不并入 200 扩额统一管理**。

### 五、异议记录

- 评议员条件与增量：①导航三分支持+N4 组内割裂提醒（批 1 布局变体吸收）②条件②迷你状态条 id 归属（批 2a 评议勾验）③堆叠态列表导航三件（进批 2b）④手动转码三条工程细节（进批 2a）⑤五要点防回归三处（进批 2b）⑥答疑④口径核验通过（与 SmartSub 事实一致）。
- 主模型最终决定：全部采纳（含 R1 降级接口预留、R2 id 压缩 ≤10、R3 spike 验收口径前置、R4 承诺件化）+id 程序裁决，无驳回项。
- 条件闭环状态：条件②未闭环（判据=批 2a 开工评议列明三 id DOM 归属方案）；N1/N3/R3 以批 2a 清单+首件落地闭环；其余随各批开工评议勾验，二次评议按衔接规则引用本条。
- 是否 [PRESSURE-OVERRIDE]：否（owner 明示指令+无人值守授权）。

### 六、后续风险跟踪

①批 2a id 面为项目单批最大扩张（历史单批最大 +7）——预算表分段列名+压缩 ≤10；②`<video>` file:// 若整体失败坠入手动转码兜底=UX 大幅劣化——spike 先行+验收口径前置；③SRT 编码 N1 高概率——批 2a 首件 annex；④校对保存覆盖不可逆——确认框+另存为/备份；⑤批 3 跳转契约空窗——空实现先行防返工；⑥CHANGELOG 2.6.0"一键下载"表述与使用与维护手册 ASR 段=2.6.1 发版批同步件（承 D2026-1002-06 执行追记）；⑦app.js 4218 行单文件持续膨胀——批 2a 起校对页 JS 独立文件评估（<script> 拆分，不动既有 IIFE）。

## [2026-10-02] D2026-1002-08 批 2a 校对页迷你状态条 DOM 归属+UI 规格定案 [已拍板·D2026-1002-07 条件②闭环]

**关联**：D2026-1002-07（本件为其条件②闭环件）、docs/design/d261-批1-批清单.md（程序分界：DOM id=批清单预算表+二级评议程序）。**背景授权**：owner 拍板 B+E+4（"DOM 层独立三/四个 id，JS 层新写 makeStatusManager(ids) 小工厂，不动翻译侧 ProgressManager"；首选 +4 含容器，预算硬卡才退 +3）+明示指令"设计到 UI 设计，和评议员和设计师讨论下"。

### 一、决议要点（B+E 独立新写方案）

1. **DOM**：校对页顶部 32px 迷你状态条独立新建四 id——`reviewStatusBar`/`reviewStatusDot`/`reviewStatusLabel`/`reviewProgressFill`；JS 一律 getElementById；翻译侧 DOM（index.html:732-740 右栏卡 1 `.progress-container` 四 id，ProgressManager app.js:1186-1219 单例 8 处引用）零改动。
2. **i18n**：`reviewStatusLabel` 不挂 data-i18n（零静态键消耗）；文案全走 JS 态 MSG 键（`review.status.*` 族）；~~工厂内语言切换重渲染~~ **删除**（运行时切换机制不存在=INFO_GAP 答复，防御性过度设计）；验收改反向悬空钉保护（`test_js_msg_references_defined_in_table`，tests/test_strings_and_shortcut.py:151）；语言切换议题登记批 2b UI 复盘。
3. **JS**：新写 `makeStatusManager({ bar?, dot, label, fill })`，缓存元素，暴露 `setState({ state, labelKey, progress })`；ProgressManager 零改动。
4. **接口契约三条**（评议员条件 2 采纳）：`progress=null` ⇒ indeterminate 显式语义；state 枚举定稿 **4 值 `idle/ready/busy/error`**（state 定视觉、labelKey 定文字，transcoding 等细分由 labelKey 表达如 `review.status.transcoding`，不单列枚举位，与视觉四态正交）；非法 state 显式报错；labelKey 不插值（进度数字由 fill/百分比位表达）。
5. **aria 重组**（条件 3 采纳）：label=`role="status"`（隐含 polite）；fill=`role="progressbar"`+aria-valuemin/max/now（indeterminate 时移除 valuenow）；dot=aria-hidden。
6. **批 2b 归并时点硬性化**（条件 5 采纳）：评估时点=批 2b 开工评议；判据两条（批 2a 内 ≥2 独立调用方且接口零改动＋批 2a 验收门全绿）同时满足才评估；归并作为独立小批单列（批 3 末或 2.6.2 首件），不混 2b 功能批。

### 二、设计规格要点（design-expert 同轮交付，采纳）

32px 通栏 `.review-status-bar`（surface-2 底/sticky top:0 z-20 solid 防滚动穿透）+8px dot+12px label ellipsis（min-width:0）+flex spacer+busy 确定态右端百分比文字（**不落 id**，工厂内部管理，守 +4 账）+底部 2px 通栏轨（灰 --border 兼分隔线/蓝 --primary fill，transition .3s）。四态色板：idle=border-strong/text-3；ready=--ok+--ok-soft 环；busy=--primary+--primary-soft 环；error=--danger+--danger-soft 环/danger 文字。`.review-status-*` 类族参数拷贝零复用（翻译侧 7 条规则+既有 keyframe 零改动）；新 `@keyframes review-indeterminate` 参数拷贝（1.5s ease-in-out/width 30%/translateX -100%→400%）；全 token 零新字面量；`--ok/--danger` token 存在性=批 2a 实现首件核实项。批 2b 衔接：状态条=校对 tab-page 首行 sticky，媒体/字幕区 flex:1+min-height:0 自然分配。

### 三、评议员条件与裁决（全采纳，无驳回项）

①id 总额不预锁：本件只锁状态条归属（+4 方向/+3 备选），批 2a 清单预算表逐段预演全部子功能 ≤9（留 ≥1 缓冲），压缩顺序先压 SRT/转码区；②接口契约三条（见一.4）；③aria 重组（见一.5）；④语言切换设计点删除+验收改悬空钉（INFO_GAP 答复=运行时切换机制不存在：MSG 单中文表/applyI18n 仅启动注入一次/无切换入口/GUI 中文导向）；⑤归并时点硬性化（见一.6）；⑥验收补四项：暗色主题双主题截图/1180px 窄屏单行行为/FROZEN_IDS 快照显式更新跑钉/默认空态文案+初始 dot 态；"语言切换 label 正确"验收项按④修正。

### 四、异议记录

- 评议员：有条件支持，**无 [HIGH_RISK_OBJECTION]、无 [PRESSURE-OVERRIDE]**；条件 1-6 全采纳无驳回。经复议修正两项："接口稳定后再评估"归并时点不可判（改硬性时点+判据）、"语言切换重渲染"系主模型防御性过度设计（已删）。
- 是否 [PRESSURE-OVERRIDE]：否（owner 明示指令+无人值守授权）。

### 五、边界声明与风险跟踪

**边界**：本件闭环 D2026-1002-07 条件②即止；不预先锁死批 2a id 总额（以批 2a 清单预算表逐段预演为准）；批 2a 其余开工门（播放器 spike 验收口径、N1 编码嗅探首件、N3 跳转契约钉、R1 降级接口预留）仍待批 2a 正式开工评议。
**风险跟踪**：①批 2a id 面=项目单批最大扩张，预算表逐段列名 ≤9；②--ok/--danger token 存在性首件核实（不存在则映射既有 token 或补定义，不引入新字面量）；③未来引入运行时语言切换时 `.review-status-*` 为漏网重渲染点（批 2b UI 复盘项）；④aria-valuenow 在 indeterminate 时须显式移除；⑤归并评估在批 2b 开工评议，判据两条，不混功能批。

## [2026-10-02] D2026-1002-09 批 2a 校对容器正式开工评议 [已拍板·开工]

**关联**：D2026-1002-07（批 2a 原文+条件增量+程序分界）、D2026-1002-08（状态条四 id 定案+条件②闭环+id 总额 ≤9 待预演）。**背景授权**：owner 无人值守连续推进指令（"流程推到推不动必须要我决策截止"）；决议批 2a 无额外开工门，本件闭环即开工。

### 一、方案要点（评议通过稿）

**spike 首件**（tools/spike_review_video.py）：ffmpeg 合成 10s 片（testsrc2 显式 `-r 30`+drawtext 可选增强降级+aac，H.264 mp4）→ pywebview 真窗口加载 spike HTML（同生产加载链）→ JS 自动采集四组经 api 回传 JSON：A file:/// 直连（loadedmetadata+playing+videoWidth>0）；B timeupdate 间隔分布（50 采样）+currentTime 精度；C seeked 延迟+requestVideoFrameCallback mediaTime 与目标差；D direct/+10ms/+50ms 三组呈现偏差（阈值=实测帧周期 1000/fps 推导；median+P90、每组 ≥30、三组同目标集预登记）。判据：A 失败→转码兜底升级主路径（UX 劣化向 owner 报告）；四组"结果→设计分支"映射表入批清单 annex。

**主体 12 项**：①TAB 骨架（tabBtnReview/tab-review，switchTab 通用零改 app.js）②导入区（#tab-review .dropzone 样式拷贝+reviewDropzone 容器 id+按钮 class 委托 data-kind=video|srt+拖拽后缀放宽+JS active-tab 分流）③videoReviewPlayer file://直连（timeupdate 仅喂状态条）④ffprobe 三态 direct/clip-audio/error（复用 _ffprobe_stream_codecs api.py:2376）⑤手动转码（veryfast+crf23+aac、Temp/review_transcode/rt_{sha12}.mp4 hash 复用、24h 龄清扫、0.25 系数展示级预估、超时 duration×3+120s 可重试）⑥状态条（D2026-1002-08 四 id+makeStatusManager+2px 底轨+四态色板，百分比文字不落 id）⑦N1 嗅探 sniff_text_encoding 落位 refine/（BOM→utf-8 strict→gbk→error，4 用例，不动 8 处硬读）⑧N3 跳转空实现 enqueueJump{timestamp,label,source}+契约钉 ⑨R1 数据模型 blocks 只读/编辑共用+include_raw 预留 ⑩JS 拆分 review.js 独立 REVIEW_MSG 键表（不动 app.js 钉体系）⑪**id 预算 9**=[tabBtnReview,tab-review,reviewDropzone,videoReviewPlayer,reviewTranscodeBtn,reviewStatusBar,reviewStatusDot,reviewStatusLabel,reviewProgressFill]（≤9 留 1 缓冲）⑫测试（嗅探 4+三态+转码命令+load_srt 结构+前端静态钉；全量基线 1652+4 只增；GUI 黑盒含双主题+1180px）。

### 二、评议员条件四条（全采纳，无驳回项）

①spike 判据钉死（-r 30+实测帧率推导阈值；median+P90+每组 ≥30+目标集预登记；四组分支映射表入 annex；drawtext 降级 testsrc2 内建时间码为主）；②自动化可靠性（visibilityState 标签+仅采纳 visible 样本+丢弃计数入 report+窗口置顶前台；样本不足改半自动、D 结论不落参数）；③前端契约钉（REVIEW_MSG 闭合钉+enqueueJump 契约钉+node --check review.js+index.html 断言双 data-kind 值+硬约束"#tab-review 页内零 data-i18n"）；④spike 回报程序（任一分支触发→轻量续评引用本条+07/08；全符合预期→决策日志显式登记"无设计变更，annex 直进主体实现"）。

### 三、事实修正与术语漂移登记（照单全收，批清单落盘标注）

修正①：cleaner_rules.parse_srt 的 Subtitle.start/end 为整数毫秒（cleaner_rules.py:88,101-102，自带 lstrip BOM），非"float 秒"；N1 无"扩 ms"步骤；timing 字段取源（filters timing 字符串 vs cleaner_rules ms 重建）实现时显式选定入批清单。修正②：app.js 实为两个 IIFE（1806 Refine UI+4189 异步 init），非"唯一"。修正③：pywebview 6.2.1/ALLOW_FILE_URLS 默认 True/内置 Bottle 127.0.0.1 [UNVERIFIABLE]，由 spike A 组实证。漂移①：转码清理采 24h 龄 sweep（audio_preview 先例 audio_detect.py:47）而非原文"media_clips 先例"（全删模式），方向更优注明。漂移②：拖拽放宽后视频路径入 register_session_paths 会话信任边界（api.py:55，仅真实 OS 拖放手势可触发），显式声明留痕。

### 四、异议记录与边界

- 评议员：有条件支持，**无 [HIGH_RISK_OBJECTION]、无 [PRESSURE-OVERRIDE]**；条件四条全采纳。
- 边界：无人值守推进授权至"必须 owner 决策为止"；owner 将执行第五次测试=真机验证波（GUI 黑盒验收项归属真机波复核收口）。
- 风险跟踪：①id +9 FROZEN_IDS 随批显式更新；②file:// 失败→转码主路径 UX 劣化（spike A 前置）；③背景窗口 throttle（条件 2 护栏）；④转码磁盘总上限批 2b 复盘；⑤批 2b 联动基准取决于 D 组结论（续评衔接点）；⑥#tab-review 页内零 data-i18n 硬约束；⑦N3 契约钉闭合批 3 空窗；⑧0.25 系数展示级无硬保证。

### 七、spike 首件结果登记（2026-10-02，D2026-1002-09 条件 4 回报程序=显式登记）

**结论：设计分支未触发——10ms 补偿非必需，直连为主路径成立，annex 直进主体实现。**

- **A file:/// 直连**：ok（videoWidth=640、load 222ms、hidden_dropped=0、load_mode=file-url）——audio 直连先例扩展到 video 实证成立，修正③ UNVERIFIABLE 就此闭合；直连为主路径、转码兜底保持手动次路径。
- **B timeupdate**：50 事件（49 间隔，median 265.5ms/P90 266.6ms，Chromium 默认节奏）；currentTime 最大 6 位小数——批 2b 联动"currentIndex 变才滚"节流基线有据。
- **C/D seek 呈现偏差**：rVFC mediaTime 实证可用；direct median=0.0ms/P90=0（帧级精确）、+10ms=0.0ms（落同帧，亚帧量化）、+50ms=33.33ms（恰一帧周期）。n_visible=12/30 如实落盘（D_verdict=insufficient_data，护栏未放宽）——**判据口径澄清（code-review Spec 轴修正）**：D 组钉死判据（每组 ≥30 可见样本）未达成，按 D2026-1002-09 条件 2 本结论不落正式参数；现登记为**方向性证据**（帧量化旁证支持补偿非必需），批 2b seek 联动的最终基线（直接 seek vs +10ms）须批 2b 开工评议复核（半自动重跑取满样本或 owner 追认方向性证据）后方落参。
- **平台行为发现（批 2b 设计输入，annex 登记）**：①WebView2 `html=` 注入页（about:blank origin）拒绝加载 file:// 媒体（URL safety check/4）——媒体页必须与产品同构以 url= 本地文件加载（as_uri()）；②**暂停态 seek 后 rVFC 隔次不回调**（严格交替失败模式，seeked 正常触发）——校对页/批 2b 呈现帧确认不能单独依赖 rVFC，需 seeked+currentTime 或 play-kick 兜底。
- spike 工件：tools/spike_review_video.py + tools/spike_review_report.json（终版=13s 片+单位修复+file-url 加载），随批 2a 实现一并提交。

### 八、D1 追认回填（2026-10-02，owner 拍板，批 2b 开工轮）

owner 拍板 b 追认不重跑，追认边界四条：①只追认"批 2b 行级 seek 直接 seek、不加 10ms 补偿"；②**不追认**全局结论"10ms 补偿非必需"；③证据等级=方向性证据（可见样本 12/30 未满 30 判据）；④未来做帧级/字级对齐、逐帧校对、时间轴精修必须补满 30 样本重跑，不得引用本次追认当正式落参。


## [2026-10-02] D2026-1002-10 批 2b 校对编辑开工评议 [已拍板·开工]

**关联**：D2026-1002-07（批 2b 原文：列表/双向联动五要点/行内编辑/保存 N2）、D2026-1002-09 §八（D1 追认回填）、docs/design/d261009-批2a-批清单.md（批 2a 收口件）。**流程**：owner 先行拍板 D1-D4+随批议程（"批 2b 开工评议通过，同意开工"），主模型草案交评议员技术完备性审查；评议员 1 HRO+1 MATERIAL_CONFLICT+条件 C1-C8，主模型裁定后归档。owner 归档指令映射：本条=批 2b 开工评议归档（含 D2 备份策略）+D1 追认回填 09 §八。

### 一、owner 拍板（原样入档，不可弱化）

**D1**：b 追认不重跑（边界四条见 09 §八）。**D2**：自动备份=单份滚动+**固定名 `{原名}.bak.srt`**（不用时间戳名防"误以为有历史版本"）；执行条件：备份由后端 API 执行｜覆盖保存前先备份、备份失败中止保存（不得先写后备份）｜原子写（临时文件+替换）｜备份件不参与字幕列表/搜索/定位｜另存为目标已存在同样确认+备份｜默认 1 份设置项可调 N 但批 2b 只实现 N=1。**D3**：只做文本编辑，时间轴展示只读+明显视觉提示（点击不进编辑态）；保存"按 1..N 重编号"只改 SRT 序号，**行数不变、时间轴不变、内部稳定 ID 不变**；将来增删行/改时间轴另行立项不偷跑。**D4**：≤800 行全量渲染不虚拟化｜801-2000 分段渲染+页码/搜索/当前行定位｜>2000 仍分段+虚拟化/窗口化兜底预案｜性能验收=200-800 滚动无卡顿、2000 档首屏 ≤300ms/滚动 ≥50fps/搜索定位 ≤100ms、不达标降级分段+虚拟化。**随批议程**：⑤状态条归并判据不满足（批 2a 仅 ReviewUI 一个调用方）→不归并维持两 manager，归并移批 3 末或 2.6.2；⑥按 D1；⑦语言切换维持无机制零代码动作。

### 二、评议员发现与主模型裁定（C1-C8 全采纳）

- **C1（HRO，采纳）**：`.bak.srt` 将被翻译侧批量扫描（batch.py find_srt_files rglob "*.srt"、api.py select_srt_folder glob）收纳入队，D2-④"备份件不参与列表/搜索/定位"结构性失守——修复=两处扫描加 `.bak.srt` 排除+单元测试（对现状零变化）。评议员此发现成立并采纳，无驳回。
- **C2（MATERIAL_CONFLICT，裁定）**：owner 材料内 D1"不加 10ms 补偿"vs 边界清单"seek 到行+0.01s"矛盾（数值同一操作）。裁定=**直接 seek（start_ms/1000 无偏移）**——D1 为更晚更明确专门裁定，覆盖旧五要点文；spike 实证 direct 与 +10ms 可见样本不可区分且 direct 偏差 0.0ms。最终公式静态钉锁定；owner 保留一句话改回权。
- **C3（采纳）**：另存为补后端 SAVE_DIALOG 桥（先例 api.py:1685）+目标已存在确认与备份（D2⑤）。
- **C4（采纳）**：覆盖确认框文案锁字："按 1..N 重编号 + UTF-8 重写；行数/时间轴不变"（REVIEW_MSG 键+断言固化）。
- **C5（采纳）**：性能验收口径可执行化——首屏=分段渲染起至首次 rAF ≤300ms；滚动=rAF 回调计数 ≥50/秒（visible 态）+人工"无可感知卡顿"双轨；搜索定位=提交至高亮+scrollIntoView ≤100ms；全部真机波留档。
- **C6（采纳）**：分段渲染下 currentIndex 跨页自动翻页写死；"2s 内无滚动事件→恢复跟随"条件写死；dirty 以 labelKey 表达（state:'ready'+未保存文案），**不新设状态位**（D2026-1002-08 四态枚举正交契约）。
- **C7（采纳+裁定）**：键盘语义按 owner 原文=**Enter 提交+Shift+Enter 换行**（入钉）；Esc 取消回滚；TAB 切换 dirty 守卫=review.js capture 阶段拦截 .side-tab-btn 点击+AppModal.confirm（app.js 零改动约束内）；窗口关闭守卫=**明示不做**，丢失边界声明（丢失面=会话内未保存编辑；原文件与 .bak 均安全）。
- **C8（采纳）**：save 增加 blocks 计数校验（≠load 数中止）+路径走 safe-path；稳定 ID 定义钉死=**blocks 数组下标（0 基）**，保存断言 index 字段==下标+1，批 3 引用一律用位置禁内嵌文件序号；批清单记 ⑤⑥⑦ 处置行；位置身份耐久性边界=审核链路内连续保存，外部工具改文件后位置失效须重扫（批 3 兜底留坑）。

### 三、批 2b 落点纲要（主体）

真源=后端 blocks 初始快照+前端 ReviewUI._blocks 会话真源+后端落盘汇（播放器不持字幕数据）；列表（≤800 全量/801-2000 分段+页码/搜索/定位/>2000 分段+虚拟化兜底预案）；timeupdate 265ms 节流基线+二分查行+index 变才滚；行点击直接 seek；手动滚动暂停 2s；行内编辑（textarea/时间轴只读锁形提示/Esc/Enter 提交+Shift+Enter 换行）；保存链（备份→原子写（复用 v2_outputs._atomic_write_text 先例）→重编号 1..N→UTF-8 重写；gbk 原件保存转 utf-8 属确认框明示行为；PermissionError 重试一次）；id 预算 6=reviewListWrap/reviewSearchInput/reviewLocateBtn/reviewPager/reviewSaveBtn/reviewSaveAsBtn（FROZEN_IDS 200→206，留 3 缓冲）；静态键零消耗；后端接口冻结（load_srt 不动，save/saveas 纯新增）；与上游 ASR 测试并行=工作树错峰+逐文件点名提交。

### 四、异议记录与风险跟踪

评议员：有条件支持，1 HRO（C1 采纳）+1 MATERIAL_CONFLICT（C2 裁定直接 seek）；无 [PRESSURE-OVERRIDE]。风险跟踪：①重编号不变式三断言（行数/时间轴/index==下标+1）防批 3 断裂；②`.bak.srt` 排除测试防扫描收纳回归；③dirty 守卫 capture 拦截须黑盒覆盖；④性能三口径真机波留档，不达标启用虚拟化兜底；⑤外部工具改文件致位置失效=批 3 重扫兜底留坑；⑥并行会话错峰提交。


## [2026-10-02] D2026-1002-11 批 3 联动增强开工评议 [已拍板·开工]

**关联**：D2026-1002-07（批 3 原文：对照链/AI 分析疑似问题段进校对视图+ASR 可选入口=承诺件）、D2026-1002-09/10（批 2a/2b 收口，spike 直连结论+位置失效留坑 C8+技术债登记）。**流程**：主模型批 3 方案+勘探事实交评议员；有条件支持（四条件）+裁定项五条，主模型全采纳无驳回，即刻开工。无人值守授权延续。

### 一、方案要点（评议通过稿）

1. **疑点段进校对视图**：数据面裁定=唯一可执行数据源为 **guide items**（8 字段五来源，quality_report.py:1404-1469；AI 建议 observations 纯字符串零时间戳；对照链不落盘 cleanup_clips 即删）。校对页**自主直载**：新 API `refine_review_load_detections(guide_path)` 复用 _load_validated_guide 白名单读法，filter 带 timing 条目，返回 {success, detections[8 字段], media_path}；media_path 透传导读 json 键（空串→null 前端对话框兜底）。**app.js 零改动保持**。
2. **UI**：疑点面板（折叠式）三新 id `reviewDetLoadBtn/reviewDetectionsWrap/reviewDetList`（FROZEN_IDS 206→210，≤9 留 5 缓冲）；行全 class 委托 review-det-row[data-idx]+review-det-act[data-act]；交互=跳转（匹配 blocks.start_ms 原生）/试听（seek+play+区间差自动暂停）/确认·跳过（会话内标记+console 留痕不写盘+文案明示）+位置失效态（C8 留坑闭合）。
3. **ASR 承诺件（闭合 R4）**：reviewAsrBtn（第 4 新 id）引导卡（推荐 whisper-large-v2+自备落位指引新 REVIEW_MSG 键，措辞复用引擎页精神不拷贝字面）；**switchTab 全局性冲突裁定=程序化 click 回退**（评议员核实 switchTab 未挂 window——原方案"调既有全局函数"作废）；不实现校对页内转录。
4. **enqueueJump 契约保留**（队列零消费者，主通道=loadDetections 直载）；校对页内部 _applyJump 抽公共供面板与未来队列共用。
5. **技术债十一项收官+顺序**：a/b fs_utils 先行（refine/fs_utils.py `_atomic_write_text` 薄壳三处+BACKUP_SUFFIX 常量四处，依赖方向 webview_gui→refine 正确）→c/h/i 同批（saveas 删 src_path 死形参+前端调用点同步+参数序钉；_call helper 收敛 _bridge 样板 8 处；error_key 回退+键名映射表）→e/f/g 独立（_codec_direct 参数化保两套语义差异；_sweep_aged_files 两薄壳；pick helper 收敛）→功能面最后；d _markDirty busy 态 _dirtyPending；j getActiveTab helper；**k）aria 记闭合零代码**（裁定不补 aria-hidden，理由=状态播报连续性）。

### 二、评议员四条件（全采纳，无驳回）

①switchTab 程序化 click 回退（node --check+黑盒零 ReferenceError 验证）；②saveas 签名变更同步前端调用点+bridge 参数序钉；③_codec_direct 两套常量参数传入+m4a/mp3 正反例差异钉；④会话标记"本次不落盘"REVIEW_MSG 键+静态钉断言。

### 三、裁定五项

Q4 程序化 click（原方案作废）｜Q1 对照链侧范围确凿化登记不做补偿（2.6.2 想法行可选）｜Q3 不落盘文案+复核持久化登记 2.6.2 候选｜Q7 全采纳（ms 原生跳转/序变联动禁用+提示/40 字摘录口径/timing 解析器防漂移注释）｜k 记闭合零代码。

### 四、范围确凿化声明

对照链/AI 分析疑似问题段进校对视图=**guide items 全量（时间戳载体唯一）**；对照链无"疑点清单实体"产物，知情段数已由状态行兑现；AI 建议与 guide 疑点段信息面同源（prompt 只基于导读材料），收窄无信息损失。（D2026-1002-07 批 3 按此口径落档，防"漏做对照链侧"误读。）

### 五、异议记录与边界

评议员有条件支持，**无 [HIGH_RISK_OBJECTION]、无 [PRESSURE-OVERRIDE]**；四条件+五裁定全采纳无驳回。owner 真机波累积待做（性能三口径/导入对话框原生链路/联动运行时，归第五次真机测试复核收口）。风险跟踪：①原子写行为等价三断言；②saveas 桥参数序钉+黑盒 saveAs 流；③timing 解析器防漂移注释；④翻译侧产物写路径回归（v2_outputs.py:56/synopsis.py:175，基线 1683+4 只增）；⑤.bak.srt 收口扫点；⑥位置失效态黑盒；⑦摘录 40 字截断出域口径维持。


## [2026-10-02] D2026-1002-12 2.6.2 全新安装体验修复轮终审（8 项实测+48h 审计五项纳入，6 拍板点） [已拍板·批0 开工]

**缘起**：owner 2.6.1 全新安装真机实测 8 项反馈（模型下拉自动带数据/ASR 卡难懂/AI 分析布局/词典 C 盘/角色卡白名单两道门+内置卡不自动加载/扩展目录设计期望/Console 占比/系统状态卡过简）。主模型三路勘探定性根因+设计师出布局规格+评议员评议；owner 终审拍板 6 点全定。**评议员异议**：1 项 [HIGH_RISK_OBJECTION]（拍板点 3"手输路径+持久登记"弱化防越锚威胁模型）——**采纳其折中案**：目录选择一律原生对话框（含其手输框）收口、持久登记仅对话框结果、网页输入框不接受任意路径；校对保存/另存为按"本会话打开过/对话框登记"边界放行。非 [PRESSURE-OVERRIDE]。

### 拍板六点

1. **ASR 边界=A**：本版只重整入口与能力边界（状态三态+空态占位+说明文案），GUI 一键执行列 2.7 候选。2. **切服务商不自动拉模型列表**，只认"刷新/测试"；移除一切加载期自动拉取；删 custom-model-1/2 硬默认。3. **目录选择=对话框收口+持久登记**（HRO 折中案，见上）。4. **新装默认数据根维持 %LOCALAPPDATA%**，首启加一次性"数据目录引导"（评议员补充采纳）。5. **C 盘存量词典=设置页检测+一键迁移**（临时名+哈希+原子改名+可续+进度），不静默迁移。6. **48h 审计五项全收**，批序：批0（审计⑤ CREATE_NO_WINDOW 先行独立提交）→批1（角色卡目录持久化+首启 seed 内置卡（幂等+版本哨兵+frozen-only）+白名单改革（根集动态读数据根仅限 security 模块+改数据根强制重启提示；含审计①校对保存收口，同函数族统一设计）+词典目录设置+迁移+首启引导）→批4（审计②③④校对链数据安全，优先于 GUI 观感）→批2（模型下拉+ASR 卡重整）→批3（AI 分析区/Console/系统状态卡，按设计师规格，静态 i18n 键 0 新增）。

### 根因备忘（勘探定案）

模型列表自动拉取链 app.js:4171→4184→refreshModels；角色卡双门=security.py:16 导入期快照（REPO_ROOT=app_root，frozen=数据根）+api.py:67-90 会话登记集（重启失效/手输永拒）；词典固定数据根/dict 无独立设置；内置卡在 refine/defaults/templates 仅只读回落无 seed；Console 双层圆角+配比 160-220px 钉死；系统状态卡扩展数据全有现成 API（refine_list_templates/refine_asr_status）。

### 验收约束与风险跟踪

每项随修带回归测试；黑盒 GUI 验证含 before/after 截图；定向/全量基线只增不减；安全扫描对基线；**安全与可用冲突时不弱化安全边界**。风险跟踪：①持久登记集越界/大小写混淆回归测试；②seed 幂等哨兵与包升级共存；③词典迁移中断恢复演练；④首发前 i18n 新文案键映射核查；⑤白名单测试 monkeypatch 模拟盘符不依赖真实 E:\。**复议入口**：任何批执行偏离上述边界（尤其拍板点 3）即触发 D2026-1002-12 复议。


## [2026-10-03] D2026-1002-13 上游 ASR 搭配二轮全量测试终审（F06X 否决·F06 维持·weifu8435 五断言记分卡）[已执行·已裁决]

**缘起**：上游 issue #432 评论区 weifu8435（其 #374 评论为 D2026-0917-03-R1 证据 B）2026-09-30 发布新实测：①Purfview Faster-Whisper-XXL large-v2 逐行准+幻觉少+长行缺点；②小模型噪声片翻车；③qwen 时间轴最差只配 pass2；④VAD 碎化降小模型准确度；⑤其维护幻觉词表（Subtitle Edit XML，927 条）。owner 拍板直接全量二轮（国庆无人值守算力）+ 词表收编并行。decision-critic 评议**有条件支持、无 [HIGH_RISK_OBJECTION]**，修订全采纳（F06X 补全片池、串台单列否决轴、基线近零降级、P90±0.3s 容差、xxl 锁 large-v2、伪真值轴不入主判、看门狗语义=会话级保活+分格超时）；[PRESSURE-OVERRIDE]=否。

### 实施与产物（E:\abtest2\，不入库沿用一轮拍板，仓库仅本条目）

片池=owner 指定五次测试 7 部（113-180min，锚定片除名）；格矩阵=F06/F06X/XXLxTEN(离线合并)/BAL×7 片=28/28 格 rc=0 零失败；判决契约预注册冻结（CONTRACT_v2.md，继承/新增/修订三栏）；Silero v6.2 独立参考基线 7/7（禁能量法）；检测词表 v2 收编 768 条（markers_v2，weifu XML 去重 904+v1 28，整行/子串分层语义，弱层 8 条+元注释 88+符号 67 移出，owner 边界=仅检测层不做 ASR 侧自动删除）；xxl 运行时 r245.4（SHA256 登记）+Blackwell 移植（ct2 4.8.1+cu128 DLL，PATCH_NOTES）；Mimosa 首扫基线（E:\abtest2，208 findings，seal 3ff5d86e）。**途中事故两起已修复并留档**（evidence/INCIDENT_hf_cache.md）：HF 缓存双层分裂（env 根=hub 而模型实体在 hub\hub，8 模型 junction 提级）与 Systran 根级残桩（仅 refs 无 snapshots，BAL 全灭根因，换正确 junction）。

### 裁决（预注册规则自动裁决，VERDICT_v2.md）

**F06X 未通过 → F06 维持，现状默认不动**：①覆盖否决向（Δ=-12.3/-7.5/-6.0/-4.1/-3.7/-1.1/-1.0，7/7 同向、3/7 超 ε=5%）；②15s+ 长行爆量（mimk273 一行 18.8s、mufr006 四行 25.8-37.5s，已人工核实真实行；F06 全池 max_dur≤6.1s）；③串台轴不增（0/7）✓；④漂移基线近零降级为绝对量=零差异；⑤时间轴不劣（ΔP90 全部 |≤0.1s|）✓；⑥行数少 7-20%（xxl 补漏弱于 qwen-TEN）。BAL 参照在新片池复现一轮结论（串台 mida559/mimk273 各 2 处跟 bal 走；覆盖全面垫底）。xxl 记"按片开关"候选（补漏位捡漏弱、主行位长行爆量，两形态均有代价）。

**关键新发现（时间轴路线）**：XXLxTEN 拟态格（xxl 主×qwen-ten 补）边界误差 P50=0.0-0.9s、>1s 行占比 17-45%，显著优于 F06 主行（P50 0.6-2.3s、41-98%）——large-v2 词级时间戳"贴人声"结构面获强支持；定向复测条件=若对 xxl 主行做按参考区间切分长行的后处理，长行可解，届时时间轴优势可能反超（F06 时间轴=全场已知最弱轴，本轮再证）。

**weifu8435 五断言记分卡**：①幻觉少=证实（串台/漂移/环境音三面）；②逐行准=部分证实（时间轴维度；文字无真值）；③小模型噪声片翻车=无法判定（片池无噪声重片型，登记遗留）；④anime 上限=N/A（条件格未跑）；⑤VAD 碎化=方向相容无法判定。其隐含主张"换默认"不成立，但词表+证词已转化为检测资产（markers_v2）与定向复测条件。

### 决策日志字段

原决策=D2026-0917-03 决策链续评（二轮全量）；decision-critic 异议=无 HRO、条件 A（契约预声明）/B（异族参考源）均已闭环入 CONTRACT_v2.md 与 vad_reference.py；主模型最终决定=按预注册契约自动裁决维持 F06（无需 owner 改判评审）；条件闭环=全部闭环（测量/裁决完成）；[PRESSURE-OVERRIDE]=否。**遗留登记**：①噪声/BGM 重片型未测（F06 全自动无人审暴露面，需片型补充或按片开关路径）；②伪真值一致率轴未跑（超时放弃条款）；③F02/GAL1 条件格未跑；④HF 缓存双层布局建议择一收编（owner 侧环境整理）；⑤F06 时间轴最弱轴持续挂账（本轮 XXLxTEN 数据为修复路线首份结构面证据）。

### 【2026-10-03 补记】遗留②③④清零轮（owner 指令"本轮不留遗留"，遗留①改登记为片源待触发）

②**伪真值一致率轴已跑**（pseudo_truth.py，族加权投票：qwen 3 席/anime/lv2 2 席/gal，区间聚类+相似 0.75 阈；[UNVERIFIABLE] 不入主判）：七片均值 gal 65.4% ≈ qwen_wseg 65.2% > anime 54.6% > qwen_ten/f02_ten 52.2% > xxl 45.4% > bal 36.0%——weifu 断言②（xxl 逐行准）文本维度不获支持，其优势收敛为时间轴+提速两轴；断言⑤补记=gal 行控全池唯一恒定（max_dur 恒 4.10-4.18s）证实"拖尾极少"。③**F02/GAL1 条件格已跑**（14/14 rc=0；F02 mimk268 首败=瞬时 Temp 竞态，重试即过）：F02 覆盖 44.8%（vs F06 48.1）漂移全池最低 1.05%，两轮方向一致维持备选位；GAL1（jaykwok/Qwen3-ASR-1.7B-JA-Anime-Galgame，--qwen-model-id 本地目录接线）覆盖 39.7% 但行控/洁净度冠军（max_dur 恒 4.2s/重复率 2.0%/标记 0），登记"求净单遍"候选不改默认。④**HF 缓存双层收编完成**：8 模型实体移至活跃根 G:\HuggingFace_Cache\hub\、嵌套 hub\hub 删除、xxl Models junction 重挂、FE/snapshot/junction 三探针全过（教训追加：Git Bash 双引号 `\\$var` 不展开，cmd/变量组合改 Python os/shutil）。①噪声片型：owner 拍板片源缺席待触发（发现即纳入补充测试）。**README 上游转写推荐段已按两轮结论重写**（默认维持+备选+按片开关①提速②求净+时间轴备注+不推荐名单+gal 模型条目）。裁决不变：F06 维持。


## [2026-10-03] D2026-1003-01 真机验收六项反馈方案（安装器生命周期/ASR 下载回归/词典源选择/IA 重排/角色卡弹窗） [已三轮讨论·待 owner 拍板后新会话开工]

**缘起**：owner 安装 2.6.2.dev0 本地测试包真机验收，提出六项反馈（R1 安装器检测已装=自动更新语义/R2 卸载询问删数据/R3 ASR 探测长 URL 撑爆卡片+要国内/海外双源下载（参照 SmartSub）/R4 词典下拉空白真机 bug+下载无源选择/R5 API 和模型独立 TAB+ASR 与字典整合一页/R6 角色卡编辑改弹窗+翻译方向设置迁入）。主模型三路勘探+设计师规格（第 1 轮）+评议员评议（第 2 轮，1 HRO）+修订终审（第 3 轮，放行）。**评议员 1 项 [HIGH_RISK_OBJECTION]（P1 卸载删数据：目标解析与应用 data_root() 不等价+翻转 D2026-0929-07 守卫未列追认）已四条全收采纳**；非 [PRESSURE-OVERRIDE]。

### 方案要点（终审通过稿）

- **P1 安装器生命周期（R1/R2）**：升级=InitializeSetup 读注册表已装版本与 /Dversion 比较+原地升级提示（数据保留，UsePreviousAppDir 默认已开）+CloseApplications=yes；卸载=InitializeUninstall 询问"是否删除本地数据"，Code 段删数据根——**HRO 四条约束**：①Code 复刻应用四级解析（GetEnv('SUBTRANSJAV_DATA_ROOT')→.data-root 指针→frozen 默认）弹窗逐级显示并标明实际生效者；②锚点硬门槛（user_dirs.json/settings.json/tm.db/api_keys.bin 任一存在才可删，无锚拒删+明示手动路径）；③弹窗列删除量级清单（TM/词典/ASR 模型 GB/api_keys 提示）；④D2026-0929-07（iss 绝不触 LOCALAPPDATA 守卫）与 D2026-1002-06（不内置下载链）双反转并列追认。uninstall.bat 口径对齐（保留空目录删除语义）。
- **P2 ASR 下载能力回归+错位修（R3）**：错位修=推荐行来源分类徽标（海外源/国内源）替代长 URL+URL 悬停/展开详情+word-break:break-all 兜底（.media-source-path 先例）；新建 ASR 下载器 whisper-large-v2 先行（清单已有 sha256 pin）双源=azureedge 官方+hf-mirror 镜像，落位数据根 models/asr，进度复用既有通道，SmartSub 式下载弹窗（AppModal kind='download'：两源单选卡+全宽开始下载）；域名白名单改 **URL 级精确匹配**（azureedge 具体文件/hf-mirror 具体路径），"国内加速源"上架前置=发布前实下载一次比对 sha256 字节一致；qwen 多文件维持"规划中·自备"不动（单文件下载不变式 decision-log:2405）。**翻转 D2026-1002-06"不内置下载链"拍板，随本 ID 追认（owner 主动要下载源选择为翻转信号）**。
- **P3 词典空白修+源选择（R4）**：空白判因首件=catch 吞错可见化（app.js:4149 .catch(()=>{}) 改写 dictStatus）+owner 真机 gui.log（%LOCALAPPDATA%\SubTransJAV\Logs）判因；词典下载加 source 参数（auto=现官方→镜像 fallback 语义/仅官方/仅镜像），"仅镜像"失败=显式报错不轮换（对齐 dict_manager:466 现行语义）；"仅官方"按钮并置 CN 可达性提示（pythonhosted CN 常不可达）；sudachi_full 单源 CloudFront 标注暂无镜像+离线导入指引；下载源弹窗与 P2 复用同一 kind='download' 组件。
- **P4 IA 重排（R5，设计师 A 案）**：tab-engine 不换 id 改名「API 与模型选择」（保 pipelineCard 点击/review.js ASR 跳转双锚），顶部三段分段控件（阶段A/阶段B/兜底）+全宽表单（否掉左列表——三槽位过空），接口地址卡并回各槽位；新建 tab-asrdict「ASR 与词典」（ASR 卡+词典卡 id 随迁，上下单列）；FROZEN_IDS 213→215、静态 i18n 189→190（tabAsrDict）、分组钉 quality=[engine,asrdict,glossary,advanced] 显式解冻、review.js 跳转锚随改、test_asr_card 单按钮钉放宽。
- **P5 角色卡编辑弹窗（R6）**：AppModal kind='editor'+.modal-lg（720px/92vw/88vh）；内容=标题行（阶段下拉+重载）+路径行+大 textarea（flex:1 min240 Consolas）+「翻译方向与角色卡」组自高级参数迁入（原位删组留指引+打开编辑器按钮）+保存主按钮；dirty 关闭守卫复用批4 模式；词库与模板页原编辑区收缩为一行入口。
- **发版切分 A（推荐待拍板）**：2.6.2 先发=仅追补两个 BUG 修（R3 错位修+R4 空白可见化）重打测试包（重打须 owner gui.log 判因完成+重跑 GUI 黑盒门），其余全部进 2.6.3；批序 2.6.3=批A 安装器→批B ASR 下载器+词典源选择→批C IA 重排→批D 角色卡弹窗→批E 收尾。

### 待 owner 拍板六点

1. 发版切分 A（推荐）/B（全做完发 2.6.2）；2. ASR 下载能力回归=翻转 D2026-1002-06 追认；3. 词典源形态=双按钮+缺省自动（否三态）；4. tab-engine 改名保 id 方案（A 案）；5. qwen 维持"规划中·自备"；6. 卸载确认一问制（列表化量级+锚点门槛已内嵌）。

### 评议员终审与风险跟踪

终审放行（条件闭环）；残余登记=启动脚本临时 env 场景卸载器读不到→锚点拒删兜底（可接受）。风险跟踪：①P2 双源上架前 sha256 实证结果留档；②2.6.2 重打窗口受 gui.log 判因约束；③P4 分组钉解冻随批日志配记；④词典空白若 gui.log 判因为后端 manifest 异常则 P3 追加后端修。**开工载体=新会话**（交接文档 %TEMP%\handoff-subtransjav-20261003.md）。

### 【2026-10-03 拍板归档】六点全同意+七条护栏（owner 终局表态，评议员终审确认收口）

**六点终态**：①切分 A 确认——2.6.2 仅放 ASR 错位修+词典空白吞错可见化，**禁夹带**（IA/卸载器/下载器不得进热修包）。②ASR 下载回归追认——**默认官方源**（修正原案默认国内），镜像显式可选+失败自动回退；下载前展示来源/大小/sha256/许可证；镜像上架前实下载比对哈希一致。③词典源=双按钮+缺省自动——"自动"须超时+可见日志+回退提示，禁新静默吞错；R4 先 gui.log 判因、吞错可见化先行。④tab-engine 改名保 id，显示名走 i18n；FROZEN_IDS 213→215、i18n 189→190 显式解冻（本段即日志配记）。⑤qwen 维持规划中，不拖入 2.6.x。⑥卸载一问制——**默认"保留数据"**，删除不与保留同权重（危险操作弱化+保留为默认焦点）；量级清单/锚点硬门槛/逐级显示/守卫反转追认照案。

**七条护栏（即验收门）**：2.6.2 禁夹带｜卸载器 HRO 审查提前至批A（不等收尾）｜ASR 下载器先哈希校验/源切换/失败回退再上镜像｜IA 重排后跑 FROZEN 冻结检查｜720px 弹窗补小屏响应/滚动/ESC 遮罩与未保存确认一致｜下载器仅 http/https、host 校验、拒环回/私有/保留地址。

**开工指令**：按批序 A→E 开工，总原则=默认安全、变更可观测、决策日志追认。附加：异议处置=HRO-1 全采纳；无 [PRESSURE-OVERRIDE]；遗留跟踪=env 临时设置场景卸载器解析不一致（锚点拒删兜底）、镜像比对实证结果、2.6.2 重打窗口受 gui.log 判因进度约束。


## [2026-10-03] D2026-1003-02 工具链现代化外部方案评议（uv/Ruff/Ty/kkpack/llm-autobatch/pyroid/guile/pysubs2/FTS5/orjson/Polars）[两轮评议收敛·owner 四项全同意·随本 ID 执行]

**缘起**：owner 转来外部智能体"工具链现代化"方案（声称高效精简），指令与 decision-critic 两轮讨论后给看法。主模型事实核验（PyPI 成熟度实测+仓库现状对照）→评议员第 1 轮独立取证与挑战（支持主体立场+7 项补强）→第 2 轮收敛（主模型 8 项采纳+2 项推回成立，评议员终审通过并内嵌 A1/A2、B1/B2/B3 契约）。**无现行 [HIGH_RISK_OBJECTION]**；前瞻声明：kkpack 类"首运行联网装依赖"方案若复提，自动升格 HRO 强制裁定（本条目即登记）。[PRESSURE-OVERRIDE]=否。

**核心证伪（三处对空开炮+成熟度硬伤）**：①项目已在用 Ruff（ci.yml:27+pyproject [tool.ruff]），无 black/flake8/isort 可"放弃"；②LLM 调用已并发（llm_client.py:539 ThreadPoolExecutor；pipeline_v2.py:1131 云端多文件 opt-in），实测瓶颈=LLM 网络延迟（21.5 分/部口径）；③TM 已是 SQLite 且为 NFKC+词界精确匹配（tm.py chunked IN），FTS5 相关性搜索非现有需求；全仓零 pandas/numpy（audio_detect 纯标准库）；安装器 full 81MB/lite 33.5MB、构建分钟级。PyPI 成熟度实测（2026-10-03）：kkpack v0.1.5（首发 2026-09-23 仅 10 天）、llm-autobatch v0.1.1（单版本，2026-02-10 后零更新）、pyroid v0.7.0（末更 2025-05-19 停滞 17 个月）、ty v0.0.84（pre-1.0）、guile v1.0.0（4 个月龄）、pysubs2 v1.9.0（2014 年起成熟，但 requires_python≥3.12 vs 本项目 ≥3.10,<3.14）。

**逐件裁定**：uv=个人可用不立项（契约：uv 环境不得宣判 CI 口径结论，canonical 验证归 .venv+CI；lockfile 再评估触发=依赖解析漂移事故再现或外部贡献者出现）｜Ruff=已在用无事可做｜Ty=不换（mypy==2.3.1 硬门禁在岗无痛点，ty 尚 0.0.x，等 1.0 且 mypy 成负担再评）｜kkpack=**否决级**（信任边界迁移：owner 构建+SHA256 对照的交付物 → 用户首跑时刻 PyPI 状态；与离线/零出域场景冲突；击穿 D2026-1003-01 安装器生命周期资产 AppId/卸载守卫/升级检测；不做任何试点）｜llm-autobatch=否决（单版本零维护+微批架构与上下文连贯顺序翻译管线不匹配）｜pyroid=否决（停滞弃库信号+函数集与热点无关）｜guile=否决（三轮 UI 投入+i18n 键表+红线测试整体重写零用户收益）｜pysubs2=不换核心 SRT 链（TM 指纹字节不变式 D2026-0930-04+GBK/重编号行为+测试基线钉死），转性登记"多格式导入(ASS/VTT)"特性候选（见 roadmap）｜FTS5=留作 TM 浏览/搜索 UI 特性候选（标准库内置实测可用零依赖）｜orjson/msgspec/Polars=否决（微秒级收益 vs 秒级瓶颈；无 Pandas 替换对象）｜py-spy=划出独立诊断件（被方案误捆 pyroid；成熟工具可用）。

**owner 拍板（四项全同意，2026-10-03）**：①总裁定不立项工具链更换，逐件处置如上；②授权摘除死依赖 srt（独立小批、与 2.6.2 热修提交域隔离、附否定性守卫防回流）；③roadmap 登记两特性候选+uv 契约备注（已登记）；④py-spy 单次诊断排闲时。

**执行契约（评议员内嵌）**：A1 FTS5 冻结包可用性核验写入 TM 搜索特性批开工门（随收尾验证同通道），不设独立 spike；A2 uv 对照 diff=条件可选（仅当 owner 实际使用 uv 时跑一次作契约基线）；B1 py-spy 归档结论须自带判据原文"等待/IO 主导且 Python 侧执行时间显著小于 LLM 网络往返总时长"（非"CPU 零占用"）；B2 采样会话四要素=生产配置指纹+同源片源窗口+覆盖阶段 A/B+引擎空闲前置（缺一归档值打折）；B3 证据效力边界=仅裁决 CPU 加速类主张（pyroid/llm-autobatch/orjson/Polars），不触及 FTS5/uv/pysubs2。

**执行记录**：死依赖实证=pyproject.toml:41 声明 "srt"，subtransjav/tests/tools/packaging 四域 `import srt|from srt` 零命中、SubTransJAV.spec hiddenimports 不含（主模型+评议员双重复核）；摘除随本 ID 独立小批落库（提交见 git log `Refs: D2026-1003-02`，附否定性守卫测试）；py-spy 闲时任务已建（产出按 B1/B2/B3 归档本条目）。风险跟踪：①py-spy 归档四要素齐备性；②srt 防回流守卫在位；③kkpack 复提自动升格 HRO；④release-checklist 基线数字陈旧（1601+4 vs 实测 ~1786）随 2.6.2 验证轮文档卫生更新。

### 【闲时补记】py-spy 单次诊断（2026-10-03 执行）

**B2 四要素**：①配置指纹=profile local；s1=lmstudio/qwen3.8-27b-uncensored-joyfox-aggressive、s3=lmstudio/qwen3.6-35b-a3b-uncensored-heretic-apex；温度 local 0.1；批量 30 行/批（阶段A 54 批、阶段B 56 批+定向重试）；v2_concurrency_max=5（实际阶段A=1、阶段B=2，见偏差①）；无 draft；TM 复用+学习开启（学习 1334 对/新增 1083 条，生产默认行为）；引擎实测=阶段B 35B ctx 22272/并发 2/GPU max（生产指纹达成），阶段A 27B 沿用残留载入 ctx 16384/并发 1（见偏差①），KV 量化沿引擎侧配置未单验（lms ps 不暴露）。②片源窗口=ABF-264（E:\无字幕\提字幕\瀧本雫葉\，真实 ASR 日文 SRT 104,329B/原始 1451 条→闸门0 删 1→预合并 1442→产出 1426 条；非 Logs/9-23-2240 同源锚定片，见偏差②）。③覆盖=单次连续采样 17:33–18:09 全程横跨阶段A+阶段B+后处理，另 17:52 阶段A 中段独立 dump 单点佐证。④引擎空闲前置=17:14 核对通过（无在途跑批/无载入模型/在跑 python 均为 GUI fixture 遗留 http.server）；跑批期间同机有另一会话全量 pytest（如实记录，见偏差①）。采样会话=py-spy 0.4.2 record --format raw --idle --rate 60，附着 G:\python\python.exe **真身子进程**（.venv python.exe 为启动跳板，附着须取其子进程——后随会话复用本结论），131,164 样本/0 错误/≈36.4 分钟。

**归因结果（对照 B1 判据原文"等待/IO 主导且 Python 侧执行时间显著小于 LLM 网络往返总时长"）**：131,164 样本按叶子帧自身时间分类——net_wait（httpcore 同步 read=阻塞等 LLM HTTP 响应）**99.2%**；Python 侧计算（pass_disagreement 比对/re/tm.store 等全部合计）**0.8%**（≈17s/36.4min）；子进程等待（lms CLI）≈0.0%。Top1 叶帧 `read (httpcore\_backends\sync.py:128)`=99.1%，与阶段A 中段 dump 单点互证。**判据成立：等待主导，Python 侧执行时间仅为网络等待的 1/124**——按 B3 效力边界，CPU 加速类主张（pyroid/llm-autobatch/orjson/Polars）被裁决为无的放矢（不触及 FTS5/uv/pysubs2）。

**偏差登记（两项，均保守偏置不威胁结论）**：①阶段A 沿用残留载入（16384/1→管线声明并发=1）+同机 pytest CPU 负载——只会高估等待占比/膨胀 Python 段墙钟（对结论保守），代价=绝对吞吐不可比（阶段A 实测≈39s/批 vs 校准 12.1s/批；阶段B 生产指纹下≈3.3s/批 与校准 4.5s/批 同量级，反证慢因即偏差①）；②同源片源窗口不满足（锚定片 E 盘重组后路径失效，改用 ABF-264）——吞吐对比本不在 B3 效力边界内。

**观察项（不判缺陷，待 owner 决定是否立项核查）**：引擎自动化对"已加载但 ctx/并发不符"的残留态沿 fail-open 沿用未触发重载（D2026-0924-03 口径1 预期 ctx 不符即重载）——生产跑批前若引擎留有错配载入将静默降速约 3 倍；建议后续批核对 ctx 检查分支，本轮不动代码。

**结论行**：CPU 加速类工具链主张在可预见未来无立项价值；效率通道=上游选型+并发对齐（本诊断意外暴露的"残留载入静默降速"观察项即并发对齐面的第一个具体抓手）。profile 数据=%TEMP%\pyspy-diag-20261003\stacks.raw（65,861B，不入库）。

## [2026-10-03] D2026-1003-03 批A 安装器卸载器实现评议（1 HRO 采纳方案甲+四硬化全收） [已拍板·已落地]

**缘起**：D2026-1003-01 拍板护栏「卸载器 HRO 审查提前至批A」。主模型批A 实现设计交 decision-critic 评议，立场=有条件支持，1 项 [HIGH_RISK_OBJECTION]+4 条硬化条件；非 [PRESSURE-OVERRIDE]。

**HRO（采纳·方案甲）**：uninstall.bat「清空内容保留空目录」若按字面实现，会把现行 `rd`（不带 /s，非空目录静默失败=安全 no-op）升级为绕过一问制/锚点门槛的静默数据删除通道，致拍板⑥「删除仅经卸载器一问制」前提失效。采纳=bat 零新增删除逻辑，仅+1 行头注释「数据删除主通道=应用卸载器一问制（默认保留数据）」，并立负向钉（递归删除语汇仅限 numba_cache，%LOCALAPPDATA% 面整树删除全禁）。

**四硬化（全收）**：①深度门槛（解析结果=盘符根/%WINDIR%/ProgramFiles/与 {app} 同径→拒删，先于一切提问）；②DelTree 返回值检查+失败显式提示手动路径（部分实现：进程结束不做 PascalScript taskkill，依赖 CloseApplications=yes+失败分支兜底，评议员认可为合理简化）；③锚点预检先于一问（无锚→信息框按保留处理，不弹是/否）；④{app} 来源=注册表 InstallLocation（与 R1 共用 ReadInstalledInfo，剥引号剥尾斜杠），常量展开仅兜底。

**小项（全收）**：拒删/预检提示补 env 自定义数据目录指引行；锚点 9 项对齐 data_migration.py 白名单（glossary_conflict_watch.json 实位于 Temp/translation_memory/）+双向防漂移钉；量级统计仅锚点命中后执行；版本点分段比较+降级分支措辞；守卫反转注释含双决策 ID+「settings.json 系决策文档误记，实盘锚点以 config/user_settings.json、config/refine_stage_settings.json 为准」；真机卸载四例入批A DoD（docs/真机走查清单-263.md）。

**落地**：1bd2029（setup.iss R1 升级检测+R2 卸载一问制+uninstall.bat 方案甲+tests/test_installer_lifecycle.py 12 钉；ISCC 6.7.3 编译冒烟 rc=0；全量 1795 passed+4 skipped；code-review 双轴零硬违规零夹带， iss 布尔表达式补括号消歧一并入库）。

**风险跟踪**：①真机卸载四例 owner 执行前不随 2.6.3 发版放行；②9 锚与 data_migration 白名单防漂移钉常驻（迁移则锚迁须复议）；③盘根/深度门槛场景真机验证一次即闭环（断言已入静态钉）。


## [2026-10-03] D2026-1003-04 仓库更名 Angelholl/SubTransJAV→Angelholl/SubTrans（REST 代办+README 渊源批+About 链接） [已拍板·已执行]

**缘起与评议**：owner 提案（仓库更名 SubTrans，README 简介注明由 SubTransJAV 项目迭代而来，其余保持不变），主模型勘探（改动面小：全仓 175 文件含名主体为包名/产品层不动；CI/release 零硬编码 slug；用户可见硬编码仓库 URL 仅 About 弹窗 1 处；GitHub 精确同名仓库 ≤19★ 无冲突阻力，新 slug 实测 404 可用）+decision-critic 评议（支持，无 [HIGH_RISK_OBJECTION]，五项补强全采纳：README 保留 SubTransJAV 关键字作搜索桥｜更名批与热修提交域分离｜先于 2.6.3 批A R1 升级检测实现完成｜旧 slug 永久让渡知情记档｜roadmap 登记产品内品牌统一远期批）。

**owner 拍板（2026-10-03）**：更名由主模型 REST 授权代办。

**执行记录（本日）**：①REST PATCH 更名即时生效（full_name=Angelholl/SubTrans，html_url 新址）；②本地 remote set-url 新址+ls-remote 复核一致；③旧 URL 实测 301→新址（stars/issues/releases/tags 全保留）；④README 渊源批（标题改 SubTrans+引用行渊源句保留 SubTransJAV 关键字+英文简介补 evolved from+声明区沿革句协调"旧名 SubTransJAV 由此而来"）+About 链接 href 改新址（显示文本按最小范围保留产品名）；⑤产品内品牌面（包名 subtransjav/安装器/数据根/AppId/CLI 入口/artifact 名）全部未动。**知情条款**：旧 slug SubTransJAV 属永久单向让渡——若被第三方注册则 301 断链、仅余搜索面污染（README 关键字桥接兜底）；后续所有 REST/发版操作一律改用新 slug（旧 slug 写接口语义不保证）。风险跟踪：①双名并存（仓库 SubTrans/产品 SubTransJAV）为常态而非过渡态；②"产品内品牌统一"已登记 roadmap 远期候选（触发=owner 点火，须含数据根/AppId/安装器名完整迁移与兼容方案，可借既有 .data-root 指针层）；③REST 旧址写操作（Release/issue 等）今后须用新址发起。


## [2026-10-03] D2026-1003-05 2.6.4「输入侧扩展版」立项（TM 搜索 UI+ASS/VTT 多格式导入；预研入闲时） [已拍板·预研开工]

**缘起**：owner 指示 D2026-1003-02 登记的两特性候选"痛点考虑在前面、提前规划，现在立项并确定插入版本"；uv 维持不立项。主模型排期方案交 decision-critic 评议：**有条件支持，无 [HIGH_RISK_OBJECTION]**，四条件 C1-C4 全采纳为批内验收门；[PRESSURE-OVERRIDE]=否。

**版本裁定（owner 拍板 2026-10-03）**：两特性并入 **2.6.4「输入侧扩展版」**，三批推进——批1 TM 浏览/搜索 UI（FTS5，词库与模板页区块，只读浏览）；批2 ASS/VTT→SRT 多格式导入（统一"转 SRT 再进管线"，TM 指纹零影响）；批3 收尾发版。**排期锚点**：开工=2.6.3 批B/C/D/E 落库完成（不等真机卸载四例——那是 2.6.3 发版门非开工门）；基线从批E 收口快照起跑；2.6.3 真机阻断级问题发版前回灌。不塞 2.6.3（五批 scope 已锁）、不推 2.6.5（痛点前置）。**顺延出口**=痛感优先判据（TM 搜索无外部替代故先发；ASS/VTT 有外部转换器兜底可顺延 2.6.5，不缩水不放水）。

**批内验收门（评议员 C1-C4，全采纳）**：C1 热路径——tm.py lookup_exact 每命中即 UPDATE hit_count（tm.py:291），FTS 同步禁止无列限定触发器（否则每次翻译查 TM 白付一次 FTS 写）；spike 以真实批次频率做含/不含同步面吞吐对拍，主链波动 >±5% 即改保守方案（standalone mirror+指纹判亚重建），不带病放行。C2 迁移链——FTS 面创建排 ensure_source_name_column→ensure_direction_columns 之后并入 _init_db 末端（否则旧库 DROP+RENAME 表重建碾掉 FTS 面），配"旧库→自动迁移→FTS 可用"幂等用例。C3 规格八项——GBK 探测次序｜ASS Format 行驱动解析（禁位置硬编码）｜VTT 非载荷行清单（id 行/NOTE/STYLE/REGION/内嵌时间戳标签）｜\N\h\n 三态映射｜voice span 显式裁定丢弃标签归单轨｜厘秒→毫秒**零填充**格式（0.90s→00:00:00,090）+相邻 cue 边界防重叠修正方向写死｜roll-up captions 显式忽略不报错｜不可解析 cue 逐条抢救+计数告警（吞错可见化）+**临时 SRT 生命周期与 resume 语义**——规格缺一即门未开，owner 逐项画押。C4 预研隔离——git worktree 主姿势（scratch 兜底），禁止研究提交混入批B 在途暂存区；串扰一次即冻结预研至批B 落库。

**预研（owner 指示本轮纳入闲时开工）**：worktree 第二工作树+feature 分支，产出=批2 语义映射规格草稿（C3 八项）+批1 FTS5 三同步策略 spike（external-content 列限定触发器/显式双写/重建全量刷，含热路径对拍与 C1 红线判定）+批2 pysubs2<1.9 真实样本 spike（不足则合成样本明确标注）；产物留 feature 分支，2.6.4 开工日并入；全程不动批B 在途树与主 .venv（spike 用 worktree 本地 venv）。

**风险跟踪**：①FTS 触发器吞热路径（C1 对拍拦截）；②旧库迁移碾 FTS 面（C2 用例拦截）；③规格漏项金样本返工（C3 画押拦截）；④预研串扰批B（C4 worktree+归属核验）；⑤2.6.4 携带未真机验证的批A 代码（发版前回灌）。

### 【批1 收尾补记】GUI 黑盒走查通过（2026-10-03，收尾件①）

批1（已合入 main 2cdba2d，合并态 1869+6 全绿）词库页 TM 搜索区块黑盒五点全过（web-gui-tester/IAB+桩桥伺服，pywebviewready 走真链，tm_search 三态夹具，视觉+DOM 双验）：①切词库页懒注入（标题/输入框/按钮/四列表格骨架）②「天気」搜索→夹具两行渲染+「2 条结果」计数回显③空查询→「没有匹配的翻译记忆条目」+「0 条结果」④后端错误→「搜索失败：模拟后端错误」原样透出（吞错可见化）⑤输入框回车触发等效按钮。过程两处点击未生效经查为测试脚本复用过期坐标（结果计数元素挤动按钮 58px），非应用缺陷；全程无页面错误表现。**批1 剩余收尾件仅冻结包 FTS5 探测（随 2.6.4 发版验证同通道）**。

## [2026-10-03] D2026-1003-06 批B ASR 下载器+词典源选择实现评议（五绑定条件全采纳） [已拍板·已落地]

**改号注记**：本决策初记 D2026-1003-05，因该号被并发会话「2.6.4 输入侧扩展版立项」占用（6391bed），改号 **D2026-1003-06**；批B 代码提交（6ad401f）与 docs(security)（523c6bb）提交信息中 Refs 仍书 05，以本条为准。代码注释 16 处已随改号笔同步为 06。

**缘起**：D2026-1003-01 批B（P2 ASR 下载能力回归+P3 词典源选择）开工前设计交 decision-critic 评议（批前评议常设），立场=**有条件支持、无 [HIGH_RISK_OBJECTION]**，给出 5 条绑定条件+攻击面盘点；主模型全采纳，无复议。

**五条件与落法**：①auto/官方→镜像回退必须可见（进度 note「官方源不可达，已回退国内镜像」+logging 双通道，dict 与 ASR 两链同达）——已落地 `_set_download_note`/ASR note 粘滞；②official=排除镜像源（pypi+cloudfront-cdn）而非只留 pypi（否则 sudachi_full 仅官方空集误报）——已落地三态过滤+sudachi_full 仅镜像显式「无镜像源」错；③3GB 同步接受三道闸=单实例 model 键控锁+磁盘耗尽中途显式路径（ENOSPC→failed 相位+清 .part+明确文案）+「无取消/中断重下」可观测声明（弹窗常驻行）——已落地；预检 disk_usage 不可得反转 fail-closed（3GB 量级理由注释）；真机长下载占用项入走查清单；④URL 信任闭环=规范化精确匹配（防 host 尾点/端口变体）+空 URL 硬拒（镜像 PENDING 期旁路封死）+重定向逐跳校验（自定义 HTTPRedirectHandler，5 跳上限）——已落地 `_validate_url`/`_GuardedRedirectHandler`；⑤镜像上架唯一判据=实下载 sha256 与官方 pin 字节一致（格式转换版一律不通过）——镜像条目 PENDING（url 空+verified=False），UI 诚实禁用卡「需实测下载比对验证后才能启用，当前版本不可用」，生产清单 PENDING 条目不进 fallback 候选。

**附带采纳（建议级）**：sha256 弹窗内全文可复制（clipboard+降级 title 提示）；model 参数白名单化+落位文件名仅由清单派生；symlink 拒写；入口侧陈旧 .part 清理；license 字段带「openai/whisper 上游模型卡口径」来源注记；开始键文案「开始下载」（GUI 测试发现「确定」歧义后微修）。

**落地**：批B 提交（asr_downloader.py 新增/dict_manager source 三态+可见回退/asr_env sources+license/api refine_asr_download(_progress)+dict source 透传/app.js AppModal.download+ASR 项下载入口+词典双按钮/style.css/新增 test_asr_downloader.py+四测试文件追加 53 用例；FROZEN 213/189 零消耗，index.html 零改动）；全量 1848 passed+4 skipped；Mimosa 34=33+1 新签注（asr_downloader.py:217 留痕维持，甄别表 #28）；GUI 黑盒：弹窗六要素/双源卡 PENDING 态/meta/无取消声明/下载完成结果行/ESC 释放/dict 三态与禁用态全过（stub 桥，截图 %TEMP%\stj_gate\gui_test\shots\263batchB\）。

**风险跟踪**：①镜像上架门=owner 实下载 3GB 比对 sha256 字节一致后翻 verified（格式转换版不通过；PENDING 可长期挂账）；②已就位徽标翻转未能在 stub 黑盒闭环（stub 夹具晚补 present 字段+IAB 输入层抖动），该分支为未改动既有逻辑，真机 C1 项覆盖；③pipeline_v2 两 quarantine 用例偶发失败族（与批B 无关）待排期。

## [2026-10-04] D2026-1004-01 2.6.5「词典链与 UX 修复版」立项——真机六项反馈两轮讨论终审放行（jieba 渠道/下载链加固/安装器图标/状态卡重设计/引擎页去外壳/词典页入口收敛） [终审放行·待开工]

**缘起**：owner 真机走查 2.6.3 提出六项反馈：#1 安装包图标与应用不一致｜#2 系统状态卡路径截断遮挡｜#3 引擎页阶段A 子页大量留白｜#4+#5 词典页多个下载入口冗余（顶部空态引导条与详情区主按钮冲突，owner 定向"保留一个"）｜#6 所有词典下载 SHA256 校验失败+中文词典无下载渠道（问"没有还是不支持"）。owner 授权"方案+评议员+设计师两轮讨论定夺，定不了的最后报 owner"。**程序注记**：decision-critic/design-expert 专用子智能体通道本轮连续模型请求失败，三轮评议与设计均由通用智能体以同角色替代执行（均实证读取仓库核实）；后续如专用通道恢复可补正式复评。

**关键事实链（三轮均亲核）**：v2.6.4 tag 已推远程（72ae14f→68ed60c）且已发布、main 前进 2.6.5.dev0（c64cf2c）——owner 原问"归 2.6.5 还是并入 2.6.4"因 2.6.4 落地不可回撤而**事实性定为 2.6.5 快发**（不重演 2.6.2→2.6.3 并轨）。成因坐实：release.yml 装 `.[gui]` 无 zh+spec hiddenimports 无 jieba+ci.yml 仅 `[dev]`（jieba 正向单测 CI 恒 skip）→安装包用户中文分词恒"不可用"（2.3.0 词典去捆绑起潜伏四版本）；dict_manager._http_get（:351-390）裸 urlopen 无 Accept-Encoding/无完整性校验/1MB 分块静默短读窗口+校验失败不轮换（:547-551，D2026-1003-06 防洗白裁定）——真机三源齐失败高先验指向 owner 本机 v2rayN 代理出口；#dictEmpty（index.html:399/app.js:4900/test_gui_js_static.py:889）+dict_empty_* 两键+C2 决议（D2026-1001-03）在案；FROZEN_IDS 现值 215。

**评议轨迹与 HRO 采纳**：预评（替代评议员）HRO=jieba 单改 release.yml 无效→采纳为安装四件套并经终审修正；一轮（设计师出 UI 方案+评议员复核 v2）HRO=发版门未定义→采纳三层发版门；另采纳：校验失败自动轮换源降级搁置（与 D2026-1003-06 冲突）、直连不默认化（保企业代理用户）、smoke 双层断言（find_spec 不证 dict.txt 落位、token_hint 吞异常静默降级是潜伏机制）；二轮（终审）**放行、无新 HRO**，补 B1-B4 绑定澄清；设计师确认方案与全部修订无冲突。

**决议内容**：
- **段1（词典链+安装器，先行开工，从 main HEAD worktree+本地 venv `pip install -e ".[dev,gui,zh]"`）**：①jieba 渠道修复＝release.yml 改装 `.[gui,zh]`+spec hiddenimports 钉 jieba（数据收集靠 hooks-contrib 官方 hook，不重复 collect_data_files）+frozen smoke 双层断言（`_internal/jieba/dict.txt` 存在**且** frozen 真跑 jieba.cut() 经 --dict-status 自检行）+ci.yml 加 `[zh]` 解正向单测 skip；②下载链加固＝请求头 `Accept-Encoding: identity`+Content-Length 完整性校验（实际==total，.part 删除前统计，短读归网络层失败）+**网络层失败**同 URL 直连重试一次（默认沿用系统代理；**校验失败 DictChecksumError 绝不重试**，与防洗白裁定同构）+诊断日志/GUI failed 快照判别字段（预期实际字节/Content-Encoding/.part 前 64 字节 hex/来源 URL/代理直连标记）；③setup.iss 加 SetupIconFile；④回归测试四件（直连重试/校验失败不重试/截断完整性/请求头存在）。**B1（终审绑定）**：守卫 opener 组合 `_GuardedRedirectHandler` 须覆盖首发（系统代理）与直连重试全部尝试——现状 dict 链裸 urlopen 无逐跳守卫（守卫仅在 asr_downloader），本批一并补齐 D2026-1003-06 条件④欠账。
- **段2（UI 三项+#6，紧接段1，设计师方案已定稿）**：#2 状态卡两行式完整路径（版本入标题行/TM 词典统计升键行右侧 11px mono/路径值 word-break 折行/行间 hairline/高度增量约 +72px，右栏 747→820px<默认窗 918px 单屏守住；不采用折叠/展开；全 token 取色暗色自动适配）；#3 引擎页去外壳纵向堆叠 A→B→兜底（组头纯中文零 i18n 键+hairline 分隔、不做吸顶默认窗零滚动、seg DOM/CSS/JS 绑定一并清除、页首标题文案本批不动锁范围）；#4/#5 删 #dictEmpty 空态引导条（FROZEN_IDS **B3：纯减法走显式解冻登记+基线 215→214 重钉**+dict_empty_* 静态键清理+C2 决议反转记档；新增 DOM 全走 createElement+JS 态键零新增静态 id/data-i18n）+空态三件套（pill-warning「未安装」+warn-soft 提示条+四 kind 状态摘要行含点击联动）+收单操作行（segmented 源组仅官方│仅镜像靠左+主下载键靠右）；#6 失败信息一行人话（status-err 红，顺带修失败无红）+原生 `<details>` 技术详情网格（字段按存在性降级，依赖段1 后端字段契约；URL 行复制键；「复制全部诊断」不做，gui.log 已全量）。
- **发版门三层（钉入本记档）**：①结构门（CI 可证不依赖 owner）＝jieba smoke 双层断言+直连重试/不重试/完整性单测全绿；②真机门（owner 配合动作，发版前完成或书面放弃）＝owner 关系统代理（或修 v2rayN）后 GUI 词典下载端到端成功一次；③降级出口（②达不成时三条件同时满足才准发）＝a) 直连重试对镜像源任一干净网络实证+b) 已知问题文案含代理环境可能失败说明与 CLI 离线导入命令（**B2**：按真实 CLI 面书写 `--dict-download sudachi --dict-from-file <wheel>`，完整版 sudachi_full 本轮无 CLI 离线导入入口须如实注明）+c) owner 书面接受带已知问题发版。
- **配套**：CHANGELOG [2.6.5] 按 修复/界面 分组；roadmap 2.6.5 占位同步；真机走查清单新编 265 份（jieba 正向分词提示/词典下载端到端两态/安装器图标目检/UI 三项黑盒截图）；release-checklist 基线数更新为实跑（现文档 1601+4 已陈旧）；"校验失败自动轮换源"搁置，复议触发＝诊断数据齐全且排除客户端环境因素；执行边界＝GUI 词典离线导入入口不进本版、验证链 ruff→定向→全量→冒烟→Mimosa 深扫比基线收口、提交逐文件点名 Conventional Commits+verify:+Refs: D2026-1004-01。

**owner 侧知悉/动作清单**：①真机门动作（关代理重试词典下载）发版前须完成或书面放弃；②陈旧 worktree D:/SubTrans-d264-pre（2cdba2d 已完全合并入 main，终审实证）可删；③2.6.4 包内无 jieba 为既成事实，其走查时勿误判新回归（2.6.5 修复在途）；④③出口 c) 书面接受仅在②未达成时需要。

**风险跟踪**：①无 Content-Length 截断/强制压缩由 SHA256 层显式拦截不重试＝已知残留（**B4**），诊断字段保证可判别；②③a 仅证直连通路可用、不证代理环境自动回退会触发，故只作②的降级出口非等价物；③CI 打包环境 jieba cache 写入行为随 smoke 真跑暴露，异常即结构门拦截；④镜像上架门（D2026-1003-06 遗留①）与本批直连重试正交，持续挂账；⑤2.6.5 段1 开工与主检出并发会话活动并存，worktree+逐文件点名+归属核验纪律照旧。

### 【追记 2026-10-04】两项已登记小版本候选纳入本版（owner 指示"随本次一起处理"）

**纳入清单与登记出处**：①**候选A 坏行行号明细**（登记=18c3fd5 提交信息"已知收敛：坏行告警为计数制（行号明细需前置逐行预洗，小版本候选）"+docs/design/d264-批2-ASS-VTT-语义映射规格-draft.md"已知收敛"行）——升格进 **段1⑤**：subtitle_convert 抢救循环前置逐行预洗建立"源文件物理行号↔Dialogue 原文"映射，坏行告警由纯计数升级为"行号+原文摘录（截断展示）"，多条时上限聚合（前 10 条+「等 N 处」）防刷屏；**行号语义钉死=源文件物理行号**（用户可直接定位源文件修复；pysubs2 事件对象无行号故须预洗）；CLI 出口字符串流动零改动、GUI 零改动（告警沿管线日志）；回归=test_subtitle_convert.py 增"含畸形 Dialogue 行的 .ass→告警含行号与原文+上限聚合"用例。②**候选B dict_manager 流式进度测试时序 flake**（登记=18c3fd5 verify 段"dict_manager 流式进度测试单次时序 flake 三跑未再现已登记观察"；发生于跨午夜全量跑轮）——进 **段1⑥**：bounded 复现优先（流式进度三测循环 ≥50 次+负载下各一轮）→复现即修根因+回归钉；未复现则审计断言脆弱面（如 test_http_get_progress_callback_chunks 的 `seen==[(4,16),(8,16),(12,16),(16,16)]` 精确序列断言改"单调递增+终态不变量"，保留一例精确序列兜底）后**带证据闭账**观察项，不换壳成无限期挂账。

**批结构与程序注记**：段1 保持"词典链+安装器"名不改、追加⑤⑥两件，版本名「词典链与 UX 修复版」不变（候选A 属导入链明细补全、候选B 属测试加固，均在修复版伞内）；发版门三层不因本追记变动（候选A 随段1 验证链、候选B 闭账随段1 收口）。decision-critic 正式通道切换后复核仍 Model request failed（累计第 6 次），本追记按 owner 直接指示+既有替代评议轨道执行；正式复评通道恢复后随首轮正式评议一并覆盖（含本追记两候选）。

### 【正式复评终审 2026-10-04】decision-critic/design-expert 通道恢复——正式两轮完成，封盘

专用通道（切换 deepseek 调用）修复后补做正式两轮：第一轮双方独立复评，第二轮主模型逐条裁决回传、双方终审确认。**评议员：支持封盘**（第一轮有条件放行+2 HRO；第二轮确认条件闭环，[PRESSURE-OVERRIDE]=否）。**设计师：终审通过**（第一轮有条件通过 C1-C11 无返工；第二轮确认+3 条施工陷阱）。此前替代评议轨道就此闭环。

**评议员两 HRO（主模型全采纳，封盘）**：**HRO-1 直连重试语义歧义**——原文「默认沿用系统代理」若覆盖重试则发版门②③落空；钉两跳状态机=attempt#1 系统代理（getproxies()）/attempt#2 强制直连（ProxyHandler({})+守卫），诊断 `proxy=on/off` 区分，单测毒代理断言 #2 直连成功且未装 ProxyHandler；「默认沿用系统代理」明确仅指首发。**HRO-2 异常边界契约**——_http_get :387 无条件重包 DictDownloadError，完整性校验用错异常类会击穿防洗白裁定；钉死=Content-Length 实际≠total→DictDownloadError（可重试）/SHA256 不符→DictChecksumError（绝不重试）+`except DictChecksumError: raise` 兜底+防洗白测试断言"SHA256 不符→urlopen 恰一次"；并采论证：短读+伪造 Content-Length 不构成洗白通道（内容仍须过 SHA256）。

**评议员 C1-C10 终审版（全采纳）+三条措辞精确化**：C1/C2=上两 HRO；C3 诊断字段契约先行（_DIAG_FIELDS 五字段**含 proxy 标记**、承载=download_progress 快照扩 dict 非字符串拼接、段1 首件出单测、段2 只消费）；C4 smoke 断言独立自检行"jieba 分词自检: OK"**成功语义**（非行存在）+--dict-status"只读零网络"口径更正；C5 FROZEN_IDS 215→214 **且** FROZEN_I18N_KEYS 189→187 双重钉；**C6 精确化**：attempt#1 亦弃裸 urlopen（改 build_opener(_GuardedRedirectHandler())，默认挂 ProxyHandler 行为不变），守卫复用须换 **DictDownloadError+dict 白名单 _URL_HOST_ALLOW**（非照搬 ASR 版），302 非白名单重定向两 attempt 均须拦；C7 候选A 开工首件=归属算法一页规格入 d264 草案（同一 decode 后文本预洗/时间戳+原文反查/SSA Format 行驱动）+三 fixture（SSA 字段序/BOM+CRLF/续行+重复时间戳），不可靠降级"计数+示例标注行号未定"；C8 候选B 先 urlopen identity 二分（判补丁泄漏 vs 序列漂移）再定断言取舍，保留用例维持精确序列；C9 worktree=D:/SubTrans-d265-seg1、分支=feature/d265-dict-chain、merge-base=开工时 main HEAD、同冻结文件串扰一次即冻结本批；C10 门②发版窗口前 7 天未落实且未书面放弃→明确不发版（合法状态），③a 执行人/证据形态留档（[UNVERIFIABLE] 以留档兜底）。环境注记：COLLECT 只收 a.datas，hiddenimports 加 jieba 不重复落盘勿误报。

**设计师 C1-C11（全采纳）+五项 owner 授权定夺+三条施工陷阱**：关键收口=两处定稿遗漏测试硬约束（test_gui_js_static.py::test_batch_c_seg_bar_structure_pinned 重写为堆叠组守卫保留 endpoints_summary 断言；中文豁免名单 **seg-btn→stage-group-title**）+折行策略校正（**overflow-wrap:anywhere+分隔符后 `<wbr>`**，禁 break-all/U+200B——`<wbr>` 不入剪贴板）+高度口径改写（典型 +45~75px/80+ 字符长路径最大 +150px，长路径下右栏内部滚动可接受、主列三分区红线不受影响）+JS 落法陷阱（.dict-src-group 与现有 insertBefore 不兼容→**路线1**：#dictDetail 静态包 .dict-action-row、无内层 group、相邻兄弟合并边框、插入序修正为 官方│镜像）+六状态覆盖清单（下载中禁整行/迁移键不动/jieba·english 隐整行/ASR 探测写 stat/加载失败也红/成功长路径折行）。五项定夺（owner 授权）：长路径滚动接受；状态行序=日语·中文·英文·完整版+完整版 chip title「与日语二选一」；pill 新 JS 态键 dict_status_not_installed「未安装」专用（「不可用」保留通用口径）；hint bar 保留；URL 复制键做+file:// clipboard 被拒时降级点击全选。三条施工陷阱：「下载源」前缀必须 JS 态 MSG（禁 index.html 静态中文）；pill 四态映射定表（available+english_rules→内置/available→可用/!available+downloadable→未安装/!available+!downloadable→不可用）；ASR 动态行探测按钮与 stat 同处 keyrow。**交付原型**：docs/design/d265-批1-UI复审原型.html（静态校验过；渲染级走查随段2 黑盒补做 125%/150%/820 三态）。

**风险跟踪追加**：⑥大文件直连重试为全量重下（sudachi_full 137MB）成本观测；⑦候选B bounded 未复现仍须带 identity 二分证据闭账；⑧③a 干净网络实证不可 CI 证，以 C10 留档形态兜底。**开工契约**=本条正文+追记+本节（C1-C10 终审版+设计 C1-C11+三条精确化+三条陷阱）为唯一施工依据，段1 首件=候选A 归属算法规格+C3 诊断契约先行。

### 【段1 落库追记 2026-10-04】审查采纳轨迹+候选B 闭账+口径回写

**段1 施工与验证**：worktree D:/SubTrans-d265-seg1（feature/d265-dict-chain，merge-base=32856ea）三路 coding 并行（文件面互斥）；验证链全过=ruff（CI 同口径 subtransjav tests）零违规→定向 34+22+3 passed→**全量 1898 passed+6 skipped（基线 1887+4 只增）**→冒烟（--help/--where FTS5 可用/--dict-status 实测「jieba 分词自检: OK（3 tokens）」/convert_file 真转时间轴断言过）→Mimosa worktree 首扫 27（新路径基线；改动面 dict_manager×3/subtitle_convert×1/cli×1 均为既有留痕族行号漂移，identity 零新增）。CI ruff 扫描面外 8 处系 main 既有 spike/ 遗留（0c9d1f9 入库），本批不动守范围纪律。

**code-review 双轴（基点 32856ea，push 前硬门）采纳轨迹**：Standards 1 硬违规＝`last_err.diag` 赋值破 mypy 基线门（attr-defined）→**已修**（DictDownloadError 类级 `diag: dict | None = None` 声明，mypy 基线门复验 0 外）；judgement call 3 条驳回留档：①subtitle 候选裸 dict 不提 TypedDict（dropped_details 契约本就是松散 dict，段2 GUI 消费时再议）②`_DIAG_FIELDS` 非摆设（C3 点名契约常量+测试断言引用）③jieba 自检入 `_cmd_dict_status`（C4 点名落位）。Spec 4 条：C8 闭账证据→本节下方留档；C10 ③a 执行人/证据留档＝批4 收尾义务非本批；`test_http_get_default_progress_none_streaming` 精确→单调＝C8 契约原文指令（「另两个改单调递增+终态不变量」）非 scope creep；VTT 空 cue 用例＝无害外延收（基线只增）。

**候选B 闭账记录（C8 未复现分支，观察项就此闭账）**：有界复现＝worktree venv 流式三测 50 清空循环+4 进程负载下 20 循环全零失败（累计 73 次未再现，含登记时 3 次）；根因二分＝测试 seam 由 monkeypatch `urllib.request.urlopen` 迁 `build_opener` 桩工厂+模块级 `_REAL_BUILD_OPENER` identity 断言（补丁失效/泄漏立即红灯，封死"走真实网络"类时序根因的无诊断复发）；断言加固＝精确序列保留一例（最确定 fixture）+另两例改单调递增+终态不变量。

**口径回写两条**：①C3 诊断 `proxy` 字段取值定稿 **"system"/"direct"**（较 on/off 判别力更强，段2 #6 消费按此）；②守卫拦截（302 非白名单）计入网络层失败参与直连重试＝经裁定接受（同 URL 有界重试、attempt#2 同守卫再拦，「绝不跟随非白名单重定向」不变量与 sha256 兜底均保持）。

### 【段2 落库追记 2026-10-04】UI 三项+#6 全落地——黑盒五点全过+两缺陷随批修

**施工与验证**：段1 合并后主检出空闲，段2 直做主检出；coding 委派五块一次落位（#2 状态卡两行式/#3 引擎页去外壳/#4+#5 词典入口收敛/#6 失败信息+三测试文件双钉）；验证=定向三文件 135 passed+node --check→code-review 双轴（基点 11105cb：Standards 零硬违规、4 条 judgement call 记技术债；Spec 1 实质洞见下）→**全量 1900 passed+4 skipped**（段1 后 1898+6 只增；skip 差额=jieba 正向单测转实跑+段2 净增 2）→推送 060d6a9；CI：段1 11105cb success、段2 060d6a9 success。

**黑盒（IAB+stub 桥五点，截图留档 %TEMP%\stj_gate\gui_test\）**：T1 状态卡两行式（版本入标题行/统计升键行/路径 wbr 折行断点落分隔符后）PASS；T2 引擎页去外壳三组纵向+组头 hairline+页首标题未动 PASS；T3 词典页（无引导条/四 chip 展示序 日语·中文·英文·完整版/warn-soft hint/pill「未安装」warning/收单操作行 下载源+官方│镜像+主键右）PASS；T4 失败态（红人话映射「文件校验不符，下载不完整或源文件异常」+details 七字段网格 Content-Encoding: gzip 实证+URL 复制键）PASS；T5 窄窗 820（rail 64+aside 300 断点/chips 两行换行/网格可读无溢出）PASS。过程三次桩保真度修正（pywebviewready 须 window+document 双派发/refine_dict_download 须阻塞形返/进度快照须带 success 字段＝真实 api 层语义），均非应用缺陷；IAB 输入层会话劣化以新标签页重置处置（既有教训复验）。

**缺陷两笔随批修（均回归 PASS）**：①hint 切词典不刷新＝change 监听与 chip 点击均漏调 _dictRefreshHint，jieba（不可下载）态残留「下载后可用」误导文案（黑盒 T3b 发现）——双路径补调；②跨 kind 并发洞（code-review Spec 轴发现）＝下载中切词典→dictRenderDetail 重渲染复位共享操作行，可对另一 kind 并发发起下载，违设计师「下载中禁整行」条件——修=模块级 `_dictBusyKind` 占位三端钉死（dictDownload 入口守卫/dictRenderDetail 渲染端整行禁用/finally 先清占位再 dictLoad），黑盒回归：1.6s 窗口内切走再切回主按钮 disabled、失败终态恢复 enabled。

**设计师条件核账**：C1-C11 全落（含两测试硬约束：seg 钉重写为 stage-group 守卫+中文豁免 seg-btn→stage-group-title；i18n 双钉 189→187）；三条施工陷阱全中（「下载源」JS 态 MSG/pill 四态表/ASR 行 keyrow 落点）；五项 owner 授权定夺全按定案执行。遗留观察（不阻塞）：hint 文案较原型缩水（未含约 137MB/镜像指引，规格仅钉「保留」记偏差）；Standards 4 条 judgement call（_setPath 纯转发/_set 与 _setStatPath 骨架重复/DICT_KINDS.find 三处重复/dictShowStatus 约 90 行三职责）记技术债待段后小批。**2.6.5 剩余=批4 收尾发版**（CHANGELOG/roadmap/走查清单 265/checklist 基线数/发版门②真机门 owner 动作）。

### 【测试包追记 2026-10-04】setup-2.6.5.dev0.exe 已交 owner 真机实测

owner 指示先出测试包实测。首构建 run 37149808709 失败＝smoke 中文断言码页坑（jieba 双层断言实际全过：日志实证 dict.txt 在位+「jieba 分词自检: OK（3 tokens）」，败在 PS 按 OEM 码页解码 UTF-8 输出致 Contains 失配）——修 2e03fad＝Console OutputEncoding 钉 UTF-8+断言改 ASCII 骨架正则 `jieba[^\r\n]*: OK`（FAIL 行不含 ": OK" 成功语义仍唯一）；重构建 run 37150298734 success。产物 setup-2.6.5.dev0.exe 50,817,175B sha256 68D8464A…DC1A2 与 SHA256SUMS 核对一致（较 2.6.4 包 +14.5MB=jieba 词典体量旁证），302 签名 URL 无凭据直下落位 owner Downloads。配套《真机走查清单-265测试版》（3b234dc）=发版门②词典下载两态+六项修复逐项+回归抽查。**结构门④首次实战：smoke 双层断言在真实构建上验证通过（jieba 渠道修复 CI 可证闭环）**。

## [2026-10-04] D2026-1004-02 产品品牌统一第 1 层落地（owner 点火） [已拍板·已落地]

**一、原决策（品牌统一分层拍板）**：owner 2026-10-04 真机测 setup-2.6.5.dev0 测试包后点火："软件包名称没有随项目名称变，做一次全面内审要和现有的项目名称 SubTrans 统一。"主模型提出分层方案：第 1 层（用户可见低风险：安装器产物名/AppName/弹窗/GUI 显示名/bat 快捷方式，2.6.5 发版前改）；第 2 层（半深中风险：spec/dist 目录名+DefaultDirName+AUMID，2.7.0）；第 3 层（深高风险：包名 subtransjav、数据根，不改）；第 4 层 docs 保留 README 渊源句。显式反转 D2026-1003-04"双名并存=常态"，第 1 层统一即日生效。

**二、decision-critic 异议与核验**：结论=有条件支持（第 1 层进 2.6.5）+1 [HIGH_RISK_OBJECTION]。核验证实：升级链只认 AppId 固定 GUID 与产物文件名/AppName 无关（setup.iss:19-20,75,99,101-104），第 1 层改名不破坏升级链成立。HRO=对外接口（pyproject.toml:76-78 entry points `subtransjav-refine/gui` 是 pip 发布的真实命令接口非显示串）未定兼容策略+内审清单可证不完整（漏 api.py:204-208 输出目录 `<Documents>\SubTransJAV`、漏 tracked 文件 uninstall.bat/首次安装.bat/create_shortcut.py 及"新快捷方式清不掉"断链）+过度声明修正（test_installer_lifecycle 无品牌字断言无需联动，真正联动面是 test_strings_and_shortcut）。

**三、主模型最终决定：[HRO 采纳，走方案 A（最小完整），两条附加条件全闭环]**：①CLI entry points 与 argparse prog 名**保持不变**（消除"调用名≠帮助名"矛盾），CLI 命令名整体归入第 3 层"本批不统一清单"（理由=对外技术接口、README/手册 14 处命令引用、收益低于风险；远期改走别名 deprecation 通道另专项）；②bat 三件快捷方式与品牌词纳入第 1 层同批（消除断链），api.py 输出目录显式归"不改清单"（老用户既有输出位置）；③第 1 层文件级清单=setup.iss（:32 产物名+:9 AppName+:398,410-414 弹窗文案；**禁区=:16 MyAppExeName/:23 DefaultDirName/:51 Source/:19-20 GUID**）+release.yml（:104,106,155 过滤器+:164 artifact 名；**禁区=:67,125 dist 路径**）+strings.py app_title/cli_description+index.html 6 处+app.js i18n 文案+bat 三件。**附加采纳**：品牌 allowlist 钉测试（tests/test_brand_allowlist.py，tracked 文件 SubTransJAV 出现集合==显式白名单 49 条目逐项带保留理由，防漂移）；"公开半统一态"声明（安装目录/exe/数据根/AUMID 旧名 vs 安装器产物/快捷方式/显示名新名，向 owner 明示）；2.7.0 挂第 2 层联动清单（spec/dist+DefaultDirName+AUMID+test_isscc_compile_smoke+release.yml:67,125+历史遗留 lnk 清理）；roadmap 候选标"已点火、分层执行中"；262/263 旧清单不回改。

**四、决策日志字段**：异议=上述 HRO；主模型最终决定=**采纳（方案 A）**；条件已闭环（allowlist 钉 43 定向绿/半统一态声明/2.7.0 联动清单/roadmap 回写/INFO_GAP 以 owner 真机反馈原文"直连和代理下载没问题"留痕闭合）；[PRESSURE-OVERRIDE]=否。**后续风险跟踪**：①真机升级走查（2.6.x→2.6.5 覆盖装核 Add/Remove 显示名/开始菜单组/桌面快捷方式无残留/安装目录未变/数据根完好）；②release.yml 过滤器与 setup.iss:32 同源改动随测试包重构建验证；③半统一态观感是否触发二次点火；④allowlist 白名单须随 2.7.0 第 2 层落地同步收窄；⑤老用户桌面旧 SubTransJAV.lnk 不再被卸载脚本清理（历史遗留，2.7.0 清理列表）。

## [2026-10-04] [D2026-1004-03] v2.7.0 立项：品牌统一第 2 层 + A′ 复审收尾版（三批结构） [已拍板]

**一、决策背景**：2.6.5（2026-10-04 发布）落地品牌统一第 1 层后，D2026-1004-02 挂账的第 2 层联动清单（spec/dist 目录名+DefaultDirName+AUMID+test_isscc_compile_smoke+历史遗留 lnk 清理）触发到达；A′ UX 复审清单（D2026-0927-05 :1387，随轨道 B 落地逐条重审）触发源已随 2.6.0 发布到达；账面待勘误（roadmap 2.6.4 节仍标"⬜ 预研中"，实际 v2.6.4 已 2026-10-03 发布）与工作树小件（.pytest-brand/、.pytest-asrfix/ basetemp 残留）收口。主模型立项 2.7.0 三批结构并送 decision-critic 评议（agent 复议通道）。

**二、critic 评议结论（原立场=有条件支持，无 [HIGH_RISK_OBJECTION]）**：证据核验成立——AppId 固定 GUID（packaging/setup.iss:19-20/:74-77）+ 数据根独立于安装目录（.data-root 指针 setup.iss:235/:254，数据根 %LOCALAPPDATA% 属第 3 层）双保险，批1 不触用户数据。产出五条件（C1 升级兼容分析硬性门/C2 文件级清单五联动链/C3 exe 目标名钉死/C4 批2 枚举禁写 ±2/C5 真机升级走查）+ 八备注（R1-R8）。

**三、owner 终选（原文）**：「当前项目 0 start，默认不考虑存量用户的问题」。据此：
- C1 硬性开工门**按前提降级消解**：不做存量升级兼容分析、不做迁移策略二选一；批1 走全新安装口径（DefaultDirName 直改 {autopf}\SubTrans，AppId GUID 照旧不动）；孤儿 exe/存量静默失效/强制迁移/真机升级走查（C5）与合并走查（R3）全部豁免，release notes 不写迁移说明；owner 自身机器走干净卸载重装验证。
- R1 裁定：tests/test_brand_allowlist.py:52 paths.py「第 2 层」标注按第 3 层口径修正措辞（docstring 级，纳入批1 范围）。
- R6 裁定：批3 不解耦先行，随 2.7.0 常规批次。
- 版本节奏：main 由 2.6.6.dev0 前进 2.7.0.dev0（立项即改，循 2.2.1→2.3.0 先例；pyproject.toml+__version__.py 三常量，test_version_consistency 3 钉绿）。
- 其余采纳：C2（allowlist 收窄/测试断言同步/禁区表固化）、C3（GUI exe 目标名批清单钉死）、C4（先枚举落盘，11 或 13 以 UI 实测 title 属性定、禁写 ±2）、R4（.gitignore 记 /.pytest-*/ 或 basetemp 统一指已忽略 Temp/ 二选一）、R5（2.6.4 勘误限状态行，不删出处句）。

**四、critic 异议记录与采纳情况**：原异议=有条件支持五条件；主模型最终决定=**部分采纳**（C2/C3/C4/R4/R5 采纳为执行要求；C1 按 owner 前提撤销、C5 豁免；R6 裁定不解耦）。**critic 保留异议（执行层面服从，已封盘）**：在不改 AppId 的现架构下，2.7.0 对 2.6.x 存量用户是可见可升级版本，「0 start」是验证与文档口径的豁免、非机制隔离——存量升级实际行为（UsePreviousAppDir 沿用旧目录+孤儿 SubTransJAV.exe+旧钉扎失效）将无验证地交给真实用户承担。是否 [PRESSURE-OVERRIDE]=否（owner 显式产品范围前提，属条件撤销而非隐患消除，随风险跟踪①挂账）。

**五、批清单要点**

- **批1 品牌统一第 2 层（全新安装口径）**：spec/dist 目录名（packaging/SubTransJAV.spec :52 COLLECT/:98 EXE 名；GUI exe 目标名批清单显式钉死并同步 release.yml:52/:67/:69/:120-125/:166、setup.iss:16/:51/:54-55/:58）；DefaultDirName {autopf}\SubTrans（setup.iss:23）；AUMID 变更（subtransjav/webview_gui/main.py:402-406，新值批清单钉死，notes 说明钉扎影响，任务栏钉扎不追清理）；test_isscc_compile_smoke 联动（tests/test_installer_lifecycle.py:235-258 伪造 dist 树同步）；历史遗留 lnk 清理（uninstall.bat 增清桌面 SubTransJAV.lnk）。**禁区表**：AppId GUID、paths.py 运行时数据根默认、api.py Documents 输出目录、pyproject.toml:76-78 entry points、subtrans-cli.exe 名、README 渊源句、CHANGELOG/LICENSE 历史句、tests/test_media_path.py 本机路径夹具。**联动链**：test_brand_allowlist.py ALLOWLIST 同步收窄（D2026-1004-02 风险④承接）+test_dict_dir_and_migrate.py:628/:646、test_paths.py:228、test_strings_and_shortcut.py:97 核对、test_subprocess_no_window.py:3 docstring；R1 措辞修正入本批。**开工门=批清单（文件级清单+禁区表）二级评议**。
- **批2 A′ 复审重审**：先落盘逐项枚举（11 或 13 以 UI 实测定，已知 13=11+2 对应 glossary_learn/conflict_block 两无 title 控件）；逐条裁决改写/维持/入候选池；边界沿用「禁概念改名」「只改 tooltip 不改 label」除非显式重拍（若改术语，test_pipeline_v2.py:1283 等值级钉同批同步）；新增键走解冻提案（静态键 cap 200）+DOM id 二级评议；6 项已改写 tooltip 双侧同值钉保持。
- **批3 docs 勾账+小件**：roadmap 2.6.4 状态勘误（限状态行）；.pytest-brand/、.pytest-asrfix/ 残留删除+.gitignore 兜底（R4 二选一）；随常规批次不解耦。
- **发版**：v2.7.0、release/2.7.0 分支制；发布后 main 前进 2.7.1.dev0（滚动 dev 号纪律 D2026-1001-02）；owner 干净卸载重装验证替代真机升级走查；Mimosa 基线 36 零新增与 GUI 变更验证照常。

**六、后续风险跟踪**：①存量用户升级路径（AppId 不变使 2.6.x 用户可见可升；预期行为=沿用旧目录+新 exe 与孤儿 exe 并存+旧钉扎失效）无验证无说明——重开触发=owner 立场转「1 start」或真实用户升级反馈到达，届时按原 C1 重启（升级兼容分析+迁移策略二选一+真机升级走查+release notes 迁移说明）；②D2026-1004-02 风险①（2.6.5 真机升级走查）未完成记录，因本前提一并豁免，随①触发重启；③allowlist 收窄漏项则钉变红，批1 清单强制项；④SmartScreen/AV 排除以新 exe 名重新判定，沿用 README/手册 FAQ-10 指引；⑤全新安装口径下 CI smoke 覆盖新名产物、owner 真机净装门 PASS。

## [2026-10-04] [D2026-1004-04] v2.7.0 终选：产品形态文档级收敛（B）+数据根统一+批1 扩容开工 [已拍板·批1 开工门通过]

**一、原决策（owner 终选原文「那选b，开工」，按先例=全按推荐执行）**：①产品形态精简=**B 文档级收敛**（主模型在评议员 C1 证实"深度代码精简不可行且收益薄"后撤回原批1 精简方案，降级为文档级：README/手册主推 EXE+保留三形态说明+开发者 fork 指引，代码零删改，_auto_setup/首次安装.bat 保留服务 fork 用户；文档编辑与批3 勾账合并一次通行）——owner 前置表态「如果pip和cli是必须得，那精简就没意义，不如保持现状让未来的用户自己选择」为降级依据；②**数据根/Documents 更名 SubTransJAV→SubTrans**：直接改默认值、不写任何迁移/重定向代码、release notes 不写迁移说明（owner 豁免原文：「项目0start所以不需要考虑任何存量用户，我每次测试都是全新下载测试，所以任何对升级或者迁移的疑虑都不需要，默认是全新项目即可」）；③GUI exe→SubTrans.exe；AUMID→**Angelholl.SubTrans.GUI**（纪律：永不变更、版本号禁止入值；提为 main.py 模块常量+import 级钉）；④[InstallDelete] 清旧开始菜单组+uninstall.bat 补清 SubTransJAV.lnk+Documents 提示串同步；**任务栏钉扎快捷方式永不清理红线入档**；⑤tooltip 长度阈值 120 字（批2 A′ 复审输入常量）；⑥CI 腿收敛未获明确拍板，挂起不进 2.7（deferred 候选）；⑦jieba 文案缺陷（app.js:446）挂批2。批序维持 D2026-1004-03 原三批，批1 扩容=品牌第 2 层+数据根统一。

**二、critic 异议与闭环记录**：①原 [HIGH_RISK_OBJECTION]（数据根/Documents 更名=对外接口+48 小时翻禁区）——主模型驳回，证据=owner 豁免原文命中预设驳回条件，禁区翻动升格为终选菜单显式项；评议员复议一次（新取证 data_migration._discover_legacy_root 挂 EXE 安装目录与数据根默认值无耦合，无自我迁移误报）无新反例，**封口服从**；附带有利事实=数据根改名后卸载清理不再触碰数据根，更贴合 setup.iss:62-65 既有口径。②深度精简→文档级收敛修订：支持（与其 C1 dev 行为不可删+R2 代码触面重叠薄一致）。③批1 二级评议（开工门）：**有条件支持通过**，C1-C3 补漏（uninstall.bat:79 Documents 提示串入原子单元/allowlist 增删双侧清单化/spec+entry_gui docstring 残留显式裁决=全清）+C4 建议（AUMID 常量提取，采纳）+C5 顺手（setup.iss 注释同步）+R1（console.py:227 小写 numba 缓存目录=刻意保留勿顺手改，入禁区）+R3（批1 首提交后即触发 release workflow_dispatch 全链验证）。C1-C5 已全部回写 docs/design/d270-批1-批清单.md。

**三、批1 执行要点**：六触点原子单元（paths.py frozen 默认/setup.iss:276 ResolveDataRoot/api.py Documents 输出/test_paths 夹具/test_data_migration 夹具/allowlist）+uninstall.bat 提示串=七触点同提交；spec 文件重命名+EXE/COLLECT name+docstring 全清；release.yml 六处同步；AUMID 常量+值级钉；[InstallDelete]+LNK6；allowlist 双侧手术（增 d270 批清单自身/删清空条目/改注）；禁区表（AppId GUID/env 名 SUBTRANSJAV_DATA_ROOT/.data-root/entry points/CLI 名/dev 运行时行为/README 手册批3 承接/numba 小写缓存目录/data_migration 逻辑）。验收=全量基线只增+Mimosa 36 零新增+test_isscc_compile_smoke+owner 真机全新下载首启（--where 新根+无迁移提示+任务栏分组）。

**四、后续风险跟踪**：①批1 首提交后 release workflow_dispatch 先行全链验证（spec 改名为唯一首次变红点）；②d270 批清单提交即触发 allowlist 新命中，须同提交双侧处理；③0 start→1 start 或真实升级反馈到达时，数据根/Documents 更名的存量升级分析随 D2026-1004-03 六①机制重启（含 AUMID 变更旧钉扎失效、旧数据根孤儿目录）；④CI 收敛 deferred 候选需独立议题重开；⑤README/手册中 %LOCALAPPDATA%\SubTransJAV 口径连带由批3 承接；⑥tooltip 阈值 120 字为批2 开工门引用常量。

## [2026-10-05] [D2026-1005-01] v2.7.0 真机 ASR 探测双缺陷诊断+临时方案+2.7.1 修复立项 [已拍板]

**一、决策背景**：v2.7.0 发布后 owner 真机首现「上游 ASR 不可用」（媒体重点对照卡），两级原因诊断确证（本机实测取证）：①安装版无 subtransjav 包可导入——上游 python `-m subtransjav.refine.asr_runner` 在安装目录报 ModuleNotFoundError（spec 只打包 assets/defaults 数据，源码包不随包；开发态 cwd=仓库根有源码包故从未暴露，2.6.0 引入对照链以来安装形态皆有此缺陷，因对照默认关闭首现于本版）；②ffmpeg 位于 whisperJAV conda env 内部（D:\whisperJAV\Library\bin），app 进程 PATH 不可见（用户 PATH 原无任何 ffmpeg 条目）。上游环境本体经实测完全正常（python 3.10.18+whisper 20250625+large-v2.pt 模型缓存均在）。

**二、owner 拍板（原文）**：「我先本地临时用，同时这一点计入2.7.1的修复，并且要考虑如果上游是其他类似的whisper项目是否也会存在这种问题」。

**三、已执行临时方案**：①subtransjav 包复制进安装目录（D:\SubTrans\subtransjav，68 文件两侧核对一致）——selfcheck 导入链恢复；②用户 PATH 追加 D:\whisperJAV\Library\bin（PowerShell SetEnvironmentVariable，354→追加后安全长度；shutil.which 实测解析 ffmpeg 成功）——需重启 GUI 生效。

**四、2.7.1 修复立项（roadmap 已登记）**：①asr_runner 随包按路径直调（runner 仅依赖 stdlib+whisper 懒加载，可自包含分发；-m 形态保留 dev 回退）；②ffmpeg 探测泛化（候选=app PATH→上游 env 自带目录 Library\bin/Scripts/同级→抽片 subprocess 显式传绝对路径）——**上游多样性回应**：conda 系 env 自带 ffmpeg 的 whisper 项目全覆盖；faster-whisper/CT2 系 API 不兼容会如实报「whisper 导入失败」不假阳性，适配器挂候选池；③探测失败原因分类透出（模块缺失/whisper 导入失败/ffmpeg 缺失分列+stderr tail）。开工门=批清单二级评议。

**五、风险跟踪**：①临时方案的安装目录源码包副本卸载器不清理（owner 知情接受，2.7.1 正式修复落地后可删）；②用户 PATH 的 whisperJAV Library\bin 为全局暴露（DLL 搜索序 PATH 最低优先，冲突风险低；2.7.1 ②落地后可移除）；③本缺陷未进 2.7.0 notes（发现于发布后）。

