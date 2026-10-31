"""
双引擎分歧采集单元测试：find_pass_siblings / probe_disagreement_mode /
judge_artifact / 内部辅助函数 / collect_disagreement。
"""
import csv
import logging
import random
from pathlib import Path

import pytest

from subtransjav.refine import pass_disagreement as pd
from subtransjav.refine.pass_disagreement import (
    REVIEW_STRICT_THRESHOLD,
    _best_overlap,
    _normalize,
    _sibling_paths,
    _similarity,
    _timing_span,
    collect_disagreement,
    find_pass_siblings,
    judge_artifact,
    probe_disagreement_mode,
)
from subtransjav.refine.quality_report import write_divergence_review_csv


def _srt(entries):
    """(index, timing, text) 列表 → SRT 文本。"""
    blocks = [f"{idx}\n{timing}\n{text}" for idx, timing, text in entries]
    return "\n\n".join(blocks) + "\n"


def test_find_pass_siblings(tmp_path):
    (tmp_path / "X.ja.pass1.srt").write_text("", encoding="utf-8")
    (tmp_path / "X.ja.pass2.srt").write_text("", encoding="utf-8")
    merged = tmp_path / "X.ja.merged.subtransjav.srt"
    merged.write_text("", encoding="utf-8")

    p1, p2 = find_pass_siblings(str(merged))
    assert p1 is not None and p2 is not None
    assert p1.name == "X.ja.pass1.srt"
    assert p2.name == "X.ja.pass2.srt"

    # 只存在 pass1 的场景 → (None, None)
    d = tmp_path / "only_p1"
    d.mkdir()
    (d / "Y.ja.pass1.srt").write_text("", encoding="utf-8")
    (d / "Y.ja.merged.subtransjav.srt").write_text("", encoding="utf-8")
    a, b = find_pass_siblings(str(d / "Y.ja.merged.subtransjav.srt"))
    assert (a, b) == (None, None)


def test_collect_disagreement(tmp_path):
    merged = _srt([
        (1, "00:00:01,000 --> 00:00:03,000", "同じ文本です"),
        (2, "00:00:04,000 --> 00:00:06,000", "完全不同的文本甲"),
        (3, "00:00:07,000 --> 00:00:09,000", "仅pass1有对应"),
    ])
    pass1 = _srt([
        (1, "00:00:01,000 --> 00:00:03,000", "同じ文本です"),
        (2, "00:00:04,000 --> 00:00:06,000", "完全不同的文本甲"),
        (3, "00:00:07,000 --> 00:00:09,000", "仅pass1有对应"),
    ])
    pass2 = _srt([
        (1, "00:00:01,000 --> 00:00:03,000", "同じ文本です"),
        (2, "00:00:04,000 --> 00:00:06,000", "まったく違う内容乙"),
    ])

    (tmp_path / "X.ja.pass1.srt").write_text(pass1, encoding="utf-8")
    (tmp_path / "X.ja.pass2.srt").write_text(pass2, encoding="utf-8")
    mp = tmp_path / "X.ja.merged.subtransjav.srt"
    mp.write_text(merged, encoding="utf-8")

    result = collect_disagreement(str(mp))
    assert result is not None
    assert result["total"] == 3
    assert result["matched"] == 2
    assert len(result["rows"]) == 2
    # rows 按 similarity 升序：低相似度行（index 2）在前，相似行（index 1）在后
    assert result["rows"][0]["index"] == 2
    assert result["rows"][1]["index"] == 1
    assert result["rows"][0]["similarity"] < result["rows"][1]["similarity"]
    assert result["rows"][1]["similarity"] > 0.9


def test_collect_disagreement_no_siblings(tmp_path):
    p = tmp_path / "Z.ja.merged.subtransjav.srt"
    p.write_text(_srt([(1, "00:00:01,000 --> 00:00:03,000", "x")]),
                 encoding="utf-8")
    assert collect_disagreement(str(p)) is None


# ======================================================================
# probe_disagreement_mode：四种模式的探测
# ======================================================================

def test_probe_disagreement_mode_dual(tmp_path):
    """pass1/pass2 齐全 → dual。"""
    (tmp_path / "A.ja.pass1.srt").write_text("", encoding="utf-8")
    (tmp_path / "A.ja.pass2.srt").write_text("", encoding="utf-8")
    mp = tmp_path / "A.ja.merged.subtransjav.srt"
    mp.write_text("", encoding="utf-8")
    assert probe_disagreement_mode(str(mp)) == "dual"


def test_probe_disagreement_mode_missing_pass1(tmp_path):
    """仅缺 pass1 → missing_pass1。"""
    (tmp_path / "B.ja.pass2.srt").write_text("", encoding="utf-8")
    mp = tmp_path / "B.ja.merged.subtransjav.srt"
    mp.write_text("", encoding="utf-8")
    assert probe_disagreement_mode(str(mp)) == "missing_pass1"


def test_probe_disagreement_mode_missing_pass2(tmp_path):
    """仅缺 pass2 → missing_pass2。"""
    (tmp_path / "C.ja.pass1.srt").write_text("", encoding="utf-8")
    mp = tmp_path / "C.ja.merged.subtransjav.srt"
    mp.write_text("", encoding="utf-8")
    assert probe_disagreement_mode(str(mp)) == "missing_pass2"


def test_probe_disagreement_mode_none(tmp_path):
    """两个兄弟文件都缺失 → none。"""
    mp = tmp_path / "D.ja.merged.subtransjav.srt"
    mp.write_text("", encoding="utf-8")
    assert probe_disagreement_mode(str(mp)) == "none"


# ======================================================================
# judge_artifact：白名单兜底 + V3 长度组合门槛
# ======================================================================

def test_judge_artifact_whitelist_hit():
    """短侧命中应和/感叹白名单 → 判伪影（similarity 未知也生效）。"""
    assert judge_artifact(0.9, 0.0, "うん", "とても長い実義文です",
                          0.20, 3.0) is True
    assert judge_artifact(0.9, 0.0, "長い側の文章", "はい",
                          0.20, 3.0, similarity=0.99) is True


def test_judge_artifact_v3_length_gate():
    """短侧≤ARTIFACT_SHORT_MAX 且 长侧≥ARTIFACT_LONG_MIN 且低相似 → 伪影。"""
    sim = REVIEW_STRICT_THRESHOLD - 0.01
    # 短侧 3 字符、长侧 4 字符以上、低相似度 → 判伪影
    assert judge_artifact(0.9, 0.0, "あああ", "実義の長文です",
                          0.20, 3.0, similarity=sim) is True
    # 长侧不足 ARTIFACT_LONG_MIN → 不判伪影（两侧均避开白名单词）
    assert judge_artifact(0.9, 0.0, "いぬ", "ねこ",
                          0.20, 3.0, similarity=sim) is False
    # 相似度达到 REVIEW_STRICT_THRESHOLD → 不判伪影
    assert judge_artifact(0.9, 0.0, "あああ", "実義の長文です",
                          0.20, 3.0,
                          similarity=REVIEW_STRICT_THRESHOLD) is False
    # similarity 未知（-1.0）时跳过 V3 门槛 → 不判伪影
    assert judge_artifact(0.9, 0.0, "あああ", "実義の長文です",
                          0.20, 3.0, similarity=-1.0) is False


def test_judge_artifact_normal_not_artifact():
    """普通不命中白名单/门槛的分歧行 → 非伪影。"""
    assert judge_artifact(0.5, 1.0, "完全不同的文本甲", "まったく違う内容乙",
                          0.20, 3.0, similarity=0.1) is False


# ======================================================================
# 内部辅助函数：_timing_span / _normalize / _similarity / _best_overlap /
# _sibling_paths
# ======================================================================

def test_timing_span_invalid():
    """非法时间码（缺失/乱码/None）→ (-1.0, -1.0)。"""
    assert _timing_span("not a timing") == (-1.0, -1.0)
    assert _timing_span("00:00:01 --> 00:00:03") == (-1.0, -1.0)
    assert _timing_span("") == (-1.0, -1.0)
    assert _timing_span(None) == (-1.0, -1.0)


def test_timing_span_valid():
    """合法时间码（毫秒逗号/点号兼容）。"""
    assert _timing_span("00:00:01,500 --> 00:00:03,000") == (1.5, 3.0)
    assert _timing_span("01:02:03.250 --> 01:02:04.750") == (3723.25, 3724.75)


def test_normalize_and_similarity_empty_or_punct():
    """空串/纯标点归一化后为空，相似度返回 0.0。"""
    assert _normalize("") == ""
    assert _normalize(None) == ""
    assert _normalize("，。！？ ") == ""
    assert _similarity("", "あいうえお") == 0.0
    assert _similarity("あいうえお", "") == 0.0
    assert _similarity("、。！", "，？") == 0.0
    # 非空正常情况：相同文本相似度 1.0
    assert _similarity("同じテキスト", "同じテキスト") == 1.0


def test_best_overlap_no_overlap():
    """无重叠 / 负坐标 span → 返回 None。"""
    entries = [{"timing": "00:00:01,000 --> 00:00:02,000", "text": "a"}]
    # span 起点在条目结束之后 → 无正重叠
    assert _best_overlap((2.0, 3.0), entries) is None
    # span 在条目开始之前 → 无正重叠
    assert _best_overlap((0.0, 0.5), entries) is None
    # 负坐标（非法时间码解析结果）→ 直接返回 None
    assert _best_overlap((-1.0, -1.0), entries) is None
    # entries 内条目时间码非法 → 被跳过
    bad = [{"timing": "bad", "text": "b"}]
    assert _best_overlap((1.0, 2.0), bad) is None


def test_sibling_paths_lang_and_markers():
    """语言后缀解析；缺省语言码为 ja；merged 可带 .subtransjav 后缀。"""
    # 带语言后缀
    p, p1, p2 = _sibling_paths("/tmp/X.ja.merged.subtransjav.srt")
    assert p1.name == "X.ja.pass1.srt"
    assert p2.name == "X.ja.pass2.srt"
    # 其他语言码
    _, p1, p2 = _sibling_paths("/tmp/X.zh.merged.subtransjav.srt")
    assert p1.name == "X.zh.pass1.srt"
    assert p2.name == "X.zh.pass2.srt"
    # merged 不带 .subtransjav 后缀
    _, p1, p2 = _sibling_paths("/tmp/X.ja.merged.srt")
    assert p1.name == "X.ja.pass1.srt"
    assert p2.name == "X.ja.pass2.srt"
    # 无语言后缀 → 默认 ja
    _, p1, p2 = _sibling_paths("/tmp/X.merged.subtransjav.srt")
    assert p1.name == "X.ja.pass1.srt"
    assert p2.name == "X.ja.pass2.srt"
    # 传入 pass1 文件本身 → 兄弟路径与其重合（只拼路径不查存在性）
    p, p1, p2 = _sibling_paths("/tmp/X.ja.pass1.srt")
    assert p1.name == "X.ja.pass1.srt"
    assert p2.name == "X.ja.pass2.srt"


def test_collect_disagreement_no_timeline_overlap(tmp_path):
    """有兄弟文件但时间轴完全无重叠的行 → 不产生分歧行。"""
    merged = _srt([
        (1, "00:00:10,000 --> 00:00:12,000", "时间轴无重叠"),
    ])
    pass1 = _srt([
        (1, "00:00:01,000 --> 00:00:02,000", "别的片段一"),
    ])
    pass2 = _srt([
        (1, "00:00:03,000 --> 00:00:04,000", "别的片段二"),
    ])
    (tmp_path / "E.ja.pass1.srt").write_text(pass1, encoding="utf-8")
    (tmp_path / "E.ja.pass2.srt").write_text(pass2, encoding="utf-8")
    mp = tmp_path / "E.ja.merged.subtransjav.srt"
    mp.write_text(merged, encoding="utf-8")

    result = collect_disagreement(str(mp))
    assert result is not None
    assert result["total"] == 1
    assert result["matched"] == 0
    assert result["rows"] == []


# ======================================================================
# v1.3.2 Task-3：上游真实命名（.merged.whisperjav）回归 + 诊断区分
# ======================================================================

def test_find_pass_siblings_whisperjav_naming(tmp_path):
    """真实命名 X.ja.merged.whisperjav.srt + pass1/pass2 同目录 → 返回两路径。"""
    (tmp_path / "4k2.me@sample-b.ja.pass1.srt").write_text("", encoding="utf-8")
    (tmp_path / "4k2.me@sample-b.ja.pass2.srt").write_text("", encoding="utf-8")
    merged = tmp_path / "4k2.me@sample-b.ja.merged.whisperjav.srt"
    merged.write_text("", encoding="utf-8")

    p1, p2 = find_pass_siblings(str(merged))
    assert p1 is not None and p2 is not None
    assert p1.name == "4k2.me@sample-b.ja.pass1.srt"
    assert p2.name == "4k2.me@sample-b.ja.pass2.srt"


def test_probe_disagreement_mode_dual_whisperjav_naming(tmp_path):
    """真实命名下 probe 契约不变：pass1/pass2 齐全 → dual（不再恒为 none）。"""
    (tmp_path / "W.ja.pass1.srt").write_text("", encoding="utf-8")
    (tmp_path / "W.ja.pass2.srt").write_text("", encoding="utf-8")
    mp = tmp_path / "W.ja.merged.whisperjav.srt"
    mp.write_text("", encoding="utf-8")
    assert probe_disagreement_mode(str(mp)) == "dual"


def test_collect_disagreement_whisperjav_naming_end_to_end(tmp_path):
    """真实命名端到端：collect_disagreement → write_divergence_review_csv
    落盘后 CSV 数据行 ≥1（不是只有表头）。"""
    merged = _srt([
        (1, "00:00:01,000 --> 00:00:03,000", "同じ文本です"),
        (2, "00:00:04,000 --> 00:00:06,000", "完全不同的文本甲"),
    ])
    pass1 = _srt([
        (1, "00:00:01,000 --> 00:00:03,000", "同じ文本です"),
        (2, "00:00:04,000 --> 00:00:06,000", "完全不同的文本甲"),
    ])
    pass2 = _srt([
        (1, "00:00:01,000 --> 00:00:03,000", "同じ文本です"),
        (2, "00:00:04,000 --> 00:00:06,000", "まったく違う内容乙"),
    ])
    (tmp_path / "W.ja.pass1.srt").write_text(pass1, encoding="utf-8")
    (tmp_path / "W.ja.pass2.srt").write_text(pass2, encoding="utf-8")
    mp = tmp_path / "W.ja.merged.whisperjav.srt"
    mp.write_text(merged, encoding="utf-8")

    result = collect_disagreement(str(mp))
    assert result is not None
    assert result["matched"] >= 1

    out_csv = tmp_path / "W_分歧复核.csv"
    write_divergence_review_csv(str(out_csv), result["rows"], mp.name)
    with open(out_csv, encoding="utf-8-sig", newline="") as f:
        data = list(csv.reader(f))
    assert len(data) >= 2  # 表头 + 至少一行数据行


def test_sibling_paths_legacy_naming_backward_compat():
    """旧命名回归：.merged.subtransjav / 裸 .merged / 裸 pass1/pass2 的
    base/lang 剥离结果与修复前逐项一致。"""
    # 旧命名一：.merged.subtransjav.srt
    own, p1, p2 = _sibling_paths("/tmp/X.ja.merged.subtransjav.srt")
    assert own.name == "X.ja.merged.subtransjav.srt"
    assert own.parent == p1.parent == p2.parent
    assert p1.name == "X.ja.pass1.srt"
    assert p2.name == "X.ja.pass2.srt"
    # 旧命名二：裸 .merged.srt（无尾缀）
    _, p1, p2 = _sibling_paths("/tmp/X.ja.merged.srt")
    assert p1.name == "X.ja.pass1.srt"
    assert p2.name == "X.ja.pass2.srt"
    # 旧命名三：裸 .pass1.srt / .pass2.srt 本身 → 兄弟路径与其同基名
    _, p1, p2 = _sibling_paths("/tmp/X.ja.pass1.srt")
    assert p1.name == "X.ja.pass1.srt"
    assert p2.name == "X.ja.pass2.srt"
    _, p1, p2 = _sibling_paths("/tmp/X.ja.pass2.srt")
    assert p1.name == "X.ja.pass1.srt"
    assert p2.name == "X.ja.pass2.srt"


def test_find_pass_siblings_parse_failure_logs_warning(caplog):
    """命名解析失败 → (None, None) 且模块 logger 发出 WARNING（与缺失区分）。"""
    logger_name = "subtransjav.refine.pass_disagreement"
    with caplog.at_level(logging.WARNING, logger=logger_name):
        a, b = find_pass_siblings(None)  # type: ignore[arg-type]
    assert (a, b) == (None, None)
    warns = [r for r in caplog.records
             if r.name == logger_name and r.levelno == logging.WARNING]
    assert len(warns) == 1
    assert "分歧复核兄弟文件命名解析失败" in warns[0].getMessage()


def test_find_pass_siblings_missing_files_no_warning(tmp_path, caplog):
    """命名正常但兄弟文件缺失 → (None, None) 且无 WARNING（正常业务场景）。"""
    logger_name = "subtransjav.refine.pass_disagreement"
    mp = tmp_path / "D.ja.merged.whisperjav.srt"
    mp.write_text("", encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger=logger_name):
        a, b = find_pass_siblings(str(mp))
    assert (a, b) == (None, None)
    warns = [r for r in caplog.records
             if r.name == logger_name and r.levelno == logging.WARNING]
    assert warns == []


def test_diagnosis_marker_mismatch_vs_missing_siblings(tmp_path, caplog):
    """"命名解析失败（正则不匹配）"与"无兄弟 pass 文件"两种失败文案可区分。

    前者是 v1.3.2 命名漂移的真实形态（上游 v1.9.3 起尾缀带 .whisperjav，
    旧正则失配）→ WARNING 含"命名解析失败"；后者是命名解析成功但同目录
    无 pass1/pass2（单引擎正常场景）→ DEBUG 含"无兄弟 pass 文件（命名
    解析成功…）"且无 WARNING。
    """
    logger_name = "subtransjav.refine.pass_disagreement"

    # 场景一：正则不匹配（文件名无任何阶段标记）
    # _sibling_paths 按文档契约抛 ValueError，异常信息含"命名解析失败"
    bad = tmp_path / "NOMARKER.srt"
    bad.write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="命名解析失败"):
        _sibling_paths(str(bad))
    # 经两个公共入口 → WARNING 文案含"命名解析失败"，且不含"无兄弟 pass 文件"
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=logger_name):
        assert find_pass_siblings(str(bad)) == (None, None)
        assert probe_disagreement_mode(str(bad)) == "none"
    warns = [r for r in caplog.records
             if r.name == logger_name and r.levelno == logging.WARNING]
    assert len(warns) == 2  # find_pass_siblings / probe_disagreement_mode 各一条
    assert all("命名解析失败" in r.getMessage() for r in warns)
    assert all("无兄弟 pass 文件" not in r.getMessage() for r in warns)

    # 场景二：命名解析成功但同目录无兄弟 pass 文件 → 文案含"无兄弟 pass 文件"
    good = tmp_path / "M.ja.merged.whisperjav.srt"
    good.write_text("", encoding="utf-8")
    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger=logger_name):
        assert find_pass_siblings(str(good)) == (None, None)
        assert probe_disagreement_mode(str(good)) == "none"
    assert "无兄弟 pass 文件" in caplog.text
    assert "命名解析成功" in caplog.text
    assert "命名解析失败" not in caplog.text


# ---------------------------------------------------------------------------
# 2.7.3 件④（D2026-1005）：pass-only 判定 + 与 _MARKER_RE pass 分支一致性钉
# ---------------------------------------------------------------------------

def test_is_pass_intermediate_truth_table():
    """is_pass_intermediate：pass1/pass2 中间稿 True；merged 产成品/普通件 False。"""
    from subtransjav.refine.pass_disagreement import is_pass_intermediate

    # pass 中间稿（剥 .srt 后的 stem）
    assert is_pass_intermediate("M.ja.pass1") is True
    assert is_pass_intermediate("M.ja.pass2") is True
    # merged 产成品（关键钉：_PASS_MARKER_RE 刻意不含 merged 分支）
    assert is_pass_intermediate("M.ja.merged.subtransjav") is False
    assert is_pass_intermediate("M.ja.merged.whisperjav") is False
    # 末尾锚定防误伤 / 普通文件
    assert is_pass_intermediate("M.pass1_final_cn") is False
    assert is_pass_intermediate("movie") is False


def test_pass_marker_consistency_pin():
    """一致性钉：is_pass_intermediate 为 True 的 stem 必然匹配 _MARKER_RE
    （防未来 _MARKER_RE 编辑丢失 pass1|pass2 分支）。"""
    from subtransjav.refine.pass_disagreement import _MARKER_RE, is_pass_intermediate

    for stem in ("M.ja.pass1", "M.ja.pass2", "M.zh.pass1",
                 "M.ja.merged.subtransjav", "M.ja.merged.whisperjav", "movie"):
        if is_pass_intermediate(stem):
            assert _MARKER_RE.search(stem), \
                f"{stem} 判为 pass 中间稿却未命中 _MARKER_RE（pass 分支疑丢失）"


# ---------------------------------------------------------------------------
# 补卡2（D2026-1030-07）：pass_disagreement 模块边界薄弱分支
# 断言一律以 subtransjav/refine/pass_disagreement.py 实码现状为准。
# ---------------------------------------------------------------------------

def _srt_ts(ms):
    """毫秒整数 → SRT 时间码（合成夹具用，避免浮点格式化误差）。"""
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms_part = divmod(rem, 1_000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms_part:03d}"


def test_best_overlap_tie_keeps_first_entry():
    """_best_overlap 平局保留首个条目（:207-209 严格大于语义）。"""
    entries = [
        {"timing": "00:00:00,000 --> 00:00:05,000", "text": "first"},
        {"timing": "00:00:05,000 --> 00:00:10,000", "text": "second"},
    ]
    # 两条与 span (0,10) 重叠均为 5.0 秒 → 平局，保留首个
    assert _best_overlap((0.0, 10.0), entries) is entries[0]
    # 后续条目重叠更大（7.0 秒）→ 允许替换，确认严格大于只挡平局
    bigger = entries + [{"timing": "00:00:01,000 --> 00:00:08,000",
                         "text": "third"}]
    assert _best_overlap((0.0, 10.0), bigger) is bigger[2]


def test_best_overlap_empty_entries_none():
    """_best_overlap 空表 → None（:197-210）。"""
    assert _best_overlap((0.0, 1.0), []) is None
    assert _best_overlap((0.0, 1.0), ()) is None


def test_probe_disagreement_mode_bare_exception_none(tmp_path, monkeypatch):
    """probe_disagreement_mode 非 ValueError 异常兜底 → "none"（:159-160）。"""
    mp = tmp_path / "P.ja.merged.subtransjav.srt"
    mp.write_text("", encoding="utf-8")

    def _boom(self):
        raise OSError("is_file exploded")

    # OSError 走裸 Exception 分支（ValueError 分支另有命名解析失败日志）
    monkeypatch.setattr(Path, "is_file", _boom)
    assert probe_disagreement_mode(str(mp)) == "none"


def test_sibling_paths_lang_family_suffixes():
    """_sibling_paths 语言族其余成员 japanese/chinese/translated（_LANG_RE :25）。"""
    for lang in ("japanese", "chinese", "translated"):
        _, p1, p2 = _sibling_paths(f"/tmp/X.{lang}.merged.whisperjav.srt")
        assert p1.name == f"X.{lang}.pass1.srt"
        assert p2.name == f"X.{lang}.pass2.srt"


def test_sibling_paths_lang_case_sensitive_contract():
    """_LANG_RE 小写锚定：大写语言码不剥离、回落 ja（_LANG_RE :25 现状契约）。"""
    _, p1, p2 = _sibling_paths("/tmp/X.JA.merged.subtransjav.srt")
    assert p1.name == "X.JA.ja.pass1.srt"
    assert p2.name == "X.JA.ja.pass2.srt"
    _, p1, p2 = _sibling_paths("/tmp/X.Japanese.merged.srt")
    assert p1.name == "X.Japanese.ja.pass1.srt"
    # 阶段标记同样大小写敏感：大写 MERGED 不命中 _MARKER_RE → ValueError
    with pytest.raises(ValueError, match="命名解析失败"):
        _sibling_paths("/tmp/X.ja.MERGED.subtransjav.srt")


def test_collect_disagreement_iou_union_zero_defensive(tmp_path, monkeypatch):
    """IoU 防御分支 union<=0 → 0.0（:268-270）。

    自然样本不可达：_best_overlap 只返回与合法 span 正重叠的条目，故
    e1>s1、e2>s2 且 overlap>0，union 必为正。此处用协作方 monkeypatch
    构造零长度命中，钉住防御分支的现行返回值为 0.0。
    """
    (tmp_path / "Q.ja.pass1.srt").write_text(
        _srt([(1, "00:00:01,000 --> 00:00:02,000", "甲")]), encoding="utf-8")
    (tmp_path / "Q.ja.pass2.srt").write_text(
        _srt([(1, "00:00:01,000 --> 00:00:02,000", "乙")]), encoding="utf-8")
    mp = tmp_path / "Q.ja.merged.subtransjav.srt"
    mp.write_text(_srt([(1, "00:00:01,000 --> 00:00:02,000", "丙")]),
                  encoding="utf-8")

    zero_len_hit = {"timing": "00:00:05,000 --> 00:00:05,000", "text": "同一文本"}
    monkeypatch.setattr(pd, "_best_overlap", lambda span, entries: zero_len_hit)

    result = collect_disagreement(str(mp))
    assert result is not None
    assert len(result["rows"]) == 1
    assert result["rows"][0]["iou"] == 0.0
    assert result["rows"][0]["offset"] == 0.0


def test_collect_disagreement_iou_property_bounded(tmp_path):
    """性质钉：随机合法样本下 iou∈[0,1]（固定种子，确定性）。

    替代自然路径不可达的 union<=0 分支（:268-270）：_best_overlap 保证
    正重叠命中，故 union 恒正；用性质断言守住 IoU 边界不越界。
    """
    rng = random.Random(20261031)
    pool = "あいうえおかきくけこ甲乙丙丁"

    def _text(n):
        return "".join(rng.choice(pool) for _ in range(n))

    merged_entries, p1_entries, p2_entries = [], [], []
    for i in range(1, 16):
        start_ms = 1_000 + (i - 1) * 3_000
        end_ms = start_ms + 1_600
        merged_entries.append(
            (i, f"{_srt_ts(start_ms)} --> {_srt_ts(end_ms)}", _text(6)))
        p1_entries.append(
            (i, f"{_srt_ts(start_ms)} --> {_srt_ts(end_ms)}", _text(6)))
        shift_ms = rng.choice((-600, -300, 0, 300, 600))
        p2_entries.append(
            (i, f"{_srt_ts(start_ms + shift_ms)} --> "
                f"{_srt_ts(end_ms + shift_ms)}", _text(6)))

    (tmp_path / "R.ja.pass1.srt").write_text(_srt(p1_entries), encoding="utf-8")
    (tmp_path / "R.ja.pass2.srt").write_text(_srt(p2_entries), encoding="utf-8")
    mp = tmp_path / "R.ja.merged.subtransjav.srt"
    mp.write_text(_srt(merged_entries), encoding="utf-8")

    result = collect_disagreement(str(mp))
    assert result is not None
    assert result["matched"] >= 1
    for row in result["rows"]:
        assert 0.0 <= row["iou"] <= 1.0
        assert row["offset"] >= 0.0
        assert 0.0 <= row["similarity"] <= 1.0


def test_timing_span_wide_hours_and_ms_precision():
    """_timing_span 超宽小时/4 位毫秒边界与 round(,3) 精度（:174-176）。"""
    start, end = _timing_span("100:00:00,000 --> 100:00:00,001")
    assert start == 360_000.0
    assert end == pytest.approx(360_000.001, abs=1e-9)
    start, end = _timing_span("999:59:59,999 --> 1000:00:00,001")
    assert start == pytest.approx(3_599_999.999, abs=1e-6)
    assert end == pytest.approx(3_600_000.001, abs=1e-6)
    # 分钟/秒不做范围校验：按字面算术累加（非进位归一化）
    assert _timing_span("00:60:00,000 --> 00:00:61,500") == (3600.0, 61.5)
    # 毫秒位宽不做上限校验：4 位数字按 /1000 解释
    assert _timing_span("00:00:00,1234 --> 00:00:01,5") == (1.234, 1.005)


def test_collect_disagreement_non_utf8_srt_tolerated(tmp_path):
    """非 UTF-8 SRT 容错契约：errors="replace" 不再上抛（D2026-1031-04 ⑦①）。

    旧钉（本卡落地前）为 ``pytest.raises(UnicodeDecodeError)`` 现状契约；
    owner 拍板补容错后同一输入应正常返回 dict，故就地改写为容错契约。
    """
    (tmp_path / "S.ja.pass1.srt").write_text(
        _srt([(1, "00:00:01,000 --> 00:00:02,000", "甲")]), encoding="utf-8")
    (tmp_path / "S.ja.pass2.srt").write_bytes(
        b"\xff\xfe\x00\x00 not utf-8")
    mp = tmp_path / "S.ja.merged.subtransjav.srt"
    mp.write_text(
        _srt([(1, "00:00:01,000 --> 00:00:02,000", "甲")]), encoding="utf-8")

    result = collect_disagreement(str(mp))
    assert result == {"total": 1, "matched": 0, "rows": []}


def _srt_with_illegal_bytes(entries, corrupt_first: bool = False) -> bytes:
    """entries → SRT 字节；corrupt_first 时首条文本行尾部混入非法字节序列。"""
    body = _srt(entries).encode("utf-8")
    if not corrupt_first:
        return body
    # 定位第 3 个换行（index/timing/text 之后），把 b"\x93\x94\x95" 插入文本行末
    first = body.index(b"\n")
    second = body.index(b"\n", first + 1)
    third = body.index(b"\n", second + 1)
    return body[:third] + b"\x93\x94\x95" + body[third:]


_ILLEGAL_LEG_TO_NAME = {
    "own": "V.ja.merged.subtransjav.srt",
    "pass1": "V.ja.pass1.srt",
    "pass2": "V.ja.pass2.srt",
}


@pytest.mark.parametrize("leg", ["own", "pass1", "pass2"])
def test_collect_disagreement_illegal_bytes_no_raise(tmp_path, leg):
    """:256/:257/:258 三处读取任一损坏均不上抛，结构正常返回（D2026-1031-04 ⑦①）。"""
    entries = [
        (1, "00:00:01,000 --> 00:00:02,000", "同じ文本です"),
        (2, "00:00:05,000 --> 00:00:06,000", "完全不同的文本甲"),
    ]
    for name in _ILLEGAL_LEG_TO_NAME.values():
        (tmp_path / name).write_bytes(
            _srt_with_illegal_bytes(entries,
                                    corrupt_first=(name == _ILLEGAL_LEG_TO_NAME[leg])))

    result = collect_disagreement(str(tmp_path / _ILLEGAL_LEG_TO_NAME["own"]))
    assert isinstance(result, dict)
    assert set(result) == {"total", "matched", "rows"}
    assert result["total"] == 2
    assert result["matched"] == 2
    assert [r["index"] for r in result["rows"]] == [1, 2]
    if leg in ("pass1", "pass2"):
        # 损坏面进比对：非法三字节被替换为三个 U+FFFD，随行文本进 rows
        texts = "".join(r["pass1"] + r["pass2"] for r in result["rows"])
        assert "\ufffd" * 3 in texts


def test_collect_disagreement_all_illegal_bytes_keeps_replacement_chars(tmp_path):
    """三件套全损坏：不抛、rows 含 U+FFFD 且时间轴匹配结构不变。"""
    entries = [(1, "00:00:01,000 --> 00:00:02,000", "同じ文本です")]
    for name in _ILLEGAL_LEG_TO_NAME.values():
        (tmp_path / name).write_bytes(
            _srt_with_illegal_bytes(entries, corrupt_first=True))

    result = collect_disagreement(str(tmp_path / _ILLEGAL_LEG_TO_NAME["own"]))
    assert result is not None
    assert result["total"] == 1
    assert result["matched"] == 1
    rows = result["rows"]
    assert len(rows) == 1
    assert "\ufffd" * 3 in rows[0]["pass1"]
    assert "\ufffd" * 3 in rows[0]["pass2"]


def test_collect_disagreement_legal_input_zero_change(tmp_path):
    """全合法 UTF-8 三件套：输出逐键与改前契约一致（errors 参数零影响）。"""
    entries = [(1, "00:00:01,000 --> 00:00:02,000", "同じ文本です")]
    for name in _ILLEGAL_LEG_TO_NAME.values():
        (tmp_path / name).write_bytes(_srt_with_illegal_bytes(entries))

    result = collect_disagreement(str(tmp_path / _ILLEGAL_LEG_TO_NAME["own"]))
    assert result == {
        "total": 1,
        "matched": 1,
        "rows": [{
            "index": 1,
            "timing": "00:00:01,000 --> 00:00:02,000",
            "pass1_timing": "00:00:01,000 --> 00:00:02,000",
            "pass2_timing": "00:00:01,000 --> 00:00:02,000",
            "pass1": "同じ文本です",
            "pass2": "同じ文本です",
            "similarity": 1.0,
            "iou": 1.0,
            "offset": 0.0,
            "artifact": False,
        }],
    }


def test_collect_disagreement_malformed_utf8_srt_contract(tmp_path):
    """损坏但可解码的 SRT：parse_srt 解析为空 → total=0/matched=0/rows=[]。"""
    (tmp_path / "T.ja.pass1.srt").write_text("垃圾内容", encoding="utf-8")
    (tmp_path / "T.ja.pass2.srt").write_text("垃圾内容", encoding="utf-8")
    mp = tmp_path / "T.ja.merged.subtransjav.srt"
    mp.write_text("不是 SRT 的任何文本", encoding="utf-8")

    result = collect_disagreement(str(mp))
    assert result == {"total": 0, "matched": 0, "rows": []}


def test_judge_artifact_equal_length_tie_prefers_text1():
    """judge_artifact 短长侧等长时 short_str 取 text1（:231-232）。"""
    # "はい" 与 "あい" 归一化后等长（2）；text1 命中白名单 → 判伪影
    assert judge_artifact(0.9, 0.0, "はい", "あい", 0.20, 3.0,
                          similarity=-1.0) is True
    # 交换顺序：text1="あい" 未命中白名单，similarity 未知跳过 V3 → False
    assert judge_artifact(0.9, 0.0, "あい", "はい", 0.20, 3.0,
                          similarity=-1.0) is False
