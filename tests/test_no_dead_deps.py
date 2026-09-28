"""pysubtrans 死依赖摘除断言（打包地基批）：
pyproject 元数据与 subtransjav/ 包源码均不得再引用 PySubtrans。
不 pip uninstall（并行作业期不动 venv，CI 干净安装自会验证独立性）。
"""
import ast
import re
from pathlib import Path

import tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]


def _load_pyproject() -> dict:
    with open(REPO_ROOT / "pyproject.toml", "rb") as f:
        return tomllib.load(f)


def test_pyproject_dependencies_no_pysubtrans():
    data = _load_pyproject()
    deps = data["project"]["dependencies"]
    offending = [d for d in deps if "pysubtrans" in d.lower()]
    assert not offending, f"pyproject dependencies 仍含 pysubtrans: {offending}"


def test_pyproject_keywords_no_pysubtrans():
    data = _load_pyproject()
    assert "pysubtrans" not in [k.lower() for k in data["project"]["keywords"]]


def test_package_sources_import_no_pysubtrans():
    # import 级断言（AST）：subtransjav/ 包全部 .py 不得引入 PySubtrans
    pattern = re.compile(r"^\s*(from|import)\s+PySubtrans", re.MULTILINE)
    pkg_root = REPO_ROOT / "subtransjav"
    for py in sorted(pkg_root.rglob("*.py")):
        source = py.read_text(encoding="utf-8")
        assert not pattern.search(source), f"{py} 出现 PySubtrans import"
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                names = [node.module or ""]
            else:
                continue
            for name in names:
                head = name.split(".")[0]
                assert head.lower() != "pysubtrans", f"{py} 引入 {name}"
