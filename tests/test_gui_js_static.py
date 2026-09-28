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
# A4：画像预设（novice=小白 / standard=标准 / developer=开发者）+ 首启初始化
# ---------------------------------------------------------------------------

def test_apply_user_mode_toggles_persona_class_and_persists_profile():
    """applyUserMode 用 CSS 类切换 novice 视图（不删 DOM，保控件 id 钉）；
    画像持久化到 settings KV 键 ui_profile；切换即存。"""
    source = _app_js_source()
    body = _extract_function(source, "applyUserMode")
    assert "persona-novice" in body, \
        "novice 必须切换 persona-novice 类（CSS 隐藏，不删 DOM）"
    assert "classList.toggle" in body
    assert "ui_profile" in source, "画像必须持久化到 settings KV 键 ui_profile"
    assert "first_run" in source, "回填路径必须消费 first_run 标志"
    assert "'novice'" in source, "首启（first_run 且无 ui_profile）默认 novice 分支"
    save_body = _extract_function(source, "saveUserMode")
    assert "refine_save_stage_settings" in save_body, "切换即存必须走后端"
    assert "ui_profile" in save_body, "切换即存键必须为 ui_profile"


def test_index_html_has_user_mode_select_and_novice_css():
    """index.html 必须含用户模式三选项下拉与 novice 隐藏 CSS 规则。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="refineUserMode"' in html, "缺少用户模式下拉"
    for value in ("novice", "standard", "developer"):
        assert f'value="{value}"' in html
    assert "persona-novice" in html, "index.html 需含 .persona-novice CSS 规则"
    assert "refine-novice-hide" in html, "index.html 需含 novice 隐藏标记类"


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
# v1.4 小白模式增补批：顶部翻译服务下拉栏 + 中央三步引导卡（面板级显隐）
# ---------------------------------------------------------------------------

_NOVICE_PROVIDER_VALUES = ["lmstudio", "ollama", "deepseek", "siliconflow",
                           "custom"]


def test_index_html_novice_panel_with_provider_options():
    """小白视图容器存在：翻译服务下拉含既定 5 个 provider 值（lmstudio 默认），
    并具备 key 行 / 本地提示行 / 开始按钮 / 完整面板根容器等锚点。"""
    html = INDEX_HTML.read_text(encoding="utf-8")
    assert 'id="refineNovicePanel"' in html, "缺少小白视图容器 refineNovicePanel"
    assert 'id="refineNoviceProvider"' in html, "缺少小白翻译服务下拉"
    m = re.search(r'<select[^>]*id="refineNoviceProvider".*?</select>',
                  html, re.S)
    assert m, "refineNoviceProvider 下拉解析失败"
    values = re.findall(r'<option value="([^"]+)"', m.group(0))
    assert values == _NOVICE_PROVIDER_VALUES, \
        f"novice 服务下拉选项值不符: {values}"
    assert 'value="lmstudio" selected' in m.group(0), \
        "默认项必须为本地 LM Studio（lmstudio）"
    for anchor in ("refineNoviceKeyRow", "refineNoviceKey",
                   "refineNoviceLocalHint", "refineNoviceStartBtn",
                   "refineFullPanel"):
        assert f'id="{anchor}"' in html, f"缺少小白面板锚点: {anchor}"


def test_apply_user_mode_toggles_panel_level_visibility():
    """applyUserMode 必须做面板级显隐：novice 显示 refineNovicePanel 并隐藏
    refineFullPanel（standard/developer 恢复完整面板）。"""
    body = _extract_function(_app_js_source(), "applyUserMode")
    assert "refineFullPanel" in body, "缺少完整面板根容器显隐"
    assert "refineNovicePanel" in body, "缺少小白面板显隐"
    assert "'none'" in body and "'flex'" in body, \
        "面板级显隐必须以 display none/flex 切换"


def test_novice_key_row_toggles_on_cloud_providers():
    """key 行联动：deepseek/siliconflow/custom（云服务）显示 key 行；
    本地服务隐藏 key 行并显示本地启动提示行。"""
    body = _extract_function(_app_js_source(), "refreshNoviceKeyRow")
    for prov in ("deepseek", "siliconflow", "custom"):
        assert prov in body, f"key 行联动缺少云服务分支: {prov}"
    assert "refineNoviceKeyRow" in body, "必须联动 key 行显隐"
    assert "refineNoviceLocalHint" in body, "本地服务必须显示提示行"


def test_novice_provider_change_syncs_stages_and_persists():
    """novice 下拉选择即同步阶段A/B provider（endpoint 缺省沿用既有映射），
    并持久化：stages 复用 saveStageEndpoints 通道 + settings KV 键
    novice_provider。"""
    source = _app_js_source()
    body = _extract_function(source, "applyNoviceProvider")
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
    assert "novice_provider" in body, \
        "必须持久化 settings KV 键 novice_provider"


def test_novice_key_save_uses_stage_a_key_channel():
    """novice 密钥保存必须复用 refine_save_stage_settings 的 keys 数组通道
    （即单阶段密钥保存通道）并落 stage A（阶段A）。"""
    body = _extract_function(_app_js_source(), "saveNoviceKey")
    assert "refine_save_stage_settings" in body, \
        "必须复用既有密钥保存通道"
    assert "stage: 1" in body, "密钥必须落 stage A（阶段A）"
    assert "provider: prov" in body, "密钥必须随当前 novice 服务商隔离存储"


def test_novice_start_btn_reuses_start_flow():
    """novice 开始按钮：无文件→行内错误提示；有文件→复用与 #refineStartBtn
    完全相同的启动流程（TranslatorManager.startTranslation），并已绑定 click。"""
    source = _app_js_source()
    body = _extract_function(source, "noviceStartTranslation")
    assert "AppState.selectedFiles.length === 0" in body, \
        "无文件分支必须先行校验"
    assert "TranslatorManager.startTranslation()" in body, \
        "必须复用既有 start 流程（不复制粘贴启动逻辑）"
    bind = _extract_function(source, "bindDom")
    assert "refineNoviceStartBtn" in bind, "novice 开始按钮必须绑定 click"
