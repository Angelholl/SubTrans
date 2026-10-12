"""v1.5 音频链路（D2026-0929-04 P2）媒体路径测试。

覆盖：
1. resolve_media_path 配对：正常 / 大小写 / 斜杠方向 / 多条目精确命中 /
   零命中 / manifest 损坏 / output 缺失 / override 优先 / override 不存在；
2. 指纹口径：manifest 带/不带 files[] → load_asr_meta 指纹不变；
   media_path 空串 → config_hash 与字段缺席一致；覆盖值大小写归一；
   覆盖值变更 → resume 指纹不匹配（validate_manifest"配置已变化"）；
3. 报告契约：导读 json media_path/media_path_source 同现同缺；报告 txt
   头部"媒体文件"行同现同缺；
4. 黄金样例（skipif：本地 .abtest 真实 manifest 不存在则跳过；不把真实
   样例内容复制进 tracked fixtures）。
"""

import json
import os
import types
from pathlib import Path

import pytest

from subtransjav.refine.asr_meta import (
    RUN_META_NAME,
    fingerprint,
    load_asr_meta,
    resolve_media_path,
)
from subtransjav.refine.manifest import compute_config_hash, validate_manifest
from subtransjav.refine.quality_report import (
    build_quality_report,
    write_guide_json,
)

# ---------------------------------------------------------------------------
# 工具
# ---------------------------------------------------------------------------

def _cfg(**kw) -> types.SimpleNamespace:
    base = {"asr_meta": "", "asr_telemetry": "",
            "v2_asr_meta_stale_max_hours": 24, "media_path": ""}
    base.update(kw)
    return types.SimpleNamespace(**base)


def _write_meta(directory, payload, name=RUN_META_NAME):
    p = directory / name
    p.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return p


def _write_srt(directory, name="demo.srt"):
    p = directory / name
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\nこんにちは\n",
                 encoding="utf-8")
    return p


def _meta_result(present=True, file=RUN_META_NAME) -> dict:
    return {"present": present, "status": None, "mileage_pct": None,
            "stale": False, "file": file, "warnings": []}


def _manifest_payload(media="E:/vid/ep01.mp4", output=None):
    return {"whisperjav_version": "1.9.2", "mode": "BAL",
            "counts": {"done": 1},
            "files": [{"path": media, "state": "done",
                       "output": output if output is not None
                       else "D:/SubTransJAV/tmp/demo.srt"}]}


# ---------------------------------------------------------------------------
# 1. resolve_media_path 配对
# ---------------------------------------------------------------------------

def test_pairing_normal_hit(tmp_path):
    """a) 正常路径：files[].output 与输入 SRT 同路径 → manifest 命中。"""
    srt = _write_srt(tmp_path)
    media = tmp_path / "ep01.mp4"
    _write_meta(tmp_path, _manifest_payload(
        media=str(media), output=str(srt)))
    meta = _meta_result()
    m, src = resolve_media_path(str(srt), meta)
    assert src == "manifest"
    assert os.path.normcase(os.path.abspath(m)) == os.path.normcase(str(media))
    assert meta["warnings"] == []


def test_pairing_case_insensitive(tmp_path):
    """b) 大小写差异（OUTPUT 大小写不同）仍命中。"""
    srt = _write_srt(tmp_path)
    media = tmp_path / "ep01.mp4"
    _write_meta(tmp_path, _manifest_payload(
        media=str(media), output=str(srt).upper()))
    m, src = resolve_media_path(str(srt), _meta_result())
    assert src == "manifest"
    assert m == str(media)


def test_pairing_slash_direction(tmp_path):
    """c) 斜杠方向（/ vs \\）仍命中。"""
    srt = _write_srt(tmp_path)
    media = tmp_path / "ep01.mp4"
    _write_meta(tmp_path, _manifest_payload(
        media=str(media), output=str(srt).replace("\\", "/")))
    m, src = resolve_media_path(str(srt), _meta_result())
    assert src == "manifest"
    assert m == str(media)


def test_pairing_multi_files_exact_hit_not_first(tmp_path):
    """d) 多 files 条目、目标 SRT 为其中之一 → 精确命中非 files[0]。"""
    srt = _write_srt(tmp_path)
    m0 = tmp_path / "a.mp4"
    m1 = tmp_path / "b.mp4"
    _write_meta(tmp_path, {
        "files": [
            {"path": str(m0), "state": "done",
             "output": str(tmp_path / "other.srt")},
            {"path": str(m1), "state": "done", "output": str(srt)},
        ]})
    got, src = resolve_media_path(str(srt), _meta_result())
    assert src == "manifest"
    assert os.path.normcase(os.path.abspath(got)) == os.path.normcase(str(m1))


def test_pairing_zero_hits_empty_with_warning(tmp_path):
    """e) 零命中 → 空 + 警告。"""
    srt = _write_srt(tmp_path)
    _write_meta(tmp_path, _manifest_payload(
        media="E:/x/y.mp4", output="D:/elsewhere/other.srt"))
    meta = _meta_result()
    assert resolve_media_path(str(srt), meta) == ("", "")
    assert any("无命中" in w for w in meta["warnings"])


def test_pairing_manifest_broken_or_no_files(tmp_path):
    """f) manifest 无 files 键 / 损坏 JSON → 空 + 容错（不抛异常）。"""
    srt = _write_srt(tmp_path)
    _write_meta(tmp_path, {"whisperjav_version": "1.9.2"})
    meta = _meta_result()
    assert resolve_media_path(str(srt), meta) == ("", "")
    assert any("files" in w for w in meta["warnings"])
    (tmp_path / RUN_META_NAME).write_text("{broken", encoding="utf-8")
    meta2 = _meta_result()
    assert resolve_media_path(str(srt), meta2) == ("", "")
    assert any("读取失败" in w for w in meta2["warnings"])


def test_pairing_missing_output_key_skips_entry(tmp_path):
    """g) output 键缺失 → 跳过条目（零命中 → 空 + 警告）。"""
    srt = _write_srt(tmp_path)
    _write_meta(tmp_path, {"files": [{"path": "E:/x/a.mp4",
                                      "state": "done"}]})
    meta = _meta_result()
    assert resolve_media_path(str(srt), meta) == ("", "")
    assert any("无命中" in w for w in meta["warnings"])


def test_override_takes_precedence_over_manifest(tmp_path):
    """h) override 优先于 manifest。"""
    srt = _write_srt(tmp_path)
    media = tmp_path / "ep01.mp4"
    _write_meta(tmp_path, _manifest_payload(
        media=str(media), output=str(srt)))
    m, src = resolve_media_path(str(srt), _meta_result(),
                                explicit_media_path="D:/other/z.mkv")
    assert src == "override"
    assert m == "D:/other/z.mkv"


def test_override_missing_file_still_recorded_with_warning(tmp_path):
    """i) override 文件不存在 → 仍记录 + 警告（用户明示即采信）。"""
    srt = _write_srt(tmp_path)
    meta = _meta_result()
    m, src = resolve_media_path(str(srt), meta,
                                explicit_media_path=str(tmp_path / "nope.mp4"))
    assert src == "override"
    assert m == str(tmp_path / "nope.mp4")
    assert any("不存在" in w for w in meta["warnings"])


def test_no_manifest_location_returns_empty(tmp_path):
    """无 manifest 定位（file 为空）→ 空，无警告噪音（常态）。"""
    srt = _write_srt(tmp_path)
    assert resolve_media_path(str(srt), _meta_result(file=None)) == ("", "")


def test_explicit_asr_meta_in_other_directory(tmp_path):
    """显式 --asr-meta 指向与 SRT 不同目录的 manifest → 配对成功（钉死
    "用已定位 file 而非重建 SRT 同目录锚点"：SRT 目录不含
    whisperjav_run.json，file 为已定位全路径）。"""
    srt_dir = tmp_path / "srt"
    run_dir = tmp_path / "run"
    srt_dir.mkdir()
    run_dir.mkdir()
    srt = _write_srt(srt_dir)
    media = tmp_path / "ep01.mp4"
    _write_meta(run_dir, _manifest_payload(media=str(media), output=str(srt)))
    meta = _meta_result(file=str(run_dir / RUN_META_NAME))
    m, src = resolve_media_path(str(srt), meta)
    assert src == "manifest"
    assert os.path.normcase(os.path.abspath(m)) == os.path.normcase(str(media))
    assert meta["warnings"] == []


def test_manifest_path_kwarg_for_explicit_cfg(tmp_path):
    """pipeline 显式 cfg 流（--asr-meta 指向他处，file 为 basename）：
    经 manifest_path 传入已定位全路径 → 配对成功；不传时 basename 只能
    退化到 SRT 同目录 → 零命中。"""
    srt_dir = tmp_path / "srt"
    run_dir = tmp_path / "run"
    srt_dir.mkdir()
    run_dir.mkdir()
    srt = _write_srt(srt_dir)
    media = tmp_path / "ep01.mp4"
    _write_meta(run_dir, _manifest_payload(media=str(media), output=str(srt)))
    meta = _meta_result(file=RUN_META_NAME)   # load_asr_meta 报告口径 basename
    assert resolve_media_path(str(srt), meta) == ("", "")
    m, src = resolve_media_path(str(srt), meta,
                                manifest_path=str(run_dir / RUN_META_NAME))
    assert src == "manifest"
    assert m == str(media)


def test_stale_manifest_does_not_block_pairing(tmp_path):
    """媒体路径属身份元数据：stale 不阻塞配对（R6 只约束信任信号）。"""
    srt = _write_srt(tmp_path)
    media = tmp_path / "ep01.mp4"
    _write_meta(tmp_path, _manifest_payload(
        media=str(media), output=str(srt)))
    meta = _meta_result(present=False)   # load_asr_meta 超龄时 present=False
    m, src = resolve_media_path(str(srt), meta)
    assert src == "manifest"
    assert m == str(media)


def test_multiple_hits_takes_first_with_warning(tmp_path):
    """>1 命中 → 取第一个 + 警告。"""
    srt = _write_srt(tmp_path)
    _write_meta(tmp_path, {
        "files": [
            {"path": "E:/x/a.mp4", "state": "done", "output": str(srt)},
            {"path": "E:/x/b.mp4", "state": "done", "output": str(srt)},
        ]})
    meta = _meta_result()
    m, src = resolve_media_path(str(srt), meta)
    assert src == "manifest"
    assert os.path.normcase(os.path.abspath(m)) \
        == os.path.normcase(os.path.abspath("E:/x/a.mp4"))
    assert any("取第一个" in w for w in meta["warnings"])


# ---------------------------------------------------------------------------
# 2. 指纹口径
# ---------------------------------------------------------------------------

def test_fingerprint_unchanged_by_files_list(tmp_path):
    """同一 manifest 带/不带 files[] → load_asr_meta 指纹不变（守卫②）。"""
    srt = _write_srt(tmp_path)
    _write_meta(tmp_path, {"status": "ok", "mileage_pct": 42})
    fp0 = fingerprint(load_asr_meta(_cfg(), str(srt)))
    _write_meta(tmp_path, {"status": "ok", "mileage_pct": 42,
                           "files": [{"path": "E:/x/a.mp4",
                                      "output": str(srt)}]})
    assert fingerprint(load_asr_meta(_cfg(), str(srt))) == fp0
    assert fp0 is not None


def test_config_hash_empty_media_path_matches_field_absent():
    """media_path 为空串时 config_hash 与字段缺席一致（不设覆盖不扰动）。"""
    absent = types.SimpleNamespace()
    for name in ("profile", "endpoints", "batch_local", "batch_cloud",
                 "batch_size_stable", "v2_profile", "v2_concurrency",
                 "v2_ctx_local", "v2_keep_untranslated", "v2_source_filter",
                 "v2_source_filter_valve_pct", "adaptive_thresholds",
                 "premerge_enabled", "temperature_cloud", "temperature_local",
                 "premerge_max_gap_s", "premerge_max_items",
                 "premerge_max_span_ms", "premerge_max_chars",
                 "premerge_min_fragment_chars", "tm_enabled", "tm_threshold",
                 "tm_fuzzy_inject", "tm_fuzzy_threshold", "tm_learn_gate",
                 "apply_glossary_stage1", "apply_glossary_stage2",
                 "glossary_conflict_block", "glossary_learn_enabled",
                 "glossary_override_path", "context_sidecar", "auto_synopsis",
                 "synopsis_max_chars", "fallback_local", "fallback_model",
                 "cleaner_config_dir"):
        setattr(absent, name, None)
    absent.stages = []
    assert compute_config_hash(absent) == compute_config_hash(
        types.SimpleNamespace(stages=[], media_path=""))


def test_config_hash_media_override_case_and_slash_normalized():
    """覆盖值 D:\\X\\a.mp4 与 d:\\x\\A.MP4 → 同指纹。"""
    cfg1 = _cfg(media_path="D:\\X\\a.mp4")
    cfg2 = _cfg(media_path="d:\\x\\A.MP4")
    cfg3 = _cfg(media_path="d:/x/a.mp4")
    assert compute_config_hash(cfg1) == compute_config_hash(cfg2)
    assert compute_config_hash(cfg1) == compute_config_hash(cfg3)


def test_config_hash_different_media_override_differs():
    """不同覆盖文件 → 不同指纹。"""
    h1 = compute_config_hash(_cfg(media_path="D:/X/a.mp4"))
    h2 = compute_config_hash(_cfg(media_path="D:/X/b.mp4"))
    assert h1 != h2


def test_resume_fingerprint_rejects_override_change():
    """resume×override 交互：override 变更 → 指纹不匹配（配置已变化）。"""
    manifest = types.SimpleNamespace(
        input_sha1="a" * 40,
        config_hash=compute_config_hash(_cfg(media_path="D:/X/a.mp4")),
        glossary_sha1=None, tm_sha1=None)
    h_now = compute_config_hash(_cfg(media_path="D:/X/b.mp4"))
    assert validate_manifest(manifest, input_sha1="a" * 40,
                             config_hash=h_now) == ["配置已变化"]
    # 未设覆盖（空串）→ 与历史指纹同口径（该 manifest 未记录覆盖时）
    manifest2 = types.SimpleNamespace(
        input_sha1="a" * 40, config_hash="c" * 40,
        glossary_sha1=None, tm_sha1=None)
    h_empty = compute_config_hash(_cfg())
    assert validate_manifest(manifest2, input_sha1="a" * 40,
                             config_hash=h_empty) == ["配置已变化"]


# ---------------------------------------------------------------------------
# 3. 报告契约（只加不减）
# ---------------------------------------------------------------------------

def _entries():
    t = "00:00:01,000 --> 00:00:02,000"
    return [{"index": 1, "timing": t, "text": "元気ですか"}]


def test_report_txt_media_line_present_and_absent():
    r = build_quality_report(_entries(), _entries(), "demo",
                             media_path="E:/vid/ep01.mp4",
                             media_path_source="manifest")
    assert "媒体文件: E:/vid/ep01.mp4（来源: 自动发现）" in r
    r2 = build_quality_report(_entries(), _entries(), "demo",
                              media_path="E:/vid/ep01.mp4",
                              media_path_source="override")
    assert "媒体文件: E:/vid/ep01.mp4（来源: 显式指定）" in r2
    r3 = build_quality_report(_entries(), _entries(), "demo")
    assert "媒体文件" not in r3


def test_guide_json_media_keys_present_and_absent(tmp_path):
    guide: dict = {}
    build_quality_report(_entries(), _entries(), "demo", guide_sink=guide,
                         media_path="E:/vid/ep01.mp4",
                         media_path_source="override")
    assert guide["media_path"] == "E:/vid/ep01.mp4"
    assert guide["media_path_source"] == "override"
    p = Path(write_guide_json(str(tmp_path), "demo", dict(guide)))
    data = json.loads(p.read_text(encoding="utf-8"))
    assert data["media_path"] == "E:/vid/ep01.mp4"
    assert data["media_path_source"] == "override"

    guide0: dict = {}
    build_quality_report(_entries(), _entries(), "demo", guide_sink=guide0)
    assert "media_path" not in guide0
    assert "media_path_source" not in guide0
    p0 = Path(write_guide_json(str(tmp_path), "demo0", dict(guide0)))
    data0 = json.loads(p0.read_text(encoding="utf-8"))
    assert "media_path" not in data0
    assert "media_path_source" not in data0


# ---------------------------------------------------------------------------
# 4. 黄金样例（本地 .abtest 真实 manifest，未跟踪；不存在则跳过）
# ---------------------------------------------------------------------------

_ABTEST_DIRS = [Path(__file__).resolve().parent.parent / ".abtest" / "out",
                Path(__file__).resolve().parent.parent / ".abtest" / "prod"]


@pytest.mark.skipif(not any(d.is_dir() for d in _ABTEST_DIRS),
                    reason="本地 .abtest 真实样例目录不存在（CI/他机跳过）")
def test_golden_abtest_manifest_media_pairing():
    """对每份真实 whisperjav_run.json 与其 files[].output 做归一化配对，
    断言 100% 命中 files[].path。真实样例内容不进 tracked fixtures。"""
    n_checked = 0
    for d in _ABTEST_DIRS:
        if not d.is_dir():
            continue
        for mf in d.rglob(RUN_META_NAME):
            data = json.loads(mf.read_text(encoding="utf-8"))
            for entry in data.get("files") or []:
                out = entry.get("output")
                if not out:
                    continue
                n_checked += 1
                meta = _meta_result()
                media, src = resolve_media_path(str(out), meta)
                assert src == "manifest", mf
                assert os.path.normcase(os.path.abspath(media)) \
                    == os.path.normcase(os.path.abspath(entry["path"])), mf
    assert n_checked > 0
