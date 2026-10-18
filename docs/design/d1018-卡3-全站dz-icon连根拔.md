# d1018-卡3：全站 dz-icon 连根拔（主导入区 #dropzone 收尾）

以下命令均在项目根目录执行；卡内路径均为相对仓库根路径。

## 根因与现象

卡2（#reviewDropzone）遗留第 1 条：全站尚存最后一处同款「蓝框 + 向上箭头 + 下划线」装饰图标组——`#dropzone` 主导入区。owner 已授权放大：全站连根拔。本卡删尽 `dz-icon` 全部残留（markup + CSS），拖拽区仅保留文字提示与动作按钮。

## 改动文件（只许改这三个 + 本卡执行记录）

1. `subtransjav/webview_gui/assets/index.html`
   删除 134-136 行整块（以 grep 锚点实测为准）：
   ```html
   <div class="dz-icon">
       <svg ... ><path d="M12 16V4"/><path d="m6 10 6-6 6 6"/><path d="M4 20h16"/></svg>
   </div>
   ```
   （135 行 SVG 整行含三条 path，全站唯一，已实测。）
   **保留** 137 行 `<div class="dz-title" data-i18n="source_header">拖拽 .srt 字幕文件到这里</div>`、138 行 `<div class="dz-hint" data-i18n="empty_hint">…</div>`、139-142 行 `<div class="dz-actions">…</div>`（含 addFilesBtn / addFolderBtn 两按钮及其内联功能性 SVG——按钮图标不是本卡目标，禁碰）。

2. `subtransjav/webview_gui/assets/style.css`
   - 630-631 行是**一条组合规则**：`#tab-translate.has-files .dz-icon,` + `#tab-translate.has-files .dz-hint { display: none; }`。只摘除 630 行 `.dz-icon` 选择器行，`.dz-hint` 分支必须保留为活规则（删后该规则为单行 `#tab-translate.has-files .dz-hint { display: none; }`）。
   - 删除 633-642 行 `#tab-translate .dz-icon { … }` 规则块整块（10 行，含空行归并；特征 `border: 1px solid var(--primary-border)`）。
   - **保留** 643-645 行 `.dz-title` / `.dz-hint` / `.dz-actions` 三条规则（使用中）。

3. `tests/test_upload_zone_no_icon.py`
   扩展回归锁（先红后绿），在既有 5 用例**全部保留**的基础上新增：
   - 全站口径：index.html 全文不含 `dz-icon`；style.css 全文不含 `dz-icon`；assets 目录全部 `.js` 文件不含 `dz-icon`（实测 js 零命中，直接钉死防复发）；
   - 三条 path d 值（`M12 16V4` / `m6 10 6-6 6 6` / `M4 20h16`）在 index.html 全文不出现（全站唯一已实测）；
   - 主导入区结构保留锁：`#dropzone` 起止区间内 `dz-title`、`dz-hint`、`dz-actions` 仍在（`source_header` / `empty_hint` 词条引用不删）；
   - 组合规则活分支锁：style.css 中 `#tab-translate.has-files .dz-hint` 仍存在（防误删整条组合规则）；
   - 修正 docstring 第 10-11 行过时口径（`#tab-translate .dz-icon 属主导入区，不在本卡范围` 已不成立，改为全站已拔说明）。

## 改法要点

- 纯静态 DOM/CSS 删除 + 测试扩展，无逻辑改动。`app-main.js:134` 的 `has-files` class 切换是活功能（配合上述 `.dz-hint` 隐藏规则），禁碰。
- 行号均为裁卡时实测值，仅作定位提示；落编辑前以 grep 锚点（`dz-icon` 与三条 path d 值）重新核对上下文，经指针工具分段看。
- 图标删除后若 `#dropzone` 垂直留白明显失衡，可对 `.dropzone` 的 padding 做最小调整；`.dz-title/.dz-hint/.dz-actions` 相关样式禁动。

## 先红后绿

1. 先扩展 `tests/test_upload_zone_no_icon.py` 新断言，跑 `python -m pytest tests/test_upload_zone_no_icon.py -q` 确认新增断言红（dz-icon 仍在）；
2. 执行 index.html / style.css 两处删除 + docstring 口径修正；
3. 复跑同命令确认全绿（既有 5 用例 + 新增全过）。

## 验收命令（执行者自测 + 主审复跑）

- `python -m pytest tests/test_upload_zone_no_icon.py -q`
- `python -m pytest tests/test_gui_js_static.py tests/test_brand_allowlist.py -q`
- `python -m ruff check tests/test_upload_zone_no_icon.py`

## 约束

- 禁起完整 GUI（`python -m subtransjav.webview_gui.main`），禁截图、禁向调用方索要截图；本任务为静态 DOM 删除，代码分析即可完成。
- >4KB 文件（index.html / style.css 均达标）只准经指针工具分段看，禁止整读全文。
- 修改后最多审查 1 次；若找不到锚点，输出已探查文件路径即退出，禁止无脑全局搜索。
- 只 commit 不 push；逐文件点名 add、按语义分段提交（测试锁 / 代码删除 / 卡文件含执行记录可分），Conventional Commits 前缀 + 中文描述，正文含 `verify:` 红转绿结果与定向测试基线数。
- 完工后在本卡末尾追加"执行记录"：改了哪些文件 / 自测结果 / 遗留问题。

## 交付物

- `read_diff_only` 输出（index.html / style.css 两处删除 + 测试扩展 diff），明确指出删除的行号与内容。

## 执行记录（d1018-卡3）

### 执行方式声明

派卡链路不可用：`tools/exec_wrapper.py` 与 `tools/pointer_tools.py` 在本仓库缺失，opencode CLI 全机未安装（npm 全局无、where 无）。按全局 AGENTS 兜底条款（所有轮转不可用时主审兜底亲执）由主审直接执行本卡；卡面锚点系裁卡前 grep 逐条实测，全程零偏差，未启用指针工具（主审拥有文件全文上下文）。

### 改动文件

- `tests/test_upload_zone_no_icon.py`：docstring 升级卡2/卡3 双卡口径 + 新增 6 用例（index/style 全站无 dz-icon、js 资产全扫、三条 path 全文禁现、#dropzone 结构保留锁、has-files .dz-hint 活分支锁）
- `subtransjav/webview_gui/assets/index.html`：删原 134-136 行 `<div class="dz-icon">…</div>` 整块（三条 path：`M12 16V4`/`m6 10 6-6 6 6`/`M4 20h16`，全站唯一）；dz-title/dz-hint/dz-actions 与两按钮功能性 SVG 原样保留
- `subtransjav/webview_gui/assets/style.css`：摘组合选择器 `.dz-icon` 行（原 630 行，`#tab-translate.has-files .dz-hint { display: none; }` 活分支保留）+ 删 `#tab-translate .dz-icon` 规则块整块（原 633-642 行）；.dz-title/.dz-hint/.dz-actions 规则保留

### 自测结果（先红后绿）

- 先红：`python -m pytest tests/test_upload_zone_no_icon.py -q` → 3 failed（index/style/paths 全站断言）8 passed；
- 后绿：同命令 → 11 passed；
- 定向基线：`tests/test_gui_js_static.py + tests/test_brand_allowlist.py` → 205 passed；
- 全量（.venv）：2510 passed, 4 skipped（卡2 基线 2504 → 2510，+6 即本卡新锁，只增不减）；
- `python -m ruff check tests/test_upload_zone_no_icon.py` → All checks passed；
- 冒烟：subtransjav-refine --help 正常、webview_gui.main 可导入；
- Mimosa 深扫：findings 37 = 基线 37 零新增（seal sha256:d745f5df…54bb）。

### 遗留问题

1. **GUI 未验证**（纯静态 DOM 删除，卡面禁起 GUI，DOM 断言回归锁代验）；`#dropzone` 删图标后垂直留白实测未见失衡风险（gap 布局同卡2 先例），真机目验留待 owner。
2. 派卡基础设施缺失待 owner 裁决：exec_wrapper.py / pointer_tools.py 不在本机（疑在其他环境或未同步），opencode CLI 未安装——后续派卡流程恢复方式需 owner 定。
3. 未 push（与分支上卡2 四笔一并待主审验收推送）。
