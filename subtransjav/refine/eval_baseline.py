"""eval_baseline——正确率评测 harness（3.1.0 测量地基，D2026-1028-03）。

句级日语正确率无金标通道（评议员 [UNVERIFIABLE] 定性），本模块只产代理指标，
供每次发版/换引擎时报告涨跌，不承诺绝对正确率数值。

代理指标四件：
- hallucination_proxy：与语音窗口重叠 <30% 行时长的行占比（幻听代理）；
- omission_proxy：语音窗口时间未被任何行覆盖的占比（漏听代理）；
- agreement：双 SRT 贪婪时轴匹配（IoU≥0.5）∧文本相似≥0.6 的行占比
  （双引擎一致率=同源代理；报告须带错误归属视图——ASR 层对比源文 SRT，
  翻译层对比终稿对源文）；
- duration/cps：行数、行均时长、CPS 分位。

语音窗口复用 audio_detect 既有检测原语整片封装；诚实退化（C18 同款）：
媒体/ffmpeg 缺失或检测失败 → 窗口类指标显式 null 并带 ``__error``，
绝不当全静音。Wilson 下界原语内置（3.3.0 预注册放行门共用；公式与
tools/c22_calibration.wilson_lower_bound 同源，改动须两处联动评议）。

评测只读媒体与 SRT，不改任何产物；金标/媒体数据不进仓库（D2026-1028-01 口径）。
"""

from __future__ import annotations

import argparse
import difflib
import json
import math
import os
import pathlib
import re
from collections.abc import Callable
from datetime import datetime, timezone

from . import audio_detect
from .filters import parse_srt

__all__ = [
    "wilson_lower_bound",
    "speech_windows_full",
    "hallucination_proxy",
    "omission_proxy",
    "agreement",
    "cps_stats",
    "evaluate",
    "write_report",
    "register_engine",
    "run_engine",
    "main",
]

# Wilson 下界（预注册量化门共用原语；与 tools/c22_calibration 同公式同 z）
_WILSON_Z = 1.96


def wilson_lower_bound(successes: int, n: int, z: float = _WILSON_Z) -> float:
    """Wilson score 下界（successes/n 的置信下界；n=0 → 0.0）。"""
    if n <= 0:
        return 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


_TIMING_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def _timing_span(timing: str) -> tuple[float, float] | None:
    m = _TIMING_RE.search(timing or "")
    if not m:
        return None
    g = [int(x) for x in m.groups()]
    start = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0
    end = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000.0
    if end <= start:
        return None
    return start, end


def _overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    inter = min(a[1], b[1]) - max(a[0], b[0])
    return inter if inter > 0 else 0.0


def speech_windows_full(media_path: str) -> dict:
    """整片语音窗口 [(start_s, end_s), ...]；诚实退化 → {"__error": 原因}。

    与 audio_detect.detect_speech_windows 同原语同阈值（85 分位、10ms hop），
    区别仅在不做间隙窗口交集（评测要整片视角）。"""
    try:
        ff = audio_detect._find_ffmpeg()
        if ff is None:
            return {"__error": "未检测到 ffmpeg"}
        if not media_path or not os.path.isfile(media_path):
            return {"__error": "无媒体文件"}
        tmp_wav = audio_detect._wav_tmp_path(audio_detect._detect_temp_root(), media_path)
        try:
            audio_detect._extract_wav(ff, media_path, tmp_wav, 16000)
            _rate, rms, duration = audio_detect._hop_rms_series(tmp_wav, 10)
            threshold = audio_detect._percentile(rms, 85)
            segs = audio_detect._speech_segments(rms, threshold, 10 / 1000.0)
        finally:
            try:
                if os.path.isfile(tmp_wav):
                    os.unlink(tmp_wav)
            except OSError:
                pass
        return {"windows": [(round(s, 3), round(e, 3)) for s, e in segs],
                "duration_s": round(duration, 3)}
    except Exception as e:      # noqa: BLE001 评测窗口检测永不抛出
        return {"__error": "语音窗口检测失败: " + str(e)}


def hallucination_proxy(entries: list[dict],
                        windows: list[tuple[float, float]] | None,
                        min_overlap: float = 0.3) -> dict | None:
    """幻听代理：与语音重叠不足行时长 30% 的行占比。窗口缺失 → None。"""
    if windows is None:
        return None
    spans = []
    for e in entries:
        span = _timing_span(e.get("timing", ""))
        if span:
            spans.append(span)
    if not spans:
        return {"lines": 0, "suspect": 0, "ratio": None}
    suspect = 0
    for s0, e0 in spans:
        dur = e0 - s0
        covered = sum(_overlap((s0, e0), w) for w in windows)
        if dur > 0 and covered / dur < min_overlap:
            suspect += 1
    return {"lines": len(spans), "suspect": suspect, "ratio": round(suspect / len(spans), 4)}


def omission_proxy(entries: list[dict],
                   windows: list[tuple[float, float]] | None) -> dict | None:
    """漏听代理：语音窗口时间未被任何行覆盖的占比。窗口缺失 → None。"""
    if windows is None:
        return None
    total = sum(e - s for s, e in windows)
    if total <= 0:
        return {"speech_s": 0.0, "uncovered_s": 0.0, "ratio": None}
    spans = [s for s in (_timing_span(e.get("timing", "")) for e in entries) if s]
    uncovered = 0.0
    for w0, w1 in windows:
        covered = sum(_overlap((w0, w1), s) for s in spans)
        gap = (w1 - w0) - min(covered, w1 - w0)
        if gap > 0:
            uncovered += gap
    return {"speech_s": round(total, 3), "uncovered_s": round(uncovered, 3),
            "ratio": round(min(1.0, uncovered / total), 4)}


def _norm_text(t: str) -> str:
    return re.sub(r"\s+", "", t or "")


def agreement(entries_a: list[dict], entries_b: list[dict],
              iou_threshold: float = 0.5, sim_threshold: float = 0.6) -> dict:
    """双引擎一致率：贪婪时轴最优匹配（IoU≥阈值）且文本相似≥阈值。"""
    spans_a = [(i, _timing_span(e.get("timing", ""))) for i, e in enumerate(entries_a)]
    spans_b = [(i, _timing_span(e.get("timing", ""))) for i, e in enumerate(entries_b)]
    pairs: list[tuple[float, int, int]] = []
    for ia, sa in spans_a:
        if not sa:
            continue
        for ib, sb in spans_b:
            if not sb:
                continue
            inter = _overlap(sa, sb)
            if inter <= 0:
                continue
            union = (sa[1] - sa[0]) + (sb[1] - sb[0]) - inter
            if union <= 0:
                continue
            iou = inter / union
            if iou >= iou_threshold:
                pairs.append((iou, ia, ib))
    pairs.sort(reverse=True)
    used_a: set[int] = set()
    used_b: set[int] = set()
    matched = 0
    for _iou, ia, ib in pairs:
        if ia in used_a or ib in used_b:
            continue
        ta = _norm_text(entries_a[ia].get("text", ""))
        tb = _norm_text(entries_b[ib].get("text", ""))
        sim = difflib.SequenceMatcher(None, ta, tb).ratio()
        if sim >= sim_threshold:
            used_a.add(ia)
            used_b.add(ib)
            matched += 1
    n_a = len(spans_a)
    n_b = len(spans_b)
    return {
        "matched": matched,
        "lines_a": n_a,
        "lines_b": n_b,
        "rate_a": round(matched / n_a, 4) if n_a else None,
        "rate_b": round(matched / n_b, 4) if n_b else None,
    }


def cps_stats(entries: list[dict]) -> dict:
    """行均时长与 CPS 分位（CPS=去空白字符数/显示时长）。"""
    values: list[float] = []
    durs: list[float] = []
    for e in entries:
        span = _timing_span(e.get("timing", ""))
        if not span:
            continue
        dur = span[1] - span[0]
        chars = len(_norm_text(e.get("text", "")))
        durs.append(round(dur, 3))
        if dur > 0:
            values.append(chars / dur)
    if not values:
        return {"lines": len(durs), "cps_p50": None, "cps_p90": None, "cps_max": None,
                "avg_dur_s": None}
    values.sort()
    durs.sort()

    def pct(v: list[float], p: float) -> float:
        # 最近秩（nearest-rank）分位：ceil(p*n)-1，分位口径与 polish 报告对齐前不做插值
        idx = min(len(v) - 1, max(0, math.ceil(p * len(v)) - 1))
        return round(v[idx], 2)

    return {"lines": len(values), "cps_p50": pct(values, 0.5), "cps_p90": pct(values, 0.9),
            "cps_max": round(values[-1], 2), "avg_dur_s": round(sum(durs) / len(durs), 3)}


# 引擎槽位注册表：评测的引擎只增不改签；ct2 由 3.2.0 后端注册
_ENGINES: dict[str, Callable[..., str]] = {}


def register_engine(engine_id: str, runner: Callable[..., str]) -> None:
    _ENGINES[engine_id] = runner


def run_engine(engine_id: str, media_path: str, workdir: str,
               model: str = "", model_dir: str = "") -> str:
    """运行评测引擎，产出 SRT 路径。未注册引擎报错明示。"""
    runner = _ENGINES.get(engine_id)
    if runner is None:
        raise RuntimeError("评测引擎未注册或不可用: " + engine_id
                           + "（ct2 需先安装运行时：见 asr_runtime 安装链，3.2.0）")
    return runner(media_path=media_path, workdir=workdir, model=model, model_dir=model_dir)


def evaluate(media_path: str, srt_by_engine: dict[str, str],
             windows: list[tuple[float, float]] | None = None) -> dict:
    """组装单媒体评测报告（窗口可外注入供测试；缺省现算）。"""
    entries_by_engine = {}
    for engine_id, path in srt_by_engine.items():
        with open(path, encoding="utf-8") as f:
            entries_by_engine[engine_id] = parse_srt(f.read())
    err = None
    if windows is None:
        win_info = speech_windows_full(media_path)
        if "__error" in win_info:
            err = win_info["__error"]
            windows = None
        else:
            windows = win_info["windows"]
    engine_reports: dict[str, dict] = {}
    for engine_id, entries in entries_by_engine.items():
        engine_reports[engine_id] = {
            "lines": len(entries),
            "hallucination_proxy": hallucination_proxy(entries, windows),
            "omission_proxy": omission_proxy(entries, windows),
            "cps": cps_stats(entries),
        }
    pair_reports: dict[str, dict] = {}
    ids = sorted(entries_by_engine)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            key = ids[i] + "+" + ids[j]
            pair_reports[key] = agreement(entries_by_engine[ids[i]], entries_by_engine[ids[j]])
    return {
        "schema": "subtransjav.eval_baseline/1",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "media": os.path.basename(media_path or ""),
        "windows_error": err,
        "engines": engine_reports,
        "pairs": pair_reports,
        "note": "代理指标口径：涨跌比较用，绝对值不承诺正确率（[UNVERIFIABLE]）",
    }


_MD_PROXY_NAMES = {
    "hallucination_proxy": "幻听代理（低重叠行占比，越低越好）",
    "omission_proxy": "漏听代理（语音未覆盖占比，越低越好）",
}


def report_markdown(report: dict) -> str:
    lines = ["# 评测基线报告：" + report["media"], "",
             "生成：" + report["generated_at"] + "（schema " + report["schema"] + "）", ""]
    if report.get("windows_error"):
        lines += ["> 语音窗口检测退化：" + report["windows_error"]
                  + "——窗口类指标本轮为 null，不代表全静音。", ""]
    for engine_id, r in report["engines"].items():
        lines.append("## 引擎 " + engine_id)
        lines.append("")
        lines.append("- 行数：" + str(r["lines"]))
        for key, name in _MD_PROXY_NAMES.items():
            v = r.get(key)
            if v is None:
                lines.append("- " + name + "：null（窗口缺失）")
            else:
                ratio = v.get("ratio")
                ratio_s = "null" if ratio is None else format(ratio * 100, ".2f") + "%"
                detail = str(v.get("suspect", v.get("uncovered_s", "")))
                total = str(v.get("lines", v.get("speech_s", "")))
                lines.append("- " + name + "：" + ratio_s + "（" + detail + "/" + total + "）")
        cps = r.get("cps") or {}
        lines.append("- CPS p50/p90/max：" + str(cps.get("cps_p50")) + " / "
                     + str(cps.get("cps_p90")) + " / " + str(cps.get("cps_max"))
                     + "；行均时长 " + str(cps.get("avg_dur_s")) + "s")
        lines.append("")
    for key, p in report["pairs"].items():
        lines.append("## 双引擎一致率 " + key)
        lines.append("")
        lines.append("- 匹配 " + str(p["matched"]) + " 行（A " + str(p["lines_a"])
                     + " 行 / B " + str(p["lines_b"]) + " 行；rate_a=" + str(p["rate_a"])
                     + " rate_b=" + str(p["rate_b"]) + "）")
        lines.append("")
    lines.append("> 代理指标口径：只作涨跌比较，不承诺句级正确率绝对值。")
    return "\n".join(lines) + "\n"


_SAFE_STEM_RE = re.compile(r"[^A-Za-z0-9._\-]+")


def _safe_stem(stem: str) -> str:
    """报告文件名前缀白名单净化（字母/数字/点/下划线/连字符以外全替 _）。"""
    cleaned = _SAFE_STEM_RE.sub("_", stem or "").strip("._") or "eval"
    return cleaned[:80]


def write_report(report: dict, out_dir: str, stem: str) -> tuple[str, str]:
    base = pathlib.Path(out_dir).resolve()
    base.mkdir(parents=True, exist_ok=True)
    safe = _safe_stem(stem)
    json_path = base / (safe + "-baseline.json")
    md_path = base / (safe + "-baseline.md")
    for p in (json_path, md_path):
        # 包含校验：stem 已白名单净化（无分隔符），父目录必须仍是 resolve 后的
        # out_dir 本身，双保险杜绝任何越界写位（父目录词越级用 os.pardir 判）。
        if os.pardir in p.parts or p.parent != base:
            raise ValueError("报告写出路径越界: " + p.name)
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(report_markdown(report), encoding="utf-8", newline="\n")
    return str(json_path), str(md_path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m subtransjav.refine.eval_baseline",
        description="正确率评测 harness：对媒体上的一或多个引擎 SRT 出代理指标报告")
    parser.add_argument("--media", default="",
                        help="媒体文件路径（窗口检测源；可空=窗口类指标 null）")
    parser.add_argument("--srt", action="append", required=True,
                        metavar="ENGINE=PATH",
                        help="引擎 SRT，可重复：--srt upstream=a.srt --srt ct2=b.srt")
    parser.add_argument("--out", required=True, help="报告输出目录")
    parser.add_argument("--stem", default="", help="报告文件名前缀（缺省=媒体名）")
    args = parser.parse_args(argv)
    srt_by_engine: dict[str, str] = {}
    for item in args.srt:
        engine_id, sep, path = item.partition("=")
        if not sep or not engine_id or not path:
            print("--srt 形态应为 ENGINE=PATH，得到: " + item)
            return 2
        if not os.path.isfile(path):
            print("SRT 不存在: " + path)
            return 2
        srt_by_engine[engine_id] = path
    report = evaluate(args.media, srt_by_engine)
    stem = args.stem or (os.path.splitext(os.path.basename(args.media))[0] if args.media
                         else "eval")
    json_path, md_path = write_report(report, args.out, stem)
    print("report: " + json_path)
    print("report: " + md_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
