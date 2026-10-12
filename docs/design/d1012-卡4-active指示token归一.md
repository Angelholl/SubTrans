# 单件卡：组件 active 指示 token 归一（别名 token，视觉零变化）

> 决策依据：D2026-1012-01 阶段 1 地基批（地基批三件套之三，视觉零变化）；A2 排印小样已锁 A 档（本卡为色值别名不涉排印）。
> 执行者：OpenCode。只 commit 不 push；超卡即停待裁决。

## 根因（为什么要改）

激活态样式散落四条规则、各自直引品牌/语义 token，"组件被激活长什么样"无单一视图：
- `style.css:250` `.side-tab-btn.active`＝`--primary-soft` 底 + `--primary-strong` 字 + `inset 2px 0 0 var(--primary-strong)` 左条；
- `style.css:2292` `.review-page-btn.active`＝`--primary-soft`+`--primary-strong`+600 字重；
- `style.css:1096` `.dict-kind-chip.active`＝`--primary-border`+`--primary-soft`+`--primary-strong`；
- `style.css:1571` `.feature-badge.active`＝`--ok-soft`+`--ok`（语义态，**不收编**，保持现状）。
阶段 2 视觉批要统一调激活态时须逐规则手改且易漏；先固化别名层，阶段 2 只动一处。

## 改动文件（一卡两文件）

1. `subtransjav/webview_gui/assets/style.css`（:root 新增 4 个别名 token + 三条 active 规则改引别名）
2. `tests/test_ui_phase3_redlines.py` 或 `tests/test_gui_js_static.py`（新增一条静态钉，放现有钉所在文件更近者）

## 改法

1. **:root 别名 token**（放品牌组之后，注释"组件激活指示别名层（D2026-1012-01 地基批）：阶段 2 调激活态只动这里"）：
   `--active-bg: var(--primary-soft); --active-text: var(--primary-strong); --active-border: var(--primary-border); --active-bar: var(--primary-strong);`
2. **三条规则改引**：`.side-tab-btn.active`→bg/text/bar；`.review-page-btn.active`→bg/text；`.dict-kind-chip.active`→border/bg/text。**值语义零变化**（别名直指原值）。`.feature-badge.active` 不动。
3. **暗色自查**：style.dark.css 若经 token 重映射覆盖同名 token 则别名自动跟随，零改动；若暗色文件直改了上述三条规则（先 grep 确认，当前探测无 .active 规则），则同步改引别名并在执行记录注明。
4. **静态钉**：新增断言——`:root` 含四个 `--active-*` 定义；三条规则体内不得再出现 `--primary-soft`/`--primary-strong`/`--primary-border` 直引（`.feature-badge` 除外）。P8 钉3（组件规则色值字面量冻结）不受影响：var() 引用非字面量。

## 先红后绿

- 红：临时删除 `--active-bg` 定义，新钉必红；还原后绿。
- 绿：定向两测试文件全绿 + 全量基线不降（当前 2397+4）。

## 验收命令

```
cd /d D:\SubTransJAV
.venv\Scripts\python -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q --basetemp=.pytest_card
.venv\Scripts\python -m pytest -q --basetemp=.pytest_card
.venv\Scripts\python -m ruff check subtransjav tests
```

## 约束

- 只动上列两文件（style.dark.css 仅在 grep 证实有直改 active 规则时才许动并注明）；
- 视觉零变化：computed-style 前后等值由主审 GUI 黑盒复核（web-gui-tester）；
- 不新增字面色值（P8 钉3 口径）；
- 执行记录追加本卡末尾（改动/自测/遗留）。
