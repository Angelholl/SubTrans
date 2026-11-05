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
  仅允许出现在 numba_cache 缓存清理处）；
- 目录防误装加固（D2026-1030-04）：F1 陈旧记录回落 + F2 开发仓库拒装
  双闸（交互 NextButtonClick + 静默 PrepareToInstall）；
- 数据根默认离 C（D2026-1103-05 项②）：落点 A 推导 + 旧默认收养 + 安装期
  写 .data-root 指针 + 系统盘告警 + 深度门槛补判据（祖先/盘符根）+
  新旧两根并存时默认不删并明示两路径。

配套 ISCC 编译冒烟（未安装 Inno Setup 6 时跳过）。
"""
import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
SETUP_ISS = REPO_ROOT / "packaging" / "setup.iss"
UNINSTALL_BAT = REPO_ROOT / "uninstall.bat"
# 仓库实况：data_migration.py 位于 subtransjav/ 包根（非 webview_gui/ 子包）
DATA_MIGRATION = REPO_ROOT / "subtransjav" / "data_migration.py"

APPID_LINE = "{{8F3A5C1E-6B2D-4E9A-9C47-1D0B5A7E2F31}"

# 10 锚（与 subtransjav/data_migration.py 白名单 + 运行时落盘对齐；
# glossary_conflict_watch.json 实际位于 Temp/translation_memory/）
ANCHOR_FILENAMES = [
    "user_dirs.json",
    "user_settings.json",
    "refine_stage_settings.json",
    "api_keys.bin",
    "glossary.csv",
    "glossary_learned.csv",
    "fullchain_c22.json",
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


def test_uninstall_size_list_ct2_pinned(iss_text):
    """卸载一问制量级清单须含 CT2 模型与运行时两大头（D2026-1103 owner 回执项3）。"""
    m = re.search(r"将删除的内容与量级：(.{0,700})", iss_text, re.S)
    assert m, "未找到卸载量级清单块"
    body = m.group(1)
    assert "models\\ct2" in body, "量级清单缺 CT2 模型行（models\\ct2，约 2.9GB）"
    assert "runtime\\ct2" in body, "量级清单缺 CT2 运行时行（runtime\\ct2，约 2.2GB）"


def test_data_root_resolution_pinned(iss_text):
    """数据根四级解析与 paths.py data_root() 对齐（含落点 A 新默认，
    D2026-1103-05 项②）。"""
    assert "SUBTRANSJAV_DATA_ROOT" in iss_text
    assert ".data-root" in iss_text
    assert "LOCALAPPDATA" in iss_text
    assert "function ResolveDataRoot(" in iss_text
    # 落点 A 推导与旧默认收养两面均须在 iss 侧存在（与 paths.py 同规格）
    assert "function _DefaultDataRootFor(" in iss_text
    assert "name + '-data'" in iss_text, "iss 侧 -data 后缀推导缺失"
    assert "SubTrans-data" in iss_text, "iss 侧盘根回退名缺失"
    assert "旧默认位置沿用" in iss_text, "iss 侧缺旧默认收养分支标签"
    assert "function _LegacyDefaultRoot(" in iss_text
    assert "function _ReadDataRootPointer(" in iss_text


def test_installer_writes_data_root_pointer_pinned(iss_text):
    """护栏 5：安装期写 {app}\\.data-root／已有有效指针不覆盖／env 生效不写／
    写入结果记日志／失败显式告警（不得静默回落）。"""
    assert "procedure WriteDataRootPointerAtInstall" in iss_text
    assert "CurStepChanged" in iss_text and "ssPostInstall" in iss_text
    assert "root + #13#10" in iss_text, "未写指针内容行"
    assert "_ReadDataRootPointer(appLoc)" in iss_text, "写前未查既有指针"
    assert "原地升级不覆盖" in iss_text
    assert "优先级高于指针" in iss_text, "env 生效时未跳过写指针"
    assert "[data-root]" in iss_text, "写入结果未记安装日志"
    assert "数据目录指针写入失败" in iss_text, "写失败未显式告警"
    # 收养旧默认位时不得写指针：写下去来源即变「数据目录指针」，GUI/--where
    # 双双误显自定义，且只对默认来源放行的首启插桩门在收养机器上永不触发
    m_adopt = re.search(r"if src = '旧默认位置沿用' then(.{0,300})", iss_text, re.S)
    assert m_adopt and "不写指针" in m_adopt.group(1), "收养态未跳过写指针"


def test_default_data_root_root_forms_pinned(iss_text):
    """iss 侧根形态推导须与 paths.py（pathlib parent==self）同解：
    盘根／UNC 服务根／UNC 分享根（反斜杠恰两处）／单根（尾段为空）。"""
    assert "_CountChar(d, '\\') = 2" in iss_text, "缺 UNC 分享根判据"
    assert "尾段为空" in iss_text, "缺单根（尾段为空）回退"
    assert "d + '\\SubTrans-data'" in iss_text, "根形态回退名缺失"
    assert "function _NormSlashes(" in iss_text, "缺斜杠归一（正斜杠来源会漏判）"


def test_system_drive_warning_pinned(iss_text):
    """护栏 4：安装目录在系统盘/Program Files 不得静默接受——交互告警＋
    改选入口，静默面记日志（披露项）。"""
    assert "function InstallDirOnSystemDrive(" in iss_text
    assert "SystemDriveWarned" in iss_text, "告警未做一次性防循环"
    assert "的默认口径冲突" in iss_text
    assert "MB_YESNO or MB_DEFBUTTON2" in iss_text
    assert "静默安装目录位于系统盘" in iss_text, "静默面未记日志"


def test_two_roots_both_have_data_pinned(iss_text):
    """护栏 8：新旧两根同时有数据 → 不静默二选一删，默认保留并明示两路径。"""
    assert "两个数据目录均存在本地数据" in iss_text
    assert "安装目录旁路：" in iss_text and "旧默认位置：" in iss_text
    m = re.search(r"两个数据目录均存在本地数据(.{0,400})", iss_text, re.S)
    assert m and "不删除任何数据" in m.group(1), "双根并存分支必须默认不删"
    assert "不在本次删除范围" in iss_text, "一问制清单未明示另一根位置"


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
    # 护栏 7 新增两判据：root 为 {app} 祖先 / 剥斜杠后仍是盘符根
    assert "祖先" in iss_text, "缺「root 为安装目录祖先」判据（D2026-1103-05 项②）"
    assert "Copy(lowLoc, 1, Length(lowRoot)) = lowRoot" in iss_text, "祖先前缀判定缺失"
    assert "(Length(lowRoot) = 2) and (lowRoot[2] = ':')" in iss_text, \
        "缺剥尾斜杠后的盘符根判定（C:/ 与 C: 两形态）"


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

    白名单（subtransjav/data_migration.py ``_BASE_FILES``，8 项）均含于
    iss 10 锚集合；DelTree 整树删除下 tm.db 的 -wal/-shm 旁车与
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
def test_isscc_compile_smoke(tmp_path):
    """ISCC 编译冒烟：在 tmp_path 隔离台编译，不依赖仓库产物树。

    为何要 stage 到临时目录：setup.iss 的 [Files] 段引用
    ``..\\Temp\\pyinstaller_dist\\SubTrans\\*``，ISCC 在编译期会校验
    通配符至少命中一个源文件；该产物树由 PyInstaller 构建产生、不在
    仓库内，而 CI 的 windows runner 预装 Inno Setup（skipif 不跳过）
    且 checkout 无产物树，直接对仓库内 setup.iss 编译会 rc=2 全红。
    故将 packaging/ 复制到 tmp_path，并伪造最小产物树（两个空 exe
    满足通配符命中），对副本编译以验证 iss 语法本身可编译。
    """
    stage = tmp_path / "stage"
    shutil.copytree(REPO_ROOT / "packaging", stage / "packaging")
    dist_dir = stage / "Temp" / "pyinstaller_dist" / "SubTrans"
    dist_dir.mkdir(parents=True)
    (dist_dir / "SubTrans.exe").write_bytes(b"")
    (dist_dir / "subtrans-cli.exe").write_bytes(b"")
    proc = subprocess.run(
        [str(_find_iscc()), "/O-", "/Dversion=test-local-compile",
         str(stage / "packaging" / "setup.iss")],
        capture_output=True, text=True, errors="replace", timeout=120,
        shell=False, cwd=stage)
    assert proc.returncode == 0, \
        f"ISCC 编译失败 rc={proc.returncode}\n{proc.stdout}\n{proc.stderr}"


# ---------------------------------------------------------------------------
# 目录防误装加固（D2026-1030-04）
# ---------------------------------------------------------------------------

def test_stale_record_fallback_pinned(iss_text):
    """F1 陈旧记录回落：记录目录不存在或疑似开发仓库 → 回落编译默认目录。

    事故锚：3.1.0 实机安装目录被改名后注册表 App Path 陈旧，安装器默认
    预填旧名，把新版装进了现开发仓库工作树根（D2026-1030-04）。
    """
    assert "procedure CurPageChanged(CurPageID: Integer);" in iss_text
    assert "wpSelectDir" in iss_text
    # 回落目标与默认同源：PickInstallDir（无候选才落 {autopf}\SubTrans）
    assert "PickInstallDir(ExpandConstant('{autopf}\\SubTrans'))" in iss_text
    m = re.search(r"if \(loc <> ''\) and\n(.{0,200}?)then", iss_text, re.S)
    assert m, "未找到 F1 回落条件"
    cond = m.group(1)
    assert "DirExists(loc)" in cond, "回落条件须含记录目录已失效分支"
    assert "IsDevRepoDir(loc)" in cond, "回落条件须含开发仓库分支"


def test_dev_repo_guard_pinned(iss_text):
    """F2 开发仓库拒装：判定特征 + 交互/静默双闸。"""
    assert "function IsDevRepoDir(const dir: String): Boolean;" in iss_text
    m = re.search(r"function IsDevRepoDir.*?Result :=(.*?);", iss_text, re.S)
    assert m, "未找到 IsDevRepoDir 判定体"
    body = m.group(1)
    assert "'\\.git'" in body, "判定须含 .git 目录特征"
    assert "pyproject.toml" in body and "subtransjav" in body, \
        "判定须含 pyproject.toml + subtransjav 源码结构特征"
    # 双闸：交互目录页 NextButtonClick + 覆盖 /SILENT /DIR= 的 PrepareToInstall
    assert "function NextButtonClick(CurPageID: Integer): Boolean;" in iss_text
    assert "function PrepareToInstall(var NeedsRestart: Boolean): String;" in iss_text
    assert "WizardDirValue" in iss_text
    m2 = re.search(r"function PrepareToInstall.*?Result := '';(.*?)end;", iss_text, re.S)
    assert m2 and "IsDevRepoDir" in m2.group(1), \
        "PrepareToInstall 须在空串初值后做开发仓判定并返回阻断文案"


# ---------------------------------------------------------------------------
# 默认安装目录离 C（D2026-1104-01 项 B4）
# ---------------------------------------------------------------------------

def test_default_dir_dynamic_non_system_drive_pinned(iss_text):
    """默认安装目录三级优先（D2026-1105-02）：软件盘标 > D 盘 > C 兜底。

    动态取盘走 [Code] scripted constant，用户在目录页仍可改选；层1/层2
    取不到合格候选时回落编译默认 Param（不得凭猜选盘）。
    """
    setup = _extract_section(iss_text, "Setup")
    assert "DefaultDirName={code:PickInstallDir|{autopf}\\SubTrans}" in setup, \
        "[Setup] 默认目录须改为 scripted constant 形态"
    # 四函数齐备（定义须先于使用，Pascal Script 无前置声明）
    assert "function FixedDriveLetters(): String;" in iss_text
    assert "function SoftwareLabeledDrives(): String;" in iss_text
    assert "function BestInstallDrive(): String;" in iss_text
    assert "function PickInstallDir(Param: String): String;" in iss_text
    # 取盘面：64 位剩余空间 + 系统盘排除 + 固定盘判据（CIM DriveType 3）
    best = re.search(
        r"function BestInstallDrive\(\): String;(.{0,4000})", iss_text, re.S)
    assert best, "未找到 BestInstallDrive 函数体"
    best_body = best.group(1)
    assert "GetSpaceOnDisk64(" in best_body, "取盘面须用 GetSpaceOnDisk64"
    assert "GetEnv('SystemDrive')" in best_body, "须排除系统盘（SystemDrive）"
    assert "IsDevRepoDir(" in best_body, "候选盘须排除开发仓库目录"
    assert "DriveType -eq 3" in iss_text, "固定盘判据须走 CIM DriveType -eq 3"


def test_default_dir_three_tier_priority_pinned(iss_text):
    """三级优先口径钉死（D2026-1105-02）：软件盘标层1 → D 盘层2 → Param 兜底层3。

    盘标匹配在 PowerShell 侧完成（-match 大小写不敏感），输出仅盘符 ASCII，
    规避 OEM 码页中文盘标读回乱码；探针文件四路径清理与 FixedDriveLetters
    同规格。
    """
    sw = re.search(
        r"function SoftwareLabeledDrives\(\): String;(.{0,2200})", iss_text, re.S)
    assert sw, "未找到 SoftwareLabeledDrives 函数体"
    sw_body = sw.group(1)
    assert "software|软件" in sw_body, "层1盘标匹配须覆盖 software 与 软件"
    assert "-match" in sw_body, "盘标匹配须在 PowerShell -match 侧完成"
    assert sw_body.count("DeleteFile(probe)") >= 4, \
        "盘标探针启动失败/退出码非零/读取失败/成功四路径须一致清理"
    best = re.search(
        r"function BestInstallDrive\(\): String;(.{0,4000})", iss_text, re.S)
    assert best, "未找到 BestInstallDrive 函数体"
    best_body = best.group(1)
    # 三级次序：SoftwareLabeledDrives 在前、D 盘居中、空串回落压轴
    i_sw = best_body.index("SoftwareLabeledDrives")
    i_d = best_body.index("Pos('D:'")
    assert i_sw < i_d, "层1（软件盘标）须先于层2（D 盘）判定"
    assert "Pos('D:'" in best_body, "层2须显式判定 D 盘在固定盘集合"
    assert "IsDevRepoDir('D:\\SubTrans')" in best_body, \
        "层2命中前须过 D:\\SubTrans 开发仓库守卫"
    assert "Result := 'D:\\';" in best_body, "层2命中须返回 D:\\"
    pick = re.search(
        r"function PickInstallDir\(Param: String\): String;(.{0,1200})", iss_text,
        re.S)
    assert pick, "未找到 PickInstallDir 函数体"
    assert "Result := Param" in pick.group(1), "层3须回落 Param（C 盘兜底）"
    # 探针文件四路径一致清理：cmd 重定向即使命令失败也会创建文件，
    # 失败分支漏删即在用户 TEMP 留残留（d1104 验收期修正随钉）
    fd = re.search(
        r"function FixedDriveLetters\(\): String;(.{0,1800})", iss_text, re.S)
    assert fd, "未找到 FixedDriveLetters 函数体"
    fd_body = fd.group(1)
    assert fd_body.count("DeleteFile(probe)") >= 4, \
        "探测启动失败/退出码非零/读取失败/成功四路径须一致清理探针文件"
    assert "if FileExists(probe) then" in fd_body, "运行前须预删陈旧探针文件"
    # 回落编译默认 Param（无候选不得猜盘）
    pick = re.search(
        r"function PickInstallDir\(Param: String\): String;(.{0,1200})", iss_text,
        re.S)
    assert pick, "未找到 PickInstallDir 函数体"
    assert "Result := Param" in pick.group(1), "无候选须回落 Param"
    # 负控：三条已证伪路径不得再出现
    assert "GetSpaceFree" not in iss_text, "不得使用不存在的 GetSpaceFree"
    assert "ExecAndCaptureOutput" not in iss_text, \
        "不得使用本机不兼容的 ExecAndCaptureOutput"
    assert "fsinfo drivetype" not in iss_text, \
        "不得用本地化输出匹配的 fsinfo drivetype"


def test_curpage_changed_dir_fallback_uses_picker(iss_text):
    """F1 回落与默认同源：缺省/疑似开发仓库时调 PickInstallDir，
    不再硬编码 {autopf}。"""
    m = re.search(
        r"procedure CurPageChanged\(CurPageID: Integer\);(.*?)"
        r"function NextButtonClick", iss_text, re.S)
    assert m, "未找到 CurPageChanged 段"
    body = m.group(1)
    assert "PickInstallDir(ExpandConstant('{autopf}\\SubTrans'))" in body, \
        "回落须调 PickInstallDir"
    assert "ExpandConstant('{autopf}') + '\\SubTrans'" not in body, \
        "回落行不得再硬编码 {autopf}"
