"""TM 方向参数化测试（2.1，D2026-0930-04 ④ HRO-1）。

迁移回环 / 跨方向隔离 / hit_count 语言隔离 / CSV 新旧格式兼容 /
内容指纹不变式。缺省参数（不传语言）= 与旧行为等价（存量测试不动）。
"""
import csv
import hashlib
import io
import os
import re
import sqlite3
import time
from pathlib import Path

from subtransjav.refine.tm import TranslationMemory, ensure_direction_columns


def _make_tm(tmp_path):
    return TranslationMemory(os.path.join(str(tmp_path), "tm.db"))


def _make_old_schema_db(db_path: str, rows: list[tuple[str, str, int]]):
    """手工构造旧 schema 库（UNIQUE(content_hash, stage)，无语言列）。"""
    conn = sqlite3.connect(db_path)
    conn.executescript("""
        CREATE TABLE tm_entries (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            content_hash TEXT NOT NULL,
            source_text  TEXT NOT NULL,
            target_text  TEXT NOT NULL,
            stage        INTEGER NOT NULL DEFAULT 0,
            char_count   INTEGER NOT NULL DEFAULT 0,
            hit_count    INTEGER NOT NULL DEFAULT 0,
            created_at   REAL NOT NULL,
            source_name  TEXT,
            UNIQUE(content_hash, stage)
        );
    """)
    for src, tgt, stage in rows:
        norm = re.sub(r"\s+", " ", src.strip())
        h = hashlib.sha256(norm.encode("utf-8")).hexdigest()[:32]
        conn.execute(
            "INSERT INTO tm_entries (content_hash, source_text, target_text,"
            " stage, char_count, hit_count, created_at) "
            "VALUES (?, ?, ?, ?, ?, 3, ?)",
            (h, norm, tgt, stage, len(norm), time.time()))
    conn.commit()
    conn.close()


class TestDirectionMigration:
    """唯一约束升维表重建迁移（幂等）。"""

    def test_migration_roundtrip_preserves_rows(self, tmp_path):
        db = os.path.join(str(tmp_path), "old.db")
        rows = [("おはよう", "早上好", 1), ("テスト", "测试", 2)]
        _make_old_schema_db(db, rows)
        assert ensure_direction_columns(db) is True
        # 幂等：再次调用无操作
        assert ensure_direction_columns(db) is False
        tm = TranslationMemory(db)
        try:
            # 内容列逐行不变（指纹不变式：_tm_fingerprint 只哈希内容列）；
            # hit_count 在查询前读（lookup 自增会污染断言）
            conn = sqlite3.connect(db)
            got = conn.execute(
                "SELECT content_hash, stage, source_text, target_text, "
                "hit_count FROM tm_entries ORDER BY stage").fetchall()
            # 存量行回填 ja/zh
            langs = conn.execute(
                "SELECT source_lang, target_lang FROM tm_entries").fetchall()
            conn.close()
            assert len(got) == 2
            assert got[0][4] == 3
            assert langs == [("ja", "zh"), ("ja", "zh")]
            assert tm.lookup_exact("おはよう", 1) == "早上好"
            assert tm.lookup_exact("テスト", 2) == "测试"
        finally:
            tm.close()

    def test_old_unique_semantics_preserved(self, tmp_path):
        """同 hash+stage+ja/zh 重复入库仍幂等更新（旧去重语义不丢）。"""
        db = os.path.join(str(tmp_path), "old.db")
        _make_old_schema_db(db, [("おはよう", "旧译文", 1)])
        tm = TranslationMemory(db)
        try:
            added = tm.store("おはよう", "新译文", 1)
            assert added is False            # 更新而非新增
            assert tm.lookup_exact("おはよう", 1) == "新译文"
            conn = sqlite3.connect(db)
            n = conn.execute("SELECT COUNT(*) FROM tm_entries").fetchone()[0]
            conn.close()
            assert n == 1
        finally:
            tm.close()


class TestDirectionIsolation:
    """跨方向同文本各自成行，互不覆写、互不刷命中数。"""

    def test_cross_direction_no_overwrite(self, tmp_path):
        tm = _make_tm(tmp_path)
        try:
            # 同一源文本（数字串，跨语言哈希必然相同）
            tm.store("12345", "五", 1)                       # ja→zh
            added = tm.store("12345", "five", 1,
                             source_lang="zh", target_lang="en")
            assert added is True                              # 各自成行
            assert tm.lookup_exact("12345", 1) == "五"        # ja→zh 不被覆写
            assert tm.lookup_exact("12345", 1, "zh", "en") == "five"
            assert tm.has_exact("12345", 1, "ja", "en") is False
        finally:
            tm.close()

    def test_hit_count_language_isolation(self, tmp_path):
        tm = _make_tm(tmp_path)
        try:
            tm.store("12345", "五", 1)
            tm.store("12345", "five", 1, source_lang="zh", target_lang="en")
            before = tm.stats()["total_hits"]
            for _ in range(3):
                tm.lookup_exact("12345", 1, "zh", "en")
            after = tm.stats()["total_hits"]
            assert after - before == 3
            conn = sqlite3.connect(tm.db_path)
            zh_hits = conn.execute(
                "SELECT hit_count FROM tm_entries WHERE target_lang='zh'"
            ).fetchone()[0]
            conn.close()
            assert zh_hits == 0               # en 命中不刷 ja→zh 行
        finally:
            tm.close()

    def test_exact_map_and_fuzzy_language_scoped(self, tmp_path):
        tm = _make_tm(tmp_path)
        try:
            tm.store("テスト文章", "测试文章", 1)
            tm.store("テスト文章", "test passage", 1,
                     source_lang="zh", target_lang="en")
            assert tm.exact_map(["テスト文章"], 1) == \
                {"テスト文章": "测试文章"}
            assert tm.exact_map(["テスト文章"], 1, "zh", "en") == \
                {"テスト文章": "test passage"}
            assert tm.lookup_fuzzy("テスト文章", 1) != []
            # en 方向的模糊查找不串到 zh 行（按语言过滤后源行存在）
            assert tm.lookup_fuzzy("テスト文章", 1, 0.8, "zh", "en") != []
        finally:
            tm.close()


class TestDirectionCsv:
    """CSV 导入导出语言列（新格式按行值/旧格式回填缺省）。"""

    def test_csv_roundtrip_with_lang_columns(self, tmp_path):
        tm = _make_tm(tmp_path)
        try:
            tm.store("テスト", "测试", 1)
            tm.store("テスト", "test", 1, source_lang="zh", target_lang="en")
            csv_path = os.path.join(str(tmp_path), "out.csv")
            tm.export_csv(csv_path)
            tm.clear()
            assert tm.stats()["total"] == 0
            added = tm.import_csv(csv_path)
            assert added == 2
            assert tm.lookup_exact("テスト", 1) == "测试"
            assert tm.lookup_exact("テスト", 1, "zh", "en") == "test"
        finally:
            tm.close()

    def test_legacy_csv_without_lang_columns(self, tmp_path):
        tm = _make_tm(tmp_path)
        try:
            csv_path = os.path.join(str(tmp_path), "legacy.csv")
            buf = io.StringIO()
            w = csv.writer(buf)
            w.writerow(["source", "target", "stage", "hit_count"])
            w.writerow(["テスト", "旧格式译文", 1, 0])
            Path(csv_path).write_text(buf.getvalue(), encoding="utf-8-sig")
            assert tm.import_csv(csv_path) == 1
            # 旧格式回填缺省 ja/zh
            assert tm.lookup_exact("テスト", 1) == "旧格式译文"
        finally:
            tm.close()
