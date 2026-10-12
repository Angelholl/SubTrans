"""ensure_lmstudio_model TTL 卸载等待复查单测（全部 mock，不触网、不真 sleep）。

背景（D2026-1006-01 件⑨，owner 真机 mufr-006 现场）：LM Studio 空闲 TTL
自动卸载把审校模型卸掉后（阶段 A 只用小模型，不重置大模型空闲计时），
无 lms CLI 时预检直接失败跳过整个文件；改为有限等待复查，给"在 LM Studio
手动加载"一个自动检测续跑窗口。

monkeypatch 目标与真实调用路径对齐：ensure_lmstudio_model 内部直接调
模块级 _loaded_ids / _find_lms / time.sleep / _loaded_ctx（后者走模块级
requests），故统一 setattr 到 lmstudio 模块命名空间。
"""

import types

from subtransjav.utils import lmstudio as lm

EP = "http://localhost:1234/v1"


class _Resp:
    def __init__(self, payload):
        self._p = payload

    def json(self):
        return self._p


class _FakeRequests:
    """只喂 HTTP 层：/v1/models 给空集（在载判定由 _loaded_ids 桩接管），
    /api/v0/models 给已下载集（兼供 _loaded_ctx 读 ctx）。"""

    def __init__(self, v0):
        self.v0 = v0

    def get(self, url, timeout=None):
        if url.endswith("/v1/models"):
            return _Resp({"data": []})
        return _Resp(self.v0)


class _FakeTime:
    """替换 lmstudio 命名空间内的 time 模块，记录 sleep 调用而非真等。"""

    def __init__(self):
        self.sleeps = []

    def sleep(self, s):
        self.sleeps.append(s)


# v0 条目 ctx=8192：供"手动加载 ctx 与配置(16384)不符"告警路径使用
V0_M1 = {"data": [{"id": "m1", "loaded_context_length": 8192}]}


def test_wait_recheck_detects_manual_load_and_continues(monkeypatch):
    """等待窗口内复查命中手动加载 → 放行续跑；ctx 不符仅告警（无 CLI
    无法重载对齐）；首查不含模型、第二次查询（窗口内首次复查）即命中，
    故 sleep 恰 1 次。"""
    monkeypatch.setattr(lm, "requests", _FakeRequests(V0_M1))
    monkeypatch.setattr(lm, "_find_lms", lambda: "")
    loaded_seq = [set(), {"m1"}]    # 首查（预检步骤1）→ 窗口内首次复查
    monkeypatch.setattr(lm, "_loaded_ids", lambda root: loaded_seq.pop(0))
    ft = _FakeTime()
    monkeypatch.setattr(lm, "time", ft)
    logs = []
    ok, msg = lm.ensure_lmstudio_model(EP, "m1", ctx_tokens=16384,
                                       log=logs.append)
    assert ok and msg == "模型已重新就绪（等待手动加载）"
    assert ft.sleeps == [lm.WAIT_INTERVAL_S]
    assert any("疑似 LM Studio 空闲 TTL 自动卸载" in m for m in logs)
    assert any("已重新就绪（检测到手动加载）" in m for m in logs)
    assert any("ctx 与管线配置不符" in m for m in logs)


def test_wait_recheck_timeout_falls_back_to_original_failure(monkeypatch):
    """复查耗尽仍不在载 → 落回现行失败文案，末尾追加已等待时长；恰好
    WAIT_RECHECKS 次 sleep。"""
    monkeypatch.setattr(lm, "requests", _FakeRequests(V0_M1))
    monkeypatch.setattr(lm, "_find_lms", lambda: "")
    monkeypatch.setattr(lm, "_loaded_ids", lambda root: set())
    ft = _FakeTime()
    monkeypatch.setattr(lm, "time", ft)
    logs = []
    ok, msg = lm.ensure_lmstudio_model(EP, "m1", log=logs.append)
    assert not ok
    assert "未按配置就绪" in msg and "已等待" in msg
    assert len(ft.sleeps) == lm.WAIT_RECHECKS
    assert any(f"第 {lm.WAIT_RECHECKS}/{lm.WAIT_RECHECKS} 次复查" in m
               for m in logs)


def test_cli_present_keeps_existing_path_no_wait(monkeypatch):
    """有 CLI → 不进入等待（sleep 零调用），走现行清场+带参加载路径。"""
    monkeypatch.setattr(lm, "requests", _FakeRequests(V0_M1))
    monkeypatch.setattr(lm, "_find_lms", lambda: "lms-fake")
    loaded = set()      # 被 fake load 联动（模拟真实 LM Studio 状态迁移）
    monkeypatch.setattr(lm, "_loaded_ids", lambda root: set(loaded))
    calls = []

    def fake_run_lms(lms, args, timeout):
        calls.append(list(args))
        if args[0] == "unload":
            loaded.clear()
        elif args[0] == "load":
            loaded.add(args[1])
        return types.SimpleNamespace(returncode=0, stdout="", stderr="",
                                     timed_out=False)

    monkeypatch.setattr(lm, "_run_lms", fake_run_lms)
    ft = _FakeTime()
    monkeypatch.setattr(lm, "time", ft)
    logs = []
    ok, msg = lm.ensure_lmstudio_model(EP, "m1", ctx_tokens=16384,
                                       log=logs.append)
    assert ok and msg == "模型已按管线配置加载"
    assert ft.sleeps == []
    assert calls and calls[0][0] == "load"
    assert any("引擎对齐" in m for m in logs)


def test_model_not_downloaded_fails_without_waiting(monkeypatch):
    """模型不在已下载集 → 沿用原失败文案，不进入等待（sleep 零调用）。"""
    monkeypatch.setattr(lm, "requests",
                        _FakeRequests({"data": [{"id": "other"}]}))
    monkeypatch.setattr(lm, "_find_lms", lambda: "")
    ft = _FakeTime()
    monkeypatch.setattr(lm, "time", ft)
    ok, msg = lm.ensure_lmstudio_model(EP, "m1")
    assert not ok and "未在 LM Studio 中下载" in msg
    assert ft.sleeps == []
