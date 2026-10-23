# 派卡基础设施跨域纳管边界 memo（Q4-CI-02，2026-10-23）

性质：边界评估备忘录，**非纳管执行**。本文件不入 closure-map（entry_count 28 维持不动），不改任何治理表状态，不实施纳管、不清理任何仓库外文件。是否纳管由 owner 拍板。

## 1. 边界事实（现状）

- **账本体在仓库外**：派卡 wrapper 三件套真身＝`%USERPROFILE%\.zcode\tools`（D2026-1020-05 收敛成果，落笔 `docs/decision-log-archive-d.md:62`）：
  - 三件套本体：`exec_wrapper.py`（19,643B）/ `pointer_tools.py`（9,880B）/ `quota_watch.py`（7,550B）；
  - 同目录治理扩展件：`audit_dispatch_compliance.py` / `monthly_l2_check.py` / `governance-secret-keywords.json` / `tools-baseline.sha256` / `cli-baseline.json` / `rollback_wrapper_convergence.sh`；
  - 该目录已独立 `git init` 版本化＋`tools-baseline.sha256` 钉（D2026-1020-05），即账本体自带一套仓外版本化地基。
- **状态＝暂停非退役**（关键措辞，落笔 `docs/decision-log-archive-d.md:47,51`，D2026-1020-04；状态词表 `docs/governance/status-vocab.md:8,26`＝closed_observation）。本 memo 不得也不将其改写为退役。
- **激活条件①-④＋X=8 周稳定窗**（唯一成文处 `docs/decision-log-archive-d.md:74-75,187`，D2026-1020-05）：①ZCode 内生通道连续 K=2 次任务失败；②需要 exec.v1 机器契约；③主模型判定测试期模型质量不达标；④需要多模型轮转/限流兜底；另有连续 M=3 次同一能力缺口→触发能力补进主通道评估、降级出口 X=8 周、重置上限 2 次。激活条件①已有实际触发先例（`docs/decision-log-archive-d.md:139`）——仅为历史先例，不改变当前暂停非退役状态。
- **仓库内引用面**：全局 AGENTS.md wrapper 命令形态（绝对路径）、dispatch-discipline skill（真值源）、docs/design 历史卡面验收命令（旧 G: 相对路径用法已冻结不回改，`docs/decision-log-archive-d.md:184` ④）。wrapper 缺失断链先例三发：`docs/design/d1018-卡3-全站dz-icon连根拔.md:68,89`、`docs/design/d1019-卡1-spike-ruff微chore.md:70`、`docs/decision-log-archive-c.md:514`。

## 2. 三选项

| 选项 | 定义 | 利 | 弊 |
|---|---|---|---|
| a. 不纳管，仅登记外部依赖 | 仓库内只在治理面留一行「外部依赖：~/.zcode/tools 三件套」指针，无契约无窗口 | 零治理成本；仓库治理面不越域 | 引用断链先例三发无对策复现；工具换代/丢失无感知面 |
| b. 外部依赖登记＋接口契约/责任人/稳定窗 | 在 a 基础上登记：接口契约＝exec.v1 stdout 单行契约、责任人＝owner、稳定窗＝X=8 周口径联动；工具侧仍由 tools 自带 git＋baseline 钉自治 | 与 D2026-1020-04/05 既有结构完全对齐；治理增量最小；断链有契约可核对 | 需要维护一处登记行与 tools-baseline 的对应关系 |
| c. 纳入治理表作为受控资产 | 三件套入 closure-map/治理表，随本仓库验证链与门禁走 | 最强可见性 | 账本体是跨 workspace 共享的 harness 侧资产（hooks-log 全局发现、wrapper 服务多项目），入本仓库治理表＝治理范围越域；且与 tools 自带版本化地基双轨冲突 |

## 3. 边界建议（供拍板，不实施）

**建议选项 b。** 理由：账本体物理上不属于本仓库管辖域（跨 workspace 共享），c 的强纳管会制造双轨版本化冲突；a 已被三发断链先例证伪其充分性；b 只登记契约（exec.v1）、责任人（owner）、稳定窗（X=8 周），与现行「暂停非退役＋激活条件」决策结构同构，是治理增量最小的方案。

## 4. 边界事实/待办风险登记（不清理、不处置）

- **双副本残留**：旧位 `<workspace>\.zcode\workspace\default\tools` 仍存三件套副本（2026-10-18 时间戳，D2026-1020-05 收敛后未删）。风险＝与 autoglm 双副本误判同型的「改错副本/读到旧版」混淆；列为待办风险，是否清理由 owner 另行拍板。
- **仓外工具链观察项**（只登记）：`audit_dispatch_compliance.py` 遇 hooks-log 坏行直接崩溃（无 errors="replace" 兜底）；hooks-log 存在疑似写竞态坏行（见 Q4-CI-02 阶段 1 执行报告只读预检记录）。依 Q4-CI-02 E 项约束本任务不修该脚本。

## 5. 未实施声明

本 memo 仅落盘本文件；未迁移账本体、未改 `~/.zcode/tools` 下任何内容、未改权限、未改 closure-map 与任何治理表状态、未清理双副本。纳管与否待 owner 依三选项拍板。
