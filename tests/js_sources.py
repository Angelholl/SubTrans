"""app.js 拆分批集中读取层（3.1 阶段 3 前置，D2026-1016-05 条件 C0）。

JS_FILES 顺序必须复现原始 app.js 文件内定义序（非仅依赖序）——
拼接视图 read_all() 是全部静态断言的文本等价物（C1）。
MSG 键表单一归属：msg_source() 返回含键表的那份文件文本（红线③）。
"""

from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "subtransjav" / "webview_gui" / "assets"

# 加载序 = index.html <script> 顺序 = 原始定义序；每批拆分随批更新本表
JS_FILES = [
    "app.js",               # 段1a 原 L1-10：品牌文件头（品牌钉白名单文件，终态纯注释桩）
    "app-msg.js",           # 段1b 原 L11-1006：MSG 文案表 + applyI18n/AppState/UIHelpers（批2）
    "app-modal.js",         # 段2 原 L1007-2820：AppModal 顶层 const 块（含区头注释）
    "app-error-handler.js", # 段3a 原 app-main.js L1-19：ErrorHandler（批3）
    "app-file-list.js",     # 段3b 原 app-main.js L21-451：FileListManager（批3）
    "app-console.js",       # 段3c 原 app-main.js L453-650：RAWLOG_MODAL_TITLE + ConsoleManager（批3）
    "app-activity.js",      # 段3d 原 app-main.js L652-790：heartbeatIsStale + ActivityStream（批3）
    "app-progress.js",      # 段3e 原 app-main.js L792-858：ProgressManager（批3）
    "app-system-summary.js",# 段3f 原 app-main.js L860-1058：SystemSummary（批3）
    "app-tm-query.js",      # 段3g 原 app-main.js L1060-1168：TmSearch（批3；文件名避开 tm-search 负向钉）
    "app-directory.js",     # 段3h 原 app-main.js L1170-1249：DirectoryControls（批3）
    "app-translator.js",    # 段3i 原 app-main.js L1251-1671：TranslatorManager（批3）
    "app-theme.js",         # 段3j 原 app-main.js L1673-1781：ThemeManager（批3）
    "app-shortcuts.js",     # 段3k 原 app-main.js L1783-1830：KeyboardShortcuts（批3）
    "app-about.js",         # 段3l 原 app-main.js L1832-1854：showAbout + closeAbout（批3）
    "app-main.js",          # 段3 留存块：批3 逐块剥离中的余量（终态=Refine IIFE，批4 目标）
]


def read_all() -> str:
    """依序拼接全部 JS 文件文本（批2 后与拆分前的整份 app.js 逐字节相等）。"""
    return "".join(
        (ASSETS / name).read_text(encoding="utf-8") for name in JS_FILES
    )


def msg_source() -> str:
    """返回含 ``const MSG = {`` 的那份文件文本；恰一份，多份/零份即 AssertionError。"""
    hits = [
        (ASSETS / name).read_text(encoding="utf-8")
        for name in JS_FILES
        if "const MSG = {" in (ASSETS / name).read_text(encoding="utf-8")
    ]
    if len(hits) != 1:
        raise AssertionError(f"const MSG 键表必须恰一份，现 {len(hits)} 份")
    return hits[0]
