"""process_manager 真实子进程测试（P3-10 测试补薄）。

全部用例以 ``sys.executable -c "import time; time.sleep(60)"`` 起真实子进程，
并在 finally 中自清理，确保不残留任何进程。
"""
import contextlib
import logging
import os
import subprocess
import sys
import time
import types

import pytest

import subtransjav.utils.process_manager as pm


def _sleep_proc(seconds: int = 60) -> subprocess.Popen:
    """起一个安静睡眠的子进程（模拟翻译子进程）。"""
    return subprocess.Popen(
        [sys.executable, "-c", f"import time; time.sleep({seconds})"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def _ensure_dead(proc: subprocess.Popen, timeout: float = 10.0) -> None:
    """兜底清理：保证测试进程树不外泄。

    venv 的 python.exe 是 launcher（真实解释器是其子进程），只杀 launcher
    会把子进程变成孤儿继续睡眠——因此先整树击杀，再回收 launcher 本体。
    """
    try:
        import psutil
        for child in psutil.Process(proc.pid).children(recursive=True):
            with contextlib.suppress(Exception):
                child.kill()
    except Exception:
        pass
    try:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=timeout)
    except Exception:
        pass


def _wait_alive(proc: subprocess.Popen, timeout: float = 10.0) -> None:
    """等待子进程真正起来（避免杀了个还没注册的 pid）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if pm.is_process_alive(proc.pid):
            return
        if proc.poll() is not None:
            raise AssertionError("子进程提前退出，测试环境异常")
        time.sleep(0.05)
    raise AssertionError("子进程未在超时内进入存活状态")


# ---------------------------------------------------------------------------
# terminate_process_tree：有 psutil（正常路径）
# ---------------------------------------------------------------------------

def test_terminate_process_tree_kills_real_child():
    proc = _sleep_proc()
    try:
        _wait_alive(proc)
        result = pm.terminate_process_tree(proc.pid, timeout=5.0)
        assert result["success"] is True
        assert result["errors"] == []
        assert proc.pid in result["terminated"] or proc.pid in result["killed"]
        # 子进程必须真的退出
        assert proc.wait(timeout=10) is not None
        assert pm.is_process_alive(proc.pid) is False
    finally:
        _ensure_dead(proc)


def test_terminate_process_tree_kills_grandchildren():
    """父子两层进程树：terminate 后孙进程也不残留。"""
    parent = subprocess.Popen(
        [sys.executable, "-c",
         "import subprocess, sys, time\n"
         "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'])\n"
         "time.sleep(60)\n"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        _wait_alive(parent)
        deadline = time.time() + 10.0
        tree = pm.get_process_tree(parent.pid)
        while not tree and time.time() < deadline:
            time.sleep(0.2)
            tree = pm.get_process_tree(parent.pid)
        assert tree, "应能枚举出至少一个子进程（psutil 正常路径）"
        result = pm.terminate_process_tree(parent.pid, timeout=5.0)
        assert result["success"] is True
        # 收集到的子孙 pid 全部命中终止结果
        handled = set(result["terminated"]) | set(result["killed"]) \
            | set(result["already_dead"])
        assert set(tree) <= handled
        assert parent.wait(timeout=10) is not None
        for pid in tree:
            assert pm.is_process_alive(pid) is False, f"孙进程 {pid} 残留"
    finally:
        for pid in pm.get_process_tree(parent.pid):
            try:
                import psutil
                psutil.Process(pid).kill()
            except Exception:
                pass
        _ensure_dead(parent)


def test_terminate_process_tree_include_parent_false_spares_parent():
    """include_parent=False：根 pid 不进终止列表，只清子孙。

    注意 venv 的 python.exe 是 launcher（会派生真实解释器子进程），
    杀光子孙后 launcher 自然退出，故这里只断言列表语义；无子孙根的
    存活语义由下方用例（基础解释器直启）单独固化。
    """
    proc = _sleep_proc()
    try:
        _wait_alive(proc)
        result = pm.terminate_process_tree(proc.pid, timeout=5.0,
                                           include_parent=False)
        assert result["success"] is True
        assert proc.pid not in result["terminated"]
        assert proc.pid not in result["killed"]
    finally:
        _ensure_dead(proc)


def test_terminate_process_tree_include_parent_false_childless_root_alive():
    """include_parent=False 且根无子孙：根进程必须原样存活。

    用 sys._base_executable 直启（绕开 venv launcher 的父子间接），
    若该环境解释器仍自带子进程则跳过（无干净无子孙场景）。
    """
    base = getattr(sys, "_base_executable", None) or sys.executable
    proc = subprocess.Popen([base, "-c", "import time; time.sleep(60)"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        _wait_alive(proc)
        if pm.get_process_tree(proc.pid):
            pytest.skip("该环境解释器自带子进程（如重定向器），"
                        "无干净无子孙根可测")
        result = pm.terminate_process_tree(proc.pid, timeout=5.0,
                                           include_parent=False)
        assert result["success"] is True
        assert result["terminated"] == [] and result["killed"] == []
        assert pm.is_process_alive(proc.pid) is True
    finally:
        _ensure_dead(proc)


# ---------------------------------------------------------------------------
# kill_process_tree：立即强杀
# ---------------------------------------------------------------------------

def test_kill_process_tree_immediate_kill():
    proc = _sleep_proc()
    try:
        _wait_alive(proc)
        result = pm.kill_process_tree(proc.pid)
        assert result["success"] is True
        assert proc.pid in result["killed"]
        assert result["terminated"] == []
        assert proc.wait(timeout=10) is not None
    finally:
        _ensure_dead(proc)


# ---------------------------------------------------------------------------
# 已死 pid：already_dead 路径
# ---------------------------------------------------------------------------

def _dead_pid() -> subprocess.Popen:
    proc = subprocess.Popen([sys.executable, "-c", "pass"],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    proc.wait(timeout=10)  # 确认已退出且被回收
    return proc


def test_terminate_process_tree_reports_already_dead():
    proc = _dead_pid()
    result = pm.terminate_process_tree(proc.pid)
    assert proc.pid in result["already_dead"]
    assert result["success"] is True
    assert result["terminated"] == [] and result["killed"] == []


def test_kill_process_tree_reports_already_dead():
    proc = _dead_pid()
    result = pm.kill_process_tree(proc.pid)
    assert proc.pid in result["already_dead"]
    assert result["success"] is True


def test_is_process_alive_false_for_dead_pid():
    proc = _dead_pid()
    assert pm.is_process_alive(proc.pid) is False


def test_is_process_alive_true_for_running_child():
    proc = _sleep_proc()
    try:
        _wait_alive(proc)
        assert pm.is_process_alive(proc.pid) is True
    finally:
        _ensure_dead(proc)


# ---------------------------------------------------------------------------
# 无 psutil：回退路径（ctypes _pid_alive / 明确的成功=False 契约）
# ---------------------------------------------------------------------------

def test_no_psutil_terminate_reports_failure_and_caller_fallback(monkeypatch):
    """PSUTIL_AVAILABLE=False 时 terminate_process_tree 返回失败契约，
    调用方（api.cancel_translation）据此回退 proc.terminate()——一并验证回退有效。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    proc = _sleep_proc()
    try:
        _wait_alive(proc)
        result = pm.terminate_process_tree(proc.pid)
        assert result["success"] is False
        assert any("psutil" in e.lower() for e in result["errors"])
        assert pm.is_process_alive(proc.pid) is True  # 无 psutil 不做任何终止
        # 调用方回退：proc.terminate() 后进程必须退出
        proc.terminate()
        assert proc.wait(timeout=10) is not None
    finally:
        _ensure_dead(proc)


def test_no_psutil_is_process_alive_uses_pid_alive_fallback(monkeypatch):
    """无 psutil 时 is_process_alive 走 _pid_alive（Windows ctypes 查询）。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    proc = _sleep_proc()
    try:
        _wait_alive(proc)
        assert pm.is_process_alive(proc.pid) is True
    finally:
        _ensure_dead(proc)
    # 死 pid
    dead = _dead_pid()
    assert pm.is_process_alive(dead.pid) is False


# ---------------------------------------------------------------------------
# 超时参数：子进程忽略 SIGTERM 的宽限场景（Windows TerminateProcess 无法
# 被捕获，仅 POSIX 可复现；Windows 环境跳过——强杀语义已由上方用例覆盖）
# ---------------------------------------------------------------------------

def test_terminate_timeout_grace_then_force_kill():
    """POSIX 宽限超时强杀：忽略 SIGTERM 的进程最终被终止（分类是平台实现细节）。"""
    if os.name == "nt":
        pytest.skip("Windows TerminateProcess 无法被进程捕获，"
                    "SIGTERM 宽限超时场景仅 POSIX 可复现")
    code = (
        "import signal, time\n"
        "signal.signal(signal.SIGTERM, lambda *a: None)\n"
        "time.sleep(60)\n"
    )
    proc = subprocess.Popen([sys.executable, "-c", code],
                            stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)
    try:
        _wait_alive(proc)
        result = pm.terminate_process_tree(proc.pid, timeout=0.5)
        assert proc.wait(timeout=15) is not None
        handled = set(result["terminated"]) | set(result["killed"]) \
            | set(result["already_dead"])
        assert proc.pid in handled, "忽略 SIGTERM 的进程应在宽限超时后被终止"
        assert pm.is_process_alive(proc.pid) is False, "进程应已终止"
    finally:
        _ensure_dead(proc, timeout=15.0)


# ---------------------------------------------------------------------------
# v1.3.2 task4：进程治理两原语
# （run_with_timeout_tree / terminate_process_tree_robust）
# ---------------------------------------------------------------------------

# 假进程树代码：父进程派生孙进程后各自长眠（命令行带 #T4 标记供残留扫描）
_TREE_PARENT_CODE = (
    "import subprocess, sys, time\n"
    "subprocess.Popen([sys.executable, '-c', "
    "'import time; time.sleep(60)#T4GC'])\n"
    "time.sleep(60)#T4P\n"
)


def _wait_tree(parent: subprocess.Popen, timeout: float = 10.0) -> list[int]:
    """等待父进程的子孙进程树出现（避免杀了个还没注册的树）。"""
    deadline = time.time() + timeout
    tree = pm.get_process_tree(parent.pid)
    while not tree and time.time() < deadline:
        time.sleep(0.2)
        tree = pm.get_process_tree(parent.pid)
    return tree


def _t4_marker_pids() -> list[int]:
    """按命令行 #T4 标记扫描假进程树 pid（含已死未清的 pid）。"""
    import psutil
    pids = []
    for p in psutil.process_iter(attrs=["cmdline"]):
        try:
            cl = p.info["cmdline"] or []
        except Exception:
            continue
        if any(isinstance(c, str) and "#T4" in c for c in cl):
            pids.append(p.pid)
    return pids


def _kill_by_pids(pids) -> None:
    """兜底清理：按 pid 强杀（best-effort，幂等无害）。"""
    import psutil
    for pid in pids:
        with contextlib.suppress(Exception):
            psutil.Process(pid).kill()


def _await_all_dead(pids, timeout: float = 10.0) -> list[int]:
    """轮询等待 pids 全部消亡，返回仍存活的 pid 列表。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline \
            and any(pm.is_process_alive(p) for p in pids):
        time.sleep(0.1)
    return [p for p in pids if pm.is_process_alive(p)]


def test_run_with_timeout_tree_completes_without_timeout():
    """正常完成路径：timed_out=False，stdout/returncode 正常回收。"""
    result = pm.run_with_timeout_tree(
        [sys.executable, "-c", "print('tree-run-ok')"], timeout=30)
    assert result.timed_out is False
    assert result.returncode == 0
    assert "tree-run-ok" in (result.stdout or "")


def test_run_with_timeout_tree_kills_tree_on_timeout():
    """psutil 实跑：cmd 自带孙进程，超时后整树（父/子/孙）无残留。"""
    assert _t4_marker_pids() == [], "运行前不应有 #T4 标记残留进程"
    start = time.monotonic()
    result = pm.run_with_timeout_tree(
        [sys.executable, "-c", _TREE_PARENT_CODE], timeout=2.0)
    elapsed = time.monotonic() - start
    assert result.timed_out is True
    assert result.returncode is not None
    leftover = _await_all_dead(_t4_marker_pids())
    assert leftover == [], f"整树未杀干净，残留: {leftover}"
    assert elapsed < 30, f"超时树杀耗时异常: {elapsed:.1f}s"
    _kill_by_pids(_t4_marker_pids())  # 清扫已死未消失的标记进程（幂等）


def test_run_with_timeout_tree_taskkill_fallback_args(monkeypatch):
    """无 psutil + Windows：超时回退 taskkill，参数形态恰为
    [taskkill, /PID, <pid>, /T, /F]。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    calls = []
    recorded = {}

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    real_popen = pm.subprocess.Popen

    def _recording_popen(*a, **kw):
        p = real_popen(*a, **kw)
        recorded["pid"] = p.pid
        return p

    monkeypatch.setattr(pm.subprocess, "run", _fake_run)
    monkeypatch.setattr(pm.subprocess, "Popen", _recording_popen)
    try:
        result = pm.run_with_timeout_tree(
            [sys.executable, "-c", "import time; time.sleep(60)"], timeout=1.0)
    finally:
        _kill_by_pids(list(recorded.values()))
    assert result.timed_out is True
    assert calls == [["taskkill", "/PID", str(recorded.get("pid")), "/T", "/F"]]


def test_run_with_timeout_tree_taskkill_failure_falls_back_single_kill(
        monkeypatch, caplog):
    """终态兜底（硬要求）：taskkill 自身抛错 → 兜底单杀 + warning 记录，
    调用方不被无限阻塞。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)

    def _boom(*a, **kw):
        raise OSError("taskkill boom")

    monkeypatch.setattr(pm.subprocess, "run", _boom)
    recorded = {}
    real_popen = pm.subprocess.Popen

    def _recording_popen(*a, **kw):
        p = real_popen(*a, **kw)
        recorded["pid"] = p.pid
        return p

    monkeypatch.setattr(pm.subprocess, "Popen", _recording_popen)
    try:
        with caplog.at_level(logging.WARNING, logger="subtransjav"):
            result = pm.run_with_timeout_tree(
                [sys.executable, "-c", "import time; time.sleep(60)"],
                timeout=1.0)
    finally:
        _kill_by_pids(list(recorded.values()))
    assert result.timed_out is True
    assert any("taskkill" in r.getMessage() for r in caplog.records)
    assert recorded.get("pid") is not None
    assert pm.is_process_alive(recorded["pid"]) is False  # 兜底单杀已生效


def test_terminate_process_tree_robust_psutil_clears_tree():
    """psutil 实跑：父→子→孙假树全清，返回 True。"""
    parent = subprocess.Popen(
        [sys.executable, "-c", _TREE_PARENT_CODE],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        _wait_alive(parent)
        tree = _wait_tree(parent)
        assert tree, "应能枚举出至少一个子进程（psutil 正常路径）"
        assert pm.terminate_process_tree_robust(parent.pid) is True
        assert parent.wait(timeout=10) is not None
        leftover = _await_all_dead(tree)
        assert leftover == [], f"孙进程残留: {leftover}"
    finally:
        _kill_by_pids(pm.get_process_tree(parent.pid))
        _ensure_dead(parent)


def test_terminate_process_tree_robust_taskkill_fallback_args(monkeypatch):
    """无 psutil + Windows：taskkill 参数形态恰为 [taskkill, /PID, <pid>, /T, /F]。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    calls = []

    def _fake_run(args, **kwargs):
        calls.append(list(args))
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(pm.subprocess, "run", _fake_run)
    proc = _sleep_proc()
    try:
        _wait_alive(proc)
        ok = pm.terminate_process_tree_robust(proc.pid)
        assert ok is True
        assert calls == [["taskkill", "/PID", str(proc.pid), "/T", "/F"]]
    finally:
        _ensure_dead(proc)


def test_terminate_process_tree_robust_taskkill_failure_returns_false(
        monkeypatch, caplog):
    """无 psutil + Windows：taskkill 抛错 → warning + 返回 False（全清失败），
    不吞错、由调用方决定后续回退。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)

    def _boom(*a, **kw):
        raise OSError("taskkill boom")

    monkeypatch.setattr(pm.subprocess, "run", _boom)
    proc = _sleep_proc()
    try:
        _wait_alive(proc)
        with caplog.at_level(logging.WARNING, logger="subtransjav"):
            ok = pm.terminate_process_tree_robust(proc.pid)
        assert ok is False
        assert any("taskkill" in r.getMessage() for r in caplog.records)
        assert pm.is_process_alive(proc.pid) is True  # 未误杀，交回调用方兜底
    finally:
        _ensure_dead(proc)


@pytest.mark.skipif(os.name == "nt",
                    reason="POSIX 专属分支（start_new_session + killpg），"
                           "Windows 本机不实跑")
def test_run_with_timeout_tree_posix_timeout_kills_group():
    """POSIX：start_new_session 创建，超时 killpg 整组杀（含孙进程）。"""
    result = pm.run_with_timeout_tree(
        [sys.executable, "-c", _TREE_PARENT_CODE], timeout=1.0)
    assert result.timed_out is True
    assert result.returncode is not None
    leftover = _await_all_dead(_t4_marker_pids())
    assert leftover == [], f"整树未杀干净，残留: {leftover}"


@pytest.mark.skipif(os.name == "nt",
                    reason="POSIX 专属分支（killpg），Windows 本机不实跑")
def test_terminate_process_tree_robust_posix_group_leader_killpg():
    """POSIX：目标自成进程组（pgid==pid）→ killpg 整组杀，返回 True。"""
    proc = subprocess.Popen(
        [sys.executable, "-c", "import time; time.sleep(60)"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True)
    try:
        _wait_alive(proc)
        assert os.getpgid(proc.pid) == proc.pid
        assert pm.terminate_process_tree_robust(proc.pid) is True
        assert proc.wait(timeout=10) is not None
    finally:
        _ensure_dead(proc)


@pytest.mark.skipif(os.name == "nt",
                    reason="POSIX 专属分支（单杀降级），Windows 本机不实跑")
def test_terminate_process_tree_robust_posix_non_leader_degrades_single_kill(caplog):
    """POSIX：目标不自成进程组 → 降级单杀 + warning，不误伤同组进程。"""
    proc = _sleep_proc()  # 未设 start_new_session，与 pytest 同组
    try:
        _wait_alive(proc)
        if os.getpgid(proc.pid) == proc.pid:
            pytest.skip("环境使子进程自成进程组，无非 leader 场景可测")
        with caplog.at_level(logging.WARNING, logger="subtransjav"):
            ok = pm.terminate_process_tree_robust(proc.pid)
        assert ok is True
        assert any("进程组" in r.getMessage() and "单杀" in r.getMessage()
                   for r in caplog.records)
        assert proc.wait(timeout=10) is not None
    finally:
        _ensure_dead(proc)
