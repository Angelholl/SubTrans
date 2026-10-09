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
    # 2.7.1 件1：候选目录扫描同读（防真机上游 env 目录恰好带 ffmpeg.exe 干扰）
    monkeypatch.setattr(asr_env, "_candidate_ffmpeg_dirs", lambda p: [])
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
    """whisper 条目带 url/bytes/sha256（available）；qwen 条目 planned 无下载字段。

    2.7.1：清单扩至 6 条（tiny/base/small/medium/large-v2/qwen3），whisper
    条目带 tier/desc/spec/backend/variants 面板元数据。"""
    assert len(asr_env.ASR_RECOMMENDED_MODELS) == 6
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


def test_recommended_models_sources_and_license():
    """2.6.3 批B（D2026-1003-01 ②）：whisper 条目增 license/sources 双源——
    official verified 且 url/sha256 与条目 pin 原样一致；mirror 已点亮
    （D2026-1005-05，2026-10-10：verified=True + hf-mirror 直链 + sha256
    与官方 pin 字节级一致）。qwen 条目不动。"""
    w = next(e for e in asr_env.ASR_RECOMMENDED_MODELS
             if e["name"] == "whisper-large-v2")
    assert w["license"] == "MIT（openai/whisper 上游模型卡口径）"
    srcs = w["sources"]
    assert [s["source"] for s in srcs] == ["official", "mirror"]
    off, mir = srcs
    assert off["label"] == "官方源" and off["verified"] is True
    assert off["url"] == w["url"] and off["sha256"] == w["sha256"]
    assert mir["label"] == "国内加速源" and mir["verified"] is True
    assert mir["url"] == ("https://hf-mirror.com/Angelholl/openai-whisper-pt"
                          "/resolve/7b3ad79575c53f369fbdb17060e6cf14c66cdc96"
                          "/large-v2.pt")
    assert mir["sha256"] == w["sha256"]
    q = next(e for e in asr_env.ASR_RECOMMENDED_MODELS
             if e["name"] == "qwen3-asr-1.7b")
    assert "sources" not in q and "license" not in q


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


# ---------------------------------------------------------------------------
# 2.7.1（D2026-1005-01 承接批）：runner 定位/脚本直调、ffmpeg 泛化、探测
# 三分类 triage、HF hub 三级 env 链、探测总预算、快照缓存、面板元数据
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


def test_runner_command_script_direct_and_dev_fallback(monkeypatch):
    """脚本直调形态优先；定位失败回退 -m（dev-only，frozen 数据根无包）。"""
    monkeypatch.setattr(asr_env, "_runner_script_path",
                        lambda: "C:/r/asr_runner.py")
    cmd = asr_env._runner_command("py.exe", "--selfcheck", "--model", "m")
    assert cmd == ["py.exe", "C:/r/asr_runner.py", "--selfcheck",
                   "--model", "m"]
    monkeypatch.setattr(asr_env, "_runner_script_path", lambda: "")
    cmd2 = asr_env._runner_command("py.exe", "--audio", "a.wav")
    assert cmd2[:3] == ["py.exe", "-m", "subtransjav.refine.asr_runner"]


def test_probe_selfcheck_uses_runner_script_path(monkeypatch, tmp_path):
    """探测命令走脚本路径直调形态（无 -m 段）。"""
    monkeypatch.setattr(asr_env, "_runner_script_path",
                        lambda: str(tmp_path / "asr_runner.py"))
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "p.exe"))
    (tmp_path / "p.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: None)
    seen = {}

    def _fake_run(cmd, **kw):
        seen["cmd"] = cmd
        return SimpleNamespace(returncode=0, stdout=json.dumps(
            {"ok": True, "info": {"whisper_version": "3.1",
                                  "model_present": True}}), stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    asr_env.probe_asr_env()
    assert seen["cmd"][1] == str(tmp_path / "asr_runner.py")
    assert "-m" not in seen["cmd"]


def test_candidate_ffmpeg_dirs_layouts(tmp_path):
    """候选目录：Library/bin、Scripts、python 目录、其父目录（去重）。"""
    py = tmp_path / "env" / "python.exe"
    (py.parent / "Library" / "bin").mkdir(parents=True)
    (py.parent / "Scripts").mkdir(parents=True)
    py.write_text("", encoding="utf-8")
    dirs = asr_env._candidate_ffmpeg_dirs(str(py))
    assert dirs == [str(py.parent / "Library" / "bin"),
                    str(py.parent / "Scripts"), str(py.parent),
                    str(tmp_path)]
    assert asr_env._candidate_ffmpeg_dirs("") == []


def test_resolve_ffmpeg_scans_upstream_dirs(monkeypatch, tmp_path):
    """PATH 缺失时逐候选目录探测 ffmpeg.exe（Library/bin 先命中）。"""
    py = tmp_path / "env" / "python.exe"
    bin_dir = py.parent / "Library" / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "ffmpeg.exe").write_bytes(b"")
    py.write_text("", encoding="utf-8")
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: None)
    assert asr_env.resolve_ffmpeg(str(py)) == str(bin_dir / "ffmpeg.exe")


def test_probe_triage_ok_and_ffmpeg_missing(monkeypatch, tmp_path):
    """selfcheck 通过：ffmpeg 有→triage=ok；无→ffmpeg-missing。"""
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "p.exe"))
    (tmp_path / "p.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(asr_env, "ASR_CACHE_DIR", str(tmp_path / "c"))
    monkeypatch.setattr(asr_env, "ASR_MODELS_ROOT", str(tmp_path / "r"))
    monkeypatch.setattr(asr_env.subprocess, "run", lambda cmd, **kw: (
        SimpleNamespace(returncode=0, stdout=json.dumps(
            {"ok": True, "info": {"whisper_version": "3.1",
                                  "model_present": True}}), stderr="")))
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: str(tmp_path / "ff"))
    r = asr_env.probe_asr_env()
    assert r["triage"] == "ok" and r["ffmpeg"] is True
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: None)
    monkeypatch.setattr(asr_env, "_candidate_ffmpeg_dirs", lambda p: [])
    r2 = asr_env.probe_asr_env()
    assert r2["triage"] == "ffmpeg-missing" and r2["ffmpeg"] is False


def test_probe_triage_whisper_import_failed_and_stderr_tail(monkeypatch,
                                                            tmp_path):
    """whisper 导入失败三分类 + stderr tail 截断透出。"""
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "p.exe"))
    (tmp_path / "p.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: None)
    monkeypatch.setattr(asr_env.subprocess, "run", lambda cmd, **kw: (
        SimpleNamespace(returncode=1, stdout=json.dumps(
            {"ok": False,
             "error": "whisper 导入失败: No module named 'whisper'"},
             ensure_ascii=False),
            stderr="x" * 500)))
    r = asr_env.probe_asr_env()
    assert r["triage"] == "whisper-import-failed"
    assert len(r["stderr_tail"]) == 200 and r["stderr_tail"] == "x" * 200


def test_probe_triage_module_missing_and_python_unavailable(monkeypatch,
                                                            tmp_path):
    """其他模块缺失→module-missing；spawn 失败→python-unavailable。"""
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "p.exe"))
    (tmp_path / "p.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(asr_env.shutil, "which", lambda n: None)

    def _raise_oserror(cmd, **kw):
        raise OSError("spawn fail")

    monkeypatch.setattr(asr_env.subprocess, "run", _raise_oserror)
    r = asr_env.probe_asr_env()
    assert r["triage"] == "python-unavailable"

    monkeypatch.setattr(asr_env.subprocess, "run", lambda cmd, **kw: (
        SimpleNamespace(returncode=1, stdout=json.dumps(
            {"ok": False,
             "error": "ModuleNotFoundError: No module named 'numpy'"}),
            stderr="")))
    r2 = asr_env.probe_asr_env()
    assert r2["triage"] == "module-missing"


def test_probe_total_budget_stops_loop(monkeypatch, tmp_path):
    """探测总预算 90s：超时即止按已得结果返回（不再 spawn 子进程）。"""
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "p.exe"))
    (tmp_path / "p.exe").write_text("", encoding="utf-8")
    monkeypatch.setattr(asr_env, "_PROBE_TOTAL_BUDGET_S", -1.0)

    def _fail_run(cmd, **kw):
        raise AssertionError("超预算后不得再 spawn 子进程")

    monkeypatch.setattr(asr_env.subprocess, "run", _fail_run)
    r = asr_env.probe_asr_env()
    assert r["available"] is False


def _make_hf_repo(root, repo, files):
    snap = root / ("models--" + repo.replace("/", "--")) / "snapshots" / "abc"
    snap.mkdir(parents=True)
    for name, size in files.items():
        (snap / name).write_bytes(b"0" * size)
    return snap


def test_hf_hub_env_chain(monkeypatch, tmp_path):
    """HF hub cache 三级 env 链：HF_HUB_CACHE→HF_HOME/hub→默认家目录。"""
    import os
    monkeypatch.delenv("HF_HUB_CACHE", raising=False)
    monkeypatch.delenv("HF_HOME", raising=False)
    d1 = tmp_path / "a"
    d1.mkdir()
    monkeypatch.setenv("HF_HUB_CACHE", str(d1))
    assert asr_env.hf_hub_cache_dir() == d1
    monkeypatch.delenv("HF_HUB_CACHE")
    d2 = tmp_path / "b"
    d2.mkdir()
    monkeypatch.setenv("HF_HOME", str(d2))
    assert asr_env.hf_hub_cache_dir() == d2 / "hub"
    monkeypatch.delenv("HF_HOME")
    default = (Path(os.path.expanduser("~")) / ".cache" / "huggingface"
               / "hub")
    assert asr_env.hf_hub_cache_dir() == default


def test_hf_hub_enumeration_families_and_failsoft(monkeypatch, tmp_path):
    """文件族识别：ct2/transformers 收录，无关目录跳过；限时/缺目录 fail-soft。"""
    hub = tmp_path / "hub"
    _make_hf_repo(hub, "Org/CT2Model", {"model.bin": 10,
                                        "tokenizer.json": 2,
                                        "vocabulary.txt": 1})
    _make_hf_repo(hub, "Org/PTModel", {"model.safetensors": 20})
    _make_hf_repo(hub, "Org/Empty", {"README.md": 1})
    monkeypatch.setenv("HF_HUB_CACHE", str(hub))
    out = asr_env.enumerate_hf_hub_models(budget_s=5)
    got = {e["name"]: e for e in out}
    assert set(got) == {"Org/CT2Model", "Org/PTModel"}
    assert got["Org/CT2Model"]["format"] == "ct2"
    assert got["Org/CT2Model"]["bytes"] == 13
    assert got["Org/PTModel"]["format"] == "transformers"
    assert got["Org/PTModel"]["source"] == "hf-hub"
    assert got["Org/CT2Model"]["backend_state"] == "adapter-needed"
    # 限时归零→空（fail-soft）
    assert asr_env.enumerate_hf_hub_models(budget_s=0) == []
    # 目录不存在→空
    monkeypatch.setenv("HF_HUB_CACHE", str(tmp_path / "nope"))
    assert asr_env.enumerate_hf_hub_models() == []


def test_three_sources_merge_dedupe(monkeypatch, tmp_path):
    """三落位合并去重：同名校验序 whisper-cache>data-root；HF 单列。"""
    cache = tmp_path / "cache"
    root = tmp_path / "root"
    cache.mkdir()
    root.mkdir()
    (cache / "large-v2.pt").write_bytes(b"x" * asr_env._MODEL_MIN_BYTES)
    (root / "large-v2.pt").write_bytes(
        b"x" * (asr_env._MODEL_MIN_BYTES + 1))
    (root / "tiny.pt").write_bytes(b"x" * asr_env._MODEL_MIN_BYTES)
    monkeypatch.setattr(asr_env, "ASR_CACHE_DIR", str(cache))
    monkeypatch.setattr(asr_env, "ASR_MODELS_ROOT", str(root))
    cat = asr_env.enumerate_models_three_sources()
    by_name = {m["name"]: m for m in cat["whisper"]}
    assert set(by_name) == {"large-v2", "tiny"}
    assert by_name["large-v2"]["source"] == "whisper-cache"
    assert by_name["tiny"]["source"] == "data-root"


def test_probe_cache_roundtrip_and_ttl(tmp_path):
    """探测快照：落盘往返/超龄失效/损坏 fail-soft。"""
    path = str(tmp_path / "asr_probe_cache.json")
    assert asr_env.load_probe_cache(path) is None
    assert asr_env.save_probe_cache({"available": True}, path) is True
    assert asr_env.load_probe_cache(path) == {"available": True}
    assert asr_env.load_probe_cache(path, max_age_s=-1) is None   # 超龄
    Path(path).write_text("{broken", encoding="utf-8")
    assert asr_env.load_probe_cache(path) is None


def test_recommended_models_panel_metadata():
    """面板元数据钉：tier/desc/spec/backend/variants + verified 硬门槛。"""
    entries = {e["name"]: e for e in asr_env.ASR_RECOMMENDED_MODELS}
    tiers = {e["tier"] for e in asr_env.ASR_RECOMMENDED_MODELS
             if e["name"] != "qwen3-asr-1.7b"}
    assert tiers == {"fast", "balanced", "precise"}
    for e in entries.values():
        assert e["desc"] and e["spec"] and e["backend"]
        if e["backend"]["state"] != "planned":
            assert e["variants"], e["name"]
        assert 1 <= e["spec"]["speed"] <= 5
        assert 1 <= e["spec"]["precision"] <= 5
    # verified 硬门槛：五档 .pt（tiny/base/small/medium/large-v2）实测
    # 核验全通过（2026-10-05 官方源实下载 sha256 字节级比对）
    assert entries["whisper-tiny"]["verified"] is True
    assert entries["whisper-base"]["verified"] is True
    assert entries["whisper-large-v2"]["verified"] is True
    assert entries["whisper-small"]["verified"] is True
    assert entries["whisper-medium"]["verified"] is True
    assert entries["whisper-large-v2"]["spec"]["recommend"] is True
    assert entries["whisper-large-v2"]["tier"] == "precise"
    # 三态双门控：whisper 系 ready，qwen3 planned
    assert entries["whisper-tiny"]["backend"]["state"] == "ready"
    assert entries["qwen3-asr-1.7b"]["backend"]["state"] == "planned"
    assert entries["qwen3-asr-1.7b"]["backend"]["type"] == "qwen3-asr-hf"


def test_runner_direct_call_no_stdlib_hijack():
    """2.7.1 热修回归钉①（指定差分）：venv python（无 whisper）直调 runner
    脚本——预期失败="No module named 'whisper'"，而非 "No module named
    'subtransjav'"（secrets.py 劫持消除的可区分失败面）。"""
    import subprocess
    import sys as _sys
    runner = Path(asr_env.__file__).parent / "asr_runner.py"
    proc = subprocess.run(
        [_sys.executable, str(runner), "--selfcheck", "--model", "large-v2"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=120,
        cwd=str(Path(asr_env.__file__).parent))
    lines = [ln for ln in (proc.stdout or "").splitlines()
             if ln.strip().startswith("{")]
    assert lines, f"runner 无 JSON 输出: {proc.stdout!r} {proc.stderr!r}"
    payload = json.loads(lines[-1])
    assert payload["ok"] is False
    assert "No module named 'whisper'" in payload["error"]
    assert "subtransjav" not in payload["error"],         "secrets.py 仍劫持标准库导入链（sys.path 自清失效）"


def test_runner_direct_call_secrets_resolves_stdlib(tmp_path):
    """2.7.1 热修回归钉②（机制差分，本机实测复现布局）：脚本目录含与标准库
    同名 secrets.py + PYTHONPATH 注入 fake whisper（__version__=所引 secrets
    模块路径）——直调 runner 后 secrets 必须解析到标准库而非脚本目录影子
    （未修复时 sys.path[0]=脚本目录，影子先命中→version 指向影子文件）。"""
    import os
    import shutil
    import subprocess
    import sys as _sys
    real_runner = Path(asr_env.__file__).parent / "asr_runner.py"
    dir_a = tmp_path / "A"          # 脚本目录（含毒化 secrets 影子）
    dir_b = tmp_path / "B"          # fake whisper（经 PYTHONPATH 注入）
    dir_a.mkdir()
    dir_b.mkdir()
    shutil.copy(real_runner, dir_a / "asr_runner.py")
    (dir_a / "secrets.py").write_text(
        "from subtransjav import paths\n", encoding="utf-8")
    (dir_b / "whisper.py").write_text(
        "import secrets\n__version__ = secrets.__file__\n",
        encoding="utf-8")
    env = dict(os.environ, PYTHONPATH=str(dir_b))
    proc = subprocess.run(
        [_sys.executable, str(dir_a / "asr_runner.py"),
         "--selfcheck", "--model", "large-v2"],
        capture_output=True, encoding="utf-8", errors="replace", timeout=120,
        env=env, cwd=str(tmp_path))
    lines = [ln for ln in (proc.stdout or "").splitlines()
             if ln.strip().startswith("{")]
    assert lines, f"runner 无 JSON 输出: {proc.stdout!r} {proc.stderr!r}"
    payload = json.loads(lines[-1])
    assert payload["ok"] is True, payload
    ver = payload["info"]["whisper_version"]
    assert Path(ver).name == "secrets.py"
    assert dir_a not in Path(ver).resolve().parents,         f"secrets 仍被脚本目录影子劫持: {ver}"


def test_recommended_models_tiny_base_verified_pins():
    """tiny/base 官方资产元数据实测核验（2026-10-05 实下载 sha256 字节级
    比对通过；sha256=URL 段=whisper 上游 _MODELS pin，与 large-v2 同标准）。"""
    entries = {e["name"]: e for e in asr_env.ASR_RECOMMENDED_MODELS}
    t = entries["whisper-tiny"]
    assert t["bytes"] == 75572083
    assert t["sha256"] == ("65147644a518d12f04e32d6f3b26facc3f8dd46e5390"
                           "956a9424a650c0ce22b9")
    assert t["url"].endswith("/tiny.pt")
    assert t["sources"][0]["verified"] is True
    assert t["sources"][0]["sha256"] == t["sha256"]
    b = entries["whisper-base"]
    assert b["bytes"] == 145262807
    assert b["sha256"] == ("ed3a0b6b1c0edf879ad9b11b1af5a0e6ab5db9205f891f"
                           "668f8b0e6c6326e34e")


def test_recommended_models_small_medium_verified_pins():
    """small/medium 官方资产元数据实测核验（2026-10-05 实下载 sha256 字节级
    比对通过；sha256=URL 段=whisper 上游 _MODELS pin，与 tiny/base 同标准；
    至此五档 .pt 全核验）。"""
    entries = {e["name"]: e for e in asr_env.ASR_RECOMMENDED_MODELS}
    s = entries["whisper-small"]
    assert s["bytes"] == 483617219
    assert s["sha256"] == ("9ecf779972d90ba49c06d968637d720dd632c55bbf19d"
                           "441fb42bf17a411e794")
    assert s["url"].endswith("/small.pt")
    assert s["sources"][0]["verified"] is True
    assert s["sources"][0]["sha256"] == s["sha256"]
    m = entries["whisper-medium"]
    assert m["bytes"] == 1528008539
    assert m["sha256"] == ("345ae4da62f9b3d59415adc60127b97c714f32e89e93"
                           "6602e85993674d08dcb1")
    assert m["url"].endswith("/medium.pt")
    assert m["sources"][0]["verified"] is True
    assert m["sources"][0]["sha256"] == m["sha256"]


# ---------------------------------------------------------------------------
# 3.0 批3 3A：asr_runner 多段模式（C17+C13）与 batch_transcribe_clips
# ---------------------------------------------------------------------------

T1 = "00:00:05,000 --> 00:00:07,000"
T2 = "00:00:20,000 --> 00:00:22,000"


def _install_fake_whisper_multiclip(monkeypatch, responses):
    """多段模式 fake whisper：load_model 计数一次；transcribe 逐次弹
    responses 列表返回。返回 calls 状态 dict。"""
    import sys
    import types
    state = {"loads": 0}

    class _FakeModel:
        def transcribe(self, audio, **kw):
            state.setdefault("called", []).append(audio)
            return responses.pop(0) if responses else {
                "text": "", "segments": []}

    fake = types.ModuleType("whisper")
    fake.__version__ = "9.9"

    def _load_model(name, **kwargs):
        state["loads"] += 1
        return _FakeModel()

    fake.load_model = _load_model
    monkeypatch.setitem(sys.modules, "whisper", fake)
    return state


def test_runner_clips_json_contract(monkeypatch, tmp_path, capsys):
    """多段模式契约钉：单次 load_model→逐 clip 转写；stdout 单行 JSON
    带 ok/language/device/clips；段级透传置信三维（C13）；坏 clip 如实
    标 error 不静默。"""
    import subtransjav.refine.asr_runner as runner
    c1 = tmp_path / "c1.wav"
    c1.write_bytes(b"wav")
    state = _install_fake_whisper_multiclip(monkeypatch, [
        {"text": "テスト", "segments": [
            {"start": 0.0, "end": 1.0, "text": "テスト",
             "no_speech_prob": 0.02, "avg_logprob": -0.25,
             "compression_ratio": 1.2}]},
    ])
    manifest = [{"clip": str(c1), "timing": T1},
                {"clip": str(tmp_path / "missing.wav"), "timing": T2}]
    cj = tmp_path / "clips.json"
    cj.write_text(json.dumps(manifest), encoding="utf-8")
    rc = runner.main(["--clips-json", str(cj), "--model", "large-v2"])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and out["ok"] is True
    assert out["language"] == "ja"
    assert out["device"] in ("cuda", "cpu")
    assert state["loads"] == 1            # C17：单次装载
    assert len(out["clips"]) == 2
    seg = out["clips"][0]["segments"][0]
    assert seg["text"] == "テスト"
    assert seg["no_speech_prob"] == 0.02  # C13 置信透传
    assert seg["avg_logprob"] == -0.25
    assert seg["compression_ratio"] == 1.2
    assert out["clips"][1]["error"] \
        and "音频不存在" in out["clips"][1]["error"]
    assert out["clips"][1]["segments"] == []


def test_runner_clips_json_empty_no_model_load(monkeypatch, tmp_path,
                                               capsys):
    """空 clips 列表：不加载模型直接返回 device（调用侧零成本设备探测）。"""
    import subtransjav.refine.asr_runner as runner
    state = _install_fake_whisper_multiclip(monkeypatch, [])
    cj = tmp_path / "empty.json"
    cj.write_text("[]", encoding="utf-8")
    rc = runner.main(["--clips-json", str(cj)])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and out["ok"] is True and out["clips"] == []
    assert out["device"] in ("cuda", "cpu")
    assert state["loads"] == 0


def test_runner_audio_and_clips_json_mutually_exclusive(monkeypatch,
                                                        tmp_path, capsys):
    import subtransjav.refine.asr_runner as runner
    cj = tmp_path / "empty.json"
    cj.write_text("[]", encoding="utf-8")
    rc = runner.main(["--audio", str(tmp_path / "a.wav"),
                      "--clips-json", str(cj)])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 2 and "互斥" in out["error"]


def test_runner_single_mode_segments_have_confidence_keys(monkeypatch,
                                                          tmp_path,
                                                          capsys):
    """单 --audio 模式行为钉（向后兼容）：既有三键不变 + C13 追加置信
    键（fake whisper 无置信键时保守透传 None，不误判）。"""
    import subtransjav.refine.asr_runner as runner
    _install_fake_whisper_multiclip(monkeypatch, [
        {"text": "テスト",
         "segments": [{"start": 0.0, "end": 1.0, "text": "テスト"}]},
    ])
    audio = tmp_path / "c.wav"
    audio.write_bytes(b"wav")
    rc = runner.main(["--audio", str(audio)])
    out = json.loads(capsys.readouterr().out.strip())
    assert rc == 0 and out["ok"] is True and out["text"] == "テスト"
    seg = out["segments"][0]
    assert seg["start"] == 0.0 and seg["end"] == 1.0
    assert seg["text"] == "テスト"
    assert set(seg) == {"start", "end", "text", "no_speech_prob",
                        "avg_logprob", "compression_ratio"}
    assert seg["no_speech_prob"] is None


def _install_batch_env(monkeypatch, tmp_path, device_payload):
    """batch_transcribe_clips 测试环境：slice_clips 替身 + 数据根重定向
    + subprocess.run 替身（空清单=设备探测；非空=按清单回 payload）。"""
    from types import SimpleNamespace
    timings = [f"00:00:{i * 10:02d},000 --> 00:00:{i * 10 + 2:02d},000"
               for i in range(10)]
    clips = [{"path": str(tmp_path / f"c{i}.wav"), "timing": t}
             for i, t in enumerate(timings)]
    monkeypatch.setattr(asr_env, "slice_clips",
                        lambda media, ts, max_clips=20: {
                            "ok": True, "clips": clips, "error": "",
                            "skipped": 0})
    monkeypatch.setattr(asr_env, "paths",
                        SimpleNamespace(
                            data_subdir=lambda *p: str(
                                tmp_path.joinpath(*p)),
                            app_root=lambda: str(tmp_path)))
    monkeypatch.setenv("SUBTRANSJAV_ASR_PYTHON", str(tmp_path / "py.exe"))
    (tmp_path / "py.exe").write_text("", encoding="utf-8")
    spawns = {"probe": 0, "batch": []}

    def _fake_run(cmd, **kw):
        cj = cmd[cmd.index("--clips-json") + 1]
        items = json.loads(Path(cj).read_text(encoding="utf-8"))
        if not items:                        # 设备探测
            spawns["probe"] += 1
            payload = device_payload
            if callable(payload):
                payload = payload()
            return SimpleNamespace(returncode=0,
                                   stdout=json.dumps(payload), stderr="")
        spawns["batch"].append([it["timing"] for it in items])
        return SimpleNamespace(returncode=0, stdout=json.dumps({
            "ok": True, "language": "ja", "device": "cpu",
            "clips": [{"timing": it["timing"], "segments": [
                {"start": 0.0, "end": 1.0, "text": "テスト",
                 "no_speech_prob": 0.02, "avg_logprob": -0.25,
                 "compression_ratio": 1.2}],
                       "text_all": "テスト", "error": ""}
                      for it in items]}), stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    return timings, spawns


def test_batch_transcribe_clips_cpu_chunk_cap(monkeypatch, tmp_path):
    """无 GPU 保守上限：device=cpu 时 10 clip 分 2 次 spawn（cap=8）；
    probe 走空清单不计入批 spawn。"""
    timings, spawns = _install_batch_env(
        monkeypatch, tmp_path,
        {"ok": True, "language": "ja", "device": "cpu", "clips": []})
    results = asr_env.batch_transcribe_clips("m.mp4", timings)
    assert spawns["probe"] == 1
    assert len(spawns["batch"]) == 2
    assert all(len(c) <= asr_env._BATCH_CPU_CLIP_CAP
               for c in spawns["batch"])
    assert len(results) == 10
    assert all(r["ok"] and r["text"] == "テスト" for r in results)
    assert results[0]["segments"][0]["no_speech_prob"] == 0.02


def test_batch_transcribe_clips_cuda_single_spawn(monkeypatch, tmp_path):
    """GPU：单次 spawn 全量（单次 load_model 转 N 段，C17 主旨）。"""
    timings, spawns = _install_batch_env(
        monkeypatch, tmp_path,
        {"ok": True, "language": "ja", "device": "cuda", "clips": []})
    asr_env.batch_transcribe_clips("m.mp4", timings)
    assert len(spawns["batch"]) == 1
    assert len(spawns["batch"][0]) == 10


def test_batch_transcribe_clips_probe_failure_conservative_cpu(monkeypatch,
                                                               tmp_path):
    """设备探测失败 → 保守按 cpu 分批（方向安全，不激进）。"""
    timings, spawns = _install_batch_env(
        monkeypatch, tmp_path, {"ok": False, "error": "boom"})
    asr_env.batch_transcribe_clips("m.mp4", timings)
    assert len(spawns["batch"]) == 2


def test_batch_transcribe_clips_timeout_honest_failure(monkeypatch,
                                                       tmp_path):
    """批 spawn 超时 → 该批全部如实 ok=False（不静默）。"""
    import subprocess
    timings, spawns = _install_batch_env(
        monkeypatch, tmp_path,
        {"ok": True, "language": "ja", "device": "cuda", "clips": []})
    real_run = asr_env.subprocess.run

    def _run(cmd, **kw):
        cj = cmd[cmd.index("--clips-json") + 1]
        if json.loads(Path(cj).read_text(encoding="utf-8")):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=kw["timeout"])
        return real_run(cmd, **kw)

    monkeypatch.setattr(asr_env.subprocess, "run", _run)
    results = asr_env.batch_transcribe_clips("m.mp4", timings)
    assert len(results) == 10
    assert all(r["ok"] is False and r["error"] for r in results)
    del spawns


def test_batch_transcribe_clips_slice_failure_honest(monkeypatch, tmp_path):
    """切片全败 → 全部 timing 如实 ok=False。"""
    monkeypatch.setattr(asr_env, "slice_clips",
                        lambda media, ts, max_clips=20: {
                            "ok": False, "clips": [],
                            "error": "媒体文件不存在", "skipped": 2})
    results = asr_env.batch_transcribe_clips("m.mp4", [T1, T2])
    assert len(results) == 2
    assert all(r["ok"] is False and "切片失败" in r["error"]
               for r in results)
