"""process_manager 跨平台进程树治理补测（卡D1，纯测试新增）。

全部用例以 **monkeypatch 伪对象** 覆盖异常分支与无 psutil 降级面，
不起真实子进程、不调用真实 kill/taskkill，杜绝误杀。

覆盖面（对应卡面五组断言点）：
1. PSUTIL_AVAILABLE=False 的四原语回退契约；
2. 伪 psutil.Process 的构造/children/terminate/kill 异常分类；
3. wait_procs 返回 still_alive 后的强杀与 terminated 剔除；
4. run_with_timeout_tree 的 TimeoutExpired 三路（psutil/taskkill/killpg）
   及二次 communicate 异常回退空输出；
5. terminate_process_tree_robust 的 POSIX 分支（killpg / 全清 / 降级单杀）。
"""
import logging
import subprocess
import types

import subtransjav.utils.process_manager as pm

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
        self.terminated = False
        self.killed = False

    def children(self, recursive=False):
        if self._children_error is not None:
            raise self._children_error
        return list(self._children)

    def terminate(self):
        if self._terminate_error is not None:
            raise self._terminate_error
        self.terminated = True

    def kill(self):
        if self._kill_error is not None:
            raise self._kill_error
        self.killed = True


def _wait_procs_all_gone(procs, timeout=None):
    """默认 wait_procs：全部优雅退出。"""
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
    """伪 subprocess.Popen：第一次 communicate 必超时，第二次按配置返回/抛错。"""

    def __init__(self, cmd, **kwargs):
        self.cmd = cmd
        self.kwargs = kwargs
        self.pid = 4321
        self.returncode = 9
        self.communicate_timeouts = []
        self.second_error = None
        self.kill_calls = 0
        self._calls = 0

    def communicate(self, timeout=None):
        self._calls += 1
        self.communicate_timeouts.append(timeout)
        if self._calls == 1:
            raise subprocess.TimeoutExpired(self.cmd, timeout)
        if self.second_error is not None:
            raise self.second_error
        return "out", "err"

    def kill(self):
        self.kill_calls += 1


def _install_popen(monkeypatch, second_error=None):
    popens = []

    def _factory(cmd, **kwargs):
        proc = _FakePopen(cmd, **kwargs)
        proc.second_error = second_error
        popens.append(proc)
        return proc

    monkeypatch.setattr(pm.subprocess, "Popen", _factory)
    return popens


_FAKE_SIGKILL = 9


def _install_posix_signal(monkeypatch):
    monkeypatch.setattr(pm, "signal", types.SimpleNamespace(SIGKILL=_FAKE_SIGKILL))


def _fake_posix_os(
    pgid,
    *,
    getpgid_error=None,
    killpg_error=None,
    kill_error=None,
):
    calls = {"killpg": [], "kill": []}

    def _getpgid(pid):
        if getpgid_error is not None:
            raise getpgid_error
        return pgid

    def _killpg(group, sig):
        calls["killpg"].append((group, sig))
        if killpg_error is not None:
            raise killpg_error

    def _kill(pid, sig):
        calls["kill"].append((pid, sig))
        if kill_error is not None:
            raise kill_error

    return types.SimpleNamespace(
        name="posix", getpgid=_getpgid, killpg=_killpg, kill=_kill), calls


# ---------------------------------------------------------------------------
# 组1：PSUTIL_AVAILABLE=False 的回退契约
# ---------------------------------------------------------------------------

def test_no_psutil_terminate_and_kill_report_failure(monkeypatch):
    """无 psutil：terminate/kill 均返回 success=False 且 errors 说明原因。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)

    terminate_result = pm.terminate_process_tree(1234)
    assert terminate_result["success"] is False
    assert any("psutil" in e.lower() for e in terminate_result["errors"])
    assert terminate_result["terminated"] == []
    assert terminate_result["killed"] == []

    kill_result = pm.kill_process_tree(1234)
    assert kill_result["success"] is False
    assert any("psutil" in e for e in kill_result["errors"])
    assert kill_result["killed"] == []


def test_no_psutil_get_process_tree_returns_empty(monkeypatch, caplog):
    """无 psutil：get_process_tree 返回 [] 并记录 warning。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    with caplog.at_level(logging.WARNING, logger="subtransjav"):
        assert pm.get_process_tree(1234) == []
    assert any("psutil not available" in r.getMessage() for r in caplog.records)


def test_no_psutil_is_process_alive_falls_back_to_pid_alive(monkeypatch):
    """无 psutil：is_process_alive 直接走 _pid_alive 回退。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    seen = []

    def _fake_pid_alive(pid):
        seen.append(pid)
        return True

    monkeypatch.setattr(pm, "_pid_alive", _fake_pid_alive)
    assert pm.is_process_alive(1234) is True
    assert seen == [1234]


# ---------------------------------------------------------------------------
# 组2：伪 psutil.Process 异常分类
# ---------------------------------------------------------------------------

def test_process_construction_errors_classified(monkeypatch):
    """Process(pid) 构造异常：NoSuchProcess→already_dead；AccessDenied/通用→errors。"""
    cases = [
        (FakeNoSuchProcess("gone"), True, "already_dead", None),
        (FakeAccessDenied("denied"), False, "errors", "Access denied"),
        (RuntimeError("boom"), False, "errors", "Cannot access"),
    ]
    for exc, expected_success, bucket, message in cases:
        _install_psutil(monkeypatch, _raiser(exc))
        result = pm.terminate_process_tree(9000)
        assert result["success"] is expected_success
        assert result[bucket]
        if bucket == "already_dead":
            assert result["already_dead"] == [9000]
        if message is not None:
            assert any(message in e for e in result["errors"])
        assert result["terminated"] == []
        assert result["killed"] == []


def test_children_enumeration_errors(monkeypatch):
    """children() 异常：NoSuchProcess 静默跳过；通用异常记录 errors，父进程照杀。"""
    parent = _FakeProc(9001, children_error=FakeNoSuchProcess("parent gone"))
    _install_psutil(monkeypatch, _proc_factory(parent))
    result = pm.terminate_process_tree(9001)
    assert result["success"] is True
    assert result["terminated"] == [9001]
    assert result["errors"] == []

    parent = _FakeProc(9002, children_error=RuntimeError("enum boom"))
    _install_psutil(monkeypatch, _proc_factory(parent))
    result = pm.terminate_process_tree(9002)
    assert any("Failed to get children" in e for e in result["errors"])
    assert result["terminated"] == [9002]


def test_terminate_classification(monkeypatch):
    """terminate() 异常：NoSuchProcess→already_dead；AccessDenied/通用→errors（success 不翻转）。"""
    cases = [
        (FakeNoSuchProcess("gone"), "already_dead", None),
        (FakeAccessDenied("denied"), "errors", "Access denied terminating"),
        (RuntimeError("boom"), "errors", "Failed to terminate"),
    ]
    for exc, bucket, message in cases:
        parent = _FakeProc(9003, terminate_error=exc)
        _install_psutil(monkeypatch, _proc_factory(parent))
        result = pm.terminate_process_tree(9003)
        assert result["success"] is True
        if bucket == "already_dead":
            assert result["already_dead"] == [9003]
        else:
            assert any(message in e for e in result["errors"])
        assert result["terminated"] == []
        assert result["killed"] == []


def test_kill_process_tree_classification(monkeypatch):
    """kill() 异常：NoSuchProcess→already_dead；AccessDenied/通用→errors 且 success=False。"""
    cases = [
        (FakeNoSuchProcess("gone"), True, "already_dead", None),
        (FakeAccessDenied("denied"), False, "errors", "Access denied killing"),
        (RuntimeError("boom"), False, "errors", "Failed to kill"),
    ]
    for exc, expected_success, bucket, message in cases:
        parent = _FakeProc(9004, kill_error=exc)
        _install_psutil(monkeypatch, _proc_factory(parent))
        result = pm.kill_process_tree(9004)
        assert result["success"] is expected_success
        if bucket == "already_dead":
            assert result["already_dead"] == [9004]
        else:
            assert any(message in e for e in result["errors"])
        assert result["killed"] == []


# ---------------------------------------------------------------------------
# 组3：wait_procs 返回 still_alive 后的强杀与分类
# ---------------------------------------------------------------------------

def test_wait_procs_force_kill_and_classification(monkeypatch):
    """still_alive 强杀成功→killed 且从 terminated 剔除；强杀异常按类型分类。"""
    child = _FakeProc(9101)
    parent = _FakeProc(9100, children=[child])
    _install_psutil(
        monkeypatch, lambda pid: parent,
        wait_procs=lambda procs, timeout=None: ([], [parent]))
    result = pm.terminate_process_tree(9100)
    assert result["success"] is True
    assert result["killed"] == [9100]
    assert result["terminated"] == [9101]  # 父进程被强杀后剔除
    assert parent.killed is True

    # 强杀 AccessDenied：success=False，且不移出 terminated
    child = _FakeProc(9111)
    parent = _FakeProc(9110, children=[child], kill_error=FakeAccessDenied("denied"))
    _install_psutil(
        monkeypatch, lambda pid: parent,
        wait_procs=lambda procs, timeout=None: ([], [parent]))
    result = pm.terminate_process_tree(9110)
    assert result["success"] is False
    assert any("Access denied killing PID 9110" in e for e in result["errors"])
    assert 9110 in result["terminated"]

    # 强杀 NoSuchProcess：归入 already_dead，success 保持 True
    child = _FakeProc(9121, kill_error=FakeNoSuchProcess("gone"))
    parent = _FakeProc(9120, children=[child])
    _install_psutil(
        monkeypatch, lambda pid: parent,
        wait_procs=lambda procs, timeout=None: ([], [child]))
    result = pm.terminate_process_tree(9120)
    assert result["success"] is True
    assert result["already_dead"] == [9121]
    assert 9121 in result["terminated"]


# ---------------------------------------------------------------------------
# 组4：run_with_timeout_tree 超时三路 + 二次 communicate 异常
# ---------------------------------------------------------------------------

def test_run_timeout_psutil_tree_kill_and_failure_warning(monkeypatch, caplog):
    """psutil 路径：超时走 terminate_process_tree；树杀失败仅告警不阻塞。"""
    popens = _install_popen(monkeypatch)
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", True)
    calls = []
    monkeypatch.setattr(
        pm, "terminate_process_tree",
        lambda pid: calls.append(pid) or {"success": True, "errors": []})
    result = pm.run_with_timeout_tree(["fake-cmd"], timeout=0.5)
    assert result.timed_out is True
    assert result.stdout == "out"
    assert calls == [4321]
    assert popens[0].kill_calls == 1  # 终态兜底单杀
    assert popens[0].communicate_timeouts == [0.5, 5]

    popens = _install_popen(monkeypatch)
    monkeypatch.setattr(
        pm, "terminate_process_tree",
        lambda pid: {"success": False, "errors": ["denied"]})
    with caplog.at_level(logging.WARNING, logger="subtransjav"):
        result = pm.run_with_timeout_tree(["fake-cmd"], timeout=0.5)
    assert result.timed_out is True
    assert any("树杀未完全成功" in r.getMessage() for r in caplog.records)
    assert popens[0].kill_calls == 1


def test_run_timeout_taskkill_fallback(monkeypatch, caplog):
    """无 psutil + Windows：超时回退 _taskkill_tree(pid)，失败告警。"""
    _install_popen(monkeypatch)
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    monkeypatch.setattr(pm, "os", types.SimpleNamespace(name="nt"))
    calls = []

    def _fake_taskkill(pid):
        calls.append(pid)
        return False, "taskkill 退出码 5"

    monkeypatch.setattr(pm, "_taskkill_tree", _fake_taskkill)
    with caplog.at_level(logging.WARNING, logger="subtransjav"):
        result = pm.run_with_timeout_tree(["fake-cmd"], timeout=0.5)
    assert result.timed_out is True
    assert calls == [4321]
    assert any("taskkill 树杀未完全成功" in r.getMessage() for r in caplog.records)


def test_run_timeout_killpg_fallback(monkeypatch):
    """无 psutil + POSIX：子进程 start_new_session=True，超时 killpg 整组杀。"""
    popens = _install_popen(monkeypatch)
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    _install_posix_signal(monkeypatch)
    killpg_calls = []
    monkeypatch.setattr(
        pm, "os",
        types.SimpleNamespace(
            name="posix",
            killpg=lambda group, sig: killpg_calls.append((group, sig))))
    result = pm.run_with_timeout_tree(["fake-cmd"], timeout=0.5)
    assert result.timed_out is True
    assert popens[0].kwargs["start_new_session"] is True
    assert killpg_calls == [(4321, _FAKE_SIGKILL)]


def test_run_timeout_second_communicate_failure_blanks_output(monkeypatch):
    """树杀后二次 communicate 仍异常：放弃回收输出，返回空串且不阻塞。"""
    popens = _install_popen(monkeypatch, second_error=OSError("pipe stuck"))
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", True)
    monkeypatch.setattr(
        pm, "terminate_process_tree",
        lambda pid: {"success": True, "errors": []})
    result = pm.run_with_timeout_tree(["fake-cmd"], timeout=0.5)
    assert result.timed_out is True
    assert result.stdout == ""
    assert result.stderr == ""
    assert popens[0].kill_calls == 1


# ---------------------------------------------------------------------------
# 组5：terminate_process_tree_robust 的 POSIX 分支
# ---------------------------------------------------------------------------

def test_robust_posix_group_leader_killpg(monkeypatch):
    """pgid==pid：killpg 整组杀；ProcessLookupError 视为已全清。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    _install_posix_signal(monkeypatch)
    fake_os, calls = _fake_posix_os(7000)
    monkeypatch.setattr(pm, "os", fake_os)
    assert pm.terminate_process_tree_robust(7000) is True
    assert calls["killpg"] == [(7000, _FAKE_SIGKILL)]
    assert calls["kill"] == []

    fake_os, calls = _fake_posix_os(
        7001, killpg_error=ProcessLookupError("gone"))
    monkeypatch.setattr(pm, "os", fake_os)
    assert pm.terminate_process_tree_robust(7001) is True
    assert calls["kill"] == []


def test_robust_posix_killpg_oserror_returns_false(monkeypatch, caplog):
    """pgid==pid 但 killpg 抛 OSError：返回 False 并告警。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    _install_posix_signal(monkeypatch)
    fake_os, _ = _fake_posix_os(7002, killpg_error=OSError("eprem"))
    monkeypatch.setattr(pm, "os", fake_os)
    with caplog.at_level(logging.WARNING, logger="subtransjav"):
        assert pm.terminate_process_tree_robust(7002) is False
    assert any("killpg 树杀失败" in r.getMessage() for r in caplog.records)


def test_robust_posix_non_leader_degrades_single_kill(monkeypatch, caplog):
    """非 leader（或 getpgid 失败）：降级 os.kill 单杀并告警。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", False)
    _install_posix_signal(monkeypatch)

    # 同组非 leader：pgid != pid → 单杀
    fake_os, calls = _fake_posix_os(1)
    monkeypatch.setattr(pm, "os", fake_os)
    with caplog.at_level(logging.WARNING, logger="subtransjav"):
        assert pm.terminate_process_tree_robust(7003) is True
    assert calls["kill"] == [(7003, _FAKE_SIGKILL)]
    assert calls["killpg"] == []
    assert any("降级为单杀" in r.getMessage() for r in caplog.records)

    # getpgid 抛 OSError → pgid=None → 同样降级单杀
    fake_os, calls = _fake_posix_os(
        7004, getpgid_error=OSError("no such group"))
    monkeypatch.setattr(pm, "os", fake_os)
    assert pm.terminate_process_tree_robust(7004) is True
    assert calls["kill"] == [(7004, _FAKE_SIGKILL)]

    # 单杀时 ProcessLookupError → 已死即全清
    fake_os, _ = _fake_posix_os(1, kill_error=ProcessLookupError("gone"))
    monkeypatch.setattr(pm, "os", fake_os)
    assert pm.terminate_process_tree_robust(7005) is True

    # 单杀时其他 OSError → False + 告警
    fake_os, _ = _fake_posix_os(1, kill_error=OSError("eperm"))
    monkeypatch.setattr(pm, "os", fake_os)
    with caplog.at_level(logging.WARNING, logger="subtransjav"):
        assert pm.terminate_process_tree_robust(7006) is False
    assert any("单杀降级失败" in r.getMessage() for r in caplog.records)


def test_robust_psutil_path_delegates(monkeypatch):
    """psutil 可用：robust 直接委托 terminate_process_tree 并取 success。"""
    monkeypatch.setattr(pm, "PSUTIL_AVAILABLE", True)
    monkeypatch.setattr(
        pm, "terminate_process_tree",
        lambda pid: {"success": True, "terminated": [pid], "killed": [],
                     "already_dead": [], "errors": []})
    assert pm.terminate_process_tree_robust(7007) is True
    monkeypatch.setattr(
        pm, "terminate_process_tree",
        lambda pid: {"success": False, "terminated": [], "killed": [],
                     "already_dead": [], "errors": ["x"]})
    assert pm.terminate_process_tree_robust(7007) is False


# 卡面组件点已全部覆盖；pytest 仅用于失败定位，无真实进程/真实 kill。
