"""疑似漏听三维置信门 + 高置信自动补行插入通道（3.0 批3 3A 纯函数层）。

======================================================================
生产者与启用门（D2026-1009-02 批3 / C22）
======================================================================
- 生产者＝全链路自动化链内 F4 段（修复 → 漏听 → 复验状态机的"漏听"
  一环）：批量转写（asr_env.batch_transcribe_clips）→ 本模块
  classify_transcript 三维分档 → 高置信走 insert_candidates 自动补行，
  低置信/判空直接放弃（owner 终裁：无核对卡，≤1s 语音能量一律放弃）；
- 启用门＝C22 校准（tools/c22_calibration.py 离线回放，高置信桶精确率
  Wilson 95% 置信下界 ≥0.95 才允许真自动补行）：运行侧读
  ``config/fullchain_c22.json`` 的 enabled 标志（3B 接线，本模块不读
  配置——门控归链路层，这里只给纯函数与恒等式）；
- 台账落账（category="auto_insert"、old_text 空串、index 允许 None）
  归链路层生产者，10 键闭集契约由 tests/test_action_retranslate.py
  钉住；回滚删行语义（C16）亦批3 接线。

阈值同源声明（防口径漂移）：
- 置信三维阈值 no_speech_prob/avg_logprob/compression_ratio 直接复用
  asr_meta 遥测低信任常量（实测出处见该模块 _TRUST_* 注释）；
- 荒谬性密度上限＝3 ×（quality_report CPS CJK 基准 × 容差），量级依据：
  行动层 CPS 阈值族（quality_report._CPS_*），补行是"窗口内凭空插入"，
  允许密度放宽到常速阅读上限的 3 倍，超过即判幻觉。
"""

from __future__ import annotations

from .asr_meta import (
    _TRUST_MAX_COMPRESSION_RATIO,
    _TRUST_MIN_MEAN_LOGPROB,
    _TRUST_NO_SPEECH_PROB,
)
from .audio_detect import _fmt_ms
from .quality_report import _CPS_CJK_BASE, _CPS_MIN_DURATION_S, _CPS_TOLERANCE
from .source_hallucination import _is_nonsense, _normalize_text
from .v2_premerge import _timing_span

# 语音能量 ≤1s 一律放弃（owner 终裁：1s 以内的语音能量放弃不影响观感）
SPEECH_MIN_SECONDS = 1.0
# 荒谬性密度上限（字符/语音秒）＝3 × CPS 阅读上限（依据见模块 docstring）
ABSURD_CHARS_PER_SEC = _CPS_CJK_BASE * _CPS_TOLERANCE * 3.0
# 补行时长换算的 CPS 上限（防挤压：窗口够长时时长至少给到阅读上限换算值）
INSERT_CPS_CAP = _CPS_CJK_BASE * _CPS_TOLERANCE
# 补行时长下限（防超短条目；与 quality_report._CPS_MIN_DURATION_S 同源）
INSERT_MIN_DURATION_S = _CPS_MIN_DURATION_S
# n-gram 重复判定参数（复用 source_hallucination 假名平铺信号 + 3-gram 主导）
_REPEAT_UNIT_MIN = 3
_REPEAT_GRAM_N = 3
_REPEAT_GRAM_RATIO = 0.5
_REPEAT_GRAM_MIN_LEN = 6


def _speech_overlap_s(timing: str,
                      windows: list[tuple[float, float]] | None) -> float:
    """间隙窗口与语音段的交集总时长（窗口无法解析/无窗口数据→0.0，
    由调用方决定是否跳过该门）。"""
    s0, e0 = _timing_span(timing)
    if s0 < 0 or not windows:
        return 0.0
    return sum(max(0.0, min(e0, e) - max(s0, s)) for s, e in windows)


def _repeat_signal(text: str) -> bool:
    """重复/循环信号（复用 source_hallucination 同源启发式）：

    - 假名单元整条平铺（2-4 字单元 ≥3 次，如 あいうあいうあいう）；
    - 3-gram 主导（长度 ≥6 的文本中同一 3-gram 占比 >0.5，跨段循环）。"""
    norm = _normalize_text(text)
    if not norm:
        return False
    from .source_hallucination import _unit_repeat_len
    if _unit_repeat_len(norm, _REPEAT_UNIT_MIN, 4) is not None:
        return True
    if len(norm) >= _REPEAT_GRAM_MIN_LEN:
        n = _REPEAT_GRAM_N
        grams = [norm[i:i + n] for i in range(0, len(norm) - n + 1)]
        if grams:
            top = max(grams.count(g) for g in set(grams))
            if top / len(grams) > _REPEAT_GRAM_RATIO:
                return True
    return False


def _absurd_signal(text: str) -> bool:
    """荒谬性信号：单字符占比异常（去空白后单一字符 ≥6 连铺）。"""
    compact = "".join((text or "").split())
    return len(compact) >= 6 and len(set(compact)) == 1


def classify_transcript(timing: str, segments: list, text_all: str,
                        speech_windows: dict,
                        *, overlap_s: float | None = None,
                        language: str = "ja") -> dict:
    """三维置信门（纯函数）：{"grade": "high"|"low"|"empty", "reasons": [...]}。

    判定序（D2026-1009-02 批3 拍板10/11）＝判空 → ≤1s 放弃 → 三维置信
    → 重复/循环 → 荒谬性 → language → 纯拟声 → 全过 high。

    - speech_windows：audio_detect.detect_speech_windows 返回形态
      {timing: [(start_s, end_s), ...]}；含 "__error" 键或本 timing 键
      缺省＝能量数据不可得 → 跳过 ≤1s 门（C18 诚实退化：门数据缺失时
      不判放弃，交由三维置信与后续信号兜底）；
    - overlap_s 显式传入时优先于 speech_windows（调用方已实测口径）；
    - language：多段模式由 runner 顶层 language 字段传递（非 ja → low）。
    """
    segs = segments if isinstance(segments, list) else []
    if not segs or not (text_all or "").strip():
        return {"grade": "empty", "reasons": ["empty_transcript"]}
    reasons: list[str] = []
    # b) ≤1s 语音能量一律放弃（owner 终裁；能量数据不可得则跳过此门）
    if overlap_s is not None:
        speech_s = float(overlap_s)
    elif (isinstance(speech_windows, dict) and timing in speech_windows):
        # 键存在（含空列表＝真实全静音）才参与判定；键缺省/带 __error
        # ＝能量数据不可得 → 跳过（C18，不静默判死）
        speech_s = _speech_overlap_s(timing,
                                     speech_windows.get(timing) or [])
    else:
        speech_s = None      # C18：能量门数据缺失，跳过（不静默判死）
    if speech_s is not None and speech_s <= SPEECH_MIN_SECONDS:
        return {"grade": "low",
                "reasons": ["speech_le_1s",
                            f"speech_s={speech_s:.2f}"]}
    # c) 置信三维（阈值同源 asr_meta._TRUST_*；nsp 取段级 max、logprob 取
    # 段级 mean——口径对齐 asr_meta.scene_low_trust 先例；nsp 或 logprob
    # 单独超阈即 low（补行是凭空插入，从严）；压缩比硬信号同源）。
    nsp_vals = [s.get("no_speech_prob") for s in segs
                if isinstance(s, dict) and s.get("no_speech_prob") is not None]
    lp_vals = [s.get("avg_logprob") for s in segs
               if isinstance(s, dict) and s.get("avg_logprob") is not None]
    cr_vals = [s.get("compression_ratio") for s in segs
               if isinstance(s, dict)
               and s.get("compression_ratio") is not None]
    if nsp_vals and max(nsp_vals) > _TRUST_NO_SPEECH_PROB:
        reasons.append("no_speech_prob_over")
    if lp_vals and (sum(lp_vals) / len(lp_vals)) < _TRUST_MIN_MEAN_LOGPROB:
        reasons.append("avg_logprob_under")
    if cr_vals and max(cr_vals) > _TRUST_MAX_COMPRESSION_RATIO:
        reasons.append("compression_ratio_over")
    if reasons:
        return {"grade": "low", "reasons": reasons}
    # d) 重复/循环
    if _repeat_signal(text_all):
        reasons.append("repeat_loop")
    # e) 荒谬性：文本长度/语音时长密度爆表（语音时长可得时）或单字符平铺
    compact_len = len("".join((text_all or "").split()))
    if _absurd_signal(text_all):
        reasons.append("absurd_single_char")
    if (speech_s is not None and speech_s > 0
            and compact_len / speech_s > ABSURD_CHARS_PER_SEC):
        reasons.append("absurd_density")
    if reasons:
        return {"grade": "low", "reasons": reasons}
    # f) language 非 ja → low（多段模式 runner 顶层传递）
    if (language or "").strip().lower() not in ("ja", "japanese", "jpn"):
        reasons.append("language_not_ja")
        return {"grade": "low", "reasons": reasons}
    # g) 纯拟声（source_hallucination nonsense_syllables 同源信号）
    norm = _normalize_text(text_all)
    if _is_nonsense(norm, {}):
        reasons.append("nonsense_syllables")
        return {"grade": "low", "reasons": reasons}
    return {"grade": "high", "reasons": []}


def insert_candidates(entries: list, picks: list) -> list:
    """插入通道（纯函数）：把 picks（{"timing": 间隙窗口, "text": 文本}）
    按时序插入 entries 副本，返回新条目列表（不改动入参）。

    - 新块 timing＝语音窗口：start=窗口起点；end=min(窗口终点,
      start+时长)；时长=min(窗口时长, max(字符数/INSERT_CPS_CAP,
      INSERT_MIN_DURATION_S))——CPS 上限换算防挤压（窗口够长时时长
      至少给到阅读上限），窗口比换算时长更短则受限于窗口；
    - 原块原样保留（text/timing 不动），调用方收尾 build_srt 重编号
      输出（本函数同步重编 index 与 build_srt 编号一致）；
    - picks 窗口无法解析的条目跳过（如实丢弃，由调用方计数）。"""
    new_entries = [dict(e) for e in entries]
    prepared: list[tuple[float, float, str]] = []
    for p in picks or []:
        s0, e0 = _timing_span(str(p.get("timing") or ""))
        text = str(p.get("text") or "").strip()
        if s0 < 0 or not text:
            continue
        window_dur = max(0.0, e0 - s0)
        chars = len("".join(text.split()))
        dur_needed = chars / INSERT_CPS_CAP if INSERT_CPS_CAP > 0 else 0.0
        dur = min(window_dur, max(dur_needed, INSERT_MIN_DURATION_S))
        dur = max(dur, 0.001)
        prepared.append((s0, min(e0, s0 + dur), text))
    for s0, e0, text in sorted(prepared, key=lambda x: (x[0], x[1])):
        block = {"index": None,      # 重编号收尾（下循环统一定位）
                 "timing": f"{_fmt_ms(int(round(s0 * 1000)))} --> "
                           f"{_fmt_ms(int(round(e0 * 1000)))}",
                 "text": text}
        # 时序插位：插在第一个起点晚于新块起点的原块之前（同起点原块
        # 优先——插入块语义上是原块之间间隙的补行）
        pos = len(new_entries)
        for i, e in enumerate(new_entries):
            es, _ee = _timing_span(e.get("timing") or "")
            if es > s0:
                pos = i
                break
        new_entries.insert(pos, block)
    # 重编号收尾（与 filters.build_srt 输出编号一致）
    for i, e in enumerate(new_entries, 1):
        e["index"] = i
    return new_entries


def assert_insert_invariants(original_entries: list, new_entries: list,
                             picks: list) -> None:
    """插入通道独立恒等式（C15，不复用 action_retranslate._assert_apply_
    invariants 的条目数不变断言——补行必增行）。失败=程序 bug，抛
    AssertionError 且不得落盘。

    - 新长度＝原长度＋有效 picks 数；
    - 原块按序全等：原 (timing, text) 序列是 new 的子序列（index 重编号
      差异豁免——断言只看 timing/text）；
    - 每个有效 pick：恰有一个新块 text=pick 文本、timing 落在窗口内、
      时长 ≤ INSERT_CPS_CAP 换算上限（且 ≥0）。"""
    valid: list[tuple[str, float, float, str]] = []
    for p in picks or []:
        s0, e0 = _timing_span(str(p.get("timing") or ""))
        text = str(p.get("text") or "").strip()
        if s0 < 0 or not text:
            continue
        valid.append((str(p.get("timing")), s0, e0, text))
    if len(new_entries) != len(original_entries) + len(valid):
        raise AssertionError(
            f"插入恒等式失败：条目数 {len(original_entries)}+{len(valid)}"
            f" != {len(new_entries)}")
    # 原块子序列校验（双指针）
    j = 0
    for n in new_entries:
        if j < len(original_entries):
            o = original_entries[j]
            if (n.get("timing") == o.get("timing")
                    and n.get("text") == o.get("text")):
                j += 1
    if j != len(original_entries):
        raise AssertionError(
            f"插入恒等式失败：原块时序/文本被改动（对上 {j}/"
            f"{len(original_entries)}）")
    # 每个 pick 的新块校验
    for _timing, s0, e0, text in valid:
        hits = [n for n in new_entries if n.get("text") == text]
        if not hits:
            raise AssertionError(f"插入恒等式失败：新块文本缺失: {text!r}")
        ok = False
        for n in hits:
            ns, ne = _timing_span(n.get("timing") or "")
            if ns < 0:
                continue
            chars = len("".join(text.split()))
            cap = max(chars / INSERT_CPS_CAP if INSERT_CPS_CAP > 0 else 0.0,
                      INSERT_MIN_DURATION_S)
            if s0 - 0.002 <= ns and ne <= e0 + 0.002 and (ne - ns) <= cap + 0.002:
                ok = True
                break
        if not ok:
            raise AssertionError(
                f"插入恒等式失败：新块 timing 越窗/超时长上限: {text!r}")
