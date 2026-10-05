"""
双引擎分歧采集单元测试：find_pass_siblings / probe_disagreement_mode /
judge_artifact / 内部辅助函数 / collect_disagreement。
"""
import csv
import logging

import pytest

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
    (tmp_path / "4k2.me@ftkd-030.ja.pass1.srt").write_text("", encoding="utf-8")
    (tmp_path / "4k2.me@ftkd-030.ja.pass2.srt").write_text("", encoding="utf-8")
    merged = tmp_path / "4k2.me@ftkd-030.ja.merged.whisperjav.srt"
    merged.write_text("", encoding="utf-8")

    p1, p2 = find_pass_siblings(str(merged))
    assert p1 is not None and p2 is not None
    assert p1.name == "4k2.me@ftkd-030.ja.pass1.srt"
    assert p2.name == "4k2.me@ftkd-030.ja.pass2.srt"


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
