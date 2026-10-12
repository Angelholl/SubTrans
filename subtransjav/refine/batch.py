"""
批量处理增强：递归目录扫描 / 文件过滤
======================================
支持递归查找 .srt 文件、按大小/日期/模式过滤。
"""

import contextlib
import os
import re
from pathlib import Path
from typing import Any

from subtransjav.refine.fs_utils import BACKUP_SUFFIX
from subtransjav.refine.pass_disagreement import is_pass_intermediate


def is_pipeline_intermediate(name: str) -> bool:
    """判定文件名是否为本工具流水线产物（中间稿/终稿）。

    2.7.3 件④（D2026-1005）：GUI 文件夹收编智能过滤用——流水线中间稿
    （pass1/pass2、_refine_A 中断残留）与终稿（_final_cn 等）不是用户想
    收编的翻译输入，产成品是 .merged.subtransjav/.merged.whisperjav。

    判定规则（对剥掉 .srt 后缀的 stem 末尾锚定、大小写敏感，随产出侧
    命名原样）：
      1. pass 中间稿：{基名}.{语言码}.pass1/.pass2（pass_disagreement 命名约定）；
      2. 中断残留：  *_refine_A（pipeline_v2 阶段A 产物）；
      3. 终稿：      *_final_cn / *_final_en 等（v2_outputs final_stem 契约）。

    刻意**不排 merged**：``{基名}.{语言码}.merged.subtransjav.srt`` 等是
    合并产成品，可能被用户当输入再次收编，排除即误杀。CLI
    ``find_srt_files`` 默认口径不受本谓词影响（一字未改）。
    """
    stem = name[:-4] if name.lower().endswith(".srt") else name
    return (
        is_pass_intermediate(stem)
        or bool(re.search(r"_refine_[A-Za-z]$", stem))
        or bool(re.search(r"_final_[A-Za-z0-9_-]+$", stem))
    )


def find_srt_files(
    directory: str,
    recursive: bool = True,
    pattern: str = "*.srt",
    min_size: int = 0,
    max_size: int = 0,
    min_date: str = "",
    max_date: str = "",
    exclude_patterns: list[str] | None = None,
) -> list[str]:
    """扫描目录下的 SRT 文件。

    Args:
        directory:    根目录
        recursive:    是否递归子目录
        pattern:      文件名 glob 模式（默认 "*.srt"）
        min_size:     最小文件大小（字节，0=不限）
        max_size:     最大文件大小（字节，0=不限）
        min_date:     最早修改日期（ISO 格式 YYYY-MM-DD，空=不限）
        max_date:     最晚修改日期（ISO 格式 YYYY-MM-DD，空=不限）
        exclude_patterns: 排除的路径模式列表（如 ["*_raw.srt", "*/Temp/*"]）

    Returns:
        排序后的绝对路径列表
    """
    root = Path(directory)
    if not root.is_dir():
        raise FileNotFoundError(f"目录不存在: {directory}")

    exclude_re = _compile_exclude_patterns(exclude_patterns or [])

    # 时间过滤
    min_ts = _parse_date(min_date) if min_date else 0
    max_ts = _parse_date(max_date, end_of_day=True) if max_date else float("inf")

    results = []
    iterator = root.rglob(pattern) if recursive else root.glob(pattern)

    for p in iterator:
        if not p.is_file():
            continue
        # C1（D2026-1002-10）：校对页备份件 *.bak.srt 不作为翻译输入收编
        #（2.6.1 批 2b 起存在，排除对现状零变化）
        if p.name.endswith(BACKUP_SUFFIX):
            continue
        abs_path = str(p.resolve())
        # Normalize path separators for regex matching
        abs_path_normalized = abs_path.replace("\\", "/")

        # 排除模式
        if any(rx.search(abs_path_normalized) for rx in exclude_re):
            continue

        try:
            stat = p.stat()
        except OSError:
            continue

        # 大小过滤
        if min_size and stat.st_size < min_size:
            continue
        if max_size and stat.st_size > max_size:
            continue

        # 日期过滤
        if stat.st_mtime < min_ts or stat.st_mtime > max_ts:
            continue

        results.append(abs_path)

    results.sort()
    return results


def scan_summary(files: list[str]) -> dict[str, Any]:
    """返回文件列表的统计摘要。"""
    if not files:
        return {"count": 0, "total_size": 0, "dirs": []}

    total_size = 0
    dirs = set()
    for f in files:
        try:
            total_size += os.path.getsize(f)
            dirs.add(os.path.dirname(f))
        except OSError:
            pass

    return {
        "count": len(files),
        "total_size": total_size,
        "total_size_mb": round(total_size / (1024 * 1024), 2),
        "dirs": sorted(dirs),
    }


def _compile_exclude_patterns(patterns: list[str]) -> list[re.Pattern]:
    """将 glob 风格排除模式编译为正则。

    支持:
      *_raw.srt  - 匹配文件名以 _raw.srt 结尾的
      */temp/*   - 匹配路径中含 /temp/ 的
      *.bak      - 匹配扩展名为 .bak 的
    """
    result = []
    for pat in patterns:
        # 统一路径分隔符为 /
        regex = pat.replace("\\", "/")
        # 转义正则特殊字符
        regex = re.escape(regex)
        # 还原 glob 通配符
        regex = regex.replace(r"\*\*", "§DOUBLESTAR§")
        regex = regex.replace(r"\*", "[^/]*")
        regex = regex.replace(r"\?", "[^/]")
        regex = regex.replace("§DOUBLESTAR§", ".*")
        # 模式匹配路径的任意部分
        regex = f"(?:^|.*/){regex}(?:/.*|$)"
        with contextlib.suppress(re.error):
            result.append(re.compile(regex, re.IGNORECASE))
    return result


def _parse_date(date_str: str, end_of_day: bool = False) -> float:
    """解析 ISO 日期字符串为 Unix 时间戳。"""
    from datetime import datetime
    from datetime import time as dtime
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d")
        if end_of_day:
            dt = datetime.combine(dt.date(), dtime.max)
        return dt.timestamp()
    except ValueError:
        return 0 if not end_of_day else float("inf")
