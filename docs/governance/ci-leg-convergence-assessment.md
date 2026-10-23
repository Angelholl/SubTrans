# CI 腿收敛 8→4 评估报告（Q4-CI-02，2026-10-23）

性质：**仅评估，不砍腿、不改 CI 拓扑**。试点与否 11/10 后另行拍板。既有登记：`docs/roadmap.md:204`（deferred 候选未拍板，源 D2026-1004-04 ⑥，原文 `docs/decision-log-archive-v1-v2.md:2924`）。

## 1. 现行拓扑（`.github/workflows/` 直读）

- **ci.yml**：单 job `test`，矩阵 `os: [ubuntu-latest, windows-latest]` × `python-version: [3.10, 3.11, 3.12, 3.13]`＝8 腿（ci.yml:13-15），`fail-fast: false`（:12）。步骤链（全腿）：checkout → line-endings 钉（:18-20）→ setup-python → install `.[dev,zh]`＋`mypy==2.3.1`（:26-27）→ ruff（:28-29）→ **mypy 基线门禁＝步骤级 `if: matrix.os == 'ubuntu-latest' && matrix.python-version == '3.12'`（:31-33）** → pytest＋cov（:34-36）。
- **gui-probe.yml**：独立 workflow（id 381790716），windows-latest＋3.12，schedule `17 3 1 * *`（UTC＝北京 11:17）＋workflow_dispatch；明确不进 required checks。
- **release.yml**：独立 workflow（id 381790718），tag/dispatch 触发，构建＋冒烟＋资产。
- 三个 workflow 互不引用（无 `needs`/`workflow_call`），各为单文件。

## 2. required checks 实证（REST 只读查询）

查询对象：repo **Angelholl/SubTrans**，分支 **main**（default_branch 实证＝main）。

| 查询 | 时点 | 方式 | 结果 |
|---|---|---|---|
| `branches/main`（public） | 2026-10-23T02:33:49Z | 无凭证 | `protected=false`（commit 52aeb5f） |
| `branches/main/protection` | 2026-10-23 本会话（北京 09:5x，分钟级估算，非精确时间戳；凭证＝git credential fill token，只读 GET） | 带凭证 | 404 `Branch not protected` |
| `rulesets` | 同上 | 带凭证 | 空数组 |
| `actions/workflows` | 2026-10-23T02:33:49Z | 无凭证 | CI/gui-probe/release 三件均 active |
| gui-probe `runs?event=schedule` | 2026-10-23T02:33:49Z | 无凭证 | `total_count=0`（定时至今零跳，11/01 为错峰后首跳） |

**结论：main 无任何 required status checks / ruleset，8 腿全部非阻断（advisory）。精确时间以无凭证轮（2026-10-23T02:33:49Z）为准，带凭证轮仅作交叉验证。**
**时点声明：以上基于查询时点配置；若后续启用 required checks，本报告结论需重评。**

## 3. 8→4 收敛候选与影响面

- **推荐候选＝砍版本维度两端**：去 3.10/3.13，保 ubuntu/windows × 3.11/3.12＝4 腿。版本腿无独有步骤，纯兼容性覆盖；runner 配额约省半。
- **不推荐砍 OS 维度（windows 腿）**：cp1252/码页真实行为仅 windows 腿暴露（历史实证 `docs/decision-log-archive-v1-v2.md:1240`）；flake 家族 6 例全在 windows 腿（`docs/decision-log-archive-c.md:234,376` 等）。砍 windows＝丢平台守护＋削 flake 观察面。
- **mypy 门禁可迁移（关键联动）**：门禁是挂在 ubuntu-3.12 组合上的步骤级 if（ci.yml:32），**不是该腿固有属性**——若砍 ubuntu-3.12 组合而不同步改 if 行，门禁静默消失；把 if 迁到保留组合（如 ubuntu-3.11）即可保门禁。试点单 commit 必须同时改 :14-15 矩阵行＋:32 条件行。
- 重复面：line-endings/ruff/pytest 全腿重复，砍腿不丢独有覆盖（除上述联动项）。

## 4. 风险与观察窗冲突

1. **版本兼容盲区**：3.10（存量用户环境）与 3.13（新版本回归）不再被测。
2. **flake 观察样本面减半**：OBS-CI-FLAKE-20261022 及 flake 家族台账依赖 8 腿×多轮的偶发样本；观察窗存续期内砍腿＝污染样本面。跨秒 flake 已于本任务加固（tests/test_quality_report.py monkeypatch 冻结），但其余 flake 家族观察项未加固。
3. **检索类观察窗（11/03-11/10）**：样本来自真实派卡（hooks-log），与 CI 腿数无耦合——不冲突，但两窗叠加期改 CI 拓扑会增加归因噪音。
4. **advisory 属性**：required checks=无 → 砍腿不会破坏任何阻断闸，但 CI 红本就不拦 push，收敛的代价只体现在检测面，不体现在门禁面。

## 5. 回滚方式

单文件 revert ci.yml 即全量回滚（矩阵＝:14-15 两行，mypy 条件＝:32 一行）；试点应做成单 commit，revert 即净。三 workflow 无相互引用，无连带回滚面。

## 6. 建议

- **11/10 前不动 CI 拓扑**（flake 加固观察＋检索观察窗均存续）。
- 11/10 后如拍板试点：形态＝单 commit（矩阵 3.11/3.12＋mypy if 迁 ubuntu-3.11），观察 ≥2 周（覆盖 flake 观察面与版本回归信号），异常即 revert。
- 试点前重核 required checks 时点状态（§2 时点声明）。
- 立项走 decision-log（先例：改触发面须先裁卡，`docs/decision-log-archive-c.md:517`）。

## 7. 未实施声明

本任务未改任何 workflow 文件、未砍腿、未改触发面、未动 GitHub 设置；本报告仅落盘本文件。
