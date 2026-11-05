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
    """源码形态 = 仓库根（subtrans/paths.py 的 parents[1]）。

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


# ---------------------------------------------------------------------------
# frozen 数据根默认推导（D2026-1103-05 项②：默认离 C，落点 A）
# 显式取代 D2026-1002-12 点 4（新装默认维持 LOCALAPPDATA）。推导规则单一规格：
# paths.py 与 packaging/setup.iss 各实现一次，形态对照表由 tests 钉住
# （tests/test_paths.py 对照表钉 + tests/test_installer_lifecycle.py iss 面钉）。
# ---------------------------------------------------------------------------
DATA_ROOT_SUFFIX = "-data"
DISK_ROOT_DATA_NAME = "SubTrans-data"

# 用户数据锚点（相对数据根）：与 packaging/setup.iss ``HasAnyAnchor`` 十锚逐条
# 一致（tests/test_paths.py 对照钉）；data_migration.py 迁移白名单（8 项）是
# 本集合的子集——白名单只列「可搬移文件」，本集合还含 templates 目录与
# user_dirs.json 等「有即算有用户数据」的判定锚（改任一须同步对照钉）。
DATA_ANCHORS: tuple[str, ...] = (
    "config/user_dirs.json",
    "config/user_settings.json",
    "config/refine_stage_settings.json",
    "config/api_keys.bin",
    "config/glossary.csv",
    "config/glossary_learned.csv",
    "config/fullchain_c22.json",
    "config/templates",
    "Temp/translation_memory/tm.db",
    "Temp/translation_memory/glossary_conflict_watch.json",
)


def install_dir() -> Path:
    """安装目录：frozen = exe 同目录；源码形态 = 仓库根（不参与默认推导）。"""
    if is_frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def default_data_root_for(base_install_dir: Path) -> Path:
    """落点 A 单一推导规格：``<安装目录父>\\<安装目录名>-data``。

    安装目录为盘符根（``D:\\`` / ``C:\\``）时回退 ``<盘符>:\\SubTrans-data``，
    绝不推出 ``D:\\`` 或 ``D:\\-data``。名字已以 ``-data`` 结尾时得双后缀
    （``D:\\SubTrans-data`` → ``D:\\SubTrans-data-data``）——刻意保持规则单一，
    换取「推导结果恒不等于安装目录」这一硬不变量：数据根落在安装目录内
    既违 D2026-0929-06 守卫、又在 Program Files 不可写，且正是 10-30
    卸载数据事故的前提（critic HRO-2）。
    """
    d = Path(base_install_dir)
    parent = d.parent
    if parent == d:  # 盘符根（含 UNC 服务根）
        return Path(d.drive + "\\") / DISK_ROOT_DATA_NAME
    return parent / (d.name + DATA_ROOT_SUFFIX)


def legacy_default_data_root() -> Path:
    """旧 frozen 默认位（3.1.1 及以前）：``%LOCALAPPDATA%\\SubTrans``，缺失回退家目录。"""
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "SubTrans"


def has_data_anchors(root: Path) -> bool:
    """root 内是否命中任一用户数据锚点（iss ``HasAnyAnchor`` 同口径）。"""
    r = Path(root)
    if not r.is_dir():
        return False
    return any(r.joinpath(*Path(a).parts).exists() for a in DATA_ANCHORS)


def _frozen_default_resolution() -> tuple[Path, str]:
    """frozen 无 env 无 pointer 时的默认数据根与来源标签（含旧根收养）。

    收养序（护栏 6）：新默认有锚点 → 用新默认；否则旧 ``%LOCALAPPDATA%\\SubTrans``
    有锚点 → 仍用旧根（标签 ``frozen-legacy-default``，不静默迁移）；
    否则用新默认（标签 ``frozen-default``）。
    """
    new_root = default_data_root_for(install_dir())
    if has_data_anchors(new_root):
        return new_root, "frozen-default"
    old_root = legacy_default_data_root()
    if old_root != new_root and has_data_anchors(old_root):
        return old_root, "frozen-legacy-default"
    return new_root, "frozen-default"


def data_root() -> Path:
    """数据根目录，四级优先级：

    1. 环境变量 ``SUBTRANS_DATA_ROOT``（非空才生效）；
    2. pointer 文件 ``.data-root``（单行绝对路径；不存在/为空/非法则忽略）；
    3. frozen → 落点 A 默认 ``<安装目录父>\\<安装目录名>-data``（默认离 C，
       D2026-1103-05 项②；旧 ``%LOCALAPPDATA%\\SubTrans`` 有数据且新默认无
       数据时收养旧根）；
    4. 否则 = app_root()（源码形态，行为与现状逐字节一致）。

    注意：各模块级常量在 import 期已求值，pointer 修改须重启应用生效。
    """
    env = os.environ.get("SUBTRANS_DATA_ROOT", "").strip()
    if env:
        return Path(env)
    pointer = _read_data_root_pointer()
    if pointer:
        return Path(pointer)
    if is_frozen():
        return _frozen_default_resolution()[0]
    return app_root()


def data_root_source() -> str:
    """数据根来源标识：``"env"`` / ``"pointer"`` / ``"frozen-default"`` /
    ``"frozen-legacy-default"``（旧默认位收养）/ ``"legacy"``（源码形态）。"""
    if os.environ.get("SUBTRANS_DATA_ROOT", "").strip():
        return "env"
    if _read_data_root_pointer():
        return "pointer"
    if is_frozen():
        return _frozen_default_resolution()[1]
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
