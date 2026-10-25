"""替2 确定性对话行检测器（D2026-1025-01 批6 b 项）。

对阶段A 输入条目（闸门0+预合并+kana_clean 后）逐条判定上游 ASR
「同 cue 自并」形态（陈述句＋应答词同条 / 单 cue 双句末标点），
命中任一信号即 flagged；随后由 pipeline_v2 仅对 flagged 批做条件
注入＋行数契约守卫（v2 §4-3）。纯函数、零 IO、零外部依赖。

形态判定口径（拍板行③ 替2）：
- 信号①（应答词形态）：文本中最后一个**内部**句末标点之后的尾段，
  剥标点后为纯假名（ぁ-ゖァ-ヺー，含促音/小假名）且核心 ≤4 字。
  形态判定，不要求应答词成员表命中（成员表口径属 a 项，勿混用）。
  整条本身 ≤4 字纯假名的不触（该类已由 a 项豁免独立成行）。
- 信号②（单 cue 双句末标点）：剥除引号/括号后句末标点出现 ≥2 次。
"""

# ---- 常量单一来源（卡面：尾段上限 4、标点集） ----
SENT_END_PUNCTS = "。？！?!"
DIALOGUE_TAIL_MAX = 4      # 信号① 尾段核心字符上限
DIALOGUE_WHOLE_MAX = 4     # 整条纯假名豁免上限（a 项独立成行面）

# 纯假名（ぁ-ゖァ-ヺー；促音/小假名/片假名长音「ー」均含于区间）
_KANA_CHARS = frozenset(
    chr(cp) for cp in range(ord("ぁ"), ord("ゖ") + 1)) | frozenset(
    chr(cp) for cp in range(ord("ァ"), ord("ヺ") + 1)) | frozenset("ー")

# 剥标点口径：句读/引号/括号/省略号/连接符 + ASCII 标点 + 空白
_STRIP_CHARS = frozenset(
    "、，。．,.;:：；！?…‥・〜～―ーー−-—「」『』（）()【】[]{}〈〉《》"
    "\"'‘’“”`*+=/<>|\\_~^$%@#&")

# 信号② 剥除口径：仅引号/括号（句读标点保留计数）
_QUOTE_CHARS = "「」『』（）()【】[]{}〈〉《》\"'‘’“”"


def _strip_punct(text: str) -> str:
    """剥除标点与空白，返回剩余字符序列。"""
    return "".join(ch for ch in text
                   if ch not in _STRIP_CHARS and not ch.isspace())


def _is_pure_kana(text: str) -> bool:
    """非空且全部字符为纯假名。"""
    return bool(text) and all(ch in _KANA_CHARS for ch in text)


def _is_dialogue_row(text: str) -> bool:
    """单条文本判定：命中信号① 或信号② 即 True。"""
    if not text:
        return False
    whole = _strip_punct(text)
    if len(whole) <= DIALOGUE_WHOLE_MAX and _is_pure_kana(whole):
        return False    # 整条 ≤4 字纯假名：a 项豁免面，不触
    # 信号②：剥除引号/括号后句末标点 ≥2
    stripped = text
    for q in _QUOTE_CHARS:
        stripped = stripped.replace(q, "")
    if sum(stripped.count(p) for p in SENT_END_PUNCTS) >= 2:
        return True
    # 信号①：最后一个句末标点之后的尾段（行尾标点 → 尾段空 → 不触）
    pos = -1
    for p in SENT_END_PUNCTS:
        pos = max(pos, text.rfind(p))
    if pos == -1:
        return False
    core = _strip_punct(text[pos + 1:])
    if not core or len(core) > DIALOGUE_TAIL_MAX:
        return False
    return _is_pure_kana(core)


def detect_dialogue_rows(entries: list) -> set:
    """对条目列表逐条判定，返回 flagged 的 index 集合（确定性）。"""
    return {e["index"] for e in entries
            if _is_dialogue_row(e.get("text") or "")}


# ---- 注入文案（两句顺序固定：行数契约句 → 标注句） ----
LINE_CONTRACT_SENT = ("输出行数必须与输入条数一一对应；禁止新增换行、"
                      "禁止合并或拆分行、禁止添加说话人前缀。")
DIALOGUE_NOTE_TMPL = ("第 {lines} 行可能包含两人对话（句末后接应答词），"
                      "该行内应答词部分不得译作同一人的续句，"
                      "应按句读分开表达（如「……。嗯。」）。")


def build_injection_block(entries: list, flagged: set) -> str | None:
    """生成批级条件注入文案。

    entries 为本批条目；flagged 为全量 flagged index 集。仅当本批
    命中 flagged 时返回文案（行号取条目 index，与协议 #N 编号一致，
    阶段A 连续批下即批内相对序号），升序确定；否则返回 None。
    """
    rows = sorted(e["index"] for e in entries if e["index"] in flagged)
    if not rows:
        return None
    lines = "、".join(str(r) for r in rows)
    return f"{LINE_CONTRACT_SENT}\n{DIALOGUE_NOTE_TMPL.format(lines=lines)}"
