"""ASR 测试：探测/运行器协议/切片/双钉（2.6.0 批3）＋模型推荐制
（2.6.1 修订 D2026-1002-06：默认值翻转/推荐清单/resolve_model_dir/
--model-dir 契约；下载链 4 例已随下载链删除）。"""
import json
from pathlib import Path
from types import SimpleNamespace

from subtransjav.refine import asr_env

# ---------------------------------------------------------------------------
# probe_asr_env：候选优先级 + selfcheck 真实契约（C2/C9）
# ---------------------------------------------------------------------------

def test_probe_prefers_env_over_default(monkeypatch, tmp_path):
    calls = []

    def _fake_run(cmd, **kw):
        calls.append(cmd[0])
        payload = json.dumps({"ok": True, "info": {
            "whisper_version": "3.1", "model_present": True}})
        return SimpleNamespace(returncode=0, stdout=payload, stderr="")

    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "envpy.exe"))
    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    (tmp_path / "envpy.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: str(tmp_path / "ff"))
    r = asr_env.probe_asr_env()
    assert r["python_source"] == "env"
    assert calls and calls[0].endswith("envpy.exe")
    assert r["whisper_version"] == "3.1"
    assert "模型缓存" in r["reason"]


def test_probe_degrades_when_all_candidates_fail(monkeypatch):
    monkeypatch.delenv("SUBTRANSJAV_ASR_PYTHON", raising=False)
    monkeypatch.setattr(asr_env.subprocess, "run",
                        lambda cmd, **kw: (_ for _ in ()).throw(
                            subprocess_draft_timeout()))
    r = asr_env.probe_asr_env(asr_python_setting="")
    assert r["available"] is False and r["reason"]


def subprocess_draft_timeout():
    import subprocess
    raise subprocess.TimeoutExpired(cmd=["x"], timeout=60)


# ---------------------------------------------------------------------------
# asr_runner 协议：JSON 契约解析（fake 子进程）
# ---------------------------------------------------------------------------

def test_run_transcription_parses_runner_json(monkeypatch, tmp_path):
    clip = tmp_path / "c.wav"
    clip.write_bytes(b"wav")
    # 显式候选必须真实存在（os.path.isfile 探测）：否则 linux CI 上全部候选
    # 落空 → 探测降级提前返回 ok=False（owner 机器默认路径存在掩盖此问题）
    py = tmp_path / "p.exe"
    py.write_text("", encoding="utf-8")
    payload = json.dumps({"ok": True, "text": "テスト",
                          "segments": [{"start": 0, "end": 1,
                                        "text": "テスト"}]},
                         ensure_ascii=False)

    def _fake_run(cmd, **kw):
        assert "--model" in cmd and "large-v2" in cmd
        return SimpleNamespace(returncode=0, stdout=payload, stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    r = asr_env.run_transcription(str(clip), asr_python=str(py))
    assert r["ok"] is True and r["text"] == "テスト"


def test_run_transcription_no_python_degrades(monkeypatch):
    monkeypatch.delenv("SUBTRANSJAV_ASR_PYTHON", raising=False)
    monkeypatch.setattr(asr_env.os.path, "isfile", lambda p: False)
    r = asr_env.run_transcription("c.wav", asr_python="")
    assert r["ok"] is False and "探测降级" in r["error"]


def test_build_crosscheck_block_whitelist_and_limit(monkeypatch, tmp_path):
    """C6：非真值声明在、≤2000 截断；ASR 文本进块、失败段降级展示。"""
    clip = tmp_path / "c.wav"
    clip.write_bytes(b"wav")
    # 显式候选真实存在（同 test_run_transcription：防 linux CI 探测降级）
    py = tmp_path / "p.exe"
    py.write_text("", encoding="utf-8")

    def _fake_run(cmd, **kw):
        payload = json.dumps({"ok": True, "text": "转写内容" * 300},
                             ensure_ascii=False)
        return SimpleNamespace(returncode=0, stdout=payload, stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(py))
    clips = [{"path": str(clip), "timing": "T1", "current": "现译一句"}]
    r = asr_env.build_crosscheck_block(clips)
    assert r["segments"] == 1
    assert "非真值" in r["block"]
    assert len(r["block"]) <= 2000
    r2 = asr_env.build_crosscheck_block([])
    assert r2["block"] == "" and r2["segments"] == 0


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
# C3 导入图钉：asr_runner 顶部仅标准库（whisper 懒加载）
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
    assert "whisper" not in top_imports


# ---------------------------------------------------------------------------
# 2.6.1 修订（D2026-1002-06，模型推荐制）：推荐清单形态 + resolve_model_dir
# 顺序 + 运行器 --model-dir 契约（下载 4 例随下载链删除）
# ---------------------------------------------------------------------------

def test_recommended_models_shape():
    """whisper 条目带 url/bytes/sha256（available）；qwen 条目 planned 无下载字段。"""
    assert len(asr_env.ASR_RECOMMENDED_MODELS) == 2
    w = next(e for e in asr_env.ASR_RECOMMENDED_MODELS
             if e["name"] == "whisper-large-v2")
    assert w["support"] == "available"
    assert w["url"].startswith("https://openaipublic.azureedge.net/")
    assert w["url"].endswith("/large-v2.pt")
    assert w["bytes"] == 3086999982
    assert w["sha256"] == ("81f7c96c852ee8fc832187b0132e569d6c3065a3252ed18"
                           "e56effd0b6a73e524")
    assert w["model"] == "large-v2"
    q = next(e for e in asr_env.ASR_RECOMMENDED_MODELS
             if e["name"] == "qwen3-asr-1.7b")
    assert q["support"] == "planned"
    assert "url" not in q and "bytes" not in q and "sha256" not in q


def test_resolve_model_dir_cache_hit_returns_none(monkeypatch, tmp_path):
    """缓存命中→None（原生加载点优先，不传旗标）。"""
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "large-v2.pt").write_bytes(b"x")
    monkeypatch.setattr(asr_env, "ASR_CACHE_DIR", str(cache))
    monkeypatch.setattr(asr_env, "ASR_MODELS_ROOT", str(tmp_path / "root"))
    assert asr_env.resolve_model_dir("large-v2") is None


def test_resolve_model_dir_data_root_hit(monkeypatch, tmp_path):
    """仅数据根命中→返回该目录字符串。"""
    root = tmp_path / "root"
    root.mkdir()
    (root / "large-v2.pt").write_bytes(b"x")
    monkeypatch.setattr(asr_env, "ASR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(asr_env, "ASR_MODELS_ROOT", str(root))
    assert asr_env.resolve_model_dir("large-v2") == str(root)


def test_resolve_model_dir_missing_returns_none(monkeypatch, tmp_path):
    monkeypatch.setattr(asr_env, "ASR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(asr_env, "ASR_MODELS_ROOT", str(tmp_path / "root"))
    assert asr_env.resolve_model_dir("large-v2") is None


def _install_fake_whisper(monkeypatch):
    import sys
    import types
    fake = types.ModuleType("whisper")
    fake.__version__ = "9.9"
    monkeypatch.setitem(sys.modules, "whisper", fake)


def test_runner_selfcheck_model_dir_custom(monkeypatch, tmp_path, capsys):
    """--model-dir 契约：model_present 查自定义目录 + model_dir 回显。"""
    import subtransjav.refine.asr_runner as runner
    _install_fake_whisper(monkeypatch)
    (tmp_path / "large-v2.pt").write_bytes(b"x")
    rc = runner._selfcheck("large-v2", str(tmp_path))
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and out["ok"] is True
    assert out["info"]["model_dir"] == str(tmp_path)
    assert out["info"]["model_path"] == str(tmp_path / "large-v2.pt")
    assert out["info"]["model_present"] is True


def test_runner_selfcheck_default_cache(monkeypatch, capsys):
    """不给 --model-dir 维持原生 ~/.cache/whisper 行为。"""
    import os

    import subtransjav.refine.asr_runner as runner

    _install_fake_whisper(monkeypatch)
    rc = runner._selfcheck("large-v2", "")
    out = json.loads(capsys.readouterr().out.strip())
    expected = os.path.join(os.path.expanduser("~"), ".cache", "whisper",
                            "large-v2.pt")
    assert rc == 0 and out["ok"] is True
    assert out["info"]["model_dir"] == ""
    assert out["info"]["model_path"] == expected
    assert out["info"]["model_present"] == os.path.isfile(expected)


def _install_fake_whisper_recorder(monkeypatch):
    """注入记录 load_model 调用参数的 fake whisper（转写路径契约钉）。"""
    import sys
    import types
    calls = {}

    class _FakeModel:
        def transcribe(self, audio, **kw):
            return {"text": "テスト",
                    "segments": [{"start": 0.0, "end": 1.0,
                                  "text": "テスト"}]}

    fake = types.ModuleType("whisper")
    fake.__version__ = "9.9"

    def _load_model(name, **kwargs):
        calls["name"] = name
        calls["kwargs"] = kwargs
        return _FakeModel()

    fake.load_model = _load_model
    monkeypatch.setitem(sys.modules, "whisper", fake)
    return calls


def test_runner_transcribe_load_model_receives_download_root(monkeypatch,
                                                             tmp_path,
                                                             capsys):
    """硬门槛（D2026-1002-06）：转写路径真以 download_root=<目录> 调
    whisper.load_model，且 transcribe 用返回的模型对象调用。"""
    import subtransjav.refine.asr_runner as runner
    calls = _install_fake_whisper_recorder(monkeypatch)
    audio = tmp_path / "c.wav"
    audio.write_bytes(b"wav")
    model_dir = str(tmp_path / "root")
    rc = runner._run_transcribe(str(audio), "large-v2", "ja", model_dir)
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and out["ok"] is True
    assert out["text"] == "テスト"
    assert calls["name"] == "large-v2"
    assert calls["kwargs"].get("download_root") == model_dir


def test_runner_transcribe_without_model_dir_no_download_root(monkeypatch,
                                                              tmp_path,
                                                              capsys):
    """硬门槛：不给 model_dir → load_model 不带有效 download_root
    （None=原生 ~/.cache/whisper 行为不变）。"""
    import subtransjav.refine.asr_runner as runner
    calls = _install_fake_whisper_recorder(monkeypatch)
    audio = tmp_path / "c.wav"
    audio.write_bytes(b"wav")
    rc = runner._run_transcribe(str(audio), "large-v2", "ja", "")
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and out["ok"] is True
    assert calls["kwargs"].get("download_root") is None


def test_run_transcription_argv_carries_model_dir(monkeypatch, tmp_path):
    """resolve_model_dir 有值时运行器 argv 追加 --model-dir（同序保证）。"""
    clip = tmp_path / "c.wav"
    clip.write_bytes(b"wav")
    root = tmp_path / "root"
    root.mkdir()
    (root / "large-v2.pt").write_bytes(b"x")
    monkeypatch.setattr(asr_env, "ASR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(asr_env, "ASR_MODELS_ROOT", str(root))
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "p.exe"))
    (tmp_path / "p.exe").write_text("", encoding="utf-8")
    seen = {}

    def _fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0,
                               stdout=json.dumps({"ok": True, "text": "t"}),
                               stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    r = asr_env.run_transcription(str(clip))
    assert r["ok"] is True
    cmd = seen["cmd"]
    assert "--model-dir" in cmd
    assert cmd[cmd.index("--model-dir") + 1] == str(root)


def test_run_transcription_no_model_dir_flag_when_unresolved(monkeypatch,
                                                             tmp_path):
    """缓存/数据根都无 → 不传 --model-dir（原生行为）。"""
    clip = tmp_path / "c.wav"
    clip.write_bytes(b"wav")
    monkeypatch.setattr(asr_env, "ASR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(asr_env, "ASR_MODELS_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "p.exe"))
    (tmp_path / "p.exe").write_text("", encoding="utf-8")
    seen = {}

    def _fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0,
                               stdout=json.dumps({"ok": True, "text": "t"}),
                               stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    r = asr_env.run_transcription(str(clip))
    assert r["ok"] is True
    assert "--model-dir" not in seen["cmd"]


def test_probe_selfcheck_carries_model_dir(monkeypatch, tmp_path):
    """探测与加载同序：probe 的 selfcheck 子进程也带 --model-dir。"""
    root = tmp_path / "root"
    root.mkdir()
    (root / "large-v2.pt").write_bytes(b"x")
    monkeypatch.setattr(asr_env, "ASR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(asr_env, "ASR_MODELS_ROOT", str(root))
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: None)
    seen = {}

    def _fake_run(cmd, **kw):
        seen["cmd"] = cmd
        payload = json.dumps({"ok": True, "info": {
            "whisper_version": "3.1", "model_present": True}})
        return SimpleNamespace(returncode=0, stdout=payload, stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "p.exe"))
    (tmp_path / "p.exe").write_text("", encoding="utf-8")
    r = asr_env.probe_asr_env()
    assert r["available"] is False      # ffmpeg 缺失（本测只看 argv）
    cmd = seen["cmd"]
    assert "--model-dir" in cmd
    assert cmd[cmd.index("--model-dir") + 1] == str(root)


# ---------------------------------------------------------------------------
# 注入 additive（C2 批 3 同款）：crosscheck_block 第五块
# ---------------------------------------------------------------------------

def test_analyze_injects_crosscheck_block_additively():
    from subtransjav.refine import quality_advisor as qa
    captured = {}

    def _chat(system, user):
        captured["user"] = user
        return json.dumps({"glossary": [], "tm": [],
                           "observations": ["o"]}, ensure_ascii=False)

    guide = {"version": 2, "items": []}
    qa.analyze_quality_report("【结论】x", guide, "", "m1", chat_fn=_chat,
                              crosscheck_block="媒体对照内容ABC")
    user = captured["user"]
    assert user.count(qa._DATA_BEGIN) == 3          # 报告+导读+对照（无聚合/冲突）
    assert "媒体重点对照（本地 ASR 重转写，非真值，仅供漏听/" in user
    assert "媒体对照内容ABC" in user
    # 空缺省：字节不变（回归既有 3 块口径由 test_quality_advisor 覆盖）
