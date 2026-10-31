"""D2026-1031-07 卡D5：artifact_lock 三态语义与跨平台释放补测。

补充既有 test_artifact_lock.py 未覆盖的分支（语句 73.0%／分支 55.0%）：

1. ArtifactLockHandle.release 幂等、Windows token 比对（不符→告警不删、
   相符→删除）、_is_our_lock_file 读失败／空 token → False；
2. _lock_fd_exclusive 冲突 errno → ArtifactLockConflict、非冲突 OSError 原样
   上抛、无实现 → RuntimeError；
3. acquire_artifact_lock 的 os.open 失败降级、token 写入失败仍返回句柄；
4. POSIX 分支（msvcrt=None＋伪 fcntl）持锁先删→解锁→关闭顺序，以及
   ProcessLookupError/OSError 容错。

全部锁文件落 tmp_path，平台锁函数一律 monkeypatch 为伪实现，禁真实
跨进程锁竞争；Windows 分支在三平台上同样以伪 msvcrt 演练。
"""
import errno
import os
from pathlib import Path

import pytest

from subtransjav.refine import artifact_lock as al


class _FakeMsvcrt:
    """伪 msvcrt：只记录 locking 调用，不做真实区域锁。"""

    LK_UNLCK = 0
    LK_NBLCK = 2

    def __init__(self, exc=None):
        self.calls = []
        self._exc = exc

    def locking(self, fd, mode, nbytes):
        self.calls.append((mode, nbytes))
        if self._exc is not None:
            raise self._exc


class _FakeFcntl:
    """伪 fcntl：可指定 flock 抛出的异常，并记录调用事件。"""

    LOCK_EX = 2
    LOCK_NB = 4
    LOCK_UN = 8

    def __init__(self, exc=None, events=None):
        self._exc = exc
        self.events = events if events is not None else []

    def flock(self, fd, op):
        self.events.append("unlock" if op == self.LOCK_UN else ("flock", op))
        if self._exc is not None:
            raise self._exc


def _handle_with_content(path: Path, content: str, token: str):
    """按指定锁文件内容与 token 构造句柄（真实 fd，伪平台锁）。"""
    path.write_text(content, encoding="utf-8")
    fd = os.open(str(path), os.O_RDWR)
    return al.ArtifactLockHandle(str(path), fd, token=token)


# ---- 1. release 幂等 / Windows token 比对 / _is_our_lock_file ----

def test_release_is_idempotent_and_none_safe(tmp_path, monkeypatch):
    """release 二次调用为无操作（不重复解锁/关闭），None 句柄安全。"""
    fake = _FakeMsvcrt()
    monkeypatch.setattr(al, "msvcrt", fake)
    lock_file = tmp_path / ".abc.subtransjav.lock"
    handle = _handle_with_content(lock_file, "token=d5token\n", "d5token")

    al.release_artifact_lock(handle)
    assert not lock_file.exists()
    first_calls = list(fake.calls)
    assert first_calls == [(fake.LK_UNLCK, 1)]

    handle.release()                            # 幂等：不再触碰 fd/文件
    assert fake.calls == first_calls
    al.release_artifact_lock(None)              # None 安全


def test_release_windows_token_mismatch_keeps_file_and_warns(
        tmp_path, monkeypatch, capsys):
    """Windows 分支 token 不符（疑似他方接管）→ 告警且不删锁文件。"""
    fake = _FakeMsvcrt()
    monkeypatch.setattr(al, "msvcrt", fake)
    lock_file = tmp_path / ".abc.subtransjav.lock"
    third_content = "subtransjav-lock pid=999999 token=thirdparty\n"
    handle = _handle_with_content(lock_file, third_content, "d5token")

    handle.release()

    out = capsys.readouterr().out
    assert "放弃删除" in out
    assert lock_file.exists(), "非己方锁文件被误删（须宁残留勿误删）"
    assert lock_file.read_text(encoding="utf-8") == third_content
    assert fake.calls == [(fake.LK_UNLCK, 1)]


def test_release_windows_token_match_removes_file(tmp_path, monkeypatch):
    """Windows 分支内容含本句柄 token → 解锁、关闭后删除锁文件。"""
    fake = _FakeMsvcrt()
    monkeypatch.setattr(al, "msvcrt", fake)
    lock_file = tmp_path / ".abc.subtransjav.lock"
    handle = _handle_with_content(
        lock_file, "subtransjav-lock pid=1 token=d5token\n", "d5token")

    handle.release()

    assert not lock_file.exists()
    assert fake.calls == [(fake.LK_UNLCK, 1)]
    assert handle._released is True


def test_is_our_lock_file_read_error_and_empty_token_false(tmp_path):
    """读失败（文件不存在/不可读）与空 token 一律判非己方。"""
    missing = tmp_path / "missing.lock"
    handle = al.ArtifactLockHandle(str(missing), -1, token="d5token")
    assert handle._is_our_lock_file() is False

    readable = tmp_path / "readable.lock"
    readable.write_text("token=d5token\n", encoding="utf-8")
    empty_token = al.ArtifactLockHandle(str(readable), -1, token="")
    # 空 token 不做子串匹配（"" in content 恒真），直接判非己方。
    assert empty_token._is_our_lock_file() is False

    dir_path = tmp_path / "is_a_dir.lock"
    dir_path.mkdir()
    unreadable = al.ArtifactLockHandle(str(dir_path), -1, token="d5token")
    assert unreadable._is_our_lock_file() is False


# ---- 2. _lock_fd_exclusive 三态错误翻译 ----

def test_lock_fd_exclusive_conflict_errno_maps_to_conflict(
        tmp_path, monkeypatch):
    """msvcrt 锁冲突 errno（EACCES）→ ArtifactLockConflict。"""
    fake = _FakeMsvcrt(exc=OSError(errno.EACCES, "simulated contention"))
    monkeypatch.setattr(al, "msvcrt", fake)
    fd = os.open(str(tmp_path / "fd.lock"), os.O_CREAT | os.O_RDWR)
    try:
        with pytest.raises(al.ArtifactLockConflict):
            al._lock_fd_exclusive(fd)
    finally:
        os.close(fd)


def test_lock_fd_exclusive_other_oserror_propagates(tmp_path, monkeypatch):
    """非冲突 errno（EIO）原样上抛，不得被翻译为冲突。"""
    fake = _FakeMsvcrt(exc=OSError(errno.EIO, "simulated io failure"))
    monkeypatch.setattr(al, "msvcrt", fake)
    fd = os.open(str(tmp_path / "fd.lock"), os.O_CREAT | os.O_RDWR)
    try:
        with pytest.raises(OSError) as excinfo:
            al._lock_fd_exclusive(fd)
        assert not isinstance(excinfo.value, al.ArtifactLockConflict)
    finally:
        os.close(fd)


def test_lock_fd_exclusive_no_impl_raises_runtime_error(monkeypatch):
    """msvcrt 与 fcntl 皆缺 → RuntimeError（调用方据此降级不锁）。"""
    monkeypatch.setattr(al, "msvcrt", None)
    monkeypatch.setattr(al, "fcntl", None, raising=False)
    with pytest.raises(RuntimeError, match="no lock implementation"):
        al._lock_fd_exclusive(-1)


def test_lock_fd_exclusive_posix_conflict_and_other_oserror(
        tmp_path, monkeypatch):
    """伪 fcntl：EAGAIN → ArtifactLockConflict；EIO 原样上抛。"""
    monkeypatch.setattr(al, "msvcrt", None)
    fd = os.open(str(tmp_path / "fd.lock"), os.O_CREAT | os.O_RDWR)
    try:
        monkeypatch.setattr(
            al, "fcntl",
            _FakeFcntl(exc=OSError(errno.EAGAIN, "simulated contention")),
            raising=False)
        with pytest.raises(al.ArtifactLockConflict):
            al._lock_fd_exclusive(fd)

        monkeypatch.setattr(
            al, "fcntl",
            _FakeFcntl(exc=OSError(errno.EIO, "simulated io failure")),
            raising=False)
        with pytest.raises(OSError) as excinfo:
            al._lock_fd_exclusive(fd)
        assert not isinstance(excinfo.value, al.ArtifactLockConflict)
    finally:
        os.close(fd)


# ---- 3. acquire_artifact_lock 降级与 token 写入容错 ----

def test_acquire_open_failure_warns_and_returns_none(
        tmp_path, monkeypatch, capsys):
    """锁文件 os.open 失败 → 告警降级返回 None。"""
    def _boom(path, flags, *args, **kwargs):
        raise OSError(errno.EACCES, "simulated open failure")

    monkeypatch.setattr(al.os, "open", _boom)
    inp = tmp_path / "ep01.srt"
    inp.write_text("1\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    assert al.acquire_artifact_lock(str(inp), str(out_dir)) is None
    out = capsys.readouterr().out
    assert "产物锁文件创建失败" in out
    assert "降级不锁" in out


def test_acquire_token_write_failure_still_returns_handle(
        tmp_path, monkeypatch, capsys):
    """持锁后 token 写入 OSError → 不阻断，仍返回持锁句柄。"""
    monkeypatch.setattr(al, "_lock_fd_exclusive", lambda fd: None)
    monkeypatch.setattr(al.os, "write",
                        lambda fd, data: (_ for _ in ()).throw(
                            OSError(errno.ENOSPC, "simulated write failure")))
    inp = tmp_path / "ep01.srt"
    inp.write_text("1\n", encoding="utf-8")
    out_dir = tmp_path / "out"
    out_dir.mkdir()

    handle = al.acquire_artifact_lock(str(inp), str(out_dir))
    try:
        assert handle is not None
        assert Path(handle.path).exists()
        assert handle._token                    # 句柄仍带持有者标识
        assert capsys.readouterr().out == ""    # 写失败静默，不告警
    finally:
        os.close(handle._fd)
        Path(handle.path).unlink(missing_ok=True)


# ---- 4. POSIX 释放时序与容错（msvcrt=None＋伪 fcntl）----

def test_release_posix_unlinks_before_unlock_and_close(
        tmp_path, monkeypatch):
    """POSIX 分支行为钉：持锁先删锁文件 → 解锁 → 关闭。"""
    events = []
    real_remove = os.remove
    real_close = os.close

    def _remove(path):
        events.append("remove")
        real_remove(path)

    def _close(fd):
        events.append("close")
        real_close(fd)

    monkeypatch.setattr(al, "msvcrt", None)
    monkeypatch.setattr(al, "fcntl", _FakeFcntl(events=events),
                        raising=False)
    monkeypatch.setattr(al.os, "remove", _remove)
    monkeypatch.setattr(al.os, "close", _close)

    lock_file = tmp_path / ".abc.subtransjav.lock"
    lock_file.write_text("token=d5token\n", encoding="utf-8")
    fd = os.open(str(lock_file), os.O_RDWR)
    handle = al.ArtifactLockHandle(str(lock_file), fd, token="d5token")

    handle.release()

    assert events == ["remove", "unlock", "close"]
    assert handle._released is True
    # Windows 上删除打开中的文件会失败（真实 POSIX 分支才可 unlink-under-lock），
    # 本用例只钉调用顺序；句柄已关闭，清理残留。
    lock_file.unlink(missing_ok=True)


def test_release_posix_tolerates_unlink_unlock_close_errors(
        tmp_path, monkeypatch):
    """POSIX 分支：删除/unlock 的 ProcessLookupError、OSError 全部吞掉，
    仍继续关闭句柄且不抛出。"""
    real_close = os.close

    def _close_after_real(fd):
        real_close(fd)
        raise OSError(errno.EIO, "simulated close failure")

    monkeypatch.setattr(al, "msvcrt", None)
    monkeypatch.setattr(
        al, "fcntl",
        _FakeFcntl(exc=ProcessLookupError(errno.ESRCH, "gone")),
        raising=False)
    monkeypatch.setattr(
        al.os, "remove",
        lambda path: (_ for _ in ()).throw(OSError(errno.EPERM, "denied")))
    monkeypatch.setattr(al.os, "close", _close_after_real)

    lock_file = tmp_path / ".abc.subtransjav.lock"
    lock_file.write_text("token=d5token\n", encoding="utf-8")
    fd = os.open(str(lock_file), os.O_RDWR)
    handle = al.ArtifactLockHandle(str(lock_file), fd, token="d5token")

    handle.release()                            # 不抛

    assert handle._released is True
    with pytest.raises(OSError):
        os.fstat(fd)                            # fd 确已关闭
    lock_file.unlink(missing_ok=True)
