#!/usr/bin/env python3
"""Version information for SubTransJAV."""

# PEP 440 compliant version for pip/wheel
# main 常驻滚动 dev 号（D2026-1001-03 第⑧项），发布版走 release 分支 bump；
# 版本号按 D2026-1001 交接 D4 已拍口径（2.2.1 不单独发版，下一版=2.3.0）
__version__ = "2.3.0.dev0"

# Human-readable version for display in UI
__version_display__ = "2.3.0.dev0"

# Version metadata
__version_info__ = {
    "major": 2,
    "minor": 3,
    "patch": 0,
    "release": "dev",
    "architecture": "refine-standalone"
}
