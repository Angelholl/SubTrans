"""附加成品件出口层：终稿 SRT 之外的 ASS/VTT 平行附加写出（D2026-1023-02）。

一致性契约：附加件一经产生，任何终稿写点同步再生（cfg 旗标 ∪ 已存在
附加件）；写点不凭空新增。本模块不拼产物名：``sync_extra_outputs`` 的
``final_path`` 由调用方经 ``final_stem`` 契约传入。
"""

from __future__ import annotations

import re

import pysubs2

from .fs_utils import _atomic_write_text

EXTRA_FORMATS = ("ass", "vtt")

# 出口前剥残留 override 标签（两格式同规则）：{\...}
_OVERRIDE_RE = re.compile(r"\{\\[^}]*\}")

# 样式逐字对齐 hardsub._FORCE_STYLE_TEMPLATE（HRO-3 冻结串）；Fontsize=48
# 为 PlayRes 1080 基准像素口径（ffmpeg 模板默认 22 属像素口径，不通用），
# 口径钉死在 tests/test_output_formats.py。
_ASS_FONTNAME = "Microsoft YaHei"
_ASS_FONTSIZE = 48
_ASS_PLAY_RES = (1920, 1080)

_TIMING_MS_FMT = "%d:%02d:%02d,%03d"


def _timing_to_ms(timing: str) -> tuple[int, int]:
    """``HH:MM:SS,mmm --> HH:MM:SS,mmm`` → (start_ms, end_ms)。"""
    left, right = timing.split("-->")
    parts = [int(x) for x in left.strip().replace(",", ":").split(":")]
    start = parts[0] * 3600000 + parts[1] * 60000 + parts[2] * 1000 + parts[3]
    parts = [int(x) for x in right.strip().replace(",", ":").split(":")]
    end = parts[0] * 3600000 + parts[1] * 60000 + parts[2] * 1000 + parts[3]
    return start, end


def _clean_text(text: str) -> str:
    return _OVERRIDE_RE.sub("", text or "")


def _make_events(entries) -> list[pysubs2.SSAEvent]:
    events = []
    for e in entries:
        start, end = _timing_to_ms(e["timing"])
        if end <= start:            # 零时长规范化（VTT 规范 end>start）
            end = start + 1
        ev = pysubs2.SSAEvent(start=start, end=end)
        ev.plaintext = _clean_text(e["text"])   # setter：\n → \N
        events.append(ev)
    return events


def _build_ass(entries) -> str:
    f = pysubs2.SSAFile()
    # PlayRes 序列化走 info 字典（pysubs2 实证：属性赋值不落盘）
    f.info["PlayResX"] = str(_ASS_PLAY_RES[0])
    f.info["PlayResY"] = str(_ASS_PLAY_RES[1])
    f.styles["Default"] = pysubs2.SSAStyle(
        fontname=_ASS_FONTNAME,
        fontsize=_ASS_FONTSIZE,
        bold=True,
        primarycolor=pysubs2.Color(255, 255, 255, 0),   # &H00FFFFFF
        outlinecolor=pysubs2.Color(0, 0, 0, 0),         # &H00000000
        borderstyle=1,
        outline=2.5,
        shadow=2.5,
        alignment=2,
        marginl=10,
        marginr=10,
        marginv=20,
        encoding=1,
    )
    f.events = _make_events(entries)
    return f.to_string("ass")


def _vtt_escape(text: str) -> str:
    return (text.replace("&", "&amp;")
                .replace("<", "&lt;")
                .replace(">", "&gt;"))


def _build_vtt(entries) -> str:
    f = pysubs2.SSAFile()
    f.events = []
    for e in entries:
        start, end = _timing_to_ms(e["timing"])
        if end <= start:
            end = start + 1
        ev = pysubs2.SSAEvent(start=start, end=end)
        ev.plaintext = _clean_text(e["text"])   # setter：\n → \N
        # pysubs2 VTT writer 不做 HTML 转义（实证），对已成形的 \N 串补转义
        ev.text = _vtt_escape(ev.text)
        f.events.append(ev)
    return f.to_string("vtt")


def build_extra_text(fmt: str, entries: list[dict]) -> str:
    """entries（parse_srt 同构 ``{"index","timing","text"}``）→ ASS/VTT 文本。"""
    if fmt == "ass":
        return _build_ass(entries)
    if fmt == "vtt":
        return _build_vtt(entries)
    raise ValueError(f"未知附加格式: {fmt}")


def existing_extra_formats(final_path: str) -> tuple[str, ...]:
    """同目录 ``{去.srt名}.ass/.vtt`` 在场探测（再生存量旗标）。"""
    from pathlib import Path

    base = Path(final_path).with_suffix("")
    found = tuple(fmt for fmt in EXTRA_FORMATS
                  if base.with_suffix(f".{fmt}").is_file())
    return found


def sync_extra_outputs(final_path: str, entries, formats) -> list[str]:
    """按 formats 平行写出附加成品件（原子写，UTF-8 无 BOM）。

    formats 空 → no-op 返回 []。返回实际写出的路径列表。
    """
    if not formats:
        return []
    from pathlib import Path

    base = Path(final_path).with_suffix("")
    written = []
    for fmt in formats:
        out = base.with_suffix(f".{fmt}")
        _atomic_write_text(str(out), build_extra_text(fmt, entries))
        written.append(str(out))
    return written
