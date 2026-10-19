"""GUI 前端 JS 修复的静态断言回归测试。

app.js 依赖浏览器 DOM/pywebview，项目内无 JS 自动化测试基建，
本文件以源码静态断言 + 人工推演说明锁定前端行为契约：
- 文件列表条目 dataset.index 与 selectedFiles 的全量重同步
- 导读路径 stem 按 basename 派生，与 refine/quality_report.py
  write_guide_json 的落盘命名一致（含 strip_lang_suffix 镜像）
- cancel_translation 返回 success=False 时前端保持运行态继续轮询
- 语法提示徽标清除内联 display:none

配套 ``node --check app.js`` 语法校验（node 不可用时该用例跳过）。
"""
import hashlib
import re
import shutil
import subprocess
from pathlib import Path

import js_sources
import pytest

ASSETS = (Path(__file__).resolve().parents[1] / "subtransjav"
          / "webview_gui" / "assets")
REVIEW_JS = ASSETS / "review.js"
INDEX_HTML = ASSETS / "index.html"


def _app_js_source() -> str:
    return js_sources.read_all()


def _extract_function(source: str, name: str) -> str:
    """按花括号配平提取 app.js 中指定函数/方法的完整源码片段。"""
    m = re.search(
        rf"(?:function\s+{name}\s*\([^)]*\)"
        rf"|(?:^|\s)(?:async\s+)?{name}\s*\([^)]*\))\s*\{{",
        source)
    assert m, f"app.js 中未找到函数: {name}"
    depth = 0
    for i in range(m.end() - 1, len(source)):
        ch = source[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return source[m.start():i + 1]
    raise AssertionError(f"app.js 函数花括号未配平: {name}")


def _tab_hooks_literal() -> str:
    """提取 app.js 顶层 const TAB_HOOKS = {...}; 切页钩子注册表字面量
    （3.1 地基批卡3 switchTab 六钩子收编；花括号配平口径同 _extract_function）。"""
    src = _app_js_source()
    m = re.search(r"const TAB_HOOKS\s*=\s*\{", src)
    assert m, "app.js 未找到 const TAB_HOOKS 切页钩子注册表"
    depth = 0
    for i in range(m.end() - 1, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[m.start():i + 1]
    raise AssertionError("app.js TAB_HOOKS 字面量花括号未配平")


def _tab_hooks_group(tab_id: str) -> str:
    """提取 TAB_HOOKS 注册表中指定 tab 分组的钩子数组源码（方括号配平），
    供各切页钩子钉在收编后按分组断言语义（键缺失即断言失败）。"""
    reg = _tab_hooks_literal()
    m = re.search(rf"'{re.escape(tab_id)}'\s*:\s*\[", reg)
    assert m, f"TAB_HOOKS 注册表缺 {tab_id} 分组"
    depth = 0
    for i in range(m.end() - 1, len(reg)):
        if reg[i] == "[":
            depth += 1
        elif reg[i] == "]":
            depth -= 1
            if depth == 0:
                return reg[m.start():i + 1]
    raise AssertionError(f"app.js TAB_HOOKS[{tab_id}] 方括号未配平")


def _js_msg_keys() -> set:
    """解析 app.js 顶部 const MSG = {...} 键名集合（同口径
    tests/test_strings_and_shortcut.py，本文件独立实现避免跨文件导入）。"""
    m = re.search(r"const MSG = \{(.*?)\n\};", _app_js_source(), re.S)
    assert m, "app.js 未找到 const MSG = {...} 键表"
    keys = set(re.findall(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*:", m.group(1),
                          re.M))
    assert keys, "app.js MSG 键表解析为空"
    return keys


def test_app_js_syntax_node_check():
    """node --check 全文件语法校验（node 不可用时跳过）。"""
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    for name in js_sources.JS_FILES:
        r = subprocess.run([node, "--check", str(ASSETS / name)],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"{name}: {r.stderr}"


# ---------------------------------------------------------------------------
# M1：文件列表条目索引失步 → 误删/误选
# ---------------------------------------------------------------------------

def test_render_resyncs_all_item_indices():
    """render() 必须对全部 .file-item 重写 dataset.index。

    人工推演（失步场景）：selectedFiles=[A,B,C]，DOM 索引 0/1/2；
    removeSelected 删除 B 后 selectedFiles=[A,C]，render() 仅移除 B 的
    DOM 节点而不刷新 C 的 dataset.index（仍为 2）→ 点击 C 时
    handleItemClick 取 index=2 映射 selectedFiles[2]=undefined：
    toggleSelection(2) 选中空号、updateSelectionUI 凭陈旧索引 2 给 C 加
    selected 类、removeSelected 对 index=2 splice 删不到任何条目——
    点选/框选/删除全部命中错误条目。重同步后 C 收敛为 1。
    """
    body = _extract_function(_app_js_source(), "render")
    assert "createFileItem(file, index)" in body
    assert "dataset.index" in body, \
        "render() 除新增项建节点外必须重写既有项的 dataset.index"
    assert "querySelectorAll('.file-item')" in body
    # 重同步必须发生在增删 DOM 之后（按源码出现次序断言）
    assert body.index("dataset.index") > body.index("item.remove()")


# ---------------------------------------------------------------------------
# M2：导读路径拼接（与 refine/quality_report.write_guide_json 命名对齐）
# ---------------------------------------------------------------------------

def test_guide_path_uses_basename_stem_and_source_dir():
    """guidePath 必须按 basename 派生 stem 并解析 output='source' 哨兵。

    修复前：stem 取自输入全路径去扩展名，绝对路径输入拼出
    "outDir/C:/videos/ep01_质量报告导读.json"（盘符冒号嵌入），
    加载导读与完成后自动探测永远失败。
    修复后命名契约：管线落盘为
    out_dir/{strip_lang_suffix(basename_stem)}_质量报告导读.json
    （quality_report.py:1126 与 pipeline_support.strip_lang_suffix），
    JS 侧镜像同一 stem 派生：basename → 去扩展名 → 剥离
    .japanese/.chinese/.translated；output 为 'source' 或空时解析到
    输入文件同目录（对应 _resolve_stage_paths 的 out_dir 回退语义）。
    """
    source = _app_js_source()
    body = _extract_function(source, "guidePath")
    assert "replace(/\\\\/g, '/')" in body, \
        "必须先归一化反斜杠再取 basename"
    assert "lastIndexOf('/')" in body, "stem 必须取自 basename"
    assert "'source'" in body, "output='source' 哨兵必须解析为输入同目录"
    suffix_m = re.search(r"GUIDE_SUFFIX\s*=\s*'([^']+)'", source)
    assert suffix_m and suffix_m.group(1) == "_质量报告导读.json"
    for lang in ("japanese", "chinese", "translated"):
        assert lang in body, f"stem 需镜像 strip_lang_suffix 的 .{lang} 剥离"


# ---------------------------------------------------------------------------
# M3：启动哨兵期取消失败必须保持运行态
# ---------------------------------------------------------------------------

def test_cancel_translation_gates_on_success():
    """cancelTranslation 必须校验 result.success，失败保持运行态继续轮询。

    人工推演（竞态场景）：哨兵期（Popen 前，冷启可达秒级）后端返回
    success=False；修复前前端不看 success 直接记"已取消"并 _finish()——
    停轮询、禁用停止键；随后 start_translation 成功只重启轮询、不复位
    isRunning → 运行中进程从此无法停止。修复后仅 success 为真才
    _finish，失败分支记录后端错误并保持运行态等轮询收尾。
    """
    body = _extract_function(_app_js_source(), "cancelTranslation")
    assert re.search(r"=\s*await\s+pywebview\.api\.cancel_translation\(\)",
                     body), "cancel_translation 返回值必须被接收"
    assert "result.success" in body, "必须校验 result.success"
    assert "result.error" in body, "失败分支须透出后端错误信息"
    # _finish 仅允许出现在成功分支（失败分支必须保持运行态）
    assert body.count("_finish(") == 1
    assert body.index("result.success") < body.index("_finish(")


# ---------------------------------------------------------------------------
# L1：语法提示徽标永不显示
# ---------------------------------------------------------------------------

def test_grammar_hint_badge_clears_inline_display_none():
    """updateGrammarHintBadge 必须清除徽标内联 display:none。"""
    body = _extract_function(_app_js_source(), "updateGrammarHintBadge")
    assert re.search(r"badge\.style\.display\s*=\s*''", body), \
        "激活/停用判定前必须清除 index.html 的内联 display:none"
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="grammarHintBadge" style="display:none;"' in html, \
        "index.html 初始隐藏机制应保持不变（显隐由 JS 接管）"


# ---------------------------------------------------------------------------
# A3：主题持久化走后端（main.py private_mode=True 下 localStorage 不可靠，
# 用户设置按既定口径走后端文件，settings KV 为现成通道）
# ---------------------------------------------------------------------------

def test_save_theme_persists_via_backend_bridge():
    """saveTheme 必须双写：localStorage（非 private 下仍生效）+ 后端 settings
    键 theme；桥不可用时静默降级（try/catch）。"""
    body = _extract_function(_app_js_source(), "saveTheme")
    assert "localStorage.setItem" in body, \
        "localStorage 写入必须保留（非 private 模式下仍生效）"
    assert "refine_save_stage_settings" in body, \
        "必须同步写后端 settings KV（refine_save_stage_settings）"
    assert "theme" in body, "后端持久化键名必须为 theme"
    assert "catch" in body, "桥不可用时必须静默降级（try/catch）"


def test_pywebviewready_applies_backend_theme():
    """pywebviewready 后读取 settings.theme 并 applyTheme
    （早于该时机的 init 保持现状默认）。"""
    source = _app_js_source()
    body = _extract_function(source, "loadSavedThemeFromBackend")
    assert "refine_get_stage_settings" in body, \
        "必须经 refine_get_stage_settings 读取后端主题"
    assert "applyTheme" in body, "读取后必须 applyTheme"
    m = re.search(r"window\.addEventListener\('pywebviewready'[\s\S]*\Z",
                  source)
    assert m, "未找到 pywebviewready 注册"
    assert "loadSavedThemeFromBackend" in m.group(0), \
        "pywebviewready 路径必须调用 loadSavedThemeFromBackend 应用后端主题"


# ---------------------------------------------------------------------------
# v1.5 GUI 外壳重构：用户模式选择器 / persona-novice / 三步引导卡删除钉
# ---------------------------------------------------------------------------

def test_user_mode_and_novice_panel_removed():
    """v1.5 删除钉：用户模式下拉、persona-novice CSS、小白引导面板与
    三步引导卡必须从 index.html / app.js 中整体移除（引导卡与 Source 区
    「导入文件」功能重复，随 TAB 重构一并取消）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = _app_js_source()
    for anchor in ("refineUserMode", "persona-novice", "refine-novice-hide",
                   "refineNovicePanel", "refineNoviceProvider",
                   "refineFullPanel", "novice-guide-card",
                   "refineNoviceStartBtn", "refineNoviceStopBtn",
                   "refineNoviceAddFilesBtn", "refineNoviceFileError"):
        assert anchor not in html, f"index.html 仍残留已删除项: {anchor}"
    for sym in ("applyUserMode", "saveUserMode", "currentUserMode",
                "REFINE_USER_MODES", "ui_profile", "noviceStartTranslation",
                "applyNoviceProvider", "saveNoviceKey", "refreshNoviceKeyRow",
                "novice_provider"):
        assert sym not in js, f"app.js 仍残留已删除项: {sym}"


# ---------------------------------------------------------------------------
# v1.5 左侧 TAB 栏（SmartSub 式）：五个功能页 + 默认选中 translate
# ---------------------------------------------------------------------------

_TAB_IDS = ["tab-translate", "tab-engine", "tab-asrdict", "tab-glossary",
            "tab-guide", "tab-review", "tab-advanced"]


def test_index_html_sidebar_tabs_structure():
    """左侧竖排 TAB 栏结构钉：五个 TAB 按钮（data-tab ↔ 页面 id 一一对应，
    translate 默认选中）+ 五个 .tab-page 页面容器。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for tid in _TAB_IDS:
        assert f'id="{tid}"' in html, f"缺少 TAB 页面容器: {tid}"
        assert f'data-tab="{tid}"' in html, f"缺少 TAB 按钮: {tid}"
    # 默认选中：tab-translate 页面与按钮带 active，其余不带
    m = re.search(r'<div class="tab-page active" id="tab-translate"', html)
    assert m, "默认选中页必须是 tab-translate"
    for tid in _TAB_IDS[1:]:
        btn = re.search(
            rf'<button[^>]*data-tab="{tid}"[^>]*>', html)
        assert btn and "active" not in btn.group(0), \
            f"{tid} 的 TAB 按钮不应默认选中"
    assert 'class="side-tab-btn active"' in html, "TAB 栏缺少选中态样式锚"


def test_app_js_switch_tab_toggles_buttons_and_pages():
    """switchTab 必须按 data-tab 同步 TAB 按钮与 .tab-page 的 active 类，
    并在 bindDom 中为全部 .side-tab-btn 绑定 click。"""
    source = _app_js_source()
    body = _extract_function(source, "switchTab")
    assert "querySelectorAll('.side-tab-btn')" in body, \
        "必须遍历 TAB 按钮切换选中态"
    assert "querySelectorAll('.tab-page')" in body, \
        "必须遍历页面容器切换显隐"
    assert "classList.toggle" in body
    assert "dataset.tab" in body, "必须按 data-tab 匹配"
    bind = _extract_function(source, "bindDom")
    assert "switchTab" in bind, "TAB 按钮必须在 bindDom 中绑定 click"


# 3.1 地基批卡3（D2026-1012-01）：switchTab 六切页钩子收编——声明式注册表
_TAB_HOOK_NAMES = ("__refineTplTabHook", "TmSearch.ensure", "__asrTabHook",
                   "__warmupTabHook", "__fullchainStatusHook",
                   "__guideStalenessHook")


def test_switch_tab_hooks_registry_dispatch_pinned():
    """switchTab 六钩子收编钉（D2026-1012-01 卡3）：函数体内只经 TAB_HOOKS
    派发循环触发切页钩子（防收编回归为散落 if 内联块），六个钩子名在
    TAB_HOOKS 字面量中各恰出现一次（缺=漏注册，重=重复触发），注册序=
    原内联执行序 ①②词库页→③ASR→④⑤⑥质量与建议页。"""
    body = _extract_function(_app_js_source(), "switchTab")
    assert "const hooks = TAB_HOOKS[tabId]" in body, "switchTab 须取注册表分组"
    assert "if (hooks) for (const h of hooks) h();" in body, "缺 TAB_HOOKS 派发循环"
    assert "if (tabId ===" not in body, "禁止回退为散落 if 内联钩子"
    reg = _tab_hooks_literal()
    for name in _TAB_HOOK_NAMES:
        assert reg.count(name) == 1, (
            f"钩子 {name} 须在 TAB_HOOKS 中恰注册一次"
            f"（实测 {reg.count(name)} 次）")
    pos = [reg.index(name) for name in _TAB_HOOK_NAMES]
    assert pos == sorted(pos), \
        "TAB_HOOKS 注册序须与原内联执行序一致（①②→③→④⑤⑥）"


# ---------------------------------------------------------------------------
# A5：batch parseInt||30 缺省表达修复（填 0 被吞成 30）
# ---------------------------------------------------------------------------

def test_batch_values_use_positive_int_guard():
    """batch_local/batch_cloud 必须经正整数守卫：空/非法/0/负数不传
    （后端缺省接管），禁止 parseInt(v)||30 形态。"""
    source = _app_js_source()
    body = _extract_function(source, "readPositiveInt")
    assert "Number.isFinite" in body, "必须用 Number.isFinite 守卫非法值"
    assert "> 0" in body, "必须仅放行正整数"
    opts = _extract_function(source, "buildRefineOptions")
    assert "batch_local: readPositiveInt('refineBatchLocal')" in opts
    assert "batch_cloud: readPositiveInt('refineBatchCloud')" in opts
    assert "|| 30" not in opts, "禁止 parseInt(v)||30 形态（0 会被吞成 30）"


# ---------------------------------------------------------------------------
# v1.5 翻译服务快捷下拉（原小白模式顶栏迁入 tab-translate，逻辑保留）
# ---------------------------------------------------------------------------

_SERVICE_QUICK_PROVIDER_VALUES = ["lmstudio", "ollama", "deepseek", "zen",
                                  "siliconflow", "custom"]


def test_index_html_service_quick_with_provider_options():
    """右栏 .aside 配置面板含翻译服务快捷下拉：既定 6 个 provider 值
    （lmstudio 默认，zen 与引擎页三处同步）+ 本地提示行锚点；API KEY
    输入域已收口至引擎页（主页 key 行整体移除，删除钉防回退）。

    位置钉随 D2026-0930-08 三栏骨架重写同步修订：原 v1.5 钉断言下拉
    位于 tab-translate 与 tab-engine 之间，方案 A 拍板后服务选择迁入
    右栏 .aside（所有页可见），本钉改为断言其在 .aside 区间内。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="refineServiceQuick"' in html, "缺少翻译服务快捷下拉"
    m = re.search(r'<select[^>]*id="refineServiceQuick".*?</select>',
                  html, re.S)
    assert m, "refineServiceQuick 下拉解析失败"
    values = re.findall(r'<option value="([^"]+)"', m.group(0))
    assert values == _SERVICE_QUICK_PROVIDER_VALUES, \
        f"服务快捷下拉选项值不符: {values}"
    assert 'value="lmstudio" selected' in m.group(0), \
        "默认项必须为本地 LM Studio（lmstudio）"
    assert 'id="refineServiceQuickLocalHint"' in html, \
        "缺少本地服务提示行锚点"
    for removed in ("refineServiceQuickKeyRow", "refineServiceQuickKey",
                    "refineServiceQuickSaveKeyBtn",
                    "refineServiceQuickKeyStatus"):
        assert f'id="{removed}"' not in html, \
            f"主页 API KEY 域应已移除却仍残留: {removed}"
    js = _app_js_source()
    for sym in ("saveServiceQuickKey", "serviceQuickKeyLabel",
                "serviceQuickKeySaveBtn"):
        assert sym not in js, f"app.js 仍残留快捷 key 旧逻辑/旧键: {sym}"
    # 快捷下拉必须位于右栏 .aside 全局配置面板内（D2026-0930-08 方案 A：
    # 服务选择迁右栏所有页可见，原「tab-translate 与 tab-engine 之间」
    # 文档序钉随三栏骨架作废；锚 <aside class="aside"> 全文唯一）
    aside_open = html.index('<aside class="aside">')
    aside_close = html.index('</aside>', aside_open)
    quick_pos = html.index('id="refineServiceQuick"')
    assert aside_open < quick_pos < aside_close, \
        "翻译服务快捷下拉必须位于右栏 .aside 配置面板内"


def test_service_quick_key_row_toggles_on_cloud_providers():
    """本地提示行联动：deepseek/siliconflow/custom（云服务）隐藏提示行；
    本地服务显示本地启动提示行（key 行已随主页密钥域移除）。"""
    body = _extract_function(_app_js_source(), "refreshServiceQuickRow")
    for prov in ("deepseek", "siliconflow", "custom"):
        assert prov in body, f"提示行联动缺少云服务分支: {prov}"
    assert "refineServiceQuickKeyRow" not in body, \
        "key 行已删除，refreshServiceQuickRow 不得再引用"
    assert "refineServiceQuickLocalHint" in body, "本地服务必须显示提示行"


def test_service_quick_change_syncs_stages_and_persists():
    """服务快捷下拉选择即同步引擎页阶段A/B provider（endpoint 缺省沿用既有
    映射），并持久化：stages 复用 saveStageEndpoints 通道 + settings KV 键
    service_quick（v1.5 由 novice_provider 改名）。"""
    source = _app_js_source()
    body = _extract_function(source, "applyServiceQuickProvider")
    # 与既有 saveStageEndpoints 同款动态 id 写法（'refineS' + n + 'Provider'，
    # n∈[1,3] 覆盖阶段A/阶段B）
    assert "'refineS' + n + 'Provider'" in body, \
        "必须同步阶段A/B provider（写 stage A 并同步 stage B）"
    assert "for (const n of [1, 3])" in body, \
        "同步范围必须覆盖阶段A与阶段B"
    assert "applyProviderEndpoint" in body, \
        "endpoint 缺省必须沿用既有 provider 切换填充逻辑"
    assert "saveStageEndpoints" in body, \
        "stages 持久化必须复用既有保存通道"
    assert "service_quick" in body, \
        "必须持久化 settings KV 键 service_quick"
    # 回填路径同步读写新键
    backfill = _extract_function(source, "applySavedStageSettings")
    assert "service_quick" in backfill, \
        "applySavedStageSettings 必须回填 service_quick"


def test_service_quick_key_save_removed():
    """删除钉：主页快捷下拉密钥保存函数已随 API KEY 域整体移除
    （引擎页为唯一密钥填写入口）。"""
    js = _app_js_source()
    assert "saveServiceQuickKey" not in js, \
        "saveServiceQuickKey 应已删除"
    assert "refineServiceQuickKey" not in js, \
        "快捷 key 输入域 id 引用应已删除"


def test_translate_page_has_start_stop_and_no_guide_card():
    """tab-translate 页保留唯一开始/停止入口（复用 refineStartBtn 通道），
    三步引导卡不复存在；开始/停止按钮已绑定 click。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for anchor in ("refineStartBtn", "refineCancelBtn",
                   "progressBar", "statusLabel"):
        assert f'id="{anchor}"' in html, f"tab-translate 缺少锚点: {anchor}"
    source = _app_js_source()
    bind = _extract_function(source, "bindDom")
    assert "refineStartBtn" in bind, "开始按钮必须绑定 click"
    assert "refineCancelBtn" in bind, "停止按钮必须绑定 click"

# ---------------------------------------------------------------------------
# AI 质量分析（D2026-0929：--ai-analyze 前后端接入）静态钉
# ---------------------------------------------------------------------------

def test_tab_guide_label_is_quality_and_suggestions():
    """TAB 名 i18n：tabGuide 键值改为「质量与建议」（键名不动）。"""
    m = re.search(r"tabGuide:\s*'([^']+)'", _app_js_source())
    assert m, "MSG 中未找到 tabGuide 键"
    assert m.group(1) == "质量与建议"


def test_ai_analyze_button_bound_and_flow_pins():
    """AI 分析按钮绑定 + 主流程契约。

    - 需先有已加载导读（lastLoadedGuidePath）否则行内提示 aiNeedGuide；
    - 分析中禁用按钮并提示 aiAnalyzing；
    - 经 pywebview.api.refine_ai_analyze 携 (报告路径, model) 两参调用。
    """
    source = _app_js_source()
    body = _extract_function(source, "refineAiAnalyze")
    assert "lastLoadedGuidePath" in body, "必须以已加载导读为前置"
    assert "aiNeedGuide" in body, "无导读时必须行内提示"
    assert "aiAnalyzing" in body, "分析中必须给进度提示"
    assert "disabled = true" in body, "分析期间按钮必须禁用"
    assert "refine_ai_analyze" in body, "必须调 refine_ai_analyze 端点"
    assert "aiReportPath()" in body, "报告路径须经 aiReportPath 从导读 stem 推导"
    bind = _extract_function(source, "bindDom")
    assert "refineAiAnalyzeBtn" in bind, "AI 分析按钮必须绑定 click"


def test_ai_report_path_derives_from_guide_stem():
    """aiReportPath 必须把导读后缀替换为 _质量报告.txt（同 stem 同目录）。"""
    body = _extract_function(_app_js_source(), "aiReportPath")
    assert "replace(/_质量报告导读\\.json$/" in body, \
        "导读路径必须按后缀替换为质量报告 txt"


def test_ai_render_result_three_sections_and_parse_ok_degrade():
    """结果面板三段结构 + parse_ok=False 降级为纯文本（无任何可执行按钮）。

    - 三段：aiSectionGlossary 表 / aiSectionTm 表（含黄标）/ aiSectionObs 列表；
    - parse_ok=False 早退分支只渲染 aiParseFailed + observations 纯文本；
    - 按钮统一带 data-ai-kind（仅 parse_ok=True 路径可达）。
    """
    source = _app_js_source()
    body = _extract_function(source, "aiRenderResult")
    for key in ("aiSectionGlossary", "aiSectionTm", "aiSectionObs",
                "aiApplyGlossary", "aiApplyTm", "aiKind"):
        assert key in body, f"渲染函数缺少 {key}"
    assert body.index("parse_ok") < body.index("aiApplyGlossary"), \
        "parse_ok=False 必须在渲染可执行按钮之前早退"
    assert "aiParseFailed" in body, "降级分支必须给解析失败提示"
    # 降级分支位于按钮构建之前，且必须 return 早退
    early = body[:body.index("aiApplyGlossary")]
    assert "return;" in early, "降级分支必须 return 早退"


def test_ai_tm_conflict_warn_badge_pin():
    """TM 建议行：conflict_warn 时渲染 aiConflictWarn 提示徽标。"""
    body = _extract_function(_app_js_source(), "aiConflictBadge")
    assert "aiConflictWarn" in body, "黄标必须带 aiConflictWarn 提示文案"
    assert "title=" in body, "提示必须挂 title（tooltip）"
    render = _extract_function(_app_js_source(), "aiRenderResult")
    assert "conflict_warn" in render and "aiConflictBadge()" in render, \
        "TM 行必须按 conflict_warn 条件渲染黄标"


def test_ai_cloud_provider_list_pinned():
    """云端 provider 清单钉：AI_CLOUD_PROVIDERS 含四服务商
    （deepseek/siliconflow/custom/zen）。aiSetPrivacy 已随 D2026-1015-01 整行移除退役。"""
    source = _app_js_source()
    _extract_function(source, "isAiCloudProvider")
    m = re.search(r"AI_CLOUD_PROVIDERS\s*=\s*\[([^\]]+)\]", source)
    assert m, "app.js 未找到 AI_CLOUD_PROVIDERS 常量"
    cloud_list = m.group(1)
    for prov in ("deepseek", "siliconflow", "custom", "zen"):
        assert f"'{prov}'" in cloud_list, f"云服务商清单缺 {prov}"


def test_ai_apply_single_entry_calls_endpoints():
    """逐条落库：单条 JSON 调 refine_ai_apply_glossary / refine_ai_apply_tm，
    并按返回 status 回写按钮状态文案。"""
    source = _app_js_source()
    gl = _extract_function(source, "aiApplyGlossary")
    assert "refine_ai_apply_glossary" in gl
    assert "JSON.stringify" in gl, "必须单条 JSON 序列化提交"
    assert "aiApplied" in gl, "added 状态必须回写按钮文案"
    tm = _extract_function(source, "aiApplyTm")
    assert "refine_ai_apply_tm" in tm
    assert "aiTmStored" in tm and "aiExists" in tm


def test_ai_apply_failure_feedback():
    """F3：落库失败（异常或 success=False）不得静默恢复——catch 分支与
    success=False 分支均须转「重试」态并经 aiStatus 展示错误摘要。"""
    source = _app_js_source()
    fail = _extract_function(source, "aiApplyFail")
    assert "aiApplyRetry" in fail, "失败态必须转「重试」按钮"
    assert "aiStatus" in fail and "aiApplyFailed" in fail, \
        "失败必须经 aiStatus 行内展示错误摘要"
    for fn_name in ("aiApplyGlossary", "aiApplyTm"):
        body = _extract_function(source, fn_name)
        assert "aiApplyFail(btn, e)" in body, \
            f"{fn_name} catch 分支必须走 aiApplyFail 错误展示"
        assert "aiApplyFail(btn, r.error" in body, \
            f"{fn_name} success=False 分支必须走 aiApplyFail 错误展示"
        assert "aiBtnState(btn, '')" not in body, \
            f"{fn_name} 不得静默恢复按钮"


def test_guide_load_records_last_loaded_path():
    """guideLoad 成功后必须记录 lastLoadedGuidePath（AI 分析的前置依据）。"""
    body = _extract_function(_app_js_source(), "guideLoad")
    assert "lastLoadedGuidePath = r.path || p" in body


# ---------------------------------------------------------------------------
# owner 实测反馈批：dry-run 勾选移除 + 其他质量报告导读入口（显式路径）
# ---------------------------------------------------------------------------

def test_dry_run_entry_removed_from_gui():
    """删除钉：GUI 试运行勾选项整体移除（CLI --dry-run 保留不动）。

    index.html 不再有 refineDryRun 控件与 dry_run_* i18n 锚；
    app.js 不再读取 dry_run（buildRefineOptions 不传该键，后端缺省
    false 语义不变），MSG 键表无 dry_run 死键。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="refineDryRun"' not in html, "refineDryRun 控件应已删除"
    assert "dry_run_label" not in html and "dry_run_title" not in html, \
        "dry_run i18n 锚应已删除"
    js = _app_js_source()
    assert "refineDryRun" not in js, "app.js 仍读取 refineDryRun"
    assert "dry_run" not in js, "app.js 仍传 dry_run 键"
    assert "dry_run_label" not in js and "dry_run_title" not in js, \
        "MSG 键表残留 dry_run 死键"
    assert "建议先用试运行预览" not in js, \
        "覆盖确认弹窗文案仍含试运行提示"


def test_glossary_learn_has_tooltip():
    """learned 词库自学习勾选项必须带悬停说明（data-i18n-title + MSG 键）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r'<label[^>]*>\s*<input type="checkbox"'
                  r'\s+id="refineGlossaryLearn">', html, re.S)
    assert m, "未找到 refineGlossaryLearn 所在 label"
    assert 'data-i18n-title="glossary_learn_title"' in m.group(0), \
        "learned 自学习选项缺少 data-i18n-title"
    assert "glossary_learn_title" in _js_msg_keys()


def test_guide_custom_path_entry_pinned():
    """「打开其他质量报告导读」入口：原生文件对话框选择（D2026-0930-07
    owner 痛点批，替代原粘贴路径行），选中即走 guideLoad 显式路径链路，
    复用只读端点 read_output_artifact；桥为 refine_pick_guide_json。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    # 入口按钮与状态 span 保留；粘贴行三锚点必须整体移除
    assert 'id="guideOpenOtherBtn"' in html, "缺少其他导读入口锚点"
    assert html.count('id="guideCustomStatus"') == 1, \
        "状态 span 必须恰出现一次"
    for anchor in ("guideCustomRow", "guideCustomInput",
                   "guideCustomLoadBtn"):
        assert f'id="{anchor}"' not in html, f"粘贴行锚点应已移除: {anchor}"
    source = _app_js_source()
    body = _extract_function(source, "guideLoad")
    assert "customPath" in body, "guideLoad 必须支持显式路径覆盖"
    bind = _extract_function(source, "bindDom")
    assert "guideOpenOtherBtn" in bind, "入口按钮必须绑定 click"
    assert "refine_pick_guide_json" in bind, \
        "入口必须调用文件对话框桥 refine_pick_guide_json"
    assert "guideCustomLoadBtn" not in source and \
        "guideCustomInput" not in source, \
        "粘贴行按钮/输入框绑定应已清理"
    keys = _js_msg_keys()
    assert "guide_open_other_btn" in keys, "MSG 缺少其他导读入口键"
    for key in ("guide_custom_placeholder", "guide_custom_load_btn",
                "guide_custom_need_path"):
        assert key not in keys, f"MSG 残留失效键: {key}"


def test_guide_txt_view_and_learned_glossary_pinned():
    """双格式报告查看 + 学习词库只读区块：锚点唯一、渲染与互斥契约。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for anchor in ("guideTxtView", "guideJsonBlocks",
                   "glLearnedReloadBtn", "glLearnedStats",
                   "glLearnedStatus", "glLearnedTable",
                   "glLearnedEmpty", "glLearnedMore"):
        assert html.count(f'id="{anchor}"') == 1, \
            f"锚点必须恰出现一次: {anchor}"
    source = _app_js_source()
    body = _extract_function(source, "guideRenderTxt")
    assert "guideJsonBlocks" in body, "txt 模式必须隐藏结构化导读块"
    assert "textContent" in body, "txt 只读文本块必须用 textContent 免注入"
    load_body = _extract_function(source, "guideLoad")
    assert "lastLoadedReportTxtPath" in load_body, \
        "txt 加载必须记录报告路径（AI 分析取数来源）"
    ai_body = _extract_function(source, "aiReportPath")
    assert "lastLoadedIsTxt" in ai_body, \
        "AI 分析必须优先采用用户加载的报告 txt stem"
    keys = _js_msg_keys()
    for key in ("guide_txt_loaded", "guide_txt_truncated_note",
                "gl_learned_title", "gl_learned_reload",
                "gl_learned_col_aliases", "gl_learned_note",
                "gl_learned_empty", "gl_learned_stats",
                "gl_learned_more", "gl_learned_load_failed"):
        assert key in keys, f"MSG 缺少新键: {key}"
    # 只读区块说明与空态引导必须挂 i18n（中文全配键）
    for i18n in ("gl_learned_title", "gl_learned_reload",
                 "gl_learned_col_aliases", "gl_learned_note",
                 "gl_learned_empty"):
        assert f'data-i18n="{i18n}"' in html, f"缺少 data-i18n: {i18n}"
    bind = _extract_function(source, "bindDom")
    assert "glLearnedReloadBtn" in bind, "学习词库刷新按钮必须绑定 click"


def test_guide_json_blocks_initial_hidden():
    """导读卡空态光秃标题收口（d1016-卡D / D2026-1016-04）。

    #guideJsonBlocks 静态默认可见时，空态（启动首屏/未加载导读）下四个 h4
    区块标题光秃显示；改为初始 display:none，由既有渲染链路在载入 json 导读时
    点亮、txt 模式隐藏。四标题本体 data-i18n 键计数锁定防误动。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    # ① 锚点标签含初始隐藏样式
    assert re.search(r'<div id="guideJsonBlocks" style="display:none;">', html), \
        "guideJsonBlocks 必须初始隐藏（空态四行光秃标题收口）"
    source = _app_js_source()
    # ② json 载入点亮既有行为锁定防回潮
    render_body = _extract_function(source, "guideRender")
    assert "jsonBlocks.style.display = ''" in render_body, \
        "guideRender 必须在 json 载入时点亮结构化导读块"
    # ③ txt 模式隐藏既有行为锁定
    txt_body = _extract_function(source, "guideRenderTxt")
    assert "jsonBlocks.style.display = 'none'" in txt_body, \
        "guideRenderTxt 必须在 txt 模式隐藏结构化导读块"
    # ④ 四标题本体 data-i18n 键各恰出现一次（防误动标题本体）
    for key in ("guide_conclusions", "guide_sections",
                "guide_items_title", "guide_companions"):
        assert html.count(f'data-i18n="{key}"') == 1, \
            f"h4 标题 data-i18n 键必须恰出现一次: {key}"


def test_asr_python_input_hint():
    """ASR Python 输入框悬停全文提示 + min-width:0 防贴边裁切。

    钉：
    - app.js 含 asrPy.title = MSG.asrPythonPlaceholder（且紧随 placeholder
      注入行同分支内）；
    - style.css 含 #asrPythonInput { min-width: 0; }（允许空白弹性匹配）。
    """
    source = _app_js_source()
    # app.js：title 同步注入，且在 asrPy.placeholder 行同一分支内
    assert "asrPy.title = MSG.asrPythonPlaceholder" in source, \
        "app.js 需包含 asrPy.title = MSG.asrPythonPlaceholder"
    # 紧随 placeholder 注入行同一分支：确保在 asrPy.placeholder 赋值之后
    m = re.search(
        r"asrPy\.placeholder\s*=\s*MSG.asrPythonPlaceholder;"
        r".*?asrPy\.title\s*=\s*MSG.asrPythonPlaceholder;",
        source, re.S)
    assert m, "asrPy.title 必须紧随 asrPy.placeholder 同一分支内注入"
    # style.css：min-width:0 防内容固有宽顶出贴卡裁切
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    assert "#asrPythonInput { min-width: 0; }" in css, \
        "style.css 需包含 #asrPythonInput { min-width: 0; }"


def test_glossary_blocks_collapsible_pinned():
    """2.1.1 owner 痛点批：词库页两区块折叠契约（静态断言）。

    全局词库编辑 / 学习词库两 .stack 默认展开（HTML 无 collapsed 类）；
    标题行常驻（含学习词库刷新按钮与状态 span），折叠只隐藏
    .gl-collapsible-content 内容区；点标题或箭头按钮均可切换；
    折叠按钮可访问名称走 MSG.collapse_toggle（data-i18n-title 挂
    title，aria-label 由 bindDom 补挂）；状态不持久化（无 localStorage）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    # 两区块均挂 .gl-collapsible 且默认展开（无内联 collapsed 类）
    assert html.count('class="stack gl-collapsible"') == 2, \
        "两个词库区块均应挂 gl-collapsible（全局词库编辑 + 学习词库）"
    assert html.count(
        'class="stack gl-collapsible" style="margin-top:10px;"') == 1, \
        "学习词库区块缺少 gl-collapsible"
    assert re.search(r'class="stack[^"]*collapsed', html) is None, \
        "词库区块必须默认展开"
    # 每区块一个折叠按钮：aria-expanded 初值 true + 可访问名称走 MSG 键
    assert html.count("gl-collapse-btn") == 2, \
        "折叠按钮应恰为每区块一个（共 2 个）"
    for frag in ('aria-expanded="true"', 'data-i18n-title="collapse_toggle"',
                 'console-collapse-icon'):
        assert html.count(frag) >= 2, f"每区块折叠按钮缺少: {frag}"
    # 标题行常驻：学习词库标题行（第二个 gl-collapse-header）包含
    # 刷新按钮与状态 span（行内元素位于标题行开标签之后）
    learned_stack_pos = html.index(
        'class="stack gl-collapsible" style="margin-top:10px;"')
    learned_header_pos = html.index("gl-collapse-header", learned_stack_pos)
    for anchor in ("gl_learned_title", "glLearnedReloadBtn",
                   "glLearnedStats", "glLearnedStatus"):
        assert html.index(f'data-i18n="{anchor}"' if anchor == "gl_learned_title"
                          else f'id="{anchor}"') > learned_header_pos, \
            f"{anchor} 应位于学习词库标题行内"
    # 折叠按钮不与既有 id 锚冲突（console 折叠按钮 id 不变）
    assert html.count('id="consoleCollapseBtn"') == 1

    source = _app_js_source()
    assert "collapse_toggle" in _js_msg_keys(), "MSG 缺少 collapse_toggle 键"
    bind = _extract_function(source, "bindDom")
    for frag in ("querySelectorAll('.gl-collapsible')", "gl-collapse-btn",
                 "gl-collapse-header", "collapse_toggle",
                 "aria-expanded", "classList.toggle('collapsed')"):
        assert frag in bind, f"bindDom 缺少折叠接线: {frag}"
    # 状态不持久化：折叠接线不写 localStorage / bridge 存储
    assert "localStorage" not in bind, "折叠状态不应持久化"
    # CSS：折叠只隐藏内容区，标题行（.gl-collapse-header）不隐藏
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    assert ".gl-collapsible.collapsed .gl-collapsible-content { display: none; }" \
        in css, "style.css 缺少内容区隐藏规则"
    assert ".gl-collapsible.collapsed .gl-collapse-header" not in css, \
        "标题行不得随折叠隐藏"
    assert "rotate(-90deg)" in css.split("gl-tab-content", 1)[-1], \
        "折叠态箭头应旋转（transform 过渡）"


# ---------------------------------------------------------------------------
# 角色卡目录下拉动态化（D2026-0930-07-追加1 范围定稿2/3）：
# 固定 option 移除 + 动态渲染 esc 钉 + datalist 接线钉
# ---------------------------------------------------------------------------

def test_template_stage_fixed_options_removed():
    """index.html 的 #refineTemplateStage 不再内嵌固定 A/B option：
    选项全部由 refine_list_templates 动态填充（HTML 骨架不留裸中文）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r'<select id="refineTemplateStage"[^>]*>(.*?)</select>',
                  html, re.S)
    assert m, "index.html 未找到 refineTemplateStage 下拉"
    assert "<option" not in m.group(1), \
        "固定 option 必须移除（含 data-i18n 引用），改由 JS 动态填充"
    assert "tpl_stage_a" not in html.split('id="refineTemplateStage"')[1]
    keys = _js_msg_keys()
    assert {"tpl_stage_a", "tpl_stage_b"}.issubset(keys), \
        "动态回落仍需复用 tpl_stage_a/b MSG 键渲染"


def test_template_options_render_esc_pinned():
    """动态渲染函数钉：列目录 → 填充下拉；option value/label 全量 esc()
    （readdir 结果是外部输入）；目录空回落固定 A/B（MSG 渲染）。"""
    source = _app_js_source()
    body = _extract_function(source, "tplRenderOptions")
    for frag in ("refine_list_templates", "esc(it.value)", "esc(it.label)",
                 "pkg_fallback", "MSG.tpl_stage_a", "MSG.tpl_stage_b",
                 "canonical"):
        assert frag in source, f"动态渲染缺少关键接线: {frag}"
    # esc 覆盖 option 的 value 与 label 两处（innerHTML 注入面）
    assert body.count("esc(") >= 2, "option 渲染必须全量 esc()"


def test_template_load_save_by_name_pinned():
    """load-by-name / save-by-name 钉：非 'A'/'B' 选项值视为文件名，
    load 传 refine_get_template 第三参，save 传 refine_save_template
    第四参；编辑器区显示当前加载完整路径（新 MSG 键）。"""
    source = _app_js_source()
    load = _extract_function(source, "tplLoad")
    assert "refine_get_template(idx, dir, idx)" in load, \
        "文件名选项必须走 load-by-name 三参调用"
    save = _extract_function(source, "tplSave")
    assert "refine_save_template(" in save and "isStageTag ? null : idx" in save, \
        "文件名选项必须走 save-by-name 四参调用"
    for frag in ("refineTplLoadedPath", "tpl_loaded_path"):
        assert frag in source, "编辑器区必须显示当前加载路径"
    assert {"tpl_loaded_path", "tpl_dir_empty_hint",
            "tpl_dir_empty_datalist"}.issubset(_js_msg_keys())


def _input_tag(html: str, dom_id: str) -> str:
    """提取 index.html 中指定 id 的 <input> 起始标签（跨行属性容忍）。"""
    m = re.search(r'<input\b[^>]*\bid="' + re.escape(dom_id) + r'"[^>]*>',
                  html, re.S)
    assert m, f"index.html 未找到 input#{dom_id}"
    return m.group(0)


def test_dir_show_inputs_readonly_dialog_only_pinned():
    """批1a 收口件（D2026-1002-12 拍板点3）：目录回显输入框必须 readonly
    ——"浏览…"原生对话框是唯一变更入口，网页输入框不接受直接提交任意路径。

    覆盖词库与模板页两组同语义目录（角色卡 refineTemplatesDirShow /
    净语配置 refineCleanerConfigShow，后者同语义一并收口）；同时钉隐藏
    载体 refineTemplatesDir/refineCleanerConfig 保持 type="hidden"——
    该元素 readOnly 属性按 HTML 规范恒为 false（readonly 不适用于
    hidden 子类型），且从未渲染、不可键盘触达，仅 app.js 从后端返回值
    程序性写入，不构成手输提交通道。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in ("refineTemplatesDirShow", "refineCleanerConfigShow"):
        tag = _input_tag(html, dom_id)
        assert re.search(r"\breadonly\b", tag), \
            f"input#{dom_id} 必须携带 readonly（手输不提交红线）"
    for dom_id in ("refineTemplatesDir", "refineCleanerConfig"):
        tag = _input_tag(html, dom_id)
        assert 'type="hidden"' in tag, \
            f"input#{dom_id} 必须保持 type=hidden（程序性载体）"


def test_dir_hidden_carrier_only_backend_written_pinned():
    """手输通道不存在钉：隐藏载体 .value 赋值点全部来自后端返回值
    （refine_default_paths 的 d.templates_dir / 对话框结果的 r.path /
    settings 回填），不存在把用户键入文本写入的赋值路径；且
    refineTemplatesDirShow 不绑定 input/change 监听（唯一变更入口=
    "浏览…"按钮 → 原生对话框）。"""
    source = _app_js_source()
    writes = re.findall(
        r"\$\('(refineTemplatesDir|refineCleanerConfig)'\)\.value"
        r"\s*=\s*([^;\n]+)", source)
    assert writes, "赋值点缺失（回显链被破坏）"
    for rhs in writes:
        assert ("d.templates_dir" in rhs) or ("r.path" in rhs) or \
            ("applySaved" in rhs), f"隐藏载体赋值必须源自后端返回值: {rhs}"
    assert not re.search(
        r"refineTemplatesDirShow.{0,200}?addEventListener", source, re.S), \
        "refineTemplatesDirShow 不得绑定 input/change 监听（唯一入口=浏览按钮）"


def test_switch_tab_glossary_refresh_hook_pinned():
    """switchTab 到 tab-glossary 触发词库页初始化钩子（动态填充下拉）。
    卡3（D2026-1012-01）收编后钩子挂 TAB_HOOKS 的 tab-glossary 分组，
    经 switchTab 派发循环触发。"""
    src = _app_js_source()
    body = _extract_function(src, "switchTab")
    assert "TAB_HOOKS[tabId]" in body, "switchTab 须经注册表派发"
    assert "__refineTplTabHook" in _tab_hooks_group("tab-glossary"), \
        "switchTab 必须带 tab-glossary 初始化钩子"


def test_direction_card_datalist_pinned():
    """高级参数页 #directionCardS1/#directionCardS3 挂同一列表生成的
    <datalist>：option value=完整路径（目录+文件名）、不带 label；
    空目录注入 disabled 提示项；自由输入语义不变（仍读 .value）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for input_id in ("directionCardS1", "directionCardS3"):
        m = re.search(rf'<input id="{input_id}"[^>]*>', html)
        assert m, f"index.html 未找到 {input_id}"
        assert 'list="directionCardList"' in m.group(0), \
            f"{input_id} 必须挂 directionCardList datalist"
    assert 'id="directionCardList"' in html, "缺 datalist 容器"
    source = _app_js_source()
    body = _extract_function(source, "tplRenderDatalist")
    assert "value=\"\" disabled" in body.replace("'", '"'), \
        "空目录必须注入 disabled 提示项"
    assert "dir + sep + f.name" in body, "option value 必须是完整路径"
    # 文件 option 一律无 label 文本节点（value 后立即闭合 '>'）；
    # disabled 提示项文案（自身 MSG 键）是唯一例外且必须 esc()
    file_opt = [ln for ln in body.splitlines() if "esc(dir ?" in ln]
    assert file_opt, "未找到文件 option 渲染行"
    close_frag = "+ " + chr(39) + chr(34) + chr(62) + chr(39)  # JS: + '">
    assert "</option>" not in file_opt[0] and close_frag in file_opt[0], \
        "datalist 文件 option 不得带 label 文本节点"
    assert "esc(MSG.tpl_dir_empty_datalist)" in body, "提示项文案须 esc()"
    # 自由输入语义不变：启动参数仍读输入框 .value（方向参数化钉
    # test_build_refine_args_direction_* 的前端来源）
    assert "direction_card_s1: ($('directionCardS1') || {}).value || ''" in source


# ---------------------------------------------------------------------------
# UI 改版阶段2 批1（D2026-0930-09）：SVG 图标与 i18n 分层守门钉
# ---------------------------------------------------------------------------

def test_data_i18n_elements_no_direct_svg_child():
    """任何带 data-i18n（纯文本键；-title/-placeholder 豁免）的元素，
    其直接子节点不得是 <svg>。

    背景：applyI18n 以 el.textContent = MSG[key] 整体覆写文本，
    SVG 作为 data-i18n 元素的直接子节点会被整棵抹掉。凡按钮/容器
    需要 SVG 图标时，data-i18n 必须移到内层 <span>（svg 与 span 为
    兄弟节点）。解析用 html.parser（标准库，稳健于正则）。
    """
    from html.parser import HTMLParser

    VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input",
            "link", "meta", "param", "source", "track", "wbr"}
    violations = []

    class SvgChildChecker(HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            # 栈元素: [tag, 该元素自身是否带 data-i18n 纯文本键]
            self.stack = []

        def handle_starttag(self, tag, attrs):
            if self.stack:
                ptag, p18n = self.stack[-1]
                if p18n and tag == "svg":
                    violations.append(
                        f"行 {self.getpos()[0]}: <{tag}> 是 data-i18n 元素 "
                        f"<{ptag}> 的直接子节点")
            has_text_i18n = any(name == "data-i18n" for name, _ in attrs)
            if tag not in VOID:
                self.stack.append([tag, has_text_i18n])

        def handle_startendtag(self, tag, attrs):
            # 自闭合（void 或 <svg .../> 形式）不入栈：不产生直接子节点
            self.handle_starttag(tag, attrs)
            if tag not in VOID:
                self.stack.pop()

        def handle_endtag(self, tag):
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break

    checker = SvgChildChecker()
    checker.feed(INDEX_HTML.read_text(encoding="utf-8"))
    checker.close()
    assert not violations, (
        "data-i18n 元素存在直接 <svg> 子节点（applyI18n textContent 会覆写"
        f"图标，须把 data-i18n 移到内层 span）: {'; '.join(violations)}")


# ---------------------------------------------------------------------------
# 批2（D2026-0930-09）：文件行新结构钉——三态 chip 与行内移除按钮防回退
# ---------------------------------------------------------------------------

def test_create_file_item_has_chip_and_remove_button():
    """createFileItem 必须生成三态 chip 与 .file-remove-btn 行内移除按钮。

    批 2 重构后的文件行结构 = 图标盒 + 名称/路径双行 + chip + 移除按钮；
    移除按钮走 fileList click 委托的 .file-remove-btn 分支（先于选择逻辑），
    chip 由 itemStates/updateChips 驱动（scan 三态 + files_status 实时点亮）。
    """
    src = _app_js_source()
    create = _extract_function(src, "createFileItem")
    assert "file-remove-btn" in create, "文件行缺少行内移除按钮（list-x）"
    assert "chip" in create, "文件行缺少状态 chip 元素"
    assert "file-ico" in create, "文件行缺少图标盒（Lucide file-text）"
    # chip 状态机四态 class 生成器在位
    for cls in ("chip-pending", "chip-running", "chip-done", "chip-resumable"):
        assert cls in src, f"缺少 chip 状态 class：{cls}"
    # 委托分支：移除按钮必须先于选择逻辑处理（全局唯一分支串，含 removeOne 调用）
    assert "closest('.file-remove-btn')" in src, "fileList click 委托缺少移除按钮分支"
    assert "removeOne(" in src, "缺少单文件移除方法 removeOne"


# ---------------------------------------------------------------------------
# 批2（D2026-1001）：刷新按钮存还模式钉——textContent 会抹掉按钮内联 SVG
# ---------------------------------------------------------------------------

def test_refresh_button_state_restore_uses_innerhtml():
    """刷新/测试按钮的 loading 存还必须用 innerHTML（textContent 恢复会丢 SVG 图标）。

    真机反馈：模型刷新按钮加载后图标永久消失——`btn.textContent = old` 中
    old 取自含 SVG 按钮的 textContent（SVG 贡献空文本），恢复时子节点树被
    整体替换为纯文本。修复后保存与恢复一律 innerHTML（old 为按钮自身静态
    模板，无用户输入，无注入面）。适用边界：不得将该模式复制到含用户输入
    内容的按钮上。
    """
    src = _app_js_source()
    assert "btn.innerHTML = old;" in src, "刷新按钮恢复未用 innerHTML（SVG 会被 textContent 抹掉）"
    assert "const old = btn.innerHTML;" in src, "刷新按钮保存未用 innerHTML"
    # 防复发：保存行不得再出现 textContent 保存旧值再写回的模式
    assert re.search(r"const old = btn\.textContent", src) is None, \
        "存在 textContent 保存按钮旧值（恢复时会丢内联 SVG）"
    # 词典卡 B2 案（D2026-1001 批3）：.dict-row 行渲染已废——骨架 id 静态落
    # index.html（见 FROZEN_IDS），JS 只填充下拉与详情区，不再动态建行。
    # 2.6.5 段2（D2026-1004-01 #4）：#dictEmpty 空态引导条显式删除
    # （FROZEN_IDS 215→214），骨架 id 清单同步去 dictEmpty
    assert "dict-row" not in src, "词典行 .dict-row 模板残留（B2 案已废行渲染）"
    html = INDEX_HTML.read_text(encoding="utf-8")
    for val_id in ("dictSelect", "dictDetail", "dictPill", "dictDesc",
                   "dictPathRow", "dictPath", "dictOpenDir", "dictActionBtn"):
        assert f'id="{val_id}"' in html, f"词典卡 B2 骨架缺少：{val_id}"
    assert 'id="dictEmpty"' not in html, \
        "#dictEmpty 空态引导条应随 2.6.5 段2 删除（D2026-1004-01 #4）"
    assert 'row.style.cssText' not in src, "词典行不得再用 inline style 布局（压住网格规则）"


# ---------------------------------------------------------------------------
# 批3（D2026-1001）：右栏系统状态摘要卡——结构在位 + 四接口逐项降级
# ---------------------------------------------------------------------------

def test_system_summary_card_structure_and_degradation():
    """摘要卡四数据行在位；SystemSummary 每接口独立 try/catch（单点失败不拖垮右栏）。

    2.6.5 段2（D2026-1004-01 #2）：截窗 2400→3600——两行式改版后 load()
    注释与 stat/path 双槽辅助加长，首个 per-call catch 后移，逐接口降级
    守卫语义不变（既有断言必要修订，按任务书注明决策号）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="systemSummaryCard"' in html
    for val_id in ("sysSummaryVersion", "sysSummaryDataRoot", "sysSummaryTm", "sysSummaryDict"):
        assert f'id="{val_id}"' in html, f"摘要卡缺少数据行：{val_id}"
    src = _app_js_source()
    for api in ("get_version", "refine_get_data_root", "tm_get_stats", "refine_dict_status"):
        assert api in src, f"摘要卡未接入 {api}"
    # 降级：SystemSummary 段内必须存在 per-call catch（截取段落内判定）
    start = src.index("const SystemSummary")
    seg = src[start:start + 3600]
    assert "catch" in seg, "SystemSummary 缺少逐接口降级 catch"


# ---------------------------------------------------------------------------
# 批3（D2026-1002-12）：AI 分析区重排 + 主页 Console 占比 + 系统状态卡扩展
# ---------------------------------------------------------------------------

def test_batch3_ai_config_row_field_cols_pinned():
    """①AI 分析配置六件套改 3 组顶置标签列（.field-col）。

    - style.css 存在 .ai-config-row .field-col 规则组与 align-items:flex-start；
    - index.html 配置行恰 3 组 .field-col（服务商/模型/跨片窗口），
      3 处内联 width:auto 不再残留；
    - 三锚点 id 全保留（FROZEN_IDS 契约）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    assert ".ai-config-row .field-col" in css, "缺 .field-col 规则组"
    m = re.search(r"\.ai-config-row \{[^}]*\}", css)
    assert m and "align-items: flex-start;" in m.group(0), \
        ".ai-config-row 缺 align-items:flex-start"
    html = INDEX_HTML.read_text(encoding="utf-8")
    i = html.index('class="ai-config-row"')
    row = html[i:html.index("</section>", i)]
    assert row.count('class="field-col"') == 3, "配置行必须恰 3 组顶置标签列"
    for dom_id in ("aiProviderSel", "aiModelInput", "aggregateWindowSel"):
        assert f'id="{dom_id}"' in row, f"配置行缺少锚点: {dom_id}"
    assert 'style="width:auto' not in row, "配置行残留内联 width:auto"


def test_batch3_console_ratio_and_section_overflow_pinned():
    """②主页 Console 与文件列表比例分配 + 空态收敛（数值逐字冻结）。

    - .section 补 overflow:hidden（收敛双层圆角不同心）；
    - .console-output 圆角降为 --radius-sm、min-height:0（高度全交外层，
      180/420 定高删除）；
    - #tab-translate > .card 60% / .console-collapsible:not(.collapsed) 40%
      （保底 180px 保留）；**上限 380px 已于卡F（D2026-1013-01）废除**——
      原 70/30 + 150/300 → D2026-1010-01 卡3 改 180/380 → D2026-1013-01
      改 60/40 + 废上限（380 硬顶截断日志 + grow=0 吃不进余量）；
    - 空态（:not(.has-files)）文件卡退出比例分配且列表容器不滚动。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    m = re.search(r"\.section \{[^}]*\}", css)
    assert m and "overflow: hidden;" in m.group(0), ".section 缺 overflow:hidden"
    m = re.search(r"\.console-output \{[^}]*\}", css)
    assert m, "缺 .console-output 规则"
    assert "border-radius: var(--radius-sm);" in m.group(0), \
        ".console-output 圆角应为 --radius-sm"
    assert "min-height: 0;" in m.group(0), ".console-output 缺 min-height:0"
    assert "min-height: 180px" not in m.group(0) \
        and "max-height: 420px" not in m.group(0), \
        ".console-output 定高未删净"
    assert "flex: 1 1 60%;" in css, "文件卡 60% 比例缺失"
    # 40% 比例制 + 保底 180px 保留；380px 上限随卡F（D2026-1013-01）废除
    # （150/300 → D2026-1010-01 卡3 改 180/380 → 卡F 废上限，决策已归档
    # docs/decision-log.md D2026-1013-01）
    assert re.search(
        r"#tab-translate \.console-collapsible:not\(\.collapsed\) \{"
        r"[^}]*flex: 1 1 40%;[^}]*min-height: 180px;",
        css), "Console 40%/180 数值漂移"
    assert not re.search(
        r"#tab-translate \.console-collapsible:not\(\.collapsed\) \{"
        r"[^}]*max-height:", css), \
        "Console 整区上限未删净（380px 硬顶已于卡F D2026-1013-01 废除）"
    assert "#tab-translate:not(.has-files) > .card { flex: 0 0 auto; }" in css, \
        "缺空态文件卡收敛规则"
    assert re.search(
        r"#tab-translate:not\(\.has-files\) \.file-list-container \{"
        r"[^}]*overflow-y: hidden;", css), "缺空态列表容器不滚动规则"


def test_workbench_explicit_row_page_scroll_pinned():
    """D2026-1010-02 件1：.workbench 显式单行限高（「无法下翻」总根因根治钉）。

    - grid-template-rows: minmax(0, 1fr) 在位——此前只定义列，隐式行随
      内容撑高越过视口，.main 被 stretch 到行高永不溢出，超视口内容被
      body overflow:hidden 裁切（Console 380px/rawLog 弹窗化均为此病灶
      的症状级补丁）；
    - .main 滚动容器语义在位（overflow-y:auto）；
    - .tab-page.active 的 flex:1 0 auto + min-height:0 契约保持
      （tab-translate 70/30 视口比例的前提），改动须先解冻本钉并走
      全 7 tab 黑盒回归。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    m = re.search(r"\.workbench \{[^}]*\}", css)
    assert m, "缺 .workbench 规则"
    assert "grid-template-rows: minmax(0, 1fr);" in m.group(0), \
        ".workbench 缺显式单行限高（grid-template-rows）"
    m = re.search(r"\.main \{[^}]*\}", css)
    assert m and "overflow-y: auto;" in m.group(0), ".main 滚动容器缺失"
    m = re.search(r"\.tab-page\.active \{[^}]*\}", css)
    assert m and "flex: 1 0 auto;" in m.group(0) \
        and "min-height: 0;" in m.group(0), \
        ".tab-page.active flex 契约漂移（70/30 视口比例前提）"


def test_batch_fix_skipped_msg_key_pinned():
    """D2026-1010-02 件3b：批修复 skipped 完成消息 JS 态键（零 data-i18n）
    在位且被结果回显消费。"""
    assert "batchFixSkipped" in _js_msg_keys(), "MSG 缺少 batchFixSkipped 键"
    assert "MSG.batchFixSkipped(" in _app_js_source(), \
        "批修复结果回显未消费 batchFixSkipped"


def test_crosscheck_block_and_tm_locate_pinned():
    """D2026-1010-03：媒体对照区块 + TM 定位/试听 + 明细弹窗过滤契约。

    - 件A：aiRenderResult 渲染 crosscheck_detail（有段才渲染，无段不占位），
      试听复用现有 openAudioPreview 链；
    - 件A：批次修复复验重渲染同步透传 crosscheck_detail（禁止丢键静默消失）；
    - 件B：TM 行定位解析器（tmResolveEntry）+「试听/查看条目」双按钮；
    - 件B（HRO-B）：全量打开入口监听改显式无参包裹——事件对象不得进入
      openGuideItemsModal 过滤逻辑；过滤仅数组实参生效。
    """
    src = _app_js_source()
    for key in ("crosscheckTitle", "ccThTiming", "ccThAsr", "ccThCurrent",
                "previewNeedGuide", "tmViewEntry"):
        assert key in _js_msg_keys(), f"MSG 缺少 {key} 键"
    assert "Array.isArray(r.crosscheck_detail)" in src, \
        "aiRenderResult 未消费 crosscheck_detail"
    assert "cc-preview-btn" in src, "媒体对照区缺试听按钮"
    assert "crosscheck_detail: Array.isArray(r.crosscheck_detail)" in src, \
        "批次修复复验重渲染未透传 crosscheck_detail"
    assert "tmResolveEntry" in src, "缺 TM 定位解析器"
    assert "tm-preview-btn" in src and "tm-view-btn" in src, \
        "TM 行缺定位/试听双按钮"
    assert "openBtn.addEventListener('click', () => openGuideItemsModal());" \
        in src, "全量打开入口未显式无参包裹（HRO-B 回归）"
    assert "openBtn.addEventListener('click', openGuideItemsModal);" \
        not in src, "全量打开入口残留监听直挂（事件对象会进入过滤逻辑）"
    assert "Array.isArray(indexes) && indexes.length" in src, \
        "弹窗过滤未限定数组实参"


def test_log_drain_loop_pinned():
    """D2026-1010-03 件C：应用级常驻日志排水——任务结束后全链自动化
    daemon 仍向翻译日志队列投递阶段行（_automation_notice 尽力投），而
    状态轮询随 _finish 停摆；无常驻排水=全链过程行到不了 Console/原始
    日志/导出（真机黑箱实证），且积压行在下次任务启动时作陈旧行误 flush。
    pywebviewready 挂常驻 2s 排水（幂等守卫防重复叠加）。"""
    src = _app_js_source()
    assert "TranslatorManager._logDrainInterval" in src, "缺常驻日志排水"
    assert "TranslatorManager.fetchLogs()" in src, "常驻排水未接 fetchLogs"
    assert "if (!TranslatorManager._logDrainInterval)" in src, \
        "常驻排水缺幂等守卫（重复 pywebviewready 会叠加定时器）"


def test_batch3_system_summary_dynamic_rows_pinned():
    """③系统状态卡扩展：两行动态渲染（零新增静态 id）+ 委托绑定 + 新 MSG 键。

    - 角色卡/ASR 两行由 SystemSummary 动态建（data-sys-row 定位，
      行样式复用 .sys-summary-row），index.html 无任何 data-sys 静态锚；
    - ASR「重新探测」走事件委托绑 #systemSummaryCard（data-sys-action
      分流，按钮零 id），probeAsr 为唯一显式探测入口（首屏不自动探测）；
    - TM/词典行改"状态 · 路径"合并值（补 db_path / effective_dir）；
    - id 全集数随 FROZEN_IDS 契约延续（2.6.3 批C D2026-1003-01 P4 显式
      解冻 213→215：tabBtnAsrdict/tab-asrdict）。
    """
    src = _app_js_source()
    for frag in ("data-sys-row=\"roles\"", "data-sys-row=\"asr\"",
                 "data-sys-action=\"asr-probe\"",
                 "sys-summary-row", "sys-summary-val"):
        assert frag in src, f"app.js 缺少批3动态行接线: {frag}"
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "data-sys-row" not in html and "data-sys-action" not in html, \
        "摘要卡动态行不得新增静态锚（FROZEN_IDS 已满，行全由 JS 渲染）"
    ids = set(re.findall(r'(?<![\w-])id="([^"]+)"', html))
    # 2.6.5 段2（D2026-1004-01 #4，B3 显式解冻）：#dictEmpty 删除，
    # FROZEN_IDS 215→214 重钉；2.7.1（D2026-1005-01）：#asrRecList 删除，
    # FROZEN_IDS 214→213（模型管理入口走 class 锚零新增 id）；
    # 2.7.3 件⑧批 8b（D2026-1006-01）：Console 活动流批显式解冻 213→217
    # （consoleActivity/rawLogToggleBtn/exportConsoleBtn/copyConsoleBtn，
    # 全部零 data-i18n，文案 JS 态 MSG 键承接）；
    # 2.7.4 件C（D2026-1007-02）：修复生效配置明示行显式解冻 217→218
    # （batchFixEffectiveLine，零 data-i18n，文案 JS 态 MSG 键承接）；
    # 2.8.0 批1（D2026-1007-03）：压制队列底条显式解冻 218→223
    # （encodeDock/encodeDockFill/encodeDockLabel/encodeDockList/
    #  encodeDockToggle，零 data-i18n，文案 JS 态 MSG 键承接）
    assert len(ids) == 222, f"id 全集数漂移（2.8.0 批1 解冻后现契约 222），实为 {len(ids)}"
    # 委托绑定在 bindDom；探测为显式入口（probeAsr 调 refine_asr_status）
    bind = _extract_function(src, "bindDom")
    assert "systemSummaryCard" in bind and "data-sys-action" in bind, \
        "bindDom 缺系统状态卡事件委托"
    probe = _extract_function(src, "probeAsr")
    assert "refine_asr_status" in probe, "probeAsr 必须调 refine_asr_status"
    # 收口件②：失败(!success)/不可用/异常三分支全部经 asrProbeFail 包文案，
    # 不得出现裸 e.message 直显
    assert probe.count("MSG.asrProbeFail") == 3, \
        "probeAsr 失败口径漂移（三分支须统一 asrProbeFail）"
    assert "e.message : String(e)" not in probe, \
        "probeAsr 异常分支残留裸 message 直显"
    assert "refine_list_templates" in src and "pkg_fallback" in src, \
        "角色卡行必须复用 refine_list_templates（pkg_fallback 标注内置回落）"
    # 合并值：TM 行补 db_path、词典行补 effective_dir（复用现 API 字段）；
    # 收口件①：TM 值形态="N 条·命中 N·<db_path>"，行标签已由静态键
    # sys-summary-key 呈现，值内不得再拼 tm_enable_label 前缀（防重复）
    start = src.index("const SystemSummary")
    seg = src[start:src.index("// ============================================================", start)]
    for frag in ("r.db_path", "r.effective_dir"):
        assert frag in seg, f"摘要卡缺少合并值字段: {frag}"
    assert not re.search(r"return `[^`]*tm_enable_label", seg), \
        "TM 行值模板拼入 tm_enable_label（与行标签重复，违反状态·路径合并语义）"
    # 新 MSG 键存在（全中文，JS 态零静态 i18n 消耗）
    keys = _js_msg_keys()
    for key in ("sys_roles_count", "sys_roles_fallback", "sys_asr_undetected",
                "sys_asr_unconfigured", "sys_asr_ready"):
        assert key in keys, f"MSG 缺少批3新键: {key}"


def test_batch4_existing_anchors_no_regression():
    """④既有锚不回归：AI 分析区四锚保留（.asr-entry-hint 说明行已随
    2.7.1 D2026-1005-01 删除，说明并入开关 title；见 ASR 面板批测试）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in ("refineAiAnalyzeBtn", "refineAiAnalyzeStatus",
                   "refineAiResult", "refineBatchFixBtn"):
        assert f'id="{dom_id}"' in html, f"AI 分析区锚点丢失: {dom_id}"


def test_batch3_followup_analyze_section_column_layout_pinned():
    """补刀（空载复测）：AI 分析区 .section-content 收敛为列向纵排。

    #refineAiAnalyzeSection 挂 .console-section 族类，被
    `.console-section .section-content { flex:1; display:flex }` 连带设为
    flex 行向——四个直接子容器被横排挤压（按钮行插进配置列之间、
    跨片窗口列折行）。列向覆盖规则必须存在于该行向规则之后（源码序，
    保证同特异性下覆盖生效）；顶置标签中文经 bindDom JS 态填充
    （三键均既有：ai_cfg_provider_label/ai_cfg_model_label/
    aggregateWindowLabel），HTML 英文留兜底。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    row_rule = css.index(".console-section .section-content {")
    col_rule = css.index("#refineAiAnalyzeSection .section-content {")
    assert col_rule > row_rule, \
        "列向覆盖规则必须位于行向规则之后（同特异性下靠源码序生效）"
    block = css[col_rule:css.index("}", col_rule)]
    assert "flex-direction: column;" in block, "缺 flex-direction:column"
    assert "align-items: stretch;" in block, "缺 align-items:stretch"
    # 收口件③：顶置标签不加 nowrap（对齐"field-col 顶置标签允许换行"口径，
    # 防窄列横向溢出被 .section overflow:hidden 截断）
    m = re.search(r"\.ai-config-row \.field-col > label \{[^}]*\}", css)
    assert m, "缺顶置标签视觉规则"
    assert "white-space" not in m.group(0), \
        "顶置标签残留 white-space:nowrap（窄列横向溢出风险）"
    src = _app_js_source()
    bind = _extract_function(src, "bindDom")
    assert 'label[for="' in bind and "ai_cfg_provider_label" in bind \
        and "ai_cfg_model_label" in bind and "aggregateWindowLabel" in bind, \
        "bindDom 缺顶置标签 JS 态填充"
    # 三键均既有（静态引用闭合由 test_js_msg_references_defined_in_table 守）
    keys = _js_msg_keys()
    for key in ("ai_cfg_provider_label", "ai_cfg_model_label",
                "aggregateWindowLabel"):
        assert key in keys, f"MSG 缺顶置标签键: {key}"



# ---------------------------------------------------------------------------
# 2.6.1 批 2a（D2026-1002-09）：校对页静态钉（review.js / tab-review 骨架）
# ---------------------------------------------------------------------------

def _review_js_source() -> str:
    return REVIEW_JS.read_text(encoding="utf-8")


def _review_msg_keys() -> set:
    """解析 review.js 顶部 const REVIEW_MSG = {...} 键名集合（仿 _js_msg_keys）。"""
    m = re.search(r"const REVIEW_MSG = \{(.*?)\n\};", _review_js_source(), re.S)
    assert m, "review.js 未找到 REVIEW_MSG 键表"
    keys = set(re.findall(r"^\s{4}([A-Za-z_][A-Za-z0-9_]*):", m.group(1), re.M))
    assert keys, "review.js REVIEW_MSG 键表解析为空"
    return keys


def test_review_msg_references_defined_in_table():
    """REVIEW_MSG 引用闭合钉（仿 test_js_msg_references_defined_in_table）。

    正向：REVIEW_MSG.x 静态引用与 setState labelKey 字面量 ⊆ 键表（防悬空）；
    反向：键表每键必须被使用（静态引用或 labelKey 字面量，防死键堆积）。
    """
    src = _review_js_source()
    keys = _review_msg_keys()
    refs = set(re.findall(r"\bREVIEW_MSG\.([A-Za-z_][A-Za-z0-9_]*)", src))
    label_keys = set(re.findall(r"labelKey:\s*'([A-Za-z_][A-Za-z0-9_]*)'", src))
    used = refs | label_keys
    dangling = sorted(used - keys)
    assert not dangling, f"review.js 引用了 REVIEW_MSG 中不存在的键: {dangling}"
    unused = sorted(keys - used)
    assert not unused, f"REVIEW_MSG 键表中存在未被使用的死键: {unused}"


def test_review_js_syntax_node_check():
    """node --check review.js 全文件语法校验（node 不可用时跳过）。"""
    node = shutil.which("node")
    if not node:
        pytest.skip("node 不可用")
    r = subprocess.run([node, "--check", str(REVIEW_JS)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


def test_review_page_structure_pinned():
    """tab-review 骨架钉：预算内 9 id、双 data-kind、review.js 挂载、
    页内 data-i18n 仅页头复用既有 tabReview 键（静态键 cap 零消耗硬约束）。

    卡10 B-10（D2026-1012-01）显式契约变更：原「区间零 data-i18n」收紧为
    「区间 data-i18n 恰 1 处且键 == 导航既有 tabReview」——B-10 裁定七页页头
    h1 复用导航既有 tabXxx 键（同键双元素），本页键集合零增减、静态键 cap
    零消耗语义不变（全集冻结另由钉⑤a/⑤b 双集合快照自证）；页内其余区域
    仍零 data-i18n（review.js REVIEW_MSG 注入口径不变）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    for i in ("tabBtnReview", "tab-review", "reviewDropzone", "videoReviewPlayer",
              "reviewTranscodeBtn", "reviewStatusBar", "reviewStatusDot",
              "reviewStatusLabel", "reviewProgressFill"):
        assert f'id="{i}"' in html, f"index.html 缺少校对页 id: {i}"
    assert 'data-kind="video"' in html and 'data-kind="srt"' in html, \
        "导入按钮必须带 data-kind 双值（事件委托分流契约）"
    assert '<script src="review.js"></script>' in html, "review.js 未挂载"
    # tab-review 区间（至 </main>）data-i18n 仅页头复用键 tabReview
    m = re.search(
        r'<div class="tab-page" id="tab-review".*?</main>', html, re.S)
    assert m, "未找到 tab-review 页面区间"
    keys = re.findall(r'data-i18n(?:-title|-placeholder)?="([^"]+)"', m.group(0))
    assert keys == ["tabReview"], (
        "tab-review 页内 data-i18n 必须恰为页头 h1 复用的既有键 tabReview"
        f"（实测 {keys}）——静态键 cap 零消耗硬约束被破坏或页头被删"
        "（卡10 B-10 契约：除页头复用键外页内零 data-i18n）")


def test_review_enqueue_jump_contract_pinned():
    """N3 契约钉：enqueueJump({timestamp,label,source}) 入队 + console.debug。"""
    body = _review_js_source()
    m = re.search(r"enqueueJump\(jump\) \{.*?\},", body, re.S)
    assert m, "review.js 缺 enqueueJump 空实现"
    seg = m.group(0)
    assert "_jumpQueue.push(jump)" in seg, "跳转必须入队（批 3 联动消费）"
    assert "console.debug" in seg and "JSON.stringify(jump)" in seg, \
        "契约=入队即可观测（console.debug 序列化）"


def test_review_status_manager_idle_no_indeterminate():
    """批 2a 黑盒缺陷回归钉：idle 态不得显 indeterminate 流光（D2026-1002-08 四态表）。

    正交表=state 定视觉、progress 定进度：idle/ready/error 恒空轨清零；
    indeterminate 类切换仅允许出现在 busy 分支（progress=null ⇒ indeterminate
    契约在 busy 语义下不变）。
    """
    body = _extract_function(_review_js_source(), "setState")
    # 非 busy 态（idle/ready/error）清零分支存在
    busy_pos = body.find("st !== 'busy'")
    assert busy_pos > -1, "setState 缺非 busy 态判定（idle/ready/error 须清零进度轨）"
    assert "width = '0%'" in body, "非 busy 态进度轨未清零（width = '0%'）"
    # indeterminate 加类只允许出现在 busy 分支判定之后
    add_pos = body.find("classList.add('indeterminate')")
    assert add_pos > busy_pos, "indeterminate 加类必须位于 busy 分支判定之后"
    # busy 分支内保留 progress=null ⇒ indeterminate 原契约
    m = re.search(r"progress === null \|\| progress === undefined", body)
    assert m and m.start() > busy_pos, "busy 态 progress=null ⇒ indeterminate 契约丢失"


def test_review_video_exts_consistent():
    """批 2a code-review 防漂移钉：拖拽放行与 JS 分流后缀必须一致。

    main.py on_drop_event 的 allowed_exts（放行集，含 .srt）与
    review.js REVIEW_VIDEO_EXTS（JS 视频分流集）按后缀集合比对：
    JS 视频后缀 ⊆ main.py 放行集，且放行集去掉 .srt 与字幕后缀
    （.ass/.ssa/.vtt，2.7.2 件1 D2026-1005-02 拖拽放开）后恰等于
    JS 视频集（防三处字面量——含 strings.py file_type_video
    过滤器文案——漂移）。
    """
    main_src = (Path(__file__).resolve().parents[1] / "subtransjav"
                / "webview_gui" / "main.py").read_text(encoding="utf-8")
    m = re.search(r"allowed_exts\s*=\s*\(([^)]*)\)", main_src)
    assert m, "main.py 未找到 allowed_exts 元组"
    main_exts = set(re.findall(r"'(\.[a-z0-9]+)'", m.group(1)))
    assert main_exts, "main.py allowed_exts 解析为空"
    js = _review_js_source()
    m2 = re.search(r"REVIEW_VIDEO_EXTS:\s*\[([^\]]*)\]", js)
    assert m2, "review.js 未找到 REVIEW_VIDEO_EXTS"
    js_video = set(re.findall(r"'(\.[a-z0-9]+)'", m2.group(1)))
    assert js_video, "review.js REVIEW_VIDEO_EXTS 解析为空"
    assert js_video <= main_exts, \
        f"JS 视频后缀超出 main.py 拖拽放行集: {sorted(js_video - main_exts)}"
    assert ".srt" in main_exts, "main.py 放行集必须含 .srt（翻译页原路径）"
    subtitle_exts = {".ass", ".ssa", ".vtt"}
    assert subtitle_exts <= main_exts, \
        "main.py 放行集必须含 .ass/.ssa/.vtt（2.7.2 件1 拖拽放开）"
    assert main_exts - {".srt"} - subtitle_exts == js_video, \
        "main.py 放行集（去 .srt 与字幕后缀）与 JS 视频集不相等（后缀漂移）"


# ---------------------------------------------------------------------------
# 2.6.1 批 2b（D2026-1002-10）：校对编辑静态钉
# ---------------------------------------------------------------------------

def test_review_seek_formula_direct():
    """C2 公式钉：行点击 seek 直接 currentTime=start_ms/1000，无偏移字面量。"""
    body = _extract_function(_review_js_source(), "_bindList")
    assert "start_ms / 1000" in body, \
        "行点击 seek 公式漂移（须 currentTime=start_ms/1000）"
    assert not re.search(r"\+\s*0\.01|\+\s*10\b", body), \
        "seek 不得带偏移字面量（C2 裁定：10ms 补偿非必需）"


def test_review_timing_readonly():
    """时间轴列只读（D3）：行模板时间轴单元挂只读 class，无输入控件。"""
    body = _extract_function(_review_js_source(), "_buildRow")
    assert "review-timing-readonly" in body, "时间轴列缺只读锁形 class"
    assert "textarea" not in body and "<input" not in body, \
        "时间轴列不得出现输入控件"


def test_review_enter_mapping():
    """C7 键映射：Enter 提交与 Esc 回滚并存；Shift+Enter 走 textarea 默认换行。"""
    body = _extract_function(_review_js_source(), "_beginEdit")
    assert "ev.key === 'Enter' && !ev.shiftKey" in body, \
        "Enter 提交分支缺失（须排除 Shift+Enter）"
    assert "ev.key === 'Escape'" in body, "Esc 回滚分支缺失"


def test_review_confirm_text_locked():
    """C4 锁字：覆盖确认文案逐字冻结。"""
    m = re.search(r"review_confirm_overwrite:\s*'([^']*)'",
                  _review_js_source())
    assert m, "REVIEW_MSG 缺 review_confirm_overwrite"
    assert m.group(1) == "保存将按 1..N 重编号 + UTF-8 重写；行数/时间轴不变。确认覆盖？", \
        "C4 锁字文案被改动"


def test_review_dirty_no_new_state():
    """C6：dirty 只以既有 'ready' 态 + labelKey 表达，无 'dirty' 新状态枚举。"""
    src = _review_js_source()
    for m in re.finditer(r"setState\(\{[^}]*review_dirty_hint[^}]*\}", src):
        assert "state: 'ready'" in m.group(0), \
            "dirty 提示必须挂 state:'ready'（不新设状态位）"
    assert re.search(r"state:\s*'dirty'", src) is None, \
        "出现 'dirty' 新状态枚举（违反 C6）"


def test_review_tab_guard_allow_once():
    """批 2b 黑盒缺陷回归钉：守卫确认后须一次放行，不得重复确认循环。

    capture 守卫同步 preventDefault + AppModal.confirm 异步 → 重放
    btn.click() 时 dirty 仍为 true，原实现会被再次拦截形成确认循环；
    修复=一次性放行标志（确认回调先置标志再重放；handler 开头先判
    标志放行一次即清，防其他按钮误放行）。
    """
    body = _extract_function(_review_js_source(), "_bindTabGuard")
    assert "_guardAllowTab" in body, "缺一次性放行标志"
    allow_pos = body.find("this._guardAllowTab === btn")
    dirty_pos = body.find("!this._dirty")
    assert allow_pos > -1 and dirty_pos > -1 and allow_pos < dirty_pos, \
        "放行分支必须先于 dirty 判定（重放 click 时 dirty 仍为 true）"
    assert re.search(r"this\._guardAllowTab = null;\s*return;", body), \
        "放行一次后必须清标志"
    assert re.search(r"this\._guardAllowTab = btn;[\s\S]*?btn\.click\(\);", body), \
        "确认回调必须先置放行标志再重放 btn.click()"


def test_review_apply_jump_uses_block_ms_native():
    """批 3 钉（D2026-1002-11 裁定）：疑点段跳转用匹配 blocks.start_ms 原生
    毫秒（/1000 转秒），无 +0.01/+10 类偏移字面量（C2 同口径）。"""
    body = _extract_function(_review_js_source(), "_applyJump")
    assert "start_ms" in body, "须引用 blocks.start_ms 原生毫秒"
    assert "/ 1000" in body, "毫秒须除以 1000 转秒"
    assert not re.search(r"\+\s*0\.01", body), "不得加 0.01 偏移（C2 直接 seek）"


def test_review_detections_session_only_pinned():
    """批 3 条件 4：确认/跳过仅会话内标记不落盘——REVIEW_MSG.review_det_no_save
    键存在且被引用（title 明示）；位置失效态 class 存在（C8 留坑闭合）。"""
    src = _review_js_source()
    assert "review_det_no_save" in src, "不落盘文案键必须被引用"
    assert "review-det-stale" in src, "位置失效态 class 必须存在"


def test_review_asr_goto_programmatic_click():
    """批 3 条件 1：switchTab 在 app.js IIFE 内未挂全局（ReferenceError）——
    ASR 引导卡跳转必须走程序化 click（真实 handler 链）。

    2.6.3 批C D2026-1003-01 P4 IA 重排随改（既有断言必要修订）：ASR 管理
    自引擎页迁独立页 tab-asrdict，跳转锚 data-tab 同步改；80 字符
    .click() 邻近断言保持不放宽。"""
    body = _extract_function(_review_js_source(), "_bindDetections")
    assert 'data-tab="tab-asrdict"' in body, "须定位 ASR 与词典页按钮"
    assert re.search(r'data-tab="tab-asrdict"[\s\S]{0,80}\.click\(\)', body), \
        "须程序化 click（禁止直调 switchTab）"


def test_review_saveas_bridge_arg_order_pinned():
    """批 3 条件 2：saveas 桥参数序钉——后端删 src_path 后新签名为
    (blocks, target_path)，前端调用必须 blocks 在前（旧三参调用会丢参）。"""
    src = _review_js_source()
    m = re.search(r"refine_review_saveas_srt\(([^)]*)\)", src)
    assert m, "saveas 桥调用未找到"
    args = [a.strip() for a in m.group(1).split(",")]
    assert len(args) == 2, f"新签名为两参，实为 {len(args)}：{args}"
    assert args[0].endswith("_blocks") or args[0] == "blocks", \
        f"第一参须为 blocks，实为 {args[0]}"


# ---------------------------------------------------------------------------
# 2.6.1 批4（D2026-1002-12）：审计④载入 dirty 守卫 + 审计③ video error 监听
# ---------------------------------------------------------------------------


def test_review_load_srt_dirty_guard_pinned():
    """审计④：载入新字幕前 dirty 守卫——未保存修改/行内编辑中须先经
    AppModal.confirm 确认，取消即中止（防 _blocks 被静默覆盖丢编辑）。"""
    body = _extract_function(_review_js_source(), "setSrtPath")
    assert "this._dirty" in body, "setSrtPath 缺 dirty 判定分支"
    assert "this._editingIdx !== null" in body, "setSrtPath 缺编辑中判定分支"
    assert "AppModal.confirm" in body, "setSrtPath 缺确认弹窗"
    assert "review_load_dirty_confirm" in body, "setSrtPath 缺守卫文案键"
    src = _review_js_source()
    assert ("review_load_dirty_confirm: "
            "'当前有未保存的编辑，载入新字幕将丢弃这些修改。确认继续？'") in src, \
        "REVIEW_MSG 缺 review_load_dirty_confirm 完整中文文案"


def test_review_video_error_listener_pinned():
    """审计③c：video 元素挂 error 监听 → 状态条可读解码失败提示（JS 态）。"""
    body = _extract_function(_review_js_source(), "_bindPlayer")
    assert "addEventListener('error'" in body, "video 元素缺 error 监听"
    assert "review_media_error" in body, "error 监听缺可读错误提示键"


# ---------------------------------------------------------------------------
# 批2（D2026-1002-12 拍板点1/2）：模型下拉不自动拉取 + 空态占位 + 删硬默认
# ---------------------------------------------------------------------------

def test_model_list_no_auto_fetch_pinned():
    """拍板点2：模型列表一律不自动拉取，只认「刷新/测试」两个显式入口。

    refreshModels 全文件仅允许两处出现：函数定义 + 刷新按钮 click 绑定
    （bindDom 的 [1,3] 循环一处覆盖阶段A/阶段B）。页面就绪链
    （loadRemote，pywebviewready → __refineLoadRemote）、服务商切换
    （provider change 监听）、快捷下拉（applyServiceQuickProvider）均不得
    触发拉取；provider change 保留接口地址预填 applyProviderEndpoint。
    """
    source = _app_js_source()
    sites = [m.start() for m in re.finditer(r"refreshModels\(", source)]
    assert len(sites) == 2, \
        f"refreshModels 只允许定义+刷新按钮绑定两处，实际 {len(sites)} 处"
    assert re.search(r"async function refreshModels\(n\)", source), \
        "缺少 refreshModels 定义"
    assert re.search(r"addEventListener\('click', \(\) => refreshModels\(n\)\)",
                     source), "刷新按钮 click 绑定缺失"
    # 三处自动拉取移除钉
    assert "refreshModels" not in _extract_function(source, "loadRemote"), \
        "loadRemote（页面就绪链）不得自动拉取模型列表"
    assert "refreshModels" not in \
        _extract_function(source, "applyServiceQuickProvider"), \
        "快捷下拉不得自动拉取模型列表"
    bind = _extract_function(source, "bindDom")
    m = re.search(r"pv\.addEventListener\('change', \(\) => \{[\s\S]*?\n      \}\);",
                  bind)
    assert m, "bindDom 缺 provider change 监听"
    assert "refreshModels" not in m.group(0), \
        "provider change 不得自动拉取模型列表"
    assert "applyProviderEndpoint" in m.group(0), \
        "provider change 必须保留接口地址预填"
    # 刷新/测试按钮绑定保留（显式入口）
    assert "$('refineRefreshS' + n)" in bind and \
        "$('refineTestS' + n)" in bind


def test_model_selects_empty_placeholder_pinned():
    """拍板点2：模型下拉空态占位 + 硬默认删除。

    index.html 两个模型下拉不得残留 custom-model 默认项与静态 data-i18n
    键（model_default_1/2、model_refresh_hint 已随默认语义删除），初始
    骨架只留 value="" disabled selected 占位 option（文案由 bindDom 以
    JS 态键 model_list_empty_hint 填充，零静态 i18n 消耗）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "custom-model" not in html, "index.html 仍残留 custom-model 硬默认"
    for dead in ("model_default_1", "model_default_2", "model_refresh_hint"):
        assert f'data-i18n="{dead}"' not in html, \
            f"index.html 仍引用已删除静态键: {dead}"
    for sel_id in ("refineS1Model", "refineS3Model"):
        m = re.search(rf'<select id="{sel_id}"[^>]*>([\s\S]*?)</select>', html)
        assert m, f"index.html 未找到 {sel_id}"
        assert 'value="" disabled selected' in m.group(1), \
            f"{sel_id} 缺空态占位 option（value=\"\" disabled selected）"
    keys = _js_msg_keys()
    assert "model_list_empty_hint" in keys, "MSG 缺空态占位键 model_list_empty_hint"
    # bindDom 必须以 JS 态键填充占位文案（两个下拉同一循环覆盖）
    bind = _extract_function(_app_js_source(), "bindDom")
    assert "MSG.model_list_empty_hint" in bind, \
        "bindDom 缺占位文案 JS 态填充"
    # 已存模型恢复链：applySavedStageSettings 注入标记 option + refreshModels
    # 命中恢复；default_model_missing 警告仅剩"已存值与刷新列表不匹配"场景
    backfill = _extract_function(_app_js_source(), "applySavedStageSettings")
    assert "savedStageModels" in backfill and "createElement('option')" in backfill
    refresh = _extract_function(_app_js_source(), "refreshModels")
    assert "savedStageModels" in refresh
    assert "default_model_missing" in refresh
    assert "selectDefaultModel" not in refresh and \
        "LOCAL_MODEL_DEFAULTS" not in _app_js_source(), \
        "前端硬默认语义未删净"


def test_asr_card_restructured_no_hardcoded_english():
    """拍板点1：ASR 卡重整（仅入口与文案，不加执行能力）。

    结构序=header 行（标题+重新探测）→ 状态行 → 说明行 → 模型行 →
    开关行 → 推荐清单；卡内不得残留 "Re-detect"/"Media crosscheck"/
    "upstream python" 硬编码英文（文案全 JS 态键填充，零静态 i18n 消耗）；
    asrSaved 仅在保存成功后写入（与空态占位区分）；无任何新增执行按钮。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    start = html.index("<!-- ASR 模型管理")
    end = html.index("<!-- 词典管理", start)
    card = html[start:end]
    for banned in ("Re-detect", "Media crosscheck", "upstream python"):
        assert banned not in card, f"ASR 卡残留硬编码英文: {banned}"
    # 结构序（2.7.1 D2026-1005-01）：header 行（标题+模型管理+重新探测）→
    # asrEnvStatus → asrModelSel → asrCrosscheckToggle（说明行/推荐清单
    # 折叠区已删：说明并入开关 title、模型管理迁 AppModal models 面板）
    anchors = ['data-i18n="asr_panel_title"',
               'class="btn btn-secondary btn-compact asr-models-btn"',
               'id="asrRefreshBtn"', 'id="asrEnvStatus"',
               'id="asrModelSel"', 'id="asrStatus"',
               'id="asrCrosscheckToggle"', 'id="asrPythonInput"']
    pos = [card.index(a) for a in anchors]
    assert pos == sorted(pos), "ASR 卡结构序漂移（header→模型管理→探测→状态→模型→开关）"
    assert 'data-testid="asr-models-btn"' in card, "模型管理入口 data-testid 缺失"
    # 按钮口径：模型管理 + 重新探测 两个（2.7.1）
    assert len(re.findall(r"<button\b", card)) == 2, \
        "ASR 卡按钮=模型管理+重新探测两个（2.7.1 口径）"
    # JS 态文案填充钉 + asrSaved 保存成功门控
    bind = _extract_function(_app_js_source(), "bindDom")
    for frag in ("MSG.asrRefreshBtn", "MSG.asr_env_undetected",
                 "MSG.asrModelsBtn", "MSG.asrSelectPlaceholder",
                 "MSG.asrCrosscheckLabel", "MSG.asrCrosscheckTitle",
                 "MSG.asrPythonPlaceholder"):
        assert frag in bind, f"bindDom 缺 ASR 卡 JS 态文案填充: {frag}"
    assert bind.count("MSG.asrSaved") == 3 and \
        bind.count("r.success ? MSG.asrSaved") == 3, \
        "asrSaved 必须仅在保存成功后写入（三处保存链均门控）"


def test_batch2_new_msg_keys_pinned():
    """批2 新增 JS 态 MSG 键存在（全中文文案，零静态 i18n 消耗）。"""
    src = _app_js_source()
    keys = _js_msg_keys()
    for key in ("model_list_empty_hint", "asr_env_undetected"):
        assert key in keys, f"MSG 缺少批2新键: {key}"
        m = re.search(rf"^\s*{key}:\s*'([^']*)'", src, re.M)
        assert m and m.group(1), f"MSG 键 {key} 文案为空"
    assert "asr_entry_hint" not in keys, "说明行独立键应随 2.7.1 删除（并入 asrCrosscheckTitle）"


# ---------------------------------------------------------------------------
# 2.6.2 热修：R3 ASR 推荐项长 URL 撑爆卡片 + R4 词典状态加载失败吞错
# ---------------------------------------------------------------------------

def test_dict_load_failure_not_swallowed_pinned():
    """R4 回归钉：dictLoad 链尾 catch 不得静默吞错，须回写 #dictStatus
    失败文案（与 then 分支 dict_load_failed 同口径）。"""
    body = _extract_function(_app_js_source(), "dictLoad")
    assert re.search(r"catch\s*\(\s*\)\s*=>\s*\{\s*\}", body) is None, \
        "dictLoad 链尾残留空 catch（吞错导致 #dictStatus 空白）"
    assert ".catch(" in body, "dictLoad 必须保留 catch 链"
    assert body.count("MSG.dict_load_failed") >= 2, \
        "catch 回调必须回写 dictStatus 失败文案（MSG.dict_load_failed）"


# ---------------------------------------------------------------------------
# 2.6.3 批B（D2026-1003-01 ② + D2026-1003-06 五条件）：ASR 下载器 + 词典源
# 选择（index.html 冻结零改动——所有新 UI 全 JS createElement 注入，class/
# dataset 承载，零新增 id/data-i18n；FROZEN_IDS=213 / i18n=189 既有钉零改动）
# ---------------------------------------------------------------------------
def test_app_modal_download_pinned():
    """AppModal.download：radio 源卡+全宽开始键+busy 防护（下载中 ESC/
    遮罩/取消键 no-op）+sha copyable+无取消声明文案在位。"""
    src = _app_js_source()
    body = _extract_function(src, "download")
    assert "createElement('label')" in body, "源卡须 createElement 注入"
    assert "createElement('input')" in body, "radio 须 createElement 注入"
    assert "dl-src-card" in body and "dl-src-disabled" in body, "源卡/禁用灰态 class 缺失"
    assert "modal-dl-start" in body, "全宽开始键 class 缺失"
    assert "this._dlRunning" in body, "busy 防护标志缺失"
    assert "navigator.clipboard.writeText" in body, "copyable 复制链缺失"
    assert "MSG.ui_copied" in body, "「已复制」轻提示缺失"
    assert "MSG.ui_copy_manual" in body, "clipboard 不可用手动复制提示缺失"
    settle = _extract_function(src, "_settle")
    assert "this._kind === 'download' && this._dlRunning" in settle, \
        "下载进行中 _settle 必须 no-op（无取消语义，评议员条件①）"
    keys = _js_msg_keys()
    # 2.7.1：asrDlNoCancel 随旧源选择模态调用链删除（面板下载可关面板，
    # 无"不支持取消"声明语义）；AppModal.download 方法体键保留
    for key in ("asrDlStart", "asrDlDone", "asrDlFailed", "ui_copied",
                "ui_copy_manual"):
        assert key in keys, f"MSG 缺少批B新键: {key}"


def test_asr_models_panel_pinned():
    """2.7.1 件3（D2026-1005-01）：模型管理面板（AppModal kind='models'）。

    复用 #appModal 骨架 + .modal-lg；body 全 createElement（零 id/data-i18n）；
    评议 C3 守卫隔离：_settle 的 no-op 分支只命中 download kind，models
    关闭永不阻塞；下载行内进度复用 .dl-progress-*、诊断网格复用
    .dict-diag-grid；三态双门控 + verified 硬门槛（未核验禁下载）；
    重开面板经 refine_asr_download_progress 恢复轮询。"""
    src = _app_js_source()
    assert "models(opts)" in src, "AppModal.models 缺失"
    body = _extract_function(src, "models")
    assert "mp-body" in body and "modal-lg" in body, "骨架扩宽/样式类缺失"
    assert "createElement" in body, "面板须 createElement 注入"
    assert "mp-tier" in body, "三档分组缺失"
    assert "mp-chip-ready" in body and "mp-chip-adapter" in body         and "mp-chip-planned" in body, "三态 chip 缺失"
    assert "mp-dot" in body and "filled" in body, "五格点阵缺失"
    assert "dl-progress-bar" in body, "行内进度须复用 .dl-progress-*"
    assert "dict-diag-grid" in body, "失败诊断网格须复用 .dict-diag-grid"
    assert "refine_asr_download(" in body, "下载桥调用缺失"
    assert "refine_asr_download_progress(" in body, "进度快照桥缺失"
    assert "startPolling" in body, "重开恢复轮询缺失"
    assert "MB/s" in body, "前端增量 MB/s 计算缺失"
    assert "entry.verified !== true" in body, "verified 硬门槛缺失"
    assert "MSG.mpAdapterTitle" in body and "MSG.mpUnverifiedTitle" in body         and "MSG.mpPlannedTitle" in body, "三态禁用 tooltip 文案缺失"
    assert "MSG.mpUnadaptedBanner" in body, "未适配 banner 缺失"
    assert "MSG.mpPathWhisper" in body and "MSG.mpPathData" in body,         "路径栏两行缺失"
    # C3：_settle 不含 models 分支（关闭永不阻塞）
    settle = _extract_function(src, "_settle")
    assert "_kind === 'models'" not in settle,         "models kind 不得进 _settle 阻塞守卫（评议 C3）"
    # 入口链：bindDom 绑 .asr-models-btn → asrOpenModelsPanel → AppModal.models
    bind = _extract_function(src, "bindDom")
    assert "asrOpenModelsPanel()" in bind, "面板入口绑定缺失"
    openfn = _extract_function(src, "asrOpenModelsPanel")
    assert "AppModal.models(" in openfn, "面板打开调用缺失"
    assert "MSG.mpNeedProbe" in openfn, "无探测结果引导缺失"

def test_asr_d271_msg_keys_pinned():
    """2.7.1 新增 JS 态 MSG 键定向断言（评议 C1：JS 态键不受静态 cap 200
    约束，由本测试守护）；红绿灯/下拉来源标注/三态文案/死键清理同钉。"""
    src = _app_js_source()
    keys = _js_msg_keys()
    new_keys = (
        "asrProbeUpstreamOk", "asrCrosscheckTitle", "asrModelsBtn",
        "mpTitle", "mpPathWhisper", "mpPathData", "mpOpenDir",
        "mpUnadaptedBanner", "mpTierFast", "mpTierBalanced", "mpTierPrecise",
        "mpSpeedLabel", "mpPrecisionLabel", "mpSpecNote", "mpStateReady",
        "mpStateAdapter", "mpStatePlanned", "mpUnverifiedTitle",
        "mpAdapterTitle", "mpPlannedTitle", "mpVariantsLabel", "mpNeedProbe",
    )
    for key in new_keys:
        assert key in keys, f"MSG 缺少 2.7.1 新键: {key}"
    # 死键清理钉：旧键随调用链删除
    for dead in ("asr_entry_hint", "asrRecTitle", "asrPresent", "asrMissing",
                 "asrPlanned", "asrSrcOverseas", "asrSrcDomestic",
                 "asrPlaceHint", "asrDownloadTitle", "asrDlNoCancel"):
        assert dead not in keys, f"2.7.1 死键残留: {dead}"
    # 红绿灯：三色点注入 + 三态映射（asrApplyEnvStatus）
    fn = _extract_function(src, "asrApplyEnvStatus")
    assert "status-dot asr-dot" in fn, "状态点 class 缺失"
    assert "dot-ok" in fn and "dot-warn" in fn and "dot-err" in fn,         "三色点映射缺失"
    assert "ffmpeg-missing" in fn and "python-unavailable" in fn,         "triage 映射缺失（whisper-import-failed/module-missing 归红档 else 分支）"
    # 下拉：来源标注 + 完整路径 title + qwen 占位删除
    refresh = _extract_function(src, "asrRefresh")
    assert "ASR_SOURCE_LABELS" in refresh, "下拉来源标注缺失"
    assert "o.title = m.path" in refresh, "option title=完整路径缺失"
    assert "__qwen__" not in src, "qwen disabled 占位应已删除"
    assert "force === true" in refresh, "force 绕过缓存参数缺失"
    # 首启空闲探测 + ASR 页懒探测钩子
    assert "refine_asr_status()" in src, "首启后台探测缺失"
    assert "__asrTabHook" in src, "ASR 页懒探测钩子缺失"


def test_asr_d271_residue_pinned():
    """grep 自证钉：删除面残留=0（推荐清单折叠区/入口说明行/旧下载模态）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    src = _app_js_source()
    for banned in ("asrRecList", "asr-entry-hint", "asr-rec-item",
                   "asr-rec-detail", "asr-rec-actions"):
        assert banned not in html, f"index.html 残留: {banned}"
        assert banned not in src, f"app.js 残留: {banned}"
        assert banned not in css, f"style.css 残留: {banned}"
    # 2.7.1 组件样式族在位（.mp-*），三色点扩展在位
    assert ".mp-tier" in css and ".mp-chip-ready" in css, ".mp-* 样式缺失"
    assert ".mp-dot.filled" in css, "点阵样式缺失"
    assert ".status-dot.dot-ok" in css and ".status-dot.dot-err" in css,         "三色点样式缺失"


def test_dict_source_buttons_pinned():
    """词典源双按钮：JS 注入零 id + CN 可达性 title + 无镜像禁用逻辑 +
    dictDownload source 透传 + p.note 可见提示。
    2.6.5 段2（D2026-1004-01 #5 收单操作行 路线1）：#dictActionBtn 静态入
    .dict-action-row 包裹层、注入序=官方│镜像（insertBefore 目标修正）、
    下载中禁整行（is-busy + 双源键 disabled）。"""
    src = _app_js_source()
    body = _extract_function(src, "dictRenderDetail")
    assert "dict-src-official" in body and "dict-src-mirror" in body, \
        "双按钮 class 注入缺失"
    assert "MSG.dictSrcOfficialOnly" in body and "MSG.dictSrcMirrorOnly" in body, \
        "双按钮文案键缺失"
    assert "MSG.dictSrcOfficialHint" in body, "官方源 CN 可达性 title 缺失"
    assert "has_mirror" in body, "无镜像禁用判定缺失"
    assert "MSG.dictSrcMirrorlessHint" in body, "无镜像禁用 title 文案缺失"
    assert "row.insertBefore(offBtn, btn)" in body \
        and "row.insertBefore(mirBtn, btn)" in body, \
        "源键插入序须为 官方│镜像（D2026-1004-01 #5 修正）"
    assert "MSG.dict_download_source" in body, "「下载源」前缀标签须 JS 态 MSG"
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r'<div class="dict-action-row">.*?</div>', html, re.S)
    assert m and 'id="dictActionBtn"' in m.group(0), \
        "#dictActionBtn 须静态入 .dict-action-row 包裹层"
    dl = _extract_function(src, "dictDownload")
    assert re.search(r"refine_dict_download\(kind,\s*source\s*\|\|\s*'auto'\)", dl), \
        "refine_dict_download 须透传 source（缺省 auto）"
    assert "p.note" in dl, "轮询回调缺 p.note 可见提示（评议员条件①）"
    assert "is-busy" in dl, "下载中缺整行 is-busy 禁用态（D2026-1004-01 #5）"
    assert "dict-src-official" in dl and "dict-src-mirror" in dl, \
        "下载中须禁双源键（三键 setDisabled）"


def test_dict_stop_button_pinned():
    """2.7.3 件⑤ 词典下载停止按钮：四态状态机静态钉——下载中主按钮转
    btn-danger 停止键（复用 MSG.stop_btn，零新增按钮键/零新增静态 id）、
    停止中过渡（禁用防连点+状态行）、stopped 终态回未安装态+解锁链、
    过渡兜底显式常数、停止走独立 dictRequestStop（refine_dict_download_stop
    端点）。"""
    src = _app_js_source()
    dl = _extract_function(src, "dictDownload")
    assert "MSG.stop_btn" in dl, "下载中主按钮须转停止键（复用 stop_btn）"
    assert "btn-danger" in dl, "停止键须挂既有 .btn-danger 样式"
    assert "MSG.dict_stop_pending" in dl and "MSG.dict_stopping" in dl, \
        "停止中过渡文案缺失（按钮禁用防连点+状态行）"
    assert "p.phase === 'stopped'" in dl and "MSG.dict_stop_note" in dl, \
        "stopped 终态收口（回未安装态+重下指引）缺失"
    assert "DICT_STOP_GRACE_MS" in dl, "过渡兜底显式常数未接入轮询"
    stopfn = _extract_function(src, "dictRequestStop")
    assert "refine_dict_download_stop(kind)" in stopfn, "停止端点调用缺失"
    assert "_dictStopPending = true" in stopfn, "停止中过渡态标记缺失"
    # 会话制：终态由轮询驱动（finish 收口），停止过渡期 _dictBusyKind 保持占用
    assert "_dictBusyKind = null" in dl, "终态收口须清 _dictBusyKind 占位"


# ---------------------------------------------------------------------------
# 2.6.4 批1（D2026-1003-05 策略 B）：词库页 TM 只读搜索区块静态钉
# （index.html 冻结零改动：全 createElement 注入，零新增静态 id/data-i18n；
# 结果渲染全 textContent 免注入；空结果与错误态界面可见）
# ---------------------------------------------------------------------------

def test_tm_search_block_injection_pinned():
    """TM 搜索区块：createElement 整块注入（零静态锚）+ MSG JS 态文案 +
    回车与按钮双触发 + tm_search 只读桥。"""
    src = _app_js_source()
    body = _extract_function(src, "ensure")
    assert "createElement('div')" in body, "TM 区块必须 createElement 注入"
    assert "createElement('input')" in body and "createElement('button')" \
        in body and "createElement('table')" in body, \
        "输入框/搜索按钮/结果表注入缺失"
    assert "tm-search-block" in body, "区块定位 class 缺失（防重复注入依据）"
    assert "querySelector('.tm-search-block')" in body, \
        "缺哨兵判定（重复打开词库页会重复注入）"
    for key in ("MSG.tmSearchTitle", "MSG.tmSearchPlaceholder",
                "MSG.tmSearchBtn", "MSG.tmSearchColSource",
                "MSG.tmSearchColTarget", "MSG.tmSearchColStage",
                "MSG.tmSearchColHits"):
        assert key in body, f"TM 区块缺少 JS 态文案键: {key}"
    assert "addEventListener('keydown'" in body and \
        "e.key === 'Enter'" in body and "addEventListener('click'" in body, \
        "回车与按钮双触发缺失"
    # 空结果态载体：empty-guide 由 ensure 预建（MSG.tmSearchEmpty 文案），
    # run 按结果切换 display（空态界面可见）
    assert "MSG.tmSearchEmpty" in body, "空结果态文案键缺失（ensure 预建）"
    # 零静态锚：index.html 不得新增 TM 搜索 id/data-i18n（FROZEN_IDS 冻结）
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "tm-search" not in html, \
        "index.html 出现 TM 搜索锚（冻结期必须全 JS 注入）"
    assert "tmSearch" not in re.sub(r"const MSG = \{.*?\n\};", "", html,
                                    flags=re.S)


def test_tm_search_render_and_error_visible_pinned():
    """结果渲染全 textContent（禁 innerHTML）+ 空态/失败态界面可见 +
    查询中按钮禁用。"""
    src = _app_js_source()
    body = _extract_function(src, "run")
    assert "window.pywebview.api.tm_search(" in body, "tm_search 桥调用缺失"
    assert "innerHTML" not in body, "结果渲染禁 innerHTML（查询词/库内容为外部输入）"
    assert "td.textContent" in body, "单元格必须 textContent 渲染"
    assert "MSG.tmSearchFailed" in body and "r.error" in body, \
        "失败态必须可见（success=False 透出后端错误）"
    assert "empty.style.display = ''" in body, "空结果态必须可切换为可见"
    assert "MSG.tmSearchCount" in body, "命中计数必须回显"
    assert "btn.disabled = true" in body, "查询中按钮必须禁用"
    assert "btn.disabled = false" in body, "finally 必须恢复按钮"
    # 注入钩子：switchTab 打开词库页时懒注入（卡3 收编后挂 tab-glossary 分组）
    assert "TAB_HOOKS[tabId]" in _extract_function(src, "switchTab"), \
        "switchTab 须经注册表派发"
    hook = _tab_hooks_group("tab-glossary")
    assert "TmSearch.ensure()" in hook, "switchTab 缺 TM 搜索区块懒注入"


# 2.6.3 批C（D2026-1003-01 P4 拍板④）：IA 重排——引擎页三段分段控件
# 2.6.5 段2（D2026-1004-01 #3）改写：seg 外壳删除，原分段结构钉重写为
# 纵向堆叠组守卫（endpoints_summary 断言保留）；ASR/词典卡迁独立页
# tab-asrdict（新增钉，基线只增不减）
# ---------------------------------------------------------------------------

def test_batch_c_engine_stage_groups_pinned():
    """批C IA 重排守卫（2.6.5 段2 D2026-1004-01 #3 重写为堆叠组守卫）：
    原引擎页 seg 分段控件（.seg-bar/.seg-btn/.seg-page）已删除，改
    .stage-group 纵向堆叠组（阶段A→阶段B→兜底），组头纯中文零 i18n 键；
    阶段A 地址行+主保存键在 A 组，阶段B 地址行+孪生保存键（class-only
    无 id）在 B 组；接口地址卡外壳（endpoints_summary）已删除不回流。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for gone in ('class="seg-bar', 'class="seg-btn', 'class="seg-page',
                 'data-seg=', 'data-seg-page='):
        assert gone not in html, f"seg 外壳残留: {gone}"
    assert html.count('class="stage-group"') == 3, "引擎页须恰 3 组 stage-group"
    titles = re.findall(r'class="stage-group-title">([^<]+)<', html)
    assert titles == ["阶段A · 净语+翻译", "阶段B · 审校+抛光", "兜底与容错"], \
        f"堆叠组组头漂移: {titles}"
    grp_a = _slice(html, '阶段A · 净语+翻译', '阶段B · 审校+抛光')
    assert 'id="refineS1Endpoint"' in grp_a, "阶段A 地址行未迁入 A 组"
    assert 'id="refineSaveEndpointsBtn"' in grp_a, "主保存键不在 A 组"
    grp_b = _slice(html, '阶段B · 审校+抛光', '兜底与容错')
    assert 'id="refineS3Endpoint"' in grp_b, "阶段B 地址行未迁入 B 组"
    assert "endpoint-save-twin" in grp_b, "B 组缺孪生保存按钮"
    assert 'id="refineSaveEndpointsBtn"' not in grp_b, \
        "孪生保存按钮不得带 id（id 冻结预算）"
    assert "endpoints_summary" not in html, "接口地址卡外壳应随 IA 重排删除"
    # 去外壳后 JS 绑定循环一并移除（stage-group 为纯 CSS 布局零 JS）
    src = _app_js_source()
    assert ".seg-btn" not in src and ".seg-page" not in src, \
        "app.js 残留 seg 绑定（D2026-1004-01 #3 已删）"
    # CSS：.stage-group 规则在位、.seg-* 规则删净
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    assert ".stage-group {" in css and ".stage-group-title" in css, \
        "style.css 缺 .stage-group 规则组"
    assert ".seg-btn" not in css and ".seg-page" not in css, \
        "style.css 残留 .seg-* 规则"


def test_batch_c_asrdict_tab_order_pinned():
    """批C 新钉：tab-asrdict 面板在 tab-engine 面板之后；ASR 卡与词典卡
    注释整体位于 tab-asrdict 内且词典注释在 ASR 注释之后（两卡相邻）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    i_engine = html.index('id="tab-engine"')
    i_asrdict = html.index('id="tab-asrdict"')
    i_glossary = html.index('id="tab-glossary"')
    assert i_engine < i_asrdict < i_glossary, "tab-asrdict 面板必须位于 tab-engine 之后、tab-glossary 之前"
    panel = html[i_asrdict:i_glossary]
    i_asr_comment = panel.index("<!-- ASR 模型管理")
    i_dict_comment = panel.index("<!-- 词典管理")
    assert i_asr_comment < i_dict_comment, \
        "词典卡注释必须在 ASR 卡注释之后（两卡迁入次序保持）"


def test_batch_c_msg_tabengine_renamed_pinned():
    """批C 新钉：MSG.tabEngine 改值「API 与模型选择」、pipeline_card_hint
    随改、唯一静态新键 tabAsrDict=「ASR 与词典」。"""
    src = _app_js_source()
    m = re.search(r"^\s*tabEngine: '([^']*)'", src, re.M)
    assert m and m.group(1) == 'API 与模型选择', \
        f"MSG.tabEngine 值漂移: {m and m.group(1)}"
    m2 = re.search(r"^\s*pipeline_card_hint: '([^']*)'", src, re.M)
    assert m2 and m2.group(1) == '点击前往「API 与模型选择」页修改', \
        "MSG.pipeline_card_hint 未随改"
    m3 = re.search(r"^\s*tabAsrDict: '([^']*)'", src, re.M)
    assert m3 and m3.group(1) == 'ASR 与词典', "MSG 缺 tabAsrDict 静态新键"


def test_batch_c_review_goto_asrdict_pinned():
    """批C 新钉：review.js ASR 跳转锚定位 tab-asrdict，文案键随改。"""
    src = _review_js_source()
    assert 'data-tab="tab-asrdict"' in src, "review.js 跳转锚未改 tab-asrdict"
    assert "review_asr_goto: '前往 ASR 与词典页'" in src, \
        "review_asr_goto 文案未随改"
    assert "API 与模型选择页" in src, "review_asr_card 缺「API 与模型选择页」表述"


def test_pipeline_card_hint_here_pinned():
    """d1013-卡1 新钉：pipelineCard 提示态惰性求值（D2026-1012-01 ⑨）。

    - refreshPipelineCardHint 函数定义存在；
    - pipelineCard 绑定了 mouseenter 与 focus 两事件且绑定行调用该函数；
    - MSG 表含 pipeline_card_hint_here 键。
    """
    src = _app_js_source()
    # 函数定义存在
    assert "function refreshPipelineCardHint()" in src, \
        "app.js 缺少 refreshPipelineCardHint 函数定义"
    # 绑定 mouseenter 与 focus 事件且绑定行调用该函数
    assert "pipelineCard.addEventListener('mouseenter', refreshPipelineCardHint)" in src, \
        "pipelineCard 缺少 mouseenter 事件绑定"
    assert "pipelineCard.addEventListener('focus', refreshPipelineCardHint)" in src, \
        "pipelineCard 缺少 focus 事件绑定"
    # MSG 表含 pipeline_card_hint_here 键
    assert "pipeline_card_hint_here" in _js_msg_keys(), \
        "MSG 表缺少 pipeline_card_hint_here 键"


def _slice(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


# ---------------------------------------------------------------------------
# 2.6.3 批D（D2026-1003-01 P5）：角色卡编辑器弹窗（AppModal.editor + vault
# 节点搬迁）。FROZEN_IDS=215 / FROZEN_I18N_KEYS=189 零变更（vault 内既有
# id/data-i18n 原样保留，新锚全部 class+data-testid 承载，文案走 MSG JS 态
# 新键）——本批零解冻，两冻结钉（test_ui_phase3_redlines）零改动保持绿。
# ---------------------------------------------------------------------------

_BATCH_D_VAULT_IDS = (
    "refineTemplateStage", "refineTemplateReload", "refineTemplateSave",
    "refineTemplateStatus", "refineTemplateText", "refineTplLoadedPath",
    "directionSource", "directionTarget", "directionCardS1",
    "directionCardS3", "directionCardList",
)


def test_batch_d_tpl_editor_vault_structure_pinned():
    """批D 新钉①：词库页 .tpl-editor-vault 隐藏容器存在且含全部既有 frozen
    编辑器 id（refineTemplate*/refineTplLoadedPath/direction*/datalist）与
    direction 组标题；两枚一行入口（class+data-testid 承载零 id）+入口状态
    span；高级参数页原位留指引行且 direction 组已不在高级页。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'class="tpl-editor-vault" hidden' in html, "缺 .tpl-editor-vault 隐藏容器"
    start = html.index('class="tpl-editor-vault"')
    end = html.index('id="tab-guide"', start)
    vault = html[start:end]
    for dom_id in _BATCH_D_VAULT_IDS:
        assert f'id="{dom_id}"' in vault, f"vault 缺既有 frozen id: {dom_id}"
    assert 'data-i18n="tpl_editor_summary"' in vault, "vault 缺编辑区标题键"
    assert 'data-i18n="direction_block_title"' in vault, \
        "direction 组标题未随组迁入 vault"
    # 两枚入口按钮：class 同名承载（词库页+高级参数页），零 id
    assert html.count("tpl-editor-entry-btn") == 2, "编辑器入口应恰两枚"
    for tid in ("tpl-editor-entry-row", "tpl-editor-entry",
                "tpl-entry-status", "tpl-entry-hint",
                "tpl-editor-entry-adv", "direction-moved-hint"):
        assert f'data-testid="{tid}"' in html, f"缺批D新锚 data-testid: {tid}"
    for btn in re.findall(r'<button[^>]*tpl-editor-entry-btn[^>]*>', html):
        assert ' id="' not in btn, "入口按钮不得携带 id（FROZEN_IDS 冻结）"
    # 高级页切片：指引行在位、direction 组已迁出、入口按钮在位
    adv = html[html.index('id="tab-advanced"'):html.index('id="tab-review"')]
    assert "翻译方向与角色卡设置已并入角色卡编辑器" in adv, "高级页缺指引行"
    assert 'data-testid="tpl-editor-entry-adv"' in adv, "高级页缺入口按钮"
    for dom_id in ("directionSource", "directionTarget", "directionCardS1",
                   "directionCardS3", "directionCardList"):
        assert f'id="{dom_id}"' not in adv, f"direction 组未迁出高级页: {dom_id}"


def test_batch_d_app_modal_editor_pinned():
    """批D 新钉②：AppModal.editor 定义在位——.modal-lg 大卡、modal-editor
    body、节点搬入（appendChild）/搬回（_editorStash 原序复位）、textarea
    dirty 监听（_edDirty）；_settle 编辑器分支（保存中 no-op 同 _dlRunning
    先例 + dirty 走 _editorDiscardGuard）；守卫经 AppModal.confirm 确认；
    保存收口（editorRunSave 成功清脏自动关闭/失败弹窗保持）。"""
    src = _app_js_source()
    body = _extract_function(src, "editor")
    assert "modal-lg" in body, "编辑器打开必须挂 .modal-lg 大卡"
    assert "modal-editor-body" in body, "body 必须挂 .modal-editor-body"
    assert "_editorUnstash" in body, "节点必须按原序搬入 modal-body"
    assert "MSG.tplEditorTitle" in body, "弹窗标题必须走 MSG 新键"
    unstash = _extract_function(src, "_editorUnstash")
    assert "editor-ta-wrap" in unstash and "appendChild" in unstash, \
        "textarea 必须在搬入时包 .editor-ta-wrap 弹性层"
    assert "refineTemplateSave" in body and "editorRunSave" in body, \
        "保存键必须走弹窗感知路径"
    assert "refineTemplateReload" in body and \
        "refineTemplateStage" in body and "editorRunStageChange" in body, \
        "重载/切阶段必须走弹窗感知路径"
    assert "addEventListener('input'" in body, "textarea 缺 dirty input 监听"
    stash = _extract_function(src, "_editorStash")
    assert "appendChild" in stash, "关闭必须把节点按原序 append 回 vault"
    settle = _extract_function(src, "_settle")
    assert "this._kind === 'editor' && this._edSaving" in settle, \
        "保存进行中 _settle 必须 no-op（同 _dlRunning 先例）"
    assert "this._editorDiscardGuard()" in settle, \
        "dirty 关闭必须走放弃确认守卫"
    guard = _extract_function(src, "_editorDiscardGuard")
    assert "MSG.tplEditorDirtyConfirm" in guard, \
        "放弃守卫必须经确认弹窗（_editorConfirmWhileOpen）"
    confirm_open = _extract_function(src, "_editorConfirmWhileOpen")
    assert "AppModal.confirm" in confirm_open and "MSG.ui_cancel" not in confirm_open, \
        "守卫确认必须复用 AppModal.confirm 单例"
    run_save = _extract_function(src, "editorRunSave")
    assert "_edSaving" in run_save, "保存进行中必须置 _edSaving"
    assert "MSG.tplEditorSaveOk" in run_save and "MSG.tplEditorSaveFailed" in run_save, \
        "保存结果文案键缺失"
    assert "this._settle(false)" in run_save, "保存成功必须自动关闭"
    keys = _js_msg_keys()
    for key in ("tplOpenEditor", "tplEditorTitle", "tplEditorDirtyConfirm",
                "tplEditorSaveOk", "tplEditorSaveFailed"):
        assert key in keys, f"MSG 缺少批D新键: {key}"


def test_appmodal_unified_skeleton_binding_pinned():
    """2.8.0.2「首绑互窃」根治钉：AppModal 骨架一次性绑定收敛为唯一一处
    kind 感知绑定（_bindSkeletonOnce，dataset.bound 守卫）——原各模态方法
    各自携带绑定块、运行时只注册首个打开模态的那一份，而各块 ok/Enter 语义
    互异（editor/tmEdit 排除 Enter、encode ok 结算 params），首绑归属谁后续
    所有模态骨架语义即被定格（实锤：tmEdit 先开后批量修复确认框 okBtn 零
    处理器，「开始修复」无反应）。本钉取代原批D「Enter 分支逐块排除」钉：
    ① 全文件 root.dataset.bound 赋值恰一处且在 _bindSkeletonOnce 内，
       逐模态绑定块绝迹；
    ② 七个模态打开路径（_open/download/editor/models/encode/
       batchFixPreview/tmEdit）逐一含 _bindSkeletonOnce(root)（首开是谁
       都由它补绑）；
    ③ Enter/ok 语义矩阵（_okValue 事件时刻读 _kind）：tmEdit/editor/
       download/models → undefined（no-op，tmEdit/editor textarea 回车=
       换行不提交，download 无确认语义）；prompt → 输入值；encode →
       {ok:true, params:_encodeCollect()}；其余（alert/confirm/batchfix）
       → true（确认）；
    ④ keydown ESC 一律 _cancelValue()（download 下载中 no-op 与 editor/
       tmEdit 脏态放弃确认由 _settle 既有分支承接）；Enter 仅分派有值时
       preventDefault+_settle（no-op kind 的回车默认行为不被吞）；
    ⑤ encode 生命周期：打开赋 _encodeCollect、结算置 null 防悬挂引用，
       okBtn.onclick 自绑绝迹（统一分派承接）。"""
    src = _app_js_source()
    binder = _extract_function(src, "_bindSkeletonOnce")
    okv = _extract_function(src, "_okValue")
    # ① 唯一绑定块
    assert src.count("root.dataset.bound = '1'") == 1, \
        "root.dataset.bound 赋值必须恰一处（首绑互窃根源回归）"
    assert "root.dataset.bound = '1'" in binder, \
        "唯一赋值必须在 _bindSkeletonOnce 内"
    assert "root.dataset.bound" in binder, "守卫必须在 _bindSkeletonOnce 内"
    assert "if (!root.dataset.bound)" not in src, \
        "逐模态绑定块必须绝迹（首绑互窃根源）"
    # ② 七个打开路径逐一补绑
    for method in ("_open", "download", "editor", "models", "encode",
                   "batchFixPreview", "tmEdit"):
        body = _extract_function(src, method)
        assert "_bindSkeletonOnce(root)" in body, \
            f"{method} 打开路径缺 _bindSkeletonOnce(root)（首开互窃回归）"
    # ③ kind→语义矩阵
    assert "this._kind === 'tmEdit' || this._kind === 'editor'" in okv \
        and "this._kind === 'download' || this._kind === 'models'" in okv \
        and "return undefined;" in okv, \
        "矩阵缺 no-op 分支（tmEdit/editor Enter 不提交、download/models 无确认语义）"
    assert "this._kind === 'prompt') return (input && input.value)" in okv, \
        "prompt 须带输入值结算"
    assert "this._kind === 'encode'" in okv and "_encodeCollect" in okv \
        and "{ ok: true, params: collect() }" in okv, \
        "encode 须按当前表单结算 {ok, params}（collect 经 _encodeCollect）"
    assert "return true;" in okv, \
        "其余 kind（alert/confirm/batchfix）须确认结算 true"
    # ④ keydown 收口
    assert "e.key === 'Escape'" in binder \
        and "AppModal._settle(AppModal._cancelValue())" in binder, \
        "ESC 须一律取消结算（脏态/下载中守卫由 _settle 承接）"
    assert "e.key === 'Enter'" in binder and "v !== undefined" in binder, \
        "Enter 须按分派结算（undefined no-op 且不 preventDefault）"
    # ⑤ encode collect 生命周期
    enc = _extract_function(src, "encode")
    assert "this._encodeCollect = collect;" in enc, "encode 打开须暴露 collect"
    assert "this._encodeCollect = null;" in enc, "结算须置 null（防悬挂引用）"
    assert "okBtn.onclick" not in enc, \
        "encode 不得再自绑 okBtn.onclick（统一分派承接，防双结算）"


def test_batch_d_tpl_editor_entry_and_on_save_pinned():
    """批D 新钉③：两枚入口按钮 bindDom 绑 openTplEditor 并 JS 态填文案；
    onSave 复用 tplSave（refine_save_template 四参形态函数钉保持）；
    onStageChange 走原链路（reload=tplRefreshSelect / change=tplLoad）。"""
    src = _app_js_source()
    bind = _extract_function(src, "bindDom")
    assert "tpl-editor-entry-btn" in bind and "MSG.tplOpenEditor" in bind, \
        "bindDom 缺编辑器入口绑定与文案填充"
    assert "openTplEditor" in bind, "入口必须绑定 openTplEditor"
    opener = _extract_function(src, "openTplEditor")
    assert "AppModal.editor(" in opener, "入口必须打开 AppModal.editor"
    assert "onSave: tplSave" in opener, "onSave 必须复用 tplSave"
    assert "tplRefreshSelect(true)" in opener and "tplLoad()" in opener, \
        "onStageChange 必须走原加载链路"
    save = _extract_function(src, "tplSave")
    assert "refine_save_template(" in save and "isStageTag ? null : idx" in save, \
        "refine_save_template 四参形态函数钉必须保持"
    assert "{ ok:" in save and "message:" in save, \
        "tplSave 必须返回 {ok, message} 供模态收口"


def test_batch_d_css_modal_lg_pinned():
    """批D 新钉④：style.css .modal-lg（min(720px, 92vw)/88vh）+ 编辑器
    body 弹性布局（flex column/overflow auto）+ .editor-ta-wrap（240px
    下限）+ 弹窗内 .tpl-goto-btn 隐藏（跳转语义在弹窗内冗余）。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    m = re.search(r"\.modal-card\.modal-lg \{[^}]*\}", css)
    assert m, "缺 .modal-card.modal-lg 规则"
    assert "min(720px, 92vw)" in m.group(0) and "88vh" in m.group(0), \
        ".modal-lg 尺寸数值漂移"
    m2 = re.search(r"\.modal-card\.modal-lg \.modal-body \{[^}]*\}", css)
    assert m2, "缺编辑器 body 规则"
    assert "flex-direction: column;" in m2.group(0) and "overflow: auto;" in m2.group(0) \
        and "min-height: 0;" in m2.group(0), "编辑器 body 弹性布局不完整"
    m3 = re.search(r"\.editor-ta-wrap \{[^}]*\}", css)
    assert m3 and "min-height: 240px" in m3.group(0), "缺 .editor-ta-wrap 240px 下限"
    assert re.search(r"\.modal-body \.tpl-goto-btn \{[^}]*display: none;", css), \
        "弹窗内 .tpl-goto-btn 必须隐藏"
    assert re.search(r"@media \(max-width: 768px\)[\s\S]*\.modal-card\.modal-lg",
                     css), "缺小屏响应微调"


# ---------------------------------------------------------------------------
# 2.7.3 件③（D2026-1005）：ASR 状态三口径对齐 + 词典下载缓解引导
# ---------------------------------------------------------------------------

def test_asr_status_three_view_alignment_pinned():
    """件③回归钉：红绿灯/下拉/摘要卡三处 UI 口径对齐，空态不得假显 large-v2。

    人工推演（假选中场景）：asrRefresh 清空重建下拉后仅在有 saved 且命中
    本机清单时设 sel.value；saved 空时不设值 → 浏览器默认选中第一项
    option = 用户未选却显示已选（假选中）；红绿灯 saved 空时硬编码兜底
    'large-v2' 同属假显（后端 CLI 不带 --asr-model 缺省 large-v2 是合法
    降级，asr_runner/quality_advisor 不动，本件只修 UI 诚实性）：
    - 红绿灯 asrApplyEnvStatus：兜底改 MSG.asrModelUnselected；
    - 下拉 asrRefresh：saved 空/不在清单时显式 sel.value='' + JS 渲染
      占位 option（MSG.asrModelPlaceholder，零静态 id/data-i18n——
      FROZEN_IDS=213 / i18n=189 既有钉零改动）；
    - change 处理器（bindDom 内 asrSel 链）：空值守卫（评议员条件⑥）
      ——占位空值不保存、不覆盖既有 saved_model（占位项恰为当前选中
      时点选=空操作）；
    - 摘要卡 probeAsr：model_present && saved_model 双门控本已诚实，
      失败三分支 asrProbeFail 恰 3 次口径不变（防连带漂移复述钉）。
    """
    src = _app_js_source()
    apply_body = _extract_function(src, "asrApplyEnvStatus")
    assert "'large-v2'" not in apply_body, \
        "红绿灯残留 large-v2 硬编码兜底（saved 空时假显已选模型）"
    assert "MSG.asrModelUnselected" in apply_body, \
        "红绿灯 saved 空态须走 MSG.asrModelUnselected"
    refresh = _extract_function(src, "asrRefresh")
    assert "sel.value = ''" in refresh, \
        "下拉 saved 空态须显式归零选中（消灭浏览器默认选中第一项的假选中）"
    assert "MSG.asrModelPlaceholder" in refresh, "下拉占位 option 须挂新键文案"
    assert "createElement('option')" in refresh, \
        "占位 option 必须 JS 渲染（零静态 id/data-i18n）"
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "asrModelPlaceholder" not in html and "asrModelUnselected" not in html, \
        "件③新键文案不得静态写入 index.html"
    bind = _extract_function(src, "bindDom")
    assert re.search(r"asrSel\.value === ''\s*\)\s*return", bind), \
        "asrSel change 缺空值守卫（占位空值不得写回 saved_model，评议员条件⑥）"
    keys = _js_msg_keys()
    for key in ("asrModelUnselected", "asrModelPlaceholder"):
        assert key in keys, f"MSG 缺少件③新键: {key}"
        m = re.search(rf"^\s*{key}:\s*'([^']*)'", src, re.M)
        assert m and m.group(1), f"MSG 键 {key} 文案为空"
    # 摘要卡口径不变：probeAsr 失败三分支 asrProbeFail 恰 3 次（既有钉复述）
    probe = _extract_function(src, "probeAsr")
    assert probe.count("MSG.asrProbeFail") == 3, \
        "摘要卡 asrProbeFail 三分支口径漂移（件③不得增删）"
    # 词典下载缓解引导（D 缓解）：三点核心信息在既有 hint 键文案内
    assert "dict_install_hint" in keys, "MSG 缺 dict_install_hint 键"
    assert "两跳" in src and "--dict-from-file" in src and "切换镜像" in src, \
        "dict_install_hint 缺下载缓解引导（两跳自动/镜像切换/离线导入）"


# ---------------------------------------------------------------------------
# 2.7.3 件⑥（D2026-1006-01）：P1 启动缺陷修复——顶层 refreshPipelineMirror
# 引用 Refine UI IIFE 私有 $ 导致两条启动链整体中断
# ---------------------------------------------------------------------------

def test_startup_chain_not_killed_by_scope_leak():
    """件⑥回归钉：顶层函数不得引用 IIFE 私有 $（词法作用域按定义位置解析）。

    人工推演（启动炸链场景）：refreshPipelineMirror 定义在顶层（:6082），
    函数体内 $('refineS1Model') 按词法作用域解析——顶层无 $ 定义（$ 是
    Refine UI IIFE 内私有函数），无论从哪调用都抛 ReferenceError：
    - 链A（DOMContentLoaded）：:6055 调用即炸 → 其后的 change 绑定、
      pipelineCard 绑定、MSG.gui_initialized 完成提示全部不可达；
    - 链B（pywebviewready）：await __refineLoadRemote → IIFE 内 loadRemote
      调用同一函数同样炸 → await reject → FeatureStatus.init()（语法徽章）
      与 3s ASR 预热全被跳过。
    修复=两处改 document.getElementById(...)（顶层合法 API，语义不变）。
    """
    source = _app_js_source()

    # 断言1 钉根因：refreshPipelineMirror 函数体不再含 $('，改走
    # document.getElementById（pipelineMirrorLine 镜像载体 + 两配置项读取）
    body = _extract_function(source, "refreshPipelineMirror")
    assert "$('" not in body, \
        "refreshPipelineMirror 顶层函数体内不得引用 IIFE 私有 $（D2026-1006-01 件⑥）"
    assert "document.getElementById('pipelineMirrorLine')" in body, \
        "镜像载体读取应保留 document.getElementById('pipelineMirrorLine')"
    assert "document.getElementById('refineS1Model')" in body, \
        "模型值必须经 document.getElementById('refineS1Model') 读取"
    assert "document.getElementById('refineConcurrency')" in body, \
        "并发值必须经 document.getElementById('refineConcurrency') 读取"

    # 断言2 钉作用域审计：全文件 $(' 的出现必须全部落在 Refine UI IIFE
    # 区间内（从含 window.__refineUI 哨兵的行到其后第一个列首 })(); 行）。
    # 等价判据：全文件出现总数 == 区间内出现总数（且 >0 自证提取有效）——
    # 任何顶层（或非 Refine IIFE 区间）新增 $(' 引用都会使总数 > 区间数。
    sentinel = source.index("window.__refineUI")
    end_m = re.search(r"^\}\)\(\);", source[sentinel:], re.M)
    assert end_m, "未找到 Refine UI IIFE 终点（列首 })();）"
    iife_seg = source[sentinel:sentinel + end_m.start()]
    total = source.count("$('")
    inner = iife_seg.count("$('")
    assert total > 0, "自证失败：未提取到任何 $(' 出现（判据失效）"
    assert total == inner, (
        "顶层不得引用 IIFE 私有 $（D2026-1006-01 件⑥）："
        f"全文件 $(' 出现 {total} 处，Refine UI IIFE 区间内仅 {inner} 处，"
        "区间外存在词法作用域致死引用"
    )

    # 断言3 钉链A 可达：顶层 DOMContentLoaded 回调内 refreshPipelineMirror()
    # 调用必须位于 MSG.gui_initialized 之前且同区间——镜像调用不再是
    # 区间末尾的致死点（其后仍有完成提示、控件绑定等可达语句）
    m = re.search(
        r"^document\.addEventListener\('DOMContentLoaded'[\s\S]*\Z",
        source, re.M)
    assert m, "未找到顶层 DOMContentLoaded 注册"
    chain_a = m.group(0)
    assert "refreshPipelineMirror()" in chain_a, \
        "链A 必须保留镜像调用 refreshPipelineMirror()"
    assert "MSG.gui_initialized" in chain_a, \
        "链A 必须保留初始化完成提示"
    assert chain_a.index("refreshPipelineMirror()") \
        < chain_a.index("MSG.gui_initialized"), \
        "镜像调用必须位于 MSG.gui_initialized 之前（同一可达区间，链A 不得在镜像处中断）"

    # 断言4 钉链B 完整：pywebviewready 回调内 FeatureStatus.init（语法徽章）
    # 与 setTimeout 3000 ASR 预热（refine_asr_status）必须保留——await
    # __refineLoadRemote 异常不再吞掉后续初始化
    m = re.search(r"window\.addEventListener\('pywebviewready'[\s\S]*\Z",
                  source)
    assert m, "未找到 pywebviewready 注册"
    chain_b = m.group(0)
    assert "FeatureStatus.init" in chain_b, \
        "pywebviewready 链必须调用 FeatureStatus.init（语法徽章初始化）"
    assert "refine_asr_status" in chain_b and "3000" in chain_b, \
        "pywebviewready 链必须保留 setTimeout 3000 ASR 预热（refine_asr_status）"


# ---------------------------------------------------------------------------
# 2.7.3 件⑦（D2026-1006-01）：翻译期 Console 流断防御——显示链生命线
# 重排（轮询先行、原始日志通道与 status 桥解耦）
# ---------------------------------------------------------------------------

def test_start_translation_polling_before_started_log():
    """startTranslation 成功分支必须轮询先行，打点异常不拖垮显示链生命线。

    人工推演（D2026-1006-01 件⑦）：ConsoleManager.log(translationStarted)
    若抛错会跳过 startStatusPolling——状态栏/进度/收尾判断全部失联（显示链
    生命线单点）。修复后 startStatusPolling() 先行，打点包 try/catch 仅降级
    为 console.warn，轮询启动不再受打点异常影响。
    """
    body = _extract_function(_app_js_source(), "startTranslation")
    assert "this.startStatusPolling()" in body, \
        "成功分支必须启动状态轮询（显示链生命线）"
    assert "MSG.translationStarted" in body, \
        "成功分支必须保留 translationStarted 打点"
    assert body.index("this.startStatusPolling()") \
        < body.index("MSG.translationStarted"), \
        "startStatusPolling() 必须位于 MSG.translationStarted 之前（轮询先行）"
    # 打点必须防弹：try/catch 包裹，异常仅 console.warn
    guard = re.search(
        r"try\s*\{[^}]*MSG\.translationStarted[\s\S]*?\}\s*catch", body)
    assert guard, "translationStarted 打点必须包 try/catch（打点异常不外溢）"


def test_status_polling_fetch_logs_decoupled_from_status_bridge():
    """startStatusPolling 内 fetchLogs 必须移出 status try 块（通道解耦）。

    人工推演（D2026-1006-01 件⑦）：fetchLogs 嵌在 status 桥的 try 块内时，
    get_translation_status 每拍异常都会连带跳过 fetchLogs——status 桥故障
    即原始日志通道死（Console 完全无输出）。修复后 fetchLogs 位于 catch
    之后（回调体末尾、done/error/cancelled 收尾判断之外），且自身自带
    try/catch，不再依赖 status 每拍成功。
    """
    body = _extract_function(_app_js_source(), "startStatusPolling")
    assert body.count("this.fetchLogs()") == 1, \
        "fetchLogs 在轮询回调内只允许出现一次"
    assert "catch" in body, "status 桥必须保留 try/catch"
    assert body.index("this.fetchLogs()") > body.index("catch"), \
        "fetchLogs 必须位于 catch 之后（原始日志通道与 status 桥解耦）"


# ---------------------------------------------------------------------------
# 2.7.3 件⑧批 8b（D2026-1006-01）：Console 结构化活动流 + 显示层 500 行
# 环形裁剪（定版 D4：裁剪仅显示层）+ 原始日志折叠默认收起并持久化。
# 后端批 8a 前置：get_translation_status 透出 files_status 四态
# （pending/running/done/failed）与 task_summary（task_finished payload）。
# ---------------------------------------------------------------------------

def _console_manager_region(source: str) -> str:
    """ConsoleManager 为对象字面量（非函数），_extract_function 不可用——
    按「const ConsoleManager = {」到「const ActivityStream = {」切片。"""
    return _slice_source(
        source, "const ConsoleManager = {", "const ActivityStream = {")


def _activity_stream_region(source: str) -> str:
    """ActivityStream 区间：到其后 Progress Management 段头注释为止。"""
    return _slice_source(
        source, "const ActivityStream = {",
        "// Progress Management (progress bar inside the refine panel)")


def _slice_source(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


def test_batch_8b_activity_stream_and_console_trim_pinned():
    """批 8b 回归钉：活动流差分打点接线、显示层裁剪、折叠持久化四线齐钉。

    人工推演（D2026-1006-01 件⑧批 8b）：
    - 长任务下 Console DOM 无界增长（每秒 appendRaw）会拖垮渲染——裁剪
      只裁 DOM 不动会话内全量 `_lines`（导出/复制仍取全量）；
    - 风险增量打点自 TranslatorManager 迁入 ActivityStream（旧
      _reportedRiskCount 段删除，Console 区不再重复打风险行）；
    - 原始日志默认收起（定版 D4）并经 localStorage 键持久化，无记录时
      init 写入默认值。
    """
    source = _app_js_source()

    # 断言1 钉活动流存在与接线：const ActivityStream 定义存在，且
    # startStatusPolling 每拍调用 ActivityStream.update(
    assert "const ActivityStream" in source, "app.js 缺少 ActivityStream 定义"
    polling = _extract_function(source, "startStatusPolling")
    assert "ActivityStream.update(" in polling, \
        "startStatusPolling 必须每拍调用 ActivityStream.update(status)"
    # 风险打点迁移钉：轮询区间不再含旧计数段（迁入 ActivityStream 后
    # 该标识只允许出现在其定义区注释里）
    assert "_reportedRiskCount" not in polling, \
        "startStatusPolling 旧风险打点段应已迁出（_reportedRiskCount 残留）"
    assert "_riskCount" in _activity_stream_region(source), \
        "ActivityStream 区间应承接风险增量计数（_riskCount）"

    # 断言2 钉显示层裁剪（定版 D4：只裁 DOM 不动 _lines）：
    # ConsoleManager 区间含 500 上限常量 + removeChild/firstChild 组合，
    # 且 _lines 由 log 与 appendRaw 双入口 push（会话内全量保留）
    cm = _console_manager_region(source)
    assert "_MAX_DOM_LINES: 500" in cm, "ConsoleManager 缺 500 行显示层上限"
    assert "removeChild" in cm and "firstChild" in cm, \
        "裁剪应从最旧行开始移除（removeChild(firstChild) 组合）"
    assert cm.count("this._lines.push") >= 2, \
        "_lines 必须由 log 与 appendRaw 逐行 push（会话内全量保留）"
    assert "this._lines = []" in cm, "clear() 必须同步清空 _lines"

    # 断言3 钉导出/复制：全量数组导出（Blob）与 clipboard 降级链
    # （源码匹配用 \\n：app.js 字面量为 join('\n')，Python 串需转义反斜杠）
    assert "join('\\n')" in cm and "Blob" in cm, \
        "导出必须取 _lines 全量（join 后包 Blob，而非裁剪后的 DOM 残行）"
    assert "subtrans-console-" in cm, "导出文件名前缀缺失"
    assert "writeText" in cm and "execCommand('copy')" in cm, \
        "复制必须先 clipboard API 后 textarea+execCommand 降级"

    # 断言4 钉原始日志弹窗化（五轮，D2026-1010-01：内联展开受 Console 区
    # 380px 上限挤压无法下翻——owner 实证；折叠持久化机制随载体退场）
    assert "openRawLogModal" in cm, "原始日志须弹窗化（openRawLogModal）"
    assert "AppModal.rawLog(" in source, "AppModal 须有 rawLog 大卡模态"
    assert "subtrans_rawlog_collapsed" not in cm, \
        "折叠持久化机制须随内联展开退场"
    assert "_liveRawLogLine" in cm, \
        "弹窗打开期间新行须实时追加（_liveRawLogLine）"
    assert "rawlog-view" in source, "弹窗内须有可滚动日志列表容器"
    # 未读徽标条件迁移：弹窗打开期不计数（经 AppModal._kind 判定）
    bump = _extract_function(cm, "_bumpRawLogUnread")
    assert "rawlog" in bump, "未读计数须以弹窗打开态为豁免条件"

    # 断言5 钉 i18n 冻结：四个新 DOM 锚存在且全部零 data-i18n（文案
    # 由 JS init 时以 MSG 填充）；活动流行载体存在
    html = INDEX_HTML.read_text(encoding="utf-8")
    for dom_id in ("consoleActivity", "rawLogToggleBtn",
                   "exportConsoleBtn", "copyConsoleBtn"):
        assert f'id="{dom_id}"' in html, f"index.html 缺少锚点: {dom_id}"
    for dom_id in ("consoleActivity", "rawLogToggleBtn",
                   "exportConsoleBtn", "copyConsoleBtn"):
        m = re.search(rf'<[^>]*id="{dom_id}"[^>]*>', html)
        assert m and "data-i18n" not in m.group(0), \
            f"{dom_id} 不得携带 data-i18n（i18n 键冻结中，文案 JS 态承接）"

    # 断言6 钉新任务新流：startTranslation 成功分支清空活动流
    start_body = _extract_function(source, "startTranslation")
    assert "ActivityStream.reset()" in start_body, \
        "startTranslation 成功分支必须清空活动流（新任务新流）"
    assert start_body.index("ActivityStream.reset()") \
        < start_body.index("this.startStatusPolling()"), \
        "活动流清空必须位于轮询启动之前（旧流残行不进新任务）"


# ---------------------------------------------------------------------------
# 2.7.4 件3（D2026-1007-01）：批量修复确认框完整化（AppModal.batchFixPreview）
# 原纯文本 AppModal.confirm 只列前 10 条（slice(0,10)+"…其余 N 条省略"），
# 改结构化弹窗：元信息区+分类 chips（数量降序）+全条目滚动列表+现译全文
# （lastGuideData 已持有导读 json；后端摘录限长仅约束回包形状）。
# ---------------------------------------------------------------------------
def test_batch_fix_preview_modal_pinned():
    """AppModal.batchFixPreview：结构化 body 全 createElement 注入（零新增
    id/data-i18n）+ .modal-lg 滚动配方 + 回退标记 + 全文不 JS 切字符串。"""
    src = _app_js_source()
    assert "batchFixPreview(opts)" in src, "AppModal.batchFixPreview 缺失"
    body = _extract_function(src, "batchFixPreview")
    assert "createElement" in body, "弹窗 body 须 createElement 注入"
    assert "bfp-meta" in body and "bfp-cats" in body and "bfp-list" in body, \
        "元信息区/分类 chips/滚动列表三段结构缺失"
    assert "bfp-cat-chip" in body, "分类 chip 缺失"
    assert "bfp-item-head" in body and "bfp-idx" in body and "bfp-timing" in body, \
        "条目头行（编号+chip+timing）缺失"
    assert "modal-lg" in body, ".modal-lg 弹性滚动配方缺失"
    assert "_bindSkeletonOnce(root)" in body, \
        "须走统一骨架绑定（2.8.0.2 互窃根治：kind 感知分派，首绑不锁语义）"
    # 结算三态：_busy 重入=resolve(false)（取消/ESC/遮罩走 _cancelValue=false）
    assert "if (this._busy) return Promise.resolve(false);" in body, \
        "_busy 重入必须立即 resolve(false)（单例不叠加）"
    # 全文匹配键 Number 强转 + null 先判（防 Number(null)=0 陷阱）+回退标记
    assert "Number(it.index)" in body, "匹配键必须 Number 强转比对"
    assert "hasOwnProperty.call(texts" in body, "全文查无回退分支缺失"
    assert "MSG.batchFixExcerptOnly" in body, "「仅摘录」回退标记缺失"
    assert "MSG.batchFixExpand" in body and "MSG.batchFixCollapse" in body, \
        "展开全文/收起切换文案缺失"
    assert "txt.title = text" in body, "现译须 title 悬停全文"
    assert ".slice(0" not in body, "弹窗内不得 JS 切字符串（防代理对切半）"
    # 全文进 DOM：文本节点取自 texts/回退摘录的完整串
    assert "String(texts[idx])" in body and "String(it.excerpt" in body, \
        "现译全文/回退摘录必须整串写入 DOM"
    # kind 隔离：_settle 不含 batchfix 阻塞分支（关闭永不阻塞）
    settle = _extract_function(src, "_settle")
    assert "_kind === 'batchfix'" not in settle, \
        "batchfix kind 不得进 _settle 阻塞守卫"
    # 短文本噪音清理（2.7.4 件3 黑盒走查修订）：渲染后收尾 pass 移除未
    # 实际折叠条目的展开键（scrollHeight<=clientHeight+1 → remove 非隐藏）
    assert "scrollHeight" in body and "clientHeight + 1" in body, \
        "折叠生效检测判据缺失（scrollHeight > clientHeight + 1）"
    assert "querySelectorAll('.bfp-item')" in body, "逐条收尾检测缺失"
    assert "toggle.remove()" in body, "未折叠条目须移除（非隐藏）展开键"
    # 检测必须在 display:flex 之后（display:none 下两值恒 0 会误杀全部按钮）
    assert body.index("root.style.display = 'flex'") \
        < body.index("scrollHeight"), \
        "折叠检测必须位于显示之后（display:none 下判据失效）"


def test_batch_fix_run_uses_structured_preview():
    """batchFixRun 改调 AppModal.batchFixPreview：不再 slice(0,10) 截断、
    分类明细按数量降序（设计取舍）、全文 textMap 取自 lastGuideData；
    AppModal.confirm 其余调用点数量不变（app.js 7 处）。"""
    src = _app_js_source()
    caller = _extract_function(src, "batchFixRun")
    assert "AppModal.batchFixPreview(" in caller, "须改调结构化弹窗"
    assert "AppModal.confirm" not in caller, \
        "批量修复确认不得回退纯文本 confirm"
    assert "slice(0, 10)" not in caller, "预览列表不得只列前 10 条"
    assert "slice(0, 50)" in caller, "50 条单批上限逻辑必须保留"
    assert "lastGuideData" in caller, "全文 textMap 须取自已加载导读"
    assert "catCount[b] - catCount[a]" in caller, \
        "分类明细必须按数量降序（设计取舍，非字母序）"
    assert "Number.isFinite(k)" in caller, "textMap 键须 Number 强转守卫"
    # confirm 其余调用点零变化（原 7 处，2.7.4 件C 迁走批量修复一处→余 6；
    # 2.8.0 批1 EncodeDock 新增 4 处→10；批2 预设删除确认 +1→11；
    # P3（D2026-1008-02）tmEdit 脏态守卫 +1→12，editor 守卫先例同款；
    # 3.0 批2（D2026-1009-02 批2）一键回滚确认框 +1→13）
    assert src.count("AppModal.confirm(") == 13, \
        "AppModal.confirm 调用点数量漂移（增删须显式改钉并回评议）"


def test_batch_fix_effective_line_pinned():
    """2.7.4 件C（D2026-1007-02）：修复生效配置常驻明示行。

    - index.html 静态锚 #batchFixEffectiveLine（FROZEN_IDS 217→218 显式
      解冻，批准依据=决策 D2026-1007-02），零 data-i18n（JS 态键承接）；
    - bfRefreshEffective 调后端 refine_preview_fix_config（C7 桥，与修复
      子进程同一解析结果），拒绝分支红色 status-err 直显原因；
    - batchFixRefresh 每次刷新同步明示行（载入导读/修复结束共用）；
    - batchFixRun 打开确认框前 await 取回生效配置进 meta 副行。"""
    src = _app_js_source()
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="batchFixEffectiveLine"' in html, \
        "index.html 缺少 #batchFixEffectiveLine 明示行锚"
    m = re.search(r'<div id="batchFixEffectiveLine"[^>]*>', html)
    assert m and "data-i18n" not in m.group(0), \
        "明示行不得带静态 data-i18n（文案走 JS 态 MSG 键）"
    eff = _extract_function(src, "bfRefreshEffective")
    assert "refine_preview_fix_config" in eff, \
        "明示行必须调 refine_preview_fix_config（与修复子进程同一解析）"
    assert "status-err" in eff, "拒绝分支必须红色 status-err 直显原因"
    assert "MSG.batchFixUsing" in eff and "MSG.batchFixModelUnset" in eff, \
        "明示行文案必须走 MSG 键"
    refresh = _extract_function(src, "batchFixRefresh")
    assert "bfRefreshEffective()" in refresh, \
        "batchFixRefresh 须同步刷新明示行（载入导读/修复结束共用）"
    caller = _extract_function(src, "batchFixRun")
    assert "await bfRefreshEffective()" in caller, \
        "batchFixRun 打开确认框前须刷新并取回生效配置"
    assert "fixCfgMeta" in caller, "确认框 meta 缺少生效配置副行"


def test_p2_cloud_warn_by_analysis_provider():
    """矩阵⑥ 云端/本地警示（D2026-1008-02 P2/C7）：修复确认弹窗云端
    判定与展示改按生效分析 provider（analyzeResolution().effProvider），
    弃 refineS3Provider 阶段B 口径；refineAiAnalyze 云确认同源；修复
    执行/复验传参走单源 helper（provider/model 同一键）。"""
    src = _app_js_source()
    run = _extract_function(src, "batchFixRun")
    assert "refineS3Provider" not in run, \
        "修复确认弹窗仍按阶段B 判云端（C7 违约：预览/执行不同源）"
    assert "analyzeResolution()" in run, "修复确认/执行须走单源解析"
    assert "isAiCloudProvider(fixRes.effProvider)" in run, \
        "云端警示判定字段须=analyzeResolution 生效 provider"
    assert "runRes.provider" in run and "runRes.model" in run, \
        "修复执行传参须=单源解析 provider/model"
    ana = _extract_function(src, "refineAiAnalyze")
    assert "AI_CLOUD_PROVIDERS.includes(res.effProvider)" in ana, \
        "分析云确认须按 analyzeResolution 生效 provider 判定"
    assert "refine_ai_analyze(\n        rp, res.model, res.provider)" in ana, \
        "分析发起传参须=单源解析 provider/model"


def test_batch_fix_preview_msg_and_css_pinned():
    """新 MSG 键存在；死键清理（batchFixPreviewMore 仅原弹窗一处消费，
    batchFixCats 被 chips 取代）；style.css bfp 族在位且全 token 零硬编码色。"""
    src = _app_js_source()
    keys = _js_msg_keys()
    for key in ("batchFixConfirmOk", "batchFixExpand", "batchFixCollapse",
                "batchFixExcerptOnly", "batchFixPreviewHead",
                "batchFixEstimate", "batchFixProvider", "batchFixCapHit",
                "batchFixCloudCost",
                # 2.7.4 件C（D2026-1007-02）：修复生效配置明示行两键
                "batchFixUsing", "batchFixModelUnset"):
        assert key in keys, f"MSG 缺少 2.7.4 件3 键: {key}"
    for dead in ("batchFixPreviewMore", "batchFixCats"):
        assert dead not in keys, f"2.7.4 件3 死键残留: {dead}"
        assert f"MSG.{dead}" not in src, f"死键仍有消费点: {dead}"
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    block = css[css.index(".bfp-meta {"):]
    for cls in (".bfp-meta-row", ".bfp-meta-warn", ".bfp-cats",
                ".bfp-list-title", ".bfp-list", ".bfp-item",
                ".bfp-item-head", ".bfp-idx", ".bfp-timing", ".bfp-trunc",
                ".bfp-text", ".bfp-toggle", ".bfp-cat-chip",
                ".bfp-cat-warn", ".bfp-cat-primary", ".bfp-cat-danger",
                ".bfp-cat-neutral"):
        assert cls in block, f"style.css 缺少 {cls}"
    # 折叠机制（二发修订）：max-height 无引擎依赖（-webkit-line-clamp 在
    # Chromium 146 实测被重映射为 flow-root 整体失效，禁回退）+ 底部渐隐
    # mask 提示截断（mask 色用 black 关键字，块内零 hex 硬编码）
    assert "max-height: calc(3 * 1.55em)" in block, "现译默认 3 行折叠缺失"
    assert "-webkit-line-clamp" not in block, \
        "line-clamp 三件套残留（Chromium 146 下失效的死特性）"
    assert "mask-image" in block and "-webkit-mask-image" in block, \
        "折叠态底部渐隐 mask 缺失（截断可感知）"
    assert ".bfp-text.bfp-open" in block and "max-height: none" in block, \
        "展开态解除折叠缺失"
    assert ".bfp-text.bfp-open" in block, "展开态解除折叠缺失"
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b", block), \
        "bfp 样式块出现硬编码色值（必须全 var() token，暗色自动适配）"


# ---------------------------------------------------------------------------
# 2.7.4 件1（D2026-1007-01）：质量报告导读页可读性整改
# （状态行升级/媒体三态徽标/区块重排/分节卡/条目三段化/试听错误槽）
# ---------------------------------------------------------------------------
def test_guide_page_readability_app_pinned():
    """件1 app.js 静态钉：新 MSG 键、#audioPreviewError 零写者（废弃静态
    保证）、player.src='' 停播保留、三分支入口清红字、错误槽动态注入
    （tab-guide 页面级容器）、媒体三态类、状态行收敛（双写撤销）。"""
    src = _app_js_source()
    keys = _js_msg_keys()
    for key in ("guide_custom_source", "guide_copy_path",
                "guide_copy_path_done", "guide_media_missing_hint",
                "preview_matching", "preview_media_matched"):
        assert key in keys, f"MSG 缺少 2.7.4 件1 新键: {key}"
    # 废弃静态保证：#audioPreviewError 在 app.js 零读写（DOM 保留不删不写）
    assert "audioPreviewError" not in src, \
        "#audioPreviewError 已废弃，app.js 不得再读写"
    # 停播保留（评议员条件）：错误即清 src，防上一次试听声音持续播放
    spe = _extract_function(src, "showPreviewError")
    assert "player.src = ''" in spe, "错误路径必须停播（player.src=''）"
    assert "ensurePreviewErrorSlot()" in spe and "audioPreviewBar" in spe, \
        "失败态=浮层条隐藏+独立错误槽红字"
    # 错误槽动态注入（页面级稳定容器，no_guide 态可见）
    eps = _extract_function(src, "ensurePreviewErrorSlot")
    assert "createElement" in eps and "tab-guide" in eps, \
        "错误槽须动态注入 #tab-guide 页面级容器"
    # 三分支入口先清旧红字（防残留）：clearPreviewError 位于 no_guide 判定前
    oap = _extract_function(src, "openAudioPreview")
    assert "clearPreviewError()" in oap, "分支入口清红字缺失"
    assert oap.index("clearPreviewError()") \
        < oap.index("audio_preview_no_guide"), \
        "清红字必须先于分支判定（每分支入口语义）"
    assert "bar-loading" in oap and "bar-ready" in oap, \
        "浮层两态（loading→ready）缺失"
    # 竞态：lastPreviewToken 失效机制保留（过期回调不写 UI）
    assert "token !== lastPreviewToken" in oap, "lastPreviewToken 失效机制缺失"
    # 媒体三态修饰类 + 缺失提示接线
    ums = _extract_function(src, "updateMediaSourceBar")
    for cls in ("tag-none", "tag-auto", "tag-explicit"):
        assert cls in ums, f"媒体三态类缺失: {cls}"
    assert "MSG.guide_media_missing_hint" in src, "缺失态琥珀提示未接线"
    # 状态行收敛：guideLoad 撤销 loading 双写（loading 不再写来源 chip）
    gl = _extract_function(src, "guideLoad")
    assert "guideCustomStatus(MSG.guide_loading" not in gl, \
        "guideLoad loading 态不得再双写 guideCustomStatus（收敛遗留）"
    # 复制路径链：clipboard 成功「已复制」1.5s 复位，失败静默降级 title
    gcp = _extract_function(src, "guideCopyPath")
    assert "writeText" in gcp and "guide_copy_path_done" in gcp, \
        "复制成功链缺失"
    assert "setTimeout" in gcp and "btn.title = text" in gcp, \
        "1.5s 复位/静默降级 title 缺失"


def test_guide_page_readability_render_css_pinned():
    """件1 渲染与样式钉：guideRender 区块重排挂类/分节卡/条目三段化
    （data-timing 契约红线）/count-chip；style.css order 声明/三态徽标/
    错误槽/浮层条扁平化（box-shadow 移除）。件3 confirm 钉不回退由
    test_batch_fix_run_uses_structured_preview 继续守护。"""
    src = _app_js_source()
    gr = _extract_function(src, "guideRender")
    assert "json-blocks" in gr, "区块重排容器挂类缺失"
    assert "section-card" in gr and "sect-open" in gr, "章节分节卡缺失"
    assert "section-card-head" in gr and "section-card-note" in gr, \
        "分节卡标题行/正文段缺失"
    # 三段化模板 + 契约红线（卡B：模板随载体移入 guideItemCardHtml 共享
    # 构造，D2026-1010-01 三轮）：试听委托锚点 class/data-timing 原样保留
    builder = _extract_function(src, "guideItemCardHtml")
    for frag in ("item-head", "idx-chip", "item-timing", "item-msg",
                 "item-cur", "bfp-cat-chip", "btn-audio-preview",
                 "data-timing="):
        assert frag in builder, f"条目三段化模板缺 {frag}"
    assert "block-title" in gr and "count-chip" in gr, \
        "行动条目标题提级/条数 chip 缺失"
    # 来源 chip 按成功来源显隐的收敛调用
    assert "guideCustomStatus(isCustom" in gr or \
        "guideCustomStatus(isCustom" in _extract_function(src, "guideLoad"), \
        "来源 chip 收敛调用缺失"
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    for cls in (".status-line", ".status-ico", ".status-path",
                ".guide-media-hint", ".guide-custom-chip",
                ".media-source-tag.tag-none", ".media-source-tag.tag-auto",
                ".media-source-tag.tag-explicit", ".json-blocks",
                ".section-card", ".section-card-head", ".section-card-note",
                ".item-head", ".idx-chip", ".item-timing", ".item-msg",
                ".item-cur", ".count-chip", ".preview-error-slot",
                ".preview-loading-note"):
        assert cls in css, f"style.css 缺少 {cls}"
    # 区块重排 order 声明（条目1/结论2/章节3/伴生4/meta5）
    for order in ("order: 1", "order: 2", "order: 3", "order: 4", "order: 5"):
        assert order in css, f"区块 order 声明缺失: {order}"
    # 浮层条扁平化（设计师偏离点）：box-shadow 移除、border-top 分隔保留
    bar = re.search(r"\.audio-preview-bar \{[^}]*\}", css)
    assert bar, "浮层条规则缺失"
    assert "box-shadow" not in bar.group(0), \
        "浮层条硬编码 box-shadow 应移除（暗色不可见，双主题统一扁平分隔）"
    assert "border-top" in bar.group(0), "浮层条 border-top 分隔缺失"
    # 错误槽层级：高于浮层条 z-900 与模态遮罩 z-1000
    slot = re.search(r"\.preview-error-slot \{[^}]*\}", css)
    assert slot and "z-index: 1001" in slot.group(0), \
        "错误槽须 z-index 1001（不被浮层条/模态遮罩遮挡）"


def test_guide_page_escape_order_and_narrow_pinned():
    """件1 三发缺陷钉（黑盒复核）：esc() 转义序根因（& 先于 " 替换，防
    &quot; 被二次转义为 &amp;quot;）+ 模板单层 esc；768px 既有断点块内
    summary 媒体来源条整行换行（勿新增断点）；试听键 nowrap+不压缩。"""
    src = _app_js_source()
    # 转义序根因钉：esc 体内 & 替换必须先于 " 替换——原序先转 " 再转 &，
    # 会把 &quot; 的 & 二次转义为 &amp;quot;（#189 页面显示字面 &quot;）
    m = re.search(r"function esc\(s\) \{(.+?)\n  \}", src, re.S)
    assert m, "esc 定义缺失"
    esc_body = m.group(1)
    assert esc_body.index("replace(/&/g, '&amp;')") \
        < esc_body.index('replace(/"/g'), \
        "esc 转义序错误：& 必须最先替换（二次转义回退）"
    # 模板单层 esc（卡B：模板构造移入 guideItemCardHtml，断言随载体）
    builder = _extract_function(src, "guideItemCardHtml")
    assert "esc(o.message)" in builder, "message 须经单层 esc 渲染"
    assert "esc(esc(" not in src, "模板双层 esc 回归"
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    # 768px 既有断点块（勿新增断点）：summary 内媒体来源条整行换行
    assert css.count("@media (max-width: 768px)") == 1, "新增了 768px 断点块"
    mq = css[css.index("@media (max-width: 768px)"):]
    mq = mq[:mq.index("\n}")]
    assert "#refineGuideViewer summary .media-source-bar" in mq \
        and "flex-basis: 100%" in mq, \
        "窄断点下卡头媒体来源条须 flex-basis:100% 整行换行"
    # 试听键：nowrap + flex-shrink:0（窄窗不被压成一字宽竖排）
    btn = re.search(r"\.btn-audio-preview \{[^}]*\}", css)
    assert btn, "试听键规则缺失"
    assert "white-space: nowrap" in btn.group(0) \
        and "flex-shrink: 0" in btn.group(0), \
        "试听键须 nowrap+flex-shrink:0（只动该按钮类）"


def test_preview_media_infer_frontend_pinned():
    """2.7.4 件2 前端接线钉：重匹配按钮按结构化 error_key 驱动（禁中文
    文案匹配）、同一后端推断入口（零第二实现）、tag-auto 推断回显、
    每 guide 推断缓存、apply 持久化写入与缓存失效。"""
    src = _app_js_source()
    keys = _js_msg_keys()
    assert "preview_rematch" in keys, "MSG 缺少 2.7.4 件2 重匹配键"
    assert "preview_media_matched" in keys, "MSG 缺少 tag-auto 横幅键"
    # 结构化 err_kind 驱动（评议员条件①：禁靠中文文案匹配）
    assert "errKind === 'path_invalid'" in src, \
        "重匹配按钮须按结构化 err_kind 驱动"
    spe = _extract_function(src, "showPreviewError")
    assert "errKind" in spe, "showPreviewError 须接收 err_kind 参数"
    # 重匹配复用同一后端推断入口（零第二实现，不复制试听链路）
    rm = _extract_function(src, "rematchPreviewMedia")
    assert "refine_preview_infer_media(" in rm, "重匹配须走推断独立入口"
    assert "refine_audio_preview(" not in rm, "重匹配不得复制试听链路"
    assert "lastPreviewTiming" in rm, "重匹配成功后自动重试本次试听"
    # 推断命中回显：media_source 判定 + tag-auto + 每 guide 缓存
    mi = _extract_function(src, "markInferredMedia")
    assert "media_source !== 'inferred'" in mi, "推断命中须按 media_source 判定"
    assert "inferredMediaCache" in mi and "tag-auto" in mi \
        and "MSG.preview_media_matched" in mi, "推断回显/缓存缺失"
    assert "let inferredMediaCache" in src, "每 guide 推断缓存声明缺失"
    gl = _extract_function(src, "guideLoad")
    assert "inferredMediaCache[lastLoadedGuidePath]" in gl, \
        "导读加载缺失态须回显缓存推断（评议员条件②）"
    # 「更换」apply：持久化写入 + 缓存失效
    bind = _extract_function(src, "bindDom")
    assert "refine_save_media_override(" in bind, "apply 持久化写入缺失"
    assert "delete inferredMediaCache[lastLoadedGuidePath]" in bind, \
        "override 变更须失效推断缓存"


# ---------------------------------------------------------------------------
# 2.7.5 件D（D2026-1007-02 P1）：F2 错误分型 / C4 audio 监听 / F3 时间列 / F5 直通选媒体
# ---------------------------------------------------------------------------
def test_review_video_error_codec_probe_typed():
    """F2 错误分型钉（C3 条件）：video error 仅 codec_probe===true 且
    code===4 才示「通道异常」文案；no-src guard 与中性文案回退保留。"""
    src = _review_js_source()
    keys = _review_msg_keys()
    assert "review_media_codec_error" in keys, "REVIEW_MSG 缺分型键"
    bind = _extract_function(src, "_bindPlayer")
    # no-src guard（批 4 审计先例）不得回退
    assert "if (!v.getAttribute('src')) { return; }" in bind, \
        "no-src guard 缺失（清 src 触发的无源 error 须忽略）"
    # 分型双门槛：codec_probe 实证 + code 4，缺一即维持中性文案
    assert "codec_probe === true" in bind and "code === 4" in bind, \
        "分型须双门槛（codec_probe===true 且 code===4）"
    assert "'review_media_codec_error'" in bind and \
        "'review_media_error'" in bind, "分型/中性双文案键缺失"


def test_preview_audio_error_listener_and_pick_media_pinned():
    """C4+F5 钉：audio error 监听（no-src guard 照抄 review.js 先例）入
    独立错误槽；「选择媒体文件…」直通键按 err_kind=no_candidate 结构化
    驱动（禁中文文案匹配）——pick_media → save_override → 清 guide 键
    推断缓存 → 自动重试上次试听；按钮动态注入零新增静态 id。"""
    src = _app_js_source()
    keys = _js_msg_keys()
    for key in ("audio_preview_play_error", "preview_pick_media"):
        assert key in keys, f"MSG 缺 2.7.5 件D 新键: {key}"
    # C4：error 监听在 bindDom + no-src guard（防清 src 幽灵 error 闪回红字）
    bind = _extract_function(src, "bindDom")
    assert "pvPlayer.addEventListener('error'" in bind, \
        "audioPreviewPlayer 缺 error 监听（direct 播放失败静默无声回归）"
    guard = "if (!pvPlayer.getAttribute('src')) return;"
    assert guard in bind, "audio error 监听缺 no-src guard（review.js:549 先例）"
    assert "MSG.audio_preview_play_error" in bind, "监听未入独立错误槽"
    # F5：直通键动态注入错误槽容器内（零新增静态 id，FROZEN_IDS 不变）
    eps = _extract_function(src, "ensurePreviewErrorSlot")
    assert "preview-error-pickmedia" in eps, "错误槽缺选择媒体直通键"
    assert "MSG.preview_pick_media" in eps, "直通键文案未走 MSG 键表"
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert "pickmedia" not in html, "直通键不得新增 index.html 静态 id/class"
    # 结构化 err_kind 驱动（评议员条件①先例：禁中文文案匹配）
    spe = _extract_function(src, "showPreviewError")
    assert "errKind === 'no_candidate'" in spe, "直通键须按 no_candidate 驱动"
    pick = _extract_function(src, "pickPreviewMediaManually")
    assert "refine_review_pick_media(" in pick, "缺文件对话框桥调用"
    assert "refine_save_media_override(" in pick, "缺持久化覆盖写入"
    assert "delete inferredMediaCache[lastLoadedGuidePath]" in pick, \
        "直通后必须按 guide 键清推断缓存（防仍走旧推断）"
    assert "lastPreviewTiming" in pick and "openAudioPreview(" in pick, \
        "选到媒体后须自动重试上次试听（rematch 先例）"
    # 用户取消对话框 → 静默返回（保留原错误态）
    assert "!r || !r.success || !r.path" in pick, "取消/失败须静默返回"


def test_review_timing_column_layout_pinned():
    """F3 时间列布局钉：11em 钉死轨道溢出叠画进文本列（真机截图错位）——
    .review-row 列定义改 3em max-content 1fr；.review-timing-readonly 带
    min-width:0 + ellipsis 防御（极窄窗口省略号截断而非叠画）。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    row = re.search(r"\.review-row \{[^}]*\}", css)
    assert row, "style.css 缺 .review-row 规则"
    assert "grid-template-columns: 3em max-content 1fr" in row.group(0), \
        "时间列须改 max-content（内容定宽，防 29 字符时间串溢出）"
    assert "11em" not in row.group(0), "残留 11em 钉死列定义（溢出叠画回归）"
    timing = re.search(r"\.review-timing-readonly \{[^}]*\}", css)
    assert timing, "style.css 缺 .review-timing-readonly 规则"
    for frag in ("min-width: 0", "overflow: hidden", "text-overflow: ellipsis"):
        assert frag in timing.group(0), f"时间列缺防御声明: {frag}"


# ---------------------------------------------------------------------------
# 批1（质量报告导读试听定位修复）：direct 分支 seek 定位 + 段内自动停播
# + 监听清理防幽灵暂停
# ---------------------------------------------------------------------------
def test_preview_direct_seek_autostop_cleanup_pinned():
    """批1 钉：direct 整文件试听不再从 0:00 播——src 赋值后挂一次性
    loadedmetadata 监听，metadata 就绪后 seek 至片段起点前置 0.5s（与
    clip 抽取 pad 对齐）；timeupdate 自然播到片段终点后 0.5s 自动暂停；
    程序化 seek / 用户拖拽经 pendingSeek 标志区分（seeked 落定后武装、
    seeking 非程序化解除武装不打断续听）；回调先校验代数防快速切换/
    重匹配重试时旧回调落错点；拆除监听在 closeAudioPreview/
    showPreviewError/openAudioPreview 重入均被调用；clip 分支既有播放
    链不得回退。"""
    src = _app_js_source()
    oap = _extract_function(src, "openAudioPreview")
    det = _extract_function(src, "detachPreviewSeekListeners")
    att = _extract_function(src, "attachPreviewSeekListeners")
    # ① direct 分支：src 赋值后挂定位监听（currentTime seek 落点前置 0.5s）
    direct = oap[oap.index("r.mode === 'direct'"):]
    direct = direct[:direct.index("r.mode === 'clip'")]
    assert "player.src = fileUrlOf(r.media_path)" in direct, \
        "direct 分支 src 赋值缺失"
    assert "attachPreviewSeekListeners(player, span)" in direct, \
        "direct 分支缺定位监听挂载（试听仍从 0:00 播）"
    assert direct.index("player.src = fileUrlOf(r.media_path)") \
        < direct.index("attachPreviewSeekListeners(player, span)"), \
        "定位监听须在 src 赋值之后挂载"
    assert "player.currentTime = Math.max(0, span[0] - 0.5)" in att, \
        "缺 seek 赋值（起点前置 0.5s 须与 clip pad 对齐）"
    assert "{ once: true }" in att, "loadedmetadata 须一次性监听"
    assert "player.play().catch(() => {})" in direct, \
        "direct 即播时机不得改动（play 仍在 src 赋值后，seek 异步落点）"
    # ② 段内自动停播：timeupdate 到 span[1]+0.5 才 pause；pendingSeek
    # 区分程序化 seek（落定武装）与用户拖拽（解除武装）
    assert "player.currentTime >= span[1] + 0.5" in att \
        and "player.pause()" in att, "缺段内自动停播（timeupdate→pause）"
    assert "previewPendingSeek = true" in att \
        and "previewPendingSeek = false" in att, \
        "缺程序化 seek 标志（seeking 时区分程序化/用户拖拽）"
    assert "if (!previewPendingSeek) previewArmStop = false" in att, \
        "用户拖拽须解除武装（不打断续听）"
    assert "previewArmStop = true" in att, "seeked 落定后须武装自动停播"
    assert "gen !== previewSeekGen" in att, \
        "回调缺代数校验（过期回调不落点，防切换/重试落错时间）"
    # ③ 清理：closeAudioPreview / showPreviewError / openAudioPreview
    # 重入均拆除新增监听（loadedmetadata/seeking/seeked/timeupdate）
    # 并复位标志（防幽灵暂停）
    for ev in ("loadedmetadata", "seeking", "seeked", "timeupdate"):
        assert f"removeEventListener('{ev}'" in det, f"清理缺 {ev} 移除"
    assert "previewSeekGen++" in det, "拆除须递增代数（作废在途回调）"
    assert "previewPendingSeek = false" in det \
        and "previewArmStop = false" in det, "拆除须复位武装/seek 标志"
    cap = _extract_function(src, "closeAudioPreview")
    spe = _extract_function(src, "showPreviewError")
    assert "detachPreviewSeekListeners()" in cap, "closeAudioPreview 缺清理"
    assert "detachPreviewSeekListeners()" in spe, "showPreviewError 缺清理"
    assert oap.index("detachPreviewSeekListeners()") \
        < oap.index("clearPreviewError()"), \
        "openAudioPreview 每次重入须先拆旧监听再走分支"
    # clip 分支既有播放链不得回退（本次修复不得波及）
    clip = oap[oap.index("r.mode === 'clip'"):]
    clip = clip[:clip.index("} else {")]
    assert "player.src = r.data_url" in clip \
        and "player.play().catch(() => {})" in clip, "clip 分支既有链缺失"
    assert "attachPreviewSeekListeners" not in clip, \
        "clip 分支不受 direct 定位影响（后端已带 pad 并自行定界）"


# ---------------------------------------------------------------------------
# 批2（D2026-1008-01）：压制参数独立设置项——弹窗参数编辑模式 + 高级参数页
# 「压制」组 + 右栏自动压制行「参数」入口 + applyParams backend 回填顺修
# ---------------------------------------------------------------------------
def _encode_dock_source(src: str) -> str:
    """从 ``const EncodeDock = {`` 锚起按花括号配平截取 EncodeDock 对象
    源码（app.js 存在多个 init 同名方法，须域内提取防误配）。"""
    anchor = "const EncodeDock = {"
    start = src.index(anchor) + len(anchor) - 1
    depth = 0
    for i in range(start, len(src)):
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
            if depth == 0:
                return src[start:i + 1]
    raise AssertionError("EncodeDock 对象花括号未配平")


def test_encode_params_edit_mode_pinned():
    """钉①编辑模式：encode(opts.editOnly) 无选中文件也可打开——「加入压制
    队列」确认键隐藏、另设「保存参数」按钮（JS 态文案）、保存只走
    encode_save_params 桥且成功经 o.onSaved 回调（同步调用方缓存/摘要行），
    绝不触碰 encode_preflight/encode_commit（编辑模式分支零调用）。"""
    src = _app_js_source()
    enc = _extract_function(src, "encode")
    assert "const editOnly = !!o.editOnly" in enc, "encode 缺编辑模式开关"
    # 「加入压制队列」确认键：编辑模式隐藏（禁用/隐藏二选一的隐藏侧）
    assert "okBtn.style.display = editOnly ? 'none' : ''" in enc, \
        "编辑模式须隐藏「加入压制队列」确认键"
    # 独立「保存参数」按钮 + 状态行（成功反馈），保存走 encode_save_params 桥
    assert "enc-save-params-btn" in enc, "编辑模式缺独立「保存参数」按钮"
    assert "enc-edit-status" in enc, "编辑模式缺保存状态行（成功/失败反馈）"
    assert "MSG.encodeSaveParams" in enc, "保存按钮文案须 JS 态 MSG 承接"
    assert "encode_save_params(JSON.stringify(params))" in enc, \
        "保存须走 encode_save_params 桥（后端校验+原子写）"
    assert "typeof o.onSaved === 'function'" in enc, \
        "保存成功须经 onSaved 回调同步调用方 _lastParams 缓存/摘要行"
    # 编辑模式绝不触碰 preflight/commit/jobs：openModal editOnly 分支
    openm = _extract_function(src, "openModal")
    edit = openm[:openm.index("const jobs = (AppState.selectedFiles")]
    assert "opts && opts.editOnly" in edit, "openModal 缺编辑模式分支"
    assert "encode_preflight" not in edit \
        and "encode_commit" not in edit, \
        "编辑模式分支不得触碰 preflight/commit（绝不建 job 不入队）"
    assert "encode_get_last_params" in edit, \
        "编辑模式须读上次参数回填弹窗"
    assert "this.renderParamsSummary()" in edit, \
        "保存成功回调须刷新高级参数页摘要行"
    # GPU 可用性：编辑模式无 preflight 双检 → 选项置灰并 title 显因
    assert "MSG.encodeGpuEditTitle" in enc, \
        "编辑模式 GPU 选项须以 title 显因（无独立探测桥，发起压制后可检测）"


def test_encode_apply_params_backend_backfill_pinned():
    """钉②顺修：applyParams 回填恢复 backend（用户预设含 backend 快照）——
    gpu 仅在探测已知可用（gpuEnc 非空）时恢复，cpu 显式恢复，其余/缺省落
    回 auto（与 collect 读取逻辑镜像）；av1Warn/syncKnobs 联动保持收尾。"""
    src = _app_js_source()
    start = src.index("const applyParams = (p) => {")
    body = src[start:src.index("const fillPresets", start)]
    assert "elBackend.value" in body and "gpuEnc" in body, \
        "applyParams 缺 backend 回填（预设加载丢后端档位）"
    assert "p.backend === 'gpu' && gpuEnc" in body, \
        "gpu 仅在已知可用时恢复（不可用须回落 auto，防选项假亮）"
    assert "p.backend === 'cpu'" in body, "cpu 档须显式恢复"
    assert "av1Warn.style.display" in body and "syncKnobs()" in body, \
        "applyParams 收尾须保持 av1Warn/syncKnobs 联动（collect 同口径）"


def test_encode_adv_group_entry_pinned():
    """钉③高级参数页「压制」组：仿「断点与日志」组结构——组标题/简述/
    「打开压制参数」按钮/参数摘要行四件套；零 id/零静态 data-i18n
    （FROZEN_IDS/FROZEN_I18N_KEYS 冻结），文案 EncodeDock.init JS 态承接；
    摘要行由 renderParamsSummary 渲染（格式/画质/音量/保存时间）。"""
    src = _app_js_source()
    html = INDEX_HTML.read_text(encoding="utf-8")
    # 四件套锚点（class+data-testid 承载）
    for frag in ('data-testid="encode-adv-group-title"',
                 'data-testid="encode-adv-desc"',
                 'data-testid="encode-params-open-btn"',
                 'data-testid="encode-params-summary"'):
        assert frag in html, f"index.html 缺压制组锚点: {frag}"
    m = re.search(r'<div class="adv-group" data-testid="encode-adv-group">.*?'
                  r'<div class="muted encode-params-summary"', html, re.S)
    assert m, "压制组结构漂移（标题→简述→按钮→摘要行顺序须保持）"
    assert "data-i18n" not in m.group(0), \
        "压制组锚点不得带静态 data-i18n（文案走 JS 态 MSG 键）"
    init = _extract_function(_encode_dock_source(src), "init")
    assert "encode-adv-title" in init and "MSG.encodeAdvGroupTitle" in init, \
        "init 缺组标题 JS 态填充"
    assert "encode-adv-desc" in init and "MSG.encodeAdvGroupDesc" in init, \
        "init 缺组简述 JS 态填充"
    assert "encode-params-open-btn" in init \
        and "editOnly: true" in init, \
        "「打开压制参数」须开编辑模式弹窗"
    summary = _extract_function(src, "renderParamsSummary")
    assert "encode_get_last_params" in summary, \
        "摘要行须读 encode_get_last_params"
    for frag in ("MSG.encodeSummaryVol", "MSG.encodeSummaryAt",
                 "MSG.encodeSummaryEmpty"):
        assert frag in summary, f"摘要行缺 JS 态拼装键: {frag}"
    keys = _js_msg_keys()
    for key in ("encodeAdvGroupTitle", "encodeAdvGroupDesc", "encodeAdvOpenBtn",
                "encodeEditHint", "encodeSaveParams", "encodeParamsSaved",
                "encodeParamsSaveFail", "encodeGpuEditTitle",
                "encodeSummaryLine", "encodeSummaryEmpty", "encodeSummaryVol",
                "encodeSummaryAt", "encodeEditTitle"):
        assert key in keys, f"MSG 缺批2新键: {key}"


def test_encode_auto_row_params_link_pinned():
    """钉④右栏自动压制行「参数」文字小按钮：同开编辑模式弹窗；置于
    encode-auto-row label 外（label 内点击会透传切换开关）；零 id/零静态
    data-i18n，文案 JS 态承接。

    d1013-卡O 钉修订（D2026-1013-01 追记；owner 2026-10-14 直接指令=依据）：
    参数钮上移卡头标题行（.pipeline-head-row 内与 block-title 同行，文档序
    移到 encode-auto-row 之前），删原「位于 encode-auto-row 之后」相对顺序
    断言，改恰 1 处存在断言+同行断言；:3065 class 正则与
    MSG.encodeParamsLink 回填键断言不动。"""
    src = _app_js_source()
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r'<button[^>]*class="btn btn-ghost btn-compact '
                  r'encode-params-link"[^>]*>', html)
    assert m, "index.html 缺 encode-auto-row 旁「参数」文字小按钮"
    tag = m.group(0)
    assert not re.search(r'(?<![\w-])id="', tag) and "data-i18n" not in tag, \
        "参数按钮不得带 id/data-i18n（FROZEN 契约，文案走 JS 态）"
    # 位置（d1013-卡O 钉修订）：上移卡头标题行——.pipeline-head-row 内与
    # block-title 同行、#pipelineCard 内恰 1 处（label 外兄弟节点，防透传
    # 切换开关）；原「位于 encode-auto-row 之后」相对顺序断言已删
    assert html.count('class="btn btn-ghost btn-compact '
                      'encode-params-link"') == 1, \
        "参数按钮须恰 1 处（#pipelineCard 卡头标题行）"
    m_head = re.search(
        r'<div class="pipeline-head-row">\s*'
        r'<div class="block-title" data-i18n="refine_panel_title">'
        r'.*?</div>\s*'
        r'<button[^>]*class="btn btn-ghost btn-compact '
        r'encode-params-link"[^>]*></button>\s*</div>',
        html, re.S)
    assert m_head, \
        "缺卡头标题行 .pipeline-head-row（参数钮须与 block-title 同行）"
    assert html.index('<div class="pipeline-head-row">') \
        > html.index('id="pipelineCard"'), \
        "卡头标题行须在 #pipelineCard 内"
    init = _extract_function(_encode_dock_source(src), "init")
    assert "encode-params-link" in init \
        and "MSG.encodeParamsLink" in init, \
        "init 缺「参数」按钮文案填充与接线"
    assert init.count("editOnly: true") == 2, \
        "两入口（高级参数页+自动压制行）须同开编辑模式弹窗"


# ---------------------------------------------------------------------------
# 批3（D2026-1008-01）：「质量与建议」页分析/修复模型三件套迁移钉
# （下拉+刷新+测试，对齐阶段页 refineS* 先例；全 class+data-testid 零 id、
#   零静态 data-i18n，文案 JS 态 MSG 承接；两份 FROZEN 集零触碰）
# ---------------------------------------------------------------------------

def test_batch3_analysis_model_select_trio_pinned():
    """①分析模型行 select 化：aiModelInput 文本框→下拉（id 保留，只换
    标签类型=FROZEN_IDS 契约）+ 刷新/测试按钮（class+data-testid 零 id、
    零静态 data-i18n）；app.js 三件套函数在位，lmstudio 走
    list_local_models（已加载 ✓ 置前）、其余走 refine_list_models。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert '<select id="aiModelInput"' in html, "分析模型未 select 化"
    assert '<input type="text" id="aiModelInput"' not in html, \
        "aiModelInput 文本框残留（应已换 select 标签类型）"
    for tid in ("ai-model-refresh", "ai-model-test", "ai-model-status"):
        m = re.search(rf'<(?:button|span)[^>]*data-testid="{tid}"[^>]*>',
                      html)
        assert m, f"分析模型行缺 data-testid={tid}"
        assert not re.search(r'(?<![\w-])id="', m.group(0)) \
            and "data-i18n" not in m.group(0), \
            f"{tid} 不得携带 id/data-i18n（FROZEN 契约）"
    src = _app_js_source()
    refresh = _extract_function(src, "refreshTrioSelect")
    assert "list_local_models" in refresh, \
        "lmstudio 必须走 list_local_models（已加载置前，HRO-2 裁定）"
    assert "refine_list_models" in refresh, \
        "其余 provider 必须走 refine_list_models"
    assert "REFINE_PROVIDER_URLS" in refresh, \
        "端点必须用该 provider 默认端点（与后端独立模式消费口径一致）"
    assert "originalHTML" in refresh and "savedModel" in refresh, \
        "刷新失败须恢复原 HTML、已存值须参与恢复（阶段页先例）"
    follow = _extract_function(src, "aiModelApplyFollowState")
    assert "MSG.ai_model_follow_hint" in follow and "disabled" in follow, \
        "follow 态须禁用模型下拉并填占位（ai_model_follow_hint）"
    test_fn = _extract_function(src, "testAnalysisModel")
    assert "testTrioModel" in test_fn and "refineS1Provider" in test_fn, \
        "分析测试按钮 follow 态须测阶段A 当前配置"
    keys = _js_msg_keys()
    for key in ("ai_model_follow_hint",):
        assert key in keys, f"MSG 缺批3新键: {key}"
    assert "ai_model_placeholder" not in keys \
        and "MSG.ai_model_placeholder" not in src, \
        "placeholder 键随文本框退役残留（死键须清）"


def test_p2_fix_model_row_removed_analysis_single_source():
    """P2（D2026-1008-02）：修复模型独立配置行随「修复=分析模型完全
    统一」删除（C11 收尾一致性）——index.html 行整块退役；app.js 旧
    函数族/batch_fix_* KV 读写/死键全清；修复解析单源 analyzeResolution
    （后端 _resolve_ai_model_config 前端镜像，含 G5-补 半配置忽略）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-testid="fix-model-row"' not in html, "修复模型行须已删除"
    assert "fix-model-row" not in html, "修复模型行残留锚"
    src = _app_js_source()
    for dead in ("fixRowEls", "refreshFixModels", "testFixModel",
                 "fixModelApplyFollowState", "savedFixModel",
                 "batch_fix_provider", "batch_fix_model"):
        assert dead not in src, f"修复行退役代码/键残留: {dead}"
    keys = _js_msg_keys()
    for dead_key in ("fix_cfg_label", "fix_prov_label", "fix_prov_follow",
                     "fix_model_follow_hint"):
        assert dead_key not in keys, f"MSG 死键残留: {dead_key}"
        assert f"MSG.{dead_key}" not in src, f"死键仍有消费点: {dead_key}"
    # 单源 helper 在位且含 G5-补 语义（半配置忽略键消费）
    res = _extract_function(src, "analyzeResolution")
    assert "aiProviderSel" in res and "aiModelInput" in res \
        and "refineS1Provider" in res and "refineS1Model" in res, \
        "analyzeResolution 读取面须=独立配置+阶段A 四元素"
    assert "MSG.aiIndepHalfIgnored" in res, \
        "analyzeResolution 缺半配置忽略注记（G5-补）"
    assert "aiIndepHalfIgnored" in keys, "MSG 缺半配置忽略键"
    # 保留键：生效源标签（后端 source_label 直拼）仍在
    assert "batchFixSourceTag" in keys, "MSG 缺生效源标签键"


def test_batch3_ai_config_row_pins_survive():
    """③既有钉不回归：.ai-config-row 恰 3 个 field-col + 三锚点 id 保留 +
    无内联 width:auto；id 全集数 222 / data-i18n 键集 187 契约数零漂移
    （全集逐键相等断言在 test_ui_phase3_redlines 钉⑤a/⑤b；P2 删修复
    模型行零 id/零 data-i18n，两契约数不漂移）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    i = html.index('class="ai-config-row"')
    row = html[i:html.index("</section>", i)]
    assert row.count('class="field-col"') == 3, "配置行必须恰 3 组顶置标签列"
    for dom_id in ("aiProviderSel", "aiModelInput", "aggregateWindowSel"):
        assert f'id="{dom_id}"' in row, f"配置行缺少锚点: {dom_id}"
    assert 'style="width:auto' not in row, "配置行残留内联 width:auto"
    ids = set(re.findall(r'(?<![\w-])id="([^"]+)"', html))
    assert len(ids) == 222, f"id 全集数漂移（契约 222），实为 {len(ids)}"
    i18n = set(re.findall(r'data-i18n(?:-title|-placeholder)?="([^"]+)"',
                          html))
    # 186=artifact_note 键退役后契约值（真机反馈 IA 重排轮，D2026-1013-01 追记；
    # 快照钉⑤b 为全集全等断言，此行只锁计数，漂移细节归钉⑤b）
    assert len(i18n) == 186, f"data-i18n 键集数漂移（契约 186），实为 {len(i18n)}"
    trio = html[html.index('class="model-trio"'):html.index("</div>",
               html.index('class="model-trio"'))]
    assert "data-i18n" not in trio, "model-trio 新增静态 data-i18n"


def test_batch3_trio_wiring_and_effective_lines_pinned():
    """④接线与生效行钉：bindDom 填三件套文案/图标（不依赖设置回填路径）；
    分析生效行中文字面量收编 MSG 键（aiRefreshEffective 零硬编码中文）；
    修复明示行追加后端 source_label 直拼（前端零解析），拒绝分支
    status-err + reason 保留。P2（D2026-1008-02）：分析生效行改走
    analyzeResolution 单源；修复行标签填充随删行退役。"""
    src = _app_js_source()
    bind = _extract_function(src, "bindDom")
    assert "MODEL_REFRESH_SVG" in bind and "MSG.refresh_model_title" in bind, \
        "bindDom 缺刷新按钮图标/title 填充"
    assert "MSG.test_stage_btn" in bind, "bindDom 缺测试按钮文案填充"
    assert "fix_cfg_label" not in bind, "修复行标签填充随删行退役残留"
    bf = _extract_function(src, "bfRefreshEffective")
    assert "analyzeResolution()" in bf, \
        "修复明示行入参须=analyzeResolution 产物（预览/执行同源，C7）"
    assert "refine_preview_fix_config" in bf and "source_label" in bf, \
        "修复明示行缺后端解析消费"
    assert "MSG.batchFixSourceTag" in bf, "修复明示行缺生效源标识直拼"
    assert "status-err" in bf and "MSG.batchFixUsing" in bf, \
        "修复明示行既有钉回归（status-err/batchFixUsing）"
    test_fix = _extract_function(src, "testTrioModel")
    assert "refine_test_stage" in test_fix, \
        "三件套测试必须复用阶段页 refine_test_stage 桥"


def test_ai_effective_line_removed():
    """D2026-1015-01 退役回归钉：AI 分析生效行黄字提示整行移除。

    - index.html 无 #refineAiPrivacy 元素；
    - style.css 无 .ai-config-row > #refineAiPrivacy 规则；
    - app.js 无 aiRefreshEffective / shortenModelName / aiSetPrivacy 函数；
    - MSG 七键（aiEffFollow/aiEffIndependent/aiModelUnset/aiEffectiveLine/
      aiCloudNote/aiPrivacyCloud/aiPrivacyLocal）全部退役。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    src = _app_js_source()
    assert "refineAiPrivacy" not in html, "index.html 残留 #refineAiPrivacy 元素"
    assert "refineAiPrivacy" not in css, "style.css 残留 #refineAiPrivacy 规则"
    assert "refineAiPrivacy" not in src, "app.js 残留 #refineAiPrivacy 引用"
    assert "aiRefreshEffective" not in src, "app.js 残留 aiRefreshEffective"
    assert "shortenModelName" not in src, "app.js 残留 shortenModelName"
    assert "aiSetPrivacy" not in src, "app.js 残留 aiSetPrivacy"
    keys = _js_msg_keys()
    for key in ("aiEffFollow", "aiEffIndependent", "aiModelUnset",
                "aiEffectiveLine", "aiCloudNote", "aiPrivacyCloud", "aiPrivacyLocal"):
        assert key not in keys, f"MSG 死键残留: {key}"
        assert f"MSG.{key}" not in src, f"死键仍有消费点: {key}"


def test_batch4_stop_buttons_pinned_and_wired():
    """停止分析/停止修复：index.html 双按钮（class+data-testid 零 id、
    零静态 data-i18n、初始隐藏）+ app.js 停止桥接线与复位。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for tid in ("ai-analyze-stop-btn", "batch-fix-stop-btn"):
        m = re.search(rf'<button[^>]*data-testid="{tid}"[^>]*>', html)
        assert m, f"index.html 缺少停止按钮: {tid}"
        tag = m.group(0)
        assert not re.search(r'\bid=', tag), \
            f"{tid} 不得携带 id（批4 新增锚全 class+data-testid）"
        assert "data-i18n" not in tag, f"{tid} 文案必须 JS 态 MSG 承接"
        assert "display:none" in tag, "停止按钮初始隐藏（运行中才显示）"
        cm = re.search(r'class="([^"]*)"', tag)
        assert cm and tid in cm.group(1).split(), \
            f"{tid} class 锚缺失（JS querySelector 依赖）"
    body = _extract_function(_app_js_source(), "refineAiAnalyze")
    assert "refine_cancel_ai_analyze" in body, "分析停止桥未接线"
    assert "ai-analyze-stop-btn" in body, "停止分析按钮未接线"
    assert "MSG.aiStopBtn" in body and "MSG.aiStopPending" in body
    bfb = _extract_function(_app_js_source(), "batchFixRun")
    assert "refine_cancel_batch_fix" in bfb, "修复停止桥未接线"
    assert "batch-fix-stop-btn" in bfb, "停止修复按钮未接线"
    assert "MSG.bfStopBtn" in bfb and "MSG.bfStopPending" in bfb
    # 取消/完成后复位可重新发起（finally 中隐藏停止按钮）
    fi = body.rindex("finally")
    assert "stopBtn.style.display = 'none'" in body[fi:], \
        "分析收尾必须复位停止按钮（可重新发起）"
    fi_bf = bfb.rindex("finally")
    assert "stopBtn.style.display = 'none'" in bfb[fi_bf:], \
        "修复收尾必须复位停止按钮（可重新发起）"


def test_batch4_cancel_and_jit_msg_keys_pinned():
    """C12 取消文案 + LM Studio JIT 说明：MSG 键存在且关键语句逐字在表。"""
    keys = _js_msg_keys()
    for k in ("aiStopBtn", "aiStopPending", "aiCancelled",
              "bfStopBtn", "bfStopPending", "bfCancelled", "aiAnalyzing"):
        assert k in keys, f"MSG 缺少批4 键: {k}"
    src = _app_js_source()
    # C12：取消后 LM Studio 侧 JIT 负载如实交代
    assert "已取消分析。LM Studio 侧可能已完成模型加载并常驻" in src, \
        "C12 取消文案缺失"
    assert "如需释放显存请在 LM Studio 中卸载模型" in src
    # 分析中提示扩含 JIT 按需加载说明
    assert "首次调用 LM Studio 需按需加载大模型" in src, \
        "JIT 说明未并入分析中提示"
    assert "期间高负载来自 LM Studio 进程属正常" in src


# ---------------------------------------------------------------------------
# 批2（D2026-1008-02）：TM 建议编辑后存入（P3 纯前端批）
# （行级编辑/恢复入口 data-ai-act 独立标记零 data-ai-kind 串扰；tmEdit
#   弹窗 createElement 注入零 id/零 data-i18n；定向 DOM 更新禁整表重渲；
#   原始建议旁路内存 Map 不写伴生 JSON；FROZEN 双钉 222/187 零触碰——
#   本批零 index.html 改动，全集契约天然不漂移）
# ---------------------------------------------------------------------------

def test_p3_tm_edit_restore_buttons_independent_pin():
    """C12：编辑/恢复按钮独立 data-ai-act 标记（与 button[data-ai-kind]
    选择器不相交），渲染后分派循环独立成环——点编辑/恢复绝不可误触
    aiApplyTm 存入链；编辑钮同款 btn-compact 样式；拟型译文单元格包
    data-testid span（黑盒锚+定向更新依据）。"""
    src = _app_js_source()
    render = _extract_function(src, "aiRenderResult")
    assert 'button[data-ai-kind]' in render and 'button[data-ai-act]' in \
        render, "kind/act 两套选择器必须并存（各自独立循环）"
    act_loop = render[render.index("button[data-ai-act]"):]
    assert "aiEditTm" in act_loop and "aiRestoreTm" in act_loop, \
        "data-ai-act 分派循环必须路由 aiEditTm/aiRestoreTm"
    assert "aiApplyTm" not in act_loop, \
        "C12 静态钉：编辑/恢复分派分支不得触达 aiApplyTm 存入链"
    edit = _extract_function(src, "aiEditBtn")
    assert 'data-ai-act="edit"' in edit, "编辑按钮必须独立 data-ai-act 标记"
    assert "data-ai-kind" not in edit, \
        "C12：编辑按钮严禁落入 button[data-ai-kind] 选择器"
    assert "btn-compact" in edit, "编辑按钮须同款紧凑样式"
    restore = _extract_function(src, "aiRestoreBtn")
    assert 'data-ai-act="restore"' in restore and "disabled" in restore, \
        "恢复钮渲染时当前恒等于原始值，须初始禁用（编辑保存后才启用）"
    assert "data-ai-kind" not in restore, \
        "C12：恢复按钮严禁落入 button[data-ai-kind] 选择器"
    assert 'data-testid="tm-sug-target"' in render, \
        "拟型译文必须包 data-testid span（黑盒锚+定向更新依据）"


def test_p3_tm_edit_modal_pinned():
    """C15/C17/G6：AppModal.tmEdit 另立方法（不塞 encode/editOnly）——
    createElement 注入零 id/零 data-i18n；原文只读、译文 textarea 可编辑
    （借 .editor-ta-wrap）；理由只读；「仅本次会话有效」提示行；脏态守卫
    （_settle tmEdit 分支+_tmEditDiscardGuard 经 confirm）；保存校验
    trim 非空在状态行显错；保存成功自动关闭；Enter 不提交（2.8.0.2 起
    走 _okValue 统一 kind 分派，textarea 回车=换行）；MSG 全键在表。"""
    src = _app_js_source()
    body = _extract_function(src, "tmEdit")
    assert "createElement" in body, "弹窗必须 createElement 注入"
    assert ' id="' not in body and "data-i18n" not in body, \
        "tmEdit 弹窗零 id/零 data-i18n（FROZEN 双钉不变）"
    assert "editor-ta-wrap" in body, "译文 textarea 须借 editor 弹性层先例"
    assert "MSG.th_source" in body and "MSG.th_target" in body \
        and "MSG.aiThReason" in body, "三字段标签须复用既有表头键"
    assert "MSG.tmEditTitle" in body and "MSG.tmEditSessionHint" in body, \
        "缺标题/「仅本次会话有效」提示行（G6）"
    assert "entry.source" in body and "entry.target" in body \
        and "entry.reason" in body, "tmEdit 字段面须=原文/译文/理由"
    assert "editOnly" not in body and "encode" not in body, \
        "C15：不得塞 encode/editOnly 语义（压制参数专用）"
    assert "addEventListener('input'" in body, "textarea 缺 dirty input 监听"
    settle = _extract_function(src, "_settle")
    assert "this._kind === 'tmEdit' && this._tmSaving" in settle, \
        "保存进行中 _settle 必须 no-op（editor 同款）"
    assert "this._tmEditDiscardGuard()" in settle, \
        "dirty 关闭必须走放弃确认守卫（G6：Esc/遮罩/关闭同源收口）"
    guard = _extract_function(src, "_tmEditDiscardGuard")
    assert "MSG.tmEditDirtyConfirm" in guard, "放弃守卫必须走确认弹窗"
    confirm_open = _extract_function(src, "_tmEditConfirmWhileOpen")
    assert "AppModal.confirm" in confirm_open, \
        "守卫确认必须复用 AppModal.confirm 单例"
    assert "stash" in confirm_open, \
        "开态确认必须收起暂存动态节点（取消原样放回）"
    save = _extract_function(src, "tmEditRunSave")
    assert "MSG.tmEditEmptyTarget" in save and "trim" in save, \
        "译文 trim 非空校验缺失（不合法在状态行显错，G6）"
    assert "MSG.tmEditSaveFailed" in save, "保存失败状态行文案键缺失"
    assert "this._settle(false)" in save, "保存成功必须自动关闭"
    # 2.8.0.2：Enter 不提交改走统一 kind 感知分派（_okValue tmEdit →
    # undefined，textarea 回车=换行不结算）；原「六处逐块排除」钉随骨架
    # 绑定收敛撤销，唯一绑定块+全 kind 矩阵在
    # test_appmodal_unified_skeleton_binding_pinned。
    okv = _extract_function(src, "_okValue")
    assert "this._kind === 'tmEdit'" in okv and "return undefined;" in okv, \
        "tmEdit Enter 须 no-op 分派（textarea 回车=换行不提交）"
    assert "AppModal._kind !== 'tmEdit'" not in src, \
        "逐块 Enter 排除条件应已由统一分派取代（残留即双轨漂移）"
    keys = _js_msg_keys()
    for key in ("aiTmEditBtn", "aiTmRestoreBtn", "aiTmStoredEdited",
                "tmEditTitle", "tmEditSessionHint", "tmEditSave",
                "tmEditEmptyTarget", "tmEditSaveFailed",
                "tmEditDirtyConfirm"):
        assert key in keys, f"MSG 缺 P3 新键: {key}"
    assert "仅本次会话有效，存入 TM 后才持久" in src, "G6 提示语逐字在表"


def test_p3_tm_edit_save_updates_memory_and_dom():
    """C16/C13/C19/C14/C20/G6：保存同时改内存+定向 DOM（禁整表重渲染）；
    原始建议旁路内存 Map（C19）随渲染源更换/lastAiSuggestions 重置而重置；
    恢复=内存+定向 DOM+禁自身；已存入/已存在行行级禁用（closest('tr')）；
    存入成功按「编辑后译文」区分文案（C20）；落库失败真实原因拼进按钮
    title+状态行（G6，重试能力保留）。"""
    src = _app_js_source()
    edit = _extract_function(src, "aiEditTm")
    assert "AppModal.tmEdit(" in edit and "entry.target = next" in edit, \
        "C16：保存必须写回内存（防复验重建重渲染回退旧值）"
    assert "aiUpdateTmTarget" in edit, "保存必须定向更新该行 DOM"
    upd = _extract_function(src, "aiUpdateTmTarget")
    assert "span[data-ai-tgt=" in upd and "textContent" in upd, \
        "C13：只许定向更新该行译文 span"
    assert "innerHTML" not in upd, "C13：禁止整表重渲染"
    assert "aiConflictBadge" not in upd, "原文格 ⚠️ 徽标不得被牵连"
    rst = _extract_function(src, "aiRestoreTm")
    assert "tmOriginalTargets" in rst and "aiUpdateTmTarget" in rst \
        and "disabled = true" in rst, "C19：恢复=内存+定向 DOM+禁自身"
    render = _extract_function(src, "aiRenderResult")
    assert "tmOriginalTargets = new Map()" in render, \
        "C19：渲染源更换（修复复验重建）时重置旁路 Map"
    gl_body = _extract_function(src, "guideLoad")
    assert "tmOriginalTargets = new Map()" in gl_body, \
        "C19：lastAiSuggestions 重置处须同批重置旁路 Map"
    ap = _extract_function(src, "aiApplyTm")
    assert "closest('tr')" in ap, "C14：已存入行须行级禁用编辑/恢复"
    assert "MSG.aiTmStoredEdited" in ap, "C20：编辑后存入须区分文案"
    assert "tmOriginalTargets" in ap, "C20：编辑与否须对原始值判定"
    assert "MSG.aiTmStored" in ap and "MSG.aiExists" in ap, \
        "原样存入/已存在文案不回归"
    fail = _extract_function(src, "aiApplyFail")
    assert "btn.title" in fail, "G6：失败须把真实原因拼进按钮 title"
    assert "MSG.aiApplyFailed" in fail, "状态行显因不回归"
    assert "MSG.aiApplyRetry" in fail, "重试能力保留不回归"
    # 旁路存储形态：模块级内存 Map（let 声明），零序列化
    assert "let tmOriginalTargets = new Map()" in src, \
        "C19：旁路存储须为模块级内存 Map"


# ---------------------------------------------------------------------------
# P1 分析模型预热（D2026-1008-02 批3，G1 落 (c) 阻断形态）：前端静态钉
# 全部 JS 态（零 index.html 改动，FROZEN 222/187 既有钉随全量回归保障）
# ---------------------------------------------------------------------------

def test_warmup_maybe_start_guards_order_and_bridge_call():
    """warmupMaybeStart 守卫顺序固定 + 桥调用参数同源（静态钉）。

    守卫链：全链开启短路（C-1，3.0 批1 a 段，D2026-1009-02 C5 复议——
    全链开启时预热由后端状态机链首环承接）→ 桥就绪 → 非翻译运行中 →
    页面有报告 → 模型解析非空 → 生效 provider 本地 → 高频抑制；
    任一不满足直接 return（不触发）。
    """
    src = _app_js_source()
    body = _extract_function(src, "warmupMaybeStart")
    marks = ["AppState.fullchainAutoEnabled", "window.pywebview",
             "AppState.isRunning", "lastLoadedGuidePath",
             "lastLoadedReportTxtPath", "analyzeResolution()", "res.model",
             "AI_CLOUD_PROVIDERS.includes", "__warmupInflight"]
    pos = [body.index(m) for m in marks]
    assert pos == sorted(pos), f"warmupMaybeStart 守卫顺序漂移: {pos}"
    assert body.index("AppState.fullchainAutoEnabled") \
        < body.index("window.pywebview"), "C-1 全链短路必须是第一守卫"
    # 桥调用与分析同参源（C6 镜像：model + provider，provider 可为 null）
    assert "refine_warmup_analysis_model(" in body
    assert "res.model, res.provider" in body
    # G4 文案：触发即透明提示 + 已在载跳过提示
    assert "MSG.warmupStarted" in body and "MSG.warmupHot" in body


def test_warmup_trigger_points_wired():
    """触发点①②接线：completed 分支 _finish 后触发；switchTab tab-guide
    姿势钩子（照 __asrTabHook 先例）触发。"""
    src = _app_js_source()
    switch_body = _extract_function(src, "switchTab")
    assert "TAB_HOOKS[tabId]" in switch_body, "switchTab 须经注册表派发"
    assert "__warmupTabHook" in _tab_hooks_group("tab-guide"), \
        "switchTab 须经 __warmupTabHook 触发"
    assert "window.__warmupTabHook = " in src, "IIFE 须导出 __warmupTabHook"
    # 触发点①：completed 分支内 _finish 之后调 __warmupMaybeStart()，
    # 且附 Console 一行 warmupAfterQueue
    # （P2-9 d1015-卡J：_finish 收尾增第二参 dotState，断言随形态同步）
    assert "window.__warmupMaybeStart()" in src
    assert src.index("this._finish(MSG.completed, dotState)") \
        < src.index("window.__warmupMaybeStart()"), "触发须在 _finish 之后"
    assert "MSG.warmupAfterQueue" in src
    # 全局别名已导出（跨 IIFE 调用通道）
    assert "window.__warmupMaybeStart = warmupMaybeStart" in src


def test_warmup_hold_lock_restore_symmetry_and_g7_third_state():
    """G9 持有模式：锁/恢复对称（锁了必恢复）+ G7 第三态（连续 3 次桥
    异常按预热已死放行）+ 超时放行调取消桥。"""
    src = _app_js_source()
    lock_body = _extract_function(src, "_lockEngineControls")
    # 锁定时记录原 disabled 值；恢复时逐一还原（对称性）
    assert "list.push({ el, disabled: el.disabled })" in lock_body
    assert "el.disabled = disabled" in lock_body
    assert "engine-locked" in lock_body, "容器须挂锁定样式类"
    # 开始/停止钮不受容器锁管理（开始钮由持有逻辑单独管）
    assert "refineStartBtn" in lock_body and "refineCancelBtn" in lock_body

    hold_body = _extract_function(src, "_warmupHoldUntilRelease")
    assert "_lockEngineControls(true)" in hold_body
    assert "_lockEngineControls(false, locked)" in hold_body
    # 恢复必须在 finally 内（异常路径也保证解锁）
    assert hold_body.index("finally {") \
        < hold_body.index("_lockEngineControls(false, locked)")
    assert "startBtn.textContent = prevText" in hold_body, \
        "开始按钮文案必须恢复"
    # G7 第三态：连续 N=3 次桥异常 → 按预热已死放行 + 专属文案
    assert "failStreak >= 3" in hold_body
    assert "MSG.warmupUnknown" in hold_body
    # 超时/不可确认释放 → 杀客户端+清状态（取消桥），防互锁死循环
    assert "refine_cancel_warmup" in hold_body
    assert "MSG.warmupTimeout" in hold_body
    # 倒计时：剩余=timeout-elapsed，每秒刷新
    assert "MSG.warmupHoldBtn" in hold_body
    assert "timeoutS - elapsedS" in hold_body
    # 后端首拍 elapsed 同源（倒计时基准对齐 G10）
    assert "st.elapsed" in hold_body


def test_warmup_decoupled_from_analyze_button():
    """C21：预热路径不碰 refineAiAnalyzeBtn、不走分析桥（不跳过真实
    ensure、不改分析按钮可用性）。"""
    for fn in ("warmupMaybeStart", "_warmupHoldUntilRelease",
               "_lockEngineControls"):
        body = _extract_function(_app_js_source(), fn)
        assert "refineAiAnalyzeBtn" not in body, \
            f"{fn} 不得触碰分析按钮（C21 解耦）"
        assert "refine_ai_analyze" not in body, \
            f"{fn} 不得经分析桥（C21：预热不替代真实 ensure）"


def test_warmup_backend_interlock_hold_retry_wired():
    """后端互锁兜底接线：startTranslation 内 warmup_loading → 持有后以
    同一 options 快照重试；入队快照在持有等待之前（G9 方案 A）。"""
    src = _app_js_source()
    body = _extract_function(src, "startTranslation")
    assert "warmup_loading" in body, "须消费后端互锁返回"
    assert "_warmupHoldUntilRelease" in body
    assert body.index("this.collectOptions()") \
        < body.index("_warmupHoldUntilRelease"), \
        "G9 方案 A：点击时快照必须先于持有等待"
    # 持有中重复点击不重复入队
    assert "_warmupHolding" in body


def test_warmup_msg_keys_present():
    """MSG 新键存在（全部 JS 态，零 data-i18n/零 id，FROZEN 双钉不变）。"""
    keys = _js_msg_keys()
    for k in ("warmupStarted", "warmupHot", "warmupAfterQueue",
              "warmupQueued", "warmupTimeout", "warmupUnknown",
              "warmupDone", "warmupFailed", "warmupHoldBtn",
              "fullchainAutoSwitch"):
        assert k in keys, f"MSG 缺少预热/全链键: {k}"


def test_fullchain_switch_wiring_pinned():
    """3.0 批1 a 段（D2026-1009-02）全链开关接线钉：index.html 开关行
    （零 id/零 data-i18n，data-testid 锚）+ EncodeDock.init 接线（文案/
    保存 KV/启动回填/AppState 镜像维护）+ MSG 双表同键（app.js 与
    strings.py，仿 warmup 存在性钉范式）。"""
    src = _app_js_source()
    html = INDEX_HTML.read_text(encoding="utf-8")
    # index.html 开关行：class 三件套 + data-testid，零 id/零 data-i18n
    m = re.search(r'<label[^>]*class="fullchain-auto-row"[^>]*>', html)
    assert m, "index.html 缺全链开关行"
    tag = m.group(0)
    assert 'data-testid="fullchain-auto-row"' in tag
    assert not re.search(r'(?<![\w-])id="', tag) and "data-i18n" not in tag, \
        "全链开关行不得带 id/data-i18n（FROZEN 契约，文案走 JS 态）"
    row = html[m.start():html.index("</label>", m.start())]
    assert 'class="fullchain-auto-switch"' in row
    assert 'class="fullchain-auto-label"' in row
    # 位置：紧随 encode-auto-row 之后（压制开关旁）
    assert html.index('data-testid="fullchain-auto-row"') \
        > html.index('data-testid="encode-auto-row"')
    # EncodeDock.init 接线：文案 + 保存 KV + 回填 + AppState 镜像维护
    init = _extract_function(_encode_dock_source(src), "init")
    assert "fullchain-auto-row" in init
    assert "MSG.fullchainAutoSwitch" in init
    assert "fullchain_auto_enabled: fcBox.checked" in init, \
        "change 须保存 KV fullchain_auto_enabled"
    assert "r.settings.fullchain_auto_enabled" in init, \
        "启动回填须读 fullchain_auto_enabled"
    assert "AppState.fullchainAutoEnabled = fcBox.checked" in init, \
        "AppState 镜像须同步维护（预热守卫 C-1 消费）"
    # MSG 双表同键（strings.py 镜像同键中文文案）
    sp = (ASSETS.parent / "strings.py").read_text(encoding="utf-8")
    assert re.search(r'"fullchainAutoSwitch":', sp), \
        "strings.py MSG 表缺 fullchainAutoSwitch（双表同键纪律）"
    assert "分析→批量修复→复验" in sp, "全链开关文案须如实描述链内序"


# ---------------------------------------------------------------------------
# GUI 黑盒缺陷回归（2.8.0 起存量）：refine_save_stage_settings 4 参调用
# ---------------------------------------------------------------------------
def _extract_call_args(source: str, open_pos: int) -> str:
    """从 open_pos（须指向 '('）起做圆括号配平，返回括号内实参文本
    （与 _extract_function 同款逐字符扫描范式）。"""
    assert source[open_pos] == "(", "open_pos 未指向左圆括号"
    depth = 0
    for i in range(open_pos, len(source)):
        ch = source[i]
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return source[open_pos + 1:i]
    raise AssertionError("调用圆括号未配平")


def _split_top_level_args(args: str) -> list:
    """按顶层逗号切分实参（()[]{}/引号串深度感知：嵌套内与串内的
    逗号不切分）。"""
    parts, buf, depth, quote = [], [], 0, None
    i = 0
    while i < len(args):
        ch = args[i]
        if quote:
            if ch == "\\":
                buf.append(args[i:i + 2])
                i += 2
                continue
            if ch == quote:
                quote = None
        elif ch in "'\"`":
            quote = ch
        elif ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            i += 1
            continue
        buf.append(ch)
        i += 1
    parts.append("".join(buf))
    return parts


def test_save_stage_settings_calls_three_args():
    """防复发钉：refine_save_stage_settings 全部调用点 ≤ 3 实参。

    黑盒根因（2.8.0 起存量）：后端签名仅 3 形参（stages/keys/settings，
    api.py 即正确形态），pywebview 真桥以 func(*params) 按位展开实参——
    多传尾随第 4 参 null 必 TypeError，而 encode/fullchain 自动化开关的
    change 监听用 catch 静默吞错（界面看似生效、重启即回缺省），
    encode_auto_enabled（2.8.0 起）与 fullchain_auto_enabled（3.0 批1 起）
    勾选因此从不落盘。"""
    src = _app_js_source()
    sites = list(re.finditer(r"refine_save_stage_settings\s*\(", src))
    assert sites, "app.js 未找到 refine_save_stage_settings 调用点"
    for m in sites:
        args = _split_top_level_args(_extract_call_args(src, m.end() - 1))
        line = src.count("\n", 0, m.start()) + 1
        assert len(args) <= 3, (
            f"app.js:{line} refine_save_stage_settings 传了 {len(args)} 个"
            "实参：后端签名仅 3 形参，真桥 func(*params) 按位展开下第 4 参"
            "必 TypeError 且被 change 监听 catch 静默吞掉（开关勾选从不"
            "落盘）")
    # 双锚精确文本钉：EncodeDock 两开关行须以 3 参对象收尾
    # （防链式调用等变体形态下漏检）
    init = _extract_function(_encode_dock_source(src), "init")
    assert "{ encode_auto_enabled: box.checked });" in init, \
        "encode 开关保存须为 3 参形态（尾随 , null 即 4 参缺陷）"
    assert "{ fullchain_auto_enabled: fcBox.checked });" in init, \
        "fullchain 开关保存须为 3 参形态（尾随 , null 即 4 参缺陷）"


def test_warmup_engine_locked_style_present():
    """G9 锁定样式类有 CSS 承接（style.js 态约定：容器 dim+锁定态）。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    assert "#tab-engine.engine-locked" in css
    assert "pointer-events: none" in css


# ---------------------------------------------------------------------------
# 批5（D2026-1008-02）：批量修复结果可见性
# （完成消息含剩余明细；修复后静默重读导读快照（禁 loadGuide 全量链，
#   不清复验建议）；行动条目行渲染台账「✅ 已修」徽标。全部 JS 态键、
#   零 index.html 改动——FROZEN 双钉 222/187 天然不漂移）
# ---------------------------------------------------------------------------

def test_batch5_fix_done_reread_and_remaining_pinned():
    """①修复成功后 finally 静默重读导读快照：只更新 lastGuideData+
    guideRender 局部重渲染，不走 loadGuide 全量链（不清 lastAiSuggestions/
    不清 #refineAiResult，复验建议刚重渲染不能被抹）；③完成消息含剩余
    未修复明细（submitted−applied 差集，主行截断+完整列表 title 悬停）。"""
    src = _app_js_source()
    caller = _extract_function(src, "batchFixRun")
    # ① 重读存在且形态正确：finally 内 batchFixRefresh 之后触发
    fin = caller[caller.rindex("} finally {"):]
    assert "read_output_artifact(lastLoadedGuidePath)" in fin, \
        "finally 缺少导读快照静默重读"
    assert fin.index("batchFixRefresh();") \
        < fin.index("read_output_artifact("), \
        "重读必须位于 batchFixRefresh 之后（徽标数据先刷新）"
    assert "lastGuideData = rr.data" in fin, "重读回包必须更新 lastGuideData"
    assert "guideRender(rr.data)" in fin, "重读后必须局部重渲染导读"
    assert "rr.kind !== 'json'" in fin, "重读回包须 kind=json 守卫"
    assert "catch(() => {" in fin, "重读失败必须静默（不提示）"
    # ① 禁全量链：不走 guideLoad，不清 AI 结果区/复验建议
    assert "guideLoad(" not in caller, "重读不得走 loadGuide 全量链"
    assert "refineAiResult" not in caller, \
        "重读路径不得清空 #refineAiResult（复验建议刚重渲染）"
    assert "lastAiSuggestions = null" not in caller, \
        "重读路径不得清 lastAiSuggestions（复验重建属既有行为，清空禁止）"
    # ③ 成功分支先等行动条目刷新再算差集（后端 applied_in_ledger 逐条标记）
    assert "await batchFixRefresh();" in caller, \
        "剩余明细必须以刷新后的 lastActionItems 为数据源"
    assert "new Set(batch.map(it => Number(it.index)))" in caller, \
        "本次提交集合缺失（Number 强转）"
    assert "submittedSet.has(Number(it.index))" in caller, \
        "差集匹配键必须 Number 强转"
    assert "!it.applied_in_ledger" in caller, "差集须排除台账已修行"
    assert "it.index != null" in caller, "index 须 null 先判（防 Number(null)=0）"
    assert "MSG.batchFixRemaining" in caller, "剩余明细文案键未接线"
    assert "ids.slice(0, REMAINING_SHOW_MAX)" in caller, \
        "主行须截断前 10 个条目号（常量形态，避开预览禁截钉字面量）"
    assert "MSG.batchFixRemaining(rem.length, ids.join(' '))" in caller, \
        "完整列表必须放 title 悬停"
    assert "if (bfSt) bfSt.title = ''" in caller, \
        "开跑时须清上一轮剩余明细悬停残留"
    # ③ 截断上限常量定义在位
    assert "const REMAINING_SHOW_MAX = 10" in caller


def test_batch5_guide_item_applied_badge_pinned():
    """②guideRender 台账已修徽标：lastActionItems 存在且 guide_path 与
    当前导读一致（分隔符/大小写归一比对）才生效；applied 集合 Number
    强转 index 匹配；applied 行 .item-head 追加绿色徽标（复用
    media-source-tag tag-auto，零新增 CSS），未 applied 行保持现状；
    ④MSG 新键存在且零静态 data-i18n 消耗。"""
    src = _app_js_source()
    gr = _extract_function(src, "guideRender")
    assert "appliedSet" in gr, "applied 集合构建缺失"
    assert "normPath(lastActionItems.guide_path)" in gr \
        and "normPath(lastLoadedGuidePath)" in gr, \
        "guide_path 身份判定缺失（须归一后比对）"
    assert "it.applied_in_ledger === true" in gr, \
        "applied 行筛选缺失（严格 === true）"
    assert "Number(it.index)" in gr, \
        "index 匹配必须 Number 强转（防字符串/数字不一）"
    assert "Number.isFinite" in gr, "非有限 index 须守卫"
    # 徽标条件渲染（卡B：徽标构造随载体移入 guideItemCardHtml，徽标侧
    # 的 Number(o.index) 强转随之迁移，D2026-1010-01 三轮；批6 起
    # status 终态优先，台账 appliedSet 降为兜底轨，条件形态改为
    # (applied || o.status === 'retranslated') 三元）
    builder = _extract_function(src, "guideItemCardHtml")
    assert "Number(o.index)" in builder, \
        "index 匹配必须 Number 强转（防字符串/数字不一）"
    assert "(applied || o.status === 'retranslated')" in builder, \
        "徽标必须条件渲染（未 applied 行保持现状）"
    assert "media-source-tag tag-auto" in builder, \
        "徽标须复用绿色 ok pill（零新增 CSS）"
    assert "MSG.guide_item_applied" in builder, "徽标文案未走 MSG 键"
    # ④ MSG 新键存在；全部 JS 态（零 data-i18n，FROZEN 双钉零消耗）
    keys = _js_msg_keys()
    for k in ("guide_item_applied", "batchFixRemaining"):
        assert k in keys, f"MSG 缺少批5 键: {k}"
    html = INDEX_HTML.read_text(encoding="utf-8")
    for k in ("guide_item_applied", "batchFixRemaining"):
        assert f'data-i18n="{k}"' not in html, f"{k} 不得消耗静态 data-i18n"


# ---------------------------------------------------------------------------
# 批6（D2026-1008-02）：导读终态渲染——全量渲染/徽标 status 优先/头部计数
# 分解/回包 nochange 计数（静态钉）
# ---------------------------------------------------------------------------

def test_batch6_guide_render_full_and_no_more_footnote():
    """①条目全量渲染（卡B 载体变更，D2026-1010-01 三轮）：主页 guideRender
    不再内联渲染条目（明细移入弹窗），全量渲染契约由 openGuideItemsModal
    承接——无 slice 截断、无 MAX_ITEMS 上限、MSG.guide_items_more 尾注
    零调用点。"""
    src = _app_js_source()
    gr = _extract_function(src, "guideRender")
    assert "MAX_ITEMS" not in gr, "渲染上限常量未删除"
    assert "items.slice(" not in gr, "条目渲染不得截断（须全量渲染）"
    modal = _extract_function(src, "openGuideItemsModal")
    assert modal and "items.map" in modal, \
        "明细须在弹窗内全量渲染（items.map，卡B 载体）"
    assert "items.slice(" not in modal, "弹窗渲染不得截断"
    assert "MSG.guide_items_more(" not in src, \
        "MSG.guide_items_more 尾注调用点未清除"


def test_batch6_status_badge_pinned():
    """②徽标 status 优先（卡B：徽标构造随卡markup移入
    guideItemCardHtml 共享构造）：nochange 灰徽标（复用 bfp-cat-chip
    bfp-cat-neutral）与 retranslated 绿徽标（复用 media-source-tag
    tag-auto）两终态分支在位且互斥优先于 appliedSet 兜底；新 MSG 键存在
    且零静态 data-i18n 消耗。"""
    src = _app_js_source()
    builder = _extract_function(src, "guideItemCardHtml")
    assert "o.status === 'nochange'" in builder, "nochange 徽标分支缺失"
    assert "bfp-cat-chip bfp-cat-neutral" in builder, \
        "灰徽标须复用 bfp-cat-chip bfp-cat-neutral（零新增 CSS）"
    assert "esc(MSG.guide_item_nochange)" in builder, "灰徽标文案未走 MSG 键"
    assert "(applied || o.status === 'retranslated')" in builder, \
        "retranslated 须复用绿色已修徽标（台账 appliedSet 保留为兜底）"
    keys = _js_msg_keys()
    for k in ("guide_item_nochange", "guide_chip_fixable",
              "guide_chip_applied", "guide_chip_nochange",
              "guide_chip_observation"):
        assert k in keys, f"MSG 缺少批6 键: {k}"
    html = INDEX_HTML.read_text(encoding="utf-8")
    for k in ("guide_item_nochange", "guide_chip_fixable",
              "guide_chip_applied", "guide_chip_nochange",
              "guide_chip_observation"):
        assert f'data-i18n="{k}"' not in html, f"{k} 不得消耗静态 data-i18n"


def test_batch6_count_chip_decomposition_pinned():
    """③头部计数五段式分解：guide_chip_* 四键在 chip 装配处接线；
    待修/观察恒显；C4 统一去重公式（新/老/混合三形态一致）——已修=
    status 终态 ∪ appliedSet 台账 timing 命中（同一 item 两源同真只计
    一次），待修=补集式 total−已修−无需改动−观察（C2：open 与未知
    status 天然计入待修）。"""
    gr = _extract_function(_app_js_source(), "guideRender")
    for k in ("guide_chip_fixable", "guide_chip_observation",
              "guide_chip_applied", "guide_chip_nochange"):
        assert "MSG." + k in gr, f"chip 装配未引用 MSG.{k}"
    assert "segs.join(' · ')" in gr, "计数段须以「 · 」分隔装配"
    # 统一去重公式：applied 为单条目级 OR 联合判定（status 终态或台账
    # 命中，同一 item 同时满足两源只计一次——混合态不重不漏）
    assert "statusOf(o) === 'retranslated'\n" \
        "            || (appliedSet != null && Number.isFinite(k)" \
        " && appliedSet.has(k))" in gr, \
        "applied 须为终态∪台账的单条目联合判定（去重）"
    # 补集式待修（C2：open/未知 status 天然落入待修；防御性钳 0）
    assert "items.length - nFixed - nNochg - nObs" in gr, \
        "待修须为补集式（total−已修−无需改动−观察）"
    assert "Math.max(0," in gr, "补集式待修须防御性钳 0"
    # 老文件退化：appliedSet 为空/无交集时 nFixed=0，「已修」段省略
    # （纯台账轨=升级前行为）
    assert "appliedSet != null" in gr, \
        "appliedSet 须 null 先判（老文件无台账时不误计）"
    assert "if (nFixed > 0)" in gr, "「已修」段为 0 时须省略"


def test_batch6_batch_fix_nochange_pinned():
    """④batchFixRun 成功分支：r.nochange>0 时在 batchFixDone 之后、
    批5 剩余明细之前拼接 batchFixNochange 计数；键存在且零 data-i18n。"""
    src = _app_js_source()
    caller = _extract_function(src, "batchFixRun")
    assert "MSG.batchFixNochange(r.nochange)" in caller, \
        "nochange 计数未接线"
    assert "r.nochange > 0" in caller, "nochange 须零值守卫"
    assert caller.index("MSG.batchFixDone(") \
        < caller.index("MSG.batchFixNochange(") \
        < caller.index("MSG.batchFixRemaining("), \
        "nochange 段须位于 batchFixDone 之后、批5 剩余明细之前"
    assert "batchFixNochange" in _js_msg_keys(), "MSG 缺少 batchFixNochange"
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'data-i18n="batchFixNochange"' not in html, \
        "batchFixNochange 不得消耗静态 data-i18n"


# ---------------------------------------------------------------------------
# 3.0 批2（D2026-1009-02 批2）：链级状态行 + digest + 一键回滚 静态钉
# ---------------------------------------------------------------------------

def test_fullchain_status_line_and_rollback_pinned():
    """批2 接线钉：index.html 状态行容器/回滚按钮（零 id/零 data-i18n，
    data-testid 锚）+ app.js 刷新链挂点（switchTab/batchFixRun）+ 回滚
    确认框链（preview→confirm→rollback→静默重读）+ MSG 双表同键。"""
    src = _app_js_source()
    html = INDEX_HTML.read_text(encoding="utf-8")
    # index.html：状态行容器（hidden 起步，零 id/零 data-i18n）
    m = re.search(r'<div[^>]*class="fullchain-status-line"[^>]*>', html)
    assert m, "index.html 缺全链链级状态行容器"
    assert 'data-testid="fullchain-status-line"' in m.group(0)
    assert "hidden" in m.group(0)
    assert not re.search(r'(?<![\w-])id="', m.group(0)), \
        "状态行容器不得带 id（FROZEN 契约）"
    assert "data-i18n" not in m.group(0)
    # index.html：一键回滚按钮（零 id/零 data-i18n，文案 JS 态填充）
    mb = re.search(
        r'<button[^>]*class="btn btn-secondary btn-compact '
        r'fullchain-rollback-btn"[^>]*>', html)
    assert mb, "index.html 缺一键回滚按钮"
    assert 'data-testid="fullchain-rollback-btn"' in mb.group(0)
    assert not re.search(r'(?<![\w-])id="', mb.group(0))
    assert "data-i18n" not in mb.group(0)
    # app.js：刷新函数 + 三挂点（切页/批修复完成/桥调用）
    fn = _extract_function(src, "fullchainStatusRefresh")
    assert "fullchain_automation_status" in fn
    assert "fcStatusRunning" in fn and "fcStatusSkipped" in fn \
        and "fcStatusUnfinished" in fn
    assert "fcMissedSkipped" in fn
    tab = _extract_function(src, "switchTab")
    assert "TAB_HOOKS[tabId]" in tab, "switchTab 须经注册表派发"
    assert "__fullchainStatusHook" in _tab_hooks_group("tab-guide"), \
        "switchTab tab-guide 分支须挂链级状态行刷新"
    run_fn = _extract_function(src, "batchFixRun")
    assert "fullchainStatusRefresh(true)" in run_fn, \
        "batchFixRun 完成后须刷新链级状态行"
    # 回滚流程：preview → confirm（条件化 auto_insert 删行提示，批3 3B：
    # 删行已接线，fcRollbackAutoInsertNote「暂不支持恢复」退场）→
    # rollback → 静默重读导读 + 刷新
    rb = _extract_function(src, "fullchainRollbackRun")
    assert "fullchain_rollback_preview" in rb
    assert "AppModal.confirm" in rb
    assert "fcRollbackAutoInsertDelete" in rb, \
        "确认框须含 auto_insert 删行条件化提示"
    assert "fcRollbackAutoInsertNote" not in src, \
        "「暂不支持恢复」旧文案须退场（删行已接线）"
    assert "fcMissedSkipped: '漏听放弃 {k} 条'" in src, \
        "漏听放弃文案不得再带批3 填充尾注"
    assert "fullchain_rollback(" in rb
    assert "read_output_artifact" in rb, "回滚成功后须静默重读导读"
    # 按钮绑定与 MSG 填充（bindDom 区，零静态键）
    assert "MSG.fullchainRollbackBtn" in src
    # MSG 双表同键（strings.py 镜像）
    sp = (ASSETS.parent / "strings.py").read_text(encoding="utf-8")
    for k in ("fullchainRollbackBtn", "fcStatusRunning", "fcStatusLast",
              "fcStatusSkipped", "fcStatusUnfinished", "fcStatusNever",
              "fcMissedSkipped", "fcRollbackConfirmBody",
              "fcRollbackAutoInsertDelete"):
        assert k in _js_msg_keys(), f"app.js MSG 缺键: {k}"
        assert re.search(rf'"{k}":', sp), f"strings.py MSG 表缺键: {k}"
    assert "fcRollbackAutoInsertNote" not in sp, \
        "strings.py 旧键须随退场摘除"
    # 回滚条件化文案不带内部批号
    mn = re.search(r'"fcRollbackAutoInsertDelete": "([^"]*)"', sp)
    assert mn and "批" not in mn.group(1), \
        "回滚 auto_insert 提示文案不得带内部批号"
    mb2 = re.search(r'fcRollbackConfirmBody: \'([^\']*)\'', src)
    assert mb2 and "批" not in mb2.group(1), \
        "回滚确认框正文不得带内部批号"


def test_fullchain_reason_visibility_and_activity_stream_pins():
    """D2026-1010-01 卡2 钉：全链原因可见化（last_run 载体——HRO 实锤
    Console 对链 notice 是前端死信）+ 活动流去「▶」误导 + 原始日志未读
    徽标。静态结构锚，不钉具体文案全文（防小改文案即碎）。"""
    src = _app_js_source()
    # 1) 活动流阶段行不得含「▶」（纯文本无点击 handler，箭头暗示可展开）
    m = re.search(r"activity_stage_start: stage => `([^`]*)`", src)
    assert m and "▶" not in m.group(1), "活动流阶段行前缀不得含 ▶"
    # 2) digest 消费 last_run.notices / notices_truncated / skip_reason
    fn = _extract_function(src, "fullchainStatusRefresh")
    assert "run.notices" in fn, "digest 须渲染 last_run.notices 逐文件原因"
    assert "notices_truncated" in fn, "digest 须透出截断计数"
    assert "run.skip_reason" in fn, "skipped 形态须透出 skip_reason 真因"
    # 3) 口径说明常量存在（零 data-i18n，不入 i18n 冻结集）
    assert "FULLCHAIN_SCOPE_NOTE" in src
    # 4) 原始日志未读徽标：计数 helper 被 log/appendRaw 调用，点击清零还原
    assert "_bumpRawLogUnread" in src
    assert "_bumpRawLogUnread" in _extract_function(src, "log"), \
        "ConsoleManager.log 须计未读"
    assert "_bumpRawLogUnread" in _extract_function(src, "appendRaw"), \
        "ConsoleManager.appendRaw 须计未读"
    toggle_fn = _extract_function(src, "_initRawLogToggle")
    assert "openRawLogModal" in toggle_fn, \
        "原始日志开关点击须打开弹窗（内联展开退场）"


def test_console_section_layout_column_and_height_pins():
    """D2026-1010-01 卡3 钉：Console 面板布局——.console-section 族已有
    两次连带横排前科（2.6.2 批3 #refineAiAnalyzeSection、2.7.3 件⑧活动流
    三兄弟节点被 style.css:478 行向 flex 横排=owner 反馈「宽度太短/比例
    畸形」根因），钉列向修复防回退；高度加码钉（活动流 200px 上限 +
    Console 整区保底 180px）。**整区 380px 上限已由卡F（D2026-1013-01）
    废除**（硬顶截断日志+grow=0 吃不进余量），本钉改钉 40% 比例制 +
    上限不得回潮。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    m = re.search(r"\.console-section \.section-content\s*\{([^}]*)\}", css)
    assert m, "style.css 缺 .console-section .section-content 规则"
    assert "flex-direction: column" in m.group(1), \
        "Console 内容区须列向纵排（横排=活动流窄盒根因）"
    ma = re.search(r"\.console-activity\s*\{([^}]*)\}", css)
    assert ma and "max-height: 200px" in ma.group(1), \
        "活动流盒上限 200px（owner：高度加一点）"
    mc = re.search(
        r"#tab-translate \.console-collapsible:not\(\.collapsed\)"
        r"\s*\{([^}]*)\}", css)
    assert mc, "style.css 缺 Console 整区高度规则"
    assert "max-height" not in mc.group(1), \
        "Console 整区不得回潮 max-height 硬顶（卡F D2026-1013-01 已废）"
    assert "flex: 1 1 40%;" in mc.group(1), \
        "Console 整区比例 40%（与文件卡 60% 配套，grow 必须为 1）"
    assert "min-height: 180px" in mc.group(1), "Console 整区保底 180px"


def test_guide_staleness_reread_and_items_modal_pins():
    """D2026-1010-01 三轮钉：A) 导读陈旧自动重读——全链/批修复后台更新
    导读文件后页面停留旧态（owner 实证：链修完 25+3 条页面仍显示待修
    28），switchTab 须挂 __guideStalenessHook，探针消费
    output_artifact_mtime、变化即静默重读；B) 行动条目明细弹窗化——主页
    零内联渲染只留计数+入口，卡片 markup 走 guideItemCardHtml 共享构造，
    试听契约锚（.btn-audio-preview + data-timing）原样保留。"""
    src = _app_js_source()
    tab = _extract_function(src, "switchTab")
    assert "TAB_HOOKS[tabId]" in tab, "switchTab 须经注册表派发"
    assert "__guideStalenessHook" in _tab_hooks_group("tab-guide"), \
        "switchTab tab-guide 分支须挂导读陈旧检测钩子"
    fn = _extract_function(src, "guideStalenessCheck")
    assert "output_artifact_mtime" in fn, "陈旧检测须走轻量 mtime 探针"
    assert "guideLoad(true)" in fn, "检测到陈旧须静默重读"
    gl = _extract_function(src, "guideLoad")
    assert "r.mtime" in gl, "guideLoad 须捕获加载时 mtime 基线"
    gr = _extract_function(src, "guideRender")
    assert "items.map(it => {" not in gr, \
        "主页面不得再内联全量渲染条目（卡B：移入弹窗）"
    assert "guide-items-open-btn" in gr, "主页须有明细入口按钮"
    builder = _extract_function(src, "guideItemCardHtml")
    assert builder, "缺共享卡片构造 guideItemCardHtml"
    assert "btn-audio-preview" in builder and "data-timing" in builder, \
        "试听契约锚（class+data-timing）须原样保留"
    modal = _extract_function(src, "guideItems")
    assert modal and "guide-item-list" in modal, \
        "AppModal.guideItems 弹窗须有可滚动明细列表容器"


def test_style_css_no_early_comment_terminator():
    """D2026-1010-01 四轮钉（owner「UI 重合」根因）：注释文本内嵌 `*/`
    （如 `--console-*/--cl-*`）会把注释提前终结，尾部中文注释文本泄漏成
    非法 token，浏览器丢弃紧随其后的整条规则——.console-activity-header
    的 display:flex/justify/margin-bottom 自 2.7.3 起静默失效（按钮
    block 流靠左、与活动流暗盒零间距，focus 环相贴=视觉「重合」）。
    词法级防复发：切分注释/代码区后，**代码区不得含 CJK 字符**（本表
    全部中文文案都在注释内，中文泄漏=必有早闭注释）。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    code_chars = []
    i, n = 0, len(css)
    in_comment = False
    while i < n:
        ch = css[i]
        if in_comment:
            if css.startswith("*/", i):
                in_comment = False
                i += 2
                continue
            i += 1
            continue
        if css.startswith("/*", i):
            in_comment = True
            i += 2
            continue
        code_chars.append(ch)
        i += 1
    leaked = [c for c in code_chars if '\u4e00' <= c <= '\u9fff']
    assert not leaked, \
        f"代码区泄漏 {len(leaked)} 个中文字符（必有注释早闭）: " \
        + repr("".join(code_chars[max(0, code_chars.index(leaked[0]) - 40)
                               : code_chars.index(leaked[0]) + 10])[-60:])
    # 修复落点双钉：header 规则在位（此前被整条丢弃）且间距加大
    m = re.search(r"\.console-activity-header\s*\{([^}]*)\}", css)
    assert m, "style.css 缺 .console-activity-header 规则"
    assert "justify-content: space-between" in m.group(1)
    assert "margin-bottom: var(--space-2)" in m.group(1), \
        "头部行与活动流暗盒须留 8px 呼吸间距（4px+focus 环视觉黏连）"


# ============================================================================
# D2026-1012-01 P8 静态钉（impeccable detect 价值本地化，零外部依赖）：token 收口趋势门
# 口径（评议条件①）：存量先固化——三项各以 2026-10-12 实测存量为冻结清单，
# 断言=不超冻结值/不出新值（收敛允许下降并应同步下调冻结值，新增即红）。
# 存量收敛属 3.1 归一包 Tier2 范围（字号 11/10px 归位需 S6 复议，见 D2026-1012-01）。
# ============================================================================

_FROZEN_FONT_PX_SMALL = 0   # 已全量清零（d1013-卡A1，2026-10-13），Ref: D2026-1013-01
_FROZEN_RADIUS_COUNTS = {    # border-radius 硬编码非 token 档（token=8/12/16/pill/round）
    "9px": 0, "10px": 0, "6px": 0, "7px": 0, "4px": 0, "99px": 0, "999px": 0,
}
_FROZEN_COLOR_DISTINCT = {   # 组件规则内色值字面量（:root token 定义不计数）
    # 蓝阴影二字面（rgba(59,130,246,.35)/rgba(37,99,235,.3)）已随 d1015-卡H
    # 收进 :root token（--shadow-brand/--shadow-primary），本卡（d1015-卡I）
    # 移出冻结集并加收紧断言防组件回潮。
    "#fff", "rgba(0, 0, 0, 0.5)",
}


def _style_css_component_scope() -> str:
    """style.css 去掉 :root token 定义块与注释后的"组件规则"视野。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    css = re.sub(r":root\s*\{[^}]*\}", "", css)
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    return css


def test_p8_no_new_small_font_size_px():
    """钉1：font-size 硬编码 11px/10px 计数不得超冻结值（存量 24，新增即红）。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    hits = re.findall(r"font-size:\s*(11|10)px", css)
    assert len(hits) <= _FROZEN_FONT_PX_SMALL, (
        f"font-size 11px/10px 硬编码超冻结存量（{len(hits)}>{_FROZEN_FONT_PX_SMALL}）："
        "新样式请引用 --font/--font-sm/--font-xs；存量收敛后请同步下调 _FROZEN_FONT_PX_SMALL"
    )


def test_p8_no_new_border_radius_values():
    """钉2：border-radius 硬编码档位不得超冻结清单且不得出现新档位。"""
    from collections import Counter

    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    actual = Counter()
    for raw in re.findall(r"border-radius:\s*([^;]+);", css):
        raw = raw.strip()
        if "var(" in raw:
            continue
        m = re.match(r"(\d+)px", raw)
        if m and m.group(1) not in ("8", "12", "16"):
            actual[f"{m.group(1)}px"] += 1
    for value, count in actual.items():
        frozen = _FROZEN_RADIUS_COUNTS.get(value)
        assert frozen is not None, (
            f"border-radius 出现冻结清单外的新硬编码档位 {value}（{count} 处）："
            "请引用 --radius-sm/--radius/--radius-lg/--radius-pill"
        )
        assert count <= frozen, (
            f"border-radius {value} 硬编码超冻结存量（{count}>{frozen}）："
            "请引用圆角 token；存量收敛后请同步下调 _FROZEN_RADIUS_COUNTS"
        )


# ============================================================================
# d1013-卡C 间距趋势钉（gap 49 分量映射）
# 判定面 = style.css 组件区 gap / row-gap / column-gap 声明的每个 px 分量值
#（双值声明两分量各计）。非 px 形态（0 / auto / 百分比 / flex 值）不计数；
# :root 定义块内不计数。允许集：{var(--space-hair), var(--space-1), ..., var(--space-6)};
# 字面保留清单 = 空（本卡已将 4px/8px 字面全部映射为 var()）。
# Ref: D2026-1013-01 间距圆角归一
# ============================================================================


def test_gap_scale_allowlist():
    """gap 趋势钉：style.css 组件区 gap/row-gap/column-gap 每个 px 分量须在允许集内。

    允许集：{var(--space-hair), var(--space-1), var(--space-2), var(--space-3),
    var(--space-4), var(--space-5), var(--space-6)};
    字面保留清单 = 空（本卡已将 4px/8px 字面全部映射为 var()）。
    判定按空白切分逐分量进行（var 开头的混合字面双值同样逐分量核查）。
    """
    allowed = {"var(--space-hair)"} | {f"var(--space-{i})" for i in range(1, 7)}
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    # 提取组件区 gap/row-gap/column-gap 声明，去除 :root 定义块
    css_scope = re.sub(r":root\s*\{[^}]*\}", "", css)
    # 提取每个 decl 的值部分（= ; 之前的内容）
    raw_vals = re.findall(r"(gap|row-gap|column-gap):\s*([^;]+);", css_scope)
    bad = []
    for decl, raw in raw_vals:
        parts = raw.strip().split()
        if not parts:
            continue
        if all(p in allowed for p in parts):
            continue
        # 非 px 形态分量（0 / auto / 百分比 / flex 值）不计数；px 字面分量即红
        if any(re.fullmatch(r"\d+(?:\.\d+)?px", p) for p in parts):
            bad.append(f"{decl}: {raw.strip()}")
    assert not bad, (
        f"style.css 组件区出现 gap 字面 px 值（不在允许集）：{bad}——"
        "允许集：{var(--space-hair), var(--space-1), ..., var(--space-6)}"
    )


# ============================================================================
# 钉3：组件规则内色值字面量冻结（P8；d1013-卡C 验收修正恢复独立函数——
# nemotron-3.5 落 gap 钉时误删 def 行致断言体并入 gap 钉，主审 2026-10-13 复原）
# ============================================================================


def test_p8_no_new_component_color_literals():
    """钉3：组件规则内色值字面量不得出现冻结清单外的新值（:root 定义不计数）。"""
    scope = _style_css_component_scope()
    actual = set(re.findall(r"(#[0-9a-fA-F]{3,8}\b|rgba?\([^)]*\))", scope))
    new = actual - _FROZEN_COLOR_DISTINCT
    assert not new, (
        f"组件规则内出现冻结清单外的新色值字面量：{sorted(new)}——"
        "请引用语义 token（--text-*/--ok/--warn/--danger 等）或在 :root 定义新 token"
    )


def test_p25_component_scope_brand_shadow_literals_banned():
    """P2-5 钉3 收紧（d1015-卡I，Refs: D2026-1015-05）：卡H 已把组件内两枚
    蓝阴影字面收进 :root token（--shadow-brand/--shadow-primary）；本钉把
    该二字面移出 _FROZEN_COLOR_DISTINCT 后，组件规则内再写回任一字面即红
    （冻结集收缩的防回潮闭环）。负控：临时向 .btn-primary 注回
    box-shadow: 0 1px 2px rgba(37,99,235,.3); → 本钉必红。"""
    scope = _style_css_component_scope()
    for literal in ("rgba(59,130,246,.35)", "rgba(37,99,235,.3)"):
        assert literal not in scope, (
            f"组件规则内回潮蓝色阴影字面 {literal}——"
            "请引用 :root token --shadow-brand/--shadow-primary（d1015-卡H）"
        )


def test_active_text_dark_aa_pinned():
    """P2-5 暗侧 active-text 钉（d1015-卡I，Refs: D2026-1015-05）：卡H 暗侧
    active 文字 AA 修复须有钉保护——style.dark.css 的 :root 覆盖块必须含
    --active-text 声明且值为 var(--primary)（#60A5FA，暗底约 6.48:1）；缺失
    即回退浅色 --primary-strong（#3B82F6）在暗底对比度不足。负控：临时注释
    该行 → 本钉必红。"""
    css = (ASSETS / "style.dark.css").read_text(encoding="utf-8")
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    m = re.search(r":root\s*\{([^}]*)\}", css)
    assert m, "style.dark.css 缺 :root 覆盖块"
    decl = re.search(r"--active-text\s*:\s*([^;}]+)", m.group(1))
    assert decl, \
        "style.dark.css :root 缺 --active-text 暗侧覆盖声明（AA 修复钉）"
    assert decl.group(1).strip() == "var(--primary)", (
        "暗侧 --active-text 必须覆盖为 var(--primary)（#60A5FA，AA 修复）；"
        f"实测 {decl.group(1).strip()!r}"
    )


# ============================================================================
# d1013-卡B 行高趋势钉（6 档收敛三值）
# 判定面 = style.css 组件区（去 :root 块，照 _style_css_component_scope 先例）。
# 允许集：1.55（多行文本基准，body 同值）/ var(--lh-tight)（单行紧凑 chip）/
#         字面 1（图标行盒豁免）；其余字面（1.6/1.5/1.25/30px/1.4 等）一律红。
# index.html 内联面不入钉（唯一内联 line-height:1.6 于 index.html:647 为已知留存边界）。
# Ref: D2026-1013-01 行高归一
# ============================================================================

_LINE_HEIGHT_ALLOWLIST = {"1.55", "var(--lh-tight)", "1"}


def test_line_height_scale_allowlist():
    """行高趋势钉：style.css 组件规则内 line-height 值须在允许集内。

    允许集：1.55 / var(--lh-tight) / 字面 1；其余字面一律红。
    判定面 = style.css 组件区（去 :root 块）。
    """
    scope = _style_css_component_scope()
    bad = []
    for raw in re.findall(r"line-height:\s*([^;]+);", scope):
        raw = raw.strip()
        if raw in _LINE_HEIGHT_ALLOWLIST:
            continue
        bad.append(raw)
    assert not bad, (
        f"style.css 组件规则出现白名单外 line-height 值：{bad}——"
        "允许集：1.55 / var(--lh-tight) / 字面 1；"
        "6 档收敛三值（d1013-卡B），新增档位须回终审"
    )


# ============================================================================
# d1013-卡A1 字号白名单钉（LC-3，owner 拍板钉死口径）
# 判定面 = style.css（去 :root 块）与 index.html（内联 style 属性）的全部 font-size 声明。
# 允许集：var(--font) / var(--font-sm) / var(--font-xs) 三档 token 引用；
#         px 豁免清单 {15, 16, 20, 22, 30, 32, 42}px（只增不减，新增项须回终审）。
# Ref: D2026-1013-01 LC-3
# ============================================================================

_FONT_SIZE_TOKENS = {"var(--font)", "var(--font-sm)", "var(--font-xs)"}
_FONT_SIZE_PX_ALLOWLIST = {15, 16, 20, 22, 30, 32, 42}
_FROZEN_INLINE_FONT_PX = 0   # index.html 内联 font-size 存量冻结（d1013-卡A2 已清存量，卡B 收紧归零）


def test_font_size_scale_allowlist():
    """字号白名单钉：style.css 与 index.html 全部 font-size 声明须在允许集内。

    允许集：var(--font)/var(--font-sm)/var(--font-xs) 三档 token 引用；
           px 豁免清单 {15, 16, 20, 22, 30, 32, 42}px。
    style.css 判定面去 :root token 定义块；index.html 扫内联 style 属性中的 font-size。
    """
    # --- style.css 面（去 :root 块） ---
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    css_no_root = re.sub(r":root\s*\{[^}]*\}", "", css)
    css_values = re.findall(r"font-size:\s*([^;]+);", css_no_root)
    css_bad = []
    for raw in css_values:
        raw = raw.strip()
        if raw in _FONT_SIZE_TOKENS:
            continue
        m = re.match(r"([\d.]+)px", raw)
        if m and float(m.group(1)) in _FONT_SIZE_PX_ALLOWLIST:
            continue
        css_bad.append(raw)
    assert not css_bad, (
        f"style.css 出现白名单外 font-size 值：{css_bad}——"
        "请引用 --font/--font-sm/--font-xs 或在豁免清单内（新增须回终审）"
    )

    # --- index.html 面（内联 style 属性中的 font-size） ---
    html = INDEX_HTML.read_text(encoding="utf-8")
    inline_values = re.findall(r'style="[^"]*font-size:\s*([^;"]+)[;"]', html)
    inline_frozen_count = 0
    for raw in inline_values:
        raw = raw.strip()
        if raw in _FONT_SIZE_TOKENS:
            continue
        m = re.match(r"([\d.]+)px", raw)
        if m and float(m.group(1)) in _FONT_SIZE_PX_ALLOWLIST:
            continue
        # 非豁免 px 值走存量冻结计数（只增不减，新增即红）
        inline_frozen_count += 1
    assert inline_frozen_count <= _FROZEN_INLINE_FONT_PX, (
        f"index.html 内联 font-size 非豁免 px 计数超冻结存量（{inline_frozen_count}>{_FROZEN_INLINE_FONT_PX}）："
        "新增内联 px 字号须回终审下调冻结值"
    )


# ============================================================================
# D2026-1012-01 地基批 卡4：组件 active 指示 token 归一（别名层静态钉）
# 阶段 2 统一调激活态只动 :root 别名层一处；收编规则体内禁止回退直引品牌 token。
# ============================================================================

_ACTIVE_ALIAS_TOKENS = ("--active-bg", "--active-text", "--active-border", "--active-bar")
# 三条收编规则；.feature-badge.active 是语义态（--ok-soft/--ok）不收编，故不在清单
_ACTIVE_RULE_SELECTORS = (".side-tab-btn.active", ".review-page-btn.active",
                          ".dict-kind-chip.active")
_ACTIVE_BANNED_REFS = ("--primary-soft", "--primary-strong", "--primary-border")


# ---------------------------------------------------------------------------
# D2026-1012-01 阶段 2 首批 B-04：进度定量反馈（.progress-meta 恢复）
# ---------------------------------------------------------------------------

def test_progress_meta_div_in_place():
    """B-04 钉①：.progress-meta div 在位（data-testid 承载，零 id 零 data-i18n）。

    人工推演（缺失场景）：progress-container 内无 .progress-meta div 时，
    ProgressManager.init() 的 document.querySelector('.progress-meta') 返回
    null，setProgress 内 progressMeta 分支整段跳过——进度条宽度正常但
    阶段名/批次/百分比定量行永远不显示（静默失效）。修复后 div 常驻，
    init 取得到，setProgress 每拍填充。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r'<div class="progress-meta" data-testid="progress-meta">',
                  html)
    assert m, "index.html 缺少 .progress-meta div（data-testid 承载）"
    # 零 id 零 data-i18n（class+testid 承载，FROZEN 契约不动）
    # 注意：用 \bid=" 而非 'id=' 避免误匹配 data-testid= 子串
    tag = m.group(0)
    assert not re.search(r'\bid="', tag), \
        ".progress-meta 不得携带 id（FROZEN_IDS 冻结）"
    assert 'data-i18n' not in tag, ".progress-meta 不得携带 data-i18n（键冻结）"


def test_app_js_set_progress_updates_meta():
    """B-04 钉②：app.js setProgress 更新点含 progress-meta 赋值。

    人工推演（缺失场景）：setProgress 只写 progressFill 宽度、不碰
    progressMeta 时，定量行永远空白（同钉① 静默失效）。修复后
    setProgress 内 progressMetaLeft/Right 双 span 同步填充，且
    idle 态（无阶段名且百分比为 0）整行留空。
    """
    src = _app_js_source()
    body = _extract_function(src, "setProgress")
    # setProgress 必须同时驱动 progressFill 与 progressMeta（同一更新点）
    assert "this.progressFill.style.width" in body, \
        "setProgress 必须保留 progressFill 宽度驱动（同源更新点）"
    assert "this.progressMetaLeft.textContent" in body and \
        "this.progressMetaRight.textContent" in body, \
        "setProgress 必须同步填充 progressMeta 双 span（左段+右段）"
    # 右段百分比取整（与 fill 宽度同一数值源）
    assert "Math.round(percent)" in body, \
        "右段百分比必须由 fill 宽度同一数值源取整"
    # 左段批次格式：阶段名 · 批次 N / M（无批次态只给阶段名）
    assert "批次 ${batchNo} / ${batchTotal}" in body, \
        "左段批次文案格式不符（阶段名 · 批次 N / M）"
    # idle 态整行留空
    assert "isEmpty" in body and "percent === 0" in body, \
        "idle 态（无阶段名且百分比为 0）必须整行留空"
    # 批次号取自 status 对象（与 progressFill 同源）
    assert "status.batch" in src and "status.batch_total" in src, \
        "批次号必须取自 status 对象（与 progressFill 同源）"


def test_progress_meta_no_id_no_i18n():
    """B-04 钉③：progress-meta 行零 id 零 data-i18n（防解冻漂移）。

    人工推演（漂移场景）：.progress-meta 携带 id 或 data-i18n 时，
    FROZEN_IDS/FROZEN_I18N_KEYS 钉⑤双集合自证失败（集合漂移）。
    修复后 .progress-meta 只以 class+testid 承载，双集合零增减。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    m = re.search(r'<div class="progress-meta"[^>]*>', html)
    assert m, "index.html 缺少 .progress-meta div"
    tag = m.group(0)
    assert not re.search(r'\bid="', tag), \
        ".progress-meta 携带 id（FROZEN_IDS 钉⑤双集合自证失败）"
    assert 'data-i18n' not in tag, \
        ".progress-meta 携带 data-i18n（FROZEN_I18N_KEYS 钉⑤双集合自证失败）"


def test_active_indicator_tokens_alias_layer():
    """卡4：:root 含四个 --active-* 别名定义；三条 active 规则体内不再直引品牌 token。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    root = re.search(r":root\s*\{([^}]*)\}", css)
    assert root, "style.css 缺 :root token 定义块"
    for token in _ACTIVE_ALIAS_TOKENS:
        assert re.search(rf"{re.escape(token)}\s*:", root.group(1)), (
            f":root 缺组件激活指示别名 token {token} 定义——"
            "阶段 2 调激活态须只动 :root 别名层一处"
        )
    for sel in _ACTIVE_RULE_SELECTORS:
        m = re.search(re.escape(sel) + r"\s*\{([^}]*)\}", css)
        assert m, f"style.css 缺 {sel} 规则"
        for banned in _ACTIVE_BANNED_REFS:
            assert banned not in m.group(1), (
                f"{sel} 规则体残留直引 {banned}：请改引 --active-* 别名"
                "（.feature-badge.active 语义态不收编，保持 --ok-*）"
            )


# ---------------------------------------------------------------------------
# 卡8 B-06（D2026-1012-01，阶段 2 首批）：右栏卡3/引擎页主栏 标题缩短——
# MSG.refine_panel_title 改短句「两阶段流水线」（改值不改键，键集零变化由
# 钉⑤b 快照冻结自证）；完整句不落 index.html 静态属性（红线 title 中文须
# data-i18n-title，而后者会被 MSG 短值覆写），改由 applyI18n 回填悬停
# （引擎页主栏 :201 与右栏卡3 :1001 同键双渲染，两处同步）。
# ---------------------------------------------------------------------------

_B06_SHORT_TITLE = '两阶段流水线'
_B06_FULL_TITLE = '净语翻译 · 两阶段流水线（净语+翻译 → 审校+抛光）'


def _b06_block_title_frags() -> list:
    """index.html 两处 refine_panel_title block-title 的开标签+内联文本片段。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    frags = re.findall(
        r'<div class="block-title" data-i18n="refine_panel_title"[^>]*>[^<]*',
        html)
    assert len(frags) == 2, \
        "refine_panel_title block-title 应恰两处（引擎页主栏+右栏卡3），" \
        f"实为 {len(frags)}"
    return frags


def test_b06_msg_refine_panel_title_shortened_pinned():
    """①MSG 值改短句（键名/键数零变化；完整句不再由 MSG 渲染）。"""
    m = re.search(r"^\s*refine_panel_title: '([^']*)'", _app_js_source(), re.M)
    assert m and m.group(1) == _B06_SHORT_TITLE, \
        f"MSG.refine_panel_title 值漂移: {m and m.group(1)}"


def test_b06_index_block_titles_shortened_pinned():
    """②index.html 两处静态回退文本同步缩短（防 data-i18n 未注入时长句回退折行）。"""
    for frag in _b06_block_title_frags():
        assert frag.endswith(">" + _B06_SHORT_TITLE), f"静态回退文本未缩短: {frag}"


def test_b06_full_sentence_hover_pinned():
    """③完整句悬停由 applyI18n 回填（引擎页主栏+右栏卡3 同键双渲染，两处同步）。

    不写静态 title= 完整句：红线 test_html_has_no_unmarked_user_visible_chinese
    的属性分支要求 title（含 *-title= 子串属性）中文须同标签 data-i18n-title，
    而 data-i18n-title 会被 applyI18n 以 MSG 短值覆写（完整句失效）——故完整句
    在 app.js 回填，index.html 零静态中文悬停（本卡为零 data-i18n 键改动）。"""
    body = _extract_function(_app_js_source(), "applyI18n")
    assert '[data-i18n="refine_panel_title"]' in body, \
        "applyI18n 须定位两处 refine_panel_title 回填悬停"
    assert _B06_FULL_TITLE in body, "applyI18n 缺完整句悬停文案"
    for frag in _b06_block_title_frags():
        assert _B06_FULL_TITLE not in frag, \
            f"完整句不得静态落 index.html（红线 title 中文须 data-i18n-title）: {frag}"


def test_b06_i18n_keyset_unchanged_pinned():
    """④键名/键数零变化自证：refine_panel_title 仍被 index.html 引用两处、
    本卡未新增任何 data-i18n* 键（187 全集冻结由钉⑤b 另行把关）。"""
    assert "refine_panel_title" in _js_msg_keys()
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert html.count('data-i18n="refine_panel_title"') == 2
    assert 'data-i18n-title="refine_panel_title"' not in html, \
        "本卡为零 data-i18n 键改动，不得挂 data-i18n-title（会被 MSG 短值覆写）"


# ---------------------------------------------------------------------------
# d1013-卡D（D2026-1013-01）：中英混排——AI 区 4 处英文 label/option MSG 运行时回填
# + 英文 label 白名单钉（LC-8 口径：白名单只增不减、新增项须回终审）
# ---------------------------------------------------------------------------

_D1013_CARD_D_MSG_KEYS = (
    "ai_provider_label",
    "follow_stage_default",
    "ai_model_label",
    "cross_film_window",
)


def test_d1013_card_d_msg_keys_present():
    """MSG 表含 d1013-卡D 新增 4 键（值必须中文——test_strings_and_shortcut.py 有 MSG 全值中文钉）。"""
    keys = _js_msg_keys()
    for key in _D1013_CARD_D_MSG_KEYS:
        assert key in keys, f"MSG 缺少 d1013-卡D 新键: {key}"
        m = re.search(rf"^\s*{key}:\s*'([^']*)'", _app_js_source(), re.M)
        assert m and m.group(1), f"MSG 键 {key} 文案为空"
        # 值必须含中文（由 test_msg_values_are_chinese 统一钉，此处仅非空自证）
        assert any("\u4e00" <= ch <= "\u9fff" for ch in m.group(1)), \
            f"MSG[{key!r}] 应为中文文案: {m.group(1)!r}"


def test_d1013_card_d_apply_i18n_backfill_calls_pinned():
    """applyI18n 内 4 处回填调用在位（防回填被误删，照 B-06 refine_panel_title 先例）。

    目标元素：index.html:729 label[for=aiProviderSel]、:731 option[value=follow]、
    :740 label[for=aiModelInput]、:758 label[for=aggregateWindowSel]。
    """
    body = _extract_function(_app_js_source(), "applyI18n")
    # 逐项 null 守卫模式（B-06 先例：const el = querySelector(...); if (el) el.textContent = MSG.key;）
    for key, selector in (
        ("ai_provider_label", 'label[for="aiProviderSel"]'),
        ("follow_stage_default", '#aiProviderSel option[value="follow"]'),
        ("ai_model_label", 'label[for="aiModelInput"]'),
        ("cross_film_window", 'label[for="aggregateWindowSel"]'),
    ):
        assert f'querySelector(\'{selector}\')' in body, \
            f"applyI18n 缺 {key} 目标定位: {selector}"
        assert f"MSG.{key}" in body, f"applyI18n 缺 {key} 回填赋值"
        assert "if (" in body and "textContent" in body, \
            f"applyI18n {key} 回填须含 null 守卫"


# 英文 label 白名单钉（LC-8 口径，回链 d1013-卡D 与 D2026-1013-01 LC-8）
# 判定面 = index.html 文本节点（去注释/去 script/style）；
# 同法复用 test_html_has_no_unmarked_user_visible_chinese 的解析骨架反向检测
# 排除：含中文的节点；带 data-i18n/data-i18n-title/data-i18n-placeholder 属性元素内的文本
# 允许集（静态写死、只增不减、新增项须回终审）：
#   - 4 处回填前静态字面：Analysis provider / Follow stage A (default) / Analysis model / Cross-film window
#   - owner 拍板保留：API Key（:253/:297 两处）
#   - 品牌 option：DeepSeek API / LM Studio (local) / Ollama (local) / SiliconFlow / Zen (free)
# 白名单外英文文本节点（含 ≥2 连续拉丁字母）即红；&times; 等 HTML 实体不算。

_D1013_EN_ALLOWLIST = frozenset({
    # d1013-卡D 4 处回填前静态字面
    "Analysis provider",
    "Follow stage A (default)",
    "Analysis model",
    "Cross-film window",
    # owner 拍板保留
    "API Key",
    # 品牌 option
    "DeepSeek API",
    "LM Studio (local)",
    "Ollama (local)",
    "SiliconFlow",
    "Zen (free)",
})


def _iter_html_text_nodes_for_en_allowlist():
    """遍历 index.html 用户可见文本节点，产出 (文本, 所在标签属性字典, 行号)。

    照既有钉 test_html_has_no_unmarked_user_visible_chinese 的解析骨架反向复用：
    - 去注释、去 script/style
    - 文本节点含 ≥2 连续拉丁字母 → 候选
    - 排除：含中文的节点；所在标签带 data-i18n/data-i18n-title/data-i18n-placeholder
    - HTML 实体（&...;）不计入拉丁字母判定
    """
    import html.parser

    html_text = INDEX_HTML.read_text(encoding="utf-8")
    # 去注释
    html_text = re.sub(r"<!--.*?-->", "", html_text, flags=re.S)
    # 去 script/style 标签及内容
    html_text = re.sub(r"<(script|style)[^>]*>.*?</\1>", "", html_text, flags=re.S | re.I)

    class EnTextCollector(html.parser.HTMLParser):
        def __init__(self):
            super().__init__(convert_charrefs=True)
            self.results = []
            self.stack = []  # [(tag, attrs_dict)]

        def handle_starttag(self, tag, attrs):
            if tag in ("script", "style"):
                return
            self.stack.append((tag, dict(attrs)))

        def handle_endtag(self, tag):
            if tag in ("script", "style"):
                return
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == tag:
                    del self.stack[i:]
                    break

        def handle_data(self, data):
            if not data.strip():
                return
            cur_attrs = self.stack[-1][1] if self.stack else {}
            pos = self.getpos()
            self.results.append((data, cur_attrs, pos[0]))

        def handle_entityref(self, name):
            pass

    parser = EnTextCollector()
    parser.feed(html_text)
    parser.close()
    return parser.results


def test_html_en_text_allowlist():
    """index.html 英文 label 白名单钉（LC-8 口径，回链 d1013-卡D 与 D2026-1013-01 LC-8）。

    判定面 = index.html 文本节点（去注释/去 script/style）；
    排除：含中文的节点；带 data-i18n/data-i18n-title/data-i18n-placeholder 属性元素内的文本。
    允许集：_D1013_EN_ALLOWLIST（静态写死、只增不减、新增项须回终审）。
    白名单外英文文本节点（含 ≥2 连续拉丁字母）即红；&times; 等 HTML 实体不算。
    """
    violations = []
    for text, attrs, line_no in _iter_html_text_nodes_for_en_allowlist():
        # 排除：含中文
        if re.search(r"[\u4e00-\u9fff]", text):
            continue
        # 排除：所在标签带 data-i18n*
        if any(k in attrs for k in ("data-i18n", "data-i18n-title", "data-i18n-placeholder")):
            continue
        # 去除 HTML 实体（&...;）后检测 ≥2 连续拉丁字母
        plain = re.sub(r"&[a-zA-Z0-9#]+;", "", text)
        if re.search(r"[A-Za-z]{2,}", plain):
            # 归一化：连续空白折叠、首尾去空
            norm = re.sub(r"\s+", " ", plain).strip()
            # 允许集精确匹配（全字符串）
            if norm not in _D1013_EN_ALLOWLIST:
                violations.append(f"行 {line_no}: {norm!r}（标签属性: {attrs}）")

    assert not violations, (
        "index.html 存在白名单外英文文本节点（LC-8：白名单只增不减、新增项须回终审；"
        "回链 d1013-卡D 与 D2026-1013-01 LC-8）：\n" + "\n".join(violations)
    )


# ---------------------------------------------------------------------------
# 卡9 B-07（D2026-1012-01，阶段 2 首批）：checkbox → toggle 滑块（纯 CSS）——
# accent-color 原生方案删净；appearance:none 轨道 + ::before 圆形滑块 +
# :checked 位移变色；只用既有 token（零新字面色值，P8 钉3 口径）；
# :focus-visible 焦点环保留（P0-4）。底层 input 与 id/事件零改动（纯视觉层）。
# ---------------------------------------------------------------------------

_B07_TOGGLE_BASE = re.compile(
    r'input\[type="checkbox"\]\s*\{([^}]*)\}', re.S)


def _b07_toggle_blocks(css: str) -> list:
    """style.css 中 checkbox 相关规则块（选择器, 规则体）列表。"""
    return re.findall(
        r'(input\[type="checkbox"\][^{]*?)\s*\{([^}]*)\}', css, re.S)


def test_b07_checkbox_toggle_pinned():
    """卡9 B-07：checkbox 规则含 appearance:none 轨道 + ::before 圆形滑块 +
    :checked 位移变色，且不含 accent-color 旧方案。

    人工推演（缺失场景）：仅删 ::before 滑块规则时，:checked::before 的
    transform 无作用对象——checked 后轨道变色但无滑块平移，toggle 语义
    视觉丢失（新钉红）。accent-color 残留则与 appearance:none 双方案并存。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    # 旧方案删净
    assert "accent-color" not in css, \
        "style.css 残留 accent-color 原生方案（B-07 已改纯 CSS toggle）"
    base = _B07_TOGGLE_BASE.search(css)
    assert base, 'style.css 缺 input[type="checkbox"] 规则块'
    body = base.group(1)
    assert "appearance: none" in body, \
        'checkbox 轨道必须 appearance:none（去原生形态）'
    assert "border-radius: var(--radius-pill)" in body, \
        "toggle 轨道圆角必须引 --radius-pill token"
    # ::before 圆形滑块（伪元素规则块独立存在，先红场景即删此块）
    knob = re.search(
        r'input\[type="checkbox"\]::before\s*\{([^}]*)\}', css, re.S)
    assert knob, '缺少 input[type="checkbox"]::before 滑块规则块'
    assert "border-radius: var(--radius-round)" in knob.group(1), \
        "滑块必须为圆形（--radius-round token）"
    assert "position: absolute" in knob.group(1), \
        "滑块必须绝对定位叠在轨道内"
    # :checked 位移 + 变色
    checked_move = re.search(
        r'input\[type="checkbox"\]:checked::before\s*\{([^}]*)\}', css, re.S)
    assert checked_move and "transform: translateX(" in checked_move.group(1), \
        ":checked::before 必须 translateX 平移（无位移则 toggle 语义视觉丢失）"
    checked_base = re.search(
        r'input\[type="checkbox"\]:checked\s*\{([^}]*)\}', css, re.S)
    assert checked_base and "var(--primary)" in checked_base.group(1), \
        ":checked 轨道必须变色为 var(--primary)"
    # 焦点环保留（P0-4）：不得 outline:none，focus-visible 环在位
    fv = re.search(
        r'input\[type="checkbox"\]:focus-visible\s*\{([^}]*)\}', css, re.S)
    assert fv and "outline: var(--focus-outline)" in fv.group(1), \
        "checkbox 必须保留 :focus-visible 焦点环（--focus-outline）"


def test_b07_toggle_zero_new_literals_pinned():
    """卡9 B-07 补钉：toggle 全部规则体内零字面量色值/零新圆角档——
    轨道/滑块颜色与圆角只走既有 token（P8 钉3 同口径，范围收窄到本批规则）。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    blocks = _b07_toggle_blocks(css)
    assert blocks, "未匹配到任何 checkbox 规则块"
    joined = "".join(body for _, body in blocks)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(", joined), \
        "toggle 规则体内出现字面色值（应引 --primary/--surface-* 等既有 token）"
    for sel, body in blocks:
        for m in re.finditer(r"border-radius:\s*([^;]+);", body):
            assert "var(" in m.group(1), (
                f"{sel.strip()} 圆角硬编码 {m.group(1).strip()}——"
                "请引 --radius-pill/--radius-round token（P8 钉2 同口径）")


# ---------------------------------------------------------------------------
# 卡10 B-10（D2026-1012-01，阶段 2 首批）：七页页头 + tabpanel 语义——
# 其余 6 页（engine/asrdict/glossary/guide/advanced/review）顶部各加与
# tab-translate :108-113 同构的 .page-head（h1 复用导航既有 tabXxx 键，与
# 导航按钮同键双元素，零新增键零新增 id）；7 个 .tab-page 补
# role="tabpanel" + aria-label 静态文本（h1 无 id，不走 aria-labelledby，
# 避免为 labelledby 新增 id）；7 个导航 .side-tab-btn 补 aria-controls 指向
# 对应 .tab-page 既有 id（FROZEN_IDS 只引用不新增）；tab-translate 既有页头
# （app_header_title + main_subtitle）原样不动。
# ---------------------------------------------------------------------------

# 新增页头的 6 页：tab-page id ->（页头 h1 data-i18n 键, 静态回退现值）
_B10_NEW_HEADS = {
    "tab-engine": ("tabEngine", "API 与模型选择"),
    "tab-asrdict": ("tabAsrDict", "ASR 与词典"),
    "tab-glossary": ("tabGlossary", "词库与模板"),
    "tab-guide": ("tabGuide", "质量与建议"),
    "tab-advanced": ("tabAdvanced", "高级参数"),
    "tab-review": ("tabReview", "校对"),
}

# 七页 aria-label 静态文本（取对应 tabXxx 现值；含 tab-translate 共 7 页）
_B10_PANEL_LABELS = {
    "tab-translate": "字幕翻译",
    "tab-review": "校对",
    "tab-guide": "质量与建议",
    "tab-engine": "API 与模型选择",
    "tab-asrdict": "ASR 与词典",
    "tab-glossary": "词库与模板",
    "tab-advanced": "高级参数",
}


def _b10_tab_page_tag(html: str, tab_id: str) -> str:
    """提取指定 .tab-page 容器开标签（跨行属性容忍）。"""
    m = re.search(
        r'<div class="tab-page(?: active)?" id="' + re.escape(tab_id)
        + r'"[^>]*>', html, re.S)
    assert m, f"index.html 未找到 .tab-page #{tab_id}"
    return m.group(0)


def _b10_tab_page_body(html: str, tab_id: str) -> str:
    """提取指定 .tab-page 区间体（开标签之后至下一个 .tab-page 或 </main>）。"""
    i = html.index(f'id="{tab_id}"')
    start = html.index(">", i) + 1
    nxt = [p for p in (html.find('<div class="tab-page', start),
                       html.find("</main>", start)) if p != -1]
    assert nxt, f"#{tab_id} 区间无终点锚"
    return html[start:min(nxt)]


def test_b10_six_page_heads_pinned():
    """①其余 6 页顶部各一页头，结构与 tab-translate :108-113 同构：
    .page-head > .page-head-text > h1.page-title（data-i18n=tabXxx + 静态回退现值）。

    人工推演（先红场景）：临时删除任一新增页头 → 本钉红（页头缺失或页头
    不再是页内首个非注释元素）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for tab_id, (key, text) in _B10_NEW_HEADS.items():
        head = re.match(
            r'\s*(?:<!--.*?-->\s*)*<div class="page-head">\s*'
            r'<div class="page-head-text">\s*'
            r'<h1 class="page-title" data-i18n="([^"]+)">([^<]*)</h1>\s*'
            r'</div>\s*</div>',
            _b10_tab_page_body(html, tab_id), re.S)
        assert head, f"#{tab_id} 顶部缺少与 tab-translate 同构的 .page-head 页头"
        assert (head.group(1), head.group(2)) == (key, text), (
            f"#{tab_id} 页头 h1 键/静态回退文本漂移: "
            f"{head.group(1)}/{head.group(2)}（应为 {key}/{text}）")


def test_b10_translate_page_head_untouched_pinned():
    """②tab-translate 既有页头（app_header_title + main_subtitle）原样保留不动。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    frag = _b10_tab_page_body(html, "tab-translate")
    m = re.search(r'<div class="page-head">.*?</div>\s*</div>', frag, re.S)
    assert m, "tab-translate 既有页头缺失"
    assert 'data-i18n="app_header_title"' in m.group(0), \
        "tab-translate 页头缺 app_header_title 键"
    assert 'data-i18n="main_subtitle"' in m.group(0), \
        "tab-translate 页头缺 main_subtitle 副标题"
    assert 'data-i18n="tabTranslate"' not in m.group(0), \
        "tab-translate 页头不得改挂 tabTranslate 键（既有页头原样保留）"


def test_b10_tabpanels_role_and_label_pinned():
    """③7 个 .tab-page 均带 role="tabpanel" + aria-label（静态文本=对应
    tabXxx 现值；h1 无 id 故不走 aria-labelledby，避免为 labelledby 新增 id）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for tab_id, label in _B10_PANEL_LABELS.items():
        tag = _b10_tab_page_tag(html, tab_id)
        assert 'role="tabpanel"' in tag, f"#{tab_id} 容器缺 role=tabpanel"
        assert f'aria-label="{label}"' in tag, \
            f"#{tab_id} aria-label 缺失或非 tabXxx 现值: {label}"
        assert "aria-labelledby" not in tag, \
            f"#{tab_id} 走了 aria-labelledby（须 aria-label 静态文本，禁新增 id）"
    panel_count = html.count('role="tabpanel"')
    assert panel_count == 7, f"role=tabpanel 应恰 7 处（实测 {panel_count}）"


def test_b10_nav_aria_controls_pinned():
    """④7 个导航 .side-tab-btn 的 aria-controls 与 .tab-page id 一一对应
    （同一按钮 data-tab == aria-controls == 目标页既有 id；集合双向相等）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    tags = re.findall(r'<button[^>]*data-tab="([^"]+)"[^>]*>', html, re.S)
    assert len(tags) == 7, f"带 data-tab 的按钮应恰 7 个（实测 {len(tags)}）"
    controls = []
    for m in re.finditer(
            r'<button[^>]*class="side-tab-btn[^"]*"[^>]*data-tab="([^"]+)"[^>]*>',
            html, re.S):
        tag, tab_id = m.group(0), m.group(1)
        cm = re.search(r'aria-controls="([^"]+)"', tag)
        assert cm, f"导航按钮 data-tab={tab_id} 缺 aria-controls"
        assert cm.group(1) == tab_id, \
            f"aria-controls 与 data-tab 不一致: {cm.group(1)} != {tab_id}"
        controls.append(cm.group(1))
    assert len(controls) == 7, \
        f".side-tab-btn 应恰 7 个且均带 aria-controls（实测 {len(controls)}）"
    assert set(controls) == set(_B10_PANEL_LABELS), \
        f"aria-controls 与 .tab-page id 集合不一一对应: {sorted(set(controls) ^ set(_B10_PANEL_LABELS))}"


def test_b10_zero_new_id_zero_new_key_pinned():
    """⑤零新增 id / 零新增键（钉⑤双集合自证的本卡局部前置）：页头块内零 id；
    7 个页头键均为导航既有键（同键双元素，集合语义零增减——FROZEN_IDS=222 /
    FROZEN_I18N_KEYS=186 全等冻结另由钉⑤a/⑤b 快照自证；187→186=artifact_note
    退役，D2026-1013-01 真机反馈轮）；aria-controls 只
    引用既有 .tab-page id，容器不新增 data-i18n。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    nav = re.search(r'<nav class="rail-nav".*?</nav>', html, re.S)
    assert nav, "未找到 rail-nav 导航块"
    nav_html = nav.group(0)
    msg_keys = _js_msg_keys()
    head_count = html.count('<div class="page-head">')
    assert head_count == 7, f"页头应恰 7 处（7 页各一，实测 {head_count}）"
    for tab_id, (key, _text) in _B10_NEW_HEADS.items():
        frag = _b10_tab_page_body(html, tab_id)
        block = re.search(
            r'<div class="page-head">.*?</div>\s*</div>', frag, re.S)
        assert block and f'data-i18n="{key}"' in block.group(0), \
            f"#{tab_id} 页头块解析失败"
        assert 'id="' not in block.group(0), \
            f"#{tab_id} 页头携带 id（FROZEN_IDS 钉⑤a 集合漂移）"
        assert key in msg_keys, f"页头键 {key} 不在 app.js MSG 键表（新增键嫌疑）"
        assert f'data-i18n="{key}"' in nav_html, \
            f"页头键 {key} 非导航既有键（须与导航按钮同键双元素复用）"
    for tab_id in _B10_PANEL_LABELS:
        tag = _b10_tab_page_tag(html, tab_id)
        id_count = len(re.findall(r'(?<![\w-])id="', tag))
        assert id_count == 1, f"#{tab_id} 容器 id 数漂移（应恰 1，实测 {id_count}）"
        assert 'data-i18n' not in tag, \
            f"#{tab_id} 容器挂了 data-i18n（aria-label 静态文本形态，禁新键）"
    for ctl in re.findall(r'aria-controls="([^"]+)"', html):
        assert re.search(
            r'<div class="tab-page[^>]*\bid="' + re.escape(ctl) + r'"', html), \
            f"aria-controls 引用了不存在的既有 id: {ctl}"


# ---------------------------------------------------------------------------
# 卡F（回链 D2026-1013-01 / 规格=docs/design/d1013-S6复议-布局表面卷.md §1）：
# 高度弹性四改同根因（高度未做弹性分配）——translate Console grow=0
# （flex:0 1 30%）吃不进余量致底部 228px 空白；max-height:380px 硬顶截断
# 日志（D2026-1010-01 卡3「高度加一点」的上调残值）；.console-section{flex:1}
# 连带撑高 guide 两卡与 AI 分析卡（guide 首卡内容全在闭合 details 内 →
# 380px 纯白空盒）。本钉逐条锁死改后值：40%/60% 比例制 + 380 硬顶已废 +
# .console-section 回归自然高。
# ---------------------------------------------------------------------------

def test_console_flex_layout():
    """卡F 布局钉（D2026-1013-01）：translate 文件卡 60% / Console 40% 比例制，
    max-height:380px 硬顶废除，.console-section 回归 flex:0 0 auto 自然高
    （余量沉 .main 页尾，translate 的弹性由 #tab-translate 前缀规则显式承接）。

    先红后绿自证（落本钉不改 style.css 时前三条断言必红：380 硬顶仍在 /
    Console 仍 30% 且 grow=0 / .console-section 仍 flex:1；完成四处改值后转绿）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    # ① 380px 硬顶废除（超量交既有内滚承接：.console-output overflow-y:auto
    #    + min-height:0，.file-list-container overflow-y:auto，均不动）
    assert "max-height: 380px" not in css, \
        "style.css 仍残留 Console max-height:380px 硬顶（大窗日志截断根因）"
    # ② translate Console 吃 40%（grow=1 才能吃掉余量，消底部 228px 空白）
    m_console = re.search(
        r"#tab-translate \.console-collapsible:not\(\.collapsed\)"
        r"\s*\{([^}]*)\}", css)
    assert m_console, "style.css 缺 #tab-translate .console-collapsible 高度规则"
    assert "flex: 1 1 40%;" in m_console.group(1), \
        "translate Console 须 flex:1 1 40%（禁回退 grow=0 比例制）"
    # ③ .console-section 回归自然高：guide 两卡与 AI 分析卡不再被撑高
    #    （空态支路 #tab-translate:not(.has-files) 两规则零改动）
    m_section = re.search(r"\.console-section\s*\{([^}]*)\}", css)
    assert m_section, "style.css 缺 .console-section 规则"
    assert "flex: 0 0 auto;" in m_section.group(1), \
        ".console-section 须 flex:0 0 auto（禁回退 flex:1 撑高 guide/AI 卡）"
    # ④ 文件卡基准 60%（与 Console 40% 合成比例制，min-height:0 不动）
    m_card = re.search(r"#tab-translate > \.card\s*\{([^}]*)\}", css)
    assert m_card, "style.css 缺 #tab-translate > .card 规则"
    assert "flex: 1 1 60%;" in m_card.group(1), \
        "文件卡须 flex:1 1 60%（70% 基准已下调，与 Console 40% 配套）"


# ---------------------------------------------------------------------------
# d1013-卡E（回链 D2026-1013-01，三钉口径③）：W1 内联宽度趋势钉——
# index.html 表单控件 style= 内 width/min-width 声明只允许
# var(--w-*) 引用 + 布局性豁免白名单；白名单外 px/em 字面即红。
# ---------------------------------------------------------------------------

# 布局性豁免白名单（2026-10-13 落钉时实扫现状全冻结：
# width:100%×1 / width:auto×3 / width:0%×1 / min-width:0×1；
# 清单随钉冻结、只增不减）
_INLINE_WIDTH_ALLOWLIST = ("100%", "auto", "0%", "0")


def test_inline_width_allowlist():
    """W1 内联宽度趋势钉（d1013-卡E / D2026-1013-01，件2 §5.2 口径③）。

    计数对象：index.html 表单控件 style= 属性内 width/min-width
    声明的 px/em 字面；允许集 = var(--w-*) 引用 + 布局性豁免
    白名单（width:100% / width:auto / width:0% 等，落钉时实扫
    现状列全冻结，清单随钉冻结、只增不减）；白名单外 px/em 字面
    即红（5.5em 已由本卡改法 3 清零，落钉时无存量）。
    先红后绿四步自证日志入 d1013-卡E 执行记录。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    violations = []
    for s in re.finditer(r'style="([^"]*)"', html):
        for d in re.finditer(
                r"(?<![\w-])(min-)?width\s*:\s*([^;\"}]+)", s.group(1)):
            prop = "min-width" if d.group(1) else "width"
            val = d.group(2).strip()
            if re.fullmatch(r"var\(--w-[\w-]+\)", val):
                continue
            if val in _INLINE_WIDTH_ALLOWLIST:
                continue
            violations.append(
                f"行 {html.count(chr(10), 0, s.start()) + 1}: "
                f"{prop}:{val}")
    assert not violations, (
        "白名单外内联宽度字面（应改走 var(--w-*) 引用；确需新增"
        "布局性字面先冻结进白名单）: " + "; ".join(violations))


# ---------------------------------------------------------------------------
# d1013-卡G2（回链 D2026-1013-01；规格=docs/design/d1013-S6复议-布局表面卷.md
# §2.2c 折叠态结构 / §2.2d 启动默认 1240 阈值 / §2.2e localStorage 单写记忆 /
# §2.2f 零 id 零键 / §2.5 阈值断言七条）：右栏折叠两钉——
#   钉①结构钉（顺延自卡G1 无钉补落；卡N 修订：两钮融合为单钮
#       .aside-toggle-btn）：style.css 折叠态基态 grid + @media1180
#       窄窗折叠支路 + index.html 单钮 class/data-testid 在位；@media 块内
#       展态 grid 规则禁新增（防误加第二条 300px 类规则）。
#   钉②行为钉：app.js localStorage 键串 / 1240 启动默认阈值 / MSG.collapse_toggle
#       复用（零新增 MSG 键）/ aside-collapsed 类名串 / workbench null 守卫；
#       运行期零 resize 驱动（窗口阈值只管启动默认，用户显式操作永久优先）。
# ---------------------------------------------------------------------------

# 卡G2 行为面的四个字面锚点（钉②断言用；与 app.js 实现逐字对应）
_ASIDE_COLLAPSE_KEY = "subtransjav.aside.collapsed"
_ASIDE_COLLAPSE_CLASS = "aside-collapsed"
# 卡N（D2026-1013-01 追记）：折叠把手双功能融合——两钮合并为单钮双态
_ASIDE_COLLAPSE_MSEL = ".aside-toggle-btn"


def _css_media_blocks(css: str, condition: str) -> list:
    """按花括号配平提取 style.css 中指定 @media 条件的全部块源码
    （style.css 有两个 @media (max-width:1180px) 块，:406 no-aside /
    :2584 折叠支路，取块全文是断言语境所必需）。"""
    blocks = []
    for m in re.finditer(r"@media\s+" + re.escape(condition) + r"\s*\{", css):
        depth = 0
        for j in range(m.end() - 1, len(css)):
            if css[j] == "{":
                depth += 1
            elif css[j] == "}":
                depth -= 1
                if depth == 0:
                    blocks.append(css[m.start():j + 1])
                    break
        else:
            raise AssertionError(f"style.css @media {condition} 块花括号未配平")
    return blocks


def _js_block_from(source: str, start: int) -> str:
    """取 app.js 中开括号位于 start 的花括号配平代码块（向后按配平取整块）
    ——供行为钉按「折叠相关代码段」口径取片段，口径同 _extract_function /
    _tab_hooks_literal。"""
    depth = 0
    for j in range(start, len(source)):
        if source[j] == "{":
            depth += 1
        elif source[j] == "}":
            depth -= 1
            if depth == 0:
                return source[start:j + 1]
    raise AssertionError("app.js 代码块花括号未配平")


def _js_block_at(source: str, pos: str) -> str:
    """取 app.js 中位置 pos 所处最近一层花括号配平代码块。"""
    return _js_block_from(source, source.rindex("{", 0, pos))


# 语句级块开关键字：向前找「行为段边界」时跳过（try/if/catch 包裹的不是行为段）
_JS_BLOCK_OPENERS = ("try", "else", "catch", "finally", "do", "if",
                     "for", "while", "switch")


def _js_opener_kind(source: str, brace_pos: int) -> str:
    """判定 source[brace_pos] 处开括号的开关键字（先剥结尾括号组：
    `if (cond) {` / `catch (e) {` → if/catch；`(function () {` → function；
    `() => {` → 空串即函数边界）。"""
    head = source[:brace_pos].rstrip()
    while head.endswith(")"):
        depth = 0
        i = len(head) - 1
        while i >= 0:
            if head[i] == ")":
                depth += 1
            elif head[i] == "(":
                depth -= 1
                if depth == 0:
                    break
            i -= 1
        if i < 0:
            return ""
        head = head[:i].rstrip()
    m = re.search(r"([A-Za-z_$][\w$]*)$", head)
    return m.group(1) if m else ""


def _aside_collapse_segment(js: str) -> str:
    """取 app.js 承载 aside 折叠行为的整段代码（以 localStorage 键串为锚点，
    向前跳过 try/if 等语句级块取所属函数/IIFE 全段，向后按花括号配平）。
    注意：锚点必须是**代码里**首次出现的键串——注释里先出现键串会把锚点
    提前到块外，段会取错。"""
    i = js.index(_ASIDE_COLLAPSE_KEY)
    start = js.rindex("{", 0, i)
    while _js_opener_kind(js, start) in _JS_BLOCK_OPENERS:
        start = js.rindex("{", 0, start)
    return _js_block_from(js, start)


def test_aside_collapse_structure():
    """卡G2 结构钉（D2026-1013-01 §2.2c，顺延自卡G1 无钉补落）：
    ①style.css 基态 `.workbench.aside-collapsed` 折叠 grid（rail 220 + 把手 44）
    与 `@media (max-width:1180px)` 内折叠支路（rail 64 + 把手 44）均在位；
    ②index.html 把手单钮 class + data-testid 在位（零 id / 零 data-i18n 形态；
      卡N 修订：两钮融合为单钮 .aside-toggle-btn + 双态 svg 图标）；
    ③@media 块内展态 grid 规则仍只有既有 300px 一条（卡G1 卡面钉死，防误加）。

    先红场景：删任一折叠规则 / 任一钮 → 本钉红；@media 块内手加第二条
    300px 展态类规则 → 断言③红。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    # ①a 基态折叠 grid（非 @media 块内那条：取全文件首个选择器命中处）
    m_base = re.search(
        r"\.workbench\.aside-collapsed\s*\{([^}]*)\}", css)
    assert m_base, "style.css 缺 .workbench.aside-collapsed 基态 grid 规则"
    assert "grid-template-columns" in m_base.group(1), \
        ".workbench.aside-collapsed 基态规则须声明 grid-template-columns"
    assert "220px" in m_base.group(1) and "44px" in m_base.group(1), (
        "基态折叠列宽漂移（应为 rail 220px + 把手 44px）: "
        f"{m_base.group(1).strip()}")
    # ①b @media1180 折叠支路（rail 64 + 把手 44）
    narrow = [b for b in _css_media_blocks(css, "(max-width: 1180px)")
              if _ASIDE_COLLAPSE_CLASS in b]
    assert narrow, (
        "@media (max-width:1180px) 内缺 .workbench.aside-collapsed 折叠支路")
    m_narrow = re.search(
        r"\.workbench\.aside-collapsed\s*\{([^}]*)\}", narrow[-1])
    assert m_narrow and "64px" in m_narrow.group(1) \
        and "44px" in m_narrow.group(1), (
        "窄窗折叠支路列宽漂移（应为 rail 64px + 把手 44px）: "
        f"{m_narrow.group(1).strip() if m_narrow else '未解析'}")
    # ①c 折叠态内卡全隐（把手条形态，aside 内 panel-card 不占位）
    assert re.search(
        r"\.workbench\.aside-collapsed\s+\.aside\s*>\s*\.panel-card"
        r"\s*\{[^}]*display:\s*none", css), \
        "折叠态缺 .aside > .panel-card display:none（内卡未全隐）"
    # ② 单钮 class + data-testid 在位，零 id / 零 data-i18n（卡N：两钮融合单钮）
    cls = "aside-toggle-btn"
    tag = re.search(
        r"<button[^>]*class=\"" + cls + r"\"[^>]*>", html, re.S)
    assert tag, f"index.html 缺 .{cls} 按钮（卡N 单钮双态回退）"
    assert f'data-testid="{cls}"' in tag.group(0), \
        f"{cls} 缺 data-testid（黑盒锚点）"
    assert not re.search(r"(?<![\w-])id=\"", tag.group(0)), \
        f"{cls} 携带 id（FROZEN_IDS 零触碰）"
    assert "data-i18n" not in tag.group(0), \
        f"{cls} 携带 data-i18n（FROZEN_I18N 零触碰）"
    for svg_cls in ("toggle-ic-collapse", "toggle-ic-expand"):
        assert f'class="{svg_cls}"' in html, \
            f"index.html 缺 .{svg_cls} 双态图标（卡N 单钮双态）"
    # ③ @media 块内展态 grid 规则仍只有既有 300px 一条（卡G1 卡面钉死；
    #    计数走 grid-template-columns 声明，注释内的 300px 字面不计）
    media_body = re.sub(r"/\*.*?\*/", "", narrow[-1], flags=re.S)
    media_body = media_body[media_body.index("{") + 1:]   # 去掉 @media 前导
    wide_cols = [r for r in re.finditer(r"([^{}]+)\{([^}]*)\}", media_body)
                 if "grid-template-columns" in r.group(2)
                 and "300px" in r.group(2)]
    assert len(wide_cols) == 1, (
        "@media1180 块内 300px 展态 grid 规则被另立新条（卡G1 卡面钉死："
        "块内展态沿用既有 300px 一条）: " + str(len(wide_cols)))
    assert wide_cols[0].group(1).strip() == ".workbench", (
        "@media1180 块内 300px 展态规则须为既有 .workbench 一条（不得改选择器）: "
        + wide_cols[0].group(1).strip())


def test_aside_collapse_behavior():
    """卡G2 行为钉（D2026-1013-01 §2.2d/e/f + §2.5）：
    ①app.js 含 localStorage 键串 `subtransjav.aside.collapsed`（单写记忆层）；
    ②启动默认按窗口阈值 1240（innerWidth <= 1240 默认收起，记忆优先于阈值）；
    ③两钮 aria-label/title 复用既有 MSG.collapse_toggle（零新增 MSG 键）；
    ④workbench/按钮获取带 null 守卫（无 workbench 页面不崩）；
    ⑤运行期零 resize 监听驱动折叠（阈值只管启动默认，用户显式操作永久优先）。

    先红后绿自证：先落本钉不改 app.js 时，①②③④ 红（键串/1240 阈值/
    collapse_toggle 回填/守卫均不在）；完成 app.js 改法 1-2 后转绿。"""
    src = _app_js_source()
    assert _ASIDE_COLLAPSE_KEY in src, (
        "app.js 缺 localStorage 键串 subtransjav.aside.collapsed"
        "（折叠记忆层未落，§2.2e localStorage 单写）")
    seg = _aside_collapse_segment(src)
    assert _ASIDE_COLLAPSE_CLASS in seg, \
        "折叠代码段未出现 aside-collapsed 类名串（挂/摘类逻辑缺失）"
    assert re.search(r"window\.innerWidth\s*<=\s*1240", seg), \
        "折叠代码段缺 1240 启动默认阈值比较（应为 innerWidth <= 1240）"
    assert re.search(r"localStorage\.getItem\(\s*['\"]"
                     + re.escape(_ASIDE_COLLAPSE_KEY), seg), \
        "折叠代码段未从 localStorage 读回折叠记忆（记忆优先于阈值）"
    assert re.search(r"localStorage\.setItem\(\s*['\"]"
                     + re.escape(_ASIDE_COLLAPSE_KEY), seg), \
        "折叠代码段未写回 localStorage 折叠记忆（单写）"
    assert "MSG.collapse_toggle" in seg, \
        "两钮 aria-label/title 未复用既有 MSG.collapse_toggle"
    for attr in ("aria-label", "title"):
        assert re.search(r"setAttribute\(\s*['\"]" + attr + r"['\"]\s*,\s*"
                         r"MSG\.collapse_toggle", seg), \
            f"两钮 {attr} 未复用既有 MSG.collapse_toggle（零新增 MSG 键）"
    used_keys = set(re.findall(r"MSG\.([A-Za-z_][A-Za-z0-9_]*)", seg))
    assert used_keys == {"collapse_toggle"}, (
        "折叠代码段引用了 collapse_toggle 之外的 MSG 键（卡面零新增 MSG 键）: "
        f"{sorted(used_keys)}")
    assert _ASIDE_COLLAPSE_MSEL in seg, \
        "app.js 未按 .aside-toggle-btn 单选择器取把手钮（卡N 双钮已融合）"
    assert re.search(r"if\s*\(\s*!\s*workbenchEl\s*\)", seg), \
        "折叠代码段缺 workbench null 守卫（无 workbench 页面会崩）"
    # 点击路径自证：click 回调体内挂/摘类 + 写回记忆 + aria-expanded 同步
    assert "addEventListener('click'" in seg, "两钮未绑定 click 监听"
    click_i = seg.index("addEventListener('click'")
    click_open = seg.index("{", click_i)
    assert "=>" in seg[click_i:click_open] or "function" in seg[click_i:click_open], \
        "click 监听开括号定位失败（实现形态变化，请同步本钉解析口径）"
    click = _js_block_from(seg, click_open)
    assert re.search(r"classList\.toggle\(\s*['\"]" + _ASIDE_COLLAPSE_CLASS,
                     click), \
        "click 回调未挂/摘 aside-collapsed（折/展点击无效）"
    assert "localStorage.setItem" in click, \
        "click 回调未写回折叠记忆（显式操作不记忆）"
    assert "aria-expanded" in click, \
        "click 回调未同步 aria-expanded（无障碍态漂移）"
    # 启动回填：记忆/阈值默认须在 click 绑定之前挂类（首屏默认失效红线）
    assert re.search(r"classList\.toggle\(\s*['\"]" + _ASIDE_COLLAPSE_CLASS,
                     seg[:click_i]), \
        "启动回填未按记忆/阈值挂 aside-collapsed（首屏默认折叠失效）"
    # ⑤ 运行期不挂 resize 自动切换：折叠代码段内零 resize 监听，
    #    且 app.js 内任一 resize 监听所在代码块都不碰 aside 折叠
    assert "addEventListener('resize'" not in seg \
        and 'addEventListener("resize"' not in seg, \
        "折叠代码段挂了 resize 监听（运行期自动切换，禁——用户显式操作优先）"
    for m in re.finditer(
            r"addEventListener\(\s*['\"]resize['\"]", src):
        blk = _js_block_at(src, m.start())
        assert _ASIDE_COLLAPSE_CLASS not in blk, (
            "app.js 存在驱动 aside 折叠的 resize 监听（禁：1240 阈值只作用"
            "启动默认，运行期不随窗口自动切换）")


# ============================================================================
# 真机反馈回归钉（2026-10-13 走查轮，D2026-1013-01 追记）：三项修复防回潮
# ① 折叠入口显眼化（卡N 修订演进：两钮融合单钮双态，原「border+surface 防隐形」
#    立法本意由「满条热区 + hover 提色 + 常驻图标」承接；owner 融合指令）；
#    展开态形态=right:0 贴边 + 14px 竖条，折叠态整条可点（width:100% 满条热区）
# ② API Key 输入 grow 封顶：保存钮紧随输入框不贴行尾
# ③ 保存接口按钮文案：去「配置」二字（MSG 值与 index.html 静态回退同步）
# ============================================================================


def test_realdevice_feedback_pins():
    """真机反馈三项修复钉（把手单钮可点性+贴边形态【卡N 演进】/
    key input 封顶 / 保存接口文案）。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    # ① 单钮可点性（卡N 修订演进：原「两钮 border+surface 防隐形」立法本意
    #    由「满条热区 + hover 提色 + 常驻图标」承接——owner 融合指令，
    #    D2026-1013-01 追记）
    m = re.search(r"\.aside-toggle-btn\s*\{[^}]*\}", css)
    assert m, "折叠把手单钮基础块缺失（卡N 双功能把手回退）"
    blk = m.group(0)
    assert "cursor: pointer" in blk, (
        "把手单钮缺 cursor: pointer（可点 affordance 消失）")
    assert re.search(
        r"\.aside-toggle-btn:hover\s*\{[^}]*background:\s*var\(--surface\)",
        css), "把手单钮缺 hover 提色（入口可点 affordance 回潮隐形）"
    # 上行为 d1015-卡1（D2026-1015-04 §1.3#3）同步：hover 提色 token 由
    # --surface-2 改指 --surface（右栏底=--bg 灰，白提亮更可辨；立法本意不变）
    assert re.search(
        r"\.workbench\.aside-collapsed\s+\.aside-toggle-btn\s*\{[^}]*"
        r"width:\s*100%", css), (
        "折叠态把手非整条可点（应 width:100% 满条热区，卡N 件2 甲案）")
    # ①' 展开态贴边竖条形态（卡N 修订：原 right:20px 与首卡对齐由
    #    right:0 贴边 + width:14px 竖条形态承接）
    m2 = re.search(
        r"\.aside-toggle-btn\s*\{[^}]*position: absolute;[^}]*\}", css)
    assert m2 and re.search(r"right:\s*0\b", m2.group(0)) \
        and re.search(r"width:\s*14px", m2.group(0)), (
        "展开态把手形态漂移（应 right:0 贴边 + width:14px 竖条热区）")
    # ⑥ 双图标态切换（卡N 修订：原两钮显隐互换改为单钮内双 svg 显隐——
    #    默认显 collapse 图标，折叠态反转显 expand 图标）
    assert re.search(
        r"\.aside-toggle-btn\s+\.toggle-ic-expand\s*\{\s*display:\s*none",
        css), "展开态未隐 .toggle-ic-expand（双图标显隐契约漂移）"
    assert re.search(
        r"\.workbench\.aside-collapsed\s+\.aside-toggle-btn\s+"
        r"\.toggle-ic-collapse\s*\{\s*display:\s*none", css), \
        "折叠态未隐 .toggle-ic-collapse（双图标显隐契约漂移）"
    assert re.search(
        r"\.workbench\.aside-collapsed\s+\.aside-toggle-btn\s+"
        r"\.toggle-ic-expand\s*\{\s*display:\s*inline-flex", css), \
        "折叠态未显 .toggle-ic-expand（双图标显隐契约漂移）"
    # ② key input grow 封顶（保存钮紧随输入框）
    #   卡Q 追记：封顶值 280px→200px 并与 min-width 140px 同步收窄。
    #   旧 280px 断言与卡Q 卡面「max-width 200px」直接冲突、必然转红，
    #   故如实下调（立法意图「保存钮紧随输入框不贴行尾」不变，仅收窄）。
    assert re.search(
        r"#refineS1Key,\s*#refineS3Key\s*\{[^}]*max-width:\s*200px", css), (
        "#refineS1Key/#refineS3Key 缺 max-width:200px 封顶"
        "（卡Q 收窄后保存钮回潮贴行尾）")
    # ③ 保存接口文案（MSG 值+index.html 静态回退两处）
    js = _app_js_source()
    assert re.search(r"save_endpoints_btn:\s*'保存接口'", js), (
        "MSG save_endpoints_btn 文案漂移（应为「保存接口」）")
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert html.count('data-i18n="save_endpoints_btn">保存接口</span>') == 2, (
        "index.html 保存接口静态回退应恰两处且无「配置」二字")


# ============================================================================
# 卡I（D2026-1013-01 真机反馈 IA 重排第二轮）：输出目录整块并入卡3 流水线卡
# ============================================================================


def test_output_dir_in_pipeline_card():
    """卡I 位置钉（d1013-卡I / D2026-1013-01 追记，前序 9ae5c9a 误入卡1 的纠正）：

    ①index.html 中 destination-section 恰 1 处，且位于 id="pipelineCard" 之后、
      id="systemSummaryCard" 之前（= 卡3「两阶段流水线」卡内，owner 图示指明位）；
    ②卡1 区段（文档起点至 id="pipelineCard" 之间）不再含 destination-section，
      且 #featureStatus 仍留在卡1 原位（语法提示 badge 不随迁）；
    ③app.js 对 .destination-section 挂 click + keydown 两个 stopPropagation
      阻断（卡3 系整卡点击跳引擎页的链接卡，不阻断则浏览/打开/开关/输入
      一律冒泡劫持跳转）。

    先红后绿自证：先落本钉不动 index.html/app.js 时，①②红（destination-section
    仍在卡1、卡1 区段仍含之）；完成改法 1-3 后转绿。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert html.count("destination-section") == 1, (
        "index.html 中 destination-section 应恰出现 1 次（整块迁入不复制不残留）: "
        f"{html.count('destination-section')}")
    card3 = html.index('id="pipelineCard"')
    card4 = html.index('id="systemSummaryCard"')
    dest = html.index("destination-section")
    assert card3 < dest < card4, (
        "destination-section 未落在卡3 pipelineCard 与 systemSummaryCard 之间"
        f"（实际下标 dest={dest}, card3={card3}, card4={card4}）")
    card1 = html[:card3]
    assert "destination-section" not in card1, \
        "卡1 运行控制卡仍含 destination-section（输出目录应整块迁至卡3）"
    assert 'id="featureStatus"' in card1, \
        "#featureStatus 须保留在卡1 原位（语法提示 badge 不随输出目录迁至卡3）"

    # app.js：整卡跳转劫持阻断（click 与 keydown 两事件各一 stopPropagation）
    js = _app_js_source()
    m = re.search(r"querySelector\(\s*['\"]\.destination-section['\"]", js)
    assert m, "app.js 缺 .destination-section 选择器（整卡跳转冒泡未阻断）"
    i = m.start()
    assert js.index("function refreshPipelineCardHint") < i, \
        ".destination-section 阻断块须挂在 pipelineCard 绑定区（refreshPipelineCardHint 之后）"
    seg = _js_block_from(js, js.index("{", m.end()))
    assert "stopPropagation" in seg, \
        ".destination-section 阻断块缺 stopPropagation（点击仍冒泡触发整卡跳转）"
    for ev in ("click", "keydown"):
        assert re.search(r"addEventListener\(\s*['\"]" + ev + r"['\"]", seg), \
            f".destination-section 阻断块未对 {ev} 事件阻断冒泡（{ev} 仍误触 switchTab）"


# ============================================================================
# 卡K（D2026-1013-01 真机反馈 IA 重排轮）：流水线卡整卡点击统一过滤
# ============================================================================


def test_pipeline_card_click_filter():
    """d1013-卡K 新钉（D2026-1013-01 追记；评议员 HRO② 裁定：统一过滤改写进
    既有监听体，另挂监听拦不住先注册的跳转监听）：

    ①pipelineCard click 监听体含统一过滤清单串——两自动化开关 label、
      .encode-params-link、输出区 .destination-section 等交互元素不触发
      整卡跳转（散点 stopPropagation 收敛为单一入口过滤）；
    ②click 与 keydown 两监听体均含 instanceof Element 守卫，且 click 体
      switchTab('tab-engine') 仍在（只读空白区点击仍跳转的语义保留）；
    ③卡I 既有 .destination-section click+keydown stopPropagation 阻断块
      原样保留（防回潮双保险，:5176 区 test_output_dir_in_pipeline_card
      主钉已锁）。

    先红后绿自证：先落本钉不动 app.js 时红（既有监听体无过滤清单/守卫）；
    完成卡K 改法 1-2 后转绿。
    """
    js = _app_js_source()
    m = re.search(r"pipelineCard\.addEventListener\(\s*['\"]click['\"]", js)
    assert m, "app.js 缺 pipelineCard click 监听（整卡跳转入口）"
    click_body = _js_block_from(js, js.index("{", m.end()))
    m2 = re.search(r"pipelineCard\.addEventListener\(\s*['\"]keydown['\"]", js)
    assert m2, "app.js 缺 pipelineCard keydown 监听（键盘跳转入口）"
    keydown_body = _js_block_from(js, js.index("{", m2.end()))

    filter_list = (
        "button, input, label, a, select, textarea, .path-row, "
        ".destination-section, .encode-auto-row, .fullchain-auto-row, "
        ".encode-params-link")
    assert filter_list in click_body, (
        "pipelineCard click 监听体缺统一过滤清单串（勾开关/点参数/开输出区"
        "仍连带跳引擎页）: "
        f"{click_body[:200]}")
    assert filter_list in keydown_body, (
        "pipelineCard keydown 监听体缺统一过滤清单串（键盘激活交互元素"
        "仍误触整卡跳转）")
    assert "instanceof Element" in click_body, \
        "click 监听体缺 instanceof Element 守卫（非元素 target 会抛错）"
    assert "instanceof Element" in keydown_body, (
        "keydown 监听体缺 instanceof Element 守卫（卡片聚焦时 e.target"
        " 可能是卡片本身）")
    assert "switchTab('tab-engine')" in click_body, \
        "click 监听体 switchTab('tab-engine') 被删（只读区点击跳转语义丢失）"
    assert "switchTab('tab-engine')" in keydown_body, \
        "keydown 监听体 switchTab('tab-engine') 被删（Enter 跳转语义丢失）"

    # 卡I 双保险：destination-section click+keydown stopPropagation 阻断块仍在
    dm = re.search(r"querySelector\(\s*['\"]\.destination-section['\"]", js)
    assert dm, "app.js 缺 .destination-section 阻断块（卡I 既有阻断被删）"
    dseg = _js_block_from(js, js.index("{", dm.end()))
    assert "stopPropagation" in dseg, \
        ".destination-section 阻断块缺 stopPropagation（卡I 钉 :5176 回潮）"
    for ev in ("click", "keydown"):
        assert re.search(r"addEventListener\(\s*['\"]" + ev + r"['\"]", dseg), \
            f".destination-section 阻断块未对 {ev} 事件阻断冒泡（卡K 不得删卡I 钉）"


# ============================================================================
# 卡M（D2026-1013-01 追记）：流水线卡文案回填——MSG 改值+三新键+主副行填充
# ============================================================================


def test_pipeline_card_copy_keys():
    """d1013-卡M 新钉：流水线卡文案回填（MSG 改值不改键 + 新增 3 键 +
    主副行回填调用在位）。

    ①MSG 新增 3 键（encodeAutoShort/fullchainAutoShort/
      pipelineGroupAuto，additive 合法，卡D 先例）在键表且值含中文
      （test_strings_and_shortcut.py 有 MSG 全值中文钉，此处非空+
      含中文自证）；
    ②encodeParamsLink 改值不改键：值='压制参数'（B-06 先例，回填链
      既有 init 填充自动生效）；
    ③EncodeDock.init 回填调用在位——小节标题 .pipeline-subhead-text
      填 MSG.pipelineGroupAuto；两开关主行 label 短句
      （encodeAutoShort/fullchainAutoShort），desc 副行承接既有长句
      （encodeAutoSwitch/fullchainAutoSwitch），全部 null 守卫
      （照既有画法）。

    先红后绿自证：先落本钉不动 app.js 时红（三新键未定义+回填调用
    缺位）；完成卡M 改法 1-3 后转绿。"""
    src = _app_js_source()
    keys = _js_msg_keys()
    for key in ("encodeAutoShort", "fullchainAutoShort",
                "pipelineGroupAuto"):
        assert key in keys, f"MSG 缺少 d1013-卡M 新键: {key}"
        m = re.search(rf"^\s*{key}:\s*'([^']*)'", src, re.M)
        assert m and m.group(1), f"MSG 键 {key} 文案为空"
        assert any("一" <= ch <= "鿿" for ch in m.group(1)), (
            f"MSG[{key!r}] 应为中文文案: {m.group(1)!r}")
    # 改值不改键：encodeParamsLink 值='压制参数'
    m = re.search(r"^\s*encodeParamsLink:\s*'([^']*)'", src, re.M)
    assert m, "MSG 缺 encodeParamsLink 键"
    assert m.group(1) == "压制参数", (
        f"encodeParamsLink 值应为「压制参数」（改值不改键），"
        f"实为「{m.group(1)}」")
    # 回填调用在位（EncodeDock.init 内，全部 null 守卫）
    init = _extract_function(_encode_dock_source(src), "init")
    assert "querySelector('.pipeline-subhead-text')" in init, (
        "init 缺小节标题 .pipeline-subhead-text 定位")
    assert "MSG.pipelineGroupAuto" in init, (
        "init 缺小节标题文案 MSG.pipelineGroupAuto")
    for frag in (
        "querySelector('.encode-auto-label')",
        "label.textContent = MSG.encodeAutoShort",
        "querySelector('.encode-auto-desc')",
        "MSG.encodeAutoSwitch",
        "querySelector('.fullchain-auto-label')",
        "fcLabel.textContent = MSG.fullchainAutoShort",
        "querySelector('.fullchain-auto-desc')",
        "MSG.fullchainAutoSwitch",
    ):
        assert frag in init, f"EncodeDock.init 缺回填接线: {frag}"
    assert "if (autoDesc)" in init and "if (fcDesc)" in init, (
        "desc 副行填充须 null 守卫（照既有画法）")


def test_pipeline_card_layout_structure():
    """d1013-卡L 移交钉固化（D2026-1013-01 追记 / 卡M 卡面改法 4）：
    流水线卡 A 案布局结构五断言（红相已由卡L 执行记录留证——卡面
    「先红后绿回归测试」段因卡面矛盾落仓外临时文件跑红绿，本钉
    固化入库时结构已在位，直接绿态）。

    ①pipeline-subhead-text 在 index.html 恰 1 处且空壳
      （>.*</span> 内无中文——文案卡M JS 态填充）；
    ②encode-auto-desc/fullchain-auto-desc 文字栈在位
      （label span 保留=JS 填充锚点，desc 空壳）；
    ③参数钮在卡头标题行 .pipeline-head-row 内与 block-title 同行
      （d1013-卡O 钉修订：自组尾行上移卡头，删相对 encode-auto-row
      顺序断言；class 四类名序列逐字冻结：btn btn-ghost btn-compact
      encode-params-link，零 id/零 data-i18n）；
    ④sr-only 类两处（browse/open）且 svg 在 span 前
      （图标化 C7 (ii) 方案：data-i18n 键随文本迁 span，applyI18n
      只覆写 span.textContent 不抹 svg）；
    ⑤style.css 含 .pipeline-subhead-text::after 尾 hairline /
      #pipelineCard .section-content 缩进归零 / 输出区 h2 统一三件。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    # ①小节标题空壳：恰 1 处且无中文
    n_subhead = html.count('class="pipeline-subhead-text"')
    assert n_subhead == 1, (
        f"pipeline-subhead-text 应恰 1 处（实测 {n_subhead} 处）")
    m = re.search(
        r'<span class="pipeline-subhead-text"[^>]*>(.*?)</span>',
        html, re.S)
    assert m, "未找到 pipeline-subhead-text span"
    assert not re.search("[\u4e00-\u9fff]", m.group(1)), (
        "小节标题空壳内不得有中文（文案卡M JS 态填充）")

    # ②开关行文字栈在位（label 锚点 + desc 空壳同胞）
    assert re.search(
        r'<span class="encode-auto-text">'
        r'<span class="encode-auto-label"></span>'
        r'<span class="encode-auto-desc"></span></span>', html), (
        "encode-auto 文字栈结构漂移（label/desc 栈须在位）")
    assert re.search(
        r'<span class="fullchain-auto-text">'
        r'<span class="fullchain-auto-label"></span>'
        r'<span class="fullchain-auto-desc"></span></span>', html), (
        "fullchain-auto 文字栈结构漂移（label/desc 栈须在位）")

    # ③参数钮在卡头标题行内与 block-title 同行（d1013-卡O 钉修订：
    #   自组尾行 .pipeline-subgroup-tail 上移卡头，删相对 encode-auto-row
    #   顺序断言；class 四类名序列逐字冻结与零 id/零 data-i18n 断言不动）
    m = re.search(
        r'<div class="pipeline-head-row">\s*'
        r'<div class="block-title" data-i18n="refine_panel_title">'
        r'.*?</div>\s*'
        r'<button[^>]*class="btn btn-ghost btn-compact '
        r'encode-params-link"[^>]*></button>\s*</div>',
        html, re.S)
    assert m, (
        "缺卡头标题行 .pipeline-head-row"
        "（参数钮须与 block-title 同行，class 四类名序列逐字冻结）")
    tag = re.search(
        r'<button[^>]*class="btn btn-ghost btn-compact '
        r'encode-params-link"[^>]*>', m.group(0))
    assert tag, "卡头行内参数钮标签解析失败"
    assert not re.search(r'(?<![\w-])id="', tag.group(0)) \
        and "data-i18n" not in tag.group(0), (
        "参数钮不得带 id/data-i18n（FROZEN 契约）")

    # ④浏览/打开图标化：sr-only 恰两处且 svg 在 span 前
    n_sr = html.count('class="sr-only"')
    assert n_sr == 2, (
        f"sr-only 类应恰两处（浏览/打开，实测 {n_sr} 处）")
    for btn_id, i18n_key in (("browseOutputBtn", "browse_btn"),
                             ("openOutputBtn", "open_btn")):
        bm = re.search(rf'<button[^>]*id="{btn_id}"[^>]*>(.*?)</button>',
                       html, re.S)
        assert bm, f"缺 {btn_id} 按钮"
        inner = bm.group(1)
        assert "<svg" in inner, f"{btn_id} 缺 Lucide svg 图标"
        assert f'class="sr-only" data-i18n="{i18n_key}"' in inner, (
            f"{btn_id} 缺 sr-only 读屏文本（data-i18n={i18n_key}）")
        assert inner.index("<svg") < inner.index("class=\"sr-only\""), (
            f"{btn_id} svg 须在 sr-only span 前")

    # ⑤style.css 三件：subhead 尾 hairline/缩进归零/h2 统一
    assert ".pipeline-subhead-text::after" in css, (
        "style.css 缺 .pipeline-subhead-text::after 尾 hairline")
    assert "#pipelineCard .section-content" in css \
        and "padding: var(--space-3) 0 var(--space-2);" in css, (
        "style.css 缺 #pipelineCard .section-content 缩进归零")
    assert ("#pipelineCard .destination-section .section-header "
            "h2::after") in css, (
        "style.css 缺输出区 h2 统一（h2::after 尾 hairline）")


# ============================================================================
# 卡Q（D2026-1013-01 追记 / 真机反馈）：API Key 行收窄左移 + 已保存态星号
#   根因：alt-row 内 label(≈50)+gap 8×2+input(min-width 200)+保存钮(30)≈296
#   > 流水线卡内容宽 244 → 保存钮被顶出卡缘。收窄后 50+8+140+8+30=236 ≤ 244。
#   ①两 placeholder 改值不改键（FROZEN_IDS/data-i18n 键集零增减）
#   ②--w-key-input 200px→140px
#   ③#refineS1Key/#refineS3Key max-width 280px→200px（承接旧钉 280px，
#     旧钉值随卡Q 收窄下调，见 test_realdevice_feedback_pins ②）
#   ④数据流红线：已保存态只改 placeholder，不回填掩码 value
# ============================================================================


def test_api_key_row_compact():
    """卡Q API Key 行收窄 + 已保存态星号 placeholder 防回潮。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    js = _app_js_source()

    # ① 两 placeholder 改值（键集零增减，仅改值）
    #   断言按 MSG 条目行取值逐字比对，不做全文件否定匹配——「留空即用」等
    #   文案在无关键（如 tm_threshold_title）合法存在，全局否会误伤。
    for key, want in (("key_placeholder", "留空用已保存密钥"),
                      ("key_saved_placeholder", "已保存 ※※※※※※")):
        mk = re.search(rf"^\s*{key}:\s*'(?P<v>[^']*)',", js, re.M)
        assert mk, f"app.js MSG 表缺 {key}（改值不改键，键不得消失）"
        assert mk.group("v") == want, (
            f"MSG.{key} 应逐字为「{want}」，实为 {mk.group('v')!r}")
    assert "LM Studio 免填" not in js, (
        "key_placeholder 仍含「LM Studio 免填」（占位过长顶出保存钮）")

    # ② 行宽 token 收窄（API Key 框下限 200px→140px）
    assert re.search(r"--w-key-input:\s*140px", css), (
        "--w-key-input 应为 140px（卡Q 收窄：框+保存钮回到卡内容宽内）")
    assert not re.search(r"--w-key-input:\s*200px", css), (
        "--w-key-input 仍为 200px（保存钮回潮被顶出卡缘）")

    # ③ key input grow 封顶 280px→200px（承接真机反馈旧钉）
    assert re.search(
        r"#refineS1Key,\s*#refineS3Key\s*\{[^}]*max-width:\s*200px", css), (
        "#refineS1Key/#refineS3Key 缺 max-width:200px 封顶（卡Q 收窄）")
    assert not re.search(
        r"#refineS1Key,\s*#refineS3Key\s*\{[^}]*max-width:\s*280px", css), (
        "#refineS1Key/#refineS3Key 仍为 max-width:280px（旧钉值，保存钮再回潮）")

    # ④ 数据流红线：已保存态只写 placeholder，严禁回填掩码假 value
    #   （掩码若被当新 KEY 提交，将污染 DPAPI 存储）
    assert not re.search(r"\.value\s*=\s*['\"][^'\"]*[※*•·]{2,}", js), (
        "app.js 存在掩码字符串回填 .value（会污染 DPAPI 存储）")
    save_fn = _extract_function(js, "saveStageKey")
    assert re.search(r"inp\.value\s*=\s*''", save_fn), (
        "saveStageKey 须保留 inp.value='' 清空（保存后不回填掩码）")
    assert re.search(
        r"inp\.placeholder\s*=\s*key\s*\?\s*MSG\.key_saved_placeholder",
        save_fn), (
        "saveStageKey 保存后须以 MSG.key_saved_placeholder 呈现已保存态")


# ============================================================================
# d1013-卡R1 跨片窗口下拉定宽（AI 分析三列按内容分配，零 DOM 纯 CSS）
#   根因：`.ai-config-row .field-col { flex: 1 1 190px }` 三列等分整行，最宽屏
#   单列 ≈520px，而跨片窗口最长选项「全部（永久）」实需 ≈116px（4.5 倍）。
#   改法：--w-agg-window 宽度 token 定 128px（≈116px 内容 + 框内边距余量），
#   三列经 :nth-child 收敛为「提供方按内容 / 模型吃余量（model-trio 三件套）/
#   跨片窗口定宽」。index.html / app.js 零改动、零 FROZEN_IDS 与 MSG 增减。
#   **严禁给 .field-col 加类**：改宽一律走 :nth-child 定位（④防加类法回潮；
#   index.html 侧由 :1009/:3188 `class="field-col"` 恰 3 处的子串计数钉守住）。
#   Ref: D2026-1013-01 第五轮反馈②「跨片窗口框可以缩短」
# ============================================================================


def test_agg_window_fixed_width():
    """卡R1：跨片窗口框定宽 --w-agg-window:128px + 三列按内容分配。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    # ① :root 宽度 token 区新增 --w-agg-window: 128px（值逐字冻结）
    root = re.search(r":root\s*\{([^}]*)\}", css)
    assert root, "style.css 缺 :root token 定义块"
    assert re.search(r"--w-agg-window:\s*128px", root.group(1)), (
        ":root 宽度 token 区缺 --w-agg-window: 128px"
        "（≈116px 最长选项「全部（永久）」+ 框内边距余量）")

    # ② 三列按内容分配（:nth-child 定位，零 DOM、零加类）
    expected = {
        1: ("flex: 0 1 auto;", "min-width: 150px;"),   # 分析提供方按内容
        2: ("flex: 1 1 220px;", "min-width: 150px;"),   # 分析模型吃余量
        3: ("flex: 0 0 var(--w-agg-window);",),         # 跨片窗口定宽
    }
    for nth, decls in expected.items():
        m = re.search(
            rf"\.ai-config-row > \.field-col:nth-child\({nth}\)\s*\{{([^}}]*)\}}",
            css)
        assert m, f"缺 .ai-config-row > .field-col:nth-child({nth}) 收敛规则（卡R1）"
        for decl in decls:
            assert decl in m.group(1), (
                f":nth-child({nth}) 规则体缺「{decl}」——三列须按内容分配，"
                "不得退回等分整行（卡R1 跨片窗口框过长根因）")

    # ③ 第 3 列宽度只走 token，不得再落 px 字面（防 token 与规则两处各写一个数）
    m3 = re.search(
        r"\.ai-config-row > \.field-col:nth-child\(3\)\s*\{([^}]*)\}", css)
    assert not re.search(r"\d+px", m3.group(1)), (
        f":nth-child(3) 出现 px 字面宽度：{m3.group(1).strip()}——"
        "宽度一律引用 var(--w-agg-window)")

    # ④ 防加类法回潮：凡提及 .field-col 的选择器，元素侧不得挂第二个类
    #    （加类会改 class="field-col" 子串、破 :1009/:3188 计数钉，零 DOM 原则失守）
    bare = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    offenders = [
        sel.strip() for sel in re.findall(r"([^{}]+)\{", bare)
        if ".field-col" in sel
        and re.search(r"\.field-col\s*\.\s*[\w-]+|\.field-col-[\w-]+", sel)
    ]
    assert not offenders, (
        ".field-col 选择器出现新增类名（禁用加类法改宽，改用 :nth-child）："
        f"{offenders}")


# ============================================================================
# d1013-卡R4 兜底与并发卡三组分组（件1 收官）
#   根因：.field-row 内 5 个 label 同权平铺（gap 均匀 16px），控件语义（接管/
#   开关/批量/并发）无分组，窄窗折行时末位「并行」被挤到第二行且贴左 → 拥挤 +
#   错落 + 孤行。改法：3 个 div.ctrl-group 把 label 包成不可拆散的原子（并行
#   并入组3，与批量同属并发参数 → 折行时组内同行，验收项「不孤行」），零 id /
#   零 data-i18n 增减、组内元素原样；style.css 追加 .ctrl-group（组内 8px）
#   + 组间距规则。app.js 零改动——六控件读写链全走 id（$('id') /
#   getElementById），与包装层深度无关，读取链断言即零改动的静态佐证。
#   本节两钉：test_fallback_card_layout（卡R3 移交固化，结构已在位直接绿，
#   红相已由卡R3 执行记录留证）+ test_concurrency_card_groups（本卡新钉，
#   对现状「无 ctrl-group」先红后绿）。
#   Ref: D2026-1013-01 第五轮反馈「并发卡一行塞 5 控件拥挤错落、『并行』孤行」
# ============================================================================

# 兜底与并发卡六控件既有 id（零增减：各恰 1 次）
_CONCURRENCY_CARD_IDS = (
    "refineFallbackModel", "refreshFallbackModels", "refineFallbackLocal",
    "refineBatchLocal", "refineBatchCloud", "refineConcurrency",
)

# 钉① 切片锚注释逐字冻结（改注释会让 test_ui_phase3_redlines 的三卡切片失义）
_SLICE_ANCHORS = (
    "<!-- 阶段A 完整行 -->",
    "<!-- 阶段B 完整行 -->",
    "<!-- 兜底档位 / 上下文窗口 / 净语配置目录 -->",
    "<!-- 兜底与并发（原高级设置第四组迁入） -->",
)

_VOID_TAGS = frozenset({
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
})


def _html_slice_between(html: str, start: str, end: str) -> str:
    """按两枚锚（注释/标记）切出 HTML 片段（与 test_ui_phase3_redlines 同口径，
    本文件独立实现避免跨文件导入）。"""
    i = html.index(start)
    j = html.index(end, i)
    return html[i:j]


def _direct_children(fragment: str) -> list[tuple[str, str]]:
    """按标签配平提取片段的直接子元素 (tag, 元素全文) 列表。

    深度只在非 void 且非自闭合标签上增减：注释（`<!--` 不以字母开头，
    正则不匹配）、void 元素（input/br…）与 SVG 自闭合（`<path …/>`）均不配平；
    片段外游离的闭合标签忽略。"""
    out: list[tuple[str, str]] = []
    depth = 0
    open_at = -1
    for m in re.finditer(
            r"<(/?)([a-zA-Z][\w-]*)((?:\"[^\"]*\"|'[^']*'|[^>])*)>", fragment):
        closing, tag, attrs = m.group(1), m.group(2).lower(), m.group(3)
        if closing:
            if depth <= 0:
                continue
            depth -= 1
            if depth == 0:
                out.append((tag, fragment[open_at:m.end()]))
        elif tag in _VOID_TAGS or attrs.rstrip().endswith("/"):
            continue
        else:
            if depth == 0:
                open_at = m.start()
            depth += 1
    return out


def _inner_of(element_text: str) -> str:
    """取元素全文的内层内容（剥外层开标签与末尾闭合标签）。"""
    return element_text[element_text.index(">") + 1:element_text.rfind("</")]


def test_fallback_card_layout():
    """卡R3 移交固化钉 + d1014-卡S2 行内化钉：兜底与容错卡布局在位，且三直接子元素结构未变。

    演进依据：owner 第六轮反馈推翻卡R3 乙案列排方向（D2026-1013-01 追记：
    2026-10-14 第六轮真机反馈②④合并）——标签与控件同行左置、折行整组归位、
    目录吃剩余宽、右侧留白消掉。
    卡R3 卡面「tests：新增钉」与同卡「约束：tests 零改动」相斥（卡R3 遗留①），
    由本卡顺带补落；结构改动已在卡R3 落码，故本钉落即绿，红相见卡R3 执行记录。
    d1014-卡S2 钉修订（m3 改写 + 新增⑤⑥⑦）先红后绿，红绿输出见卡S2 执行记录。
    断言面：
    ① 外壳 class="form-card fallback-card" 在位；
    ② 三直接子元素结构零改动——:has() 列排按直系子级命中，多一层包装即失配，
       故按序钉死为 档位 label / 上下文 label / 目录 label.path-row.grow；
    ③ style.css 规则在位——m1（卡本体 align-items: flex-start +
       gap: var(--space-3)）/m2（前两列内容宽 width: auto !important）/
       m3（目录列 flex: 1 1 auto + min-height: var(--h-ctl-sm)，加否定断言
       防回 flex: 0 1 320px）；
    ④ 钉① 三切片锚注释逐字不动；
    ⑤ 行内化 override 在位（三直系 label 同行左置，压过通用列排规则）；
    ⑥ 目录输入吃宽规则在位（width: auto !important + min-width: var(--w-cleaner)）；
    ⑦ 卡S1 过渡规则 #refineCleanerConfigShow 全文无残留（id(1,0,0) 压 class
       防复发），且 --w-model: 200px 仍在位（防借卡顺手改 token）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    # ① 外壳加类在位（乙案入口）
    assert '<div class="form-card fallback-card">' in html, \
        "兜底与容错卡外壳缺 fallback-card 类（卡R3 乙案未落码？）"

    # ② 三直接子元素结构零改动（:has() 列排依赖直系子级）
    block = _html_slice_between(html, "<!-- 兜底档位", "<!-- 兜底与并发")
    top = _direct_children(block)
    assert len(top) == 1 and top[0][0] == "div", \
        f"兜底容错卡切片应只含一个卡片容器，实得 {len(top)} 个：{[t[0] for t in top]}"
    kids = _direct_children(_inner_of(top[0][1]))
    assert [k[0] for k in kids] == ["label", "label", "label"], \
        f"兜底容错卡直接子元素须恰为三个 label（:has() 列排依赖），实得 {[k[0] for k in kids]}"
    assert 'class="inline-field field-label"' in kids[0][1] \
        and 'id="refineProfile"' in kids[0][1], "第一列须为兜底档位 label（refineProfile）"
    assert 'class="inline-field field-label"' in kids[1][1] \
        and 'id="refineV2Ctx"' in kids[1][1], "第二列须为上下文窗口 label（refineV2Ctx）"
    assert 'class="path-row grow"' in kids[2][1], \
        f"第三列须为目录 label.path-row.grow（乙案不拆其直系子级），实得 {kids[2][1][:60]}"
    for dom_id in ("refineCleanerConfig", "refineCleanerConfigShow",
                   "refinePickCleanerDir", "refineOpenCleanerDir"):
        assert f'id="{dom_id}"' in kids[2][1], f"目录列缺 {dom_id}（三直接子元素结构漂移）"

    # ③ 乙案三规则在位（作用域 .form-card.fallback-card 锁死）
    m1 = re.search(r"\.form-card\.fallback-card\s*\{([^}]*)\}", css)
    assert m1, "style.css 缺 .form-card.fallback-card 规则（卡R3 乙案未落码？）"
    for decl in ("align-items: flex-start;", "gap: var(--space-3);"):
        assert decl in m1.group(1), f".form-card.fallback-card 规则体缺「{decl}」（卡R3 乙案）"
    m2 = re.search(
        r"\.form-card\.fallback-card\s*>\s*label\.inline-field\s*>\s*"
        r"\.form-select\s*\{([^}]*)\}", css)
    assert m2 and "width: auto !important;" in m2.group(1), \
        "style.css 缺乙案第二规则（前两列内容宽 width: auto !important）"
    m3 = re.search(
        r"\.form-card\.fallback-card\s*>\s*label\.path-row\s*\{([^}]*)\}", css)
    assert m3, "style.css 缺目录列规则（卡S2 行内化）"
    for decl in ("flex: 1 1 auto;", "min-height: var(--h-ctl-sm);"):
        assert decl in m3.group(1), f"目录列规则体缺「{decl}」（卡S2 行内化）"
    assert "flex: 0 1 320px" not in m3.group(1), \
        "目录列规则回潮：不得回 flex: 0 1 320px（乙案限宽已由卡S2 推翻）"

    # ⑤ 行内化 override 在位（(0,3,1) 特异性 + !important 压过通用列排，源序在后）
    m5 = re.search(
        r"\.form-card\.fallback-card:not\(\.stack\)\s*>\s*label\s*\{([^}]*)\}", css)
    assert m5, "style.css 缺行内化 override（.form-card.fallback-card:not(.stack) > label）"
    assert "flex-direction: row !important;" in m5.group(1), \
        "行内化 override 规则体缺「flex-direction: row !important;」（卡S2）"

    # ⑥ 目录输入吃宽规则在位（(0,4,1) 覆盖通用 width:100%）
    m6 = re.search(
        r"\.form-card\.fallback-card\s*>\s*label\.path-row\s*>\s*"
        r"\.form-input\s*\{([^}]*)\}", css)
    assert m6, "style.css 缺目录输入吃宽规则（path-row > .form-input，卡S2）"
    for decl in ("width: auto !important;", "min-width: var(--w-cleaner);"):
        assert decl in m6.group(1), f"目录输入规则体缺「{decl}」（卡S2）"

    # ⑦ 卡S1 过渡规则已摘（id(1,0,0) 压 class，必须摘源规则）+ token 防顺手改
    assert "#refineCleanerConfigShow" not in css, \
        "style.css 残留 #refineCleanerConfigShow 规则（卡S1 过渡规则须摘除）"
    assert "--w-model: 200px" in css, "--w-model: 200px 被改动（须保持不动）"

    # ④ 钉① 三切片锚注释逐字不动（卡R3 与本卡共同硬约束）
    for anchor in _SLICE_ANCHORS:
        assert anchor in html, f"切片锚注释被改动：{anchor}"


def test_concurrency_card_groups():
    """卡R4 新钉：兜底与并发卡三组分组在位，并行不孤行，六控件读取链不变。

    先红后绿：落钉时现状无任何 .ctrl-group（断言①③必红），改码后转绿。
    断言面：
    ① .stack.form-card 直接子元素仍为 group-title + field-row，field-row 的
       直接子元素恰 3 个 div.ctrl-group，组内元素原样（label 原位、零新 id）；
    ② 组语义：组1=接管模型下拉+刷新钮 / 组2=云端故障开关 / 组3=批量·本地 +
       批量·云端 + 并行（并行与批量同组 → 折行时不同行孤零零贴左）；
    ③ 六控件 id 各恰 1 次（零增减），且全部落在本卡内；
    ④ app.js 零改动的静态佐证：refineConcurrency 读取链（readRefineConcurrency
       / refreshPipelineMirror / change 绑定）全走 id，与包装层深度无关；
    ⑤ style.css 分组两规则在位（组内 8px、组间 12px，均走 token）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    js = _app_js_source()
    card = _html_slice_between(html, "<!-- 兜底与并发", "<!-- ASR 与词典页")

    # ① 卡片壳与两直接子元素结构
    top = _direct_children(card)
    assert top and top[0][0] == "div" and 'class="stack form-card"' in top[0][1], \
        "兜底与并发卡外壳 class=\"stack form-card\" 不在位（分组须建在本卡内）"
    kids = _direct_children(_inner_of(top[0][1]))
    assert [k[0] for k in kids] == ["div", "div"], \
        f"本卡直接子元素须仍为 group-title + field-row 两块，实得 {[k[0] for k in kids]}"
    assert 'class="group-title"' in kids[0][1], "第一块须仍为 .group-title"
    assert 'class="field-row"' in kids[1][1], "第二块须仍为 .field-row"

    # ①/② 三组包装与组内语义
    groups = _direct_children(_inner_of(kids[1][1]))
    assert len(groups) == 3 and all(
        g[0] == "div" and 'class="ctrl-group"' in g[1] for g in groups), (
        f"兜底与并发卡 .field-row 直接子元素须恰为 3 个 div.ctrl-group，"
        f"实得 {[(g[0], g[1][:40]) for g in groups]}")
    labels = [[c[0] for c in _direct_children(_inner_of(g[1]))] for g in groups]
    assert labels == [["label"], ["label"], ["label", "label", "label"]], \
        f"三组内 label 分布须为 1 / 1 / 3（组3 批量两框 + 并行），实得 {labels}"

    group_ids = [[i for i in _CONCURRENCY_CARD_IDS if f'id="{i}"' in g[1]]
                 for g in groups]
    assert group_ids == [["refineFallbackModel", "refreshFallbackModels"],
                         ["refineFallbackLocal"],
                         ["refineBatchLocal", "refineBatchCloud", "refineConcurrency"]], \
        f"三组控件归属漂移：{group_ids}（组1 接管 / 组2 开关 / 组3 批量+并行）"
    # 组包装层本身零 id（分组只增类包装，不动 R1 id 契约）
    for g in groups:
        assert "id=" not in g[1][:g[1].index(">") + 1], \
            ".ctrl-group 包装层不得新增 id（分组零 FROZEN_IDS 增减）"

    # ③ 六控件 id 各恰 1 次且全在本卡内
    for dom_id in _CONCURRENCY_CARD_IDS:
        assert html.count(f'id="{dom_id}"') == 1, \
            f"id={dom_id} 次数漂移（须恰 1 次，零增减）"
        assert f'id="{dom_id}"' in card, f"id={dom_id} 逸出兜底与并发卡"

    # ④ app.js 零改动的静态佐证：读取链全走 id
    assert "$('refineConcurrency')" in _extract_function(js, "readRefineConcurrency"), \
        "readRefineConcurrency 读取链漂移（须仍经 $('refineConcurrency') 取值）"
    assert "document.getElementById('refineConcurrency')" \
        in _extract_function(js, "refreshPipelineMirror"), \
        "refreshPipelineMirror 读取链漂移（须仍经 getElementById 取值）"
    assert "['refineS1Model', 'refineConcurrency'].forEach" in js, \
        "并发/模型 change 联动绑定漂移（镜像读链依赖）"

    # ⑤ 分组两规则在位：组内 8px 咬合 + 组间 12px 分组（作用域锁本卡）
    m1 = re.search(r"\.ctrl-group\s*\{([^}]*)\}", css)
    assert m1, "style.css 缺 .ctrl-group 规则（组内咬合在位？）"
    for decl in ("display: flex;", "align-items: center;", "gap: var(--space-2);"):
        assert decl in m1.group(1), f".ctrl-group 规则体缺「{decl}」（卡R4 分组）"
    m2 = re.search(r"\.stack\.form-card\s*>\s*\.field-row\s*\{([^}]*)\}", css)
    assert m2, "style.css 缺 .stack.form-card > .field-row 组间距规则（卡R4 分组）"
    assert "gap: var(--space-3);" in m2.group(1), \
        "组间距须为 var(--space-3)（组间 12px / 组内 8px 两级分级，均走 token）"


# ---------------------------------------------------------------------------
# d1014-卡S1：阶段卡折行治理——stage 单元化（API Key 组恒与模型栏同行）
# D2026-1013-01 追记（2026-1014 第六轮真机反馈①）
# ---------------------------------------------------------------------------

def test_stage_card_unit_layout():
    """阶段卡折行治理钉：alt-row 删除 + stage-unit/stage-key 单元化。

    断言面：
    - 阶段A/阶段B 双卡成对：<div class="stage-unit"> 与 <div class="stage-key">
      各恰 2 处；stage-key 内序=API Key label→key input→保存钮；
      stage-unit 内序含 model select→刷新→测试→stage-key；
      status span 在 stage-unit 之外（stage-unit 块内不含
      refineTestS1Status/refineTestS3Status）；
    - index.html 全文零 alt-row 字样；style.css 零 .alt-row 规则
      （--w-alt-row token 保留不算）；
    - 三 token 逐值在位：--w-stage-model: 140px / --w-stage-unit: 520px /
      --w-stage-key: 240px；
    - 模型下限规则只含两模型 id（#refineS1Model, #refineS3Model），
      #refineCleanerConfigShow 不在该规则内；
    - --w-model: 200px 仍在位（防顺手改 token）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    # ① stage-unit / stage-key 各恰 2 处
    assert html.count('<div class="stage-unit">') == 2, \
        "stage-unit 必须恰 2 处（阶段A/阶段B 各一）"
    assert html.count('<div class="stage-key">') == 2, \
        "stage-key 必须恰 2 处（阶段A/阶段B 各一）"

    # ② stage-key 内序：API Key label → key input → 保存钮
    for n, key_id, save_btn_id in (
        (1, "refineS1Key", "refineSaveS1KeyBtn"),
        (3, "refineS3Key", "refineSaveS3KeyBtn"),
    ):
        unit_m = re.search(
            rf'<div class="stage-unit">(?:(?!</div>).)*?'
            rf'<select id="refineS{n}Model"', html, re.S)
        assert unit_m, f"stage-unit 内未找到 refineS{n}Model（n={n}）"
        key_m = re.search(
            rf'<div class="stage-key">(?:(?!</div>).)*?'
            rf'id="{key_id}"(?:(?!</div>).)*?'
            rf'id="{save_btn_id}"', html, re.S)
        assert key_m, \
            f"stage-key 内序漂移：{key_id} → {save_btn_id}（n={n}）"

    # ③ stage-unit 内序含 model select → 刷新 → 测试 → stage-key
    for n, model_id, refresh_id, test_id in (
        (1, "refineS1Model", "refineRefreshS1", "refineTestS1"),
        (3, "refineS3Model", "refineRefreshS3", "refineTestS3"),
    ):
        m = re.search(
            rf'<select id="{model_id}"[\s\S]*?'
            rf'id="{refresh_id}"[\s\S]*?'
            rf'id="{test_id}"[\s\S]*?'
            rf'<div class="stage-key">', html)
        assert m, \
            f"stage-unit 内序漂移：model→refresh→test→stage-key（n={n}）"

    # ④ status span 在 stage-unit 之外
    for n in (1, 3):
        unit_start = html.index(f'<select id="refineS{n}Model"')
        unit_end = html.index('</div>', html.index(
            '<div class="stage-key">', unit_start))
        unit_block = html[unit_start:unit_end]
        status_id = f"refineTestS{n}Status"
        assert status_id not in unit_block, \
            f"{status_id} 不得出现在 stage-unit 块内（须独立成行）"

    # ⑤ index.html 全文零 alt-row 字样
    assert "alt-row" not in html, "index.html 残留 alt-row 字样"

    # ⑥ style.css 零 .alt-row 规则（--w-alt-row token 保留不算）
    assert ".alt-row" not in css, \
        "style.css 残留 .alt-row 规则（token --w-alt-row 保留合法）"

    # ⑦ 三 token 逐值在位
    assert "--w-stage-model: 140px" in css, "缺 --w-stage-model: 140px"
    assert "--w-stage-unit: 520px" in css, "缺 --w-stage-unit: 520px"
    assert "--w-stage-key: 240px" in css, "缺 --w-stage-key: 240px"

    # ⑧ 模型下限规则只含两模型 id
    m = re.search(
        r'#refineS1Model,\s*#refineS3Model\s*\{\s*min-width:\s*var\(--w-stage-model\);\s*\}',
        css)
    assert m, \
        "模型下限规则漂移：须为 #refineS1Model, #refineS3Model { min-width: var(--w-stage-model); }"
    assert "#refineCleanerConfigShow" not in m.group(0), \
        "#refineCleanerConfigShow 不得出现在模型下限规则内"

    # ⑨ --w-model: 200px 仍在位
    assert "--w-model: 200px" in css, "--w-model: 200px 被改动（须保持不动）"


def test_style_css_comment_blocks_balanced():
    """D2026-1015-01 验收修正防复发：style.css 注释开闭配平。

    卡执行曾误删注释闭合 `*/` 致 `.ai-config-row` 整组规则被吞进注释
    （静态文本断言测不出 CSS 语法破损，浏览器端整段失效）；此钉锁
    `/*` 与 `*/` 出现次数相等（配平即无未闭合注释跑吃规则的形态）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    assert css.count("/*") == css.count("*/"), \
        "style.css 注释开闭不配平（存在未闭合注释，将吞吃后续规则）"


# ============================================================================
# d1015-卡1（回链 D2026-1015-04；规格 docs/design/d1015-P0必修批-设计规格.md §1 v2）
# P0-1 三栏表面分层 A1-②（左/右栏降 --bg、中栏转白 --surface、子卡 --surface-2、
# 分隔线升级 --border-strong）+ G1 案乙（左栏导航/主题钮基态 text-1）静态钉。
# ============================================================================
def _p01_rule_blocks(css: str, selector: str) -> list:
    """取 style.css 中该选择器的规则块体（花括号内声明文本，可多块）。

    选择器按字面转义、后接 `{`（故 `.section` 不会命中 `.section-header`，
    `:hover` / ` .child` 等后缀选择器亦不命中），与既有源码文本钉法同源。
    """
    return re.findall(re.escape(selector) + r"\s*\{([^}]*)\}", css)


def test_p01_surface_layering_pinned():
    """D2026-1015-04 / 卡1：P0-1 三栏表面分层 + 分隔线升级 + G1 案乙 静态钉。

    断言面 = style.css 点名选择器规则块的声明文本（防回潮；dark 主题经
    token 自动继承，不在本钉面）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    def has(selector: str, decl: str) -> bool:
        return any(decl in blk for blk in _p01_rule_blocks(css, selector))

    # A. 表面重分配
    assert has(".rail", "background: var(--bg)"), \
        ".rail background 须降为 var(--bg)（左栏降为应用底灰，A1-②）"
    assert has(".main", "background: var(--surface)"), \
        ".main 须新增 background: var(--surface)（中栏转白=全屏唯一亮区）"
    for sel in (".card", ".section", ".form-card", ".mp-tier",
                ".adv-group", ".media-source-bar"):
        assert has(sel, "background: var(--surface-2)"), \
            f"{sel} background 须为 var(--surface-2)（中栏子卡）"

    # A. 分隔线升级
    assert has(".rail", "var(--border-strong)"), \
        ".rail 分隔线须升级 var(--border-strong)"
    assert has(".aside", "var(--border-strong)"), \
        ".aside 分隔线须升级 var(--border-strong)"

    # D. G1 案乙：左栏导航/主题钮基态转 text-1（改后 #F3F4F6 面上 text-2 仅 4.39:1）
    assert has(".side-tab-btn", "color: var(--text-1)"), \
        ".side-tab-btn 基态 color 须为 var(--text-1)（G1 案乙）"
    assert has(".theme-button", "color: var(--text-1)"), \
        ".theme-button 基态 color 须为 var(--text-1)（G1 案乙）"

    # 防误伤：右栏子卡与透明覆盖规则维持不动
    assert has(".panel-card", "background: var(--surface)"), \
        ".panel-card background 须维持 var(--surface)（右栏子卡保持白）"
    assert has(".aside", "background: var(--bg)"), \
        ".aside background 须维持 var(--bg)"
    assert has(".panel-card .section", "background: transparent"), \
        ".panel-card .section 透明覆盖规则不得改动"


# ============================================================================
# d1015-卡2（回链 D2026-1015-04；规格 docs/design/d1015-P0必修批-设计规格.md §2 v2）
# P0-4 键盘焦点环恢复：button:focus 灭环规则加 :not(:focus-visible) 闸门，
# 键盘聚焦时该规则不匹配 → 全局 :focus-visible 胜出（WCAG 2.4.7）。
# ============================================================================
def test_p04_focus_ring_pinned():
    """D2026-1015-04 / 卡2：P0-4 焦点环闸门静态钉（防回潮）。

    断言面 = style.css 源码精确串：
    - 新形态在位（带 :not(:focus-visible) 闸门）；
    - 旧形态（不带闸门的 `button:focus { outline: none; }`）不再存在。
    同时锁住整行未被删除（评议员已否决删除案）与未被改为 box-shadow 方案。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    assert "button:focus:not(:focus-visible) { outline: none; }" in css, \
        "style.css 须含带 :not(:focus-visible) 闸门的灭环规则（P0-4）"
    assert "button:focus { outline: none; }" not in css, \
        "style.css 不得残留旧形态 button:focus { outline: none; }（键盘焦点环被吞）"


# ============================================================================
# d1015-卡3（回链 D2026-1015-04；规格 docs/design/d1015-P0必修批-设计规格.md §3.1-§3.3
# + §3.4 P2-6 v2，G2 已裁案 A）
# P0-5 三组对比度修复（G1 灰字 / G2 琥珀 / G3 主按钮白字）+ P2-6 空态 opacity 全开。
# ============================================================================
def test_p05_contrast_tokens_pinned():
    """D2026-1015-04 / 卡3：P0-5 三组对比度 token + P2-6 空态 opacity 静态钉。

    断言面 = style.css / style.dark.css 的 :root 定义与点名组件规则块：
    - 亮 :root 新 token 终值（text-3/warn/status-warn/on-primary/primary-deep/
      btn-primary-bg 族）在位；
    - 暗 :root 两 token（text-3/on-primary）在位；
    - `.btn-primary` / `.brand-mark` 规则块内不再含 `color: #fff` 字面量
      （一律 var(--on-primary)，P8 钉3 判定集只缩不涨）；
    - `.empty-icon` / `.empty-hint` 规则块不含小数透明度声明（P2-6 全开）；
    - 防误伤：`--primary` 本体维持原品牌蓝（亮 #3B82F6）；`.nav-item-placeholder`
      块仍含 `opacity: .55`（WCAG 1.4.3 例外 D 登记不误伤）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    dark = (ASSETS / "style.dark.css").read_text(encoding="utf-8")

    def blocks(text: str, selector: str) -> list:
        """取指定选择器的规则块体（选择器字面转义后接 `{`，故精确命中基规则）。"""
        return re.findall(re.escape(selector) + r"\s*\{([^}]*)\}", text)

    # A. 亮 :root token 终值
    for pat in (r"--text-3:\s*#656D7A\b", r"--warn:\s*#B45309\b",
                r"--status-warn:\s*var\(--warn\)",
                r"--on-primary:\s*#FFFFFF\b", r"--primary-deep:\s*#1D4ED8\b",
                r"--btn-primary-bg:\s*\S", r"--btn-primary-bg-hover:\s*\S"):
        assert re.search(pat, css), f"style.css :root 缺少 P0-5 token: {pat}"

    # C. 暗 :root token 终值（暗 --warn/--status-warn 达标不动）
    for pat in (r"--text-3:\s*#828A98\b", r"--on-primary:\s*#111827\b"):
        assert re.search(pat, dark), f"style.dark.css :root 缺少 P0-5 token: {pat}"

    # B. 组件规则消字面量：.btn-primary / .brand-mark 块内无 color:#fff
    for sel in (".btn-primary", ".brand-mark"):
        for blk in blocks(css, sel):
            assert "color: #fff" not in blk, \
                f"{sel} 规则块仍含 color: #fff 字面量（应走 var(--on-primary)）"
    assert blocks(css, ".btn-primary"), "未找到 .btn-primary 规则块"

    # D. P2-6 空态 opacity 全开：两规则块无小数透明度声明
    for sel in (".empty-icon", ".empty-hint"):
        assert blocks(css, sel), f"未找到 {sel} 规则块"
        for blk in blocks(css, sel):
            assert not re.search(r"opacity:\s*\.", blk), \
                f"{sel} 规则块仍含小数透明度声明（P2-6 应全开）"

    # 防误伤：--primary 本体仍是原品牌蓝；占位导航项 opacity 豁免不误伤
    m = re.search(r"--primary:\s*([^;]+);", css)
    assert m and m.group(1).strip() == "#3B82F6", \
        "--primary 品牌蓝本体被改动（应维持亮 #3B82F6）"
    nb = blocks(css, ".nav-item-placeholder")
    assert nb, "未找到 .nav-item-placeholder 规则块"
    assert any("opacity: .55" in blk for blk in nb), \
        ".nav-item-placeholder 的 opacity:.55 属例外 D 豁免，不得误伤"


# ============================================================================
# d1015-卡4（回链 D2026-1015-04；规格 docs/design/d1015-P0必修批-设计规格.md
# §3.4 P2-7 v2，路线甲已裁定）
# P2-7 图标 stroke-width 统一为 2（Lucide 上游默认值）+ 双静态钉。
# ============================================================================
def test_p27_stroke_width_uniform_pinned():
    """D2026-1015-04 / 卡4：P2-7 index.html 内联 svg 粗细统一为 2 双断言钉。

    背景（规格 §3.4 v2 实扫口径）：index.html 内联 svg 共 36 处 =
    1.8×12 + 2×24 混用（品牌 logo / 导航 7 项 / 拖拽区与上传复用 /
    浏览 + 打开），选 2 的理由=与 app.js 既有生成物一致、占多数、
    且为 Lucide 上游默认（未来粘贴官方 svg 不再漂移）；反向选 1.8 须改
    app.js 字符串，违反本批「不碰 JS」边界。路线甲=逐 svg 改属性值
    （属性即事实源，diff 可审计，对已为 2 的 24 处零扰动）。

    断言面=仅 index.html（app.js 不入断言面：其生成 svg 5 处 = 4×2 + 1×1，
    :1692 推荐星 `stroke-width="1"` 在 JS 字符串内，D2026-1015-04 登记
    「本批硬边界不碰、登记不动」；review.js 0 处、style.css 仅 select
    箭头 data-uri 内 1 处已是 2，均不在本钉判定面）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")

    # ① 防回潮（窄口径，如实命名）：1.8 混用值命中数必须为 0
    mixed = html.count('stroke-width="1.8"')
    assert mixed == 0, (
        "index.html 仍有 stroke-width=\"1.8\" 混用值"
        f"（P2-7 回潮或新增 1.8 图标，实测 {mixed} 处）")

    # ② 严口径：全部 stroke-width 属性值集合 == {"2"}（正则提取，机器可判）
    values = set(re.findall(r'stroke-width="([^"]*)"', html))
    assert values == {"2"}, \
        f"index.html stroke-width 属性值集合漂移（应恒为 {{'2'}}）：{sorted(values)}"


# ============================================================================
# d1015-卡A（回链 D2026-1015-05；规格 docs/design/d1015-P1残余批-设计规格.md §1
# 〔主审裁定追记 v2 已收口〕+ docs/design/d1015-P2残余批-设计规格.md §4）
# P1-2 五套卡头归一②级规格（14px/700/text-2 + 尾 hairline）+ P2-3 词库折叠
# 簇右对齐（生长规则并入卡A #10）。解析 helper 沿用 _p01_rule_blocks（既有钉
# 同源，勿另造解析器）。
# ============================================================================
def test_p12_card_header_unified_pinned():
    """D2026-1015-05 / 卡A：P1-2 五套卡头归一②级规格静态钉（防回潮）。

    断言面 = style.css 点名选择器规则块体（_p01_rule_blocks 取花括号内声明文本）。
    规格：S6 §2.2 ②级底座 = `var(--font)`/700/`--text-2` + 尾 hairline
    （`::after{content:""; flex:1; height:1px; background:var(--border)}`），
    行布局与 .stage-group-title 现值/pipeline 先例逐字一致。

    ① `.section-header` 与 `.panel-card .section-header` 两规则体不含 border-bottom
      （全宽下划线移除，分隔职责移交 h2 尾 hairline）；
    ② 五规则体各含尾 hairline 片段（::after + flex: 1 + height: 1px +
      var(--border)）与行布局三声明（display:flex/align-items:center/
      gap:var(--space-3)）；
    ③ 五规则族 font-size 只允许 var(--font)、color 只允许 var(--text-2)；
    ④ `.adv-group > .group-title:not(:first-child)` 仍含 border-top（组间结构线
      非卡头画法，防误删）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    # ① 卡头实线移除。注：_p01_rule_blocks 按「选择器子串 + {」命中，
    #    `.section-header` 会连带命中 `#pipelineCard .destination-section
    #    .section-header`（卡A #11/#5482 保留项，其 border-bottom: none 为覆写
    #    非实线）——按实线口径断言并豁免该 none 覆写块（该块在位另正向锁）。
    for sel in (".section-header", ".panel-card .section-header"):
        blks = [b for b in _p01_rule_blocks(css, sel)
                if "border-bottom: none" not in b]
        assert blks, f"未找到 {sel} 规则块"
        for blk in blks:
            assert "border-bottom" not in blk, \
                f"{sel} 规则块仍含 border-bottom（应删实线，移交 h2 尾 hairline）"
    assert any("border-bottom: none" in b
               for b in _p01_rule_blocks(css, ".section-header")), \
        "#pipelineCard .destination-section .section-header 的 border-bottom:none " \
        "覆写块须在位（卡A #11 保留项；tests:5482 既有钉）"

    # ② 五规则体尾 hairline + 行布局三声明
    for sel in (".section-header h2", ".group-title", ".form-card-header",
                ".block-title", ".stage-group-title"):
        afters = _p01_rule_blocks(css, sel + "::after")
        assert afters, f"{sel} 缺 ::after 尾 hairline 规则块"
        assert any("flex: 1" in b and "height: 1px" in b
                   and "var(--border)" in b for b in afters), \
            f"{sel}::after 规则体须含 flex: 1 / height: 1px / var(--border) 片段"
        bases = _p01_rule_blocks(css, sel)
        assert bases, f"未找到 {sel} 规则块"
        assert any("display: flex" in b and "align-items: center" in b
                   and "gap: var(--space-3)" in b for b in bases), \
            f"{sel} 规则体须含行布局 display:flex/align-items:center/" \
            "gap:var(--space-3)"

    # ③ 字级/色阶归一（五规则族内所有声明只允许目标 token，无字面量回流）
    for sel in (".section-header h2", ".group-title", ".form-card-header",
                ".block-title", ".stage-group-title"):
        fam = _p01_rule_blocks(css, sel) + _p01_rule_blocks(css, sel + "::after")
        sizes = {d.strip() for blk in fam
                 for d in re.findall(r"font-size:\s*([^;]+);", blk)}
        colors = {d.strip() for blk in fam
                  for d in re.findall(r"color:\s*([^;]+);", blk)}
        assert sizes and sizes <= {"var(--font)"}, \
            f"{sel} 规则族 font-size 只允许 var(--font)，实测 {sorted(sizes)}"
        assert colors and colors <= {"var(--text-2)"}, \
            f"{sel} 规则族 color 只允许 var(--text-2)，实测 {sorted(colors)}"

    # ④ advanced 组间结构线保留（防误删同族 border-top）
    notfirst = _p01_rule_blocks(
        css, ".adv-group > .group-title:not(:first-child)")
    assert notfirst and any("border-top" in b for b in notfirst), \
        ".adv-group > .group-title:not(:first-child) 须仍含 border-top（组间结构线）"


def test_p23_collapse_header_right_aligned():
    """D2026-1015-05 / 卡A：P2-3 词库折叠簇右对齐（方向=Console space-between 母版）。

    ⑤ style.css 含 `.gl-collapse-header .block-title` 规则且规则体含
      `flex: 1 1 auto` 与 `min-width: 0`（标题吃满剩余宽 → count/chevron/刷新
      整簇右推；DOM 序不变）；
    ⑥ `.action-row` 基类规则体不含 `justify-content`（其余 action-row 左对齐
      为正确语义，防全局两端对齐外溢）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    # ⑤ 词库折叠标题生长规则在位
    assert any("flex: 1 1 auto" in b and "min-width: 0" in b
               for b in _p01_rule_blocks(css, ".gl-collapse-header .block-title")), \
        ".gl-collapse-header .block-title 须含 flex: 1 1 auto 与 min-width: 0（P2-3）"

    # ⑥ action-row 基类左对齐语义零改动
    action_row = _p01_rule_blocks(css, ".action-row")
    assert action_row, "未找到 .action-row 规则块"
    for blk in action_row:
        assert "justify-content" not in blk, \
            ".action-row 规则块不得含 justify-content（防左对齐语义被两端对齐外溢）"


# ============================================================================
# d1015-卡C（回链 D2026-1015-05）；卡B 落地（HEAD 29276d8）之主次 class /
# 图标 / 文案双表同步尚无回归钉保护（主次回潮或双表失步无法被测试捕获）。
# 本钉锁定 P1-4 拖拽区恢复面（写法沿用本文件既有读取/解析 helper 与
# tests:5466 同款 button 片段正则）：
# ① #addFolderBtn 次级（含 `btn btn-secondary`，不含 `btn-primary`）；
# ② #addFilesBtn / #addFolderBtn 各含 `<svg` 且含 `stroke-width="2"`；
# ③ app.js MSG.source_header == '拖拽 .srt 字幕文件到这里'；
# ④ app.js MSG.empty_hint == index.html data-i18n="empty_hint" 挂点静态文本
#    （防双表失步）；
# ⑤ 校对页两枚 review-import-btn 各含 `<svg` 且含 `stroke-width="2"`。
# 红证据=负控（卡B 已落地，钉落盘即绿；先红由负控证明钉真能红，防空转）：
# 负控一改回 #addFolderBtn=btn btn-primary → 断言①红；负控二改回 app.js
# source_header 旧值 → 断言③红；红/绿两段原文见本卡执行记录。
# ============================================================================
def test_p14_dropzone_restored_pinned():
    """D2026-1015-05 / 卡C：P1-4 拖拽区恢复五断言钉（主次/图标/文案双表/校对钮）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    src = _app_js_source()

    def button_fragment(dom_id: str) -> str:
        """按 id 提取 button 完整元素片段（同 tests:5466 同款正则口径）。"""
        m = re.search(
            rf'<button[^>]*id="{re.escape(dom_id)}"[^>]*>(.*?)</button>',
            html, re.S)
        assert m, f"index.html 未找到 button#{dom_id}"
        return m.group(0)

    # ① 主次恢复：目录钮为次级，且不得回潮为 primary（P1-4 两枚并列 primary 无主次）
    folder = button_fragment("addFolderBtn")
    assert "btn btn-secondary" in folder, \
        "#addFolderBtn 须为次级按钮（class 含 btn btn-secondary，P1-4 主次恢复）"
    assert "btn-primary" not in folder, \
        "#addFolderBtn 回潮为 btn-primary（两枚并列 primary 无主次的 P1-4 缺陷）"

    # ② 拖拽区两钮图标化且粗细统一 2（Lucide 上游默认）
    for dom_id in ("addFilesBtn", "addFolderBtn"):
        frag = button_fragment(dom_id)
        assert "<svg" in frag, f"#{dom_id} 缺内联 svg 图标"
        assert 'stroke-width="2"' in frag, \
            f"#{dom_id} 图标 stroke-width 须为 2"

    # ③ app.js MSG.source_header 取值锁定（操作性文案，勿回旧值）
    m = re.search(r"^\s*source_header:\s*'([^']*)'", src, re.M)
    assert m, "app.js MSG 缺 source_header 键"
    assert m.group(1) == "拖拽 .srt 字幕文件到这里", \
        f"source_header 文案漂移：{m.group(1)!r}"

    # ④ 双表同步：MSG.empty_hint == index.html data-i18n="empty_hint" 两挂点静态文本
    m = re.search(r"^\s*empty_hint:\s*'([^']*)'", src, re.M)
    assert m, "app.js MSG 缺 empty_hint 键"
    msg_empty = m.group(1)
    texts = re.findall(r'data-i18n="empty_hint"[^>]*>([^<]*)<', html)
    assert texts, "index.html 未找到 data-i18n=\"empty_hint\" 挂点"
    assert set(texts) == {msg_empty}, \
        f"empty_hint 双表失步：MSG={msg_empty!r}，index 挂点={texts!r}"

    # ⑤ 校对页两枚导入钮图标化且粗细统一 2
    review = re.findall(
        r'<button[^>]*class="[^"]*review-import-btn[^"]*"[^>]*>.*?</button>',
        html, re.S)
    assert len(review) == 2, \
        f"review-import-btn 应恰 2 枚（校对页），实测 {len(review)}"
    for frag in review:
        assert "<svg" in frag, "review-import-btn 缺内联 svg 图标"
        assert 'stroke-width="2"' in frag, \
            "review-import-btn 图标 stroke-width 须为 2"


# ============================================================================
# d1015-卡L（回链 D2026-1015-05）：review.js `_injectTexts` 对两枚
# `.review-import-btn` 的裸 textContent 覆写会抹掉卡B 预置的内联 svg
# （图标运行期消失）——改为「清文本、回插 svg」并加防回退钉。
# ============================================================================
def test_review_import_icons_survive_inject():
    """D2026-1015-05 / 卡L：review.js 导入钮图标存活钉。

    卡B 已在校对页两枚 review-import-btn 内预置 video/file-text 内联 svg，
    但 `_injectTexts()` 以 `btn.textContent = REVIEW_MSG…` 整段覆写子节点树
    → svg 运行期被抹（图标永久消失）。修复=先取 svg 引用、清文本、再回插。
    正向双断言：① 函数体含 `querySelector('svg')` 取图标引用；② 含回插手段
    （prepend/appendChild/insertBefore 任一）——两者齐备即证明「清文本后又
    把 svg 插回」；裸 textContent 覆写不回插的形态必然不同时满足两断言。
    """
    body = _extract_function(_review_js_source(), "_injectTexts")
    assert "querySelector('svg')" in body, \
        "_injectTexts 未先取按钮内 svg 引用（裸 textContent 覆写会抹掉图标）"
    assert any(fn in body for fn in ("prepend", "appendChild", "insertBefore")), \
        "_injectTexts 未回插 svg（清文本后图标不存活）"


# ============================================================================
# d1015-卡E（回链 D2026-1015-05）：B-01 计数 JS 接线钉——卡D 骨架
# `<span class="card-head-count" data-testid="card-head-count">` 已落地，
# 但 app.js 从无写者，span 恒空、计数不显示。本钉四断言锁死接线：
# ① index.html 骨架锚恰 1 处（卡D 已落地，绿到即至）；
# ② MSG 表含 JS 态键 selected_count；
# ③ FileListManager.updateButtons 函数体消费 card-head-count/selected_count；
# ④ style.css .card-head-count 规则体两 token（--font-xs/--text-2）。
# ============================================================================
def test_b01_selected_count_pinned():
    """B-01 计数 JS 接线钉（d1015-卡E / D2026-1015-05）。

    人工推演（计数不显示场景）：卡D 已在文件卡头（.card-head）落地
    `<span class="card-head-count" data-testid="card-head-count">` 惰性骨架，
    但全文件零写入点——span 文本恒空，增删清空文件均无量化反馈。
    修复：MSG 表补 JS 态键 `selected_count: (n) => \\`已选 ${n} 个\\``（先例
    encodeSummaryVol/encodeSummaryAt 箭头函数值形态），并在
    FileListManager.updateButtons（增/删/清空/点选全路径的单点汇）按
    队列文件总数（AppState.selectedFiles.length，非勾选索引数）回写：
    >0 走计数文案、=0 置空（空态不得显「已选 0 个」）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    # ① 骨架锚恰 1 处（卡D 已落地，本断言绿到即至）
    assert html.count('data-testid="card-head-count"') == 1, \
        "index.html 须恰 1 处 data-testid=\"card-head-count\"（卡D 骨架）"
    # ② MSG 表含 selected_count 键（箭头函数值形态，_js_msg_keys 解析兼容）
    assert "selected_count" in _js_msg_keys(), \
        "app.js MSG 表缺 selected_count 键"
    # ③ 接线点：updateButtons 函数体（首匹配 = FileListManager.updateButtons）
    body = _extract_function(_app_js_source(), "updateButtons")
    assert "card-head-count" in body, \
        "updateButtons 未接线 .card-head-count（计数永不显示）"
    assert "selected_count" in body, "updateButtons 未消费 MSG.selected_count"
    # ④ style.css 规则体两 token（对比度/字号档位沿用卡D）
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    m = re.search(r"\.card-head-count \{[^}]*\}", css)
    assert m, "style.css 缺 .card-head-count 规则"
    assert "var(--font-xs)" in m.group(0) and "var(--text-2)" in m.group(0), \
        ".card-head-count 规则体缺 --font-xs/--text-2 token"


# ============================================================================
# d1015-卡G（回链 D2026-1015-05）：P1-9 空态/JS 态三态兜底终态钉——卡F 静态
# 兜底已落地（:empty 收形/details open/「—」占位），但学习词库空态仍静态
# display:none（JS 未跑时表头裸露）。本钉锁跨卡终态，防任一环回退：
# ① index.html `<details id="refineGuideViewer" open`（卡F 落地，绿到即至）；
# ② style.css 两族作用域 :empty 收形规则（卡F 落地，绿到即至）；
# ③ index.html #glLearnedEmpty 不再含静态 display:none 且 app.js
#    glLearnedLoad 函数体对其有显隐操作（本卡红核：先红后绿）；
# ④ index.html #dataRootCurrentPath 含「—」静态占位（卡F 落地）。
# 负控（硬要求）：临时删 details 的 open → ① 必红（红/绿留痕见卡执行记录）。
# ============================================================================
def test_p19_empty_state_fallback_pinned():
    """P1-9 空态/JS 态三态兜底终态钉（d1015-卡G / D2026-1015-05）。

    人工推演（JS 未跑/失败时逐格病灶）：
    - 质量页导读 details 默认闭合 → 「暂无导读数据」引导首屏不可见（卡F 已 open）；
    - 校对页空药丸/幽灵钮、高级页白卡空框 → 卡F 已 :empty 收形；
    - 学习词库空态元素静态 display:none → JS 未跑时表头裸露（卡G：显隐交
      JS 全权，入口先隐防加载中闪烁）；
    - 高级页数据目录路径空 span → 首帧无占位（卡F 已静态「—」）。
    本钉四项锁跨卡终态：①②④ 卡F 落地即绿，③ 为本卡红核（先红后绿）。
    """
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    src = _app_js_source()

    # ① 质量页导读 details 默认展开（卡F 落地，绿到即至）
    assert '<details id="refineGuideViewer" open' in html, \
        "① index.html 缺 `<details id=\"refineGuideViewer\" open`" \
        "（导读引导首屏不可见）"

    # ② 校对页/高级页空子件 :empty 收形规则（卡F 落地，绿到即至）
    assert ".review-det-tools button:empty" in css, \
        "② style.css 缺 .review-det-tools button:empty 收形规则"
    assert re.search(r'\[data-testid="encode-adv-group"\][^{]*:empty', css), \
        "② style.css 缺 [data-testid=\"encode-adv-group\"] 作用域 :empty 规则"

    # ③ 学习词库空态显隐交 JS 全权（本卡红核）
    m_empty = re.search(r'<div\b[^>]*id="glLearnedEmpty"[^>]*>', html)
    assert m_empty, "③ index.html 缺 #glLearnedEmpty 元素"
    tag = m_empty.group(0).replace(" ", "")
    assert "display:none" not in tag, \
        "③ #glLearnedEmpty 仍含静态 display:none（JS 未跑时表头裸露）"
    body = _extract_function(src, "glLearnedLoad")
    assert "glLearnedEmpty" in body and "empty.style.display" in body, \
        "③ glLearnedLoad 未对 #glLearnedEmpty 做显隐操作"

    # ④ 高级页数据目录路径静态「—」占位（卡F 落地）
    assert re.search(r'id="dataRootCurrentPath"[^>]*>\s*—\s*<', html), \
        "④ #dataRootCurrentPath 缺静态「—」占位"


# ============================================================================
# P2-9 右栏状态点五态接线（d1015-卡J / D2026-1015-05）
# ============================================================================
def test_p29_status_dot_wired():
    """P2-9 状态点五态接线钉（d1015-卡J / D2026-1015-05）。

    人工推演（owner 主诉"出错也不变红"）：setDot 原只切 running/idle 两态，
    .dot-ok/.dot-warn/.dot-err 三类虽在 style.css 在位却永不被右栏运行点
    点亮 → 出错/告警/正常完成一律灰或蓝。本卡收口：
    - setDot 全集化五态（未知值回落 dot-idle，全量 toggle）；
    - _finish 增第二参 dotState（默认 'idle'）收尾。
    评议实测勘误（必须遵守）：startStatusPolling 与 _finish 挂在
    TranslatorManager 上，TranslatorManager 无 setDot 方法；新调用点严禁
    this.setDot，须照抄现有 ProgressManager.setDot('running'|'idle') 同款
    真实引用形态——故本钉③断言带 ProgressManager. 前缀，禁裸子串防假绿。
    """
    src = _app_js_source()
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    # ① setDot 五类映射 + 五类全集 toggle（本卡红核）
    dot = _extract_function(src, "setDot")
    for cls in ("dot-idle", "dot-running", "dot-ok", "dot-warn", "dot-err"):
        assert f"'{cls}'" in dot, f"① setDot 缺五态类映射: {cls}"
        assert re.search(rf"toggle\('{cls}'", dot), \
            f"① setDot 未对 {cls} 做全量 toggle"
    assert re.search(r"map\[state\]|\?\?\s*'dot-idle'|\|\|\s*'dot-idle'", dot), \
        "① setDot 缺未知值回落 dot-idle"

    # ② _finish 第二参 dotState + 按真实引用形态 ProgressManager.setDot 收尾
    fin = _extract_function(src, "_finish")
    assert re.search(r"_finish\s*\(\s*statusText\s*,\s*dotState\s*=\s*'idle'", fin), \
        "② _finish 缺第二参 dotState（默认 'idle'）"
    assert "ProgressManager.setDot(dotState)" in fin, \
        "② _finish 未按真实引用形态 ProgressManager.setDot(dotState) 收尾"
    assert "this.setDot(" not in fin, \
        "② _finish 误用 this.setDot（TranslatorManager 无该方法）"

    # ③ 轮询函数体 warn/err 分支 + error 路径（带真实引用前缀形态）
    poll = _extract_function(src, "startStatusPolling")
    assert "ProgressManager.setDot('warn')" in poll, \
        "③ 轮询 tick 风险降级未接 ProgressManager.setDot('warn')"
    assert "dotState = 'warn'" in poll, \
        "③ completed 告警/多数未译分支未归 'warn'"
    assert "dotState = 'ok'" in poll, \
        "③ completed 正常完成分支未归 'ok'"
    assert "_finish(MSG.completed, dotState)" in poll, \
        "③ completed 收尾未把 dotState 传入 _finish"
    assert "_finish(MSG.error, 'err')" in poll, \
        "③ 轮询 status==='error' 分支未传 'err'"

    # ③b start 主链两处 error（collectOptions catch + 主 catch）全传 'err'
    start = _extract_function(src, "startTranslation")
    assert start.count("_finish(MSG.error, 'err')") == 2, \
        "③b start 主链 error 双处未全传 'err'"
    assert "this.setDot(" not in start, \
        "③b start 主链误用 this.setDot（须经 ProgressManager）"
    assert "ProgressManager.setDot('running')" in start, \
        "③b start 起跑态点色形态漂移"

    # ④ style.css .dot-err 规则仍在（错误红点样式在位）
    assert re.search(r"\.status-dot\.dot-err\s*\{", css), \
        "④ style.css 缺 .status-dot.dot-err 规则"


# ============================================================================
# d1015-卡K（回链 D2026-1015-05；规格 docs/design/d1015-P2残余批-设计规格.md §3
# 〔主审裁定追记 v2 R12〕）
# P2-4 质量页 #refineGuideViewer details 折叠头原生标记归一（mask 自绘
# Lucide chevron-right + [open] rotate）静态钉。
# ============================================================================
def test_p24_guide_details_chevron_pinned():
    """D2026-1015-05 / 卡K：P2-4 质量页 details chevron 归一静态钉（防回潮）。

    背景（规格 §3）：`<details id="refineGuideViewer">` 的 summary 是全站唯一
    既未摘原生 ▶ 标记、又无箭头语言的折叠头（站内两套既有语言：Console/词库
    按钮式 rotate；dict-diag/mp-tier 内嵌 svg 或 marker 摘除），与全站
    Lucide chevron+rotate 不一致。收口路线=先摘原生标记（list-style:none +
    ::-webkit-details-marker 双写）再以 `::after` 自绘 Lucide chevron-right：
    mask 只取 alpha，颜色由 background-color var(--text-2) 承担（随主题），
    [open] 时 rotate(90deg)。

    断言面：
    - style.css：#refineGuideViewer > summary 族四条规则（摘标记 / 自绘 /
      旋转）逐条在位，自绘规则体含 var(--text-2) 与 -webkit-mask/mask 双写；
    - index.html：`refineGuideViewer` 出现次数不变（==1，防误改 HTML，
      现值经 grep 记数）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    # ① 原生 ▶ 标记摘除：base summary list-style:none + WebKit 伪元素 display:none
    assert any("list-style: none" in blk for blk in
               _p01_rule_blocks(css, "#refineGuideViewer > summary")), \
        "① #refineGuideViewer > summary 缺 list-style: none（原生标记未摘）"
    marker = _p01_rule_blocks(
        css, "#refineGuideViewer > summary::-webkit-details-marker")
    assert marker and all("display: none" in blk for blk in marker), \
        "① 缺 #refineGuideViewer > summary::-webkit-details-marker{display:none}"

    # ② [open] 旋转规则在位（chevron 展开时转向）
    opened = _p01_rule_blocks(css, "#refineGuideViewer[open] > summary::after")
    assert opened and all("rotate(90deg)" in blk for blk in opened), \
        "② 缺 #refineGuideViewer[open] > summary::after{transform:rotate(90deg)}"

    # ③ 自绘 chevron 规则体：mask 取 alpha + 颜色 var(--text-2) + 双写 mask
    drawn = _p01_rule_blocks(css, "#refineGuideViewer > summary::after")
    assert drawn, "③ 缺 #refineGuideViewer > summary::after 自绘规则"
    for blk in drawn:
        assert "var(--text-2)" in blk, \
            "③ 自绘 chevron 未由 background-color var(--text-2) 承担颜色"
        assert "-webkit-mask:" in blk and re.search(r"(?<!-)\bmask:", blk), \
            "③ 自绘 chevron 未 -webkit-mask / mask 双写"

    # ④ index.html 零改动（防误改 HTML；现值 grep 记数 ==1）
    assert html.count("refineGuideViewer") == 1, \
        "④ index.html refineGuideViewer 出现次数漂移（应恒为 1，proof HTML 未动）"


# ============================================================================
# d1016 卡A（回链 D2026-1016-01；规格 docs/design/
# d1016-卡A-校对页ASR对照折叠钮.md）
# 校对页疑点区「ASR 对照」钮补 chevron 折叠语言 + aria-expanded 状态接线
# 静态钉（防回潮）：CSS chevron 常显 + [aria-expanded="true"] rotate(90deg)
# + review.js handler 同步 aria-expanded。
# ============================================================================
def test_review_asr_chevron_pinned():
    """D2026-1016-01 / 卡A：校对页 ASR 对照钮 chevron + aria 状态静态钉。

    背景（卡面根因）：`.review-det-tools` 工具行「ASR 对照」钮是
    `.review-asr-card` 显隐唯一切换钮，但无 chevron、无 aria 状态、切换无
    视觉反馈，与全站「Lucide chevron + rotate」折叠语言（P2-4 卡K / 词库页
    B2）不一致。收口路线=`#reviewAsrBtn::after` 自绘 Lucide chevron-right
    （mask 取 alpha，颜色由 background-color var(--text-2) 承担随主题），
    `[aria-expanded="true"]` 时 rotate(90deg)；review.js click handler 同步
    写 aria-expanded。

    断言面：
    - style.css：#reviewAsrBtn::after 自绘规则（含 var(--text-2) 与
      -webkit-mask/mask 双写）+ [aria-expanded="true"]::after rotate 规则；
    - review.js：reviewAsrBtn click handler 体含 setAttribute('aria-expanded');
    - index.html：`reviewAsrBtn` 出现次数恒为 1（防误改 HTML）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")
    js = REVIEW_JS.read_text(encoding="utf-8")

    # ① 自绘 chevron 规则体：mask 取 alpha + 颜色 var(--text-2) + 双写 mask
    drawn = _p01_rule_blocks(css, "#reviewAsrBtn::after")
    assert drawn, "① 缺 #reviewAsrBtn::after 自绘 chevron 规则"
    for blk in drawn:
        assert "var(--text-2)" in blk, \
            "① 自绘 chevron 未由 background-color var(--text-2) 承担颜色"
        assert "-webkit-mask:" in blk and re.search(r"(?<!-)\bmask:", blk), \
            "① 自绘 chevron 未 -webkit-mask / mask 双写"

    # ② [aria-expanded="true"] 旋转规则在位（chevron 展开时转向）
    opened = _p01_rule_blocks(css, '#reviewAsrBtn[aria-expanded="true"]::after')
    assert opened and all("rotate(90deg)" in blk for blk in opened), \
        '② 缺 #reviewAsrBtn[aria-expanded="true"]::after{transform:rotate(90deg)}'

    # ③ review.js reviewAsrBtn click handler 体同步 aria-expanded
    m = re.search(
        r"const asrBtn = document\.getElementById\('reviewAsrBtn'\);", js)
    assert m, "③ review.js 未找到 reviewAsrBtn 绑定段"
    seg = js[m.end():]
    mm = re.search(r"asrBtn\.addEventListener\('click',\s*\(\)\s*=>\s*\{", seg)
    assert mm, "③ review.js reviewAsrBtn 缺 click handler"
    depth = 0
    handler = ""
    for i in range(mm.end() - 1, len(seg)):
        ch = seg[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                handler = seg[mm.end() - 1:i + 1]
                break
    assert handler, "③ review.js reviewAsrBtn handler 花括号未配平"
    assert "setAttribute('aria-expanded'" in handler, \
        "③ reviewAsrBtn handler 未同步 setAttribute('aria-expanded')"

    # ④ index.html 零改动（防误改 HTML；现值 grep 记数 ==1）
    assert html.count("reviewAsrBtn") == 1, \
        "④ index.html reviewAsrBtn 出现次数漂移（应恒为 1，proof HTML 未动）"


# ============================================================================
# d1016 卡B（回链 D2026-1016-02；规格 docs/design/
# d1016-卡B-校对页右栏折叠钮.md）
# 校对页右栏解除强制隐藏（no-aside）改「折叠态起步」（右缘保留折叠/展开钮）
# 静态钉（防回潮）。
# ============================================================================


def test_review_aside_collapse_pinned():
    """D2026-1016-02 / 卡B：校对页右栏折叠态起步静态钉。

    背景（卡面根因）：review.js active tab=tab-review 时给 .workbench 挂
    no-aside → CSS 整体 display:none 右栏，全局折叠/展开钮（.aside-toggle-btn
    位于 .aside 内）随之消失，校对页无任何折叠入口。改法=进校对页强制
    aside-collapsed 折叠态（右缘保留 « 钮），离页恢复进页前状态（快照制，
    不读 localStorage）。

    断言面：
    ① review.js `_syncWorkbench` 函数体不含 no-aside 且含 aside-collapsed；
    ② review.js 含 _asidePreReview 快照字段/恢复分支与 _syncAsideAria 定义；
    ③ index.html no-aside 出现次数恒为 0（注释改写防回潮）；
    ④ style.css 零改动防线：.workbench.no-aside 规则仍存在（休眠保留）+
       .aside-toggle-btn 折叠态规则仍在。

    先红场景：本钉先落、JS 未改时 ①②③ 红（旧逻辑仍挂 no-aside、
    _asidePreReview/_syncAsideAria 未定义、HTML 注释仍含 no-aside）。
    """
    js = _review_js_source()
    html = INDEX_HTML.read_text(encoding="utf-8")
    css = (ASSETS / "style.css").read_text(encoding="utf-8")

    # ① _syncWorkbench 函数体：no-aside 摘除 + aside-collapsed 挂载
    body = _extract_function(js, "_syncWorkbench")
    assert "no-aside" not in body, \
        "① _syncWorkbench 仍挂/卸 no-aside（旧强制隐藏未摘除）"
    assert _ASIDE_COLLAPSE_CLASS in body, \
        "① _syncWorkbench 未挂 aside-collapsed（折叠态起步缺失）"

    # ② 快照字段声明 + 恢复分支 + aria 同步定义
    assert re.search(r"_asidePreReview:\s*null", js), \
        "② review.js 缺 _asidePreReview 快照字段声明"
    assert "_asidePreReview" in body, \
        "② _syncWorkbench 缺 _asidePreReview 快照恢复分支"
    assert re.search(r"_syncAsideAria\s*\([^)]*\)\s*\{", js), \
        "② review.js 缺 _syncAsideAria 定义（进页强制折叠态 aria 未补齐）"

    # ③ index.html no-aside 零命中（注释改写防回潮）
    assert html.count("no-aside") == 0, \
        "③ index.html 仍含 no-aside（注释回潮）"

    # ④ style.css 零改动防线（休眠保留，防误删破既有 @media 计数/卡G2卡N 钉面）
    assert re.search(r"\.workbench\.no-aside\s*\{[^}]*grid-template-columns",
                     css), \
        "④ style.css .workbench.no-aside 规则被删（休眠保留防线破裂）"
    assert re.search(
        r"\.workbench\.no-aside\s+\.aside\s*\{[^}]*display:\s*none", css), \
        "④ style.css .workbench.no-aside .aside 隐藏规则被删（休眠保留）"
    assert _p01_rule_blocks(css, ".aside-toggle-btn"), \
        "④ style.css 缺 .aside-toggle-btn 折叠把手规则（卡G2/卡N 钉面）"


# ============================================================================
# d1016 卡C（回链 D2026-1016-03；规格 docs/design/
# d1016-卡C-跳摘折叠头归一.md）
# 质量页「最近一次跳摘」details.fc-status-digest 折叠头原生 ▶ 归一
# （Lucide chevron + [open] rotate 90°）静态钉（防回潮）。
# 元素由 app.js 动态 createElement 创建（非 index.html），故 ④ 反钉零命中。
# ============================================================================
def test_fc_digest_chevron_pinned():
    """D2026-1016-03 / 卡C：跳摘折叠头 chevron 归一静态钉（防回潮）。

    背景（卡面根因）：全链状态行摘要 `details.fc-status-digest > summary`
    由 app.js 动态 createElement 创建（全库零 CSS），是 P2-4 卡K 归一时的
    漏网折叠头——原生 ▶ marker 直接外露、无任何 chevron 语言，与卡K 定下的
    「Lucide chevron + [open] rotate 90°」不一致。收口路线与卡K 同款：先摘
    原生标记（list-style:none + ::-webkit-details-marker 双写），再以
    `::after` 自绘 Lucide chevron-right（mask 只取 alpha，颜色由
    background-color var(--text-2) 承担随主题），[open] 时 rotate(90deg)；
    summary 改 display:flex 为 transform 生效前提。

    断言面：
    - style.css：.fc-status-digest summary 族三条规则（摘标记 / 自绘 /
      旋转）逐条在位，自绘规则体含 var(--text-2) 与 -webkit-mask/mask 双写；
    - index.html：`fc-status-digest` 出现次数恒为 0（该元素由 app.js 动态
      创建，防误搬进 HTML）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    html = INDEX_HTML.read_text(encoding="utf-8")

    # ① 原生 ▶ 标记摘除：base summary list-style:none + WebKit 伪元素 display:none
    assert any("list-style: none" in blk for blk in
               _p01_rule_blocks(css, ".fc-status-digest > summary")), \
        "① .fc-status-digest > summary 缺 list-style: none（原生标记未摘）"
    marker = _p01_rule_blocks(
        css, ".fc-status-digest > summary::-webkit-details-marker")
    assert marker and all("display: none" in blk for blk in marker), \
        "① 缺 .fc-status-digest > summary::-webkit-details-marker{display:none}"

    # ② 自绘 chevron 规则体：mask 取 alpha + 颜色 var(--text-2) + 双写 mask
    drawn = _p01_rule_blocks(css, ".fc-status-digest > summary::after")
    assert drawn, "② 缺 .fc-status-digest > summary::after 自绘规则"
    for blk in drawn:
        assert "var(--text-2)" in blk, \
            "② 自绘 chevron 未由 background-color var(--text-2) 承担颜色"
        assert "-webkit-mask:" in blk and re.search(r"(?<!-)\bmask:", blk), \
            "② 自绘 chevron 未 -webkit-mask / mask 双写"

    # ③ [open] 旋转规则在位（chevron 展开时转向）
    opened = _p01_rule_blocks(css, ".fc-status-digest[open] > summary::after")
    assert opened and all("rotate(90deg)" in blk for blk in opened), \
        "③ 缺 .fc-status-digest[open] > summary::after{transform:rotate(90deg)}"

    # ④ index.html 零命中（该元素由 app.js 动态创建，防误搬进 HTML）
    assert html.count("fc-status-digest") == 0, \
        "④ index.html 出现 fc-status-digest（该元素应由 app.js 动态创建）"


# ---------------------------------------------------------------------------
# 卡 0（D2026-1016-05 条件 C0/C1/C4）：app.js 拆分前置集中读取层接线钉
# ---------------------------------------------------------------------------

def test_js_sources_layer_pinned():
    """js_sources 集中读取层接线钉（卡 0；D2026-1016-05）。

    ① JS_FILES 现值锁定（后续拆分批随批更新本断言；批3 逐块切出自包含块）；
    ② read_all() 拼接视图 sha256 锁定（拆分后与整份 app.js 的守恒等价物）；
    ③ 三个静态测试文件均已接线 js_sources（读取点防回潮）。
    """
    assert js_sources.JS_FILES == [
        "app.js", "app-msg.js", "app-modal.js", "app-error-handler.js",
        "app-file-list.js", "app-console.js", "app-activity.js", "app-progress.js",
        "app-system-summary.js", "app-tm-query.js", "app-directory.js", "app-translator.js",
        "app-theme.js", "app-main.js",
    ], \
        f"JS_FILES 现值漂移（拆分批须随批同步本钉）: {js_sources.JS_FILES}"
    assert hashlib.sha256(
        js_sources.read_all().encode("utf-8")).hexdigest() == (
        "787460b7db478e48e104616e91cc32ac852fb05e0d922da15ad6fd7c4a433533"), \
        "read_all() 拼接视图 sha256 漂移（C0/C1 守恒不变量破）"
    tests_dir = Path(__file__).resolve().parent
    for name in ("test_gui_js_static.py", "test_strings_and_shortcut.py",
                 "test_ui_phase3_redlines.py"):
        src = (tests_dir / name).read_text(encoding="utf-8")
        assert "js_sources" in src, \
            f"{name} 未接线 js_sources 集中读取层（读取点回潮）"


def test_js_split_integrity_pinned():
    """app.js 拆分批1-3 完整性护栏（R-A，d1018-卡1 / D2026-1018-01；node 缺失亦生效）。

    ① 各分文件字节数与 sha256 锁定（纯字节搬运守恒的物证，函数不跨文件）；
    ② index.html 加载序 = JS_FILES 定义序（批3 后全部分文件全量钉），
       且 review.js 在该序之后（review.js 不属本拆分家族）。
    """
    frozen = {
        "app.js": (248,
                   "bc6e6a2f16167a94af74e404d368a5daca9e4fd3de0a8c063496da9b456aa9a0"),
        "app-msg.js": (58451,
                       "e6af08d83ff64d1c7366eb140deecefc68b0c6a01af08100e9998d623a4413eb"),
        "app-modal.js": (92754,
                         "4e987b4944251fc083b564ff94cc9a8b7a009c3b48f37852d98310f71b9b6707"),
        "app-error-handler.js": (745,
                                 "f0cf710570b468c793f5f5bd19ffdc51fc91a8822611da8946b90d793577724a"),
        "app-file-list.js": (15821,
                             "4ace89a8da62e4317535538abb4f7ed973b1f23de85a9b08381f1b0c22512d8b"),
        "app-console.js": (7818,
                           "2f877e37da26830a28808bb1df4b3ea8b025e942f460f0c095487c4f5e45f534"),
        "app-activity.js": (6167,
                            "bc9f860ca0399083c038faa2db9561449d1c9e48408b1dbc1d318b95db12665d"),
        "app-progress.js": (3070,
                            "e19571ec0a38d3e517501efb735771b31a0ac5a7ea39b371e29de596e19f2763"),
        "app-system-summary.js": (9494,
                                  "980cfd6a394de75f0f346387a382bc8cc302482a41605d4839551d5599b143c9"),
        "app-tm-query.js": (4893,
                            "c923272db15462c77875acdb27a32cc202860bd07fdf3245220bf1c4f70a4a2e"),
        "app-directory.js": (3149,
                             "2b4d435badd728491b076d295a4ff6b32109637166a790bfc12072e43c8686e3"),
        "app-translator.js": (19835,
                              "17e60b12b64381c428c11cde07fdedf5a558a2140d2bc1b60db8d52c8f490186"),
        "app-theme.js": (4234,
                         "943902377f465a30975c4e77d443ec784b0f44855203139c1055a5c6185f8d34"),
        "app-main.js": (243519,
                        "2dc6556ea55e2851ce106c6d9cb1d23d647a898a7e65cce35951e3fd5b2dd09f"),
    }
    for name, (size, digest) in frozen.items():
        raw = (ASSETS / name).read_bytes()
        assert len(raw) == size, f"{name} 字节数漂移: {len(raw)} != {size}"
        assert hashlib.sha256(raw).hexdigest() == digest, \
            f"{name} sha256 漂移（切分非纯字节搬运）"
    html = INDEX_HTML.read_text(encoding="utf-8")
    order = [html.index(f'src="{name}"')
             for name in (
                 "app.js", "app-msg.js", "app-modal.js",
                 "app-error-handler.js", "app-file-list.js", "app-console.js",
                 "app-activity.js", "app-progress.js", "app-system-summary.js",
                 "app-tm-query.js", "app-directory.js", "app-translator.js",
                 "app-theme.js", "app-main.js",
             )]
    assert order == sorted(order), \
        "index.html 加载序必须与 JS_FILES 定义序一致（批3 全量钉）"
    assert html.index('src="review.js"') > order[-1], \
        "review.js 必须在全部分文件之后加载（非本拆分家族）"
