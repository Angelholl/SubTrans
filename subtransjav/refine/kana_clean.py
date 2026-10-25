"""
源文假名清洗（纯函数层）
====================
职责：ja→zh 源文侧纯假名条目的确定性清洗——分类（实义/喘息/短句/保留）、
应答词豁免（封闭表，永不并/永不删）、纯假名短句/喘息合并（并入前条 /
前向挂接后条，链式可续并）、孤立喘息删除（opt-in，默认关）。

依据：D2026-1025-01 批2 离线 A/B 已验证放行（7 部实测语料误删 0、
纯假名短句约减半）；分类与间隙语义与批2 模拟逐条一致，本模块为
相关常量的单一来源。批6 a 项（D2026-1025-01 规格 v3 案甲）新增：
应答词豁免封闭表（归一 core 命中，决策段入口先判豁免）、合并间隙
按类分档（短句 200ms / 喘息 800ms）、三向全封＋显式守卫。

**三向全封与链式语义（规格 v3 §5，显式封闭）**：豁免条三向全封——
①自身决策恒 keep（封 merge_prev/carry_next）；②执行段 merge_prev
落点 out[-1] 若为豁免条→宿主守卫，后条独立保留不吸收；③carry 缓冲
遇豁免条→前端守卫，缓冲原样落定、豁免条独立成行。守卫全开下豁免行
永不吸收任何条目，故「豁免行永不入合并产物」不变式链式封闭。

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
#: 短句类合并间隙上限（毫秒）：与前/后条间隙 ≤ 此值即并入/挂接
#: （批6 a 项规格 v3 §6：800→200 收紧；原 MERGE_GAP_MS=800 拆档后删除，
#:  仓内核实无其他消费点）
FRAGMENT_GAP_MS = 200
#: 喘息类合并间隙上限（毫秒）：维持 800 不变（规格 v3 §6）
MOAN_GAP_MS = 800
#: 孤立喘息判定间隙下限（毫秒）：与前/后间隙均 > 此值才算孤立
ISOLATED_GAP_MS = 1200

#: 促音/小假名折叠表（规格 v3 §2：逐字映射，全量折叠不区分位置）
_SMALL_FOLD = {"ぁ": "あ", "ぃ": "い", "ぅ": "う", "ぇ": "え", "ぉ": "お",
               "っ": "つ", "ゃ": "や", "ゅ": "ゆ", "ょ": "よ", "ゎ": "わ",
               "ゐ": "い", "ゑ": "え"}
#: 应答词豁免成员表（封闭表，规格 v3 §1；表内写**归一形**：えっ→えつ、
#: わかった→わかつた、マジで→まじで；ねー 剥长音后=ね 同 core 不另列。
#: A2 同 core 相邻对合并不落码——0-⑥ 实测 12<20，门已关）
_MEMBER_TABLE = frozenset({
    "はい", "うん", "そう", "そうね", "そうか", "ね", "えつ", "ええ", "ん",
    "まじで", "なるほど", "わかつた", "うそ",
})
#: 豁免标记内部字段（输出前清除，不泄漏进产物 dict）
_EXEMPT_FIELD = "_kana_exempt"


def _exempt_core(text: str) -> str:
    """归一 core（规格 v3 §2）：剥标点（复用 _STRIP_PUNCT_RE，长音 ー 在
    剥离集内）→片假名（ァ-ヺ 偏移 −0x60）→小假名折叠。"""
    core = _STRIP_PUNCT_RE.sub("", text or "")
    out = []
    for ch in core:
        if "ァ" <= ch <= "ヺ":
            ch = chr(ord(ch) - 0x60)
        out.append(_SMALL_FOLD.get(ch, ch))
    return "".join(out)


def is_exempt_entry(text: str) -> bool:
    """豁免判定（规格 v3 §1/§3）：归一 core 与成员表精确整词命中
    （非子串）。命中即豁免条：永不参与合并，也永不参与删除。"""
    return _exempt_core(text) in _MEMBER_TABLE


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

    豁免语义（D2026-1025-01 规格 v3 §4）：成员表命中条（应答词类）在
    决策段入口**先判豁免**，命中即落 keep 并退出整个 action 决策——显式
    先于短句/喘息两档合并判定与孤立喘息删除判定（ん 现归 CLASS_MOAN，
    豁免必须抢在删除前，防 opt-in 删除丢数据）。行为与分类缺省 keep
    一致（原样保留独立行），但语义来源是显式白名单。

    合并语义（批6 a 项规格 v3 §6 分档）：
    - 短句类与前/后条间隙 ≤ FRAGMENT_GAP_MS（200ms）→ 并入前条（文本按
      时间序拼接，span 取并集，链式可续并）/ 前向缓冲挂到后条；
    - 喘息类同判定，档位 ≤ MOAN_GAP_MS（800ms）；
    - 两向均超限 → 短句类保留；喘息类若与前/后间隙均 > ISOLATED_GAP_MS
      （孤立）且 delete_enabled → 删除，否则保留。
    - 三向全封＋显式守卫（§5）：豁免行永不吸收任何条目（docstring 头部
      链式语义声明），merge_prev 落点/缓冲挂接遇豁免条均被守卫挡下。

    返回 (entries, stats)；stats 键：
      kana_merged — 被并入相邻条的条数；
      kana_moan_deleted — 删除的孤立喘息条数；
      kana_moan_deleted_timings — 删除台账 [{timing, text}]（报告消费）；
      kana_kept — 判为短句/喘息但原样保留的条数（含豁免条，对齐模拟器
        口径：豁免条同时计 kept）；
      kana_exempted — 豁免条计数（规格 v3 §7 新键）；
      kana_exempted_ledger — 豁免台账 list，元素五键：timing / text /
        core（归一命中值）/ gap（触发时相邻间隙毫秒，双侧取能取到的一侧
        （prev 优先），无邻居/时间轴非法记 null）/ neighbor_text（原邻条
        文本前 40 字，无邻居记 null）。
    """
    merged_n = deleted_n = kept_n = exempt_n = 0
    deleted_log: list = []
    exempt_log: list = []
    if not entries:
        return entries, {"kana_merged": 0, "kana_moan_deleted": 0,
                         "kana_moan_deleted_timings": [], "kana_kept": 0,
                         "kana_exempted": 0, "kana_exempted_ledger": []}
    n = len(entries)
    classes = [classify_kana_entry(e.get("text") or "") for e in entries]
    exempt_flags = [is_exempt_entry(e.get("text") or "") for e in entries]
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
        if exempt_flags[i]:
            # 豁免条（规格 v3 §4）：决策段入口先判豁免即 keep——先于
            # 短句/喘息两档合并判定与孤立喘息删除判定
            g_prev = side_gap(i - 1, i)
            g_next = side_gap(i, i + 1)
            gap = None
            neighbor = None
            if g_prev is not None and g_prev != inf:        # prev 优先
                gap, neighbor = g_prev, entries[i - 1]
            elif g_next is not None and g_next != inf:
                gap, neighbor = g_next, entries[i + 1]
            exempt_log.append({
                "timing": entries[i].get("timing") or "",
                "text": entries[i].get("text") or "",
                "core": _exempt_core(entries[i].get("text") or ""),
                "gap": gap,
                "neighbor_text": ((neighbor.get("text") or "")[:40]
                                  if neighbor is not None else None),
            })
            exempt_n += 1
            actions.append("keep")
            continue
        c = classes[i]
        if c not in (CLASS_SHORT, CLASS_MOAN):
            actions.append(None)            # 实义/保留条目不参与决策
            continue
        g_prev = side_gap(i - 1, i)
        g_next = side_gap(i, i + 1)
        gap_ms = MOAN_GAP_MS if c == CLASS_MOAN else FRAGMENT_GAP_MS
        if merge_enabled:
            if g_prev is not None and g_prev <= gap_ms:
                actions.append("merge_prev")
                continue
            if g_next is not None and g_next <= gap_ms:
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
            if exempt_flags[i]:
                # 前端显式守卫（规格 v3 §5-4）：缓冲条目遇豁免条不挂接
                # （原防御分支仅巧合保护，间隙互斥论证随豁免失效）——
                # 缓冲条目原样落定保留，豁免条独立成行
                out.append(carry)
                kept_n += 1
                carry = None
            elif act is None:
                # 实义/保留后条：缓冲条目挂到后条（文本时间序拼接、span 并集）
                out.append(_merge_pair(carry, e))
                merged_n += 1
                carry = None
                continue
            elif act == "merge_prev":
                # 后条决策并入前条（=缓冲条目）：缓冲条目吸收后条后落定，
                # 链式续并交由后续 merge_prev 并入该落定条目
                out.append(_merge_pair(carry, e))
                merged_n += 1
                carry = None
                continue
            else:
                # delete/keep/carry_next 与缓冲语义互斥（间隙论证见上），
                # 防御性落定：缓冲条目原样保留
                out.append(carry)
                kept_n += 1
                carry = None
        if act is None:
            out.append(dict(e))
        elif act == "merge_prev":
            if not out:                     # 决策阶段保证 i>0；防御
                out.append(dict(e))
                kept_n += 1
            elif out[-1].get(_EXEMPT_FIELD):
                # 宿主守卫（规格 v3 §5-3）：merge_prev 落点 out[-1] 为豁免条
                # 时不吸收，后条独立保留（计 kept），不并入
                out.append(dict(e))
                kept_n += 1
            else:
                out[-1] = _merge_pair(out[-1], e)
                merged_n += 1
        elif act == "carry_next":
            carry = dict(e)
        elif act == "delete":
            deleted_n += 1
            deleted_log.append({"timing": e.get("timing") or "",
                                "text": e.get("text") or ""})
        else:                               # keep
            m = dict(e)
            if exempt_flags[i]:
                m[_EXEMPT_FIELD] = True     # 内部标记：宿主守卫判定用
            out.append(m)
            kept_n += 1
    if carry is not None:                   # 末尾缓冲条目落定保留
        out.append(carry)
        kept_n += 1
    for m in out:                           # 豁免标记输出前清除，不泄漏产物
        m.pop(_EXEMPT_FIELD, None)
    return out, {"kana_merged": merged_n, "kana_moan_deleted": deleted_n,
                 "kana_moan_deleted_timings": deleted_log, "kana_kept": kept_n,
                 "kana_exempted": exempt_n, "kana_exempted_ledger": exempt_log}


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
