# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SubTransJAV (onedir).

布局约定（PyInstaller 6.x，onedir，contents_directory 默认 _internal）：
- 运行时 sys._MEIPASS 指向 <dist>/SubTransJAV/_internal；
- webview_gui.main.get_asset_path 的 frozen 分支按
  sys._MEIPASS/webview_gui_assets/<相对路径> 找资源，故 assets 目录
  的 datas 目标名固定为 "webview_gui_assets"（建后须实测核对布局）；
- refine defaults 保持包内相对路径 subtransjav/refine/defaults，
  rules_loader.py:34 / source_hallucination.py:74 按 __file__ 拼接可达。

禁 UPX（D2026-0929-07 点 9：upx=False，避免误压缩损坏 DLL/运行时）。
console=True 为内部门禁件便于诊断（可看 stderr/日志）；正式发布前
再评估 windowed（届时需确认 print/异常有 GUI 弹窗或日志兜底）。
"""

import os
from PyInstaller.utils.hooks import collect_data_files

BLOCK = None  # 不禁用任何 hook（webview / pythonnet 官方 hook 需自动收集 DLL）

datas = [
    # GUI 资源：目标名 webview_gui_assets，与 get_asset_path frozen 分支一致
    (os.path.join(SPECPATH, "..", "subtransjav", "webview_gui", "assets"),
     "webview_gui_assets"),
    # refine 默认规则：保持包内相对路径
    (os.path.join(SPECPATH, "..", "subtransjav", "refine", "defaults"),
     os.path.join("subtransjav", "refine", "defaults")),
]
# sudachidict_core 词典（system.dic 约 80MB）必须进包
datas += collect_data_files("sudachidict_core")

hiddenimports = [
    "subtransjav.refine.cli",
    "subtransjav.translate.providers",
    "webview.platforms.winforms",
    "clr",
]

a = Analysis(
    [os.path.join(SPECPATH, "entry_gui.py")],
    pathex=[SPECPATH],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    module_collection_mode={},
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SubTransJAV",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=os.path.join(SPECPATH, "..", "subtransjav", "webview_gui", "assets", "icon.ico"),
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SubTransJAV",
)
