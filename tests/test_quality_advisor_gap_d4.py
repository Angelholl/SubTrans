"""D2026-1031-07 卡D4：quality_advisor 前置校验与降级补测。

补充既有 test_quality_advisor.py 未覆盖的分支：截断尾部丢块、
_normalize_suggestions 形状容错、chat_fn 异常/围栏/花括号兜底、
run_ai_analyze 前置 rc1 与聚合/媒体对照降级、run_warmup 未配置模型。

全部用 fake chat_fn / fake 客户端 / tmp_path 假报告导读，不发真实网络请求。
"""
import argparse
import dataclasses
import json

from subtransjav.refine import quality_advisor as qa
from subtransjav.refine.config import RefineConfig

_OK_JSON = json.dumps({
    "glossary": [{"src": "先生", "target": "老师", "reason": "统一称谓"}],
    "tm": [{"source": "源句", "target": "译句", "reason": "更口语"}],
    "observations": ["术语「先生」译法不一致，建议统一"],
}, ensure_ascii=False)


def _chat_ok(system, user):
    return _OK_JSON


def test_truncate_report_keep_sections_and_tail_drop():
    """未超限原样返回；超限只留 _KEEP_SECTIONS，超预算从尾部丢块即停。"""
    small = "【结论】短报告无需截断"
    assert qa.truncate_report(small) is small

    big = "\n".join([
        "前导" * 20,
        "【白话导读】", "导读" * 30,
        "【结论】", "结论" * 30,
        "【双引擎分歧】", "分歧" * 50,
        "【统计】", "统计" * 50,
    ])
    assert len(big) > 120

    # 预算足够容纳保留章节：非保留章节整块丢弃，保留章节原样留下。
    kept = qa.truncate_report(big, limit=200)
    assert "【白话导读】" in kept and "【结论】" in kept
    assert "【双引擎分歧】" not in kept and "【统计】" not in kept

    # 预算收紧：保留章节也放不下时从当前块起停，后续块全部丢弃。
    tight = qa.truncate_report(big, limit=120)
    assert "【白话导读】" in tight
    assert "【结论】" not in tight
    assert len(tight) <= len(big)


def test_normalize_suggestions_top_level_and_field_passthrough():
    """顶层形态容错；aliases/reason 透传；index 仅收 int（排除 bool）；
    形状不符整体 None。"""
    top = {
        "glossary": [{"src": "先生", "target": "老师",
                      "aliases": ["老师", "先生"], "reason": "统一称谓"}],
        "tm": [{"source": "あ", "target": "甲", "reason": "更口语",
                "index": 7}],
        "observations": ["观察一", ""],
    }
    out = qa._normalize_suggestions(top)
    assert out is not None
    assert out["glossary"] == [{"src": "先生", "target": "老师",
                                "aliases": ["老师", "先生"],
                                "reason": "统一称谓"}]
    assert out["tm"][0]["reason"] == "更口语"
    assert out["tm"][0]["index"] == 7
    assert out["observations"] == ["观察一"]

    # bool 是 int 子类但必须排除；aliases 元素按 str 透传。
    bool_idx = qa._normalize_suggestions({"suggestions": {
        "glossary": [{"src": "x", "target": "y", "aliases": [1]}],
        "tm": [{"source": "a", "target": "b", "index": True}],
        "observations": [],
    }})
    assert bool_idx is not None
    assert bool_idx["glossary"][0]["aliases"] == ["1"]
    assert "index" not in bool_idx["tm"][0]

    # 形状不符 → None（整体降级，禁半解析）。
    assert qa._normalize_suggestions(
        {"suggestions": {"glossary": {}, "tm": [], "observations": []}}
    ) is None
    assert qa._normalize_suggestions(
        {"glossary": [], "tm": "不是列表", "observations": []}
    ) is None
    assert qa._normalize_suggestions({"suggestions": []}) is None


def test_analyze_quality_report_chat_exception_and_json_fallbacks():
    """chat_fn 抛异常→parse_ok=False＋固定观察回退；围栏与首尾花括号
    兜底解析成功。"""
    def boom(system, user):
        raise RuntimeError("模拟网络不可用")

    failed = qa.analyze_quality_report(
        "【结论】x", {"items": []}, "", "fake/model", chat_fn=boom)
    assert failed["parse_ok"] is False
    assert failed["suggestions"] == {
        "glossary": [], "tm": [],
        "observations": ["LLM 调用失败，无原始文本"]}

    def fenced(system, user):
        return "```json\n" + _OK_JSON + "\n```"

    fenced_out = qa.analyze_quality_report(
        "【结论】x", {"items": []}, "", "fake/model", chat_fn=fenced)
    assert fenced_out["parse_ok"] is True
    assert fenced_out["suggestions"]["glossary"][0]["src"] == "先生"

    def brace_wrapped(system, user):
        return "模型说明在前 " + _OK_JSON + " 说明在后"

    brace_out = qa.analyze_quality_report(
        "【结论】x", {"items": []}, "", "fake/model", chat_fn=brace_wrapped)
    assert brace_out["parse_ok"] is True
    assert brace_out["suggestions"]["tm"][0]["source"] == "源句"


def test_run_ai_analyze_preconditions_and_degraded_continue(
        tmp_path, monkeypatch):
    """报告/导读/JSON/items/客户端失败均 rc1；聚合与媒体对照失败按无
    对应块继续；成功路径落盘建议件。"""
    from subtransjav.refine import aggregate_stats, asr_env

    cfg = RefineConfig(inputs=[])
    cfg.aggregate_stats_inject = False
    cfg.media_crosscheck_enabled = False
    args = argparse.Namespace(ai_analyze="", ai_model="fake/model-a",
                              asr_python="", asr_model="")

    # 1) 质量报告缺失 → rc1
    args.ai_analyze = str(tmp_path / "nope_质量报告.txt")
    assert qa.run_ai_analyze(cfg, args) == 1

    # 2) 导读缺失 → rc1
    report = tmp_path / "ep01_质量报告.txt"
    report.write_text("【结论】待分析\n", encoding="utf-8")
    args.ai_analyze = str(report)
    assert qa.run_ai_analyze(cfg, args) == 1

    guide_path = tmp_path / "ep01_质量报告导读.json"
    # 3) 导读非法 JSON → rc1
    guide_path.write_text("{不是合法 JSON", encoding="utf-8")
    assert qa.run_ai_analyze(cfg, args) == 1

    # 4) items 非 list → rc1
    guide_path.write_text(json.dumps({"items": {}}, ensure_ascii=False),
                          encoding="utf-8")
    assert qa.run_ai_analyze(cfg, args) == 1

    guide_path.write_text(json.dumps({"items": []}, ensure_ascii=False),
                          encoding="utf-8")

    # 5) 客户端构造失败 → rc1
    def _bad_client(*a, **k):
        raise RuntimeError("模拟客户端构造失败")

    monkeypatch.setattr(qa, "_make_ai_client", _bad_client)
    assert qa.run_ai_analyze(cfg, args) == 1

    seen_users = []

    class _FakeClient:
        def _chat(self, system, user):
            seen_users.append(user)
            return _OK_JSON

    monkeypatch.setattr(qa, "_make_ai_client", lambda *a, **k: _FakeClient())

    # 6) 聚合构建失败 → 按无聚合继续，rc0
    orig_aggregate = aggregate_stats.build_aggregate_block

    def _bad_aggregate(*a, **k):
        raise RuntimeError("模拟聚合库不可用")

    monkeypatch.setattr(aggregate_stats, "build_aggregate_block",
                        _bad_aggregate)
    cfg.aggregate_stats_inject = True
    assert qa.run_ai_analyze(cfg, args) == 0
    assert "跨片聚合统计（只读" not in seen_users[-1]
    monkeypatch.setattr(aggregate_stats, "build_aggregate_block",
                        orig_aggregate)
    cfg.aggregate_stats_inject = False

    # 7) 媒体对照失败 → 按无对照继续，rc0，detail 为空列表
    cfg.media_crosscheck_enabled = True
    guide_path.write_text(json.dumps({
        "items": [{"index": 1, "category": "suspected_missed_speech",
                   "timing": "00:00:01,000 --> 00:00:02,000",
                   "current_text": "现译"}],
        "media_path": str(tmp_path / "fake_media.mp4"),
    }, ensure_ascii=False), encoding="utf-8")
    orig_slice = asr_env.slice_clips

    def _bad_slice(*a, **k):
        raise RuntimeError("模拟切片失败")

    monkeypatch.setattr(asr_env, "slice_clips", _bad_slice)
    assert qa.run_ai_analyze(cfg, args) == 0
    assert "媒体重点对照" not in seen_users[-1]
    degraded = json.loads((tmp_path / "ep01_AI质量建议.json")
                          .read_text(encoding="utf-8"))
    assert degraded["crosscheck_detail"] == []
    monkeypatch.setattr(asr_env, "slice_clips", orig_slice)
    cfg.media_crosscheck_enabled = False

    # 8) 成功路径 → 建议件落盘（tmp_path），字段契约完整
    assert qa.run_ai_analyze(cfg, args) == 0
    out = json.loads((tmp_path / "ep01_AI质量建议.json")
                     .read_text(encoding="utf-8"))
    assert out["model"] == "fake/model-a"
    assert out["parse_ok"] is True
    assert out["suggestions"]["glossary"][0]["target"] == "老师"
    assert len(out["suggestions"]["tm"]) == 1
    assert out["crosscheck_detail"] == []


def test_run_warmup_missing_model_rc1(monkeypatch):
    """模型未配置（槽A 空且服务商无默认）→ rc1，且不构造客户端。"""
    cfg = RefineConfig(inputs=[])
    cfg.stages[0] = dataclasses.replace(cfg.stages[0], model="",
                                        provider="lmstudio")
    args = argparse.Namespace(ai_model="")

    def _must_not_build(*a, **k):
        raise AssertionError("模型未配置时不应构造客户端")

    monkeypatch.setattr(qa, "_make_ai_client", _must_not_build)
    assert qa.run_warmup(cfg, args) == 1
