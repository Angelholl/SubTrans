// ============================================================
// 校对页 UI 层（2.6.1 批 2a D2026-1002-09）。
// 硬约束：#tab-review 页内零 data-i18n（静态键 cap 零消耗），
// 文案全走本文件 REVIEW_MSG 独立键表；app.js 零改动
// （switchTab 通用机制自动纳新 tab；FileListManager 复用）。
// ============================================================

const REVIEW_MSG = {
    review_drop_title: '导入视频与字幕开始校对',
    review_drop_hint: '拖入视频（mp4 / mkv / webm / mov / avi）与字幕（.srt），或点击下方按钮选择',
    review_import_video: '导入视频',
    review_import_srt: '导入字幕',
    review_status_idle: '未导入',
    review_status_ready: '已就绪',
    review_status_busy: '处理中…',
    review_status_transcoding: '转码中…',
    review_status_error: '出错了',
    review_transcode_btn: '手动转码预览',
    review_transcode_estimating: '该编码需转码后预览',
    review_transcode_estimate: (s) => `预计转码约 ${s} 秒，点击按钮开始`,
    review_transcode_running: '转码进行中…',
    review_transcode_failed: '转码失败，请重试或手动转换格式',
    review_bad_encoding: '字幕文件编码无法识别（仅支持 UTF-8 / GBK），请另存为 UTF-8 后重试',
    review_api_not_ready: '接口未就绪，请稍后再试',
    review_media_error: '无法解码该媒体，请尝试手动转码',
    review_srt_loaded: (n, enc) => `字幕已载入：${n} 条（${enc}）`,
};

// 状态条管理器（D2026-1002-08 定案：四态 + 确定百分比 + 不定进度动画）。
// 四态枚举外的 state 一律 console.error 且不渲染（契约护栏）。
function makeStatusManager(ids) {
    const bar = document.getElementById(ids.bar);
    const dot = document.getElementById(ids.dot);
    const label = document.getElementById(ids.label);
    const fill = document.getElementById(ids.fill);
    const percent = bar ? bar.querySelector('.review-status-percent') : null;
    const STATES = ['idle', 'ready', 'busy', 'error'];
    return {
        setState(opt) {
            if (!bar || !dot || !label || !fill) { return; }
            const st = opt && opt.state;
            if (STATES.indexOf(st) < 0) {
                console.error('[review] 非法状态枚举：', st);
                return;
            }
            bar.style.display = '';
            bar.classList.remove('review-st-idle', 'review-st-ready',
                                 'review-st-busy', 'review-st-error');
            bar.classList.add('review-st-' + st);
            const key = opt.labelKey;
            const val = REVIEW_MSG[key];
            label.textContent = (typeof val === 'string') ? val : (key || '');
            const progress = opt.progress;
            // D2026-1002-08 正交表：state 定视觉、progress 定进度——
            // indeterminate 流光仅属 busy 态（批 2a 黑盒缺陷回归：
            // idle 态曾误显 30% 流光）；idle/ready/error 恒空轨
            if (st !== 'busy') {
                fill.style.width = '0%';
                bar.classList.remove('indeterminate');
                fill.removeAttribute('aria-valuenow');
                if (percent) { percent.style.display = 'none'; }
            } else if (progress === null || progress === undefined) {
                fill.style.width = '30%';
                bar.classList.add('indeterminate');
                fill.removeAttribute('aria-valuenow');
                if (percent) { percent.style.display = 'none'; }
            } else {
                bar.classList.remove('indeterminate');
                const pct = Math.max(0, Math.min(100, Number(progress) || 0));
                fill.style.width = pct + '%';
                fill.setAttribute('aria-valuenow', String(Math.round(pct)));
                if (percent) {
                    percent.textContent = Math.round(pct) + '%';
                    percent.style.display = '';
                }
            }
        },
        hide() {
            if (bar) { bar.style.display = 'none'; }
        },
    };
}

const ReviewUI = {
    REVIEW_VIDEO_EXTS: ['.mp4', '.mkv', '.webm', '.mov', '.avi'],
    REVIEW_SRT_EXTS: ['.srt'],

    _videoPath: null,
    _hasVideo: false,
    _hasSrt: false,
    _blocks: [],
    _probe: null,
    _pollTimer: null,
    _jumpQueue: [],
    _barShown: false,

    // app.js 顶层 fileUrlOf 在 IIFE 内不可复用，语义拷贝
    // （逐段 encodeURIComponent，兼容空格/中文路径）
    fileUrlOf(p) {
        return 'file:///' + String(p).replace(/\\/g, '/').split('/')
            .map(encodeURIComponent).join('/');
    },

    _bridge() {
        return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
    },

    init() {
        this._status = makeStatusManager({
            bar: 'reviewStatusBar', dot: 'reviewStatusDot',
            label: 'reviewStatusLabel', fill: 'reviewProgressFill',
        });
        this._injectTexts();
        this._bindDropzone();
        this._bindTranscode();
        this._bindTabWatcher();
    },

    _injectTexts() {
        // 页内零 data-i18n：全部静态文案由此注入（#tab-review 容器已由
        // HTML 注释标注；data-i18n 悬空钉只认 app.js MSG，本表独立）
        const dz = document.getElementById('reviewDropzone');
        if (dz) {
            const title = dz.querySelector('.dz-title');
            const hint = dz.querySelector('.dz-hint');
            if (title) { title.textContent = REVIEW_MSG.review_drop_title; }
            if (hint) { hint.textContent = REVIEW_MSG.review_drop_hint; }
        }
        document.querySelectorAll('.review-import-btn').forEach((btn) => {
            btn.textContent = (btn.dataset.kind === 'video')
                ? REVIEW_MSG.review_import_video : REVIEW_MSG.review_import_srt;
        });
        const tcBtn = document.getElementById('reviewTranscodeBtn');
        if (tcBtn) { tcBtn.textContent = REVIEW_MSG.review_transcode_btn; }
    },

    _bindDropzone() {
        const dz = document.getElementById('reviewDropzone');
        if (!dz) { return; }
        dz.addEventListener('click', (e) => {
            const btn = e.target.closest('.review-import-btn');
            if (btn) { this._pick(btn.dataset.kind); }
        });
        // 拖拽高亮纯视觉（OS 级 drop 由 main.py DOMEventHandler 承接）
        dz.addEventListener('dragover', () => dz.classList.add('drag-over'));
        dz.addEventListener('dragleave', () => dz.classList.remove('drag-over'));
        dz.addEventListener('drop', () => dz.classList.remove('drag-over'));
    },

    _bindTranscode() {
        const btn = document.getElementById('reviewTranscodeBtn');
        if (btn) { btn.addEventListener('click', () => this._startTranscode()); }
    },

    _bindTabWatcher() {
        // 简案：每次 side-tab 点击后一个 tick 检查 active tab → 挂/卸 no-aside
        document.querySelectorAll('.side-tab-btn').forEach((btn) => {
            btn.addEventListener('click', () => setTimeout(() => this._syncWorkbench(), 0));
        });
        this._syncWorkbench();
    },

    _syncWorkbench() {
        const wb = document.querySelector('.workbench');
        if (!wb) { return; }
        const active = document.querySelector('.side-tab-btn.active');
        const tab = active ? active.dataset.tab : '';
        wb.classList.toggle('no-aside', tab === 'tab-review');
        // 首次进入校对页即亮状态条（idle 态提示未导入）
        if (tab === 'tab-review' && !this._barShown && this._status) {
            this._barShown = true;
            this._status.setState({ state: 'idle', labelKey: 'review_status_idle' });
        }
    },

    _pick(kind) {
        const api = this._bridge();
        if (!api) {
            this._status.setState({ state: 'error', labelKey: 'review_api_not_ready' });
            return;
        }
        const call = (kind === 'video') ? api.refine_review_pick_media()
                                        : api.refine_review_pick_srt();
        Promise.resolve(call).then((r) => {
            if (!r) { return; }
            if (r.success && r.path) {
                if (kind === 'video') { this.setVideoPath(r.path); }
                else { this.setSrtPath(r.path); }
            } else if (!r.cancelled && r.error) {
                console.warn('[review] pick failed:', r.error);
                this._status.setState({ state: 'error', labelKey: 'review_status_error' });
            }
        }).catch((err) => console.error('[review] pick error:', err));
    },

    // OS 拖入分流（main.py on_drop_event 放宽后缀后统一入口）：
    // tab-review 激活 → 按后缀各自消费；否则原样转发翻译页既有路径
    onDroppedFiles(paths) {
        const list = (paths || []).map(String);
        const active = document.querySelector('.side-tab-btn.active');
        const tab = active ? active.dataset.tab : '';
        if (tab !== 'tab-review') {
            if (typeof FileListManager !== 'undefined' && FileListManager.addDroppedFiles) {
                FileListManager.addDroppedFiles(list);
            }
            return;
        }
        const isVideo = (p) => this.REVIEW_VIDEO_EXTS.some(
            (e) => p.toLowerCase().endsWith(e));
        const isSrt = (p) => this.REVIEW_SRT_EXTS.some(
            (e) => p.toLowerCase().endsWith(e));
        list.filter(isVideo).forEach((p) => this.setVideoPath(p));
        list.filter(isSrt).forEach((p) => this.setSrtPath(p));
    },

    setVideoPath(path) {
        this._videoPath = path || null;
        this._hasVideo = false;
        const api = this._bridge();
        if (!api) {
            this._status.setState({ state: 'error', labelKey: 'review_api_not_ready' });
            return;
        }
        this._status.setState({ state: 'busy', labelKey: 'review_status_busy' });
        Promise.resolve(api.refine_review_probe_media(path)).then((r) => {
            this._probe = r || null;
            const st = r && r.state;
            const row = document.querySelector('.review-transcode-row');
            const btn = document.getElementById('reviewTranscodeBtn');
            const hint = document.querySelector('.review-transcode-hint');
            if (st === 'direct') {
                if (row) { row.style.display = 'none'; }
                this._showVideo(this.fileUrlOf(path));
                this._hasVideo = true;
                this._refreshReadiness();
            } else if (st === 'clip-audio') {
                this._showVideo(null);
                if (row) { row.style.display = ''; }
                if (btn) { btn.style.display = ''; }
                if (hint) {
                    hint.style.display = '';
                    hint.textContent = REVIEW_MSG.review_transcode_estimating;
                }
                this._status.setState({ state: 'busy', labelKey: 'review_status_busy' });
            } else {
                this._showVideo(null);
                if (row) { row.style.display = ''; }
                if (btn) { btn.style.display = ''; }
                if (hint) { hint.style.display = 'none'; }
                console.warn('[review] probe error:', r && r.error);
                this._status.setState({ state: 'error', labelKey: 'review_media_error' });
            }
        }).catch((err) => {
            console.error('[review] probe error:', err);
            this._status.setState({ state: 'error', labelKey: 'review_media_error' });
        });
    },

    _startTranscode() {
        const api = this._bridge();
        if (!api) {
            this._status.setState({ state: 'error', labelKey: 'review_api_not_ready' });
            return;
        }
        this._status.setState({ state: 'busy', labelKey: 'review_status_busy', progress: null });
        Promise.resolve(api.refine_review_start_transcode(this._videoPath)).then((r) => {
            if (!r || !r.success) {
                console.warn('[review] transcode rejected:', r && r.error);
                this._status.setState({ state: 'error', labelKey: 'review_status_error' });
                return;
            }
            if (r.cached) {
                this._showVideo(this.fileUrlOf(r.path));
                this._hasVideo = true;
                this._refreshReadiness();
                return;
            }
            const hint = document.querySelector('.review-transcode-hint');
            if (hint && r.estimated_s) {
                hint.textContent = REVIEW_MSG.review_transcode_estimate(r.estimated_s);
            }
            this._status.setState({ state: 'busy', labelKey: 'review_transcode_running' });
            this._pollTranscode();
        }).catch((err) => {
            console.error('[review] transcode error:', err);
            this._status.setState({ state: 'error', labelKey: 'review_transcode_failed' });
        });
    },

    _pollTranscode() {
        const api = this._bridge();
        if (!api) { return; }
        if (this._pollTimer) { clearInterval(this._pollTimer); }
        this._pollTimer = setInterval(() => {
            Promise.resolve(api.refine_review_transcode_status()).then((s) => {
                if (!s) { return; }
                if (s.running) {
                    this._status.setState({ state: 'busy',
                                            labelKey: 'review_status_transcoding',
                                            progress: s.percent });
                    return;
                }
                clearInterval(this._pollTimer);
                this._pollTimer = null;
                if (s.error) {
                    console.warn('[review] transcode failed:', s.error);
                    this._status.setState({ state: 'error',
                                            labelKey: 'review_transcode_failed' });
                    return;
                }
                if (s.path) {
                    this._showVideo(this.fileUrlOf(s.path));
                    this._hasVideo = true;
                    this._refreshReadiness();
                }
            }).catch(() => {});
        }, 800);
    },

    setSrtPath(path) {
        const api = this._bridge();
        if (!api) {
            this._status.setState({ state: 'error', labelKey: 'review_api_not_ready' });
            return;
        }
        Promise.resolve(api.refine_review_load_srt(path)).then((r) => {
            if (r && r.success) {
                this._hasSrt = true;
                this._blocks = r.blocks || [];
                console.log('[review]', REVIEW_MSG.review_srt_loaded(r.count, r.encoding));
                this._refreshReadiness();
            } else {
                console.warn('[review] srt load failed:', r && r.error);
                this._status.setState({ state: 'error', labelKey: 'review_bad_encoding' });
            }
        }).catch((err) => {
            console.error('[review] srt load error:', err);
            this._status.setState({ state: 'error', labelKey: 'review_bad_encoding' });
        });
    },

    // 文件就绪判定（批 2a 契约）：video 与 srt 均 set → ready 覆盖先前态；
    // 单件就绪也亮 ready（状态条语义=已导入件可用）
    _refreshReadiness() {
        if (this._hasVideo || this._hasSrt) {
            this._status.setState({ state: 'ready', labelKey: 'review_status_ready' });
        }
    },

    // N3 跳转入队（批 3 联动预留；契约={timestamp,label,source}，空实现）
    enqueueJump(jump) {
        this._jumpQueue.push(jump);
        console.debug('[review] jump enqueued', JSON.stringify(jump));
    },

    _showVideo(url) {
        const v = document.getElementById('videoReviewPlayer');
        const wrap = document.querySelector('.review-player-wrap');
        if (!v) { return; }
        if (url) {
            v.src = url;
            v.style.display = '';
            if (wrap) { wrap.style.display = ''; }
        } else {
            v.removeAttribute('src');
            v.style.display = 'none';
            if (wrap) { wrap.style.display = 'none'; }
        }
    },
};

document.addEventListener('DOMContentLoaded', () => ReviewUI.init());
