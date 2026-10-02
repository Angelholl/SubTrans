"""内置角色卡首启 seed（批1a D2026-1002-12 件4）。

frozen-only：仅打包（PyInstaller）形态执行——把包内
``defaults/templates`` 的角色卡补拷到数据根 ``config/templates/``；
源码形态一律 no-op（包内即仓库内，拷贝只会弄脏工作树）。

规则：
- 仅当目标文件不存在才拷贝，绝不覆盖用户已改卡；
- 哨兵文件 ``config/templates/.seed-<版本号>`` 记来源版本：哨兵存在
  且版本相同 → 整个扫描跳过（幂等）；包升级带新卡（当前版本哨兵
  缺席）→ 重扫一遍补拷新文件名，已存在文件仍不覆盖；写当前版本
  哨兵并清理旧版本哨兵防堆积；
- 全容错：任何异常折算进返回值（reason），由调用方决定是否继续。
"""

import shutil
from pathlib import Path
from typing import Any

from subtransjav import paths


def _pkg_templates_dir() -> Path:
    """包内模板锚：复用 pipeline_v2 常量（同一打包 datas 源，防漂移）。"""
    from subtransjav.refine.pipeline_v2 import _PKG_TEMPLATES_DIR
    return Path(_PKG_TEMPLATES_DIR)


def _current_version() -> str:
    from subtransjav.__version__ import __version__
    return str(__version__)


def seed_default_templates() -> dict[str, Any]:
    """首启 seed 入口；返回动作摘要（供日志与测试断言）。

    返回形如 ``{"seeded": bool, "reason"/"copied"/"dir"/"version": ...}``；
    永不抛异常（OSError 等折叠为 reason）。
    """
    try:
        if not paths.is_frozen():
            return {"seeded": False, "reason": "not-frozen"}
        pkg_dir = _pkg_templates_dir()
        if not pkg_dir.is_dir():
            return {"seeded": False, "reason": "pkg-templates-missing"}
        tpl_dir = Path(paths.data_root()) / "config" / "templates"
        version = _current_version()
        sentinel = tpl_dir / f".seed-{version}"
        if sentinel.exists():
            # 幂等：当前版本哨兵在 → 整个扫描跳过（零拷贝）
            return {"seeded": False, "reason": "already-seeded"}
        tpl_dir.mkdir(parents=True, exist_ok=True)
        copied: list[str] = []
        for src in sorted(pkg_dir.iterdir()):
            if not src.is_file() or src.suffix.lower() != ".txt":
                continue
            dst = tpl_dir / src.name
            if dst.exists():
                continue  # 绝不覆盖用户已改卡
            shutil.copy2(str(src), str(dst))
            copied.append(src.name)
        # 写当前版本哨兵，清理旧版本哨兵防堆积
        for old in tpl_dir.glob(".seed-*"):
            if old.name != sentinel.name:
                old.unlink()
        sentinel.write_text(version + "\n", encoding="utf-8")
        return {"seeded": True, "copied": copied, "dir": str(tpl_dir),
                "version": version}
    except OSError as e:
        return {"seeded": False, "reason": f"OSError: {e}"}
    except Exception as e:  # noqa: BLE001 - 全容错桩：seed 失败不阻塞启动
        return {"seeded": False, "reason": f"{type(e).__name__}: {e}"}
