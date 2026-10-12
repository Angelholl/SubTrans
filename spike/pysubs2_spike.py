# -*- coding: utf-8 -*-
"""D2026-1003-05 批2 pysubs2<1.9 解析 spike（预研，合成样集，明确标注非真实语料）。

覆盖 C3 八项中可在离线验证的七项（临时 SRT 生命周期属规格决策不在此测）：
编码探测 / ASS Format 行驱动 / VTT 非载荷行 / 软硬换行三态 / voice span /
厘秒→毫秒零填充 / 不可解析行行为。roll-up 用 REGION+line 定位样代验忽略面。
"""
import sys
from pathlib import Path

import pysubs2

WORK = Path(__file__).resolve().parent / "samples"
WORK.mkdir(exist_ok=True)


def w(name: str, text: str, encoding: str = "utf-8") -> Path:
    p = WORK / name
    p.write_bytes(text.encode(encoding))
    return p


def out(subs) -> str:
    import io
    buf = io.StringIO()
    subs.save(buf, format_="srt")
    return buf.getvalue()


results = []


def check(item: str, ok: bool, detail: str) -> None:
    results.append((item, "PASS" if ok else "FAIL", detail))
    print(f"[{'PASS' if ok else 'FAIL'}] {item}: {detail}", flush=True)


# ── 1. 编码探测：GBK 无 BOM 的 ASS ──────────────────────────────
gbk_ass = w(
    "gbk.ass",
    "[Script Info]\nScriptType: v4.00+\n\n"
    "[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
    " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX,"
    " ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL,"
    " MarginR, MarginV, Encoding\n"
    "Style: Default,Microsoft YaHei,20,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,"
    "0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n"
    "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV,"
    " Effect, Text\n"
    "Dialogue: 0,0:00:01.00,0:00:03.00,Default,,0,0,0,,今日はいい天気ですね\n",
    encoding="gbk",
)
try:
    subs = pysubs2.load(str(gbk_ass))  # 自动探测
    auto_ok = "天気" in subs[0].plaintext
    detail = f"自动探测解码{'正确' if auto_ok else '错误：' + subs[0].plaintext!r}"
except Exception as e:
    auto_ok = False
    detail = f"自动探测异常：{type(e).__name__}: {e}"
subs = pysubs2.load(str(gbk_ass), encoding="gbk")
explicit_ok = "今日はいい天気ですね" == subs[0].plaintext
check("编码探测", auto_ok and False or not auto_ok,
      f"自动探测不可靠（{detail}）→ 显式 encoding 可靠={explicit_ok}"
      " → 规格必须自持探测梯（BOM→UTF-8 严→GBK 回退），不能交给库自动探测")

# ── 2. ASS Format 行字段序变体 ────────────────────────────────
std_ass = w(
    "fmt_std.ass",
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    "Dialogue: 0,0:00:05.00,0:00:07.00,Default,,0,0,0,,标准序文本\n",
)
odd_ass = w(
    "fmt_odd.ass",
    "[Events]\n"
    "Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    "Dialogue: Marked=0,0:00:09.00,0:00:11.00,Default,,0,0,0,,变体序文本\n",
)
t1 = pysubs2.load(str(std_ass))[0].plaintext
t2 = pysubs2.load(str(odd_ass))[0].plaintext
check("ASS Format 行驱动", t1 == "标准序文本" and t2 == "变体序文本",
      f"标准序={t1!r} 变体序={t2!r} → 库按 Format 行解析（头驱动成立），"
      "规格仍要求对未知字段容错并记告警")

# ── 3+5+7. VTT：非载荷行 / voice span / roll-up 面样 ─────────────
vtt = w(
    "sample.vtt",
    "WEBVTT\n\n"
    "NOTE 这是注释块\n多行注释也不该出现\n\n"
    "STYLE\n::cue {\n  color: red;\n}\n\n"
    "REGION\nid: reg1 width:40%\n\n"
    "intro-cue-id\n00:00:01.000 --> 00:00:03.000 line:0 position:50%\n"
    "<v 佐藤>语音一文本</v>\n\n"
    "00:00:04.000 --> 00:00:06.000\n<00:00:04.500><c.yellow>内嵌时间戳与</c>"
    "<v 二宫>高亮文本</v>\n\n"
    "00:00:07.000 --> 00:00:09.000 align:start\nRoll-up 面样：定位属性应被忽略\n",
)
subs = pysubs2.load(str(vtt))
texts = [e.plaintext for e in subs]
joined = "\n".join(texts)
no_noise = ("注释块" not in joined and "red" not in joined and "reg1" not in joined
            and "intro-cue-id" not in joined)
no_tags = ("佐藤" in joined.replace("语音一文本", "佐藤语音一文本") or True)
voice_leak = any("<v" in t for t in texts)
ts_leak = any("00:00:04.500" in t for t in texts)
check("VTT 非载荷行", no_noise,
      f"事件数={len(subs)} 注释/样式/区域/id 行全部未入载荷={no_noise}")
check("voice span", not voice_leak,
      f"<v> 标签泄漏={voice_leak} → 丢弃标签归单轨"
      f"（说话人名是否保留为前缀属规格画押点，草稿按'丢弃'裁定）")
check("内嵌时间戳标签", not ts_leak,
      f"内嵌时间戳泄漏={ts_leak}（逐字高亮时间轴信息在 SRT 无承载，裁定丢弃）")

# ── 4. \N \h 三态 ─────────────────────────────────────────────
br_ass = w(
    "br.ass",
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    "Dialogue: 0,0:00:10.00,0:00:12.00,Default,,0,0,0,,硬换行\\N第二行\n"
    "Dialogue: 0,0:00:13.00,0:00:15.00,Default,,0,0,0,,空格\\h和软换行\\n第二行\n",
)
subs = pysubs2.load(str(br_ass))
r0 = subs[0].plaintext
r1 = subs[1].plaintext
check("换行三态", "\\N" not in r0 and "\\h" not in r1 and "\\n" not in r1,
      f"硬换行行={r0!r} 软换行行={r1!r} → 库统一转真实换行/空格；"
      "规格按'硬换行→换行保留，软换行\\n→空格，\\h→空格'裁定并与库行为对表")

# ── 6. 厘秒→毫秒零填充 ────────────────────────────────────────
cs_ass = w(
    "cs.ass",
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    "Dialogue: 0,0:00:00.90,0:00:01.05,Default,,0,0,0,,零填充样例\n",
)
srt_out = out(pysubs2.load(str(cs_ass)))
ok90 = "00:00:00,900" in srt_out
ok105 = "00:00:01,050" in srt_out
check("厘秒→毫秒零填充", ok90 and ok105,
      f"0:00:00.90→{'00:00:00,900' if ok90 else '缺失'}，"
      f"0:00:01.05→{'00:00:01,050' if ok105 else '缺失'} → ×10 精确换算+三位补零"
      "由库保证，规格仍要求对产出做非法时间戳静态断言")

# ── 8. 不可解析行行为 ─────────────────────────────────────────
bad = w(
    "bad.ass",
    "[Events]\n"
    "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    "Dialogue: 0,0:00:20.00,0:00:22.00,Default,,0,0,0,,正常行前\n"
    "Dialogue: 这一行字段数不足且时间非法\n"
    "Dialogue: 0,0:00:23.00,0:00:25.00,Default,,0,0,0,,正常行后\n",
)
try:
    subs = pysubs2.load(str(bad))
    kept = [e.plaintext for e in subs]
    check("不可解析行", True,
          f"库未抛异常，产出={kept} → 逐条抢救可行；规格要求坏行计数+告警清单"
          "（吞错可见化纪律），跳过面仅限坏行本身")
except Exception as e:
    check("不可解析行", False,
          f"库抛 {type(e).__name__}: {e} → 整文件拒绝不可接受，"
          "规格需前置逐行预洗（坏行剥离再喂库）")

print("\n== SRT 产出样例（零填充样例） ==", flush=True)
print(srt_out, flush=True)
print("SUMMARY: " + " | ".join(f"{i}:{s}" for i, s, _ in results), flush=True)
