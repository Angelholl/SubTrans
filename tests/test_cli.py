"""cli v2 接线测试（--s1-* 落槽0、--s3-* 落槽2，槽1/3 禁用）"""
import json

import pytest

import subtransjav.refine.config as refine_config
import subtransjav.refine.pipeline_v2 as pv
from subtransjav.refine.cli import build_parser, config_from_args, main


def test_config_from_args_builds_v2_slots(tmp_path):
    args = build_parser().parse_args([
        "-i", str(tmp_path / "x.srt"),
        "--s1-provider", "lmstudio",
        "--s1-model", "qwen-a",
        "--s3-provider", "deepseek",
        "--s3-model", "deepseek-v4-flash",
    ])
    cfg = config_from_args(args)
    assert len(cfg.stages) == 4
    assert [s.index for s in cfg.stages] == [0, 1, 2, 3]
    # --s1-* 落槽0（阶段A），--s3-* 落槽2（阶段B）
    assert cfg.stages[0].provider == "lmstudio"
    assert cfg.stages[0].model == "qwen-a"
    assert cfg.stages[2].provider == "deepseek"
    assert cfg.stages[2].model == "deepseek-v4-flash"
    # 槽0/2 启用（阶段A/B），槽1/3 为 v2 未用占位禁用槽
    assert cfg.stages[0].enabled and cfg.stages[2].enabled
    assert not cfg.stages[1].enabled and not cfg.stages[3].enabled


def test_cli_multi_input_accumulates(tmp_path):
    """回归：GUI 文件夹模式发多个 -i，必须累积而非覆盖（曾只翻译最后一个文件）。"""
    args = build_parser().parse_args([
        "-i", str(tmp_path / "a.srt"),
        "-i", str(tmp_path / "b.srt"),
        "-i", str(tmp_path / "c.srt"),
    ])
    assert len(args.input) == 3
    cfg = config_from_args(args)
    assert len(cfg.inputs) == 3


# ---------------------------------------------------------------------------
# P0：断点续跑 / 事件格式参数 + 退出码映射
# ---------------------------------------------------------------------------

def test_cli_new_resume_and_event_args(tmp_path):
    args = build_parser().parse_args([
        "-i", str(tmp_path / "x.srt"),
        "--resume", "--force-resume",
        "--event-format", "ndjson",
        "--heartbeat-interval", "5.5",
    ])
    cfg = config_from_args(args)
    assert cfg.resume is True
    assert cfg.force_resume is True
    assert cfg.event_format == "ndjson"
    assert cfg.heartbeat_interval == 5.5


def test_cli_force_resume_implies_resume(tmp_path):
    """O4 回归：仅传 --force-resume（不带 --resume）时 resume 隐含生效。"""
    args = build_parser().parse_args([
        "-i", str(tmp_path / "x.srt"),
        "--force-resume",
    ])
    cfg = config_from_args(args)
    assert cfg.force_resume is True
    assert cfg.resume is True


def test_cli_default_args_keep_legacy_behavior(tmp_path):
    """默认值保持旧行为：不复用、text 事件、20s 心跳。"""
    args = build_parser().parse_args(["-i", str(tmp_path / "x.srt")])
    cfg = config_from_args(args)
    assert cfg.resume is False
    assert cfg.force_resume is False
    assert cfg.event_format == "text"
    assert cfg.heartbeat_interval == 20.0


def test_cli_glossary_learn_flags_wired_to_config(tmp_path):
    """D6 遗留：学习闸两开关接线（--glossary-learn / --glossary-conflict-block）。"""
    args = build_parser().parse_args([
        "-i", str(tmp_path / "x.srt"),
        "--glossary-learn", "--glossary-conflict-block",
    ])
    cfg = config_from_args(args)
    assert cfg.glossary_learn_enabled is True
    assert cfg.glossary_conflict_block is True


def test_cli_glossary_learn_flags_default_false(tmp_path):
    """缺省两开关保持关闭（D2026-0921-02 拍板：学习通道重开须显式传参）。"""
    args = build_parser().parse_args(["-i", str(tmp_path / "x.srt")])
    cfg = config_from_args(args)
    assert cfg.glossary_learn_enabled is False
    assert cfg.glossary_conflict_block is False


def _write_input(tmp_path):
    inp = tmp_path / "x.srt"
    inp.write_text("1\n00:00:01,000 --> 00:00:02,000\nこんにちは\n",
                   encoding="utf-8")
    return str(inp)


def _isolate_logs(tmp_path, monkeypatch):
    """把运行日志目录隔离到临时目录（避免污染仓库 Logs/）。"""
    monkeypatch.setattr(refine_config, "LOGS_DIR", str(tmp_path / "Logs"))


def _fake_run_v2(monkeypatch, sink=None, error=None):
    def _run(cfg, *, summary_sink=None, event_stream=None):
        if error is not None:
            raise error
        if summary_sink is not None and sink is not None:
            summary_sink.update(dict(sink))
        return "out_final_cn.srt"
    monkeypatch.setattr(pv, "run_v2", _run)


def test_cli_exit_code_success(tmp_path, monkeypatch):
    _isolate_logs(tmp_path, monkeypatch)
    _fake_run_v2(monkeypatch, sink={
        "files_ok": 1, "files_degraded": 0, "files_failed": 0,
        "untranslated_majority": False, "risk_count": 0,
        "summary_lines": []})
    with pytest.raises(SystemExit) as ei:
        main(["-i", _write_input(tmp_path)])
    assert ei.value.code == 0


def test_cli_exit_code_partial_degradation(tmp_path, monkeypatch, capsys):
    """存在降级/风险但部分成功 → 退出码 3 + 部分降级状态行 + 风险摘要收尾。"""
    _isolate_logs(tmp_path, monkeypatch)
    _fake_run_v2(monkeypatch, sink={
        "files_ok": 1, "files_degraded": 1, "files_failed": 0,
        "untranslated_majority": False, "risk_count": 2,
        "summary_lines": ["⚠️ [warning] B | 降级动作: 回退A译文"]})
    with pytest.raises(SystemExit) as ei:
        main(["-i", _write_input(tmp_path)])
    assert ei.value.code == 3
    # 风险摘要收尾打印到 stdout
    assert "回退A译文" in capsys.readouterr().out
    # 部分降级状态行写入运行日志（⚠️ 开头会归档到 Errors，符合预期）
    logs = list((tmp_path / "Logs").glob("*.txt"))
    assert logs
    assert "部分降级（成功1/降级1/失败0）" in logs[0].read_text(encoding="utf-8")


def test_cli_exit_code_all_failed(tmp_path, monkeypatch):
    """全部失败走现有 RefineError 路径 → 退出码 1。"""
    from subtransjav.refine.pipeline_support import RefineError
    _isolate_logs(tmp_path, monkeypatch)
    _fake_run_v2(monkeypatch, error=RefineError("全部 1 个文件均处理失败"))
    with pytest.raises(SystemExit) as ei:
        main(["-i", _write_input(tmp_path)])
    assert ei.value.code == 1


def test_cli_ndjson_stdout_stays_pure(tmp_path, monkeypatch, capsys):
    """D1 回归：ndjson 模式下 stdout 每一行都必须能被 json.loads——
    收尾的人类可读页脚（📄 运行日志已保存 等）一律改走 stderr。"""
    import json
    _isolate_logs(tmp_path, monkeypatch)
    _fake_run_v2(monkeypatch, sink={
        "files_ok": 1, "files_degraded": 0, "files_failed": 0,
        "untranslated_majority": False, "risk_count": 0,
        "summary_lines": ["   汇总行"]})
    with pytest.raises(SystemExit) as ei:
        main(["-i", _write_input(tmp_path), "--event-format", "ndjson"])
    assert ei.value.code == 0
    captured = capsys.readouterr()
    for line in captured.out.splitlines():
        if line.strip():
            json.loads(line)            # 混入人类可读行会在此抛错
    assert "运行日志已保存" not in captured.out
    assert "运行日志已保存" in captured.err


def test_cli_text_mode_footer_still_on_stdout(tmp_path, monkeypatch, capsys):
    """D1 对照：text 模式（默认）收尾页脚仍打印到 stdout，行为保持不变。"""
    _isolate_logs(tmp_path, monkeypatch)
    _fake_run_v2(monkeypatch, sink={
        "files_ok": 1, "files_degraded": 0, "files_failed": 0,
        "untranslated_majority": False, "risk_count": 0,
        "summary_lines": []})
    with pytest.raises(SystemExit):
        main(["-i", _write_input(tmp_path)])
    assert "运行日志已保存" in capsys.readouterr().out


def test_cli_dry_run_exit_codes_unchanged(tmp_path, monkeypatch):
    """dry-run 行为完全不变：配置正确 → 0（保留现状：成功不产 3）。"""
    _isolate_logs(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as ei:
        main(["-i", _write_input(tmp_path), "--dry-run",
              "--s1-model", "m", "--s3-model", "m"])
    assert ei.value.code == 0
    logs = list((tmp_path / "Logs").glob("*.txt"))
    assert logs
    assert "dry-run" in logs[0].read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# P3-10 补薄：未知 provider 的 validate 报错路径 / 非法 --event-format 退出码
# ---------------------------------------------------------------------------

def test_cli_validate_flags_unknown_provider():
    """argparse choices 之外（程序内构造）的未知 provider 必须被 validate 兜住。"""
    from subtransjav.refine.config import RefineConfig, StageConfig
    cfg = RefineConfig(
        inputs=["whatever.srt"],
        stages=[StageConfig(0, True, "no-such-provider", "some-model")],
    )
    errs = cfg.validate()
    assert errs, "未知 provider 必须产生校验错误"
    assert any("no-such-provider" in e for e in errs)
    assert any("缺少接口地址" in e for e in errs), \
        "未知 provider 无默认 endpoint，必须报缺少接口地址"
    assert any("缺少 API Key" in e for e in errs), \
        "未知 provider 解析不到密钥，必须报缺少 API Key"


def test_cli_invalid_event_format_exits_2(tmp_path, monkeypatch):
    """--event-format 非法值：argparse 报错并退出码 2（不进入翻译流程）。"""
    _isolate_logs(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as ei:
        main(["-i", _write_input(tmp_path), "--event-format", "xml"])
    assert ei.value.code == 2
    # 不应产生运行日志（在解析阶段即终止）
    assert not list((tmp_path / "Logs").glob("*.txt"))


# ---------------------------------------------------------------------------
# 闸门0：--source-filter 三档
# ---------------------------------------------------------------------------

def test_cli_source_filter_modes(tmp_path):
    """--source-filter 三档逐一解析落 cfg.v2_source_filter。"""
    for value in ("strict", "default", "off"):
        args = build_parser().parse_args([
            "-i", str(tmp_path / "x.srt"), "--source-filter", value])
        cfg = config_from_args(args)
        assert cfg.v2_source_filter == value


def test_cli_source_filter_default_keeps_std_gate(tmp_path):
    """默认 default 档（闸门0 开启，仅明确幻觉删除）。"""
    args = build_parser().parse_args(["-i", str(tmp_path / "x.srt")])
    cfg = config_from_args(args)
    assert cfg.v2_source_filter == "default"


def test_cli_invalid_source_filter_exits_2(tmp_path, monkeypatch):
    """--source-filter 非法值：argparse 报错并退出码 2（仿 --event-format）。"""
    _isolate_logs(tmp_path, monkeypatch)
    with pytest.raises(SystemExit) as ei:
        main(["-i", _write_input(tmp_path), "--source-filter", "bogus"])
    assert ei.value.code == 2
    assert not list((tmp_path / "Logs").glob("*.txt"))


# ---------------------------------------------------------------------------
# H4a：--asr-meta（上游 WhisperJAV 运行 manifest）
# ---------------------------------------------------------------------------

def test_cli_asr_meta_default_empty_means_auto_discovery(tmp_path):
    """默认空串：自动发现 SRT 旁车 whisperjav_run.json 的语义。"""
    args = build_parser().parse_args(["-i", str(tmp_path / "x.srt")])
    cfg = config_from_args(args)
    assert cfg.asr_meta == ""


def test_cli_asr_meta_wired_to_config(tmp_path):
    """--asr-meta 解析并接线到 cfg.asr_meta（文件/目录路径透传）。"""
    meta_path = tmp_path / "run" / "whisperjav_run.json"
    meta_path.parent.mkdir()
    meta_path.write_text("{}", encoding="utf-8")
    args = build_parser().parse_args([
        "-i", str(tmp_path / "x.srt"), "--asr-meta", str(meta_path)])
    cfg = config_from_args(args)
    assert cfg.asr_meta == str(meta_path)


def test_cli_v2_ctx_default_is_generic_16384_with_layering(tmp_path,
                                                           monkeypatch):
    """A1 缺省重绑定（D2026-0927-01）：CLI 不传 --v2-ctx 时缺省=通用保守值
    16384；22272 退到文档/示例层（作者 16GB 档案值，非全局缺省）。
    分层契约：默认 16384 < user_settings.json < SUBTRANSJAV_V2_CTX_LOCAL
    < 显式 --v2-ctx（显式 22272 档案值仍生效）。"""
    monkeypatch.setattr(refine_config, "CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("SUBTRANSJAV_V2_CTX_LOCAL", raising=False)

    # 不传 --v2-ctx：dataclass 缺省 16384
    cfg = config_from_args(build_parser().parse_args(
        ["-i", str(tmp_path / "x.srt")]))
    assert cfg.v2_ctx_local == 16384

    # user_settings.json 分层覆盖
    (tmp_path / "user_settings.json").write_text('{"v2_ctx_local": 8192}',
                                                 encoding="utf-8")
    cfg2 = config_from_args(build_parser().parse_args(
        ["-i", str(tmp_path / "x.srt")]))
    assert cfg2.v2_ctx_local == 8192

    # 环境变量分层覆盖（高于用户文件）
    monkeypatch.setenv("SUBTRANSJAV_V2_CTX_LOCAL", "12288")
    cfg3 = config_from_args(build_parser().parse_args(
        ["-i", str(tmp_path / "x.srt")]))
    assert cfg3.v2_ctx_local == 12288

    # 显式 --v2-ctx 最高优先级：显式 22272 档案值仍生效
    cfg4 = config_from_args(build_parser().parse_args(
        ["-i", str(tmp_path / "x.srt"), "--v2-ctx", "22272"]))
    assert cfg4.v2_ctx_local == 22272


def test_cli_v2_ctx_explicit_override(tmp_path):
    """显式 --v2-ctx 时正确覆盖缺省值（LM Studio 手工改过 ctx 的场景）。"""
    args = build_parser().parse_args([
        "-i", str(tmp_path / "x.srt"), "--v2-ctx", "16384"])
    cfg = config_from_args(args)
    assert cfg.v2_ctx_local == 16384


# ---------------------------------------------------------------------------
# A2 兜底重绑定（D2026-0927-01）：--fallback-model 缺省空串=不启用本地兜底
# ---------------------------------------------------------------------------

def test_cli_fallback_model_default_empty(tmp_path):
    """缺省空串：gemma-4-12b（已否决模型）不再作隐式缺省；未启用
    fallback_local 时缺省构造校验零报错。"""
    args = build_parser().parse_args(["-i", _write_input(tmp_path)])
    cfg = config_from_args(args)
    assert cfg.fallback_model == ""
    assert cfg.fallback_local is False
    errs = cfg.validate()
    assert not any("接管" in e for e in errs)


def test_cli_fallback_model_explicit_still_wired(tmp_path):
    """显式 --fallback-model 照常接线（留空=不启用的反面：显式指定即传）。"""
    args = build_parser().parse_args([
        "-i", str(tmp_path / "x.srt"), "--fallback-model", "my-local-model"])
    cfg = config_from_args(args)
    assert cfg.fallback_model == "my-local-model"


def test_cli_fallback_local_with_empty_model_fails_validation(tmp_path):
    """启用 --fallback-local 而未指定接管模型 → validate 友好报错。"""
    args = build_parser().parse_args([
        "-i", _write_input(tmp_path), "--fallback-local"])
    cfg = config_from_args(args)
    errs = cfg.validate()
    assert any("未指定接管模型" in e for e in errs)


def test_main_module_entry_forwards_exit_code():
    """python -m subtransjav.refine 冒烟：--help 退出码 0。

    __main__.py 必须经 sys.exit(main()) 转发返回值，否则行动层执行器
    （0=成功/1=全败/2=entries 非法/3=部分降级）的退出码在 python -m 下
    静默丢失为 0。--help 走 argparse SystemExit(0) 覆盖不到该分支，
    故同钉源码转发行，防止回退成裸 main()。

    回归钉：PYTHONIOENCODING=cp1252 强制子进程 stdout（管道）用窄码页，
    本地复现 CI windows 实测失败——argparse 打印中文 help 即
    UnicodeEncodeError → 退出 1；main() 开头 stdio 加固
    （reconfigure(errors="backslashreplace")，同 tools/guard_banned_paths.py
    批一修复手法）后恢复退出 0。"""
    import os
    import subprocess
    import sys
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[1]
    src = (repo_root / "subtransjav" / "refine" / "__main__.py").read_text(
        encoding="utf-8")
    assert "sys.exit(main())" in src, \
        "__main__.py 丢失 sys.exit(main())，python -m 下退出码将不传播"
    r = subprocess.run(
        [sys.executable, "-m", "subtransjav.refine", "--help"],
        capture_output=True, cwd=str(repo_root),
        env={**os.environ, "PYTHONIOENCODING": "cp1252"})
    assert r.returncode == 0


# ---------------------------------------------------------------------------
# D2026-0929：--ai-analyze / --ai-model（行动层风格，CLI 直连不进指纹）
# ---------------------------------------------------------------------------

def test_cli_ai_analyze_args_parse():
    args = build_parser().parse_args([
        "--ai-analyze", "out/ep01_质量报告.txt",
        "--ai-model", "qwen-a",
    ])
    assert args.ai_analyze == "out/ep01_质量报告.txt"
    assert args.ai_model == "qwen-a"


def test_cli_ai_analyze_args_default_empty():
    args = build_parser().parse_args([])
    assert args.ai_analyze == "" and args.ai_model == ""


def _ai_materials(tmp_path):
    guide = {"version": 2, "stem": "ep01", "items": [],
             "conclusions": [], "sections": [], "extras": {},
             "source": "ep01.srt", "generated_at": "t",
             "basis": "基于本次运行"}
    (tmp_path / "ep01_质量报告.txt").write_text("报告\n", encoding="utf-8")
    (tmp_path / "ep01_质量报告导读.json").write_text(
        json.dumps(guide, ensure_ascii=False), encoding="utf-8")


def test_cli_ai_analyze_early_exit_calls_advisor(tmp_path, monkeypatch,
                                                 capsys):
    """给定 --ai-analyze 后早退分流（不跑 run_v2），advisor 收到 cfg/args。"""
    import json as _json

    import subtransjav.refine.quality_advisor as qa_mod
    _ai_materials(tmp_path)
    calls = []

    def _fake(cfg, args):
        calls.append((cfg, args))
        (tmp_path / "ep01_AI质量建议.json").write_text(
            _json.dumps({"fake": True}, ensure_ascii=False),
            encoding="utf-8")
        return 0

    monkeypatch.setattr(qa_mod, "run_ai_analyze", _fake)
    rc = main(["--ai-analyze", str(tmp_path / "ep01_质量报告.txt"),
               "--ai-model", "qwen-a"])
    assert rc == 0
    assert len(calls) == 1
    assert calls[0][1].ai_analyze == str(tmp_path / "ep01_质量报告.txt")
    assert calls[0][1].ai_model == "qwen-a"


def test_cli_ai_analyze_exit_code_propagated(tmp_path, monkeypatch):
    import subtransjav.refine.quality_advisor as qa_mod
    _ai_materials(tmp_path)
    monkeypatch.setattr(qa_mod, "run_ai_analyze", lambda cfg, args: 1)
    assert main(["--ai-analyze",
                 str(tmp_path / "ep01_质量报告.txt")]) == 1


def test_cli_ai_analyze_params_not_in_config_fingerprint():
    """负向钉（手法同行动层参数）：--ai-analyze/--ai-model 走 CLI 直连，
    不进 RefineConfig → 天然不进 manifest 指纹。"""
    from subtransjav.refine.config import RefineConfig
    from subtransjav.refine.manifest import _CONFIG_FIELDS, compute_config_hash
    assert "ai_analyze" not in _CONFIG_FIELDS
    assert "ai_model" not in _CONFIG_FIELDS
    base = RefineConfig(inputs=["a.srt"])
    with_ai = RefineConfig(inputs=["a.srt"])
    with_ai.ai_analyze = "r.txt"          # 模拟误挂字段
    with_ai.ai_model = "m"
    assert compute_config_hash(with_ai) == compute_config_hash(base)


# ---------------------------------------------------------------------------
# 2.6.1 修订（D2026-1002-06，验证可选化）：--media-crosscheck-enabled 三态
# ---------------------------------------------------------------------------
def test_cli_media_crosscheck_flag_three_states(tmp_path):
    """0/1 显式落到 cfg（bool 化）；缺省 None 不赋（保分层链默认关）。"""
    base_inputs = ["-i", str(tmp_path / "x.srt")]

    args = build_parser().parse_args([*base_inputs,
                                      "--media-crosscheck-enabled", "1"])
    assert args.media_crosscheck_enabled == 1
    cfg = config_from_args(args)
    assert cfg.media_crosscheck_enabled is True

    args0 = build_parser().parse_args([*base_inputs,
                                       "--media-crosscheck-enabled", "0"])
    assert config_from_args(args0).media_crosscheck_enabled is False

    args_def = build_parser().parse_args(base_inputs)
    assert args_def.media_crosscheck_enabled is None
    cfg_def = config_from_args(args_def)
    assert cfg_def.media_crosscheck_enabled is False   # dataclass 缺省

    # 旗标不进 manifest 指纹（负向钉随批）
    from subtransjav.refine.manifest import _CONFIG_FIELDS
    assert "media_crosscheck_enabled" not in _CONFIG_FIELDS


def test_cli_media_crosscheck_invalid_choice_exits(tmp_path, capsys):
    with pytest.raises(SystemExit) as ei:
        build_parser().parse_args([
            "-i", str(tmp_path / "x.srt"),
            "--media-crosscheck-enabled", "2"])
    assert ei.value.code == 2


# ---------------------------------------------------------------------------
# --where 数据路径诊断（D2026-0929-07 点 3：一次报全、零副作用早退）
# ---------------------------------------------------------------------------
def test_cli_where_prints_key_fields(capsys):
    from subtransjav.refine.cli import main
    rc = main(["--where"])
    assert rc == 0
    out = capsys.readouterr().out
    for key in ("程序版本", "运行形态", "数据根", "配置目录",
                "翻译记忆库路径", "术语冲突观察路径", "DPAPI 密钥位置",
                "迁移状态", "完整迁移随 EXE 首发"):
        assert key in out, f"--where 输出缺字段: {key}"


def test_cli_where_migration_note_by_mode(monkeypatch, capsys):
    """--where 迁移状态行按运行形态分支：frozen 报自动迁移与当前状态，源码保留旧文案。"""
    from subtransjav import paths
    from subtransjav.refine import cli as cli_mod

    monkeypatch.setattr(paths, "is_frozen", lambda: True)
    assert cli_mod.main(["--where"]) == 0
    frozen_out = capsys.readouterr().out
    assert "迁移在 EXE 首次启动时自动执行" in frozen_out
    assert "未迁移" in frozen_out or "已迁移" in frozen_out

    monkeypatch.setattr(paths, "is_frozen", lambda: False)
    assert cli_mod.main(["--where"]) == 0
    source_out = capsys.readouterr().out
    assert "完整迁移随 EXE 首发，当前版本不迁移" in source_out


def test_cli_where_exits_before_config_from_args(monkeypatch):
    """--where 必须早退于 config_from_args（纯诊断不建配置）。"""
    from subtransjav.refine import cli as cli_mod
    calls = []
    monkeypatch.setattr(cli_mod, "config_from_args",
                        lambda args: calls.append(args))
    assert cli_mod.main(["--where"]) == 0
    assert calls == []


def test_cli_where_zero_side_effects(tmp_path, monkeypatch):
    """--where 全程只读：数据根指向 tmp 后，不得在 tmp 创建任何目录。"""
    monkeypatch.setenv("SUBTRANSJAV_DATA_ROOT", str(tmp_path))
    from subtransjav.refine.cli import main
    assert main(["--where"]) == 0
    assert list(tmp_path.rglob("*")) == []


def test_cli_where_fts5_probe_line():
    """--where 输出含 FTS5 可用性行（2.6.4 批1 冻结包探测载体，D2026-1003-05 A1）。"""
    from subtransjav.refine import cli
    out = cli._print_where()
    # 宽松断言：只钉前缀行存在，不绑定可用/不可用（极旧环境 sqlite3 可能无 FTS5）
    assert "FTS5 全文搜索:" in out


# ---------------------------------------------------------------------------
# 2.7.3 件⑦（D2026-1006-01）：stdio 加固按管道/tty 区分编码策略
# ---------------------------------------------------------------------------

class _FakeStream:
    """最小假流：记录 reconfigure 调用参数，isatty/故障行为可控。"""

    def __init__(self, tty, *, support_reconfigure=True,
                 fail_reconfigure=False, fail_isatty=False):
        self._tty = tty
        self._fail_reconfigure = fail_reconfigure
        self._fail_isatty = fail_isatty
        self.calls = []
        if support_reconfigure:
            self.reconfigure = self._do_reconfigure

    def isatty(self):
        if self._fail_isatty:
            raise OSError("tty probe failed")
        return self._tty

    def write(self, s):
        return len(s)

    def flush(self):
        return None

    def _do_reconfigure(self, **kwargs):
        self.calls.append(kwargs)
        if self._fail_reconfigure:
            raise ValueError("boom")


def test_harden_stdio_pipe_uses_utf8(monkeypatch):
    """isatty=False（管道，GUI spawn 场景）：reconfigure 必须显式挂 utf-8。

    D2026-1006-01 件⑦：frozen 下 PyInstaller 无视 PYTHONUTF8/
    PYTHONIOENCODING（2026-10-06 动态实验实证），GUI 按 utf-8 解码管道，
    编码必须显式钉 utf-8 修 frozen GBK 乱码。
    """
    from subtransjav.refine.cli import _harden_stdio
    out = _FakeStream(tty=False)
    err = _FakeStream(tty=False)
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    _harden_stdio()
    assert len(out.calls) == 1 and len(err.calls) == 1
    assert out.calls[0].get("encoding") == "utf-8", "管道必须显式挂 utf-8"
    assert out.calls[0].get("errors") == "backslashreplace"
    assert err.calls[0].get("encoding") == "utf-8"
    assert err.calls[0].get("errors") == "backslashreplace"


def test_harden_stdio_tty_keeps_encoding_untouched(monkeypatch):
    """isatty=True（真实终端）：只放宽 errors，encoding 不动（cp936 中文照常）。"""
    from subtransjav.refine.cli import _harden_stdio
    out = _FakeStream(tty=True)
    err = _FakeStream(tty=True)
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    _harden_stdio()
    assert len(out.calls) == 1 and len(err.calls) == 1
    assert "encoding" not in out.calls[0], "tty 场景不得改挂 encoding"
    assert out.calls[0] == {"errors": "backslashreplace"}
    assert "encoding" not in err.calls[0]
    assert err.calls[0] == {"errors": "backslashreplace"}


def test_harden_stdio_tolerates_broken_streams(monkeypatch):
    """无 reconfigure 属性 / reconfigure 抛 ValueError / isatty 抛 OSError：
    全部静默跳过，绝不外抛影响主流程。"""
    from subtransjav.refine.cli import _harden_stdio
    no_attr = _FakeStream(tty=False, support_reconfigure=False)
    broken = _FakeStream(tty=False, fail_reconfigure=True)
    broken_tty = _FakeStream(tty=True, fail_isatty=True)
    monkeypatch.setattr("sys.stdout", no_attr)
    monkeypatch.setattr("sys.stderr", broken_tty)
    _harden_stdio()  # stdout 无属性 + stderr isatty 抛错，不应外抛
    assert no_attr.calls == []
    assert broken_tty.calls == []
    # 再单独验证 reconfigure 抛 ValueError 的流（管道场景：kwargs 先记录后抛错）
    monkeypatch.setattr("sys.stdout", broken)
    monkeypatch.setattr("sys.stderr", _FakeStream(tty=False))
    _harden_stdio()
    assert broken.calls == [{"encoding": "utf-8", "errors": "backslashreplace"}]
