"""guard_banned_paths 测试（v1.3.1 D10，D2026-0925-02）。

覆盖：
1. tmp git 仓构造 tracked 违规文件 → 退出码 1；
2. 干净仓 → 退出码 0；
3. --staged 模式只查 staged（未 staged 的违规文件不触发）；
4. 名单契约：BANNED_PATTERNS 每一项均被 .gitignore 对应规则覆盖
   或属 docs/decision-log.md :139 收尾清单（防名单与 .gitignore 漂移）；
5. cp1252 窄码页（PYTHONIOENCODING=cp1252）下干净仓 → 退出码 0
   （Windows CI 中文输出不崩溃回归）；
6. 反向契约：.gitignore「TM 备份」敏感段每条规则在 BANNED_PATTERNS
   有可命中对应（防敏感规则新增而名单漏收，白名单豁免行除外）。
"""
import os
import subprocess
import sys
from pathlib import Path

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


def test_pattern_contract_gitignore_or_decisionlog():
    """名单契约：每个 pattern 有出处标注，且字面条目能在 .gitignore
    或 decision-log :139 清单里 grep 到（防漂移）。"""
    assert BANNED_PATTERNS, "名单不得为空"
    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    dlog = (ROOT / "docs" / "decision-log.md").read_text(encoding="utf-8")
    for pattern, source in BANNED_PATTERNS:
        assert source, f"{pattern} 缺出处标注"
        literal = pattern.split("/")[0] if "*" in pattern else pattern
        if "decision-log" in source:
            assert literal in dlog, f"{pattern} 未见于 decision-log 清单"
        else:
            assert literal in gitignore, f"{pattern} 未见于 .gitignore 现值"


def test_match_any_semantics():
    """fnmatch 语义抽查：命中/不命中/子目录均正确。"""
    assert match_any("config/api_keys.bin")
    assert match_any("internal_docs/notes.md")
    assert match_any("Temp/build_blind_pack.py")
    assert not match_any("subtransjav/refine/cli.py")
    assert not match_any("tools/guard_banned_paths.py")


def test_gitignore_tm_rules_have_guard_counterpart():
    """反向契约（防 .gitignore 敏感规则漏收）：.gitignore「TM 备份」
    敏感段（tm/翻译记忆相关规则）每条规则构造具体探测路径走 match_any
    真实语义，断言 BANNED_PATTERNS 有可命中对应。注释/空行跳过，
    `!` 白名单豁免行不要求收名单（与既有名单-契约测试豁免口径对齐）。
    """
    rules = []
    in_tm_section = False
    for raw in (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line.startswith("#"):
            in_tm_section = "TM 备份" in line    # 段头开闸，其余段头关闸
            continue
        if not in_tm_section or not line:
            continue
        if line.startswith("!"):                 # 白名单豁免行除外
            continue
        rules.append(line)
    assert rules, "锚点失配：.gitignore 未解析出 TM 备份敏感段规则"
    for rule in rules:
        probe = rule.replace("*", "20260927")    # 通配符换具体名走真实匹配
        hits = match_any(probe)
        assert hits, (f".gitignore TM 备份敏感段规则 {rule} 在 BANNED_PATTERNS "
                      f"无对应（probe={probe} 未命中守卫名单）")
