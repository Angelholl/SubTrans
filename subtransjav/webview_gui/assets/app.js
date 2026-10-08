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
    folderSkippedPipeline: n => `ℹ 跳过 ${n} 个流水线中间稿/终稿（pass1/pass2、_refine_、_final_）`,
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
    // 硬字幕压制（2.8.0 批1 件5，D2026-1007-03）：全 JS 态键（零静态
    // data-i18n 消耗）；双表同步镜像见 strings.py「硬字幕压制」节
    // ============================================================
    encodeEntryReview: '压制成品（硬字幕）',
    encodeEntryGuide: '压制成品',
    encodeModalTitle: '压制成品',
    encodeModalFmt: '格式',
    encodeFmtH264: 'H.264（兼容性最好）',
    encodeFmtH265: 'H.265（体积更小）',
    encodeFmtAv1: 'AV1（体积最小·耗时可能最长）',
    encodeModalBackend: '后端',
    encodeBackendAuto: '自动',
    encodeBackendGpu: 'GPU（批2 提供）',
    encodeModalQuality: '画质',
    encodeQCompress: '高压缩（体积优先）',
    encodeQBalanced: '均衡（推荐）',
    encodeQQuality: '高画质（观感优先）',
    encodeModalRes: '分辨率',
    encodeResOriginal: '保持原样',
    encodeModalRate: '码控',
    encodeRateTier: '按画质档（推荐）',
    encodeRateVbr: '目标码率',
    encodeModalBitrate: '目标码率（kbps，留空=按参考表派生）',
    encodeModalOutDir: '输出目录（留空=与视频同目录）',
    encodeModalFont: '字幕字号（12-72，缺省 22）',
    encodeModalAudio: '音频',
    encodeAudioCopy: '直接复制（推荐）',
    encodeModalEnhance: '画质增强（降噪+锐化；关闭=忠实源）',
    encodeModalAdvanced: '高级',
    encodeModalAdvancedPh: '自定义参数 / 预设管理 —— 批2 面板完整化时启用',
    encodePresetLabel: '预设',
    encodePresetSave: '存为预设',
    encodePresetDelete: '删除',
    encodePresetBuiltinGroup: '内置',
    encodePresetUserGroup: '我的预设',
    encodePresetNamePrompt: '预设名称：',
    encodePresetSaved: '预设已保存',
    encodePresetDeleteConfirm: '删除预设「{n}」？',
    encodeCustomLabel: '自定义参数（逃生门，追加到命令尾部）',
    encodeCustomHint: '以空格分隔，如：-crf 18 -threads 8；与面板参数冲突或破坏固定约束（像素格式/滤镜链/码控映射）的旗标会被拒绝并显因',
    encodeAv1Warn: 'AV1 编码耗时显著更长（CPU 下与视频时长同量级），请留意预估时长',
    encodeKnobDenoise: '降噪强度（0-10）',
    encodeKnobDeblock: '去块强度（0-1）',
    encodeKnobSharpen: '锐化量（0-2）',
    encodeKnobVolume: '音量增益 dB（±12，≠0 需重编码音频）',
    encodeAutoSwitch: '翻译完成后自动压制（硬字幕）',
    encodeAutoDoneLine: '[压制] 全部完成——可在队列底条「打开文件夹」',
    encodeJobsLine: '共 {n} 个文件 · 硬字幕烧录 · 底端居中白字黑边',
    encodeSecBase: '基础',
    encodeSecSubAudio: '字幕与音频',
    encodeEtaNone: '（时长预估需 ffmpeg 就绪后预检提供）',
    encodeEtaTotal: '预计总时长：约 {t}',
    encodeOk: '加入压制队列',
    encodeNoJobs: '没有可压制的文件——请先在「翻译」页添加文件并完成翻译',
    encodeSupplyMissing: '当前 ffmpeg 不支持硬字幕烧录（缺 libass/subtitles 滤镜）。需要下载一次完整版 ffmpeg（约 191MB，存到数据目录，仅下载一次）。现在下载吗？',
    encodeSupplyFailed: 'ffmpeg 下载失败：{e}',
    encodeSupplyDone: '完整版 ffmpeg 就绪，请重新点击「压制成品」发起压制',
    encodeOverwriteTitle: '覆盖确认',
    encodeOverwriteBody: '以下成品文件已存在，覆盖它们吗？\n\n{list}',
    encodeCommitRejected: '未能入队：{e}',
    encodeConflict: '压制任务进行中，无法开始翻译——请等待压制完成，或在队列底条中取消压制任务',
    encodeTranslateConflict: '翻译任务进行中，无法加入压制队列——请等待翻译完成后再试',
    encodeCancelOneConfirm: '取消当前压制任务？',
    encodeCancelAllConfirm: '取消当前任务并清空排队中的任务？',
    encodeDockRunning: '压制中',
    encodeDockDone: '压制完成',
    encodeDockFailed: '压制失败',
    encodeDockIdle: '队列空闲',
    encodeStQueued: '排队中',
    encodeStRunning: '压制中',
    encodeStDone: '已完成',
    encodeStFailed: '失败',
    encodeStCancelled: '已取消',
    encodeStStopped: '已停止',
    encodeNoVideo: '未找到视频',
    encodeNoSubtitle: '终稿字幕不存在',
    encodeProbeErr: '媒体识别失败',
    encodeRetry: '重试',
    encodeOpenFolder: '打开文件夹',
    encodeCancelJob: '取消',
    encodeStop: '停止',
    encodeExpand: '展开',
    encodeCollapse: '收起',
    encodeDismiss: '关闭',
    encodeDownloadDock: '下载 ffmpeg 组件',
    encodeMinutes: '{m} 分',
    encodeEtaPending: '预估中',

    // 压制参数独立设置项（D2026-1008-01 批2，D2026-1008-01）：弹窗编辑
    // 模式+高级参数页/右栏自动压制行两入口；全 JS 态键（零静态 data-i18n），
    // 双表同步镜像见 strings.py「硬字幕压制」节
    encodeEditTitle: '压制参数',
    encodeEditHint: '参数编辑模式——仅保存压制参数，不发起压制；压制成品请在校对页/导读页选中已完成字幕后再点「压制成品」',
    encodeSaveParams: '保存参数',
    encodeParamsSaved: '压制参数已保存——自动压制与下次压制将使用这组参数',
    encodeParamsSaveFail: '参数保存失败：{e}',
    encodeAdvGroupTitle: '压制',
    encodeAdvGroupDesc: '压制成品的默认参数（格式/画质/音量等），「翻译完成后自动压制」同样使用这组参数',
    encodeAdvOpenBtn: '打开压制参数',
    encodeParamsLink: '参数',
    encodeGpuEditTitle: 'GPU 可用性在发起一次压制时自动检测；此处暂不可选',
    encodeSummaryLine: (parts) => `当前压制参数：${parts.join(' · ')}`,
    encodeSummaryEmpty: '暂无已保存的压制参数（点「打开压制参数」设置）',
    encodeSummaryVol: (db) => `音量 ${db}dB`,
    encodeSummaryAt: (t) => `保存于 ${t}`,

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
    // 批4（D2026-1008-01）：提示扩含 LM Studio JIT 按需加载说明
    //（首次调用高负载来自 LM Studio 进程属正常，交待给用户）
    aiAnalyzing: '分析中（可能需要 1-3 分钟）…首次调用 LM Studio 需按需加载大模型（大模型首次加载可能需数分钟，期间高负载来自 LM Studio 进程属正常）',
    // 批4（D2026-1008-01）：分析/修复可停止——停止按钮与取消收口文案
    //（C12：取消后 LM Studio 侧可能已完成 JIT 加载并常驻，如实交代）
    aiStopBtn: '停止分析',
    aiStopPending: '正在停止分析…',
    aiCancelled: '已取消分析。LM Studio 侧可能已完成模型加载并常驻（后续分析会更快）；如需释放显存请在 LM Studio 中卸载模型。',
    bfStopBtn: '停止修复',
    bfStopPending: '正在停止修复…',
    bfCancelled: '已取消批量修复。已落盘条目以重翻台账为准，可再次发起处理余量。',
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
    // 批 8b：chip 增第四态 failed（后端 files_status 四态，批 8a 透出）
    chip_pending: '等待中',
    chip_running: '翻译中',
    chip_done: '已完成',
    chip_resumable: '可续传',
    chip_failed: '失败',
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
    // 2.7.4 件1（D2026-1007-01）：缺失态文案收敛为 chip 短句（tag-none）
    media_source_none: '未包含媒体路径',
    media_source_change_btn: '更换',
    // 2.7.4 件1 新增 JS 态键（零静态 i18n 消耗；preview_media_matched 备件2
    // 「已自动匹配」数据接线用）
    guide_custom_source: '自定义导读',
    guide_copy_path: '复制路径',
    guide_copy_path_done: '已复制',
    guide_media_missing_hint: '媒体路径缺失：条目可查看但不可试听，请在「更换」中显式指定媒体文件路径',
    preview_matching: '正在匹配媒体路径并定位片段…',
    preview_media_matched: '已自动匹配媒体路径',
    // 「重新自动匹配」键（err_kind=path_invalid 时错误槽内出现）
    preview_rematch: '重新自动匹配',
    media_override_apply: '应用',
    media_override_placeholder: '输入媒体文件完整路径（等价 --media-path，仅本报告会话内生效）',
    media_override_applied: '已设为本报告会话内媒体来源（显式指定）',
    media_override_cleared: '已清除覆盖，恢复导读自动发现来源',
    audio_preview_close: '关闭',
    audio_preview_failed: m => `试听失败：${m}`,
    audio_preview_no_timing: '该条目缺少可解析时间轴，无法试听',
    audio_preview_no_guide: '请先加载质量报告导读',
    // C4（D2026-1007-02）：direct 播放静默失败可见化（audio error 监听入错误槽）
    audio_preview_play_error:
      '音频播放失败：浏览器无法解码该媒体（编码不受支持或文件不可访问）',
    // F5（D2026-1007-02）：试听「未找到媒体」（err_kind=no_candidate）时
    // 错误槽内出现的文件选择直通键
    preview_pick_media: '选择媒体文件…',

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
    // 2.7.3 件⑤（词典下载停止按钮）：停止中过渡/已停止收口文案（JS 态
    // 键，禁 index.html 静态消耗）；停止按钮主文案复用 MSG.stop_btn（
    // :235 既有键），零新增按钮键
    dict_stop_pending: '正在停止下载…',
    dict_stopping: '停止中…',
    dict_stop_note: '已停止下载（未安装）。可切换网络代理后重新下载。',
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
    dict_install_hint: '该词典未安装——下载后语法提示可用。直连下载慢属正常：系统会先走系统代理、失败自动切直连（两跳）；也可切换镜像或用 --dict-from-file 离线导入。',
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
    // 2.7.3 件⑧批 8b（D2026-1006-01）：Console 结构化活动流 + 显示层裁剪
    // （全部 JS 态键，不入 data-i18n 快照——index.html 零新增 data-i18n）
    activity_title: '活动流',
    raw_log_toggle: '原始日志',
    export_log: '导出日志',
    copy_log: '复制日志',
    activity_stage_start: stage => `▶ ${stage} 开始`,
    activity_file_done: f => `✓ ${f} 完成`,
    activity_file_failed: f => `✗ ${f} 失败`,
    activity_risk_file: (f, phase, m) => `⚠ ${f}（${phase}）：${m}`,
    activity_risk: (phase, m) => `⚠（${phase}）：${m}`,
    activity_error: m => `✗ ${m}`,
    activity_heartbeat_stale: s => `心跳超时 ${s} 秒，进程仍在运行…`,
    // task_finished payload 字段（pipeline_v2.py _finish_task）：
    // files_ok/files_degraded/files_failed/risk_count/status（success|partial|failed）
    activity_summary: (ok, deg, fail, n) =>
        `任务完成：成功 ${ok} · 降级 ${deg} · 失败 ${fail} · 风险 ${n}`,
    activity_summary_status: s => `（${s}）`,
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
    // 2.7.4 件3（D2026-1007-01）：预览改结构化弹窗（AppModal.batchFixPreview），
    // 全条目渲染不再省略（batchFixPreviewMore 删除）、分类明细改 chips
    // （batchFixCats 删除）；下列为弹窗新增 JS 态键
    batchFixConfirmOk: '开始修复',
    batchFixExpand: '展开全文',
    batchFixCollapse: '收起',
    batchFixExcerptOnly: '仅摘录，完整译文未加载',
    batchFixEstimate: n => `预估调用：翻译 ${n} 次 + 复验全片 AI 分析 1 次`,
    batchFixProvider: p => `修复服务商：${p}`,
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
    // 2.7.4 件C（D2026-1007-02）：修复生效配置明示行（C7 补链：生效
    // provider/model 由后端 refine_preview_fix_config 统一解析，拒绝原因
    // 明示行红色直显；确认框副行同键复用）
    batchFixUsing: (p, m) => `修复将使用：${p} / ${m}`,
    batchFixModelUnset: '未配置',
    // 批3（D2026-1008-01）：分析模型三件套（下拉+刷新+测试）+ 生效行
    // 中文字面量收编（全 JS 态键，零静态 data-i18n）；批3 修复模型独立
    // 配置行四键（fix_cfg_label 等）随 P2（D2026-1008-02）删行退役
    ai_model_follow_hint: '跟随阶段A 当前模型',
    aiEffFollow: '跟随阶段A',
    aiEffIndependent: '独立配置',
    aiModelUnset: '（未指定）',
    aiEffectiveLine: (tag, prov, model) => `分析模型：${tag} — ${prov} / ${model}`,
    aiCloudNote: ' ｜ 注意：分析时报告内容将发送至该云端服务',
    // P2（D2026-1008-02）：分析独立配置半配置忽略说明（G5-补，JS 态键；
    // 后端侧同义键=strings.py fix_ai_indep_half_ignored，双表镜像）
    aiIndepHalfIgnored: '分析独立配置不完整，已忽略',
    batchFixSourceTag: s => `（生效源：${s}）`,
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
    // 2.7.3 件③：ASR 状态三口径对齐——红绿灯空态文案 + 下拉占位项
    // （全 JS 态零静态 id/data-i18n；strings.py 双表同步）
    asrModelUnselected: '未选择',
    asrModelPlaceholder: '未选择（点选即保存）',
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
    mpUnverifiedTitle: '下载元数据未核验：请自备落位',
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
    },

    // ============================================================
    // 压制参数弹窗（2.8.0 批1 件5，D2026-1007-03）：kind='encode' 三分区
    // 容器（批1/批2 共用骨架，开工门 C8——高级区批1 置空禁用占位，批2
    // 扩展不重建）。body 全 createElement 注入（全 class+data-testid，
    // 零新增 id/data-i18n）。okBtn.onclick 赋值式绑定（防叠加）→
    // _settle(true)；resolve 包装器把 true（含 Enter 键）转 {ok, params}
    // ——Enter=按当前表单值确认。取消/ESC/遮罩=resolve(null)。
    // opts = {jobs:[{name, out_path, eta_s, video_exists, subtitle_exists}],
    //         totalEtaS, last:<encode_get_last_params 的 params>}
    // 参数编辑模式（D2026-1008-01 批2：压制参数独立设置项）：opts.editOnly
    // =true 时无选中文件也可打开——标题改「压制参数」、jobsLine 换编辑
    // 提示、「加入压制队列」确认键隐藏，另设「保存参数」按钮（状态行给
    // 成功/失败反馈，成功经 o.onSaved 回调同步调用方 _lastParams 缓存与
    // 摘要行）；保存只走 encode_save_params 桥，绝不触碰 preflight/commit/
    // jobs（Enter=关闭不保存，保存只经「保存参数」按钮，失败反馈留状态行）。
    // GPU 可用性无独立探测桥（仅 preflight 顺带双检），编辑模式 GPU 选项
    // 保持置灰并以 title 显因（encodeGpuEditTitle）。
    // ============================================================
    encode(opts) {
        if (this._busy) return Promise.resolve(null);       // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(null);            // 骨架缺席兜底
        const o = opts || {};
        const editOnly = !!o.editOnly;
        const jobs = o.jobs || [];
        const api = window.pywebview && window.pywebview.api;   // 预设通道（models 先例）
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent =
            editOnly ? MSG.encodeEditTitle : MSG.encodeModalTitle;
        body.textContent = '';
        body.style.whiteSpace = 'normal';
        input.style.display = 'none';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        // 编辑模式：隐藏「加入压制队列」（开始压制仅存于正常模式），
        // 另设「保存参数」按钮于分区 3 尾部（下文 saveParamsBtn）
        okBtn.style.display = editOnly ? 'none' : '';
        okBtn.textContent = MSG.encodeOk + '（' + jobs.length + '）';
        const last = o.last || {};

        const mk = (tag, cls, parent) => {
            const el = document.createElement(tag);
            if (cls) el.className = cls;
            if (parent) parent.appendChild(el);
            return el;
        };
        const mkField = (parent, text) => {
            const w = mk('div', 'enc-field', parent);
            const lb = mk('label', null, w);
            lb.textContent = text;
            return w;
        };
        const mkSelect = (parent, options, value) => {
            const s = mk('select', 'form-select', parent);
            options.forEach((op) => {
                const opt = document.createElement('option');
                opt.value = op.v;
                opt.textContent = op.t;
                if (op.disabled) opt.disabled = true;
                s.appendChild(opt);
            });
            if (value) s.value = value;
            return s;
        };

        // 任务概览行（编辑模式换编辑提示：本弹窗只存参数不入队）
        const jobsLine = mk('div', 'enc-jobs-line', body);
        jobsLine.textContent = editOnly
            ? MSG.encodeEditHint
            : MSG.encodeJobsLine.replace('{n}', String(jobs.length));

        // —— 分区 1：基础 ——
        const sec1 = mk('div', 'enc-section', body);
        mk('h4', null, sec1).textContent = MSG.encodeSecBase;
        const grid1 = mk('div', 'enc-grid', sec1);
        const elFmt = mkSelect(mkField(grid1, MSG.encodeModalFmt), [
            { v: 'h264', t: MSG.encodeFmtH264 },
            { v: 'h265', t: MSG.encodeFmtH265 },
            { v: 'av1', t: MSG.encodeFmtAv1 },
        ], last.video_format || 'h264');
        // 后端（批2）：GPU 编码器经供给层双检解析——可用则点亮并显名，
        // 不可用保持禁用并以 title 透出逐候选显因（A9 不静默降级）
        const gpuEnc = (o.gpu && o.gpu.encoder) || "";
        const elBackend = mkSelect(mkField(grid1, MSG.encodeModalBackend), [
            { v: 'auto', t: MSG.encodeBackendAuto },
            { v: 'cpu', t: 'CPU' },
            { v: 'gpu', t: gpuEnc ? ('GPU（' + gpuEnc + '）') : MSG.encodeBackendGpu,
              disabled: !gpuEnc },
        ], 'auto');
        if (!gpuEnc && o.gpu && o.gpu.reasons && o.gpu.reasons.length) {
            elBackend.title = o.gpu.reasons.join('；');
        }
        // 编辑模式无 preflight（不触碰）→ GPU 可用性无从探测：选项置灰
        // 并以 title 显因（发起一次压制后经预检自动检测点亮）
        if (editOnly && !gpuEnc) {
            elBackend.title = MSG.encodeGpuEditTitle;
        }
        const elQuality = mkSelect(mkField(grid1, MSG.encodeModalQuality), [
            { v: 'compress', t: MSG.encodeQCompress },
            { v: 'balanced', t: MSG.encodeQBalanced },
            { v: 'quality', t: MSG.encodeQQuality },
        ], last.quality || 'balanced');
        const elRes = mkSelect(mkField(grid1, MSG.encodeModalRes), [
            { v: 'original', t: MSG.encodeResOriginal },
            { v: '720p', t: '720p' },
            { v: '1080p', t: '1080p' },
            { v: '1440p', t: '1440p' },
            { v: '2160p', t: '2160p' },
        ], last.resolution || 'original');
        const elRate = mkSelect(mkField(grid1, MSG.encodeModalRate), [
            { v: 'quality_tier', t: MSG.encodeRateTier },
            { v: 'target_vbr', t: MSG.encodeRateVbr },
        ], last.rate_mode || 'quality_tier');
        const bitField = mkField(grid1, MSG.encodeModalBitrate);
        const elBitrate = mk('input', 'form-input', bitField);
        elBitrate.type = 'number';
        elBitrate.min = '100';
        elBitrate.style.display = elRate.value === 'target_vbr' ? '' : 'none';
        if (last.target_bitrate_kbps) elBitrate.value = String(last.target_bitrate_kbps);
        elRate.addEventListener('change', () => {
            elBitrate.style.display = elRate.value === 'target_vbr' ? '' : 'none';
        });
        const outField = mkField(grid1, MSG.encodeModalOutDir);
        outField.classList.add('full');
        const elOutDir = mk('input', 'form-input', outField);
        elOutDir.type = 'text';
        elOutDir.placeholder = 'D:\\Videos';
        if (last.out_dir) elOutDir.value = String(last.out_dir);
        // 长任务硬性规定①（E3 批1 落点）：预估行（编辑模式不发起压制，
        // 预估无意义 → 整行隐藏）
        const etaRow = mk('div', 'enc-eta-row', sec1);
        if (editOnly) {
            etaRow.style.display = 'none';
        } else if (o.totalEtaS && o.totalEtaS > 0) {
            etaRow.textContent = '⏱ ' + MSG.encodeEtaTotal
                .replace('{t}', Math.max(1, Math.round(o.totalEtaS / 60)) + ' ' + '分');
        } else {
            etaRow.textContent = '⏱ ' + MSG.encodeEtaNone;
        }
        // 长任务硬性规定③（E3 批2 落点）：AV1 警告条（预期管理）
        const av1Warn = mk('div', 'enc-eta-row', sec1);
        av1Warn.style.background = 'var(--warn-soft)';
        av1Warn.style.display = 'none';
        av1Warn.textContent = '⚠ ' + MSG.encodeAv1Warn;
        elFmt.addEventListener('change', () => {
            av1Warn.style.display = elFmt.value === 'av1' ? '' : 'none';
        });
        if (elFmt.value === 'av1') av1Warn.style.display = '';

        // —— 分区 2：字幕与音频 ——
        const sec2 = mk('div', 'enc-section', body);
        mk('h4', null, sec2).textContent = MSG.encodeSecSubAudio;
        const grid2 = mk('div', 'enc-grid', sec2);
        const elFont = mk('input', 'form-input', mkField(grid2, MSG.encodeModalFont));
        elFont.type = 'number';
        elFont.min = '12';
        elFont.max = '72';
        elFont.value = String(last.font_size || 22);
        const elAudio = mkSelect(mkField(grid2, MSG.encodeModalAudio), [
            { v: 'copy', t: MSG.encodeAudioCopy },
            { v: '96k', t: 'AAC 96k' },
            { v: '128k', t: 'AAC 128k' },
            { v: '192k', t: 'AAC 192k' },
        ], last.audio_mode || 'copy');
        const enhWrap = mk('div', 'enc-field full', grid2);
        const enhLabel = mk('label', null, enhWrap);
        const elEnhance = mk('input', null, enhLabel);
        elEnhance.type = 'checkbox';
        elEnhance.checked = last.enhance_on !== false;
        enhLabel.appendChild(document.createTextNode(' ' + MSG.encodeModalEnhance));
        // 批3 增强链旋钮（决策九-1 C3''：缺省=owner AV1 链，可调随预设存取；
        // 三旋钮映射 hqdn3d 降噪主强度/deblock alpha/unsharp luma amount；
        // 初值从 last.enhance_params 解析——预设与上次参数同源）
        const knob0 = (s, i, dft) => {
            const v = parseFloat(String(s || '').split(':')[i]);
            return isNaN(v) ? dft : v;
        };
        const lastEp = last.enhance_params || {};
        const knobRow = mk('div', 'enc-field full', grid2);
        knobRow.style.display = 'grid';
        knobRow.style.gridTemplateColumns = '1fr 1fr 1fr';
        knobRow.style.gap = '8px';
        const mkKnob = (labelText, min, max, step, val) => {
            const w = mk('div', null, knobRow);
            const lb = mk('label', null, w);
            lb.textContent = labelText;
            const inp = mk('input', 'form-input', w);
            inp.type = 'number';
            inp.min = String(min);
            inp.max = String(max);
            inp.step = String(step);
            inp.value = String(val);
            return inp;
        };
        const knobDenoise = mkKnob(MSG.encodeKnobDenoise, 0, 10, 0.1,
            knob0(lastEp.hqdn3d, 0, 0.8));
        const knobDeblock = mkKnob(MSG.encodeKnobDeblock, 0, 1, 0.01,
            knob0(String(lastEp.deblock || '').replace('alpha=', ''), 0, 0.07));
        const knobSharpen = mkKnob(MSG.encodeKnobSharpen, 0, 2, 0.05,
            knob0(lastEp.unsharp, 2, 0.5));
        const syncKnobs = () => {
            const dis = !elEnhance.checked;
            [knobDenoise, knobDeblock, knobSharpen].forEach((k) => { k.disabled = dis; });
        };
        elEnhance.addEventListener('change', syncKnobs);
        syncKnobs();
        // 批3 音量旋钮（±12dB 受控；≠0 强制 aac 重编码——后端回落显因透出）
        const volField = mkField(grid2, MSG.encodeKnobVolume);
        const elVolume = mk('input', 'form-input', volField);
        elVolume.type = 'number';
        elVolume.min = '-12';
        elVolume.max = '12';
        elVolume.step = '0.5';
        elVolume.value = String(typeof last.volume_db === 'number' ? last.volume_db : 0);

        // —— 分区 3：高级（批2 启用：预设管理+自定义参数逃生门；增强链
        //     参数旋钮归批3）——
        const sec3 = mk('div', 'enc-section', body);
        mk('h4', null, sec3).textContent = MSG.encodeModalAdvanced;
        const grid3 = mk('div', 'enc-grid', sec3);
        const presetField = mkField(grid3, MSG.encodePresetLabel);
        presetField.classList.add('full');
        const presetRow = mk('div', null, presetField);
        presetRow.style.display = 'flex';
        presetRow.style.gap = '6px';
        const elPreset = mk('select', 'form-select', presetRow);
        const saveBtn = mk('button', 'btn btn-secondary btn-compact', presetRow);
        saveBtn.type = 'button';
        saveBtn.textContent = MSG.encodePresetSave;
        const delBtn = mk('button', 'btn btn-ghost btn-compact', presetRow);
        delBtn.type = 'button';
        delBtn.textContent = MSG.encodePresetDelete;
        const cpField = mkField(grid3, MSG.encodeCustomLabel);
        cpField.classList.add('full');
        const elCustom = mk('textarea', 'form-input', cpField);
        elCustom.rows = 2;
        elCustom.placeholder = MSG.encodeCustomHint;
        if (last.custom_params) elCustom.value = String(last.custom_params);

        // —— 参数编辑模式（D2026-1008-01 批2）专属尾部：状态行+「保存参数」
        // ——保存=collect()→encode_save_params 桥（后端同一校验路径+原子写
        // hardsub_last.json）；成功经 o.onSaved 同步调用方 _lastParams 缓存
        // 与高级参数页摘要行，状态行人话反馈；绝不触碰 preflight/commit/jobs
        const saveStatus = editOnly ? mk('div', 'enc-eta-row enc-edit-status', body) : null;
        const saveParamsBtn = editOnly
            ? mk('button', 'btn btn-secondary btn-compact enc-save-params-btn', body) : null;
        const saveEditParams = async () => {
            if (!api) return false;
            const params = collect();
            saveParamsBtn.disabled = true;
            let r = null;
            try {
                r = await api.encode_save_params(JSON.stringify(params));
            } catch (e) {
                r = { success: false, error: String(e) };
            }
            saveParamsBtn.disabled = false;
            if (r && r.success) {
                if (typeof o.onSaved === 'function') o.onSaved(params);
                saveStatus.textContent = MSG.encodeParamsSaved;
                return true;
            }
            const why = (r && (r.tip || r.error)) || String(r);
            saveStatus.textContent = MSG.encodeParamsSaveFail.replace('{e}', why);
            return false;
        };
        if (editOnly) {
            saveParamsBtn.type = 'button';
            saveParamsBtn.textContent = MSG.encodeSaveParams;
            saveParamsBtn.addEventListener('click', () => { saveEditParams(); });
        }

        // 表单值回填（预设加载用；字段全集=collect 快照）
        const applyParams = (p) => {
            p = p || {};
            if (p.video_format) elFmt.value = p.video_format;
            // backend 回填（批2 顺修）：用户预设含 backend 快照，gpu 仅在
            // 探测已知可用时恢复（collect 同口径），cpu 显式恢复，其余/缺省
            // 落回 auto——与 collect 读取逻辑镜像
            if (p.backend) {
                elBackend.value = (p.backend === 'gpu' && gpuEnc) ? 'gpu'
                    : (p.backend === 'cpu' ? 'cpu' : 'auto');
            }
            if (p.quality) elQuality.value = p.quality;
            if (p.resolution) elRes.value = p.resolution;
            if (p.rate_mode) elRate.value = p.rate_mode;
            elBitrate.style.display = elRate.value === 'target_vbr' ? '' : 'none';
            if (p.target_bitrate_kbps) elBitrate.value = String(p.target_bitrate_kbps);
            if (p.audio_mode) elAudio.value = p.audio_mode;
            if (p.font_size) elFont.value = String(p.font_size);
            if (typeof p.enhance_on === 'boolean') elEnhance.checked = p.enhance_on;
            if (p.enhance_params) {
                const ep = p.enhance_params;
                if (String(ep.hqdn3d || '').length) knobDenoise.value = knob0(ep.hqdn3d, 0, 0.8);
                if (String(ep.deblock || '').length) {
                    knobDeblock.value = knob0(String(ep.deblock).replace('alpha=', ''), 0, 0.07);
                }
                if (String(ep.unsharp || '').length) knobSharpen.value = knob0(ep.unsharp, 2, 0.5);
            }
            if (typeof p.volume_db === 'number') elVolume.value = String(p.volume_db);
            if (typeof p.custom_params === 'string') elCustom.value = p.custom_params;
            av1Warn.style.display = elFmt.value === 'av1' ? '' : 'none';
            syncKnobs();
        };
        const fillPresets = async () => {
            let pl = null;
            try { pl = await api.encode_presets_list(); } catch (e) { pl = null; }
            elPreset.textContent = '';
            if (pl && pl.success) {
                const g1 = document.createElement('optgroup');
                g1.label = MSG.encodePresetBuiltinGroup;
                (pl.builtin || []).forEach((p) => {
                    const op = document.createElement('option');
                    op.value = '__b__:' + p.name;
                    op.textContent = p.name;
                    g1.appendChild(op);
                });
                elPreset.appendChild(g1);
                const names = Object.keys(pl.user || {});
                if (names.length) {
                    const g2 = document.createElement('optgroup');
                    g2.label = MSG.encodePresetUserGroup;
                    names.forEach((n) => {
                        const op = document.createElement('option');
                        op.value = '__u__:' + n;
                        op.textContent = n;
                        g2.appendChild(op);
                    });
                    elPreset.appendChild(g2);
                }
            }
        };
        elPreset.addEventListener('change', async () => {
            const v = elPreset.value || '';
            if (v.startsWith('__b__:')) {
                let pl = null;
                try { pl = await api.encode_presets_list(); } catch (e) { return; }
                const hit = (pl.builtin || []).find((p) => p.name === v.slice(6));
                if (hit) applyParams(hit.params);
            } else if (v.startsWith('__u__:')) {
                let pl = null;
                try { pl = await api.encode_presets_list(); } catch (e) { return; }
                const hit = (pl.user || {})[v.slice(6)];
                if (hit) applyParams(hit);
            }
        });
        saveBtn.addEventListener('click', async () => {
            const name = await AppModal.prompt(MSG.encodePresetNamePrompt, '');
            if (!name || !String(name).trim()) return;
            try {
                const r = await api.encode_preset_save(String(name).trim(), collect());
                if (r && r.success) await fillPresets();
                AppModal.alert(MSG.encodeModalTitle,
                    r && r.success ? MSG.encodePresetSaved : String(r && r.error || ''));
            } catch (e) {
                AppModal.alert(MSG.encodeModalTitle, String(e));
            }
        });
        delBtn.addEventListener('click', async () => {
            const v = elPreset.value || '';
            if (!v.startsWith('__u__:')) return;   // 内置三档不可删
            const name = v.slice(6);
            const ok = await AppModal.confirm(
                MSG.encodeModalTitle, MSG.encodePresetDeleteConfirm.replace('{n}', name));
            if (!ok) return;
            try {
                const r = await api.encode_preset_delete(name);
                if (r && r.success) await fillPresets();
            } catch (e) { /* 下次打开自愈 */ }
        });
        fillPresets();

        const collect = () => ({
            video_format: elFmt.value,
            backend: elBackend.value === 'gpu' && gpuEnc ? 'gpu' : 'auto',
            quality: elQuality.value,
            resolution: elRes.value,
            rate_mode: elRate.value,
            target_bitrate_kbps: elRate.value === 'target_vbr'
                ? (parseInt(elBitrate.value, 10) || null) : null,
            audio_mode: elAudio.value,
            font_size: Math.min(72, Math.max(12, parseInt(elFont.value, 10) || 22)),
            enhance_on: elEnhance.checked,
            enhance_params: {
                hqdn3d: knobDenoise.value + ':0.6:0.7:0.6',
                deblock: 'alpha=' + knobDeblock.value + ':beta=0.07',
                unsharp: '5:5:' + knobSharpen.value + ':3:3:0.3',
            },
            volume_db: Math.max(-12, Math.min(12, parseFloat(elVolume.value) || 0)),
            out_dir: elOutDir.value.trim(),
            custom_params: elCustom.value.trim(),
        });
        okBtn.onclick = () => AppModal._settle(true);

        this._busy = true;
        this._kind = 'encode';
        root.style.display = 'flex';
        return new Promise((resolve) => {
            this._resolve = (value) => {
                okBtn.onclick = null;
                // true（确认键/Enter）→ 按当前表单值结算；falsy（取消/ESC/遮罩）→ null。
                // 编辑模式确认键隐藏、Enter=关闭不保存（保存只经「保存参数」
                // 按钮——失败反馈须留在可见状态行，结算后弹窗已收起）
                resolve(value ? { ok: true, params: collect() } : null);
            };
        });
    },

    // ============================================================
    // 批量修复确认框（2.7.4 件3，D2026-1007-01）：结构化确认弹窗，取代
    // batchFixRun 原纯文本 AppModal.confirm（slice(0,10) 只列前 10 条）。
    // 复用 #appModal 骨架 + dataset.bound 一次性绑定（download 先例；
    // 绑定块与 _open confirm 同款：Enter=确认/ESC=取消/遮罩=取消）；
    // kind='batchfix' 不命中 _settle 任何阻塞分支（_dlRunning/_edSaving
    // 仅 download/editor kind），关闭永不阻塞。
    // 结算三态（钉）：确认键/Enter=resolve(true)；取消键/ESC/遮罩点击=
    // resolve(false)；_busy 重入=立即 resolve(false)（单例不叠加）。
    // 布局：.modal-lg 配方（编辑器同款）——.bfp-meta/.bfp-cats 固定不
    // 滚动，仅 .bfp-list 滚动（flex:1;min-height:0;overflow-y:auto），
    // 按钮区在 .modal-card 弹性列内恒可见（窄窗滚到底确认键仍在）。
    // 列表容器零键盘监听：不拦截 keydown/不 stopPropagation，Enter/Esc
    // 语义保持 document 全局（列表滚动由鼠标滚轮承载）。
    // 现译全文：texts 由调用方从 lastGuideData.items 构建（前端经
    // read_output_artifact 已持有导读 json；后端 action_items 摘录限长
    // 仅约束回包形状）——按 Number(it.index) 强转匹配（后端 idx 非 int
    // 回 null，先判 null 再强转防 Number(null)=0 陷阱），查无全文回退
    // it.excerpt 并带「仅摘录」标记；DOM 放全文不 JS 切字符串（防代理对
    // 切半），CSS max-height 3 行折叠（底部渐隐 mask 提示截断；Chromium
    // 146 实测 -webkit-line-clamp 被重映射为 flow-root 失效，故弃用）
    // + 逐条展开/收起键 + title 悬停全文。
    // opts = {title, okText?, meta:[{text,warn?}], cats:[{cat,count}],
    //         head, items:[{index,category,timing,excerpt}], texts:{idx:text}}
    // body 全 createElement 注入（FROZEN_IDS 冻结：零新增 id/data-i18n）；
    // 关闭自清理 modal-lg/whiteSpace（editor 同款，防污染后续 confirm）。
    // ============================================================
    batchFixPreview(opts) {
        if (this._busy) return Promise.resolve(false);      // 重入=取消结算
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        const o = opts || {};
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = o.title || '';
        body.textContent = '';
        body.style.whiteSpace = 'normal';   // .modal-card .modal-body 默认 pre-wrap
        const card = root.querySelector('.modal-card');
        if (card) card.classList.add('modal-lg');
        input.style.display = 'none';
        okBtn.style.display = '';
        okBtn.textContent = o.okText || MSG.ui_ok;
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        if (!root.dataset.bound) {          // 与 _open 同款一次性绑定（首个打开的可能是本模态）
            root.dataset.bound = '1';
            root.addEventListener('click', (e) => {
                if (e.target === root) AppModal._settle(AppModal._cancelValue());
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

        const el = (tag, cls, text) => {
            const n = document.createElement(tag);
            if (cls) n.className = cls;
            if (text != null) n.textContent = text;
            return n;
        };
        // 分类色系（复用既有 token 族，非映射类回退中性灰）：
        // cps_too_fast=警示 / untranslated=主色 / antonym_yamete=危险
        const catCls = (c) => (c === 'cps_too_fast' ? ' bfp-cat-warn'
            : c === 'untranslated' ? ' bfp-cat-primary'
            : c === 'antonym_yamete' ? ' bfp-cat-danger' : ' bfp-cat-neutral');

        // —— 头部非滚动元信息区（预估调用/服务商/云端成本/超上限提示）——
        const metaBox = el('div', 'bfp-meta');
        (o.meta || []).forEach((m) => {
            metaBox.appendChild(el('div',
                'bfp-meta-row' + (m.warn ? ' bfp-meta-warn' : ''), m.text));
        });
        body.appendChild(metaBox);

        // —— 分类明细 chips（调用方已按数量降序排列）——
        const catBox = el('div', 'bfp-cats');
        (o.cats || []).forEach((c) => {
            catBox.appendChild(el('span',
                'bfp-cat-chip' + catCls(c.cat), c.cat + ' ' + c.count));
        });
        body.appendChild(catBox);

        if (o.head) body.appendChild(el('div', 'bfp-list-title', o.head));

        // —— 可滚动列表：全部条目渲染，零 slice 截断 ——
        const texts = o.texts || {};
        const listBox = el('div', 'bfp-list');
        (o.items || []).forEach((it) => {
            const idx = (it.index == null) ? null : Number(it.index);
            const full = (idx != null
              && Object.prototype.hasOwnProperty.call(texts, idx))
              ? String(texts[idx]) : null;
            const text = full != null ? full : String(it.excerpt || '');
            const item = el('div', 'bfp-item');
            const head = el('div', 'bfp-item-head');
            head.appendChild(el('span', 'bfp-idx', '#' + it.index));
            head.appendChild(el('span',
                'bfp-cat-chip' + catCls(it.category), it.category));
            const timing = el('span', 'bfp-timing', it.timing || '');
            timing.title = it.timing || '';
            head.appendChild(timing);
            if (full == null) {
                head.appendChild(el('span', 'bfp-trunc', MSG.batchFixExcerptOnly));
            }
            item.appendChild(head);
            const txt = el('div', 'bfp-text', text);
            txt.title = text;               // 悬停全文（折叠态可取全文）
            item.appendChild(txt);
            const toggle = el('button', 'btn btn-ghost btn-compact bfp-toggle',
                MSG.batchFixExpand);
            toggle.type = 'button';
            toggle.addEventListener('click', () => {
                const open = txt.classList.toggle('bfp-open');
                toggle.textContent = open
                  ? MSG.batchFixCollapse : MSG.batchFixExpand;
            });
            item.appendChild(toggle);
            listBox.appendChild(item);
        });
        body.appendChild(listBox);

        this._busy = true;
        this._kind = 'batchfix';
        root.style.display = 'flex';

        // —— 收尾 pass：移除未实际折叠条目的展开键（短文本按钮噪音清理，
        // 2.7.4 件3 黑盒走查修订）——判据 scrollHeight > clientHeight + 1
        // （max-height 折叠生效时 clientHeight 被钉在 3 行高度、scrollHeight
        // 反映全文高度，该判据可靠）。须在 display:flex 之后测：display:none
        // 下两值恒 0，判据失效会误杀全部按钮。取舍：仅本渲染 tick 检测一次
        // （本地系统字体无 FOUT，同 tick 内读取即强制同步布局）；弹窗会话内
        // 不随宽度变化重新检测——窄窗拖宽后新达标条目残留按钮属极端场景
        // 可接受（title 悬停仍可读全文），已折叠条目展开/收起往复后按钮
        // 恒保留（不二次检测）。
        listBox.querySelectorAll('.bfp-item').forEach((row) => {
            const txt = row.querySelector('.bfp-text');
            const toggle = row.querySelector('.bfp-toggle');
            if (txt && toggle && txt.scrollHeight <= txt.clientHeight + 1) {
                toggle.remove();        // 移除而非隐藏（DOM 干净，无死节点）
            }
        });

        okBtn.focus();
        return new Promise((resolve) => {
            this._resolve = (value) => {
                // 自清理（editor 同款）：modal-lg/whiteSpace 复位，
                // 防污染后续 alert/confirm/prompt
                if (card) card.classList.remove('modal-lg');
                body.style.whiteSpace = '';
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

    // ---- chip 态映射（D2026-0930-09 批2 三态；批 8b 增 failed 第四态：
    //      后端 files_status 四态 pending/running/done/failed，批 8a 透出）----
    chipClass(state) {
        return {
            pending: 'chip-pending',
            running: 'chip-running',
            done: 'chip-done',
            resumable: 'chip-resumable',
            failed: 'chip-failed'
        }[state] || 'chip-pending';
    },

    chipText(state) {
        return {
            pending: MSG.chip_pending,
            running: MSG.chip_running,
            done: MSG.chip_done,
            resumable: MSG.chip_resumable,
            failed: MSG.chip_failed
        }[state] || MSG.chip_pending;
    },

    setState(path, state) {
        if (!state) return;
        this.itemStates[path] = state;
        this.updateChips();
    },

    // files_status 映射（basename -> state）：只更新命中的文件，不回退其他项。
    // 批 8a 口径补充：backend pending（phase_started 前的初始态）视为无态——
    // 命中不写入，文件 chip 保持现状（默认即为 pending 等待灰，视觉等价，
    // 且不覆盖断点恢复探测已打上的 resumable 态）
    applyStates(map) {
        if (!map) return;
        const base = p => p.split(/[\\/]/).pop();
        let touched = false;
        AppState.selectedFiles.forEach(p => {
            const st = map[base(p)];
            if (st && st !== 'pending' && this.itemStates[p] !== st) {
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
                // 2.7.3 件④：流水线中间稿/终稿被智能过滤跳过时补明细行
                if (result.skipped_count > 0) {
                    ConsoleManager.log(MSG.folderSkippedPipeline(result.skipped_count), 'info');
                }
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
// 2.7.3 件⑧批 8b（D2026-1006-01）：显示层 500 行环形裁剪 + 会话内全量
// `_lines`（定版 D4：裁剪仅显示层，导出/复制走全量数组）
// ============================================================
const ConsoleManager = {
    _lines: [],
    _MAX_DOM_LINES: 500,

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

        // 导出/复制按钮（i18n 冻结：文案 JS 填，HTML 零 data-i18n）
        const exportBtn = document.getElementById('exportConsoleBtn');
        if (exportBtn) {
            exportBtn.textContent = MSG.export_log;
            exportBtn.addEventListener('click', () => this.exportLog());
        }
        const copyBtn = document.getElementById('copyConsoleBtn');
        if (copyBtn) {
            copyBtn.textContent = MSG.copy_log;
            copyBtn.addEventListener('click', () => this.copyLog(copyBtn));
        }

        this._initRawLogToggle();
    },

    // ---- 原始日志折叠（默认收起 + localStorage 持久化，定版 D4）----
    _RAWLOG_KEY: 'subtrans_rawlog_collapsed',

    _initRawLogToggle() {
        const toggle = document.getElementById('rawLogToggleBtn');
        const output = document.getElementById('consoleOutput');
        if (!toggle || !output) return;
        toggle.textContent = MSG.raw_log_toggle;

        const apply = collapsed => {
            output.style.display = collapsed ? 'none' : '';
            toggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
            toggle.setAttribute('title', MSG.raw_log_toggle);
        };
        const persist = collapsed => {
            try {
                localStorage.setItem(this._RAWLOG_KEY, collapsed ? '1' : '0');
            } catch (e) { /* localStorage 不可用（隐私模式等）：仅本次会话生效 */ }
        };

        let collapsed;
        try {
            collapsed = localStorage.getItem(this._RAWLOG_KEY);
        } catch (e) { collapsed = null; }
        if (collapsed === null) {
            // 无历史记录：默认收起并落盘（定版 D4）
            collapsed = '1';
            persist(true);
        }
        apply(collapsed === '1');

        toggle.addEventListener('click', () => {
            const next = output.style.display !== 'none';
            persist(next);
            apply(next);
        });
    },

    // ---- 会话内全量行缓冲 + 显示层裁剪 ----

    _trimDom(output) {
        // 只裁 DOM 不动 _lines（定版 D4）：超出 500 行从最旧开始移除
        while (output.children.length > this._MAX_DOM_LINES) {
            output.removeChild(output.firstChild);
        }
    },

    _scrollBottom(output) {
        requestAnimationFrame(() => {
            if (output) {
                output.scrollTop = output.scrollHeight;
            }
        });
    },

    log(message, type = 'info') {
        const output = document.getElementById('consoleOutput');
        this._lines.push(message);
        const line = document.createElement('div');
        line.className = `console-line ${type}`;
        line.textContent = message;
        output.appendChild(line);
        this._trimDom(output);
        this._scrollBottom(output);
    },

    clear() {
        const output = document.getElementById('consoleOutput');
        output.innerHTML = `<div class="console-line">${MSG.ready}</div>`;
        this._lines = [];
    },

    appendRaw(text) {
        const output = document.getElementById('consoleOutput');

        const lines = text.split('\n');

        lines.forEach((line, index) => {
            if (index === lines.length - 1 && line === '') return;

            this._lines.push(line || ' ');
            const lineEl = document.createElement('div');
            lineEl.className = 'console-line';
            lineEl.textContent = line || ' ';
            output.appendChild(lineEl);
        });
        this._trimDom(output);
        this._scrollBottom(output);
    },

    // ---- 导出 / 复制（空内容静默忽略）----

    exportLog() {
        if (this._lines.length === 0) return;
        const stamp = new Date();
        const p = n => String(n).padStart(2, '0');
        const name = `subtrans-console-${stamp.getFullYear()}${p(stamp.getMonth() + 1)}${p(stamp.getDate())}-${p(stamp.getHours())}${p(stamp.getMinutes())}${p(stamp.getSeconds())}.log`;
        const blob = new Blob([this._lines.join('\n')],
            { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    },

    copyLog(btn) {
        if (this._lines.length === 0) return;
        const text = this._lines.join('\n');
        const flash = () => {
            btn.textContent = MSG.ui_copied;
            setTimeout(() => { btn.textContent = MSG.copy_log; }, 1500);
        };
        const fallback = () => {
            // clipboard API 不可用/被拒：textarea + execCommand 降级
            try {
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                const ok = document.execCommand('copy');
                ta.remove();
                if (ok) flash();
            } catch (e) { /* 两条复制通路都失败：静默（剪贴板非关键路径） */ }
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(flash).catch(fallback);
        } else {
            fallback();
        }
    }
};

// ============================================================
// Activity Stream（2.7.3 件⑧批 8b：Console 面板内、原始日志上方的
// 结构化活动流）。由 TranslatorManager.startStatusPolling 每拍喂
// get_translation_status 快照，内部差分打点：
//   阶段开始 / 文件完成与失败 / 风险增量（自 TranslatorManager 迁移，
//   _reportedRiskCount 旧字段删除）/ 错误 / 心跳超时告警 / 完成摘要。
// 上限 200 行，DOM 与内部数组同裁（无全量保留需求，导出走 ConsoleManager）。
// ============================================================
// 心跳超时判定单点：优先消费后端 snapshot 已算好的 heartbeat_stale；
// 仅当该键为 undefined（旧后端兼容）才回退本地 age>阈值 判定
// （阈值取后端 heartbeat_stale_s，缺省 45s ≈ 2.25×心跳间隔 20s）。
function heartbeatIsStale(status) {
    if (status.heartbeat_stale !== undefined) {
        return status.heartbeat_stale === true;
    }
    const staleS = (typeof status.heartbeat_stale_s === 'number')
        ? status.heartbeat_stale_s : 45;
    return status.heartbeat_age != null && status.heartbeat_age > staleS;
}

const ActivityStream = {
    _MAX_LINES: 200,
    _rows: [],
    _last: null,            // 首拍基线标记（null=尚未初始化，不回放历史）
    _fileStates: {},        // 上次 files_status 快照
    _riskCount: 0,          // 原 TranslatorManager._reportedRiskCount 迁移至此
    _lastError: null,
    _heartbeatAlerted: false,
    _summaryShown: false,
    _stage: null,

    // 新任务新流：startTranslation 成功分支调用，清空活动流与差分状态
    reset() {
        this._rows = [];
        this._last = null;
        this._fileStates = {};
        this._riskCount = 0;
        this._lastError = null;
        this._heartbeatAlerted = false;
        this._summaryShown = false;
        this._stage = null;
        const el = document.getElementById('consoleActivity');
        if (el) el.innerHTML = '';
    },

    _add(text, cls) {
        this._rows.push(text);
        const el = document.getElementById('consoleActivity');
        if (el) {
            const line = document.createElement('div');
            line.className = `console-line ${cls || 'info'}`;
            line.textContent = text;
            el.appendChild(line);
            // DOM 与内部数组同裁
            while (this._rows.length > this._MAX_LINES) {
                this._rows.shift();
                if (el.firstChild) el.removeChild(el.firstChild);
            }
            el.scrollTop = el.scrollHeight;
        }
    },

    update(status) {
        if (!status) return;

        // 阶段开始：current_stage 变化且非空（阶段名用后端原文）
        if (status.current_stage && status.current_stage !== this._stage) {
            this._stage = status.current_stage;
            this._add(MSG.activity_stage_start(status.current_stage), 'info');
        }

        // 文件完成/失败：对比上次 files_status 快照；首拍只建基线不回放历史；
        // running 新出现不打点（避免刷屏）；pending 视为无变化
        if (status.files_status) {
            if (this._last !== null) {
                Object.keys(status.files_status).forEach(f => {
                    const st = status.files_status[f];
                    const prev = this._fileStates[f];
                    if (st === 'done' && prev !== 'done') {
                        this._add(MSG.activity_file_done(f), 'success');
                    } else if (st === 'failed' && prev !== 'failed') {
                        this._add(MSG.activity_file_failed(f), 'error');
                    }
                });
            }
            this._fileStates = Object.assign({}, status.files_status);
        }

        // 风险增量（自 startStatusPolling 迁移，行文案带文件归属）
        const reported = this._riskCount || 0;
        if ((status.risk_count || 0) > reported) {
            const risks = status.risks || [];
            const fresh = risks.slice(
                Math.max(0, risks.length - (status.risk_count - reported)));
            fresh.forEach(r => {
                const msg = (r && (r.message || r.type)) || MSG.risk_word;
                const phase = (r && r.phase) || MSG.risk_word;
                if (r && r.file) {
                    this._add(MSG.activity_risk_file(r.file, phase, msg),
                        'warning');
                } else {
                    this._add(MSG.activity_risk(phase, msg), 'warning');
                }
            });
            this._riskCount = status.risk_count;
        }

        // 错误：与上次不同才打（去重）
        if (status.error && status.error !== this._lastError) {
            this._lastError = status.error;
            this._add(MSG.activity_error(status.error), 'error');
        }

        // 心跳超时：进入超时态打一行黄色告警，恢复（不超时）重置告警态
        // （判定单点 heartbeatIsStale：优先后端 heartbeat_stale，旧后端回退本地算）
        const stale = status.status === 'running' && heartbeatIsStale(status);
        if (stale && !this._heartbeatAlerted) {
            this._heartbeatAlerted = true;
            this._add(MSG.activity_heartbeat_stale(
                Math.round(status.heartbeat_age)), 'warning');
        } else if (!stale) {
            this._heartbeatAlerted = false;
        }

        // 完成摘要：task_summary（task_finished payload）非空且未打过 →
        // 绿色摘要行；status 字段（success/partial/failed）存在则加后缀
        const ts = status.task_summary;
        if (ts && !this._summaryShown) {
            this._summaryShown = true;
            const suffix = ts.status
                ? MSG.activity_summary_status(ts.status) : '';
            this._add(MSG.activity_summary(
                ts.files_ok || 0, ts.files_degraded || 0,
                ts.files_failed || 0, ts.risk_count || 0) + suffix, 'success');
        }

        this._last = status;
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
                // 新任务新流：清空结构化活动流与差分状态（2.7.3 件⑧批 8b）
                try { ActivityStream.reset(); }
                catch (e) { console.warn('activity stream reset failed:', e); }
                // 显示链生命线先行：轮询启动不受打点异常影响（D2026-1006-01 件⑦）
                this.startStatusPolling();
                try {
                    ConsoleManager.log(MSG.translationStarted(result.pid), 'info');
                } catch (e) { console.warn('translationStarted log failed:', e); }
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
        this.state.isRunning = false;
        AppState.isRunning = false;
        FileListManager.updateButtons();
        ProgressManager.setIndeterminate(false);
        ProgressManager.setDot('idle');
        this.setStatus(statusText);
    },

    // ---- Status polling ----

    startStatusPolling() {
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
                // （判定单点 heartbeatIsStale：优先后端 heartbeat_stale，
                // 旧后端回退本地算；秒数显示仍用 heartbeat_age）
                if (status.status === 'running' && heartbeatIsStale(status)) {
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

                // 结构化活动流（2.7.3 件⑧批 8b）：差分打点（阶段/文件/风险/
                // 错误/心跳/摘要）。风险打点已整体迁入 ActivityStream（Translator
                // 侧旧计数段删除）；防弹包裹，打点异常不拖垮 status 桥（件⑦
                // 显示链生命线口径）
                try { ActivityStream.update(status); }
                catch (e) { console.warn('activity stream update failed:', e); }

                if (status.progress !== undefined && status.progress > 0) {
                    ProgressManager.setIndeterminate(false);
                    this.setProgress(status.progress);
                }

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

            // 原始日志通道与 status 桥解耦（D2026-1006-01 件⑦）：fetchLogs
            // 自带 try/catch，不随 status 每拍异常断流。
            this.fetchLogs();
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
    // 2.7.4 件1 三发修订（#189 双重转义根因）：& 必须最先转义——原序先
    // 把 " 转成 &quot; 再转 &，会把 &quot; 的 & 二次转义为 &amp;quot;，
    // 页面显示字面 &quot;（所有含引号文本全局受害，非模板双层包裹）
    return String(s == null ? '' : s).replace(/&/g, '&amp;')
      .replace(/"/g, '&quot;').replace(/</g, '&lt;');
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

  // 批3（D2026-1008-01）：分析模型独立配置的已存模型名（回填/保存成功后
  // 记忆；恢复语义对齐 savedStageModels 先例——刷新命中列表恢复选中，
  // 未命中注入标记 option 后选中）
  let savedAiModel = '';

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

  // ============================================================
  // 批3（D2026-1008-01）：分析/修复模型三件套（下拉+刷新+测试）
  // 下拉=select（阶段页 refineS*Model 先例）、刷新=在线拉模型、测试=
  // refine_test_stage 同桥。分析行锚 aiModelInput（id 保留）；修复行全
  // class+data-testid 零 id。状态反馈对齐 stageStatus（✅/❌+状态色）。
  // ============================================================

  // 刷新按钮内联 SVG（逐字对齐阶段页 refineRefreshS* 图标；innerHTML
  // 保存/恢复惯例见 D2026-1001 批2 注释——textContent 会丢图标）
  const MODEL_REFRESH_SVG = '<svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M3 12a9 9 0 0 1 9-9 9.75 9.75 0 0 1 6.74 2.74L21 8"/><path d="M21 3v5h-5"/><path d="M21 12a9 9 0 0 1-9 9 9.75 9.75 0 0 1-6.74-2.74L3 16"/><path d="M8 16H3v5"/></svg>';

  // 行内状态 span（分析行/修复行共用；kind 对齐 stageStatus 口径）
  function trioStatus(el, text, kind) {
    if (!el) return;
    el.style.color = kind === 'err' ? 'var(--status-err)'
      : (kind === 'ok' ? 'var(--status-ok)' : 'var(--text-muted)');
    el.textContent = text;
  }

  // 三件套独立态刷新主体（分析行/修复行同款）：lmstudio 走
  // list_local_models（已加载 ✓ 置前 + 已下载合并——HRO-2 裁定：通用
  // /v1/models 只列已加载会复现"列表空"痛点）；其余 provider 走
  // refine_list_models（api_key 传 null=后端回退已存密钥）。端点用
  // REFINE_PROVIDER_URLS 默认端点（与后端 ai_provider 独立分支"CLI 各
  // provider 默认端点"消费口径一致）。失败恢复原 HTML（阶段页先例）。
  async function refreshTrioSelect(prov, sel, btn, savedModel, status) {
    if (!sel || !btn) return;
    if (!window.pywebview || !window.pywebview.api) {
      status(MSG.api_not_ready, 'err');
      return;
    }
    if (!prov || prov === 'follow') {
      status(MSG.select_provider_first, 'err');
      return;
    }
    btn.disabled = true;
    const old = btn.innerHTML; btn.textContent = '…';
    const originalHTML = sel.innerHTML;
    sel.innerHTML = '<option value="">' + MSG.loading_models + '</option>';
    status(MSG.fetching_models, '');
    try {
      const r = (prov === 'lmstudio')
        ? await window.pywebview.api.list_local_models(
            REFINE_PROVIDER_URLS.lmstudio || '')
        : await window.pywebview.api.refine_list_models(
            prov, REFINE_PROVIDER_URLS[prov] || '', null);
      if (r && r.success && r.models.length) {
        sel.innerHTML = r.models.map(m =>
          '<option value="' + esc(m) + '">' + esc(m)
          + (prov === 'lmstudio' && r.loaded && r.loaded.includes(m)
              ? ' ✓' : '')
          + '</option>').join('');
        // 已存值不在列表→注入标记 option（阶段页先例）；命中→恢复选中
        if (savedModel && !r.models.includes(savedModel)) {
          const marker = document.createElement('option');
          marker.value = savedModel;
          marker.textContent = savedModel;
          sel.appendChild(marker);
        }
        if (savedModel) sel.value = savedModel;
        status(MSG.models_loaded(r.models.length), 'ok');
      } else {
        sel.innerHTML = originalHTML;
        status('❌ ' + ((r && r.error) || MSG.fetch_failed)
          + (r && r.tip ? ' · ' + r.tip : ''), 'err');
      }
    } catch (e) {
      sel.innerHTML = originalHTML;
      status('❌ ' + e, 'err');
    } finally {
      btn.disabled = false; btn.innerHTML = old;
    }
  }

  // 三件套测试主体：桥=refine_test_stage（与阶段页测试按钮同桥同参），
  // 反馈样式对齐 stageStatus（✅/❌ + 状态色 span）
  async function testTrioModel(prov, model, endpoint, key, btn, status) {
    if (!btn) return;
    if (!window.pywebview || !window.pywebview.api) {
      status(MSG.api_not_ready, 'err');
      return;
    }
    btn.disabled = true;
    status(MSG.testing, '');
    try {
      const r = await window.pywebview.api.refine_test_stage(
        prov, model, endpoint, key);
      const ok = !!(r && r.success);
      status((ok ? '✅ ' : '❌ ') + (ok
        ? (r.message || MSG.testing)
        : ((r && (r.tip || r.error)) || MSG.failed)),
        ok ? 'ok' : 'err');
      if (!ok && r && r.tip) console.warn('[refine]', r.tip);
    } catch (e) {
      status('❌ ' + e, 'err');
    } finally {
      btn.disabled = false;
    }
  }

  // 分析行 follow 态统一口径：模型下拉禁用+占位（ai_model_follow_hint）、
  // 刷新/测试按钮随禁（follow=无独立配置可刷可测；provider 切换/回填
  // 共用此单源，避免状态漂移）
  function aiModelApplyFollowState() {
    const sel = $('aiModelInput');
    if (!sel) return;
    const follow = (($('aiProviderSel') || {}).value || 'follow') === 'follow';
    sel.innerHTML = '<option value="" disabled selected>'
      + (follow ? MSG.ai_model_follow_hint : MSG.model_list_empty_hint)
      + '</option>';
    sel.disabled = follow;
    const row = document.querySelector('.ai-config-row');
    ['.ai-model-refresh', '.ai-model-test'].forEach((cls) => {
      const b = row && row.querySelector(cls);
      if (b) b.disabled = follow;
    });
  }

  // 分析行刷新（独立态）
  async function refreshAnalysisModels() {
    const sel = $('aiModelInput');
    const btn = document.querySelector('.ai-config-row .ai-model-refresh');
    if (!sel || !btn) return;
    const st = document.querySelector('.ai-config-row .ai-model-status');
    await refreshTrioSelect(
      (($('aiProviderSel') || {}).value || 'follow'),
      sel, btn, savedAiModel, (t, k) => trioStatus(st, t, k));
  }

  // 分析行测试：follow=测阶段A 当前配置（生效模型语义一致）；
  // 独立态=测所选独立 provider/model（key=null=后端回退已存密钥）
  async function testAnalysisModel() {
    const btn = document.querySelector('.ai-config-row .ai-model-test');
    if (!btn) return;
    const st = document.querySelector('.ai-config-row .ai-model-status');
    const status = (t, k) => trioStatus(st, t, k);
    const prov = (($('aiProviderSel') || {}).value || 'follow');
    if (prov === 'follow') {
      await testTrioModel(
        (($('refineS1Provider') || {}).value || '').toLowerCase(),
        (($('refineS1Model') || {}).value || '').trim(),
        stageEndpoint(1), stageKeyOrNull(1), btn, status);
    } else {
      await testTrioModel(prov,
        (($('aiModelInput') || {}).value || '').trim(),
        REFINE_PROVIDER_URLS[prov] || '', null, btn, status);
    }
  }

  // P2（D2026-1008-02）：修复模型独立配置行随「修复=分析模型完全统一」
  // 删除（其元素定位/follow 态/刷新/测试函数族一并退役）；修复生效模型
  // 以分析独立配置为唯一来源。

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
          // 批3（D2026-1008-01）：模型文本框→下拉——回填改"follow 态单源
          // 应用（禁用+占位，刷新/测试按钮随禁）+ 独立态注入标记 option 后
          // 选中"（阶段页先例）；placeholder 语义随文本框一并退役
          savedAiModel = (r.settings.ai_analyze_model || '').trim();
          const aiFollow = !aiProvSel || aiProvSel.value === 'follow';
          aiModelApplyFollowState();
          if (!aiFollow) {
            if (savedAiModel
                && ![...aiModelInput.options].some(o => o.value === savedAiModel)) {
              const marker = document.createElement('option');
              marker.value = savedAiModel;
              marker.textContent = savedAiModel;
              aiModelInput.appendChild(marker);
            }
            if (savedAiModel) aiModelInput.value = savedAiModel;
          }
        }
        // P2（D2026-1008-02）：修复模型独立配置行已删除——batch_fix_* KV
        // 不再读写（旧键留在用户配置文件无害，不迁移）
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
              ai_analyze_model: ((($('aiModelInput') || {}).value) || '').trim()
            }).then(rv => {
              if (!rv || rv.success !== true) console.warn('[refine] AI 分析设置保存失败');
            }).catch(e => console.warn('[refine] AI 分析设置保存失败', e));
            aiRefreshEffective();
          };
          // 批3（D2026-1008-01）：切 provider 只重置模型下拉空态（follow=
          // 禁用+占位，刷新/测试按钮随禁），不自动拉取（阶段页先例）
          aiProvSel.addEventListener('change', () => {
            aiModelApplyFollowState();
            saveAiConfig();
          });
          const aiModelSel = $('aiModelInput');
          if (aiModelSel) aiModelSel.addEventListener('change', saveAiConfig);
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
  // 2.7.4 件2：试听媒体推断结果每 guide 前端缓存（override/持久化变更时
  // 失效）——导读加载后缺失态即可显示 tag-auto 横幅，不等首次试听
  let inferredMediaCache = {};

  // 状态行（2.7.4 件1 语义收敛）：#guideStatus 同槽复用（FROZEN 零改动），
  // 首用时动态补齐 .status-line 骨架——图标槽（成功✓/失败⚠）+.status-path
  // （mono 11px/nowrap/ellipsis）+媒体缺失琥珀提示槽+复制路径键；
  // 路径回显唯一走本行（guideCustomStatus 收敛为来源 chip，双写撤销）
  function ensureGuideStatusLine() {
    const st = $('guideStatus');
    if (!st || st.dataset.statusUpgraded) return st;
    st.dataset.statusUpgraded = '1';
    st.classList.add('status-path');
    const wrap = st.parentElement;
    if (!wrap) return st;
    wrap.classList.add('status-line');
    const ico = document.createElement('span');
    ico.className = 'status-ico';
    ico.textContent = '✓';
    wrap.insertBefore(ico, st);
    const hint = document.createElement('span');
    hint.className = 'guide-media-hint';
    hint.style.display = 'none';
    wrap.appendChild(hint);
    const copy = document.createElement('button');
    copy.type = 'button';
    copy.className = 'btn btn-ghost btn-sm guide-copy-btn';
    copy.textContent = MSG.guide_copy_path;
    copy.addEventListener('click', () => guideCopyPath(copy));
    wrap.appendChild(copy);
    return st;
  }

  function guideStatus(text, isError) {
    const st = ensureGuideStatusLine();
    if (!st) return;
    st.textContent = text || '';
    st.title = text || '';          // 悬停全文（ellipsis 截断兜底）
    const line = st.parentElement;
    if (!line) return;
    line.classList.toggle('status-err', !!isError);
    const ico = line.querySelector('.status-ico');
    if (ico) ico.textContent = isError ? '⚠' : '✓';
  }

  // 复制路径：clipboard 失败/缺席静默降级（title 悬停可取全文，同
  // AppModal.download copyable 先例）；成功「已复制」1.5s 复位
  function guideCopyPath(btn) {
    const st = $('guideStatus');
    const text = st ? (st.title || st.textContent || '') : '';
    if (!btn || !text) return;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(() => {
        btn.textContent = MSG.guide_copy_path_done;
        setTimeout(() => { btn.textContent = MSG.guide_copy_path; }, 1500);
      }).catch(() => { btn.title = text; });
    } else {
      btn.title = text;
    }
  }

  // 媒体缺失琥珀提示槽（状态行内独立 span，随媒体来源三态联动）
  function mediaMissingHint(show) {
    ensureGuideStatusLine();
    const st = $('guideStatus');
    const hint = st && st.parentElement
      ? st.parentElement.querySelector('.guide-media-hint') : null;
    if (!hint) return;
    hint.textContent = show ? MSG.guide_media_missing_hint : '';
    hint.style.display = show ? '' : 'none';
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
    // 区块重排（2.7.4 件1）：零 DOM 移动——容器挂 .json-blocks（flex
    // column + CSS order：条目1/结论2/章节3/伴生4/meta5），子节点 append
    // 顺序保持静态 DOM 原序
    if (jsonBlocks) jsonBlocks.classList.add('json-blocks');
    const ulC = $('guideConclusions');
    const dlS = $('guideSections');
    const ulP = $('guideCompanions');
    if (ulC) {
      ulC.innerHTML = (data.conclusions || [])
        .map(c => '<li>' + esc(c) + '</li>').join('')
        || '<li>' + MSG.no_conclusions + '</li>';
    }
    if (dlS) {
      // 章节导读分节卡（2.7.4 件1）：dt/dd 平铺改 .section-card——标题行
      // （chevron+title 600 字重）点击展开/收起，note 正文 muted 默认折叠。
      // 容器 dl#guideSections 与 id 零改动；dl 内分组 div 为 HTML5 合法子元素
      const sections = Array.isArray(data.sections) ? data.sections : [];
      dlS.innerHTML = '';
      if (!sections.length) {
        dlS.innerHTML = '<dt>' + MSG.no_sections + '</dt>';
      }
      sections.forEach((s) => {
        const o = s || {};
        const card = document.createElement('div');
        card.className = 'section-card';
        const head = document.createElement('div');
        head.className = 'section-card-head';
        const chev = document.createElement('span');
        chev.className = 'guide-chevd';
        chev.textContent = '▾';
        const title = document.createElement('span');
        title.className = 'section-card-title';
        title.textContent = String(o.title || '');
        head.appendChild(chev);
        head.appendChild(title);
        head.addEventListener('click', () => {
          card.classList.toggle('sect-open');
        });
        const note = document.createElement('div');
        note.className = 'section-card-note';
        note.textContent = String(o.note || '');
        card.appendChild(head);
        card.appendChild(note);
        dlS.appendChild(card);
      });
    }
    const divI = $('guideItems');
    if (divI) {
      const items = Array.isArray(data.items) ? data.items : [];
      // 行动条目标题提级 + 条数 chip（2.7.4 件1）：标题 h4 为静态节点，
      // JS 动态加 .block-title.main 与 .count-chip（applyI18n 首屏已跑完，
      // 动态子节点不会被 i18n 重写抹除；幂等——重渲染仅更新计数）
      const itemsHead = divI.previousElementSibling;
      if (itemsHead && itemsHead.tagName === 'H4') {
        itemsHead.classList.add('block-title', 'main');
        let chip = itemsHead.querySelector('.count-chip');
        if (!chip) {
          chip = document.createElement('span');
          chip.className = 'count-chip';
          itemsHead.appendChild(chip);
        }
        chip.textContent = String(items.length) + ' 条';
      }
      if (!items.length) {
        divI.innerHTML = '<div>' + MSG.guide_items_none + '</div>';
      } else {
        const MAX_ITEMS = 50;
        // 分类徽标复用件3 bfp-cat-chip 色系类（cps=warn/untranslated=
        // primary/antonym=danger，映射缺失回退中性 bfp-cat-neutral）
        const catCls = (c) => (c === 'cps_too_fast' ? 'bfp-cat-warn'
          : c === 'untranslated' ? 'bfp-cat-primary'
          : c === 'antonym_yamete' ? 'bfp-cat-danger' : 'bfp-cat-neutral');
        // 条目行三段化（2.7.4 件1）：.item-head（#编号 mono + 分类徽标 +
        // mono timing ellipsis + 右对齐试听键）/.item-msg（message 全文）/
        // .item-cur（现译 · 状态 muted）。
        // 契约红线：.btn-audio-preview class 与 data-timing 属性必须原样
        // 保留（bindDom 事件委托锚点，试听链路依赖）
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
            + '<div class="item-head">'
            + '<span class="idx-chip">#' + esc(o.index) + '</span>'
            + '<span class="bfp-cat-chip ' + catCls(String(o.category || ''))
            + '">' + esc(o.category) + '</span>'
            + '<span class="item-timing">' + esc(o.timing) + '</span>'
            + (hasTiming
              ? '<button type="button" class="btn btn-ghost btn-sm'
                + ' btn-audio-preview" data-timing="' + esc(o.timing)
                + '">' + esc(MSG.preview_play_btn) + '</button>'
              : '')
            + '</div>'
            + '<div class="item-msg">' + esc(o.message) + '</div>'
            + '<div class="item-cur">' + MSG.guide_item_current_label + cur
            + ' · ' + esc(o.status) + '</div>'
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
      if (!silent) guideStatus(MSG.api_not_ready, true);
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
    // 2.7.4 件1 双写收敛：加载中隐藏来源 chip（成功后按来源重显），
    // 路径回显唯一走 #guideStatus 状态行
    guideCustomStatus('');
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
          // 来源 chip：仅自定义导读成功加载时显示（2.7.4 件1 收敛）
          guideCustomStatus(isCustom
            ? (MSG.guide_txt_loaded(r.path || p)
              + (r.truncated ? MSG.guide_txt_truncated_note : ''))
            : '');
          return;
        }
        lastLoadedGuidePath = r.path || p;
        lastLoadedIsTxt = false;
        lastGuideData = r.data || {};
        updateMediaSourceBar(lastGuideData);
        // 2.7.4 件2：推断缓存命中且当前为缺失态 → tag-auto 横幅显示
        // 推断路径（评议员条件②：持久化条目不在加载时阻塞校验，仅展示）
        const tagNow = $('mediaSourceTag');
        if (tagNow && tagNow.classList.contains('tag-none')
            && inferredMediaCache[lastLoadedGuidePath]) {
          renderMediaTag('tag-auto', MSG.preview_media_matched,
            inferredMediaCache[lastLoadedGuidePath]);
          mediaMissingHint(false);
        }
        guideRender(r.data || {});
        batchFixRefresh();
        guideStatus(MSG.guide_loaded(r.path || p));
        guideCustomStatus(isCustom ? MSG.guide_loaded(r.path || p) : '');
      } else {
        const err = MSG.guide_load_failed((r && r.error) || MSG.unknownError);
        guideStatus(err, true);
      }
    } catch (e) {
      const err = MSG.guide_load_failed(
        e && e.message ? e.message : String(e));
      guideStatus(err, true);
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

  // 「打开其他质量报告导读」来源徽标（2.7.4 件1 语义收敛）：仅自定义导读
  // 成功加载时显示 chip（primary-soft/strong 来源色，title 悬停本次加载
  // 路径）；加载中/失败/非自定义一律隐藏——路径与错误回显唯一走
  // #guideStatus 状态行
  function guideCustomStatus(text, isError) {
    const st = $('guideCustomStatus');
    if (!st) return;
    const show = !isError && !!text;
    st.style.display = show ? '' : 'none';
    if (show) {
      st.classList.add('guide-custom-chip');
      st.textContent = MSG.guide_custom_source;
      st.title = text;
    }
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

  // 媒体来源条标签/路径直写（2.7.4 件2）：推断命中（tag-auto）/重匹配
  // 成功后显示推断路径横幅；与 updateMediaSourceBar 的三态切换共用 DOM
  function renderMediaTag(cls, text, path) {
    const tagEl = $('mediaSourceTag');
    const pathEl = $('mediaSourcePath');
    if (!tagEl || !pathEl) return;
    tagEl.classList.remove('tag-none', 'tag-auto', 'tag-explicit');
    if (cls) tagEl.classList.add(cls);
    tagEl.textContent = text;
    pathEl.textContent = path || '';
    pathEl.title = path || '';
  }

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
    // 三态修饰类（2.7.4 件1）：tag-none=warn 色系 / tag-auto=ok 色系 /
    // tag-explicit=主色（现蓝不变）。tag-auto 仅备类——「已自动匹配」的
    // 数据接线属件2，本件不触发（autoPath 命中仍按既有文案原蓝展示）
    const setTag = (cls, text) => {
      tagEl.classList.remove('tag-none', 'tag-auto', 'tag-explicit');
      if (cls) tagEl.classList.add(cls);
      tagEl.textContent = text;
    };
    if (mediaOverridePath) {
      setTag('tag-explicit', MSG.media_source_explicit);
      pathEl.textContent = mediaOverridePath;
      pathEl.title = mediaOverridePath;   // 悬停全路径
      mediaMissingHint(false);
    } else if (autoPath) {
      // 后端回包 media_path_source=override 时按原语义归显式态（tag-explicit）；
      // 纯自动命中暂用默认原蓝，「已自动匹配」接线属件2（tag-auto 备而不触发）
      setTag(autoIsOverride ? 'tag-explicit' : '',
        autoIsOverride ? MSG.media_source_explicit : MSG.media_source_auto);
      pathEl.textContent = autoPath;
      pathEl.title = autoPath;
      mediaMissingHint(false);
    } else {
      // 缺失态：tag-none 短句 + 状态行琥珀提示（条目可查看但不可试听）
      setTag('tag-none', MSG.media_source_none);
      pathEl.textContent = '';
      pathEl.title = '';
      mediaMissingHint(true);
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

  // ============================================================
  // 试听错误槽（2.7.4 件1 owner 终版裁定）：错误展示从浮层条内迁出为
  // 独立动态槽——旧浮层内静态错误元素废弃（DOM 保留不删不写，零
  // FROZEN 解冻）。槽注入 #tab-guide 页面级稳定容器（no_guide 态——导读
  // 未加载/折叠收起——也可见，不依赖导读加载后才存在的容器）；
  // position:fixed + z-index 1001：高于浮层条 z-900 与模态遮罩 z-1000，
  // 错误态永不被遮。幂等：首帧注入后复用。
  // ============================================================
  function ensurePreviewErrorSlot() {
    let slot = document.querySelector('.preview-error-slot');
    if (slot) return slot;
    slot = document.createElement('div');
    slot.className = 'preview-error-slot';
    const ico = document.createElement('span');
    ico.className = 'preview-error-ico';
    ico.textContent = '⚠';
    const txt = document.createElement('span');
    txt.className = 'preview-error-text';
    const rematch = document.createElement('button');
    rematch.type = 'button';
    rematch.className = 'btn btn-ghost btn-compact preview-error-rematch';
    rematch.textContent = MSG.preview_rematch;
    rematch.style.display = 'none';   // 仅 err_kind=path_invalid 时出现
    rematch.addEventListener('click', () => rematchPreviewMedia());
    const pick = document.createElement('button');
    pick.type = 'button';
    pick.className = 'btn btn-ghost btn-compact preview-error-pickmedia';
    pick.textContent = MSG.preview_pick_media;
    pick.style.display = 'none';   // 仅 err_kind=no_candidate（未找到媒体）时出现
    pick.addEventListener('click', () => pickPreviewMediaManually());
    slot.appendChild(ico);
    slot.appendChild(txt);
    slot.appendChild(rematch);
    slot.appendChild(pick);
    const page = document.getElementById('tab-guide');
    (page || document.body).appendChild(slot);
    return slot;
  }

  function clearPreviewError() {
    const slot = document.querySelector('.preview-error-slot');
    if (!slot) return;
    slot.classList.remove('show');
    const txt = slot.querySelector('.preview-error-text');
    if (txt) txt.textContent = '';
    const rematch = slot.querySelector('.preview-error-rematch');
    if (rematch) rematch.style.display = 'none';
    const pick = slot.querySelector('.preview-error-pickmedia');
    if (pick) pick.style.display = 'none';
  }

  // err_kind 结构化驱动（2.7.4 件2，评议员条件①）：前端按 error_key
  // 判定、禁靠中文文案匹配——仅 path_invalid（已有路径失效）时错误槽内
  // 出现「重新自动匹配」
  function showPreviewError(text, errKind) {
    // 停播保留（评议员条件）：错误即清 src，防上一次试听的声音持续播放
    detachPreviewSeekListeners();   // 同步拆 seek/停播监听（防幽灵暂停）
    const player = $('audioPreviewPlayer');
    if (player) { player.src = ''; }
    // 失败态=浮层条隐藏 + 独立错误槽红字（浮层不再承载错误展示）
    const bar = $('audioPreviewBar');
    if (bar) {
      bar.classList.remove('bar-loading', 'bar-ready');
      bar.style.display = 'none';
    }
    const slot = ensurePreviewErrorSlot();
    const txt = slot.querySelector('.preview-error-text');
    if (txt) txt.textContent = text;
    slot.classList.add('show');
    const rematch = slot.querySelector('.preview-error-rematch');
    if (rematch) rematch.style.display = errKind === 'path_invalid' ? '' : 'none';
    // F5 直通键：仅「未找到媒体」（结构化 err_kind=no_candidate）时出现
    const pick = slot.querySelector('.preview-error-pickmedia');
    if (pick) pick.style.display = errKind === 'no_candidate' ? '' : 'none';
  }

  // 「重新自动匹配」（2.7.4 件2）：复用后端推断引擎（refine_preview_infer_media
  // 与试听同源实现，零第二份）；成功后更新媒体条横幅并自动重试本次试听
  async function rematchPreviewMedia() {
    const slot = document.querySelector('.preview-error-slot');
    const btn = slot ? slot.querySelector('.preview-error-rematch') : null;
    if (btn) btn.disabled = true;
    try {
      if (!lastLoadedGuidePath || !window.pywebview
          || !window.pywebview.api
          || !window.pywebview.api.refine_preview_infer_media) {
        return;
      }
      const r = await window.pywebview.api.refine_preview_infer_media(
        lastLoadedGuidePath);
      if (r && r.ok && r.media_path) {
        inferredMediaCache[lastLoadedGuidePath] = String(r.media_path);
        renderMediaTag('tag-auto', MSG.preview_media_matched,
          String(r.media_path));
        mediaMissingHint(false);
        clearPreviewError();
        if (lastPreviewTiming) openAudioPreview(lastPreviewTiming);
      } else {
        showPreviewError(MSG.audio_preview_failed(
          (r && r.error) || MSG.unknownError), (r && r.error_key) || '');
      }
    } catch (e) {
      showPreviewError(MSG.audio_preview_failed(
        e && e.message ? e.message : String(e)), '');
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // 「选择媒体文件…」（F5 直通，D2026-1007-02）：试听「未找到媒体」
  // （err_kind=no_candidate）时错误槽内出现——文件对话框直选 → 持久化
  // 覆盖（refine_save_media_override，media_overrides KV，失败不阻塞会话
  // 内重试）→ 清该 guide 推断缓存（防直通后仍走旧推断）→ 自动重试上次
  // 试听（rematch 先例：lastPreviewTiming）。用户取消对话框 → 静默返回。
  async function pickPreviewMediaManually() {
    const slot = document.querySelector('.preview-error-slot');
    const btn = slot ? slot.querySelector('.preview-error-pickmedia') : null;
    if (btn) btn.disabled = true;
    try {
      if (!window.pywebview || !window.pywebview.api
          || !window.pywebview.api.refine_review_pick_media) {
        return;
      }
      const r = await window.pywebview.api.refine_review_pick_media();
      // 取消（cancelled）/桥失败 → 静默返回（保留原错误态）
      if (!r || !r.success || !r.path || !lastLoadedGuidePath) return;
      if (window.pywebview.api.refine_save_media_override) {
        try {
          await window.pywebview.api.refine_save_media_override(
            lastLoadedGuidePath, String(r.path));
        } catch (e) { /* 持久化失败不阻塞会话内重试 */ }
      }
      delete inferredMediaCache[lastLoadedGuidePath];
      renderMediaTag('tag-explicit', MSG.media_source_explicit, String(r.path));
      mediaMissingHint(false);
      clearPreviewError();
      if (lastPreviewTiming) openAudioPreview(lastPreviewTiming);
    } finally {
      if (btn) btn.disabled = false;
    }
  }

  // loading 提示行（浮层条内动态注入，幂等）：timing 右侧「正在匹配媒体
  // 路径并定位片段…」，ready 态隐藏、audio 才显示
  function ensurePreviewLoadingNote() {
    const main = document.querySelector('#audioPreviewBar .audio-preview-main');
    if (!main) return null;
    let note = main.querySelector('.preview-loading-note');
    if (!note) {
      note = document.createElement('span');
      note.className = 'preview-loading-note';
      note.textContent = MSG.preview_matching;
      const audio = main.querySelector('audio');
      if (audio) main.insertBefore(note, audio); else main.appendChild(note);
    }
    return note;
  }

  function closeAudioPreview() {
    detachPreviewSeekListeners();   // 拆 seek/停播监听（防幽灵暂停）
    const bar = $('audioPreviewBar');
    const player = $('audioPreviewPlayer');
    if (player) { player.pause(); player.src = ''; }
    if (bar) {
      bar.classList.remove('bar-loading', 'bar-ready');
      bar.style.display = 'none';
    }
    clearPreviewError();   // 同步清理错误槽（关浮层不留残红）
    lastPreviewToken++;   // 在途请求返回后作废
  }

  // 请求序号：连续点击/关闭后旧响应不得覆盖新状态
  let lastPreviewToken = 0;
  // 2.7.4 件2：最近一次试听 timing（重匹配成功后自动重试用）
  let lastPreviewTiming = '';

  // ============================================================
  // direct 分支定位与段内自动停播（质量报告导读试听定位修复）：
  // direct 整文件此前一律从 0:00 起播；改为 metadata 就绪后 seek 至
  // 片段起点前置 0.5s（与 clip 抽取 pad 对齐），自然播到片段终点后
  // 0.5s 自动暂停。程序化 seek / 用户拖拽区分（pendingSeek 标志）：
  // seeking 时为真视为程序化（seeked 落定后清标志并武装自动停播）；
  // 为假即用户拖拽，解除武装（不打断续听）。代数计数器防过期：
  // openAudioPreview 每次重入 / close / error 均拆除监听并递增代数，
  // 新增回调先校验代数、过期即返回，防快速切换条目/重匹配重试时旧
  // 回调落错时间点。
  // ============================================================
  let previewSeekGen = 0;         // 代数：每次拆装递增作废在途回调
  let previewPendingSeek = false; // seeking 时区分程序化/用户拖拽
  let previewArmStop = false;     // 武装后 timeupdate 才可自动停播
  let previewSeekHandlers = null; // 当前监听句柄（拆除/防重复挂载）

  // 拆除 direct 分支 seek/停播监听并复位标志（close/error/重入共用）
  function detachPreviewSeekListeners() {
    previewSeekGen++;   // 作废全部在途 seek/停播回调
    previewPendingSeek = false;
    previewArmStop = false;
    if (!previewSeekHandlers) return;
    const h = previewSeekHandlers;
    previewSeekHandlers = null;
    h.el.removeEventListener('loadedmetadata', h.loadedmetadata);
    h.el.removeEventListener('seeking', h.seeking);
    h.el.removeEventListener('seeked', h.seeked);
    h.el.removeEventListener('timeupdate', h.timeupdate);
  }

  // direct 分支 src 赋值后挂载（play() 时机不变：即播，seek 在
  // metadata 就绪后落点；坏文件不触发 loadedmetadata 时仅不定位，
  // 既有 error 路径与 no-src guard 不受影响）
  function attachPreviewSeekListeners(player, span) {
    const gen = previewSeekGen;   // 入口 detach 已递增，此后过期即弃
    const onLoadedMetadata = () => {
      if (gen !== previewSeekGen) return;
      previewPendingSeek = true;   // 程序化 seek：seeking 不解除武装
      player.currentTime = Math.max(0, span[0] - 0.5);
    };
    const onSeeking = () => {
      if (gen !== previewSeekGen) return;
      if (!previewPendingSeek) previewArmStop = false;   // 拖拽解除武装
    };
    const onSeeked = () => {
      if (gen !== previewSeekGen) return;
      if (!previewPendingSeek) return;
      previewPendingSeek = false;   // 程序化 seek 落定
      previewArmStop = true;        // 落定后才武装段内自动停播
    };
    const onTimeUpdate = () => {
      if (gen !== previewSeekGen || !previewArmStop) return;
      if (player.currentTime >= span[1] + 0.5) player.pause();
    };
    previewSeekHandlers = {
      el: player,
      loadedmetadata: onLoadedMetadata,
      seeking: onSeeking,
      seeked: onSeeked,
      timeupdate: onTimeUpdate
    };
    player.addEventListener('loadedmetadata', onLoadedMetadata,
      { once: true });
    player.addEventListener('seeking', onSeeking);
    player.addEventListener('seeked', onSeeked);
    player.addEventListener('timeupdate', onTimeUpdate);
  }

  async function openAudioPreview(timing) {
    const bar = $('audioPreviewBar');
    const player = $('audioPreviewPlayer');
    const timingEl = $('audioPreviewTiming');
    if (!bar || !player || !timingEl) return;
    detachPreviewSeekListeners();   // 重入拆旧监听+递增代数（防过期回调落错点）
    clearPreviewError();   // 每分支入口先清旧红字（防残留），再判断分支
    if (!lastLoadedGuidePath) {
      // no_guide：失败态（浮层不展开，错误槽红字页面级可见）
      showPreviewError(MSG.audio_preview_no_guide);
      return;
    }
    const span = timingToSeconds(timing);
    if (!span) {
      showPreviewError(MSG.audio_preview_no_timing);
      return;
    }
    ensurePreviewLoadingNote();
    // 两态浮层：点击即 loading（timing + 匹配中文案，播放器隐藏）；
    // 拿到可播放 src 才 ready 显示 audio
    timingEl.textContent = String(timing || '');
    player.src = '';
    bar.classList.remove('bar-ready');
    bar.classList.add('bar-loading');
    bar.style.display = '';
    lastPreviewTiming = String(timing || '');   // 重匹配自动重试依据
    const token = ++lastPreviewToken;
    try {
      const r = await window.pywebview.api.refine_audio_preview(
        lastLoadedGuidePath, span[0], span[1], mediaOverridePath);
      if (token !== lastPreviewToken) return;   // 过期回调不写 UI
      if (r && r.ok && r.mode === 'direct' && r.media_path) {
        bar.classList.remove('bar-loading');
        bar.classList.add('bar-ready');
        markInferredMedia(r);
        player.src = fileUrlOf(r.media_path);
        attachPreviewSeekListeners(player, span);   // 定位+段内自动停播
        player.play().catch(() => {});
      } else if (r && r.ok && r.mode === 'clip' && r.data_url) {
        bar.classList.remove('bar-loading');
        bar.classList.add('bar-ready');
        markInferredMedia(r);
        player.src = r.data_url;
        player.play().catch(() => {});
      } else {
        showPreviewError(MSG.audio_preview_failed(
          (r && r.error) || MSG.unknownError),
          (r && r.error_key) || '');
      }
    } catch (e) {
      if (token === lastPreviewToken) {
        showPreviewError(MSG.audio_preview_failed(
          e && e.message ? e.message : String(e)), '');
      }
    }
  }

  // 推断命中回显（2.7.4 件2）：media_source=inferred → 媒体条 tag-auto
  // 横幅显示匹配路径 + 写入每 guide 缓存（导读加载后缺失态即可展示）
  function markInferredMedia(r) {
    if (!r || r.media_source !== 'inferred' || !r.media_path) return;
    inferredMediaCache[lastLoadedGuidePath] = String(r.media_path);
    renderMediaTag('tag-auto', MSG.preview_media_matched,
      String(r.media_path));
    mediaMissingHint(false);
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

  // P2（D2026-1008-02）：分析/修复模型解析单源（后端共用 helper
  // _resolve_ai_model_config 的前端镜像，C6/C7/G5-补）。语义：
  // - 独立配置全有（provider+model）→ 生效（provider=所选，model=所填）；
  // - 仅 provider（半配置）→ 视为未配置忽略（notes 记说明），回落阶段A；
  // - follow / 独立模型空 → provider=null（跟随阶段A），model=阶段A 输入
  //   （后端再落阶段A 模型/服务商默认兜底，C9）。
  // 返回 {provider, model, effProvider, notes}：provider=null=跟随阶段A
  // （桥参语义同 refine_ai_analyze）；effProvider=实际生效 provider（云端
  // 警示/展示判定用）；notes=人话注记（预览/确认框拼入）。
  function analyzeResolution() {
    const indep = (($('aiProviderSel') || {}).value || 'follow');
    const indepModel = (($('aiModelInput') || {}).value || '').trim();
    const s1p = (($('refineS1Provider') || {}).value || '').toLowerCase();
    const s1m = (($('refineS1Model') || {}).value || '').trim();
    if (indep !== 'follow' && indepModel) {
      return { provider: indep, model: indepModel,
               effProvider: indep, notes: [] };
    }
    const notes = [];
    if (indep !== 'follow') notes.push(MSG.aiIndepHalfIgnored);
    return { provider: null, model: s1m, effProvider: s1p, notes: notes };
  }

  // 2.5.0 批5（D2026-1001-07）：AI 分析生效配置常驻显示（C1/C5：复用 refineAiPrivacy）
  // 批3（D2026-1008-01）：中文字面量收编 MSG 键（aiEffectiveLine 等）
  // P2（D2026-1008-02）：改走 analyzeResolution 单源（半配置如实显示
  // 回落+忽略说明，与实际发起的分析/修复解析一致）
  function aiRefreshEffective() {
    const el = $('refineAiPrivacy');
    if (!el) return;
    const res = analyzeResolution();
    const cloud = window.AI_CLOUD_PROVIDERS || [];
    const tag = res.provider ? MSG.aiEffIndependent : MSG.aiEffFollow;
    const note = (res.notes || []).join('；');
    el.style.display = '';
    el.textContent = MSG.aiEffectiveLine(tag, res.effProvider,
                                          res.model || MSG.aiModelUnset)
      + (note ? '｜' + note : '')
      + (cloud.includes(res.effProvider) ? MSG.aiCloudNote : '');
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
    // 修复B+2.5.0 批5（D2026-1001-07）：生效 provider/model 读数改单源
    // analyzeResolution（P2/D2026-1008-02：G5-补 半配置忽略+回落阶段A，
    // 弃「独立 provider×阶段A 模型」跨服务商拼装）；云 provider 发送前
    // 确认读实际生效值（C1/C7）
    const res = analyzeResolution();
    if (AI_CLOUD_PROVIDERS.includes(res.effProvider)) {
      const go = await AppModal.confirm(MSG.aiCloudConfirm(res.effProvider));
      if (!go) return;
    }
    const btn = $('refineAiAnalyzeBtn');
    if (btn) btn.disabled = true;
    // 批4（D2026-1008-01）：分析中旁挂「停止分析」（class 锚零 id，
    // 文案 JS 态 MSG；点击置 pending 态并发取消桥，最终结果由主调用
    // 回包收口——回包 cancelled=True 时状态行显 C12 文案）
    const stopBtn = document.querySelector('.ai-analyze-stop-btn');
    if (stopBtn) {
      stopBtn.textContent = MSG.aiStopBtn;
      if (!stopBtn.dataset.stopBound) {
        stopBtn.dataset.stopBound = '1';
        stopBtn.addEventListener('click', () => {
          if (!window.pywebview || !window.pywebview.api) return;
          stopBtn.disabled = true;
          aiStatus(MSG.aiStopPending);
          Promise.resolve(window.pywebview.api.refine_cancel_ai_analyze())
            .catch(() => {})
            .finally(() => { stopBtn.disabled = false; });
        });
      }
      stopBtn.style.display = '';
    }
    aiStatus(MSG.aiAnalyzing);
    try {
      const r = await window.pywebview.api.refine_ai_analyze(
        rp, res.model, res.provider);
      if (r && r.success) {
        lastAiSuggestions = r;
        aiSetPrivacy(r.provider_name);
        aiRenderResult(r);
        aiStatus(MSG.aiDone + (r.crosscheck_segments
          ? MSG.asrCrosscheckNote(r.crosscheck_segments) : ''));
      } else if (r && r.cancelled) {
        aiStatus(MSG.aiCancelled);
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
      // 批4：停止按钮隐藏复位——取消/完成后均可重新发起
      if (stopBtn) stopBtn.style.display = 'none';
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

  // 2.7.4 件C（D2026-1007-02）：修复生效配置常驻明示行（对齐
  // aiRefreshEffective 先例）：生效 provider/model 由后端
  // refine_preview_fix_config 统一解析，拒绝时明示行红色直显原因；
  // 未加载导读时隐藏。P2（D2026-1008-02）：入参=analyzeResolution()
  // 产物（预览与修复执行同源 by construction，C7）；notes（半配置
  // 忽略说明）前端直拼；返回桥结果（供 batchFixRun 确认框副行复用），
  // 桥异常回 null。
  function bfRefreshEffective() {
    const el = $('batchFixEffectiveLine');
    if (!el) return Promise.resolve(null);
    if (!lastLoadedGuidePath || lastLoadedIsTxt) {
      el.style.display = 'none';
      return Promise.resolve(null);
    }
    if (!window.pywebview || !window.pywebview.api) {
      return Promise.resolve(null);
    }
    const res = analyzeResolution();
    const note = (res.notes || []).join('；');
    return window.pywebview.api.refine_preview_fix_config(
        res.provider, res.model)
      .then((r) => {
        if (!r) return null;
        el.style.display = '';
        if (r.ok) {
          el.classList.remove('status-err');
          // 生效源人话标识（分析模型/跟随阶段A）由后端 source_label
          // 直出，前端零解析直拼（拒绝分支仍走 reason）
          el.textContent = MSG.batchFixUsing(
            r.provider || MSG.batchFixModelUnset,
            r.model || MSG.batchFixModelUnset)
            + (r.source_label ? MSG.batchFixSourceTag(r.source_label) : '')
            + (note ? '｜' + note : '');
        } else {
          el.classList.add('status-err');
          el.textContent = (note ? note + '；' : '')
            + (r.reason || MSG.batchFixModelUnset);
        }
        return r;
      })
      .catch(() => null);
  }

  function batchFixRefresh() {
    // 使能钩子：导读 json 加载成功后拉取行动条目（含台账已修标记）
    const btn = $('refineBatchFixBtn');
    const scope = $('refineBatchFixScope');
    if (!btn || !window.pywebview || !window.pywebview.api) return;
    // 2.7.4 件C（D2026-1007-02）：明示行随刷新链同步（载入导读/修复结束共用）
    bfRefreshEffective();
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
    // P2（D2026-1008-02）：云端警示/服务商展示按生效分析 provider 判定
    // （C7——修复与分析已完全同一模型源，弃阶段B 服务商旧口径）
    const fixRes = analyzeResolution();
    const cloud = isAiCloudProvider(fixRes.effProvider);
    const provLabel = fixRes.effProvider
      ? (MSG['ai_prov_' + fixRes.effProvider] || fixRes.effProvider)
      : MSG.batchFixModelUnset;
    const catCount = {};
    batch.forEach(it => {
      catCount[it.category] = (catCount[it.category] || 0) + 1;
    });
    // 分类明细按数量降序（设计取舍：主要问题类前置，原字母序弱化主次
    // ——2.7.4 件3 D2026-1007-01）
    const cats = Object.keys(catCount)
      .sort((a, b) => catCount[b] - catCount[a])
      .map(c => ({ cat: c, count: catCount[c] }));
    // 现译全文取自已加载导读（lastGuideData 经 read_output_artifact 持有；
    // 后端 action_items 摘录限长仅约束回包形状）——Number 强转匹配，
    // index 非 int 的条目查无全文自动回退摘录并带标记（弹窗内处理）
    const textMap = {};
    ((lastGuideData && lastGuideData.items) || []).forEach((g) => {
      if (!g || g.current_text == null) return;
      const k = Number(g.index);
      if (Number.isFinite(k)) textMap[k] = String(g.current_text);
    });
    // 2.7.4 件C（D2026-1007-02）：打开确认框前刷新明示行并取生效配置
    // （与修复子进程同一解析结果；拒绝时确认框 warn 行直显原因）
    const fixCfg = await bfRefreshEffective();
    const fixCfgMeta = !fixCfg
      ? null
      : (fixCfg.ok
          ? { text: MSG.batchFixUsing(
                fixCfg.provider || MSG.batchFixModelUnset,
                fixCfg.model || MSG.batchFixModelUnset) }
          : { text: fixCfg.reason || MSG.batchFixModelUnset, warn: true });
    const go = await AppModal.batchFixPreview({
      title: MSG.batchFixConfirmTitle,
      okText: MSG.batchFixConfirmOk,
      meta: [
        { text: MSG.batchFixEstimate(batch.length) },
        { text: MSG.batchFixProvider(provLabel) },
        fixCfgMeta,
        cloud ? { text: MSG.batchFixCloudCost, warn: true } : null,
        capNote ? { text: capNote, warn: true } : null,
      ].filter(Boolean),
      cats: cats,
      head: MSG.batchFixPreviewHead,
      items: batch,
      texts: textMap,
    });
    if (!go) return;
    const btn = $('refineBatchFixBtn');
    if (btn) btn.disabled = true;
    // 批4（D2026-1008-01）：修复中旁挂「停止修复」（class 锚零 id；后端
    // cancelled 分支保证取消后不再自动复跑 AI 分析）；轮询让位 pending 态
    const stopBtn = document.querySelector('.batch-fix-stop-btn');
    let stopRequested = false;
    if (stopBtn) {
      stopBtn.textContent = MSG.bfStopBtn;
      if (!stopBtn.dataset.stopBound) {
        stopBtn.dataset.stopBound = '1';
        stopBtn.addEventListener('click', () => {
          if (!window.pywebview || !window.pywebview.api) return;
          stopRequested = true;
          stopBtn.disabled = true;
          bfStatus(MSG.bfStopPending);
          Promise.resolve(window.pywebview.api.refine_cancel_batch_fix())
            .catch(() => {})
            .finally(() => { stopBtn.disabled = false; });
        });
      }
      stopBtn.style.display = '';
    }
    bfStatus(MSG.batchFixRunning(0, batch.length));
    const poll = setInterval(async () => {
      try {
        const p = await window.pywebview.api.refine_batch_fix_progress();
        if (p && p.running && p.phase === 'verify') {
          if (!stopRequested) bfStatus(MSG.batchFixVerifying);
        } else if (p && p.running && !stopRequested) {
          // 执行器无逐条进度输出契约——done=0 时用中性文案（评审修订）
          bfStatus(p.done > 0
            ? MSG.batchFixRunning(p.done, p.total)
            : MSG.batchFixRunningPlain);
        }
      } catch (e) { /* 单次轮询失败静默，主调用最终回显为准 */ }
    }, 1000);
    try {
      // 修复执行/复验与确认框同一解析源（P2/D2026-1008-02：单源
      // analyzeResolution，后端共用 helper 同参语义）
      const runRes = analyzeResolution();
      const r = await window.pywebview.api.refine_batch_fix(
        lastLoadedGuidePath, batch.map(it => it.index),
        runRes.provider, runRes.model);
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
      } else if (r && r.cancelled) {
        bfStatus(MSG.bfCancelled);
      } else {
        bfStatus(MSG.batchFixFail + '：' + ((r && r.error) || ''));
      }
    } catch (e) {
      bfStatus(MSG.batchFixFail + '：'
        + (e && e.message ? e.message : String(e)));
    } finally {
      clearInterval(poll);
      if (btn) btn.disabled = false;
      // 批4：停止按钮隐藏复位——取消/完成后均可重新发起
      if (stopBtn) stopBtn.style.display = 'none';
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
        r.model_present ? (r.saved_model || MSG.asrModelUnselected)
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
      if (saved && models.some(m => m.name === saved)) {
        sel.value = saved;
      } else {
        // 2.7.3 件③：saved 空或不在本机清单时，确保占位 option（JS 渲染）
        // 并显式归零选中——否则浏览器默认选中第一项=假选中（后端 CLI 不带
        // --asr-model 缺省 large-v2 是合法降级，UI 不得替用户显示已选）
        if (!sel.querySelector('option[value=""]')) {
          const ph = document.createElement('option');
          ph.value = '';
          ph.textContent = MSG.asrModelPlaceholder;
          sel.appendChild(ph);
        }
        sel.value = '';
      }
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
        // 2.7.4 件1 收敛：错误回显唯一走 #guideStatus 状态行
        // （guideCustomStatus 已收敛为来源 chip，不承载错误文案）
        guideStatus(MSG.api_not_ready, true);
        return;
      }
      try {
        const r = await window.pywebview.api.refine_pick_guide_json();
        if (r && r.success && r.path) {
          guideLoad(false, r.path);
        } else if (!r || !r.cancelled) {
          // 用户取消（cancelled）静默返回；其余错误（如无活动窗口）显示在状态行，不弹窗
          guideStatus(
            MSG.guide_load_failed((r && r.error) || MSG.unknownError), true);
        }
      } catch (e) {
        guideStatus(MSG.guide_load_failed(
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
    // 批3（D2026-1008-01）：分析模型三件套接线（文案/图标 JS 态填充，
    // 绑 DOM 即填不依赖设置回填路径；follow 缺省态单源应用）
    const aiRow = document.querySelector('.ai-config-row');
    if (aiRow) {
      const aiRefreshBtn = aiRow.querySelector('.ai-model-refresh');
      const aiTestBtn = aiRow.querySelector('.ai-model-test');
      if (aiRefreshBtn) {
        aiRefreshBtn.title = MSG.refresh_model_title;
        aiRefreshBtn.innerHTML = MODEL_REFRESH_SVG;
        aiRefreshBtn.addEventListener('click', () => refreshAnalysisModels());
      }
      if (aiTestBtn) {
        aiTestBtn.title = MSG.test_stage_title;
        aiTestBtn.textContent = MSG.test_stage_btn;
        aiTestBtn.addEventListener('click', () => testAnalysisModel());
      }
      aiModelApplyFollowState();
      const aiProvBind = $('aiProviderSel');
      if (aiProvBind && !aiProvBind.dataset.trioBound) {
        aiProvBind.dataset.trioBound = '1';
        aiProvBind.addEventListener('change', () => aiModelApplyFollowState());
      }
    }
    // P2（D2026-1008-02）：修复模型独立配置行接线随删行退役——修复生效
    // 模型唯一来源=分析独立配置（analyzeResolution 单源），旧 batch_fix_*
    // KV 不再读写
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
      // 2.7.3 件③（评议员条件⑥）：占位空值不保存、不覆盖既有 saved_model
      // （占位项恰为当前选中时用户点选=空操作）
      if (asrSel.value === '') return;
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
    // C4（D2026-1007-02）：direct 播放失败可见化——audio error 监听入独立
    // 错误槽（no-src guard 照抄 review.js：showPreviewError/closeAudioPreview
    // 清 src 触发的无源 error 忽略，防幽灵红字闪回）
    const pvPlayer = $('audioPreviewPlayer');
    if (pvPlayer) pvPlayer.addEventListener('error', () => {
      if (!pvPlayer.getAttribute('src')) return;
      console.error('[guide] audio preview error:',
        (pvPlayer.error && pvPlayer.error.code) || 'unknown');
      showPreviewError(MSG.audio_preview_play_error, '');
    });
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
      // 2.7.4 件2：override 变更 → 推断缓存失效；显式路径持久化写入
      // （media_overrides KV，空串=删除该条；失败静默——会话内覆盖已生效）
      delete inferredMediaCache[lastLoadedGuidePath];
      if (lastLoadedGuidePath && window.pywebview
          && window.pywebview.api
          && window.pywebview.api.refine_save_media_override) {
        try {
          window.pywebview.api.refine_save_media_override(
            lastLoadedGuidePath, mediaOverridePath).catch(() => {});
        } catch (e) { /* 桥缺席静默（会话内覆盖已生效） */ }
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
  // 2.7.3 件⑤（词典下载停止按钮）：停止中过渡态标记 + 请求时刻（过渡
  // 兜底量纲用）。停止过渡期 _dictBusyKind 保持占用直到终态（防提前
  // 解锁邀请重下——与后端 HRO-1.3「不乐观写 stopped 快照」对齐）
  let _dictStopPending = false;
  let _dictStopRequestedAt = 0;
  // 过渡兜底显式常数（评议员条件③）：单分块 socket 超时 10s（后端
  // opener.open timeout=10，停止信号最迟等当前 1MB 分块读返回才到检查
  // 点）+ 2 拍轮询间隔（实测轮询 1000ms/拍）；超时未见终态→本地按失败
  // 收口（后端线程终会写 stopped 快照，后续状态查询自纠）
  const DICT_STOP_GRACE_MS = 10000 + 2000;
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
      // 2.7.3 件⑤ 四态分派：下载中=主按钮已转停止键（调停止端点），
      // 空闲=发起下载。回调读当前 sel.value 保证通用性
      if (!btn.dataset.bound) {
        btn.dataset.bound = '1';
        btn.addEventListener('click', () => {
          if (_dictBusyKind) {
            dictRequestStop($('dictSelect').value, btn);
          } else {
            dictDownload($('dictSelect').value, btn);
          }
        });
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
    _dictStopPending = false;         // 件⑤：新会话复位停止过渡态
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
    // 2.7.3 件⑤：终态收口（done/failed/stopped/互斥拒绝/兜底超时共用）——
    // 原同步 await 的 finally 解锁链整体前移至此，终态改由轮询驱动
    // （会话制下 refine_dict_download 立即返回，不再以该 await 为终态）；
    // finished 单次闸防轮询多拍并发重复收口
    let finished = false;
    const finish = (statusText, isErr, diag) => {
      if (finished) return;
      finished = true;
      stopPoll();                       // 防重复 poller 泄漏
      showProgress(false);              // 隐藏统一放收口（覆盖成功/失败/停止三路径）
      _dictBusyKind = null;             // 先清占位再 dictLoad()：重渲染据此解除整行禁用
      _dictStopPending = false;
      if (actionRow) actionRow.classList.remove('is-busy');
      srcBtns.forEach((b) => { if (b) b.disabled = false; });
      const sel = $('dictSelect');
      if (!sel || sel.value === kind) {
        // 终态与当前选中词典一致才直改按钮（className 同步复位：下载中
        // 挂过 btn-danger 停止态）；不一致交由 dictLoad()→dictRenderDetail()
        // 重刷详情区对齐（重渲染不触碰静态进度条）
        if (btn) {
          btn.disabled = false;
          const finInfo = _dictStatusCache[kind] || {};
          btn.className = finInfo.available ? 'btn btn-ghost btn-compact'
            : 'btn btn-primary btn-compact';
          btn.textContent = doneLabel;
        }
      }
      if (st) dictShowStatus(st, statusText, isErr, diag);
      dictLoad();
    };
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
        // 过渡兜底（2.7.3 件⑤ 评议员条件③）：停止请求后超时未见终态→
        // 本地按失败收口（后端线程终会写 stopped，后续状态查询自纠）
        if (_dictStopPending &&
            Date.now() - _dictStopRequestedAt > DICT_STOP_GRACE_MS) {
          finish(MSG.dict_stop_note, true, null);
          return;
        }
        if (!owned) return;
        // 2.7.3 件⑤ 四态状态机：download/verify/extract=下载中可停止
        // （主按钮转 btn-danger「停止」，复用既有 .btn-danger 样式与
        // MSG.stop_btn 键）；done/failed/stopped=终态收口
        if (p.phase === 'download' || p.phase === 'verify' ||
            p.phase === 'extract') {
          if (btn && _dictStopPending) {
            // 停止中过渡：按钮禁用防连点，_dictBusyKind 保持占用直到终态
            btn.disabled = true;
            btn.textContent = MSG.dict_stop_pending;
          } else if (btn) {
            btn.disabled = false;               // 停止键须可点
            btn.className = 'btn btn-danger btn-compact';
            btn.textContent = MSG.stop_btn;
          }
          if (st && _dictStopPending) st.textContent = MSG.dict_stopping;
          return;
        }
        if (p.phase === 'stopped') {
          // 已停止：回未安装态，状态行人话指引（finish 解锁链覆盖 stopped
          // ——dictLoad() 重渲染后源 pill/整行立即解锁）
          finish(MSG.dict_stop_note, false, null);
        } else if (p.phase === 'done') {
          // 终态大小以 done 快照链路的 lastBytes 为准（会话制下无同步
          // 返回 path，改为字节数口径）
          finish(`${MSG.dict_download_done}（${fmtMB(lastBytes)}MB）`,
            false, null);
        } else if (p.phase === 'failed') {
          finish(dictFailureText(`${p.error || ''}`, p.diag), true, p.diag);
        }
      } catch (e) { /* 进度轮询失败不干扰主流程 */ }
    }, 1000);
    try {
      // 2.7.3 件⑤ 会话制：refine_dict_download 立即返回 session_id，
      // 下载在后端线程执行，终态（done/failed/stopped）由上方轮询驱动；
      // 本 await 仅处理「启动失败」（kind 校验/同 kind 互斥拒绝等）
      const r = await pywebview.api.refine_dict_download(kind, source || 'auto');
      if (r && r.success) {
        // 已启动：读取一次当前快照校准计数（后端可能已推进）
        try {
          const f = await pywebview.api.refine_dict_download_progress(kind);
          if (f && f.success && typeof f.downloaded === 'number' &&
              f.downloaded > 0) lastBytes = f.downloaded;
        } catch (e) { /* ignore */ }
        return;
      }
      // 启动失败（含 dict_download_busy 互斥拒绝）：立即按失败收口
      finish((r && (r.message || r.error)) || MSG.dict_download_failed,
        true, null);
    } catch (e) {
      // 异常路径=未知错误：一行人话沿用原文（红），无诊断网格
      finish(dictFailureText(String(e), null), true, null);
    }
  }
  // 2.7.3 件⑤：停止请求（下载中主按钮=停止键）。本地立即进入停止中
  // 过渡（按钮禁用防连点 + 状态行「停止中…」），后端经 stop 端点置位
  // Event，下载线程在检查点收口写 stopped 快照（后端绝不乐观代写）；
  // 超时未见终态由轮询兜底（DICT_STOP_GRACE_MS）本地按失败收口
  async function dictRequestStop(kind, btn) {
    if (_dictStopPending) return;       // 防连点（按钮禁用是第一道）
    // 跨 kind 守卫（code-review 触碰式修复②，与 _dictBusyKind 跨 kind
    // 并发洞收口同口径）：A 下载中把下拉切到 B 再点停止——kind 参数读自
    // 当前 sel.value，不校验会对 B 调 stop 端点（后端幂等 False 无害，
    // 但 UI 误入停止中过渡、绕过 _dictBusyKind 跨 kind 互斥占位）。只认
    // _dictBusyKind 本尊：当前选中 kind ≠ 下载中 kind 一律忽略
    if (_dictBusyKind !== kind) return;
    _dictStopPending = true;
    _dictStopRequestedAt = Date.now();
    const st = $('dictStatus');
    if (btn) { btn.disabled = true; btn.textContent = MSG.dict_stop_pending; }
    if (st) dictShowStatus(st, MSG.dict_stopping, false, null);
    try {
      await pywebview.api.refine_dict_download_stop(kind);
    } catch (e) { /* 停止请求失败不本地解锁——轮询/兜底收口 */ }
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
    const model = ((document.getElementById('refineS1Model') || {}).value || '').trim() || '—';
    const conc = ((document.getElementById('refineConcurrency') || {}).value || '').trim() || '1';
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

    // 硬字幕压制底条/入口接线（2.8.0 批1 件5）；若有在途队列（热刷新场景）
    // 由 refresh 轮询自然恢复显示
    EncodeDock.init();

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

// ============================================================
// 硬字幕压制队列底条（2.8.0 批1 件5，D2026-1007-03）：全局串行队列 UI。
// - 常驻骨架（#encodeDock）由 show() 显现；只在用户点关闭（×）时隐藏，
//   不随队列空闲自动消失（DoD：完成后「打开文件夹」与失败「重试」须可达）；
// - 轮询 1s：encode_status() + ffmpeg_supply_progress()（下载行复用同面板）；
// - 列表行 createElement 注入（零 id）；外部文本全部 textContent 承载
//   （不经 innerHTML，esc() 语义无涉）；禁 line-clamp（2.7.4 教训）；
// - 行内动作按态：running/queued=取消、failed/cancelled=重试、done=打开文件夹。
// ============================================================
const EncodeDock = {
    _poll: null,
    _expanded: false,
    _lastParams: null,
    _doneLogged: false,

    _api() {
        return (window.pywebview && window.pywebview.api) || null;
    },

    init() {
        const self = this;
        document.querySelectorAll('.encode-entry-btn').forEach((btn) => {
            btn.textContent = btn.dataset.testid === 'encode-entry-guide'
                ? MSG.encodeEntryGuide : MSG.encodeEntryReview;
            btn.addEventListener('click', () => self.openModal());
        });
        // 自动压制开关（批3：管线设置 encode_auto_enabled；缺省关）
        const autoRow = document.querySelector('.encode-auto-row');
        if (autoRow) {
            const box = autoRow.querySelector('.encode-auto-switch');
            const label = autoRow.querySelector('.encode-auto-label');
            label.textContent = MSG.encodeAutoSwitch;
            box.addEventListener('change', async () => {
                const api2 = self._api();
                if (!api2) return;
                try {
                    await api2.refine_save_stage_settings(null, null,
                        { encode_auto_enabled: box.checked }, null);
                } catch (e) { /* 下次切换自愈 */ }
            });
            // 启动回填（桥就绪后异步读设置；失败保持缺省关）
            (async () => {
                const api2 = self._api();
                if (!api2) return;
                try {
                    const r = await api2.refine_get_stage_settings();
                    if (r && r.success && r.settings) {
                        box.checked = !!r.settings.encode_auto_enabled;
                    }
                } catch (e) { /* 保持缺省关 */ }
            })();
        }
        // 压制参数独立设置项（D2026-1008-01 批2）：高级参数页「压制」组
        // （标题/简述 JS 态填充）+「打开压制参数」按钮+右栏自动压制行
        // 「参数」——两入口同开编辑模式弹窗（无选中文件也可用）；摘要行
        // JS 态渲染（保存成功后随 onSaved 刷新）
        const advTitle = document.querySelector('.encode-adv-title');
        if (advTitle) advTitle.textContent = MSG.encodeAdvGroupTitle;
        const advDesc = document.querySelector('.encode-adv-desc');
        if (advDesc) advDesc.textContent = MSG.encodeAdvGroupDesc;
        document.querySelectorAll('.encode-params-open-btn').forEach((btn) => {
            btn.textContent = MSG.encodeAdvOpenBtn;
            btn.addEventListener('click', () => self.openModal({ editOnly: true }));
        });
        const paramsLink = document.querySelector('.encode-params-link');
        if (paramsLink) {
            paramsLink.textContent = MSG.encodeParamsLink;
            paramsLink.addEventListener('click', (e) => {
                e.preventDefault();
                self.openModal({ editOnly: true });
            });
        }
        self.renderParamsSummary();
        const dock = document.getElementById('encodeDock');
        if (!dock) return;
        dock.querySelector('.queue-dock-dismiss').textContent = MSG.encodeDismiss;
        dock.querySelector('.queue-dock-dismiss').addEventListener('click', () => self.hide());
        const toggle = document.getElementById('encodeDockToggle');
        toggle.textContent = MSG.encodeExpand;
        toggle.addEventListener('click', () => self.togglePanel());
        dock.querySelector('.queue-dock-cancel').textContent = MSG.encodeCancelJob;
        dock.querySelector('.queue-dock-cancel').addEventListener('click', () => self.cancelAll());
    },

    async openModal(opts) {
        const api = this._api();
        if (!api) return;
        // 参数编辑模式（D2026-1008-01 批2）：压制参数独立设置项——无选中
        // 文件也可打开，读上次参数进弹窗编辑；保存走 encode_save_params 桥
        // （弹窗内「保存参数」按钮），此处绝不触碰 preflight/commit/jobs。
        // GPU 可用性无独立探测桥（仅 preflight 顺带双检懒缓存），编辑模式
        // 传 gpu:null → GPU 选项置灰、弹窗 title 显因「发起压制后可检测」
        if (opts && opts.editOnly) {
            let lp = null;
            try { lp = await api.encode_get_last_params(); } catch (e) { lp = null; }
            const last = (lp && lp.success && lp.params) || this._lastParams || {};
            await AppModal.encode({
                editOnly: true,
                jobs: [],
                last,
                presets: null,
                gpu: null,
                onSaved: (params) => {
                    this._lastParams = params;
                    this.renderParamsSummary();
                },
            });
            return;
        }
        const jobs = (AppState.selectedFiles || []).map((p) => ({ srt_path: p }));
        if (jobs.length === 0) {
            AppModal.alert(MSG.encodeModalTitle, MSG.encodeNoJobs);
            return;
        }
        let pre = null;
        try {
            if (!this._lastParams) {
                const lp = await api.encode_get_last_params();
                if (lp && lp.success) this._lastParams = lp.params || {};
            }
            pre = await api.encode_preflight(jobs, this._lastParams || {});
        } catch (e) {
            AppModal.alert(MSG.encodeModalTitle, String(e));
            return;
        }
        if (!pre || pre.success === false) {
            AppModal.alert(MSG.encodeModalTitle, (pre && pre.error) || String(pre));
            return;
        }
        // 供给缺口 → 引导一次完整版下载（HRO-1：能力探测是主路径保障）
        if (pre.supply_missing && pre.supply_missing.length > 0) {
            const ok = await AppModal.confirm(MSG.encodeModalTitle, MSG.encodeSupplyMissing);
            if (ok) {
                try {
                    await api.ffmpeg_supply_download();
                } catch (e) { /* 单飞守卫拒绝视为已在下载 */ }
                this.show();
            }
            return;
        }
        // 有效任务过滤（缺视频/缺终稿字幕的项不入队，明细在 preflight items）
        const valid = [];
        let noVideo = 0;
        let noSub = 0;
        (pre.items || []).forEach((it) => {
            if (!it.video_exists) { noVideo += 1; return; }
            if (!it.subtitle_exists) { noSub += 1; return; }
            valid.push(it);
        });
        if (valid.length === 0) {
            const why = noVideo > 0 ? MSG.encodeNoVideo : MSG.encodeNoSubtitle;
            AppModal.alert(MSG.encodeModalTitle, why + '（' + (pre.items || []).length + ' 个文件）');
            return;
        }
        let presets = null;
        try { presets = await api.encode_presets_list(); } catch (e) { presets = null; }
        const res = await AppModal.encode({
            jobs: valid,
            totalEtaS: pre.total_eta_s,
            last: this._lastParams || {},
            presets,
            gpu: pre.gpu,
        });
        if (!res || !res.ok) return;
        this._lastParams = res.params;
        try { api.encode_save_last_params(res.params); } catch (e) { /* 持久化失败不阻塞 */ }
        await this.commit(valid, res.params, false);
    },

    // 高级参数页摘要行（D2026-1008-01 批2）：读 encode_get_last_params
    // 渲染「格式 · 画质 · 音量 · 保存时间」一行简报（JS 态 MSG 函数键拼装；
    // 缺已保存参数时空态文案）。弹窗编辑模式保存成功后经 onSaved 重渲染。
    async renderParamsSummary() {
        const row = document.querySelector('.encode-params-summary');
        if (!row) return;
        let p = this._lastParams;
        if (!p || !Object.keys(p).length) {
            const api = this._api();
            if (api) {
                try {
                    const lp = await api.encode_get_last_params();
                    if (lp && lp.success) { p = lp.params || {}; this._lastParams = p; }
                } catch (e) { /* 渲染降级：保留空态文案 */ }
            }
        }
        p = p || {};
        if (!p.video_format && !p.quality && !p.saved_at) {
            row.textContent = MSG.encodeSummaryEmpty;
            return;
        }
        const parts = [];
        const fmt = { h264: 'H.264', h265: 'H.265', av1: 'AV1' }[p.video_format];
        if (fmt) parts.push(fmt);
        const q = { compress: MSG.encodeQCompress, balanced: MSG.encodeQBalanced,
                    quality: MSG.encodeQQuality }[p.quality];
        if (q) parts.push(String(q).split('（')[0]);
        const db = typeof p.volume_db === 'number' ? p.volume_db : 0;
        parts.push(MSG.encodeSummaryVol((db > 0 ? '+' : '') + db));
        if (p.saved_at) parts.push(MSG.encodeSummaryAt(p.saved_at));
        row.textContent = MSG.encodeSummaryLine(parts);
    },

    async commit(jobs, params, allowOverwrite) {
        const api = this._api();
        let commit = null;
        try {
            commit = await api.encode_commit(jobs, params, allowOverwrite === true);
        } catch (e) {
            AppModal.alert(MSG.encodeModalTitle, String(e));
            return;
        }
        if (commit && commit.needs_confirm) {
            const list = (commit.existing || []).map((p) => '· ' + p).join('\n');
            const ok = await AppModal.confirm(
                MSG.encodeOverwriteTitle,
                MSG.encodeOverwriteBody.replace('{list}', list));
            if (ok) await this.commit(jobs, params, true);
            return;
        }
        if (!commit || commit.success === false) {
            const err = (commit && commit.error) || String(commit);
            AppModal.alert(MSG.encodeModalTitle,
                MSG.encodeCommitRejected.replace('{e}', err));
            return;
        }
        if (commit.rejected && commit.rejected.length > 0) {
            const first = commit.rejected[0] || {};
            AppModal.alert(MSG.encodeModalTitle, String(first.reason || ''));
        }
        this.show();
        this.refresh();
    },

    show() {
        const dock = document.getElementById('encodeDock');
        if (dock) dock.style.display = '';
        this.startPolling();
    },

    hide() {
        const dock = document.getElementById('encodeDock');
        if (dock) dock.style.display = 'none';
        this.stopPolling();
    },

    togglePanel() {
        this._expanded = !this._expanded;
        const panel = document.getElementById('encodeDockList');
        const toggle = document.getElementById('encodeDockToggle');
        if (panel) panel.style.display = this._expanded ? '' : 'none';
        if (toggle) toggle.textContent = this._expanded ? MSG.encodeCollapse : MSG.encodeExpand;
    },

    startPolling() {
        if (this._poll) return;
        this.refresh();
        this._poll = setInterval(() => this.refresh(), 1000);
    },

    stopPolling() {
        if (this._poll) {
            clearInterval(this._poll);
            this._poll = null;
        }
    },

    async refresh() {
        const api = this._api();
        if (!api) return;
        let st = null;
        let sup = null;
        try {
            st = await api.encode_status();
            sup = await api.ffmpeg_supply_progress();
        } catch (e) {
            return;   // 桥未就绪/瞬时失败：下轮自愈
        }
        if (!st || st.success === false) return;
        const jobs = st.jobs || [];
        const supplyActive = sup && sup.success !== false
            && (sup.busy || sup.phase === 'downloading');
        // 交付闭环（批3）：全部完成的瞬间 Console 活动流一行人话（完成不打断
        // ——不弹窗不抢焦点，四处硬性规定之批3 落点）；每次排空只报一次
        const anyActive = jobs.some((j) => j.state === 'running' || j.state === 'queued');
        if (jobs.length > 0 && !anyActive && !this._doneLogged) {
            this._doneLogged = true;
            try {
                ConsoleManager.log(MSG.encodeAutoDoneLine, 'success');
            } catch (e) { /* console 通道缺席不阻塞 */ }
        }
        if (anyActive) this._doneLogged = false;
        if (jobs.length === 0 && !supplyActive) return;   // 未显过底条则保持隐藏
        this.show();
        this.render(jobs, sup);
    },

    _stateText(state) {
        return MSG['encodeSt' + String(state || '').charAt(0).toUpperCase()
            + String(state || '').slice(1)] || state;
    },

    render(jobs, sup) {
        const dock = document.getElementById('encodeDock');
        if (!dock) return;
        const dot = dock.querySelector('.queue-dock-state');
        const label = document.getElementById('encodeDockLabel');
        const fill = document.getElementById('encodeDockFill');
        const eta = dock.querySelector('.queue-dock-eta');
        const cancelBtn = dock.querySelector('.queue-dock-cancel');
        const running = jobs.find((j) => j.state === 'running');

        // 供给下载行优先（压制未启动时占住底条）
        if (sup && (sup.busy || (sup.phase && sup.phase !== 'idle' && sup.phase !== 'done'))) {
            const pct = (sup.total > 0)
                ? Math.min(99, Math.round((sup.received / sup.total) * 100)) : 0;
            dot.className = 'queue-dock-state running';
            label.textContent = MSG.encodeDownloadDock
                + ' ' + ((sup.received / (1024 * 1024)) || 0).toFixed(0) + 'MB';
            fill.style.width = pct + '%';
            fill.classList.remove('err');
            eta.textContent = pct + '%';
            cancelBtn.style.display = '';
            cancelBtn.textContent = MSG.encodeStop;
        } else if (running) {
            dot.className = 'queue-dock-state running';
            label.textContent = MSG.encodeDockRunning + ' ' + this._baseName(running.out_path)
                + ' · ' + String(running.params && running.params.video_format || '').toUpperCase()
                + ' ' + this._stateText(running.state);
            fill.style.width = (running.progress || 0) + '%';
            fill.classList.remove('err');
            eta.textContent = (running.progress || 0) + '%'
                + (running.eta_s > 0
                    ? ' · ETA ' + MSG.encodeMinutes.replace('{m}', Math.max(1, Math.round(running.eta_s / 60)))
                    : '');
            cancelBtn.style.display = '';
            cancelBtn.textContent = MSG.encodeCancelJob;
        } else {
            // 空闲态标签/圆点跟随最新任务（黑盒修正：历史含取消/失败项时
            // 不得永久卡「压制失败」——history 只增，以末条为准）
            const latest = jobs.length ? jobs[jobs.length - 1] : null;
            const bad = !!(latest
                && (latest.state === 'failed' || latest.state === 'cancelled'));
            dot.className = 'queue-dock-state' + (bad ? ' failed' : '');
            label.textContent = !latest ? MSG.encodeDockIdle
                : (latest.state === 'failed' ? MSG.encodeDockFailed
                    : (latest.state === 'cancelled' ? MSG.encodeStCancelled
                        : MSG.encodeDockDone));
            fill.style.width = bad ? fill.style.width : '100%';
            if (bad) fill.classList.add('err'); else fill.classList.remove('err');
            eta.textContent = '';
            cancelBtn.style.display = 'none';
        }
        this.renderList(jobs, sup);
    },

    _baseName(p) {
        return String(p || '').split(/[\\/]/).pop() || String(p || '');
    },

    renderList(jobs, sup) {
        const panel = document.getElementById('encodeDockList');
        if (!panel) return;
        panel.textContent = '';
        const mk = (tag, cls, parent) => {
            const el = document.createElement(tag);
            if (cls) el.className = cls;
            if (parent) parent.appendChild(el);
            return el;
        };
        if (sup && (sup.busy || sup.phase === 'downloading')) {
            const row = mk('div', 'queue-item', panel);
            mk('span', 'queue-item-dot running', row);
            const nm = mk('span', 'queue-item-name', row);
            nm.textContent = MSG.encodeDownloadDock;
            const tr = mk('span', 'queue-item-track', row);
            const f = mk('span', 'progress-fill', tr);
            f.style.width = ((sup.total > 0)
                ? Math.min(99, Math.round((sup.received / sup.total) * 100)) : 0) + '%';
        }
        jobs.slice().reverse().forEach((j) => {
            const row = mk('div', 'queue-item', panel);
            row.dataset.encodeJobId = j.id;
            mk('span', 'queue-item-dot ' + j.state, row);
            const nm = mk('span', 'queue-item-name', row);
            nm.textContent = this._baseName(j.out_path);
            nm.title = j.out_path;
            if (j.state === 'running' || j.state === 'queued') {
                const tr = mk('span', 'queue-item-track', row);
                const f = mk('span', 'progress-fill', tr);
                f.style.width = (j.progress || 0) + '%';
                if (j.state === 'queued') f.style.width = '0%';
            } else if (j.state === 'done') {
                const pill = mk('span', 'queue-item-pill', row);
                pill.textContent = MSG.encodeStDone;
            } else if (j.error) {
                const err = mk('span', 'queue-item-err', row);
                err.textContent = j.error;
                err.title = j.error;
            }
            const act = mk('button', 'btn btn-ghost btn-sm', row);
            if (j.state === 'running' || j.state === 'queued') {
                act.textContent = MSG.encodeCancelJob;
                act.addEventListener('click', () => this.cancelOne(j));
            } else if (j.state === 'failed' || j.state === 'cancelled') {
                act.textContent = MSG.encodeRetry;
                act.addEventListener('click', () => this.retry(j.id));
            } else if (j.state === 'done') {
                act.textContent = MSG.encodeOpenFolder;
                act.addEventListener('click', () => this.openFolder(j.id));
            } else {
                act.style.display = 'none';
            }
        });
    },

    async cancelOne(job) {
        const api = this._api();
        if (!api) return;
        if (job.state === 'running') {
            const ok = await AppModal.confirm(MSG.encodeModalTitle, MSG.encodeCancelOneConfirm);
            if (!ok) return;
        }
        try { await api.encode_cancel(job.id); } catch (e) { /* 下轮轮询自愈 */ }
        this.refresh();
    },

    async cancelAll() {
        const api = this._api();
        if (!api) return;
        // 供给下载进行中 → 停止下载；否则取消队列
        try {
            const sup = await api.ffmpeg_supply_progress();
            if (sup && sup.success !== false && (sup.busy || sup.phase === 'downloading')) {
                await api.ffmpeg_supply_stop();
                this.refresh();
                return;
            }
        } catch (e) { /* 忽略走队列取消 */ }
        const ok = await AppModal.confirm(MSG.encodeModalTitle, MSG.encodeCancelAllConfirm);
        if (!ok) return;
        try { await api.encode_cancel(''); } catch (e) { /* 下轮轮询自愈 */ }
        this.refresh();
    },

    async retry(jobId) {
        const api = this._api();
        if (!api) return;
        try { await api.encode_retry(jobId); } catch (e) { /* 下轮轮询自愈 */ }
        this.show();
        this.refresh();
    },

    async openFolder(jobId) {
        const api = this._api();
        if (!api) return;
        try { await api.encode_open_folder(jobId); } catch (e) { /* 静默 */ }
    },
};

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
