// ============================================================
// Translator Manager (净语翻译两阶段执行)
// ============================================================
const TranslatorManager = {
    state: {
        isRunning: false,
        progress: 0
    },

    init() {
        console.log('TranslatorManager initialized');
    },

    /**
     * Update Start/Cancel button states.
     * Called whenever the shared file list or run state changes.
     */
    updateButtons() {
        const hasFiles = AppState.selectedFiles.length > 0;
        const isRunning = this.state.isRunning;

        const startBtns = [
            document.getElementById('refineStartBtn'),
            document.querySelector('[data-testid="btn-start-translate"]')
        ].filter(Boolean);
        const cancelBtn = document.getElementById('refineCancelBtn');
        startBtns.forEach((startBtn) => { startBtn.disabled = !hasFiles || isRunning; });
        if (cancelBtn) cancelBtn.disabled = !isRunning;
    },

    async startTranslation() {
        if (AppState.isRunning) return;
        if (this._warmupHolding) return;   // 预热持有中重复点击：已入队不重复

        if (AppState.selectedFiles.length === 0) {
            ErrorHandler.show(MSG.noFilesTitle, MSG.no_files_hint);
            return;
        }

        // G9 入队参数快照（方案 A，D2026-1008-02 批3）：点击那一刻的
        // collectOptions 即「所点即所跑」，持有放行后按本快照走启动链
        let options = null;
        try {
            // collectOptions 抛错时按钮状态才能正常复位并提示
            options = this.collectOptions();
        } catch (error) {
            ConsoleManager.log(MSG.translationErrorLog(error.message), 'error');
            ErrorHandler.show(MSG.translationErrorTitle, error.message);
            this._finish(MSG.error, 'err');
            return;
        }

        // P1 G9 (c) 阻断（D2026-1008-02 批3）：预热 loading 中 → 持有模式
        //（参数区锁定+开始按钮倒计时），终态/超时/桥不可达放行后继续下方
        // 正常启动链（含后端 needs_confirm 等既有门，不新增确认弹窗）
        const go = await this._warmupHoldUntilRelease();
        if (!go) return;

        try {
            AppState.isRunning = true;
            this.state.isRunning = true;
            FileListManager.updateButtons();
            this.setProgress(0);
            this.setStatus(MSG.starting);
            ProgressManager.setDot('running');
            ProgressManager.setIndeterminate(true);

            // 断点恢复探测：三态 chip 初始点亮（D2026-0930-09 批2）+ 可恢复文件打到控制台
            if (AppState.selectedFiles.length > 0) {
                try {
                    const states = await pywebview.api.scan_resume_states(
                        AppState.selectedFiles.slice());
                    (states || []).forEach(s => {
                        if (!s || !s.path) return;
                        // state: completed|resumable|none -> done|resumable|pending
                        FileListManager.setState(
                            s.path,
                            s.state === 'completed' ? 'done'
                                : s.state === 'resumable' ? 'resumable'
                                    : 'pending');
                    });
                    const resumable = (states || [])
                        .filter(s => s && s.state === 'resumable');
                    if (resumable.length > 0) {
                        ConsoleManager.log(
                            MSG.resumable_found(resumable.length), 'info');
                        resumable.forEach(s =>
                            ConsoleManager.log(`   ↺ ${s.stem}`, 'info'));
                    }
                } catch (e) {
                    console.warn('scan_resume_states failed:', e);
                }
            }

            let result = await pywebview.api.start_translation(options);

            // 后端预热互锁兜底（P1 批3 B.5）：后端拒启并带 warmup_loading
            // → 同样进入持有模式，终态后以同一快照重试启动
            if (result && result.warmup_loading) {
                await this._warmupHoldUntilRelease();
                result = await pywebview.api.start_translation(options);
            }

            // 已有终稿产物：needs_confirm 时弹确认框（D2026-0925-01 D6）
            if (result && result.needs_confirm) {
                const ok = await AppModal.confirm(
                    MSG.overwriteConfirm(result.existing || []));
                if (!ok) {
                    // 用户取消：静默返回，仅复位按钮/状态
                    this.state.isRunning = false;
                    AppState.isRunning = false;
                    FileListManager.updateButtons();
                    ProgressManager.setIndeterminate(false);
                    ProgressManager.setDot('idle');
                    this.setStatus(MSG.idle);
                    return;
                }
                options.force = true;
                result = await pywebview.api.start_translation(options);
            }

            if (result.success) {
                // 新任务新流：清空结构化活动流与差分状态（2.7.3 件⑧批 8b）
                try { ActivityStream.reset(); }
                catch (e) { console.warn('activity stream reset failed:', e); }
                // 显示链生命线先行：轮询启动不受打点异常影响（D2026-1006-01 件⑦）
                this.startStatusPolling();
                try {
                    ConsoleManager.log(MSG.translationStarted(result.pid), 'info');
                } catch (e) { console.warn('translationStarted log failed:', e); }
            } else {
                throw new Error(result.error || MSG.startFailed);
            }
        } catch (error) {
            ConsoleManager.log(MSG.translationErrorLog(error.message), 'error');
            ErrorHandler.show(MSG.translationErrorTitle, error.message);
            this._finish(MSG.error, 'err');
        }
    },

    async cancelTranslation() {
        try {
            const result = await pywebview.api.cancel_translation();
            if (result && result.success) {
                ConsoleManager.log(MSG.cancelledLog, 'warning');
                // 状态轮询会检测到进程退出并收尾；此处立即恢复按钮避免竞态窗口
                this._finish(MSG.cancelled);
            } else {
                ConsoleManager.log((result && result.error) || MSG.unknownError,
                    'warning');
            }
        } catch (error) {
            console.error('Error cancelling translation:', error);
        }
    },

    // P2-9（d1015-卡J）：收尾点色随终态收束（默认 idle；cancelled 等
    // 用户主动取消维持 idle，ok/warn/err 由调用方按终态传入）。注意：
    // TranslatorManager 无 setDot 方法，一律经 ProgressManager 转发。
    _finish(statusText, dotState = 'idle') {
        this.stopStatusPolling();
        this.state.isRunning = false;
        AppState.isRunning = false;
        FileListManager.updateButtons();
        ProgressManager.setIndeterminate(false);
        ProgressManager.setDot(dotState);
        this.setStatus(statusText);
    },

    // ============================================================
    // P1 G9 (c) 阻断持有模式（D2026-1008-02 批3）
    // ============================================================

    /**
     * 参数区容器级锁定/恢复（G9 方案 A）。锁定时记录每个控件的原 disabled
     * 值（恢复必须对称：锁了必恢复），恢复时逐一还原；容器加 .engine-locked
     * 样式类（dim+锁定态，style.css 承接）。范围=#tab-engine 内全部可交互
     * 控件；不含翻译页右侧开始/停止钮（refineStartBtn/refineCancelBtn——
     * 开始钮由持有逻辑单独管文案/禁用）。
     * @param {boolean} lock true=锁定 false=恢复
     * @param {Array<{el: HTMLElement, disabled: boolean}>} recorded 锁定时返回的清单（恢复时传入）
     * @returns {Array<{el: HTMLElement, disabled: boolean}>} 锁定时返回记录清单
     */
    _lockEngineControls(lock, recorded) {
        const page = document.getElementById('tab-engine');
        if (!page) return [];
        if (lock) {
            const list = [];
            page.querySelectorAll('button, input, select, textarea')
                .forEach(el => {
                    // 防御性排除：开始/停止钮若日后挪入引擎页也不得被本锁管
                    if (el.id === 'refineStartBtn'
                        || el.id === 'refineCancelBtn') return;
                    list.push({ el, disabled: el.disabled });
                    el.disabled = true;
                });
            page.classList.add('engine-locked');
            return list;
        }
        (recorded || []).forEach(({ el, disabled }) => {
            el.disabled = disabled;
        });
        page.classList.remove('engine-locked');
        return [];
    },

    /**
     * 预热持有等待（G9）：预热 loading 中阻断启动——参数区锁定+开始按钮
     * 倒计时（剩余=timeout-elapsed，每秒刷新），每 1s 轮询 warmup 状态桥。
     * 释放条件：终态（loaded/hot/failed）或 supported:false；超时（G10
     * timeout 值）；桥连续 N=3 次异常（G7 第三态：按预热已死放行）。
     * 超时/不可确认释放时先 refine_cancel_warmup（杀客户端+清状态+放行，
     * 防后端互锁兜底把翻译顶回持有死循环），再由调用方以点击时快照继续
     * 正常启动链（含后端既有门，不新增确认弹窗）。
     * @returns {Promise<boolean>} true=继续启动链 / false=中止（保留语义位）
     */
    async _warmupHoldUntilRelease() {
        let st = null;
        try {
            if (window.pywebview && pywebview.api
                && pywebview.api.refine_warmup_status) {
                st = await pywebview.api.refine_warmup_status();
            }
        } catch (e) { st = null; }
        if (!st || !st.supported || st.state !== 'loading') return true;

        // ---- 进入持有模式 ----
        ConsoleManager.log(MSG.warmupQueued, 'info');
        this._warmupHolding = true;
        const locked = this._lockEngineControls(true);
        const startBtns = [
            document.getElementById('refineStartBtn'),
            document.querySelector('[data-testid="btn-start-translate"]')
        ].filter(Boolean);
        const prevText = startBtns.length ? startBtns[0].textContent : '';
        startBtns.forEach((startBtn) => { startBtn.disabled = true; });
        const firstTimeout = Number(st.timeout) > 0 ? Number(st.timeout) : 300;
        // elapsed 与后端同源（首拍回带起流经秒数），倒计时基准对齐 G10
        const startedAtMs = Number(st.elapsed) > 0
            ? Date.now() - Number(st.elapsed) * 1000 : Date.now();
        let released = null;   // 'loaded'|'hot'|'failed'|'timeout'|'unknown'|'unsupported'
        let failStreak = 0;
        try {
            while (true) {
                await new Promise(r => setTimeout(r, 1000));
                const elapsedS = (Date.now() - startedAtMs) / 1000;
                let cur = null;
                try {
                    cur = await pywebview.api.refine_warmup_status();
                    failStreak = 0;
                } catch (e) {
                    failStreak += 1;
                    if (failStreak >= 3) { released = 'unknown'; break; }
                }
                if (cur) {
                    if (!cur.supported) { released = 'unsupported'; break; }
                    if (cur.state === 'loaded' || cur.state === 'hot'
                        || cur.state === 'failed') {
                        released = cur.state;
                        break;
                    }
                    if (cur.state !== 'loading') { released = 'failed'; break; }
                }
                const timeoutS = cur && Number(cur.timeout) > 0
                    ? Number(cur.timeout) : firstTimeout;
                if (elapsedS >= timeoutS) { released = 'timeout'; break; }
                // 倒计时文案（每秒刷新，剩余=timeout-elapsed）
                if (startBtns.length) {
                    const holdText =
                        MSG.warmupHoldBtn(Math.max(0, Math.ceil(timeoutS - elapsedS)));
                    startBtns.forEach((startBtn) => {
                        startBtn.disabled = true;   // 持有期间即便他处重排也保持锁定
                        startBtn.textContent = holdText;
                    });
                }
            }
        } finally {
            this._warmupHolding = false;
            this._lockEngineControls(false, locked);
            startBtns.forEach((startBtn) => {
                startBtn.textContent = prevText;
                startBtn.disabled = false;   // updateButtons 会按运行态再纠正
            });
            if (released === 'timeout' || released === 'unknown') {
                // G7 第三态/超时放行：杀客户端+清状态（后端互锁随之放行）
                try {
                    Promise.resolve(pywebview.api.refine_cancel_warmup())
                        .catch(() => {});
                } catch (e) { /* 桥不可达：后端兜底不阻塞放行 */ }
            }
            if (released === 'timeout') {
                ConsoleManager.log(MSG.warmupTimeout, 'warning');
            } else if (released === 'unknown') {
                ConsoleManager.log(MSG.warmupUnknown, 'warning');
            } else if (released === 'failed' || released === 'unsupported') {
                ConsoleManager.log(MSG.warmupFailed, 'warning');
            } else if (released === 'loaded' || released === 'hot') {
                ConsoleManager.log(MSG.warmupDone, 'success');
            }
        }
        return true;
    },

    // ---- Status polling ----

    startStatusPolling() {
        this.statusInterval = setInterval(async () => {
            try {
                const status = await pywebview.api.get_translation_status();

                // 状态栏：阶段名（current_stage）优先，叠加当前文件（current_file）
                let text = '';
                if (status.current_stage) text = status.current_stage;
                if (status.current_file &&
                    (!text || !status.current_file.includes(text))) {
                    text = text ? `${text} · ${status.current_file}` : status.current_file;
                }
                // 心跳超时且仍在运行：追加最近活动提示
                // （判定单点 heartbeatIsStale：优先后端 heartbeat_stale，
                // 旧后端回退本地算；秒数显示仍用 heartbeat_age）
                if (status.status === 'running' && heartbeatIsStale(status)) {
                    const secs = Math.round(status.heartbeat_age);
                    text = `${text || MSG.running}${MSG.still_running(secs)}`;
                }
                // 风险计数
                if (status.risk_count > 0) {
                    text = `${text || MSG.running}${MSG.risk_suffix(status.risk_count)}`;
                    // P2-9：运行中一旦有风险即降级琥珀（幂等，重复无副作用）
                    ProgressManager.setDot('warn');
                }
                if (text) this.setStatus(text);

                // 三态 chip 实时点亮（D2026-0930-09 批2 档1）：basename join，未命中的不回退
                if (status.files_status) {
                    FileListManager.applyStates(status.files_status);
                }

                // 结构化活动流（2.7.3 件⑧批 8b）：差分打点（阶段/文件/风险/
                // 错误/心跳/摘要）。风险打点已整体迁入 ActivityStream（Translator
                // 侧旧计数段删除）；防弹包裹，打点异常不拖垮 status 桥（件⑦
                // 显示链生命线口径）
                try { ActivityStream.update(status); }
                catch (e) { console.warn('activity stream update failed:', e); }

                if (status.progress !== undefined && status.progress > 0) {
                    ProgressManager.setIndeterminate(false);
                    this.setProgress(status.progress, status.current_stage,
                                     status.batch, status.batch_total);
                }

                if (status.status === 'completed') {
                    this.setProgress(100);
                    // P2-9：完成态点色收束——多数未译（有告警框）必归 warn，
                    // 防"绿点+告警框"矛盾；warning_level 告警归 warn；其余 ok
                    let dotState = 'ok';
                    if (status.untranslated_majority) {
                        dotState = 'warn';
                        ErrorHandler.show(MSG.untranslated_title,
                            MSG.untranslated_hint);
                    } else if (status.warning_level) {
                        dotState = 'warn';
                        const level = status.warning_level === 'critical'
                            ? MSG.level_critical : MSG.level_warning;
                        ConsoleManager.log(
                            MSG.completed_with_risks(level, status.risk_count || 0),
                            'warning');
                    } else {
                        ConsoleManager.log(MSG.completedLog, 'success');
                        ErrorHandler.showSuccess(MSG.completed_title, MSG.completed_detail);
                    }
                    if (typeof this.guideAutoDetect === 'function') this.guideAutoDetect();
                    this._finish(MSG.completed, dotState);
                    // P1 预热触发点①（D2026-1008-02 批3，G2 会话级完成=
                    // 整队列回 idle）：Console 一行 + 调预热（后端会话钩子
                    // 并发触发，后端桥内单飞+指纹去重）
                    ConsoleManager.log(MSG.warmupAfterQueue, 'info');
                    if (typeof window.__warmupMaybeStart === 'function') {
                        try { window.__warmupMaybeStart(); }
                        catch (e) { console.warn('warmup trigger failed:', e); }
                    }
                } else if (status.status === 'error') {
                    ConsoleManager.log(MSG.translationErrorLog(status.error), 'error');
                    ErrorHandler.show(MSG.translationFailedTitle,
                        status.error || MSG.unknownError);
                    this._finish(MSG.error, 'err');
                } else if (status.status === 'cancelled') {
                    this._finish(MSG.cancelled);
                }
            } catch (error) {
                console.error('Status poll error:', error);
            }

            // 原始日志通道与 status 桥解耦（D2026-1006-01 件⑦）：fetchLogs
            // 自带 try/catch，不随 status 每拍异常断流。
            this.fetchLogs();
        }, 1000);
    },

    stopStatusPolling() {
        if (this.statusInterval) {
            clearInterval(this.statusInterval);
            this.statusInterval = null;
        }
    },

    async fetchLogs() {
        try {
            const logs = await pywebview.api.get_translation_logs();
            if (logs && logs.length > 0) {
                logs.forEach(line => {
                    const cleanLine = line.replace(/\n$/, '');
                    if (cleanLine) {
                        ConsoleManager.appendRaw(cleanLine);
                    }
                });
            }
        } catch (error) {
            console.error('Error fetching logs:', error);
        }
    },

    setProgress(percent) {
        this.state.progress = percent;
        ProgressManager.setProgress(percent);
    },

    setStatus(text) {
        ProgressManager.setStatus(text);
    }
};

