"""guard_banned_paths 测试（v1.3.1 D10，D2026-0925-02；禁推段全量反向契约
与真仓 tracked 核对随 D2026-1106 自检轮扩面）。

覆盖：
1. tmp git 仓构造 tracked 违规文件 → 退出码 1；
2. 干净仓 → 退出码 0；
3. --staged 模式只查 staged（未 staged 的违规文件不触发）；
4. 名单契约（正向）：BANNED_PATTERNS 每一项均被 .gitignore 对应规则覆盖
   或属 decision-log 清单（防名单与 .gitignore 漂移）；
5. cp1252 窄码页（PYTHONIOENCODING=cp1252）下干净仓 → 退出码 0
   （Windows CI 中文输出不崩溃回归）；
6. 反向契约：.gitignore 每个禁推段（锚点见 BANNED_SECTION_ANCHORS）每条规则
   在 BANNED_PATTERNS 有可命中对应（防禁推规则新增而名单漏收，豁免行除外）；
7. 真仓 tracked 核对：本仓库全部 tracked 文件均不命中禁推名单——禁推件
   实际入库（force-add／历史遗留未清）即红，本项经 pytest 进 CI 即牙齿。
"""
import os
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from tools.guard_banned_paths import BANNED_PATTERNS, match_any  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
GUARD = ROOT / "tools" / "guard_banned_paths.py"


def _git(cwd: Path, *args: str) -> None:
    # encoding 显式钉 utf-8 + errors=replace：全局 git 钩子（如提交通知）
    # 向 stderr 写 GBK 等非 UTF-8 字节时，Windows locale 默认解码会抛
    # UnicodeDecodeError 且被静默吞掉，显式宽解码保住退出码与输出。
    subprocess.run(["git", *args], cwd=cwd, check=True,
                   capture_output=True, text=True,
                   encoding="utf-8", errors="replace")


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "--allow-empty", "-m", "init")
    return repo


def _run_guard(repo: Path, *extra: str, env=None):
    # env=None 时 subprocess.run 继承当前环境，行为与旧签名完全一致。
    # encoding/errors 同 _git：显式 utf-8 + replace 防 locale 解码崩溃。
    return subprocess.run(
        [sys.executable, str(GUARD), *extra],
        cwd=repo, capture_output=True, text=True,
        encoding="utf-8", errors="replace", env=env)


def test_tracked_violation_exits_1(tmp_path):
    """tracked 违规文件 → 退出码 1，且输出点名该文件。"""
    repo = _init_repo(tmp_path)
    secret = repo / "config"
    secret.mkdir()
    (secret / "api_keys.bin").write_bytes(b"\x00\x01")
    _git(repo, "add", "config/api_keys.bin")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-m", "oops")
    r = _run_guard(repo)
    assert r.returncode == 1
    assert "config/api_keys.bin" in r.stderr


def test_clean_repo_exits_0(tmp_path):
    """干净仓（仅无辜 tracked 文件）→ 退出码 0。"""
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("ok", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-m", "clean")
    r = _run_guard(repo)
    assert r.returncode == 0


def test_clean_repo_exits_0_with_cp1252_stdio(tmp_path):
    """Windows CI 控制台 cp1252 下中文 [OK] 输出不得崩溃
    （2026-09-26 CI 实测回归）：与 test_clean_repo_exits_0 同造法，
    仅强制 PYTHONIOENCODING=cp1252，干净仓仍须退出码 0。"""
    repo = _init_repo(tmp_path)
    (repo / "README.md").write_text("ok", encoding="utf-8")
    _git(repo, "add", "README.md")
    _git(repo, "-c", "user.email=t@t", "-c", "user.name=t",
         "commit", "-m", "clean")
    r = _run_guard(repo, env=dict(os.environ, PYTHONIOENCODING="cp1252"))
    assert r.returncode == 0


def test_staged_mode_only_checks_staged(tmp_path):
    """--staged 只查 staged：违规文件未 add 时不触发，add 后触发。"""
    repo = _init_repo(tmp_path)
    (repo / "sexual_terms.csv").write_text("x", encoding="utf-8")
    # 未 staged（untracked）→ --staged 模式放行
    r = _run_guard(repo, "--staged")
    assert r.returncode == 0
    # staged 后触发
    _git(repo, "add", "sexual_terms.csv")
    r = _run_guard(repo, "--staged")
    assert r.returncode == 1
    assert "sexual_terms.csv" in r.stderr


def _pattern_literal(pattern: str) -> str:
    """取 pattern 的可 grep 字面：通配条目取首段目录名，字面条目取全名。"""
    return pattern.split("/")[0] if "*" in pattern else pattern


def test_pattern_contract_gitignore_or_decisionlog():
    """名单契约（正向）：每个 pattern 有出处标注，且字面条目能在 .gitignore
    现值或 decision-log 清单里 grep 到（防漂移）。"""
    assert BANNED_PATTERNS, "名单不得为空"
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    dlog_path = ROOT / "docs" / "decision-log.md"
    # D2026-1028-01 公开仓收窄：decision-log 转本地留档（.gitignore 忽略），
    # 全新 clone 无此文件 → decision-log 出处的字面核对仅在本地执行。
    assert "docs/decision-log.md" in gitignore, "decision-log 本地留档未入 .gitignore"
    dlog = dlog_path.read_text(encoding="utf-8") if dlog_path.exists() else None
    for pattern, source in BANNED_PATTERNS:
        assert source, f"{pattern} 缺出处标注"
        literal = _pattern_literal(pattern)
        if literal in gitignore:
            continue
        if "decision-log" in source and dlog is None:
            continue  # 出处＝decision-log 且该文件不在此检出（CI 常态）
        assert dlog is not None and literal in dlog, (
            f"{pattern} 未见于 .gitignore 现值或 decision-log 清单")


def test_match_any_semantics():
    """fnmatch 语义抽查：命中/不命中/子目录均正确。"""
    assert match_any("config/api_keys.bin")
    assert match_any("internal_docs/notes.md")
    assert match_any("Temp/build_blind_pack.py")
    assert not match_any("subtrans/refine/cli.py")
    assert not match_any("tools/guard_banned_paths.py")


def test_real_repo_tracked_files_not_in_banned_list():
    """真仓 tracked 核对（CI 牙齿）：本仓库全部 tracked 文件均不得命中禁推名单。

    禁推清单此前只有 .gitignore 一道防线（`git add -f` 与历史遗留未清不受其管）；
    本项把「清单上的东西确实不在仓里」变成每次 CI 全量 pytest 都跑的断言。
    无 .git 的检出（源码分发包等）跳过，不误报。"""
    if not (ROOT / ".git").exists():
        pytest.skip("无 .git，真仓 tracked 核对不适用")
    r = _run_guard(ROOT)
    assert r.returncode == 0, f"禁推件已实际入库：\n{r.stderr}"


# 反向契约的段锚点：.gitignore 段头注释含该串即该段全部规则须有名单对应。
# 只增不减；新增禁推段须先在此登记，登记即「扩公开面禁推清单」的强制评审点
# （未登记的段其规则不受本契约保护）。逐段出处见注释。
BANNED_SECTION_ANCHORS = (
    "敏感数据（严禁入库）",   # 凭据/真实 glossary/用户态配置
    "TM 备份",               # 私有译文备份（D2026-0918-01 全量清空留痕）
    "误入公开仓库",           # 治理运行时：防御脚本副本/安全源/统计产物
    "内部工作材料",           # D2026-1028-01 公开仓 push 面收窄（owner 三令）
    "公开仓收窄第二批",       # D2026-1106-01 领域包/过程文档/评测工具/入口脚本
    "C22 门控运行态",         # D2026-1031-04 ① 门控状态本地写
)


def _gitignore_section_rules(anchor: str) -> list[str]:
    """取 .gitignore 中段头含 anchor 的段内规则（空行与 `!` 豁免行除外）。

    段边界＝连续注释行构成的段头，其后规则归属该段头，新注释块出现即换段。
    多行段头（如「内部工作材料」段的续行）不会因续行不含锚点而被截断——
    旧实现逐行判定「其余段头关闸」正是这么漏掉了续行后的规则。"""
    rules: list[str] = []
    header: list[str] = []
    prev_comment = False
    for raw in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            if not prev_comment:
                header = []
            header.append(line)
            prev_comment = True
            continue
        prev_comment = False
        if not line or line.startswith("!"):
            continue
        if any(anchor in h for h in header):
            rules.append(line)
    return rules


@pytest.mark.parametrize("anchor", BANNED_SECTION_ANCHORS)
def test_gitignore_banned_section_rules_have_guard_counterpart(anchor):
    """反向契约（防禁推规则新增而名单漏收）：每个禁推段每条规则构造具体
    探测路径走 match_any 真实语义，断言 BANNED_PATTERNS 有可命中对应。"""
    rules = _gitignore_section_rules(anchor)
    assert rules, f"锚点失配：.gitignore 未解析出「{anchor}」段规则"
    for rule in rules:
        probe = rule.replace("*", "20260927").lstrip("/")  # 通配符换具体名
        if probe.endswith("/"):
            probe += "probe.md"       # 目录规则按真实 tracked 形态探测
        hits = match_any(probe)
        assert hits, (f".gitignore「{anchor}」段规则 {rule} 在 BANNED_PATTERNS "
                      f"无对应（probe={probe} 未命中守卫名单）")
