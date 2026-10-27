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

from .. import paths
from ..utils.subprocess_flags import CREATE_NO_WINDOW

__all__ = [
    "PINNED_DEPS",
    "RUNTIME_ZIP_URL",
    "RUNTIME_ZIP_SHA256",
    "CT2_MODELS",
    "runtime_root",
    "runtime_python",
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
                   "/resolve/main/subtrans-ct2-runtime-1.0.0-win64.zip")
RUNTIME_ZIP_SHA256 = "c0eb408fc4404cb96c35faaede4b149398880c169d9c9e01db7dc23104daf1bb"
RUNTIME_ZIP_BYTES = 106267550

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


def runtime_root() -> str:
    """运行时落位：数据根 runtime/ct2（user_dirs 体系内，随数据根迁移）。"""
    return paths.data_subdir("runtime", "ct2")


def runtime_python() -> str:
    return os.path.join(runtime_root(), "Scripts", "python.exe")


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


def is_installed() -> bool:
    py = runtime_python()
    return bool(py) and os.path.isfile(py)


_SELFHECK_SNIPPET = (
    "import ctranslate2, av\n"
    "assert ctranslate2.__version__ == '4.8.4', ctranslate2.__version__\n"
    "assert av.__version__.startswith('13.'), av.__version__\n"
    "import faster_whisper\n"
    "from faster_whisper import WhisperModel  # noqa: F401\n"
    "print('ct2-runtime-selfcheck OK')\n"
)


def selfcheck() -> tuple[bool, str]:
    """运行时自检：导入链+版本钉断言（模型无关，不下载任何模型）。"""
    if not is_installed():
        return False, "运行时未安装（" + runtime_root() + " 无 python.exe）"
    cmd = [runtime_python(), "-c", _SELFHECK_SNIPPET]
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
    """状态快照（GUI/CLI 双消费）。"""
    ok, detail = selfcheck() if is_installed() else (False, "未安装")
    return {
        "installed": is_installed(),
        "python": runtime_python() if is_installed() else "",
        "selfcheck": "pass" if ok else "fail",
        "detail": detail,
        "zip_published": bool(RUNTIME_ZIP_URL and RUNTIME_ZIP_SHA256),
        "pinned_deps": list(PINNED_DEPS),
        "models": CT2_MODELS,
    }


def _pip_env() -> dict:
    env = dict(os.environ)
    env.setdefault("PYTHONUTF8", "1")
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
    """案 C：现场 venv+pip 装全钉依赖（spike 全链实证；仅非 frozen 形态）。"""
    if getattr(sys, "frozen", False):
        print("frozen 安装形态无解释器可建 venv——请使用案 A 预打包件"
              "（当前未发布，待镜像上传+pin）；pip/源码形态可用 "
              "--provider venv。")
        return 3
    root = runtime_root()
    if is_installed():
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


def _install_via_zip() -> int:
    """案 A：预打包件守卫下载+sha256 核验+防 zip-slip 解包+自检。"""
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
        print("[1/3] 守卫下载运行时件（" + format(RUNTIME_ZIP_BYTES / 1048576, ".0f")
              + "MB）")
        _guarded_download(RUNTIME_ZIP_URL, tmp_zip, RUNTIME_ZIP_SHA256,
                          RUNTIME_ZIP_BYTES)
        print("[2/3] sha256 核验通过，解包到 " + root)
        _safe_extract_zip(tmp_zip, root)
    except RuntimeError as e:
        print("运行时安装失败: " + str(e))
        return 1
    with contextlib.suppress(OSError):
        os.remove(tmp_zip)
    print("[3/3] 自检")
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
