"""
模型缓存路径管理：把 HF / ModelScope / Torch / Whisper 的下载缓存
重定向到仓库根目录 models/ 下，避免占用 C 盘用户目录空间。

用法（在进程早期调用一次，子进程会继承环境变量）：
    from subtransjav.utils.model_cache import apply_model_cache_env
    apply_model_cache_env()
"""

import os
from pathlib import Path

from subtransjav import paths


def project_models_root() -> Path:
    """模型缓存根目录：仓库根/models（源码运行）或数据根/models（打包）"""
    # frozen 打包 → 数据根（不碰安装目录，D2026-0929-08）；
    # 源码运行：subtransjav/utils/model_cache.py → 仓库根
    root = paths.data_root() / "models" if paths.is_frozen() else Path(__file__).resolve().parents[2]
    return root / "models"


_ENV_MAP = {
    "HF_HOME": "hf",                 # huggingface_hub（faster-whisper/qwen/kotoba 模型）
    "MODELSCOPE_CACHE": "modelscope",  # ZipEnhancer 等 ModelScope 模型
    "TORCH_HOME": "torch",           # torch hub
    "CACHE_ROOT": "whisper",         # openai-whisper 官方库识别此变量
    "XDG_CACHE_HOME": "xdg",         # crispasr 等遵循 XDG 的组件
}

# 国内 HF 镜像：解决 huggingface.co 直连挂起/被墙导致的模型下载卡死
HF_ENDPOINT_MIRROR = "https://hf-mirror.com"


def apply_model_cache_env(force: bool = False) -> str:
    """把各模型缓存环境变量指向项目目录（setdefault 语义，不覆盖用户显式设置）"""
    root = project_models_root()
    root.mkdir(parents=True, exist_ok=True)
    for env, sub in _ENV_MAP.items():
        target = str(root / sub)
        if force or not os.environ.get(env):
            os.environ[env] = target
    # HF 站点镜像（国内网络防卡死）；用户显式设置的优先
    if not os.environ.get("HF_ENDPOINT"):
        os.environ["HF_ENDPOINT"] = HF_ENDPOINT_MIRROR
    return str(root)
