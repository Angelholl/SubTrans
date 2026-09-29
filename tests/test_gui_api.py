"""webview_gui.api 浅层测试（P3-10/P3-11）。

不启动任何窗口：
- ``_build_refine_args`` 为模块级纯函数，直接调用；
- ``scan_resume_states`` 不依赖实例状态，用 ``object.__new__`` 构造实例，
  规避 ``__init__`` 的副作用（Documents 建目录 / atexit 注册）；
- URL/endpoint 守卫入口在发起任何网络请求之前即短路，无网络副作用。
"""
import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path
from types import SimpleNamespace

import openai
import pytest

pytestmark = [pytest.mark.gui]

pytest.importorskip("webview", reason="pywebview 为可选 gui extra，未安装时跳过 GUI API 测试", exc_type=ImportError)

from subtransjav.webview_gui.api import (  # noqa: E402  须在 importorskip 之后
    REPO_ROOT,
    SESSION_SELECTED_PATHS,
    TranslateAPI,
    _build_refine_args,
    register_session_paths,
)


@pytest.fixture()
def gui_api_obj():
    """无副作用的 TranslateAPI 实例 + 干净的会话路径登记表。"""
    SESSION_SELECTED_PATHS.clear()
    yield object.__new__(TranslateAPI)
    SESSION_SELECTED_PATHS.clear()


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
    args = _build_refine_args({"inputs": ["a.srt"], "glossary_learn": True})
    assert "--glossary-learn" in args


def test_build_refine_args_glossary_learn_absent_by_default():
    args = _build_refine_args({"inputs": ["a.srt"]})
    assert "--glossary-learn" not in args


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


def _install_fake_ai_run(monkeypatch, *, returncode=0, stderr="",
                         raise_timeout=False):
    """替身 subprocess.run：捕获 CLI 参数与环境，杜绝真实子进程。"""
    import subtransjav.webview_gui.api as api_mod
    captured: dict = {}

    def _fake_run(args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        if raise_timeout:
            raise subprocess.TimeoutExpired(cmd=args, timeout=600)
        return SimpleNamespace(returncode=returncode, stderr=stderr,
                               stdout="")

    monkeypatch.setattr(api_mod.subprocess, "run", _fake_run)
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
    assert kw.get("timeout") == 600
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
    env = captured["kwargs"].get("env") or {}
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
    env = captured["kwargs"].get("env") or {}
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
    env = captured["kwargs"].get("env") or {}
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
    assert captured == {}, "前置拒绝必须发生在 subprocess 之前"


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


def _install_fake_ffprobe(monkeypatch, video="", audio=""):
    """替身 ffprobe 链路：shutil.which 命中 + subprocess.run 返回 codec JSON。"""
    import subtransjav.webview_gui.api as api_mod
    captured: dict = {}

    def _fake_run(args, **kwargs):
        captured["args"] = args
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
    """导读缺 media_path 且未显式指定 → 结构化失败（前端提示显式指定）。"""
    guide = _make_guide(tmp_path)
    r = gui_api_obj.refine_audio_preview(str(guide), 0.0, 2.0)
    assert r["ok"] is False
    assert "媒体路径" in r["error"]


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
    assert set(got["dicts"]) == {"sudachi", "jieba", "english_rules"}
    assert got["dicts"]["english_rules"]["available"] is True


def test_refine_dict_download_unsupported_kind(gui_api_obj):
    got = gui_api_obj.refine_dict_download("jieba")
    assert got["success"] is False
    assert "不支持下载" in got["error"]


def test_refine_dict_download_success_and_checksum(gui_api_obj, monkeypatch,
                                                   tmp_path):
    from subtransjav.refine import dict_manager as dm
    from subtransjav.refine.dict_manager import DictChecksumError, DictDownloadError
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    # api 方法为函数内导入，patch 源模块属性才生效
    monkeypatch.setattr(dm, "download_dict",
                        lambda kind: str(tmp_path / "dict" / "system_core.dic"))
    got = gui_api_obj.refine_dict_download("sudachi")
    assert got["success"] is True

    def _raise_checksum(kind):
        raise DictChecksumError("SHA256 不符")

    monkeypatch.setattr(dm, "download_dict", _raise_checksum)
    got2 = gui_api_obj.refine_dict_download("sudachi")
    assert got2["success"] is False
    assert "校验失败" in got2["error"]

    def _raise_net(kind):
        raise DictDownloadError("超时")

    monkeypatch.setattr(dm, "download_dict", _raise_net)
    got3 = gui_api_obj.refine_dict_download("sudachi")
    assert got3["success"] is False
    assert "下载失败" in got3["error"]


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
