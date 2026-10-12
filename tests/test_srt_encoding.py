"""srt_encoding 嗅探纯函数单测（2.6.1 批 2a N1，D2026-1002-09）。

四用例：BOM / 纯 utf-8 / gbk 中文样本 / 坏字节（双解码失败 → 不可信）。
"""
from subtransjav.refine.srt_encoding import sniff_text_encoding


def test_sniff_utf8_bom():
    enc, ok = sniff_text_encoding(
        b"\xef\xbb\xbf1\n00:00:01,000 --> 00:00:02,000\n\xe6\xb5\x8b\xe8\xaf\x95\n")
    assert (enc, ok) == ("utf-8-sig", True)


def test_sniff_plain_utf8():
    enc, ok = sniff_text_encoding(
        "1\n00:00:01,000 --> 00:00:02,000\n字幕内容\n".encode())
    assert (enc, ok) == ("utf-8", True)


def test_sniff_gbk_fallback():
    sample = "1\n00:00:01,000 --> 00:00:02,000\n简体中文测试台词\n".encode("gbk")
    enc, ok = sniff_text_encoding(sample)
    assert (enc, ok) == ("gbk", True)


def test_sniff_bad_bytes_untrusted():
    # 结尾孤立 \x81（GBK 截断双字节首字节）：utf-8 与 gbk 双双解码失败
    enc, ok = sniff_text_encoding(b"1\n00:00:01,000 --> 00:00:02,000\nabc\x81")
    assert ok is False
