"""commit message 脱敏器钉（D2026-1105-06/07 防复发 hook，D2026-1106-03 承接）。

钉面：四规则命中/替换、幂等、合法 message 零误伤（含 URL 保护）、路径白名单
校验、CLI --check 语义、installer 幂等/备份/解释器钉定、真仓 hook 巡检。"""

from __future__ import annotations

import re
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


def test_abs_path_spares_urls():
    """URL 的协议分隔符（scheme://）不是盘符路径——整体零误伤。"""
    for url in (
        "https://example.com",
        "http://127.0.0.1:8080/api?x=1",
        "见 https://example.com/a/b?c=d 说明",
        "ftp://host.tld/dir",
        "https://example.com:443/x#frag",
    ):
        cleaned, applied = sanitize(url)
        assert cleaned == url and applied == [], url


def test_abs_path_real_paths_still_caught():
    """URL 保护零覆盖回归：真实盘符路径（含词邻接、URL 内嵌形态）仍清洗。"""
    for raw, want in (
        ("file:///C:/Users/x/y", "file:///内部路径"),
        ("数据在D:/SubTrans/Temp/a.py", "数据在内部路径"),
        ("(C:\\x\\y)", "(内部路径)"),
    ):
        cleaned, applied = sanitize(raw)
        assert cleaned == want and applied == ["abs_path"], raw


def test_url_text_compose_and_idempotent():
    raw = ("参照 https://example.com/a 与路径 D:/x/Temp/b.py、"
           "教训 L-20261103-09、会话态 .auto/log.jsonl")
    once, a1 = sanitize(raw)
    twice, a2 = sanitize(once)
    assert twice == once and a2 == [], "含 URL 文本二次清洗必须零命中（幂等）"
    assert a1 == ["abs_path", "lesson_id", "auto_state_path"]
    assert "https://example.com/a" in once


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
        # 链上现行形态（全清后）：旧前缀字面已不在合法 message 里
        "refactor(env)!: 兼容层下线——env 旧前缀与旧命令别名移除，单前缀 SUBTRANS_* 新地基",
        "feat: 校对页行内编辑与保存（重编号不变式）",
        "fix(env): 旧根发现 env_get 空值兜底",  # L- 词面不同形（无 -nn 尾）不误伤
        "verify: 全量 3311+6 零失败；Refs: D2026-1106-01",
        "ruff check 全过；重构 paths 数据根直读",  # 机制词族/口径词族近形词不误伤
    ]
    for msg in legit:
        cleaned, applied = sanitize(msg)
        assert cleaned == msg and applied == [], msg


def test_rule_mech_words():
    """R2 机制词族十条抽检：机制词→中性替换，族名去重。"""
    cases = [
        ("评审揪出 git.ts:49 的行号引用", "评审揪出 工具源码行号 的行号引用"),
        ("先 soft-reset 再重建", "先 软重置 再重建"),
        ("pathspec 冲突致误扫", "路径模式 冲突致误扫"),
        ("SUBTRANSJAV_DATA_ROOT 已退役", "旧数据根 env 已退役"),
        ("SUBTRANSJAV_* 别名已删", "旧 env 前缀* 别名已删"),  # 表原语义：[A-Z_]* 含尾下划线，星号保留
        ("worktree 隔离检出法", "隔离检出 隔离检出法"),
        ("过程记录在 Temp/_x.log", "过程记录在 临时目录_x.log"),
        ("会话态 .auto 已收段", "会话态 内部会话态 已收段"),
    ]
    for raw, want in cases:
        cleaned, applied = sanitize(raw)
        assert cleaned == want and applied == ["mech_word"], raw


def test_rule_internal_terms():
    """R4 内部口径词族抽检：保义中性替换，长串先于短串。"""
    cases = [
        ("金标比对完成", "标注基准比对完成"),
        ("盲判结果复核", "独立判定结果复核"),
        ("语料码进 message 即红", "样本码进 message 即红"),
        ("裁决门三态", "裁定门三态"),
        ("经 判批6网页.bat 启动", "经 内部判定网页入口 启动"),
        ("批次表 批6 摘要", "批次表 内部批次 摘要"),
        ("敏感句网页已下线", "专项测试网页已下线"),
        ("ruling_b6 工具归档", "内部判定工具 工具归档"),  # 表原语义：只替换词面，后文原样保留
        ("换人率偏离期望", "复核差异率偏离期望"),
        ("イク系条款下沉规则层", "分级条款系条款下沉规则层"),
        ("退役批批6 材料归档", "退役内部批次 材料归档"),
    ]
    for raw, want in cases:
        cleaned, applied = sanitize(raw)
        assert cleaned == want and applied == ["internal_term"], raw


def test_fullwidth_tail_not_swallowed():
    """路径尾类排除全角标点：中文分号起的续句不被整段吞进替换区。"""
    raw = "落 D:/a/b；随后正常续句照写"
    cleaned, applied = sanitize(raw)
    assert cleaned == "落 内部路径；随后正常续句照写"
    assert applied == ["abs_path"]


def test_expanded_rules_compose_and_idempotent():
    raw = ("金标轮按 worktree 检出，路径 D:/x/a；语料码 R-1 于 Temp/_r.log；"
           "会话态 .auto/log.jsonl 见附录 https://example.com/p")
    once, a1 = sanitize(raw)
    twice, a2 = sanitize(once)
    assert twice == once and a2 == [], "扩面后二次清洗必须零命中（幂等）"
    assert a1 == ["abs_path", "auto_state_path", "mech_word", "internal_term"]
    assert "https://example.com/p" in once, "URL 仍须零误伤"


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


def test_install_identical_reinstall_no_backup(tmp_path):
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    install_hook(str(git_dir))
    install_hook(str(git_dir))
    assert list((git_dir / "hooks").glob("commit-msg.bak-*")) == []


def test_install_backs_up_existing_hook(tmp_path):
    """既有内容不同的 hook：先备份原文再覆写，绝不静默丢弃用户链条。"""
    git_dir = tmp_path / ".git"
    hooks = git_dir / "hooks"
    hooks.mkdir(parents=True)
    hook = hooks / "commit-msg"
    old_body = "#!/bin/sh\n# 用户的旧链条\nold-hook --run\n"
    hook.write_text(old_body, encoding="utf-8", newline="\n")
    install_hook(str(git_dir))
    baks = list(hooks.glob("commit-msg.bak-*"))
    assert len(baks) == 1
    assert baks[0].read_text(encoding="utf-8") == old_body
    new_body = hook.read_text(encoding="utf-8")
    assert new_body.startswith("#!/bin/sh") and "sanitize_commit_msg.py" in new_body


def test_hook_template_pins_absolute_interpreter(tmp_path):
    """hook 解释器钉死为安装时绝对路径——不依赖运行时 PATH（fail-open 根因修复）。"""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    install_hook(str(git_dir))
    body = (git_dir / "hooks" / "commit-msg").read_text(encoding="utf-8")
    m = re.search(r'^"([^"]+)" "([^"]+)" "\$1" \|\| exit 0$', body, re.M)
    assert m, body
    interp = Path(m.group(1))
    assert interp.is_absolute(), body
    assert interp.exists(), "钉死的解释器路径必须真实存在"
    assert interp.as_posix() == Path(sys.executable).as_posix()


def test_installed_hook_healthcheck():
    """真仓巡检（保护缺席不再静默）：hook 在位时必须结构完整且解释器真实存在。

    CI／未装机器（无 hook 文件）自动跳过；本地跑全量套件即完成一次巡检，
    旧形态（裸 ``python`` 或被覆盖的异形 hook）在此直接红。"""
    hook = Path(__file__).resolve().parents[1] / ".git" / "hooks" / "commit-msg"
    if not hook.is_file():
        pytest.skip("commit-msg hook 未安装（CI／未装机器）")
    body = hook.read_text(encoding="utf-8")
    assert body.startswith("#!/bin/sh")
    assert "sanitize_commit_msg.py" in body and '"$1"' in body
    assert "|| exit 0" in body, "fail-open（永不阻塞提交）契约必须保留"
    m = re.search(r'^"([^"]+)" "([^"]+)" "\$1" \|\| exit 0$', body, re.M)
    assert m, f"hook 行形态不符合当前模板（旧形态须重装）: {body!r}"
    assert Path(m.group(1)).exists()
