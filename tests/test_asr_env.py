"""2.6.0 批 3（D2026-1002-04-批3）测试：ASR 探测/运行器协议/切片/下载/双钉。"""
import json
from pathlib import Path
from types import SimpleNamespace

from subtransjav.refine import asr_env
from subtransjav.refine import dict_manager as dm

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
    payload = json.dumps({"ok": True, "text": "テスト",
                          "segments": [{"start": 0, "end": 1,
                                        "text": "テスト"}]},
                         ensure_ascii=False)

    def _fake_run(cmd, **kw):
        assert "--model" in cmd and "large-v2" in cmd
        return SimpleNamespace(returncode=0, stdout=payload, stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
    r = asr_env.run_transcription(str(clip), asr_python=str(tmp_path / "p.exe"))
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

    def _fake_run(cmd, **kw):
        payload = json.dumps({"ok": True, "text": "转写内容" * 300},
                             ensure_ascii=False)
        return SimpleNamespace(returncode=0, stdout=payload, stderr="")

    monkeypatch.setattr(asr_env.subprocess, "run", _fake_run)
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
    from subtransjav.refine.config import TUNABLE_FIELD_TYPES, RefineConfig
    from subtransjav.refine.manifest import _CONFIG_FIELDS
    assert TUNABLE_FIELD_TYPES.get("media_crosscheck_enabled") is bool
    assert "media_crosscheck_enabled" not in _CONFIG_FIELDS
    assert "asr_model" not in _CONFIG_FIELDS
    assert "asr_python" not in _CONFIG_FIELDS
    assert RefineConfig(inputs=["a.srt"]).media_crosscheck_enabled is True


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
# 下载件（dict_manager 扩展）：sha256 pin + 落点守卫 + 进度快照
# ---------------------------------------------------------------------------

def test_asr_download_unknown_kind():
    r = dm.download_asr_model("no-such")
    assert r["success"] is False and "未知" in r["error"]


def test_asr_download_cached_short_circuit(monkeypatch, tmp_path):
    entry = dm._ASR_DOWNLOADS["whisper-large-v2"]
    body = b"large-v2-content"
    import hashlib
    sha = hashlib.sha256(body).hexdigest()
    monkeypatch.setattr(dm, "_ASR_MODELS_ROOT", str(tmp_path))
    monkeypatch.setattr(dm, "_ASR_DOWNLOADS", {
        "whisper-large-v2": {**entry, "sha256": sha, "bytes": len(body)}})
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None:
                        Path(dest).write_bytes(body))
    dest = Path(dm._ASR_MODELS_ROOT) / "large-v2.pt"   # monkeypatch 后取根（隔离真实库）
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    r = dm.download_asr_model("whisper-large-v2")
    assert r["success"] is True and r["cached"] is True
    p = dm.asr_download_progress()
    assert p["running"] is False and p["phase"] == "done"


def test_asr_download_full_flow_with_fake_http(monkeypatch, tmp_path):
    entry = dm._ASR_DOWNLOADS["whisper-large-v2"]
    body = b"downloaded-model-bytes"
    import hashlib
    sha = hashlib.sha256(body).hexdigest()

    def _fake_http(url, dest, progress=None):
        Path(dest).write_bytes(body)
        if progress:
            progress(len(body), len(body))

    monkeypatch.setattr(dm, "_ASR_MODELS_ROOT", str(tmp_path))
    monkeypatch.setattr(dm, "_ASR_DOWNLOADS", {
        "whisper-large-v2": {**entry, "sha256": sha, "bytes": len(body)}})
    monkeypatch.setattr(dm, "_http_get", _fake_http)
    r = dm.download_asr_model("whisper-large-v2")
    assert r["success"] is True and r["cached"] is False
    assert Path(r["path"]).read_bytes() == body
    p = dm.asr_download_progress()
    assert p["phase"] == "done" and p["downloaded"] == len(body)


def test_asr_download_sha_mismatch_deletes(monkeypatch, tmp_path):
    entry = dm._ASR_DOWNLOADS["whisper-large-v2"]
    monkeypatch.setattr(dm, "_ASR_MODELS_ROOT", str(tmp_path))
    monkeypatch.setattr(dm, "_ASR_DOWNLOADS", {
        "whisper-large-v2": {**entry}})
    monkeypatch.setattr(dm, "_http_get",
                        lambda url, dest, progress=None:
                        Path(dest).write_bytes(b"tampered"))
    monkeypatch.setattr(dm, "_sha256_stream",
                        lambda path: "0" * 64)
    r = dm.download_asr_model("whisper-large-v2")
    assert r["success"] is False and "SHA256" in r["error"]
    assert not (tmp_path / "large-v2.pt").exists()


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
