"""
ASS/SSA/VTT → SRT 转换包装层（2.6.4 批2，D2026-1003-05）。

规格依据：docs/design/d264-批2-ASS-VTT-语义映射规格-draft.md（八项决策，
owner 五画押项全按草案）。纯 stdlib + pysubs2（钉 <1.9）。

职责边界：
- 编码探测自持梯（BOM → utf-8 → cp932 → gb18030 → 整文件拒绝），禁用库自动探测；
- 事件清洗：空事件剔除（坏行抢救，含行号+原文明细归属）、相邻 cue 重叠顺延、
  内嵌时间戳标签后洗；
- 产物落输入同目录 `<原名>.<扩展名>.conv.srt`，永久保留（画押④）。

坏行行号明细：2.6.5 段1⑤（D2026-1004-01 正式复评 C7）——pysubs2 解析前对同一份
解码文本逐行预洗提取坏行候选（行号=1-based 物理行号，与编辑器一致），
dropped_empty 事件按 (start,end) 精确→text strip 消歧两步归属。
"""

from __future__ import annotations

import os
import re
import warnings
from pathlib import Path

import pysubs2

# 支持转换的输入扩展名（CLI 显式 -i 放行 + GUI 对话框过滤同口径）
SUPPORTED_EXTS = {".ass", ".ssa", ".vtt"}

# 产出 SRT 时间轴行静态断言（保险带，规格第 6 项）
_SRT_TIMELINE_RE = re.compile(r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$")

# VTT 逐字高亮内嵌时间戳标签（spike 实证库不剥，后洗兜底）
_TS_TAG_RE = re.compile(r"<\d{2}:\d{2}:\d{2}\.\d{3}>")
# 残余 <c> 类标签（库通常已剥，正则兜底）
_C_TAG_RE = re.compile(r"</?c[^>]*>")

# ── 坏行行号明细：预洗候选提取（2.6.5 段1⑤） ─────────────────────────
# ASS 时间戳 H:MM:SS.cc（厘秒；分数部分截断/补齐到毫秒）
_ASS_TS_RE = re.compile(r"(\d+):(\d{1,2}):(\d{1,2})(?:\.(\d+))?")
# VTT 时间戳 MM:SS.mmm / HH:MM:SS.mmm（小时段可省）
_VTT_TS_RE = re.compile(r"(?:(\d+):)?(\d{1,2}):(\d{1,2})(?:\.(\d+))?")
# 告警摘录截断上限（字符）/ 明细条数上限（超出上限聚合）
_EXCERPT_MAX = 40
_DETAIL_LIMIT = 10


def _ts_ms(h: str, m: str, s: str, frac: str | None) -> int:
    """时间戳分量 → 毫秒（与 pysubs2 事件 start/end 同单位，测试实证对齐）。"""
    ms = int(frac[:3].ljust(3, "0")) if frac else 0
    return ((int(h) * 60 + int(m)) * 60 + int(s)) * 1000 + ms


def _parse_ass_ts(raw: str) -> int | None:
    m = _ASS_TS_RE.fullmatch(raw.strip())
    return _ts_ms(m.group(1), m.group(2), m.group(3), m.group(4)) if m else None


def _parse_vtt_ts(raw: str) -> int | None:
    m = _VTT_TS_RE.fullmatch(raw.strip())
    return (_ts_ms(m.group(1) or "0", m.group(2), m.group(3), m.group(4))
            if m else None)


def _ass_candidates(lines: list[str]) -> list[dict]:
    """ASS/SSA 候选提取：[Events] 段内最近一条 Format: 行驱动列映射
    （禁位置硬编码=规格第 2 项同源纪律）；Format 缺失/时间戳解析失败时
    候选退化为仅 (行号, 原文)，不参与 ts 匹配。"""
    cands: list[dict] = []
    cols: list[str] | None = None  # [Events] 段内最近 Format: 行的列名表（小写）
    in_events = False
    for lineno, raw in enumerate(lines, 1):
        s = raw.strip()
        if s.startswith("[") and s.endswith("]"):
            in_events = s.lower() == "[events]"
            continue
        if not in_events or not s:
            continue
        low = s.lower()
        if low.startswith("format:"):
            names = [c.strip().lower() for c in s[len("format:"):].split(",")]
            cols = names if {"start", "end", "text"} <= set(names) else None
            continue
        if not low.startswith("dialogue:"):
            continue
        payload = s[len("dialogue:"):].strip()
        unresolved = {"line": lineno, "start": None, "end": None, "text": payload}
        if cols is None:
            cands.append(unresolved)
            continue
        parts = payload.split(",", maxsplit=len(cols) - 1)
        if len(parts) < len(cols):
            cands.append(unresolved)  # 字段数不足：同时间戳解析失败处理
            continue
        cands.append({"line": lineno,
                      "start": _parse_ass_ts(parts[cols.index("start")]),
                      "end": _parse_ass_ts(parts[cols.index("end")]),
                      "text": parts[cols.index("text")]})
    return cands


def _vtt_candidates(lines: list[str]) -> list[dict]:
    """VTT 候选提取：以含 --> 的时间轴行开块，块内后续非空行 join 为 text；
    候选行号=时间轴行物理行号。"""
    cands: list[dict] = []
    cur: dict | None = None
    for lineno, raw in enumerate(lines, 1):
        s = raw.strip()
        if "-->" in s:
            left, _, right = s.partition("-->")
            head = right.strip().split()
            cur = {"line": lineno, "start": _parse_vtt_ts(left.strip()),
                   "end": _parse_vtt_ts(head[0]) if head else None, "text": ""}
            cands.append(cur)
        elif cur is None:
            continue
        elif s:
            cur["text"] = f"{cur['text']}\n{s}" if cur["text"] else s
        else:
            cur = None  # 空行收块
    return cands


def _prewash_candidates(text: str) -> list[dict]:
    """坏行候选预洗（pysubs2 解析前，同一份 _decode 后文本）：
    splitlines() 统一吃 CRLF/CR/LF，行号=1-based 物理行号。"""
    lines = text.splitlines()
    if any(ln.strip().lower() == "[events]" for ln in lines):
        return _ass_candidates(lines)
    return _vtt_candidates(lines)


def _resolve_dropped(cands: list[dict], ev: pysubs2.SSAEvent) -> dict | None:
    """dropped_empty 事件归属：①(start,end) 精确匹配恰一命中；
    ②多条（重复时间戳）按 text 归一化（strip）过滤恰一命中；否则行号未定。"""
    ts_hits = [c for c in cands
               if c["start"] is not None and c["start"] == ev.start
               and c["end"] == ev.end]
    if len(ts_hits) == 1:
        return ts_hits[0]
    if len(ts_hits) > 1:
        ev_text = ev.text.strip()  # ev 侧取原始 text 字段（转义态）strip
        by_text = [c for c in ts_hits if c["text"].strip() == ev_text]
        if len(by_text) == 1:
            return by_text[0]
    return None


def _excerpt(text: str) -> str:
    t = text.strip()
    return t[:_EXCERPT_MAX] + "…" if len(t) > _EXCERPT_MAX else t


def _dropped_warning(total: int, details: list[dict]) -> str:
    """坏行告警文案：命中条目「第 L 行「摘录」」前 10 条+上限聚合；
    部分未定收尾（其中 K 处行号未定）；全部未定退回旧纯计数文案。"""
    hits = [d for d in details if d["resolved"]]
    if not hits:
        return f"剔除空事件（坏行抢救）×{total}"
    msg = (f"剔除空事件（坏行抢救）×{total}："
           + "、".join(f"第 {d['line']} 行「{d['text']}」" for d in hits[:_DETAIL_LIMIT]))
    if len(hits) > _DETAIL_LIMIT:
        msg += f"（等 {total} 处）"
    unresolved = total - len(hits)
    if unresolved:
        msg += f"（其中 {unresolved} 处行号未定）"
    return msg


class ConvertError(Exception):
    """转换失败（用户可读中文消息；整文件拒绝，不猜拉丁兜底）。"""


def detect_encoding(data: bytes) -> str:
    """编码探测梯（规格第 1 项，画押① CP932 先于 GB18030）。

    ①BOM（utf-8-sig / utf-16-le / utf-16-be）
    → ②utf-8 严格 → ③cp932 严格 → ④gb18030 严格
    → ⑤全部失败抛 ConvertError（消息列尝试明细，吞错可见化）。

    utf-16 BOM 返回 "utf-16-le"/"utf-16-be"（不带 BOM 剥离语义的窄码名），
    解码侧负责剥 BOM 字符。
    """
    if data.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig"
    if data.startswith(b"\xff\xfe"):
        return "utf-16-le"
    if data.startswith(b"\xfe\xff"):
        return "utf-16-be"

    attempts: list[str] = []
    for enc in ("utf-8", "cp932", "gb18030"):
        try:
            data.decode(enc)
        except UnicodeDecodeError as e:
            attempts.append(f"{enc}: {e}")
            continue
        return enc
    raise ConvertError(
        "无法识别字幕文件编码（已尝试 "
        + "；".join(attempts)
        + "），请另存为 UTF-8 后重试")


def _decode(data: bytes) -> tuple[str, str]:
    """按探测梯解码并处理 BOM；返回 (文本, 编码名)。"""
    enc = detect_encoding(data)
    if enc in ("utf-16-le", "utf-16-be"):
        # 窄码名不剥 BOM，显式剥掉前导 \ufeff
        return data.decode(enc).lstrip("\ufeff"), enc
    return data.decode(enc), enc


def convert_file(input_path: str) -> dict:
    """转换单个 ASS/SSA/VTT 文件为 SRT。

    返回 {"srt_path", "warnings", "dropped_empty", "dropped_details",
    "shifted_overlaps", "stripped_tags"}；解析失败/编码不可识别抛
    ConvertError 整文件拒绝。
    """
    path = Path(input_path)
    text, _enc = _decode(path.read_bytes())

    # 坏行候选预洗（2.6.5 段1⑤）：pysubs2 解析前对同一份文本逐行扫描
    dropped_cands = _prewash_candidates(text)

    # 解析（格式自动识别）；解析期 RuntimeWarning 计入告警（规格第 2 项）
    parse_warns: list[str] = []
    try:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            subs = pysubs2.SSAFile.from_string(text)
        parse_warns = [f"解析警告: {w.message}" for w in caught
                       if issubclass(w.category, RuntimeWarning)]
    except Exception as e:  # noqa: BLE001 - 任何库内解析异常统一转用户可读拒绝
        raise ConvertError(
            f"字幕解析失败（{path.name}）：{type(e).__name__}: {e}") from e

    # 事件清洗①：plaintext 为空的事件剔除（坏行被库静默跳过但留空事件，
    # spike 实证）——逐条抢救语义，剔除计数+行号/原文明细进告警与返回 dict
    kept: list[pysubs2.SSAEvent] = []
    dropped_empty = 0
    dropped_details: list[dict] = []
    for ev in sorted(subs.events, key=lambda e: (e.start, e.end)):
        if not ev.plaintext:
            dropped_empty += 1
            hit = _resolve_dropped(dropped_cands, ev)
            dropped_details.append(
                {"line": hit["line"], "text": _excerpt(hit["text"]),
                 "resolved": True}
                if hit else
                {"line": None, "text": ev.text.strip(), "resolved": False})
            continue
        kept.append(ev)

    # 事件清洗②：相邻 cue 重叠修正——前一 end > 后一 start 时后一 start
    # 顺延至前一 end（方向写死，end 不动），修正计数（规格第 6 项）
    shifted_overlaps = 0
    for prev, cur in zip(kept, kept[1:], strict=False):
        if prev.end > cur.start:
            cur.start = prev.end
            shifted_overlaps += 1

    # 事件清洗③：内嵌时间戳标签剥除 + 残余 <c> 类标签兜底（规格第 7 项，
    # spike 实证库不剥时间戳标签）；voice span 说话人名随库丢弃不处理
    stripped_tags = 0
    for ev in kept:
        cleaned, n1 = _TS_TAG_RE.subn("", ev.plaintext)
        cleaned, n2 = _C_TAG_RE.subn("", cleaned)
        if n1 or n2:
            stripped_tags += n1 + n2
            # plaintext setter 把真实换行重转义为 \N，SRT 导出安全还原
            ev.plaintext = cleaned

    subs.events = kept

    # 导出 SRT + 逐条时间轴行静态断言（保险带，不匹配整文件拒绝）
    out_text = subs.to_string(format_="srt")
    bad_lines = [ln for ln in out_text.splitlines()
                 if "-->" in ln and not _SRT_TIMELINE_RE.match(ln)]
    if bad_lines:
        raise ConvertError(
            f"产出时间轴校验失败（{path.name}）：{bad_lines[:3]}")

    # 落盘：输入同目录 `<原名>.<扩展名>.conv.srt`（UTF-8，覆盖旧件，
    # 永久保留——画押④；重跑幂等指向同一文件）
    srt_path = path.with_name(path.name + ".conv.srt")
    with open(srt_path, "w", encoding="utf-8", newline="") as f:
        f.write(out_text)

    conv_warns = list(parse_warns)
    if dropped_empty:
        conv_warns.append(_dropped_warning(dropped_empty, dropped_details))
    if shifted_overlaps:
        conv_warns.append(f"相邻重叠顺延修正 ×{shifted_overlaps}")
    if stripped_tags:
        conv_warns.append(f"剥离内嵌时间戳/残余标签 ×{stripped_tags}")

    return {"srt_path": str(srt_path),
            "warnings": conv_warns,
            "dropped_empty": dropped_empty,
            "dropped_details": dropped_details,
            "shifted_overlaps": shifted_overlaps,
            "stripped_tags": stripped_tags}


def convert_inputs(paths: list[str]) -> tuple[list[str], list[str]]:
    """批处理助手：SUPPORTED_EXTS 内逐个 convert_file，其余原样透传。

    返回 (新路径表, 汇总 warning 行表)；warning 行带源文件名前缀供 CLI 逐行
    打印。转换失败（ConvertError）向上抛出，由调用方决定终止语义。
    """
    new_paths: list[str] = []
    warn_lines: list[str] = []
    for p in paths:
        ext = os.path.splitext(p)[1].lower()
        if ext not in SUPPORTED_EXTS:
            new_paths.append(p)
            continue
        result = convert_file(p)
        new_paths.append(result["srt_path"])
        for w in result["warnings"]:
            warn_lines.append(f"{os.path.basename(p)}: {w}")
    return new_paths, warn_lines
