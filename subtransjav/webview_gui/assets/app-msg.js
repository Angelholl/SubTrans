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
    // 全链自动化开关（3.0 批1 a 段，D2026-1009-02；strings.py MSG 同键镜像）
    fullchainAutoSwitch: '翻译完成后自动执行：分析→批量修复→复验（含自动压制排布）',
    // 流水线卡文案（d1013-卡M / D2026-1013-01：开关主行短句升位
    // （原长句降副行 desc）+ 自动化小节标题；JS 态键零静态 i18n 消耗）
    encodeAutoShort: '自动压制',
    fullchainAutoShort: '全链自动化',
    pipelineGroupAuto: '自动化',
    // 全链链级状态行+digest+一键回滚（3.0 批2，D2026-1009-02 批2；
    // strings.py MSG 同键镜像双表，JS 态零静态 i18n 消耗）
    fullchainRollbackBtn: '一键回滚',
    fcStatusRunning: '全链自动化进行中：已处理 {d}/{t} 文件，修复 {f} 条',
    fcStatusLast: '上次全链（{time}）：修复 {f} 条 · 失败 {m} · 待修 {p}（{phase}）',
    fcStatusSkipped: '未启动全链（服务商原因）',
    fcStatusUnfinished: '上次未完成：待修 {p} 条',
    fcStatusNever: '全链自动化尚未运行',
    fcStatusFail: '全链状态读取失败',
    fcMissedSkipped: '漏听放弃 {k} 条',
    fcDigestTitle: '最近一次链摘要',
    fcDigestSummary: '文件 {d}/{t} · 修复 {f} · 失败 {m} · 待修 {p}',
    fcDigestVerifyNone: '复验三键计数差值：—（本链快照未记录复验前后计数）',
    fcDigestLedgerNote: '逐条改动明细见各文件的重翻台账（{stem}_重翻记录.json）',
    fcRollbackConfirmTitle: '一键回滚',
    fcRollbackConfirmBody: '台账中可回滚的改写记录 {n} 条。\n确认后将把终稿译文恢复为修复前文本。',
    fcRollbackAutoInsertDelete: '将删除 {n} 条自动插入行。',
    fcRollbackNone: '台账中无可回滚的改写记录',
    fcRollbackDone: '回滚完成：恢复 {n} 条',
    fcRollbackUnmatched: '；未命中 {n} 条（timing 不在终稿中）',
    fcRollbackSkipped: '；自动插入行已删除 {k} 条',
    fcRollbackFail: '回滚失败',
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
    encodeParamsLink: '压制参数',
    encodeGpuEditTitle: 'GPU 可用性在发起一次压制时自动检测；此处暂不可选',
    encodeSummaryLine: (parts) => `当前压制参数：${parts.join(' · ')}`,
    encodeSummaryEmpty: '暂无已保存的压制参数（点「打开压制参数」设置）',
    encodeSummaryVol: (db) => `音量 ${db}dB`,
    encodeSummaryAt: (t) => `保存于 ${t}`,

    // 字幕清洗参数弹窗（D2026-1024-01 批2 件A）：高级参数 TAB「字幕清洗」
    // 入口组+弹窗全 JS 态文案（零静态 data-i18n/零 id）；入口组标题复用
    // polish_enabled_label（「字幕清洗（实验性）」文字相同）。文案照抄
    // 批2 卡面（D2026-1024-01），未应用 summary 零散拼接片段随值内联
    polishAdvBadge: 'PROVISIONAL · 待校准',
    polishAdvDesc: '总开关在右侧「输出格式」区的「字幕清洗（实验性）」复选框；本弹窗参数仅在开关开启后生效。留空或填 0 = 使用内置默认值（默认口径暂定 PROVISIONAL，待校准）。',
    polishAdvOpenBtn: '字幕清洗设置…',
    polishAdvSummaryDefault: '当前参数：默认口径（每行 16 全角字 · 每条 2 行 · 上限 7000ms · 间隔 83.4ms）',
    polishAdvSummaryLine: (parts) => `当前参数：${parts.join(' · ')}`,
    polishPopupTitle: '字幕清洗参数',
    polishPopupJobsLine: '仅保存清洗参数，不会立即处理已有字幕；总开关在右栏「输出格式」区，开启后本组参数才生效。',
    polishPopupSecText: '文本规范',
    polishPopupSecTiming: '时间轴',
    polishPopupSave: '保存',
    polishLblMaxChars: '每行最大全角字数',
    polishLblMaxLines: '每条最大行数',
    polishLblQuoteStyle: '引号派系',
    polishLblStripPeriod: '句末去句号',
    polishLblDialogGt: '行首「>>」对话标记',
    polishLblRewrap: '拆行重排',
    polishLblMaxDur: '显示时长上限 ms',
    polishLblMinGap: '相邻最小间隔 ms',
    polishLblClampLong: '超长缩短钳制',
    polishPhMaxChars: '默认 16',
    polishPhMaxLines: '默认 2',
    polishPhMaxDur: '默认 7000',
    polishPhMinGap: '默认 83.4',
    polishQuoteDefault: '跟随默认（「」）',
    polishQuoteKeep: '完全不动',
    polishQuoteCurly: '弯引号“”',
    polishPeriodDefault: '跟随默认（去）',
    polishPeriodKeep: '保留句号',
    polishGtDefault: '跟随默认（保留）',
    polishGtRemove: '删除',
    polishNoteMaxChars: '一行最多排多少个全角字，超出就折到下一行；留空即用默认 16。',
    polishNoteMaxLines: '一条字幕最多分成几行显示，不够放就拆成多条；留空即用默认 2。',
    polishNoteQuoteStyle: '中文引号统一成哪套样式：「」是默认；选「完全不动」则一个引号都不碰。',
    polishNoteStripPeriod: '句尾的句号要不要删掉：默认删（画面更干净），也可统一保留。',
    polishNoteDialogGt: '行首的 >> 对话标记：默认保留（区分说话人），也可统一删掉。',
    polishNoteRewrap: '过长的一条按上面设定的字数/行数重新断行排版，必要时拆成多条；关闭则不重排。',
    polishNoteMaxDur: '单条字幕最多显示多久（毫秒），再长也会被切走；留空即用默认 7000。',
    polishNoteMinGap: '相邻两条字幕之间至少留多长空档（毫秒）；留空即用默认 83.4。',
    polishNoteClampLong: '单条显示超过「时长上限」时自动切走多余时长；关闭则超长条目只记入报告、不缩短。',
    polishTimingCaliber: '口径提示：最小间隔 83.4 ms ≈ 2 帧 @ 23.976fps，指「相邻两条之间的空档」，与「最短显示时长」不是一个参数，勿与 833 ms 口径混淆。',

    // TM 与断点合并弹窗（D2026-1024-01 批3 件B）：高级参数 TAB「TM 与断点」
    // 入口组+弹窗壳文案；8 控件标签/长提示 title/placeholder/分区标题全部
    // 复用既有键（tm_* / glossary_* / resume_* / force_resume_* / verbose_* /
    // adv_group_tm_learn_gate / adv_group_resume_logging），新增键仅组名/
    // 说明/入口钮/弹窗标题/保存钮/短注×8；summary 状态词与偏离片段随值内联
    // （encode 摘要 'H.264' 内联先例同构）
    tmBreakAdvGroupTitle: 'TM 与断点',
    tmBreakAdvDesc: '翻译记忆库与学习闸、断点恢复与日志的合并设置（原「TM 与学习闸」「断点与日志」两组已整合迁入弹窗）。',
    tmBreakAdvOpenBtn: 'TM 与学习闸 / 断点与日志…',
    tmBreakPopupTitle: 'TM 与断点设置',
    tmBreakPopupSave: '保存',
    tmBreakNoteTmEnable: '开启后翻译时复用以往积累的译文记忆；取消则本次完全不读写记忆库。',
    tmBreakNoteTmThreshold: '模糊匹配严格程度 0-1（步进 0.05）；留空即用管线默认，一般无需填写。',
    tmBreakNoteTmDb: '留空 = 使用默认 TM 库。',
    tmBreakNoteGlossaryLearn: '翻译命中写入学习词库（默认关闭）；与手动词库分层生效，可在词库页查看。',
    tmBreakNoteConflictBlock: '冲突条目默认仅观察；开启后禁入 TM。',
    tmBreakNoteResume: '中断后重跑自动续跑剩余部分；一般保持勾选。',
    tmBreakNoteForceResume: '指纹不匹配也接着上次进度继续，可能用到过期中间结果。',
    tmBreakNoteVerbose: '向子进程传递 --verbose 输出调试日志。',

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
    source_header: '拖拽 .srt 字幕文件到这里',
    no_files_selected: '暂未选择文件',
    // d1015-卡E（D2026-1015-05）：文件卡头「已选 X 个」计数（JS 态键，
    // 卡D 骨架 .card-head-count 由此填充；0 文件时不显示）
    selected_count: (n) => `已选 ${n} 个`,
    empty_hint: '点击按钮选择文件或文件夹，也可直接拖入 · 支持 .srt / .ass / .ssa / .vtt 批量添加',
    add_files: '添加文件',
    add_folder: '添加文件夹',
    remove_selected: '移除选中',
    clear_btn: '清空',

    // ---- 输出目录 ----
    output_header: '输出目录',
    output_format_header: '输出格式',
    output_fmt_ass: '同时输出 .ass',
    output_fmt_vtt: '同时输出 .vtt',
    // 字幕清洗总开关（D2026-1023-03 批3）：默认不勾，会话级无持久化
    polish_enabled_label: '字幕清洗（实验性）',
    save_to_source_dir: '保存到字幕同目录',
    output_label: '输出:',
    output_placeholder: '输出目录...',
    browse_btn: '浏览',
    open_btn: '打开',

    // ---- 净语翻译面板 ----
    // 卡8 B-06（D2026-1012-01）：标题缩短防右栏 316px 折行（改值不改键），
    // 完整句改走 applyI18n 内 JS 回填悬停（不落静态属性，见 applyI18n 注释）
    refine_panel_title: '两阶段流水线',
    // d1013-卡D（D2026-1013-01）：AI 区英文 label/option 运行时 MSG 回填四键
    // （index.html 零 data-i18n 新增，走 B-06 先例 MSG 运行时回填路线）
    ai_provider_label: '分析提供方',
    follow_stage_default: '跟随阶段 A（默认）',
    ai_model_label: '分析模型',
    cross_film_window: '跨片统计窗口',
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
    key_placeholder: '留空用已保存密钥',
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
    save_endpoints_btn: '保存接口',
    start_btn: '开始净语翻译',
    // 翻译 TAB 快捷开始钮独立键（d1023 owner 指定四字文案；右栏主钮 start_btn 不动）
    start_btn_tab: '开始翻译',
    stop_btn: '停止',
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
    key_saved_placeholder: '已保存 ※※※※※※',
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
    // 批5（D2026-1008-02）：行动条目台账已修徽标（JS 态；guideRender 按
    // lastActionItems.applied_in_ledger 渲染，guide_path 一致才生效）
    guide_item_applied: '✅ 已修',
    // 批6（D2026-1008-02）：终态徽标与头部计数分解（JS 态；零 data-i18n）
    guide_item_nochange: '已一致',
    guide_chip_fixable: '待修',
    guide_chip_applied: '已修',
    guide_chip_nochange: '无需改动',
    guide_chip_observation: '观察',

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
    // P3（D2026-1008-02）：TM 建议编辑后存入——行级编辑/恢复入口 +
    // tmEdit 弹窗全 JS 态文案（零静态 data-i18n/零 id，FROZEN 双钉不变）
    aiTmEditBtn: '编辑',
    aiTmRestoreBtn: '恢复原建议',
    aiTmStoredEdited: '已存入 ✓（编辑后译文）',
    tmEditTitle: '编辑 TM 建议',
    tmEditSessionHint: '仅本次会话有效，存入 TM 后才持久',
    tmEditSave: '保存',
    tmEditEmptyTarget: '译文不能为空',
    tmEditSaveFailed: '保存失败',
    tmEditDirtyConfirm: '有未保存的修改，确定放弃并关闭？',
    aiParseFailed: '⚠️ AI 输出解析失败，以下为原始观察文本',
    aiDone: 'AI 分析完成，建议仅供人工裁决',
    aiFailed: m => `AI 分析失败：${m}`,
    // ---- P1 分析模型预热（D2026-1008-02 批3，G1 落 (c) 阻断形态）----
    // G4 透明文案：预热可能顶掉 LM Studio 手动加载的当前模型（后端 gui.log 同步留痕）
    warmupStarted: '正在预热分析模型，可能切换 LM Studio 当前模型',
    warmupHot: '分析模型已在载，跳过预热',
    warmupAfterQueue: '翻译队列完成，触发分析模型预热',
    warmupQueued: '正在预热分析模型，翻译已排队（以点击时参数为准）',
    warmupTimeout: '预热等待超时，已放行翻译',
    warmupUnknown: '预热状态不可确认，已放行翻译',
    warmupDone: '预热完成，继续启动翻译',
    warmupFailed: '预热未完成，放行翻译（翻译将按自身流程加载模型）',
    warmupHoldBtn: s => `预热中 ${s}s，翻译已排队…`,
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
    pipeline_card_hint_here: '当前已在「API 与模型选择」页',

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
    activity_stage_start: stage => `${stage} 开始`,
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
    dict_sudachi_full_label: '日语完整版（sudachi full）',
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
    // 批6（D2026-1008-02）：已与现译一致条目单独计数（后端 r.nochange）
    batchFixNochange: n => `${n} 条已与现译一致，无需改动`,
    // D2026-1010-02 件3b：源文退化守卫跳过单列（后端 r.skipped；未调模型
    // 不计失败，status 保持 open，提供原始日文 SRT 后可重试）
    batchFixSkipped: n => `${n} 条因缺源文跳过（提供原始日文 SRT 后可重试）`,
    // D2026-1010-03 件A/件B：媒体对照区块 + TM 定位/试听（JS 态零 data-i18n）
    crosscheckTitle: n => `媒体对照（本地转写 ${n} 段）`,
    ccThTiming: '时间轴',
    ccThAsr: 'ASR 转写',
    ccThCurrent: '现译',
    previewNeedGuide: '先加载导读后可试听',
    tmViewEntry: '查看条目',
    // 批5（D2026-1008-02）：完成消息剩余明细（主行截断前 10 个条目号，
    // 完整列表走 #refineBatchFixStatus title 悬停）
    batchFixRemaining: (n, ids) => `未修复 ${n} 条：${ids}`,
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
    // 卡8 B-06（D2026-1012-01）：refine_panel_title 视觉标题缩短为
    // 「两阶段流水线」（右栏 316px 防折行，改值不改键），完整句改由本处
    // 回填悬停——引擎页主栏与右栏卡3 同键双渲染，两处同步。完整句不进
    // index.html 静态属性：title=（含 *-title= 子串属性）中文须
    // data-i18n-title 管理（红线 test_html_has_no_unmarked_user_visible_chinese），
    // 而 data-i18n-title 又会被上一段以 MSG 短值覆写（完整句失效）；
    // 卡面明令键集零变化，故此处以字面量承接而不新增 MSG 键。
    document.querySelectorAll('[data-i18n="refine_panel_title"]').forEach(el => {
        el.setAttribute('title', '净语翻译 · 两阶段流水线（净语+翻译 → 审校+抛光）');
    });
    // d1013-卡D（D2026-1013-01）：AI 区英文 label/option 运行时回填（B-06 先例）
    // 目标：index.html:729 label[for=aiProviderSel]、:731 option[value=follow]、
    // :740 label[for=aiModelInput]、:758 label[for=aggregateWindowSel]
    const aiProviderLabel = document.querySelector('label[for="aiProviderSel"]');
    if (aiProviderLabel) aiProviderLabel.textContent = MSG.ai_provider_label;
    const followOption = document.querySelector('#aiProviderSel option[value="follow"]');
    if (followOption) followOption.textContent = MSG.follow_stage_default;
    const aiModelLabel = document.querySelector('label[for="aiModelInput"]');
    if (aiModelLabel) aiModelLabel.textContent = MSG.ai_model_label;
    const aggWindowLabel = document.querySelector('label[for="aggregateWindowSel"]');
    if (aggWindowLabel) aggWindowLabel.textContent = MSG.cross_film_window;
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

    // 全链自动化开关镜像（3.0 批1 a 段，D2026-1009-02）：EncodeDock.init
    // 启动回填时同步维护；warmupMaybeStart 守卫消费（C-1：全链开启时前端
    // 预热短路，预热由后端链首环承接）
    fullchainAutoEnabled: false,

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

