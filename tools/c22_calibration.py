#!/usr/bin/env python3
"""C22 离线回放 harness（3.0 批3 开工门，D2026-1009-02 第三节）。

用法：
  python tools/c22_calibration.py --manifest <json> --out <report.md> [--enable]
  python tools/c22_calibration.py --manifest <json> --out <report.md> \
      --speech-min-s <float|none>
  python tools/c22_calibration.py --selftest --out <report.md>

- manifest json＝[{"guide": 导读 json 路径, "media": 媒体路径,
  "label": true|false}, ...]（label=该间隙确有台词的真值，owner 独立
  标注，与阈值测算方分离——防循环自证）；guide 与 "timings" 显式清单
  至少其一（timings 非空时不读导读）；条目可带三个可选键（均缺省或
  null=旧行为）："labels"=bool 数组逐 timing 取 labels[i] 作该行真值
  （逐间隙口径，D2026-1009-02 §三）；"timings"=SRT 区间字符串数组，显式
  清单取代导读派生（标注包只截前 20 条，显式清单才精确对齐）；
  "exclude_reasons"=逐 timing 排除原因数组（D2026-1029-11 裁决②/D3
  排除面载体：非空行不进主口径统计，喘息类在参照口径回样）。数组长度
  必须与 timings 相等，不匹配即 raise 中文 ValueError → main 退出码 1
  （fail-closed）；单样本 timings 上限=asr_env._MAX_CLIPS（超限先于
  引擎 fail-closed 报错，构建侧分块方案存内部记录）；
- 流程：逐样本读导读 observation 条目（category=suspected_missed_speech）
  → slice+batch_transcribe_clips → classify_transcript 三维分档 → 聚合：
  高置信桶精确率（判 high 中 label=true 占比）+Wilson 95% 置信下界+
  覆盖率（high 占全部）+召回（high 占 label=true）；
- 门判定（D2026-1029-11 裁决①第 0 件：双条件＋不可判档，fail-closed）：
  n_high < _GATE_MIN_HIGH → verdict=unjudgeable（不评估精确率门）；
  pass 当且仅当精确率下界与覆盖率双达标；其余 verdict=fail；
- 分诊（D2026-1029-12 D2）：切片/转写失败或引擎未装段如实计入分档样本
  （grade=empty，与实现一致的勘正口径），报告单列 asr_error 与 empty
  分桶（带 error／真空输出）；主口径分母不变（与既有报告可比）；
- 双读数（同报告参照节，D2026-1029-11 裁决①）：同一批转写产物以
  speech_min_s=None 二次 classify（不重复转写）得参照读数；参照节无门
  判定语义（只报计数与点精确率，D3 口径）；
- --enable：且 verdict=pass 才写 config/fullchain_c22.json
  （{"enabled": true, "measured_at": ..., "precision_lb": ..., "n": ...}），
  否则拒绝并退出码 2（门控文件是 F4 真自动补行的批内开工开关，3B 读）；
- --selftest：无真实媒体时的统计管线自检——构造合成 segments 直接过
  classify 聚合（不切片不转写），验证 harness 本身；
- 报告落 --out（指标+样本明细+阈值声明）。

全程离线零网络（真实转写经 batch_transcribe_clips 引擎分派＝CT2 唯一引擎
本地子进程，D2026-1029-01 退役批口径；环境前置＝CT2 运行时认证安装+模型
落位，未装时转写段如实报错不计入分档样本）；退出码：0=完成 /
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
    _MAX_CLIPS,
    batch_transcribe_clips,
    cleanup_clips,
)
from subtransjav.refine.audio_detect import detect_speech_windows  # noqa: E402
from subtransjav.refine.missed_insert import classify_transcript  # noqa: E402

# C22 首版从严（owner 拍板②）：高置信桶精确率 Wilson 95% 置信下界门槛
_PRECISION_LB_GATE = 0.95
# 门双条件补充（D2026-1029-11 裁决①第 0 件；PROVISIONAL 预注册，owner 可终裁改值）：
# 高置信桶最小可判样本数——低于此值判「不可判」（样本不足无法与引擎差区分）
_GATE_MIN_HIGH = 30
# 覆盖率地板——high 占比低于此值即使精确率达标也不放行（防高放弃率下虚过）
_GATE_COVERAGE_FLOOR = 0.50
#Wilson 95% z 值（双侧）
_WILSON_Z = 1.959963984540054
_OBS_CATEGORY = "suspected_missed_speech"
_GATE_RELPATH = ("config", "fullchain_c22.json")
# 排除率上限（D2026-1029-12 D3；PROVISIONAL 预注册，owner 可终裁改值）：
# 监管「不可归因排除」（杂音无法判定＋复标不一致）合计占全体候选行比例；
# 喘息档系裁决固定排除语义（排除单列、参照口径回样），不设上限。
_EXCLUDE_CAP_UNATTRIBUTED = 0.10
_UNATTRIBUTED_MARKS = ("杂音无法判定", "复标不一致")
# 参照口径（含喘息）回样标记：exclude_reason 含此子串者不进主口径统计、
# 在参照口径回样（裁决②修正版：喘息类不进主分母＋含/不含双口径同报）
_REF_INCLUDE_MARK = "喘息"
# 「CLI 未给 --speech-min-s」哨兵：与显式 none（None）区分，缺省时不向
# classify_transcript 传 speech_min_s kwarg（仍走产品缺省终裁值，零变化）
_SPEECH_MIN_UNSET = object()


def _parse_speech_min_s(raw: str) -> float | None:
    """--speech-min-s 取值解析：浮点数或字面量 none（大小写不敏感）。"""
    text = str(raw).strip()
    if text.lower() == "none":
        return None
    try:
        return float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"speech-min-s 须为浮点数或字面量 none，实际为 {raw!r}") from None


def _speech_min_label(value: object) -> str:
    """报告头声明用：缺省哨兵 → 产品终裁值说明；None → none；浮点 → %g。"""
    if value is _SPEECH_MIN_UNSET:
        return "缺省(产品终裁值)"
    if value is None:
        return "none"
    return f"{float(value):g}"


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


def _replay_sample(sample: dict, ctx: list[dict] | None = None,
                   *, speech_min_s: object = _SPEECH_MIN_UNSET) -> list[dict]:
    """单样本回放：切片批量转写→逐 timing 三维分档。

    返回 [{"timing", "grade", "label", "reasons", "asr_error",
    "exclude_reason"}]；切片/转写失败→grade="empty"（不静默：错误进
    样本明细 asr_error 独立列）。ctx 非空时顺带落转写上下文（供参照
    读数二次 classify，不重复转写）。
    可选键（缺省或 null=旧行为）："labels"=逐 timing 真值数组，
    "timings"=显式清单（非空时取代导读派生，导读可不提供），
    "exclude_reasons"=逐 timing 排除原因数组（D2026-1029-11 裁决②/D3，
    非空行不进主口径统计）；
    len(timings) 与各数组不等长 → ValueError 中文（fail-closed，
    不静默截断/不循环补齐），len(timings) 超 asr_env._MAX_CLIPS →
    ValueError（先于引擎报错，构建侧分块），由 main 捕获转退出码 1。
    speech_min_s：仅显式传值（float 或 None）时透传主口径
    classify_transcript；缺省哨兵＝不传 kwarg（产品终裁值零变化）。"""
    raw_timings = sample.get("timings")
    if raw_timings is not None and not isinstance(raw_timings, list):
        raise ValueError(f"manifest 条目 timings 须为 SRT 区间字符串数组，"
                         f"实际为 {type(raw_timings).__name__}")
    timings = ([str(t) for t in raw_timings] if raw_timings
               else _observation_timings(str(sample.get("guide") or "")))
    labels = sample.get("labels")
    if labels is not None and not isinstance(labels, list):
        raise ValueError(f"manifest 条目 labels 须为 bool 数组，"
                         f"实际为 {type(labels).__name__}")
    exclude_reasons = sample.get("exclude_reasons")
    if exclude_reasons is not None and not isinstance(exclude_reasons, list):
        raise ValueError(f"manifest 条目 exclude_reasons 须为字符串数组，"
                         f"实际为 {type(exclude_reasons).__name__}")
    if labels is not None and len(timings) != len(labels):
        raise ValueError(f"labels 与 timings 长度不匹配："
                         f"len(timings)={len(timings)} != "
                         f"len(labels)={len(labels)}，拒绝回放")
    if exclude_reasons is not None and len(timings) != len(exclude_reasons):
        raise ValueError(f"exclude_reasons 与 timings 长度不匹配："
                         f"len(timings)={len(timings)} != "
                         f"len(exclude_reasons)={len(exclude_reasons)}，"
                         "拒绝回放")
    if len(timings) > _MAX_CLIPS:
        raise ValueError(
            f"manifest 条目 timings {len(timings)} 条超出单样本上限 "
            f"{_MAX_CLIPS}（引擎切片批量 fail-closed）；manifest 构建"
            f"须按 ≤{_MAX_CLIPS} 条/样本分块"
            "（构建侧分块方案存内部记录）")
    label = bool(sample.get("label"))
    if not timings:
        if ctx is not None:
            ctx.append({"timing": "", "segments": [], "text": "",
                        "windows": {}, "overlap_s": None, "label": label,
                        "asr_error": "", "exclude_reason": None})
        return [{"timing": "", "grade": "empty", "label": label,
                 "reasons": ["no_observations"], "exclude_reason": None}]
    media = str(sample.get("media") or "")
    windows = detect_speech_windows(media, timings)
    transcripts = batch_transcribe_clips(media, timings,
                                         max_clips=_MAX_CLIPS)
    rows: list[dict] = []
    classify_kwargs: dict = {}
    if speech_min_s is not _SPEECH_MIN_UNSET:
        classify_kwargs["speech_min_s"] = speech_min_s
    for i, (t, tr) in enumerate(zip(timings, transcripts, strict=True)):
        verdict = classify_transcript(
            t, tr.get("segments") or [], tr.get("text") or "", windows,
            language="ja", **classify_kwargs)
        row_label = label if labels is None else labels[i]
        exc = (str(exclude_reasons[i])
               if exclude_reasons and exclude_reasons[i] else None)
        rows.append({"timing": t, "grade": verdict["grade"],
                     "label": row_label,
                     "reasons": verdict["reasons"],
                     "asr_error": tr.get("error") or "",
                     "exclude_reason": exc})
        if ctx is not None:
            ctx.append({"timing": t, "segments": tr.get("segments") or [],
                        "text": tr.get("text") or "", "windows": windows,
                        "overlap_s": None, "label": row_label,
                        "asr_error": tr.get("error") or "",
                        "exclude_reason": exc})
    return rows


def _selftest_rows(ctx: list[dict] | None = None) -> list[dict]:
    """--selftest：合成 segments 直过 classify 聚合（不切片不转写）。

    合成谱：4 真阳性（high）、1 假阳性（三维过但 label=false）、
    2 真阴性（低置信/判空、label=false）、1 漏检（label=true 但低置信）。
    预期 n_high=4 < _GATE_MIN_HIGH → verdict=unjudgeable → --enable 必拒
    （harness 方向自证）。"""
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
        if ctx is not None:
            ctx.append({"timing": t, "segments": segs, "text": text,
                        "windows": windows, "overlap_s": 1.5,
                        "label": label, "asr_error": ""})
    return rows


def _gate_verdict(agg: dict) -> str:
    """门判定（fail-closed）：unjudgeable|pass|fail（D2026-1029-11 裁决①）。

    判定序：n_high 不足最小可判样本数 → unjudgeable（不评估精确率门，
    避免 0.0000 读数冒充「引擎差」）；pass 当且仅当精确率 Wilson 下界与
    覆盖率双达标；其余 fail。"""
    if agg["n_high"] < _GATE_MIN_HIGH:
        return "unjudgeable"
    if (agg["precision_lb"] >= _PRECISION_LB_GATE
            and agg["coverage"] >= _GATE_COVERAGE_FLOOR):
        return "pass"
    return "fail"


def _reclassify_no_energy_gate(ctx: list[dict]) -> list[dict]:
    """参照读数（D2026-1029-11 裁决① 双读数＋裁决② 含喘息双口径）：
    同一批转写产物以 speech_min_s=None 二次 classify（不重复转写，零
    新增引擎调用）。

    排除面处置：exclude_reason 含「喘息」者在参照口径回样（label=true，
    裁决②修正版——喘息类不进主分母但保留喘息场景唯一观测窗口）；
    杂音/复标不一致行两口径均排除（exclude_reason 保留，出统计）。
    产出行形态与主口径 rows 同构；只供计数与点精确率呈现，不得带任何
    门判定语义（D3 口径：参照列无 Wilson 下界/覆盖率/verdict）。"""
    rows: list[dict] = []
    for c in ctx:
        exc = c.get("exclude_reason") or None
        v = classify_transcript(c["timing"], c["segments"], c["text"],
                                c.get("windows") or {},
                                overlap_s=c.get("overlap_s"),
                                speech_min_s=None)
        ref_label = bool(c.get("label"))
        ref_exc = exc
        if exc and _REF_INCLUDE_MARK in str(exc):
            ref_label = True
            ref_exc = None
        rows.append({"timing": c["timing"], "grade": v["grade"],
                     "label": ref_label,
                     "reasons": v["reasons"],
                     "asr_error": c.get("asr_error") or "",
                     "exclude_reason": ref_exc})
    return rows


def _aggregate(rows: list[dict]) -> dict:
    """聚合指标：高置信桶精确率/Wilson 下界/覆盖率/召回＋分诊计数
    （asr_error/empty 分桶，报告面单列）＋排除面计数（D2026-1029-12
    D3：exclude_reason 非空行不进主口径统计——分母/召回均基于入样行；
    无 exclude_reason 键的旧行为 = 零排除 = 分母与原 total 全等）。"""
    excluded = [r for r in rows if r.get("exclude_reason")]
    eff = [r for r in rows if not r.get("exclude_reason")]
    high = [r for r in eff if r.get("grade") == "high"]
    tp = sum(1 for r in high if r.get("label"))
    n = len(high)
    total = len(eff)
    positives = sum(1 for r in eff if r.get("label"))
    empty_rows = [r for r in eff if r.get("grade") == "empty"]
    err_rows = [r for r in eff if r.get("asr_error")]
    empty_with_error = [r for r in empty_rows if r.get("asr_error")]
    by_reason: dict[str, int] = {}
    for r in excluded:
        k = str(r.get("exclude_reason"))
        by_reason[k] = by_reason.get(k, 0) + 1
    return {"n_high": n,
            "tp_high": tp,
            "precision": (tp / n) if n else 0.0,
            "precision_lb": wilson_lower_bound(tp, n),
            "coverage": (n / total) if total else 0.0,
            "recall": (tp / positives) if positives else 0.0,
            "n_total": total,
            "n_positive": positives,
            "n_asr_error": len(err_rows),
            "n_empty_with_error": len(empty_with_error),
            "n_empty_silent": len(empty_rows) - len(empty_with_error),
            "n_rows_all": len(rows),
            "n_excluded": len(excluded),
            "exclude_rate": (len(excluded) / len(rows)) if rows else 0.0,
            "n_excluded_by_reason": by_reason}


def _unattributed_excluded(agg: dict) -> int:
    """不可归因排除合计（D3：杂音无法判定＋复标不一致；监管上限用）。"""
    by_reason = agg.get("n_excluded_by_reason") or {}
    return sum(v for k, v in by_reason.items()
               if any(m in k for m in _UNATTRIBUTED_MARKS))


def _write_report(out_path: str, rows: list[dict], agg: dict,
                  *, selftest: bool, enabled_written: bool, verdict: str,
                  ref_agg: dict,
                  speech_min_s: object = _SPEECH_MIN_UNSET) -> None:
    n_all = agg.get("n_rows_all") or agg["n_total"]
    unattr = _unattributed_excluded(agg)
    unattr_rate = (unattr / n_all) if n_all else 0.0
    over_cap = unattr_rate > _EXCLUDE_CAP_UNATTRIBUTED
    breath_n = sum(v for k, v in (agg.get("n_excluded_by_reason") or {}).items()
                   if _REF_INCLUDE_MARK in k)
    lines = [
        "# C22 校准回放报告",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 模式：{'selftest（合成 segments，统计管线自检）' if selftest else '真实回放'}",
        f"- 主口径 speech_min_s={_speech_min_label(speech_min_s)}"
        "（参照口径恒 none，不受本值影响）",
        f"- 阈值声明：门判定双条件＝n_high ≥ {_GATE_MIN_HIGH}"
        f"（不足判不可判）且精确率 Wilson 95% 置信下界 ≥ "
        f"{_PRECISION_LB_GATE:.2f} 且覆盖率 ≥ {_GATE_COVERAGE_FLOOR:.2f}"
        " 才允许 --enable 写门控（D2026-1009-02 第三节＋D2026-1029-11 "
        "裁决① 门死锁修复；两新增门值 PROVISIONAL，owner 可终裁改值）",
        "",
        "## 指标",
        "",
        f"- 判定（verdict）：{verdict}"
        + ("（n_high 不足最小可判样本数，精确率门不评估）"
           if verdict == "unjudgeable" else ""),
        f"- 判 high：{agg['n_high']} / {agg['n_total']}"
        f"（其中 label=true：{agg['tp_high']}）",
        f"- 精确率：{agg['precision']:.4f}",
        f"- Wilson 95% 置信下界：{agg['precision_lb']:.4f}"
        f"（门槛 {_PRECISION_LB_GATE:.2f}："
        f"{'达标' if agg['precision_lb'] >= _PRECISION_LB_GATE else '未达标'}）",
        f"- 覆盖率（high/全部）：{agg['coverage']:.4f}"
        f"（地板 {_GATE_COVERAGE_FLOOR:.2f}："
        f"{'达标' if agg['coverage'] >= _GATE_COVERAGE_FLOOR else '未达标'}）",
        f"- 召回（high/label=true）：{agg['recall']:.4f}",
        f"- 分诊：asr_error 行 {agg['n_asr_error']}；empty 分桶＝"
        f"带 error {agg['n_empty_with_error']}／真空输出 "
        f"{agg['n_empty_silent']}（主口径分母不变，D2026-1029-12 D2）",
        f"- 门控文件：{'已写入' if enabled_written else '未写入'}"
        f"（config/fullchain_c22.json）",
        "",
        "## 排除面（D2026-1029-11 裁决②/D2026-1029-12 D3）",
        "",
        f"- 排除行：{agg.get('n_excluded', 0)} / 全体候选 {n_all}"
        f"（排除率 {agg.get('exclude_rate', 0.0):.4f}；排除行不进主口径"
        "统计，排除行不删、清单见报告尾）",
        f"- 分原因：{'；'.join(f'{k} {v}' for k, v in (agg.get('n_excluded_by_reason') or {}).items()) or '（无排除）'}",
        f"- 不可归因排除（杂音无法判定＋复标不一致）：{unattr} 条，"
        f"比率 {unattr_rate:.4f}／上限 {_EXCLUDE_CAP_UNATTRIBUTED:.2f}"
        "（PROVISIONAL 预注册，owner 可终裁）："
        + ("⚠️ WARN 超限——本读数仅呈报，不得作开门验收依据，须 owner 复核"
           if over_cap else "未超限"),
        f"- 喘息档（裁决固定排除语义，参照口径回样）：{breath_n} 条",
        "",
        "## 样本明细",
        "",
        "| # | timing | grade | label | reasons | asr_error | exclude_reason |",
        "|---|--------|-------|-------|---------|-----------|----------------|",
    ]
    for i, r in enumerate(rows, 1):
        reasons = "; ".join(r.get("reasons") or [])
        err = str(r.get("asr_error") or "").replace("|", "\\|")
        exc = str(r.get("exclude_reason") or "").replace("|", "\\|")
        lines.append(f"| {i} | {r.get('timing')} | {r.get('grade')} "
                     f"| {r.get('label')} | {reasons} | {err} | {exc} |")
    lines += [
        "",
        "## 参照读数（不含 ≤1s 能量门；含喘息口径）",
        "",
        "参照口径＝同一批转写产物以 speech_min_s=None 二次 classify"
        "（不重复转写）；喘息档排除行在本口径回样（label=true，裁决②"
        "含/不含双口径同报——判定列唯一为本报告主口径）；本节无门判定"
        "语义，只报计数与点精确率（D2026-1029-11 裁决①/D3 口径）。",
        "",
        f"- n_high：{ref_agg['n_high']}（label=true：{ref_agg['tp_high']}）"
        f" / n_total：{ref_agg['n_total']}",
        f"- 点精确率：{ref_agg['precision']:.4f}",
        f"- empty 分桶＝带 error {ref_agg['n_empty_with_error']}"
        f"／真空输出 {ref_agg['n_empty_silent']}；"
        f"asr_error 行 {ref_agg['n_asr_error']}；两口径均排除行 "
        f"{ref_agg.get('n_excluded', 0)}",
    ]
    exc_rows = [r for r in rows if r.get("exclude_reason")]
    if exc_rows:
        lines += [
            "",
            "## 排除项清单（审计，D2026-1029-12 D3）",
            "",
            "| # | timing | exclude_reason |",
            "|---|--------|----------------|",
        ]
        for i, r in enumerate(exc_rows, 1):
            exc = str(r.get("exclude_reason") or "").replace("|", "\\|")
            lines.append(f"| {i} | {r.get('timing')} | {exc} |")
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
    parser.add_argument("--speech-min-s", dest="speech_min_s",
                        type=_parse_speech_min_s,
                        default=_SPEECH_MIN_UNSET,
                        help="主口径能量门阈值（浮点数或字面量 none；缺省不传"
                             "＝产品终裁值，零变化；参照口径恒 none 不受影响）")
    args = parser.parse_args(argv)

    ctx: list[dict] = []
    if args.selftest:
        rows = _selftest_rows(ctx)
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
            if (not isinstance(sample, dict)
                    or not (sample.get("guide") or sample.get("timings"))):
                print(f"❌ manifest 第 {i} 项缺 guide 路径或 timings "
                      "显式清单（至少其一）")
                return 1
            try:
                rows.extend(_replay_sample(sample, ctx,
                                           speech_min_s=args.speech_min_s))
            except ValueError as e:
                # fail-closed：labels/timings 校验失败直接中止（不静默截断、
                # 不循环补齐），退出码 1
                print(f"❌ manifest 第 {i} 项回放失败：{e}")
                return 1
        cleanup_clips()

    agg = _aggregate(rows)
    verdict = _gate_verdict(agg)
    ref_agg = _aggregate(_reclassify_no_energy_gate(ctx))
    gate_path = Path(paths.data_subdir(*_GATE_RELPATH))
    enabled_written = False
    if verdict == "pass":
        if args.enable:
            gate_path.parent.mkdir(parents=True, exist_ok=True)
            gate_path.write_text(json.dumps(
                {"enabled": True,
                 "measured_at": datetime.now().strftime(
                     "%Y-%m-%d %H:%M:%S"),
                 "precision_lb": round(agg["precision_lb"], 4),
                 "coverage": round(agg["coverage"], 4),
                 "n": agg["n_high"]}, ensure_ascii=False, indent=1),
                encoding="utf-8")
            enabled_written = True
            print(f"✅ C22 达标（下界 {agg['precision_lb']:.4f}，覆盖率 "
                  f"{agg['coverage']:.4f}），门控已写入: {gate_path}")
        else:
            print(f"ℹ️ C22 达标（下界 {agg['precision_lb']:.4f}，覆盖率 "
                  f"{agg['coverage']:.4f}）；未给 --enable，门控未写")
    elif verdict == "unjudgeable":
        if args.enable:
            print(f"❌ C22 不可判（n_high {agg['n_high']} < 最小可判样本 "
                  f"{_GATE_MIN_HIGH}）：拒绝写门控（fail-closed，样本不足"
                  "无法与引擎差区分）")
            _write_report(args.out, rows, agg, selftest=args.selftest,
                          enabled_written=False, verdict=verdict,
                          ref_agg=ref_agg,
                          speech_min_s=args.speech_min_s)
            return 2
        print(f"ℹ️ C22 不可判（n_high {agg['n_high']} < {_GATE_MIN_HIGH}）；"
              "门控未写")
    else:
        if args.enable:
            print(f"❌ C22 未达标（下界 {agg['precision_lb']:.4f} < "
                  f"{_PRECISION_LB_GATE:.2f} 或覆盖率 "
                  f"{agg['coverage']:.4f} < {_GATE_COVERAGE_FLOOR:.2f}）："
                  "拒绝写门控（不达标=漏听条目全部放弃，owner 知情处置）")
            _write_report(args.out, rows, agg, selftest=args.selftest,
                          enabled_written=False, verdict=verdict,
                          ref_agg=ref_agg,
                          speech_min_s=args.speech_min_s)
            return 2
        print(f"ℹ️ C22 未达标（下界 {agg['precision_lb']:.4f}）；"
              "门控未写")
    _write_report(args.out, rows, agg, selftest=args.selftest,
                  enabled_written=enabled_written, verdict=verdict,
                  ref_agg=ref_agg,
                  speech_min_s=args.speech_min_s)
    print(f"📄 报告已落盘: {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
