# d1018-卡1：app.js 拆分批1——AppModal 块切出（D2026-1016-05）

- **决策依据**：D2026-1016-05（阶段3 app.js 拆分）＋D2026-1018-01（批1 开拆门复核闭环：C1 闭环、C5 过评、Q1 三文件严格序、Q2 纯字节搬运豁免三条件、R-A 采纳=文件级 sha256 护栏、C2 审痕面裁定）。
- **卡0 已落地**：`tests/js_sources.py` 读取层（639d8f1），基线 2498+4，分支 `refactor/appjs-split`。

## 根因 / 目标

app.js（9830 行）按自包含度分批拆为零构建经典脚本多文件。首批切出 AppModal 顶层 const 块（L1011–2819，含区头注释 L1007–1010）。切分是**纯字节搬运**：三段按原始定义序拼接必须与原 app.js **逐字节相等**（守恒不变量），全部静态断言文本等价自动成立（C1 总判据）。

## 改动文件（6 个；拆分批多文件卡，触点显式列出仅限这些）

1. `subtransjav/webview_gui/assets/app.js` — 原 L1–1006（58,699B）
2. `subtransjav/webview_gui/assets/app-modal.js` — 新增，原 L1007–2820（92,754B）
3. `subtransjav/webview_gui/assets/app-main.js` — 新增，原 L2821–9830（318,745B）
4. `subtransjav/webview_gui/assets/index.html` — 仅在 app.js 与 review.js 两个 script 标签之间插入两行（app-modal.js、app-main.js）
5. `tests/js_sources.py` — 仅 `JS_FILES` 一行 + 注释同步
6. `tests/test_gui_js_static.py` — 仅钉 `test_js_sources_layer_pinned` 的①②更新 + 末尾新增钉 `test_js_split_integrity_pinned`

**C2 审痕面裁定（D2026-1018-01）**：三测试的断言行/锚点串/`3600` 数字零改动（审痕面=卡0 迁移 diff）；`test_js_sources_layer_pinned` 为随批更新钉、豁免于 C2 审痕面，但其新预期值已在本卡写死，验收逐行对照。

## 改法（纯字节搬运，零新增代码行）

### 1. 三文件切分（唯一合法切法）

用 Python **二进制模式**切分（防 CRLF/编码污染；原文件 LF-only、UTF-8 无 BOM）：

```python
from pathlib import Path
p = Path("subtransjav/webview_gui/assets/app.js")
raw = p.read_bytes()
lines = raw.split(b"\n")   # keepends 语义：join 还原逐字节
seg1 = b"\n".join(lines[:1006]) + b"\n"      # app.js      L1-1006
seg2 = b"\n".join(lines[1006:2820]) + b"\n"  # app-modal.js L1007-2820
seg3 = b"\n".join(lines[2820:])              # app-main.js  L2821-9830
assert seg1 + seg2 + seg3 == raw
p.write_bytes(seg1)
Path("subtransjav/webview_gui/assets/app-modal.js").write_bytes(seg2)
Path("subtransjav/webview_gui/assets/app-main.js").write_bytes(seg3)
```

**冻结 sha256（切分后逐一比对，任何偏差即停）**：

| 文件 | 行范围 | 字节数 | sha256 |
|---|---|---|---|
| app.js | L1–1006 | 58,699 | `a6ca418f606b7c753a759c499bc8181cafd9da6b2d1001648dc792baa8dfcc26` |
| app-modal.js | L1007–2820 | 92,754 | `4e987b4944251fc083b564ff94cc9a8b7a009c3b48f37852d98310f71b9b6707` |
| app-main.js | L2821–9830 | 318,745 | `067b0ec443bd83a9f75aa3854853c053de21bf578495eee3d71a95f912d9fc1f` |
| read_all() 拼接 | — | 470,198 | `787460b7db478e48e104616e91cc32ac852fb05e0d922da15ad6fd7c4a433533` |

### 2. index.html 接线（加载序 = JS_FILES = 原始定义序）

```html
<script src="app.js"></script>
<script src="app-modal.js"></script>
<script src="app-main.js"></script>
<script src="review.js"></script>
```

零构建经典脚本为硬约束（file:// 下 ES module 被 WebView2/CORS 拒载，D2026-1018-01 R-C）：**禁 `type="module"`、禁 import/export**。

### 3. tests/js_sources.py

`JS_FILES = ["app.js", "app-modal.js", "app-main.js"]`（每文件一个文件的顺序注释同步一句）。

### 4. tests/test_gui_js_static.py 钉更新

- `test_js_sources_layer_pinned`：① `JS_FILES == ["app.js", "app-modal.js", "app-main.js"]`；② `sha256(read_all().encode("utf-8")).hexdigest() == "787460b7db478e48e104616e91cc32ac852fb05e0d922da15ad6fd7c4a433533"`（docstring 同步一句）；③ 不动。
- 末尾新增 `test_js_split_integrity_pinned`（R-A 护栏，node 缺失时仍生效）：
  - 三文件各自 sha256 == 上表冻结值；
  - index.html 中 `src="app.js"` < `src="app-modal.js"` < `src="app-main.js"` 位置递增，且 `src="review.js"` 在 `src="app-main.js"` 之后（review.js 下位，不属本拆分家族）。

### 5. 先红后绿

1. 先落钉（`test_js_sources_layer_pinned` 新预期值 + `test_js_split_integrity_pinned`）→ 跑钉：**红**（JS_FILES 尚为 `["app.js"]`、新文件不存在）。
2. 落 js_sources.py + 三文件切分 + index.html → 全绿。红/绿输出原文贴执行记录。

## 验收命令

以下命令均在项目根目录执行：

```
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k "js_sources or js_split"
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py tests/test_strings_and_shortcut.py tests/test_ui_phase3_redlines.py tests/test_brand_allowlist.py -q
.venv/Scripts/python.exe -m pytest tests/ -q   # 全量，基线预期 2499 passed + 4 skipped（新钉 +1）
ruff check tests/js_sources.py tests/test_gui_js_static.py
```

## 约束（红线）

- **纯字节搬运**：零新增/改写/删除任何 JS 代码行（index.html 两行 script 与测试钉除外）。
- **守恒不变量**：`sha256(read_all())` 批1–3 恒为 `787460b7…3533`；批4（Refine）前才依 D2026-1016-05 Q3 门解冻。
- **禁清理 12 处既有 `window.__X` 赋值**（既有字节搬运非新增桥接，行号：L4759/6393/7124/7127/7421/7824/7826/7965/8368/9096/9112/9256，均落 app-main.js）；禁任何**新增** `window.X =` 赋值；禁清理任何 IIFE 钩子。
- **品牌**：新文件无 SubTransJAV 品牌头（切出字节本身零命中，勿添加任何新注释头）；禁扩 `test_brand_allowlist.py` ALLOWLIST。
- 函数不跨文件；MSG 键表单一归属（仍在 app.js 段1）；DOM 行为零变化。
- 三测试断言行/锚点串/`3600` 数字零改动（C2）。
- 执行者只 commit 不 push；GUI 黑盒验证由主审验收时执行，执行者自测限静态链。

## 执行记录（执行者填写）

（待填：改动文件清单 / 自测结果红绿原文 / 遗留问题）
