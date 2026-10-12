"""方向参数化批 1 契约钉（D2026-0930-04）：命名单点映射 / validate 三查。

缺省方向（ja→zh）全链零感知是本批回归红线：现有断言不改一字，新钉只增。
"""
from pathlib import Path

from subtransjav.refine.config import RefineConfig, StageConfig
from subtransjav.refine.v2_outputs import final_stem, final_suffix


# ---------------------------------------------------------------------------
# 产物命名契约（单点映射）
# ---------------------------------------------------------------------------
def test_final_suffix_contract():
    """target=zh→"cn" 历史别名钉死；其余取语言码；缺省=zh。"""
    assert final_suffix("zh") == "cn"
    assert final_suffix("en") == "en"
    assert final_suffix("ja") == "ja"
    assert final_suffix() == "cn"
    assert final_stem("片名") == "片名_final_cn"
    assert final_stem("片名", "en") == "片名_final_en"
    assert final_stem("片名", "ja") == "片名_final_ja"


# ---------------------------------------------------------------------------
# validate 三查（白名单/同语言/缺卡前置）
# ---------------------------------------------------------------------------
def _valid_cfg(tmp_path: Path) -> RefineConfig:
    src = tmp_path / "in.srt"
    src.write_text("1\n00:00:01,000 --> 00:00:02,000\nテスト\n",
                   encoding="utf-8")
    return RefineConfig(
        inputs=[str(src)],
        stages=[StageConfig(0, True, "lmstudio", "m1"),
                StageConfig(2, True, "lmstudio", "m2")],
    )


def test_validate_default_direction_ok(tmp_path):
    assert _valid_cfg(tmp_path).validate() == []


def test_validate_rejects_same_langs(tmp_path):
    cfg = _valid_cfg(tmp_path)
    cfg.source_lang = "zh"
    cfg.target_lang = "zh"
    assert any("不得相同" in e for e in cfg.validate())


def test_validate_rejects_unknown_lang(tmp_path):
    cfg = _valid_cfg(tmp_path)
    cfg.target_lang = "fr"
    assert any("仅支持" in e for e in cfg.validate())
    cfg2 = _valid_cfg(tmp_path)
    cfg2.source_lang = "ko"
    assert any("source_lang 仅支持" in e for e in cfg2.validate())


def test_validate_non_default_direction_requires_cards(tmp_path):
    """非缺省方向：全部启用阶段须显式配卡，缺一即错；齐备后放行。"""
    cfg = _valid_cfg(tmp_path)
    cfg.target_lang = "en"
    errs = cfg.validate()
    assert any("配套模板卡" in e for e in errs)
    cfg.stages[0].instructions = str(tmp_path / "card_a.txt")
    assert any("配套模板卡" in e for e in cfg.validate())
    cfg.stages[1].instructions = str(tmp_path / "card_b.txt")
    assert cfg.validate() == []


def test_validate_default_direction_ignores_card_rule(tmp_path):
    """缺省方向不触发配卡规则（包内卡兜底，现状不动）。"""
    cfg = _valid_cfg(tmp_path)
    cfg.source_lang = "ja"
    cfg.target_lang = "zh"
    assert cfg.validate() == []
