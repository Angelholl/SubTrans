"""commit message 脱敏器钉（D2026-1105-06/07 防复发 hook，D2026-1106-03 承接）。

钉面：四规则命中/替换、幂等、合法 message 零误伤、路径白名单校验、
CLI --check 语义、installer 幂等与 hook 内容。"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))

from sanitize_commit_msg import (  # noqa: E402
    _validated_msg_path,
    install_hook,
    sanitize,
)


def test_rule_abs_path():
    text, applied = sanitize("改 D:\\SubTrans\\Temp\\fuzz_x.py 三处")
    assert "内部路径" in text and "D:\\SubTrans" not in text
    assert applied == ["abs_path"]


def test_rule_lesson_id():
    text, applied = sanitize("按教训 L-20261104-01 改回")
    assert "教训（存内部记录）" in text and "L-20261104-01" not in text
    assert applied == ["lesson_id"]


def test_rule_auto_state_path():
    text, applied = sanitize(".auto/log.jsonl 显示段9 已收")
    assert "内部会话态路径" in text and ".auto/" not in text
    assert applied == ["auto_state_path"]


def test_rule_temp_env_path():
    text, applied = sanitize("产物在 %TEMP%/eval-310/ 报告")
    assert "内部临时路径" in text and "%TEMP%" not in text
    assert applied == ["temp_env_path"]


def test_rules_compose_and_idempotent():
    raw = ("路径 D:/x/Temp/a.py 与教训 L-20261103-09、会话态 .auto/log.jsonl、"
           "临时 %TEMP%/r.json")
    once, a1 = sanitize(raw)
    twice, a2 = sanitize(once)
    assert twice == once and a2 == [], "二次清洗必须零命中（幂等）"
    assert set(a1) == {"abs_path", "lesson_id", "auto_state_path", "temp_env_path"}


def test_legit_messages_untouched():
    legit = [
        "refactor(env)!: 旧前缀 SUBTRANSJAV_* 别名移除，单前缀新地基",
        "feat: 校对页行内编辑与保存（重编号不变式）",
        "fix(env): 旧根发现 env_get 空值兜底",  # L- 词面不同形（无 -nn 尾）不误伤
        "verify: 全量 3311+6 零失败；Refs: D2026-1106-01",
    ]
    for msg in legit:
        cleaned, applied = sanitize(msg)
        assert cleaned == msg and applied == [], msg


def test_path_allowlist_rejects_traversal():
    with pytest.raises(ValueError):
        _validated_msg_path("D:/SubTrans/subtrans/refine/config.py")
    with pytest.raises(ValueError):
        _validated_msg_path("../../etc/passwd")
    # git 消息文件放行
    p = _validated_msg_path("D:/SubTrans/.git/COMMIT_EDITMSG")
    assert p.name == "COMMIT_EDITMSG"


def test_cli_check_semantics(tmp_path, monkeypatch):
    tool = Path(__file__).resolve().parents[1] / "tools" / "sanitize_commit_msg.py"
    msg = tmp_path / "COMMIT_EDITMSG"
    msg.write_text("带 D:/x/Temp/a.py 的消息\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", str(tool), "--check", str(msg)],
                       capture_output=True, text=True)
    assert r.returncode == 1
    r = subprocess.run([sys.executable, "-I", str(tool), str(msg)],
                       capture_output=True, text=True)
    assert r.returncode == 0
    assert "内部路径" in msg.read_text(encoding="utf-8")
    msg.write_text("干净消息\n", encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", str(tool), "--check", str(msg)],
                       capture_output=True, text=True)
    assert r.returncode == 0


def test_installer_idempotent_and_hook_body(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    h1 = install_hook(str(git_dir))
    h2 = install_hook(str(git_dir))
    assert h1 == h2
    body = (git_dir / "hooks" / "commit-msg").read_text(encoding="utf-8")
    assert body.startswith("#!/bin/sh") and '"$1"' in body
    assert "sanitize_commit_msg.py" in body
    # 白名单外路径拒绝：install 只接受 .git 目录形态
    with pytest.raises(ValueError):
        _validated_msg_path(str(tmp_path / "evil.txt"))
