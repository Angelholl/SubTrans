// ============================================================
// 转录共享核（d1103 抽公共模块）：校对页（review.js）与首页转录卡
// （app-home-transcribe.js）的桥调用/CT2 探测归一化/轮询骨架单源。
// 只承载与页面无关的协议面；渲染与终态动作留在各消费方（回调注入）。
// 轮询契约：800ms 间隔；异常 payload（空/无 running 布尔/非 running
// 却无产出无错误）连续 POLL_MAX_MISS 次即停轮并回调 onMiss；非
// running 无条件停轮进 onSettled（transcode 先例：worker 在 running
// 落 False 之前已写定 error/path，非终态窗口不存在）。
// ============================================================

const TranscribeCore = {
    POLL_INTERVAL_MS: 800,
    POLL_MAX_MISS: 5,

    bridge() {
        return (window.pywebview && window.pywebview.api)
            ? window.pywebview.api : null;
    },

    // B2 垫片入口：设置组四页并入 hub 后统一经 openSettingsOverlay
    openAsrSettings() {
        if (typeof openSettingsOverlay === 'function') {
            openSettingsOverlay('asrdict');
            return;
        }
        const b = document.querySelector('[data-settings-domain="asrdict"]');
        if (b) { b.click(); }
    },

    // CT2 探测（渲染即重探口径，结果不作缓存短路）：归一化为
    // ct2 对象或 { probe_failed: true }（探测失败不阻断，后端转录
    // 失败面会如实回报）
    probeCt2(api) {
        return Promise.resolve(api.refine_asr_status())
            .then((r) => (r && r.success && r.ct2)
                ? r.ct2 : { probe_failed: true })
            .catch(() => ({ probe_failed: true }));
    },

    // CT2 探测编排单源（B3 抽共享，D2026-1104-01）：渲染即重探＋pending
    // 防重入＋旧结果作废，两页逐字同构段收编。host＝{_ct2Pending,
    // _ct2Status} 容器（各页实例态原位复用）；line＝状态行元素（可 null）；
    // render＝探测完成后的各页渲染回调（install/start 钮面差异留在页内）。
    refreshCt2Flow(host, api, line, render) {
        if (!line) { return; }
        const m = window.REVIEW_MSG || {};
        if (!api) {
            line.textContent = m.review_transcribe_ct2_unknown;
            return;
        }
        line.textContent = m.review_transcribe_ct2_checking;
        if (host._ct2Pending) { return; }
        host._ct2Status = null;   // 旧探测结果作废，防开始钮按陈旧态门控
        host._ct2Pending = true;
        this.probeCt2(api).then((s) => {
            host._ct2Pending = false;
            host._ct2Status = s;
            render();
        });
    },

    // 启动+轮询编排单源（B3 抽共享，D2026-1104-01）：busy→start→拒绝/异常
    // →reset→poll 控制流收编；渲染面经 hooks 注入（两页 setState 与
    // textContent 差异留在页内）。返回 stopper（轮询句柄）。
    startAndPollFlow(api, { path, passes, maxMiss, hooks }) {
        const m = window.REVIEW_MSG || {};
        const h = hooks || {};
        if (h.onBusy) { h.onBusy(); }
        return this.startTranscribe(api, path, passes).then((r) => {
            if (!r || !r.success) {
                console.warn('[transcribe-core] rejected:', r && r.error);
                if (h.onRejected) { h.onRejected((r && r.error) || ''); }
                return null;
            }
            if (h.onStarted) { h.onStarted(); }
            return this.startPolling(api, {
                onTick: (st) => { if (h.onTick) { h.onTick(st); } },
                onSettled: (st) => {
                    if (st.error) {
                        console.warn('[transcribe-core] failed:', st.error);
                        if (h.onFailed) { h.onFailed(st.error); }
                        if (h.onRefresh) { h.onRefresh(); }
                        return;
                    }
                    if (st.path) { if (h.onDone) { h.onDone(st); } }
                },
                onMiss: () => {
                    console.warn('[transcribe-core] status anomalous, stop polling');
                    if (h.onFailed) { h.onFailed(''); }
                    if (h.onRefresh) { h.onRefresh(); }
                },
            }, maxMiss);
        }).catch((err) => {
            console.error('[transcribe-core] error:', err);
            if (h.onStartError) { h.onStartError(err); }
            return null;
        });
    },

    // 门控口径：引擎就绪或探测失败放行
    ct2Ready(s) {
        return !!(s && s.installed && s.model_present)
            || !!(s && s.probe_failed);
    },
    ct2HardMissing(s) {
        return !!(s && s.installed === false && !s.probe_failed);
    },

    pickMedia(api) {
        return Promise.resolve(api.refine_review_pick_media());
    },
    startTranscribe(api, path, passes) {
        return Promise.resolve(
            api.refine_review_start_transcribe(path, passes));
    },
    statusOnce(api) {
        return Promise.resolve(api.refine_review_transcribe_status());
    },

    // 异常 payload：空响应 / running 非布尔 / 非 running 却既无产出
    // 也无错误（后端零值快照误配 start 成功）
    isBadPayload(st) {
        return !st || typeof st.running !== 'boolean'
            || (!st.running && !st.error && !st.path);
    },

    doneName(path) { return String(path).split(/[\\/]/).pop(); },

    // 轮询骨架：onTick(st) running 态每 tick；onSettled(st) 终态一次；
    // onMiss() 连续异常达上限一次；返回 stop()。maxMiss 可覆写默认值
    //（校对页传 REVIEW_POLL_MAX_MISS 常量保持钉面）。
    startPolling(api, handlers, maxMiss) {
        const cap = maxMiss || this.POLL_MAX_MISS;
        let miss = 0;
        let timer = null;
        const stop = () => {
            if (timer) { clearInterval(timer); }
            timer = null;
        };
        const missTick = () => {
            miss += 1;
            if (miss < cap) { return; }
            stop();
            if (handlers.onMiss) { handlers.onMiss(); }
        };
        timer = setInterval(() => {
            this.statusOnce(api).then((st) => {
                if (this.isBadPayload(st)) { missTick(); return; }
                miss = 0;
                if (st.running) {
                    if (handlers.onTick) { handlers.onTick(st); }
                    return;
                }
                stop();
                if (handlers.onSettled) { handlers.onSettled(st); }
            }).catch(() => { missTick(); });
        }, this.POLL_INTERVAL_MS);
        return stop;
    },
};
