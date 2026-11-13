"""
Refine - v2 两阶段字幕净语翻译流水线（SubTrans 整合版）
=========================================================
阶段A 净语+翻译(ja→zh) → 阶段B 审校+抛光(zh→zh)

每阶段可独立选择服务商与模型：
  deepseek  : DeepSeek 官方 API（原生通道）
  zen       : OpenCode Zen（OpenAI 兼容，含免费模型）
  lmstudio  : 本地 LM Studio（OpenAI 兼容端点，默认 http://localhost:1234/v1）
  custom    : 任意 OpenAI 兼容接口（须提供 endpoint）

导入惰性化（壳层启动优化，2026-11-13）：包级导出改为 PEP 562
``__getattr__`` 按需装载。此前仅 ``import subtrans.refine.<任意子模块>``
（GUI 启动链的 template_seed / asr_meta / fs_utils）就会连带拉起
tm（sqlite3）/glossary/batch/config 全套，约 +70ms 冷启动税；现仅在使用
包级符号时才装载对应模块。``from subtrans.refine import RefineConfig`` 等
既有写法语义不变（命中后写入 globals 缓存）。
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # 仅注解/静态检查位消费，运行期零导入
    from .batch import find_srt_files, scan_summary
    from .config import (
        DEFAULT_BATCH_CLOUD,
        DEFAULT_BATCH_LOCAL,
        PROVIDER_TEXT,
        STAGE_NAMES,
        RefineConfig,
        StageConfig,
        ensure_language_support,
    )
    from .glossary import (
        format_glossary_block,
        load_glossary,
        match_glossary,
        save_glossary,
    )
    from .tm import TranslationMemory

__all__ = [
    "RefineConfig",
    "StageConfig",
    "STAGE_NAMES",
    "DEFAULT_BATCH_LOCAL",
    "DEFAULT_BATCH_CLOUD",
    "PROVIDER_TEXT",
    "ensure_language_support",
    "load_glossary",
    "save_glossary",
    "match_glossary",
    "format_glossary_block",
    "TranslationMemory",
    "find_srt_files",
    "scan_summary",
]

# 包级符号 → (子模块, 属性名)。PyInstaller 静态分析看不到本表驱动的动态
# import，故 packaging/SubTrans.spec 对这四个子模块显式 hiddenimports 钉死。
_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "RefineConfig": (".config", "RefineConfig"),
    "StageConfig": (".config", "StageConfig"),
    "STAGE_NAMES": (".config", "STAGE_NAMES"),
    "DEFAULT_BATCH_LOCAL": (".config", "DEFAULT_BATCH_LOCAL"),
    "DEFAULT_BATCH_CLOUD": (".config", "DEFAULT_BATCH_CLOUD"),
    "PROVIDER_TEXT": (".config", "PROVIDER_TEXT"),
    "ensure_language_support": (".config", "ensure_language_support"),
    "load_glossary": (".glossary", "load_glossary"),
    "save_glossary": (".glossary", "save_glossary"),
    "match_glossary": (".glossary", "match_glossary"),
    "format_glossary_block": (".glossary", "format_glossary_block"),
    "TranslationMemory": (".tm", "TranslationMemory"),
    "find_srt_files": (".batch", "find_srt_files"),
    "scan_summary": (".batch", "scan_summary"),
}


def __getattr__(name: str) -> Any:
    """PEP 562 惰性导出：首次访问包级符号时才导入对应子模块。"""
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(target[0], __name__), target[1])
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
