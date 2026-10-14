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

### 执行者：OpenCode / 2026-10-14

**改动文件（4 个，其中测试文件为卡面 §先红后绿 授权）**

| 文件 | 改动 |
|---|---|
| `subtransjav/webview_gui/assets/app.js` | 两 placeholder **仅改值**：`key_placeholder`「留空用已保存密钥（LM Studio 免填）」→「留空用已保存密钥」；`key_saved_placeholder`「已保存密钥 ✓（留空即用）」→「已保存 ※※※※※※」 |
| `subtransjav/webview_gui/assets/style.css` | `--w-key-input: 200px`→`140px`（:115 注释同步）；`#refineS1Key, #refineS3Key … max-width: 280px`→`200px`（:1602 注释同步，含卡面算术 236 ≤ 244） |
| `tests/test_gui_js_static.py` | 新增钉 `test_api_key_row_compact`；**下调既有冲突钉**（详见下方「锁钉处置」） |
| 本卡 | 执行记录 |

**红线遵守**：index.html **零改动**（未进 diff）；app.js 改动仅限 `const MSG` 两行值，**保存数据流零触碰**——`saveStageKey`（:5599 `inp.value=''` 清空 + placeholder 三元）与启动回填（:5690 placeholder）逐字未动；FROZEN_IDS/data-i18n/MSG **键集零增减**（改值不改键）。

### 锁钉处置（先 grep 两 placeholder 值，如实汇报）

1. `key_placeholder` 旧值「留空用已保存密钥（LM Studio 免填）」**全仓 3 处**：app.js:262（已改）、index.html:255 / :299（`placeholder=` 静态回退字面量，**按卡面 index.html 零改动未动**，见遗留问题①）、本卡卡面。
2. `key_saved_placeholder` 旧值「已保存密钥 ✓（留空即用）」**全仓仅 app.js:472 一处**。
3. **两 placeholder 旧值在 tests 中均无值级锁钉**。`tests/ui_contract_snapshot.json:320` 只钉**键名** `key_placeholder`（键集钉），改值不受影响；`tests/test_strings_and_shortcut.py:50` 全值中文钉作用于 `strings.py` 的 Python MSG 表，本二键不在其中（app.js MSG 已 grep 确认无 Python 镜像键，故无双表值冲突）。
4. **卡面 grep 范围外发现 1 处硬冲突（如实处置）**：既有钉 `tests/test_gui_js_static.py::test_realdevice_feedback_pins` ②（:5180-5182）断言 `#refineS1Key/#refineS3Key` 必须 `max-width: 280px`，与卡面强制值 `200px` **直接矛盾、不改必红**。已如实下调为 `200px` 并加注说明：立法意图（「保存钮紧随输入框不贴行尾」）不变，仅随卡Q 收窄下调数值。
5. `--w-key-input: 200px` 在 tests 中无值级锁钉。

### 先红后绿

1. **落钉→红**：先写 `test_api_key_row_compact` 不动产品码，运行 → 红（断言① `MSG.key_placeholder 应为「留空用已保存密钥」` AssertionError）。
2. **改→绿**：4 处改动后 → 绿。
3. **反向自证（stash 回滚产品码，钉仍红）**：`git stash push` 仅回滚 app.js/style.css → 钉红；`git stash pop` 还原 → 钉绿。确认钉对旧码具备判别力、非恒绿。
4. **执行者自身缺陷如实记录**：首版钉的「`留空即用` 不在 app.js」全文件否定断言误伤无关键 `tm_threshold_title`（app.js:297，阈值标题文案）导致绿转红。已改为按 MSG 条目行提取逐字比对（`^\s*<key>:\s*'(?P<v>[^']*)',` + 精确等值），**未触碰任何产品码**即转绿。

### 自测结果（卡面 §验收）

| # | 命令 | 结果 |
|---|---|---|
| 1 | `ruff check subtransjav tests` | ✅ All checks passed |
| 2 | `pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py tests/test_strings_and_shortcut.py -q` | ✅ **231 passed**（基线 230 + 新钉 1，全绿） |
| 3 | `pytest tests/ -q` | ⚠️ 46 failed / 2088 passed / 18 skipped（基线 46 failed / 2087 passed / 18 skipped）。**失败集逐条 diff 完全一致**，与本卡无关 |
| 4 | `python -m subtransjav.refine.cli --help` | ✅ 退出码 0 |

**#3 假失败定性（如实记录）**：46 条全为**基线既存失败**，根因 `ModuleNotFoundError: No module named 'pysubs2'`（`subtransjav/refine/subtitle_convert.py:25`），即本机缺可选依赖，与 GUI 资产改动无因果关系。已用「stash 至净基线跑全量 → 导出 FAILED 清单 → 与改动后清单 diff」双向验证**零差异**（分布：test_cli.py 25 / test_subtitle_convert.py 20 / test_h4b_adaptive.py 1）。未掩饰、未绕过、未为本卡顺手修。

### 遗留问题（交主审判定，本卡未自行扩权处理）

① **index.html 静态回退未同步**：:255 / :299 仍写死旧长占位「留空用已保存密钥（LM Studio 免填）」。运行时由 `applyI18n()`（app.js:917-920）以 MSG 值覆盖，功能正常；但 **i18n 应用前存在旧长文案一闪**，且卡面「index.html 零改动」为硬约束，故未动。是否放宽卡面同步静态回退，请主审裁定（改动会触及 index.html 两处 placeholder 字面量 + 连带静态回退钉）。
② **`--w-key-input` 为共享 token 的连带影响**：该 token 另一消费点为 `index.html:672`（`mediaOverrideInput` 的 `min-width`），200px→140px 会**一并收窄媒体覆盖行输入框**（非 API Key 行）。卡面点名该 token 故属授权内，但真机观感需主审一并过目（卡E 曾以 200px 上调治「占位被截断」，此处回退 140px 有反向观感风险）。
③ **GUI 真机验收未做**：卡面 §验收 5 明示由主审另跑；自测视为未验证。
④ `pysubs2` 缺失导致的 46 条基线红待环境侧处理，非本卡范围。
