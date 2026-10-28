"""转写编排层测试（3.2 退役批 D2026-1029-01 收敛后）：ct2 唯一引擎分派、
对照块、切片、runner 定位与脚本直调防劫持。

legacy whisper 链（探测/候选/推荐清单/模型枚举/whisper 批量）契约钉已随
硬删移除；ct2 引擎契约钉在 test_asr_ct2.py，三维置信透传钉在
test_asr_ct2.TestConfidencePassthrough。"""
import json
from pathlib import Path

import pytest

from subtransjav.refine import asr_env


@pytest.fixture(autouse=True)
def _no_ct2_engine(monkeypatch):
    """编排层钉统一隔离 ct2 引擎（本机装了运行时时防劫持分派断言）。"""
    monkeypatch.setattr(asr_env, "_ct2_ready", lambda: False)


# ---------------------------------------------------------------------------
# run_transcription：ct2 唯一分派＋未装导向（退役批对冲钉）
# ---------------------------------------------------------------------------

def test_run_transcription_no_engine_guides_ct2_install():
    """未装运行时：唯一错误出口＝ct2 安装导向人话（「唯一引擎，首次使用
    需安装」口径）。"""
    r = asr_env.run_transcription("c.wav", asr_python="")
    assert r["ok"] is False
    assert "唯一引擎" in r["error"] and "asr_runtime install" in r["error"]


# ---------------------------------------------------------------------------
# build_crosscheck_block：C6 非真值声明/截断/detail 结构（D2026-1010-03 件A）
# ---------------------------------------------------------------------------

def test_build_crosscheck_block_whitelist_and_limit(monkeypatch, tmp_path):
    """C6：非真值声明在、≤2000 截断；ASR 文本进块、失败段降级展示。"""
    clip = tmp_path / "c.wav"
    clip.write_bytes(b"wav")

    def _fake_rt(clip, asr_python="", model="large-v2", language="ja",
                 timeout=300):
        return {"ok": True, "text": "转写内容" * 300, "error": ""}

    monkeypatch.setattr(asr_env, "run_transcription", _fake_rt)
    clips = [{"path": str(clip), "timing": "T1", "current": "现译一句"}]
    r = asr_env.build_crosscheck_block(clips)
    assert r["segments"] == 1
    assert "非真值" in r["block"]
    assert len(r["block"]) <= 2000
    # D2026-1010-03 件A：detail 结构化对照段全文不截断（与喂 LLM 的
    # block 截断口径分离），随 _AI质量建议.json 落盘供 GUI 媒体对照区
    assert r["detail"] == [{"timing": "T1",
                            "asr_text": "转写内容" * 300,
                            "current_text": "现译一句"}]
    r2 = asr_env.build_crosscheck_block([])
    assert r2["block"] == "" and r2["segments"] == 0
    assert r2["detail"] == []


def test_build_crosscheck_block_detail_keys_and_failed_excluded(
        monkeypatch, tmp_path):
    """D2026-1010-03 件A：detail 仅收成功段（失败段只进 block 展示），
    键闭集 {timing, asr_text, current_text}。"""
    clip = tmp_path / "c.wav"
    clip.write_bytes(b"wav")
    calls = {"n": 0}

    def _fake_rt(clip, asr_python="", model="large-v2", language="ja",
                 timeout=300):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"ok": True, "text": "成功段转写", "error": ""}
        return {"ok": False, "text": "", "error": "boom"}

    monkeypatch.setattr(asr_env, "run_transcription", _fake_rt)
    clips = [{"path": str(clip), "timing": "T1", "current": "现译甲"},
             {"path": str(clip), "timing": "T2", "current": "现译乙"}]
    r = asr_env.build_crosscheck_block(clips)
    assert r["segments"] == 1 and r["failed"] == 1
    assert r["detail"] == [{"timing": "T1", "asr_text": "成功段转写",
                            "current_text": "现译甲"}]
    for seg in r["detail"]:
        assert set(seg) == {"timing", "asr_text", "current_text"}


# ---------------------------------------------------------------------------
# slice_clips：选段/截断/清理（C8）
# ---------------------------------------------------------------------------

def test_slice_clips_caps_and_cleans(monkeypatch, tmp_path):
    monkeypatch.setattr(asr_env.shutil, "which",
                        lambda n: str(tmp_path / "ffmpeg.exe"))
    media = tmp_path / "m.mp4"
    media.write_bytes(b"media")
    created = []

    def _fake_run(cmd, **kw):
        out = Path(cmd[-1])
        out.write_bytes(b"wav")
        created.append(out)
        from types import SimpleNamespace
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    timings = [f"00:{i // 60:02d}:{i % 60:02d},000 --> "
               f"00:{(i + 1) // 60:02d}:{(i + 1) % 60:02d},000"
               for i in range(25)]
    r = asr_env.slice_clips(str(media), timings)
    assert r["ok"] is True and len(r["clips"]) == asr_env._MAX_CLIPS == 20
    assert all(Path(c["path"]).is_file() for c in r["clips"])
    n = asr_env.cleanup_clips()
    assert n == len(created)


def test_slice_clips_no_ffmpeg_degrades(monkeypatch, tmp_path):
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: None)
    r = asr_env.slice_clips(str(tmp_path / "m.mp4"), ["T1"])
    assert r["ok"] is False and "ffmpeg" in r["error"]


def test_resolve_ffmpeg_path_only(monkeypatch, tmp_path):
    """退役批（D2026-1029-01）：resolve_ffmpeg=PATH which 单源（上游 python
    相对候选目录语义随 whisper 链删除）。"""
    monkeypatch.setattr(asr_env.shutil, "which",
                        lambda n: str(tmp_path / "ffmpeg.exe"))
    assert asr_env.resolve_ffmpeg() == str(tmp_path / "ffmpeg.exe")
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: None)
    assert asr_env.resolve_ffmpeg() == ""


# ---------------------------------------------------------------------------
# C6 双钉：media_crosscheck_enabled 注册 + 负向钉（不进指纹）
# ---------------------------------------------------------------------------

def test_media_crosscheck_flag_registered_and_not_in_fingerprint():
    """2.6.1 修订（D2026-1002-06）：默认值翻转 False（验证可选化）。"""
    from subtransjav.refine.config import TUNABLE_FIELD_TYPES, RefineConfig
    from subtransjav.refine.manifest import _CONFIG_FIELDS
    assert TUNABLE_FIELD_TYPES.get("media_crosscheck_enabled") is bool
    assert "media_crosscheck_enabled" not in _CONFIG_FIELDS
    assert "asr_model" not in _CONFIG_FIELDS
    assert "asr_python" not in _CONFIG_FIELDS
    assert RefineConfig(inputs=["a.srt"]).media_crosscheck_enabled is False


# ---------------------------------------------------------------------------
# C3 导入图钉：asr_runner 顶部仅标准库（faster_whisper 懒加载）
# ---------------------------------------------------------------------------

def test_asr_runner_import_chain_stdlib_only():
    import ast
    src = Path(asr_env.__file__).parent / "asr_runner.py"
    tree = ast.parse(src.read_text(encoding="utf-8"))
    top_imports = []
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = ([a.name for a in node.names]
                     if isinstance(node, ast.Import)
                     else [node.module or ""])
            top_imports.extend(names)
    assert top_imports == ["argparse", "json", "os", "sys"], \
        f"运行器顶部导入面漂移（C3 导入图钉）: {top_imports}"


# ---------------------------------------------------------------------------
# 批3 扩展（D2026-1002-12）：系统状态卡角色卡目录行（复用 refine_list_
# templates）跨面钉随 quality_advisor 侧；此处仅 runner 定位三钉
# ---------------------------------------------------------------------------

def test_runner_script_path_dev(monkeypatch):
    """dev 形态：包内同目录 asr_runner.py 直取。"""
    import sys
    monkeypatch.delattr(sys, "frozen", raising=False)
    p = asr_env._runner_script_path()
    assert p and Path(p).is_file() and Path(p).name == "asr_runner.py"


def test_runner_script_path_frozen_internal(monkeypatch, tmp_path):
    """frozen：exe 同目录 _internal/subtransjav/refine/asr_runner.py 命中。"""
    import sys
    exe = tmp_path / "SubTrans.exe"
    exe.write_bytes(b"")
    runner = (tmp_path / "_internal" / "subtransjav" / "refine"
              / "asr_runner.py")
    runner.parent.mkdir(parents=True)
    runner.write_text("# runner", encoding="utf-8")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe), raising=False)
    assert asr_env._runner_script_path() == str(runner)


def test_runner_script_path_frozen_fallback_and_miss(monkeypatch, tmp_path):
    """frozen 回退：_internal 缺失→exe 同目录；都无→空串。"""
    import sys
    exe = tmp_path / "SubTrans.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe), raising=False)
    assert asr_env._runner_script_path() == ""
    fb = tmp_path / "asr_runner.py"
    fb.write_text("# runner", encoding="utf-8")
    assert asr_env._runner_script_path() == str(fb)


# ---------------------------------------------------------------------------
# 2.7.1 热修回归钉（ct2 形态改写）：脚本直调防 secrets.py 劫持标准库
# ---------------------------------------------------------------------------

def test_runner_direct_call_no_stdlib_hijack():
    """回归钉①（指定差分，ct2 形态）：venv python（无 faster_whisper）直调
    runner 脚本——预期失败="No module named 'faster_whisper'"，而非
    "No module named 'subtransjav'"（secrets.py 劫持消除的可区分失败面）。"""
    import subprocess
    import sys as _sys
    import tempfile
    runner = Path(asr_env.__file__).parent / "asr_runner.py"
    with tempfile.TemporaryDirectory() as td:
        media = Path(td) / "a.wav"
        media.write_bytes(b"RIFF")
        mdir = Path(td) / "m"
        mdir.mkdir()
        proc = subprocess.run(
            [_sys.executable, str(runner), "--engine", "ct2",
             "--media", str(media), "--srt-out", str(Path(td) / "o.srt"),
             "--model-dir", str(mdir)],
            capture_output=True, encoding="utf-8", errors="replace",
            timeout=120, cwd=str(Path(asr_env.__file__).parent))
    lines = [ln for ln in (proc.stdout or "").splitlines()
             if ln.strip().startswith("{")]
    assert lines, f"runner 无 JSON 输出: {proc.stdout!r} {proc.stderr!r}"
    payload = json.loads(lines[-1])
    assert payload["ok"] is False
    assert "No module named 'faster_whisper'" in payload["error"]
    # 劫持可区分面：失败原因链不含 "No module named 'subtransjav'"
    # （被劫持时 refine/secrets.py 顶部 import 先炸出该错；注意安装指引
    # 文案本身含 subtransjav 字样，须按完整错误形态匹配）
    assert "No module named 'subtransjav'" not in payload["error"], \
        "secrets.py 仍劫持标准库导入链（sys.path 自清失效）"


def test_runner_direct_call_secrets_resolves_stdlib(tmp_path):
    """回归钉②（机制差分，本机实测复现布局，ct2 形态）：脚本目录含与标准库
    同名 secrets.py + PYTHONPATH 注入 fake faster_whisper（__init__ 抛出
    所引 secrets 模块路径）——直调 runner 后 secrets 必须解析到标准库而非
    脚本目录影子（未修复时 sys.path[0]=脚本目录，影子先命中→路径指向影子
    文件）。"""
    import os
    import shutil
    import subprocess
    import sys as _sys
    real_runner = Path(asr_env.__file__).parent / "asr_runner.py"
    dir_a = tmp_path / "A"          # 脚本目录（含毒化 secrets 影子）
    dir_b = tmp_path / "B"          # fake faster_whisper（经 PYTHONPATH 注入）
    dir_a.mkdir()
    dir_b.mkdir()
    shutil.copy(real_runner, dir_a / "asr_runner.py")
    (dir_a / "secrets.py").write_text(
        "from subtransjav import paths\n", encoding="utf-8")
    (dir_b / "faster_whisper.py").write_text(
        "import secrets\n"
        "\n"
        "\n"
        "class WhisperModel:\n"
        "    def __init__(self, *a, **k):\n"
        "        raise RuntimeError('fake-secrets-probe:' + secrets.__file__)\n",
        encoding="utf-8")
    media = tmp_path / "a.wav"
    media.write_bytes(b"RIFF")
    mdir = tmp_path / "m"
    mdir.mkdir()
    env = dict(os.environ, PYTHONPATH=str(dir_b))
    proc = subprocess.run(
        [_sys.executable, str(dir_a / "asr_runner.py"), "--engine", "ct2",
         "--media", str(media), "--srt-out", str(tmp_path / "o.srt"),
         "--model-dir", str(mdir)],
        capture_output=True, encoding="utf-8", errors="replace", timeout=120,
        env=env, cwd=str(tmp_path))
    lines = [ln for ln in (proc.stdout or "").splitlines()
             if ln.strip().startswith("{")]
    assert lines, f"runner 无 JSON 输出: {proc.stdout!r} {proc.stderr!r}"
    payload = json.loads(lines[-1])
    assert payload["ok"] is False, payload
    assert "fake-secrets-probe:" in payload["error"], payload
    ver = payload["error"].split("fake-secrets-probe:", 1)[1]
    assert Path(ver).name == "secrets.py"
    assert dir_a not in Path(ver).resolve().parents, \
        f"secrets 仍被脚本目录影子劫持: {ver}"
