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

        // Console 折叠开关（默认展开；折叠后隐藏输出区且外层不再占 flex:1）
        const collapseBtn = document.getElementById('consoleCollapseBtn');
        if (collapseBtn) {
            collapseBtn.setAttribute('aria-label', MSG.console_collapse);
            collapseBtn.addEventListener('click', () => {
                const section = collapseBtn.closest('.console-section');
                if (!section) return;
                const collapsed = section.classList.toggle('collapsed');
                collapseBtn.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
                const key = collapsed ? 'console_expand' : 'console_collapse';
                collapseBtn.setAttribute('title', MSG[key]);
                collapseBtn.setAttribute('aria-label', MSG[key]);
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
    },

    // ---- 原始日志（五轮 D2026-1010-01：弹窗化，内联展开退场）----
    // 内联展开受 Console 区 380px 上限挤压无法下翻（owner 实证），点击
    // 开关改为打开 AppModal 大卡承载 _lines 全量缓冲；#consoleOutput 保留
    // 为隐藏 DOM 承载（log/appendRaw 仍写 DOM + 显示层裁剪，契约零破坏）

    // 卡2（D2026-1010-01 三轮）：折叠期新行未读计数（弹窗打开态豁免）
    _rawLogUnread: 0,

    _bumpRawLogUnread() {
        const toggle = document.getElementById('rawLogToggleBtn');
        if (!toggle) return;
        if (AppModal._kind === 'rawlog') return;   // 弹窗打开期不计数
        this._rawLogUnread += 1;
        toggle.textContent = `${MSG.raw_log_toggle} •${this._rawLogUnread}`;
    },

    // 弹窗打开期间新行实时追加（等宽列表尾随+滚底，500 行显示层同款裁剪）
    _liveRawLogLine(text) {
        if (AppModal._kind !== 'rawlog') return;
        const list = document.querySelector('#appModal .rawlog-view');
        if (!list) return;
        const line = document.createElement('div');
        line.className = 'console-line';
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
        this._rawLogUnread = 0;
        const toggle = document.getElementById('rawLogToggleBtn');
        if (toggle) toggle.textContent = MSG.raw_log_toggle;
    },

    _initRawLogToggle() {
        const toggle = document.getElementById('rawLogToggleBtn');
        const output = document.getElementById('consoleOutput');
        if (!toggle || !output) return;
        toggle.textContent = MSG.raw_log_toggle;
        output.style.display = 'none';   // 内联展开退场，永久隐藏承载
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
        this._bumpRawLogUnread();
        this._liveRawLogLine(message);
    },

    clear() {
        const output = document.getElementById('consoleOutput');
        output.innerHTML = `<div class="console-line">${MSG.ready}</div>`;
        this._lines = [];
    },

    appendRaw(text) {
        const output = document.getElementById('consoleOutput');

        const lines = text.split('\n');

        lines.forEach((line, index) => {
            if (index === lines.length - 1 && line === '') return;

            this._lines.push(line || ' ');
            const lineEl = document.createElement('div');
            lineEl.className = 'console-line';
            lineEl.textContent = line || ' ';
            output.appendChild(lineEl);
            this._liveRawLogLine(line || ' ');
        });
        this._trimDom(output);
        this._scrollBottom(output);
        this._bumpRawLogUnread();
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

