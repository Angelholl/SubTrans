"""环境变量双前缀兼容层（D2026-1106-02 ①：包名 subtransjav→subtrans）。

SUBTRANS_* 优先、SUBTRANSJAV_* 兜底：存量用户脚本/CI/本地工具的旧前缀
设置零破坏。本模块只依赖标准库（os），无项目内依赖，可被任何层安全导入。

口径：SUBTRANS_<name> 存在即生效（含空串；空串按各调用点原语义处理，
与单前缀时代同构）——显式设置优先后备，与数据根 pointer 收养语义同型。
"""

from __future__ import annotations

import os

NEW_PREFIX = "SUBTRANS_"
LEGACY_PREFIX = "SUBTRANSJAV_"


def env_get(name: str) -> str | None:
    """双前缀 env 读取：SUBTRANS_<name> 优先，SUBTRANSJAV_<name> 兜底。

    返回 None = 两前缀均未设置；空串=设置但空（调用方按原语义 strip/判空）。
    """
    new = os.environ.get(NEW_PREFIX + name)
    if new is not None:
        return new
    return os.environ.get(LEGACY_PREFIX + name)
