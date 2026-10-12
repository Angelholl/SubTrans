# D2026-1010-01 卡3（P1）：Console 面板布局重设计——修行向横排根因 + 加高

Refs: D2026-1010-01。owner 反馈原话「小窗高度可以加一点，宽度太短了，比例畸形」。设计规格由主审基于代码根因直出（design-expert 两度超时取消，主审直做设计）。执行者：OpenCode。只 commit 不 push；只改本卡点名文件，卡外问题即停待裁决。

## 根因（宽度畸形真根因，已实证，勿再诊断）

`subtransjav/webview_gui/assets/style.css:478-482` `.console-section .section-content { flex: 1; display: flex; }`——flex 默认行向，而 2.7.3 件⑧给该区新增了两个兄弟节点（`.console-activity-header` + `#consoleActivity`，index.html:186-190），三块被横排：活动流头部（原始日志按钮）竖在左列、活动流暗盒按内容宽居中、右侧大片空白=owner 看到的畸形窄盒。2.6.2 批3 当年给同样中招的 `#refineAiAnalyzeSection` 做过列向补刀（style.css:488-491），漏了正主 #tab-translate 的 Console。

## 设计规格（改法）

改动文件（仅此 2 个）：

1. `subtransjav/webview_gui/assets/style.css`
2. `tests/test_gui_js_static.py`

1. **修宽度（根因）**：style.css:478-482 `.console-section .section-content` 增加
   ```css
   flex-direction: column;
   align-items: stretch;
   ```
   （与既有 #refineAiAnalyzeSection 补刀同法补全正主；该既有覆盖因此冗余但无害，**不删**，最小 diff。）→ 活动流盒与原始日志恢复纵向堆叠、占满行宽；「原始日志」按钮回标题行右侧（`.console-activity-header` 本身就是 space-between 头部行）。
2. **加高**：style.css:765 `.console-activity` `max-height: 140px` → `max-height: 200px`。
3. **整区随高**：style.css:787-791 `#tab-translate .console-collapsible:not(.collapsed)` `min-height: 150px` → `180px`；`max-height: 300px` → `380px`。
4. 零 HTML 改动、零 JS 改动；双主题配色走既有 `--console-*` 令牌自动适配，无需新规则。

## 回归钉（tests/test_gui_js_static.py，同文件既有钉法）

- 钉 style.css 中 `.console-section .section-content` 规则块含 `flex-direction: column`（防回退——.console-section 族已有两次连带横排前科）。

## 验收命令（仓库根）

```
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q --basetemp=.pytest-tmp
```

## 验收现象清单（主审黑盒/真机核对，不属执行者职责）

1. 翻译页 Console：活动流暗盒占满内容区全宽（不再窄盒）。
2. 「原始日志」按钮位于活动流盒上方标题行右侧。
3. 展开原始日志：活动流在上、原始日志在下，纵向堆叠均全宽。
4. 活动流盒高约 200px（约 7-8 行摘要）。
5. 折叠（chevron）收起后仅剩标题行。
6. AI 分析页（#refineAiAnalyzeSection）布局无回归；亮/暗主题暗盒文字可读。

## 约束

- 只动上述 2 文件；不动 app.js / index.html。
- 遵守仓库 AGENTS.md：Conventional Commits 中文描述，正文含 `verify:` 与 `Refs: D2026-1010-01`；只 commit 不 push；禁止 `git add -A`。
- 提交信息注明「GUI 未验证（黑盒由主审补跑）」。
- 完成后在本卡末尾追加执行记录（改动文件/自测结果/遗留问题）。

## 执行记录（2026-10-10，主审亲执——owner 令本轮写码不转 OpenCode）

- **改动文件**：`subtransjav/webview_gui/assets/style.css`、`tests/test_gui_js_static.py`（未超出卡片点名范围）。
- **实现要点**：①`.console-section .section-content` 增 `flex-direction: column; align-items: stretch;`（横排根因修复，#refineAiAnalyzeSection 既有补刀按卡片保留不删）；②`.console-activity` max-height 140→200px；③整区 min-height 150→180px / max-height 300→380px；④新钉 `test_console_section_layout_column_and_height_pins`（列向防回退+新数值）。
- **既有钉更新（决策依据已归档）**：`test_batch3_console_ratio_and_section_overflow_pinned` 原 150/300 数值冻结与本次 owner 令的规格变更冲突——按 D2026-1010-01 更新为 180/380 并注记决策出处（钉只增不灭，30% 比例制保留）。
- **先红后绿**：新钉先红 → 改后全绿。
- **自测**：`pytest tests/test_gui_js_static.py` 135 passed。
- **遗留**：GUI 黑盒由主审负责（见提交信息「GUI 已验证/未验证」注记）。
