"""CT2 运行时 zip 构建脚本（d1028-36，D2026-1028-04 拍板 B 案升级版）。

产出 d1028-32 §4 定稿布局（python/ + site-packages/ + runtime.json +
selfcheck.py），替代已上传的 embed 平铺件（与 asr_runtime 认证契约
不一致的生产缺陷，见 D2026-1028-04）。

构建源（本机现成材料，配方实录见 d1028-32 报告）：
- --embed：python-embed 官方发行版 zip（python.exe/python312._pth/python312.zip…）
- --site-packages：全钉依赖解包目录（faster-whisper/ctranslate2/av 等关键
  依赖存在性+版本钉断言，与 asr_runtime.PINNED_DEPS 一致）

定稿布局要点：
- python/ 子目录收纳 embed 全件；python312._pth 重写为 ../site-packages
  （embed 在 python/ 内、site-packages 在 zip 根——_pth 相对 python/ 解析）；
- runtime.json 构建期写三字段（layout_version/python_exe/site_packages），
  zip_sha256 由安装器下载核验后回写（zip 自身 sha 无法自嵌）；
- selfcheck.py 契约=asr_runtime.selfcheck：import 全链+版本钉+1s 正弦波
  音频链 rc=0（两处文本须同步维护，改动任一处须联动）。

确定性构建：成员排序+固定时间戳（同输入同 sha256，pin 可复核）。
产物落仓库外（%TEMP%），不进 git 树；HF 上传照 d1028-35 runbook。

用法（项目根执行）：
  python tools/build_ct2_runtime.py
  python tools/build_ct2_runtime.py --embed <zip> --site-packages <dir> \
      --out <zip> --version 1.1.0
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import tempfile
import zipfile

# 与 subtransjav/refine/asr_runtime.py PINNED_DEPS 同步（构建期断言防漂移）
PINNED_DEPS: list[str] = [
    "faster-whisper==1.2.1",
    "ctranslate2==4.8.4",
    "av==13.1.0",
]

RUNTIME_LAYOUT_VERSION = 1

# selfcheck.py 文本（契约=asr_runtime.selfcheck / _SELFHECK_AUDIO_BODY，
# 两处同步维护）；embed python 直跑，site-packages 经 python312._pth 可见
_SELFCHECK_SCRIPT = '''"""CT2 运行时自检脚本（构建期写入；契约=asr_runtime.selfcheck）。

import 全链+版本钉断言+1s 正弦波音频链（模型无关，不下载任何模型）。
"""
import os
import tempfile
import wave

import av
import ctranslate2
import numpy

assert ctranslate2.__version__ == "4.8.4", ctranslate2.__version__
assert av.__version__.startswith("13."), av.__version__

import faster_whisper
from faster_whisper import WhisperModel  # noqa: F401

sr = 16000
t = numpy.arange(sr) / sr
pcm = (0.5 * numpy.sin(2 * numpy.pi * 440.0 * t) * 32767).astype("int16")
fd, path = tempfile.mkstemp(suffix=".wav")
os.close(fd)
try:
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())
    from faster_whisper.audio import decode_audio

    audio = decode_audio(path, sampling_rate=sr)
    assert audio.shape[0] == sr, audio.shape
finally:
    os.remove(path)

print("ct2-runtime-selfcheck OK")
'''

# 定稿布局下的 python312._pth（embed 在 python/ 内、site-packages 在 zip 根；
# _pth 相对 python/ 解析，故 ../site-packages）
_PYTHON_PTH_BODY = "python312.zip\n.\n../site-packages\nimport site\n"


def _verify_embed_zip(path: str) -> None:
    required = ("python.exe", "python312._pth", "python312.zip")
    with zipfile.ZipFile(path) as z:
        names = set(z.namelist())
    missing = [n for n in required if n not in names]
    if missing:
        raise SystemExit("embed.zip 缺成员: " + ", ".join(missing)
                         + "——须为 python-embed 官方发行版原 zip")


def _verify_site_packages(root: str) -> None:
    for pin in PINNED_DEPS:
        dist, version = pin.split("==")
        pkg_dir = dist.replace("-", "_").lower().split(".")[0]
        dist_infos = list(pathlib.Path(root).glob(
            pkg_dir + "-" + version + ".dist-info"))
        if not dist_infos:
            raise SystemExit("site-packages 缺关键依赖: " + pin
                             + "（构建源与 asr_runtime.PINNED_DEPS 不同源）")
    if not pathlib.Path(root, "faster_whisper").is_dir():
        raise SystemExit("site-packages 缺 faster_whisper 包目录")


def _stage_tree(embed_zip: str, site_packages: str, work: str) -> pathlib.Path:
    """staging：embed 解包入 python/、site-packages 复制入 zip 根、写
    python312._pth / runtime.json / selfcheck.py。返回 staging 根。"""
    import shutil
    stage = pathlib.Path(work)
    if stage.exists():
        shutil.rmtree(stage)
    py_dir = stage / "python"
    with zipfile.ZipFile(embed_zip) as z:
        z.extractall(py_dir)
    # _pth 重写：embed 原件指向 Lib/site-packages（平铺假设），定稿布局
    # 下 site-packages 在 zip 根——相对 python/ 为 ../site-packages
    (py_dir / "python312._pth").write_text(_PYTHON_PTH_BODY, encoding="utf-8")
    shutil.copytree(site_packages, stage / "site-packages")
    manifest = {
        "layout_version": RUNTIME_LAYOUT_VERSION,
        "python_exe": "python/python.exe",
        "site_packages": "site-packages",
    }
    (stage / "runtime.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8")
    (stage / "selfcheck.py").write_text(_SELFCHECK_SCRIPT, encoding="utf-8")
    return stage


def _pack_zip(stage: pathlib.Path, out: str) -> tuple[str, int, int]:
    """确定性打包：成员按路径排序+固定时间戳（同输入同 sha256）。"""
    files: list[pathlib.Path] = sorted(
        p for p in stage.rglob("*") if p.is_file())
    count = 0
    h_src = __import__("hashlib").sha256()
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as z:
        for f in files:
            rel = f.relative_to(stage).as_posix()
            data = f.read_bytes()
            h_src.update(data)
            zi = zipfile.ZipInfo(rel, date_time=(1980, 1, 1, 0, 0, 0))
            zi.compress_type = zipfile.ZIP_DEFLATED
            zi.external_attr = 0o644 << 16
            z.writestr(zi, data)
            count += 1
    return h_src.hexdigest(), os.path.getsize(out), count


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="build_ct2_runtime",
        description="CT2 运行时 zip 构建（d1028-32 §4 定稿布局；确定性构建）")
    parser.add_argument("--embed", default=os.path.join(
        tempfile.gettempdir(), "ct2-stage", "runtime-build", "embed.zip"),
        help="python-embed 官方发行版 zip 路径")
    parser.add_argument("--site-packages", default=os.path.join(
        os.environ.get("LOCALAPPDATA", str(pathlib.Path.home())),
        "SubTrans", "runtime", "ct2", "Lib", "site-packages"),
        help="全钉依赖 site-packages 目录（构建源）")
    parser.add_argument("--out", default="", help="输出 zip 路径"
                        "（默认 %%TEMP%%/ct2-stage/subtrans-ct2-runtime-"
                        "<ver>-win64.zip）")
    parser.add_argument("--version", default="1.1.0",
                        help="运行时件版本号（进输出文件名与 URL 面）")
    parser.add_argument("--work", default="",
                        help="staging 工作目录（默认系统临时目录内自建）")
    args = parser.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")

    if not os.path.isfile(args.embed):
        raise SystemExit("embed.zip 不存在: " + args.embed)
    if not os.path.isdir(args.site_packages):
        raise SystemExit("site-packages 目录不存在: " + args.site_packages)
    _verify_embed_zip(args.embed)
    _verify_site_packages(args.site_packages)

    out = args.out or os.path.join(
        tempfile.gettempdir(), "ct2-stage",
        "subtrans-ct2-runtime-" + args.version + "-win64.zip")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    work = args.work or os.path.join(
        tempfile.gettempdir(), "ct2-stage", "build-work-" + args.version)

    print("[1/2] staging（embed 解包+site-packages 复制+契约文件写入）…")
    stage = _stage_tree(args.embed, args.site_packages, work)
    print("[2/2] 确定性打包 → " + out)
    content_sha, out_bytes, members = _pack_zip(stage, out)

    print("=" * 72)
    print("构建实录（d1028-32 §4 定稿布局）")
    print("  产物: " + out)
    print("  bytes: " + str(out_bytes))
    print("  sha256: " + content_sha)
    print("  members: " + str(members))
    print("  embed: " + args.embed)
    print("  site-packages: " + args.site_packages)
    print("  pins: " + ", ".join(PINNED_DEPS))
    print("  目标 <200MB: " + ("满足" if out_bytes < 200 * 1048576 else "超出"))
    print("-" * 72)
    print("asr_runtime.py pin 回填行：")
    print('RUNTIME_ZIP_URL = ("https://hf-mirror.com/Angelholl/subtrans-ct2-runtime"')
    print('                   "/resolve/main/subtrans-ct2-runtime-'
          + args.version + '-win64.zip")')
    print('RUNTIME_ZIP_SHA256 = "' + content_sha + '"')
    print("RUNTIME_ZIP_BYTES = " + str(out_bytes))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
