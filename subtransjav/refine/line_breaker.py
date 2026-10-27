"""line_breaker——CT2 长行确定性断行器（3.2.1 骨架，D2026-1028-03）。

社区实证（WhisperJAV issues #442/#468 存内部记录）：CT2 large-v2 原生输出
长行多（十几二十秒），社区靠 Subtitle Edit 手工分割+波形图调轴。本件把该
手工流程自动化：词级时间戳+CPS+停顿检测的确定性断行，零依赖零随机。

**定序声明（D4 范式）**：链序=ct2 断行器（ASR 产出成形点，本件）→
kana_clean（预翻译源文清洗）→ 翻译 → polish（翻译后重排）。断行器对既有
两层零接触——kana_clean/polish 的输入在断行之后天然已是短行，polish
幂等性不受影响。顺序不变量（tests/test_line_breaker.py 钉死）：
①文本守恒 ②时间轴覆盖守恒 ③对达标行幂等。

输入=asr_runner ct2 后端的 words sidecar（subtransjav.ct2.words/1）；输出=
切分后 segment 列表。参数全部 PROVISIONAL，最终值待真机语料校准后单点
改默认（对齐 polish POLICY_DEFAULTS 范式）。
"""

from __future__ import annotations

import re

__all__ = ["POLICY_DEFAULTS", "break_segment", "break_segments", "main"]

# 单一常量参数表（逐行 PROVISIONAL；改动须真机语料校准+联动测试）
POLICY_DEFAULTS: dict[str, float] = {
    "max_chars": 16,       # PROVISIONAL：单片全角字上限（对齐 polish 每行上限）
    "max_lines": 2,        # PROVISIONAL：单块最多行数；超出即继续切（本版不做块内重排）
    "pause_ms": 300,       # PROVISIONAL：词间隙 ≥ 此值视为停顿点（优先切点）
    "min_dur_s": 0.8,      # PROVISIONAL：单片最短显示时长（过短并入下片）
}

_WS_RE = re.compile(r"\s+")


def _text_len(t: str) -> int:
    return len(_WS_RE.sub("", t or ""))


def _join_words(words: list[dict]) -> str:
    return "".join(str(w.get("word") or "") for w in words)


def _cov_span(words: list[dict]) -> tuple[float, float] | None:
    starts = [float(w["start"]) for w in words if w.get("start") is not None]
    ends = [float(w["end"]) for w in words if w.get("end") is not None]
    if not starts or not ends:
        return None
    return min(starts), max(ends)


def break_segment(seg: dict, params: dict[str, float] | None = None) -> list[dict]:
    """单片→多片确定性切分。达标原样返回（幂等）；无词级时间戳原样返回。"""
    p = dict(POLICY_DEFAULTS)
    if params:
        p.update(params)
    max_chars = int(p["max_chars"])
    pause_s = float(p["pause_ms"]) / 1000.0
    min_dur = float(p["min_dur_s"])

    words = list(seg.get("words") or [])
    if len(words) < 2:
        return [seg]
    if _text_len(_join_words(words)) <= max_chars:
        return [seg]

    # 候选切点：词 i 与 i+1 之间（间隙=下一词起点-本词终点）
    cuts: list[tuple[float, int]] = []   # (优先级, 词界索引 i=切在此词后)
    for i in range(len(words) - 1):
        end_i = words[i].get("end")
        start_next = words[i + 1].get("start")
        if end_i is None or start_next is None:
            continue
        gap = float(start_next) - float(end_i)
        if gap >= pause_s:
            cuts.append((1.0, i))        # 停顿点=优先切点
        else:
            cuts.append((0.0, i))        # 非停顿点=硬切候选（仅超限时用）
    if not cuts:
        return [seg]

    # 贪心累计：达到字符上限时，取窗内最后一个可用切点（优先停顿点）
    parts: list[list[dict]] = []
    cur: list[dict] = []
    cur_chars = 0
    cut_map = {i: (pri, i) for pri, i in cuts}
    for i, w in enumerate(words):
        cur.append(w)
        cur_chars += _text_len(str(w.get("word") or ""))
        if cur_chars >= max_chars and len(cur) >= 2:
            # 窗内可切点：cur[j] 之后的词界（j=0..len(cur)-2），全局词界索引
            # = base + j（base=本窗首词全局下标）。取优先级最高者，同级取最后
            # 一个（靠后切=前片更长更均匀）。
            base = i - len(cur) + 1
            best = None
            for j in range(len(cur) - 1):
                cand = cut_map.get(base + j)
                if cand is None:
                    continue
                if best is None or cand[0] >= best[0]:
                    best = cand
            if best is None:
                continue                 # 无合法切点，继续累计
            cut_idx = best[1]
            take = cut_idx - base + 1
            parts.append(cur[:take])
            cur = cur[take:]
            cur_chars = _text_len(_join_words(cur))
    if cur:
        parts.append(cur)
    if len(parts) <= 1:
        return [seg]

    # 过短片并入邻片（min_dur）；字符上限优先于时长下限——并入后超上限则
    # 不并（短但诚实的独立片好过超宽片）。
    def _chunk_chars(chunk: list[dict]) -> int:
        return _text_len(_join_words(chunk))

    merged: list[list[dict]] = []
    for chunk in parts:
        span = _cov_span(chunk)
        if (span and (span[1] - span[0]) < min_dur and merged
                and _chunk_chars(merged[-1]) + _chunk_chars(chunk) <= max_chars):
            merged[-1].extend(chunk)
        else:
            merged.append(chunk)
    if len(merged) > 1:
        span = _cov_span(merged[0])
        if (span and (span[1] - span[0]) < min_dur
                and _chunk_chars(merged[0]) + _chunk_chars(merged[1]) <= max_chars):
            merged[1] = merged[0] + merged[1]
            merged.pop(0)

    out: list[dict] = []
    for chunk in merged:
        span = _cov_span(chunk)
        if span is None:
            continue
        out.append({"start": round(span[0], 3), "end": round(span[1], 3),
                    "text": _join_words(chunk), "words": chunk})
    return out if out else [seg]


def break_segments(segments: list[dict], params: dict[str, float] | None = None) -> list[dict]:
    """segment 列表逐片断行（顺序保持）。"""
    out: list[dict] = []
    for seg in segments:
        out.extend(break_segment(seg, params))
    return out


def main(argv: list[str] | None = None) -> int:
    """CLI：读 words sidecar → 断行 → 写 sidecar+SRT（路径由调用方显式给定）。"""
    import argparse
    import json
    import pathlib

    from .asr_runner import _segments_to_srt

    parser = argparse.ArgumentParser(
        prog="python -m subtransjav.refine.line_breaker",
        description="CT2 长行确定性断行器（words sidecar → 切分后 sidecar+SRT）")
    parser.add_argument("--sidecar", required=True, help="subtransjav.ct2.words/1 sidecar 路径")
    parser.add_argument("--srt-out", required=True, help="断行后 SRT 输出路径")
    parser.add_argument("--sidecar-out", default="",
                        help="断行后 sidecar 输出路径（缺省=<srt-out>.words.json）")
    parser.add_argument("--max-chars", type=int, default=int(POLICY_DEFAULTS["max_chars"]))
    parser.add_argument("--pause-ms", type=int, default=int(POLICY_DEFAULTS["pause_ms"]))
    parser.add_argument("--min-dur-s", type=float, default=float(POLICY_DEFAULTS["min_dur_s"]))
    args = parser.parse_args(argv)
    src = pathlib.Path(args.sidecar)
    data = json.loads(src.read_text(encoding="utf-8"))
    if data.get("schema") != "subtransjav.ct2.words/1":
        print("sidecar schema 不符: " + str(data.get("schema")))
        return 2
    params = {"max_chars": args.max_chars, "pause_ms": args.pause_ms,
              "min_dur_s": args.min_dur_s}
    broken = break_segments(list(data.get("segments") or []), params)
    out_srt = pathlib.Path(args.srt_out)
    out_srt.write_text(_segments_to_srt(broken), encoding="utf-8", newline="\n")
    out_sc = pathlib.Path(args.sidecar_out or (str(out_srt) + ".words.json"))
    out_sc.write_text(json.dumps({**data, "segments": broken,
                                  "broken_by": "line_breaker/1"},
                                 ensure_ascii=False, indent=1),
                      encoding="utf-8")
    print("broken segments: " + str(len(broken)) + " -> " + str(out_srt))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
