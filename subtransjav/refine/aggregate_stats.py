"""跨片聚合统计（2.6.0 批 2；2026-10-02 owner 修订，D2026-1002-05）：
统计与对比全部基于**保存的翻译记忆库**（tm.db，只读）。

口径（owner 修订成文）：统计源＝保存的翻译记忆库，**不做同目录扫描**
（owner 明示"不应是同目录"）；对比窗口三档 7/30/永久由用户选择（GUI 下拉/
CLI 旗标 ``--tm-stats-window``，缺省 30 天）；CPS/风险类跨片对比因质量
数据未库化暂缺（块内如实声明）。只建议不改默认值：本模块零写路径。

下载面（推荐 ASR 模型）委托 dict_manager；本模块无网络面。
"""

import sqlite3
import time
from pathlib import Path

_TM_LOOKBACK_DEFAULT = 30
_AGG_BLOCK_CHAR_LIMIT = 2000
_PREVIEW_SOURCES = 5
_TM_DB_REL = ("Temp", "translation_memory", "tm.db")

# 窗口三档（owner 修订）：7/30/永久（None=全部）；GUI 下拉与 CLI 旗标共用
WINDOW_MAP = {"7": 7, "30": 30, "all": None}
WINDOW_CHOICES = ("7", "30", "all")


def default_tm_db_path() -> str:
    """默认 tm.db 路径（只读推导，零 mkdir——本模块零写路径）。"""
    from .tm import _DEFAULT_TM_DIR
    return str(Path(_DEFAULT_TM_DIR) / "tm.db")


def query_tm_summary(db_path: str, current_stem: str = "",
                     window_days: int | None = _TM_LOOKBACK_DEFAULT) -> dict | None:
    """tm.db 只读聚合（mode=ro＋busy_timeout；任何异常降级返回 None）。

    window_days：7/30＝按 created_at 回看天数；None＝永久（全部）。
    返回 {total_entries, window_added, recent_by_source: [(source, n)...],
    other_films, current_film_entries, window_days}。"""
    try:
        con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro",
                              uri=True, timeout=2.0)
        try:
            con.execute("PRAGMA busy_timeout=2000")
            total = con.execute(
                "SELECT COUNT(*) FROM tm_entries").fetchone()[0]
            if window_days is not None:
                cutoff = time.time() - window_days * 86400
                window_added = con.execute(
                    "SELECT COUNT(*) FROM tm_entries "
                    "WHERE created_at >= ?", (cutoff,)).fetchone()[0]
                recent = con.execute(
                    "SELECT source_name, COUNT(*) FROM tm_entries "
                    "WHERE created_at >= ? AND source_name IS NOT NULL "
                    "GROUP BY source_name ORDER BY COUNT(*) DESC LIMIT 5",
                    (cutoff,)).fetchall()
            else:
                window_added = total
                recent = con.execute(
                    "SELECT source_name, COUNT(*) FROM tm_entries "
                    "WHERE source_name IS NOT NULL "
                    "GROUP BY source_name ORDER BY COUNT(*) DESC LIMIT 5",
                    ()).fetchall()
            if current_stem and window_days is not None:
                cutoff = time.time() - window_days * 86400
                cur_n = con.execute(
                    "SELECT COUNT(*) FROM tm_entries "
                    "WHERE source_name = ? AND created_at >= ?",
                    (current_stem, cutoff)).fetchone()[0]
            elif current_stem:
                cur_n = con.execute(
                    "SELECT COUNT(*) FROM tm_entries "
                    "WHERE source_name = ?", (current_stem,)).fetchone()[0]
            else:
                cur_n = 0
            if current_stem:
                others = con.execute(
                    "SELECT COUNT(DISTINCT source_name) FROM tm_entries "
                    "WHERE source_name IS NOT NULL AND source_name != ?",
                    (current_stem,)).fetchone()[0]
            else:
                others = con.execute(
                    "SELECT COUNT(DISTINCT source_name) FROM tm_entries "
                    "WHERE source_name IS NOT NULL").fetchone()[0]
        finally:
            con.close()
        return {"total_entries": int(total),
                "window_added": int(window_added),
                "recent_by_source": [(str(r[0]), int(r[1]))
                                     for r in recent],
                "other_films": int(others),
                "current_film_entries": int(cur_n),
                "window_days": window_days}
    except (sqlite3.Error, OSError):
        return None


def build_aggregate_block(tm_db_path: str = "", current_stem: str = "",
                          window_days: int | None = _TM_LOOKBACK_DEFAULT,
                          char_limit: int = _AGG_BLOCK_CHAR_LIMIT) -> str:
    """产 TM 库对照统计文本块（库不可用或全空返回空串＝不注入）。

    内容白名单：计数＋stem；块头声明（统计源/窗口/未库化项/仅供参考）；
    恒报窗口内其他片数 n；超 char_limit 截断＋声明。DATA 围栏由调用方
    quality_advisor 包裹。"""
    tm = query_tm_summary(tm_db_path or default_tm_db_path(), current_stem,
                          window_days)
    if tm is None or (tm["total_entries"] == 0 and tm["window_added"] == 0):
        return ""
    window_label = ("永久（全部）" if tm["window_days"] is None
                    else f"近 {tm['window_days']} 天")
    lines: list[str] = [
        f"口径声明：统计源＝保存的翻译记忆库（只读）；窗口＝{window_label}；"
        "CPS/风险类跨片对比因质量数据未库化暂缺；以下仅对照参考，"
        "不改变任何默认阈值/白名单。"]
    if current_stem:
        lines.append(f"- 当前片（{current_stem}）窗口内入库 "
                     f"{tm['current_film_entries']} 条")
    lines.append(f"- 窗口内入库合计 {tm['window_added']} 条"
                 f"（库内其他影片 {tm['other_films']} 部）")
    if tm["recent_by_source"]:
        top = "、".join(f"{name}={n}"
                        for name, n in tm["recent_by_source"])
        lines.append(f"- 窗口内按片入库 top: {top}")
    lines.append(f"- 库总量 {tm['total_entries']} 条")
    block = "\n".join(lines)
    if len(block) > char_limit:
        block = block[:char_limit] + "\n（聚合块超长已截断）"
    return block
