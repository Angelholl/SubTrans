"""双 pass 覆盖合并（3.2.0 件A，D2026-1029-02 拍板①）。

纯函数、零 I/O、零新依赖：pass1（精准档）为主干**逐段全保留**；pass2
（召回档）只在 pass1 相邻段之间的空洞（含片首/片尾空区）时长超过预注册
阈值处、且**完全落在空洞界内并与 pass1 全部段零重叠**时被采纳，按 start
排序插入。越界/重叠的 pass2 段一律弃置——覆盖优先，不裁剪、不改写任何
一段文本与时间轴。

幂等：``merge(merge(p1, p2), p2) == merge(p1, p2)``（已采纳段二次合并时
因与主干重叠被排除，其余候选仍被既有规则排除）。

预注册值（阈值/召回档配置）见内部追记 d1028-40-追记-件A-pass2预注册。
"""

from __future__ import annotations

# 空洞采纳阈值（秒）：预注册值，评测门数据回呈后 owner 可调并重注册。
GAP_THRESHOLD_S = 1.0

# 双 pass 留痕 sidecar schema（asr_runner --passes 2 产物面）。
DUALPASS_SCHEMA = "subtransjav.ct2.dualpass/1"


def _overlaps(a_start: float, a_end: float,
              b_start: float, b_end: float) -> bool:
    """半开区间重叠判定（首尾相接不算重叠）。"""
    return a_start < b_end and b_start < a_end


def _gaps(main: list[dict], duration: float | None) -> list[tuple[float, float]]:
    """主干相邻段空洞（含片首/片尾空区）。

    duration 缺省（None）时片尾上界取 +inf——调用方无法给出全片时长时
    仍允许末段之后的 pass2 段参与采纳；给出 duration 时越界段自然弃置。
    """
    gaps: list[tuple[float, float]] = []
    cursor = 0.0
    for seg in main:
        start = float(seg["start"])
        end = float(seg["end"])
        if start > cursor:
            gaps.append((cursor, start))
        cursor = max(cursor, end)
    tail_end = float(duration) if duration is not None else float("inf")
    if tail_end > cursor:
        gaps.append((cursor, tail_end))
    return gaps


def merge_passes(pass1: list[dict], pass2: list[dict], *,
                 gap_threshold_s: float = GAP_THRESHOLD_S,
                 duration: float | None = None) -> list[dict]:
    """pass1 覆盖优先 + pass2 空洞补全（返回按 start 排序的段数组）。

    - pass1 段对象原样保留（同一 dict 引用，文本/时间轴零改动）；
    - 仅时长 ``> gap_threshold_s`` 的空洞参与采纳（等于阈值不填）；
    - 采纳段须完全落在空洞界内、与 pass1 全部段及已采纳段零重叠；
    - 同一空洞内多条候选按 start 排序贪心采纳，互不重叠。
    """
    main = sorted(pass1, key=lambda s: (float(s["start"]), float(s["end"])))
    usable = [(gs, ge) for gs, ge in _gaps(main, duration)
              if (ge - gs) > gap_threshold_s]

    adopted: list[dict] = []
    for seg in sorted(pass2, key=lambda s: (float(s["start"]), float(s["end"]))):
        start = float(seg["start"])
        end = float(seg["end"])
        if end < start:
            continue
        if any(_overlaps(start, end, float(m["start"]), float(m["end"]))
               for m in main):
            continue
        if not any(gs <= start and end <= ge for gs, ge in usable):
            continue
        if any(_overlaps(start, end, float(a["start"]), float(a["end"]))
               for a in adopted):
            continue
        adopted.append(seg)

    if not adopted:
        return list(pass1)
    merged = list(pass1) + adopted
    merged.sort(key=lambda s: (float(s["start"]), float(s["end"])))
    return merged


def adopted_pass2_indices(pass1: list[dict], pass2: list[dict],
                          merged: list[dict]) -> list[int]:
    """采纳映射：merged 中来自 pass2 的段下标（供 dualpass sidecar 审计）。

    按对象同一性比对（merge_passes 原样返回候选段对象），零文本比对开销。
    """
    return [i for i, seg in enumerate(pass2)
            if any(seg is m for m in merged)]
