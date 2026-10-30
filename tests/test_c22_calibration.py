"""tests for tools/c22_calibration.py（C22 离线回放 harness，逐间隙 labels 数组，C22-卡1）。

五钉（D2026-1009-02 §三逐间隙口径；d1012-C22-卡1）：
  1. 逐间隙 labels：sample 带 labels=[True, False] → 两行 label 分别 True/False；
  2. 旧行为回归：无 labels 键（或 null）→ 全行用 sample 的 label；
  3. 长度不匹配：_replay_sample raise 中文 ValueError；main 层退出码 1；
  4. 门控语义不回归：全 labels=true 走 main（不打 --enable）→ 退出码 0 且门控文件不产生；
  5. timings 显式清单：取代导读派生、labels 逐条对齐；timings/labels 不等长 → 退出码 1。

全程离线：monkeypatch 模块级 detect_speech_windows / batch_transcribe_clips
（不切片不装载 whisper），cleanup_clips 打桩避免碰真实数据根临时切片目录。
"""

from __future__ import annotations

import importlib.util
import json
import re
from pathlib import Path

import pytest

_TOOL_PATH = Path(__file__).resolve().parents[1] / "tools" / "c22_calibration.py"
_spec = importlib.util.spec_from_file_location("c22_calibration_under_test",
                                               _TOOL_PATH)
assert _spec is not None and _spec.loader is not None
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)

T1 = "00:00:01,000 --> 00:00:03,000"
T2 = "00:00:04,000 --> 00:00:06,000"
T3 = "00:00:07,000 --> 00:00:09,000"

# 合成转写：good 段 + 无拟声文本 → classify 三维全过 = high（与 --selftest 同谱）
_GOOD_SEG = {"start": 0.0, "end": 2.0, "text": "本当にすみません",
             "no_speech_prob": 0.02, "avg_logprob": -0.25,
             "compression_ratio": 1.2}


def _fake_batch(media: str, timings: list[str], **kwargs) -> list[dict]:
    """batch_transcribe_clips 打桩：逐 timing 返回同一条合成转写。"""
    return [{"segments": [_GOOD_SEG], "text": "本当にすみません",
             "error": ""} for _ in timings]


@pytest.fixture
def c22(monkeypatch):
    """回放打桩：能量窗口空、转写合成、切片清理 no-op（只钉 label 分发）。"""
    monkeypatch.setattr(mod, "detect_speech_windows",
                        lambda media, timings: {})
    monkeypatch.setattr(mod, "batch_transcribe_clips", _fake_batch)
    monkeypatch.setattr(mod, "cleanup_clips", lambda *a, **k: 0)
    return mod


def _write_guide(tmp_path: Path, timings: list[str],
                 name: str = "guide.json") -> Path:
    """导读 json：目标 timings 各夹一条非目标类别条目（派生须按类别过滤）。"""
    items: list[dict] = []
    for i, t in enumerate(timings):
        items.append({"category": "suspected_missed_speech", "timing": t})
        if i == 0:
            items.append({"category": "other",
                          "timing": "00:00:50,000 --> 00:00:51,000"})
    p = tmp_path / name
    p.write_text(json.dumps({"items": items}, ensure_ascii=False),
                 encoding="utf-8")
    return p


def _write_manifest(tmp_path: Path, samples: list[dict],
                    name: str = "manifest.json") -> Path:
    p = tmp_path / name
    p.write_text(json.dumps(samples, ensure_ascii=False), encoding="utf-8")
    return p


def _has_chinese(text: str) -> bool:
    return bool(re.search(r"[一-鿿]", text))


# ------------------------------------------------------------------ 钉1 逐间隙

def test_pin1_labels_per_gap(c22, tmp_path):
    guide = _write_guide(tmp_path, [T1, T2])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": True, "labels": [True, False]})
    assert [r["timing"] for r in rows] == [T1, T2]
    assert [r["label"] for r in rows] == [True, False]


# ------------------------------------------------------ 钉2 旧行为回归（零外溢）

def test_pin2_legacy_single_label_without_key(c22, tmp_path):
    guide = _write_guide(tmp_path, [T1, T2])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": False})
    assert [r["label"] for r in rows] == [False, False]


def test_pin2_legacy_label_null_keeps_old_behavior(c22, tmp_path):
    """labels=null 与缺省同义：仍走单 label 旧行为。"""
    guide = _write_guide(tmp_path, [T1, T2])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": True, "labels": None})
    assert [r["label"] for r in rows] == [True, True]


# ------------------------------------------------------- 钉3 长度不匹配 fail-closed

def test_pin3_mismatch_raises_chinese_value_error(c22, tmp_path):
    guide = _write_guide(tmp_path, [T1, T2])
    with pytest.raises(ValueError) as exc:
        c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                            "label": True, "labels": [True]})
    assert _has_chinese(str(exc.value))


def test_pin3_mismatch_main_exit_1(c22, tmp_path, capsys):
    guide = _write_guide(tmp_path, [T1, T2])
    manifest = _write_manifest(tmp_path, [
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "labels": [True]}])
    rc = c22.main(["--manifest", str(manifest),
                   "--out", str(tmp_path / "report.md")])
    assert rc == 1
    out = capsys.readouterr().out
    assert "❌" in out and _has_chinese(out)


# ------------------------------------------------- 钉4 门控语义不回归（防外溢）

def test_pin4_gate_not_written_without_enable(c22, tmp_path, monkeypatch):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    guide = _write_guide(tmp_path, [T1, T2])
    manifest = _write_manifest(tmp_path, [
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "labels": [True, True]}])
    out = tmp_path / "report.md"
    rc = c22.main(["--manifest", str(manifest), "--out", str(out)])
    assert rc == 0
    assert out.is_file()
    assert not (tmp_path / "config" / "fullchain_c22.json").exists()


# ------------------------------------------------------ 钉5 timings 显式清单

def test_pin5_explicit_timings_align_labels(c22, tmp_path):
    """导读实际 3 条 > 显式 2 条：按显式 timing 出行且 label 逐条对齐。"""
    guide = _write_guide(tmp_path, [T1, T2, T3])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": False, "timings": [T3, T1],
                               "labels": [True, False]})
    assert [r["timing"] for r in rows] == [T3, T1]
    assert [r["label"] for r in rows] == [True, False]


def test_pin5_timings_labels_mismatch_main_exit_1(c22, tmp_path, capsys):
    guide = _write_guide(tmp_path, [T1, T2])
    manifest = _write_manifest(tmp_path, [
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "timings": [T1, T2], "labels": [True]}])
    rc = c22.main(["--manifest", str(manifest),
                   "--out", str(tmp_path / "report.md")])
    assert rc == 1
    assert "❌" in capsys.readouterr().out



# ------------------------------------------------------------------ 前置件②
# （d1029-3.2.1 前置件：回放臂 ct2 唯一引擎路径钉，D2026-1029-01 批6 直连
# recipe 固化——runner 形态出段→grade 非空；legacy whisper 死代码不回潮）

def test_replay_rows_grade_high_from_runner_payload(c22, tmp_path):
    """mock runner 出段（含三维置信键）→ _replay_sample 出 high 行、
    asr_error 空（grade 非空路径，批6 直连 recipe 等价断言）。"""
    guide = _write_guide(tmp_path, [T1])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": True, "timings": [T1]})
    assert len(rows) == 1
    assert rows[0]["grade"] == "high"
    assert rows[0]["asr_error"] == ""


def test_replay_failure_row_grade_empty(c22, monkeypatch, tmp_path):
    """转写失败（error 文本）→ grade="empty" 且错误如实入
    asr_error（不静默，环境层阻断可见）。"""
    def _fail_batch(media, timings, **kwargs):
        return [{"segments": [], "text": "", "error": "转写引擎未安装"}]
    monkeypatch.setattr(c22, "batch_transcribe_clips", _fail_batch)
    guide = _write_guide(tmp_path, [T1])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": True, "timings": [T1]})
    assert rows[0]["grade"] == "empty"
    assert "转写引擎未安装" in rows[0]["asr_error"]


# ------------------------------------------------- d1030 卡1（D2026-1029-11 裁决①）
# 门死锁修复＝双条件＋不可判档（fail-closed）；asr_error 分诊报告面单列；
# 参照读数（不含 ≤1s 能量门）无门语义。

def test_gate_verdict_dual_condition_and_unjudgeable():
    """判定序钉：n_high < 30 → unjudgeable（不评估精确率）；达 n_high 后
    须精确率下界与 coverage 地板双达标才 pass（PROVISIONAL 门值）。"""
    assert mod._gate_verdict({"n_high": 29, "precision_lb": 0.99,
                              "coverage": 0.90}) == "unjudgeable"
    assert mod._gate_verdict({"n_high": 30, "precision_lb": 0.99,
                              "coverage": 0.90}) == "pass"
    assert mod._gate_verdict({"n_high": 40, "precision_lb": 0.96,
                              "coverage": 0.49}) == "fail"
    assert mod._gate_verdict({"n_high": 40, "precision_lb": 0.96,
                              "coverage": 0.50}) == "pass"
    assert mod._gate_verdict({"n_high": 40, "precision_lb": 0.94,
                              "coverage": 0.90}) == "fail"


def test_gate_unjudgeable_refuses_enable_exit_2(c22, tmp_path, monkeypatch,
                                                capsys):
    """n_high < 30 → --enable 拒写门控退出码 2（fail-closed 不破）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    guide = _write_guide(tmp_path, [T1])
    manifest = _write_manifest(tmp_path, [
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "timings": [T1], "labels": [True]}])
    rc = c22.main(["--manifest", str(manifest),
                   "--out", str(tmp_path / "r.md"), "--enable"])
    assert rc == 2
    assert not (tmp_path / "config" / "fullchain_c22.json").exists()
    assert "不可判" in capsys.readouterr().out


def test_aggregate_asr_error_triage_buckets(c22, monkeypatch, tmp_path):
    """分诊计数：n_asr_error 与 empty 两桶（带 error／真空输出）；
    主口径分母不动（n_total 含全部行，与 D2026-1029-06 报告可比）。"""
    def _mixed_batch(media, timings, **kwargs):
        return [{"segments": [], "text": "", "error": "切片失败"}
                if t == T1 else
                ({"segments": [], "text": "", "error": ""} if t == T2 else
                 {"segments": [_GOOD_SEG], "text": "本当にすみません",
                  "error": ""})
                for t in timings]
    monkeypatch.setattr(c22, "batch_transcribe_clips", _mixed_batch)
    guide = _write_guide(tmp_path, [T1, T2, T3])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": True})
    agg = c22._aggregate(rows)
    assert agg["n_asr_error"] == 1
    assert agg["n_empty_with_error"] == 1
    assert agg["n_empty_silent"] == 1
    assert agg["n_total"] == 3
    assert agg["n_high"] == 1


def test_report_triage_column_and_verdict(c22, tmp_path, monkeypatch):
    """报告面：asr_error 独立列（reasons 不再拼 error 文本）＋verdict
    与分诊计数入汇总。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(c22, "batch_transcribe_clips",
                        lambda media, timings, **k: [
                            {"segments": [], "text": "",
                             "error": "转写引擎未安装"} for _ in timings])
    guide = _write_guide(tmp_path, [T1])
    manifest = _write_manifest(tmp_path, [
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "timings": [T1], "labels": [True]}])
    out = tmp_path / "r.md"
    c22.main(["--manifest", str(manifest), "--out", str(out)])
    text = out.read_text(encoding="utf-8")
    assert "| asr_error |" in text
    assert "asr_error=" not in text
    assert "转写引擎未安装" in text
    assert "unjudgeable" in text
    assert "真空输出" in text and "带 error" in text


def test_reference_readout_flips_energy_gate_rows(c22, tmp_path, monkeypatch):
    """双读数：同一批转写产物二次 classify（speech_min_s=None，不重复
    转写）——主口径能量门 low 行在参照口径按其余信号重判。"""
    monkeypatch.setattr(c22, "detect_speech_windows",
                        lambda media, timings: {T1: [(1.0, 1.5)]})
    guide = _write_guide(tmp_path, [T1])
    ctx: list[dict] = []
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": True, "timings": [T1],
                               "labels": [True]}, ctx)
    assert rows[0]["grade"] == "low"
    assert rows[0]["reasons"][0] == "speech_le_1s"
    ref_rows = c22._reclassify_no_energy_gate(ctx)
    assert ref_rows[0]["grade"] == "high"


def test_reference_section_no_gate_semantics(c22, tmp_path, monkeypatch):
    """参照节物理隔离：只报计数与点精确率，无门判定语义字段。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    guide = _write_guide(tmp_path, [T1])
    manifest = _write_manifest(tmp_path, [
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "timings": [T1], "labels": [True]}])
    out = tmp_path / "r.md"
    c22.main(["--manifest", str(manifest), "--out", str(out)])
    text = out.read_text(encoding="utf-8")
    head, sep, ref = text.partition("## 参照读数")
    assert sep, "参照节缺失"
    assert "Wilson" not in ref
    assert "verdict" not in ref
    assert "达标" not in ref
    assert "覆盖率" not in ref


def test_replay_arm_no_legacy_whisper_symbols():
    """回放臂源文零 legacy whisper 残留（写死 whisper 子进程不回潮；
    引擎唯一出口=batch_transcribe_clips ct2 分派）。"""
    src = _TOOL_PATH.read_text(encoding="utf-8")
    assert "asr_runner" not in src, "回放臂不得直调 runner 子进程"
    assert re.search(r"whisper", src, re.I) is None,         "回放臂残留 legacy whisper 引用"
    assert "batch_transcribe_clips" in src, "回放臂引擎出口缺失"


# ------------------------------------------------------- d1030 卡2（裁决②/D3）
# 217 条挂接：exclude_reasons 数据载体＋排除面统计＋喘息双口径回样＋
# guide 惰性化＋_MAX_CLIPS 透传前置防呆。

def test_pin8_exclude_reasons_mismatch_raises(c22, tmp_path):
    """exclude_reasons 与 timings 不等长 → 中文 ValueError（fail-closed）。"""
    with pytest.raises(ValueError) as exc:
        c22._replay_sample({"media": "x.mkv", "label": True,
                            "timings": [T1, T2],
                            "exclude_reasons": ["杂音无法判定"]})
    assert _has_chinese(str(exc.value)) and "exclude_reasons" in str(exc.value)


def test_pin8_exclude_rows_out_of_main_denominator(c22, tmp_path):
    """排除行不进主口径统计：分母/召回基于入样行；排除面计数齐全。"""
    guide = _write_guide(tmp_path, [T1, T2, T3])
    rows = c22._replay_sample(
        {"guide": str(guide), "media": "x.mkv", "label": True,
         "labels": [True, True, True],
         "exclude_reasons": [None, "前条喘息呻吟", "杂音无法判定"]})
    agg = c22._aggregate(rows)
    assert agg["n_rows_all"] == 3
    assert agg["n_total"] == 1
    assert agg["n_excluded"] == 2
    assert agg["exclude_rate"] == pytest.approx(2 / 3)
    assert agg["n_excluded_by_reason"] == {"前条喘息呻吟": 1,
                                           "杂音无法判定": 1}
    assert agg["n_high"] == 1


def test_pin8_breath_ref_recovered_noise_excluded_both(c22, tmp_path):
    """双口径：喘息排除行参照口径回样（label=true）；杂音行两口径均排除。"""
    guide = _write_guide(tmp_path, [T1, T2])
    ctx: list[dict] = []
    c22._replay_sample(
        {"guide": str(guide), "media": "x.mkv", "label": False,
         "timings": [T1, T2], "labels": [False, False],
         "exclude_reasons": ["前后喘息呻吟", "杂音无法判定"]}, ctx)
    ref_rows = c22._reclassify_no_energy_gate(ctx)
    ref_by_t = {r["timing"]: r for r in ref_rows}
    assert ref_by_t[T1]["exclude_reason"] is None
    assert ref_by_t[T1]["label"] is True
    assert ref_by_t[T2]["exclude_reason"] == "杂音无法判定"
    ref_agg = c22._aggregate(ref_rows)
    assert ref_agg["n_total"] == 1
    assert ref_agg["n_excluded"] == 1


def test_pin8_exclusion_section_and_audit_list(c22, tmp_path, monkeypatch):
    """报告面：排除面统计节＋分原因＋排除项清单表＋样本明细 exclude 列。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    manifest = _write_manifest(tmp_path, [
        {"media": "x.mkv", "label": True,
         "timings": [T1, T2], "labels": [True, False],
         "exclude_reasons": [None, "后条喘息呻吟"]}])
    out = tmp_path / "r.md"
    rc = c22.main(["--manifest", str(manifest), "--out", str(out)])
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "## 排除面" in text
    assert "后条喘息呻吟 1" in text
    assert "## 排除项清单" in text
    assert "| exclude_reason |" in text


def test_pin8_unattributed_over_cap_warn(c22, tmp_path, monkeypatch):
    """不可归因排除率超预注册上限 → 报告 WARN 行（仅呈报不阻断）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    timings = [f"00:00:0{i},000 --> 00:00:0{i},500" for i in range(9)]
    manifest = _write_manifest(tmp_path, [
        {"media": "x.mkv", "label": True,
         "timings": timings, "labels": [True] * 9,
         "exclude_reasons": [None] * 8 + ["杂音无法判定"]}])
    out = tmp_path / "r.md"
    c22.main(["--manifest", str(manifest), "--out", str(out)])
    text = out.read_text(encoding="utf-8")
    assert "WARN 超限" in text


def test_pin8_timings_over_max_clips_fails_closed(c22, tmp_path):
    """timings 超 asr_env._MAX_CLIPS → 中文 ValueError（先于引擎防呆，
    提示分块）。"""
    timings = ["00:00:01,000 --> 00:00:02,000"] * (c22._MAX_CLIPS + 1)
    with pytest.raises(ValueError) as exc:
        c22._replay_sample({"media": "x.mkv", "label": True,
                            "timings": timings})
    assert _has_chinese(str(exc.value)) and "分块" in str(exc.value)


def test_pin8_timings_without_guide_replays(c22, tmp_path, monkeypatch):
    """guide 惰性化：无 guide 键、仅 timings 显式清单 → 回放正常
    （main 层校验放宽为二者其一）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    manifest = _write_manifest(tmp_path, [
        {"media": "x.mkv", "label": True,
         "timings": [T1], "labels": [True]}])
    out = tmp_path / "r.md"
    rc = c22.main(["--manifest", str(manifest), "--out", str(out)])
    assert rc == 0 and out.is_file()


def test_pin8_legacy_manifest_zero_exclusion(c22, tmp_path):
    """旧行为零外溢：无 exclude_reasons 键 → 零排除、分母=全体。"""
    guide = _write_guide(tmp_path, [T1, T2])
    rows = c22._replay_sample({"guide": str(guide), "media": "x.mkv",
                               "label": True,
                               "labels": [True, False]})
    agg = c22._aggregate(rows)
    assert agg["n_excluded"] == 0
    assert agg["exclude_rate"] == 0.0
    assert agg["n_total"] == agg["n_rows_all"] == 2
    assert agg["n_excluded_by_reason"] == {}


# ------------------------------------------------ d1031 卡（D2026-1030-06 ②）
# 主口径 speech-min-s CLI override：缺省零变化；显式值进主口径 classify；
# 参照口径恒 None 不被 flag 泄漏。

def _windows_subsecond(media: str, timings: list[str]) -> dict:
    """T1 能量 0.5s（≤产品缺省 1.0s）、T2 能量 2.0s（过门）。"""
    return {T1: [(1.0, 1.5)], T2: [(4.0, 6.0)]}


def _run_manifest(c22, tmp_path, monkeypatch, name: str,
                  argv_extra: list[str]) -> str:
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    monkeypatch.setattr(c22, "detect_speech_windows", _windows_subsecond)
    manifest = _write_manifest(tmp_path, [
        {"media": "x.mkv", "label": True,
         "timings": [T1, T2], "labels": [True, True]}], name=f"{name}.json")
    out = tmp_path / f"{name}.md"
    rc = c22.main(["--manifest", str(manifest), "--out", str(out),
                   *argv_extra])
    assert rc == 0
    return out.read_text(encoding="utf-8")


def _n_high(text: str) -> int:
    m = re.search(r"- 判 high：(\d+) /", text)
    assert m, "报告缺「判 high」行"
    return int(m.group(1))


def _ref_n_high(text: str) -> int:
    head, sep, ref = text.partition("## 参照读数")
    assert sep, "参照节缺失"
    m = re.search(r"- n_high：(\d+)（label=true", ref)
    assert m, "参照节缺 n_high 行"
    return int(m.group(1))


def test_pin9_default_speech_min_zero_change(c22, tmp_path, monkeypatch):
    """钉1 缺省零变化：不传 --speech-min-s → 主口径仍走产品缺省 1.0s，
    逐行读数与 verdict 同改动前一致；报告头声明「缺省(产品终裁值)」。"""
    text = _run_manifest(c22, tmp_path, monkeypatch, "d", [])
    assert "| 1 | " + T1 + " | low | True | speech_le_1s" in text
    assert "| 2 | " + T2 + " | high | True" in text
    assert _n_high(text) == 1
    assert "unjudgeable" in text
    assert "主口径 speech_min_s=缺省(产品终裁值)" in text


def test_pin9_override_zero_promotes_subsecond_high(c22, tmp_path,
                                                   monkeypatch):
    """钉2 override 生效：--speech-min-s 0 → ≤1s 行不再被能量门判 low，
    主口径判 high 数多于缺省 case。"""
    default_text = _run_manifest(c22, tmp_path, monkeypatch, "dflt", [])
    override_text = _run_manifest(c22, tmp_path, monkeypatch, "zero",
                                  ["--speech-min-s", "0"])
    assert _n_high(override_text) == _n_high(default_text) + 1
    assert "| 1 | " + T1 + " | high | True" in override_text


def test_pin9_none_equals_reference_readout(c22, tmp_path, monkeypatch):
    """钉3 主口径=None 等值性：--speech-min-s none → 主口径 n_high 与
    参照口径节（恒 None）读数一致。"""
    text = _run_manifest(c22, tmp_path, monkeypatch, "none",
                         ["--speech-min-s", "none"])
    assert _n_high(text) == _ref_n_high(text) == 2
    assert "| 1 | " + T1 + " | high | True" in text


def test_pin9_report_header_declares_speech_min(c22, tmp_path, monkeypatch):
    """钉4 报告头声明行：缺省与显式（浮点/字面 none）两形态均在。"""
    default_text = _run_manifest(c22, tmp_path, monkeypatch, "d", [])
    zero_text = _run_manifest(c22, tmp_path, monkeypatch, "z",
                              ["--speech-min-s", "0"])
    none_text = _run_manifest(c22, tmp_path, monkeypatch, "n",
                              ["--speech-min-s", "NONE"])
    assert "主口径 speech_min_s=缺省(产品终裁值)" in default_text
    assert "主口径 speech_min_s=0" in zero_text
    assert "主口径 speech_min_s=none" in none_text


def test_pin9_reference_section_ignores_flag(c22, tmp_path, monkeypatch):
    """钉5 flag 不泄漏到参照口径：两 flag 形态下参照节读数逐字一致。"""
    default_text = _run_manifest(c22, tmp_path, monkeypatch, "d", [])
    override_text = _run_manifest(c22, tmp_path, monkeypatch, "z",
                                  ["--speech-min-s", "0"])
    default_ref = default_text.partition("## 参照读数")[2]
    override_ref = override_text.partition("## 参照读数")[2]
    assert default_ref == override_ref
    assert _n_high(default_text) != _n_high(override_text)
