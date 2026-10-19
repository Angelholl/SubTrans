// ============================================================
// Progress Management (progress bar inside the refine panel)
// ============================================================
const ProgressManager = {
    init() {
        this.progressBar = document.getElementById('progressBar');
        this.progressFill = document.getElementById('progressFill');
        this.progressMeta = document.querySelector('.progress-meta');
        this.statusLabel = document.getElementById('statusLabel');
        this.statusDot = document.getElementById('statusDot');
        this.lastStage = null;
        // 预创建两个 span 供 CSS flex 两端布局（左段阶段+批次，右段百分比）
        if (this.progressMeta) {
            this.progressMetaLeft = document.createElement('span');
            this.progressMetaRight = document.createElement('span');
            this.progressMeta.appendChild(this.progressMetaLeft);
            this.progressMeta.appendChild(this.progressMetaRight);
        }
    },

    setIndeterminate(active) {
        if (this.progressBar) this.progressBar.classList.toggle('indeterminate', active);
    },

    setProgress(percent, stageName, batchNo, batchTotal) {
        if (this.progressFill) this.progressFill.style.width = `${percent}%`;
        if (this.progressMeta) {
            const pct = `${Math.round(percent)}%`;
            let left = stageName || this.lastStage || '';
            if (stageName) this.lastStage = stageName;
            if (batchNo !== undefined && batchNo !== null && batchTotal) {
                left = `${left} · 批次 ${batchNo} / ${batchTotal}`;
            }
            // idle 态（无阶段名且百分比为 0）整行留空
            const isEmpty = !left && percent === 0;
            this.progressMetaLeft.textContent = isEmpty ? '' : left;
            this.progressMetaRight.textContent = isEmpty ? '' : pct;
        }
    },

    setStatus(text) {
        if (this.statusLabel) this.statusLabel.textContent = text;
    },

    // 状态点（D2026-0930-09 批2 两态 → P2-9 d1015-卡J 五态全集）：
    // idle 灰 / running 蓝 / ok 绿 / warn 琥珀 / err 红；未知值回落 idle。
    // 五类全量 toggle（当前类 true 其余 false），终态色保留至下一次 start。
    setDot(state) {
        if (!this.statusDot) return;
        const dotClass = {
            idle: 'dot-idle', running: 'dot-running',
            ok: 'dot-ok', warn: 'dot-warn', err: 'dot-err'
        }[state] || 'dot-idle';
        this.statusDot.classList.toggle('dot-idle', dotClass === 'dot-idle');
        this.statusDot.classList.toggle('dot-running', dotClass === 'dot-running');
        this.statusDot.classList.toggle('dot-ok', dotClass === 'dot-ok');
        this.statusDot.classList.toggle('dot-warn', dotClass === 'dot-warn');
        this.statusDot.classList.toggle('dot-err', dotClass === 'dot-err');
    },

    reset() {
        this.setIndeterminate(false);
        this.setProgress(0);
        this.setStatus(MSG.idle);
        this.setDot('idle');
    }
};

