# 3.2.0 CT2 骨架批钉（D2026-1028-03）：ct2 后端契约+运行时模块纯函数面。
# 全程零真实模型/零网络；ct2 转写链用注入 fake 模块走全函数。
import json
import pathlib
import sys
import types

from subtransjav.refine import asr_runner, asr_runtime


class TestEngineRouting:
    """缺省与互斥：不带 --engine 时一切走 whisper 老路（零行为变化）。"""

    def test_default_engine_is_whisper_path(self, capsys):
        # 无 --engine、无 --audio → whisper 路径的参数校验报错（不触 whisper 导入）
        rc = asr_runner.main([])
        assert rc == 2
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert out["ok"] is False and "音频不存在" in out["error"]

    def test_media_only_rejected_on_whisper(self, capsys):
        rc = asr_runner.main(["--media", "x.mp4"])
        assert rc == 2
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "仅在 --engine ct2" in out["error"]

    def test_ct2_requires_srt_out(self, tmp_path, capsys):
        media = tmp_path / "a.wav"
        media.write_bytes(b"RIFF")
        rc = asr_runner.main(["--engine", "ct2", "--media", str(media)])
        assert rc == 2
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "--srt-out" in out["error"]

    def test_ct2_mutex_with_audio(self, tmp_path, capsys):
        rc = asr_runner.main(["--engine", "ct2", "--media", "x", "--srt-out",
                              "o.srt", "--audio", "y"])
        assert rc == 2
        out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert "互斥" in out["error"]

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
    def __init__(self, s, e, t, words):
        self.start, self.end, self.text, self.words = s, e, t, words


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
        assert out["ok"] is True and out["segments"] == 2
        text = srt_out.read_text(encoding="utf-8")
        assert "00:00:00,500 --> 00:00:02,500" in text
        assert "こんにちは" in text
        sidecar = json.loads(
            pathlib.Path(str(srt_out) + ".words.json").read_text(encoding="utf-8"))
        assert sidecar["schema"] == "subtransjav.ct2.words/1"
        assert sidecar["segments"][0]["words"][0]["word"] == "こんにちは"


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
        assert st["zip_published"] is False
        assert st["pinned_deps"] == ["faster-whisper==1.2.1", "ctranslate2==4.8.4",
                                     "av==13.1.0"]
        assert st["models"][0]["verified"] is False

    def test_install_zip_unpublished_honest_error(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
        rc = asr_runtime.install("zip")
        assert rc == 3
        assert "尚未发布" in capsys.readouterr().out

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
