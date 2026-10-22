# audit-filter-rules.md — 扫描/审计前置过滤规则（账本收口治理轮，2026-10-22）

从属声明：本规则消费 closure-map.yaml，不裁决。冲突时以 decision-log 条目正文终态＋证据为准；映射表只作检索过滤层。MEMORY.md 索引行非状态真值源，不得作盘点依据（C22 误列根因，L-20261022-01）。

## §0 前置约束

1. **本轮交付定性：规则层验收通过；运行时层未交付。** 本规则是文档层口径，本轮无脚本实现（audit_dispatch_compliance.py 未改、输出目录不存在）。实现卡单列待办（docs/governance/impl-card-audit-runtime.md；条目见 provisional 区 GOV-P-2026-1022-03）。在此之前，任何人工盘点按本规则口径执行，但一律表述为"规则层生效，运行时待实现卡"——不得写"已止住循环""运行时生效"。
2. 品牌钉：治理文件不得含旧品牌词字面量（case-sensitive，tests/test_brand_allowlist.py:129）；legacy_keywords 小写存储、匹配大小写不敏感。若必须引字面量，走 ALLOWLIST 加条目（先例 450a628），不扩大豁免面。
3. 一状态一条目：条目内不得打包两个状态；残余单列 canonical_id（① 残余、③⑤ standing、1021-01 追记③ 均已单列）。
4. next_review 必须是具体日期或显式触发条件，禁止留空；两者皆无→该条目自身判 evidence_gap 强制浮出（防"未到期不出账＋缺日期＝永久静默"）。
5. **敏感关键词从本地安全源动态加载，治理文件不存原值。** 本仓库为公开仓库（2026-10-22 GitHub API 核实 private=false），docs/governance/ 一旦提交推送即公开；① 类要清的目标正是用户名命中，治理文件若保留原值＝在公开仓库留下可检索副本，与清史方向相反。故用户名类／绝对路径类关键词在本表以 `hash:<sha256 前 8 位>（类别，本地源加载）` 表示（规范化＝小写＋正斜杠），运行时对命中文本做同样规范化后比对哈希前缀；本地安全源路径由实现卡定义（建议置于本地工具目录，不入仓库）。品牌钉只管旧品牌词字面量，不管用户名和绝对路径——脱敏是治理文件自身的卫生要求，与品牌钉无关。威胁模型边界：哈希前缀仅用于防止明文误 grep 与意外扩散，不抗字典反查；威胁模型不含主动攻击者。

## §1 过滤流程（硬序）

1. **读取 closure-map**（docs/governance/closure-map.yaml，两个区：`entries` 正式／`provisional` 临时）。
2. **规范化命中**：ID（D20xx-xxxx-xx 及子项号）、标题关键词、路径、commit hash、seal、分支名、cron 行；大小写不敏感；旧品牌词按小写形态匹配。
3. **匹配映射**，优先级：
   - a) canonical_id 精确匹配；
   - b) 精确关键词/路径/commit/seal/分支名匹配；
   - c) 标题相似匹配——**只提示不自动关闭**：一律输出"疑似匹配（含指向 closed 条目），待人工确认"，绝不静默（静默放行＝scanner_enobufs 教训）。此类入"待确认"桶单列计数，使抑制率可审计。
4. **按 status/default_action 处置**：
   - **provisional 区条目只输出"临时条目，待归档，见 {canonical_id}"，不参与 disposition 处置、不计入统计字段**（其命中只体现在 raw_hits 总量，由 §4 基线单列"临时 3"）。去重仍适用于 provisional（每轮每 ID 一次，见 §2 `per_round_dedup`），但去重跳过的行不进任何统计字段——§3 中 `seen.add` 位于分区判定之前。
   - closed / written_back / meta_cleared → 只输出一行"已收口，见 {canonical_id}；证据 {evidence_refs}"，不生成待办、不重新解释历史。
   - **closed 且 default_action=optional_no_action（① 先例，优先于上一条）** → 输出"已收口，见 {canonical_id}；残余可选决策见 {canonical_id}-residual，默认不动"。残余指针只指向、不重复展开；若残余条目本身同轮命中，以残余条目（status=optional_decision）的输出为准。
   - optional_decision → 只输出"原账已关闭，可选决策默认不动；除非 owner 明确覆盖红线"，不生成执行动作。
   - owner_decision_pending → 每轮只出现一次，输出拍板问题、默认选项、不拍板的后果。
   - closed_observation → 仅当 next_review 到期（日期已过或触发条件已满足）才出账；未到期不出账；不得写成"在途欠账"。
   - open → 正常出账。
   - evidence_gap → 输出补证清单，不输出执行清单。
   - 未命中映射 → 显式输出"未分类（未在映射中）"，不静默归 open 也不静默归 closed。
5. **输出审计统计**（字段固定；"可复核"须待运行时层实现卡交付＋落盘后方可称，本轮只冻结字段）：原始命中数、去重后命中数、closed 引用数、pending 数、观察到期数、open 数、冲突数、证据缺口数、待确认（相似匹配）数、未分类数——以上字段只计正式区条目。

禁止行为：同一 canonical_id 同一轮重复展开；对 closed 命中重新解释历史；把"观察"写成"在途欠账"；把"待拍板"混入"已完成"；相似匹配静默关闭。

## §2 可加载配置片段（YAML）

```yaml
filter:
  map_path: docs/governance/closure-map.yaml
  zones: [entries, provisional]            # entries＝正式（计入统计）；provisional＝临时（不计入）
  normalize: [canonical_id, title_keyword, path, commit, seal, branch, cron]
  case_insensitive: true
  sensitive_keyword_source: local_secure_source    # §0 第 5 条：原值不入治理文件，运行时动态加载
  sensitive_match: sha256_prefix8_over_normalized   # 规范化＝小写＋正斜杠
  match_priority: [canonical_id, exact_keyword, title_similarity]
  similarity_action: prompt_only          # 不自动关闭，入待确认桶
  unmapped_action: report_unclosed_classified   # 显式"未分类"
  per_round_dedup: canonical_id            # 同 ID 每轮最多一次（含 provisional）
  provisional_action: placeholder_line_only   # 只输出"临时条目，待归档，见 {canonical_id}"；不入 disposition、不计入 statistics_fields
  disposition:
    closed_and_optional_no_action: cite_only_line_plus_residual_pointer   # status=closed 且 default_action=optional_no_action（① 先例），优先于 closed
    closed: cite_only_line
    written_back: cite_only_line
    meta_cleared: cite_only_line
    optional_decision: default_no_action_line
    owner_decision_pending: once_per_round_with_default_option
    closed_observation: bill_only_if_due
    open: bill
    evidence_gap: supplement_list_only
  next_review_guard: date_or_explicit_trigger_required   # 皆无→evidence_gap
  statistics_fields: [raw_hits, dedup_hits, closed_cited, pending, observation_due, open, conflicts, evidence_gaps, similarity_pending, unclassified]
  statistics_scope: entries_only           # provisional 不进入以上任一字段
```

## §3 加载伪代码

```python
def audit_round(hits, map_entries, today):
    stats = Counter()
    seen = set()
    for h in hits:
        stats["raw_hits"] += 1
        n = normalize(h)                      # ID/关键词/路径/commit/seal/分支（大小写不敏感）
        e = match(n, map_entries)             # canonical_id > 精确 > 相似；e.zone ∈ {entries, provisional}
        if e is None:
            stats["unclassified"] += 1
            emit(f"未分类（未在映射中）：{h}")
            continue
        if e.canonical_id in seen:
            continue                          # 每轮每 ID 只展开一次（含 provisional）
        seen.add(e.canonical_id)              # 去重先于分区判定：provisional 同样受每轮一次约束（选 (a)）
        if e.zone == "provisional":
            # 临时条目：只出占位行，不参与 disposition、不计入任何统计字段（相似命中同样只出此行）
            emit(f"临时条目，待归档，见 {e.canonical_id}")
            continue
        if e.match_type == "similarity":
            stats["similarity_pending"] += 1
            emit(f"疑似匹配 {e.canonical_id}（status={e.status}），待人工确认，不自动关闭")
            continue
        stats["dedup_hits"] += 1
        if e.status in ("closed", "written_back", "meta_cleared"):
            stats["closed_cited"] += 1
            if e.status == "closed" and e.default_action == "optional_no_action":
                emit(f"已收口，见 {e.canonical_id}；残余可选决策见 {e.canonical_id}-residual，默认不动")
            else:
                emit(f"已收口，见 {e.canonical_id}；证据 {e.evidence_refs}")
        elif e.status == "optional_decision":
            emit(f"原账已关闭（{e.canonical_id}），可选决策默认不动；除非 owner 明确覆盖红线")
        elif e.status == "owner_decision_pending":
            stats["pending"] += 1
            # RULED＝运行时侧临时登记表，不是第二真值源，只作提示；每条须带 decision-log 锚点＋拍板日期，
            # decision-log 归档后退役或改判。已拍板条目只提示不重问。
            if e.canonical_id in RULED:
                emit(f"{e.canonical_id}｜已拍板，待落 decision-log（锚点 {RULED[e.canonical_id]['anchor']}，拍板 {RULED[e.canonical_id]['date']}）｜不再重问")
            else:
                emit(f"待拍板（每轮一次）：{e.ruling_question}｜默认：{e.default_option}｜不拍板后果：{e.consequence}")
        elif e.status == "closed_observation":
            if due(e.next_review, today):
                stats["observation_due"] += 1
                emit(f"观察到期出账：{e.canonical_id}（{e.next_review}）")
            # 未到期：不出账
        elif e.status == "open":
            stats["open"] += 1
            emit(f"出账：{e.canonical_id}")
        elif e.status == "evidence_gap":
            stats["evidence_gaps"] += 1
            emit(f"补证清单（无执行动作）：{e.canonical_id}")
        if e.conflict:
            stats["conflicts"] += 1
            emit(f"冲突登记（不自动裁决）：{e.canonical_id}｜{e.notes}")
    emit(stats)
```

## §4 本轮统计基线（人工登记，运行时层未交付，脚本实现前不称"可复核"）

- 映射表条目数：**正式 24／临时 3**（正式＝去重后唯一 canonical_id 24；临时 3 条只出占位行，不参与统计）
- 正式区按 status 分布（合计 24）：closed 11 / closed_observation 6 / owner_decision_pending 1 / optional_decision 1 / meta_cleared 1 / written_back 3 / evidence_gap 1 / open 0
- 临时区按 status 分布（合计 3，不计入统计字段）：owner_decision_pending 1（GOV-P-2026-1022-01）/ optional_decision 1（GOV-P-2026-1022-02）/ evidence_gap 1（GOV-P-2026-1022-03）
- 冲突登记（正式区）：2（⑤ 任务规则映射 vs 归档原文；②-conflict docstring vs decision-log:141）
- evidence_gap（正式区）：1（②-conflict）／临时区：1（GOV-P-2026-1022-03）
- owner_decision_pending（正式区）：1（②）／临时区：1（GOV-P-2026-1022-01）
- closed_observation 6 条（全在正式区）中：触发型 4（③⑤-standing、④、1021-01-追记③、S7），日期型 2（⑥ 2026-12-15、gui-probe 2026-11-01）
- 七项主项分布（可复算，对应 status-vocab §4.1）：闭环/核销 4（①③⑤⑦）＋待 owner 拍板 1（②）＋长期观察 2（④⑥）＝7；①-residual 为 ① 子项单列，不计入七项主项
- 统计数字可复核：未满足（运行时层未交付，仅冻结口径与字段；待实现卡 docs/governance/impl-card-audit-runtime.md）
- **双口径声明（不可互推）**：运行时口径＝输入行（每行最多一次判定），静态口径＝条目数；二者量纲不同，不得互相反推。运行时对账式 `raw_hits = dedup_hits + unclassified + dedup_skipped` 只在运行时口径下成立；§4 的条目分布不是运行时统计的结果，也不能由某轮实跑反推。
