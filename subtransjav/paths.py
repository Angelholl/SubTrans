"""
数据路径单一来源（打包地基批 D2026-0929-06 修订①/⑧ + 07/08 定案）
====================================================================
源码/pip 形态下所有锚点解析结果与历史行为逐字节一致（硬验收）；
frozen（PyInstaller）形态下一切旧"仓库根"写入语义改为用户数据根。

本模块只依赖标准库（os/sys/pathlib），禁止 import 项目内其他模块，
防止循环依赖（config/tm/secrets 等模块级常量在其 import 期即调用本模块）。
"""

import os
import sys
from pathlib import Path


def is_frozen() -> bool:
    """canonical frozen 判定：全库内联 ``getattr(sys, "frozen", False)`` 收拢到此。"""
    return getattr(sys, "frozen", False)


def app_root() -> Path:
    """源码形态 = 仓库根（subtransjav/paths.py 的 parents[1]）。

    frozen 形态 = 数据根（frozen 下旧"仓库根"写入语义一律改落数据根，
    不碰安装目录，D2026-0929-08）。
    """
    if is_frozen():
        return data_root()
    return Path(__file__).resolve().parents[1]


def data_root() -> Path:
    """数据根目录，三级优先级：

    1. 环境变量 ``SUBTRANSJAV_DATA_ROOT``（非空才生效）；
    2. frozen → ``%LOCALAPPDATA%\\SubTransJAV``（LOCALAPPDATA 缺失回退家目录，
       不抛异常）；
    3. 否则 = app_root()（源码形态，行为与现状逐字节一致）。
    """
    env = os.environ.get("SUBTRANSJAV_DATA_ROOT", "").strip()
    if env:
        return Path(env)
    if is_frozen():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "SubTransJAV"
    return app_root()


def data_root_source() -> str:
    """数据根来源标识：``"env"`` / ``"frozen-default"`` / ``"legacy"``。"""
    if os.environ.get("SUBTRANSJAV_DATA_ROOT", "").strip():
        return "env"
    if is_frozen():
        return "frozen-default"
    return "legacy"


def data_subdir(*parts: str) -> str:
    """str(data_root() / parts)，供各锚点替换；返回字符串保持 os.path.join 语义。"""
    return str(data_root().joinpath(*parts))


# 完整迁移逻辑随 EXE 首发另批实现，本批只做状态读取。
MIGRATION_SENTINEL = ".migration-complete"

# 旧位（pip/源码形态数据）保留期下限：≥ 1.4.1 EOL 声明时点
# （D2026-0929-05 R4 / D2026-0929-08 点 3）。当前为占位值，最终由发布文档
# EOL 字段定值驱动（1.4.1 EOL 声明随通道启用写入 release notes 后回填）；
# 未来的旧位清理逻辑读本常量判断是否到期，而非"保留 N 版"
# （字面量 = EOL 声明时点，非版本计数）。
LEGACY_RETENTION_EOL = "2027-06-30"


def migration_state() -> str:
    """迁移状态：数据根存在哨兵 → ``"migrated"``，否则 ``"not-migrated"``。"""
    if (data_root() / MIGRATION_SENTINEL).exists():
        return "migrated"
    return "not-migrated"
