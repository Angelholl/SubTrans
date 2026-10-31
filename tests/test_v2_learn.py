"""v2_learn 学习开关与 TM 准入补测（卡D7，纯测试新增）。

覆盖面（全部 monkeypatch＋tmp_path 伪 S2 产物，零真实网络调用）：
- `_auto_learn_glossary`：glossary_learn_enabled=False 记账跳过、
  resolve_endpoint 异常回退默认端点、新增术语计数打印；
- `_learn_to_tm`：post_validate 导入失败降级、五类准入缺陷分类跳过、
  时间轴不对应/合并行不学习、学习异常返回 None 并记账。
"""

import sys
from types import SimpleNamespace

from subtransjav.refine import v2_learn as vl
from subtransjav.refine.risk import SEVERITY_INFO, RiskCollector
from subtransjav.refine.tm import TranslationMemory


def _ts(sec: float) -> str:
    """秒 → SRT 时间轴片段（毫秒取整）。"""
    ms = int(round(sec * 1000))
    return f"00:00:{ms // 1000:02d},{ms % 1000:03d}"


def _entry(index: int, start: float, end: float, text: str) -> dict:
    return {"index": index, "timing": f"{_ts(start)} --> {_ts(end)}", "text": text}


# ---------------------------------------------------------------------------
# 组1：glossary_learn_enabled=False 记账跳过，且不调用学习函数
# ---------------------------------------------------------------------------

def test_auto_learn_disabled_records_skip(monkeypatch, tmp_path, capsys):
    calls = []

    def _fake_learn(*args, **kwargs):
        calls.append((args, kwargs))
        return 0

    monkeypatch.setattr("subtransjav.refine.glossary_learn.learn_from_s2_output",
                        _fake_learn)
    collector = RiskCollector()
    cfg = SimpleNamespace(glossary_learn_enabled=False)

    vl._auto_learn_glossary(cfg, str(tmp_path / "in.srt"),
                            str(tmp_path / "out.srt"),
                            collector=collector, file_name="demo.srt")

    assert calls == []                       # 学习路径零调用
    assert len(collector.events) == 1
    ev = collector.events[0]
    assert (ev.stage, ev.file) == ("final", "demo.srt")
    assert ev.reason == "glossary_learn_enabled=False"
    assert ev.action == "跳过 learned 词库学习（配置治理开关）"
    assert ev.severity == SEVERITY_INFO
    assert "跳过" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 组2：端点解析异常回退默认端点；新增术语打印计数
# ---------------------------------------------------------------------------

def test_auto_learn_endpoint_failure_falls_back_and_prints_count(monkeypatch,
                                                                tmp_path, capsys):
    captured = {}

    def _fake_learn(in_path, out_final_path, learned_path, **kwargs):
        captured.update({"in_path": in_path, "out_path": out_final_path,
                         "learned_path": learned_path, **kwargs})
        return 7

    monkeypatch.setattr("subtransjav.refine.glossary_learn.learn_from_s2_output",
                        _fake_learn)
    glossary = tmp_path / "glossary_learned.csv"
    monkeypatch.setattr(vl, "learned_glossary_path", lambda: str(glossary))

    class _Cfg:
        glossary_learn_enabled = True
        timeout_http = 9.5
        timeout_probe = 2.5

        def resolve_endpoint(self, provider):
            assert provider == "lmstudio"
            raise OSError("端点未配置")

    vl._auto_learn_glossary(_Cfg(), str(tmp_path / "in.srt"),
                            str(tmp_path / "out.srt"), file_name="demo.srt")

    out = capsys.readouterr().out
    assert captured["endpoint"] == "http://localhost:1234/v1"
    assert captured["timeout_http"] == 9.5
    assert captured["timeout_probe"] == 2.5
    assert captured["learned_path"] == str(glossary)
    assert captured["in_path"] == str(tmp_path / "in.srt")
    assert "新增 7 条术语" in out


# ---------------------------------------------------------------------------
# 组3：post_validate 导入失败 → 降级判定（仅 [未翻译] 前缀，缺陷扫描关闭）
# ---------------------------------------------------------------------------

def test_learn_to_tm_downgrades_when_post_validate_unavailable(monkeypatch,
                                                               tmp_path):
    # sys.modules 置 None → 函数内 ``from .post_validate import ...`` 抛 ImportError
    monkeypatch.setitem(sys.modules, "subtransjav.refine.post_validate", None)
    tm = TranslationMemory(str(tmp_path / "tm.db"))

    orig = [
        _entry(1, 0, 1, "これは何ですか"),
        _entry(2, 2, 3, "とても綺麗だ"),
        _entry(3, 4, 5, "ありがとうございます"),
    ]
    final = [
        _entry(1, 0, 1, "这是什么"),                 # 干净 → 学习
        _entry(2, 2, 3, "[未翻译] 保留原文"),         # 降级前缀判定 → 跳过
        _entry(3, 4, 5, "ありがとう"),                # 假名残留：降级不扫缺陷 → 学习
    ]

    added = vl._learn_to_tm(tm, orig, final, file_name="demo.srt")

    assert added == 2
    assert tm.lookup_exact("これは何ですか", stage=1) == "这是什么"
    assert tm.lookup_exact("とても綺麗だ", stage=1) is None
    # 真实 post_validate 会把假名译法判 kana 拦截；降级后缺陷扫描关闭才入库
    assert tm.lookup_exact("ありがとうございます", stage=1) == "ありがとう"


# ---------------------------------------------------------------------------
# 组4a：五类准入缺陷分类跳过（kana/leak/src_prefix/placeholder/len_ratio）
# ---------------------------------------------------------------------------

def test_learn_to_tm_skips_all_defect_classes(tmp_path, capsys):
    tm = TranslationMemory(str(tmp_path / "tm.db"))

    orig = [
        _entry(1, 0, 1, "こんにちは、元気ですか。"),
        _entry(2, 2, 3, "設定画面を開きます。"),
        _entry(3, 4, 5, "ABC"),
        _entry(4, 6, 7, "彼は学生です。"),
        _entry(5, 8, 9, "とても長い文章をここに書いておきます"),
    ]
    final = [
        _entry(1, 0, 1, "ありがとうございます"),        # kana
        _entry(2, 2, 3, "打开设置Translation"),          # leak
        _entry(3, 4, 5, "ABCD"),                        # src_prefix
        _entry(4, 6, 7, "他无对应条目"),                 # placeholder
        _entry(5, 8, 9, "对"),                           # len_ratio
    ]

    added = vl._learn_to_tm(tm, orig, final, file_name="demo.srt")
    out = capsys.readouterr().out

    assert added == 0
    assert "跳过 5 行" in out
    assert "假名1/泄漏1/源残留1/占位符1/长度比1" in out


# ---------------------------------------------------------------------------
# 组4b：时间轴不对应不消费；合并行不学习且不计门禁跳过；异常返回 None 并记账
# ---------------------------------------------------------------------------

def test_learn_to_tm_timeline_and_exception_paths(tmp_path, capsys):
    tm = TranslationMemory(str(tmp_path / "tm.db"))

    # 原文行1 无对应终稿（起点错位）→ 不消费 final 行，行2 仍能正常学习
    orig = [_entry(1, 0, 1, "A原文"), _entry(2, 2, 3, "B原文")]
    final = [_entry(1, 2, 3, "B译文")]
    assert vl._learn_to_tm(tm, orig, final) == 1
    assert tm.lookup_exact("B原文", stage=1) == "B译文"

    # 同起点被合并（终点延长）→ 不学习也不消费，不计入任何门禁分类
    orig = [_entry(1, 0, 1, "甲"), _entry(2, 0, 1, "乙")]
    final = [_entry(1, 0, 2, "合并译文")]
    assert vl._learn_to_tm(tm, orig, final) == 0
    assert "跳过 0 行" in capsys.readouterr().out

    # 入库异常 → 打印失败、记账、返回 None
    collector = RiskCollector()

    class _BrokenTM:
        def store_batch(self, pairs, source_name=None):
            raise RuntimeError("db boom")

    orig = [_entry(1, 0, 1, "こんにちは")]
    final = [_entry(1, 0, 1, "你好")]
    result = vl._learn_to_tm(_BrokenTM(), orig, final,
                             collector=collector, file_name="demo.srt")
    out = capsys.readouterr().out

    assert result is None
    assert "翻译记忆库学习失败: db boom" in out
    assert len(collector.events) == 1
    ev = collector.events[0]
    assert ev.reason == "翻译记忆库学习失败: db boom"
    assert ev.action == "跳过TM学习"
    assert ev.severity == SEVERITY_INFO
