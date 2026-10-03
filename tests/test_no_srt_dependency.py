"""srt 死依赖守卫（D2026-1003-02）：
pyproject 已摘除 srt 依赖，subtransjav/ 包源码不得回流 `import srt` / `from srt ...`。
只匹配行首 import 语句，不误伤 .srt 字幕扩展名、字符串/注释或局部变量名。
"""
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]

# 行首语句匹配（MULTILINE）：import srt / from srt ...，\b 防止误伤 srt_parser 等同名前缀
_SRT_IMPORT_RE = re.compile(r"^\s*(import\s+srt\b|from\s+srt\b)", re.MULTILINE)


def test_subtransjav_sources_no_srt_import():
    # 扫描 subtransjav/ 包全部 .py 源文件，断言不存在 srt 包的 import 语句
    pkg_root = REPO_ROOT / "subtransjav"
    violations: list[str] = []
    for py in sorted(pkg_root.rglob("*.py")):
        source = py.read_text(encoding="utf-8", errors="replace")
        for match in _SRT_IMPORT_RE.finditer(source):
            line_no = source.count("\n", 0, match.start()) + 1
            violations.append(f"{py}:{line_no}: {match.group(0).strip()}")
    assert not violations, (
        "subtransjav/ 源码出现 srt 包 import，依赖回流：\n"
        + "\n".join(violations)
        + "\n若需字幕解析请勿引入 srt 包（D2026-1003-02 已摘除）"
    )
