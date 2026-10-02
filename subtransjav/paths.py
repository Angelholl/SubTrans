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


def normalize_path_case(path: str) -> str:
    """路径大小写归一化（Windows 语义跨平台对齐）。

    ``os.path.normcase`` 仅在 Windows 折叠大小写，POSIX 上是 no-op；
    本项目为 Windows-only，大小写不敏感配对是既定设计语义，故显式
    ``.lower()`` 补齐跨平台一致性。``abspath`` 先行保证相对路径的
    解析基准一致。斜杠方向统一为正斜杠（normcase 之后 replace，Windows
    下 normcase 已折叠斜杠、再 replace 幂等无害；POSIX 下把反斜杠
    转为正斜杠使正反斜杠两变体归一后相等）。

    注意：2.0.0b0 期间哈希口径统一（斜杠表示改变），依赖本函数指纹的
    旧 manifest 断点会一次性失配，需 ``--force-resume`` 恢复。
    """
    return os.path.normcase(os.path.abspath(path)).lower().replace("\\", "/")


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


POINTER_FILENAME = ".data-root"


def _data_root_pointer_path() -> Path:
    """pointer 文件固定位置（先找到先算的唯一候选）：

    frozen → exe 同目录（``Path(sys.executable).parent``）；
    源码 → app_root()（即仓库根）。
    """
    if is_frozen():
        return Path(sys.executable).parent / POINTER_FILENAME
    return Path(__file__).resolve().parents[1] / POINTER_FILENAME


def _read_data_root_pointer() -> str:
    """读 pointer：存在且内容为单行绝对路径才生效，否则忽略（容错）。"""
    p = _data_root_pointer_path()
    try:
        if not p.is_file():
            return ""
        content = p.read_text(encoding="utf-8").strip()
    except OSError:
        return ""
    if not content or not os.path.isabs(content):
        return ""
    return content


def data_root() -> Path:
    """数据根目录，四级优先级：

    1. 环境变量 ``SUBTRANSJAV_DATA_ROOT``（非空才生效）；
    2. pointer 文件 ``.data-root``（单行绝对路径；不存在/为空/非法则忽略）；
    3. frozen → ``%LOCALAPPDATA%\\SubTransJAV``（LOCALAPPDATA 缺失回退家目录，
       不抛异常）；
    4. 否则 = app_root()（源码形态，行为与现状逐字节一致）。

    注意：各模块级常量在 import 期已求值，pointer 修改须重启应用生效。
    """
    env = os.environ.get("SUBTRANSJAV_DATA_ROOT", "").strip()
    if env:
        return Path(env)
    pointer = _read_data_root_pointer()
    if pointer:
        return Path(pointer)
    if is_frozen():
        base = os.environ.get("LOCALAPPDATA") or str(Path.home())
        return Path(base) / "SubTransJAV"
    return app_root()


def data_root_source() -> str:
    """数据根来源标识：``"env"`` / ``"pointer"`` / ``"frozen-default"`` / ``"legacy"``。"""
    if os.environ.get("SUBTRANSJAV_DATA_ROOT", "").strip():
        return "env"
    if _read_data_root_pointer():
        return "pointer"
    if is_frozen():
        return "frozen-default"
    return "legacy"


def get_data_root_pointer() -> str:
    """当前 pointer 指向（无 pointer / pointer 无效时返回空串）。"""
    return _read_data_root_pointer()


def set_data_root_pointer(path: str) -> tuple[bool, str]:
    """写/清除 pointer 文件。

    path 为空串 = 清除 pointer，恢复默认（返回 (True, 默认数据根)）；
    否则写单行绝对路径（utf-8）。写前确保 pointer 所在目录存在。

    返回 (成功?, 新数据根或错误信息)。
    """
    target = (path or "").strip()
    try:
        if not target:
            p = _data_root_pointer_path()
            if p.exists():
                p.unlink()
            return True, str(data_root())
        if not os.path.isabs(target):
            return False, str(Path(target))
        new_root = str(Path(target))
        p = _data_root_pointer_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            f.write(new_root + "\n")
        return True, new_root
    except OSError as e:
        return False, f"{type(e).__name__}: {e}"


GUIDE_SENTINEL_FILENAME = ".data-guide-done"


def data_guide_sentinel_path() -> Path:
    """首启数据目录引导哨兵位置（批1b 件4）：与 .data-root 指针同位——

    frozen → exe 同目录（``Path(sys.executable).parent``）；
    源码 → 仓库根（app_root 前身锚，源码形态引导 no-op，哨兵不落地）。

    与数据根解耦是刻意裁定：哨兵若落数据根，首次改数据根后新根无哨兵
    会再次弹窗骚扰；exe 同目录随安装生命周期只写一次。
    """
    if is_frozen():
        return Path(sys.executable).parent / GUIDE_SENTINEL_FILENAME
    return Path(__file__).resolve().parents[1] / GUIDE_SENTINEL_FILENAME


def data_subdir(*parts: str) -> str:
    """str(data_root() / parts)，供各锚点替换；返回字符串保持 os.path.join 语义。"""
    return str(data_root().joinpath(*parts))


# 完整迁移逻辑随 EXE 首发另批实现，本批只做状态读取。
MIGRATION_SENTINEL = ".migration-complete"

# 旧位（pip/源码形态数据）保留期下限：≥ 1.4.1 EOL 声明时点
# （D2026-0929-05 R4 / D2026-0929-08 点 3）。值已由 owner 终裁定版
# （D2026-0930-03 ⑤）：到达 EOL 后旧版停止修补、旧位数据保留可用；
# 未来的旧位清理逻辑读本常量判断是否到期，而非"保留 N 版"
# （字面量 = EOL 声明时点，非版本计数）。
LEGACY_RETENTION_EOL = "2027-06-30"


def migration_state() -> str:
    """迁移状态：数据根存在哨兵 → ``"migrated"``，否则 ``"not-migrated"``。"""
    if (data_root() / MIGRATION_SENTINEL).exists():
        return "migrated"
    return "not-migrated"
