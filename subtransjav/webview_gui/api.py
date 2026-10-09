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
from collections import Counter
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


# ---------------------------------------------------------------------------
# 登记子进程治理（批4 D2026-1008-01，HRO-1 方案A + owner 拍板⑤ P1-P4）：
# 分析/修复子进程 spawn 时登记（槽 + 台账 child_procs.json），取消/退出
# 一律走 terminate_registered 身份核验（PID 复用防误杀），GUI 启动时按
# 台账自愈清理上次会话残留（P3 预案核心）。主翻译链不经此机制（语义零变化）。
# ---------------------------------------------------------------------------

# 台账文件名：数据根 config/child_procs.json（与 asr 探测快照/hardsub_last
# 同 CONFIG_DIR 锚）；覆盖式原子写（fs_utils 既有），条目即当前登记快照。
_CHILD_PROCS_LEDGER_NAME = "child_procs.json"
# kind → 该类子进程必带的 CLI 旗标（身份核验第③重的一部分）
_CHILD_KIND_MARKERS = {
    "ai_analyze": "--ai-analyze",
    "batch_fix": "--action-retranslate",
    # P1 分析模型预热（D2026-1008-02 批3）：登记后台账/启动自愈自动覆盖
    "warmup": "--warmup-analysis",
}
# 项目标记：cmdline 须含其一（源码形态模块名 / frozen CLI 可执行体名）
_CHILD_PROJECT_TOKENS = ("subtransjav", "subtrans-cli")
# create_time 匹配容差（秒）：同机时钟粒度内的两次采样视为同一进程
_CHILD_CREATE_TIME_TOL_S = 1.5


def _child_procs_ledger_path() -> str:
    """子进程台账落点（函数化便于测试打桩隔离）。"""
    from subtransjav.refine.config import CONFIG_DIR
    return os.path.join(str(CONFIG_DIR), _CHILD_PROCS_LEDGER_NAME)


# 全链自动修复分类白名单（批1 a 段，D2026-1009-02 批1 a 段 d 项）：grep
# quality_report.py 全部 guide item category 赋值点得闭集——来源 A
# structured_warnings（post_validate.py _record 三处："dewei"/"subject"/
# 动态规则名）、来源 B "untranslated"、来源 E "cps_too_fast"。来源 C
# "single_line_too_long"（重翻无长度收敛保证）与来源 D
# "suspected_missed_speech"（纯观测类 current_text=None）不入白名单。
# fail-closed：未知/未列类别一律不自动修复（宁可漏修不误修）。
_FULLCHAIN_AUTO_CATEGORIES = frozenset(
    {"untranslated", "cps_too_fast", "dewei", "subject"})
# structured_warnings 动态规则名族（B2 批 antonym_*/body_part_*/climax_*，
# 规则名来自 YAML 规则表无法静态枚举，按前缀闭集匹配）
_FULLCHAIN_AUTO_CATEGORY_PREFIXES = ("antonym_", "body_part_", "climax_")


def _ledger_read_entries(path: str) -> list[dict[str, Any]]:
    """读台账条目；缺失/损坏一律回退空表（自愈宁漏勿滥）。"""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    return [e for e in data if isinstance(e, dict)]


def _ledger_write_entries(path: str, entries: list[dict[str, Any]]) -> None:
    """台账覆盖式原子写（fs_utils 既有原子写；目录不存在则先建）。"""
    from subtransjav.refine.fs_utils import _atomic_write_text
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    _atomic_write_text(p, json.dumps(entries, ensure_ascii=False))


def _registered_identity_reason(entry: dict[str, Any]) -> str:
    """登记条目三重身份核验：空串=匹配，否则返回跳过原因（人话）。

    ① psutil.Process(pid) 存在；② create_time 与登记值差 <1.5s；
    ③ cmdline 含项目标记（subtransjav / subtrans-cli）与 kind 旗标。
    ②③联合防 PID 复用误杀：操作系统分配复用 pid 时 create_time/cmdline
    必不相同，届时拒绝击杀只清登记（安全方向正确）。
    """
    try:
        import psutil
    except ImportError:
        return "psutil 不可用，无法核验身份"
    try:
        p = psutil.Process(int(entry.get("pid") or 0))
    except Exception:
        return "进程已不存在"
    try:
        actual_ct = float(p.create_time())
    except Exception as e:
        return f"进程信息读取失败: {e}"
    if abs(actual_ct - float(entry.get("create_time") or 0.0)) \
            > _CHILD_CREATE_TIME_TOL_S:
        return "create_time 与登记值不符（疑似 PID 复用）"
    try:
        low = " ".join(str(x) for x in (p.cmdline() or [])).lower()
    except Exception as e:
        return f"cmdline 读取失败: {e}"
    marker = str(entry.get("marker") or "").lower()
    if marker and marker not in low:
        return "cmdline 缺少 kind 旗标（疑似 PID 复用）"
    if not any(t in low for t in _CHILD_PROJECT_TOKENS):
        return "cmdline 缺少项目标记（疑似 PID 复用）"
    return ""


def terminate_registered(entry: dict[str, Any]) -> dict[str, Any]:
    """身份核验后的登记子进程树杀（批4 D2026-1008-01）。

    核验通过 → terminate_process_tree（未完全成功升级 robust 回退）；
    任一不满足 → 不杀，仅返回 skipped + 原因（调用方只清登记）。
    取消桥与退出清理一律走本函数。无 psutil：仅对本会话持有的活 Popen
    句柄直接单杀（句柄对象无 PID 复用风险），无句柄则跳过。

    返回 {"success": bool, "skipped": bool, "reason": str}。
    """
    proc = entry.get("proc")
    if not PSUTIL_AVAILABLE:
        poll = getattr(proc, "poll", None)
        if proc is not None and callable(poll) and poll() is None:
            with contextlib.suppress(Exception):
                proc.kill()
            return {"success": True, "skipped": False, "reason": ""}
        return {"success": False, "skipped": True,
                "reason": "psutil 不可用，无法核验身份"}
    reason = _registered_identity_reason(entry)
    if reason:
        _log.info("terminate_registered 跳过（kind=%s pid=%s）: %s",
                  entry.get("kind"), entry.get("pid"), reason)
        return {"success": False, "skipped": True, "reason": reason}
    pid = int(entry.get("pid") or 0)
    result = terminate_process_tree(pid)
    ok = bool(result.get("success"))
    if not ok:
        ok = bool(terminate_process_tree_robust(pid))
    return {"success": ok, "skipped": False,
            "reason": "" if ok else "进程树终止未完全成功"}


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

        # 批4（D2026-1008-01）：分析/修复子进程登记槽 + 启动自愈扫描
        # （P3 预案：上次会话崩溃残留的登记子进程按台账三重核验后清理；
        # 只跑一次=TranslateAPI 每次启动仅构造一个实例）
        self._init_ai_state()
        self._selfheal_stale_children()

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
            # 压制互斥预检（D2 单一状态源；claim 原子占用，失败路径一律释放）
            from subtransjav.webview_gui.encode_queue import (
                claim_translate_slot,
                encode_active,
            )
            if encode_active():
                return {"success": False, "error": msg("encode_translate_conflict")}
            if not claim_translate_slot():
                return {"success": False, "error": msg("translation_in_progress")}
            # P1 预热互锁后端兜底（D2026-1008-02 批3，G1 (c) 阻断形态）：
            # 预热 loading 中拒启翻译（前端 G9 持有重试为主责，此处兜底）；
            # 已 claim 的槽原路归还防泄漏；不置哨兵（进程尚未启动）
            self._init_ai_state()
            with self._ai_lock:
                warmup_loading = ((self._warmup_state or {}).get("state")
                                  == "loading")
                warmup_snapshot = dict(self._warmup_state or {})
                # 批1 b 段（D2026-1009-02）互斥对①：全链自动化在飞拒启翻译
                #（同锁原子读；判定位于 _session_hook_fired 复位前的启动序内）
                fullchain_running = bool(self._fullchain_running)
            if warmup_loading:
                from subtransjav.webview_gui.encode_queue import release_translate_slot
                release_translate_slot()
                return {"success": False, "warmup_loading": True,
                        "warmup_status": warmup_snapshot}
            # 全链在飞：已 claim 的槽原路归还防泄漏；不置哨兵（进程尚未启动，
            # 与 warmup 互锁同 rationale）
            if fullchain_running:
                from subtransjav.webview_gui.encode_queue import release_translate_slot
                release_translate_slot()
                return {"success": False, "fullchain_running": True,
                        "error": msg("fullchain_running")}
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
            # 会话结束钩子 once 守卫复位（C9：每会话至多触发一次）
            self._session_hook_fired = False

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
            from subtransjav.webview_gui.encode_queue import release_translate_slot
            release_translate_slot()
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
            from subtransjav.webview_gui.encode_queue import release_translate_slot
            release_translate_slot()
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

                # 终态消费点（轮询驱动；每进程至多进入一次——proc 已清空）：
                # 翻译互斥槽归还（幂等）+ 会话结束钩子（批1 骨架 no-op，批3 接
                # 「批量翻译→批后自动压制」；C9 once 守卫在钩子内）
                from subtransjav.webview_gui.encode_queue import release_translate_slot
                release_translate_slot()
                if self._translate_status == "completed":
                    self._on_translation_session_completed(snap)

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
                # 批2（D2026-1007-03）：原子写改造——中断不再留半截设置文件
                # （mkstemp+fsync+os.replace，fs_utils 单一来源）
                from subtransjav.refine.fs_utils import _atomic_write_text
                _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
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

    # ----------------------------------------------------------------
    # 登记子进程槽与台账（批4 D2026-1008-01）：分析/修复子进程可停止
    # 与退出清理全覆盖的基础设施。槽=单条目 dict（proc/pid/create_time/
    # kind/marker/cancelled），_ai_lock 保护；台账=槽快照覆盖式原子写。
    # ----------------------------------------------------------------

    def _init_ai_state(self):
        """分析/修复/预热登记槽惰性初始化（对齐 _init_translation_state 先例；
        测试以 object.__new__ 构造实例不经 __init__，故取槽前必须先调）。"""
        if not hasattr(self, "_ai_analyze_proc"):
            self._ai_analyze_proc: dict[str, Any] | None = None
            self._batch_fix_proc: dict[str, Any] | None = None
            # P1 预热槽（D2026-1008-02 批3）：登记/台账/退出清理与批4 同构
            self._warmup_proc: dict[str, Any] | None = None
            # 预热状态机（G9/C4）：state=idle|loading|loaded|failed|hot，
            # 另含 fingerprint/started_at/pid/provider/model（详见桥 docstring）
            self._warmup_state: dict[str, Any] = {}
            self._ai_analyze_running = False
            self._ai_analyze_cancel = threading.Event()
            # 批1 a 段（D2026-1009-02）：全链状态机运行标志（防重叠；b 段
            # 互斥矩阵消费）+ 批修复重入守卫标志（refine_batch_fix 入口
            # 同步置位/finally 清位，覆盖链/手动互斥）
            self._fullchain_running = False
            self._batch_fix_running = False
            self._ai_lock = threading.Lock()

    def _register_child(self, proc: subprocess.Popen,
                        kind: str) -> dict[str, Any]:
        """登记子进程槽 + 台账同步（覆盖式原子写）。

        create_time 经 psutil 采样（登记值=身份核验基准）；采样失败回退
        time.time()——届时核验必因 create_time 不匹配拒绝击杀（安全方向）。
        """
        create_time = time.time()
        try:
            import psutil
            create_time = float(psutil.Process(proc.pid).create_time())
        except Exception:
            pass
        entry: dict[str, Any] = {
            "proc": proc, "pid": int(proc.pid), "create_time": create_time,
            "kind": kind, "marker": _CHILD_KIND_MARKERS.get(kind, ""),
        }
        with self._ai_lock:
            if kind == "ai_analyze":
                self._ai_analyze_proc = entry
            elif kind == "warmup":
                self._warmup_proc = entry
            else:
                self._batch_fix_proc = entry
        self._ledger_sync()
        return entry

    def _release_child_slot(self, kind: str, entry: dict[str, Any]) -> None:
        """正常 reap 后清登记槽 + 台账同步（覆盖式写=条目移除）。"""
        with self._ai_lock:
            slot = {"ai_analyze": "_ai_analyze_proc",
                    "warmup": "_warmup_proc"}.get(kind, "_batch_fix_proc")
            if getattr(self, slot, None) is entry:
                setattr(self, slot, None)
        self._ledger_sync()

    def _ledger_entries(self) -> list[dict[str, Any]]:
        """当前登记快照（台账持久化形状：仅 pid/create_time/kind/marker）。"""
        with self._ai_lock:
            slots = [getattr(self, "_ai_analyze_proc", None),
                     getattr(self, "_batch_fix_proc", None),
                     getattr(self, "_warmup_proc", None)]
        return [{"pid": e["pid"], "create_time": e["create_time"],
                 "kind": e["kind"], "marker": e["marker"]}
                for e in slots if e]

    def _ledger_sync(self) -> None:
        """台账覆盖式原子写当前快照（fail-soft：绝不因台账拖垮业务链）。"""
        try:
            _ledger_write_entries(_child_procs_ledger_path(),
                                  self._ledger_entries())
        except Exception:
            _log_exc("_ledger_sync")

    def _selfheal_stale_children(self) -> None:
        """启动自愈扫描（批4 D2026-1008-01，P3 预案核心，只跑一次）。

        读上次会话遗留台账 → 逐条三重核验（进程存在 + cmdline 含项目标记
        与 kind 旗标 + create_time 与登记匹配且早于本次启动）→ 满足即
        terminate_process_tree 并记 gui.log 一行；任一不满足跳过。结束写空
        台账。全程异常吞掉不阻塞启动；psutil 缺失跳过并记 log。
        """
        try:
            if not PSUTIL_AVAILABLE:
                _log.info(msg("selfheal_psutil_missing"))
                return
            path = _child_procs_ledger_path()
            entries = _ledger_read_entries(path)
            if not entries:
                return
            t0 = time.time()
            for e in entries:
                try:
                    pid = int(e.get("pid") or 0)
                    reason = _registered_identity_reason(e)
                    if reason:
                        _log.info("自愈跳过残留条目（kind=%s pid=%s）: %s",
                                  e.get("kind"), pid, reason)
                        continue
                    if float(e.get("create_time") or 0.0) >= t0:
                        continue  # 晚于本次启动：非上次会话遗留，不碰
                    terminate_process_tree(pid)
                    _log.info(msg("selfheal_cleaned",
                                  kind=e.get("kind"), pid=pid))
                except Exception:
                    _log_exc("_selfheal_stale_children.entry")
            _ledger_write_entries(path, [])
        except Exception:
            _log_exc("_selfheal_stale_children")

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
    # 本地型 provider（C8 预检覆盖面，D2026-1007-02 件E；与
    # RefineConfig.resolve_api_key「lmstudio / ollama 本地服务」口径一致）：
    # spawn 修复子进程前对其端点探活；云端 provider 一律跳过（行为不变）
    _AI_LOCAL_PROVIDERS = ("lmstudio", "ollama")
    # 本地 provider 缺省端点（CLI 既有默认；解析 endpoint 为空时的探活/
    # 旗标缺省回退，与前端 REFINE_PROVIDER_URLS 镜像）
    _AI_PROVIDER_ENDPOINT_DEFAULTS = {
        "lmstudio": "http://localhost:1234/v1",
        "ollama": "http://localhost:11434/v1",
    }
    # C8 探活超时（秒）：只判连通，超时=不通（宁误拦不放任 35 条逐条全败）
    _ENDPOINT_PROBE_TIMEOUT_S = 5
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
                          ai_provider: str = None,
                          from_fullchain: bool = False) -> dict[str, Any]:
        """同步执行 AI 质量分析并读回建议件（批4 起可停止，D2026-1008-01）。

        流程：路径守卫链 → spawn Popen（双管道捕获）并登记槽+台账 →
        worker 线程 communicate(timeout=600s) 排水（保 stdout 解析）→
        主桥线程 join 等待 → 成功后读回 ``{stem}_AI质量建议.json`` 解析返回。
        单飞守卫（进行中再调=拒绝）；取消闩（spawn 前秒点停止不 spawn）；
        取消/超时 → 身份核验后 terminate_registered 树杀。
        取消返回 {success:False, cancelled:True}；
        超时/非零退出/建议件缺失 → success=False + error。
        批1 b 段（D2026-1009-02）互斥对④：from_fullchain 形参（缺省
        False=手动路径）——全链在飞时手动分析显式拒绝（msg
        fullchain_running，不排队）；链级复验调用传 True 绕过全链判定
        （仍受单飞守卫约束）。"""
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
                # P2（D2026-1008-02）：文案收编 strings.py——与共用解析
                # helper _resolve_ai_model_config 同串单源
                return {"success": False,
                        "error": msg("ai_indep_custom_unsupported")}
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

        # 批4（D2026-1008-01）：分析链可停止（HRO-1 方案A）。原
        # spawn_refine_cli(capture=True)=subprocess.run 拿不到进程句柄无法
        # 取消；改 Popen 双管道捕获 + worker 线程 communicate(timeout)
        # 排水（stdout 解析输入原样保留），主桥线程 join 等待（600s+余量），
        # 取消桥在另一桥线程并发可达。超时语义同现状（文案逐字不变）。
        self._init_ai_state()
        with self._ai_lock:
            # 批1 b 段互斥对④（前置判定）：全链在飞拒绝手动 AI 分析——
            # 显式拒绝+明确提示，不排队；链内复验携 from_fullchain=True
            # 绕过本判定（仍受单飞守卫约束）
            if self._fullchain_running and not from_fullchain:
                return {"success": False,
                        "error": msg("fullchain_running")}
            # 单飞守卫：分析进行中再次调用 → 拒绝且不再 spawn
            if self._ai_analyze_running or self._ai_analyze_proc is not None:
                return {"success": False,
                        "error": msg("ai_analyze_in_progress")}
            # 取消闩：用户在 spawn 前秒点停止的竞态 → 置闩状态下不 spawn
            # 直接返回 cancelled（闩由本处消费）
            if self._ai_analyze_cancel.is_set():
                self._ai_analyze_cancel.clear()
                return {"success": False, "cancelled": True,
                        "error": msg("ai_analyze_cancelled")}
            self._ai_analyze_running = True
        try:
            try:
                proc = cast(subprocess.Popen, spawn_refine_cli(
                    args, cwd=str(REPO_ROOT),
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, encoding="utf-8", errors="replace",
                    env_extra=env_extra))
            except Exception as e:
                _log_exc("refine_ai_analyze.spawn")
                return {"success": False,
                        "error": f"AI 分析子进程启动失败: {e}"}
            entry = self._register_child(proc, "ai_analyze")
            # spawn 后二次闩检：覆盖 spawn 与登记间隙内到达的取消请求
            with self._ai_lock:
                if self._ai_analyze_cancel.is_set():
                    self._ai_analyze_cancel.clear()
                    entry["cancelled"] = True
            if entry.get("cancelled"):
                terminate_registered(entry)

            run_box: dict[str, Any] = {}

            def _drain() -> None:
                """worker：排水两管道（保 stdout 解析输入）。取消/超时树杀后
                管道关闭，本函数自然收敛——排水语义与原 subprocess.run 等价。"""
                try:
                    out, err = proc.communicate(
                        timeout=self._AI_ANALYZE_TIMEOUT_S)
                    run_box.update({"stdout": out or "", "stderr": err or "",
                                    "rc": proc.returncode, "timed_out": False})
                except subprocess.TimeoutExpired:
                    # 超时：身份核验后树杀并排水残余（超时文案同现状）
                    terminate_registered(entry)
                    try:
                        out, err = proc.communicate(timeout=5)
                    except Exception:
                        out, err = "", ""
                    run_box.update({"stdout": out or "", "stderr": err or "",
                                    "rc": proc.returncode, "timed_out": True})
                except Exception as e:
                    run_box.update({"stdout": "", "stderr": str(e),
                                    "rc": proc.returncode, "timed_out": False,
                                    "drain_error": True})

            th = threading.Thread(target=_drain, daemon=True,
                                  name="gui-ai-analyze-drain")
            th.start()
            th.join(self._AI_ANALYZE_TIMEOUT_S + 30)
            if th.is_alive():
                # 极端兜底：communicate 未按超时收敛 → 核验后强杀、放弃等待
                terminate_registered(entry)
                th.join(10)
                return {"success": False,
                        "error": f"AI 分析超时（>{self._AI_ANALYZE_TIMEOUT_S}s）"}
            # reap：登记槽清位 + 台账同步（覆盖式写=条目移除）
            self._release_child_slot("ai_analyze", entry)
            if entry.get("cancelled"):
                return {"success": False, "cancelled": True,
                        "error": msg("ai_analyze_cancelled")}
            if run_box.get("timed_out"):
                return {"success": False,
                        "error": f"AI 分析超时（>{self._AI_ANALYZE_TIMEOUT_S}s）"}
            if run_box.get("drain_error"):
                return {"success": False,
                        "error": "AI 分析子进程异常: "
                                 f"{run_box.get('stderr', '')}"}
            stderr_tail = (run_box.get("stderr") or "")[-2000:]
            if run_box.get("rc") != 0:
                return {"success": False,
                        "error": msg("process_exit_code",
                                     code=run_box.get("rc")),
                        "stderr_tail": stderr_tail}
            # 2.6.0 批 3 知情行（C6）：对照段数随成功返回（前端状态行提示）
            crosscheck_segments = 0
            m = re.search(r"\[crosscheck\] segments=(\d+)",
                          run_box.get("stdout") or "")
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
        finally:
            with self._ai_lock:
                self._ai_analyze_running = False
                # 本轮已收尾：未被消费的闩属陈旧请求（取消桥在登记前后
                # 均可直达进程），清之防吞掉下一次分析
                self._ai_analyze_cancel.clear()

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
    # 批6（D2026-1008-02）：导读条目修复终态集合——retranslated/nochange
    # 已有落盘结论，不再进 open_items；未知 status 默认可见（禁静默丢）
    KNOWN_TERMINAL_STATUS = {"retranslated", "nochange"}
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

    def _resolve_ai_model_config(self, ai_provider: str = None,
                                 ai_model: str = None) -> dict[str, Any]:
        """C6 单源（D2026-1008-02 P2）：一键修复与 AI 分析共用同一模型解析。

        输入=分析按钮同源参（refine_ai_analyze 同签名语义：ai_provider
        空/None=跟随阶段A，非空=分析独立配置）。解析规则：
        1. 独立配置全有（ai_model 非空且 ai_provider 非空）→ 生效
           （source=analyze_independent；端点走 CLI 各 provider 默认，
           与分析路径同法；custom 无默认端点沿分析先例拒绝）；
        2. ai_model 非空且 ai_provider 空 → 生效（source=stage_a_follow，
           provider/endpoint 取阶段A）；
        3. G5-补：ai_model 空但 ai_provider 非空 → 独立配置不完整（跨
           服务商错配风险）→ 视为未配置，notes 追加「分析独立配置不
           完整，已忽略」，落入阶段A 链；
        4. 阶段A 链（C9 回退链终点，不回退阶段B——破坏「与分析完全
           同一」契约）：model=阶段A model 或
           PROVIDER_MODEL_DEFAULTS[阶段A provider]；provider/model 全无
           线索 → 解析失败，reason 如实（此时才报错）。

        C18 边界：本 helper 只做配置层解析；配置完整后的运行时失败
        （模型不存在/未下载/装载失败）由 ensure/CLI 原样报错，此处不做
        任何配置回退（防「以为在用分析模型、实际跑阶段A」失真）。

        返回 dict(ok, provider, endpoint, model, source, notes, reason)；
        拒绝时 ok=False + 人话 reason 且三元组为空串（notes 仍回带，
        供调用方拼装完整人话）。"""
        provider_in = str(ai_provider or "").strip().lower()
        model_in = str(ai_model or "").strip()
        notes: list[str] = []

        def _deny(reason: str) -> dict[str, Any]:
            return {"ok": False, "provider": "", "endpoint": "",
                    "model": "", "source": "", "notes": notes,
                    "reason": reason}

        # 独立配置全有才做 custom 兜底拒绝（无默认端点，与分析路径
        # 同串单源）；半配置 custom 落 G5-补 忽略规则
        if provider_in == "custom" and model_in:
            return _deny(msg("ai_indep_custom_unsupported"))
        if model_in:
            if provider_in:
                return {"ok": True, "provider": provider_in,
                        "endpoint": "", "model": model_in,
                        "source": "analyze_independent",
                        "notes": notes, "reason": ""}
            return {"ok": True, "provider": self._stage_a_provider_name(),
                    "endpoint": self._stage_a_endpoint(),
                    "model": model_in,
                    "source": "stage_a_follow", "notes": notes,
                    "reason": ""}
        if provider_in:
            notes.append(msg("fix_ai_indep_half_ignored"))
        # 阶段A 链（G5-补 忽略/follow 落此；provider 空时子进程落 CLI
        # 缺省 lmstudio，与分析路径放行语义一致）
        a_provider = self._stage_a_provider_name()
        a_endpoint = self._stage_a_endpoint()
        a_model = self._stage_a_model()
        from subtransjav.refine.config import PROVIDER_MODEL_DEFAULTS
        model = a_model or PROVIDER_MODEL_DEFAULTS.get(
            a_provider.strip().lower(), "")
        if not model:
            return _deny(msg("fix_ai_model_unset"))
        return {"ok": True, "provider": a_provider, "endpoint": a_endpoint,
                "model": model, "source": "stage_a_follow",
                "notes": notes, "reason": ""}

    # P2（D2026-1008-02）：生效源人话标识（预览行直出，前端零解析；
    # source 机器码 → 中文标签；修复解析已并轨分析源，仅两源）
    _FIX_SOURCE_LABELS = {
        "analyze_independent": "分析模型",
        "stage_a_follow": "跟随阶段A",
    }

    def refine_preview_fix_config(self, ai_provider: str = None,
                                  ai_model: str = None) -> dict[str, Any]:
        """C7 桥（D2026-1007-02 件C；P2 D2026-1008-02 改源）：修复生效
        配置预览（只读、无副作用、不 spawn），供前端修复卡明示行与确认
        框刷新。入参=前端 analyzeResolution() 产物，与 refine_batch_fix
        共用 _resolve_ai_model_config 解析（预览与执行同源 by
        construction，C7）。形状钉（provider/endpoint/model/source/
        source_label/reason 恒为字符串，ok 恒为布尔，notes 恒为字符串
        列表；source_label=生效源人话标识）。"""
        try:
            cfg = self._resolve_ai_model_config(ai_provider, ai_model)
        except Exception as e:
            _log_exc("refine_preview_fix_config")
            return {"ok": False, "provider": "", "endpoint": "",
                    "model": "", "source": "", "source_label": "",
                    "reason": str(e), "notes": []}
        source = str(cfg.get("source") or "")
        return {"ok": bool(cfg.get("ok")),
                "provider": str(cfg.get("provider") or ""),
                "endpoint": str(cfg.get("endpoint") or ""),
                "model": str(cfg.get("model") or ""),
                "source": source,
                "source_label": self._FIX_SOURCE_LABELS.get(source, ""),
                "reason": str(cfg.get("reason") or ""),
                "notes": [str(n) for n in (cfg.get("notes") or [])]}

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

    def _ledger_top_reason(self, guide_dir: str, stem: str) -> str:
        """C9（D2026-1007-02 件E）：台账失败 reason 主因（Counter top1，
        截断 ≤200 字符）。跳过空/缺失 reason；台账缺失/损坏/读失败/无
        有效 reason 一律返回 ""（降级为仅退出码文案），任何情况不抛异常。
        复用 _read_ledger（fail-soft 返回 []），零新增读取通道。"""
        try:
            reasons: list[str] = []
            for rec in self._read_ledger(guide_dir, stem):
                if not isinstance(rec, dict):
                    continue
                if rec.get("outcome") != "failed":
                    continue   # 批6：主因只统计失败记录，nochange/applied 不入
                reason = str(rec.get("reason") or "").strip()
                if reason:
                    reasons.append(reason)
            if not reasons:
                return ""
            top, _count = Counter(reasons).most_common(1)[0]
            return top[:200]
        except Exception:
            return ""

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
            retranslated_count = 0
            nochange_count = 0
            applied_open_count = 0
            for it in items:
                if not isinstance(it, dict):
                    continue
                status = str(it.get("status") or "")
                if status == "observation":
                    observation_count += 1
                    continue
                # 批6：终态（retranslated/nochange）只计数不进 open_items；
                # 其余（open 或未知 status）一律可见（C2：未知默认可见）
                if status in self.KNOWN_TERMINAL_STATUS:
                    if status == "retranslated":
                        retranslated_count += 1
                    else:
                        nochange_count += 1
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
                "retranslated_count": retranslated_count,
                "nochange_count": nochange_count,
                "direction": str(guide.get("direction") or ""),
                "has_media": bool(guide.get("media_path")),
            }
        except Exception as e:
            _log_exc("refine_guide_action_items")
            return {"success": False, "error": str(e)}

    def refine_batch_fix(self, guide_path: str, entries: Any,
                         ai_provider: str = None,
                         ai_model: str = None,
                         verify: bool = True,
                         from_fullchain: bool = False) -> dict[str, Any]:
        """一键批次修复：确认与逐条预览在前端（AppModal），本方法执行。

        守卫链：路径/后缀 → entries 整数数组 ≤_BATCH_FIX_MAX_ENTRIES →
        逐条命中 open 且有现译（观察类必拒，C6）→ 台账已修拒入批
        （C1 幂等守卫；重修走 CLI --entries 显式通道）。执行=
        spawn_refine_cli 子进程跑 --action-retranslate --apply（修复
        provider/model 与 AI 分析完全同一解析：P2/D2026-1008-02 弃独立
        修复链，改用分析按钮同源形参 ai_provider/ai_model 经共用 helper
        _resolve_ai_model_config 解析（C6 单源）；拒绝即不 spawn 且
        reason 如实透出（C8，弃统一 generic 盖法）；台账先于终稿写序/
        恒等式断言在执行器侧原样生效）；复验=生效后重跑全片 AI 分析
        恰 1 次做建议件三键计数 diff（复验与执行同一解析入参）。
        批1 a 段（D2026-1009-02）增注：①重入守卫——方法最入口（早于
        load/spawn）在 _ai_lock 下检查+置位 _batch_fix_running，进行中
        再调=结构化拒绝（msg batch_fix_running），finally 清位覆盖全部
        退出路径；锁内只做检查+置位/清理、不跨越 spawn wait 持有，链内
        串行逐批调用=每批独立进出（无嵌套无死锁），b 段互斥矩阵按同
        一标志消费。②verify 形参（缺省 True=手动路径零变化）——全链
        状态机链内传 False 跳过内置复验，链级复验唯一一次在其收口，
        保证长期链级不变式「LLM 分析（--ai-analyze）spawn==1」。
        批1 b 段增注：③from_fullchain 形参（缺省 False=手动路径）——
        互斥对②，全链在飞时手动批量修复结构化拒绝（msg fullchain_running，
        不排队）；链内调用传 True 绕过全链判定（仍受 _batch_fix_running
        重入守卫约束）。"""
        self._init_ai_state()
        with self._ai_lock:
            if self._batch_fix_running:
                return {"success": False, "error": msg("batch_fix_running")}
            # 批1 b 段互斥对②：全链在飞拒绝手动批量修复（不排队）
            if self._fullchain_running and not from_fullchain:
                return {"success": False, "fullchain_running": True,
                        "error": msg("fullchain_running")}
            self._batch_fix_running = True
        try:
            return self._refine_batch_fix_locked(
                guide_path, entries, ai_provider, ai_model, verify)
        finally:
            with self._ai_lock:
                self._batch_fix_running = False

    def _refine_batch_fix_locked(self, guide_path: str, entries: Any,
                                 ai_provider: str = None,
                                 ai_model: str = None,
                                 verify: bool = True) -> dict[str, Any]:
        """refine_batch_fix 主体（重入守卫置位后调用；形参/语义同上游）。"""
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
        # 批6：终态守卫——导读 status 已是 retranslated/nochange 的 index
        # 直接过滤（前端不会提交，防御直连 CLI/陈旧前端）；全被过滤即
        # 无可修条目，给出可读原因
        terminal_idx = {it.get("index") for it in items
                        if isinstance(it, dict)
                        and str(it.get("status") or "")
                        in self.KNOWN_TERMINAL_STATUS}
        terminal_hits = sorted(want & terminal_idx)
        if terminal_hits:
            want -= set(terminal_hits)
        if not want:
            return {"success": False,
                    "error": "所选条目均已是修复终态（已重翻/无需改动），"
                             "无可修条目"}
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

        # 修复 provider/endpoint/model 与 AI 分析完全同一解析（P2/
        # D2026-1008-02：C6 单源 helper，入参=分析按钮同源形参；拒绝即
        # 不 spawn 且 reason 如实透出（C8）——原先空 model 放任子进程落
        # CLI 缺省空串 → pipeline RefineError 全败退出 1 的拦截保持在
        # spawn 之前；notes（半配置忽略说明）拼入人话错误；密钥仍仅经
        # 子进程环境变量注入（白名单表与翻译/分析一致）。
        cfg = self._resolve_ai_model_config(ai_provider, ai_model)
        notes = [str(n) for n in (cfg.get("notes") or []) if n]
        if not cfg.get("ok"):
            reason = str(cfg.get("reason") or msg("fix_ai_model_unset"))
            if notes:
                reason = "；".join(notes) + "；" + reason
            return {"success": False, "error": reason}
        # C8 端点预检（D2026-1007-02 件E）：仅本地型 provider（provider 空
        # = CLI 缺省 lmstudio，见 cli.config_from_args）在 spawn 前对其端点
        # /v1/models 探一次连通性——端点不通时子进程逐条全败才退出 1（故障
        # 史），探活秒级拦截。只判连通不校验模型在载（LM Studio 按需加载）；
        # 端点缺省回退与 CLI --<provider>-endpoint 缺省同源
        # （PROVIDER_ENDPOINT_DEFAULTS，cli.py 旗标 default 同值）。云端
        # provider 一律跳过，行为与既往一致。探活实现在 provider 客户端
        # 模块（llm_client.probe_endpoint_reachable，复用其回环直连 HTTP
        # 惯例），本层只包薄调用，零新增网络/文件写读点（Mimosa 纪律）。
        probe_provider = (str(cfg.get("provider") or "").strip().lower()
                          or "lmstudio")
        if probe_provider in self._AI_LOCAL_PROVIDERS:
            endpoint = str(cfg.get("endpoint") or "")
            if not endpoint:
                from subtransjav.refine.config import PROVIDER_ENDPOINT_DEFAULTS
                endpoint = PROVIDER_ENDPOINT_DEFAULTS.get(probe_provider, "")
            from subtransjav.translate.llm_client import probe_endpoint_reachable
            reachable, detail = probe_endpoint_reachable(
                endpoint, timeout=self._ENDPOINT_PROBE_TIMEOUT_S)
            if not reachable:
                _log.warning("refine_batch_fix 端点预检失败: %s (%s)",
                             endpoint, detail)
                return {"success": False,
                        "error": msg("fix_endpoint_unreachable",
                                     endpoint=endpoint)}
        args = ["--action-retranslate", p,
                "--entries", ",".join(str(i) for i in sorted(want))]
        # F1 修复源文增强（D2026-1009-02 批0 / D2026-1009-01 C1）：三级
        # 定位原始源文 SRT，命中即透传 --action-source（按 timing 对齐恢复
        # 完整源文）；解析退化（None）不追加，CLI 侧既有提示兜底，不新增
        # 通知管线。source_name 取导读顶层 source（真实输入名落盘口径）。
        from subtransjav.refine.pipeline_support import resolve_action_source_path
        action_source = resolve_action_source_path(
            p, str(guide.get("source") or ""))
        if action_source is not None:
            args.extend(["--action-source", str(action_source)])
        args.append("--apply")
        provider = str(cfg.get("provider") or "")
        if provider:
            # P2（D2026-1008-02）：与 refine_ai_analyze 同源旗标——动作
            # 客户端已改槽A（stages[0]，与 quality_advisor._make_ai_client
            # 同构），provider/endpoint 走 --s1-provider/
            # --<provider>-endpoint（同分析路径传法）；独立配置端点空=
            # CLI 各 provider 默认（同分析）
            args.extend(["--s1-provider", provider])
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
        self._init_ai_state()  # 批4：登记槽惰性初始化（先于 _register_child）
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
        # 批4（D2026-1008-01）：登记槽+台账（取消桥/退出清理可达；
        # 取消经 terminate_registered 身份核验后树杀）
        entry = self._register_child(proc, "batch_fix")

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
            self._release_child_slot("batch_fix", entry)
            prog.update({"running": False, "phase": "failed",
                         "last_line": "超时终止"})
            return {"success": False,
                    "error": f"批量修复超时（>{self._BATCH_FIX_TIMEOUT_S}s）；"
                             "已落盘条目以台账为准，可再次发起处理余量",
                    "stdout_tail": "\n".join(tail[-40:])[-2000:]}
        # reap：登记槽清位 + 台账同步（覆盖式写=条目移除）
        self._release_child_slot("batch_fix", entry)
        # 批4：取消收口——不再走退出码分账，且绝不自动复跑 AI 分析
        #（修复子进程被杀的已落盘条目以重翻台账为准，可再次发起）
        if entry.get("cancelled"):
            prog.update({"running": False, "phase": "failed",
                         "last_line": "已取消"})
            return {"success": False, "cancelled": True,
                    "error": msg("batch_fix_cancelled"),
                    "stdout_tail": "\n".join(tail[-40:])[-2000:]}
        prog.update({"running": False,
                     "phase": "done" if rc in (0, 3) else "failed"})
        result: dict[str, Any] = {
            "success": rc in (0, 3),
            "exit_code": rc,
            "applied": 0,
            "failed": 0,
            "nochange": 0,
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
        result["nochange"] = sum(
            1 for r in new_records
            if isinstance(r, dict) and r.get("outcome") == "nochange")
        result["source_partial"] = sum(
            1 for r in new_records
            if isinstance(r, dict) and r.get("source_partial"))
        if rc != 3 and rc != 0:
            # C9 失败可观测性（D2026-1007-02 件E）：stdout_tail 原本只存
            # 内存回包，失败时落 gui.log（单行摘要防日志超长）；台账失败
            # reason 主因（Counter top1）拼入 error——此前端点不通/模型缺失
            # 时用户只见「退出码 1」。台账缺失/损坏一律降级为仅退出码文案
            # （_ledger_top_reason fail-soft），任何情况不抛异常。
            _log.warning("refine_batch_fix 失败: exit=%s stdout_tail(尾段)=%s",
                         rc, " | ".join(tail[-8:])[-600:] or "（空）")
            result["error"] = msg("process_exit_code", code=rc)
            top_reason = self._ledger_top_reason(guide_dir, stem)
            if top_reason:
                result["error"] += f"；主因：{top_reason}"
            return result

        # 复验（批1 a 段参数化：verify 缺省 True=手动路径原形态；链内传
        # False 跳过——链级复验唯一一次在 _run_fullchain_automation 收口，
        # 保证长期链级不变式「--ai-analyze spawn==1」）：重跑全片 AI 分析
        # 恰 1 次，建议件三键计数 diff
        if verify:
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
        else:
            # 链内跳过：显式标记（phase 不进 "verify"，直接终态）
            result["verify"] = {"skipped": True}
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

    def _cancel_registered(self, kind: str,
                           no_entry: dict[str, Any]) -> dict[str, Any]:
        """取消桥共用体（批4 D2026-1008-01）：置 cancelled 旗标 → 身份核验
        后树杀 → 短窗等退出（保证调用方返回时进程已收尾）。

        槽空（进程尚未 spawn/已收尾）→ 分析链置取消闩（spawn 前预检消费，
        覆盖「用户秒点停止」竞态）；修复/预热链无启动窗口竞态，不置闩。
        槽判别按 kind 显式映射（批3 P1 修正：非 ai_analyze 不再一律当
        batch_fix 取槽）。"""
        self._init_ai_state()
        with self._ai_lock:
            slot = {"ai_analyze": "_ai_analyze_proc",
                    "warmup": "_warmup_proc"}.get(kind, "_batch_fix_proc")
            entry = getattr(self, slot, None)
        if entry is None:
            if kind == "ai_analyze":
                self._ai_analyze_cancel.set()
            return no_entry
        entry["cancelled"] = True
        kill = terminate_registered(entry)
        proc = entry.get("proc")
        if proc is not None:
            with contextlib.suppress(Exception):
                proc.wait(timeout=5)
        return {"success": True, "cancelled": True, "kill": kill}

    def refine_cancel_ai_analyze(self) -> dict[str, Any]:
        """停止进行中的 AI 分析（批4 D2026-1008-01，HRO-1 方案A）。

        已登记 → 身份核验后树杀（worker communicate 因管道关闭返回，
        分析桥线程以 cancelled 结果收尾，LM Studio 侧负载不受影响——
        服务器侧 JIT 加载无法经本通道中止，前端文案如实交代）；
        尚未 spawn（启动窗口内）→ 置取消闩，由 spawn 前预检消费。
        """
        r = self._cancel_registered(
            "ai_analyze",
            {"success": True, "cancelled_pending": True,
             "message": msg("ai_analyze_cancel_pending")})
        if r.get("cancelled_pending"):
            return r
        r["message"] = msg("ai_analyze_cancelled")
        return r

    def refine_cancel_batch_fix(self) -> dict[str, Any]:
        """停止进行中的一键批量修复（批4 D2026-1008-01）。修复桥读
        cancelled 旗标提前返回，保证取消后不再自动复跑 AI 分析。"""
        return self._cancel_registered(
            "batch_fix",
            {"success": False, "error": msg("no_batch_fix_in_progress")})

    # ----------------------------------------------------------------
    # P1 分析模型预热（D2026-1008-02 批3，G1 落 (c) 阻断形态）
    # 设计契约落点：C1 同源通道（spawn --warmup-analysis 子进程，cfg 与
    # 分析同参）；C3 透明（spawn/gui.log 留痕）；C4 状态优先去重（探
    # /v1/models 在载判定为主，指纹为辅）；C5 退出清理/启动自愈经登记槽
    # 自动覆盖；G3 同源指纹；G9 单飞+入队快照（快照在前端）；G10 硬超时
    # 走 settings KV（缺省 300，gui.log 留痕依据）。
    # 本节新增错误文案沿用批4 先例为内联中文（未进 strings.py，行为与
    # msg() 回退语义等价），注释即契约。
    # ----------------------------------------------------------------

    # G10：预热装载硬超时 KV 键与缺省（KV 非法/非正值一律按缺省处理）
    _WARMUP_TIMEOUT_KV = "preheat_load_hard_timeout"
    _WARMUP_TIMEOUT_DEFAULT_S = 300
    # C4 在载探活超时（/v1/models 只含已载模型；口径同 list_local_models）
    _WARMUP_PROBE_TIMEOUT_S = 5

    def _warmup_resolve_current(self) -> tuple[str, str] | None:
        """按当前配置（ai_analyze_* KV→阶段A 同源链）解析预热三元组。

        返回 (provider, model)；解析失败/非本地 provider 返回 None
        （状态桥据此报 supported:false，静默不扰）。"""
        try:
            got = self.refine_get_stage_settings()
            kv = (got or {}).get("settings") or {}
        except Exception:
            kv = {}
        try:
            res = self._resolve_ai_model_config(
                str(kv.get("ai_analyze_provider") or "") or None,
                str(kv.get("ai_analyze_model") or "") or None)
        except Exception:
            return None
        if not res.get("ok"):
            return None
        prov = str(res.get("provider") or "").strip().lower()
        model = str(res.get("model") or "").strip()
        if prov not in self._AI_LOCAL_PROVIDERS or not model:
            return None
        return prov, model

    def _warmup_fingerprint(self, provider: str, endpoint: str,
                            model: str) -> str:
        """G3 同源指纹：provider/endpoint/model/生效 ctx/并发。

        C1：预热 CLI 不传 --v2-ctx/--v2-concurrency，与分析子进程同走
        config 分层链——故 ctx 取 resolve_tunable 生效值、并发恒为 CLI
        缺省 1（与分析路径一致），配置变更即指纹变更。"""
        try:
            from subtransjav.refine.config import resolve_tunable
            ctx = int(resolve_tunable("v2_ctx_local") or 0)
        except Exception:
            ctx = 0
        return "|".join(str(x) for x in (provider, endpoint, model, ctx, 1))

    def _warmup_timeout_s(self) -> tuple[int, str]:
        """G10 预热装载硬超时：settings KV ``preheat_load_hard_timeout``
        读取 + int 合法化（非法/非正 → 缺省 300）。

        返回 (秒, 依据)——依据∈{"settings KV", "settings 缺省"}，供 gui.log
        打「本次预热超时=Xs，依据=Y」留痕（打点在 spawn 处，每轮预热一行）。"""
        basis = "settings 缺省"
        try:
            got = self.refine_get_stage_settings()
            raw = str(((got or {}).get("settings") or {})
                      .get(self._WARMUP_TIMEOUT_KV, "") or "").strip()
        except Exception:
            raw = ""
        if raw:
            try:
                v = int(raw)
            except (TypeError, ValueError):
                v = 0
            if v > 0:
                return v, "settings KV"
        return self._WARMUP_TIMEOUT_DEFAULT_S, basis

    def _warmup_probe_loaded(self, endpoint: str) -> list[str] | None:
        """C4 在载探活：GET {root}/v1/models（只列已载模型，与
        lmstudio._loaded_ids/list_local_models 同口径）。

        返回已载模型 id 列表；端点不可达/服务不在/lms 环境异常一律返回
        None（调用方静默转 supported:false，绝不 spawn 硬探）。"""
        root = (endpoint or "").rstrip("/")
        if root.endswith("/v1"):
            root = root[:-3]
        if not root:
            return None
        try:
            import requests as _req
            r = _req.get(f"{root}/v1/models",
                         timeout=self._WARMUP_PROBE_TIMEOUT_S)
            data = (r.json() or {}).get("data") or []
            return [str(x.get("id") or "") for x in data
                    if isinstance(x, dict) and x.get("id")]
        except Exception:
            return None

    def _warmup_payload(self, st: dict[str, Any]) -> dict[str, Any]:
        """由状态字典组装 status 回包（调用方持锁外调用；timeout 现读）。"""
        timeout_s, _basis = self._warmup_timeout_s()
        state = str(st.get("state") or "idle")
        started_at = float(st.get("started_at") or 0.0)
        elapsed = max(0.0, time.time() - started_at) if started_at else 0.0
        return {"supported": True, "state": state,
                "fingerprint": str(st.get("fingerprint") or ""),
                "elapsed": round(elapsed, 3), "timeout": timeout_s,
                "provider": str(st.get("provider") or ""),
                "model": str(st.get("model") or "")}

    def refine_warmup_status(self) -> dict[str, Any]:
        """P1 预热状态桥（前端 G9 持有轮询 + 开始翻译前预检）。

        返回 {supported, state, fingerprint, elapsed, timeout, provider,
        model}：state∈idle|loading|loaded|failed|hot；elapsed=本预热起流经
        秒数；timeout=G10 值（前端倒计时/超时放行同源）。supported=False=
        预热通道对当前配置不适用（云 provider/解析失败/(c) 阻断不适用，
        前端直接放行）。"""
        self._init_ai_state()
        with self._ai_lock:
            st = dict(self._warmup_state or {})
        if st.get("state"):
            return self._warmup_payload(st)
        timeout_s, _ = self._warmup_timeout_s()
        cur = self._warmup_resolve_current()
        if cur is None:
            return {"supported": False, "state": "idle", "fingerprint": "",
                    "elapsed": 0.0, "timeout": timeout_s,
                    "provider": "", "model": ""}
        return {"supported": True, "state": "idle", "fingerprint": "",
                "elapsed": 0.0, "timeout": timeout_s,
                "provider": cur[0], "model": cur[1]}

    def refine_warmup_analysis_model(self, model: str = None,
                                     provider: str = None) -> dict[str, Any]:
        """P1 预热桥（D2026-1008-02 批3）。触发方=前端 warmupMaybeStart()
        （G2 队列完成/切质量页）与后端会话钩子；去重三层=单飞+C4 在载探活
        +G3 指纹（5s 内重复触发抑制由前端兜底）。

        流程：
        ① 解析同源（C6 helper）：provider 空=跟随阶段A；解析失败/非本地
           provider → {supported:False, reason}（静默不扰）。
        ② 单飞：已有在飞预热（state=loading/槽在位）→ 返回现状态不重复
           spawn（G9 点击入队语义）。
        ③ C4 状态优先：探 /v1/models，目标模型已在载 → 置 state=hot 并
           返回 {already_hot:True} 不 spawn；端点不可达 → supported:False。
        ④ G3 指纹：与上次已完成（state=loaded）指纹相同 → 跳过（能走到
           此处说明③探活不在载，该分支仅在探活与状态读取竞态窗口内生效，
           TTL 卸载后不会误抑制——状态判定为主，C4）。
        ⑤ spawn ``--warmup-analysis`` 子进程（与 refine_ai_analyze 同参源：
           --ai-model/--s1-provider/--<provider>-endpoint；密钥 env 同表）
           并登记 warmup 槽（台账/退出清理/启动自愈自动生效=C5）；状态机
           loading→loaded/failed 由 reap 线程按退出码收口。
        """
        m = str(model or "").strip()
        if not m:
            return {"success": False, "supported": False,
                    "reason": "模型名为空，跳过预热"}
        # ① 解析同源 + 本地 provider 判定
        try:
            res = self._resolve_ai_model_config(
                str(provider or "").strip().lower() or None, m)
        except Exception as e:
            return {"success": False, "supported": False,
                    "reason": f"模型解析失败: {e}"}
        if not res.get("ok"):
            return {"success": False, "supported": False,
                    "reason": str(res.get("reason") or "模型解析失败")}
        prov = str(res.get("provider") or "").strip().lower()
        if prov not in self._AI_LOCAL_PROVIDERS:
            return {"success": False, "supported": False,
                    "reason": f"预热仅支持本地服务商（当前生效 {prov or '未配置'}）"}
        endpoint = str(res.get("endpoint") or "").strip() \
            or self._AI_PROVIDER_ENDPOINT_DEFAULTS.get(prov, "")
        fp = self._warmup_fingerprint(prov, endpoint, m)

        self._init_ai_state()
        # ② 单飞预检（快速路径；权威复检在④置 loading 的锁内）
        with self._ai_lock:
            cur = dict(self._warmup_state or {})
            busy = cur.get("state") == "loading" \
                or self._warmup_proc is not None
        if busy:
            return {"success": True, "supported": True,
                    "already_loading": True, **self._warmup_payload(cur)}
        # ③ C4 状态优先去重：在载 → hot 不 spawn
        loaded = self._warmup_probe_loaded(endpoint)
        if loaded is None:
            # lms 不在/端点不可达：静默不扰（不 spawn、不改状态机）
            return {"success": False, "supported": False,
                    "reason": f"端点不可达: {endpoint}"}
        if m in loaded:
            with self._ai_lock:
                self._warmup_state = {
                    "state": "hot", "fingerprint": fp, "provider": prov,
                    "model": m, "started_at": time.time(), "pid": None}
            _log.info("[warmup] 分析模型已在载，跳过预热（model=%s）", m)
            return {"success": True, "supported": True, "already_hot": True,
                    **self._warmup_payload(self._warmup_state)}
        # C4 状态优先（真值覆写）：探活成功且目标不在载 → 状态机残留的
        # loaded/hot 终态必属陈旧（典型=LM Studio TTL 已卸载），降级清位，
        # 防④指纹缓存把 TTL 后的重新预热永久抑制（误抑制=P1 收益归零）
        with self._ai_lock:
            stale = self._warmup_state
            if stale.get("state") in ("loaded", "hot"):
                _log.info("[warmup] 探活确认模型不在载，降级陈旧终态 "
                          "(state=%s) 允许重新预热（C4 状态判定优先）",
                          stale.get("state"))
                stale["state"] = "idle"
        # ④ G3 指纹去重 + 权威单飞（置 loading 前锁内复检，杜绝并发双 spawn）
        dup_fp = False
        with self._ai_lock:
            prev = dict(self._warmup_state or {})
            if prev.get("state") == "loading" \
                    or self._warmup_proc is not None:
                busy = True
            else:
                if prev.get("state") == "loaded" \
                        and prev.get("fingerprint") == fp:
                    self._warmup_state = {
                        "state": "loaded", "fingerprint": fp,
                        "provider": prov, "model": m,
                        "started_at": prev.get("started_at"),
                        "pid": prev.get("pid")}
                    dup_fp = True
                else:
                    self._warmup_state = {
                        "state": "loading", "fingerprint": fp,
                        "provider": prov, "model": m,
                        "started_at": time.time(), "pid": None}
                    dup_fp = False
        if busy:
            return {"success": True, "supported": True,
                    "already_loading": True, **self._warmup_payload(prev)}
        if dup_fp:
            return {"success": True, "supported": True, "skipped": True,
                    **self._warmup_payload(self._warmup_state)}
        # ⑤ spawn（同 refine_ai_analyze 参数源；G10 超时依据留痕）
        timeout_s, basis = self._warmup_timeout_s()
        _log.info("[warmup] 本次预热超时=%ss，依据=%s", timeout_s, basis)
        args = ["--warmup-analysis", "--ai-model", m, "--s1-provider", prov]
        flag = self._AI_PROVIDER_ENDPOINT_FLAGS.get(prov)
        if endpoint and flag:
            args.extend([flag, endpoint])
        env_extra: dict[str, str] = {"PYTHONUNBUFFERED": "1"}
        # 密钥仅经子进程环境变量注入（本地 provider 无密钥，表内不命中）
        key_env = self._AI_PROVIDER_KEY_ENV.get(prov)
        if key_env:
            try:
                from subtransjav.refine.secrets import read_secret
                key = read_secret(prov)
            except Exception:
                key = ""
            if key:
                env_extra[key_env] = key
        _log.info("[warmup] 预热可能切换 LM Studio 当前模型（model=%s "
                  "provider=%s endpoint=%s），已在 gui.log 留痕", m, prov,
                  endpoint)
        try:
            proc = cast(subprocess.Popen, spawn_refine_cli(
                args, cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                text=True, encoding="utf-8", errors="replace",
                env_extra=env_extra))
        except Exception as e:
            _log_exc("refine_warmup_analysis_model.spawn")
            with self._ai_lock:
                st = self._warmup_state
                if st.get("state") == "loading":
                    st["state"] = "failed"
                    st["finished_at"] = time.time()
            return {"success": False, "supported": True,
                    "error": f"预热子进程启动失败: {e}"}
        entry = self._register_child(proc, "warmup")
        with self._ai_lock:
            self._warmup_state["pid"] = int(proc.pid)

        def _reap(en: dict[str, Any], warm_model: str = m) -> None:
            """worker：communicate 排水两管道（批4 同款，防管道写满阻塞）
            并按退出码收口状态机；daemon 线程，退出清理树杀后自然返回。"""
            try:
                en["proc"].communicate()
                rc = en["proc"].returncode
            except Exception:
                rc = en["proc"].poll()
            with self._ai_lock:
                st = self._warmup_state
                if st.get("state") == "loading" \
                        and st.get("pid") == en.get("pid"):
                    st["state"] = "loaded" if rc == 0 else "failed"
                    st["finished_at"] = time.time()
                    done_state = str(st.get("state"))
                else:
                    done_state = ""
            self._release_child_slot("warmup", en)
            if done_state:
                _log.info("[warmup] 预热子进程退出 rc=%s（state=%s, "
                          "model=%s）", rc, done_state, warm_model)
        threading.Thread(target=_reap, args=(entry,), daemon=True,
                         name="gui-warmup-reap").start()
        return {"success": True, "supported": True,
                **self._warmup_payload(self._warmup_state)}

    def refine_cancel_warmup(self) -> dict[str, Any]:
        """停止进行中的分析模型预热（P1 批3）。

        (c) 阻断形态用户面无取消入口——本桥供超时放行（G7 第三态「杀客户端
        +清状态+放行翻译」）、退出清理与测试使用：已登记 → 身份核验后树杀
        +状态置 failed；未登记 → 幂等返回（不置闩：预热无 spawn 前用户
        取消竞态）。"""
        self._init_ai_state()
        r = self._cancel_registered(
            "warmup",
            {"success": True, "cancelled_pending": True,
             "message": "无进行中的预热"})
        if r.get("cancelled_pending"):
            return r
        with self._ai_lock:
            st = self._warmup_state
            if isinstance(st, dict) and st.get("state") == "loading":
                st["state"] = "failed"
                st["finished_at"] = time.time()
                st["cancelled"] = True
        return r

    def _warmup_after_session(self) -> None:
        """G2 触发点①主体（翻译会话级完成=整队列回 idle）。

        后端无前端解析上下文，自行读 ai_analyze_* KV+阶段A（批1
        _resolve_ai_model_config 同源）算解析并 spawn；解析失败/云 provider/
        已在载 → 桥内静默跳过。与前端触发去重靠桥内单飞+指纹。
        压制自动化（若有）为 ffmpeg 非 LLM 消费者，不构成同资源冲突，
        不抑制预热（勾账口径）。"""
        cur = self._warmup_resolve_current()
        if cur is None:
            return
        r = self.refine_warmup_analysis_model(cur[1], cur[0])
        _log.info("[warmup] 会话完成触发预热: supported=%s already_hot=%s "
                  "skipped=%s state=%s reason=%s",
                  r.get("supported"), r.get("already_hot"),
                  r.get("skipped"), r.get("state"), r.get("reason"))

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
    # 2.7.4 件F（D2026-1007-02）：上次手动媒体目录（推断⑤层附加搜索目录）
    # ——与 media_overrides 同走 stage_settings KV 既有读写通道
    _PREVIEW_MEDIA_LAST_DIR_KEY = "preview_media_last_dir"

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

    def _load_preview_media_last_dir(self) -> str:
        """preview_media_last_dir KV 读取（2.7.4 件F ⑤层）。

        缺失/空值/非现存目录 → 空串（调用方静默跳过⑤层，行为与
        四层时代完全一致）。经 refine_get_stage_settings 既有读取
        通道（零新增 open），全容错不抛。"""
        try:
            res = self.refine_get_stage_settings()
            if not res.get("success"):
                return ""
            settings = res.get("settings")
            val = settings.get(self._PREVIEW_MEDIA_LAST_DIR_KEY) \
                if isinstance(settings, dict) else None
            val = str(val or "").strip()
            if val and os.path.isdir(val):
                return val
            return ""
        except Exception:
            return ""

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
        2.7.4 件F（D2026-1007-02）：media_path 非空保存时同步把所选媒体
        父目录（normcase 绝对路径）写入同命名空间新键
        preview_media_last_dir（试听推断⑤层附加搜索目录）；空串删除
        不触碰该键。同一帧 patch 落盘，零新增写点。
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
            patch: dict[str, Any] = {self._MEDIA_OVERRIDES_KEY: overrides}
            if mp:
                from subtransjav.paths import normalize_path_case
                patch[self._PREVIEW_MEDIA_LAST_DIR_KEY] = \
                    normalize_path_case(os.path.dirname(os.path.abspath(mp)))
            res = self.refine_save_stage_settings(None, None, patch)
            if not res.get("success"):
                return {"success": False,
                        "error": str(res.get("error") or "持久化写入失败")}
            return {"success": True, "overrides_saved": len(overrides)}
        except Exception as e:
            _log_exc("refine_save_media_override")
            return {"success": False, "error": str(e)}

    def _infer_preview_media(self, guide_path: str,
                             clip_end_s: float,
                             search_dir: str = "") -> dict[str, Any]:
        """目录内自动推断试听媒体（件2 ④层 + 件F ⑤层共用唯一实现）。

        guide json 文件名剥导读后缀（复用 _AUDIO_PREVIEW_GUIDE_SUFFIX，不新增
        第 5 处字面量）→ 复用 asr_meta.strip_stem_suffixes 剥语言/管线后缀 →
        搜索目录内（不递归）normcase 精确基名匹配视频扩展名闭集。搜索目录
        由 search_dir 决定：空串=导读同目录（④层，media_source="inferred"）；
        非空=上次手动媒体目录（件F ⑤层，media_source="last_dir"）——stem
        仍取自导读文件名，跨目录候选集不合并（由调用方保证逐层独立）。
        2.7.4 件B
        （D2026-1007-02）：精确匹配按 _preview_stem_candidates 的 leveled
        候选序贯进行（首个产生命中的层即裁决：恰 1 个采用、多命中
        fail-closed），全层零命中再做边界感知前缀兜底。唯一命中再过
        时长守卫（fail-closed，owner 终版第 7 条）：复用 _review_media_duration
        （15s 超时元数据级），比较基准 clip_end=end+_AUDIO_PREVIEW_PAD_S，
        容差 max(5s, 1% 时长)；ffprobe 失败/None/时长不足一律拒绝自动采用。
        .ja 过度剥离边缘（如 song.ja.whisperjav 导读剥为 "song"，同目录仅有
        song.ja.mp4 时前缀兜底亦不命中——root "song.ja" 比 stem "song" 长，
        不构成 stem 前缀）→ 优雅降级 no_candidate，不误配。

        返回 {ok, media_path, media_source:"inferred"|"last_dir"} 或
        {ok:False, error_key, error, candidates:[文件名,...]}——
        no_candidate（零命中/多命中，多命中带候选列表并在 error 标注
        来源目录）/ duration_mismatch / verify_failed。
        """
        from subtransjav.paths import normalize_path_case
        from subtransjav.refine.asr_meta import strip_stem_suffixes
        suffix = self._AUDIO_PREVIEW_GUIDE_SUFFIX
        base = os.path.basename(str(guide_path or ""))
        if not base.endswith(suffix) or len(base) <= len(suffix):
            return {"ok": False, "error_key": "no_candidate",
                    "error": f"非导读文件: {base}", "candidates": []}
        stem = strip_stem_suffixes(base[:-len(suffix)])
        if search_dir:
            gdir = os.path.abspath(str(search_dir))
            src_label = f"指定目录 {gdir}"
        else:
            gdir = os.path.dirname(os.path.abspath(str(guide_path)))
            src_label = "导读同目录"
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
                    "error": f"未在{src_label}找到与「{stem}」匹配的媒体文件",
                    "candidates": []}
        if len(candidates) > 1:
            sorted_hits = sorted(candidates)
            return {"ok": False, "error_key": "no_candidate",
                    "error": f"{src_label}命中多个候选媒体，请显式指定: "
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
                "media_source": "last_dir" if search_dir else "inferred",
                "duration_s": round(dur, 3)}

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

        # —— 试听媒体路径五层优先级（2.7.4 件2 四层 + 件F ⑤层，评议员钉测）——
        # ① 本次请求显式 override > ② guide json 自带 media_path（文件有效
        # 时）> ③ GUI 持久化配置 > ④ 同目录自动推断 > ⑤ 上次手动媒体目录
        # 推断（④ 零命中后才尝试）。②失效（文件不存在/ffprobe 失败）才落
        # ③④⑤——不自动覆盖有效已有路径（owner 裁定）。
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
        last_dir_res: dict[str, Any] | None = None
        if not media and infer_res is not None \
                and infer_res.get("error_key") == "no_candidate" \
                and not infer_res.get("candidates"):
            # ⑤ 上次手动媒体目录（2.7.4 件F）：④ 零命中后才尝试——
            # 键缺失/目录不存在/非法静默跳过（行为与四层时代一致）；
            # 同目录多命中（fail-closed 带候选）不落⑤（不跨目录合并）；
            # last_dir 内多候选同样 fail-closed（error 标注来源目录）。
            last_dir = self._load_preview_media_last_dir()
            if last_dir:
                last_dir_res = self._infer_preview_media(
                    p, end + self._AUDIO_PREVIEW_PAD_S, search_dir=last_dir)
                if last_dir_res.get("ok"):
                    media = str(last_dir_res["media_path"])
                    media_source = str(
                        last_dir_res.get("media_source") or "last_dir")
        if not media:
            if failed_existing:
                return {"ok": False, "error_key": "path_invalid",
                        "error": "已有媒体路径失效: "
                                 + "；".join(failed_existing),
                        "candidates": (last_dir_res or infer_res or {}
                                       ).get("candidates", [])}
            if last_dir_res is not None:
                return last_dir_res
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
        # 批4（D2026-1008-01）：分析/修复登记槽全覆盖清理——上述 _translate
        # 分支语义零变化；新槽锁下快照后逐个走 terminate_registered（身份
        # 核验防 PID 复用误杀），随后台账覆盖写空（正常退出不留残留条目）。
        # 批3（D2026-1008-02 P1/C5）：预热槽一并纳入
        try:
            self._init_ai_state()
            with self._ai_lock:
                pending = [e for e in (self._ai_analyze_proc,
                                       self._batch_fix_proc,
                                       self._warmup_proc) if e]
                self._ai_analyze_proc = None
                self._batch_fix_proc = None
                self._warmup_proc = None
            for entry in pending:
                with contextlib.suppress(Exception):
                    terminate_registered(entry)
            self._ledger_sync()
        except Exception:
            pass
        import shutil
        for d in dict.fromkeys(getattr(self, "_refine_tmp_dirs", [])):
            try:
                if d and os.path.isdir(d):
                    shutil.rmtree(d, ignore_errors=True)
            except Exception:
                pass
        if getattr(self, "_refine_tmp_dirs", None):
            self._refine_tmp_dirs.clear()

    # ========================================================================
    # 硬字幕压制（2.8.0 批1 件4，D2026-1007-03；批清单 docs/design/d280-批1-批清单.md）
    # ========================================================================

    @staticmethod
    def _encode_queue():
        from subtransjav.webview_gui.encode_queue import (
            get_encode_queue,
            release_encode_slot,
        )
        q = get_encode_queue()
        # 队列空闲自动归还互斥槽（幂等重接；回调异常队列内侧已吞）
        q.on_idle = release_encode_slot
        return q

    @staticmethod
    def _parse_encode_params(raw: dict[str, Any]):
        """前端参数 dict → EncodeParams（缺省项补齐；非法值抛 ValueError）。"""
        from subtransjav.refine.hardsub import EncodeParams, parse_custom_params, validate_params
        raw = dict(raw or {})
        known = set(EncodeParams.__dataclass_fields__)
        params = EncodeParams(
            **{k: v for k, v in raw.items() if k in known and k != "out_path"})
        validate_params(params)
        parse_custom_params(params.custom_params)   # 逃生门黑名单前置校验
        return params

    def _encode_out_path(self, video_path: str, out_dir: str) -> str:
        """成品缺省名 <stem>_hardsub.mp4（输出目录缺省=视频同目录）。"""
        stem = os.path.splitext(os.path.basename(video_path))[0]
        directory = out_dir or os.path.dirname(video_path) or "."
        return os.path.join(directory, f"{stem}_hardsub.mp4")

    # 压制配对（批1：校对页/导读页给 srt，后端按契约配「终稿字幕+视频」）
    _ENCODE_VIDEO_EXTS = (".mp4", ".mkv", ".webm", ".mov", ".avi", ".ts", ".m2ts")

    @classmethod
    def _resolve_final_subtitle(cls, srt_path: str) -> str:
        """输入 srt → 终稿字幕：已是 _final_ 产物原样返回；否则按剥链候选
        （_preview_stem_candidates 闭集，深→浅）逐层拼 final_stem 契约名，
        首个存在即返；全无返回空串（调用方显因，不猜）。

        注意 strip_lang_suffix 只剥语言后缀（.zh 系），不剥 .ja.whisperjav
        管线链——必须走 preview 剥链闭集（黑盒实锤）。"""
        if "_final_" in os.path.basename(srt_path):
            return srt_path
        try:
            from subtransjav.refine.v2_outputs import final_stem
            p = Path(srt_path)
            stem = p.stem
            if "_final_" in stem:
                stem = stem[:stem.index("_final_")]
            for cand_stem in reversed(_preview_stem_candidates(stem)):
                cand = p.with_name(final_stem(cand_stem) + ".srt")
                if cand.is_file():
                    return str(cand)
            return ""
        except Exception:
            return ""

    @classmethod
    def _resolve_video_for_subtitle(cls, subtitle_path: str) -> str:
        """终稿字幕 → 视频：剥链候选 stem（复用 _preview_stem_candidates
        闭集，.merged/.ja/.whisperjav 系）× 常见视频扩展名，同目录首个
        命中；找不到返回空串。"""
        from subtransjav.refine.pipeline_support import strip_lang_suffix
        stem = Path(subtitle_path).stem
        if "_final_" in stem:
            stem = stem[:stem.index("_final_")]
        stem = strip_lang_suffix(stem)
        directory = os.path.dirname(subtitle_path) or "."
        for cand_stem in _preview_stem_candidates(stem):
            for ext in cls._ENCODE_VIDEO_EXTS:
                cand = os.path.join(directory, cand_stem + ext)
                if os.path.isfile(cand):
                    return cand
        return ""

    def _normalize_encode_jobs(self, jobs: list[dict[str, Any]]) -> list[dict[str, str]]:
        """入队载荷归一：{srt_path} 自动配对；显式 video/subtitle 优先。"""
        out: list[dict[str, str]] = []
        for job in jobs or []:
            srt = str(job.get("srt_path") or "")
            video = str(job.get("video_path") or "")
            subtitle = str(job.get("subtitle_path") or "")
            if subtitle and not video:
                video = self._resolve_video_for_subtitle(subtitle)
            if not subtitle and srt:
                subtitle = self._resolve_final_subtitle(srt)
                if subtitle and not video:
                    video = self._resolve_video_for_subtitle(subtitle)
            out.append({"video_path": video, "subtitle_path": subtitle,
                        "srt_path": srt})
        return out

    def encode_preflight(self, jobs: list[dict[str, Any]],
                         params: dict[str, Any]) -> dict[str, Any]:
        """入队前一次性校验（不落队、不占互斥槽）。

        逐 job：存在性（视频/字幕）→ ffprobe 探测 → 产物路径/覆盖 →
        体积估算与 ETA。供给缺口整体返回 supply_missing（前端引导按需
        下载）。ffmpeg 未就绪时跳过探测，仅返回存在性结果。批2 增：
        所选格式的 GPU 编码器解析（双检懒缓存，供面板后端选项显因）。
        """
        try:
            parsed = self._parse_encode_params(params)
        except ValueError as e:
            return {"success": False, "error": msg("encode_jobs_invalid", reason=str(e))}
        from subtransjav.refine.ffmpeg_supply import FfprobeError, resolve_hardsub_ffmpeg
        from subtransjav.refine.hardsub import speed_factor
        from subtransjav.webview_gui.encode_queue import (
            encode_active,
            estimate_output_bytes,
        )

        out_dir = str(params.get("out_dir") or "")
        supply = resolve_hardsub_ffmpeg()
        items: list[dict[str, Any]] = []
        total_eta = 0.0
        for job in self._normalize_encode_jobs(jobs):
            video = job["video_path"]
            subtitle = job["subtitle_path"]
            item: dict[str, Any] = {
                "video_path": video, "subtitle_path": subtitle,
                "srt_path": job["srt_path"],
                "video_exists": bool(video) and os.path.isfile(video),
                "subtitle_exists": bool(subtitle) and os.path.isfile(subtitle),
            }
            if supply.missing or not item["video_exists"]:
                items.append(item)
                continue
            out_path = self._encode_out_path(video, out_dir)
            item["out_path"] = out_path
            item["overwrite"] = os.path.isfile(out_path)
            try:
                if supply.ffprobe_path:
                    from subtransjav.refine.ffmpeg_supply import probe_media
                    info = probe_media(supply.ffprobe_path, video)
                    eta = info.duration_s * speed_factor(
                        parsed.video_format, parsed.quality)
                    item.update({
                        "duration_s": round(info.duration_s, 2),
                        "has_audio": info.has_audio,
                        "audio_codec": info.audio_codec,
                        "eta_s": round(eta, 1),
                        "estimated_bytes": estimate_output_bytes(
                            parsed, info.bit_rate_bps, info.duration_s),
                    })
                    total_eta += eta
            except FfprobeError as e:
                item["probe_error"] = str(e)
            items.append(item)
        return {
            "success": True,
            "supply_missing": list(supply.missing),
            "encode_running": encode_active(),
            "items": items,
            "total_eta_s": round(total_eta, 1),
            "gpu": self._resolve_gpu_for_preflight(supply, parsed),
        }

    @staticmethod
    def _resolve_gpu_for_preflight(supply, parsed) -> dict[str, Any]:
        """所选格式的 GPU 编码器解析（ffmpeg 就绪时；双检懒缓存）。"""
        if supply.missing or not supply.ffmpeg_path:
            return {"encoder": "", "reasons": ["ffmpeg 未就绪"]}
        from subtransjav.refine.ffmpeg_supply import resolve_gpu_encoder
        enc, reasons = resolve_gpu_encoder(supply.ffmpeg_path, parsed.video_format)
        return {"encoder": enc, "reasons": reasons}

    def encode_commit(self, jobs: list[dict[str, Any]],
                      params: dict[str, Any],
                      allow_overwrite: bool = False,
                      from_fullchain: bool = False) -> dict[str, Any]:
        """入队（D3：commit 时复验覆盖；互斥槽 check-and-set 后整批落队）。

        批1 b 段（D2026-1009-02）互斥对③：手动压制与全链状态机互斥——
        全链在飞时手动入队结构化拒绝（msg fullchain_running，不排队）；
        链尾自动压制经 _run_encode_automation 携 from_fullchain=True 绕过
        本判定（手动占用让位判定在链尾调用前完成=互斥对⑥反向）。"""
        self._init_ai_state()
        with self._ai_lock:
            # 批1 b 段互斥对③（入口判定，早于参数解析/落队）：全链在飞
            # 拒绝手动压制
            if self._fullchain_running and not from_fullchain:
                return {"success": False, "fullchain_running": True,
                        "error": msg("fullchain_running")}
        try:
            parsed = self._parse_encode_params(params)
        except ValueError as e:
            return {"success": False, "error": msg("encode_jobs_invalid", reason=str(e))}
        from subtransjav.webview_gui.encode_queue import (
            EncodeJob,
            claim_encode_slot,
            encode_active,
            release_encode_slot,
        )
        if encode_active():
            return {"success": False, "error": msg("translate_encode_conflict")}
        out_dir = str(params.get("out_dir") or "")
        # D3 复验：覆盖清单以 commit 时实际存在为准，新增覆盖项须重新确认
        overwrite_now: list[str] = []
        prepared: list[tuple[str, str, str]] = []
        for job in self._normalize_encode_jobs(jobs):
            video = job["video_path"]
            subtitle = job["subtitle_path"]
            if not video or not os.path.isfile(video):
                return {"success": False,
                        "error": msg("encode_jobs_invalid",
                                     reason=f"未找到视频文件（{job['srt_path'] or subtitle} 同目录需有同名视频）")}
            if not subtitle or not os.path.isfile(subtitle):
                return {"success": False,
                        "error": msg("encode_jobs_invalid",
                                     reason=f"终稿字幕不存在: {subtitle or job['srt_path']}")}
            out_path = self._encode_out_path(video, out_dir)
            if os.path.isfile(out_path):
                overwrite_now.append(out_path)
            prepared.append((video, subtitle, out_path))
        if overwrite_now and not allow_overwrite:
            return {"success": False, "needs_confirm": True,
                    "existing": overwrite_now}

        if not claim_encode_slot():
            return {"success": False, "error": msg("translate_encode_conflict")}
        q = self._encode_queue()
        encoded_jobs = [
            EncodeJob(video_path=v, subtitle_path=s, out_path=o, params=parsed)
            for v, s, o in prepared
        ]
        accepted, rejected = q.enqueue_batch(encoded_jobs)
        if not accepted:
            release_encode_slot()
            reason = "；".join(r for _, r in rejected[:3]) or "未知原因"
            return {"success": False,
                    "error": msg("encode_commit_rejected", reason=reason)}
        return {
            "success": True,
            "accepted": [j.snapshot() for j in accepted],
            "rejected": [{"video_path": j.video_path, "reason": r}
                         for j, r in rejected],
        }

    def encode_status(self) -> dict[str, Any]:
        """队列快照（前端 1s 轮询）。"""
        q = self._encode_queue()
        return {"success": True, "running": q.is_running(),
                "jobs": q.snapshot()}

    def encode_cancel(self, job_id: str = "") -> dict[str, Any]:
        """取消（job_id 空=当前 running+清空 queued）。"""
        q = self._encode_queue()
        q.cancel(job_id or None)
        return {"success": True}

    def encode_retry(self, job_id: str) -> dict[str, Any]:
        """失败/取消任务重试（复制入队尾）。"""
        q = self._encode_queue()
        new_id = q.retry(job_id)
        if new_id is None:
            return {"success": False, "error": msg("encode_jobs_invalid",
                                                   reason="任务不可重试或不存在")}
        return {"success": True, "new_id": new_id}

    def encode_open_folder(self, job_id: str) -> dict[str, Any]:
        """打开任务成品所在文件夹（复用 open_output_folder 既有通道）。"""
        q = self._encode_queue()
        target = next((j for j in q.snapshot() if j["id"] == job_id), None)
        if target is None:
            return {"success": False, "error": msg("encode_jobs_invalid",
                                                   reason="任务不存在")}
        folder = os.path.dirname(target["out_path"]) or "."
        return self.open_output_folder(folder, create=False)

    def encode_get_last_params(self) -> dict[str, Any]:
        """上次压制参数（config/hardsub_last.json；缺省返回空 dict）。"""
        from subtransjav.refine.config import CONFIG_DIR
        path = os.path.join(str(CONFIG_DIR), "hardsub_last.json")
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            return {"success": True, "params": data if isinstance(data, dict) else {}}
        except Exception:
            return {"success": True, "params": {}}

    # -- 自建预设（批2：hardsub_presets.json KV 上限 20，损坏降级+.bak）----

    _HARDSUB_PRESET_CAP = 20

    @staticmethod
    def _hardsub_presets_path() -> str:
        from subtransjav.refine.config import CONFIG_DIR
        return os.path.join(str(CONFIG_DIR), "hardsub_presets.json")

    def _load_hardsub_presets(self) -> dict[str, Any]:
        """预设装载：形状损坏→key 级降级（留 .bak 档案）回空表，不抛。"""
        path = self._hardsub_presets_path()
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict) and isinstance(data.get("presets"), dict):
                return {str(k): v for k, v in data["presets"].items()
                        if isinstance(k, str) and isinstance(v, dict)}
            raise ValueError("形状不符")
        except Exception:
            if os.path.isfile(path):
                import shutil
                with contextlib.suppress(OSError):
                    shutil.copy2(path, path + ".bak")
                _log_exc("_load_hardsub_presets(降级)")
            return {}

    def _save_hardsub_presets(self, presets: dict[str, Any]) -> None:
        """预设原子落盘（_atomic_write_text；写前旧档滚动 .bak）。"""
        import shutil

        from subtransjav.refine.config import CONFIG_DIR
        from subtransjav.refine.fs_utils import _atomic_write_text
        path = self._hardsub_presets_path()
        os.makedirs(str(CONFIG_DIR), exist_ok=True)
        if os.path.isfile(path):
            with contextlib.suppress(OSError):
                shutil.copy2(path, path + ".bak")
        _atomic_write_text(path, json.dumps({"presets": presets},
                                            ensure_ascii=False, indent=2))

    def encode_presets_list(self) -> dict[str, Any]:
        """预设清单：内置三档（只读）+ 用户自建。"""
        return {
            "success": True,
            "builtin": [
                {"name": "高压缩", "params": {"video_format": "h264", "quality": "compress"}},
                {"name": "均衡", "params": {"video_format": "h264", "quality": "balanced"}},
                {"name": "高画质", "params": {"video_format": "h264", "quality": "quality"}},
            ],
            "user": self._load_hardsub_presets(),
        }

    def encode_preset_save(self, name: str, params: dict[str, Any]) -> dict[str, Any]:
        """保存/覆盖用户预设（上限 20；params 全量快照由前端组装）。"""
        key = str(name or "").strip()
        if not key:
            return {"success": False, "error": "预设名不能为空"}
        if len(key) > 40:
            return {"success": False, "error": "预设名过长（≤40 字符）"}
        presets = self._load_hardsub_presets()
        if key not in presets and len(presets) >= self._HARDSUB_PRESET_CAP:
            return {"success": False,
                    "error": f"预设已达上限 {self._HARDSUB_PRESET_CAP} 个，请先删除不再使用的预设"}
        presets[key] = dict(params or {})
        try:
            self._save_hardsub_presets(presets)
        except Exception as e:
            _log_exc("encode_preset_save")
            return {"success": False, "error": str(e)}
        return {"success": True}

    def encode_preset_delete(self, name: str) -> dict[str, Any]:
        """删除用户预设（内置三档不可删，前端不下发此处兜底）。"""
        presets = self._load_hardsub_presets()
        key = str(name or "").strip()
        if key not in presets:
            return {"success": False, "error": "预设不存在"}
        del presets[key]
        try:
            self._save_hardsub_presets(presets)
        except Exception as e:
            _log_exc("encode_preset_delete")
            return {"success": False, "error": str(e)}
        return {"success": True}

    def encode_save_last_params(self, params: dict[str, Any]) -> dict[str, Any]:
        """上次压制参数持久化（fs_utils 原子写；不碰 refine_save_stage_settings）。"""
        from subtransjav.refine.config import CONFIG_DIR
        from subtransjav.refine.fs_utils import _atomic_write_text
        try:
            path = os.path.join(str(CONFIG_DIR), "hardsub_last.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _atomic_write_text(path, json.dumps(params or {}, ensure_ascii=False, indent=2))
            return {"success": True}
        except Exception as e:
            _log_exc("encode_save_last_params")
            return {"success": False, "error": str(e)}

    def encode_save_params(self, params_json: str) -> dict[str, Any]:
        """压制参数独立设置项保存（D2026-1008-01 批2）：复用 encode_preflight
        同一校验路径（_parse_encode_params=EncodeParams 全量校验+逃生门黑
        名单前置），只校验不建 job 不入队；通过后原子写 config/hardsub_last.json
        （写法对齐 encode_get_last_params / encode_save_last_params 先例，
        数据根解析沿用 CONFIG_DIR 既有 helper），并盖 saved_at 时间戳供前端
        摘要行展示。失败返回 {success, error, tip}（_refine_error_tip 人话
        风格）；编辑模式弹窗经此保存，绝不触碰 preflight/commit/jobs。"""
        try:
            raw = json.loads(params_json) if isinstance(params_json, str) \
                else dict(params_json or {})
        except (TypeError, ValueError) as e:
            return {"success": False,
                    "error": msg("encode_jobs_invalid", reason=f"参数 JSON 无法解析（{e}）"),
                    "tip": msg("encode_params_tip_json")}
        if not isinstance(raw, dict):
            return {"success": False,
                    "error": msg("encode_jobs_invalid", reason="参数须为对象（键值表）"),
                    "tip": msg("encode_params_tip_json")}
        try:
            self._parse_encode_params(raw)
        except ValueError as e:
            return {"success": False,
                    "error": msg("encode_jobs_invalid", reason=str(e)),
                    "tip": msg("encode_params_tip_invalid")}
        from subtransjav.refine.config import CONFIG_DIR
        from subtransjav.refine.fs_utils import _atomic_write_text
        try:
            data = dict(raw)
            data["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            path = os.path.join(str(CONFIG_DIR), "hardsub_last.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            _atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2))
        except Exception as e:
            _log_exc("encode_save_params")
            return {"success": False, "error": str(e),
                    "tip": msg("encode_params_tip_write")}
        return {"success": True, "params": data}

    # -- ffmpeg 按需下载（独立进度通道；词典四态范式，_supplyBusy 单飞）----

    def ffmpeg_supply_download(self) -> dict[str, Any]:
        """后台下载 pinned BtbN full 变体落位数据根（单飞；进度走
        ffmpeg_supply_progress 轮询）。"""
        if getattr(self, "_supply_busy", False):
            return {"success": False, "error": "ffmpeg 下载已在进行中"}
        self._supply_busy = True
        self._supply_stop = threading.Event()
        state = self._ensure_supply_state()
        state.update(phase="downloading", received=0, total=0, error="")

        def worker():
            try:
                from subtransjav import paths
                from subtransjav.refine.ffmpeg_supply import download_full_variant

                def cb(received: int, total: int) -> None:
                    state["received"] = received
                    state["total"] = total

                download_full_variant(str(paths.data_root()), progress_cb=cb,
                                      stop_event=self._supply_stop)
                state["phase"] = "done"
                self._encode_queue().reset_supply()
            except Exception as e:  # noqa: BLE001  供给异常统一落状态（含 SupplyStopped）
                from subtransjav.refine.ffmpeg_supply import SupplyStopped
                state["phase"] = "stopped" if isinstance(e, SupplyStopped) else "failed"
                state["error"] = str(e)
            finally:
                self._supply_busy = False

        threading.Thread(target=worker, name="ffmpeg-supply-download",
                         daemon=True).start()
        return {"success": True}

    def ffmpeg_supply_stop(self) -> dict[str, Any]:
        """协作停止下载（残件清理由供给层 finally 保证）。"""
        event = getattr(self, "_supply_stop", None)
        if event is not None:
            event.set()
        return {"success": True}

    def ffmpeg_supply_progress(self) -> dict[str, Any]:
        """下载进度快照（phase: idle/downloading/done/failed/stopped）。"""
        state = self._ensure_supply_state()
        return {"success": True, **state,
                "busy": bool(getattr(self, "_supply_busy", False))}

    def _ensure_supply_state(self) -> dict[str, Any]:
        if not hasattr(self, "_supply_state"):
            self._supply_state: dict[str, Any] = {
                "phase": "idle", "received": 0, "total": 0, "error": ""}
        return self._supply_state

    def _on_translation_session_completed(self, summary: dict[str, Any]) -> None:
        """翻译会话结束钩子（批3 自动化接线）：用户勾选「翻译完成后自动
        压制」（管线设置 encode_auto_enabled）时，收集本会话完成文件→
        契约配对→成品已存在跳过（自动化语义，不覆盖）→余者入队→
        lms unload --all 清场（复用 lmstudio 既有路径，失败告警不阻塞）。
        once 守卫见批1；cancelled/error 不触发（C9）。
        P1 批3 增：钩子尾部挂 G2 预热触发点①（会话级完成=整队列回 idle，
        "无自动继续"以会话级判据落实；压制自动化为 ffmpeg 非 LLM 消费者
        不构成资源冲突，不抑制预热）。
        批1 a 段（D2026-1009-02）C5/C-2 单通道：全链开关开启时整体改道
        _run_fullchain_automation daemon 线程——旧 encode 分支与 warmup
        daemon 均不执行（预热由链首环承接，压制改链尾 C7 时序门）；关闭
        态下列路径逐字节不变（C-3 回归口径）。钩子被 get_translation_status
        轮询线程同步调用，链必须 daemon 化防卡死前端轮询。"""
        if getattr(self, "_session_hook_fired", False):
            return
        self._session_hook_fired = True
        if self._fullchain_auto_enabled():
            try:
                th = threading.Thread(target=self._run_fullchain_automation,
                                      args=(summary,), daemon=True,
                                      name="gui-fullchain-auto")
                self._fullchain_thread = th   # 测试可显式 join（批1 a 段）
                th.start()
            except Exception:
                _log_exc("_run_fullchain_automation")
            return
        try:
            if self._encode_automation_enabled():
                self._run_encode_automation(summary)
        except Exception:
            _log_exc("_on_translation_session_completed")
        # G2 触发点①：daemon 线程内解析+spawn（探活≤5s 不占桥轮询线程）；
        # 桥内单飞+C4 探活+G3 指纹与前端触发天然去重
        try:
            threading.Thread(target=self._warmup_after_session,
                             daemon=True,
                             name="gui-warmup-session-hook").start()
        except Exception:
            _log_exc("_warmup_after_session")

    def _encode_automation_enabled(self) -> bool:
        """管线设置 encode_auto_enabled（refine_save_stage_settings 同一
        settings KV；缺省关）。"""
        try:
            with open(self._refine_stage_settings_path(), encoding="utf-8") as f:
                data = json.load(f)
            return bool((data.get("settings") or {}).get("encode_auto_enabled"))
        except Exception:
            return False

    def _fullchain_auto_enabled(self) -> bool:
        """管线设置 fullchain_auto_enabled（refine_save_stage_settings 同一
        settings KV；缺省关）。全链自动化总开关（批1 a 段，
        D2026-1009-02 批1 a 段）。"""
        try:
            with open(self._refine_stage_settings_path(), encoding="utf-8") as f:
                data = json.load(f)
            return bool(
                (data.get("settings") or {}).get("fullchain_auto_enabled"))
        except Exception:
            return False

    # ------------------------------------------------------------------
    # 全链自动化状态机（批1 a 段骨架，D2026-1009-02 批1 a 段）
    # ------------------------------------------------------------------

    @staticmethod
    def _fullchain_now() -> str:
        """C9 运行快照时间戳（本地时间，秒级 ISO 形态）。"""
        return time.strftime("%Y-%m-%dT%H:%M:%S")

    def _fullchain_last_run_path(self) -> str:
        """全链上次运行落点（config/fullchain_last_run.json；CONFIG_DIR
        同款锚 + 安全锚点校验，仿 _refine_stage_settings_path）。"""
        try:
            from subtransjav.refine.config import CONFIG_DIR
        except Exception:
            return os.path.join(os.getcwd(), "fullchain_last_run.json")
        return str(_resolve_safe_path(
            os.path.join(CONFIG_DIR, "fullchain_last_run.json")))

    def _fullchain_read_last_run(self) -> dict[str, Any]:
        """读上次运行快照（缺失/损坏回退空 dict——宁漏勿滥，与子进程
        台账读口径一致）。"""
        try:
            with open(self._fullchain_last_run_path(),
                      encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _fullchain_write_last_run(self, run: dict[str, Any]) -> None:
        """覆盖式原子写运行快照（fs_utils 单一来源；fail-soft：落盘绝不
        拖垮业务链）。字段语义：phase=running|skipped|done|failed；
        files_total/files_done=会话完成文件数/已处理完文件数；
        entries_fixed/failed=台账口径修复成败条数；entries_pending=已甄别
        可修但未结算（含 nochange 等未入账量）；missed_skipped=漏听段
        （F4）跳过/放弃数（a 段插缝恒 0，批3 接线）。"""
        try:
            from subtransjav.refine.fs_utils import _atomic_write_text
            path = self._fullchain_last_run_path()
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            _atomic_write_text(
                path, json.dumps(run, ensure_ascii=False, indent=2))
        except Exception:
            _log_exc("_fullchain_write_last_run")

    def _resolve_guide_for_done_key(self, done_key: str) -> str:
        """会话完成文件 → 导读 json 路径（同目录伴生成品命名口径）。

        summary files 键=管线 phase 事件 file 字段（输入文件 basename，
        event_stream.py per-file 通道现役形态）。stem 取 basename 剥扩展
        → 剥 ``_final_`` 段（_resolve_final_subtitle 同法）→
        strip_lang_suffix → _preview_stem_candidates 剥链闭集逐层试
        ``{cand}_质量报告导读.json``，首个存在即返；全无返回空串（调用方
        诚实跳过+通知，不静默不强制生成）。"""
        from subtransjav.refine.pipeline_support import (
            GUIDE_JSON_SUFFIX,
            strip_lang_suffix,
        )
        key = str(done_key or "").strip()
        base = os.path.basename(key)
        if not base:
            return ""
        if base.endswith(GUIDE_JSON_SUFFIX):
            return key                     # 键已是导读（防御）
        stem = base[:-4] if base.lower().endswith(".srt") \
            else os.path.splitext(base)[0]
        if "_final_" in stem:
            stem = stem[:stem.index("_final_")]
        stem = strip_lang_suffix(stem)
        directory = os.path.dirname(key) or "."
        for cand in _preview_stem_candidates(stem):
            gp = os.path.join(directory, cand + GUIDE_JSON_SUFFIX)
            if os.path.isfile(gp):
                return gp
        return ""

    def _fullchain_fixable_entries(self, p: str, stem: str,
                                   guide: dict[str, Any]) -> list[dict[str, Any]]:
        """逐文件 fixable 甄别（零 AI 调用；a 段 d 项）：status=="open" +
        current_text 非空（无现译绝不自动，C6 同源）+ 台账未修
        （_applied_timings 同源口径，与 refine_batch_fix 幂等守卫同法）+
        分类白名单 fail-closed（_FULLCHAIN_AUTO_CATEGORIES 闭集，未知类别
        不自动）。返回 [{index, timing}] 按 index 升序（供 ≤50 切批）。"""
        applied = self._applied_timings(os.path.dirname(p), stem)
        out: list[dict[str, Any]] = []
        for it in guide.get("items") or []:
            if not isinstance(it, dict) or it.get("status") != "open":
                continue
            cur = it.get("current_text")
            if not isinstance(cur, str) or not cur.strip():
                continue
            cat = str(it.get("category") or "")
            if (cat not in _FULLCHAIN_AUTO_CATEGORIES
                    and not cat.startswith(
                        _FULLCHAIN_AUTO_CATEGORY_PREFIXES)):
                continue
            idx = it.get("index")
            if isinstance(idx, bool) or not isinstance(idx, int):
                continue
            if str(it.get("timing") or "") in applied:
                continue                   # 台账已修：幂等跳过
            out.append({"index": idx,
                        "timing": str(it.get("timing") or "")})
        out.sort(key=lambda e: e["index"])
        return out

    def _run_fullchain_missed_stage(self, files_ctx: list[dict[str, Any]]) -> None:
        """F4 疑似漏听二级自动化插缝（批3 接入；a 段空位恒 None 零副作用）。

        批3 计划（D2026-1009-02 第二节批3，C19 序=修复→漏听→复验）：
        批量转写一次装载转 N 段（C17）→ asr_runner 透传 no_speech_prob/
        avg_logprob（C13）三维置信门 + ≤1s 语音能量一律放弃 → 高置信自动
        补行走独立插入通道（C15/C16；开工门=C22 校准达标）→ 放弃数计入
        missed_skipped 与 digest/通知。files_ctx=a 段甄别产物（有导读
        文件的 guide_path/p/stem 清单），批3 据此定位媒体与时间轴。"""
        return None

    def _run_fullchain_automation(self, summary: dict[str, Any]) -> None:
        """全链自动化状态机主体（批1 a 段骨架）。

        触发=翻译会话完成钩子 daemon 线程（钩子被 get_translation_status
        轮询线程同步调用，链不得占桥线程）。链内序：
        a) 入口重入判定（_fullchain_running，_ai_lock 保护）；
        b) provider 单源门（_resolve_ai_model_config；未配置/云端不启动，
           N-6 云端零出域）；
        c) 预热首环（C5：全链开启时前端预热短路，由本环承接，等价
           _warmup_after_session 主体；解析不可用=通知注明后跳过）；
        d) 逐文件甄别（导读解析+fixable 过滤，零 AI 调用）；
        e) 分批 refine_batch_fix(verify=False)（串行逐批独立进出；单批
           失败计数后继续，不中断链、不重试）；
        f) F4 漏听插缝（批3 接入，a 段空位）；
        g) 复验恰 1 次（refine_ai_analyze 显式 provider/model，链级长期
           不变式「--ai-analyze spawn==1」；失败如实计入不重试）；
        h) 链尾压制（C7 时序门：encode 自动化在复验后排布，复用其内部
           notice/unload；关闭态仅通知收尾）。

        全程通知走 _automation_notice（不静默不强制生成）；C9 运行快照落
        config/fullchain_last_run.json（启动写一次/每文件后更新/收尾补
        ended_at）；finally 清 _fullchain_running。b 段互斥矩阵消费
        _fullchain_running 标志（链在飞=手动入口显式拒绝，不排队；链内
        调用携 from_fullchain=True 绕过，复验/压制占用让位见链内 b 段注）。"""
        self._init_ai_state()
        with self._ai_lock:
            if self._fullchain_running:
                return                     # 防重叠：链已在飞直接返回
            self._fullchain_running = True
        # C9 运行快照：启动写一次（ended_at 空=未完成态），每文件后更新，
        # 收尾（含异常）补 ended_at
        run: dict[str, Any] = {
            "phase": "running", "files_total": 0, "files_done": 0,
            "entries_fixed": 0, "entries_failed": 0, "entries_pending": 0,
            "missed_skipped": 0,
            "started_at": self._fullchain_now(), "ended_at": ""}
        try:
            self._fullchain_write_last_run(run)
            # b) provider 单源门（云端/未配置=通知不启动）
            try:
                cfg = self._resolve_ai_model_config()
            except Exception as e:
                _log_exc("_run_fullchain_automation.resolve")
                cfg = {"ok": False, "reason": str(e)}
            provider = str(cfg.get("provider") or "").strip().lower()
            model = str(cfg.get("model") or "").strip()
            if (not cfg.get("ok")
                    or provider not in self._AI_LOCAL_PROVIDERS or not model):
                self._automation_notice(
                    "[全链] 自动化未启动：分析模型未配置或当前生效服务商为"
                    "云端（全链自动化仅支持本地模型）")
                run["phase"] = "skipped"
                return
            self._automation_notice(
                "[全链] 自动化开始：分析→批量修复→复验"
                "（自动压制排布视压制开关，于复验后执行）")
            # c) 预热首环（C5：承接前端短路的预热；失败/跳过不阻断链）
            cur = self._warmup_resolve_current()
            if cur is not None:
                try:
                    wr = self.refine_warmup_analysis_model(cur[1], cur[0])
                    _log.info("[fullchain] 链首预热: supported=%s "
                              "already_hot=%s", wr.get("supported"),
                              wr.get("already_hot"))
                except Exception:
                    _log_exc("_run_fullchain_automation.warmup")
            else:
                self._automation_notice(
                    "[全链] 预热跳过：当前分析模型配置不可用（链照常继续）")
            # d/e) 逐文件甄别 + 分批修复
            files_status = dict(summary.get("files") or {})
            done_keys = [str(k) for k, st in files_status.items()
                         if st == "done"]
            run["files_total"] = len(done_keys)
            self._fullchain_write_last_run(run)
            planned = 0                    # 累计甄别可修条数（pending 分母）
            verify_target: str = ""        # g) 复验目标=首个有导读文件的报告 txt
            files_ctx: list[dict[str, Any]] = []   # f) F4 插缝上下文
            for key in done_keys:
                guide_path = self._resolve_guide_for_done_key(key)
                if not guide_path:
                    self._automation_notice(
                        f"[全链] 跳过 {key}：未找到导读 json（诚实跳过）")
                    run["files_done"] = int(run["files_done"]) + 1
                    self._fullchain_write_last_run(run)
                    continue
                p, stem, guide, err = self._load_validated_guide(guide_path)
                if err is not None:
                    self._automation_notice(
                        f"[全链] 跳过 {os.path.basename(guide_path)}："
                        f"{err.get('error') or '导读校验失败'}")
                    run["files_done"] = int(run["files_done"]) + 1
                    self._fullchain_write_last_run(run)
                    continue
                files_ctx.append({"guide_path": guide_path, "p": p,
                                  "stem": stem})
                if not verify_target:
                    verify_target = os.path.join(
                        os.path.dirname(p), stem + self._AI_REPORT_SUFFIX)
                fixable = self._fullchain_fixable_entries(p, stem, guide)
                planned += len(fixable)
                run["entries_pending"] = planned - int(run["entries_fixed"]) \
                    - int(run["entries_failed"])
                if not fixable:
                    self._automation_notice(
                        f"[全链] {stem}：无可自动修复条目，跳过")
                    run["files_done"] = int(run["files_done"]) + 1
                    self._fullchain_write_last_run(run)
                    continue
                file_fixed = 0
                file_failed = 0
                batches = [fixable[i:i + self._BATCH_FIX_MAX_ENTRIES]
                           for i in range(0, len(fixable),
                                          self._BATCH_FIX_MAX_ENTRIES)]
                for batch in batches:
                    try:
                        # 批1 b 段互斥对②：链内调用携 from_fullchain=True
                        # 绕过全链在飞判定（仍受重入守卫约束）
                        r = self.refine_batch_fix(
                            guide_path, [e["index"] for e in batch],
                            verify=False, from_fullchain=True)
                    except Exception:
                        _log_exc("_run_fullchain_automation.batch")
                        r = {"success": False}
                    if r.get("success"):
                        file_fixed += int(r.get("applied") or 0)
                        file_failed += int(r.get("failed") or 0)
                    else:
                        # 单批失败：计数后继续下一批（不中断链、不重试；
                        # 失败主因已由 refine_batch_fix 落 gui.log）
                        file_failed += len(batch)
                run["entries_fixed"] = int(run["entries_fixed"]) + file_fixed
                run["entries_failed"] = int(run["entries_failed"]) + file_failed
                run["entries_pending"] = planned - int(run["entries_fixed"]) \
                    - int(run["entries_failed"])
                self._automation_notice(
                    f"[全链] {stem}：修复完成 {file_fixed} 条，"
                    f"失败 {file_failed} 条")
                run["files_done"] = int(run["files_done"]) + 1
                self._fullchain_write_last_run(run)
            # f) F4 漏听插缝（批3 接入：批量转写→置信门→补行/放弃）
            self._run_fullchain_missed_stage(files_ctx)
            # g) 复验恰 1 次（链级不变式：--ai-analyze spawn==1）。与批内
            # 修复同 model/provider 源（链首单源解析结果显式透传，绕开
            # refine_ai_analyze 内联决策歧义；报告 txt 与手动复验同源=
            # 导读 companions _AI_REPORT_SUFFIX）
            if verify_target and os.path.isfile(verify_target):
                # 批1 b 段互斥对④反向：手动 AI 分析在飞 → 复验跳过（不排队
                # 不重试），链继续收尾；链内调用携 from_fullchain=True 绕过
                # b 段新增的全链在飞拒绝（仍受 refine_ai_analyze 单飞守卫）
                with self._ai_lock:
                    manual_analyze_busy = bool(
                        self._ai_analyze_running
                        or self._ai_analyze_proc is not None)
                if manual_analyze_busy:
                    self._automation_notice(
                        "[全链] 复验跳过：AI 分析正被手动任务占用（不排队不"
                        "重试），可待其完成后手动发起全片分析")
                else:
                    self._automation_notice("[全链] 全片复验（恰 1 次）…")
                    try:
                        vr = self.refine_ai_analyze(
                            verify_target, model, provider,
                            from_fullchain=True)
                    except Exception:
                        _log_exc("_run_fullchain_automation.verify")
                        vr = {"success": False}
                    if vr.get("success"):
                        self._automation_notice(
                            "[全链] 复验完成，建议件已更新（仅供人工裁决）")
                    else:
                        self._automation_notice(
                            "[全链] 复验失败（如实计入，不重试）："
                            f"{str(vr.get('error') or '')[:120]}")
            else:
                self._automation_notice(
                    "[全链] 复验跳过：质量报告 txt 缺失")
            # h) 链尾压制（C7 时序门：压制排布在复验之后；全链开启时旧
            # 钩子 encode 分支已短路，此处为唯一压制入口）。批1 b 段互斥对
            # ⑥反向：手动压制在飞（encode 队列忙=互斥槽已占）→ 跳过自动
            # 压制（不排队不重试）+通知；否则携 from_fullchain=True 入队
            pending = int(run["entries_pending"])
            done_note = (f"[全链] 收尾：文件 {run['files_done']}/"
                         f"{run['files_total']}，修复 {run['entries_fixed']} 条"
                         f"，失败 {run['entries_failed']} 条"
                         + (f"，待处理 {pending} 条" if pending else ""))
            if self._encode_automation_enabled():
                from subtransjav.webview_gui.encode_queue import encode_active
                manual_encode_busy = encode_active()
                self._automation_notice(done_note)
                if manual_encode_busy:
                    self._automation_notice(
                        "[全链] 全链完成，压制被手动任务占用，请手动压制")
                else:
                    self._run_encode_automation(summary, from_fullchain=True)
            else:
                self._automation_notice(
                    done_note + "；未开启自动压制")
            run["phase"] = "done"
        except Exception:
            _log_exc("_run_fullchain_automation")
            run["phase"] = "failed"
        finally:
            run["ended_at"] = self._fullchain_now()
            self._fullchain_write_last_run(run)
            with self._ai_lock:
                self._fullchain_running = False

    def fullchain_last_run_status(self) -> dict[str, Any]:
        """全链上次运行状态桥（批1 a 段 C9；公开桥方法=js_api 全量暴露，
        批2 链级面板与黑盒断言消费）。

        返回 {success, last_run（落盘快照，缺失/损坏=空 dict）, unfinished}；
        「上次未完成」判定=有快照且读取时 ended_at 为空且 phase!="done"
        （链中途进程终止的残迹；正常收尾含 failed 亦补 ended_at，不算
        未完成；无快照/空快照=从未运行，不误报未完成）。"""
        run = self._fullchain_read_last_run()
        unfinished = (bool(run)
                      and not str(run.get("ended_at") or "").strip()
                      and str(run.get("phase") or "") != "done")
        return {"success": True, "last_run": run, "unfinished": unfinished}

    def fullchain_automation_status(self) -> dict[str, Any]:
        """全链运行态查询桥（批1 a 段；公开桥方法）：running=状态机在飞
        （_fullchain_running 标志，_ai_lock 下读取）；last_run=上次运行
        快照（与 fullchain_last_run_status 同源读取）。批2 消费。"""
        self._init_ai_state()
        with self._ai_lock:
            running = bool(self._fullchain_running)
        return {"success": True, "running": running,
                "last_run": self._fullchain_read_last_run()}

    # ------------------------------------------------------------------
    # 一键回滚（3.0 批2，D2026-1009-02 批2）：改写恢复语义——把终稿译文
    # 恢复为台账 outcome=="applied" 记录的修复前文本（old_text 是唯一
    # 回滚依据，action_retranslate 写序契约保证台账先于终稿落盘）。删行
    # 路径（auto_insert 回滚）批3 接线，本批跳过并如实计数。
    # ------------------------------------------------------------------

    def _rollback_candidates(self, guide_dir: str,
                             stem: str) -> tuple[dict[str, str], int]:
        """台账 → timing→old_text 恢复映射 + auto_insert 跳过计数。

        只取 outcome=="applied" 且 old_text 非空的记录；同一 timing 多条
        applied 时后者覆盖前者（最后一次修复的 old_text 即终稿当前文本）。
        category=="auto_insert"（批3 插入行）不参与恢复，只计数。"""
        restore: dict[str, str] = {}
        auto_insert = 0
        for rec in self._read_ledger(guide_dir, stem):
            if not isinstance(rec, dict):
                continue
            if str(rec.get("category") or "") == "auto_insert":
                auto_insert += 1
                continue
            if rec.get("outcome") != "applied":
                continue
            timing = str(rec.get("timing") or "").strip()
            old_text = rec.get("old_text")
            if not timing or not isinstance(old_text, str) or not old_text:
                continue
            restore[timing] = old_text
        return restore, auto_insert

    def fullchain_rollback_preview(self, guide_path: str) -> dict[str, Any]:
        """回滚预检桥（前端确认框文案消费）：返回 {success, applied,
        auto_insert}——applied=可恢复条数（去重后 timing 数），
        auto_insert=台账中插入行条数（暂不支持恢复，确认框条件化提示）。"""
        try:
            from subtransjav.refine.action_retranslate import _load_guide
            _, guide_dir, stem = _load_guide(guide_path)
        except Exception as e:  # noqa: BLE001  结构化失败如实回传
            return {"success": False, "error": str(e)}
        restore, auto_insert = self._rollback_candidates(
            str(guide_dir), stem)
        return {"success": True, "applied": len(restore),
                "auto_insert": auto_insert}

    def fullchain_rollback(self, guide_path: str) -> dict[str, Any]:
        """一键回滚桥（3.0 批2）：终稿译文恢复为台账修复前文本。

        语义（D2026-1009-02 批2）：
        - 预检：全链在飞（_fullchain_running）显式拒绝（互斥矩阵同源）；
          台账无 applied 记录 → success+restored=0 如实返回；
          终稿缺失 → 结构化失败（msg("fullchain_rollback_missing_final")）。
        - 定位：parse_srt 终稿 → timing setdefault 单值映射（重号 timing
          第一命中，与 action_retranslate._load_source_map 同口径）；
          未命中 timing 计入 unmatched 如实返回，不猜测。
        - 写序契约保持：回滚台账记录（outcome="rollback"，10 键齐，
          old_text=回滚前当前文、new_text=恢复后文本、reason="manual
          rollback"）先于终稿原子写落盘。
        - auto_insert（批3 插入行）跳过不处理，计数 auto_insert_skipped
          供前端条件化文案（删行接线批3）。"""
        self._init_ai_state()
        with self._ai_lock:
            if self._fullchain_running:
                return {"success": False, "error": msg("fullchain_running")}
        try:
            from subtransjav.refine.action_retranslate import (
                _append_ledger,
                _load_guide,
            )
            from subtransjav.refine.filters import build_srt, parse_srt
            from subtransjav.refine.fs_utils import _atomic_write_text
            from subtransjav.refine.v2_outputs import final_stem
        except Exception as e:  # noqa: BLE001
            return {"success": False, "error": str(e)}
        try:
            guide, guide_dir, stem = _load_guide(guide_path)
        except Exception as e:  # noqa: BLE001  导读缺失/格式不符如实回传
            return {"success": False, "error": str(e)}
        restore, auto_insert = self._rollback_candidates(
            str(guide_dir), stem)
        ledger_path = os.path.join(guide_dir, stem + self._LEDGER_SUFFIX)
        if not restore:
            return {"success": True, "restored": 0, "unmatched": [],
                    "auto_insert_skipped": auto_insert,
                    "ledger_path": ledger_path}
        final_path = os.path.join(guide_dir, f"{final_stem(stem)}.srt")
        if not os.path.isfile(final_path):
            return {"success": False,
                    "error": msg("fullchain_rollback_missing_final",
                                 path=final_path)}
        try:
            with open(final_path, encoding="utf-8") as f:
                entries = parse_srt(f.read())
        except Exception as read_err:  # noqa: BLE001
            return {"success": False, "error": str(read_err)}
        timing_map: dict[str, int] = {}
        for i, blk in enumerate(entries):
            timing_map.setdefault(str(blk.get("timing") or ""), i)
        unmatched: list[str] = []
        records: list[dict[str, Any]] = []
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for timing, old_text in restore.items():
            pos = timing_map.get(timing)
            if pos is None:
                unmatched.append(timing)
                continue
            cur = entries[pos]["text"]
            entries[pos]["text"] = old_text
            records.append({"index": entries[pos].get("index"),
                            "timing": timing, "category": "rollback",
                            "old_text": cur, "new_text": old_text,
                            "model_used": "", "outcome": "rollback",
                            "reason": "manual rollback", "ts": ts,
                            "source_partial": False})
        if not records:
            return {"success": True, "restored": 0, "unmatched": unmatched,
                    "auto_insert_skipped": auto_insert,
                    "ledger_path": ledger_path}
        # 写序契约：台账先于终稿落盘（回滚记录的 old_text 是再次回滚的
        # 依据；终稿写失败时台账已记录回滚动作不丢失）
        _append_ledger(Path(ledger_path), records)
        _atomic_write_text(final_path, build_srt(entries))
        _log.info("[fullchain] 一键回滚: %s 恢复 %d 条（未命中 %d，"
                  "插入行跳过 %d）", stem, len(records), len(unmatched),
                  auto_insert)
        return {"success": True, "restored": len(records),
                "unmatched": unmatched,
                "auto_insert_skipped": auto_insert,
                "ledger_path": ledger_path}

    def _run_encode_automation(self, summary: dict[str, Any],
                               from_fullchain: bool = False) -> None:
        """自动压制主体（触发上下文=前端轮询 get_translation_status 的
        GUI 桥线程：轻量文件操作+入队，可接受）。

        批1 b 段（D2026-1009-02）互斥对③：from_fullchain 形参透传
        encode_commit——链尾自动压制传 True 绕过全链在飞拒绝（手动入口
        缺省 False，全链在飞时结构化拒绝）。"""
        files_status = dict(summary.get("files") or {})
        done_srts = [str(p) for p, st in files_status.items() if st == "done"]
        if not done_srts:
            _log.info("[encode] 自动压制：本会话无完成文件，跳过")
            return
        last = self.encode_get_last_params().get("params") or {}
        params = dict(last)
        params["auto"] = True   # 自动化入队标记（skip-existing 语义）
        out_dir = str(params.get("out_dir") or "")
        ready: list[dict[str, str]] = []
        skipped: list[str] = []
        for job in self._normalize_encode_jobs(
                [{"srt_path": p} for p in done_srts]):
            video = job["video_path"]
            subtitle = job["subtitle_path"]
            label = os.path.basename(job["srt_path"] or subtitle or video)
            if not video or not os.path.isfile(video):
                skipped.append(f"{label}（未找到视频）")
                continue
            if not subtitle or not os.path.isfile(subtitle):
                skipped.append(f"{label}（终稿字幕不存在）")
                continue
            out_path = self._encode_out_path(video, out_dir)
            if os.path.isfile(out_path):
                skipped.append(f"{os.path.basename(out_path)}（成品已存在）")
                continue
            ready.append({"video_path": video, "subtitle_path": subtitle})
        notice = f"[encode] 自动压制：完成 {len(done_srts)} 个文件，入队 {len(ready)}"
        if skipped:
            notice += (f"，跳过 {len(skipped)}"
                       f"（{'；'.join(skipped[:3])}{'…' if len(skipped) > 3 else ''}）")
        if not ready:
            self._automation_notice(notice)
            return
        # 槽占用由 encode_commit 内部 claim（预占会与自己撞锁）；失败即人话回报
        commit = self.encode_commit(ready, params, allow_overwrite=False,
                                    from_fullchain=from_fullchain)
        if commit and commit.get("needs_confirm"):
            # 入队瞬间出现新成品：自动化语义=跳过不覆盖
            self._automation_notice("[encode] 自动压制：入队前出现新成品，按跳过处理（不覆盖）")
            return
        if not (commit and commit.get("success")):
            _log.info("[encode] 自动压制入队失败：%s", (commit or {}).get("error"))
            return
        self._automation_notice(notice)
        self._lms_unload_all_quiet()

    def _automation_notice(self, text: str) -> None:
        """自动压制人话通知：gui.log 恒落 + 翻译日志队列尽力投（测试桩/未初始化
        上下文容错——object.__new__ 实例无队列属性时跳过）。"""
        _log.info(text)
        q = getattr(self, "_translate_log_queue", None)
        if q is not None:
            with contextlib.suppress(Exception):
                q.put(text + "\n")

    def _lms_unload_all_quiet(self) -> None:
        """压制前 LM Studio 清场（决策：复用 lmstudio 既有 unload --all 路径；
        失败告警不阻塞压制）。风险跟踪①：用户感知=开启自动化后压制开始会
        清空已载模型（手册批注口径）。"""
        try:
            from subtransjav.utils import lmstudio
            lms = lmstudio._find_lms()
            if not lms:
                _log.info("[encode] 未找到 lms CLI，跳过模型清场（不阻塞）")
                return
            res = lmstudio._run_lms(lms, ["unload", "--all"], 60.0)
            state = "超时" if getattr(res, "timed_out", False) else "完成"
            _log.info("[encode] LM Studio 清场%s（unload --all）", state)
        except Exception:
            _log_exc("_lms_unload_all_quiet")
