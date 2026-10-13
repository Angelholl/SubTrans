"""文件系统底层工具（批 3 技术债 a/b，D2026-1002-11 收官）。

依赖方向：refine 共享基底层（webview_gui 可依赖 refine，反向禁止）。
"""
from __future__ import annotations

import contextlib
import os
import time
from pathlib import Path

# 校对页备份件固定名后缀（D2026-1002-10 D2：单份滚动 {原名}.bak.srt；
# 批 3 收口四处字面量唯一来源）
BACKUP_SUFFIX = ".bak.srt"


def _is_file_lock_error(e: BaseException) -> bool:
    """判定是否为 Windows 文件占用错误（WinError 32/33）。"""
    return isinstance(e, PermissionError) or (
        isinstance(e, OSError) and getattr(e, "winerror", None) in (32, 33)
    )


def _atomic_write_text(path, text: str, suffix: str = ".tmp") -> None:
    """原子写文本：同目录临时文件 + os.replace，防中断留下半截产物。

    - ``path`` 接受 str / Path；
    - ``suffix`` 参数化保留三处既有调用点的原值（v2_outputs=".srt.tmp"、
      synopsis/api=".tmp"/".srt.tmp"），行为等价：mkstemp 同目录 +
      fsync + os.replace，失败 finally unlink 临时文件。
    - Windows 文件占用（WinError 32/33）时有界重试：5 次 × 20ms 起
      指数退避，总量 ≤ ~300ms；重试耗尽抛原异常。
    """
    import tempfile
    p = Path(path)
    fd, tmp = tempfile.mkstemp(dir=str(p.parent), suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
            f.flush()
            os.fsync(f.fileno())
        # Windows 文件占用型 flake 有界重试（D2026-1012-01 ⑨）
        for attempt in range(5):
            try:
                os.replace(tmp, str(p))
                break
            except (PermissionError, OSError) as e:
                if attempt == 4 or not _is_file_lock_error(e):
                    raise
                time.sleep(0.02 * (2 ** attempt))
    finally:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
