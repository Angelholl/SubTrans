"""CT2 运行时布局契约测试（d1028-36，D2026-1028-04 拍板 B 案升级版）。

防布局再漂移：认证只绑定 d1028-32 §4 定稿单一布局
（python/ + site-packages/ + runtime.json + selfcheck.py）；manifest
（runtime.json）为生产认证路径，fallback 探测（Scripts/、python/、根）
仅诊断非认证；embed 平铺等错布局 install 必须失败且诊断含「布局」。
verified 初值本卡不翻转（门禁翻转属主验收动作）。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import zipfile
from pathlib import Path

import pytest

from subtransjav.refine import asr_runtime

# ---------------------------------------------------------------- fixtures

def _build_zip(path: Path, members: dict[str, bytes]) -> str:
    """构造 fixture zip，返回 sha256（供 pin monkeypatch 对齐真校验）。"""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, data in members.items():
            z.writestr(name, data)
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_bytes() -> bytes:
    return json.dumps({
        "layout_version": 1,
        "python_exe": "python/python.exe",
        "site_packages": "site-packages",
    }).encode("utf-8")


def _finalized_members() -> dict[str, bytes]:
    """定稿布局小体积假体：入口/关键依赖标记/manifest/selfcheck 脚本。"""
    members: dict[str, bytes] = {
        "runtime.json": _manifest_bytes(),
        "selfcheck.py": b"print('ct2-runtime-selfcheck OK')\n",
        "python/python.exe": b"stub-python",
    }
    for pkg in ("faster_whisper", "ctranslate2", "av"):
        members["site-packages/" + pkg + "/__init__.py"] = b""
    return members


def _flat_members() -> dict[str, bytes]:
    """embed 平铺错布局（已上传件形态：python.exe 在根、Lib/site-packages）。"""
    members: dict[str, bytes] = {"python.exe": b"stub-python",
                                 "LICENSE.txt": b"stub"}
    for pkg in ("faster_whisper", "ctranslate2", "av"):
        members["Lib/site-packages/" + pkg + "/__init__.py"] = b""
    return members


def _pin_fixture_zip(monkeypatch, zip_path: Path, members: dict[str, bytes]) -> str:
    """pin 三件套对齐 fixture zip；_http_get 换本地复制（sha256/尺寸真校验）。"""
    sha = _build_zip(zip_path, members)
    monkeypatch.setattr(asr_runtime, "RUNTIME_ZIP_URL",
                        "https://hf-mirror.com/fake/subtrans-ct2-runtime-9.9.9-win64.zip")
    monkeypatch.setattr(asr_runtime, "RUNTIME_ZIP_SHA256", sha)
    monkeypatch.setattr(asr_runtime, "RUNTIME_ZIP_BYTES", zip_path.stat().st_size)

    def _fake_http_get(url, dest, progress=None, stop_event=None):
        shutil.copyfile(str(zip_path), dest)

    import subtransjav.refine.dict_manager as dm
    monkeypatch.setattr(dm, "_http_get", _fake_http_get)
    return sha


@pytest.fixture()
def isolated_env(tmp_path, monkeypatch):
    """运行时落位与数据根全隔离（防 site-packages 内容落仓库树）。"""
    rt = tmp_path / "rt"
    monkeypatch.setenv("SUBTRANSJAV_CT2_RUNTIME_DIR", str(rt))
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path / "data"))
    return rt


def _norm(p: str) -> str:
    return os.path.normpath(p)


# ---------------------------------------------------------------- install

class TestInstallContractLayout:
    def test_finalized_layout_install_probe_end_to_end(
            self, tmp_path, monkeypatch, isolated_env, capsys):
        """定稿布局 fixture → install → probe 全链 rc=0：manifest 落位回写
        zip_sha256、认证翻转、runtime_python 走 manifest 路径。"""
        sha = _pin_fixture_zip(monkeypatch, tmp_path / "fixture-finalized.zip",
                               _finalized_members())
        monkeypatch.setattr(asr_runtime, "selfcheck",
                            lambda: (True, "ct2-runtime-selfcheck OK"))
        rc = asr_runtime.install("zip")
        assert rc == 0
        out = capsys.readouterr().out
        assert "布局" in out and "sha256 核验通过" in out
        manifest = asr_runtime.read_runtime_manifest()
        assert manifest is not None
        assert manifest["python_exe"] == "python/python.exe"
        assert manifest["site_packages"] == "site-packages"
        assert manifest["zip_sha256"] == sha
        assert asr_runtime.is_installed() is True
        assert _norm(asr_runtime.runtime_python()) == _norm(
            str(isolated_env / "python" / "python.exe"))
        status = asr_runtime.provider_status()
        assert status["installed"] is True
        assert status["certified"] is True
        assert _norm(status["python"]) == _norm(
            str(isolated_env / "python" / "python.exe"))
        assert status["selfcheck"] == "pass"
        assert status["probe"]

    def test_flat_layout_install_rejected(
            self, tmp_path, monkeypatch, isolated_env, capsys):
        """embed 平铺错布局：install 必须失败、诊断含「布局」、零残留。"""
        _pin_fixture_zip(monkeypatch, tmp_path / "fixture-flat.zip", _flat_members())
        rc = asr_runtime.install("zip")
        assert rc == 1
        out = capsys.readouterr().out
        assert "布局" in out
        assert asr_runtime.is_installed() is False
        assert asr_runtime.read_runtime_manifest() is None
        assert not (isolated_env / "python.exe").exists()

    def test_bad_manifest_rejected_and_cleaned(
            self, tmp_path, monkeypatch, isolated_env, capsys):
        """layout_version 非法：布局清单可过但 manifest 校验拒，解包残留清理。"""
        members = _finalized_members()
        members["runtime.json"] = json.dumps({
            "layout_version": 99,
            "python_exe": "python/python.exe",
            "site_packages": "site-packages",
        }).encode("utf-8")
        _pin_fixture_zip(monkeypatch, tmp_path / "fixture-badman.zip", members)
        rc = asr_runtime.install("zip")
        assert rc == 1
        assert "布局" in capsys.readouterr().out
        assert asr_runtime.is_installed() is False
        for name in ("runtime.json", "selfcheck.py", "python", "site-packages"):
            assert not (isolated_env / name).exists(), name

    def test_verify_zip_layout_missing_selfcheck(self, tmp_path):
        """布局清单直测：缺 selfcheck.py 即拒且诊断含「布局」。"""
        members = {k: v for k, v in _finalized_members().items()
                   if k != "selfcheck.py"}
        fixture = tmp_path / "no-selfcheck.zip"
        _build_zip(fixture, members)
        with pytest.raises(RuntimeError) as ei:
            asr_runtime._verify_zip_layout(str(fixture))
        assert "布局" in str(ei.value)


# ---------------------------------------------------------------- 解析序

class TestRuntimePythonResolution:
    def test_manifest_takes_precedence_over_fallback(self, isolated_env,
                                                     monkeypatch):
        """fallback 探测仅诊断非认证；manifest 一到即认证翻转且路径优先。"""
        monkeypatch.setattr(asr_runtime, "selfcheck", lambda: (False, "x"))
        (isolated_env / "Scripts").mkdir(parents=True)
        (isolated_env / "Scripts" / "python.exe").write_bytes(b"stub")
        assert asr_runtime.is_installed() is False
        assert _norm(asr_runtime.runtime_python()) == _norm(
            str(isolated_env / "Scripts" / "python.exe"))
        status = asr_runtime.provider_status()
        assert status["installed"] is False
        assert status["certified"] is False
        assert status["probe"]
        (isolated_env / "python").mkdir()
        (isolated_env / "python" / "python.exe").write_bytes(b"stub")
        (isolated_env / "site-packages").mkdir()
        (isolated_env / "runtime.json").write_bytes(_manifest_bytes())
        assert asr_runtime.is_installed() is True
        assert _norm(asr_runtime.runtime_python()) == _norm(
            str(isolated_env / "python" / "python.exe"))


# ---------------------------------------------------------------- selfcheck

class TestSelfcheckContract:
    def _install_skeleton(self, isolated_env: Path, with_script: bool) -> None:
        (isolated_env / "python").mkdir(parents=True)
        (isolated_env / "python" / "python.exe").write_bytes(b"stub")
        (isolated_env / "site-packages").mkdir()
        (isolated_env / "runtime.json").write_bytes(_manifest_bytes())
        if with_script:
            (isolated_env / "selfcheck.py").write_bytes(
                b"print('ct2-runtime-selfcheck OK')\n")

    def test_selfcheck_runs_selfcheck_script_via_manifest_python(
            self, isolated_env, monkeypatch):
        self._install_skeleton(isolated_env, with_script=True)
        captured: dict = {}

        class _Proc:
            returncode = 0
            stdout = "ct2-runtime-selfcheck OK\n"
            stderr = ""

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _Proc()

        monkeypatch.setattr(asr_runtime.subprocess, "run", fake_run)
        ok, detail = asr_runtime.selfcheck()
        assert ok and "OK" in detail
        assert captured["cmd"][0] == _norm(
            str(isolated_env / "python" / "python.exe"))
        assert captured["cmd"][1] == _norm(str(isolated_env / "selfcheck.py"))

    def test_selfcheck_falls_back_to_snippet_without_script(
            self, isolated_env, monkeypatch):
        """无 selfcheck.py（案 C venv 形态）退化 -c 版本钉断言。"""
        self._install_skeleton(isolated_env, with_script=False)
        captured: dict = {}

        class _Proc:
            returncode = 0
            stdout = "ct2-runtime-selfcheck OK\n"
            stderr = ""

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _Proc()

        monkeypatch.setattr(asr_runtime.subprocess, "run", fake_run)
        ok, _ = asr_runtime.selfcheck()
        assert ok
        assert captured["cmd"][1] == "-c"

    def test_selfcheck_unavailable_reports_human_message(self, isolated_env):
        ok, detail = asr_runtime.selfcheck()
        assert ok is False and "未安装" in detail


# ---------------------------------------------------------------- pin 面

class TestRuntimeZipPin:
    def test_pin_points_to_rebuilt_layout(self):
        """重建件 pin：URL 版本号与 sha/bytes 齐备（构建实录回填后绿）。"""
        assert "1.1.0" in asr_runtime.RUNTIME_ZIP_URL
        assert len(asr_runtime.RUNTIME_ZIP_SHA256) == 64
        assert asr_runtime.RUNTIME_ZIP_BYTES > 0
