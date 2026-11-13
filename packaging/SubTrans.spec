# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for SubTrans (onedir).

布局约定（PyInstaller 6.x，onedir，contents_directory 默认 _internal）：
- 运行时 sys._MEIPASS 指向 <dist>/SubTrans/_internal；
- webview_gui.main.get_asset_path 的 frozen 分支按
  sys._MEIPASS/webview_gui_assets/<相对路径> 找资源，故 assets 目录
  的 datas 目标名固定为 "webview_gui_assets"（建后须实测核对布局）；
- refine defaults 保持包内相对路径 subtrans/refine/defaults，
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
    (os.path.join(SPECPATH, "..", "subtrans", "webview_gui", "assets"),
     "webview_gui_assets"),
    # refine 默认规则：保持包内相对路径
    # （整目录递归拷贝，已覆盖 defaults/templates/**——通用角色卡随包内回落链走）
    (os.path.join(SPECPATH, "..", "subtrans", "refine", "defaults"),
     os.path.join("subtrans", "refine", "defaults")),
    # asr_runner.py 单文件随包（2.7.1 件1 D2026-1005-01：frozen 上游
    # python 脚本路径直调 asr_runner，不再依赖 -m 数据根包形态）；
    # 落点与 asr_env._runner_script_path() frozen 分支逐字节一致。
    # dest 须为目录（PyInstaller datas 语义=dest_dir/basename）：原
    # dest 以文件名结尾会把产物装成嵌套目录 asr_runner.py/asr_runner.py，
    # is_file() 判假→frozen 静默回退 -m 形态必失败（CI Test-Path 对
    # 目录恒真故冒烟未拦）；2026-10-10 测试包轮实证修复
    (os.path.join(SPECPATH, "..", "subtrans", "refine", "asr_runner.py"),
     os.path.join("subtrans", "refine")),
    # line_breaker.py 随包（3.2.1 件①）：asr_runner 脚本直调形态的断行器
    # 回退装载按同目录文件路径解析（_load_break_segments），缺件=断行在
    # frozen 形态静默降级回原生段（2026-10-29 测试包冒烟双路径实证拦获）。
    (os.path.join(SPECPATH, "..", "subtrans", "refine", "line_breaker.py"),
     os.path.join("subtrans", "refine")),
    # pass_merge.py 随包（3.2.0 件A，卡C §七 勘误）：asr_runner 脚本直调
    # 形态的双 pass 合并件回退装载按同目录文件路径解析（_load_pass_merge），
    # 缺件=--passes 2 在 frozen 形态不可用（明示报错，不静默）。
    (os.path.join(SPECPATH, "..", "subtrans", "refine", "pass_merge.py"),
     os.path.join("subtrans", "refine")),
]
# 词典数据不进包（D3 去捆绑 D2026-1001）：sudachidict_core（system.dic 约
# 208MB）不再随安装器分发，语法提示运行时 Dictionary() 失败走既有
# try/except 降级链自动降级，词典经 CLI --dict-download / GUI 引擎页下载。

hiddenimports = [
    "subtrans.refine.cli",
    "subtrans.translate.providers",
    "webview.platforms.winforms",
    "clr",
    # jieba 不进包（D2026-1113-01 反转 D2026-1004-01 段1① 的 hiddenimports 钉）：
    # 安装包默认卸离（可选组件，−30MB）；缺失态三层降级链已就位
    # （token_hint try-import / pipeline_v2 is_zh_hint_available / cli
    # --dict-status FAIL 行）。原「函数内惰性 import 静态不可见」注释与
    # 实际不符——modulegraph 会追踪函数级 import，故卸钉还须打包环境
    # 不装 [zh] extra（release.yml 已同步），产物核对见 release smoke。
    # 壳层启动惰性化（2026-11-13）：refine/__init__ 的包级导出改 PEP 562
    # __getattr__ 动态 import（静态分析不可见），batch/config/glossary/tm
    # 四子模块动态化钉；asr_meta / fs_utils 实为 GUI api.py:33-34 顶层
    # eager 导入（modulegraph 本可收集），属防御性冗余钉——合计
    # 「四子模块动态化钉＋两子模块防御性冗余钉」。
    "subtrans.refine.batch",
    "subtrans.refine.config",
    "subtrans.refine.glossary",
    "subtrans.refine.tm",
    "subtrans.refine.asr_meta",
    "subtrans.refine.fs_utils",
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
    # jieba 结构性卸离（D2026-1113-01）：仅卸 hiddenimports 钉不够——
    # modulegraph 会追踪 token_hint/cli 的函数级 import，构建环境装有
    # [zh] extra 时（本地/开发机构建）仍会连词库 30MB 收进包；excludes
    # 面向两个 Analysis 双侧钉死，产物无 jieba 不再依赖打包环境偶然态
    # （CI 打包链同时已卸 [zh] extra，release smoke 双保险断言）。
    excludes=["jieba"],
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
    excludes=["jieba"],  # 与 GUI 分析同口径（结构性卸离 D2026-1113-01）
    noarchive=False,
    module_collection_mode={},
)
pyz_cli = PYZ(a_cli.pure)

_ICON = os.path.join(SPECPATH, "..", "subtrans", "webview_gui", "assets", "icon.ico")

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
