# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SubTrans (onedir).

布局约定（PyInstaller 6.x，onedir，contents_directory 默认 _internal）：
- 运行时 sys._MEIPASS 指向 <dist>/SubTrans/_internal；
- webview_gui.main.get_asset_path 的 frozen 分支按
  sys._MEIPASS/webview_gui_assets/<相对路径> 找资源，故 assets 目录
  的 datas 目标名固定为 "webview_gui_assets"（建后须实测核对布局）；
- refine defaults 保持包内相对路径 subtransjav/refine/defaults，
  rules_loader.py:34 / source_hallucination.py:74 按 __file__ 拼接可达。

禁 UPX（D2026-0929-07 点 9：upx=False，避免误压缩损坏 DLL/运行时）。

2.0.0 双 EXE（owner 反馈：GUI 启动有 CMD 黑框）：
- SubTrans.exe：console=False（windowed 子系统，启动无黑框），
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

BLOCK = None  # 不禁用任何 hook（webview / pythonnet 官方 hook 需自动收集 DLL）

datas = [
    # GUI 资源：目标名 webview_gui_assets，与 get_asset_path frozen 分支一致
    (os.path.join(SPECPATH, "..", "subtransjav", "webview_gui", "assets"),
     "webview_gui_assets"),
    # refine 默认规则：保持包内相对路径
    # （整目录递归拷贝，已覆盖 defaults/templates/**——通用角色卡随包内回落链走）
    (os.path.join(SPECPATH, "..", "subtransjav", "refine", "defaults"),
     os.path.join("subtransjav", "refine", "defaults")),
]
# 词典数据不进包（D3 去捆绑 D2026-1001）：sudachidict_core（system.dic 约
# 208MB）不再随安装器分发，语法提示运行时 Dictionary() 失败走既有
# try/except 降级链自动降级，词典经 CLI --dict-download / GUI 引擎页下载。

hiddenimports = [
    "subtransjav.refine.cli",
    "subtransjav.translate.providers",
    "webview.platforms.winforms",
    "clr",
    "jieba",  # 显式钉防重构漂移（token_hint 函数内惰性 import 静态不可见）；数据文件由 pyinstaller-hooks-contrib 官方 hook-jieba.py 自动收集，勿重复 collect_data_files（D2026-1004-01）
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

# sudachipy 官方 hook 会在 Analysis 阶段重新收集 sudachidict_core 词典数据
# （构建机已装词典数据时同样触发）——对 Analysis 结果无条件过滤（HRO①，
# dest 路径含 sudachidict_core 的数据一律剔除，防 hook 重新带回词典）。
before = len(a.datas)
a.datas = [t for t in a.datas if "sudachidict_core" not in t[0].replace("\\", "/")]
print(f"[spec] removed {before - len(a.datas)} dict data entries")
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
    name="SubTrans",
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
    name="SubTrans",
)
