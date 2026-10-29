#!/usr/bin/env python3
"""GPU DLL 补丁包确定性构建（件B，D2026-1029-02 拍板③；勘探卡 §6）。

用法（项目根目录执行）：
  python tools/build_gpu_patch.py \
    --cublas-wheel <nvidia_cublas_cu12-12.8.5.5-...whl> \
    --cudnn-wheel <nvidia_cudnn_cu12-9.19.0.56-...whl> \
    --out artifacts/gpu-patch/subtrans-gpu-dll-patch-1.0.0-win64.zip

- 输入=双 nvidia 官方 win_amd64 wheel（sha256 构建期核验，版本锁死）；
- 输出=确定性 zip（固定时间戳/排序，可复现）：10 DLL 平铺＋
  gpu_patch_manifest.json（wheel 版本＋逐 DLL sha256 清单＋构建时间）；
- 落位契约=asr_runtime._verify_gpu_patch_layout 消费面；
- pin 回填=asr_runtime.GPU_PATCH_ZIP_SHA256/BYTES（上传 HF 镜像后由 owner
  点亮 URL——上传闸=owner HF token）；
- 许可：wheel 内许可证文本随包附（license/ 目录），分发合规面由 owner
  按 cuDNN SLA／CUDA EULA 复核后随发布资产定稿。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import zipfile

# pin：与 asr_runtime/勘探卡 §2 同源锁死（跨小版本差异须先组合冒烟）
CUBLAS_PIN = {
    "wheel": "nvidia_cublas_cu12-12.8.5.5-py3-none-win_amd64.whl",
    "version": "12.8.5.5",
    # 2026-10-29 构建实录核验（PyPI 官方件实下载）
    "sha256": "1e272895b82946b4db6f592d9080291fb60f78c9fe253a5c71ba5ebb74864c3e",
}
CUDNN_PIN = {
    "wheel": "nvidia_cudnn_cu12-9.19.0.56-py3-none-win_amd64.whl",
    "version": "9.19.0.56",
    "sha256": "cec70596b9ce878fab83810c3f5a2e606d35f510e5fee579759e4cbc68a23750",
}
GPU_DLL_REQUIRED = (
    "cublas64_12.dll", "cublasLt64_12.dll",
    "cudnn64_9.dll", "cudnn_adv64_9.dll", "cudnn_cnn64_9.dll",
    "cudnn_engines_precompiled64_9.dll",
    "cudnn_engines_runtime_compiled64_9.dll",
    "cudnn_graph64_9.dll", "cudnn_heuristic64_9.dll",
    "cudnn_ops64_9.dll",
)
CUBLAS_DLLS = ("cublas64_12.dll", "cublasLt64_12.dll")
CUDNN_DLL_PREFIXES = tuple(n[:-4] for n in GPU_DLL_REQUIRED if n not in CUBLAS_DLLS)
# 确定性 zip 时间戳（1980-01-01，zipfile 下限）
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def sha256_of(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def collect_dlls(wheel: pathlib.Path, wanted: tuple[str, ...]) -> dict[str, bytes]:
    """从 wheel 抽取指定 DLL（nvidia wheel 布局 nvidia/<pkg>/bin/ 递归搜）。"""
    out: dict[str, bytes] = {}
    with zipfile.ZipFile(wheel) as z:
        for name in z.namelist():
            base = name.replace("\\", "/").rsplit("/", 1)[-1]
            if base in wanted and base not in out:
                out[base] = z.read(name)
    return out


def collect_licenses(wheel: pathlib.Path) -> bytes | None:
    """抽取 wheel 内随包许可文本（NVIDIA 许可随包附义务，勘探卡 §6）。"""
    with zipfile.ZipFile(wheel) as z:
        for name in z.namelist():
            n = name.replace("\\", "/")
            if "dist-info/licenses/" in n and n.lower().endswith(".txt"):
                return z.read(name)
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="build_gpu_patch")
    ap.add_argument("--cublas-wheel", required=True)
    ap.add_argument("--cudnn-wheel", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--built-at", default="")
    args = ap.parse_args(argv)

    cublas_w = pathlib.Path(args.cublas_wheel)
    cudnn_w = pathlib.Path(args.cudnn_wheel)
    for w, pin in ((cublas_w, CUBLAS_PIN), (cudnn_w, CUDNN_PIN)):
        if w.name != pin["wheel"]:
            print(f"wheel 文件名与 pin 不符: {w.name} != {pin['wheel']}")
            return 2
        print(f"{pin['wheel']} sha256={sha256_of(w)}")
        if pin["sha256"] and sha256_of(w) != pin["sha256"]:
            print("wheel sha256 与 pin 不符: " + w.name)
            return 2

    dlls: dict[str, bytes] = {}
    dlls.update(collect_dlls(cublas_w, CUBLAS_DLLS))
    dlls.update(collect_dlls(cudnn_w, tuple(GPU_DLL_REQUIRED)))
    missing = [d for d in GPU_DLL_REQUIRED if d not in dlls]
    if missing:
        print("wheel 内缺 DLL: " + ", ".join(missing))
        return 1

    lic_cublas = collect_licenses(cublas_w)
    lic_cudnn = collect_licenses(cudnn_w)
    if lic_cublas is None or lic_cudnn is None:
        print("wheel 内缺许可文本（licenses/License.txt）——拒绝构建"
              "（NVIDIA 许可随包附义务）")
        return 1
    manifest = {
        "schema": "subtransjav.gpu_patch/1",
        "built_at": args.built_at,
        "wheel_versions": {"nvidia-cublas-cu12": CUBLAS_PIN["version"],
                           "nvidia-cudnn-cu12": CUDNN_PIN["version"]},
        "dlls": {d: hashlib.sha256(b).hexdigest() for d, b in dlls.items()},
    }
    extra = {"licenses/License-cublas-cu12.txt": lic_cublas,
             "licenses/License-cudnn-cu12.txt": lic_cudnn}
    out = pathlib.Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(list(dlls) + list(extra)
                           + ["gpu_patch_manifest.json"]):
            info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            if name.endswith(".json"):
                data = json.dumps(manifest, ensure_ascii=False,
                                  indent=1).encode("utf-8")
            elif name in extra:
                data = extra[name]
            else:
                data = dlls[name]
            z.writestr(info, data)
    print("产物: " + str(out))
    print("bytes=" + str(out.stat().st_size))
    print("sha256=" + sha256_of(out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
