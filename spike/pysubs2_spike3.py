# -*- coding: utf-8 -*-
"""pysubs2 spike 补测：不可解析行行为（C3 第 8 项前半）。"""
from pathlib import Path

import pysubs2

WORK = Path(__file__).resolve().parent / "samples"
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
p = WORK / "bad.ass"
p.write_text(
    HDR + EVFMT
    + "Dialogue: 0,0:00:20.00,0:00:22.00,Default,,0,0,0,,正常行前\n"
    + "Dialogue: 这一行字段数不足且时间非法\n"
    + "Dialogue: 0,0:00:23.00,0:00:25.00,Default,,0,0,0,,正常行后\n",
    encoding="utf-8",
)
try:
    subs = pysubs2.load(str(p))
    kept = [e.plaintext for e in subs]
    print(f"未抛异常，产出={kept}")
    print("结论：逐条抢救可行（坏行被静默跳过）→ 规格要求转换包装层做坏行"
          "计数+告警清单，补齐吞错可见化")
except Exception as e:
    print(f"抛 {type(e).__name__}: {e}")
    print("结论：整文件拒绝不可接受 → 规格需前置逐行预洗（坏行剥离再喂库）")
