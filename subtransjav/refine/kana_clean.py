"""
源文假名清洗（纯函数层）
====================
职责：ja→zh 源文侧纯假名条目的确定性清洗——分类（实义/喘息/短句/保留）、
纯假名短句/喘息合并（并入前条 / 前向挂接后条，链式可续并）、
孤立喘息删除（opt-in，默认关）。

依据：D2026-1025-01 批2 离线 A/B 已验证放行（7 部实测语料误删 0、
纯假名短句约减半）；分类与间隙语义与批2 模拟逐条一致，本模块为
相关常量的单一来源。

无 IO：clean_entries 为纯函数，stats 由调用方（pipeline_v2）并入
merge_stats 流供质量报告消费。
"""

import re

from .v2_premerge import _timing_span

# ---------------------------------------------------------------------------
# 分类常量与正则（规格单一来源）
# ---------------------------------------------------------------------------

CLASS_CONTENT = "content"      # 实义类（含汉字或拉丁字母/数字，永不触）
CLASS_MOAN = "moan"            # 喘息类
CLASS_SHORT = "short"          # 纯假名短句类
CLASS_KEEP = "keep"            # 保留（长纯假名 / 含其他符号）

#: 剥标点正则（与批2 模拟一致，常量单一来源）
_STRIP_PUNCT_RE = re.compile(r"[、。！？!?\s♪・「」『』()（）~～…ー]")
#: 喘息核心整词：剥标点后的核心只由这些假名组成（含空核心）
_MOAN_CORE_RE = re.compile(r"^[あぁアンんンっッヴ]+$")
#: 纯假名核心判定（短句类前置条件）
_KANA_CORE_RE = re.compile(r"^[ぁ-ゖァ-ヺー]+$")
#: 汉字（实义类判定；与 quality_report._KANJI_RE 同字符集口径）
_KANJI_RE = re.compile(r"[一-鿿々]")
#: 拉丁字母/数字（实义类判定）
_LATIN_ALNUM_RE = re.compile(r"[A-Za-z0-9]")

#: 纯假名短句核心长度上限
_SHORT_CORE_MAX = 6
#: 合并间隙上限（毫秒）：与前/后条间隙 ≤ 此值即并入/挂接
MERGE_GAP_MS = 800
#: 孤立喘息判定间隙下限（毫秒）：与前/后间隙均 > 此值才算孤立
ISOLATED_GAP_MS = 1200


def classify_kana_entry(text: str) -> str:
    """对源文条目文本 t 分类（D2026-1025-01 批2 模拟口径）。

    - 含汉字或含 [A-Za-z0-9] → 实义类（永不触）；
    - 剥标点后核心为空，或核心整词匹配 ^[あぁアンんンっッヴ]+$ → 喘息类；
    - 其余纯假名且核心长 ≤ 6 → 短句类；
    - 其余 → 保留。
    """
    t = text or ""
    if _KANJI_RE.search(t) or _LATIN_ALNUM_RE.search(t):
        return CLASS_CONTENT
    core = _STRIP_PUNCT_RE.sub("", t)
    if not core or _MOAN_CORE_RE.fullmatch(core):
        return CLASS_MOAN
    if _KANA_CORE_RE.fullmatch(core) and len(core) <= _SHORT_CORE_MAX:
        return CLASS_SHORT
    return CLASS_KEEP


# ---------------------------------------------------------------------------
# 清洗主入口
# ---------------------------------------------------------------------------

def clean_entries(entries: list, merge_enabled: bool = True,
                  delete_enabled: bool = False) -> tuple:
    """源文假名清洗主入口（纯函数，无 IO）。

    entries: parse_srt 产物条目列表（dict: index/timing/text），时间轴升序。
    merge_enabled: 短句类/喘息类并入相邻条开关（默认开）。
    delete_enabled: 孤立喘息删除开关（默认关）。

    合并语义（批2 模拟同款）：
    - 短句类/喘息类条目与前条间隙 ≤ MERGE_GAP_MS → 并入前条（文本按
      时间序拼接，span 取并集，链式可续并）；
    - 否则与后条间隙 ≤ MERGE_GAP_MS → 前向缓冲挂到后条；
    - 两向均超限 → 短句类保留；喘息类若与前/后间隙均 > ISOLATED_GAP_MS
      （孤立）且 delete_enabled → 删除，否则保留。

    返回 (entries, stats)；stats 键：
      kana_merged — 被并入相邻条的条数；
      kana_moan_deleted — 删除的孤立喘息条数；
      kana_moan_deleted_timings — 删除台账 [{timing, text}]（报告消费）；
      kana_kept — 判为短句/喘息但原样保留的条数。
    """
    stats = {"kana_merged": 0, "kana_moan_deleted": 0,
             "kana_moan_deleted_timings": [], "kana_kept": 0}
    if not entries:
        return entries, stats
    n = len(entries)
    classes = [classify_kana_entry(e.get("text") or "") for e in entries]
    spans = [_timing_span(e.get("timing") or "") for e in entries]
    inf = float("inf")

    def side_gap(i: int, j: int):
        """条目 i 与后继 j（=i+1）的间隙毫秒。i/j 越界（无邻居）→ inf；
        任一时间轴非法 → None（决策侧保守：不合并不删除）。"""
        if i < 0 or j >= n:
            return inf
        if spans[i][0] < 0 or spans[j][0] < 0:
            return None
        return round((spans[j][0] - spans[i][1]) * 1000)

    # ---- 决策：只依赖原始序列的相邻间隙，与合并执行解耦（可同时成立、
    #      不因删除级联改判——删除条前后间隙必 >1200，不含任何 ≤800 侧）----
    actions: list = []
    for i in range(n):
        c = classes[i]
        if c not in (CLASS_SHORT, CLASS_MOAN):
            actions.append(None)            # 实义/保留条目不参与决策
            continue
        g_prev = side_gap(i - 1, i)
        g_next = side_gap(i, i + 1)
        if merge_enabled:
            if g_prev is not None and g_prev <= MERGE_GAP_MS:
                actions.append("merge_prev")
                continue
            if g_next is not None and g_next <= MERGE_GAP_MS:
                actions.append("carry_next")
                continue
        if (c == CLASS_MOAN and delete_enabled
                and g_prev is not None and g_next is not None
                and g_prev > ISOLATED_GAP_MS and g_next > ISOLATED_GAP_MS):
            actions.append("delete")
        else:
            actions.append("keep")

    # ---- 执行：左→右单趟，carry 为前向缓冲条目 ----
    out: list = []
    carry = None
    for i in range(n):
        e = entries[i]
        act = actions[i]
        if carry is not None:
            if act is None:
                # 实义/保留后条：缓冲条目挂到后条（文本时间序拼接、span 并集）
                out.append(_merge_pair(carry, e))
                stats["kana_merged"] += 1
                carry = None
                continue
            if act == "merge_prev":
                # 后条决策并入前条（=缓冲条目）：缓冲条目吸收后条后落定，
                # 链式续并交由后续 merge_prev 并入该落定条目
                out.append(_merge_pair(carry, e))
                stats["kana_merged"] += 1
                carry = None
                continue
            # delete/keep/carry_next 与缓冲语义互斥（间隙论证见上），
            # 防御性落定：缓冲条目原样保留
            out.append(carry)
            stats["kana_kept"] += 1
            carry = None
        if act is None:
            out.append(dict(e))
        elif act == "merge_prev":
            if not out:                     # 决策阶段保证 i>0；防御
                out.append(dict(e))
                stats["kana_kept"] += 1
            else:
                out[-1] = _merge_pair(out[-1], e)
                stats["kana_merged"] += 1
        elif act == "carry_next":
            carry = dict(e)
        elif act == "delete":
            stats["kana_moan_deleted"] += 1
            stats["kana_moan_deleted_timings"].append(
                {"timing": e.get("timing") or "",
                 "text": e.get("text") or ""})
        else:                               # keep
            out.append(dict(e))
            stats["kana_kept"] += 1
    if carry is not None:                   # 末尾缓冲条目落定保留
        out.append(carry)
        stats["kana_kept"] += 1
    return out, stats


def _merge_pair(a: dict, b: dict) -> dict:
    """合并相邻两条目（a 在前）：文本按时间序拼接，span 取并集
    （a 起 ~ b 止）。条目身份沿用 a（与 premerge 同口径：保留首条
    index 及其余字段）；时间轴格式异常时保持 a 侧原值（防御）。"""
    parts_a = (a.get("timing") or "").split("-->")
    parts_b = (b.get("timing") or "").split("-->")
    m = dict(a)
    m["text"] = (a.get("text") or "").strip() + (b.get("text") or "").strip()
    if len(parts_a) >= 2 and len(parts_b) >= 2:
        m["timing"] = parts_a[0].strip() + " --> " + parts_b[1].strip()
    return m
