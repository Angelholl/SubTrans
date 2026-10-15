# d1015 残余批 · 卡L · review.js 导入按钮图标存活修复（P1-4 #8 收尾）+ 钉

> 以下命令均在项目根目录执行。背景：卡B 已在校对页两枚 `review-import-btn` 内预置 video/file-text svg，但 `review.js` 的 `_injectTexts()`（re-grep `_injectTexts`）对按钮执行裸 `btn.textContent = REVIEW_MSG…` 整段覆写 → svg 运行期被抹（卡B 执行记录遗留①）。**卡面行号参考，执行以 re-grep 定位。**

## 根因

`textContent` 赋值清空全部子节点；图标需保留、文案需追填，二者必须共存于按钮内。

## 改动文件（仅 2 个）

1. `subtransjav/webview_gui/assets/review.js`
2. `tests/test_gui_js_static.py`

## 改法

review.js `_injectTexts` 内对两枚 `.review-import-btn` 的写入改为「清文本、回插 svg」：
```js
const svg = btn.querySelector('svg');
btn.textContent = REVIEW_MSG.review_import_video;   // 原值不动
if (svg) btn.prepend(svg);
```
（srt 钮同款；变量名以函数实境为准，先读再改。若函数内还有其他对 `.review-import-btn` 的 textContent/innerHTML 覆写点（re-grep `review-import-btn` 核全），同款处理。）

## 先红后绿

tests 新增 `test_review_import_icons_survive_inject`：
- ① review.js `_injectTexts` 函数体含 `querySelector('svg')` 与回插手段（`prepend`/`appendChild`/`insertBefore` 任一）；
- ② 函数体内不得存在对 `.review-import-btn` 的裸 `textContent =` 直接赋值后不回插 svg 的写法（按 ① 的存在即视为满足，写成正向断言即可）。

流程：先写钉 → 必红 → 改 review.js → 全绿。红/绿输出贴执行记录。

## 验收命令

```
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k review_import_icons
grep -n "review-import-btn" subtransjav/webview_gui/assets/review.js
```

## 约束

- 只改上列 2 文件；index.html/strings.py 零触碰；REVIEW_MSG 键零增减。
- 提交信息：`fix(gui): P1-4#8 校对页导入钮图标存活（svg 回插）+钉（d1015-卡L）`，正文含 `verify: 先红后绿+全链绿` 与 `Refs: D2026-1015-05`。
- 完成后在本卡末尾追加执行记录。
