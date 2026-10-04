"""品牌统一钉测试（D2026-1004-02 第 1 层：用户可见层 SubTransJAV→SubTrans）。

遍历 git tracked 文本文件，断言含品牌词 ``SubTransJAV`` 的文件集合
等于显式白名单 ALLOWLIST。未来任何新代码/新文案引入旧品牌词即本测试变红，
防止品牌漂移；白名单内每项均带保留理由。

白名单之外的新增出现 → 先判断是否禁区残留（数据根/spec 名/env 名等第 2 层口径），
确属新品牌污染则改为 SubTrans，确需保留则在本白名单补条目并注释理由。
"""

from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 扩展名兜底排除（二进制/资产；正文另有 NUL 字节 + 解码双重探测）
_BINARY_EXTS = {
    ".png", ".jpg", ".jpeg", ".ico", ".gif", ".exe", ".zip", ".dll",
    ".ttf", ".woff", ".woff2", ".mp3", ".bin", ".srt",
}

# 旧品牌词 SubTransJAV 保留白名单（每项一行理由；路径以 / 分隔，跨平台比较）：
ALLOWLIST = frozenset({
    # ---- CI/打包链（第 2 层禁区分辨率：spec 名、dist 目录、产物 exe 名、注释级残留）----
    ".github/workflows/release.yml",       # 行1注释历史定案号 + SubTransJAV.spec 禁区名 + dist 目录 Temp/pyinstaller_dist/SubTransJAV + 产物 SubTransJAV.exe（随 spec 名）
    "packaging/SubTransJAV.spec",          # spec 文件名本身即禁区：PyInstaller 产物名/CI 引用绑死，第 2 层迁移
    "packaging/setup.iss",                 # 禁区四项：MyAppExeName 绑 spec 产物、DefaultDirName、[Files] Source dist 路径、数据根 %LOCALAPPDATA%\SubTransJAV（ResolveDataRoot 默认位）；另 :1/:3 注释级残留
    "packaging/entry_gui.py",              # 模块 docstring 注释级残留（第 2 层随 spec 名一并处置）
    "pyproject.toml",                      # 顶部注释与 description 历史口径；entry points 用小写包名 subtransjav（第 2 层）
    # ---- 用户/历史文档（渊源句、历史沿革、走查记录，不改史）----
    "README.md",                           # 渊源句（"由 SubTransJAV 项目迭代而来"/evolved from）+ 数据根路径 %LOCALAPPDATA%\SubTransJAV 口径
    "CHANGELOG.md",                        # 历史变更记录（历史 commit 链接 Angelholl/SubTransJAV）
    "LICENSE",                             # 版权署名 The SubTransJAV Project Authors（法律文本不改）
    "docs/使用与维护手册.md",               # 标题渊源口径（第 2 层文档批处理）
    "docs/decision-log.md",                # 决策历史记录，永不改写
    "docs/roadmap.md",                     # 历史规划文档
    "docs/B2-门②语料基线-20260926.md",     # 历史走查记录（树外归档绝对路径）
    "docs/design/UI-REDESIGN-HANDOFF.md",  # 历史设计交接文档
    "docs/design/ZCODE-MIGRATION-NOTES.md",  # 历史迁移笔记
    "docs/design/d1d4-批清单.md",          # 历史设计批清单
    "docs/design/d265-批1-UI复审原型.html",  # 历史设计原型快照
    "docs/design/redesign-prototype.html",  # 历史设计原型快照
    "docs/design/ui-phase2-真机走查清单.md",  # 历史走查记录
    "docs/真机走查清单-262.md",             # 历史走查记录（旧名时期产出）
    "docs/真机走查清单-263.md",             # 历史走查记录（旧名时期产出）
    "docs/模型测试两轮交接.md",             # 历史交接文档
    "docs/mimosa-findings-甄别表.md",       # 历史安全审查记录
    "docs/examples/direction-packs/README.txt",  # 方向包示例说明（历史口径句）
    # ---- 运行时禁区（数据根路径 / env 名 / AUMID / Documents 输出目录 / 包名）----
    "subtransjav/paths.py",                # 数据根 frozen 默认 %LOCALAPPDATA%\SubTransJAV（代码 Path(base)/"SubTransJAV" + docstring），第 2 层
    "subtransjav/webview_gui/api.py",      # Documents 输出目录 <Documents>/SubTransJAV/output（用户既有数据路径，改则断链）+ docstring
    "subtransjav/webview_gui/main.py",     # AUMID 'SubTransJAV.Translate.GUI.v1'（开始菜单钉扎标识，改则丢钉扎）+ docstring
    "subtransjav/__init__.py",             # 包 docstring 注释级残留（第 2 层随包名 subtransjav 口径）
    "subtransjav/__version__.py",          # 包 docstring 注释级残留
    "subtransjav/refine/__init__.py",      # 包 docstring 注释级残留
    "subtransjav/translate/__init__.py",   # 包 docstring 注释级残留
    "subtransjav/utils/__init__.py",       # 包 docstring 注释级残留
    "subtransjav/utils/console.py",        # docstring 注释级残留
    "subtransjav/utils/process_manager.py",  # docstring 注释级残留
    "subtransjav/utils/subprocess_flags.py",  # docstring 引用 spec 名 SubTransJAV.spec（禁区）
    # ---- 前端注释级残留（用户不可见；未提交工作树段只读不碰）----
    "subtransjav/webview_gui/assets/app.js",        # 文件头注释 "SubTransJAV GUI 前端控制器"（注释级，非显示文案）
    "subtransjav/webview_gui/assets/style.css",     # 文件头注释（注释级；本文件另有未提交 ASR 行改动，本层不碰）
    "subtransjav/webview_gui/assets/style.dark.css",  # 文件头注释（注释级）
    # ---- 测试内路径/产物名断言（随第 2 层迁移才同步）----
    "tests/test_paths.py",                 # 数据根默认路径断言 Path.home()/"SubTransJAV" 等
    "tests/test_data_migration.py",        # 旧根迁移夹具 SubTransJAV 数据根
    "tests/test_dict_dir_and_migrate.py",  # frozen exe 名 SubTransJAV.exe 夹具（随 spec 名）
    "tests/test_installer_lifecycle.py",   # setup.iss [Files] Source dist 路径断言（禁区）
    "tests/test_media_path.py",            # 本机仓库绝对路径 D:/SubTransJAV 夹具
    "tests/test_subprocess_no_window.py",  # docstring 引用 spec 名 SubTransJAV.spec
    # ---- 工具脚本（本机绝对路径/历史输出文案，非产品代码）----
    "spike/fts5_spike.py",                 # 本机绝对路径 D:/SubTransJAV/Temp/...（spike 脚本）
    "tools/bench_refine.py",               # 基准脚本 print 历史口径
    "tools/model_matrix_run.py",           # 本机仓库绝对路径 D:\SubTransJAV
    "tools/spike_review_video.py",         # spike 窗口标题（工具脚本）
    # ---- bat 残留（数据根/Documents 路径段）----
    "uninstall.bat",                       # 数据根 %LOCALAPPDATA%\subtransjav 清理行 + Documents 提示 文档\SubTransJAV\output（路径不动）
})

# 本测试文件自身因白名单引用 packaging/SubTransJAV.spec 文件名字符串而含品牌词，
# 显式自排除（tracked 前后行为一致），不入白名单集合。
_SELF = "tests/test_brand_allowlist.py"


def _tracked_text_files() -> list[str]:
    """git ls-files 全量 tracked 文件；排除二进制（NUL 字节探测 + 解码失败跳过）。"""
    out = subprocess.run(
        ["git", "ls-files", "-z"], cwd=REPO_ROOT, check=True,
        capture_output=True,
    )
    files = []
    for raw in out.stdout.split(b"\0"):
        if not raw:
            continue
        rel = raw.decode("utf-8", "surrogateescape")
        if Path(rel).suffix.lower() in _BINARY_EXTS:
            continue
        path = REPO_ROOT / rel
        if not path.is_file():
            continue
        blob = path.read_bytes()
        if b"\x00" in blob:  # 二进制
            continue
        try:
            blob.decode("utf-8")
        except UnicodeDecodeError:
            try:
                blob.decode("gbk")
            except UnicodeDecodeError:
                continue  # 非 utf-8/gbk 文本（二进制兜底）
        files.append(rel.replace("\\", "/"))
    return files


def test_brand_subtransjav_only_in_allowlist():
    """含旧品牌词 SubTransJAV 的 tracked 文本文件集合 == 白名单（防品牌漂移钉）。"""
    hits = {
        rel for rel in _tracked_text_files()
        if rel != _SELF
        and b"SubTransJAV" in (REPO_ROOT / rel).read_bytes()
    }
    unexpected = sorted(hits - ALLOWLIST)
    missing = sorted(ALLOWLIST - hits)
    assert not unexpected, (
        "发现白名单外的旧品牌词 SubTransJAV（品牌漂移），"
        f"请改为 SubTrans 或补白名单并注释理由：\n" + "\n".join(unexpected)
    )
    assert not missing, (
        "白名单条目已不再含 SubTransJAV，请从白名单移除（保持钉的精度）：\n"
        + "\n".join(missing)
    )
