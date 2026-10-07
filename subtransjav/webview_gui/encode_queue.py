"""硬字幕压制串行队列与看门狗（2.8.0 批1 件3，D2026-1007-03）。

单例 EncodeQueue：daemon worker 串行消费 EncodeJob，逐 job 走
「探测→构建 argv→Popen→进度解析→看门狗→原子成片」全链。

关键语义（批清单裁定，改动须回评议）：
- 看门狗：编码相 90s 无新 out_time 行即树杀 failed（C2：看门狗为主）；
  progress≥99 或 out_time≥duration 后停看门狗表、进入收尾相——收尾
  deadline 独立 = max(120s, 预计输出字节/40MBps)（C5，faststart 收尾
  对大文件显著慢于编码相节奏，不得沿用 90s 表误杀）。
- 总超时：duration×max(speed_factor×4, 2) 与 duration×3+120 取大
  （C2：AV1 下限系数×4→统一安全系数；speed_factor 为 spike 冻结表）。
- 原子成片：ffmpeg 经 params.out_path 直写 ``<out>.part``，rc==0 且
  .part 非空才 os.replace 成片；异常/取消/超时 finally 清 .part（48h
  审计③「半截件当 cache」教训）；入队时同前缀 .part 孤儿清扫（C4）。
- 磁盘预检 fail-closed：入队时逐 job 估算，不足整批拒（返回 rejected）。
- 双向互斥（D2 单一状态源）：encode/translate 共用 encode_translate_mutex
  做 check-and-set；api.start_translation 须以同锁实现 claim_translate_slot
  （check-and-set _translate_running）——api 层接线在下一批（件4）。

不做（批3）：队列持久化、并行、自动化入队。
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field, replace
from typing import Any

from subtransjav.refine import hardsub
from subtransjav.refine.ffmpeg_supply import (
    FfprobeError,
    MediaInfo,
    SupplyResult,
    probe_media,
    resolve_hardsub_ffmpeg,
)
from subtransjav.utils.subprocess_flags import CREATE_NO_WINDOW  # 窗口标志单一来源（批0）

__all__ = [
    "EncodeJob",
    "EncodeQueue",
    "claim_encode_slot",
    "claim_translate_slot",
    "encode_active",
    "estimate_output_bytes",
    "get_encode_queue",
    "is_encode_slot_free",
    "release_encode_slot",
    "release_translate_slot",
]

_NO_PROGRESS_TIMEOUT_S = 90.0        # 看门狗：编码相无新 out_time 的容忍窗
_FINALIZE_MIN_DEADLINE_S = 120.0     # C5：收尾相 deadline 下限
_FINALIZE_BYTES_PER_S = 40_000_000   # C5：40MB/s 收尾吞吐（faststart 重排）
_DISK_HEADROOM_BYTES = 200 * 1024 * 1024  # 预检裕量（faststart 收尾峰值等）
_DISK_OVERHEAD_RATIO = 1.2
_STDERR_TAIL_CHARS = 800
_WAIT_PROC_TIMEOUT_S = 30.0


# ---------------------------------------------------------------------------
# 双向互斥原语（D2 单一状态源：encode/translate 两态同一把锁 check-and-set）
# ---------------------------------------------------------------------------

encode_translate_mutex = threading.Lock()
_encode_active = False
_translate_running = False  # 翻译侧置位/复位由 api 层 claim_translate_slot 同款实现（下一批接线）


def claim_encode_slot() -> bool:
    """占用编码互斥槽（翻译运行中或已被占用即拒）。api 层 encode_commit 前调用。"""
    global _encode_active
    with encode_translate_mutex:
        if _encode_active or _translate_running:
            return False
        _encode_active = True
        return True


def release_encode_slot() -> None:
    """释放编码互斥槽（队列全终态后由 api 层调用）。"""
    global _encode_active
    with encode_translate_mutex:
        _encode_active = False


def is_encode_slot_free() -> bool:
    """互斥状态查询（翻译侧 start_translation 预检用，非占用）。"""
    with encode_translate_mutex:
        return not (_encode_active or _translate_running)


def encode_active() -> bool:
    """编码侧占用查询（翻译侧互斥文案分型用，不判翻译自身）。"""
    with encode_translate_mutex:
        return _encode_active


def claim_translate_slot() -> bool:
    """占用翻译互斥槽（D2 单一状态源：与 encode 侧同锁 check-and-set）。

    api.start_translation 在进程哨兵置位后调用；返回 False=压制运行中
    或翻译已在启动序（后者 api 层先经 _translate_process 检查，此处兜底）。
    """
    global _translate_running
    with encode_translate_mutex:
        if _encode_active or _translate_running:
            return False
        _translate_running = True
        return True


def release_translate_slot() -> None:
    """释放翻译互斥槽（幂等）：start 失败/取消/终态消费时调用。"""
    global _translate_running
    with encode_translate_mutex:
        _translate_running = False


# ---------------------------------------------------------------------------
# 任务模型
# ---------------------------------------------------------------------------


@dataclass
class EncodeJob:
    """单个压制任务；params.out_path 由队列改写为 .part 后用于构建 argv。"""

    video_path: str
    subtitle_path: str
    params: hardsub.EncodeParams
    out_path: str
    id: str = ""                              # 视频 stem+序号，入队时赋值
    state: str = "queued"                     # queued/running/done/failed/cancelled
    progress: int = 0                         # 0-100（编码相封顶 99，成片后 100）
    eta_s: float = 0.0
    error: str = ""
    note: str = ""                            # 非致命提示（音频 copy 回落原因等，透出 UI）
    created_at: float = field(default_factory=time.time)
    probe: MediaInfo | None = field(default=None, repr=False, compare=False)  # 入队探测缓存
    estimated_bytes: int = 0                  # 收尾相 deadline / 磁盘预检派生用

    def snapshot(self) -> dict:
        """json 可序列化快照（api 轮询用）。"""
        return {
            "id": self.id,
            "video_path": self.video_path,
            "subtitle_path": self.subtitle_path,
            "out_path": self.out_path,
            "state": self.state,
            "progress": self.progress,
            "eta_s": round(self.eta_s, 1),
            "error": self.error,
            "note": self.note,
            "created_at": self.created_at,
            "params": asdict(self.params),
        }


def estimate_output_bytes(params: hardsub.EncodeParams, bit_rate_bps: int,
                          duration_s: float) -> int:
    """产物体积估算（C3）：VBR 模式=参考表视频码率+音频 128k；CRF 模式取
    max(VBR 参考表派生, 源码率×duration×1.1)。"""
    ref_kbps = hardsub.reference_bitrate_kbps(
        params.video_format, params.resolution, params.quality)
    vbr_bytes = (ref_kbps + 128) * 1000 / 8 * max(0.0, duration_s)
    if params.rate_mode != "quality_tier":
        return int(vbr_bytes)
    src_bytes = max(0, bit_rate_bps) / 8 * max(0.0, duration_s) * 1.1
    return int(max(vbr_bytes, src_bytes))


# ---------------------------------------------------------------------------
# 子进程封装（模块级函数，测试经 monkeypatch 注入 fake，不触真 ffmpeg）
# ---------------------------------------------------------------------------


def _spawn_ffmpeg(argv: list[str]) -> subprocess.Popen:
    """list-args + CREATE_NO_WINDOW；stdout 收 -progress 行、stderr 排空。"""
    return subprocess.Popen(
        argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        shell=False, creationflags=CREATE_NO_WINDOW)  # windowed 防黑框（批0）


def _kill_tree(proc: subprocess.Popen) -> None:
    """进程树击杀；任何异常都降级单杀兜底，绝不阻断状态收口。"""
    try:
        from subtransjav.utils import process_manager
        result = process_manager.terminate_process_tree(proc.pid)
        if not result.get("success"):
            proc.kill()
    except Exception:  # noqa: BLE001  树杀兜底：重复杀/已死进程无害
        with contextlib.suppress(Exception):
            proc.kill()


def _wait_proc(proc: subprocess.Popen, timeout: float) -> int:
    """限時等待退出；超时树杀后再兜底取码（永不抛 TimeoutExpired）。"""
    try:
        return proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        _kill_tree(proc)
        try:
            return proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            return proc.returncode if proc.returncode is not None else -1


def _drain_stderr(proc: subprocess.Popen, box: dict) -> None:
    """stderr 排空线程：只留尾 800 字符供失败诊断。"""
    tail = ""
    if proc.stderr is None:
        return
    try:
        for raw in proc.stderr:
            tail += raw.decode("utf-8", "replace")
            if len(tail) > _STDERR_TAIL_CHARS:
                tail = tail[-_STDERR_TAIL_CHARS:]
    except Exception:  # noqa: BLE001  排空失败不影响主流程
        pass
    box["stderr_tail"] = tail


# ---------------------------------------------------------------------------
# 队列
# ---------------------------------------------------------------------------


class EncodeQueue:
    """串行压制队列。``clock``/``watchdog_interval`` 仅供测试注入假钟。"""

    def __init__(self, clock: Callable[[], float] = time.monotonic,
                 watchdog_interval: float = 0.5):
        self._clock = clock
        self._watchdog_interval = watchdog_interval
        self._cond = threading.Condition(threading.RLock())
        self._pending: list[EncodeJob] = []
        self._history: list[EncodeJob] = []       # 全终态/在队任务快照源（只增）
        self._current: EncodeJob | None = None
        self._current_box: dict | None = None
        self._current_proc: subprocess.Popen | None = None
        self._worker: threading.Thread | None = None
        self._seq = 0
        self._supply: SupplyResult | None = None
        self._stop = False
        # 队列空闲回调（api 层接 release_encode_slot 做互斥槽自动归还；
        # worker 收尾发现无 pending 时触发一次，异常被吞不回传队列）
        self.on_idle: Callable[[], None] | None = None

    # -- 供给 ----------------------------------------------------------------

    def _ensure_supply(self) -> SupplyResult:
        if self._supply is None:
            self._supply = resolve_hardsub_ffmpeg()
        return self._supply

    def reset_supply(self) -> None:
        """供给缓存失效（ffmpeg 按需下载成功落位后由 api 层调用，下轮重解析）。"""
        self._supply = None

    # -- 入队 ----------------------------------------------------------------

    def enqueue_batch(
        self, jobs: list[EncodeJob],
    ) -> tuple[list[EncodeJob], list[tuple[EncodeJob, str]]]:
        """批量入队：逐 job 磁盘预检（fail-closed），返回 (accepted, rejected)。

        rejected 为 (job, 人话原因) 列表；整批内逐 job 独立判定，不足者拒、
        足者入队尾。入队同时做同前缀 .part 孤儿清扫（C4）。
        """
        accepted: list[EncodeJob] = []
        rejected: list[tuple[EncodeJob, str]] = []
        supply = self._ensure_supply()
        for job in jobs:
            if supply.missing:
                rejected.append((job, "ffmpeg 能力不足：" + "；".join(supply.missing)))
                continue
            try:
                info = job.probe or probe_media(supply.ffprobe_path, job.video_path)
            except FfprobeError as e:
                rejected.append((job, f"媒体探测失败：{e}"))
                continue
            if info.duration_s <= 0:
                rejected.append((job, "媒体时长无效"))
                continue
            job.probe = info
            job.estimated_bytes = estimate_output_bytes(
                job.params, info.bit_rate_bps, info.duration_s)
            need = int(job.estimated_bytes * _DISK_OVERHEAD_RATIO) + _DISK_HEADROOM_BYTES
            out_dir = os.path.dirname(job.out_path) or "."
            try:
                free = shutil.disk_usage(out_dir).free
            except OSError:
                rejected.append((job, "磁盘空间信息不可得（fail-closed）"))
                continue
            if free < need:
                rejected.append((job, (
                    f"磁盘空间不足：约需 {need // (1024 * 1024)}MB，"
                    f"当前仅剩 {free // (1024 * 1024)}MB")))
                continue
            accepted.append(job)

        with self._cond:
            for job in accepted:
                self._seq += 1
                stem = os.path.splitext(os.path.basename(job.video_path))[0]
                job.id = f"{stem}-{self._seq}"
                # 原子成片：ffmpeg 直写 .part（同卷 os.replace）
                job.params.out_path = job.out_path + ".part"
                job.state = "queued"
                self._pending.append(job)
                self._history.append(job)
                self._cleanup_orphan_parts(
                    os.path.dirname(job.out_path) or ".", f"{stem}_hardsub")
            if accepted:
                self._ensure_worker_locked()
            self._cond.notify_all()
        return accepted, rejected

    def _ensure_worker_locked(self) -> None:
        if self._worker is None or not self._worker.is_alive():
            self._worker = threading.Thread(
                target=self._worker_loop, name="encode-queue-worker", daemon=True)
            self._worker.start()

    def _cleanup_orphan_parts(self, out_dir: str, prefix: str) -> None:
        """同前缀 .part 孤儿清扫（C4）：崩溃/中断残留的半截件不入 cache。
        仅豁免当前在跑任务的 .part（排队中任务尚未起写，无需豁免）。"""
        protected: set[str] = set()
        if self._current is not None:
            protected.add(os.path.normpath(self._current.params.out_path))
        try:
            names = os.listdir(out_dir)
        except OSError:
            return
        for name in names:
            if not (name.startswith(prefix) and name.endswith(".part")):
                continue
            full = os.path.normpath(os.path.join(out_dir, name))
            if full in protected:
                continue
            with contextlib.suppress(OSError):
                os.unlink(full)

    # -- worker ----------------------------------------------------------------

    def _worker_loop(self) -> None:
        while True:
            with self._cond:
                while not self._pending and not self._stop:
                    self._cond.wait(timeout=0.5)
                if self._stop and not self._pending:
                    return
                job = self._pending.pop(0)
                job.state = "running"
                self._current = job
            try:
                self._run_job(job)
            except Exception as e:  # noqa: BLE001  worker 兜底：任何异常收口为 failed
                job.state = "failed"
                job.error = str(e)
            finally:
                with self._cond:
                    self._current = None
                    self._current_box = None
                    self._current_proc = None
                    idle = not self._pending and not self._stop
            if idle and self.on_idle is not None:
                with contextlib.suppress(Exception):
                    self.on_idle()

    def _fail(self, job: EncodeJob, reason: str) -> None:
        job.state = "failed"
        job.error = reason

    def _run_job(self, job: EncodeJob) -> None:
        supply = self._ensure_supply()
        info = job.probe
        if info is None:
            try:
                info = probe_media(supply.ffprobe_path, job.video_path)
            except FfprobeError as e:
                self._fail(job, f"媒体探测失败：{e}")
                return
        try:
            args, fall_reason = hardsub.build_ffmpeg_args(
                job.params, job.video_path, job.subtitle_path, info.duration_s,
                info.has_audio, info.audio_codec)
        except ValueError as e:  # 含 BannedFlagError（逃生门黑名单）
            self._fail(job, f"参数构建失败：{e}")
            return
        if fall_reason:
            job.note = fall_reason  # C6：回落原因透出 UI

        speed = hardsub.speed_factor(job.params.video_format, job.params.quality)
        duration = info.duration_s
        # C2 总超时：统一安全系数 max(speed×4, 2)，与固定下限 duration×3+120 取大
        total_timeout = max(duration * 3 + 120.0, duration * max(speed * 4.0, 2.0))
        # C5 收尾 deadline：max(120s, 预计输出字节/40MBps)
        finalize_deadline = max(_FINALIZE_MIN_DEADLINE_S,
                                job.estimated_bytes / _FINALIZE_BYTES_PER_S)
        box: dict[str, Any] = {
            "last": self._clock(), "phase": "encode",
            "fin_start": 0.0, "fin_deadline": finalize_deadline,
            "cancel": False, "reason": "", "stderr_tail": "",
            "wake": threading.Event(),
        }
        with self._cond:
            self._current_box = box
        try:
            proc = _spawn_ffmpeg([supply.ffmpeg_path, *args])
        except OSError as e:
            self._fail(job, f"ffmpeg 启动失败：{e}")
            return
        with self._cond:
            self._current_proc = proc

        threading.Thread(target=_drain_stderr, args=(proc, box), daemon=True).start()
        threading.Thread(target=self._watchdog, args=(proc, box, total_timeout),
                         daemon=True).start()

        assert proc.stdout is not None
        for raw in proc.stdout:
            line = raw.decode("utf-8", "replace").strip()
            if not line.startswith("out_time_ms="):
                continue
            try:
                out_us = float(line.split("=", 1)[1])
            except ValueError:
                continue  # ffmpeg -progress 还有 frame/fps 等行与空行
            out_s = max(0.0, out_us / 1_000_000.0)  # out_time_ms 实为微秒（先例口径）
            box["last"] = self._clock()
            if duration > 0:
                raw_pct = out_s / duration * 100.0
                job.progress = min(99, int(raw_pct))
                job.eta_s = max(0.0, (duration - out_s) * speed)
                if raw_pct >= 99.0 or out_s >= duration:
                    # C5：停看门狗表→收尾相（fin_start 先置位防 watchdog 读到半态）
                    box["fin_start"] = self._clock()
                    box["phase"] = "finalize"

        rc = _wait_proc(proc, _WAIT_PROC_TIMEOUT_S)
        box["wake"].set()

        part_path = job.params.out_path
        if box["cancel"]:
            job.state = "cancelled"
        elif box["reason"]:
            job.state = "failed"
            job.error = box["reason"]
        elif rc == 0 and os.path.isfile(part_path) and os.path.getsize(part_path) > 0:
            os.replace(part_path, job.out_path)  # 同卷原子成片
            job.state = "done"
            job.progress = 100
            job.eta_s = 0.0
        elif rc == 0:
            self._fail(job, "ffmpeg 退出码 0 但产物缺失")
        else:
            tail = (box["stderr_tail"] or "").strip()[-200:]
            self._fail(job, f"ffmpeg 退出码 {rc}" + (f"：{tail}" if tail else ""))

        if job.state != "done":  # finally 语义：非成片一律清 .part（半截零残留）
            with contextlib.suppress(OSError):
                if os.path.isfile(part_path):
                    os.unlink(part_path)

    def _watchdog(self, proc: subprocess.Popen, box: dict, total_timeout: float) -> None:
        start = self._clock()
        while proc.poll() is None:
            now = self._clock()
            if box["cancel"]:
                return
            if now - start > total_timeout:
                box["reason"] = "编码超时"
                _kill_tree(proc)
                return
            if box["phase"] == "encode":
                if now - box["last"] > _NO_PROGRESS_TIMEOUT_S:
                    box["reason"] = "编码无进展（90 秒）"
                    _kill_tree(proc)
                    return
            elif now - box["fin_start"] > box["fin_deadline"]:
                box["reason"] = "收尾超时"
                _kill_tree(proc)
                return
            box["wake"].wait(self._watchdog_interval)

    # -- 控制 ------------------------------------------------------------------

    def cancel(self, job_id: str | None = None) -> None:
        """取消：None=当前 running 树杀+清空 queued；指定 id=取消该项。"""
        target: EncodeJob | None = None
        with self._cond:
            if job_id is None:
                for j in self._pending:
                    j.state = "cancelled"
                self._pending.clear()
                target = self._current
            else:
                pending_hit = next((j for j in self._pending if j.id == job_id), None)
                if pending_hit is not None:
                    pending_hit.state = "cancelled"
                    self._pending.remove(pending_hit)
                    return
                if self._current is not None and self._current.id == job_id:
                    target = self._current
                else:
                    return
            box = self._current_box if target is self._current else None
            proc = self._current_proc if target is self._current else None
        if target is not None and box is not None:
            box["cancel"] = True
            box["wake"].set()
            if proc is not None:
                _kill_tree(proc)

    def retry(self, job_id: str) -> str | None:
        """failed/cancelled 任务按原参数复制入队尾；返回新 id，不可重试返回 None。"""
        with self._cond:
            orig = next((j for j in self._history
                         if j.id == job_id and j.state in ("failed", "cancelled")), None)
            if orig is None:
                return None
            self._seq += 1
            stem = os.path.splitext(os.path.basename(orig.video_path))[0]
            fresh = replace(orig, id=f"{stem}-{self._seq}", state="queued",
                            progress=0, eta_s=0.0, error="", note="",
                            created_at=time.time())
            self._pending.append(fresh)
            self._history.append(fresh)
            self._ensure_worker_locked()
            self._cond.notify_all()
            return fresh.id

    def snapshot(self) -> list[dict]:
        with self._cond:
            return [j.snapshot() for j in self._history]

    def is_running(self) -> bool:
        with self._cond:
            return self._current is not None or bool(self._pending)


# ---------------------------------------------------------------------------
# 单例
# ---------------------------------------------------------------------------

_queue_lock = threading.Lock()
_singleton: EncodeQueue | None = None


def get_encode_queue() -> EncodeQueue:
    """模块级单例（GUI 进程内全生命周期；无持久化——批3）。"""
    global _singleton
    with _queue_lock:
        if _singleton is None:
            _singleton = EncodeQueue()
        return _singleton
