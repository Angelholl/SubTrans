// ============================================================
// Activity Stream（2.7.3 件⑧批 8b：Console 面板内、原始日志上方的
// 结构化活动流）。由 TranslatorManager.startStatusPolling 每拍喂
// get_translation_status 快照，内部差分打点：
//   阶段开始 / 文件完成与失败 / 风险增量（自 TranslatorManager 迁移，
//   _reportedRiskCount 旧字段删除）/ 错误 / 心跳超时告警 / 完成摘要。
// 上限 200 行，DOM 与内部数组同裁（无全量保留需求，导出走 ConsoleManager）。
// ============================================================
// 心跳超时判定单点：优先消费后端 snapshot 已算好的 heartbeat_stale；
// 仅当该键为 undefined（旧后端兼容）才回退本地 age>阈值 判定
// （阈值取后端 heartbeat_stale_s，缺省 45s ≈ 2.25×心跳间隔 20s）。
function heartbeatIsStale(status) {
    if (status.heartbeat_stale !== undefined) {
        return status.heartbeat_stale === true;
    }
    const staleS = (typeof status.heartbeat_stale_s === 'number')
        ? status.heartbeat_stale_s : 45;
    return status.heartbeat_age != null && status.heartbeat_age > staleS;
}

const ActivityStream = {
    _MAX_LINES: 200,
    _rows: [],
    _last: null,            // 首拍基线标记（null=尚未初始化，不回放历史）
    _fileStates: {},        // 上次 files_status 快照
    _riskCount: 0,          // 原 TranslatorManager._reportedRiskCount 迁移至此
    _lastError: null,
    _heartbeatAlerted: false,
    _summaryShown: false,
    _stage: null,

    // 新任务新流：startTranslation 成功分支调用，清空活动流与差分状态
    reset() {
        this._rows = [];
        this._last = null;
        this._fileStates = {};
        this._riskCount = 0;
        this._lastError = null;
        this._heartbeatAlerted = false;
        this._summaryShown = false;
        this._stage = null;
        const el = document.getElementById('consoleActivity');
        if (el) el.innerHTML = '';
    },

    _add(text, cls) {
        this._rows.push(text);
        const el = document.getElementById('consoleActivity');
        if (el) {
            const line = document.createElement('div');
            line.className = `console-line ${cls || 'info'}`;
            line.textContent = text;
            el.appendChild(line);
            // DOM 与内部数组同裁
            while (this._rows.length > this._MAX_LINES) {
                this._rows.shift();
                if (el.firstChild) el.removeChild(el.firstChild);
            }
            el.scrollTop = el.scrollHeight;
        }
    },

    update(status) {
        if (!status) return;

        // 阶段开始：current_stage 变化且非空（阶段名用后端原文）
        if (status.current_stage && status.current_stage !== this._stage) {
            this._stage = status.current_stage;
            this._add(MSG.activity_stage_start(status.current_stage), 'info');
        }

        // 文件完成/失败：对比上次 files_status 快照；首拍只建基线不回放历史；
        // running 新出现不打点（避免刷屏）；pending 视为无变化
        if (status.files_status) {
            if (this._last !== null) {
                Object.keys(status.files_status).forEach(f => {
                    const st = status.files_status[f];
                    const prev = this._fileStates[f];
                    if (st === 'done' && prev !== 'done') {
                        this._add(MSG.activity_file_done(f), 'success');
                    } else if (st === 'failed' && prev !== 'failed') {
                        this._add(MSG.activity_file_failed(f), 'error');
                    }
                });
            }
            this._fileStates = Object.assign({}, status.files_status);
        }

        // 风险增量（自 startStatusPolling 迁移，行文案带文件归属）
        const reported = this._riskCount || 0;
        if ((status.risk_count || 0) > reported) {
            const risks = status.risks || [];
            const fresh = risks.slice(
                Math.max(0, risks.length - (status.risk_count - reported)));
            fresh.forEach(r => {
                const msg = (r && (r.message || r.type)) || MSG.risk_word;
                const phase = (r && r.phase) || MSG.risk_word;
                if (r && r.file) {
                    this._add(MSG.activity_risk_file(r.file, phase, msg),
                        'warning');
                } else {
                    this._add(MSG.activity_risk(phase, msg), 'warning');
                }
            });
            this._riskCount = status.risk_count;
        }

        // 错误：与上次不同才打（去重）
        if (status.error && status.error !== this._lastError) {
            this._lastError = status.error;
            this._add(MSG.activity_error(status.error), 'error');
        }

        // 心跳超时：进入超时态打一行黄色告警，恢复（不超时）重置告警态
        // （判定单点 heartbeatIsStale：优先后端 heartbeat_stale，旧后端回退本地算）
        const stale = status.status === 'running' && heartbeatIsStale(status);
        if (stale && !this._heartbeatAlerted) {
            this._heartbeatAlerted = true;
            this._add(MSG.activity_heartbeat_stale(
                Math.round(status.heartbeat_age)), 'warning');
        } else if (!stale) {
            this._heartbeatAlerted = false;
        }

        // 完成摘要：task_summary（task_finished payload）非空且未打过 →
        // 绿色摘要行；status 字段（success/partial/failed）存在则加后缀
        const ts = status.task_summary;
        if (ts && !this._summaryShown) {
            this._summaryShown = true;
            const suffix = ts.status
                ? MSG.activity_summary_status(ts.status) : '';
            this._add(MSG.activity_summary(
                ts.files_ok || 0, ts.files_degraded || 0,
                ts.files_failed || 0, ts.risk_count || 0) + suffix, 'success');
        }

        this._last = status;
    }
};

