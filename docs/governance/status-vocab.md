# status-vocab.md — 状态词标准化（账本收口治理轮，2026-10-22）

## §1 固定枚举（8 词，唯一合法状态词）

| 枚举词 | 定义 | 出账行为 |
|---|---|---|
| closed | 已执行/已核销/已回写，无需再出账 | 只引用，不生成待办 |
| closed_observation | 已收口但属长期观察/暂停非退役，按 next_review 出账 | 未到期不出账；不得写成"在途欠账" |
| owner_decision_pending | 规则变更或需 owner 拍板 | 每轮只出现一次，附默认选项与拍板问题 |
| optional_decision | 原账已关闭，保留可选增强 | 默认不动，除非 owner 明确覆盖红线 |
| meta_cleared | 元澄清/事实勘正类，已收口 | 命中只引用 |
| written_back | 已回写销账并有推送证据 | 只引用（须带 commit/ls-remote 证据） |
| open | 真实未完成项 | 正常出账 |
| evidence_gap | 证据不足，待补证 | 只出补证清单，不生成执行动作 |

枚举增补（standing/paused）属规则变更，待 owner 拍板（见 closure-map **provisional** 区 GOV-P-2026-1022-01，尚未入 decision-log）；拍板前按下表消歧规则处置。

## §2 旧状态词 → 枚举映射

| 旧词 | 映射 | 消歧规则 |
|---|---|---|
| 待执行 | open（真欠账）或 written_back（追记已完成仅标签滞后） | 须下钻条目正文判别；D2026-1020-01 核销表三标签即"标签滞后型"，已核销 |
| 在途 | **废弃词**（C22 误列的原始触发词） | 禁止自动 1:1 映射；强制人工消歧：语境为"等令执行"→open，"观察未到期"→closed_observation，"可选增强"→optional_decision，"已随关闭不再挂"→closed |
| 维护 | closed_observation（触发型 next_review）或 meta_cleared（判据本体已交付） | "维护"＝持续动作非一次性交付，不得随整条核销吞掉残余（③⑤-standing 先例） |
| 观察 | closed_observation | next_review 必须为日期或显式触发条件，禁止留空 |
| 暂停 | closed_observation（暂停≠退役） | 枚举无 paused 位，按消歧规则；"暂停非退役"是状态词非欠账 |
| 已回写 | written_back | 须有推送证据（commit＋ls-remote），否则降 evidence_gap |
| 待 owner 令 | 两义强制拆分：可选增强→optional_decision（①-residual 先例）；规则变更→owner_decision_pending（②先例） | 判别式：原账是否已关闭——已关闭＋默认不动＝optional（主账仍归 closed，optional 只挂在单列残余条目上）；原账未关闭＋须拍板改规则＝pending |
| 已核销 | 两义强制拆分：账面回写→written_back（⑦先例）；事实勘正→meta_cleared（③先例） | 判别式：核销对象是"标签/回写"还是"事实认定" |
| 已收口 | closed（一次性）或 closed_observation（含观察残余） | 残余单列 canonical_id，不得打包 |
| 已拍板/已执行 | closed | 与"待拍板"不得混入同一摘要 |
| 挂账 | open（真欠账）或 closed_observation（触发型） | 已勾销的挂账（D2026-1021-01 三点）＝closed/written_back，只引用 |
| 等令 | open 或 owner_decision_pending | 无触发线定义的"等令"先下钻正文：已交付/已定性即 meta_cleared（③先例） |
| 无回音 | 默认禁止使用 | 已随关闭不再挂"在途"（⑤先例）；跟踪类须新立独立条目走 owner |

## §3 使用规则

1. 任务标题、摘要、扫描输出、审计报告只能使用 §1 枚举词；旧词只能出现在 legacy_titles/legacy_keywords（只读引用，不回改归档原文与历史卡面）。
2. 宽泛标题（如"任务完成""全收口"）的摘要必须写成计数式：
   > "X 项闭环/核销，Y 项原账关闭保留可选决策，Z 项待 owner 拍板，W 项长期观察"
   不得笼统写"全部完成"。计数硬约束：**括号内 ID 数必须与文字计数一致，同一 ID 不得重复计入两个桶**。
   本轮七项摘要示范（按 closure-map 实际 status）：**4 项闭环/核销（① closed、③ meta_cleared、⑤ closed、⑦ written_back），1 项待 owner 拍板（② owner_decision_pending），2 项长期观察（④、⑥ closed_observation）——合计七项，可复算算式 4+1+2=7；①-residual 为 ① 的子项，单列 optional_decision，不计入七项主项；③⑤ standing 残余单列。**
3. 相似匹配命中 closed 条目时只输出"疑似匹配，待人工确认"，不自动关闭、不静默。
4. 状态打包禁令：一个条目一个状态；残余单列 canonical_id。
5. 真值源顺序：decision-log 条目正文 ＞ 归档卷原文 ＞ closure-map ＞ MEMORY.md 索引行。map 只跟随不领先；MEMORY 索引行禁作盘点依据。

## §4 本轮七项状态词落位（对照任务规则映射）

| 项 | 任务规则规定 | 实际落位 | 偏差说明 |
|---|---|---|---|
| ① | closed＋optional_no_action＋保留 optional_decision 说明 | closed（主账）＋①-residual optional_decision | 按"一状态一条目"拆分，满足 |
| ② | owner_decision_pending＋ask_owner | 满足 | 附默认选项＋拍板问题＋不拍板后果 |
| ③ | meta_cleared＋cite_only | 满足 | 子项⑤ standing 残余单列 |
| ④ | closed_observation＋observe_due | 满足 | next_review＝触发＋兜底日期 |
| ⑤ | closed_observation＋observe_due | **closed＋cite_only，conflict=true** | 归档原文＝owner 裁决关闭（HRO-1 采纳，硬约束 1 优先）；未强行通过 |
| ⑥ | closed_observation＋observe_due | 满足 | next_review 2026-12-15 |
| ⑦ | written_back＋cite_only | 满足 | 证据 commit 18d3ea2 |

### §4.1 七项状态分布（按 closure-map 实际 status，可复算）

| 桶 | 项 | 计数 |
|---|---|---|
| 闭环/核销 | ① closed、③ meta_cleared、⑤ closed、⑦ written_back | 4 |
| 待 owner 拍板 | ② owner_decision_pending | 1 |
| 长期观察 | ④ closed_observation、⑥ closed_observation | 2 |
| 子项（不计入七项主项） | ①-residual optional_decision（① 的子项，单列） | — |

**可复算算式：4＋1＋2＝7。** ⑥ 只属"长期观察"桶，不得同时计入"闭环/核销"；⑤ 按归档原文落 closed（conflict=true，见上表），不属观察桶。
（注：原文件的计数句在 §3 使用规则第 2 条，已按本表口径改写；§4 表本身无计数错误。）
