"""D6 回归钉：已否决旧缺省模型 gemma3:12b 的清理与兼容告警。

- PROVIDER_CONFIGS 任一缺省不再含 "gemma"（防回添）；
- v1 配置读入 model=="gemma3:12b" 时告警并清空，落回自动推荐链
  （PROVIDER_MODEL_DEFAULTS → 空值由 validate 的非空校验兜底）；
- recommend_model 覆盖链最小钉：空模型经 resolve_model 取推荐值。
"""

from __future__ import annotations

import json

from subtransjav.refine.config import PROVIDER_MODEL_DEFAULTS, RefineConfig, StageConfig
from subtransjav.translate.providers import PROVIDER_CONFIGS

_LEGACY_VETO_MODEL = "gemma3:12b"


def test_no_gemma_in_provider_default_models():
    """断言 PROVIDER_CONFIGS 任一缺省模型不含 "gemma"（不区分大小写）。"""
    blob = json.dumps(PROVIDER_CONFIGS, ensure_ascii=False).lower()
    assert "gemma" not in blob


def test_legacy_gemma_model_warned_and_cleared(capsys):
    """旧缺省 gemma3:12b 读入：打印告警、模型清空落回推荐链；
    其他阶段模型不受影响。"""
    cfg = RefineConfig(
        inputs=["a.srt"],
        stages=[
            StageConfig(0, True, "lmstudio", _LEGACY_VETO_MODEL),
            StageConfig(1, False, "deepseek", ""),
            StageConfig(2, True, "lmstudio", "custom-model-b"),
            StageConfig(3, False, "lmstudio", ""),
        ])
    out = capsys.readouterr().out
    assert "检测到已否决的旧缺省模型 gemma3:12b" in out
    assert "本次运行将使用自动推荐模型" in out
    assert cfg.stages[0].model == ""
    assert cfg.stages[2].model == "custom-model-b"


def test_recommend_model_chain_pin():
    """覆盖链钉：空模型经 resolve_model 取 PROVIDER_MODEL_DEFAULTS
    推荐值；彻底为空时 validate 报"未指定模型名"兜底。"""
    cfg = RefineConfig(inputs=["a.srt"])
    empty_stage = StageConfig(0, True, "lmstudio", "")
    assert cfg.resolve_model(empty_stage) \
        == PROVIDER_MODEL_DEFAULTS["lmstudio"]
    # 兜底：推荐值也为空的服务商（如 custom 未填）在 validate 报错
    bad = RefineConfig(inputs=["a.srt"],
                       stages=[StageConfig(0, True, "custom", "")])
    errors = bad.validate()
    assert any("未指定模型名" in e for e in errors)
