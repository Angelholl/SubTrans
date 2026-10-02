"""
Process management utilities for SubTransJAV.

Provides cross-platform process tree termination to ensure
child processes (including GPU workers) are properly cleaned up
when the user cancels an operation.

v1.7.4+: Fixes orphaned GPU worker processes on cancellation.
v1.3.2 task4: 项目级进程治理两原语——run_with_timeout_tree（带超时子进程
统一入口，超时整树击杀且不抛 TimeoutExpired）与 terminate_process_tree_robust
（用户取消/退出场景的跨环境树杀）。
"""

import logging
import os
import signal
import subprocess
import sys
from pathlib import Path
from typing import Any

from subtransjav import paths
from subtransjav.utils.subprocess_flags import CREATE_NO_WINDOW as _CREATE_NO_WINDOW  # 窗口标志单一来源

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None
    PSUTIL_AVAILABLE = False

logger = logging.getLogger("subtransjav")


def _pid_alive(pid: int) -> bool:
    """Check if a PID is alive without killing it on Windows.

    On Windows, os.kill(pid, 0) can actually terminate the target process.
    This uses ctypes OpenProcess + GetExitCodeProcess instead.
    On POSIX, falls back to os.kill(pid, 0) with OSError catching.
    """
    if os.name == "nt":
        import ctypes
        import ctypes.wintypes

        kernel32 = ctypes.windll.kernel32
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259

        h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if h == 0:
            return False
        try:
            exit_code = ctypes.wintypes.DWORD()
            if kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code)):
                return exit_code.value == STILL_ACTIVE
            return False
        finally:
            kernel32.CloseHandle(h)
    else:
        # POSIX: os.kill(pid, 0) only sends signal 0, does not kill
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False


def get_process_tree(pid: int) -> list[int]:
    """
    Get all descendant PIDs of a process (children, grandchildren, etc.).

    Args:
        pid: Parent process ID

    Returns:
        List of descendant PIDs (does NOT include the parent itself)
    """
    if not PSUTIL_AVAILABLE:
        logger.warning("psutil not available, cannot enumerate process tree")
        return []

    try:
        parent = psutil.Process(pid)
        children = parent.children(recursive=True)
        return [child.pid for child in children]
    except psutil.NoSuchProcess:
        return []
    except Exception as e:
        logger.warning(f"Failed to enumerate process tree for PID {pid}: {e}")
        return []


def terminate_process_tree(
    pid: int,
    timeout: float = 5.0,
    include_parent: bool = True
) -> dict[str, Any]:
    """
    Terminate a process and all its descendants gracefully.

    Uses a two-phase approach:
    1. SIGTERM to all processes (graceful shutdown request)
    2. Wait for timeout
    3. SIGKILL to any survivors (force kill)

    This ensures GPU workers spawned by multiprocessing are properly
    terminated when the user cancels an operation.

    Args:
        pid: Root process ID to terminate
        timeout: Seconds to wait for graceful shutdown before force-killing
        include_parent: Whether to also terminate the parent process

    Returns:
        dict with termination results:
            {
                "success": bool,
                "terminated": [list of PIDs that were terminated gracefully],
                "killed": [list of PIDs that required force-kill],
                "already_dead": [list of PIDs that were already dead],
                "errors": [list of error messages]
            }
    """
    result: dict[str, Any] = {
        "success": True,
        "terminated": [],
        "killed": [],
        "already_dead": [],
        "errors": []
    }

    if not PSUTIL_AVAILABLE:
        result["success"] = False
        result["errors"].append("psutil not available - falling back to basic termination")
        return result

    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        result["already_dead"].append(pid)
        return result
    except psutil.AccessDenied as e:
        result["success"] = False
        result["errors"].append(f"Access denied to process {pid}: {e}")
        return result
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"Cannot access process {pid}: {e}")
        return result

    # Collect all processes to terminate (children first, then parent)
    # Killing children first prevents orphan creation
    processes_to_kill: list[Any] = []

    try:
        children = parent.children(recursive=True)
        # Reverse order: deepest children first
        processes_to_kill.extend(reversed(children))
    except psutil.NoSuchProcess:
        pass  # Parent already dead
    except Exception as e:
        result["errors"].append(f"Failed to get children: {e}")

    if include_parent:
        processes_to_kill.append(parent)

    if not processes_to_kill:
        return result

    pids_to_kill = [p.pid for p in processes_to_kill]
    logger.debug(f"Terminating process tree: {pids_to_kill}")

    # Phase 1: Send SIGTERM to all (graceful termination)
    alive_processes = []
    for proc in processes_to_kill:
        try:
            proc.terminate()
            alive_processes.append(proc)
            result["terminated"].append(proc.pid)
        except psutil.NoSuchProcess:
            result["already_dead"].append(proc.pid)
        except psutil.AccessDenied:
            result["errors"].append(f"Access denied terminating PID {proc.pid}")
        except Exception as e:
            result["errors"].append(f"Failed to terminate PID {proc.pid}: {e}")

    if not alive_processes:
        return result

    # Phase 2: Wait for graceful shutdown
    gone, still_alive = psutil.wait_procs(alive_processes, timeout=timeout)

    # Update terminated list to only include those that actually died gracefully（历史变量已移除）

    # Phase 3: Force-kill survivors
    for proc in still_alive:
        try:
            logger.warning(f"Force-killing PID {proc.pid} (did not terminate gracefully)")
            proc.kill()
            result["killed"].append(proc.pid)
            # Remove from terminated since it required force-kill
            if proc.pid in result["terminated"]:
                result["terminated"].remove(proc.pid)
        except psutil.NoSuchProcess:
            result["already_dead"].append(proc.pid)
        except psutil.AccessDenied:
            result["errors"].append(f"Access denied killing PID {proc.pid}")
            result["success"] = False
        except Exception as e:
            result["errors"].append(f"Failed to kill PID {proc.pid}: {e}")
            result["success"] = False

    # Wait briefly for kills to complete
    if still_alive:
        psutil.wait_procs(still_alive, timeout=2.0)

    logger.debug(
        f"Process tree termination complete: "
        f"{len(result['terminated'])} terminated gracefully, "
        f"{len(result['killed'])} force-killed, "
        f"{len(result['already_dead'])} already dead"
    )

    return result


def kill_process_tree(pid: int, include_parent: bool = True) -> dict[str, Any]:
    """
    Immediately force-kill a process and all its descendants.

    No graceful shutdown - sends SIGKILL directly.
    Use this when immediate termination is required.

    Args:
        pid: Root process ID to kill
        include_parent: Whether to also kill the parent process

    Returns:
        dict with kill results (same format as terminate_process_tree)
    """
    result: dict[str, Any] = {
        "success": True,
        "terminated": [],
        "killed": [],
        "already_dead": [],
        "errors": []
    }

    if not PSUTIL_AVAILABLE:
        result["success"] = False
        result["errors"].append("psutil not available")
        return result

    try:
        parent = psutil.Process(pid)
    except psutil.NoSuchProcess:
        result["already_dead"].append(pid)
        return result
    except Exception as e:
        result["success"] = False
        result["errors"].append(f"Cannot access process {pid}: {e}")
        return result

    # Collect all processes (children first, then parent)
    processes_to_kill: list[Any] = []

    try:
        children = parent.children(recursive=True)
        # Reverse order: deepest children first
        processes_to_kill.extend(reversed(children))
    except psutil.NoSuchProcess:
        pass
    except Exception as e:
        result["errors"].append(f"Failed to get children: {e}")

    if include_parent:
        processes_to_kill.append(parent)

    logger.debug(f"Force-killing process tree: {[p.pid for p in processes_to_kill]}")

    # Kill all immediately
    for proc in processes_to_kill:
        try:
            proc.kill()
            result["killed"].append(proc.pid)
        except psutil.NoSuchProcess:
            result["already_dead"].append(proc.pid)
        except psutil.AccessDenied:
            result["errors"].append(f"Access denied killing PID {proc.pid}")
            result["success"] = False
        except Exception as e:
            result["errors"].append(f"Failed to kill PID {proc.pid}: {e}")
            result["success"] = False

    # Wait briefly for kills to complete
    if processes_to_kill:
        psutil.wait_procs(processes_to_kill, timeout=2.0)

    return result


# ---------------------------------------------------------------------------
# v1.3.2 task4：项目级进程治理两原语
# ---------------------------------------------------------------------------

_TASKKILL_TIMEOUT_S = 10.0  # taskkill 自身限时，防止其挂死拖垮调用方


class _TreeRunResult(subprocess.CompletedProcess):
    """run_with_timeout_tree 的返回类型：CompletedProcess 附加 timed_out 标记。"""

    def __init__(self, args, returncode, stdout, stderr, timed_out: bool):
        super().__init__(args, returncode, stdout, stderr)
        self.timed_out = timed_out


def _taskkill_tree(pid: int) -> tuple[bool, str]:
    """Windows 无 psutil 回退：taskkill /T /F 整树强杀。

    返回 (是否成功, 失败原因)。taskkill 自身限时 _TASKKILL_TIMEOUT_S。
    """
    try:
        cp = subprocess.run(
            ["taskkill", "/PID", str(pid), "/T", "/F"],
            capture_output=True, timeout=_TASKKILL_TIMEOUT_S, check=False,
            creationflags=_CREATE_NO_WINDOW,  # 批0：GUI 取消路径防黑框（POSIX=0 无操作）
        )
    except Exception as e:  # 含 TimeoutExpired / FileNotFoundError
        return False, f"taskkill 执行失败: {e}"
    if cp.returncode == 0:
        return True, ""
    return False, f"taskkill 退出码 {cp.returncode}"


def _single_kill(proc: subprocess.Popen) -> None:
    """终态兜底：直接子进程单杀（目标已死则无害）。"""
    try:
        proc.kill()
    except Exception as e:
        logger.warning(f"兜底单杀失败（pid={proc.pid}）: {e}")


def run_with_timeout_tree(
    cmd: list[str],
    timeout: float,
    *,
    capture_output: bool = True,
    text: bool = True,
    encoding: str | None = None,
    errors: str | None = None,
    env: dict[str, str] | None = None,
    cwd: str | None = None,
) -> subprocess.CompletedProcess:
    """带超时的子进程调用统一入口：超时即整树击杀，永不抛 TimeoutExpired。

    签名对齐 subprocess.run 风格（cmd 列表 + 必填 timeout + 常用透传参数），
    内部用 Popen + communicate(timeout) 自管。超时清理顺序：
      ① psutil 可用 → terminate_process_tree 树杀（含孙进程）；
      ② 无 psutil 且 Windows → taskkill /PID <pid> /T /F；
      ③ POSIX → 子进程以 start_new_session=True 创建，超时 os.killpg 整组杀。
    任何树杀路径之后无条件执行 proc.kill() 单杀兜底（重复杀已死进程无害），
    保证调用方在任何分支下都不会无限阻塞。

    返回 _TreeRunResult（CompletedProcess 子类）：正常完成 timed_out=False；
    超时 timed_out=True，returncode 为击杀后的实际退出码（极端场景可为 None）。
    """
    popen_kwargs: dict[str, Any] = {}
    if os.name != "nt":
        # POSIX：让子进程自成进程组，超时时可 killpg 整树击杀
        popen_kwargs["start_new_session"] = True
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE if capture_output else None,
        stderr=subprocess.PIPE if capture_output else None,
        text=text,
        encoding=encoding,
        errors=errors,
        env=env,
        cwd=cwd,
        creationflags=_CREATE_NO_WINDOW,  # 批0：防黑框（POSIX=0 无操作）
        **popen_kwargs,
    )
    timed_out = False
    try:
        stdout, stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        logger.warning(f"命令超时（>{timeout:g}s），整树击杀: {list(cmd)[:3]}")
        if PSUTIL_AVAILABLE:
            result = terminate_process_tree(proc.pid)
            if not result["success"]:
                logger.warning(
                    f"psutil 树杀未完全成功（pid={proc.pid}）: {result['errors']}")
        elif os.name == "nt":
            ok, detail = _taskkill_tree(proc.pid)
            if not ok:
                logger.warning(f"taskkill 树杀未完全成功（pid={proc.pid}）: {detail}")
        else:
            try:
                os.killpg(proc.pid, signal.SIGKILL)  # type: ignore[attr-defined]  # start_new_session → 自成进程组
            except Exception as e:
                logger.warning(f"killpg 树杀失败（pid={proc.pid}）: {e}")
        _single_kill(proc)  # 终态兜底：任何路径都不允许调用方无限阻塞
        try:
            stdout, stderr = proc.communicate(timeout=5)
        except Exception:
            # 残留孙进程仍握着管道等极端场景：放弃回收输出，绝不阻塞
            blank = "" if (text or encoding) else b""
            stdout, stderr = blank, blank
    return _TreeRunResult(cmd, proc.returncode, stdout, stderr, timed_out)


def terminate_process_tree_robust(pid: int) -> bool:
    """用户显式取消/退出场景的进程树终止（无超时语义），返回是否全清。

    优先级：psutil 可用 → 现有 terminate_process_tree 两阶段树杀原样走；
    无 psutil 且 Windows → taskkill /PID <pid> /T /F 整树强杀（升级自单杀）；
    POSIX → 仅当目标自成进程组（getpgid(pid)==pid）才 killpg 整组杀，
    否则降级单杀并告警（防止误杀同组内 GUI 自身等无辜进程）。
    """
    if PSUTIL_AVAILABLE:
        return bool(terminate_process_tree(pid)["success"])

    if os.name == "nt":
        ok, detail = _taskkill_tree(pid)
        if not ok:
            logger.warning(f"taskkill 树杀未完全成功（pid={pid}）: {detail}")
        return ok

    # POSIX：确认目标自成进程组才可整组杀（pgid==pid），否则误伤同组进程
    try:
        pgid = os.getpgid(pid)  # type: ignore[attr-defined]
    except OSError:
        pgid = None
    if pgid == pid:
        try:
            os.killpg(pgid, signal.SIGKILL)  # type: ignore[attr-defined]
            return True
        except ProcessLookupError:
            return True  # 组内进程均已消亡，视为全清
        except OSError as e:
            logger.warning(f"killpg 树杀失败（pid={pid}）: {e}")
            return False
    logger.warning(f"进程 {pid} 不自成进程组，降级为单杀")
    try:
        os.kill(pid, signal.SIGKILL)  # type: ignore[attr-defined]
        return True
    except ProcessLookupError:
        return True  # 已死即全清
    except OSError as e:
        logger.warning(f"单杀降级失败（pid={pid}）: {e}")
        return False


# ---------------------------------------------------------------------------
# spawn 单一收敛点（D2026-0929-06 修订③ + 07 点 1 + 08 点 1）
# ---------------------------------------------------------------------------

# _CREATE_NO_WINDOW 已收敛到 subtransjav.utils.subprocess_flags（批0 防黑框
# 单一来源）：Windows=0x08000000 / POSIX=0，本文件顶部导入别名，行为不变。


def _utf8_child_env(env_extra: dict[str, str] | None) -> dict[str, str]:
    """UTF-8 保证落点：子进程环境统一在此强制 UTF-8（#190）。

    - ``PYTHONUTF8=1``：子进程 open()/locale 缺省即 UTF-8；
    - ``PYTHONIOENCODING=utf-8:replace``：窄码页管道下输出不崩、不可编码降级替换。
    在 os.environ.copy() 基础上合并 env_extra——显式变量（API 密钥、
    SUBTRANSJAV_DATA_ROOT 等）自然继承，无需特判。
    """
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    env["PYTHONIOENCODING"] = "utf-8:replace"
    if env_extra:
        env.update(env_extra)
    return env


def spawn_refine_cli(
    args: list[str],
    *,
    purpose: str = "subprocess",
    capture: bool = False,
    cwd: str = "",
    env_extra: dict[str, str] | None = None,
    **kwargs: Any,
) -> subprocess.Popen | subprocess.CompletedProcess | None:
    """refine CLI 子进程统一 spawn 入口（全项目三 spawn 点收敛到此）。

    收敛口径（改动前落点 → 现一律调本函数）：
      1. webview_gui/api.py start_translation（主翻译子进程，Popen 流式）；
      2. webview_gui/api.py refine_ai_analyze（AI 分析子进程，run 同步捕获）；
      3. webview_gui/main.py _auto_setup（venv 引导，purpose="venv_bootstrap"）。

    purpose 两位（D2026-0929-08）：
      - "subprocess"：拉起 refine CLI 子进程。命令形态：
        frozen（paths.is_frozen()）→ 优先安装目录内独立 CLI 可执行体
        ``Path(sys.executable).parent / "subtrans-cli.exe"``（2.0.0 双 EXE
        改造：GUI 主程序为 windowed，输出不可见，命令行走专用 console 版）；
        该文件不存在（旧单 exe 构建兼容回退）→
        ``[sys.executable, "--subtrans-cli"] + args``；
        源码 → ``[sys.executable, "-u", "-m", "subtransjav.refine.cli"] + args``。
      - "venv_bootstrap"：venv 引导（``-m venv`` 等）。frozen 下整段 no-op
        直接返回 None（调用方据 None 跳过）；源码形态 ``[sys.executable] + args``，
        维持控制台语义（creationflags 直传 0，不带 CREATE_NO_WINDOW）。

    其余口径：
      - env：``_utf8_child_env`` 强制 UTF-8 两变量后合并 env_extra；
      - "subprocess" 段直传 creationflags（批0）：Windows=CREATE_NO_WINDOW
        （不弹黑窗），POSIX 常量解析为 0（等价缺省）；
      - capture=True → subprocess.run 返回 CompletedProcess；否则 Popen；
      - cwd 缺省 app_root()（源码=仓库根，frozen=数据根）；
      - 杀树复用现有 terminate_process_tree / taskkill /T /F 原语，本函数不重复造轮子。

    kwargs 原样透传给 Popen / run（stdout/stderr/bufsize/timeout/...）。
    """
    if purpose == "venv_bootstrap":
        if paths.is_frozen():
            # 打包版不走 venv 自举（main._auto_setup 的 frozen guard 之外的第二道保险）
            return None
        return subprocess.run(
            [sys.executable, *args],
            env=_utf8_child_env(env_extra),
            cwd=cwd or None,
            creationflags=0,  # venv 引导维持控制台语义（源码模式专属）；0 ≡ Windows 缺省，行为不变
            **kwargs,
        )
    if purpose != "subprocess":
        raise ValueError(f"未知 purpose: {purpose!r}（应为 subprocess | venv_bootstrap）")

    if paths.is_frozen():
        # 2.0.0 双 EXE：优先同目录独立 CLI 可执行体（完整控制台语义）；
        # 旧单 exe 构建（console 版，无 subtrans-cli.exe）回退 --subtrans-cli 分派。
        cli_exe = Path(sys.executable).parent / "subtrans-cli.exe"
        cmd = ([str(cli_exe), *args] if cli_exe.exists()
               else [sys.executable, "--subtrans-cli", *args])
    else:
        cmd = [sys.executable, "-u", "-m", "subtransjav.refine.cli", *args]

    # 批0：窗口标志改直传（Windows=CREATE_NO_WINDOW 防黑框；POSIX 常量=0，
    # 为 subprocess 唯一合法值、等价缺省，行为不变）。调用方如显式传
    # creationflags 将与直传参数冲突报 TypeError——现行调用面（api.py ×3、
    # main.py venv 引导）均不传该参数。
    if capture:
        return subprocess.run(
            cmd, capture_output=True, cwd=cwd or str(paths.app_root()),
            env=_utf8_child_env(env_extra),
            creationflags=_CREATE_NO_WINDOW, **kwargs)
    return subprocess.Popen(
        cmd, cwd=cwd or str(paths.app_root()),
        env=_utf8_child_env(env_extra),
        creationflags=_CREATE_NO_WINDOW, **kwargs)


def is_process_alive(pid: int) -> bool:
    """
    Check if a process is still running.

    Args:
        pid: Process ID to check

    Returns:
        True if process is running, False otherwise
    """
    if not PSUTIL_AVAILABLE:
        return _pid_alive(pid)

    try:
        proc = psutil.Process(pid)
        return proc.is_running() and proc.status() != psutil.STATUS_ZOMBIE
    except psutil.NoSuchProcess:
        return False
    except Exception:
        return False


def get_process_info(pid: int) -> dict[str, Any]:
    """
    Get information about a process and its children.

    Useful for debugging process management issues.

    Args:
        pid: Process ID to inspect

    Returns:
        dict with process information
    """
    if not PSUTIL_AVAILABLE:
        return {"error": "psutil not available"}

    try:
        proc = psutil.Process(pid)
        children = proc.children(recursive=True)

        return {
            "pid": pid,
            "name": proc.name(),
            "status": proc.status(),
            "cmdline": proc.cmdline()[:3] if proc.cmdline() else [],  # First 3 args only
            "children_count": len(children),
            "children": [
                {
                    "pid": child.pid,
                    "name": child.name(),
                    "status": child.status()
                }
                for child in children
            ]
        }
    except psutil.NoSuchProcess:
        return {"error": f"Process {pid} not found"}
    except Exception as e:
        return {"error": str(e)}
