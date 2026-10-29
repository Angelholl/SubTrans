// ============================================================
// 评测报告页（3.1.1 件B，D2026-1030-02 B3）：只读消费 eval_baseline
// 报告 JSON（桥端点 eval_reports_list / eval_reports_get 白名单），
// 页面零二次计算；Wilson 区间只展示（区间计算在 harness B1 层）；
// CPS 分位数与 omission_proxy 秒比不给区间，区间位显「—」；
// 窗口检测退化显式 null 态（诚实退化口径，不显示假数）。
// 页内文案全走 MSG（静态键 cap 硬约束，沿 review 页模式：页内零 data-i18n）；
// DOM 一律 createElement+textContent（报告内容不做 innerHTML 拼接）。
// ============================================================
(function () {
    'use strict';

    const state = { current: null };

    function el(id) { return document.getElementById(id); }

    function div(className, text) {
        const d = document.createElement('div');
        if (className) d.className = className;
        if (text != null) d.textContent = text;
        return d;
    }

    function fmtPct(v) {
        return v == null ? MSG.evalNoCI : (v * 100).toFixed(2) + '%';
    }

    function fmtCI(w) {
        if (!w) return MSG.evalNoCI;
        return '[' + (w.lo * 100).toFixed(2) + '%, ' + (w.hi * 100).toFixed(2) + '%]';
    }

    function renderEmpty(res) {
        const host = el('evalReportsBody');
        if (!host) return;
        host.textContent = '';
        const hint = div('gl-muted', res && res.empty_reason
            ? MSG.evalEmptyDir : MSG.evalEmptyHint);
        host.appendChild(hint);
        if (res && res.dir) {
            host.appendChild(div('gl-muted', MSG.evalDataRoot + res.dir));
        }
    }

    function renderList(res) {
        const sel = el('evalReportsSelect');
        if (!sel) return;
        sel.textContent = '';
        for (const r of (res.reports || [])) {
            const opt = document.createElement('option');
            opt.value = r.name;
            opt.textContent = r.name;
            sel.appendChild(opt);
        }
    }

    function engineCard(engineId, r) {
        const card = div('eval-engine-card');
        const head = div('eval-engine-head', engineId);
        card.appendChild(head);
        card.appendChild(div(null, MSG.evalLinesLabel + ': ' + (r.lines ?? '—')));
        const hp = r.hallucination_proxy;
        if (hp == null) {
            card.appendChild(div('gl-muted', MSG.evalHallucination + ': null'));
        } else {
            card.appendChild(div(null, MSG.evalHallucination + ': '
                + fmtPct(hp.ratio) + ' ' + fmtCI(hp.wilson)
                + '（' + (hp.suspect ?? '—') + '/' + (hp.lines ?? '—') + '）'));
        }
        const om = r.omission_proxy;
        if (om == null) {
            card.appendChild(div('gl-muted', MSG.evalOmission + ': null'));
        } else {
            // 秒比非二项，不给区间（区间位显「—」）
            card.appendChild(div(null, MSG.evalOmission + ': '
                + fmtPct(om.ratio) + ' ' + MSG.evalNoCI
                + '（' + (om.uncovered_s ?? '—') + 's/' + (om.speech_s ?? '—') + 's）'));
        }
        const cps = r.cps || {};
        card.appendChild(div(null, MSG.evalCpsLabel + ': '
            + (cps.cps_p50 ?? '—') + ' / ' + (cps.cps_p90 ?? '—') + ' / '
            + (cps.cps_max ?? '—') + '；' + (cps.avg_dur_s ?? '—') + 's'));
        return card;
    }

    function pairsTable(pairs) {
        const wrap = div(null);
        const keys = Object.keys(pairs || {});
        if (keys.length === 0) {
            wrap.appendChild(div('gl-muted', MSG.evalNoPairs));
            return wrap;
        }
        const table = document.createElement('table');
        table.className = 'eval-pairs-table';
        const thead = document.createElement('thead');
        const hr = document.createElement('tr');
        for (const t of [MSG.evalPairsHead, 'matched', 'rate_a', 'rate_b']) {
            const th = document.createElement('th');
            th.textContent = t;
            hr.appendChild(th);
        }
        thead.appendChild(hr);
        table.appendChild(thead);
        const tbody = document.createElement('tbody');
        for (const k of keys) {
            const p = pairs[k] || {};
            const tr = document.createElement('tr');
            for (const v of [
                k,
                String(p.matched ?? '—'),
                (p.rate_a == null ? '—' : fmtPct(p.rate_a)) + ' ' + fmtCI(p.rate_a_wilson),
                (p.rate_b == null ? '—' : fmtPct(p.rate_b)) + ' ' + fmtCI(p.rate_b_wilson),
            ]) {
                const td = document.createElement('td');
                td.textContent = v;
                tr.appendChild(td);
            }
            tbody.appendChild(tr);
        }
        table.appendChild(tbody);
        wrap.appendChild(table);
        return wrap;
    }

    function renderReport(report) {
        const host = el('evalReportsBody');
        if (!host) return;
        host.textContent = '';
        const head = div('eval-report-head');
        head.appendChild(div(null, MSG.evalMediaLabel + ': '
            + (report.media || '—')));
        head.appendChild(div(null, MSG.evalGenLabel + ': '
            + (report.generated_at || '—') + '（'
            + (report.schema || '—') + '）'));
        head.appendChild(div(null, MSG.evalEngineCountLabel + ': '
            + Object.keys(report.engines || {}).length));
        host.appendChild(head);
        if (report.windows_error) {
            // 诚实退化显式态：不显示假数
            host.appendChild(div('eval-windows-degraded',
                MSG.evalWindowsDegraded + '（' + report.windows_error + '）'));
        }
        for (const [engineId, r] of Object.entries(report.engines || {})) {
            host.appendChild(engineCard(engineId, r || {}));
        }
        host.appendChild(pairsTable(report.pairs || {}));
    }

    async function refresh() {
        const host = el('evalReportsBody');
        const sel = el('evalReportsSelect');
        if (!host || !window.pywebview || !window.pywebview.api) return;
        let res;
        try {
            res = await window.pywebview.api.eval_reports_list();
        } catch (e) {
            host.textContent = '';
            host.appendChild(div('gl-muted', MSG.evalListFailed + ': ' + e));
            return;
        }
        if (!res || res.success !== true) {
            host.textContent = '';
            host.appendChild(div('gl-muted',
                (res && res.error) || MSG.evalListFailed));
            return;
        }
        renderList(res);
        if ((res.reports || []).length > 0) {
            sel.value = res.reports[0].name;
            await load(res.reports[0].name);
        } else {
            renderEmpty(res);
        }
    }

    async function load(name) {
        const host = el('evalReportsBody');
        if (!host || !window.pywebview || !window.pywebview.api) return;
        if (!name) return;
        let res;
        try {
            res = await window.pywebview.api.eval_reports_get(name);
        } catch (e) {
            host.textContent = '';
            host.appendChild(div('gl-muted', MSG.evalLoadFailed + ': ' + e));
            return;
        }
        if (!res || res.success !== true) {
            host.textContent = '';
            host.appendChild(div('gl-muted',
                (res && res.error) || MSG.evalLoadFailed));
            return;
        }
        state.current = res.data;
        renderReport(res.data);
    }

    async function init() {
        const sel = el('evalReportsSelect');
        const btn = el('evalReportsRefreshBtn');
        if (!sel || !btn) return;
        // 文案 JS 态注入（页内零 data-i18n，键 cap 硬约束）
        btn.textContent = MSG.evalRefreshBtn;
        btn.setAttribute('aria-label', MSG.evalRefreshBtn);
        sel.setAttribute('aria-label', MSG.evalSelectHint);
        btn.addEventListener('click', () => { try { refresh(); } catch (e) { /* 不阻断 */ } });
        sel.addEventListener('change', () => { try { load(sel.value); } catch (e) { /* 不阻断 */ } });
        if (window.pywebview && window.pywebview.api) {
            refresh();
        }
    }

    window.addEventListener('pywebviewready', () => {
        try { init(); } catch (e) { /* 不阻断 */ }
    });
    document.addEventListener('DOMContentLoaded', () => {
        // pywebviewready 先于 DOMContentLoaded 的时序兜底
        if (window.pywebview && window.pywebview.api) {
            try { init(); } catch (e) { /* 不阻断 */ }
        }
    });

    window.EvalReports = { init, refresh, load, renderReport, state };
})();
