# 单件卡：B-07 恢复——checkbox→toggle 滑块（纯 CSS）

> 决策依据：d1012-阶段0a-基线偏差裁定表 B-07（owner 2026-10-12 裁"恢复基线"；handoff §7 阶段2 第 6 条原文"原生 checkbox → toggle 样式（底层 input 保留）"）。阶段 2 首批。
> 执行者：OpenCode（longcat-2.5-preview-free）。只 commit 不 push；超卡即停待裁决。

## 根因

style.css:968-976 复选框仍是 `accent-color: var(--primary)` 原生形态，注释自认"toggle 改造为阶段 2"未执行。owner 裁定恢复：纯 CSS toggle。

## 改动文件（一文件）

1. `subtransjav/webview_gui/assets/style.css`：将 :968-976 的 accent-color 方案改为 toggle 滑块——`input[type="checkbox"]`（表单类选择器沿用既有作用域，勿扩大到全局）`appearance:none` + 宽高轨道 + `::before` 圆形滑块 + `:checked` 平移变色；**只用既有 token**（--primary/--surface/--border 等，零新字面色值，P8 钉3 口径）；保留 :focus-visible 焦点环（P0-4 相关，不得引入 outline:none）；底层 input 元素与全部 id/事件零改动（纯视觉层）。暗色经 token 重映射自动跟随，style.dark.css 零改动（执行时 grep 证实后记录）。

## 先红后绿

- 红：临时删除 toggle 伪元素规则块 → 新钉红。
- 绿：新增静态钉（tests/test_gui_js_static.py）：复选框规则含 `appearance:none`+`::before` 滑块+`:checked` 位移，且**不含 accent-color 旧方案**；还原后定向全绿+全量基线不降（当前 2400+4）。

## 验收命令

```
cd /d D:\SubTransJAV
.venv\Scripts\python -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q --basetemp=.pytest_card
.venv\Scripts\python -m pytest -q --basetemp=.pytest_card
.venv\Scripts\python -m ruff check subtransjav tests
```

## 约束

- 只动 style.css 一个文件；不改任何 input 的 DOM/事件（黑盒行为等值由主审 GUI 复核）；
- **收尾硬纪律：全部自测完成后必须完成 commit+卡片执行记录追加并向主审报告"卡9 完成"，禁止在测试运行期间以"等待中"类文本结束回复**；
- 执行记录追加本卡末尾（改动/自测/遗留）。

## 执行记录（2026-10-12，OpenCode）

**改动文件（3 个，零超卡）：**

1. `subtransjav/webview_gui/assets/style.css`：:974-1007，原 `accent-color: var(--primary)` + 15px 原生形态方案改为纯 CSS toggle——`input[type="checkbox"]`（沿用既有全局作用域）`appearance:none` + 34×18px 轨道（`--border-strong` 边框 / `--surface-2` 底 / `--radius-pill` 圆角）+ `::before` 14px 圆形滑块（`--surface` / `--radius-round` / `--shadow-sm`）+ `:checked` 轨道变色 `--primary` + 滑块 `translateX(16px)` 平移 + `:focus-visible` 焦点环保留（`--focus-outline`，未引入 outline:none）。零新字面色值/零新圆角硬编码（全部 var() 引既有 token）。底层 input 元素与全部 id/事件零改动。
2. `tests/test_gui_js_static.py`：末尾新增 B-07 两钉——`test_b07_checkbox_toggle_pinned`（accent-color 删净 + appearance:none 轨道 + ::before 圆形滑块 + :checked 位移变色 + focus-visible 焦点环）、`test_b07_toggle_zero_new_literals_pinned`（toggle 全部规则体零字面量色值/零圆角硬编码档）。
3. 本卡文件（执行记录追加）。

**自测结果（先红后绿 + 验收命令逐条）：**

- 先红：临时删除 `::before` 滑块与 `:checked::before` 位移两规则块 → `test_b07_checkbox_toggle_pinned` 红（"缺少 input[type=\"checkbox\"]::before 滑块规则块"），还原后绿 ✓
- 定向：`pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q` → 163 passed ✓
- 全量：`pytest -q` → 1 failed, 2408 passed, 4 skipped（基线 2407+4 不降）；红例 `test_review_save_success_backup_and_rewrite` 为 Windows 文件占用类 flake（PermissionError os.replace 拒绝访问，不在本卡改动面），单跑即绿（1 passed）✓
- ruff：`ruff check subtransjav tests` → All checks passed ✓
- 暗色零改动证实：grep style.dark.css 无 checkbox/accent 引用，toggle 颜色全走 token（--surface-2/--border-strong/--primary/--surface），暗色经 token 重映射自动跟随 ✓

**遗留问题：**

- 无。黑盒行为等值（复选框勾选/事件）由主审 GUI 复核；词库行内 .gl-sel 复选框等既有作用域内元素一并呈 toggle 形态（作用域未扩大，34px 轨道带 flex-shrink:0，主审复核如需收紧可另开卡）。
