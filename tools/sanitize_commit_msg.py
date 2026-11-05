"""commit message 脱敏器（D2026-1105-06/07 脱敏债的防复发 hook 本体）。

背景：perf 分支 15 commit message 曾含内部引用三族（Temp/ fuzz 脚本路径／
教训号＋环境细节／插件机制过程记录），存量已随 D2026-1105-07 force-push
脱敏清偿；本件把其中**机器可判定的模式**固化为 commit-msg hook 自动脱敏，
防复发。语义敏感词（内部机制措辞/裁决细节/片名码）不在此自动层——仍归
提交五步人工纪律（tools/guard_banned_paths.py 管文件面，本件只管 message）。

规则（机器可判定、替换后不再被自身命中=幂等）：
1. 机器绝对路径（``X:/...`` / ``X:\\...``，含 Temp、venv 等一切盘符路径）
   → 「内部路径」
2. 教训号 ``L-YYYYMMDD-nn`` → 「教训（存内部记录）」
3. ``.auto/`` 会话态路径 → 「内部会话态路径」
4. ``%TEMP%`` 环境变量路径 → 「内部临时路径」

用法：
- commit-msg hook：``python tools/sanitize_commit_msg.py <msgfile>``——
  原地重写、恒 exit 0（失败不阻塞提交）；
- 检查模式：``--check <msgfile>``——将被改写时 exit 1（测试/巡检用）；
- 库用：``sanitize(text) -> tuple[str, list[str]]``（清洗后文本＋命中规则名）。
"""

from __future__ import annotations

import contextlib
import re
import sys
from pathlib import Path

# git 消息文件名白名单＋ .git 目录内约束（本工具只允许处理 git 消息文件，
# 拒绝一切其他路径——路径校验是功能边界不是附加装饰）。
_MSG_FILENAMES = {"COMMIT_EDITMSG", "MERGE_MSG", "TAG_EDITMSG", "SQUASH_MSG"}

# (规则名, 编译好的模式, 替换文本)。顺序即执行序；替换文本不得含任何模式
# 可再匹配的字面（内部路径/教训/会话态/临时 均无盘符、无 L- 前缀、无 .auto/）。
_RULES: list[tuple[str, re.Pattern[str], str]] = [
    ("abs_path", re.compile(r"[A-Za-z]:[/\\][^\s'\"()<>|]*"), "内部路径"),
    ("lesson_id", re.compile(r"\bL-\d{8}-\d{2}\b"), "教训（存内部记录）"),
    ("auto_state_path", re.compile(r"\.auto[/\\][^\s'\"()<>|]*"), "内部会话态路径"),
    ("temp_env_path", re.compile(r"%TEMP%[/\\][^\s'\"()<>|]*"), "内部临时路径"),
]


def _validated_msg_path(raw: str) -> Path:
    """解析并校验路径：仅接受 git 消息文件（白名单文件名或 .git 目录内）。

    拒绝 ../ 穿越（resolve 后白名单外一律 ValueError）。"""
    p = Path(raw).resolve()
    if p.name in _MSG_FILENAMES or ".git" in p.parts:
        return p
    raise ValueError(f"非 git 消息文件路径，拒绝处理: {p}")


def sanitize(text: str) -> tuple[str, list[str]]:
    """清洗 commit message 文本，返回 (清洗后文本, 命中规则名列表)。"""
    applied: list[str] = []
    for name, pattern, repl in _RULES:
        new_text, n = pattern.subn(repl, text)
        if n:
            text = new_text
            applied.append(name)
    return text, applied


def sanitize_file(path: str) -> int:
    """原地重写 message 文件（commit-msg hook 契约）。恒返回 0，不阻塞提交。"""
    try:
        p = _validated_msg_path(path)
        raw = p.read_text(encoding="utf-8", errors="replace")
        cleaned, _ = sanitize(raw)
        if cleaned != raw:
            p.write_text(cleaned, encoding="utf-8", newline="")
    except (OSError, ValueError):
        pass  # hook 永不阻塞提交
    return 0


def main(argv: list[str]) -> int:
    if "--install" in argv:
        import subprocess

        git_dir = subprocess.run(["git", "rev-parse", "--absolute-git-dir"],
                                 capture_output=True, text=True, check=True
                                 ).stdout.strip()
        print(install_hook(git_dir))
        return 0
    args = [a for a in argv if a != "--check"]
    check = "--check" in argv
    if not args:
        print("usage: sanitize_commit_msg.py [--install|--check] <msgfile>",
              file=sys.stderr)
        return 2
    try:
        p = _validated_msg_path(args[0])
    except ValueError as e:
        print(str(e), file=sys.stderr)
        return 2
    raw = p.read_text(encoding="utf-8", errors="replace")
    cleaned, applied = sanitize(raw)
    if check:
        if applied:
            print("would sanitize: " + ", ".join(applied), file=sys.stderr)
            return 1
        return 0
    if applied:
        p.write_text(cleaned, encoding="utf-8", newline="")
        print("sanitized: " + ", ".join(applied), file=sys.stderr)
    return 0


HOOK_TEMPLATE = """#!/bin/sh
# commit message 脱敏 hook（D2026-1105-06/07 防复发，由 tools/install_commit_msg_hook.py 安装）
python "{tool}" "$1" || exit 0
"""


def install_hook(git_dir: str) -> str:
    """向指定 git dir 写入 commit-msg hook（幂等）。返回 hook 路径。"""
    tool = Path(__file__).resolve().as_posix()
    hooks = Path(git_dir) / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "commit-msg"
    body = HOOK_TEMPLATE.format(tool=tool)
    if hook.is_file() and hook.read_text(encoding="utf-8") == body:
        return str(hook)
    hook.write_text(body, encoding="utf-8", newline="\n")
    with contextlib.suppress(OSError):
        hook.chmod(0o755)
    return str(hook)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
