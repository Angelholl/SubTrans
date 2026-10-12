#!/usr/bin/env python3
"""C22 离线回放 harness（3.0 批3 开工门，D2026-1009-02 第三节）。

用法：
  python tools/c22_calibration.py --manifest <json> --out <report.md> [--enable]
  python tools/c22_calibration.py --selftest --out <report.md>

- manifest json＝[{"guide": 导读 json 路径, "media": 媒体路径,
  "label": true|false}, ...]（label=该间隙确有台词的真值，owner 独立
  标注，与阈值测算方分离——防循环自证）；
- 流程：逐样本读导读 observation 条目（category=suspected_missed_speech）
  → slice+batch_transcribe_clips → classify_transcript 三维分档 → 聚合：
  高置信桶精确率（判 high 中 label=true 占比）+Wilson 95% 置信下界+
  覆盖率（high 占全部）+召回（high 占 label=true）；
- --enable：且精确率下界 ≥0.95 才写 config/fullchain_c22.json
  （{"enabled": true, "measured_at": ..., "precision_lb": ..., "n": ...}），
  否则拒绝并退出码 2（门控文件是 F4 真自动补行的批内开工开关，3B 读）；
- --selftest：无真实媒体时的统计管线自检——构造合成 segments 直接过
  classify 聚合（不切片不转写），验证 harness 本身；
- 报告落 --out（指标+样本明细+阈值声明）。

全程离线零网络（真实转写走本机上游 whisper 子进程）；退出码：0=完成 /
1=参数或运行失败 / 2=校准未达标拒绝写门控。
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from subtransjav import paths  # noqa: E402
from subtransjav.refine.asr_env import (  # noqa: E402
    batch_transcribe_clips,
    cleanup_clips,
)
from subtransjav.refine.audio_detect import detect_speech_windows  # noqa: E402
from subtransjav.refine.missed_insert import classify_transcript  # noqa: E402

# C22 首版从严（owner 拍板②）：高置信桶精确率 Wilson 95% 置信下界门槛
_PRECISION_LB_GATE = 0.95
#Wilson 95% z 值（双侧）
_WILSON_Z = 1.959963984540054
_OBS_CATEGORY = "suspected_missed_speech"
_GATE_RELPATH = ("config", "fullchain_c22.json")


def wilson_lower_bound(successes: int, n: int, z: float = _WILSON_Z) -> float:
    """Wilson 分数区间 95% 下界（n=0 → 0.0）。"""
    if n <= 0:
        return 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * ((p * (1 - p) + z * z / (4 * n)) / n) ** 0.5
    return max(0.0, (centre - margin) / denom)


def _observation_timings(guide_path: str) -> list[str]:
    """读导读 json 的疑似漏听 observation 条目 timing 列表。"""
    data = json.loads(Path(guide_path).read_text(encoding="utf-8"))
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return []
    return [str(it.get("timing") or "") for it in items
            if isinstance(it, dict)
            and it.get("category") == _OBS_CATEGORY and it.get("timing")]


def _replay_sample(sample: dict) -> list[dict]:
    """单样本回放：切片批量转写→逐 timing 三维分档。

    返回 [{"timing", "grade", "label"}]；切片/转写失败→grade="empty"
    （不静默：错误进样本明细 reasons）。"""
    timings = _observation_timings(str(sample.get("guide") or ""))
    label = bool(sample.get("label"))
    if not timings:
        return [{"timing": "", "grade": "empty", "label": label,
                 "reasons": ["no_observations"]}]
    media = str(sample.get("media") or "")
    windows = detect_speech_windows(media, timings)
    transcripts = batch_transcribe_clips(media, timings)
    rows: list[dict] = []
    for t, tr in zip(timings, transcripts, strict=True):
        verdict = classify_transcript(
            t, tr.get("segments") or [], tr.get("text") or "", windows,
            language="ja")
        rows.append({"timing": t, "grade": verdict["grade"],
                     "label": label, "reasons": verdict["reasons"],
                     "asr_error": tr.get("error") or ""})
    return rows


def _selftest_rows() -> list[dict]:
    """--selftest：合成 segments 直过 classify 聚合（不切片不转写）。

    合成谱：4 真阳性（high）、1 假阳性（三维过但 label=false）、
    2 真阴性（低置信/判空、label=false）、1 漏检（label=true 但低置信）。
    预期精确率=4/5=0.8 → 下界 <0.95 → --enable 必拒（harness 方向自证）。"""
    good = {"start": 0.0, "end": 2.0, "text": "本当にすみません",
            "no_speech_prob": 0.02, "avg_logprob": -0.25,
            "compression_ratio": 1.2}
    junk = {"start": 0.0, "end": 2.0, "text": "ああああああああ",
            "no_speech_prob": 0.02, "avg_logprob": -0.3,
            "compression_ratio": 1.1}
    hallucinate = {"start": 0.0, "end": 2.0, "text": "カラカラカラカラ",
                   "no_speech_prob": 0.9, "avg_logprob": -1.8,
                   "compression_ratio": 3.5}
    windows: dict = {}
    t = "00:00:05,000 --> 00:00:07,000"
    rows = []
    for label, segs, text in ((True, [good], "本当にすみません"),
                              (True, [good], "本当にすみません"),
                              (True, [good], "本当にすみません"),
                              (True, [good], "本当にすみません"),
                              (False, [junk], "ああああああああ"),
                              (False, [hallucinate], "カラカラカラカラ"),
                              (False, [], ""),
                              (True, [hallucinate], "カラカラカラカラ")):
        v = classify_transcript(t, segs, text, windows, overlap_s=1.5)
        rows.append({"timing": t, "grade": v["grade"], "label": label,
                     "reasons": v["reasons"], "asr_error": ""})
    return rows


def _aggregate(rows: list[dict]) -> dict:
    """聚合指标：高置信桶精确率/Wilson 下界/覆盖率/召回。"""
    high = [r for r in rows if r.get("grade") == "high"]
    tp = sum(1 for r in high if r.get("label"))
    n = len(high)
    total = len(rows)
    positives = sum(1 for r in rows if r.get("label"))
    return {"n_high": n,
            "tp_high": tp,
            "precision": (tp / n) if n else 0.0,
            "precision_lb": wilson_lower_bound(tp, n),
            "coverage": (n / total) if total else 0.0,
            "recall": (tp / positives) if positives else 0.0,
            "n_total": total,
            "n_positive": positives}


def _write_report(out_path: str, rows: list[dict], agg: dict,
                  *, selftest: bool, enabled_written: bool) -> None:
    lines = [
        "# C22 校准回放报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 模式：{'selftest（合成 segments，统计管线自检）' if selftest else '真实回放'}",
        f"- 阈值声明：高置信桶精确率 Wilson 95% 置信下界 ≥ "
        f"{_PRECISION_LB_GATE:.2f} 才允许 --enable 写门控"
        "（D2026-1009-02 第三节，首版从严）",
        "",
        "## 指标",
        "",
        f"- 判 high：{agg['n_high']} / {agg['n_total']}"
        f"（其中 label=true：{agg['tp_high']}）",
        f"- 精确率：{agg['precision']:.4f}",
        f"- Wilson 95% 置信下界：{agg['precision_lb']:.4f}"
        f"（门槛 {_PRECISION_LB_GATE:.2f}："
        f"{'达标' if agg['precision_lb'] >= _PRECISION_LB_GATE else '未达标'}）",
        f"- 覆盖率（high/全部）：{agg['coverage']:.4f}",
        f"- 召回（high/label=true）：{agg['recall']:.4f}",
        f"- 门控文件：{'已写入' if enabled_written else '未写入'}"
        f"（config/fullchain_c22.json）",
        "",
        "## 样本明细",
        "",
        "| # | timing | grade | label | reasons |",
        "|---|--------|-------|-------|---------|",
    ]
    for i, r in enumerate(rows, 1):
        reasons = "; ".join(r.get("reasons") or [])
        if r.get("asr_error"):
            reasons = (reasons + f" | asr_error={r['asr_error']}").strip(" |")
        lines.append(f"| {i} | {r.get('timing')} | {r.get('grade')} "
                     f"| {r.get('label')} | {reasons} |")
    Path(out_path).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="c22_calibration",
        description="C22 离线回放 harness（3.0 批3 开工门）")
    parser.add_argument("--manifest", default="",
                        help="样本清单 json（[{'guide','media','label'}]）")
    parser.add_argument("--out", required=True, help="报告 markdown 落点")
    parser.add_argument("--enable", action="store_true",
                        help="达标时写 config/fullchain_c22.json 门控")
    parser.add_argument("--selftest", action="store_true",
                        help="合成 segments 统计管线自检（不切片不转写）")
    args = parser.parse_args(argv)

    if args.selftest:
        rows = _selftest_rows()
    else:
        if not args.manifest or not Path(args.manifest).is_file():
            print("❌ --manifest 缺失或不存在（离线回放需真实样本清单；"
                  "无媒体时用 --selftest 验证统计管线）")
            return 1
        try:
            manifest = json.loads(
                Path(args.manifest).read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            print(f"❌ manifest 读取失败: {e}")
            return 1
        if not isinstance(manifest, list) or not manifest:
            print("❌ manifest 须为非空数组")
            return 1
        rows = []
        for i, sample in enumerate(manifest, 1):
            if not isinstance(sample, dict) or not sample.get("guide"):
                print(f"❌ manifest 第 {i} 项缺 guide 路径")
                return 1
            rows.extend(_replay_sample(sample))
        cleanup_clips()

    agg = _aggregate(rows)
    gate_path = Path(paths.data_subdir(*_GATE_RELPATH))
    enabled_written = False
    if agg["precision_lb"] >= _PRECISION_LB_GATE:
        if args.enable:
            gate_path.parent.mkdir(parents=True, exist_ok=True)
            gate_path.write_text(json.dumps(
                {"enabled": True,
                 "measured_at": datetime.now().strftime(
                     "%Y-%m-%d %H:%M:%S"),
                 "precision_lb": round(agg["precision_lb"], 4),
                 "n": agg["n_high"]}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            enabled_written = True
            print(f"✅ C22 达标（下界 {agg['precision_lb']:.4f}），"
                  f"门控已写入: {gate_path}")
        else:
            print(f"ℹ️ C22 达标（下界 {agg['precision_lb']:.4f}）；"
                  "未给 --enable，门控未写")
    else:
        if args.enable:
            print(f"❌ C22 未达标（下界 {agg['precision_lb']:.4f} < "
                  f"{_PRECISION_LB_GATE:.2f}）：拒绝写门控（不达标=漏听"
                  "条目全部放弃，owner 知情处置）")
            _write_report(args.out, rows, agg, selftest=args.selftest,
                          enabled_written=False)
            return 2
        print(f"ℹ️ C22 未达标（下界 {agg['precision_lb']:.4f}）；"
              "门控未写")
    _write_report(args.out, rows, agg, selftest=args.selftest,
                  enabled_written=enabled_written)
    print(f"📄 报告已落盘: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
