"""webview_gui.api 浅层测试（P3-10/P3-11）。

不启动任何窗口：
- ``_build_refine_args`` 为模块级纯函数，直接调用；
- ``scan_resume_states`` 不依赖实例状态，用 ``object.__new__`` 构造实例，
  规避 ``__init__`` 的副作用（Documents 建目录 / atexit 注册）；
- URL/endpoint 守卫入口在发起任何网络请求之前即短路，无网络副作用。
"""
import contextlib
import io
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace

import openai
import pytest

pytestmark = [pytest.mark.gui]

pytest.importorskip("webview", reason="pywebview 为可选 gui extra，未安装时跳过 GUI API 测试", exc_type=ImportError)

from subtransjav.refine.events import EventEmitter  # noqa: E402
from subtransjav.webview_gui.api import (  # noqa: E402  须在 importorskip 之后
    REPO_ROOT,
    SESSION_SELECTED_PATHS,
    TranslateAPI,
    _build_refine_args,
    register_session_paths,
)
from subtransjav.webview_gui.event_stream import EventStreamParser  # noqa: E402


@pytest.fixture()
def gui_api_obj():
    """无副作用的 TranslateAPI 实例 + 干净的会话路径登记表。"""
    SESSION_SELECTED_PATHS.clear()
    yield object.__new__(TranslateAPI)
    SESSION_SELECTED_PATHS.clear()


@pytest.fixture(autouse=True)
def _isolate_child_procs_ledger(tmp_path, monkeypatch):
    """批4：子进程台账落点打桩到测试 tmp（登记/自愈路径防真实写仓库
    config/；仅重定向 api._child_procs_ledger_path，不触碰 CONFIG_DIR
    其余消费方，零既有行为扰动）。"""
    import subtransjav.webview_gui.api as api_mod
    monkeypatch.setattr(
        api_mod, "_child_procs_ledger_path",
        lambda: str(tmp_path / "config" / "child_procs.json"))


# ---------------------------------------------------------------------------
# _build_refine_args：CLI 参数装配（模块级纯函数）
# ---------------------------------------------------------------------------

def test_build_refine_args_resume_flag():
    args = _build_refine_args({"inputs": ["a.srt"], "resume": True})
    assert "--resume" in args


def test_build_refine_args_no_resume_by_default():
    args = _build_refine_args({"inputs": ["a.srt"]})
    assert "--resume" not in args


def test_build_refine_args_ctx_passthrough():
    """上下文窗口经 GUI 透传为对应 CLI 旗标（D2026-0923-01）。"""
    args = _build_refine_args({"inputs": ["a.srt"], "v2_ctx": 22272})
    assert args[args.index("--v2-ctx") + 1] == "22272"


def test_build_refine_args_no_ctx_by_default():
    args = _build_refine_args({"inputs": ["a.srt"]})
    assert "--v2-ctx" not in args


def test_build_refine_args_concurrency_default_1():
    """GUI 桥接并发缺省=1（v1.3.2 X 方案，与管线 v2_concurrency=1 对齐）。

    options 不含 v2_concurrency（GUI 未传/持久化无值）时，传给 CLI 的
    --v2-concurrency 必须为 1；显式值（含存量持久化 2）照常透传。
    """
    args = _build_refine_args({"inputs": ["a.srt"]})
    assert args[args.index("--v2-concurrency") + 1] == "1"


def test_build_refine_args_concurrency_explicit_2_passthrough():
    """显式并发值 2（如本机 refine_stage_settings.json 已持久化值）照常生效。"""
    args = _build_refine_args({"inputs": ["a.srt"], "v2_concurrency": 2})
    assert args[args.index("--v2-concurrency") + 1] == "2"


def test_build_refine_args_always_ndjson_event_format():
    """GUI 子进程恒以 ndjson 事件流输出（GUI 侧解析依赖）。"""
    for options in ({"inputs": ["a.srt"]},
                    {"inputs": ["a.srt"], "resume": True},
                    {"inputs": ["a.srt"], "verbose": True}):
        args = _build_refine_args(options)
        i = args.index("--event-format")
        assert args[i + 1] == "ndjson"


def test_build_refine_args_dash_prefixed_input_guard():
    """以 '-' 开头的文件名必须改用 --input= 形式，防止被解析成 CLI 旗标。"""
    p = "-weird-name.srt"
    args = _build_refine_args({"inputs": [p, "normal.srt"]})
    assert f"--input={p}" in args
    assert "-i" in args
    assert args[args.index("-i") + 1] == "normal.srt"


def test_build_refine_args_new_safety_params_absent_by_default():
    """四个安全参数缺省时均不产生 CLI 旗标。"""
    args = _build_refine_args({"inputs": ["a.srt"]})
    for flag in ("--source-filter", "--no-auto-synopsis", "--dry-run"):
        assert flag not in args


def test_build_refine_args_source_filter_non_default():
    """source_filter 传合法非默认值时产生 --source-filter；默认值不传。"""
    args = _build_refine_args({"inputs": ["a.srt"], "source_filter": "strict"})
    i = args.index("--source-filter")
    assert args[i + 1] == "strict"
    args = _build_refine_args({"inputs": ["a.srt"], "source_filter": "default"})
    assert "--source-filter" not in args


def test_build_refine_args_auto_synopsis_inverted_only_when_false():
    """auto_synopsis 仅显式 False 时产生 --no-auto-synopsis。"""
    for v in (None, True):
        options = {"inputs": ["a.srt"]}
        if v is not None:
            options["auto_synopsis"] = v
        assert "--no-auto-synopsis" not in _build_refine_args(options)
    args = _build_refine_args({"inputs": ["a.srt"], "auto_synopsis": False})
    assert "--no-auto-synopsis" in args


def test_build_refine_args_dry_run_flag():
    args = _build_refine_args({"inputs": ["a.srt"], "dry_run": True})
    assert "--dry-run" in args
    assert "--dry-run" not in _build_refine_args({"inputs": ["a.srt"]})


def test_build_refine_args_tm_params_passthrough():
    args = _build_refine_args({
        "inputs": ["a.srt"],
        "no_tm": True,
        "tm_db": "D:/tm/tm.db",
        "tm_threshold": "0.75",
    })
    assert "--no-tm" in args
    assert args[args.index("--tm-db") + 1] == "D:/tm/tm.db"
    assert args[args.index("--tm-threshold") + 1] == "0.75"


def test_build_refine_args_tm_params_absent_by_default():
    args = _build_refine_args({"inputs": ["a.srt"]})
    assert "--no-tm" not in args
    assert "--tm-db" not in args
    assert "--tm-threshold" not in args


def test_build_refine_args_no_tm_absent_when_tm_enabled():
    args = _build_refine_args({"inputs": ["a.srt"], "no_tm": False, "tm_db": "D:/tm/tm.db"})
    assert "--no-tm" not in args
    assert "--tm-db" in args


# ---------------------------------------------------------------------------
# force 覆盖确认（D2026-0925-01 D6 终选）：
# - _build_refine_args 仅在 options["force"] 为真时追加 --force；
# - start_translation 检测到已完成终稿且未带 force 时不启动进程，
#   返回 needs_confirm + existing 产物清单。
# ---------------------------------------------------------------------------

def test_build_refine_args_force_only_when_true():
    """critic 要求的可回归约束：未带 force 不拼 --force，带 force 才含。"""
    args = _build_refine_args({"inputs": ["a.srt"]})
    assert "--force" not in args
    args = _build_refine_args({"inputs": ["a.srt"], "force": False})
    assert "--force" not in args
    args = _build_refine_args({"inputs": ["a.srt"], "force": True})
    assert "--force" in args


def test_start_translation_needs_confirm_when_final_exists(tmp_path, gui_api_obj):
    """已完成终稿（{stem}_final_cn.srt 存在）且未带 force：不启动进程，
    返回结构化 needs_confirm 与 existing 产物文件名清单。"""
    (tmp_path / "ep01_final_cn.srt").write_text("终稿", encoding="utf-8")
    result = gui_api_obj.start_translation({"inputs": [str(tmp_path / "ep01.srt")]})
    assert result["success"] is False
    assert result["needs_confirm"] is True
    assert result["existing"] == ["ep01_final_cn.srt"]
    # 未启动任何子进程
    assert getattr(gui_api_obj, "_translate_process", None) is None


# ---------------------------------------------------------------------------
# D6 遗留：force-resume 通道 + 学习闸开关（--glossary-learn /
# --glossary-conflict-block；tm_learn_gate 默认 True，GUI 不设开关）
# ---------------------------------------------------------------------------

def test_build_refine_args_force_resume_flag():
    """勾选 refineForceResume 才拼 --force-resume；隐含 resume 由
    RefineConfig.__post_init__ 不变式保证，此处不重复拼 --resume。"""
    args = _build_refine_args({"inputs": ["a.srt"], "force_resume": True})
    assert "--force-resume" in args


def test_build_refine_args_no_force_resume_by_default():
    args = _build_refine_args({"inputs": ["a.srt"]})
    assert "--force-resume" not in args


def test_build_refine_args_glossary_learn_flag():
    # 批4 件1：GUI 勾选「学习词库」= 双闸同开（外层 --glossary-learn +
    # 内层 --auto-glossary 同时拼装）
    args = _build_refine_args({"inputs": ["a.srt"], "glossary_learn": True})
    assert "--glossary-learn" in args
    assert "--auto-glossary" in args


def test_build_refine_args_glossary_learn_absent_by_default():
    # 缺省（不勾）= 两旗标皆无，默认行为零变化
    args = _build_refine_args({"inputs": ["a.srt"]})
    assert "--glossary-learn" not in args
    assert "--auto-glossary" not in args


def test_build_refine_args_glossary_conflict_block_flag():
    args = _build_refine_args({"inputs": ["a.srt"],
                               "glossary_conflict_block": True})
    assert "--glossary-conflict-block" in args


def test_build_refine_args_glossary_conflict_block_absent_by_default():
    args = _build_refine_args({"inputs": ["a.srt"]})
    assert "--glossary-conflict-block" not in args


class _StopLaunch(Exception):
    """fake Popen 哨兵：捕获拼好的 args 后终止启动流程。"""


def _capture_popen(monkeypatch, captured, api_obj):
    import threading

    import subtransjav.webview_gui.api as api_mod

    # _translate_lock 由 __init__ 创建；object.__new__ 实例需手动补齐
    api_obj._translate_lock = threading.Lock()

    def fake_popen(args, **kwargs):
        captured["args"] = list(args)
        raise _StopLaunch("stop-before-spawn")

    monkeypatch.setattr(api_mod.subprocess, "Popen", fake_popen)


def test_start_translation_without_force_args_have_no_force_flag(
        tmp_path, gui_api_obj, monkeypatch):
    """无终稿走正常启动路径：mock 进程层捕获 args，未带 force 则不含 --force。"""
    captured = {}
    _capture_popen(monkeypatch, captured, gui_api_obj)
    result = gui_api_obj.start_translation({"inputs": [str(tmp_path / "ep02.srt")]})
    assert result["success"] is False  # _StopLaunch 被启动异常分支吞掉
    assert "--force" not in captured["args"]


def test_start_translation_with_force_args_include_force_flag(
        tmp_path, gui_api_obj, monkeypatch):
    """确认后带 force=True 重调：拼出的 args 含 --force（确认路径可达）。"""
    captured = {}
    _capture_popen(monkeypatch, captured, gui_api_obj)
    result = gui_api_obj.start_translation(
        {"inputs": [str(tmp_path / "ep01.srt")], "force": True})
    assert result["success"] is False
    assert "--force" in captured["args"]


# ---------------------------------------------------------------------------
# scan_resume_states：断点恢复三态 + 信任边界（未登记路径跳过）
# ---------------------------------------------------------------------------

def _prepare_states(tmp_path):
    """造三个输入：ep01 有终稿（completed）、ep02 有清单（resumable）、
    ep03 什么都没有（none）。返回对应的 srt 路径列表。"""
    (tmp_path / "ep01_final_cn.srt").write_text("终稿", encoding="utf-8")
    (tmp_path / "ep02_manifest.json").write_text("{}", encoding="utf-8")
    return [str(tmp_path / f"ep0{n}.srt") for n in (1, 2, 3)]


def test_scan_resume_states_three_states(tmp_path, gui_api_obj):
    paths = _prepare_states(tmp_path)
    register_session_paths(paths)
    results = gui_api_obj.scan_resume_states(paths)
    by_stem = {r["stem"]: r["state"] for r in results}
    assert by_stem == {"ep01": "completed", "ep02": "resumable", "ep03": "none"}


def test_scan_resume_states_skips_unregistered_paths(tmp_path, gui_api_obj):
    """信任边界：未经理受信入口登记的路径一律跳过，不做任意路径解析。"""
    paths = _prepare_states(tmp_path)  # ep01 本可返回 completed
    assert gui_api_obj.scan_resume_states(paths) == []


def test_scan_resume_states_skips_invalid_entries(tmp_path, gui_api_obj):
    """None / 空串等非法条目静默跳过，不抛异常。"""
    good = str(tmp_path / "ep01.srt")
    (tmp_path / "ep01_final_cn.srt").write_text("终稿", encoding="utf-8")
    register_session_paths([good])
    results = gui_api_obj.scan_resume_states([None, "", 123, good])
    assert [r["stem"] for r in results] == ["ep01"]


# ---------------------------------------------------------------------------
# URL / endpoint 守卫（P3-11 回归）：入口在触网前短路
# 设计决策：仅校验 scheme（http/https），不拦截 localhost/私有地址——
# 连接本地 LM Studio/Ollama 是本工具的核心功能。
# ---------------------------------------------------------------------------

def test_open_url_rejects_unsafe_schemes(gui_api_obj):
    for url in ("file:///C:/Windows/System32/calc.exe",
                "javascript:alert(1)",
                "ftp://example.com/x", ""):
        result = gui_api_obj.open_url(url)
        assert result["success"] is False, url
        assert "http/https" in result["error"]


def test_refine_list_models_rejects_non_http_endpoint(gui_api_obj):
    result = gui_api_obj.refine_list_models("lmstudio",
                                            endpoint="file:///etc/passwd")
    assert result["success"] is False
    assert "http/https" in result["error"]


def test_refine_test_stage_rejects_non_http_endpoint(gui_api_obj):
    result = gui_api_obj.refine_test_stage("lmstudio", "some-model",
                                           endpoint="javascript:alert(1)")
    assert result["success"] is False
    assert "http/https" in result["error"]


# ---------------------------------------------------------------------------
# OpenAI 客户端生命周期：两处按钮入口均为"创建→单次调用→丢弃"，
# GUI 常驻进程下客户端必须随调用结束关闭（含异常路径），防连接池累积。
# ---------------------------------------------------------------------------

def _install_fake_openai(monkeypatch, list_error=None, create_error=None):
    """替换 openai.OpenAI 为记录型替身（零网络请求），返回创建的客户端列表。"""
    created: list = []

    class FakeModels:
        def list(self):
            if list_error is not None:
                raise list_error
            return [SimpleNamespace(id="model-b"), SimpleNamespace(id="model-a")]

    class FakeCompletions:
        def create(self, **kwargs):
            if create_error is not None:
                raise create_error
            message = SimpleNamespace(content="pong", reasoning_content=None)
            return SimpleNamespace(choices=[SimpleNamespace(message=message)])

    class FakeChat:
        def __init__(self):
            self.completions = FakeCompletions()

    class FakeClient:
        def __init__(self, base_url=None, api_key=None, timeout=None):
            self.base_url = base_url
            self.api_key = api_key
            self.timeout = timeout
            self.closed = False
            self.models = FakeModels()
            self.chat = FakeChat()
            created.append(self)

        def close(self):
            self.closed = True

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

    monkeypatch.setattr(openai, "OpenAI", FakeClient)
    return created


def test_refine_list_models_closes_client(gui_api_obj, monkeypatch):
    """刷新模型列表用完即关：重复点击不累积未关闭客户端。"""
    created = _install_fake_openai(monkeypatch)
    for _ in range(2):
        result = gui_api_obj.refine_list_models(
            "lmstudio", endpoint="http://localhost:1234/v1")
        assert result["success"] is True
        assert result["models"] == ["model-a", "model-b"]
    assert [c.closed for c in created] == [True, True]


def test_refine_list_models_closes_client_on_list_error(gui_api_obj, monkeypatch):
    """models.list 抛错时客户端同样被关闭（异常路径不泄漏）。"""
    created = _install_fake_openai(monkeypatch, list_error=RuntimeError("boom"))
    result = gui_api_obj.refine_list_models(
        "lmstudio", endpoint="http://localhost:1234/v1")
    assert result["success"] is False
    assert created and created[0].closed is True


def test_refine_test_stage_closes_client(gui_api_obj, monkeypatch):
    """连通性测试用完即关：客户端在成功返回前已关闭。"""
    created = _install_fake_openai(monkeypatch)
    result = gui_api_obj.refine_test_stage(
        "lmstudio", "model-a", endpoint="http://localhost:1234/v1")
    assert result["success"] is True
    assert result["message"] == "pong"
    assert created and created[0].closed is True


def test_refine_test_stage_closes_client_on_create_error(gui_api_obj, monkeypatch):
    """chat.completions.create 抛错时客户端同样被关闭。"""
    created = _install_fake_openai(monkeypatch, create_error=RuntimeError("boom"))
    result = gui_api_obj.refine_test_stage(
        "lmstudio", "model-a", endpoint="http://localhost:1234/v1")
    assert result["success"] is False
    assert created and created[0].closed is True


# ---------------------------------------------------------------------------
# 角色卡目录守卫（反路径穿越）：refine_get_template / refine_save_template
# 仅放行 服务端默认目录 或 本会话登记的用户自选目录，其余一律拒绝。
# ---------------------------------------------------------------------------

def test_refine_get_template_rejects_traversal_payload(gui_api_obj):
    """前端传入相对穿越载荷必须在 open() 之前被守卫短路拒绝。"""
    sep = os.sep
    payload = (".." + sep + ".." + sep + "config" + sep
               + ("api_keys" + chr(46) + "bin"))
    result = gui_api_obj.refine_get_template("A", payload)
    assert result["success"] is False


def test_refine_save_template_rejects_abs_beyond_anchor(gui_api_obj):
    """未登记且越出 home/仓库根锚点的绝对路径必须拒绝写入。"""
    outside = os.path.join(os.path.expanduser("~"), os.pardir,
                           os.pardir, "beyond_anchor_cards")
    result = gui_api_obj.refine_save_template("A", "测试内容", outside)
    assert result["success"] is False
    assert not os.path.exists(outside), "守卫应在建目录/写文件之前拒绝"


def test_refine_template_registered_dir_still_works(gui_api_obj):
    """不误伤正常路径：本会话经对话框登记的自选目录读写角色卡仍放行。

    目录锚在用户主目录之下（_resolve_safe_path 的 home 白名单内），
    且测试产物在 finally 中清理，不残留。
    """
    d = Path.home() / ("subtransjav_tpl_test_" + uuid.uuid4().hex[:8])
    register_session_paths([str(d)])
    try:
        saved = gui_api_obj.refine_save_template("A", "卡片内容", str(d))
        assert saved["success"] is True
        loaded = gui_api_obj.refine_get_template("A", str(d))
        assert loaded["success"] is True
        assert loaded["text"] == "卡片内容"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_get_template_default_dir_still_works(gui_api_obj):
    """不误伤主路径：不传目录时走服务端默认 config/templates。"""
    result = gui_api_obj.refine_get_template("A", None)
    assert result["success"] is True


# ---------------------------------------------------------------------------
# 词库保存别名保留（v1.2.2 P2）：GUI 前端只收集两列行，保存时后端必须
# 回填旧库 target_aliases 第三列，不得静默抹掉。词库锚在用户主目录下
# （_resolve_safe_path 的 home 白名单内），测试产物在 finally 中清理。
# ---------------------------------------------------------------------------

def _home_glossary_dir() -> Path:
    d = Path.home() / ("subtransjav_gl_test_" + uuid.uuid4().hex[:8])
    d.mkdir(parents=True, exist_ok=True)
    return d


def test_refine_save_glossary_keeps_existing_aliases(gui_api_obj):
    """旧库含别名：前端传两列行保存后，读回别名仍在第三列。"""
    d = _home_glossary_dir()
    try:
        p = d / "glossary.csv"
        p.write_text("ムラムラ,心痒,燥热|悸动\nIKU,去了\n", encoding="utf-8-sig")
        saved = gui_api_obj.refine_save_glossary(
            [["ムラムラ", "心痒"], ["IKU", "去了"]], str(p))
        assert saved["success"] is True
        assert saved["alias_kept"] == 1          # 仅一条带别名
        got = gui_api_obj.refine_get_glossary(str(p))
        assert got["success"] is True
        assert got["rows"] == [["ムラムラ", "心痒", "燥热|悸动"],
                               ["IKU", "去了", ""]]
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_save_glossary_no_alias_writes_two_columns(gui_api_obj):
    """旧库无别名：保存后 CSV 不出现第三列（learned 行格式不受影响）。"""
    d = _home_glossary_dir()
    try:
        p = d / "glossary.csv"
        p.write_text("こんにちは,你好\n", encoding="utf-8-sig")
        saved = gui_api_obj.refine_save_glossary([["こんにちは", "你好"]], str(p))
        assert saved["success"] is True
        assert saved["alias_kept"] == 0
        assert p.read_text(encoding="utf-8-sig").strip() == "こんにちは,你好"
        got = gui_api_obj.refine_get_glossary(str(p))
        assert got["rows"] == [["こんにちは", "你好", ""]]
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# read_output_artifact：质量报告导读查看器（W1b）
# ---------------------------------------------------------------------------

def test_read_output_artifact_valid_guide(gui_api_obj, tmp_path):
    """合法导读 JSON：success=True 且 data 透传（含 basis 字段）。"""
    p = tmp_path / "EP01_质量报告导读.json"
    p.write_text(
        '{"version":"1.0","source":"a.srt","stem":"EP01",'
        '"generated_at":"2026-09-25T00:00:00","basis":"基于本次运行",'
        '"conclusions":["c1"],"sections":[{"title":"t","note":"n"}],'
        '"companions":{"a.srt":true}}',
        encoding="utf-8",
    )
    got = gui_api_obj.read_output_artifact(str(p))
    assert got["success"] is True
    assert got["data"]["basis"] == "基于本次运行"
    assert got["path"] == str(p)


def test_read_output_artifact_rejects_arbitrary_json(gui_api_obj, tmp_path):
    """非导读后缀的任意 json 一律拒绝（防任意 json 读取）。"""
    p = tmp_path / "other.json"
    p.write_text('{"a":1}', encoding="utf-8")
    got = gui_api_obj.read_output_artifact(str(p))
    assert got["success"] is False
    assert "导读" in got["error"]


def test_read_output_artifact_missing_or_system_path(gui_api_obj, tmp_path):
    """不存在的导读路径与系统目录路径均拒绝。"""
    got = gui_api_obj.read_output_artifact(str(tmp_path / "none_质量报告导读.json"))
    assert got["success"] is False
    assert "不存在" in got["error"]
    import os
    win_root = os.environ.get("SYSTEMROOT", r"C:\Windows")
    bad = gui_api_obj.read_output_artifact(
        os.path.join(win_root, "x_质量报告导读.json"))
    assert bad["success"] is False
    got_empty = gui_api_obj.read_output_artifact("")
    assert got_empty["success"] is False


def test_read_output_artifact_corrupt_json(gui_api_obj, tmp_path):
    """损坏 JSON：报"文件损坏"类错误而非抛异常。"""
    p = tmp_path / "bad_质量报告导读.json"
    p.write_text("{not json", encoding="utf-8")
    got = gui_api_obj.read_output_artifact(str(p))
    assert got["success"] is False
    assert "损坏" in got["error"]


# ---------------------------------------------------------------------------
# C1（D2026-0925-01）：stages[].model 持久化档位（直存直读，不进分层）
# ---------------------------------------------------------------------------
def test_refine_stage_settings_saves_model(gui_api_obj, tmp_path, monkeypatch):
    """保存含 model 的 stages 后，文件与读取接口均回传 model。"""
    path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(path))
    r = gui_api_obj.refine_save_stage_settings(
        stages=[{"stage": 1, "provider": "zen", "endpoint": "https://x",
                 "model": "glm-4"},
                {"stage": 3, "provider": "custom", "endpoint": "https://y",
                 "model": "m2"}],
        settings={"v2_concurrency": 3, "v2_ctx": 16384})
    assert r["success"] is True
    assert r["endpoints_saved"] == 2

    got = gui_api_obj.refine_get_stage_settings()
    assert got["success"] is True
    by_stage = {s.get("stage"): s for s in got["stages"]}
    assert by_stage[1]["model"] == "glm-4"
    assert by_stage[3]["model"] == "m2"
    # settings 键集不变
    assert got["settings"]["v2_concurrency"] == 3
    assert got["settings"]["v2_ctx"] == 16384

    import json
    data = json.loads(path.read_text(encoding="utf-8"))
    assert {s["stage"]: s.get("model") for s in data["stages"]} == \
        {1: "glm-4", 3: "m2"}


def test_refine_stage_settings_model_incremental_merge(gui_api_obj, tmp_path,
                                                       monkeypatch):
    """缺 model 的增量保存不抹掉已有 model；缺省 model 读取不报错。"""
    path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(path))
    r1 = gui_api_obj.refine_save_stage_settings(
        stages=[{"stage": 1, "provider": "zen", "endpoint": "https://x",
                 "model": "glm-4"}])
    assert r1["success"] is True
    r2 = gui_api_obj.refine_save_stage_settings(
        stages=[{"stage": 1, "endpoint": "https://z"}])
    assert r2["success"] is True

    got = gui_api_obj.refine_get_stage_settings()
    entry = next(s for s in got["stages"] if s.get("stage") == 1)
    assert entry["model"] == "glm-4"
    assert entry["endpoint"] == "https://z"


# ---------------------------------------------------------------------------
# A4 首启初始化：refine_get_stage_settings additive first_run 标志
# ---------------------------------------------------------------------------
def test_refine_get_stage_settings_first_run_flag(gui_api_obj, tmp_path,
                                                  monkeypatch):
    """settings 文件不存在 → first_run=True；存在 → False（additive 键）。"""
    path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(path))
    got = gui_api_obj.refine_get_stage_settings()
    assert got["success"] is True
    assert got["first_run"] is True
    path.write_text('{"stages": [], "settings": {"ui_profile": "novice"}}',
                    encoding="utf-8")
    got2 = gui_api_obj.refine_get_stage_settings()
    assert got2["success"] is True
    assert got2["first_run"] is False
    assert got2["settings"]["ui_profile"] == "novice"


# ---------------------------------------------------------------------------
# 2.6.1 修订（D2026-1002-06，模型推荐制+验证可选化）：ASR status 增强
# recommended/models_dir/cache_dir/crosscheck_enabled + 设置 KV 直存
# ---------------------------------------------------------------------------
def test_refine_asr_status_recommended_and_crosscheck(gui_api_obj, tmp_path,
                                                      monkeypatch):
    """status 含 recommended（present/path/expected_path）与两处落位/开关。"""
    from subtransjav.refine import asr_env
    path = tmp_path / "refine_stage_settings.json"
    path.write_text(
        json.dumps({"stages": [], "settings": {
            "media_crosscheck_enabled": "1", "asr_model": "large-v2"}},
                   ensure_ascii=False),
        encoding="utf-8")
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(path))

    def _fake_probe(asr_python_setting=""):
        return {"available": False, "reason": "x",
                "models": [{"name": "large-v2",
                            "path": "C:/cache/large-v2.pt", "bytes": 3}]}

    monkeypatch.setattr(asr_env, "probe_asr_env", _fake_probe)
    # 2.7.1：探测快照缓存路径隔离（防写真实数据根）
    monkeypatch.setattr(gui_api_obj, "_asr_probe_cache_path",
                        lambda: str(tmp_path / "asr_probe_cache.json"))
    r = gui_api_obj.refine_asr_status()
    assert r["success"] is True
    recs = {e["name"]: e for e in r["recommended"]}
    w = recs["whisper-large-v2"]
    assert w["present"] is True
    assert w["path"] == "C:/cache/large-v2.pt"
    assert w["expected_path"] == os.path.join(asr_env.ASR_MODELS_ROOT,
                                              "large-v2.pt")
    q = recs["qwen3-asr-1.7b"]
    assert q["present"] is False and q["support"] == "planned"
    assert r["models_dir"] == asr_env.ASR_MODELS_ROOT
    assert r["cache_dir"] == asr_env.ASR_CACHE_DIR
    assert r["crosscheck_enabled"] is True


def test_refine_asr_status_crosscheck_default_false(gui_api_obj, tmp_path,
                                                    monkeypatch):
    """KV 无 media_crosscheck_enabled → crosscheck_enabled=False（默认关）。"""
    from subtransjav.refine import asr_env
    path = tmp_path / "refine_stage_settings.json"
    path.write_text('{"stages": [], "settings": {}}', encoding="utf-8")
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(path))
    monkeypatch.setattr(asr_env, "probe_asr_env",
                        lambda asr_python_setting="": {"models": []})
    monkeypatch.setattr(gui_api_obj, "_asr_probe_cache_path",
                        lambda: str(tmp_path / "asr_probe_cache.json"))
    r = gui_api_obj.refine_asr_status()
    assert r["success"] is True
    assert r["crosscheck_enabled"] is False


def test_refine_stage_settings_accepts_media_crosscheck(gui_api_obj, tmp_path,
                                                        monkeypatch):
    """save 接受 media_crosscheck_enabled（存 "1"/"0" 惯例）并原样读回。"""
    path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(path))
    r = gui_api_obj.refine_save_stage_settings(
        settings={"media_crosscheck_enabled": "0"})
    assert r["success"] is True and r["settings_saved"] == 1
    got = gui_api_obj.refine_get_stage_settings()
    assert got["settings"]["media_crosscheck_enabled"] == "0"


# ---------------------------------------------------------------------------
# cancel_translation 运行态契约（M3）：
# - 哨兵期（Popen 未完成）取消返回 success=False，由前端保持运行态；
# - 击杀成功后 cancelled 状态才置位；击杀抛异常时状态/句柄原样保留
#   （进程实际仍在运行，轮询继续收尾）。
# ---------------------------------------------------------------------------

def _manual_state_api(gui_api_obj):
    import threading
    gui_api_obj._translate_lock = threading.Lock()
    gui_api_obj._init_translation_state()
    return gui_api_obj


def test_cancel_translation_sentinel_period_returns_failure(gui_api_obj):
    """启动哨兵期取消：返回失败且状态/句柄原样保留。

    契约钉：前端 cancelTranslation 依赖此 success=False 保持运行态
    继续轮询，不得视作已取消。
    """
    api = _manual_state_api(gui_api_obj)
    api._translate_process = True
    result = api.cancel_translation()
    assert result["success"] is False
    assert api._translate_process is True
    assert api._translate_status != "cancelled"


def test_cancel_translation_success_sets_cancelled_after_kill(
        gui_api_obj, monkeypatch):
    """击杀成功路径：cancelled 状态在击杀完成之后置位，句柄清空。"""
    import subtransjav.webview_gui.api as api_mod
    api = _manual_state_api(gui_api_obj)

    class _FakeProc:
        pid = 424242

        def wait(self, timeout=None):
            return 0

    proc = _FakeProc()
    api._translate_process = proc
    api._translate_status = "running"
    monkeypatch.setattr(api_mod, "PSUTIL_AVAILABLE", True)
    monkeypatch.setattr(api_mod, "terminate_process_tree",
                        lambda pid: {"success": True})

    result = api.cancel_translation()
    assert result["success"] is True
    assert api._translate_status == "cancelled"
    assert api._translate_process is None


def test_cancel_translation_kill_failure_keeps_running_state(
        gui_api_obj, monkeypatch):
    """击杀抛异常：不得置 cancelled，进程句柄保留（进程仍在运行）。"""
    import subtransjav.webview_gui.api as api_mod
    api = _manual_state_api(gui_api_obj)

    class _UnkillableProc:
        pid = 424242

    proc = _UnkillableProc()
    api._translate_process = proc
    api._translate_status = "running"

    def _boom(pid):
        raise RuntimeError("terminate failed")

    monkeypatch.setattr(api_mod, "PSUTIL_AVAILABLE", True)
    monkeypatch.setattr(api_mod, "terminate_process_tree", _boom)

    result = api.cancel_translation()
    assert result["success"] is False
    assert api._translate_status != "cancelled"
    assert api._translate_process is proc


# ---------------------------------------------------------------------------
# TM db_path 锚点校验（M4）：四个 TM 接口的 db_path 与同函数导出/导入
# path 同过 _resolve_safe_path，且拒绝必须发生在 TranslationMemory
# 构造（makedirs + sqlite 建库）之前。
# ---------------------------------------------------------------------------

_OUTSIDE_DB = os.path.join(os.path.expanduser("~"), os.pardir, os.pardir,
                           "beyond_anchor_tm.db")


def _install_fake_tm(monkeypatch):
    """替身 TranslationMemory：记录构造参数，杜绝测试触碰真实 sqlite。"""
    import subtransjav.refine.tm as tm_mod
    constructed: list = []

    class _FakeTM:
        def __init__(self, db_path=None):
            constructed.append(db_path)

        def stats(self):
            return {"entries": 1}

        def clear(self, stage):
            return None

        def export_csv(self, path, stage):
            return None

        def import_csv(self, path):
            return 0

        def close(self):
            return None

    monkeypatch.setattr(tm_mod, "TranslationMemory", _FakeTM)
    return constructed


@pytest.mark.parametrize("method", ["tm_get_stats", "tm_clear",
                                    "tm_export_csv", "tm_import_csv"])
def test_tm_db_path_outside_anchor_rejected(gui_api_obj, monkeypatch,
                                            tmp_path, method):
    """越锚 db_path 必须被拒，且不触碰 TranslationMemory。"""
    constructed = _install_fake_tm(monkeypatch)
    kwargs = {"db_path": _OUTSIDE_DB}
    if method == "tm_export_csv":
        kwargs["path"] = str(tmp_path / "export.csv")
    elif method == "tm_import_csv":
        kwargs["path"] = str(tmp_path / "import.csv")
    result = getattr(gui_api_obj, method)(**kwargs)
    assert result["success"] is False
    assert "路径不在允许的目录下" in result["error"]
    assert constructed == [], "拒绝必须发生在建库之前"


@pytest.mark.parametrize("method", ["tm_get_stats", "tm_clear",
                                    "tm_export_csv", "tm_import_csv"])
def test_tm_db_path_within_anchor_passthrough(gui_api_obj, monkeypatch,
                                              tmp_path, method):
    """锚内 db_path 照常透传（守卫不误伤正常路径）。"""
    constructed = _install_fake_tm(monkeypatch)
    db = tmp_path / "ok.db"
    kwargs = {"db_path": str(db)}
    if method == "tm_export_csv":
        kwargs["path"] = str(tmp_path / "export.csv")
    elif method == "tm_import_csv":
        kwargs["path"] = str(tmp_path / "import.csv")
    result = getattr(gui_api_obj, method)(**kwargs)
    assert result["success"] is True
    assert constructed == [str(db)]


# ---------------------------------------------------------------------------
# start_translation 日志队列（L2）：启动必须清空上轮残留，
# 否则上一轮未排干的日志（含 [CANCELLED]）混入新一轮。
# ---------------------------------------------------------------------------

def test_start_translation_drains_stale_log_queue(gui_api_obj, monkeypatch):
    """连续两轮启动：上轮残留日志（含 [CANCELLED]）不得混入新一轮。"""
    captured = {}
    _capture_popen(monkeypatch, captured, gui_api_obj)
    gui_api_obj._init_translation_state()
    for round_no in (1, 2):
        gui_api_obj._translate_log_queue.put(f"leftover-{round_no}\n")
        gui_api_obj._translate_log_queue.put(
            f"\n[CANCELLED] stale-round-{round_no}\n")
        gui_api_obj.start_translation({"inputs": ["a.srt"], "force": True})
        residue = []
        while not gui_api_obj._translate_log_queue.empty():
            residue.append(gui_api_obj._translate_log_queue.get_nowait())
        assert residue == [], f"第 {round_no} 轮启动后残留上轮日志: {residue}"

# ---------------------------------------------------------------------------
# AI 质量分析（D2026-0929：--ai-analyze 前后端接入）
# ---------------------------------------------------------------------------

_AI_REPORT_STEM = "ep01"
_AI_SUGGESTIONS = {
    "glossary": [{"src": "気持ちよさそう", "target": "看起来很爽",
                  "reason": "全片统一"}],
    "tm": [{"source": "先生、だめです", "target": "老师，不行的",
            "reason": "高频句式"}],
    "observations": ["整体节奏良好"],
}


def _make_ai_report(tmp_path: Path, with_companion: bool = True) -> Path:
    """落一份 _质量报告.txt（可选伴生 _AI质量建议.json）供分析接口消费。"""
    report = tmp_path / f"{_AI_REPORT_STEM}_质量报告.txt"
    report.write_text("【结论】正常\n", encoding="utf-8")
    if with_companion:
        (tmp_path / f"{_AI_REPORT_STEM}_AI质量建议.json").write_text(
            json.dumps({"model": "m", "parse_ok": True,
                        "suggestions": _AI_SUGGESTIONS},
                       ensure_ascii=False),
            encoding="utf-8")
    return report


def _install_fake_stage_settings(gui_api_obj, monkeypatch,
                                 provider="deepseek", endpoint=""):
    """替身 refine_get_stage_settings：不触碰真实 config/refine_stage_settings.json。"""
    monkeypatch.setattr(
        gui_api_obj, "refine_get_stage_settings",
        lambda: {"success": True,
                 "stages": [{"stage": 1, "provider": provider,
                             "endpoint": endpoint}],
                 "settings": {}, "key_status": {}, "first_run": False})


class _FakeAnalyzeProc:
    """替身分析子进程（批4：分析链改 Popen+communicate 可取消形态）。

    communicate 记录超时实参（timeout 语义自 spawn 迁至 communicate，
    形状钉消费）；raise_timeout 模拟 communicate 超时。"""

    def __init__(self, returncode=0, stdout="", stderr="",
                 raise_timeout=False):
        self.pid = 424242
        self.returncode = None
        self._rc = returncode
        self._stdout = stdout
        self._stderr = stderr
        self._raise_timeout = raise_timeout
        self.timeout_seen = None

    def communicate(self, timeout=None):
        self.timeout_seen = timeout
        if self._raise_timeout:
            raise subprocess.TimeoutExpired(cmd=["ai-analyze"],
                                            timeout=timeout or 0)
        self.returncode = self._rc
        return self._stdout, self._stderr

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        pass


def _install_fake_ai_run(monkeypatch, *, returncode=0, stderr="",
                         raise_timeout=False):
    """替身 spawn_refine_cli（分析链）：捕获 CLI 参数与 spawn 环境，
    杜绝真实子进程。批4 起分析链改 Popen+communicate，替身自
    subprocess.run 捕获同步迁移（args/kwargs 捕获语义不变）。"""
    import subtransjav.webview_gui.api as api_mod
    captured: dict = {}
    procs: list[_FakeAnalyzeProc] = []

    def _fake_spawn(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        proc = _FakeAnalyzeProc(returncode=returncode, stderr=stderr,
                                raise_timeout=raise_timeout)
        procs.append(proc)
        return proc

    monkeypatch.setattr(api_mod, "spawn_refine_cli", _fake_spawn)
    captured["proc"] = lambda: procs[0] if procs else None
    return captured


def test_refine_ai_analyze_success(gui_api_obj, monkeypatch, tmp_path):
    """成功路径：CLI 参数/超时/cwd 正确，读回建议件并带 provider 名。"""
    report = _make_ai_report(tmp_path)
    _install_fake_stage_settings(gui_api_obj, monkeypatch, provider="zen")
    captured = _install_fake_ai_run(monkeypatch, stderr="warn-tail\n")

    r = gui_api_obj.refine_ai_analyze(str(report))
    assert r["success"] is True
    assert r["parse_ok"] is True
    assert r["suggestions"] == _AI_SUGGESTIONS
    assert r["provider_name"] == "zen"
    assert r["companion_path"].endswith(
        f"{_AI_REPORT_STEM}_AI质量建议.json")
    assert "warn-tail" in r["stderr_tail"]

    args = captured["args"]
    assert "--ai-analyze" in args
    assert args[args.index("--ai-analyze") + 1] == str(report)
    assert "--ai-model" not in args, "model 缺省不得传空 --ai-model"
    # F1：分析子进程跟随阶段A 服务商（fake 存储 provider=zen）
    assert args[args.index("--s1-provider") + 1] == "zen"
    kw = captured["kwargs"]
    # 批4：超时语义自 spawn kwargs 迁至 communicate(timeout)（可取消形态）
    assert "timeout" not in kw
    assert captured["proc"]().timeout_seen == 600
    assert kw.get("cwd") == str(REPO_ROOT)
    assert kw.get("encoding") == "utf-8"


def test_refine_ai_analyze_model_passthrough(gui_api_obj, monkeypatch,
                                             tmp_path):
    """显式 model → 追加 --ai-model <m>。"""
    report = _make_ai_report(tmp_path)
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    captured = _install_fake_ai_run(monkeypatch)
    r = gui_api_obj.refine_ai_analyze(str(report), model="glm-4")
    assert r["success"] is True
    args = captured["args"]
    assert args[args.index("--ai-model") + 1] == "glm-4"


def _install_fake_secret(monkeypatch, stored=("deepseek",)):
    """替身 DPAPI read_secret：仅 stored 中 provider 返回假密钥。"""
    import subtransjav.refine.secrets as secrets_mod
    monkeypatch.setattr(
        secrets_mod, "read_secret",
        lambda name, store_path=None: "sk-fake" if name in stored else "")


def test_refine_ai_analyze_follows_stage_a_endpoint(gui_api_obj,
                                                    monkeypatch, tmp_path):
    """F1：阶段A 存储 endpoint → 子进程 argv 带 --<provider>-endpoint。"""
    report = _make_ai_report(tmp_path)
    _install_fake_stage_settings(
        gui_api_obj, monkeypatch, provider="siliconflow",
        endpoint="https://api.siliconflow.cn/v1")
    _install_fake_secret(monkeypatch, stored=("siliconflow",))
    captured = _install_fake_ai_run(monkeypatch)
    r = gui_api_obj.refine_ai_analyze(str(report))
    assert r["success"] is True
    args = captured["args"]
    assert args[args.index("--s1-provider") + 1] == "siliconflow"
    assert args[args.index("--siliconflow-endpoint") + 1] == \
        "https://api.siliconflow.cn/v1"
    # 批4：捕获点自 subprocess.run（env 已合并）迁至 spawn_refine_cli
    #（env_extra 差异项），密钥最终经 _utf8_child_env 合并进子进程 env
    env = captured["kwargs"].get("env_extra") or {}
    assert env.get("SILICONFLOW_API_KEY") == "sk-fake"
    # 密钥不写命令行
    assert all("sk-fake" not in str(a) for a in args)


def test_refine_ai_analyze_deepseek_key_env(gui_api_obj, monkeypatch,
                                            tmp_path):
    """F1：deepseek 已存密钥 → env 注入 DEEPSEEK_API_KEY（不落 argv）。"""
    report = _make_ai_report(tmp_path)
    _install_fake_stage_settings(gui_api_obj, monkeypatch, provider="deepseek")
    _install_fake_secret(monkeypatch, stored=("deepseek",))
    captured = _install_fake_ai_run(monkeypatch)
    r = gui_api_obj.refine_ai_analyze(str(report))
    assert r["success"] is True
    env = captured["kwargs"].get("env_extra") or {}
    assert env.get("DEEPSEEK_API_KEY") == "sk-fake"
    assert all("sk-fake" not in str(a) for a in captured["args"])


def test_refine_ai_analyze_local_provider_no_key_env(gui_api_obj,
                                                     monkeypatch, tmp_path):
    """F1：本地 provider（lmstudio）→ 不注入密钥 env，端点跟随存储。"""
    report = _make_ai_report(tmp_path)
    _install_fake_stage_settings(
        gui_api_obj, monkeypatch, provider="lmstudio",
        endpoint="http://localhost:1234/v1")
    _install_fake_secret(monkeypatch, stored=("deepseek", "zen",
                                              "siliconflow", "custom"))
    captured = _install_fake_ai_run(monkeypatch)
    r = gui_api_obj.refine_ai_analyze(str(report))
    assert r["success"] is True
    args = captured["args"]
    assert args[args.index("--s1-provider") + 1] == "lmstudio"
    assert args[args.index("--lmstudio-endpoint") + 1] == \
        "http://localhost:1234/v1"
    env = captured["kwargs"].get("env_extra") or {}
    for var in ("DEEPSEEK_API_KEY", "OPENCODE_API_KEY",
                "SILICONFLOW_API_KEY", "CUSTOM_API_KEY"):
        assert var not in env, f"本地 provider 不得注入 {var}"


def test_refine_ai_analyze_nonzero_exit(gui_api_obj, monkeypatch, tmp_path):
    """非零退出 → success=False，stderr 尾部随行返回。"""
    report = _make_ai_report(tmp_path, with_companion=False)
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    _install_fake_ai_run(monkeypatch, returncode=1,
                         stderr="boom-line1\nboom-line2\n")
    r = gui_api_obj.refine_ai_analyze(str(report))
    assert r["success"] is False
    assert "boom-line2" in r["stderr_tail"]


def test_refine_ai_analyze_timeout(gui_api_obj, monkeypatch, tmp_path):
    """超时 → success=False 且错误含超时语义。"""
    report = _make_ai_report(tmp_path)
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    _install_fake_ai_run(monkeypatch, raise_timeout=True)
    r = gui_api_obj.refine_ai_analyze(str(report))
    assert r["success"] is False
    assert "超时" in r["error"]


def test_refine_ai_analyze_rejects_non_report_and_missing(
        gui_api_obj, monkeypatch, tmp_path):
    """非 _质量报告.txt 后缀 / 路径不存在 → 前置拒绝，不触 subprocess。"""
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    captured = _install_fake_ai_run(monkeypatch)
    other = tmp_path / "ep01.txt"
    other.write_text("x", encoding="utf-8")
    r1 = gui_api_obj.refine_ai_analyze(str(other))
    assert r1["success"] is False and "质量报告" in r1["error"]
    r2 = gui_api_obj.refine_ai_analyze(
        str(tmp_path / "不存在_质量报告.txt"))
    assert r2["success"] is False
    r3 = gui_api_obj.refine_ai_analyze("")
    assert r3["success"] is False
    # 批4：捕获点改 spawn_refine_cli——"args" 缺席即未触达 spawn
    assert "args" not in captured, "前置拒绝必须发生在 spawn 之前"


def test_refine_ai_analyze_user_directory_guard_differential(
        gui_api_obj, monkeypatch, tmp_path):
    """修复B（D2026-1001-06）守卫差分回归四断言：
    _resolve_safe_path（home/仓库根白名单）→ _validate_user_directory
    （任意用户磁盘目录、拦系统目录+可执行；后缀白名单保留）。

    方案（二级评议 C5）：monkeypatch security.Path.home 与 api.REPO_ROOT
    至不含测试路径的假目录——tmp_path 在假 home 外，修复前会被
    _resolve_safe_path 拒绝，修复后必须放行。
    """
    import subtransjav.webview_gui.api as api_mod
    import subtransjav.webview_gui.security as security_mod

    fake_home = tmp_path / "fakehome"
    fake_home.mkdir()
    monkeypatch.setattr(security_mod.Path, "home", lambda: fake_home)
    monkeypatch.setattr(api_mod, "REPO_ROOT", str(tmp_path / "fakerepo"))
    _install_fake_stage_settings(gui_api_obj, monkeypatch)

    # 断言①home 外路径被接受：tmp_path 既不在假 home 也不在假 REPO_ROOT 下，
    # 走 _validate_user_directory 放行 → 抵达 subprocess（fake run returncode=1
    # 的确定性失败，证明守卫已过、非路径拒绝）
    report = _make_ai_report(tmp_path, with_companion=False)
    captured = _install_fake_ai_run(monkeypatch, returncode=1,
                                    stderr="boom-line1\nboom-line2\n")
    r_ok = gui_api_obj.refine_ai_analyze(str(report))
    assert r_ok["success"] is False
    assert "不允许" not in r_ok["error"] and "允许范围" not in r_ok["error"], \
        f"home 外用户目录被误拒：{r_ok['error']}"
    assert "exit_code" in r_ok["error"] or r_ok.get("stderr_tail"), \
        "应抵达 subprocess 阶段（守卫放行）"
    assert captured.get("args"), "放行路径必须触达 fake subprocess"

    # 断言②系统目录拒：SystemRoot 下（守卫先行，不触 subprocess）
    system_root = os.environ.get("SystemRoot", r"C:\Windows")  # noqa: SIM112 - 与 security.py 同口径
    r_sys = gui_api_obj.refine_ai_analyze(
        os.path.join(system_root, "fake_ep01_质量报告.txt"))
    assert r_sys["success"] is False and "允许范围" in r_sys["error"]

    # 断言③可执行拒：真实存在的 .exe 文件（守卫在 isfile/后缀检查前拒绝）
    exe = tmp_path / "fake_质量报告.txt.exe"
    exe.write_bytes(b"MZ")
    r_exe = gui_api_obj.refine_ai_analyze(str(exe))
    assert r_exe["success"] is False and "允许范围" in r_exe["error"]

    # 断言④前置拒绝 captured：两拒绝路径均未触 subprocess（先清①的基线）
    captured.clear()
    gui_api_obj.refine_ai_analyze(
        os.path.join(system_root, "fake_ep01_质量报告.txt"))
    gui_api_obj.refine_ai_analyze(str(exe))
    # 批4：捕获点改 spawn_refine_cli——"args" 缺席即未触达 spawn
    assert "args" not in captured, "拒绝路径不得触达 spawn"


def test_refine_ai_analyze_companion_missing(gui_api_obj, monkeypatch,
                                             tmp_path):
    """CLI 退出 0 但建议件未落盘 → success=False。"""
    report = _make_ai_report(tmp_path, with_companion=False)
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    _install_fake_ai_run(monkeypatch)
    r = gui_api_obj.refine_ai_analyze(str(report))
    assert r["success"] is False
    assert "建议件" in r["error"]


def test_refine_ai_analyze_parse_failed_degraded(gui_api_obj, monkeypatch,
                                                 tmp_path):
    """parse_ok=False 的降级建议件：原样透传，前端按纯文本降级展示。"""
    report = tmp_path / f"{_AI_REPORT_STEM}_质量报告.txt"
    report.write_text("【结论】x\n", encoding="utf-8")
    (tmp_path / f"{_AI_REPORT_STEM}_AI质量建议.json").write_text(
        json.dumps({"model": "m", "parse_ok": False,
                    "suggestions": {"glossary": [], "tm": [],
                                    "observations": ["原始文本"]}},
                   ensure_ascii=False),
        encoding="utf-8")
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    _install_fake_ai_run(monkeypatch)
    r = gui_api_obj.refine_ai_analyze(str(report))
    assert r["success"] is True
    assert r["parse_ok"] is False
    assert r["suggestions"]["observations"] == ["原始文本"]


# ---------------------------------------------------------------------------
# 批4（D2026-1008-01）：AI 分析/一键修复可停止 + 登记治理 + 启动自愈。
# 真子进程以 ``sys.executable -c "import time; time.sleep(30)"`` 制造
# （-c 串尾注释携带 "subtransjav <kind 旗标>"，cmdline 身份核验第③重
# 可命中的最小真实载体）；finally 全量兜底回收，防测试进程外泄。
# ---------------------------------------------------------------------------

def _spawn_marker_proc(marker: str, **popen_kw) -> subprocess.Popen:
    """起一个安静长睡的真子进程（cmdline 含项目标记与 kind 旗标）。"""
    kw = dict(stdout=subprocess.PIPE, stderr=subprocess.PIPE,
              text=True, encoding="utf-8", errors="replace")
    kw.update(popen_kw)
    proc = subprocess.Popen(
        [sys.executable, "-c",
         f"import time; time.sleep(30)  # subtransjav {marker}"], **kw)
    _wait_proc_alive(proc)
    return proc


def _wait_proc_alive(proc: subprocess.Popen, timeout: float = 10.0) -> None:
    """等待子进程完全就绪（psutil 可查询 create_time/cmdline）。"""
    import psutil
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            psutil.Process(proc.pid).create_time()
            return
        except psutil.Error:
            pass
        if proc.poll() is not None:
            raise AssertionError("子进程提前退出，测试环境异常")
        time.sleep(0.05)
    raise AssertionError("子进程未在超时内进入存活状态")


def _wait_dead(proc: subprocess.Popen, timeout: float = 10.0) -> None:
    """断言子进程在短窗口内退出（防取消链退化成只登记不杀）。"""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if proc.poll() is not None:
            return
        time.sleep(0.05)
    raise AssertionError("子进程未在超时窗口内退出")


def _ensure_reaped(proc: subprocess.Popen) -> None:
    """兜底清理：整树击杀 + 回收（照 test_process_manager 先例防外泄）。"""
    try:
        import psutil
        for child in psutil.Process(proc.pid).children(recursive=True):
            with contextlib.suppress(Exception):
                child.kill()
    except Exception:
        pass
    try:
        if proc.poll() is None:
            proc.kill()
        proc.wait(timeout=10)
    except Exception:
        pass


def _install_real_sleep_spawn(monkeypatch, marker: str = "--ai-analyze"):
    """替身 spawn_refine_cli：返回真长睡子进程（登记/取消链全真实）。"""
    import subtransjav.webview_gui.api as api_mod
    procs: list[subprocess.Popen] = []

    def _fake_spawn(args, **kwargs):
        proc = _spawn_marker_proc(marker)
        procs.append(proc)
        return proc

    monkeypatch.setattr(api_mod, "spawn_refine_cli", _fake_spawn)
    return procs


def _start_analyze_thread(gui_api_obj, report_path: Path, box: dict):
    th = threading.Thread(
        target=lambda: box.update(
            gui_api_obj.refine_ai_analyze(str(report_path))),
        daemon=True)
    th.start()
    return th


def _wait_registered(gui_api_obj, attr: str = "_ai_analyze_proc",
                     timeout: float = 10.0) -> dict:
    """等待登记槽出现（spawn+注册完成；上限保护防 CI 挂死）。"""
    gui_api_obj._init_ai_state()
    deadline = time.time() + timeout
    while time.time() < deadline:
        entry = getattr(gui_api_obj, attr)
        if entry is not None:
            return entry
        time.sleep(0.05)
    raise AssertionError(f"登记槽 {attr} 未在超时内出现")


def test_ai_analyze_cancel_kills_proc_and_reports_cancelled(
        gui_api_obj, monkeypatch, tmp_path):
    """取消链全真实：取消桥 → 身份核验树杀 → cancelled 结果 + 进程短窗
    退出 + 登记/台账收尾。"""
    import subtransjav.webview_gui.api as api_mod
    report = _make_ai_report(tmp_path, with_companion=False)
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    procs = _install_real_sleep_spawn(monkeypatch)
    box: dict = {}
    th = _start_analyze_thread(gui_api_obj, report, box)
    try:
        entry = _wait_registered(gui_api_obj)
        assert entry["pid"] == procs[0].pid
        rc = gui_api_obj.refine_cancel_ai_analyze()
        assert rc.get("success") is True and rc.get("cancelled") is True
        th.join(timeout=20)
        assert not th.is_alive(), "refine_ai_analyze 未在取消后及时返回"
        assert box.get("success") is False and box.get("cancelled") is True
        _wait_dead(procs[0], timeout=10)
        # reap：登记槽清位 + 台账条目移除（覆盖式写=空快照）
        assert gui_api_obj._ai_analyze_proc is None
        assert api_mod._ledger_read_entries(
            api_mod._child_procs_ledger_path()) == []
    finally:
        for p in procs:
            _ensure_reaped(p)


def test_ai_analyze_single_flight_refuses_second_call(
        gui_api_obj, monkeypatch, tmp_path):
    """单飞守卫：分析进行中二次调用 → 人话拒绝且不再 spawn。"""
    report = _make_ai_report(tmp_path, with_companion=False)
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    procs = _install_real_sleep_spawn(monkeypatch)
    box: dict = {}
    th = _start_analyze_thread(gui_api_obj, report, box)
    try:
        _wait_registered(gui_api_obj)
        r2 = gui_api_obj.refine_ai_analyze(str(report))
        assert r2["success"] is False
        assert "进行中" in r2["error"]
        assert len(procs) == 1, "单飞拒绝必须发生在 spawn 之前"
    finally:
        gui_api_obj.refine_cancel_ai_analyze()
        th.join(timeout=20)
        for p in procs:
            _ensure_reaped(p)


def test_ai_analyze_cancel_latch_blocks_spawn_before_start(
        gui_api_obj, monkeypatch, tmp_path):
    """取消竞态（用户秒点停止）：spawn 前置闩 → 不 spawn 直接 cancelled，
    闩一次性消费（后续调用不再被拦）。"""
    report = _make_ai_report(tmp_path, with_companion=False)
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    procs = _install_real_sleep_spawn(monkeypatch)
    try:
        gui_api_obj._init_ai_state()
        # 未 spawn 前先调取消（此刻槽为空）→ 置闩
        r0 = gui_api_obj.refine_cancel_ai_analyze()
        assert r0.get("success") is True
        assert r0.get("cancelled_pending") is True
        r = gui_api_obj.refine_ai_analyze(str(report))
        assert r["success"] is False and r.get("cancelled") is True
        assert procs == [], "置闩状态下不得 spawn"
        assert not gui_api_obj._ai_analyze_cancel.is_set(), \
            "闩应一次性消费"
    finally:
        for p in procs:
            _ensure_reaped(p)


def test_terminate_registered_kills_matching_entry():
    """身份核验命中：create_time/cmdline 全匹配 → 真实整树击杀。"""
    import psutil

    import subtransjav.webview_gui.api as api_mod
    proc = _spawn_marker_proc("--ai-analyze")
    try:
        entry = {"proc": proc, "pid": proc.pid,
                 "create_time": psutil.Process(proc.pid).create_time(),
                 "kind": "ai_analyze", "marker": "--ai-analyze"}
        r = api_mod.terminate_registered(entry)
        assert r["success"] is True and r["skipped"] is False
        _wait_dead(proc, timeout=10)
    finally:
        _ensure_reaped(proc)


def test_terminate_registered_skips_on_create_time_mismatch():
    """身份核验不命中（create_time 与登记不符，疑似 PID 复用）→ 不杀、
    只报 skipped 原因。"""
    import psutil

    import subtransjav.webview_gui.api as api_mod
    proc = _spawn_marker_proc("--ai-analyze")
    try:
        entry = {"proc": proc, "pid": proc.pid,
                 "create_time": psutil.Process(proc.pid).create_time() - 999,
                 "kind": "ai_analyze", "marker": "--ai-analyze"}
        r = api_mod.terminate_registered(entry)
        assert r["success"] is False and r["skipped"] is True
        assert "create_time" in r["reason"]
        assert proc.poll() is None, "核验不命中不得误杀"
    finally:
        _ensure_reaped(proc)


def test_child_ledger_write_on_register_and_remove_on_reap(
        gui_api_obj, monkeypatch, tmp_path):
    """台账契约：spawn 登记 → 覆盖写条目（pid/create_time/kind/marker）；
    正常 reap → 条目移除。"""
    import psutil

    import subtransjav.webview_gui.api as api_mod
    report = _make_ai_report(tmp_path, with_companion=False)
    _install_fake_stage_settings(gui_api_obj, monkeypatch)
    procs = _install_real_sleep_spawn(monkeypatch)
    box: dict = {}
    th = _start_analyze_thread(gui_api_obj, report, box)
    try:
        _wait_registered(gui_api_obj)
        path = api_mod._child_procs_ledger_path()
        # 台账写在登记槽置位之后（同线程次序），短窗轮询等落盘
        entries: list = []
        deadline = time.time() + 5
        while time.time() < deadline:
            entries = api_mod._ledger_read_entries(path)
            if entries:
                break
            time.sleep(0.05)
        assert len(entries) == 1
        e = entries[0]
        assert e["pid"] == procs[0].pid
        assert e["kind"] == "ai_analyze" and e["marker"] == "--ai-analyze"
        assert abs(e["create_time"]
                   - psutil.Process(procs[0].pid).create_time()) < 1.5
        # 正常 reap（此处以取消驱动收尾）→ 条目移除
        gui_api_obj.refine_cancel_ai_analyze()
        th.join(timeout=20)
        assert api_mod._ledger_read_entries(path) == []
    finally:
        for p in procs:
            _ensure_reaped(p)


def test_selfheal_kills_matching_ledger_entries(gui_api_obj):
    """启动自愈：台账条目（活进程+marker+create_time 匹配且早于本次启动）
    → 树杀 + gui.log 一行 + 台账写空。"""
    import psutil

    import subtransjav.webview_gui.api as api_mod
    proc = _spawn_marker_proc("--ai-analyze")
    try:
        path = api_mod._child_procs_ledger_path()
        api_mod._ledger_write_entries(path, [{
            "pid": proc.pid,
            "create_time": psutil.Process(proc.pid).create_time(),
            "kind": "ai_analyze", "marker": "--ai-analyze"}])
        gui_api_obj._selfheal_stale_children()
        _wait_dead(proc, timeout=10)
        assert api_mod._ledger_read_entries(path) == []
    finally:
        _ensure_reaped(proc)


def test_selfheal_skips_mismatched_ledger_entries(gui_api_obj):
    """自愈防误杀：create_time 与登记不符（疑似 PID 复用）→ 跳过不杀；
    台账仍写空。"""
    import psutil

    import subtransjav.webview_gui.api as api_mod
    proc = _spawn_marker_proc("--ai-analyze")
    try:
        path = api_mod._child_procs_ledger_path()
        api_mod._ledger_write_entries(path, [{
            "pid": proc.pid,
            "create_time": psutil.Process(proc.pid).create_time() + 999,
            "kind": "ai_analyze", "marker": "--ai-analyze"}])
        gui_api_obj._selfheal_stale_children()
        time.sleep(0.3)
        assert proc.poll() is None, "核验不命中不得误杀"
        assert api_mod._ledger_read_entries(path) == []
    finally:
        _ensure_reaped(proc)


def test_on_exit_cleanup_covers_all_three_slots(gui_api_obj):
    """退出清理全覆盖：translate 走原分支（含 True 哨兵语义零变化）、
    分析/修复槽走 terminate_registered；三进程全退出 + 台账清空。"""
    gui_api_obj._translate_lock = threading.Lock()
    gui_api_obj._init_translation_state()
    gui_api_obj._init_ai_state()
    tp = _spawn_marker_proc("translate-slot")     # 原分支不核验 cmdline
    ai = _spawn_marker_proc("--ai-analyze")
    bf = _spawn_marker_proc("--action-retranslate")
    try:
        gui_api_obj._translate_process = tp
        gui_api_obj._register_child(ai, "ai_analyze")
        gui_api_obj._register_child(bf, "batch_fix")
        gui_api_obj._on_exit_cleanup()
        for p in (tp, ai, bf):
            _wait_dead(p, timeout=10)
        assert gui_api_obj._translate_process is None
        assert gui_api_obj._ai_analyze_proc is None
        assert gui_api_obj._batch_fix_proc is None
        import subtransjav.webview_gui.api as api_mod
        assert api_mod._ledger_read_entries(
            api_mod._child_procs_ledger_path()) == []
        # _translate 哨兵语义零变化：True 哨兵被忽略且被清位（不炸）
        gui_api_obj._translate_process = True
        gui_api_obj._on_exit_cleanup()
        assert gui_api_obj._translate_process is None
    finally:
        for p in (tp, ai, bf):
            _ensure_reaped(p)


def test_batch_fix_cancel_reports_cancelled_and_skips_verify(
        gui_api_obj, monkeypatch, tmp_path):
    """修复链取消：取消桥树杀执行器 → cancelled 结果，且绝不自动复跑
    AI 分析（verify 键不得出现）。"""
    import subtransjav.webview_gui.api as api_mod
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    _install_fake_secret(monkeypatch, stored=("deepseek",))
    procs: list[subprocess.Popen] = []

    def _fake_spawn(args, **kwargs):
        proc = _spawn_marker_proc("--action-retranslate")
        procs.append(proc)
        return proc

    monkeypatch.setattr(api_mod, "spawn_refine_cli", _fake_spawn)
    box: dict = {}
    th = threading.Thread(target=lambda: box.update(
        gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")), daemon=True)
    th.start()
    try:
        _wait_registered(gui_api_obj, attr="_batch_fix_proc")
        rc = gui_api_obj.refine_cancel_batch_fix()
        assert rc.get("success") is True and rc.get("cancelled") is True
        th.join(timeout=20)
        assert not th.is_alive(), "refine_batch_fix 未在取消后及时返回"
        assert box.get("success") is False and box.get("cancelled") is True
        assert "verify" not in box, "取消后不得自动复跑 AI 分析"
        _wait_dead(procs[0], timeout=10)
        assert gui_api_obj._batch_fix_proc is None
    finally:
        for p in procs:
            _ensure_reaped(p)


def test_refine_ai_apply_glossary_passes_entries(gui_api_obj, monkeypatch,
                                                 tmp_path):
    """词库追加：走 config.default_glossary_path 同源路径 + 逐条状态回传。"""
    import subtransjav.refine.config as cfg_mod
    import subtransjav.refine.glossary as gl_mod
    gp = tmp_path / "glossary.csv"
    monkeypatch.setattr(cfg_mod, "default_glossary_path", lambda: str(gp))
    seen: dict = {}

    def _fake_append(entries, path):
        seen["entries"] = entries
        seen["path"] = path
        return [{"src": e.get("src"), "target": e.get("target"),
                 "status": "added"} for e in entries]

    monkeypatch.setattr(gl_mod, "append_glossary_entries", _fake_append)
    entries = [{"src": "気持ちよさそう", "target": "看起来很爽"}]
    r = gui_api_obj.refine_ai_apply_glossary(json.dumps(
        entries, ensure_ascii=False))
    assert r["success"] is True
    assert r["path"] == str(gp)
    assert r["results"][0]["status"] == "added"
    assert seen["entries"] == entries
    assert seen["path"] == str(gp)


def test_refine_ai_apply_glossary_bad_json(gui_api_obj):
    """entries_json 非 JSON / 非数组 → success=False 且不触词库。"""
    for payload in ("not-json", "123", "null"):
        r = gui_api_obj.refine_ai_apply_glossary(payload)
        assert r["success"] is False, payload


def test_refine_ai_apply_tm_store_and_conflict_warn(gui_api_obj,
                                                    monkeypatch,
                                                    tmp_path):
    """TM 落库：store 新增/已存在状态 + watch 未裁决冲突 conflict_warn 黄标。"""
    import subtransjav.refine.glossary_conflict as gc_mod
    import subtransjav.refine.tm as tm_mod

    stored: list = []

    class _FakeTM:
        def __init__(self, db_path=None):
            pass

        def store(self, source, target, stage=0, source_name=None):
            stored.append((source, target))
            return len(stored) == 1  # 第 1 条新增，第 2 条已存在

        def close(self):
            return None

    monkeypatch.setattr(tm_mod, "TranslationMemory", _FakeTM)
    watch = tmp_path / "glossary_conflict_watch.json"
    watch.write_text(json.dumps([
        {"date": "2026-09-29", "source": "a.srt",
         "per_term": {"魔鏡番号": {"candidates": 3, "conflicts": 2},
                      "先生": {"candidates": 5, "conflicts": 1}},
         "manual_false_positive": {"先生": {"by": "user"}}},
    ], ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(gc_mod, "default_watch_path", lambda: str(watch))

    entries = [
        {"source": "魔鏡番号", "target": "片商编号"},
        {"source": "先生、だめです", "target": "老师，不行的"},
    ]
    r = gui_api_obj.refine_ai_apply_tm(json.dumps(entries,
                                                  ensure_ascii=False))
    assert r["success"] is True
    assert [x["status"] for x in r["results"]] == ["added", "exists"]
    assert r["results"][0]["conflict_warn"] is True, \
        "watch 未裁决冲突词必须黄标"
    assert r["results"][1]["conflict_warn"] is False, \
        "manual_false_positive 豁免词不黄标"
    assert stored == [(e["source"], e["target"]) for e in entries]


def test_refine_ai_apply_tm_watch_missing_no_block(gui_api_obj,
                                                   monkeypatch,
                                                   tmp_path):
    """watch JSON 缺失 → 不阻断，warn 全 False。"""
    import subtransjav.refine.glossary_conflict as gc_mod
    import subtransjav.refine.tm as tm_mod

    class _FakeTM:
        def __init__(self, db_path=None):
            pass

        def store(self, source, target, stage=0, source_name=None):
            return True

        def close(self):
            return None

    monkeypatch.setattr(tm_mod, "TranslationMemory", _FakeTM)
    monkeypatch.setattr(gc_mod, "default_watch_path",
                        lambda: str(tmp_path / "no_such_watch.json"))
    r = gui_api_obj.refine_ai_apply_tm(json.dumps(
        [{"source": "あ", "target": "啊"}], ensure_ascii=False))
    assert r["success"] is True
    assert r["results"][0]["conflict_warn"] is False


def test_refine_ai_apply_tm_bad_json(gui_api_obj):
    """entries_json 非 JSON → success=False。"""
    r = gui_api_obj.refine_ai_apply_tm("{{{bad")
    assert r["success"] is False

# ---------------------------------------------------------------------------
# 快速试听 refine_audio_preview（D2026-0929-09 视听对比第二阶段）
# 五态：direct / clip / 无 ffmpeg / override 越界拒绝 / 导读缺 media_path
# mock 口径参照本文件既有模式：subprocess.run 捕获参数、audio_detect
# 探测函数与 GUI 侧抽片函数 monkeypatch，零真实子进程。
# ---------------------------------------------------------------------------

_GUIDE_SUFFIX = "_质量报告导读.json"


def _make_guide(tmp_path: Path, media_path=None, stem="ep01") -> Path:
    """落一份导读 json（media_path 非空时写入 v1.5 契约键）。"""
    data = {"version": "1.5", "source": f"{stem}.srt", "stem": stem,
            "conclusions": [], "sections": [], "items": [],
            "companions": {}}
    if media_path:
        data["media_path"] = media_path
        data["media_path_source"] = "manifest"
    p = tmp_path / f"{stem}{_GUIDE_SUFFIX}"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def _install_fake_ffprobe(monkeypatch, video="", audio="", duration_s=3600.0):
    """替身 ffprobe 链路：shutil.which 命中 + subprocess.run 返回 codec JSON；
    format=duration 查询（2.7.4 件2 层② 时长验证/④ 时长守卫）返回
    duration_s（缺省 3600s=媒体时长充足）。"""
    import subtransjav.webview_gui.api as api_mod
    captured: dict = {}

    def _fake_run(args, **kwargs):
        captured["args"] = args
        if "format=duration" in args:
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {"format": {"duration": str(duration_s)}}
                ).encode("utf-8"),
                stderr=b"")
        return SimpleNamespace(
            returncode=0,
            stdout=json.dumps({"streams": [
                {"codec_type": "video", "codec_name": video},
                {"codec_type": "audio", "codec_name": audio},
            ]}).encode("utf-8"),
            stderr=b"")

    monkeypatch.setattr(api_mod.shutil, "which",
                        lambda name: "/fake/ffprobe" if name == "ffprobe" else None)
    monkeypatch.setattr(api_mod.subprocess, "run", _fake_run)
    return captured


def test_refine_audio_preview_direct_playable(gui_api_obj, monkeypatch,
                                              tmp_path):
    """direct 态：mp4 + h264/aac（ffprobe 真实 codec）→ 浏览器原生可播。"""
    media = tmp_path / "ep01.mp4"
    media.write_bytes(b"fake-mp4")
    guide = _make_guide(tmp_path, media_path=str(media))
    captured = _install_fake_ffprobe(monkeypatch, video="h264", audio="aac")

    r = gui_api_obj.refine_audio_preview(str(guide), 10.0, 12.0)
    assert r["ok"] is True
    assert r["mode"] == "direct"
    assert r["media_path"] == str(media)
    assert r["codec_probe"] is True
    # ffprobe 走 list-args（禁 shell）且输入为导读 media_path
    assert captured["args"][-1] == str(media)
    assert all(isinstance(a, str) for a in captured["args"])


def test_refine_audio_preview_clip_fallback(gui_api_obj, monkeypatch,
                                            tmp_path):
    """clip 态：mkv + hevc 边界编码 → ffmpeg 抽 [start-0.5, end+0.5] wav；
    timing 起点为负时钳制到 0。"""
    import subtransjav.refine.audio_detect as ad
    import subtransjav.refine.config as cfg_mod
    import subtransjav.webview_gui.api as api_mod

    media = tmp_path / "ep02.mkv"
    media.write_bytes(b"fake-mkv")
    guide = _make_guide(tmp_path, media_path=str(media), stem="ep02")
    _install_fake_ffprobe(monkeypatch, video="hevc", audio="aac")
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(cfg_mod, "TEMP_DIR", str(tmp_path / "temp"))

    captured: dict = {}

    def _fake_extract(ffmpeg_path, media_path, out_path, start_s, duration_s):
        captured.update(ff=ffmpeg_path, media=media_path, out=out_path,
                        start=start_s, dur=duration_s)
        Path(out_path).write_bytes(b"RIFF....WAVEfmt ")

    monkeypatch.setattr(api_mod.TranslateAPI, "_extract_preview_wav",
                        staticmethod(_fake_extract))

    r = gui_api_obj.refine_audio_preview(str(guide), 10.0, 12.0)
    assert r["ok"] is True
    assert r["mode"] == "clip"
    assert r["data_url"].startswith("data:audio/wav;base64,")
    assert r["duration_s"] == 3.0
    # 2.7.4 件2：clip 回包补 media_path/media_source（向后兼容加列）
    assert r["media_path"] == str(media)
    assert r["media_source"] == "guide"
    assert captured["start"] == 9.5 and captured["dur"] == 3.0
    assert captured["media"] == str(media)
    # 片段落 TEMP_DIR/audio_detect/preview/，命名带哈希
    out = Path(captured["out"])
    assert out.parent == tmp_path / "temp" / "audio_detect" / "preview"
    assert out.name.startswith("pv_") and out.name.endswith(".wav")

    # timing 越界钳制：start=-5 → clip_start 钳 0，duration = 3+0.5
    r2 = gui_api_obj.refine_audio_preview(str(guide), -5.0, 3.0)
    assert r2["ok"] is True
    assert captured["start"] == 0.0 and captured["dur"] == 3.5


def test_refine_audio_preview_no_ffmpeg(gui_api_obj, monkeypatch, tmp_path):
    """无 ffmpeg：mp4/m4a（aac 语义）尝试 direct；其余容器报错灰显。"""
    import subtransjav.refine.audio_detect as ad
    import subtransjav.webview_gui.api as api_mod

    monkeypatch.setattr(api_mod.shutil, "which", lambda name: None)
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: None)

    mp4 = tmp_path / "ep03.mp4"
    mp4.write_bytes(b"fake")
    guide_mp4 = _make_guide(tmp_path, media_path=str(mp4), stem="ep03")
    r1 = gui_api_obj.refine_audio_preview(str(guide_mp4), 0.0, 2.0)
    assert r1["ok"] is True and r1["mode"] == "direct"
    assert r1["codec_probe"] is False

    mkv = tmp_path / "ep04.mkv"
    mkv.write_bytes(b"fake")
    guide_mkv = _make_guide(tmp_path, media_path=str(mkv), stem="ep04")
    r2 = gui_api_obj.refine_audio_preview(str(guide_mkv), 0.0, 2.0)
    assert r2["ok"] is False
    assert "未检测到 ffmpeg" in r2["error"]


def test_refine_audio_preview_override_outside_anchor_rejected(
        gui_api_obj, monkeypatch, tmp_path):
    """override 越界路径（越出 home/仓库根锚点）必须拒绝，不触 ffprobe。"""
    guide = _make_guide(tmp_path)
    captured = _install_fake_ffprobe(monkeypatch)
    outside = os.path.join(os.path.expanduser("~"), os.pardir, os.pardir,
                           "beyond_anchor_media.mp4")
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0,
                                         media_override=outside)
    assert r["ok"] is False
    assert "路径不在允许的目录下" in r["error"]
    assert captured == {}, "拒绝必须发生在 ffprobe 之前"


def test_refine_audio_preview_guide_missing_media_path(gui_api_obj,
                                                       tmp_path):
    """导读缺 media_path 且同目录无推断候选 → no_candidate 结构化失败
    （2.7.4 件2：原 no_media 文案被四层解析的零命中态取代）。"""
    guide = _make_guide(tmp_path)
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False
    assert r["error_key"] == "no_candidate"
    assert "媒体" in r["error"]
    assert r["candidates"] == []


# ---------------------------------------------------------------------------
# 数据保存目录（owner 反馈②）：refine_get/set_data_root 三态
# ---------------------------------------------------------------------------
def test_refine_get_data_root_default(gui_api_obj, monkeypatch):
    """读态：返回 data_root/source/pointer/is_frozen，与 paths 同源。"""
    from subtransjav import paths
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    got = gui_api_obj.refine_get_data_root()
    assert got["success"] is True
    assert got["data_root"] == str(paths.data_root())
    assert got["source"] == paths.data_root_source()
    assert got["pointer"] == paths.get_data_root_pointer()
    assert got["is_frozen"] is False


def test_refine_set_data_root_writes_pointer(gui_api_obj, monkeypatch,
                                             tmp_path):
    """写态：绝对路径写入 pointer 文件，need_restart=True。"""
    from subtransjav import paths
    pointer = tmp_path / ".data-root"
    monkeypatch.setattr(paths, "_data_root_pointer_path", lambda: pointer)
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    target = tmp_path / "custom_root"
    target.mkdir()
    got = gui_api_obj.refine_set_data_root(str(target))
    assert got["success"] is True
    assert got["need_restart"] is True
    assert got["data_root"] == str(target)
    assert pointer.read_text(encoding="utf-8").strip() == str(target)


def test_refine_set_data_root_clear_and_reject(gui_api_obj, monkeypatch,
                                               tmp_path):
    """清除态（空串=恢复默认）+ 相对路径拒绝。"""
    from subtransjav import paths
    pointer = tmp_path / ".data-root"
    monkeypatch.setattr(paths, "_data_root_pointer_path", lambda: pointer)
    monkeypatch.delenv("SUBTRANSJAV_DATA_ROOT", raising=False)
    target = tmp_path / "custom_root"
    target.mkdir()
    assert gui_api_obj.refine_set_data_root(str(target))["success"] is True
    got = gui_api_obj.refine_set_data_root("")
    assert got["success"] is True
    assert got["need_restart"] is True
    assert not pointer.exists()
    # 相对路径拒绝
    bad = gui_api_obj.refine_set_data_root("relative/dir")
    assert bad["success"] is False
    assert bad["error"] == "请输入绝对路径"


# ---------------------------------------------------------------------------
# read_output_artifact 双格式扩展：*_质量报告.txt 只读文本
# ---------------------------------------------------------------------------

def test_read_output_artifact_txt(gui_api_obj, tmp_path):
    """报告 txt：kind=txt + text 透传（只读，不解析 JSON）。"""
    p = tmp_path / "EP01_质量报告.txt"
    p.write_text("== 报告 ==\n结论一行\n", encoding="utf-8")
    got = gui_api_obj.read_output_artifact(str(p))
    assert got["success"] is True
    assert got["kind"] == "txt"
    assert got["text"] == "== 报告 ==\n结论一行\n"
    assert got["truncated"] is False


def test_read_output_artifact_json_kind_backward_compat(gui_api_obj, tmp_path):
    """导读 json：返回含 kind=json 且 data 透传（向后兼容）。"""
    p = tmp_path / "EP01_质量报告导读.json"
    p.write_text('{"version":"2","items":[]}', encoding="utf-8")
    got = gui_api_obj.read_output_artifact(str(p))
    assert got["success"] is True
    assert got["kind"] == "json"
    assert got["data"]["version"] == "2"


# ---------------------------------------------------------------------------
# refine_get_learned_glossary：学习词库只读查看（存在/缺失/上限截断）
# ---------------------------------------------------------------------------

def _learned_csv(rows: list[tuple]) -> str:
    return "\n".join(
        ",".join(list(r)) for r in rows) + "\n"


def test_learned_glossary_missing(gui_api_obj, monkeypatch, tmp_path):
    """文件缺失：exists=False 零门槛不报错。"""
    from subtransjav.refine import config as cfg_mod
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(tmp_path))
    got = gui_api_obj.refine_get_learned_glossary()
    assert got["success"] is True
    assert got["exists"] is False
    assert got["count"] == 0 and got["rows"] == []


def test_learned_glossary_present(gui_api_obj, monkeypatch, tmp_path):
    """存在：返回 source/target/aliases 行（utf-8-sig 兼容）。"""
    from subtransjav.refine import config as cfg_mod
    cfg = tmp_path / "glossary_learned.csv"
    cfg.write_text(
        "マスター,主人,女将|ママ\n先生,老师,\n", encoding="utf-8-sig")
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(tmp_path))
    got = gui_api_obj.refine_get_learned_glossary()
    assert got["success"] is True
    assert got["exists"] is True
    assert got["total"] == 2 and got["count"] == 2
    assert got["truncated"] is False
    assert got["rows"][0] == {"source": "マスター", "target": "主人",
                              "aliases": "女将|ママ"}
    assert got["rows"][1]["aliases"] == ""


def test_learned_glossary_truncated_at_cap(gui_api_obj, monkeypatch, tmp_path):
    """上限截断：只返回前 500 行，total/truncated 如实。"""
    from subtransjav.refine import config as cfg_mod
    cfg = tmp_path / "glossary_learned.csv"
    lines = "".join(f"src{i},dst{i}\n" for i in range(503))
    cfg.write_text(lines, encoding="utf-8")
    monkeypatch.setattr(cfg_mod, "CONFIG_DIR", str(tmp_path))
    got = gui_api_obj.refine_get_learned_glossary()
    assert got["success"] is True
    assert got["count"] == 500
    assert got["total"] == 503
    assert got["truncated"] is True
    assert got["rows"][0]["source"] == "src0"


# ---------------------------------------------------------------------------
# 词典管理端点（2.1 引擎页词典管理三区块）
# ---------------------------------------------------------------------------
def test_refine_dict_status_shape(gui_api_obj, monkeypatch, tmp_path):
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    got = gui_api_obj.refine_dict_status()
    assert got["success"] is True
    # 2.5.0 修复A：kind 架构增 sudachi_full（文件存在判定，未装即 False）
    assert set(got["dicts"]) == {"sudachi", "sudachi_full", "jieba",
                                 "english_rules"}
    assert got["dicts"]["english_rules"]["available"] is True
    assert got["dicts"]["sudachi_full"]["available"] is False


def test_refine_dict_download_unsupported_kind(gui_api_obj):
    got = gui_api_obj.refine_dict_download("jieba")
    assert got["success"] is False
    assert "不支持下载" in got["error"]


def _dict_dl_wait_idle(kind: str, timeout: float = 5.0) -> None:
    """等待 kind 的下载 worker 收口（注册表条目清除）。daemon 线程跨测试
    残留会在 monkeypatch 还原后调用真实 download_dict（真实网络），故每
    例收尾必须等待收口。"""
    from subtransjav.webview_gui import api as api_mod
    deadline = time.time() + timeout
    while time.time() < deadline:
        with api_mod._DICT_DL_LOCK:
            entry = api_mod._DICT_DL_REGISTRY.get(kind)
        if entry is None:
            return
        entry["thread"].join(timeout=0.05)
    raise AssertionError(f"词典下载线程 {kind} 未在 {timeout}s 内收口")


def test_refine_dict_download_success_and_checksum(gui_api_obj, monkeypatch,
                                                   tmp_path):
    """2.7.3 件⑤ 会话制改契约：refine_dict_download 立即返回
    success+session_id（下载转后台线程；网络/校验失败改经 dict 层
    failed 快照透出给轮询，不再经本方法返回值——原同步错误映射断言随
    语义废止，失败快照语义由 test_dict_manager 覆盖）。保留原覆盖意图：
    kind 白名单放行 + 会话可启动 + worker 真实调用 download_dict。"""
    from subtransjav.refine import dict_manager as dm
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    calls = []

    def _fake(kind, *args, **kwargs):
        calls.append(kind)
        return str(tmp_path / "dict" / "system_core.dic")

    monkeypatch.setattr(dm, "download_dict", _fake)
    got = gui_api_obj.refine_dict_download("sudachi")
    assert got["success"] is True
    assert got.get("session_id")
    _dict_dl_wait_idle("sudachi")
    assert calls == ["sudachi"], "worker 须真实调用 download_dict(kind)"


def test_refine_dict_download_async_immediate_session(gui_api_obj,
                                                      monkeypatch):
    """2.7.3 件⑤ ①：立即返回不阻塞 jsapi 线程——download_dict 打桩为
    慢函数，返回时 worker 仍在跑（同步实现会在此挂死至慢函数返回）。"""
    from subtransjav.refine import dict_manager as dm
    from subtransjav.webview_gui import api as api_mod
    started = threading.Event()
    release = threading.Event()

    def _slow(kind, *args, **kwargs):
        started.set()
        release.wait(timeout=5)

    monkeypatch.setattr(dm, "download_dict", _slow)
    try:
        r = gui_api_obj.refine_dict_download("sudachi")
        assert r["success"] is True and r["session_id"]
        assert started.wait(timeout=5), "后台 worker 未启动"
        with api_mod._DICT_DL_LOCK:
            entry = api_mod._DICT_DL_REGISTRY["sudachi"]
        assert entry["session"] == r["session_id"]
        assert entry["thread"].is_alive(), \
            "慢下载未完成时线程必须仍存活（同步实现此处已返回终值）"
    finally:
        release.set()
        _dict_dl_wait_idle("sudachi")


def test_refine_dict_download_same_kind_busy_rejected(gui_api_obj,
                                                      monkeypatch):
    """2.7.3 件⑤ ②：同 kind 旧线程存活 → 二次调用被 dict_download_busy
    人话拒绝（HRO-1 单一活跃下载者）；异 kind 不受互斥影响。"""
    from subtransjav.refine import dict_manager as dm
    release = threading.Event()

    def _slow(kind, *args, **kwargs):
        release.wait(timeout=5)

    monkeypatch.setattr(dm, "download_dict", _slow)
    try:
        first = gui_api_obj.refine_dict_download("sudachi")
        assert first["success"] is True
        second = gui_api_obj.refine_dict_download("sudachi")
        assert second["success"] is False
        assert "进行中" in second["message"]
        other = gui_api_obj.refine_dict_download("sudachi_full")
        assert other["success"] is True, "互斥按 kind 分键，异 kind 不拒绝"
    finally:
        release.set()
        _dict_dl_wait_idle("sudachi")
        _dict_dl_wait_idle("sudachi_full")


def test_refine_dict_download_stop_sets_event_no_snapshot(gui_api_obj,
                                                          monkeypatch):
    """2.7.3 件⑤ ③：stop 端点置位 Event（下载线程可观测）且绝不乐观写
    stopped 快照（HRO-1.3：快照只能由下载线程检查点收口写）。"""
    from subtransjav.refine import dict_manager as dm
    monkeypatch.setattr(dm, "_DOWNLOAD_PROGRESS", {})
    seen_stop = threading.Event()

    def _waiter(kind, *args, stop_event=None, **kwargs):
        if stop_event is not None:
            stop_event.wait(timeout=5)
            seen_stop.set()

    monkeypatch.setattr(dm, "download_dict", _waiter)
    try:
        r = gui_api_obj.refine_dict_download("sudachi")
        assert r["success"] is True
        got = gui_api_obj.refine_dict_download_stop("sudachi")
        assert got == {"success": True}
        assert seen_stop.wait(timeout=5), "stop Event 未被下载线程观测到"
        assert dm.download_progress("sudachi") == {}, \
            "stop 端点不得乐观写 stopped 快照"
    finally:
        _dict_dl_wait_idle("sudachi")


def test_refine_dict_download_stop_idempotent_no_entry(gui_api_obj):
    """2.7.3 件⑤ ④：无线程时 stop 幂等宽容 False（绝不抛错）。"""
    from subtransjav.webview_gui import api as api_mod
    with api_mod._DICT_DL_LOCK:
        api_mod._DICT_DL_REGISTRY.pop("sudachi", None)
    assert gui_api_obj.refine_dict_download_stop("sudachi") \
        == {"success": False}


def test_refine_dict_download_registry_cleared_can_restart(gui_api_obj,
                                                           monkeypatch):
    """2.7.3 件⑤ ⑤：线程收口后注册表清空、可再次下载（新 session_id）。"""
    from subtransjav.refine import dict_manager as dm
    from subtransjav.webview_gui import api as api_mod
    monkeypatch.setattr(dm, "download_dict", lambda kind, *a, **k: "x")
    first = gui_api_obj.refine_dict_download("sudachi")
    assert first["success"] is True
    _dict_dl_wait_idle("sudachi")
    with api_mod._DICT_DL_LOCK:
        assert "sudachi" not in api_mod._DICT_DL_REGISTRY
    second = gui_api_obj.refine_dict_download("sudachi")
    assert second["success"] is True
    assert second["session_id"] != first["session_id"]
    _dict_dl_wait_idle("sudachi")


def test_refine_dict_download_register_start_atomic(gui_api_obj, monkeypatch):
    """code-review 触碰式修复①：登记与 worker.start() 同锁原子。旧实现
    start() 在锁外——用 GatedThread 把 start 阻塞在「已登记未 start」窗口
    内放大竞态，此时并发第二次调用会看到 is_alive()=False 覆盖条目致双
    下载；修复后第二次调用阻塞等锁、锁释放时线程必已活，必被
    dict_download_busy 拒（单一活跃下载者不变量）。"""
    from subtransjav.refine import dict_manager as dm
    from subtransjav.webview_gui import api as api_mod
    real_thread_cls = threading.Thread        # 补丁前捕获真身（编排线程用）
    dl_gate = threading.Event()               # 放大 start 前窗口
    gated_seen = []

    class _GatedThread(real_thread_cls):
        def start(self):
            if not gated_seen:                # 仅首个 worker（首次下载）设卡
                gated_seen.append(self)
                dl_gate.wait(timeout=5)       # 旧实现此处在锁外，新实现在锁内
            super().start()

    monkeypatch.setattr(api_mod.threading, "Thread", _GatedThread)
    release = threading.Event()

    def _slow(kind, *args, **kwargs):
        release.wait(timeout=5)

    monkeypatch.setattr(dm, "download_dict", _slow)
    results = {}

    def _call(slot):
        results[slot] = gui_api_obj.refine_dict_download("sudachi")

    t1 = real_thread_cls(target=_call, args=("first",))
    t1.start()
    # 等 t1 完成登记（条目可见）——此刻 t1 卡在 gated start() 内（持锁），
    # 故这里只做无锁读轮询（GIL 下 dict 成员判断原子），绝不取锁防死锁
    deadline = time.time() + 5
    while time.time() < deadline:
        if "sudachi" in api_mod._DICT_DL_REGISTRY:
            break
        time.sleep(0.01)
    t2 = real_thread_cls(target=_call, args=("second",))
    t2.start()
    try:
        dl_gate.set()                         # 放行首次 start，锁随后释放
        t1.join(timeout=5)
        t2.join(timeout=5)
        assert results["first"]["success"] is True
        assert results["second"]["success"] is False, \
            "start 前窗口内的并发二次调用必须被互斥拒绝"
        assert "进行中" in results["second"]["message"]
    finally:
        dl_gate.set()                         # 防断言失败时 t1 仍卡 gate
        release.set()
        _dict_dl_wait_idle("sudachi")


def test_refine_dict_download_progress_endpoint(gui_api_obj, monkeypatch):
    """进度端点（第四批词典下载体验）：success+快照；无记录 success+空。"""
    from subtransjav.refine import dict_manager as dm
    # api 方法为函数内导入，patch 源模块属性才生效
    monkeypatch.setattr(dm, "_DOWNLOAD_PROGRESS", {
        "sudachi": {"kind": "sudachi", "phase": "download",
                    "downloaded": 5, "total": 10, "error": None}})
    got = gui_api_obj.refine_dict_download_progress("sudachi")
    assert got["success"] is True
    assert got["phase"] == "download"
    assert got["downloaded"] == 5 and got["total"] == 10
    # 无记录 kind：success + 空（前端按无进度处理）
    empty = gui_api_obj.refine_dict_download_progress("jieba")
    assert empty == {"success": True}


# ---------------------------------------------------------------------------
# 2.1 翻译方向控件（D2026-0930-04 定案① GUI 补齐，第五批）
# ---------------------------------------------------------------------------
def test_build_refine_args_direction_default_omitted():
    """缺省 ja/zh/空卡：不传方向与指令卡参数（与 CLI 缺省一致，字节钉）。"""
    args = _build_refine_args({"inputs": ["a.srt"], "profile": "local"})
    joined = " ".join(args)
    assert "--source-lang" not in joined
    assert "--target-lang" not in joined
    assert "--s1-instructions" not in joined
    assert "--s3-instructions" not in joined


def test_build_refine_args_direction_default_values_omitted():
    """显式传 ja/zh（=缺省值）同样不传参（控件缺省选中不产生旗标）。"""
    args = _build_refine_args({"inputs": ["a.srt"], "profile": "local",
                               "source_lang": "ja", "target_lang": "zh"})
    joined = " ".join(args)
    assert "--source-lang" not in joined and "--target-lang" not in joined


def test_build_refine_args_direction_non_default_passthrough():
    """非缺省方向+指令卡：四旗标逐项透传。"""
    card_a = str(Path("cards") / "a.txt")
    card_b = str(Path("cards") / "b.txt")
    args = _build_refine_args({
        "inputs": ["a.srt"], "profile": "local",
        "source_lang": "zh", "target_lang": "en",
        "s1_instructions": card_a, "s3_instructions": card_b})
    joined = " ".join(args)
    assert "--source-lang zh" in joined
    assert "--target-lang en" in joined
    assert f"--s1-instructions {card_a}" in joined
    assert f"--s3-instructions {card_b}" in joined


def test_stage_settings_direction_keys_roundtrip(gui_api_obj, tmp_path,
                                                 monkeypatch):
    """direction_* 四键写→读一致（settings 顶层字典任意键）。"""
    path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(path))
    r = gui_api_obj.refine_save_stage_settings(
        settings={"direction_source": "zh", "direction_target": "en",
                  "direction_card_s1": "cards/a.txt",
                  "direction_card_s3": "cards/b.txt"})
    assert r["success"] is True
    got = gui_api_obj.refine_get_stage_settings()
    assert got["success"] is True
    s = got["settings"]
    assert (s["direction_source"], s["direction_target"]) == ("zh", "en")
    assert s["direction_card_s1"] == "cards/a.txt"
    assert s["direction_card_s3"] == "cards/b.txt"


def test_stage_settings_cleaner_config_dir_roundtrip(gui_api_obj, tmp_path,
                                                     monkeypatch):
    """cleaner_config_dir 写→读一致（settings 顶层字典任意键，含空串）。"""
    path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(path))
    r = gui_api_obj.refine_save_stage_settings(
        settings={"cleaner_config_dir": "config/templates"})
    assert r["success"] is True
    got = gui_api_obj.refine_get_stage_settings()
    assert got["success"] is True
    assert got["settings"]["cleaner_config_dir"] == "config/templates"
    # 空串覆盖清除旧存档值（回填侧得到留空=自动查找语义）
    r2 = gui_api_obj.refine_save_stage_settings(
        settings={"cleaner_config_dir": ""})
    assert r2["success"] is True
    got2 = gui_api_obj.refine_get_stage_settings()
    assert got2["settings"]["cleaner_config_dir"] == ""


def test_build_refine_args_cleaner_config_dir_flag():
    """cleaner_config_dir 非空才拼 --cleaner-config；空串/缺席不拼。"""
    args = _build_refine_args({"inputs": ["a.srt"], "profile": "local",
                               "cleaner_config_dir": "config/templates"})
    joined = " ".join(args)
    assert "--cleaner-config config/templates" in joined

    for empty in ("", None):
        opts = {"inputs": ["a.srt"], "profile": "local"}
        if empty is not None:
            opts["cleaner_config_dir"] = empty
        joined2 = " ".join(_build_refine_args(opts))
        assert "--cleaner-config" not in joined2


# ---------------------------------------------------------------------------
# 文件对话框桥（D2026-0930-07 owner 痛点批）：无活动窗口 error 分支；
# 真实对话框弹出留 owner 真机验收（headless 无法验证）
# ---------------------------------------------------------------------------

def test_refine_pick_guide_json_no_active_window(gui_api_obj, monkeypatch):
    """无活动窗口时导读 json 对话框桥走 error 分支（no_active_window）。"""
    import subtransjav.webview_gui.api as api_mod
    monkeypatch.setattr(api_mod.webview, "windows", [])
    r = gui_api_obj.refine_pick_guide_json()
    assert r["success"] is False
    assert r["error"] == "无活动窗口"
    assert "cancelled" not in r, "无窗口属环境错误，不得误标为用户取消"


# ---------------------------------------------------------------------------
# 角色卡目录下拉动态化（D2026-0930-07-追加1）：
# refine_list_templates / refine_save_template 值域闭环 / load-by-name
# 文件名参数位穿越防线 + canonical 精确匹配语义。
# ---------------------------------------------------------------------------

def _dyn_tpl_dir() -> Path:
    """主目录下登记一个会话目录（_ensure_template_dir 白名单内）。"""
    d = Path.home() / ("subtransjav_tpl_dyn_" + uuid.uuid4().hex[:8])
    d.mkdir(parents=True, exist_ok=True)
    register_session_paths([str(d)])
    return d


def test_refine_list_templates_top_level_txt_only(gui_api_obj):
    """list 端点：仅顶层 .txt（含复合后缀卡/README 类），不递归子目录，
    非 .txt 排除；canonical 精确文件名随返回值下发。"""
    d = _dyn_tpl_dir()
    try:
        (d / "角色-净语翻译.txt").write_text("A卡", encoding="utf-8")
        (d / "角色-净语翻译.en2zh.txt").write_text("en2zh卡", encoding="utf-8")
        (d / "README-说明.txt").write_text("说明", encoding="utf-8")
        (d / "ignore.csv").write_text("x", encoding="utf-8")
        sub = d / "sub"
        sub.mkdir()
        (sub / "nested.txt").write_text("n", encoding="utf-8")
        r = gui_api_obj.refine_list_templates(str(d))
        assert r["success"] is True
        names = [f["name"] for f in r["files"]]
        assert "角色-净语翻译.en2zh.txt" in names
        assert "README-说明.txt" in names
        assert "ignore.csv" not in names, "非 .txt 必须排除"
        assert "nested.txt" not in names and "sub" not in names, \
            "子目录不递归"
        assert all(os.path.basename(n) == n for n in names), "仅返回相对文件名"
        assert all(isinstance(f["mtime"], float) for f in r["files"])
        assert r["pkg_fallback"] is False
        assert r["dir"] == str(d)
        assert r["canonical"] == {"A": "角色-净语翻译.txt",
                                  "B": "角色-审校抛光.txt"}
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_list_templates_empty_dir_pkg_fallback(gui_api_obj):
    """空目录：files=[]、pkg_fallback=True，且不创建任何文件。"""
    d = _dyn_tpl_dir()
    try:
        r = gui_api_obj.refine_list_templates(str(d))
        assert r["success"] is True
        assert r["files"] == [] and r["pkg_fallback"] is True
        assert list(d.iterdir()) == [], "目录必须保持为空"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_list_templates_missing_dir_no_mkdir(gui_api_obj):
    """目录不存在：不创建目录，pkg_fallback=True。"""
    d = Path.home() / ("subtransjav_tpl_absent_" + uuid.uuid4().hex[:8])
    register_session_paths([str(d)])
    try:
        r = gui_api_obj.refine_list_templates(str(d))
        assert r["success"] is True
        assert r["files"] == [] and r["pkg_fallback"] is True
        assert not d.exists(), "list 端点绝不能创建目录"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_list_templates_unregistered_dir_rejected(gui_api_obj):
    """未登记目录走目录位守卫拒绝（不新增任意目录列举能力）。"""
    outsider = Path.home() / ("subtransjav_no_such_" + uuid.uuid4().hex[:8])
    r = gui_api_obj.refine_list_templates(str(outsider))
    assert r["success"] is False


def test_refine_save_template_filename_traversal_rejected(gui_api_obj):
    """保存文件名参数位穿越载荷（../../x.txt、绝对路径、嵌套目录）拒绝。"""
    d = _dyn_tpl_dir()
    try:
        (d / "README-说明.txt").write_text("r", encoding="utf-8")
        bad_names = [
            str(Path(os.pardir) / os.pardir / "x.txt"),     # ../../x.txt
            str(Path.home() / "evil_cards.txt"),            # 绝对路径
            str(Path("sub") / "x.txt"),                     # 嵌套目录
        ]
        for bad in bad_names:
            r = gui_api_obj.refine_save_template("A", "穿越", str(d),
                                                 filename=bad)
            assert r["success"] is False, f"穿越载荷必须拒绝: {bad}"
        assert list(d.iterdir()) == [d / "README-说明.txt"], \
            "拒绝路径不得落盘任何新文件"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_save_template_unlisted_target_rejected(gui_api_obj):
    """target 不在 list 返回集（目录内不存在的非 canonical 名）→ 拒绝。"""
    d = _dyn_tpl_dir()
    try:
        (d / "README-说明.txt").write_text("r", encoding="utf-8")
        r = gui_api_obj.refine_save_template("A", "内容", str(d),
                                             filename="凭空新建卡.txt")
        assert r["success"] is False
        assert not (d / "凭空新建卡.txt").exists(), "值域外目标不得落盘"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_save_template_noncanonical_ok_and_disk(gui_api_obj):
    """正常非 canonical 复合后缀卡保存成功，且磁盘内容写对。"""
    d = _dyn_tpl_dir()
    try:
        target = "角色-净语翻译.en2zh.txt"
        (d / target).write_text("旧内容", encoding="utf-8")
        r = gui_api_obj.refine_save_template("A", "新卡内容", str(d),
                                             filename=target)
        assert r["success"] is True
        assert (d / target).read_text(encoding="utf-8") == "新卡内容"
        assert os.path.dirname(r["path"]) == str(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_save_template_canonical_on_empty_dir_allowed(gui_api_obj):
    """pkg_fallback（目录为空）时保存 canonical 名 = 新建默认文件，放行。"""
    d = _dyn_tpl_dir()
    try:
        r = gui_api_obj.refine_save_template(
            "A", "默认卡", str(d), filename="角色-净语翻译.txt")
        assert r["success"] is True
        assert (d / "角色-净语翻译.txt").read_text(
            encoding="utf-8") == "默认卡"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_get_template_by_name_ok(gui_api_obj):
    """load-by-name：按文件名读取目录内复合后缀卡（非 canonical）。"""
    d = _dyn_tpl_dir()
    try:
        (d / "角色-净语翻译.en2zh.txt").write_text("en2zh卡内容",
                                                   encoding="utf-8")
        r = gui_api_obj.refine_get_template("A", str(d),
                                            filename="角色-净语翻译.en2zh.txt")
        assert r["success"] is True
        assert r["text"] == "en2zh卡内容"
        assert os.path.dirname(r["path"]) == str(d)
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_get_template_by_name_traversal_rejected(gui_api_obj):
    """load-by-name 穿越载荷拒绝（含绝对路径/嵌套/非 .txt）。"""
    d = _dyn_tpl_dir()
    try:
        (d / "README-说明.txt").write_text("r", encoding="utf-8")
        bad_names = [
            str(Path(os.pardir) / os.pardir / "x.txt"),
            str(Path.home() / "evil_cards.txt"),
            str(Path("sub") / "x.txt"),
            "config_keys.bin",   # 非 .txt 后缀
        ]
        for bad in bad_names:
            r = gui_api_obj.refine_get_template("A", str(d), filename=bad)
            assert r["success"] is False, f"穿越/非法载荷必须拒绝: {bad}"
    finally:
        shutil.rmtree(d, ignore_errors=True)


def test_refine_get_template_by_name_missing_reports_error(gui_api_obj):
    """load-by-name 不做 pkg 回落：文件缺失走 template_file_missing 分支。"""
    from subtransjav.webview_gui.strings import msg
    d = _dyn_tpl_dir()
    try:
        (d / "README-说明.txt").write_text("r", encoding="utf-8")
        r = gui_api_obj.refine_get_template("A", str(d),
                                            filename="不存在的卡.txt")
        assert r["success"] is False
        assert r["error"] == msg("template_file_missing",
                                 path=os.path.join(str(d), "不存在的卡.txt"))
    finally:
        shutil.rmtree(d, ignore_errors=True)


# ---------------------------------------------------------------------------
# get_translation_status：per-file 三态 chip 归组透传（批 2a files_status）
# ---------------------------------------------------------------------------

def test_get_translation_status_exposes_files_status(gui_api_obj):
    """NDJSON 解析器归组的 per-file 状态经 files_status 键透传给前端。"""
    import io

    from subtransjav.refine.events import EventEmitter
    from subtransjav.webview_gui.event_stream import EventStreamParser

    api = _manual_state_api(gui_api_obj)
    buf = io.StringIO()
    em = EventEmitter(stream=buf, task_id="t")
    em.emit("phase_started", phase="A", file="ep01.srt")
    em.emit("phase_started", phase="A", file="ep02.srt")
    em.emit("phase_finished", phase="final", file="ep01.srt")
    parser = EventStreamParser()
    for line in buf.getvalue().splitlines():
        if line.strip():
            parser.feed(line)
    api._translate_parser = parser

    status = api.get_translation_status()

    assert status["files_status"] == {
        "ep01.srt": "done", "ep02.srt": "running"}


def test_get_translation_status_files_status_empty_when_no_parser(gui_api_obj):
    """无解析器（未启动/遗留输出）时 files_status 为空 dict，键始终存在。"""
    api = _manual_state_api(gui_api_obj)
    status = api.get_translation_status()
    assert status["files_status"] == {}


# ---------------------------------------------------------------------------
# 批 8a（D2026-1006-01）：_pump_stdout 闸门 + gui.log 全量落盘 +
# get_translation_status files 口径 / task_summary 透出
# ---------------------------------------------------------------------------

def _pump_lines(gui_api_obj, lines):
    """构造假 proc 逐行喂 _pump_stdout，返回排干的日志队列内容。"""
    api = _manual_state_api(gui_api_obj)
    api._translate_parser = EventStreamParser()
    proc = SimpleNamespace(stdout=iter(lines), wait=lambda: None)
    api._pump_stdout(proc)
    logs = []
    while not api._translate_log_queue.empty():
        logs.append(api._translate_log_queue.get_nowait())
    return logs


def _emit_event_lines(*events) -> list[str]:
    """用 EventEmitter 生成真实 NDJSON 事件行列表（含行尾换行）。"""
    buf = io.StringIO()
    em = EventEmitter(stream=buf, task_id="t")
    for ev in events:
        em.emit(*ev[0], **ev[1])
    return buf.getvalue().splitlines(keepends=True)


def test_pump_stdout_heartbeat_not_enqueued(gui_api_obj):
    """心跳事件行被闸门丢弃：队列无裸 JSON（批 8a P0 缺陷钉）。"""
    lines = _emit_event_lines((("heartbeat",), {"payload": {"elapsed_s": 1}}))
    assert _pump_lines(gui_api_obj, lines) == []


def test_pump_stdout_gate0_summary_human_line_enqueued(gui_api_obj):
    """gate0_summary 入队恰一条人话行（非 JSON）。"""
    lines = _emit_event_lines(
        (("gate0_summary",),
         {"phase": "gate0", "file": "ep01.srt",
          "payload": {"detected_total": 12, "deleted": 5, "total": 300}}),
    )
    logs = _pump_lines(gui_api_obj, lines)
    assert len(logs) == 1
    assert not logs[0].lstrip().startswith("{")
    assert logs[0] == "[事件] 闸门0 ep01.srt：检出 12 · 处置 5 · 净语 295"


def test_pump_stdout_non_event_line_passthrough(gui_api_obj):
    """非事件行（遗留文本）原样入队。"""
    logs = _pump_lines(gui_api_obj, ["Translating 42 lines\n"])
    assert logs == ["Translating 42 lines\n"]


def test_pump_stdout_logs_enqueued_lines_to_gui_log(gui_api_obj, monkeypatch):
    """入队行全量落盘：logger.info 收到 strip 行尾换行的行
    （事件人话行与非事件行均落盘；心跳不入队故也不落盘）。"""
    import subtransjav.webview_gui.api as api_mod

    records: list = []

    class _FakeLogger:
        def info(self, message: str) -> None:
            records.append(message)

    monkeypatch.setattr(api_mod, "_log", _FakeLogger())
    lines = _emit_event_lines(
        (("task_started",), {"payload": {"files": 2}}),
    ) + ["plain legacy line\n"]
    logs = _pump_lines(gui_api_obj, lines)
    assert logs == ["[事件] 任务开始", "plain legacy line\n"]
    assert records == ["[事件] 任务开始", "plain legacy line"]


def _status_api_with_parser(gui_api_obj):
    """伪造 parser 聚合状态：task_started(files=3) + 1 完成 + 1 失败。"""
    api = _manual_state_api(gui_api_obj)
    buf = io.StringIO()
    em = EventEmitter(stream=buf, task_id="t")
    em.emit("task_started", payload={"files": 3, "profile": "default"})
    em.emit("phase_started", phase="A", file="ep01.srt")
    em.emit("phase_finished", phase="final", file="ep01.srt")
    em.emit("error", file="ep03.srt", payload={"reason": "x"})
    parser = EventStreamParser()
    for line in buf.getvalue().splitlines():
        if line.strip():
            parser.feed(line)
    api._translate_parser = parser
    return api


def test_get_translation_status_files_completed_and_total(gui_api_obj):
    """files_completed 数 done 态、files_total 取 max(已知文件数, 期望总数)，
    不再把 snapshot 的行数 total 当文件数（批 8a 缺陷①②钉）。"""
    status = _status_api_with_parser(gui_api_obj).get_translation_status()
    assert status["files_completed"] == 1
    assert status["files_total"] == 3    # len(files)=2，expected=3 → 3
    assert status["files_status"] == {"ep01.srt": "done",
                                      "ep03.srt": "failed"}


def test_get_translation_status_files_total_falls_back_to_known_files(gui_api_obj):
    """无 task_started（期望总数 0）时 files_total 回退已知文件数。"""
    api = _manual_state_api(gui_api_obj)
    buf = io.StringIO()
    em = EventEmitter(stream=buf, task_id="t")
    em.emit("phase_finished", phase="final", file="ep01.srt")
    parser = EventStreamParser()
    for line in buf.getvalue().splitlines():
        if line.strip():
            parser.feed(line)
    api._translate_parser = parser
    status = api.get_translation_status()
    assert status["files_completed"] == 1
    assert status["files_total"] == 1


def test_get_translation_status_passes_task_summary(gui_api_obj):
    """snapshot 的 task_summary 经新键透出（批 8a 完成摘要透出钉）。"""
    api = _manual_state_api(gui_api_obj)
    buf = io.StringIO()
    em = EventEmitter(stream=buf, task_id="t")
    em.emit("task_finished", payload={"status": "ok", "files_ok": 2,
                                      "files_failed": 0})
    parser = EventStreamParser()
    for line in buf.getvalue().splitlines():
        if line.strip():
            parser.feed(line)
    api._translate_parser = parser
    status = api.get_translation_status()
    assert status["task_summary"] == {"status": "ok", "files_ok": 2,
                                      "files_failed": 0}


# ---------------------------------------------------------------------------
# 2.6.0 批1（D2026-1002-02-批1）：质量闭环一键批次修复
# ---------------------------------------------------------------------------

_BF_GUIDE_STEM = "ep01"
_T3 = "00:00:03,000 --> 00:00:04,000"
_T7 = "00:00:07,000 --> 00:00:08,000"


def _bf_item(index, timing, text, category="cps_too_fast", status="open"):
    return {"index": index, "timing": timing, "category": category,
            "message": "m", "current_text": text,
            "source_excerpt": "src", "status": status, "severity": None}


def _make_bf_guide(tmp_path: Path, items, ledger=None, with_report=True,
                   with_suggestion=None, source="") -> Path:
    guide = {"version": 2, "stem": _BF_GUIDE_STEM, "items": items,
             "direction": "", "media_path": ""}
    if source:
        guide["source"] = source    # F1 批0：顶层 source（真实输入名口径）
    p = tmp_path / f"{_BF_GUIDE_STEM}_质量报告导读.json"
    p.write_text(json.dumps(guide, ensure_ascii=False), encoding="utf-8")
    if ledger is not None:
        (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").write_text(
            json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    if with_report:
        (tmp_path / f"{_BF_GUIDE_STEM}_质量报告.txt").write_text(
            "【结论】x\n", encoding="utf-8")
    if with_suggestion is not None:
        (tmp_path / f"{_BF_GUIDE_STEM}_AI质量建议.json").write_text(
            json.dumps({"parse_ok": True, "suggestions": with_suggestion},
                       ensure_ascii=False), encoding="utf-8")
    return p


def _install_fake_stage3(gui_api_obj, monkeypatch, provider="deepseek",
                         endpoint="", model="sb-model"):
    """替身 refine_get_stage_settings：只含阶段B（存储 stage=3）。

    P2（D2026-1008-02）后修复解析不再读阶段B（改共用分析解析 helper），
    本替身保留用于「阶段B 设置不得影响修复解析」的反向断言；正向链
    请给 refine_batch_fix 传 ai_provider/ai_model 形参或注阶段A。"""
    monkeypatch.setattr(
        gui_api_obj, "refine_get_stage_settings",
        lambda: {"success": True,
                 "stages": [{"stage": 3, "provider": provider,
                             "endpoint": endpoint, "model": model}],
                 "settings": {}, "key_status": {}, "first_run": False})


def _install_fake_stages(gui_api_obj, monkeypatch, stage1=None, stage3=None,
                         settings=None):
    """替身 refine_get_stage_settings：阶段A/B 双段可配（C7 修复模型解析
    测试用，D2026-1007-02 件C）；批3（D2026-1008-01）增 settings 形参——
    独立修复配置 KV（batch_fix_provider/model）注入用，缺省 {}=无键。
    P2（D2026-1008-02）后该两 KV 不再被解析消费（保留形参兼容旧调用）。"""
    stages: list[dict] = []
    if stage1 is not None:
        stages.append({"stage": 1, **stage1})
    if stage3 is not None:
        stages.append({"stage": 3, **stage3})
    monkeypatch.setattr(
        gui_api_obj, "refine_get_stage_settings",
        lambda: {"success": True, "stages": stages,
                 "settings": settings or {}, "key_status": {},
                 "first_run": False})


class _FakePopen:
    def __init__(self, lines, rc=0):
        self.stdout = iter(lines)
        self.pid = 4242
        self._rc = rc

    def wait(self, timeout=None):
        return self._rc

    def kill(self):
        pass


def _install_fake_bf_spawn(monkeypatch, *, lines=(), rc=0, ledger_path=None,
                           ledger_records=None, verify_suggestions=None,
                           verify_returncode=0):
    """替身 spawn_refine_cli：批修复走 Popen 流式路径（可选模拟执行器落
    台账）；复验 --ai-analyze 路径（批4 起为 Popen+communicate 形状，
    按 argv 旗标识别）可选覆写建议件后返回 _FakeAnalyzeProc（refine_ai_analyze
    消费 communicate 返回的 .stderr/.returncode）。"""
    import subtransjav.webview_gui.api as api_mod
    captured: dict = {}

    def _fake_spawn(args, **kwargs):
        captured.setdefault("calls", []).append(
            {"args": args, "kwargs": kwargs})
        if "--ai-analyze" in args:
            if verify_suggestions is not None:
                report_arg = args[args.index("--ai-analyze") + 1]
                stem = Path(report_arg).name[:-len("_质量报告.txt")]
                out = Path(report_arg).parent / f"{stem}_AI质量建议.json"
                out.write_text(json.dumps(
                    {"parse_ok": True, "suggestions": verify_suggestions},
                    ensure_ascii=False), encoding="utf-8")
            return _FakeAnalyzeProc(returncode=verify_returncode)
        if ledger_path is not None and ledger_records:
            existing = []
            if ledger_path.is_file():
                try:
                    existing = json.loads(
                        ledger_path.read_text(encoding="utf-8"))
                except (OSError, ValueError):
                    existing = []
            existing.extend(ledger_records)
            ledger_path.write_text(json.dumps(existing, ensure_ascii=False),
                                   encoding="utf-8")
        return _FakePopen(lines, rc=rc)

    monkeypatch.setattr(api_mod, "spawn_refine_cli", _fake_spawn)
    return captured


def test_batch_fix_constants_pinned():
    """成本护栏常量钉：单批上限/超时/导读后缀。"""
    from subtransjav.webview_gui.api import TranslateAPI as _T
    assert _T._BATCH_FIX_MAX_ENTRIES == 50
    assert _T._BATCH_FIX_TIMEOUT_S == 1800
    assert _T._GUIDE_SUFFIX == "_质量报告导读.json"


def test_guide_action_items_marks_applied(gui_api_obj, tmp_path):
    """台账感知标记：applied 条目入 open_items 但不计入可修分类计数。"""
    items = [_bf_item(3, _T3, "甲"), _bf_item(7, _T7, "乙")]
    ledger = [{"timing": _T3, "outcome": "applied"}]
    guide = _make_bf_guide(tmp_path, items, ledger=ledger)
    r = gui_api_obj.refine_guide_action_items(str(guide))
    assert r["success"] is True
    assert r["applied_open_count"] == 1
    assert r["cat_counts"] == {"cps_too_fast": 1}
    marks = {it["index"]: it["applied_in_ledger"] for it in r["open_items"]}
    assert marks == {3: True, 7: False}
    assert r["open_items"][0]["excerpt"] == "甲"


# ---------------------------------------------------------------------------
# 批6（D2026-1008-02）：终态状态落盘的后端可见性
# ---------------------------------------------------------------------------

def test_guide_action_items_terminal_statuses_counted(gui_api_obj, tmp_path):
    """终态（retranslated/nochange）只计数不进 open_items；未知 status
    仍进 open_items（C2：未知默认可见，禁静默丢）。"""
    items = [_bf_item(3, _T3, "甲", status="retranslated"),
             _bf_item(7, _T7, "乙", status="nochange"),
             _bf_item(9, "T9", "丙", status="weird"),
             _bf_item(11, "T11", "丁")]
    guide = _make_bf_guide(tmp_path, items)
    r = gui_api_obj.refine_guide_action_items(str(guide))
    assert r["success"] is True
    assert r["retranslated_count"] == 1
    assert r["nochange_count"] == 1
    assert [it["index"] for it in r["open_items"]] == [9, 11]
    assert r["cat_counts"] == {"cps_too_fast": 2}


def test_ledger_top_reason_only_counts_failed(gui_api_obj, tmp_path):
    """主因只统计 outcome==failed：nochange/applied 的 reason 不入选。"""
    items = [_bf_item(3, _T3, "甲")]
    ledger_path = tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json"
    ledger_path.write_text(json.dumps([
        {"timing": _T3, "outcome": "nochange",
         "reason": "已与现译一致，判无需改动"},
        {"timing": _T3, "outcome": "applied", "reason": "不应入选"},
    ], ensure_ascii=False), encoding="utf-8")
    _make_bf_guide(tmp_path, items)
    assert gui_api_obj._ledger_top_reason(str(tmp_path),
                                          _BF_GUIDE_STEM) == ""
    ledger_path.write_text(json.dumps([
        {"timing": _T3, "outcome": "nochange",
         "reason": "已与现译一致，判无需改动"},
        {"timing": _T3, "outcome": "failed", "reason": "端点不通"},
    ], ensure_ascii=False), encoding="utf-8")
    assert gui_api_obj._ledger_top_reason(str(tmp_path),
                                          _BF_GUIDE_STEM) == "端点不通"


def test_batch_fix_result_counts_nochange(gui_api_obj, monkeypatch, tmp_path):
    """批6：回包新增 nochange 计数（台账增量 outcome==nochange）。"""
    items = [_bf_item(3, _T3, "甲")]
    ledger_path = tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json"
    guide = _make_bf_guide(tmp_path, items, with_suggestion={
        "glossary": [], "tm": [], "observations": []})
    _install_fake_secret(monkeypatch, stored=("deepseek",))
    _install_fake_bf_spawn(
        monkeypatch, lines=["ok"], rc=0, ledger_path=ledger_path,
        ledger_records=[{"index": 3, "timing": _T3, "outcome": "nochange",
                         "source_partial": False}],
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")
    assert r["success"] is True and r["exit_code"] == 0
    assert r["nochange"] == 1
    assert r["applied"] == 0 and r["failed"] == 0


def test_batch_fix_skips_terminal_status_entries(gui_api_obj, tmp_path):
    """终态守卫（批6）：导读 status 已终态的 index 被过滤；全被过滤→
    可读拒绝且不 spawn。"""
    items = [_bf_item(3, _T3, "甲", status="nochange"),
             _bf_item(7, _T7, "乙", status="retranslated")]
    guide = _make_bf_guide(tmp_path, items)
    r = gui_api_obj.refine_batch_fix(str(guide), [3, 7], "deepseek",
                                     "sb-model")
    assert r["success"] is False
    assert "终态" in r["error"] and "无可修条目" in r["error"]


def test_batch_fix_guards(gui_api_obj, tmp_path):
    """守卫链：空/非整数 entries、越 cap、观察类与未知条目、错误后缀。"""
    items = [_bf_item(3, _T3, "甲"),
             _bf_item(9, "T9", "乙", category="x", status="observation")]
    guide = _make_bf_guide(tmp_path, items)
    assert gui_api_obj.refine_batch_fix(str(guide), [])["success"] is False
    assert gui_api_obj.refine_batch_fix(
        str(guide), ["3"])["success"] is False
    r = gui_api_obj.refine_batch_fix(str(guide), list(range(1, 53)))
    assert "上限" in r["error"]
    r = gui_api_obj.refine_batch_fix(str(guide), [9])
    assert "不可自动重翻" in r["error"]          # 观察类必拒（C6）
    r = gui_api_obj.refine_batch_fix(str(guide), [99])
    assert "不可自动重翻" in r["error"]
    bad = tmp_path / "x.json"
    bad.write_text("{}", encoding="utf-8")
    r = gui_api_obj.refine_batch_fix(str(bad), [3])
    assert "_质量报告导读.json" in r["error"]


def test_batch_fix_rejects_already_applied(gui_api_obj, tmp_path):
    """C1 幂等守卫：台账已修条目拒入批，明示 CLI 重修通道。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items,
                           ledger=[{"timing": _T3, "outcome": "applied"}])
    r = gui_api_obj.refine_batch_fix(str(guide), [3])
    assert r["success"] is False
    assert "已修过" in r["error"]
    assert "CLI" in r["error"]


def test_batch_fix_success_and_ledger_delta(gui_api_obj, monkeypatch,
                                            tmp_path):
    """成功链：CLI 参数（--s1-provider/--action-model/--apply）+密钥 env
    注入+台账增量计数+复验三键 diff+进度终态。
    P2（D2026-1008-02）：修复与 AI 分析同源——provider 旗标改
    --s1-provider（动作客户端已改槽A），provider/model 经形参透传。"""
    items = [_bf_item(3, _T3, "甲"),
             _bf_item(7, _T7, "乙", category="untranslated")]
    ledger_path = tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json"
    guide = _make_bf_guide(tmp_path, items, with_suggestion={
        "glossary": [], "tm": [], "observations": ["o1"]})
    _install_fake_secret(monkeypatch, stored=("deepseek",))
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=["[1/2] ok", "[2/2] ok"], rc=0,
        ledger_path=ledger_path,
        ledger_records=[{"index": 3, "timing": _T3, "outcome": "applied",
                         "source_partial": True}],
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    r = gui_api_obj.refine_batch_fix(str(guide), [3, 7], "deepseek",
                                     "sb-model")
    assert r["success"] is True and r["exit_code"] == 0
    assert r["applied"] == 1 and r["source_partial"] == 1
    b = captured["calls"][0]          # 第 0 次=批修复；第 1 次=复验 --ai-analyze
    args = b["args"]
    assert args[args.index("--action-retranslate") + 1] == str(guide)
    assert args[args.index("--entries") + 1] == "3,7"
    assert "--apply" in args
    assert args[args.index("--s1-provider") + 1] == "deepseek"
    assert "--s3-provider" not in args          # 旧阶段B 旗标随链退役
    assert args[args.index("--action-model") + 1] == "sb-model"
    assert b["kwargs"]["env_extra"].get("DEEPSEEK_API_KEY") == "sk-fake"
    # 第 1 次=复验 --ai-analyze（批4 起 Popen 形态，按 argv 旗标识别）
    assert "--ai-analyze" in captured["calls"][1]["args"]
    assert r["verify"]["before"] == {"glossary": 0, "tm": 0,
                                     "observations": 1}
    assert r["verify"]["after"] == {"glossary": 0, "tm": 0,
                                    "observations": 0}
    assert r["suggestions"] == {"glossary": [], "tm": [], "observations": []}
    p = gui_api_obj.refine_batch_fix_progress()
    assert p["running"] is False and p["phase"] == "done"


def test_batch_fix_passes_action_source_when_resolved(gui_api_obj,
                                                      monkeypatch,
                                                      tmp_path):
    """F1 批0（D2026-1009-01 C1）：三级定位命中 → spawn args 含
    --action-source 指向已解析源文件，且位于 --entries 之后 --apply 之前。"""
    src = tmp_path / "ep01.japanese.srt"
    src.write_text(f"1\n{_T3}\n甲\n", encoding="utf-8")
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items, source=src.name)
    _install_fake_secret(monkeypatch, stored=("deepseek",))
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=["ok"], rc=0,
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")
    assert r["success"] is True and r["exit_code"] == 0
    args = captured["calls"][0]["args"]
    assert args[args.index("--action-source") + 1] == str(src)
    assert args.index("--entries") < args.index("--action-source") \
        < args.index("--apply")


def test_batch_fix_omits_action_source_when_unresolved(gui_api_obj,
                                                       monkeypatch,
                                                       tmp_path):
    """F1 批0 退化（C1 第三级）：source 指名文件与 {stem}.srt 均不存在
    → args 不含 --action-source（CLI 侧既有提示兜底，不新增通知管线）。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items, source="missing.srt")
    _install_fake_secret(monkeypatch, stored=("deepseek",))
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=["ok"], rc=0,
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")
    assert r["success"] is True and r["exit_code"] == 0
    assert "--action-source" not in captured["calls"][0]["args"]


def test_batch_fix_exit1_skips_verify(gui_api_obj, monkeypatch, tmp_path):
    """全败（rc=1）：success=False 且不触发复验。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    captured = _install_fake_bf_spawn(monkeypatch, lines=["boom"], rc=1)
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")
    assert r["success"] is False and r["exit_code"] == 1
    assert "verify" not in r
    # 复验未发起：全程恰一次 spawn（批4：复验亦走 spawn 通道，按次数断言）
    assert len(captured["calls"]) == 1


def test_batch_fix_timeout_reports_ledger_semantics(gui_api_obj, monkeypatch,
                                                    tmp_path):
    """超时：杀树+如实口径（已落盘以台账为准，可再发起）。"""
    import subtransjav.webview_gui.api as api_mod
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    monkeypatch.setattr(api_mod, "terminate_process_tree", lambda pid: None)

    class _Hang:
        stdout = iter([])
        pid = 1

        def wait(self, timeout=None):
            raise subprocess.TimeoutExpired(cmd=["x"], timeout=1800)

        def kill(self):
            pass

    monkeypatch.setattr(api_mod, "spawn_refine_cli", lambda a, **kw: _Hang())
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")
    assert r["success"] is False and "超时" in r["error"]
    assert "台账" in r["error"]


def test_batch_fix_exit3_partial_with_verify(gui_api_obj, monkeypatch,
                                             tmp_path):
    """部分成功（rc=3）：success=True、applied/failed 分账、复验仍执行。"""
    items = [_bf_item(3, _T3, "甲"), _bf_item(7, "T7", "乙")]
    ledger_path = tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json"
    guide = _make_bf_guide(tmp_path, items)
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=["done"], rc=3, ledger_path=ledger_path,
        ledger_records=[
            {"index": 3, "timing": _T3, "outcome": "applied"},
            {"index": 7, "timing": "T7", "outcome": "failed",
             "source_partial": True}],
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    r = gui_api_obj.refine_batch_fix(str(guide), [3, 7], "deepseek",
                                     "sb-model")
    assert r["success"] is True and r["exit_code"] == 3
    assert r["applied"] == 1 and r["failed"] == 1
    assert r["source_partial"] == 1
    assert "verify" in r and "after" in r["verify"]
    assert "--action-retranslate" in captured["calls"][0]["args"]


def test_batch_fix_guard_path_missing(gui_api_obj, tmp_path):
    """守卫：路径不存在 → guide_file_missing。"""
    r = gui_api_obj.refine_batch_fix(
        str(tmp_path / "无_质量报告导读.json"), [3])
    assert r["success"] is False and r["error"]


# ---------------------------------------------------------------------------
# P2 修复/分析模型统一（D2026-1008-02）：共用解析 helper
# _resolve_ai_model_config（C6 单源）——旧独立修复链（C7 补链/批3 三源
# 解析）钉随链解冻重钉（C11）；以下为六项回归矩阵 + C18 边界钉
# ---------------------------------------------------------------------------

def test_fix_matrix_ab_same_config(gui_api_obj, monkeypatch):
    """矩阵① A/B 同配置：修复解析只看分析源（独立缺席→阶段A 链），
    阶段B 不再参与（同配置下结果=A 整组，非 B 模型）。"""
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "deepseek",
                                 "endpoint": "https://a.example/v1",
                                 "model": "a-model"},
                         stage3={"provider": "deepseek",
                                 "endpoint": "https://b.example/v1",
                                 "model": "a-model"})
    r = gui_api_obj._resolve_ai_model_config(None, None)
    assert r["ok"] is True and r["source"] == "stage_a_follow"
    assert (r["provider"], r["endpoint"], r["model"]) == \
        ("deepseek", "https://a.example/v1", "a-model")
    assert r["notes"] == []


def test_fix_matrix_ab_diff_config(gui_api_obj, monkeypatch):
    """矩阵② A/B 不同配置：A=lmstudio/qwen、B=deepseek/b-model → 修复
    仍用 A 整组（B 端点/模型零消费——「与分析完全同一」契约，C9 不回退
    阶段B）。"""
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "lmstudio",
                                 "endpoint": "http://192.168.1.8:1234/v1",
                                 "model": "qwen"},
                         stage3={"provider": "deepseek",
                                 "endpoint": "https://b.example/v1",
                                 "model": "b-model"})
    r = gui_api_obj._resolve_ai_model_config(None, None)
    assert r["ok"] is True and r["source"] == "stage_a_follow"
    assert (r["provider"], r["endpoint"], r["model"]) == \
        ("lmstudio", "http://192.168.1.8:1234/v1", "qwen")


def test_fix_matrix_indep_half_ignored(gui_api_obj, monkeypatch):
    """矩阵③ G5-补 分析独立半配置（仅 provider 无 model）→ 视为未配置
    忽略 + notes 注记 + 回落阶段A 链；阶段A 也无线索时如实拒绝且 notes
    仍回带（错误人话可拼装完整因果）。"""
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "deepseek",
                                 "endpoint": "https://a.example/v1",
                                 "model": "a-model"})
    r = gui_api_obj._resolve_ai_model_config("deepseek", "")
    assert r["ok"] is True and r["source"] == "stage_a_follow"
    assert (r["provider"], r["model"]) == ("deepseek", "a-model")
    assert r["notes"] == ["分析独立配置不完整，已忽略"]
    # 半配置 + 阶段A 空 → 拒绝（notes 回带供拼装；reason 如实）
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "", "endpoint": "",
                                 "model": ""})
    r = gui_api_obj._resolve_ai_model_config("zen", None)
    assert r["ok"] is False
    assert r["notes"] == ["分析独立配置不完整，已忽略"]
    assert "分析模型与阶段A 均未配置" in r["reason"]
    assert not any((r["provider"], r["endpoint"], r["model"]))


def test_fix_matrix_stage_a_empty_denied_verbatim(gui_api_obj, monkeypatch):
    """矩阵④ 阶段A 空（provider 无默认模型时才失败）：A 全空 → 拒绝且
    reason 与 strings.py fix_ai_model_unset 逐字一致（C8 如实，弃
    generic 盖法）；A=lmstudio（无默认模型）且 model 空 → 同样拒绝。"""
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "", "endpoint": "",
                                 "model": ""})
    r = gui_api_obj._resolve_ai_model_config(None, None)
    assert r["ok"] is False
    assert r["reason"] == ("分析模型与阶段A 均未配置，无法修复：请在"
                           "「质量与建议」配置 AI 分析模型，或在"
                           "「翻译设置 · 阶段A（净语+翻译）」填写模型名")
    assert not any((r["provider"], r["endpoint"], r["model"]))
    # provider=lmstudio 有名无默认模型、model 空 → 无线索同拒绝
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "lmstudio", "endpoint": "",
                                 "model": ""})
    r = gui_api_obj._resolve_ai_model_config(None, None)
    assert r["ok"] is False and "均未配置" in r["reason"]


def test_fix_matrix_provider_default_fallback(gui_api_obj, monkeypatch):
    """矩阵⑤ 服务商默认兜底：阶段A model 空但 provider=zen（表内有默认
    模型）→ 默认模型生效，source=stage_a_follow。"""
    from subtransjav.refine.config import PROVIDER_MODEL_DEFAULTS
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "zen", "endpoint": "",
                                 "model": ""})
    r = gui_api_obj._resolve_ai_model_config(None, None)
    assert r["ok"] is True and r["source"] == "stage_a_follow"
    assert r["provider"] == "zen"
    assert r["model"] == PROVIDER_MODEL_DEFAULTS["zen"]
    assert r["model"] == "x-preview-f-free"


def test_fix_matrix_c18_no_runtime_fallback(gui_api_obj, monkeypatch):
    """C18 边界：配置层完整（独立配置全有）时解析层不做任何替换——
    model 原样透出，即使阶段A 存在另一套模型（运行时失败由 ensure/CLI
    原样报错，禁止静默回退阶段A）。"""
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "lmstudio",
                                 "endpoint": "http://192.168.1.8:1234/v1",
                                 "model": "qwen"})
    r = gui_api_obj._resolve_ai_model_config("deepseek", "analyze-model")
    assert r["ok"] is True and r["source"] == "analyze_independent"
    assert r["model"] == "analyze-model"          # 原样，零替换
    assert (r["provider"], r["endpoint"]) == ("deepseek", "")
    assert r["notes"] == []


def test_fix_indep_custom_full_pair_denied(gui_api_obj, monkeypatch):
    """独立配置全有且 provider=custom → 兜底拒绝（无默认端点；与分析
    路径同串单源 ai_indep_custom_unsupported）；半配置 custom 落 G5-补
    忽略规则不在此拒绝。"""
    r = gui_api_obj._resolve_ai_model_config("custom", "m1")
    assert r["ok"] is False
    assert r["reason"] == ("自定义接口暂不支持独立配置："
                           "请将阶段A 服务商设为 custom 后使用")
    # 半配置 custom（无 model）→ 忽略回落阶段A（G5-补 优先于 custom 拒绝）
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "lmstudio", "endpoint": "",
                                 "model": "qwen"})
    r = gui_api_obj._resolve_ai_model_config("custom", "")
    assert r["ok"] is True and (r["provider"], r["model"]) == \
        ("lmstudio", "qwen")
    assert r["notes"] == ["分析独立配置不完整，已忽略"]


def test_refine_preview_fix_config_shape(gui_api_obj, monkeypatch):
    """桥方法形状钉：只读不 spawn，恒返回八键形状（ok 布尔 + 六字符串
    + notes 字符串列表，P2 追加 notes），拒绝带人话 reason；ok=True
    分支 source=stage_a_follow（阶段A 链）。"""
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "", "endpoint": "",
                                 "model": ""})
    r = gui_api_obj.refine_preview_fix_config()
    assert set(r) == {"ok", "provider", "endpoint", "model",
                      "source", "source_label", "reason", "notes"}
    assert r["ok"] is False
    assert all(isinstance(r[k], str) for k in
               ("provider", "endpoint", "model", "source", "source_label",
                "reason"))
    assert isinstance(r["notes"], list)
    assert r["reason"]
    # ok=True 分支同样形状（入参=前端 analyzeResolution 同源形参）
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "deepseek",
                                 "endpoint": "https://a.example/v1",
                                 "model": "a-model"})
    r = gui_api_obj.refine_preview_fix_config(None, "a-model")
    assert set(r) == {"ok", "provider", "endpoint", "model",
                      "source", "source_label", "reason", "notes"}
    assert r["ok"] is True and r["source"] == "stage_a_follow"
    assert r["provider"] == "deepseek" and r["model"] == "a-model"


def test_fix_preview_source_label(gui_api_obj, monkeypatch):
    """生效源标识两源人话标签由后端直出（前端零解析）：独立配置=分析
    模型；阶段A 链=跟随阶段A；拒绝分支 source_label 空串 + reason 直显；
    半配置忽略 notes 透出（预览行拼装）。"""
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "deepseek",
                                 "endpoint": "https://a.example/v1",
                                 "model": "a-model"})
    r = gui_api_obj.refine_preview_fix_config("deepseek", "fix-model")
    assert r["ok"] is True
    assert r["source"] == "analyze_independent"
    assert r["source_label"] == "分析模型"
    r = gui_api_obj.refine_preview_fix_config(None, "a-model")
    assert r["ok"] is True and r["source_label"] == "跟随阶段A"
    # 拒绝分支：source_label 空串 + reason 明示；半配置 notes 透出
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "", "endpoint": "",
                                 "model": ""})
    r = gui_api_obj.refine_preview_fix_config("lmstudio", "")
    assert r["ok"] is False and r["source_label"] == ""
    assert "均未配置" in r["reason"]
    assert r["notes"] == ["分析独立配置不完整，已忽略"]


def test_batch_fix_rejects_when_model_unresolvable(gui_api_obj, monkeypatch,
                                                   tmp_path):
    """分析与阶段A 皆无线索 → 拒绝且不 spawn（fail-closed 保持：原空
    model 放任子进程落 CLI 缺省空串 → pipeline RefineError 全败退出 1，
    拦截在 GUI 层；P2 起 reason 如实=新链文案，弃统一 generic 盖法）。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "", "endpoint": "",
                                 "model": ""})
    captured = _install_fake_bf_spawn(monkeypatch)
    r = gui_api_obj.refine_batch_fix(str(guide), [3])
    assert r["success"] is False
    assert "分析模型与阶段A 均未配置" in r["error"]
    assert "calls" not in captured          # 未 spawn


# ---------------------------------------------------------------------------
# 2.7.4 件E（D2026-1007-02）：C8 本地端点 spawn 前预检 + C9 失败可观测性
# ---------------------------------------------------------------------------

def test_endpoint_probe_timeout_constant_pinned():
    """C8 探活超时常量钉（秒）：只判连通，超时=不通。"""
    from subtransjav.webview_gui.api import TranslateAPI as _T
    assert _T._ENDPOINT_PROBE_TIMEOUT_S == 5


def test_batch_fix_probe_blocks_spawn_when_endpoint_down(gui_api_obj,
                                                         monkeypatch,
                                                         tmp_path):
    """C8：本地 provider 端点不通 → 不 spawn，error 含 endpoint 与启动提示。
    P2 后端点取自分析同源解析（阶段A 链端点=阶段A 存储，探活同值）。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "lmstudio",
                                 "endpoint": "http://localhost:9999/v1",
                                 "model": "sb-model"})
    probe_calls: list = []

    def _fake_probe(endpoint, **kwargs):
        probe_calls.append((endpoint, kwargs.get("timeout")))
        return False, "connection refused"

    import subtransjav.translate.llm_client as llm_mod
    monkeypatch.setattr(llm_mod, "probe_endpoint_reachable", _fake_probe)
    captured = _install_fake_bf_spawn(monkeypatch)
    r = gui_api_obj.refine_batch_fix(str(guide), [3])
    assert r["success"] is False
    assert "http://localhost:9999/v1" in r["error"]
    assert "本地推理服务已启动" in r["error"]
    assert "calls" not in captured              # 未 spawn
    assert probe_calls == [("http://localhost:9999/v1",
                            gui_api_obj._ENDPOINT_PROBE_TIMEOUT_S)]


def test_batch_fix_probe_passes_then_spawns(gui_api_obj, monkeypatch,
                                            tmp_path):
    """C8：探活连通（HTTP 任意响应码都算通）→ 走既有 spawn 流程不受影响。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    _install_fake_stages(gui_api_obj, monkeypatch,
                         stage1={"provider": "lmstudio",
                                 "endpoint": "http://localhost:1234/v1",
                                 "model": "sb-model"})
    probe_endpoints: list = []

    def _fake_probe(endpoint, **kwargs):
        probe_endpoints.append(endpoint)
        return True, "HTTP 404"                 # 非 2xx 也算通

    import subtransjav.translate.llm_client as llm_mod
    monkeypatch.setattr(llm_mod, "probe_endpoint_reachable", _fake_probe)
    _install_fake_bf_spawn(monkeypatch, lines=["ok"], rc=0,
                           verify_suggestions={"glossary": [], "tm": [],
                                               "observations": []})
    r = gui_api_obj.refine_batch_fix(str(guide), [3])
    assert r["success"] is True and r["exit_code"] == 0
    assert probe_endpoints == ["http://localhost:1234/v1"]


def test_batch_fix_cloud_provider_skips_probe(gui_api_obj, monkeypatch,
                                              tmp_path):
    """C8：云端 provider 一律跳过探活（探活调用次数 0），行为与既往一致。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    _install_fake_secret(monkeypatch, stored=("deepseek",))

    def _must_not_probe(endpoint, **kwargs):
        raise AssertionError("云端 provider 不得触发端点探活")

    import subtransjav.translate.llm_client as llm_mod
    monkeypatch.setattr(llm_mod, "probe_endpoint_reachable", _must_not_probe)
    captured = _install_fake_bf_spawn(monkeypatch, lines=["ok"], rc=0)
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")
    assert r["success"] is True and r["exit_code"] == 0
    assert "calls" in captured                  # 照常 spawn


def test_batch_fix_exit1_ledger_top_reason(gui_api_obj, monkeypatch,
                                           tmp_path):
    """C9：rc=1 且台账 105 条同 reason → error 拼主因（截断 ≤200 字符）；
    空/缺失 reason 不参与计数；台账读取走 _read_ledger 复用（patch 点在
    _read_ledger 而非内建 open——证明无第二读取通道）。"""
    items = [_bf_item(3, _T3, "甲")]
    ledger = ([{"timing": f"T{i}", "outcome": "failed",
                "reason": "长" * 300} for i in range(105)]
              + [{"timing": f"U{i}", "outcome": "failed", "reason": ""}
                 for i in range(50)]
              + [{"timing": f"V{i}", "outcome": "failed", "reason": "短因"}
                 for i in range(3)])
    guide = _make_bf_guide(tmp_path, items, ledger=ledger)
    ledger_calls: list = []
    real_read = gui_api_obj._read_ledger

    def _counting_read(guide_dir, stem):
        ledger_calls.append(stem)
        return real_read(guide_dir, stem)

    monkeypatch.setattr(gui_api_obj, "_read_ledger", _counting_read)
    _install_fake_bf_spawn(monkeypatch, lines=["boom"] * 3, rc=1)
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")
    assert r["success"] is False and r["exit_code"] == 1
    assert "主因：" in r["error"]
    assert r["error"].split("主因：", 1)[1] == "长" * 200      # 截断 ≤200
    assert ledger_calls                              # 确经 _read_ledger 读取


def test_batch_fix_exit1_ledger_corrupt_degrades(gui_api_obj, monkeypatch,
                                                 tmp_path):
    """C9：台账损坏（非法 json）→ 降级为仅退出码文案，不抛异常。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").write_text(
        "{not json", encoding="utf-8")
    _install_fake_bf_spawn(monkeypatch, lines=["boom"], rc=1)
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")
    assert r["success"] is False and r["exit_code"] == 1
    assert "退出码 1" in r["error"] and "主因" not in r["error"]


def test_batch_fix_exit1_ledger_missing_degrades(gui_api_obj, monkeypatch,
                                                 tmp_path):
    """C9：台账缺失 → 降级为仅退出码文案，不抛异常。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    _install_fake_bf_spawn(monkeypatch, lines=["boom"], rc=1)
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model")
    assert r["success"] is False and r["exit_code"] == 1
    assert "退出码 1" in r["error"] and "主因" not in r["error"]


# ---------------------------------------------------------------------------
# 2.6.1 批 2a（D2026-1002-09）：校对页后端（probe 三态 / load_srt / 转码命令）
# ---------------------------------------------------------------------------

def test_review_probe_direct(gui_api_obj, monkeypatch, tmp_path):
    """direct 态：mp4 + h264/aac → 浏览器原生可播（codec_probe=True）。"""
    media = tmp_path / "ep01.mp4"
    media.write_bytes(b"fake-mp4")
    _install_fake_ffprobe(monkeypatch, video="h264", audio="aac")
    r = gui_api_obj.refine_review_probe_media(str(media))
    assert r["state"] == "direct" and r["codec_probe"] is True


def test_review_probe_clip_audio(gui_api_obj, monkeypatch, tmp_path):
    """clip-audio 态：hevc 边界编码 → 需转码。"""
    media = tmp_path / "ep02.mkv"
    media.write_bytes(b"fake-mkv")
    _install_fake_ffprobe(monkeypatch, video="hevc", audio="aac")
    r = gui_api_obj.refine_review_probe_media(str(media))
    assert r["state"] == "clip-audio" and r["codec_probe"] is True


def test_review_probe_error_when_undetectable(gui_api_obj, monkeypatch, tmp_path):
    """error 态：ffprobe 缺失且非乐观直连容器 → error + codec_probe=False。"""
    import subtransjav.webview_gui.api as api_mod
    media = tmp_path / "ep03.mkv"
    media.write_bytes(b"fake-mkv")
    monkeypatch.setattr(api_mod.shutil, "which", lambda name: None)
    r = gui_api_obj.refine_review_probe_media(str(media))
    assert r["state"] == "error" and r["codec_probe"] is False and r["error"]


def test_review_load_srt_utf8(gui_api_obj, tmp_path):
    """utf-8 样本：结构化 blocks + timing 由 ms 重建。"""
    p = tmp_path / "a.srt"
    p.write_text(
        "1\n00:00:01,000 --> 00:00:02,500\n你好\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\n世界\n",
        encoding="utf-8")
    r = gui_api_obj.refine_review_load_srt(str(p))
    assert r["success"] is True
    assert r["encoding"] == "utf-8" and r["count"] == 2
    b = r["blocks"][0]
    assert b["index"] == 1 and b["start_ms"] == 1000 and b["end_ms"] == 2500
    assert b["timing"] == "00:00:01,000 --> 00:00:02,500"
    assert b["text"] == "你好"


def test_review_load_srt_gbk(gui_api_obj, tmp_path):
    """gbk 中文样本：嗅探命中 gbk 且正确解码。"""
    p = tmp_path / "b.srt"
    p.write_bytes("1\n00:00:01,000 --> 00:00:02,000\n简体中文台词\n".encode("gbk"))
    r = gui_api_obj.refine_review_load_srt(str(p))
    assert r["success"] is True and r["encoding"] == "gbk" and r["count"] == 1
    assert r["blocks"][0]["text"] == "简体中文台词"


def test_review_load_srt_bad_encoding(gui_api_obj, tmp_path):
    """坏字节：双解码失败 → success=False + 编码无法识别文案。"""
    p = tmp_path / "c.srt"
    p.write_bytes(b"1\n00:00:01,000 --> 00:00:02,000\nabc\x81")
    r = gui_api_obj.refine_review_load_srt(str(p))
    assert r["success"] is False and "编码" in r["error"]


def test_review_transcode_command_construction(gui_api_obj, monkeypatch,
                                                tmp_path):
    """转码命令构造：libx264/veryfast/crf 23/aac/-progress pipe:1 +
    输出路径 rt_{sha256[:12]}.mp4；线程同步化直测主体。"""
    import subtransjav.refine.audio_detect as ad
    import subtransjav.refine.config as cfg_mod
    import subtransjav.webview_gui.api as api_mod

    media = tmp_path / "ep01.mkv"
    media.write_bytes(b"fake-mkv")
    _install_fake_ffprobe(monkeypatch, video="hevc", audio="aac")
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(cfg_mod, "TEMP_DIR", str(tmp_path / "temp"))

    captured: dict = {}

    class FakeProc:
        stdout = iter(())
        @staticmethod
        def wait(timeout=None):
            return 0

    def fake_popen(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return FakeProc()

    class SyncThread:
        def __init__(self, target=None, daemon=None, name=None):
            self._target = target
        def start(self):
            self._target()

    monkeypatch.setattr(api_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(api_mod.threading, "Thread", SyncThread)

    r = gui_api_obj.refine_review_start_transcode(str(media))
    assert r["success"] is True and r.get("started") is True
    args = captured["args"]
    assert args[0] == "/fake/ffmpeg" and "-i" in args
    for frag in ("libx264", "veryfast", "23", "aac", "-progress", "pipe:1"):
        assert frag in args, f"转码命令缺 {frag}: {args}"
    # list-args 禁 shell + 输出件命名 rt_{sha256[:12]}.mp4
    assert all(isinstance(a, str) for a in args)
    out = Path(args[-1])
    assert out.parent.name == "review_transcode"
    assert out.stem.startswith("rt_") and len(out.stem) == 15
    assert out.suffix == ".mp4"
    assert captured["kwargs"].get("shell") is False


# ---------------------------------------------------------------------------
# 2.6.1 批 2b（D2026-1002-10）：校对编辑（save/saveas/备份/C1 排除）
# ---------------------------------------------------------------------------

def test_review_save_backup_failure_aborts(gui_api_obj, monkeypatch, tmp_path):
    """备份先行中止（D2）：copy2 两次（含重试一次）均失败 → success=False
    且原文件未动、无半截 .bak.srt 残留。"""
    import subtransjav.webview_gui.api as api_mod
    original = "1\n00:00:01,000 --> 00:00:02,000\n旧\n"
    p = tmp_path / "a.srt"
    p.write_text(original, encoding="utf-8")
    blocks = [{"index": 1, "start_ms": 1000, "end_ms": 2000, "text": "新"}]
    calls = {"n": 0}

    def flaky_copy2(src, dst):
        calls["n"] += 1
        raise PermissionError("locked")

    monkeypatch.setattr(api_mod.shutil, "copy2", flaky_copy2)
    r = gui_api_obj.refine_review_save_srt(str(p), blocks)
    assert r["success"] is False and "备份" in r["error"]
    assert calls["n"] == 2, "备份失败必须重试一次"
    assert p.read_text(encoding="utf-8") == original, "原文件未动"
    assert not (tmp_path / "a.bak.srt").exists(), "无半截备份残留"


def test_review_save_success_backup_and_rewrite(gui_api_obj, tmp_path):
    """成功流：.bak.srt 内容==原内容；新文件==重编号 UTF-8 内容。"""
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\n旧\n", encoding="utf-8")
    blocks = [
        {"index": 1, "start_ms": 1000, "end_ms": 2500, "text": "你好"},
        {"index": 2, "start_ms": 3000, "end_ms": 4000, "text": "世界"},
    ]
    r = gui_api_obj.refine_review_save_srt(str(p), blocks)
    assert r["success"] is True and r["count"] == 2
    assert r["backup_path"] == str(p) + ".bak.srt"
    assert Path(r["backup_path"]).read_text(encoding="utf-8") \
        .endswith("旧\n"), "备份必须等于原内容"
    assert p.read_text(encoding="utf-8") == (
        "1\n00:00:01,000 --> 00:00:02,500\n你好\n\n"
        "2\n00:00:03,000 --> 00:00:04,000\n世界\n")


def test_review_save_renumber_invariant(gui_api_obj, tmp_path):
    """重编号不变式（D3）：跳号源文件 1,3,7 → 保存后 1,2,3，
    start_ms/end_ms/text 逐块不变。"""
    p = tmp_path / "j.srt"
    p.write_text(
        "1\n00:00:01,000 --> 00:00:02,000\n甲\n\n"
        "3\n00:00:03,000 --> 00:00:04,000\n乙\n\n"
        "7\n00:00:05,000 --> 00:00:06,000\n丙\n", encoding="utf-8")
    loaded = gui_api_obj.refine_review_load_srt(str(p))
    assert [b["index"] for b in loaded["blocks"]] == [1, 3, 7]
    r = gui_api_obj.refine_review_save_srt(str(p), loaded["blocks"])
    assert r["success"] is True and r["count"] == 3
    out = p.read_text(encoding="utf-8")
    parts = out.rstrip("\n").split("\n\n")
    assert [pt.splitlines()[0] for pt in parts] == ["1", "2", "3"]
    assert parts[0].splitlines()[1] == "00:00:01,000 --> 00:00:02,000"
    assert parts[1].splitlines()[1] == "00:00:03,000 --> 00:00:04,000"
    assert parts[2].splitlines()[1] == "00:00:05,000 --> 00:00:06,000"
    assert [pt.splitlines()[2] for pt in parts] == ["甲", "乙", "丙"]


def test_review_save_invalid_blocks_rejected(gui_api_obj, tmp_path):
    """C8 结构校验：空 blocks / 缺键 / ms 非数值 → 拒绝且不写。"""
    p = tmp_path / "v.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\n旧\n", encoding="utf-8")
    assert gui_api_obj.refine_review_save_srt(str(p), [])["success"] is False
    bad = [{"start_ms": "x", "end_ms": 2000, "text": "t"}]
    r = gui_api_obj.refine_review_save_srt(str(p), bad)
    assert r["success"] is False and "无效" in r["error"]
    missing = [{"start_ms": 1000, "text": "t"}]
    assert gui_api_obj.refine_review_save_srt(str(p), missing)["success"] is False
    assert "新" not in p.read_text(encoding="utf-8")


def test_review_saveas_two_phase(gui_api_obj, tmp_path):
    """另存为两段式：目标不存在直接写；存在 → exists 标记不写；
    mode='force' → 备份+覆盖写。"""
    blocks = [{"index": 1, "start_ms": 1000, "end_ms": 2000, "text": "T"}]
    target = tmp_path / "out.srt"
    # 批 3 技术债 c：删 src_path 死形参，新签名 (blocks, target_path)
    r = gui_api_obj.refine_review_saveas_srt(blocks, str(target))
    assert r["success"] is True and target.exists()
    before = target.read_text(encoding="utf-8")
    r2 = gui_api_obj.refine_review_saveas_srt(blocks, str(target))
    assert r2["success"] is False and r2["exists"] is True
    assert target.read_text(encoding="utf-8") == before, "exists 态不得写"
    r3 = gui_api_obj.refine_review_save_srt(str(target), blocks, mode="force")
    assert r3["success"] is True and r3.get("backup_path")
    assert Path(r3["backup_path"]).read_text(encoding="utf-8") == before


def test_review_pick_save_path_no_window(gui_api_obj):
    """pick_save_path：无窗口（测试环境）→ error 分支；真实对话框留真机。"""
    r = gui_api_obj.refine_review_pick_save_path("x.srt")
    assert r["success"] is False and r["error"]


def test_review_bak_srt_excluded_from_sources(gui_api_obj, monkeypatch, tmp_path):
    """C1：*.bak.srt 在 batch.find_srt_files 与 select_srt_folder 两处排除。"""
    from subtransjav.refine.batch import find_srt_files
    (tmp_path / "a.srt").write_text("x", encoding="utf-8")
    (tmp_path / "a.bak.srt").write_text("bak", encoding="utf-8")
    files = find_srt_files(str(tmp_path), recursive=False)
    assert str(tmp_path / "a.srt") in files
    assert all(not f.endswith(".bak.srt") for f in files)
    import subtransjav.webview_gui.api as api_mod

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(tmp_path)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.select_srt_folder()
    assert r["success"] is True
    assert str(tmp_path / "a.srt") in r["paths"]
    assert all(not pth.endswith(".bak.srt") for pth in r["paths"])


def test_review_gbk_srt_saved_as_utf8(gui_api_obj, tmp_path):
    """gbk 原件经 load → save 后落盘为严格 UTF-8。"""
    p = tmp_path / "g.srt"
    p.write_bytes("1\n00:00:01,000 --> 00:00:02,000\n中文\n".encode("gbk"))
    loaded = gui_api_obj.refine_review_load_srt(str(p))
    assert loaded["encoding"] == "gbk"
    r = gui_api_obj.refine_review_save_srt(str(p), loaded["blocks"])
    assert r["success"] is True
    raw = p.read_bytes()
    text = raw.decode("utf-8")   # 严格 UTF-8 可解码（gbk 字节序列不再存在）
    assert "中文" in text


# ============================================================
# 2.6.1 批 3（D2026-1002-11）：疑点段加载 / fs_utils / _codec_direct
# ============================================================

def _make_guide(tmp_path, stem="demo", items=None, media_path=None):
    """导读 json 夹具（items 8 字段；media_path 空串时键缺席=生产口径）。"""
    data = {"version": 1, "source": f"{stem}.srt", "items": items or [],
            "stem": stem}
    if media_path is not None:
        data["media_path"] = media_path
    p = tmp_path / f"{stem}_质量报告导读.json"
    p.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    return p


def test_review_load_detections_filters_and_passthrough(gui_api_obj, tmp_path):
    """load_detections：仅保留带 timing 的 items；8 字段透传；
    media_path 透传（非空）。"""
    items = [
        {"index": 1, "timing": "00:00:01,000 --> 00:00:02,000",
         "category": "suspected_missed_speech", "message": "疑似漏听（粗筛）",
         "current_text": None, "source_excerpt": "", "status": "observation",
         "severity": None},
        {"index": 2, "timing": "", "category": "x", "message": "无时间戳",
         "current_text": None, "source_excerpt": "", "status": "open",
         "severity": None},
    ]
    p = _make_guide(tmp_path, items=items, media_path="D:/m.mp4")
    r = gui_api_obj.refine_review_load_detections(str(p))
    assert r["success"] is True and r["count"] == 1
    d = r["detections"][0]
    assert d["category"] == "suspected_missed_speech"
    assert d["timing"] == "00:00:01,000 --> 00:00:02,000"
    assert r["media_path"] == "D:/m.mp4"


def test_review_load_detections_media_path_absent(gui_api_obj, tmp_path):
    """media_path 空串/缺席 → None（前端对话框兜底分支）。"""
    p = _make_guide(tmp_path, items=[{"index": 1,
        "timing": "00:00:01,000 --> 00:00:02,000", "category": "untranslated",
        "message": "整段未翻译", "current_text": "[未翻译]",
        "source_excerpt": "", "status": "open", "severity": None}],
        media_path="")
    r = gui_api_obj.refine_review_load_detections(str(p))
    assert r["success"] is True and r["media_path"] is None


def test_review_load_detections_rejects_non_guide(gui_api_obj, tmp_path):
    """白名单外后缀 → error（守卫链不因批 3 放宽）。"""
    p = tmp_path / "demo.json"
    p.write_text("{}", encoding="utf-8")
    r = gui_api_obj.refine_review_load_detections(str(p))
    assert r["success"] is False


def test_codec_direct_two_matrices_diverge():
    """批 3 技术债 e 语义差异钉：同一输入在两套常量下判定分叉。
    实测分叉点：m4a 容器（ext 集差异：仅 audio-preview 集）；
    .mp4+mp3 音频（audio 集差异：仅 review 集）。两套常量均为
    TranslateAPI 类属性（模块级不可 import）。"""
    from subtransjav.webview_gui.api import TranslateAPI, _codec_direct
    ap = TranslateAPI._AUDIO_PREVIEW_DIRECT_EXTS
    av = TranslateAPI._AUDIO_PREVIEW_DIRECT_VIDEO
    aa = TranslateAPI._AUDIO_PREVIEW_DIRECT_AUDIO
    rv = TranslateAPI._REVIEW_DIRECT_EXTS
    rvid = TranslateAPI._REVIEW_DIRECT_VIDEO
    ra = TranslateAPI._REVIEW_DIRECT_AUDIO
    m4a = (".m4a", {"video": "", "audio": "aac"})
    assert _codec_direct(m4a[0], m4a[1], ap, av, aa) is True
    assert _codec_direct(m4a[0], m4a[1], rv, rvid, ra) is False
    mp4_mp3 = (".mp4", {"video": "h264", "audio": "mp3"})
    assert _codec_direct(mp4_mp3[0], mp4_mp3[1], rv, rvid, ra) is True
    assert _codec_direct(mp4_mp3[0], mp4_mp3[1], ap, av, aa) is False


def test_fs_utils_atomic_write_and_backup_suffix(tmp_path):
    """fs_utils 收口（批 3 技术债 a/b）：原子写成功+无残留+BACKUP_SUFFIX。"""
    from subtransjav.refine import fs_utils
    p = tmp_path / "x.srt"
    fs_utils._atomic_write_text(str(p), "内容", suffix=".srt.tmp")
    assert p.read_text(encoding="utf-8") == "内容"
    assert not list(tmp_path.glob("*.tmp")), "原子写不得留 tmp 残留"
    assert fs_utils.BACKUP_SUFFIX == ".bak.srt"


# ---------------------------------------------------------------------------
# 批1a（D2026-1002-12）：角色卡目录持久化 + 审计①校对保存收口
# 持久化文件一律经 SUBTRANSJAV_DATA_ROOT 隔离到 tmp，绝不写真实仓库 config。
# ---------------------------------------------------------------------------

@pytest.fixture()
def isolated_user_dirs(tmp_path, monkeypatch):
    """把数据根指向 tmp（env 通道现读），user_dirs.json 隔离落盘。"""
    root = tmp_path / "dataroot"
    root.mkdir()
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(root))
    return root


def test_ensure_template_dir_default_persisted_then_config(
        gui_api_obj, isolated_user_dirs, monkeypatch):
    """缺省目录解析（批1a 件3）：user_dirs.templates_dir → 数据根
    config/templates 两级依次回落。"""
    import subtransjav.webview_gui.api as api_mod
    import subtransjav.webview_gui.user_dirs as ud
    from subtransjav.refine.config import default_templates_dir
    # 未持久化 → 服务端默认目录
    assert os.path.normcase(api_mod._ensure_template_dir(None)) == \
        os.path.normcase(str(Path(default_templates_dir()).resolve()))
    # 持久化后 → 持久值优先
    d = isolated_user_dirs / "tpl"
    d.mkdir()
    monkeypatch.setattr(ud, "get_templates_dir", lambda: str(d))
    monkeypatch.setattr(ud, "get_registered_dirs",
                        lambda: [ud.normalize_key(str(d))])
    assert os.path.normcase(api_mod._ensure_template_dir(None)) == \
        os.path.normcase(str(d.resolve()))


def test_ensure_template_dir_persistent_registered_dir_allowed(
        gui_api_obj, tmp_path, monkeypatch):
    """显式传入持久登记目录 → 放行（重启仍生效语义，件3）。"""
    import subtransjav.webview_gui.api as api_mod
    import subtransjav.webview_gui.user_dirs as ud
    d = tmp_path / "persisted_cards"
    d.mkdir()
    monkeypatch.setattr(ud, "get_registered_dirs",
                        lambda: [ud.normalize_key(str(d))])
    assert os.path.normcase(api_mod._ensure_template_dir(str(d))) == \
        os.path.normcase(str(d.resolve()))


def test_ensure_template_dir_session_registered_dir_still_allowed(
        gui_api_obj, tmp_path):
    """显式传入会话登记目录 → 放行（既有语义保留，不因持久化收窄）。"""
    import subtransjav.webview_gui.api as api_mod
    d = tmp_path / "session_cards"
    d.mkdir()
    register_session_paths([str(d)])
    assert os.path.normcase(api_mod._ensure_template_dir(str(d))) == \
        os.path.normcase(str(d.resolve()))


def test_ensure_template_dir_unregistered_dir_still_rejected(
        gui_api_obj, tmp_path, monkeypatch):
    """四类拒绝对照：目录在白名单锚内但未登记（会话+持久均无）→ 拒绝
    （持久化改革不放宽登记语义）。"""
    import subtransjav.webview_gui.api as api_mod
    import subtransjav.webview_gui.user_dirs as ud
    monkeypatch.setattr(ud, "get_registered_dirs", lambda: [])
    monkeypatch.setattr(ud, "get_templates_dir", lambda: None)
    d = tmp_path / "unregistered_cards"
    d.mkdir()
    with pytest.raises(ValueError):
        api_mod._ensure_template_dir(str(d))
    r = gui_api_obj.refine_list_templates(str(d))
    assert r["success"] is False


def test_refine_pick_folder_persists_and_sets_templates_dir(
        gui_api_obj, isolated_user_dirs, monkeypatch, tmp_path):
    """件3 e2e：refine_pick_folder('templates') → 会话登记 + 持久
    registered_dirs + set_templates_dir；此后缺省目录跟随持久值。"""
    import subtransjav.webview_gui.api as api_mod
    import subtransjav.webview_gui.user_dirs as ud
    picked = tmp_path / "picked"
    picked.mkdir()

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(picked)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.refine_pick_folder("templates")
    assert r["success"] is True
    data = ud.load()
    assert ud.normalize_key(str(picked)) in data["registered_dirs"]
    assert data["templates_dir"] == ud.normalize_key(str(picked))
    assert os.path.normcase(api_mod._ensure_template_dir(None)) == \
        ud.normalize_key(str(picked))


# ---------------------------------------------------------------------------
# 批1a 件5：审计①校对保存收口
# 放行 = 动态根 ∪ 持久登记 ∪ 会话登记；"E 盘"目录全部 monkeypatch 模拟。
# ---------------------------------------------------------------------------

def test_review_save_registered_e_drive_dir_ok(gui_api_obj, monkeypatch):
    """持久登记的"E 盘"目录内文件保存放行（不依赖真实磁盘：
    持久登记 monkeypatch + 原子写捕获，验证裁决与落盘点）。"""
    if os.name != "nt":
        pytest.skip("盘符语义仅 Windows")
    import subtransjav.webview_gui.api as api_mod
    import subtransjav.webview_gui.user_dirs as ud
    fake_e = r"E:\SubJAV"
    monkeypatch.setattr(ud, "get_registered_dirs",
                        lambda: [ud.normalize_key(fake_e)])
    writes: list[tuple[str, str]] = []
    monkeypatch.setattr(api_mod, "_write_srt_atomic",
                        lambda p, text: writes.append((p, text)))
    blocks = [{"index": 1, "start_ms": 1000, "end_ms": 2000, "text": "T"}]
    r = gui_api_obj.refine_review_save_srt(
        os.path.join(fake_e, "a.srt"), blocks)
    assert r["success"] is True
    assert len(writes) == 1
    assert os.path.normcase(writes[0][0]) == \
        os.path.normcase(os.path.join(fake_e, "a.srt")), \
        "落盘点必须是登记目录内路径"


def test_review_saveas_registered_e_drive_ok(gui_api_obj, monkeypatch):
    """另存为：目标在持久登记"E 盘"目录（不存在文件）→ 直接原子写放行。"""
    if os.name != "nt":
        pytest.skip("盘符语义仅 Windows")
    import subtransjav.webview_gui.api as api_mod
    import subtransjav.webview_gui.user_dirs as ud
    fake_e = r"E:\SubJAV"
    monkeypatch.setattr(ud, "get_registered_dirs",
                        lambda: [ud.normalize_key(fake_e)])
    writes: list[tuple[str, str]] = []
    monkeypatch.setattr(api_mod, "_write_srt_atomic",
                        lambda p, text: writes.append((p, text)))
    blocks = [{"index": 1, "start_ms": 1000, "end_ms": 2000, "text": "S"}]
    r = gui_api_obj.refine_review_saveas_srt(
        blocks, os.path.join(fake_e, "out.srt"))
    assert r["success"] is True and len(writes) == 1


def test_review_save_unregistered_outside_roots_rejected(gui_api_obj):
    """审计①主断言：白名单外且未登记（假盘符 Q:）→ 保存拒绝。"""
    blocks = [{"index": 1, "start_ms": 1000, "end_ms": 2000, "text": "T"}]
    r = gui_api_obj.refine_review_save_srt("Q:/somewhere/out.srt", blocks)
    assert r["success"] is False
    r2 = gui_api_obj.refine_review_saveas_srt(blocks, "Q:/somewhere/new.srt")
    assert r2["success"] is False


def test_review_save_allowed_session_fallback_branch(gui_api_obj, monkeypatch,
                                                     tmp_path):
    """会话登记兜底分支：_resolve_safe_path 拒绝但路径 ∈ 会话登记 → 放行
    （覆盖对话框/拖放登记的任意盘文件的保存路径）。"""
    import subtransjav.webview_gui.api as api_mod
    p = tmp_path / "s.srt"
    monkeypatch.setattr(
        api_mod, "SESSION_SELECTED_PATHS", {str(p.resolve())})

    def _always_reject(path, extra_roots=None):
        raise ValueError(f"路径不在允许的目录下: {path}")

    monkeypatch.setattr(api_mod, "_resolve_safe_path", _always_reject)
    assert api_mod._review_save_allowed(str(p)) == str(p.resolve())
    # 未登记同类路径仍拒绝
    with pytest.raises(ValueError):
        api_mod._review_save_allowed(str(tmp_path / "other.srt"))


# ---------------------------------------------------------------------------
# 2.6.1 批4（D2026-1002-12）：审计②写入端 sanitize / ③转码三件收口
# ---------------------------------------------------------------------------


def test_review_save_srt_sanitize_blank_line_roundtrip(gui_api_obj, tmp_path):
    """审计②写入端 sanitize：块内文本含空行/连续空白行 → 保存时压成单
    换行，重解析块数与文本逐字一致（不再裂出残块丢内容）。"""
    p = tmp_path / "a.srt"
    p.write_text("1\n00:00:01,000 --> 00:00:02,000\n原文\n", encoding="utf-8")
    blocks = [
        {"index": 1, "start_ms": 1000, "end_ms": 2000, "text": "行1\n\n行2"},
        {"index": 2, "start_ms": 3000, "end_ms": 4000, "text": "行3\r\n\r\n行4"},
    ]
    r = gui_api_obj.refine_review_save_srt(str(p), blocks)
    assert r["success"] is True and r["count"] == 2
    content = p.read_text(encoding="utf-8")
    # 块间恰好一个空行（无三连换行）、无尾部多余空行
    assert "\n\n\n" not in content
    assert content.endswith("\n") and not content.endswith("\n\n")
    loaded = gui_api_obj.refine_review_load_srt(str(p))
    assert loaded["success"] is True and loaded["count"] == 2
    assert loaded["blocks"][0]["text"] == "行1\n行2"
    assert loaded["blocks"][1]["text"] == "行3\n行4"


def test_transcode_sync_timeout_unlinks_partial(tmp_path, monkeypatch):
    """审计③a：超时 kill 路径清理半截产物（成功才保留，防 cache 误复用）。"""
    import subtransjav.webview_gui.api as api_mod
    out = tmp_path / "out.mp4"
    out.write_bytes(b"partial-bytes")
    clock = iter([0.0, 1.0, 999.0])

    class FakeProc:
        stdout = iter([b"out_time_ms=500000\n", b"out_time_ms=600000\n"])

        @staticmethod
        def kill() -> None:
            return None

    monkeypatch.setattr(api_mod.time, "monotonic", lambda: next(clock, 999.0))
    monkeypatch.setattr(api_mod.subprocess, "Popen",
                        lambda args, **kwargs: FakeProc())
    ok, err = api_mod._transcode_sync("/fake/ffmpeg", "in.mkv", str(out), 5.0)
    assert ok is False and err == "transcode timeout"
    assert not out.exists()


def test_transcode_sync_exception_unlinks_partial(tmp_path, monkeypatch):
    """审计③a：异常路径（wait 抛错）同样清理半截产物。"""
    import subtransjav.webview_gui.api as api_mod
    out = tmp_path / "out.mp4"
    out.write_bytes(b"partial-bytes")

    class FakeProc:
        stdout = iter([b"out_time_ms=1\n"])

        @staticmethod
        def kill() -> None:
            return None

        @staticmethod
        def wait(timeout=None) -> int:
            raise RuntimeError("boom")

    monkeypatch.setattr(api_mod.subprocess, "Popen",
                        lambda args, **kwargs: FakeProc())
    ok, err = api_mod._transcode_sync("/fake/ffmpeg", "in.mkv", str(out), 5.0)
    assert ok is False and "boom" in err
    assert not out.exists()


def test_transcode_sync_success_keeps_file(tmp_path, monkeypatch):
    """审计③a 对照：成功路径产物保留不误删。"""
    import subtransjav.webview_gui.api as api_mod
    out = tmp_path / "out.mp4"
    out.write_bytes(b"transcoded-bytes")

    class FakeProc:
        stdout = iter(())

        @staticmethod
        def wait(timeout=None) -> int:
            return 0

    monkeypatch.setattr(api_mod.time, "monotonic", lambda: 0.0)
    monkeypatch.setattr(api_mod.subprocess, "Popen",
                        lambda args, **kwargs: FakeProc())
    ok, err = api_mod._transcode_sync("/fake/ffmpeg", "in.mkv", str(out), 5.0)
    assert ok is True and err == ""
    assert out.exists()


def test_review_transcode_cache_integrity(gui_api_obj, monkeypatch, tmp_path):
    """审计③b：cache 命中前完整性校验——ffprobe 探不到正时长（半截件）
    不复用走重转码；探到正时长才 cached 复用。"""
    import hashlib

    import subtransjav.refine.audio_detect as ad
    import subtransjav.refine.config as cfg_mod
    import subtransjav.webview_gui.api as api_mod

    media = tmp_path / "ep01.mkv"
    media.write_bytes(b"fake-mkv")
    _install_fake_ffprobe(monkeypatch, video="hevc", audio="aac")
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(cfg_mod, "TEMP_DIR", str(tmp_path / "temp"))
    out_dir = tmp_path / "temp" / "review_transcode"
    out_dir.mkdir(parents=True)
    identity = f"{media}|{media.stat().st_mtime}|{media.stat().st_size}"
    digest = hashlib.sha256(identity.encode("utf-8", "replace")).hexdigest()[:12]
    out = out_dir / f"rt_{digest}.mp4"
    out.write_bytes(b"half-file")

    class SyncThread:
        def __init__(self, target=None, daemon=None, name=None):
            self._target = target
        def start(self):
            self._target()

    monkeypatch.setattr(api_mod.threading, "Thread", SyncThread)

    # 半截件：探测不到正时长 → 不复用，走重转码（worker 同步跑完）
    monkeypatch.setattr(gui_api_obj, "_review_media_duration",
                        lambda p: None if str(p).endswith(".mp4") else 100.0)
    r = gui_api_obj.refine_review_start_transcode(str(media))
    assert r["success"] is True and r.get("started") is True
    assert not r.get("cached")

    # 完整件：探测到正时长 → cached 复用
    monkeypatch.setattr(gui_api_obj, "_review_media_duration", lambda p: 30.0)
    r = gui_api_obj.refine_review_start_transcode(str(media))
    assert r["success"] is True and r.get("cached") is True
    assert r["path"] == str(out)


def test_review_transcode_inflight_lock(gui_api_obj, monkeypatch, tmp_path):
    """审计③d：per-media 在飞锁——重复调用幂等返回"转码中"，完成后移除。"""
    import subtransjav.refine.audio_detect as ad
    import subtransjav.refine.config as cfg_mod
    import subtransjav.webview_gui.api as api_mod

    media = tmp_path / "ep01.mkv"
    media.write_bytes(b"fake-mkv")
    _install_fake_ffprobe(monkeypatch, video="hevc", audio="aac")
    monkeypatch.setattr(ad, "_find_ffmpeg", lambda: "/fake/ffmpeg")
    monkeypatch.setattr(cfg_mod, "TEMP_DIR", str(tmp_path / "temp"))
    monkeypatch.setattr(gui_api_obj, "_review_media_duration", lambda p: 10.0)

    key = api_mod.os.path.normcase(str(media))
    # 在飞中重复调用：幂等返回"转码中"
    api_mod._REVIEW_TRANSCODE_INFLIGHT.add(key)
    try:
        r = gui_api_obj.refine_review_start_transcode(str(media))
        assert r["success"] is False
        assert r["error"] == api_mod.msg("review_transcode_running")
    finally:
        api_mod._REVIEW_TRANSCODE_INFLIGHT.discard(key)

    # 正常完成（SyncThread 同步跑 worker）→ 在飞集合不含该 media
    class SyncThread:
        def __init__(self, target=None, daemon=None, name=None):
            self._target = target
        def start(self):
            self._target()

    monkeypatch.setattr(api_mod.threading, "Thread", SyncThread)
    r = gui_api_obj.refine_review_start_transcode(str(media))
    assert r["success"] is True
    assert key not in api_mod._REVIEW_TRANSCODE_INFLIGHT


# ---------------------------------------------------------------------------
# 2.6.3 批B（D2026-1003-01 ②）：ASR 下载器端点 + source 透传 + sources 摘要
# ---------------------------------------------------------------------------
def test_refine_asr_download_invalid_model_and_source(gui_api_obj):
    """model 白名单（support=="available"）与 source 白名单硬拒。"""
    got = gui_api_obj.refine_asr_download("nope")
    assert got["success"] is False and "未知或不可下载" in got["error"]
    got2 = gui_api_obj.refine_asr_download("qwen3-asr-1.7b")    # planned 不可下
    assert got2["success"] is False and "未知或不可下载" in got2["error"]
    got3 = gui_api_obj.refine_asr_download("whisper-large-v2", "bogus")
    assert got3["success"] is False and "非法下载源" in got3["error"]


def test_refine_asr_download_success_and_failure(gui_api_obj, monkeypatch,
                                                 tmp_path):
    from subtransjav.refine import asr_downloader as ad
    rec = {}

    def _fake(model, source="auto"):
        rec["args"] = (model, source)
        return str(tmp_path / "large-v2.pt")

    monkeypatch.setattr(ad, "download_asr_model", _fake)
    got = gui_api_obj.refine_asr_download("whisper-large-v2", "mirror")
    assert got["success"] is True
    assert got["path"] == str(tmp_path / "large-v2.pt")
    assert rec["args"] == ("whisper-large-v2", "mirror")

    def _busy(model, source="auto"):
        raise ad.AsrDownloadError("该模型已有下载进行中")

    monkeypatch.setattr(ad, "download_asr_model", _busy)
    got2 = gui_api_obj.refine_asr_download("whisper-large-v2")
    assert got2["success"] is False and "已有下载进行中" in got2["error"]

    def _checksum(model, source="auto"):
        raise ad.AsrChecksumError("SHA256 校验失败，已拒绝落位")

    monkeypatch.setattr(ad, "download_asr_model", _checksum)
    got3 = gui_api_obj.refine_asr_download("whisper-large-v2")
    assert got3["success"] is False and "SHA256" in got3["error"]


def test_refine_asr_download_progress_endpoint(gui_api_obj, monkeypatch):
    """进度端点形状：success + 快照同形透传（含 note 可见提示）；无记录
    success + 空。"""
    from subtransjav.refine import asr_downloader as ad
    monkeypatch.setattr(ad, "_ASR_DOWNLOAD_PROGRESS", {
        "whisper-large-v2": {
            "kind": "whisper-large-v2", "phase": "download",
            "downloaded": 5, "total": 10, "error": None,
            "note": "官方源不可达，已回退国内镜像"}})
    got = gui_api_obj.refine_asr_download_progress("whisper-large-v2")
    assert got["success"] is True
    assert got["phase"] == "download"
    assert got["downloaded"] == 5 and got["total"] == 10
    assert got["note"] == "官方源不可达，已回退国内镜像"
    empty = gui_api_obj.refine_asr_download_progress("nope")
    assert empty == {"success": True}


def test_refine_dict_download_source_passthrough(gui_api_obj, monkeypatch):
    """source 透传（D2026-1003-06 条件②）：official/mirror 双参调用；
    auto/非法值按 auto 语义（2.7.3 件⑤ 会话制：worker 统一
    download_dict(kind, source=..., stop_event=...) 调用，source 语义
    不变——既有 mock 改 kwargs 兼容形，非法值仍由 download_dict 按
    auto 处理）。"""
    from subtransjav.refine import dict_manager as dm
    rec = {}

    def _fake(kind, *args, **kwargs):
        rec["source"] = kwargs.get("source", "auto")
        return "x"

    monkeypatch.setattr(dm, "download_dict", _fake)
    assert gui_api_obj.refine_dict_download("sudachi")["success"] is True
    _dict_dl_wait_idle("sudachi")       # 等 worker 跑完再读 rec（会话制异步）
    assert rec["source"] == "auto"
    assert gui_api_obj.refine_dict_download("sudachi", "official")["success"] is True
    _dict_dl_wait_idle("sudachi")
    assert rec["source"] == "official"
    assert gui_api_obj.refine_dict_download("sudachi", "mirror")["success"] is True
    _dict_dl_wait_idle("sudachi")
    assert rec["source"] == "mirror"
    assert gui_api_obj.refine_dict_download("sudachi", "bogus")["success"] is True
    _dict_dl_wait_idle("sudachi")
    assert rec["source"] == "bogus"


def test_refine_dict_status_sources_summary(gui_api_obj, monkeypatch, tmp_path):
    """dict_status 增 sources 摘要键（追加式，既有 shape 断言不删）。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    got = gui_api_obj.refine_dict_status()
    assert got["success"] is True
    assert got["sources"]["sudachi_full"]["has_mirror"] is True
    assert got["sources"]["sudachi"]["has_mirror"] is True
    assert got["sources"]["sudachi"]["has_official"] is True


# ---------------------------------------------------------------------------
# 2.7.1（D2026-1005-01 承接批，评议 R5）：refine_asr_status 探测快照缓存
# + 三落位枚举/三分类透出（models_hf/triage/probe_cached）
# ---------------------------------------------------------------------------

def test_refine_asr_status_probe_cache_roundtrip(gui_api_obj, tmp_path,
                                                 monkeypatch):
    """非 force 读快照立即返回（probe_cached=True）并回填 decorations；
    force=True 绕过缓存重新探测；超龄缓存不命中。
    设置存储隔离到 tmp：本机真实 refine_stage_settings.json 可能含
    media_crosscheck_enabled="1" 等用户态（2026-10-05 真机污染案例，
    crosscheck 断言不得依赖本机文件）。"""
    from subtransjav.refine import asr_env
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(tmp_path / "refine_stage_settings.json"))
    cache = tmp_path / "asr_probe_cache.json"
    monkeypatch.setattr(gui_api_obj, "_asr_probe_cache_path",
                        lambda: str(cache))
    calls = []
    real_probe = asr_env.probe_asr_env

    def _probe(asr_python_setting=""):
        calls.append(1)
        return real_probe(asr_python_setting="")

    monkeypatch.setattr(asr_env, "probe_asr_env", _probe)
    r1 = gui_api_obj.refine_asr_status()
    assert r1["success"] is True and r1["probe_cached"] is False
    assert len(calls) == 1
    assert cache.is_file()
    r2 = gui_api_obj.refine_asr_status()
    assert r2["success"] is True and r2["probe_cached"] is True
    assert len(calls) == 1                       # 快照命中，不再探测
    assert r2["models_dir"] == asr_env.ASR_MODELS_ROOT
    assert r2["crosscheck_enabled"] is False
    r3 = gui_api_obj.refine_asr_status(force=True)
    assert r3["probe_cached"] is False and len(calls) == 2
    # 超龄失效
    data = json.loads(cache.read_text(encoding="utf-8"))
    data["timestamp"] -= 601
    cache.write_text(json.dumps(data), encoding="utf-8")
    r4 = gui_api_obj.refine_asr_status()
    assert r4["probe_cached"] is False and len(calls) == 3


def test_refine_asr_status_passthrough_triage_and_hf(gui_api_obj, tmp_path,
                                                     monkeypatch):
    """probe 结果的 triage/stderr_tail/models_hf/ffmpeg_path 原样透出。
    设置存储隔离到 tmp（同 2026-10-05 本机设置态污染案例，防复发）。"""
    from subtransjav.refine import asr_env
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(tmp_path / "refine_stage_settings.json"))

    def _probe(asr_python_setting=""):
        return {"available": False, "reason": "x", "models": [],
                "models_hf": [{"name": "Org/m", "source": "hf-hub",
                               "path": "p", "bytes": 1,
                               "format": "ct2",
                               "backend_state": "adapter-needed"}],
                "ffmpeg": False, "ffmpeg_path": "",
                "triage": "module-missing", "stderr_tail": "tail..."}
    monkeypatch.setattr(asr_env, "probe_asr_env", _probe)
    monkeypatch.setattr(gui_api_obj, "_asr_probe_cache_path",
                        lambda: str(tmp_path / "asr_probe_cache.json"))
    r = gui_api_obj.refine_asr_status()
    assert r["triage"] == "module-missing"
    assert r["stderr_tail"] == "tail..."
    assert r["models_hf"][0]["backend_state"] == "adapter-needed"
    assert r["ffmpeg_path"] == ""


# ---------------------------------------------------------------------------
# 2.7.2 件1（D2026-1005-02）：字幕入口点亮——对话框 filter 直测钉 /
# select_srt_folder 提示分支 / on_drop_event 白名单放开
# ---------------------------------------------------------------------------

def test_file_type_subtitle_filter_parse_pin():
    """直测钉（C2）：新 filter 串必须被 pywebview parse_file_type 解析为预期元组。

    旧串描述段含 `/`（"ASS/SSA/VTT"）被 parse_file_type 正则拒绝抛
    ValueError → create_file_dialog 整体失败（「添加文件」按钮挂死）。
    断言返回值元组内容，不只断言不抛。
    实跑面=gui-probe/本地（daily CI 两腿无 pywebview，importorskip 跳过）。
    """
    from webview.util import parse_file_type

    from subtransjav.webview_gui.strings import MSG
    assert parse_file_type(MSG["file_type_subtitle"]) == \
        ("ASS SSA VTT 字幕", "*.ass;*.ssa;*.vtt")


def test_select_srt_folder_subtitle_only_hint_branch(gui_api_obj, monkeypatch, tmp_path):
    """2.7.2 件1：目录只有 ASS/SSA/VTT 无 .srt → 针对性提示分支（复用 message 通道）。"""
    import subtransjav.webview_gui.api as api_mod
    from subtransjav.webview_gui.strings import msg
    (tmp_path / "a.ass").write_text("x", encoding="utf-8")
    (tmp_path / "b.vtt").write_text("x", encoding="utf-8")

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(tmp_path)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.select_srt_folder()
    assert r["success"] is False
    assert r["message"] == msg("no_srt_but_subtitle_in_folder")


def test_select_srt_folder_srt_regression(gui_api_obj, monkeypatch, tmp_path):
    """回归钉：目录含 .srt 时行为与改动前一致（收编 .srt，不受新分支影响）。"""
    (tmp_path / "a.srt").write_text("x", encoding="utf-8")
    (tmp_path / "a.ass").write_text("x", encoding="utf-8")
    import subtransjav.webview_gui.api as api_mod

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(tmp_path)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.select_srt_folder()
    assert r["success"] is True
    assert str(tmp_path / "a.srt") in r["paths"]
    assert str(tmp_path / "a.ass") not in r["paths"]


def test_select_srt_folder_empty_keeps_no_srt_channel(gui_api_obj, monkeypatch, tmp_path):
    """目录既无 .srt 也无 ASS/SSA/VTT → 走原 no_srt_in_folder 通道不变。"""
    import subtransjav.webview_gui.api as api_mod
    from subtransjav.webview_gui.strings import msg

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(tmp_path)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.select_srt_folder()
    assert r["success"] is False
    assert r["message"] == msg("no_srt_in_folder")


def test_on_drop_event_subtitle_exts_whitelist(gui_api_obj, monkeypatch):
    """2.7.2 件1：拖拽白名单放行 .ass/.ssa/.vtt（.srt 原路径不变），.txt 拒收。"""
    import webview

    from subtransjav.webview_gui.main import on_drop_event

    scripts = []

    class FakeWin:
        @staticmethod
        def evaluate_js(script):
            scripts.append(script)

    # on_drop_event 内延迟 import webview 取同一模块对象，patch 其 windows 即可
    monkeypatch.setattr(webview, "windows", [FakeWin()])
    event = {"dataTransfer": {"files": [
        {"pywebviewFullPath": "D:/x/a.srt"},
        {"pywebviewFullPath": "D:/x/b.ass"},
        {"pywebviewFullPath": "D:/x/c.ssa"},
        {"pywebviewFullPath": "D:/x/d.vtt"},
        {"pywebviewFullPath": "D:/x/e.txt"},
    ]}}
    on_drop_event(event)
    assert len(scripts) == 1, "放行文件应汇聚为一次 ReviewUI 转发"
    for name in ("a.srt", "b.ass", "c.ssa", "d.vtt"):
        assert name in scripts[0], f"{name} 应被放行"
    assert "e.txt" not in scripts[0], ".txt 必须被拒收"


def test_select_srt_folder_subtitle_exts_pinned_to_drop_whitelist():
    """防漂移钉（code-review 跟进）：api.py select_srt_folder 的字幕后缀元组
    与 main.py on_drop_event allowed_exts 的字幕后缀一致。

    全链 4 处字面量（main.py allowed_exts / app.js allowedSubtitleExts /
    api.py 提示分支元组 / strings.py filter 串）中 api.py 元组此前唯一无守护；
    源码文本提取判定（沿用 test_gui_js_static 静态钉惯例）。api 元组不含 .srt
    属刻意设计（.srt 由 glob 收编），故比对对象=main 放行集字幕子集去 .srt。
    """
    root = Path(__file__).resolve().parents[1]
    api_src = (root / "subtransjav" / "webview_gui" / "api.py").read_text(encoding="utf-8")
    main_src = (root / "subtransjav" / "webview_gui" / "main.py").read_text(encoding="utf-8")

    body = api_src.split("def select_srt_folder", 1)[1] \
                  .split("def scan_srt_folder", 1)[0]
    m = re.search(r"suffix\.lower\(\) in \(([^)]*)\)", body)
    assert m, "api.py select_srt_folder 未找到字幕后缀元组"
    api_exts = set(re.findall(r'"(\.[a-z0-9]+)"', m.group(1)))
    assert api_exts, "api.py 字幕后缀元组解析为空"

    m2 = re.search(r"allowed_exts\s*=\s*\(([^)]*)\)", main_src)
    assert m2, "main.py 未找到 allowed_exts 元组"
    main_exts = set(re.findall(r"'(\.[a-z0-9]+)'", m2.group(1)))
    assert main_exts, "main.py allowed_exts 解析为空"

    assert api_exts == {".ass", ".ssa", ".vtt"}, \
        f"select_srt_folder 字幕后缀漂移: {sorted(api_exts)}"
    subtitle_subset = main_exts & {".srt", ".ass", ".ssa", ".vtt"}
    assert subtitle_subset == {".srt", ".ass", ".ssa", ".vtt"}, \
        f"main.py 放行集字幕子集漂移: {sorted(subtitle_subset)}"
    assert api_exts == subtitle_subset - {".srt"}, \
        "api.py 目录提示后缀与 main.py 拖放白名单字幕后缀不一致（防漂移）"


# ---------------------------------------------------------------------------
# 2.7.3 件④（D2026-1005）：文件夹收编智能过滤——keep/skip 分流 /
# 全滤光第四分支 / bak 排除优先 / scan skipped_count 透传
# ---------------------------------------------------------------------------

def test_select_srt_folder_mixed_dir_net_set_and_skipped(gui_api_obj, monkeypatch, tmp_path):
    """混合目录：paths=净集（流水线产物被滤），skipped 明细+计数齐全。"""
    import subtransjav.webview_gui.api as api_mod

    names = ["movie.srt", "a.ja.pass1.srt", "a.ja.pass2.srt",
             "a_refine_A.srt", "a_final_cn.srt", "a.ja.merged.subtransjav.srt"]
    for n in names:
        (tmp_path / n).write_text("x", encoding="utf-8")

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(tmp_path)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.select_srt_folder()
    assert r["success"] is True
    # 净集：普通件 + merged 产成品（不排）
    assert str(tmp_path / "movie.srt") in r["paths"]
    assert str(tmp_path / "a.ja.merged.subtransjav.srt") in r["paths"]
    assert str(tmp_path / "a.ja.pass1.srt") not in r["paths"]
    assert str(tmp_path / "a_refine_A.srt") not in r["paths"]
    assert str(tmp_path / "a_final_cn.srt") not in r["paths"]
    assert len(r["paths"]) == 2
    assert sorted(r["skipped"]) == ["a.ja.pass1.srt", "a.ja.pass2.srt",
                                    "a_final_cn.srt", "a_refine_A.srt"]
    assert r["skipped_count"] == 4


def test_select_srt_folder_all_pipeline_fourth_branch(gui_api_obj, monkeypatch, tmp_path):
    """全滤光：目录确有 .srt 但全是流水线产物 → 第四分支 message+skipped。"""
    import subtransjav.webview_gui.api as api_mod
    from subtransjav.webview_gui.strings import msg
    for n in ("a.ja.pass1.srt", "a.ja.pass2.srt", "a_refine_A.srt", "a_final_cn.srt"):
        (tmp_path / n).write_text("x", encoding="utf-8")

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(tmp_path)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.select_srt_folder()
    assert r["success"] is False
    assert r["message"] == msg("folder_all_skipped_pipeline")
    assert sorted(r["skipped"]) == ["a.ja.pass1.srt", "a.ja.pass2.srt",
                                    "a_final_cn.srt", "a_refine_A.srt"]


def test_select_srt_folder_all_pipeline_branch_precedes_ass_branch(gui_api_obj, monkeypatch, tmp_path):
    """第四分支优先于 ass 系分支：目录有流水线 .srt + .ass → 如实诊断而非提示 ass。"""
    import subtransjav.webview_gui.api as api_mod
    from subtransjav.webview_gui.strings import msg
    (tmp_path / "a.ja.pass1.srt").write_text("x", encoding="utf-8")
    (tmp_path / "a.ass").write_text("x", encoding="utf-8")

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(tmp_path)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.select_srt_folder()
    assert r["success"] is False
    assert r["message"] == msg("folder_all_skipped_pipeline")


def test_select_srt_folder_bak_exclusion_still_first(gui_api_obj, monkeypatch, tmp_path):
    """bak 排除仍优先：bak-only 目录不走第四分支，保持原 no_srt_in_folder 通道。"""
    import subtransjav.webview_gui.api as api_mod
    from subtransjav.webview_gui.strings import msg
    (tmp_path / "a.bak.srt").write_text("x", encoding="utf-8")

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(tmp_path)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.select_srt_folder()
    assert r["success"] is False
    assert r["message"] == msg("no_srt_in_folder")
    assert "skipped" not in r


def test_select_srt_folder_bak_filtered_before_pipeline_split(gui_api_obj, monkeypatch, tmp_path):
    """bak 排除 + 流水线过滤共存：bak 不计入 skipped，净件照常收编。"""
    import subtransjav.webview_gui.api as api_mod
    (tmp_path / "movie.srt").write_text("x", encoding="utf-8")
    (tmp_path / "movie.bak.srt").write_text("x", encoding="utf-8")
    (tmp_path / "movie.ja.pass1.srt").write_text("x", encoding="utf-8")

    class FakeWin:
        @staticmethod
        def create_file_dialog(*args, **kwargs):
            return [str(tmp_path)]

    monkeypatch.setattr(api_mod.webview, "windows", [FakeWin()])
    r = gui_api_obj.select_srt_folder()
    assert r["success"] is True
    assert r["paths"] == [str(tmp_path / "movie.srt")]
    assert r["skipped"] == ["movie.ja.pass1.srt"]
    assert r["skipped_count"] == 1


def test_scan_srt_folder_skipped_count_passthrough(gui_api_obj, monkeypatch, tmp_path):
    """scan_srt_folder：summary.skipped_count 透传（既有 summary 键不动）。"""
    (tmp_path / "movie.srt").write_text("x", encoding="utf-8")
    (tmp_path / "a.ja.pass1.srt").write_text("x", encoding="utf-8")
    (tmp_path / "a_final_cn.srt").write_text("x", encoding="utf-8")

    r = gui_api_obj.scan_srt_folder(str(tmp_path), recursive=False)
    assert r["success"] is True
    assert r["summary"]["count"] == 3          # find_srt_files 默认口径不变
    assert r["summary"]["skipped_count"] == 2  # pass1 + _final_cn
    assert "total_size" in r["summary"] and "dirs" in r["summary"]


# ---------------------------------------------------------------------------
# 2.7.4 件2（D2026-1007-01）：试听媒体路径自动推断 + 失效重建 + GUI 持久化
# 四层优先级：①请求 override > ②guide media_path（有效时）> ③持久化 KV
# > ④同目录推断（fail-closed 时长守卫）；结构化 error_key 四态。
# ---------------------------------------------------------------------------

def test_strip_stem_suffixes_public_export():
    """剥链公共名导出（唯一实现，禁第二份）：owner 实名样本 + 中文/日语样本。"""
    import subtransjav.refine.asr_meta as am
    from subtransjav.refine.asr_meta import strip_stem_suffixes
    # owner 实名样本：4k2.me@mida-559ja.merged.whisperjav_质量报告导读.json
    # → 剥导读后缀 + 管线后缀 → 4k2.me@mida-559ja.merged
    assert strip_stem_suffixes("4k2.me@mida-559ja.merged.whisperjav") \
        == "4k2.me@mida-559ja.merged"
    assert strip_stem_suffixes("song.ja.whisperjav") == "song"
    assert strip_stem_suffixes("第01话.ja") == "第01话"
    assert strip_stem_suffixes("第01话.ja.whisperjav") == "第01话"
    assert strip_stem_suffixes("plain") == "plain"
    # 导出完整性：旧私有名零残留（唯一内部调用点已同步更新）
    assert "_strip_stem_suffixes" not in dir(am)


def _make_video(tmp_path: Path, name: str) -> Path:
    p = tmp_path / name
    p.write_bytes(b"fake-media")
    return p


def test_preview_infer_unique_hit_adopted(gui_api_obj, monkeypatch, tmp_path):
    """④ 唯一命中采用：导读无 media_path、同目录同名 mp4 → inferred 采纳
    （时长守卫通过：3600s ≥ clip_end+容差），direct 直播。"""
    _install_fake_ffprobe(monkeypatch, video="h264", audio="aac")
    media = _make_video(tmp_path, "ep09.mp4")
    guide = _make_guide(tmp_path, stem="ep09")
    r = gui_api_obj.refine_audio_preview(str(guide), 10.0, 12.0)
    assert r["ok"] is True and r["mode"] == "direct"
    assert r["media_path"] == str(media)
    assert r["media_source"] == "inferred"


def test_preview_infer_multi_hit_lists_candidates(gui_api_obj, monkeypatch,
                                                  tmp_path):
    """多命中 → no_candidate + 候选文件名列表（评议员条件①）。"""
    _install_fake_ffprobe(monkeypatch)
    _make_video(tmp_path, "ep10.mp4")
    _make_video(tmp_path, "ep10.mkv")
    guide = _make_guide(tmp_path, stem="ep10")
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False and r["error_key"] == "no_candidate"
    assert sorted(r["candidates"]) == ["ep10.mkv", "ep10.mp4"]
    assert "ep10.mp4" in r["error"]


def test_preview_infer_zero_hit_graceful_degrade(gui_api_obj, monkeypatch,
                                                 tmp_path):
    """零命中 → no_candidate 空候选（.ja 过度剥离边缘优雅降级：剥链后
    stem="song"，同目录仅 song.ja.mp4 不误配）。"""
    _install_fake_ffprobe(monkeypatch)
    _make_video(tmp_path, "song.ja.mp4")
    guide = _make_guide(tmp_path, stem="song.ja.whisperjav")
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False and r["error_key"] == "no_candidate"
    assert r["candidates"] == []


def test_preview_infer_duration_mismatch_rejected(gui_api_obj, monkeypatch,
                                                  tmp_path):
    """时长不符拒绝（fail-closed）：媒体 10s，clip_end=30.5 > 10+max(5,1%)。"""
    _install_fake_ffprobe(monkeypatch, duration_s=10.0)
    _make_video(tmp_path, "ep11.mp4")
    guide = _make_guide(tmp_path, stem="ep11")
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 30.0)
    assert r["ok"] is False and r["error_key"] == "duration_mismatch"
    assert r["candidates"] == ["ep11.mp4"]


def test_preview_infer_ffprobe_fail_rejected(gui_api_obj, monkeypatch,
                                             tmp_path):
    """ffprobe 探测失败拒绝（fail-closed）：rc≠0 → verify_failed。"""
    import subtransjav.webview_gui.api as api_mod
    _make_video(tmp_path, "ep12.mp4")
    guide = _make_guide(tmp_path, stem="ep12")
    monkeypatch.setattr(api_mod.shutil, "which",
                        lambda name: "/fake/ffprobe"
                        if name == "ffprobe" else None)
    monkeypatch.setattr(
        api_mod.subprocess, "run",
        lambda args, **kw: SimpleNamespace(returncode=1, stdout=b"",
                                           stderr=b""))
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False and r["error_key"] == "verify_failed"
    assert r["candidates"] == ["ep12.mp4"]


def test_preview_layer2_invalid_falls_to_path_invalid(gui_api_obj,
                                                      monkeypatch, tmp_path):
    """已有路径失效：guide media 指向不存在文件且零候选 → path_invalid。"""
    _install_fake_ffprobe(monkeypatch)
    guide = _make_guide(tmp_path, media_path=str(tmp_path / "gone.mp4"),
                        stem="ep13")
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False and r["error_key"] == "path_invalid"
    assert "gone.mp4" in r["error"]
    assert r["candidates"] == []


def test_preview_layer2_invalid_falls_to_infer_success(gui_api_obj,
                                                       monkeypatch, tmp_path):
    """②失效落 ④：guide media 指向不存在文件但推断唯一命中 → 采用推断
    （不自动覆盖的是【有效】已有路径；无效路径被推断替换，owner 裁定）。"""
    _install_fake_ffprobe(monkeypatch, video="h264", audio="aac")
    media = _make_video(tmp_path, "ep14.mp4")
    guide = _make_guide(tmp_path, media_path=str(tmp_path / "dead.mp4"),
                        stem="ep14")
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is True and r["media_source"] == "inferred"
    assert r["media_path"] == str(media)


def test_preview_persisted_layer_and_priority(gui_api_obj, monkeypatch,
                                              tmp_path):
    """③ 持久化层 + 优先级钉：③ 压 ④；② 有效压 ③；① override 压一切。
    settings 文件 monkeypatch 到 tmp（防本机 refine_stage_settings.json
    污染，沿既有隔离先例）。"""
    settings_path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(settings_path))
    _install_fake_ffprobe(monkeypatch, video="h264", audio="aac")
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    persisted_media = other_dir / "movie.mp4"
    persisted_media.write_bytes(b"fake")
    _make_video(tmp_path, "ep15.mp4")   # ④ 会命中——验证 ③ 优先于 ④
    guide = _make_guide(tmp_path, stem="ep15")
    w = gui_api_obj.refine_save_media_override(str(guide), str(persisted_media))
    assert w["success"] is True
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is True and r["media_source"] == "persisted"
    assert r["media_path"] == str(persisted_media)

    # ② 有效（文件存在+ffprobe 可读）压过 ③（不自动覆盖有效已有路径）
    guide2_media = _make_video(tmp_path, "ep15b.mp4")
    guide2 = _make_guide(tmp_path, media_path=str(guide2_media), stem="ep15b")
    gui_api_obj.refine_save_media_override(str(guide2), str(persisted_media))
    r2 = gui_api_obj.refine_audio_preview(str(guide2), 0.0, 2.0)
    assert r2["ok"] is True and r2["media_source"] == "guide"
    assert r2["media_path"] == str(guide2_media)

    # ① 请求 override 压一切
    r3 = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0,
                                          media_override=str(persisted_media))
    assert r3["media_source"] == "override"


def test_preview_override_lru_cap_and_delete(gui_api_obj, monkeypatch,
                                             tmp_path):
    """media_overrides LRU 上限 50：超限淘汰最旧、重写触尾、空串删除。"""
    settings_path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(settings_path))
    guides = [_make_guide(tmp_path, stem=f"lru{i:02d}") for i in range(51)]
    for i, g in enumerate(guides[:50]):
        assert gui_api_obj.refine_save_media_override(
            str(g), f"X:/m{i}.mp4")["success"]
    # 重写最旧键 → 触尾（不再是最旧）
    gui_api_obj.refine_save_media_override(str(guides[0]), "X:/m0b.mp4")
    # 第 51 条写入 → 淘汰当前最旧（guides[1]）
    gui_api_obj.refine_save_media_override(str(guides[50]), "X:/m50.mp4")
    ov = gui_api_obj._load_media_overrides()
    assert len(ov) == 50
    assert gui_api_obj._media_override_key(str(guides[1])) not in ov
    assert ov[gui_api_obj._media_override_key(str(guides[0]))] == "X:/m0b.mp4"
    assert ov[gui_api_obj._media_override_key(str(guides[50]))] == "X:/m50.mp4"
    # 空串 = 删除该条
    gui_api_obj.refine_save_media_override(str(guides[2]), "")
    assert gui_api_obj._media_override_key(str(guides[2])) not in \
        gui_api_obj._load_media_overrides()


# ---------------------------------------------------------------------------
# 2.7.4 件B（D2026-1007-02）：试听推断 leveled 剥链 + 边界感知前缀兜底（C5）
# 共享剥链 asr_meta.strip_stem_suffixes 不动；api.py 内 _preview_stem_candidates
# 专用 leveled 候选（闭集插入 ".merged"），首个命中层裁决 + 全层零命中前缀兜底。
# ---------------------------------------------------------------------------

def test_preview_infer_leveled_level0_no_fallback(gui_api_obj, monkeypatch,
                                                  tmp_path):
    """C5-a：X.mp4 与 X.ja.merged.mp4 同目录，导读 X.ja.merged.whisperjav
    → level0（X.ja.merged）精确直配 X.ja.merged.mp4，不回退 X.mp4。"""
    _install_fake_ffprobe(monkeypatch, video="h264", audio="aac")
    _make_video(tmp_path, "X.mp4")
    merged = _make_video(tmp_path, "X.ja.merged.mp4")
    guide = _make_guide(tmp_path, stem="X.ja.merged.whisperjav")
    r = gui_api_obj.refine_audio_preview(str(guide), 10.0, 12.0)
    assert r["ok"] is True and r["media_source"] == "inferred"
    assert r["media_path"] == str(merged)


def test_preview_infer_prefix_boundary_blocks_extension_spoof(
        gui_api_obj, monkeypatch, tmp_path):
    """C5-b：stem="X"、目录仅 X.merged.mp4 → 前缀兜底不命中（'.' 边界
    防 "X" 误配 "X.merged.mp4" 扩展伪装）→ no_candidate 空候选。"""
    _install_fake_ffprobe(monkeypatch)
    _make_video(tmp_path, "X.merged.mp4")
    guide = _make_guide(tmp_path, stem="X")
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False and r["error_key"] == "no_candidate"
    assert r["candidates"] == []


def test_preview_infer_leveled_strip_merged_hits(gui_api_obj, monkeypatch,
                                                 tmp_path):
    """C5-c：目录仅 X.mp4，导读 X.ja.merged.whisperjav（共享剥链停于
    X.ja.merged）→ leveled 剥 ".merged" 至 X → 命中 X.mp4。"""
    _install_fake_ffprobe(monkeypatch, video="h264", audio="aac")
    media = _make_video(tmp_path, "X.mp4")
    guide = _make_guide(tmp_path, stem="X.ja.merged.whisperjav")
    r = gui_api_obj.refine_audio_preview(str(guide), 10.0, 12.0)
    assert r["ok"] is True and r["media_source"] == "inferred"
    assert r["media_path"] == str(media)


def test_preview_infer_legacy_path_no_regression(gui_api_obj, monkeypatch,
                                                 tmp_path):
    """C5-d：老路径导读 X.ja.whisperjav（level0=X）仍直配 X.mp4，
    leveled 改造零回退。"""
    _install_fake_ffprobe(monkeypatch, video="h264", audio="aac")
    media = _make_video(tmp_path, "X.mp4")
    guide = _make_guide(tmp_path, stem="X.ja.whisperjav")
    r = gui_api_obj.refine_audio_preview(str(guide), 10.0, 12.0)
    assert r["ok"] is True and r["media_source"] == "inferred"
    assert r["media_path"] == str(media)


def test_preview_infer_leveled_multi_hit_fail_closed(gui_api_obj, monkeypatch,
                                                     tmp_path):
    """C5-e：leveled 命中层多候选（X.mp4 + X.mkv）→ no_candidate 带候选
    列表（fail-closed：不向更深层回退，也不落前缀兜底）。"""
    _install_fake_ffprobe(monkeypatch)
    _make_video(tmp_path, "X.mp4")
    _make_video(tmp_path, "X.mkv")
    guide = _make_guide(tmp_path, stem="X.ja.merged.whisperjav")
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False and r["error_key"] == "no_candidate"
    assert sorted(r["candidates"]) == ["X.mkv", "X.mp4"]
    assert "X.mp4" in r["error"]


def test_refine_ai_apply_tm_telemetry_features_only(gui_api_obj, monkeypatch,
                                                    tmp_path, caplog):
    """件4 埋点：疑似整段/长句入库特征聚合一条 debug——只记长度+句末标点
    计数，不含 TM 原文；不阻断不改落库行为。"""
    import logging

    import subtransjav.refine.glossary_conflict as gc_mod
    import subtransjav.refine.tm as tm_mod

    stored: list = []

    class _FakeTM:
        def __init__(self, db_path=None):
            pass

        def store(self, source, target, stage=0, source_name=None):
            stored.append((source, target))
            return True

        def close(self):
            return None

    monkeypatch.setattr(tm_mod, "TranslationMemory", _FakeTM)
    monkeypatch.setattr(gc_mod, "default_watch_path",
                        lambda: str(tmp_path / "absent_watch.json"))

    long_src = "あ" * 120
    multi_src = "第一句。第二句！第三句？"
    normal_src = "はい"
    entries = [
        {"source": long_src, "target": "长句译"},
        {"source": multi_src, "target": "多句译"},
        {"source": normal_src, "target": "普通译"},
    ]
    with caplog.at_level(logging.DEBUG, logger="subtransjav.gui"):
        r = gui_api_obj.refine_ai_apply_tm(
            json.dumps(entries, ensure_ascii=False))
    assert r["success"] is True
    assert stored == [(e["source"], e["target"]) for e in entries], \
        "埋点不得改变落库行为"
    debug_text = "\n".join(rec.getMessage() for rec in caplog.records
                           if rec.name == "subtransjav.gui")
    assert "flagged=2" in debug_text and "total=3" in debug_text, \
        "聚合特征计数缺失（长句 1 + 多句标点 1）"
    assert "max_len=120" in debug_text and "max_sent_punct=3" in debug_text
    # 不记 TM 原文（出域面纪律）：debug 输出零原文泄漏
    assert long_src not in debug_text
    assert multi_src not in debug_text
    assert normal_src not in debug_text


# ---------------------------------------------------------------------------
# 2.7.4 件F（D2026-1007-02）：上次手动媒体目录持久化为推断⑤层附加搜索目录
# 保存 override 时落 preview_media_last_dir KV（normcase 父目录）；④ 零命中
# 后才搜 last_dir（不递归、同套 leveled 剥链+前缀兜底+时长守卫）；跨目录
# 候选集不合并（last_dir 多候选 fail-closed、同目录多命中不落⑤）。
# ---------------------------------------------------------------------------

def test_preview_last_dir_saved_on_override(gui_api_obj, monkeypatch, tmp_path):
    """override 保存成功 → preview_media_last_dir KV 落所选媒体父目录
    （normcase 绝对路径）；空串删除不触碰该键。"""
    from subtransjav.paths import normalize_path_case
    settings_path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(settings_path))
    other_dir = tmp_path / "elsewhere"
    other_dir.mkdir()
    media = _make_video(other_dir, "movie.mp4")
    guide = _make_guide(tmp_path, stem="ld00")
    w = gui_api_obj.refine_save_media_override(str(guide), str(media))
    assert w["success"] is True
    assert gui_api_obj._load_preview_media_last_dir() == \
        normalize_path_case(str(other_dir))
    # 空串 = 删除 override 条目，last_dir 键保留不触碰
    gui_api_obj.refine_save_media_override(str(guide), "")
    assert gui_api_obj._load_preview_media_last_dir() == \
        normalize_path_case(str(other_dir))


def test_preview_last_dir_layer5_hit(gui_api_obj, monkeypatch, tmp_path):
    """⑤ 命中：导读目录无视频 + last_dir 有 X.mp4（导读
    X.ja.merged.whisperjav 式，leveled 剥 ".merged" 达 root X）→
    media_source="last_dir" 采纳，时长守卫照常生效。"""
    settings_path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(settings_path))
    _install_fake_ffprobe(monkeypatch, video="h264", audio="aac")
    movies = tmp_path / "movies"
    movies.mkdir()
    media = _make_video(movies, "X.mp4")
    assert gui_api_obj.refine_save_stage_settings(
        None, None, {"preview_media_last_dir": str(movies)})["success"]
    guide = _make_guide(tmp_path, stem="X.ja.merged.whisperjav")
    r = gui_api_obj.refine_audio_preview(str(guide), 10.0, 12.0)
    assert r["ok"] is True
    assert r["media_source"] == "last_dir"
    assert r["media_path"] == str(media)


def test_preview_last_dir_multi_candidate_fail_closed(gui_api_obj, monkeypatch,
                                                      tmp_path):
    """⑤ 多候选 fail-closed：last_dir 内 X.mp4+X.mkv → no_candidate 带
    候选列表，error 标注来源目录（跨目录候选集不合并）。"""
    from subtransjav.paths import normalize_path_case
    settings_path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(settings_path))
    _install_fake_ffprobe(monkeypatch)
    movies = tmp_path / "movies"
    movies.mkdir()
    _make_video(movies, "X.mp4")
    _make_video(movies, "X.mkv")
    assert gui_api_obj.refine_save_stage_settings(
        None, None, {"preview_media_last_dir": str(movies)})["success"]
    guide = _make_guide(tmp_path, stem="X.ja.merged.whisperjav")
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False and r["error_key"] == "no_candidate"
    assert sorted(r["candidates"]) == ["X.mkv", "X.mp4"]
    assert normalize_path_case(str(movies)) in normalize_path_case(r["error"])


def test_preview_last_dir_missing_or_invalid_noop(gui_api_obj, monkeypatch,
                                                  tmp_path):
    """last_dir 键缺失/目录不存在 → 静默跳过⑤层，行为与四层时代完全
    一致（no_candidate、error 仍指向导读同目录，零回归）。"""
    settings_path = tmp_path / "refine_stage_settings.json"
    monkeypatch.setattr(gui_api_obj, "_refine_stage_settings_path",
                        lambda: str(settings_path))
    _install_fake_ffprobe(monkeypatch)
    guide = _make_guide(tmp_path, stem="Y")
    # 键缺失
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False and r["error_key"] == "no_candidate"
    assert "导读同目录" in r["error"]
    assert r["candidates"] == []
    # 目录不存在 → 行为与键缺失完全一致
    assert gui_api_obj.refine_save_stage_settings(
        None, None,
        {"preview_media_last_dir": str(tmp_path / "gone")})["success"]
    assert gui_api_obj._load_preview_media_last_dir() == ""
    r2 = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r2 == r


# ---------------------------------------------------------------------------
# 硬字幕压制 api（2.8.0 批1 件4：会话钩子 once（C9）+ 互斥（D2）+ 参数持久化）
# ---------------------------------------------------------------------------

class _FakeTermProc:
    """假翻译子进程：poll() 返回预设退出码（终态消费路径驱动）。"""

    def __init__(self, code):
        self._code = code

    def poll(self):
        return self._code


def _hook_probe_api(code):
    """构造带翻译终态的最小 api 实例（object.__new__ 跳过 __init__ 副作用）。"""
    api = object.__new__(TranslateAPI)
    api._translate_lock = threading.Lock()
    TranslateAPI._init_translation_state(api)
    api._translate_process = _FakeTermProc(code)
    api._translate_status = "running"
    api._translate_parser = EventStreamParser()
    fired = []
    api._on_translation_session_completed = lambda summary: fired.append(summary)
    return api, fired


def test_encode_session_hook_fires_once_on_completed(gui_api_obj):
    """C9：completed 终态触发钩子且仅一次（重复轮询不重复触发）。"""
    api, fired = _hook_probe_api(0)
    api.get_translation_status()
    assert api._translate_status == "completed"
    assert len(fired) == 1
    api.get_translation_status()   # proc 已清空，不再进入终态消费
    assert len(fired) == 1


def test_encode_session_hook_not_fired_on_error_or_cancelled(gui_api_obj):
    """C9：error/cancelled 终态不触发钩子（cancelled 不进终态消费分支）。"""
    api, fired = _hook_probe_api(1)
    api.get_translation_status()
    assert api._translate_status == "error"
    assert fired == []
    api2, fired2 = _hook_probe_api(0)
    api2._translate_status = "cancelled"
    api2.get_translation_status()
    assert fired2 == []


def test_encode_session_hook_guard_blocks_second_call(gui_api_obj, monkeypatch):
    """C9：once 守卫——同会话第二次直接短路（真实方法直调不产生第二次副作用）。"""
    import subtransjav.webview_gui.api as api_mod
    api = object.__new__(TranslateAPI)
    api._session_hook_fired = True   # 模拟已触发
    seen = []
    monkeypatch.setattr(api_mod._log, "info",
                        lambda msg, *a, **k: seen.append(str(msg)))
    api._on_translation_session_completed({})
    assert seen == []                # 守卫短路：无日志副作用
    assert api._session_hook_fired is True


def test_start_translation_rejected_while_encoding(gui_api_obj, monkeypatch):
    """互斥（D2）：压制运行中 start_translation 拒绝并人话显因。"""
    import subtransjav.webview_gui.encode_queue as eq
    gui_api_obj._translate_lock = threading.Lock()
    monkeypatch.setattr(eq, "encode_active", lambda: True)
    r = gui_api_obj.start_translation({"inputs": []})
    assert r["success"] is False and "压制" in r["error"]


def test_encode_commit_rejected_while_translating(gui_api_obj, tmp_path,
                                                  monkeypatch):
    """互斥（D2）：翻译槽被占（_translate_running 同锁置位）→ commit 拒。"""
    import subtransjav.webview_gui.encode_queue as eq
    video = tmp_path / "v.mp4"
    video.write_bytes(b"v")
    sub = tmp_path / "v.srt"
    sub.write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    monkeypatch.setattr(eq, "_translate_running", True)
    r = gui_api_obj.encode_commit(
        [{"video_path": str(video), "subtitle_path": str(sub)}],
        {"video_format": "h264"})
    assert r["success"] is False and "翻译" in r["error"]


def test_encode_last_params_roundtrip(gui_api_obj, tmp_path, monkeypatch):
    """上次压制参数持久化（fs_utils 原子写；CONFIG_DIR 打桩隔离）。"""
    import subtransjav.refine.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp_path))
    assert gui_api_obj.encode_get_last_params()["params"] == {}
    assert gui_api_obj.encode_save_last_params(
        {"video_format": "av1", "quality": "balanced"})["success"]
    r = gui_api_obj.encode_get_last_params()
    assert r["success"] and r["params"]["video_format"] == "av1"


# ---------------------------------------------------------------------------
# 压制参数独立设置项（D2026-1008-01 批2）：encode_save_params 桥——校验复用
# encode_preflight 同路径（_parse_encode_params），只校验不建 job 不入队，
# 通过后原子写 config/hardsub_last.json。数据根隔离：CONFIG_DIR 与读路径
# （encode_get_last_params）同一 import 期常量，沿用本文件既有打桩先例
# （test_encode_last_params_roundtrip），另设 SUBTRANSJAV_DATA_ROOT 环境变量
# 双保险（env 通道现读 helper 兜底隔离）。
# ---------------------------------------------------------------------------

def test_encode_save_params_valid_writes_hardsub_last(gui_api_obj, tmp_path,
                                                      monkeypatch):
    """合法参数：写 hardsub_last.json 且与读路径同源；原子写无 tmp 残留；
    非 EncodeParams 字段（out_dir）透传保留；盖 saved_at 供摘要行。"""
    import subtransjav.refine.config as cfg
    root = tmp_path / "dataroot"
    root.mkdir()
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(root))
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(root / "config"))
    params = {"video_format": "h265", "quality": "quality", "font_size": 28,
              "volume_db": -1.5, "out_dir": str(tmp_path)}
    r = gui_api_obj.encode_save_params(json.dumps(params))
    assert r["success"] is True
    path = root / "config" / "hardsub_last.json"
    assert path.is_file(), "校验通过必须落盘 hardsub_last.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["video_format"] == "h265" and data["quality"] == "quality"
    assert data["out_dir"] == str(tmp_path), "out_dir 非字段键须透传保留"
    assert data.get("saved_at"), "须盖 saved_at 时间戳（前端摘要行素材）"
    assert not list((root / "config").glob("*.tmp")), "原子写不得留 tmp 残留"
    # 与读路径同源：encode_get_last_params 读回同一份
    lp = gui_api_obj.encode_get_last_params()
    assert lp["success"] and lp["params"]["video_format"] == "h265"
    # 回包携带写入快照（前端 onSaved 直接同步缓存）
    assert r["params"]["video_format"] == "h265" and r["params"]["saved_at"]


def test_encode_save_params_invalid_rejected_with_reason_and_tip(gui_api_obj,
                                                                 tmp_path,
                                                                 monkeypatch):
    """非法参数：拒绝带人话原因+tip，且不落盘（校验前置）。"""
    import subtransjav.refine.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp_path))
    r = gui_api_obj.encode_save_params(json.dumps({"video_format": "mpeg2"}))
    assert r["success"] is False and "视频格式" in r["error"], "须显因"
    assert r.get("tip"), "失败须带 tip（_refine_error_tip 人话风格）"
    assert not (tmp_path / "hardsub_last.json").exists(), "校验失败不得落盘"
    # 逃生门黑名单同样前置拒绝（与 preflight 同路径）
    r2 = gui_api_obj.encode_save_params(
        json.dumps({"video_format": "h264", "custom_params": "-f mp4"}))
    assert r2["success"] is False and r2.get("tip")
    # JSON 不可解析 / 非对象：拒绝带 tip
    r3 = gui_api_obj.encode_save_params("not-json{{")
    assert r3["success"] is False and r3.get("error") and r3.get("tip")
    assert not (tmp_path / "hardsub_last.json").exists()


def test_encode_save_params_never_enqueues_job(gui_api_obj, tmp_path,
                                               monkeypatch):
    """只校验不建 job 不入队：enqueue_batch 若被触碰即炸；互斥槽不被占用。"""
    import subtransjav.refine.config as cfg
    import subtransjav.webview_gui.encode_queue as eq
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp_path))

    def _boom(*_a, **_k):
        raise AssertionError("encode_save_params 不得入队（enqueue_batch 被触碰）")

    monkeypatch.setattr(eq.EncodeQueue, "enqueue_batch", _boom)
    r = gui_api_obj.encode_save_params(
        json.dumps({"video_format": "h264", "quality": "balanced"}))
    assert r["success"] is True
    assert eq.encode_active() is False, "不得占用/触发压制互斥槽"


def test_encode_pairing_chain(gui_api_obj, tmp_path):
    """srt→终稿字幕→视频契约配对（黑盒实锤回归钉：.ja.whisperjav 全链剥层）。"""
    video = tmp_path / "vid1.mp4"
    video.write_bytes(b"v")
    final = tmp_path / "vid1_final_cn.srt"
    final.write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    inp = tmp_path / "vid1.ja.whisperjav.srt"
    inp.write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    # 终稿解析：管线中间稿名 → _final_cn 终稿（剥链闭集）
    assert gui_api_obj._resolve_final_subtitle(str(inp)) == str(final)
    assert gui_api_obj._resolve_final_subtitle(str(final)) == str(final)  # 已是终稿原样
    # 视频解析：终稿 stem 剥 _final_ → 同目录视频
    assert gui_api_obj._resolve_video_for_subtitle(str(final)) == str(video)
    # 缺视频 → 空串
    (tmp_path / "vid2_final_cn.srt").write_text("x", encoding="utf-8")
    assert gui_api_obj._resolve_video_for_subtitle(str(tmp_path / "vid2_final_cn.srt")) == ""


def test_encode_presets_crud_and_cap(gui_api_obj, tmp_path, monkeypatch):
    """批2 预设：CRUD+上限 20+内置三档只读。"""
    import subtransjav.refine.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp_path))
    lst = gui_api_obj.encode_presets_list()
    assert lst["success"] and len(lst["builtin"]) == 3 and lst["user"] == {}
    for i in range(20):
        r = gui_api_obj.encode_preset_save(f"p{i}", {"quality": "balanced"})
        assert r["success"]
    r = gui_api_obj.encode_preset_save("p20", {"quality": "balanced"})
    assert r["success"] is False and "上限" in r["error"]
    # 覆盖既有名不受上限约束
    assert gui_api_obj.encode_preset_save("p0", {"quality": "quality"})["success"]
    assert gui_api_obj.encode_preset_delete("p0")["success"]
    assert gui_api_obj.encode_preset_save("p20", {})["success"]
    assert gui_api_obj.encode_preset_delete("no-such")["success"] is False
    assert gui_api_obj.encode_preset_save("  ", {})["success"] is False


def test_encode_presets_corruption_degrades_with_bak(gui_api_obj, tmp_path,
                                                     monkeypatch):
    """批2 预设：文件损坏→key 级降级回空+.bak 留档。"""
    import subtransjav.refine.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp_path))
    assert gui_api_obj.encode_preset_save("keep", {"quality": "balanced"})["success"]
    path = tmp_path / "hardsub_presets.json"
    good = path.read_bytes()
    path.write_text("{broken json!!", encoding="utf-8")
    lst = gui_api_obj.encode_presets_list()
    assert lst["success"] and lst["user"] == {}          # 降级回空不抛
    assert (tmp_path / "hardsub_presets.json.bak").exists()  # 坏档留 .bak
    # 下次保存从空表重建（坏档 .bak 仍留）
    assert gui_api_obj.encode_preset_save("fresh", {})["success"]
    assert path.read_bytes() != good


# ---------------------------------------------------------------------------
# 批3：自动化（钩子→收集→跳过语义→入队；开关存管线设置）
# ---------------------------------------------------------------------------
@pytest.fixture()
def _auto_env(tmp_path, monkeypatch):
    """自动化测试环境：CONFIG_DIR 打桩 + 干净互斥态 + 队列供给桩。"""
    import subtransjav.refine.config as cfg
    import subtransjav.webview_gui.encode_queue as eq
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp_path))
    monkeypatch.setattr(eq, "_encode_active", False)
    monkeypatch.setattr(eq, "_translate_running", False)
    # 媒体：vid1.mp4+终稿字幕+管线中间稿（配对链复用）
    media = tmp_path / "media"
    media.mkdir()
    (media / "vid1.mp4").write_bytes(b"v")
    (media / "vid1_final_cn.srt").write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    inp = media / "vid1.ja.whisperjav.srt"
    inp.write_text("1\n00:00:00,000 --> 00:00:01,000\nx\n", encoding="utf-8")
    monkeypatch.setattr(eq, "resolve_hardsub_ffmpeg", lambda *a, **k: SimpleNamespace(
        ffmpeg_path="", ffprobe_path="", capability={}, missing=[]))
    # 媒体探测桩（enqueue_batch 内 probe）
    monkeypatch.setattr(eq, "probe_media", lambda *a, **k: SimpleNamespace(
        duration_s=10.0, width=640, height=360, bit_rate_bps=2_000_000,
        has_audio=True, audio_codec="aac"))
    yield {"srt": str(inp), "media": media}
    eq._singleton = None   # 队列单例重置（history 只增，跨测试须换新）


def test_automation_disabled_by_default(gui_api_obj, _auto_env):
    """开关缺省关：钩子触发不入队（零副作用）。"""
    gui_api_obj._on_translation_session_completed(
        {"files": {_auto_env["srt"]: "done"}})
    assert gui_api_obj.encode_status()["jobs"] == []


def test_automation_enqueues_done_and_skips_existing(gui_api_obj, _auto_env,
                                                     monkeypatch):
    """开关开：done 文件配对入队；成品已存在跳过并通知（自动化语义）。"""
    import json as _json
    settings = {"settings": {"encode_auto_enabled": True}}
    (tmp := _auto_env["media"].parent / "cfg").mkdir(exist_ok=True)
    import subtransjav.refine.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp))
    (tmp / "refine_stage_settings.json").write_text(
        _json.dumps(settings), encoding="utf-8")
    # 队列供给桩已由 _auto_env 注入（missing=[] → 入队走通；spawn 桩防真进程）
    import subtransjav.webview_gui.encode_queue as eq
    monkeypatch.setattr(eq, "_spawn_ffmpeg",
                        lambda argv: (_ for _ in ()).throw(OSError("no ffmpeg")))
    gui_api_obj._on_translation_session_completed(
        {"files": {_auto_env["srt"]: "done"}})
    jobs = gui_api_obj.encode_status()["jobs"]
    assert len(jobs) == 1 and jobs[0]["state"] in ("queued", "failed")
    assert jobs[0]["params"].get("auto") is True
    # 二次触发：once 守卫（同会话不重复入队）
    gui_api_obj._on_translation_session_completed(
        {"files": {_auto_env["srt"]: "done"}})
    assert len(gui_api_obj.encode_status()["jobs"]) == 1
    eq.get_encode_queue().cancel(None)
    eq.release_encode_slot()


def test_automation_skips_existing_output(gui_api_obj, _auto_env, monkeypatch):
    """成品已存在→跳过不入队（自动压制 skip-existing，决策自动化定稿）。"""
    import json as _json

    import subtransjav.refine.config as cfg
    tmp = _auto_env["media"].parent / "cfg2"
    tmp.mkdir(exist_ok=True)
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp))
    (tmp / "refine_stage_settings.json").write_text(
        _json.dumps({"settings": {"encode_auto_enabled": True}}), encoding="utf-8")
    out = _auto_env["media"] / "vid1_hardsub.mp4"
    out.write_bytes(b"exists")
    gui_api_obj._on_translation_session_completed(
        {"files": {_auto_env["srt"]: "done"}})
    assert gui_api_obj.encode_status()["jobs"] == []   # 全跳过零入队


# ---------------------------------------------------------------------------
# P1 分析模型预热（D2026-1008-02 批3，G1 落 (c) 阻断形态）：
# 桥单飞/C4 在载去重/云 provider/互锁兜底/G10 超时合法化/取消判别/退出清理/
# G2 会话挂点/CLI --warmup-analysis。预热状态机与登记槽全部打桩，零触网。
# ---------------------------------------------------------------------------

class _WarmupFakeProc:
    """替身预热子进程：communicate 阻塞至 release（在飞/单飞语义可钉）。"""

    def __init__(self, returncode=0):
        self.pid = 424242
        self.returncode = None
        self._rc = returncode
        self._release = threading.Event()

    def release(self, rc=0):
        self._rc = rc
        self._release.set()

    def communicate(self, timeout=None):
        self._release.wait(timeout=30)
        self.returncode = self._rc
        return "", ""

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        self._release.wait(timeout=timeout or 5)
        self.returncode = self._rc
        return self.returncode

    def kill(self):
        self.release(1)


def _install_fake_warmup_spawn(monkeypatch):
    """替身 spawn_refine_cli（预热链）：捕获 CLI argv，返回可控假进程。"""
    import subtransjav.webview_gui.api as api_mod
    procs: list = []
    argvs: list = []

    def _fake(args, **kwargs):
        argvs.append(list(args))
        proc = _WarmupFakeProc()
        procs.append(proc)
        return proc

    monkeypatch.setattr(api_mod, "spawn_refine_cli", _fake)
    return procs, argvs


def _fake_settings(settings: dict):
    return {"success": True,
            "stages": [{"stage": 1, "provider": "lmstudio",
                        "endpoint": "", "model": ""}],
            "settings": settings, "key_status": {}, "first_run": False}


def test_warmup_bridge_spawn_args_and_single_flight(gui_api_obj, monkeypatch):
    """桥主路径：spawn 旗标同分析参源（--warmup-analysis/--ai-model/
    --s1-provider）+ 单飞（在飞二次调用不重复 spawn）+ 登记/台账含 warmup
    + reap 收口 loaded。"""
    import subtransjav.webview_gui.api as api_mod
    monkeypatch.setattr(gui_api_obj, "refine_get_stage_settings",
                        lambda: _fake_settings({}))
    monkeypatch.setattr(gui_api_obj, "_warmup_probe_loaded", lambda ep: [])
    procs, argvs = _install_fake_warmup_spawn(monkeypatch)
    gui_api_obj._init_ai_state()

    r1 = gui_api_obj.refine_warmup_analysis_model("m1", "lmstudio")
    assert r1["success"] is True and r1["state"] == "loading"
    assert len(argvs) == 1
    argv = argvs[0]
    assert argv[0] == "--warmup-analysis"
    assert argv[argv.index("--ai-model") + 1] == "m1"
    assert argv[argv.index("--s1-provider") + 1] == "lmstudio"

    # 单飞：在飞中二次调用 → 返回现状态且不再 spawn
    r2 = gui_api_obj.refine_warmup_analysis_model("m1", "lmstudio")
    assert r2.get("already_loading") is True
    assert len(argvs) == 1, "单飞拒绝必须发生在 spawn 之前"

    # 登记槽 + 台账（kind/marker 批3 新增）
    entry = gui_api_obj._warmup_proc
    assert entry is not None and entry["kind"] == "warmup"
    assert entry["marker"] == "--warmup-analysis"
    entries = api_mod._ledger_read_entries(
        api_mod._child_procs_ledger_path())
    assert any(e.get("kind") == "warmup"
               and e.get("marker") == "--warmup-analysis" for e in entries)

    # 收尾：release → reap 收口 loaded + 槽清位
    procs[0].release(0)
    deadline = time.time() + 10
    while time.time() < deadline and gui_api_obj._warmup_proc is not None:
        time.sleep(0.05)
    assert gui_api_obj._warmup_proc is None
    assert gui_api_obj.refine_warmup_status()["state"] == "loaded"


def test_warmup_bridge_already_hot_skips_spawn(gui_api_obj, monkeypatch):
    """C4 状态优先去重：探活返回含目标模型 → already_hot 不 spawn。"""
    monkeypatch.setattr(gui_api_obj, "refine_get_stage_settings",
                        lambda: _fake_settings({}))
    monkeypatch.setattr(gui_api_obj, "_warmup_probe_loaded",
                        lambda ep: ["m1", "other-model"])
    procs, argvs = _install_fake_warmup_spawn(monkeypatch)
    gui_api_obj._init_ai_state()
    r = gui_api_obj.refine_warmup_analysis_model("m1", "lmstudio")
    assert r.get("already_hot") is True and r.get("supported") is True
    assert argvs == [], "已在载不得 spawn"
    assert gui_api_obj.refine_warmup_status()["state"] == "hot"


def test_warmup_bridge_cloud_provider_unsupported(gui_api_obj, monkeypatch):
    """云 provider → supported:false 且不探活不 spawn（静默不扰）。"""
    monkeypatch.setattr(gui_api_obj, "refine_get_stage_settings",
                        lambda: _fake_settings({}))
    probed: list = []
    monkeypatch.setattr(gui_api_obj, "_warmup_probe_loaded",
                        lambda ep: probed.append(ep))
    procs, argvs = _install_fake_warmup_spawn(monkeypatch)
    gui_api_obj._init_ai_state()
    r = gui_api_obj.refine_warmup_analysis_model("m1", "deepseek")
    assert r.get("supported") is False
    assert argvs == [] and probed == []


def test_warmup_bridge_endpoint_unreachable_silent(gui_api_obj, monkeypatch):
    """端点不可达（探活 None）→ supported:false 静默不 spawn、状态机不动。"""
    monkeypatch.setattr(gui_api_obj, "refine_get_stage_settings",
                        lambda: _fake_settings({}))
    monkeypatch.setattr(gui_api_obj, "_warmup_probe_loaded", lambda ep: None)
    procs, argvs = _install_fake_warmup_spawn(monkeypatch)
    gui_api_obj._init_ai_state()
    r = gui_api_obj.refine_warmup_analysis_model("m1", "lmstudio")
    assert r.get("supported") is False and argvs == []
    assert gui_api_obj.refine_warmup_status()["state"] == "idle"


def test_start_translation_blocked_while_warmup_loading(gui_api_obj,
                                                        monkeypatch):
    """互锁兜底：预热 loading 中 start_translation 拒启并带 warmup_loading；
    已 claim 的翻译槽原路归还（防泄漏）；终态放行。"""
    import subtransjav.webview_gui.encode_queue as eq
    gui_api_obj._translate_lock = threading.Lock()
    monkeypatch.setattr(eq, "encode_active", lambda: False)
    monkeypatch.setattr(eq, "claim_translate_slot", lambda: True)
    released: list = []
    monkeypatch.setattr(eq, "release_translate_slot",
                        lambda: released.append(1))
    gui_api_obj._init_ai_state()
    gui_api_obj._warmup_state = {"state": "loading",
                                 "started_at": time.time(), "model": "m1"}
    r = gui_api_obj.start_translation({"inputs": ["a.srt"], "force": True})
    assert r.get("success") is False and r.get("warmup_loading") is True
    assert r.get("warmup_status", {}).get("state") == "loading"
    assert released, "已 claim 的翻译槽必须原路归还"

    # 非 loading（终态）不拦：走正常启动链（spawn 桩抛错收尾，见既有先例）
    captured: dict = {}
    _capture_popen(monkeypatch, captured, gui_api_obj)
    gui_api_obj._warmup_state = {"state": "failed"}
    r2 = gui_api_obj.start_translation({"inputs": ["a.srt"], "force": True})
    assert "warmup_loading" not in r2


def test_warmup_timeout_kv_normalization(gui_api_obj, monkeypatch):
    """G10：preheat_load_hard_timeout KV int 合法化（非法/非正/缺省=300）
    与依据留痕字段（settings KV / settings 缺省）。"""
    cases = [
        ({"preheat_load_hard_timeout": "600"}, 600, "settings KV"),
        ({"preheat_load_hard_timeout": 900}, 900, "settings KV"),
        ({"preheat_load_hard_timeout": "abc"}, 300, "settings 缺省"),
        ({"preheat_load_hard_timeout": "0"}, 300, "settings 缺省"),
        ({"preheat_load_hard_timeout": "-5"}, 300, "settings 缺省"),
        ({}, 300, "settings 缺省"),
    ]
    for settings, want_s, want_basis in cases:
        monkeypatch.setattr(
            gui_api_obj, "refine_get_stage_settings",
            lambda s=settings: _fake_settings(s))
        got_s, got_basis = gui_api_obj._warmup_timeout_s()
        assert (got_s, got_basis) == (want_s, want_basis), settings


def test_warmup_cancel_targets_warmup_slot_only(gui_api_obj):
    """⑥ 取消判别修正：refine_cancel_warmup 只取 warmup 槽（不再把非
    ai_analyze 一律当 batch_fix），其余槽零扰动；loading 状态收口 failed。"""
    gui_api_obj._init_ai_state()

    def _entry(kind, marker):
        return {"proc": None, "pid": 999998, "create_time": 0.0,
                "kind": kind, "marker": marker, "cancelled": False}

    a = _entry("ai_analyze", "--ai-analyze")
    b = _entry("batch_fix", "--action-retranslate")
    w = _entry("warmup", "--warmup-analysis")
    gui_api_obj._ai_analyze_proc = a
    gui_api_obj._batch_fix_proc = b
    gui_api_obj._warmup_proc = w
    gui_api_obj._warmup_state = {"state": "loading",
                                 "started_at": time.time()}
    r = gui_api_obj.refine_cancel_warmup()
    assert r.get("success") is True and r.get("cancelled") is True
    assert w["cancelled"] is True
    assert not a["cancelled"] and not b["cancelled"], "取消不得外溢他槽"
    assert gui_api_obj._warmup_state["state"] == "failed"

    # 幂等：槽空时 cancelled_pending 且不炸
    gui_api_obj._warmup_proc = None
    r2 = gui_api_obj.refine_cancel_warmup()
    assert r2.get("cancelled_pending") is True


def test_exit_cleanup_includes_warmup_slot(gui_api_obj):
    """⑦ 退出清理（C5）：预热槽纳入 terminate_registered 全覆盖 + 台账写空。"""
    import subtransjav.webview_gui.api as api_mod
    gui_api_obj._init_ai_state()
    gui_api_obj._translate_lock = threading.Lock()
    gui_api_obj._warmup_proc = {"proc": None, "pid": 999998,
                                "create_time": 0.0, "kind": "warmup",
                                "marker": "--warmup-analysis"}
    gui_api_obj._on_exit_cleanup()
    assert gui_api_obj._warmup_proc is None
    assert gui_api_obj._ai_analyze_proc is None
    assert gui_api_obj._batch_fix_proc is None
    assert api_mod._ledger_read_entries(
        api_mod._child_procs_ledger_path()) == []


def test_session_completed_triggers_warmup_hook(gui_api_obj, monkeypatch):
    """G2 触发点①：会话级完成钩子尾部触发 _warmup_after_session（daemon），
    后端自行按 ai_analyze_* KV 同源解析后调桥；解析失败静默跳过。"""
    gui_api_obj._init_ai_state()
    calls: list = []
    monkeypatch.setattr(gui_api_obj, "refine_get_stage_settings",
                        lambda: _fake_settings({
                            "ai_analyze_provider": "lmstudio",
                            "ai_analyze_model": "m1"}))
    monkeypatch.setattr(gui_api_obj, "refine_warmup_analysis_model",
                        lambda m, p: calls.append((m, p)) or
                        {"success": True})
    monkeypatch.setattr(gui_api_obj, "_encode_automation_enabled",
                        lambda: False)
    gui_api_obj._session_hook_fired = False
    gui_api_obj._on_translation_session_completed({})
    assert gui_api_obj._session_hook_fired is True
    deadline = time.time() + 5
    while time.time() < deadline and not calls:
        time.sleep(0.05)
    assert calls == [("m1", "lmstudio")], "会话完成须以同源解析结果调桥"

    # 解析失败（全空配置）→ 静默跳过，不调桥
    calls.clear()
    monkeypatch.setattr(gui_api_obj, "refine_get_stage_settings",
                        lambda: _fake_settings({}))
    gui_api_obj._warmup_after_session()
    assert calls == []


def test_warmup_status_bridge_shapes(gui_api_obj, monkeypatch):
    """状态桥形状：从未预热时按当前配置报 supported；timeout 恒随行。"""
    monkeypatch.setattr(gui_api_obj, "refine_get_stage_settings",
                        lambda: _fake_settings({
                            "ai_analyze_provider": "lmstudio",
                            "ai_analyze_model": "m1"}))
    gui_api_obj._init_ai_state()
    r = gui_api_obj.refine_warmup_status()
    assert r["supported"] is True and r["state"] == "idle"
    assert r["timeout"] == 300 and r["model"] == "m1"

    monkeypatch.setattr(gui_api_obj, "refine_get_stage_settings",
                        lambda: _fake_settings({}))
    r2 = gui_api_obj.refine_warmup_status()
    assert r2["supported"] is False and r2["state"] == "idle"


def test_cli_warmup_analysis_invokes_client_and_exit_code(monkeypatch):
    """⑧ --warmup-analysis 早退分流：_make_ai_client 被调且退出码 0/1
    （替身客户端零触网）。"""
    import subtransjav.refine.cli as cli_mod
    import subtransjav.refine.quality_advisor as qa_mod
    calls: list = []

    def _fake_client(cfg, model_override=""):
        calls.append(model_override)
        return SimpleNamespace(_chat=lambda s, u: "{}")

    monkeypatch.setattr(qa_mod, "_make_ai_client", _fake_client)
    rc = cli_mod.main(["--warmup-analysis", "--ai-model", "m1"])
    assert rc == 0 and calls == ["m1"]

    def _boom(cfg, model_override=""):
        raise RuntimeError("LM Studio down")

    monkeypatch.setattr(qa_mod, "_make_ai_client", _boom)
    assert cli_mod.main(["--warmup-analysis", "--ai-model", "m1"]) == 1


def test_warmup_analysis_flag_in_child_kind_markers():
    """kind→旗标映射含 warmup（身份核验第③重依据）。"""
    import subtransjav.webview_gui.api as api_mod
    assert api_mod._CHILD_KIND_MARKERS.get("warmup") == "--warmup-analysis"


def test_warmup_probe_miss_downgrades_stale_loaded_state(gui_api_obj,
                                                        monkeypatch):
    """C4 状态优先（TTL 回归钉）：LM Studio TTL 卸载后，陈旧 loaded 状态
    +同指纹不得把重新预热永久抑制——探活确认不在载须降级并重新 spawn。"""
    monkeypatch.setattr(gui_api_obj, "refine_get_stage_settings",
                        lambda: _fake_settings({}))
    monkeypatch.setattr(gui_api_obj, "_warmup_probe_loaded", lambda ep: [])
    procs, argvs = _install_fake_warmup_spawn(monkeypatch)
    gui_api_obj._init_ai_state()
    # 第一轮：spawn → release(0) → 状态机 loaded
    r1 = gui_api_obj.refine_warmup_analysis_model("m1", "lmstudio")
    assert r1["state"] == "loading"
    procs[0].release(0)
    deadline = time.time() + 10
    while time.time() < deadline \
            and gui_api_obj.refine_warmup_status()["state"] != "loaded":
        time.sleep(0.05)
    assert gui_api_obj.refine_warmup_status()["state"] == "loaded"
    # TTL 卸载后（探活仍 miss）：必须重新 spawn 而非 skipped
    r2 = gui_api_obj.refine_warmup_analysis_model("m1", "lmstudio")
    assert r2["state"] == "loading"
    assert len(argvs) == 2, "TTL 卸载后须重新预热（C4 真值覆写指纹缓存）"


# ---------------------------------------------------------------------------
# 3.0 批1 a 段（D2026-1009-02）：全链开关+会话完成状态机骨架+C7 时序门
# +复验参数化+重入守卫+C5 三条件
# ---------------------------------------------------------------------------

def _fullchain_env(gui_api_obj, monkeypatch, tmp_path, *, settings,
                   stage1=None):
    """全链测试环境：CONFIG_DIR 打桩（开关 KV 真实读写走
    refine_stage_settings.json 文件）+ refine_get_stage_settings 替身
    （模型解析/回填读内存表，避 DPAPI 密钥库；仿 _install_fake_stages）
    + 端点探活桩（C8 预检与预热 loaded 探测不真连 localhost:1234，
    CI 无 LM Studio 也稳定；仿 test_batch_fix_probe_passes_then_spawns
    假探活口径，非 2xx 也算通）。"""
    import subtransjav.refine.config as cfg
    d = tmp_path / "cfg"
    d.mkdir(exist_ok=True)
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(d))
    (d / "refine_stage_settings.json").write_text(
        json.dumps({"stages": [], "settings": settings},
                   ensure_ascii=False), encoding="utf-8")
    stages = [{"stage": 1, **(stage1 or {})}] if stage1 is not None else []
    monkeypatch.setattr(
        gui_api_obj, "refine_get_stage_settings",
        lambda: {"success": True, "stages": stages, "settings": settings,
                 "key_status": {}, "first_run": False})
    import subtransjav.translate.llm_client as llm_mod
    monkeypatch.setattr(llm_mod, "probe_endpoint_reachable",
                        lambda endpoint, **kw: (True, "HTTP 404"))
    monkeypatch.setattr(gui_api_obj, "_warmup_probe_loaded",
                        lambda endpoint: None)
    return d


def test_fullchain_switch_default_off_and_roundtrip(gui_api_obj, monkeypatch,
                                                    tmp_path):
    """开关缺省关 + 保存/读取 roundtrip（CONFIG_DIR 打桩）：KV
    fullchain_auto_enabled 走 refine_save_stage_settings 持久化，与
    encode_auto_enabled 同文件共存互不覆盖。"""
    import subtransjav.refine.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp_path))
    gui = gui_api_obj
    assert gui._fullchain_auto_enabled() is False      # 缺省关（无文件）
    assert gui.refine_save_stage_settings(
        None, None, {"fullchain_auto_enabled": True})["success"]
    assert gui._fullchain_auto_enabled() is True
    assert gui.refine_save_stage_settings(
        None, None, {"encode_auto_enabled": True})["success"]
    assert gui._fullchain_auto_enabled() is True       # 同 KV 文件共存
    assert gui._encode_automation_enabled() is True
    assert gui.refine_save_stage_settings(
        None, None, {"fullchain_auto_enabled": False})["success"]
    assert gui._fullchain_auto_enabled() is False
    assert gui._encode_automation_enabled() is True    # 不连坐


def test_fullchain_closed_state_hook_unchanged(gui_api_obj, monkeypatch,
                                               tmp_path):
    """C5/C-3 关闭态回归钉：fullchain 关（缺省）时钩子直调后
    _fullchain_running 保持 False、链线程未创建、零 spawn；warmup daemon
    仍触发（原 P1 形态；encode/warmup 逐字节路径另由
    test_session_completed_triggers_warmup_hook / test_automation_* 钉住）。"""
    gui_api_obj._init_ai_state()
    _fullchain_env(gui_api_obj, monkeypatch, tmp_path, settings={})
    monkeypatch.setattr(gui_api_obj, "_encode_automation_enabled",
                        lambda: False)
    warm = threading.Event()
    monkeypatch.setattr(gui_api_obj, "_warmup_after_session",
                        lambda: warm.set())
    captured = _install_fake_bf_spawn(monkeypatch)
    gui_api_obj._session_hook_fired = False
    gui_api_obj._on_translation_session_completed({})
    assert warm.wait(5), "关闭态钩子尾部仍须 daemon 触发 _warmup_after_session"
    assert getattr(gui_api_obj, "_fullchain_thread", None) is None, \
        "关闭态不得创建全链线程"
    with gui_api_obj._ai_lock:
        assert gui_api_obj._fullchain_running is False
    assert not captured.get("calls"), "关闭态钩子不得触发任何批修复/分析 spawn"


def test_fullchain_chain_happy_path(gui_api_obj, monkeypatch, tmp_path):
    """开启态钩子直调→链跑通：预热首环承接（C5）→单批修复（verify=False
    无 --ai-analyze）→链级复验恰 1 次→链尾不压制（encode 关）→C9 落盘
    ended_at/计数正确。"""
    gui_api_obj._init_ai_state()
    _fullchain_env(
        gui_api_obj, monkeypatch, tmp_path,
        settings={"fullchain_auto_enabled": True},
        stage1={"provider": "lmstudio", "endpoint": "", "model": "qwen-m"})
    items = [_bf_item(3, _T3, "甲"),
             _bf_item(7, _T7, "乙", category="untranslated")]
    ledger_path = tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json"
    _make_bf_guide(tmp_path, items, ledger=[],
                   with_suggestion={"glossary": [], "tm": [],
                                    "observations": []})
    warmup_calls: list = []
    monkeypatch.setattr(gui_api_obj, "refine_warmup_analysis_model",
                        lambda m, p: warmup_calls.append((m, p))
                        or {"success": True})
    encode_calls: list = []
    monkeypatch.setattr(gui_api_obj, "_run_encode_automation",
                        lambda s: encode_calls.append(s))
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=["[1/2] ok"], rc=0, ledger_path=ledger_path,
        ledger_records=[{"index": 3, "timing": _T3, "outcome": "applied"},
                        {"index": 7, "timing": _T7, "outcome": "applied"}],
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    gui_api_obj._session_hook_fired = False
    gui_api_obj._on_translation_session_completed(
        {"files": {str(tmp_path / "ep01_final_cn.srt"): "done"}})
    assert getattr(gui_api_obj, "_fullchain_thread", None) is not None
    gui_api_obj._fullchain_thread.join(15)
    assert not gui_api_obj._fullchain_thread.is_alive()
    bf = [c for c in captured["calls"]
          if "--action-retranslate" in c["args"]]
    an = [c for c in captured["calls"] if "--ai-analyze" in c["args"]]
    assert len(bf) == 1 and len(an) == 1
    assert bf[0]["args"][bf[0]["args"].index("--entries") + 1] == "3,7"
    assert all("--ai-analyze" not in c["args"] for c in bf), \
        "批内 verify=False 不得触发分析 spawn"
    assert warmup_calls == [("qwen-m", "lmstudio")], \
        "链首预热承接（C5）：解析结果同源 (model, provider)"
    assert encode_calls == [], "C7：encode 关 → 链尾不压制"
    run = gui_api_obj._fullchain_read_last_run()
    assert run["phase"] == "done" and run["ended_at"]
    assert run["files_total"] == 1 and run["files_done"] == 1
    assert run["entries_fixed"] == 2 and run["entries_failed"] == 0
    assert run["entries_pending"] == 0
    assert gui_api_obj.fullchain_last_run_status()["unfinished"] is False
    assert gui_api_obj.fullchain_automation_status()["running"] is False


def test_fullchain_single_analyze_invariant(gui_api_obj, monkeypatch,
                                            tmp_path):
    """长期链级不变式钉（D2026-1009-02 批1 a 段；批3 3B 白名单化）：一次
    会话完整链内 LLM 分析（--ai-analyze）spawn==1——批内 verify=False +
    链级复验唯一。白名单语义：F4 whisper 批量转写走 asr_env 通道（本地
    python 子进程），不计入分析不变式——本测试经 fake batch_transcribe_
    clips 独立计数证明（无媒体=C18 跳过，转写 fake 零调用、分析 spawn
    仍==1，两通道互不干扰）。"""
    gui_api_obj._init_ai_state()
    _fullchain_env(
        gui_api_obj, monkeypatch, tmp_path,
        settings={"fullchain_auto_enabled": True},
        stage1={"provider": "lmstudio", "endpoint": "", "model": "qwen-m"})
    items = [_bf_item(3, _T3, "甲"), _bf_item(7, _T7, "乙"),
             # F4 观察条目（无媒体 → C18 诚实退化，不 spawn 转写）
             _bf_item(9, "00:00:09,000 --> 00:00:10,000", "",
                      category="suspected_missed_speech")]
    ledger_path = tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json"
    _make_bf_guide(tmp_path, items, ledger=[],
                   with_suggestion={"glossary": [], "tm": [],
                                    "observations": []})
    monkeypatch.setattr(gui_api_obj, "refine_warmup_analysis_model",
                        lambda m, p: {"success": True})
    import subtransjav.refine.asr_env as asr_env_mod
    batch_calls: list = []
    monkeypatch.setattr(asr_env_mod, "batch_transcribe_clips",
                        lambda media, timings, **kw:
                        batch_calls.append(timings) or [])
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=[], rc=0, ledger_path=ledger_path,
        ledger_records=[{"index": 3, "timing": _T3, "outcome": "applied"}],
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    gui_api_obj._session_hook_fired = False
    gui_api_obj._on_translation_session_completed(
        {"files": {str(tmp_path / "ep01_final_cn.srt"): "done"}})
    gui_api_obj._fullchain_thread.join(15)
    analyze_calls = [c for c in captured["calls"]
                     if "--ai-analyze" in c["args"]]
    assert len(analyze_calls) == 1, \
        "链级不变式（白名单语义）：LLM 分析 --ai-analyze spawn 必须==1" \
        "（复验参数化+链级唯一；F4 转写走 asr_env 通道不计入）"
    a = analyze_calls[0]["args"]
    assert a[a.index("--ai-model") + 1] == "qwen-m"
    assert a[a.index("--s1-provider") + 1] == "lmstudio"
    assert batch_calls == [], \
        "转写 fake 独立计数：C18 无媒体不得触发批量转写（白名单通道）"


def test_fullchain_batch_split_max_50(gui_api_obj, monkeypatch, tmp_path):
    """60 条 fixable 切 2 批（≤_BATCH_FIX_MAX_ENTRIES/批）；批间独立进出
    （重入守卫不嵌套），批内零 --ai-analyze（verify=False）。"""
    gui_api_obj._init_ai_state()
    _fullchain_env(
        gui_api_obj, monkeypatch, tmp_path,
        settings={"fullchain_auto_enabled": True},
        stage1={"provider": "lmstudio", "endpoint": "", "model": "qwen-m"})
    items = [_bf_item(i, f"00:00:{i:02d},000 --> 00:00:{i + 1:02d},000",
                      f"t{i}") for i in range(60)]
    ledger_path = tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json"
    _make_bf_guide(tmp_path, items, ledger=[])
    monkeypatch.setattr(gui_api_obj, "refine_warmup_analysis_model",
                        lambda m, p: {"success": True})
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=[], rc=0, ledger_path=ledger_path,
        ledger_records=[{"timing": "t", "outcome": "applied"}])
    gui_api_obj._session_hook_fired = False
    gui_api_obj._on_translation_session_completed(
        {"files": {str(tmp_path / "ep01_final_cn.srt"): "done"}})
    gui_api_obj._fullchain_thread.join(15)
    bf = [c for c in captured["calls"]
          if "--action-retranslate" in c["args"]]
    assert len(bf) == 2, "60 条须切 2 批"
    sizes = [len(c["args"][c["args"].index("--entries") + 1].split(","))
             for c in bf]
    assert sizes == [50, 10], f"批大小须 ≤50 且整除切批: {sizes}"
    assert all("--ai-analyze" not in c["args"] for c in bf)


def test_fullchain_cloud_provider_gate(gui_api_obj, monkeypatch, tmp_path,
                                       caplog):
    """N-6 云端零出域：解析生效 provider 为云端 → 链不启动（零 spawn）、
    人话通知落日志、C9 落 skipped+ended_at、运行标志复位。"""
    import logging
    gui_api_obj._init_ai_state()
    _fullchain_env(
        gui_api_obj, monkeypatch, tmp_path,
        settings={"fullchain_auto_enabled": True},
        stage1={"provider": "deepseek", "endpoint": "", "model": "cloud-m"})
    captured = _install_fake_bf_spawn(monkeypatch)
    with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
        gui_api_obj._session_hook_fired = False
        gui_api_obj._on_translation_session_completed(
            {"files": {str(tmp_path / "ep01_final_cn.srt"): "done"}})
        gui_api_obj._fullchain_thread.join(10)
    assert not captured.get("calls"), "云端 provider 链不得 spawn 任何子进程"
    assert any("自动化未启动" in r.message for r in caplog.records), \
        "不启动须人话通知（不静默）"
    run = gui_api_obj._fullchain_read_last_run()
    assert run["phase"] == "skipped" and run["ended_at"]
    assert gui_api_obj.fullchain_automation_status()["running"] is False


def test_fullchain_c7_encode_after_verify(gui_api_obj, _auto_env, monkeypatch):
    """C7 时序门（双开）：压制入队发生在复验（--ai-analyze spawn）之后——
    fake spawn 捕获序=批修复→分析→encode 标记；入队任务带 auto 标记。"""
    import subtransjav.webview_gui.encode_queue as eq
    gui_api_obj._init_ai_state()
    # 双开 KV（真实文件：钩子入口 _fullchain_auto_enabled + 链尾
    # _encode_automation_enabled 均直读文件；CONFIG_DIR 换独立目录）
    import subtransjav.refine.config as cfg
    cfgdir = _auto_env["media"].parent / "cfg_fc"
    cfgdir.mkdir(exist_ok=True)
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(cfgdir))
    (cfgdir / "refine_stage_settings.json").write_text(
        json.dumps({"stages": [], "settings": {
            "fullchain_auto_enabled": True, "encode_auto_enabled": True}},
            ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(
        gui_api_obj, "refine_get_stage_settings",
        lambda: {"success": True,
                 "stages": [{"stage": 1, "provider": "lmstudio",
                             "endpoint": "", "model": "qwen-m"}],
                 "settings": {"fullchain_auto_enabled": True,
                              "encode_auto_enabled": True},
                 "key_status": {}, "first_run": False})
    # C8 端点预检桩（CI 无 LM Studio；与 _fullchain_env 同口径，
    # 非 2xx 也算通——本测试未走 helper，须自打）
    import subtransjav.translate.llm_client as llm_mod
    monkeypatch.setattr(llm_mod, "probe_endpoint_reachable",
                        lambda endpoint, **kw: (True, "HTTP 404"))
    media = _auto_env["media"]
    # 导读/报告/空台账落媒体目录（done 键剥链候选 vid1.ja.whisperjav→
    # vid1.ja→vid1 命中 vid1_质量报告导读.json，兼测剥链候选序）
    (media / "vid1_质量报告导读.json").write_text(json.dumps(
        {"version": 2, "stem": "vid1",
         "items": [_bf_item(3, _T3, "甲")], "direction": "",
         "media_path": ""}, ensure_ascii=False), encoding="utf-8")
    (media / "vid1_质量报告.txt").write_text("【结论】x\n", encoding="utf-8")
    ledger_path = media / "vid1_重翻记录.json"
    ledger_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(gui_api_obj, "refine_warmup_analysis_model",
                        lambda m, p: {"success": True})
    monkeypatch.setattr(eq, "_spawn_ffmpeg",
                        lambda argv: (_ for _ in ()).throw(
                            OSError("no ffmpeg")))
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=[], rc=0, ledger_path=ledger_path,
        ledger_records=[{"index": 3, "timing": _T3, "outcome": "applied"}],
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    orig_encode = TranslateAPI._run_encode_automation

    def _encode_spy(summary, **kwargs):   # b 段：链尾透传 from_fullchain
        captured["calls"].append({"args": ["__encode_tail__"], "kwargs": {}})
        return orig_encode(gui_api_obj, summary, **kwargs)

    monkeypatch.setattr(gui_api_obj, "_run_encode_automation", _encode_spy)
    gui_api_obj._session_hook_fired = False
    gui_api_obj._on_translation_session_completed(
        {"files": {_auto_env["srt"]: "done"}})
    gui_api_obj._fullchain_thread.join(15)
    seq = captured["calls"]
    bf_idx = [i for i, c in enumerate(seq)
              if "--action-retranslate" in c["args"]]
    an_idx = next(i for i, c in enumerate(seq) if "--ai-analyze" in c["args"])
    enc_idx = next(i for i, c in enumerate(seq)
                   if c["args"] and c["args"][0] == "__encode_tail__")
    assert bf_idx and an_idx > max(bf_idx), "复验须晚于全部批修复"
    assert enc_idx > an_idx, "C7：压制排布须在复验之后（链尾）"
    jobs = gui_api_obj.encode_status()["jobs"]
    assert len(jobs) == 1 and jobs[0]["params"].get("auto") is True
    eq.get_encode_queue().cancel(None)
    eq.release_encode_slot()


def test_batch_fix_verify_false_skips_analyze(gui_api_obj, monkeypatch,
                                              tmp_path):
    """复验参数化（批1 a 段）：verify=False 时无 --ai-analyze spawn 且
    result.verify={"skipped": True}；缺省 True 行为由既有
    test_batch_fix_success_and_ledger_delta 原样钉住（不动）。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items)
    captured = _install_fake_bf_spawn(monkeypatch, lines=["ok"], rc=0)
    r = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                     "sb-model", verify=False)
    assert r["success"] is True
    assert r["verify"] == {"skipped": True}
    assert all("--ai-analyze" not in c["args"] for c in captured["calls"])


def test_batch_fix_reentry_guard_rejects_concurrent(gui_api_obj, monkeypatch,
                                                    tmp_path):
    """重入守卫（批1 a 段）：第一调用阻塞在 fake spawn wait 期间第二调用
    被结构化拒绝（batch_fix_running，不二次 spawn）；finally 清位后可
    再次发起。"""
    import subtransjav.webview_gui.api as api_mod
    gui_api_obj._init_ai_state()
    release = threading.Event()
    entered = threading.Event()

    class _BlockingProc:
        pid = 424242
        stdout = iter([])

        def __init__(self):
            self.returncode = None

        def wait(self, timeout=None):
            entered.set()
            release.wait(10)
            self.returncode = 0
            return 0

        def kill(self):
            pass

    calls: list = []

    def _fake_spawn(args, **kwargs):
        calls.append(args)
        return _BlockingProc()

    monkeypatch.setattr(api_mod, "spawn_refine_cli", _fake_spawn)
    # 模型解析打桩（云端 provider 跳过端点探活，零网络；守卫测试不消费
    # 解析细节，只要 ok 即可走到 spawn wait）
    monkeypatch.setattr(
        gui_api_obj, "_resolve_ai_model_config",
        lambda *a, **k: {"ok": True, "provider": "deepseek", "endpoint": "",
                         "model": "m1", "source": "stage_a_follow",
                         "notes": [], "reason": ""})
    items = [_bf_item(3, _T3, "甲"), _bf_item(7, _T7, "乙")]
    guide = _make_bf_guide(tmp_path, items, ledger=[])

    box: dict = {}

    def _first():
        box["r"] = gui_api_obj.refine_batch_fix(str(guide), [3, 7],
                                                verify=False)

    t = threading.Thread(target=_first, daemon=True)
    t.start()
    assert entered.wait(10), "第一调用未到达 spawn wait"
    r2 = gui_api_obj.refine_batch_fix(str(guide), [3], verify=False)
    assert r2["success"] is False
    assert "批量修复进行中" in r2["error"], "并发第二调用须结构化拒绝"
    assert len(calls) == 1, "拒绝路径不得二次 spawn"
    release.set()
    t.join(10)
    assert box["r"]["success"] is True
    r3 = gui_api_obj.refine_batch_fix(str(guide), [3], verify=False)
    assert r3["success"] is True
    assert len(calls) == 2, "finally 清位后须可再次发起"


def test_fullchain_c9_interrupted_last_run(gui_api_obj, monkeypatch,
                                           tmp_path):
    """C9「上次未完成」判定：fullchain_last_run.json 无 ended_at 且
    phase!=done → unfinished True + entries_pending 透出；done 快照/缺失
    快照 → False（不误报）。"""
    import subtransjav.refine.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp_path))
    p = tmp_path / "fullchain_last_run.json"
    p.write_text(json.dumps(
        {"phase": "running", "files_total": 3, "files_done": 1,
         "entries_fixed": 4, "entries_failed": 0, "entries_pending": 21,
         "missed_skipped": 0, "started_at": "2026-10-10T00:00:00",
         "ended_at": ""}, ensure_ascii=False), encoding="utf-8")
    st = gui_api_obj.fullchain_last_run_status()
    assert st["unfinished"] is True
    assert st["last_run"]["entries_pending"] == 21
    p.write_text(json.dumps({"phase": "done", "ended_at": "T1",
                             "entries_pending": 0}, ensure_ascii=False),
                 encoding="utf-8")
    assert gui_api_obj.fullchain_last_run_status()["unfinished"] is False
    p.unlink()
    assert gui_api_obj.fullchain_last_run_status()["unfinished"] is False


# ---------------------------------------------------------------------------
# 3.0 批1 b 段（D2026-1009-02 第二节批1 b 段）：互斥矩阵六对+云端零出域
# 注入。纪律：每对断言拒绝先于 spawn（captured 空）=零出域承诺的测试面；
# 链内调用携 from_fullchain=True 绕过全链在飞判定（仍受各自守卫约束）。
# 互斥对⑤（前端预热抑制）由 tests/test_gui_js_static.py 既有静态钉覆盖
#（warmupMaybeStart 守卫序/触发点①②），本文件不重复。
# ---------------------------------------------------------------------------

_FULLCHAIN_ERR = "全链路自动化进行中"


def test_fullchain_blocks_start_translation(gui_api_obj, monkeypatch):
    """互斥对①：全链在飞 → start_translation 结构化拒绝（fullchain_running
    标记+人话 error）；已 claim 的翻译槽原路归还（防泄漏）；拒绝先于
    spawn（零出域）。"""
    import threading

    import subtransjav.webview_gui.api as api_mod
    import subtransjav.webview_gui.encode_queue as eq
    monkeypatch.setattr(eq, "_encode_active", False)
    monkeypatch.setattr(eq, "_translate_running", False)
    gui_api_obj._init_ai_state()
    # _translate_lock 由 __init__ 创建；object.__new__ 实例需手动补齐
    gui_api_obj._translate_lock = threading.Lock()
    no_spawn: list = []

    def _no_spawn(args, **kwargs):
        no_spawn.append(args)
        raise AssertionError("拒绝路径不得 spawn")

    monkeypatch.setattr(api_mod, "spawn_refine_cli", _no_spawn)
    with gui_api_obj._ai_lock:
        gui_api_obj._fullchain_running = True
    try:
        r = gui_api_obj.start_translation({"force": True, "inputs": []})
        assert r["success"] is False
        assert r["fullchain_running"] is True
        assert _FULLCHAIN_ERR in r["error"]
        assert no_spawn == [], "拒绝须先于 spawn（零出域测试面）"
        assert eq.claim_translate_slot() is True, \
            "拒绝路径须归还已 claim 的翻译槽（防泄漏）"
        eq.release_translate_slot()
    finally:
        with gui_api_obj._ai_lock:
            gui_api_obj._fullchain_running = False


def test_fullchain_blocks_manual_batch_fix(gui_api_obj, monkeypatch, tmp_path):
    """互斥对②：全链在飞 → 手动批量修复结构化拒绝（零 spawn）；链内调用
    携 from_fullchain=True 放行（仍受重入守卫约束，行为=链内逐批）。"""
    items = [_bf_item(3, _T3, "甲")]
    guide = _make_bf_guide(tmp_path, items, ledger=[])
    captured = _install_fake_bf_spawn(monkeypatch, lines=["ok"], rc=0)
    gui_api_obj._init_ai_state()
    with gui_api_obj._ai_lock:
        gui_api_obj._fullchain_running = True
    try:
        r = gui_api_obj.refine_batch_fix(str(guide), [3], verify=False)
        assert r["success"] is False
        assert r["fullchain_running"] is True
        assert _FULLCHAIN_ERR in r["error"]
        assert captured.get("calls") is None, \
            "拒绝须先于 spawn（零出域测试面）"
        r2 = gui_api_obj.refine_batch_fix(str(guide), [3], "deepseek",
                                          "sb-model", verify=False,
                                          from_fullchain=True)
        assert r2["success"] is True, "链内调用（from_fullchain=True）须放行"
        assert any("--action-retranslate" in c["args"]
                   for c in captured["calls"])
    finally:
        with gui_api_obj._ai_lock:
            gui_api_obj._fullchain_running = False


def test_fullchain_blocks_manual_ai_analyze(gui_api_obj, monkeypatch,
                                            tmp_path):
    """互斥对④：全链在飞 → 手动 AI 分析结构化拒绝（零 spawn，显式拒绝
    不排队）；链内复验携 from_fullchain=True 放行（captured 含
    --ai-analyze）。"""
    report = _make_ai_report(tmp_path)
    _install_fake_stage_settings(gui_api_obj, monkeypatch, provider="zen")
    captured = _install_fake_ai_run(monkeypatch)
    gui_api_obj._init_ai_state()
    with gui_api_obj._ai_lock:
        gui_api_obj._fullchain_running = True
    try:
        r = gui_api_obj.refine_ai_analyze(str(report))
        assert r["success"] is False
        assert _FULLCHAIN_ERR in r["error"]
        assert "args" not in captured, "拒绝须先于 spawn（零出域测试面）"
        r2 = gui_api_obj.refine_ai_analyze(str(report), from_fullchain=True)
        assert r2["success"] is True, "链内复验（from_fullchain=True）须放行"
        assert "--ai-analyze" in captured["args"]
    finally:
        with gui_api_obj._ai_lock:
            gui_api_obj._fullchain_running = False


def test_fullchain_blocks_manual_encode(gui_api_obj):
    """互斥对③：全链在飞 → 手动压制入队入口 encode_commit 结构化拒绝
    （入口判定早于参数解析/落队，零入队零 spawn）。"""
    gui_api_obj._init_ai_state()
    with gui_api_obj._ai_lock:
        gui_api_obj._fullchain_running = True
    try:
        r = gui_api_obj.encode_commit([], {})
        assert r["success"] is False
        assert r["fullchain_running"] is True
        assert _FULLCHAIN_ERR in r["error"]
        assert gui_api_obj.encode_status()["jobs"] == [], "拒绝须零入队"
    finally:
        with gui_api_obj._ai_lock:
            gui_api_obj._fullchain_running = False


def test_fullchain_tail_encode_skipped_when_manual_busy(gui_api_obj, _auto_env,
                                                        monkeypatch, caplog):
    """互斥对⑥反向：链尾压制前判定手动压制在飞（encode_active=互斥槽
    已占）→ 跳过自动压制（不排队不重试）+人话通知；链本体照常完成
    （复验恰 1 次、phase=done）。"""
    import logging

    import subtransjav.webview_gui.encode_queue as eq
    gui_api_obj._init_ai_state()
    _fullchain_env(
        gui_api_obj, monkeypatch, _auto_env["media"].parent,
        settings={"fullchain_auto_enabled": True, "encode_auto_enabled": True},
        stage1={"provider": "lmstudio", "endpoint": "", "model": "qwen-m"})
    media = _auto_env["media"]
    (media / "vid1_质量报告导读.json").write_text(json.dumps(
        {"version": 2, "stem": "vid1",
         "items": [_bf_item(3, _T3, "甲")], "direction": "",
         "media_path": ""}, ensure_ascii=False), encoding="utf-8")
    (media / "vid1_质量报告.txt").write_text("【结论】x\n", encoding="utf-8")
    ledger_path = media / "vid1_重翻记录.json"
    ledger_path.write_text("[]", encoding="utf-8")
    monkeypatch.setattr(gui_api_obj, "refine_warmup_analysis_model",
                        lambda m, p: {"success": True})
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=[], rc=0, ledger_path=ledger_path,
        ledger_records=[{"index": 3, "timing": _T3, "outcome": "applied"}],
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    encode_calls: list = []
    monkeypatch.setattr(gui_api_obj, "_run_encode_automation",
                        lambda s, **k: encode_calls.append((s, k)))
    assert eq.claim_encode_slot() is True, "预置：手动压制在飞（互斥槽已占）"
    try:
        with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
            gui_api_obj._session_hook_fired = False
            gui_api_obj._on_translation_session_completed(
                {"files": {_auto_env["srt"]: "done"}})
            gui_api_obj._fullchain_thread.join(15)
        assert encode_calls == [], \
            "手动压制在飞须跳过自动压制（不排队不重试）"
        assert any("压制被手动任务占用" in r.message for r in caplog.records), \
            "占用跳过须人话通知（不静默）"
        assert len([c for c in captured["calls"]
                    if "--ai-analyze" in c["args"]]) == 1, \
            "链本体不受影响：复验照常恰 1 次"
        run = gui_api_obj._fullchain_read_last_run()
        assert run["phase"] == "done" and run["ended_at"]
    finally:
        eq.release_encode_slot()


def test_fullchain_verify_skipped_when_manual_analyze_busy(gui_api_obj,
                                                           monkeypatch,
                                                           tmp_path, caplog):
    """互斥对④反向：手动分析在飞（_ai_analyze_running 预置）→ 链跑完、
    链级复验跳过（零 --ai-analyze spawn、不重试）、notice 落 caplog、
    last_run phase=done（链继续收尾）。"""
    import logging
    gui_api_obj._init_ai_state()
    _fullchain_env(
        gui_api_obj, monkeypatch, tmp_path,
        settings={"fullchain_auto_enabled": True},
        stage1={"provider": "lmstudio", "endpoint": "", "model": "qwen-m"})
    items = [_bf_item(3, _T3, "甲")]
    ledger_path = tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json"
    _make_bf_guide(tmp_path, items, ledger=[],
                   with_suggestion={"glossary": [], "tm": [],
                                    "observations": []})
    monkeypatch.setattr(gui_api_obj, "refine_warmup_analysis_model",
                        lambda m, p: {"success": True})
    captured = _install_fake_bf_spawn(
        monkeypatch, lines=[], rc=0, ledger_path=ledger_path,
        ledger_records=[{"index": 3, "timing": _T3, "outcome": "applied"}],
        verify_suggestions={"glossary": [], "tm": [], "observations": []})
    with gui_api_obj._ai_lock:
        gui_api_obj._ai_analyze_running = True   # 预置：手动分析在飞
    try:
        with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
            gui_api_obj._session_hook_fired = False
            gui_api_obj._on_translation_session_completed(
                {"files": {str(tmp_path / "ep01_final_cn.srt"): "done"}})
            gui_api_obj._fullchain_thread.join(15)
        assert not [c for c in captured["calls"]
                    if "--ai-analyze" in c["args"]], \
            "手动分析在飞 → 链级复验跳过（零 --ai-analyze spawn）"
        assert any("复验跳过" in r.message for r in caplog.records), \
            "复验占用跳过须人话通知（不静默）"
        run = gui_api_obj._fullchain_read_last_run()
        assert run["phase"] == "done" and run["ended_at"], \
            "复验跳过后链继续收尾（phase=done）"
    finally:
        with gui_api_obj._ai_lock:
            gui_api_obj._ai_analyze_running = False


def test_fullchain_config_error_injection(gui_api_obj, monkeypatch, tmp_path,
                                          caplog):
    """云端零出域注入（N-6 补钉，双向）：_resolve_ai_model_config 打桩——
    ①半配置 ok=False（provider 有 model 空）②ok=True 但 provider=云端
    名单值 → 均链不启动（零 spawn）+notice+phase=skipped+运行标志复位。"""
    import logging
    gui_api_obj._init_ai_state()
    _fullchain_env(gui_api_obj, monkeypatch, tmp_path,
                   settings={"fullchain_auto_enabled": True})
    captured = _install_fake_bf_spawn(monkeypatch)
    cases = [
        # 半配置：provider 有值 model 空 → ok=False
        {"ok": False, "provider": "lmstudio", "endpoint": "", "model": "",
         "source": "stage_a_follow", "notes": [], "reason": "半配置"},
        # ok=True 但 provider 为云端名单值（N-6 云端零出域）
        {"ok": True, "provider": "deepseek", "endpoint": "https://x/v1",
         "model": "cloud-m", "source": "stage_a_follow", "notes": [],
         "reason": ""},
    ]
    for case in cases:
        monkeypatch.setattr(
            gui_api_obj, "_resolve_ai_model_config",
            lambda *a, _c=dict(case), **k: dict(_c))
        with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
            gui_api_obj._session_hook_fired = False
            gui_api_obj._on_translation_session_completed(
                {"files": {str(tmp_path / "ep01_final_cn.srt"): "done"}})
            gui_api_obj._fullchain_thread.join(10)
        assert not captured.get("calls"), \
            f"注入 {case['provider']!r} 链不得 spawn 任何子进程"
        assert any("自动化未启动" in r.message for r in caplog.records), \
            "不启动须人话通知（不静默）"
        run = gui_api_obj._fullchain_read_last_run()
        assert run["phase"] == "skipped" and run["ended_at"]
        assert gui_api_obj.fullchain_automation_status()["running"] is False
        caplog.clear()


# ---------------------------------------------------------------------------
# 3.0 批2（D2026-1009-02 批2）：一键回滚（改写恢复语义）
# ---------------------------------------------------------------------------

_RT1 = "00:00:01,000 --> 00:00:02,000"
_RT2 = "00:00:03,000 --> 00:00:04,000"


def _make_rollback_env(tmp_path: Path, ledger, final_texts=None):
    """回滚夹具：导读（v2）+ 台账 + 终稿（final_stem 契约名）。

    final_texts: {timing: text} 终稿两块（缺省甲/乙）。"""
    from subtransjav.refine.filters import build_srt
    from subtransjav.refine.v2_outputs import final_stem
    guide = {"version": 2, "stem": _BF_GUIDE_STEM,
             "items": [_bf_item(1, _RT1, ""), _bf_item(2, _RT2, "")],
             "direction": "", "media_path": ""}
    (tmp_path / f"{_BF_GUIDE_STEM}_质量报告导读.json").write_text(
        json.dumps(guide, ensure_ascii=False), encoding="utf-8")
    if ledger is not None:
        (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").write_text(
            json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    entries = [
        {"index": 1, "timing": _RT1,
         "text": (final_texts or {}).get(_RT1, "甲（已改）")},
        {"index": 2, "timing": _RT2,
         "text": (final_texts or {}).get(_RT2, "乙")},
    ]
    (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt").write_text(
        build_srt(entries), encoding="utf-8")
    return tmp_path / f"{_BF_GUIDE_STEM}_质量报告导读.json"


def _applied_rec(timing, old, new):
    return {"index": 1, "timing": timing, "category": "cps_too_fast",
            "old_text": old, "new_text": new, "model_used": "m",
            "outcome": "applied", "reason": "", "ts": "2026-10-10 00:00:00",
            "source_partial": False}


def _read_rollback_final(tmp_path: Path):
    from subtransjav.refine.filters import parse_srt
    from subtransjav.refine.v2_outputs import final_stem
    return parse_srt(
        (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt").read_text(
            encoding="utf-8"))


def test_fullchain_rollback_happy_path(gui_api_obj, tmp_path, monkeypatch):
    """回滚 happy path：applied 记录 old_text 回写终稿 + rollback 台账
    追加（10 键齐）+ 写序契约保持（台账先于终稿落盘）。"""
    import subtransjav.refine.fs_utils as fs_mod
    from subtransjav.refine import action_retranslate as art
    guide = _make_rollback_env(tmp_path, [
        _applied_rec(_RT1, "甲（原）", "甲（已改）")])
    order: list = []
    real_append = art._append_ledger

    def _append(path, records):
        order.append("ledger")
        return real_append(path, records)

    _real_atomic = fs_mod._atomic_write_text

    def _atomic(path, text, **kwargs):
        # _append_ledger 内部的台账原子写也经 fs_utils._atomic_write_text，
        # 探针按文件名区分（重翻记录.json=台账落盘，.srt=终稿落盘）
        order.append("atomic:" + Path(path).name)
        return _real_atomic(path, text)

    monkeypatch.setattr(art, "_append_ledger", _append)
    monkeypatch.setattr(fs_mod, "_atomic_write_text", _atomic)
    r = gui_api_obj.fullchain_rollback(str(guide))
    assert r["success"] is True and r["restored"] == 1
    assert r["unmatched"] == [] and r["auto_insert_skipped"] == 0
    # 终稿恢复为修复前文本
    final = _read_rollback_final(tmp_path)
    assert final[0]["text"] == "甲（原）" and final[1]["text"] == "乙"
    # 台账追加 rollback 记录（10 键闭集；old_text=回滚前当前文）
    ledger = json.loads(
        (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").read_text(
            encoding="utf-8"))
    assert len(ledger) == 2
    rb = ledger[1]
    assert set(rb) == {"index", "timing", "category", "old_text",
                       "new_text", "model_used", "outcome", "reason",
                       "ts", "source_partial"}
    assert rb["outcome"] == "rollback" and rb["reason"] == "manual rollback"
    assert rb["old_text"] == "甲（已改）" and rb["new_text"] == "甲（原）"
    # 写序契约：台账先于终稿（order 细粒度=append 标记+两笔落盘文件名）
    assert order == ["ledger",
                     f"atomic:{_BF_GUIDE_STEM}_重翻记录.json",
                     f"atomic:{_BF_GUIDE_STEM}_final_cn.srt"]


def test_fullchain_rollback_unmatched_timing(gui_api_obj, tmp_path):
    """timing 未命中终稿：不猜测，unmatched 如实返回且零写入。"""
    guide = _make_rollback_env(tmp_path, [
        _applied_rec("00:09:09,000 --> 00:09:10,000", "原", "改")])
    r = gui_api_obj.fullchain_rollback(str(guide))
    assert r["success"] is True and r["restored"] == 0
    assert r["unmatched"] == ["00:09:09,000 --> 00:09:10,000"]
    assert len(_read_rollback_final(tmp_path)) == 2            # 终稿未动
    ledger = json.loads(
        (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").read_text(
            encoding="utf-8"))
    assert len(ledger) == 1                                    # 无 rollback 追加


def test_fullchain_rollback_final_missing(gui_api_obj, tmp_path):
    """终稿缺失：结构化失败（msg 人话文案），台账不被误追加。"""
    from subtransjav.refine.v2_outputs import final_stem
    guide = _make_rollback_env(tmp_path, [
        _applied_rec(_RT1, "甲（原）", "甲（已改）")])
    (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt").unlink()
    r = gui_api_obj.fullchain_rollback(str(guide))
    assert r["success"] is False and "终稿字幕不存在" in r["error"]
    ledger = json.loads(
        (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").read_text(
            encoding="utf-8"))
    assert len(ledger) == 1


def test_fullchain_rollback_rejected_when_running(gui_api_obj):
    """全链在飞（_fullchain_running）显式拒绝（互斥矩阵同源）。"""
    gui_api_obj._init_ai_state()
    with gui_api_obj._ai_lock:
        gui_api_obj._fullchain_running = True
    try:
        r = gui_api_obj.fullchain_rollback("任意_质量报告导读.json")
        assert r["success"] is False
        assert r["error"] == "全链路自动化进行中，请稍后再试"
    finally:
        with gui_api_obj._ai_lock:
            gui_api_obj._fullchain_running = False


def test_fullchain_rollback_auto_insert_deleted(gui_api_obj, tmp_path):
    """批3 3B 删行接线：auto_insert applied 记录按 timing 精确命中删除
    终稿块+重编号；删除记录（new_text=None）追加入台账；applied 改写
    照常恢复。"""
    guide = _make_rollback_env(tmp_path, [
        _applied_rec(_RT1, "甲（原）", "甲（已改）"),
        {"index": None, "timing": "00:00:09,000 --> 00:00:10,000",
         "category": "auto_insert", "old_text": "",
         "new_text": "补行文本", "model_used": "", "outcome": "applied",
         "reason": "auto insert", "ts": "2026-10-10 00:00:00",
         "source_partial": False},
    ])
    # 终稿含已插入行（auto_insert 记录 timing 处第三块）
    from subtransjav.refine.filters import build_srt as _bsrt
    from subtransjav.refine.v2_outputs import final_stem as _fstem
    (tmp_path / f"{_fstem(_BF_GUIDE_STEM)}.srt").write_text(
        _bsrt([
            {"index": 1, "timing": _RT1, "text": "甲（已改）"},
            {"index": 2, "timing": _RT2, "text": "乙"},
            {"index": 3, "timing": "00:00:09,000 --> 00:00:10,000",
             "text": "补行文本"},
        ]), encoding="utf-8")
    r = gui_api_obj.fullchain_rollback(str(guide))
    assert r["success"] is True
    assert r["restored"] == 1 and r["auto_insert_deleted"] == 1
    assert r["auto_insert_skipped"] == 1   # 兼容键语义=实删数
    final = _read_rollback_final(tmp_path)
    assert final[0]["text"] == "甲（原）" and len(final) == 2  # 插入行已删
    ledger = json.loads(
        (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").read_text(
            encoding="utf-8"))
    assert len(ledger) == 4   # 种子 2（applied+auto_insert）+改写 rollback+删行 rollback
    dl = ledger[-1]
    assert dl["category"] == "auto_insert" and dl["outcome"] == "rollback"
    assert dl["new_text"] is None
    assert dl["old_text"] == "补行文本"
    assert dl["reason"] == "manual rollback (delete inserted row)"
    assert set(dl) == {"index", "timing", "category", "old_text",
                       "new_text", "model_used", "outcome", "reason",
                       "ts", "source_partial"}


def test_fullchain_rollback_empty_ledger(gui_api_obj, tmp_path):
    """台账空：success+restored=0 如实返回，零写入。"""
    guide = _make_rollback_env(tmp_path, [])
    r = gui_api_obj.fullchain_rollback(str(guide))
    assert r == {"success": True, "restored": 0, "unmatched": [],
                 "auto_insert_skipped": 0, "auto_insert_deleted": 0,
                 "ledger_path": r["ledger_path"]}
    assert r["ledger_path"].endswith("ep01_重翻记录.json")


def test_fullchain_rollback_preview(gui_api_obj, tmp_path):
    """回滚预检桥：applied=可恢复 timing 数（去重），auto_insert=插入行数。"""
    guide = _make_rollback_env(tmp_path, [
        _applied_rec(_RT1, "甲（原）", "甲（已改）"),
        _applied_rec(_RT1, "甲（更早）", "甲（原）"),      # 同 timing 去重
        {"index": None, "timing": "", "category": "auto_insert",
         "old_text": "", "new_text": "补", "model_used": "",
         "outcome": "applied", "reason": "", "ts": "t",
         "source_partial": False},
    ])
    r = gui_api_obj.fullchain_rollback_preview(str(guide))
    assert r == {"success": True, "applied": 1, "auto_insert": 1}


# ---------------------------------------------------------------------------
# 3.0 批3 3B（D2026-1009-02 批3）：F4 链内接线+C22 门控+回滚删行+C23 四点
# ---------------------------------------------------------------------------

_MT = "00:00:05,000 --> 00:00:08,000"       # 漏听观察窗口（3s 语音能量）
_MTEXT = "ありがとう"


def _missed_item(index=9, timing=_MT, text=""):
    return {"index": index, "timing": timing, "category":
            "suspected_missed_speech", "message": "疑似漏听",
            "current_text": text, "source_excerpt": "", "status": "open",
            "severity": None}


def _make_missed_env(tmp_path: Path, *, items=None, media=True,
                     final=True, extras=None):
    """漏听段夹具：导读（含 suspected_missed_speech 观察+media_path）+
    哑媒体文件 + 终稿（final_stem 契约名）。"""
    from subtransjav.refine.filters import build_srt
    from subtransjav.refine.v2_outputs import final_stem
    media_path = ""
    if media:
        media_path = str(tmp_path / "ep01.mp4")
        Path(media_path).write_bytes(b"fake")
    guide = {"version": 2, "stem": _BF_GUIDE_STEM,
             "items": items if items is not None else [_missed_item()],
             "direction": "", "media_path": media_path,
             "language": "ja"}
    if extras is not None:
        guide["extras"] = extras
    p = tmp_path / f"{_BF_GUIDE_STEM}_质量报告导读.json"
    p.write_text(json.dumps(guide, ensure_ascii=False), encoding="utf-8")
    if final:
        entries = [
            {"index": 1, "timing": "00:00:01,000 --> 00:00:02,000",
             "text": "甲"},
            {"index": 2, "timing": "00:00:10,000 --> 00:00:11,000",
             "text": "乙"},
        ]
        (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt").write_text(
            build_srt(entries), encoding="utf-8")
    return p


def _install_missed_stubs(monkeypatch, *, text=_MTEXT):
    """打桩 detect_speech_windows（每窗口 3s 语音）+ batch_transcribe_
    clips（高置信段，三维全过门）；返回 (detect 调用, batch 调用)。"""
    import subtransjav.refine.asr_env as asr_mod
    import subtransjav.refine.audio_detect as ad_mod
    detect_calls: list = []
    batch_calls: list = []

    def _detect(media_path, gap_timings):
        detect_calls.append(list(gap_timings))
        return {t: [(5.0, 8.0)] for t in gap_timings}

    def _batch(media_path, timings, **kw):
        batch_calls.append(list(timings))
        return [{"timing": t, "ok": True, "text": text,
                 "segments": [{"no_speech_prob": 0.0,
                               "avg_logprob": -0.1,
                               "compression_ratio": 1.0}],
                 "error": ""} for t in timings]

    monkeypatch.setattr(ad_mod, "detect_speech_windows", _detect)
    monkeypatch.setattr(asr_mod, "batch_transcribe_clips", _batch)
    monkeypatch.setattr(asr_mod, "cleanup_clips", lambda *a, **kw: 0)
    return detect_calls, batch_calls


def test_fullchain_c22_gate_default_off_helper(gui_api_obj, monkeypatch,
                                               tmp_path):
    """_fullchain_c22_enabled fail-closed：缺失/损坏/enabled 非 True 均
    False；enabled is True 才放行（CONFIG_DIR 打桩）。"""
    import subtransjav.refine.config as cfg
    monkeypatch.setattr(cfg, "CONFIG_DIR", str(tmp_path))
    gui = gui_api_obj
    assert gui._fullchain_c22_enabled() is False       # 缺失
    p = tmp_path / "fullchain_c22.json"
    p.write_text("{broken", encoding="utf-8")
    assert gui._fullchain_c22_enabled() is False       # 损坏
    p.write_text(json.dumps({"enabled": False, "precision_lb": 0.9}),
                 encoding="utf-8")
    assert gui._fullchain_c22_enabled() is False       # 非 True
    p.write_text(json.dumps({"enabled": True, "precision_lb": 0.96,
                             "n": 60}), encoding="utf-8")
    assert gui._fullchain_c22_enabled() is True


def test_fullchain_missed_gate_off_abandons_all(gui_api_obj, monkeypatch,
                                                tmp_path, caplog):
    """门控缺省关：high 也全放弃——零终稿写入/零台账 auto_insert，
    notice 明示放弃数，last_run.missed_skipped 如实计数。"""
    import logging

    from subtransjav.refine.v2_outputs import final_stem
    guide = _make_missed_env(tmp_path)
    _install_missed_stubs(monkeypatch)
    final_before = (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt"
                    ).read_text(encoding="utf-8")
    run = {"missed_skipped": 0}
    with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
        gui_api_obj._run_fullchain_missed_stage(
            [{"guide_path": str(guide), "p": str(guide), "stem":
              _BF_GUIDE_STEM}], run)
    assert run["missed_skipped"] == 1
    assert (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt"
            ).read_text(encoding="utf-8") == final_before
    assert not (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").exists()
    assert any("C22 校准门未通过" in r.message and "全部放弃：1 条"
               in r.message for r in caplog.records), "放弃数须明示不静默"


def test_fullchain_missed_gate_on_inserts(gui_api_obj, monkeypatch,
                                          tmp_path):
    """门控开（CONFIG_DIR 打桩写 fullchain_c22.json enabled=true）：
    high 补行——终稿 +1 行且重编号/台账 auto_insert 10 键/写序契约
    （ledger 先于 final 落盘）/guide extras.auto_insert 标记/SRT 正文
    零标记。"""
    import subtransjav.refine.config as _cfg
    import subtransjav.refine.fs_utils as fs_mod
    from subtransjav.refine import action_retranslate as art
    from subtransjav.refine.filters import parse_srt
    from subtransjav.refine.v2_outputs import final_stem
    monkeypatch.setattr(_cfg, "CONFIG_DIR", str(tmp_path))
    guide = _make_missed_env(tmp_path, extras={"对齐率": "98.0%"})
    _install_missed_stubs(monkeypatch)
    (tmp_path / "fullchain_c22.json").write_text(
        json.dumps({"enabled": True, "precision_lb": 0.97, "n": 65}),
        encoding="utf-8")
    order: list = []
    real_append = art._append_ledger

    def _append(path, records):
        order.append("ledger")
        return real_append(path, records)

    _real_atomic = fs_mod._atomic_write_text

    def _atomic(path, text, **kwargs):
        order.append("atomic:" + Path(path).name)
        return _real_atomic(path, text)

    monkeypatch.setattr(art, "_append_ledger", _append)
    monkeypatch.setattr(fs_mod, "_atomic_write_text", _atomic)
    run = {"missed_skipped": 0}
    gui_api_obj._run_fullchain_missed_stage(
        [{"guide_path": str(guide), "p": str(guide), "stem":
          _BF_GUIDE_STEM}], run)
    assert run["missed_skipped"] == 0
    final = parse_srt(
        (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt").read_text(
            encoding="utf-8"))
    assert len(final) == 3
    # 插入按时间序落位（00:00:05 在两既有块之间），非追加队尾；
    # 时长经 CPS 压缩（5 字 ÷ 9.2 CPS ≈ 0.543s < 3s 窗口，防挤压）
    assert final[1]["text"] == _MTEXT
    assert final[1]["timing"] == "00:00:05,000 --> 00:00:05,543"
    assert final[2]["text"] == "乙"
    assert [e["timing"] for e in final] == [
        "00:00:01,000 --> 00:00:02,000",
        "00:00:05,000 --> 00:00:05,543",
        "00:00:10,000 --> 00:00:11,000"]
    # 台账 10 键闭集 + auto_insert 形态
    ledger = json.loads(
        (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").read_text(
            encoding="utf-8"))
    assert len(ledger) == 1
    rec = ledger[0]
    assert set(rec) == {"index", "timing", "category", "old_text",
                        "new_text", "model_used", "outcome", "reason",
                        "ts", "source_partial"}
    assert rec["category"] == "auto_insert" and rec["index"] is None
    assert rec["old_text"] == "" and rec["new_text"] == _MTEXT
    assert rec["outcome"] == "applied"
    assert rec["reason"] == "fullchain auto insert"
    # 写序契约：ledger 先于 final（其后为 guide extras 标记写回）
    assert order[:3] == ["ledger",
                         f"atomic:{_BF_GUIDE_STEM}_重翻记录.json",
                         f"atomic:{_BF_GUIDE_STEM}_final_cn.srt"]
    # guide extras.auto_insert 标记 + SRT 正文零标记
    guide_data = json.loads(guide.read_text(encoding="utf-8"))
    assert guide_data["extras"]["auto_insert"] == [
        {"timing": final[1]["timing"], "text": _MTEXT}]
    assert "auto_insert" not in (
        tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt").read_text(
            encoding="utf-8")


def test_fullchain_missed_gate_on_invariant_failure_abandons(
        gui_api_obj, monkeypatch, tmp_path, caplog):
    """插入恒等式失败防御（C15）：篡改 assert 抛 AssertionError → 该
    文件放弃，终稿/台账/extras 零落盘。"""
    import logging

    import subtransjav.refine.config as _cfg
    from subtransjav.refine import missed_insert as mi
    from subtransjav.refine.v2_outputs import final_stem
    monkeypatch.setattr(_cfg, "CONFIG_DIR", str(tmp_path))
    guide = _make_missed_env(tmp_path)
    _install_missed_stubs(monkeypatch)
    (tmp_path / "fullchain_c22.json").write_text(
        json.dumps({"enabled": True}), encoding="utf-8")

    def _boom(o, n, p):
        raise AssertionError("injected")

    monkeypatch.setattr(mi, "assert_insert_invariants", _boom)
    final_before = (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt"
                    ).read_text(encoding="utf-8")
    run = {"missed_skipped": 0}
    with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
        gui_api_obj._run_fullchain_missed_stage(
            [{"guide_path": str(guide), "p": str(guide), "stem":
              _BF_GUIDE_STEM}], run)
    assert run["missed_skipped"] == 1
    assert (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt"
            ).read_text(encoding="utf-8") == final_before
    assert not (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").exists()
    assert not (tmp_path / f"{_BF_GUIDE_STEM}_质量报告导读.json"
                ).is_file() or "auto_insert" not in json.loads(
        (tmp_path / f"{_BF_GUIDE_STEM}_质量报告导读.json").read_text(
            encoding="utf-8")).get("extras", {})
    assert any("恒等式校验失败" in r.message for r in caplog.records)


def test_fullchain_missed_c21_first_20(gui_api_obj, monkeypatch, tmp_path,
                                       caplog):
    """C21 仅前 20 明示：25 条观察 → 转写仅前 20 个 timing+notice。"""
    import logging
    guide = _make_missed_env(
        tmp_path,
        items=[_missed_item(100 + i,
                            f"00:00:{i + 5:02d},000 --> 00:00:{i + 6:02d},000")
               for i in range(25)])
    detect_calls, batch_calls = _install_missed_stubs(monkeypatch)
    run = {"missed_skipped": 0}
    with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
        gui_api_obj._run_fullchain_missed_stage(
            [{"guide_path": str(guide), "p": str(guide), "stem":
              _BF_GUIDE_STEM}], run)
    assert len(detect_calls) == 1 and len(detect_calls[0]) == 20
    assert batch_calls and len(batch_calls[0]) == 20
    assert any("仅处理前 20 条" in r.message and "共 25 条"
               in r.message for r in caplog.records)


def test_fullchain_missed_c18_no_media(gui_api_obj, monkeypatch, tmp_path,
                                       caplog):
    """C18 媒体缺失：notice 无音频对照+零 spawn（detect/batch 均不调）。"""
    import logging
    guide = _make_missed_env(tmp_path, media=False)
    detect_calls, batch_calls = _install_missed_stubs(monkeypatch)
    run = {"missed_skipped": 0}
    with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
        gui_api_obj._run_fullchain_missed_stage(
            [{"guide_path": str(guide), "p": str(guide), "stem":
              _BF_GUIDE_STEM}], run)
    assert run["missed_skipped"] == 1
    assert detect_calls == [] and batch_calls == []
    assert any("无音频对照" in r.message for r in caplog.records)


def test_fullchain_rollback_delete_clears_extras(gui_api_obj, tmp_path):
    """回滚删行收口：guide extras.auto_insert 同步清空；timing 未命中的
    插入行计入 unmatched。"""
    ins_t = "00:00:09,000 --> 00:00:10,000"
    guide = _make_rollback_env(tmp_path, [
        {"index": None, "timing": ins_t, "category": "auto_insert",
         "old_text": "", "new_text": "补行文本", "model_used": "",
         "outcome": "applied", "reason": "fullchain auto insert",
         "ts": "t", "source_partial": False},
    ], final_texts={_RT1: "甲（已改）"})
    # 种子 extras.auto_insert 标记 + 终稿含插入行
    gdata = json.loads(guide.read_text(encoding="utf-8"))
    gdata["extras"] = {"auto_insert": [{"timing": ins_t,
                                        "text": "补行文本"}]}
    guide.write_text(json.dumps(gdata, ensure_ascii=False),
                     encoding="utf-8")
    from subtransjav.refine.filters import build_srt
    from subtransjav.refine.v2_outputs import final_stem
    (tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt").write_text(
        build_srt([
            {"index": 1, "timing": _RT1, "text": "甲（已改）"},
            {"index": 2, "timing": _RT2, "text": "乙"},
            {"index": 3, "timing": ins_t, "text": "补行文本"},
        ]), encoding="utf-8")
    r = gui_api_obj.fullchain_rollback(str(guide))
    assert r["success"] is True
    assert r["restored"] == 0 and r["auto_insert_deleted"] == 1
    final = _read_rollback_final(tmp_path)
    assert [e["text"] for e in final] == ["甲（已改）", "乙"]  # 删行+重编号
    gdata = json.loads(guide.read_text(encoding="utf-8"))
    assert gdata["extras"]["auto_insert"] == []
    # 未命中：台账中 auto_insert timing 不在终稿 → unmatched（零删行）
    ins_miss = "00:00:20,000 --> 00:00:21,000"
    ledger = [{"index": None, "timing": ins_miss, "category":
               "auto_insert", "old_text": "", "new_text": "x",
               "model_used": "", "outcome": "applied", "reason": "r",
               "ts": "t", "source_partial": False}]
    (tmp_path / f"{_BF_GUIDE_STEM}_重翻记录.json").write_text(
        json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
    r2 = gui_api_obj.fullchain_rollback(str(guide))
    assert r2["unmatched"] == [ins_miss]
    assert r2["auto_insert_deleted"] == 0
    assert len(_read_rollback_final(tmp_path)) == 2            # 终稿未动


def _encode_env(gui_api_obj, monkeypatch, tmp_path):
    """C23 压制测试环境：视频/终稿伴生 + out_dir/commit 打桩。
    返回 (commits, params_box)。"""
    from subtransjav.refine.v2_outputs import final_stem
    monkeypatch.setattr(gui_api_obj, "encode_get_last_params",
                        lambda: {"params": {"out_dir": str(tmp_path)}})
    commits: list = []

    def _commit(jobs, params, allow_overwrite=False, from_fullchain=False):
        commits.append({"jobs": [dict(j) for j in jobs],
                        "allow_overwrite": allow_overwrite,
                        "from_fullchain": from_fullchain})
        return {"success": True}

    monkeypatch.setattr(gui_api_obj, "encode_commit", _commit)
    return commits, final_stem


def test_encode_skip_existing_mtime_requeue(gui_api_obj, monkeypatch,
                                            tmp_path, caplog):
    """C23③ skip-existing mtime 语义：成品旧于终稿 → 不跳过重新入队
    +notice；成品不旧于终稿 → 照旧跳过。"""
    import logging

    from subtransjav.refine.v2_outputs import final_stem
    _encode_env(gui_api_obj, monkeypatch, tmp_path)
    video = tmp_path / "ep01.mp4"
    video.write_bytes(b"v")
    sub = tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt"
    sub.write_text("1\n00:00:01,000 --> 00:00:02,000\n甲\n\n",
                   encoding="utf-8")
    out = tmp_path / "ep01_hardsub.mp4"
    summary = {"files": {str(sub): "done"}}
    with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
        # 成品较新 → 跳过
        out.write_bytes(b"new")
        future = time.time() + 100
        os.utime(out, (future, future))
        gui_api_obj._run_encode_automation(summary, from_fullchain=True)
        # 成品较旧 → 重新入队+notice
        out.write_bytes(b"old")
        os.utime(out, (time.time() - 100, time.time() - 100))
        gui_api_obj._run_encode_automation(summary, from_fullchain=True)
    notices = [r.message for r in caplog.records]
    assert any("成品已存在" in m for m in notices), "成品不旧于字幕照旧跳过"
    assert any("重新压制" in m for m in notices), "终稿晚于成品须重压通知"


def test_encode_auto_insert_sorted_last_and_checkpoint(
        gui_api_obj, monkeypatch, tmp_path, caplog):
    """C23①②：含 auto_insert 标记文件排队尾；标记有台账无 → 排除出
    自动压制+告警。"""
    import logging

    from subtransjav.refine.pipeline_support import GUIDE_JSON_SUFFIX
    from subtransjav.refine.v2_outputs import final_stem
    commits, _ = _encode_env(gui_api_obj, monkeypatch, tmp_path)
    # 两个文件：ep01（普通）、ep02（含 auto_insert 标记）
    jobs = []
    for stem, marks in (("ep01", None), ("ep02", [{"timing": "t",
                                                   "text": "补"}])):
        v = tmp_path / f"{stem}.mp4"
        v.write_bytes(b"v")
        sub = tmp_path / f"{final_stem(stem)}.srt"
        sub.write_text("1\n00:00:01,000 --> 00:00:02,000\n甲\n\n",
                       encoding="utf-8")
        gdata = {"version": 2, "stem": stem, "items": [], "direction": "",
                 "media_path": ""}
        if marks is not None:
            gdata["extras"] = {"auto_insert": marks}
        (tmp_path / f"{stem}{GUIDE_JSON_SUFFIX}").write_text(
            json.dumps(gdata, ensure_ascii=False), encoding="utf-8")
        jobs.append(str(sub))
    summary = {"files": {jobs[0]: "done", jobs[1]: "done"}}
    with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
        # 第一轮：ep02 标记有+台账无 → 排除+告警；仅 ep01 入队
        gui_api_obj._run_encode_automation(summary, from_fullchain=True)
        # 修复一致性（补台账）后：两文件入队且 ep02 排队尾
        ledger = [{"index": None, "timing": "t", "category":
                   "auto_insert", "old_text": "", "new_text": "补",
                   "model_used": "", "outcome": "applied", "reason": "r",
                   "ts": "t", "source_partial": False}]
        (tmp_path / "ep02_重翻记录.json").write_text(
            json.dumps(ledger, ensure_ascii=False), encoding="utf-8")
        gui_api_obj._run_encode_automation(summary, from_fullchain=True)
    notices = [r.message for r in caplog.records]
    assert any("来源不一致" in m and "ep02" in m for m in notices), \
        "标记有台账无不一致须告警"
    assert len(commits) == 2
    assert len(commits[0]["jobs"]) == 1, "不一致文件须排除出自动压制"
    order = [Path(j["subtitle_path"]).stem
             for j in commits[1]["jobs"]]
    assert order == [final_stem("ep01"), final_stem("ep02")], \
        f"含 auto_insert 标记文件须排队尾: {order}"


def test_encode_needs_confirm_mtime_requeue(gui_api_obj, monkeypatch,
                                            tmp_path, caplog):
    """C23③ 第二处：commit needs_confirm（入队瞬间出现新成品）时，终稿
    晚于成品 → allow_overwrite=True 重新入队；不旧 → 照旧跳过。"""
    import logging

    from subtransjav.refine.v2_outputs import final_stem
    calls: list = []

    def _commit(jobs, params, allow_overwrite=False, from_fullchain=False):
        calls.append({"n": len(jobs), "allow_overwrite": allow_overwrite})
        if len(calls) == 1 and not allow_overwrite:
            return {"success": False, "needs_confirm": True}
        return {"success": True}

    monkeypatch.setattr(gui_api_obj, "encode_get_last_params",
                        lambda: {"params": {"out_dir": str(tmp_path)}})
    monkeypatch.setattr(gui_api_obj, "encode_commit", _commit)
    video = tmp_path / "ep01.mp4"
    video.write_bytes(b"v")
    sub = tmp_path / f"{final_stem(_BF_GUIDE_STEM)}.srt"
    sub.write_text("1\n00:00:01,000 --> 00:00:02,000\n甲\n\n",
                   encoding="utf-8")
    out = tmp_path / "ep01_hardsub.mp4"
    out.write_bytes(b"old")
    os.utime(out, (time.time() - 100,) * 2)
    with caplog.at_level(logging.INFO, logger="subtransjav.gui"):
        gui_api_obj._run_encode_automation({"files": {str(sub): "done"}},
                                           from_fullchain=True)
    assert calls == [{"n": 1, "allow_overwrite": False},
                     {"n": 1, "allow_overwrite": True}]
    assert any("重新压制" in r.message for r in caplog.records)
