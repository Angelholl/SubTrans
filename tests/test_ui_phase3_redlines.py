"""阶段3（2.2.1）三面红线静态钉（D2026-1001-02 批清单二级评议闭环件）。

R1 DOM 恒定 / R2 节奏禁区 / R3 契约恒空的机器化落点：
- 钉① 批1：阶段A/B/第三卡区间无残留内联宽度（C3 断言域=三卡，域外内联合法）
- 钉② 批2：两张词库表挂 .gl-table
- 钉③ 批2：glRender/glLearnedLoad 行模板无 style= 字面量
- 钉④ R2：:root 节奏禁区变量与文档级字号行高逐字冻结
- 钉⑤ R1/R3（HRO-1 采纳件）：id 全集 + data-i18n 键全集快照冻结

快照体与解冻史外置（3.1 阶段 1 地基批 卡2，D2026-1012-01）：id 全集（223）
与 data-i18n 键全集（187）迁入 tests/ui_contract_snapshot.json（数组排序
序列化保证 diff 稳定），2.6.x 起全部解冻/变更记录（190→191→200→206→210→
213→215→214→213→217→218→223，逐笔含决策号）全量迁入该文件 _meta.history，
本文件不再承载解冻史；未来合法契约变更必须跑再生工具
tools/ui_contract_snapshot.py --update 重生成快照 + 人工审 diff + 二级评议
（R1/R3 契约恒空口径与有意摩擦不降级，防静默漂移）。
"""
import json
import re
from pathlib import Path

import js_sources

ROOT = Path(__file__).resolve().parent.parent
_ASSETS = ROOT / "subtransjav" / "webview_gui" / "assets"
HTML = (_ASSETS / "index.html").read_text(encoding="utf-8")
JS = js_sources.read_all()
CSS = (_ASSETS / "style.css").read_text(encoding="utf-8")


def _slice_between(text: str, start: str, end: str) -> str:
    i = text.index(start)
    j = text.index(end, i)
    return text[i:j]


def test_batch1_stage_cards_no_inline_width():
    """钉①（C3 域）：阶段A/阶段B/兜底档位三卡无内联宽度。

    2.6.3 批C D2026-1003-01 P4 IA 重排随改（既有断言必要修订）：接口地址
    卡外壳删除、两行地址迁入分段段内（其 label 合法携带内联
    min-width:var(--w-endpoint-label)，原「阶段A→接口地址」切片锚失义），
    故改按卡注释逐卡切片；断言本体（两禁内联形态）不变。
    """
    for start, end in (
        ("<!-- 阶段A 完整行 -->", "<!-- 阶段A 地址"),
        ("<!-- 阶段B 完整行 -->", "<!-- 阶段B 地址"),
        ("<!-- 兜底档位", "<!-- 兜底与并发"),
    ):
        block = _slice_between(HTML, start, end)
        assert 'style="min-width' not in block, \
            f"{start} 起卡内残留内联 min-width（批1 收编遗漏）"
        assert 'style="width' not in block, \
            f"{start} 起卡内残留内联 width（批1 收编遗漏）"


def test_batch2_glossary_tables_carry_gl_table():
    """钉②：两词库表挂 gl-table（表级宽度/列宽规则依托该类生效）。"""
    assert '<table id="refineGlossTable" class="gl-table">' in HTML
    assert '<table id="glLearnedTable" class="gl-collapsible-content gl-table">' in HTML


def test_batch2_gl_row_templates_no_inline_style():
    """钉③：glRender/glLearnedLoad 函数体无 style= 字面量。"""
    render = _slice_between(JS, "function glRender(", "async function glLoad(")
    learned = _slice_between(JS, "async function glLearnedLoad(", "function glAdd(")
    assert "style=" not in render, "glRender 行模板残留内联样式"
    assert "style=" not in learned, "glLearnedLoad 行模板残留内联样式"


def test_r2_rhythm_tokens_frozen():
    """钉④：节奏禁区变量值逐字冻结（动它=候选池禁区项，须显式复议）。"""
    assert "--space-1: 4px;" in CSS
    assert "--font: 14px; --font-sm: 13px; --font-xs: 12px;" in CSS
    assert re.search(r"html\s*\{[^}]*font-size:\s*var\(--font\);", CSS), \
        "html 文档级字号被改动"
    assert re.search(r"body\s*\{[^}]*line-height:\s*1\.55;", CSS), \
        "body 文档级行高被改动"


# 快照体外置（3.1 地基批 卡2，D2026-1012-01）：tests/ui_contract_snapshot.json
# 承载 id 全集/data-i18n 键全集（数组排序序列化，diff 逐条可读、增删一目了然）
# 与 _meta.history 解冻史；再生工具 tools/ui_contract_snapshot.py（--update 才写盘，
# 无漂移打印 "no drift"）。集合零增减，仅形态迁移。
_SNAPSHOT_PATH = Path(__file__).resolve().parent / "ui_contract_snapshot.json"
_SNAPSHOT = json.loads(_SNAPSHOT_PATH.read_text(encoding="utf-8"))

FROZEN_IDS = frozenset(_SNAPSHOT["ids"])
FROZEN_I18N_KEYS = frozenset(_SNAPSHOT["i18n_keys"])


def _current_ids():
    return frozenset(re.findall(r'(?<![\w-])id="([^"]+)"', HTML))


def _current_i18n_keys():
    return frozenset(re.findall(r'data-i18n(?:-title|-placeholder)?="([^"]+)"', HTML))


def test_r3_id_fullset_frozen():
    """钉⑤a（HRO-1）：id 全集快照冻结，新增/删除/改名一律显式改快照。

    快照显式解冻记录：2.7.4 件C（D2026-1007-02）新增
    batchFixEffectiveLine（修复生效配置明示行，决策明示批准）。"""
    cur = _current_ids()
    assert cur == FROZEN_IDS, (
        f"id 全集漂移：新增={sorted(cur - FROZEN_IDS)} 删除={sorted(FROZEN_IDS - cur)}"
        "（R1/R3 契约恒空；合法变更须跑 tools/ui_contract_snapshot.py --update 重生成快照"
        " tests/ui_contract_snapshot.json，并人工审 diff + 二级评议）"
    )


def test_r3_i18n_key_fullset_frozen():
    """钉⑤b（HRO-1）：data-i18n 键全集快照冻结（含 title/placeholder 变体）。"""
    cur = _current_i18n_keys()
    assert cur == FROZEN_I18N_KEYS, (
        f"data-i18n 键全集漂移：新增={sorted(cur - FROZEN_I18N_KEYS)} 删除={sorted(FROZEN_I18N_KEYS - cur)}"
        "（R3 契约恒空；合法变更须跑 tools/ui_contract_snapshot.py --update 重生成快照"
        " tests/ui_contract_snapshot.json，并人工审 diff + 二级评议）"
    )


# ---------------------------------------------------------------------------
# 2.6.1 批1（D2026-1002-07）UI 基建追加钉
# ---------------------------------------------------------------------------

def test_r2b_rhythm_tokens_extended():
    """批 1 token 扩充钉：间距/控件高度/过渡时长 token 化只增不改。

    钉④冻结项不在此重复断言（由 test_r2_rhythm_tokens_frozen 守）；
    本钉守新增 token 的定义存在性（只增不改的"增"方向机器闸）。
    """
    assert ("--space-2: 8px; --space-3: 12px; --space-4: 16px; "
            "--space-5: 24px; --space-6: 32px;") in CSS, \
        "间距 token 扩充（--space-2..6）缺失或值被改"
    assert "--h-ctl: 36px; --h-ctl-sm: 30px;" in CSS, \
        "控件高度 token（--h-ctl/--h-ctl-sm）缺失或值被改"
    assert "--dur-fast:" in CSS and "--dur:" in CSS, \
        "过渡时长 token（--dur-fast/--dur）缺失"


def test_nav_grouping_pinned():
    """导航三分结构钉（批 1 立钉、批 2a 随批更新）：组标题与按钮顺序显式冻结。

    工作区组=字幕翻译/校对（批 2a D2026-1002-09 占位转正为
    .side-tab-btn#tabBtnReview）/质量与建议/评测报告（3.1.1 件B
    D2026-1030-02 B3，与校对/结果页同级的结果查看类页签）；
    设置组=API 与模型选择/ASR 与词典（2.6.3 批C D2026-1003-01 P4 插入）/
    词库与模板/高级参数。
    """
    m = re.search(r'<nav class="rail-nav".*?</nav>', HTML, re.S)
    assert m, "未找到 rail-nav 导航块"
    nav = m.group(0)
    seq = re.findall(
        r'<div class="nav-section" data-i18n="([^"]+)">|data-tab="([^"]+)"', nav)
    groups: dict = {}
    current = None
    for sec, tab in seq:
        if sec:
            current = sec
            groups[current] = []
        elif current:
            groups[current].append(tab)
    assert list(groups.keys()) == ["nav_group_workspace", "nav_group_quality"], \
        f"导航分组标题顺序漂移：{list(groups.keys())}"
    assert groups["nav_group_workspace"] == \
        ["tab-translate", "tab-review", "tab-guide", "tab-eval-reports"], \
        f"工作区组 data-tab 顺序漂移：{groups['nav_group_workspace']}"
    assert groups["nav_group_quality"] == \
        ["tab-engine", "tab-asrdict", "tab-glossary", "tab-advanced"], \
        f"设置组 data-tab 顺序漂移：{groups['nav_group_quality']}"
    # 批 2a（D2026-1002-09）：占位项已转正——nav-item-placeholder 必须消失，
    # 校对项为 .side-tab-btn#tabBtnReview[data-tab=tab-review]（预算表程序落 id）
    assert "nav-item-placeholder" not in HTML, \
        "批 1 校对占位项应在批 2a 转正后移除"
    rb = re.search(r'<button[^>]*id="tabBtnReview"[^>]*>', HTML)
    assert rb, "缺校对 TAB 按钮 tabBtnReview"
    assert 'data-tab="tab-review"' in rb.group(0) \
        and "side-tab-btn" in rb.group(0), \
        "校对 TAB 按钮必须挂 data-tab=tab-review 且为 .side-tab-btn"
    assert "tabReview: '校对'" in JS, "MSG 缺 tabReview 静态键"


# ---------------------------------------------------------------------------
# d1023-polish 批3（D2026-1023-03）：字幕清洗复选框输出格式区块落位钉
# ---------------------------------------------------------------------------

def test_polish_checkbox_in_output_format_block_existing_class():
    """清洗复选框落在「输出格式」区块（outputFmtVtt 之后、path-row 之前），
    行容器沿用既有 output-source-toggle 类（019b205 死类教训），默认不勾
    （=polish_enabled 默认 False 的 GUI 镜像）。"""
    block = _slice_between(
        HTML, '<div class="field-label" data-i18n="output_format_header">',
        '<div class="path-row">')
    m = re.search(r'<input[^>]*id="polishEnabled"[^>]*>', block)
    assert m, "输出格式区块缺 polishEnabled 复选框"
    assert "checked" not in m.group(0), "polishEnabled 默认必须不勾"
    row_start = block.rindex("<div", 0, m.start())
    assert 'class="output-source-toggle"' in block[row_start:m.start()], \
        "清洗复选框行须沿用既有 output-source-toggle 类（禁止死类）"
    assert 'data-i18n="polish_enabled_label"' in block, \
        "清洗复选框缺 data-i18n 键 polish_enabled_label"
