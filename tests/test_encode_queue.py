"""encode_queue 串行队列单测（2.8.0 批1 件3 测试，D2026-1007-03）。

零真实 ffmpeg/零真子进程：``_spawn_ffmpeg`` 经 monkeypatch 注入 FakeProc
（脚本化 out_time 行/阻塞/可杀/写 .part），``_kill_tree`` 注入记录器，
``resolve_hardsub_ffmpeg``/``probe_media`` 注入假供给，看门狗注入假钟
（FakeClock，wait_until 轮询时推进）。覆盖：串行顺序+原子成片、取消
（queued 清空+running 树杀→cancelled）、看门狗假钟三态（90s 无进展/
收尾相不误杀/收尾超时独立判）、总超时、失败清 .part、磁盘预检整批拒、
互斥 claim/release、retry 入队尾、snapshot json 可序列化、孤儿 .part 清扫。
"""
import json
import os
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from subtransjav.refine import ffmpeg_supply as fsup  # noqa: E402
from subtransjav.refine import hardsub  # noqa: E402
from subtransjav.webview_gui import encode_queue as eq  # noqa: E402

SUPPLY = fsup.SupplyResult(ffmpeg_path="ffmpeg-fake", ffprobe_path="ffprobe-fake",
                           capability={"ok": True}, missing=[])
INFO = fsup.MediaInfo(duration_s=60.0, width=1920, height=1080,
                      bit_rate_bps=4_000_000, has_audio=True, audio_codec="aac")


# ---------------------------------------------------------------------------
# Fake 基建
# ---------------------------------------------------------------------------
class FakeClock:
    """假单调钟：wait_until 轮询时手动推进（step=每次推进的假秒数）。"""

    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        return self.t

    def advance(self, d):
        self.t += d


class FakeProc:
    """假 ffmpeg 进程：stdout 按脚本 yield out_time 行；可阻塞、可杀。

    rc==0 且 write_part 时在收尾写 .part（模拟 ffmpeg 产物）；killed 置位后
    stdout EOF、rc=-9（树杀路径）。
    """

    def __init__(self, argv, lines=(), rc=0, write_part=True, block_after=False,
                 infinite=False):
        self.argv = argv
        self.pid = 4242
        self._part = argv[argv.index("-y") + 1] if "-y" in argv else None
        self._lines = list(lines)
        self._rc_final = rc
        self._write_part = write_part
        self._block_after = block_after
        self._infinite = infinite
        self._counter = 0
        self.killed = False
        self._rc = None
        self._wakeup = threading.Event()
        self.stdout = self._gen_stdout()
        self.stderr = iter(())

    def _gen_stdout(self):
        for ln in self._lines:
            if self.killed:
                return
            yield ln
        if self._infinite:
            while not self.killed:  # 持续产出=看门狗「有进展」，专测总超时
                self._counter += 1
                yield f"out_time_ms={self._counter * 5_000_000}".encode()
            return
        if self._block_after:
            self._wakeup.wait()
        if self.killed:
            return
        if self._write_part and self._part:
            with open(self._part, "wb") as f:
                f.write(b"MP4DATA")
        self._rc = self._rc_final

    def wait(self, timeout=None):
        deadline = time.monotonic() + (timeout or 30.0)
        while self._rc is None and time.monotonic() < deadline:
            time.sleep(0.001)
        return self._rc

    def poll(self):
        return self._rc

    def kill(self):
        self.killed = True
        if self._rc is None:
            self._rc = -9
        self._wakeup.set()

    def terminate(self):
        self.kill()

    def release(self):
        """测试放行：解除阻塞并按脚本收尾（非 kill 的正常完成路径）。"""
        self._wakeup.set()


class FakeSpawner:
    """按预设脚本序列吐 FakeProc，并记录调用序。"""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.procs = []

    def __call__(self, argv):
        script = self.scripts[min(len(self.procs), len(self.scripts) - 1)]
        proc = FakeProc(argv, **script)
        self.procs.append(proc)
        return proc


@pytest.fixture()
def fake_env(monkeypatch):
    """假供给+假媒体探测+树杀记录器。"""
    monkeypatch.setattr(eq, "resolve_hardsub_ffmpeg", lambda *a, **k: SUPPLY)
    monkeypatch.setattr(eq, "probe_media", lambda *a, **k: INFO)
    killed = []
    monkeypatch.setattr(eq, "_kill_tree", lambda proc: (killed.append(proc), proc.kill()))
    yield SimpleNamespace(killed=killed)


def wait_until(cond, clock=None, timeout=5.0):
    """轮询等待；clock 非 None 时每次轮询推进假钟 5 秒（驱动看门狗）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if clock is not None:
            clock.advance(5.0)
        if cond():
            return True
        time.sleep(0.005)
    return False


def mkjob(tmp_path, n, **pkw):
    video = tmp_path / f"vid{n}.mp4"
    video.write_bytes(b"v")
    sub = tmp_path / f"vid{n}.srt"
    sub.write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    out = tmp_path / f"vid{n}_hardsub.mp4"
    params = hardsub.EncodeParams(out_path=str(out), **pkw)
    return eq.EncodeJob(video_path=str(video), subtitle_path=str(sub),
                        params=params, out_path=str(out))


def fresh_queue(clock=None):
    return eq.EncodeQueue(clock=clock or FakeClock(), watchdog_interval=0.005)


# ---------------------------------------------------------------------------
# 串行顺序 + 原子成片
# ---------------------------------------------------------------------------
def test_serial_and_atomic(tmp_path, fake_env, monkeypatch):
    spawner = FakeSpawner([dict(lines=[b"out_time_ms=30000000"]),
                           dict(lines=[b"out_time_ms=59500000"])])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    accepted, rejected = q.enqueue_batch([mkjob(tmp_path, 1), mkjob(tmp_path, 2)])
    assert not rejected
    assert [j.id for j in accepted] == ["vid1-1", "vid2-2"]
    assert wait_until(lambda: all(j.state == "done" for j in accepted))
    # 串行：argv 顺序=入队顺序
    assert [os.path.basename(spawner.procs[0].argv[-1]),
            os.path.basename(spawner.procs[1].argv[-1])] == \
        ["vid1_hardsub.mp4.part", "vid2_hardsub.mp4.part"]
    # 原子成片：.part → os.replace，成品存在、半截零残留
    for job in accepted:
        assert Path(job.out_path).read_bytes() == b"MP4DATA"
        assert not os.path.exists(job.out_path + ".part")
        assert job.progress == 100
    assert not q.is_running()


def test_orphan_part_swept_on_enqueue(tmp_path, fake_env, monkeypatch):
    """C4：入队时同前缀 _hardsub 的孤儿 .part 清扫（豁免在跑任务）。"""
    orphan = tmp_path / "vid1_hardsub_old.mp4.part"
    orphan.write_bytes(b"stale")
    monkeypatch.setattr(eq, "_spawn_ffmpeg", FakeSpawner([dict()]))
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert wait_until(lambda: accepted[0].state == "done")
    assert not orphan.exists()


def test_progress_and_eta_update(tmp_path, fake_env, monkeypatch):
    spawner = FakeSpawner([dict(lines=[b"out_time_ms=30000000"])])  # 30s/60s=50%
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    job = accepted[0]
    assert wait_until(lambda: job.state == "done")
    snap = [s for s in q.snapshot() if s["id"] == job.id][0]
    assert snap["state"] == "done" and snap["progress"] == 100


# ---------------------------------------------------------------------------
# 取消
# ---------------------------------------------------------------------------
def test_cancel_running_and_queued(tmp_path, fake_env, monkeypatch):
    spawner = FakeSpawner([dict(lines=[b"out_time_ms=1000000"], block_after=True)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1), mkjob(tmp_path, 2)])
    assert wait_until(lambda: accepted[0].state == "running" and len(spawner.procs) == 1)
    q.cancel(None)
    assert wait_until(lambda: accepted[0].state == "cancelled"
                      and accepted[1].state == "cancelled")
    assert spawner.procs[0].killed
    assert fake_env.killed
    assert not os.path.exists(accepted[0].out_path + ".part")  # 半截零残留
    assert not q.is_running()


def test_cancel_single_queued_job(tmp_path, fake_env, monkeypatch):
    spawner = FakeSpawner([dict(lines=[b"out_time_ms=1000000"], block_after=True)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1), mkjob(tmp_path, 2)])
    assert wait_until(lambda: accepted[0].state == "running")
    q.cancel(accepted[1].id)
    assert accepted[1].state == "cancelled"
    assert accepted[0].state == "running"
    q.cancel(None)
    assert wait_until(lambda: accepted[0].state == "cancelled")


# ---------------------------------------------------------------------------
# 看门狗（假钟）
# ---------------------------------------------------------------------------
def test_watchdog_no_progress_fails(tmp_path, fake_env, monkeypatch):
    """编码相 90s 无新 out_time 行 → 树杀 + failed(显因)。"""
    spawner = FakeSpawner([dict(lines=[b"out_time_ms=1000000"], block_after=True)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    clock = FakeClock()
    q = fresh_queue(clock)
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert wait_until(lambda: accepted[0].state == "failed", clock=clock)
    assert "无进展" in accepted[0].error
    assert spawner.procs[0].killed
    assert not os.path.exists(accepted[0].out_path + ".part")


def test_finalize_phase_not_killed_before_deadline(tmp_path, fake_env, monkeypatch):
    """progress≥99 → 收尾相：deadline 内慢收尾不误杀（C5 回归钉）。"""
    spawner = FakeSpawner([dict(lines=[b"out_time_ms=60000000"],  # out==duration
                                block_after=True)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    clock = FakeClock()
    q = fresh_queue(clock)
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    job = accepted[0]
    assert wait_until(lambda: job.progress >= 99, clock=clock)
    clock.advance(60.0)  # 收尾相内 60s < deadline 120s：不得杀
    time.sleep(0.05)
    assert job.state == "running"
    spawner.procs[0].release()  # 放行收尾 → 正常成片
    assert wait_until(lambda: job.state == "done", clock=clock)
    assert not fake_env.killed


def test_finalize_phase_timeout_independent(tmp_path, fake_env, monkeypatch):
    """收尾超时独立于 90s 表判（deadline=max(120, 字节/40MBps)）。"""
    spawner = FakeSpawner([dict(lines=[b"out_time_ms=60000000"], block_after=True)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    clock = FakeClock()
    q = fresh_queue(clock)
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    job = accepted[0]
    assert wait_until(lambda: job.progress >= 99, clock=clock)
    assert wait_until(lambda: job.state == "failed", clock=clock)
    assert "收尾超时" in job.error
    assert spawner.procs[0].killed


def test_total_timeout_fires(tmp_path, fake_env, monkeypatch):
    """总超时（C2）：持续有进展仍受 duration×max(speed×4,2) 上限约束。"""
    spawner = FakeSpawner([dict(infinite=True)])  # 永远有 out_time 行=永不触发 90s 表
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    clock = FakeClock()
    q = fresh_queue(clock)
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    job = accepted[0]
    assert wait_until(lambda: job.state == "failed", clock=clock, timeout=15.0)
    assert "超时" in job.error and "无进展" not in job.error
    assert spawner.procs[0].killed


# ---------------------------------------------------------------------------
# 失败与 .part 清理
# ---------------------------------------------------------------------------
def test_ffmpeg_failure_cleans_part(tmp_path, fake_env, monkeypatch):
    """rc=1 且已写半截 .part → failed + finally 清 .part。"""
    spawner = FakeSpawner([dict(rc=1, write_part=True)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert wait_until(lambda: accepted[0].state == "failed")
    assert "退出码" in accepted[0].error
    assert not os.path.exists(accepted[0].out_path + ".part")
    assert not os.path.exists(accepted[0].out_path)


def test_missing_output_reported_failed(tmp_path, fake_env, monkeypatch):
    spawner = FakeSpawner([dict(rc=0, write_part=False)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert wait_until(lambda: accepted[0].state == "failed")
    assert "产物缺失" in accepted[0].error


def test_supply_missing_rejects(tmp_path, monkeypatch):
    monkeypatch.setattr(eq, "resolve_hardsub_ffmpeg",
                        lambda *a, **k: fsup.SupplyResult("", "", {}, ["缺 libass"]))
    q = fresh_queue()
    accepted, rejected = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert accepted == []
    assert len(rejected) == 1
    assert "能力不足" in rejected[0][1]
    assert q.snapshot() == []  # 拒者不进历史


# ---------------------------------------------------------------------------
# 磁盘预检（fail-closed，整批拒）
# ---------------------------------------------------------------------------
def test_disk_preflight_rejects_whole_batch(tmp_path, fake_env, monkeypatch):
    monkeypatch.setattr(eq.shutil, "disk_usage", lambda p: SimpleNamespace(free=1024))
    q = fresh_queue()
    accepted, rejected = q.enqueue_batch([mkjob(tmp_path, 1), mkjob(tmp_path, 2)])
    assert accepted == []
    assert len(rejected) == 2
    assert "磁盘空间不足" in rejected[0][1]
    assert q.snapshot() == []


def test_disk_preflight_oserror_rejects(tmp_path, fake_env, monkeypatch):
    def boom(p):
        raise OSError("volume gone")
    monkeypatch.setattr(eq.shutil, "disk_usage", boom)
    q = fresh_queue()
    accepted, rejected = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert accepted == []
    assert "fail-closed" in rejected[0][1]


def test_estimate_output_bytes_c3():
    """C3：CRF 模式取 max(VBR 参考表派生, 源码率×1.1)。"""
    params = hardsub.EncodeParams(video_format="h264", quality="balanced",
                                  rate_mode="quality_tier")
    # 源码率×1.1 更大：4Mbps×60s×1.1=33MB；VBR 表 (5500+128)k×60s≈42.2MB
    est = eq.estimate_output_bytes(params, 4_000_000, 60.0)
    assert est == int((5500 + 128) * 1000 / 8 * 60.0)
    # 源码率更大：8Mbps×60s×1.1=66MB > VBR 派生
    est_hi = eq.estimate_output_bytes(params, 8_000_000, 60.0)
    assert est_hi == int(8_000_000 / 8 * 60.0 * 1.1)


# ---------------------------------------------------------------------------
# 互斥原语（D2）
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_mutex():
    eq._encode_active = False
    eq._translate_running = False
    yield
    eq._encode_active = False
    eq._translate_running = False


def test_mutex_claim_release_semantics():
    assert eq.claim_encode_slot() is True
    assert eq.claim_encode_slot() is False  # 二次占用拒
    eq.release_encode_slot()
    assert eq.claim_encode_slot() is True
    eq.release_encode_slot()


def test_mutex_translate_side_blocks_encode():
    """翻译运行中（_translate_running 同锁置位）→ encode claim 拒。"""
    eq._translate_running = True
    assert eq.claim_encode_slot() is False
    assert eq.is_encode_slot_free() is False
    eq._translate_running = False
    assert eq.is_encode_slot_free() is True


def test_on_idle_fires_once_after_queue_drains(tmp_path, fake_env, monkeypatch):
    """队列排空触发 on_idle 恰一次（api 层接互斥槽归还）。"""
    monkeypatch.setattr(eq, "_spawn_ffmpeg", FakeSpawner([dict(rc=0)]))
    q = fresh_queue()
    calls = []
    q.on_idle = lambda: calls.append(1)
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert wait_until(lambda: accepted[0].state == "done")
    assert wait_until(lambda: len(calls) == 1)
    time.sleep(0.05)
    assert len(calls) == 1


def test_gpu_explicit_unavailable_fails_and_auto_falls_cpu(tmp_path, fake_env,
                                                           monkeypatch):
    """批2 GPU 分支：显式 gpu 不可用=显因拒绝；auto 回落 CPU 跑通。"""
    fake_ff = tmp_path / "ff.exe"
    fake_ff.write_bytes(b"x")   # 真实存在→can_probe_gpu 通过（解析本身被桩）
    monkeypatch.setattr(eq, "resolve_hardsub_ffmpeg",
                        lambda *a, **k: fsup.SupplyResult(
                            ffmpeg_path=str(fake_ff), ffprobe_path=str(fake_ff),
                            capability={}, missing=[]))
    monkeypatch.setattr(eq, "resolve_gpu_encoder",
                        lambda *a, **k: ("", ["h264_nvenc: 试编码失败（x）"]))
    spawner = FakeSpawner([dict(rc=0), dict(rc=0)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    job = mkjob(tmp_path, 1, backend="gpu")
    acc, _ = q.enqueue_batch([job])
    assert wait_until(lambda: acc[0].state == "failed")
    assert "GPU 编码不可用" in acc[0].error
    assert spawner.procs == []   # 未起进程即拒
    # auto：GPU 不可用回落 CPU 正常完成
    q2 = fresh_queue()
    job2 = mkjob(tmp_path, 2, backend="auto")
    acc2, _ = q2.enqueue_batch([job2])
    assert wait_until(lambda: acc2[0].state == "done")


def test_gpu_auto_prefers_gpu_and_notes(tmp_path, fake_env, monkeypatch):
    """auto+GPU 可用：走 GPU 编码器且 note 透出选择。"""
    fake_ff = tmp_path / "ff2.exe"
    fake_ff.write_bytes(b"x")
    monkeypatch.setattr(eq, "resolve_hardsub_ffmpeg",
                        lambda *a, **k: fsup.SupplyResult(
                            ffmpeg_path=str(fake_ff), ffprobe_path=str(fake_ff),
                            capability={}, missing=[]))
    monkeypatch.setattr(eq, "resolve_gpu_encoder",
                        lambda *a, **k: ("h264_nvenc", []))
    spawner = FakeSpawner([dict(rc=0)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    job = mkjob(tmp_path, 3, backend="auto")
    acc, _ = q.enqueue_batch([job])
    assert wait_until(lambda: acc[0].state == "done")
    assert "h264_nvenc" in spawner.procs[0].argv
    assert "硬件编码" in acc[0].note


# ---------------------------------------------------------------------------
# retry / snapshot / id
# ---------------------------------------------------------------------------
def test_retry_requeues_failed_job(tmp_path, fake_env, monkeypatch):
    spawner = FakeSpawner([dict(rc=1, write_part=False), dict(rc=0)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert wait_until(lambda: accepted[0].state == "failed")
    new_id = q.retry(accepted[0].id)
    assert new_id is not None and new_id != accepted[0].id
    assert wait_until(lambda: any(s["state"] == "done" for s in q.snapshot()))
    assert spawner.procs[0].argv[-1].endswith(".part")
    assert len(spawner.procs) == 2  # 重试=新 FakeProc 入队尾


def test_retry_rejects_done_or_unknown():
    pass  # 由 test_retry_unretryable 覆盖


def test_retry_unretryable(tmp_path, fake_env, monkeypatch):
    monkeypatch.setattr(eq, "_spawn_ffmpeg", FakeSpawner([dict(rc=0)]))
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert wait_until(lambda: accepted[0].state == "done")
    assert q.retry(accepted[0].id) is None  # done 不可重试
    assert q.retry("no-such-id") is None


def test_snapshot_json_serializable(tmp_path, fake_env, monkeypatch):
    monkeypatch.setattr(eq, "_spawn_ffmpeg", FakeSpawner([dict()]))
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert wait_until(lambda: accepted[0].state in ("done", "failed"))
    snaps = q.snapshot()
    assert snaps and snaps[0]["state"] in ("done", "failed")
    payload = json.dumps(snaps)  # 全结构可序列化
    assert json.loads(payload)[0]["id"] == snaps[0]["id"]


def test_retry_after_cancel_runs_again(tmp_path, fake_env, monkeypatch):
    """黑盒 DoD ③：失败/取消 → 行内重试成功。"""
    spawner = FakeSpawner([dict(lines=[b"out_time_ms=1000000"], block_after=True),
                           dict(rc=0)])
    monkeypatch.setattr(eq, "_spawn_ffmpeg", spawner)
    q = fresh_queue()
    accepted, _ = q.enqueue_batch([mkjob(tmp_path, 1)])
    assert wait_until(lambda: accepted[0].state == "running")
    q.cancel(accepted[0].id)
    assert wait_until(lambda: accepted[0].state == "cancelled")
    new_id = q.retry(accepted[0].id)
    assert new_id is not None
    assert wait_until(lambda: any(s["id"] == new_id and s["state"] == "done"
                                  for s in q.snapshot()))
