"""CPS（每秒字符数）分布观测：逐份 SRT 统计条目语速分布（v1.4 批次 1b-C4）
================================================================================

用途：对一份或多份 SRT 逐条计算 CPS（去空白字符数 / 时长秒），输出
per-file 与全局分布（count/mean/p50/p90/p95/max、超阈计数），供日文
语速定标调研；可选 --telemetry 接 ASR 场景遥测按 scene 聚合 CPS 均值。

用法：
    python tools/cps_distribution.py a.srt b.srt [--json] [--telemetry PATH]

口径免责声明（与 subtransjav.refine.quality_report【语速与间隙观测】
同源，阈值勿单改）：
- CPS = 条目文本去全部空白后的字符数 / 条目时长（秒）；
- CJK 为主（ord(c)>0x2E80 字符占比 ≥50%）基准 8、其他基准 20，容差
  ×1.15，超阈计数按各自基准严格大于判定；
- 时长无效（时间轴解析失败）、时长 ≤0、空文本的条目跳过（skipped）不入
  分布；时长 <0.5s 的超短条目（skipped_short，D5c 最小时长门槛）即使
  CPS 爆表也不入分布；
- 遥测场景无时间码：按 audio_duration_s 升序累计窗口 [start, end) 把
  条目中点近似归属场景（场景间空隙不计），仅作调研参考；
- 纯只读观测：不写任何文件、不触发重翻。
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from subtransjav.refine.asr_meta import load_asr_telemetry  # noqa: E402
from subtransjav.refine.config import RefineConfig  # noqa: E402
from subtransjav.refine.filters import parse_srt  # noqa: E402
from subtransjav.refine.v2_premerge import _timing_span  # noqa: E402

# CPS 阈值常量（与 quality_report._CPS_* 同值；test_cps_distribution 钉等值）
CPS_CJK_BASE = 8.0
CPS_OTHER_BASE = 20.0
CPS_TOLERANCE = 1.15
# D5c：CPS 最小时长门槛——时长 <0.5s 的超短条目即使爆表也不入分布
# （与 quality_report._CPS_MIN_DURATION_S 等值，test_cps_distribution 钉等值），
# 单独计入 skipped_short，不与无效跳过（skipped）混淆。
CPS_MIN_DURATION_S = 0.5

DISCLAIMER = (
    "注：CPS 为'去空白字符数/时长秒'观测口径；场景归属按遥测时长累计窗口"
    "近似。本工具为只读调研，不触发重翻。"
)


# ---------------------------------------------------------------- 单条口径

def _cjk_dominant(compact: str) -> bool:
    """CJK 为主判定：ord>0x2E80 字符占比 ≥50%（按去空白文本计）。"""
    if not compact:
        return False
    n = sum(1 for c in compact if ord(c) > 0x2E80)
    return n / len(compact) >= 0.5


def entry_stats(text: str, timing: str) -> tuple[float, float] | None:
    """单条 → (CPS, 该条超阈判定上限)；跳过口径返回 None。

    跳过：空文本 / 时间轴解析失败 / 时长 < CPS_MIN_DURATION_S（D5c 最小
    时长门槛，含 ≤0；与 quality_report 同口径）。
    """
    compact = "".join((text or "").split())
    if not compact:
        return None
    s0, e0 = _timing_span(timing)
    dur = e0 - s0
    if s0 < 0 or dur < CPS_MIN_DURATION_S:
        return None
    base = CPS_CJK_BASE if _cjk_dominant(compact) else CPS_OTHER_BASE
    return len(compact) / dur, base * CPS_TOLERANCE


# ---------------------------------------------------------------- 统计

def _percentile(sorted_vals: list[float], q: float) -> float:
    """最近秩百分位（ceil(q% × n) - 1，越界钳到末位）。"""
    n = len(sorted_vals)
    idx = min(max(0, math.ceil(q / 100 * n) - 1), n - 1)
    return sorted_vals[idx]


def summarize_stats(values: list[float]) -> dict:
    """分布摘要 count/mean/p50/p90/p95/max；空样本 count=0、其余 None。"""
    if not values:
        return {"count": 0, "mean": None, "p50": None, "p90": None,
                "p95": None, "max": None}
    sv = sorted(values)
    return {"count": len(sv), "mean": sum(sv) / len(sv),
            "p50": _percentile(sv, 50.0), "p90": _percentile(sv, 90.0),
            "p95": _percentile(sv, 95.0), "max": sv[-1]}


def collect_file(path: Path) -> tuple[list[float], int, int, int,
                                      list[tuple[float, float]]]:
    """解析单份 SRT → (cps 列表, 超阈条数, 无效跳过条数, 超短跳过条数,
    场景归属行)。

    无效跳过（skipped）= 空文本/时间轴解析失败/时长 ≤0；超短跳过
    （skipped_short，D5c）= 0 < 时长 < CPS_MIN_DURATION_S（即使 CPS 爆表
    也不入分布）。场景归属行为 (条目中点秒, cps)，供 --telemetry 场景
    聚合用。
    """
    cps_values: list[float] = []
    scene_rows: list[tuple[float, float]] = []
    over = 0
    skipped = 0
    skipped_short = 0
    for e in parse_srt(path.read_text(encoding="utf-8", errors="replace")):
        text = e.get("text") or ""
        timing = e.get("timing") or ""
        st = entry_stats(text, timing)
        if st is None:
            compact = "".join(text.split())
            s0, e0 = _timing_span(timing)
            dur = e0 - s0
            if compact and s0 >= 0 and 0 < dur < CPS_MIN_DURATION_S:
                skipped_short += 1
            else:
                skipped += 1
            continue
        cps, limit = st
        cps_values.append(cps)
        if cps > limit:
            over += 1
        s0, e0 = _timing_span(timing)
        scene_rows.append(((s0 + e0) / 2.0, cps))
    return cps_values, over, skipped, skipped_short, scene_rows


def aggregate_by_scene(scenes: dict, rows: list[tuple[float, float]]) -> dict:
    """scene→CPS 均值表（近似归属，见模块 docstring 口径）。

    scenes 为 load_asr_telemetry 的 scenes（scene→信号 dict）；rows 为
    (条目中点秒, cps)。无条目落入的场景与时长非法/≤0 的场景不出现在
    结果里。
    """
    windows: list[tuple[float, float, int]] = []
    acc = 0.0
    # scene 键防御：解析侧只产 int（bool 亦拒），非 int 键跳过不建窗口
    int_scenes = sorted(no for no in scenes
                        if isinstance(no, int) and not isinstance(no, bool))
    for no in int_scenes:
        try:
            dur = float(scenes[no].get("audio_duration_s") or 0.0)
        except (TypeError, ValueError):
            continue
        if dur <= 0:
            continue
        windows.append((acc, acc + dur, no))
        acc += dur
    per: dict[int, list[float]] = {}
    for mid, cps in rows:
        for lo, hi, no in windows:
            if lo <= mid < hi:
                per.setdefault(no, []).append(cps)
                break
    return {no: {"count": len(v), "mean": sum(v) / len(v)}
            for no, v in sorted(per.items())}


# ---------------------------------------------------------------- 输出

def _dist_line(stats: dict) -> str:
    if not stats["count"]:
        return "  CPS 分布: 无有效条目"
    return (f"  CPS 分布: mean={stats['mean']:.2f} "
            f"p50={stats['p50']:.2f} p90={stats['p90']:.2f}"
            f" p95={stats['p95']:.2f} max={stats['max']:.2f}")


def render_human(files: list[dict], overall: dict,
                 scenes: dict | None) -> str:
    """人读输出：per-file 分布 + 全局分布 +（可选）场景聚合表 + 免责声明。"""
    lines: list[str] = []
    for f in files:
        lines.append(f"== {f['file']} ==")
        lines.append(f"  条目 {f['count']} 条"
                     f"（跳过 {f['skipped']}：空文本/时长无效或 ≤0；"
                     f"超短 {f['skipped_short']}：时长 <{CPS_MIN_DURATION_S:g}s）"
                     f" | 超 CPS {f['over_threshold']} 条")
        lines.append(_dist_line(f))
    lines.append("== 全局 ==")
    lines.append(f"  条目 {overall['count']} 条"
                 f"（跳过 {overall['skipped']}；超短 {overall['skipped_short']}）"
                 f" | 超 CPS {overall['over_threshold']} 条")
    lines.append(_dist_line(overall))
    if scenes is not None:
        lines.append("场景聚合（--telemetry，按场景时长累计窗口归属）:")
        if scenes:
            for no, s in scenes.items():
                lines.append(f"  scene {no}: 条目 {s['count']} 条"
                             f" | CPS 均值 {s['mean']:.2f}")
        else:
            lines.append("  （无条目落入任何场景窗口）")
    lines.append(DISCLAIMER)
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="CPS 分布观测：逐份 SRT 统计条目语速分布"
                    "（count/mean/p50/p90/p95/max、超阈计数）。")
    ap.add_argument("srt", nargs="+", type=Path, help="SRT 文件路径（可多份）")
    ap.add_argument("--json", action="store_true", help="输出机器可读 JSON")
    ap.add_argument("--telemetry", type=Path, default=None,
                    help="ASR 场景遥测 jsonl 路径（可选，按 scene 聚合 CPS 均值）")
    args = ap.parse_args(argv)

    missing = [str(p) for p in args.srt if not p.is_file()]
    if missing:
        print(f"[cps_distribution] 文件不存在: {', '.join(missing)}",
              file=sys.stderr)
        return 2

    files: list[dict] = []
    all_cps: list[float] = []
    all_over = 0
    all_skipped = 0
    all_skipped_short = 0
    rows_for_scene: list[tuple[float, float]] = []
    for p in args.srt:
        cps_values, over, skipped, skipped_short, scene_rows = collect_file(p)
        files.append({"file": p.name, "skipped": skipped,
                      "skipped_short": skipped_short,
                      "over_threshold": over, **summarize_stats(cps_values)})
        all_cps.extend(cps_values)
        all_over += over
        all_skipped += skipped
        all_skipped_short += skipped_short
        rows_for_scene.extend(scene_rows)
    overall = {"skipped": all_skipped, "skipped_short": all_skipped_short,
               "over_threshold": all_over, **summarize_stats(all_cps)}

    scenes_out: dict | None = None
    if args.telemetry is not None:
        cfg = RefineConfig(inputs=[], asr_telemetry=str(args.telemetry))
        tele = load_asr_telemetry(cfg, "")
        if not tele.get("present"):
            print(f"[cps_distribution] asr_telemetry 不可用（路径不存在或"
                  f"解析失败），跳过场景聚合: {args.telemetry}", file=sys.stderr)
        else:
            scenes_out = aggregate_by_scene(tele.get("scenes") or {},
                                            rows_for_scene)

    if args.json:
        print(json.dumps({"files": files, "global": overall,
                          "scenes": scenes_out},
                         ensure_ascii=False, indent=2))
    else:
        print(render_human(files, overall, scenes_out))
    if not overall["count"]:
        print("[cps_distribution] 无有效条目（全部被跳过）", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
