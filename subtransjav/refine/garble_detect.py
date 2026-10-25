"""疑似听错（ASR 错音）规则型检测器 —— 纯函数、无 IO。

D2026-1025-01 批4（D 件仓内补丁）：ASR 错音句（なんでるじゃんよー/
見てくだひゃ 级）进翻译会被 LLM 胡翻，需在质量报告打标供人工复核一眼
锁定。**只标不删、禁 LLM 改写**——本模块产出是报告面信号，绝不进
正文改写链路。

检测主路径：sudachipy 分词未知词（OOV）字符占比。分词复用 grammar_hint
的词典懒加载单例（不自建加载器，dict/sudachi/ 优先 + 缺省回退链同源）；
sudachi 不可用（ImportError/初始化失败）时优雅降级（available=False），
绝不抛错阻断报告生成。

保守取向（宁漏勿滥）：本检测是报告面、非阻断面——宁可漏报也不把正常
口语/俚语/叠词误标进复核清单，故：
- 核心长（剥标点后）不足 :data:`MIN_CORE_CHARS` 的短句一律不判；
- OOV 占比阈值 :data:`OOV_RATIO_THRESHOLD` 取 0.4，仅在整行大部分字符
  都不在词典时才标；
- 非日文条目（无假名）不消费（兼作语言门；调用方另有 ja→zh 门控，
  与 kana_clean 同门）。

实测注记（dict/sudachi/system_full.dic，sudachipy 0.7.0）：Sudachi 的
MeCab OOV 兜底会把常见假名串判为已知词——なんでるじゃんよー/
見てくだひゃ 等真实 ASR 错音串分词后 OOV 占比为 0（判为已知，漏报，
属保守取向预期）；OOV 判定对 ゔ 系非常见组合（ゔぁれんじゃ/
ゔぉるじゃん）与异常片假名串（ヴェテャミョ）稳定触发。测试样例以
实测为准（tests/test_garble_detect.py）。
"""

from __future__ import annotations

import re
import unicodedata

from . import grammar_hint as _gh

# ---------------------------------------------------------------------------
# 常量（单一来源；调整即全库生效，测试以 import 引用钉值）
# ---------------------------------------------------------------------------

# OOV 字符占比阈值：未知词字符数 / 剥标点后核心字符数 ≥ 该值才判疑似听错。
# 0.4＝整行近半字符不在词典——口语实义词（叠词/俚语/专名）单 token OOV
# 也达不到，保守防误伤。
OOV_RATIO_THRESHOLD = 0.4

# 剥标点后核心字符数下限：短句（ああ/うん/はい 级）一律不判。
MIN_CORE_CHARS = 4

# 假名存在性＝日文条目门（与 quality_report._KANA_RE 同字符区间）：
# 无假名的行（中文/英文/纯汉字/数字）不消费，防非日文源文被 OOV 误标。
_JP_KANA_RE = re.compile(r"[ぁ-ゖァ-ヺー]")


def _core_chars(text: str) -> str:
    """剥除标点/符号/空白/控制符，保留实义字符（假名/汉字/拉丁/数字）。

    ー（长音符）unicodedata 类别为 Lm（字母修饰符），按音素成分保留。
    """
    return "".join(
        ch for ch in text
        if not unicodedata.category(ch).startswith(("P", "S", "Z", "C"))
    )


def _tokenize_ja(text: str) -> list | None:
    """复用 grammar_hint 懒加载分词单例做形态素解析（不自建加载器）。

    经模块属性间接调用（monkeypatch 可达），返回 morpheme 列表；
    分词器不可用（未安装/词典缺失/初始化失败）或单次分词异常时返回
    None——调用方按降级处理，绝不抛错阻断报告。
    """
    try:
        return _gh._tokenize_cached(text)
    except Exception:   # noqa: BLE001 - 报告面不阻断：分词异常按不可用降级
        return None


def _sudachi_ready() -> bool:
    """探测 sudachi 分词器可用性（懒加载探测，失败静默为不可用）。"""
    try:
        return _gh._get_tokenizer() is not None
    except Exception:   # noqa: BLE001 - 降级口径：任何初始化异常=不可用
        return False


def judge_garble_text(text: str) -> tuple[bool, float]:
    """判定单条日文源文是否疑似听错。

    Parameters
    ----------
    text : str
        源文条目文本（日文）。

    Returns
    -------
    tuple[bool, float]
        (是否疑似听错, OOV 字符占比)。非日文（无假名）、核心长不足
        :data:`MIN_CORE_CHARS`、或分词器不可用时恒为 (False, 0.0)
        （保守取向：宁漏勿滥）。
    """
    text = text or ""
    core = _core_chars(text)
    if len(core) < MIN_CORE_CHARS or not _JP_KANA_RE.search(core):
        return False, 0.0
    try:
        tokens = _tokenize_ja(core)
    except Exception:   # noqa: BLE001 - 报告面不阻断：分词链任何异常=降级
        return False, 0.0
    if not tokens:
        return False, 0.0
    total = len(core)
    oov_chars = 0
    try:
        oov_chars = sum(len(m.surface()) for m in tokens if m.is_oov())
    except Exception:   # noqa: BLE001 - morpheme 接口异常按不可用降级
        return False, 0.0
    if not total:
        return False, 0.0
    ratio = oov_chars / total
    return ratio >= OOV_RATIO_THRESHOLD, ratio


def scan_garble_suspects(entries: list) -> dict:
    """扫描源文条目列表，产出质量报告「疑似听错」候选（只标不删）。

    Parameters
    ----------
    entries : list
        源文侧条目列表（dict：index/timing/text）。仅日文条目消费——
        调用方门控 ja→zh（与 kana_clean 同门），本函数再按条目级假名
        存在性过滤非日文行。

    Returns
    -------
    dict
        ``{"available": bool, "items": [{"index", "timing", "text",
        "oov_ratio"}]}``。available=False（sudachi 不可用/初始化失败）
        时 items 恒为 []，报告侧按整行/整节省略处理；本函数绝不抛错
        阻断报告生成。
    """
    try:
        if not _sudachi_ready():
            return {"available": False, "items": []}
        items: list[dict] = []
        for e in (entries or []):
            if not isinstance(e, dict):
                continue
            text = e.get("text") or ""
            core = _core_chars(text)
            # 条目级预过滤（不经分词，便宜）：短句/非日文行直接跳过
            if len(core) < MIN_CORE_CHARS or not _JP_KANA_RE.search(core):
                continue
            hit, ratio = judge_garble_text(text)
            if hit:
                items.append({
                    "index": e.get("index"),
                    "timing": e.get("timing", ""),
                    "text": text,
                    "oov_ratio": round(ratio, 4),
                })
        return {"available": True, "items": items}
    except Exception:   # noqa: BLE001 - 降级口径：扫描任何异常=报告缺席
        return {"available": False, "items": []}
