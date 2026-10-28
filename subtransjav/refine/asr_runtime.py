"""asr_runtime——CT2 转写引擎自管运行时（3.2.0，D2026-1028-03）。

上游 whisperjav 对齐已终裁关闭（owner 2026-10-23），转写引擎迁移 CT2 的
运行时承载落本模块。分发机制经 spike 三案对拍定案（HRO-1 采纳，报告
存内部记录 D2026-1028-03 引）：

- **案 A 预打包 zip＝主路径**：单文件 zip（python-embed+全钉 site-packages）
  下载+sha256 pin+解包 selfcheck，照词典链先例。pin 表双空＝镜像件未发布
  态（待 owner 上传+pin），调用即人话报错，不虚装。
- **案 C 在线 venv＝降级路径**：现场 venv+pip 装全钉依赖（spike 全链实证
  可行）；仅 pip/源码安装形态可用——frozen EXE 无解释器可建 venv，明确
  报错指引案 A，不静默降级。

依赖钉（spike 实锤）：faster-whisper==1.2.1 + ctranslate2==4.8.4 +
av==13.1.0（av>=15 移除 metadata_errors 实证炸；av 官方无 14.3.0 该版本号；
--only-binary 防 source build）。版本组合变更须重跑 spike 对拍并联动
selfcheck 版本断言。

零出域声明：本模块仅下载运行时/模型件（URL 均须 pin+白名单域），转写
全程本地；不触碰既有上游 whisper 链（asr_env 零改动）。
"""

from __future__ import annotations

import argparse
import contextlib
import json
import os
import pathlib
import subprocess
import sys
import threading

from .. import paths
from ..utils.subprocess_flags import CREATE_NO_WINDOW

__all__ = [
    "PINNED_DEPS",
    "RUNTIME_ZIP_URL",
    "RUNTIME_ZIP_SHA256",
    "CT2_MODELS",
    "RUNTIME_MANIFEST_NAME",
    "RUNTIME_LAYOUT_VERSION",
    "runtime_root",
    "runtime_python",
    "read_runtime_manifest",
    "is_installed",
    "provider_status",
    "install",
    "selfcheck",
    "download_model",
    "ct2_model_dir",
    "resolve_ct2_model_dir",
    "ct2_runner_command",
    "main",
]

# 依赖钉（spike 实证组合；改动须重跑 spike 并联动 selfcheck 断言）
PINNED_DEPS: list[str] = [
    "faster-whisper==1.2.1",
    "ctranslate2==4.8.4",
    "av==13.1.0",
]

# 案 A 预打包件 pin（构建实录 sha256；URL 走 hf-mirror 中转，完整性锚=
# sha256 pin 本身——镜像仓库内容变更即校验拒载，与词典链同威胁模型）
RUNTIME_ZIP_URL = ("https://hf-mirror.com/Angelholl/subtrans-ct2-runtime"
                   "/resolve/main/subtrans-ct2-runtime-1.1.0-win64.zip")
RUNTIME_ZIP_SHA256 = "a53da81338238ad5a7cc6d27ac373bd3666a3a1029b0bda53e98f0cbc8795140"
RUNTIME_ZIP_BYTES = 109673863

# CT2 模型元数据（zip 打包件 pin；verified=True 须经生产路径实下载逐字节
# 核验后翻转——上架门沿词典链先例）
CT2_MODELS: list[dict] = [
    {
        "model": "large-v2",
        "backend": "ct2",
        "bytes": 3089579624,       # zip 打包件（model.bin/config/tokenizer/vocab 四件）
        "sha256": "4ca806c0061940ad903fe2e41d7f4a424b4a1cfe2f352a335cefc23e87fe1932",
        "url": ("https://hf-mirror.com/Angelholl/faster-whisper-large-v2-ct2"
                "/resolve/main/faster-whisper-large-v2-ct2.zip"),
        "verified": False,         # 待镜像上传+生产路径实下载核验后翻转
        "desc": "CT2 版 large-v2（社区天花板配置 int8_float16 同源权重）",
    },
]

# 子进程统一形态：参数列表+shell=False+无窗口（CREATE_NO_WINDOW 单一来源）
_SPAWN_FLAGS = CREATE_NO_WINDOW

# 定稿布局契约（D2026-1028-04）：认证只绑定 manifest 单一布局
# （python/ + site-packages/ + runtime.json + selfcheck.py），fallback
# 探测（Scripts/、python/、根）仅作诊断不作生产认证路径。
RUNTIME_MANIFEST_NAME = "runtime.json"
RUNTIME_LAYOUT_VERSION = 1
_RUNTIME_FALLBACK_PYTHONS = (
    os.path.join("Scripts", "python.exe"),     # 案 C venv 形态
    os.path.join("python", "python.exe"),      # 定稿 embed 布局
    "python.exe",                              # 平铺（诊断用，认证不认）
)
_INSTALL_TOP_MEMBERS = ("runtime.json", "selfcheck.py", "python", "site-packages")


def runtime_root() -> str:
    """运行时落位：数据根 runtime/ct2（随数据根迁移）。

    例外（脱钩轮）：数据根=仓库根（pip/源码开发形态）时不落仓库树——
    site-packages 内第三方自带测试文件会污染全树安全扫描面，改落
    %LOCALAPPDATA%/SubTrans/runtime/ct2（与 frozen 缺省数据根同域）；
    可经 SUBTRANSJAV_CT2_RUNTIME_DIR 显式覆盖。"""
    override = os.environ.get("SUBTRANSJAV_CT2_RUNTIME_DIR", "").strip()
    if override:
        return override
    try:
        if paths.data_root().resolve() == paths.app_root().resolve():
            local = pathlib.Path(os.environ.get("LOCALAPPDATA",
                                                str(pathlib.Path.home())))
            return str(local / "SubTrans" / "runtime" / "ct2")
    except OSError:
        pass
    return paths.data_subdir("runtime", "ct2")


def read_runtime_manifest(root: str = "") -> dict | None:
    """读+校验运行时 manifest；缺失/非法一律返回 None（不抛，诊断面用）。

    认证语义（D2026-1028-04）：layout_version 匹配 + python_exe/site_packages
    为相对路径且解包落位真实存在。zip_sha256 由安装器核验后回写，本函数
    不作强校验（有无皆可读）。"""
    base = root or runtime_root()
    try:
        data = json.loads(pathlib.Path(base, RUNTIME_MANIFEST_NAME)
                          .read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    if data.get("layout_version") != RUNTIME_LAYOUT_VERSION:
        return None
    py_rel = data.get("python_exe")
    sp_rel = data.get("site_packages")
    if not py_rel or not sp_rel or os.path.isabs(str(py_rel)) \
            or os.path.isabs(str(sp_rel)):
        return None
    if not os.path.isfile(os.path.join(base, str(py_rel))):
        return None
    if not os.path.isdir(os.path.join(base, str(sp_rel))):
        return None
    return data


def _probe_runtime_python(root: str = "") -> str:
    """fallback 探测（Scripts/、python/、根）——仅诊断非生产认证路径。"""
    base = root or runtime_root()
    for rel in _RUNTIME_FALLBACK_PYTHONS:
        cand = os.path.join(base, rel)
        if os.path.isfile(cand):
            return os.path.normpath(cand)
    return ""


def runtime_python() -> str:
    """运行时解释器：manifest 声明优先，无 manifest 退化 fallback 探测
    （供 selfcheck/runner 诊断性使用；认证判定见 is_installed）。"""
    manifest = read_runtime_manifest()
    if manifest:
        return os.path.normpath(
            os.path.join(runtime_root(), str(manifest["python_exe"])))
    return _probe_runtime_python()


def is_installed() -> bool:
    """运行时已安装＝manifest 认证布局在位（D2026-1028-04：verified 只
    绑定定稿单一布局，不做多布局全兼容认证）。"""
    return read_runtime_manifest() is not None


def ct2_model_dir() -> str:
    return paths.data_subdir("models", "ct2")


def resolve_ct2_model_dir(model: str, model_dir: str = "") -> str:
    """ct2 模型目录解析：显式 --model-dir 优先，否则数据根 models/ct2/<model>。

    与 whisper 链"探测与加载同序"口径一致：解析失败返回空串由调用方人话
    报错，绝不静默回退缓存。"""
    if model_dir:
        return model_dir if os.path.isdir(model_dir) else ""
    cand = os.path.join(ct2_model_dir(), model)
    if os.path.isdir(cand) and os.path.isfile(os.path.join(cand, "model.bin")):
        return cand
    return ""


# 1s 正弦波音频链自检体（d1028-32 selfcheck 契约：import 全链+版本钉+
# 真音频解码 rc=0；numpy/wave 在运行时 site-packages/stdlib 内）
_SELFHECK_AUDIO_BODY = (
    "import wave, tempfile, os\n"
    "import numpy as np\n"
    "sr = 16000\n"
    "t = np.arange(sr) / sr\n"
    "pcm = (0.5 * np.sin(2 * np.pi * 440.0 * t) * 32767).astype('int16')\n"
    "fd, path = tempfile.mkstemp(suffix='.wav')\n"
    "os.close(fd)\n"
    "try:\n"
    "    with wave.open(path, 'wb') as w:\n"
    "        w.setnchannels(1)\n"
    "        w.setsampwidth(2)\n"
    "        w.setframerate(sr)\n"
    "        w.writeframes(pcm.tobytes())\n"
    "    from faster_whisper.audio import decode_audio\n"
    "    audio = decode_audio(path, sampling_rate=sr)\n"
    "    assert audio.shape[0] == sr, audio.shape\n"
    "finally:\n"
    "    os.remove(path)\n"
)
_SELFHECK_SNIPPET = (
    "import ctranslate2, av\n"
    "assert ctranslate2.__version__ == '4.8.4', ctranslate2.__version__\n"
    "assert av.__version__.startswith('13.'), av.__version__\n"
    "import faster_whisper\n"
    "from faster_whisper import WhisperModel  # noqa: F401\n"
    + _SELFHECK_AUDIO_BODY +
    "print('ct2-runtime-selfcheck OK')\n"
)


def selfcheck() -> tuple[bool, str]:
    """运行时自检：import 全链+版本钉+1s 正弦波音频链（模型无关，不下载
    任何模型）。执行形态＝selfcheck.py（定稿布局自带）优先，缺脚本退化
    -c 片段（案 C venv 无 manifest 也可自检——认证判定另见 is_installed）。"""
    py = runtime_python()
    if not py:
        return False, "运行时未安装（" + runtime_root() \
            + " 无 manifest 且 fallback 探测无 python.exe）"
    script = os.path.join(runtime_root(), "selfcheck.py")
    cmd = [py, script] if os.path.isfile(script) else [py, "-c", _SELFHECK_SNIPPET]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120,
                              encoding="utf-8", errors="replace", shell=False,
                              creationflags=_SPAWN_FLAGS)
    except (OSError, subprocess.TimeoutExpired) as e:
        return False, "自检进程失败: " + str(e)
    if proc.returncode != 0:
        return False, "自检失败 rc=" + str(proc.returncode) + ": " + proc.stderr[-400:]
    if "ct2-runtime-selfcheck OK" not in proc.stdout:
        return False, "自检输出缺少成功行: " + proc.stdout[-200:]
    return True, proc.stdout.strip().splitlines()[-1]


def provider_status() -> dict:
    """状态快照（GUI/CLI 双消费）。

    installed＝manifest 认证布局（D2026-1028-04）；probe＝fallback 探测
    结果（诊断面，认证不认）；certified＝认证通过（manifest+清单校验+
    自检过）。"""
    manifest = read_runtime_manifest()
    probe = _probe_runtime_python()
    py = os.path.normpath(os.path.join(runtime_root(),
                                       str(manifest["python_exe"]))) \
        if manifest else probe
    ok, detail = selfcheck() if py else (False, "未安装")
    return {
        "installed": manifest is not None,
        "python": py,
        "probe": probe,
        "certified": manifest is not None and ok,
        "selfcheck": "pass" if ok else "fail",
        "detail": detail,
        "zip_published": bool(RUNTIME_ZIP_URL and RUNTIME_ZIP_SHA256),
        "pinned_deps": list(PINNED_DEPS),
        "models": CT2_MODELS,
    }


def _pip_env() -> dict:
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
    # 镜像下载子进程代理中和（D2026-1028-04）：仅注入子进程环境不污染
    # 全局——pip 镜像源走境内直连，系统代理反成坏损/限速源
    env["no_proxy"] = "*"
    env["NO_PROXY"] = "*"
    return env


def _venv_create_cmd(base_python: str, root: str) -> list[str]:
    return [base_python, "-m", "venv", root]


def _pip_install_cmd(runtime_py: str, index_args: list[str]) -> list[str]:
    cmd = [runtime_py, "-m", "pip", "install", "--only-binary=:all:",
           "--disable-pip-version-check"]
    cmd.extend(index_args)
    cmd.extend(PINNED_DEPS)
    return cmd


def _install_via_venv() -> int:
    """案 C：现场 venv+pip 装全钉依赖（spike 全链实证；仅非 frozen 形态）。

    venv 布局（Scripts/python.exe）无 manifest——selfcheck 经 fallback
    探测可跑，但认证面（is_installed/provider_status.installed）不认：
    D2026-1028-04 认证只绑定定稿布局。"""
    if getattr(sys, "frozen", False):
        print("frozen 安装形态无解释器可建 venv——请使用案 A 预打包件"
              "（下载+sha256 pin 自动安装）；pip/源码形态可用 "
              "--provider venv。")
        return 3
    root = runtime_root()
    if _probe_runtime_python():
        print("运行时已存在: " + root + "（重装请先手动删除该目录）")
        return 1
    base = sys.executable
    print("[1/3] 创建 venv: " + root)
    proc = subprocess.run(_venv_create_cmd(base, root), env=_pip_env(), shell=False,
                          creationflags=_SPAWN_FLAGS)
    if proc.returncode != 0:
        print("venv 创建失败 rc=" + str(proc.returncode))
        return proc.returncode
    py = runtime_python()
    mirrors: tuple[tuple[str, list[str]], ...] = (
        ("清华镜像", ["-i", "https://pypi.tuna.tsinghua.edu.cn/simple"]),
        ("官方源", []))
    for label, index_args in mirrors:
        print("[2/3] 安装全钉依赖（" + label + "）: " + ", ".join(PINNED_DEPS))
        proc = subprocess.run(_pip_install_cmd(py, index_args), env=_pip_env(),
                              shell=False, creationflags=_SPAWN_FLAGS)
        if proc.returncode == 0:
            break
        print(label + " 安装失败 rc=" + str(proc.returncode) + "，尝试下一镜像")
    else:
        print("全部镜像安装失败；运行时目录保留供排查: " + root)
        return proc.returncode if proc.returncode else 1
    print("[3/3] 自检")
    ok, detail = selfcheck()
    print(detail)
    return 0 if ok else 1


def _sha256_of(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _guarded_download(url: str, dest: str, expected_sha256: str,
                      expected_bytes: int = 0, progress=None) -> None:
    """守卫下载（复用 dict_manager 下载原语）+sha256 逐字节核验。

    _http_get 自带：https+域白名单（hf-mirror.com/cas-bridge 在案）、重定向
    逐跳守卫、两跳代理状态机、.part 原子落盘、Content-Length 核验。本函数
    追加 pin 级 sha256 校验（词典链同威胁模型：镜像内容变更即拒载）。"""
    from .dict_manager import DictDownloadError, _http_get, _validate_url
    _validate_url(url)
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    try:
        _http_get(url, dest, progress=progress)
    except DictDownloadError as e:
        raise RuntimeError("下载失败: " + str(e)) from e
    if expected_bytes and os.path.getsize(dest) != expected_bytes:
        raise RuntimeError("尺寸不符: 预期 " + str(expected_bytes) + "B，实得 "
                           + str(os.path.getsize(dest)) + "B")
    got = _sha256_of(dest)
    if got != expected_sha256:
        with contextlib.suppress(OSError):
            os.remove(dest)
        raise RuntimeError("sha256 不符（预期 " + expected_sha256[:16] + "…，实得 "
                           + got[:16] + "…）——镜像件与 pin 不匹配，已删除残件")


def _safe_extract_zip(zip_path: str, dest_dir: str) -> None:
    """防 zip-slip 解包：逐成员校验后落位（运行时/模型 zip 共用）。"""
    import zipfile
    dest_res = pathlib.Path(dest_dir).resolve()
    with zipfile.ZipFile(zip_path) as z:
        for member in z.namelist():
            if member.startswith("/") or os.path.isabs(member):
                raise RuntimeError("zip 成员为绝对路径: " + member)
            norm = member.replace("\\", "/")
            if os.pardir in pathlib.PurePosixPath(norm).parts:
                raise RuntimeError("zip 成员越界: " + member)
            target = (dest_res / norm).resolve()
            if dest_res != target and dest_res not in target.parents:
                raise RuntimeError("zip 成员越出目标目录: " + member)
        z.extractall(dest_dir)


def _verify_zip_layout(zip_path: str) -> None:
    """定稿布局内容清单校验（sha256 之后的第二道门，D2026-1028-04）。

    必含：runtime.json／selfcheck.py／python/python.exe 入口／
    site-packages/ 前缀成员／三个关键依赖标记（faster_whisper/ctranslate2/
    av）。不符即失败，诊断含「布局」。"""
    import zipfile
    with zipfile.ZipFile(zip_path) as z:
        names = [n.replace("\\", "/") for n in z.namelist()]
    name_set = set(names)
    missing: list[str] = [x for x in ("runtime.json", "selfcheck.py",
                                      "python/python.exe")
                          if x not in name_set]
    if not any(n.startswith("site-packages/") for n in names):
        missing.append("site-packages/")
    for dep in ("faster_whisper", "ctranslate2", "av"):
        if not any(n.startswith("site-packages/" + dep + "/") for n in names):
            missing.append("site-packages/" + dep + "/")
    if missing:
        raise RuntimeError(
            "zip 布局不符定稿契约（缺: " + ", ".join(missing) +
            "）——须为 python/ + site-packages/ + runtime.json + selfcheck.py "
            "布局（D2026-1028-04）")


def _write_manifest_after_extract(root: str, zip_sha256: str) -> dict:
    """解包后 manifest 落位核验+回写 zip_sha256（安装器为 manifest 写入方）。

    zip 内自带 runtime.json（构建期定 python_exe/site_packages/layout_version），
    安装器校验字段与落位后补 zip_sha256（zip 自身 sha 在打包期内无法自嵌）。"""
    mpath = os.path.join(root, RUNTIME_MANIFEST_NAME)
    try:
        data = json.loads(pathlib.Path(mpath).read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise RuntimeError("解包产物缺 " + RUNTIME_MANIFEST_NAME
                           + " 或非合法 JSON——布局契约不符") from e
    if not isinstance(data, dict) \
            or data.get("layout_version") != RUNTIME_LAYOUT_VERSION:
        raise RuntimeError(RUNTIME_MANIFEST_NAME
                           + " layout_version 非法——布局契约不符")
    py_rel = data.get("python_exe")
    sp_rel = data.get("site_packages")
    if not py_rel or not sp_rel or os.path.isabs(str(py_rel)) \
            or os.path.isabs(str(sp_rel)):
        raise RuntimeError(RUNTIME_MANIFEST_NAME
                           + " 字段非法（python_exe/site_packages 须相对路径）"
                           "——布局契约不符")
    if not os.path.isfile(os.path.join(root, str(py_rel))):
        raise RuntimeError("python_exe 落位缺失: " + str(py_rel)
                           + "——布局契约不符")
    if not os.path.isdir(os.path.join(root, str(sp_rel))):
        raise RuntimeError("site_packages 落位缺失: " + str(sp_rel)
                           + "——布局契约不符")
    data["zip_sha256"] = zip_sha256
    pathlib.Path(mpath).write_text(
        json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    return data


def _cleanup_install_members(root: str) -> None:
    """布局/manifest 校验失败后清理本次解包引入的顶层成员（只删定稿布局
    四件名，不触 root 下其他内容——如案 C venv 残留的 Scripts/）。"""
    import shutil
    for name in _INSTALL_TOP_MEMBERS:
        p = os.path.join(root, name)
        if os.path.isdir(p):
            shutil.rmtree(p, ignore_errors=True)
        elif os.path.isfile(p):
            with contextlib.suppress(OSError):
                os.remove(p)


def _install_via_zip() -> int:
    """案 A：预打包件守卫下载+sha256 核验+布局清单校验+防 zip-slip 解包
    +manifest 落位+自检（D2026-1028-04 核验门全序）。"""
    root = runtime_root()
    if is_installed():
        print("运行时已存在: " + root + "（重装请先手动删除该目录）")
        return 1
    if not (RUNTIME_ZIP_URL and RUNTIME_ZIP_SHA256):
        print("案 A 预打包运行时件尚未发布（缺 URL/sha256 pin）；"
              "pip/源码形态可用降级路径：install --provider venv")
        return 3
    tmp_zip = paths.data_subdir("runtime", "ct2-runtime.zip.part.tmp")
    try:
        print("[1/4] 守卫下载运行时件（" + format(RUNTIME_ZIP_BYTES / 1048576, ".0f")
              + "MB）")
        _guarded_download(RUNTIME_ZIP_URL, tmp_zip, RUNTIME_ZIP_SHA256,
                          RUNTIME_ZIP_BYTES)
        print("[2/4] sha256 核验通过，布局清单校验")
        _verify_zip_layout(tmp_zip)
        print("[3/4] 布局校验通过，解包到 " + root)
        _safe_extract_zip(tmp_zip, root)
        _write_manifest_after_extract(root, RUNTIME_ZIP_SHA256)
    except RuntimeError as e:
        _cleanup_install_members(root)
        print("运行时安装失败: " + str(e))
        return 1
    with contextlib.suppress(OSError):
        os.remove(tmp_zip)
    print("[4/4] 自检")
    ok, detail = selfcheck()
    print(detail)
    return 0 if ok else 1


def download_model(model: str = "large-v2", progress=None) -> int:
    """CT2 模型 zip 守卫下载+核验+解包到 models/ct2/<model>（verified 门）。"""
    entry = next((m for m in CT2_MODELS if m["model"] == model), None)
    if entry is None:
        print("未知 ct2 模型: " + model)
        return 2
    if not entry.get("verified"):
        print("模型件未经生产路径实下载核验（verified=False），下载门未开——"
              "沿词典链上架门纪律，镜像上传后核验翻转即可用")
        return 3
    dest_model_dir = os.path.join(ct2_model_dir(), model)
    if os.path.isdir(dest_model_dir) and os.path.isfile(
            os.path.join(dest_model_dir, "model.bin")):
        print("模型已落位: " + dest_model_dir)
        return 1
    zip_path = paths.data_subdir("models", "ct2", model + "-ct2.zip.tmp")
    print("[1/3] 守卫下载模型件（" + format(int(entry["bytes"]) / 1048576, ".0f")
          + "MB）")
    _guarded_download(str(entry["url"]), zip_path, str(entry["sha256"]),
                      int(entry["bytes"]), progress=progress)
    print("[2/3] sha256 核验通过，解包到 " + dest_model_dir)
    _safe_extract_zip(zip_path, dest_model_dir)
    with contextlib.suppress(OSError):
        os.remove(zip_path)
    print("[3/3] 落位核验")
    if not os.path.isfile(os.path.join(dest_model_dir, "model.bin")):
        print("解包后缺 model.bin——镜像件结构异常")
        return 1
    print("模型就绪: " + dest_model_dir)
    return 0


def install(provider: str = "auto") -> int:
    if provider == "auto":
        provider = "zip" if (RUNTIME_ZIP_URL and RUNTIME_ZIP_SHA256) else "venv"
        print("provider=auto → " + provider)
    if provider == "zip":
        return _install_via_zip()
    if provider == "venv":
        return _install_via_venv()
    print("未知 provider: " + provider + "（可用 auto|zip|venv）")
    return 2


# ---------------------------------------------------------------------------
# 异步操作面（api 桥消费；GUI 接线待钉⑤解冻提案，见 D2026-1028-03 脱钩轮）
# ---------------------------------------------------------------------------

_OP_LOCK = threading.Lock()
_OP_STATE: dict = {"phase": "idle", "kind": "", "detail": "", "rc": None}


def operation_progress() -> dict:
    """当前异步操作快照（phase ∈ idle/running/done/failed；只读零副作用）。"""
    with _OP_LOCK:
        return dict(_OP_STATE)


def _set_op(phase: str, kind: str = "", detail: str = "", rc: object = None) -> None:
    with _OP_LOCK:
        _OP_STATE.update(phase=phase, kind=kind, detail=detail, rc=rc)


def start_install(provider: str = "auto") -> dict:
    """后台线程执行运行时安装（api 桥入口；重复启动拒绝）。"""
    with _OP_LOCK:
        if _OP_STATE["phase"] == "running":
            return {"started": False, "reason": "已有 ct2 安装任务在跑"}
        _OP_STATE.update(phase="running", kind="install", detail="", rc=None)

    def _run() -> None:
        try:
            rc = install(provider)
            _set_op("done" if rc == 0 else "failed", "install", rc=rc)
        except Exception as e:      # noqa: BLE001 线程兜底
            _set_op("failed", "install", detail=str(e), rc=1)

    threading.Thread(target=_run, daemon=True, name="ct2-install").start()
    return {"started": True, "provider": provider}


def start_model_download(model: str = "large-v2") -> dict:
    """后台线程执行模型下载（verified 门在 download_model 内）。"""
    with _OP_LOCK:
        if _OP_STATE["phase"] == "running":
            return {"started": False, "reason": "已有 ct2 任务在跑"}
        _OP_STATE.update(phase="running", kind="model", detail="", rc=None)

    def _run() -> None:
        try:
            rc = download_model(model)
            _set_op("done" if rc == 0 else "failed", "model", rc=rc)
        except Exception as e:      # noqa: BLE001 线程兜底
            _set_op("failed", "model", detail=str(e), rc=1)

    threading.Thread(target=_run, daemon=True, name="ct2-model-dl").start()
    return {"started": True, "model": model}


def ct2_runner_command(media_path: str, srt_out: str, model: str = "large-v2",
                       model_dir: str = "", *, beam_size: int = 5,
                       vad_filter: bool = True, condition_previous: bool = False) -> list[str]:
    """ct2 整片转写命令构造（runtime python + runner 脚本直调）。

    runner 脚本=asr_env._runner_script_path()（frozen/dev 双形态既有解析），
    运行时 venv 无需安装本项目包（runner 设计为上游环境独立脚本）。
    四旋钮缺省=PROVISIONAL（待金标 A/B 预注册定案）。"""
    from .asr_env import _runner_script_path
    cmd = [runtime_python(), _runner_script_path(),
           "--engine", "ct2", "--media", media_path, "--srt-out", srt_out,
           "--model", model, "--language", "ja"]
    if model_dir:
        cmd.append("--model-dir")
        cmd.append(model_dir)
    cmd.append("--beam-size")
    cmd.append(str(beam_size))
    if not vad_filter:
        cmd.append("--no-vad-filter")
    if condition_previous:
        cmd.append("--condition-previous")
    return cmd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m subtransjav.refine.asr_runtime",
        description="CT2 转写引擎自管运行时：install/status/selfcheck")
    sub = parser.add_subparsers(dest="cmd")
    p_install = sub.add_parser("install", help="安装运行时")
    p_install.add_argument("--provider", default="auto", choices=["auto", "zip", "venv"])
    sub.add_parser("status", help="状态快照（JSON）")
    sub.add_parser("selfcheck", help="安装后自检")
    p_dl = sub.add_parser("download-model", help="下载 CT2 模型件（verified 门）")
    p_dl.add_argument("--model", default="large-v2")
    args = parser.parse_args(argv)
    if args.cmd == "install":
        return install(args.provider)
    if args.cmd == "download-model":
        return download_model(args.model)
    if args.cmd == "status":
        print(json.dumps(provider_status(), ensure_ascii=False, indent=2))
        return 0
    if args.cmd == "selfcheck":
        ok, detail = selfcheck()
        print(detail)
        return 0 if ok else 1
    parser.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
