// ============================================================
// Console Management
// 2.7.3 件⑧批 8b（D2026-1006-01）：显示层 500 行环形裁剪 + 会话内全量
// `_lines`（定版 D4：裁剪仅显示层，导出/复制走全量数组）
// ============================================================
// 五轮（D2026-1010-01，零 data-i18n）：原始日志弹窗标题
const RAWLOG_MODAL_TITLE = '原始日志（本轮全量）';

const ConsoleManager = {
    _lines: [],
    _MAX_DOM_LINES: 500,

    init() {
        document.getElementById('clearConsoleBtn').addEventListener('click', () => this.clear());

        // Console 折叠开关（语义=收起/展开底部抽屉，d1102-件C）
        const collapseBtn = document.getElementById('consoleCollapseBtn');
        if (collapseBtn) {
            collapseBtn.setAttribute('aria-label', MSG.console_collapse);
            collapseBtn.addEventListener('click', () => {
                if (typeof ConsoleDrawer !== 'undefined') ConsoleDrawer.close();
            });
        }

        // 导出/复制按钮（i18n 冻结：文案 JS 填，HTML 零 data-i18n）
        const exportBtn = document.getElementById('exportConsoleBtn');
        if (exportBtn) {
            exportBtn.textContent = MSG.export_log;
            exportBtn.addEventListener('click', () => this.exportLog());
        }
        const copyBtn = document.getElementById('copyConsoleBtn');
        if (copyBtn) {
            copyBtn.textContent = MSG.copy_log;
            copyBtn.addEventListener('click', () => this.copyLog(copyBtn));
        }

        this._initRawLogToggle();
        if (typeof ConsoleDrawer !== 'undefined') ConsoleDrawer.init();
    },

    // ---- 原始日志（五轮 D2026-1010-01：弹窗化，内联展开退场）----
    // 内联展开受 Console 区 380px 上限挤压无法下翻（owner 实证），点击
    // 开关改为打开 AppModal 大卡承载 _lines 全量缓冲；#consoleOutput 保留
    // 为隐藏 DOM 承载（log/appendRaw 仍写 DOM + 显示层裁剪，契约零破坏）

    // 卡2（D2026-1010-01 三轮）：折叠期新行未读计数（弹窗/抽屉打开态豁免）
    _rawLogUnread: 0,
    _rawLogError: false,

    _bumpRawLogUnread(type) {
        if (AppModal._kind === 'rawlog') return;   // 弹窗打开期不计数
        if (typeof ConsoleDrawer !== 'undefined' && ConsoleDrawer.isOpen()) {
            return;                                // 抽屉展开期日志可见，不计数
        }
        this._rawLogUnread += 1;
        if (type === 'error') this._rawLogError = true;
        if (typeof ConsoleDrawer !== 'undefined') ConsoleDrawer.renderCapsule();
    },

    // 打开抽屉/弹窗即视为已读（未读计数与 error 徽标清零）
    clearUnread() {
        this._rawLogUnread = 0;
        this._rawLogError = false;
        if (typeof ConsoleDrawer !== 'undefined') ConsoleDrawer.renderCapsule();
    },

    // 弹窗打开期间新行实时追加（等宽列表尾随+滚底，500 行显示层同款裁剪）
    _liveRawLogLine(text, type = '') {
        if (AppModal._kind !== 'rawlog') return;
        const list = document.querySelector('#appModal .rawlog-view');
        if (!list) return;
        const line = document.createElement('div');
        line.className = 'console-line' + (type ? ' ' + type : '');
        line.textContent = text;
        list.appendChild(line);
        while (list.children.length > this._MAX_DOM_LINES) {
            list.removeChild(list.firstChild);
        }
        list.scrollTop = list.scrollHeight;
    },

    openRawLogModal() {
        AppModal.rawLog({
            title: RAWLOG_MODAL_TITLE,
            lines: this._lines.slice(),
        });
        this.clearUnread();
    },

    _initRawLogToggle() {
        const toggle = document.getElementById('rawLogToggleBtn');
        const output = document.getElementById('consoleOutput');
        if (!toggle || !output) return;
        toggle.textContent = MSG.raw_log_toggle;
        // d1102-件C：Console 已入底部抽屉，原始日志承载恢复可见（抽屉内
        // 显示最近行；全量仍走 rawLogToggle 的 AppModal.rawLog 弹窗）。
        output.style.display = '';
        toggle.addEventListener('click', () => this.openRawLogModal());
    },

    // ---- 会话内全量行缓冲 + 显示层裁剪 ----

    _trimDom(output) {
        // 只裁 DOM 不动 _lines（定版 D4）：超出 500 行从最旧开始移除
        while (output.children.length > this._MAX_DOM_LINES) {
            output.removeChild(output.firstChild);
        }
    },

    _scrollBottom(output) {
        requestAnimationFrame(() => {
            if (output) {
                output.scrollTop = output.scrollHeight;
            }
        });
    },

    log(message, type = 'info') {
        const output = document.getElementById('consoleOutput');
        this._lines.push(message);
        const line = document.createElement('div');
        line.className = `console-line ${type}`;
        line.textContent = message;
        output.appendChild(line);
        this._trimDom(output);
        this._scrollBottom(output);
        this._bumpRawLogUnread(type);
        this._liveRawLogLine(message);
    },

    clear() {
        const output = document.getElementById('consoleOutput');
        output.innerHTML = `<div class="console-line">${MSG.ready}</div>`;
        this._lines = [];
    },

    // 后端日志行类型分流（d1102-E 件5）：appendRaw 收的行不带 type，
    // 按行首括号标签与 Python 崩溃栈特征识别，供行着色与胶囊 error 徽标
    // 消费（后端 [ERROR]/[CRITICAL]/[FATAL] 也点亮 _rawLogError）。
    _rawLineType(line) {
        const text = String(line || '');
        if (/^\s*\[(?:ERROR|CRITICAL|FATAL)\]/i.test(text)) return 'error';
        if (/^\s*Traceback \(most recent call last\):/.test(text)) {
            return 'error';
        }
        if (/^\s*\[(?:WARN|WARNING)\]/i.test(text)) return 'warning';
        if (/^\s*\[SUCCESS\]/i.test(text)) return 'success';
        return '';
    },

    appendRaw(text) {
        const output = document.getElementById('consoleOutput');

        const lines = text.split('\n');
        let hasError = false;

        lines.forEach((line, index) => {
            if (index === lines.length - 1 && line === '') return;

            const content = line || ' ';
            const type = this._rawLineType(content);
            if (type === 'error') hasError = true;
            this._lines.push(content);
            const lineEl = document.createElement('div');
            lineEl.className = 'console-line' + (type ? ' ' + type : '');
            lineEl.textContent = content;
            output.appendChild(lineEl);
            this._liveRawLogLine(content, type);
        });
        this._trimDom(output);
        this._scrollBottom(output);
        this._bumpRawLogUnread(hasError ? 'error' : '');
    },

    // ---- 导出 / 复制（空内容静默忽略）----

    exportLog() {
        if (this._lines.length === 0) return;
        const stamp = new Date();
        const p = n => String(n).padStart(2, '0');
        const name = `subtrans-console-${stamp.getFullYear()}${p(stamp.getMonth() + 1)}${p(stamp.getDate())}-${p(stamp.getHours())}${p(stamp.getMinutes())}${p(stamp.getSeconds())}.log`;
        const blob = new Blob([this._lines.join('\n')],
            { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = name;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
    },

    copyLog(btn) {
        if (this._lines.length === 0) return;
        const text = this._lines.join('\n');
        const flash = () => {
            btn.textContent = MSG.ui_copied;
            setTimeout(() => { btn.textContent = MSG.copy_log; }, 1500);
        };
        const fallback = () => {
            // clipboard API 不可用/被拒：textarea + execCommand 降级
            try {
                const ta = document.createElement('textarea');
                ta.value = text;
                ta.style.position = 'fixed';
                ta.style.opacity = '0';
                document.body.appendChild(ta);
                ta.select();
                const ok = document.execCommand('copy');
                ta.remove();
                if (ok) flash();
            } catch (e) { /* 两条复制通路都失败：静默（剪贴板非关键路径） */ }
        };
        if (navigator.clipboard && navigator.clipboard.writeText) {
            navigator.clipboard.writeText(text).then(flash).catch(fallback);
        } else {
            fallback();
        }
    }
};

// ============================================================
// 任务黑框底部抽屉 / 右下角触发胶囊（d1102-件C，D2026-1102-02）
// - fixed 只占主栏宽（left/right 走 --rail-w/--aside-w），z-950：高于
//   queue-dock/audio 900，低于 modal 1000 与错误槽 1001；
// - 默认收起；顶部 6px 把手调高（mouse 会话，铁律：只 preventDefault，
//   禁 stopPropagation——document 级 pywebview 桥靠冒泡）；
// - 高度记忆 localStorage subtransjav.console.h；min 180px / max 70vh；
// - 展开时 .workbench.console-drawer-open 压缩主区高度，并以
//   --console-drawer-offset 抬升 queue-dock/audio 底缘（布局让位非覆盖）。
// ============================================================
const ConsoleDrawer = {
    KEY: 'subtransjav.console.h',
    DEFAULT_RATIO: 0.36,
    MIN_PX: 180,
    MAX_RATIO: 0.7,
    _open: false,
    _height: 0,
    _running: false,

    init() {
        this.drawer = document.getElementById('consoleDrawer');
        this.capsule = document.getElementById('consoleCapsule');
        this.handle = document.getElementById('consoleDrawerHandle');
        this.workbench = document.querySelector('.workbench');
        if (!this.drawer || !this.capsule) return;
        this.restoreHeight();
        this.capsule.addEventListener('click', () => this.toggle());
        if (this.handle) {
            this.handle.addEventListener('mousedown', (e) => this.onDown(e));
        }
        window.addEventListener('resize', () => this.setHeight(this._height, false));
        // ESC 第三层（AppModal > 设置 overlay > 抽屉 > about）：上层活跃即
        // early-return，防一次 ESC 关多层；捕获阶段先于 AppModal 冒泡监听。
        document.addEventListener('keydown', (e) => {
            if (e.key !== 'Escape' || !this._open) return;
            if (typeof AppModal !== 'undefined' && AppModal._busy) return;
            if (typeof SettingsHub !== 'undefined' && SettingsHub._isOpen) return;
            e.preventDefault();
            e.stopPropagation();
            this.close();
        }, true);
        this._syncRunning();
        setInterval(() => this._syncRunning(), 1000);
        this.renderCapsule();
    },

    isOpen() {
        return this._open;
    },

    toggle() {
        if (this._open) this.close();
        else this.open();
    },

    open() {
        if (!this.drawer || this._open) return;
        this._open = true;
        this.drawer.classList.add('is-open');
        if (this.workbench) this.workbench.classList.add('console-drawer-open');
        if (typeof ConsoleManager !== 'undefined') {
            ConsoleManager._rawLogUnread = 0;
            ConsoleManager._rawLogError = false;
        }
        this._syncOffset();
        this.renderCapsule();
    },

    close() {
        if (!this.drawer || !this._open) return;
        this._open = false;
        this.drawer.classList.remove('is-open');
        if (this.workbench) this.workbench.classList.remove('console-drawer-open');
        this._syncOffset();
        this.renderCapsule();
    },

    restoreHeight() {
        let saved = NaN;
        try {
            saved = parseFloat(localStorage.getItem(this.KEY));
        } catch (e) {
            // private/无痕读不到 → 默认 36vh
        }
        this.setHeight(saved, false);
    },

    clampHeight(h) {
        const min = this.MIN_PX;
        const max = Math.max(min, Math.round(window.innerHeight * this.MAX_RATIO));
        if (typeof h !== 'number' || !isFinite(h)) {
            h = Math.round(window.innerHeight * this.DEFAULT_RATIO);
        }
        return Math.min(Math.max(h, min), max);
    },

    setHeight(h, persist) {
        const v = this.clampHeight(h);
        this._height = v;
        document.documentElement.style.setProperty('--console-drawer-h', v + 'px');
        if (persist) {
            try {
                localStorage.setItem(this.KEY, String(v));
            } catch (e) {
                // 写入失败静默（private 模式降级为会话级高度）
            }
        }
        if (this._open) this._syncOffset();
    },

    _syncOffset() {
        document.documentElement.style.setProperty(
            '--console-drawer-offset', this._open ? this._height + 'px' : '0px');
    },

    onDown(e) {
        if (!this.drawer || e.button !== 0) return;
        e.preventDefault();   // 只 preventDefault：禁 stopPropagation（桥靠冒泡）
        const startY = e.clientY;
        const startH = this._height;
        const onMove = (ev) => {
            this.setHeight(startH + (startY - ev.clientY), false);
        };
        const onUp = () => {
            document.removeEventListener('mousemove', onMove);
            document.removeEventListener('mouseup', onUp);
            this.setHeight(this._height, true);   // 会话末尾单写记忆
        };
        document.addEventListener('mousemove', onMove);
        document.addEventListener('mouseup', onUp);
    },

    _syncRunning() {
        const running = typeof AppState !== 'undefined' && !!AppState.isRunning;
        if (running === this._running) return;
        this._running = running;
        this.renderCapsule();
        if (typeof FlowOverview !== 'undefined') FlowOverview.refreshNodes();
    },

    renderCapsule() {
        const cap = this.capsule;
        if (!cap) return;
        const unread = (typeof ConsoleManager !== 'undefined')
            ? ConsoleManager._rawLogUnread : 0;
        const errored = (typeof ConsoleManager !== 'undefined')
            && !!ConsoleManager._rawLogError;
        cap.classList.toggle('is-open', this._open);
        cap.classList.toggle('is-running', this._running && !this._open);
        cap.classList.toggle('has-unread', !this._open && unread > 0);
        cap.classList.toggle('is-error', !this._open && errored);
        const badge = cap.querySelector('.console-capsule-badge');
        if (badge) {
            const show = !this._open && unread > 0;
            badge.hidden = !show;
            badge.textContent = show ? (unread > 99 ? '99+' : String(unread)) : '';
        }
        const key = this._open ? 'console_collapse' : 'console_expand';
        cap.setAttribute('aria-label', MSG[key]);
        cap.setAttribute('title', MSG[key]);
        cap.setAttribute('aria-expanded', this._open ? 'true' : 'false');
        if (this.drawer) {
            this.drawer.setAttribute('aria-hidden', this._open ? 'false' : 'true');
        }
        const collapseBtn = document.getElementById('consoleCollapseBtn');
        if (collapseBtn) {
            collapseBtn.setAttribute('aria-expanded', this._open ? 'true' : 'false');
        }
    }
};
