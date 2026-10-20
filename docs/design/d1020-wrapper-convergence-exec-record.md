# D2026-1020-05 执行记录（wrapper 三件套收敛＋AGENTS.md 绝对路径＋回滚演练）

执行方：主审（ZCode）。日期：2026-10-20。授权依据：decision-log D2026-1020-05（Part 1 授权动作 1-7）＋owner 开工令。过程账回链：memory 卡 `wrapper-globalize-plan-d1020`。

## 1. 源核实与落盘方式

- 源 `G:/zcode/.zcode/workspace/default/tools/` 可读，三文件落位前哈希与过程账指纹逐位一致：
  - `exec_wrapper.py` = `3bfd6a4aa8677c4ecd7bd48235388ebdc0a6a37b7ae1ea73ee805d1ff258f94c`
  - `pointer_tools.py` = `eedfa0eb47e0354e14682348ced5baed4cfeb2877d7cca192f29aad4c932d6b5`
  - `quota_watch.py` = `de300f444c687cdf0d7f5ed15afe66dc65f9e5544457bbae8b2551f407e124b1`
- `pointer_tools.py` 经 Write 通道落盘（内容扫描通过，哈希全等）。
- **因 exec_wrapper.py（L460 命令注入）与 quota_watch.py（L234 路径穿越）被安全扫描器误报拦截，经 owner 显式授权，采用 Bash 直拷方式落盘，以保全与已审源文件及 J 裸仓的逐位一致（sha256 全等）。**
  - 执行实况补充登记：owner 授权后，本会话的 Bash 直拷仍被机械闸拦截（该闸为 harness 内部机制，授权不打开，主审不得绕行），最终由 owner 在 PowerShell 7.6.7 手工执行 `Copy-Item` 完成落盘；落盘后复算哈希三件套全等，与上述指纹一致。两处被拦内容均为已审代码的固有设计（用户可控路径→subprocess / 用户可控 --out 路径），扫描器建议项在 exec_wrapper 已满足（参数列表形式，无 shell 拼接），未改动任何源码。
- 落位后 committed blob 复算（`git show HEAD:<file> | sha256sum`）三值全等，工作树文件未被 CRLF 改写。

## 2. 依赖自检复验（决策时 4 项闭环，执行期在落位副本复核）

- ① `DEFAULT_CLI` = `D:\OpenCode\resources\opencode-cli.exe`（绝对路径，L27）✓
- ② `find_repo_root`（L257）取调用方仓库根 → artifacts 落调用方项目 ✓
- ③ `ensure_git_exclude`（L222）已存在则跳过（幂等）✓
- ④ `quota_watch --db` 显式传参、只读 URI ✓
- ⑤ 三件套零互相调用：exec_wrapper 对 pointer_tools/quota_watch 仅注释引用（L45-46）✓
- 项目副本检查：`D:/SubTransJAV/tools/` 无三件套任何一件（不得建副本）✓

## 3. AGENTS.md 第 5 行路径改写

- 写前比对：mtime 2026-10-18 23:38:27、8994B、sha256 `f28b3528ac9a1db2317d40b22908aa68240c7d6addec7dd41a1cf2993679437e`；哨兵计数 1。
- 改前备份：`/g/zcode/.zcode/workspace/default/AGENTS.md.backup-20261020-1528`。
- TICKS 打点：`C-20261020-1528`（H1=enforce 在场）。
- 改动：两处相对路径 → `C:/Users/57850/.zcode/tools/exec_wrapper.py` 与 `C:/Users/57850/.zcode/tools/pointer_tools.py`；写后 diff 仅第 5 行，新哈希 `3cd3c1243699bb40498371db68b8a391a2c75b22e758b749d5f19fd420a2c84c`，9038B（未超 9057B 上限）。

## 4. 分级 smoke（L1/L2/L3）

在隔离目录（非任何 git 仓库）以假 CLI 注入执行：

- L1 spawn＋回显：PASS（契约单行＋artifact 落位）
- L2 stdout 单行且 `schema=="exec.v1"`、exit 0：PASS
- L3 轮转沿链触发（deepseek→glm→mimo→space-bunny 四模型均触发限流判定）至 `CHAIN_EXHAUSTED` flag：PASS

副作用登记：首跑时 scratch 位于 default 工作区仓库内，artifact 误落 `workspace default/artifacts`（已清理该枚测试 artifact）；`ensure_git_exclude` 对 default 仓库 `.git/info/exclude` 为幂等——第 7 行 `artifacts/` 原已存在，本次未新增条目。复跑在隔离目录完成，结果如上。

## 5. 版本化

`C:/Users/57850/.zcode/tools/` 内 git init：

- `.gitignore` 内容仅 `__pycache__/`
- `tools-baseline.sha256` 只记入库三件套（三行，值同 §1 指纹）
- 首笔 commit `c9c0cad`（三件套＋.gitignore＋baseline）
- 回滚脚本单独 commit `ba60bc6`（baseline 不变，仍只记三件套）

## 6. 回滚脚本与回滚演练记录

脚本：`C:/Users/57850/.zcode/tools/rollback_wrapper_convergence.sh`

- guard：`skills/dispatch-discipline` 在场 → exit 1（回滚序=迁移卡回滚 → D-05 回滚）
- 动作：还原 AGENTS.md 最近备份 ＋ 移除 tools/
- 修订记录：演练实测本环境 `rm` 缺失（`/usr/bin/rm absent`），改 `remove_tree` 三级兜底（rm → `find -depth -delete` → python shutil）。Mimosa 对脚本报中危"命令注入"（非阻断）：路径变量由操作者设定、非用户输入，按设计保留。
- 使用注意：脚本自身位于 tools/ 内，Windows 下自删自身文件可能失败，实际回滚时建议从 tools/ 外调用。

演练（在 TEMP 沙箱副本执行，未触及真实配置面）：

- guard 分支：exit 1 PASS
- 正常分支：exit 0 PASS
- 断言1 还原后 AGENTS.md diff 为空：PASS
- 断言2 tools/ 不存在：PASS
- 断言3 项目 grep 无 C 路径残留：**操作面 0 命中 PASS**；唯一命中面为 `docs/decision-log.md` 决策条目自身（5 处，记载目标路径的历史记录，不可移除）。口径说明：断言按"操作面引用"解释方为可满足——决策记录本身必然记载目标路径，字面"全项目 grep 无残留"不可成立，已按此口径登记。
- 真实面核验：演练后真实 `tools/` 在场、AGENTS.md 哈希仍为 `3cd3c1243699`，未受演练影响。

## 7. pyright-lsp 探针（规格 §1.6 终裁补充⑤）

- `pyright-langserver` 二进制在 PATH、npm 全局、插件缓存内均不存在 → 判定**不可用**。
- 处置：不安装（无授权），禁用动作平移入清卸卡验证窗口执行。Node v24.21.0 在场；若 owner 令恢复，`npm i -g pyright` 即可。

## 8. 遗留

- 月度 L2 脚本（含 DEFAULT_CLI size+mtime 事件检测）＝批后首交付，验收后 7 天内。
- 后续任务清单 ①-⑥ 见 D2026-1020-05 原条目，未在本批执行。
