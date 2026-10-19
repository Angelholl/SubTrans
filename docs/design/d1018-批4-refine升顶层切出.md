# d1018-批4：Refine IIFE 去壳升顶层 + 15 块切出（执行卡）

> **以下命令均在项目根目录执行**（执行者以仓库根为 cwd；卡面不写根路径字面量，D2026-1012-03）。
> 决策依据：D2026-1016-05（末批 Refine）／D2026-1018-01（守恒钉、C2 审痕面、Q3）／D2026-1018-02（O2、风险③）／
> **D2026-1019-01**（本方案拍板：升顶层 + 去壳载荷钉 + `app-modal.js` 永久单块 + `AppState/UIHelpers` 不迁移）。
> 勘探与数字来源：`docs/design/d1019-批4-勘探报告.md`；方案与候选取舍：`docs/design/d1019-批4-方案书.md`。

## 一、起点（开工前先核，不符即停）

| 项 | 期望值 | 复核 |
|---|---|---|
| 分支 / HEAD | `refactor/appjs-split` / `1eb262c` | `git rev-parse --abbrev-ref HEAD`；`git log --oneline -1` |
| 工作树 | 仅 `%TEMP%ci-logs.zip`、`.tokcheck` 两笔无关未跟踪项 | `git status --short` |
| 旧守恒钉 | `sha256(read_all())` = `787460b7db478e48e104616e91cc32ac852fb05e0d922da15ad6fd7c4a433533`，470,198B | 下方① |
| `app-main.js` | 204,060B，sha256 `ea558c8ee9232dd74dc0d4bcedb11e7fc07c4041462286bcbaca4b6662a329f4` | `Get-FileHash` 或 python |
| 定向基线 | 259 passed | 下方③ |
| 全量基线 | 本机 2509+5／主审机 2510+4 | 下方⑤ |

```
# ① 旧钉
.venv/Scripts/python.exe -c "import sys,hashlib; sys.path.insert(0,'tests'); import js_sources; t=js_sources.read_all(); print(len(t.encode('utf-8')), hashlib.sha256(t.encode('utf-8')).hexdigest())"
```

## 二、触点（只允许改这些文件；超出即停）

1. `subtransjav/webview_gui/assets/app-main.js`（阶段 A 改写；阶段 B 逐块缩减；末块改名）
2. `subtransjav/webview_gui/assets/app-refine-*.js`（**15 个新文件**，见 §五表）
3. `subtransjav/webview_gui/assets/index.html`（只动 `<script src>` 块）
4. `tests/js_sources.py`（只动 `JS_FILES` 列表与其行注释）
5. `tests/test_gui_js_static.py`（两处随批钉数据 + 三处文案（阶段0）+ 一处断言行重写 + 两条新钉）
6. 本卡末尾「执行记录」（只追加）

**禁改**：`app.js`／`app-msg.js`／`app-modal.js`（字节全批不变）；`review.js`；`style*.css`；`packaging/*`；`pyproject.toml`；`spike/*`；CI。

## 三、阶段 0（仅当拍板点 P7 选 A）：先清凭据判据误拦

单笔提交，只改 `tests/test_gui_js_static.py` 的三处**文案**（不动断言逻辑、不动正则、不动期望值）：

| 位置 | 现文案特征 | 改为 |
|---|---|---|
| :4111 注释 | 英文 token 一词后接等号再接占位符 | `# border-radius 硬编码非 token 档（档位占位符已移除）` |
| :6125 断言消息 | 英文 token 一词后接冒号再接插值占位 | `…缺少 P0-5 语义变量：{pat}` |
| :6129 断言消息 | 同上（dark） | 同上 |

提交：`chore(test): d1018-批4 前置——改写三处触发凭据判据的断言文案`
验收：`.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q` → 与起点同绿（用例数不变）。

## 四、阶段 A：去壳升顶层（1 笔提交，非纯搬运，唯一一次）

### A.1 改动（只动 `app-main.js`，全部用**唯一锚点**定位，禁止用行号）

1. **删壳开**：删除唯一行 `(function () {`。
2. **删重入守卫**：删除唯一行 `  if (window.__refineUI) return;`。
   **保留** `  window.__refineUI = true;`（12 处 dunder 红线；拍板点 P3-A）。
3. **删壳闭**：删除文件末尾唯一行 `})();`（其后仅空行）。
4. **搬一行**：把唯一行 `  TranslatorManager.guideAutoDetect = guideAutoDetect;` **整行剪出**，
   原样插入到 `  function guideAutoDetect() {` / `    guideLoad(true);` / `  }` 三行之后的下一行。
   ——理由：升顶层后函数声明只提升到本脚本；不搬则 `app-refine-core.js` 求值到该行抛 `ReferenceError`，
   `app-translator.js:362` 的 `typeof` 守卫会静默跳过「翻译完成后自动探测」。
5. **其余字节零改动**：缩进、空行、注释一律不动（**禁格式化**）。

### A.2 验收（先红后绿，红/绿原文入执行记录）

```
# ② 新钉值（去壳后应恒为此值；阶段A之前先改钉再跑=红）
.venv/Scripts/python.exe -c "import sys,hashlib; sys.path.insert(0,'tests'); import js_sources; t=js_sources.read_all(); print(len(t.encode('utf-8')), hashlib.sha256(t.encode('utf-8')).hexdigest())"
# 期望：204006 6051c666d37bf1a11b17064c1478ff91ea139860374b9e1c1f679602e546fe33

node --check subtransjav/webview_gui/assets/app-main.js

# ③ 独立复算（防「改字节再同步改钉」）：从起始提交重算配方，不得用工作区产物
git show 1eb262c:subtransjav/webview_gui/assets/app-main.js > artifacts/app-main.before.js
# 对上述临时文件跑勘探 §二 的配方 → 必须 204006 / 6051c666…；且与 read_all() 实算相等
```

### A.3 同笔测试改动（**必须逐字**）

1. `test_js_sources_layer_pinned`：`read_all()` 期望值 `787460b7…3533` → `6051c666…fe33`；
   docstring 追加「批4 去壳载荷钉；旧钉 787460b7…（470,198B）已退役」。
2. `test_js_split_integrity_pinned`：`frozen["app-main.js"]` → `(204006, "6051c666d37bf1a11b17064c1478ff91ea139860374b9e1c1f679602e546fe33")`。
3. `tests/js_sources.py`：`"app-main.js"` 行注释改为「原 L1936-6293：Refine 去壳单块（批4-A；批4-B 起逐块切出）」（仅注释）。
4. `test_startup_chain_not_killed_by_scope_leak` **只改断言 2**，其余三条断言逐字不动。替换为：

```python
    # 断言2 钉作用域审计（批4 去壳后重写，D2026-1019-01）：Refine 私有助手 $ 已升为顶层函数，
    # 但仍只允许 refine 家族消费——全库 $(' 出现必须全部落在「refine 家族 + 过渡期剩余 app-main」。
    family = [n for n in js_sources.JS_FILES
              if n.startswith("app-refine-") or n == "app-main.js"]
    total = source.count("$('")
    inner = sum((ASSETS / n).read_text(encoding="utf-8").count("$('")
                for n in family)
    assert total > 0, "自证失败：未提取到任何 $(' 出现（判据失效）"
    assert total == inner, (
        "refine 家族外出现 $(' 引用（跨模块耦合）："
        f"全库 {total} 处，家族内仅 {inner} 处"
    )
```

> 该式对中间态**单调成立**：阶段 A 全家在 `app-main.js`；第 k 块后分散在 k 个新文件 + `app-main.js` 剩余段；
> 第 15 块后 `app-main.js` 已不存在，只剩 15 个 `app-refine-*.js`（终态另由 `test_refine_family_deshell_pinned` 钉死）。

### A.4 提交

```
refactor(gui): d1018-批4 Refine IIFE 去壳升顶层（+1 行重排）

- 删壳开/重入守卫/壳闭 3 行；window.__refineUI 标记保留（12 dunder 红线）
- TranslatorManager.guideAutoDetect 挂接行搬到 guideAutoDetect 声明后（升顶层唯一前向引用）
- 守恒钉换代：787460b7…(470198B) → 6051c666…(204006B)
verify: 载荷钉 6051c666…（204006B）；node --check rc=0；定向套件 259 passed；全量与本机基线逐项相等（本机 2509+5／主审机 2510+4）
Refs: D2026-1016-05, D2026-1018-01, D2026-1018-02, D2026-1019-01
```

## 五、阶段 B：15 块逐块切出（14 笔切块 + 1 笔改名）

### B.1 每块执行式（5 个文件，逐文件点名 add）

块 k（k=1..15）的字节 = **从本块首行（含）到下一块首行（不含）**（第 15 块到文件末）。

1. 新建 `assets/<新文件>`：写入上述切片（UTF-8、LF、无 BOM）。
2. `app-main.js`：删除刚切走的字节前缀（第 15 块为纯改名，见 B.4）。
3. `index.html`：在 `<script src="app-main.js"></script>` **之前**插入 `<script src="<新文件>"></script>`。
4. `tests/js_sources.py`：在 `"app-main.js",` **之前**插入 `    "<新文件>",  # 原 app-main.js L<a>-<b>：<块名>（批4）`。
5. `tests/test_gui_js_static.py`：
   - `test_js_sources_layer_pinned` 的 `JS_FILES` 现值列表插入同名；
   - `test_js_split_integrity_pinned` 的 `frozen` 增加 `"<新文件>": (<bytes>, "<sha256>")`，并更新 `"app-main.js"` 的新 size/sha；
   - 同钉 index 顺序元组插入同名。
   **断言本体零改动**（C2 审痕面：这两钉属随批更新钉，新值全部在本卡 §五表写死，验收逐行对照）。

### B.2 15 块坐标与冻结值（sha256 全值）

| # | 新文件 | 首行锚点（用于切点定位） | 字节 | sha256 |
|---|---|---|---|---|
| 1 | `app-refine-core.js` | `// ===== Refine UI：模型刷新/测试 + 词库表格编辑器 + 角色卡编辑器 =====` | 7,401 | `332e810e3760a891eb6f20c92cd24461dd4cf2f8ab808e15fc306a2f1718d7f9` |
| 2 | `app-refine-models.js` | `  // ---- 已存模型名（批2 D2026-1002-12 拍板点2：删 custom-model-1/2 前端` | 13,345 | `1cfcd67bd02664ce6dde64d87d9b4c3ee023b42d6d81bbc13c2417b73f7321c2` |
| 3 | `app-refine-glossary.js` | `  // P2（D2026-1008-02）：修复模型独立配置行随「修复=分析模型完全统一」` | 6,588 | `5836d3481b3b20b6d49933559c9893b719621e003cd46890c34b99f708a24516` |
| 4 | `app-refine-templates.js` | `  // ---- 角色卡编辑器 ----` | 9,297 | `10f95ce8f11589d91e394029d82f21e312206e1293fdfd205f1658a97813150c` |
| 5 | `app-refine-settings.js` | `  async function pickDir() {` | 19,255 | `20907b96509e55835dcae5f1790519c880069d2f4f4dad0d705a2524941e1c55` |
| 6 | `app-refine-guide.js` | `  // ---- 质量报告导读查看器（W1b：仅读 *_质量报告导读.json，不读 txt/全量 json）----` | 26,042 | `60debeb42e15fd1fc8f98f6707472597aca2f7fe45130dc62a5b7cf29f30d4c9` |
| 7 | `app-refine-preview.js` | `  // ============================================================` ＋次行 `  // 试听错误槽（2.7.4 件1 owner 终版裁定）：错误展示从浮层条内迁出为` | 14,493 | `2847f1ca77bfcc313d1383a47df86d14797f47b9b33f42c54c5131b52b20947b` |
| 8 | `app-refine-ai.js` | `  // ============================================================` ＋次行 `  // AI 质量分析（D2026-0929：--ai-analyze 前后端接入）` | 14,303 | `ce941f6b1605d221321a52daaaf9e896b7ce64d570fd1125d8913a1219792de9` |
| 9 | `app-refine-batchfix.js` | `  async function refineAiAnalyze() {` | 25,976 | `fb802a9b43e509aad696be184fd8b16fd925da89ae6f577dab00665ccfd1ea4a` |
| 10 | `app-refine-asr.js` | `  // ===== 2.6.0 批3（D2026-1002-04-批3）：ASR 模型管理 =====` | 5,258 | `24da1757e9defaba78ccb935e7708497ba8ac6b948ae79bee787ab70247b7776` |
| 11 | `app-refine-ai-actions.js` | `  function aiBtnState(btn, statusText) {` | 5,166 | `5ef94c67fa6d630a863f4e35bbc9719c264e23b84fbc20f47f659d5cccca30fb` |
| 12 | `app-refine-bind.js` | `  // ---- 性暗示词替换（legacy 功能，已随 legacy 管线删除）----` | 17,170 | `a0711b0f7de046555bdced38c8b7aabb7b70e5867b0378464918476ab799bb39` |
| 13 | `app-refine-dataroot.js` | `  // ---- 数据保存目录（高级参数页；pointer 写入 .data-root，重启应用后生效）----` | 2,310 | `45f55c77c352b1dbada53060a312d75211319dab09c117574051603e50eaff85` |
| 14 | `app-refine-dict.js` | `  // ---- 词典管理（2.1 引擎页三区块：日/中/英 状态/下载/路径）----` | 34,748 | `5d1051662e0a97863e54ba187faa960e0ce2d966ccb6d7a5e855d77d18d98609` |
| 15 | `app-refine-boot.js` | `  // ---- 首启数据目录引导（批1b 件4）：frozen-only，哨兵防再弹 ----` | 2,654 | `53c979ce29549a397f52b7507ecb9b2bcac88df997e06dc641138544f3243c77` |
| — | 合计 | — | **204,006** | `6051c666d37bf1a11b17064c1478ff91ea139860374b9e1c1f679602e546fe33` |

> 第 7、8 块首行是 `// ====` 分隔线，**分隔线随块走**；用「首行+次行」双锚点定位，避免与文件中其它分隔线混淆。
> 每块完成后 `app-main.js` 必须等于「剩余后缀」；任何偏差由载荷钉兜底（必红）。

### B.3 每块验收（逐块跑，失败即停）

```
# ① 载荷钉（恒 6051c666… / 204006）
.venv/Scripts/python.exe -c "import sys,hashlib; sys.path.insert(0,'tests'); import js_sources; t=js_sources.read_all(); print(len(t.encode('utf-8')), hashlib.sha256(t.encode('utf-8')).hexdigest())"

# ② 三钉 + node 遍历
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py -q -k "js_sources or js_split or node_check or refine_family or global_surface"

# ③ 四文件定向套件（起点 259 passed；第 15 块后 261 passed）
.venv/Scripts/python.exe -m pytest tests/test_gui_js_static.py tests/test_strings_and_shortcut.py tests/test_ui_phase3_redlines.py tests/test_brand_allowlist.py -q

# ④ 新文件语法
node --check subtransjav/webview_gui/assets/<新文件>.js

# ⑤ 新文件品牌零命中（产品面 default-deny）
.venv/Scripts/python.exe -c "from pathlib import Path; p=Path('subtransjav/webview_gui/assets/<新文件>.js'); print('SubTransJAV' in p.read_text(encoding='utf-8'))"
```

### B.4 第 15 块（改名，不是切块）

前置：第 14 块后 `app-main.js` 应恰等于第 15 块（2,654B / `53c979ce…`）。若不等，停。

1. `git mv subtransjav/webview_gui/assets/app-main.js subtransjav/webview_gui/assets/app-refine-boot.js`
2. `index.html`：`app-main.js` 的 `<script>` 行改为 `app-refine-boot.js`（位置不变）。
3. `tests/js_sources.py`：`"app-main.js"` 行改为 `"app-refine-boot.js"`（行注释改「原 app-main.js L4301-4360：引导/loadRemote/启动（批4）」）。
4. `tests/test_gui_js_static.py`：`frozen` 删 `app-main.js` 条目、加 `app-refine-boot.js`；`JS_FILES` 现值与顺序元组同步。
5. **同一笔**加入下方「两条新钉（逐字）」（此时 15 文件齐备，应直接绿；若红，按错误修真，不得放宽断言）。

两条新钉（逐字）：

```python
def test_refine_family_deshell_pinned():
    """批4 去壳钉（D2026-1019-01）：Refine 家族 15 文件已脱离 IIFE 壳，且每个文件在 index.html 恰加载一次。"""
    refine = [n for n in js_sources.JS_FILES if n.startswith("app-refine-")]
    assert len(refine) == 15, f"Refine 家族应为 15 个分文件，实为 {len(refine)}"
    assert "app-main.js" not in js_sources.JS_FILES, "app-main.js 应已并入 refine 家族"
    html = INDEX_HTML.read_text(encoding="utf-8")
    for name in refine:
        src = (ASSETS / name).read_text(encoding="utf-8")
        assert "(function () {" not in src, f"{name} 残留 IIFE 壳开"
        assert "\n})();" not in src, f"{name} 残留 IIFE 终结行"
        assert html.count(f'src="{name}"') == 1, f"{name} 在 index.html 出现次数 != 1"


# 批4 全局面冻结名单（172 个；末次变更=批4 去壳升顶层）
_REFINE_TOP_NAMES = frozenset({
    "$", "AI_CLOUD_PROVIDERS", "ASR_SOURCE_LABELS", "DICT_KINDS", "DICT_KIND_DISPLAY_ORDER",
    "DICT_STOP_GRACE_MS", "FULLCHAIN_SCOPE_NOTE", "GUIDE_ITEMS_MODAL_TITLE",
    "GUIDE_ITEMS_OPEN_BTN_LABEL", "GUIDE_SUFFIX", "MODEL_REFRESH_SVG", "REFINE_PROVIDER_URLS",
    "__warmupInflight", "_dictBusyKind", "_dictCustomDir", "_dictDirCache", "_dictEnsureHint",
    "_dictEnsureKindRow", "_dictNeedsMigration", "_dictOldDir", "_dictRefreshHint",
    "_dictRefreshKindRow", "_dictSourcesCache", "_dictStatusCache", "_dictStopPending",
    "_dictStopRequestedAt", "aiActionBtn", "aiApplyFail", "aiApplyGlossary", "aiApplyTm",
    "aiBtnState", "aiConflictBadge", "aiEditBtn", "aiEditTm", "aiModelApplyFollowState",
    "aiRenderResult", "aiReportPath", "aiRestoreBtn", "aiRestoreTm", "aiStatus",
    "aiUpdateTmTarget", "analyzeResolution", "applyProviderEndpoint", "applySavedStageSettings",
    "applyServiceQuickProvider", "asrApplyEnvStatus", "asrOpenModelsPanel", "asrRefresh",
    "asrStatus", "attachPreviewSeekListeners", "batchFixRefresh", "batchFixRun",
    "bfRefreshEffective", "bfStatus", "bindCleanerDirControls", "bindDirectionControls", "bindDom",
    "buildRefineOptions", "clearPreviewError", "closeAudioPreview", "dataRootBrowse",
    "dataRootLoad", "dataRootSave", "dataRootSourceLabel", "detachPreviewSeekListeners",
    "dictDownload", "dictFailureText", "dictLoad", "dictMigrate", "dictPickDir",
    "dictRenderDetail", "dictRequestStop", "dictRestoreDir", "dictShowStatus",
    "ensureGuideStatusLine", "ensurePreviewErrorSlot", "ensurePreviewLoadingNote", "esc", "fcFmt",
    "fileUrlOf", "fmtGB", "fullchainRollbackRun", "fullchainStatusRefresh", "glAdd", "glDel",
    "glExport", "glImport", "glLearnedLoad", "glLoad", "glRender", "glRows", "glSave", "glStatus",
    "guideAutoDetect", "guideCopyPath", "guideCustomStatus", "guideItemCardHtml", "guideLoad",
    "guidePath", "guideRender", "guideRenderTxt", "guideStalenessCheck", "guideStatus",
    "inferredMediaCache", "isAiCloudProvider", "lastActionItems", "lastAiSuggestions",
    "lastAsrProbe", "lastGuideData", "lastLoadedGuideMtime", "lastLoadedGuidePath",
    "lastLoadedIsTxt", "lastLoadedReportTxtPath", "lastPreviewTiming", "lastPreviewToken",
    "loadRemote", "markInferredMedia", "maybeShowDataGuide", "mediaMissingHint",
    "mediaOverridePath", "modelEmptyOptionHTML", "openAudioPreview", "openDir",
    "openGuideItemsModal", "openTplEditor", "pickCleanerDir", "pickDir",
    "pickPreviewMediaManually", "previewArmStop", "previewPendingSeek", "previewSeekGen",
    "previewSeekHandlers", "readPositiveInt", "readRefineConcurrency", "readRefineCtx",
    "refineAiAnalyze", "refreshAnalysisModels", "refreshFallbackModels", "refreshModels",
    "refreshServiceQuickRow", "refreshTrioSelect", "rematchPreviewMedia", "renderMediaTag",
    "saveCleanerDir", "saveStageEndpoints", "saveStageKey", "savedAiModel", "savedStageModels",
    "showPreviewError", "stageEndpoint", "stageEndpointFor", "stageKeyFor", "stageKeyOrNull",
    "stageStatus", "syncServiceQuickFromStages", "testAnalysisModel", "testStage", "testTrioModel",
    "timingToSeconds", "tmOriginalSeed", "tmOriginalTargets", "tmResolveEntry", "tplDirState",
    "tplGotoEdit", "tplLoad", "tplRefreshSelect", "tplRenderDatalist", "tplRenderOptions",
    "tplSave", "trioStatus", "updateMediaSourceBar", "warmupMaybeStart",
})


def test_refine_global_surface_pinned():
    """批4 全局面钉（D2026-1019-01）：Refine 15 文件顶层声明集合 == 冻结的 172 个名字，且与其余分文件零重名。"""
    pat_fn = re.compile(r"^  (?:async )?function\s+([A-Za-z_$][\w$]*)\s*\(")
    pat_var = re.compile(r"^  (?:const|let|var)\s+([A-Za-z_$][\w$]*)")
    refine_names = []
    for name in (n for n in js_sources.JS_FILES if n.startswith("app-refine-")):
        for line in (ASSETS / name).read_text(encoding="utf-8").split("\n"):
            m = pat_fn.match(line) or pat_var.match(line)
            if m:
                refine_names.append(m.group(1))
    assert len(refine_names) == len(set(refine_names)), "Refine 家族顶层声明存在重名"
    assert set(refine_names) == _REFINE_TOP_NAMES, (
        "Refine 顶层声明集合漂移："
        f"新增 {sorted(set(refine_names) - _REFINE_TOP_NAMES)}；"
        f"缺失 {sorted(_REFINE_TOP_NAMES - set(refine_names))}"
    )
    others = []
    for name in js_sources.JS_FILES:
        if name.startswith("app-refine-"):
            continue
        for line in (ASSETS / name).read_text(encoding="utf-8").split("\n"):
            m = (re.match(r"^(?:async )?function\s+([A-Za-z_$][\w$]*)\s*\(", line)
                 or re.match(r"^(?:const|let|var)\s+([A-Za-z_$][\w$]*)", line))
            if m:
                others.append(m.group(1))
    assert not (set(refine_names) & set(others)), \
        f"顶层声明跨文件重名（经典脚本会 SyntaxError）: {sorted(set(refine_names) & set(others))}"
```

> 两条新钉**不得提前到阶段 A 加入**：`refine` 家族在阶段 B 结束前不齐，提前加会长期红。

## 六、阶段 C：终态验收（主审复核用）

```
.venv/Scripts/python.exe -c "import sys,hashlib; sys.path.insert(0,'tests'); import js_sources; t=js_sources.read_all(); print(len(t.encode('utf-8')), hashlib.sha256(t.encode('utf-8')).hexdigest())"
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m ruff check tests/
node --check <34 个文件逐个>
```

| 项 | 期望 |
|---|---|
| 载荷钉 | `6051c666…fe33`（204,006B） |
| 全量 | 2512+4（主审机）／2511+5（本机，ISCC 缺席） |
| 定向 | 261 passed |
| ruff | All checks passed（`spike/` 8 处基线不碰） |
| 品牌 | 15 新文件 `SubTransJAV` 零命中；`docs/design/**` 豁免不入判定面 |
| 零构建 | 34 个 `JS_FILES` 的 `import`/`export`/`type=module` 零命中；`index.html` 共 **35 个 `<script>`**（34 + `review.js`） |
| window 赋值 | 仍 12 dunder 全仓（`__refineUI` 保留）+ `AppDictKindsCount`；**零新增** |
| `app-modal.js` | 92,754B `4e987b49…b6707` 未动 |
| 单 revert | `git revert --no-commit <起点>..HEAD` 后 `git diff <起点> --stat` 为空（整批可回） |

## 七、红线（违反任一即失败）

1. 载荷钉去壳后每块恒为 `6051c666…fe33`（204,006B）；旧钉 `787460b7…` 只在阶段 A 之前成立。
2. 阶段 A 只允许：删 3 行 + 搬 1 行；其余字节零改动（含缩进/空行/注释）。
3. 函数不跨文件：切点只能是顶层完整语句（区头注释随块走）；块内不得出现半个函数。
4. `app.js`／`app-msg.js`／`app-modal.js` 零字节改动；`MSG` 单一归属不变。
5. 新文件禁 `import`/`export`/`type=module`；禁品牌头；**禁新增 `window.X =` 文本**；禁清理既有钩子。
6. 重入守卫删除后**不再支持重复加载**：同一文件被写两次会因 `const` 重复声明抛 `SyntaxError`；`index.html`「每文件恰 1 次」由新钉守住。
7. 不 push、不改 `main`、不碰 `spike/`、不扩品牌 ALLOWLIST、不动版本号与 CI。
8. 除阶段 A 的 3 删 1 搬外，不改任何逻辑；发现问题只登记，不动手。
9. 每笔提交逐文件点名 add；禁 `git add -A`。

## 八、勾账栏（执行者逐块滚动填写）

| 块 | 文件 | 字节 | sha256（前16） | 载荷钉 | 定向 | node | commit |
|---|---|---|---|---|---|---|---|
| A | 去壳升顶层 | 204,006 | `6051c666d37bf1a1` | ✓（先红后绿） | ✓ 259 | ✓ rc=0 | fd6ee8a |
| 1 | `app-refine-core.js` | 7,401 | `332e810e3760a891` | ✓ | ✓ 259 | ✓ rc=0 | cd4342f |
| 2 | `app-refine-models.js` | 13,345 | `1cfcd67bd02664ce` | ✓ | ✓ 259 | ✓ rc=0 | 28669c7 |
| 3 | `app-refine-glossary.js` | 6,588 | `5836d3481b3b20b6` | ✓ | ✓ 259 | ✓ rc=0 | 1005e72 |
| 4 | `app-refine-templates.js` | 9,297 | `10f95ce8f11589d9` | ✓ | ✓ 259 | ✓ rc=0 | 794cc3e |
| 5 | `app-refine-settings.js` | 19,255 | `20907b96509e5583` | ✓ | ✓ 259 | ✓ rc=0 | 0689bb0 |
| 6 | `app-refine-guide.js` | 26,042 | `60debeb42e15fd1f` | ✓ | ✓ 259 | ✓ rc=0 | 3618019 |
| 7 | `app-refine-preview.js` | 14,493 | `2847f1ca77bfcc31` | ✓ | ✓ 259 | ✓ rc=0 | 30efd76 |
| 8 | `app-refine-ai.js` | 14,303 | `ce941f6b1605d221` | ✓ | ✓ 259 | ✓ rc=0 | e84bf84 |
| 9 | `app-refine-batchfix.js` | 25,976 | `fb802a9b43e509aa` | ✓ | ✓ 259 | ✓ rc=0 | 55d2a7c |
| 10 | `app-refine-asr.js` | 5,258 | `24da1757e9defaba` | ✓ | ✓ 259 | ✓ rc=0 | 3d3cfbd |
| 11 | `app-refine-ai-actions.js` | 5,166 | `5ef94c67fa6d630a` | ✓ | ✓ 259 | ✓ rc=0 | e490449 |
| 12 | `app-refine-bind.js` | 17,170 | `a0711b0f7de04655` | ✓ | ✓ 259 | ✓ rc=0 | 00aad55 |
| 13 | `app-refine-dataroot.js` | 2,310 | `45f55c77c352b1db` | ✓ | ✓ 259 | ✓ rc=0 | 0cff421 |
| 14 | `app-refine-dict.js` | 34,748 | `5d1051662e0a9786` | ✓ | ✓ 259 | ✓ rc=0 | 2865d88 |
| 15 | `app-refine-boot.js`（改名） | 2,654 | `53c979ce29549a39` | ✓ | ✓ 261 | ✓ rc=0 | f9f4ce3 |

## 九、执行记录（执行者追加于此）

### 执行轮次与提交清单（17 笔，含阶段 0；执行者只 commit 未 push）

| 笔 | commit | 内容 | 触点 | 纯搬运 |
|---|---|---|---|---|
| 0 | `2889ac5` | chore(test) P7 三处文案改写 | tests/test_gui_js_static.py | 文案（无逻辑改动） |
| A | `fd6ee8a` | 去壳升顶层（删 3 行 + 搬 1 行） | app-main.js + js_sources.py + test_gui_js_static.py | **否**（唯一一次非纯搬运） |
| 1-14 | `cd4342f` `28669c7` `1005e72` `794cc3e` `0689bb0` `3618019` `30efd76` `e84bf84` `55d2a7c` `3d3cfbd` `e490449` `00aad55` `0cff421` `2865d88` | 逐块切出 core/models/glossary/templates/settings/guide/preview/ai/batchfix/asr/ai-actions/bind/dataroot/dict | 每笔 5 文件：新文件 + app-main.js + index.html + js_sources.py + test_gui_js_static.py | 是（字节恒等） |
| 15 | `f9f4ce3` | app-main.js 纯 git mv → app-refine-boot.js + 两条新钉 | 改名对 + index.html + js_sources.py + test_gui_js_static.py | 改名零改 + 新增钉 |

### 自测结果（关键红绿原文）

- 载荷钉（家族拼接：refine 家族 + 过渡期 app-main.js）：去壳提交起每笔恒 `204006 / 6051c666…fe33`，终态 15 文件同值；独立复算 `git show 1eb262c:…app-main.js` 重算配方 = 同值（防「改字节再同步改钉」）。
- 笔A 先红：`2 failed, 257 passed`（test_js_sources_layer_pinned + test_js_split_integrity_pinned；原文「app-main.js 字节数漂移: 204060 != 204006」）→ 去壳后绿 `259 passed`；全量 `2509 passed, 5 skipped`（与本机基线逐项相等）。
- 块 1-14 每块先红 `2 failed, 202 passed`（JS_FILES 列表漂移 + integrity FileNotFoundError）→ 绿 `259 passed`；node --check rc=0；SubTransJAV 零命中。
- 笔15：定向 `261 passed`（+2 新钉：deshell 钉 + 全局面钉 172 名单集合相等，名单规模实抽 172）。
- 终态：全量 `2511 passed, 5 skipped`（本机；主审机口径 2512+4）；ruff check tests/ All checks passed；34 文件 node --check 全 rc=0；index.html 共 35 个 `<script>`（34 + review.js 恒末位）；app.js/app-msg.js/app-modal.js 字节钉未动（248/58,451/92,754B）；window dunder 赋值全库 12 处零增减 + AppDictKindsCount 1 处；零构建检查（真实 import/export/type=module 零命中；app-msg.js L4 中文注释含英文 import 一词系误命中，字节钉冻结未动）；单 revert 实证两范围（`1eb262c..HEAD` 与 `36f9944..HEAD`）diff 均为空。
- 加载期 harness（Node vm ≈ 浏览器经典脚本）：去壳态 21/21、终态 35/35 零失败；`typeof openDir/guideAutoDetect/$` = function；`TranslatorManager.guideAutoDetect` = function（vm 词法探针；globalThis 属性探针显 undefined 系 const 词法绑定不挂属性的假象）；`__refineUI === true`；DOMContentLoaded/pywebviewready 监听数与改前零增减（app-main 内注册 2:2 文本计数相等）。

### 偏差披露（owner 问询未应答，按文档一致数值执行，请追认）

1. **载荷钉机制**：卡面 A.3-1/验收命令字面式 `sha256(js_sources.read_all()) == 6051c666…` 数学不可满足——read_all() 是 20→34 文件全库拼接（去壳后恒 470,144B/`10f6ef82…`，= 470,198−54B 已实测）。实际落笔：① 新增「refine 家族拼接 == 6051c666…/204,006B」断言（与 P2/卡面全部数值一致，与断言2 重写同款家族模式，17 笔恒真）；② 原 C0/C1 全库拼接不变量**保留**，期望值随批换代 `10f6ef82…`（470,144B）。未删除、未弱化任何既有护栏；建议主审在 decision-log 追认并勘误卡面 A.3-1 字样与 §七①/§B.3① 验收命令。
2. **P7 chore**：三处文案按卡面 §三 改写，经普通 edit 通道一次通过（未被凭据判据拦截，含旧形态「token 词后接等号」的 oldText 锚点）。

### 过程异常（均已处置，未影响交付面）

1. 块2 首次执行时驱动脚本 JS_FILES 列表锚点未计入已累积 refine 名 → pins 未生效（红相失效）。处置：修复脚本 → 工作树回退块1 提交态（app-main 196,605B/`a914af90…` 校验）→ 重跑块2 完整红→绿。无残留。
2. 笔15 首次 commit 因 git add 对已改名路径报 `fatal: pathspec` 整体失败，仅 rename 入库（`01cf673`）。处置：补齐 3 文件 git commit --amend → `f9f4ce3`（4 文件完整）。本地未推送，amend 不涉历史改写。
3. 驱动脚本 after 子命令 k=15 分支 UnboundLocalError（辅助脚本缺陷，非产品面）；改用直接哈希断言完成 §B.4 前置校验（app-main 恰 2,654B/`53c979ce…`）。
4. 本执行记录首次写入被凭据判据误拦（触发点为上一行 P7 披露里的旧形态描述字面），已改写措辞重试；该误拦正是 P7 chore 要消除的复发形态，判定为误判如实披露。

### 唯一行为差量（P4-A）

**唯一行为差量：ASR 模型面板「打开目录」按钮由不可用变可用**（app-modal.js:662 分支激活，调用 refine_open_dir 打开资源管理器）。执行记录与后续 CHANGELOG 不写「行为无变化」。代码零改动。

### 已知全局面（与拍板清单一致）

172 个顶层声明（129 函数挂 `window`）；跨文件零重名（全局面钉冻结集合相等）；4 个元素 id 被同名函数遮蔽（refreshFallbackModels/asrStatus/guideStatus/guideCustomStatus，全仓无 window.<四名> 读取，现状无消费）；`window.__refineUI` 保留为只写兼容标记；重复加载由静默 return 变 SyntaxError（每文件恰 1 次静态钉兑底）。

### 遗留问题

1. **GUI 黑盒点验待主审**（本执行环境无法点击原生 WebView2 窗口）：静态与加载期等价证据已由 harness 提供（35/35 零失败）；真窗口点验建议主审在终态一次补全：首屏加载、ASR 模型面板「打开目录」按钮点验（唯一行为差量）、四元素显示/绑定、翻译完成后自动探测链路（app-translator.js:362）。
2. test_upload_zone_no_icon.py:102 注释仍提 app-main.js（无路径依赖，勘探 §7.5 登记不动）——终态后该注释已过期，留待后续批次顺手修。
3. 本执行轮零 Mimosa 复扫（本机无该命令）；建议主审机按惯例复扫（主审口径基线 28 findings identity）。
