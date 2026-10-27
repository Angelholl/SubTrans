# SubTransJAV 项目规则

适用于在本仓库工作的所有 AI 执行者（ZCode / OpenCode 或其他）。

## 权威顺序

- 与 `docs/decision-log.md` 冲突时，一律以 decision-log 为准；不得自行推翻已拍板的决策。
- 任务卡（如 `docs/design/*-批清单.md` 及其派生单件卡）是执行单元：只改卡片点名的文件，超出卡片范围的改动先停下来说明，不得顺手扩展。

## 提交约定

- Conventional Commits 前缀 + 中文描述（feat / fix / docs / test / refactor / chore…）。
- 正文含 `verify:` 验证结果（测试基线数 / lint / 冒烟）；有决策依据时含 `Refs: D20xx-xxxx` 决策 ID 回链。
- 执行者只 commit，不 push；push 由主审方验收后执行。
- 禁止 `git add -A`，逐文件点名 add，按语义分段提交。

## 验证

- Python 部分：改动后跑 ruff check 与定向 pytest；失败即停，如实写进执行记录，不得掩饰或绕过。
- 执行完毕在任务卡末尾追加执行记录：改了哪些文件 / 自测结果 / 遗留问题。

## 任务卡裁卡约定（品牌钉防复发，D2026-1012-03）

- **卡面禁根路径字面量**：验收命令区不写真实仓库根路径（如 `cd /d D:\…`），统一改为首行注明「以下命令均在项目根目录执行」+ 相对命令（执行者本就以仓库根为 cwd）。触发源：docs/design 卡面曾因该行入库即触发品牌钉（三批复发）。
- 品牌钉口径：`docs/design/**` 已整体豁免出 `tests/test_brand_allowlist.py` 判定面（guard 断言锁死，扩大豁免须先评议）；产品面（源码/UI 资产/打包/发布资产/根级文档）仍 default-deny 全量钉死，新增文件含旧品牌词即红。


## 公开仓 push 面收窄（D2026-1028-01，owner 三令）

- **只推版本迭代内容**：源码、tests、packaging、.github、README/CHANGELOG/手册/roadmap、产品向工具脚本。
- **禁推清单（只 commit 留本地，严禁出现在公开仓）**：`artifacts/`、`spike/`、`docs/design/**`、`docs/archive/**`、`docs/governance/**`、`docs/decision-log*.md`、讨论/评议/测试/标注/判定材料及其工具（tools/ruling_b6*、tools/sensitive_b6_web、tools/model_matrix_run 等）、语料/媒体/标注数据、凭据类文件。以上均已入 `.gitignore`；今后新位置的同性质文件同样不得 add（先补 .gitignore 再落盘）。
- 语料码/片名/内部裁决细节不得进 commit message 与产品文档；产品文档引用内部记录一律写「存内部记录」不写路径。
- commit message 的产品化摘要可提测试结论数字，不引用片名与内部判定过程。

## 设计任务派发约定（design-expert 长时中断根治，D2026-1012-01）

- **分件派发**：设计产出物逐件为独立交付单元，单次派发 ≤2 件；每件完成立即写盘到目标路径，不得积攒在会话内等最终报告。
- **判定与产出分离**：逐项表态类请求不与大体量产出混入同一派发（混入则判定必随超时丢失）。
- **超时兜底**：单次设计派发约 30 分钟未回即按超时处置——按 D2026-1010-01 先例由主审直出规格兜底；已写盘文件即为有效交付，会话报告丢失不返工不重派。
- **保底序声明**：派发时显式声明产出优先序（超时保哪几件），未完成件按优先序由后续小批派发或主审兜底补齐。
