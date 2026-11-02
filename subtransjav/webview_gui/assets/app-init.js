// ============================================================
// Initialization
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
    console.log('SubTrans GUI initialized');

    // i18n：先把 MSG 文案注入 data-i18n* 标记的元素
    applyI18n();

    // Initialize components (pure DOM parts)
    ConsoleManager.init();
    // d1102-件C（D2026-1102-02）：首页 L2 流程概览条绑定与首刷
    FlowOverview.init();
    ProgressManager.init();
    ProgressManager.reset();
    FileListManager.init();
    DirectoryControls.init();
    RunControlsInit();
    KeyboardShortcuts.init();
    ThemeManager.init();
    TranslatorManager.init();
    // d1102-件B2（D2026-1102-02）：设置 hub 独立 overlay 绑定（域卡/页签/
    // dirty 守卫/滚动锁）。禁用 AppModal 单例承载，故不随 AppModal 初始化。
    SettingsHub.init();

    // Update Start button state once at startup
    TranslatorManager.updateButtons();

    // 右栏卡 3 镜像：加载后渲染 + 引擎页控件变更时同步（只读，无回写）
    refreshPipelineMirror();
    ['refineS1Model', 'refineConcurrency'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', refreshPipelineMirror);
    });

    // 卡G2（D2026-1013-01 §2.2d/e/f）：右栏折叠行为——启动默认 + 把手单钮绑定
    // （卡N：两钮融合为单钮双态） + localStorage 单写记忆（键串见下方 getItem）。
    // - 1240 窗口阈值只作用启动默认：记忆优先，无记忆按 innerWidth <= 1240 收起；
    //   运行期不挂 resize 自动切换（用户显式操作永久优先，粘滞不回弹）。
    // - 降级三分支：a) 实测持久 OK 本路线即定案；b) 实测不持久由主审关记忆层
    //   回落阈值默认；c) theme 式双写为休眠备选，启用须新的显式拍板。
    // - 已知代价：升级或换数据目录可能清 localStorage → 记忆复位为默认（非丢数据）。
    (function () {
        const BTN_SEL = '.aside-toggle-btn';
        let asideCollapsed = null;
        try {
            asideCollapsed = localStorage.getItem('subtransjav.aside.collapsed');
        } catch (e) {
            // private/无痕读不到 → 降级走窗口阈值默认
        }
        if (asideCollapsed !== '0' && asideCollapsed !== '1') {
            asideCollapsed = window.innerWidth <= 1240 ? '1' : '0';
        }
        const startupCollapsed = asideCollapsed === '1';
        document.querySelectorAll(BTN_SEL).forEach((btn) => {
            const asideEl = btn.closest('.aside');
            const workbenchEl = asideEl ? asideEl.closest('.workbench') : null;
            if (!workbenchEl) return;
            // 文案回填复用既有 MSG 键（零新增键；HTML 侧零 id 零 data-i18n）
            btn.setAttribute('aria-label', MSG.collapse_toggle);
            btn.setAttribute('title', MSG.collapse_toggle);
            workbenchEl.classList.toggle('aside-collapsed', startupCollapsed);
            btn.setAttribute('aria-expanded', startupCollapsed ? 'false' : 'true');
            btn.addEventListener('click', () => {
                const collapsed =
                    !workbenchEl.classList.contains('aside-collapsed');
                workbenchEl.classList.toggle('aside-collapsed', collapsed);
                asideEl.querySelectorAll(BTN_SEL).forEach((b) => {
                    b.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
                });
                try {
                    localStorage.setItem('subtransjav.aside.collapsed',
                                         collapsed ? '1' : '0');
                } catch (e) {
                    // 写入失败静默（private 模式降级为会话级折叠）
                }
            });
        });
    })();

    // 卡 3 提示态惰性求值：hover/focus 时按当前页切换提示文案（D2026-1012-01 ⑨）
    function refreshPipelineCardHint() {
        const el = document.getElementById('pipelineCard');
        if (!el) return;
        const here = document.querySelector('.tab-page.active')?.id === 'tab-engine';
        el.title = MSG[here ? 'pipeline_card_hint_here' : 'pipeline_card_hint'];
    }

    // 卡 3 整卡跳转引擎页（只读镜像的修改入口）
    const pipelineCard = document.getElementById('pipelineCard');
    if (pipelineCard) {
        pipelineCard.addEventListener('click', (e) => {
            // 卡K（D2026-1013-01 真机反馈）：交互元素不触发整卡跳转（统一入口过滤）
            const target = e.target;
            if (target instanceof Element && target.closest(
                    'button, input, label, a, select, textarea, .path-row, .destination-section, .encode-auto-row, .fullchain-auto-row, .encode-params-link')) {
                return;
            }
            switchTab('tab-engine');
        });
        pipelineCard.addEventListener('keydown', (e) => {
            // 卡K（D2026-1013-01 真机反馈）：同一过滤——键盘激活交互元素不跳转；
            // 卡片本身聚焦时 Enter 仍跳（closest 不命中交互元素即放行）
            const target = e.target;
            if (target instanceof Element && target.closest(
                    'button, input, label, a, select, textarea, .path-row, .destination-section, .encode-auto-row, .fullchain-auto-row, .encode-params-link')) {
                return;
            }
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                switchTab('tab-engine');
            }
        });
        pipelineCard.addEventListener('mouseenter', refreshPipelineCardHint);
        pipelineCard.addEventListener('focus', refreshPipelineCardHint);
        refreshPipelineCardHint();
    }

    // 卡I（D2026-1013-01 真机反馈）：输出目录并入本卡，交互区域内阻断
    // 整卡跳转冒泡（click 与键盘 Enter 均不触发 switchTab）
    const destSection = document.querySelector('.destination-section');
    if (destSection) {
        destSection.addEventListener('click', (e) => e.stopPropagation());
        destSection.addEventListener('keydown', (e) => e.stopPropagation());
    }

    ConsoleManager.log(MSG.gui_initialized, 'success');
    ConsoleManager.log(MSG.gui_usage_hint, 'info');
});

function RunControlsInit() {
    // Placeholder hook for future global controls; refine panel owns its own buttons.
}

// 右栏卡 3 只读镜像（D2026-0930-09 批2）：读引擎页当前配置渲染，不做双向同步
function refreshPipelineMirror() {
    const line = document.getElementById('pipelineMirrorLine');
    if (!line) return;
    const model = ((document.getElementById('refineS1Model') || {}).value || '').trim() || '—';
    const conc = ((document.getElementById('refineConcurrency') || {}).value || '').trim() || '1';
    line.textContent = `${MSG.pipeline_mirror_model}：${model}　·　${MSG.pipeline_mirror_conc} ${conc}`;
}

// PyWebView ready event — backend bridge is now available.
window.addEventListener('pywebviewready', async () => {    console.log('PyWebView API ready!');
    ConsoleManager.log(MSG.bridgeConnected, 'success');
    window.__pywebviewReady = true;

    // D2026-1010-03 件C：应用级常驻日志排水——全链自动化 daemon 在任务
    // 结束后仍向翻译日志队列投递阶段行（_automation_notice 尽力投），而
    // 状态轮询随 _finish 停摆，若无常驻排水，全链过程行永远到不了
    // Console/原始日志/导出（真机黑箱实证），且积压行会在下次任务启动
    // 时作陈旧行误 flush。2s 轻拍仅排日志不触状态桥；与任务期 1s 主轮
    // 询并存幂等（fetchLogs 自带 try/catch，空队列零开销）。
    if (!TranslatorManager._logDrainInterval) {
        TranslatorManager._logDrainInterval = setInterval(() => {
            try { TranslatorManager.fetchLogs(); }
            catch (e) { console.warn('log drain failed:', e); }
        }, 2000);
    }

    // A3 主题持久化走后端：读取 settings.theme 并应用
    await ThemeManager.loadSavedThemeFromBackend();

    await AppState.loadDefaultOutputDir();

    // 右栏系统状态摘要卡（D2026-1001 批3）：只读四接口，逐项降级
    SystemSummary.load();

    // d1102-件C：首页概览条消费 fullchain_automation_status（C22 门＋last_run），
    // 与质量中心 fullchain-status-line 同 API 双渲染（digest 模式复用）
    FlowOverview.refresh();

    // Load saved stage settings, glossary, templates and model lists
    if (window.__refineLoadRemote) {
        await window.__refineLoadRemote();
    }

    // 硬字幕压制底条/入口接线（2.8.0 批1 件5）；若有在途队列（热刷新场景）
    // 由 refresh 轮询自然恢复显示
    EncodeDock.init();

    // Initialize feature status indicators
    await FeatureStatus.init();

    // 2.7.1 首启空闲探测（D2026-1005-01 承接批，README 提示句口径）：后台
    // 触发一次 refine_asr_status 回填探测快照缓存（短暂启动一次 Python
    // 子进程，通常数秒；不阻塞首屏，结果稍后显示在 ASR 卡/模型管理面板）
    setTimeout(() => {
        try {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.refine_asr_status();
            }
        } catch (e) { /* 后台预热失败静默（显式探测按钮兜底） */ }
    }, 3000);
});

// ============================================================
// 首页 L2 流程概览条（d1102-件C，D2026-1102-02；卡B 换代跳转）
// - 转录→翻译→校对→全链四节点 chip 直达：转录→本页转录卡、校对→校对页、
//   翻译→本页 dropzone、全链→本页开关行；滚动定位一律 block:center＋
//   .flow-flash 高亮脉冲（jump() 内 flash() 两 chip 共用）；
// - C22 门状态行＋last_run 一行摘要消费 fullchain_automation_status，
//   与质量中心 fullchain-status-line 同 API 双渲染（复用 fcStatus* 键）；
// - 门关态 muted 灰点＋原因码，不用警报红（校准未达标系常态）。
// ============================================================
// 门原因码→人话（d1102-E 件3）：后端 evaluate_c22_gate 的裸码不得直出
// 用户界面；未知码统一兜底「原因未知」，不暴露内部码。
const GATE_REASON_TEXT = {
    'missing': '门控文件缺失',
    'invalid': '门控文件损坏或无法读取',
    'disabled': '校准尚未启用',
    'fingerprint-missing': '校准指纹缺失，需重新校准',
    'fingerprint-mismatch': '规则集已变更，需重新校准',
};

const FlowOverview = {
    _lastRun: {},
    _running: false,
    // d1102-件D（D2026-1102-02）：转录桥状态（idle/running/done 三态）
    _transcribeState: 'idle',
    // d1102-件F：done 仅对本次会话最近一次转录的媒体成立——媒体切换/
    // 离开校对页即清回 idle（防一次转录后节点常亮）
    _transcribeDoneMedia: null,

    init() {
        const box = document.getElementById('flowOverview');
        if (!box) return;
        box.addEventListener('click', (e) => {
            const chip = e.target.closest('.flow-chip');
            if (!chip) return;
            this.jump(chip.dataset.flow);
        });
        window.__homeOverviewRefresh = () => this.refresh();
        // d1102-件F：转录 done 清/标记入口（review.js 媒体切换/离页/完成时调用）
        window.__homeOverviewTranscribeReset = () => this.resetTranscribeNode();
        window.__homeOverviewTranscribeDone =
            (mediaPath) => this.markTranscribeDone(mediaPath);
        this.refresh();
    },

    fmt(tpl, kw) {
        return String(tpl).replace(/\{(\w+)\}/g,
            (m, k) => (kw[k] === undefined || kw[k] === null ? m : kw[k]));
    },

    gateReason(code) {
        const key = String(code || '').trim();
        return GATE_REASON_TEXT[key] || '原因未知';
    },

    setChip(flow, state) {
        const chip = document.querySelector(
            `.flow-chip[data-flow="${flow}"]`);
        if (!chip) return;
        chip.classList.remove('is-ok', 'is-warn', 'is-danger');
        if (state && state !== 'idle') chip.classList.add('is-' + state);
    },

    jump(flow) {
        // d1102-卡B：chip 可见反馈统一——滚动居中 + .flow-flash 高亮脉冲
        // （animationend 移除，两 chip 共用本 flash 小函数）
        const flash = (el) => {
            if (!el) return;
            el.scrollIntoView({ behavior: 'smooth', block: 'center' });
            el.classList.add('flow-flash');
            el.addEventListener('animationend',
                () => el.classList.remove('flow-flash'), { once: true });
        };
        if (flow === 'review') {
            switchTab('tab-review');
            return;
        }
        if (flow === 'transcribe') {
            // d1102-卡B：首页新增转录卡后转录 chip 留首页定位，不再跳校对页
            switchTab('tab-translate');
            flash(document.getElementById('homeTranscribeCard'));
            return;
        }
        if (flow === 'translate') {
            switchTab('tab-translate');
            flash(document.getElementById('dropzone'));
            return;
        }
        if (flow === 'fullchain') {
            switchTab('tab-translate');
            const row = document.querySelector('.fullchain-auto-row');
            if (!row) return;
            row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            const box = row.querySelector('input');
            if (box) box.focus();
        }
    },

    refreshNodes() {
        const files = (typeof AppState !== 'undefined'
            && Array.isArray(AppState.selectedFiles))
            ? AppState.selectedFiles.length : 0;
        const running = typeof AppState !== 'undefined' && !!AppState.isRunning;
        this.setChip('translate', running ? 'warn' : (files ? 'ok' : 'idle'));
        // 件D：转录节点接转录桥 status（running=warn / done=ok / idle 原灰点）
        this.setChip('transcribe', this._transcribeChipState());
        this.setChip('review', 'idle');
        this.refreshTranscribeNode();
        const run = this._lastRun || {};
        const hasRun = Object.keys(run).length > 0;
        let fc = 'idle';
        if (running) fc = 'warn';
        else if (hasRun && String(run.phase || '') === 'failed') fc = 'danger';
        else if (hasRun) fc = 'ok';
        this.setChip('fullchain', fc);
    },

    _transcribeChipState() {
        if (this._transcribeState === 'running') return 'warn';
        if (this._transcribeState === 'done') return 'ok';
        return 'idle';
    },

    _sameMedia(a, b) {
        const norm = (p) => String(p || '').replace(/\\/g, '/').toLowerCase();
        return !!a && !!b && norm(a) === norm(b);
    },

    resetTranscribeNode() {
        this._transcribeDoneMedia = null;
        this._transcribeState = 'idle';
        this.setChip('transcribe', 'idle');
    },

    markTranscribeDone(mediaPath) {
        this._transcribeDoneMedia = mediaPath || null;
        this._transcribeState = 'done';
        this.setChip('transcribe', this._transcribeChipState());
    },

    async refreshTranscribeNode() {
        // 转录桥 status 轮询面（无任务/未就绪时保持 idle 灰点）
        if (!window.pywebview || !window.pywebview.api) {
            this.resetTranscribeNode();
            return;
        }
        try {
            const api = window.pywebview.api;
            const s = await api.refine_review_transcribe_status();
            if (s && s.running) {
                // 新一轮进行中：旧 done 作废（避免上一条媒体常亮）
                this._transcribeDoneMedia = null;
                this._transcribeState = 'running';
            } else if (this._transcribeDoneMedia
                       && this._sameMedia(s && s.media_path,
                                          this._transcribeDoneMedia)) {
                this._transcribeState = 'done';
            } else {
                this._transcribeState = 'idle';
            }
        } catch (e) {
            this._transcribeDoneMedia = null;
            this._transcribeState = 'idle';
        }
        this.setChip('transcribe', this._transcribeChipState());
    },

    async refresh() {
        const gate = document.querySelector('.flow-gate');
        const gateText = document.querySelector('.flow-gate-text');
        const last = document.querySelector('.flow-lastrun');
        if (!gate || !gateText || !last) return;
        if (!window.pywebview || !window.pywebview.api) {
            gate.classList.remove('is-on');
            gateText.textContent = MSG.flowGateUnavailable;
            last.textContent = MSG.fcStatusFail;
            return;
        }
        let r = null;
        try {
            r = await window.pywebview.api.fullchain_automation_status();
        } catch (e) { /* 桥异常按读取失败处理 */ }
        if (!r || !r.success) {
            gate.classList.remove('is-on');
            gateText.textContent = MSG.flowGateUnavailable;
            last.textContent = MSG.fcStatusFail;
            return;
        }
        const cg = r.c22_gate || {};
        gate.classList.toggle('is-on', !!cg.enabled);
        gateText.textContent = cg.enabled ? MSG.flowGateOn
            : this.fmt(MSG.flowGateOff, { reason: this.gateReason(cg.reason) });
        const run = r.last_run || {};
        const k = Number(run.missed_skipped) || 0;
        this._lastRun = run;
        this._running = !!r.running;
        if (r.running) {
            last.textContent = this.fmt(MSG.fcStatusRunning, {
                d: run.files_done || 0, t: run.files_total || 0,
                f: run.entries_fixed || 0 });
        } else if (!Object.keys(run).length) {
            last.textContent = MSG.fcStatusNever;
        } else if (String(run.phase || '') === 'skipped') {
            const why = String(run.skip_reason || '').trim();
            last.textContent = why ? `未启动全链：${why}` : MSG.fcStatusSkipped;
        } else if (!String(run.ended_at || '').trim()) {
            last.textContent = this.fmt(MSG.fcStatusUnfinished,
                { p: run.entries_pending || 0 });
        } else {
            last.textContent = this.fmt(MSG.fcStatusLast, {
                time: String(run.ended_at).slice(11, 16),
                f: run.entries_fixed || 0, m: run.entries_failed || 0,
                p: run.entries_pending || 0,
                phase: String(run.phase || '') });
            if (k > 0) {
                last.textContent += ' · ' + this.fmt(MSG.fcMissedSkipped, { k });
            }
        }
        this.refreshNodes();
    }
};
