"""srt_encoding 嗅探纯函数单测（2.6.1 批 2a N1，D2026-1002-09）。

八用例：BOM / 纯 utf-8 / gbk 中文样本 / 坏字节（双解码失败 → 不可信）＋
C1 卡A（D2026-1031-05）四钉：GBK 反向主钉（防 cp932-first 回潮）、
SJIS 半角假名债务钉（cp932 兜 gbk 失败面）、gbk 可解的 SJIS 已知缺口钉、
gbk/cp932 双失败负向钉。
"""
import pytest

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


# ---------------------------------------------------------------------------
# C1 卡A（D2026-1031-05）：SJIS 判定梯 a' 四钉
# ---------------------------------------------------------------------------

def test_sniff_gbk_chinese_not_stolen_by_cp932():
    """反向主钉：常用中文 GBK 句必须仍判 gbk 且逐字还原。

    cp932 可解码该字节串但出乱码，故 cp932 不得置于 gbk 之前
    （D2026-1031-05 选型 a'）。断言值等值，不只断言编码名。
    """
    text = "中文字幕测试，第一句话。"
    sample = text.encode("gbk")
    enc, ok = sniff_text_encoding(sample)
    assert (enc, ok) == ("gbk", True)
    assert sample.decode(enc) == text


def test_sniff_cp932_halfwidth_kana_debt():
    """债务钉：SJIS 半角假名（0xA1-0xDF 单字节区）使 gbk 失败 → cp932 兜底。

    现状（a' 前）返 ("utf-8", False) → api 层 review_srt_bad_encoding 硬错。
    """
    text = "ﾃｽﾄ1\n"
    sample = text.encode("cp932")
    with pytest.raises(UnicodeDecodeError):
        sample.decode("gbk")  # 前提：gbk 对半角假名必失败
    enc, ok = sniff_text_encoding(sample)
    assert (enc, ok) == ("cp932", True)
    assert sample.decode(enc) == text


def test_sniff_cp932_fullwidth_kana_known_gap():
    """已知缺口钉：gbk 可解码的 SJIS 静默乱码（本卡有意不修）。

    残余缺口（D2026-1031-05）：gbk 能解则 gbk 胜出、解码出乱码但标可信；
    启发式打分另立时本钉有意翻转。
    """
    text = "こんにちは、字幕です。"
    sample = text.encode("cp932")
    enc, ok = sniff_text_encoding(sample)
    assert (enc, ok) == ("gbk", True)
    assert sample.decode(enc) != text


def test_sniff_gbk_cp932_both_fail_untrusted():
    """负向钉：gbk 与 cp932 双失败不误吞 → ("utf-8", False)。

    与既有坏字节用例同口径，补断言编码名与 cp932 兜底不吞坏字节。
    """
    sample = b"1\n00:00:01,000 --> 00:00:02,000\nabc\x81"
    with pytest.raises(UnicodeDecodeError):
        sample.decode("cp932")
    assert sniff_text_encoding(sample) == ("utf-8", False)
