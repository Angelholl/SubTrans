"""
subtransjav-refine 命令行入口
"""

import argparse
import contextlib
import os
from typing import Any, cast


def build_parser():
    p = argparse.ArgumentParser(
        prog="subtransjav-refine",
        description="v2 两阶段字幕净语翻译流水线（阶段A 净语+翻译 → 阶段B 审校+抛光）")

    # ---- 输入源 ----
    grp_input = p.add_argument_group("输入源")
    grp_input.add_argument("-i", "--input", nargs="+", default=[],
                           action="extend",
                           help="输入字幕文件路径（SRT；ASS/SSA/VTT 自动转换为"
                                " SRT；可多个，可多次 -i 累积）")
    grp_input.add_argument("--input-dir", default="",
                           help="输入目录（扫描目录下所有 .srt 文件）")
    grp_input.add_argument("-r", "--recursive", action="store_true",
                           help="递归扫描子目录（需配合 --input-dir）")
    grp_input.add_argument("--filter-pattern", default="*.srt",
                           help="文件名过滤模式（默认 *.srt，支持 *.ja.srt 等）")
    grp_input.add_argument("--min-size", type=int, default=0,
                           help="最小文件大小（字节）")
    grp_input.add_argument("--max-size", type=int, default=0,
                           help="最大文件大小（字节，0=不限）")
    grp_input.add_argument("--min-date", default="",
                           help="最早修改日期（YYYY-MM-DD）")
    grp_input.add_argument("--max-date", default="",
                           help="最晚修改日期（YYYY-MM-DD）")
    grp_input.add_argument("--exclude", nargs="*", default=[],
                           help="排除的路径模式（如 *_raw.srt）")
    grp_input.add_argument("--asr-meta", default="",
                           help="上游 WhisperJAV 运行 manifest（可选，文件或目录）；"
                                "未给时自动发现 SRT 同目录同名旁车文件 whisperjav_run.json")
    grp_input.add_argument("--asr-telemetry", default="",
                           help="上游场景级 ASR 转写遥测 JSONL 路径（可选）；"
                                "未给时自动发现 SRT 同目录 raw_subs/ 下前缀匹配"
                                "的 <名>.asr_telemetry.jsonl")
    grp_input.add_argument("--media-path", default="",
                           help="显式指定媒体文件路径；缺省经上游 "
                                "whisperjav_run.json 自动发现")
    grp_input.add_argument("--adaptive-thresholds", action="store_true",
                           help="条目级阈值自适应（H4b，默认关闭）：场景低信任条目按收紧"
                                "参数执行闸门0（仅收紧删五类）；需上游 Balanced 模式的"
                                "asr_telemetry.jsonl，缺失时按默认阈值执行并在风险清单标注")

    p.add_argument("-o", "--output-dir", default="", help="输出目录（默认与输入同目录）")

    p.add_argument("--profile", choices=["local", "cloud"], default="local",
                   help="v2 兜底档位：local=strict(cleaner_rules+误译拦截) | cloud=lenient(仅通用校验)")

    for n, label in ((1, "阶段A"), (3, "阶段B")):
        g = p.add_argument_group(f"{label}（槽位 s{n}）")
        g.add_argument(f"--s{n}-provider",
                       choices=["deepseek", "zen", "lmstudio", "ollama",
                                "siliconflow", "custom"],
                       help=f"{label} 服务商（槽位 s{n}）")
        g.add_argument(f"--s{n}-model", help=f"{label} 模型名（槽位 s{n}）")
        g.add_argument(f"--s{n}-instructions", help=f"{label} 指令模板文件（槽位 s{n}）")

    p.add_argument("--templates-dir", default=".",
                   help="角色卡所在目录（默认在当前目录查找 角色-净语翻译.txt / 角色-审校抛光.txt 两张 v2 角色卡）")
    p.add_argument("--lmstudio-endpoint", default="http://localhost:1234/v1")
    p.add_argument("--ollama-endpoint", default="http://localhost:11434/v1")
    p.add_argument("--zen-endpoint", default="https://opencode.ai/zen/v1")
    p.add_argument("--siliconflow-endpoint", default="https://api.siliconflow.cn/v1")
    p.add_argument("--custom-endpoint", default="", help="自定义 OpenAI 兼容接口地址")

    p.add_argument("--batch-local", type=int, default=30, help="本地服务商每批条数（上限50）")
    p.add_argument("--batch-cloud", type=int, default=30, help="云端服务商每批条数")

    p.add_argument("--glossary", default="", help="词库 CSV 文件（原文,译文）")
    p.add_argument("--glossary-override", type=str, default="",
                   help="最高优先覆盖词表（同源词压过用户词表与学习词表）")
    p.add_argument("--no-gl1", action="store_true", help="词库不作用于阶段A（净语+翻译）")
    p.add_argument("--no-gl2", action="store_true", help="词库不作用于阶段B（审校+抛光）")

    # ---- 翻译记忆库 ----
    grp_tm = p.add_argument_group("翻译记忆库 (TM)")
    grp_tm.add_argument("--tm-db", default="",
                        help="翻译记忆库路径（默认 Temp/translation_memory/tm.db）")
    grp_tm.add_argument("--tm", action="store_true", default=True,
                        help="启用翻译记忆库（兼容保留：默认即启用，停用用 --no-tm）")
    grp_tm.add_argument("--no-tm", action="store_true",
                        help="禁用翻译记忆库")
    grp_tm.add_argument("--tm-threshold", type=float, default=0.85,
                        help="模糊匹配阈值 (0-1，默认 0.85)")
    grp_tm.add_argument("--no-tm-learn-gate", action="store_true",
                        help="关闭 TM 学习准入门槛（默认开启，用于 A/B 验证）")
    p.add_argument("--auto-glossary", action="store_true",
                   help="阶段A 完成后自动从翻译结果中提取术语到词库")
    # 学习闸开关（与 --auto-glossary 双闸门 AND，见 config.py 注释；
    # 影响学习行为 → 入 manifest 指纹）
    p.add_argument("--glossary-learn", action="store_true",
                   help="启用 learned 词库自学习路径（默认关闭，开启影响产物须过指纹）")
    p.add_argument("--glossary-conflict-block", action="store_true",
                   help="术语冲突条目禁止进入 TM 学习（默认仅观察）")
    p.add_argument("--cleaner-config", default=None,
                   help="自定义净语规则配置目录（默认使用内置模板）")
    grp_tm.add_argument("--tm-stats", action="store_true",
                        help="显示翻译记忆库统计后退出")
    grp_tm.add_argument("--tm-export", default="",
                        help="导出翻译记忆库为 CSV 后退出")
    grp_tm.add_argument("--tm-import", default="",
                        help="从 CSV 导入翻译记忆库后退出")
    grp_tm.add_argument("--tm-clear", action="store_true",
                        help="清空翻译记忆库后退出")

    # ---- 诊断 ----
    grp_diag = p.add_argument_group("诊断")
    grp_diag.add_argument("--where", action="store_true",
                          help="数据路径诊断：打印版本/运行形态/数据根及来源/"
                               "配置与翻译记忆库/密钥/旧数据根/迁移状态后退出"
                               "（纯只读，不创建任何目录）")
    grp_diag.add_argument("--import-legacy", metavar="DIR", default="",
                          help="从旧目录导入旧资产后退出：仅迁移 tm.db（含 "
                               "-wal/-shm 旁车）与 glossary.csv/"
                               "glossary_learned.csv；目标已存在先备份到数据根 "
                               "backups/，内容一致幂等跳过")

    # ---- 词典管理（2.1，D2026-0930-03 ②④）----
    grp_dict = p.add_argument_group("词典管理")
    grp_dict.add_argument("--dict-status", action="store_true",
                          help="查看日/中/英三词典状态（可用性/自定义路径/"
                               "已落位文件）后退出（只读零网络）")
    grp_dict.add_argument("--dict-download", choices=["sudachi"], default="",
                          help="下载词典到数据根 dict/ 后退出（显式动作；"
                               "SHA256 与源清单不符拒绝落位）")
    grp_dict.add_argument("--dict-from-file", metavar="FILE", default="",
                          help="离线导入：本地 wheel/dic 文件路径"
                               "（配合 --dict-download；wheel 过哈希校验）")
    grp_dict.add_argument("--dict-allow-unverified", action="store_true",
                          help="允许使用源清单中未核实哈希的下载源")

    p.add_argument("--deepseek-key", default="",
                   help="DeepSeek API Key（命令行传密钥会暴露在进程列表，建议改用环境变量 DEEPSEEK_API_KEY）")
    p.add_argument("--zen-key", default="",
                   help="Zen/OpenCode API Key（命令行传密钥会暴露在进程列表，建议改用环境变量 OPENCODE_API_KEY）")
    p.add_argument("--siliconflow-key", default="",
                   help="SiliconFlow API Key（命令行传密钥会暴露在进程列表，建议改用环境变量 SILICONFLOW_API_KEY）")
    p.add_argument("--custom-key", default="",
                   help="自定义服务商 API Key（命令行传密钥会暴露在进程列表，建议改用环境变量 CUSTOM_API_KEY）")

    p.add_argument("--fallback-local", action="store_true",
                   help="云端阶段故障(限流/宕机/持续解析失败)时自动切换本地模型接管")
    p.add_argument("--fallback-model", default="",
                   help="本地接管使用的 LM Studio 模型名（留空=不启用本地兜底；"
                        "需与 --fallback-local 同用且显式指定模型，否则校验报错）")

    grp_v2 = p.add_argument_group("v2 管线")
    grp_v2.add_argument("--v2-concurrency", type=int, default=1,
                        help="批间并发数（1-5，默认1为串行，越界自动钳制）")
    grp_v2.add_argument("--v2-ctx", type=int, default=None,
                        help="本地模型上下文窗口（不传=缺省 16384 通用保守值，"
                             "可经 config/user_settings.json 或环境变量 "
                             "SUBTRANSJAV_V2_CTX_LOCAL 覆盖；22272 为作者 16GB "
                             "单卡档案值示例，非缺省；LM Studio 手工改过 ctx 时"
                             "用本参数显式覆盖）")
    grp_v2.add_argument("--force", action="store_true",
                        help="忽略已有产物强制重跑（覆盖前自动备份）")
    grp_v2.add_argument("--resume", action="store_true",
                        help="断点续跑：校验输入/配置/词库/TM 指纹后复用上次中断任务已完成的阶段A产物")
    grp_v2.add_argument("--force-resume", action="store_true",
                        help="指纹校验不匹配时仍强制复用旧产物（隐含 --resume，无需单独传）")
    grp_v2.add_argument("--source-filter", choices=["strict", "default", "off"],
                        default="default",
                        help="闸门0 送翻前源侧幻觉检测档位：strict=严格(叠加启发式删除) | default=标准(仅明确幻觉删除) | off=关闭")
    grp_v2.add_argument("--source-lang", choices=["ja", "zh", "en"],
                        default="ja",
                        help="源语言（2.1 方向参数化，缺省 ja 全链零感知；"
                             "非缺省方向须配套模板卡 --s{n}-instructions）")
    grp_v2.add_argument("--target-lang", choices=["ja", "zh", "en"],
                        default="zh",
                        help="目标语言（2.1 方向参数化，缺省 zh 产物名"
                             "一字符不变；非缺省方向产物 _final_{lang}）")
    grp_v2.add_argument("--no-auto-synopsis", action="store_true",
                        help="关闭剧情自摘要（Beta：默认开启；摘要仅注入翻译提示词，不产生任何输出内容）")
    p.add_argument("--event-format", choices=["text", "ndjson"], default="text",
                   help="事件输出格式：text=人类可读（默认）| ndjson=结构化事件行（GUI 用，人类文本转 stderr）")
    p.add_argument("--heartbeat-interval", type=float, default=20.0,
                   help="ndjson 心跳间隔秒数（默认 20）")

    # ---- 行动层（D11 契约④⑤：基于导读清单的定点重翻执行器）----
    # 参数走 CLI 直连、不进 RefineConfig → 天然不进 manifest 指纹
    grp_action = p.add_argument_group("行动层（质量报告导读定点重翻）")
    grp_action.add_argument("--action-retranslate", default="",
                            help="行动层重翻：质量报告导读 json 清单路径"
                                 "（给定后进入执行器模式并早退，不跑 run_v2）")
    grp_action.add_argument("--entries", default="",
                            help="重翻条目选择：逗号分隔的单值与闭区间，"
                                 "如 3,7,12-15（缺省=全部 open 且有现译的条目）")
    grp_action.add_argument("--action-source", default="",
                            help="原始日文 SRT 路径（可选：按 timing 对齐恢复"
                                 "完整源文；缺省退化为导读摘录）")
    grp_action.add_argument("--action-model", default="",
                            help="重翻模型名（缺省用阶段B/槽 B 模型）")
    grp_action.add_argument("--action-sample", type=int, default=0,
                            help="只取选中条目的前 N 条（0=不限；供小样对比工作流）")
    grp_action.add_argument("--apply", action="store_true",
                            help="真正落盘改写终稿（缺省 dry-run：只打印计划，零写入）")

    grp_action.add_argument("--ai-analyze", default="",
                            help="AI 质量分析：质量报告 txt 路径"
                                 "（给定后进入分析模式并早退，不跑 run_v2；"
                                 "导读 json/术语冲突观察 CSV 同目录自动发现）")
    grp_action.add_argument("--ai-model", default="",
                            help="AI 分析模型名（缺省用阶段A/槽 A 模型）")
    # 2.6.0 批 3（D2026-1002-04-批3）：媒体重点对照的 ASR 指定（镜像
    # --ai-model 直连先例；不入 manifest 指纹——负向钉随批）
    grp_action.add_argument("--asr-model", default="",
                            help="媒体重点对照 ASR 模型名"
                                 "（缺省 large-v2，~/.cache/whisper 缓存）")
    grp_action.add_argument("--asr-python", default="",
                            help="本地 ASR 用的上游环境 Python 路径"
                                 "（缺省按 env/实测默认探测）")
    # 2.6.1 修订（D2026-1002-06，owner 反馈验证可选化）：媒体重点对照开关
    # 显式 CLI 层（镜像 v2_ctx/source_lang "缺省不赋"模式：不传=保 dataclass
    # 缺省 False 以让引擎页开关/user_settings/env 分层链生效；不入 manifest
    # 指纹——负向钉随批）
    grp_action.add_argument("--media-crosscheck-enabled", type=int,
                            choices=(0, 1), default=None,
                            help="媒体重点对照开关：1=开 0=关"
                                 "（缺省=配置分层链决定，默认关）")
    # 2.6.0 批 2 修订（D2026-1002-05，owner 2026-10-02）：跨片统计窗口
    # 三档（不入 manifest 指纹——负向钉随批）
    grp_action.add_argument("--tm-stats-window", default="30",
                            choices=["7", "30", "all"],
                            help="AI 分析跨片统计窗口：7/30 天或 all=永久"
                                 "（缺省 30）")

    p.add_argument("--verbose", action="store_true")
    p.add_argument("--clean-tmp-on-exit", action="store_true",
                   help="进程退出时自动清理 .refine_tmp 临时目录")
    p.add_argument("--dry-run", action="store_true", help="仅打印执行计划，不实际调用")
    return p


def _collect_input_files(args) -> list:
    """收集输入文件：来自 -i 和 --input-dir（含递归/过滤）。"""
    from .batch import find_srt_files
    files = list(args.input)

    if args.input_dir:
        # 批2 多格式导入（D2026-1003-05）范围外：--input-dir 目录扫描保持
        # *.srt 口径不变（批量收编面不放行 ASS/VTT，仅显式 -i 走转换步）。
        scanned = find_srt_files(
            directory=args.input_dir,
            recursive=args.recursive,
            pattern=args.filter_pattern,
            min_size=args.min_size,
            max_size=args.max_size,
            min_date=args.min_date,
            max_date=args.max_date,
            exclude_patterns=args.exclude or None,
        )
        if not scanned:
            print(f"⚠️ 目录下未找到匹配的 SRT 文件: {args.input_dir}")
        else:
            print(f"📂 目录扫描: {args.input_dir} -> {len(scanned)} 个文件")
            files.extend(scanned)

    # 去重（保持顺序）
    seen = set()
    deduped = []
    for f in files:
        af = os.path.abspath(f)
        if af not in seen:
            seen.add(af)
            deduped.append(af)
    return deduped


def _convert_inputs_or_exit(files: list) -> list:
    """批2 多格式导入接线（D2026-1003-05）：ASS/SSA/VTT → SRT 转换步。

    输入清单最终确定后、进管线前调用；无可转换文件时零打印零开销直接透传。
    显式 -i 无 .srt 后缀强制校验（config.validate 仅查文件存在），故转换层
    的 SUPPORTED_EXTS 即放行面；转换失败（编码不可识别/解析拒绝）打印用户
    可读错误后 exit 2，不带病进管线。
    """
    from .subtitle_convert import SUPPORTED_EXTS, ConvertError, convert_inputs

    n_conv = sum(1 for p in files
                 if os.path.splitext(p)[1].lower() in SUPPORTED_EXTS)
    if not n_conv:
        return files
    try:
        converted, warns = convert_inputs(files)
    except ConvertError as e:
        print(f"❌ 格式转换失败: {e}")
        raise SystemExit(2) from e
    for w in warns:
        print(f"⚠ {w}")
    print(f"🔄 格式转换: {n_conv} 个 ASS/VTT → SRT（{len(warns)} 警告）")
    return converted


def config_from_args(args):
    from .config import RefineConfig, StageConfig

    # v2 固定 4 槽：槽0（--s1-*）=阶段A 启用、槽2（--s3-*）=阶段B 启用；
    # 槽1/3 为占位禁用槽（v2 未用，保留 4 槽结构以兼容 TM by_stage 历史数据）
    stages = [
        StageConfig(0, True, args.s1_provider or "lmstudio",
                    args.s1_model or "", args.s1_instructions or ""),
        StageConfig(1, False, "deepseek", "", ""),
        StageConfig(2, True, args.s3_provider or "lmstudio",
                    args.s3_model or "", args.s3_instructions or ""),
        StageConfig(3, False, "lmstudio", "", ""),
    ]

    endpoints = {"lmstudio": args.lmstudio_endpoint,
                 "ollama": args.ollama_endpoint,
                 "zen": args.zen_endpoint,
                 "siliconflow": args.siliconflow_endpoint,
                 "custom": args.custom_endpoint}

    input_files = _collect_input_files(args)

    # 批2 多格式导入（D2026-1003-05）：转换后路径（*.conv.srt）作为管线
    # 输入与指纹口径；conv.srt 落输入同目录永久保留（画押④）
    input_files = _convert_inputs_or_exit(input_files)

    cfg = RefineConfig(
        inputs=input_files,
        output_dir=args.output_dir,
        stages=stages,
        templates_dir=args.templates_dir,
        batch_local=args.batch_local,
        batch_cloud=args.batch_cloud,
        glossary_path=args.glossary,
        glossary_override_path=args.glossary_override,
        apply_glossary_stage1=not args.no_gl1,
        apply_glossary_stage2=not args.no_gl2,
        api_key_deepseek=args.deepseek_key,
        api_key_zen=args.zen_key,
        api_key_siliconflow=args.siliconflow_key,
        api_key_custom=args.custom_key,
        endpoints=endpoints,
        fallback_local=args.fallback_local,
        fallback_model=args.fallback_model,
        verbose=args.verbose,
        tm_enabled=not args.no_tm,
        tm_db_path=args.tm_db,
        tm_threshold=args.tm_threshold,
        auto_glossary=args.auto_glossary,
        glossary_learn_enabled=args.glossary_learn,
        glossary_conflict_block=args.glossary_conflict_block,
        cleaner_config_dir=args.cleaner_config or "",
        v2_profile=args.profile,
        v2_concurrency=args.v2_concurrency,
        v2_source_filter=args.source_filter,
        auto_synopsis=not args.no_auto_synopsis,
        asr_meta=args.asr_meta,
        asr_telemetry=args.asr_telemetry,
        media_path=args.media_path,
        adaptive_thresholds=args.adaptive_thresholds,
        force=args.force,
        resume=args.resume,
        force_resume=args.force_resume,
        event_format=args.event_format,
        heartbeat_interval=args.heartbeat_interval,
        tm_learn_gate=not args.no_tm_learn_gate,
    )
    # A1 缺省重绑定：仅显式传 --v2-ctx 时赋值（构造后赋值天然处于分层链
    # 最高优先级）；不传时 dataclass 缺省 16384 与 user_settings/env 分层
    # 链在 RefineConfig.__post_init__ 内生效。
    if args.v2_ctx is not None:
        cfg.v2_ctx_local = args.v2_ctx
    # 方向参数化（D2026-0930-04 ①）：同 v2_ctx 模式——仅非缺省 CLI 值
    # 赋值（构造后赋值=user_settings/env 分层链之上的显式层）；缺省值
    # 不赋，保 dataclass 缺省以让分层链生效。
    if args.source_lang != "ja":
        cfg.source_lang = args.source_lang
    if args.target_lang != "zh":
        cfg.target_lang = args.target_lang
    # 2.6.1 修订（D2026-1002-06）：媒体重点对照开关——仅显式传参时赋值
    #（同 v2_ctx 模式；缺省不赋保分层链生效）。
    if getattr(args, "media_crosscheck_enabled", None) is not None:
        cfg.media_crosscheck_enabled = bool(args.media_crosscheck_enabled)
    return cfg


def print_plan(cfg):
    from .batch import scan_summary
    from .config import PROVIDER_TEXT
    print("📋 执行计划：")
    print(f"   输入: {len(cfg.inputs)} 个文件")
    summary = scan_summary(cfg.inputs)
    if summary["total_size_mb"] > 0:
        print(f"   总大小: {summary['total_size_mb']} MB")
    if len(summary["dirs"]) > 1:
        print(f"   涉及目录: {len(summary['dirs'])} 个")
    for p in cfg.inputs[:10]:
        print(f"     - {os.path.basename(p)}")
    if len(cfg.inputs) > 10:
        print(f"     ... 共 {len(cfg.inputs)} 个文件")
    print(f"   输出目录: {cfg.output_dir or '(与输入同目录)'}")
    errs = cfg.validate()
    print(f"   管线: v2 两阶段（净语+翻译 / 审校+抛光）| 兜底档位: {cfg.v2_profile}")
    for tag, slot in (("阶段A 净语+翻译", 0), ("阶段B 审校+抛光", 2)):
        s = cfg.stages[slot]
        m = cfg.resolve_model(s) or "(默认)"
        print(f"   ▶ {tag}  [{PROVIDER_TEXT.get(s.provider, s.provider)}] {m}")
    if cfg.glossary_path:
        scope = [n for n, on in (("阶段A", cfg.apply_glossary_stage1),
                                 ("阶段B", cfg.apply_glossary_stage2)) if on]
        print(f"   词库: {cfg.glossary_path} -> {','.join(scope) or '无'}")
    if cfg.tm_enabled:
        print(f"   翻译记忆库: {'启用' if cfg.tm_enabled else '禁用'}"
              f" (阈值 {cfg.tm_threshold})")
    if errs:
        print("❌ 配置问题:")
        for e in errs:
            print("   -", e)
    return not errs


def _handle_tm_commands(args):
    """处理翻译记忆库管理命令（执行后退出）。返回 True 表示已处理。"""
    import sys as _sys

    from .tm import TranslationMemory

    # Windows GBK 终端兼容：确保 UTF-8 输出
    # （windowed 回退链：GUI exe 无 subtrans-cli.exe 时经 --subtrans-cli 进入，
    # stdout 可能为无 encoding 属性的 NullWriter——getattr 容错，不炸）
    _out_enc = getattr(_sys.stdout, "encoding", None)
    if _out_enc and _out_enc.lower() not in ("utf-8", "utf8"):
        with contextlib.suppress(Exception):
            cast(Any, _sys.stdout).reconfigure(encoding="utf-8",
                                               errors="replace")

    # 2.1 方向参数化（D2026-0930-05 批内缺陷修复）：实例缺省方向接
    # args（tm 管理命令与主解析共用 namespace，字段有白名单缺省
    # ja/zh，直接用即可）——修复非缺省方向任务学出的 TM 行落缺省列
    tm = (TranslationMemory(args.tm_db, source_lang=args.source_lang,
                            target_lang=args.target_lang) if args.tm_db
          else TranslationMemory(source_lang=args.source_lang,
                                 target_lang=args.target_lang))
    try:
        if args.tm_stats:
            s = tm.stats()
            print("翻译记忆库统计：")
            print(f"   总条目: {s['total']}")
            print(f"   总命中: {s['total_hits']}")
            for stage, cnt in sorted(s.get("by_stage", {}).items()):
                stage_names = {0: "阶段1(净语)", 1: "阶段2(翻译)",
                               2: "阶段3(审核)", 3: "阶段4(抛光)"}
                print(f"   {stage_names.get(stage, f'阶段{stage}')}: {cnt} 条")
            print(f"   数据库: {s['db_path']}")
            return True
        if args.tm_export:
            tm.export_csv(args.tm_export)
            print(f"已导出到: {args.tm_export}")
            return True
        if args.tm_import:
            n = tm.import_csv(args.tm_import)
            print(f"已导入 {n} 条新记录")
            return True
        if args.tm_clear:
            tm.clear()
            print("翻译记忆库已清空")
            return True
    finally:
        tm.close()
    return False


def _fts5_probe() -> bool:
    """探测当前解释器 sqlite3 是否支持 FTS5 全文搜索（只读零副作用）。

    2.6.4 批1 冻结包 FTS5 探测载体（D2026-1003-05 A1）：在内存库上建
    fts5 虚拟表即可验证，不落盘、不触碰任何真实数据库。
    """
    import sqlite3

    try:
        con = sqlite3.connect(":memory:")
        try:
            con.execute("CREATE VIRTUAL TABLE _fts5_probe USING fts5(x)")
        finally:
            con.close()
        return True
    except Exception:
        return False


def _print_where() -> str:
    """--where 数据路径诊断（D2026-0929-07 点 3）：一次报全，全程只读零副作用。

    所有路径均做不落盘的拼接展示（不走 _default_tm_path 等带 makedirs
    副作用的函数），绝不创建任何目录。
    """
    import os as _os

    from subtransjav import paths
    from subtransjav.__version__ import __version_display__

    from . import glossary_conflict, secrets, tm
    from .config import CONFIG_DIR

    run_mode = "frozen 打包" if paths.is_frozen() else "pip 源码"
    source_map = {
        "env": "环境变量显式指定",
        "frozen-default": "frozen 默认（%LOCALAPPDATA%）",
        "legacy": "仓库根（传统）",
    }
    state_map = {"migrated": "已迁移", "not-migrated": "未迁移"}
    source = paths.data_root_source()
    state = paths.migration_state()
    data_root = paths.data_root()

    if paths.is_frozen():
        old_tm_db = data_root / "Temp" / "translation_memory" / "tm.db"
        old_label = "旧数据根"
    else:
        old_tm_db = paths.app_root() / "Temp" / "translation_memory" / "tm.db"
        old_label = "旧数据根（仓库根）"
    old_exists = "存在" if old_tm_db.exists() else "不存在"

    if paths.is_frozen():
        migration_note = (
            f"迁移在 EXE 首次启动时自动执行；当前状态：{state_map[state]}"
        )
    else:
        migration_note = "完整迁移随 EXE 首发，当前版本不迁移"

    lines = [
        f"程序版本: {__version_display__}",
        f"运行形态: {run_mode}",
        f"数据根: {data_root}（来源: {source_map[source]}）",
        f"配置目录: {CONFIG_DIR}",
        f"翻译记忆库路径: {_os.path.join(tm._DEFAULT_TM_DIR, 'tm.db')}",
        f"FTS5 全文搜索: {'可用' if _fts5_probe() else '不可用'}",
        f"术语冲突观察路径: {glossary_conflict.default_watch_path()}",
        f"DPAPI 密钥位置: {secrets.get_store_path()}",
        f"{old_label} TM 库: {old_tm_db}（{old_exists}）",
        f"迁移状态: {state_map[state]}（{migration_note}）",
    ]
    return "\n".join(lines)


def _cmd_dict_status() -> int:
    """--dict-status：三词典状态（只读零网络；jieba 自检会触发首次
    初始化与 cache 写盘（%TEMP%））。"""
    from .dict_manager import dict_status
    st = dict_status()
    print(f"数据根词典目录: {st['dict_dir']}")
    for kind, info in st["dicts"].items():
        line = f"  {kind}: {'可用' if info['available'] else '不可用'}"
        if info.get("custom_path"):
            line += f" | 自定义词典: {info['custom_path']}（优先于数据根下载词典）"
        if info.get("files"):
            line += f" | 文件: {', '.join(info['files'])}"
        print(line)
    # jieba 独立自检行（D2026-1004-01）：真跑分词，供打包 smoke 做成功
    # 语义断言；任何异常只报 FAIL 不抛——探测命令保持返回 0。
    try:
        import jieba
        toks = list(jieba.cut("字幕分词自检"))
        print(f"jieba 分词自检: OK（{len(toks)} tokens）")
    except Exception as e:  # noqa: BLE001 - 自检失败不抛，保持 rc=0
        print(f"jieba 分词自检: FAIL: {e}")
    return 0


def _cmd_dict_download(kind: str, from_file: str = "",
                       allow_unverified: bool = False) -> int:
    """--dict-download：显式下载/离线导入词典（两类失败分开报错）。"""
    from .dict_manager import DictChecksumError, DictDownloadError, download_dict
    try:
        path = download_dict(kind, allow_unverified=allow_unverified,
                             local_file=from_file)
    except DictDownloadError as e:
        print(f"❌ 词典下载失败（网络/源不可达）: {e}")
        return 1
    except DictChecksumError as e:
        print(f"❌ 词典校验失败（SHA256 不符或清单非法，已拒绝落位）: {e}")
        return 1
    print(f"✅ 词典已就位: {path}")
    return 0


def main(argv=None):
    # stdio 加固（同 tools/guard_banned_paths.py）：argparse 在 parse 时才打印
    # 中文 help，stdout 为管道且 locale 码页过窄（CI windows cp1252 实测回归）
    # 会 UnicodeEncodeError → 退出 1；只放宽 errors 不挂 encoding——本地 cp936
    # 控制台中文照常，窄码页降级 \uXXXX 转义不崩；流不可 reconfigure 时静默跳过。
    import sys as _sys
    for _stream in (_sys.stdout, _sys.stderr):
        if _stream is None or not hasattr(_stream, "reconfigure"):
            continue
        with contextlib.suppress(OSError, ValueError):
            _stream.reconfigure(errors="backslashreplace")

    # 模型缓存重定向到仓库 models/ 目录（不占 C 盘）
    from subtransjav.utils.model_cache import apply_model_cache_env
    apply_model_cache_env()

    args = build_parser().parse_args(argv)

    # 数据路径诊断（独立早退：先于 config_from_args，纯诊断不建配置不建目录）
    if getattr(args, "where", False):
        print(_print_where())
        return 0

    # ---- 旧资产手动导入（--import-legacy）：--where 同层早退，不进 run_v2；
    #      全容错降级在 import_legacy 内部完成（errors 不抛出），恒返回 0 ----
    legacy_dir = getattr(args, "import_legacy", "") or ""
    if legacy_dir:
        from subtransjav.data_migration import import_legacy
        import_legacy(legacy_dir)
        return 0

    # ---- 词典管理命令（2.1）：--where 同层早退，不进 run_v2、不触发迁移 ----
    if getattr(args, "dict_status", False):
        return _cmd_dict_status()
    if getattr(args, "dict_download", ""):
        return _cmd_dict_download(
            args.dict_download,
            from_file=getattr(args, "dict_from_file", "") or "",
            allow_unverified=getattr(args, "dict_allow_unverified", False))

    # ---- EXE 首发数据迁移插桩（D2026-0929-05/07/08）：位于 --where 只读
    #      早退之后、config_from_args 之前；全容错，任何异常不阻塞 CLI ----
    try:
        from subtransjav.data_migration import ensure_migrated
        ensure_migrated(verbose=True)
    except Exception as e:  # noqa: BLE001 - 全容错桩：迁移失败不阻塞启动
        print(f"⚠️ [迁移] 数据迁移检查失败（忽略，继续启动）: {e}")

    # TM 管理命令（独立于翻译流程）
    if _handle_tm_commands(args):
        return

    cfg = config_from_args(args)

    # ---- 行动层重翻执行器（D11 契约④⑤）：早退分流，同 _handle_tm_commands
    #      形态——不进 run_v2；退出码 0=成功/1=全败/2=entries 非法/3=部分降级 ----
    if args.action_retranslate:
        from .action_retranslate import run_action_retranslate
        return run_action_retranslate(cfg, args)

    # ---- AI 质量分析（D2026-0929）：早退分流，同行动层形态——不进
    #      run_v2；退出码 0=建议件已落盘 / 1=前置失败或执行异常 ----
    if getattr(args, "ai_analyze", ""):
        from .quality_advisor import run_ai_analyze
        return run_ai_analyze(cfg, args)

    # ------------------------------------------------------------------
    # 运行日志：全量落盘（Logs/M-D.txt，同日追加时间）+ 7 天自动清理
    # ------------------------------------------------------------------
    import sys as _sys
    import time as _time

    from .config import LOGS_DIR
    from .runlog import TeeWriter, archive_error_log, cleanup_old_logs, errors_dir, next_log_path, write_summary

    cleanup_old_logs(LOGS_DIR)
    log_path = next_log_path(LOGS_DIR)
    log_file = open(log_path, 'w', encoding='utf-8', buffering=1)  # noqa: SIM115  主流程长生命周期日志句柄，末尾统一 close；行缓冲保证硬杀时已写行落盘
    shared_counts = {'error': 0, 'warn': 0, 'failover': 0}
    tee_out = TeeWriter(_sys.stdout, log_file, shared_counts)
    tee_err = TeeWriter(_sys.stderr, log_file, shared_counts)
    start_time = _time.time()
    status = "⚠️ 中断"
    err_msg = ""
    exit_code = 0

    _orig_stdout, _orig_stderr = _sys.stdout, _sys.stderr
    real_stdout = _orig_stdout    # ndjson 事件流的真实 stdout（Tee 之前捕获）
    _sys.stdout = tee_out
    _sys.stderr = tee_err
    if cfg.event_format == "ndjson":
        # 结构化事件独占 stdout：人类可读文本全部转走 stderr（Tee 照常进日志）
        _sys.stdout = _sys.stderr
    try:
        if args.clean_tmp_on_exit:
            import atexit

            from .pipeline_support import cleanup_created_tmp_dirs
            atexit.register(cleanup_created_tmp_dirs)

        if args.dry_run:
            ok = print_plan(cfg)
            status = "✅ 成功（dry-run）" if ok else "❌ 失败（dry-run 配置错误）"
            exit_code = 0 if ok else 2
        else:
            summary: dict[str, Any] = {}
            try:
                from .pipeline_v2 import run_v2
                out = run_v2(cfg, summary_sink=summary,
                             event_stream=(real_stdout if cfg.event_format == "ndjson"
                                           else None))
                for _line in summary.get("summary_lines") or []:
                    print(_line)
                n_ok = summary.get("files_ok", 0)
                n_deg = summary.get("files_degraded", 0)
                n_fail = summary.get("files_failed", 0)
                if n_deg or n_fail or summary.get("risk_count", 0):
                    status = (f"⚠️ 部分降级（成功{n_ok}/降级{n_deg}/失败{n_fail}）")
                    exit_code = 3
                else:
                    status = "✅ 成功"
                    exit_code = 0
                print(f"\n✅ [refine-v2] 最终输出: {out}")
            except KeyboardInterrupt:
                status = "⚠️ 用户中断"
                exit_code = 130
            except Exception as e:
                status = "❌ 失败"
                err_msg = str(e)
                exit_code = 1
                print(f"\n❌ [refine] 执行失败：{e}")
                for _line in summary.get("summary_lines") or []:
                    print(_line)
    finally:
        _sys.stdout, _sys.stderr = _orig_stdout, _orig_stderr
        # D1：ndjson 模式下 stdout 是结构化事件流（GUI 逐行 json.loads），
        # 此处收尾的人类可读页脚必须改走 stderr；text 模式保持 stdout 原行为。
        _echo = (lambda msg: print(msg, file=_sys.stderr)) \
            if cfg.event_format == "ndjson" else print
        try:
            tee_out.close()
            tee_err.close()
            write_summary(log_file, status, _time.time() - start_time,
                          len(cfg.inputs), shared_counts, log_path)
        finally:
            log_file.close()
        # 失败/中断的运行归档到 Errors/，并按同一保留策略清理
        archived = archive_error_log(log_path, status, LOGS_DIR)
        if archived:
            cleanup_old_logs(errors_dir(LOGS_DIR))
            _echo(f"❗ 错误日志已归档: {archived}")

        _echo(f"\n📄 运行日志已保存: {log_path}")
        if err_msg:
            _echo(f"   {err_msg}")
        _sys.exit(exit_code)


if __name__ == "__main__":
    main()
