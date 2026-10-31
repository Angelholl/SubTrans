# 卡D6（D2026-1031-07 周末续燃补卡池）：line_breaker 切分边界与 CLI 补测。
# 全部伪段对象＋tmp_path，零模型零网络；main() 一律 in-process 调用
# （monkeypatch sys.argv＋断言返回值/SystemExit，不起真实子进程）。
import json
import sys

from subtransjav.refine.line_breaker import (
    POLICY_DEFAULTS,
    _cov_span,
    break_segment,
    main,
)


def _w(word: str, start: float | None = None,
       end: float | None = None) -> dict:
    w: dict = {"word": word}
    if start is not None:
        w["start"] = start
    if end is not None:
        w["end"] = end
    return w


def _seg(words: list[dict]) -> dict:
    starts = [w["start"] for w in words if w.get("start") is not None]
    ends = [w["end"] for w in words if w.get("end") is not None]
    return {"start": starts[0] if starts else 0.0,
            "end": ends[-1] if ends else 0.0,
            "text": "".join(str(w["word"]) for w in words),
            "words": words}


def _chars(seg: dict) -> int:
    return len("".join(str(seg.get("text") or "").split()))


class TestCoverageSpan:
    def test_missing_endpoint_returns_none(self):
        # 缺 start 或缺 end 任一 → None（不猜、不补 0）
        assert _cov_span([_w("あ")]) is None
        assert _cov_span([_w("あ", start=0.5)]) is None
        assert _cov_span([_w("あ", end=0.5)]) is None
        assert _cov_span([_w("あ", start=0.5, end=1.5)]) == (0.5, 1.5)
        # 混合词：只取有值端点，缺值的词被跳过而非 KeyError
        assert _cov_span([_w("あ", start=1.0, end=2.0), _w("い", end=3.0)]) == (1.0, 3.0)


class TestBreakSegmentPassthrough:
    def test_uncuttable_shapes_return_seg_as_is(self):
        # ① 词数 <2
        one = _seg([_w("あ" * 20, start=0.0, end=5.0)])
        assert break_segment(one) == [one]
        # ② 未超字符上限
        short = _seg([_w("あ" * 8, start=0.0, end=1.0),
                      _w("い" * 8, start=1.0, end=2.0)])
        assert _chars(short) <= POLICY_DEFAULTS["max_chars"]
        assert break_segment(short) == [short]
        # ③ 超上限但无任何可用词界时间戳（cuts 为空）→ 原样返回
        no_ts = _seg([_w("あ" * 10, start=0.0), _w("い" * 10),
                      _w("う" * 10, end=4.0)])
        assert _chars(no_ts) > POLICY_DEFAULTS["max_chars"]
        assert break_segment(no_ts) == [no_ts]


class TestGreedyAccumulation:
    def test_window_without_cut_keeps_accumulating(self):
        # w0 缺 end → 词界 0 不可切；窗内（base=0）无合法切点时必须继续累计，
        # 直到词界 1（w1 停顿 0.5s）才切。
        seg = _seg([_w("あ" * 4, start=0.0),
                    _w("い" * 12, start=1.0, end=2.0),
                    _w("う" * 12, start=2.5, end=3.5)])
        parts = break_segment(seg)
        assert len(parts) == 2
        # 首片含 w0+w1（16 字），未被“窗内无切点”误吞或误切
        assert parts[0]["text"] == "あ" * 4 + "い" * 12
        assert parts[0]["start"] == 0.0 and parts[0]["end"] == 2.0
        assert parts[1]["start"] == 2.5 and parts[1]["end"] == 3.5
        assert "".join(p["text"] for p in parts) == "".join(seg["text"])


class TestMinDurMerge:
    def test_short_piece_merges_into_neighbour_within_char_cap(self):
        # 末片仅 0.1s → 后向并入前片（8+8=16 恰在上限内）
        backward = _seg([_w("あ" * 8, start=0.0, end=1.0),
                         _w("い" * 8, start=1.0, end=2.0),
                         _w("う" * 8, start=2.5, end=2.6)])
        parts = break_segment(backward)
        assert len(parts) == 2
        assert parts[-1]["text"] == "い" * 8 + "う" * 8
        assert (parts[-1]["end"] - parts[-1]["start"]) >= POLICY_DEFAULTS["min_dur_s"]

        # 首片仅 0.1s → 前向并入第二片（1+15=16 恰在上限内）
        forward = _seg([_w("あ", start=0.0, end=0.1),
                        _w("い" * 15, start=0.5, end=2.0),
                        _w("う" * 8, start=2.5, end=3.5)])
        merged = break_segment(forward)
        assert merged[0]["text"] == "あ" + "い" * 15
        assert merged[0]["start"] == 0.0 and merged[0]["end"] == 2.0
        assert (merged[0]["end"] - merged[0]["start"]) >= POLICY_DEFAULTS["min_dur_s"]


class TestMainCli:
    def test_schema_mismatch_returns_rc2(self, tmp_path, monkeypatch, capsys):
        src = tmp_path / "words.json"
        src.write_text(json.dumps({"schema": "other/0", "segments": []}),
                       encoding="utf-8")
        out = tmp_path / "out.srt"
        monkeypatch.setattr(sys, "argv", [
            "line_breaker", "--sidecar", str(src), "--srt-out", str(out)])
        assert main() == 2
        assert "schema" in capsys.readouterr().out
        assert not out.exists()
        assert not (tmp_path / "out.srt.words.json").exists()

    def test_writes_srt_and_sidecar_with_custom_out(self, tmp_path, monkeypatch):
        words = [_w("あ" * 8, start=0.0, end=1.0),
                 _w("い" * 8, start=1.0, end=2.0),
                 _w("う" * 8, start=2.5, end=3.5)]
        seg = _seg(words)
        src = tmp_path / "words.json"
        src.write_text(json.dumps({"schema": "subtransjav.ct2.words/1",
                                   "segments": [seg], "src": "synthetic"},
                                  ensure_ascii=False), encoding="utf-8")
        srt = tmp_path / "out.srt"
        # ① 缺省 sidecar 路径 = <srt-out>.words.json
        monkeypatch.setattr(sys, "argv", [
            "line_breaker", "--sidecar", str(src), "--srt-out", str(srt)])
        assert main() == 0
        srt_text = srt.read_text(encoding="utf-8")
        assert "00:00:00,000 --> 00:00:01,000" in srt_text
        assert srt_text.count("-->") == 3
        assert "00:00:02,500 --> 00:00:03,500" in srt_text
        side = tmp_path / "out.srt.words.json"
        payload = json.loads(side.read_text(encoding="utf-8"))
        assert payload["schema"] == "subtransjav.ct2.words/1"
        assert payload["broken_by"] == "line_breaker/1"
        assert payload["src"] == "synthetic"           # 原 sidecar 字段原样透传
        assert len(payload["segments"]) == 3
        assert "".join(s["text"] for s in payload["segments"]) == seg["text"]

        # ② --sidecar-out 自定义路径生效（缺省文件不再产生）
        custom = tmp_path / "custom-words.json"
        srt2 = tmp_path / "out2.srt"
        monkeypatch.setattr(sys, "argv", [
            "line_breaker", "--sidecar", str(src), "--srt-out", str(srt2),
            "--sidecar-out", str(custom)])
        assert main() == 0
        assert custom.exists()
        assert not (tmp_path / "out2.srt.words.json").exists()
        custom_payload = json.loads(custom.read_text(encoding="utf-8"))
        assert custom_payload["broken_by"] == "line_breaker/1"
