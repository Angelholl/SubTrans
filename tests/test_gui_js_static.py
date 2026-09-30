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
import re
import shutil
import subprocess
from pathlib import Path

import pytest

ASSETS = (Path(__file__).resolve().parents[1] / "subtransjav"
          / "webview_gui" / "assets")
APP_JS = ASSETS / "app.js"
INDEX_HTML = ASSETS / "index.html"


def _app_js_source() -> str:
    return APP_JS.read_text(encoding="utf-8")


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
    r = subprocess.run([node, "--check", str(APP_JS)],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stderr


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

_TAB_IDS = ["tab-translate", "tab-engine", "tab-glossary", "tab-guide",
            "tab-advanced"]


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
    """tab-translate 页含翻译服务快捷下拉：既定 6 个 provider 值
    （lmstudio 默认，zen 与引擎页三处同步）+ 本地提示行锚点；API KEY
    输入域已收口至引擎页（主页 key 行整体移除，删除钉防回退）。"""
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
    # 快捷下拉必须位于 tab-translate 页内（引导卡删除后仍属翻译主页）
    assert html.index('id="refineServiceQuick"') \
        > html.index('id="tab-translate"')
    assert html.index('id="refineServiceQuick"') \
        < html.index('id="tab-engine"')


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


def test_ai_privacy_bar_provider_branch():
    """隐私提示条：云端 provider（deepseek/siliconflow/custom/zen）显示
    aiPrivacyCloud；本地显示 aiPrivacyLocal。"""
    source = _app_js_source()
    _extract_function(source, "isAiCloudProvider")
    m = re.search(r"AI_CLOUD_PROVIDERS\s*=\s*\[([^\]]+)\]", source)
    assert m, "app.js 未找到 AI_CLOUD_PROVIDERS 常量"
    cloud_list = m.group(1)
    for prov in ("deepseek", "siliconflow", "custom", "zen"):
        assert f"'{prov}'" in cloud_list, f"云服务商清单缺 {prov}"
    bar = _extract_function(source, "aiSetPrivacy")
    assert "aiPrivacyCloud" in bar and "aiPrivacyLocal" in bar, \
        "隐私条必须双分支文案"


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
