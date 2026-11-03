"""CT2 运行时布局契约测试（d1028-36，D2026-1028-04 拍板 B 案升级版）。

防布局再漂移：认证只绑定 d1028-32 §4 定稿单一布局
（python/ + site-packages/ + runtime.json + selfcheck.py）；manifest
（runtime.json）为生产认证路径，fallback 探测（Scripts/、python/、根）
仅诊断非认证；embed 平铺等错布局 install 必须失败且诊断含「布局」。
verified 已于 2026-10-29 随生产路径三门核验通过翻转 True
（d1028-35 runbook 执行记录；门禁翻转后关断语义由 test_asr_ct2 强制
False 回放钉住）。
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import time
import zipfile
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from subtransjav.refine import asr_runtime, dict_manager

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


# ---------------------------------------------------------------- GPU 补丁包

def _runtime_skeleton(rt: Path) -> None:
    """已安装运行时最小骨架（manifest 认证布局）。"""
    (rt / "python").mkdir(parents=True)
    (rt / "python" / "python.exe").write_bytes(b"stub")
    (rt / "site-packages").mkdir()
    (rt / "runtime.json").write_bytes(_manifest_bytes())


def _gpu_patch_members() -> dict[str, bytes]:
    from subtransjav.refine.asr_runner import GPU_DLL_REQUIRED
    members = {"gpu_patch_manifest.json": json.dumps({
        "built_at": "2026-10-29T00:00:00",
        "wheel_versions": {"nvidia-cublas-cu12": "12.8.5.5",
                           "nvidia-cudnn-cu12": "9.19.0.56"},
        "dlls": {d: "stubsha" for d in GPU_DLL_REQUIRED},
    }).encode("utf-8")}
    for d in GPU_DLL_REQUIRED:
        members[d] = b"stub-dll"
    return members


class TestGpuPatchContract:
    def test_install_writes_manifest_and_status_complete(
            self, tmp_path, isolated_env):
        """补丁包安装全链：布局门→解包→DLL 对盘→runtime.json 增 gpu_patch
        字段（未知键透传契约）→status complete=True。"""
        _runtime_skeleton(isolated_env)
        fixture = tmp_path / "gpu-patch.zip"
        _build_zip(fixture, _gpu_patch_members())
        rc = asr_runtime.install_gpu_patch(str(fixture))
        assert rc == 0
        manifest = asr_runtime.read_runtime_manifest()
        assert manifest is not None
        assert manifest["gpu_patch"]["wheel_versions"][
            "nvidia-cudnn-cu12"] == "9.19.0.56"
        assert asr_runtime.read_gpu_patch_manifest() is not None
        status = asr_runtime.gpu_patch_status()
        assert status["installed"] is True and status["complete"] is True
        assert status["missing"] == []

    def test_install_records_verified_stamp(self, tmp_path, isolated_env):
        """D1 加固（D2026-1031-04 ⑧）：安装成功回写验证时刻＋本次 zip 实算
        sha256；既有 installed_at/wheel_versions/dlls 三键保持。"""
        from datetime import datetime

        _runtime_skeleton(isolated_env)
        fixture = tmp_path / "gpu-patch.zip"
        _build_zip(fixture, _gpu_patch_members())
        sha = hashlib.sha256(fixture.read_bytes()).hexdigest()
        assert asr_runtime.install_gpu_patch(str(fixture)) == 0
        manifest = asr_runtime.read_runtime_manifest()
        assert manifest is not None
        gp = manifest["gpu_patch"]
        assert gp["verified_sha256"] == sha
        stamp = gp["last_verified_at"]
        assert isinstance(stamp, str) and stamp
        assert datetime.fromisoformat(stamp).isoformat(
            timespec="seconds") == stamp
        assert gp["installed_at"] and gp["dlls"] and gp["wheel_versions"]

    def test_status_exposes_verified_stamp(self, tmp_path, isolated_env):
        """status 顶层透出两键，值与 runtime.json 的 gpu_patch dict 一致。"""
        _runtime_skeleton(isolated_env)
        fixture = tmp_path / "gpu-patch.zip"
        _build_zip(fixture, _gpu_patch_members())
        sha = hashlib.sha256(fixture.read_bytes()).hexdigest()
        assert asr_runtime.install_gpu_patch(str(fixture)) == 0
        gp = asr_runtime.read_runtime_manifest()["gpu_patch"]
        status = asr_runtime.gpu_patch_status()
        assert status["last_verified_at"] == gp["last_verified_at"]
        assert status["verified_sha256"] == sha

    def test_status_legacy_manifest_without_stamp(self, tmp_path,
                                                 isolated_env):
        """旧态兼容：runtime.json 的 gpu_patch 无两键（伪造旧形态）→ status
        两键 None，既有键读数零变化（不 break 既有消费面）。"""
        _runtime_skeleton(isolated_env)
        fixture = tmp_path / "gpu-patch.zip"
        _build_zip(fixture, _gpu_patch_members())
        assert asr_runtime.install_gpu_patch(str(fixture)) == 0
        before = asr_runtime.gpu_patch_status()
        mpath = isolated_env / "runtime.json"
        data = json.loads(mpath.read_text(encoding="utf-8"))
        data["gpu_patch"] = {k: data["gpu_patch"][k] for k in
                             ("installed_at", "wheel_versions", "dlls")}
        mpath.write_text(json.dumps(data, ensure_ascii=False, indent=1),
                         encoding="utf-8")
        after = asr_runtime.gpu_patch_status()
        assert after["last_verified_at"] is None
        assert after["verified_sha256"] is None
        for key in ("dll_dir", "installed", "complete", "missing", "manifest",
                    "cuda_visible", "online_pin_ready"):
            assert after[key] == before[key]
        assert after["installed"] is True and after["complete"] is True
        assert after["missing"] == [] and after["manifest"] is not None
        assert after["online_pin_ready"] is True

    def test_incomplete_layout_rejected(self, tmp_path, isolated_env,
                                        capsys):
        """半套 DLL zip（缺 cudnn_ops）：布局门拒绝 rc=1（回退分支源头）。"""
        _runtime_skeleton(isolated_env)
        members = _gpu_patch_members()
        del members["cudnn_ops64_9.dll"]
        fixture = tmp_path / "gpu-patch-half.zip"
        _build_zip(fixture, members)
        rc = asr_runtime.install_gpu_patch(str(fixture))
        assert rc == 1
        assert "布局" in capsys.readouterr().out

    def test_install_requires_runtime_first(self, tmp_path, isolated_env):
        """运行时未装：补丁包拒装 rc=3（依赖序 fail-closed）。"""
        fixture = tmp_path / "gpu-patch.zip"
        _build_zip(fixture, _gpu_patch_members())
        assert asr_runtime.install_gpu_patch(str(fixture)) == 3

    def test_runner_command_device_args_only_with_complete_patch(
            self, isolated_env):
        """命令构造钉：补丁齐全→--device auto＋--gpu-dll-dir；未装→不传
        （零行为变化承诺：缺省命令面与件B 前逐字节同）。"""
        _runtime_skeleton(isolated_env)
        cmd = asr_runtime.ct2_runner_command("m.wav", "o.srt")
        assert "--device" not in cmd and "--gpu-dll-dir" not in cmd
        fixture_zip = isolated_env.parent / "gp.zip"
        _build_zip(fixture_zip, _gpu_patch_members())
        assert asr_runtime.install_gpu_patch(str(fixture_zip)) == 0
        cmd2 = asr_runtime.ct2_runner_command("m.wav", "o.srt")
        assert cmd2[cmd2.index("--device") + 1] == "auto"
        assert cmd2[cmd2.index("--gpu-dll-dir") + 1] == \
            str(isolated_env / "gpu-dll")

    def test_online_pin_published_state(self):
        """在线 pin 已点亮态（2026-10-30 时序锁全链走完：上传→远端 oid 对拍
        →会话态冒烟三门过）。字面断言防漂移——原形状断言（len==64/bytes>0）
        拦不住 pin 静默变更（D2026-1029-12 D1 追加门）；URL 域必落下载白名单
        （huggingface.co 不放行，裁决⑤口径）。"""
        assert asr_runtime.GPU_PATCH_ZIP_URL == (
            "https://hf-mirror.com/Angelholl/faster-whisper-large-v2-ct2"
            "/resolve/main/subtrans-gpu-dll-patch-1.0.1-win64.zip")
        host = urlsplit(asr_runtime.GPU_PATCH_ZIP_URL).hostname
        assert host in dict_manager._URL_HOST_ALLOW
        assert asr_runtime.GPU_PATCH_ZIP_SHA256 == \
            "1d9389d61b273149644ddc2803599be9c6cfb2a6e416c14a7bccb96ddb1a3693"
        assert asr_runtime.GPU_PATCH_ZIP_BYTES == 1211323535

    def test_gpu_patch_download_rejects_unpinned_host(self):
        """点亮后守卫下载仍受域白名单约束：非白名单域（含 huggingface.co）
        即拒——白名单与 pin 双门缺一不可（裁决⑤）。"""
        from subtransjav.refine.dict_manager import DictDownloadError
        with pytest.raises(DictDownloadError) as ei:
            asr_runtime._guarded_download(
                "https://huggingface.co/Angelholl/faster-whisper-large-v2-ct2"
                "/resolve/main/subtrans-gpu-dll-patch-1.0.1-win64.zip",
                "out.zip", asr_runtime.GPU_PATCH_ZIP_SHA256, 1)
        assert "白名单" in str(ei.value)

    def test_cuda_probe_goes_through_runtime_subprocess(self, isolated_env,
                                                        monkeypatch):
        """打包态恒灰回归（3.1.1 修，D2026-1030-03 点亮链发现）：CUDA 探测必须
        经自管运行时子进程取真值，不再依赖应用进程可 import ctranslate2——
        3.1.0 引擎脱钩后 ct2 非项目依赖，打包面不含它，原进程内探测恒 0。"""
        monkeypatch.setattr(asr_runtime, "_cuda_probe_cache", None)
        _runtime_skeleton(isolated_env)
        captured: dict = {}

        class _Proc:
            returncode = 0
            stdout = "1\n"
            stderr = ""

        def fake_run(cmd, **kwargs):
            captured["cmd"] = cmd
            return _Proc()

        monkeypatch.setattr(asr_runtime.subprocess, "run", fake_run)
        assert asr_runtime.gpu_patch_status()["cuda_visible"] is True
        assert captured["cmd"][0] == _norm(
            str(isolated_env / "python" / "python.exe"))
        assert "get_cuda_device_count" in captured["cmd"][2]

    def test_cuda_probe_cached_across_status_polls(self, isolated_env,
                                                   monkeypatch):
        """GUI 引擎页 1s 轮询不得反复起进程：成功值按 TTL 缓存。"""
        monkeypatch.setattr(asr_runtime, "_cuda_probe_cache", None)
        _runtime_skeleton(isolated_env)
        calls: list[int] = []

        class _Proc:
            returncode = 0
            stdout = "2\n"
            stderr = ""

        def fake_run(cmd, **kwargs):
            calls.append(1)
            return _Proc()

        monkeypatch.setattr(asr_runtime.subprocess, "run", fake_run)
        assert asr_runtime.cuda_device_count() == 2
        assert asr_runtime.cuda_device_count() == 2
        assert len(calls) == 1

    def test_cuda_probe_no_spawn_and_zero_without_runtime(self, isolated_env,
                                                          monkeypatch):
        """运行时未装＝不起探测进程、不缓存（install 完成即可探到真值）。"""
        monkeypatch.setattr(asr_runtime, "_cuda_probe_cache", None)

        def fake_run(cmd, **kwargs):
            raise AssertionError("运行时未装不得起探测进程")

        monkeypatch.setattr(asr_runtime.subprocess, "run", fake_run)
        assert asr_runtime.cuda_device_count() == 0
        assert asr_runtime._cuda_probe_cache is None

    def test_cuda_probe_failure_degrades_to_zero(self, isolated_env,
                                                 monkeypatch):
        """探测失败（rc≠0/输出不可解析）＝0 不抛（探测面永不抛承诺），
        且失败按短 TTL 缓存后重试。"""
        monkeypatch.setattr(asr_runtime, "_cuda_probe_cache", None)
        _runtime_skeleton(isolated_env)

        class _Proc:
            returncode = 1
            stdout = ""
            stderr = "ModuleNotFoundError: No module named 'ctranslate2'"

        monkeypatch.setattr(asr_runtime.subprocess, "run",
                            lambda cmd, **kw: _Proc())
        assert asr_runtime.cuda_device_count() == 0
        assert asr_runtime._cuda_probe_cache is not None


# ---------------------------------------------------------------------------
# d1103（D2026-1103-03）：运行时落位可自定义＋源码形态默认离 C 盘
# ---------------------------------------------------------------------------

def _settings_kv(dir_value: str) -> str:
    """构造含 ct2_runtime_dir 键的 settings KV JSON 文本。"""
    return json.dumps({"stages": [], "settings": {
        asr_runtime.CT2_RUNTIME_DIR_KEY: dir_value}})


def test_ct2_runtime_dir_resolution_order(tmp_path, monkeypatch):
    """解析序 env > settings 键 > 现形默认，来源标签随源切换（GUI 落位行＋
    CLI 诊断消费；负控：settings 键不被读取即红）。"""
    from subtransjav.refine import config as refine_config
    monkeypatch.delenv("SUBTRANSJAV_CT2_RUNTIME_DIR", raising=False)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "refine_stage_settings.json").write_text(
        _settings_kv(str(tmp_path / "custom")), encoding="utf-8")
    monkeypatch.setattr(refine_config, "CONFIG_DIR", str(cfg))
    info = asr_runtime.runtime_dir_info()
    assert info["dir"] == str(tmp_path / "custom"), "settings 键未生效"
    assert info["source"] == "settings"
    assert asr_runtime.runtime_root() == str(tmp_path / "custom")
    # env 优先级最高（测试隔离/CI 通道不得被设置键遮蔽）
    monkeypatch.setenv("SUBTRANSJAV_CT2_RUNTIME_DIR", str(tmp_path / "envrt"))
    assert asr_runtime.runtime_dir_info()["source"] == "env"
    # 空串＝清除自定义回落默认（GUI「恢复默认」语义）
    (cfg / "refine_stage_settings.json").write_text(
        _settings_kv(""), encoding="utf-8")
    monkeypatch.delenv("SUBTRANSJAV_CT2_RUNTIME_DIR", raising=False)
    assert asr_runtime.runtime_dir_info()["source"] != "settings"
    # 设置文件缺失/非法一律缺省语义不抛
    monkeypatch.setattr(refine_config, "CONFIG_DIR",
                        str(tmp_path / "no-such-dir"))
    assert asr_runtime.runtime_dir_info()["source"] != "settings"


def test_ct2_runtime_default_sibling_off_repo(tmp_path, monkeypatch):
    """源码形态（数据根=仓库根）默认落位＝**仓库同级旁路**
    ``<仓库父目录>/<仓库名>-runtime/ct2``：不在仓库树内（脱钩裁定原意＝
    site-packages 第三方自带测试文件污染全树扫描面，不因离 C 盘而松动），
    且随仓库所在盘走不再固定 C 盘（owner 走查 D2026-1103-03）。
    旧 LOCALAPPDATA 位降为 legacy 兜底：新位无运行时而旧位有认证运行时时
    沿用旧位（防存量用户升级后静默重下 106MB 运行时＋1.21GB GPU 补丁）。"""
    from subtransjav.refine import config as refine_config
    monkeypatch.delenv("SUBTRANSJAV_CT2_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(refine_config, "CONFIG_DIR",
                        str(tmp_path / "no-conf"))
    repo = tmp_path / "repo"
    (repo / "subtransjav").mkdir(parents=True)
    monkeypatch.setattr(asr_runtime.paths, "app_root", lambda: repo)
    monkeypatch.setattr(asr_runtime.paths, "data_root", lambda: repo)
    local = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(local))

    sibling = repo.parent / "repo-runtime" / "ct2"
    info = asr_runtime.runtime_dir_info()
    assert _norm(info["dir"]) == _norm(str(sibling)), \
        "默认落位须为仓库同级旁路"
    assert info["source"] == "default"
    assert not _norm(info["dir"]).startswith(
        _norm(str(repo)) + os.sep), "旁路默认不得落仓库树内"
    assert _norm(info["dir"]) != _norm(
        str(local / "SubTrans" / "runtime" / "ct2")), \
        "默认不得再固定 C 盘 LOCALAPPDATA"

    # 旧位有认证运行时 → legacy 兜底（不静默重下）
    legacy = local / "SubTrans" / "runtime" / "ct2"
    _runtime_skeleton(legacy)
    info = asr_runtime.runtime_dir_info()
    assert info["source"] == "legacy" and _norm(info["dir"]) == _norm(
        str(legacy))

    # 新位也有运行时 → 新默认优先，不再回旧位
    _runtime_skeleton(sibling)
    info = asr_runtime.runtime_dir_info()
    assert info["source"] == "default" and _norm(info["dir"]) == _norm(
        str(sibling))
    assert asr_runtime.gpu_patch_dir().startswith(_norm(str(sibling)))


def test_cuda_probe_cache_keyed_by_runtime_root(tmp_path, monkeypatch):
    """切落位后旧根探测值不得在 TTL 内继续生效（缓存按运行时根分键）。"""
    monkeypatch.setattr(asr_runtime, "_cuda_probe_cache", None)
    root_a = tmp_path / "rtA"
    _runtime_skeleton(root_a)
    monkeypatch.setenv("SUBTRANSJAV_CT2_RUNTIME_DIR", str(root_a))
    calls: list[str] = []

    class _Proc:
        returncode = 0
        stdout = "1\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        calls.append(str(cmd[0]))
        return _Proc()

    monkeypatch.setattr(asr_runtime.subprocess, "run", fake_run)
    assert asr_runtime.cuda_device_count() == 1
    assert asr_runtime.cuda_device_count() == 1      # 同根 TTL 内不重探
    assert len(calls) == 1, "同根缓存未命中（反复起进程）"

    root_b = tmp_path / "rtB"
    _runtime_skeleton(root_b)
    monkeypatch.setenv("SUBTRANSJAV_CT2_RUNTIME_DIR", str(root_b))
    assert asr_runtime.cuda_device_count() == 1
    assert len(calls) == 2, "切根未重探（缓存未按运行时根分键）"
    assert _norm(calls[1]) == _norm(str(root_b / "python" / "python.exe"))


def test_download_tmp_path_follows_runtime_root(tmp_path, monkeypatch):
    """下载中间件（106MB 运行时 zip／1.21GB GPU 补丁 zip）落位跟运行时根走，
    不再落数据根＝源码形态下的仓库根（评审补漏 D2026-1103-03：owner 要「不装
    在 C 盘」，旧口径 paths.data_subdir("runtime") 在源码形态即仓库根 /runtime，
    中间件仍落仓库所在盘）；且落运行时根的**同级**旁路，不落解包目标根内。
    自定义位恰为盘根时退回系统临时目录（不在盘根建目录）。"""
    root = tmp_path / "outer" / "ct2"
    root.mkdir(parents=True)
    monkeypatch.setenv("SUBTRANSJAV_CT2_RUNTIME_DIR", str(root))
    p = asr_runtime._download_tmp_path("ct2-gpu-patch.zip.tmp")
    assert _norm(p) == _norm(str(tmp_path / "outer" / ".ct2-downloads"
                                 / "ct2-gpu-patch.zip.tmp"))
    assert os.path.isdir(os.path.dirname(p)), "中间件目录须已创建"
    assert not _norm(p).startswith(_norm(str(root))), \
        "半成品 zip 不得躺在解包目标运行时根内"

    drive = Path(str(tmp_path)).drive + os.sep
    monkeypatch.setenv("SUBTRANSJAV_CT2_RUNTIME_DIR", drive)
    p2 = asr_runtime._download_tmp_path("ct2-runtime.zip.part.tmp")
    assert not _norm(p2).startswith(_norm(drive + ".ct2-downloads")), \
        "自定义位为盘根时不得在盘根建目录"
    assert _norm(p2).startswith(_norm(tempfile.gettempdir())), p2


def test_default_root_legacy_fallback_accepts_venv_form(tmp_path, monkeypatch):
    """旧 LOCALAPPDATA 位为案 C venv 形态（无 manifest）时仍算可复用运行时→
    回落 legacy，不让存量用户升级后静默重下（评审补漏 D2026-1103-03）。
    放宽只在**落位选择面**：认证判定仍绑 manifest 单一布局（is_installed 不
    松动，D2026-1028-04）；半套骨架（有 python 无 site-packages）不算可复用。"""
    from subtransjav.refine import config as refine_config
    monkeypatch.delenv("SUBTRANSJAV_CT2_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(refine_config, "CONFIG_DIR", str(tmp_path / "no-conf"))
    repo = tmp_path / "repo"
    (repo / "subtransjav").mkdir(parents=True)
    monkeypatch.setattr(asr_runtime.paths, "app_root", lambda: repo)
    monkeypatch.setattr(asr_runtime.paths, "data_root", lambda: repo)
    local = tmp_path / "localappdata"
    monkeypatch.setenv("LOCALAPPDATA", str(local))
    legacy = local / "SubTrans" / "runtime" / "ct2"

    (legacy / "Scripts").mkdir(parents=True)
    (legacy / "Scripts" / "python.exe").write_bytes(b"stub")
    (legacy / "site-packages").mkdir()
    info = asr_runtime.runtime_dir_info()
    assert info["source"] == "legacy" and _norm(info["dir"]) == _norm(
        str(legacy)), "venv 形态旧位未被识别（会静默重下）"
    assert asr_runtime.is_installed() is False, "认证判定不得随落位放宽而松动"

    shutil.rmtree(legacy / "site-packages")
    assert asr_runtime.runtime_dir_info()["source"] == "default", \
        "半套骨架不应被当作可复用运行时"


# ---------------------------------------------------------------------------
# d1103（D2026-1103-04）：模型落位可自定义（owner 令「模型安装位置设置和
# GPU 加速补丁包一样」）
# ---------------------------------------------------------------------------

def _model_skeleton(root: Path, model: str = "large-v2") -> Path:
    """模型落位件最小骨架（``model.bin`` 在位＝「已落位」谓词）。"""
    d = root / model
    d.mkdir(parents=True, exist_ok=True)
    (d / "model.bin").write_bytes(b"stub-model")
    return d


def test_ct2_model_dir_resolution_order(tmp_path, monkeypatch):
    """解析序 env > settings 键 > 现形默认；与运行时键互不干扰（两键两
    来源各读各的，混读即红）。"""
    from subtransjav.refine import config as refine_config
    monkeypatch.delenv("SUBTRANSJAV_CT2_MODEL_DIR", raising=False)
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "refine_stage_settings.json").write_text(json.dumps({
        "settings": {asr_runtime.CT2_MODEL_DIR_KEY: str(tmp_path / "custom")}},
    ), encoding="utf-8")
    monkeypatch.setattr(refine_config, "CONFIG_DIR", str(cfg))
    info = asr_runtime.ct2_model_dir_info()
    assert info["dir"] == str(tmp_path / "custom"), "settings 键未生效"
    assert info["source"] == "settings"
    assert asr_runtime.ct2_model_dir() == str(tmp_path / "custom")
    monkeypatch.setenv("SUBTRANSJAV_CT2_MODEL_DIR", str(tmp_path / "envm"))
    assert asr_runtime.ct2_model_dir_info()["source"] == "env"
    # 两键互不干扰：运行时 env 值不得被模型面读走
    monkeypatch.delenv("SUBTRANSJAV_CT2_MODEL_DIR", raising=False)
    monkeypatch.setenv("SUBTRANSJAV_CT2_RUNTIME_DIR", str(tmp_path / "rt"))
    assert asr_runtime.ct2_model_dir_info()["source"] == "settings"
    assert asr_runtime.runtime_dir_info()["dir"] == str(tmp_path / "rt")
    # 空串＝清除自定义（GUI「恢复默认」语义）
    (cfg / "refine_stage_settings.json").write_text(json.dumps(
        {"settings": {asr_runtime.CT2_MODEL_DIR_KEY: ""}}), encoding="utf-8")
    monkeypatch.delenv("SUBTRANSJAV_CT2_RUNTIME_DIR", raising=False)
    assert asr_runtime.ct2_model_dir_info()["source"] != "settings"


def test_ct2_model_default_gate_and_legacy_candidates(tmp_path, monkeypatch):
    """默认落位门控（critic HRO-1）：仅源码形态（非 frozen 且数据根=仓库根）
    默认改仓库同级旁路；数据根自定义与 frozen 一律随数据根——否则存量用户
    旧件失联静默重下 2.9 GB。legacy 候选按序取首个有货者（旧仓库位有货即
    标 legacy），旁路有货则新默认优先。"""
    from subtransjav.refine import config as refine_config
    monkeypatch.delenv("SUBTRANSJAV_CT2_MODEL_DIR", raising=False)
    monkeypatch.setattr(refine_config, "CONFIG_DIR", str(tmp_path / "no-conf"))
    repo = tmp_path / "repo"
    (repo / "subtransjav").mkdir(parents=True)
    monkeypatch.setattr(asr_runtime.paths, "app_root", lambda: repo)
    monkeypatch.setattr(asr_runtime.paths, "data_root", lambda: repo)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    sibling = repo.parent / "repo-runtime" / "models" / "ct2"

    info = asr_runtime.ct2_model_dir_info()
    assert _norm(info["dir"]) == _norm(str(sibling)), "默认须为仓库同级旁路"
    assert info["source"] == "default"
    assert not _norm(info["dir"]).startswith(
        _norm(str(repo)) + os.sep), "旁路默认不得落仓库树内"

    _model_skeleton(repo / "models" / "ct2")
    info = asr_runtime.ct2_model_dir_info()
    assert info["source"] == "legacy" and _norm(info["dir"]) == _norm(
        str(repo / "models" / "ct2")), "旧仓库位有货未被识别（会重下 2.9GB）"

    _model_skeleton(sibling)
    info = asr_runtime.ct2_model_dir_info()
    assert info["source"] == "default" and _norm(info["dir"]) == _norm(
        str(sibling))

    ext = tmp_path / "data-ext"
    monkeypatch.setattr(asr_runtime.paths, "data_root", lambda: ext)
    info = asr_runtime.ct2_model_dir_info()
    assert _norm(info["dir"]) == _norm(str(ext / "models" / "ct2")), \
        "数据根自定义时默认不得改旁路（HRO-1）"
    assert info["source"] == "default"

    # frozen 形态：app_root() 返回数据根致两值天然相等，不得触发旁路分支
    monkeypatch.setattr(asr_runtime.paths, "app_root", lambda: ext)
    monkeypatch.setattr(asr_runtime.paths, "is_frozen", lambda: True)
    info = asr_runtime.ct2_model_dir_info()
    assert _norm(info["dir"]) == _norm(str(ext / "models" / "ct2"))
    assert info["source"] == "default", "frozen 不得走旁路/legacy 分支"


def test_runtime_default_gate_excludes_frozen(tmp_path, monkeypatch):
    """运行时侧同一门控自查修正（D2026-1103-04）：frozen 下 app_root() 依
    D2026-0929-08 返回数据根，旧实现以「数据根=仓库根」为条件即误命中，会把
    frozen 实例运行时指向数据根同级旁路或另一实例旧位。"""
    from subtransjav.refine import config as refine_config
    monkeypatch.delenv("SUBTRANSJAV_CT2_RUNTIME_DIR", raising=False)
    monkeypatch.setattr(refine_config, "CONFIG_DIR", str(tmp_path / "no-conf"))
    data = tmp_path / "frozen-data"
    monkeypatch.setattr(asr_runtime.paths, "app_root", lambda: data)
    monkeypatch.setattr(asr_runtime.paths, "data_root", lambda: data)
    monkeypatch.setattr(asr_runtime.paths, "is_frozen", lambda: True)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    info = asr_runtime.runtime_dir_info()
    assert _norm(info["dir"]) == _norm(str(data / "runtime" / "ct2"))
    assert info["source"] == "default", "frozen 不得被标 legacy 或改旁路"


def test_model_download_tmp_path_and_atomic_install(tmp_path, monkeypatch):
    """模型 2.9 GB 中间件随模型落位走（补齐 D2026-1103-03 只覆盖运行时件的
    缺口，评议 DEPENDENCY-IMPACT）；解包只进 ``<model>.partial``，核验失败
    不留半截最终位也不留暂存残骸（评议 HRO-2/Q3：半截 model.bin 会被「已
    落位」谓词当真，还会让 legacy 兜底选中坏目录）。"""
    model_root = tmp_path / "engine" / "models" / "ct2"
    model_root.mkdir(parents=True)
    monkeypatch.setenv("SUBTRANSJAV_CT2_MODEL_DIR", str(model_root))
    p = asr_runtime._download_tmp_path("large-v2-ct2.zip.tmp",
                                       asr_runtime.ct2_model_dir())
    assert _norm(p) == _norm(str(tmp_path / "engine" / "models"
                                 / ".ct2-downloads" / "large-v2-ct2.zip.tmp"))
    assert not _norm(p).startswith(_norm(str(model_root))), \
        "半成品 zip 不得躺在模型落位根内"

    entry = dict(asr_runtime.CT2_MODELS[0])
    monkeypatch.setattr(asr_runtime, "CT2_MODELS", [dict(entry, verified=True)])

    junk = tmp_path / "junk.zip"
    _build_zip(junk, {"junk/config.json": b"{}"})
    monkeypatch.setattr(asr_runtime, "_guarded_download",
                        lambda url, dest, sha, size=0, progress=None:
                        shutil.copyfile(str(junk), dest))
    # rc=4＝解包结构异常（D2026-1103-04 拆分：旧版兼指「已落位」的 rc=1
    # 会让异步面把真失败洗成成功）
    assert asr_runtime.download_model("large-v2") == 4
    assert not (model_root / "large-v2").exists(), "结构异常件不得留最终位"
    assert not (model_root / "large-v2.partial").exists(), "暂存残骸须清走"

    good = tmp_path / "good.zip"
    _build_zip(good, {"model.bin": b"MODEL", "config.json": b"{}"})
    monkeypatch.setattr(asr_runtime, "_guarded_download",
                        lambda url, dest, sha, size=0, progress=None:
                        shutil.copyfile(str(good), dest))
    assert asr_runtime.download_model("large-v2") == 0
    assert (model_root / "large-v2" / "model.bin").is_file()
    assert not (model_root / "large-v2.partial").exists(), "换名后暂存位不得留"


def test_provider_status_exposes_model_dir_fields(tmp_path, monkeypatch):
    """GUI 模型落位行要显「该位置有无模型＋体量」，provider_status 须透出
    model_dir/model_source/model_present/model_bytes 四键（D2026-1103-04）；
    models 列表仍＝pin 常量，不得被就地加键污染。"""
    monkeypatch.delenv("SUBTRANSJAV_CT2_MODEL_DIR", raising=False)
    model_root = tmp_path / "models" / "ct2"
    monkeypatch.setenv("SUBTRANSJAV_CT2_MODEL_DIR", str(model_root))
    st = asr_runtime.provider_status()
    assert st["model_runtime"] == {"dir": str(model_root), "source": "env"}
    assert st["model_present"] is False and st["model_bytes"] == 0
    _model_skeleton(model_root)
    (model_root / "large-v2" / "model.bin").write_bytes(b"x" * 1234)
    st2 = asr_runtime.provider_status()
    assert st2["model_present"] is True and st2["model_bytes"] == 1234
    assert st["models"] == asr_runtime.CT2_MODELS
    # 暂存位不得算「有货」（评审补漏：半成品遮蔽会让 legacy 选中坏目录）
    shutil.rmtree(model_root / "large-v2")
    (model_root / "large-v2.partial").mkdir()
    (model_root / "large-v2.partial" / "model.bin").write_bytes(b"half")
    assert asr_runtime.has_model_at(str(model_root)) is False
    assert asr_runtime.provider_status()["model_present"] is False


def test_start_model_download_already_installed_maps_done(monkeypatch):
    """rc=1＝「模型已落位」不是失败：旧口径把 rc!=0 一律记 failed，GUI 点
    下载即显「模型下载失败 rc=1」误导（D2026-1103-04 评审补漏）。"""
    monkeypatch.setattr(asr_runtime, "download_model",
                        lambda model="large-v2": 1)
    monkeypatch.setattr(asr_runtime, "_OP_STATE",
                        {"phase": "idle", "kind": "", "detail": "", "rc": None})
    assert asr_runtime.start_model_download("large-v2")["started"] is True
    for _ in range(100):
        if asr_runtime.operation_progress()["phase"] != "running":
            break
        time.sleep(0.02)
    op = asr_runtime.operation_progress()
    assert op["phase"] == "done" and op["rc"] == 1, "已落位仍被记 failed"
    assert "已落位" in (op["detail"] or "")
