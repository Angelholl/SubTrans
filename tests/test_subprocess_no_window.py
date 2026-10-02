"""批0 钉测试：GUI windowed 路径子进程统一 CREATE_NO_WINDOW。

PyInstaller windowed（packaging/SubTransJAV.spec console=False）下，
GUI 进程内未设 creationflags 的 subprocess.run/Popen 在 Windows 上会闪
黑框。本文件钉死三条约束：

1. webview_gui/api.py、refine/asr_env.py、refine/audio_detect.py（GUI
   试听/转码路径经 ``api.py ad._find_ffmpeg`` 触达其 ffmpeg 冒烟）与
   utils/process_manager.py（spawn 单一收敛点：_taskkill_tree、
   run_with_timeout_tree、spawn_refine_cli 两段均直传；venv_bootstrap 段
   直传 0 维持控制台语义）内，每个
   subprocess.run/Popen/check_output/check_call（含
   ``from subprocess import`` 形态）调用都带 creationflags 关键字；
2. 共享常量 subtransjav.utils.subprocess_flags.CREATE_NO_WINDOW：
   Windows 语义 = 0x08000000、POSIX 语义 = 0——平台无关复核（Ubuntu CI
   照样绿）：AST 摘取常量赋值表达式，在假 os.name 下分别求值；
3. process_manager 的 spawn 收敛点确实消费该共享常量（单一来源防旁路，
   行为与批0 前一致：仅 Windows "subprocess" 段注入）。

AST 判定而非文本 grep——多行调用、别名导入、from-import 形态统一覆盖
（模式对齐 tests/test_spawn_convergence.py）。
"""
import ast
import os
import types
from pathlib import Path

import subtransjav

# 钉测范围：GUI windowed 进程内直接 spawn 的模块 + spawn 单一收敛点
MODULES = [
    Path(subtransjav.__file__).parent / "webview_gui" / "api.py",
    Path(subtransjav.__file__).parent / "refine" / "asr_env.py",
    Path(subtransjav.__file__).parent / "refine" / "audio_detect.py",
    Path(subtransjav.__file__).parent / "utils" / "process_manager.py",
]

# subprocess 顶层 spawn 族（批0 关注带窗口语义的进程创建面）
_SPAWN_FUNCS = {"run", "Popen", "check_output", "check_call"}


def _import_aliases(tree: ast.Module) -> tuple[set[str], set[str]]:
    """收集 (subprocess 模块别名集合, 绑定到 spawn 族函数的本地名集合)。

    覆盖 ``import subprocess`` / ``import subprocess as sp`` 与
    ``from subprocess import run`` / ``from subprocess import run as sr``。
    """
    mod_names: set[str] = set()
    func_names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                if a.name == "subprocess":
                    mod_names.add(a.asname or "subprocess")
        elif isinstance(node, ast.ImportFrom) and node.module == "subprocess":
            for a in node.names:
                if a.name in _SPAWN_FUNCS:
                    func_names.add(a.asname or a.name)
    return mod_names, func_names


def _bare_spawn_calls(path: Path) -> list[str]:
    """返回文件中未带 creationflags 关键字的 subprocess spawn 调用清单。"""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mod_names, func_names = _import_aliases(tree)
    out: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            if not (isinstance(func.value, ast.Name)
                    and func.value.id in mod_names and func.attr in _SPAWN_FUNCS):
                continue
            label = f"subprocess.{func.attr}"
        elif isinstance(func, ast.Name):
            if func.id not in func_names:
                continue
            label = func.id
        else:
            continue
        if "creationflags" not in {kw.arg for kw in node.keywords if kw.arg}:
            out.append(f"{path.name}:{node.lineno} {label}")
    return out


def test_all_spawn_calls_carry_creationflags():
    """钉：GUI windowed 路径每个 subprocess spawn 调用都带 creationflags。"""
    offenders: list[str] = []
    for path in MODULES:
        offenders.extend(_bare_spawn_calls(path))
    assert offenders == [], (
        "以下 subprocess 调用未带 creationflags（windowed 打包会闪黑框，"
        "统一补 subtransjav.utils.subprocess_flags.CREATE_NO_WINDOW）: "
        + ", ".join(offenders))


# ---------------------------------------------------------------------------
# 共享常量语义（平台无关：假 os 模块 exec 源码求值）
# ---------------------------------------------------------------------------

_CONST_MODULE = (Path(subtransjav.__file__).parent / "utils"
                 / "subprocess_flags.py")


def _const_value_for(os_name: str) -> int:
    """在模拟 os.name 下对常量赋值表达式求值（不依赖测试机平台）。

    只摘取 ``CREATE_NO_WINDOW = ...`` 的 AST 节点单独 eval——整模块 exec
    会因源码顶部的 ``import os`` 把假 os 覆盖回真模块，失去模拟语义。
    """
    tree = ast.parse(_CONST_MODULE.read_text(encoding="utf-8"))
    for node in tree.body:
        # 兼容普通赋值与注解赋值（CREATE_NO_WINDOW: int = ... 为 AnnAssign）
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (node.targets if isinstance(node, ast.Assign)
                   else [node.target])
        if not any(isinstance(t, ast.Name) and t.id == "CREATE_NO_WINDOW"
                   for t in targets):
            continue
        ns: dict[str, object] = {"os": types.SimpleNamespace(name=os_name)}
        value = eval(compile(ast.Expression(node.value), "<const>", "eval"), ns)  # noqa: S307  受控源码（仓库内常量模块）
        assert isinstance(value, int)
        return value
    raise AssertionError("subprocess_flags.py 中未找到 CREATE_NO_WINDOW 赋值")


def test_constant_windows_semantics():
    """Windows 语义：0x08000000（CREATE_NO_WINDOW）。"""
    assert _const_value_for("nt") == 0x08000000


def test_constant_posix_semantics():
    """POSIX 语义：0（subprocess 拒绝非 0 creationflags，0 即无操作）。"""
    assert _const_value_for("posix") == 0


def test_imported_constant_matches_platform_semantics():
    """真实导入值与当前平台的模拟求值一致（单一来源未被旁路硬编码）。"""
    from subtransjav.utils.subprocess_flags import CREATE_NO_WINDOW
    assert _const_value_for(
        "nt" if os.name == "nt" else "posix") == CREATE_NO_WINDOW


def test_process_manager_consumes_shared_constant():
    """spawn 收敛点 process_manager 消费共享常量（别名导入、行为不变）。"""
    from subtransjav.utils import process_manager as pm
    assert _const_value_for(
        "nt" if os.name == "nt" else "posix") == pm._CREATE_NO_WINDOW
