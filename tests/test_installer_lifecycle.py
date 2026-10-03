"""2.6.3 批A 安装器生命周期的静态断言回归测试（D2026-1003-01）。

项目内无 Inno Setup 自动化 UI 测试基建，本文件以源码静态断言锁定
``packaging/setup.iss`` 的安装器生命周期契约与 ``uninstall.bat`` 的
非破坏语义：
- R1 升级检测：AppId 不变 + 显式 CloseApplications + DisplayVersion/
  InstallLocation 读已装信息 + 版本比较 + 降级警告 + 数据保留声明；
- R2 卸载一问制：数据根四级解析 + 锚点硬门槛（与 data_migration.py
  白名单对齐）+ 深度门槛 + 默认保留（MB_DEFBUTTON2）+ DelTree 后保留
  空目录与失败分支；
- 守卫反转注释：[UninstallDelete] 保持空段，绝不静默清理；
- uninstall.bat：仅清快捷方式与缓存，不清理数据根内容（递归删除行
  仅允许出现在 numba_cache 缓存清理处）。

配套 ISCC 编译冒烟（未安装 Inno Setup 6 时跳过）。
"""
import os
import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_ISS = REPO_ROOT / "packaging" / "setup.iss"
UNINSTALL_BAT = REPO_ROOT / "uninstall.bat"
# 仓库实况：data_migration.py 位于 subtransjav/ 包根（非 webview_gui/ 子包）
DATA_MIGRATION = REPO_ROOT / "subtransjav" / "data_migration.py"

APPID_LINE = "{{8F3A5C1E-6B2D-4E9A-9C47-1D0B5A7E2F31}"

# 9 锚（与 subtransjav/data_migration.py 白名单 + 运行时落盘对齐；
# glossary_conflict_watch.json 实际位于 Temp/translation_memory/）
ANCHOR_FILENAMES = [
    "user_dirs.json",
    "user_settings.json",
    "refine_stage_settings.json",
    "api_keys.bin",
    "glossary.csv",
    "glossary_learned.csv",
    "glossary_conflict_watch.json",
    "tm.db",
    "templates",
]


@pytest.fixture(scope="module")
def iss_text() -> str:
    return SETUP_ISS.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def bat_text() -> str:
    """uninstall.bat 为 GBK 编码（无 BOM），按 GBK 解码。"""
    return UNINSTALL_BAT.read_bytes().decode("gbk")


def _extract_section(source: str, name: str) -> str:
    """提取 [Section] 段体（到下一个 [ 段头为止）。"""
    m = re.search(
        rf"^\[{re.escape(name)}\]\s*?\n(.*?)(?=^\[|\Z)",
        source, re.S | re.M)
    assert m, f"未找到 [{name}] 段"
    return m.group(1)


# ---------------------------------------------------------------------------
# R1 安装侧
# ---------------------------------------------------------------------------

def test_appid_unchanged(iss_text):
    """AppId 固定 GUID 是卸载/升级识别口径，永不变更。"""
    assert APPID_LINE in iss_text
    assert "永不变更" in iss_text


def test_close_applications_explicit(iss_text):
    assert "CloseApplications=yes" in _extract_section(iss_text, "Setup")


def test_r1_upgrade_prompt_pinned(iss_text):
    assert "DisplayVersion" in iss_text
    assert "InstallLocation" in iss_text
    assert "MB_OKCANCEL" in iss_text
    assert "完整保留" in iss_text
    assert "function CompareVersion(const oldV, newV: String): Integer;" \
        in iss_text
    # 降级分支文案
    assert "回退到较低版本" in iss_text


# ---------------------------------------------------------------------------
# R2 卸载侧
# ---------------------------------------------------------------------------

def test_r2_one_question_default_keep(iss_text):
    assert "MB_DEFBUTTON2" in iss_text
    assert "MB_YESNO" in iss_text
    assert "【推荐保留】" in iss_text
    assert "function InitializeUninstall(): Boolean;" in iss_text
    assert "procedure CurUninstallStepChanged(CurStep: TUninstallStep);" \
        in iss_text
    assert "usPostUninstall" in iss_text


def test_data_root_resolution_pinned(iss_text):
    """数据根四级解析与 paths.py data_root() 对齐。"""
    assert "SUBTRANSJAV_DATA_ROOT" in iss_text
    assert ".data-root" in iss_text
    assert "LOCALAPPDATA" in iss_text
    assert "function ResolveDataRoot(" in iss_text


def test_anchor_gate_pinned(iss_text):
    for name in ANCHOR_FILENAMES:
        assert name in iss_text, f"iss 锚点集合缺少用户数据锚: {name}"
    assert "function HasAnyAnchor(" in iss_text
    # 拒删分支：未识别到数据按保留处理 + env 自定义提示
    assert "未在" in iss_text
    assert "按保留数据处理" in iss_text
    m = re.search(r"识别到本地数据文件(.{0,400})", iss_text, re.S)
    assert m and "SUBTRANSJAV_DATA_ROOT" in m.group(1), \
        "拒删提示文案应包含环境变量 SUBTRANSJAV_DATA_ROOT 的自查提示"


def test_depth_gate_pinned(iss_text):
    assert "function IsUnsafeRoot(" in iss_text
    # 盘符根判定特征（C: / C:\）
    assert "Length(root) <= 3" in iss_text
    assert "root[2] = ':'" in iss_text
    # 与 {app} 同径比较（实现注释注明）
    assert "{app} 同径" in iss_text


def test_delete_keeps_empty_dir_and_failure_branch(iss_text):
    assert re.search(r"if\s+DelTree\(", iss_text), "DelTree 返回值须被判定"
    assert "ForceDirectories(DataRoot)" in iss_text
    assert "请手动删除" in iss_text


def test_guard_reversal_comment_pinned(iss_text):
    """守卫反转记录：[UninstallDelete] 段头前的注释 + 保持空段。"""
    m = re.search(r"((?:;[^\n]*\n|\n)*)\[UninstallDelete\]", iss_text)
    assert m, "未找到 [UninstallDelete] 段头"
    comment = "\n".join(
        line for line in m.group(1).splitlines()
        if line.strip().startswith(";"))
    assert "D2026-0929-07" in comment
    assert "D2026-1003-01" in comment
    assert "settings.json 系误记" in comment
    # 段体为空：段头到下一 [ 段间除注释与空行外无条目行
    section = _extract_section(iss_text, "UninstallDelete")
    entries = [
        line for line in section.splitlines()
        if line.strip() and not line.strip().startswith(";")
    ]
    assert entries == [], f"[UninstallDelete] 段出现条目行: {entries!r}"


def test_anchor_aligns_with_migration_whitelist():
    """data_migration.py 白名单中的用户数据文件名必须全部出现在 iss 锚点。

    白名单（subtransjav/data_migration.py ``_BASE_FILES``，7 项）均含于
    iss 9 锚集合；DelTree 整树删除下 tm.db 的 -wal/-shm 旁车与
    glossary_conflict_watch.json.bak 随目录一并清除，无需单列锚点；
    config/templates 目录锚覆盖白名单未单列的角色卡/模板目录。
    """
    dm_src = DATA_MIGRATION.read_text(encoding="utf-8")
    m = re.search(r"_BASE_FILES: tuple\[str, \.\.\.\] = \((.*?)\)", dm_src,
                  re.S)
    assert m, "data_migration.py 未找到 _BASE_FILES 白名单"
    names = [Path(item).name for item in re.findall(r'"([^"]+)"', m.group(1))]
    assert names, "白名单解析为空"
    iss = SETUP_ISS.read_text(encoding="utf-8")
    missing = [n for n in names if n not in iss]
    assert missing == [], f"data_migration.py 白名单中 iss 缺失的文件名: {missing}"


# ---------------------------------------------------------------------------
# uninstall.bat 非破坏语义
# ---------------------------------------------------------------------------

def test_uninstall_bat_no_destructive_semantics(bat_text):
    """bat 不得清理数据根内容；递归删除行仅允许 numba_cache 缓存清理。

    仓库实况差异：既有脚本用 ``rmdir /s /q "%CACHE%"`` 递归清 numba_cache
    （缓存可重建，属本脚本「仅清快捷方式与缓存」的既定语义），故此处
    不做 ``rmdir /s`` 一刀切禁令，改为钉死其仅可出现在 numba_cache 行。
    """
    low = bat_text.lower()
    assert "del /s" not in low
    assert "del /q" not in low
    recursive_lines = [
        line for line in low.splitlines()
        if re.search(r"\b(?:rd|rmdir)\s+/s", line)
    ]
    assert recursive_lines, "numba_cache 缓存清理行应保留"
    # CACHE 变量指向 numba_cache（rmdir 行经 %CACHE% 间接引用）
    cache_assign = next(
        (line for line in low.splitlines()
         if re.match(r'\s*set\s+"cache=', line)), "")
    assert "numba_cache" in cache_assign, \
        f"%CACHE% 变量应指向 numba_cache 缓存: {cache_assign!r}"
    for line in recursive_lines:
        assert "numba_cache" in line or "%cache%" in line, \
            f"出现非 numba_cache 的递归删除行: {line!r}"
    # 主通道声明注释
    assert "一问制" in bat_text
    # 数据根内容清理主通道不在 bat（默认保留数据）
    assert "不清理数据根内容" in bat_text


# ---------------------------------------------------------------------------
# ISCC 编译冒烟
# ---------------------------------------------------------------------------

def _find_iscc():
    candidates = [
        Path(os.environ.get("LOCALAPPDATA", ""))
        / "Programs" / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", ""))
        / "Inno Setup 6" / "ISCC.exe",
        Path(os.environ.get("PROGRAMFILES", ""))
        / "Inno Setup 6" / "ISCC.exe",
    ]
    for p in candidates:
        if p.is_file():
            return p
    return None


@pytest.mark.skipif(_find_iscc() is None,
                    reason="未找到 Inno Setup 6 的 ISCC.exe")
def test_isscc_compile_smoke():
    proc = subprocess.run(
        [str(_find_iscc()), "/O-", "/Dversion=test-local-compile",
         str(SETUP_ISS)],
        capture_output=True, text=True, errors="replace", timeout=120,
        shell=False, cwd=REPO_ROOT)
    assert proc.returncode == 0, \
        f"ISCC 编译失败 rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}"
