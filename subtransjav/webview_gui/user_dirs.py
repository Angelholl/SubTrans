"""用户目录持久化登记（批1a D2026-1002-12 件1）。

单源模块：把用户经受信入口（原生对话框）选择的目录持久化到
``<数据根>/config/user_dirs.json``，形成重启后仍生效的白名单。
消费方式：api.py 装载后作为 ``extra_roots`` 参数传给
``security._resolve_safe_path``——security.py 保持纯函数，不 import
本模块（依赖方向：security ← api → user_dirs）。

文件 schema（顶层 dict，未知键原样保留=前向兼容）：
    {
      "registered_dirs": ["<resolve+normcase 后的绝对目录>", ...],
      "templates_dir": null | "<绝对目录>",   # 角色卡目录（件3）
      "dict_dir": null | "<绝对目录>"          # 词典目录（批1b 件1 起消费）
    }

存储口径：路径一律 ``resolve + normcase`` 后入库（Windows 大小写
不敏感语义与 security._norm_case_key 对齐）；数据根每次现读
（paths.data_root()），改数据根重启后自动跟随新根。
"""

from __future__ import annotations

import contextlib
import json
import os
from pathlib import Path
from typing import Any

from subtransjav import paths
from subtransjav.refine.fs_utils import _atomic_write_text  # 2.6.1 统一原子写件

_FILENAME = "user_dirs.json"

# schema 默认键（templates_dir/dict_dir 为"null=未设置"语义）
_DEFAULT_KEYS = ("templates_dir", "dict_dir")


def store_path() -> str:
    """持久化文件绝对路径（每次调用现读数据根，非导入期快照）。"""
    return os.path.join(str(paths.data_root()), "config", _FILENAME)


def normalize_key(path: str) -> str:
    """归一化键：resolve + normcase（与存储口径一致，供调用方做成员判定）。"""
    return os.path.normcase(str(Path(path).resolve()))


def load() -> dict[str, Any]:
    """读持久化文件；缺失/损坏/形态不符 → 空表（含 schema 默认键）。

    registered_dirs 仅收字符串元素；templates_dir/dict_dir 仅收非空
    字符串（null = 未设置）；未知键原样保留（前向兼容）。
    """
    data: dict[str, Any] = {
        "registered_dirs": [],
        "templates_dir": None,
        "dict_dir": None,
    }
    try:
        with open(store_path(), encoding="utf-8") as f:
            raw = json.load(f)
    except (OSError, ValueError):
        return data
    if not isinstance(raw, dict):
        return data
    dirs = raw.get("registered_dirs")
    if isinstance(dirs, list):
        data["registered_dirs"] = [
            str(d) for d in dirs if isinstance(d, str) and d]
    for key in _DEFAULT_KEYS:
        value = raw.get(key)
        if isinstance(value, str) and value:
            data[key] = value
    for k, v in raw.items():
        if k not in data:
            data[k] = v
    return data


def save(data: dict[str, Any]) -> None:
    """原子写持久化文件（目录不存在先建；写失败向上抛 OSError）。"""
    path = store_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    _atomic_write_text(
        path, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def get_registered_dirs() -> list[str]:
    """持久登记目录集（归一化键，直接可用作 extra_roots）。"""
    return list(load()["registered_dirs"])


def register_dir(path: str) -> str | None:
    """持久登记一个目录（去重、立即落盘）。

    返回归一化键；路径非法返回 None。落盘失败不抛（会话内登记已由
    select_folder 完成，持久化失败仅降级为"重启后失效"）。
    """
    try:
        key = normalize_key(str(path or ""))
    except (OSError, ValueError):
        return None
    if not key:
        return None
    data = load()
    dirs = data["registered_dirs"]
    if key not in dirs:
        dirs.append(key)
        data["registered_dirs"] = dirs
        # 落盘失败仅降级为"重启后失效"，不阻断登记语义
        with contextlib.suppress(OSError):
            save(data)
    return key


def get_templates_dir() -> str | None:
    """持久化的角色卡目录（未设置返回 None）。"""
    value = load().get("templates_dir")
    return str(value) if value else None


def set_templates_dir(path: str | None) -> None:
    """写/清除持久化角色卡目录（None=清除；路径非法抛 ValueError/OSError）。"""
    data = load()
    data["templates_dir"] = normalize_key(str(path)) if path else None
    save(data)


def get_dict_dir() -> str | None:
    """持久化的自定义词典目录（未设置返回 None；批1b 件1 起消费预留键）。"""
    value = load().get("dict_dir")
    return str(value) if value else None


def set_dict_dir(path: str | None) -> None:
    """写/清除持久化自定义词典目录（None=清除恢复数据根默认）。

    语义与 set_templates_dir 对齐：入库走 normalize_key（resolve+normcase）；
    仅写白名单登记文件，落位生效由 api 层注入 dict_manager（依赖方向：
    user_dirs ← api → dict_manager，refine 不反向 import webview_gui）。
    """
    data = load()
    data["dict_dir"] = normalize_key(str(path)) if path else None
    save(data)
