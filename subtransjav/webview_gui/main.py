"""
SubTransJAV PyWebView GUI Entry Point

Standalone desktop GUI for the two-stage SRT refinement pipeline
(stage A: cleanup + translation; stage B: review + polish).

Requires the [gui] extra: pip install subtransjav[gui]
"""

# ===========================================================================
# EARLY SETUP - Must be before any library imports
# ===========================================================================
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, cast

from subtransjav.utils.console import (
    print_missing_extra_error,
    setup_console,
)

setup_console()

import platform  # noqa: E402

from subtransjav import paths  # noqa: E402  frozen 判定单一来源
from subtransjav.utils.process_manager import spawn_refine_cli  # noqa: E402  spawn 单一收敛点
from subtransjav.webview_gui.strings import msg  # noqa: E402  文案表零依赖

# AUMID 永不变更、版本号禁止入值（版本入值=每次升级换身份，任务栏钉扎/
# 通知设置作废）——D2026-1004-04
AUMID = "Angelholl.SubTrans.GUI"


def _deps_ok():
    """检查 GUI 核心依赖是否可导入"""
    try:
        import webview  # noqa: F401
        if platform.system() == "Windows":
            import clr  # noqa: F401
        return True
    except (ImportError, RuntimeError, SystemError):
        return False


def _auto_setup():
    """首次运行自动创建 venv 并安装依赖，然后重启到 venv 环境"""
    # PyInstaller 打包版不应走自动安装流程
    if paths.is_frozen():
        return
    # 已在 venv 中且依赖完整 → 正常继续
    if sys.prefix != sys.base_prefix and _deps_ok():
        return

    project_root = Path(__file__).resolve().parent.parent.parent
    # Issue#5: 平台感知的 venv python 路径
    if os.name == "nt":
        venv_python = project_root / ".venv" / "Scripts" / "python.exe"
    else:
        venv_python = project_root / ".venv" / "bin" / "python"

    try:
        # 创建虚拟环境（如果不存在）
        if not venv_python.exists():
            print(msg("setup_creating_venv"))
            # spawn 收敛点（修订③）：venv 引导走 helper；frozen 下 helper
            # 返回 None（此处实际不可达——上方 frozen guard 已短路，双保险）
            spawn_refine_cli(
                ["-m", "venv", str(project_root / ".venv")],
                purpose="venv_bootstrap", check=True)

        # Issue#4: venv已存在且依赖完整 → 跳过安装直接重启
        if venv_python.exists():
            try:
                probe = "import webview; import clr" if platform.system() == "Windows" else "import webview"
                subprocess.run(
                    [str(venv_python), "-c", probe],
                    check=True, capture_output=True, timeout=10
                )
                # 依赖已完整，直接重启
                print(msg("setup_env_ready"))
                os.execv(str(venv_python), [str(venv_python), "-m", "subtransjav.webview_gui.main"])
            except subprocess.TimeoutExpired:
                # v1.3.2 task4：从泛 except 中单独捞出，行为不变仅补可读日志
                print("   ⚠️ venv 探测超时(10s)，将走依赖安装/引导分支")
            except Exception:
                pass  # 依赖不完整，继续安装

        # 安装依赖（使用 venv 中的 pip）
        print(msg("setup_installing"))
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-e", ".[gui]"],
            cwd=str(project_root),
            check=True
        )

        # 安装完成后重启到 venv 环境
        print(msg("setup_install_done"))
        try:
            os.execv(str(venv_python), [str(venv_python), "-m", "subtransjav.webview_gui.main"])
        except Exception:
            # Issue#3: fallback Popen 增加 cwd
            subprocess.Popen(
                [str(venv_python), "-m", "subtransjav.webview_gui.main"],
                cwd=str(project_root)
            )
            sys.exit(0)
    # Issue#2: 异常处理 — 友好中文错误 + 暂停
    except subprocess.CalledProcessError as e:
        print(f"\n{msg('setup_init_failed', e=e)}")
        print(msg("setup_manual_hint"))
        input(msg("setup_press_enter"))
        sys.exit(1)
    except Exception as e:
        print(f"\n{msg('setup_unknown_error', e=e)}")
        print(msg("setup_manual_hint"))
        input(msg("setup_press_enter"))
        sys.exit(1)


def _check_gui_dependencies():
    """Check if GUI dependencies are installed."""
    missing = []

    try:
        import webview  # noqa: F401
    except ImportError:
        missing.append("pywebview")

    if platform.system() == "Windows":
        try:
            import clr  # noqa: F401  # pythonnet 可用性探测
        except ImportError:
            missing.append("pythonnet")

    if missing:
        print_missing_extra_error(
            extra_name="gui",
            missing_packages=missing,
            feature_description="PyWebView GUI interface"
        )
        if platform.system() == "Windows":
            print("Note: On Windows, WebView2 runtime is also required.")
            print("Download from: https://developer.microsoft.com/en-us/microsoft-edge/webview2/")
        sys.exit(1)


# Issue#1: _auto_setup() 必须在 _check_gui_dependencies() 之前执行，
# 否则首次运行缺依赖时直接 sys.exit(1)，自动安装永远不可达。
# ===========================================================================
# 命令行参数（在 venv 自举与依赖检查之前解析，--help/--version 直接退出）
# ===========================================================================
import json  # noqa: E402


def _parse_args(argv=None):
    """解析 GUI 命令行参数（中文 help）。

    必须在 _auto_setup() / _check_gui_dependencies() 之前调用，
    保证 ``--help`` / ``--version`` 不触发 venv 自举与依赖检查。
    """
    import argparse
    parser = argparse.ArgumentParser(
        prog="subtransjav-gui",
        description=msg("cli_description"))
    parser.add_argument(
        "--debug", action="store_true",
        help=msg("cli_help_debug"))
    parser.add_argument(
        "--version", action="store_true",
        help=msg("cli_help_version"))
    return parser.parse_args(argv)


def _print_version() -> str:
    """返回版本展示字符串（无法加载版本信息时返回 unknown）。"""
    try:
        from subtransjav.__version__ import __version_display__
        return __version_display__
    except ImportError:
        return "unknown"


APP_TITLE = msg("app_title")

# 2.7.5 件A（D2026-1007-02）：媒体通道 origin 自检横幅文案（Python 常量，
# JS 注入时经 json.dumps 转义，中文直书不入 strings 表）
MEDIA_ORIGIN_BANNER_TEXT = (
    "媒体通道异常：页面未以 file:// 加载，视频/试听将不可用（详见 gui.log）"
)


def on_drop_event(e):
    """
    Handle file drops from OS into WebView.

    Uses PyWebView's pywebviewFullPath to get absolute file paths,
    bypassing browser security restrictions.
    """
    import webview
    files = e.get('dataTransfer', {}).get('files', [])
    if len(files) == 0:
        return

    paths = []
    # 2.6.1 批 2a（D2026-1002-09）：放宽至视频后缀供校对页消费；
    # 非 tab-review 激活时由 ReviewUI.onDroppedFiles 原样转发
    # FileListManager.addDroppedFiles（对非字幕本就静默跳过），翻译页行为零变化
    # 2.7.2 件1（D2026-1005-02）：字幕后缀放开至 .ass/.ssa/.vtt（与对话框口径一致）
    allowed_exts = ('.srt', '.ass', '.ssa', '.vtt',
                    '.mp4', '.mkv', '.webm', '.mov', '.avi')
    for file in files:
        full_path = file.get('pywebviewFullPath')
        if full_path and str(full_path).lower().endswith(allowed_exts):
            paths.append(full_path)

    if not paths:
        return

    # 登记拖放路径，纳入 scan_resume_states 的会话信任边界
    # （视频路径入登记=信任边界扩大，已在 D2026-1002-09 登记备案）
    from .api import register_session_paths
    register_session_paths(paths)

    try:
        window = webview.windows[0]
        paths_json = json.dumps(paths)
        window.evaluate_js(f"ReviewUI.onDroppedFiles({paths_json})")
    except Exception as ex:
        print(msg("drop_event_error", e=ex))


def bind_dom_events(window):
    """Bind drag-drop events to window DOM after creation."""
    from webview.dom import DOMEventHandler  # noqa: E402  延迟导入 GUI 依赖
    try:
        window.dom.document.events.dragenter += DOMEventHandler(lambda e: None, True, True)
        window.dom.document.events.dragover += DOMEventHandler(lambda e: None, True, True)
        window.dom.document.events.drop += DOMEventHandler(on_drop_event, True, True)
        print(msg("dom_events_bound"))
    except Exception as ex:
        print(msg("dom_events_bind_failed", e=ex))
        print(msg("dom_events_fallback"))


def get_asset_path(relative_path: str) -> Path:
    """Get absolute path to an asset file (dev mode or PyInstaller bundle)."""
    if paths.is_frozen() and hasattr(sys, '_MEIPASS'):
        base_path = Path(sys._MEIPASS)
        asset_path = base_path / "webview_gui_assets" / relative_path
    else:
        base_path = Path(__file__).parent
        asset_path = base_path / "assets" / relative_path

    if not asset_path.exists():
        raise FileNotFoundError(
            f"Asset file not found: {asset_path}\n"
            f"Relative path requested: {relative_path}"
        )
    return asset_path


def asset_page_url(path: str | Path) -> str:
    """资产页面加载 URL：Path.as_uri() 钉 file:// origin（2.7.5 件A）。

    pywebview 6.x 对 ``url=`` 纯路径串走内置 Bottle 伺服，页面 origin 变
    http://127.0.0.1:随机端口，WebView2 随即拒绝页面内 file:/// 媒体（校对页
    <video>、试听 <audio> 直连全挂）；传 as_uri() 则 origin=file://，媒体
    直连恢复（D2026-1002-09 §七 spike 结论，本函数即生产落码对齐闭环）。

    转换失败（实测 Python 3.12 pathlib：相对路径抛
    ValueError("relative path can't be expressed as a file URI")；UNC
    //srv/share/x.html 不抛，得 file://srv/share/x.html——评议员预设 UNC
    抛 ValueError 不成立，以实测为准）→ 回退 str(path)，并复用 api.py 既有
    gui.log 通道记 warning（延迟导入，零新增 open 写点）。
    """
    try:
        return Path(path).as_uri()
    except ValueError as e:
        try:
            from .api import _log  # 延迟导入：复用既有 gui.log 通道，避免 import 期建 Logs 目录
            _log.warning("asset_page_url 回退 str(path)：%r（%s）", path, e)
        except Exception:
            pass
        return str(path)


def bind_media_origin_check(window) -> None:
    """2.7.5 件A（D2026-1007-02）启动自检：loaded 后校验页面 origin。

    非 ``file:`` → ①经既有 gui.log 通道记 error；②往页面 body 前插一个
    固定定位红色横幅（文案=MEDIA_ORIGIN_BANNER_TEXT）。全程 try/except
    包裹：evaluate 失败不影响启动。
    """

    def _on_loaded():
        try:
            protocol = window.evaluate_js("location.protocol")
            if protocol == "file:":
                return
            try:
                from .api import _log  # 延迟导入：复用既有 gui.log 通道
                _log.error(
                    "媒体通道异常：页面 origin=%r 非 file://，视频/试听不可用",
                    protocol,
                )
            except Exception:
                pass
            banner = (
                "<div id='stj-media-origin-banner' style='position:fixed;top:0;"
                "left:0;right:0;z-index:2147483647;background:#c0392b;color:#fff;"
                "padding:8px 16px;font-size:14px;text-align:center;'>"
                + MEDIA_ORIGIN_BANNER_TEXT
                + "</div>"
            )
            window.evaluate_js(
                "document.body.insertAdjacentHTML('afterbegin', "
                + json.dumps(banner)
                + ");"
            )
        except Exception as e:
            # 全容错：自检/evaluate 失败不阻塞启动
            print(f"⚠️ [origin 自检] 检查失败（忽略，继续启动）: {e}")

    window.events.loaded += _on_loaded


def check_webview2_windows():
    """Check if WebView2 runtime is installed on Windows."""
    if platform.system() != 'Windows':
        return True

    try:
        import winreg
        key_paths = [
            r"SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}",
            r"SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
        ]
        for key_path in key_paths:
            try:
                winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path).Close()
                return True
            except FileNotFoundError:
                continue
        return False
    except Exception as e:
        print(msg("webview2_check_failed", e=e))
        return True


def show_webview2_error():
    """Show user-friendly error dialog if WebView2 is missing."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "WebView2 Required",
            "WebView2 Runtime is required but not installed.\n\n"
            "Please download and install it from:\n"
            "https://go.microsoft.com/fwlink/p/?LinkId=2124703\n\n"
            "After installation, restart the application."
        )
        root.destroy()
    except Exception:
        print("\nERROR: WebView2 Runtime Required.")
        print("Download: https://go.microsoft.com/fwlink/p/?LinkId=2124703")


def create_window():
    """Create and configure the PyWebView window."""
    import webview

    from .api import TranslateAPI

    html_path = get_asset_path("index.html")
    api = TranslateAPI()

    icon_path = None
    if os.getenv('SUBTRANSJAV_NO_ICON', '').lower() not in ('1', 'true', 'yes'):
        icon_file = Path(__file__).parent / "assets" / "icon.ico"
        if icon_file.exists():
            icon_path = icon_file

    width_s, height_s = int(1920 * 0.63), int(1080 * 0.85)

    window_kwargs = {
        'title': APP_TITLE,
        # 2.7.5 件A（D2026-1007-02）：as_uri 钉 file:// origin，媒体直连恢复
        'url': asset_page_url(html_path),
        'js_api': api,
        'width': width_s,
        'height': height_s,
        'resizable': True,
        'frameless': False,
        'easy_drag': True,
        'text_select': True,
        'min_size': (820, 600)
    }

    if icon_path:
        try:
            import inspect
            if 'icon' in inspect.signature(webview.create_window).parameters:
                window_kwargs['icon'] = str(icon_path)
        except Exception:
            pass

    window = webview.create_window(**cast(dict[str, Any], window_kwargs))
    # 2.7.5 件A：loaded 后 origin 自检（非 file: → gui.log error + 红色横幅）
    bind_media_origin_check(window)
    return window


def main():
    """Entry point for subtransjav-gui."""
    # PyInstaller frozen 多进程（multiprocessing）安全：必须在任何
    # multiprocessing 子进程被拉起之前调用；非 frozen 下为 no-op。
    import multiprocessing

    multiprocessing.freeze_support()

    # --subtrans-cli 分派（D2026-0929-06 修订③）：frozen 下 exe 直接充当
    # refine CLI 解释器（spawn_refine_cli 拼的 [exe, --subtrans-cli, ...]）。
    # 必须先于 pywebview 初始化与 _parse_args（GUI 参数解析不认 CLI 旗标）。
    # 源码形态同样生效；packaging/entry_gui.py 经 main() 进入，天然覆盖。
    if "--subtrans-cli" in sys.argv:
        sys.argv.remove("--subtrans-cli")
        from subtransjav.refine.cli import main as refine_main

        sys.exit(refine_main())

    # --help / --version 在此直接退出，不触发 venv 自举与依赖检查
    args = _parse_args()
    if args.version:
        print(_print_version())
        return

    # ---- EXE 首发数据迁移插桩（D2026-0929-05/07/08）：freeze_support 之后、
    #      _auto_setup 之前；--help/--version 只读早退在其前不受影响；
    #      全容错，任何异常不阻塞 GUI 启动 ----
    try:
        from subtransjav.data_migration import ensure_migrated
        ensure_migrated(verbose=True)
    except Exception as e:  # noqa: BLE001 - 全容错桩：迁移失败不阻塞启动
        print(f"⚠️ [迁移] 数据迁移检查失败（忽略，继续启动）: {e}")

    # ---- 内置角色卡首启 seed（批1a D2026-1002-12 件4）：frozen-only
    #      （源码形态 no-op 防脏工作树）；仅补拷缺失文件不覆盖已改卡；
    #      全容错，失败不阻塞启动 ----
    try:
        from subtransjav.refine.template_seed import seed_default_templates
        seeded = seed_default_templates()
        if seeded.get("seeded"):
            print(f"✅ [seed] 内置角色卡已初始化: {seeded.get('copied')}")
    except Exception as e:  # noqa: BLE001 - 全容错桩：seed 失败不阻塞启动
        print(f"⚠️ [seed] 内置角色卡初始化失败（忽略，继续启动）: {e}")

    _auto_setup()
    _check_gui_dependencies()

    # 延迟导入：--help/--version 路径不要求 GUI 依赖已安装
    import logging

    import webview  # noqa: E402

    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    logging.getLogger('bottle').setLevel(logging.ERROR)

    version = _print_version()
    print(msg("gui_banner", version=version))
    print("=" * 50)

    if not check_webview2_windows():
        show_webview2_error()
        sys.exit(1)

    # Set Windows AppUserModelID so the taskbar groups this app separately
    if platform.system() == 'Windows':
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                AUMID)
        except Exception as e:
            print(msg("appusermodelid_failed", e=e))

    try:
        window = create_window()
        print(msg("window_created"))

        # --debug 透传 webview.start；环境变量 SUBTRANSJAV_DEBUG 仍然有效
        debug_mode = args.debug or os.getenv(
            'SUBTRANSJAV_DEBUG', '').lower() in ('1', 'true', 'yes')
        print(msg("starting_webview", debug=debug_mode))

        # private_mode=True avoids WebView2 disk-cache staleness;
        # all user settings persist via backend files, not localStorage.
        webview.start(debug=debug_mode, private_mode=True,
                      func=lambda: bind_dom_events(window))

    except FileNotFoundError as e:
        print(f"\n{msg('asset_not_found')}")
        print(str(e))
        sys.exit(1)
    except Exception as e:
        print(f"\n{msg('gui_start_failed')}")
        print(f"{type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
