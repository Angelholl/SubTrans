"""
翻译记忆库 (Translation Memory)
================================
基于 SQLite 的句子级翻译记忆：避免对相同/高度相似内容重复调用 API。
与词库（术语级）互补——TM 是句子级。

存储格式：
  source_text  原文（日文/中文）
  target_text  译文
  stage        来源阶段 (1/2/3)
  char_count   原文字符数（用于快速过滤）
  created_at   创建时间戳
  hit_count    命中次数（自学习排序）
  source_name  来源 srt 文件名 stem（v1.2.2 起；旧行为 NULL 不回填）
  source_lang  源语言码（2.1 方向参数化起；存量行迁移回填 'ja'）
  target_lang  目标语言码（2.1 起存量行回填 'zh'）

匹配策略：
  精确匹配（O(1) 哈希查找）→ 返回完全一致的译文
  模糊匹配（字符重叠率 ≥ threshold）→ 返回候选项供提示
"""

import hashlib
import os
import sqlite3
import time
from pathlib import Path

from subtransjav import paths

# 数据路径统一收口（frozen 下解析到数据根；源码形态与旧
# __file__ 三层 dirname 写法逐字节一致）
_DEFAULT_TM_DIR = paths.data_subdir("Temp", "translation_memory")

# exact_map 单批 IN 查询的哈希个数上限（sqlite 变量上限默认 999，留安全余量）
_EXACT_MAP_CHUNK = 500


def _default_tm_path() -> str:
    os.makedirs(_DEFAULT_TM_DIR, exist_ok=True)
    return os.path.join(_DEFAULT_TM_DIR, "tm.db")


def _normalize(text: str) -> str:
    """归一化：去首尾空白、合并连续空白"""
    import re
    return re.sub(r"\s+", " ", (text or "").strip())


def _simhash(text: str) -> str:
    """内容哈希（用于精确匹配的快速索引）"""
    return hashlib.sha256(_normalize(text).encode("utf-8")).hexdigest()[:32]


def ensure_source_name_column(db_path: str) -> bool:
    """幂等迁移：tm_entries 缺 source_name 列时补加（v1.2.2 批次 A2）。

    - 已存在（或表尚未创建）→ 什么都不做，可安全重复调用（幂等）；
    - 旧行保持 NULL，不回填（历史行无来源信息，回填即造假）；
    - 在 TranslationMemory 初始化/打开路径自动调用，旧库打开即自动迁移。
    返回是否实际执行了加列。

    schema 变化对 TM 指纹/manifest 的影响（只说明，不改指纹逻辑）:
    - 加列本身不影响 TM 指纹：pipeline_v2._tm_fingerprint 只哈希内容列
      _TM_FINGERPRINT_COLUMNS = (content_hash, stage, source_text,
      target_text)，source_name 属 provenance 簿记列、不参与指纹——
      迁移前后 manifest.tm_sha1 不变，既有 --resume 清单不因本次迁移失效；
    - source_name 的写入/更新同样不改指纹（指纹列集合未变）；真正使指纹
      变化的是 TM 内容行的新增/修改/删除（如 tools/tm_purge.py --yes
      清洗删行）——指纹必变，旧 resume 清单校验失败，须按 tm_purge
      风险声明 1 处置（删旧 resume 产物，禁止复用）。
    """
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tm_entries)")}
        if not cols or "source_name" in cols:
            return False
        conn.execute("ALTER TABLE tm_entries ADD COLUMN source_name TEXT")
        conn.commit()
        return True
    finally:
        conn.close()


def ensure_direction_columns(db_path: str) -> bool:
    """幂等迁移（2.1 方向参数化，D2026-0930-04 ④ HRO-1）：唯一约束升维。

    旧约束 ``UNIQUE(content_hash, stage)`` 在跨方向同文本（日中同汉字盘、
    数字、纯符号——content_hash 必然相同）下，zh→en 入库会命中既有 ja→zh
    行走 UPDATE 分支**静默覆写存量译文**。升维为
    ``UNIQUE(content_hash, stage, source_lang, target_lang)``：
    - SQLite 不能 ALTER 改 UNIQUE → 建新表+拷贝+改名（表重建迁移）；
    - 存量行回填 source_lang='ja' / target_lang='zh'（历史行即缺省方向，
      回填不是造假：方向字段是机制列非 provenance）；
    - 旧约束保证 (content_hash, stage) 无重复行，加常量列拷贝不可能违反
      新约束，迁移无歧义；
    - 内容列（content_hash/stage/source_text/target_text/hit_count）逐行
      不变 → pipeline_v2._tm_fingerprint（内容列指纹）迁移前后一致，
      既有 --resume 清单不因本次迁移失效；
    - 已是新 schema（含 source_lang）或表尚未创建 → 什么都不做，可安全
      重复调用（幂等）；在 TranslationMemory._init_db 自动调用。
    返回是否实际执行了表重建。
    """
    conn = sqlite3.connect(db_path, timeout=10)
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(tm_entries)")}
        if not cols or "source_lang" in cols:
            return False
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tm_entries_new (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
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
            INSERT INTO tm_entries_new
                (content_hash, source_text, target_text, stage, char_count,
                 hit_count, created_at, source_name, source_lang, target_lang)
            SELECT content_hash, source_text, target_text, stage, char_count,
                   hit_count, created_at, source_name, 'ja', 'zh'
            FROM tm_entries;
            DROP TABLE tm_entries;
            ALTER TABLE tm_entries_new RENAME TO tm_entries;
            CREATE INDEX IF NOT EXISTS idx_tm_hash
                ON tm_entries(content_hash);
            CREATE INDEX IF NOT EXISTS idx_tm_chars
                ON tm_entries(char_count);
        """)
        conn.commit()
        return True
    finally:
        conn.close()


class TranslationMemory:
    """SQLite 翻译记忆库"""

    def __init__(self, db_path: str = "",
                 source_lang: str = "ja", target_lang: str = "zh"):
        self.db_path = db_path or _default_tm_path()
        # 2.1 方向参数化（D2026-0930-05 批内缺陷修复）：实例缺省方向——
        # 管线/CLI 构造时传入任务方向，store/lookup 未显式传参时回落到它
        # （修复 zh→en 任务学出的行落 ('ja','zh') 缺省列）；裸构造缺省
        # ja/zh 与旧行为逐字节等价（API 兼容零破坏，GUI/工具零改动）。
        self.source_lang = source_lang
        self.target_lang = target_lang
        os.makedirs(os.path.dirname(self.db_path) or ".", exist_ok=True)
        self._conn: sqlite3.Connection | None = None
        self._init_db()

    def _langs(self, source_lang: str | None,
               target_lang: str | None) -> tuple:
        """语言参数解析：None 回落实例缺省（显式传参原样透传，优先级最高）。"""
        return (source_lang if source_lang is not None else self.source_lang,
                target_lang if target_lang is not None else self.target_lang)

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, timeout=10)
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        return self._conn

    def _init_db(self):
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS tm_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
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
            CREATE INDEX IF NOT EXISTS idx_tm_hash
                ON tm_entries(content_hash);
            CREATE INDEX IF NOT EXISTS idx_tm_chars
                ON tm_entries(char_count);
        """)
        conn.commit()
        # v1.2.2：旧库打开即自动补 source_name 列（幂等迁移，新建库无操作）
        ensure_source_name_column(self.db_path)
        # 2.1：唯一约束升维表重建迁移（幂等；旧库打开即自动迁移）
        ensure_direction_columns(self.db_path)

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    # ------------------------------------------------------------------
    # 存储
    # ------------------------------------------------------------------

    def store(self, source: str, target: str, stage: int = 0,
              source_name: str | None = None,
              source_lang: str | None = None,
              target_lang: str | None = None) -> bool:
        """存入翻译对。已存在（同 hash + stage + 方向）则更新译文。返回是否新增。

        source_name：来源 srt 文件名 stem（provenance，v1.2.2 起）。
        新插入时写入；覆盖已有条目时仅在该值非 None 时更新
        （COALESCE 保留旧 provenance，None 不回填）。

        source_lang/target_lang（2.1 方向参数化，D2026-0930-04 ④）：None
        （缺省）回落实例缺省方向（D2026-0930-05 批内缺陷修复），显式传参
        优先；跨方向同文本各自成行，互不覆写。

        无竞态实现：INSERT OR IGNORE 的 rowcount 直接区分 新插入(1)/
        已存在(0)，无需前置 SELECT（消除 SELECT 与写入之间的竞态窗口；
        实测 conn.total_changes 对 REPLACE 无论新增还是覆盖差值均为 1，
        无法区分，故不用）。已存在时走 UPDATE：保留原 hit_count 与
        created_at，与原 INSERT OR REPLACE + COALESCE(hit_count) 语义一致。
        """
        source_lang, target_lang = self._langs(source_lang, target_lang)
        src = _normalize(source)
        tgt = _normalize(target)
        if not src or not tgt:
            return False
        h = _simhash(src)
        conn = self._get_conn()
        cur = conn.execute(
            "INSERT OR IGNORE INTO tm_entries "
            "(content_hash, source_text, target_text, stage, char_count, "
            "hit_count, created_at, source_name, source_lang, target_lang) "
            "VALUES (?, ?, ?, ?, ?, 0, ?, ?, ?, ?)",
            (h, src, tgt, stage, len(src), time.time(), source_name,
             source_lang, target_lang))
        if cur.rowcount == 1:
            conn.commit()
            return True
        conn.execute(
            "UPDATE tm_entries SET source_text=?, target_text=?, char_count=?, "
            "source_name=COALESCE(?, source_name) "
            "WHERE content_hash=? AND stage=? AND source_lang=? "
            "AND target_lang=?",
            (src, tgt, len(src), source_name, h, stage, source_lang,
             target_lang))
        conn.commit()
        return False

    def store_batch(self, pairs: list[tuple[str, str, int]],
                    source_name: str | None = None,
                    source_lang: str | None = None,
                    target_lang: str | None = None) -> int:
        """批量存入。pairs = [(source, target, stage), ...]。返回新增条数。

        source_name 为本批统一来源标识（srt 文件名 stem），写入每个条目。
        source_lang/target_lang None 回落实例缺省（v2_learn 学习链经此
        落库，D2026-0930-05 批内缺陷修复的接线受益点）。
        """
        source_lang, target_lang = self._langs(source_lang, target_lang)
        added = 0
        for src, tgt, stg in pairs:
            if self.store(src, tgt, stg, source_name=source_name,
                          source_lang=source_lang, target_lang=target_lang):
                added += 1
        return added

    # ------------------------------------------------------------------
    # 查找
    # ------------------------------------------------------------------

    def lookup_exact(self, source: str, stage: int = 0,
                     source_lang: str | None = None,
                     target_lang: str | None = None) -> str | None:
        """精确查找：返回译文或 None。命中时自动更新 hit_count。"""
        source_lang, target_lang = self._langs(source_lang, target_lang)
        h = _simhash(_normalize(source))
        conn = self._get_conn()
        row = conn.execute(
            "SELECT target_text FROM tm_entries WHERE content_hash=? "
            "AND stage=? AND source_lang=? AND target_lang=?",
            (h, stage, source_lang, target_lang)).fetchone()
        if row:
            conn.execute(
                "UPDATE tm_entries SET hit_count=hit_count+1 "
                "WHERE content_hash=? AND stage=? AND source_lang=? "
                "AND target_lang=?", (h, stage, source_lang, target_lang))
            conn.commit()
            return row[0]
        return None

    def exact_map(self, sources: list[str], stage: int = 0,
                  source_lang: str | None = None,
                  target_lang: str | None = None) -> dict:
        """批量精确查找（P1-6）：一次参数化 SQL 取回 {原输入串: 译文}。

        - sqlite 变量上限（默认 999）→ 按 _EXACT_MAP_CHUNK 分批 IN 查询；
        - 返回 dict 以**调用方传入的原始字符串**为键（内部归一化仅用于
          哈希），调用方无需再做归一化对齐；
        - 命中条目 hit_count 一次性自增并提交（与 lookup_exact 语义一致，
          但从 N 次 commit 收敛为每批 1 次）。
        """
        source_lang, target_lang = self._langs(source_lang, target_lang)
        mapping: dict = {}
        hash_to_sources: dict = {}
        for src in sources:
            norm = _normalize(src)
            if not norm:
                continue
            hash_to_sources.setdefault(_simhash(norm), []).append(src)
        hashes = list(hash_to_sources)
        if not hashes:
            return mapping
        conn = self._get_conn()
        for i in range(0, len(hashes), _EXACT_MAP_CHUNK):
            chunk = hashes[i:i + _EXACT_MAP_CHUNK]
            placeholders = ",".join("?" * len(chunk))
            rows = conn.execute(
                "SELECT content_hash, target_text FROM tm_entries "
                "WHERE stage=? AND source_lang=? AND target_lang=? "
                f"AND content_hash IN ({placeholders})",
                (stage, source_lang, target_lang, *chunk)).fetchall()
            if not rows:
                continue
            for h, target in rows:
                for src in hash_to_sources[h]:
                    mapping[src] = target
            hit_placeholders = ",".join("?" * len(rows))
            conn.execute(
                "UPDATE tm_entries SET hit_count=hit_count+1 "
                f"WHERE stage=? AND source_lang=? AND target_lang=? "
                f"AND content_hash IN ({hit_placeholders})",
                (stage, source_lang, target_lang, *[r[0] for r in rows]))
        conn.commit()
        return mapping

    def has_exact(self, source: str, stage: int = 0,
                  source_lang: str | None = None,
                  target_lang: str | None = None) -> bool:
        """只读精确查找：返回是否存在匹配条目（不更新 hit_count）。"""
        source_lang, target_lang = self._langs(source_lang, target_lang)
        h = _simhash(_normalize(source))
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM tm_entries WHERE content_hash=? AND stage=? "
            "AND source_lang=? AND target_lang=?",
            (h, stage, source_lang, target_lang)).fetchone()
        return row is not None

    def lookup_exact_all_stages(self, source: str,
                                source_lang: str | None = None,
                                target_lang: str | None = None) -> dict:
        """精确查找所有阶段：返回 {stage: target_text}"""
        source_lang, target_lang = self._langs(source_lang, target_lang)
        h = _simhash(_normalize(source))
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT stage, target_text FROM tm_entries "
            "WHERE content_hash=? AND source_lang=? AND target_lang=?",
            (h, source_lang, target_lang)).fetchall()
        if rows:
            for r in rows:
                conn.execute(
                    "UPDATE tm_entries SET hit_count=hit_count+1 "
                    "WHERE content_hash=? AND stage=?", (h, r[0]))
            conn.commit()
            return {r[0]: r[1] for r in rows}
        return {}

    def lookup_fuzzy(self, source: str, stage: int = 0,
                     threshold: float = 0.8,
                     source_lang: str | None = None,
                     target_lang: str | None = None
                     ) -> list[tuple[str, str, float]]:
        """模糊查找：返回 [(source, target, similarity), ...] 按相似度降序。
        threshold: 字符重叠率下限 (0-1)。
        """
        source_lang, target_lang = self._langs(source_lang, target_lang)
        src = _normalize(source)
        if not src:
            return []
        src_len = len(src)
        conn = self._get_conn()
        # 按字符数缩小范围（±50% 以覆盖不同长度的相似句子）
        lo, hi = max(1, int(src_len * 0.5)), int(src_len * 1.5)
        rows = conn.execute(
            "SELECT source_text, target_text FROM tm_entries "
            "WHERE stage=? AND source_lang=? AND target_lang=? "
            "AND char_count BETWEEN ? AND ? "
            "ORDER BY hit_count DESC LIMIT 200",
            (stage, source_lang, target_lang, lo, hi)).fetchall()
        results = []
        src_lower = src.lower()
        for s, t in rows:
            s_norm = _normalize(s)
            sim = _char_overlap(src_lower, s_norm.lower())
            if sim >= threshold:
                results.append((s_norm, t, sim))
        results.sort(key=lambda x: x[2], reverse=True)
        return results[:10]

    # ------------------------------------------------------------------
    # 统计
    # ------------------------------------------------------------------

    def stats(self) -> dict:
        conn = self._get_conn()
        total = conn.execute("SELECT COUNT(*) FROM tm_entries").fetchone()[0]
        by_stage = {}
        for row in conn.execute(
                "SELECT stage, COUNT(*) FROM tm_entries GROUP BY stage"):
            by_stage[row[0]] = row[1]
        total_hits = conn.execute(
            "SELECT SUM(hit_count) FROM tm_entries").fetchone()[0] or 0
        return {
            "total": total,
            "by_stage": by_stage,
            "total_hits": total_hits,
            "db_path": self.db_path,
        }

    def clear(self, stage: int | None = None):
        """清空记忆库。stage=None 清空全部。"""
        conn = self._get_conn()
        if stage is not None:
            conn.execute("DELETE FROM tm_entries WHERE stage=?", (stage,))
        else:
            conn.execute("DELETE FROM tm_entries")
        conn.commit()

    def export_csv(self, path: str, stage: int | None = None):
        """导出为 CSV（2.1 起末尾追加 source_lang/target_lang 两列）"""
        import csv
        import io
        data_path = Path(_validated_path(path))
        conn = self._get_conn()
        if stage is not None:
            rows = conn.execute(
                "SELECT source_text, target_text, stage, hit_count, "
                "source_lang, target_lang "
                "FROM tm_entries WHERE stage=? ORDER BY hit_count DESC",
                (stage,)).fetchall()
        else:
            rows = conn.execute(
                "SELECT source_text, target_text, stage, hit_count, "
                "source_lang, target_lang "
                "FROM tm_entries ORDER BY stage, hit_count DESC").fetchall()
        buf = io.StringIO()
        w = csv.writer(buf)
        w.writerow(["source", "target", "stage", "hit_count",
                    "source_lang", "target_lang"])
        for r in rows:
            w.writerow(r)
        data_path.write_text(buf.getvalue(), encoding="utf-8-sig")

    def import_csv(self, path: str, source_lang: str | None = None,
                   target_lang: str | None = None) -> int:
        """从 CSV 导入。返回新增条数。

        语言列兼容：新格式（含 source_lang/target_lang 列）按行值优先；
        旧格式（无语言列）按解析后的语言回填（None 回落实例缺省，裸构造
        仍为 ja/zh 存量库语义，D2026-0930-05 批内缺陷修复）。
        """
        source_lang, target_lang = self._langs(source_lang, target_lang)
        import csv
        import io
        text = Path(_validated_path(path)).read_text(encoding="utf-8-sig")
        added = 0
        for row in csv.reader(io.StringIO(text)):
            if len(row) >= 2 and row[0].strip() and row[1].strip():
                # Skip header row
                if row[0].strip().lower() in ("source", "原文", "original"):
                    continue
                stage = int(row[2]) if len(row) > 2 and row[2].isdigit() else 0
                row_sl = (row[4].strip()
                          if len(row) > 4 and row[4].strip() else "")
                row_tl = (row[5].strip()
                          if len(row) > 5 and row[5].strip() else "")
                if self.store(row[0].strip(), row[1].strip(), stage,
                              source_lang=row_sl or source_lang,
                              target_lang=row_tl or target_lang):
                    added += 1
        return added


def _char_overlap(a: str, b: str) -> float:
    """字符级重叠率（Jaccard-like on characters）。用于快速模糊匹配。"""
    if not a or not b:
        return 0.0
    set_a, set_b = set(a), set(b)
    inter = len(set_a & set_b)
    union = len(set_a | set_b)
    return inter / union if union else 0.0


def _validated_path(path: str) -> str:
    """CSV 进出路径读侧校验：拒绝带 ``..`` 分量的路径并 resolve 规范化
    （穿越面收口；本地工具语义=用户明示路径可读写，此处仅禁越界分量）。"""
    from pathlib import Path as _P
    p = _P(path)
    if ".." in p.parts:
        raise ValueError(f"路径含越界分量: {path}")
    return str(p.resolve())
