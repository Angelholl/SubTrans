"""
Tests for ASS/VTT → SRT subtitle conversion layer (2.6.4 批2, D2026-1003-05).

纯 tmp_path 样本内联构造，不留外部痕迹；样本构造参照
D:/SubTrans-d264-pre/spike/pysubs2_spike2.py（[Script Info] 头必须带，
否则 pysubs2 解析异常）。
"""

import os
import re
import sys
from pathlib import Path

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ASS 最小样本头（spike 实证：缺 [Script Info] 头解析失败）
_HDR = (
    "[Script Info]\nScriptType: v4.00+\n\n[V4+ Styles]\n"
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
    " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX,"
    " ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL,"
    " MarginR, MarginV, Encoding\n"
    "Style: Default,Microsoft YaHei,20,&H00FFFFFF,&H000000FF,&H00000000,"
    "&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1\n\n[Events]\n"
)
_EVFMT = ("Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV,"
          " Effect, Text\n")

_SRT_TIMELINE_RE = re.compile(
    r"^\d{2}:\d{2}:\d{2},\d{3} --> \d{2}:\d{2}:\d{2},\d{3}$")


def _write(path: Path, text: str, encoding: str = "utf-8") -> Path:
    path.write_bytes(text.encode(encoding))
    return path


# ── ① 编码探测梯 ─────────────────────────────────────────────────────


class TestDetectEncoding:
    def test_utf8_plain(self):
        from subtransjav.refine.subtitle_convert import detect_encoding
        assert detect_encoding("1\n00:00:01,000 --> 00:00:02,000\n中文\n"
                               .encode()) == "utf-8"

    def test_utf8_bom(self):
        from subtransjav.refine.subtitle_convert import detect_encoding
        assert detect_encoding("字幕\n".encode("utf-8-sig")) == "utf-8-sig"

    def test_cp932(self):
        # 样本含 "、"（cp932 字节 0x81 0x41）→ 严格 utf-8 必败，落到 cp932
        from subtransjav.refine.subtitle_convert import detect_encoding
        data = "こんにちは、字幕\n".encode("cp932")
        assert detect_encoding(data) == "cp932"
        assert data.decode("cp932") == "こんにちは、字幕\n"

    def test_gb18030(self):
        # 样本含 BMP 外字符（gb18030 四字节序列）→ utf-8/cp932 均严格失败
        from subtransjav.refine.subtitle_convert import detect_encoding
        data = "𠀀中文测试\n".encode("gb18030")
        assert detect_encoding(data) == "gb18030"
        assert data.decode("gb18030") == "𠀀中文测试\n"

    def test_undecodable_raises_with_attempts(self):
        # b"\x81\x39"：utf-8 非法起始 / cp932 非法序列 / gb18030 不完整序列
        from subtransjav.refine.subtitle_convert import (
            ConvertError,
            detect_encoding,
        )
        with pytest.raises(ConvertError) as ei:
            detect_encoding(b"\x81\x39")
        msg = str(ei.value)
        assert "utf-8" in msg and "cp932" in msg and "gb18030" in msg


# ── ② VTT 内嵌时间戳标签剥除 ─────────────────────────────────────────


class TestVttTimestampTagStrip:
    def test_timestamp_tag_stripped_and_counted(self, tmp_path):
        from subtransjav.refine.subtitle_convert import convert_file
        p = _write(tmp_path / "sample.vtt", (
            "WEBVTT\n"
            "\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "<00:00:01.500><c.yellow>内嵌时间戳与</c>高亮文本\n"
        ))
        res = convert_file(str(p))
        out = Path(res["srt_path"]).read_text(encoding="utf-8")
        assert "<00:00:01.500>" not in out          # spike 实证泄漏点已兜底
        assert "<c." not in out and "</c>" not in out
        assert "内嵌时间戳与高亮文本" in out
        assert res["stripped_tags"] >= 1
        assert any("剥离内嵌时间戳/残余标签" in w for w in res["warnings"])


# ── ③ 空事件剔除（坏行抢救） ─────────────────────────────────────────


class TestEmptyEventDrop:
    def test_bad_dialogue_line_dropped_and_counted(self, tmp_path):
        """畸形坏行（预洗时间戳解析失败）→ 候选不参与 ts 匹配，行号未定，
        告警退回纯计数兜底文案、dropped_details 记 resolved=False。
        2.6.5 段1⑤ 行号明细特性的预期行为变更：可解析坏行才升级为
        「第 L 行「摘录」」明细（见 TestBadLineDetail* 各用例）。"""
        from subtransjav.refine.subtitle_convert import convert_file
        p = _write(tmp_path / "bad.ass", _HDR + _EVFMT
                   + "Dialogue: 0,0:00:20.00,0:00:22.00,Default,,0,0,0,,正常行前\n"
                   + "Dialogue: 这一行字段数不足且时间非法\n"
                   + "Dialogue: 0,0:00:23.00,0:00:25.00,Default,,0,0,0,,正常行后\n")
        res = convert_file(str(p))
        assert res["dropped_empty"] == 1
        assert any("剔除空事件（坏行抢救）×1" in w for w in res["warnings"])
        assert res["dropped_details"] == [
            {"line": None, "text": "", "resolved": False}]
        # 解析期 RuntimeWarning 进告警清单（吞错可见化）
        assert any("解析警告" in w for w in res["warnings"])
        out = Path(res["srt_path"]).read_text(encoding="utf-8")
        assert "正常行前" in out and "正常行后" in out
        # 空事件零残留：产出仅 2 个 cue 时间轴行
        timeline = [ln for ln in out.splitlines() if "-->" in ln]
        assert len(timeline) == 2


# ── ③' 坏行行号明细（2.6.5 段1⑤，D2026-1004-01 正式复评 C7） ─────────
# 预洗行号=1-based 物理行号；_HDR 占 1-8 行、_EVFMT 占第 9 行，首个 Dialogue=第 10 行
_HDR_LINES = [
    "[Script Info]",
    "ScriptType: v4.00+",
    "",
    "[V4+ Styles]",
    "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
    " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX,"
    " ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL,"
    " MarginR, MarginV, Encoding",
    "Style: Default,Microsoft YaHei,20,&H00FFFFFF,&H000000FF,&H00000000,"
    "&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1",
    "",
    "[Events]",
]


class TestBadLineDetailAss:
    def test_ssa_v4_field_order_variant(self, tmp_path):
        """fixture①：SSA V4 字段序变体（Marked, Start, End, ...）空文本
        Dialogue → Format 行驱动列映射（禁位置硬编码），行号正确。"""
        from subtransjav.refine.subtitle_convert import convert_file
        lines = [
            "[Script Info]",
            "ScriptType: v4.00",
            "",
            "[V4 Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour,"
            " OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut,"
            " ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow,"
            " Alignment, MarginL, MarginR, MarginV, Encoding",
            "Style: Default,Microsoft YaHei,20,&H00FFFFFF,&H000000FF,"
            "&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,2,0,2,10,10,10,1",
            "",
            "[Events]",
            "Format: Marked, Start, End, Style, Name, MarginL, MarginR,"
            " MarginV, Effect, Text",                                      # 行 9
            "Dialogue: Marked=0,0:00:10.00,0:00:12.00,Default,,0,0,0,,",   # 行 10 坏行
            "Dialogue: Marked=0,0:00:13.00,0:00:14.00,Default,,0,0,0,,"
            "SSA字段序样例",                                                # 行 11
        ]
        p = _write(tmp_path / "ssa.ssa", "\n".join(lines) + "\n")
        res = convert_file(str(p))
        assert res["dropped_empty"] == 1
        assert res["dropped_details"] == [
            {"line": 10, "text": "", "resolved": True}]
        assert "剔除空事件（坏行抢救）×1：第 10 行「」" in res["warnings"]

    def test_utf8sig_crlf_line_numbers_match_editor(self, tmp_path):
        """fixture②：utf-8-sig BOM + CRLF → 行号与编辑器一致（1-based 物理行号）。"""
        from subtransjav.refine.subtitle_convert import convert_file
        lines = _HDR_LINES + [
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR,"
            " MarginV, Effect, Text",                                       # 行 9
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,第一行",     # 行 10
            "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,",           # 行 11 坏行
            "Dialogue: 0,0:00:05.00,0:00:06.00,Default,,0,0,0,,第三行",     # 行 12
        ]
        p = _write(tmp_path / "bomcrlf.ass", "\r\n".join(lines) + "\r\n",
                   encoding="utf-8-sig")
        res = convert_file(str(p))
        assert res["dropped_empty"] == 1
        assert res["dropped_details"] == [
            {"line": 11, "text": "", "resolved": True}]
        assert any("第 11 行「」" in w for w in res["warnings"])

    def test_vtt_empty_cue_block_resolved_to_timeline_line(self, tmp_path):
        """VTT 补充：空 cue 块归属到 --> 时间轴行物理行号（块内无非空行）。"""
        from subtransjav.refine.subtitle_convert import convert_file
        p = _write(tmp_path / "bad.vtt", (
            "WEBVTT\n"
            "\n"
            "00:00:01.000 --> 00:00:03.000\n"
            "正常行\n"
            "\n"
            "00:00:05.000 --> 00:00:06.000\n"
            "\n"
        ))
        res = convert_file(str(p))
        assert res["dropped_empty"] == 1
        assert res["dropped_details"] == [
            {"line": 6, "text": "", "resolved": True}]
        assert any("第 6 行「」" in w for w in res["warnings"])


class TestDuplicateTimestampDisambiguation:
    def test_same_ts_one_empty_one_text_resolved_by_text(self, tmp_path):
        """fixture③a：重复时间戳一空一非空 → text strip 消歧命中空行。"""
        from subtransjav.refine.subtitle_convert import convert_file
        p = _write(tmp_path / "dup1.ass", _HDR + _EVFMT
                   + "Dialogue: 0,0:00:30.00,0:00:31.00,Default,,0,0,0,,\n"
                   + "Dialogue: 0,0:00:30.00,0:00:31.00,Default,,0,0,0,,非空消歧\n")
        res = convert_file(str(p))
        assert res["dropped_empty"] == 1
        assert res["dropped_details"] == [
            {"line": 10, "text": "", "resolved": True}]
        assert any("第 10 行「」" in w and "行号未定" not in w
                   for w in res["warnings"])

    def test_same_ts_both_empty_unresolved_fallback(self, tmp_path):
        """fixture③b：双空（重复时间戳均空文本）→ 消歧失败行号未定，
        全部未定退回旧纯计数文案兜底（规格归属规则 2/3）。"""
        from subtransjav.refine.subtitle_convert import convert_file
        p = _write(tmp_path / "dup2.ass", _HDR + _EVFMT
                   + "Dialogue: 0,0:00:30.00,0:00:31.00,Default,,0,0,0,,\n"
                   + "Dialogue: 0,0:00:30.00,0:00:31.00,Default,,0,0,0,,\n")
        res = convert_file(str(p))
        assert res["dropped_empty"] == 2
        assert all(d["line"] is None and d["resolved"] is False
                   for d in res["dropped_details"])
        assert any(w == "剔除空事件（坏行抢救）×2" for w in res["warnings"])


class TestDetailAggregationLimit:
    def test_over_ten_bad_lines_capped_with_total_suffix(self, tmp_path):
        """上限聚合：>10 条坏行 → 明细只取前 10 条，收尾「等 N 处」，
        全部命中无「行号未定」收尾。"""
        from subtransjav.refine.subtitle_convert import convert_file
        bad = [f"Dialogue: 0,0:00:{10 + i:02d}.00,0:00:{10 + i:02d}.05,"
               f"Default,,0,0,0,," for i in range(12)]       # 行 10-21，坏行 12 条
        p = _write(tmp_path / "many.ass",
                   _HDR + _EVFMT + "".join(ln + "\n" for ln in bad))
        res = convert_file(str(p))
        assert res["dropped_empty"] == 12
        assert len(res["dropped_details"]) == 12
        assert all(d["resolved"] and d["line"] == 10 + i
                   for i, d in enumerate(res["dropped_details"]))
        msg = next(w for w in res["warnings"] if "坏行抢救" in w)
        assert msg.startswith("剔除空事件（坏行抢救）×12：")
        for i in range(10):                                  # 明细只含前 10 条
            assert f"第 {10 + i} 行「」" in msg
        assert "第 20 行" not in msg and "第 21 行" not in msg
        assert "（等 12 处）" in msg
        assert "行号未定" not in msg


# ── ④ 相邻 cue 重叠顺延 ──────────────────────────────────────────────


class TestOverlapShift:
    def test_later_start_pushed_to_prev_end(self, tmp_path):
        from subtransjav.refine.subtitle_convert import convert_file
        p = _write(tmp_path / "ov.ass", _HDR + _EVFMT
                   + "Dialogue: 0,0:00:01.00,0:00:05.00,Default,,0,0,0,,第一条\n"
                   + "Dialogue: 0,0:00:03.00,0:00:07.00,Default,,0,0,0,,第二条\n")
        res = convert_file(str(p))
        assert res["shifted_overlaps"] == 1
        out = Path(res["srt_path"]).read_text(encoding="utf-8")
        # 后一 cue start 顺延至前一 end（方向写死，end 不动）
        assert "00:00:05,000 --> 00:00:07,000" in out


# ── ⑤ 产出时间轴静态断言（厘秒→毫秒零填充保险带） ────────────────────


class TestTimelineAssertion:
    def test_centisecond_zero_padding_and_regex(self, tmp_path):
        from subtransjav.refine.subtitle_convert import convert_file
        p = _write(tmp_path / "cs.ass", _HDR + _EVFMT
                   + "Dialogue: 0,0:00:00.90,0:00:01.05,Default,,0,0,0,,零填充样例\n")
        res = convert_file(str(p))
        out = Path(res["srt_path"]).read_text(encoding="utf-8")
        assert "00:00:00,900 --> 00:00:01,050" in out
        for ln in out.splitlines():
            if "-->" in ln:
                assert _SRT_TIMELINE_RE.match(ln), f"时间轴行不匹配: {ln!r}"


# ── ⑥ conv 命名与覆盖幂等 ────────────────────────────────────────────


class TestConvNamingIdempotent:
    def test_run_twice_same_result(self, tmp_path):
        from subtransjav.refine.subtitle_convert import convert_file
        p = _write(tmp_path / "foo.ass", _HDR + _EVFMT
                   + "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,命名样例\n")
        r1 = convert_file(str(p))
        r2 = convert_file(str(p))
        expected = tmp_path / "foo.ass.conv.srt"
        assert r1["srt_path"] == r2["srt_path"] == str(expected)
        assert expected.exists()
        t1 = expected.read_bytes()
        t2 = expected.read_bytes()
        assert t1 == t2  # 覆盖旧件、逐字节幂等
        assert "命名样例" in t1.decode("utf-8")


# ── ⑦⑧ convert_inputs 批处理 ────────────────────────────────────────


class TestConvertInputs:
    def test_unsupported_ext_passthrough(self, tmp_path):
        from subtransjav.refine.subtitle_convert import (
            SUPPORTED_EXTS,
            convert_inputs,
        )
        txt = tmp_path / "a.txt"
        txt.write_text("not a subtitle", encoding="utf-8")
        new_paths, warns = convert_inputs([str(txt)])
        assert new_paths == [str(txt)]      # 原样透传
        assert warns == []
        assert ".txt" not in SUPPORTED_EXTS
        assert not (tmp_path / "a.txt.conv.srt").exists()

    def test_end_to_end_ass_to_conv_srt(self, tmp_path):
        from subtransjav.refine.subtitle_convert import convert_inputs
        p = _write(tmp_path / "jp.ass", _HDR + _EVFMT
                   + "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,こんにちは\n"
                   + "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,中文字幕\n")
        new_paths, warns = convert_inputs([str(p)])
        assert new_paths == [str(tmp_path / "jp.ass.conv.srt")]
        assert warns == []
        out = (tmp_path / "jp.ass.conv.srt").read_text(encoding="utf-8")
        assert "こんにちは" in out and "中文字幕" in out


# ── CLI 接线钉（config_from_args 转换步 + 零噪音） ───────────────────


class TestCliWiring:
    def test_config_from_args_converts_and_prints(self, tmp_path, capsys):
        from subtransjav.refine.cli import build_parser, config_from_args
        p = _write(tmp_path / "s.ass", _HDR + _EVFMT
                   + "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,接线样例\n")
        cfg = config_from_args(build_parser().parse_args(["-i", str(p)]))
        assert cfg.inputs == [str(tmp_path / "s.ass.conv.srt")]
        out = capsys.readouterr().out
        assert "🔄 格式转换: 1 个 ASS/VTT → SRT（0 警告）" in out

    def test_config_from_args_srt_zero_noise(self, tmp_path, capsys):
        from subtransjav.refine.cli import build_parser, config_from_args
        p = _write(tmp_path / "s.srt",
                   "1\n00:00:01,000 --> 00:00:02,000\n普通\n")
        cfg = config_from_args(build_parser().parse_args(["-i", str(p)]))
        assert cfg.inputs == [str(p)]
        assert capsys.readouterr().out == ""  # N=0 完全不打印


# ── GUI 对话框/i18n 键钉（只增不减） ─────────────────────────────────


class TestGuiFiletypePin:
    def test_file_type_subtitle_key_registered(self):
        from subtransjav.webview_gui.strings import MSG
        assert MSG["file_type_subtitle"] == "ASS/SSA/VTT 字幕 (*.ass;*.ssa;*.vtt)"

    def test_select_srt_files_dialog_includes_subtitle_type(self):
        src = (Path(__file__).resolve().parents[1] / "subtransjav"
               / "webview_gui" / "api.py").read_text(encoding="utf-8")
        body = src.split("def select_srt_files", 1)[1] \
                  .split("def select_srt_folder", 1)[0]
        assert 'msg("file_type_subtitle")' in body, \
            "select_srt_files 对话框须放行 file_type_subtitle（批2 多格式导入）"
