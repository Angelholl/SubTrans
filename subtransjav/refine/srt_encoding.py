"""SRT 字幕编码嗅探（2.6.1 批 2a N1，D2026-1002-09；C1 卡A 补 cp932）。

判定序：BOM（utf-8-sig / utf-16 le/be）→ 无 BOM 段按候选编码序
utf-8 严格解码 → gbk 兜底 → cp932 兜底 → 全部失败则标记不可信
（由调用方报错，本模块不抛异常）。

cp932 仅兜 gbk 失败面（D2026-1031-05）：cp932 前置会把常用中文 GBK 静默
误判为 cp932（实测），不得前移。纯函数，无 IO。
"""
from __future__ import annotations


def sniff_text_encoding(data: bytes) -> tuple[str, bool]:
    """嗅探字节流文本编码，返回 ``(编码名, 是否可信)``。

    - BOM 命中：utf-8-sig / utf-16（可信）；
    - 无 BOM：按候选序 "utf-8" → "gbk" → "cp932" 逐个严格解码，
      首个成功者即判定结果并标可信；
    - 全部候选失败：("utf-8", False)，调用方按编码无法识别处理。
    """
    if data.startswith(b"\xef\xbb\xbf"):
        return ("utf-8-sig", True)
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return ("utf-16", True)
    for enc in ("utf-8", "gbk", "cp932"):
        try:
            data.decode(enc)
        except UnicodeDecodeError:
            continue
        return (enc, True)
    return ("utf-8", False)
