# d1015 残余批 · 卡K · P2-4 质量页 details 原生标记归一（mask 自绘 chevron）+ 钉

> 以下命令均在项目根目录执行。规格依据：docs/design/d1015-P2残余批-设计规格.md §3（裁定追记 v2 R12）。**卡面行号参考，执行以 re-grep 定位。**

## 根因

质量页 `<details id="refineGuideViewer">` 的 summary 是全站唯一既未摘原生 ▶ 标记、又无任何箭头语言的折叠头（站内两套既有语言：Console/词库按钮式 rotate；dict-diag/mp-tier summary 内嵌 svg 或 marker 摘除）。owner 痛点=与全站 Lucide chevron+rotate 不一致。

## 改动文件（仅 2 个）

1. `subtransjav/webview_gui/assets/style.css`
2. `tests/test_gui_js_static.py`

## 改法

style.css 在 `#refineGuideViewer > summary` 既有规则（re-grep `refineGuideViewer`，现仅一条 color/weight 规则）之后新增 4 条：
```css
#refineGuideViewer > summary { list-style: none; }
#refineGuideViewer > summary::-webkit-details-marker { display: none; }
#refineGuideViewer > summary::after {
    content: "";
    flex: none;
    width: 14px;
    height: 14px;
    background-color: var(--text-2);
    -webkit-mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m9 18 6-6-6-6'/%3E%3C/svg%3E") center / contain no-repeat;
    mask: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='14' height='14' viewBox='0 0 24 24' fill='none' stroke='%23000' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m9 18 6-6-6-6'/%3E%3C/svg%3E") center / contain no-repeat;
    transition: transform var(--dur) ease;
}
#refineGuideViewer[open] > summary::after { transform: rotate(90deg); }
```
要点：图形=Lucide chevron-right（与全站同源同粗 stroke-width=2）；颜色由 background-color var(--text-2) 承担（mask 只取 alpha，自动随主题，暗侧 6.9:1）；%23 编码走 select 箭头 data-uri 先例（不命中钉3 正则，已核）；-webkit-mask 与 mask **双写**；summary 本就是 display:flex（内联），::after 自然落行尾不挤压。

## 先红后绿

tests 新增 `test_p24_guide_details_chevron_pinned`：
- ① style.css 含 `#refineGuideViewer > summary::-webkit-details-marker` 摘除规则；
- ② 含 `#refineGuideViewer[open] > summary::after` 旋转规则；
- ③ 含 `#refineGuideViewer > summary::after` 且规则体含 `var(--text-2)` 与 `mask`；
- ④ index.html 中 `refineGuideViewer` 出现次数不变（==现值，先 grep 记数——防误改 HTML）。

流程：先写钉 → ①②③ 必红 → 落 CSS → 全绿。红/绿输出贴执行记录。

## 验收命令

```
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k p24
grep -n "refineGuideViewer" subtransjav/webview_gui/assets/style.css
```

## 约束

- 只改上列 2 文件；index.html 零改动（内联样式保持）；零新 svg 标签（不碰 stroke 双钉判定面）；`.mp-variants-summary`/`.dict-diag` 披露行不动（登记不修，防验收误判）。
- 既有钉 `#refineGuideViewer summary .media-source-bar` 不受影响（规则体未动）。
- 提交信息：`fix(gui): P2-4 质量页 details chevron 归一+钉（d1015-卡K）`，正文含 `verify: 先红后绿+全链绿` 与 `Refs: D2026-1015-05`。
- 完成后在本卡末尾追加执行记录。
