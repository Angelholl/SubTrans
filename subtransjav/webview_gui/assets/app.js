/**
 * SubTransJAV GUI 前端控制器
 *
 * Features:
 * - SRT 文件列表管理（按钮选择 / 文件夹扫描 / 拖拽）
 * - 两阶段流水线配置与启动（refine 子进程）
 * - 实时日志流 + 进度轮询
 * - 主题切换
 */

// ============================================================
// User-Facing Strings（用户可见文案表）
// 与后端 subtransjav/webview_gui/strings.py 的 MSG 字典对应；
// JS 侧无法 import Python，故集中镜像于此（键名尽量保持一致）。
// ============================================================
const MSG = {
    // 状态栏 / 流程
    idle: '空闲',
    starting: '正在启动...',
    running: '运行中',
    completed: '已完成',
    cancelled: '已取消',
    error: '错误',
    ready: '就绪。',

    // 文件列表
    usingSourceOutput: '未获取默认输出目录，已切换为「保存到字幕同目录」',
    addedViaDrop: n => `✓ 已通过拖放添加 ${n} 个字幕文件`,
    skippedDuplicates: n => `ℹ 跳过 ${n} 个重复文件`,
    skippedNonSrt: n => `ℹ 跳过 ${n} 个不支持的文件（仅支持 .srt/.ass/.ssa/.vtt）`,
    addedFiles: n => `已添加 ${n} 个字幕文件`,
    addedFilesFromFolder: n => `已从文件夹添加 ${n} 个 .srt 文件`,
    fileSelectError: '文件选择出错',
    folderSelectError: '文件夹选择出错',
    removedItems: n => `已移除 ${n} 项`,
    clearedItems: n => `已清空 ${n} 项`,

    // 输出目录
    outputDirSet: p => `输出目录：${p}`,
    browseOutputError: '浏览输出目录出错',
    noOutputDirTitle: '未设置输出目录',
    noOutputDirHint: '请先指定输出目录。',
    folderOpened: p => `已打开文件夹：${p}`,
    openFolderFailed: '打开文件夹失败',
    openFolderError: '打开文件夹出错',

    // 翻译流程
    noFilesTitle: '未添加文件',
    translationStarted: pid => `翻译已启动（pid ${pid}）`,
    startFailed: '启动翻译失败',
    translationErrorLog: m => `翻译出错：${m}`,
    translationErrorTitle: '翻译出错',
    cancelledLog: '翻译已取消',
    overwriteConfirm: files =>
        '检测到已完成的终稿产物：\n'
        + (files || []).join('\n')
        + '\n\n· 旧产物将自动备份为 *_bak_时间戳 同目录文件\n'
        + '· 备份失败将继续覆盖并在日志告警\n\n是否覆盖并重新翻译？',
    completedLog: '翻译完成',
    translationFailedTitle: '翻译失败',
    unknownError: '未知错误',

    // 杂项
    themeSwitched: k => `主题：${k}`,
    bridgeConnected: 'PyWebView 桥接已连接',

    // ============================================================
    // i18n 键表（W2 收编）：index.html data-i18n/data-i18n-title/
    // data-i18n-placeholder 引用的键必须全部出现在本表（tests 钉住）；
    // JS 动态文案也统一收编于此，键名 snake_case 或 camelCase 语义化。
    // ============================================================

    // ---- 顶栏 / 主题 ----
    doc_title: '净语翻译 · SubTrans Translate',
    app_header_title: '净语翻译 · SRT',
    main_subtitle: '一站式 AI 字幕翻译与校对',
    nav_group_workspace: '工作区',
    nav_group_quality: '设置',
    feature_status_title: '功能状态',
    grammar_hint_text: '语法提示',
    theme_label: 'Theme',
    theme_default: '默认主题',
    theme_dark: '暗色主题',

    // ---- Source 区 / 文件按钮 ----
    source_header: 'Source（.srt / .ass / .ssa / .vtt 字幕）',
    no_files_selected: '暂未选择文件',
    empty_hint: '点击上方按钮或拖入文件开始',
    add_files: '添加文件',
    add_folder: '添加文件夹',
    remove_selected: '移除选中',
    clear_btn: '清空',

    // ---- 输出目录 ----
    output_header: '输出目录',
    save_to_source_dir: '保存到字幕同目录',
    output_label: '输出:',
    output_placeholder: '输出目录...',
    browse_btn: '浏览',
    open_btn: '打开',

    // ---- 净语翻译面板 ----
    refine_panel_title: '净语翻译 · 两阶段流水线（净语+翻译 → 审校+抛光）',
    stage_a_label: '阶段A 净语+翻译（日译中）',
    stage_b_label: '阶段B 审校+抛光（中文）',
    provider_zen: 'Zen 免费',
    provider_lmstudio: '本地 LM Studio',
    provider_ollama: '本地 Ollama',
    provider_siliconflow: '硅基流动',
    provider_custom: '自定义兼容接口',
    // 批2（D2026-1002-12 拍板点2）：模型下拉空态占位（JS 态键，HTML 不挂
    // 静态 data-i18n）；custom-model-1/2 硬默认键随默认语义一并删除
    model_list_empty_hint: '点击「刷新」获取模型列表',
    refresh_model_title: '在线拉取模型列表',
    test_stage_title: '测试该阶段连通性',
    test_stage_btn: '测试',
    key_placeholder: '留空用已保存密钥（LM Studio 免填）',
    save_key_title: '保存该阶段服务商的 API Key（DPAPI 加密存储）',
    profile_label: '兜底档位',
    profile_title: '本地模型选 local 清理与拦截更严格，云端强模型选 cloud 宽松以免误伤正常译文。\n技术细节：local=strict（cleaner_rules+误译拦截）；cloud=lenient（仅零维护通用校验）',
    profile_local: '本地·严格',
    profile_cloud: '云端·宽松',
    ctx_label: '上下文窗口',
    ctx_title: '模型一次能读取的文字量上限。留空即可，默认值已适配绝大多数情况；只有当翻译报错提示文字被截断或超长时，才需要把它调大。',
    ctx_placeholder: '缺省 16384',
    cleaner_dir_label: '净语配置目录',
    cleaner_dir_placeholder: '留空=自动查找（config/templates→包内默认）',
    browse_dots: '浏览...',
    templates_dir_label: '角色卡目录',
    templates_dir_placeholder: '（未设置，使用默认）',

    // ---- 翻译方向（2.1 D2026-0930-04 定案① GUI 补齐；批1 D2026-0930-07
    //      统一叙述：指令卡=角色卡，回落链 UI 明示） ----
    direction_label: '翻译方向',
    direction_block_title: '翻译方向与角色卡',
    direction_title: '缺省 日文→中文 全链零感知；切换非缺省方向（如 中文→英文）须为全部启用阶段显式指定配套模板卡（阶段A/阶段B 角色卡路径），缺卡启动即被校验拒绝',
    lang_ja: '日文',
    lang_zh: '中文',
    lang_en: '英文',
    direction_card_s1_label: '阶段A 角色卡（可选，留空=自动查找）',
    direction_card_s3_label: '阶段B 角色卡（可选，留空=自动查找）',
    direction_card_placeholder: '非缺省方向必填（.txt 路径）',
    direction_hint: '缺省日→中无需配置；切换非缺省方向须为全部启用阶段显式指定配套角色卡，缺卡启动即报错',
    direction_card_fallback_hint: '角色卡查找：显式路径优先，其次角色卡目录下同名文件，最后使用内置默认。注意：净语配置目录是另一套独立查找规则，互不关联。',

    // ---- 翻译记忆库高级 ----
    tm_enable_label: '翻译记忆库',
    tm_enable_title: '开启后翻译时可复用以往积累的译文记忆，取消后本次完全不读写记忆库，一般保持勾选。\n技术细节：取消勾选时向管线传递 --no-tm（不读取也不写入翻译记忆库）',
    tm_db_label: 'TM 库路径',
    tm_db_placeholder: '留空=使用默认 TM 库',
    tm_threshold_label: 'TM 阈值',
    tm_threshold_title: '控制复用记忆库译文的匹配严格程度，调低会更宽松、也更容易套用不贴切的旧译文，留空即用默认值，一般无需填写。\n技术细节：模糊匹配阈值 0-1（步进 0.05），越低越宽松；留空=使用管线默认',
    tm_threshold_placeholder: '默认',
    // 学习闸开关（manifest 钉定三开关之二；tm_learn_gate 默认开启，GUI 不设开关）
    glossary_learn_label: 'learned 词库自学习',
    glossary_learn_title: '开启后翻译命中将写入学习词库（默认关闭）；学习词库与手动词库分层生效，可在词库页查看',
    glossary_conflict_block_label: '冲突条目禁入 TM（默认仅观察）',

    // ---- 角色卡编辑 ----
    tpl_editor_summary: '角色卡模板编辑',
    tpl_explicit_card_hint: '若在高级参数页为当前方向指定了显式角色卡路径，以其为准；此处编辑的是角色卡目录下的同名文件。',
    tpl_stage_a: '阶段A · 角色-净语翻译.txt',
    tpl_stage_b: '阶段B · 角色-审校抛光.txt',
    tpl_reload: '重新加载',
    tpl_save: '保存角色卡',
    tpl_placeholder: '选择阶段后自动加载角色卡内容，可直接编辑后保存',
    tpl_loaded_path: p => `📄 当前加载：${p}`,
    tpl_dir_empty_hint: '⚠ 角色卡目录为空，保存将新建默认文件',
    tpl_dir_empty_datalist: '（角色卡目录为空，将使用内置默认卡）',
    // 2.6.3 批D（D2026-1003-01 P5）：角色卡编辑器模态（AppModal.editor）JS 态键
    // （HTML 零新增 data-i18n，FROZEN_I18N_KEYS 零变更）
    tplOpenEditor: '打开编辑器',
    tplEditorTitle: '角色卡编辑器',
    tplEditorDirtyConfirm: '有未保存修改，放弃并关闭？',
    tplEditorSaveOk: '已保存',
    tplEditorSaveFailed: '保存失败',

    // ---- 全局词库 ----
    gl_summary: '全局词库编辑',
    th_source: '原文词条',
    th_target: '期望译文',
    gl_add: '＋添加',
    gl_del: '删除选中',
    gl_import: '导入CSV/TXT',
    gl_export: '导出CSV',
    gl_save: '保存词库',
    gl_scope_note: '生效范围用下方"词库→阶段A/阶段B"勾选控制；绑定文件：',
    gl_path_empty: '（未加载）',
    gl_empty_hint: '词库为空：点击「＋添加」新增词条，或「导入CSV/TXT」批量导入；保存后翻译时自动生效。',

    // ---- 批量 / 开关 ----
    batch_local_label: '批量·本地',
    batch_cloud_label: '批量·云端',
    concurrency_label: '并行',
    concurrency_title: '批间并发数（1-5），默认 1',
    gl1_label: '词库→阶段A',
    gl2_label: '词库→阶段B',
    resume_label: '断点恢复（复用已完成阶段）',
    resume_title: '上次中断后重跑时，自动接着上次的进度继续，只处理没做完的部分，一般保持勾选。\n技术细节：中断后重跑时，检测到 *_manifest.json 即复用已完成阶段，仅续跑剩余阶段',
    force_resume_label: '强制断点恢复（指纹不匹配仍复用）',
    force_resume_title: '上次中断后重跑时，即使检测到改动也接着上次的进度继续，可能用到过期的中间结果。\n技术细节：覆盖清单指纹校验；会复用可能过期的阶段A产物',
    verbose_label: '详细日志',
    verbose_title: '向子进程传递 --verbose 输出调试日志',
    source_filter_label: '源侧检测',
    sf_strict: '严格',
    sf_default: '标准',
    sf_off: '关闭',
    sf_title: '翻译前自动清理原文里的乱码、复读等可疑内容。严格=清理得更多，标准=只清理明确的问题，关闭=不清理。一般保持标准即可。',
    synopsis_label: '剧情自摘要',
    synopsis_title: '剧情自摘要（Beta）：默认开启，摘要仅注入翻译提示词，不产生任何输出内容',
    adaptive_thresholds_label: '阈值自适应',
    adaptive_thresholds_title: '按字幕配套的检测数据自动微调各项检查的松紧，缺少数据时自动按默认标准执行，一般无需勾选。\n技术细节：条目级阈值自适应：需上游 Balanced 模式的 asr_telemetry.jsonl，缺失时按默认阈值执行并在风险清单标注',
    fallback_local_label: '云端故障时本地接管',
    fallback_local_title: '云端翻译失败时自动用本地模型补完失败的部分；只救云端，需先配好本地兜底模型。\n技术细节：失败行级接管重跑一次；仅对云端服务商阶段生效；未配置 --fallback-model 时启动即校验拒绝',
    fallback_model_label: '接管模型',
    // A2 兜底重绑定：空值默认项（不启用本地兜底）
    fallback_no_auto: '不自动兜底',
    refresh_local_title: '刷新本地模型列表',

    // ---- 高级设置折叠区（v1.3.2 任务2：纯 DOM 收纳，仅小标题文案键，无 JS 行为逻辑）----
    advanced_settings_notice: '以下为进阶选项，默认值已适配绝大多数使用场景，通常无需改动。',
    adv_group_translation_glossary: '翻译与词库',
    adv_group_tm_learn_gate: 'TM 与学习闸',
    adv_group_resume_logging: '断点与日志',
    adv_group_fallback_concurrency: '兜底与并发',

    // ---- 接口地址 / 启动 ----
    s1_endpoint_label: '阶段A 地址',
    s1_endpoint_placeholder: '阶段A 服务商的接口地址',
    s3_endpoint_label: '阶段B 地址',
    s3_endpoint_placeholder: '阶段B 服务商的接口地址',
    save_endpoints_btn: '保存接口配置',
    start_btn: '开始净语翻译',
    stop_btn: '停止',
    artifact_note: '产物命名含 .subtransjav 中间件与 *_final_cn.srt 终稿；已存在产物默认跳过',
    status_idle: 'Idle',

    // ---- v1.5 左侧 TAB 栏（SmartSub 式功能选择）----
    tabTranslate: '字幕翻译',
    tabReview: '校对',
    tabEngine: 'API 与模型选择',
    tabAsrDict: 'ASR 与词典',
    tabGlossary: '词库与模板',
    tabGuide: '质量与建议',
    tabAdvanced: '高级参数',

    // ---- v1.5 翻译服务快捷下拉（原小白模式顶栏迁入 translate TAB）----
    serviceQuickLabel: '翻译服务',
    serviceQuickBadge: 'AI 大模型',
    serviceQuickHintLocal: '需本机安装并启动 LM Studio（或 Ollama）并加载模型',

    // ---- 质量报告导读 ----
    guide_summary: '质量报告导读',
    guide_empty_hint: '暂无导读数据：先完成一次翻译，然后点击「加载导读」查看质量报告导读；也可直接点击「AI 分析本报告」前先加载导读。',
    guide_load_btn: '加载导读',
    guide_conclusions: '结论',
    guide_sections: '章节导读',
    guide_companions: '伴生文件',
    guide_items_title: '行动条目',

    // ---- 控制台 / 页脚 ----
    console_header: 'Console',
    clear_console: 'Clear',
    footer_brand: '净语翻译 · SubTrans Translate |',
    about_link: '关于',

    // ---- About 模态 ----
    about_title: '关于',
    about_intro: '简介',
    about_intro_text: 'SubTrans 是一款 .srt 字幕翻译与精修桌面工具，支持本地与云端双引擎推理。' +
        '自带通用角色卡与三语词典，日→中为主，可经翻译方向参数化切换中→英、英→中。' +
        '采用 v2 两阶段流水线：阶段A 净语+翻译（一次调用完成文本清洗与翻译）→ ' +
        '阶段B 审校+抛光（对照原文审核、补译、润色）。',
    feat_tm: 'TM 翻译记忆库（三层准入门槛，防止低质翻译入库）',
    feat_report: '双引擎分歧质量报告与伪影/幻觉过滤（删除台账见报告【处置】章节）',
    feat_glossary_learn: '词库自动学习（带准入门槛，防止污染词库）',
    feat_fallback: '云端故障本地接管（云端限流/宕机时自动切换本地模型）',
    feat_context_review: '双语字幕上下文预审（context_review 分歧复核工具）',
    shortcuts_title: '快捷键',
    sc_ctrl_o: 'Ctrl+O - 添加文件',
    sc_ctrl_r: 'Ctrl+R - 开始翻译',
    sc_escape: 'Escape - 取消/关闭对话框',
    sc_f1: 'F1 - 显示本对话框',
    project_home_link: 'SubTrans 项目主页',
    close_btn: '关闭',

    // ---- 动态文案收编（原表外内联中文）----
    no_files_hint: '请先在上方 Source 区添加字幕文件（支持 .srt/.ass/.ssa/.vtt）。',
    resumable_found: n => `🔄 检测到可恢复 ${n} 个（将复用已完成阶段）`,
    still_running: secs => `（仍在运行，最近活动 ${secs}s 前）`,
    risk_suffix: n => `｜风险 ${n}`,
    risk_word: '风险',
    untranslated_title: '⚠️ 整段未翻译',
    untranslated_hint: '大量条目保留了日文原文，请检查风险清单',
    level_critical: '严重风险',
    level_warning: '风险',
    completed_with_risks: (level, n) => `翻译完成，但检测到${level}（${n} 条），请检查风险清单`,
    completed_title: '翻译完成',
    completed_detail: '全部文件处理完毕，产物见输出目录。',
    confirm_reload: '翻译正在进行中。仍要刷新吗？这将终止子进程。',
    ep_deepseek_placeholder: 'DeepSeek 原生通道（无需地址）',
    ep_placeholder: '接口地址（以 /v1 结尾）',
    select_provider_first: '⚠️ 请先选择该阶段的服务商',
    loading_models: '加载中...',
    fetching_models: '拉取模型列表中...',
    // 批2（D2026-1002-12）：唯一触发源=已存值与刷新所得列表不匹配（不再有前端硬默认）
    default_model_missing: (id, cur) => `⚠️ 已保存模型 ${id} 不在当前模型列表中，已选择 ${cur}，请按需更换`,
    models_loaded: n => `✅ 模型 ${n} 个`,
    fetch_failed: '获取失败',
    testing: '测试中...',
    failed: '失败',
    alias_label: '别名: ',
    gl_saved: n => `💾 已保存 ${n} 条`,
    tpl_saved: p => `💾 已保存 ${p}`,
    gl_prompt_src: '原文词条（字幕中出现的词）：',
    gl_prompt_dst: s => `「${s}」的期望译文：`,
    gl_imported: n => `📥 导入完成：新增 ${n} 条（已自动保存）`,
    gl_exported: (n, p) => `📤 已导出 ${n} 条 -> ${p}`,
    dir_not_set: '⚠ 目录未设置，请先通过「浏览」选择目录',
    dir_opened: p => `📂 已打开目录: ${p}`,
    dir_open_failed: m => `✗ 打开目录失败: ${m}`,
    dir_open_error: e => `✗ 打开目录异常: ${e}`,
    provider_required: '⚠️ 请先选择服务商',
    lmstudio_no_key: 'LM Studio 无需密钥',
    ollama_no_key: 'Ollama 无需密钥',
    key_saved: p => `💾 密钥已加密保存（${p}）`,
    key_cleared: '🗑 已清除该服务商密钥',
    key_saved_placeholder: '已保存密钥 ✓（留空即用）',
    grammar_hint_on_title: '语法提示已启用 - 阶段A自动分析日语语法结构',
    grammar_hint_off_title: '语法提示未启用 - 安装 sudachipy 可启用',
    endpoints_saved: '💾 接口配置已保存，下次启动自动加载',
    resume_fingerprint_hint: '（修改模型或窗口/并发参数后，旧断点将不可复用）',
    no_conclusions: '（无结论）',
    no_sections: '（无章节导读）',
    no_companions: '（无伴生文件信息）',
    generated_at_label: '生成时间：',
    unknown: '未知',
    api_not_ready: '接口未就绪，请稍后再试',
    guide_need_inputs: '请先选择输入文件并指定输出目录',
    guide_loading: '加载中…',
    guide_loaded: p => `已加载：${p}`,
    guide_load_failed: m => `加载失败：${m}`,
    guide_open_other_btn: '打开其他质量报告导读',
    guide_txt_loaded: p => `已加载报告全文（只读）：${p}`,
    guide_txt_truncated_note: '（报告过长，仅显示前 100 万字符）',
    gl_learned_title: '学习词库',
    gl_learned_reload: '刷新',
    gl_learned_col_aliases: '别名',
    gl_learned_note: '自学习写入，优先级低于全局词库。',
    gl_learned_empty: '尚无学习词库：完成一次翻译后引擎自动学习写入，届时点击「刷新」查看。',
    gl_learned_stats: (n, t) => `共 ${n} 条${n !== t ? `（总计 ${t} 条，仅显示前 ${n} 条）` : ''}`,
    gl_learned_more: n => `…其余 ${n} 条未显示`,
    gl_learned_load_failed: m => `学习词库加载失败：${m}`,
    guide_items_none: '行动条目：0',
    guide_item_current_label: '现译: ',
    guide_item_unresolvable: '不可自动重翻',
    guide_items_more: n => `…其余 ${n} 条见 json`,

    // ---- AI 质量分析（D2026-0929 前后端接入）----
    aiAnalyzeBtn: 'AI 分析本报告',
    aiAnalyzing: '分析中（可能需要 1-3 分钟）…',
    aiNeedGuide: '请先加载质量报告导读',
    aiPrivacyCloud: p => `⚠️ 分析内容（含字幕译文）将发送至 ${p}`,
    aiPrivacyLocal: '本地模型分析，内容不出本机',
    aiSectionGlossary: '术语建议',
    aiSectionTm: 'TM 建议',
    aiSectionObs: '一般观察',
    aiThReason: '理由',
    aiApplyGlossary: '加入词库',
    aiApplyTm: '存入 TM',
    aiApplied: '已加入 ✓',
    aiTmStored: '已存入 ✓',
    aiExists: '已存在',
    aiExistsDiff: '译法不一致',
    aiLocked: '锁定（他方持锁）',
    aiApplyRetry: '重试',
    aiApplyFailed: m => `落库失败：${m}`,
    aiConflictWarn: '该词存在未裁决术语冲突，请确认',
    aiParseFailed: '⚠️ AI 输出解析失败，以下为原始观察文本',
    aiDone: 'AI 分析完成，建议仅供人工裁决',
    aiFailed: m => `AI 分析失败：${m}`,
    gui_initialized: '净语翻译 GUI 已初始化',
    gui_usage_hint: '在上方 Source 区添加字幕后点击「开始净语翻译」',

    // ---- 快速试听 / 媒体来源（D2026-0929-09 视听对比第二阶段）----
    preview_play_btn: '试听',

    // ---- 文件列表三态 chip / 流水线镜像（D2026-0930-09 批2）----
    chip_pending: '等待中',
    chip_running: '翻译中',
    chip_done: '已完成',
    chip_resumable: '可续传',
    pipeline_mirror_model: '阶段A 模型',
    pipeline_mirror_conc: '并行',
    pipeline_card_hint: '点击前往「API 与模型选择」页修改',

    // ---- 右栏系统状态摘要卡（D2026-1001 批3；strings.py 特批 2 键镜像 + JS-only 标签）----
    sys_summary_title: '系统状态',
    sys_summary_unavailable: '不可用',
    sys_summary_version: '版本',
    // 批3 扩展（D2026-1002-12）：角色卡行 + ASR 行动态渲染所需键（全 JS 态，
    // 零静态 i18n 消耗；角色卡标签复用 templates_dir_label，ASR 行用短标签
    // sys_asr_row_label 防溢出，全称经行级 title 悬停呈现——D2026-1004-01 段2 追回）
    sys_roles_count: n => `${n} 张`,
    sys_roles_fallback: '内置回落',
    sys_asr_row_label: 'ASR 模型',
    sys_asr_undetected: '未探测',
    sys_asr_unconfigured: '未配置',
    sys_asr_ready: m => `就绪 · ${m}`,
    media_source_label: '媒体来源',
    media_source_auto: '自动发现',
    media_source_explicit: '显式指定',
    media_source_none: '（导读未包含媒体路径）',
    media_source_change_btn: '更换',
    media_override_apply: '应用',
    media_override_placeholder: '输入媒体文件完整路径（等价 --media-path，仅本报告会话内生效）',
    media_override_applied: '已设为本报告会话内媒体来源（显式指定）',
    media_override_cleared: '已清除覆盖，恢复导读自动发现来源',
    audio_preview_close: '关闭',
    audio_preview_failed: m => `试听失败：${m}`,
    audio_preview_no_timing: '该条目缺少可解析时间轴，无法试听',
    audio_preview_no_guide: '请先加载质量报告导读',

    // ---- 数据保存目录（高级参数页；pointer 写入 .data-root，重启生效）----
    data_root_title: '数据保存目录',
    data_root_current_label: '当前',
    data_root_source_env: '环境变量指定',
    data_root_source_pointer: '自定义目录',
    data_root_source_frozen_default: '打包默认',
    data_root_source_legacy: '仓库根传统',
    data_root_change_btn: '浏览…',
    data_root_restore_btn: '恢复默认',
    data_root_unchanged: '目录未变化',
    data_root_saved_restart: '已保存，重启应用后生效',
    data_root_default_restored: '已恢复默认，重启应用后生效',
    data_root_need_abs: '请输入绝对路径',
    // 数据根变更阻断式提示（批1a 件5；仅 JS 侧消费，不入 strings.py）
    data_root_restart_title: '数据目录已变更',
    data_root_restart_body: '须重启应用后生效。重启前的后续写入仍会落到旧数据目录，建议确认后尽快重启。',

    // 词典管理（引擎页三区块，2.1）
    dict_panel_title: '词典管理（日/中/英）',
    dict_sudachi_label: '日语（sudachi）',
    dict_sudachi_desc: '日语形态素分析词典（语法提示分词用；默认不随安装包附带，点下方按钮下载，SHA256 校验三源）',
    dict_jieba_label: '中文（jieba）',
    dict_jieba_desc: '中文分词（安装包已内置并自动启用；仅源码方式运行需自备 [zh] 组件，缺失时自动降级）',
    dict_english_label: '英文（规则级）',
    dict_english_desc: '英文分词规则级（内置，无需下载）',
    dict_status_available: '可用',
    dict_status_unavailable: '不可用',
    dict_custom_path: '自定义词典已就位',
    dict_download: '下载',
    dict_downloading: '下载中…',
    dict_verify: '校验中…',
    dict_extract: '解压中…',
    dict_download_done: '下载完成',
    dict_download_failed: '下载失败',
    dict_load_failed: '词典状态加载失败',
    // 词典管理 B2 案（批3 解冻键 6 个）：空态引导/CTA 已随 2.6.5 段2
    // （D2026-1004-01 #4）删除——空态语义由下方新 JS 态键承接（零静态
    // data-i18n 消耗，R6 快照只收 HTML 静态键）
    dict_select_label: '选择词典查看详情',
    dict_status_builtin: '内置',
    dict_open_dir: '打开文件夹',
    dict_redownload: '重新下载',
    // 2.6.5 段2（D2026-1004-01 #4/#5/#6）新 JS 态键：pill 未安装专用态/
    // hint 条/四 kind chip/收单操作行前缀/失败人话映射/诊断网格字段标签
    // （全 JS 态填充，禁 index.html 静态中文）
    dict_status_not_installed: '未安装',
    dict_install_hint: '该词典未安装——下载后语法提示可用',
    dict_sudachi_full_chip_title: '与日语二选一',
    dict_download_source: '下载源',
    dict_fail_checksum: '文件校验不符，下载不完整或源文件异常',
    dict_fail_network: '网络不可达或代理拦截（已尝试直连重试）',
    dict_diag_summary: '技术详情',
    dict_diag_copy: '复制',
    dict_diag_selected: '已全选',
    dict_diag_expected_bytes: '预期字节',
    dict_diag_actual_bytes: '实际字节',
    dict_diag_encoding: 'Content-Encoding',
    dict_diag_part_hex: '响应前缀(.part 前64B)',
    dict_diag_url: '来源 URL',
    dict_diag_proxy: '代理',
    dict_diag_proxy_system: '系统代理',
    dict_diag_proxy_direct: '直连',
    dict_diag_attempts: '尝试次数',
    // 批1b 件1/件2（D2026-1002-12）：词典目录设置 + 一键迁移（JS 态键，
    // 不静态落 data-i18n——R6，静态键快照零消耗）
    dict_migrate_btn: '迁移旧词典',
    dict_migrate_title: '迁移旧词典',
    dict_migrate_confirm: (src, n) => `在旧目录\n${src}\n发现 ${n} 个词典文件。将复制到新目录后生效（源文件保留，同名同大小自动跳过）。确认迁移吗？`,
    dict_migrating: '迁移中…',
    dict_migrate_done: (n, skipped) => `迁移完成：复制 ${n} 个文件${skipped ? `，跳过 ${skipped} 个（同大小已存在）` : ''}`,
    dict_migrate_failed: '迁移失败',
    dict_dir_set_ok: '词典目录已更改，新下载的词典将保存到所选目录',
    dict_dir_restored: '已恢复默认词典目录（原目录文件保留，可重新下载或迁移）',
    // 批1b 件4：首启数据目录引导（frozen-only，哨兵防再弹）
    data_guide_title: '数据保存目录',
    data_guide_body: dir => `当前：${dir}\n\n数据目录存放翻译记忆库、词典、角色卡等，可随时在 高级参数 页更改。\n\n「选择其他目录」可更改保存位置；「使用当前目录」保持现状。`,
    data_guide_pick: '选择其他目录...',
    data_guide_keep: '使用当前目录',

    // 控制台折叠
    console_collapse: '折叠控制台',
    console_expand: '展开控制台',
    // 词库页区块折叠按钮（2.1.1 owner 痛点批：单键双向文案，展开/折叠态通用）
    collapse_toggle: '折叠/展开',
    // 2.4.0 批1/批2（JS 态键，不入 data-i18n 快照）：自制模态按钮 + 首启引导
    ui_ok: '确定',
    ui_cancel: '取消',
    // 2.6.3 批B：AppModal.download 复制轻提示（clipboard 不可用时降级 title 提示）
    ui_copied: '已复制',
    ui_copy_manual: '无法自动复制，请长按/手动选择复制',
    first_run_guide: '首次使用：点击「添加文件」导入字幕（支持 .srt/.ass/.ssa/.vtt），或直接拖入文件开始翻译。',
    // 2.5.0 修复批（JS 态键）：词典 full 变体/云分析确认/角色卡跳转与回落提示
    dict_sudachi_full_label: '日语词典·完整版（sudachi full）',
    dict_sudachi_full_desc: '完整版词典数据（语法提示分词用，与 core 版二选一即可；官方 CDN 单源直链，点下方按钮下载）',
    aiCloudConfirm: p => `当前使用的服务商为「${p}」（云端），质量报告内容将发送至云端进行 AI 分析。确认继续吗？`,
    ai_model_placeholder: '留空=使用阶段A 当前模型',
    ai_cfg_provider_label: '分析服务商',
    ai_cfg_model_label: '分析模型',
    ai_prov_follow: '跟随阶段A（默认）',
    ai_prov_lmstudio: 'LM Studio（本地）',
    ai_prov_ollama: 'Ollama（本地）',
    ai_prov_deepseek: 'DeepSeek API',
    ai_prov_siliconflow: '硅基流动',
    ai_prov_zen: 'Zen 免费',
    // 2.6.0 批1（D2026-1002-02-批1）：质量闭环一键批次修复。
    // batchFixBtn 为静态 data-i18n 键（HTML+MSG 表+钉⑤快照三处同步）；
    // 其余为 JS 态键（不入 data-i18n 快照，受反向悬空钉保护）
    batchFixBtn: '一键修复建议',
    batchFixConfirmTitle: '确认执行批量修复？',
    batchFixPreviewHead: '将修复以下条目：',
    batchFixPreviewMore: n => `…其余 ${n} 条省略`,
    batchFixEstimate: n => `预估调用：翻译 ${n} 次 + 复验全片 AI 分析 1 次`,
    batchFixProvider: p => `修复服务商：${p}`,
    batchFixCats: c => `分类明细：${c}`,
    batchFixCloudCost: '当前修复服务商为云端（按量计费）；发送内容为字幕文本与词条上下文，不含音视频。',
    batchFixCapHit: (n, total) => `待修共 ${total} 条，单批上限 50：本次修前 ${n} 条（按序），确认后可再次发起处理余量`,
    batchFixNoItems: '当前导读没有可自动修复的待修条目（或均已修过）',
    batchFixNeedGuide: '请先加载质量报告导读',
    batchFixRunning: (done, total) => `批量修复中… ${done}/${total}`,
    batchFixRunningPlain: '批量修复中…（执行器逐条处理，完成后回显结果）',
    batchFixDone: (a, f) => `批量修复完成：成功 ${a} 条` + (f ? `，失败 ${f} 条` : ''),
    batchFixFail: '批量修复失败',
    batchFixVerifying: '复验中：重跑全片 AI 分析…',
    batchFixVerifyFail: '；复验失败（修复前建议已保留，可手动重跑 AI 分析）',
    batchFixVerifyDelta: d => `；复验建议差 Δ${d >= 0 ? '+' : ''}${d}`,
    batchFixSourcePartial: '；部分条目按导读摘录对齐（未提供原始源文）',
    batchFixScopeAll: '全部待修条目',
    batchFixScopeCat: (c, n) => `${c}（${n} 条）`,
    // 2.6.0 批3（D2026-1002-04-批3）：ASR 模型管理（媒体重点对照，音频零出域）。
    // asr_panel_title 为静态 data-i18n 键（HTML+MSG+钉⑤三处同步）；其余 JS 态
    asr_panel_title: 'ASR 模型（媒体重点对照）',
    asrRefreshBtn: '重新探测',
    asrProbeReady: (ver, m) => `上游 ASR 就绪（whisper ${ver}｜模型缓存 ${m}）`,
    asrProbeNoModel: '模型缓存缺失（可自备推荐模型）',
    asrProbeFail: e => `上游 ASR 不可用：${e}`,
    // 2.7.1（D2026-1005-01 承接批）：红绿灯🟡档文案（上游通但缺模型/缺 ffmpeg）
    asrProbeUpstreamOk: '上游环境可达；模型或 ffmpeg 有缺口——打开「模型管理」查看/补齐',
    asrSelectPlaceholder: '选择 ASR 模型（媒体重点对照用）',
    asrSaved: '已保存 ASR 模型选择',
    // 批2（D2026-1002-12 拍板点1）：ASR 卡重整空态/说明文案（JS 态零静态键）
    asr_env_undetected: '未探测——点击「重新探测」检测本机 ASR 环境',
    asrCrosscheckNote: n => `；本地转写 ${n} 段对照`,
    // 2.6.1 修订（D2026-1002-06，模型推荐制）；2.7.1：入口说明独立行删除
    // （asr_entry 系提示并入开关 title 悬停，asrCrosscheckTitle）
    asrCrosscheckLabel: '启用媒体重点对照（本地切片重转写验证）',
    asrCrosscheckTitle: '用于翻译完成后对媒体切片做本地重转写重点对照；须自备上游 Python 环境，未配置不影响正常翻译。',
    asrPythonPlaceholder: '上游环境 Python 路径（如 D:\\whisperJAV\\python.exe）',
    // 2.7.1 模型管理面板（D2026-1005-01 承接批，AppModal kind='models'；
    // 全 JS 态键不受静态 cap 200 约束，由 test_gui_js_static 定向断言守护）
    asrModelsBtn: '模型管理',
    mpTitle: 'ASR 模型管理',
    mpPathWhisper: 'Whisper 默认缓存',
    mpPathData: '应用模型目录',
    mpOpenDir: '打开文件夹',
    mpUnadaptedBanner: n => `检测到 ${n} 个 HF hub 模型尚未适配当前后端（CT2/transformers 布局）；适配器上线（2.8.0）后此处可直接选用。`,
    mpTierFast: '快速档 · 内存 ≤2GB',
    mpTierBalanced: '均衡档',
    mpTierPrecise: '高精档 · 内存 ≥8GB',
    mpSpeedLabel: '速度',
    mpPrecisionLabel: '精度',
    mpSpecNote: '推荐参考：静态评定，非实测',
    mpStateReady: '可用',
    mpStateAdapter: '需适配',
    mpStatePlanned: '规划中',
    mpUnverifiedTitle: '下载元数据未核验：请自备落位（2.7.2 逐档开放下载）',
    mpAdapterTitle: '后端未适配（仅展示）',
    mpPlannedTitle: '规划中（2.9.0 适配器上线后可用）',
    mpVariantsLabel: '变体',
    mpNeedProbe: '暂无探测结果——请先点击「重新探测」',
    // 2.6.3 批B（D2026-1003-01 ②/D2026-1003-06 五条件）：ASR 下载器 + 词典
    // 源选择（全 JS 态键，零静态 i18n 消耗；index.html 冻结期 body 全 createElement）
    // 2.7.1：下载标题/元信息行键随旧源选择模态链删除
    // （面板下载行内化）；asrDlStart/asrDlDone/asrDlFailed/asrDlNoCancel 为
    // AppModal.download 方法体内引用+定向钉，保留
    asrDownloadBtn: '下载…',
    asrDlStart: '开始下载',
    asrDlDone: '下载完成',
    asrDlFailed: '下载失败',
    srcOfficialLabel: '官方源',
    srcMirrorLabel: '国内加速源',
    srcMirrorPendingHint: '需实测下载比对验证后才能启用，当前版本不可用',
    dictSrcOfficialOnly: '仅官方',
    dictSrcMirrorOnly: '仅镜像',
    dictSrcOfficialHint: 'pythonhosted 官方源在中国大陆常不可达，失败请用「下载」（自动源）',
    dictSrcMirrorlessHint: '该词典暂无镜像源（官方 CDN 单源）；可用 CLI --dict-from-file 离线导入',
    dictFallbackNotice: '官方源不可达，已回退镜像源',
    // 2.6.0 批2 修订（D2026-1002-05）：跨片统计窗口三档
    aggregateWindowLabel: '跨片窗口',
    aggregateWindow7: '7 天',
    aggregateWindow30: '30 天',
    aggregateWindowAll: '全部（永久）',
    batchFixScopeLabel: '修复范围',
    tpl_goto_edit: '去编辑',
    tpl_goto_empty_hint: '该阶段角色卡未显式指定（留空=自动查找回落链）；编辑器仅支持角色卡目录内顶层文件',
    tpl_goto_outside_hint: '显式卡在角色卡目录外，编辑器仅支持目录内文件；已在下方定位角色卡目录',
    tpl_save_hint_explicit: '（显式卡路径指向同名文件，保存后自动生效）',
    tpl_save_hint_auto: '（角色卡输入留空=自动查找回落链）',
    // 2.6.4 批1（D2026-1003-05 策略 B）：词库页 TM 只读搜索区块
    // （全 JS 态键零静态 i18n 消耗；零静态 id——FROZEN_IDS 冻结，
    // 区块全 createElement 注入，对齐 dict-src 双按钮先例）
    tmSearchTitle: '翻译记忆库搜索',
    tmSearchPlaceholder: '输入原文或译文关键词/整句，回车或点「搜索」',
    tmSearchBtn: '搜索',
    tmSearchRunning: '搜索中…',
    tmSearchFailed: '搜索失败',
    tmSearchCount: n => `${n} 条结果`,
    tmSearchEmpty: '没有匹配的翻译记忆条目',
    tmSearchColSource: '原文',
    tmSearchColTarget: '译文',
    tmSearchColStage: '阶段',
    tmSearchColHits: '命中',
};

// i18n 注入：DOMContentLoaded 时把 MSG 写回带 data-i18n* 标记的元素
function applyI18n() {
    document.querySelectorAll('[data-i18n]').forEach(el => {
        const v = MSG[el.dataset.i18n];
        if (typeof v === 'string') el.textContent = v;
    });
    document.querySelectorAll('[data-i18n-title]').forEach(el => {
        const v = MSG[el.dataset.i18nTitle];
        if (typeof v === 'string') el.setAttribute('title', v);
    });
    document.querySelectorAll('[data-i18n-placeholder]').forEach(el => {
        const v = MSG[el.dataset.i18nPlaceholder];
        if (typeof v === 'string') el.setAttribute('placeholder', v);
    });
}

// ============================================================
// State Management
// ============================================================
const AppState = {
    // File list
    selectedFiles: [],
    selectedIndices: new Set(),

    // UI state
    isRunning: false,

    // Default output directory
    outputDir: '',
    _fallbackOutputDir: '',

    async init() {
        await this.loadDefaultOutputDir();
    },

    async loadDefaultOutputDir() {
        try {
            const defaultDir = await pywebview.api.get_default_output_dir();
            this._fallbackOutputDir = defaultDir;

            const sourceCheckbox = document.getElementById('outputToSource');
            if (sourceCheckbox && sourceCheckbox.checked) {
                this.outputDir = 'source';
                document.getElementById('outputDir').value = 'source';
                document.getElementById('outputDir').disabled = true;
                document.getElementById('browseOutputBtn').disabled = true;
            } else {
                this.outputDir = defaultDir;
                document.getElementById('outputDir').value = defaultDir;
            }
        } catch (error) {
            console.error('Failed to load default output directory:', error);
            this._fallbackOutputDir = '';
            this.outputDir = 'source';
            document.getElementById('outputDir').value = 'source';
            ConsoleManager.log(MSG.usingSourceOutput, 'warning');
        }
    }
};

// ============================================================
// UI Helpers - Loading States
// ============================================================
const UIHelpers = {
    showLoadingState(button, isLoading) {
        button.disabled = isLoading ? true : false;
        button.classList.toggle('loading', isLoading);
    },

    showError(title, message) {
        ErrorHandler.show(title, message);
    },

    showSuccess(title, message) {
        ErrorHandler.showSuccess(title, message);
    }
};

// ============================================================
// App Modal（2.4.0 批1 S1）：原生 alert/confirm/prompt 的宿主无关自制模态
// （prompt 在部分 WebView 宿主返回 null——行为与宿主解耦；Promise 永不 reject）
// ============================================================
const AppModal = {
    _busy: false,        // 硬性条款①：打开中守卫——单例，防 F5 连按/glAdd 双击叠加
    _kind: null,
    _resolve: null,
    _dlRunning: false,   // 2.6.3 批B：download 模态下载进行中（onStart Promise 未 settle）
    _edDirty: false,     // 2.6.3 批D：编辑器有未保存修改（textarea input 置位）
    _edSaving: false,    // 批D：保存进行中（onSave Promise 未 settle，禁止关闭）
    _edConfirming: false,// 批D：放弃确认弹窗进行中（防守卫递归）
    _edOpts: null,       // 批D：editor(opts) 暂存（onSave/onStageChange/onDiscard/onClose）

    _settle(value) {
        if (!this._busy) return;
        // 2.6.3 批B：下载进行中 ESC/遮罩点击/取消键全部 no-op（无取消语义，
        // 评议员条件①；完成/失败后 _dlRunning 复位，关闭键恢复可用）。
        // 2.7.1 评议 C3：该 no-op 分支仅命中 download kind——models kind
        // 不复用 _dlRunning 布尔，关闭永不阻塞（下载后台继续）。
        if (this._kind === 'download' && this._dlRunning) return;
        // 2.6.3 批D：编辑器保存进行中禁止关闭（同 _dlRunning 先例）；
        // 有未保存修改先走放弃确认守卫（确认后经 _settle 正式结算）
        if (this._kind === 'editor' && this._edSaving) return;
        if (this._kind === 'editor' && this._edDirty && !this._edConfirming) {
            this._editorDiscardGuard();
            return;
        }
        this._busy = false;
        this._kind = null;
        const resolve = this._resolve;
        this._resolve = null;
        const root = document.getElementById('appModal');
        if (root) root.style.display = 'none';
        if (resolve) resolve(value);
    },

    _cancelValue() { return AppModal._kind === 'prompt' ? null : false; },

    _open(kind, title, body, def, opts) {
        if (this._busy) {
            // 重入：单例不叠加——在途调用方仍持原 Promise，新调用立即按取消结算
            return Promise.resolve(kind === 'prompt' ? null : false);
        }
        const root = document.getElementById('appModal');
        if (!root) {
            // 骨架缺席兜底：退回原生对话框（永不 reject）
            if (kind === 'alert') { window.alert(`${title}\n\n${body}`); return Promise.resolve(undefined); }
            if (kind === 'confirm') { return Promise.resolve(window.confirm(`${title}\n\n${body}`)); }
            return Promise.resolve(window.prompt(`${title}`, def || ''));
        }
        root.querySelector('.modal-title').textContent = title || '';
        root.querySelector('.modal-body').textContent = body || '';
        const input = root.querySelector('.modal-input');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        // 批1b 件4：confirm 支持自定义双键文案（opts.okText/cancelText，
        // 缺省回退 ui_ok/ui_cancel——既有调用点行为零变化）
        cancelBtn.textContent = (opts && opts.cancelText) || MSG.ui_cancel;
        okBtn.textContent = (opts && opts.okText) || MSG.ui_ok;
        cancelBtn.style.display = kind === 'alert' ? 'none' : '';   // 硬性条款②：alert 无取消键
        input.style.display = kind === 'prompt' ? '' : 'none';
        input.value = kind === 'prompt' ? (def || '') : '';
        if (!root.dataset.bound) {          // 静态 DOM 一次性绑定
            root.dataset.bound = '1';
            root.addEventListener('click', (e) => {
                if (e.target === root) AppModal._settle(AppModal._cancelValue());   // 遮罩取消
            });
            okBtn.addEventListener('click', () => {
                AppModal._settle(AppModal._kind === 'prompt' ? input.value : true);
            });
            cancelBtn.addEventListener('click', () => AppModal._settle(AppModal._cancelValue()));
            document.addEventListener('keydown', (e) => {
                if (!AppModal._busy) return;
                if (e.key === 'Escape') {
                    e.preventDefault();
                    AppModal._settle(AppModal._cancelValue());
                } else if (e.key === 'Enter' && AppModal._kind !== 'alert' && AppModal._kind !== 'editor') {
                    e.preventDefault();
                    AppModal._settle(AppModal._kind === 'prompt' ? input.value : true);
                }
            });
        }
        this._busy = true;
        this._kind = kind;
        root.style.display = 'flex';        // 等效 .modal-overlay.active（inline 覆盖基类 display:none）
        (kind === 'prompt' ? input : okBtn).focus();   // focus 管理：prompt 聚输入框，其余聚确认键
        if (kind === 'prompt' && input.value) input.select();
        return new Promise((resolve) => { this._resolve = resolve; });
    },

    alert(title, body) { return this._open('alert', title, body); },
    confirm(title, body, opts) { return this._open('confirm', title, body, undefined, opts); },
    prompt(title, body, def) { return this._open('prompt', title, body, def); },

    // ============================================================
    // download 模态（2.6.3 批B，D2026-1003-01 ②）：源单选卡+meta 行+无取消
    // 声明+全宽开始键+进度区一体化。复用 #appModal 骨架（title/关闭键），
    // body 内容全 createElement 注入（FROZEN_IDS 冻结：零新增 id/data-i18n）。
    // 不走 _open 三分支（alert/confirm/prompt 行为零变化），但复用其
    // dataset.bound 一次性监听绑定（遮罩/取消/ESC→_settle，_settle 内
    // _dlRunning 守卫承载"下载中 no-op"）。
    // opts = {title, sources:[{key,label,hint,disabled}],
    //         meta:[{label,value,copyable}], notice,
    //         onStart(sourceKey, update)->Promise<{ok,message}>, onClose?}
    // update(snap) 为进度区渲染回调（snap={phase,downloaded,total,note}）。
    // ============================================================
    download(opts) {
        if (this._busy) return Promise.resolve(false);      // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        const o = opts || {};
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = o.title || '';
        body.textContent = '';
        body.style.whiteSpace = 'normal';   // .modal-card .modal-body 默认 pre-wrap，布局需正常折行
        input.style.display = 'none';
        okBtn.style.display = 'none';       // download 只留关闭键（确认语义由开始键承载）
        okBtn.textContent = '';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        if (!root.dataset.bound) {          // 与 _open 同款一次性绑定（首个打开的可能是本模态）
            root.dataset.bound = '1';
            root.addEventListener('click', (e) => {
                if (e.target === root) AppModal._settle(AppModal._cancelValue());
            });
            cancelBtn.addEventListener('click', () => AppModal._settle(AppModal._cancelValue()));
            document.addEventListener('keydown', (e) => {
                if (!AppModal._busy) return;
                if (e.key === 'Escape') {
                    e.preventDefault();
                    AppModal._settle(AppModal._cancelValue());
                } else if (e.key === 'Enter' && AppModal._kind !== 'alert' && AppModal._kind !== 'editor') {
                    e.preventDefault();
                    AppModal._settle(AppModal._kind === 'prompt' ? input.value : true);
                }
            });
        }

        // —— 源单选卡（label+radio；disabled 卡灰态，radio 默认选第一个非禁用）——
        const sources = o.sources || [];
        const srcBox = document.createElement('div');
        srcBox.className = 'dl-src-list';
        const radios = [];
        sources.forEach((s) => {
            const card = document.createElement('label');
            card.className = 'dl-src-card' + (s.disabled ? ' dl-src-disabled' : '');
            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = 'dl-src-choice';
            radio.value = String(s.key || '');
            if (s.disabled) radio.disabled = true;
            const txt = document.createElement('span');
            txt.className = 'dl-src-label';
            txt.textContent = s.label || s.key || '';
            card.appendChild(radio);
            card.appendChild(txt);
            if (s.hint) {
                const hint = document.createElement('span');
                hint.className = 'dl-src-hint muted';
                hint.textContent = s.hint;
                card.appendChild(hint);
            }
            radio.addEventListener('change', () => {
                radios.forEach((r) => r.closest('.dl-src-card')
                  .classList.toggle('dl-src-selected', r.checked));
            });
            srcBox.appendChild(card);
            radios.push(radio);
        });
        body.appendChild(srcBox);
        const firstEnabled = radios.find((r) => !r.disabled);
        if (firstEnabled) {
            firstEnabled.checked = true;
            firstEnabled.closest('.dl-src-card').classList.add('dl-src-selected');
        }

        // —— meta 行表（copyable 行点击复制+「已复制」轻提示）——
        (o.meta || []).forEach((m) => {
            const row = document.createElement('div');
            row.className = 'dl-meta-row';
            const lab = document.createElement('span');
            lab.className = 'dl-meta-label';
            lab.textContent = (m.label || '') + (m.label ? '：' : '');
            const val = document.createElement('span');
            val.textContent = m.value == null ? '' : String(m.value);
            row.appendChild(lab);
            row.appendChild(val);
            if (m.copyable && m.value) {
                val.className = 'dl-copyable';
                val.title = String(m.value);
                val.addEventListener('click', () => {
                    if (!navigator.clipboard || !navigator.clipboard.writeText) {
                        val.title = MSG.ui_copy_manual;     // clipboard 不可用：title 提示手动复制
                        return;
                    }
                    navigator.clipboard.writeText(String(m.value)).then(() => {
                        val.textContent = MSG.ui_copied;
                        setTimeout(() => { val.textContent = String(m.value); }, 1200);
                    }).catch(() => { val.title = MSG.ui_copy_manual; });
                });
            }
            body.appendChild(row);
        });

        // —— 无取消声明（无取消语义成文）——
        if (o.notice) {
            const note = document.createElement('div');
            note.className = 'dl-notice muted';
            note.textContent = o.notice;
            body.appendChild(note);
        }

        // —— 全宽开始键 + 进度区（bar/fill/text 三件套，class 独立 .dl-progress-*）+ 结果行 ——
        const startBtn = document.createElement('button');
        startBtn.type = 'button';
        startBtn.className = 'btn btn-primary modal-dl-start';
        startBtn.textContent = MSG.asrDlStart;
        if (!firstEnabled) startBtn.disabled = true;        // 全 disabled → 开始禁用
        body.appendChild(startBtn);
        const prog = document.createElement('div');
        prog.className = 'dl-progress';
        prog.style.display = 'none';
        const bar = document.createElement('div');
        bar.className = 'dl-progress-bar';
        const fill = document.createElement('div');
        fill.className = 'dl-progress-fill';
        bar.appendChild(fill);
        const text = document.createElement('div');
        text.className = 'dl-progress-text';
        prog.appendChild(bar);
        prog.appendChild(text);
        body.appendChild(prog);
        const result = document.createElement('div');
        result.className = 'dl-result';
        result.style.display = 'none';
        body.appendChild(result);
        const fmtMB = (n) => (n / 1048576).toFixed(1);

        startBtn.addEventListener('click', () => {
            if (this._dlRunning) return;
            const sel = radios.find((r) => r.checked && !r.disabled);
            if (!sel || typeof o.onStart !== 'function') return;
            this._dlRunning = true;
            startBtn.disabled = true;
            cancelBtn.disabled = true;      // 下载中关闭键不可用（完成/失败后恢复）
            prog.style.display = '';
            fill.style.width = '';
            bar.classList.add('indeterminate');
            text.textContent = '';
            result.style.display = 'none';
            let poller = null;
            const stopPoll = () => { if (poller) { clearInterval(poller); poller = null; } };
            const render = (snap) => {
                snap = snap || {};
                if (snap.phase === 'download' && snap.total) {
                    bar.classList.remove('indeterminate');
                    fill.style.width =
                      Math.min(100, Math.round((snap.downloaded || 0) / snap.total * 100)) + '%';
                    text.textContent = `${fmtMB(snap.downloaded || 0)}/${fmtMB(snap.total)}MB`;
                } else {
                    fill.style.width = '';
                    bar.classList.add('indeterminate');
                    text.textContent = snap.phase === 'verify' ? MSG.dict_verify
                      : MSG.dict_downloading;
                }
                if (snap.note) text.textContent += '｜' + snap.note;   // 回退可见提示（条件①）
            };
            Promise.resolve()
              .then(() => o.onStart(sel.value, render))
              .then((res) => {
                  stopPoll();
                  this._dlRunning = false;
                  prog.style.display = 'none';
                  const ok = !!(res && res.ok);
                  result.style.display = '';
                  result.className = 'dl-result ' + (ok ? 'dl-result-ok' : 'dl-result-err');
                  result.textContent = (ok ? MSG.asrDlDone : MSG.asrDlFailed)
                    + '：' + ((res && res.message) || '');
                  cancelBtn.disabled = false;   // 关闭键恢复可用
              })
              .catch((e) => {
                  stopPoll();
                  this._dlRunning = false;
                  prog.style.display = 'none';
                  result.style.display = '';
                  result.className = 'dl-result dl-result-err';
                  result.textContent = MSG.asrDlFailed + '：'
                    + (e && e.message ? e.message : String(e));
                  cancelBtn.disabled = false;
              });
        });

        // 收口：关闭时恢复骨架默认态（_open 不重置 okBtn.display/whiteSpace，
        // download 自清理防污染后续 alert/confirm/prompt）
        const closeResolve = () => {
            okBtn.style.display = '';
            body.style.whiteSpace = '';
            if (typeof o.onClose === 'function') o.onClose();
        };
        this._busy = true;
        this._kind = 'download';
        this._dlRunning = false;
        root.style.display = 'flex';
        startBtn.focus();
        return new Promise((resolve) => {
            this._resolve = (value) => { closeResolve(); resolve(value); };
        });
    },

    // ============================================================
    // 编辑器模态（2.6.3 批D，D2026-1003-01 P5）：角色卡编辑器整体迁入。
    // 节点搬迁模式：vault（.tpl-editor-vault，hidden 常驻）内既有节点按
    // 原序 appendChild 进 modal-body（textarea 包一层 .editor-ta-wrap
    // 弹性层），关闭/确认放弃时逐个 append 回 vault——appendChild 即复位，
    // 幂等可逆（FROZEN_IDS 零变更：vault 与其内 id/data-i18n 全部原样）。
    // 复用 dataset.bound 一次性监听（遮罩/取消/ESC→_settle）；modal-card
    // 打开加 .modal-lg、body 加 .modal-editor-body，关闭自清理（download
    // 同款自管 body 模式，防污染后续 alert/confirm/prompt）。
    // dirty 守卫：textarea input 置 _edDirty；_settle 编辑器分支——有未
    // 保存修改先经 AppModal.confirm 确认（confirm 与编辑器共用单例骨架：
    // 先收起编辑器——节点搬回 vault 保状态+_busy=false——再弹确认）。
    // opts = {title, onSave(stage, text)->Promise<{ok,message}>,
    //         onStageChange(stage, mode)->Promise, onDiscard?, onClose?}
    // ============================================================
    editor(opts) {
        if (this._busy) return Promise.resolve(false);      // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        if (!document.querySelector('.tpl-editor-vault')) return Promise.resolve(false);
        const o = opts || {};
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = o.title || MSG.tplEditorTitle;
        body.textContent = '';
        body.style.whiteSpace = 'normal';   // .modal-card .modal-body 默认 pre-wrap
        body.classList.add('modal-editor-body');
        const card = root.querySelector('.modal-card');
        if (card) card.classList.add('modal-lg');
        input.style.display = 'none';
        okBtn.style.display = 'none';       // 确认语义由 vault 内保存键承载
        okBtn.textContent = '';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        if (!root.dataset.bound) {          // 与 _open 同款一次性绑定（首个打开的可能是本模态）
            root.dataset.bound = '1';
            root.addEventListener('click', (e) => {
                if (e.target === root) AppModal._settle(AppModal._cancelValue());
            });
            cancelBtn.addEventListener('click', () => AppModal._settle(AppModal._cancelValue()));
            document.addEventListener('keydown', (e) => {
                if (!AppModal._busy) return;
                if (e.key === 'Escape') {
                    e.preventDefault();
                    AppModal._settle(AppModal._cancelValue());
                } else if (e.key === 'Enter' && AppModal._kind !== 'alert' && AppModal._kind !== 'editor') {
                    e.preventDefault();
                    AppModal._settle(AppModal._kind === 'prompt' ? input.value : true);
                }
            });
        }
        // —— 节点搬入：vault → modal-body（原序；textarea 包弹性层）——
        this._editorUnstash();
        // —— textarea dirty 一次性监听（搬入搬出不卸载）——
        const ta = document.getElementById('refineTemplateText');
        if (ta && !ta.dataset.edDirtyBound) {
            ta.dataset.edDirtyBound = '1';
            ta.addEventListener('input', () => { AppModal._edDirty = true; });
        }
        // —— vault 内保存/重载/切阶段键：弹窗感知路径一次性绑定（原
        // bindDom 直绑移除，见 bindDom 批D 注记）——
        const saveBtn = document.getElementById('refineTemplateSave');
        if (saveBtn && !saveBtn.dataset.edSaveBound) {
            saveBtn.dataset.edSaveBound = '1';
            saveBtn.addEventListener('click', () => AppModal.editorRunSave());
        }
        const reloadBtn = document.getElementById('refineTemplateReload');
        if (reloadBtn && !reloadBtn.dataset.edReloadBound) {
            reloadBtn.dataset.edReloadBound = '1';
            reloadBtn.addEventListener('click', () => AppModal.editorRunStageChange('reload'));
        }
        const stageSel = document.getElementById('refineTemplateStage');
        if (stageSel && !stageSel.dataset.edStageBound) {
            stageSel.dataset.edStageBound = '1';
            stageSel.addEventListener('change', () => AppModal.editorRunStageChange('change'));
        }
        this._edOpts = o;
        this._busy = true;
        this._kind = 'editor';
        this._edDirty = false;
        this._edSaving = false;
        this._edConfirming = false;
        root.style.display = 'flex';
        if (ta) ta.focus();
        return new Promise((resolve) => {
            this._resolve = (value) => {
                this._editorTeardown();
                if (typeof o.onClose === 'function') o.onClose();
                resolve(value);
            };
        });
    },

    // 节点搬回 vault（关闭/确认前收起）：modal-body 子节点逐个 append 回
    // vault 原序复位（textarea 自弹性层拆出）；vault 原 hidden 保留，
    // 节点回 vault 即随容器隐藏——vault hidden ↔ 弹窗互斥
    _editorStash() {
        const vault = document.querySelector('.tpl-editor-vault');
        const body = document.querySelector('#appModal .modal-body');
        if (!vault || !body) return;
        Array.prototype.slice.call(body.childNodes).forEach((n) => {
            if (n.nodeType === 1 && n.classList.contains('editor-ta-wrap')) {
                while (n.firstChild) vault.appendChild(n.firstChild);
            } else {
                vault.appendChild(n);
            }
        });
        while (body.firstChild) body.removeChild(body.firstChild);   // 残余包装层
    },

    // 节点搬入 modal-body（vault → 弹窗；原序；textarea 包 .editor-ta-wrap）
    _editorUnstash() {
        const vault = document.querySelector('.tpl-editor-vault');
        const body = document.querySelector('#appModal .modal-body');
        if (!vault || !body) return;
        Array.prototype.slice.call(vault.childNodes).forEach((n) => {
            if (n.nodeType === 1 && n.id === 'refineTemplateText') {
                const wrap = document.createElement('div');
                wrap.className = 'editor-ta-wrap';
                wrap.appendChild(n);
                body.appendChild(wrap);
            } else {
                body.appendChild(n);
            }
        });
    },

    // 编辑器开态确认弹窗（与 confirm 共用单例骨架）：先收起编辑器（节点
    // 搬回 vault hidden 保状态 + _busy=false 放行 confirm），取消=原样恢复
    // （_busy/_kind/_resolve/display/节点全部还原）；确认=保持收起态由调用
    // 方收尾（关闭结算或放行原动作）
    _editorConfirmWhileOpen(msg) {
        const edResolve = this._resolve;    // confirm 会覆写 _resolve，先持有
        const root = document.getElementById('appModal');
        const okBtn = root && root.querySelector('.modal-ok');
        this._edConfirming = true;
        this._editorStash();
        if (root) root.style.display = 'none';
        this._busy = false;
        if (okBtn) okBtn.style.display = '';    // confirm 需要 OK 键（编辑器开态隐藏）
        return AppModal.confirm(msg).then((ok) => {
            this._busy = true;
            this._kind = 'editor';
            this._resolve = edResolve;
            this._edConfirming = false;
            if (okBtn) okBtn.style.display = 'none';
            if (ok) return true;
            if (root) root.style.display = 'flex';
            this._editorUnstash();
            return false;
        });
    },

    // dirty 关闭守卫：未保存修改先确认——取消=弹窗与编辑状态原样保留；
    // 确认=真放弃（脏复位+正式结算+onDiscard 按当前阶段重载丢编辑）
    _editorDiscardGuard() {
        this._editorConfirmWhileOpen(MSG.tplEditorDirtyConfirm).then((ok) => {
            if (!ok) return;
            this._edDirty = false;
            this._settle(false);            // 正式结算（_resolve 收尾 teardown+onClose）
            const o = this._edOpts || {};
            if (typeof o.onDiscard === 'function') {
                try { o.onDiscard(); } catch (e) { /* 重载失败静默 */ }
            }
        });
    },

    // 保存主键（vault 内 #refineTemplateSave）弹窗感知路径：onSave 进行中
    // 禁止关闭（_edSaving 同 _dlRunning 先例）；成功=清脏+status/入口摘要
    // 写已保存+自动关闭；失败=status 写失败文案、弹窗保持
    async editorRunSave() {
        if (this._edSaving || this._edConfirming) return;
        const o = this._edOpts || {};
        if (typeof o.onSave !== 'function') return;
        this._edSaving = true;
        const cancelBtn = document.querySelector('#appModal .modal-cancel');
        if (cancelBtn) cancelBtn.disabled = true;
        const stage = (document.getElementById('refineTemplateStage') || {}).value;
        const text = (document.getElementById('refineTemplateText') || {}).value;
        let ok = false, message = '';
        try {
            const res = await Promise.resolve(o.onSave(stage, text));
            ok = !!(res && res.ok);
            message = (res && res.message) || '';
        } catch (e) {
            ok = false;
            message = e && e.message ? e.message : String(e);
        }
        this._edSaving = false;
        if (cancelBtn) cancelBtn.disabled = false;
        const st = document.getElementById('refineTemplateStatus');
        if (st) {
            st.style.color = ok ? 'var(--status-ok)' : 'var(--status-err)';
            st.textContent = (ok ? MSG.tplEditorSaveOk : MSG.tplEditorSaveFailed)
                + (message ? '：' + message : '');
        }
        const entrySt = document.querySelector('[data-testid="tpl-entry-status"]');
        if (entrySt) {
            entrySt.style.color = ok ? 'var(--status-ok)' : 'var(--status-err)';
            entrySt.textContent = (ok ? MSG.tplEditorSaveOk : MSG.tplEditorSaveFailed)
                + (message ? '：' + message : '');
        }
        if (ok) {
            this._edDirty = false;
            this._settle(false);            // 自动关闭（_resolve 收尾搬回节点）
        }
    },

    // 重载/切阶段（弹窗感知）：有未保存修改先同款确认，放行后执行原动作
    // （reload=列目录+按选中加载；change=按当前选中加载，语义同原绑定）
    editorRunStageChange(mode) {
        if (this._edSaving || this._edConfirming) return;
        const o = this._edOpts || {};
        const run = () => {
            const stage = (document.getElementById('refineTemplateStage') || {}).value;
            Promise.resolve(typeof o.onStageChange === 'function'
                ? o.onStageChange(stage, mode) : null).catch(() => {});
        };
        if (this._edDirty) {
            this._editorConfirmWhileOpen(MSG.tplEditorDirtyConfirm).then((ok) => {
                if (!ok) return;
                this._edDirty = false;
                const root = document.getElementById('appModal');
                if (root) root.style.display = 'flex';   // 放行后恢复弹窗与节点
                this._editorUnstash();
                run();
            });
            return;
        }
        run();
    },

    // 关闭收尾（_resolve 包装内调用）：节点搬回 vault + 骨架默认态恢复
    // （download 同款自清理：_open 不重置 okBtn.display/whiteSpace，防污染
    // 后续 alert/confirm/prompt）
    _editorTeardown() {
        this._editorStash();
        const root = document.getElementById('appModal');
        if (root) {
            const card = root.querySelector('.modal-card');
            if (card) card.classList.remove('modal-lg');
            const body = root.querySelector('.modal-body');
            if (body) {
                body.classList.remove('modal-editor-body');
                body.style.whiteSpace = '';
            }
            const okBtn = root.querySelector('.modal-ok');
            if (okBtn) okBtn.style.display = '';
        }
        this._edSaving = false;
        this._edConfirming = false;
    },

    // ============================================================
    // 模型管理模态（2.7.1 件3，D2026-1005-01 承接批）：AppModal kind='models'，
    // 720px .modal-lg（复用编辑器同款骨架扩宽）。body 全 createElement 注入
    // （全 class+data-testid，零新增 id/data-i18n）。
    // _settle 守卫隔离（评议 C3）：models kind 不复用 _dlRunning 布尔——
    // _settle 的 no-op 分支仅命中 download kind，models 关闭永不阻塞；
    // 下载由后端同步桥承载（关面板不终止），重开面板经
    // refine_asr_download_progress 快照恢复显示（进程内 _ASR_DOWNLOAD_PROGRESS）。
    // 布局：路径栏→未适配 banner→三档分组（档间可折叠）→模型行
    // （名称+描述+速度/精度五格点阵·静态评定+大小+下载按钮+推荐★）→
    // 变体行内展开→下载行内进度（.dl-progress-* 复用+前端增量 MB/s）→
    // 失败诊断网格（.dict-diag-grid 复用）。
    // 三态双门控：backend_state ready=绿 chip 可下载/adapter-needed=琥珀
    // 禁用+不入下拉/planned=灰禁用；verified==False 额外禁下载（件5 硬门槛）。
    // opts = {probe: <refine_asr_status 结果>, onFinished?: 下载收尾回调}
    // ============================================================
    models(opts) {
        if (this._busy) return Promise.resolve(false);      // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        const o = opts || {};
        const probe = o.probe || {};
        const api = window.pywebview && window.pywebview.api;
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = MSG.mpTitle;
        body.textContent = '';
        body.style.whiteSpace = 'normal';
        body.classList.add('mp-body');
        const card = root.querySelector('.modal-card');
        if (card) card.classList.add('modal-lg');
        input.style.display = 'none';
        okBtn.style.display = 'none';       // 关闭语义由取消键承载
        okBtn.textContent = '';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        if (!root.dataset.bound) {          // 与 _open 同款一次性绑定
            root.dataset.bound = '1';
            root.addEventListener('click', (e) => {
                if (e.target === root) AppModal._settle(AppModal._cancelValue());
            });
            cancelBtn.addEventListener('click', () =>
                AppModal._settle(AppModal._cancelValue()));
            document.addEventListener('keydown', (e) => {
                if (!AppModal._busy) return;
                if (e.key === 'Escape') {
                    e.preventDefault();
                    AppModal._settle(AppModal._cancelValue());
                } else if (e.key === 'Enter' && AppModal._kind !== 'alert'
                           && AppModal._kind !== 'editor') {
                    e.preventDefault();
                    AppModal._settle(AppModal._cancelValue());
                }
            });
        }

        // —— 轮询登记表（关面板统一清理；进度数据在 _ASR_DOWNLOAD_PROGRESS）——
        const polls = {};
        const stopAllPolls = () => {
            Object.keys(polls).forEach((k) => {
                clearInterval(polls[k]);
                delete polls[k];
            });
        };

        const fmtMB = (n) => (n / 1048576).toFixed(1);
        // fmtGB 本地版：模块级同名函数在 RefineUI IIFE 闭包内（:4730），
        // AppModal 顶层对象不可见（黑盒抓缺陷：ReferenceError 中断面板渲染）
        const fmtGB = (n) => Math.round(n / 1073741824 * 10) / 10 + 'GB';
        const el = (tag, cls, text) => {
            const n = document.createElement(tag);
            if (cls) n.className = cls;
            if (text != null) n.textContent = text;
            return n;
        };

        // —— 路径栏（whisper 缓存+应用数据目录两行，各带「打开文件夹」）——
        const pathBox = el('div', 'mp-paths');
        [
            [MSG.mpPathWhisper, probe.cache_dir || ''],
            [MSG.mpPathData, probe.models_dir || ''],
        ].forEach(([label, dir]) => {
            const row = el('div', 'mp-path-row');
            row.appendChild(el('span', 'mp-path-label', label));
            const p = el('span', 'mp-path-val', dir);
            p.title = dir;
            row.appendChild(p);
            const btn = el('button', 'btn btn-ghost btn-compact mp-path-open',
                           MSG.mpOpenDir);
            btn.type = 'button';
            btn.addEventListener('click', () => {
                if (typeof openDir === 'function') openDir(dir);
            });
            row.appendChild(btn);
            pathBox.appendChild(row);
        });
        body.appendChild(pathBox);

        // —— 未适配 banner（探测到 N 个未适配模型时显示；全面板唯一长文案位）——
        const hf = probe.models_hf || [];
        if (hf.length) {
            body.appendChild(el('div', 'mp-banner hint-warn',
                                MSG.mpUnadaptedBanner(hf.length)));
        }

        // —— 模型行构造（三态双门控；下载行内进度+MB/s 增量；失败诊断网格）——
        const rowBind = {};     // name -> {startPolling, setPresent}
        const renderModelRow = (entry) => {
            const state = (entry.backend && entry.backend.state) || 'planned';
            const row = el('div', 'mp-row mp-row-' + state);
            row.dataset.mpModel = entry.name;
            // 名称行：名称+推荐★（内联 Lucide star，色 --warn）+三态 chip
            const head = el('div', 'mp-row-head');
            head.appendChild(el('span', 'mp-row-name', entry.name));
            if (entry.spec && entry.spec.recommend) {
                const star = el('span', 'mp-star');
                star.title = MSG.mpSpecNote;
                star.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13"'
                    + ' fill="var(--warn)" stroke="var(--warn)" stroke-width="1"'
                    + ' stroke-linecap="round" stroke-linejoin="round"'
                    + ' aria-hidden="true"><polygon points="12 2 15.09 8.26 22'
                    + ' 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2'
                    + ' 9.27 8.91 8.26 12 2"/></svg>';
                head.appendChild(star);
            }
            const chipCls = state === 'ready' ? 'mp-chip-ready'
                : (state === 'adapter-needed' ? 'mp-chip-adapter'
                   : 'mp-chip-planned');
            const chipLabel = state === 'ready' ? MSG.mpStateReady
                : (state === 'adapter-needed' ? MSG.mpStateAdapter
                   : MSG.mpStatePlanned);
            head.appendChild(el('span', 'mp-chip ' + chipCls, chipLabel));
            if (entry.present) head.appendChild(el('span', 'mp-present',
                                                   '✓ ' + MSG.mpStateReady));
            row.appendChild(head);
            if (entry.desc) row.appendChild(el('div', 'mp-row-desc',
                                               entry.desc));
            // 五格点阵（静态评定，标注非实测）：速度+精度两行
            const spec = entry.spec || {};
            const matrix = el('div', 'mp-dots-wrap');
            [['mpSpeedLabel', spec.speed], ['mpPrecisionLabel', spec.precision]]
              .forEach(([key, val]) => {
                const line = el('div', 'mp-dots-row');
                line.appendChild(el('span', 'mp-dots-label', MSG[key]));
                const dots = el('span', 'mp-dots');
                dots.dataset.mpSpecNote = MSG.mpSpecNote;
                for (let i = 1; i <= 5; i++) {
                    dots.appendChild(el('span', 'mp-dot'
                        + (i <= (val || 0) ? ' filled' : '')));
                }
                line.appendChild(dots);
                matrix.appendChild(line);
            });
            row.appendChild(matrix);
            // 元信息行：大小+变体行内展开
            const meta = el('div', 'mp-row-meta');
            if (entry.bytes) meta.appendChild(el('span', 'mp-size',
                                                 fmtGB(entry.bytes)));
            const variants = entry.variants || [];
            if (variants.length) {
                const det = el('details', 'mp-variants');
                det.appendChild(el('summary', 'mp-variants-summary',
                                   MSG.mpVariantsLabel + '（'
                                   + variants.length + '）'));
                variants.forEach((v) => {
                    const vRow = el('div', 'mp-variant-row');
                    vRow.appendChild(el('span', 'mp-variant-name', v.name));
                    const vOk = v.state === 'ready';
                    vRow.appendChild(el('span',
                        'mp-chip ' + (vOk ? 'mp-chip-ready'
                                          : 'mp-chip-adapter'),
                        (vOk ? '✓ ' : '') + (vOk ? MSG.mpStateReady
                                                 : MSG.mpStateAdapter)));
                    if (v.note) vRow.title = v.note;
                    det.appendChild(vRow);
                });
                meta.appendChild(det);
            }
            row.appendChild(meta);
            // 下载行内进度（复用 .dl-progress-*）+ 失败诊断网格
            const prog = el('div', 'dl-progress mp-progress');
            prog.style.display = 'none';
            const bar = el('div', 'dl-progress-bar');
            const fill = el('div', 'dl-progress-fill');
            bar.appendChild(fill);
            const text = el('div', 'dl-progress-text');
            prog.appendChild(bar);
            prog.appendChild(text);
            row.appendChild(prog);
            const diag = el('div', 'dict-diag-grid mp-diag');
            diag.style.display = 'none';
            const showDiag = (r) => {
                diag.textContent = '';
                const items = [
                    ['错误', (r && (r.error || r.message)) || ''],
                    ['模型', entry.name],
                    ['来源', (probe.python_source && probe.python) || ''],
                ];
                items.forEach(([k, v]) => {
                    if (!v) return;
                    diag.appendChild(el('span', 'k', k));
                    diag.appendChild(el('span', 'v', String(v)));
                });
                diag.style.display = diag.children.length ? '' : 'none';
            };
            row.appendChild(diag);
            // 下载按钮（三态双门控+verified 硬门槛）
            const actions = el('div', 'mp-row-actions');
            const dlBtn = el('button', 'btn btn-secondary btn-compact mp-dl-btn',
                             MSG.asrDownloadBtn);
            dlBtn.type = 'button';
            let dlRunning = false;
            const startPolling = () => {
                prog.style.display = '';
                let lastBytes = 0;
                let lastT = 0;
                const poll = setInterval(async () => {
                    if (!api || !api.refine_asr_download_progress) return;
                    try {
                        const p = await api
                          .refine_asr_download_progress(entry.model
                                                        || entry.name);
                        if (!(p && p.success && p.phase)) return;
                        if (p.phase === 'download' && p.total) {
                            bar.classList.remove('indeterminate');
                            const dl = p.downloaded || 0;
                            fill.style.width = Math.min(100, Math.round(
                                dl / p.total * 100)) + '%';
                            let speed = '';
                            if (lastT && dl >= lastBytes) {
                                const dt = (Date.now() - lastT) / 1000;
                                if (dt > 0) {
                                    speed = '｜' + ((dl - lastBytes)
                                        / 1048576 / dt).toFixed(1) + 'MB/s';
                                }
                            }
                            lastBytes = dl;
                            lastT = Date.now();
                            text.textContent = fmtMB(dl) + '/'
                                + fmtMB(p.total) + 'MB' + speed
                                + (p.note ? '｜' + p.note : '');
                        } else if (p.phase === 'verify') {
                            bar.classList.add('indeterminate');
                            text.textContent = MSG.dict_verify
                                + (p.note ? '｜' + p.note : '');
                        } else if (p.phase === 'done') {
                            bar.classList.remove('indeterminate');
                            fill.style.width = '100%';
                            text.textContent = MSG.asrDlDone;
                        } else if (p.phase === 'failed') {
                            bar.classList.add('indeterminate');
                            text.textContent = MSG.asrDlFailed
                                + (p.error ? '：' + p.error : '');
                            showDiag(p);
                        }
                    } catch (e) { /* 进度轮询失败不干扰主流程 */ }
                }, 1000);
                polls[entry.name] = poll;
            };
            const finishOk = () => {
                dlRunning = false;
                prog.style.display = 'none';
                dlBtn.style.display = 'none';
                if (!entry.present) {
                    entry.present = true;
                    head.appendChild(el('span', 'mp-present',
                                        '✓ ' + MSG.mpStateReady));
                }
                if (typeof o.onFinished === 'function') o.onFinished();
            };
            const finishFail = (r) => {
                dlRunning = false;
                if (dlBtn) dlBtn.disabled = false;
                bar.classList.add('indeterminate');
                text.textContent = MSG.asrDlFailed + '：'
                    + ((r && (r.error || r.message)) || MSG.unknown);
                showDiag(r);
                if (typeof o.onFinished === 'function') o.onFinished();
            };
            dlBtn.addEventListener('click', () => {
                if (dlRunning || !api || !api.refine_asr_download) return;
                dlRunning = true;
                dlBtn.disabled = true;
                startPolling();
                api.refine_asr_download(entry.model || entry.name, 'auto')
                  .then((r) => {
                      const p = polls[entry.name];
                      if (p) { clearInterval(p); delete polls[entry.name]; }
                      if (r && r.success) finishOk(); else finishFail(r);
                  })
                  .catch((e) => {
                      const p = polls[entry.name];
                      if (p) { clearInterval(p); delete polls[entry.name]; }
                      finishFail(e);
                  });
            });
            if (entry.present) {
                dlBtn.style.display = 'none';       // 已就位：无下载入口
            } else if (state === 'planned') {
                dlBtn.disabled = true;
                dlBtn.title = MSG.mpPlannedTitle;
            } else if (state !== 'ready') {
                dlBtn.disabled = true;
                dlBtn.title = MSG.mpAdapterTitle;
            } else if (entry.verified !== true) {
                dlBtn.disabled = true;              // 件5 硬门槛：未核验禁下载
                dlBtn.title = MSG.mpUnverifiedTitle;
            }
            actions.appendChild(dlBtn);
            row.appendChild(actions);
            rowBind[entry.name] = { startPolling };
            return row;
        };

        // —— 三档分组（档间可折叠 details；分组=分页等效，owner 拍板）——
        const TIERS = [
            ['fast', MSG.mpTierFast],
            ['balanced', MSG.mpTierBalanced],
            ['precise', MSG.mpTierPrecise],
        ];
        const recs = probe.recommended || [];
        let rowsBuilt = 0;
        TIERS.forEach(([tier, label]) => {
            const items = recs.filter((e) => (e.tier || '') === tier);
            if (!items.length) return;
            const det = el('details', 'mp-tier');
            det.open = true;
            const sum = el('summary', 'mp-tier-head');
            sum.appendChild(el('span', 'mp-tier-name', label));
            det.appendChild(sum);
            items.forEach((entry) => {
                det.appendChild(renderModelRow(entry));
                rowsBuilt++;
            });
            body.appendChild(det);
        });
        if (!rowsBuilt) {
            body.appendChild(el('div', 'muted', MSG.mpNeedProbe));
        }

        // —— 重开恢复：逐条查下载进度快照，下载中/校验中→恢复轮询显示 ——
        if (api && api.refine_asr_download_progress) {
            recs.forEach((entry) => {
                const bind = rowBind[entry.name];
                if (!bind) return;
                api.refine_asr_download_progress(
                    entry.model || entry.name).then((p) => {
                    if (p && p.success
                            && (p.phase === 'download'
                                || p.phase === 'verify')) {
                        bind.startPolling();
                    }
                }).catch(() => { /* 恢复失败静默（下次轮询自愈） */ });
            });
        }

        // 收口：关面板恢复骨架默认态（modal-lg/mp-body 自清理）+轮询清理；
        // 下载本身由后端桥承载，关面板不终止（评议 C3 隔离的关键语义）
        this._busy = true;
        this._kind = 'models';
        root.style.display = 'flex';
        return new Promise((resolve) => {
            this._resolve = (value) => {
                stopAllPolls();
                const card2 = root.querySelector('.modal-card');
                if (card2) card2.classList.remove('modal-lg');
                const body2 = root.querySelector('.modal-body');
                if (body2) body2.classList.remove('mp-body');
                if (okBtn) okBtn.style.display = '';
                resolve(value);
            };
        });
    }
};

// ============================================================
// Error Handler
// ============================================================
const ErrorHandler = {
    show(title, message) {
        ConsoleManager.log(`✗ ${title}: ${message}`, 'error');
        // 2.4.0 批1：原生 alert → 自制模态（非阻塞化语义安全——全调用点均为
        // "展示后随即 _finish/return"模式，无阻塞依赖；行为变化=模态期间 UI 可交互）
        AppModal.alert(title, message);
    },

    showWarning(title, message) {
        ConsoleManager.log(`⚠ ${title}: ${message}`, 'warning');
    },

    showSuccess(title, message) {
        ConsoleManager.log(`✓ ${title}: ${message}`, 'success');
    }
};

// ============================================================
// File List Management (always .srt mode)
// ============================================================
const FileListManager = {
    init() {
        this.itemStates = {};   // path -> 'pending'|'running'|'done'|'resumable'（D2026-0930-09 批2）

        const fileList = document.getElementById('fileList');

        fileList.addEventListener('click', (e) => {
            const removeBtn = e.target.closest('.file-remove-btn');
            if (removeBtn) {
                const item = removeBtn.closest('.file-item');
                if (item && item.dataset.path) {
                    this.removeOne(item.dataset.path);
                }
                return;
            }
            const item = e.target.closest('.file-item');
            if (item) {
                this.handleItemClick(item, e);
            }
        });

        fileList.addEventListener('keydown', (e) => {
            this.handleKeyboard(e);
        });

        this.initializeDragDrop();

        document.getElementById('addFilesBtn').addEventListener('click', () => this.addFiles());
        document.getElementById('addFolderBtn').addEventListener('click', () => this.addFolder());
        document.getElementById('removeSelectedBtn').addEventListener('click', () => this.removeSelected());
        document.getElementById('clearBtn').addEventListener('click', () => this.clearAll());
    },

    initializeDragDrop() {
        const fileList = document.getElementById('fileList');
        const dropzone = document.getElementById('dropzone');

        // D2026-0930-09 批2：拖拽高亮同时作用于 dropzone 本体（preventDefault 已有，防 PyWebView 打开文件）
        const highlight = (on) => {
            fileList.classList.toggle('drag-over', on);
            if (dropzone) dropzone.classList.toggle('drag-over', on);
        };

        fileList.addEventListener('dragover', (e) => {
            e.preventDefault();
            e.stopPropagation();
            highlight(true);
        });

        fileList.addEventListener('dragenter', (e) => {
            e.preventDefault();
            e.stopPropagation();
            highlight(true);
        });

        fileList.addEventListener('dragleave', () => {
            highlight(false);
        });

        fileList.addEventListener('drop', (e) => {
            e.preventDefault();
            e.stopPropagation();
            highlight(false);
            // Actual path extraction happens in Python (main.py) via pywebviewFullPath,
            // which calls back into FileListManager.addDroppedFiles(paths).
        });
    },

    // Method called by Python DOM event handler with full file paths
    // (.srt/.ass/.ssa/.vtt only，2.7.2 件1 与对话框口径一致)
    addDroppedFiles(paths) {
        if (!Array.isArray(paths) || paths.length === 0) {
            return;
        }

        let addedCount = 0;
        let duplicates = 0;
        let skipped = 0;
        const allowedSubtitleExts = ['.srt', '.ass', '.ssa', '.vtt'];

        paths.forEach(path => {
            const p = String(path).toLowerCase();
            if (!allowedSubtitleExts.some(ext => p.endsWith(ext))) {
                skipped++;
                return;
            }
            if (!AppState.selectedFiles.includes(path)) {
                AppState.selectedFiles.push(path);
                addedCount++;
            } else {
                duplicates++;
            }
        });

        if (addedCount > 0) {
            this.render();
            ConsoleManager.log(MSG.addedViaDrop(addedCount), 'success');
        }
        if (duplicates > 0) {
            ConsoleManager.log(MSG.skippedDuplicates(duplicates), 'info');
        }
        if (skipped > 0) {
            ConsoleManager.log(MSG.skippedNonSrt(skipped), 'warning');
        }
    },

    render() {
        // A案 has-files 态单点切换（批1，C1 修正）：必须在函数体第一行、
        // 空态提前 return 之前——六条 selectedFiles 变更路径全汇 render()，
        // 单点双出口（空态 return / 正常渲染）全覆盖，清空路径可回归空态
        document.getElementById('tab-translate').classList.toggle('has-files', AppState.selectedFiles.length > 0);
        const fileList = document.getElementById('fileList');
        const emptyState = document.getElementById('emptyState');

        if (AppState.selectedFiles.length === 0) {
            emptyState.style.display = 'flex';
            fileList.querySelectorAll('.file-item').forEach(item => item.remove());
            this.updateButtons();
            return;
        }

        emptyState.style.display = 'none';

        const existingItems = Array.from(fileList.querySelectorAll('.file-item'));
        const existingPaths = existingItems.map(item => item.dataset.path);

        AppState.selectedFiles.forEach((file, index) => {
            if (!existingPaths.includes(file)) {
                const item = this.createFileItem(file, index);
                fileList.appendChild(item);
            }
        });

        existingItems.forEach(item => {
            if (!AppState.selectedFiles.includes(item.dataset.path)) {
                item.remove();
            }
        });

        const pathToIndex = new Map();
        AppState.selectedFiles.forEach((file, index) => {
            if (!pathToIndex.has(file)) pathToIndex.set(file, index);
        });
        fileList.querySelectorAll('.file-item').forEach(item => {
            const index = pathToIndex.get(item.dataset.path);
            if (index !== undefined) item.dataset.index = String(index);
        });

        this.updateChips();
        this.updateButtons();
    },

    createFileItem(path, index) {
        const item = document.createElement('div');
        item.className = 'file-item';
        item.dataset.path = path;
        item.dataset.index = index;
        item.tabIndex = 0;

        const icon = document.createElement('span');
        icon.className = 'file-ico';
        icon.innerHTML =
            '<svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M15 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V7Z"/><path d="M14 2v4a2 2 0 0 0 2 2h4"/><path d="M10 9H8"/><path d="M16 13H8"/><path d="M16 17H8"/></svg>';

        const grow = document.createElement('span');
        grow.className = 'grow';
        const name = document.createElement('span');
        name.className = 'file-name';
        name.textContent = path.split(/[\\/]/).pop() || path;
        const sub = document.createElement('span');
        sub.className = 'file-path';
        sub.textContent = path;
        grow.appendChild(name);
        grow.appendChild(sub);

        const chip = document.createElement('span');
        chip.className = 'chip chip-pending';
        chip.textContent = MSG.chip_pending;

        const removeBtn = document.createElement('button');
        removeBtn.type = 'button';
        removeBtn.className = 'file-remove-btn';
        removeBtn.title = MSG.remove_selected;
        removeBtn.setAttribute('aria-label', MSG.remove_selected);
        removeBtn.innerHTML =
            '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M11 4H4a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-5"/><path d="M10 14 21 3"/><path d="M15 3h6v6"/></svg>';

        item.appendChild(icon);
        item.appendChild(grow);
        item.appendChild(chip);
        item.appendChild(removeBtn);

        return item;
    },

    // ---- 三态 chip（D2026-0930-09 批2）：pending/running/done/resumable ----
    chipClass(state) {
        return {
            pending: 'chip-pending',
            running: 'chip-running',
            done: 'chip-done',
            resumable: 'chip-resumable'
        }[state] || 'chip-pending';
    },

    chipText(state) {
        return {
            pending: MSG.chip_pending,
            running: MSG.chip_running,
            done: MSG.chip_done,
            resumable: MSG.chip_resumable
        }[state] || MSG.chip_pending;
    },

    setState(path, state) {
        if (!state) return;
        this.itemStates[path] = state;
        this.updateChips();
    },

    // files_status 映射（basename -> state）：只更新命中的文件，不回退其他项
    applyStates(map) {
        if (!map) return;
        const base = p => p.split(/[\\/]/).pop();
        let touched = false;
        AppState.selectedFiles.forEach(p => {
            const st = map[base(p)];
            if (st && this.itemStates[p] !== st) {
                this.itemStates[p] = st;
                touched = true;
            }
        });
        if (touched) this.updateChips();
    },

    updateChips() {
        document.querySelectorAll('.file-item').forEach(item => {
            const state = this.itemStates[item.dataset.path] || 'pending';
            const chip = item.querySelector('.chip');
            if (chip) {
                chip.className = 'chip ' + this.chipClass(state);
                chip.textContent = this.chipText(state);
            }
        });
    },

    removeOne(path) {
        const idx = AppState.selectedFiles.indexOf(path);
        if (idx >= 0) AppState.selectedFiles.splice(idx, 1);
        delete this.itemStates[path];
        AppState.selectedIndices.clear();
        this.render();
    },

    handleItemClick(item, event) {
        const index = parseInt(item.dataset.index);

        if (event.ctrlKey || event.metaKey) {
            this.toggleSelection(index);
        } else if (event.shiftKey && AppState.selectedIndices.size > 0) {
            const lastIndex = Math.max(...Array.from(AppState.selectedIndices));
            this.selectRange(lastIndex, index);
        } else {
            this.selectSingle(index);
        }

        this.updateSelectionUI();
        this.updateButtons();
    },

    toggleSelection(index) {
        if (AppState.selectedIndices.has(index)) {
            AppState.selectedIndices.delete(index);
        } else {
            AppState.selectedIndices.add(index);
        }
    },

    selectSingle(index) {
        AppState.selectedIndices.clear();
        AppState.selectedIndices.add(index);
    },

    selectRange(start, end) {
        const [min, max] = [Math.min(start, end), Math.max(start, end)];
        for (let i = min; i <= max; i++) {
            AppState.selectedIndices.add(i);
        }
    },

    updateSelectionUI() {
        document.querySelectorAll('.file-item').forEach(item => {
            const index = parseInt(item.dataset.index);
            item.classList.toggle('selected', AppState.selectedIndices.has(index));
        });
    },

    updateButtons() {
        const hasFiles = AppState.selectedFiles.length > 0;
        const hasSelection = AppState.selectedIndices.size > 0;

        document.getElementById('removeSelectedBtn').disabled = !hasSelection || AppState.isRunning;
        document.getElementById('clearBtn').disabled = !hasFiles || AppState.isRunning;

        TranslatorManager.updateButtons();
    },

    handleKeyboard(e) {
        const items = Array.from(document.querySelectorAll('.file-item'));
        if (items.length === 0) return;

        const currentIndex = Array.from(AppState.selectedIndices).sort((a, b) => b - a)[0] || 0;

        let newIndex = currentIndex;

        if (e.key === 'ArrowDown') {
            newIndex = Math.min(items.length - 1, currentIndex + 1);
            e.preventDefault();
        } else if (e.key === 'ArrowUp') {
            newIndex = Math.max(0, currentIndex - 1);
            e.preventDefault();
        } else if (e.key === 'Delete' || e.key === 'Backspace') {
            this.removeSelected();
            e.preventDefault();
            return;
        } else {
            return;
        }

        if (e.shiftKey) {
            this.selectRange(currentIndex, newIndex);
        } else {
            this.selectSingle(newIndex);
        }

        this.updateSelectionUI();
        this.updateButtons();

        if (items[newIndex]) {
            items[newIndex].scrollIntoView({ block: 'nearest' });
        }
    },

    async addFiles() {
        const btn = document.getElementById('addFilesBtn');
        UIHelpers.showLoadingState(btn, true);

        try {
            const result = await pywebview.api.select_srt_files();

            if (result.success && result.paths && result.paths.length > 0) {
                result.paths.forEach(file => {
                    if (!AppState.selectedFiles.includes(file)) {
                        AppState.selectedFiles.push(file);
                    }
                });

                this.render();
                ConsoleManager.log(MSG.addedFiles(result.paths.length), 'info');
            }
        } catch (error) {
            ErrorHandler.show(MSG.fileSelectError, error.toString());
        } finally {
            UIHelpers.showLoadingState(btn, false);
        }
    },

    async addFolder() {
        const btn = document.getElementById('addFolderBtn');
        UIHelpers.showLoadingState(btn, true);

        try {
            const result = await pywebview.api.select_srt_folder();
            if (result.success && result.paths && result.paths.length > 0) {
                result.paths.forEach(filePath => {
                    if (!AppState.selectedFiles.includes(filePath)) {
                        AppState.selectedFiles.push(filePath);
                    }
                });
                this.render();
                ConsoleManager.log(MSG.addedFilesFromFolder(result.paths.length), 'info');
            } else if (result.message) {
                ConsoleManager.log(result.message, 'warning');
            }
        } catch (error) {
            ErrorHandler.show(MSG.folderSelectError, error.toString());
        } finally {
            UIHelpers.showLoadingState(btn, false);
        }
    },

    removeSelected() {
        if (AppState.selectedIndices.size === 0) return;

        const indicesToRemove = Array.from(AppState.selectedIndices).sort((a, b) => b - a);
        indicesToRemove.forEach(index => {
            AppState.selectedFiles.splice(index, 1);
        });

        AppState.selectedIndices.clear();
        this.render();
        ConsoleManager.log(MSG.removedItems(indicesToRemove.length), 'info');
    },

    clearAll() {
        if (AppState.selectedFiles.length === 0) return;

        const count = AppState.selectedFiles.length;
        AppState.selectedFiles = [];
        AppState.selectedIndices.clear();
        this.itemStates = {};
        this.render();
        ConsoleManager.log(MSG.clearedItems(count), 'info');
    }
};

// ============================================================
// Console Management
// ============================================================
const ConsoleManager = {
    init() {
        document.getElementById('clearConsoleBtn').addEventListener('click', () => this.clear());

        // Console 折叠开关（默认展开；折叠后隐藏输出区且外层不再占 flex:1）
        const collapseBtn = document.getElementById('consoleCollapseBtn');
        if (collapseBtn) {
            collapseBtn.setAttribute('aria-label', MSG.console_collapse);
            collapseBtn.addEventListener('click', () => {
                const section = collapseBtn.closest('.console-section');
                if (!section) return;
                const collapsed = section.classList.toggle('collapsed');
                collapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
                const key = collapsed ? 'console_expand' : 'console_collapse';
                collapseBtn.setAttribute('title', MSG[key]);
                collapseBtn.setAttribute('aria-label', MSG[key]);
            });
        }
    },

    log(message, type = 'info') {
        const output = document.getElementById('consoleOutput');
        const line = document.createElement('div');
        line.className = `console-line ${type}`;
        line.textContent = message;
        output.appendChild(line);

        requestAnimationFrame(() => {
            if (output) {
                output.scrollTop = output.scrollHeight;
            }
        });
    },

    clear() {
        const output = document.getElementById('consoleOutput');
        output.innerHTML = `<div class="console-line">${MSG.ready}</div>`;
    },

    appendRaw(text) {
        const output = document.getElementById('consoleOutput');

        const lines = text.split('\n');

        lines.forEach((line, index) => {
            if (index === lines.length - 1 && line === '') return;

            const lineEl = document.createElement('div');
            lineEl.className = 'console-line';
            lineEl.textContent = line || ' ';
            output.appendChild(lineEl);
        });

        requestAnimationFrame(() => {
            if (output) {
                output.scrollTop = output.scrollHeight;
            }
        });
    }
};

// ============================================================
// Progress Management (progress bar inside the refine panel)
// ============================================================
const ProgressManager = {
    init() {
        this.progressBar = document.getElementById('progressBar');
        this.progressFill = document.getElementById('progressFill');
        this.statusLabel = document.getElementById('statusLabel');
        this.statusDot = document.getElementById('statusDot');
    },

    setIndeterminate(active) {
        if (this.progressBar) this.progressBar.classList.toggle('indeterminate', active);
    },

    setProgress(percent) {
        if (this.progressFill) this.progressFill.style.width = `${percent}%`;
    },

    setStatus(text) {
        if (this.statusLabel) this.statusLabel.textContent = text;
    },

    // 状态点（D2026-0930-09 批2）：idle 灰 / running 蓝
    setDot(state) {
        if (!this.statusDot) return;
        this.statusDot.classList.toggle('dot-running', state === 'running');
        this.statusDot.classList.toggle('dot-idle', state !== 'running');
    },

    reset() {
        this.setIndeterminate(false);
        this.setProgress(0);
        this.setStatus(MSG.idle);
        this.setDot('idle');
    }
};

// ============================================================
// System Summary（D2026-1001 批3：右栏系统状态摘要卡，全部只读现成接口）
// 每接口独立降级：任一失败仅该行显示"不可用"，不拖垮右栏布局
// ============================================================
const SystemSummary = {
    load() {
        // 批3 扩展（D2026-1002-12）：角色卡/ASR 两行动态渲染（FROZEN_IDS 已满，
        // 行与控件零新增静态 id，经 data-sys-row 定位）
        this._ensureDynamicRows();
        // 2.6.5 段2（D2026-1004-01 #2 两行式改版）：版本入标题行 stat 槽；
        // TM/词典统计值升 keyrow 右 stat 槽，路径值独立成行完整折行；
        // 悬停 title 全文兜底移除（折行后不再截断，无需悬停）
        this._set('sysSummaryVersion', async () => {
            const r = await pywebview.api.get_version();
            return (r && r.success) ? r.version : null;
        });
        this._setPath('sysSummaryDataRoot', async () => {
            const r = await pywebview.api.refine_get_data_root();
            return (r && r.success && r.data_root) ? r.data_root : null;
        });
        this._setStatPath('sysSummaryTm', async () => {
            const r = await pywebview.api.tm_get_stats();
            if (!r || !r.success) return null;
            // 收口件①延续：行标签已是"翻译记忆库"（静态键），stat 槽只放
            // 统计值，不拼 tm_enable_label 前缀防重复
            return {
                stat: `${r.total || 0} 条 · 命中 ${r.total_hits || 0} 次`,
                val: r.db_path || '—'
            };
        });
        this._setStatPath('sysSummaryDict', async () => {
            const r = await pywebview.api.refine_dict_status();
            if (!r || !r.success || !r.dicts) return null;
            // 修复A：分母取 DICT_KINDS 桥接值（防 manifest 增 kind 时前端漂移/漏改）
            const kinds = Object.values(r.dicts);
            const ok = kinds.filter(d => d && d.available).length;
            const total = window.AppDictKindsCount || kinds.length;
            return {
                stat: `${ok}/${total} ${MSG.dict_status_available}`,
                val: r.effective_dir || '—'
            };
        });
        this._loadRoles();
    },

    // 2.6.5 段2（D2026-1004-01 #2 折行策略红线）：路径值安全写入——按
    // 分隔符拆分、TextNode + <wbr> 安全 DOM 构建（overflow-wrap:anywhere
    // 兜底 + 分隔符处优先断行）；禁 innerHTML、禁 U+200B（wbr 不入剪贴板）
    _setPathValue(el, text) {
        el.textContent = '';
        const parts = String(text).split(/([\\/]+)/);
        parts.forEach((part, i) => {
            el.appendChild(document.createTextNode(part));
            // 奇数位=分隔符（捕获组），其后插 wbr 提供优先断点
            if (i % 2 === 1 && i < parts.length - 1) {
                el.appendChild(document.createElement('wbr'));
            }
        });
    },

    async _set(id, fn) {
        const el = document.getElementById(id);
        if (!el) return;
        let text = MSG.sys_summary_unavailable;
        try {
            const v = await fn();
            if (v !== null && v !== undefined && v !== '') text = v;
        } catch (e) {
            console.warn('SystemSummary[' + id + ']:', e);
        }
        this._setPathValue(el, text);
    },

    // 2.6.5 段2（D2026-1004-01 #2）：纯路径行（无 stat 槽）——数据保存目录
    async _setPath(id, fn) {
        await this._set(id, fn);
    },

    // 2.6.5 段2（D2026-1004-01 #2）：stat+路径双槽行——fn 返回 {stat, val}，
    // 统计值写 keyrow 右 stat 槽（mono 11px），路径写全宽值行；降级时
    // stat 清空、值行显示"不可用"
    async _setStatPath(id, fn) {
        const el = document.getElementById(id);
        if (!el) return;
        const row = el.closest('.sys-summary-row');
        const stat = row ? row.querySelector('.sys-summary-stat') : null;
        let valText = MSG.sys_summary_unavailable;
        let statText = '';
        try {
            const v = await fn();
            if (v && typeof v === 'object') {
                valText = v.val || MSG.sys_summary_unavailable;
                statText = v.stat || '';
            }
        } catch (e) {
            console.warn('SystemSummary[' + id + ']:', e);
        }
        this._setPathValue(el, valText);
        if (stat) stat.textContent = statText;
    },

    // 批3 扩展（D2026-1002-12）：角色卡行 + ASR 行动态渲染——
    // 行样式复用 .sys-summary-row，标签复用既有静态键文案（JS 态取值，
    // 不挂 data-i18n：applyI18n 首屏已跑完，动态节点收不到）；
    // 2.6.5 段2（D2026-1004-01 #2）：两行式改版——角色卡统计值（N 张）
    // 升 keyrow 右 stat 槽、路径独立值行；ASR 探测按钮与 .sys-summary-stat
    // 同处 keyrow（弱化语义 val-muted 迁 stat，该行不再用 val）；
    // ASR 行「重新探测」小按钮不带 id，事件委托绑在卡上（见 bindDom）
    _ensureDynamicRows() {
        const card = document.getElementById('systemSummaryCard');
        if (!card || card.querySelector('[data-sys-row="roles"]')) return;
        const roles = document.createElement('div');
        roles.className = 'sys-summary-row';
        roles.dataset.sysRow = 'roles';
        roles.innerHTML = '<div class="sys-summary-keyrow">'
            + '<span class="sys-summary-key"></span>'
            + '<span class="sys-summary-stat"></span></div>'
            + '<div class="sys-summary-val"></div>';
        roles.querySelector('.sys-summary-key').textContent
            = MSG.templates_dir_label;
        card.appendChild(roles);
        const asr = document.createElement('div');
        asr.className = 'sys-summary-row';
        asr.dataset.sysRow = 'asr';
        asr.innerHTML = '<div class="sys-summary-keyrow">'
            + '<span class="sys-summary-key"></span>'
            + '<span class="sys-summary-stat val-muted"></span>'
            + '<button type="button" class="btn btn-ghost btn-compact"'
            + ' data-sys-action="asr-probe"></button></div>';
        asr.querySelector('.sys-summary-key').textContent = MSG.sys_asr_row_label;
        asr.title = MSG.asr_panel_title;
        asr.querySelector('button').textContent = MSG.asrRefreshBtn;
        card.appendChild(asr);
        asr.querySelector('.sys-summary-stat').textContent
            = MSG.sys_asr_undetected;
    },

    // 批3 扩展（D2026-1002-12）：角色卡目录行（复用 refine_list_templates，
    // 只读零写路径）；统计值="N 张"+pkg_fallback 标注内置回落（stat 槽），
    // 目录独立值行 wbr 折行（悬停 title 兜底随折行策略移除）
    async _loadRoles() {
        const row = document.querySelector(
            '#systemSummaryCard [data-sys-row="roles"]');
        if (!row) return;
        const val = row.querySelector('.sys-summary-val');
        const stat = row.querySelector('.sys-summary-stat');
        if (!val) return;
        let text = MSG.sys_summary_unavailable;
        let statText = '';
        try {
            const r = await pywebview.api.refine_list_templates(null);
            if (r && r.success) {
                const tag = r.pkg_fallback ? `（${MSG.sys_roles_fallback}）` : '';
                statText = `${MSG.sys_roles_count((r.files || []).length)}${tag}`;
                text = r.dir || '—';
            }
        } catch (e) {
            console.warn('SystemSummary[roles]:', e);
        }
        this._setPathValue(val, text);
        if (stat) stat.textContent = statText;
    },

    // 批3 扩展（D2026-1002-12）：ASR 行显式探测（首屏不自动探测——上游
    // selfcheck 慢，避免卡首屏）；成功="就绪 · 已存模型名/未配置"，
    // 失败透出原因（复用 asr 相关既有键文案）。
    // 2.6.5 段2（D2026-1004-01 #2）：探测结果改写 keyrow 右 stat 槽
    async probeAsr() {
        const row = document.querySelector(
            '#systemSummaryCard [data-sys-row="asr"]');
        if (!row) return;
        const stat = row.querySelector('.sys-summary-stat');
        const btn = row.querySelector('[data-sys-action="asr-probe"]');
        if (btn) btn.disabled = true;
        if (stat) stat.textContent = '…';
        try {
            const r = await pywebview.api.refine_asr_status();
            let text;
            if (!r || !r.success) {
                text = MSG.asrProbeFail((r && r.error) || MSG.unknown);
            } else if (r.available) {
                text = MSG.sys_asr_ready(
                    r.model_present && r.saved_model
                        ? r.saved_model : MSG.sys_asr_unconfigured);
                if (stat) stat.classList.remove('val-muted');
            } else {
                text = MSG.asrProbeFail(r.reason || '');
            }
            if (stat) stat.textContent = text;
        } catch (e) {
            // 收口件②：异常分支不走裸 e.message，与失败分支同口径包 asrProbeFail
            const text = MSG.asrProbeFail(
                (e && e.message) || MSG.unknown);
            if (stat) stat.textContent = text;
        } finally {
            if (btn) btn.disabled = false;
        }
    }
};

// ============================================================
// TM 搜索区块（2.6.4 批1，D2026-1003-05 策略 B）：词库与模板页只读
// 全文检索。index.html 冻结零改动（FROZEN_IDS=213 / 静态 i18n 既有钉
// 零消耗）：区块全 createElement + class/dataset 承载（零新增静态
// id/data-i18n），文案走 MSG JS 态键，结果渲染全 textContent（禁
// innerHTML，查询词/库内容均为外部输入），错误与空态界面可见
// （吞错可见化纪律），经 window.pywebview.api.tm_search 只读查询。
// ============================================================
const TmSearch = {
    // 首次打开词库页时注入整块（.tm-search-block 定位，防重复注入）
    ensure() {
        const page = document.getElementById('tab-glossary');
        if (!page || page.querySelector('.tm-search-block')) return;
        const block = document.createElement('div');
        block.className = 'stack tm-search-block';
        block.style.marginTop = '10px';
        const title = document.createElement('div');
        title.className = 'block-title';
        title.textContent = MSG.tmSearchTitle;
        block.appendChild(title);
        // 搜索行：输入框 + 按钮 + 状态 span（回车与按钮均可触发）
        const row = document.createElement('div');
        row.className = 'action-row';
        const input = document.createElement('input');
        input.type = 'text';
        input.className = 'form-input compact grow tm-search-input';
        input.placeholder = MSG.tmSearchPlaceholder;
        input.autocomplete = 'off';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = 'btn btn-secondary btn-compact tm-search-btn';
        btn.textContent = MSG.tmSearchBtn;
        const status = document.createElement('span');
        status.className = 'muted tm-search-status';
        row.appendChild(input);
        row.appendChild(btn);
        row.appendChild(status);
        block.appendChild(row);
        // 结果表（表头四列）+ 空态引导行
        const table = document.createElement('table');
        table.className = 'gl-table tm-search-table';
        const thead = document.createElement('thead');
        const hrow = document.createElement('tr');
        [MSG.tmSearchColSource, MSG.tmSearchColTarget,
         MSG.tmSearchColStage, MSG.tmSearchColHits].forEach(label => {
            const th = document.createElement('th');
            th.textContent = label;
            hrow.appendChild(th);
        });
        thead.appendChild(hrow);
        table.appendChild(thead);
        const tbody = document.createElement('tbody');
        table.appendChild(tbody);
        const empty = document.createElement('div');
        empty.className = 'empty-guide tm-search-empty';
        empty.style.display = 'none';
        empty.textContent = MSG.tmSearchEmpty;
        block.appendChild(table);
        block.appendChild(empty);
        const run = () => this.run(input, status, tbody, empty, btn);
        btn.addEventListener('click', run);
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                run();
            }
        });
        page.appendChild(block);
    },

    // 只读查询 + 渲染：单元格全 textContent；失败/空结果状态可见
    async run(input, status, tbody, empty, btn) {
        const q = input.value.trim();
        btn.disabled = true;
        tbody.textContent = '';
        empty.style.display = 'none';
        status.textContent = MSG.tmSearchRunning;
        try {
            const r = await window.pywebview.api.tm_search(q, 50);
            if (!r || !r.success) {
                status.textContent = MSG.tmSearchFailed
                    + '：' + ((r && r.error) || MSG.unknown);
                return;
            }
            const results = r.results || [];
            status.textContent = MSG.tmSearchCount(results.length);
            if (!results.length) {
                empty.style.display = '';
                return;
            }
            for (const it of results) {
                const tr = document.createElement('tr');
                [it.source_text, it.target_text, it.stage, it.hit_count]
                    .forEach(val => {
                        const td = document.createElement('td');
                        td.textContent = (val === null || val === undefined)
                            ? '' : String(val);
                        tr.appendChild(td);
                    });
                tbody.appendChild(tr);
            }
        } catch (e) {
            status.textContent = MSG.tmSearchFailed + '：'
                + ((e && e.message) || String(e));
        } finally {
            btn.disabled = false;
        }
    }
};

// ============================================================
// Directory Controls (Destination section)
// ============================================================
const DirectoryControls = {
    _savedOutputDir: '',

    init() {
        document.getElementById('browseOutputBtn').addEventListener('click', () => this.browseOutput());
        document.getElementById('openOutputBtn').addEventListener('click', () => this.openOutput());

        const sourceCheckbox = document.getElementById('outputToSource');
        sourceCheckbox.addEventListener('change', () => this.toggleSourceOutput(sourceCheckbox.checked));
    },

    toggleSourceOutput(enabled) {
        const outputDirInput = document.getElementById('outputDir');
        const browseBtn = document.getElementById('browseOutputBtn');

        if (enabled) {
            this._savedOutputDir = outputDirInput.value;
            outputDirInput.value = 'source';
            AppState.outputDir = 'source';
            outputDirInput.disabled = true;
            browseBtn.disabled = true;
        } else {
            const restoreDir = this._savedOutputDir && this._savedOutputDir !== 'source'
                ? this._savedOutputDir
                : (AppState._fallbackOutputDir || AppState.outputDir);
            outputDirInput.value = restoreDir === 'source' ? '' : restoreDir;
            AppState.outputDir = restoreDir === 'source' ? '' : restoreDir;
            outputDirInput.disabled = false;
            browseBtn.disabled = false;
        }
    },

    async browseOutput() {
        try {
            const result = await pywebview.api.select_output_directory();

            if (result.success && result.path) {
                document.getElementById('outputDir').value = result.path;
                AppState.outputDir = result.path;
                ConsoleManager.log(MSG.outputDirSet(result.path), 'info');
            }
        } catch (error) {
            ErrorHandler.show(MSG.browseOutputError, error.toString());
        }
    },

    async openOutput() {
        let path = document.getElementById('outputDir').value;

        if (!path) {
            ErrorHandler.showWarning(MSG.noOutputDirTitle, MSG.noOutputDirHint);
            return;
        }

        // "source" is a sentinel meaning "save next to source file" -
        // resolve to the parent directory of the first selected file
        if (path === 'source' && AppState.selectedFiles.length > 0) {
            const firstFile = AppState.selectedFiles[0];
            const lastSlash = Math.max(firstFile.lastIndexOf('/'), firstFile.lastIndexOf('\\'));
            if (lastSlash > 0) {
                path = firstFile.substring(0, lastSlash);
            }
        }

        try {
            const result = await pywebview.api.open_output_folder(path, true);

            if (result.success) {
                ConsoleManager.log(MSG.folderOpened(path), 'info');
            } else {
                ErrorHandler.show(MSG.openFolderFailed, result.message);
            }
        } catch (error) {
            ErrorHandler.show(MSG.openFolderError, error.toString());
        }
    }
};

// ============================================================
// Translator Manager (净语翻译两阶段执行)
// ============================================================
const TranslatorManager = {
    state: {
        isRunning: false,
        progress: 0
    },

    init() {
        console.log('TranslatorManager initialized');
    },

    /**
     * Update Start/Cancel button states.
     * Called whenever the shared file list or run state changes.
     */
    updateButtons() {
        const hasFiles = AppState.selectedFiles.length > 0;
        const isRunning = this.state.isRunning;

        const startBtn = document.getElementById('refineStartBtn');
        const cancelBtn = document.getElementById('refineCancelBtn');
        if (startBtn) startBtn.disabled = !hasFiles || isRunning;
        if (cancelBtn) cancelBtn.disabled = !isRunning;
    },

    async startTranslation() {
        if (AppState.isRunning) return;

        if (AppState.selectedFiles.length === 0) {
            ErrorHandler.show(MSG.noFilesTitle, MSG.no_files_hint);
            return;
        }

        try {
            // collectOptions 抛错时按钮状态才能正常复位并提示
            const options = this.collectOptions();

            AppState.isRunning = true;
            this.state.isRunning = true;
            FileListManager.updateButtons();
            this.setProgress(0);
            this.setStatus(MSG.starting);
            ProgressManager.setDot('running');
            ProgressManager.setIndeterminate(true);

            // 断点恢复探测：三态 chip 初始点亮（D2026-0930-09 批2）+ 可恢复文件打到控制台
            if (AppState.selectedFiles.length > 0) {
                try {
                    const states = await pywebview.api.scan_resume_states(
                        AppState.selectedFiles.slice());
                    (states || []).forEach(s => {
                        if (!s || !s.path) return;
                        // state: completed|resumable|none -> done|resumable|pending
                        FileListManager.setState(
                            s.path,
                            s.state === 'completed' ? 'done'
                                : s.state === 'resumable' ? 'resumable'
                                    : 'pending');
                    });
                    const resumable = (states || [])
                        .filter(s => s && s.state === 'resumable');
                    if (resumable.length > 0) {
                        ConsoleManager.log(
                            MSG.resumable_found(resumable.length), 'info');
                        resumable.forEach(s =>
                            ConsoleManager.log(`   ↺ ${s.stem}`, 'info'));
                    }
                } catch (e) {
                    console.warn('scan_resume_states failed:', e);
                }
            }

            let result = await pywebview.api.start_translation(options);

            // 已有终稿产物：needs_confirm 时弹确认框（D2026-0925-01 D6）
            if (result && result.needs_confirm) {
                const ok = await AppModal.confirm(
                    MSG.overwriteConfirm(result.existing || []));
                if (!ok) {
                    // 用户取消：静默返回，仅复位按钮/状态
                    this.state.isRunning = false;
                    AppState.isRunning = false;
                    FileListManager.updateButtons();
                    ProgressManager.setIndeterminate(false);
                    ProgressManager.setDot('idle');
                    this.setStatus(MSG.idle);
                    return;
                }
                options.force = true;
                result = await pywebview.api.start_translation(options);
            }

            if (result.success) {
                ConsoleManager.log(MSG.translationStarted(result.pid), 'info');
                this.startStatusPolling();
            } else {
                throw new Error(result.error || MSG.startFailed);
            }
        } catch (error) {
            ConsoleManager.log(MSG.translationErrorLog(error.message), 'error');
            ErrorHandler.show(MSG.translationErrorTitle, error.message);
            this._finish(MSG.error);
        }
    },

    async cancelTranslation() {
        try {
            const result = await pywebview.api.cancel_translation();
            if (result && result.success) {
                ConsoleManager.log(MSG.cancelledLog, 'warning');
                // 状态轮询会检测到进程退出并收尾；此处立即恢复按钮避免竞态窗口
                this._finish(MSG.cancelled);
            } else {
                ConsoleManager.log((result && result.error) || MSG.unknownError,
                    'warning');
            }
        } catch (error) {
            console.error('Error cancelling translation:', error);
        }
    },

    _finish(statusText) {
        this.stopStatusPolling();
        this._reportedRiskCount = 0;
        this.state.isRunning = false;
        AppState.isRunning = false;
        FileListManager.updateButtons();
        ProgressManager.setIndeterminate(false);
        ProgressManager.setDot('idle');
        this.setStatus(statusText);
    },

    // ---- Status polling ----

    startStatusPolling() {
        this._reportedRiskCount = 0;
        this.statusInterval = setInterval(async () => {
            try {
                const status = await pywebview.api.get_translation_status();

                // 状态栏：阶段名（current_stage）优先，叠加当前文件（current_file）
                let text = '';
                if (status.current_stage) text = status.current_stage;
                if (status.current_file &&
                    (!text || !status.current_file.includes(text))) {
                    text = text ? `${text} · ${status.current_file}` : status.current_file;
                }
                // 心跳超时且仍在运行：追加最近活动提示
                // （阈值来自后端配置 heartbeat_stale_s 分层解析结果，缺省 45s ≈ 2.25×心跳间隔 20s）
                const staleS = (typeof status.heartbeat_stale_s === 'number')
                    ? status.heartbeat_stale_s : 45;
                if (status.status === 'running' &&
                    status.heartbeat_age != null && status.heartbeat_age > staleS) {
                    const secs = Math.round(status.heartbeat_age);
                    text = `${text || MSG.running}${MSG.still_running(secs)}`;
                }
                // 风险计数
                if (status.risk_count > 0) {
                    text = `${text || MSG.running}${MSG.risk_suffix(status.risk_count)}`;
                }
                if (text) this.setStatus(text);

                // 三态 chip 实时点亮（D2026-0930-09 批2 档1）：basename join，未命中的不回退
                if (status.files_status) {
                    FileListManager.applyStates(status.files_status);
                }

                // 风险明细：仅在数量增长时把新增条目追加到控制台
                const reported = this._reportedRiskCount || 0;
                if (status.risk_count > reported) {
                    const risks = status.risks || [];
                    const fresh = risks.slice(
                        Math.max(0, risks.length - (status.risk_count - reported)));
                    fresh.forEach(r => {
                        const where = r.phase ? `（${r.phase}）` : '';
                        ConsoleManager.log(
                            `⚠️ ${where}${r.message || r.type || MSG.risk_word}`, 'warning');
                    });
                    this._reportedRiskCount = status.risk_count;
                }

                if (status.progress !== undefined && status.progress > 0) {
                    ProgressManager.setIndeterminate(false);
                    this.setProgress(status.progress);
                }

                this.fetchLogs();

                if (status.status === 'completed') {
                    this.setProgress(100);
                    if (status.untranslated_majority) {
                        ErrorHandler.show(MSG.untranslated_title,
                            MSG.untranslated_hint);
                    } else if (status.warning_level) {
                        const level = status.warning_level === 'critical'
                            ? MSG.level_critical : MSG.level_warning;
                        ConsoleManager.log(
                            MSG.completed_with_risks(level, status.risk_count || 0),
                            'warning');
                    } else {
                        ConsoleManager.log(MSG.completedLog, 'success');
                        ErrorHandler.showSuccess(MSG.completed_title, MSG.completed_detail);
                    }
                    if (typeof this.guideAutoDetect === 'function') this.guideAutoDetect();
                    this._finish(MSG.completed);
                } else if (status.status === 'error') {
                    ConsoleManager.log(MSG.translationErrorLog(status.error), 'error');
                    ErrorHandler.show(MSG.translationFailedTitle,
                        status.error || MSG.unknownError);
                    this._finish(MSG.error);
                } else if (status.status === 'cancelled') {
                    this._finish(MSG.cancelled);
                }
            } catch (error) {
                console.error('Status poll error:', error);
            }
        }, 1000);
    },

    stopStatusPolling() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
    },

    async fetchLogs() {
        try {
            const logs = await pywebview.api.get_translation_logs();
            if (logs && logs.length > 0) {
                logs.forEach(line => {
                    const cleanLine = line.replace(/\n$/, '');
                    if (cleanLine) {
                        ConsoleManager.appendRaw(cleanLine);
                    }
                });
            }
        } catch (error) {
            console.error('Error fetching logs:', error);
        }
    },

    setProgress(percent) {
        this.state.progress = percent;
        ProgressManager.setProgress(percent);
    },

    setStatus(text) {
        ProgressManager.setStatus(text);
    }
};

// ============================================================
// Theme Manager (runtime stylesheet switching with persistence)
// ============================================================
const ThemeManager = {
    storageKey: 'subtransjav_theme',
    themes: { 'default': 'style.css', 'dark': 'style.dark.css' },

    init() {
        this.linkEl = document.getElementById('themeStylesheet');
        if (!this.linkEl) {
            console.warn('ThemeManager: #themeStylesheet not found; falling back to style.css');
            return;
        }

        const saved = this.getSavedTheme();
        this.applyTheme(saved);

        const btn = document.getElementById('themeBtn');
        const menu = document.getElementById('themeMenu');
        if (btn && menu) {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                menu.classList.toggle('active');
                if (menu.classList.contains('active')) {
                    const first = menu.querySelector('.theme-option');
                    if (first) first.focus();
                }
            });

            document.addEventListener('click', (e) => {
                if (menu.classList.contains('active')) {
                    menu.classList.remove('active');
                }
            });

            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    menu.classList.remove('active');
                }
            });

            menu.querySelectorAll('.theme-option').forEach(opt => {
                opt.addEventListener('click', (e) => {
                    const theme = opt.dataset.theme;
                    this.applyTheme(theme);
                    menu.classList.remove('active');
                });
            });
        }
    },

    getSavedTheme() {
        try {
            const key = localStorage.getItem(this.storageKey) || 'default';
            return this.themes[key] ? key : 'default';
        } catch (e) {
            return 'default';
        }
    },

    saveTheme(key) {
        try {
            localStorage.setItem(this.storageKey, key);
        } catch (e) {
            // ignore（private_mode 下 localStorage 不可用，仅后端持久化生效）
        }
        // A3 主题持久化走后端（main.py private_mode=True：用户设置一律走
        // 后端文件）：settings KV 键 theme；桥不可用时静默降级（仅
        // localStorage 生效）
        try {
            const p = window.pywebview && pywebview.api
                ? pywebview.api.refine_save_stage_settings(null, null,
                    { theme: key })
                : null;
            if (p && typeof p.catch === 'function') p.catch(() => {});
        } catch (e) {
            // 桥不可用时静默降级
        }
    },

    applyTheme(key) {
        if (!this.linkEl) return;
        const href = this.themes[key] || this.themes['default'];
        this.linkEl.setAttribute('href', href);
        // 阶段2 批1（D2026-0930-09）：主题按钮双图标显隐同步
        //（dark=显示 sun、隐藏 moon；浅色反之。仅切图标，不动持久化逻辑）
        const dark = (key in this.themes ? key : 'default') === 'dark';
        const moonIcon = document.getElementById('iconMoon');
        const sunIcon = document.getElementById('iconSun');
        if (moonIcon) moonIcon.style.display = dark ? 'none' : '';
        if (sunIcon) sunIcon.style.display = dark ? '' : 'none';
        this.saveTheme(key in this.themes ? key : 'default');
        ConsoleManager.log(MSG.themeSwitched(key), 'info');
    },

    // A3：pywebviewready 后读取后端 settings.theme 并应用
    //（早于该时机的 ThemeManager.init 保持 localStorage/默认主题现状）
    async loadSavedThemeFromBackend() {
        try {
            const r = await pywebview.api.refine_get_stage_settings();
            const t = (r && r.success && r.settings) ? r.settings.theme : null;
            if (t && this.themes[t]) {
                this.applyTheme(t);
            }
        } catch (e) {
            // 静默降级：后端无存档/读取失败时保持现状默认
        }
    }
};

// ============================================================
// Keyboard Shortcuts
// ============================================================
const KeyboardShortcuts = {
    init() {
        document.addEventListener('keydown', async (e) => {
            // Ctrl+O: Add files
            if (e.ctrlKey && e.key === 'o') {
                e.preventDefault();
                FileListManager.addFiles();
            }

            // Ctrl+R: Start translation
            if (e.ctrlKey && e.key === 'r') {
                e.preventDefault();
                if (!AppState.isRunning && AppState.selectedFiles.length > 0) {
                    TranslatorManager.startTranslation();
                }
            }

            // Escape: Close modal
            if (e.key === 'Escape') {
                const modal = document.getElementById('aboutModal');
                if (modal && modal.classList.contains('active')) {
                    closeAbout();
                }
            }

            // F1: Show About dialog
            if (e.key === 'F1') {
                e.preventDefault();
                showAbout();
            }

            // F5: Refresh with warning
            if (e.key === 'F5') {
                if (AppState.isRunning) {
                    // preventDefault 必须保持在首个 await 之前同步执行（防默认刷新先跑）
                    e.preventDefault();
                    const ok = await AppModal.confirm(MSG.confirm_reload);
                    if (ok) {
                        location.reload();
                    }
                }
            }
        });
    }
};

// ============================================================
// About Dialog
// ============================================================
async function showAbout() {
    const modal = document.getElementById('aboutModal');
    const versionEl = document.getElementById('aboutVersion');

    try {
        const result = await pywebview.api.get_version();
        if (result.success) {
            versionEl.textContent = `Version ${result.version}`;
        }
    } catch (e) {
        console.warn('Could not fetch version:', e);
    }

    modal.classList.add('active');
}

function closeAbout() {
    const modal = document.getElementById('aboutModal');
    modal.classList.remove('active');
}

// ============================================================
// v1.5 左侧 TAB 导航（SmartSub 式）：按 data-tab 切换主内容区页面，
// 选中态同步到 TAB 按钮（accent 高亮）与对应页面（.tab-page.active）
// ============================================================
function switchTab(tabId) {
    document.querySelectorAll('.side-tab-btn').forEach(btn => {
        const on = btn.dataset.tab === tabId;
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    document.querySelectorAll('.tab-page').forEach(page => {
        page.classList.toggle('active', page.id === tabId);
    });
    // 词库页初始化钩子（D2026-0930-07-追加1 必要⑧）：打开 tab-glossary 时
    // 动态填充角色卡下拉并加载当前选中项（refine IIFE 未加载时静默跳过）
    if (tabId === 'tab-glossary' && typeof window.__refineTplTabHook === 'function') {
        try { window.__refineTplTabHook(); } catch (e) { /* 初始化失败不阻断切页 */ }
    }
    // TM 搜索区块懒注入（2.6.4 批1）：首次打开词库页 createElement 注入
    // 整块（index.html 冻结零改动；失败不阻断切页，对齐上方钩子姿势）
    if (tabId === 'tab-glossary' && typeof TmSearch === 'object') {
        try { TmSearch.ensure(); } catch (e) { /* 初始化失败不阻断切页 */ }
    }
    // ASR 卡懒探测（2.7.1 D2026-1005-01）：首次打开 ASR 与词典页时读探测
    // 快照立即渲染（快照由首启空闲探测回填；强制刷新走「重新探测」按钮）
    if (tabId === 'tab-asrdict' && typeof window.__asrTabHook === 'function') {
        try { window.__asrTabHook(); } catch (e) { /* 初始化失败不阻断切页 */ }
    }
}

// ===== Refine UI：模型刷新/测试 + 词库表格编辑器 + 角色卡编辑器 =====
(function () {
  if (window.__refineUI) return;
  window.__refineUI = true;

  function $(id) { return document.getElementById(id); }
  function esc(s) {
    return String(s == null ? '' : s).replace(/"/g, '&quot;')
      .replace(/&/g, '&amp;').replace(/</g, '&lt;');
  }

  // 服务商默认接口地址（切换服务商时自动填充到该阶段的地址栏）
  const REFINE_PROVIDER_URLS = {
    lmstudio: 'http://localhost:1234/v1',
    ollama: 'http://localhost:11434/v1',
    zen: 'https://opencode.ai/zen/v1',
    deepseek: 'https://api.deepseek.com/v1',
    siliconflow: 'https://api.siliconflow.cn/v1',
    custom: ''
  };

  // 每阶段独立的接口地址输入框
  function stageEndpoint(n) {
    const v = ($('refineS' + n + 'Endpoint') || {}).value;
    return v && v.trim() ? v.trim() : '';
  }

  // 指定服务商当前使用的接口地址：优先取使用该服务商的阶段地址栏，否则用默认
  function stageEndpointFor(prov) {
    for (const n of [1, 3]) {
      if ((($('refineS' + n + 'Provider') || {}).value) === prov) {
        const ep = stageEndpoint(n);
        if (ep) return ep;
      }
    }
    return REFINE_PROVIDER_URLS[prov] || '';
  }

  // 服务商切换 → 该阶段地址栏自动填充对应默认地址
  function applyProviderEndpoint(n) {
    const prov = ($('refineS' + n + 'Provider') || {}).value;
    const ep = $('refineS' + n + 'Endpoint');
    if (!ep) return;
    ep.value = REFINE_PROVIDER_URLS[prov] || '';
    ep.disabled = (prov === 'deepseek');
    if (prov === 'deepseek') ep.value = '';
    ep.placeholder = prov === 'deepseek'
      ? MSG.ep_deepseek_placeholder : MSG.ep_placeholder;
    // ollama 地址同样可编辑（与 lmstudio 一致，placeholder 提示默认端口）
  }

  // 每阶段独立 API Key（LM Studio 无需；留空则后端回退到已保存密钥）
  function stageKeyOrNull(n) {
    const v = ($('refineS' + n + 'Key') || {}).value;
    return v && v.trim() ? v.trim() : null;
  }

  // 取指定服务商在阶段行里填写的第一个非空密钥（随启动参数传给子进程）
  function stageKeyFor(prov) {
    for (const n of [1, 3]) {
      if ((($('refineS' + n + 'Provider') || {}).value) === prov) {
        const k = stageKeyOrNull(n);
        if (k) return k;
      }
    }
    return '';
  }

  // 行内状态提示（每阶段自己的 span）
  function stageStatus(n, text, kind) {
    const st = $('refineTestS' + n + 'Status');
    if (!st) return;
    st.style.color = kind === 'err' ? 'var(--status-err)' : (kind === 'ok' ? 'var(--status-ok)' : 'var(--text-muted)');
    st.textContent = text;
  }

  // ---- 并行度读取（1-5，非法/缺省回退1）----
  function readRefineConcurrency() {
    let n = parseInt(($('refineConcurrency') || {}).value, 10);
    if (!Number.isFinite(n)) n = 1;
    return Math.max(1, Math.min(5, n));
  }

  // ---- 上下文窗口读取（A1 缺省重绑定：显式合法值才传；空/非法/<4096
  // 返回 null=不传，走后端缺省 16384；管线会按生效值对齐引擎）----
  function readRefineCtx() {
    let n = parseInt(($('refineV2Ctx') || {}).value, 10);
    if (!Number.isFinite(n) || n < 4096) return null;
    return n;
  }

  // ---- 正整数读取（A5：空/非法/0/负数返回 null=不传，后端缺省接管；
  // 替代 parseInt(v)||30 形态——0 会被吞成缺省值）----
  function readPositiveInt(id) {
    let n = parseInt(($(id) || {}).value, 10);
    return (Number.isFinite(n) && n > 0) ? n : null;
  }

  // ---- 启动选项收集器（v2 两阶段：阶段A→s1 槽位，阶段B→s3 槽位）----
  function buildRefineOptions() {
    return {
      inputs: AppState.selectedFiles,
      output_dir: $('outputDir') ? $('outputDir').value : '',
      profile: ($('refineProfile') || {}).value || 'local',
      v2_concurrency: readRefineConcurrency(),
      v2_ctx: readRefineCtx(),
      s1_provider: ($('refineS1Provider') || {}).value,
      s1_model: ($('refineS1Model') || {}).value || '',
      s3_provider: ($('refineS3Provider') || {}).value,
      s3_model: ($('refineS3Model') || {}).value || '',
      templates_dir: ($('refineTemplatesDir') || {}).value || '',
      glossary: ($('refineGlossary') || {}).value || '',
      custom_key: stageKeyFor('custom'),
      zen_key: stageKeyFor('zen'),
      siliconflow_key: stageKeyFor('siliconflow'),
      deepseek_key: stageKeyFor('deepseek'),
      apply_glossary_stage1: !($('refineGl1') && !$('refineGl1').checked),
      apply_glossary_stage2: !($('refineGl2') && !$('refineGl2').checked),
      batch_local: readPositiveInt('refineBatchLocal'),
      batch_cloud: readPositiveInt('refineBatchCloud'),
      lmstudio_endpoint: stageEndpointFor('lmstudio'),
      ollama_endpoint: stageEndpointFor('ollama'),
      zen_endpoint: stageEndpointFor('zen'),
      siliconflow_endpoint: stageEndpointFor('siliconflow'),
      custom_endpoint: stageEndpointFor('custom'),
      fallback_local: !!($('refineFallbackLocal') || {}).checked,
      fallback_model: (($('refineFallbackModel') || {}).value || '').trim(),
      cleaner_config_dir: (($('refineCleanerConfig') || {}).value || '').trim(),
      resume: !!($('resumeToggle') && $('resumeToggle').checked),
      // 强制断点恢复：--force-resume 隐含 --resume 由 RefineConfig.__post_init__ 保证，前端只传一个键
      force_resume: !!($('refineForceResume') || {}).checked,
      // 学习闸开关：默认 false 不拼旗标（api.py 侧按需转 --glossary-learn / --glossary-conflict-block）
      glossary_learn: !!($('refineGlossaryLearn') || {}).checked,
      glossary_conflict_block: !!($('refineGlossaryConflictBlock') || {}).checked,
      verbose: !!($('debugLogging') || {}).checked,
      source_filter: (($('refineSourceFilter') || {}).value || 'default'),
      auto_synopsis: !($('refineAutoSynopsis') && !$('refineAutoSynopsis').checked),
      // H4b 条目级阈值自适应：默认不勾选不传旗标（api.py 侧按需转 --adaptive-thresholds）
      adaptive_thresholds: !!($('refineAdaptiveThresholds') || {}).checked,
      // 翻译记忆库：勾选取消时才传 no_tm（--no-tm）；路径/阈值非空才传
      no_tm: !!($('refineTmEnable') && !$('refineTmEnable').checked),
      tm_db: (($('refineTmDb') || {}).value || '').trim(),
      tm_threshold: (($('refineTmThreshold') || {}).value || '').trim(),
      // 2.1 翻译方向（D2026-0930-04 定案①）：缺省 ja/zh 由 api 侧过滤
      // 不产生旗标；指令卡路径有值才传（缺卡由 CLI validate 报错）
      source_lang: ($('directionSource') || {}).value || '',
      target_lang: ($('directionTarget') || {}).value || '',
      s1_instructions: (($('directionCardS1') || {}).value || '').trim(),
      s3_instructions: (($('directionCardS3') || {}).value || '').trim()
    };
  }

  TranslatorManager.collectOptions = buildRefineOptions;
  TranslatorManager.guideAutoDetect = guideAutoDetect;

  // ---- 已存模型名（批2 D2026-1002-12 拍板点2：删 custom-model-1/2 前端
  // 硬默认，模型下拉不再有"默认模型"语义——仅认用户显式保存过的值）----
  // 更新时机：applySavedStageSettings 回填 / saveStageEndpoints 保存成功；
  // 消费时机：refreshModels 成功后命中列表则恢复选中，未命中才提示更换
  //（default_model_missing 警告的唯一触发源）；无已存值不预选不出警告
  const savedStageModels = { 1: '', 3: '' };

  // 模型下拉空态占位 option（批2 D2026-1002-12）：value 空 + disabled +
  // selected，文案走 JS 态键 model_list_empty_hint；HTML 初始骨架 /
  // 切服务商重置 / 拉取失败恢复共用同一形态
  function modelEmptyOptionHTML() {
    return '<option value="" disabled selected>'
      + MSG.model_list_empty_hint + '</option>';
  }

  // ---- 模型列表刷新 ----
  async function refreshModels(n) {
    const prov = ($('refineS' + n + 'Provider') || {}).value;
    const btn = $('refineRefreshS' + n);
    const sel = $('refineS' + n + 'Model');
    if (!btn || !sel) return;
    if (!prov) { stageStatus(n, MSG.select_provider_first, 'err'); return; }
    btn.disabled = true;
    const old = btn.innerHTML; btn.textContent = '…';   // innerHTML 保存：按钮含内联 SVG，textContent 会丢图标（D2026-1001 批2）
    // 保留 HTML 空态占位 option，失败/异常时恢复，避免下拉被清空
    const originalHTML = sel.innerHTML;
    sel.innerHTML = '<option value="">' + MSG.loading_models + '</option>';
    stageStatus(n, MSG.fetching_models, '');
    try {
      const r = await pywebview.api.refine_list_models(
        prov, stageEndpoint(n), stageKeyOrNull(n));
      if (r.success && r.models.length) {
        sel.innerHTML = r.models.map(m =>
          '<option value="' + esc(m) + '">' + esc(m) + '</option>').join('');
        let warn = '';
        if (prov === 'zen') {
          const free = r.models.filter(x => x.endsWith('-free'));
          if (free.length) sel.value = free[0]; else sel.selectedIndex = 0;
        } else if (savedStageModels[n]
                   && r.models.includes(savedStageModels[n])) {
          // 已存模型命中刷新所得列表：恢复选中（老用户无感）
          sel.value = savedStageModels[n];
        } else if (savedStageModels[n]) {
          // 已存值与刷新所得列表不匹配：优先选第一个非嵌入模型，避免误选
          // text-embedding-*，并提示更换（default_model_missing 唯一触发源）
          const opts = Array.from(sel.options || []);
          const nonEmbed = opts.find(o =>
            !(o.value || '').toLowerCase().startsWith('text-embedding'));
          sel.value = nonEmbed ? nonEmbed.value : sel.options[0].value;
          warn = MSG.default_model_missing(savedStageModels[n], sel.value);
        }
        // 无已存值：不预选任何模型（列表首项自然显示）、不出警告
        stageStatus(n, warn || MSG.models_loaded(r.models.length),
                    warn ? '' : 'ok');
      } else {
        sel.innerHTML = originalHTML;
        stageStatus(n, '❌ ' + (r.error || MSG.fetch_failed) + (r.tip ? ' · ' + r.tip : ''), 'err');
      }
    } catch (e) {
      sel.innerHTML = originalHTML;
      stageStatus(n, '❌ ' + e, 'err');
    } finally {
      btn.disabled = false; btn.innerHTML = old;
    }
  }

  // ---- 接管模型列表刷新 ----
  async function refreshFallbackModels() {
    const sel = $('refineFallbackModel');
    const btn = $('refreshFallbackModels');
    if (!sel || !btn) return;

    // 获取 LM Studio endpoint（从阶段A的 lmstudio 配置中读取）
      const endpoint = stageEndpointFor('lmstudio') || 'http://localhost:1234/v1';

    btn.disabled = true;
    const old = btn.innerHTML; btn.textContent = '…';   // innerHTML 保存：按钮含内联 SVG，textContent 会丢图标（D2026-1001 批2）
    try {
      const r = await pywebview.api.list_local_models(endpoint);
      if (r.success && r.models.length) {
        const cur = sel.value;
        // A2 兜底重绑定：保留空值默认项（"不自动兜底"），用户未显式
        // 选择接管模型时不强塞本地模型
        sel.innerHTML = '<option value="">' + MSG.fallback_no_auto + '</option>'
          + r.models.map(m =>
            '<option value="' + esc(m) + '">' + esc(m) + (r.loaded.includes(m) ? ' ✓' : '') + '</option>').join('');
        // 尝试保持之前选中的值
        if (cur && r.models.includes(cur)) sel.value = cur;
      } else {
        // 保留默认选项
      }
    } catch (e) {
      // 静默失败，保留现有选项
    } finally {
      btn.disabled = false; btn.innerHTML = old;
    }
  }

  // 页面加载时自动刷新接管模型列表
  document.addEventListener('DOMContentLoaded', function() {
    setTimeout(refreshFallbackModels, 1000);
  });

  // ---- 单阶段测试 ----
  async function testStage(n) {
    const prov = ($('refineS' + n + 'Provider') || {}).value;
    const model = ($('refineS' + n + 'Model') || {}).value;
    const st = $('refineTestS' + n + 'Status');
    const btn = $('refineTestS' + n);
    if (!btn) return;
    btn.disabled = true;
    if (st) { st.style.color = 'var(--text-muted)'; st.textContent = MSG.testing; }
    try {
      const r = await pywebview.api.refine_test_stage(
        prov, model, stageEndpoint(n), stageKeyOrNull(n));
      if (st) {
        st.style.color = r.success ? 'var(--status-ok)' : 'var(--status-err)';
        st.textContent = (r.success ? '✅ ' : '❌ ') +
          (r.success ? r.message : (r.tip || r.error || MSG.failed));
      }
      if (!r.success && r.tip) console.warn('[refine]', r.tip);
    } catch (e) {
      if (st) { st.style.color = 'var(--status-err)'; st.textContent = '❌ ' + e; }
    } finally {
      btn.disabled = false;
    }
  }

  function glStatus(t) {
    const el = $('refineGlStatus');
    if (el) { el.style.color = 'var(--text-muted)'; el.textContent = t; }
  }

  // ---- 词库表格 ----
  function glRows() {
    const rows = [];
    document.querySelectorAll('#refineGlossTable tbody tr').forEach(tr => {
      const i = tr.querySelector('input.gl-src');
      const o = tr.querySelector('input.gl-dst');
      if (i && o && i.value.trim() && o.value.trim())
        rows.push([i.value.trim(), o.value.trim()]);
    });
    return rows;
  }

  function glRender(rows) {
    const tb = document.querySelector('#refineGlossTable tbody');
    tb.innerHTML = rows.map(r =>
      '<tr>' +
      '<td><input class="form-input compact gl-src" value="' + esc(r[0]) + '"></td>' +
      '<td><input class="form-input compact gl-dst" value="' + esc(r[1]) + '">' +
      // 别名第三列只读展示（不由前端编辑；无别名不渲染，保存时后端保留）
      (r[2] ? '<div class="gl-alias">' + MSG.alias_label +
        esc(r[2]) + '</div>' : '') + '</td>' +
      '<td class="gl-sel-cell"><input type="checkbox" class="gl-sel"></td>' +
      '</tr>').join('');
    const cnt = $('refineGlCount');
    if (cnt) cnt.textContent = rows.length;
    const eh = $('glEmptyHint');
    if (eh) eh.style.display = rows.length ? 'none' : '';
  }

  async function glLoad() {
    try {
      const d = await pywebview.api.refine_default_paths();
      if (d.success) {
        if ($('refineGlossary'))
          $('refineGlossary').value = d.glossary_path;
        if ($('refineTemplatesDir')) {
          $('refineTemplatesDir').value = d.templates_dir;
          const show = $('refineTemplatesDirShow');
          if (show) show.value = d.templates_dir;
        }
        const p = $('refineGlossary') ? $('refineGlossary').value : '';
        const gp = $('refineGlPath');
        if (gp) gp.textContent = p;
      }
      const g = $('refineGlossary') ? $('refineGlossary').value : '';
      if (!g) return;
      const r = await pywebview.api.refine_get_glossary(g);
      if (r.success) glRender(r.rows);
    } catch (e) { console.warn('[refine] 词库加载失败', e); }
  }

  // 学习词库只读查看（config/glossary_learned.csv；自学习产物，优先级低于全局词库）
  async function glLearnedLoad() {
    const st = $('glLearnedStatus');
    const stats = $('glLearnedStats');
    const empty = $('glLearnedEmpty');
    const more = $('glLearnedMore');
    const tb = document.querySelector('#glLearnedTable tbody');
    if (!tb) return;
    try {
      const r = await window.pywebview.api.refine_get_learned_glossary();
      if (!r || r.success === false) {
        if (st) st.textContent = MSG.gl_learned_load_failed(
          (r && r.error) || MSG.unknown);
        return;
      }
      if (st) st.textContent = '';
      if (!r.exists) {
        tb.innerHTML = '';
        if (stats) stats.textContent = '';
        if (more) more.style.display = 'none';
        if (empty) empty.style.display = '';
        return;
      }
      if (empty) empty.style.display = 'none';
      const rows = r.rows || [];
      tb.innerHTML = rows.map(row =>
        '<tr>' +
        '<td>' + esc(row.source || '') + '</td>' +
        '<td>' + esc(row.target || '') + '</td>' +
        '<td>' + esc(row.aliases || '') + '</td>' +
        '</tr>').join('');
      if (stats) {
        stats.textContent = MSG.gl_learned_stats(
          r.count != null ? r.count : rows.length,
          r.total != null ? r.total : rows.length);
      }
      if (more) {
        const rest = (r.total || 0) - rows.length;
        more.textContent = rest > 0 ? MSG.gl_learned_more(rest) : '';
        more.style.display = rest > 0 ? '' : 'none';
      }
    } catch (e) {
      if (st) st.textContent = MSG.gl_learned_load_failed(
        e && e.message ? e.message : String(e));
    }
  }

  async function glSave() {
    const r = await pywebview.api.refine_save_glossary(
      glRows(), $('refineGlossary') ? $('refineGlossary').value : null);
    glStatus(r.success ? MSG.gl_saved(r.count) : '❌ ' + r.error);
  }

  async function glAdd() {
    const src = await AppModal.prompt(MSG.gl_prompt_src);
    if (!src || !src.trim()) return;
    const dst = await AppModal.prompt(MSG.gl_prompt_dst(src.trim()));
    if (!dst || !dst.trim()) return;
    const rows = glRows().filter(r => r[0] !== src.trim());
    rows.push([src.trim(), dst.trim()]);
    glRender(rows);
  }

  async function glDel() {
    document.querySelectorAll('#refineGlossTable tbody tr').forEach(tr => {
      const cb = tr.querySelector('.gl-sel');
      if (cb && cb.checked) tr.remove();
    });
    const cnt = $('refineGlCount');
    if (cnt) cnt.textContent = glRows().length;
    await glSave();
  }

  async function glImport() {
    const pick = await pywebview.api.refine_pick_csv_open();
    if (!pick.success) return;
    const r = await pywebview.api.refine_get_glossary(pick.path);
    if (!r.success) { glStatus('❌ ' + r.error); return; }
    // 合并基准 = 文件中的既有词条（权威来源），而非 DOM 表格
    const target = $('refineGlossary') ? $('refineGlossary').value : null;
    let merged = [];
    try {
      const baseR = await pywebview.api.refine_get_glossary(target || null);
      if (baseR && baseR.success) merged = baseR.rows;
    } catch (e) { console.warn('[refine] 读取既有词库失败，将仅导入所选文件', e); }
    const have = new Set(merged.map(x => x[0]));
    let added = 0;
    r.rows.forEach(row => {
      if (!have.has(row[0])) { merged.push(row); have.add(row[0]); added++; }
    });
    glRender(merged);
    glStatus(MSG.gl_imported(added));
    await pywebview.api.refine_save_glossary(merged, target || null);
  }

  async function glExport() {
    const pick = await pywebview.api.refine_pick_csv_save();
    if (!pick.success) return;
    const r = await pywebview.api.refine_save_glossary(glRows(), pick.path);
    glStatus(r.success ? MSG.gl_exported(r.count, r.path) : '❌ ' + r.error);
  }

  // ---- 角色卡编辑器 ----
  // 下拉动态化（D2026-0930-07-追加1 范围定稿2）：refineTemplateStage 的
  // 选项由后端 refine_list_templates 动态填充（canonical A/B 精确匹配
  // V2_TEMPLATE_FILES 文件名排最前并带阶段标注，其余文件按文件名列示，
  // "所见即所编"）；目录空/pkg_fallback 回落固定 A/B 两项（MSG 渲染，
  // HTML 骨架不留裸中文）。readdir 结果是外部输入 → 渲染全量 esc()。
  let tplDirState = null;   // 最近一次 refine_list_templates 结果缓存

  function tplRenderOptions(r) {
    const sel = $('refineTemplateStage');
    if (!sel) return;
    const files = (r && r.success && Array.isArray(r.files)) ? r.files : [];
    const canon = (r && r.success && r.canonical) || {};
    const items = [];
    if (files.length) {
      // canonical 精确匹配（复合后缀卡如 角色-净语翻译.en2zh.txt 不是 canonical）
      for (const tag of Object.keys(canon)) {
        if (files.some(f => f.name === canon[tag])) {
          items.push({ value: tag, label: MSG['tpl_stage_' + tag.toLowerCase()] });
        }
      }
      for (const f of files) {
        if (Object.values(canon).indexOf(f.name) !== -1) continue;
        items.push({ value: f.name, label: f.name });
      }
    } else {
      // 目录空 → 回落固定 A/B 两项（JS 按 MSG 渲染）
      items.push({ value: 'A', label: MSG.tpl_stage_a });
      items.push({ value: 'B', label: MSG.tpl_stage_b });
    }
    const prev = sel.value;
    sel.innerHTML = items.map(it =>
      '<option value="' + esc(it.value) + '">' + esc(it.label) + '</option>'
    ).join('');
    if (prev && items.some(it => it.value === prev)) sel.value = prev;
  }

  // 高级参数页 #directionCardS1/#directionCardS3 的 datalist（范围定稿3、
  // 建议⑩）：option value=完整路径（目录+文件名）、不带 label；自由输入
  // 与空=自动查找语义不变。空目录注入一条 disabled 提示项。
  function tplRenderDatalist(r) {
    const dl = $('directionCardList');
    if (!dl) return;
    const files = (r && r.success && Array.isArray(r.files)) ? r.files : [];
    const dir = (r && r.success && r.dir) || '';
    if (!files.length) {
      dl.innerHTML = '<option value="" disabled>' + esc(MSG.tpl_dir_empty_datalist) + '</option>';
      return;
    }
    const sep = dir.indexOf('\\') !== -1 ? '\\' : '/';
    dl.innerHTML = files.map(f =>
      '<option value="' + esc(dir ? dir + sep + f.name : f.name) + '">'
    ).join('');
  }

  // 打开词库页（switchTab 钩子）/点"重新加载"/启动时：列目录 → 填下拉
  // 与 datalist；load=true 时按当前选中项加载（选中即加载 load-by-name）。
  async function tplRefreshSelect(load) {
    const dir = $('refineTemplatesDir') ? $('refineTemplatesDir').value : '';
    const st = $('refineTemplateStatus');
    try {
      const r = await pywebview.api.refine_list_templates(dir || null);
      tplDirState = r;
      tplRenderOptions(r);
      tplRenderDatalist(r);
      if (st && r && r.success && r.pkg_fallback) {
        st.style.color = 'var(--status-warn, #b8860b)';
        st.textContent = MSG.tpl_dir_empty_hint;
      }
    } catch (e) {
      // 列举失败也回落固定 A/B，编辑器不空转
      tplDirState = null;
      tplRenderOptions(null);
      tplRenderDatalist(null);
    }
    if (load) tplLoad();
  }

  async function tplLoad() {
    const sel = $('refineTemplateStage');
    const idx = (sel || {}).value;
    const dir = $('refineTemplatesDir') ? $('refineTemplatesDir').value : '';
    const st = $('refineTemplateStatus');
    // 非 'A'/'B' 值 = 动态填充的文件名选项 → load-by-name（必要⑤）
    const isStageTag = idx === 'A' || idx === 'B';
    try {
      const r = isStageTag
        ? await pywebview.api.refine_get_template(idx, dir)
        : await pywebview.api.refine_get_template(idx, dir, idx);
      if (r.success) {
        $('refineTemplateText').value = r.text;
        if (st) {
          st.style.color = 'var(--text-muted)';
          st.textContent = (r.note ? '📌 ' + r.note + '  ' : '') + r.path;
        }
        const lp = $('refineTplLoadedPath');
        if (lp) lp.textContent = MSG.tpl_loaded_path(r.path);
      } else if (st) {
        st.style.color = 'var(--status-err)'; st.textContent = r.error;
      }
    } catch (e) { if (st) st.textContent = '❌ ' + e; }
  }

  // 2.5.0 修复D：高级参数阶段A/B 角色卡"去编辑"跳转——两分支写死：
  // 显式卡路径父目录恰为模板服务端目录且文件名∈refine_list_templates 返回集
  // （"目录内"定义，子目录属目录外）=跳词库页+编辑器精确打开（canonical→
  // 下拉 tag 值映射）；目录外=降级跳词库页+定位角色卡目录+状态行提示
  async function tplGotoEdit(stage) {
    const inp = $('directionCard' + stage);
    const p = ((inp && inp.value) || '').trim();
    switchTab('tab-glossary');
    const st = $('refineTemplateStatus');
    if (!p) {
      if (st) {
        st.style.color = '';
        st.textContent = MSG.tpl_goto_empty_hint;
      }
      tplRefreshSelect(false);
      return;
    }
    // 列举刷新（显式路径可能刚填，缓存或已过期）
    const dir = $('refineTemplatesDir') ? $('refineTemplatesDir').value : '';
    let listing = tplDirState;
    try {
      listing = await pywebview.api.refine_list_templates(dir || null);
      tplDirState = listing;
      tplRenderOptions(listing);
      tplRenderDatalist(listing);
    } catch (e) { listing = null; }
    const files = (listing && listing.success && Array.isArray(listing.files))
      ? listing.files : [];
    const canon = (listing && listing.success && listing.canonical) || {};
    const serverDir = (listing && listing.success && listing.dir) || '';
    const norm = (s) => String(s || '').replace(/\//g, '\\').toLowerCase();
    const parentDir = p.replace(/[\\/][^\\/]*$/, '');
    const fileName = p.split(/[\\/]/).pop() || '';
    const inDir = serverDir && norm(parentDir) === norm(serverDir)
      && files.some(f => f.name === fileName);
    if (!inDir) {
      if (st) {
        st.style.color = 'var(--status-warn, #b8860b)';
        st.textContent = MSG.tpl_goto_outside_hint;
      }
      const show = $('refineTemplatesDirShow');
      if (show) show.focus();   // 定位角色卡目录
      return;
    }
    // 目录内：canonical→tag 映射（A/B tag）或动态文件名选项精确打开
    const tag = Object.keys(canon).find(t => canon[t] === fileName);
    const sel = $('refineTemplateStage');
    if (sel && (tag || files.some(f => f.name === fileName))) {
      sel.value = tag || fileName;
    }
    tplLoad();
  }

  // 2.6.3 批D（D2026-1003-01 P5）：tplSave 改为 AppModal.editor 的 onSave
  // 实现（入参 (stage, text) 由模态传入，缺省回落 DOM 现值；返回
  // {ok, message} 供模态收口：成功清脏+自动关闭，失败弹窗保持）。
  // refine_save_template 四参形态（isStageTag ? null : idx）保持函数钉不变；
  // 保存后按显式卡路径动态提示回落语义（原提示逻辑保留，随 message 回传，
  // 由模态统一写 #refineTemplateStatus 与入口摘要）。
  async function tplSave(stage, text) {
    const idx = (stage != null && stage !== '') ? stage
      : (($('refineTemplateStage') || {}).value);
    const isStageTag = idx === 'A' || idx === 'B';
    const ta = $('refineTemplateText');
    const bodyText = (text != null) ? text : ((ta || {}).value || '');
    let r = null;
    try {
      r = await pywebview.api.refine_save_template(
        idx, bodyText,
        $('refineTemplatesDir') ? $('refineTemplatesDir').value : null,
        isStageTag ? null : idx);
    } catch (e) {
      r = { success: false, error: String(e) };
    }
    if (r && r.success) {
      const savedName = (r.path || '').split(/[\\/]/).pop() || '';
      const c1 = (($('directionCardS1') || {}).value || '').trim();
      const c3 = (($('directionCardS3') || {}).value || '').trim();
      const sameName = [c1, c3].some(v =>
        v && (v.split(/[\\/]/).pop() || '') === savedName);
      const hint = sameName ? MSG.tpl_save_hint_explicit
        : (!c1 && !c3) ? MSG.tpl_save_hint_auto : '';
      return { ok: true, message: (r.path || '') + (hint ? ' ' + hint : '') };
    }
    return { ok: false, message: (r && r.error) || MSG.unknownError };
  }

  // 2.6.3 批D：编辑器入口（词库页+高级参数页两枚 .tpl-editor-entry-btn）——
  // 先列目录+按选中加载（高级页直达时下拉可能尚未初始化），再迁节点开模态。
  // 弹窗内「重新加载/切阶段」经 onStageChange 走原链路（reload=tplRefreshSelect
  // 列目录+加载；change=tplLoad 按当前选中加载，语义同原 bindDom 直绑）。
  async function openTplEditor() {
    if (AppModal._busy) return;
    await tplRefreshSelect(true);
    AppModal.editor({
      title: MSG.tplEditorTitle,
      onSave: tplSave,
      onStageChange: (stage, mode) =>
        (mode === 'reload' ? tplRefreshSelect(true) : tplLoad()),
      onDiscard: () => { tplLoad(); }   // 放弃=按当前阶段重载（丢未保存修改）
    });
  }

  async function pickDir() {
    // 批1a 件3：角色卡目录对话框收口——输入框只读回显（手输不提交），
    // 仅本按钮经原生对话框变更；purpose='templates' 让后端把选择
    // 持久化为角色卡目录（user_dirs.json），重启仍生效。
    const r = await pywebview.api.refine_pick_folder('templates');
    if (r.success && r.path) {
      $('refineTemplatesDir').value = r.path;
      const show = $('refineTemplatesDirShow');
      if (show) show.value = r.path;
      tplRefreshSelect(true);
    }
  }

  async function pickCleanerDir() {
    const r = await pywebview.api.refine_pick_folder();
    if (r.success && r.path) {
      $('refineCleanerConfig').value = r.path;
      const show = $('refineCleanerConfigShow');
      if (show) show.value = r.path;
      saveCleanerDir();   // 程序性赋值不触发 change，显式持久化
    }
  }

  async function openDir(path) {
    if (!path) {
      ConsoleManager.log(MSG.dir_not_set, 'warning');
      return;
    }
    try {
      const r = await pywebview.api.open_output_folder(path, false);
      if (r.success) {
        ConsoleManager.log(MSG.dir_opened(path), 'info');
      } else {
        ConsoleManager.log(MSG.dir_open_failed(r.message), 'error');
      }
    } catch (e) {
      ConsoleManager.log(MSG.dir_open_error(e), 'error');
    }
  }

  // ---- 保存/读取 每阶段服务商+接口地址+密钥 ----
  async function saveStageKey(n) {
    const prov = ($('refineS' + n + 'Provider') || {}).value;
    const key = stageKeyOrNull(n) || '';
    if (!prov) { stageStatus(n, MSG.provider_required, 'err'); return; }
    if (prov === 'lmstudio') { stageStatus(n, MSG.lmstudio_no_key, ''); return; }
    if (prov === 'ollama') { stageStatus(n, MSG.ollama_no_key, ''); return; }
    try {
      const r = await pywebview.api.refine_save_stage_settings(null,
        [{ stage: n, provider: prov, key: key }]);
      if (r.success) {
        stageStatus(n, key ? MSG.key_saved(prov) : MSG.key_cleared, 'ok');
        const inp = $('refineS' + n + 'Key');
        if (inp) { inp.value = ''; inp.placeholder = key ? MSG.key_saved_placeholder : inp.placeholder; }
      } else {
        stageStatus(n, '❌ ' + r.error, 'err');
      }
    } catch (e) { stageStatus(n, '❌ ' + e, 'err'); }
  }

  async function saveStageEndpoints() {
    const st = $('refineEndpointStatus');
    const stages = [];
    for (const n of [1, 3]) {
      stages.push({
        stage: n,
        provider: ($('refineS' + n + 'Provider') || {}).value || '',
        endpoint: stageEndpoint(n),
        model: ($('refineS' + n + 'Model') || {}).value || ''
      });
    }
    try {
      const r = await pywebview.api.refine_save_stage_settings(stages, null,
        { v2_concurrency: readRefineConcurrency(),
          // A1：留空存空串（回填侧 parseInt('')=NaN 忽略），null 由后端
          // 跳过不入库——空串即可覆盖清除旧存档值
          v2_ctx: readRefineCtx() || '' });
      if (r.success) {
        // 批2（D2026-1002-12）：保存成功即更新已存模型名（refreshModels
        // 恢复选中的唯一依据，与后端 settings 保持同源）
        savedStageModels[1] = stages[0].model;
        savedStageModels[3] = stages[1].model;
      }
      if (st) {
        st.style.color = r.success ? 'var(--status-ok)' : 'var(--status-err)';
        st.textContent = r.success
          ? MSG.endpoints_saved + MSG.resume_fingerprint_hint
          : '❌ ' + r.error;
      }
    } catch (e) {
      if (st) { st.style.color = 'var(--status-err)'; st.textContent = '❌ ' + e; }
    }
  }

  async function applySavedStageSettings() {
    try {
      const r = await pywebview.api.refine_get_stage_settings();
      if (!r.success) return;
      // v1.5 用户模式选择器已取消：画像回填（模式记忆/首启默认）随之删除，
      // 初始安装即默认参数（全部自定义收进左侧 TAB 页）
      // 回填并行度（1-5，越界忽略；缺省时保持控件默认值1）
      if (r.settings && r.settings.v2_concurrency != null) {
        const n = parseInt(r.settings.v2_concurrency, 10);
        const sel = $('refineConcurrency');
        if (sel && n >= 1 && n <= 5) sel.value = String(n);
      }
      // 回填上下文窗口（非法/缺省保持控件默认值）
      if (r.settings && r.settings.v2_ctx != null) {
        const c = parseInt(r.settings.v2_ctx, 10);
        const ctxEl = $('refineV2Ctx');
        if (ctxEl && Number.isFinite(c) && c >= 4096) ctxEl.value = String(c);
      }
      for (const s of (r.stages || [])) {
        const n = parseInt(s.stage);
        if (!n || n < 1 || n > 4) continue;
        const pv = $('refineS' + n + 'Provider');
        const ep = $('refineS' + n + 'Endpoint');
        if (pv && s.provider) pv.value = s.provider;
        if (ep && s.endpoint) ep.value = s.endpoint;
        else if (ep && !ep.value) applyProviderEndpoint(n);
        // 批2（D2026-1002-12 拍板点2）：记录已存模型名作为恢复依据；
        // 无列表状态（空态占位）下注入标记 option 显示已存名并选中
        // （老用户无感）——不匹配警告仅保留给"刷新所得列表"场景
        if (n === 1 || n === 3) {
          savedStageModels[n] = (s.model || '').trim();
          if (savedStageModels[n]) {
            const sel = $('refineS' + n + 'Model');
            if (sel && ![...sel.options].some(o => o.value === savedStageModels[n])) {
              const marker = document.createElement('option');
              marker.value = savedStageModels[n];
              marker.textContent = savedStageModels[n];
              sel.appendChild(marker);
            }
            if (sel) sel.value = savedStageModels[n];
          }
        }
      }
      for (const n of [1, 3]) {
        const ep = $('refineS' + n + 'Endpoint');
        if (ep && !ep.value) applyProviderEndpoint(n);
        const prov = ($('refineS' + n + 'Provider') || {}).value;
        if (prov && r.key_status && r.key_status[prov]) {
          const inp = $('refineS' + n + 'Key');
          if (inp && prov !== 'lmstudio' && prov !== 'ollama')
            inp.placeholder = MSG.key_saved_placeholder;
        }
      }
      // v1.5 翻译服务快捷下拉回填（settings KV 键 service_quick）+ key 行联动
      if (r.settings && r.settings.service_quick && $('refineServiceQuick')) {
        $('refineServiceQuick').value = String(r.settings.service_quick);
      }
      // 2.1 翻译方向（D2026-0930-04 定案①）：回填方向与配套指令卡路径
      // （缺省 ja/zh/空——控件 HTML selected 即缺省，缺键不动）
      if (r.settings) {
        const dSrc = $('directionSource');
        const dTgt = $('directionTarget');
        if (dSrc && r.settings.direction_source) {
          dSrc.value = String(r.settings.direction_source);
        }
        if (dTgt && r.settings.direction_target) {
          dTgt.value = String(r.settings.direction_target);
        }
        const dC1 = $('directionCardS1');
        if (dC1 && r.settings.direction_card_s1 != null) {
          dC1.value = String(r.settings.direction_card_s1);
        }
        const dC3 = $('directionCardS3');
        if (dC3 && r.settings.direction_card_s3 != null) {
          dC3.value = String(r.settings.direction_card_s3);
        }
        // 净语配置目录回填（空串=未指定，走自动查找回落链）
        const ccd = $('refineCleanerConfig');
        if (ccd && r.settings.cleaner_config_dir != null) {
          ccd.value = String(r.settings.cleaner_config_dir);
          const show = $('refineCleanerConfigShow');
          if (show) show.value = ccd.value;
        }
        // 2.4.0 S2 首启引导（HRO-1 翻转句）：first_run marker 一次性消费——
        // 显示横幅后立即写惰性 marker（refine_save_stage_settings 空参=静默
        // no-op 不落盘，必须带 settings 实参；first_run_seen 对现有消费端惰性
        // 零污染），os.makedirs+json.dump 建档 → 次启 first_run=false 确定性
        // 翻转；写回失败仅 console 告警留痕（次启重播属可接受降级）。
        // first_run 非 true 时零动作；横幅保留至用户点击关闭（不自动消失）
        // 2.5.0 批5（D2026-1001-07）：AI 分析独立配置回填+生效显示
        // （C3：AI 设置写入会建档 → first_run 折叠为 false，已显性入设计；
        //   跟随态不写键、独立态才写，最小化建档面）
        const aiProvSel = $('aiProviderSel');
        const aiModelInput = $('aiModelInput');
        if (aiProvSel) {
          aiProvSel.value = (r.settings.ai_analyze_provider) || 'follow';
          // 2.5.0 批5：option/label 中文走 MSG（HTML 留英文占位，防未收编中文钉）
          const provOpts = { follow: MSG.ai_prov_follow, lmstudio: MSG.ai_prov_lmstudio, ollama: MSG.ai_prov_ollama, deepseek: MSG.ai_prov_deepseek, siliconflow: MSG.ai_prov_siliconflow, zen: MSG.ai_prov_zen };
          [...aiProvSel.options].forEach(o => { if (provOpts[o.value]) o.textContent = provOpts[o.value]; });
          const lblP = document.querySelector('label[for="aiProviderSel"]');
          if (lblP) lblP.textContent = MSG.ai_cfg_provider_label;
          const lblM = document.querySelector('label[for="aiModelInput"]');
          if (lblM) lblM.textContent = MSG.ai_cfg_model_label;
        }
        if (aiModelInput) {
          aiModelInput.value = (r.settings.ai_analyze_model) || '';
          aiModelInput.placeholder = MSG.ai_model_placeholder;
        }
        // 2.6.0 批2 修订（D2026-1002-05）：跨片统计窗口三档（填充/恢复/保存）
        const aggWin = $('aggregateWindowSel');
        if (aggWin) {
          if (!aggWin.dataset.filled) {
            aggWin.dataset.filled = '1';
            const winOpts = { 7: MSG.aggregateWindow7, 30: MSG.aggregateWindow30, all: MSG.aggregateWindowAll };
            Object.keys(winOpts).forEach(k => {
              const o = document.createElement('option');
              o.value = k;
              o.textContent = winOpts[k];
              aggWin.appendChild(o);
            });
            const lblW = document.querySelector('label[for="aggregateWindowSel"]');
            if (lblW) lblW.textContent = MSG.aggregateWindowLabel;
            aggWin.addEventListener('change', () => {
              window.pywebview.api.refine_save_stage_settings(null, null,
                { tm_stats_window: aggWin.value });
            });
          }
          aggWin.value = (r.settings.tm_stats_window) || '30';
        }
        if (typeof aiRefreshEffective === 'function') aiRefreshEffective();
        if (aiProvSel && !aiProvSel.dataset.bound) {
          aiProvSel.dataset.bound = '1';
          const saveAiConfig = () => {
            window.pywebview.api.refine_save_stage_settings(null, null, {
              ai_analyze_provider: aiProvSel.value,
              ai_analyze_model: aiModelInput.value.trim()
            }).then(rv => {
              if (!rv || rv.success !== true) console.warn('[refine] AI 分析设置保存失败');
            }).catch(e => console.warn('[refine] AI 分析设置保存失败', e));
            aiRefreshEffective();
          };
          aiProvSel.addEventListener('change', saveAiConfig);
          aiModelInput.addEventListener('change', saveAiConfig);
        }
        if (r.settings.first_run === true) {
          const banner = $('firstRunBanner');
          if (banner) {
            const txt = banner.querySelector('.first-run-text');
            const closeBtn = banner.querySelector('.first-run-close');
            if (txt) txt.textContent = MSG.first_run_guide;
            if (closeBtn) {
              closeBtn.textContent = MSG.ui_ok;
              if (!closeBtn.dataset.bound) {
                closeBtn.dataset.bound = '1';
                closeBtn.addEventListener('click', () => { banner.style.display = 'none'; });
              }
            }
            banner.style.display = '';
            pywebview.api.refine_save_stage_settings(null, null, { first_run_seen: true })
              .then((s) => {
                if (!s || s.success !== true) {
                  console.warn('[refine] first_run_seen 翻转写回失败（次启将重播引导横幅）:',
                    s && s.error);
                }
              })
              .catch((e) => console.warn('[refine] first_run_seen 翻转写回异常:', e));
          }
        }
      }
      refreshServiceQuickRow();
    } catch (e) { console.warn('[refine] 读取已保存接口配置失败', e); }
  }

  // 2.1 翻译方向控件持久化（D2026-0930-04 定案①）：change 即写 settings
  // 顶层字典（direction_* 四键），程序性回填 .value 不触发 change 不打架
  function bindDirectionControls() {
    const saveDirection = () => {
      pywebview.api.refine_save_stage_settings(null, null, {
        direction_source: ($('directionSource') || {}).value || 'ja',
        direction_target: ($('directionTarget') || {}).value || 'zh',
        direction_card_s1: ($('directionCardS1') || {}).value || '',
        direction_card_s3: ($('directionCardS3') || {}).value || ''
      }).catch((e) => console.warn('[refine] 翻译方向保存失败', e));
    };
    // input 防抖兜底程序化赋值（自动填充等）不触发 change 的场景
    let t = null;
    const saveDebounced = () => {
      clearTimeout(t);
      t = setTimeout(saveDirection, 400);
    };
    for (const id of ['directionSource', 'directionTarget',
                      'directionCardS1', 'directionCardS3']) {
      const el = $(id);
      if (!el) continue;
      el.addEventListener('change', saveDirection);   // select 即时保存保留
      el.addEventListener('input', saveDebounced);    // text input 双通道
    }
  }

  // 净语配置目录持久化（批1 D2026-0930-07 bug 修复：浏览/输入值经
  // settings 键 cleaner_config_dir 保存，重启由 applySavedStageSettings
  // 回填；trim 后空串=未指定，后端走 config/templates→包内默认回落链）
  function saveCleanerDir() {
    pywebview.api.refine_save_stage_settings(null, null, {
      cleaner_config_dir: (($('refineCleanerConfig') || {}).value || '').trim()
    }).catch((e) => console.warn('[refine] 净语配置目录保存失败', e));
  }

  // 与方向控件同款双通道：change 即存 + input 400ms 防抖兜底
  // （show 输入框当前 readonly，input 通道为防御性保留）
  function bindCleanerDirControls() {
    let t = null;
    const saveDebounced = () => {
      clearTimeout(t);
      t = setTimeout(saveCleanerDir, 400);
    };
    for (const id of ['refineCleanerConfig', 'refineCleanerConfigShow']) {
      const el = $(id);
      if (!el) continue;
      el.addEventListener('change', saveCleanerDir);
      el.addEventListener('input', saveDebounced);
    }
  }

  // ---- 兜底档位（v2：local=strict / cloud=lenient，无 UI 联动需求）----

  // ---- v1.5 翻译服务快捷下拉（tab-translate 页；原小白模式顶栏迁入）----
  // 本地提示行联动：本地 lmstudio/ollama 显示启动提示行，云服务隐藏。
  // （API Key 填写已收口至「引擎与模型」TAB，主页不再提供 key 输入域）
  function refreshServiceQuickRow() {
    const prov = ($('refineServiceQuick') || {}).value || '';
    const cloud = (prov === 'deepseek' || prov === 'siliconflow'
      || prov === 'custom');
    const hint = $('refineServiceQuickLocalHint');
    if (hint) hint.style.display = cloud ? 'none' : '';
    return cloud;
  }

  // 服务快捷下拉联动：同步引擎页阶段A/B provider（写 stage A 并同步
  // stage B），endpoint 缺省沿用 applyProviderEndpoint 既有映射（不新造）；
  // 持久化复用 saveStageEndpoints 的 stages 数组通道 + settings KV 键
  // service_quick（v1.5 由旧小白模式持久化键改名；回填在
  // applySavedStageSettings / pywebviewready 链路）
  function applyServiceQuickProvider(persist) {
    const prov = ($('refineServiceQuick') || {}).value || 'lmstudio';
    for (const n of [1, 3]) {
      const pv = $('refineS' + n + 'Provider');
      if (pv) pv.value = prov;
      // 与引擎页 provider change 行为一致：重置模型下拉为空态占位并填充
      // 缺省地址（批2 D2026-1002-12 拍板点2：不自动拉取模型列表）
      const sel = $('refineS' + n + 'Model');
      if (sel) {
        sel.innerHTML = modelEmptyOptionHTML();
      }
      applyProviderEndpoint(n);
    }
    refreshServiceQuickRow();
    if (persist && window.__pywebviewReady) {
      saveStageEndpoints();
      try {
        const p = window.pywebview && pywebview.api
          ? pywebview.api.refine_save_stage_settings(null, null,
              { service_quick: prov })
          : null;
        if (p && typeof p.catch === 'function') p.catch(() => {});
      } catch (e) { /* 静默降级 */ }
    }
  }

  // 反向同步（批1 D2026-0930-07）：引擎页阶段A/B provider 变化后刷新
  // 快捷条显示——A/B 一致且为快捷条已知选项时跟随显示该值；否则置空
  // （中性态）。只改显示不写 settings：engine 页 provider 的持久化仍走
  // 「保存接口配置」按钮通道，service_quick 键仅在快捷条自身变更时写。
  function syncServiceQuickFromStages() {
    const quick = $('refineServiceQuick');
    if (!quick) return;
    const p1 = ($('refineS1Provider') || {}).value || '';
    const p3 = ($('refineS3Provider') || {}).value || '';
    const known = [...quick.options].some(o => o.value === p1);
    quick.value = (p1 && p1 === p3 && known) ? p1 : '';
    refreshServiceQuickRow();
  }

  // ---- 质量报告导读查看器（W1b：仅读 *_质量报告导读.json，不读 txt/全量 json）----
  const GUIDE_SUFFIX = '_质量报告导读.json';
  // 最近一次成功加载的导读路径（AI 分析按其 stem 推导质量报告 txt 路径）
  let lastLoadedGuidePath = '';
  // 最近一次成功加载的报告 txt 路径（双格式入口：AI 分析直接以其为入参）
  let lastLoadedReportTxtPath = '';
  // 最近一次加载的成品类型：'json' | 'txt'（决定 AI 分析取数来源）
  let lastLoadedIsTxt = false;
  // 最近一次 AI 分析的建议载荷（逐条落库时按下标取条目）
  let lastAiSuggestions = null;
  // 最近一次成功加载的导读数据（媒体来源条渲染依据）
  let lastGuideData = null;
  // 会话内媒体路径覆盖（等价 --media-path；仅显式输入，非空即优先生效）
  let mediaOverridePath = '';

  function guideStatus(text) {
    const st = $('guideStatus');
    if (st) st.textContent = text || '';
  }

  function guidePath() {
    const opts = buildRefineOptions();
    const first = (opts.inputs || [])[0] || '';
    if (!first) return '';
    const norm = String(first).replace(/\\/g, '/');
    const outDirRaw = (opts.output_dir || '').trim();
    const outDir = (!outDirRaw || outDirRaw === 'source')
      ? norm.slice(0, norm.lastIndexOf('/')) || '.'
      : outDirRaw;
    const stem = norm.slice(norm.lastIndexOf('/') + 1)
      .replace(/\.[^./]+$/, '')
      .replace(/\.(japanese|chinese|translated)$/, '');
    return outDir.replace(/[\\/]+$/, '') + '/' + stem + GUIDE_SUFFIX;
  }

  function guideRender(data) {
    // json 模式：显示结构化导读块，隐藏只读文本块（双格式互斥）
    const txtView = $('guideTxtView');
    const jsonBlocks = $('guideJsonBlocks');
    if (txtView) txtView.style.display = 'none';
    if (jsonBlocks) jsonBlocks.style.display = '';
    const ulC = $('guideConclusions');
    const dlS = $('guideSections');
    const ulP = $('guideCompanions');
    if (ulC) {
      ulC.innerHTML = (data.conclusions || [])
        .map(c => '<li>' + esc(c) + '</li>').join('')
        || '<li>' + MSG.no_conclusions + '</li>';
    }
    if (dlS) {
      dlS.innerHTML = (data.sections || [])
        .map(s => '<dt>' + esc(s.title) + '</dt><dd>' + esc(s.note) + '</dd>')
        .join('') || '<dt>' + MSG.no_sections + '</dt>';
    }
    const divI = $('guideItems');
    if (divI) {
      const items = Array.isArray(data.items) ? data.items : [];
      if (!items.length) {
        divI.innerHTML = '<div>' + MSG.guide_items_none + '</div>';
      } else {
        const MAX_ITEMS = 50;
        divI.innerHTML = items.slice(0, MAX_ITEMS).map(it => {
          const o = it || {};
          const cur = (o.current_text == null)
            ? MSG.guide_item_unresolvable
            : esc(String(o.current_text).slice(0, 80));
          // 快速试听（D2026-0929-09）：所有带 timing 的条目显示试听按钮；
          // suspected_missed_speech 条目默认高亮样式
          const isMissed = String(o.category || '')
            === 'suspected_missed_speech';
          const hasTiming = !!o.timing;
          return '<div class="guide-item'
            + (isMissed ? ' guide-item-missed' : '') + '">'
            + esc('#' + o.index) + ' [' + esc(o.category) + '] '
            + esc(o.timing) + '｜' + esc(o.message) + '｜'
            + MSG.guide_item_current_label + cur + '｜' + esc(o.status)
            + (hasTiming
              ? ' <button type="button" class="btn btn-ghost btn-sm'
                + ' btn-audio-preview" data-timing="' + esc(o.timing)
                + '">' + esc(MSG.preview_play_btn) + '</button>'
              : '')
            + '</div>';
        }).join('')
          + (items.length > MAX_ITEMS
            ? '<div>' + MSG.guide_items_more(items.length - MAX_ITEMS) + '</div>'
            : '');
      }
    }
    if (ulP) {
      const comp = data.companions || {};
      const keys = Object.keys(comp);
      ulP.innerHTML = keys.length
        ? keys.map(k => '<li>' + esc(k) + ' ' + (comp[k] ? '✓' : '✗') + '</li>').join('')
        : '<li>' + MSG.no_companions + '</li>';
    }
    const meta = $('guideMeta');
    if (meta) {
      meta.textContent = MSG.generated_at_label + (data.generated_at || MSG.unknown)
        + ' · ' + (data.basis || '');
    }
  }

  // customPath 传入时走「打开其他质量报告导读」：加载用户显式指定路径
  // （后端 read_output_artifact 白名单后缀 + 目录守卫，只读）；缺省走
  // guidePath 按输入/输出目录自动推导（只加载最近产出）
  async function guideLoad(silent, customPath) {
    if (!window.pywebview || !window.pywebview.api) {
      if (!silent) guideStatus(MSG.api_not_ready);
      return;
    }
    let p;
    const isCustom = customPath != null;
    if (isCustom) {
      // customPath 来自文件对话框选中结果（refine_pick_guide_json），
      // 后端 read_output_artifact 仍有白名单后缀 + 目录守卫兜底
      p = String(customPath).trim();
    } else {
      p = guidePath();
      if (!p) {
        if (!silent) guideStatus(MSG.guide_need_inputs);
        return;
      }
    }
    if (!silent || isCustom) guideStatus(MSG.guide_loading);
    if (isCustom) guideCustomStatus(MSG.guide_loading, false);
    try {
      const r = await window.pywebview.api.read_output_artifact(p);
      if (r && r.success) {
        // 修复C：载入新报告后清空旧 AI 分析结果——lastAiSuggestions=null
        // 防 aiApplyGlossary/aiApplyTm 把旧建议落进新报告对应的词库/TM
        // （错配消费），结果区 DOM 同步清零给用户可见反馈
        lastAiSuggestions = null;
        const air = $('refineAiResult');
        if (air) air.innerHTML = '';
        const dv = $('refineGuideViewer');
        if (dv) dv.open = true;
        const geh = $('guideEmptyHint');
        if (geh) geh.style.display = 'none';
        if (r.kind === 'txt') {
          // 报告 txt：只读文本块展示；AI 分析直接以该报告 stem 为入参
          lastLoadedReportTxtPath = r.path || p;
          lastLoadedIsTxt = true;
          guideRenderTxt(r);
          batchFixRefresh();
          guideStatus(MSG.guide_txt_loaded(r.path || p)
            + (r.truncated ? MSG.guide_txt_truncated_note : ''));
          if (isCustom) {
            guideCustomStatus(MSG.guide_txt_loaded(r.path || p)
              + (r.truncated ? MSG.guide_txt_truncated_note : ''), false);
          }
          return;
        }
        lastLoadedGuidePath = r.path || p;
        lastLoadedIsTxt = false;
        lastGuideData = r.data || {};
        updateMediaSourceBar(lastGuideData);
        guideRender(r.data || {});
        batchFixRefresh();
        guideStatus(MSG.guide_loaded(r.path || p));
        if (isCustom) guideCustomStatus(MSG.guide_loaded(r.path || p), false);
      } else {
        const err = MSG.guide_load_failed((r && r.error) || MSG.unknownError);
        guideStatus(err);
        if (isCustom) guideCustomStatus(err, true);
      }
    } catch (e) {
      const err = MSG.guide_load_failed(
        e && e.message ? e.message : String(e));
      guideStatus(err);
      if (isCustom) guideCustomStatus(err, true);
    }
  }

  // 报告 txt 只读文本块：等宽/可滚动/保留换行（CSS 类 guide-txt-view）
  function guideRenderTxt(r) {
    const txtView = $('guideTxtView');
    const jsonBlocks = $('guideJsonBlocks');
    if (jsonBlocks) jsonBlocks.style.display = 'none';
    if (txtView) {
      txtView.style.display = '';
      // textContent 赋值天然保留换行且免注入
      txtView.textContent = String(r.text || '');
    }
  }

  // 「打开其他质量报告导读」行内状态（成功灰色 / 失败红色）
  function guideCustomStatus(text, isError) {
    const st = $('guideCustomStatus');
    if (!st) return;
    st.textContent = text || '';
    st.style.color = isError ? 'var(--status-err)' : 'var(--text-muted)';
  }

  // 完成翻译后的静默自动探测：成功才展开面板，失败不打扰用户
  function guideAutoDetect() {
    guideLoad(true);
  }

  // ============================================================
  // 媒体来源条 + 快速试听（D2026-0929-09 视听对比第二阶段）
  // 媒体路径来源收窄（C-5 契约内选择）：导读 media_path（自动发现）
  // 或用户显式输入（等价 --media-path，会话内覆盖）；无文件对话框。
  // ============================================================

  function updateMediaSourceBar(data) {
    const bar = $('mediaSourceBar');
    if (!bar) return;
    const pathEl = $('mediaSourcePath');
    const tagEl = $('mediaSourceTag');
    if (!pathEl || !tagEl) return;
    const autoPath = String((data && data.media_path) || '');
    const autoIsOverride = String((data && data.media_path_source) || '')
      === 'override';
    const path = mediaOverridePath || autoPath;
    if (mediaOverridePath) {
      tagEl.textContent = MSG.media_source_explicit;
      pathEl.textContent = mediaOverridePath;
    } else if (autoPath) {
      tagEl.textContent = autoIsOverride
        ? MSG.media_source_explicit : MSG.media_source_auto;
      pathEl.textContent = autoPath;
    } else {
      tagEl.textContent = MSG.media_source_none;
      pathEl.textContent = '';
    }
    bar.style.display = '';
  }

  // "HH:MM:SS,mmm --> HH:MM:SS,mmm" → [start_s, end_s]；解析失败 null
  function timingToSeconds(timing) {
    const m = String(timing || '').match(
      /(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})/);
    if (!m) return null;
    const s = (+m[1]) * 3600 + (+m[2]) * 60 + (+m[3]) + (+m[4]) / 1000;
    const e = (+m[5]) * 3600 + (+m[6]) * 60 + (+m[7]) + (+m[8]) / 1000;
    return [s, e];
  }

  // 本地媒体文件 → file:// URL（逐段 encodeURIComponent，兼容空格/中文）
  function fileUrlOf(p) {
    return 'file:///' + String(p).replace(/\\/g, '/').split('/')
      .map(encodeURIComponent).join('/');
  }

  function showPreviewError(text) {
    const errEl = $('audioPreviewError');
    const player = $('audioPreviewPlayer');
    if (player) { player.src = ''; }
    if (errEl) {
      errEl.textContent = text;
      errEl.style.display = '';
    }
  }

  function closeAudioPreview() {
    const bar = $('audioPreviewBar');
    const player = $('audioPreviewPlayer');
    const errEl = $('audioPreviewError');
    if (player) { player.pause(); player.src = ''; }
    if (errEl) { errEl.style.display = 'none'; errEl.textContent = ''; }
    if (bar) bar.style.display = 'none';
    lastPreviewToken++;   // 在途请求返回后作废
  }

  // 请求序号：连续点击/关闭后旧响应不得覆盖新状态
  let lastPreviewToken = 0;

  async function openAudioPreview(timing) {
    const bar = $('audioPreviewBar');
    const player = $('audioPreviewPlayer');
    const timingEl = $('audioPreviewTiming');
    const errEl = $('audioPreviewError');
    if (!bar || !player || !timingEl || !errEl) return;
    if (!lastLoadedGuidePath) {
      bar.style.display = '';
      showPreviewError(MSG.audio_preview_no_guide);
      return;
    }
    const span = timingToSeconds(timing);
    if (!span) {
      bar.style.display = '';
      showPreviewError(MSG.audio_preview_no_timing);
      return;
    }
    errEl.style.display = 'none';
    errEl.textContent = '';
    timingEl.textContent = String(timing || '');
    player.src = '';
    bar.style.display = '';
    const token = ++lastPreviewToken;
    try {
      const r = await window.pywebview.api.refine_audio_preview(
        lastLoadedGuidePath, span[0], span[1], mediaOverridePath);
      if (token !== lastPreviewToken) return;
      if (r && r.ok && r.mode === 'direct' && r.media_path) {
        player.src = fileUrlOf(r.media_path);
        player.play().catch(() => {});
      } else if (r && r.ok && r.mode === 'clip' && r.data_url) {
        player.src = r.data_url;
        player.play().catch(() => {});
      } else {
        showPreviewError(MSG.audio_preview_failed(
          (r && r.error) || MSG.unknownError));
      }
    } catch (e) {
      if (token === lastPreviewToken) {
        showPreviewError(MSG.audio_preview_failed(
          e && e.message ? e.message : String(e)));
      }
    }
  }

  // ============================================================
  // AI 质量分析（D2026-0929：--ai-analyze 前后端接入）
  // ============================================================

  // 与 refreshServiceQuickRow / saveStageEndpoints 同源的云服务商口径
  const AI_CLOUD_PROVIDERS = ['deepseek', 'siliconflow', 'custom', 'zen'];

  function isAiCloudProvider(prov) {
    return AI_CLOUD_PROVIDERS.includes(String(prov || '').toLowerCase());
  }

  function aiStatus(text) {
    const st = $('refineAiAnalyzeStatus');
    if (st) st.textContent = text || '';
  }

  function aiReportPath() {
    // 双格式联动：用户显式加载的报告 txt 优先（stem 即用户自选报告），
    // 缺省仍按导读 json stem 推导（向后兼容）
    if (lastLoadedIsTxt) return lastLoadedReportTxtPath;
    const gp = lastLoadedGuidePath || guidePath();
    if (!gp) return '';
    return gp.replace(/_质量报告导读\.json$/, '_质量报告.txt');
  }

  function aiSetPrivacy(providerName) {
    const bar = $('refineAiPrivacy');
    if (!bar) return;
    if (isAiCloudProvider(providerName)) {
      bar.textContent = MSG.aiPrivacyCloud(providerName || MSG.unknown);
    } else {
      bar.textContent = MSG.aiPrivacyLocal;
    }
    bar.style.display = '';
  }

  function aiActionBtn(kind, idx, label) {
    return '<button type="button" class="btn btn-secondary btn-compact btn-sm"'
      + ' data-ai-kind="' + kind + '" data-ai-idx="' + idx + '">'
      + esc(label) + '</button>';
  }

  function aiConflictBadge() {
    return ' <span class="pill pill-warning" title="' + esc(MSG.aiConflictWarn)
      + '" style="cursor:help;">⚠️</span>';
  }

  function aiRenderResult(r) {
    const box = $('refineAiResult');
    if (!box) return;
    const sug = (r && r.suggestions) || {};
    // parse_ok=False → 整体降级为纯文本观察，不渲染任何可执行按钮
    if (!r.parse_ok) {
      box.innerHTML = '<h4>' + esc(MSG.aiParseFailed) + '</h4><ul>'
        + (sug.observations || []).map(o => '<li>' + esc(o) + '</li>').join('')
        + '</ul>';
      return;
    }
    const parts = [];
    // 一段：术语建议
    parts.push('<h4>' + esc(MSG.aiSectionGlossary) + '</h4>');
    parts.push('<table class="gl-table">'
      + '<thead><tr><th>' + esc(MSG.th_source)
      + '</th><th>' + esc(MSG.th_target)
      + '</th><th>' + esc(MSG.aiThReason)
      + '</th><th></th></tr></thead><tbody>');
    (sug.glossary || []).forEach((g, i) => {
      parts.push('<tr><td>' + esc(g.src) + '</td><td>' + esc(g.target)
        + '</td><td>' + esc(g.reason || '') + '</td><td>'
        + aiActionBtn('glossary', i, MSG.aiApplyGlossary) + '</td></tr>');
    });
    parts.push('</tbody></table>');
    // 二段：TM 建议（conflict_warn 行加黄色 ⚠️ 徽标）
    parts.push('<h4>' + esc(MSG.aiSectionTm) + '</h4>');
    parts.push('<table class="gl-table">'
      + '<thead><tr><th>' + esc(MSG.th_source)
      + '</th><th>' + esc(MSG.th_target)
      + '</th><th>' + esc(MSG.aiThReason)
      + '</th><th></th></tr></thead><tbody>');
    (sug.tm || []).forEach((t, i) => {
      parts.push('<tr><td>' + esc(t.source) + (t.conflict_warn
        ? aiConflictBadge() : '') + '</td><td>' + esc(t.target)
        + '</td><td>' + esc(t.reason || '') + '</td><td>'
        + aiActionBtn('tm', i, MSG.aiApplyTm) + '</td></tr>');
    });
    parts.push('</tbody></table>');
    // 三段：一般观察（纯文本，不可执行）
    parts.push('<h4>' + esc(MSG.aiSectionObs) + '</h4><ul>'
      + (sug.observations || []).map(o => '<li>' + esc(o) + '</li>').join('')
      + '</ul>');
    box.innerHTML = parts.join('');
    box.querySelectorAll('button[data-ai-kind]').forEach(btn => {
      btn.addEventListener('click', () => {
        const i = Number(btn.dataset.aiIdx) || 0;
        if (btn.dataset.aiKind === 'glossary') aiApplyGlossary(i, btn);
        else aiApplyTm(i, btn);
      });
    });
  }

  // 2.5.0 批5（D2026-1001-07）：AI 分析生效配置常驻显示（C1/C5：复用 refineAiPrivacy）
  function aiRefreshEffective() {
    const el = $('refineAiPrivacy');
    if (!el) return;
    const indep = ($('aiProviderSel') || {}).value || 'follow';
    const s1p = ($('refineS1Provider') || {}).value || 'lmstudio';
    const s1m = ($('refineS1Model') || {}).value || '';
    const im = ($('aiModelInput') || {}).value.trim();
    const cloud = window.AI_CLOUD_PROVIDERS || [];
    let prov, model, tag;
    if (indep === 'follow') { prov = s1p; model = s1m || '（未指定）'; tag = '跟随阶段A'; }
    else { prov = indep; model = im || '（未指定）'; tag = '独立配置'; }
    el.style.display = '';
    el.textContent = '分析模型：' + tag + ' — ' + prov + ' / ' + model
      + (cloud.includes(prov) ? ' ｜ 注意：分析时报告内容将发送至该云端服务' : '');
  }

  async function refineAiAnalyze() {
    if (!lastLoadedGuidePath && !lastLoadedIsTxt) {
      aiStatus(MSG.aiNeedGuide);
      return;
    }
    if (!window.pywebview || !window.pywebview.api) {
      aiStatus(MSG.api_not_ready);
      return;
    }
    const rp = aiReportPath();
    if (!rp || !rp.endsWith('_质量报告.txt')) {
      aiStatus(MSG.aiNeedGuide);
      return;
    }
    // 修复B+2.5.0 批5（D2026-1001-07）：生效 provider/model=独立配置优先，缺席跟随阶段A；
    // 云 provider 发送前确认读实际生效值（C1）
    const indepProv = (($('aiProviderSel') || {}).value || 'follow');
    const indepModel = (($('aiModelInput') || {}).value || '').trim();
    const effProvider = (indepProv === 'follow'
      ? (($('refineS1Provider') || {}).value || '').toLowerCase()
      : indepProv).toLowerCase();
    const model = (indepModel || (($('refineS1Model') || {}).value || '')).trim();
    if (AI_CLOUD_PROVIDERS.includes(effProvider)) {
      const go = await AppModal.confirm(MSG.aiCloudConfirm(effProvider));
      if (!go) return;
    }
    const btn = $('refineAiAnalyzeBtn');
    if (btn) btn.disabled = true;
    aiStatus(MSG.aiAnalyzing);
    try {
      const r = await window.pywebview.api.refine_ai_analyze(
        rp, model, indepProv === 'follow' ? null : indepProv);
      if (r && r.success) {
        lastAiSuggestions = r;
        aiSetPrivacy(r.provider_name);
        aiRenderResult(r);
        aiStatus(MSG.aiDone + (r.crosscheck_segments
          ? MSG.asrCrosscheckNote(r.crosscheck_segments) : ''));
      } else {
        // 修复B：分析失败时 stderr_tail 首行摘要进错误信息（截断 200 字符）
        let detail = (r && r.error) || MSG.unknown;
        const tail = (r && r.stderr_tail) || '';
        const firstLine = tail.split('\n').map(s => s.trim()).find(Boolean) || '';
        if (firstLine) detail += '｜' + firstLine.slice(0, 200);
        aiStatus(MSG.aiFailed(detail));
      }
    } catch (e) {
      aiStatus(MSG.aiFailed(e && e.message ? e.message : String(e)));
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // ===== 2.6.0 批1（D2026-1002-02-批1）：质量闭环一键批次修复 =====
  // 幂等守卫在后端（台账 applied 拒入批）；前端只做范围选择+逐条预览+
  // 确认放行（无无人值守自动写盘）。stderr_tail/stdout_tail 一律走
  // textContent 渲染（R2），禁 innerHTML 拼接。
  let lastActionItems = null;

  function bfStatus(text) {
    const st = $('refineBatchFixStatus');
    if (st) st.textContent = text || '';
  }

  function batchFixRefresh() {
    // 使能钩子：导读 json 加载成功后拉取行动条目（含台账已修标记）
    const btn = $('refineBatchFixBtn');
    const scope = $('refineBatchFixScope');
    if (!btn || !window.pywebview || !window.pywebview.api) return;
    if (!lastLoadedGuidePath || lastLoadedIsTxt) {
      lastActionItems = null;
      btn.disabled = true;
      if (scope) { scope.style.display = 'none'; scope.innerHTML = ''; }
      return;
    }
    window.pywebview.api.refine_guide_action_items(lastLoadedGuidePath)
      .then((r) => {
        if (!r || !r.success) {
          lastActionItems = null;
          btn.disabled = true;
          return;
        }
        lastActionItems = r;
        const fixable = (r.open_items || []).filter(it => !it.applied_in_ledger);
        btn.disabled = fixable.length === 0;
        if (scope) {
          scope.innerHTML = '';
          scope.title = MSG.batchFixScopeLabel;
          const optAll = document.createElement('option');
          optAll.value = 'all';
          optAll.textContent = MSG.batchFixScopeAll + '（' + fixable.length + '）';
          scope.appendChild(optAll);
          Object.keys(r.cat_counts || {}).sort().forEach((c) => {
            const o = document.createElement('option');
            o.value = c;
            o.textContent = MSG.batchFixScopeCat(c, r.cat_counts[c]);
            scope.appendChild(o);
          });
          scope.style.display = fixable.length ? '' : 'none';
        }
      })
      .catch(() => {
        lastActionItems = null;
        if (btn) btn.disabled = true;
      });
  }

  async function batchFixRun() {
    if (!lastActionItems) { bfStatus(MSG.batchFixNeedGuide); return; }
    if (!window.pywebview || !window.pywebview.api) {
      bfStatus(MSG.api_not_ready);
      return;
    }
    const all = (lastActionItems.open_items || [])
      .filter(it => !it.applied_in_ledger);
    if (!all.length) { bfStatus(MSG.batchFixNoItems); return; }
    const scope = $('refineBatchFixScope');
    const v = (scope && scope.style.display !== 'none') ? scope.value : 'all';
    const chosen = (v && v !== 'all')
      ? all.filter(it => it.category === v)
      : all.slice();
    if (!chosen.length) { bfStatus(MSG.batchFixNoItems); return; }
    let batch = chosen;
    let capNote = '';
    if (batch.length > 50) {
      capNote = MSG.batchFixCapHit(50, batch.length);
      batch = batch.slice(0, 50);
    }
    const provRaw = (($('refineS3Provider') || {}).value || '').toLowerCase();
    const cloud = isAiCloudProvider(provRaw);
    const provLabel = provRaw
      ? (MSG['ai_prov_' + provRaw] || provRaw) : '跟随阶段B 配置';
    const catCount = {};
    batch.forEach(it => {
      catCount[it.category] = (catCount[it.category] || 0) + 1;
    });
    const catsText = Object.keys(catCount).sort()
      .map(c => c + '（' + catCount[c] + '）').join('、');
    const lines = batch.slice(0, 10).map(it =>
      '#' + it.index + ' [' + it.category + '] ' + it.timing
      + ' ｜ ' + (it.excerpt || '（无摘录）'));
    if (batch.length > 10) {
      lines.push(MSG.batchFixPreviewMore(batch.length - 10));
    }
    const body = [
      MSG.batchFixEstimate(batch.length),
      MSG.batchFixProvider(provLabel),
      MSG.batchFixCats(catsText),
      cloud ? MSG.batchFixCloudCost : '',
      capNote,
      MSG.batchFixPreviewHead,
      lines.join('\n'),
    ].filter(Boolean).join('\n\n');
    const go = await AppModal.confirm(MSG.batchFixConfirmTitle, body);
    if (!go) return;
    const btn = $('refineBatchFixBtn');
    if (btn) btn.disabled = true;
    bfStatus(MSG.batchFixRunning(0, batch.length));
    const poll = setInterval(async () => {
      try {
        const p = await window.pywebview.api.refine_batch_fix_progress();
        if (p && p.running && p.phase === 'verify') {
          bfStatus(MSG.batchFixVerifying);
        } else if (p && p.running) {
          // 执行器无逐条进度输出契约——done=0 时用中性文案（评审修订）
          bfStatus(p.done > 0
            ? MSG.batchFixRunning(p.done, p.total)
            : MSG.batchFixRunningPlain);
        }
      } catch (e) { /* 单次轮询失败静默，主调用最终回显为准 */ }
    }, 1000);
    try {
      // 复验 provider/model 透传 AI 分析独立配置（与 refineAiAnalyze 同源读取）
      const indepProv = (($('aiProviderSel') || {}).value || 'follow');
      const indepModel = (($('aiModelInput') || {}).value || '').trim();
      const effModel = (indepModel
        || (($('refineS1Model') || {}).value || '')).trim();
      const r = await window.pywebview.api.refine_batch_fix(
        lastLoadedGuidePath, batch.map(it => it.index),
        indepProv === 'follow' ? null : indepProv, effModel);
      if (r && r.success) {
        let msg = MSG.batchFixDone(r.applied || 0, r.failed || 0);
        if (r.source_partial) msg += MSG.batchFixSourcePartial;
        const vfy = r.verify || {};
        if (vfy.error) {
          msg += MSG.batchFixVerifyFail;
        } else if (vfy.after) {
          const sum = (o) => ['glossary', 'tm', 'observations']
            .reduce((s, k) => s + ((o && o[k]) || 0), 0);
          const d = sum(vfy.after) - sum(vfy.before);
          msg += MSG.batchFixVerifyDelta(d);
          if (r.suggestions) {
            lastAiSuggestions = {
              success: true,
              parse_ok: vfy.parse_ok !== false,
              suggestions: r.suggestions,
              provider_name: vfy.provider_name || '',
            };
            aiRenderResult(lastAiSuggestions);
          }
        }
        bfStatus(msg);
      } else {
        bfStatus(MSG.batchFixFail + '：' + ((r && r.error) || ''));
      }
    } catch (e) {
      bfStatus(MSG.batchFixFail + '：'
        + (e && e.message ? e.message : String(e)));
    } finally {
      clearInterval(poll);
      if (btn) btn.disabled = false;
      batchFixRefresh();
    }
  }

  // ===== 2.6.0 批3（D2026-1002-04-批3）：ASR 模型管理 =====
  // 2.6.1 修订（D2026-1002-06，模型推荐制）：删内置下载链与 1s 进度轮询，
  // 改推荐清单渲染（present 徽标/大小/来源 URL/落位指引）+验证开关+上游
  // Python 路径回填（均 JS 态文案，零静态键消耗）。
  function asrStatus(text) {
    const st = $('asrStatus');
    if (st) st.textContent = text || '';
  }

  function fmtGB(bytes) {
    return Math.round(bytes / 1073741824 * 10) / 10 + 'GB';
  }

  // 2.7.1 红绿灯（D2026-1005-01 承接批件2）：三色状态点前置注入 asrEnvStatus
  // （span.status-dot.asr-dot，复用既有状态点 class，零新增 id）。
  // 🟢=available；🟡=上游通但缺模型/缺 ffmpeg（triage ok/ffmpeg-missing）；
  // 🔴=不可用（python 不可达/模块缺失/whisper 导入失败）。探测结果单一来源：
  // 红绿灯/面板/下拉共用同一 probe 对象（评议 R4，禁双份维护）。
  function asrApplyEnvStatus(r) {
    const el = $('asrEnvStatus');
    if (!el) return;
    el.textContent = '';
    const triage = (r && r.triage) || 'python-unavailable';
    let cls = 'dot-err';
    let text = MSG.asrProbeFail((r && r.reason) || '');
    if (r && r.available) {
      cls = 'dot-ok';
      text = MSG.asrProbeReady(r.whisper_version || '?',
        r.model_present ? (r.saved_model || 'large-v2')
          : MSG.asrProbeNoModel);
    } else if (triage === 'ok' || triage === 'ffmpeg-missing') {
      cls = 'dot-warn';
      text = MSG.asrProbeUpstreamOk;
    }
    const dot = document.createElement('span');
    dot.className = 'status-dot asr-dot ' + cls;
    el.appendChild(dot);
    el.appendChild(document.createTextNode(text));
  }

  // 2.7.1 件4：下拉来源标注（「<名>（<来源>）」，title=完整路径）
  const ASR_SOURCE_LABELS = {
    'whisper-cache': 'whisper 缓存',
    'data-root': '应用数据',
    'hf-hub': 'HF hub',
  };

  // 模型管理面板数据源（asrRefresh 回填；asrOpenModelsPanel 消费）
  let lastAsrProbe = null;

  // 2.7.1 件3：模型管理面板入口（AppModal kind='models'）。数据=最近一次
  // 探测结果（单一来源）；下载语义全量复用 asr_downloader 桥（面板行内
  // 进度，替代原 AppModal.download 源选择模态调用链）。
  function asrOpenModelsPanel() {
    if (!lastAsrProbe) {
      asrStatus(MSG.mpNeedProbe);
      return;
    }
    AppModal.models({
      probe: lastAsrProbe,
      onFinished: () => asrRefresh(true),   // 下载收尾后强制刷新（徽标/红绿灯翻转）
    });
  }

  function asrRefresh(force) {
    if (!window.pywebview || !window.pywebview.api) return;
    const env = $('asrEnvStatus');
    if (env) env.textContent = '…';
    // force=true（「重新探测」按钮/下载收尾）→ 绕过快照缓存同步重探；
    // 缺省（首开 ASR 页/后台预热）→ 优先读磁盘快照立即返回（TTL 10 分钟）。
    window.pywebview.api.refine_asr_status(force === true).then((r) => {
      if (!r || !r.success) {
        asrStatus((r && r.error) || MSG.unknown);
        return;
      }
      lastAsrProbe = r;
      asrApplyEnvStatus(r);
      const sel = $('asrModelSel');
      if (!sel) return;
      sel.innerHTML = '';
      const models = r.models || [];
      if (!models.length) {
        const o = document.createElement('option');
        o.value = '';
        o.textContent = MSG.asrSelectPlaceholder;
        sel.appendChild(o);
      }
      // 三落位合并去重结果（后端已按 whisper-cache>data-root 校验序去重，
      // 只收 whisper 系 ready 项；HF hub 条目不进下拉——需适配，走面板）
      models.forEach((m) => {
        const o = document.createElement('option');
        o.value = m.name;
        const src = ASR_SOURCE_LABELS[m.source] || '';
        o.textContent = m.name + (src ? '（' + src + '）' : '');
        o.title = m.path || '';
        sel.appendChild(o);
      });
      const saved = r.saved_model || '';
      if (saved && models.some(m => m.name === saved)) sel.value = saved;
      const tgl = $('asrCrosscheckToggle');
      if (tgl) tgl.checked = !!r.crosscheck_enabled;
      const pyInp = $('asrPythonInput');
      if (pyInp) pyInp.value = r.saved_python || '';
    }).catch((e) => asrStatus(String(e)));
  }

  // ASR 卡懒探测钩子（switchTab 首开 tab-asrdict 触发一次；缓存秒回，
  // 强制刷新走「重新探测」按钮）
  window.__asrTabHook = () => {
    if (window.__asrTabHookDone) return;
    window.__asrTabHookDone = true;
    asrRefresh(false);
  };

  function aiBtnState(btn, statusText) {
    if (statusText) {
      btn.textContent = statusText;
      btn.disabled = true;
    } else {
      btn.disabled = false;
    }
  }

  // 落库失败反馈：按钮转「重试」态 + 行内（aiStatus）显示错误摘要，
  // 不再静默恢复；成功路径不受影响。
  function aiApplyFail(btn, err) {
    const m = (err && err.message) ? err.message : String(err || MSG.unknown);
    btn.textContent = MSG.aiApplyRetry;
    btn.disabled = false;
    aiStatus(MSG.aiApplyFailed(m));
  }

  async function aiApplyGlossary(idx, btn) {
    const entry = (((lastAiSuggestions || {}).suggestions || {}).glossary
      || [])[idx];
    if (!entry || !window.pywebview || !window.pywebview.api) return;
    btn.disabled = true;
    try {
      const r = await window.pywebview.api.refine_ai_apply_glossary(
        JSON.stringify([{ src: entry.src, target: entry.target,
                          aliases: entry.aliases || [] }]));
      if (r && r.success === false) {
        aiApplyFail(btn, r.error || MSG.unknown);
        return;
      }
      const st = ((r && r.results && r.results[0]) || {}).status || '';
      aiBtnState(btn,
        st === 'added' ? MSG.aiApplied
          : st === 'exists' ? MSG.aiExists
            : st === 'exists_diff' ? MSG.aiExistsDiff
              : st === 'locked' ? MSG.aiLocked : '');
      if (st === 'added' && typeof glLoad === 'function') glLoad();
    } catch (e) {
      aiApplyFail(btn, e);
    }
  }

  async function aiApplyTm(idx, btn) {
    const entry = (((lastAiSuggestions || {}).suggestions || {}).tm
      || [])[idx];
    if (!entry || !window.pywebview || !window.pywebview.api) return;
    btn.disabled = true;
    try {
      const r = await window.pywebview.api.refine_ai_apply_tm(
        JSON.stringify([{ source: entry.source, target: entry.target }]));
      if (r && r.success === false) {
        aiApplyFail(btn, r.error || MSG.unknown);
        return;
      }
      const st = ((r && r.results && r.results[0]) || {}).status || '';
      aiBtnState(btn,
        st === 'added' ? MSG.aiTmStored
          : st === 'exists' ? MSG.aiExists : '');
    } catch (e) {
      aiApplyFail(btn, e);
    }
  }

  // ---- 性暗示词替换（legacy 功能，已随 legacy 管线删除）----

  // ---- DOM 绑定（不依赖 pywebview 就绪）----
  function bindDom() {
    if (!$('refineStartBtn') || window.__refineBound) {
      if (!window.__refineBound) setTimeout(bindDom, 300);
      return;
    }
    window.__refineBound = true;

    $('refineStartBtn').addEventListener('click', () => TranslatorManager.startTranslation());
    $('refineCancelBtn').addEventListener('click', () => TranslatorManager.cancelTranslation());

    for (const n of [1, 3]) {
      // 批2（D2026-1002-12）：空态占位文案 JS 态填充（HTML 不挂静态 data-i18n）
      const msel = $('refineS' + n + 'Model');
      const mph = msel ? msel.querySelector('option[value=""]') : null;
      if (mph) mph.textContent = MSG.model_list_empty_hint;
      const rb = $('refineRefreshS' + n);
      if (rb) rb.addEventListener('click', () => refreshModels(n));
      const tb = $('refineTestS' + n);
      if (tb) tb.addEventListener('click', () => testStage(n));
      // 批2（D2026-1002-12 拍板点2）：切服务商不自动拉取模型列表，只认
      // 「刷新/测试」两个显式入口——此处仅重置空态占位并填充缺省地址
      const pv = $('refineS' + n + 'Provider');
      if (pv) pv.addEventListener('change', () => {
        const sel = $('refineS' + n + 'Model');
        if (sel) sel.innerHTML = modelEmptyOptionHTML();
        applyProviderEndpoint(n);
        syncServiceQuickFromStages();
      });
      const kb = $('refineSaveS' + n + 'KeyBtn');
      if (kb) kb.addEventListener('click', () => saveStageKey(n));
    }

    $('refreshFallbackModels').addEventListener('click', refreshFallbackModels);

    // 2.6.3 批C（D2026-1003-01 P4 IA 重排）：接口地址行迁段后，保存键拆为
    // 主键（#refineSaveEndpointsBtn，阶段A 段，携带状态 span）与阶段B 段
    // class-only 孪生按钮（无 id，零 id 预算消耗），两者绑同一 handler
    document.querySelectorAll('#refineSaveEndpointsBtn, .endpoint-save-twin')
      .forEach(b => b.addEventListener('click', saveStageEndpoints));

    // v1.5 翻译服务快捷下拉绑定（tab-translate 页）
    const quickProv = $('refineServiceQuick');
    if (quickProv) quickProv.addEventListener('change',
      () => applyServiceQuickProvider(true));
    // 「打开其他质量报告导读」：弹原生文件对话框选择导读 json
    // （D2026-0930-07 owner 痛点批，替代原粘贴路径行）；选中即走
    // guideLoad 显式路径链路，用户取消静默返回，无窗口/异常显示在状态 span
    const guideOtherBtn = $('guideOpenOtherBtn');
    if (guideOtherBtn) guideOtherBtn.addEventListener('click', async () => {
      if (!window.pywebview || !window.pywebview.api) {
        guideCustomStatus(MSG.api_not_ready, true);
        return;
      }
      try {
        const r = await window.pywebview.api.refine_pick_guide_json();
        if (r && r.success && r.path) {
          guideLoad(false, r.path);
        } else if (!r || !r.cancelled) {
          // 用户取消（cancelled）静默返回；其余错误（如无活动窗口）静默显示在状态 span，不弹窗
          guideCustomStatus(
            MSG.guide_load_failed((r && r.error) || MSG.unknownError), true);
        }
      } catch (e) {
        guideCustomStatus(MSG.guide_load_failed(
          e && e.message ? e.message : String(e)), true);
      }
    });

    // v1.5 左侧 TAB 栏绑定（SmartSub 式功能选择）
    document.querySelectorAll('.side-tab-btn').forEach(btn => {
      btn.addEventListener('click', () => switchTab(btn.dataset.tab));
    });

    // 2.6.5 段2（D2026-1004-01 #3）：引擎页 seg 分段控件已删除（三段改
    // stage-group 纵向堆叠，纯 CSS 布局零 JS 绑定），原绑定循环一并移除

    const glAddBtn = $('refineGlAdd');
    if (glAddBtn) glAddBtn.addEventListener('click', glAdd);
    // 2.5.0 修复D：高级参数阶段A/B 角色卡"去编辑"跳转（class 承载零 id 预算）
    document.querySelectorAll('.tpl-goto-btn').forEach((b) => {
      b.textContent = MSG.tpl_goto_edit;
      b.addEventListener('click', () => tplGotoEdit(b.dataset.tplStage));
    });
    // 学习词库只读刷新（词库与模板页）
    const glLearnedReload = $('glLearnedReloadBtn');
    if (glLearnedReload) glLearnedReload.addEventListener('click', glLearnedLoad);
    // 词库页区块折叠（2.1.1 owner 痛点批：默认展开；点标题或箭头按钮均可切换，
    // 会话内生效不持久化；刷新按钮等标题行内其余控件不受影响）
    document.querySelectorAll('.gl-collapsible').forEach(stack => {
      const btn = stack.querySelector('.gl-collapse-btn');
      const title = stack.querySelector('.gl-collapse-header .block-title');
      const toggle = () => {
        const collapsed = stack.classList.toggle('collapsed');
        if (btn) btn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      };
      if (btn) {
        btn.setAttribute('aria-label', MSG.collapse_toggle);
        btn.addEventListener('click', (e) => { e.stopPropagation(); toggle(); });
      }
      if (title) title.addEventListener('click', toggle);
    });
    const glDelBtn = $('refineGlDel');
    if (glDelBtn) glDelBtn.addEventListener('click', glDel);
    const glImpBtn = $('refineGlImport');
    if (glImpBtn) glImpBtn.addEventListener('click', glImport);
    const glExpBtn = $('refineGlExport');
    if (glExpBtn) glExpBtn.addEventListener('click', glExport);
    const glSaveBtn = $('refineGlSave');
    if (glSaveBtn) glSaveBtn.addEventListener('click', glSave);

    // 2.6.3 批D（D2026-1003-01 P5）：编辑器整体迁入 AppModal.editor 模态——
    // 保存（#refineTemplateSave）/重新加载（#refineTemplateReload）/切阶段
    // （#refineTemplateStage change）改由 editor() 开态一次性绑定弹窗感知
    // 路径（脏确认守卫 + _edSaving 保存中禁关闭），原 bindDom 直绑
    // tplLoad / tplRefreshSelect(true) / tplSave 移除（既有绑定必要随改）。
    // 编辑器入口两枚（词库页+高级参数页）：class 承载零 id，文案 JS 态填充；
    // 入口行提示 span 复用既有键 tpl_explicit_card_hint（JS 态写入零静态消耗）
    document.querySelectorAll('.tpl-editor-entry-btn').forEach((b) => {
      b.textContent = MSG.tplOpenEditor;
      b.addEventListener('click', openTplEditor);
    });
    const tplEntryHint = document.querySelector('[data-testid="tpl-entry-hint"]');
    if (tplEntryHint) tplEntryHint.textContent = MSG.tpl_explicit_card_hint;
    const pickBtn = $('refinePickDirBtn');
    if (pickBtn) pickBtn.addEventListener('click', pickDir);

    // 角色卡目录打开按钮
    const openDirBtn = $('refineOpenDirBtn');
    if (openDirBtn) openDirBtn.addEventListener('click', () => {
      openDir($('refineTemplatesDir') ? $('refineTemplatesDir').value : '');
    });

    // 净语配置目录浏览按钮
    const pickCleanerBtn = $('refinePickCleanerDir');
    if (pickCleanerBtn) pickCleanerBtn.addEventListener('click', pickCleanerDir);

    // 净语配置目录打开按钮
    const openCleanerBtn = $('refineOpenCleanerDir');
    if (openCleanerBtn) openCleanerBtn.addEventListener('click', () => {
      openDir($('refineCleanerConfig') ? $('refineCleanerConfig').value : '');
    });

    // S3 引擎联动已随 v2 移除（原 updateS3EngineUI）
    // 性暗示词替换按钮已随 legacy 管线删除

    // 质量报告导读查看器（W1b）
    const guideBtn = $('refineGuideLoadBtn');
    if (guideBtn) guideBtn.addEventListener('click', () => guideLoad(false));
    // AI 质量分析（D2026-0929）
    const aiBtn = $('refineAiAnalyzeBtn');
    if (aiBtn) aiBtn.addEventListener('click', () => refineAiAnalyze());
    // 批3 补刀（D2026-1002-12 空载复测）：AI 分析区顶置标签中文填充
    // （HTML 英文留兜底；三键均既有，绑 DOM 即填不依赖设置回填路径，
    //   设置回填路径的同名填充保留为幂等二次写）
    const aiCfgLabels = { aiProviderSel: 'ai_cfg_provider_label',
                          aiModelInput: 'ai_cfg_model_label',
                          aggregateWindowSel: 'aggregateWindowLabel' };
    Object.keys(aiCfgLabels).forEach((k) => {
      const lbl = document.querySelector('label[for="' + k + '"]');
      if (lbl) lbl.textContent = MSG[aiCfgLabels[k]];
    });
    // 质量闭环一键批次修复（2.6.0 批1）
    const bfBtn = $('refineBatchFixBtn');
    if (bfBtn) bfBtn.addEventListener('click', () => batchFixRun());
    // ASR 模型管理（2.6.0 批3；批2 D2026-1002-12 卡重整：空态/说明/占位文案
    // JS 态填充，HTML 不留英文占位）
    const asrBtn = $('asrRefreshBtn');
    if (asrBtn) {
      const t = asrBtn.querySelector('span');
      if (t) t.textContent = MSG.asrRefreshBtn;
      asrBtn.addEventListener('click', () => asrRefresh(true));   // 强制刷新（绕过快照缓存）
    }
    const asrEnv = $('asrEnvStatus');
    if (asrEnv) asrEnv.textContent = MSG.asr_env_undetected;
    // 2.7.1：模型管理面板入口（.asr-models-btn class 锚，零新增 id）
    const asrModelsBtn = document.querySelector('.asr-models-btn');
    if (asrModelsBtn) {
      const t = asrModelsBtn.querySelector('span');
      if (t) t.textContent = MSG.asrModelsBtn;
      asrModelsBtn.addEventListener('click', () => asrOpenModelsPanel());
    }
    const asrSelPh = $('asrModelSel');
    if (asrSelPh) {
      const ph = asrSelPh.querySelector('option[value=""]');
      if (ph) ph.textContent = MSG.asrSelectPlaceholder;
    }
    // 批3 扩展（D2026-1002-12）：系统状态卡 ASR 行「重新探测」事件委托——
    // 行由 SystemSummary 动态渲染（零新增静态 id），委托绑卡上按
    // data-sys-action 分流；首屏不自动探测（上游 selfcheck 慢）
    const sysCard = $('systemSummaryCard');
    if (sysCard) sysCard.addEventListener('click', (e) => {
      if (e.target.closest('[data-sys-action="asr-probe"]')) {
        SystemSummary.probeAsr();
      }
    });
    // 2.6.1 修订（D2026-1002-06）：验证开关 + 上游 Python 路径（下载按钮删除）；
    // 批2：asrSaved 仅在保存成功后写入（失败透出错误，与空态占位区分）
    const asrTgl = $('asrCrosscheckToggle');
    if (asrTgl) {
      const lbl = asrTgl.parentElement
        ? asrTgl.parentElement.querySelector('span') : null;
      if (lbl) lbl.textContent = MSG.asrCrosscheckLabel;
      // 2.7.1：入口说明独立行删除，说明文案并入开关 title 悬停
      asrTgl.title = MSG.asrCrosscheckTitle;
      asrTgl.addEventListener('change', async () => {
        if (!window.pywebview || !window.pywebview.api) return;
        try {
          const r = await window.pywebview.api.refine_save_stage_settings(
            null, null,
            { media_crosscheck_enabled: asrTgl.checked ? '1' : '0' });
          asrStatus(r && r.success ? MSG.asrSaved
            : '❌ ' + ((r && r.error) || MSG.unknown));
        } catch (e) {
          asrStatus('❌ ' + e);
        }
      });
    }
    const asrPy = $('asrPythonInput');
    if (asrPy) {
      asrPy.placeholder = MSG.asrPythonPlaceholder;
      asrPy.addEventListener('change', async () => {
        if (!window.pywebview || !window.pywebview.api) return;
        try {
          const r = await window.pywebview.api.refine_save_stage_settings(
            null, null, { asr_python: asrPy.value.trim() });
          asrStatus(r && r.success ? MSG.asrSaved
            : '❌ ' + ((r && r.error) || MSG.unknown));
        } catch (e) {
          asrStatus('❌ ' + e);
        }
      });
    }
    const asrSel = $('asrModelSel');
    if (asrSel) asrSel.addEventListener('change', async () => {
      if (!window.pywebview || !window.pywebview.api) return;
      try {
        const r = await window.pywebview.api.refine_save_stage_settings(
          null, null, { asr_model: asrSel.value });
        asrStatus(r && r.success ? MSG.asrSaved
          : '❌ ' + ((r && r.error) || MSG.unknown));
      } catch (e) {
        asrStatus('❌ ' + e);
      }
    });

    // 快速试听（D2026-0929-09）：条目试听按钮事件委托 + 浮层关闭 +
    // 媒体来源条「更换」展开 + 覆盖路径应用
    const guideItemsEl = $('guideItems');
    if (guideItemsEl) guideItemsEl.addEventListener('click', (e) => {
      const btn = e.target.closest('.btn-audio-preview');
      if (btn) openAudioPreview(btn.dataset.timing);
    });
    const pvCloseBtn = $('audioPreviewCloseBtn');
    if (pvCloseBtn) pvCloseBtn.addEventListener('click', closeAudioPreview);
    const msToggleBtn = $('mediaSourceToggleBtn');
    if (msToggleBtn) msToggleBtn.addEventListener('click', () => {
      const row = $('mediaSourceEditRow');
      if (row) row.style.display =
        row.style.display === 'none' ? '' : 'none';
    });
    const msApplyBtn = $('mediaOverrideApplyBtn');
    if (msApplyBtn) msApplyBtn.addEventListener('click', () => {
      const inp = $('mediaOverrideInput');
      const st = $('mediaOverrideStatus');
      mediaOverridePath = inp && inp.value.trim() ? inp.value.trim() : '';
      if (st) {
        st.textContent = mediaOverridePath
          ? MSG.media_override_applied : MSG.media_override_cleared;
      }
      updateMediaSourceBar(lastGuideData);
    });

    // 数据保存目录（高级参数页）：浏览选择目录（与角色卡同款原生目录对话框）
    const drToggleBtn = $('dataRootToggleBtn');
    if (drToggleBtn) drToggleBtn.addEventListener('click', dataRootBrowse);
    const drRestoreBtn = $('dataRootRestoreBtn');
    if (drRestoreBtn) drRestoreBtn.addEventListener('click',
      () => dataRootSave(''));
  }

  // ---- 数据保存目录（高级参数页；pointer 写入 .data-root，重启应用后生效）----
  function dataRootSourceLabel(src) {
    const k = 'data_root_source_' + (src || '');
    return typeof MSG[k] === 'string' ? MSG[k] : (src || '');
  }
  function dataRootLoad() {
    if (!window.pywebview || !pywebview.api ||
        !pywebview.api.refine_get_data_root) return;
    pywebview.api.refine_get_data_root().then(r => {
      if (!r || !r.success) return;
      const pathEl = $('dataRootCurrentPath');
      const tagEl = $('dataRootSourceTag');
      if (pathEl) pathEl.textContent = r.data_root;
      if (tagEl) tagEl.textContent = dataRootSourceLabel(r.source);
    }).catch(() => {});
  }
  async function dataRootBrowse() {
    const st = $('dataRootStatus');
    try {
      const r = await pywebview.api.refine_pick_folder();
      if (!r || !r.success || !r.path) return; // 取消/失败静默返回
      const cur = $('dataRootCurrentPath');
      if (cur && cur.textContent && cur.textContent === r.path) {
        if (st) st.textContent = MSG.data_root_unchanged;
        return;
      }
      await dataRootSave(r.path);
    } catch (e) {
      if (st) st.textContent = String(e);
    }
  }
  async function dataRootSave(value) {
    const st = $('dataRootStatus');
    try {
      const r = await pywebview.api.refine_set_data_root(value || '');
      if (st) {
        st.textContent = (r && r.success)
          ? (value ? MSG.data_root_saved_restart
                   : MSG.data_root_default_restored)
          : ((r && r.error) || '');
      }
      if (r && r.success) {
        dataRootLoad();
        // 批1a 件5：数据根变更后阻断式提示（AppModal 模态须点确认关闭；
        // 重启前后续写入仍落旧根的说明随文案带出）
        await AppModal.alert(MSG.data_root_restart_title,
                             MSG.data_root_restart_body);
      }
    } catch (e) {
      if (st) st.textContent = String(e);
    }
  }

  // ---- 词典管理（2.1 引擎页三区块：日/中/英 状态/下载/路径）----
  const DICT_KINDS = [
    { kind: 'sudachi', label: MSG.dict_sudachi_label,
      desc: MSG.dict_sudachi_desc, downloadable: true },
    { kind: 'sudachi_full', label: MSG.dict_sudachi_full_label,
      desc: MSG.dict_sudachi_full_desc, downloadable: true },
    { kind: 'jieba', label: MSG.dict_jieba_label,
      desc: MSG.dict_jieba_desc, downloadable: false },
    { kind: 'english_rules', label: MSG.dict_english_label,
      desc: MSG.dict_english_desc, downloadable: false },
  ];
  // 修复A：词典卡分母单一事实源——顶层 SystemSummary 经此桥取 DICT_KINDS 长度
  window.AppDictKindsCount = DICT_KINDS.length;
  // 词典状态缓存（B2 案批3）：dictLoad 拉取后写入，dictSelect change 复渲染读取
  let _dictStatusCache = {};
  let _dictDirCache = '';
  // 下载中词典占位（2.6.5 段2 D2026-1004-01 #5「下载中禁整行」收口：
  // code-review 发现下载中切词典→dictRenderDetail 重渲染复位共享操作行，
  // 可对另一 kind 并发发起下载——以模块级占位在渲染与入口双端钉死）
  let _dictBusyKind = null;
  // 批1b 件1/件2：自定义词典目录态（custom_dir=设置值|null；
  // needs_migration/old_dir=选新目录后由 refine_pick_dict_dir 返回的迁移提示）
  let _dictCustomDir = null;
  let _dictNeedsMigration = false;
  let _dictOldDir = '';
  // 2.6.3 批B（D2026-1003-06 条件②）：源摘要缓存（{kind: {has_official,
  // has_mirror}}），「仅镜像」键 disabled 门控读取
  let _dictSourcesCache = {};
  // 2.6.5 段2（D2026-1004-01 #4）：四 kind 摘要行展示序=日语·中文·英文·
  // 完整版（owner 定夺，独立于 DICT_KINDS 数组序）
  const DICT_KIND_DISPLAY_ORDER = ['sudachi', 'jieba', 'english_rules',
    'sudachi_full'];
  // 四 kind 状态摘要行（空态三件套①）：全 createElement 零静态 id；实心点=
  // 已装（--ok）/空心=未装（--text-3）/内置 english_rules=primary 点；
  // 完整版 chip title「与日语二选一」；点击 chip→切 #dictSelect 并刷新详情
  function _dictEnsureKindRow() {
    const box = $('dictRows');
    if (!box || box.querySelector('.dict-kind-row')) return;
    const row = document.createElement('div');
    row.className = 'dict-kind-row';
    DICT_KIND_DISPLAY_ORDER.forEach(kind => {
      const item = DICT_KINDS.find(k => k.kind === kind) || {};
      const chip = document.createElement('button');
      chip.type = 'button';
      chip.className = 'dict-kind-chip';
      chip.dataset.kind = kind;
      const dot = document.createElement('span');
      dot.className = 'dot';
      chip.appendChild(dot);
      chip.appendChild(document.createTextNode(item.label || kind));
      if (kind === 'sudachi_full') chip.title = MSG.dict_sudachi_full_chip_title;
      chip.addEventListener('click', () => {
        const sel = $('dictSelect');
        if (sel && sel.value !== kind) {
          sel.value = kind;
          _dictRefreshKindRow();
          _dictRefreshHint();              // 与下拉 change 同路径：hint 显隐随词典切换
          dictRenderDetail();
        }
      });
      row.appendChild(chip);
    });
    box.insertBefore(row, box.firstChild);
  }
  // chip 状态刷新：active=当前选中词典；on/builtin=安装态（点色）
  function _dictRefreshKindRow() {
    const row = document.querySelector('#dictRows .dict-kind-row');
    const sel = $('dictSelect');
    if (!row || !sel) return;
    row.querySelectorAll('.dict-kind-chip').forEach(chip => {
      const kind = chip.dataset.kind;
      const info = _dictStatusCache[kind] || {};
      chip.classList.toggle('active', sel.value === kind);
      chip.classList.toggle('on',
        !!(info.available && kind !== 'english_rules'));
      chip.classList.toggle('builtin', kind === 'english_rules');
    });
  }
  // warn-soft 提示条（空态三件套②，空态三件套承载原 #dictEmpty 后果语义）
  function _dictEnsureHint() {
    const box = $('dictRows');
    if (!box || box.querySelector('.dict-install-hint')) return;
    const hint = document.createElement('div');
    hint.className = 'dict-install-hint';
    hint.style.display = 'none';
    hint.textContent = MSG.dict_install_hint;
    const kindRow = box.querySelector('.dict-kind-row');
    if (kindRow) box.insertBefore(hint, kindRow.nextSibling);
    else box.insertBefore(hint, box.firstChild);
  }
  // hint 条显隐：仅当前选中 kind downloadable&&!available 时显示
  function _dictRefreshHint() {
    const box = $('dictRows');
    const hint = box ? box.querySelector('.dict-install-hint') : null;
    const sel = $('dictSelect');
    if (!hint || !sel) return;
    const kind = sel.value;
    const item = DICT_KINDS.find(k => k.kind === kind) || {};
    const info = _dictStatusCache[kind] || {};
    hint.style.display = (item.downloadable && !info.available) ? '' : 'none';
  }
  // 2.6.5 段2（D2026-1004-01 #6）：失败一行人话映射——校验失败/网络失败
  // 短句（诊断数据来自后端 failed 快照 diag 字段，段1 已落契约），磁盘/
  // 未知沿用原文；技术串下沉 details 诊断网格
  function dictFailureText(error, diag) {
    if (/SHA256/.test(error)) return MSG.dict_fail_checksum;
    if (diag && (diag.url || diag.attempts)) return MSG.dict_fail_network;
    return error || MSG.dict_download_failed;
  }
  // 状态行统一出口：isErr=true 加 status-err 红 + 技术详情 <details> 网格
  // （重渲染前清空旧 details；诊断值一律 TextNode 禁 innerHTML；URL 行带
  // 复制键，file:// clipboard 被拒降级为点击全选该值）
  function dictShowStatus(st, text, isErr, diag) {
    if (!st) return;
    st.textContent = text || '';
    st.classList.toggle('status-err', !!isErr);
    const card = st.parentElement;
    if (card) {
      const old = card.querySelector('.dict-diag');
      if (old) old.remove();
    }
    if (!isErr || !diag || typeof diag !== 'object') return;
    const details = document.createElement('details');
    details.className = 'dict-diag';
    const summary = document.createElement('summary');
    const chev = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    chev.setAttribute('viewBox', '0 0 24 24');
    chev.setAttribute('width', '14');
    chev.setAttribute('height', '14');
    chev.setAttribute('fill', 'none');
    chev.setAttribute('stroke', 'currentColor');
    chev.setAttribute('stroke-width', '2');
    chev.setAttribute('stroke-linecap', 'round');
    chev.setAttribute('stroke-linejoin', 'round');
    chev.setAttribute('aria-hidden', 'true');
    const chevPath = document.createElementNS('http://www.w3.org/2000/svg', 'path');
    chevPath.setAttribute('d', 'm9 18 6-6-6-6');
    chev.appendChild(chevPath);
    summary.appendChild(chev);
    summary.appendChild(document.createTextNode(MSG.dict_diag_summary));
    details.appendChild(summary);
    const grid = document.createElement('div');
    grid.className = 'dict-diag-grid';
    // 字段按存在性逐行降级（proxy 取值=段1 定稿 "system"/"direct"）
    const addRow = (label, value) => {
      const k = document.createElement('span');
      k.className = 'k';
      k.textContent = label;
      const v = document.createElement('span');
      v.className = 'v';
      v.textContent = value;
      grid.appendChild(k);
      grid.appendChild(v);
      return v;
    };
    const defined = (x) => x !== undefined && x !== null && x !== '';
    if (defined(diag.expected_bytes))
      addRow(MSG.dict_diag_expected_bytes, String(diag.expected_bytes));
    if (defined(diag.actual_bytes))
      addRow(MSG.dict_diag_actual_bytes, String(diag.actual_bytes));
    if (defined(diag.content_encoding))
      addRow(MSG.dict_diag_encoding, String(diag.content_encoding));
    if (defined(diag.part_prefix_hex))
      addRow(MSG.dict_diag_part_hex, String(diag.part_prefix_hex));
    if (defined(diag.url)) {
      const v = addRow(MSG.dict_diag_url, String(diag.url));
      const copy = document.createElement('button');
      copy.type = 'button';
      copy.className = 'copy';
      copy.textContent = MSG.dict_diag_copy;
      copy.addEventListener('click', () => {
        const flash = (t) => {
          copy.textContent = t;
          setTimeout(() => { copy.textContent = MSG.dict_diag_copy; }, 1500);
        };
        const selectAll = () => {
          try {
            const range = document.createRange();
            range.selectNodeContents(v);
            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
          } catch (e) { /* ignore */ }
          flash(MSG.dict_diag_selected);
        };
        try {
          navigator.clipboard.writeText(String(diag.url)).then(
            () => flash(MSG.ui_copied), selectAll);
        } catch (e) {
          selectAll();
        }
      });
      v.appendChild(copy);
    }
    if (defined(diag.proxy))
      addRow(MSG.dict_diag_proxy,
        diag.proxy === 'system' ? MSG.dict_diag_proxy_system
          : diag.proxy === 'direct' ? MSG.dict_diag_proxy_direct
            : String(diag.proxy));
    if (defined(diag.attempts))
      addRow(MSG.dict_diag_attempts, String(diag.attempts));
    details.appendChild(grid);
    if (card) card.insertBefore(details, st.nextSibling);
  }
  function dictLoad() {
    const box = $('dictRows');
    if (!box || !window.pywebview || !pywebview.api ||
        !pywebview.api.refine_dict_status) return;
    pywebview.api.refine_dict_status().then(r => {
      if (!r || !r.success) {
        const st = $('dictStatus');
        // 2.6.5 段2（D2026-1004-01 #6）：加载失败也红（status-err）
        if (st) dictShowStatus(st,
          `${MSG.dict_load_failed}${r && r.error ? '：' + r.error : ''}`,
          true, null);
        return;
      }
      _dictStatusCache = (r && r.dicts) || {};
      _dictDirCache = (r && r.effective_dir) || (r && r.dict_dir) || '';
      _dictCustomDir = (r && r.custom_dir) || null;
      _dictSourcesCache = (r && r.sources) || {};
      // 2.6.5 段2（D2026-1004-01 #4）：#dictEmpty 空态引导条已删（C2 决议
      // 反转记档，FROZEN_IDS 215→214 显式解冻）——空态语义由四 kind 摘要
      // 行 + pill-warning「未安装」+ warn-soft hint 条承接
      _dictEnsureKindRow();
      // 下拉填充（label=词典名，可用性由状态行/chip 承载去重复），
      // change→详情刷新（静态骨架只填充不建行）
      const sel = $('dictSelect');
      if (sel) {
        sel.innerHTML = '';
        DICT_KINDS.forEach(item => {
          const opt = document.createElement('option');
          opt.value = item.kind;
          opt.textContent = item.label;
          sel.appendChild(opt);
        });
        if (!sel.dataset.bound) {          // 一次性绑定，数据经缓存读取防陈旧闭包
          sel.dataset.bound = '1';
          sel.addEventListener('change', () => {
            _dictRefreshKindRow();
            _dictRefreshHint();            // 黑盒缺陷#1 修复：切词典须同步 hint 显隐
            dictRenderDetail();            // （否则 downloadable→非 downloadable 残留误导文案）
          });
        }
      }
      _dictEnsureHint();
      _dictRefreshKindRow();
      _dictRefreshHint();
      // 打开文件夹（R3：复用现成 openDir(path)→open_output_folder 链，零新 API）
      const openBtn = $('dictOpenDir');
      if (openBtn && !openBtn.dataset.bound) {
        openBtn.dataset.bound = '1';
        openBtn.addEventListener('click', () => openDir($('dictPath') && $('dictPath').textContent));
      }
      // 批1b 件1/件2：目录行三键一次性绑定（浏览/恢复默认/迁移；
      // 标签 JS 态 MSG 键填充，与 dictActionBtn 同款空 HTML 骨架）
      const browseBtn = $('dictBrowseBtn');
      if (browseBtn && !browseBtn.dataset.bound) {
        browseBtn.dataset.bound = '1';
        browseBtn.textContent = MSG.data_root_change_btn;
        browseBtn.addEventListener('click', dictPickDir);
      }
      const restoreBtn = $('dictRestoreBtn');
      if (restoreBtn && !restoreBtn.dataset.bound) {
        restoreBtn.dataset.bound = '1';
        restoreBtn.textContent = MSG.data_root_restore_btn;
        restoreBtn.addEventListener('click', dictRestoreDir);
      }
      const migBtn = $('dictMigrateBtn');
      if (migBtn && !migBtn.dataset.bound) {
        migBtn.dataset.bound = '1';
        migBtn.textContent = MSG.dict_migrate_btn;
        migBtn.addEventListener('click', () => dictMigrate());
      }
      dictRenderDetail();
    }).catch((e) => {
      const st = $('dictStatus');
      // 2.6.5 段2（D2026-1004-01 #6）：加载异常也红（status-err）
      if (st) dictShowStatus(st, MSG.dict_load_failed + '：' + String(e),
        true, null);
    });
  }
  function dictRenderDetail() {
    const detail = $('dictDetail');
    const sel = $('dictSelect');
    if (!detail || !sel) return;
    const kind = sel.value || (DICT_KINDS[0] && DICT_KINDS[0].kind);
    const info = _dictStatusCache[kind] || {};
    const item = DICT_KINDS.find(k => k.kind === kind) || {};
    detail.style.display = '';
    // 状态 pill 四态（2.6.5 段2 D2026-1004-01 定表）：available&&english_rules
    // →「内置」/available→「可用」/!available&&downloadable→新 JS 态键
    // 「未安装」+pill-warning（删 inline style hack）/其余→「不可用」
    // （jieba 未装落此格）
    const pill = $('dictPill');
    if (pill) {
      const dlItem0 = DICT_KINDS.find(k => k.kind === kind) || {};
      if (info.available) {
        pill.textContent = kind === 'english_rules'
          ? MSG.dict_status_builtin : MSG.dict_status_available;
        pill.className = 'pill pill-success';
      } else if (dlItem0.downloadable) {
        pill.textContent = MSG.dict_status_not_installed;
        pill.className = 'pill pill-warning';
      } else {
        pill.textContent = MSG.dict_status_unavailable;
        pill.className = 'pill';
      }
      pill.style.color = '';
    }
    const desc = $('dictDesc');
    if (desc) {
      desc.textContent = info.description || item.desc || '';
      desc.title = desc.textContent;
    }
    // 安装目录行（批1b：dict_dir=现生效目录，悬停 title 全文）+ 目录行按钮
    const path = $('dictPath');
    if (path) {
      path.textContent = _dictDirCache;
      path.title = _dictDirCache;       // 悬停全文（长路径截断可读）
    }
    const pathRow = $('dictPathRow');
    if (pathRow) pathRow.style.display = '';
    // 恢复默认键：仅设置了自定义目录时显示
    const restoreBtn = $('dictRestoreBtn');
    if (restoreBtn) restoreBtn.style.display = _dictCustomDir ? '' : 'none';
    // 迁移键：仅更改目录且旧目录有词典文件时显示（迁移成功/恢复默认后隐藏）
    const migBtn = $('dictMigrateBtn');
    if (migBtn) migBtn.style.display = _dictNeedsMigration ? '' : 'none';
    // R2 三态门控：可下载 kind（sudachi/sudachi_full）未装=primary「下载」/
    // 已装=ghost「重新下载」；jieba 无按钮只显 desc 指引（downloadable=false）；
    // english 恒内置隐藏按钮（修复A：下载门泛化由 DICT_KINDS.downloadable 驱动）
    const btn = $('dictActionBtn');
    const dlItem = DICT_KINDS.find(k => k.kind === kind) || {};
    if (btn) {
      if (dlItem.downloadable) {
        btn.style.display = '';
        btn.className = info.available ? 'btn btn-ghost btn-compact' : 'btn btn-primary btn-compact';
        btn.textContent = info.available ? MSG.dict_redownload : MSG.dict_download;
      } else {
        btn.style.display = 'none';
        btn.textContent = '';
      }
      // 一次性 click 绑定（静态 DOM 不重建，dataset.bound 防重复挂监听）；
      // 回调读当前 sel.value 保证通用性（按钮现仅 sudachi 分支显示）
      if (!btn.dataset.bound) {
        btn.dataset.bound = '1';
        btn.addEventListener('click', () => dictDownload($('dictSelect').value, btn));
      }
      // 源选择双按钮（2.6.3 批B，D2026-1003-06 条件②①）：JS 注入零 id
      // （FROZEN_IDS 冻结）。2.6.5 段2（D2026-1004-01 #5 收单操作行 路线1）：
      // #dictActionBtn 已静态入 .dict-action-row 包裹层（无内层 group），
      // 注入序修正为 官方│镜像（原 镜像│官方）；行首「下载源」前缀标签走
      // JS 态 MSG（禁 index.html 静态中文）；无操作 kind 整行隐藏不留空行
      const row = btn.parentElement;
      if (row && dlItem.downloadable) {
        row.style.display = '';
        let srcLabel = row.querySelector('.dict-src-label');
        if (!srcLabel) {
          srcLabel = document.createElement('span');
          srcLabel.className = 'dict-src-label';
          srcLabel.textContent = MSG.dict_download_source;
          row.insertBefore(srcLabel, row.firstChild);
        }
        let offBtn = row.querySelector('.dict-src-official');
        if (!offBtn) {
          offBtn = document.createElement('button');
          offBtn.type = 'button';
          offBtn.className = 'btn btn-ghost btn-compact dict-src-official';
          offBtn.textContent = MSG.dictSrcOfficialOnly;
          offBtn.title = MSG.dictSrcOfficialHint;   // CN 可达性提示
          offBtn.addEventListener('click', () =>
            dictDownload($('dictSelect').value, offBtn, 'official'));
          row.insertBefore(offBtn, btn);
        }
        let mirBtn = row.querySelector('.dict-src-mirror');
        if (!mirBtn) {
          mirBtn = document.createElement('button');
          mirBtn.type = 'button';
          mirBtn.className = 'btn btn-ghost btn-compact dict-src-mirror';
          mirBtn.textContent = MSG.dictSrcMirrorOnly;
          mirBtn.addEventListener('click', () =>
            dictDownload($('dictSelect').value, mirBtn, 'mirror'));
          row.insertBefore(mirBtn, btn);   // 插入序=官方│镜像│主下载键
        }
        offBtn.style.display = '';
        mirBtn.style.display = '';
        // 无镜像 kind（sudachi_full=官方 CDN 单源）→ disabled + 离线导入指引
        const srcInfo = _dictSourcesCache[kind] || {};
        const hasMirror = srcInfo.has_mirror !== false;
        mirBtn.disabled = !hasMirror;
        mirBtn.title = hasMirror ? '' : MSG.dictSrcMirrorlessHint;
        // 下载中禁整行（跨 kind 切换洞收口，见 _dictBusyKind 注）：任一词典
        // 下载进行中，无论当前选中谁，整行三键禁用+is-busy——切走的用户看到
        // 禁用态，切回下载中的 kind 也不会误读为可重入；终态由 finally 的
        // dictLoad() 重渲染自然解除
        if (_dictBusyKind) {
          row.classList.add('is-busy');
          btn.disabled = true;
          offBtn.disabled = true;
          mirBtn.disabled = true;
        } else {
          row.classList.remove('is-busy');
        }
      } else if (row) {
        // 无操作 kind（jieba/english_rules，无下载按钮/无源组）：整行隐藏
        row.style.display = 'none';
      }
    }
  }
  async function dictDownload(kind, btn, source) {
    const st = $('dictStatus');
    // 下载中占位（D2026-1004-01 #5 跨 kind 并发洞收口）：已有下载进行中
    // 直接拒绝重入（按钮禁用态是第一道，此处兜底防编程态/竞态双击）
    if (_dictBusyKind) return;
    _dictBusyKind = kind;
    // 终态按钮文案（2.6.3 批B）：双按钮路径恢复各自标签，主按钮恢复「下载」
    const doneLabel = source === 'official' ? MSG.dictSrcOfficialOnly
      : source === 'mirror' ? MSG.dictSrcMirrorOnly : MSG.dict_download;
    // 进度迁移（2.3.1 批1）：实时进度显示在详情区独立进度条 #dictProgress，
    // #dictStatus 降级为终态行+错误兜底（轮询中的 MB 文本不再写 #dictStatus）
    const prog = $('dictProgress');
    const bar = prog ? prog.querySelector('.progress-bar') : null;
    const fill = prog ? prog.querySelector('.progress-fill') : null;
    const text = prog ? prog.querySelector('.progress-text') : null;
    const showProgress = (visible) => { if (prog) prog.style.display = visible ? '' : 'none'; };
    const fmtMB = (n) => (n / 1048576).toFixed(1);
    // 每次轮询按 p.phase 全量刷新进度条状态（相位往返安全：切换须重置旧态——
    // download→verify 清 fill 宽度、verify→download 移除 indeterminate）
    const renderProgress = (phase, downloaded, total, owned) => {
      if (!prog) return;
      const prefix = owned ? '' : `${kind} `;   // 下载中切换下拉：文本标注词典归属
      if (phase === 'download' && total) {
        if (bar) bar.classList.remove('indeterminate');
        const pct = Math.min(100, Math.round(downloaded / total * 100));
        if (fill) fill.style.width = pct + '%';
        if (text) text.textContent = `${prefix}${fmtMB(downloaded)}/${fmtMB(total)}MB`;
      } else {
        // verify/extract 相位与无 total 的 download 相位走不定态
        if (fill) fill.style.width = '';
        if (bar) bar.classList.add('indeterminate');
        const label = phase === 'verify' ? MSG.dict_verify
          : phase === 'extract' ? MSG.dict_extract : MSG.dict_downloading;
        if (text) text.textContent = prefix + label;
      }
    };
    // 下载中禁整行（2.6.5 段2 D2026-1004-01 #5）：三键 setDisabled + 行
    // .is-busy（disabled 态走 --surface-3 底，非仅 opacity）
    const actionRow = btn ? btn.parentElement : null;
    const srcBtns = actionRow
      ? [actionRow.querySelector('.dict-src-official'),
         actionRow.querySelector('.dict-src-mirror')]
      : [];
    if (actionRow) actionRow.classList.add('is-busy');
    srcBtns.forEach((b) => { if (b) b.disabled = true; });
    if (btn) { btn.disabled = true; btn.textContent = MSG.dict_downloading; }
    if (st) dictShowStatus(st, '', false, null);
    let poller = null;
    let lastBytes = 0;
    const stopPoll = () => { if (poller) { clearInterval(poller); poller = null; } };
    showProgress(true);
    poller = setInterval(async () => {
      try {
        const p = await pywebview.api.refine_dict_download_progress(kind);
        if (!p || !p.success || !p.phase) return;
        if (typeof p.downloaded === 'number' && p.downloaded > 0) {
          lastBytes = p.downloaded;
        }
        // kind 归属校验（批清单条件 3）：下载中切换下拉→进度条标注词典归属，
        // 且不覆盖当前选中词典的按钮态
        const sel = $('dictSelect');
        const owned = !sel || sel.value === kind;
        renderProgress(p.phase, p.downloaded || 0, p.total, owned);
        // 回退可见提示（2.6.3 批B 评议员条件①）：auto 轮换不再静默，
        // note 写 #dictStatus（后端快照粘滞字段，轮询必能采样）
        if (p.note && owned && st) st.textContent = p.note;
        if (!owned) return;
        if (p.phase === 'download') {
          if (btn) btn.textContent = MSG.dict_downloading;   // 纯文案，百分比迁移至进度条
        } else if (p.phase === 'verify') {
          if (btn) btn.textContent = MSG.dict_verify;
        } else if (p.phase === 'extract') {
          if (btn) btn.textContent = MSG.dict_extract;
        }
      } catch (e) { /* 进度轮询失败不干扰主流程 */ }
    }, 1000);
    try {
      // 源透传（2.6.3 批B）：undefined/非法由后端按 auto 处理
      const r = await pywebview.api.refine_dict_download(kind, source || 'auto');
      if (r && r.success) {
        // 终态大小以 done 快照为准（轮询最后一拍可能滞后）
        try {
          const f = await pywebview.api.refine_dict_download_progress(kind);
          if (f && f.success && typeof f.downloaded === 'number' &&
              f.downloaded > 0) lastBytes = f.downloaded;
        } catch (e) { /* ignore */ }
      }
      // 2.6.5 段2（D2026-1004-01 #6）：失败时一行人话（红）+ 技术串下沉
      // details 诊断网格——diag 取自后端 failed 快照（refine_dict_download_
      // progress 轮询桥，phase=failed 时携带段1 落库的七字段契约）
      let diag = null;
      if (!(r && r.success)) {
        try {
          const f = await pywebview.api.refine_dict_download_progress(kind);
          if (f && f.success && f.phase === 'failed' && f.diag) diag = f.diag;
        } catch (e) { /* 诊断快照获取失败不掩盖主错误 */ }
      }
      if (st) {
        dictShowStatus(st,
          (r && r.success)
            ? `${MSG.dict_download_done}：${r.path}（${fmtMB(lastBytes)}MB）`
            : dictFailureText(`${(r && r.error) || ''}`, diag),
          !(r && r.success), diag);
      }
    } catch (e) {
      // 异常路径=未知错误：一行人话沿用原文（红），无诊断网格
      if (st) dictShowStatus(st, dictFailureText(String(e), null), true, null);
    } finally {
      stopPoll();                       // 防重复 poller 泄漏
      showProgress(false);              // 隐藏统一放 finally（覆盖成功/失败/异常三路径含 catch）
      _dictBusyKind = null;             // 先清占位再 dictLoad()：重渲染据此解除整行禁用
      if (actionRow) actionRow.classList.remove('is-busy');
      srcBtns.forEach((b) => { if (b) b.disabled = false; });
      const sel = $('dictSelect');
      if (!sel || sel.value === kind) {
        // 终态与当前选中词典一致才直改按钮；不一致交由 dictLoad()→
        // dictRenderDetail() 重刷详情区对齐（重渲染不触碰静态进度条）
        if (btn) { btn.disabled = false; btn.textContent = doneLabel; }
      }
      dictLoad();
    }
  }

  // ---- 词典目录设置 + 一键迁移（批1b D2026-1002-12 件1/件2）----
  // 更改目录：refine_pick_dict_dir 收口（对话框+持久化+注入生效）；
  // needs_migration 时弹 AppModal 确认（不静默自动迁移），确认后走迁移
  async function dictPickDir() {
    const st = $('dictStatus');
    try {
      const r = await pywebview.api.refine_pick_dict_dir();
      if (!r || !r.success || !r.path) return;   // 取消/失败静默返回
      _dictOldDir = r.old_dir || '';
      _dictNeedsMigration = !!r.needs_migration;
      if (_dictNeedsMigration) {
        const ok = await AppModal.confirm(
          MSG.dict_migrate_title,
          MSG.dict_migrate_confirm(_dictOldDir, r.old_files || 0),
          { okText: MSG.dict_migrate_btn });
        if (ok) {
          await dictMigrate();
          return;                       // dictMigrate 内部已 dictLoad 收尾
        }
        // 用户暂不迁移：保留迁移键（旧文件仍在旧目录，可稍后点按钮）
      }
      if (st) st.textContent = MSG.dict_dir_set_ok;
      dictLoad();
    } catch (e) {
      if (st) st.textContent = String(e);
    }
  }
  // 恢复默认：refine_clear_dict_dir 收口（不做任何文件删除/迁移）
  async function dictRestoreDir() {
    const st = $('dictStatus');
    try {
      const r = await pywebview.api.refine_clear_dict_dir();
      if (st) st.textContent = (r && r.success)
        ? MSG.dict_dir_restored
        : ((r && r.error) || '');
      _dictNeedsMigration = false;
      dictLoad();
    } catch (e) {
      if (st) st.textContent = String(e);
    }
  }
  // 一键迁移：refine_dict_migrate 执行引擎（复制+校验+原子改名，源不删）；
  // 进度复用下载进度通道（伪 kind '__migrate__'）1s 轮询 #dictProgress
  async function dictMigrate() {
    const st = $('dictStatus');
    const migBtn = $('dictMigrateBtn');
    const prog = $('dictProgress');
    const bar = prog ? prog.querySelector('.progress-bar') : null;
    const fill = prog ? prog.querySelector('.progress-fill') : null;
    const text = prog ? prog.querySelector('.progress-text') : null;
    const showProgress = (visible) => { if (prog) prog.style.display = visible ? '' : 'none'; };
    const fmtMB = (n) => (n / 1048576).toFixed(1);
    if (migBtn) { migBtn.disabled = true; migBtn.textContent = MSG.dict_migrating; }
    if (st) st.textContent = '';
    showProgress(true);
    if (bar) bar.classList.add('indeterminate');
    let poller = null;
    const stopPoll = () => { if (poller) { clearInterval(poller); poller = null; } };
    poller = setInterval(async () => {
      try {
        const p = await pywebview.api.refine_dict_download_progress('__migrate__');
        if (!p || !p.success || !p.phase) return;
        if (typeof p.total === 'number' && p.total > 0) {
          if (bar) bar.classList.remove('indeterminate');
          const pct = Math.min(100, Math.round((p.downloaded || 0) / p.total * 100));
          if (fill) fill.style.width = pct + '%';
          if (text) text.textContent = `${MSG.dict_migrating} ${fmtMB(p.downloaded || 0)}/${fmtMB(p.total)}MB`;
        } else if (text) {
          const xy = p.file_count ? `（${p.file_index || 0}/${p.file_count}）` : '';
          text.textContent = MSG.dict_migrating + xy;
        }
      } catch (e) { /* 进度轮询失败不干扰主流程 */ }
    }, 1000);
    try {
      const r = await pywebview.api.refine_dict_migrate(_dictOldDir);
      if (r && r.success) {
        _dictNeedsMigration = false;      // 成功才消迁移态（失败可重试续传）
        if (st) st.textContent = MSG.dict_migrate_done(
          (r.migrated || []).length, (r.skipped || []).length);
      } else {
        if (st) st.textContent = `${MSG.dict_migrate_failed}：${(r && r.error) || ''}`;
      }
    } catch (e) {
      if (st) st.textContent = `${MSG.dict_migrate_failed}：${String(e)}`;
    } finally {
      stopPoll();                         // 防重复 poller 泄漏
      showProgress(false);
      if (fill) fill.style.width = '';    // 复位填充（bar 相位态由下次使用方全量刷新）
      if (migBtn) { migBtn.disabled = false; migBtn.textContent = MSG.dict_migrate_btn; }
      dictLoad();
    }
  }

  // ---- 首启数据目录引导（批1b 件4）：frozen-only，哨兵防再弹 ----
  // AppModal.confirm 自定义双键：ok=选择其他目录（原生对话框→
  // refine_set_data_root 复用既有重启提示文案），cancel=使用当前目录；
  // 引导交互过即写哨兵（mark_data_guide_done），任何分支不重复骚扰
  async function maybeShowDataGuide() {
    try {
      if (!window.pywebview || !pywebview.api ||
          !pywebview.api.should_show_data_guide) return;
      const r = await pywebview.api.should_show_data_guide();
      if (!r || !r.success || !r.show) return;
      const pick = await AppModal.confirm(
        MSG.data_guide_title,
        MSG.data_guide_body(r.data_root || ''),
        { okText: MSG.data_guide_pick, cancelText: MSG.data_guide_keep });
      if (pick) {
        const sel = await pywebview.api.refine_pick_folder();
        if (sel && sel.success && sel.path) {
          const s = await pywebview.api.refine_set_data_root(sel.path);
          if (s && s.success) {
            // 复用批1a 件5 的重启阻断提示文案（改根后重启生效语义一致）
            await AppModal.alert(MSG.data_root_restart_title,
                                 MSG.data_root_restart_body);
          }
        }
      }
      pywebview.api.mark_data_guide_done();
    } catch (e) { /* 引导失败静默（不阻塞主流程） */ }
  }

  // ---- 远程数据加载（pywebview 就绪后调用一次）----
  async function loadRemote() {
    applySavedStageSettings();
    bindDirectionControls();
    bindCleanerDirControls();
    dataRootLoad();
    dictLoad();
    maybeShowDataGuide();   // 批1b 件4：首启数据目录引导（frozen-only，哨兵防再弹）
    // 角色卡下拉动态化（追加1）：启动时列目录填充下拉与方向卡 datalist
    // （不自动加载编辑器内容——保持现状，打开词库页/切换选中时才加载）
    tplRefreshSelect(false);
    window.__refineTplTabHook = () => tplRefreshSelect(true);
    // 净语配置目录：不再硬编码填充——留空=自动查找（回落链
    // config/templates→包内默认）；已存值由 applySavedStageSettings 回填
    glLoad();
    glLearnedLoad();
    // 批2（D2026-1002-12 拍板点2）：页面就绪不再自动拉取模型列表，只认
    // 「刷新/测试」两个显式入口；已存模型名由 applySavedStageSettings 注入
    refreshPipelineMirror();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindDom);
  } else {
    bindDom();
  }

  window.__refineLoadRemote = loadRemote;
})();

// ============================================================
// Initialization
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
    console.log('SubTrans GUI initialized');

    // i18n：先把 MSG 文案注入 data-i18n* 标记的元素
    applyI18n();

    // Initialize components (pure DOM parts)
    ConsoleManager.init();
    ProgressManager.init();
    ProgressManager.reset();
    FileListManager.init();
    DirectoryControls.init();
    RunControlsInit();
    KeyboardShortcuts.init();
    ThemeManager.init();
    TranslatorManager.init();

    // Update Start button state once at startup
    TranslatorManager.updateButtons();

    // 右栏卡 3 镜像：加载后渲染 + 引擎页控件变更时同步（只读，无回写）
    refreshPipelineMirror();
    ['refineS1Model', 'refineConcurrency'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', refreshPipelineMirror);
    });

    // 卡 3 整卡跳转引擎页（只读镜像的修改入口）
    const pipelineCard = document.getElementById('pipelineCard');
    if (pipelineCard) {
        pipelineCard.addEventListener('click', () => switchTab('tab-engine'));
        pipelineCard.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                switchTab('tab-engine');
            }
        });
    }

    ConsoleManager.log(MSG.gui_initialized, 'success');
    ConsoleManager.log(MSG.gui_usage_hint, 'info');
});

function RunControlsInit() {
    // Placeholder hook for future global controls; refine panel owns its own buttons.
}

// 右栏卡 3 只读镜像（D2026-0930-09 批2）：读引擎页当前配置渲染，不做双向同步
function refreshPipelineMirror() {
    const line = document.getElementById('pipelineMirrorLine');
    if (!line) return;
    const model = (($('refineS1Model') || {}).value || '').trim() || '—';
    const conc = (($('refineConcurrency') || {}).value || '').trim() || '1';
    line.textContent = `${MSG.pipeline_mirror_model}：${model}　·　${MSG.pipeline_mirror_conc} ${conc}`;
}

// PyWebView ready event — backend bridge is now available.
window.addEventListener('pywebviewready', async () => {    console.log('PyWebView API ready!');
    ConsoleManager.log(MSG.bridgeConnected, 'success');
    window.__pywebviewReady = true;

    // A3 主题持久化走后端：读取 settings.theme 并应用
    await ThemeManager.loadSavedThemeFromBackend();

    await AppState.loadDefaultOutputDir();

    // 右栏系统状态摘要卡（D2026-1001 批3）：只读四接口，逐项降级
    SystemSummary.load();

    // Load saved stage settings, glossary, templates and model lists
    if (window.__refineLoadRemote) {
        await window.__refineLoadRemote();
    }

    // Initialize feature status indicators
    await FeatureStatus.init();

    // 2.7.1 首启空闲探测（D2026-1005-01 承接批，README 提示句口径）：后台
    // 触发一次 refine_asr_status 回填探测快照缓存（短暂启动一次 Python
    // 子进程，通常数秒；不阻塞首屏，结果稍后显示在 ASR 卡/模型管理面板）
    setTimeout(() => {
        try {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.refine_asr_status();
            }
        } catch (e) { /* 后台预热失败静默（显式探测按钮兜底） */ }
    }, 3000);
});

// Feature status management
const FeatureStatus = {
    async init() {
        try {
            const status = await pywebview.api.get_system_status();
            if (status.success && status.features) {
                this.updateGrammarHintBadge(status.features.grammar_hints);
            }
        } catch (e) {
            console.warn('Failed to load system status:', e);
        }
    },

    updateGrammarHintBadge(info) {
        const badge = document.getElementById('grammarHintBadge');
        if (!badge) return;
        badge.style.display = '';

        if (info.available) {
            badge.className = 'feature-badge active';
                badge.title = MSG.grammar_hint_on_title;
        } else {
            badge.className = 'feature-badge inactive';
            badge.title = MSG.grammar_hint_off_title;
        }
    }
};
