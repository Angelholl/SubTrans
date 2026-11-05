// ============================================================
// d1102-件B2 设置 hub（D2026-1102-02）：顶层「设置」页四张域卡 +
// 独立 overlay 分页承载原四个设置页。
//
// 关键约束（设计审核意见书 §五 / 立项卡铁律 1-4）：
// - 禁用 AppModal 单例承载：AppModal 的 _busy 守卫会吞掉弹窗内的
//   prompt/confirm（词库新增词条、词典 confirm 死锁），故本弹窗为
//   独立 overlay 容器（z=990，低于 AppModal 1000，内部嵌套确认可压其上）；
// - 四页面板节点在 index.html 内 DOM 原地搬入 overlay（不在此处建 DOM、
//   不做 JS 模板注入重建），静态 data-i18n 节点原样保留；
// - 页签切换只切 display（.tab-page.active），复用既有切页机制；
// - 滚动锁锁真实滚动容器 .main/.aside（style.css），body 兜底；
// - dirty 守卫只覆盖显式保存域：保存接口 / API Key / 保存词库 / 保存角色卡，
//   其余控件本就 change 即存，无「未保存」语义。
// ============================================================

const SettingsHub = {
    DOMAINS: ['engine', 'asrdict', 'glossary', 'advanced'],
    // 域 → 原 tab-page id（面板 id 与 TAB_HOOKS 分组键均沿用，零改名）
    TAB_BY_DOMAIN: {
        engine: 'tab-engine',
        asrdict: 'tab-asrdict',
        glossary: 'tab-glossary',
        advanced: 'tab-advanced',
    },
    _inited: false,
    _isOpen: false,
    _closing: false,
    _domain: 'engine',
    _lastFocus: null,
    _asrProbed: false,
    // 显式保存域白名单（设计审核 §五：dirty 面=显式保存域 only）
    _dirty: { endpoints: false, keys: false, glossary: false, template: false },

    init() {
        if (this._inited) return;
        const overlay = document.getElementById('settingsOverlay');
        if (!overlay) return;
        this._inited = true;
        this._overlay = overlay;
        this._nav = overlay.querySelector('.settings-nav');
        this._content = overlay.querySelector('.settings-content');

        // 设置页四张域卡：点击 → 打开对应域页签
        const settingsPage = document.getElementById('tab-settings');
        if (settingsPage) {
            settingsPage.addEventListener('click', (e) => {
                const card = e.target.closest('.settings-domain-card');
                if (!card || !card.dataset.settingsDomain) return;
                this.open(card.dataset.settingsDomain);
            });
        }

        // 弹窗左竖列页签
        if (this._nav) {
            this._nav.addEventListener('click', (e) => {
                const btn = e.target.closest('.settings-nav-btn');
                if (!btn || !btn.dataset.settingsDomain) return;
                this.showDomain(btn.dataset.settingsDomain);
                try { btn.focus(); } catch (err) { /* 焦点不可用静默 */ }
            });
        }

        // 关闭三通道：关闭钮 / ESC / 遮罩点击，同走 dirty 守卫
        const closeBtn = document.getElementById('settingsCloseBtn');
        if (closeBtn) closeBtn.addEventListener('click', () => this._requestClose());
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) this._requestClose();
        });
        // 捕获阶段先于 AppModal 的 document 冒泡监听：AppModal 活跃时
        // early-return，把 ESC 让给上层（ESC 链 AppModal > 设置 overlay > about）
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape' || !this._isOpen) return;
            if (typeof AppModal !== 'undefined' && AppModal._busy) return;
            const about = document.getElementById('aboutModal');
            if (about && about.classList.contains('active')) return;
            e.preventDefault();
            e.stopPropagation();
            this._requestClose();
        }, true);

        this._bindDirtyWatch();
    },

    // 显式保存域 dirty 监听：输入即脏；对应保存键点击即视为已提交（清零）。
    // 角色卡编辑器本体在 AppModal.editor 内（z=1000 压 overlay），其未保存态
    // 由 AppModal 自带 dirty 守卫承接；此处补 textarea/保存键同口径清零。
    _bindDirtyWatch() {
        const mark = (ids, key) => {
            ids.forEach((id) => {
                const el = document.getElementById(id);
                if (!el) return;
                const on = () => { this._dirty[key] = true; };
                el.addEventListener('input', on);
                el.addEventListener('change', on);
            });
        };
        mark(['refineS1Endpoint', 'refineS3Endpoint'], 'endpoints');
        mark(['refineS1Key', 'refineS3Key'], 'keys');
        mark(['refineTemplateText'], 'template');

        const glTable = document.getElementById('refineGlossTable');
        if (glTable) {
            const on = () => { this._dirty.glossary = true; };
            glTable.addEventListener('input', on);
            glTable.addEventListener('change', on);
        }
        ['refineGlAdd'].forEach((id) => {
            const el = document.getElementById(id);
            if (el) el.addEventListener('click', () => { this._dirty.glossary = true; });
        });

        const clear = (selector, key) => {
            document.querySelectorAll(selector).forEach((el) => {
                el.addEventListener('click', () => { this._dirty[key] = false; });
            });
        };
        clear('#refineSaveEndpointsBtn, .endpoint-save-twin', 'endpoints');
        clear('#refineSaveS1KeyBtn, #refineSaveS3KeyBtn', 'keys');
        // 保存/删除/导入三键均落盘（glDel/glImport 内部自动调 save）
        clear('#refineGlSave, #refineGlDel, #refineGlImport', 'glossary');
        clear('#refineTemplateSave', 'template');
    },

    _resetDirty() {
        Object.keys(this._dirty).forEach((k) => { this._dirty[k] = false; });
    },

    _hasDirty() {
        return Object.keys(this._dirty).some((k) => this._dirty[k]);
    },

    isOpen() {
        return this._isOpen;
    },

    open(domain) {
        this.init();
        if (!this._overlay) return;
        const d = this.DOMAINS.indexOf(domain) >= 0 ? domain : 'engine';
        // 顶层页同步到「设置」：覆盖 review 跳转等非 switchTab 入口，
        // 关闭 overlay 后仍停留在设置页（与旧 tabId 垫片同终态）
        if (typeof switchTab === 'function') switchTab('tab-settings');
        this._isOpen = true;
        this._lastFocus = document.activeElement;
        this._resetDirty();
        this._overlay.classList.add('active');
        this._overlay.setAttribute('aria-hidden', 'false');
        const wb = document.querySelector('.workbench');
        if (wb) wb.classList.add('settings-open');
        document.body.classList.add('settings-open');
        this.showDomain(d);
        const focusEl = (this._nav && this._nav.querySelector('.settings-nav-btn.active'))
            || document.getElementById('settingsCloseBtn');
        if (focusEl) {
            try { focusEl.focus(); } catch (e) { /* 焦点不可用不阻断打开 */ }
        }
        // CT2/词典状态由域钩子异步回填（1s 轮询），稍后补刷一次摘要
        setTimeout(() => { if (this._isOpen) this.refreshSummaries(); }, 800);
    },

    close() {
        if (!this._overlay) return;
        this._isOpen = false;
        this._closing = false;
        this._overlay.classList.remove('active');
        this._overlay.setAttribute('aria-hidden', 'true');
        const wb = document.querySelector('.workbench');
        if (wb) wb.classList.remove('settings-open');
        document.body.classList.remove('settings-open');
        this._resetDirty();
        if (this._lastFocus && typeof this._lastFocus.focus === 'function') {
            try { this._lastFocus.focus(); } catch (e) { /* 焦点复位失败静默 */ }
        }
        this._lastFocus = null;
    },

    async _requestClose() {
        if (!this._isOpen || this._closing) return;
        if (!this._hasDirty()) {
            this.close();
            return;
        }
        this._closing = true;
        let discard = false;
        try {
            discard = await AppModal.confirm(MSG.settingsDirtyConfirm,
                                             MSG.settingsDirtyBody);
        } catch (e) {
            discard = false;
        }
        this._closing = false;
        if (discard) this.close();      // 确认放弃后才关；不自动保存
    },

    showDomain(domain) {
        const d = this.DOMAINS.indexOf(domain) >= 0 ? domain : 'engine';
        this._domain = d;
        if (this._nav) {
            this._nav.querySelectorAll('.settings-nav-btn').forEach((btn) => {
                const on = btn.dataset.settingsDomain === d;
                btn.classList.toggle('active', on);
                btn.setAttribute('aria-selected', on ? 'true' : 'false');
            });
        }
        if (this._content) {
            this._content.querySelectorAll('[data-settings-panel]').forEach((p) => {
                p.classList.toggle('active', p.dataset.settingsPanel === d);
            });
        }
        // TAB_HOOKS 挂点从「切页」改挂「打开对应域页签」：钩子本体不动
        if (typeof TAB_HOOKS !== 'undefined') {
            const hooks = TAB_HOOKS[this.TAB_BY_DOMAIN[d]];
            if (hooks) for (const h of hooks) h();
        }
        this.refreshSummaries();
    },

    // 域卡摘要：只读现成 DOM/接口值，打开与切域时刷新（零新算、零新桥）
    refreshSummaries() {
        this._refreshEngineSummary();
        this._refreshAsrSummary();
        this._refreshGlossarySummary();
        this._refreshAdvancedSummary();
    },

    _val(id) {
        const el = document.getElementById(id);
        return el && typeof el.value === 'string' ? el.value.trim() : '';
    },

    _text(id) {
        const el = document.getElementById(id);
        return el ? (el.textContent || '').trim() : '';
    },

    _selected(id) {
        const el = document.getElementById(id);
        return el && el.selectedIndex >= 0 && el.options[el.selectedIndex]
            ? (el.options[el.selectedIndex].textContent || '').trim() : '';
    },

    _setSummary(domain, lines) {
        const el = document.querySelector(
            `[data-settings-summary="${domain}"]`);
        if (el) el.textContent = lines.filter(Boolean).join('\n');
    },

    _refreshEngineSummary() {
        if (!document.getElementById('refineS1Provider')) return;
        const a = this._selected('refineS1Provider') || '—';
        const am = this._val('refineS1Model') || '—';
        const b = this._selected('refineS3Provider') || '—';
        const bm = this._val('refineS3Model') || '—';
        const profile = this._selected('refineProfile') || '—';
        const conc = this._val('refineConcurrency') || '1';
        this._setSummary('engine', [
            `A · ${a} / ${am}`,
            `B · ${b} / ${bm}`,
            `${profile} · ${MSG.concurrency_label} ${conc}`,
        ]);
    },

    _refreshAsrSummary() {
        const ct2 = this._text('refineCt2Status');
        if (!ct2 && !document.getElementById('refineCt2Status')) return;
        // 域卡摘要要在设置页即可读：CT2/对照状态未探测过时补一次现有桥
        // 只读探测（不新增桥端点；结果经 800ms 延迟刷新回填域卡）
        if (!ct2 && !this._asrProbed && window.pywebview && window.pywebview.api) {
            this._asrProbed = true;
            try { if (typeof asrRefresh === 'function') asrRefresh(false); } catch (e) { /* 静默 */ }
            try { if (typeof ct2Refresh === 'function') ct2Refresh(); } catch (e) { /* 静默 */ }
        }
        const model = this._text('refineCt2ModelStatus') || '—';
        const cross = document.getElementById('asrCrosscheckToggle');
        const onoff = cross && cross.checked ? MSG.settingsSummaryOn
                                            : MSG.settingsSummaryOff;
        const dictEl = document.getElementById('sysSummaryDict');
        const dictRow = dictEl ? dictEl.closest('.sys-summary-row') : null;
        const dictStat = dictRow
            ? (dictRow.querySelector('.sys-summary-stat') || {}).textContent || ''
            : '';
        this._setSummary('asrdict', [
            ct2 || '—',
            model,
            `${MSG.settingsSummaryCrosscheck} ${onoff} · `
                + `${MSG.settingsSummaryDict} ${dictStat.trim() || '—'}`,
        ]);
    },

    _refreshGlossarySummary() {
        if (!document.getElementById('refineGlCount')) return;
        const gl = this._text('refineGlCount') || '—';
        const learned = this._text('glLearnedStats') || '—';
        const dir = `${this._selected('directionSource') || '—'} → `
            + `${this._selected('directionTarget') || '—'}`;
        const tpl = this._val('refineTemplatesDirShow')
            || MSG.templates_dir_placeholder;
        this._setSummary('glossary', [
            `${MSG.settingsSummaryGlobalGlossary} ${gl}`,
            `${MSG.settingsSummaryLearnedGlossary} ${learned}`,
            `${dir} · ${tpl}`,
        ]);
    },

    _refreshAdvancedSummary() {
        if (!document.getElementById('dataRootCurrentPath')) return;
        const path = this._text('dataRootCurrentPath') || '—';
        const tag = this._text('dataRootSourceTag');
        this._setSummary('advanced', [path, tag]);
    },
};

// 设计审核 B2-2 约定的入口名：旧设置 tabId → 域页签垫片统一经此进入
function openSettingsOverlay(domain) {
    SettingsHub.open(domain);
}
