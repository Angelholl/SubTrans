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

2.0.0 双 EXE（owner 反馈：GUI 启动有 CMD 黑框）：
- SubTransJAV.exe：console=False（windowed 子系统，启动无黑框），
  入口 packaging/entry_gui.py；
- subtrans-cli.exe：console=True（命令行保留完整控制台语义），
  入口 packaging/entry_cli.py（薄委托 refine.cli.main）。
两者共享一次 Analysis 的 binaries/datas（COLLECT 只收 GUI 分析一份，
_internal 数据只落一份盘）；CLI 分析仅取其 pure/scripts 供 PYZ/入口。
GUI windowed 下 stdout 为 NullWriter，print 链已按容错加固（见
utils/console.py / refine/cli.py stdio 处理）；旧构建兼容回退路径
`[sys.executable, "--subtrans-cli"]` 保留在 spawn_refine_cli。
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
# sudachidict_core 词典（system.dic 约 208MB）默认进包；
# SUBTRANSJAV_SPEC_LITE=1 时剔除词典数据（精简版：语法提示运行时
# Dictionary() 失败走既有 try/except 降级链，功能自动降级不炸）。
_LITE = os.environ.get("SUBTRANSJAV_SPEC_LITE", "").strip() == "1"
if _LITE:
    print("[spec] SUBTRANSJAV_SPEC_LITE=1: excluding sudachidict_core dict data")
else:
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

if _LITE:
    # sudachipy 官方 hook 会在 Analysis 阶段重新收集 sudachidict_core 词典，
    # 仅靠 datas 开关剔不干净——对 Analysis 结果再过滤一次（dest 路径含
    # sudachidict_core 的数据一律剔除，运行时 Dictionary() 失败走降级链）。
    before = len(a.datas)
    a.datas = [t for t in a.datas if "sudachidict_core" not in t[0].replace("\\", "/")]
    print(f"[spec] lite: removed {before - len(a.datas)} dict data entries")
pyz = PYZ(a.pure)

# CLI 薄入口独立 Analysis：只取 pure/scripts 供 PYZ/EXE 入口；
# binaries/datas 共享上方 GUI 分析（refine.cli 及其依赖已在 GUI 分析的
# hiddenimports 中钉死，运行库由 COLLECT 统一落 _internal 一份）。
a_cli = Analysis(
    [os.path.join(SPECPATH, "entry_cli.py")],
    pathex=[SPECPATH],
    binaries=[],
    datas=[],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    module_collection_mode={},
)
pyz_cli = PYZ(a_cli.pure)

_ICON = os.path.join(SPECPATH, "..", "subtransjav", "webview_gui", "assets", "icon.ico")

exe_gui = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SubTransJAV",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=_ICON,
)

exe_cli = EXE(
    pyz_cli,
    a_cli.scripts,
    [],
    exclude_binaries=True,
    name="subtrans-cli",
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
    icon=_ICON,
)

coll = COLLECT(
    exe_gui,
    exe_cli,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SubTransJAV",
)
