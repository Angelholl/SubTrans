# d1019-卡1：spike/ 8 处 ruff 存量微 chore（UP009/F401/SIM300）

- 派发：ZCode 主审（2026-10-19）；执行：主审兜底亲执（派卡链路不可用，见 §七）
- 依据：owner 2026-10-19 派单裁决（「微 chore 修掉，不选 ruff exclude」）；源头登记 D2026-1019-02（批4 红线第 7 条「不碰 spike/」留下的存量）

## 一、根因

spike/ 为 D2026-1003-05 预研产物（FTS5 / pysubs2 spike，其结论已收编 2.6.4 批1/批2），入库时带 8 处 ruff 存量。批4 执行红线明令不碰 spike/，存量由 D2026-1019-02 登记移交；本卡独立清理，语义零变。

修复前 `ruff check spike/`（红，原文）：

```
spike\fts5_spike.py:1:1: UP009 [*] UTF-8 encoding declaration is unnecessary
spike\fts5_spike.py:15:8: F401 [*] `os` imported but unused
spike\fts5_spike.py:19:8: F401 [*] `sys` imported but unused
spike\pysubs2_spike.py:1:1: UP009 [*] UTF-8 encoding declaration is unnecessary
spike\pysubs2_spike.py:8:8: F401 [*] `sys` imported but unused
spike\pysubs2_spike.py:61:15: SIM300 [*] Yoda condition detected
spike\pysubs2_spike2.py:1:1: UP009 [*] UTF-8 encoding declaration is unnecessary
spike\pysubs2_spike3.py:1:1: UP009 [*] UTF-8 encoding declaration is unnecessary
Found 8 errors.
[*] 8 fixable with `--fix`.
```

修复前全库 `ruff check .` 亦恰为该 8 处（无其他存量）。

## 二、改动文件（仅此 4 个，一卡多文件系派单「单一 chore 提交＋单 revert 实证」设计，裁量已披露）

| 文件 | 处 | 修法 |
|---|---|---|
| spike/fts5_spike.py | 3 | L1 删 coding 声明行（UP009）；L15 删 `import os`、L19 删 `import sys`（F401，裁卡前已核实全文件零 `os.`／`sys.` 使用，纯 stdlib 无副作用导入） |
| spike/pysubs2_spike.py | 3 | L1 删 coding 声明行（UP009）；L8 删 `import sys`（F401，零使用）；L61 比较翻转 `"今日はいい天気ですね" == subs[0].plaintext` → `subs[0].plaintext == "今日はいい天気ですね"`（SIM300，纯比较无副作用） |
| spike/pysubs2_spike2.py | 1 | L1 删 coding 声明行（UP009） |
| spike/pysubs2_spike3.py | 1 | L1 删 coding 声明行（UP009） |

## 三、改法

`.venv/Scripts/python.exe -m ruff check spike/ --fix` 一键机械修；随后逐处核对 `git diff` 恰为上表 8 处、无其他字节变化。

## 四、先红后绿回归

- 红：§一原文（8 errors）。
- 绿：修复后 `ruff check spike/` = 0；`ruff check .` = 0（全库归零）。
- 全量测试基线 **2512 passed + 4 skipped** 恒等（tests 对 spike/ 仅注释与品牌 allowlist 引用、零导入，已核）。

## 五、验收命令

以下命令均在项目根目录执行。

```
.venv/Scripts/python.exe -m ruff check spike/                       # 期望 0 违规
.venv/Scripts/python.exe -m ruff check .                            # 期望 0 违规（全库）
git diff --stat                                                     # 期望仅 §二 4 文件
.venv/Scripts/python.exe -m pytest -q                               # 期望 2512 passed, 4 skipped
.venv/Scripts/python.exe -m subtransjav.refine.cli --help           # 冒烟 rc=0
.venv/Scripts/python.exe -c "import subtransjav.webview_gui.main"   # GUI 主模块导入 rc=0
```

## 六、约束

1. 禁止 ruff exclude／全局配置弱化替代修复。
2. 仅改 §二 4 文件；禁碰产品面、tests、CI、artifacts/（含 b4 树外 harness 15 条）、Mimosa seal 覆盖对象。
3. 语义零变；若某处无法机械修复，停下上报，不得自行裁决 exclude。
4. 逐文件点名 add（禁 `git add -A`）；chore 提交与文档登记严格分离。
5. 只 commit 不 push；push 由主审验收后执行。
6. 卡面不写真实仓库根路径字面量（品牌钉口径）。

## 七、执行方式披露

`tools/exec_wrapper.py` 与 `tools/pointer_tools.py` 不在本仓库，opencode CLI 全机未安装（npm 全局无、where 无）——与 d1018-卡3（2026-10-18）登记的缺失同型第二发（批2~批4 期间曾恢复，现又不可用）。按全局 AGENTS 兜底条款（所有轮转不可用时主审兜底亲执）由主审直接执行本卡；8 处全为 ruff `--fix` 确定性自动修，无指针工具依赖。基础设施恢复方式待 owner 裁决。

## 八、执行记录

- **执行**（2026-10-19 深夜～10-20 凌晨，主审兜底亲执，§七 披露）：`ruff check spike/ --fix` 一键机械修，8 处全修（8 fixed, 0 remaining）；`git diff` 逐处核对恰为 §二 8 处（4 删 coding 行、3 删未用导入、1 翻转比较），零越界。
- **验证链**：静态 `ruff check spike/` = 0、`ruff check .` = 0（全库 8→0）；全量 pytest **2512 passed + 4 skipped**（152.7s，基线恒等）；冒烟 `refine --help` rc=0 ＋ GUI 主模块导入 rc=0；secret 扫描（diff 新增行＋未跟踪卡片全文，75 行）0 命中。
- **单 revert 实证**：临时 worktree（%TEMP%\stj-revert-proof-d1019，已清）revert `f6d3a01` 后 `git diff c42d1e9` = **0 行**（--stat 空）。
- **Mimosa**：deep 扫描产品面 28 identity 零新增，seal 见 decision-log D2026-1019-03（提交钩子 scanner_enobufs 兼容放行在本笔 chore 提交时再次复现，深扫按临时替代口径会话侧取得，未宣称钩子面安全）。
- **提交**：`f6d3a01`（spike 4 文件，逐文件点名）；docs（本卡执行记录＋decision-log 登记）随后单独提交，push 由主审执行。
- **遗留问题**：本卡范围内无。派卡基础设施缺失第二发按 §七 披露，恢复方式待 owner 裁决（L-20261020-01）。
