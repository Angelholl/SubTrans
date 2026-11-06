"""commit message 脱敏器（D2026-1105-06/07 脱敏债的防复发 hook 本体）。

背景：perf 分支 15 commit message 曾含内部引用三族（Temp/ fuzz 脚本路径／
教训号＋环境细节／插件机制过程记录），存量已随 D2026-1105-07 force-push
脱敏清偿；本件把其中**机器可判定的模式**固化为 commit-msg hook 自动脱敏，
防复发。语义敏感词（内部机制措辞/裁决细节/片名码）不在此自动层——仍归
提交五步人工纪律（tools/guard_banned_paths.py 管文件面，本件只管 message）。

规则（机器可判定、替换后不再被自身命中=幂等），三族：
1. R1 机器四规则：机器绝对路径（``X:/...`` / ``X:\\...``）→「内部路径」；
   教训号 ``L-YYYYMMDD-nn``→「教训（存内部记录）」；``.auto/`` 会话态路径→
   「内部会话态路径」；``%TEMP%`` 路径→「内部临时路径」。URL 不受影响：
   盘符后首个斜杠若再接斜杠即协议分隔符（``scheme://``），负向前瞻整体排除
   （``https://`` 不被误吞）；路径尾类排除全角标点（，；（）「」），防
   「``X:/a；后半句``」把续句整段吞进替换区（与全链清洗重写器同款尾类）。
2. R2 机制词族十条（工具源码行号引用／软重置／路径模式／旧 env 前缀族／
   隔离检出／裸会话态字面等）→中性替换（D2026-1105-07 违禁模式清单全量）。
3. R4 内部口径词族二十四条（内部批次／标注基准／独立判定／样本码等）
   →保义中性替换；替换表＝全链 message 清洗轮已逐笔核过的同源表。

用法：
- commit-msg hook：``python tools/sanitize_commit_msg.py <msgfile>``——
  原地重写、恒 exit 0（失败不阻塞提交）；
- 检查模式：``--check <msgfile>``——将被改写时 exit 1（测试/巡检用）；
- 库用：``sanitize(text) -> tuple[str, list[str]]``（清洗后文本＋命中规则族名）；
- 安装：``--install``——写入 hook（解释器钉死为安装时的绝对路径，防
  PATH 缺失静默失效；既有内容不同则先备份再覆写，见 install_hook）。
"""

from __future__ import annotations

import contextlib
import re
import sys
from datetime import datetime
from pathlib import Path

# git 消息文件名白名单＋ .git 目录内约束（本工具只允许处理 git 消息文件，
# 拒绝一切其他路径——路径校验是功能边界不是附加装饰）。
_MSG_FILENAMES = {"COMMIT_EDITMSG", "MERGE_MSG", "TAG_EDITMSG", "SQUASH_MSG"}

# 替换尾类：与全链清洗重写器同款——在既有排除面外追加全角标点，
# 防「X:/a；后半句」把中文分号起的续句整段吞进替换区（全清轮已核的坑）。
_TAIL = r"[^\s'\"()<>|，；（）「」]*"

# (规则族名, 编译好的模式, 替换文本)。顺序即执行序（长串先于短串）；替换
# 文本不得含任何模式可再匹配的字面（幂等，族名命中去重后进 applied）。
_RULES: list[tuple[str, re.Pattern[str], str]] = [
    # ---- R1 机器四规则 ----
    # 盘符后首个斜杠再接斜杠＝协议分隔符（scheme://），不是盘符路径——
    # 负向前瞻把 URL 整体排除在 abs_path 之外（对既有命中面零收窄）。
    ("abs_path", re.compile(r"[A-Za-z]:[/\\](?![/\\])" + _TAIL), "内部路径"),
    ("lesson_id", re.compile(r"\bL-\d{8}-\d{2}\b"), "教训（存内部记录）"),
    ("auto_state_path", re.compile(r"\.auto[/\\]" + _TAIL), "内部会话态路径"),
    ("temp_env_path", re.compile(r"%TEMP%[/\\]" + _TAIL), "内部临时路径"),
    # ---- R2 机制词族十条（旧 env 前缀字面按规范大小写拼写＋re.I：运行期
    # 照匹配全大写 env 串，文件面由品牌钉白名单明文追踪——见
    # tests/test_brand_allowlist.py ALLOWLIST 同名条目）----
    ("mech_word", re.compile(r"git\.ts:\d+"), "工具源码行号"),
    ("mech_word", re.compile(r"git\.ts"), "工具源码"),
    ("mech_word", re.compile(r"soft-?reset", re.I), "软重置"),
    ("mech_word", re.compile(r"pathspec", re.I), "路径模式"),
    ("mech_word", re.compile(r"SubTransJAV_DATA_ROOT", re.I), "旧数据根 env"),
    ("mech_word", re.compile(r"SubTransJAV_[A-Z_]*", re.I), "旧 env 前缀"),
    ("mech_word", re.compile(r"\bSubTransJAV-\*", re.I), "旧命令别名"),
    ("mech_word", re.compile(r"worktree", re.I), "隔离检出"),
    ("mech_word", re.compile(r"\bTemp/"), "临时目录"),
    ("mech_word", re.compile(r"\.auto(?![A-Za-z])"), "内部会话态"),
    # ---- R4 内部口径词族二十四条（全链清洗轮已逐笔核过的替换表，长串先于短串）----
    ("internal_term", re.compile(r"判批6网页\.bat"), "内部判定网页入口"),
    ("internal_term", re.compile(r"判批6网页"), "内部判定网页"),
    ("internal_term", re.compile(r"判批6\.bat"), "内部判定入口脚本"),
    ("internal_term", re.compile(r"判批6"), "内部判定入口"),
    ("internal_term", re.compile(r"ruling_b6_web"), "内部判定网页工具"),
    ("internal_term", re.compile(r"ruling_b6"), "内部判定工具"),
    ("internal_term", re.compile(r"sensitive_b6_web"), "内部专项网页工具"),
    ("internal_term", re.compile(r"sensitive_b6"), "内部专项工具"),
    ("internal_term", re.compile(r"敏感句网页"), "专项测试网页"),
    ("internal_term", re.compile(r"敏感句"), "专项测试句"),
    ("internal_term", re.compile(r"退役批批6"), "退役内部批次"),
    ("internal_term", re.compile(r"批6"), "内部批次"),
    ("internal_term", re.compile(r"批 6"), "内部批次"),
    ("internal_term", re.compile(r"批0"), "内部基线批"),
    ("internal_term", re.compile(r"金标"), "标注基准"),
    ("internal_term", re.compile(r"盲判"), "独立判定"),
    ("internal_term", re.compile(r"盲标"), "独立标注"),
    ("internal_term", re.compile(r"换人率"), "复核差异率"),
    ("internal_term", re.compile(r"语料码"), "样本码"),
    ("internal_term", re.compile(r"语料"), "样本"),
    ("internal_term", re.compile(r"净语"), "旧品牌名"),
    ("internal_term", re.compile(r"イク系"), "分级条款系"),
    ("internal_term", re.compile(r"イク"), "分级条款"),
    ("internal_term", re.compile(r"裁决"), "裁定"),
]


def _validated_msg_path(raw: str) -> Path:
    """解析并校验路径：仅接受 git 消息文件（白名单文件名或 .git 目录内）。

    拒绝 ../ 穿越（resolve 后白名单外一律 ValueError）。"""
    p = Path(raw).resolve()
    if p.name in _MSG_FILENAMES or ".git" in p.parts:
        return p
    raise ValueError(f"非 git 消息文件路径，拒绝处理: {p}")


def sanitize(text: str) -> tuple[str, list[str]]:
    """清洗 commit message 文本，返回 (清洗后文本, 命中规则族名列表)。"""
    applied: list[str] = []
    for name, pattern, repl in _RULES:
        new_text, n = pattern.subn(repl, text)
        if n:
            text = new_text
            if name not in applied:   # 同族多条命中只记一次族名
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
# commit message 脱敏 hook（D2026-1105-06/07 防复发，由 tools/sanitize_commit_msg.py --install 安装）
"{interp}" "{tool}" "$1" || exit 0
"""


def _backup_hook(hook: Path) -> Path:
    """覆写前把既有 hook 原文备份为 ``commit-msg.bak-<时间戳>``（撞名则续 -N）。"""
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    bak = hook.with_name(f"{hook.name}.bak-{stamp}")
    n = 1
    while bak.exists():
        bak = hook.with_name(f"{hook.name}.bak-{stamp}-{n}")
        n += 1
    bak.write_text(hook.read_text(encoding="utf-8"), encoding="utf-8", newline="")
    return bak


def install_hook(git_dir: str) -> str:
    """向指定 git dir 写入 commit-msg hook（幂等）。返回 hook 路径。

    既有 hook 存在且内容与模板不同时：先备份原文（``commit-msg.bak-<时间戳>``）
    再覆写——绝不静默丢弃用户链条。解释器在安装时钉死为绝对路径，不依赖
    运行时 PATH（PATH 缺失导致保护静默缺席的旧形态已移除）。"""
    tool = Path(__file__).resolve().as_posix()
    interp = Path(sys.executable).as_posix() if sys.executable else "python"
    hooks = Path(git_dir) / "hooks"
    hooks.mkdir(exist_ok=True)
    hook = hooks / "commit-msg"
    body = HOOK_TEMPLATE.format(interp=interp, tool=tool)
    if hook.is_file():
        if hook.read_text(encoding="utf-8") == body:
            return str(hook)
        _backup_hook(hook)
    hook.write_text(body, encoding="utf-8", newline="\n")
    with contextlib.suppress(OSError):
        hook.chmod(0o755)
    return str(hook)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
