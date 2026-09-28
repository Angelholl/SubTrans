"""spawn 收敛钉测试（D2026-0929-06 修订③ + 07 点 1 / 08 点 1）。

钉死约束：subtransjav 包内除 process_manager.py（spawn_refine_cli 单一
收敛点）外，不允许任何 ``subprocess`` 调用（Popen/run/call/check_call/
check_output）的解释器参数含 ``sys.executable``。按 AST 语义判定而非文本
grep——``Path(sys.executable).parent``（model_cache 类用法）等非 spawn
语义不误伤；反之文本上不出现 "sys.executable" 字样的动态拼装也逃不掉
（AST 视角统一覆盖）。

另附逆向自证用例：构造假违规片段，断言检测器能抓到、干净片段不误报。
"""
import ast
from pathlib import Path

import subtransjav

# 收敛点白名单：spawn_refine_cli 所在文件
ALLOWED = {"process_manager.py"}

# subprocess 模块顶层 spawn 族函数（含 check_call，属 call 家族）
_SPAWN_FUNCS = {"Popen", "run", "call", "check_call", "check_output"}


def _uses_sys_executable(node: ast.AST) -> bool:
    """递归判断表达式是否引用 sys.executable（含 getattr(sys, 'executable')）。"""
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Attribute) and sub.attr == "executable"
                and isinstance(sub.value, ast.Name) and sub.value.id == "sys"):
            return True
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                and sub.func.id == "getattr" and len(sub.args) == 2
                and isinstance(sub.args[0], ast.Name)
                and sub.args[0].id == "sys"
                and isinstance(sub.args[1], ast.Constant)
                and sub.args[1].value == "executable"):
            return True
    return False


def _violations(path: Path) -> list[str]:
    """返回该文件中"subprocess 调用且首个位置参数引用 sys.executable"的行号清单。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            name = func.attr
        elif isinstance(func, ast.Name):
            name = func.id
        else:
            continue
        if name not in _SPAWN_FUNCS:
            continue
        if _uses_sys_executable(node.args[0]):
            out.append(f"{path.name}:{node.lineno} subprocess.{name}")
    return out


def test_no_sys_executable_spawn_outside_process_manager():
    """钉：包内 spawn 点全部收敛到 process_manager.py。"""
    pkg_dir = Path(subtransjav.__file__).resolve().parent
    bad: list[str] = []
    for py in sorted(pkg_dir.rglob("*.py")):
        if py.name in ALLOWED:
            continue
        bad.extend(_violations(py))
    assert bad == [], f"spawn 点未收敛（应改走 spawn_refine_cli）: {bad}"


def test_detector_catches_synthetic_violation(tmp_path: Path):
    """逆向自证：假违规片段必须被抓到（防检测器退化为恒真）。"""
    f = tmp_path / "fake_gui.py"
    f.write_text(
        "import subprocess, sys\n"
        "def launch():\n"
        "    return subprocess.run([sys.executable, '-m', 'evil'])\n",
        encoding="utf-8",
    )
    assert _violations(f), "检测器未能抓到合成违规片段"


def test_detector_passes_clean_snippets(tmp_path: Path):
    """逆向自证：非 spawn 用法（Path(sys.executable).parent 等）不误报。"""
    f = tmp_path / "fake_clean.py"
    f.write_text(
        "import subprocess\n"
        "from pathlib import Path\n"
        "import sys\n"
        "exe = Path(sys.executable).parent\n"
        "subprocess.run(['taskkill', '/PID', '1'])\n"
        "subprocess.Popen(['notepad.exe'])\n",
        encoding="utf-8",
    )
    assert _violations(f) == []
