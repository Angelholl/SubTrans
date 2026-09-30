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
import shutil
import subprocess
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import Any, cast

import webview
from webview import FileDialog

from subtransjav import paths
from subtransjav.utils.process_manager import (
    PSUTIL_AVAILABLE,
    spawn_refine_cli,
    terminate_process_tree,
    terminate_process_tree_robust,
)

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


def _ensure_template_dir(templates_dir) -> str:
    """角色卡目录守卫（反路径穿越加固）。

    角色卡是仓库固定资源语义，仅放行两类目录：
      1. 服务端默认模板目录（config/templates）——不传目录时的正常主路径；
      2. 本会话经受信入口（原生文件夹对话框/拖放）登记的用户自选目录，
         且必须通过 _resolve_safe_path 锚点校验（home/仓库根白名单）。
    其余前端任意路径一律拒绝，阻断被攻陷前端借角色卡读写接口
    越锚访问用户主目录下的同名文件。
    """
    try:
        from subtransjav.refine.config import default_templates_dir
        default_dir = str(_resolve_safe_path(default_templates_dir()))
    except Exception:
        default_dir = ""
    if not templates_dir:
        return default_dir
    resolved = str(_resolve_safe_path(templates_dir))
    if default_dir and os.path.normcase(resolved) == os.path.normcase(default_dir):
        return resolved
    allowed = {os.path.normcase(p) for p in SESSION_SELECTED_PATHS}
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
    """Default output dir: <Documents>/SubTransJAV/output."""
    base = _get_documents_dir()
    if base.name.lower() != "documents" or not base.exists():
        base = Path.home()
    p = base / "SubTransJAV" / "output"
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
        args.append("--glossary-learn")
    if options.get("glossary_conflict_block"):
        args.append("--glossary-conflict-block")

    # NDJSON 结构化事件流（GUI 侧解析进度/风险/心跳；同仓 CLI 固定支持）
    args.extend(["--event-format", "ndjson"])

    return args


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

    def select_srt_files(self) -> dict[str, Any]:
        """Open file dialog to select SRT files for translation."""
        windows = webview.windows
        if not windows:
            return {"success": False, "message": msg("no_active_window")}

        file_types = [
            'Subtitle Files (*.srt)',
            'All Files (*.*)'
        ]

        result = windows[0].create_file_dialog(
            FileDialog.OPEN,
            allow_multiple=True,
            file_types=file_types
        )

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
            srt_files = sorted(str(f) for f in folder.glob("*.srt"))
            if srt_files:
                register_session_paths(srt_files)
                return {"success": True, "paths": srt_files, "folder": result[0]}
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
            from subtransjav.refine.batch import find_srt_files, scan_summary
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
                subprocess.run(["open", str(folder)])
            else:
                subprocess.run(["xdg-open", str(folder)])

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
            self._translate_files_completed = 0
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
        self._translate_files_completed = 0
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

        - 事件行格式化成 "[事件] 阶段B 批次 3/10" 风格（心跳不落日志防刷屏）；
        - 非事件行原样入日志队列，并由解析器的遗留兼容层提取进度/错误。
        """
        parser = self._translate_parser or EventStreamParser()
        try:
            for line in proc.stdout:
                try:
                    event = parser.feed(line)
                except Exception:
                    _log_exc("_pump_stdout.feed")
                    event = None
                text = format_event_line(event) if event else None
                self._translate_log_queue.put(text if text is not None else line)
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

        return {
            "status": self._translate_status,
            "progress": int(snap.get('progress') or 0),
            "current_file": snap.get('current_file'),
            "files_completed": getattr(self, '_translate_files_completed', 0),
            "files_total": int(snap.get('total') or 0),
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
            "degraded": risk_count > 0 or majority,
            "warning_level": warning_level,
            "ndjson_mode": bool(snap.get('ndjson_mode')),
            "files_status": snap.get('files', {}),
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
        """返回词库/角色卡目录的默认路径"""
        try:
            from subtransjav.refine.config import default_glossary_path, default_templates_dir
            return {
                "success": True,
                "templates_dir": default_templates_dir(),
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

    def refine_dict_download(self, kind: str) -> dict[str, Any]:
        """显式下载词典（2.1；当前仅 sudachi；SHA256 不符拒绝落位）。

        同步执行（下载几十 MB 级 wheel，GUI 侧按钮转下载中态，进度经
        refine_dict_download_progress 1s 轮询）；网络失败与校验失败
        分开报错（DictDownloadError / DictChecksumError）。
        """
        try:
            from subtransjav.refine.dict_manager import (
                DictChecksumError,
                DictDownloadError,
                download_dict,
            )
            if kind != "sudachi":
                return {"success": False,
                        "error": msg("dict_kind_unsupported")}
            path = download_dict(kind)
            return {"success": True, "path": path}
        except DictDownloadError as e:
            return {"success": False,
                    "error": f"{msg('dict_download_failed')}: {e}"}
        except DictChecksumError as e:
            return {"success": False,
                    "error": f"{msg('dict_checksum_failed')}: {e}"}
        except Exception as e:
            _log_exc("refine_dict_download")
            return {"success": False, "error": str(e)}

    def refine_dict_download_progress(self, kind: str) -> dict[str, Any]:
        """词典下载进度快照（第四批 owner 验收反馈；只读零副作用）。

        前端在 refine_dict_download 期间 1s 轮询：phase ∈
        download/verify/extract/done/failed，downloaded/total 为字节
        数（total 取 Content-Length，可能为 None）。
        """
        try:
            from subtransjav.refine.dict_manager import download_progress
            return {"success": True, **download_progress(kind)}
        except Exception as e:
            _log_exc("refine_dict_download_progress")
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

    def refine_pick_folder(self) -> dict[str, Any]:
        return self.select_folder()

    def refine_pick_csv_open(self) -> dict[str, Any]:
        """打开词库 CSV/TXT 文件选择对话框"""
        try:
            windows = webview.windows
            if not windows:
                return {"success": False, "error": msg("no_active_window")}
            result = windows[0].create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=(msg("file_type_glossary"), msg("file_type_all")))
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
            result = windows[0].create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=(msg("file_type_guide"), msg("file_type_all")))
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
            result = windows[0].create_file_dialog(
                webview.SAVE_DIALOG,
                file_types=(msg("file_type_csv"),),
                save_filename="glossary_export.csv")
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

    def refine_ai_analyze(self, report_path: str,
                          model: str = None) -> dict[str, Any]:
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
        try:
            p = str(_resolve_safe_path(p))
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

        # 分析子进程跟随阶段A 服务商/端点（与 refine_get_stage_settings
        # 同源读取）：GUI 阶段A 配云端时，分析子进程若不传 --s1-provider
        # 会落到 CLI 缺省 lmstudio 本地端点，必然失败且与隐私横幅错位。
        # 端点按 CLI 既有旗标 --<provider>-endpoint 显式非空才传。
        # 密钥/差异项经 env_extra 注入；PYTHONUTF8/PYTHONIOENCODING 由
        # spawn_refine_cli 统一强制（#190）。
        env_extra: dict[str, str] = {"PYTHONUNBUFFERED": "1"}
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
            "provider_name": self._stage_a_provider_name(),
            "companion_path": companion,
            "stderr_tail": stderr_tail,
        }

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
            try:
                for e in entries:
                    if not isinstance(e, dict):
                        continue
                    src = str(e.get("source", "")).strip()
                    tgt = str(e.get("target", "")).strip()
                    if not src or not tgt:
                        continue
                    added = db.store(src, tgt)
                    warn = src in conflicted or (
                        src.isascii() and src.lower() in conflicted)
                    results.append({"source": src, "target": tgt,
                                    "status": "added" if added else "exists",
                                    "conflict_warn": warn})
            finally:
                db.close()
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
                timeout=self._AUDIO_PREVIEW_FFPROBE_TIMEOUT_S)
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
    def _sweep_stale_preview_clips(preview_dir: str) -> int:
        """preview 片段受 audio_detect 既有 stale 时限管辖（同阈值清扫）。

        播放后片段保留（供复播），仅清理超龄文件；目录不存在静默返回。"""
        try:
            from subtransjav.refine.audio_detect import STALE_MAX_AGE_HOURS
            cutoff = datetime.now().timestamp() - STALE_MAX_AGE_HOURS * 3600
            removed = 0
            for name in os.listdir(preview_dir):
                p = Path(preview_dir) / name
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
                timeout=TranslateAPI._AUDIO_PREVIEW_EXTRACT_TIMEOUT_S)
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

        返回 {ok, mode:"direct", media_path} 或
        {ok, mode:"clip", data_url, duration_s}，失败 {ok:false, error}。
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
        media = ""
        if str(media_override or "").strip():
            try:
                media = str(_resolve_safe_path(str(media_override).strip()))
            except ValueError as ve:
                return {"ok": False,
                        "error": f"媒体路径不在允许的目录下: {ve}"}
            if not os.path.isfile(media):
                return {"ok": False, "error": f"媒体文件不存在: {media}"}
        else:
            media = str((data or {}).get("media_path") or "")
        if not media:
            return {"ok": False,
                    "error": "导读未包含媒体路径，请在媒体来源中显式指定",
                    "error_key": "no_media"}

        # timing 越界钳制：start ≥ 0；end ≥ start；零长时段拒绝
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

        ext = os.path.splitext(media)[1].lower()
        codecs = self._ffprobe_stream_codecs(media)
        if codecs is not None:
            direct = (ext in self._AUDIO_PREVIEW_DIRECT_EXTS
                      and codecs["video"] in self._AUDIO_PREVIEW_DIRECT_VIDEO
                      and codecs["audio"] in self._AUDIO_PREVIEW_DIRECT_AUDIO)
            if direct:
                return {"ok": True, "mode": "direct", "media_path": media,
                        "codec_probe": True}
        else:
            # ffprobe 缺失/失败：mp4/m4a（aac 语义）尝试 direct；
            # 其余容器无法解码判定 → 无 ffmpeg 即报错
            if ext in (".mp4", ".m4a"):
                return {"ok": True, "mode": "direct", "media_path": media,
                        "codec_probe": False}
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
                "duration_s": round(duration, 3), "clip_path": out_path}

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
            result = windows[0].create_file_dialog(
                webview.OPEN_DIALOG, allow_multiple=False,
                file_types=(msg("file_type_sqlite"), msg("file_type_all")))
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
