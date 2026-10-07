"""
SubTransJAV PyWebView API

Backend API for the standalone SRT translation GUI.
Maintains the thin wrapper pattern - delegates work to the
``subtransjav.refine.cli`` subprocess and streams its output.
"""

import base64
import contextlib
import hashlib
import json
import logging
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import webview
from webview import FileDialog

from subtransjav import paths
from subtransjav.refine.fs_utils import BACKUP_SUFFIX  # noqa: E402  共享基底层
from subtransjav.utils.process_manager import (
    PSUTIL_AVAILABLE,
    spawn_refine_cli,
    terminate_process_tree,
    terminate_process_tree_robust,
)
from subtransjav.utils.subprocess_flags import (
    CREATE_NO_WINDOW,  # windowed 防黑框单一来源（spawn_refine_cli 内部 + 本模块直接调用共用）
)

from . import user_dirs  # noqa: E402  用户目录持久登记（批1a 件1；security 保持纯函数，由本模块装载传入）
from .event_stream import (  # noqa: E402  webview-free 可测模块
    HEARTBEAT_STALE_S_DEFAULT,
    EventStreamParser,
    format_event_line,
    resume_state_for_path,
)
from .strings import msg  # noqa: E402  用户可见文案唯一中文来源

# Project root (subtransjav/webview_gui/api.py -> project root)
# 数据路径统一收口到 subtransjav.paths：源码=仓库根；frozen=用户数据根
REPO_ROOT = paths.app_root()

# ---------------------------------------------------------------------------
# 会话内用户选择的路径登记（信任边界：scan_resume_states 只处理这些路径）
# 由受信入口登记：文件对话框 / 文件夹扫描 / 拖放（main.py on_drop_event）。
# ---------------------------------------------------------------------------
SESSION_SELECTED_PATHS: set[str] = set()


def register_session_paths(paths) -> None:
    """登记用户通过受信入口选择的路径（拖放入口由 main.py 调用）。"""
    for p in paths or []:
        if isinstance(p, str) and p:
            try:
                SESSION_SELECTED_PATHS.add(str(Path(p).resolve()))
            except (OSError, ValueError):
                continue


# ---------------------------------------------------------------------------
# 词典下载会话注册表（2.7.3 件⑤，HRO-1 同 kind 后端真互斥）
# kind → {"session": str(uuid4), "stop": threading.Event, "thread": Thread}，
# threading.Lock 保护全部读写。单一活跃下载者语义：同 kind 旧线程存活即
# 拒绝新下载（终态快照会话门控与临时件隔离随之天然满足）；stop 只作用于
# 当前注册表条目（互斥保证无旧会话残留可误停）；线程收口仅当注册表条目
# 仍属本会话才清除（防新会话条目被旧线程误删）。
# ---------------------------------------------------------------------------
_DICT_DL_REGISTRY: dict[str, dict[str, Any]] = {}
_DICT_DL_LOCK = threading.Lock()


def _dict_download_worker(kind: str, source: str, session: str,
                          stop_event: threading.Event) -> None:
    """后台下载线程目标（2.7.3 件⑤）：调 dict 层 download_dict。

    DictDownloadStopped 静默收口（stopped 快照已在 dict 层检查点收口时
    写好，api 层绝不乐观代写——HRO-1.3）；其余异常的 failed 快照亦已在
    dict 层落库，此处仅记日志防线程裸崩。finally 持锁清除条目前校验
    session 归属（期间同 kind 可能已被新会话登记，旧线程不得误删）。"""
    from subtransjav.refine.dict_manager import (
        DictDownloadStopped,
        download_dict,
    )
    try:
        download_dict(kind, source=source, stop_event=stop_event)
    except DictDownloadStopped:
        pass
    except Exception:  # noqa: BLE001 - 后台线程兜底：failed 快照已落，勿裸崩
        _log_exc("refine_dict_download(worker)")
    finally:
        with _DICT_DL_LOCK:
            entry = _DICT_DL_REGISTRY.get(kind)
            if entry is not None and entry["session"] == session:
                del _DICT_DL_REGISTRY[kind]


def _review_save_allowed(path: str) -> str:
    """审计①收口（批1a 件5）：校对保存/另存的放行裁决单一入口。

    放行集 = 动态根（home ∪ 数据根 ∪ 安装根，_resolve_safe_path 现读）
    ∪ 持久登记目录（user_dirs.json registered_dirs，经 extra_roots 传入）
    ∪ 本会话受信入口登记路径（对话框/拖放——覆盖任意盘已登记文件，
    如从 E:\\ 载入后原盘保存）。
    返回归一化后的绝对路径；越界抛 ValueError。
    载入侧（refine_review_load_srt）保持既有语义不动。
    """
    try:
        return str(_resolve_safe_path(
            path, extra_roots=user_dirs.get_registered_dirs()))
    except ValueError:
        resolved = str(Path(path).resolve())
        if resolved in SESSION_SELECTED_PATHS:
            return resolved
        raise


def _ensure_template_dir(templates_dir) -> str:
    """角色卡目录守卫（反路径穿越加固；批1a 件3 持久化收口）。

    缺省目录解析（不传目录时）：持久登记 templates_dir（user_dirs.json）
    → 服务端默认模板目录（数据根 config/templates）。
    显式传入目录时仅放行三类（其余前端任意路径一律拒绝，阻断被攻陷
    前端借角色卡读写接口越锚访问用户主目录下的同名文件）：
      1. 服务端默认模板目录；
      2. 本会话经受信入口（原生文件夹对话框/拖放）登记的目录（重启失效）；
      3. 持久登记目录（user_dirs.json registered_dirs，重启仍生效）。
    且必须通过 _resolve_safe_path 锚点校验（动态根 ∪ 持久登记 extra_roots）。
    """
    try:
        from subtransjav.refine.config import default_templates_dir
        default_dir = str(_resolve_safe_path(default_templates_dir()))
    except Exception:
        default_dir = ""
    persisted = ""
    try:
        t = user_dirs.get_templates_dir()
        if t:
            persisted = str(_resolve_safe_path(
                t, extra_roots=user_dirs.get_registered_dirs()))
    except Exception:
        persisted = ""
    if not templates_dir:
        # 缺省目录：持久登记的 templates_dir 优先，其次数据根 config/templates
        return persisted or default_dir
    resolved = str(_resolve_safe_path(
        templates_dir, extra_roots=user_dirs.get_registered_dirs()))
    for cand in (default_dir, persisted):
        if cand and os.path.normcase(resolved) == os.path.normcase(cand):
            return resolved
    allowed = {os.path.normcase(p) for p in SESSION_SELECTED_PATHS}
    allowed |= {os.path.normcase(p) for p in user_dirs.get_registered_dirs()}
    if os.path.normcase(resolved) not in allowed:
        raise ValueError(
            msg("template_dir_not_allowed", path=resolved))
    return resolved


def _safe_template_basename(filename) -> str | None:
    """角色卡**文件名参数位**守卫（D2026-0930-07-追加1 必改②/⑤）。

    仅接受"纯文件名"：无目录成分、无路径分隔符、非空且 .txt 后缀。
    含任何穿越/嵌套/绝对路径形态（``../../x.txt``、``/abs/x.txt``、
    ``sub/x.txt``）一律返回 None，由调用方拒绝——目录位守卫
    （_ensure_template_dir）之外补齐文件名参数位的穿越防线。
    """
    raw = str(filename or "").strip()
    if not raw or raw != os.path.basename(raw):
        return None
    if "/" in raw or "\\" in raw or raw in (".", ".."):
        return None
    if not raw.lower().endswith(".txt"):
        return None
    return raw


def _template_file_in_dir(d: str, base: str) -> str | None:
    """join 后 resolve 复核：结果必须仍落在守卫目录内（双保险）。

    返回绝对路径；越出目录（平台别名/符号链接漂移等异常形态）返回 None。
    """
    p = os.path.join(d, base)
    try:
        real_p = os.path.realpath(p)
        real_d = os.path.realpath(d)
    except OSError:
        return None
    if os.path.normcase(os.path.dirname(real_p)) != os.path.normcase(real_d):
        return None
    return p


# Security guards live in a webview-free module so they are testable on CI
from .security import (  # noqa: E402
    _resolve_safe_path,
    _validate_user_directory,
    is_safe_url_scheme,
)

# ---------------------------------------------------------------------------
# Observability: module-level logger writing to Logs/gui.log
# ---------------------------------------------------------------------------
_log = logging.getLogger("subtransjav.gui")
if not _log.handlers:
    _log_dir = REPO_ROOT / "Logs"
    _log_dir.mkdir(parents=True, exist_ok=True)
    _fh = logging.FileHandler(
        _log_dir / "gui.log", encoding="utf-8",
    )
    _fh.setFormatter(
        logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
    )
    _fh.setLevel(logging.INFO)
    _log.addHandler(_fh)
    _log.setLevel(logging.INFO)


def _log_exc(context: str) -> None:
    """Log current exception with traceback at ERROR level."""
    _log.exception(context)


def _get_documents_dir() -> Path:
    """Platform-neutral Documents directory resolution."""
    home = Path.home()
    docs = home / "Documents"
    return docs if docs.exists() else home


def _compute_default_output_dir() -> Path:
    """Default output dir: <Documents>/SubTrans/output."""
    base = _get_documents_dir()
    if base.name.lower() != "documents" or not base.exists():
        base = Path.home()
    p = base / "SubTrans" / "output"
    p.mkdir(parents=True, exist_ok=True)
    return p


DEFAULT_OUTPUT = _compute_default_output_dir()


def _refine_error_tip(e: Exception) -> str:
    """refine 测试失败的中文诊断提示"""
    s = str(e)
    if "RegionError" in s or "not available in your country" in s:
        return msg("tip_region_blocked")
    if "429" in s or "RateLimit" in s or "FreeUsageLimit" in s:
        return msg("tip_rate_limited")
    if "unavailable" in s or "Upstream" in s:
        return msg("tip_upstream_down")
    if "api_key" in s.lower() or "401" in s:
        return msg("tip_invalid_key")
    return msg("tip_check_key_network")


def _build_refine_args(options: dict[str, Any]) -> list[str]:
    """构建净语翻译 CLI 参数（v2 两阶段管线）。

    options 键：
      inputs: List[str]                输入 SRT 列表
      output_dir: str                  输出目录（'source' 哨兵=随输入）
      profile: str                     兜底档位 local|cloud
      s1_provider / s1_model           阶段A 服务商与模型（槽位0）
      s3_provider / s3_model           阶段B 服务商与模型（槽位2）
      templates_dir: str               角色卡目录
      glossary: str                    词库 CSV 路径
      apply_glossary_stage1/2: bool
      batch_local / batch_cloud: int
      v2_concurrency: int              批间并发数（1-5，缺省1）
      v2_ctx: int                      本地模型上下文窗口（显式对齐引擎与管线两侧；
                                       缺省不传=后端缺省 16384（A1 缺省重绑定，
                                       D2026-0927-01）；22272 为作者 16GB 档案值示例，非缺省）
      lmstudio_endpoint / zen_endpoint / custom_endpoint: str
      deepseek_key / zen_key / custom_key: str
      source_filter: str                闸门0 源侧幻觉检测档位 strict|default|off（缺省 default 不传参）
      auto_synopsis: bool               剧情自摘要（默认 True；显式 False 才传 --no-auto-synopsis）
      adaptive_thresholds: bool         条目级阈值自适应（H4b，默认 False；勾选才传 --adaptive-thresholds）
      source_lang / target_lang: str    翻译方向（2.1 D2026-0930-04 定案① GUI 补齐；
                                        缺省 ja/zh 不传参=CLI 缺省字节不变；非缺省才传）
      s1_instructions / s3_instructions: str
                                        非缺省方向配套的阶段A/B 指令卡路径
                                        （有值才传 --s{n}-instructions；缺卡由 CLI validate 报错）
      dry_run: bool                     试运行（仅生成执行计划，不调用模型）
      verbose: bool
    """
    # 纯 CLI 参数（不含解释器前缀）：解释器形态统一由
    # process_manager.spawn_refine_cli 拼装（frozen → --subtrans-cli，
    # 源码 → -u -m subtransjav.refine.cli，D2026-0929-06 修订③）
    args: list[str] = []

    inputs = options.get("inputs") or []
    for p in inputs:
        # Guard against filenames starting with '-' being parsed as CLI flags
        if p.startswith("-"):
            args.append(f"--input={p}")
        else:
            args.extend(["-i", p])

    out_dir = options.get("output_dir", "")
    if out_dir and out_dir.lower().strip() != "source":
        args.extend(["-o", out_dir])

    # v2 两阶段管线（阶段A→s1 槽位、阶段B→s3 槽位）
    if options.get("profile"):
        args.extend(["--profile", str(options["profile"])])

    for n in (1, 3):
        pv = options.get(f"s{n}_provider")
        if pv:
            args.extend([f"--s{n}-provider", str(pv)])
        mv = options.get(f"s{n}_model")
        if mv:
            args.extend([f"--s{n}-model", str(mv)])

    # 2.1 翻译方向（D2026-0930-04 定案① GUI 补齐）：仅非缺省方向传参
    # （缺省 ja→zh 与 CLI 缺省一致，不产生旗标=字节不变）；非缺省方向
    # 须配套全部启用阶段的指令卡，缺卡由 CLI validate 前置报错
    src_lang = options.get("source_lang")
    tgt_lang = options.get("target_lang")
    if src_lang and src_lang != "ja":
        args.extend(["--source-lang", str(src_lang)])
    if tgt_lang and tgt_lang != "zh":
        args.extend(["--target-lang", str(tgt_lang)])
    if options.get("s1_instructions"):
        args.extend(["--s1-instructions", str(options["s1_instructions"])])
    if options.get("s3_instructions"):
        args.extend(["--s3-instructions", str(options["s3_instructions"])])

    if options.get("templates_dir"):
        args.extend(["--templates-dir", options["templates_dir"]])
    if options.get("glossary"):
        args.extend(["--glossary", options["glossary"]])
    if options.get("apply_glossary_stage1") is False:
        args.append("--no-gl1")
    if options.get("apply_glossary_stage2") is False:
        args.append("--no-gl2")

    bl = options.get("batch_local")
    if bl:
        args.extend(["--batch-local", str(bl)])
    bc = options.get("batch_cloud")
    if bc:
        args.extend(["--batch-cloud", str(bc)])

    # 批间并发数（缺省1；钳制上限经 config 单一来源，CLI 端 __post_init__ 会再钳制一次）
    try:
        n_conc = int(options.get("v2_concurrency") or 1)
    except (TypeError, ValueError):
        n_conc = 1
    from subtransjav.refine.config import resolve_tunable
    n_max = int(resolve_tunable("v2_concurrency_max"))
    args.extend(["--v2-concurrency", str(max(1, min(n_max, n_conc)))])

    # 本地模型上下文窗口：GUI 显式传值即对齐引擎与管线两侧（引擎加载 -c
    # 由管线内 ensure_lmstudio_model 派生自同一配置，见 utils/lmstudio.py）
    try:
        n_ctx = int(options.get("v2_ctx") or 0)
    except (TypeError, ValueError):
        n_ctx = 0
    if n_ctx > 0:
        args.extend(["--v2-ctx", str(n_ctx)])

    for key, flag in (("lmstudio_endpoint", "--lmstudio-endpoint"),
                      ("ollama_endpoint", "--ollama-endpoint"),
                      ("zen_endpoint", "--zen-endpoint"),
                      ("siliconflow_endpoint", "--siliconflow-endpoint"),
                      ("custom_endpoint", "--custom-endpoint")):
        v = options.get(key)
        if v:
            args.extend([flag, str(v)])

    # API keys are NOT passed via CLI args (visible in process list);
    # they are injected into the subprocess env by start_translation().

    # API 密钥不再通过命令行参数传递（进程列表可见），
    # 由 start_translation() 注入子进程环境变量。

    if options.get("fallback_local"):
        args.append("--fallback-local")
    if options.get("fallback_model"):
        args.extend(["--fallback-model", str(options["fallback_model"])])

    # 自定义净语规则配置目录
    if options.get("cleaner_config_dir"):
        args.extend(["--cleaner-config", str(options["cleaner_config_dir"])])

    if options.get("verbose"):
        args.append("--verbose")

    # 闸门0 源侧幻觉检测档位（仅非默认值时传递，choices 与 cli.py 保持一致）
    sf = options.get("source_filter")
    if sf and sf != "default":
        args.extend(["--source-filter", str(sf)])

    # 剧情自摘要（默认开启；仅显式关闭时传反转开关）
    if options.get("auto_synopsis") is False:
        args.append("--no-auto-synopsis")

    # H4b 条目级阈值自适应（默认关闭；显式勾选才传旗标）
    if options.get("adaptive_thresholds"):
        args.append("--adaptive-thresholds")

    # 试运行：仅生成执行计划，不调用模型、不产出字幕
    if options.get("dry_run"):
        args.append("--dry-run")

    # 批量处理参数
    if options.get("input_dir"):
        args.extend(["--input-dir", str(options["input_dir"])])
    if options.get("recursive"):
        args.append("-r")
    if options.get("filter_pattern"):
        args.extend(["--filter-pattern", str(options["filter_pattern"])])
    if options.get("min_size"):
        args.extend(["--min-size", str(options["min_size"])])
    if options.get("max_size"):
        args.extend(["--max-size", str(options["max_size"])])

    # 翻译记忆库参数
    if options.get("no_tm"):
        args.append("--no-tm")
    if options.get("tm_db"):
        args.extend(["--tm-db", str(options["tm_db"])])
    if options.get("tm_threshold"):
        args.extend(["--tm-threshold", str(options["tm_threshold"])])

    # 断点恢复（复用已完成阶段；仅当用户勾选时传递）
    if options.get("resume"):
        args.append("--resume")

    # 覆盖已完成产物：仅 GUI 确认框确认后由前端显式传入 force=True 时追加
    # （D2026-0925-01 D6 终选：force 仅作为确认路径可达）
    if options.get("force"):
        args.append("--force")

    # 强制断点恢复：指纹校验不匹配仍复用旧产物；force_resume 隐含 resume
    # 由 RefineConfig.__post_init__ 不变式保证，无需在此重复拼 --resume
    if options.get("force_resume"):
        args.append("--force-resume")

    # 学习闸开关（manifest 钉定的三个影响学习行为的开关之二，入产物指纹；
    # tm_learn_gate 默认 True 与 TM 勾选语义重叠，GUI 不设开关，
    # 保持 CLI --no-tm-learn-gate 通道）
    if options.get("glossary_learn"):
        # 双闸门 AND 语义：GUI 勾选「学习词库」= 两闸同开（--glossary-learn
        # 外层闸 + --auto-glossary 内层闸）；不勾 = 两闸皆缺省 False，默认
        # 行为零变化。auto_glossary 刻意不入产物指纹（见 manifest.py）。
        args.append("--glossary-learn")
        args.append("--auto-glossary")
    if options.get("glossary_conflict_block"):
        args.append("--glossary-conflict-block")

    # NDJSON 结构化事件流（GUI 侧解析进度/风险/心跳；同仓 CLI 固定支持）
    args.extend(["--event-format", "ndjson"])

    return args


# ---------------------------------------------------------------------------
# 校对页转码/时长工具（2.6.1 批 2a D2026-1002-09；模块级纯函数便于直测）
# ---------------------------------------------------------------------------

# 审计③d（批4 D2026-1002-12）：per-media 转码在飞集合（normcase 绝对路径
# 为键）。running 标志前置的 ffprobe 探测/缓存校验耗时窗口内双击可双线程
# 写同一 out_path——in-flight 集合在 _review_lock 内 check-and-add 原子
# 判定，第二次进入幂等返回"转码中"，worker finally 完成后移除。
_REVIEW_TRANSCODE_INFLIGHT: set[str] = set()


def _transcode_sync(ffmpeg_path: str, media_path: str, out_path: str,
                    timeout_s: float, progress_cb=None) -> tuple[bool, str]:
    """同步转码主体（后台线程包壳调用；list-args 禁 shell）。

    - ``-progress pipe:1`` 逐行解析 out_time_ms（ffmpeg 语义实为微秒）；
    - progress_cb(seconds) 回报已转码媒体秒数（供调用方折算百分比）；
    - 总时长超 timeout_s 杀进程（proc.kill）返回失败，可重试；
    - 审计③（D2026-1002-12）：finally 语义——成功才保留产物，kill/
      超时/异常/非零退出路径一律 unlink 半截产物（24h sweep 只清旧
      文件，兜不住"半截件当 cache 复用"）；
    - 返回 ``(success, error)``。
    """
    cmd = [ffmpeg_path, "-y", "-i", media_path,
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
           "-c:a", "aac", "-progress", "pipe:1", out_path]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE,
                                stderr=subprocess.DEVNULL, shell=False,
                                creationflags=CREATE_NO_WINDOW)  # windowed 防黑框（批0）
    except OSError as e:
        return False, str(e)
    deadline = time.monotonic() + max(1.0, timeout_s)
    success = False
    try:
        assert proc.stdout is not None
        for raw in proc.stdout:
            if time.monotonic() > deadline:
                proc.kill()
                return False, "transcode timeout"
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("out_time_ms=") and progress_cb is not None:
                try:
                    progress_cb(max(0.0, float(line.split("=", 1)[1]) / 1_000_000.0))
                except ValueError:
                    continue
        code = proc.wait(timeout=30)
        if code == 0 and os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
            success = True
            return True, ""
        return False, f"ffmpeg exit {code}"
    except Exception as e:  # noqa: BLE001  兜底杀进程后如实回报
        proc.kill()
        return False, str(e)
    finally:
        if not success:
            # 产物本不存在/被占用：清理语义已达成，不再扩散异常
            with contextlib.suppress(OSError):
                os.unlink(out_path)


def _codec_direct(ext: str, codecs: dict, exts, vids, auds) -> bool:
    """播放矩阵参数化判定（批 3 技术债 e）。

    direct = 容器后缀 ∈ exts ∧ 视频 codec ∈ vids ∧ 音频 codec ∈ auds；
    两套常量集（audio preview / review probe）各自传参保留语义差异。
    """
    return (str(ext or "").lower() in set(exts)
            and str(codecs.get("video") or "") in set(vids)
            and str(codecs.get("audio") or "") in set(auds))


# 2.7.4 件B（D2026-1007-02）：试听媒体推断专用剥链后缀表。在既有闭集
# （".ja.whisperjav"/".whisperjav"/".ja"，即 asr_meta._STEM_STRIP_SUFFIXES）
# 基础上插入 ".merged"——owner merged 工作流产物 X.ja.merged.whisperjav
# 经共享剥链停于 X.ja.merged，须再剥一层才可达视频 root X。
_PREVIEW_STEM_SUFFIXES = (".ja.whisperjav", ".whisperjav", ".merged", ".ja")


def _preview_stem_candidates(stem: str) -> list[str]:
    """试听媒体推断专用：由导读 stem 生成 leveled 候选 stem 序列。

    只服务 _infer_preview_media 的候选生成——**不动**
    asr_meta.strip_stem_suffixes 共享剥链（其闭集被 manifest 配对/指纹
    等消费方依赖，插入 ".merged" 会波及面失控，故在此独立成表）。

    生成规则（确定性：按 (剥的层数, 生成顺序) 排列，BFS 逐层）：
      - level 0 = 原 stem（与既有 strip_stem_suffixes 全剥结果一致，
        保证老路径零回退）；
      - 每层对当前候选从右剥「一个」后缀：按 _PREVIEW_STEM_SUFFIXES
        表序尝试取首个命中（大小写不敏感，对齐共享剥链 endswith 语义），
        守卫 len(候选) > len(后缀)（对齐 strip_stem_suffixes，剥后非空）；
      - 已见过的候选不重复入队（防 ".ja.ja" 类分支重复/回环）。
    """
    start = str(stem or "")
    seen = {start}
    ordered = [start]
    frontier = [start]
    while frontier:
        nxt: list[str] = []
        for cur in frontier:
            low = cur.lower()
            for suf in _PREVIEW_STEM_SUFFIXES:
                if low.endswith(suf) and len(cur) > len(suf):
                    stripped = cur[:-len(suf)]
                    if stripped not in seen:
                        seen.add(stripped)
                        ordered.append(stripped)
                        nxt.append(stripped)
                    break   # 每候选每层只剥一个后缀（表序首个命中）
        frontier = nxt
    return ordered


def _ms_to_srt_time(ms: int) -> str:
    """毫秒 → SRT 时间戳 ``HH:MM:SS,mmm``（cleaner_rules ms 原生重建 timing）。"""
    ms = max(0, int(ms))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms3 = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms3:03d}"


def _write_srt_atomic(path: str, text: str) -> None:
    """原子写 SRT 文本（批 3 技术债 a：薄壳委托 refine.fs_utils，行为等价：
    mkstemp 同目录 + fsync + os.replace，防中断半截产物）。"""
    from subtransjav.refine.fs_utils import _atomic_write_text as _atomic
    _atomic(path, text, suffix=".srt.tmp")


def _review_sanitize_block_text(text: str) -> str:
    """块内文本写入端规范化（批4 D2026-1002-12 审计②）。

    SRT 中空行是块分隔符语义：编辑框引入的块内空行/连续空白行原样写出，
    下次 parse_srt 会把后续文本裂成残块（内容静默丢失且随 .bak.srt 滚动
    覆盖固化）。保存前统一换行符、把连续空白行压成单换行、掐头去尾，
    保证写出的必是标准 SRT 块结构（序号连续/块间恰好一个空行/无尾部
    多余空行由 save_srt 的组装方式原生保证），往返解析不漂移。
    """
    normalized = str(text or "").replace("\r\n", "\n").replace("\r", "\n")
    return re.sub(r'\n\s*\n+', '\n', normalized).strip()


def _load_dict_dir_override() -> None:
    """装载持久化词典目录注入 dict_manager（批1b 件1；追补裁定后为冗余兜底）。

    跨进程单源已由 dict_manager.effective_dict_dir() 直读 user_dirs.json
    承担（GUI/CLI/--dict-download 统一生效）；本注入保两点：①pick 后
    JSON 落盘失败时 GUI 会话内仍即时生效（降级语义与 register_dir 一致）；
    ②get_custom_dir()/状态显示保留用户选取的原始路径（JSON 存储为
    resolve+normcase 归一化值）。依赖方向：refine 不得反向 import
    webview_gui，装载由 api 层做；CLI 进程不经此装载，走 JSON 直读。
    装载失败静默（回落数据根默认）。
    """
    try:
        from subtransjav.refine import dict_manager as dm
        dm.set_custom_dir(user_dirs.get_dict_dir())
    except Exception:  # noqa: BLE001 - 全容错：注入失败不阻断 GUI 启动
        _log_exc("_load_dict_dir_override")


class TranslateAPI:
    """
    API class exposed to JavaScript via PyWebView.

    All public methods are callable from JavaScript via:
        pywebview.api.method_name(args)
    """

    def __init__(self):
        """Initialize API state."""
        self.process: subprocess.Popen | None = None

        # 退出时清理 refine 临时目录并终止残留子进程
        import atexit
        atexit.register(self._on_exit_cleanup)
        self._refine_tmp_dirs: list[str] = []

        # Lock for _translate_process access (GUI thread vs reader thread)
        self._translate_lock = threading.Lock()

        # Default output directory (ensure it exists and is normalized)
        self.default_output = str(_compute_default_output_dir())

        # 批1b 件1：启动时装载持久化词典目录（user_dirs.dict_dir）注入生效
        _load_dict_dir_override()

    # ========================================================================
    # Version / misc
    # ========================================================================

    def get_version(self) -> dict[str, Any]:
        """Get application version information."""
        try:
            from subtransjav.__version__ import (
                __version__,
                __version_display__,
                __version_info__,
            )
            return {
                "success": True,
                "version": __version_display__,
                "version_pep440": __version__,
                "version_info": __version_info__,
            }
        except ImportError:
            return {
                "success": False,
                "version": "unknown",
                "message": msg("version_load_failed")
            }

    def get_system_status(self) -> dict[str, Any]:
        """Get system status including optional features like grammar hints."""
        features: dict[str, dict[str, Any]] = {}
        status = {
            "success": True,
            "features": features
        }

        # Check SudachiPy availability for grammar hints
        try:
            from subtransjav.refine.grammar_hint import is_grammar_hint_available
            features["grammar_hints"] = {
                "available": is_grammar_hint_available(),
                "description": msg("grammar_hints_available")
            }
        except ImportError:
            features["grammar_hints"] = {
                "available": False,
                "description": msg("grammar_hints_unavailable")
            }

        return status

    def open_url(self, url: str) -> dict[str, Any]:
        """Open a URL in the system browser."""
        try:
            if not is_safe_url_scheme(url):
                return {"success": False, "error": msg("url_scheme_unsupported")}
            import webbrowser
            webbrowser.open(url)
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ========================================================================
    # File dialogs
    # ========================================================================

    def select_folder(self) -> dict[str, Any]:
        """Open native folder dialog to select a folder."""
        windows = webview.windows
        if not windows:
            return {"success": False, "message": msg("no_active_window")}

        result = windows[0].create_file_dialog(FileDialog.FOLDER)
        if result and len(result) > 0:
            register_session_paths(result)  # 受信入口：文件夹对话框选取即登记
            return {"success": True, "path": result[0]}
        return {"success": False, "message": msg("no_folder_selected")}

    def select_output_directory(self) -> dict[str, Any]:
        """Open native folder dialog to select output directory."""
        return self.select_folder()

    @staticmethod
    def _open_file_dialog(type_keys, save=False, default_name=None,
                          allow_multiple=False):
        """文件对话框收敛（批 3 技术债 g）：统一 OPEN/SAVE 分支。

        返回用户选择结果（OPEN=list / SAVE=str），取消或无窗口返回 None；
        无窗口分支仍由各调用方先行判定（保留 no_active_window 语义）。
        """
        windows = webview.windows
        if not windows:
            return None
        if save:
            kwargs: dict[str, Any] = {"file_types": list(type_keys)}
            if default_name:
                kwargs["save_filename"] = default_name
            return windows[0].create_file_dialog(webview.SAVE_DIALOG, **kwargs)
        return windows[0].create_file_dialog(
            webview.OPEN_DIALOG, allow_multiple=allow_multiple,
            file_types=list(type_keys))

    def select_srt_files(self) -> dict[str, Any]:
        """Open file dialog to select SRT files for translation."""
        windows = webview.windows
        if not windows:
            return {"success": False, "message": msg("no_active_window")}

        # 批2 多格式导入（D2026-1003-05）：对话框放行 ASS/SSA/VTT，
        # 转换在 refine 管线入口（subtitle_convert.convert_inputs）完成
        result = self._open_file_dialog(
            (msg("file_type_srt"), msg("file_type_subtitle"),
             msg("file_type_all")),
            allow_multiple=True)

        if result and len(result) > 0:
            register_session_paths(result)
            return {"success": True, "paths": list(result)}
        return {"success": False, "message": msg("no_files_selected")}

    def select_srt_folder(self) -> dict[str, Any]:
        """Open folder dialog and find .srt files in the selected folder."""
        windows = webview.windows
        if not windows:
            return {"success": False, "message": msg("no_active_window")}

        result = windows[0].create_file_dialog(FileDialog.FOLDER)
        if result and len(result) > 0:
            folder = Path(result[0])
            # 批2 多格式导入范围外：目录收编保持 *.srt 口径（与 CLI
            # --input-dir 同口径，ASS/VTT 仅显式选择走转换步）
            # C1（D2026-1002-10）：排除校对页备份件 *.bak.srt
            candidates = [f for f in folder.glob("*.srt")
                          if not f.name.endswith(BACKUP_SUFFIX)]
            # 2.7.3 件④（D2026-1005）：流水线中间稿/终稿（pass1/pass2、
            # _refine_、_final_）不是可收编的翻译输入，智能过滤跳过；
            # merged 产成品不排（见 refine.batch.is_pipeline_intermediate）
            from subtransjav.refine.batch import is_pipeline_intermediate
            keep = [f for f in candidates if not is_pipeline_intermediate(f.name)]
            skipped = [f.name for f in candidates if is_pipeline_intermediate(f.name)]
            if keep:
                srt_files = sorted(str(f) for f in keep)
                register_session_paths(srt_files)
                return {"success": True, "paths": srt_files, "folder": result[0],
                        "skipped": sorted(skipped),
                        "skipped_count": len(skipped)}
            if candidates:
                # 2.7.3 件④：目录确有 .srt 但全是流水线产物 → 如实诊断
                # （优先于 ass 系分支；bak 排除仍优先，bak-only 走原 no_srt 通道）
                return {"success": False,
                        "message": msg("folder_all_skipped_pipeline"),
                        "skipped": sorted(skipped)}
            # 2.7.2 件1（D2026-1005-02）：目录无 .srt 但检测到 ASS/SSA/VTT 时
            # 给出针对性提示（目录收编口径仍为 *.srt，不放开；复用 message 通道）
            subtitle_files = [f for f in folder.glob("*")
                              if f.suffix.lower() in (".ass", ".ssa", ".vtt")]
            if subtitle_files:
                return {"success": False,
                        "message": msg("no_srt_but_subtitle_in_folder")}
            return {"success": False, "message": msg("no_srt_in_folder")}
        return {"success": False, "message": msg("no_folder_selected")}

    def scan_srt_folder(self, folder: str, recursive: bool = True,
                        pattern: str = "*.srt", min_size: int = 0,
                        max_size: int = 0, min_date: str = "",
                        max_date: str = "",
                        exclude: list[str] | None = None) -> dict[str, Any]:
        """扫描目录下的 SRT 文件（支持递归/过滤）。

        Args:
            folder:   根目录路径
            recursive: 是否递归子目录
            pattern:   文件名 glob 模式
            min_size:  最小文件大小（字节）
            max_size:  最大文件大小（字节，0=不限）
            min_date:  最早修改日期（YYYY-MM-DD）
            max_date:  最晚修改日期（YYYY-MM-DD）
            exclude:   排除的路径模式列表
        """
        try:
            from subtransjav.refine.batch import find_srt_files, is_pipeline_intermediate, scan_summary
            folder = _validate_user_directory(folder)
            files = find_srt_files(
                directory=folder,
                recursive=recursive,
                pattern=pattern,
                min_size=min_size,
                max_size=max_size,
                min_date=min_date,
                max_date=max_date,
                exclude_patterns=exclude,
            )
            summary = scan_summary(files)
            # 2.7.3 件④：流水线中间稿/终稿计数增量（既有 summary 键一字不动）
            summary["skipped_count"] = sum(
                1 for f in files if is_pipeline_intermediate(os.path.basename(f)))
            register_session_paths(files)
            return {
                "success": True,
                "paths": files,
                "summary": summary,
            }
        except FileNotFoundError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def open_output_folder(self, path: str, create: bool = True) -> dict[str, Any]:
        """Open a folder in file explorer.

        Args:
            path:   Directory path to open.
            create: If True (default), create the directory when it doesn't exist
                    (useful for output dirs). If False, return an error when the
                    directory doesn't exist (useful for browsing existing dirs).
        """
        try:
            path = _validate_user_directory(path)
            folder = Path(path)
            if create:
                folder.mkdir(parents=True, exist_ok=True)
            elif not folder.is_dir():
                return {"success": False,
                        "message": msg("dir_not_exist", path=folder)}

            if sys.platform.startswith("win"):
                os.startfile(str(folder))
            elif sys.platform == "darwin":
                # POSIX 分支（Windows 走 os.startfile）：常量在 POSIX 解析为 0，
                # 补 flag 仅为全模块 AST 钉测统一（tests/test_subprocess_no_window.py）。
                subprocess.run(["open", str(folder)],
                               creationflags=CREATE_NO_WINDOW)
            else:
                subprocess.run(["xdg-open", str(folder)],
                               creationflags=CREATE_NO_WINDOW)

            return {"success": True, "message": msg("folder_opened")}
        except Exception as e:
            return {"success": False, "message": msg("cannot_open_folder", e=e)}

    def get_default_output_dir(self) -> str:
        """Get the default output directory path."""
        self.default_output = str(_compute_default_output_dir())
        return self.default_output

    # ========================================================================
    # Translation process management
    # ========================================================================

    def _init_translation_state(self):
        """Initialize translation-specific state if not already done."""
        if not hasattr(self, '_translate_process'):
            self._translate_process: subprocess.Popen | None = None
            self._translate_status = "idle"
            self._translate_error: str | None = None
            self._translate_log_queue: queue.Queue = queue.Queue()
            self._translate_thread: threading.Thread | None = None
            self._translate_files_total = 0
            self._translate_current_file = None
            self._translate_lines_total = 0
            self._translate_lines_done = 0
            self._translate_current_stage = ""
            # NDJSON 事件流解析器（start_translation 时重建）
            self._translate_parser: EventStreamParser | None = None

    def start_translation(self, options: dict[str, Any]) -> dict[str, Any]:
        """
        Start the refine translation subprocess.

        Args:
            options: Options collected by buildRefineOptionsV2() in app.js.
        """
        # D2026-0925-01 D6：终稿覆盖确认。与 resume_state_for_path 同源判定
        # （completed = {stem}_final_cn.srt 存在）；任一输入已完成且未带
        # force=True 时不启动进程，返回结构化 needs_confirm 由前端弹确认框。
        if not options.get("force"):
            existing = []
            for _p in (options.get("inputs") or []):
                try:
                    _st = resume_state_for_path(str(_p))
                except Exception:
                    continue
                if _st.get("state") == "completed":
                    from subtransjav.refine.v2_outputs import final_stem
                    existing.append(f"{final_stem(_st['stem'])}.srt")
            if existing:
                return {
                    "success": False,
                    "needs_confirm": True,
                    "existing": existing,
                }

        self._init_translation_state()

        with self._translate_lock:
            if self._translate_process is not None:
                return {"success": False, "error": msg("translation_in_progress")}
            # Sentinel: mark "starting" to block double-start while Popen runs
            #（True 哨兵仅作占位，消费侧均先判 `is True`；cast 仅为类型清零）
            self._translate_process = cast(subprocess.Popen, True)

        while True:
            try:
                self._translate_log_queue.get_nowait()
            except queue.Empty:
                break

        self._translate_files_total = 0
        self._translate_current_file = None
        self._translate_lines_total = 0
        self._translate_lines_done = 0
        self._translate_current_stage = ""
        # 每次启动重建事件流解析器（进度/风险/心跳/摘要从零聚合）；
        # 心跳超时阈值走配置分层（默认 < 用户文件 < 环境变量）
        try:
            from subtransjav.refine.config import resolve_tunable
            _stale_s = float(resolve_tunable("heartbeat_stale_s"))
        except Exception:
            _stale_s = HEARTBEAT_STALE_S_DEFAULT
        self._translate_parser = EventStreamParser(heartbeat_stale_s=_stale_s)

        try:
            args = _build_refine_args(options)

            # 记录 refine 临时目录，供程序退出时清理
            try:
                from subtransjav.refine.pipeline_support import refine_tmp_dir, strip_lang_suffix
                for _p in (options.get("inputs") or []):
                    _ip = Path(_p).resolve()
                    _stem = strip_lang_suffix(_ip.stem)
                    _td = refine_tmp_dir(str(_ip), _stem)
                    if _td not in self._refine_tmp_dirs:
                        self._refine_tmp_dirs.append(_td)
            except Exception:
                pass

            # Unbuffered + UTF-8（PYTHONUTF8/PYTHONIOENCODING 已由
            # spawn_refine_cli 统一注入，这里只补差异项）(#190)
            env_extra: dict[str, str] = {"PYTHONUNBUFFERED": "1"}

            # Inject API keys into subprocess env (not CLI args) for security.
            # Variable names match those checked by RefineConfig.resolve_api_key().
            _key_env_map = {
                "deepseek_key": "DEEPSEEK_API_KEY",
                "zen_key": "OPENCODE_API_KEY",
                "siliconflow_key": "SILICONFLOW_API_KEY",
                "custom_key": "CUSTOM_API_KEY",
            }
            for opt_key, env_var in _key_env_map.items():
                v = options.get(opt_key)
                if v:
                    env_extra[env_var] = str(v)

            # stdout/stderr 分离：stdout 逐行喂 NDJSON 事件解析器，
            # stderr 原样入日志队列；各自独立线程排空管道防死锁（#190）
            proc = cast(subprocess.Popen, spawn_refine_cli(
                args,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=1,
                universal_newlines=True,
                encoding="utf-8",
                errors="replace",
                cwd=str(REPO_ROOT),
                env_extra=env_extra,
            ))

            with self._translate_lock:
                self._translate_process = proc

            self._translate_status = "running"
            self._translate_error = None

            # 两个守护 reader 线程：stdout→解析器 feed + 人类可读行入日志队列；
            # stderr→原样入日志队列
            self._translate_thread = threading.Thread(
                target=self._pump_stdout, args=(proc,),
                name="gui-stdout-reader", daemon=True
            )
            self._translate_thread.start()
            threading.Thread(
                target=self._pump_stderr, args=(proc,),
                name="gui-stderr-reader", daemon=True
            ).start()

            return {
                "success": True,
                "message": msg("translation_started",
                               n=len(options.get('inputs', []))),
                "pid": proc.pid
            }

        except Exception as e:
            _log_exc("start_translation")
            with self._translate_lock:
                proc = self._translate_process
                self._translate_process = None
            if proc is not None and proc is not True and hasattr(proc, 'kill'):
                with contextlib.suppress(Exception):
                    proc.kill()
            self._translate_status = "error"
            return {"success": False, "error": str(e)}

    def _pump_stdout(self, proc: subprocess.Popen):
        """stdout 守护线程：NDJSON 事件解析 + 人类可读行入日志队列。

        - 事件行格式化成 "[事件] 阶段B 批次 3/10" 风格；format 结果为 None
          的事件（心跳等）丢弃不入队，防裸 JSON 漏进日志队列；
        - 非事件行原样入日志队列，并由解析器的遗留兼容层提取进度/错误；
        - 每条入队行 strip 行尾换行后全量落盘 gui.log（D2026-1006-01 D4：
          全量保留；心跳行不入队故也不落盘）。
        """
        parser = self._translate_parser or EventStreamParser()
        try:
            for line in proc.stdout:
                try:
                    event = parser.feed(line)
                except Exception:
                    _log_exc("_pump_stdout.feed")
                    event = None
                if event is not None:
                    text = format_event_line(event)
                    if text is not None:
                        _log.info(text.rstrip("\n"))
                        self._translate_log_queue.put(text)
                else:
                    _log.info(line.rstrip("\n"))
                    self._translate_log_queue.put(line)
        except Exception as e:
            _log_exc("_pump_stdout")
            self._translate_log_queue.put(f"\n[ERROR] {e}\n")
        finally:
            with contextlib.suppress(Exception):
                proc.wait()

    def _pump_stderr(self, proc: subprocess.Popen):
        """stderr 守护线程：原样入日志队列。"""
        try:
            for line in proc.stderr:
                self._translate_log_queue.put(line)
        except Exception as e:
            _log_exc("_pump_stderr")
            self._translate_log_queue.put(f"\n[ERROR] {e}\n")

    def cancel_translation(self) -> dict[str, Any]:
        """Cancel running translation process."""
        self._init_translation_state()

        with self._translate_lock:
            proc = self._translate_process
            if proc is None:
                return {"success": False, "error": msg("no_translation_in_progress")}
            # Sentinel (True) means start_translation is still launching — cannot cancel yet
            if proc is True:
                return {"success": False, "error": msg("translation_still_starting")}

        try:
            if PSUTIL_AVAILABLE:
                result = terminate_process_tree(proc.pid)
                ok = bool(result["success"])
            else:
                # v1.3.2 task4：无 psutil 回退升级为整树击杀（原为单杀）
                ok = terminate_process_tree_robust(proc.pid)
            if not ok:
                proc.terminate()

            # Always wait for process to exit to avoid zombie processes
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

            self._translate_status = "cancelled"
            self._translate_log_queue.put(
                f"\n[CANCELLED] {msg('log_cancelled')}\n")
            with self._translate_lock:
                self._translate_process = None

            return {"success": True, "message": msg("translation_cancelled")}
        except Exception as e:
            _log_exc("cancel_translation")
            return {"success": False, "error": str(e)}

    def get_translation_status(self) -> dict[str, Any]:
        """Get current translation status."""
        self._init_translation_state()

        with self._translate_lock:
            proc = self._translate_process

        # Guard against sentinel (True) from start_translation
        if proc is True:
            proc = None

        parser = getattr(self, '_translate_parser', None)
        snap = parser.snapshot() if parser is not None else {}
        warning_level = None

        if proc is not None:
            poll = proc.poll()
            if poll is not None:
                exit_code = poll
                with self._translate_lock:
                    if self._translate_process is proc:
                        self._translate_process = None

                risk_count = int(snap.get('risk_count') or 0)
                majority = bool(snap.get('untranslated_majority'))

                if self._translate_status != "cancelled":
                    if exit_code == 3:
                        # CLI 约定：exit 3 = 完成但存在严重质量风险
                        self._translate_status = "completed"
                        warning_level = "critical"
                        self._translate_log_queue.put(
                            f"\n[WARN] {msg('warn_exit3')}\n")
                    elif exit_code == 0:
                        self._translate_status = "completed"
                        if majority:
                            warning_level = "critical"
                            self._translate_log_queue.put(
                                f"\n[WARN] {msg('warn_majority')}\n")
                        elif risk_count > 0:
                            warning_level = "warning"
                            self._translate_log_queue.put(
                                f"\n[WARN] {msg('warn_risks', n=risk_count)}\n")
                        else:
                            self._translate_log_queue.put(
                                f"\n[SUCCESS] {msg('log_success')}\n")
                    else:
                        self._translate_status = "error"
                        if not self._translate_error:
                            self._translate_error = (
                                snap.get('error')
                                or msg("process_exit_code", code=exit_code))
                        self._translate_log_queue.put(
                            f"\n[ERROR] {msg('log_exit_code', code=exit_code)}\n")

        risk_count = int(snap.get('risk_count') or 0)
        majority = bool(snap.get('untranslated_majority'))
        # 批 8a（D2026-1006-01）：files 口径改由 snapshot 的 per-file 状态
        # 驱动——completed 数 done 态文件，total 取 max(已知文件数,
        # task_started 上报的期望总数)；旧 _translate_files_completed
        # 字段（恒 0 死字段）删除。
        files_status = dict(snap.get('files') or {})
        files_total_expected = int(snap.get('files_total_expected') or 0)

        return {
            "status": self._translate_status,
            "progress": int(snap.get('progress') or 0),
            "current_file": snap.get('current_file'),
            "files_completed": sum(
                1 for st in files_status.values() if st == "done"),
            "files_total": max(len(files_status), files_total_expected),
            "has_logs": not self._translate_log_queue.empty(),
            "error": self._translate_error or snap.get('error'),
            # --- NDJSON 事件流扩展键（保留全部旧键） ---
            "current_stage": snap.get('stage'),
            "risks": snap.get('risks', []),
            "risk_count": risk_count,
            "untranslated_majority": majority,
            "heartbeat_age": snap.get('heartbeat_age'),
            "heartbeat_stale_s": float(
                snap.get('heartbeat_stale_s') or HEARTBEAT_STALE_S_DEFAULT),
            # 后端已算好的心跳超时判定（app.js 单点消费；旧 snapshot 缺键时 False）
            "heartbeat_stale": bool(snap.get('heartbeat_stale', False)),
            "degraded": risk_count > 0 or majority,
            "warning_level": warning_level,
            "ndjson_mode": bool(snap.get('ndjson_mode')),
            "files_status": files_status,
            "task_summary": snap.get('task_summary'),
        }

    def get_translation_logs(self) -> list[str]:
        """Get new translation log lines."""
        self._init_translation_state()

        logs = []
        while not self._translate_log_queue.empty():
            try:
                logs.append(self._translate_log_queue.get_nowait())
            except queue.Empty:
                break
        return logs

    def scan_resume_states(self, paths: list[str]) -> list[dict[str, Any]]:
        """对用户本次会话选择的输入 srt 计算断点恢复状态。

        - 有 ``{stem}_final_cn.srt`` → completed（整文件已完成）
        - 有 ``{stem}_manifest.json`` 无终稿 → resumable（可复用已完成阶段）
        - 否则 → none

        信任边界：仅处理通过受信入口（文件对话框/文件夹扫描/拖放）登记过的
        路径，未登记的路径直接跳过，不做任意路径解析。
        """
        results: list[dict[str, Any]] = []
        for p in paths or []:
            if not isinstance(p, str) or not p:
                continue
            try:
                resolved = str(Path(p).resolve())
            except (OSError, ValueError):
                continue
            if resolved not in SESSION_SELECTED_PATHS:
                continue
            try:
                results.append(resume_state_for_path(resolved))
            except Exception:
                continue
        return results

    # ================================================================
    # Refine UI 辅助 API（净语翻译两阶段界面）
    # ================================================================
    def refine_default_paths(self) -> dict[str, Any]:
        """返回词库/角色卡目录的默认路径。

        角色卡目录解析（批1a 件3）：持久登记 templates_dir（user_dirs.json）
        → 服务端默认目录（数据根 config/templates）。
        """
        try:
            from subtransjav.refine.config import default_glossary_path, default_templates_dir
            try:
                persisted = user_dirs.get_templates_dir() or ""
            except Exception:
                persisted = ""
            return {
                "success": True,
                "templates_dir": persisted or default_templates_dir(),
                "glossary_path": default_glossary_path(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def refine_get_data_root(self) -> dict[str, Any]:
        """返回当前数据保存根目录与来源（供高级参数页「数据保存目录」区块）。"""
        try:
            return {
                "success": True,
                "data_root": str(paths.data_root()),
                "source": paths.data_root_source(),
                "pointer": paths.get_data_root_pointer(),
                "is_frozen": paths.is_frozen(),
            }
        except Exception as e:
            _log_exc("refine_get_data_root")
            return {"success": False, "error": str(e)}

    def refine_dict_status(self) -> dict[str, Any]:
        """三词典状态（2.1 引擎页词典管理三区块；只读零网络）。"""
        try:
            from subtransjav.refine.dict_manager import dict_status
            return {"success": True, **dict_status()}
        except Exception as e:
            _log_exc("refine_dict_status")
            return {"success": False, "error": str(e)}

    def refine_dict_download(self, kind: str, source: str = "auto") -> dict[str, Any]:
        """显式下载词典（2.1；2.7.3 件⑤ 改会话制：立即返回不阻塞 jsapi 线程）。

        2.7.3 件⑤（词典下载停止按钮）：下载改后台线程执行，本方法校验
        kind 后登记会话（uuid4 + stop Event + Thread）并立即返回
        ``{"success": True, "session_id": ...}``；进度仍经
        refine_dict_download_progress 1s 轮询，终态新增 stopped（用户停止）。
        网络失败与校验失败由 dict 层写 failed 快照（download_dict 语义不变）。

        HRO-1 同 kind 后端真互斥：持锁查注册表，同 kind 旧线程存活即拒绝
        （dict_download_busy 人话文案）——单一活跃下载者，终态快照会话门控
        与临时件隔离随之天然满足。登记与 ``worker.start()`` 同锁原子
        （code-review 触碰式修复①：start 留在锁外时，登记后 start 前的
        微窗口内同 kind 二次调用可见 ``is_alive()==False`` 覆盖条目致双
        下载，破坏单一活跃下载者不变量）。source（2.6.3 批B，
        D2026-1003-06 条件②①）∈ {auto, official, mirror}，非法值由
        download_dict 按 auto 处理。
        """
        if kind not in ("sudachi", "sudachi_full"):
            # 2.5.0 修复A：kind 兼容三联——硬拒放开为双词典 kind 白名单
            return {"success": False,
                    "error": msg("dict_kind_unsupported")}
        with _DICT_DL_LOCK:
            entry = _DICT_DL_REGISTRY.get(kind)
            if entry is not None and entry["thread"].is_alive():
                # HRO-1：同 kind 单一活跃下载者，重入显式拒绝（不发新线程）
                return {"success": False, "message": msg("dict_download_busy")}
            session = str(uuid.uuid4())
            stop_event = threading.Event()
            worker = threading.Thread(
                target=_dict_download_worker,
                args=(kind, source, session, stop_event),
                name=f"dict-dl-{kind}",
                daemon=True)
            _DICT_DL_REGISTRY[kind] = {"session": session,
                                       "stop": stop_event,
                                       "thread": worker}
            # 同锁内启动（修复①）：start() 返回时线程必已 alive
            # （Thread.start 语义保证），锁外观察者只会看到活跃条目
            worker.start()
        return {"success": True, "session_id": session}

    def refine_dict_download_stop(self, kind: str) -> dict[str, Any]:
        """请求停止当前词典下载（2.7.3 件⑤；协作式——置位 stop Event）。

        会话绑定语义：只作用于当前注册表条目（互斥保证无旧会话残留可
        误停）；无条目=幂等宽容返回 ``{"success": False}``。**绝不乐观写
        stopped 快照**（HRO-1.3：防 UI 提前解锁邀请重下——stopped 快照
        只能由下载线程在检查点收口时写入）。"""
        with _DICT_DL_LOCK:
            entry = _DICT_DL_REGISTRY.get(kind)
            if entry is None:
                return {"success": False}
            entry["stop"].set()
        return {"success": True}

    def refine_dict_download_progress(self, kind: str) -> dict[str, Any]:
        """词典下载进度快照（第四批 owner 验收反馈；只读零副作用）。

        前端在 refine_dict_download 期间 1s 轮询：phase ∈
        download/verify/extract/done/failed/stopped（2.7.3 件⑤ 增
        stopped 终态），downloaded/total 为字节数（total 取
        Content-Length，可能为 None）。
        """
        try:
            from subtransjav.refine.dict_manager import download_progress
            return {"success": True, **download_progress(kind)}
        except Exception as e:
            _log_exc("refine_dict_download_progress")
            return {"success": False, "error": str(e)}

    def refine_asr_download(self, model: str, source: str = "auto") -> dict[str, Any]:
        """显式下载推荐 ASR 模型（2.6.3 批B，D2026-1003-01 ②）。

        model 白名单=推荐清单中 support=="available" 的 name；source ∈
        {auto, official, mirror}（镜像 PENDING 时 mirror 显式报"暂无可用
        镜像源"）。同步执行（3GB 档大文件，GUI 侧经 refine_asr_download_
        progress 1s 轮询）；AsrDownloadError/AsrChecksumError 统一转
        success=False + error（校验失败为后者的子类，一并覆盖）。
        """
        try:
            from subtransjav.refine import asr_env
            from subtransjav.refine.asr_downloader import (
                AsrChecksumError,
                AsrDownloadError,
                download_asr_model,
            )
            ok_models = {str(e.get("name"))
                         for e in asr_env.ASR_RECOMMENDED_MODELS
                         if e.get("support") == "available"}
            if str(model or "") not in ok_models:
                return {"success": False,
                        "error": f"未知或不可下载的 ASR 模型: {model}"}
            if source not in ("auto", "official", "mirror"):
                return {"success": False, "error": f"非法下载源: {source}"}
            path = download_asr_model(str(model), source)
            return {"success": True, "path": path}
        except AsrChecksumError as e:
            return {"success": False, "error": str(e)}
        except AsrDownloadError as e:
            return {"success": False, "error": str(e)}
        except Exception as e:
            _log_exc("refine_asr_download")
            return {"success": False, "error": str(e)}

    def refine_asr_download_progress(self, model: str) -> dict[str, Any]:
        """ASR 模型下载进度快照（2.6.3 批B；只读零副作用）。

        快照结构与词典下载进度同形：phase ∈ download/verify/done/failed，
        可选 note=源回退可见提示（评议员条件①）。"""
        try:
            from subtransjav.refine.asr_downloader import (
                asr_download_progress,
            )
            return {"success": True, **asr_download_progress(str(model))}
        except Exception as e:
            _log_exc("refine_asr_download_progress")
            return {"success": False, "error": str(e)}

    def refine_pick_dict_dir(self) -> dict[str, Any]:
        """自定义词典目录收口（批1b 件1）：原生对话框 → 持久登记 → 注入生效。

        链路 = refine_pick_folder('dict')（会话登记 + registered_dirs +
        user_dirs.dict_dir 持久化）→ dict_manager.set_custom_dir 进程内
        立即生效。返回体带变更前后目录与旧目录文件数（needs_migration
        供前端弹迁移确认，不静默自动迁移）；用户取消原样透传失败结果。
        """
        try:
            from subtransjav.refine import dict_manager as dm
            old_dir = dm.effective_dict_dir()
            result = self.refine_pick_folder("dict")
            if not (result.get("success") and result.get("path")):
                return result               # 取消/失败：原样透传（含 message）
            dm.set_custom_dir(str(result["path"]))
            old_files = dm.count_dict_files(old_dir)
            changed = os.path.normcase(old_dir) != \
                os.path.normcase(dm.effective_dict_dir())
            return {
                "success": True,
                "path": str(result["path"]),
                "old_dir": old_dir,
                "old_files": old_files,
                "custom_dir": dm.get_custom_dir(),
                "effective_dir": dm.effective_dict_dir(),
                "needs_migration": bool(changed and old_files > 0),
            }
        except Exception as e:
            _log_exc("refine_pick_dict_dir")
            return {"success": False, "error": str(e)}

    def refine_clear_dict_dir(self) -> dict[str, Any]:
        """恢复默认词典目录（批1b 件1）：清除持久值 + 进程内注入。

        返回体带旧目录与其文件数（供前端提示"原目录文件保留"——本接口
        不做任何删除/迁移，源文件一律不动）。
        """
        try:
            from subtransjav.refine import dict_manager as dm
            old_dir = dm.effective_dict_dir()
            old_custom = dm.get_custom_dir()
            user_dirs.set_dict_dir(None)
            dm.set_custom_dir(None)
            return {
                "success": True,
                "old_dir": old_dir,
                "old_files": dm.count_dict_files(old_dir),
                "had_custom": bool(old_custom),
                "effective_dir": dm.effective_dict_dir(),
            }
        except Exception as e:
            _log_exc("refine_clear_dict_dir")
            return {"success": False, "error": str(e)}

    def refine_dict_migrate(self, source_dir: str) -> dict[str, Any]:
        """一键迁移旧词典（批1b 件2）：source_dir → 现生效目录。

        复制+校验+原子改名引擎在 dict_manager.migrate_dicts（源文件一律
        不删；任一文件失败即中止）。进度经 refine_dict_download_progress
        伪 kind ``__migrate__`` 1s 轮询（复用下载进度通道，零新桥）。
        未设置自定义目录时拒绝（无可迁移目标）。
        """
        try:
            from subtransjav.refine import dict_manager as dm
            if not dm.get_custom_dir():
                return {"success": False,
                        "error": msg("dict_migrate_need_custom")}
            src = str(source_dir or "").strip()
            if not src:
                return {"success": False,
                        "error": msg("dict_migrate_need_source")}
            result = dm.migrate_dicts(src)
            return {"success": True, **result}
        except Exception as e:
            _log_exc("refine_dict_migrate")
            return {"success": False,
                    "error": f"{msg('dict_migrate_failed')}: {e}"}

    # ================================================================
    # 首启数据目录引导（批1b 件4）：后端只供哨兵读写两个 API，
    # 弹窗与流转逻辑在前端（与既有前端初始化流一致）
    # ================================================================
    def should_show_data_guide(self) -> dict[str, Any]:
        """是否弹首启数据目录引导（frozen-only，源码形态恒否防骚扰）。"""
        try:
            if not paths.is_frozen():
                return {"success": True, "show": False, "reason": "not-frozen"}
            return {
                "success": True,
                "show": not paths.data_guide_sentinel_path().exists(),
                "data_root": str(paths.data_root()),
            }
        except Exception as e:
            _log_exc("should_show_data_guide")
            return {"success": False, "error": str(e)}

    def mark_data_guide_done(self) -> dict[str, Any]:
        """写引导哨兵（防再弹；与 .data-root 指针同位=exe 同目录）。

        源码形态 no-op（哨兵不落地防脏工作树，与 template_seed 同口径）。
        """
        try:
            if not paths.is_frozen():
                return {"success": True, "written": False,
                        "reason": "not-frozen"}
            p = paths.data_guide_sentinel_path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text("done\n", encoding="utf-8")
            return {"success": True, "written": True}
        except OSError as e:
            _log_exc("mark_data_guide_done")
            return {"success": False, "error": str(e)}

    def refine_set_data_root(self, path: str) -> dict[str, Any]:
        """设置/清除数据保存根目录（写入 .data-root 指针，重启应用后生效）。

        path 为空串 = 清除指针恢复默认；否则必须是绝对路径
        （交 paths.set_data_root_pointer，不做白名单：
        用户自选本机目录，env 通道本就无界）。
        """
        try:
            target = str(path or "").strip()
            if target and not os.path.isabs(target):
                return {"success": False, "error": msg("data_root_need_abs")}
            ok, result = paths.set_data_root_pointer(target)
            if not ok:
                return {"success": False, "error": result}
            return {"success": True, "data_root": result,
                    "need_restart": True}
        except Exception as e:
            _log_exc("refine_set_data_root")
            return {"success": False, "error": str(e)}

    def refine_list_models(self, provider: str, endpoint: str = None,
                           api_key: str = None) -> dict[str, Any]:
        """在线拉取服务商可用模型列表（Zen 免费模型置顶）"""
        try:
            from openai import OpenAI

            from subtransjav.refine.config import (
                DEEPSEEK_BASE_DEFAULT,
                DEFAULT_TIMEOUT_HTTP,
                PROVIDER_ENDPOINT_DEFAULTS,
            )
            from subtransjav.refine.secrets import read_secret

            provider = (provider or "").lower()
            if provider == "deepseek":
                base = DEEPSEEK_BASE_DEFAULT
                key = api_key or os.environ.get("DEEPSEEK_API_KEY", "") \
                    or read_secret("deepseek")
            else:
                base = endpoint or PROVIDER_ENDPOINT_DEFAULTS.get(provider, "")
                if provider == "zen":
                    key = api_key or os.environ.get("OPENCODE_API_KEY", "") \
                        or read_secret("zen")
                elif provider == "siliconflow":
                    key = api_key or os.environ.get("SILICONFLOW_API_KEY", "") \
                        or read_secret("siliconflow")
                elif provider == "lmstudio":
                    key = "lm-studio"
                elif provider == "ollama":
                    key = "ollama"
                else:
                    key = api_key or read_secret("custom")
            if not base:
                return {"success": False, "error": msg("endpoint_missing")}
            # endpoint 与外部 URL 同源信任级别：仅放行 http/https
            # （本地 LM Studio/Ollama 走 http://localhost 属核心功能，不放行私有地址拦截）
            if not is_safe_url_scheme(base):
                return {"success": False, "error": msg("endpoint_scheme_unsupported")}
            if provider not in ("lmstudio", "ollama") and not key:
                return {"success": False, "error": msg("api_key_missing")}

            with OpenAI(base_url=base, api_key=key or "none",
                        timeout=DEFAULT_TIMEOUT_HTTP) as client:
                models = sorted(m.id for m in client.models.list())
            if provider == "zen":
                models.sort(key=lambda x: (not x.endswith("-free"), x))
            return {"success": True, "models": models}
        except Exception as e:
            _log_exc("refine_list_models")
            return {"success": False, "error": f"{type(e).__name__}: {e}",
                    "tip": _refine_error_tip(e)}

    def list_local_models(self, endpoint: str = None) -> dict[str, Any]:
        """获取本地 LM Studio 可用模型列表（已加载 + 已下载）"""
        try:
            import requests as _req
            base = (endpoint or "http://localhost:1234/v1").rstrip("/")
            # 去掉 /v1 后缀得到 root
            root = base[:-3] if base.endswith("/v1") else base

            # 获取已加载模型
            loaded = []
            try:
                r = _req.get(f"{root}/v1/models", timeout=5)
                loaded = [m.get("id", "") for m in r.json().get("data", [])]
            except Exception:
                pass

            # 获取已下载模型
            downloaded = []
            try:
                r0 = _req.get(f"{root}/api/v0/models", timeout=5)
                downloaded = [m.get("id", "") for m in r0.json().get("data", [])]
            except Exception:
                pass

            # 合并去重，已加载的排前面
            all_models = list(dict.fromkeys(loaded + downloaded))
            return {"success": True, "models": all_models, "loaded": loaded}
        except Exception as e:
            _log_exc("list_local_models")
            return {"success": False, "error": str(e), "models": []}

    def refine_test_stage(self, provider: str, model: str,
                          endpoint: str = None, api_key: str = None) -> dict[str, Any]:
        """单阶段连通性测试：极小请求验证服务商+模型可用性"""
        try:
            from openai import OpenAI

            from subtransjav.refine.config import DEEPSEEK_BASE_DEFAULT, DEFAULT_TIMEOUT_HTTP
            from subtransjav.refine.secrets import read_secret

            provider = (provider or "").lower()
            model = (model or "").strip()
            if not model:
                return {"success": False, "error": msg("model_name_missing")}
            if provider == "deepseek":
                base = DEEPSEEK_BASE_DEFAULT
                key = api_key or os.environ.get("DEEPSEEK_API_KEY", "") \
                    or read_secret("deepseek")
            else:
                from subtransjav.refine.config import PROVIDER_ENDPOINT_DEFAULTS as _PED
                base = endpoint or _PED.get(provider, "")
                if provider == "zen":
                    key = api_key or os.environ.get("OPENCODE_API_KEY", "") \
                        or read_secret("zen")
                elif provider == "siliconflow":
                    key = api_key or os.environ.get("SILICONFLOW_API_KEY", "") \
                        or read_secret("siliconflow")
                elif provider == "lmstudio":
                    key = "lm-studio"
                elif provider == "ollama":
                    key = "ollama"
                else:
                    key = api_key or read_secret("custom")
            if not base:
                return {"success": False, "error": msg("endpoint_missing")}
            # endpoint 与外部 URL 同源信任级别：仅放行 http/https
            # （本地 LM Studio/Ollama 走 http://localhost 属核心功能，不放行私有地址拦截）
            if not is_safe_url_scheme(base):
                return {"success": False, "error": msg("endpoint_scheme_unsupported")}

            with OpenAI(base_url=base, api_key=key or "none",
                        timeout=DEFAULT_TIMEOUT_HTTP) as client:
                r = client.chat.completions.create(
                    model=model,
                    messages=[{"role": "user", "content": msg("stage_test_ping")}],
                    max_tokens=512, temperature=0, stream=False)
                resp = r.choices[0].message
                txt = (resp.content or "").strip()[:40]
                if not txt:
                    rc = (getattr(resp, "reasoning_content", None) or "").strip()
                    txt = (msg("stage_test_reasoning", tail=rc[-28:])
                           if rc else msg("stage_test_empty"))
                return {"success": True, "message": txt}
        except Exception as e:
            _log_exc("refine_test_stage")
            return {"success": False,
                    "error": f"{type(e).__name__}: {e}",
                    "tip": _refine_error_tip(e)}

    def _refine_stage_settings_path(self) -> str:
        """每阶段 服务商/接口地址 持久化文件（config/refine_stage_settings.json）"""
        try:
            from subtransjav.refine.config import CONFIG_DIR
        except Exception:
            return os.path.join(os.getcwd(), "refine_stage_settings.json")
        # 服务端固定资源：目录由 CONFIG_DIR 决定、文件名硬编码；
        # 仍经安全锚点校验后返回，阻断环境/配置注入的越界路径直达 open() 汇点。
        return str(_resolve_safe_path(
            os.path.join(CONFIG_DIR, "refine_stage_settings.json")))

    def refine_save_stage_settings(self, stages: list[dict[str, Any]] = None,
                                   keys: list[dict[str, Any]] = None,
                                   settings: dict[str, Any] = None) -> dict[str, Any]:
        """保存每阶段设置。
        stages: [{"stage":1, "provider":"zen", "endpoint":"https://...",
                  "model":"..."}, ...]
        keys:   [{"stage":1, "provider":"zen", "key":"sk-..."}, ...]  -> DPAPI 密钥库
        settings: {"v2_concurrency": 2, ...}  -> 写入 JSON 顶层 settings 字典
        """
        saved_eps = 0
        saved_keys = 0
        saved_settings = 0
        try:
            if stages or settings:
                path = self._refine_stage_settings_path()
                data: dict[str, Any] = {"stages": [], "settings": {}}
                try:
                    with open(path, encoding="utf-8") as f:
                        old = json.load(f)
                    if isinstance(old, dict):
                        if isinstance(old.get("stages"), list):
                            data["stages"] = old["stages"]
                        if isinstance(old.get("settings"), dict):
                            data["settings"] = old["settings"]
                except Exception:
                    pass

                if stages:
                    by_stage = {s.get("stage"): s for s in data["stages"]
                                if isinstance(s, dict)}
                    for item in stages or []:
                        try:
                            n = int(item.get("stage"))
                        except Exception:
                            continue
                        entry = by_stage.get(n, {"stage": n})
                        if item.get("provider") is not None:
                            entry["provider"] = str(item["provider"])
                        if item.get("endpoint") is not None:
                            entry["endpoint"] = str(item["endpoint"])
                        # C1（D2026-0925-01）：模型缺省值档位随 stages 直存直读，
                        # 不进 config.py 分层。
                        if item.get("model") is not None:
                            entry["model"] = str(item["model"])
                        by_stage[n] = entry
                        saved_eps += 1
                    data["stages"] = [by_stage[k] for k in sorted(by_stage)]

                if settings:
                    for k, v in settings.items():
                        if k is None or v is None:
                            continue
                        data["settings"][str(k)] = v
                        saved_settings += 1

                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
            if keys:
                from subtransjav.refine.secrets import store_secret
                for item in keys or []:
                    prov = (item.get("provider") or "").strip()
                    key = (item.get("key") or "").strip()
                    if not prov:
                        continue
                    store_secret(prov, key)   # 空串 = 删除该密钥
                    saved_keys += 1
            return {"success": True, "endpoints_saved": saved_eps,
                    "keys_saved": saved_keys,
                    "settings_saved": saved_settings}
        except Exception as e:
            _log_exc("refine_save_stage_settings")
            return {"success": False, "error": str(e)}

    def refine_get_stage_settings(self) -> dict[str, Any]:
        """读取已保存的每阶段设置；密钥不回传明文，只返回 has_key 标记"""
        try:
            path = self._refine_stage_settings_path()
            stages: list[Any] = []
            settings: dict[str, Any] = {}
            if os.path.isfile(path):
                try:
                    with open(path, encoding="utf-8") as f:
                        data = json.load(f)
                    if isinstance(data, dict):
                        stages = data.get("stages", []) \
                            if isinstance(data.get("stages"), list) else []
                        settings = data.get("settings", {}) \
                            if isinstance(data.get("settings"), dict) else {}
                except Exception:
                    stages = []
            from subtransjav.refine.secrets import read_secret
            key_status = {}
            for prov in ("deepseek", "zen", "siliconflow", "custom"):
                try:
                    key_status[prov] = bool(read_secret(prov))
                except Exception:
                    key_status[prov] = False
            # 首启信号（additive 键）：settings 文件不存在即首启，供前端
            # 或集成方做欢迎/初始化引导
            return {"success": True, "stages": stages,
                    "settings": settings, "key_status": key_status,
                    "first_run": not os.path.isfile(path)}
        except Exception as e:
            _log_exc("refine_get_stage_settings")
            return {"success": False, "error": str(e)}

    def refine_get_glossary(self, path: str = None) -> dict[str, Any]:
        """读取词库词条列表（含可选别名第三列）。

        行格式 [src, dst, aliases]：aliases 为 `|` 分隔的别名文本，
        无别名时为空字符串 ""（行长度恒为 3，便于前端渲染）。
        """
        try:
            from subtransjav.refine.config import default_glossary_path
            from subtransjav.refine.glossary import load_glossary_ex
            p = path or default_glossary_path()
            p = str(_resolve_safe_path(p))
            rows = load_glossary_ex(p)
            return {"success": True, "path": p,
                    "rows": [[s, d, "|".join(a) if a else ""]
                             for s, d, a in rows]}
        except Exception as e:
            _log_exc("refine_get_glossary")
            return {"success": False, "error": str(e)}

    def refine_save_glossary(self, rows: list[list[str]], path: str = None) -> dict[str, Any]:
        """保存词库词条（保留别名：GUI 前端无别名编辑列，保存前先读
        旧库回填别名第三列，避免两列清洗静默抹掉 target_aliases）。

        返回值含 alias_kept = 实际写出时带别名的词条数。
        """
        try:
            from subtransjav.refine.config import default_glossary_path
            from subtransjav.refine.glossary import load_glossary_ex, save_glossary
            p = path or default_glossary_path()
            p = str(_resolve_safe_path(p))
            old_aliases: dict[str, tuple] = {}
            for src, _dst, aliases in load_glossary_ex(p):
                old_aliases.setdefault(src, aliases)
            clean = []
            alias_kept = 0
            for r in rows or []:
                if len(r) >= 2 and str(r[0]).strip() and str(r[1]).strip():
                    src, dst = str(r[0]).strip(), str(r[1]).strip()
                    aliases = old_aliases.get(src, ())
                    if len(r) >= 3 and str(r[2]).strip():
                        aliases = tuple(a.strip() for a in str(r[2]).split("|")
                                        if a.strip())
                    pair = (src, dst)
                    if pair not in clean:
                        clean.append((src, dst, aliases) if aliases else pair)
                        if aliases:
                            alias_kept += 1
            save_glossary(p, clean)
            return {"success": True, "count": len(clean),
                    "alias_kept": alias_kept, "path": p}
        except Exception as e:
            _log_exc("refine_save_glossary")
            return {"success": False, "error": str(e)}

    # 学习词库只读查看上限（防超大自学习文件卡 UI；超出截断 + total 计数）
    _LEARNED_GLOSSARY_MAX_ROWS = 500

    def refine_get_learned_glossary(self) -> dict[str, Any]:
        """只读查看学习词库 config/glossary_learned.csv（自学习产物）。

        路径锚 CONFIG_DIR（数据根 config 子目录，与 v2_learn 写入侧
        learned_glossary_path 同源），经 _resolve_safe_path 校验；
        复用 glossary.load_glossary_ex（utf-8-sig、两列起有效、别名
        第三列 `|` 拆分）。文件缺失 → ``{"exists": False}`` 零门槛不报错。
        超过 _LEARNED_GLOSSARY_MAX_ROWS 只返回前 N 行，``total`` 给全量
        行数，``truncated`` 标记截断。
        """
        try:
            from subtransjav.refine.config import CONFIG_DIR
            from subtransjav.refine.glossary import load_glossary_ex
            p = str(_resolve_safe_path(
                os.path.join(CONFIG_DIR, "glossary_learned.csv")))
            if not os.path.isfile(p):
                return {"success": True, "exists": False, "count": 0,
                        "total": 0, "rows": []}
            rows = load_glossary_ex(p)
            total = len(rows)
            cap = self._LEARNED_GLOSSARY_MAX_ROWS
            out = [{"source": s, "target": d,
                    "aliases": "|".join(a) if a else ""}
                   for s, d, a in rows[:cap]]
            return {"success": True, "exists": True, "path": p,
                    "count": len(out), "total": total,
                    "truncated": total > cap, "rows": out}
        except Exception as e:
            _log_exc("refine_get_learned_glossary")
            return {"success": False, "error": str(e)}

    def refine_list_templates(self, templates_dir: str = None) -> dict[str, Any]:
        """列出角色卡目录顶层 .txt 文件（下拉动态化，追加1 必改①）。

        - 目录口径与 _ensure_template_dir 一致（服务端默认目录或本会话
          登记目录），不新增任意目录列举能力；
        - 仅顶层不递归、仅 .txt、返回相对文件名（含复合后缀卡与 README
          类文件，"所见即所编"）；
        - 目录不存在/为空 → files=[]、pkg_fallback=True，**不创建目录**
          （前端据此回落固定 A/B 两项）；
        - ``canonical`` 附带 V2_TEMPLATE_FILES 精确文件名，供前端把
          阶段A/B 标注排最前（GUI 侧不重复硬编码文件名）。
        """
        try:
            from subtransjav.refine.pipeline_v2 import V2_TEMPLATE_FILES
            d = _ensure_template_dir(templates_dir)
            files: list[dict[str, Any]] = []
            if d and os.path.isdir(d):
                try:
                    names = sorted(os.listdir(d))
                except OSError:
                    names = []
                for name in names:
                    full = os.path.join(d, name)
                    if os.path.isfile(full) and name.lower().endswith(".txt"):
                        try:
                            mtime = os.path.getmtime(full)
                        except OSError:
                            mtime = 0.0
                        files.append({"name": name, "mtime": mtime})
            return {
                "success": True,
                "dir": d,
                "files": files,
                "pkg_fallback": not files,
                "canonical": dict(V2_TEMPLATE_FILES),
            }
        except Exception as e:
            _log_exc("refine_list_templates")
            return {"success": False, "error": str(e)}

    def refine_get_template(self, stage_index, templates_dir: str = None,
                            filename: str = None) -> dict[str, Any]:
        """读取角色卡原文。

        stage_index: 'A'|'B'（v2 两阶段，canonical 路径）；
        filename（追加1 必要⑤ load-by-name）：有效目录内纯文件名直读，
        守卫同保存端（basename 化 + resolve 在目录内 + .txt）；GUI load
        不做 pkg 回落——文件缺失走既有 template_file_missing 分支。
        """
        try:
            from subtransjav.refine.pipeline_v2 import V2_TEMPLATE_FILES
            d = _ensure_template_dir(templates_dir)
            note = ""
            if filename is not None and str(filename).strip():
                base = _safe_template_basename(filename)
                if base is None:
                    return {"success": False,
                            "error": msg("template_filename_invalid",
                                         name=filename)}
                p = _template_file_in_dir(d, base)
                if p is None:
                    return {"success": False,
                            "error": msg("template_filename_invalid",
                                         name=filename)}
                if base == V2_TEMPLATE_FILES.get("B"):
                    note = msg("template_b_note")
            else:
                tag = str(stage_index).upper()
                if tag not in V2_TEMPLATE_FILES:
                    return {"success": False,
                            "error": msg("invalid_stage_tag", tag=stage_index)}
                p = os.path.join(d, V2_TEMPLATE_FILES[tag])
                if tag == "B":
                    note = msg("template_b_note")
            if not os.path.isfile(p):
                return {"success": False,
                        "error": msg("template_file_missing", path=p), "path": p}
            with open(p, encoding="utf-8") as _f:
                text = _f.read()
            return {"success": True, "path": p, "text": text, "note": note}
        except Exception as e:
            _log_exc("refine_get_template")
            return {"success": False, "error": str(e)}

    # 质量报告查看器白名单后缀（只读；双格式 D2026-0929 批次：
    # 导读 json 渲染结构化导读，报告 txt 只读文本展示，不扩安全面）
    _GUIDE_JSON_SUFFIX = "_质量报告导读.json"
    _GUIDE_TXT_SUFFIX = "_质量报告.txt"
    # 报告 txt 只读展示上限（防超大报告卡 UI；超出截断并置 truncated）
    _GUIDE_TXT_MAX_CHARS = 1_000_000

    def read_output_artifact(self, path: str) -> dict[str, Any]:
        """读取输出目录中的质量报告成品（白名单双后缀，均只读）。

        - ``*_质量报告导读.json``：解析 JSON，返回 ``data``（行为向后兼容）；
        - ``*_质量报告.txt``：返回 ``text``/``kind:"txt"``/``truncated``，
          供前端页内只读文本块展示。
        其余后缀一律拒绝（目录守卫 + 后缀白名单不扩安全面）。
        """
        try:
            p = str(path or "").strip()
            if not p:
                return {"success": False, "error": msg("guide_path_empty")}
            try:
                _validate_user_directory(p)
            except ValueError as ve:
                return {"success": False, "error": msg("guide_path_denied", e=ve)}
            if not os.path.isfile(p):
                return {"success": False, "error": msg("guide_file_missing", path=p)}
            name = os.path.basename(p)
            if name.endswith(self._GUIDE_JSON_SUFFIX):
                with open(p, encoding="utf-8") as _f:
                    data = json.load(_f)
                if not isinstance(data, dict):
                    return {"success": False,
                            "error": msg("guide_bad_format")}
                return {"success": True, "path": p, "kind": "json",
                        "data": data}
            if name.endswith(self._GUIDE_TXT_SUFFIX):
                with open(p, encoding="utf-8", errors="replace") as _f:
                    text = _f.read(self._GUIDE_TXT_MAX_CHARS + 1)
                truncated = len(text) > self._GUIDE_TXT_MAX_CHARS
                if truncated:
                    text = text[: self._GUIDE_TXT_MAX_CHARS]
                return {"success": True, "path": p, "kind": "txt",
                        "text": text, "truncated": truncated}
            return {"success": False,
                    "error": msg("guide_suffix_only",
                                 suffix=self._GUIDE_JSON_SUFFIX
                                 + " / " + self._GUIDE_TXT_SUFFIX,
                                 name=name)}
        except json.JSONDecodeError:
            _log_exc("read_output_artifact")
            return {"success": False,
                    "error": msg("guide_corrupted")}
        except Exception as e:
            _log_exc("read_output_artifact")
            return {"success": False, "error": str(e)}

    def refine_save_template(self, stage_index, text: str,
                             templates_dir: str = None,
                             filename: str = None) -> dict[str, Any]:
        """保存角色卡文本。

        stage_index: 'A'|'B'（canonical 路径，现状行为保留兼容）；
        filename（追加1 必改② 值域闭环）：允许保存到"有效目录内、
        .txt 后缀、且该文件名 ∈ refine_list_templates 返回集（目录内
        既有顶层 .txt）或 canonical 默认卡名"的文件。守卫三重：
        basename 化（纯文件名，拒穿越/嵌套/绝对路径）+ join 后 resolve
        仍在有效目录内 + 值域成员校验；pkg_fallback（目录为空）时保存
        canonical 名 = 新建默认文件，照常放行。
        """
        try:
            from subtransjav.refine.pipeline_v2 import V2_TEMPLATE_FILES
            d = _ensure_template_dir(templates_dir)
            if filename is not None and str(filename).strip():
                base = _safe_template_basename(filename)
                if base is None:
                    return {"success": False,
                            "error": msg("template_filename_invalid",
                                         name=filename)}
                p = _template_file_in_dir(d, base)
                if p is None:
                    return {"success": False,
                            "error": msg("template_filename_invalid",
                                         name=filename)}
                # 值域成员校验：目录内既有 .txt（=list 返回集）或
                # canonical 默认卡名（目录为空时新建默认文件的放行路径）
                if base not in V2_TEMPLATE_FILES.values() \
                        and not os.path.isfile(p):
                    return {"success": False,
                            "error": msg("template_save_not_allowed",
                                         name=base)}
            else:
                tag = str(stage_index).upper()
                if tag not in V2_TEMPLATE_FILES:
                    return {"success": False,
                            "error": msg("invalid_stage_tag", tag=stage_index)}
                p = os.path.join(d, V2_TEMPLATE_FILES[tag])
            os.makedirs(d, exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text or "")
            return {"success": True, "path": p}
        except Exception as e:
            _log_exc("refine_save_template")
            return {"success": False, "error": str(e)}

    def refine_pick_folder(self, purpose: str = None) -> dict[str, Any]:
        """原生目录对话框选取 + 持久登记（批1a 件3）。

        成功即写 user_dirs.json registered_dirs（重启仍生效，供校对保存/
        角色卡目录等白名单消费；数据根浏览等所有经此入口的选取统一受益）；
        purpose='templates' 时同时持久化为角色卡目录；purpose='dict' 时
        同时持久化为自定义词典目录（批1b 件1，落位注入由
        refine_pick_dict_dir 收口）。持久化失败不阻断选择结果（会话登记
        已由 select_folder 完成，仅降级为重启失效）。
        """
        result = self.select_folder()
        if result.get("success") and result.get("path"):
            try:
                user_dirs.register_dir(str(result["path"]))
                if str(purpose or "").strip() == "templates":
                    user_dirs.set_templates_dir(str(result["path"]))
                elif str(purpose or "").strip() == "dict":
                    user_dirs.set_dict_dir(str(result["path"]))
            except Exception:
                _log_exc("refine_pick_folder")
        return result

    def refine_pick_csv_open(self) -> dict[str, Any]:
        """打开词库 CSV/TXT 文件选择对话框"""
        try:
            windows = webview.windows
            if not windows:
                return {"success": False, "error": msg("no_active_window")}
            result = self._open_file_dialog(
                (msg("file_type_glossary"), msg("file_type_all")))
            if result:
                return {"success": True, "path": result[0]}
            return {"success": False, "error": msg("dialog_cancelled")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def refine_pick_guide_json(self) -> dict[str, Any]:
        """打开其他质量报告导读 json 文件选择对话框
        （D2026-0930-07 owner 痛点批：替代原粘贴路径行；cancelled 标记
        供前端区分用户取消——静默返回，其余 error 走状态 span）"""
        try:
            windows = webview.windows
            if not windows:
                return {"success": False, "error": msg("no_active_window")}
            result = self._open_file_dialog(
                (msg("file_type_guide"), msg("file_type_all")))
            if result:
                return {"success": True, "path": result[0]}
            return {"success": False, "cancelled": True,
                    "error": msg("dialog_cancelled")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def refine_pick_csv_save(self) -> dict[str, Any]:
        """词库导出保存对话框"""
        try:
            windows = webview.windows
            if not windows:
                return {"success": False, "error": msg("dialog_cancelled")}
            result = self._open_file_dialog(
                (msg("file_type_csv"),), save=True,
                default_name="glossary_export.csv")
            if result:
                return {"success": True, "path": result[0]}
            return {"success": False, "error": msg("dialog_cancelled")}
        except Exception as e:
            _log_exc("tm_pick_db")
            return {"success": False, "error": str(e)}

    # ================================================================
    # AI 质量分析（D2026-0929：--ai-analyze 前后端接入）
    # 注意：本批新增错误文案为内联中文（未进 strings.py），系任务边界
    # 限定改动面（api.py/app.js/index.html/两测试）所致；行为与
    # msg() 回退语义等价（fail 返回 error 字符串）。
    # ================================================================

    _AI_ANALYZE_TIMEOUT_S = 600
    _AI_REPORT_SUFFIX = "_质量报告.txt"
    _AI_SUGGESTION_SUFFIX = "_AI质量建议.json"

    # 分析子进程按 provider 选择的端点旗标（与 cli.build_parser 一致）
    _AI_PROVIDER_ENDPOINT_FLAGS = {
        "lmstudio": "--lmstudio-endpoint",
        "ollama": "--ollama-endpoint",
        "zen": "--zen-endpoint",
        "siliconflow": "--siliconflow-endpoint",
        "custom": "--custom-endpoint",
    }
    # 云端 provider → 子进程密钥环境变量名（与 RefineConfig.resolve_api_key、
    # start_translation 注入表一致；zen 走 OPENCODE_API_KEY）
    _AI_PROVIDER_KEY_ENV = {
        "deepseek": "DEEPSEEK_API_KEY",
        "zen": "OPENCODE_API_KEY",
        "siliconflow": "SILICONFLOW_API_KEY",
        "custom": "CUSTOM_API_KEY",
    }

    def _stage_a_provider_name(self) -> str:
        """阶段A（槽0/存储 stage=1）provider 名；读取失败返回空串。"""
        try:
            got = self.refine_get_stage_settings()
        except Exception:
            return ""
        if not isinstance(got, dict) or not got.get("success"):
            return ""
        for s in got.get("stages") or []:
            if isinstance(s, dict) and int(s.get("stage") or 0) == 1:
                return str(s.get("provider") or "")
        return ""

    def _stage_a_endpoint(self) -> str:
        """阶段A（存储 stage=1）端点；读取失败/未存返回空串。"""
        try:
            got = self.refine_get_stage_settings()
        except Exception:
            return ""
        if not isinstance(got, dict) or not got.get("success"):
            return ""
        for s in got.get("stages") or []:
            if isinstance(s, dict) and int(s.get("stage") or 0) == 1:
                return str(s.get("endpoint") or "").strip()
        return ""

    def _stage_a_model(self) -> str:
        """阶段A（存储 stage=1）模型名；读取失败/未存返回空串。"""
        try:
            got = self.refine_get_stage_settings()
        except Exception:
            return ""
        if not isinstance(got, dict) or not got.get("success"):
            return ""
        for s in got.get("stages") or []:
            if isinstance(s, dict) and int(s.get("stage") or 0) == 1:
                return str(s.get("model") or "").strip()
        return ""

    def refine_ai_analyze(self, report_path: str, model: str = None,
                          ai_provider: str = None) -> dict[str, Any]:
        """同步执行 AI 质量分析并读回建议件。

        流程：_resolve_safe_path 校验 → 同步 subprocess 跑
        ``python -m subtransjav.refine.cli --ai-analyze <path>
        [--ai-model m]``（cwd=项目根，timeout=600s）→ 成功后读回
        ``{stem}_AI质量建议.json`` 解析返回。
        超时/非零退出/建议件缺失 → success=False + error。
        """
        p = str(report_path or "").strip()
        if not p:
            return {"success": False, "error": msg("guide_path_empty")}
        # 2.5.0 修复B：守卫 _resolve_safe_path（home/仓库根白名单）→
        # _validate_user_directory（任意用户磁盘目录、拦系统目录+可执行；
        # 与 read_output_artifact 同口径），后缀白名单 _AI_REPORT_SUFFIX 保留
        try:
            p = str(_validate_user_directory(p))
        except ValueError as ve:
            return {"success": False, "error": msg("guide_path_denied", e=ve)}
        if not os.path.isfile(p):
            return {"success": False,
                    "error": msg("guide_file_missing", path=p)}
        if not os.path.basename(p).endswith(self._AI_REPORT_SUFFIX):
            return {"success": False,
                    "error": f"需要 {self._AI_REPORT_SUFFIX} 质量报告文件: "
                             f"{os.path.basename(p)}"}

        name = os.path.basename(p)
        if name.endswith(self._AI_REPORT_SUFFIX):
            stem = name[: -len(self._AI_REPORT_SUFFIX)]
        else:
            stem = os.path.splitext(name)[0]

        # 纯 CLI 参数：解释器前缀由 spawn_refine_cli 统一拼装（修订③收敛）
        args = ["--ai-analyze", p]
        model = (model or "").strip()
        if model:
            args.extend(["--ai-model", model])
        # 2.6.0 批 3（D2026-1002-04-批3）：媒体重点对照的 ASR 指定
        # （设置 KV asr_model/asr_python → CLI 旗标；缺省=运行器侧探测降级）
        # 2.6.0 批 2 修订（D2026-1002-05）：跨片统计窗口（KV tm_stats_window
        # → CLI 旗标 --tm-stats-window，三档）
        try:
            got = self.refine_get_stage_settings()
            kv = (got or {}).get("settings") or {}
            asr_model_kv = str(kv.get("asr_model") or "").strip()
            asr_python_kv = str(kv.get("asr_python") or "").strip()
            tm_window_kv = str(kv.get("tm_stats_window") or "").strip()
            mc_kv = str(kv.get("media_crosscheck_enabled") or "").strip()
        except Exception:
            asr_model_kv = ""
            asr_python_kv = ""
            tm_window_kv = ""
            mc_kv = ""
        if asr_model_kv:
            args.extend(["--asr-model", asr_model_kv])
        if asr_python_kv:
            args.extend(["--asr-python", asr_python_kv])
        if tm_window_kv in ("7", "30", "all"):
            args.extend(["--tm-stats-window", tm_window_kv])
        # 2.6.1 修订（D2026-1002-06）：媒体重点对照开关（KV "1"/"0" →
        # CLI 旗标 --media-crosscheck-enabled；缺省不传=分层链默认关）
        if mc_kv in ("0", "1"):
            args.extend(["--media-crosscheck-enabled", mc_kv])

        # 分析子进程跟随阶段A 服务商/端点（与 refine_get_stage_settings
        # 同源读取）：GUI 阶段A 配云端时，分析子进程若不传 --s1-provider
        # 会落到 CLI 缺省 lmstudio 本地端点，必然失败且与隐私横幅错位。
        # 端点按 CLI 既有旗标 --<provider>-endpoint 显式非空才传。
        # 密钥/差异项经 env_extra 注入；PYTHONUTF8/PYTHONIOENCODING 由
        # spawn_refine_cli 统一强制（#190）。
        env_extra: dict[str, str] = {"PYTHONUNBUFFERED": "1"}
        # provider 决策（D2026-1001-07）：ai_provider 缺省=跟随阶段A；
        # 独立 provider 时端点走 CLI 各 provider 默认（custom 无默认端点，
        # 前端下拉已排除，此处兜底拒绝）；密钥仍按 provider 同槽注入。
        if ai_provider:
            provider = str(ai_provider).strip().lower()
            if provider == "custom":
                return {"success": False,
                        "error": "自定义接口暂不支持独立配置："
                                 "请将阶段A 服务商设为 custom 后使用"}
            endpoint = ""
        else:
            provider = self._stage_a_provider_name()
            endpoint = self._stage_a_endpoint()
        if provider:
            args.extend(["--s1-provider", provider])
            flag = self._AI_PROVIDER_ENDPOINT_FLAGS.get(provider)
            if endpoint and flag:
                args.extend([flag, endpoint])
            # 密钥仅经子进程环境变量注入（不写命令行、不落日志），
            # 变量名与 RefineConfig.resolve_api_key / start_translation 一致；
            # 本地服务商（lmstudio/ollama）无密钥，不注入。
            key_env = self._AI_PROVIDER_KEY_ENV.get(provider)
            if key_env:
                try:
                    from subtransjav.refine.secrets import read_secret
                    key = read_secret(provider)
                except Exception:
                    key = ""
                if key:
                    env_extra[key_env] = key

        try:
            proc = cast(subprocess.CompletedProcess, spawn_refine_cli(
                args, capture=True, cwd=str(REPO_ROOT),
                timeout=self._AI_ANALYZE_TIMEOUT_S,
                encoding="utf-8", errors="replace",
                env_extra=env_extra))
        except subprocess.TimeoutExpired:
            return {"success": False,
                    "error": f"AI 分析超时（>{self._AI_ANALYZE_TIMEOUT_S}s）"}
        stderr_tail = (proc.stderr or "")[-2000:]
        if proc.returncode != 0:
            return {"success": False,
                    "error": msg("process_exit_code", code=proc.returncode),
                    "stderr_tail": stderr_tail}
        # 2.6.0 批 3 知情行（C6）：对照段数随成功返回（前端状态行提示）
        crosscheck_segments = 0
        m = re.search(r"\[crosscheck\] segments=(\d+)", proc.stdout or "")
        if m:
            crosscheck_segments = int(m.group(1))

        companion = os.path.join(os.path.dirname(p),
                                 stem + self._AI_SUGGESTION_SUFFIX)
        if not os.path.isfile(companion):
            return {"success": False,
                    "error": "分析已结束但建议件缺失: "
                             f"{os.path.basename(companion)}",
                    "stderr_tail": stderr_tail}
        try:
            with open(companion, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError) as e:
            return {"success": False,
                    "error": f"建议件读取/解析失败: {e}",
                    "stderr_tail": stderr_tail}
        if not isinstance(data, dict):
            return {"success": False, "error": "建议件格式异常（非对象）",
                    "stderr_tail": stderr_tail}
        return {
            "success": True,
            "parse_ok": bool(data.get("parse_ok")),
            "suggestions": (data.get("suggestions")
                            if isinstance(data.get("suggestions"), dict)
                            else {}),
            "provider_name": provider,
            "companion_path": companion,
            "stderr_tail": stderr_tail,
            "crosscheck_segments": crosscheck_segments,
        }

    # ----------------------------------------------------------------
    # 质量闭环一键批次修复（2.6.0 批1，D2026-1002-02-批1：HRO-1 条件③
    # 一键批次人工放行——确认与逐条预览在前端 AppModal，执行经 CLI
    # --action-retranslate 子进程，无无人值守自动写盘；复验=重跑全片
    # AI 分析恰 1 次做建议件三键 diff。幂等守卫=GUI 层台账感知
    # （执行器本体无台账跳过，_refresh_guide 不翻 status，实证
    # action_retranslate.py:262-280）；威胁模型=docs/design/
    # 威胁模型-质量闭环-d1002.md）
    # ----------------------------------------------------------------

    _GUIDE_SUFFIX = "_质量报告导读.json"
    _LEDGER_SUFFIX = "_重翻记录.json"
    _BATCH_FIX_MAX_ENTRIES = 50
    _BATCH_FIX_TIMEOUT_S = 1800
    _SUGGESTION_KEYS = ("glossary", "tm", "observations")
    # 惰性初始化（_bf_progress），避免触碰 __init__
    _batch_fix_progress_state: dict[str, Any]

    def _bf_progress(self) -> dict[str, Any]:
        if not hasattr(self, "_batch_fix_progress_state"):
            self._batch_fix_progress_state = {
                "running": False, "phase": "idle", "done": 0,
                "total": 0, "last_line": ""}
        return self._batch_fix_progress_state

    def _stage_b_stage_settings(self, key: str) -> str:
        """阶段B（存储 stage=3，槽 s3）设置项；读取失败/未存返回空串。"""
        try:
            got = self.refine_get_stage_settings()
        except Exception:
            return ""
        if not isinstance(got, dict) or not got.get("success"):
            return ""
        for s in got.get("stages") or []:
            if isinstance(s, dict) and int(s.get("stage") or 0) == 3:
                return str(s.get(key) or "").strip()
        return ""

    def _stage_b_provider_name(self) -> str:
        return self._stage_b_stage_settings("provider")

    def _stage_b_endpoint(self) -> str:
        return self._stage_b_stage_settings("endpoint")

    def _stage_b_model(self) -> str:
        return self._stage_b_stage_settings("model")

    def _resolve_fix_model_config(self) -> dict[str, Any]:
        """C7 补链（D2026-1007-02 件C）：批量修复 provider/endpoint/model
        统一解析（fail-closed；三元组全部读既有阶段 KV getter，零新增
        读取通道）。修复子进程 model 缺失时 CLI 落缺省空串 →
        pipeline RefineError「未指定模型名」全败退出，故拒绝必须发生在
        spawn 之前而非放任子进程失败。

        规则（三元组=provider/endpoint/model）：
        - 阶段B provider 与 model 均非空 → 用 B 整组（endpoint=B，可空）；
        - 阶段B provider 与 model 均空 → 整组回退阶段A（全取 A）；A 的
          model 也空 → 拒绝（无模型修复必然全败）；
        - 阶段B provider 非空但 model 空 → 仅当阶段A provider 与 B 同名
          （小写比较）时取 B provider/endpoint + A model，否则拒绝（防
          「B 端点 + A 异服务商模型名」跨服务商错配）；
        - 阶段B model 非空但 provider 空 → 维持现行为：provider 不传落
          CLI 缺省 lmstudio，放行但以 source 标注（注释即本行）；阶段A
          provider 已配置且非 lmstudio 时拒绝（防「lmstudio 本地端点 +
          云模型名」错配——与上一条同理 fail-closed；A 未配置不算错配）。

        返回 dict(provider, endpoint, model, source, ok, reason)；
        拒绝时 ok=False + 人话 reason 且三元组为空串。"""
        b_provider = self._stage_b_provider_name()
        b_model = self._stage_b_model()
        b_endpoint = self._stage_b_endpoint()

        def _deny(reason: str) -> dict[str, Any]:
            return {"ok": False, "provider": "", "endpoint": "",
                    "model": "", "source": "", "reason": reason}

        if b_provider and b_model:
            return {"ok": True, "provider": b_provider,
                    "endpoint": b_endpoint, "model": b_model,
                    "source": "stage_b", "reason": ""}
        if not b_provider and not b_model:
            a_provider = self._stage_a_provider_name()
            a_endpoint = self._stage_a_endpoint()
            a_model = self._stage_a_model()
            if not a_model:
                return _deny(
                    "阶段B 与阶段A 均未配置可用模型：请先在「翻译设置」"
                    "为至少一个阶段填写模型名")
            return {"ok": True, "provider": a_provider,
                    "endpoint": a_endpoint, "model": a_model,
                    "source": "stage_a_fallback", "reason": ""}
        if b_provider and not b_model:
            a_provider = self._stage_a_provider_name()
            if (a_provider or "").strip().lower() == b_provider.lower():
                a_model = self._stage_a_model()
                if a_model:
                    return {"ok": True, "provider": b_provider,
                            "endpoint": b_endpoint, "model": a_model,
                            "source": "stage_b_provider_stage_a_model",
                            "reason": ""}
            return _deny(
                f"阶段B（{b_provider}）未填写模型名，且阶段A 没有同名"
                "服务商的可用模型：请在「翻译设置 · 阶段B（审校+抛光）」"
                "填写模型名")
        # 剩余分支：B model 非空但 provider 空（见 docstring 第 4 条）
        a_provider = self._stage_a_provider_name()
        if (a_provider or "").strip().lower() not in ("", "lmstudio"):
            return _deny(
                f"阶段B 只填了模型名未填服务商，而阶段A 服务商为 "
                f"{a_provider}（非 lmstudio）：修复将落本地 lmstudio 端点"
                "与该模型名错配，已拒绝；请在阶段B 补全服务商")
        return {"ok": True, "provider": "", "endpoint": "",
                "model": b_model,
                "source": "stage_b_model_provider_default", "reason": ""}

    def refine_preview_fix_config(self) -> dict[str, Any]:
        """C7 桥（D2026-1007-02 件C）：修复生效配置预览（只读、无副作用、
        不 spawn），供前端修复卡明示行与确认框刷新。共用
        _resolve_fix_model_config 解析结果，形状钉（provider/endpoint/
        model/source/reason 恒为字符串，ok 恒为布尔）。"""
        try:
            cfg = self._resolve_fix_model_config()
        except Exception as e:
            _log_exc("refine_preview_fix_config")
            return {"ok": False, "provider": "", "endpoint": "",
                    "model": "", "source": "", "reason": str(e)}
        return {"ok": bool(cfg.get("ok")),
                "provider": str(cfg.get("provider") or ""),
                "endpoint": str(cfg.get("endpoint") or ""),
                "model": str(cfg.get("model") or ""),
                "source": str(cfg.get("source") or ""),
                "reason": str(cfg.get("reason") or "")}

    def _load_guide_json(self, p: str) -> dict[str, Any] | None:
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return None
        return data if isinstance(data, dict) else None

    def _applied_timings(self, guide_dir: str, stem: str) -> set[str]:
        """台账中 outcome=="applied" 的 timing 集合；缺/损坏返回空集。"""
        try:
            with open(os.path.join(guide_dir, stem + self._LEDGER_SUFFIX),
                      encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return set()
        out: set[str] = set()
        if isinstance(data, list):
            for rec in data:
                if (isinstance(rec, dict) and rec.get("outcome") == "applied"
                        and rec.get("timing")):
                    out.add(str(rec["timing"]))
        return out

    def _read_ledger(self, guide_dir: str, stem: str) -> list:
        try:
            with open(os.path.join(guide_dir, stem + self._LEDGER_SUFFIX),
                      encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return []
        return data if isinstance(data, list) else []

    def _suggestion_counts(self, guide_dir: str, stem: str) -> dict[str, int]:
        counts = {k: 0 for k in self._SUGGESTION_KEYS}
        try:
            with open(os.path.join(guide_dir,
                                   stem + self._AI_SUGGESTION_SUFFIX),
                      encoding="utf-8") as f:
                data = json.load(f)
        except (OSError, ValueError):
            return counts
        sug = data.get("suggestions") if isinstance(data, dict) else None
        if isinstance(sug, dict):
            for k in self._SUGGESTION_KEYS:
                v = sug.get(k)
                counts[k] = len(v) if isinstance(v, list) else 0
        return counts

    def _load_validated_guide(self, guide_path: str):
        """守卫链（批修复/条目读取共用）：路径校验+后缀白名单+导读加载。

        返回 (p, stem, guide, error)：error 非 None 时前三者无意义。"""
        p = str(guide_path or "").strip()
        if not p:
            return None, None, None, {
                "success": False, "error": msg("guide_path_empty")}
        try:
            p = str(_validate_user_directory(p))
        except ValueError as ve:
            return None, None, None, {
                "success": False, "error": msg("guide_path_denied", e=ve)}
        if not os.path.isfile(p):
            return None, None, None, {
                "success": False, "error": msg("guide_file_missing", path=p)}
        name = os.path.basename(p)
        if not name.endswith(self._GUIDE_SUFFIX):
            return None, None, None, {
                "success": False,
                "error": f"需要 {self._GUIDE_SUFFIX} 导读文件: {name}"}
        stem = name[: -len(self._GUIDE_SUFFIX)]
        guide = self._load_guide_json(p)
        if guide is None:
            return None, None, None, {
                "success": False, "error": "导读读取/解析失败"}
        items = guide.get("items")
        if not isinstance(items, list):
            return None, None, None, {
                "success": False, "error": "导读格式异常（无 items 数组）"}
        return p, stem, guide, None

    def refine_guide_action_items(self, guide_path: str) -> dict[str, Any]:
        """读导读 json 行动条目并标记台账已修状态（幂等守卫数据源）。

        只回元数据与短摘录（现译前 20 字），不回全量文本。摘录限长仅约束
        后端回包形状；GUI 确认框展示全文来自其已持有的导读 json
        （read_output_artifact），实际暴露面不变（D2026-1007-01）。"""
        try:
            p, stem, guide, err = self._load_validated_guide(guide_path)
            if err is not None:
                return err
            items = guide["items"]
            applied = self._applied_timings(os.path.dirname(p), stem)
            open_items: list[dict[str, Any]] = []
            cat_counts: dict[str, int] = {}
            observation_count = 0
            applied_open_count = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                status = str(it.get("status") or "")
                if status == "observation":
                    observation_count += 1
                    continue
                if status != "open":
                    continue
                idx = it.get("index")
                cur = it.get("current_text")
                timing = str(it.get("timing") or "")
                in_ledger = timing in applied
                if in_ledger:
                    applied_open_count += 1
                open_items.append({
                    "index": idx if isinstance(idx, int) else None,
                    "category": str(it.get("category") or ""),
                    "timing": timing,
                    "excerpt": cur[:20] if isinstance(cur, str) else "",
                    "applied_in_ledger": in_ledger,
                })
                if not in_ledger:
                    cat = str(it.get("category") or "")
                    cat_counts[cat] = cat_counts.get(cat, 0) + 1
            return {
                "success": True,
                "stem": stem,
                "guide_path": p,
                "report_path": os.path.join(os.path.dirname(p),
                                            stem + self._AI_REPORT_SUFFIX),
                "open_items": open_items,
                "cat_counts": cat_counts,
                "applied_open_count": applied_open_count,
                "observation_count": observation_count,
                "direction": str(guide.get("direction") or ""),
                "has_media": bool(guide.get("media_path")),
            }
        except Exception as e:
            _log_exc("refine_guide_action_items")
            return {"success": False, "error": str(e)}

    def refine_batch_fix(self, guide_path: str, entries: Any,
                         ai_provider: str = None,
                         ai_model: str = None) -> dict[str, Any]:
        """一键批次修复：确认与逐条预览在前端（AppModal），本方法执行。

        守卫链：路径/后缀 → entries 整数数组 ≤_BATCH_FIX_MAX_ENTRIES →
        逐条命中 open 且有现译（观察类必拒，C6）→ 台账已修拒入批
        （C1 幂等守卫；重修走 CLI --entries 显式通道）。执行=
        spawn_refine_cli 子进程跑 --action-retranslate --apply（修复
        provider/model 经 _resolve_fix_model_config 统一解析
        （C7/D2026-1007-02 件C：拒绝即不 spawn）；台账先于终稿写序/
        恒等式断言在执行器侧
        原样生效）；复验=生效后重跑全片 AI 分析恰 1 次做建议件三键
        计数 diff（复验 provider/model 透传 AI 分析独立配置）。"""
        p, stem, guide, err = self._load_validated_guide(guide_path)
        if err is not None:
            return err
        items = guide["items"]

        if not isinstance(entries, list) or not entries:
            return {"success": False, "error": "entries 需为非空整数数组"}
        want: set[int] = set()
        for e in entries:
            if isinstance(e, bool) or not isinstance(e, int):
                return {"success": False, "error": "entries 需为整数数组"}
            want.add(e)
        if len(want) > self._BATCH_FIX_MAX_ENTRIES:
            return {"success": False,
                    "error": f"单批上限 {self._BATCH_FIX_MAX_ENTRIES} 条"
                             f"（本次 {len(want)} 条）；请分批发起"}
        fixable: dict[int, str] = {}
        for it in items:
            if not isinstance(it, dict) or it.get("status") != "open":
                continue
            if not isinstance(it.get("current_text"), str):
                continue  # 观察类/无现译：绝不自动重翻（C6）
            idx = it.get("index")
            if isinstance(idx, int):
                fixable[idx] = str(it.get("timing") or "")
        unknown = sorted(want - set(fixable))
        if unknown:
            return {"success": False,
                    "error": "条目不存在或不可自动重翻（观察类/无现译）: "
                             + ",".join(str(i) for i in unknown[:10])}
        applied = self._applied_timings(os.path.dirname(p), stem)
        already = sorted(i for i in want if fixable[i] in applied)
        if already:
            return {"success": False,
                    "error": "以下条目已修过（台账在案）: "
                             + ",".join(str(i) for i in already[:10])
                             + "；如需重修请用 CLI --entries 显式指定"}

        guide_dir = os.path.dirname(p)
        pre_counts = self._suggestion_counts(guide_dir, stem)
        pre_suggestion_missing = not os.path.isfile(
            os.path.join(guide_dir, stem + self._AI_SUGGESTION_SUFFIX))
        pre_ledger_len = len(self._read_ledger(guide_dir, stem))

        # 修复 provider/endpoint/model 统一经 C7 解析（D2026-1007-02 件C：
        # 阶段B 缺模型时回退/拒绝链；拒绝即不 spawn——原先空 model 放任
        # 子进程落 CLI 缺省空串 → pipeline RefineError 全败退出 1）；
        # 密钥仍仅经子进程环境变量注入（白名单表与翻译/分析一致）。
        cfg = self._resolve_fix_model_config()
        if not cfg.get("ok"):
            return {"success": False, "error": msg("fix_model_unconfigured")}
        args = ["--action-retranslate", p,
                "--entries", ",".join(str(i) for i in sorted(want)),
                "--apply"]
        provider = str(cfg.get("provider") or "")
        if provider:
            args.extend(["--s3-provider", provider])
            flag = self._AI_PROVIDER_ENDPOINT_FLAGS.get(provider)
            endpoint = str(cfg.get("endpoint") or "")
            if endpoint and flag:
                args.extend([flag, endpoint])
        fix_model = str(cfg.get("model") or "")
        if fix_model:
            args.extend(["--action-model", fix_model])
        env_extra: dict[str, str] = {"PYTHONUNBUFFERED": "1"}
        key_env = self._AI_PROVIDER_KEY_ENV.get(provider)
        if key_env:
            try:
                from subtransjav.refine.secrets import read_secret
                key = read_secret(provider)
            except Exception:
                key = ""
            if key:
                env_extra[key_env] = key

        prog = self._bf_progress()
        prog.update({"running": True, "phase": "run", "done": 0,
                     "total": len(want), "last_line": ""})
        try:
            proc = cast(subprocess.Popen, spawn_refine_cli(
                args, cwd=str(REPO_ROOT), env_extra=env_extra,
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                text=True, encoding="utf-8", errors="replace", bufsize=1))
        except Exception as e:
            _log_exc("refine_batch_fix.spawn")
            prog.update({"running": False, "phase": "failed"})
            return {"success": False, "error": f"修复子进程启动失败: {e}"}

        tail: list[str] = []

        def _pump() -> None:
            # 执行器 stdout 无逐条进度契约（评审修订：原 n/m 正则钉住了
            # 不存在的格式）——只透传尾行供状态展示，计数以台账增量结算。
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.rstrip()
                if not line:
                    continue
                tail.append(line)
                prog["last_line"] = line[-200:]

        threading.Thread(target=_pump, daemon=True).start()
        try:
            rc = proc.wait(timeout=self._BATCH_FIX_TIMEOUT_S)
        except subprocess.TimeoutExpired:
            try:
                terminate_process_tree(proc.pid)
            except Exception:
                with contextlib.suppress(Exception):
                    proc.kill()
            prog.update({"running": False, "phase": "failed",
                         "last_line": "超时终止"})
            return {"success": False,
                    "error": f"批量修复超时（>{self._BATCH_FIX_TIMEOUT_S}s）；"
                             "已落盘条目以台账为准，可再次发起处理余量",
                    "stdout_tail": "\n".join(tail[-40:])[-2000:]}
        prog.update({"running": False,
                     "phase": "done" if rc in (0, 3) else "failed"})
        result: dict[str, Any] = {
            "success": rc in (0, 3),
            "exit_code": rc,
            "applied": 0,
            "failed": 0,
            "source_partial": 0,
            "stdout_tail": "\n".join(tail[-40:])[-2000:],
            "schema": 1,
        }
        if rc == 2:
            result["error"] = "条目选择非法（执行器退出码 2）"
            return result
        post_ledger = self._read_ledger(guide_dir, stem)
        new_records = post_ledger[pre_ledger_len:] \
            if len(post_ledger) > pre_ledger_len else []
        result["applied"] = sum(
            1 for r in new_records
            if isinstance(r, dict) and r.get("outcome") == "applied")
        result["failed"] = sum(
            1 for r in new_records
            if isinstance(r, dict) and r.get("outcome") == "failed")
        result["source_partial"] = sum(
            1 for r in new_records
            if isinstance(r, dict) and r.get("source_partial"))
        if rc != 3 and rc != 0:
            result["error"] = msg("process_exit_code", code=rc)
            return result

        # 复验（恒开）：重跑全片 AI 分析恰 1 次，建议件三键计数 diff
        report_txt = os.path.join(guide_dir, stem + self._AI_REPORT_SUFFIX)
        prog.update({"phase": "verify"})
        if not os.path.isfile(report_txt):
            result["verify"] = {"error": "报告 txt 缺失，跳过复验"}
            prog.update({"phase": "done"})
            return result
        vr = self.refine_ai_analyze(report_txt,
                                    (ai_model or "").strip() or None,
                                    ai_provider)
        if vr.get("success"):
            result["verify"] = {
                "before": pre_counts,
                "before_missing": pre_suggestion_missing,
                "after": self._suggestion_counts(guide_dir, stem),
                "provider_name": vr.get("provider_name"),
                "parse_ok": vr.get("parse_ok"),
            }
            result["suggestions"] = vr.get("suggestions") or {}
        else:
            # refine_ai_analyze 失败不落写建议件——修复前建议件原样保留（R4）
            result["verify"] = {"error": vr.get("error"),
                                "stderr_tail": vr.get("stderr_tail", "")}
        prog.update({"phase": "done"})
        return result

    def refine_batch_fix_progress(self) -> dict[str, Any]:
        """批修复进度快照（前端 1s 轮询；复刻 refine_dict_download_progress）。"""
        try:
            return dict(self._bf_progress())
        except Exception as e:
            _log_exc("refine_batch_fix_progress")
            return {"running": False, "phase": "failed", "done": 0,
                    "total": 0, "last_line": "", "error": str(e)}

    def _asr_probe_cache_path(self) -> str:
        """探测快照落点（tests 可 monkeypatch；fail-soft 返回 "" 禁用缓存）。"""
        try:
            from subtransjav.refine import asr_env
            return asr_env.probe_cache_path()
        except Exception:
            return ""

    def refine_asr_status(self, force: bool = False) -> dict[str, Any]:
        """零写路径探测＋已存 ASR 选择回显（设置 KV asr_model/asr_python）。

        2.6.1 修订（D2026-1002-06，模型推荐制）：新增 recommended（推荐
        清单逐条 present/path/expected_path）、models_dir/cache_dir（两处
        落位绝对路径）、crosscheck_enabled（设置 KV 回显）——下载链已删，
        前端只展示"自备落位指引"。既有键全保留。
        2.7.1（D2026-1005-01 承接批，评议 R5）：探测结果磁盘级快照缓存
        （数据根 config/asr_probe_cache.json，TTL 10 分钟）——非 force 且
        快照在龄→立即返回快照（probe_cached=True）；force（「重新探测」
        按钮）或超龄/缺失→同步探测并写回快照。models_hf=HF hub cache
        第 3 落位枚举（面板「需适配」来源）；triage/stderr_tail/ffmpeg_path
        三分类诊断透出。"""
        try:
            asr_python = ""
            asr_model = ""
            crosscheck_enabled = False
            try:
                got = self.refine_get_stage_settings()
                settings = (got or {}).get("settings") or {}
                asr_python = str(settings.get("asr_python") or "")
                asr_model = str(settings.get("asr_model") or "")
                crosscheck_enabled = \
                    str(settings.get("media_crosscheck_enabled") or "") == "1"
            except Exception:
                pass
            from subtransjav.refine import asr_env
            cache_path = self._asr_probe_cache_path()
            r: dict[str, Any] | None = None
            probe_cached = False
            if not force and cache_path:
                r = asr_env.load_probe_cache(cache_path)
                probe_cached = r is not None
            if r is None:
                r = asr_env.probe_asr_env(asr_python_setting=asr_python)
                if cache_path:
                    asr_env.save_probe_cache(r, cache_path)
            by_name = {m.get("name"): m for m in (r.get("models") or [])}
            recommended: list[dict[str, Any]] = []
            for entry in asr_env.ASR_RECOMMENDED_MODELS:
                stem = str(entry.get("model") or entry.get("name") or "")
                hit = by_name.get(stem)
                recommended.append({
                    **entry,
                    "present": hit is not None,
                    "path": str((hit or {}).get("path") or ""),
                    "expected_path": os.path.join(asr_env.ASR_MODELS_ROOT,
                                                  f"{stem}.pt"),
                })
            r["recommended"] = recommended
            r["models_dir"] = asr_env.ASR_MODELS_ROOT
            r["cache_dir"] = asr_env.ASR_CACHE_DIR
            r["crosscheck_enabled"] = crosscheck_enabled
            r["probe_cached"] = probe_cached
            r["probe_cache_path"] = cache_path
            r["success"] = True
            r["saved_model"] = asr_model
            r["saved_python"] = asr_python
            return r
        except Exception as e:
            _log_exc("refine_asr_status")
            return {"success": False, "error": str(e)}

    def refine_ai_apply_glossary(self, entries_json: str) -> dict[str, Any]:
        """把 AI 术语建议逐条锁定追加进词库（glossary.append_glossary_entries）。

        词库路径与 refine_get_glossary 同源（config.default_glossary_path）。
        entries_json 解析失败/非数组 → success=False。
        """
        try:
            entries = json.loads(entries_json)
        except (TypeError, ValueError):
            return {"success": False, "error": "entries_json 不是合法 JSON"}
        if not isinstance(entries, list):
            return {"success": False, "error": "entries_json 需为对象数组"}
        try:
            from subtransjav.refine.config import default_glossary_path
            from subtransjav.refine.glossary import append_glossary_entries
            gp = str(_resolve_safe_path(default_glossary_path()))
            results = append_glossary_entries(entries, gp)
            return {"success": True, "path": gp, "results": results}
        except Exception as e:
            _log_exc("refine_ai_apply_glossary")
            return {"success": False, "error": str(e)}

    def refine_ai_apply_tm(self, entries_json: str) -> dict[str, Any]:
        """把 AI TM 建议逐条存入翻译记忆库（缺省库路径）。

        每条附 conflict_warn：source 命中术语冲突观察闸 JSON
        （glossary_conflict_watch.json）中"未裁决冲突"（conflicts>0 且
        未被 manual_false_positive 标记）的源词集合。观察闸读取失败
        不阻断（warn 全 False）。
        """
        try:
            entries = json.loads(entries_json)
        except (TypeError, ValueError):
            return {"success": False, "error": "entries_json 不是合法 JSON"}
        if not isinstance(entries, list):
            return {"success": False, "error": "entries_json 需为对象数组"}
        try:
            from subtransjav.refine import glossary_conflict as gc
            from subtransjav.refine import tm as tm_mod

            conflicted: set[str] = set()
            try:
                records = gc.load_watch_records(gc.default_watch_path())
                for rec in records:
                    if not isinstance(rec, dict):
                        continue
                    mfp = rec.get("manual_false_positive") or {}
                    for term, info in (rec.get("per_term") or {}).items():
                        try:
                            n_conf = int((info or {}).get("conflicts", 0) or 0)
                        except (TypeError, ValueError):
                            n_conf = 0
                        if n_conf > 0 and term not in mfp:
                            conflicted.add(str(term))
            except Exception:   # noqa: BLE001 观察闸旁路数据，绝不阻断
                conflicted = set()

            db = tm_mod.TranslationMemory()
            results: list[dict] = []
            # 件4 埋点（2.7.4 批 D2026-1007-01）：疑似整段/长句入库特征
            # 聚合观测——每次调用至多一条 debug（防刷屏）；只记长度与句末
            # 标点计数（。！？），绝不记 TM 原文、不阻断不改落库行为。
            n_total = 0
            n_flagged = 0
            max_len = 0
            max_punct = 0
            try:
                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    src = str(e.get("source", "")).strip()
                    tgt = str(e.get("target", "")).strip()
                    if not src or not tgt:
                        continue
                    n_total += 1
                    punct = sum(src.count(c) for c in "。！？")
                    if len(src) > max_len:
                        max_len = len(src)
                    if punct > max_punct:
                        max_punct = punct
                    if punct >= 2 or len(src) > 100:
                        n_flagged += 1
                    added = db.store(src, tgt)
                    warn = src in conflicted or (
                        src.isascii() and src.lower() in conflicted)
                    results.append({"source": src, "target": tgt,
                                    "status": "added" if added else "exists",
                                    "conflict_warn": warn})
            finally:
                db.close()
            if n_flagged:
                _log.debug(
                    "refine_ai_apply_tm 疑似整段/长句入库特征: "
                    "flagged=%d total=%d max_len=%d max_sent_punct=%d",
                    n_flagged, n_total, max_len, max_punct)
            return {"success": True, "results": results}
        except Exception as e:
            _log_exc("refine_ai_apply_tm")
            return {"success": False, "error": str(e)}

    # ================================================================
    # 快速试听（2.0.0-beta 视听对比第二阶段，D2026-0929-09）
    # 注意：本段错误文案为内联中文（未进 strings.py），系任务边界限定
    # 改动面（api.py/assets/测试）所致，与上方 AI 分析段同口径。
    #
    # 媒体路径来源收窄（C-5 契约内选择）：
    #   ① 导读 json 的 media_path（v1.5 契约键，管线 resolve_media_path
    #      结果或 cfg.media_path 显式覆盖值）；
    #   ② 用户显式经 UI 输入框填写的 media_override（语义等价
    #      --media-path，经 _resolve_safe_path 校验）。
    # 无文件浏览对话框；无任意路径读取 API。
    #
    # direct/clip 判定矩阵（ffprobe 真实 codec）：
    #   容器 ∈ {mp4, m4a, webm, mov} 且 video ∈ {"", h264, vp8, vp9}
    #   且 audio ∈ {"", aac} → mode=direct（浏览器原生可播）；
    #   hevc/h265/opus 等边界编码 → 一律 ffmpeg 抽 [start-0.5s, end+0.5s]
    #   wav 片段兜底（mode=clip，list-args 禁 shell）；抽不了才失败。
    #   ffprobe 缺失：mp4/m4a（aac 语义）尝试 direct，其余报错。
    # ================================================================

    _AUDIO_PREVIEW_GUIDE_SUFFIX = "_质量报告导读.json"
    _AUDIO_PREVIEW_PAD_S = 0.5
    _AUDIO_PREVIEW_FFPROBE_TIMEOUT_S = 15
    _AUDIO_PREVIEW_EXTRACT_TIMEOUT_S = 120
    _AUDIO_PREVIEW_DIRECT_EXTS = {".mp4", ".m4a", ".webm", ".mov"}
    _AUDIO_PREVIEW_DIRECT_VIDEO = {"", "h264", "vp8", "vp9"}
    _AUDIO_PREVIEW_DIRECT_AUDIO = {"", "aac"}
    # 2.7.4 件2（D2026-1007-01）：试听媒体自动推断——视频扩展名闭集 +
    # 持久化 override LRU 上限（复用 refine_stage_settings.json settings KV）
    _AUDIO_PREVIEW_VIDEO_EXTS = frozenset(
        {".mp4", ".mkv", ".webm", ".mov", ".avi", ".m4v"})
    _MEDIA_OVERRIDES_KEY = "media_overrides"
    _MEDIA_OVERRIDES_MAX = 50

    def _media_override_key(self, guide_path: str) -> str:
        """media_overrides KV 键：normcase 归一化导读路径（Windows 语义）。"""
        from subtransjav.paths import normalize_path_case
        return normalize_path_case(str(guide_path or ""))

    def _load_media_overrides(self) -> dict[str, str]:
        """media_overrides KV 读取（settings 命名空间；缺省/损坏→空 dict）。

        经 refine_get_stage_settings 既有读取通道（本方法零自有 open——
        Mimosa path-traversal 消模式：api.py 零新增 open occurrence）。"""
        res = self.refine_get_stage_settings()
        if not res.get("success"):
            return {}
        settings = res.get("settings")
        ov = settings.get(self._MEDIA_OVERRIDES_KEY) \
            if isinstance(settings, dict) else None
        return {str(k): str(v) for k, v in ov.items()
                } if isinstance(ov, dict) else {}

    def refine_save_media_override(self, guide_path: str,
                                   media_path: str = "") -> dict[str, Any]:
        """「更换」apply 持久化（2.7.4 件2 owner 终版第 2 条）。

        写入 refine_stage_settings.json 顶层 settings 字典的
        media_overrides 命名空间：{normcase(guide_path): 媒体路径}——
        LRU 语义：重写键触尾、超 _MEDIA_OVERRIDES_MAX(50) 淘汰最旧；
        media_path 空串=删除该条（空表时该键存空 dict，读取端视为缺省）。
        落盘统一走 refine_save_stage_settings 既有通道（settings 按键合并、
        未知键保留；前端 refine_save_stage_settings(null, null, {...})
        service_quick 先例）——本方法零自有 open 写点（Mimosa
        path-traversal 消模式，甄别表 #29 先例：改代码消模式不挂账），
        对外响应契约 {success, overrides_saved} 不变。
        """
        try:
            gp = str(guide_path or "").strip()
            if not gp:
                return {"success": False, "error": "缺少导读文件路径"}
            overrides = self._load_media_overrides()
            key = self._media_override_key(gp)
            overrides.pop(key, None)   # LRU：重写即触尾
            mp = str(media_path or "").strip()
            if mp:
                overrides[key] = mp
            while len(overrides) > self._MEDIA_OVERRIDES_MAX:
                overrides.pop(next(iter(overrides)))
            res = self.refine_save_stage_settings(
                None, None, {self._MEDIA_OVERRIDES_KEY: overrides})
            if not res.get("success"):
                return {"success": False,
                        "error": str(res.get("error") or "持久化写入失败")}
            return {"success": True, "overrides_saved": len(overrides)}
        except Exception as e:
            _log_exc("refine_save_media_override")
            return {"success": False, "error": str(e)}

    def _infer_preview_media(self, guide_path: str,
                             clip_end_s: float) -> dict[str, Any]:
        """同目录自动推断试听媒体（2.7.4 件2 ④层，与试听同源唯一实现）。

        guide json 文件名剥导读后缀（复用 _AUDIO_PREVIEW_GUIDE_SUFFIX，不新增
        第 5 处字面量）→ 复用 asr_meta.strip_stem_suffixes 剥语言/管线后缀 →
        同目录（不递归）normcase 精确基名匹配视频扩展名闭集。2.7.4 件B
        （D2026-1007-02）：精确匹配按 _preview_stem_candidates 的 leveled
        候选序贯进行（首个产生命中的层即裁决：恰 1 个采用、多命中
        fail-closed），全层零命中再做边界感知前缀兜底。唯一命中再过
        时长守卫（fail-closed，owner 终版第 7 条）：复用 _review_media_duration
        （15s 超时元数据级），比较基准 clip_end=end+_AUDIO_PREVIEW_PAD_S，
        容差 max(5s, 1% 时长)；ffprobe 失败/None/时长不足一律拒绝自动采用。
        .ja 过度剥离边缘（如 song.ja.whisperjav 导读剥为 "song"，同目录仅有
        song.ja.mp4 时前缀兜底亦不命中——root "song.ja" 比 stem "song" 长，
        不构成 stem 前缀）→ 优雅降级 no_candidate，不误配。

        返回 {ok, media_path, media_source:"inferred"} 或
        {ok:False, error_key, error, candidates:[文件名,...]}——
        no_candidate（零命中/多命中，多命中带候选列表）/
        duration_mismatch / verify_failed。
        """
        from subtransjav.paths import normalize_path_case
        from subtransjav.refine.asr_meta import strip_stem_suffixes
        suffix = self._AUDIO_PREVIEW_GUIDE_SUFFIX
        base = os.path.basename(str(guide_path or ""))
        if not base.endswith(suffix) or len(base) <= len(suffix):
            return {"ok": False, "error_key": "no_candidate",
                    "error": f"非导读文件: {base}", "candidates": []}
        stem = strip_stem_suffixes(base[:-len(suffix)])
        gdir = os.path.dirname(os.path.abspath(str(guide_path)))
        try:
            names = os.listdir(gdir)
        except OSError:
            names = []
        # 预筛视频扩展名闭集候选（扩展名闭集与过滤口径不变）
        video_named: list[tuple[str, str, str]] = [
            (name, *os.path.splitext(name)) for name in names]
        # leveled 序贯匹配（2.7.4 件B）：按候选层序逐层做 normcase 精确
        # 基名匹配，首个产生命中的层即裁决——恰 1 个走时长守卫后采用；
        # 多于 1 个维持既有 fail-closed 多命中语义（不向更深层回退：
        # 近层歧义即歧义）。
        candidates: list[str] = []
        for cand in _preview_stem_candidates(stem):
            ckey = normalize_path_case(cand)
            candidates = [
                name for name, root, ext in video_named
                if ext.lower() in self._AUDIO_PREVIEW_VIDEO_EXTS
                and normalize_path_case(root) == ckey]
            if candidates:
                break
        if not candidates:
            # 前缀兜底（边界感知）：全部精确层零命中时，收集「候选文件
            # root + '.' 是 level 0 stem 前缀」的文件（即
            # stem.startswith(root + '.')）。'.' 边界防扩展伪装误配：
            # stem="X" 不以 "X.merged." 开头，故不误命中 "X.merged.mp4"；
            # 而 stem="X.ja.merged" 可前缀命中 root="X" 的文件。恰 1 个
            # 才走时长守卫后采用；0/多维持 no_candidate（多候选举证列表）。
            key0 = normalize_path_case(stem)
            candidates = [
                name for name, root, ext in video_named
                if ext.lower() in self._AUDIO_PREVIEW_VIDEO_EXTS
                and key0.startswith(normalize_path_case(root) + ".")]
        if not candidates:
            return {"ok": False, "error_key": "no_candidate",
                    "error": f"未在导读同目录找到与「{stem}」匹配的媒体文件",
                    "candidates": []}
        if len(candidates) > 1:
            sorted_hits = sorted(candidates)
            return {"ok": False, "error_key": "no_candidate",
                    "error": "同目录命中多个候选媒体，请显式指定: "
                             + "、".join(sorted_hits),
                    "candidates": sorted_hits}
        hit = candidates[0]
        hit_path = os.path.join(gdir, hit)
        dur = self._review_media_duration(hit_path)
        if dur is None:
            return {"ok": False, "error_key": "verify_failed",
                    "error": f"候选媒体元数据探测失败，拒绝自动采用: {hit}",
                    "candidates": [hit]}
        tolerance = max(5.0, dur * 0.01)
        if clip_end_s > dur + tolerance:
            return {"ok": False, "error_key": "duration_mismatch",
                    "error": f"候选媒体时长与试听时段不符: {hit}"
                             f"（媒体 {dur:.1f}s < 所需 {clip_end_s:.1f}s）",
                    "candidates": [hit]}
        return {"ok": True, "media_path": hit_path,
                "media_source": "inferred", "duration_s": round(dur, 3)}

    def refine_preview_infer_media(self, guide_path: str,
                                   clip_end_s: float = 0.0) -> dict[str, Any]:
        """试听媒体自动推断独立入口（复用 _infer_preview_media，零第二实现）。

        「重新自动匹配」按钮契约（err_kind=path_invalid 时前端错误槽内
        出现）：clip_end_s 缺省 0——无试听上下文时时长守卫退化为 ffprobe
        可读性验证（verify_failed 仍 fail-closed）；正式试听会再过完整守卫。
        """
        try:
            p = str(guide_path or "").strip()
            if not p:
                return {"ok": False, "error_key": "no_candidate",
                        "error": "缺少导读文件路径", "candidates": []}
            try:
                clip_end = max(0.0, float(clip_end_s))
            except (TypeError, ValueError):
                clip_end = 0.0
            return self._infer_preview_media(p, clip_end)
        except Exception as e:
            _log_exc("refine_preview_infer_media")
            return {"ok": False, "error_key": "verify_failed",
                    "error": str(e), "candidates": []}

    def _ffprobe_stream_codecs(self, media_path: str) -> dict | None:
        """ffprobe 取首路 video/audio 真实 codec（list-args 禁 shell）。

        ffprobe 缺失/失败一律返回 None（调用方按"不可判"分支处理）。"""
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None
        try:
            r = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries",
                 "stream=codec_type,codec_name", "-of", "json", media_path],
                capture_output=True,
                timeout=self._AUDIO_PREVIEW_FFPROBE_TIMEOUT_S,
                creationflags=CREATE_NO_WINDOW)  # windowed 防黑框（批0）
            if r.returncode != 0:
                return None
            data = json.loads(r.stdout.decode("utf-8", "replace"))
            codecs = {"video": "", "audio": ""}
            for st in data.get("streams") or []:
                if not isinstance(st, dict):
                    continue
                ct = str(st.get("codec_type") or "")
                name = str(st.get("codec_name") or "")
                if ct == "video" and not codecs["video"]:
                    codecs["video"] = name
                elif ct == "audio" and not codecs["audio"]:
                    codecs["audio"] = name
            return codecs
        except Exception:
            return None

    @staticmethod
    def _sweep_aged_files(dir_path: str, hours: int) -> int:
        """龄期清扫共享实现（批 3 技术债 f）：删除目录内超 hours 龄文件，
        目录不存在静默返回 0。"""
        try:
            cutoff = datetime.now().timestamp() - hours * 3600
            removed = 0
            for name in os.listdir(dir_path):
                p = Path(dir_path) / name
                try:
                    if p.is_file() and p.stat().st_mtime < cutoff:
                        p.unlink()
                        removed += 1
                except OSError:
                    continue
            return removed
        except Exception:
            return 0

    @staticmethod
    def _sweep_stale_preview_clips(preview_dir: str) -> int:
        """preview 片段受 audio_detect 既有 stale 时限管辖（批 3 技术债 f：
        薄壳委托 _sweep_aged_files，行为等价）。"""
        from subtransjav.refine.audio_detect import STALE_MAX_AGE_HOURS
        return TranslateAPI._sweep_aged_files(preview_dir, STALE_MAX_AGE_HOURS)

    @staticmethod
    def _extract_preview_wav(ffmpeg_path: str, media_path: str, out_path: str,
                             start_s: float, duration_s: float) -> None:
        """抽取 [start_s, start_s+duration_s] 的 16kHz 单声道 PCM WAV。

        audio_detect._extract_wav 仅整片抽取、不支持时段，故在 GUI 侧
        独立实现（同样 list-args 禁 shell，media_path 必须为契约路径）。
        失败时清理半截文件后抛 RuntimeError。"""
        try:
            r = subprocess.run(
                [ffmpeg_path, "-y", "-ss", f"{start_s:.3f}", "-i",
                 media_path, "-t", f"{duration_s:.3f}", "-vn", "-ac", "1",
                 "-ar", "16000", out_path],
                capture_output=True,
                timeout=TranslateAPI._AUDIO_PREVIEW_EXTRACT_TIMEOUT_S,
                creationflags=CREATE_NO_WINDOW)  # windowed 防黑框（批0）
        except Exception:
            with contextlib.suppress(OSError):
                os.unlink(out_path)
            raise
        if r.returncode != 0 or not os.path.isfile(out_path):
            with contextlib.suppress(OSError):
                os.unlink(out_path)
            raise RuntimeError(
                f"ffmpeg 抽取试听片段失败 (rc={r.returncode}): "
                f"{(r.stderr or b'')[-200:]!r}")

    def refine_audio_preview(self, report_key_or_path: str,
                             timing_start_s: float, timing_end_s: float,
                             media_override: str = "") -> dict[str, Any]:
        """质量导读条目快速试听（全容错不抛，前端显示错误条）。

        返回 {ok, mode:"direct", media_path, media_source} 或
        {ok, mode:"clip", data_url, media_path, media_source, duration_s}，
        失败 {ok:false, error, error_key?}——error_key 四态
        no_candidate/duration_mismatch/verify_failed/path_invalid
        （2.7.4 件2 结构化错误，前端按 key 驱动、禁靠中文文案匹配）。
        """
        try:
            return self._refine_audio_preview_impl(
                report_key_or_path, timing_start_s, timing_end_s,
                media_override)
        except Exception as e:
            _log_exc("refine_audio_preview")
            return {"ok": False, "error": str(e)}

    def _refine_audio_preview_impl(self, report_key_or_path: str,
                                   timing_start_s: float,
                                   timing_end_s: float,
                                   media_override: str) -> dict[str, Any]:
        p = str(report_key_or_path or "").strip()
        if not p:
            return {"ok": False, "error": "缺少导读文件路径"}
        suffix = self._AUDIO_PREVIEW_GUIDE_SUFFIX
        if not p.endswith(suffix):
            return {"ok": False,
                    "error": f"仅支持 {suffix} 导读文件: "
                             f"{os.path.basename(p)}"}
        # 复用既有导读读取链的路径解析与安全锚（_validate_user_directory
        # + 后缀白名单 + JSON 解析）
        got = self.read_output_artifact(p)
        if not got.get("success"):
            return {"ok": False,
                    "error": str(got.get("error") or "导读读取失败")}
        data = got.get("data")

        # timing 越界钳制：start ≥ 0；end ≥ start；零长时段拒绝
        # （件2 前移：时长守卫基准 clip_end 依赖 end，须先于媒体解析）
        try:
            start = max(0.0, float(timing_start_s))
        except (TypeError, ValueError):
            start = 0.0
        try:
            end = max(start, float(timing_end_s))
        except (TypeError, ValueError):
            end = start
        if end - start <= 0:
            return {"ok": False, "error": "试听时段无效（起止时间）"}

        # —— 试听媒体路径四层优先级（2.7.4 件2，评议员钉测）——
        # ① 本次请求显式 override > ② guide json 自带 media_path（文件有效
        # 时）> ③ GUI 持久化配置 > ④ 同目录自动推断。②失效（文件不存在/
        # ffprobe 失败）才落 ③④——不自动覆盖有效已有路径（owner 裁定）。
        # 结构化错误四态（沿用 error_key 先例，前端禁靠中文文案匹配）：
        # no_candidate / duration_mismatch / verify_failed / path_invalid。
        guide_media = str((data or {}).get("media_path") or "")
        failed_existing: list[str] = []   # 已有路径失效（path_invalid 汇报）
        media = ""
        media_source = ""
        if str(media_override or "").strip():
            try:
                media = str(_resolve_safe_path(str(media_override).strip()))
            except ValueError as ve:
                return {"ok": False, "error_key": "path_invalid",
                        "error": f"媒体路径不在允许的目录下: {ve}"}
            if not os.path.isfile(media):
                return {"ok": False, "error_key": "path_invalid",
                        "error": f"媒体文件不存在: {media}"}
            media_source = "override"
        if not media and guide_media:
            gp = ""
            try:
                gp = str(_resolve_safe_path(guide_media))
            except ValueError:
                gp = ""
            if not gp or not os.path.isfile(gp):
                # 安全锚拒绝/文件不存在 → ②失效，落 ③④
                failed_existing.append(guide_media)
            elif self._review_media_duration(gp) is not None:
                media = gp
                media_source = "guide"
            elif shutil.which("ffprobe") is None:
                # ffprobe 二进制缺席：无法验证亦无法否证——保持既有
                # no-ffmpeg 降级契约（mp4/m4a direct 或 clip 自然报错），
                # 不据此判 ②失效
                media = gp
                media_source = "guide"
            else:
                # ffprobe 可用但探测失败 → ②失效，落 ③④
                failed_existing.append(guide_media)
        if not media:
            # ③ GUI 持久化配置（media_overrides KV；失效仅记录不阻塞）
            persisted = self._load_media_overrides().get(
                self._media_override_key(p))
            if persisted:
                pp = ""
                try:
                    pp = str(_resolve_safe_path(persisted))
                except ValueError:
                    pp = ""
                if pp and os.path.isfile(pp):
                    media = pp
                    media_source = "persisted"
                else:
                    failed_existing.append(persisted)
        infer_res: dict[str, Any] | None = None
        if not media:
            # ④ 同目录自动推断（fail-closed 时长守卫，唯一实现见
            # _infer_preview_media；re-match 入口复用同一实现）
            infer_res = self._infer_preview_media(
                p, end + self._AUDIO_PREVIEW_PAD_S)
            if infer_res.get("ok"):
                media = str(infer_res["media_path"])
                media_source = "inferred"
        if not media:
            if failed_existing:
                return {"ok": False, "error_key": "path_invalid",
                        "error": "已有媒体路径失效: "
                                 + "；".join(failed_existing),
                        "candidates": (infer_res or {}).get("candidates", [])}
            if infer_res is not None:
                return infer_res
            return {"ok": False, "error_key": "no_candidate",
                    "error": "导读未包含媒体路径，请在媒体来源中显式指定",
                    "candidates": []}

        ext = os.path.splitext(media)[1].lower()
        codecs = self._ffprobe_stream_codecs(media)
        if codecs is not None:
            direct = _codec_direct(ext, codecs,
                                   self._AUDIO_PREVIEW_DIRECT_EXTS,
                                   self._AUDIO_PREVIEW_DIRECT_VIDEO,
                                   self._AUDIO_PREVIEW_DIRECT_AUDIO)
            if direct:
                return {"ok": True, "mode": "direct", "media_path": media,
                        "media_source": media_source, "codec_probe": True}
        else:
            # ffprobe 缺失/失败：mp4/m4a（aac 语义）尝试 direct；
            # 其余容器无法解码判定 → 无 ffmpeg 即报错
            if ext in (".mp4", ".m4a"):
                return {"ok": True, "mode": "direct", "media_path": media,
                        "media_source": media_source, "codec_probe": False}
            if shutil.which("ffmpeg") is None:
                return {"ok": False,
                        "error": "未检测到 ffmpeg，无法解码该容器",
                        "error_key": "no_ffmpeg"}

        # clip 兜底：hevc/opus 等边界编码或 codec 不可判时抽 wav 片段
        from subtransjav.refine import audio_detect as ad
        from subtransjav.refine.config import TEMP_DIR
        ff = ad._find_ffmpeg()
        if ff is None:
            return {"ok": False, "error": "未检测到 ffmpeg，无法解码该容器",
                    "error_key": "no_ffmpeg"}
        clip_start = max(0.0, start - self._AUDIO_PREVIEW_PAD_S)
        clip_end = end + self._AUDIO_PREVIEW_PAD_S
        duration = clip_end - clip_start
        preview_dir = Path(TEMP_DIR) / ad.AUDIO_DETECT_SUBDIR / "preview"
        try:
            os.makedirs(preview_dir, exist_ok=True)
        except OSError as e:
            return {"ok": False, "error": f"试听临时目录创建失败: {e}"}
        self._sweep_stale_preview_clips(str(preview_dir))
        identity = f"{media}|{clip_start:.3f}|{clip_end:.3f}"
        h = hashlib.sha1(identity.encode("utf-8", "replace")).hexdigest()[:12]
        out_path = str(preview_dir / f"pv_{h}.wav")
        if not os.path.isfile(out_path):    # 同参数复播直接复用既有片段
            try:
                self._extract_preview_wav(ff, media, out_path,
                                          clip_start, duration)
            except Exception as e:
                return {"ok": False,
                        "error": f"试听片段抽取失败: {e}"}
        try:
            with open(out_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode("ascii")
        except OSError as e:
            return {"ok": False, "error": f"试听片段读取失败: {e}"}
        return {"ok": True, "mode": "clip",
                "data_url": f"data:audio/wav;base64,{b64}",
                "media_path": media, "media_source": media_source,
                "duration_s": round(duration, 3), "clip_path": out_path}

    # ================================================================
    # 校对页（2.6.1 批 2a D2026-1002-09）：媒体导入 / 三态探测 / 手动转码 / SRT 载入
    # 直接播判定矩阵沿用 audio preview 语义（批清单 §2）；转码产物 24h 龄
    # sweep（术语漂移登记：audio_preview 先例）；全部容错不抛 + msg() 文案。
    #
    # error_key 映射表（批 3 技术债 i：后端错误点 → 前端 REVIEW_MSG 键名，
    # 显式映射防暗合；前端按 key 查表优先、回退 error 文本）：
    #   review_backup_failed        -> review_save_failed
    #   review_save_blocks_invalid  -> review_save_failed
    #   review_srt_bad_encoding     -> review_bad_encoding
    # ================================================================

    _REVIEW_DIRECT_EXTS = {".mp4", ".webm", ".mov"}
    _REVIEW_DIRECT_VIDEO = {"h264", "vp8", "vp9"}
    _REVIEW_DIRECT_AUDIO = {"", "aac", "mp3"}
    _REVIEW_TRANSCODE_SUBDIR = "review_transcode"
    _REVIEW_SWEEP_MAX_AGE_HOURS = 24
    _REVIEW_FFPROBE_TIMEOUT_S = 15

    def _review_state(self) -> dict:
        """转码状态 dict + 锁的惰性初始化（object.__new__ 测试实例兼容）。"""
        state = getattr(self, "_review_transcode_state", None)
        if state is None:
            state = {"running": False, "percent": None, "error": None,
                     "path": None, "cached": False}
            self._review_transcode_state = state
        if getattr(self, "_review_lock", None) is None:
            self._review_lock = threading.Lock()
        return state

    def refine_review_pick_media(self) -> dict[str, Any]:
        """校对页视频文件选择对话框（create_file_dialog 先例；cancelled 标记）"""
        try:
            windows = webview.windows
            if not windows:
                return {"success": False, "error": msg("no_active_window")}
            result = self._open_file_dialog(
                (msg("file_type_video"), msg("file_type_all")))
            if result:
                return {"success": True, "path": result[0]}
            return {"success": False, "cancelled": True,
                    "error": msg("dialog_cancelled")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def refine_review_pick_srt(self) -> dict[str, Any]:
        """校对页字幕文件选择对话框（同上）"""
        try:
            windows = webview.windows
            if not windows:
                return {"success": False, "error": msg("no_active_window")}
            result = self._open_file_dialog(
                (msg("file_type_srt"), msg("file_type_all")))
            if result:
                return {"success": True, "path": result[0]}
            return {"success": False, "cancelled": True,
                    "error": msg("dialog_cancelled")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _review_media_duration(self, media_path: str) -> float | None:
        """ffprobe format=duration 探测（秒）；缺失/失败返回 None。"""
        ffprobe = shutil.which("ffprobe")
        if not ffprobe:
            return None
        try:
            r = subprocess.run(
                [ffprobe, "-v", "error", "-show_entries", "format=duration",
                 "-of", "json", media_path],
                capture_output=True, timeout=self._REVIEW_FFPROBE_TIMEOUT_S,
                creationflags=CREATE_NO_WINDOW)  # windowed 防黑框（批0）
            if r.returncode != 0:
                return None
            data = json.loads(r.stdout.decode("utf-8", "replace"))
            value = (data.get("format") or {}).get("duration")
            return float(value) if value is not None else None
        except Exception:
            return None

    def refine_review_probe_media(self, path: str) -> dict[str, Any]:
        """三态探测：direct（浏览器原生可播）/ clip-audio（需转码）/ error。

        direct = video∈{h264,vp8,vp9} ∧ audio∈{"",aac,mp3}（批清单 §2）；
        ffprobe 缺失/失败：mp4/webm/mov 乐观 direct（codec_probe=False，
        与 audio preview 同口径），其余容器 error。
        """
        try:
            p = str(path or "")
            if not p or not os.path.isfile(p):
                return {"state": "error", "codec_probe": False,
                        "error": msg("review_media_missing")}
            ext = os.path.splitext(p)[1].lower()
            codecs = self._ffprobe_stream_codecs(p)
            duration = self._review_media_duration(p)
            if codecs is not None:
                direct = _codec_direct(ext, codecs,
                                       self._REVIEW_DIRECT_EXTS,
                                       self._REVIEW_DIRECT_VIDEO,
                                       self._REVIEW_DIRECT_AUDIO)
                return {"state": "direct" if direct else "clip-audio",
                        "codec_probe": True, "codecs": codecs,
                        "duration": duration}
            if ext in self._REVIEW_DIRECT_EXTS:
                return {"state": "direct", "codec_probe": False,
                        "duration": duration}
            return {"state": "error", "codec_probe": False,
                    "error": msg("review_probe_failed")}
        except Exception as e:
            return {"state": "error", "codec_probe": False, "error": str(e)}

    @staticmethod
    def _sweep_review_transcode(transcode_dir: str) -> int:
        """转码产物 24h 龄清扫（批 3 技术债 f：薄壳委托 _sweep_aged_files）。"""
        return TranslateAPI._sweep_aged_files(transcode_dir, 24)

    def refine_review_start_transcode(self, path: str) -> dict[str, Any]:
        """后台线程转码为直连可播 mp4（hevc 等边界编码兜底）。

        - 三态 direct 时拒绝（review_transcode_no_need）；
        - 目标件 ``Temp/review_transcode/rt_{sha256(path+mtime+size)[:12]}.mp4``
          已存在且完整性校验通过（ffprobe 探到正时长，审计③b）→ cached 复用，
          否则视为无效 cache 走重转码；
        - per-media 在飞锁（审计③d）：同一媒体转码中重复调用幂等返回
          "转码中"，完成后移除；
        - 超时 = duration×3+120s 杀进程置 error（可重试，半截产物随失败
          清理，审计③a）；
        - 进度经 refine_review_transcode_status 轮询。
        """
        try:
            p = str(path or "")
            if not p or not os.path.isfile(p):
                return {"success": False, "error": msg("review_media_missing")}
            state = self._review_state()
            lock = self._review_lock
            with lock:
                if state.get("running"):
                    return {"success": False,
                            "error": msg("review_transcode_running")}
            codecs = self._ffprobe_stream_codecs(p)
            if codecs is not None and codecs["video"] in self._REVIEW_DIRECT_VIDEO:
                return {"success": False, "error": msg("review_transcode_no_need")}
            from subtransjav.refine import audio_detect as ad
            from subtransjav.refine.config import TEMP_DIR
            ff = ad._find_ffmpeg()
            if ff is None:
                return {"success": False, "error": msg("review_no_ffmpeg")}
            out_dir = Path(TEMP_DIR) / self._REVIEW_TRANSCODE_SUBDIR
            os.makedirs(out_dir, exist_ok=True)
            self._sweep_review_transcode(str(out_dir))
            identity = f"{p}|{os.path.getmtime(p)}|{os.path.getsize(p)}"
            digest = hashlib.sha256(identity.encode("utf-8", "replace")).hexdigest()[:12]
            out_path = str(out_dir / f"rt_{digest}.mp4")
            key = os.path.normcase(p)
            if os.path.isfile(out_path) and os.path.getsize(out_path) > 0:
                # 审计③b：cache 命中前完整性校验——kill 残留半截件"存在且
                # 非空"但不可解码，ffprobe 探不到正时长即视为无效 cache，
                # 落到下方重转码（ffmpeg -y 覆盖写）。cache 命中本就是低频
                # 路径，逐次付一次 ffprobe 探测可接受。
                cached_dur = self._review_media_duration(out_path)
                if cached_dur is not None and cached_dur > 0:
                    return {"success": True, "cached": True, "path": out_path}
            duration = self._review_media_duration(p) or 0.0
            timeout_s = duration * 3 + 120
            with lock:
                # 审计③d：running/在飞判定 + add 原子化（探测窗口内的
                # 双击第二次进入在此幂等返回"转码中"，不落双线程写）
                if state.get("running") or key in _REVIEW_TRANSCODE_INFLIGHT:
                    return {"success": False,
                            "error": msg("review_transcode_running")}
                _REVIEW_TRANSCODE_INFLIGHT.add(key)
                state.update({"running": True, "percent": None, "error": None,
                              "path": out_path, "cached": False})

            def _worker() -> None:
                def _cb(seconds: float) -> None:
                    if duration > 0:
                        pct = min(100.0, seconds / duration * 100.0)
                        with lock:
                            state["percent"] = round(pct, 1)

                try:
                    ok, err = _transcode_sync(ff, p, out_path, timeout_s, _cb)
                    with lock:
                        state["running"] = False
                        if ok:
                            state["percent"] = 100.0
                        else:
                            state["error"] = err or msg("review_transcode_failed")
                finally:
                    _REVIEW_TRANSCODE_INFLIGHT.discard(key)

            try:
                threading.Thread(target=_worker, daemon=True,
                                 name="review-transcode").start()
            except Exception:
                # spawn 失败（极端边界）：解除在飞标记，防媒体被永久锁死
                _REVIEW_TRANSCODE_INFLIGHT.discard(key)
                with lock:
                    state["running"] = False
                raise
            estimated_s = int(duration / 0.25) if duration > 0 else 0
            return {"success": True, "started": True,
                    "estimated_s": estimated_s, "path": out_path}
        except Exception as e:
            _log_exc("refine_review_start_transcode")
            return {"success": False, "error": str(e)}

    def refine_review_transcode_status(self) -> dict[str, Any]:
        """转码状态快照（前端 800ms 轮询；无任务时零值字典）。"""
        state = getattr(self, "_review_transcode_state", None) or {}
        return {"running": bool(state.get("running")),
                "percent": state.get("percent"),
                "error": state.get("error"),
                "path": state.get("path"),
                "cached": bool(state.get("cached"))}

    def refine_review_load_srt(self, path: str,
                               include_raw: bool = False) -> dict[str, Any]:
        """嗅探编码读 SRT → cleaner_rules.parse_srt（ms 原生）→ 结构化 blocks。

        timing 字符串由 ms 重建（HH:MM:SS,mmm）；include_raw 为批 2b 编辑
        通道预留参数（本批不消费）。
        """
        try:
            p = str(path or "")
            if not p or not os.path.isfile(p):
                return {"success": False, "error": msg("review_srt_missing")}
            from subtransjav.refine.srt_encoding import sniff_text_encoding
            data = Path(p).read_bytes()
            enc, trusted = sniff_text_encoding(data)
            if not trusted:
                return {"success": False, "error": msg("review_srt_bad_encoding"),
                        "error_key": "review_bad_encoding"}
            content = data.decode(enc)
            from subtransjav.refine.cleaner_rules import parse_srt
            blocks = [
                {
                    "index": int(it.index),
                    "start_ms": int(it.start),
                    "end_ms": int(it.end),
                    "timing": (f"{_ms_to_srt_time(it.start)} --> "
                               f"{_ms_to_srt_time(it.end)}"),
                    "text": it.text,
                }
                for it in parse_srt(content)
            ]
            return {"success": True, "encoding": enc,
                    "count": len(blocks), "blocks": blocks}
        except Exception as e:
            _log_exc("refine_review_load_srt")
            return {"success": False, "error": str(e)}

    def refine_review_load_detections(self, guide_path: str) -> dict[str, Any]:
        """疑点段加载（批 3 D2026-1002-11）：复用 _load_validated_guide
        白名单读法 → 过滤 items 带 timing（无时间戳=非疑点段）→
        8 字段透传 {index,timing,category,message,current_text,
        source_excerpt,status,severity} + media_path（空串→None）。"""
        try:
            p, stem, guide, err = self._load_validated_guide(guide_path)
            if err:
                return {"success": False,
                        "error": str(err.get("error") or err)}
            items = (guide or {}).get("items") or []
            detections = []
            for it in items:
                if not isinstance(it, dict):
                    continue
                timing = str(it.get("timing") or "").strip()
                if not timing:
                    continue
                detections.append({
                    "index": it.get("index"),
                    "timing": timing,
                    "category": it.get("category"),
                    "message": it.get("message"),
                    "current_text": it.get("current_text"),
                    "source_excerpt": it.get("source_excerpt"),
                    "status": it.get("status"),
                    "severity": it.get("severity"),
                })
            media_path = (guide or {}).get("media_path") or None
            return {"success": True, "detections": detections,
                    "media_path": media_path, "count": len(detections)}
        except Exception as e:
            _log_exc("refine_review_load_detections")
            return {"success": False, "error": str(e)}

    @staticmethod
    def _review_validate_blocks(blocks: Any) -> str | None:
        """C8 结构校验：blocks 须为非空 list、每项含 start_ms/end_ms/text
        且 ms 可转 int。合法返回 None，否则返回错误键。"""
        if not isinstance(blocks, list) or not blocks:
            return "review_save_blocks_invalid"
        for it in blocks:
            if not isinstance(it, dict):
                return "review_save_blocks_invalid"
            try:
                int(it["start_ms"])
                int(it["end_ms"])
            except (KeyError, TypeError, ValueError):
                return "review_save_blocks_invalid"
            if "text" not in it:
                return "review_save_blocks_invalid"
        return None

    def refine_review_save_srt(self, path: str, blocks: Any,
                               mode: str = "overwrite") -> dict[str, Any]:
        """校对结果保存（D2026-1002-10）：备份先行 → 原子写 UTF-8 重写。

        - D3 重编号不变式：输出序号恒按数组位置 enumerate(blocks, 1)，
          时间轴 ms 由 start_ms/end_ms 重建（跳号源文件合法，行内 index
          字段仅展示用、不参与输出）；
        - D2 备份单份滚动固定名 {原名}.bak.srt（overwrite/force 同规则）：
          shutil.copy2 失败重试一次，再失败中止且**原文件未动**；
        - mode='force'（另存为确认后）：跳过调用方 exists 判定直接走
          备份+写（两段式第二段）；
        - 审计①收口（批1a 件5）：放行 = _review_save_allowed
          （动态根 ∪ 持久登记 ∪ 会话登记），越界写盘在备份前即拒绝。
        """
        try:
            p = str(path or "")
            if not p:
                return {"success": False, "error": msg("review_srt_missing")}
            invalid = self._review_validate_blocks(blocks)
            if invalid:
                return {"success": False, "error": msg(invalid),
                        "error_key": "review_save_failed"}
            # 审计②（D2026-1002-12）写入端 sanitize：块内空行压平（见
            # _review_sanitize_block_text），杜绝非常规文本被下次解析改写
            blocks = [
                {**it, "text": _review_sanitize_block_text(str(it["text"]))}
                for it in blocks
            ]
            safe = _review_save_allowed(p)
            target = Path(safe)
            backup_path = None
            if target.exists():
                backup_path = str(target) + BACKUP_SUFFIX
                last_err: Exception | None = None
                for _ in range(2):  # D2：失败重试一次
                    try:
                        shutil.copy2(str(target), backup_path)
                        last_err = None
                        break
                    except (PermissionError, OSError) as e:
                        last_err = e
                if last_err is not None:
                    return {"success": False,
                            "error": f"{msg('review_backup_failed')}: {last_err}",
                            "error_key": "review_save_failed"}
            parts = []
            for i, it in enumerate(blocks, 1):
                # 块内单换行、块间空行（多行文本内部 \n 原样保留）
                parts.append(f"{i}\n"
                             f"{_ms_to_srt_time(int(it['start_ms']))} --> "
                             f"{_ms_to_srt_time(int(it['end_ms']))}\n"
                             f"{it['text']}")
            text = "\n\n".join(parts) + "\n"
            _write_srt_atomic(safe, text)
            result: dict[str, Any] = {"success": True, "count": len(blocks),
                                      "bytes": len(text.encode("utf-8"))}
            if backup_path:
                result["backup_path"] = backup_path
            return result
        except Exception as e:
            _log_exc("refine_review_save_srt")
            return {"success": False, "error": str(e)}

    def refine_review_saveas_srt(self, blocks: Any,
                                 target_path: str) -> dict[str, Any]:
        """另存为第一段（批 3 技术债 c：删 src_path 死形参）：目标已存在 →
        exists 标记不写（前端确认后走 refine_review_save_srt(mode='force')
        两段式）；不存在 → 直接原子写。"""
        try:
            t = str(target_path or "")
            if not t:
                return {"success": False, "error": msg("review_srt_missing")}
            invalid = self._review_validate_blocks(blocks)
            if invalid:
                return {"success": False, "error": msg(invalid),
                        "error_key": "review_save_failed"}
            safe_t = _review_save_allowed(t)
            if Path(safe_t).exists():
                return {"success": False, "exists": True}
            return self.refine_review_save_srt(safe_t, blocks, mode="force")
        except Exception as e:
            _log_exc("refine_review_saveas_srt")
            return {"success": False, "error": str(e)}

    def refine_review_pick_save_path(self, default_name: str = "校对.srt") -> dict[str, Any]:
        """另存为保存路径对话框（webview.SAVE_DIALOG 先例 refine_pick_csv_save）。

        审计①收口（批1a 件5）：对话框返回路径（用户受信入口）即时登记
        进会话集，保证后续 refine_review_saveas_srt 对任意盘目标放行。
        """
        try:
            windows = webview.windows
            if not windows:
                return {"success": False, "error": msg("no_active_window")}
            result = self._open_file_dialog(
                (msg("file_type_srt"), msg("file_type_all")), save=True,
                default_name=str(default_name or "校对.srt"))
            if result:
                register_session_paths([result])
                return {"success": True, "path": result}
            return {"success": False, "cancelled": True,
                    "error": msg("dialog_cancelled")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # 翻译记忆库 (Translation Memory) API
    # ================================================================

    def tm_get_stats(self, db_path: str = None) -> dict[str, Any]:
        """获取翻译记忆库统计信息"""
        try:
            from subtransjav.refine.tm import TranslationMemory
            if db_path:
                db_path = str(_resolve_safe_path(db_path))
            tm = TranslationMemory(db_path) if db_path else TranslationMemory()
            try:
                stats = tm.stats()
                return {"success": True, **stats}
            finally:
                tm.close()
        except Exception as e:
            _log_exc("tm_get_stats")
            return {"success": False, "error": str(e)}

    def tm_search(self, query: str = "", limit: int = 50,
                  db_path: str = None) -> dict[str, Any]:
        """FTS 搜索翻译记忆库（2.6.4 批1 只读面，D2026-1003-05 策略 B）。

        镜像 tm_get_stats 的 db 路径解析与错误信封（success/error，读侧
        零写路径）；query 为空返回空结果集不报错（前端空态展示）。
        """
        try:
            from subtransjav.refine.tm import TranslationMemory
            if db_path:
                db_path = str(_resolve_safe_path(db_path))
            tm = TranslationMemory(db_path) if db_path else TranslationMemory()
            try:
                results = tm.search(str(query or ""), limit=limit)
                return {"success": True, "results": results,
                        "count": len(results)}
            finally:
                tm.close()
        except Exception as e:
            _log_exc("tm_search")
            return {"success": False, "error": str(e)}

    def tm_clear(self, stage: int = None, db_path: str = None) -> dict[str, Any]:
        """清空翻译记忆库。

        Args:
            stage: 指定阶段 (0/1/2)，None=清空全部
            db_path: 自定义数据库路径
        """
        try:
            from subtransjav.refine.tm import TranslationMemory
            if db_path:
                db_path = str(_resolve_safe_path(db_path))
            tm = TranslationMemory(db_path) if db_path else TranslationMemory()
            try:
                tm.clear(stage)
                return {"success": True, "message": msg("tm_cleared")}
            finally:
                tm.close()
        except Exception as e:
            _log_exc("tm_clear")
            return {"success": False, "error": str(e)}

    def tm_export_csv(self, path: str = None,
                      stage: int = None, db_path: str = None) -> dict[str, Any]:
        """导出翻译记忆库为 CSV"""
        try:
            from subtransjav.refine.tm import TranslationMemory
            if not path:
                return {"success": False, "error": msg("tm_export_path_missing")}
            path = str(_resolve_safe_path(path))
            if db_path:
                db_path = str(_resolve_safe_path(db_path))
            tm = TranslationMemory(db_path) if db_path else TranslationMemory()
            try:
                tm.export_csv(path, stage)
                return {"success": True, "path": path}
            finally:
                tm.close()
        except Exception as e:
            _log_exc("tm_export_csv")
            return {"success": False, "error": str(e)}

    def tm_import_csv(self, path: str = None,
                      db_path: str = None) -> dict[str, Any]:
        """从 CSV 导入翻译记忆库"""
        try:
            from subtransjav.refine.tm import TranslationMemory
            if not path:
                return {"success": False, "error": msg("tm_import_path_missing")}
            path = str(_resolve_safe_path(path))
            if db_path:
                db_path = str(_resolve_safe_path(db_path))
            tm = TranslationMemory(db_path) if db_path else TranslationMemory()
            try:
                added = tm.import_csv(path)
                return {"success": True, "added": added,
                        "message": msg("tm_imported", n=added)}
            finally:
                tm.close()
        except Exception as e:
            _log_exc("tm_import_csv")
            return {"success": False, "error": str(e)}

    def tm_pick_db(self) -> dict[str, Any]:
        """打开翻译记忆库数据库文件选择对话框"""
        try:
            windows = webview.windows
            if not windows:
                return {"success": False, "error": msg("no_active_window")}
            result = self._open_file_dialog(
                (msg("file_type_sqlite"), msg("file_type_all")))
            if result:
                return {"success": True, "path": result[0]}
            return {"success": False, "error": msg("dialog_cancelled")}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ================================================================
    # Cleanup
    # ================================================================

    def cleanup_refine_tmp_dirs(self) -> dict[str, Any]:
        """手动清理 refine 临时目录（退出钩子亦调用此逻辑）"""
        import shutil
        cleaned = []
        for d in dict.fromkeys(getattr(self, "_refine_tmp_dirs", [])):
            try:
                if d and os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)
                    cleaned.append(d)
            except Exception:
                pass
        if getattr(self, "_refine_tmp_dirs", None):
            self._refine_tmp_dirs.clear()
        return {"success": True, "cleaned": cleaned}

    def _on_exit_cleanup(self):
        """GUI 进程退出：终止残留子进程 + 清理 refine 临时目录"""
        proc = getattr(self, "_translate_process", None)
        # Ignore sentinel (True) — means start_translation never completed
        if proc is True:
            proc = None
        try:
            if proc and proc.poll() is None:
                if PSUTIL_AVAILABLE:
                    terminate_process_tree(proc.pid)
                else:
                    proc.terminate()
                try:
                    proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    # v1.3.2 task4：先给 3 秒优雅退出，仍存活则整树击杀（原为单杀）
                    if not terminate_process_tree_robust(proc.pid):
                        proc.kill()
        except Exception:
            pass
        with self._translate_lock:
            self._translate_process = None
        import shutil
        for d in dict.fromkeys(getattr(self, "_refine_tmp_dirs", [])):
            try:
                if d and os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        if getattr(self, "_refine_tmp_dirs", None):
            self._refine_tmp_dirs.clear()
