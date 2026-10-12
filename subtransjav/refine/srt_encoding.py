"""SRT 字幕编码嗅探（2.6.1 批 2a N1，D2026-1002-09）。

判定序：BOM（utf-8-sig / utf-16 le/be）→ utf-8 严格解码 → gbk 兜底
→ 全部失败则标记不可信（由调用方报错，本模块不抛异常）。
纯函数，无 IO。
"""
from __future__ import annotations


def sniff_text_encoding(data: bytes) -> tuple[str, bool]:
    """嗅探字节流文本编码，返回 ``(编码名, 是否可信)``。

    - BOM 命中：utf-8-sig / utf-16（可信）；
    - 无 BOM：utf-8 严格解码成功 → ("utf-8", True)；
    - utf-8 失败：gbk 解码成功 → ("gbk", True)；
    - 再失败：("utf-8", False)，调用方按编码无法识别处理。
    """
    if data.startswith(b"\xef\xbb\xbf"):
        return ("utf-8-sig", True)
    if data.startswith(b"\xff\xfe") or data.startswith(b"\xfe\xff"):
        return ("utf-16", True)
    try:
        data.decode("utf-8")
        return ("utf-8", True)
    except UnicodeDecodeError:
        pass
    try:
        data.decode("gbk")
        return ("gbk", True)
    except UnicodeDecodeError:
        return ("utf-8", False)
