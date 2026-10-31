# 3.2.0 CT2 骨架批钉（D2026-1028-03）：ct2 后端契约+运行时模块纯函数面。
# 全程零真实模型/零网络；ct2 转写链用注入 fake 模块走全函数。
import argparse
import json
import os
import pathlib
import sys
import threading
import time
import types
from types import SimpleNamespace

import pytest

from subtransjav.refine import asr_env, asr_runner, asr_runtime


class TestEngineRouting:
    """缺省与参数面：3.2 退役批起 ct2 唯一引擎（--engine 旗标保留=命令
    契约稳定；legacy whisper 形态钉随硬删移除）。"""

    def test_default_engine_is_ct2_requires_media(self, capsys):
        # 无 --media → 参数校验报错（不触 faster_whisper 导入）
        rc = asr_runner.main([])
        assert rc == 2
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["ok"] is False and "--media" in out["error"]

    def test_ct2_requires_srt_out(self, tmp_path, capsys):
        media = tmp_path / "a.wav"
        media.write_bytes(b"RIFF")
        rc = asr_runner.main(["--engine", "ct2", "--media", str(media)])
        assert rc == 2
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "--srt-out" in out["error"]

    def test_ct2_missing_media(self, tmp_path, capsys):
        rc = asr_runner.main(["--engine", "ct2", "--media", str(tmp_path / "gone.wav"),
                              "--srt-out", str(tmp_path / "o.srt"),
                              "--model-dir", str(tmp_path)])
        assert rc == 2
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "媒体不存在" in out["error"]

    def test_ct2_invalid_model_dir(self, tmp_path, capsys):
        media = tmp_path / "a.wav"
        media.write_bytes(b"RIFF")
        rc = asr_runner.main(["--engine", "ct2", "--media", str(media),
                              "--srt-out", str(tmp_path / "o.srt"),
                              "--model-dir", str(tmp_path / "nomodel")])
        assert rc == 2
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "模型目录无效" in out["error"]

    def test_ct2_without_runtime_import_fail(self, tmp_path, capsys, monkeypatch):
        # .venv 无 faster_whisper → 人话指引安装链（rc=1）
        monkeypatch.delitem(sys.modules, "faster_whisper", raising=False)
        media = tmp_path / "a.wav"
        media.write_bytes(b"RIFF")
        mdir = tmp_path / "m"
        mdir.mkdir()
        rc = asr_runner.main(["--engine", "ct2", "--media", str(media),
                              "--srt-out", str(tmp_path / "o.srt"),
                              "--model-dir", str(mdir)])
        assert rc == 1
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "asr_runtime install" in out["error"]


class _FakeWord:
    def __init__(self, s, e, w, p):
        self.start, self.end, self.word, self.probability = s, e, w, p


class _FakeSeg:
    def __init__(self, s, e, t, words, nsp=0.1, alp=-0.5, cr=1.2):
        self.start, self.end, self.text, self.words = s, e, t, words
        self.no_speech_prob = nsp
        self.avg_logprob = alp
        self.compression_ratio = cr


class _FakeInfo:
    language = "ja"
    duration = 6.5


class _FakeModel:
    def __init__(self, model_dir, device=None, compute_type=None):
        assert compute_type == "int8"
        assert str(model_dir).endswith("m")

    def transcribe(self, media, language=None, beam_size=None, vad_filter=None,
                   condition_on_previous_text=None, word_timestamps=None):
        assert word_timestamps is True          # 断行器依赖恒开
        assert vad_filter is True and condition_on_previous_text is False
        assert beam_size == 5
        segs = [
            _FakeSeg(0.5, 2.5, " こんにちは ", [_FakeWord(0.5, 1.2, "こんにちは", 0.9)]),
            _FakeSeg(3.0, 4.0, "またね", [_FakeWord(3.0, 3.8, "またね", 0.8)]),
        ]
        return iter(segs), _FakeInfo()


class TestCt2E2EWithFake:
    def test_full_function_via_fake_module(self, tmp_path, capsys, monkeypatch):
        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = _FakeModel
        monkeypatch.setitem(sys.modules, "faster_whisper", fake)
        media = tmp_path / "a.wav"
        media.write_bytes(b"RIFF")
        mdir = tmp_path / "m"
        mdir.mkdir()
        srt_out = tmp_path / "out" / "a.srt"
        rc = asr_runner.main(["--engine", "ct2", "--media", str(media),
                              "--srt-out", str(srt_out), "--model-dir", str(mdir)])
        assert rc == 0
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["ok"] is True
        # 批1 置信透传：stdout segments=完整段数组（含三维置信键）
        assert isinstance(out["segments"], list) and len(out["segments"]) == 2
        assert out["segments"][0]["no_speech_prob"] == 0.1
        assert out["segments"][1]["avg_logprob"] == -0.5
        text = srt_out.read_text(encoding="utf-8")
        assert "00:00:00,500 --> 00:00:02,500" in text
        assert "こんにちは" in text
        sidecar = json.loads(
            pathlib.Path(str(srt_out) + ".words.json").read_text(encoding="utf-8"))
        assert sidecar["schema"] == "subtransjav.ct2.words/1"
        assert sidecar["segments"][0]["words"][0]["word"] == "こんにちは"


class _FakeDualModel:
    """双 pass fake：按 vad_filter 区分档位（pass1 VAD 开 / pass2 召回档关）。"""

    calls: list = []

    def __init__(self, model_dir, device=None, compute_type=None):
        assert compute_type == "int8"
        assert str(model_dir).endswith("m")
        _FakeDualModel.calls = []

    def transcribe(self, media, language=None, beam_size=None, vad_filter=None,
                   condition_on_previous_text=None, word_timestamps=None):
        assert word_timestamps is True          # 断行器依赖恒开
        _FakeDualModel.calls.append({
            "beam_size": beam_size, "vad_filter": vad_filter,
            "condition_on_previous_text": condition_on_previous_text})
        if vad_filter:                          # pass1 精准档
            segs = [
                _FakeSeg(0.5, 2.5, " こんにちは ",
                         [_FakeWord(0.5, 2.5, "こんにちは", 0.9)]),
                _FakeSeg(4.0, 5.0, "またね",
                         [_FakeWord(4.0, 5.0, "またね", 0.8)]),
            ]
        else:                                   # pass2 召回档（vad 关/beam 8）
            segs = [
                _FakeSeg(2.8, 3.6, "そうですね",
                         [_FakeWord(2.8, 3.6, "そうですね", 0.7)]),
                _FakeSeg(1.0, 1.5, "重複",
                         [_FakeWord(1.0, 1.5, "重複", 0.6)]),
                _FakeSeg(5.2, 6.0, "末尾",
                         [_FakeWord(5.2, 6.0, "末尾", 0.6)]),
            ]
        return iter(segs), _FakeInfo()


class TestCt2DualPass:
    """--passes 2 双 pass 覆盖合并（3.2.0 件A，D2026-1029-02 拍板①）。"""

    def test_passes2_dual_products_and_recall_profile(self, tmp_path, capsys,
                                                      monkeypatch):
        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = _FakeDualModel
        monkeypatch.setitem(sys.modules, "faster_whisper", fake)
        media = tmp_path / "a.wav"
        media.write_bytes(b"RIFF")
        mdir = tmp_path / "m"
        mdir.mkdir()
        srt_out = tmp_path / "out" / "a.srt"
        rc = asr_runner.main(["--engine", "ct2", "--media", str(media),
                              "--srt-out", str(srt_out),
                              "--model-dir", str(mdir), "--passes", "2"])
        assert rc == 0
        # 恰调两次：pass1 精准档原样 / pass2 召回档预注册常量
        assert _FakeDualModel.calls == [
            {"beam_size": 5, "vad_filter": True,
             "condition_on_previous_text": False},
            {"beam_size": 8, "vad_filter": False,
             "condition_on_previous_text": False},
        ]
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["ok"] is True and out["passes"] == 2
        # 主输出=覆盖合并：空洞补全 2 段，重叠候选弃置
        assert [s["text"].strip() for s in out["segments"]] == \
            ["こんにちは", "そうですね", "またね", "末尾"]
        text = srt_out.read_text(encoding="utf-8")
        assert "そうですね" in text and "重複" not in text
        # 产物面：pass1/pass2 中间件＋各自词级 sidecar＋dualpass sidecar
        for name in ("a.pass1.srt", "a.pass2.srt",
                     "a.pass1.srt.words.json", "a.pass2.srt.words.json",
                     "a.srt.words.json", "a.srt.dualpass.json"):
            assert (srt_out.parent / name).is_file(), name
        dual = json.loads(
            (srt_out.parent / "a.srt.dualpass.json").read_text(encoding="utf-8"))
        assert dual["schema"] == "subtransjav.ct2.dualpass/1"
        assert dual["gap_threshold_s"] == 1.0
        assert dual["pass1"]["params"]["beam_size"] == 5
        assert dual["pass2"]["params"] == {
            "beam_size": 8, "vad_filter": False,
            "condition_on_previous_text": False, "word_timestamps": True}
        assert len(dual["pass1"]["segments"]) == 2
        assert len(dual["pass2"]["segments"]) == 3
        assert len(dual["adopted"]) == 2

    def test_default_single_pass_zero_change(self, tmp_path, capsys,
                                             monkeypatch):
        """单 pass 零变化钉：不传 --passes → transcribe 恰一次、无新产物面。"""
        calls = []

        class _CountingModel(_FakeModel):
            def __init__(self, *a, **k):
                calls.append(1)
                super().__init__(*a, **k)

        fake = types.ModuleType("faster_whisper")
        fake.WhisperModel = _CountingModel
        monkeypatch.setitem(sys.modules, "faster_whisper", fake)
        media = tmp_path / "a.wav"
        media.write_bytes(b"RIFF")
        mdir = tmp_path / "m"
        mdir.mkdir()
        srt_out = tmp_path / "out" / "a.srt"
        rc = asr_runner.main(["--engine", "ct2", "--media", str(media),
                              "--srt-out", str(srt_out),
                              "--model-dir", str(mdir)])
        assert rc == 0
        assert len(calls) == 1
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["ok"] is True and "passes" not in out
        assert (srt_out.parent / "a.srt.words.json").is_file()
        assert not (srt_out.parent / "a.pass1.srt").exists()
        assert not (srt_out.parent / "a.pass2.srt").exists()
        assert not (srt_out.parent / "a.srt.dualpass.json").exists()


class TestSegmentsToSrt:
    def test_format_and_clamp(self):
        segs = [{"start": -0.2, "end": 1.0, "text": " あ "},
                {"start": 3661.5, "end": 3662.0, "text": "い"}]
        t = asr_runner._segments_to_srt(segs)
        assert t.splitlines()[1] == "00:00:00,000 --> 00:00:01,000"
        assert "01:01:01,500 --> 01:01:02,000" in t
        assert "あ" in t and "い" in t


class TestAsrRuntime:
    def test_status_fresh_state(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        st = asr_runtime.provider_status()
        assert st["installed"] is False
        assert st["selfcheck"] == "fail"
        assert st["zip_published"] is True      # pin 已填（构建实录）
        assert st["pinned_deps"] == ["faster-whisper==1.2.1", "ctranslate2==4.8.4",
                                     "av==13.1.0"]
        assert st["models"][0]["verified"] is True    # 2026-10-29 三门核验后翻转

    def test_install_zip_download_failure_honest(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))

        def boom(*a, **k):
            raise RuntimeError("sha256 不符（模拟）")

        monkeypatch.setattr(asr_runtime, "_guarded_download", boom)
        rc = asr_runtime.install("zip")
        assert rc == 1
        assert "运行时安装失败" in capsys.readouterr().out

    def test_install_zip_happy_path_mocked(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        monkeypatch.setattr(asr_runtime, "_guarded_download",
                            lambda *a, **k: None)
        monkeypatch.setattr(asr_runtime, "_verify_zip_layout", lambda p: None)
        monkeypatch.setattr(asr_runtime, "_safe_extract_zip",
                            lambda *a, **k: None)
        monkeypatch.setattr(asr_runtime, "_write_manifest_after_extract",
                            lambda root, sha: {"zip_sha256": sha})
        monkeypatch.setattr(asr_runtime, "selfcheck",
                            lambda: (True, "ct2-runtime-selfcheck OK"))
        rc = asr_runtime.install("zip")
        assert rc == 0
        out = capsys.readouterr().out
        assert "sha256 核验通过" in out and "自检" in out

    def test_download_model_verified_gate(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        # verified 现已翻转 True（三门核验过）；门的关断语义仍须钉住——
        # 强制 False 回放关断路径
        monkeypatch.setitem(asr_runtime.CT2_MODELS[0], "verified", False)
        rc = asr_runtime.download_model("large-v2")
        assert rc == 3
        assert "verified=False" in capsys.readouterr().out

    def test_download_model_flattens_single_inner_dir(self, tmp_path,
                                                      monkeypatch):
        """回归钉（d1028-35 重传勘因）：镜像模型件带单内层目录
        faster-whisper-large-v2/——解包后必须压平归位到 dest 根
        （model.bin 落位契约=resolve_ct2_model_dir 消费面），否则
        verified 门生产核验永不可过。"""
        import io
        import zipfile as zf

        buf = io.BytesIO()
        with zf.ZipFile(buf, "w") as z:
            z.writestr("faster-whisper-large-v2/model.bin", b"MBIN")
            z.writestr("faster-whisper-large-v2/config.json", b"{}")

        def fake_download(url, dest, sha, size, progress=None):
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            pathlib.Path(dest).write_bytes(buf.getvalue())

        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        monkeypatch.setattr(asr_runtime, "_guarded_download", fake_download)
        monkeypatch.setitem(asr_runtime.CT2_MODELS[0], "verified", True)
        rc = asr_runtime.download_model("large-v2")
        assert rc == 0
        dest = tmp_path / "models" / "ct2" / "large-v2"
        assert (dest / "model.bin").read_bytes() == b"MBIN"
        assert not (dest / "faster-whisper-large-v2").exists()

    def test_install_venv_rejected_when_frozen(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        monkeypatch.setattr(sys, "frozen", True, raising=False)
        rc = asr_runtime.install("venv")
        assert rc == 3
        assert "frozen" in capsys.readouterr().out

    def test_resolve_model_dir(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        assert asr_runtime.resolve_ct2_model_dir("large-v2") == ""
        mdir = tmp_path / "models" / "ct2" / "large-v2"
        mdir.mkdir(parents=True)
        (mdir / "model.bin").write_bytes(b"x")
        got = asr_runtime.resolve_ct2_model_dir("large-v2")
        assert got == str(mdir)
        # 显式 model_dir 优先且校验存在性
        assert asr_runtime.resolve_ct2_model_dir("x", str(mdir)) == str(mdir)
        assert asr_runtime.resolve_ct2_model_dir("x", str(tmp_path / "nope")) == ""

    def test_runner_command_shape(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        cmd = asr_runtime.ct2_runner_command("m.mp4", "o.srt", model_dir=str(tmp_path))
        assert cmd[0] == asr_runtime.runtime_python()
        assert "--engine" in cmd and "ct2" in cmd
        assert "--no-vad-filter" not in cmd and "--condition-previous" not in cmd
        cmd2 = asr_runtime.ct2_runner_command("m.mp4", "o.srt", model_dir=str(tmp_path),
                                              vad_filter=False, condition_previous=True,
                                              beam_size=3)
        assert "--no-vad-filter" in cmd2 and "--condition-previous" in cmd2
        assert cmd2[cmd2.index("--beam-size") + 1] == "3"

    def test_cli_status(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        rc = asr_runtime.main(["status"])
        assert rc == 0
        st = json.loads(capsys.readouterr().out)
        assert st["installed"] is False


class TestDecouple:
    """退役批（D2026-1029-01）源码面钉：legacy whisper 链无残留+ct2 唯一分派。"""

    def test_no_whisper_backend_residual(self):
        import inspect
        src = inspect.getsource(asr_env)
        # legacy whisper 链符号随硬删清零（退役批源码面钉，ct2 口径；
        # def 级锚防 ct2_runner_command/resolve_ct2_model_dir 活符号误伤）
        for sym in ("def _candidate_pythons", "def _runner_command",
                    "def _spawn_runner", "def probe_asr_env",
                    "ASR_RECOMMENDED_MODELS: list", "def resolve_model_dir",
                    "def enumerate_models_three_sources"):
            assert sym not in src, f"legacy whisper 链残留: {sym}"

    def test_run_transcription_dispatches_ct2(self, tmp_path, monkeypatch):
        # ct2 就绪 → ct2 路径（monkeypatch _run_transcription_ct2 捕获调用）
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        monkeypatch.setattr(asr_env, "_ct2_ready", lambda: True)
        seen = {}

        def fake_ct2(clip, language, timeout=300):
            seen["clip"] = clip
            return {"ok": True, "text": "CT2OUT", "segments": []}

        monkeypatch.setattr(asr_env, "_run_transcription_ct2", fake_ct2)
        r = asr_env.run_transcription("clip.wav")
        assert r["ok"] is True and r["text"] == "CT2OUT"
        assert seen["clip"] == "clip.wav"

    def test_run_transcription_engine_absent_guides_install(self, tmp_path,
                                                            monkeypatch):
        # ct2 未装：唯一错误出口＝安装导向人话（退役批对冲钉，「唯一引擎，
        # 首次使用需安装」口径；不再有 legacy whisper 回落）
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        r = asr_env.run_transcription("clip.wav")
        assert r["ok"] is False and "唯一引擎" in r["error"]
        assert "asr_runtime install" in r["error"]

    def test_probe_includes_ct2_section(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        st = asr_env._ct2_status()
        assert st["installed"] is False and st["model_present"] is False
        assert st["model"] == "large-v2"


class TestConfidencePassthrough:
    """ct2 链三维置信键透传（D2026-1029-01 批1，HRO 修复）。

    faster_whisper segment 原生 no_speech_prob/avg_logprob/compression_ratio
    此前在 runner 段构建与 SRT 回读两处被丢弃，漏听二级三维置信门静默失效
    （missed_insert C22 依赖）。钉①＝batch ct2 路径 mock runner stdout 带
    三键→返回 segments 含三键（现行实现红）；钉②＝classify 收 ct2 形态段
    （nsp>0.6）→grade=low（门恢复生效，test_missed_insert 侧）。"""

    _T = "00:00:01,000 --> 00:00:03,000"

    def test_batch_ct2_path_passes_confidence_keys(self, tmp_path,
                                                   monkeypatch):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        monkeypatch.setattr(asr_env, "_ct2_ready", lambda: True)
        monkeypatch.setattr(
            asr_env, "slice_clips",
            lambda media, timings, max_clips=20: {
                "ok": True,
                "clips": [{"path": "c1.wav", "timing": self._T}],
                "error": "", "skipped": 0})
        monkeypatch.setattr(asr_runtime, "resolve_ct2_model_dir",
                            lambda *a, **k: str(tmp_path / "m"))
        payload = json.dumps({"ok": True, "segments": [
            {"start": 1.0, "end": 3.0, "text": " あ ",
             "no_speech_prob": 0.8, "avg_logprob": -0.2,
             "compression_ratio": 1.5}]}, ensure_ascii=False)
        monkeypatch.setattr(
            asr_env.subprocess, "run",
            lambda *a, **k: SimpleNamespace(stdout=payload + "\n",
                                            stderr="", returncode=0))
        r = asr_env.batch_transcribe_clips("media.mp4", [self._T])
        assert r[0]["ok"] is True
        seg = (r[0].get("segments") or [{}])[0]
        assert seg.get("no_speech_prob") == 0.8
        assert seg.get("avg_logprob") == -0.2
        assert seg.get("compression_ratio") == 1.5


    def test_batch_ct2_only_no_whisper_fallback(self, tmp_path, monkeypatch):
        """退役批对冲钉：批量链 ct2 唯一——运行时/模型未落位时逐 timing
        如实报错（不再有 legacy whisper 回落分支）。"""
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        monkeypatch.setattr(
            asr_env, "slice_clips",
            lambda media, timings, max_clips=20: {
                "ok": True,
                "clips": [{"path": "c1.wav", "timing": self._T}],
                "error": "", "skipped": 0})
        r = asr_env.batch_transcribe_clips("media.mp4", [self._T])
        assert r[0]["ok"] is False
        assert "模型未落位" in r[0]["error"]

    def test_batch_slice_failure_honest(self, tmp_path, monkeypatch):
        """切片整段失败 → 全 timing 如实标记（不静默，C17 口径）。"""
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        monkeypatch.setattr(
            asr_env, "slice_clips",
            lambda media, timings, max_clips=20: {
                "ok": False, "clips": [], "error": "ffmpeg 不可用",
                "skipped": 0})
        r = asr_env.batch_transcribe_clips("media.mp4", [self._T])
        assert r[0]["ok"] is False and "切片失败" in r[0]["error"]


class TestAsyncOps:
    def setup_method(self):
        # 全局操作态隔离（线程异步测试不串场）
        asr_runtime._set_op("idle", "", "")

    def test_install_async_lifecycle(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        monkeypatch.setattr(asr_runtime, "install", lambda provider="auto": 0)
        r = asr_runtime.start_install("venv")
        assert r["started"] is True
        deadline = time.time() + 5
        while time.time() < deadline:
            snap = asr_runtime.operation_progress()
            if snap["phase"] in ("done", "failed"):
                break
            time.sleep(0.05)
        snap = asr_runtime.operation_progress()
        assert snap["phase"] == "done" and snap["rc"] == 0
        r2 = asr_runtime.start_install("venv")
        assert r2["started"] in (True, False)   # idle 后可重入

    def test_double_start_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        started = threading.Event()

        def slow_install(provider="auto"):
            started.set()
            time.sleep(0.5)
            return 0

        monkeypatch.setattr(asr_runtime, "install", slow_install)
        r1 = asr_runtime.start_install("venv")
        assert r1["started"] is True
        started.wait(2)
        r2 = asr_runtime.start_install("venv")
        assert r2["started"] is False and "在跑" in r2["reason"]

    def test_model_download_async_gate(self, tmp_path, monkeypatch):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        # verified 已翻转 True；门的关断语义回放须强制 False（防真实 3GB 下载）
        monkeypatch.setitem(asr_runtime.CT2_MODELS[0], "verified", False)
        r = asr_runtime.start_model_download("large-v2")
        assert r["started"] is True
        deadline = time.time() + 5
        while time.time() < deadline:
            snap = asr_runtime.operation_progress()
            if snap["phase"] in ("done", "failed"):
                break
            time.sleep(0.05)
        snap = asr_runtime.operation_progress()
        assert snap["phase"] == "failed" and snap["rc"] == 3   # verified 门


class TestRunnerParserExactMatch:
    """runner parser 精确匹配钉（D2026-1031-04 ⑦②）：cmd 契约里的
    --model 元素此前靠 argparse 前缀缩写被收进 --model-dir（后值覆盖
    冲正才可用）；收敛后 --model 是真实选项、缩写一律拒绝。"""

    @staticmethod
    def _runner_parser(monkeypatch):
        """捕获 main() 内联构造的 runner parser（不改源面结构）。"""
        captured = []
        real_parse_args = argparse.ArgumentParser.parse_args

        def _capture(self, args=None, namespace=None):
            captured.append(self)
            return real_parse_args(self, args, namespace)

        with monkeypatch.context() as m:
            m.setattr(argparse.ArgumentParser, "parse_args", _capture)
            rc = asr_runner.main([])
        assert rc == 2, "main([]) 应先构造 parser 再报缺 --media"
        assert captured, "未捕获到 runner parser 构造"
        return captured[0]

    def test_model_option_not_swallowed_by_model_dir(self, monkeypatch):
        # 钉1：--model 精确命中自身，不再被 --model-dir 前缀缩写吞掉
        parser = self._runner_parser(monkeypatch)
        args = parser.parse_args(["--model", "large-v2", "--model-dir", "/x"])
        assert args.model_dir == "/x"
        assert args.model == "large-v2"

    def test_abbreviation_rejected(self, monkeypatch):
        # 钉2：allow_abbrev=False 生效——前缀缩写报 argparse error（rc=2）
        parser = self._runner_parser(monkeypatch)
        with pytest.raises(SystemExit) as ei:
            parser.parse_args(["--mo", "x"])
        assert ei.value.code == 2

    def test_runner_command_keeps_model_element(self, tmp_path, monkeypatch):
        # 钉3：ct2_runner_command 契约保活——--model 元素原样保留且
        # 与 --model-dir 各自独立成对（cmd 构造面零变化）
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        cmd = asr_runtime.ct2_runner_command("m.mp4", "o.srt",
                                             model_dir=str(tmp_path))
        assert cmd[cmd.index("--model") + 1] == "large-v2"
        assert cmd[cmd.index("--model-dir") + 1] == str(tmp_path)
