# d1013-卡3 · flake 甄别 B2：test_review_save_success_backup_and_rewrite（Windows 文件占用型）

- **回链**：D2026-1012-01 ⑨ flake 家族台账（卡9 执行中登记为"Windows 文件占用型 flake 第 5 例"）；症状=单跑绿、全量/组合跑间歇红于 `tests/test_gui_api.py::test_review_save_success_backup_and_rewrite`（:3623，保存流 .bak.srt 备份+重写）。
- **改动文件（只准这两个）**：
  1. `subtransjav/refine/fs_utils.py`
  2. `tests/test_v2_split_modules.py`（fs_utils 单测的既有落点；若该文件无 fs_utils 节则在文件尾新增节）
- **主审候选根因（须先实证甄别，再动手）**：`fs_utils._atomic_write_text`（:16-32，同目录 tmp + `os.replace`，fsync 后替换）**对 PermissionError 无重试**——Windows Defender/索引器对刚落盘文件短暂持有句柄，`os.replace` 抛 WinError 32/33 → 间歇红。真实用户同样暴露此竞态，故倾向**生产侧有界重试**而非测试侧绕过；若你的甄别推翻此假设（如复现指向测试自留句柄），按实情停在执行记录待裁决，不得硬修。

## 改法（假设成立时）

`_atomic_write_text` 的 `os.replace` 与临时文件写入路径对 `PermissionError`（含 WinError 32/33 共享冲突）加**有界重试**：如 5 次 × 20ms 起指数退避（总量 ≤ ~300ms），仅捕获 `PermissionError`/`OSError winerror in (32, 33)`，其余异常照抛；重试耗尽抛原异常。实现风格对齐该文件现有注释密度；禁止捕获宽泛 `Exception`。

## 先红后绿

- **红**：`tests/test_v2_split_modules.py` 新增单测——monkeypatch `os.replace` 首两次抛 `PermissionError`、第三次成功，断言 `_atomic_write_text` 最终成功且临时文件清理；改前跑必红（现实现无重试）。
- **绿**：实装重试后全绿；再补一条"耗尽后抛原异常"的负例单测（monkeypatch 恒抛，断言异常类型不变）。
- GUI 侧 `test_review_save_success_backup_and_rewrite` 本身不改（生产加固后自然受益）；若你甄别出该测试另有缺陷（如缺关闭句柄），只记录不改。

## 验收标准

以下命令均在项目根目录执行：

1. `ruff check subtransjav tests` → All checks passed
2. `python -m pytest tests/test_v2_split_modules.py tests/test_gui_api.py -q` → 全绿（含新单测先红后绿留证）
3. `python -m pytest tests/test_gui_api.py -q` 连续 3 次 → 全绿（逐一记录）
4. `python -m pytest tests/ -q` → 全量通过，基线只增不减（当前 2453+4）
5. `python -m subtransjav.refine.cli --help` 退出码 0（冒烟）

## 约束

- 只改上列 2 个文件 + 本卡追加执行记录。
- commit：`fix(fs): 原子写对 Windows 文件占用加有界重试（review_save 间歇红甄别）`，正文含 `verify:` 与 `Refs: D2026-1012-01`；只 commit 不 push；逐文件点名 add。
- 若甄别推翻假设：不改任何文件，把证据写进执行记录并停（commit 仅本卡执行记录亦须走 commit，正文注明"甄别推翻，未动代码"）。

## 执行记录

- **改动文件**：
  1. `subtransjav/refine/fs_utils.py`：`_atomic_write_text` 的 `os.replace` 对 `PermissionError`/WinError 32/33 加有界重试（5 次 × 20ms 起指数退避，总量 ≤ ~300ms）；新增 `_is_file_lock_error` 辅助函数；import `time`。
  2. `tests/test_v2_split_modules.py`：新增 `test_atomic_write_text_retry_on_permission_error`（前两次抛 PermissionError 第三次成功）与 `test_atomic_write_text_retry_exhausted_raises`（恒抛断言原异常）；import `os`、`pytest`。
- **甄别结论**：假设成立——现实现 `os.replace` 对 `PermissionError` 无重试，红测试证实。
- **自测结果**：
  - ruff check subtransjav tests → All checks passed
  - pytest tests/test_v2_split_modules.py tests/test_gui_api.py -q → 21 passed, 1 skipped
  - pytest tests/test_gui_api.py -q × 3 → 全绿（1 skipped）
  - pytest tests/ -q → 2072 passed, 18 skipped, 46 failed（全部为 `test_subtitle_convert.py` 预存基线问题，git stash 验证改动前同样失败）
  - python -m subtransjav.refine.cli --help → 退出码 0
- **遗留问题**：无
