"""subtrans-cli.exe 薄入口（2.0.0 双 EXE 改造）。

命令行形态保留完整控制台语义（console=True），与 GUI 主程序
（entry_gui.py，windowed）共享同一 PyInstaller onedir 产物（_internal
datas/binaries 只留一份）。逻辑全部委托 subtransjav.refine.cli.main。
"""

import sys

from subtransjav.refine.cli import main

sys.exit(main())
