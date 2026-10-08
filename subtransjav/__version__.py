#!/usr/bin/env python3
"""Version information for SubTransJAV."""

# PEP 440 compliant version for pip/wheel
# main 常驻滚动 dev 号（D2026-1001-03 第⑧项，PEP 440 语义 2.6.2.dev0<2.6.2），
# 发布版走 release 分支 bump；发布后 main 前进到下一 dev 号=即时检查点
__version__ = "2.8.0.2"

# Human-readable version for display in UI
__version_display__ = "2.8.0.2"

# Version metadata
__version_info__ = {
    "major": 2,
    "minor": 8,
    "patch": 0,
    "micro": 2,
    "release": "",
    "architecture": "refine-standalone"
}
