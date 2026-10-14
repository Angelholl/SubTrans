# d1013-卡Q · API Key 行收窄左移+已保存星号显示（真机反馈）

- **回链**：D2026-1013-01 追记；owner 2026-10-14 指示：①保存按钮错位超出，API KEY+框+保存按钮整体左移；②API 框不需要文字（placeholder 长文案删），已加载保存的 KEY 直接 ※ 星号显示。
- **根因**（主审实扫）：流水线卡内容宽 244px，alt-row 内 label(API Key ≈50px)+gap 8×2+input(min-width 200px)+保存钮(30px)≈296px>244 → 保存钮被顶出卡缘（错位超出主因=input min-width:200px 过大）。
- **改动文件（只准这两个）**：
  1. `subtransjav/webview_gui/assets/app.js`
  2. `subtransjav/webview_gui/assets/style.css`
- index.html 零改动。

## 改法

1. **placeholder 两键改值（改值不改键，先 grep 值锁钉）**：
   - `key_placeholder`（app.js:262）：「留空用已保存密钥（LM Studio 免填）」→「留空用已保存密钥」（删括号补充）；
   - `key_saved_placeholder`（app.js:472）：「已保存密钥 ✓（留空即用）」→「已保存 ※※※※※※」（已保存态框内直接呈现星号视觉；含中文字满足 MSG 全值中文钉）。
2. **行宽收窄（整体左移）**：
   - style.css:115 `--w-key-input: 200px` → `140px`（注释同步）；
   - `#refineS1Key, #refineS3Key` 规则 `max-width: 280px` → `200px`（注释同步）。
   - 校验算术：label 50+gap 8+input(min 140)+gap 8+钮 30=236 ≤ 244 内容宽 → 保存钮回到卡内紧随输入框。
3. **数据流零改动**（安全红线）：不回填假掩码 value——已保存态视觉星号由 placeholder 承载；保存路径「留空=用已保存密钥」逻辑零触碰（避免掩码假值被当新 KEY 污染 DPAPI 存储）。

## 先红后绿回归测试

新增钉 `test_api_key_row_compact`（tests/test_gui_js_static.py）：断言 ①两 placeholder 改值在 MSG 表 ②`--w-key-input: 140px` 在 style.css ③`max-width: 200px` 在 #refineS1Key/#refineS3Key 规则。先落钉→红→改→绿，输出入执行记录。若两 placeholder 有既有值锁钉（先 grep），一并如实处置。

## 验收标准

以下命令均在项目根目录执行：

1. `ruff check subtransjav tests` → All checks passed
2. `python -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py tests/test_strings_and_shortcut.py -q --basetemp=.pytest_card` → 全绿
3. `python -m pytest tests/ -q --basetemp=.pytest_card` → 全量（假失败如实记录）
4. `python -m subtransjav.refine.cli --help` → 退出码 0
5. GUI 由主审另跑。

## 约束

- 只改上列 2 文件+本卡执行记录；index.html 零改动；FROZEN_IDS/data-i18n 键集零增减（改值不改键）；**保存数据流零触碰**（不回填 value、不改提交逻辑）。
- commit：`fix(gui): API Key 行收窄左移+已保存星号 placeholder`，verify:+Refs: D2026-1013-01；只 commit 不 push；逐文件点名 add（含本卡）。
- 自测视为未验证。

## 执行记录

（执行者追加）
