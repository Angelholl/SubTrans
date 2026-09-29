"""方向参数化批 2 测试（D2026-0930-04）：透传与门控。

缺省方向逐字节不变是放行门（D2026-0930-03 ③ E2E 快照口径）：每枚测试
都成对钉"缺省=现状 / 非缺省=新行为"。
"""
import json
from types import SimpleNamespace

from subtransjav.refine.language_validator import (
    _normalize_target,
    is_valid_stage_text,
)
from subtransjav.refine.manifest import _v2_stage_prompts_sha1
from subtransjav.refine.pipeline_v2 import (
    _generic_stage_prompt,
    _grammar_cache_key,
    _is_default_direction,
    _load_v2_instruction,
)
from subtransjav.refine.source_hallucination import is_fluent_target
from subtransjav.refine.v2_outputs import final_stem


# ---------------------------------------------------------------------------
# 缺省方向判定
# ---------------------------------------------------------------------------
def test_is_default_direction():
    cfg = SimpleNamespace(source_lang="ja", target_lang="zh")
    assert _is_default_direction(cfg) is True
    assert _is_default_direction(SimpleNamespace(
        source_lang="ja", target_lang="en")) is False
    assert _is_default_direction(SimpleNamespace()) is True   # 缺席=缺省


# ---------------------------------------------------------------------------
# 提示词方向分派（缺省字节不变 / 非缺省通用词）
# ---------------------------------------------------------------------------
def test_generic_stage_prompt_direction_wording():
    a = _generic_stage_prompt("A", "ja", "en")
    b = _generic_stage_prompt("B", "zh", "en")
    assert "翻译成英文" in a and "英文译文" in a
    assert "英文原文 ||| 英文译文" in b or "中文原文 ||| 英文译文" in b
    # 无日语特调段标记（拟声假名/中文抛光豁免等仅 ja→zh 所有）
    from subtransjav.refine.pipeline_v2 import V2_STAGE_PROMPTS
    for tag in ("A", "B"):
        assert _generic_stage_prompt(tag, "ja", "zh") != V2_STAGE_PROMPTS[tag]


def test_load_v2_instruction_default_byte_identical(tmp_path):
    """缺省方向：无 ### prompt 卡拼内置提示词（现状路径，B 卡加固段照旧）。"""
    from subtransjav.refine.pipeline_v2 import V2_STAGE_PROMPTS
    card = tmp_path / "card_a.txt"
    card.write_text("你是净语翻译角色。", encoding="utf-8")
    cfg = _cfg_for(card, tmp_path)
    system_text, user_prompt = _load_v2_instruction(
        cfg, "A", "", str(tmp_path))
    assert V2_STAGE_PROMPTS["A"] in system_text + user_prompt


def test_load_v2_instruction_non_default_suppresses_hardened(tmp_path):
    """非缺省方向：卡无 ### prompt 时拼通用提示词，不追加中文抛光豁免段。"""
    from subtransjav.refine.pipeline_v2 import hardened_suffix
    card = tmp_path / "card_a_en.txt"
    card.write_text("You are a clean-translate role.", encoding="utf-8")
    cfg = _cfg_for(card, tmp_path)
    cfg.target_lang = "en"
    system_text, user_prompt = _load_v2_instruction(
        cfg, "A", "", str(tmp_path))
    joined = system_text + user_prompt
    assert "翻译成英文" in joined
    assert hardened_suffix().strip()[:20] not in joined
    # B 阶段同样抑制
    card_b = tmp_path / "card_b_en.txt"
    card_b.write_text("You are a polish role.", encoding="utf-8")
    cfg.stages[1].instructions = str(card_b)
    s2, u2 = _load_v2_instruction(cfg, "B", "", str(tmp_path))
    assert hardened_suffix().strip()[:20] not in s2 + u2
    assert "『日文原文 ||| 英文译文』" in s2 + u2 or \
        "『中文原文 ||| 英文译文』" in s2 + u2


def _cfg_for(card_path, tmp_path):
    """最小 cfg：4 槽 stages（0/2 生产槽各配显式卡，1/3 停用）——槽位对齐
    V2_STAGE_SLOT 索引语义。"""
    from subtransjav.refine.config import RefineConfig, StageConfig
    return RefineConfig(
        inputs=[str(tmp_path / "in.srt")] if (tmp_path / "in.srt").exists()
        else [],
        stages=[StageConfig(0, True, "lmstudio", "m1",
                            instructions=str(card_path)),
                StageConfig(1, False, "lmstudio", ""),
                StageConfig(2, True, "lmstudio", "m2",
                            instructions=str(card_path)),
                StageConfig(3, False, "lmstudio", "")],
        templates_dir=str(tmp_path),
    )


# ---------------------------------------------------------------------------
# 语言校验 en 签名（D2026-0930-04 ⑤）
# ---------------------------------------------------------------------------
def test_normalize_target_aliases():
    assert _normalize_target("zh") == "zh"
    assert _normalize_target("chinese") == "zh"
    assert _normalize_target("en") == "en"
    assert _normalize_target("english") == "en"
    assert _normalize_target("ja") == "ja"
    assert _normalize_target("fr") == "ja"      # 未知归 ja（旧行为等价）


def test_en_signature_valid_and_invalid():
    assert is_valid_stage_text("Hello world!", "en") is True
    assert is_valid_stage_text("Stop it.", "en") is True
    assert is_valid_stage_text("こんにちは", "en") is False   # 假名残留
    assert is_valid_stage_text("テストです", "en") is False
    assert is_valid_stage_text("12345", "en") is False        # 须含拉丁字母
    # zh/ja 现状语义不变（纯拉丁仍无效）
    assert is_valid_stage_text("Hello world!", "zh") is False
    assert is_valid_stage_text("こんにちは、皆さん。", "ja") is True


# ---------------------------------------------------------------------------
# 质量门分派（is_fluent_target）
# ---------------------------------------------------------------------------
def test_is_fluent_target_dispatch():
    assert is_fluent_target("Hello there, friend.", "en") is True
    assert is_fluent_target("こんにちは", "en") is False
    assert is_fluent_target("a", "en") is False               # <2 拉丁字母
    assert is_fluent_target("这是一个测试译文", "zh") is True
    assert is_fluent_target("[未翻译]テスト", "zh") is False


# ---------------------------------------------------------------------------
# 文法缓存键方向隔离
# ---------------------------------------------------------------------------
def test_grammar_cache_key_includes_direction():
    k1 = _grammar_cache_key("テスト", "A", "local")
    k2 = _grammar_cache_key("テスト", "A", "local", "ja→en")
    assert k1 != k2
    assert k1[3] == "ja→zh"
    assert k1[:3] == _grammar_cache_key("テスト", "A", "local",
                                        "ja→zh")[:3]


# ---------------------------------------------------------------------------
# manifest 提示词指纹 cfg 感知（缺省=旧值 / 非缺省=变）
# ---------------------------------------------------------------------------
def test_v2_stage_prompts_sha1_default_matches_legacy():
    assert _v2_stage_prompts_sha1() == _v2_stage_prompts_sha1(
        SimpleNamespace(source_lang="ja", target_lang="zh"))
    assert _v2_stage_prompts_sha1(
        SimpleNamespace(source_lang="ja", target_lang="en")) != \
        _v2_stage_prompts_sha1()


# ---------------------------------------------------------------------------
# GUI 完成检测方向化（event_stream.resume_state_for_path）
# ---------------------------------------------------------------------------
def test_resume_state_direction_aware(tmp_path, monkeypatch):
    import os

    from subtransjav.webview_gui.event_stream import resume_state_for_path
    srt = tmp_path / "show.srt"
    srt.write_text("1\n00:00:01,000 --> 00:00:02,000\nx\n", encoding="utf-8")
    # ja→en 任务：_final_en.srt 存在即 completed（_final_cn 不存在）
    (tmp_path / "show_manifest.json").write_text(
        json.dumps({"direction": "ja→en"}), encoding="utf-8")
    (tmp_path / f"{final_stem('show', 'en')}.srt").write_text(
        "1\n00:00:01,000 --> 00:00:02,000\nok\n", encoding="utf-8")
    st = resume_state_for_path(str(srt), exists=os.path.exists,
                               strip_stem=lambda s: s)
    assert st["state"] == "completed"
    # 旧 manifest（无 direction 字段）回退缺省：_final_en 不算完成
    (tmp_path / "show_manifest.json").write_text("{}", encoding="utf-8")
    st2 = resume_state_for_path(str(srt), exists=os.path.exists,
                                strip_stem=lambda s: s)
    assert st2["state"] == "resumable"
