"""quality_autoloop——全自动质量闭环预置机制（3.3.0 预留，D2026-1028-03）。

**激活状态：默认关闭（OFF）。本模块是 D2026-1028-03 owner 开工令"冲突件
预置待启用"的承载——机制骨架先建、激活门另拍。**

激活前置（三者齐备方可接线，缺一即停）：
1. **HRO-1 条件③完整复议**（D2026-1002-02：无人值守全自动写盘须显式复议；
   owner 2026-10-28 裁"本轮暂不授权，立项时再议"）；
2. **3.1.0 基线在手**：reverify 放行门数值（Wilson 下界阈值）只能来自
   基线数据，门数值未定=永远降级人工（fail-closed）；
3. **30 条 origin:"real" 真实语料前置债务清偿**（D2026-0926-01 硬化条件，
   adaptive/自动调整族共用）。

机制形态（与既有零件的关系）：
- 分析=quality_advisor 既有链；修复=action_retranslate 既有执行器；复验=
  有限子集重检。本模块只做**编排与放行门**，不重写任何执行件
  （D2026-1002-02 C 系条件：GUI bridge 直调模块本体禁旁路重写）。
- 台账契约：每次自动动作必须携带台账上下文（provider/请求上下文/old_text
  唯一回滚依据）；无台账不得发起修复（b3 条件硬化）。
- 放行门=预注册量化门（Wilson 下界 ≥ 阈值；与 tools/c22_calibration、
  refine.eval_baseline 同公式族）。门未过=降级人工为缺省，不是可选项。
"""

from __future__ import annotations

import math

__all__ = [
    "ACTIVATION_ENABLED",
    "GATE_DEFAULTS",
    "reverify_gate",
    "plan_autofix",
    "run_autoloop_cycle",
    "main",
]

# 激活总闸：默认关。翻 True 须同时满足模块 docstring 三前置并走 decision-log
# 复议条目（D2026-1002-02 HRO-1 条件③），缺一即违规。
ACTIVATION_ENABLED = False

# 预注册门参数（PROVISIONAL/占位）：阈值 None=未定=fail-closed 永远降级人工。
GATE_DEFAULTS: dict[str, object] = {
    "reverify_wilson_lb": None,     # PROVISIONAL：复验 Wilson 下界阈值（等 3.1.0 基线）
    "max_auto_fix_entries": 20,     # PROVISIONAL：单批自动修复条目上限
    "max_reverify_n": 30,           # PROVISIONAL：复验子集规模上界（有限子集口径）
}

_WILSON_Z = 1.96


def _wilson_lb(successes: int, n: int, z: float = _WILSON_Z) -> float:
    """Wilson 下界（与 refine.eval_baseline.wilson_lower_bound 同公式；
    两处联动评议纪律，见该函数 docstring）。"""
    if n <= 0:
        return 0.0
    p = successes / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom)


def _as_int(v: object, default: int) -> int:
    return int(v) if isinstance(v, (int, float)) else default


def _as_float_or_none(v: object) -> float | None:
    return float(v) if isinstance(v, (int, float)) else None


def reverify_gate(passed: int, total: int, threshold_lb: float | None) -> bool:
    """复验放行门：Wilson 下界 ≥ 阈值才放行。

    阈值 None（未定）→ 恒 False（fail-closed）：门数值来自 3.1.0 基线，
    未定即永远降级人工，不做任何默认放行。"""
    if threshold_lb is None:
        return False
    return _wilson_lb(passed, total) >= float(threshold_lb)


def plan_autofix(suggestions: list[dict], cap: int = 20) -> list[dict]:
    """从 AI 建议中选自动修复目标（低置信优先、条目上限、台账必填）。

    术语冲突类不纳入自动重翻目标（b2 红线，D2026-1002-02）。建议项须携带
    ledger 上下文键（provider/old_text），缺任一即剔除并计数——无台账不得
    修复。"""
    eligible: list[dict] = []
    for s in suggestions:
        if str(s.get("category") or "") == "term_conflict":
            continue
        if not s.get("provider") or not s.get("old_text"):
            continue
        eligible.append(s)
    return eligible[:max(0, int(cap))]


def run_autoloop_cycle(suggestions: list[dict], *, analyze_fn=None, fix_fn=None,
                       reverify_fn=None, gate: dict[str, object] | None = None) -> dict:
    """单轮闭环编排（纯函数：执行件经参数注入，本模块零生产接线）。

    流程=PROPOSE（plan_autofix）→ AUTO_FIX（fix_fn）→ REVERIFY（reverify_fn）
    → RELEASE（门过）/ DEGRADE（门不过=缺省）。ACTIVATION_ENABLED=False 时
    直接拒绝执行（返回 refused，不触任何 fn）。"""
    if not ACTIVATION_ENABLED:
        return {"action": "refused",
                "reason": "全自动闭环默认关：激活须 HRO-1 条件③复议+3.1.0 基线门数值"
                          "+30 条真实语料三前置（见模块 docstring，D2026-1028-03）"}
    g = dict(GATE_DEFAULTS)
    if gate:
        g.update(gate)
    plan = plan_autofix(suggestions, _as_int(g["max_auto_fix_entries"], 20))
    if not plan:
        return {"action": "degrade", "reason": "无可自动修复目标", "planned": 0}
    fixed = 0
    failed = 0
    if fix_fn is not None:
        for item in plan:
            if fix_fn(item):
                fixed += 1
            else:
                failed += 1
    passed = total = 0
    if reverify_fn is not None and fixed:
        passed, total = reverify_fn(plan)
    threshold = _as_float_or_none(g["reverify_wilson_lb"])
    action = "release" if reverify_gate(passed, total, threshold) else "degrade"
    return {"action": action, "planned": len(plan), "fixed": fixed,
            "failed": failed, "reverify_passed": passed, "reverify_total": total,
            "threshold_lb": threshold}


def main(argv: list[str] | None = None) -> int:
    """CLI 仅暴露状态查看（激活面不进 CLI，防误触）。"""
    import argparse
    import json

    parser = argparse.ArgumentParser(
        prog="python -m subtransjav.refine.quality_autoloop",
        description="全自动质量闭环预置机制（默认关；激活三前置见 docstring）")
    parser.add_argument("--status", action="store_true", help="查看激活状态与门参数")
    parser.parse_args(argv)
    print(json.dumps({
        "activation_enabled": ACTIVATION_ENABLED,
        "activation_prerequisites": [
            "HRO-1 条件③完整复议（owner 拍板）",
            "3.1.0 基线门数值（reverify_wilson_lb）",
            "30 条 origin:real 真实语料（D2026-0926-01）",
        ],
        "gate_defaults": GATE_DEFAULTS,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
