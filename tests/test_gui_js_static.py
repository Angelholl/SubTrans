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
REVIEW_JS = ASSETS / "review.js"
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
            "tab-review", "tab-advanced"]


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
    """switchTab 到 tab-glossary 触发词库页初始化钩子（动态填充下拉）。"""
    body = _extract_function(_app_js_source(), "switchTab")
    assert "'tab-glossary'" in body and "__refineTplTabHook" in body, \
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
    # index.html（见 FROZEN_IDS），JS 只填充下拉与详情区，不再动态建行
    assert "dict-row" not in src, "词典行 .dict-row 模板残留（B2 案已废行渲染）"
    html = INDEX_HTML.read_text(encoding="utf-8")
    for val_id in ("dictEmpty", "dictSelect", "dictDetail", "dictPill", "dictDesc",
                   "dictPathRow", "dictPath", "dictOpenDir", "dictActionBtn"):
        assert f'id="{val_id}"' in html, f"词典卡 B2 骨架缺少：{val_id}"
    assert 'row.style.cssText' not in src, "词典行不得再用 inline style 布局（压住网格规则）"


# ---------------------------------------------------------------------------
# 批3（D2026-1001）：右栏系统状态摘要卡——结构在位 + 四接口逐项降级
# ---------------------------------------------------------------------------

def test_system_summary_card_structure_and_degradation():
    """摘要卡四数据行在位；SystemSummary 每接口独立 try/catch（单点失败不拖垮右栏）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="systemSummaryCard"' in html
    for val_id in ("sysSummaryVersion", "sysSummaryDataRoot", "sysSummaryTm", "sysSummaryDict"):
        assert f'id="{val_id}"' in html, f"摘要卡缺少数据行：{val_id}"
    src = _app_js_source()
    for api in ("get_version", "refine_get_data_root", "tm_get_stats", "refine_dict_status"):
        assert api in src, f"摘要卡未接入 {api}"
    # 降级：SystemSummary 段内必须存在 per-call catch（截取段落内判定）
    start = src.index("const SystemSummary")
    seg = src[start:start + 2400]
    assert "catch" in seg, "SystemSummary 缺少逐接口降级 catch"


# ---------------------------------------------------------------------------
# 批3（D2026-1002-12）：AI 分析区重排 + 主页 Console 占比 + 系统状态卡扩展
# ---------------------------------------------------------------------------

def test_batch3_ai_config_row_field_cols_pinned():
    """①AI 分析配置六件套改 3 组顶置标签列（.field-col）。

    - style.css 存在 .ai-config-row .field-col 规则组与 align-items:flex-start；
    - index.html 配置行恰 3 组 .field-col（服务商/模型/跨片窗口），
      3 处内联 width:auto 不再残留；
    - 橙色提示 #refineAiPrivacy 移入行尾（order:99 独立成行），
      四锚点 id 全保留（FROZEN_IDS 契约）。
    """
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    assert ".ai-config-row .field-col" in css, "缺 .field-col 规则组"
    m = re.search(r"\.ai-config-row \{[^}]*\}", css)
    assert m and "align-items: flex-start;" in m.group(0), \
        ".ai-config-row 缺 align-items:flex-start"
    assert re.search(r"\.ai-config-row > #refineAiPrivacy \{[^}]*order: 99;", css), \
        "#refineAiPrivacy 缺 order:99 行尾规则"
    html = INDEX_HTML.read_text(encoding="utf-8")
    i = html.index('class="ai-config-row"')
    row = html[i:html.index("</section>", i)]
    assert row.count('class="field-col"') == 3, "配置行必须恰 3 组顶置标签列"
    for dom_id in ("aiProviderSel", "aiModelInput", "aggregateWindowSel",
                   "refineAiPrivacy"):
        assert f'id="{dom_id}"' in row, f"配置行缺少锚点: {dom_id}"
    assert 'style="width:auto' not in row, "配置行残留内联 width:auto"


def test_batch3_console_ratio_and_section_overflow_pinned():
    """②主页 Console 与文件列表 70/30 比例分配 + 空态收敛（数值逐字冻结）。

    - .section 补 overflow:hidden（收敛双层圆角不同心）；
    - .console-output 圆角降为 --radius-sm、min-height:0（高度全交外层，
      180/420 定高删除）；
    - #tab-translate > .card 70% / .console-collapsible:not(.collapsed)
      30%（150 保底 / 300 上限，替换原 160/220）；
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
    assert "flex: 1 1 70%;" in css, "文件卡 70% 比例缺失"
    assert re.search(
        r"#tab-translate \.console-collapsible:not\(\.collapsed\) \{"
        r"[^}]*flex: 0 1 30%;[^}]*min-height: 150px;[^}]*max-height: 300px;",
        css), "Console 30%/150/300 数值漂移"
    assert "#tab-translate:not(.has-files) > .card { flex: 0 0 auto; }" in css, \
        "缺空态文件卡收敛规则"
    assert re.search(
        r"#tab-translate:not\(\.has-files\) \.file-list-container \{"
        r"[^}]*overflow-y: hidden;", css), "缺空态列表容器不滚动规则"


def test_batch3_system_summary_dynamic_rows_pinned():
    """③系统状态卡扩展：两行动态渲染（零新增静态 id）+ 委托绑定 + 新 MSG 键。

    - 角色卡/ASR 两行由 SystemSummary 动态建（data-sys-row 定位，
      行样式复用 .sys-summary-row），index.html 无任何 data-sys 静态锚；
    - ASR「重新探测」走事件委托绑 #systemSummaryCard（data-sys-action
      分流，按钮零 id），probeAsr 为唯一显式探测入口（首屏不自动探测）；
    - TM/词典行改"状态 · 路径"合并值（补 db_path / effective_dir）；
    - id 全集 213 不变（FROZEN_IDS 契约延续）。
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
    assert len(ids) == 213, f"id 全集数漂移（批3 契约 213 不变），实为 {len(ids)}"
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
    """④既有锚不回归：.asr-entry-hint 与 AI 分析区四锚保留。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'class="muted asr-entry-hint"' in html, ".asr-entry-hint 锚回归"
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
    页内零 data-i18n（静态键 cap 零消耗硬约束）。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    for i in ("tabBtnReview", "tab-review", "reviewDropzone", "videoReviewPlayer",
              "reviewTranscodeBtn", "reviewStatusBar", "reviewStatusDot",
              "reviewStatusLabel", "reviewProgressFill"):
        assert f'id="{i}"' in html, f"index.html 缺少校对页 id: {i}"
    assert 'data-kind="video"' in html and 'data-kind="srt"' in html, \
        "导入按钮必须带 data-kind 双值（事件委托分流契约）"
    assert '<script src="review.js"></script>' in html, "review.js 未挂载"
    # tab-review 区间（至 </main>）零 data-i18n
    m = re.search(
        r'<div class="tab-page" id="tab-review".*?</main>', html, re.S)
    assert m, "未找到 tab-review 页面区间"
    assert "data-i18n" not in m.group(0), \
        "tab-review 页内出现 data-i18n（静态键 cap 零消耗硬约束被破坏）"


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
    JS 视频后缀 ⊆ main.py 放行集，且放行集去掉 .srt 后恰等于
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
    assert main_exts - {".srt"} == js_video, \
        "main.py 放行集（去 .srt）与 JS 视频集不相等（后缀漂移）"


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
    ASR 引导卡跳引擎页必须走程序化 click（真实 handler 链）。"""
    body = _extract_function(_review_js_source(), "_bindDetections")
    assert 'data-tab="tab-engine"' in body, "须定位引擎页按钮"
    assert re.search(r'data-tab="tab-engine"[\s\S]{0,80}\.click\(\)', body), \
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
    # 结构序：header 行（含按钮）→ asrEnvStatus → .asr-entry-hint →
    # asrModelSel → asrCrosscheckToggle → asrRecList（id 全集不变，仅重排）
    anchors = ['data-i18n="asr_panel_title"', 'id="asrRefreshBtn"',
               'id="asrEnvStatus"', 'class="muted asr-entry-hint"',
               'id="asrModelSel"', 'id="asrStatus"',
               'id="asrCrosscheckToggle"', 'id="asrPythonInput"',
               'id="asrRecList"']
    pos = [card.index(a) for a in anchors]
    assert pos == sorted(pos), "ASR 卡结构序漂移（header→状态→说明→模型→开关→推荐）"
    # 无执行按钮：卡内 button 仅 asrRefreshBtn 一个
    assert len(re.findall(r"<button\b", card)) == 1, \
        "ASR 卡只允许「重新探测」一个按钮（不加执行能力）"
    # JS 态文案填充钉 + asrSaved 保存成功门控
    bind = _extract_function(_app_js_source(), "bindDom")
    for frag in ("MSG.asrRefreshBtn", "MSG.asr_env_undetected",
                 "MSG.asr_entry_hint", "MSG.asrSelectPlaceholder",
                 "MSG.asrCrosscheckLabel", "MSG.asrPythonPlaceholder"):
        assert frag in bind, f"bindDom 缺 ASR 卡 JS 态文案填充: {frag}"
    assert bind.count("MSG.asrSaved") == 3 and \
        bind.count("r.success ? MSG.asrSaved") == 3, \
        "asrSaved 必须仅在保存成功后写入（三处保存链均门控）"


def test_batch2_new_msg_keys_pinned():
    """批2 新增 JS 态 MSG 键存在（全中文文案，零静态 i18n 消耗）。"""
    src = _app_js_source()
    keys = _js_msg_keys()
    for key in ("model_list_empty_hint", "asr_env_undetected",
                "asr_entry_hint"):
        assert key in keys, f"MSG 缺少批2新键: {key}"
        m = re.search(rf"^\s*{key}:\s*'([^']*)'", src, re.M)
        assert m and m.group(1), f"MSG 键 {key} 文案为空"


# ---------------------------------------------------------------------------
# 2.6.2 热修：R3 ASR 推荐项长 URL 撑爆卡片 + R4 词典状态加载失败吞错
# ---------------------------------------------------------------------------

def test_asr_render_rec_list_details_fold_pinned():
    """R3 回归钉：ASR 推荐项折叠为 details/summary，完整 URL 与 sha256
    移入展开详情（.asr-rec-detail），summary 行只留来源分类文案
    （hf-mirror.com=国内源，否则海外源），title 悬停可见完整 URL。"""
    body = _extract_function(_app_js_source(), "asrRenderRecList")
    assert "createElement('details')" in body, "推荐项必须折叠为 <details>"
    assert "createElement('summary')" in body, "缺少 summary 摘要行"
    assert "asr-rec-detail" in body, "展开详情容器缺失"
    for key in ("MSG.asrSrcOverseas", "MSG.asrSrcDomestic"):
        assert key in body, f"summary 来源分类缺少 {key}"
    assert "hf-mirror.com" in body, "来源分类规则（hf-mirror.com=国内源）缺失"
    assert re.search(r"\.title\s*=\s*[^;]*rec\.url", body), \
        "summary 必须挂 title=完整 URL（悬停可见）"


def test_dict_load_failure_not_swallowed_pinned():
    """R4 回归钉：dictLoad 链尾 catch 不得静默吞错，须回写 #dictStatus
    失败文案（与 then 分支 dict_load_failed 同口径）。"""
    body = _extract_function(_app_js_source(), "dictLoad")
    assert re.search(r"catch\s*\(\s*\)\s*=>\s*\{\s*\}", body) is None, \
        "dictLoad 链尾残留空 catch（吞错导致 #dictStatus 空白）"
    assert ".catch(" in body, "dictLoad 必须保留 catch 链"
    assert body.count("MSG.dict_load_failed") >= 2, \
        "catch 回调必须回写 dictStatus 失败文案（MSG.dict_load_failed）"


def test_asr_rec_detail_css_pinned():
    """R3 配套 CSS：.asr-rec-detail 规则块在位且含长串断行
    （word-break: break-all，先例 .media-source-path）。"""
    css = (ASSETS / "style.css").read_text(encoding="utf-8")
    m = re.search(r"\.asr-rec-detail \{[^}]*\}", css)
    assert m, "style.css 缺 .asr-rec-detail 规则"
    assert "word-break: break-all" in m.group(0), \
        ".asr-rec-detail 缺 word-break: break-all"


# ---------------------------------------------------------------------------
# 2.6.3 批B（D2026-1003-01 ② + D2026-1003-05 五条件）：ASR 下载器 + 词典源
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
    for key in ("asrDlNoCancel", "asrDlDone", "asrDlFailed", "ui_copied",
                "ui_copy_manual"):
        assert key in keys, f"MSG 缺少批B新键: {key}"


def test_asr_rec_download_entry_pinned():
    """ASR 推荐项下载入口：details 展开区「下载…」→ AppModal.download →
    refine_asr_download + 1s 轮询 + settle 后 asrRefresh；PENDING 镜像
    （!verified）前端同口径禁用。"""
    src = _app_js_source()
    body = _extract_function(src, "asrRenderRecList")
    assert "MSG.asrDownloadBtn" in body, "下载按钮文案键缺失"
    assert "asrDownloadModal(rec)" in body, "下载模态调用缺失"
    dl = _extract_function(src, "asrDownloadModal")
    assert "refine_asr_download(" in dl, "下载桥调用缺失"
    assert "refine_asr_download_progress(" in dl, "进度轮询桥缺失"
    assert "setInterval" in dl, "1s 轮询缺失"
    assert "asrRefresh()" in dl, "settle 后刷新推荐清单缺失"
    assert "!s.verified" in dl, "PENDING 镜像禁用判定缺失"
    assert "MSG.srcMirrorPendingHint" in dl, "禁用卡 hint 文案键缺失"
    assert "MSG.asrDlNoCancel" in dl, "无取消声明文案缺失"
    assert "MSG.dictFallbackNotice" in dl, "回退提示文案键缺失"


def test_dict_source_buttons_pinned():
    """词典源双按钮：JS 注入零 id + CN 可达性 title + 无镜像禁用逻辑 +
    dictDownload source 透传 + p.note 可见提示。"""
    src = _app_js_source()
    body = _extract_function(src, "dictRenderDetail")
    assert "dict-src-official" in body and "dict-src-mirror" in body, \
        "双按钮 class 注入缺失"
    assert "MSG.dictSrcOfficialOnly" in body and "MSG.dictSrcMirrorOnly" in body, \
        "双按钮文案键缺失"
    assert "MSG.dictSrcOfficialHint" in body, "官方源 CN 可达性 title 缺失"
    assert "has_mirror" in body, "无镜像禁用判定缺失"
    assert "MSG.dictSrcMirrorlessHint" in body, "无镜像禁用 title 文案缺失"
    dl = _extract_function(src, "dictDownload")
    assert re.search(r"refine_dict_download\(kind,\s*source\s*\|\|\s*'auto'\)", dl), \
        "refine_dict_download 须透传 source（缺省 auto）"
    assert "p.note" in dl, "轮询回调缺 p.note 可见提示（评议员条件①）"
