"""D11 契约④⑤ 行动层重翻执行器测试：全部真函数 + tmp_path + FakeClient
monkeypatch（_make_action_client 注入点），不起真 LLM、不触网。"""

import argparse
import json

import pytest

from subtransjav.refine import action_retranslate
from subtransjav.refine.action_retranslate import (
    parse_entries_arg,
    run_action_retranslate,
)
from subtransjav.refine.config import RefineConfig
from subtransjav.refine.filters import build_srt, parse_srt

T1 = "00:00:01,000 --> 00:00:02,000"
T2 = "00:00:03,000 --> 00:00:04,000"
T3 = "00:00:05,000 --> 00:00:06,000"
T4 = "00:00:07,000 --> 00:00:08,000"

FINAL_ENTRIES = [
    {"index": 1, "timing": T1, "text": "こんにちは"},
    {"index": 2, "timing": T2, "text": "[未翻译] テスト"},
    {"index": 3, "timing": T3, "text": "前辈真厉害"},
    {"index": 4, "timing": T4, "text": "四"},
]

LEDGER_FIELDS = {"index", "timing", "category", "old_text", "new_text",
                 "model_used", "outcome", "reason", "ts", "source_partial"}


def _item(index, timing, text, category="mistranslation", **kw):
    it = {"index": index, "timing": timing, "category": category,
          "message": "疑似误译", "current_text": text,
          "source_excerpt": "せんぱい", "status": "open", "severity": "warning"}
    it.update(kw)
    return it


def _write_final(tmp_path, entries):
    (tmp_path / "ep01_final_cn.srt").write_text(build_srt(entries),
                                                encoding="utf-8")


def _write_guide(tmp_path, items):
    guide = {"version": 2, "source": "ep01.srt", "stem": "ep01",
             "generated_at": "2026-01-01 00:00:00", "basis": "基于本次运行",
             "conclusions": ["结论甲"], "sections": ["章节乙"],
             "extras": {"对齐率": "90.0%"}, "items": items,
             "companions": {}}
    p = tmp_path / "ep01_质量报告导读.json"
    p.write_text(json.dumps(guide, ensure_ascii=False), encoding="utf-8")
    return p


def _args(tmp_path, **kw):
    defaults = dict(
        action_retranslate=str(tmp_path / "ep01_质量报告导读.json"),
        entries="", action_source="", action_model="",
        action_sample=0, apply=False)
    defaults.update(kw)
    return argparse.Namespace(**defaults)


def _cfg():
    return RefineConfig(inputs=[])


def _read_final(tmp_path):
    return parse_srt((tmp_path / "ep01_final_cn.srt").read_text(
        encoding="utf-8"))


def _read_ledger(tmp_path):
    return json.loads((tmp_path / "ep01_重翻记录.json").read_text(
        encoding="utf-8"))


class FakeClient:
    """单条 _chat 替身：按序回放响应（序列元素为 Exception 实例则抛出）
    或整体抛错，记录全部调用。"""

    def __init__(self, responses=None, error=None):
        self.calls = []
        self.responses = list(responses or [])
        self.error = error

    def _chat(self, system_text, user_text, max_tokens=None):
        self.calls.append((system_text, user_text))
        if self.error is not None:
            raise self.error
        if self.responses:
            item = self.responses.pop(0)
            if isinstance(item, BaseException):
                raise item
            return item
        return "重翻后的中文台词"


@pytest.fixture
def install_client(monkeypatch):
    """安装 _make_action_client 注入点替身，返回 FakeClient 实例。"""
    def _install(responses=None, error=None):
        fake = FakeClient(responses=responses, error=error)
        monkeypatch.setattr(action_retranslate, "_make_action_client",
                            lambda cfg, model_override="": fake)
        return fake
    return _install


# ---------------------------------------------------------------------------
# --entries 解析
# ---------------------------------------------------------------------------

def test_parse_entries_arg_single_range_and_mixed():
    assert parse_entries_arg("3") == {3}
    assert parse_entries_arg("12-15") == {12, 13, 14, 15}
    assert parse_entries_arg("3,7,12-15") == {3, 7, 12, 13, 14, 15}
    assert parse_entries_arg(" 3 , 7 ") == {3, 7}      # 容忍空隙空白
    assert parse_entries_arg("") == set()              # 缺省=空集


@pytest.mark.parametrize("spec", ["3;a", "a", "1,,2", "15-12", "1-2-3", "-5"])
def test_parse_entries_arg_illegal_raises(spec):
    with pytest.raises(ValueError):
        parse_entries_arg(spec)


# ---------------------------------------------------------------------------
# dry-run：零写入 + 计划打印
# ---------------------------------------------------------------------------

def test_dry_run_zero_writes_and_prints_plan(tmp_path, capsys):
    _write_final(tmp_path, FINAL_ENTRIES)
    guide_path = _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト", category="untranslated"),
        _item(3, T3, "前辈真厉害"),
    ])
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    rc = run_action_retranslate(_cfg(), _args(tmp_path))
    assert rc == 0
    after = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert before == after                          # 零写入（含台账不产生）
    out = capsys.readouterr().out
    assert "重翻计划" in out and "零写入" in out
    assert "#2" in out and "#3" in out
    assert "テスト" in out[:out.index("#3")]        # 现译文本预览出现
    assert guide_path.is_file()


# ---------------------------------------------------------------------------
# apply：恒等式（非目标块逐字节不变 + 目标块文本更新）
# ---------------------------------------------------------------------------

def test_apply_updates_targets_and_keeps_others_byte_identical(
        tmp_path, install_client):
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト"),
        _item(3, T3, "前辈真厉害"),
    ])
    install_client(responses=["新翻的第二块。", "重翻的第三块。"])
    rc = run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert rc == 0
    entries = _read_final(tmp_path)
    assert len(entries) == len(FINAL_ENTRIES)       # 条目数不变
    assert [e["timing"] for e in entries] == \
        [e["timing"] for e in FINAL_ENTRIES]        # 逐块 timing 全等
    assert entries[0]["text"] == "こんにちは"        # 非目标块原样
    assert entries[3]["text"] == "四"
    assert entries[1]["text"] == "新翻的第二块。"     # 目标块文本更新
    assert entries[2]["text"] == "重翻的第三块。"


# ---------------------------------------------------------------------------
# timing 定位纪律：歧义/未命中/空 timing 一律 failed 不猜
# ---------------------------------------------------------------------------

def test_timing_ambiguity_miss_and_empty_recorded_failed(
        tmp_path, install_client):
    dup = [dict(e) for e in FINAL_ENTRIES]
    dup[2]["timing"] = T2                            # 人造 timing 歧义
    _write_final(tmp_path, dup)
    _write_guide(tmp_path, [
        _item(5, T2, "x"),                           # 命中两块 → 歧义
        _item(6, "00:00:99,000 --> 00:00:99,500", "y"),  # 未命中
        _item(7, "", "z"),                           # 空 timing
    ])
    fake = install_client()
    rc = run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert rc == 1                                   # 全败
    records = _read_ledger(tmp_path)
    assert len(records) == 3
    assert all(r["outcome"] == "failed" for r in records)
    assert "歧义" in records[0]["reason"]
    assert "未命中" in records[1]["reason"]
    assert "timing 为空" in records[2]["reason"]
    assert fake.calls == []                          # 绝不猜 → 零 LLM 调用
    # 终稿未被改动
    assert _read_final(tmp_path) == parse_srt(build_srt(dup))


# ---------------------------------------------------------------------------
# 失败最小质量门：不过→保留原文 outcome=failed
# ---------------------------------------------------------------------------

def test_quality_gate_failures_keep_original_text(tmp_path, install_client):
    """批6 改判后：真质量门失败（非合格中文）仍 failed；等值形态见
    test_equal_translation_marks_nochange_rc0。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト"),
    ])
    install_client(responses=["123456"])
    rc = run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert rc == 1
    assert _read_final(tmp_path) == parse_srt(build_srt(FINAL_ENTRIES))
    records = _read_ledger(tmp_path)
    assert all(r["outcome"] == "failed" for r in records)
    assert "合格中文" in records[0]["reason"]
    assert records[0]["new_text"] == "123456"        # 落选候选入台账供审计


def test_llm_call_exception_marks_item_failed_not_batch(
        tmp_path, install_client):
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト"),
        _item(3, T3, "前辈真厉害"),
    ])
    install_client(responses=[RuntimeError("boom"), "合格的新译文。"])
    rc = run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert rc == 3                                   # 一败一成 → 部分降级
    records = _read_ledger(tmp_path)
    assert records[0]["outcome"] == "failed"
    assert "LLM 调用失败" in records[0]["reason"]
    assert records[1]["outcome"] == "applied"
    assert _read_final(tmp_path)[2]["text"] == "合格的新译文。"


def test_client_construction_failure_marks_all_failed(tmp_path, monkeypatch):
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [_item(2, T2, "[未翻译] テスト")])

    def _boom(cfg, model_override=""):
        raise RuntimeError("no endpoint")
    monkeypatch.setattr(action_retranslate, "_make_action_client", _boom)
    rc = run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert rc == 1
    records = _read_ledger(tmp_path)
    assert records[0]["outcome"] == "failed"
    assert "客户端构造失败" in records[0]["reason"]


# ---------------------------------------------------------------------------
# 台账：累积追加与字段齐全
# ---------------------------------------------------------------------------

def test_ledger_appends_across_runs_with_full_fields(tmp_path, install_client):
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト"),
        _item(3, T3, "前辈真厉害"),
    ])
    install_client(responses=["第一轮改写文本。"])
    assert run_action_retranslate(
        _cfg(), _args(tmp_path, apply=True, entries="2")) == 0
    install_client(responses=["第二轮改写文本。"])
    assert run_action_retranslate(
        _cfg(), _args(tmp_path, apply=True, entries="3")) == 0
    records = _read_ledger(tmp_path)
    assert len(records) == 2                         # 累积追加不覆盖
    assert records[0]["index"] == 2 and records[1]["index"] == 3
    for r in records:
        assert set(r) >= LEDGER_FIELDS
        assert r["outcome"] == "applied"
        assert r["ts"] and r["model_used"]
        assert r["old_text"] and r["new_text"]


# ---------------------------------------------------------------------------
# 写序契约：台账先于终稿落盘（台账 old_text 是唯一回滚依据）
# ---------------------------------------------------------------------------

def test_ledger_precedes_final_write(tmp_path, install_client, monkeypatch):
    """台账先于终稿落盘：终稿写盘失败时台账已在，old_text 仍可回滚。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [_item(3, T3, "前辈真厉害")])
    install_client(responses=["重翻的第三块。"])
    calls = []
    real_append = action_retranslate._append_ledger

    def _atomic_write(path, text):
        calls.append("final")
        raise OSError("终稿写盘失败")

    def _append(ledger_path, records):
        calls.append("ledger")
        return real_append(ledger_path, records)

    monkeypatch.setattr(action_retranslate, "_atomic_write_text", _atomic_write)
    monkeypatch.setattr(action_retranslate, "_append_ledger", _append)
    with pytest.raises(OSError):
        run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert calls == ["ledger", "final"]              # 台账先于终稿落盘
    assert _read_ledger(tmp_path)[0]["old_text"] == "前辈真厉害"
    assert _read_final(tmp_path)[2]["text"] == "前辈真厉害"   # 终稿未被改动


def test_guide_refresh_failure_keeps_ledger_for_rollback(
        tmp_path, install_client, monkeypatch):
    """导读刷新抛错：台账已含 old_text 记录，终稿改动可回滚（不留
    "终稿已改而台账无记录" 的窗口）。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [_item(3, T3, "前辈真厉害")])
    install_client(responses=["重翻的第三块。"])

    def _boom(*a, **k):
        raise RuntimeError("导读写盘失败")

    monkeypatch.setattr(action_retranslate, "write_guide_json", _boom)
    with pytest.raises(RuntimeError):
        run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    records = _read_ledger(tmp_path)
    assert len(records) == 1 and records[0]["outcome"] == "applied"
    assert records[0]["old_text"] == "前辈真厉害"     # 回滚依据在台账
    assert records[0]["new_text"] == "重翻的第三块。"
    assert _read_final(tmp_path)[2]["text"] == "重翻的第三块。"


def test_invariant_assertion_failure_writes_nothing(
        tmp_path, install_client, monkeypatch):
    """恒等式断言失败仍零落盘（写序调整不放宽 D11 契约④不落盘要求）。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [_item(3, T3, "前辈真厉害")])
    install_client(responses=["重翻的第三块。"])

    def _boom(*a, **k):
        raise AssertionError("恒等式断言失败（测试注入）")

    monkeypatch.setattr(action_retranslate, "_assert_apply_invariants", _boom)
    before = (tmp_path / "ep01_final_cn.srt").read_bytes()
    with pytest.raises(AssertionError):
        run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert not (tmp_path / "ep01_重翻记录.json").exists()   # 台账未落盘
    assert (tmp_path / "ep01_final_cn.srt").read_bytes() == before


# ---------------------------------------------------------------------------
# 导读快照刷新
# ---------------------------------------------------------------------------

def test_guide_snapshot_refreshed_but_conclusions_kept(tmp_path,
                                                       install_client):
    _write_final(tmp_path, FINAL_ENTRIES)
    (tmp_path / "ep01_质量报告.txt").write_text("旧报告", encoding="utf-8")
    _write_guide(tmp_path, [_item(2, T2, "[未翻译] テスト")])
    install_client(responses=["全新的第二块。"])
    run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    guide = json.loads((tmp_path / "ep01_质量报告导读.json").read_text(
        encoding="utf-8"))
    assert guide["generated_at"] != "2026-01-01 00:00:00"
    assert guide["retranslated_at"] == guide["generated_at"]
    assert guide["conclusions"] == ["结论甲"]         # 结论区保真
    assert guide["sections"] == ["章节乙"]
    assert guide["extras"] == {"对齐率": "90.0%"}
    assert guide["items"][0]["current_text"] == "全新的第二块。"
    assert len(guide["companions"]) == 6             # 六件存在性重算
    assert guide["companions"]["ep01_质量报告.txt"] is True
    assert guide["companions"]["ep01_风险清单.md"] is False


# ---------------------------------------------------------------------------
# 标陈旧打印
# ---------------------------------------------------------------------------

def test_stale_print_contains_three_names(tmp_path, install_client, capsys):
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [_item(2, T2, "[未翻译] テスト")])
    install_client(responses=["重翻后的第二块。"])
    run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    out = capsys.readouterr().out
    for name in ("ep01_质量报告.txt", "ep01_分歧复核.csv",
                 "ep01_术语冲突观察.csv"):
        assert name in out


# ---------------------------------------------------------------------------
# 源文恢复：--action-source timing 对齐 / 退化摘录
# ---------------------------------------------------------------------------

def test_source_recovery_full_hit_and_partial_fallback(tmp_path,
                                                       install_client):
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト"),
        _item(3, T3, "前辈真厉害"),
    ])
    (tmp_path / "ep01.ja.srt").write_text(
        build_srt([{"index": 1, "timing": T2, "text": "お疲れ様です。"}]),
        encoding="utf-8")
    fake = install_client(responses=["辛苦了呀。", "前辈真棒呀。"])
    rc = run_action_retranslate(_cfg(), _args(
        tmp_path, apply=True, action_source=str(tmp_path / "ep01.ja.srt")))
    assert rc == 0
    records = _read_ledger(tmp_path)
    assert records[0]["source_partial"] is False
    assert "お疲れ様です。" in fake.calls[0][1]       # 完整源文进提示词
    assert records[1]["source_partial"] is True      # 未命中 → 摘录退化
    assert "せんぱい" in fake.calls[1][1]             # 摘录进提示词


def test_no_action_source_hint_without_path(tmp_path, capsys):
    """未提供 --action-source：提示含"未提供 --action-source"与退化条数，
    不含"不存在"、不打任何路径。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト"),
        _item(3, T3, "前辈真厉害"),
    ])
    rc = run_action_retranslate(_cfg(), _args(tmp_path))   # 默认 action_source=""
    assert rc == 0
    out = capsys.readouterr().out
    assert "未提供 --action-source" in out
    assert "2 条退化为导读摘录" in out
    assert "不存在" not in out
    assert "仅导读摘录" in out                       # dry-run 计划行形态不变


def test_nonexistent_action_source_prints_given_path(tmp_path, capsys):
    """提供了 --action-source 但文件不存在：保留"不存在"提示并回显传入路径。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [_item(2, T2, "[未翻译] テスト")])
    rc = run_action_retranslate(_cfg(), _args(
        tmp_path, action_source=str(tmp_path / "missing.ja.srt")))
    assert rc == 0
    out = capsys.readouterr().out
    assert "指定的原始日文 SRT 不存在" in out
    assert "missing.ja.srt" in out
    assert "1 条退化为导读摘录" in out


# ---------------------------------------------------------------------------
# --action-sample：只取前 N 条
# ---------------------------------------------------------------------------

def test_action_sample_limits_selection(tmp_path, capsys):
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト"),
        _item(3, T3, "前辈真厉害"),
        _item(4, T4, "四"),
    ])
    rc = run_action_retranslate(_cfg(), _args(tmp_path, action_sample=2))
    assert rc == 0
    out = capsys.readouterr().out
    assert "#2" in out and "#3" in out
    assert "#4" not in out
    assert not (tmp_path / "ep01_重翻记录.json").exists()   # dry-run 不写台账


# ---------------------------------------------------------------------------
# 负向钉：行动层参数不进 manifest 指纹
# ---------------------------------------------------------------------------

def test_action_params_not_in_config_fingerprint():
    from subtransjav.refine.manifest import _CONFIG_FIELDS, compute_config_hash
    assert "action_retranslate" not in _CONFIG_FIELDS
    # 含/不含行动层参数的 cfg 哈希必须相等（参数走 CLI 直连，不进指纹；
    # 手法同 test_manifest_model 的哈希敏感度钉）
    base = RefineConfig(inputs=["a.srt"])
    with_action = RefineConfig(inputs=["a.srt"])
    with_action.action_retranslate = "guide.json"    # 模拟误挂字段
    assert compute_config_hash(with_action) == compute_config_hash(base)
    assert compute_config_hash(base) == compute_config_hash(RefineConfig(
        inputs=["a.srt"]))


# ---------------------------------------------------------------------------
# C1（v1.4 批次 1b）：重翻提示词类别条件化（_CATEGORY_HINTS）
# ---------------------------------------------------------------------------

def test_category_hint_line_for_known_categories(tmp_path, install_client):
    """已登记类别：user 提示词在"告警说明"行后插入固定格式
    "处理要点：{hint}"行。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(3, T3, "前辈真厉害", category="single_line_too_long"),
        _item(4, T4, "四", category="dewei"),
    ])
    fake = install_client(responses=["精简后的短句。", "指代已复核。"])
    assert run_action_retranslate(_cfg(), _args(tmp_path, apply=True)) == 0
    assert len(fake.calls) == 2
    u1, u2 = fake.calls[0][1], fake.calls[1][1]
    assert "处理要点：在不丢失原意的前提下精简译文" in u1
    assert "处理要点：上下文复核「で」：先判断其功能" in u2
    assert "不确定则保留原译" in u2
    # 固定格式钉：处理要点行紧跟告警说明行之后
    for u in (u1, u2):
        ls = u.splitlines()
        i = next(k for k, x in enumerate(ls) if x.startswith("告警说明："))
        assert ls[i + 1].startswith("处理要点：")


def test_unknown_category_prompt_has_no_hint_line(tmp_path, install_client):
    """未登记类别：无处理要点行，其余五行与旧版逐行一致。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [_item(3, T3, "前辈真厉害")])  # 默认 mistranslation
    fake = install_client(responses=["重翻后的中文。"])
    assert run_action_retranslate(_cfg(), _args(tmp_path, apply=True)) == 0
    u = fake.calls[0][1]
    assert "处理要点" not in u
    assert u.splitlines() == [
        "日文原文：せんぱい",
        "现有中文译文：前辈真厉害",
        "告警类别：mistranslation",
        "告警说明：疑似误译",
        "请只输出重翻后的中文正文一行。",
    ]


# ---------------------------------------------------------------------------
# 2.6.0 批1（D2026-1002-02-批1 C2）：台账原子写+损坏恢复
# ---------------------------------------------------------------------------

def test_ledger_append_atomic_and_corrupt_recovery(tmp_path, install_client):
    """C2：台账写入走 _atomic_write_text（tmp+replace）——杀树落在写中途
    不再留半截 JSON；既有损坏件不崩溃、重新起账后仍是合法 JSON 数组。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [_item(3, T3, "前辈真厉害")])
    ledger = tmp_path / "ep01_重翻记录.json"
    ledger.write_text('{"broken": true', encoding="utf-8")   # 模拟半截写
    install_client(responses=["修复后的译文。"])
    assert run_action_retranslate(
        _cfg(), _args(tmp_path, apply=True, entries="3")) == 0
    records = _read_ledger(tmp_path)          # 重新起账后可解析（原子写完整）
    assert len(records) == 1 and records[0]["outcome"] == "applied"
    assert records[0]["old_text"] == "前辈真厉害"
    assert not list(tmp_path.glob("*.tmp"))   # 原子写不残留临时件



# ---------------------------------------------------------------------------
# P2（D2026-1008-02）：动作客户端槽 A 同构（修复与分析模型完全统一）
# ---------------------------------------------------------------------------

def test_action_client_slot_a_isomorphism(monkeypatch):
    """_make_action_client 与 quality_advisor._make_ai_client 同构：
    槽 A 客户端工厂 + 模型覆盖（仅换 stages[0]，不改入参 cfg 本体）；
    _resolve_action_model 台账兜底链=override→槽 A 模型→服务商默认
    （与 _resolve_ai_model 同构）。CLI --action-model 缺省路径=空覆盖
    → 槽 A 链（GUI spawn 侧恒传解析 model，缺省链为 CLI 直跑兜底）。"""
    from subtransjav.refine import pipeline_v2
    from subtransjav.refine.config import StageConfig

    cfg = RefineConfig(stages=[
        StageConfig(0, True, "deepseek", "a-model"),
        StageConfig(1, False, "deepseek", ""),
        StageConfig(2, True, "lmstudio", "b-model"),
        StageConfig(3, False, "lmstudio", ""),
    ])
    seen: list = []

    def _fake_make_client(c, tag):
        seen.append((c, tag))
        return object()

    monkeypatch.setattr(pipeline_v2, "_make_client", _fake_make_client)
    action_retranslate._make_action_client(cfg, "")
    c, tag = seen[-1]
    assert (tag, c.stages[0].provider, c.stages[0].model) == \
        ("A", "deepseek", "a-model")            # 槽 A（非旧槽 B）
    # 模型覆盖：仅换槽0 模型，入参 cfg 本体不被改写
    action_retranslate._make_action_client(cfg, "override-model")
    c2, tag2 = seen[-1]
    assert tag2 == "A" and c2.stages[0].model == "override-model"
    assert c2 is not cfg and cfg.stages[0].model == "a-model"
    # 台账 model_used 兜底链与 quality_advisor._resolve_ai_model 同构
    assert action_retranslate._resolve_action_model(cfg, "") == "a-model"
    assert action_retranslate._resolve_action_model(cfg, "x") == "x"
    cfg_default = RefineConfig(stages=[
        StageConfig(0, True, "zen", ""),
        StageConfig(1, False, "deepseek", ""),
        StageConfig(2, True, "lmstudio", "b-model"),
        StageConfig(3, False, "lmstudio", ""),
    ])
    assert action_retranslate._resolve_action_model(cfg_default, "") == \
        "x-preview-f-free"                      # 服务商默认兜底


# ---------------------------------------------------------------------------
# 批6（D2026-1008-02）：等值终态 nochange——状态落盘 + rc 纪律
# ---------------------------------------------------------------------------

def _read_guide(tmp_path):
    return json.loads(
        (tmp_path / "ep01_质量报告导读.json").read_text(encoding="utf-8"))


def test_equal_translation_marks_nochange_rc0(tmp_path, install_client):
    """等值→outcome=nochange（非 failed）、rc=0、台账字段齐全、终稿不动，
    导读 status 分别落盘 retranslated/nochange（C1/C3）。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト"),
        _item(3, T3, "前辈真厉害"),
    ])
    install_client(responses=["改正后的译文。", "前辈真厉害"])
    rc = run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert rc == 0
    assert _read_final(tmp_path)[2]["text"] == "前辈真厉害"   # 终稿不改
    records = _read_ledger(tmp_path)
    assert records[0]["outcome"] == "applied"
    assert records[1]["outcome"] == "nochange"
    assert records[1]["new_text"] == "前辈真厉害"
    assert "已与现译一致" in records[1]["reason"]
    assert set(records[1]) == LEDGER_FIELDS
    statuses = {it["index"]: it["status"] for it in
                _read_guide(tmp_path)["items"]}
    assert statuses == {2: "retranslated", 3: "nochange"}


def test_all_nochange_still_refreshes_guide(tmp_path, install_client):
    """全 nochange（零终稿变更）：导读仍刷新且 status 全落盘 nochange
    （critic C1：刷新触发与终稿写入解耦）。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(3, T3, "前辈真厉害"),
        _item(4, T4, "四"),
    ])
    install_client(responses=["前辈真厉害", "四"])
    rc = run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert rc == 0
    assert _read_final(tmp_path) == parse_srt(build_srt(FINAL_ENTRIES))
    records = _read_ledger(tmp_path)
    assert all(r["outcome"] == "nochange" for r in records)
    guide = _read_guide(tmp_path)
    assert guide.get("retranslated_at")              # 顶层时间戳已刷
    statuses = {it["index"]: it["status"] for it in guide["items"]}
    assert statuses == {3: "nochange", 4: "nochange"}


def test_mixed_fail_and_nochange_rc3(tmp_path, install_client):
    """1 真失败 + N nochange：rc=3（部分降级），失败条目 status 不落终态。"""
    _write_final(tmp_path, FINAL_ENTRIES)
    _write_guide(tmp_path, [
        _item(2, T2, "[未翻译] テスト"),
        _item(3, T3, "前辈真厉害"),
    ])
    install_client(responses=[RuntimeError("boom"), "前辈真厉害"])
    rc = run_action_retranslate(_cfg(), _args(tmp_path, apply=True))
    assert rc == 3
    records = _read_ledger(tmp_path)
    assert records[0]["outcome"] == "failed"
    assert "LLM 调用失败" in records[0]["reason"]
    assert records[1]["outcome"] == "nochange"
    statuses = {it["index"]: it["status"] for it in
                _read_guide(tmp_path)["items"]}
    assert statuses == {2: "open", 3: "nochange"}
