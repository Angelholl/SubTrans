"""2.6.0 批 2 聚合数据层（D2026-1002-03）测试：只读聚合层+注入装配+双钉。"""
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from subtransjav.refine import aggregate_stats as ags
from subtransjav.refine import quality_advisor as qa

# ---------------------------------------------------------------------------
# 夹具
# ---------------------------------------------------------------------------

def _guide(stem, generated_at, open_n=3, cps_n=1, obs_n=1, extra_cats=None):
    items = []
    for i in range(open_n):
        cat = "cps_too_fast" if i < cps_n else (extra_cats or "untranslated")
        items.append({"index": i + 1, "timing": f"T{i}", "category": cat,
                      "message": f"周边片原文_{stem}_{i}",
                      "current_text": f"周边片现译_{stem}_{i}",
                      "source_excerpt": "src", "status": "open",
                      "severity": None})
    for i in range(obs_n):
        items.append({"index": 100 + i, "timing": f"O{i}",
                      "category": "suspected_missed_speech",
                      "message": "疑似漏听", "current_text": None,
                      "source_excerpt": "", "status": "observation",
                      "severity": None})
    return {"version": 2, "stem": stem, "generated_at": generated_at,
            "items": items}


def _write_guide(tmp_path: Path, stem, **kw) -> Path:
    p = tmp_path / f"{stem}_质量报告导读.json"
    p.write_text(json.dumps(_guide(stem, **kw), ensure_ascii=False),
                 encoding="utf-8")
    return p


# ---------------------------------------------------------------------------
# collect_directory_stats
# ---------------------------------------------------------------------------

def test_collect_orders_desc_excludes_current_and_caps(tmp_path):
    for i in range(25):
        _write_guide(tmp_path, f"ep{i:02d}",
                     generated_at=f"2026-01-{i % 28 + 1:02d} 00:00:00")
    stats, skipped = ags.collect_directory_stats(str(tmp_path), "ep00")
    assert skipped == 0
    assert len(stats) == ags._SCAN_LIMIT == 20          # 枚举上限 20
    assert all(s["stem"] != "ep00" for s in stats)      # 排除当前片
    generated = [s["generated_at"] for s in stats]
    assert generated == sorted(generated, reverse=True)  # 降序


def test_collect_skips_bad_json_and_missing_dir(tmp_path):
    (tmp_path / "bad_质量报告导读.json").write_text("{broken", encoding="utf-8")
    (tmp_path / "empty_质量报告导读.json").write_text(
        json.dumps({"version": 2}), encoding="utf-8")
    stats, skipped = ags.collect_directory_stats(str(tmp_path), "x")
    assert stats == [] and skipped == 2
    assert ags.collect_directory_stats(str(tmp_path / "不存在"), "x") == ([], 0)


# ---------------------------------------------------------------------------
# build_aggregate_block：白名单/字段名契约（C4 静态钉）
# ---------------------------------------------------------------------------

def test_block_whitelist_and_field_names(tmp_path):
    _write_guide(tmp_path, "ep02", generated_at="2026-01-02 00:00:00",
                 open_n=4, cps_n=2)
    cur = _guide("ep01", "2026-01-03 00:00:00", open_n=6, cps_n=3)["items"]
    block = ags.build_aggregate_block(str(tmp_path), "ep01",
                                      current_items=cur,
                                      tm_db_path=str(tmp_path / "no.db"))
    assert block, "有基线片时必须产出聚合块"
    # C4 字段名精确契约
    assert "CPS行动密度(单片上限20)" in block
    assert "open项数" in block
    assert "n=1" in block
    assert "n 过小不可作为可靠基线" in block
    assert "分母未埋点" in block
    assert "≥20" in block
    assert "不改变任何默认阈值/白名单" in block
    # 基线计数在（ep02 open=4）
    assert "ep02=4" in block
    assert "当前片=6" in block and "当前片=3" in block
    # 白名单：周边片字幕原文绝不出现在块内
    assert "周边片原文" not in block
    assert "周边片现译" not in block
    # 长度上限
    assert len(block) <= ags._AGG_BLOCK_CHAR_LIMIT


def test_block_empty_when_single_film_and_no_tm(tmp_path):
    _write_guide(tmp_path, "ep01", generated_at="2026-01-02 00:00:00")
    block = ags.build_aggregate_block(str(tmp_path), "ep01",
                                      current_items=[],
                                      tm_db_path=str(tmp_path / "no.db"))
    assert block == ""


def test_block_truncates_at_char_limit(tmp_path):
    for i in range(20):
        _write_guide(tmp_path, f"long-stem-{i:02d}",
                     generated_at=f"2026-01-{i % 28 + 1:02d} 00:00:00")
    block = ags.build_aggregate_block(str(tmp_path), "zzz",
                                      current_items=[],
                                      tm_db_path=str(tmp_path / "no.db"))
    assert len(block) <= ags._AGG_BLOCK_CHAR_LIMIT


# ---------------------------------------------------------------------------
# query_tm_summary：只读纪律（C3）
# ---------------------------------------------------------------------------

def _make_tm_db(path: Path):
    con = sqlite3.connect(str(path))
    con.execute("CREATE TABLE tm_entries (id INTEGER PRIMARY KEY, "
                "source_name TEXT, created_at REAL)")
    now = 1_800_000_000.0
    con.execute("INSERT INTO tm_entries (source_name, created_at) "
                "VALUES ('ep02', ?)", (now,))
    con.execute("INSERT INTO tm_entries (source_name, created_at) "
                "VALUES ('ep01', ?)", (now,))
    con.commit()
    con.close()


def test_tm_summary_readonly_aggregates(tmp_path):
    db = tmp_path / "tm.db"
    _make_tm_db(db)
    r = ags.query_tm_summary(str(db), current_stem="ep01", days=10_000)
    assert r is not None
    assert r["total_entries"] == 2
    assert r["current_film_entries"] == 1
    assert ("ep02", 1) in r["recent_by_source"]


def test_tm_summary_missing_db_degrades(tmp_path):
    assert ags.query_tm_summary(str(tmp_path / "no.db"), "ep01") is None


def test_tm_summary_locked_db_degrades(tmp_path, monkeypatch):
    """C3：库被锁/连接失败 → 降级 None 不抛。"""
    def _raise(*a, **kw):
        raise sqlite3.OperationalError("database is locked")
    monkeypatch.setattr(ags.sqlite3, "connect", _raise)
    assert ags.query_tm_summary(str(tmp_path / "tm.db"), "ep01") is None


def test_default_tm_db_path_no_mkdir(tmp_path, monkeypatch):
    """零写路径：默认路径推导不得触发 makedirs。"""
    import subtransjav.refine.tm as tm_mod
    monkeypatch.setattr(tm_mod, "_DEFAULT_TM_DIR", str(tmp_path / "sub"))
    p = Path(ags.default_tm_db_path())
    assert p.name == "tm.db"
    assert not (tmp_path / "sub").exists()


# ---------------------------------------------------------------------------
# C6 双钉：注册 + 负向钉（不进指纹）
# ---------------------------------------------------------------------------

def test_aggregate_flag_registered_and_not_in_fingerprint():
    from subtransjav.refine.config import TUNABLE_FIELD_TYPES, RefineConfig
    from subtransjav.refine.manifest import _CONFIG_FIELDS
    assert TUNABLE_FIELD_TYPES.get("aggregate_stats_inject") is bool
    assert "aggregate_stats_inject" not in _CONFIG_FIELDS
    assert RefineConfig(inputs=["a.srt"]).aggregate_stats_inject is True


# ---------------------------------------------------------------------------
# 注入装配（C2 additive）+ 端到端开关
# ---------------------------------------------------------------------------

_OK_JSON = json.dumps({"glossary": [], "tm": [],
                       "observations": ["o"]}, ensure_ascii=False)


def test_analyze_injects_aggregate_block_additively():
    captured = {}

    def _chat(system, user):
        captured["system"] = system
        captured["user"] = user
        return _OK_JSON

    guide = _guide("ep01", "2026-01-03 00:00:00")
    qa.analyze_quality_report("【结论】x", guide, "冲突摘要", "m1",
                              chat_fn=_chat,
                              aggregate_block="跨片聚合统计内容XYZ")
    user = captured["user"]
    assert user.count(qa._DATA_BEGIN) == 4            # 3 既有+1 聚合
    assert user.count(qa._DATA_END) == 4
    assert "跨片聚合统计（只读，仅供对照参考）:" in user
    assert "跨片聚合统计内容XYZ" in user
    # 块序：冲突摘要块之后、终指令之前
    assert user.index("冲突摘要") < user.index("跨片聚合统计") \
        < user.index("请只输出符合契约的 JSON 对象")


def test_run_ai_analyze_flag_on_and_off(monkeypatch, tmp_path):
    report = tmp_path / "ep01_质量报告.txt"
    report.write_text("【结论】x\n", encoding="utf-8")
    _write_guide(tmp_path, "ep01", generated_at="2026-01-03 00:00:00")
    _write_guide(tmp_path, "ep02", generated_at="2026-01-02 00:00:00")
    # 隔离真实 tm.db：默认路径指向不存在文件 → TM 段降级 None
    monkeypatch.setattr(ags, "default_tm_db_path",
                        lambda: str(tmp_path / "no-tm" / "tm.db"))
    captured = {}

    class _FakeClient:
        def __init__(self, tag):
            self.tag = tag

        def _chat(self, system, user):
            captured[self.tag] = user
            return _OK_JSON

    clients = {"on": _FakeClient("on"), "off": _FakeClient("off")}
    monkeypatch.setattr(qa, "_make_ai_client",
                        lambda cfg, m: clients["on" if cfg.
                                                aggregate_stats_inject
                                                else "off"])
    args = SimpleNamespace(ai_analyze=str(report), ai_model="")
    for flag in (True, False):
        cfg = SimpleNamespace(
            stages=[SimpleNamespace(provider="lmstudio", model="m1")],
            aggregate_stats_inject=flag)
        rc = qa.run_ai_analyze(cfg, args)
        assert rc == 0
    # 夹具无冲突 CSV：on=报告+导读+聚合=3 块；off=报告+导读=2 块
    assert "跨片聚合统计" in captured["on"]
    assert captured["on"].count("<<<<DATA_BEGIN>>>>") == 3
    assert "跨片聚合统计" not in captured["off"]
    assert captured["off"].count("<<<<DATA_BEGIN>>>>") == 2
