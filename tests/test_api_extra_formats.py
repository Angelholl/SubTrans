"""多格式输出 GUI 面＋全链写点 api 接线钉（D2026-1023-02 批2）。

- ``_build_refine_args``：extra_output_formats 旗标透传（白名单过滤），
  未勾/缺省零旗标（默认零变化钉）；
- 全链写点一致性：终稿写回（回滚/补行）后已存在附加件与终稿 SRT 逐条
  一致（只再生不新增）；无预置件 → 写回后仍无附加件。

浅层测试：不启动窗口，TranslateAPI 用 ``object.__new__`` 构造。
"""
import json
from pathlib import Path

import pytest

pytestmark = [pytest.mark.gui]

pytest.importorskip("webview", reason="pywebview 为可选 gui extra，未安装时跳过 GUI API 测试", exc_type=ImportError)

from subtransjav.refine.filters import build_srt, parse_srt  # noqa: E402
from subtransjav.refine.v2_outputs import final_stem  # noqa: E402
from subtransjav.webview_gui.api import (  # noqa: E402  须在 importorskip 之后
    TranslateAPI,
    _build_refine_args,
)

_PRODUCT_STEM = "示例"          # 导读 stem（剥 _质量报告导读.json 后缀）
_GUIDE_SUFFIX = "_质量报告导读.json"
_TIMING_1 = "00:00:01,000 --> 00:00:03,000"
_TIMING_2 = "00:00:04,000 --> 00:00:06,000"
_TIMING_NEW = "00:00:07,000 --> 00:00:09,000"


# ---------------------------------------------------------------------------
# 1) _build_refine_args 旗标透传
# ---------------------------------------------------------------------------

def test_build_refine_args_extra_formats_passthrough():
    args = _build_refine_args({
        "inputs": ["a.srt"],
        "extra_output_formats": ["ass", "vtt"],
    })
    assert args.count("--extra-output-format") == 2
    assert args[args.index("--extra-output-format") + 1] == "ass"
    i2 = args.index("--extra-output-format",
                    args.index("--extra-output-format") + 1)
    assert args[i2 + 1] == "vtt"


def test_build_refine_args_extra_formats_default_zero_change():
    """未勾/缺省/白名单外 → 零旗标（默认零变化钉）。"""
    for options in ({"inputs": ["a.srt"]},
                    {"inputs": ["a.srt"], "extra_output_formats": []},
                    {"inputs": ["a.srt"], "extra_output_formats": None},
                    {"inputs": ["a.srt"], "extra_output_formats": ["mp4"]}):
        args = _build_refine_args(options)
        assert "--extra-output-format" not in args


# ---------------------------------------------------------------------------
# 2) 全链回滚写点一致性（fullchain_rollback）
# ---------------------------------------------------------------------------

def _applied_rec(timing, old, new):
    return {"index": 1, "timing": timing, "category": "cps_too_fast",
            "old_text": old, "new_text": new, "model_used": "m",
            "outcome": "applied", "reason": "", "ts": "2026-10-10 00:00:00",
            "source_partial": False}


def _make_rollback_env(tmp_path: Path, ledger_recs):
    """终稿 + 台账 + 导读最小夹具（镜像 test_gui_api 回滚夹具契约）。"""
    final_stem_name = final_stem(_PRODUCT_STEM)
    entries = [
        {"index": 1, "timing": _TIMING_1, "text": "甲（已改）"},
        {"index": 2, "timing": _TIMING_2, "text": "乙"},
    ]
    (tmp_path / f"{final_stem_name}.srt").write_text(
        build_srt(entries), encoding="utf-8")
    (tmp_path / f"{_PRODUCT_STEM}_重翻记录.json").write_text(
        json.dumps(ledger_recs, ensure_ascii=False), encoding="utf-8")
    guide = {"version": 2, "stem": _PRODUCT_STEM, "items": [],
             "source": "源.srt"}
    guide_path = tmp_path / f"{_PRODUCT_STEM}{_GUIDE_SUFFIX}"
    guide_path.write_text(json.dumps(guide, ensure_ascii=False),
                          encoding="utf-8")
    return guide_path


@pytest.fixture()
def api_obj():
    return object.__new__(TranslateAPI)


def test_rollback_syncs_existing_ass(api_obj, tmp_path):
    """预置 {stem}_final_cn.ass → 回滚写回后 .ass 与终稿 SRT 逐条一致。"""
    guide = _make_rollback_env(tmp_path, [
        _applied_rec(_TIMING_1, "甲（原）", "甲（已改）")])
    ass_path = tmp_path / f"{final_stem(_PRODUCT_STEM)}.ass"
    ass_path.write_text("stale", encoding="utf-8")
    r = api_obj.fullchain_rollback(str(guide))
    assert r["success"] is True and r["restored"] == 1
    srt_entries = parse_srt(
        (tmp_path / f"{final_stem(_PRODUCT_STEM)}.srt").read_text(
            encoding="utf-8"))
    assert [e["text"] for e in srt_entries] == ["甲（原）", "乙"]
    # 附加件与终稿逐条一致（Dialogue 行数与文本覆盖复核）
    ass_text = ass_path.read_text(encoding="utf-8")
    for e in srt_entries:
        assert e["text"] in ass_text
    assert "stale" not in ass_text


def test_rollback_no_preset_no_new_ass(api_obj, tmp_path):
    """无预置附加件 → 回滚写回后仍无 .ass/.vtt（只再生不新增）。"""
    guide = _make_rollback_env(tmp_path, [
        _applied_rec(_TIMING_1, "甲（原）", "甲（已改）")])
    r = api_obj.fullchain_rollback(str(guide))
    assert r["success"] is True and r["restored"] == 1
    assert not (tmp_path / f"{final_stem(_PRODUCT_STEM)}.ass").exists()
    assert not (tmp_path / f"{final_stem(_PRODUCT_STEM)}.vtt").exists()


# ---------------------------------------------------------------------------
# 3) 全链补行写点一致性（_run_fullchain_missed_stage，重依赖全桩）
# ---------------------------------------------------------------------------

def _make_missed_env(tmp_path: Path, with_ass: bool):
    final_stem_name = final_stem(_PRODUCT_STEM)
    entries = [
        {"index": 1, "timing": _TIMING_1, "text": "甲"},
        {"index": 2, "timing": _TIMING_2, "text": "乙"},
    ]
    (tmp_path / f"{final_stem_name}.srt").write_text(
        build_srt(entries), encoding="utf-8")
    if with_ass:
        (tmp_path / f"{final_stem_name}.ass").write_text(
            "stale", encoding="utf-8")
    media = tmp_path / "fake_audio.wav"
    media.write_bytes(b"")
    guide = {"items": [
        {"timing": _TIMING_NEW,
         "category": "suspected_missed_speech", "text": ""}],
        "media_path": str(media), "source": "源.srt",
        "language": "ja", "version": 2, "stem": _PRODUCT_STEM}
    guide_path = tmp_path / f"{_PRODUCT_STEM}{_GUIDE_SUFFIX}"
    guide_path.write_text(json.dumps(guide, ensure_ascii=False),
                          encoding="utf-8")
    return guide_path


def _run_missed_stage(api_obj, tmp_path, guide_path, monkeypatch):
    import subtransjav.refine.asr_env as asr_env
    import subtransjav.refine.audio_detect as audio_detect
    import subtransjav.refine.missed_insert as missed_insert

    monkeypatch.setattr(audio_detect, "detect_speech_windows",
                        lambda media, timings: {})
    monkeypatch.setattr(
        asr_env, "batch_transcribe_clips",
        lambda media, timings: [{"timing": t, "ok": True, "text": "插入",
                                 "segments": []} for t in timings])
    monkeypatch.setattr(missed_insert, "classify_transcript",
                        lambda *a, **k: {"grade": "high"})
    notices: list[str] = []
    monkeypatch.setattr(type(api_obj), "_fullchain_c22_enabled",
                        lambda self: True)
    monkeypatch.setattr(type(api_obj), "_fullchain_notice",
                        lambda self, run, text: notices.append(text))
    monkeypatch.setattr(type(api_obj), "_fullchain_write_last_run",
                        lambda self, run: None)
    monkeypatch.setattr(type(api_obj), "_fullchain_now",
                        lambda self: "2026-10-23 00:00:00")
    run = {"missed_skipped": 0}
    api_obj._run_fullchain_missed_stage(
        [{"guide_path": str(guide_path), "p": str(guide_path),
          "stem": _PRODUCT_STEM}], run)
    return run, notices


def test_missed_stage_syncs_existing_ass(api_obj, tmp_path, monkeypatch):
    """预置 .ass → 补行写回后 .ass 与终稿（含新插行）逐条一致。"""
    guide_path = _make_missed_env(tmp_path, with_ass=True)
    run, _ = _run_missed_stage(api_obj, tmp_path, guide_path, monkeypatch)
    assert run.get("missed_skipped", 0) == 0
    final_name = final_stem(_PRODUCT_STEM)
    srt_entries = parse_srt(
        (tmp_path / f"{final_name}.srt").read_text(encoding="utf-8"))
    assert len(srt_entries) == 3          # 两原行 + 一新插行
    assert srt_entries[-1]["text"] == "插入"
    ass_text = (tmp_path / f"{final_name}.ass").read_text(encoding="utf-8")
    for e in srt_entries:
        assert e["text"] in ass_text
    assert "stale" not in ass_text        # 旧内容已被再生覆盖


def test_missed_stage_no_preset_no_new_ass(api_obj, tmp_path, monkeypatch):
    """无预置附加件 → 补行写回后仍无 .ass/.vtt。"""
    guide_path = _make_missed_env(tmp_path, with_ass=False)
    run, _ = _run_missed_stage(api_obj, tmp_path, guide_path, monkeypatch)
    assert run.get("missed_skipped", 0) == 0
    final_name = final_stem(_PRODUCT_STEM)
    assert (tmp_path / f"{final_name}.srt").is_file()
    assert not (tmp_path / f"{final_name}.ass").exists()
    assert not (tmp_path / f"{final_name}.vtt").exists()
