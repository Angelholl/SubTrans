"""§5 判定面单列卡回归测试（D2026-1022-03）：默认判定面仅 code-Executor，code-reader 仅观察列。

脚本在本地工具目录（跨域资产），CI 无该文件时 skip（skip 计入基线，基线只增不减）。
"""
import importlib.util
import json
import os
from pathlib import Path

import pytest

SCRIPT = Path(os.path.expanduser("~")) / ".zcode" / "tools" / "audit_dispatch_compliance.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("audit_dispatch_compliance", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _write_jsonl(path, rows):
    with open(path, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


@pytest.mark.skipif(not SCRIPT.is_file(), reason="本地工具目录脚本不在场（跨域文件，CI 无）")
def test_default_face_code_executor_only_and_code_reader_observation(tmp_path, capsys, monkeypatch):
    mod = _load_script()
    skill_row = {"ts": "2026-10-22T10:00:00", "raw": {"session_id": "sA", "tool_name": "Skill",
                 "tool_input": {"skill": "dispatch-discipline"}}}
    exec_row = {"ts": "2026-10-22T10:01:00", "raw": {"session_id": "sA", "tool_name": "Agent",
                "tool_input": {"subagent_type": "code-Executor", "description": "x"}}}
    reader_row = {"ts": "2026-10-22T10:02:00", "raw": {"session_id": "sB", "tool_name": "Agent",
                "tool_input": {"subagent_type": "code-reader", "description": "y"}}}
    _write_jsonl(tmp_path / "skill-loads.jsonl", [skill_row])
    _write_jsonl(tmp_path / "agent-calls.jsonl", [exec_row, reader_row])
    monkeypatch.setattr("sys.argv", ["audit_dispatch_compliance.py", "--logdir", str(tmp_path)])
    assert mod.main() == 0
    out = capsys.readouterr().out
    # 判定面默认仅 code-Executor：样本 1（非合并集的 2），sB 不得作为判定面 miss 展开
    assert "派卡类 subagent_type： code-Executor" in out
    assert "派卡样本：1 次" in out
    assert "sB" not in out
    # code-reader 只进观察列（未读，单列计数）
    assert "观察列（不计入判定率）：1 次" in out
    assert "已读 0 次／未读 1 次" in out
