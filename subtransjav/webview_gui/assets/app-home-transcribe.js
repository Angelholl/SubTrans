// ============================================================
// 首页转录卡（d1102-卡B，D2026-1102-03）：首页新增转录模块，
// 仿 review.js 校对页转录卡三段范式（选媒体 / CT2 门控 / 启动+轮询）。
// 硬约束：页内零 data-i18n，文案全走 window.REVIEW_MSG（review.js
// 单源暴露）与 MSG（app-msg.js 专属键），零键值字面量复制；
// 他页发起的转录不建第二轮询，首页仅做 status 快照渲染。
// ============================================================

const HomeTranscribe = {
    _pollStop: null,        // 仅本卡发起的转录自建轮询；句柄挂管理器防泄漏
    _ct2Status: null,
    _ct2Pending: false,
    _videoPath: null,

    _bridge() {
        // d1103：桥访问单源共享核
        return TranscribeCore.bridge();
    },

    init() {
        const card = document.getElementById('homeTranscribeCard');
        if (!card || this._inited) { return; }
        this._inited = true;   // 双兜底入口防重复绑定
        const title = card.querySelector('.home-transcribe-title');
        const media = document.getElementById('homeTranscribeMedia');
        const pick = document.getElementById('homeTranscribePickBtn');
        const start = document.getElementById('homeTranscribeStartBtn');
        const dual = document.getElementById('homeTranscribeDualPass');
        const install = document.getElementById('homeTranscribeInstall');
        if (title) { title.textContent = MSG.flowNodeTranscribe; }
        if (media) {
            media.textContent = MSG.homeTranscribeEmpty;
        }
        if (pick) {
            pick.textContent = MSG.homeTranscribePick;
            pick.addEventListener('click', () => this.pickMedia());
        }
        if (start) {
            start.textContent = (window.REVIEW_MSG || {})
                .review_transcribe_start_btn;
            start.addEventListener('click', () => this.beginTranscribe());
        }
        if (dual && dual.parentElement) {
            const text = dual.parentElement
                .querySelector('.review-transcribe-pass-text');
            if (text) {
                text.textContent = (window.REVIEW_MSG || {})
                    .review_transcribe_dualpass;
            }
        }
        if (install) {
            install.addEventListener('click', () => this._openAsrSettings());
        }
        this.refreshCt2Status();
        this.snapshotRender();
        this._wrapHomeOverviewHook();
    },

    // d1102-卡B：切回首页 tab 时对概览条 __homeOverviewRefresh 链挂快照
    // 渲染（app-tabs.js TAB_HOOKS 零改动；自建轮询进行中则轮询面为准）。
    _wrapHomeOverviewHook() {
        const prev = window.__homeOverviewRefresh;
        const self = this;
        window.__homeOverviewRefresh = () => {
            if (typeof prev === 'function') {
                try { prev(); } catch (e) { /* 概览条刷新失败不阻断 */ }
            }
            try { self.snapshotRender(); } catch (e) { /* 快照失败不阻断 */ }
        };
    },

    _openAsrSettings() {
        // B2 垫片入口（d1103：下沉共享核，本卡仅适配器）
        TranscribeCore.openAsrSettings();
    },

    pickMedia() {
        const api = this._bridge();
        const status = document.getElementById('homeTranscribeStatus');
        if (!api) {
            if (status) {
                status.textContent = (window.REVIEW_MSG || {})
                    .review_api_not_ready;
            }
            return;
        }
        // cancelled 静默；选媒体桥经共享核（d1103）
        TranscribeCore.pickMedia(api).then((r) => {
            if (!r || r.cancelled || !r.success || !r.path) { return; }
            this.setMediaPath(r.path);
            this.refreshCt2Status();
        }).catch((err) => { console.error('[home-transcribe] pick:', err); });
    },

    setMediaPath(path) {
        this._videoPath = path;
        const media = document.getElementById('homeTranscribeMedia');
        if (media) {
            media.textContent = (window.REVIEW_MSG || {})
                .review_transcribe_media(path);
            media.title = path;
            media.classList.remove('muted');
        }
        this._gateStart();
    },

    // CT2 门控（探测归一化经共享核；渲染即重探、结果不作缓存短路）
    refreshCt2Status() {
        const line = document.getElementById('homeTranscribeCt2');
        if (!line) { return; }
        const api = this._bridge();
        const m = window.REVIEW_MSG || {};
        if (!api) {
            line.textContent = m.review_transcribe_ct2_unknown;
            return;
        }
        line.textContent = m.review_transcribe_ct2_checking;
        if (this._ct2Pending) { return; }
        this._ct2Status = null;   // 旧探测结果作废，防开始钮按陈旧态门控
        this._ct2Pending = true;
        TranscribeCore.probeCt2(api).then((s) => {
            this._ct2Pending = false;
            this._ct2Status = s;
            this._renderCt2Status();
        });
    },

    _renderCt2Status() {
        const line = document.getElementById('homeTranscribeCt2');
        const install = document.getElementById('homeTranscribeInstall');
        if (!line) { return; }
        const m = window.REVIEW_MSG || {};
        const s = this._ct2Status || {};
        if (s.installed && s.model_present) {
            line.textContent = m.review_transcribe_ct2_ready(s.model || '');
            if (install) { install.style.display = 'none'; }
        } else if (s.probe_failed) {
            // 探测失败不阻断（后端转录失败面会如实回报）
            line.textContent = m.review_transcribe_ct2_unknown;
            if (install) { install.style.display = 'none'; }
        } else {
            line.textContent = s.installed
                ? m.review_transcribe_ct2_model
                : m.review_transcribe_ct2_missing;
            if (install) { install.style.display = ''; }
        }
        this._gateStart();
    },

    // 门控：选了媒体且（引擎就绪或探测失败放行）才启用开始钮
    _gateStart() {
        const start = document.getElementById('homeTranscribeStartBtn');
        if (!start) { return; }
        start.disabled = !(this._videoPath
            && TranscribeCore.ct2Ready(this._ct2Status || {}));
    },

    beginTranscribe() {
        const api = this._bridge();
        const status = document.getElementById('homeTranscribeStatus');
        const m = window.REVIEW_MSG || {};
        if (!api) {
            if (status) { status.textContent = m.review_api_not_ready; }
            return;
        }
        if (!this._videoPath) { return; }
        const s = this._ct2Status || {};
        if (TranscribeCore.ct2HardMissing(s)) {
            if (status) { status.textContent = m.review_transcribe_ct2_missing; }
            return;
        }
        const dual = document.getElementById('homeTranscribeDualPass');
        const passes = (dual && dual.checked) ? 2 : 1;
        if (status) {
            status.textContent = m.review_transcribe_busy;
        }
        // d1103：start 桥下沉共享核
        TranscribeCore.startTranscribe(api, this._videoPath, passes).then((r) => {
            if (!r || !r.success) {
                console.warn('[home-transcribe] rejected:', r && r.error);
                // 拒绝文案单源——后端 strings.py msg() 文案经桥回传直出
                if (status) {
                    status.textContent = (r && r.error)
                        || m.review_transcribe_failed;
                }
                return;
            }
            this._pollTranscribe();
        }).catch((err) => {
            console.error('[home-transcribe] error:', err);
            if (status) { status.textContent = m.review_transcribe_failed; }
        });
    },

    _stopPoll() {
        // d1103：清轮委托共享核 stopper
        if (this._pollStop) { this._pollStop(); }
        this._pollStop = null;
    },

    // 800ms 轮询（骨架经共享核：payload 校验、连续 miss 上限 5、终态
    // 停表；离开首页 tab 不停表，句柄挂管理器，重复 start 前先清）
    _pollTranscribe() {
        const api = this._bridge();
        if (!api) { return; }
        this._stopPoll();
        const m = window.REVIEW_MSG || {};
        const status = document.getElementById('homeTranscribeStatus');
        const refresh = () => {
            if (window.__homeOverviewRefresh) {
                window.__homeOverviewRefresh();
            }
        };
        this._pollStop = TranscribeCore.startPolling(api, {
            onTick: (st) => {
                if (status) {
                    status.textContent = m.review_transcribe_busy
                        + (typeof st.percent === 'number'
                            ? ` ${st.percent}%` : '');
                }
            },
            onSettled: (st) => {
                if (st.error) {
                    console.warn('[home-transcribe] failed:', st.error);
                    if (status) {
                        status.textContent = m.review_transcribe_failed;
                    }
                    refresh();
                    return;
                }
                if (st.path) {
                    const name = TranscribeCore.doneName(st.path);
                    if (status) {
                        status.textContent =
                            (m.review_transcribe_done || ((n) => n))(name);
                    }
                    refresh();
                }
            },
            onMiss: () => {
                console.warn('[home-transcribe] status anomalous, stop polling');
                if (status) { status.textContent = m.review_transcribe_failed; }
                refresh();
            },
        });
    },

    // 他页发起的转录在首页的呈现：只读快照三分渲染（照抄 app-init.js
    // refreshTranscribeNode 的 idle/running/done 三态；不建第二个轮询）
    snapshotRender() {
        if (this._pollStop) { return; }   // 本卡轮询进行中：轮询面为准
        const api = this._bridge();
        const status = document.getElementById('homeTranscribeStatus');
        if (!api || !status) { return; }
        const m = window.REVIEW_MSG || {};
        Promise.resolve(TranscribeCore.statusOnce(api)).then((st) => {
            if (!st || (typeof st.running !== 'boolean'
                        && !st.error && !st.path)) { return; }
            if (st.running) {
                status.textContent = m.review_transcribe_busy;
            } else if (st.error) {
                status.textContent = m.review_transcribe_failed;
            } else if (st.path) {
                const name = String(st.path).split(/[\\/]/).pop();
                status.textContent =
                    (m.review_transcribe_done || ((n) => n))(name);
            }
        }).catch(() => { /* 快照失败静默（首页常态为无任务 idle） */ });
    },
};

// init 挂 DOMContentLoaded/pywebviewready 双兜底（仿 app-eval-reports.js 范式）
window.addEventListener('pywebviewready', () => {
    try { HomeTranscribe.init(); } catch (e) { /* 不阻断 */ }
});
document.addEventListener('DOMContentLoaded', () => {
    // pywebviewready 先于 DOMContentLoaded 的时序兜底
    if (window.pywebview && window.pywebview.api) {
        try { HomeTranscribe.init(); } catch (e) { /* 不阻断 */ }
    }
});
