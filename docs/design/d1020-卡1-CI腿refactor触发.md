# d1020-卡1：CI push 触发面增 refactor/**（CI 腿 A 方案落地）

- 派发/执行：ZCode 主审裁卡＋兜底亲执（派卡链路不可用环境态，先例 d1018-卡3/d1019-卡1，L-20261020-01）
- 依据：D2026-1019-03 事项① owner 2026-10-20 复核裁决**拍板选 A**（workflow_dispatch 或 refactor/** 触发＋paths 过滤可选；合并 main 前手动全量双保险）
- 批次：3.1 阶段3 app.js 拆分收尾前置门禁第一卡（合并列车首格）

## 一、根因

`.github/workflows/ci.yml` push 触发面仅 `[main, master]`，`refactor/*` 分支推送零 CI 腿——批1-4 全程仅主审本地验证链（D2026-1019-03 事项① 登记：批1-3 同样无腿，不得作为不修理由）。

## 二、改动文件（仅 1 个）

| 文件 | 改动 |
|---|---|
| .github/workflows/ci.yml | `on.push.branches: [main, master]` → `[main, master, 'refactor/**']`；其余零字节改动 |

## 三、改法与裁量

- 触发面纯增量，job 逻辑零改动。
- **不加 paths 过滤**：过滤漏跑＝无腿等价，与本门禁目的相悖；refactor 分支推送节奏由主审批级把关（每次推送均为整批验收后），频率天然受控。owner 若坚持过滤可后补评议。
- **不加 workflow_dispatch**：打包类 dispatch 入口已由 release.yml（version 输入）承担；ci.yml 保持最小增量。
- pull_request 面不动（项目走直推分支制，无 PR 流）。

## 四、先红后绿回归

- 红：触发面无 refactor（事实在案：批1-4 推送零 run，D2026-1019-03 事项①）。
- 绿：本笔推送 refactor/appjs-split 后，GitHub 出现以该分支为 ref 的 CI run 且全腿绿——触发面生效＋拆分全程首次获得 CI 背书（兼作合并前双保险数据）。

## 五、验收命令

以下命令均在项目根目录执行。

```
python -c "import yaml; d=yaml.safe_load(open('.github/workflows/ci.yml',encoding='utf-8')); print(d[True if True else 'on'])"   # YAML 可解析（注意 PyYAML 把裸 on 读成 True 键），branches 含 refactor/**
git diff --stat                     # 仅 ci.yml
grep -c $'\r' .github/workflows/ci.yml || echo ok   # 零 CRLF（CI 首腿有 CRLF 守卫）
push 后 gh run list --branch refactor/appjs-split   # 出现 CI run
```

## 六、约束

1. 不动 main/master 触发面、pull_request 面、任何 job 步骤。
2. 逐文件点名 add；禁 `git add -A`（工作树另有并发会话在途文件 docs/decision-log.md 的 D2026-1020-01 条目，**不得触碰不得混入**）。
3. 卡面无真实仓库根路径字面量；不引入品牌全称字样。
4. 遇 YAML 解析失败或 diff 超范围即停。
5. push 由主审执行（本卡主审亲执，commit 后按提交五步走）。

## 七、执行记录

- **执行**（2026-10-20 凌晨，主审兜底亲执）：ci.yml L4 `branches: [main, master]` → `[main, master, 'refactor/**']`，单行替换，job 逻辑零改动。
- **验证**：`yaml.safe_load` 过、push.branches=['main','master','refactor/**']；`grep -c $'\r'` = 0（CI 首腿 CRLF 守卫不触）；`git diff --stat` 仅 ci.yml 1 行；secret 扫描新增行 0 命中。
- **提交**：`a131bda`（ci.yml，逐文件点名）；本卡 docs 随后单独提交。工作树中并发会话在途件 docs/decision-log.md（D2026-1020-01 归档方案条目，+20 行）未触碰未混入。
- **绿相待验证**：推送后 refactor/appjs-split 应出现 CI run（8 腿矩阵＋lint＋mypy 门）——触发面生效即本卡绿相，run 结果兼作批1-4 首次 CI 背书与合并前双保险数据；结果回填本节。
- **绿相回填（2026-10-20，主审合并列车批）**：首个 refactor CI run=**39292183541 success**（head 86b92c3，2026-10-19T17:12Z，8 腿矩阵＋lint＋mypy 门）＝触发面生效实证、CI-A 闭环；合并列车随批两 run 同绿——第一段合并提交 33cf856＝run 39298268375 success、main 第二段 ce2ed7b＝run 39299151483 success（拆分内容首次进 main CI）。本卡绿相闭环，勾账详见 decision-log **D2026-1020-02**。
