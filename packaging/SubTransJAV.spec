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
