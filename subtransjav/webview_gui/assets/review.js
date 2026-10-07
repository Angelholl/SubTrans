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
    // F2 错误分型（D2026-1007-02 C3）：probe 实证编解码探测通过
    // （codec_probe=true）仍 error code 4 → 真编解码/通道异常专用文案；
    // 其余路径（ffprobe 缺席乐观 direct 等）维持中性 review_media_error
    review_media_codec_error: '该媒体通道编码异常，浏览器无法解码播放，请尝试手动转码',
    review_srt_loaded: (n, enc) => `字幕已载入：${n} 条（${enc}）`,
    // ---- 批 2b（D2026-1002-10）：校对编辑 ----
    review_list_empty: '字幕未载入有效条目：请导入 .srt 字幕',
    review_search_placeholder: '搜索文本/时间轴（Enter）',
    review_locate_btn: '定位',
    review_page_info: (cur, total) => `${cur}/${total}`,
    review_save_btn: '保存',
    review_saveas_btn: '另存为',
    // C4 锁字（逐字冻结，静态钉断言）：
    review_confirm_overwrite: '保存将按 1..N 重编号 + UTF-8 重写；行数/时间轴不变。确认覆盖？',
    review_saveas_confirm_exists: '目标文件已存在，将按同一规则备份并覆盖。确认？',
    review_dirty_hint: '有未保存修改',
    review_edit_hint: '双击编辑文本；Enter 提交，Shift+Enter 换行，Esc 取消（时间轴只读）',
    review_save_ok: (n) => `已保存 ${n} 条（UTF-8 重写）`,
    review_save_failed: (m) => `保存失败：${m}`,
    // ---- 批 3（D2026-1002-11）：疑点段联动 / ASR 入口 ----
    review_det_load_btn: '载入疑点段',
    review_asr_btn: 'ASR 对照',
    review_det_summary: (total, stale) => (stale > 0
        ? `已载入 ${total} 条疑点，${stale} 处位置失效` : `已载入 ${total} 条疑点`),
    review_det_seek_btn: '转跳',
    review_det_listen_btn: '试听',
    review_det_confirm_btn: '确认已修',
    review_det_skip_btn: '跳过',
    review_det_no_srt: '先导入 .srt 字幕，方可转跳/试听',
    review_det_no_save: '判定标记仅本会话内生效，不落盘',
    review_asr_card: 'ASR 语音对照为可选能力（依赖本机自备 whisper，非必需）：'
        + '推荐 whisper-large-v2，自备落位 ~/.cache/whisper 或数据根 models/asr，'
        + '配好后可在 API 与模型选择页旁的「ASR 与词典」页启用 ASR 验证。',
    review_asr_goto: '前往 ASR 与词典页',
    // ---- 批 4（D2026-1002-12）：审计④载入 dirty 守卫 ----
    review_load_dirty_confirm: '当前有未保存的编辑，载入新字幕将丢弃这些修改。确认继续？',
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
    let current = null;   // 批 3 技术债 d：暴露当前态供 _markDirty 延迟判定
    return {
        setState(opt) {
            if (!bar || !dot || !label || !fill) { return; }
            const st = opt && opt.state;
            current = st;
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
            if (typeof val === 'function') {
                label.textContent = val.apply(null, opt.labelArgs || []);
            } else {
                label.textContent = (typeof val === 'string') ? val : (key || '');
            }
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
        state() { return current; },
    };
}

const ReviewUI = {
    REVIEW_VIDEO_EXTS: ['.mp4', '.mkv', '.webm', '.mov', '.avi'],
    REVIEW_SRT_EXTS: ['.srt'],

    _videoPath: null,
    _srtPath: null,
    _hasVideo: false,
    _hasSrt: false,
    _blocks: [],
    _loadedCount: null,
    _probe: null,
    _pollTimer: null,
    _jumpQueue: [],
    _barShown: false,
    // ---- 批 2b（D2026-1002-10）：列表/编辑/联动状态 ----
    _currentIndex: -1,
    _dirty: false,
    _pageMode: 'full',      // 'full' ≤800 行全量；'paged' 801-2000+ 分段
    _pageSize: 500,
    _page: 0,
    _pageCount: 1,
    _followPaused: false,
    _followTimer: null,
    _autoScroll: false,
    _lastTuTs: 0,
    _editingIdx: null,
    _editingRow: null,
    _guardAllowTab: null,
    // ---- 批 3（D2026-1002-11）：疑点段/ASR/dirty 延迟 ----
    _detections: [],
    _listenTimer: null,
    _dirtyPending: false,

    // app.js 顶层 fileUrlOf 在 IIFE 内不可复用，语义拷贝
    // （逐段 encodeURIComponent，兼容空格/中文路径）
    fileUrlOf(p) {
        return 'file:///' + String(p).replace(/\\/g, '/').split('/')
            .map(encodeURIComponent).join('/');
    },

    _bridge() {
        return (window.pywebview && window.pywebview.api) ? window.pywebview.api : null;
    },

    // 批 3 技术债 j：active tab 读取收敛
    getActiveTab() {
        const active = document.querySelector('.side-tab-btn.active');
        return active ? active.dataset.tab : '';
    },

    // 批 3 技术债 h：桥调用统一包装（桥在位检查 + 异常/error 兜底渲染）。
    // 失败时 setState(errLabelKey || status_error) 并返回 null；特殊流
    //（转码轮询 interval、确认弹窗链）不强行套用。
    _call(promiseFactory, errLabelKey) {
        const api = this._bridge();
        if (!api) {
            this._status.setState({ state: 'error', labelKey: 'review_api_not_ready' });
            return Promise.resolve(null);
        }
        return Promise.resolve().then(promiseFactory).catch((err) => {
            console.error('[review] call error:', err);
            this._status.setState({ state: 'error',
                                    labelKey: errLabelKey || 'review_status_error' });
            return null;
        });
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
        this._bindPlayer();
        this._bindList();
        this._bindSearch();
        this._bindLocate();
        this._bindSave();
        this._bindTabGuard();
        this._bindDetections();
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
        // 批 2b：列表工具条/保存组文案注入
        const search = document.getElementById('reviewSearchInput');
        if (search) { search.placeholder = REVIEW_MSG.review_search_placeholder; }
        const locate = document.getElementById('reviewLocateBtn');
        if (locate) { locate.textContent = REVIEW_MSG.review_locate_btn; }
        const save = document.getElementById('reviewSaveBtn');
        if (save) { save.textContent = REVIEW_MSG.review_save_btn; }
        const saveas = document.getElementById('reviewSaveAsBtn');
        if (saveas) { saveas.textContent = REVIEW_MSG.review_saveas_btn; }
        // 批 3：疑点面板/ASR 卡文案注入
        const detLoad = document.getElementById('reviewDetLoadBtn');
        if (detLoad) { detLoad.textContent = REVIEW_MSG.review_det_load_btn; }
        const asrBtn = document.getElementById('reviewAsrBtn');
        if (asrBtn) { asrBtn.textContent = REVIEW_MSG.review_asr_btn; }
        const asrText = document.querySelector('.review-asr-card-text');
        if (asrText) { asrText.textContent = REVIEW_MSG.review_asr_card; }
        const asrGoto = document.querySelector('.review-asr-goto');
        if (asrGoto) { asrGoto.textContent = REVIEW_MSG.review_asr_goto; }
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
        const tab = this.getActiveTab();
        wb.classList.toggle('no-aside', tab === 'tab-review');
        // 首次进入校对页即亮状态条（idle 态提示未导入）
        if (tab === 'tab-review' && !this._barShown && this._status) {
            this._barShown = true;
            this._status.setState({ state: 'idle', labelKey: 'review_status_idle' });
        }
    },

    _pick(kind) {
        this._call(() => (kind === 'video')
            ? this._bridge().refine_review_pick_media()
            : this._bridge().refine_review_pick_srt(),
        'review_status_error').then((r) => {
            if (!r) { return; }
            if (r.success && r.path) {
                if (kind === 'video') { this.setVideoPath(r.path); }
                else { this.setSrtPath(r.path); }
            } else if (!r.cancelled && r.error) {
                console.warn('[review] pick failed:', r.error);
                this._status.setState({ state: 'error', labelKey: 'review_status_error' });
            }
        });
    },

    // OS 拖入分流（main.py on_drop_event 放宽后缀后统一入口）：
    // tab-review 激活 → 按后缀各自消费；否则原样转发翻译页既有路径
    onDroppedFiles(paths) {
        const list = (paths || []).map(String);
        const tab = this.getActiveTab();
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
        this._call(() => api.refine_review_probe_media(path),
                   'review_media_error').then((r) => {
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
                    this._flushDirtyPending();
                    return;
                }
                if (s.path) {
                    this._showVideo(this.fileUrlOf(s.path));
                    this._hasVideo = true;
                    this._refreshReadiness();
                    this._flushDirtyPending();
                }
            }).catch(() => {});
        }, 800);
    },

    async setSrtPath(path) {
        // 批 4 审计④：载入新字幕前 dirty 守卫——未保存修改/行内编辑中
        // 时直接覆盖 _blocks 会丢用户编辑；确认才继续，取消即中止。
        // （pick 对话框 / 拖放分流统一经本入口，守卫单点全覆盖）
        if (this._dirty || this._editingIdx !== null) {
            const ok = await AppModal.confirm(REVIEW_MSG.review_load_dirty_confirm);
            if (!ok) { return; }
        }
        this._call(() => this._bridge().refine_review_load_srt(path),
                   'review_bad_encoding').then((r) => {
            if (!r) { return; }
            if (r.success) {
                this._srtPath = path || null;
                this._hasSrt = true;
                this._blocks = r.blocks || [];
                this._loadedCount = r.count;   // C8：前端行数守卫基线
                this._dirty = false;
                console.log('[review]', REVIEW_MSG.review_srt_loaded(r.count, r.encoding));
                this._setupList();
                this._refreshReadiness();
            } else {
                // 批 3 技术债 i：error_key 优先查 REVIEW_MSG，回退 error 文本
                console.warn('[review] srt load failed:', r.error);
                if (r.error_key && REVIEW_MSG[r.error_key]) {
                    this._status.setState({ state: 'error', labelKey: r.error_key });
                } else {
                    this._status.setState({ state: 'error',
                                            labelKey: 'review_bad_encoding' });
                }
            }
        });
    },

    // ================================================================
    // 批 2b（D2026-1002-10）：列表渲染三档 / 播放联动 / 行内编辑 / 保存流
    // ================================================================

    // D4 性能三档：≤800 行全量渲染；801-2000 分段（500 行/页）+页码；
    // >2000 分段同上——虚拟化兜底预案=性能口径（首屏 ≤300ms / 滚动
    // rAF ≥50fps / 定位 ≤100ms）真机不达标时启用窗口化渲染（本批不实现）。
    _setupList() {
        const tools = document.querySelector('.review-list-tools');
        const wrap = document.getElementById('reviewListWrap');
        if (tools) { tools.style.display = ''; }
        if (wrap) { wrap.style.display = ''; }
        this._pageMode = this._blocks.length > 800 ? 'paged' : 'full';
        this._pageCount = (this._pageMode === 'paged')
            ? Math.ceil(this._blocks.length / this._pageSize) : 1;
        this._page = 0;
        this._currentIndex = -1;
        this._renderPage();
    },

    _renderPage() {
        const wrap = document.getElementById('reviewListWrap');
        if (!wrap) { return; }
        wrap.textContent = '';
        if (!this._blocks.length) {
            const eg = document.createElement('div');
            eg.className = 'empty-guide';
            eg.textContent = REVIEW_MSG.review_list_empty;
            wrap.appendChild(eg);
            this._renderPager();
            return;
        }
        const frag = document.createDocumentFragment();
        const start = (this._pageMode === 'paged') ? this._page * this._pageSize : 0;
        const end = (this._pageMode === 'paged')
            ? Math.min(start + this._pageSize, this._blocks.length)
            : this._blocks.length;
        for (let i = start; i < end; i++) {
            frag.appendChild(this._buildRow(i));
        }
        wrap.appendChild(frag);
        this._renderPager();
    },

    _buildRow(idx) {
        const b = this._blocks[idx];
        const row = document.createElement('div');
        row.className = 'review-row';
        row.dataset.idx = String(idx);   // 稳定 ID=blocks 数组下标（0 基）
        const no = document.createElement('span');
        no.className = 'review-row-no';
        no.textContent = String(idx + 1);
        const tm = document.createElement('span');
        tm.className = 'review-timing-readonly';
        tm.title = REVIEW_MSG.review_edit_hint;
        tm.textContent = b.timing || '';
        const tx = document.createElement('span');
        tx.className = 'review-row-text';
        tx.textContent = b.text || '';
        row.appendChild(no);
        row.appendChild(tm);
        row.appendChild(tx);
        if (idx === this._currentIndex) { row.classList.add('review-row-current'); }
        return row;
    },

    _renderPager() {
        const pager = document.getElementById('reviewPager');
        if (!pager) { return; }
        pager.textContent = '';
        if (this._pageMode !== 'paged' || this._pageCount <= 1) {
            pager.style.display = 'none';
            return;
        }
        pager.style.display = '';
        for (let p = 0; p < this._pageCount; p++) {
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.className = 'review-page-btn' + (p === this._page ? ' active' : '');
            btn.dataset.page = String(p);
            btn.textContent = String(p + 1);
            pager.appendChild(btn);
        }
        const info = document.createElement('span');
        info.className = 'review-pager-info';
        info.textContent = REVIEW_MSG.review_page_info(this._page + 1, this._pageCount);
        pager.appendChild(info);
    },

    _bindPlayer() {
        const v = document.getElementById('videoReviewPlayer');
        if (!v) { return; }
        v.addEventListener('timeupdate', () => this._onTimeUpdate(v));
        // 批 4 审计③c：解码/加载失败可读提示（半截件 cache、编码异常
        // 兜底；_showVideo(null) removeAttribute 触发的无源 error 忽略）
        v.addEventListener('error', () => {
            if (!v.getAttribute('src')) { return; }
            const code = (v.error && v.error.code) || 0;
            console.error('[review] video error:', code || 'unknown');
            // F2 分型（D2026-1007-02 C3）：仅 ffprobe 编解码探测实证通过
            // （codec_probe=true）仍 code 4 才示「通道异常」文案；其余
            // （ffprobe 缺席乐观 direct 等）维持中性文案（转码引导保留）
            if (this._probe && this._probe.codec_probe === true
                    && code === 4) {
                this._status.setState({ state: 'error',
                                        labelKey: 'review_media_codec_error' });
                return;
            }
            this._status.setState({ state: 'error',
                                    labelKey: 'review_media_error' });
        });
    },

    _onTimeUpdate(v) {
        const now = performance.now();
        if (now - this._lastTuTs < 265) { return; }   // 节流基线（spike B 口径 265.5ms）
        this._lastTuTs = now;
        if (!this._blocks.length) { return; }
        const idx = this._findBlockIndex(v.currentTime * 1000);
        if (idx < 0 || idx === this._currentIndex) { return; }
        this._currentIndex = idx;
        this._highlightCurrent();
    },

    // 二分查行：start_ms<=t<end_ms；块间隙/越界找不到 → -1（保持原状）
    _findBlockIndex(t) {
        const bs = this._blocks;
        if (!bs.length || t < bs[0].start_ms) { return -1; }
        let lo = 0;
        let hi = bs.length - 1;
        while (lo <= hi) {
            const mid = (lo + hi) >> 1;
            if (t < bs[mid].start_ms) { hi = mid - 1; }
            else if (t >= bs[mid].end_ms) { lo = mid + 1; }
            else { return mid; }
        }
        return -1;
    },

    _highlightCurrent() {
        const wrap = document.getElementById('reviewListWrap');
        if (!wrap) { return; }
        const prev = wrap.querySelector('.review-row-current');
        if (prev) { prev.classList.remove('review-row-current'); }
        if (this._currentIndex < 0) { return; }
        // C6：跨页自动翻页
        if (this._pageMode === 'paged') {
            const page = Math.floor(this._currentIndex / this._pageSize);
            if (page !== this._page) {
                this._page = page;
                this._renderPage();
            }
        }
        const row = wrap.querySelector('.review-row[data-idx="' + this._currentIndex + '"]');
        if (row) {
            row.classList.add('review-row-current');
            if (!this._followPaused) {
                this._autoScroll = true;   // 程序滚动豁免 scroll 暂停判定
                row.scrollIntoView({ block: 'nearest' });
            }
        }
    },

    _pauseFollow() {
        this._followPaused = true;
        if (this._followTimer) { clearTimeout(this._followTimer); }
        // C6：2s 内无滚动事件 → 恢复跟随（恢复后 currentIndex 变才滚，逻辑不变）
        this._followTimer = setTimeout(() => { this._followPaused = false; }, 2000);
    },

    _bindList() {
        const wrap = document.getElementById('reviewListWrap');
        if (!wrap) { return; }
        // 行点击 → seek（C2 裁定：直接 currentTime=start_ms/1000，无偏移）
        wrap.addEventListener('click', (e) => {
            const row = e.target.closest('.review-row');
            if (!row) { return; }
            if (row.dataset.idx === String(this._editingIdx)) { return; }
            const idx = Number(row.dataset.idx);
            const b = this._blocks[idx];
            const v = document.getElementById('videoReviewPlayer');
            if (!b || !v) { return; }
            v.currentTime = b.start_ms / 1000;
        });
        // 行双击 → 行内编辑（单击留给 seek 跳转）
        wrap.addEventListener('dblclick', (e) => {
            const row = e.target.closest('.review-row');
            if (!row) { return; }
            this._beginEdit(Number(row.dataset.idx), row);
        });
        // 手动滚动暂停跟随（wheel=用户意图；scroll 经 _autoScroll 豁免程序滚动）
        wrap.addEventListener('wheel', () => this._pauseFollow(), { passive: true });
        wrap.addEventListener('scroll', () => {
            if (this._autoScroll) { this._autoScroll = false; return; }
            this._pauseFollow();
        }, { passive: true });
        // 页码条委托
        const pager = document.getElementById('reviewPager');
        if (pager) {
            pager.addEventListener('click', (e) => {
                const btn = e.target.closest('.review-page-btn');
                if (!btn) { return; }
                const p = Number(btn.dataset.page);
                if (!isNaN(p) && p !== this._page) {
                    this._page = p;
                    this._renderPage();
                }
            });
        }
    },

    _beginEdit(idx, row) {
        if (this._editingIdx !== null) { this._commitEdit(); }
        if (isNaN(idx) || !this._blocks[idx] || !row) { return; }
        this._editingIdx = idx;
        this._editingRow = row;
        const tx = row.querySelector('.review-row-text');
        if (!tx) { return; }
        row.classList.add('review-row-editing');
        const ta = document.createElement('textarea');
        ta.className = 'review-edit-input';
        ta.value = this._blocks[idx].text || '';
        ta.rows = Math.min(6, ta.value.split('\n').length + 1);
        tx.textContent = '';
        tx.appendChild(ta);
        ta.addEventListener('keydown', (ev) => {
            if (ev.key === 'Escape') {
                ev.stopPropagation();
                this._cancelEdit();
            } else if (ev.key === 'Enter' && !ev.shiftKey) {
                // Enter 提交；Shift+Enter 换行（textarea 默认，不拦截）
                ev.preventDefault();
                this._commitEdit();
            }
        });
        // 失焦即提交（裁定：与 Enter 等效，避免丢输入）
        ta.addEventListener('blur', () => {
            if (this._editingIdx !== null) { this._commitEdit(); }
        });
        ta.focus();
    },

    _cancelEdit() {
        const idx = this._editingIdx;
        const row = this._editingRow;
        this._editingIdx = null;
        this._editingRow = null;
        if (row) {
            row.classList.remove('review-row-editing');
            const tx = row.querySelector('.review-row-text');
            if (tx) { tx.textContent = this._blocks[idx] ? this._blocks[idx].text : ''; }
        }
    },

    _commitEdit() {
        const idx = this._editingIdx;
        const row = this._editingRow;
        if (idx === null) { return; }
        const ta = row ? row.querySelector('.review-edit-input') : null;
        const val = ta ? ta.value : (this._blocks[idx] ? this._blocks[idx].text : '');
        this._editingIdx = null;
        this._editingRow = null;
        this._blocks[idx].text = val;
        if (row) {
            row.classList.remove('review-row-editing');
            const tx = row.querySelector('.review-row-text');
            if (tx) { tx.textContent = val; }
        }
        this._markDirty();
    },

    _markDirty() {
        if (this._dirty) { return; }
        this._dirty = true;
        // C6：不新设状态位——dirty=state:'ready'+labelKey 表达；
        // 技术债 d：busy 态不覆盖 busy 视觉，置 _dirtyPending 由 busy 结束回调补显
        if (this._status.state && this._status.state() === 'busy') {
            this._dirtyPending = true;
            return;
        }
        if (this._hasVideo || this._hasSrt) {
            this._status.setState({ state: 'ready', labelKey: 'review_dirty_hint' });
        }
    },

    // busy 结束后补显 dirty 提示（技术债 d 配套；_dirty 已 true 故不走 _markDirty）
    _flushDirtyPending() {
        if (!this._dirtyPending) { return; }
        this._dirtyPending = false;
        this._status.setState({ state: 'ready', labelKey: 'review_dirty_hint' });
    },

    _bindSearch() {
        const input = document.getElementById('reviewSearchInput');
        if (!input) { return; }
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                this._search(input.value);
            }
        });
    },

    // 搜索：blocks 内 text/timing 不区分大小写匹配；命中行跳所在页+高亮
    //（口径：定位 ≤100ms，命中计数 console 留档）
    _search(q) {
        const query = String(q || '').trim().toLowerCase();
        const wrap = document.getElementById('reviewListWrap');
        if (!wrap || !query) { return; }
        const t0 = performance.now();
        const hits = [];
        for (let i = 0; i < this._blocks.length; i++) {
            const b = this._blocks[i];
            if (((b.text || '').toLowerCase().indexOf(query) >= 0) ||
                ((b.timing || '').toLowerCase().indexOf(query) >= 0)) {
                hits.push(i);
            }
        }
        if (!hits.length) {
            console.log('[review] search: 0 hits');
            return;
        }
        const first = hits[0];
        if (this._pageMode === 'paged') {
            const page = Math.floor(first / this._pageSize);
            if (page !== this._page) {
                this._page = page;
                this._renderPage();
            }
        }
        hits.forEach((i) => {
            const inPage = (this._pageMode !== 'paged') ||
                (i >= this._page * this._pageSize && i < (this._page + 1) * this._pageSize);
            if (!inPage) { return; }
            const row = wrap.querySelector('.review-row[data-idx="' + i + '"]');
            if (row) { row.classList.add('review-row-hit'); }
        });
        const row0 = wrap.querySelector('.review-row[data-idx="' + first + '"]');
        if (row0) { row0.scrollIntoView({ block: 'nearest' }); }
        console.log('[review] search:', hits.length, 'hits in',
                    (performance.now() - t0).toFixed(1), 'ms');
    },

    _bindLocate() {
        const btn = document.getElementById('reviewLocateBtn');
        if (!btn) { return; }
        btn.addEventListener('click', () => {
            if (this._currentIndex < 0) { return; }
            this._followPaused = false;   // 定位=强制恢复跟随
            this._highlightCurrent();
            const row = document.getElementById('reviewListWrap')
                .querySelector('.review-row[data-idx="' + this._currentIndex + '"]');
            if (row) { row.scrollIntoView({ block: 'center' }); }
        });
    },

    _bindSave() {
        const save = document.getElementById('reviewSaveBtn');
        const saveas = document.getElementById('reviewSaveAsBtn');
        if (save) { save.addEventListener('click', () => this._save()); }
        if (saveas) { saveas.addEventListener('click', () => this._saveAs()); }
    },

    async _save() {
        if (this._editingIdx !== null) { this._commitEdit(); }   // 先提交编辑中行
        if (!this._srtPath || !this._blocks.length) { return; }
        if (this._loadedCount !== null && this._blocks.length !== this._loadedCount) {
            // C8 前端防御：行数不变式（编辑不改行数），漂移即拒绝
            console.error('[review] 行数与载入时不一致，拒绝保存');
            return;
        }
        const ok = await AppModal.confirm(REVIEW_MSG.review_confirm_overwrite);
        if (!ok) { return; }
        await this._doSave(this._srtPath);
    },

    async _saveAs() {
        if (this._editingIdx !== null) { this._commitEdit(); }
        const api = this._bridge();
        if (!api) {
            this._status.setState({ state: 'error', labelKey: 'review_api_not_ready' });
            return;
        }
        if (!this._blocks.length) { return; }
        const defaultName = this._srtPath
            ? this._srtPath.split(/[\\/]/).pop() : '校对.srt';
        const r = await Promise.resolve(api.refine_review_pick_save_path(defaultName));
        if (!r || !r.success || !r.path) { return; }   // 取消静默
        const target = String(r.path);
        if (this._srtPath && target === this._srtPath) {
            await this._save();   // 同路径 → 走覆盖流
            return;
        }
        // 批 3 技术债 c：后端删 src_path 死形参，新签名 (blocks, target_path)
        const c = await Promise.resolve(
            api.refine_review_saveas_srt(this._blocks, target));
        if (c && c.success) {
            this._srtPath = target;   // 另存后当前路径切换到新件
            this._dirty = false;
            console.log('[review]', REVIEW_MSG.review_save_ok(c.count));
            this._status.setState({ state: 'ready', labelKey: 'review_save_ok',
                                    labelArgs: [c.count] });
            return;
        }
        if (c && c.exists) {
            const ok = await AppModal.confirm(REVIEW_MSG.review_saveas_confirm_exists);
            if (ok) { await this._doSave(target); }
            return;
        }
        const m = (c && c.error) || 'unknown';
        console.warn('[review] saveas failed:', m);
        this._status.setState({ state: 'error', labelKey: 'review_save_failed',
                                labelArgs: [m] });
    },

    async _doSave(path) {
        const api = this._bridge();
        if (!api) {
            this._status.setState({ state: 'error', labelKey: 'review_api_not_ready' });
            return;
        }
        try {
            const r = await Promise.resolve(
                api.refine_review_save_srt(path, this._blocks));
            if (r && r.success) {
                if (r.backup_path) { console.log('[review] backup:', r.backup_path); }
                if (path !== this._srtPath) { this._srtPath = path; }
                this._dirty = false;
                console.log('[review]', REVIEW_MSG.review_save_ok(r.count));
                this._status.setState({ state: 'ready', labelKey: 'review_save_ok',
                                        labelArgs: [r.count] });
            } else {
                const m = (r && r.error) || 'unknown';
                console.warn('[review] save failed:', m);
                this._status.setState({ state: 'error', labelKey: 'review_save_failed',
                                        labelArgs: [m] });
            }
        } catch (err) {
            console.error('[review] save error:', err);
            this._status.setState({ state: 'error', labelKey: 'review_save_failed',
                                    labelArgs: [String(err)] });
        }
    },

    // C7 TAB dirty 守卫：capture 阶段拦截切页（app.js 零改动）。
    // AppModal.confirm 异步 → 同步 preventDefault+stopImmediatePropagation
    // 后确认再 btn.click() 重放；确认放行时 dirty/_blocks 保留在内存
    //（编辑不丢，切回校对页还在）。窗口关闭守卫明示不做：未保存编辑
    // 仅存内存，原文件与 .bak.srt 均安全（丢失边界声明，见批清单 C7）。
    _bindTabGuard() {
        document.addEventListener('click', (e) => {
            const target = e.target;
            const btn = target && target.closest ? target.closest('.side-tab-btn') : null;
            if (!btn) { return; }
            // 一次性放行（批 2b 黑盒缺陷回归：确认重放的 click 时 dirty 仍
            // 为 true，须放行一次防重复确认循环）；先判标志再判 dirty，
            // 放行一次即清，防其他按钮误放行
            if (this._guardAllowTab && this._guardAllowTab === btn) {
                this._guardAllowTab = null;
                return;
            }
            if (!this._dirty) { return; }
            if (btn.dataset.tab === 'tab-review') { return; }
            e.preventDefault();
            e.stopImmediatePropagation();
            AppModal.confirm(REVIEW_MSG.review_dirty_hint +
                '离开将保留编辑于内存（未写盘），确认切换？').then((ok) => {
                if (ok) {
                    this._guardAllowTab = btn;   // 先置标志再重放
                    btn.click();
                }
            });
        }, true);
    },

    // 文件就绪判定（批 2a 契约）：video 与 srt 均 set → ready 覆盖先前态；
    // 单件就绪也亮 ready（状态条语义=已导入件可用）
    _refreshReadiness() {
        if (this._hasVideo || this._hasSrt) {
            this._status.setState({ state: 'ready', labelKey: 'review_status_ready' });
        }
        // 技术债 d 盲区修补（code-review 批 3）：所有 ready 路径统一补显
        // pending 的 dirty 提示（probe direct 分支等不经 _pollTranscode）
        this._flushDirtyPending();
    },

    // N3 跳转入队（批 3 联动预留；契约={timestamp,label,source}，空实现）
    enqueueJump(jump) {
        this._jumpQueue.push(jump);
        console.debug('[review] jump enqueued', JSON.stringify(jump));
    },

    // ===== 疑点段面板（批 3 D2026-1002-11）：自主直载导读 items（带 timing）=====
    // 数据源裁定（D2026-1002-11 §四）：guide items 为唯一时间戳载体；确认/跳过
    // 仅会话内标记不落盘（REVIEW_MSG.review_det_no_save 明示）。
    _autoGuidePath() {
        // 弱提示自动发现：srt 同目录 {stem}_质量报告导读.json；实际存在性由
        // 后端 load_detections 校验（失败走文件对话框兜底）
        if (!this._srtPath) { return null; }
        const i = this._srtPath.lastIndexOf('.');
        const stem = i > 0 ? this._srtPath.slice(0, i) : this._srtPath;
        return stem + '_质量报告导读.json';
    },

    // 同 app.js timingToSeconds 语义（HH:MM:SS[,.]mmm --> HH:MM:SS[,.]mmm，
    // 容忍 ,/. 毫秒分隔），禁止只改一处造成漂移。返回 [startMs, endMs]。
    _parseTimingMs(timing) {
        const m = String(timing || '').match(
            /(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{1,3})/);
        if (!m) { return null; }
        const n = m.slice(1).map(Number);
        return [((n[0] * 60 + n[1]) * 60 + n[2]) * 1000 + n[3],
                ((n[4] * 60 + n[5]) * 60 + n[6]) * 1000 + n[7]];
    },

    _matchDetections() {
        // 位置失效态闭合（D2026-1002-10 C8 留坑）：timing 区间与 blocks 区间
        // 重叠→记 blockIdx（跳转走 blocks.start_ms 原生）；无 blocks 或无重叠
        // →stale/pending
        const dets = this._detections || [];
        const hasBlocks = (this._blocks || []).length > 0;
        for (const d of dets) {
            d.blockIdx = null; d.stale = false; d.pending = !hasBlocks;
            const ms = this._parseTimingMs(d.timing);
            if (!ms) { d.stale = hasBlocks; continue; }
            d.startMs = ms[0]; d.endMs = ms[1];
            if (!hasBlocks) { continue; }
            let hit = null;
            for (let i = 0; i < this._blocks.length; i++) {
                const b = this._blocks[i];
                if (b.start_ms < d.endMs && d.startMs < b.end_ms) { hit = i; break; }
            }
            if (hit === null) { d.stale = true; } else { d.blockIdx = hit; }
        }
    },

    _loadDetections() {
        const api = this._bridge();
        if (!api) {
            this._status.setState({ state: 'error', labelKey: 'review_api_not_ready' });
            return;
        }
        const attempt = (p) => Promise.resolve()
            .then(() => api.refine_review_load_detections(p))
            .then((r) => {
                if (!r || !r.success) { return false; }
                this._detections = r.detections || [];
                this._matchDetections();
                this._renderDetections();
                return true;
            }).catch(() => false);
        const auto = this._autoGuidePath();
        attempt(auto).then((ok) => {
            if (ok) { return null; }
            // 自动发现失败→文件对话框兜底（refine_pick_guide_json 既有 API）
            return Promise.resolve(api.refine_pick_guide_json()).then((picked) => {
                if (!picked || !picked.success) { return null; }
                return attempt(picked.path);
            });
        });
    },

    _renderDetections() {
        const wrap = document.getElementById('reviewDetectionsWrap');
        const list = document.getElementById('reviewDetList');
        const summary = document.querySelector('.review-det-summary');
        if (!wrap || !list) { return; }
        const dets = this._detections || [];
        wrap.style.display = dets.length ? '' : 'none';
        if (!dets.length) { return; }
        const stale = dets.filter((d) => d.stale).length;
        if (summary) {
            summary.style.display = '';
            summary.textContent = REVIEW_MSG.review_det_summary(dets.length, stale);
            summary.title = REVIEW_MSG.review_det_no_save;
        }
        const esc = (s) => String(s == null ? '' : s)
            .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
        list.textContent = '';
        dets.forEach((d, i) => {
            const row = document.createElement('div');
            row.className = 'review-det-row' + (d.stale ? ' review-det-stale' : '');
            row.dataset.idx = String(i);
            const noSrt = d.pending;
            const noSeek = d.pending || d.stale;   // 位置失效态：不崩不跳（D2026-1002-11 §一.2）
            const acts = [['seek', REVIEW_MSG.review_det_seek_btn],
                          ['listen', REVIEW_MSG.review_det_listen_btn],
                          ['confirm', REVIEW_MSG.review_det_confirm_btn],
                          ['skip', REVIEW_MSG.review_det_skip_btn]];
            row.innerHTML =
                '<span class="review-det-cat">' + esc(d.category) + '</span>' +
                '<span class="review-det-timing">' + esc(d.timing) + '</span>' +
                '<span class="review-det-msg">' + esc(d.message) + '</span>' +
                ((d.source_excerpt || d.current_text) ?
                    '<span class="review-det-excerpt">' +
                    esc([d.current_text, d.source_excerpt].filter(Boolean).join(' / ')) +
                    '</span>' : '') +
                '<span class="review-det-acts">' +
                acts.map((a) => '<button type="button" class="btn btn-ghost btn-sm review-det-act"' +
                    ' data-act="' + a[0] + '"' +
                    ((a[0] === 'seek' || a[0] === 'listen') && noSeek ?
                        ' disabled title="' + REVIEW_MSG.review_det_no_srt + '"' : '') +
                    '>' + a[1] + '</button>').join('') +
                '</span>';
            list.appendChild(row);
        });
    },

    _applyJump(det) {
        // 跳转用匹配 blocks.start_ms 原生（D2026-1002-11 裁定：timing 解析
        // 仅用于匹配+试听区间，避免双时钟源）；位置失效态不崩不跳
        const v = document.getElementById('videoReviewPlayer');
        if (!v || !det || det.stale) { return; }
        const ms = (det.blockIdx != null && this._blocks[det.blockIdx])
            ? this._blocks[det.blockIdx].start_ms : det.startMs;
        if (ms == null) { return; }
        v.currentTime = ms / 1000;
        if (det.blockIdx != null) {
            this._currentIndex = det.blockIdx;
            this._highlightCurrent();
        }
    },

    _listen(det) {
        const v = document.getElementById('videoReviewPlayer');
        if (!v || !det || det.stale || det.endMs == null) { return; }
        const startMs = (det.blockIdx != null && this._blocks[det.blockIdx])
            ? this._blocks[det.blockIdx].start_ms : det.startMs;
        if (startMs == null) { return; }
        v.currentTime = startMs / 1000;
        v.play().catch(() => {});
        if (this._listenTimer) { clearTimeout(this._listenTimer); }
        this._listenTimer = setTimeout(() => v.pause(),
                                       Math.max(300, det.endMs - startMs));
    },

    _bindDetections() {
        const load = document.getElementById('reviewDetLoadBtn');
        if (load) { load.addEventListener('click', () => this._loadDetections()); }
        const list = document.getElementById('reviewDetList');
        if (list) {
            list.addEventListener('click', (e) => {
                const act = e.target.closest('.review-det-act');
                if (!act) { return; }
                const row = act.closest('.review-det-row');
                const det = (this._detections || [])[Number(row && row.dataset.idx)];
                if (!det) { return; }
                if (act.dataset.act === 'seek') { this._applyJump(det); }
                if (act.dataset.act === 'listen') { this._listen(det); }
                if (act.dataset.act === 'confirm' || act.dataset.act === 'skip') {
                    // 会话内标记（互斥）+console 留痕；不落盘（review_det_no_save 明示）
                    const mark = act.dataset.act === 'confirm' ? 'confirmed' : 'skipped';
                    det.mark = mark;
                    row.classList.toggle('review-det-confirmed', mark === 'confirmed');
                    row.classList.toggle('review-det-skipped', mark === 'skipped');
                    console.log('[review] detection', mark, JSON.stringify({
                        idx: row.dataset.idx, timing: det.timing, category: det.category }));
                }
            });
        }
        const asrBtn = document.getElementById('reviewAsrBtn');
        if (asrBtn) {
            asrBtn.addEventListener('click', () => {
                const card = document.querySelector('.review-asr-card');
                if (card) {
                    card.style.display = getComputedStyle(card).display !== 'none' ? 'none' : '';
                }
            });
        }
        const goto = document.querySelector('.review-asr-goto');
        if (goto) {
            // switchTab 在 app.js IIFE 内未挂全局（D2026-1002-11 裁定）——
            // 程序化 click 走真实 handler 链
            goto.addEventListener('click', () => {
                // 2.6.3 批C（D2026-1003-01 P4 IA 重排）：ASR 管理迁独立页
                // tab-asrdict，跳转锚随改
                const b = document.querySelector('.side-tab-btn[data-tab="tab-asrdict"]');
                if (b) { b.click(); }
            });
        }
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
