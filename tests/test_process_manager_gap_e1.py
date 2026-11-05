"""process_manager 残余失败链与 venv 分派补测（卡E1，纯测试新增）。

全部用例以 **monkeypatch 伪对象** 覆盖异常分支，不起真实子进程、
不调用真实 kill/taskkill，杜绝误杀。

覆盖面（对应卡面七组断言点）：
1. get_process_tree 通用异常告警含 pid 且返回 []；
2. kill_process_tree 构造异常与 children 枚举异常分类；
3. terminate_process_tree 强杀阶段通用异常；_single_kill 只告警不外抛；
4. _taskkill_tree 非零退出码与执行异常；
5. run_with_timeout_tree POSIX 分支 killpg 异常后仍走单杀兜底；
6. spawn_refine_cli 的 venv_bootstrap 分派与未知 purpose 拒绝；
7. is_process_alive 通用异常；get_process_info 三态 error dict。
"""
import logging
import subprocess
import sys
import types

import pytest

import subtrans.utils.process_manager as pm

# ---------------------------------------------------------------------------
# 伪对象：异常类、伪进程、伪 psutil 模块
# ---------------------------------------------------------------------------

class FakeNoSuchProcess(Exception):
    """对应 psutil.NoSuchProcess 的分类槽位。"""


class FakeAccessDenied(Exception):
    """对应 psutil.AccessDenied 的分类槽位。"""


class _FakeProc:
    """伪 psutil.Process：仅实现被测分支用到的方法。"""

    def __init__(
        self,
        pid,
        *,
        children=(),
        children_error=None,
        terminate_error=None,
        kill_error=None,
    ):
        self.pid = pid
        self._children = list(children)
        self._children_error = children_error
        self._terminate_error = terminate_error
        self._kill_error = kill_error
        self.killed = False

    def children(self, recursive=False):
        if self._children_error is not None:
            raise self._children_error
        return list(self._children)

    def terminate(self):
        if self._terminate_error is not None:
            raise self._terminate_error

    def kill(self):
        if self._kill_error is not None:
            raise self._kill_error
        self.killed = True


def _wait_procs_all_gone(procs, timeout=None):
    """默认 wait_procs：全部已退出。"""
    return list(procs), []


def _fake_psutil(process_factory, wait_procs=None):
    return types.SimpleNamespace(
        Process=process_factory,
        NoSuchProcess=FakeNoSuchProcess,
        AccessDenied=FakeAccessDenied,
        wait_procs=wait_procs or _wait_procs_all_gone,
        STATUS_ZOMBIE="zombie",
    )


def _install_psutil(monkeypatch, process_factory, wait_procs=None):
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", True)
    monkeypatch.setattr(pm, "psutil", _fake_psutil(process_factory, wait_procs))


def _raiser(exc):
    def _factory(pid):
        raise exc

    return _factory


def _proc_factory(proc):
    def _factory(pid):
        return proc

    return _factory


class _FakePopen:
    """伪 subprocess.Popen：第一次 communicate 必超时，第二次返回输出。"""

    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        self.kwargs = kwargs
        self.pid = 4321
        self.returncode = 9
        self.kill_calls = 0
        self._calls = 0

    def communicate(self, timeout=None):
        self._calls += 1
        if self._calls == 1:
            raise subprocess.TimeoutExpired(self.cmd, timeout)
        return "out", "err"

    def kill(self):
        self.kill_calls += 1


def _install_popen(monkeypatch):
    popens = []

    def _factory(cmd, **kwargs):
        proc = _FakePopen(cmd, **kwargs)
        popens.append(proc)
        return proc

    monkeypatch.setattr(pm.subprocess, "Popen", _factory)
    return popens


_FAKE_SIGKILL = 9


def _install_posix_signal(monkeypatch):
    monkeypatch.setattr(pm, "signal", types.SimpleNamespace(SIGKILL=_FAKE_SIGKILL))


# ---------------------------------------------------------------------------
# 组1：get_process_tree 通用异常
# ---------------------------------------------------------------------------

def test_get_process_tree_generic_exception_warns_with_pid(monkeypatch, caplog):
    """Process(pid) 抛通用异常：告警含 pid，返回 []。"""
    _install_psutil(monkeypatch, _raiser(RuntimeError("enum boom")))
    with caplog.at_level(logging.WARNING, logger="subtrans"):
        assert pm.get_process_tree(3101) == []
    messages = [r.getMessage() for r in caplog.records]
    assert any(
        "Failed to enumerate process tree" in m and "3101" in m for m in messages
    )


# ---------------------------------------------------------------------------
# 组2：kill_process_tree 构造异常与 children 枚举异常
# ---------------------------------------------------------------------------

def test_kill_process_tree_construction_error_and_children_failures(monkeypatch):
    """构造通用异常→success=False＋Cannot access；children 异常分类且父进程照杀。"""
    _install_psutil(monkeypatch, _raiser(RuntimeError("boom")))
    result = pm.kill_process_tree(3200)
    assert result["success"] is False
    assert any("Cannot access process 3200" in e for e in result["errors"])
    assert result["killed"] == []
    assert result["already_dead"] == []

    parent = _FakeProc(3201, children_error=FakeNoSuchProcess("parent gone"))
    _install_psutil(monkeypatch, _proc_factory(parent))
    result = pm.kill_process_tree(3201)
    assert result["success"] is True
    assert result["errors"] == []
    assert result["killed"] == [3201]

    parent = _FakeProc(3202, children_error=RuntimeError("enum boom"))
    _install_psutil(monkeypatch, _proc_factory(parent))
    result = pm.kill_process_tree(3202)
    assert result["success"] is True
    assert any("Failed to get children" in e for e in result["errors"])
    assert result["killed"] == [3202]


# ---------------------------------------------------------------------------
# 组3：terminate_process_tree 强杀阶段异常与 _single_kill 兜底
# ---------------------------------------------------------------------------

def test_terminate_force_kill_generic_error(monkeypatch):
    """强杀阶段通用异常：Failed to kill PID＋success=False，不移出 terminated。"""
    parent = _FakeProc(3300, kill_error=RuntimeError("kill boom"))
    _install_psutil(
        monkeypatch,
        _proc_factory(parent),
        wait_procs=lambda procs, timeout=None: ([], [parent]),
    )
    result = pm.terminate_process_tree(3300)
    assert result["success"] is False
    assert any("Failed to kill PID 3300" in e for e in result["errors"])
    assert result["killed"] == []
    assert 3300 in result["terminated"]


def test_single_kill_swallows_exception_and_warns(caplog):
    """_single_kill 遇异常只告警，不外抛。"""

    class _BrokenProc:
        pid = 3301

        def kill(self):
            raise OSError("kill failed")

    with caplog.at_level(logging.WARNING, logger="subtrans"):
        pm._single_kill(_BrokenProc())  # 不抛即通过
    messages = [r.getMessage() for r in caplog.records]
    assert any("兜底单杀失败" in m and "3301" in m for m in messages)


# ---------------------------------------------------------------------------
# 组4：_taskkill_tree 失败路径
# ---------------------------------------------------------------------------

def test_taskkill_tree_returncode_and_execution_failure(monkeypatch):
    """returncode!=0 → 退出码描述；run 抛异常 → 执行失败描述。"""
    monkeypatch.setattr(
        pm.subprocess, "run",
        lambda *args, **kwargs: types.SimpleNamespace(returncode=5))
    assert pm._taskkill_tree(3400) == (False, "taskkill 退出码 5")

    def _boom(*args, **kwargs):
        raise FileNotFoundError("taskkill missing")

    monkeypatch.setattr(pm.subprocess, "run", _boom)
    ok, detail = pm._taskkill_tree(3401)
    assert ok is False
    assert detail.startswith("taskkill 执行失败: ")
    assert "taskkill missing" in detail


# ---------------------------------------------------------------------------
# 组5：run_with_timeout_tree POSIX 分支 killpg 异常
# ---------------------------------------------------------------------------

def test_run_timeout_posix_killpg_error_still_single_kills(monkeypatch, caplog):
    """killpg 抛异常：告警后仍走 _single_kill，不阻塞、不抛出。"""
    popens = _install_popen(monkeypatch)
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    _install_posix_signal(monkeypatch)

    def _killpg(group, sig):
        raise OSError("eperm")

    monkeypatch.setattr(
        pm, "os", types.SimpleNamespace(name="posix", killpg=_killpg))
    with caplog.at_level(logging.WARNING, logger="subtrans"):
        result = pm.run_with_timeout_tree(["fake-cmd"], timeout=0.5)
    assert result.timed_out is True
    assert result.stdout == "out"
    assert popens[0].kill_calls == 1
    assert any("killpg 树杀失败" in r.getMessage() for r in caplog.records)


# ---------------------------------------------------------------------------
# 组6：spawn_refine_cli 的 venv_bootstrap 分派与未知 purpose
# ---------------------------------------------------------------------------

def test_spawn_refine_cli_venv_bootstrap_dispatch(monkeypatch):
    """frozen → None；非 frozen → subprocess.run 且 creationflags=0。"""
    monkeypatch.setattr(pm.paths, "is_frozen", lambda: True)
    assert pm.spawn_refine_cli(
        ["-m", "venv", ".venv"], purpose="venv_bootstrap") is None

    monkeypatch.setattr(pm.paths, "is_frozen", lambda: False)
    calls = []
    sentinel = object()

    def _fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return sentinel

    monkeypatch.setattr(pm.subprocess, "run", _fake_run)
    result = pm.spawn_refine_cli(
        ["-m", "venv", ".venv"], purpose="venv_bootstrap", cwd="D:/work")
    assert result is sentinel
    assert len(calls) == 1
    cmd, kwargs = calls[0]
    assert cmd == [sys.executable, "-m", "venv", ".venv"]
    assert kwargs["creationflags"] == 0
    assert kwargs["cwd"] == "D:/work"


def test_spawn_refine_cli_unknown_purpose_raises():
    """未知 purpose：ValueError。"""
    with pytest.raises(ValueError, match="未知 purpose"):
        pm.spawn_refine_cli([], purpose="bogus")


# ---------------------------------------------------------------------------
# 组7：is_process_alive 与 get_process_info 的异常三态
# ---------------------------------------------------------------------------

def test_is_process_alive_generic_exception_returns_false(monkeypatch):
    """psutil 通用异常 → False。"""
    _install_psutil(monkeypatch, _raiser(RuntimeError("boom")))
    assert pm.is_process_alive(3600) is False


def test_get_process_info_three_error_states(monkeypatch):
    """无 psutil／NoSuchProcess／通用异常 → 三种 error dict。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    assert pm.get_process_info(3700) == {"error": "psutil not available"}

    _install_psutil(monkeypatch, _raiser(FakeNoSuchProcess("gone")))
    assert pm.get_process_info(3701) == {"error": "Process 3701 not found"}

    _install_psutil(monkeypatch, _raiser(RuntimeError("boom")))
    assert pm.get_process_info(3702) == {"error": "boom"}


# 卡面七组断言点已全部覆盖；pytest 仅用于失败定位，无真实进程/真实 kill。
