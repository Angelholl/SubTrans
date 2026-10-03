"""2.6.4 批1 TM FTS 搜索（策略 B 显式双写，D2026-1003-05）回归测试。

覆盖五类验收场景：
① 旧库（无 FTS 表的裸 tm_entries）→ 打开自动建面 → search 可用；
② store 后可搜、UPDATE 覆盖后搜到新值（双写一致性）；
③ 全角入库半角查询命中 + 反向（NFKC 双口径）；
④ 强制走 direction-columns 表重建迁移路径后 FTS 面仍一致（C2）；
⑤ search 只读性（前后行内容不变）+ limit 钳制。
"""

import os
import sqlite3
import sys

import pytest

# Ensure project root is on sys.path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# 2.1 迁移前的旧 schema：UNIQUE(content_hash, stage)、无 source_name /
# source_lang / target_lang 列（打开即触发 ensure_source_name_column +
# ensure_direction_columns 表重建迁移链）
_LEGACY_SCHEMA = """
CREATE TABLE IF NOT EXISTS tm_entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT NOT NULL,
    source_text  TEXT NOT NULL,
    target_text  TEXT NOT NULL,
    stage        INTEGER NOT NULL DEFAULT 0,
    char_count   INTEGER NOT NULL DEFAULT 0,
    hit_count    INTEGER NOT NULL DEFAULT 0,
    created_at   REAL NOT NULL,
    UNIQUE(content_hash, stage)
);
"""

# 现行 schema（新库，含方向列）
_CURRENT_SCHEMA = """
CREATE TABLE IF NOT EXISTS tm_entries (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    content_hash TEXT NOT NULL,
    source_text  TEXT NOT NULL,
    target_text  TEXT NOT NULL,
    stage        INTEGER NOT NULL DEFAULT 0,
    char_count   INTEGER NOT NULL DEFAULT 0,
    hit_count    INTEGER NOT NULL DEFAULT 0,
    created_at   REAL NOT NULL,
    source_name  TEXT,
    source_lang  TEXT NOT NULL DEFAULT 'ja',
    target_lang  TEXT NOT NULL DEFAULT 'zh',
    UNIQUE(content_hash, stage, source_lang, target_lang)
);
"""


def _make_tm(tmp_path, name="tm_search.db"):
    from subtransjav.refine.tm import TranslationMemory
    db_path = os.path.join(str(tmp_path), name)
    return TranslationMemory(db_path), db_path


def _legacy_row(conn, source, target, stage=1, row_id=None):
    """按旧 schema 直插一行（content_hash 值对 FTS 搜索无影响）。"""
    cols = ("(id, content_hash, source_text, target_text, stage, "
            "char_count, hit_count, created_at)" if row_id is not None else
            "(content_hash, source_text, target_text, stage, "
            "char_count, hit_count, created_at)")
    vals = ("(?, ?, ?, ?, ?, ?, 0, 0)" if row_id is not None else
            "(?, ?, ?, ?, ?, 0, 0)")
    params = ((row_id,) if row_id is not None else ()) + \
        ("h" + source, source, target, stage, len(source))
    conn.execute(f"INSERT INTO tm_entries {cols} VALUES {vals}", params)


def _fts_counts(conn):
    entries = conn.execute("SELECT COUNT(*) FROM tm_entries").fetchone()[0]
    fts = conn.execute("SELECT COUNT(*) FROM tm_fts").fetchone()[0]
    return entries, fts


def _snapshot_rows(conn):
    return conn.execute(
        "SELECT id, source_text, target_text, hit_count, created_at "
        "FROM tm_entries ORDER BY id").fetchall()


# ---------------------------------------------------------------------------
# ① 旧库（无 FTS 表的裸 tm_entries）→ 打开自动建面 → search 可用
# ---------------------------------------------------------------------------

class TestLegacyDbAutoFts:
    def test_legacy_db_without_fts_opens_and_searches(self, tmp_path):
        db_path = os.path.join(str(tmp_path), "legacy.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(_LEGACY_SCHEMA)
        _legacy_row(conn, "おはようございます", "早上好")
        _legacy_row(conn, "こんにちは", "你好")
        conn.commit()
        conn.close()

        from subtransjav.refine.tm import TranslationMemory
        tm = TranslationMemory(db_path)
        try:
            # 打开即自动建面（幂等迁移链末端 _ensure_fts）
            with sqlite3.connect(db_path) as chk:
                entries, fts = _fts_counts(chk)
            assert (entries, fts) == (2, 2), "FTS 面未随打开自动建立"
            # 迁移链已把旧库升到新 schema
            with sqlite3.connect(db_path) as chk:
                cols = {r[1] for r in chk.execute(
                    "PRAGMA table_info(tm_entries)")}
            assert {"source_name", "source_lang", "target_lang"} <= cols

            hits = tm.search("おはようございます")
            assert [h["target_text"] for h in hits] == ["早上好"]
            # 返回字段契约
            assert set(hits[0]) == {"id", "source_text", "target_text",
                                    "stage", "hit_count", "created_at"}
            assert tm.search("こんにちは")[0]["target_text"] == "你好"
        finally:
            tm.close()

    def test_ensure_fts_reentrant_idempotent(self, tmp_path):
        """重入 _ensure_fts（面已一致）不重建不炸。"""
        tm, db_path = _make_tm(tmp_path)
        try:
            tm.store("テスト", "测试", stage=1)
            tm._ensure_fts()
            tm._ensure_fts()
            with sqlite3.connect(db_path) as chk:
                assert _fts_counts(chk) == (1, 1)
            assert tm.search("テスト")[0]["target_text"] == "测试"
        finally:
            tm.close()


# ---------------------------------------------------------------------------
# ② store 后可搜、UPDATE 覆盖后搜到新值（双写一致性）
# ---------------------------------------------------------------------------

class TestStoreDoubleWrite:
    def test_store_then_search_and_update_overwrites(self, tmp_path):
        tm, _ = _make_tm(tmp_path)
        try:
            assert tm.store("今日はいい天気ですね",
                            "今天天气真不错呢", stage=1) is True
            hits = tm.search("今日はいい天気ですね")
            assert len(hits) == 1
            assert hits[0]["target_text"] == "今天天气真不错呢"
            assert hits[0]["stage"] == 1

            # 同 hash+stage+方向再 store → UPDATE 分支，FTS 行同步重写
            assert tm.store("今日はいい天気ですね",
                            "今天天气真好呀", stage=1) is False
            hits = tm.search("今日はいい天気ですね")
            assert [h["target_text"] for h in hits] == ["今天天气真好呀"], \
                "UPDATE 覆盖后 FTS 面未同步（双写一致性破坏）"

            # 旧译文不再命中（面内已重写）
            assert tm.search("今天天气真不错呢") == []
        finally:
            tm.close()

    def test_store_batch_double_writes_all_pairs(self, tmp_path):
        tm, db_path = _make_tm(tmp_path)
        try:
            added = tm.store_batch([
                ("おはよう", "早上好", 1),
                ("さようなら", "再见", 1),
                ("また明日", "明天见", 2),
            ])
            assert added == 3
            with sqlite3.connect(db_path) as chk:
                assert _fts_counts(chk) == (3, 3)
            assert tm.search("おはよう")[0]["target_text"] == "早上好"
            assert tm.search("さようなら")[0]["target_text"] == "再见"
            assert tm.search("また明日")[0]["target_text"] == "明天见"

            # clear 后同会话内 FTS 即刻一致（连带清面）
            tm.clear()
            assert tm.search("おはよう") == []
            with sqlite3.connect(db_path) as chk:
                assert _fts_counts(chk) == (0, 0)
        finally:
            tm.close()


# ---------------------------------------------------------------------------
# ③ 全角入库半角查询命中 + 反向（NFKC 双口径）
# ---------------------------------------------------------------------------

class TestNfkcDualCaliber:
    def test_fullwidth_stored_halfwidth_query_hits(self, tmp_path):
        tm, _ = _make_tm(tmp_path)
        try:
            # 空格分词保证目标词独立成 token（unicode61 不切 CJK 连写）
            tm.store("ＣＡＴ が 好き", "喜欢猫", stage=1)
            hits = tm.search("cat")          # 半角小写查询命中全角入库
            assert hits, "半角查询未命中全角入库内容（NFKC 归一列失效）"
            assert hits[0]["target_text"] == "喜欢猫"
        finally:
            tm.close()

    def test_halfwidth_stored_fullwidth_query_hits(self, tmp_path):
        tm, _ = _make_tm(tmp_path)
        try:
            tm.store("cat が 好き", "喜欢猫", stage=1)
            hits = tm.search("ＣＡＴ")        # 全角查询命中半角入库
            assert hits, "全角查询未命中半角入库内容（NFKC 归一列失效）"
            assert hits[0]["target_text"] == "喜欢猫"
        finally:
            tm.close()

    def test_casefold_dual_caliber(self, tmp_path):
        tm, _ = _make_tm(tmp_path)
        try:
            tm.store("Hello World", "你好世界", stage=1)
            assert tm.search("hello world")[0]["target_text"] == "你好世界"
            assert tm.search("HELLO WORLD")[0]["target_text"] == "你好世界"
        finally:
            tm.close()


# ---------------------------------------------------------------------------
# ④ 强制走 direction-columns 表重建迁移路径后 FTS 面仍一致（C2）
# ---------------------------------------------------------------------------

class TestRebuildMigrationCoherence:
    def test_c2_rebuild_migration_rebuilds_fts(self, tmp_path):
        """预研 C2 损面场景闭环：旧库预置 FTS 面（旧行非连续 rowid）→
        打开触发表重建迁移（AUTOINCREMENT 重排 id）→ FTS 面必须连带
        重建使 rowid 重新对齐，搜索返回正确译文。"""
        db_path = os.path.join(str(tmp_path), "c2.db")
        conn = sqlite3.connect(db_path)
        conn.executescript(_LEGACY_SCHEMA)
        # 非连续 id（模拟历史删行）：迁移重建后 AUTOINCREMENT 重排为 1、2
        _legacy_row(conn, "おはよう", "早上好", row_id=5)
        _legacy_row(conn, "こんにちは", "你好", row_id=10)
        # 模拟"先建 FTS 后迁移"：按旧 rowid 预置面（迁移后必失连）
        conn.execute(
            "CREATE VIRTUAL TABLE tm_fts USING fts5"
            "(source_text, target_text, norm_source, norm_target)")
        for rid, src, tgt in ((5, "おはよう", "早上好"),
                              (10, "こんにちは", "你好")):
            conn.execute(
                "INSERT INTO tm_fts(rowid, source_text, target_text, "
                "norm_source, norm_target) VALUES (?, ?, ?, ?, ?)",
                (rid, src, tgt, src, tgt))
        conn.commit()
        conn.close()

        from subtransjav.refine.tm import TranslationMemory
        tm = TranslationMemory(db_path)
        try:
            # 打开即迁移重建：新 schema + FTS 面连带重建
            with sqlite3.connect(db_path) as chk:
                cols = {r[1] for r in chk.execute(
                    "PRAGMA table_info(tm_entries)")}
                assert "source_lang" in cols, "表重建迁移未执行"
                assert _fts_counts(chk) == (2, 2), "重建后 FTS 面行数不一致"
            # rowid 对齐：搜索按新 id join 命中正确译文（旧行 id 5→新 1）
            hits = tm.search("おはよう")
            assert [h["target_text"] for h in hits] == ["早上好"], \
                "表重建迁移后 FTS rowid 失连（C2 义务未闭环）"
            assert [h["target_text"]
                    for h in tm.search("こんにちは")] == ["你好"]
            # 迁移后继续 store 双写正常（新行可搜）
            tm.store("また明日", "明天见", stage=1)
            assert tm.search("また明日")[0]["target_text"] == "明天见"
            with sqlite3.connect(db_path) as chk:
                assert _fts_counts(chk) == (3, 3)
        finally:
            tm.close()


# ---------------------------------------------------------------------------
# ⑤ search 只读性（前后行内容不变）+ limit 钳制
# ---------------------------------------------------------------------------

class TestSearchReadonlyAndLimit:
    def test_search_is_readonly(self, tmp_path):
        tm, db_path = _make_tm(tmp_path)
        try:
            tm.store_batch([
                ("aaa bbb", "第一", 1),
                ("aaa ccc", "第二", 1),
            ])
            with sqlite3.connect(db_path) as chk:
                before = _snapshot_rows(chk)

            assert tm.search("aaa") is not None
            tm.search("aaa", limit=1)
            tm.search("不存在词xyz")

            with sqlite3.connect(db_path) as chk:
                after = _snapshot_rows(chk)
            assert before == after, "search 改动了 tm_entries 行内容" \
                "（hit_count/内容不得被只读搜索触碰）"
        finally:
            tm.close()

    def test_search_limit_clamped(self, tmp_path):
        tm, _ = _make_tm(tmp_path)
        try:
            tm.store_batch([(f"zzz item{i}", f"条目{i}", 1)
                            for i in range(5)])
            assert len(tm.search("zzz", limit=3)) == 3
            # 下钳 1：limit=0 → 至少返回 1 条
            assert len(tm.search("zzz", limit=0)) == 1
            assert len(tm.search("zzz", limit=-5)) == 1
            # 上钳 200：limit=999 不越界（5 条全出）
            assert len(tm.search("zzz", limit=999)) == 5
        finally:
            tm.close()

    def test_search_empty_and_no_match(self, tmp_path):
        tm, _ = _make_tm(tmp_path)
        try:
            tm.store("テスト", "测试", stage=1)
            assert tm.search("") == []
            assert tm.search("   ") == []
            assert tm.search("存在しない言葉") == []
        finally:
            tm.close()


# ---------------------------------------------------------------------------
# 补充：MATCH 语法注入面收口（引号包裹转义钉）
# ---------------------------------------------------------------------------

class TestMatchSyntaxSafety:
    def test_match_operator_injection_neutralized(self, tmp_path):
        """查询词含 FTS5 语法字符（引号/冒号/运算符）不逃逸、不报错。"""
        tm, _ = _make_tm(tmp_path)
        try:
            tm.store("tail note text", "尾注文本", stage=1)
            for evil in ('"尾注', "tail:", "tail OR note",
                         "tail NOT note", 'note" OR target_text MATCH'):
                # 语法串被引号包裹转义后按字面 token 处理：不抛
                # OperationalError（语法错误），只可能零命中
                tm.search(evil)
        finally:
            tm.close()


if __name__ == "__main__":
    pytest.main([__file__, "-q"])
