# d1017 卡0 · app.js 拆分前置：tests/js_sources.py 集中读取层（C0/C2/C4）+ 钉

> 以下命令均在项目根目录执行。依据：D2026-1016-05（3.1 阶段 3 动工评审，C0/C2/C4 条件落地卡）。分支 **refactor/appjs-split**。**卡面行号参考，执行以 re-grep 定位。**

## 目标

新增集中读取层 `tests/js_sources.py`，把三个静态测试对 app.js 的读取点改为经该层；`JS_FILES` 初始 `["app.js"]`，拼接视图与现 app.js **逐字节相等**；**断言本体零改动（C2）**；本卡**不拆任何代码**。

## 改动文件（4 个；拆分批为多文件卡，触点显式列出仅限这些——D2026-1016-05 已承认）

1. `tests/js_sources.py`（**新增**）
2. `tests/test_gui_js_static.py`（仅读取点 helper + node --check 用例遍历化 + 末尾新钉）
3. `tests/test_strings_and_shortcut.py`（仅读取点一行）
4. `tests/test_ui_phase3_redlines.py`（仅读取点一行）

## 改法

### 1. tests/js_sources.py（新增；文件头**不得**含 `SubTransJAV` 字样——C3）

```python
"""app.js 拆分批集中读取层（3.1 阶段 3 前置，D2026-1016-05 条件 C0）。

JS_FILES 顺序必须复现原始 app.js 文件内定义序（非仅依赖序）——
拼接视图 read_all() 是全部静态断言的文本等价物（C1）。
MSG 键表单一归属：msg_source() 返回含键表的那份文件文本（红线③）。
"""

from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "subtransjav" / "webview_gui" / "assets"

# 加载序 = index.html <script> 顺序 = 原始定义序；每批拆分随批更新本表
JS_FILES = ["app.js"]


def read_all() -> str:
    """依序拼接全部 JS 文件文本（JS_FILES=["app.js"] 时与 app.js 全文逐字节相等）。"""
    return "".join(
        (ASSETS / name).read_text(encoding="utf-8") for name in JS_FILES
    )


def msg_source() -> str:
    """返回含 ``const MSG = {`` 的那份文件文本；恰一份，多份/零份即 AssertionError。"""
    hits = [
        (ASSETS / name).read_text(encoding="utf-8")
        for name in JS_FILES
        if "const MSG = {" in (ASSETS / name).read_text(encoding="utf-8")
    ]
    if len(hits) != 1:
        raise AssertionError(f"const MSG 键表必须恰一份，现 {len(hits)} 份")
    return hits[0]
```

### 2. test_gui_js_static.py（三处）

- re-grep `APP_JS = ASSETS / "app.js"`（现 L22）：路径常量**保留**（node --check 用），文件头 import 区加 `import js_sources`（同目录模块，pytest 自动插 tests/ 至 sys.path；**若导入失败即停卡回报，不得自行 hack sys.path**）。
- re-grep `_app_js_source`（现 L27-28）：函数体 `return APP_JS.read_text(...)` 改为 `return js_sources.read_all()`。**仅此一行，其余零动。**
- re-grep `test_app_js_syntax_node_check`（现 L95 起）：`node --check` 对象由单个 app.js 改为**遍历 `js_sources.JS_FILES`** 各跑一次（C4；初始 ["app.js"] 行为等价，skip 语义保持）。
- 文件末尾新增钉 `test_js_sources_layer_pinned`：
  - ① `js_sources.JS_FILES == ["app.js"]`（现值锁定，后续拆分批随批更新本断言）；
  - ② `js_sources.read_all() == (ASSETS / "app.js").read_text(encoding="utf-8")` 逐字节相等；
  - ③ 三个测试文件源码均含 `js_sources`（接线防回潮：读 test_gui_js_static.py/test_strings_and_shortcut.py/test_ui_phase3_redlines.py 各自文件文本断言子串存在）。

### 3. test_strings_and_shortcut.py（一处）

- re-grep `_APP_JS_PATH`（现 L161）：`_APP_JS_PATH` 路径常量保留或删除均可，但其**读取行**（re-grep `_APP_JS_PATH.read_text`，现 L169 一带）改为 `js_sources.msg_source()`；`import js_sources` 加文件头 import 区。**断言与正则零改动。**

### 4. test_ui_phase3_redlines.py（一处）

- re-grep `JS = (_ASSETS / "app.js").read_text`（现 L25）：改为 `JS = js_sources.read_all()`；import 区加 `import js_sources`。**断言零改动。**

## 先红后绿

先写钉 `test_js_sources_layer_pinned` → ③ 必红（三测试尚未接线；①② 因实现同构暂绿属预期，红相以 ③ 为准）→ 落读取层+三处接线 → 全绿。红/绿输出原文贴执行记录。

## 验收命令

```
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k js_sources_layer
.venv/Scripts/python.exe -m pytest -q
ruff check tests/js_sources.py tests/test_gui_js_static.py tests/test_strings_and_shortcut.py tests/test_ui_phase3_redlines.py
git diff main --stat
```

末条预期：仅上列 4 文件变更。

## 约束（D2026-1016-05 硬条件）

- **C2**：三测试文件断言行/锚点字符串/`3600` 数字**零改动**——diff 仅允许 import 行、`_app_js_source` 函数体一行、node --check 用例遍历化、strings 读取行、redlines 读取行、末尾新钉。主审将逐行审 diff。
- **C3**：js_sources.py 无品牌词头；ALLOWLIST 条目数不变（`test_brand_allowlist.py` 必须绿）。
- **C0**：不拆任何代码；app.js/index.html/style.css 零改动。
- 全量测试 **2497+4 恒等**（不增不减——断言零改动下测试数必须不变）。
- 提交信息：`test(gui): app.js 拆分前置读取层 js_sources（d1017-卡0）`，正文含 `verify: 全量 2497+4 恒等+ruff 绿` 与 `Refs: D2026-1016-05`。
- 执行者只 commit 不 push；代码与 docs 执行记录拆两 commit。
- 完成后在本卡末尾追加执行记录。

---

## 执行记录（2026-10-17，执行者：OpenCode / DeepSeek V4.1 Flash Free）

### 一、改动文件（4，与卡面「改动文件」清单一致）

| 文件 | 改动 |
| --- | --- |
| `tests/js_sources.py` | **新增**：集中读取层 `ASSETS` / `JS_FILES = ["app.js"]` / `read_all()` / `msg_source()`；文件头零品牌词（C3） |
| `tests/test_gui_js_static.py` | +`import js_sources`；`_app_js_source()` 函数体**一行** → `js_sources.read_all()`；`test_app_js_syntax_node_check` 改**遍历 `js_sources.JS_FILES`**（skip 语义保持）；末尾新增钉 `test_js_sources_layer_pinned`（①JS_FILES 现值 ②read_all() 与 app.js 逐字节相等 ③三测试文件源码含 `js_sources`） |
| `tests/test_strings_and_shortcut.py` | +`import js_sources`；`_js_msg_keys()` 读取行 → `js_sources.msg_source()`（`_APP_JS_PATH` 常量按卡保留） |
| `tests/test_ui_phase3_redlines.py` | +`import js_sources`；`JS = js_sources.read_all()` |

`app.js` / `index.html` / `style.css` 零改动（C0）；三测试文件**断言行 / 锚点串 / `3600` 数字零改动**（C2）；未增删 ALLOWLIST 条目（C3，`test_brand_allowlist.py` 绿）；`import js_sources` 由 pytest rootdir 插 `tests/` 至 sys.path 生效，**未 hack sys.path**。

### 二、先红后绿（输出原文）

**红**（已落读取层 + 新钉，三处接线未落）：
```
$ .venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k js_sources_layer
F                                                                        [100%]
================================== FAILURES ===================================
________________________ test_js_sources_layer_pinned _________________________
...
        tests_dir = Path(__file__).resolve().parent
        for name in ("test_gui_js_static.py", "test_strings_and_shortcut.py",
                     "test_ui_phase3_redlines.py"):
            src = (tests_dir / name).read_text(encoding="utf-8")
>           assert "js_sources" in src, \
                f"{name} 未接线 js_sources 集中读取层（读取点回潮）"
E           AssertionError: test_strings_and_shortcut.py 未接线 js_sources 集中读取层（读取点回潮）
tests\test_gui_js_static.py:6796: AssertionError
=========================== short test summary info ============================
FAILED tests/test_gui_js_static.py::test_js_sources_layer_pinned - AssertionE...
1 failed, 202 deselected in 0.84s
```
红相落点 = ③（①② 因实现同构暂绿，与卡面「红相以 ③ 为准」一致）。

**绿**（三处接线落盘后）：
```
$ .venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k js_sources_layer
.                                                                        [100%]
1 passed, 202 deselected in 0.87s

$ .venv/Scripts/python.exe -m ruff check tests/js_sources.py tests/test_gui_js_static.py tests/test_strings_and_shortcut.py tests/test_ui_phase3_redlines.py
All checks passed!
```

### 三、逐字节等价证据（C0/C1）

```
$ .venv/Scripts/python.exe -c "import sys; sys.path.insert(0,'tests'); import js_sources as js; ..."
JS_FILES = ['app.js']
len(read_all()) = 399335 len(app.js) = 399335 逐字节相等 = True
msg_source() is app.js = True
```

### 四、验收命令实跑

```
$ .venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py tests/test_strings_and_shortcut.py tests/test_ui_phase3_redlines.py tests/test_brand_allowlist.py -q
258 passed in 5.00s

$ .venv/Scripts/python.exe -m pytest -q
2498 passed, 4 skipped, 2 warnings in 154.69s (0:02:34)

$ git diff main --stat
 tests/test_gui_js_static.py        | 33 +++++++++++++++++++++++++++++----
 tests/test_strings_and_shortcut.py |  3 ++-
 tests/test_ui_phase3_redlines.py   |  4 +++-
 3 files changed, 34 insertions(+), 6 deletions(-)
（另有卡面点名的**新增**文件 `tests/js_sources.py`，未跟踪时不出现在 `git diff` 里；入库后共 4 文件变更，域外零变更）
```

### 五、遗留问题 / 与卡面两处不符（如实上报，未自行放行）

1. **「全量 2497+4 恒等」与卡面末尾新钉自相矛盾**：卡面同时要求「全量测试 2497+4 恒等（不增不减）」与「文件末尾新增钉 `test_js_sources_layer_pinned`」；新钉必然使收集数 +1。实得 **2498+4**（基线 2497+4 的现有用例**零增删改**，skip 仍 4，唯一增量即卡面点名的新钉）。故提交正文未按卡面模板照抄「2497+4 恒等」，改为如实口径并注明差值来源，请主审裁定是否接受该口径或要求把新钉并进既有用例以凑「恒等」。
2. **`test_strings_and_shortcut.py` 读取点实际 3 处（卡面写「仅读取点一行 /（一处）」）**：re-grep `_APP_JS_PATH.read_text` 命中 **L172**（`_js_msg_keys`，MSG 键表）、**L200**（`test_js_msg_references_defined_in_table`，整文件 `MSG.x` 引用扫描）、**L350**（`_js_msg_value`，MSG 键值解析）。按 AGENTS.md「超出卡片范围的改动先停下来说明，不得顺手扩展」+ 卡面「一处」表述，本次**只接 L172 → `msg_source()`**，L200/L350 保留原读法，未擅自扩展。**建议**主审裁定补一版（本卡修订或并入首批拆分批）：`L350 → msg_source()`、`L200 → read_all()`——注意 L200 若误接 `msg_source()`，拆分后 `MSG.x` 引用分散于多文件时会**静默收窄断言面**。当前 `JS_FILES=["app.js"]` 下三者行为完全等价，不影响本卡绿相与等价性结论。
3. `test_gui_js_static.py` 的 `APP_JS` 常量按卡**保留**，但 node --check 遍历化后已不再由该用例使用，现仅被新钉 ② 复用（卡面「路径常量保留（node --check 用）」在遍历化后字面不成立）。若主审要求，可二选一：钉 ② 与卡面字面一致改回 `(ASSETS / "app.js")` 并删常量，或维持现状（常量保活）。
4. 域外未跟踪文件 `%TEMP%ci-logs.zip`、`.tokcheck` 为环境预存物，**未纳入本次提交**。
