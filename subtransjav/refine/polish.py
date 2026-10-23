"""翻译后确定性字幕清洗层（polish）：文本规范化 + 时间轴钳制。

设计口径（D2026-1023-03）：
- 纯函数：不修改入参，深拷贝后操作，返回（新条目列表, stats）。
- 非破坏优先：时间轴只做收缩式钳制；不延长显示时长、不填充间隙
  （CPS 行动化=HRO 剔除项，本模块无任何此类逻辑）。
- 默认值单一真值源：全部集中在 POLICY_DEFAULTS，D5 校准门内为 PROVISIONAL。
- 零依赖：只 import 标准库（不得 import pipeline_v2 / config / api）。

条目结构与 filters.parse_srt 同构：
``{"index": int, "timing": "HH:MM:SS,mmm --> HH:MM:SS,mmm", "text": str}``
"""

import copy
import math
import re
import unicodedata

#: 清洗策略默认值（D5 校准门）——全部默认值只在此表，严禁散落硬编码。
#: 每条 PROVISIONAL 均为占位：owner 提供 SE 成品样例后单点改默认，不声称已定标。
POLICY_DEFAULTS: dict = {
    "strip_final_period": True,  # PROVISIONAL（D5 校准门，owner SE 成品样例到达后单点改默认）
    "quote_style": "corner",  # PROVISIONAL（D5 校准门，owner SE 成品样例到达后单点改默认）
    "max_line_chars": 16,  # PROVISIONAL（D5 校准门，owner SE 成品样例到达后单点改默认）
    "max_lines": 2,  # PROVISIONAL（D5 校准门，owner SE 成品样例到达后单点改默认）
    "min_duration_ms": 833,  # PROVISIONAL（D5 校准门，owner SE 成品样例到达后单点改默认）
    "max_duration_ms": 7000,  # PROVISIONAL（D5 校准门，owner SE 成品样例到达后单点改默认）
    "min_gap_ms": 83.416,  # PROVISIONAL（D5 校准门，owner SE 成品样例到达后单点改默认）
    "remove_dialogue_gt": False,  # PROVISIONAL（D5 校准门，owner SE 成品样例到达后单点改默认）
    "extend_short_into_gap": False,  # PROVISIONAL（D5 校准门，owner SE 成品样例到达后单点改默认）
}

#: stats 键（批3 报告消费，命名钉死）
STATS_KEYS = (
    "whitespace_collapsed",
    "music_fixed",
    "italic_tags_reported",
    "i_tags_repaired",
    "gt_removed",
    "periods_stripped",
    "quotes_normalized",
    "lines_rewrapped",
    "long_clamped",
    "short_reported",
    "overlaps_resolved",
    "gaps_enforced",
    "dropped_empty",
)

#: 引号派系：corner=「」/ curly=“”；keep=完全不动（不入此表）。
_QUOTE_PAIRS = {
    "corner": ("「", "」"),
    "curly": ("“", "”"),
}
_QUOTE_STYLES = frozenset({"corner", "keep", "curly"})
_QUOTE_OPENERS = frozenset({'"', "“", "「"})
_QUOTE_CLOSERS = frozenset({'"', "”", "」"})

#: ♪ 的编码乱码序列（UTF-8 字节 E2 99 AA 被按 latin-1/cp1252 误读）；只修不删。
_MUSIC_MOJIBAKE = ("â™ª", "â\x99ª")

#: 软折行断点：句读与闭括号之后、以及空格处。
_BREAK_AFTER = frozenset("、。，！？；：…—）」』】,.;:!?)]}")

_ITALIC_TAG_RE = re.compile(r"</?i>")

_TIMING_RE = re.compile(
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{1,2}):(\d{2}):(\d{2})[,.](\d{3})"
)


def _char_width(char):
    """全角当量宽度：CJK 汉字/CJK 标点=1.0，ASCII/半角=0.5。"""
    return 1.0 if unicodedata.east_asian_width(char) in ("W", "F") else 0.5


def _text_width(text):
    return sum(_char_width(char) for char in text)


def _repair_italic(text):
    """只修残缺 <i>：补缺失闭标签、删孤儿闭标签；成对完整标签原样不动。

    返回 ``(text, added, removed, had_pair)``。
    """
    pieces = []
    depth = 0
    added = 0
    removed = 0
    had_pair = False
    pos = 0
    for match in _ITALIC_TAG_RE.finditer(text):
        pieces.append(text[pos:match.start()])
        if match.group(0) == "<i>":
            depth += 1
            pieces.append("<i>")
        elif depth > 0:
            depth -= 1
            had_pair = True
            pieces.append("</i>")
        else:
            removed += 1
            pos = match.end()
            continue
        pos = match.end()
    pieces.append(text[pos:])
    if depth:
        pieces.append("</i>" * depth)
        added += depth
    return "".join(pieces), added, removed, had_pair


def _normalize_quotes(line, style):
    """把成对直引号/弯引号/直角引号引段统一为目标派系；不成对则整行不动。

    返回 ``(line, changed_marks)``，changed_marks 计入 stats.quotes_normalized。
    """
    open_quote, close_quote = _QUOTE_PAIRS[style]
    pieces = []
    depth = 0
    changed = 0
    for char in line:
        if char == '"' and depth == 1:
            pieces.append(close_quote)
            changed += close_quote != char
            depth = 0
        elif char in _QUOTE_OPENERS:
            if depth == 0:
                pieces.append(open_quote)
                changed += open_quote != char
                depth = 1
            else:
                pieces.append(char)
        elif char in _QUOTE_CLOSERS:
            if depth == 1:
                pieces.append(close_quote)
                changed += close_quote != char
                depth = 0
            else:
                pieces.append(char)
        else:
            pieces.append(char)
    if depth:
        return line, 0
    return "".join(pieces), changed


def _wrap_lines(lines, max_chars, max_lines):
    """把逻辑行软折为 ≤max_lines 行，优先自然断点，放不下时取最优断点强拆。

    返回 ``(new_lines, forced)``；forced=True 表示仍存在超宽行（极端超长）。
    """
    joined = ""
    natural = set()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if joined:
            natural.add(len(joined))
        joined += line
    if not joined:
        return [""], False
    for idx, char in enumerate(joined):
        if char in _BREAK_AFTER:
            natural.add(idx + 1)
        elif char == " ":
            natural.add(idx)

    # 不在 <i>/</i> 标签内部断行
    forbidden: set = set()
    for match in _ITALIC_TAG_RE.finditer(joined):
        forbidden.update(range(match.start() + 1, match.end()))

    prefix = [0.0]
    for char in joined:
        prefix.append(prefix[-1] + _char_width(char))

    def range_width(start, end):
        while start < end and joined[start] == " ":
            start += 1
        while end > start and joined[end - 1] == " ":
            end -= 1
        return prefix[end] - prefix[start]

    total = len(joined)
    max_parts = min(max_lines, total)
    fallback = None
    for parts in range(1, max_parts + 1):
        # dp[part][end] = (over, unnatural, max_width, start)
        dp: list = [[None] * (total + 1) for _ in range(parts + 1)]
        dp[0][0] = (0, 0, 0.0, -1)
        for part in range(1, parts + 1):
            for end in range(1, total + 1):
                best = None
                for start in range(part - 1, end):
                    prev = dp[part - 1][start]
                    if prev is None or start in forbidden:
                        continue
                    width = range_width(start, end)
                    if width <= 0:
                        continue
                    max_width = max(prev[2], width)
                    over = 1 if max_width > max_chars else 0
                    unnatural = prev[1] + (0 if start == 0 or start in natural else 1)
                    cand = (over, unnatural, max_width, start)
                    if best is None or (cand[0], cand[1], cand[2]) < (best[0], best[1], best[2]):
                        best = cand
                dp[part][end] = best
        cell = dp[parts][total]
        if cell is None:
            continue
        result = cell
        new_lines = []
        end = total
        for part in range(parts, 0, -1):
            start = dp[part][end][3]
            new_lines.append(joined[start:end].strip())
            end = start
        new_lines.reverse()
        fallback = (new_lines, result[0] == 1)
        if result[0] == 0:
            return fallback
    if fallback is None:
        return [joined], True
    return fallback


def _polish_text(text, policy, stats):
    """文本层白名单规则：返回清洗后 text（可能为空串=应删除该条）。"""
    raw_lines = (text or "").split("\n")
    lines = []
    whitespace_changed = False
    for raw in raw_lines:
        collapsed = re.sub(r"[ \t]+", " ", raw).strip()
        if collapsed != raw:
            whitespace_changed = True
        if collapsed:
            lines.append(collapsed)
    if whitespace_changed:
        stats["whitespace_collapsed"] += 1

    working = "\n".join(lines)

    # 规则 2：♪ 乱码修复（绝不删除 ♪）
    for mojibake in _MUSIC_MOJIBAKE:
        count = working.count(mojibake)
        if count:
            working = working.replace(mojibake, "♪")
            stats["music_fixed"] += count

    # 规则 3：<i> 只修残缺；成对完整不动、只报告
    working, added, removed, had_pair = _repair_italic(working)
    if had_pair:
        stats["italic_tags_reported"] += 1
    if added or removed:
        stats["i_tags_repaired"] += added + removed

    # 规则 4：行首 >> 仅在显式开启时删除
    if policy["remove_dialogue_gt"]:
        rebuilt = []
        for line in working.split("\n"):
            stripped, count = re.subn(r"^>>\s*", "", line)
            stats["gt_removed"] += count
            if stripped:
                rebuilt.append(stripped)
        working = "\n".join(rebuilt)

    # 规则 5：只去行末「。」，？！…等一律不动
    if policy["strip_final_period"]:
        rebuilt = []
        for line in working.split("\n"):
            count = 0
            while line.endswith("。"):
                line = line[:-1]
                count += 1
            stats["periods_stripped"] += count
            if line:
                rebuilt.append(line)
        working = "\n".join(rebuilt)

    # 规则 6：引号派系统一
    style = policy["quote_style"]
    if style != "keep":
        rebuilt = []
        for line in working.split("\n"):
            line, count = _normalize_quotes(line, style)
            stats["quotes_normalized"] += count
            rebuilt.append(line)
        working = "\n".join(rebuilt)

    # 规则 7：拆行重排（已 ≤max_lines 时不再触发，保证幂等）
    max_chars = int(policy["max_line_chars"])
    max_lines = int(policy["max_lines"])
    lines = [line for line in working.split("\n") if line]
    needs_wrap = len(lines) > max_lines or (
        len(lines) < max_lines and any(_text_width(line) > max_chars for line in lines)
    )
    if needs_wrap and lines:
        lines, _forced = _wrap_lines(lines, max_chars, max_lines)
        stats["lines_rewrapped"] += 1
    return "\n".join(lines)


def _parse_timing(timing):
    match = _TIMING_RE.search(timing or "")
    if not match:
        return None
    hour, minute, second, milli, hour2, minute2, second2, milli2 = match.groups()
    start = ((int(hour) * 60 + int(minute)) * 60 + int(second)) * 1000 + int(milli)
    end = ((int(hour2) * 60 + int(minute2)) * 60 + int(second2)) * 1000 + int(milli2)
    return start, end


def _format_ms(ms):
    ms = max(0, int(ms))
    hour, rem = divmod(ms, 3_600_000)
    minute, rem = divmod(rem, 60_000)
    second, milli = divmod(rem, 1000)
    return f"{hour:02d}:{minute:02d}:{second:02d},{milli:03d}"


def _shrink_before(prev, cur, gap):
    """前条 end 回拉到后条 start − gap；会致零/负时长则改为后条 start 后推。

    后推分支仅在为避免零/负时长时把后条 end 撑到 +1ms 防御，不填充空闲间隙。
    """
    prev_start, prev_end = prev
    cur_start, cur_end = cur
    target = int(math.floor(cur_start - gap))
    if target > prev_start:
        return (prev_start, target), (cur_start, cur_end)
    new_start = int(math.ceil(prev_end + gap))
    if new_start >= cur_end:
        cur_end = new_start + 1
    return (prev_start, prev_end), (new_start, cur_end)


def _polish_timings(entries, policy, stats):
    """时间轴层：顺序定死 ① 重叠消解 → ② 时长钳制 → ③ 最小间隔。"""
    gap = float(policy["min_gap_ms"])
    max_duration = int(policy["max_duration_ms"])
    min_duration = int(policy["min_duration_ms"])
    original = [_parse_timing(entry.get("timing", "")) for entry in entries]
    spans = list(original)

    # ① 重叠消解
    for idx in range(1, len(spans)):
        prev, cur = spans[idx - 1], spans[idx]
        if prev is None or cur is None:
            continue
        if prev[1] > cur[0]:
            spans[idx - 1], spans[idx] = _shrink_before(prev, cur, gap)
            stats["overlaps_resolved"] += 1

    # ② 时长钳制：超长缩短；过短只报告不延长（D8）
    for idx, span in enumerate(spans):
        if span is None:
            continue
        start, end = span
        if end - start > max_duration:
            end = start + max_duration
            stats["long_clamped"] += 1
        if end - start < min_duration:
            stats["short_reported"] += 1
        spans[idx] = (start, end)

    # ③ 最小间隔保证
    for idx in range(1, len(spans)):
        prev, cur = spans[idx - 1], spans[idx]
        if prev is None or cur is None:
            continue
        if cur[0] - prev[1] < gap:
            spans[idx - 1], spans[idx] = _shrink_before(prev, cur, gap)
            stats["gaps_enforced"] += 1

    # 兜底：任何残留零/负时长（不可解析时间轴不参与改写）
    for idx, span in enumerate(spans):
        if span is not None and span[1] <= span[0]:
            spans[idx] = (span[0], span[0] + 1)

    for entry, span, before in zip(entries, spans, original, strict=False):
        if span is None or before is None or span == before:
            continue
        entry["timing"] = f"{_format_ms(span[0])} --> {_format_ms(span[1])}"


def _assert_invariants(entries, max_lines):
    """出口不变量：无空条目、无零/负时长、无重叠、每条目 ≤max_lines 行。"""
    for entry in entries:
        assert entry["text"].strip(), "polish 出口不变量：空条目未删除"
        span = _parse_timing(entry["timing"])
        assert span is not None, "polish 出口不变量：时间轴不可解析"
        assert span[1] > span[0], "polish 出口不变量：零/负时长"
        assert len(entry["text"].split("\n")) <= max_lines, "polish 出口不变量：行数超限"
    for prev, cur in zip(entries, entries[1:], strict=False):
        assert _parse_timing(prev["timing"])[1] <= _parse_timing(cur["timing"])[0], (
            "polish 出口不变量：相邻条目重叠"
        )


def polish_entries(entries, options=None):
    """清洗条目列表：返回（新条目列表, stats），入参不被修改。

    options 为覆盖 POLICY_DEFAULTS 的扁平 dict（None=全默认）；未知键忽略。
    extend_short_into_gap 为占位参数：本轮不实现任何延长/填充间隙行为。
    """
    policy = dict(POLICY_DEFAULTS)
    if options:
        policy.update({key: value for key, value in options.items() if key in POLICY_DEFAULTS})
    if policy["quote_style"] not in _QUOTE_STYLES:
        raise ValueError(f"不支持的 quote_style：{policy['quote_style']!r}")

    stats = {key: 0 for key in STATS_KEYS}
    working = copy.deepcopy(list(entries or []))
    kept = []
    for entry in working:
        text = _polish_text(entry.get("text", ""), policy, stats)
        if not text:
            stats["dropped_empty"] += 1
            continue
        entry["text"] = text
        kept.append(entry)

    _polish_timings(kept, policy, stats)
    _assert_invariants(kept, int(policy["max_lines"]))
    return kept, stats
