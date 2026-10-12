"""GUI 用户可见文案字符串表（唯一中文来源，webview-free 可测模块）。

- Python 侧（api.py / main.py）通过 ``msg(key, **kw)`` 取文案；
- JS 侧无法 import Python，app.js 顶部维护一个 ``const MSG = {...}``
  镜像对象（注释注明与本表对应，键名保持一致）。

约定：
- 值为中文文案；占位符用 str.format 风格（``{n}``/``{e}``/``{code}``），
  错误消息中夹带异常详情时占位符名固定为 ``e``；
- ``msg()`` 对未知键回退返回键名本身、格式化失败回退原文，绝不抛异常；
- 日志哨兵前缀（``[SUCCESS]``/``[ERROR]``/``[CANCELLED]``/``[WARN]``）
  保留英文标记（前端/测试依赖），仅后缀文案走本表。
"""

# 语义键 -> 中文文案
MSG = {
    # ---- 窗口 / 文件对话框（api.py）----
    "no_active_window": "无活动窗口",
    "no_folder_selected": "未选择文件夹",
    "no_files_selected": "未选择文件",
    "no_srt_in_folder": "所选文件夹中未找到 .srt 字幕（目录添加仅收 .srt；ASS/SSA/VTT 请用「添加文件」选择）",
    # 2.7.2 件1（D2026-1005-02）：目录无 .srt 但检测到 ASS/SSA/VTT 时的针对性提示
    "no_srt_but_subtitle_in_folder": "检测到 ASS/SSA/VTT 字幕，目录添加仅收 .srt，请用「添加文件」逐个选择",
    # 2.7.3 件④（D2026-1005）：目录 .srt 全为流水线产物时的针对性提示
    "folder_all_skipped_pipeline": "文件夹内的 .srt 全部是本工具的流水线中间稿或终稿"
                                   "（pass1/pass2、_refine_、_final_ 命名），"
                                   "没有可收编的新文件。如需添加，请用「添加文件」手动选择产成品。",
    "folder_opened": "文件夹已打开",
    "cannot_open_folder": "无法打开文件夹：{e}",

    # ---- 版本信息（api.py）----
    "version_load_failed": "无法加载版本信息",

    # ---- 翻译进程管理（api.py）----
    "translation_in_progress": "翻译已在进行中",
    "translation_started": "翻译已启动，共 {n} 个文件",
    "translation_cancelled": "翻译已取消",
    "no_translation_in_progress": "当前没有进行中的翻译",
    "translation_still_starting": "翻译仍在启动中，请稍后重试",
    "process_exit_code": "翻译进程已退出，退出码 {code}",

    # ---- 日志哨兵行后缀（api.py；前缀 [SUCCESS]/[ERROR]/[CANCELLED] 保留英文）----
    "log_success": "翻译完成。",
    "log_cancelled": "翻译已取消。",
    "log_exit_code": "退出码：{code}",

    # ---- GUI 启动 / 控制台日志（main.py）----
    "window_created": "窗口创建成功",
    "starting_webview": "正在启动 PyWebView...（debug={debug}）",
    "dom_events_bound": "DOM 拖放事件绑定成功",
    "dom_events_bind_failed": "警告：DOM 事件绑定失败：{e}",
    "dom_events_fallback": "拖放功能可能不可用，请改用「添加文件」按钮。",
    "gui_banner": "净语翻译 GUI v{version}",
    "appusermodelid_failed": "警告：设置 AppUserModelID 失败：{e}",
    "asset_not_found": "错误：资源文件未找到！",
    "gui_start_failed": "错误：GUI 启动失败！",
    "drop_event_error": "处理拖放事件出错：{e}",
    "webview2_check_failed": "警告：无法检查 WebView2 运行时状态：{e}",

    # ---- CLI 帮助 / 自举（main.py）----
    "app_title": "净语翻译 · SubTrans Translate",
    "cli_description": "净语翻译 · SubTrans 桌面 GUI"
                       "（两阶段字幕流水线：阶段A 净语+翻译 → 阶段B 审校+抛光）",
    "cli_help_debug": "以调试模式启动 WebView（可打开开发者工具）",
    "cli_help_version": "打印程序版本号后退出",
    "setup_creating_venv": "[SETUP] 首次运行，正在创建虚拟环境...",
    "setup_env_ready": "[SETUP] 环境就绪，正在启动程序...",
    "setup_installing": "[SETUP] 正在安装依赖，请稍候...",
    "setup_install_done": "[SETUP] 安装完成，正在重启程序...",
    "setup_init_failed": "[SETUP] 环境初始化失败: {e}",
    "setup_unknown_error": "[SETUP] 发生未知错误: {e}",
    "setup_manual_hint": "请尝试手动运行: pip install subtransjav[gui]",
    "setup_press_enter": "按回车键退出...",

    # ---- 角色卡目录守卫（api.py）----
    "template_dir_not_allowed": "模板目录仅允许服务端默认目录或本会话选择的目录: {path}",

    # ---- refine 失败诊断提示（api.py）----
    "tip_region_blocked": "该模型对中国大陆区域封锁(403)，请换其他模型",
    "tip_rate_limited": "免费额度限速(429)，稍等几分钟再试或换模型",
    "tip_upstream_down": "上游服务临时宕机，稍后重试或换模型",
    "tip_invalid_key": "密钥无效或未配置",
    "tip_check_key_network": "请检查密钥/网络",

    # ---- 系统状态（api.py）----
    "grammar_hints_available": "日语形态素分析提示（阶段A 自动启用）",
    "grammar_hints_unavailable": "日语形态素分析提示（未安装 sudachipy）",

    # ---- 词典管理（api.py，2.1 引擎页词典管理三区块）----
    "dict_kind_unsupported": "该词典暂不支持下载（仅 sudachi 提供下载式）",
    "dict_download_failed": "词典下载失败（网络/源不可达）",
    "dict_checksum_failed": "词典校验失败（SHA256 不符，已拒绝落位）",
    # 2.7.3 件⑤（D2026-1005）：词典下载会话制——同 kind 互斥拒绝文案
    "dict_download_busy": "已有词典任务在进行中，请稍候或先停止当前下载。",
    # 下载进度阶段文案（第四批 owner 验收反馈；前端 app.js MSG 同名键双表）
    "dict_verify": "校验中…",
    "dict_extract": "解压中…",
    # 批1b 件2：一键迁移（refine_dict_migrate）
    "dict_migrate_need_custom": "尚未设置自定义词典目录，无需迁移",
    "dict_migrate_need_source": "缺少旧词典目录（请先更改词典目录再迁移）",
    "dict_migrate_failed": "词典迁移失败",

    # ---- 翻译方向（高级参数页，2.1 D2026-0930-04 定案① GUI 补齐）----
    "direction_label": "翻译方向",
    "direction_title": "缺省 日文→中文 全链零感知；切换非缺省方向（如 中文→英文）须为全部启用阶段显式指定配套模板卡（阶段A/阶段B 角色卡路径），缺卡启动即被校验拒绝",
    "lang_ja": "日文",
    "lang_zh": "中文",
    "lang_en": "英文",
    "direction_card_s1_label": "阶段A 指令卡",
    "direction_card_s3_label": "阶段B 指令卡",
    "direction_card_placeholder": "非缺省方向必填（.txt 路径）",
    "direction_hint": "缺省日→中无需配置；切换非缺省方向须为全部启用阶段显式指定配套模板卡，缺卡启动即报错",

    # ---- open_url / 目录（api.py）----
    "url_scheme_unsupported": "仅支持 http/https 链接",
    "dir_not_exist": "目录不存在: {path}",

    # ---- 模型列表 / 连通性测试（api.py）----
    "endpoint_missing": "缺少接口地址(endpoint)",
    "endpoint_scheme_unsupported": "接口地址仅支持 http/https",
    "api_key_missing": "缺少 API Key（请先在密钥区保存）",
    "model_name_missing": "未填写模型名",
    "stage_test_ping": "回复：OK",
    "stage_test_reasoning": "(推理模型)...{tail}",
    "stage_test_empty": "(空响应)",

    # ---- 角色卡模板（api.py）----
    "invalid_stage_tag": "无效阶段标识：{tag}（应为 A 或 B）",
    "template_file_missing": "模板文件不存在：{path}",
    "template_b_note": "阶段B(审校抛光)的硬性豁免段由引擎运行时自动追加，无需写在本卡内",
    # 角色卡文件名参数位守卫（D2026-0930-07-追加1 必改②/⑤）
    "template_filename_invalid": "角色卡文件名不合法（仅允许目录内纯 .txt 文件名）：{name}",
    "template_save_not_allowed": "仅允许保存角色卡目录中已存在的 .txt 文件或默认角色卡：{name}",

    # ---- 质量报告导读（api.py）----
    "guide_path_empty": "路径为空，请先指定导读文件",
    "guide_path_denied": "该路径不在允许范围：{e}（系统目录与可执行文件除外，用户磁盘目录均可）",
    "guide_file_missing": "文件不存在：{path}",
    "guide_suffix_only": "仅支持质量报告导读/报告文件（*{suffix}），拒绝读取其他文件：{name}",
    "guide_bad_format": "导读文件格式异常：顶层应为 JSON 对象",
    "guide_corrupted": "导读文件损坏：不是有效的 JSON，请重新生成质量报告",

    # ---- 文件对话框类型 / 取消（api.py）----
    "file_type_glossary": "词库文件 (*.csv;*.txt)",
    "file_type_guide": "质量报告导读 json (*.json)",
    "file_type_csv": "CSV 文件 (*.csv)",
    "file_type_sqlite": "SQLite 数据库 (*.db)",
    "file_type_all": "所有文件 (*.*)",
    "dialog_cancelled": "已取消",

    # ---- 翻译记忆库（api.py）----
    "tm_cleared": "翻译记忆库已清空",
    "tm_export_path_missing": "未指定导出路径",
    "tm_import_path_missing": "未指定导入文件",
    "tm_imported": "已导入 {n} 条新记录",

    # ---- 完成态 [WARN] 行后缀（api.py；前缀 [WARN] 保留英文）----
    "warn_exit3": "翻译完成，但存在严重质量风险（exit 3），请检查风险清单。",
    "warn_majority": "翻译完成，但检测到整段未翻译风险，请检查风险清单。",
    "warn_risks": "翻译完成，但检测到 {n} 条风险，请检查风险清单。",

    # ---- 事件流格式化（event_stream.py；字节级文案与原实现一致，测试钉住）----
    "stage_a": "阶段A 净语+翻译",
    "stage_b": "阶段B 审校+抛光",
    "ev_tag": "[事件]",
    "ev_task_started": "任务开始",
    "ev_task_finished": "任务结束",
    "ev_phase_started": "开始",
    "ev_phase_started_generic": "阶段开始",
    "ev_phase_finished": "完成",
    "ev_phase_finished_generic": "阶段完成",
    "ev_in_progress": "进行中",
    "ev_batch": "批次 {done}/{total}",
    "ev_lines": "{done}/{total} 行",
    "ev_warning": "⚠ 警告：{e}",
    "ev_degraded": "⚠ 降级：{e}",
    "ev_error": "✗ 错误：{e}",
    # 批 8a（D2026-1006-01）：闸门0 摘要人话行（后端侧键，本批不入 app.js
    # 镜像；前端活动流消费时再随批同步双表）
    "ev_gate0": "闸门0 {file}：检出 {detected} · 处置 {deleted} · 净语 {net}",
    "processing": "处理中",
    "progress_text": "已翻译约 {done}/{total} 行（{label}）",

    # ---- refine 阶段设置（app.js MSG 镜像；JS 侧专用，双表同步）----
    "resume_fingerprint_hint": "（修改模型或窗口/并发参数后，旧断点将不可复用）",

    # ---- UI 改版阶段2（D2026-0930-09 批1；app.js MSG 镜像，双表同步）----
    "nav_group_workspace": "工作区",
    "nav_group_quality": "设置",
    "main_subtitle": "一站式 AI 字幕翻译与校对",

    # ---- 右栏系统状态摘要卡（D2026-1001 批3，owner 特批 2 键）----
    "sys_summary_title": "系统状态",
    "sys_summary_unavailable": "不可用",

    # ---- 数据保存目录（api.py refine_set_data_root 校验文案）----
    "data_root_need_abs": "请输入绝对路径",

    # ---- 校对页（2.6.1 批 2a D2026-1002-09；api.py refine_review_* 镜像，
    #      后端侧键不入前端静态快照口径）----
    "file_type_video": "视频文件 (*.mp4;*.mkv;*.webm;*.mov;*.avi)",
    "file_type_srt": "字幕文件 (*.srt)",
    # 批2 多格式导入（D2026-1003-05）：后端侧键（select_srt_files 对话框过滤）
    # 2.7.2 件1（D2026-1005-02）：描述段去 `/`——pywebview parse_file_type
    # 描述段正则 `^([\w ]+)` 不容斜杠，旧串致 create_file_dialog 整体 ValueError
    "file_type_subtitle": "ASS SSA VTT 字幕 (*.ass;*.ssa;*.vtt)",
    "review_transcode_no_need": "该媒体可直接预览，无需转码",
    "review_transcode_running": "已有转码任务进行中",
    "review_transcode_failed": "转码失败，请重试或手动转换格式",
    "review_no_ffmpeg": "未检测到 ffmpeg，无法转码",
    "review_media_missing": "媒体文件不存在或未导入",
    "review_srt_missing": "字幕文件不存在或未导入",
    "review_probe_failed": "无法识别该媒体的编码信息",
    "review_srt_bad_encoding": "字幕文件编码无法识别（仅支持 UTF-8 / GBK），请另存为 UTF-8 后重试",

    # ---- 校对编辑（2.6.1 批 2b D2026-1002-10；api.py refine_review_save* 镜像）----
    "review_backup_failed": "备份原文件失败，已中止保存（原文件未改动）",
    "review_save_blocks_invalid": "字幕数据无效（blocks 须为非空且每项含 start_ms/end_ms/text）",

    # ---- ASR 模型状态三口径对齐（2.7.3 件③；app.js MSG 镜像，JS 侧专用，
    #      双表同步——红绿灯空态文案 + 下拉占位项，全 JS 态零静态 i18n 消耗）----
    "asrModelUnselected": "未选择",
    "asrModelPlaceholder": "未选择（点选即保存）",

    # ---- P2 修复/分析模型统一（D2026-1008-02）：共用解析 helper
    #      _resolve_ai_model_config 拒绝/注记文案（C6 单源；旧独立修复链
    #      键 fix_model_unconfigured/fix_model_a_b_unset/
    #      fix_model_b_provider_no_model/fix_model_b_model_provider_mismatch/
    #      fix_config_half_set/fix_config_custom_unsupported 随链删除，
    #      C11 解冻-重钉）----
    # 独立配置半配置（G5-补：仅 provider 无 model）→ 视为未配置忽略
    "fix_ai_indep_half_ignored": "分析独立配置不完整，已忽略",
    # 阶段A 链终点仍无线索（C9：分析未配置+阶段A 无模型）→ 如实拒绝（C8）
    "fix_ai_model_unset": "分析模型与阶段A 均未配置，无法修复：请在「质量与建议」配置 AI 分析模型，或在「翻译设置 · 阶段A（净语+翻译）」填写模型名",
    # 独立配置 custom 兜底拒绝（无默认端点；refine_ai_analyze 与共用
    # helper 同串单源消费）
    "ai_indep_custom_unsupported": "自定义接口暂不支持独立配置：请将阶段A 服务商设为 custom 后使用",

    # ---- 批修复端点预检（D2026-1007-02 件E：C8 本地端点 spawn 前探活，
    #      不通即拦截；api.py refine_batch_fix 预检失败分支）----
    "fix_endpoint_unreachable": "本地推理端点不可达（{endpoint}）：请确认本地推理服务已启动，或检查「翻译设置」中的接口地址后再发起批量修复",

    # ---- 硬字幕压制（2.8.0 批1 件4，D2026-1007-03；app.js MSG 镜像双表同步，
    #      JS 态零静态 i18n 消耗）----
    "encode_translate_conflict": "压制任务进行中，无法开始翻译——请等待压制完成，或在队列底条中取消压制任务",
    "translate_encode_conflict": "翻译任务进行中，无法加入压制队列——请等待翻译完成后再试",
    # 批修复重入守卫（批1 a 段，D2026-1009-02：_batch_fix_running 在飞时
    # 二次调用结构化拒绝；api.py refine_batch_fix 消费）
    "batch_fix_running": "批量修复进行中，请等待当前批次完成后再发起新的修复",
    # 全链互斥矩阵（批1 b 段，D2026-1009-02：_fullchain_running 在飞时手动
    # 入口结构化拒绝；api.py start_translation/refine_batch_fix/
    # refine_ai_analyze/encode_commit 消费，显式拒绝不排队）
    "fullchain_running": "全链路自动化进行中，请稍后再试",
    # 一键回滚结构化失败（3.0 批2：api.fullchain_rollback 终稿缺失分支）
    "fullchain_rollback_missing_final": "终稿字幕不存在，无法回滚：{path}",
    "encode_jobs_invalid": "入队任务无效：{reason}",
    "encode_commit_rejected": "全部任务未能入队：{reason}",
    # 压制参数独立设置项（D2026-1008-01 批2：encode_save_params 失败 tip，
    # 对齐 _refine_error_tip 人话提示风格）
    "encode_params_tip_invalid": "请检查压制参数——格式/画质/分辨率/字号/码率/音量须在允许范围内",
    "encode_params_tip_json": "参数数据无法解析，请重新打开压制参数弹窗后再保存",
    "encode_params_tip_write": "参数写入失败，请检查数据保存目录是否可写",
    # —— 以下为 app.js MSG「硬字幕压制」节的双表镜像（JS 态专用，后端不消费；
    #     键值以此处为准同步，防止两表漂移）——
    "encodeEntryReview": "压制成品（硬字幕）",
    "encodeEntryGuide": "压制成品",
    "encodeModalTitle": "压制成品",
    "encodeSecBase": "基础",
    "encodeSecSubAudio": "字幕与音频",
    "encodeModalFmt": "格式",
    "encodeFmtH264": "H.264（兼容性最好）",
    "encodeFmtH265": "H.265（体积更小）",
    "encodeFmtAv1": "AV1（体积最小·耗时可能最长）",
    "encodeModalBackend": "后端",
    "encodeBackendAuto": "自动",
    "encodeBackendGpu": "GPU（批2 提供）",
    "encodeModalQuality": "画质",
    "encodeQCompress": "高压缩（体积优先）",
    "encodeQBalanced": "均衡（推荐）",
    "encodeQQuality": "高画质（观感优先）",
    "encodeModalRes": "分辨率",
    "encodeResOriginal": "保持原样",
    "encodeModalRate": "码控",
    "encodeRateTier": "按画质档（推荐）",
    "encodeRateVbr": "目标码率",
    "encodeModalBitrate": "目标码率（kbps，留空=按参考表派生）",
    "encodeModalOutDir": "输出目录（留空=与视频同目录）",
    "encodeModalFont": "字幕字号（12-72，缺省 22）",
    "encodeModalAudio": "音频",
    "encodeAudioCopy": "直接复制（推荐）",
    "encodeModalEnhance": "画质增强（降噪+锐化；关闭=忠实源）",
    "encodeModalAdvanced": "高级",
    "encodeModalAdvancedPh": "自定义参数 / 预设管理 —— 批2 面板完整化时启用",
    "encodePresetLabel": "预设",
    "encodePresetSave": "存为预设",
    "encodePresetDelete": "删除",
    "encodePresetBuiltinGroup": "内置",
    "encodePresetUserGroup": "我的预设",
    "encodePresetNamePrompt": "预设名称：",
    "encodePresetSaved": "预设已保存",
    "encodePresetDeleteConfirm": "删除预设「{n}」？",
    "encodeCustomLabel": "自定义参数（逃生门，追加到命令尾部）",
    "encodeCustomHint": "以空格分隔，如：-crf 18 -threads 8；与面板参数冲突或破坏固定约束（像素格式/滤镜链/码控映射）的旗标会被拒绝并显因",
    "encodeAv1Warn": "AV1 编码耗时显著更长（CPU 下与视频时长同量级），请留意预估时长",
    "encodeKnobDenoise": "降噪强度（0-10）",
    "encodeKnobDeblock": "去块强度（0-1）",
    "encodeKnobSharpen": "锐化量（0-2）",
    "encodeKnobVolume": "音量增益 dB（±12，≠0 需重编码音频）",
    "encodeAutoSwitch": "翻译完成后自动压制（硬字幕）",
    # 全链自动化开关（批1 a 段，D2026-1009-02；app.js MSG 同键镜像，JS 态
    # 零静态 i18n 消耗）：如实描述链内序=分析→批量修复→复验（含压制排布）
    "fullchainAutoSwitch": "翻译完成后自动执行：分析→批量修复→复验（含自动压制排布）",
    # ---- 全链链级状态行+digest+一键回滚（3.0 批2，D2026-1009-02 批2；
    #      app.js MSG 同键镜像双表，JS 态零静态 i18n 消耗）----
    "fullchainRollbackBtn": "一键回滚",
    "fcStatusRunning": "全链自动化进行中：已处理 {d}/{t} 文件，修复 {f} 条",
    "fcStatusLast": "上次全链（{time}）：修复 {f} 条 · 失败 {m} · 待修 {p}（{phase}）",
    "fcStatusSkipped": "未启动全链（服务商原因）",
    "fcStatusUnfinished": "上次未完成：待修 {p} 条",
    "fcStatusNever": "全链自动化尚未运行",
    "fcStatusFail": "全链状态读取失败",
    "fcMissedSkipped": "漏听放弃 {k} 条",
    "fcDigestTitle": "最近一次链摘要",
    "fcDigestSummary": "文件 {d}/{t} · 修复 {f} · 失败 {m} · 待修 {p}",
    "fcDigestVerifyNone": "复验三键计数差值：—（本链快照未记录复验前后计数）",
    "fcDigestLedgerNote": "逐条改动明细见各文件的重翻台账（{stem}_重翻记录.json）",
    "fcRollbackConfirmTitle": "一键回滚",
    "fcRollbackConfirmBody": "台账中可回滚的改写记录 {n} 条。\n确认后将把终稿译文恢复为修复前文本。",
    "fcRollbackAutoInsertDelete": "将删除 {n} 条自动插入行。",
    "fcRollbackNone": "台账中无可回滚的改写记录",
    "fcRollbackDone": "回滚完成：恢复 {n} 条",
    "fcRollbackUnmatched": "；未命中 {n} 条（timing 不在终稿中）",
    "fcRollbackSkipped": "；自动插入行已删除 {k} 条",
    "fcRollbackFail": "回滚失败",
    "encodeAutoDoneLine": "[压制] 全部完成——可在队列底条「打开文件夹」",
    "encodeJobsLine": "共 {n} 个文件 · 硬字幕烧录 · 底端居中白字黑边",
    "encodeEtaNone": "（时长预估需 ffmpeg 就绪后预检提供）",
    "encodeEtaTotal": "预计总时长：约 {t}",
    "encodeOk": "加入压制队列",
    "encodeNoJobs": "没有可压制的文件——请先在「翻译」页添加文件并完成翻译",
    "encodeSupplyMissing": "当前 ffmpeg 不支持硬字幕烧录（缺 libass/subtitles 滤镜）。需要下载一次完整版 ffmpeg（约 191MB，存到数据目录，仅下载一次）。现在下载吗？",
    "encodeSupplyFailed": "ffmpeg 下载失败：{e}",
    "encodeSupplyDone": "完整版 ffmpeg 就绪，请重新点击「压制成品」发起压制",
    "encodeOverwriteTitle": "覆盖确认",
    "encodeOverwriteBody": "以下成品文件已存在，覆盖它们吗？\n\n{list}",
    "encodeCommitRejected": "未能入队：{e}",
    "encodeCancelOneConfirm": "取消当前压制任务？",
    "encodeCancelAllConfirm": "取消当前任务并清空排队中的任务？",
    "encodeDockRunning": "压制中",
    "encodeDockDone": "压制完成",
    "encodeDockFailed": "压制失败",
    "encodeDockIdle": "队列空闲",
    "encodeStQueued": "排队中",
    "encodeStRunning": "压制中",
    "encodeStDone": "已完成",
    "encodeStFailed": "失败",
    "encodeStCancelled": "已取消",
    "encodeStStopped": "已停止",
    "encodeNoVideo": "未找到视频",
    "encodeNoSubtitle": "终稿字幕不存在",
    "encodeProbeErr": "媒体识别失败",
    "encodeRetry": "重试",
    "encodeOpenFolder": "打开文件夹",
    "encodeCancelJob": "取消",
    "encodeStop": "停止",
    "encodeExpand": "展开",
    "encodeCollapse": "收起",
    "encodeDismiss": "关闭",
    "encodeDownloadDock": "下载 ffmpeg 组件",
    "encodeMinutes": "{m} 分",
    "encodeEtaPending": "预估中",
    # 压制参数独立设置项（D2026-1008-01 批2：弹窗编辑模式+高级参数页入口）
    "encodeEditHint": "参数编辑模式——仅保存压制参数，不发起压制；压制成品请在校对页/导读页选中已完成字幕后再点「压制成品」",
    "encodeSaveParams": "保存参数",
    "encodeParamsSaved": "压制参数已保存——自动压制与下次压制将使用这组参数",
    "encodeParamsSaveFail": "参数保存失败：{e}",
    "encodeAdvGroupTitle": "压制",
    "encodeAdvGroupDesc": "压制成品的默认参数（格式/画质/音量等），「翻译完成后自动压制」同样使用这组参数",
    "encodeAdvOpenBtn": "打开压制参数",
    "encodeParamsLink": "参数",
    "encodeGpuEditTitle": "GPU 可用性在发起一次压制时自动检测；此处暂不可选",
    "encodeEditTitle": "压制参数",
    "encodeSummaryLine": "当前压制参数：{parts}",
    "encodeSummaryEmpty": "暂无已保存的压制参数（点「打开压制参数」设置）",
    "encodeSummaryVol": "音量 {db}dB",
    "encodeSummaryAt": "保存于 {t}",

    # ---- 批4（D2026-1008-01）：AI 分析/一键修复可停止 + 启动自愈
    #      （api.py 后端侧键：单飞拒绝/取消收口/取消闩/自愈 log；前端
    #      展示文案走 app.js MSG 镜像键，不入本表）----
    "ai_analyze_in_progress": "AI 分析已在进行中，请等待完成，或先停止当前分析再重新发起",
    "ai_analyze_cancelled": "AI 分析已取消",
    "ai_analyze_cancel_pending": "已收到停止请求，正在等待分析子进程退出…",
    "batch_fix_cancelled": "批量修复已取消：已落盘条目以重翻台账为准，可再次发起处理余量",
    "no_batch_fix_in_progress": "当前没有进行中的批量修复",
    # 启动自愈（gui.log 一行；kind 取 ai_analyze/batch_fix 机器码）
    "selfheal_cleaned": "已清理上次残留子进程（kind={kind} pid={pid}）",
    "selfheal_psutil_missing": "psutil 不可用，跳过残留子进程自愈扫描",
}


def msg(key: str, **kw) -> str:
    """按语义键取中文文案；支持 ``{name}`` 占位符格式化。

    - 未知键：回退返回键名本身（便于发现缺失，不抛异常）；
    - 格式化失败（缺参/占位符非法）：回退返回未格式化原文。
    """
    text = MSG.get(key, key)
    if kw:
        try:
            return text.format(**kw)
        except (KeyError, IndexError, ValueError):
            return text
    return text
