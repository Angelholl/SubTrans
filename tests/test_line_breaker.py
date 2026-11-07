# 3.2.1 断行器钉（D2026-1028-03）：确定性切分+三顺序不变量（文本守恒/时间轴
# 守恒/幂等）+CPS 改善。纯合成词级夹具，零模型零网络。
from subtrans.refine.line_breaker import (
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


# ------------------------------------------------ 候卡①（D2026-1108 owner 拍板）
# 尾段/中段达标复切回归钉：d1107 卡B 真数据缺口——切点回溯停顿边界或窗口结转
# 后，产出片可超 max_chars（真数据 4 例 17–19 字），且该超限片重喂即被再切
# ＝幂等反例。修复后：一切输出片 ≤ 上限（单词超限原样保留＝无合法切点口径），
# 幂等恢复。


class TestTailRecut:
    def _real_shape(self):
        # 真数据同型（W-2026-015 seg#272）：段首单词＋大停顿＋尾段 18 字
        # （前缀和只在末词越限 → 主循环停顿回溯后整段尾段未再检；短片
        # 并入被 cap 拒绝 1+18>16 → 超限尾段落盘）
        spec = [("宅", 0.0, 0.3)]
        tail_words = ["あああ", "いいい", "ううう", "えええ", "かきくけこさ"]
        for i, w in enumerate(tail_words):
            spec.append((w, 4.68 + i * 0.2, 4.68 + i * 0.2 + 0.15))
        return _seg(_words(spec))

    def test_no_part_over_cap(self):
        parts = break_segment(self._real_shape())
        assert len(parts) >= 2
        assert all(_chars(p) <= POLICY_DEFAULTS["max_chars"] for p in parts)

    def test_idempotent_on_real_shape(self):
        parts = break_segment(self._real_shape())
        again = break_segments(parts)
        assert [p["text"] for p in again] == [p["text"] for p in parts]
        assert [p["start"] for p in again] == [p["start"] for p in parts]

    def test_invariants_hold_on_recut(self):
        seg = self._real_shape()
        parts = break_segment(seg)
        # 文本守恒＋时间轴覆盖守恒（复切不改词分区）
        assert "".join(p["text"] for p in parts).replace(" ", "") \
            == seg["text"].replace(" ", "")
        assert parts[0]["start"] == round(
            min(w["start"] for w in seg["words"]), 3)
        assert parts[-1]["end"] == round(
            max(w["end"] for w in seg["words"]), 3)

    def test_tail_exactly_cap_untouched(self):
        # 尾段恰在上限＝达标，不触发复切
        spec = [("あ", 0.0, 0.3)]
        chars = "い" * 16
        for i, c in enumerate(chars):
            spec.append((c, 4.68 + i * 0.2, 4.68 + i * 0.2 + 0.15))
        parts = break_segment(_seg(_words(spec)))
        assert all(_chars(p) <= POLICY_DEFAULTS["max_chars"] for p in parts)
        assert len(parts) == 2 and _chars(parts[1]) == 16

    def test_single_over_cap_word_kept(self):
        # 单词超上限＝无合法切点口径一致，原样保留（不破幂等）
        w = _words([("あ" * 20, 0.0, 1.0), ("い", 1.5, 1.8)])
        parts = break_segment(_seg(w))
        assert any(_chars(p) == 20 for p in parts)
        again = break_segments(parts)
        assert [p["text"] for p in again] == [p["text"] for p in parts]
