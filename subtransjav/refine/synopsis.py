"""
剧情自摘要（v1.2.2 Beta 特性）
====================
在闸门0+预合并后的条目序列中过滤纯噪声行、按时间分桶均匀抽样剧情行，
以一次独立 LLM 调用生成 3-5 行中文剧情梗概，供 pipeline_v2 注入 A/B
两阶段提示词（消解指代与歧义）。

红线（验收口径，勿破坏）：
- 摘要文本只注入提示词，绝不写入输出目录/终稿/质量报告；
- 摘要缓存使用独立目录 Temp/synopsis_cache/，与翻译记忆库（TM）完全隔离；
- 任何失败（异常/空输出）返回 None，调用方静默跳过（管线照常）；
- 摘要内容、缓存与人物表校对 sidecar 不参与 manifest 指纹（与 sidecar
  内容同款已知边界）；
- 摘要调用独立 max_tokens（D2026-1025-01 定死 500），不走阶段A 的批级
  输出预算；超时独立收敛为 min(timeout_llm, 300s)（由调用方在 client 上
  设置）。
"""

import contextlib
import hashlib
import logging
import math
import os
import re
import threading
from pathlib import Path

from .config import TEMP_DIR
from .source_hallucination import is_source_counting_noise

# 缓存键成分：提示词要素变化时递增，旧缓存自然失效（不会误命中）。
# D2026-1025-01 起为机械 hash 键双保险：任一提示词正文/预算/温度变化
# → 键必变（语义以 hash 为准），PROMPT_VERSION 仅作演进标记保留在键内。
PROMPT_VERSION = "v2"

# 独立缓存目录（严禁放 translation_memory / TM 库所在位置）
SYNOPSIS_CACHE_DIR = os.path.join(TEMP_DIR, "synopsis_cache")

# 摘要调用独立预算：不继承阶段A 批级 max_tokens 预算（compute_max_output_tokens）
SYNOPSIS_MAX_TOKENS = 500
# 摘要调用超时上限（秒）：min(timeout_llm, 本值)；timeout_llm 默认见 config
SYNOPSIS_TIMEOUT_CAP_S = 300.0
SYNOPSIS_TIMEOUT_DEFAULT_S = 900.0

# 桶采样常量：桶数 = max(3, min(8, ceil(总字符数/750)))
_BUCKET_CHAR_PER = 750
_BUCKET_MIN = 3
_BUCKET_MAX = 8

# 摘要逃生口措辞（提示词约束要求模型信息不足时写"信息不足"，日志统计该词计数）
_INSUFFICIENT_MARK = "信息不足"

# system 提示词：角色 + 抽样不连续声明 + 禁止补足 + 忽略噪声行
SYNOPSIS_SYSTEM_PROMPT = (
    "你是一名剧情分析员。"
    "以下片段来自整片不同位置的抽样，时间上不连续；"
    "信息跨片段缺失属正常，禁止补足跳跃段内容；忽略纯噪声行。")

# user 提示词任务段：3-5 行概括 + 只输出梗概 + 禁止编造 + 信息不足逃生口。
# 第一段人物表只做称呼/关系确定性（D2026-1025-01 行⑤）：措辞禁出现
# 「性别」「身份」「年龄」等第二段字段（防越段）。
_SYNOPSIS_TASK_PROMPT = (
    "任务：根据以上抽样片段，用 3-5 行中文概括整部影片：\n"
    "- 主要人物表：人数、各人物称呼与关系（有文本证据才写；"
    f"证据不足就在该行写「{_INSUFFICIENT_MARK}」）\n"
    "- 核心剧情线（威胁/冲突等）\n"
    "- 场景构成\n"
    "约束：只输出梗概本身；禁止编造源文没有的内容；"
    f"某项信息不足就在该行写「{_INSUFFICIENT_MARK}」。")

# 人物表校对 sidecar：以「人物」开头（宽松匹配，容许列表符与「主要」前缀）
_CAST_LINE_RE = re.compile(r"^\s*[-*·＊>#\s]*(?:主要)?人物")

# 时间轴解析（ synopsis 模块自实现，不依赖 pipeline_v2，避免反向依赖）
_TIMING_RE = re.compile(
    r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def _start_sec(timing: str) -> float:
    """解析时间轴起始秒；解析失败返回 inf（排序时稳定沉底）。"""
    m = _TIMING_RE.match((timing or "").strip())
    if not m:
        return float("inf")
    g = list(map(int, m.groups()))
    return g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000.0


def build_synopsis_input(entries: list, max_chars: int = 6000) -> tuple:
    """从条目序列（闸门0+预合并后，含 timing/text）抽样剧情行。

    步骤：
      ① 过滤纯噪声行（source_hallucination.is_source_counting_noise 为
         True 的跳过）与空行；
      ② 按起始时间排序后分桶均匀采样：桶数 = max(3, min(8,
         ceil(总字符数/750)))，每桶预算 = max_chars/桶数，从桶首依序
         取行至预算止（逐行成本计入换行符，保证拼接结果 ≤ max_chars）；
      ③ 总字符 ≤ max_chars 时单桶全量。

    返回 (sampled_text, meta)；无有效条目返回 ("", {"buckets": 0, ...})。
    meta 含桶数（buckets）、各桶条目区间（bucket_ranges：首末 index 与
    起始时间）、实际字符数（chars）与过滤后总字符数（total_chars）。
    """
    try:
        max_chars = int(max_chars)
    except (TypeError, ValueError):
        max_chars = 6000
    if max_chars <= 0:
        max_chars = 1

    kept = []
    for e in entries or []:
        text = (e.get("text") or "").strip()
        if not text:
            continue
        if is_source_counting_noise(text):
            continue
        kept.append({"index": e.get("index"),
                     "timing": e.get("timing") or "", "text": text})
    kept.sort(key=lambda e: _start_sec(e["timing"]))
    total_chars = sum(len(e["text"]) for e in kept)
    if not kept:
        return "", {"buckets": 0, "bucket_ranges": [], "chars": 0,
                    "total_chars": 0}

    def _span(first: dict, last: dict) -> dict:
        return {"first_index": first.get("index"),
                "last_index": last.get("index"),
                "first_start": round(_start_sec(first["timing"]), 3),
                "last_start": round(_start_sec(last["timing"]), 3)}

    # 总字符未超预算：单桶全量
    if total_chars <= max_chars:
        text = "\n".join(e["text"] for e in kept)
        return text, {"buckets": 1,
                      "bucket_ranges": [_span(kept[0], kept[-1])],
                      "chars": len(text), "total_chars": total_chars}

    n_buckets = max(_BUCKET_MIN, min(_BUCKET_MAX, math.ceil(
        total_chars / _BUCKET_CHAR_PER)))
    budget = max_chars / n_buckets
    n = len(kept)
    ranges, parts = [], []
    for i in range(n_buckets):
        s, t = i * n // n_buckets, (i + 1) * n // n_buckets
        bucket = kept[s:t]
        if not bucket:
            continue
        ranges.append(_span(bucket[0], bucket[-1]))
        acc = 0
        for e in bucket:
            cost = len(e["text"]) + 1     # 计入换行符，保证拼接后 ≤ max_chars
            if acc + cost > budget:
                break                     # 从桶首依序取行至预算止
            parts.append(e["text"])
            acc += cost
    text = "\n".join(parts)
    return text, {"buckets": n_buckets, "bucket_ranges": ranges,
                  "chars": len(text), "total_chars": total_chars}


def cache_key(provider: str, model: str, sampled_text: str, *,
              system_prompt: str = SYNOPSIS_SYSTEM_PROMPT,
              task_prompt: str = _SYNOPSIS_TASK_PROMPT,
              max_tokens: int | None = SYNOPSIS_MAX_TOKENS,
              temperature: float | None = None) -> str:
    """机械缓存键（D2026-1025-01，I-7：取代人工 bump 纪律）。

    键 = sha256(PROMPT_VERSION + "\\0" + provider + "/" + model + "\\0"
    + sampled_text + "\\0" + 完整 system 提示词 + "\\0" + 完整 user 任务段
    + "\\0" + max_tokens + "\\0" + temperature)。

    既有成分（版本/服务商/模型/抽样文本）之外新增四成分：①完整 system
    提示词 ②完整 user 任务段 ③max_tokens ④temperature——任一提示词
    正文、预算、温度变化 → 键必变（旧缓存自然失效，不误命中）。
    PROMPT_VERSION 保留在键内作演进标记（双保险，语义以 hash 为准）；
    换模型（--s1-model）或版本递增同样使旧缓存自然失效。
    """
    raw = "\x00".join((
        PROMPT_VERSION,
        f"{provider or ''}/{model or ''}",
        sampled_text or "",
        system_prompt or "",
        task_prompt or "",
        str(max_tokens),
        repr(temperature),
    ))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# 截断率入账（D2026-1025-01）：模块级累计计数，pipeline_v2 收尾 print 一行
# （不进质量报告/manifest）。total＝实际发生的 LLM 生成调用数（缓存命中
# 与硬失败不计），truncated＝其中 finish_reason=="length" 被丢弃的次数。
_STATS_LOCK = threading.Lock()
_STATS: dict = {"total": 0, "truncated": 0}


def synopsis_truncation_stats() -> dict:
    """只读暴露截断率计数：{"total": N, "truncated": M}（副本）。"""
    with _STATS_LOCK:
        return dict(_STATS)


# temperature 取不到时 warning 只告一次（进程级）
_TEMP_WARNED = False
_LOG = logging.getLogger(__name__)


def _extract_cast_lines(text: str) -> list[str]:
    """宽松解析人物表行（以「人物」开头，容许列表符/引用符与「主要」
    前缀）；无命中返回空列表。"""
    return [ln.strip() for ln in (text or "").splitlines()
            if _CAST_LINE_RE.match(ln)]


def _write_cast_sidecar(cpath: Path, text: str) -> None:
    """人物表校对 sidecar：<key>.cast.md（原子写，仅供人工校对称呼/关系；
    不进输出目录/终稿/质量报告/manifest 指纹）。解析失败/无人物行静默
    跳过，任何失败不影响摘要可用性。"""
    try:
        cast_lines = _extract_cast_lines(text)
        if not cast_lines:
            return
        _atomic_write_text(cpath.with_name(cpath.stem + ".cast.md"),
                           "\n".join(cast_lines) + "\n")
    except Exception:  # noqa: BLE001 sidecar 静默降级
        pass


# 每键一把 threading.Lock（防多文件并行时同键重复调用/写缓存）
_KEY_LOCKS: dict = {}
_KEY_LOCKS_GUARD = threading.Lock()


def _key_lock(key: str) -> threading.Lock:
    with _KEY_LOCKS_GUARD:
        lock = _KEY_LOCKS.get(key)
        if lock is None:
            lock = threading.Lock()
            _KEY_LOCKS[key] = lock
        return lock


def _atomic_write_text(path: Path, text: str) -> None:
    """原子写（批 3 技术债 a：薄壳委托 refine.fs_utils，行为等价：
    先建父目录 + mkstemp 同目录 + fsync + os.replace，防半截缓存）。"""
    from subtransjav.refine.fs_utils import _atomic_write_text as _atomic
    path.parent.mkdir(parents=True, exist_ok=True)
    _atomic(path, text, suffix=".tmp")


def request_synopsis(client, sampled_text: str, *, provider: str, model: str,
                     cache_dir: str | None = None,
                     max_tokens: int = SYNOPSIS_MAX_TOKENS,
                     temperature: float | None = None) -> str | None:
    """一次 LLM 调用生成剧情梗概（带磁盘缓存）。任何失败返回 None。

    - 缓存键见 cache_key（机械 hash 键：提示词正文/max_tokens/temperature
      任一变化 → 键变）；命中（非空缓存文件）直接返回，不触发 LLM；
    - 未命中走 client._chat_with_finish 薄封装（取 finish_reason；stub 无
      该封装时回退 _chat，按未截断处理）；finish_reason=="length" → info
      日志＋丢弃不写缓存（防截断被缓存固化/静默注入）并计入截断计数；
      finish_reason 取不到 → warning 一次＋按未截断正常处理；
    - max_tokens 独立传入（默认 SYNOPSIS_MAX_TOKENS=500），调用方保证
      client 的超时已按 min(timeout_llm, 300s) 收敛；temperature 由调用方
      显式传入（取 client 实例的温度属性；取不到记 None 进键并 warning
      一次）；
    - 任何异常/空输出 → None（调用方静默跳过，管线照常）；
    - 成功（含缓存命中）时顺带原子写人物表校对 sidecar <key>.cast.md。
    """
    global _TEMP_WARNED
    text = (sampled_text or "").strip()
    if not text:
        return None
    if temperature is None and not _TEMP_WARNED:
        _TEMP_WARNED = True
        _LOG.warning("[synopsis] 未取得调用温度（client 温度属性缺失），"
                     "cache 键温度成分记 None")
    key = cache_key(provider or "", model or "", text,
                    system_prompt=SYNOPSIS_SYSTEM_PROMPT,
                    task_prompt=_SYNOPSIS_TASK_PROMPT,
                    max_tokens=max_tokens, temperature=temperature)
    cpath = Path(cache_dir or SYNOPSIS_CACHE_DIR) / f"{key}.txt"
    with _key_lock(key):
        try:
            if cpath.is_file():
                cached = cpath.read_text(encoding="utf-8")
                if cached.strip():
                    _write_cast_sidecar(cpath, cached)
                    return cached
        except OSError:
            pass                       # 缓存读取失败按未命中处理
        user_text = f"{text}\n\n{_SYNOPSIS_TASK_PROMPT}"
        chat_finish = getattr(client, "_chat_with_finish", None)
        try:
            if callable(chat_finish):
                out, finish_reason = chat_finish(
                    SYNOPSIS_SYSTEM_PROMPT, user_text, max_tokens=max_tokens)
            else:
                # 第三方 stub 无薄封装：回退 _chat，按未截断处理
                out = client._chat(SYNOPSIS_SYSTEM_PROMPT, user_text,
                                   max_tokens=max_tokens)
                finish_reason = None
        except Exception:
            return None
        with _STATS_LOCK:
            _STATS["total"] += 1
        fr = str(finish_reason).lower() if finish_reason is not None else None
        if fr == "length":
            with _STATS_LOCK:
                _STATS["truncated"] += 1
            _LOG.info("[synopsis] 摘要被截断（finish_reason=length，"
                      "键前8位=%s），丢弃不写缓存", key[:8])
            return None
        if fr is None:
            _LOG.warning("[synopsis] 未取得 finish_reason（端不回传/路径"
                         "未覆盖），按未截断处理")
        out = (out or "").strip()
        if not out:
            return None
        # 缓存写失败不影响本次摘要可用性
        with contextlib.suppress(OSError):
            _atomic_write_text(cpath, out)
            _write_cast_sidecar(cpath, out)
        return out
