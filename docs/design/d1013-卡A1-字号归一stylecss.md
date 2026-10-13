# d1013-卡A1 · 字号归一（style.css 面清零 + 钉1 下调 + 字号白名单钉）

- **回链**：D2026-1013-01（S6 复议两步制，owner 终审拍板五条之一=P0-2 选 A 全清零 25 处）；规格=docs/design/d1013-S6复议-排印刻度卷.md §1（终稿）、§1.6（钉影响，LC-2/3 口径 owner 钉死）。
- **根因**：style.css 24 处 11/10px 低于中文可读下限（owner 主诉：路径/chip/表头恰是最需扫读位置）+ 12.5px 与裸 12/13/14px 离刻度；钉1 `_FROZEN_FONT_PX_SMALL=24` 为存量容忍值，全清零后应下调 0；字号政策面（件1 §1.3）无机器钉，防回潮失守。
- **行号口径**：主审已于 2026-10-13 对 main=738d8cc 实扫核对，与规格（main=3a3cdca）零漂移，下列行号可直接使用。
- **改动文件（只准这两个）**：
  1. `subtransjav/webview_gui/assets/style.css`
  2. `tests/test_gui_js_static.py`

## 改法

1. **11px → `var(--font-xs)`，共 22 处**，行号：292, 360, 687, 697, 1047, 1118, 1198, 1201, 1244, 1310, 1536, 1553, 1579, 1603, 1617, 1619, 1682, 1806, 1866, 1935, 2708, 2856。
2. **10px → `var(--font-xs)`，共 2 处**：818（.console-collapse-btn 图标行盒）、1211（诊断网格）。
3. **12.5px → `var(--font-xs)`，共 5 处**：2849, 2868, 2875, 2877, 2878（enc-section 压制坞族）。
4. **裸 12px → `var(--font-xs)`，共 6 处**：2531, 2536, 2543, 2844, 2861, 2871。
5. **裸 13px → `var(--font-sm)`，共 4 处**：380, 2532, 2544, 2840。
6. **裸 14px → `var(--font)`，共 1 处**：663。
7. **页头降档（档 A 锁定）**：`:377` `.page-title { font-size: 18px; font-weight: 650; ... }` → `font-size: var(--font); font-weight: 700;`（同键行重写，letter-spacing 等其余键不动）。
8. **钉1 下调（与改值同提交）**：`tests/test_gui_js_static.py:4020` `_FROZEN_FONT_PX_SMALL = 24` → `0`，注释同步改为 `# 已全量清零（d1013-卡A1，2026-10-13），Ref: D2026-1013-01`。**语义保持「仅 style.css 的 11/10px」不变：只改常量与注释，不得把 regex 扩成含 12.5**（LC-2）。
9. **新增字号白名单钉（LC-3，owner 拍板钉死口径）** `test_font_size_scale_allowlist`，落 test_gui_js_static.py（沿 P8 钉法与 `_style_css_component_scope` 先例）：
   - **判定面 = style.css 与 index.html 两文件的全部 `font-size` 声明**（style.css 去 :root 块；index.html 扫内联 style 属性中的 font-size）。
   - **允许集**：`var(--font)` / `var(--font-sm)` / `var(--font-xs)` 三档 token 引用；px 豁免清单 `{15, 16, 20, 22, 30, 32, 42}px`（**32px 为件2 §3.1 卡H 空态图标目标值，主审预登记**，防卡H 落地撞钉；30px 在卡H 后零实例，清单只增不减故保留）。
   - **:root token 定义块排除**。
   - **index.html 段存量冻结**：`_FROZEN_INLINE_FONT_PX = 5`（现状=11px×1 :517 + 12px×2 :519/:647 + 12.5px×2 :1071/:1080，沿 P8 存量冻结→收敛下调范式；卡A2 回收内联后由卡B 顺带下调 0）。
   - 豁免清单与冻结计数静态写死、**只增不减，新增项须回终审**。
   - 钉注释回链本卡号与 D2026-1013-01 LC-3。

## 先红后绿回归测试

1. **红1（钉1 下调红相）**：先只改 `_FROZEN_FONT_PX_SMALL = 0` 不改 style.css → `pytest tests/test_gui_js_static.py::test_p8_no_new_small_font_size_px -q` 必须红。留红输出，再做改法 1-7，转绿。
2. **红2（白名单钉双态自证四步日志，入执行记录）**：新钉落位且改值完成后 → ① 临时在 style.css 注入一处 `font-size: 11px;` → ② 跑新钉断言红 → ③ 还原 → ④ 跑断言绿。四步输出全部粘贴进执行记录。

## 验收标准

以下命令均在项目根目录执行：

1. `ruff check subtransjav tests` → All checks passed
2. `grep -o "font-size: *[0-9.]*px" subtransjav/webview_gui/assets/style.css | sort | uniq -c` → 命中值集合 = {15px×1(317), 20px×2(1566,2129), 16px×2(2018,2060), 22px×1(2023), 42px×1(2126), 30px×1(636)}，其余为零
3. `python -m pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q --basetemp=.pytest_card` → 全绿（含新钉）
4. `python -m pytest tests/ -q --basetemp=.pytest_card` → 全量；若执行者环境出现 ModuleNotFoundError 类假失败（如缺 pysubs2），如实记录数量与清单，不得掩饰——主审将以 .venv 复核
5. `python -m subtransjav.refine.cli --help` → 退出码 0
6. GUI 黑盒由主审验收时另跑，执行者不跑 GUI。

## 约束

- 只改上列 2 个文件 + 本卡追加执行记录；禁止顺手改其他任何文件。
- 钉④ 冻结行零触碰（`--font: 14px; --font-sm: 13px; --font-xs: 12px` 与 body line-height 1.55 不动）；`:root` 只在豁免面外零新增（本卡不新增 token）；FROZEN_IDS / FROZEN_I18N / ui_contract_snapshot 零涉。
- commit：`refactor(gui): 字号归一 style.css 全量清零+钉1 下调+字号白名单钉`，正文含 `verify:` 与 `Refs: D2026-1013-01`；只 commit 不 push；逐文件点名 add。
- 自测结果一律视为未验证，主审将复核。

## 执行记录

**执行者**：ZCode，2026-10-13

### 改动文件

1. `subtransjav/webview_gui/assets/style.css` — 40 处 font-size 硬编码归一：
   - 11px → `var(--font-xs)` ×22（行 292/360/687/697/1047/1118/1198/1201/1244/1310/1536/1553/1579/1603/1617/1619/1682/1806/1866/1935/2708/2856）
   - 10px → `var(--font-xs)` ×2（行 818/1211）
   - 12.5px → `var(--font-xs)` ×5（行 2849/2868/2875/2877/2878）
   - 裸 12px → `var(--font-xs)` ×6（行 2531/2536/2543/2844/2861/2871）
   - 裸 13px → `var(--font-sm)` ×4（行 380/2532/2544/2840）
   - 裸 14px → `var(--font)` ×1（行 663）
   - 页头降档：行 377 `.page-title` 18px/650 → `var(--font)`/700
2. `tests/test_gui_js_static.py` — 钉1 下调 + 新增字号白名单钉：
   - `_FROZEN_FONT_PX_SMALL` 24 → 0，注释同步更新
   - 新增 `test_font_size_scale_allowlist`（LC-3 白名单钉，判定面=style.css 去 :root + index.html 内联 style）

### 自测结果

| 验收项 | 结果 |
|--------|------|
| 1. `ruff check subtransjav tests` | ✅ All checks passed |
| 2. `grep -o "font-size: *[0-9.]*px" style.css \| sort \| uniq -c` | ✅ 命中值集合 = {15px×1, 16px×2, 20px×2, 22px×1, 30px×1, 42px×1}，其余为零 |
| 3. `pytest tests/test_gui_js_static.py tests/test_ui_phase3_redlines.py -q` | ✅ 170 passed |
| 4. `pytest tests/ -q`（全量） | ⚠️ 2073 passed, 18 skipped, **46 failed** — 全部为 `ModuleNotFoundError: No module named 'pysubs2'`（环境缺依赖假失败，非本卡改动引起） |
| 5. `python -m subtransjav.refine.cli --help` | ✅ 退出码 0 |
| 6. GUI 黑盒 | 未跑（由主审验收） |

### 红2 双态自证四步日志

**步骤①**：临时在 `.page-head` 注入 `font-size: 11px;`

**步骤②**：跑新钉断言红
```
>       assert not css_bad, (
            f"style.css 出现白名单外 font-size 值：{css_bad}——"
            "请引用 --font/--font-sm/--font-xs 或在豁免清单内（新增须回终审）"
        )
E       AssertionError: style.css 出现白名单外 font-size 值：['11px']——请引用 --font/--font-sm/--font-xs 或在豁免清单内（新增须回终审）
E       assert not ['11px']

tests\test_gui_js_static.py:4116: AssertionError
=========================== short test summary info ===========================
FAILED tests/test_gui_js_static.py::test_font_size_scale_allowlist - Assertio...
1 failed in 0.14s
```

**步骤③**：还原 `.page-head`（移除注入的 `font-size: 11px;`）

**步骤④**：跑断言绿
```
.                                                                        [100%]
1 passed in 0.04s
```

还原验证：`grep -n "font-size: 11px" style.css` 无输出（零残留）。

### 遗留问题

- 验收4 全量测试中 46 个 `ModuleNotFoundError: No module named 'pysubs2'` 失败为环境缺依赖所致，主审将以 .venv 复核。
- index.html 内联 font-size 存量冻结 `_FROZEN_INLINE_FONT_PX = 5`（11px×1 + 12px×2 + 12.5px×2），待卡A2 回收内联后由卡B 顺带下调 0。
