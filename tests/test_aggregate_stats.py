"""2.6.0 批 2 修订（D2026-1002-05）测试：TM 库窗口对比+注入装配+双钉。

owner 修订口径：统计源=保存的翻译记忆库（不做同目录扫描）；窗口三档
7/30/永久用户可选。
"""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from subtransjav.refine import aggregate_stats as ags
from subtransjav.refine import quality_advisor as qa


def _make_tm_db(path: Path, rows: list[tuple[str, float]]):
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE tm_entries (id INTEGER PRIMARY KEY, "
                "source_name TEXT, created_at REAL)")
    for stem, ts in rows:
        con.execute("INSERT INTO tm_entries (source_name, created_at) "
                    "VALUES (?, ?)", (stem, ts))
    con.commit()
    con.close()


def test_tm_summary_windows(monkeypatch, tmp_path):
    """窗口三档：7/30 天按 created_at 回看，all=永久（全库）。"""
    import time
    db = tmp_path / "tm.db"
    now = time.time()
    _make_tm_db(db, [("ep01", now), ("ep02", now - 3 * 86400),
                     ("ep03", now - 60 * 86400)])
    r7 = ags.query_tm_summary(str(db), "ep01", window_days=7)
    assert r7["window_added"] == 2 and r7["current_film_entries"] == 1
    assert r7["other_films"] == 2
    r30 = ags.query_tm_summary(str(db), "ep01", window_days=30)
    assert r30["window_added"] == 2
    rall = ags.query_tm_summary(str(db), "ep01", window_days=None)
    assert rall["window_added"] == 3 and rall["total_entries"] == 3
    assert ("ep03", 1) in rall["recent_by_source"]


def test_tm_summary_missing_db_degrades(tmp_path):
    assert ags.query_tm_summary(str(tmp_path / "no.db"), "ep") is None


def test_tm_summary_locked_db_degrades(monkeypatch, tmp_path):
    def _raise(*a, **kw):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(ags.sqlite3, "connect", _raise)
    assert ags.query_tm_summary(str(tmp_path / "tm.db"), "ep") is None


def test_block_window_label_and_declaration(tmp_path):
    db = tmp_path / "tm.db"
    now = 1_900_000_000.0
    _make_tm_db(db, [("ep02", now), ("ep03", now - 86400)])
    block = ags.build_aggregate_block(tm_db_path=str(db),
                                      current_stem="ep01", window_days=7)
    assert block, "有 TM 数据时必须产出聚合块"
    assert "统计源＝保存的翻译记忆库" in block
    assert "近 7 天" in block
    assert "未库化" in block                      # CPS/风险未库化如实声明
    assert "不改变任何默认阈值/白名单" in block
    assert "ep01" in block and "ep02" in block
    block_all = ags.build_aggregate_block(tm_db_path=str(db),
                                          current_stem="ep01",
                                          window_days=None)
    assert "永久（全部）" in block_all


def test_block_empty_when_db_missing(tmp_path):
    assert ags.build_aggregate_block(tm_db_path=str(tmp_path / "no.db"),
                                     current_stem="ep01") == ""


def test_block_truncates_at_char_limit(monkeypatch, tmp_path):
    db = tmp_path / "tm.db"
    now = 1_900_000_000.0
    rows = [(f"very-long-stem-{i:03d}-aaaaaaaaaaaaaaaa", now - i)
            for i in range(200)]
    _make_tm_db(db, rows)
    block = ags.build_aggregate_block(tm_db_path=str(db),
                                      current_stem="zzz", window_days=30)
    assert len(block) <= ags._AGG_BLOCK_CHAR_LIMIT


def test_default_tm_db_path_no_mkdir(tmp_path, monkeypatch):
    """零写路径：默认路径推导不得触发 makedirs。"""
    import subtransjav.refine.tm as tm_mod
    monkeypatch.setattr(tm_mod, "_DEFAULT_TM_DIR", str(tmp_path / "sub"))
    p = Path(ags.default_tm_db_path())
    assert p.name == "tm.db"
    assert not (tmp_path / "sub").exists()


# ---------------------------------------------------------------------------
# C6 双钉（批 2 原有）+ 修订新增：tm_stats_window 负向钉
# ---------------------------------------------------------------------------

def test_aggregate_flag_registered_and_not_in_fingerprint():
    from subtransjav.refine.config import TUNABLE_FIELD_TYPES, RefineConfig
    from subtransjav.refine.manifest import _CONFIG_FIELDS
    assert TUNABLE_FIELD_TYPES.get("aggregate_stats_inject") is bool
    assert "aggregate_stats_inject" not in _CONFIG_FIELDS
    assert RefineConfig(inputs=["a.srt"]).aggregate_stats_inject is True


def test_tm_stats_window_flag_not_in_fingerprint():
    """owner 修订：--tm-stats-window 三档旗标不入 manifest 指纹。"""
    from subtransjav.refine.manifest import _CONFIG_FIELDS
    assert "tm_stats_window" not in _CONFIG_FIELDS


def test_window_map_contract():
    assert ags.WINDOW_MAP == {"7": 7, "30": 30, "all": None}
    assert ags.WINDOW_CHOICES == ("7", "30", "all")


# ---------------------------------------------------------------------------
# 注入 additive（C2）+ 端到端窗口透传
# ---------------------------------------------------------------------------

_OK_JSON = json.dumps({"glossary": [], "tm": [],
                       "observations": ["o"]}, ensure_ascii=False)


def test_analyze_injects_aggregate_block_additively():
    captured = {}

    def _chat(system, user):
        captured["user"] = user
        return _OK_JSON

    guide = {"version": 2, "items": []}
    qa.analyze_quality_report("【结论】x", guide, "冲突摘要", "m1",
                              chat_fn=_chat,
                              aggregate_block="跨片聚合统计内容XYZ")
    user = captured["user"]
    assert user.count(qa._DATA_BEGIN) == 4            # 3 既有+1 聚合
    assert "跨片聚合统计（只读，仅供对照参考）:" in user
    assert "跨片聚合统计内容XYZ" in user
    assert user.index("冲突摘要") < user.index("跨片聚合统计") \
        < user.index("请只输出符合契约的 JSON 对象。")


def test_run_ai_analyze_aggregate_window_passthrough(monkeypatch, tmp_path):
    """端到端：TM 库对照进分析 prompt（隔离真实 tm.db）。"""
    report = tmp_path / "ep01_质量报告.txt"
    report.write_text("【结论】x\n", encoding="utf-8")
    guide_p = tmp_path / "ep01_质量报告导读.json"
    guide_p.write_text(json.dumps({"version": 2, "stem": "ep01",
                                   "items": []}, ensure_ascii=False),
                       encoding="utf-8")
    db = tmp_path / "tm.db"
    _make_tm_db(db, [("other01", 1_900_000_000.0)])
    monkeypatch.setattr(ags, "default_tm_db_path", lambda: str(db))
    captured = {}

    class _FakeClient:
        def _chat(self, system, user):
            captured["user"] = user
            return _OK_JSON

    monkeypatch.setattr(qa, "_make_ai_client",
                        lambda cfg, m: _FakeClient())
    args = SimpleNamespace(ai_analyze=str(report), ai_model="",
                           tm_stats_window="30", asr_python="",
                           asr_model="")
    cfg = SimpleNamespace(
        stages=[SimpleNamespace(provider="lmstudio", model="m1")],
        aggregate_stats_inject=True, media_crosscheck_enabled=False)
    rc = qa.run_ai_analyze(cfg, args)
    assert rc == 0
    assert "统计源＝保存的翻译记忆库" in captured["user"]
    assert "近 30 天" in captured["user"]
    assert "ep01" in captured["user"] and "other01" in captured["user"]
