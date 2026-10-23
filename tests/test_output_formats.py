"""附加成品件（ASS/VTT）出口层测试（d1023 批1，D2026-1023-02）。

口径钉：
- ASS 样式逐字对齐 hardsub._FORCE_STYLE_TEMPLATE（Fontsize=48 为 PlayRes
  1080 基准像素，非 ffmpeg 22 口径）；
- 多行文本必经 SSAEvent.plaintext setter（\\n → \\N）；
- VTT 文本转义 &/< > 由本模块直接断言文件文本，不以 pysubs2 自回读为唯一验证。
"""

from pathlib import Path  # noqa: E402

import pytest

pysubs2 = pytest.importorskip("pysubs2")

from subtransjav.refine.output_formats import (  # noqa: E402
    EXTRA_FORMATS,
    build_extra_text,
    existing_extra_formats,
    sync_extra_outputs,
)


def _entries(*texts, timing=None):
    out = []
    for i, t in enumerate(texts, 1):
        tm = timing or "00:00:01,000 --> 00:00:02,500"
        out.append({"index": i, "timing": tm, "text": t})
    return out


def test_ass_multiline_roundtrip():
    entries = _entries("第一行\n第二行", "single")
    text = build_extra_text("ass", entries)
    ass = pysubs2.SSAFile.from_string(text)
    assert [ev.plaintext for ev in ass.events] == ["第一行\n第二行", "single"]
    # 无裸换行截断 Dialogue 行
    for line in text.splitlines():
        if line.startswith("Dialogue:"):
            assert line.count("\n") == 0


def test_ass_timing_centisecond_tolerance():
    entries = _entries("x", timing="00:00:01,123 --> 00:00:02,567")
    ass = pysubs2.SSAFile.from_string(build_extra_text("ass", entries))
    ev = ass.events[0]
    assert abs(ev.start - 1123) <= 10
    assert abs(ev.end - 2567) <= 10


def test_vtt_timing_exact_ms():
    entries = _entries("x", timing="00:00:01,123 --> 00:00:02,567")
    vtt = pysubs2.SSAFile.from_string(build_extra_text("vtt", entries))
    ev = vtt.events[0]
    assert ev.start == 1123
    assert ev.end == 2567


def test_override_stripped_both_formats():
    entries = _entries("{\\i1}x{\\i}")
    for fmt in EXTRA_FORMATS:
        out = build_extra_text(fmt, entries)
        assert "{\\" not in out, fmt


def test_vtt_html_escape_in_file_text():
    entries = _entries("a & b <b>bold</b>")
    out = build_extra_text("vtt", entries)
    assert "&amp;" in out
    assert "&lt;b&gt;" in out
    assert "<b>" not in out.replace("&lt;b&gt;", "")


def test_zero_duration_normalized():
    entries = _entries("x", timing="00:00:01,000 --> 00:00:01,000")
    vtt = pysubs2.SSAFile.from_string(build_extra_text("vtt", entries))
    assert vtt.events[0].end > vtt.events[0].start
    # ASS 为 centisecond 精度（卡面言明不补偿）：+1ms 同 cs 舍入，断言 end>=start
    ass = pysubs2.SSAFile.from_string(build_extra_text("ass", entries))
    assert ass.events[0].end >= ass.events[0].start


def test_ass_style_snapshot():
    text = build_extra_text("ass", _entries("x"))
    # pysubs2 以 Style: 行输出样式（无 Fontname= 键值对），字体/分辨率直接断言文本
    assert "Microsoft YaHei" in text
    assert "PlayResX: 1920" in text
    assert "PlayResY: 1080" in text
    assert "Arial" not in text
    st = pysubs2.SSAFile.from_string(text).styles["Default"]
    assert st.fontname == "Microsoft YaHei"
    assert st.fontsize == 48
    assert st.bold is True
    assert st.primarycolor == pysubs2.Color(255, 255, 255, 0)  # &H00FFFFFF
    assert st.outlinecolor == pysubs2.Color(0, 0, 0, 0)        # &H00000000
    assert st.borderstyle == 1
    assert st.outline == 2.5
    assert st.shadow == 2.5
    assert st.alignment == 2
    assert (st.marginl, st.marginr, st.marginv) == (10, 10, 20)


def test_sync_empty_formats_noop(tmp_path):
    final = tmp_path / "v_final_cn.srt"
    final.write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n", encoding="utf-8")
    written = sync_extra_outputs(str(final), _entries("x"), ())
    assert written == []
    assert list(tmp_path.glob("*.ass")) == []
    assert list(tmp_path.glob("*.vtt")) == []


def test_existing_extra_formats_probe(tmp_path):
    final = tmp_path / "v_final_cn.srt"
    final.write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n", encoding="utf-8")
    assert existing_extra_formats(str(final)) == ()
    (tmp_path / "v_final_cn.ass").write_text("[Script Info]", encoding="utf-8")
    assert existing_extra_formats(str(final)) == ("ass",)
    (tmp_path / "v_final_cn.vtt").write_text("WEBVTT\n", encoding="utf-8")
    assert existing_extra_formats(str(final)) == ("ass", "vtt")


def test_sync_writes_both(tmp_path):
    final = tmp_path / "v_final_cn.srt"
    final.write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n", encoding="utf-8")
    written = sync_extra_outputs(str(final), _entries("x"), ("ass", "vtt"))
    assert sorted(written) == [str(tmp_path / "v_final_cn.ass"),
                               str(tmp_path / "v_final_cn.vtt")]
    for p in written:
        assert Path(p).read_bytes()[:3] != b"\xef\xbb\xbf"  # UTF-8 无 BOM
