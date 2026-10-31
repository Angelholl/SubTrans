"""webview_gui.api 桥端点补测（补卡5，D2026-1030-07）。

覆盖 ``TranslateAPI`` 既有测试差集中的纯逻辑端点与对话框端点：
不启动真窗口、不跑子进程/下载；CT2 运行时与 ffmpeg 供给一律打桩。
现状薄弱点只钉契约，不修产品代码。
"""
from pathlib import Path

import pytest

pytestmark = [pytest.mark.gui]

pytest.importorskip("webview", reason="pywebview 为可选 gui extra，未安装时跳过 GUI API 测试",
                    exc_type=ImportError)

import subtransjav.webview_gui.api as api_mod  # noqa: E402  须在 importorskip 之后
from subtransjav.webview_gui.api import (  # noqa: E402
    SESSION_SELECTED_PATHS,
    TranslateAPI,
)
from subtransjav.webview_gui.encode_queue import get_encode_queue  # noqa: E402


@pytest.fixture()
def gui_api_obj():
    """无副作用的 TranslateAPI 实例 + 干净的会话路径登记表（沿用先例）。"""
    SESSION_SELECTED_PATHS.clear()
    yield object.__new__(TranslateAPI)
    SESSION_SELECTED_PATHS.clear()


def _fake_window(monkeypatch, picked):
    """打桩原生窗口：``create_file_dialog`` 返回 [picked]（None=取消）。"""
    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(picked)] if picked else []

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])


def _nonempty_windows(monkeypatch):
    """``_open_file_dialog`` 类端点只需 ``webview.windows`` 非空。"""
    monkeypatch.setattr(api_mod.webview, "windows", [object()])


def _patch_dialog(monkeypatch, obj, result):
    """monkeypatch 实例的 ``_open_file_dialog``（open=list / save=list / 取消=None）。"""
    monkeypatch.setattr(obj, "_open_file_dialog", lambda *a, **k: result)


# ---------------------------------------------------------------------------
# A 组：纯逻辑端点（19）
# ---------------------------------------------------------------------------

def test_get_version_contract(gui_api_obj):
    """api.py:832 get_version：成功信封 + 版本三元组。"""
    r = gui_api_obj.get_version()
    assert r["success"] is True
    assert r["version"]
    assert r["version_pep440"]
    assert "version_info" in r


def test_get_system_status_grammar_available(gui_api_obj, monkeypatch):
    """api.py:853 get_system_status：子状态正常分支。"""
    from subtransjav.refine import grammar_hint
    monkeypatch.setattr(grammar_hint, "is_grammar_hint_available", lambda: True)
    r = gui_api_obj.get_system_status()
    assert r["success"] is True
    assert r["features"]["grammar_hints"]["available"] is True


def test_get_system_status_grammar_import_error_degrades(gui_api_obj, monkeypatch):
    """api.py:853 get_system_status：ImportError 降级为 unavailable。"""
    from subtransjav.refine import grammar_hint

    def _boom():
        raise ImportError("sudachi 缺席")

    monkeypatch.setattr(grammar_hint, "is_grammar_hint_available", _boom)
    r = gui_api_obj.get_system_status()
    assert r["success"] is True
    assert r["features"]["grammar_hints"]["available"] is False
    assert r["features"]["grammar_hints"]["description"]


def test_get_translation_logs_drains_queue(gui_api_obj):
    """api.py:1452 get_translation_logs：惰性初始化后一次性排空日志队列。"""
    gui_api_obj._init_translation_state()
    gui_api_obj._translate_log_queue.put("line-1")
    gui_api_obj._translate_log_queue.put("line-2")
    assert gui_api_obj.get_translation_logs() == ["line-1", "line-2"]
    assert gui_api_obj.get_translation_logs() == []


def test_refine_default_paths_contract(gui_api_obj, monkeypatch, tmp_path):
    """api.py:1493 refine_default_paths：持久模板目录优先 + 两路径键。"""
    monkeypatch.setattr(api_mod.user_dirs, "get_templates_dir", lambda: str(tmp_path))
    r = gui_api_obj.refine_default_paths()
    assert r["success"] is True
    assert r["templates_dir"] == str(tmp_path)
    assert r["glossary_path"]


def test_refine_ct2_status_not_installed_shape(gui_api_obj, monkeypatch):
    """api.py:1612 refine_ct2_status：未装运行时态 + 快照合并。"""
    from subtransjav.refine import asr_runtime
    monkeypatch.setattr(asr_runtime, "provider_status", lambda: {
        "installed": False, "selfcheck": "fail", "models": []})
    monkeypatch.setattr(asr_runtime, "gpu_patch_status", lambda: {"missing": []})
    monkeypatch.setattr(asr_runtime, "operation_progress", lambda: {"phase": "idle"})
    r = gui_api_obj.refine_ct2_status()
    assert r["success"] is True
    assert r["installed"] is False
    assert r["gpu_patch"] == {"missing": []}
    assert r["operation"] == {"phase": "idle"}


def test_open_output_folder_creates_missing_dir(gui_api_obj, monkeypatch, tmp_path):
    """api.py:1032 open_output_folder：create=True 建目录并放行。"""
    calls = []
    monkeypatch.setattr(api_mod.sys, "platform", "win32")
    monkeypatch.setattr(api_mod.os, "startfile", lambda p: calls.append(p), raising=False)
    target = tmp_path / "new-output"
    r = gui_api_obj.open_output_folder(str(target), create=True)
    assert r["success"] is True
    assert target.is_dir()
    assert calls == [str(target)]


def test_open_output_folder_missing_dir_without_create(gui_api_obj, monkeypatch, tmp_path):
    """api.py:1032 open_output_folder：create=False 缺目录返回结构化失败。"""
    monkeypatch.setattr(api_mod.sys, "platform", "win32")
    monkeypatch.setattr(api_mod.os, "startfile", lambda p: None, raising=False)
    r = gui_api_obj.open_output_folder(str(tmp_path / "absent"), create=False)
    assert r["success"] is False
    assert r["message"]


def test_open_output_folder_rejects_executable(gui_api_obj, monkeypatch, tmp_path):
    """api.py:1032 open_output_folder：经 ``_validate_user_directory`` 拦截可执行文件。"""
    calls = []
    monkeypatch.setattr(api_mod.sys, "platform", "win32")
    monkeypatch.setattr(api_mod.os, "startfile", lambda p: calls.append(p), raising=False)
    exe = tmp_path / "evil.exe"
    exe.write_bytes(b"MZ")
    r = gui_api_obj.open_output_folder(str(exe), create=False)
    assert r["success"] is False
    assert r["message"]
    assert calls == []


def test_get_default_output_dir_recomputes(gui_api_obj, monkeypatch, tmp_path):
    """api.py:1065 get_default_output_dir：重算并回写实例属性。"""
    target = tmp_path / "out"
    monkeypatch.setattr(api_mod, "_compute_default_output_dir", lambda: target)
    assert gui_api_obj.get_default_output_dir() == str(target)
    assert gui_api_obj.default_output == str(target)


def test_tm_get_stats_contract(gui_api_obj, tmp_path):
    """api.py:5128 tm_get_stats：空库统计信封。"""
    db = tmp_path / "tm.sqlite"
    r = gui_api_obj.tm_get_stats(db_path=str(db))
    assert r["success"] is True
    assert r["total"] == 0
    assert Path(r["db_path"]) == db.resolve()


def test_tm_clear_stage_legal(gui_api_obj, tmp_path):
    """api.py:5166 tm_clear：stage=1 定向清空，stage=0 保留。"""
    from subtransjav.refine.tm import TranslationMemory
    db = tmp_path / "tm.sqlite"
    tm = TranslationMemory(str(db))
    try:
        tm.store("a", "A", 0)
        tm.store("b", "B", 1)
    finally:
        tm.close()
    r = gui_api_obj.tm_clear(stage=1, db_path=str(db))
    assert r["success"] is True
    assert r["message"]
    tm = TranslationMemory(str(db))
    try:
        assert tm.stats()["total"] == 1
        assert tm.stats()["by_stage"] == {0: 1}
    finally:
        tm.close()


def test_tm_clear_illegal_stage_noop(gui_api_obj, tmp_path):
    """api.py:5166 tm_clear：现状对非法 stage 无范围校验——成功且零删除。"""
    from subtransjav.refine.tm import TranslationMemory
    db = tmp_path / "tm.sqlite"
    tm = TranslationMemory(str(db))
    try:
        tm.store("a", "A", 0)
    finally:
        tm.close()
    r = gui_api_obj.tm_clear(stage=9, db_path=str(db))
    assert r["success"] is True
    tm = TranslationMemory(str(db))
    try:
        assert tm.stats()["total"] == 1
    finally:
        tm.close()


def test_tm_export_csv_overwrites_existing(gui_api_obj, tmp_path):
    """api.py:5187 tm_export_csv：覆盖既有文件，返回落点路径。"""
    from subtransjav.refine.tm import TranslationMemory
    db = tmp_path / "tm.sqlite"
    tm = TranslationMemory(str(db))
    try:
        tm.store("源", "译", 0)
    finally:
        tm.close()
    out = tmp_path / "out.csv"
    out.write_text("OLD", encoding="utf-8")
    r = gui_api_obj.tm_export_csv(path=str(out), db_path=str(db))
    assert r["success"] is True
    assert Path(r["path"]) == out.resolve()
    text = out.read_text(encoding="utf-8-sig")
    assert "源" in text and "译" in text
    assert "OLD" not in text


def test_tm_import_csv_skips_bad_rows(gui_api_obj, tmp_path):
    """api.py:5207 tm_import_csv：坏行跳过，只计有效新增。"""
    from subtransjav.refine.tm import TranslationMemory
    db = tmp_path / "tm.sqlite"
    csv = tmp_path / "in.csv"
    csv.write_text(
        "source,target,stage\n"
        "甲,乙,0\n"
        "只有一列\n"
        ",空原文,0\n",
        encoding="utf-8-sig")
    r = gui_api_obj.tm_import_csv(path=str(csv), db_path=str(db))
    assert r["success"] is True
    assert r["added"] == 1
    assert r["message"]
    tm = TranslationMemory(str(db))
    try:
        assert tm.stats()["total"] == 1
    finally:
        tm.close()


def test_tm_import_csv_missing_path(gui_api_obj):
    """api.py:5207 tm_import_csv：缺 path 结构化拒绝。"""
    r = gui_api_obj.tm_import_csv(path=None)
    assert r["success"] is False
    assert r["error"]


def test_cleanup_refine_tmp_dirs(gui_api_obj, tmp_path):
    """api.py:5246 cleanup_refine_tmp_dirs：删存在项、跳过缺失项、清空台账。"""
    d1 = tmp_path / "t1"
    d2 = tmp_path / "t2"
    d1.mkdir()
    d2.mkdir()
    missing = tmp_path / "gone"
    gui_api_obj._refine_tmp_dirs = [str(d1), str(d2), str(missing)]
    r = gui_api_obj.cleanup_refine_tmp_dirs()
    assert r["success"] is True
    assert r["cleaned"] == [str(d1), str(d2)]
    assert not d1.exists() and not d2.exists()
    assert gui_api_obj._refine_tmp_dirs == []


def test_encode_cancel_unknown_job_passthrough(gui_api_obj):
    """api.py:5560 encode_cancel：任意 job_id 透传成功（现状无拒绝）。"""
    r = gui_api_obj.encode_cancel("no-such-job")
    assert r["success"] is True
    assert get_encode_queue() is not None


def test_encode_retry_unknown_job_structured_error(gui_api_obj):
    """api.py:5566 encode_retry：job 不存在返回结构化错误。"""
    r = gui_api_obj.encode_retry("no-such-job")
    assert r["success"] is False
    assert r["error"]


def test_encode_open_folder_unknown_job_structured_error(gui_api_obj):
    """api.py:5575 encode_open_folder：job 不存在返回结构化错误。"""
    r = gui_api_obj.encode_open_folder("no-such-job")
    assert r["success"] is False
    assert r["error"]


def test_refine_review_transcode_status_empty_state(gui_api_obj):
    """api.py:4918 refine_review_transcode_status：无会话零值快照（无 success 键）。"""
    r = gui_api_obj.refine_review_transcode_status()
    assert "success" not in r
    assert r == {"running": False, "percent": None, "error": None,
                 "path": None, "cached": False}


def test_refine_preview_infer_media_empty_guide(gui_api_obj):
    """api.py:4398 refine_preview_infer_media：空路径 no_candidate。"""
    r = gui_api_obj.refine_preview_infer_media("")
    assert r["ok"] is False
    assert r["error_key"] == "no_candidate"
    assert r["candidates"] == []


def test_refine_preview_infer_media_non_guide(gui_api_obj, tmp_path):
    """api.py:4398 refine_preview_infer_media：非导读文件 no_candidate。"""
    r = gui_api_obj.refine_preview_infer_media(str(tmp_path / "x.txt"))
    assert r["ok"] is False
    assert r["error_key"] == "no_candidate"
    assert r["candidates"] == []


def test_refine_preview_infer_media_missing_media(gui_api_obj, tmp_path):
    """api.py:4398 refine_preview_infer_media：导读存在但同目录无媒体。"""
    guide = tmp_path / "clip_质量报告导读.json"
    guide.write_text("{}", encoding="utf-8")
    r = gui_api_obj.refine_preview_infer_media(str(guide))
    assert r["ok"] is False
    assert r["error_key"] == "no_candidate"
    assert r["candidates"] == []


def test_ffmpeg_supply_progress_idle_default(gui_api_obj):
    """api.py:5777 ffmpeg_supply_progress：未初始化时 ``_ensure_supply_state`` 建 idle。"""
    r = gui_api_obj.ffmpeg_supply_progress()
    assert r["success"] is True
    assert r["phase"] == "idle"
    assert r["received"] == 0 and r["total"] == 0
    assert r["busy"] is False


def test_ffmpeg_supply_stop_without_download(gui_api_obj):
    """api.py:5770 ffmpeg_supply_stop：无进行中下载仍返回成功。"""
    assert gui_api_obj.ffmpeg_supply_stop() == {"success": True}


def test_refine_ct2_model_download_invalid_param(gui_api_obj, monkeypatch):
    """api.py:1653 refine_ct2_model_download：非法参数走桩，不起真下载。"""
    from subtransjav.refine import asr_runtime
    seen = []

    def _fake(model):
        seen.append(model)
        return {"started": False, "reason": f"非法模型: {model}"}

    monkeypatch.setattr(asr_runtime, "start_model_download", _fake)
    r = gui_api_obj.refine_ct2_model_download("bogus")
    assert r["success"] is False
    assert r["started"] is False
    assert r["reason"] == "非法模型: bogus"
    assert seen == ["bogus"]


# ---------------------------------------------------------------------------
# B 组：对话框端点（7，选中/取消两态）
# ---------------------------------------------------------------------------

def test_select_folder_selected(gui_api_obj, monkeypatch, tmp_path):
    """api.py:891 select_folder：选中即登记会话路径。"""
    picked = tmp_path / "picked"
    picked.mkdir()
    _fake_window(monkeypatch, picked)
    r = gui_api_obj.select_folder()
    assert r == {"success": True, "path": str(picked)}
    assert str(picked.resolve()) in SESSION_SELECTED_PATHS


def test_select_folder_cancelled(gui_api_obj, monkeypatch):
    """api.py:891 select_folder：取消返回 no_folder_selected。"""
    _fake_window(monkeypatch, None)
    r = gui_api_obj.select_folder()
    assert r["success"] is False
    assert r["message"]


def test_select_output_directory_selected(gui_api_obj, monkeypatch, tmp_path):
    """api.py:903 select_output_directory：委托 select_folder。"""
    picked = tmp_path / "out"
    picked.mkdir()
    _fake_window(monkeypatch, picked)
    r = gui_api_obj.select_output_directory()
    assert r == {"success": True, "path": str(picked)}


def test_select_output_directory_cancelled(gui_api_obj, monkeypatch):
    """api.py:903 select_output_directory：取消同源透传。"""
    _fake_window(monkeypatch, None)
    r = gui_api_obj.select_output_directory()
    assert r["success"] is False
    assert r["message"]


def test_select_srt_files_selected(gui_api_obj, monkeypatch, tmp_path):
    """api.py:927 select_srt_files：多选返回 paths 并登记。"""
    picked = [str(tmp_path / "a.srt"), str(tmp_path / "b.ass")]
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, picked)
    r = gui_api_obj.select_srt_files()
    assert r == {"success": True, "paths": picked}
    assert str(Path(picked[0]).resolve()) in SESSION_SELECTED_PATHS


def test_select_srt_files_cancelled(gui_api_obj, monkeypatch):
    """api.py:927 select_srt_files：取消返回 no_files_selected。"""
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, None)
    r = gui_api_obj.select_srt_files()
    assert r["success"] is False
    assert r["message"]


def test_refine_pick_csv_open_selected(gui_api_obj, monkeypatch, tmp_path):
    """api.py:2472 refine_pick_csv_open：选中返回单路径。"""
    picked = [str(tmp_path / "glossary.csv")]
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, picked)
    r = gui_api_obj.refine_pick_csv_open()
    assert r == {"success": True, "path": picked[0]}


def test_refine_pick_csv_open_cancelled(gui_api_obj, monkeypatch):
    """api.py:2472 refine_pick_csv_open：取消结构化失败。"""
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, None)
    r = gui_api_obj.refine_pick_csv_open()
    assert r["success"] is False
    assert r["error"]


def test_refine_pick_csv_save_selected(gui_api_obj, monkeypatch, tmp_path):
    """api.py:2503 refine_pick_csv_save：保存路径返回单路径。"""
    picked = [str(tmp_path / "export.csv")]
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, picked)
    r = gui_api_obj.refine_pick_csv_save()
    assert r == {"success": True, "path": picked[0]}


def test_refine_pick_csv_save_cancelled(gui_api_obj, monkeypatch):
    """api.py:2503 refine_pick_csv_save：取消结构化失败。"""
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, None)
    r = gui_api_obj.refine_pick_csv_save()
    assert r["success"] is False
    assert r["error"]


def test_refine_review_pick_media_selected(gui_api_obj, monkeypatch, tmp_path):
    """api.py:4741 refine_review_pick_media：选中返回单路径。"""
    picked = [str(tmp_path / "clip.mp4")]
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, picked)
    r = gui_api_obj.refine_review_pick_media()
    assert r == {"success": True, "path": picked[0]}


def test_refine_review_pick_media_cancelled(gui_api_obj, monkeypatch):
    """api.py:4741 refine_review_pick_media：取消带 cancelled 标记。"""
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, None)
    r = gui_api_obj.refine_review_pick_media()
    assert r["success"] is False
    assert r["cancelled"] is True


def test_refine_review_pick_srt_selected(gui_api_obj, monkeypatch, tmp_path):
    """api.py:4756 refine_review_pick_srt：选中返回单路径。"""
    picked = [str(tmp_path / "clip.srt")]
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, picked)
    r = gui_api_obj.refine_review_pick_srt()
    assert r == {"success": True, "path": picked[0]}


def test_refine_review_pick_srt_cancelled(gui_api_obj, monkeypatch):
    """api.py:4756 refine_review_pick_srt：取消带 cancelled 标记。"""
    _nonempty_windows(monkeypatch)
    _patch_dialog(monkeypatch, gui_api_obj, None)
    r = gui_api_obj.refine_review_pick_srt()
    assert r["success"] is False
    assert r["cancelled"] is True


# ---------------------------------------------------------------------------
# C 组：子进程型端点（补卡7；桩内部安装/下载调用，不真起进程不真写网络）
# ---------------------------------------------------------------------------

def _capture_threads(monkeypatch, captured):
    """打桩 ``threading.Thread``：只记录参数，不真起线程。"""
    class FakeThread:
        def __init__(self, target=None, name=None, daemon=None, args=(), kwargs=None):
            captured.append({"target": target, "name": name,
                             "daemon": daemon, "args": args})
        def start(self):
            return None

    monkeypatch.setattr(api_mod.threading, "Thread", FakeThread)


def test_refine_ct2_install_started(gui_api_obj, monkeypatch):
    """api.py:1640 refine_ct2_install：started=True 透传成功并带 provider。"""
    from subtransjav.refine import asr_runtime
    seen = []

    def _fake(provider):
        seen.append(provider)
        return {"started": True, "provider": provider}

    monkeypatch.setattr(asr_runtime, "start_install", _fake)
    r = gui_api_obj.refine_ct2_install("zip")
    assert r == {"success": True, "started": True, "provider": "zip"}
    assert seen == ["zip"]


def test_refine_ct2_install_already_running(gui_api_obj, monkeypatch):
    """api.py:1640 refine_ct2_install：重复启动被拒，reason 原样透传。"""
    from subtransjav.refine import asr_runtime
    monkeypatch.setattr(asr_runtime, "start_install",
                        lambda p: {"started": False, "reason": "已有 ct2 安装任务在跑"})
    r = gui_api_obj.refine_ct2_install("auto")
    assert r["success"] is False
    assert r["started"] is False
    assert r["reason"] == "已有 ct2 安装任务在跑"


def test_refine_ct2_install_invalid_provider_short_circuits(gui_api_obj, monkeypatch):
    """api.py:1640 refine_ct2_install：非法 provider 前置拒绝，不调安装。"""
    from subtransjav.refine import asr_runtime
    seen = []
    monkeypatch.setattr(asr_runtime, "start_install",
                        lambda p: seen.append(p) or {"started": True})
    r = gui_api_obj.refine_ct2_install("bogus")
    assert r == {"success": False, "error": "非法 provider: bogus"}
    assert seen == []


def test_refine_ct2_install_internal_error(gui_api_obj, monkeypatch):
    """api.py:1640 refine_ct2_install：内部异常降级为结构化失败。"""
    from subtransjav.refine import asr_runtime

    def _boom(provider):
        raise RuntimeError("安装入口炸")

    monkeypatch.setattr(asr_runtime, "start_install", _boom)
    r = gui_api_obj.refine_ct2_install()
    assert r["success"] is False
    assert "安装入口炸" in r["error"]


def test_refine_ct2_gpu_install_started(gui_api_obj, monkeypatch):
    """api.py:1628 refine_ct2_gpu_install：started=True 透传成功。"""
    from subtransjav.refine import asr_runtime
    monkeypatch.setattr(asr_runtime, "start_gpu_patch_install",
                        lambda: {"started": True})
    assert gui_api_obj.refine_ct2_gpu_install() == {"success": True, "started": True}


def test_refine_ct2_gpu_install_precheck_blocked(gui_api_obj, monkeypatch):
    """api.py:1628 refine_ct2_gpu_install：前置拦截（未装运行时）透传 reason。"""
    from subtransjav.refine import asr_runtime
    monkeypatch.setattr(asr_runtime, "start_gpu_patch_install",
                        lambda: {"started": False, "reason": "CT2 运行时未安装"})
    r = gui_api_obj.refine_ct2_gpu_install()
    assert r["success"] is False
    assert r["started"] is False
    assert r["reason"] == "CT2 运行时未安装"


def test_refine_ct2_gpu_install_internal_error(gui_api_obj, monkeypatch):
    """api.py:1628 refine_ct2_gpu_install：内部异常降级为结构化失败。"""
    from subtransjav.refine import asr_runtime

    def _boom():
        raise RuntimeError("补丁安装入口炸")

    monkeypatch.setattr(asr_runtime, "start_gpu_patch_install", _boom)
    r = gui_api_obj.refine_ct2_gpu_install()
    assert r["success"] is False
    assert "补丁安装入口炸" in r["error"]


def test_ffmpeg_supply_download_starts_worker(gui_api_obj, monkeypatch):
    """api.py:5736 ffmpeg_supply_download：置 busy + downloading，daemon 线程发起。"""
    captured = []
    _capture_threads(monkeypatch, captured)
    r = gui_api_obj.ffmpeg_supply_download()
    assert r == {"success": True}
    assert gui_api_obj._supply_busy is True
    assert gui_api_obj._supply_state["phase"] == "downloading"
    assert gui_api_obj._supply_state["received"] == 0
    assert gui_api_obj._supply_state["total"] == 0
    assert len(captured) == 1
    assert captured[0]["name"] == "ffmpeg-supply-download"
    assert captured[0]["daemon"] is True


def test_ffmpeg_supply_download_rejects_duplicate(gui_api_obj):
    """api.py:5736 ffmpeg_supply_download：busy 时重复发起结构化拒绝。"""
    gui_api_obj._supply_busy = True
    r = gui_api_obj.ffmpeg_supply_download()
    assert r == {"success": False, "error": "ffmpeg 下载已在进行中"}


def test_ffmpeg_supply_download_worker_completes(gui_api_obj, monkeypatch, tmp_path):
    """api.py:5736 后台 worker：下载完成置 done、回进度并清 busy。"""
    captured = []
    _capture_threads(monkeypatch, captured)
    from subtransjav import paths
    from subtransjav.refine import ffmpeg_supply
    calls = []

    def _fake_download(root, progress_cb=None, stop_event=None):
        calls.append((root, stop_event))
        progress_cb(5, 10)

    class FakeQueue:
        def __init__(self):
            self.reset_calls = 0

        def reset_supply(self):
            self.reset_calls += 1

    queue = FakeQueue()
    monkeypatch.setattr(ffmpeg_supply, "download_full_variant", _fake_download)
    monkeypatch.setattr(paths, "data_root", lambda: tmp_path)
    monkeypatch.setattr(gui_api_obj, "_encode_queue", lambda: queue)
    gui_api_obj.ffmpeg_supply_download()
    captured[0]["target"]()
    assert calls[0][0] == str(tmp_path)
    assert gui_api_obj._supply_state["phase"] == "done"
    assert gui_api_obj._supply_state["received"] == 5
    assert gui_api_obj._supply_busy is False
    assert queue.reset_calls == 1


def test_ffmpeg_supply_download_worker_failure(gui_api_obj, monkeypatch, tmp_path):
    """api.py:5736 后台 worker：下载异常置 failed 并保留错误文本。"""
    captured = []
    _capture_threads(monkeypatch, captured)
    from subtransjav import paths
    from subtransjav.refine import ffmpeg_supply

    def _boom(root, progress_cb=None, stop_event=None):
        raise RuntimeError("网络断")

    monkeypatch.setattr(ffmpeg_supply, "download_full_variant", _boom)
    monkeypatch.setattr(paths, "data_root", lambda: tmp_path)
    gui_api_obj.ffmpeg_supply_download()
    captured[0]["target"]()
    assert gui_api_obj._supply_state["phase"] == "failed"
    assert gui_api_obj._supply_state["error"] == "网络断"
    assert gui_api_obj._supply_busy is False


def test_ffmpeg_supply_stop_sets_active_event(gui_api_obj):
    """api.py:5770 ffmpeg_supply_stop：进行中下载置停止事件并返回成功。"""
    event = api_mod.threading.Event()
    gui_api_obj._supply_stop = event
    assert gui_api_obj.ffmpeg_supply_stop() == {"success": True}
    assert event.is_set()
