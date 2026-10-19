// ============================================================
// 硬字幕压制队列底条（2.8.0 批1 件5，D2026-1007-03）：全局串行队列 UI。
// - 常驻骨架（#encodeDock）由 show() 显现；只在用户点关闭（×）时隐藏，
//   不随队列空闲自动消失（DoD：完成后「打开文件夹」与失败「重试」须可达）；
// - 轮询 1s：encode_status() + ffmpeg_supply_progress()（下载行复用同面板）；
// - 列表行 createElement 注入（零 id）；外部文本全部 textContent 承载
//   （不经 innerHTML，esc() 语义无涉）；禁 line-clamp（2.7.4 教训）；
// - 行内动作按态：running/queued=取消、failed/cancelled=重试、done=打开文件夹。
// ============================================================
const EncodeDock = {
    _poll: null,
    _expanded: false,
    _lastParams: null,
    _doneLogged: false,

    _api() {
        return (window.pywebview && window.pywebview.api) || null;
    },

    init() {
        const self = this;
        document.querySelectorAll('.encode-entry-btn').forEach((btn) => {
            btn.textContent = btn.dataset.testid === 'encode-entry-guide'
                ? MSG.encodeEntryGuide : MSG.encodeEntryReview;
            btn.addEventListener('click', () => self.openModal());
        });
        // 自动化小节标题行（d1013-卡M / D2026-1013-01：卡L 落空壳
        // span 由 JS 态填充「自动化」小节标题；尾 hairline 由 CSS
        // .pipeline-subhead-text::after 承接）
        const subheadText = document.querySelector('.pipeline-subhead-text');
        if (subheadText) subheadText.textContent = MSG.pipelineGroupAuto;
        // 自动压制开关（批3：管线设置 encode_auto_enabled；缺省关）
        const autoRow = document.querySelector('.encode-auto-row');
        if (autoRow) {
            const box = autoRow.querySelector('.encode-auto-switch');
            const label = autoRow.querySelector('.encode-auto-label');
            // 主行短句（d1013-卡M）：既有长句降副行（desc 空壳填充）
            label.textContent = MSG.encodeAutoShort;
            const autoDesc = autoRow.querySelector('.encode-auto-desc');
            if (autoDesc) autoDesc.textContent = MSG.encodeAutoSwitch;
            box.addEventListener('change', async () => {
                const api2 = self._api();
                if (!api2) return;
                try {
                    await api2.refine_save_stage_settings(null, null,
                        { encode_auto_enabled: box.checked });
                } catch (e) { /* 下次切换自愈 */ }
            });
            // 启动回填（桥就绪后异步读设置；失败保持缺省关）
            (async () => {
                const api2 = self._api();
                if (!api2) return;
                try {
                    const r = await api2.refine_get_stage_settings();
                    if (r && r.success && r.settings) {
                        box.checked = !!r.settings.encode_auto_enabled;
                    }
                } catch (e) { /* 保持缺省关 */ }
            })();
        }
        // 全链自动化开关（3.0 批1 a 段，D2026-1009-02：管线设置
        // fullchain_auto_enabled；缺省关。开启时后端会话钩子整体改道全链
        // 状态机、前端预热经 AppState.fullchainAutoEnabled 短路——C-1/C-2
        // 同门控；镜像同步维护 AppState 供 warmupMaybeStart 守卫消费）
        const fullchainRow = document.querySelector('.fullchain-auto-row');
        if (fullchainRow) {
            const fcBox = fullchainRow.querySelector('.fullchain-auto-switch');
            const fcLabel = fullchainRow.querySelector('.fullchain-auto-label');
            // 主行短句（d1013-卡M）：既有长句降副行（desc 空壳填充）
            fcLabel.textContent = MSG.fullchainAutoShort;
            const fcDesc = fullchainRow.querySelector('.fullchain-auto-desc');
            if (fcDesc) fcDesc.textContent = MSG.fullchainAutoSwitch;
            fcBox.addEventListener('change', async () => {
                const api2 = self._api();
                if (!api2) return;
                AppState.fullchainAutoEnabled = fcBox.checked;
                try {
                    await api2.refine_save_stage_settings(null, null,
                        { fullchain_auto_enabled: fcBox.checked });
                } catch (e) { /* 下次切换自愈 */ }
            });
            // 启动回填（桥就绪后异步读设置；失败保持缺省关）
            (async () => {
                const api2 = self._api();
                if (!api2) return;
                try {
                    const r = await api2.refine_get_stage_settings();
                    if (r && r.success && r.settings) {
                        fcBox.checked = !!r.settings.fullchain_auto_enabled;
                        AppState.fullchainAutoEnabled = fcBox.checked;
                    }
                } catch (e) { /* 保持缺省关 */ }
            })();
        }
        // 压制参数独立设置项（D2026-1008-01 批2）：高级参数页「压制」组
        // （标题/简述 JS 态填充）+「打开压制参数」按钮+右栏自动压制行
        // 「参数」——两入口同开编辑模式弹窗（无选中文件也可用）；摘要行
        // JS 态渲染（保存成功后随 onSaved 刷新）
        const advTitle = document.querySelector('.encode-adv-title');
        if (advTitle) advTitle.textContent = MSG.encodeAdvGroupTitle;
        const advDesc = document.querySelector('.encode-adv-desc');
        if (advDesc) advDesc.textContent = MSG.encodeAdvGroupDesc;
        document.querySelectorAll('.encode-params-open-btn').forEach((btn) => {
            btn.textContent = MSG.encodeAdvOpenBtn;
            btn.addEventListener('click', () => self.openModal({ editOnly: true }));
        });
        const paramsLink = document.querySelector('.encode-params-link');
        if (paramsLink) {
            paramsLink.textContent = MSG.encodeParamsLink;
            paramsLink.addEventListener('click', (e) => {
                e.preventDefault();
                self.openModal({ editOnly: true });
            });
        }
        self.renderParamsSummary();
        const dock = document.getElementById('encodeDock');
        if (!dock) return;
        dock.querySelector('.queue-dock-dismiss').textContent = MSG.encodeDismiss;
        dock.querySelector('.queue-dock-dismiss').addEventListener('click', () => self.hide());
        const toggle = document.getElementById('encodeDockToggle');
        toggle.textContent = MSG.encodeExpand;
        toggle.addEventListener('click', () => self.togglePanel());
        dock.querySelector('.queue-dock-cancel').textContent = MSG.encodeCancelJob;
        dock.querySelector('.queue-dock-cancel').addEventListener('click', () => self.cancelAll());
    },

    async openModal(opts) {
        const api = this._api();
        if (!api) return;
        // 参数编辑模式（D2026-1008-01 批2）：压制参数独立设置项——无选中
        // 文件也可打开，读上次参数进弹窗编辑；保存走 encode_save_params 桥
        // （弹窗内「保存参数」按钮），此处绝不触碰 preflight/commit/jobs。
        // GPU 可用性无独立探测桥（仅 preflight 顺带双检懒缓存），编辑模式
        // 传 gpu:null → GPU 选项置灰、弹窗 title 显因「发起压制后可检测」
        if (opts && opts.editOnly) {
            let lp = null;
            try { lp = await api.encode_get_last_params(); } catch (e) { lp = null; }
            const last = (lp && lp.success && lp.params) || this._lastParams || {};
            await AppModal.encode({
                editOnly: true,
                jobs: [],
                last,
                presets: null,
                gpu: null,
                onSaved: (params) => {
                    this._lastParams = params;
                    this.renderParamsSummary();
                },
            });
            return;
        }
        const jobs = (AppState.selectedFiles || []).map((p) => ({ srt_path: p }));
        if (jobs.length === 0) {
            AppModal.alert(MSG.encodeModalTitle, MSG.encodeNoJobs);
            return;
        }
        let pre = null;
        try {
            if (!this._lastParams) {
                const lp = await api.encode_get_last_params();
                if (lp && lp.success) this._lastParams = lp.params || {};
            }
            pre = await api.encode_preflight(jobs, this._lastParams || {});
        } catch (e) {
            AppModal.alert(MSG.encodeModalTitle, String(e));
            return;
        }
        if (!pre || pre.success === false) {
            AppModal.alert(MSG.encodeModalTitle, (pre && pre.error) || String(pre));
            return;
        }
        // 供给缺口 → 引导一次完整版下载（HRO-1：能力探测是主路径保障）
        if (pre.supply_missing && pre.supply_missing.length > 0) {
            const ok = await AppModal.confirm(MSG.encodeModalTitle, MSG.encodeSupplyMissing);
            if (ok) {
                try {
                    await api.ffmpeg_supply_download();
                } catch (e) { /* 单飞守卫拒绝视为已在下载 */ }
                this.show();
            }
            return;
        }
        // 有效任务过滤（缺视频/缺终稿字幕的项不入队，明细在 preflight items）
        const valid = [];
        let noVideo = 0;
        let noSub = 0;
        (pre.items || []).forEach((it) => {
            if (!it.video_exists) { noVideo += 1; return; }
            if (!it.subtitle_exists) { noSub += 1; return; }
            valid.push(it);
        });
        if (valid.length === 0) {
            const why = noVideo > 0 ? MSG.encodeNoVideo : MSG.encodeNoSubtitle;
            AppModal.alert(MSG.encodeModalTitle, why + '（' + (pre.items || []).length + ' 个文件）');
            return;
        }
        let presets = null;
        try { presets = await api.encode_presets_list(); } catch (e) { presets = null; }
        const res = await AppModal.encode({
            jobs: valid,
            totalEtaS: pre.total_eta_s,
            last: this._lastParams || {},
            presets,
            gpu: pre.gpu,
        });
        if (!res || !res.ok) return;
        this._lastParams = res.params;
        try { api.encode_save_last_params(res.params); } catch (e) { /* 持久化失败不阻塞 */ }
        await this.commit(valid, res.params, false);
    },

    // 高级参数页摘要行（D2026-1008-01 批2）：读 encode_get_last_params
    // 渲染「格式 · 画质 · 音量 · 保存时间」一行简报（JS 态 MSG 函数键拼装；
    // 缺已保存参数时空态文案）。弹窗编辑模式保存成功后经 onSaved 重渲染。
    async renderParamsSummary() {
        const row = document.querySelector('.encode-params-summary');
        if (!row) return;
        let p = this._lastParams;
        if (!p || !Object.keys(p).length) {
            const api = this._api();
            if (api) {
                try {
                    const lp = await api.encode_get_last_params();
                    if (lp && lp.success) { p = lp.params || {}; this._lastParams = p; }
                } catch (e) { /* 渲染降级：保留空态文案 */ }
            }
        }
        p = p || {};
        if (!p.video_format && !p.quality && !p.saved_at) {
            row.textContent = MSG.encodeSummaryEmpty;
            return;
        }
        const parts = [];
        const fmt = { h264: 'H.264', h265: 'H.265', av1: 'AV1' }[p.video_format];
        if (fmt) parts.push(fmt);
        const q = { compress: MSG.encodeQCompress, balanced: MSG.encodeQBalanced,
                    quality: MSG.encodeQQuality }[p.quality];
        if (q) parts.push(String(q).split('（')[0]);
        const db = typeof p.volume_db === 'number' ? p.volume_db : 0;
        parts.push(MSG.encodeSummaryVol((db > 0 ? '+' : '') + db));
        if (p.saved_at) parts.push(MSG.encodeSummaryAt(p.saved_at));
        row.textContent = MSG.encodeSummaryLine(parts);
    },

    async commit(jobs, params, allowOverwrite) {
        const api = this._api();
        let commit = null;
        try {
            commit = await api.encode_commit(jobs, params, allowOverwrite === true);
        } catch (e) {
            AppModal.alert(MSG.encodeModalTitle, String(e));
            return;
        }
        if (commit && commit.needs_confirm) {
            const list = (commit.existing || []).map((p) => '· ' + p).join('\n');
            const ok = await AppModal.confirm(
                MSG.encodeOverwriteTitle,
                MSG.encodeOverwriteBody.replace('{list}', list));
            if (ok) await this.commit(jobs, params, true);
            return;
        }
        if (!commit || commit.success === false) {
            const err = (commit && commit.error) || String(commit);
            AppModal.alert(MSG.encodeModalTitle,
                MSG.encodeCommitRejected.replace('{e}', err));
            return;
        }
        if (commit.rejected && commit.rejected.length > 0) {
            const first = commit.rejected[0] || {};
            AppModal.alert(MSG.encodeModalTitle, String(first.reason || ''));
        }
        this.show();
        this.refresh();
    },

    show() {
        const dock = document.getElementById('encodeDock');
        if (dock) dock.style.display = '';
        this.startPolling();
    },

    hide() {
        const dock = document.getElementById('encodeDock');
        if (dock) dock.style.display = 'none';
        this.stopPolling();
    },

    togglePanel() {
        this._expanded = !this._expanded;
        const panel = document.getElementById('encodeDockList');
        const toggle = document.getElementById('encodeDockToggle');
        if (panel) panel.style.display = this._expanded ? '' : 'none';
        if (toggle) toggle.textContent = this._expanded ? MSG.encodeCollapse : MSG.encodeExpand;
    },

    startPolling() {
        if (this._poll) return;
        this.refresh();
        this._poll = setInterval(() => this.refresh(), 1000);
    },

    stopPolling() {
        if (this._poll) {
            clearInterval(this._poll);
            this._poll = null;
        }
    },

    async refresh() {
        const api = this._api();
        if (!api) return;
        let st = null;
        let sup = null;
        try {
            st = await api.encode_status();
            sup = await api.ffmpeg_supply_progress();
        } catch (e) {
            return;   // 桥未就绪/瞬时失败：下轮自愈
        }
        if (!st || st.success === false) return;
        const jobs = st.jobs || [];
        const supplyActive = sup && sup.success !== false
            && (sup.busy || sup.phase === 'downloading');
        // 交付闭环（批3）：全部完成的瞬间 Console 活动流一行人话（完成不打断
        // ——不弹窗不抢焦点，四处硬性规定之批3 落点）；每次排空只报一次
        const anyActive = jobs.some((j) => j.state === 'running' || j.state === 'queued');
        if (jobs.length > 0 && !anyActive && !this._doneLogged) {
            this._doneLogged = true;
            try {
                ConsoleManager.log(MSG.encodeAutoDoneLine, 'success');
            } catch (e) { /* console 通道缺席不阻塞 */ }
        }
        if (anyActive) this._doneLogged = false;
        if (jobs.length === 0 && !supplyActive) return;   // 未显过底条则保持隐藏
        this.show();
        this.render(jobs, sup);
    },

    _stateText(state) {
        return MSG['encodeSt' + String(state || '').charAt(0).toUpperCase()
            + String(state || '').slice(1)] || state;
    },

    render(jobs, sup) {
        const dock = document.getElementById('encodeDock');
        if (!dock) return;
        const dot = dock.querySelector('.queue-dock-state');
        const label = document.getElementById('encodeDockLabel');
        const fill = document.getElementById('encodeDockFill');
        const eta = dock.querySelector('.queue-dock-eta');
        const cancelBtn = dock.querySelector('.queue-dock-cancel');
        const running = jobs.find((j) => j.state === 'running');

        // 供给下载行优先（压制未启动时占住底条）
        if (sup && (sup.busy || (sup.phase && sup.phase !== 'idle' && sup.phase !== 'done'))) {
            const pct = (sup.total > 0)
                ? Math.min(99, Math.round((sup.received / sup.total) * 100)) : 0;
            dot.className = 'queue-dock-state running';
            label.textContent = MSG.encodeDownloadDock
                + ' ' + ((sup.received / (1024 * 1024)) || 0).toFixed(0) + 'MB';
            fill.style.width = pct + '%';
            fill.classList.remove('err');
            eta.textContent = pct + '%';
            cancelBtn.style.display = '';
            cancelBtn.textContent = MSG.encodeStop;
        } else if (running) {
            dot.className = 'queue-dock-state running';
            label.textContent = MSG.encodeDockRunning + ' ' + this._baseName(running.out_path)
                + ' · ' + String(running.params && running.params.video_format || '').toUpperCase()
                + ' ' + this._stateText(running.state);
            fill.style.width = (running.progress || 0) + '%';
            fill.classList.remove('err');
            eta.textContent = (running.progress || 0) + '%'
                + (running.eta_s > 0
                    ? ' · ETA ' + MSG.encodeMinutes.replace('{m}', Math.max(1, Math.round(running.eta_s / 60)))
                    : '');
            cancelBtn.style.display = '';
            cancelBtn.textContent = MSG.encodeCancelJob;
        } else {
            // 空闲态标签/圆点跟随最新任务（黑盒修正：历史含取消/失败项时
            // 不得永久卡「压制失败」——history 只增，以末条为准）
            const latest = jobs.length ? jobs[jobs.length - 1] : null;
            const bad = !!(latest
                && (latest.state === 'failed' || latest.state === 'cancelled'));
            dot.className = 'queue-dock-state' + (bad ? ' failed' : '');
            label.textContent = !latest ? MSG.encodeDockIdle
                : (latest.state === 'failed' ? MSG.encodeDockFailed
                    : (latest.state === 'cancelled' ? MSG.encodeStCancelled
                        : MSG.encodeDockDone));
            fill.style.width = bad ? fill.style.width : '100%';
            if (bad) fill.classList.add('err'); else fill.classList.remove('err');
            eta.textContent = '';
            cancelBtn.style.display = 'none';
        }
        this.renderList(jobs, sup);
    },

    _baseName(p) {
        return String(p || '').split(/[\\/]/).pop() || String(p || '');
    },

    renderList(jobs, sup) {
        const panel = document.getElementById('encodeDockList');
        if (!panel) return;
        panel.textContent = '';
        const mk = (tag, cls, parent) => {
            const el = document.createElement(tag);
            if (cls) el.className = cls;
            if (parent) parent.appendChild(el);
            return el;
        };
        if (sup && (sup.busy || sup.phase === 'downloading')) {
            const row = mk('div', 'queue-item', panel);
            mk('span', 'queue-item-dot running', row);
            const nm = mk('span', 'queue-item-name', row);
            nm.textContent = MSG.encodeDownloadDock;
            const tr = mk('span', 'queue-item-track', row);
            const f = mk('span', 'progress-fill', tr);
            f.style.width = ((sup.total > 0)
                ? Math.min(99, Math.round((sup.received / sup.total) * 100)) : 0) + '%';
        }
        jobs.slice().reverse().forEach((j) => {
            const row = mk('div', 'queue-item', panel);
            row.dataset.encodeJobId = j.id;
            mk('span', 'queue-item-dot ' + j.state, row);
            const nm = mk('span', 'queue-item-name', row);
            nm.textContent = this._baseName(j.out_path);
            nm.title = j.out_path;
            if (j.state === 'running' || j.state === 'queued') {
                const tr = mk('span', 'queue-item-track', row);
                const f = mk('span', 'progress-fill', tr);
                f.style.width = (j.progress || 0) + '%';
                if (j.state === 'queued') f.style.width = '0%';
            } else if (j.state === 'done') {
                const pill = mk('span', 'queue-item-pill', row);
                pill.textContent = MSG.encodeStDone;
            } else if (j.error) {
                const err = mk('span', 'queue-item-err', row);
                err.textContent = j.error;
                err.title = j.error;
            }
            const act = mk('button', 'btn btn-ghost btn-sm', row);
            if (j.state === 'running' || j.state === 'queued') {
                act.textContent = MSG.encodeCancelJob;
                act.addEventListener('click', () => this.cancelOne(j));
            } else if (j.state === 'failed' || j.state === 'cancelled') {
                act.textContent = MSG.encodeRetry;
                act.addEventListener('click', () => this.retry(j.id));
            } else if (j.state === 'done') {
                act.textContent = MSG.encodeOpenFolder;
                act.addEventListener('click', () => this.openFolder(j.id));
            } else {
                act.style.display = 'none';
            }
        });
    },

    async cancelOne(job) {
        const api = this._api();
        if (!api) return;
        if (job.state === 'running') {
            const ok = await AppModal.confirm(MSG.encodeModalTitle, MSG.encodeCancelOneConfirm);
            if (!ok) return;
        }
        try { await api.encode_cancel(job.id); } catch (e) { /* 下轮轮询自愈 */ }
        this.refresh();
    },

    async cancelAll() {
        const api = this._api();
        if (!api) return;
        // 供给下载进行中 → 停止下载；否则取消队列
        try {
            const sup = await api.ffmpeg_supply_progress();
            if (sup && sup.success !== false && (sup.busy || sup.phase === 'downloading')) {
                await api.ffmpeg_supply_stop();
                this.refresh();
                return;
            }
        } catch (e) { /* 忽略走队列取消 */ }
        const ok = await AppModal.confirm(MSG.encodeModalTitle, MSG.encodeCancelAllConfirm);
        if (!ok) return;
        try { await api.encode_cancel(''); } catch (e) { /* 下轮轮询自愈 */ }
        this.refresh();
    },

    async retry(jobId) {
        const api = this._api();
        if (!api) return;
        try { await api.encode_retry(jobId); } catch (e) { /* 下轮轮询自愈 */ }
        this.show();
        this.refresh();
    },

    async openFolder(jobId) {
        const api = this._api();
        if (!api) return;
        try { await api.encode_open_folder(jobId); } catch (e) { /* 静默 */ }
    },
};

