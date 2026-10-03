# -*- coding: utf-8 -*-
"""pysubs2 spike 修订轮：补 [Script Info] 头 + to_string 输出 + 非空断言防假通过。"""
from pathlib import Path

import pysubs2

WORK = Path(__file__).resolve().parent / "samples"
WORK.mkdir(exist_ok=True)
HDR = (
    "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
    " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX,"
    " ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL,"
    " MarginR, MarginV, Encoding\n"
    "Style: Default,Microsoft YaHei,20,&H00FFFFFF,&H000000FF,&H00000000,"
    "&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n[Events]\n"
)
EVFMT = ("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV,"
         " Effect, Text\n")


def w(name: str, text: str, encoding: str = "utf-8") -> Path:
    p = WORK / name
    p.write_bytes(text.encode(encoding))
    return p


# 2. Format 行驱动（带完整头）
w("fmt_std.ass", HDR + EVFMT
  + "Dialogue: 0,0:00:05.00,0:00:07.00,Default,,0,0,0,,标准序文本\n")
w("fmt_odd.ass", HDR.replace("v4.00+", "v4.00")
  + "Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV,"
    " Effect, Text\n"
  + "Dialogue: Marked=0,0:00:09.00,0:00:11.00,Default,,0,0,0,,变体序文本\n")
t1 = pysubs2.load(str(WORK / "fmt_std.ass"))[0].plaintext
t2 = pysubs2.load(str(WORK / "fmt_odd.ass"))[0].plaintext
ok = t1 == "标准序文本" and t2 == "变体序文本"
print(f"[{'PASS' if ok else 'FAIL'}] Format 行驱动: std={t1!r} odd={t2!r}")

# 4. 换行三态（带完整头）
bs_n = chr(92) + "N"      # 字面 \N
bs_h = chr(92) + "h"      # 字面 \h
bs_ln = chr(92) + "n"     # 字面 \n
w("br.ass", HDR + EVFMT
  + f"Dialogue: 0,0:00:10.00,0:00:12.00,Default,,0,0,0,,硬换行{bs_n}第二行\n"
  + f"Dialogue: 0,0:00:13.00,0:00:15.00,Default,,0,0,0,,空格{bs_h}和软换行{bs_ln}第二行\n")
subs = pysubs2.load(str(WORK / "br.ass"))
r0, r1 = subs[0].plaintext, subs[1].plaintext
ok = (bool(r0) and bool(r1) and bs_n not in r0
      and bs_h not in r1 and bs_ln not in r1)
print(f"[{'PASS' if ok else 'FAIL'}] 换行三态: 硬={r0!r} 软={r1!r}（非空断言防假通过）")

# 5b. <c> 标签与内嵌时间戳标签泄漏明细
vtt = WORK / "sample.vtt"
subs = pysubs2.load(str(vtt))
for e in subs:
    print(f"  VTT 事件 plaintext={e.plaintext!r}")

# 6. 厘秒→毫秒零填充（to_string 修正）
w("cs.ass", HDR + EVFMT
  + "Dialogue: 0,0:00:00.90,0:00:01.05,Default,,0,0,0,,零填充样例\n")
srt_out = pysubs2.load(str(WORK / "cs.ass")).to_string(format_="srt")
ok90 = "00:00:00,900" in srt_out
ok105 = "00:00:01,050" in srt_out
print(f"[{'PASS' if ok90 and ok105 else 'FAIL'}] 厘秒→毫秒零填充:"
      f" ,900={ok90} ,050={ok105}")
print("== SRT 产出 ==")
print(srt_out)
