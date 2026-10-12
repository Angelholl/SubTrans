# -*- coding: utf-8 -*-
"""D2026-1003-05 批1 FTS5 三同步策略 spike（预研，不入主库）。

输入：生产 tm.db 的只读拷贝（spike/tmp/tm_copy.db）。
策略：
  A = external-content FTS5 + 列限定触发器（UPDATE OF 内容列清单，hit_count 不在面内）
  B = 显式双写模拟（store 侧写 FTS，含 python 端 NFKC 列；热路径零 FTS 成本）
  C = 重建时全量刷（python 端 NFKC 列，指纹判亚——本 spike 只测重建耗时与查询面）
测量：
  1) 建索引耗时/库体积增量   2) BM25 查询延迟（原文+归一化双口径，20 词 x 2）
  3) 热路径对拍（每 30 行批 30 次 lookup+命中 UPDATE，无 FTS 基线 vs A vs B）
  4) C2 隐患演示：先建 FTS 再做表重建迁移 -> FTS 面被碾；正确顺序（迁移后建）存活。
输出：stdout 结构化结果（由调用方落盘 spike/fts5_result.txt）。
"""
import os
import re
import shutil
import sqlite3
import sys
import time
import unicodedata
from pathlib import Path

SRC_DB = Path(r"D:/SubTransJAV/Temp/translation_memory/tm.db")
WORK = Path(__file__).resolve().parent
TMP = WORK / "tmp"
REAL_BATCH_SECONDS = {"stageA": 12.1, "stageB": 3.3}  # 校准轮口径，供占比换算
LINES_PER_BATCH = 30
REPLAY_BATCHES = 200  # 6000 次 lookup（100% 命中上限面）


def norm(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").casefold()


def fresh_db(name: str) -> Path:
    TMP.mkdir(exist_ok=True)
    p = TMP / name
    if p.exists():
        p.unlink()
    shutil.copy(SRC_DB, p)
    return p


def inspect(conn: sqlite3.Connection) -> dict:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(tm_entries)")]
    n = conn.execute("SELECT COUNT(*) FROM tm_entries").fetchone()[0]
    return {"cols": cols, "rows": n}


def make_fts_a(conn: sqlite3.Connection) -> float:
    """策略 A：external-content + 列限定触发器（仅原文列，NFKC 限制见报告）。"""
    t0 = time.perf_counter()
    conn.executescript(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS tm_fts USING fts5(
            source_text, target_text, content='tm_entries', content_rowid='rowid');
        CREATE TRIGGER IF NOT EXISTS tm_fts_ai AFTER INSERT ON tm_entries BEGIN
            INSERT INTO tm_fts(rowid, source_text, target_text)
            VALUES (new.rowid, new.source_text, new.target_text);
        END;
        CREATE TRIGGER IF NOT EXISTS tm_fts_ad AFTER DELETE ON tm_entries BEGIN
            INSERT INTO tm_fts(tm_fts, rowid, source_text, target_text)
            VALUES ('delete', old.rowid, old.source_text, old.target_text);
        END;
        CREATE TRIGGER IF NOT EXISTS tm_fts_au
        AFTER UPDATE OF source_text, target_text, content_hash, stage,
                        source_lang, target_lang ON tm_entries BEGIN
            INSERT INTO tm_fts(tm_fts, rowid, source_text, target_text)
            VALUES ('delete', old.rowid, old.source_text, old.target_text);
            INSERT INTO tm_fts(rowid, source_text, target_text)
            VALUES (new.rowid, new.source_text, new.target_text);
        END;
        INSERT INTO tm_fts(tm_fts) VALUES ('rebuild');
        """
    )
    conn.commit()
    return time.perf_counter() - t0


def make_fts_bc(conn: sqlite3.Connection, rebuild: bool) -> float:
    """策略 B/C：standalone FTS5 表（含 python 端 NFKC 列）。B=增量双写写入侧，
    C=一次性全量刷。这里统一按全量刷测建索引成本，B 的增量成本单独测。"""
    t0 = time.perf_counter()
    conn.execute(
        """CREATE VIRTUAL TABLE IF NOT EXISTS tm_fts2 USING fts5(
           source_text, target_text, norm_source, norm_target)"""
    )
    rows = conn.execute(
        "SELECT rowid, source_text, target_text FROM tm_entries"
    ).fetchall()
    conn.executemany(
        "INSERT INTO tm_fts2(rowid, source_text, target_text, norm_source, norm_target)"
        " VALUES (?,?,?,?,?)",
        [(r[0], r[1], r[2], norm(r[1]), norm(r[2])) for r in rows],
    )
    conn.commit()
    dt = time.perf_counter() - t0
    if rebuild:
        pass
    return dt


def incremental_cost_b(conn: sqlite3.Connection, n: int = 1000) -> float:
    """策略 B 单行双写增量成本（含 NFKC），外推每批（30 行新句最坏面）。"""
    rows = conn.execute(
        "SELECT source_text, target_text FROM tm_entries LIMIT ?", (n,)
    ).fetchall()
    t0 = time.perf_counter()
    for i, (s, t) in enumerate(rows):
        rid = 9_000_000 + i
        conn.execute(
            "INSERT OR REPLACE INTO tm_fts2(rowid, source_text, target_text,"
            " norm_source, norm_target) VALUES (?,?,?,?,?)",
            (rid, s, t, norm(s), norm(t)),
        )
    conn.commit()
    return (time.perf_counter() - t0) / n


def query_bench(conn: sqlite3.Connection, table: str, has_norm: bool) -> dict:
    """BM25 查询延迟：从真实行取词，原文与归一化双口径。"""
    srcs = [r[0] for r in conn.execute(
        "SELECT source_text FROM tm_entries WHERE LENGTH(source_text)>6"
        " ORDER BY rowid LIMIT 200")]
    # 取行内片段当查询词（模拟用户搜索输入）
    words = []
    for s in srcs[::10]:
        s2 = re.sub(r"[\s，。、！？「」()（）]+", " ", s).strip()
        parts = s2.split(" ")
        parts = [p for p in parts if len(p) >= 2]
        if parts:
            words.append(parts[len(parts) // 2])
    words = words[:20] or ["字幕"]
    res = {"raw_ms": 0.0, "norm_ms": 0.0, "hits": 0}
    if has_norm:
        t0 = time.perf_counter()
        for w in words:
            q = norm(w).replace('"', '""')
            cur = conn.execute(
                f"SELECT rowid FROM {table} WHERE {table} MATCH ? ORDER BY rank LIMIT 10",
                (q,))
            res["hits"] += len(cur.fetchall())
        res["norm_ms"] = (time.perf_counter() - t0) / len(words) * 1000
    t0 = time.perf_counter()
    for w in words:
        q = w.replace('"', '""')
        cur = conn.execute(
            f"SELECT rowid FROM {table} WHERE {table} MATCH ? ORDER BY rank LIMIT 10",
            (q,))
        res["hits"] += len(cur.fetchall())
    res["raw_ms"] = (time.perf_counter() - t0) / len(words) * 1000
    return res


def hotpath_replay(path: Path, label: str) -> float:
    """每批 30 次 lookup（content_hash 精确查）+ 命中即 UPDATE hit_count。"""
    conn = sqlite3.connect(path, timeout=10)
    hashes = [r[0] for r in conn.execute(
        "SELECT content_hash FROM tm_entries ORDER BY rowid LIMIT ?",
        (LINES_PER_BATCH * REPLAY_BATCHES,))]
    t0 = time.perf_counter()
    for b in range(REPLAY_BATCHES):
        chunk = hashes[b * LINES_PER_BATCH:(b + 1) * LINES_PER_BATCH]
        for h in chunk:
            row = conn.execute(
                "SELECT rowid FROM tm_entries WHERE content_hash=? AND stage=?",
                (h, "A")).fetchone() or conn.execute(
                "SELECT rowid FROM tm_entries WHERE content_hash=?", (h,)).fetchone()
            if row:
                conn.execute(
                    "UPDATE tm_entries SET hit_count=hit_count+1 WHERE rowid=?",
                    (row[0],))
        conn.commit()
    dt = time.perf_counter() - t0
    conn.close()
    print(f"  hotpath[{label}] total={dt*1000:.0f}ms "
          f"per_batch={dt/REPLAY_BATCHES*1000:.1f}ms", flush=True)
    return dt / REPLAY_BATCHES * 1000


def size_of(path: Path) -> int:
    return path.stat().st_size


def main() -> None:
    print("== 环境 ==", flush=True)
    base = fresh_db("tm_base.db")
    conn = sqlite3.connect(base)
    info = inspect(conn)
    conn.close()
    print(f"rows={info['rows']} cols={info['cols']} base_size={size_of(base)}", flush=True)

    # ---- 策略 A ----
    print("\n== 策略 A：external-content + 列限定触发器 ==", flush=True)
    dba = fresh_db("tm_a.db")
    ca = sqlite3.connect(dba)
    t_build = make_fts_a(ca)
    ca.close()
    print(f"build_rebuild={t_build:.2f}s size={size_of(dba)} "
          f"(+{size_of(dba)-size_of(base)}B)", flush=True)
    ca = sqlite3.connect(dba)
    qa = query_bench(ca, "tm_fts", has_norm=False)
    ca.close()
    print(f"query raw_avg={qa['raw_ms']:.2f}ms hits={qa['hits']}", flush=True)
    pa = hotpath_replay(dba, "A")

    # ---- 策略 B/C（同一 standalone 表，B 增量成本单测）----
    print("\n== 策略 B/C：standalone + python NFKC 列 ==", flush=True)
    dbc = fresh_db("tm_bc.db")
    cc = sqlite3.connect(dbc)
    t_full = make_fts_bc(cc, rebuild=True)
    cc.commit()
    print(f"full_rebuild={t_full:.2f}s size={size_of(dbc)} "
          f"(+{size_of(dbc)-size_of(base)}B)", flush=True)
    qb = query_bench(cc, "tm_fts2", has_norm=True)
    print(f"query raw_avg={qb['raw_ms']:.2f}ms norm_avg={qb['norm_ms']:.2f}ms "
          f"hits={qb['hits']}", flush=True)
    per_row = incremental_cost_b(cc)
    cc.close()
    print(f"B_incremental per_row={per_row*1000:.3f}ms "
          f"per_batch(30 新句)={per_row*30*1000:.1f}ms", flush=True)
    pb = hotpath_replay(dbc, "B/C(热路径零 FTS 面)")

    # ---- 热路径基线（无 FTS）----
    print("\n== 基线：无 FTS ==", flush=True)
    p0 = hotpath_replay(base, "baseline")

    # ---- 占比换算 ----
    print("\n== C1 对拍结论（对真实批耗时占比） ==", flush=True)
    for tag, per in (("A", pa), ("B/C", pb), ("baseline", p0)):
        for st, secs in REAL_BATCH_SECONDS.items():
            print(f"  {tag:8s} vs {st}({secs}s): {per/ (secs*1000) *100:.3f}%",
                  flush=True)

    # ---- C2 隐患演示 ----
    print("\n== C2 演示：先建 FTS 再表重建迁移 ==", flush=True)
    dbd = fresh_db("tm_c2.db")
    cd = sqlite3.connect(dbd)
    make_fts_a(cd)
    before = cd.execute("SELECT COUNT(*) FROM tm_fts").fetchone()[0]
    cd.executescript(
        """
        ALTER TABLE tm_entries RENAME TO tm_entries_old;
        CREATE TABLE tm_entries_new (content_hash TEXT, stage TEXT,
            source_text TEXT, target_text TEXT, hit_count INTEGER DEFAULT 0);
        INSERT INTO tm_entries_new(content_hash, stage, source_text, target_text,
            hit_count) SELECT content_hash, stage, source_text, target_text,
            hit_count FROM tm_entries_old;
        DROP TABLE tm_entries_old;
        ALTER TABLE tm_entries_new RENAME TO tm_entries;
        """
    )
    cd.commit()
    try:
        after = cd.execute("SELECT COUNT(*) FROM tm_fts").fetchone()[0]
        print(f"  重建前 FTS 行={before} 重建后 COUNT={after}"
              f"（external-content 表随内容表被碾，查询面已损坏需 rebuild）", flush=True)
    except sqlite3.OperationalError as e:
        print(f"  重建后 FTS 查询直接报错：{e}（面已损）", flush=True)
    cd.close()
    print("\nSPIKE_DONE", flush=True)


if __name__ == "__main__":
    main()
