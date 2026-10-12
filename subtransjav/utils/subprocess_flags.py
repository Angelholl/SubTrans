"""子进程窗口标志单一来源（批0：windowed 打包防黑框）。

PyInstaller windowed（packaging/SubTrans.spec console=False）下，
GUI 进程内未设 creationflags 的 subprocess.run/Popen 在 Windows 上会闪
黑框。本模块把 CREATE_NO_WINDOW 收敛为全仓单一来源：

- Windows（os.name == "nt"）→ 0x08000000（CREATE_NO_WINDOW，不弹控制台）；
- POSIX → 0（subprocess 在非 Windows 平台拒绝非 0 creationflags，
  传 0 即无操作，Ubuntu CI / Linux 运行时零影响）。

消费方：subtransjav.utils.process_manager（spawn 单一收敛点）、
subtransjav.webview_gui.api、subtransjav.refine.asr_env。
仅依赖标准库 os，无循环导入风险；测试经"假 os 模块 + exec 源码"在任意
平台复核两种语义（见 tests/test_subprocess_no_window.py）。
"""

import os

# Windows: 不为子进程弹控制台窗口；POSIX 必须为 0（非 0 会抛 ValueError）
CREATE_NO_WINDOW: int = 0x08000000 if os.name == "nt" else 0
