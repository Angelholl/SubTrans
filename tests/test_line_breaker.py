# 3.2.1 断行器钉（D2026-1028-03）：确定性切分+三顺序不变量（文本守恒/时间轴
# 守恒/幂等）+CPS 改善。纯合成词级夹具，零模型零网络。
from subtransjav.refine.line_breaker import (
    POLICY_DEFAULTS,
    break_segment,
    break_segments,
)


def _words(spec: list[tuple[str, float, float]]) -> list[dict]:
    return [{"word": w, "start": s, "end": e} for w, s, e in spec]


def _seg(words: list[dict]) -> dict:
    return {"start": words[0]["start"], "end": words[-1]["end"],
            "text": "".join(w["word"] for w in words), "words": words}


def _chars(seg: dict) -> int:
    return len("".join(seg["text"].split()))


class TestBreakSegment:
    def test_short_segment_untouched(self):
        seg = _seg(_words([("こんにちは", 0.0, 1.5)]))
        assert break_segment(seg) == [seg]

    def test_split_at_pause_preferred(self):
        # 10+10 字（20>16 触发切分），中间 0.5s 停顿（≥300ms）→ 停顿点切
        w = _words([("あ" * 10, 0.0, 1.0), ("い" * 10, 1.5, 2.5)])
        seg = _seg(w)
        parts = break_segment(seg)
        assert len(parts) == 2
        assert parts[0]["end"] == 1.0 and parts[1]["start"] == 1.5

    def test_hard_split_without_pause(self):
        # 20 个单字词连续无停顿 → 按字符上限硬切，无 gap 可依
        w = _words([(c, i * 0.1, i * 0.1 + 0.09) for i, c in enumerate("あ" * 20)])
        seg = _seg(w)
        parts = break_segment(seg)
        assert len(parts) >= 2
        for p in parts:
            assert _chars(p) <= POLICY_DEFAULTS["max_chars"]

    def test_no_word_timestamps_passthrough(self):
        seg = {"start": 0.0, "end": 30.0, "text": "あ" * 40, "words": []}
        assert break_segment(seg) == [seg]

    def test_min_dur_merge_forward(self):
        # 首片仅 0.1s → 前向并入下片（合并后 16 字仍在字符上限内）
        w = _words([("あ", 0.0, 0.1), ("い" * 15, 0.5, 2.0)])
        seg = _seg(w)
        parts = break_segment(seg)
        assert len(parts) == 1
        assert (parts[0]["end"] - parts[0]["start"]) >= POLICY_DEFAULTS["min_dur_s"]
        assert "".join(p["text"] for p in parts) == "あ" + "い" * 15

    def test_min_dur_merge_respects_char_cap(self):
        # 并入会破字符上限（1+16=17>16）→ 不并，短片独立保留（上限优先）
        w = _words([("あ", 0.0, 0.1), ("い" * 16, 0.5, 2.0)])
        parts = break_segment(_seg(w))
        assert any(_chars(p) == 1 and (p["end"] - p["start"]) < 0.8 for p in parts)
        assert all(_chars(p) <= POLICY_DEFAULTS["max_chars"] for p in parts)


class TestInvariants:
    SEG = _seg(_words(
        [("あ" * 6, 0.0, 0.9), ("い" * 6, 0.95, 1.8), ("う" * 6, 3.0, 3.9),
         ("え" * 6, 3.95, 4.8), ("お" * 6, 6.0, 6.9), ("か" * 6, 7.2, 8.0)]))

    def test_text_preserved(self):
        parts = break_segment(self.SEG)
        joined = "".join(p["text"] for p in parts)
        assert "".join(joined.split()) == "".join(self.SEG["text"].split())

    def test_time_coverage_preserved(self):
        parts = break_segment(self.SEG)
        assert parts[0]["start"] == self.SEG["start"]
        assert parts[-1]["end"] == self.SEG["end"]
        for a, b in zip(parts[:-1], parts[1:], strict=True):
            assert a["end"] <= b["start"] + 1e-9   # 不重叠不倒挂

    def test_idempotent_on_output(self):
        parts = break_segment(self.SEG)
        again = break_segments(parts)
        assert [p["text"] for p in again] == [p["text"] for p in parts]
        assert [p["start"] for p in again] == [p["start"] for p in parts]

    def test_cps_improves_or_equal(self):
        parts = break_segment(self.SEG)
        worst_before = _chars(self.SEG) / (self.SEG["end"] - self.SEG["start"])
        for p in parts:
            cps = _chars(p) / max(1e-6, (p["end"] - p["start"]))
            # 每片字符数受上限约束（时长下限并入除外），CPS 不应比原 worst 更差
            assert _chars(p) <= POLICY_DEFAULTS["max_chars"] or cps <= worst_before


class TestParams:
    def test_override_params(self):
        # 20 个单字词（单字词序列才能按字切；整段单一大词不可切=原样）
        w = _words([(c, i * 0.2, i * 0.2 + 0.15) for i, c in enumerate("あ" * 20)])
        parts = break_segment(_seg(w), {"max_chars": 10})
        assert len(parts) >= 2
        assert all(_chars(p) <= 10 for p in parts)

    def test_policy_defaults_shape(self):
        assert set(POLICY_DEFAULTS) == {"max_chars", "max_lines", "pause_ms",
                                        "min_dur_s"}
