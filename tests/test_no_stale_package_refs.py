"""陈旧包名/入口/根路径引用钉（D2026-1108-02，owner 同意落守卫）。

补 test_brand_allowlist.py 的结构性盲区：品牌钉按 **git tracked** 索引枚举，
且判定面为大小写敏感的旧品牌词——包改名（旧包名→subtrans，D2026-1106-02）后，
落在 .gitignore 禁推区的本地评测工具与小写 import 形态都不在其判定面内，
断链因此可长期潜伏（立项实证：三件 gitignored 本地工具分别 import 旧包名、
指向不存在的旧入口 exe 与已消失的旧仓库根路径）。

本钉改为**按目录枚举**（不看 git 索引），且只匹配「可执行形态」的旧引用：
import 语句 / 入口 exe·命令名 / 绝对根路径 / venv 入口 exe 实体。可执行形态判定含「注释面剔除」：.py 行注释经 tokenize 精确剔除（行号列宽不变），
.iss/.bat/.ps1 剔行首注释；故注释级旧名引用（品牌钉白名单理由、清理锚说明）
不算可执行形态、不必入本钉白名单。docstring **不剔**——里面写着旧包名用法
示例本身就是真陈旧。CHANGELOG 等历史散文不在判定目录内。

判定面：tools/ + subtrans/ + tests/ + packaging/ + 根级 *.bat / *.ps1
（含 gitignored 件，这是本钉存在的理由）。
不扫：artifacts/ 与 spike/（历史会话日志与探针残件，旧名散文密集，扫之必假红）、
docs/（由品牌钉与卡面豁免口径治理）、config/ 与运行态目录（用户数据非代码）。

本文件自身只含小写旧包名字面（匹配模式即被测对象），不含旧品牌词大写形态，
故不入品牌钉白名单；另按 _SELF 自排除，防模式字面自匹配。
"""

from __future__ import annotations

import io
import re
import subprocess
import tokenize
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

_SELF = "tests/test_no_stale_package_refs.py"

# 判定目录（目录枚举，含 gitignored 件）与根级脚本
_SCAN_DIRS = ("tools", "subtrans", "tests", "packaging")
_SCAN_SUFFIXES = {".py", ".iss", ".spec", ".bat", ".ps1"}
_SKIP_DIR_NAMES = {"__pycache__", ".mimosa", ".git", "Temp", "node_modules"}

# 可执行形态旧引用模式（一律大小写不敏感；本文件内不出现其大写形态）
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    # 旧包 import 形态：包改名后 import 旧包即 ModuleNotFoundError
    ("旧包 import", re.compile(r"^[ \t]*(?:from|import)\s+subtransjav\b", re.I | re.M)),
    # 旧入口 exe / console-script 名（改名后 venv 内实体已换名）
    ("旧入口 exe/命令名", re.compile(r"\bsubtransjav-(?:refine|gui|cli)\b", re.I)),
    # 旧绝对根路径字面量（工作区已改名，旧根不存在）；\b 前置令 https:// 类 URL 不匹配
    ("旧绝对根路径", re.compile(r"\b[A-Za-z]:[\\/]{1,2}subtransjav", re.I)),
)

# venv 入口 exe 实体存在性检查用（raw 字符串内单反斜杠、普通字符串内双反斜杠均容）
_VENV_EXE_RE = re.compile(r"venv[\\/]{1,3}Scripts[\\/]{1,3}([A-Za-z0-9_.\-]+)\.exe")

# 白名单（每项一行理由；路径以 / 分隔，跨平台比较）
_ALLOWLIST: dict[str, str] = {
    "tests/test_media_path.py": "本机仓库绝对路径夹具 D:/旧根/tmp/demo.srt（与品牌钉白名单同源，禁区夹具不改史）",
}


def _iter_scan_files() -> list[Path]:
    """按目录枚举待扫文件（不看 git 索引，故 gitignored 本地工具同样入面）。"""
    files: list[Path] = []
    for rel_dir in _SCAN_DIRS:
        abs_dir = REPO_ROOT / rel_dir
        if not abs_dir.is_dir():
            continue
        for p in abs_dir.rglob("*"):
            if not p.is_file() or p.suffix not in _SCAN_SUFFIXES:
                continue
            if _SKIP_DIR_NAMES & set(p.relative_to(abs_dir).parts[:-1]):
                continue
            files.append(p)
    for pattern in ("*.bat", "*.ps1"):
        files.extend(p for p in REPO_ROOT.glob(pattern) if p.is_file())
    return sorted(files)


def _read_text(path: Path) -> str | None:
    """二进制/不可解码文件返回 None（跳过），与品牌钉同口径。"""
    data = path.read_bytes()
    if b"\x00" in data:
        return None
    return data.decode("utf-8", errors="replace")


def _strip_py_comments(text: str) -> str:
    """剔除 .py 行注释（保留行号与列宽，docstring 不剔——旧名用法示例属真陈旧）。

    tokenize 不可解析时保守回退全文扫描（fail-closed：宁可假红也不漏）。
    """
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
    except (tokenize.TokenError, IndentationError, SyntaxError, UnicodeError):
        return text
    lines = text.split("\n")
    for tok in tokens:
        if tok.type == tokenize.COMMENT:
            row, col = tok.start[0] - 1, tok.start[1]
            if 0 <= row < len(lines):
                lines[row] = lines[row][:col] + " " * (len(lines[row]) - col)
    return "\n".join(lines)


def _drop_comment_lines(text: str, prefixes: tuple[str, ...]) -> str:
    """非 Python 脚本的行注释剔除（大小写不敏感前缀）。"""
    out = []
    for line in text.split("\n"):
        if line.strip().lower().startswith(prefixes):
            out.append("")
        else:
            out.append(line)
    return "\n".join(out)


def _scan_text(path: Path) -> str | None:
    """待扫文本：注释面已剔除，故注释级旧名引用（品牌钉白名单理由、清理锚说明）
    不算可执行形态、不必入本钉白名单。"""
    raw = _read_text(path)
    if raw is None:
        return None
    suffix = path.suffix.lower()
    if suffix == ".py":
        return _strip_py_comments(raw)
    if suffix == ".iss":
        return _drop_comment_lines(raw, (";",))
    if suffix == ".bat":
        return _drop_comment_lines(raw, ("rem ", "::"))
    if suffix == ".ps1":
        return _drop_comment_lines(raw, ("#",))
    return raw


def _rel(path: Path) -> str:
    return path.relative_to(REPO_ROOT).as_posix()


def test_patterns_bite_the_historical_breaks() -> None:
    """钉咬合自检：本钉立项时的三件真断链形态必须逐条命中。

    防模式被放宽到形同虚设（钉存在但不咬）。字面一律小写：品牌钉判定面为
    大写旧品牌词，本文件若写大写形态即自身触发品牌钉。
    """
    cases = (
        ("旧包 import", "from subtransjav.refine.filters import parse_srt"),
        ("旧入口 exe/命令名", r'REFINE = REPO + r"\.venv\Scripts\subtransjav-refine.exe"'),
        ("旧绝对根路径", r'REPO = r"D:\subtransjav"'),
    )
    for label, sample in cases:
        pattern = dict(_PATTERNS)[label]
        assert pattern.search(sample), f"模式「{label}」已咬不住立项形态：{sample}"

    # venv 实体钉的捕获面同样自检（单反斜杠 raw 与双反斜杠普通串皆须可捕获）
    assert _VENV_EXE_RE.search(r'ref = r"\.venv\Scripts\subtrans-refine.exe"')
    assert _VENV_EXE_RE.search('ref = ".venv\\\\Scripts\\\\subtrans-refine.exe"')


def test_scan_face_includes_gitignored_tools() -> None:
    """守卫完整性钉：本判定面必须至少含一个 git 未追踪文件。

    若退化为「只扫 tracked 文件」，本钉即与品牌钉重叠而失去补盲价值——
    正是本次断链潜伏的结构性成因，故直接钉死。
    """
    tracked = subprocess.run(
        ["git", "ls-files"], cwd=REPO_ROOT, capture_output=True, text=True, check=True
    ).stdout.splitlines()
    tracked_set = {t.replace("\\", "/") for t in tracked}
    untracked = [f for f in _iter_scan_files() if _rel(f) not in tracked_set]
    if not untracked:
        # 公开仓检出面无 gitignored 本地工具（禁推件只存本地），无从核对——如实跳过，
        # 不误红；本钉的效力在本地全量跑时成立（本地判定面必含禁推区工具）。
        return
    assert untracked, (
        "陈旧引用钉的判定面已不含任何 gitignored 文件，退化为品牌钉的重复品；"
        "本钉的职能正是覆盖禁推区本地工具（包改名断链潜伏处），不得收窄。"
    )


def test_no_stale_executable_refs() -> None:
    """判定：可执行形态旧引用命中集合 == 白名单。"""
    hits: list[str] = []
    for path in _iter_scan_files():
        rel = _rel(path)
        if rel == _SELF:
            continue
        text = _scan_text(path)
        if text is None:
            continue
        for label, pattern in _PATTERNS:
            for m in pattern.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                hits.append(f"{rel}:{line_no} [{label}] {m.group(0).strip()}")

    allowed = set(_ALLOWLIST)
    new_offenders = {h.split(":", 1)[0] for h in hits} - allowed
    assert not new_offenders, (
        "发现白名单外的可执行形态旧引用（包改名断链类）：\n"
        + "\n".join(h for h in hits if h.split(":", 1)[0] in new_offenders)
        + "\n处置：本地工具改指现行包名 subtrans / 现行入口 subtrans-refine·subtrans-gui / "
        "现行仓库根；确需保留旧名（清理锚、禁区夹具）则在 _ALLOWLIST 补条目并写明理由。"
    )


def test_whitelist_entries_still_match() -> None:
    """白名单精度钉：条目若已不再命中模式，须从白名单移除（防精度漂移）。"""
    stale_entries: list[str] = []
    for rel in _ALLOWLIST:
        path = REPO_ROOT / rel
        if not path.is_file():
            stale_entries.append(f"{rel}（文件已不存在）")
            continue
        text = _scan_text(path) or ""
        if not any(p.search(text) for _, p in _PATTERNS):
            stale_entries.append(f"{rel}（已不含任何可执行形态旧引用）")
    assert not stale_entries, "白名单条目已失效，请移除以保持钉的精度：\n" + "\n".join(stale_entries)


def test_venv_entry_exe_refs_exist_on_disk() -> None:
    """实体钉：本地工具字面量指向的 venv 入口 exe 必须真实存在。

    包改名后入口 console-script 同步换名，工具内旧 exe 名不会报错于 import 期，
    只在真正调用时才炸——故对字面量做实体核对。无 .venv/Scripts 的环境（CI、
    非本机）如实跳过，不误红。
    """
    scripts_dir = REPO_ROOT / ".venv" / "Scripts"
    if not scripts_dir.is_dir():
        return  # 如实跳过：无 venv 环境无从核对

    missing: list[str] = []
    for path in _iter_scan_files():
        if _rel(path) == _SELF:
            continue
        text = _scan_text(path)
        if text is None:
            continue
        for m in _VENV_EXE_RE.finditer(text):
            name = m.group(1)
            line_no = text.count("\n", 0, m.start()) + 1
            if not (scripts_dir / f"{name}.exe").is_file():
                missing.append(f"{_rel(path)}:{line_no} → .venv/Scripts/{name}.exe 不存在")

    assert not missing, (
        "本地工具引用的 venv 入口 exe 实体缺失（入口改名断链）：\n"
        + "\n".join(missing)
        + "\n处置：改指现行入口名（subtrans-refine / subtrans-gui）。"
    )
