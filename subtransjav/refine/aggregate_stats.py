"""跨片聚合统计（2.6.0 批 2，D2026-1002-03）：只读聚合层。

职责边界（D2026-1002-03 评议 C1-C7）：
- 数据源＝被分析报告同目录的 ``{stem}_质量报告导读.json``（generated_at
  降序取最近 N 片、排除当前片）＋ tm.db **只读** SQL（mode=ro；
  禁经 TranslationMemory() 构造——其 __init__ 建表/WAL 属写路径）；
- 产出＝纯计数文本块（DATA 围栏由调用方 quality_advisor 包裹）；内容
  白名单限定：计数＋extras 数值＋stem，**绝不引用周边片字幕原文**
  （message/current_text/source_excerpt）——防周边片内容进 prompt；
- 口径声明（C4/C1 成文）：CPS 行动密度＝行动口径（单片截断≤20，值 20
  意为 ≥20）；TM 入库量为命中率**代理指标**（分母未埋点，无法计算真实
  命中率）；基线片数 n 恒报，n 过小提示不可靠；
- 只建议不改默认值：本模块零写路径，不写任何配置/阈值/词库/TM。
"""

import json
import sqlite3
import time
from pathlib import Path

_SCAN_LIMIT = 20            # 目录枚举上限（generated_at 降序取最近）
_TM_LOOKBACK_DAYS = 30
_AGG_BLOCK_CHAR_LIMIT = 2000
_BASELINE_MIN_N = 3         # 低于此值块内提示基线不可靠
_PREVIEW_SOURCES = 5        # 基线明细最多列的片数

_GUIDE_SUFFIX = "_质量报告导读.json"

# C4 字段名契约（测试钉）：精确措辞防"入库量"被误读为"命中率"
_HEADER_DECLARATION = (
    "口径声明：CPS行动密度(单片上限20)＝行动口径，值 20 意为 ≥20；"
    "TM入库量新增(近30天)为命中率代理指标（命中率分母未埋点，无法计算"
    "真实命中率）；基线片数 n 过小不可作为可靠基线；本块仅对照参考，"
    "不改变任何默认阈值/白名单。")


def default_tm_db_path() -> str:
    """默认 tm.db 路径（只读推导；禁 makedirs——本模块零写路径）。"""
    from .tm import _DEFAULT_TM_DIR
    return str(Path(_DEFAULT_TM_DIR) / "tm.db")


def collect_directory_stats(analysis_dir: str, current_stem: str,
                            limit: int = _SCAN_LIMIT):
    """扫描目录内导读 json（排除当前片），generated_at 降序取最近 limit 片。

    返回 (stats_list, skipped_bad)：stats 元素＝白名单字段 dict
    {stem, generated_at, open_total, obs_total, cat_counts}；
    解析失败/缺 items 的文件计入 skipped_bad 跳过（不抛）。目录不存在
    返回 ([], 0)。"""
    directory = Path(analysis_dir)
    if not directory.is_dir():
        return [], 0
    entries: list[dict] = []
    skipped_bad = 0
    for p in sorted(directory.glob(f"*{_GUIDE_SUFFIX}")):
        stem = p.name[: -len(_GUIDE_SUFFIX)]
        if stem == current_stem:
            continue
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            skipped_bad += 1
            continue
        if not isinstance(data, dict) \
                or not isinstance(data.get("items"), list):
            skipped_bad += 1
            continue
        open_total = 0
        obs_total = 0
        cat_counts: dict[str, int] = {}
        for it in data["items"]:
            if not isinstance(it, dict):
                continue
            status = str(it.get("status") or "")
            cat = str(it.get("category") or "")
            if status == "open":
                open_total += 1
                cat_counts[cat] = cat_counts.get(cat, 0) + 1
            elif status == "observation":
                obs_total += 1
        entries.append({
            "stem": stem,
            "generated_at": str(data.get("generated_at") or ""),
            "open_total": open_total,
            "obs_total": obs_total,
            "cat_counts": cat_counts,
        })
    entries.sort(key=lambda e: e["generated_at"], reverse=True)
    return entries[:limit], skipped_bad


def query_tm_summary(db_path: str, current_stem: str = "",
                     days: int = _TM_LOOKBACK_DAYS) -> dict | None:
    """tm.db 只读聚合（mode=ro＋busy_timeout；任何异常降级返回 None）。

    返回 {total_entries, recent_by_source: [(source, n)...],
    current_film_entries, window_days}。禁经 TranslationMemory() 构造
    （其初始化建表/WAL 属写路径）；库缺失/被锁/DDL 重建窗口均降级。"""
    try:
        con = sqlite3.connect(f"file:{Path(db_path).as_posix()}?mode=ro",
                              uri=True, timeout=2.0)
        try:
            con.execute("PRAGMA busy_timeout=2000")
            total = con.execute(
                "SELECT COUNT(*) FROM tm_entries").fetchone()[0]
            cutoff = time.time() - days * 86400
            recent = con.execute(
                "SELECT source_name, COUNT(*) FROM tm_entries "
                "WHERE created_at >= ? AND source_name IS NOT NULL "
                "GROUP BY source_name ORDER BY COUNT(*) DESC LIMIT 10",
                (cutoff,)).fetchall()
            cur_n = 0
            if current_stem:
                cur_n = con.execute(
                    "SELECT COUNT(*) FROM tm_entries WHERE source_name = ?",
                    (current_stem,)).fetchone()[0]
        finally:
            con.close()
        return {"total_entries": int(total),
                "recent_by_source": [(str(r[0]), int(r[1]))
                                     for r in recent],
                "current_film_entries": int(cur_n),
                "window_days": days}
    except (sqlite3.Error, OSError):
        return None


def _avg(values: list[int]) -> float:
    return sum(values) / len(values) if values else 0.0


def build_aggregate_block(analysis_dir: str, current_stem: str,
                          current_items: list | None = None,
                          tm_db_path: str = "",
                          char_limit: int = _AGG_BLOCK_CHAR_LIMIT) -> str:
    """产跨片聚合统计文本块（无其他片且无 TM 统计返回空串＝不注入）。

    内容白名单：计数＋stem（C4）；恒报基线 n；超 char_limit 截断＋声明。
    DATA 围栏由调用方包裹。"""
    stats, skipped_bad = collect_directory_stats(analysis_dir, current_stem)
    tm = query_tm_summary(tm_db_path or default_tm_db_path(), current_stem)
    if not stats and tm is None:
        return ""

    cur_items = [it for it in (current_items or [])
                 if isinstance(it, dict)]
    cur_open = sum(1 for it in cur_items if str(it.get("status") or "") == "open")
    cur_cps = sum(1 for it in cur_items
                  if str(it.get("status") or "") == "open"
                  and str(it.get("category") or "") == "cps_too_fast")

    lines: list[str] = [_HEADER_DECLARATION]
    baseline_open = [s["open_total"] for s in stats]
    baseline_cps = [s["cat_counts"].get("cps_too_fast", 0) for s in stats]
    lines.append(f"- 基线片数 n={len(stats)}（按导读生成时间取最近"
                 f" {_SCAN_LIMIT} 片；坏件跳过 {skipped_bad}）"
                 + ("；n 过小不可作为可靠基线" if len(stats) < _BASELINE_MIN_N
                    else ""))
    if stats:
        lines.append(f"- open项数 当前片={cur_open} vs 基线均值"
                     f" {_avg(baseline_open):.1f}")
        lines.append(f"- CPS行动密度(单片上限20) 当前片={cur_cps} vs 基线均值"
                     f" {_avg(baseline_cps):.1f}")
        per_film = "、".join(f"{s['stem']}={s['open_total']}"
                             for s in stats[:_PREVIEW_SOURCES])
        more = f"（另有 {len(stats) - _PREVIEW_SOURCES} 片未列出）" \
            if len(stats) > _PREVIEW_SOURCES else ""
        lines.append(f"- 基线各片 open项数: {per_film}{more}")
    if tm is not None:
        top = "、".join(f"{name}={n}" for name, n in tm["recent_by_source"]) \
            or "（无记录）"
        lines.append(f"- TM入库量新增(近30天): 库总量 {tm['total_entries']} 条；"
                     f"按片 top: {top}；当前片 {tm['current_film_entries']} 条")
    text = "\n".join(lines)
    if len(text) > char_limit:
        text = text[:char_limit] + "\n（聚合块超长已截断）"
    return text
