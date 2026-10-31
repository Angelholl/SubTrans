"""D2026-1031-07 卡E2：quality_advisor 术语冲突摘要与模型覆盖补测。

补测既有 test_quality_advisor.py / test_quality_advisor_gap_d4.py 未覆盖的
纯函数分支：_derive_stem 后缀剥离、_load_conflict_summary 摘要与降级、
_make_ai_client 仅换槽0 模型、run_ai_analyze 缺冲突 CSV 告警继续与分析
异常 rc1。按卡面「明确不含」条款，媒体重点对照（C22）零触碰。

全部用 fake 客户端 / tmp_path 假报告导读，不发真实网络请求；文件面一律
tmp_path。
"""
import argparse
import json
from pathlib import Path

from subtransjav.refine import quality_advisor as qa
from subtransjav.refine.config import RefineConfig

_OK_JSON = json.dumps({
    "glossary": [{"src": "先生", "target": "老师", "reason": "统一称谓"}],
    "tm": [{"source": "源句", "target": "译句", "reason": "更口语"}],
    "observations": ["术语「先生」译法不一致，建议统一"],
}, ensure_ascii=False)


def test_derive_stem_strips_quality_report_suffix():
    """_质量报告.txt 后缀整段剥离；其他扩展名走 Path.stem。"""
    assert qa._derive_stem(Path("ep01_质量报告.txt")) == "ep01"
    assert qa._derive_stem(Path("dir/ep02_质量报告.txt")) == "ep02"
    assert qa._derive_stem(Path("ep03.srt")) == "ep03"
    # 仅剥扩展名时，中文文件名中段保留。
    assert qa._derive_stem(Path("ep04_质量报告")) == "ep04_质量报告"


def test_load_conflict_summary_parses_rows_and_skips_short(tmp_path):
    """表头跳过后逐行拼 #id [类型] 期望/译；不足 4 列短行跳过。"""
    csv_path = tmp_path / "ep01_术语冲突观察.csv"
    csv_path.write_text(
        "#id,term,type,expected,translated\n"
        "7,先生,称谓,老师,先生\n"
        "9,殿下,称谓,殿下\n"
        "short,row\n",
        encoding="utf-8",
    )
    assert qa._load_conflict_summary(csv_path) == (
        "  #7 [称谓] 期望: 老师 译: 先生\n"
        "  #9 [称谓] 期望: 殿下 译: "
    )


def test_load_conflict_summary_missing_or_corrupt_returns_empty(tmp_path):
    """文件缺失/空文件/csv 解析损坏 → 空串（不抛出）。"""
    assert qa._load_conflict_summary(tmp_path / "nope.csv") == ""

    empty_path = tmp_path / "empty.csv"
    empty_path.write_text("", encoding="utf-8")
    assert qa._load_conflict_summary(empty_path) == ""

    # 单字段超过 csv 模块默认上限（131072）→ csv.Error → 空串。
    corrupt_path = tmp_path / "corrupt.csv"
    corrupt_path.write_text(
        "#id,term,type,expected,translated\n"
        "1," + "x" * 140000 + ",称谓,老师,先生\n",
        encoding="utf-8",
    )
    assert qa._load_conflict_summary(corrupt_path) == ""


def test_make_ai_client_override_only_replaces_stage0_model(monkeypatch):
    """非空 override：仅槽0 模型换、入参 cfg 本体不变、其余槽原样；
    空 override：cfg 原样透传（同一对象）。"""
    from subtransjav.refine import pipeline_v2

    cfg = RefineConfig(inputs=[])
    original_model = cfg.stages[0].model
    captured: dict = {}

    def _fake_make_client(conf, slot):
        captured["cfg"] = conf
        captured["slot"] = slot
        return "fake-client"

    monkeypatch.setattr(pipeline_v2, "_make_client", _fake_make_client)

    assert qa._make_ai_client(cfg, "override/model") == "fake-client"
    assert captured["slot"] == "A"
    assert captured["cfg"] is not cfg
    assert captured["cfg"].stages[0].model == "override/model"
    assert captured["cfg"].stages[1:] == cfg.stages[1:]
    # 入参本体零变化。
    assert cfg.stages[0].model == original_model

    # 空 override 不构造副本，原样透传同一 cfg。
    assert qa._make_ai_client(cfg, "") == "fake-client"
    assert captured["cfg"] is cfg


def test_run_ai_analyze_missing_conflict_csv_and_analyze_exception(
        tmp_path, monkeypatch, capsys):
    """冲突 CSV 不存在 → 告警＋空摘要继续 rc0；分析抛异常 → rc1 且打印
    固定失败前缀。"""
    report = tmp_path / "ep01_质量报告.txt"
    report.write_text("【结论】待分析\n", encoding="utf-8")
    (tmp_path / "ep01_质量报告导读.json").write_text(
        json.dumps({"items": []}, ensure_ascii=False), encoding="utf-8")

    cfg = RefineConfig(inputs=[])
    cfg.aggregate_stats_inject = False
    # C22：媒体重点对照面零触碰，显式关闭。
    cfg.media_crosscheck_enabled = False
    args = argparse.Namespace(ai_analyze=str(report), ai_model="fake/model",
                              asr_python="", asr_model="")

    class _FakeClient:
        def _chat(self, system, user):
            return _OK_JSON

    monkeypatch.setattr(qa, "_make_ai_client", lambda *a, **k: _FakeClient())

    assert qa.run_ai_analyze(cfg, args) == 0
    out = capsys.readouterr().out
    assert "⚠️ [AI分析] 术语冲突观察 CSV 不存在" in out
    saved = json.loads((tmp_path / "ep01_AI质量建议.json")
                       .read_text(encoding="utf-8"))
    assert saved["parse_ok"] is True

    def _boom(*a, **k):
        raise RuntimeError("模拟分析崩溃")

    monkeypatch.setattr(qa, "analyze_quality_report", _boom)
    capsys.readouterr()
    assert qa.run_ai_analyze(cfg, args) == 1
    failed_out = capsys.readouterr().out
    assert "❌ [AI分析] 执行失败" in failed_out
