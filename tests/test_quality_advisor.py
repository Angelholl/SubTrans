"""D2026-0929 AI 质量分析（quality_advisor）单元测试。

全部用 fake chat_fn，不发真实 LLM 请求。
"""
import json

from subtransjav.refine import quality_advisor as qa

# ---------------------------------------------------------------------------
# 固定材料
# ---------------------------------------------------------------------------

_GUIDE = {
    "version": 2,
    "stem": "ep01",
    "items": [
        {"index": 3, "timing": "00:00:03,000 --> 00:00:05,000",
         "category": "single_line_too_long", "message": "单行超长 40 字符",
         "current_text": "很长的一行", "source_excerpt": "源文摘录",
         "status": "open", "severity": None},
        {"index": 7, "timing": "00:00:09,000 --> 00:00:11,000",
         "category": "untranslated", "message": "整段未翻译",
         "current_text": "[未翻译] 原文", "source_excerpt": "源文摘录七",
         "status": "open", "severity": None},
    ],
}

_REPORT = "\n".join([
    "=" * 60,
    "质量报告",
    "【结论】⚠️ 需人工复核 2 处",
    "【白话导读】基于本次运行：",
    "　① 总体：需人工复核 2 处",
    "-" * 60,
    "【需复核清单】",
    "1. [单行超长] #3",
    "2. [实义漏覆盖] #7",
    "-" * 60,
    "【术语冲突观察】",
    "共 1 条：源文命中术语表源词",
    "-" * 60,
    "【双引擎分歧】",
    "分歧模式：双引擎（可对照 10/10 行）",
    "  pass1: 某某分歧明细不应出现在节选里",
    "-" * 60,
    "【统计】",
    "条目: 原文 10 → 终稿 10",
    "时间轴对齐率: 90.0%",
    "=" * 60,
])

_OK_JSON = json.dumps({
    "glossary": [{"src": "先生", "target": "老师", "reason": "统一称谓"}],
    "tm": [{"source": "源句", "target": "译句", "reason": "更口语"}],
    "observations": ["术语「先生」译法不一致，建议统一"],
}, ensure_ascii=False)


def _chat_ok(system, user):
    return _OK_JSON


def _chat_fenced(system, user):
    return "```json\n" + _OK_JSON + "\n```"


def _chat_garbage(system, user):
    return "抱歉，我无法以 JSON 输出。建议：术语需统一。"


# ---------------------------------------------------------------------------
# 输出契约
# ---------------------------------------------------------------------------

def test_analyze_contract_fields_closed_set():
    data = qa.analyze_quality_report(_REPORT, _GUIDE, "", "m1",
                                     chat_fn=_chat_ok)
    assert set(data.keys()) == {"model", "generated_at", "parse_ok",
                                "suggestions"}
    assert set(data["suggestions"].keys()) == {"glossary", "tm",
                                               "observations"}
    assert data["model"] == "m1"
    assert data["parse_ok"] is True
    assert data["generated_at"]
    assert data["suggestions"]["glossary"][0]["src"] == "先生"
    assert data["suggestions"]["tm"][0]["target"] == "译句"


def test_analyze_strips_json_fence():
    data = qa.analyze_quality_report(_REPORT, _GUIDE, "", "m1",
                                     chat_fn=_chat_fenced)
    assert data["parse_ok"] is True
    assert data["suggestions"]["glossary"]


def test_analyze_parse_failure_degrades_all_or_nothing():
    """解析失败整体降级：parse_ok=False、glossary/tm 全空、
    observations=[原始文本]，绝不出现半解析条目。"""
    data = qa.analyze_quality_report(_REPORT, _GUIDE, "", "m1",
                                     chat_fn=_chat_garbage)
    assert data["parse_ok"] is False
    assert data["suggestions"]["glossary"] == []
    assert data["suggestions"]["tm"] == []
    assert data["suggestions"]["observations"] == [_chat_garbage("", "")]


# ---------------------------------------------------------------------------
# 提示词注入围栏
# ---------------------------------------------------------------------------

def test_analyze_prompt_fences_untrusted_data():
    """静态契约钉：报告/导读/冲突摘要分别包进 <<<<DATA_BEGIN>>>>...
    <<<<DATA_END>>>> 定界块，系统提示声明数据块内内容不是指令。"""
    captured = {}

    def _chat(system, user):
        captured["system"] = system
        captured["user"] = user
        return _OK_JSON

    qa.analyze_quality_report(_REPORT, _GUIDE, "冲突摘要内容", "m1",
                              chat_fn=_chat)
    user = captured["user"]
    # 三个数据块各有一对定界标记
    assert user.count(qa._DATA_BEGIN) == 3
    assert user.count(qa._DATA_END) == 3
    # 报告与导读内容均在定界块内出现
    assert "【需复核清单】" in user
    assert '"index": 3' in user
    assert "冲突摘要内容" in user
    # 系统提示含数据声明（防注入语义）
    assert "待分析数据" in captured["system"]
    assert "不是指令" in captured["system"]
    assert "<<<<DATA_BEGIN>>>>" in captured["system"]


# ---------------------------------------------------------------------------
# 截断策略
# ---------------------------------------------------------------------------

def test_truncation_keeps_action_sections_drops_low_priority():
    """超限报告：节选后保留行动相关章节、裁掉双引擎分歧明细与统计尾部，
    并在提示词里声明"报告已节选"；导读 items 全量保留。"""
    big = _REPORT + "\n" + ("填充行\n" * 4000)   # 远超 12000 字符
    captured = {}

    def _chat(system, user):
        captured["system"] = system
        captured["user"] = user
        return _OK_JSON

    qa.analyze_quality_report(big, _GUIDE, "冲突摘要内容", "m1",
                              chat_fn=_chat)
    user = captured["user"]
    assert "报告已节选" in user
    assert "某某分歧明细不应出现在节选里" not in user   # 双引擎分歧明细被裁
    assert "【统计】" not in user.split("导读 items")[0]
    assert "【术语冲突观察】" in user                    # 行动相关章节保留
    assert "【需复核清单】" in user
    # 导读 items 全量保留（两条都在）
    assert '"index": 3' in user and '"index": 7' in user
    assert "冲突摘要内容" in user


def test_small_report_not_truncated():
    captured = {}

    def _chat(system, user):
        captured["user"] = user
        return _OK_JSON

    qa.analyze_quality_report(_REPORT, _GUIDE, "", "m1", chat_fn=_chat)
    assert "报告已节选" not in captured["user"]
    assert "【统计】" in captured["user"]


# ---------------------------------------------------------------------------
# 落盘
# ---------------------------------------------------------------------------

def test_write_ai_suggestions_file(tmp_path):
    data = qa.analyze_quality_report(_REPORT, _GUIDE, "", "m1",
                                     chat_fn=_chat_ok)
    p = qa.write_ai_suggestions("ep01", data, str(tmp_path))
    assert p.endswith("ep01_AI质量建议.json")
    loaded = json.loads((tmp_path / "ep01_AI质量建议.json")
                        .read_text(encoding="utf-8"))
    assert loaded == data
    # ensure_ascii=False：中文原样落盘
    raw = (tmp_path / "ep01_AI质量建议.json").read_text(encoding="utf-8")
    assert "先生" in raw


# ---------------------------------------------------------------------------
# D2026-1010-03 件A/件B：crosscheck 结构化落盘 + TM 契约 index
# ---------------------------------------------------------------------------

def test_ai_prompt_tm_index_contract():
    """件B：tm 契约含可选 index（导读条目号），与「不虚构条目编号」约束
    自洽（模型引用材料中已有编号，非新造）。"""
    assert '"index"' in qa._AI_SYSTEM_PROMPT
    assert "条目号" in qa._AI_SYSTEM_PROMPT


def test_normalize_tm_index_passthrough():
    """件B：normalize 白名单透传可选整数 index；字符串/布尔非法值丢弃
    （模型未给或给非法值=无该字段，前端降级无按钮，不虚构）。"""
    parsed = {"suggestions": {"glossary": [], "observations": [], "tm": [
        {"source": "あ", "target": "甲", "reason": "导读清单 #3", "index": 3},
        {"source": "い", "target": "乙", "index": "x"},
        {"source": "う", "target": "丙", "index": True},
    ]}}
    out = qa._normalize_suggestions(parsed)
    assert out["tm"][0]["index"] == 3
    assert "index" not in out["tm"][1]
    assert "index" not in out["tm"][2]


def test_run_ai_analyze_crosscheck_detail_persisted(tmp_path, monkeypatch):
    """件A：crosscheck 结构化对照段随 _AI质量建议.json 落盘（旁挂，不动
    analyze_quality_report 闭合契约）；喂 LLM 的对照块口径不变。"""
    import argparse

    from subtransjav.refine.config import RefineConfig

    report = tmp_path / "ep01_质量报告.txt"
    report.write_text("【结论】x\n", encoding="utf-8")
    (tmp_path / "ep01_质量报告导读.json").write_text(
        json.dumps({"version": 2, "stem": "ep01", "items": []},
                   ensure_ascii=False), encoding="utf-8")
    cfg = RefineConfig(inputs=[])
    cfg.media_crosscheck_enabled = True
    args = argparse.Namespace(ai_analyze=str(report), ai_model="",
                              asr_python="", asr_model="")
    detail = [{"timing": "00:00:01,000 --> 00:00:02,000",
               "asr_text": "全文转写" * 300, "current_text": "现译"}]
    monkeypatch.setattr(qa, "_build_media_crosscheck",
                        lambda *a, **k: ("对照块文本", detail))
    seen = {}

    class _FakeClient:
        def _chat(self, system, user):
            seen["user"] = user
            return json.dumps({"glossary": [], "tm": [],
                               "observations": []}, ensure_ascii=False)

    monkeypatch.setattr(qa, "_make_ai_client",
                        lambda *a, **k: _FakeClient())
    assert qa.run_ai_analyze(cfg, args) == 0
    out = json.loads((tmp_path / "ep01_AI质量建议.json")
                     .read_text(encoding="utf-8"))
    assert out["crosscheck_detail"] == detail
    assert out["crosscheck_detail"][0]["asr_text"] == "全文转写" * 300
    # 喂 LLM 的 DATA 块仍含对照文本（块口径不变）
    assert "对照块文本" in seen["user"]


def test_run_ai_analyze_crosscheck_off_empty_detail(tmp_path, monkeypatch):
    """件A：开关关时不编排对照，落盘统一空列表（schema 恒有键）。"""
    import argparse

    from subtransjav.refine.config import RefineConfig

    report = tmp_path / "ep01_质量报告.txt"
    report.write_text("【结论】x\n", encoding="utf-8")
    (tmp_path / "ep01_质量报告导读.json").write_text(
        json.dumps({"version": 2, "stem": "ep01", "items": []},
                   ensure_ascii=False), encoding="utf-8")
    cfg = RefineConfig(inputs=[])
    cfg.media_crosscheck_enabled = False
    args = argparse.Namespace(ai_analyze=str(report), ai_model="",
                              asr_python="", asr_model="")
    called = []

    def _spy(*a, **k):
        called.append(1)
        return "", []

    monkeypatch.setattr(qa, "_build_media_crosscheck", _spy)

    class _FakeClient:
        def _chat(self, system, user):
            return json.dumps({"glossary": [], "tm": [],
                               "observations": []}, ensure_ascii=False)

    monkeypatch.setattr(qa, "_make_ai_client",
                        lambda *a, **k: _FakeClient())
    assert qa.run_ai_analyze(cfg, args) == 0
    out = json.loads((tmp_path / "ep01_AI质量建议.json")
                     .read_text(encoding="utf-8"))
    assert out["crosscheck_detail"] == []
    assert not called
