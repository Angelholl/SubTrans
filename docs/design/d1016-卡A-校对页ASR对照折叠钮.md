# d1016 卡A · 校对页 ASR 对照钮补 chevron 折叠语言 + aria 状态 + 钉

> 以下命令均在项目根目录执行。规格依据：阶段4 统一真机走查反馈（2026-10-16，owner：校对 TAB 页缺失折叠/展开按钮，走查清单 F 节裁卡修复）。**卡面行号参考，执行以 re-grep 定位。**

## 根因

校对页疑点区工具行（`.review-det-tools`，index.html L964-975）两枚 `btn-ghost` 钮：「载入疑点段」=纯加载动作；「ASR 对照」=`.review-asr-card` 显隐唯一切换钮——但该钮无 chevron、无 aria 状态、切换无任何视觉反馈，观感与纯文本链接无异。全站折叠语言已归一为「Lucide chevron + rotate」（P2-4 卡K 钉质量页 details；词库页走查项 B2 折叠箭头），校对页是唯一漏网的可切换区块，真机走查 B 组判为缺失。

## 改动文件（3 个，语义不可分——chevron 常显 / 展开旋转 / 状态接线三件套一体交付）

1. `subtransjav/webview_gui/assets/style.css`
2. `subtransjav/webview_gui/assets/review.js`
3. `tests/test_gui_js_static.py`

## 改法

### 1. style.css

在 `.review-det-tools` 既有规则块（re-grep，现 L2595）之后新增 2 条：

```css
#reviewAsrBtn::after {
    content: "";
    flex: none;
    width: 14px;
    height: 14px;
    background-color: var(--text-2);
    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m9 18 6-6-6-6'/%3E%3C/svg%3E") center / contain no-repeat;
    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m9 18 6-6-6-6'/%3E%3C/svg%3E") center / contain no-repeat;
    transition: transform var(--dur) ease;
}
#reviewAsrBtn[aria-expanded="true"]::after { transform: rotate(90deg); }
```

要点：图形=Lucide chevron-right 与 P2-4 同源同粗（stroke-width=2）；颜色由 `background-color: var(--text-2)` 承担（mask 只取 alpha，自动随主题）；`%23` 编码走 select 箭头 data-uri 先例（不命中钉3 正则，卡K 已核同款串）；`-webkit-mask` 与 mask **双写**；`.btn` 基类本就是 inline-flex+gap（L930-934），`::after` 自然落文案尾。既有 `.review-det-tools button:empty { display: none }`（L652）不受影响（伪元素不参与 `:empty` 判定，且运行时 JS 已填文案）。

### 2. review.js

`_bindDetections()` 内 `reviewAsrBtn` click handler（re-grep `reviewAsrBtn`，现 L1120-1128）等价重写——display 切换语义不变，仅补状态属性同步：

```javascript
asrBtn.addEventListener('click', () => {
    const card = document.querySelector('.review-asr-card');
    if (!card) { return; }
    const open = getComputedStyle(card).display === 'none';
    card.style.display = open ? '' : 'none';
    asrBtn.setAttribute('aria-expanded', open ? 'true' : 'false');
});
```

index.html **零改动**（初始无 aria-expanded 属性=收起态语义；chevron 常显即提供折叠可发现性）。

### 3. tests/test_gui_js_static.py（先红后绿）

新增 `test_review_asr_chevron_pinned`（写法参照既有 `test_p24_guide_details_chevron_pinned`，re-grep 定位，沿用本地解析 helper）：

- ① style.css 含 `#reviewAsrBtn::after` 规则且规则体含 `var(--text-2)` 与 `-webkit-mask`、`mask` 双写；
- ② style.css 含 `#reviewAsrBtn[aria-expanded="true"]::after` 且规则体含 `rotate(90deg)`；
- ③ review.js 的 reviewAsrBtn handler 体含 `setAttribute('aria-expanded'`；
- ④ index.html 中 `reviewAsrBtn` 出现次数恒为 1（防误改 HTML）。

流程：先写钉 → ①②③ 必红 → 落 CSS+JS → 全绿。红/绿输出原文贴执行记录。

## 验收命令

```
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k review_asr_chevron
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q
ruff check tests/test_gui_js_static.py
grep -n "reviewAsrBtn" subtransjav/webview_gui/assets/style.css subtransjav/webview_gui/assets/review.js
```

## 约束

- 只改上列 3 文件；index.html 零改动（FROZEN_IDS / `tests/ui_contract_snapshot.json` 零触碰）；零新 svg 标签（不碰 stroke 双钉判定面）。
- 「载入疑点段」钮**不加** chevron（加载动作非折叠切换，语义不符，保持现状）；`.review-asr-card` 位于 `#reviewDetectionsWrap` 内、wrap 无数据时整体隐藏——未导入态点 ASR 对照无可见效果属既有设计（走查清单 E3 登记态），本卡不扩范围。
- 既有黑盒/契约测试零回潮；`test_p24_guide_details_chevron_pinned` 不动。
- 提交信息：`fix(gui): 校对页 ASR 对照钮补 chevron 折叠语言+aria 状态（d1016-卡A）`，正文含 `verify: 先红后绿+定向/全量绿` 与 `Refs: D2026-1016-01`。
- 执行者只 commit 不 push；代码与 docs 执行记录按仓库惯例拆两 commit。
- 完成后在本卡末尾追加执行记录：改了哪些文件 / 自测结果 / 遗留问题。

---

## 执行记录（2026-10-16，执行者：OpenCode / DeepSeek V4.1 Flash）

### 改动文件

1. `subtransjav/webview_gui/assets/style.css`（+15 行）：在 `.review-det-tools` 规则块之后新增 `#reviewAsrBtn::after` 自绘 Lucide chevron-right 规则 + `#reviewAsrBtn[aria-expanded="true"]::after { transform: rotate(90deg); }`，与卡面给文一字不差。
2. `subtransjav/webview_gui/assets/review.js`（L1120-1128，等价重写）：`_bindDetections()` 内 `reviewAsrBtn` click handler 改为 `if (!card) { return; }` 早退 + 以 `open` 变量同步 `setAttribute('aria-expanded', ...)`；display 切换语义不变。
3. `tests/test_gui_js_static.py`（+69 行）：新增 `test_review_asr_chevron_pinned`（断言面 ④= style.css `#reviewAsrBtn::after` 体含 `var(--text-2)` + `-webkit-mask`/`mask` 双写；②= `[aria-expanded="true"]::after` 旋转；③= review.js handler 体含 `setAttribute('aria-expanded'`；④= index.html `reviewAsrBtn` 计数恒为 1）。

`index.html` 零改动；FROZEN_IDS / `tests/ui_contract_snapshot.json` 零触碰；零新 svg 标签（仍走 data-uri mask）。

### 自测结果（先红后绿）

先写钉、未落 CSS/JS 时（红）：

```
$ .venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k review_asr_chevron
F                                                                        [100%]
================================== FAILURES ===================================
_______________________ test_review_asr_chevron_pinned ________________________
    # ① 自绘 chevron 规则体：mask 取 alpha + 颜色 var(--text-2) + 双写 mask
    drawn = _p01_rule_blocks(css, "#reviewAsrBtn::after")
>       assert drawn, "① 缺 #reviewAsrBtn::after 自绘 chevron 规则"
E       AssertionError: ① 缺 #reviewAsrBtn::after 自绘 chevron 规则
E       assert []
tests\test_gui_js_static.py:6593: AssertionError
=========================== short test summary info ============================
FAILED tests/test_gui_js_static.py::test_review_asr_chevron_pinned - Assertio...
1 failed, 198 deselected in 1.56s
```

②③ 同面因断言 ① 先止而未触达，另以 grep 直证同红（改动前 style.css 无 `reviewAsrBtn`、review.js 无 `setAttribute('aria-expanded'`）：

```
$ grep -c "reviewAsrBtn" subtransjav/webview_gui/assets/style.css
0
$ grep -n "setAttribute('aria-expanded'" subtransjav/webview_gui/assets/review.js
(none; exit 1)
```

落 CSS+JS 后（绿）：

```
$ .venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k review_asr_chevron
.                                                                        [100%]
1 passed, 198 deselected in 0.16s

$ .venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q
........................................................................ [ 36%]
........................................................................ [ 72%]
.......................................................                  [100%]
199 passed in 2.43s

$ .venv/Scripts/python.exe -m ruff check tests/test_gui_js_static.py
All checks passed!

$ grep -n "reviewAsrBtn" subtransjav/webview_gui/assets/style.css subtransjav/webview_gui/assets/review.js
subtransjav/webview_gui/assets/style.css:2606:#reviewAsrBtn::after {
subtransjav/webview_gui/assets/style.css:2616:#reviewAsrBtn[aria-expanded="true"]::after { transform: rotate(90deg); }
subtransjav/webview_gui/assets/review.js:242:        const asrBtn = document.getElementById('reviewAsrBtn');
subtransjav/webview_gui/assets/review.js:1120:        const asrBtn = document.getElementById('reviewAsrBtn');
```

零回潮旁证（品牌钉 / Phase3 红线面）：

```
$ .venv/Scripts/python.exe -m pytest tests/test_brand_allowlist.py tests/test_ui_phase3_redlines.py -q
.........                                                                [100%]
9 passed in 1.18s
```

### 遗留问题

- 无阻断项。未导入态点「ASR 对照」无可见效果属既有设计（走查清单 E3 登记态，卡面明确不扩范围），本卡未动。
- 「载入疑点段」钮按约束不加 chevron，保持现状。
- 提交：本执行者只 commit 不 push；代码（style.css / review.js / test）一 commit，本卡执行记录（docs）另一 commit。
