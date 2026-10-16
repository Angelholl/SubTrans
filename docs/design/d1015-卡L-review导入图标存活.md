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

---

## 执行记录（d1015-卡L）

### 一、改动文件（2 个，与卡面一致）

1. `subtransjav/webview_gui/assets/review.js`
   - `_injectTexts()` 内 `.review-import-btn` 循环改为「先取 svg 引用 → 写入文案 → 回插」：

     ```js
     document.querySelectorAll('.review-import-btn').forEach((btn) => {
         // textContent 覆写会清空全部子节点：先存图标引用，写入文案后回插
         const svg = btn.querySelector('svg');
         btn.textContent = (btn.dataset.kind === 'video')
             ? REVIEW_MSG.review_import_video : REVIEW_MSG.review_import_srt;
         if (svg) { btn.prepend(svg); }
     });
     ```

   - re-grep `review-import-btn` 核全：仅 `:221`（本循环，唯一 textContent 覆写点）与
     `:254`（`_bindDropzone` 事件委托 `.closest()`），无其他覆写点，故 srt 钮同款
     处理即被同一循环覆盖，无需第二处改动。
   - REVIEW_MSG 键零增减（原 `review_import_video`/`review_import_srt` 取用不变）。

2. `tests/test_gui_js_static.py`
   - 文件末追加 `test_review_import_icons_survive_inject`（d1015-卡L 段 + 钉）：
     正向双断言——`_injectTexts` 函数体含 `querySelector('svg')` 取图标引用 +
     含回插手段（`prepend`/`appendChild`/`insertBefore` 任一）。

### 二、自测结果（验收命令实测）

0. 先红（钉先落盘、review.js 未改）：

   ```
   .venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k review_import_icons
   ...

   >       assert "querySelector('svg')" in body, \
               "_injectTexts 未先取按钮内 svg 引用（裸 textContent 覆写会抹掉图标）"
   E       AssertionError: _injectTexts 未先取按钮内 svg 引用（裸 textContent 覆写会抹掉图标）
   E       assert "querySelector('svg')" in " _injectTexts() {\n ... \n    }"
   tests\test_gui_js_static.py:6309: AssertionError
   =========================== short test summary info ===========================
   FAILED tests/test_gui_js_static.py::test_review_import_icons_survive_inject
   1 failed, 191 deselected in 0.82s
   ```

1. 改 review.js 后复跑（后绿）：

   ```
   .venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k review_import_icons
   .                                                                        [100%]
   1 passed, 191 deselected in 0.08s
   ```

2. `grep -n "review-import-btn" subtransjav/webview_gui/assets/review.js`：

   ```
   221:        document.querySelectorAll('.review-import-btn').forEach((btn) => {
   254:            const btn = e.target.closest('.review-import-btn');
   ```

3. 全文件测试：`.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q`
   → `192 passed in 1.96s`（加钉前 191）。

4. 全链：`.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q`
   → `200 passed in 1.98s`。

5. `node --check subtransjav/webview_gui/assets/review.js` → 通过（无输出）。

6. ruff：`.venv/Scripts/python.exe -m ruff check tests/test_gui_js_static.py`
   → `All checks passed!`

7. 品牌钉（product 面改 review.js 后复核）：`.venv/Scripts/python.exe -m pytest tests/test_brand_allowlist.py -q`
   → `1 passed in 0.15s`。

### 三、遗留问题

1. 本钉为静态面钉（源码结构），真机「图标可见」仍需 owner 实机复核；静态断言
   只锁「清文本后回插 svg」的写法在位。
2. 卡B 执行记录遗留①（本条根因）已闭合；卡C 遗留②登记的本卡由本次改动承接。
3. `index.html`/`strings.py` 零触碰，REVIEW_MSG 键零增减，改动面与卡面
   「仅 2 文件」硬约束一致。
