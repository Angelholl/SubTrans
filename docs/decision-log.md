# 项目决策日志（decision-log）

> 由主模型维护，重大架构设计、技术选型、方案拍板经 decision-critic 评议后按 "## [日期] [决策ID/标题] [状态]" 格式追加归档，供续评与二次评议检索。

## 归档速查

- **权威声明（D2026-1020-01 C9）**：归档卷 [decision-log-archive-v1-v2.md](decision-log-archive-v1-v2.md)（A+B 组，104 条，D2026-0914-01 ~ 2026-10-08 末条）与 [decision-log-archive-c.md](decision-log-archive-c.md)（C 组，22 标题/21 条目＋1 追记，D2026-1009-01 ~ D2026-1019-03，2026-10-22 二阶段割续）与 [decision-log-archive-d.md](decision-log-archive-d.md)（D 组第三波，13 条，D2026-1020-01 ~ D2026-1022-03，2026-10-23 第三波割续，执行记录 D2026-1023-01）均属 decision-log 语料延续、**同等权威**；卷内条目为历史执行记录、含旧品牌词，正文逐字节未动，不作为现行表述依据；后续修订只在现行日志追记，卷不改写。现行区条目自 D2026-1023-01（2026-10-23）起。
- 检索口径：按决策 ID 全文检索定位；行号不作引用锚（D2026-1020-01 owner-②）。
- **现行约束速查**（结论＋原始 ID＋回链；D2026-1020-01 验收标准⑤自检面）：
  1. 品牌钉＝产品面 default-deny 全量钉死、`docs/design/**` 整体豁免、扩大豁免须先评议（原始 D2026-1004-02 品牌统一第 1 层＋现行区 D2026-1012-03 口径修订）。
  2. Mimosa git-gate 模式＝PreToolUse 快扫拦截与密封扫描双口径分列、不强行核平，插件版本变更即重评（原始 D2026-0921-03，归档卷）。
  3. guard 树外契约＝`internal_docs/`、`sexual_terms.csv`、`api_keys.bin` 等敏感件移仓库树外；tools/guard_banned_paths.py 名单⊆契约测试（原始 D2026-0916-01 收尾清单＋D2026-0925-02 D10 守卫落地，均归档卷）。
  4. 4 槽结构保留不动、压缩为 2 槽永久不做（原始 D2026-0922-02，归档卷）。
  5. v2_ctx 缺省＝16384（原始 D2026-0929-01，归档卷）。
  6. 生产模型搭配＝s1 lmstudio/qwen3.8-27b-uncensored-joyfox-aggressive＋s3 lmstudio/qwen3.6-35b-a3b-uncensored-heretic-apex（原始 D2026-1003-02 B2 四要素，归档卷）。
  7. 代码签名议题已关闭（D2026-1021-04，owner 2026-10-21 裁决）＝不再讨论，默认完整性口径＝SHA256 哈希比对（S码）；原 D2026-1011-01 触发条件与替代候选登记作废。
  8. 版本政策＝纯修复走四段号不递增、功能更新才递增版号（原始 D2026-1008-01，归档卷）。
- **契约锚（D2026-1020-01 C4）**：敏感路径守卫名单中源于决策日志的条目（`internal_docs/*`、`sexual_terms.csv`，出处＝D2026-0916-01 收尾清单，原文见归档卷）以本速查节为现行契约字面量载体（tests/test_guard_banned_paths.py 整文件子串断言源，二阶段 C 组归档后不灭源）。
- 归档执行核销表见 archive-d 卷 D2026-1020-01 条目「执行追记」（第三波割续迁卷）；第三波割续执行记录＝现行区 D2026-1023-01 条目。

## [2026-10-23] [D2026-1023-01] 「主日志第三波归档割续：10-20 后 13 条全量入 archive-d 卷＋C5 白名单同步＋closure-map 锚改指」 [已执行（Q4-GOV-01 执行代理·待主审验收，分支 chore/decision-log-archive-d）]

- **裁定与范围**：owner 2026-10-23 Q4-GOV-01 阶段 1 裁定（Q1-Q7）签发。本次＝第三波归档（承 D2026-1020-01 C7 时机分支），范围＝主日志 10-20 后全部条目现 13 条（D2026-1020-01/04/05/02/06/07、D2026-1021-01~04、D2026-1022-01~03），不以旧「11 条」计数为范围。
- **新卷**：`docs/decision-log-archive-d.md`（Q2 命名裁定），承 archive-c 同款模板：卷首只读声明＋条目逐字节不动＋行号不作引用锚。
- **割续对账**：边界锚＝块首 `## 2026-10-20 D2026-1020-01`（全文件唯一，原行 21）→原文件末行 217，块 197 行；块 sha256 割续前后相等＝`d9b4a1ebd7f0462b524bc4bf4243ac45fc43733e3a5035a619df835fc448ae0c`；`^## ` 计数断言：割前主日志 14（速查 1＋13 条）→割后主日志 2（速查 1＋本条）、archive-d 卷 13。
- **C5 白名单同步（D2026-1020-01 C5 前置登记兑现）**：主日志品牌词 4 处全在 13 条内，割续后主日志品牌词归零→`tests/test_brand_allowlist.py` ALLOWLIST 删 `docs/decision-log.md` 条目、增 `docs/decision-log-archive-d.md` 条目（Q4 裁定：仅数据条目，判定逻辑零改动）；新卷同批 git add 保持 tracked 防孤儿。
- **closure-map 锚改指**：evidence_refs/notes 内 `decision-log.md:行号` 20 处改指 `archive-d:行号`（映射＝原行号−16，块首 21→卷 5）；`decision-log.md:16`（速查节第 7 条）在割块外保留；条目状态零改动、entry_count 28 维持；从属声明与 meta.truth_source 增补 archive-d（Q6：impl-card-audit-runtime.md:120 陈旧锚留历史原样不追改）。
- **零改动清单（Q5/Q6 裁定）**：roadmap.md（现状已核一致）、audit-filter-rules.md、status-vocab.md、impl-card-audit-runtime.md、两既有归档卷、全部长期观察项（哈希漂移 evidence_gap／offlineAdvisory／adaptive thresholds／OBS-CI-FLAKE-20261022）。
- **验证**：ruff 全库 0；定向 pytest（test_brand_allowlist＋test_guard_banned_paths）全绿；全量 pytest 2521 passed＋4 skipped（基线 2520+4→2521+4 只增不减，§5 回归测试笔已入基线）；冒烟 refine --help/--where rc=0。
- **通道**：分支 chore/decision-log-archive-d，执行代理只 commit 不 push，留主审验收（Q7 裁定）。
