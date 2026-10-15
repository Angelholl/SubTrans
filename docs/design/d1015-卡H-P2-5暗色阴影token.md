# d1015 残余批 · 卡H · P2-5 暗色蓝阴影 token 化 + 暗侧 active 文字 AA 修复（登记项搭车）

> 以下命令均在项目根目录执行。规格依据：docs/design/d1015-P2残余批-设计规格.md §1+§5（裁定追记 v2 R9/R14）。**卡面行号参考；插入锚勘正：--shadow-md 实为 :80 附近（非 :72），re-grep `--shadow-md` 定位。**

## 根因

`.brand-mark` 与 `.btn-primary` 的蓝阴影以 rgba 字面写死在组件规则内（style.css 两处，全量 grep 核过恰此 2 处），不走 --shadow-* token → style.dark.css 的变量覆盖机制失效，深色下发蓝光晕（owner P2-5 原话"浅色值漏改"，裁定暗侧应为中性更暗更淡 rgba(0,0,0,.4~.6)）。亮侧蓝影是基线原型明文（非漏改），原样收编保留。搭车项（P0 遗留登记①）：暗主题 .side-tab-btn.active 的 --active-text 取暗侧 --primary-strong #3B82F6，合成底对比 4.48:1 擦线不达 AA（critic 独立复算确认 4.476），1 行 token 覆盖修复。

## 改动文件（仅 2 个）

1. `subtransjav/webview_gui/assets/style.css`
2. `subtransjav/webview_gui/assets/style.dark.css`

## 改法

style.css `:root`（紧跟 `--shadow-md` 声明后）新增 2 行：
```css
--shadow-brand: 0 2px 6px rgba(59,130,246,.35);
--shadow-primary: 0 1px 2px rgba(37,99,235,.3);
```
组件替换（值原样收编，仅 var 化）：
- `.brand-mark` 的 `box-shadow: 0 2px 6px rgba(59,130,246,.35);`（re-grep `brand-mark`）→ `box-shadow: var(--shadow-brand);`
- `.btn-primary` 的 `box-shadow: 0 1px 2px rgba(37,99,235,.3);`（re-grep `.btn-primary` 规则体）→ `box-shadow: var(--shadow-primary);`

style.dark.css `:root`（re-grep 其 --shadow 覆盖组，紧随其后）新增 3 行：
```css
--shadow-brand: 0 2px 6px rgba(0, 0, 0, 0.5);
--shadow-primary: 0 1px 2px rgba(0, 0, 0, 0.5);
--active-text: var(--primary);   /* 暗侧激活文字提亮 #60A5FA，AA 修复（P0 遗留①），6.48:1 */
```

亮主题零变化（两 token 亮值=现值逐字）；暗主题两组件阴影转中性黑、激活文字转亮蓝（#3B82F6→#60A5FA，三处消费 .side-tab-btn.active/.review-page-btn.active/.dict-kind-chip.active 同步达标）。

## 先红后绿（本卡无钉；红证据=grep 前后值留痕，钉在卡I）

执行记录必含：
```
grep -n "rgba(59,130,246,.35)\|rgba(37,99,235,.3)" subtransjav/webview_gui/assets/style.css     # 改前 2 处组件字面；改后仅 :root 2 行
grep -n "shadow-brand\|shadow-primary\|active-text" subtransjav/webview_gui/assets/style.css subtransjav/webview_gui/assets/style.dark.css
```
自测：`.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q` 全绿（:root 不在钉3 判定面，已核；别名层钉判定面在 style.css，暗侧覆盖不触）。

## 验收命令

```
grep -c "rgba(59,130,246,.35)" subtransjav/webview_gui/assets/style.css    # 期望 1（仅 :root）
grep -n "active-text" subtransjav/webview_gui/assets/style.dark.css        # 期望 1 行覆盖
```

## 约束

- 只改上列 2 文件；--shadow-sm/md 不动；不并入现有 token（评议已裁）；亮侧两 rgba 字面移入 :root 后组件规则内不得残留。
- 提交信息：`fix(gui): P2-5 暗色蓝阴影 token 化+暗侧 active 文字 AA 修复（d1015-卡H）`，正文含 `verify: grep 留痕+全链绿` 与 `Refs: D2026-1015-05`。
- 完成后在本卡末尾追加执行记录（含「P0 规格遗留登记① 已由本卡收口」一句，供主答回写）。
