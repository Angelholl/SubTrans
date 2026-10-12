"""
中/英分词提示生成模块（2.1，D2026-0930-05）

按源语言提供分词级提示，与 ja 源的 grammar_hint（SudachiPy 句法分析）
并列：
- zh 源：jieba 精确模式分词（[zh] 可选组件，缺失时静默降级）；
- en 源：内置规则（全大写缩写/强调标注，纯规则零依赖）。

对 D2026-0930-01 审校绑定口径的澄清：存在真实消费点（A/B 注入缝均
消费，见 pipeline_v2._collect_grammar_hints 的源语言分派）即接线。
"""

from __future__ import annotations

import re
import string
import threading

# ---------------------------------------------------------------------------
# 惰性单例 jieba（[zh] 可选组件）
# ---------------------------------------------------------------------------

_jieba_instance = None
_zh_available: bool | None = None
# D4 同款（镜像 grammar_hint 注释风格）：jieba 冷启动需加载词库 dict，
# 多线程并发 miss 时同时 import/初始化会重复建库，双检锁防重复初始化。
_init_lock = threading.Lock()


def _get_jieba():
    """懒加载 jieba 模块单例（双重检查锁，防并发重复初始化）。

    import 失败（[zh] extra 未安装等）→ 缓存 None，静默降级。
    """
    global _jieba_instance, _zh_available
    if _jieba_instance is not None:
        return _jieba_instance
    with _init_lock:
        if _jieba_instance is not None:   # 等锁期间可能已被其他线程初始化
            return _jieba_instance
        try:
            import jieba  # [zh] 可选组件（pyproject extra，>=0.42）
            _jieba_instance = jieba
            _zh_available = True
        except Exception:   # noqa: BLE001 - ImportError 等一律静默降级
            _jieba_instance = None
            _zh_available = False
        return _jieba_instance


def is_zh_hint_available() -> bool:
    """检查 jieba（zh 分词后端）是否可用（惰性触发单例初始化）。"""
    if _zh_available is None:
        _get_jieba()
    return bool(_zh_available)


# ---------------------------------------------------------------------------
# 共享：条目定位与纯标点判定
# ---------------------------------------------------------------------------

# 纯标点 token 剔除用：ASCII 标点 + 常见中文标点
_ZH_PUNCT = "，。！？；：“”‘’（）…、·—《》【】"


def _is_punct_token(token: str) -> bool:
    """纯标点/空白 token 判定：strip 后为空，或全部字符属标点集。"""
    t = token.strip()
    if not t:
        return True
    punct = string.punctuation + _ZH_PUNCT
    return all(ch in punct for ch in t)


def _current_text(srt_content: str, current_index: int,
                  entries: list[dict] | None) -> str:
    """按 index 定位当前条目文本（找不到/空文本返回 ""，同款查找逻辑）。"""
    if entries is None:
        from .filters import parse_srt
        entries = parse_srt(srt_content)
    for e in entries or []:
        if e.get("index") == current_index:
            return e.get("text") or ""
    return ""


# ---------------------------------------------------------------------------
# zh 源：jieba 分词参考
# ---------------------------------------------------------------------------

# 文本含 CJK 判定（U+4E00-U+9FFF，含汉字即视为中文行）
_CJK_RE = re.compile(r"[一-鿿]")


def generate_zh_hints(srt_content: str, current_index: int,
                      entries: list[dict] | None = None) -> str:
    """zh 源分词提示：jieba 精确模式切分，产出「分词参考」一行提示。

    门槛：文本含 CJK、strip 后长度 >= 6、剔除纯标点/空白 token 后
    剩余 >= 2 个 token——任一不满足或任何异常均返回 ""（宁缺毋滥）。
    """
    try:
        text = _current_text(srt_content, current_index, entries)
        if not text.strip():
            return ""
        if not _CJK_RE.search(text):
            return ""
        if len(text.strip()) < 6:
            return ""
        jieba_mod = _get_jieba()
        if jieba_mod is None:
            return ""
        tokens = [t for t in jieba_mod.cut(text) if not _is_punct_token(t)]
        if len(tokens) < 2:
            return ""
        return "【语法提示】\n- 分词参考：" + " | ".join(tokens)
    except Exception:   # noqa: BLE001 - 分词失败宁缺毋滥，不阻塞管线
        return ""


# ---------------------------------------------------------------------------
# en 源：内置规则（缩写/强调标注）
# ---------------------------------------------------------------------------

# 全大写缩写/强调判定：词边界内 2+ 连续大写拉丁字母
_UPPER_RE = re.compile(r"\b[A-Z]{2,}\b")


def generate_en_hints(srt_content: str, current_index: int,
                      entries: list[dict] | None = None) -> str:
    """en 源分词提示：内置规则标注全大写缩写/强调（纯规则零依赖）。"""
    text = _current_text(srt_content, current_index, entries)
    m = _UPPER_RE.search(text)
    if not m:
        return ""
    return ("【语法提示】\n- 缩写『" + m.group(0)
            + "』为缩写/强调，建议保留原文不译")
