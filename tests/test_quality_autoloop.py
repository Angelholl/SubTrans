# 3.3.0 预置机制钉（D2026-1028-03）：默认关拒执行+门 fail-closed+编排数学。
import json

from subtransjav.refine.quality_autoloop import (
    ACTIVATION_ENABLED,
    GATE_DEFAULTS,
    plan_autofix,
    reverify_gate,
    run_autoloop_cycle,
)


def _sug(i, cat="misread", provider="p", old="x"):
    return {"index": i, "category": cat, "provider": provider, "old_text": old}


class TestActivation:
    def test_default_off(self):
        assert ACTIVATION_ENABLED is False
        assert GATE_DEFAULTS["reverify_wilson_lb"] is None   # 门未定=fail-closed

    def test_cycle_refused_when_disabled(self):
        calls = []

        def fix(item):
            calls.append(item)
            return True

        r = run_autoloop_cycle([_sug(1)], fix_fn=fix)
        assert r["action"] == "refused"
        assert calls == []          # 关闭态绝不触执行件

    def test_cli_status_shows_prerequisites(self, capsys):
        from subtransjav.refine.quality_autoloop import main
        assert main(["--status"]) == 0
        st = json.loads(capsys.readouterr().out)
        assert st["activation_enabled"] is False
        assert len(st["activation_prerequisites"]) == 3


class TestGate:
    def test_threshold_none_fail_closed(self):
        assert reverify_gate(30, 30, None) is False

    def test_wilson_math(self):
        # 20/20 → LB≈0.838；阈值 0.9 → 不过；0.8 → 过
        assert reverify_gate(20, 20, 0.9) is False
        assert reverify_gate(20, 20, 0.8) is True
        assert reverify_gate(0, 0, 0.5) is False
        assert reverify_gate(0, 10, 0.0) is True    # LB=0 ≥ 0 边界放行

    def test_partial_pass(self):
        assert reverify_gate(25, 30, 0.7) is False   # LB(25,30)≈0.684<0.7
        # 精确核对：LB(25,30) 计算
        import math
        z = 1.96
        p = 25 / 30
        denom = 1 + z * z / 30
        centre = p + z * z / 60
        margin = z * math.sqrt(p * (1 - p) / 30 + z * z / (4 * 900))
        lb = (centre - margin) / denom
        assert reverify_gate(25, 30, lb) is True
        assert reverify_gate(25, 30, round(lb + 0.01, 3)) is False


class TestPlan:
    def test_cap_and_term_conflict_excluded(self):
        sug = [_sug(i) for i in range(30)] + [_sug(99, cat="term_conflict")]
        plan = plan_autofix(sug, cap=20)
        assert len(plan) == 20
        assert all(s["category"] != "term_conflict" for s in plan)

    def test_ledger_context_required(self):
        sug = [{"index": 1, "category": "misread"},           # 无 provider/old_text
               {"index": 2, "category": "misread", "provider": "p"},
               {"index": 3, "category": "misread", "old_text": "x"}]
        assert plan_autofix(sug) == []


class TestCycleMath:
    def test_release_path(self, monkeypatch):
        import subtransjav.refine.quality_autoloop as m
        monkeypatch.setattr(m, "ACTIVATION_ENABLED", True)
        fixed = []

        def fix(item):
            fixed.append(item["index"])
            return True

        def reverify(plan):
            return 20, 20

        r = run_autoloop_cycle([_sug(i) for i in range(5)], fix_fn=fix,
                               reverify_fn=reverify,
                               gate={"reverify_wilson_lb": 0.8})
        assert r["action"] == "release" and r["fixed"] == 5
        assert fixed == [0, 1, 2, 3, 4]

    def test_degrade_on_gate_fail(self, monkeypatch):
        import subtransjav.refine.quality_autoloop as m
        monkeypatch.setattr(m, "ACTIVATION_ENABLED", True)
        r = run_autoloop_cycle([_sug(1)], fix_fn=lambda i: True,
                               reverify_fn=lambda p: (1, 2),
                               gate={"reverify_wilson_lb": 0.9})
        assert r["action"] == "degrade"

    def test_no_targets_degrades(self, monkeypatch):
        import subtransjav.refine.quality_autoloop as m
        monkeypatch.setattr(m, "ACTIVATION_ENABLED", True)
        r = run_autoloop_cycle([], fix_fn=lambda i: True)
        assert r["action"] == "degrade" and r["planned"] == 0

    def test_fix_failure_counted(self, monkeypatch):
        import subtransjav.refine.quality_autoloop as m
        monkeypatch.setattr(m, "ACTIVATION_ENABLED", True)
        r = run_autoloop_cycle([_sug(i) for i in range(3)],
                               fix_fn=lambda i: i["index"] != 1,
                               reverify_fn=lambda p: (0, 0),
                               gate={"reverify_wilson_lb": None})
        assert r["fixed"] == 2 and r["failed"] == 1
        assert r["action"] == "degrade"   # 门 None → fail-closed
