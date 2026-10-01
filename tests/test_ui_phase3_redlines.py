"""阶段3（2.2.1）三面红线静态钉（D2026-1001-02 批清单二级评议闭环件）。

R1 DOM 恒定 / R2 节奏禁区 / R3 契约恒空的机器化落点：
- 钉① 批1：阶段A/B/第三卡区间无残留内联宽度（C3 断言域=三卡，域外内联合法）
- 钉② 批2：两张词库表挂 .gl-table
- 钉③ 批2：glRender/glLearnedLoad 行模板无 style= 字面量
- 钉④ R2：:root 节奏禁区变量与文档级字号行高逐字冻结
- 钉⑤ R1/R3（HRO-1 采纳件）：id 全集 191 + data-i18n 键全集 192 快照冻结
  （批3 190/192；批2 修订 D2026-1002-05 +1 id=aggregateWindowSel 恰达
  静态键 cap 192；下一 UI 耗键批首件=扩 cap 192→200 提案）——
  gate.check 只拦"丢失"不拦"新增"，本钉补上新增方向的机器闸；
  未来合法契约变更必须显式更新本文件快照（有意摩擦，防静默漂移）。
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_ASSETS = ROOT / "subtransjav" / "webview_gui" / "assets"
HTML = (_ASSETS / "index.html").read_text(encoding="utf-8")
JS = (_ASSETS / "app.js").read_text(encoding="utf-8")
CSS = (_ASSETS / "style.css").read_text(encoding="utf-8")


def _slice_between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


def test_batch1_stage_cards_no_inline_width():
    """钉①（C3 域）：阶段A 完整行→接口地址区之间的三卡无内联宽度。"""
    block = _slice_between(HTML, "<!-- 阶段A 完整行 -->", "<!-- 接口地址")
    assert 'style="min-width' not in block, "三卡区间残留内联 min-width（批1 收编遗漏）"
    assert 'style="width' not in block, "三卡区间残留内联 width（批1 收编遗漏）"


def test_batch2_glossary_tables_carry_gl_table():
    """钉②：两词库表挂 gl-table（表级宽度/列宽规则依托该类生效）。"""
    assert '<table id="refineGlossTable" class="gl-table">' in HTML
    assert '<table id="glLearnedTable" class="gl-collapsible-content gl-table">' in HTML


def test_batch2_gl_row_templates_no_inline_style():
    """钉③：glRender/glLearnedLoad 函数体无 style= 字面量。"""
    render = _slice_between(JS, "function glRender(", "async function glLoad(")
    learned = _slice_between(JS, "async function glLearnedLoad(", "function glAdd(")
    assert "style=" not in render, "glRender 行模板残留内联样式"
    assert "style=" not in learned, "glLearnedLoad 行模板残留内联样式"


def test_r2_rhythm_tokens_frozen():
    """钉④：节奏禁区变量值逐字冻结（动它=候选池禁区项，须显式复议）。"""
    assert "--space-1: 4px;" in CSS
    assert "--font: 14px; --font-sm: 13px; --font-xs: 12px;" in CSS
    assert re.search(r"html\s*\{[^}]*font-size:\s*var\(--font\);", CSS), \
        "html 文档级字号被改动"
    assert re.search(r"body\s*\{[^}]*line-height:\s*1\.55;", CSS), \
        "body 文档级行高被改动"


# 快照刻意用多行字符串形态（SIM905 已在 pyproject per-file-ignores 豁免）：diff 逐词可读、增删一目了然
FROZEN_IDS = frozenset(
    """
    aboutModal aboutVersion aggregateWindowSel aiModelInput aiProviderSel appModal addFilesBtn addFolderBtn asrDownloadBtn asrEnvStatus
asrModelSel asrProgress asrProgressText asrRefreshBtn asrStatus audioPreviewBar audioPreviewCloseBtn
audioPreviewError audioPreviewPlayer audioPreviewTiming browseOutputBtn clearBtn
clearConsoleBtn consoleCollapseBtn consoleOutput dataRootBar dataRootCurrentPath
dataRootRestoreBtn dataRootSourceTag dataRootStatus dataRootToggleBtn debugLogging
dictActionBtn dictDesc dictDetail dictEmpty dictOpenDir dictPath dictPathRow dictPill
dictProgress dictRows dictSelect dictStatus directionCardList directionCardS1
directionCardS3
directionSource directionTarget dropzone emptyState featureStatus fileList
fileListContainer firstRunBanner glEmptyHint
glLearnedEmpty glLearnedMore glLearnedReloadBtn glLearnedStats glLearnedStatus
glLearnedTable glTabGlossary grammarHintBadge guideCompanions guideConclusions
guideCustomStatus guideEmptyHint guideItems guideJsonBlocks guideMeta guideOpenOtherBtn
guideSections guideStatus guideTxtView iconMoon iconSun mediaOverrideApplyBtn
mediaOverrideInput mediaOverrideStatus mediaSourceBar mediaSourceEditRow mediaSourcePath
mediaSourceTag mediaSourceToggleBtn openOutputBtn outputDir outputToSource pipelineCard
pipelineMirrorLine progressBar progressFill refineAdaptiveThresholds refineAiAnalyzeBtn
refineAiAnalyzeSection refineAiAnalyzeStatus refineAiPrivacy refineAiResult
refineAutoSynopsis refineBatchCloud refineBatchLocal
refineBatchFixBtn refineBatchFixScope refineBatchFixStatus
refineCancelBtn refineCleanerConfig
refineCleanerConfigShow refineConcurrency refineEndpointStatus refineFallbackLocal
refineFallbackModel refineForceResume refineGl1 refineGl2 refineGlAdd refineGlCount
refineGlDel refineGlExport refineGlImport refineGlPath refineGlSave refineGlStatus
refineGlossTable
refineGlossary refineGlossaryConflictBlock refineGlossaryLearn refineGuideLoadBtn
refineGuideViewer refineOpenCleanerDir refineOpenDirBtn refinePickCleanerDir
refinePickDirBtn refineProfile refineRefreshS1 refineRefreshS3 refineS1Enabled
refineS1Endpoint refineS1Key refineS1Model refineS1Provider refineS3Enabled
refineS3Endpoint refineS3Key refineS3Model refineS3Provider refineSaveEndpointsBtn
refineSaveS1KeyBtn refineSaveS3KeyBtn refineServiceQuick refineServiceQuickLocalHint
refineSourceFilter refineStartBtn refineTemplateReload refineTemplateSave
refineTemplateStage refineTemplateStatus refineTemplateText refineTemplatesDir
refineTemplatesDirShow refineTestS1 refineTestS1Status refineTestS3 refineTestS3Status
refineTmDb refineTmEnable refineTmThreshold refineTplLoadedPath refineV2Ctx
refreshFallbackModels removeSelectedBtn resumeToggle statusDot statusLabel
sysSummaryDataRoot sysSummaryDict sysSummaryTm sysSummaryVersion systemSummaryCard
tab-advanced tab-engine tab-glossary tab-guide tab-translate tabBtnAdvanced tabBtnEngine
tabBtnGlossary tabBtnGuide tabBtnTranslate themeBtn themeMenu themeStylesheet
""".split())

FROZEN_I18N_KEYS = frozenset(
    """
    about_intro about_intro_text about_link about_title adaptive_thresholds_label
adaptive_thresholds_title add_files add_folder adv_group_fallback_concurrency
adv_group_resume_logging adv_group_tm_learn_gate adv_group_translation_glossary
advanced_settings_notice aiAnalyzeBtn app_header_title artifact_note asr_panel_title audio_preview_close
batchFixBtn batch_cloud_label batch_local_label browse_btn browse_dots cleaner_dir_label
cleaner_dir_placeholder clear_btn clear_console close_btn collapse_toggle
concurrency_label concurrency_title console_collapse console_header ctx_label
ctx_placeholder ctx_title data_root_change_btn data_root_restore_btn data_root_title
dict_empty_cta dict_empty_guide dict_open_dir dict_select_label dict_panel_title
direction_block_title direction_card_fallback_hint
direction_card_placeholder direction_card_s1_label direction_card_s3_label
direction_hint direction_label direction_title doc_title empty_hint endpoints_summary
fallback_local_label fallback_local_title fallback_model_label fallback_no_auto
feat_context_review feat_fallback feat_glossary_learn feat_report feat_tm
feature_status_title footer_brand force_resume_label force_resume_title gl1_label
gl2_label gl_add gl_del gl_empty_hint gl_export gl_import gl_learned_col_aliases
gl_learned_empty gl_learned_note gl_learned_reload gl_learned_title gl_path_empty
gl_save gl_scope_note gl_summary glossary_conflict_block_label glossary_learn_label
glossary_learn_title grammar_hint_text guide_companions guide_conclusions
guide_empty_hint guide_items_title guide_load_btn guide_open_other_btn guide_sections
guide_source_group_title guide_summary key_placeholder lang_en lang_ja lang_zh
main_subtitle media_override_apply media_override_placeholder media_source_change_btn
media_source_label model_default_1 model_default_2 model_refresh_hint nav_group_quality
nav_group_workspace no_files_selected open_btn output_header output_label
output_placeholder pipeline_card_hint profile_cloud profile_label profile_local
profile_title project_home_link provider_custom provider_lmstudio provider_ollama
provider_siliconflow provider_zen ready refine_panel_title refresh_local_title
refresh_model_title remove_selected resume_label resume_title s1_endpoint_label
s1_endpoint_placeholder s3_endpoint_label s3_endpoint_placeholder save_endpoints_btn
save_key_title save_to_source_dir sc_ctrl_o sc_ctrl_r sc_escape sc_f1 serviceQuickBadge
serviceQuickHintLocal serviceQuickLabel sf_default sf_off sf_strict sf_title
shortcuts_title source_filter_label source_header stage_a_label stage_b_label start_btn
status_idle stop_btn synopsis_label synopsis_title sys_summary_title sys_summary_version
tabAdvanced tabEngine tabGlossary tabGuide tabTranslate templates_dir_label
templates_dir_placeholder test_stage_btn test_stage_title th_source th_target theme_dark
theme_default theme_label tm_db_label tm_db_placeholder tm_enable_label tm_enable_title
tm_threshold_label tm_threshold_placeholder tm_threshold_title tpl_editor_summary
tpl_explicit_card_hint tpl_placeholder tpl_reload tpl_save verbose_label verbose_title
""".split())


def _current_ids():
    return frozenset(re.findall(r'(?<![\w-])id="([^"]+)"', HTML))


def _current_i18n_keys():
    return frozenset(re.findall(r'data-i18n(?:-title|-placeholder)?="([^"]+)"', HTML))


def test_r3_id_fullset_frozen():
    """钉⑤a（HRO-1）：id 全集快照冻结，新增/删除/改名一律显式改快照。"""
    cur = _current_ids()
    assert cur == FROZEN_IDS, (
        f"id 全集漂移：新增={sorted(cur - FROZEN_IDS)} 删除={sorted(FROZEN_IDS - cur)}"
        "（R1/R3 契约恒空；合法变更须显式更新快照并走二级评议）"
    )


def test_r3_i18n_key_fullset_frozen():
    """钉⑤b（HRO-1）：data-i18n 键全集快照冻结（含 title/placeholder 变体）。"""
    cur = _current_i18n_keys()
    assert cur == FROZEN_I18N_KEYS, (
        f"data-i18n 键全集漂移：新增={sorted(cur - FROZEN_I18N_KEYS)} 删除={sorted(FROZEN_I18N_KEYS - cur)}"
        "（R3 契约恒空；合法变更须显式更新快照并走二级评议）"
    )
