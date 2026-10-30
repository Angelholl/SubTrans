"""双 pass 覆盖合并纯函数钉（3.2.0 件A，D2026-1029-02 拍板①）。

规则钉：pass1 主干逐段原样保留；pass2 仅在时长 > 阈值的空洞内、完全
落界且与主干零重叠时被采纳；越界/重叠弃置；合并结果幂等。
"""

from subtransjav.refine.pass_merge import (
    GAP_THRESHOLD_S,
    adopted_pass2_indices,
    merge_passes,
)


def _seg(start: float, end: float, text: str = "t") -> dict:
    return {"start": start, "end": end, "text": text, "words": []}


def _assert_strictly_increasing(segs: list[dict]) -> None:
    for prev, cur in zip(segs, segs[1:], strict=False):
        assert float(cur["start"]) >= float(prev["end"]), \
            f"合并后时轴重叠: {prev} -> {cur}"


def test_text_conservation_pass1_kept_verbatim():
    """文本守恒：pass1 段逐段原样保留（对象同一，文本/时间轴零改动）。"""
    pass1 = [_seg(0.0, 1.0, "甲"), _seg(2.5, 3.5, "乙")]
    pass2 = [_seg(1.2, 1.8, "补")]
    merged = merge_passes(pass1, pass2, duration=5.0)
    assert merged[0] is pass1[0] and merged[2] is pass1[1]
    assert [s["text"] for s in merged] == ["甲", "补", "乙"]
    assert [(s["start"], s["end"]) for s in merged] == \
        [(0.0, 1.0), (1.2, 1.8), (2.5, 3.5)]
    _assert_strictly_increasing(merged)


def test_gap_above_threshold_adopted():
    """空洞时长 > 阈值（预注册 1.0s）→ 采纳完全落界的 pass2 段。"""
    pass1 = [_seg(0.0, 2.0), _seg(3.5, 4.0)]
    pass2 = [_seg(2.2, 3.0, "填洞")]
    merged = merge_passes(pass1, pass2, duration=6.0)
    assert [s["text"] for s in merged] == ["t", "填洞", "t"]
    _assert_strictly_increasing(merged)


def test_gap_at_threshold_not_filled():
    """空洞时长 == 阈值（不大于）→ 不采纳。"""
    pass1 = [_seg(0.0, 2.0), _seg(3.0, 4.0)]      # 空洞恰 1.0s
    pass2 = [_seg(2.1, 2.9, "不填")]
    merged = merge_passes(pass1, pass2, duration=6.0)
    assert [s["text"] for s in merged] == ["t", "t"]
    assert GAP_THRESHOLD_S == 1.0


def test_out_of_gap_candidates_discarded():
    """越界（跨空洞界/超片尾）pass2 段一律弃置，不做裁剪。"""
    pass1 = [_seg(0.0, 2.0), _seg(3.5, 4.0)]
    pass2 = [_seg(1.5, 2.5, "跨界"), _seg(5.0, 7.0, "超片尾")]
    merged = merge_passes(pass1, pass2, duration=6.0)
    assert [s["text"] for s in merged] == ["t", "t"]


def test_overlapping_pass2_discarded():
    """与 pass1 段重叠（含部分重叠）→ 弃置（覆盖优先，不改主干）。"""
    pass1 = [_seg(0.0, 2.0, "主干"), _seg(4.0, 5.0, "主干2")]
    pass2 = [_seg(1.0, 1.5, "重叠"), _seg(3.9, 4.2, "贴边重叠")]
    merged = merge_passes(pass1, pass2, duration=8.0)
    assert [s["text"] for s in merged] == ["主干", "主干2"]


def test_no_gap_passthrough():
    """主干连续无空洞 → 直通（pass2 无从插入）。"""
    pass1 = [_seg(0.0, 2.0, "甲"), _seg(2.0, 5.0, "乙")]
    pass2 = [_seg(1.0, 1.5, "候选"), _seg(2.5, 3.0, "候选2")]
    merged = merge_passes(pass1, pass2, duration=5.0)
    assert merged == pass1


def test_head_and_tail_gaps_filled():
    """片首/片尾空区（>阈值）照常采纳；缺 duration 时片尾上界开放。"""
    pass1 = [_seg(2.0, 3.0, "中")]
    pass2 = [_seg(0.2, 1.5, "片首"), _seg(4.0, 5.0, "片尾")]
    merged = merge_passes(pass1, pass2, duration=6.0)
    assert [s["text"] for s in merged] == ["片首", "中", "片尾"]
    _assert_strictly_increasing(merged)
    # duration 缺省：片尾候选仍可采纳（上界开放），但片首/中间规则不变
    merged_no_dur = merge_passes(pass1, pass2)
    assert [s["text"] for s in merged_no_dur] == ["片首", "中", "片尾"]


def test_idempotent():
    """幂等：merge(merge(p1,p2),p2) == merge(p1,p2)。"""
    pass1 = [_seg(0.0, 2.0, "甲"), _seg(5.0, 6.0, "乙")]
    pass2 = [_seg(2.5, 3.5, "补1"), _seg(6.5, 7.5, "补2"),
             _seg(1.0, 1.5, "重叠")]
    once = merge_passes(pass1, pass2, duration=9.0)
    twice = merge_passes(once, pass2, duration=9.0)
    assert twice == once
    _assert_strictly_increasing(once)


def test_adopted_indices_mapping():
    """采纳映射（dualpass sidecar 审计用）：只报被采纳的 pass2 下标。"""
    pass1 = [_seg(0.0, 2.0)]
    pass2 = [_seg(2.5, 3.0, "采纳"), _seg(0.5, 1.0, "重叠")]
    merged = merge_passes(pass1, pass2, duration=4.0)
    assert adopted_pass2_indices(pass1, pass2, merged) == [0]
