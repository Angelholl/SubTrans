// ============================================================
// App Modal（2.4.0 批1 S1）：原生 alert/confirm/prompt 的宿主无关自制模态
// （prompt 在部分 WebView 宿主返回 null——行为与宿主解耦；Promise 永不 reject）
// ============================================================
const AppModal = {
    _busy: false,        // 硬性条款①：打开中守卫——单例，防 F5 连按/glAdd 双击叠加
    _kind: null,
    _resolve: null,
    _dlRunning: false,   // 2.6.3 批B：download 模态下载进行中（onStart Promise 未 settle）
    _edDirty: false,     // 2.6.3 批D：编辑器有未保存修改（textarea input 置位）
    _edSaving: false,    // 批D：保存进行中（onSave Promise 未 settle，禁止关闭）
    _edConfirming: false,// 批D：放弃确认弹窗进行中（防守卫递归）
    _edOpts: null,       // 批D：editor(opts) 暂存（onSave/onStageChange/onDiscard/onClose）
    _tmSaving: false,    // P3：tmEdit 保存进行中（禁关，editor 同款）
    _tmOpts: null,       // P3：tmEdit(opts) 暂存（onSaved）
    _encodeCollect: null,// 2.8.0.2：encode 闭包 collect（打开赋值/结算置 null，防悬挂引用）
    _polishCollect: null,// D2026-1024-01 批2 件A：polish 闭包 collect（同 encode 先例）

    _settle(value) {
        if (!this._busy) return;
        // 2.6.3 批B：下载进行中 ESC/遮罩点击/取消键全部 no-op（无取消语义，
        // 评议员条件①；完成/失败后 _dlRunning 复位，关闭键恢复可用）。
        // 2.7.1 评议 C3：该 no-op 分支仅命中 download kind——models kind
        // 不复用 _dlRunning 布尔，关闭永不阻塞（下载后台继续）。
        if (this._kind === 'download' && this._dlRunning) return;
        // 2.6.3 批D：编辑器保存进行中禁止关闭（同 _dlRunning 先例）；
        // 有未保存修改先走放弃确认守卫（确认后经 _settle 正式结算）
        if (this._kind === 'editor' && this._edSaving) return;
        if (this._kind === 'editor' && this._edDirty && !this._edConfirming) {
            this._editorDiscardGuard();
            return;
        }
        // P3（D2026-1008-02）：tmEdit 同 editor 先例——保存中禁关；
        // 脏态先经放弃确认（_edDirty/_edConfirming 共用布尔，kind 互斥
        // 安全），确认后经 _settle 正式结算
        if (this._kind === 'tmEdit' && this._tmSaving) return;
        if (this._kind === 'tmEdit' && this._edDirty && !this._edConfirming) {
            this._tmEditDiscardGuard();
            return;
        }
        this._busy = false;
        this._kind = null;
        const resolve = this._resolve;
        this._resolve = null;
        const root = document.getElementById('appModal');
        if (root) root.style.display = 'none';
        if (resolve) resolve(value);
    },

    _cancelValue() { return AppModal._kind === 'prompt' ? null : false; },

    // ok/Enter 确认值分派（2.8.0.2「首绑互窃」类级根治）：事件时刻读 _kind，
    // kind→语义矩阵——
    //   tmEdit/editor/download/models：ok 键在这些 kind 下隐藏、Enter 无确认
    //     语义（tmEdit/editor textarea 回车=换行不提交）→ undefined（调用方
    //     no-op 且不 preventDefault）；
    //   prompt：带输入值结算；encode：按当前表单值结算（_resolve 包装器落
    //     {ok, params}，collect 闭包经 _encodeCollect 暴露、关闭置 null）；
    //   polish（D2026-1024-01 批2 件A）：同 encode 分派（_polishCollect）；
    //   其余（alert/confirm/batchfix）：true（确认）。
    _okValue(input) {
        if (this._kind === 'tmEdit' || this._kind === 'editor'
            || this._kind === 'download' || this._kind === 'models') {
            return undefined;
        }
        if (this._kind === 'prompt') return (input && input.value) || '';
        if (this._kind === 'encode') {
            const collect = this._encodeCollect;
            return collect ? { ok: true, params: collect() } : true;
        }
        // D2026-1024-01 批2 件A：polish 同 encode 分派——ok 键/Enter=保存，
        // 按当前表单值结算 {ok, params}（collect 闭包经 _polishCollect 暴露）
        if (this._kind === 'polish') {
            const collect = this._polishCollect;
            return collect ? { ok: true, params: collect() } : true;
        }
        return true;
    },

    // 统一骨架一次性绑定（2.8.0.2）：原各模态方法各自携带 dataset.bound
    // 一次性绑定块、运行时只注册会话首个打开模态的那一份，而各块 ok/Enter 语义互异
    // （editor/tmEdit 排除 Enter、encode ok 结算 params）——首绑归属谁，后续
    // 所有模态的骨架语义就被谁定格（实锤：tmEdit 先开后，批量修复确认框
    // okBtn 零处理器，「开始修复」无反应）。现收敛为唯一一处 kind 感知绑定：
    // 每个模态打开路径都先经本方法补绑（守卫保证整个会话只执行一次），
    // ok/Enter 事件时刻经 _okValue() 按 _kind 分派；ESC/遮罩/取消键一律
    // _cancelValue()（download 下载中 no-op 与 editor/tmEdit 脏态放弃确认
    // 均由 _settle 既有分支承接）。
    _bindSkeletonOnce(root) {
        if (root.dataset.bound) return;
        root.dataset.bound = '1';
        root.addEventListener('click', (e) => {
            if (e.target === root) AppModal._settle(AppModal._cancelValue());   // 遮罩取消
        });
        root.querySelector('.modal-ok').addEventListener('click', () => {
            const v = AppModal._okValue(root.querySelector('.modal-input'));
            if (v !== undefined) AppModal._settle(v);
        });
        root.querySelector('.modal-cancel').addEventListener('click', () =>
            AppModal._settle(AppModal._cancelValue()));
        document.addEventListener('keydown', (e) => {
            if (!AppModal._busy) return;
            if (e.key === 'Escape') {
                e.preventDefault();
                AppModal._settle(AppModal._cancelValue());
            } else if (e.key === 'Enter') {
                const v = AppModal._okValue(root.querySelector('.modal-input'));
                if (v !== undefined) {
                    e.preventDefault();
                    AppModal._settle(v);
                }
            }
        });
    },

    _open(kind, title, body, def, opts) {
        if (this._busy) {
            // 重入：单例不叠加——在途调用方仍持原 Promise，新调用立即按取消结算
            return Promise.resolve(kind === 'prompt' ? null : false);
        }
        const root = document.getElementById('appModal');
        if (!root) {
            // 骨架缺席兜底：退回原生对话框（永不 reject）
            if (kind === 'alert') { window.alert(`${title}\n\n${body}`); return Promise.resolve(undefined); }
            if (kind === 'confirm') { return Promise.resolve(window.confirm(`${title}\n\n${body}`)); }
            return Promise.resolve(window.prompt(`${title}`, def || ''));
        }
        root.querySelector('.modal-title').textContent = title || '';
        root.querySelector('.modal-body').textContent = body || '';
        const input = root.querySelector('.modal-input');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        // 批1b 件4：confirm 支持自定义双键文案（opts.okText/cancelText，
        // 缺省回退 ui_ok/ui_cancel——既有调用点行为零变化）
        cancelBtn.textContent = (opts && opts.cancelText) || MSG.ui_cancel;
        okBtn.textContent = (opts && opts.okText) || MSG.ui_ok;
        cancelBtn.style.display = kind === 'alert' ? 'none' : '';   // 硬性条款②：alert 无取消键
        input.style.display = kind === 'prompt' ? '' : 'none';
        input.value = kind === 'prompt' ? (def || '') : '';
        this._bindSkeletonOnce(root);       // 2.8.0.2：唯一 kind 感知骨架绑定
        this._busy = true;
        this._kind = kind;
        root.style.display = 'flex';        // 等效 .modal-overlay.active（inline 覆盖基类 display:none）
        (kind === 'prompt' ? input : okBtn).focus();   // focus 管理：prompt 聚输入框，其余聚确认键
        if (kind === 'prompt' && input.value) input.select();
        return new Promise((resolve) => { this._resolve = resolve; });
    },

    alert(title, body) { return this._open('alert', title, body); },
    confirm(title, body, opts) { return this._open('confirm', title, body, undefined, opts); },
    prompt(title, body, def) { return this._open('prompt', title, body, def); },

    // ============================================================
    // download 模态（2.6.3 批B，D2026-1003-01 ②）：源单选卡+meta 行+无取消
    // 声明+全宽开始键+进度区一体化。复用 #appModal 骨架（title/关闭键），
    // body 内容全 createElement 注入（FROZEN_IDS 冻结：零新增 id/data-i18n）。
    // 不走 _open 三分支（alert/confirm/prompt 行为零变化），但经
    // _bindSkeletonOnce 统一骨架绑定（2.8.0.2：遮罩/取消/ESC→_settle，
    // _settle 内 _dlRunning 守卫承载"下载中 no-op"；ok/Enter 无确认语义）。
    // opts = {title, sources:[{key,label,hint,disabled}],
    //         meta:[{label,value,copyable}], notice,
    //         onStart(sourceKey, update)->Promise<{ok,message}>, onClose?}
    // update(snap) 为进度区渲染回调（snap={phase,downloaded,total,note}）。
    // ============================================================
    download(opts) {
        if (this._busy) return Promise.resolve(false);      // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        const o = opts || {};
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = o.title || '';
        body.textContent = '';
        body.style.whiteSpace = 'normal';   // .modal-card .modal-body 默认 pre-wrap，布局需正常折行
        input.style.display = 'none';
        okBtn.style.display = 'none';       // download 只留关闭键（确认语义由开始键承载）
        okBtn.textContent = '';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        this._bindSkeletonOnce(root);       // 2.8.0.2：唯一 kind 感知骨架绑定

        // —— 源单选卡（label+radio；disabled 卡灰态，radio 默认选第一个非禁用）——
        const sources = o.sources || [];
        const srcBox = document.createElement('div');
        srcBox.className = 'dl-src-list';
        const radios = [];
        sources.forEach((s) => {
            const card = document.createElement('label');
            card.className = 'dl-src-card' + (s.disabled ? ' dl-src-disabled' : '');
            const radio = document.createElement('input');
            radio.type = 'radio';
            radio.name = 'dl-src-choice';
            radio.value = String(s.key || '');
            if (s.disabled) radio.disabled = true;
            const txt = document.createElement('span');
            txt.className = 'dl-src-label';
            txt.textContent = s.label || s.key || '';
            card.appendChild(radio);
            card.appendChild(txt);
            if (s.hint) {
                const hint = document.createElement('span');
                hint.className = 'dl-src-hint muted';
                hint.textContent = s.hint;
                card.appendChild(hint);
            }
            radio.addEventListener('change', () => {
                radios.forEach((r) => r.closest('.dl-src-card')
                  .classList.toggle('dl-src-selected', r.checked));
            });
            srcBox.appendChild(card);
            radios.push(radio);
        });
        body.appendChild(srcBox);
        const firstEnabled = radios.find((r) => !r.disabled);
        if (firstEnabled) {
            firstEnabled.checked = true;
            firstEnabled.closest('.dl-src-card').classList.add('dl-src-selected');
        }

        // —— meta 行表（copyable 行点击复制+「已复制」轻提示）——
        (o.meta || []).forEach((m) => {
            const row = document.createElement('div');
            row.className = 'dl-meta-row';
            const lab = document.createElement('span');
            lab.className = 'dl-meta-label';
            lab.textContent = (m.label || '') + (m.label ? '：' : '');
            const val = document.createElement('span');
            val.textContent = m.value == null ? '' : String(m.value);
            row.appendChild(lab);
            row.appendChild(val);
            if (m.copyable && m.value) {
                val.className = 'dl-copyable';
                val.title = String(m.value);
                val.addEventListener('click', () => {
                    if (!navigator.clipboard || !navigator.clipboard.writeText) {
                        val.title = MSG.ui_copy_manual;     // clipboard 不可用：title 提示手动复制
                        return;
                    }
                    navigator.clipboard.writeText(String(m.value)).then(() => {
                        val.textContent = MSG.ui_copied;
                        setTimeout(() => { val.textContent = String(m.value); }, 1200);
                    }).catch(() => { val.title = MSG.ui_copy_manual; });
                });
            }
            body.appendChild(row);
        });

        // —— 无取消声明（无取消语义成文）——
        if (o.notice) {
            const note = document.createElement('div');
            note.className = 'dl-notice muted';
            note.textContent = o.notice;
            body.appendChild(note);
        }

        // —— 全宽开始键 + 进度区（bar/fill/text 三件套，class 独立 .dl-progress-*）+ 结果行 ——
        const startBtn = document.createElement('button');
        startBtn.type = 'button';
        startBtn.className = 'btn btn-primary modal-dl-start';
        startBtn.textContent = MSG.asrDlStart;
        if (!firstEnabled) startBtn.disabled = true;        // 全 disabled → 开始禁用
        body.appendChild(startBtn);
        const prog = document.createElement('div');
        prog.className = 'dl-progress';
        prog.style.display = 'none';
        const bar = document.createElement('div');
        bar.className = 'dl-progress-bar';
        const fill = document.createElement('div');
        fill.className = 'dl-progress-fill';
        bar.appendChild(fill);
        const text = document.createElement('div');
        text.className = 'dl-progress-text';
        prog.appendChild(bar);
        prog.appendChild(text);
        body.appendChild(prog);
        const result = document.createElement('div');
        result.className = 'dl-result';
        result.style.display = 'none';
        body.appendChild(result);
        const fmtMB = (n) => (n / 1048576).toFixed(1);

        startBtn.addEventListener('click', () => {
            if (this._dlRunning) return;
            const sel = radios.find((r) => r.checked && !r.disabled);
            if (!sel || typeof o.onStart !== 'function') return;
            this._dlRunning = true;
            startBtn.disabled = true;
            cancelBtn.disabled = true;      // 下载中关闭键不可用（完成/失败后恢复）
            prog.style.display = '';
            fill.style.width = '';
            bar.classList.add('indeterminate');
            text.textContent = '';
            result.style.display = 'none';
            let poller = null;
            const stopPoll = () => { if (poller) { clearInterval(poller); poller = null; } };
            const render = (snap) => {
                snap = snap || {};
                if (snap.phase === 'download' && snap.total) {
                    bar.classList.remove('indeterminate');
                    fill.style.width =
                      Math.min(100, Math.round((snap.downloaded || 0) / snap.total * 100)) + '%';
                    text.textContent = `${fmtMB(snap.downloaded || 0)}/${fmtMB(snap.total)}MB`;
                } else {
                    fill.style.width = '';
                    bar.classList.add('indeterminate');
                    text.textContent = snap.phase === 'verify' ? MSG.dict_verify
                      : MSG.dict_downloading;
                }
                if (snap.note) text.textContent += '｜' + snap.note;   // 回退可见提示（条件①）
            };
            Promise.resolve()
              .then(() => o.onStart(sel.value, render))
              .then((res) => {
                  stopPoll();
                  this._dlRunning = false;
                  prog.style.display = 'none';
                  const ok = !!(res && res.ok);
                  result.style.display = '';
                  result.className = 'dl-result ' + (ok ? 'dl-result-ok' : 'dl-result-err');
                  result.textContent = (ok ? MSG.asrDlDone : MSG.asrDlFailed)
                    + '：' + ((res && res.message) || '');
                  cancelBtn.disabled = false;   // 关闭键恢复可用
              })
              .catch((e) => {
                  stopPoll();
                  this._dlRunning = false;
                  prog.style.display = 'none';
                  result.style.display = '';
                  result.className = 'dl-result dl-result-err';
                  result.textContent = MSG.asrDlFailed + '：'
                    + (e && e.message ? e.message : String(e));
                  cancelBtn.disabled = false;
              });
        });

        // 收口：关闭时恢复骨架默认态（_open 不重置 okBtn.display/whiteSpace，
        // download 自清理防污染后续 alert/confirm/prompt）
        const closeResolve = () => {
            okBtn.style.display = '';
            body.style.whiteSpace = '';
            if (typeof o.onClose === 'function') o.onClose();
        };
        this._busy = true;
        this._kind = 'download';
        this._dlRunning = false;
        root.style.display = 'flex';
        startBtn.focus();
        return new Promise((resolve) => {
            this._resolve = (value) => { closeResolve(); resolve(value); };
        });
    },

    // ============================================================
    // 编辑器模态（2.6.3 批D，D2026-1003-01 P5）：角色卡编辑器整体迁入。
    // 节点搬迁模式：vault（.tpl-editor-vault，hidden 常驻）内既有节点按
    // 原序 appendChild 进 modal-body（textarea 包一层 .editor-ta-wrap
    // 弹性层），关闭/确认放弃时逐个 append 回 vault——appendChild 即复位，
    // 幂等可逆（FROZEN_IDS 零变更：vault 与其内 id/data-i18n 全部原样）。
    // 经 _bindSkeletonOnce 统一骨架监听（2.8.0.2：遮罩/取消/ESC→_settle，
    // Enter 无确认语义——textarea 回车=换行）；modal-card
    // 打开加 .modal-lg、body 加 .modal-editor-body，关闭自清理（download
    // 同款自管 body 模式，防污染后续 alert/confirm/prompt）。
    // dirty 守卫：textarea input 置 _edDirty；_settle 编辑器分支——有未
    // 保存修改先经 AppModal.confirm 确认（confirm 与编辑器共用单例骨架：
    // 先收起编辑器——节点搬回 vault 保状态+_busy=false——再弹确认）。
    // opts = {title, onSave(stage, text)->Promise<{ok,message}>,
    //         onStageChange(stage, mode)->Promise, onDiscard?, onClose?}
    // ============================================================
    editor(opts) {
        if (this._busy) return Promise.resolve(false);      // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        if (!document.querySelector('.tpl-editor-vault')) return Promise.resolve(false);
        const o = opts || {};
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = o.title || MSG.tplEditorTitle;
        body.textContent = '';
        body.style.whiteSpace = 'normal';   // .modal-card .modal-body 默认 pre-wrap
        body.classList.add('modal-editor-body');
        const card = root.querySelector('.modal-card');
        if (card) card.classList.add('modal-lg');
        input.style.display = 'none';
        okBtn.style.display = 'none';       // 确认语义由 vault 内保存键承载
        okBtn.textContent = '';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        this._bindSkeletonOnce(root);       // 2.8.0.2：唯一 kind 感知骨架绑定
        // —— 节点搬入：vault → modal-body（原序；textarea 包弹性层）——
        this._editorUnstash();
        // —— textarea dirty 一次性监听（搬入搬出不卸载）——
        const ta = document.getElementById('refineTemplateText');
        if (ta && !ta.dataset.edDirtyBound) {
            ta.dataset.edDirtyBound = '1';
            ta.addEventListener('input', () => { AppModal._edDirty = true; });
        }
        // —— vault 内保存/重载/切阶段键：弹窗感知路径一次性绑定（原
        // bindDom 直绑移除，见 bindDom 批D 注记）——
        const saveBtn = document.getElementById('refineTemplateSave');
        if (saveBtn && !saveBtn.dataset.edSaveBound) {
            saveBtn.dataset.edSaveBound = '1';
            saveBtn.addEventListener('click', () => AppModal.editorRunSave());
        }
        const reloadBtn = document.getElementById('refineTemplateReload');
        if (reloadBtn && !reloadBtn.dataset.edReloadBound) {
            reloadBtn.dataset.edReloadBound = '1';
            reloadBtn.addEventListener('click', () => AppModal.editorRunStageChange('reload'));
        }
        const stageSel = document.getElementById('refineTemplateStage');
        if (stageSel && !stageSel.dataset.edStageBound) {
            stageSel.dataset.edStageBound = '1';
            stageSel.addEventListener('change', () => AppModal.editorRunStageChange('change'));
        }
        this._edOpts = o;
        this._busy = true;
        this._kind = 'editor';
        this._edDirty = false;
        this._edSaving = false;
        this._edConfirming = false;
        root.style.display = 'flex';
        if (ta) ta.focus();
        return new Promise((resolve) => {
            this._resolve = (value) => {
                this._editorTeardown();
                if (typeof o.onClose === 'function') o.onClose();
                resolve(value);
            };
        });
    },

    // 节点搬回 vault（关闭/确认前收起）：modal-body 子节点逐个 append 回
    // vault 原序复位（textarea 自弹性层拆出）；vault 原 hidden 保留，
    // 节点回 vault 即随容器隐藏——vault hidden ↔ 弹窗互斥
    _editorStash() {
        const vault = document.querySelector('.tpl-editor-vault');
        const body = document.querySelector('#appModal .modal-body');
        if (!vault || !body) return;
        Array.prototype.slice.call(body.childNodes).forEach((n) => {
            if (n.nodeType === 1 && n.classList.contains('editor-ta-wrap')) {
                while (n.firstChild) vault.appendChild(n.firstChild);
            } else {
                vault.appendChild(n);
            }
        });
        while (body.firstChild) body.removeChild(body.firstChild);   // 残余包装层
    },

    // 节点搬入 modal-body（vault → 弹窗；原序；textarea 包 .editor-ta-wrap）
    _editorUnstash() {
        const vault = document.querySelector('.tpl-editor-vault');
        const body = document.querySelector('#appModal .modal-body');
        if (!vault || !body) return;
        Array.prototype.slice.call(vault.childNodes).forEach((n) => {
            if (n.nodeType === 1 && n.id === 'refineTemplateText') {
                const wrap = document.createElement('div');
                wrap.className = 'editor-ta-wrap';
                wrap.appendChild(n);
                body.appendChild(wrap);
            } else {
                body.appendChild(n);
            }
        });
    },

    // 编辑器开态确认弹窗（与 confirm 共用单例骨架）：先收起编辑器（节点
    // 搬回 vault hidden 保状态 + _busy=false 放行 confirm），取消=原样恢复
    // （_busy/_kind/_resolve/display/节点全部还原）；确认=保持收起态由调用
    // 方收尾（关闭结算或放行原动作）
    _editorConfirmWhileOpen(msg) {
        const edResolve = this._resolve;    // confirm 会覆写 _resolve，先持有
        const root = document.getElementById('appModal');
        const okBtn = root && root.querySelector('.modal-ok');
        this._edConfirming = true;
        this._editorStash();
        if (root) root.style.display = 'none';
        this._busy = false;
        if (okBtn) okBtn.style.display = '';    // confirm 需要 OK 键（编辑器开态隐藏）
        return AppModal.confirm(msg).then((ok) => {
            this._busy = true;
            this._kind = 'editor';
            this._resolve = edResolve;
            this._edConfirming = false;
            if (okBtn) okBtn.style.display = 'none';
            if (ok) return true;
            if (root) root.style.display = 'flex';
            this._editorUnstash();
            return false;
        });
    },

    // dirty 关闭守卫：未保存修改先确认——取消=弹窗与编辑状态原样保留；
    // 确认=真放弃（脏复位+正式结算+onDiscard 按当前阶段重载丢编辑）
    _editorDiscardGuard() {
        this._editorConfirmWhileOpen(MSG.tplEditorDirtyConfirm).then((ok) => {
            if (!ok) return;
            this._edDirty = false;
            this._settle(false);            // 正式结算（_resolve 收尾 teardown+onClose）
            const o = this._edOpts || {};
            if (typeof o.onDiscard === 'function') {
                try { o.onDiscard(); } catch (e) { /* 重载失败静默 */ }
            }
        });
    },

    // 保存主键（vault 内 #refineTemplateSave）弹窗感知路径：onSave 进行中
    // 禁止关闭（_edSaving 同 _dlRunning 先例）；成功=清脏+status/入口摘要
    // 写已保存+自动关闭；失败=status 写失败文案、弹窗保持
    async editorRunSave() {
        if (this._edSaving || this._edConfirming) return;
        const o = this._edOpts || {};
        if (typeof o.onSave !== 'function') return;
        this._edSaving = true;
        const cancelBtn = document.querySelector('#appModal .modal-cancel');
        if (cancelBtn) cancelBtn.disabled = true;
        const stage = (document.getElementById('refineTemplateStage') || {}).value;
        const text = (document.getElementById('refineTemplateText') || {}).value;
        let ok = false, message = '';
        try {
            const res = await Promise.resolve(o.onSave(stage, text));
            ok = !!(res && res.ok);
            message = (res && res.message) || '';
        } catch (e) {
            ok = false;
            message = e && e.message ? e.message : String(e);
        }
        this._edSaving = false;
        if (cancelBtn) cancelBtn.disabled = false;
        const st = document.getElementById('refineTemplateStatus');
        if (st) {
            st.style.color = ok ? 'var(--status-ok)' : 'var(--status-err)';
            st.textContent = (ok ? MSG.tplEditorSaveOk : MSG.tplEditorSaveFailed)
                + (message ? '：' + message : '');
        }
        const entrySt = document.querySelector('[data-testid="tpl-entry-status"]');
        if (entrySt) {
            entrySt.style.color = ok ? 'var(--status-ok)' : 'var(--status-err)';
            entrySt.textContent = (ok ? MSG.tplEditorSaveOk : MSG.tplEditorSaveFailed)
                + (message ? '：' + message : '');
        }
        if (ok) {
            this._edDirty = false;
            this._settle(false);            // 自动关闭（_resolve 收尾搬回节点）
        }
    },

    // 重载/切阶段（弹窗感知）：有未保存修改先同款确认，放行后执行原动作
    // （reload=列目录+按选中加载；change=按当前选中加载，语义同原绑定）
    editorRunStageChange(mode) {
        if (this._edSaving || this._edConfirming) return;
        const o = this._edOpts || {};
        const run = () => {
            const stage = (document.getElementById('refineTemplateStage') || {}).value;
            Promise.resolve(typeof o.onStageChange === 'function'
                ? o.onStageChange(stage, mode) : null).catch(() => {});
        };
        if (this._edDirty) {
            this._editorConfirmWhileOpen(MSG.tplEditorDirtyConfirm).then((ok) => {
                if (!ok) return;
                this._edDirty = false;
                const root = document.getElementById('appModal');
                if (root) root.style.display = 'flex';   // 放行后恢复弹窗与节点
                this._editorUnstash();
                run();
            });
            return;
        }
        run();
    },

    // 关闭收尾（_resolve 包装内调用）：节点搬回 vault + 骨架默认态恢复
    // （download 同款自清理：_open 不重置 okBtn.display/whiteSpace，防污染
    // 后续 alert/confirm/prompt）
    _editorTeardown() {
        this._editorStash();
        const root = document.getElementById('appModal');
        if (root) {
            const card = root.querySelector('.modal-card');
            if (card) card.classList.remove('modal-lg');
            const body = root.querySelector('.modal-body');
            if (body) {
                body.classList.remove('modal-editor-body');
                body.style.whiteSpace = '';
            }
            const okBtn = root.querySelector('.modal-ok');
            if (okBtn) okBtn.style.display = '';
        }
        this._edSaving = false;
        this._edConfirming = false;
    },

    // ============================================================
    // 模型管理模态（2.7.1 件3，D2026-1005-01 承接批）：AppModal kind='models'，
    // 720px .modal-lg（复用编辑器同款骨架扩宽）。body 全 createElement 注入
    // （全 class+data-testid，零新增 id/data-i18n）。
    // _settle 守卫隔离（评议 C3）：models kind 不复用 _dlRunning 布尔——
    // _settle 的 no-op 分支仅命中 download kind，models 关闭永不阻塞；
    // 下载由后端同步桥承载（关面板不终止），重开面板经
    // refine_asr_download_progress 快照恢复显示（进程内 _ASR_DOWNLOAD_PROGRESS）。
    // 布局：路径栏→未适配 banner→三档分组（档间可折叠）→模型行
    // （名称+描述+速度/精度五格点阵·静态评定+大小+下载按钮+推荐★）→
    // 变体行内展开→下载行内进度（.dl-progress-* 复用+前端增量 MB/s）→
    // 失败诊断网格（.dict-diag-grid 复用）。
    // 三态双门控：backend_state ready=绿 chip 可下载/adapter-needed=琥珀
    // 禁用+不入下拉/planned=灰禁用；verified==False 额外禁下载（件5 硬门槛）。
    // opts = {probe: <refine_asr_status 结果>, onFinished?: 下载收尾回调}
    // ============================================================
    models(opts) {
        if (this._busy) return Promise.resolve(false);      // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        const o = opts || {};
        const probe = o.probe || {};
        const api = window.pywebview && window.pywebview.api;
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = MSG.mpTitle;
        body.textContent = '';
        body.style.whiteSpace = 'normal';
        body.classList.add('mp-body');
        const card = root.querySelector('.modal-card');
        if (card) card.classList.add('modal-lg');
        input.style.display = 'none';
        okBtn.style.display = 'none';       // 关闭语义由取消键承载
        okBtn.textContent = '';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        this._bindSkeletonOnce(root);       // 2.8.0.2：唯一 kind 感知骨架绑定

        // —— 轮询登记表（关面板统一清理；进度数据在 _ASR_DOWNLOAD_PROGRESS）——
        const polls = {};
        const stopAllPolls = () => {
            Object.keys(polls).forEach((k) => {
                clearInterval(polls[k]);
                delete polls[k];
            });
        };

        const fmtMB = (n) => (n / 1048576).toFixed(1);
        // fmtGB 本地版：模块级同名函数在 RefineUI IIFE 闭包内（:4730），
        // AppModal 顶层对象不可见（黑盒抓缺陷：ReferenceError 中断面板渲染）
        const fmtGB = (n) => Math.round(n / 1073741824 * 10) / 10 + 'GB';
        const el = (tag, cls, text) => {
            const n = document.createElement(tag);
            if (cls) n.className = cls;
            if (text != null) n.textContent = text;
            return n;
        };

        // —— 路径栏（whisper 缓存+应用数据目录两行，各带「打开文件夹」）——
        const pathBox = el('div', 'mp-paths');
        [
            [MSG.mpPathWhisper, probe.cache_dir || ''],
            [MSG.mpPathData, probe.models_dir || ''],
        ].forEach(([label, dir]) => {
            const row = el('div', 'mp-path-row');
            row.appendChild(el('span', 'mp-path-label', label));
            const p = el('span', 'mp-path-val', dir);
            p.title = dir;
            row.appendChild(p);
            const btn = el('button', 'btn btn-ghost btn-compact mp-path-open',
                           MSG.mpOpenDir);
            btn.type = 'button';
            btn.addEventListener('click', () => {
                if (typeof openDir === 'function') openDir(dir);
            });
            row.appendChild(btn);
            pathBox.appendChild(row);
        });
        body.appendChild(pathBox);

        // —— 未适配 banner（探测到 N 个未适配模型时显示；全面板唯一长文案位）——
        const hf = probe.models_hf || [];
        if (hf.length) {
            body.appendChild(el('div', 'mp-banner hint-warn',
                                MSG.mpUnadaptedBanner(hf.length)));
        }

        // —— 模型行构造（三态双门控；下载行内进度+MB/s 增量；失败诊断网格）——
        const rowBind = {};     // name -> {startPolling, setPresent}
        const renderModelRow = (entry) => {
            const state = (entry.backend && entry.backend.state) || 'planned';
            const row = el('div', 'mp-row mp-row-' + state);
            row.dataset.mpModel = entry.name;
            // 名称行：名称+推荐★（内联 Lucide star，色 --warn）+三态 chip
            const head = el('div', 'mp-row-head');
            head.appendChild(el('span', 'mp-row-name', entry.name));
            if (entry.spec && entry.spec.recommend) {
                const star = el('span', 'mp-star');
                star.title = MSG.mpSpecNote;
                star.innerHTML = '<svg viewBox="0 0 24 24" width="13" height="13"'
                    + ' fill="var(--warn)" stroke="var(--warn)" stroke-width="1"'
                    + ' stroke-linecap="round" stroke-linejoin="round"'
                    + ' aria-hidden="true"><polygon points="12 2 15.09 8.26 22'
                    + ' 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2'
                    + ' 9.27 8.91 8.26 12 2"/></svg>';
                head.appendChild(star);
            }
            const chipCls = state === 'ready' ? 'mp-chip-ready'
                : (state === 'adapter-needed' ? 'mp-chip-adapter'
                   : 'mp-chip-planned');
            const chipLabel = state === 'ready' ? MSG.mpStateReady
                : (state === 'adapter-needed' ? MSG.mpStateAdapter
                   : MSG.mpStatePlanned);
            head.appendChild(el('span', 'mp-chip ' + chipCls, chipLabel));
            if (entry.present) head.appendChild(el('span', 'mp-present',
                                                   '✓ ' + MSG.mpStateReady));
            row.appendChild(head);
            if (entry.desc) row.appendChild(el('div', 'mp-row-desc',
                                               entry.desc));
            // 五格点阵（静态评定，标注非实测）：速度+精度两行
            const spec = entry.spec || {};
            const matrix = el('div', 'mp-dots-wrap');
            [['mpSpeedLabel', spec.speed], ['mpPrecisionLabel', spec.precision]]
              .forEach(([key, val]) => {
                const line = el('div', 'mp-dots-row');
                line.appendChild(el('span', 'mp-dots-label', MSG[key]));
                const dots = el('span', 'mp-dots');
                dots.dataset.mpSpecNote = MSG.mpSpecNote;
                for (let i = 1; i <= 5; i++) {
                    dots.appendChild(el('span', 'mp-dot'
                        + (i <= (val || 0) ? ' filled' : '')));
                }
                line.appendChild(dots);
                matrix.appendChild(line);
            });
            row.appendChild(matrix);
            // 元信息行：大小+变体行内展开
            const meta = el('div', 'mp-row-meta');
            if (entry.bytes) meta.appendChild(el('span', 'mp-size',
                                                 fmtGB(entry.bytes)));
            const variants = entry.variants || [];
            if (variants.length) {
                const det = el('details', 'mp-variants');
                det.appendChild(el('summary', 'mp-variants-summary',
                                   MSG.mpVariantsLabel + '（'
                                   + variants.length + '）'));
                variants.forEach((v) => {
                    const vRow = el('div', 'mp-variant-row');
                    vRow.appendChild(el('span', 'mp-variant-name', v.name));
                    const vOk = v.state === 'ready';
                    vRow.appendChild(el('span',
                        'mp-chip ' + (vOk ? 'mp-chip-ready'
                                          : 'mp-chip-adapter'),
                        (vOk ? '✓ ' : '') + (vOk ? MSG.mpStateReady
                                                 : MSG.mpStateAdapter)));
                    if (v.note) vRow.title = v.note;
                    det.appendChild(vRow);
                });
                meta.appendChild(det);
            }
            row.appendChild(meta);
            // 下载行内进度（复用 .dl-progress-*）+ 失败诊断网格
            const prog = el('div', 'dl-progress mp-progress');
            prog.style.display = 'none';
            const bar = el('div', 'dl-progress-bar');
            const fill = el('div', 'dl-progress-fill');
            bar.appendChild(fill);
            const text = el('div', 'dl-progress-text');
            prog.appendChild(bar);
            prog.appendChild(text);
            row.appendChild(prog);
            const diag = el('div', 'dict-diag-grid mp-diag');
            diag.style.display = 'none';
            const showDiag = (r) => {
                diag.textContent = '';
                const items = [
                    ['错误', (r && (r.error || r.message)) || ''],
                    ['模型', entry.name],
                    ['来源', (probe.python_source && probe.python) || ''],
                ];
                items.forEach(([k, v]) => {
                    if (!v) return;
                    diag.appendChild(el('span', 'k', k));
                    diag.appendChild(el('span', 'v', String(v)));
                });
                diag.style.display = diag.children.length ? '' : 'none';
            };
            row.appendChild(diag);
            // 下载按钮（三态双门控+verified 硬门槛）
            const actions = el('div', 'mp-row-actions');
            const dlBtn = el('button', 'btn btn-secondary btn-compact mp-dl-btn',
                             MSG.asrDownloadBtn);
            dlBtn.type = 'button';
            let dlRunning = false;
            const startPolling = () => {
                prog.style.display = '';
                let lastBytes = 0;
                let lastT = 0;
                const poll = setInterval(async () => {
                    if (!api || !api.refine_asr_download_progress) return;
                    try {
                        const p = await api
                          .refine_asr_download_progress(entry.model
                                                        || entry.name);
                        if (!(p && p.success && p.phase)) return;
                        if (p.phase === 'download' && p.total) {
                            bar.classList.remove('indeterminate');
                            const dl = p.downloaded || 0;
                            fill.style.width = Math.min(100, Math.round(
                                dl / p.total * 100)) + '%';
                            let speed = '';
                            if (lastT && dl >= lastBytes) {
                                const dt = (Date.now() - lastT) / 1000;
                                if (dt > 0) {
                                    speed = '｜' + ((dl - lastBytes)
                                        / 1048576 / dt).toFixed(1) + 'MB/s';
                                }
                            }
                            lastBytes = dl;
                            lastT = Date.now();
                            text.textContent = fmtMB(dl) + '/'
                                + fmtMB(p.total) + 'MB' + speed
                                + (p.note ? '｜' + p.note : '');
                        } else if (p.phase === 'verify') {
                            bar.classList.add('indeterminate');
                            text.textContent = MSG.dict_verify
                                + (p.note ? '｜' + p.note : '');
                        } else if (p.phase === 'done') {
                            bar.classList.remove('indeterminate');
                            fill.style.width = '100%';
                            text.textContent = MSG.asrDlDone;
                        } else if (p.phase === 'failed') {
                            bar.classList.add('indeterminate');
                            text.textContent = MSG.asrDlFailed
                                + (p.error ? '：' + p.error : '');
                            showDiag(p);
                        }
                    } catch (e) { /* 进度轮询失败不干扰主流程 */ }
                }, 1000);
                polls[entry.name] = poll;
            };
            const finishOk = () => {
                dlRunning = false;
                prog.style.display = 'none';
                dlBtn.style.display = 'none';
                if (!entry.present) {
                    entry.present = true;
                    head.appendChild(el('span', 'mp-present',
                                        '✓ ' + MSG.mpStateReady));
                }
                if (typeof o.onFinished === 'function') o.onFinished();
            };
            const finishFail = (r) => {
                dlRunning = false;
                if (dlBtn) dlBtn.disabled = false;
                bar.classList.add('indeterminate');
                text.textContent = MSG.asrDlFailed + '：'
                    + ((r && (r.error || r.message)) || MSG.unknown);
                showDiag(r);
                if (typeof o.onFinished === 'function') o.onFinished();
            };
            dlBtn.addEventListener('click', () => {
                if (dlRunning || !api || !api.refine_asr_download) return;
                dlRunning = true;
                dlBtn.disabled = true;
                startPolling();
                api.refine_asr_download(entry.model || entry.name, 'auto')
                  .then((r) => {
                      const p = polls[entry.name];
                      if (p) { clearInterval(p); delete polls[entry.name]; }
                      if (r && r.success) finishOk(); else finishFail(r);
                  })
                  .catch((e) => {
                      const p = polls[entry.name];
                      if (p) { clearInterval(p); delete polls[entry.name]; }
                      finishFail(e);
                  });
            });
            if (entry.present) {
                dlBtn.style.display = 'none';       // 已就位：无下载入口
            } else if (state === 'planned') {
                dlBtn.disabled = true;
                dlBtn.title = MSG.mpPlannedTitle;
            } else if (state !== 'ready') {
                dlBtn.disabled = true;
                dlBtn.title = MSG.mpAdapterTitle;
            } else if (entry.verified !== true) {
                dlBtn.disabled = true;              // 件5 硬门槛：未核验禁下载
                dlBtn.title = MSG.mpUnverifiedTitle;
            }
            actions.appendChild(dlBtn);
            row.appendChild(actions);
            rowBind[entry.name] = { startPolling };
            return row;
        };

        // —— 三档分组（档间可折叠 details；分组=分页等效，owner 拍板）——
        const TIERS = [
            ['fast', MSG.mpTierFast],
            ['balanced', MSG.mpTierBalanced],
            ['precise', MSG.mpTierPrecise],
        ];
        const recs = probe.recommended || [];
        let rowsBuilt = 0;
        TIERS.forEach(([tier, label]) => {
            const items = recs.filter((e) => (e.tier || '') === tier);
            if (!items.length) return;
            const det = el('details', 'mp-tier');
            det.open = true;
            const sum = el('summary', 'mp-tier-head');
            sum.appendChild(el('span', 'mp-tier-name', label));
            det.appendChild(sum);
            items.forEach((entry) => {
                det.appendChild(renderModelRow(entry));
                rowsBuilt++;
            });
            body.appendChild(det);
        });
        if (!rowsBuilt) {
            body.appendChild(el('div', 'muted', MSG.mpNeedProbe));
        }

        // —— 重开恢复：逐条查下载进度快照，下载中/校验中→恢复轮询显示 ——
        if (api && api.refine_asr_download_progress) {
            recs.forEach((entry) => {
                const bind = rowBind[entry.name];
                if (!bind) return;
                api.refine_asr_download_progress(
                    entry.model || entry.name).then((p) => {
                    if (p && p.success
                            && (p.phase === 'download'
                                || p.phase === 'verify')) {
                        bind.startPolling();
                    }
                }).catch(() => { /* 恢复失败静默（下次轮询自愈） */ });
            });
        }

        // 收口：关面板恢复骨架默认态（modal-lg/mp-body 自清理）+轮询清理；
        // 下载本身由后端桥承载，关面板不终止（评议 C3 隔离的关键语义）
        this._busy = true;
        this._kind = 'models';
        root.style.display = 'flex';
        return new Promise((resolve) => {
            this._resolve = (value) => {
                stopAllPolls();
                const card2 = root.querySelector('.modal-card');
                if (card2) card2.classList.remove('modal-lg');
                const body2 = root.querySelector('.modal-body');
                if (body2) body2.classList.remove('mp-body');
                if (okBtn) okBtn.style.display = '';
                resolve(value);
            };
        });
    },

    // ============================================================
    // 压制参数弹窗（2.8.0 批1 件5，D2026-1007-03）：kind='encode' 三分区
    // 容器（批1/批2 共用骨架，开工门 C8——高级区批1 置空禁用占位，批2
    // 扩展不重建）。body 全 createElement 注入（全 class+data-testid，
    // 零新增 id/data-i18n）。ok/Enter 走 _bindSkeletonOnce 统一 kind 感知
    // 绑定（2.8.0.2：_okValue encode 分支 → _settle({ok:true, params:
    // collect()})，collect 闭包经 _encodeCollect 暴露、结算置 null）；
    // resolve 包装器保持 {ok, params}/null 形态。取消/ESC/遮罩=resolve(null)。
    // opts = {jobs:[{name, out_path, eta_s, video_exists, subtitle_exists}],
    //         totalEtaS, last:<encode_get_last_params 的 params>}
    // 参数编辑模式（D2026-1008-01 批2：压制参数独立设置项）：opts.editOnly
    // =true 时无选中文件也可打开——标题改「压制参数」、jobsLine 换编辑
    // 提示、「加入压制队列」确认键隐藏，另设「保存参数」按钮（状态行给
    // 成功/失败反馈，成功经 o.onSaved 回调同步调用方 _lastParams 缓存与
    // 摘要行）；保存只走 encode_save_params 桥，绝不触碰 preflight/commit/
    // jobs（Enter=关闭不保存，保存只经「保存参数」按钮，失败反馈留状态行）。
    // GPU 可用性无独立探测桥（仅 preflight 顺带双检），编辑模式 GPU 选项
    // 保持置灰并以 title 显因（encodeGpuEditTitle）。
    // ============================================================
    encode(opts) {
        if (this._busy) return Promise.resolve(null);       // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(null);            // 骨架缺席兜底
        const o = opts || {};
        const editOnly = !!o.editOnly;
        const jobs = o.jobs || [];
        const api = window.pywebview && window.pywebview.api;   // 预设通道（models 先例）
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent =
            editOnly ? MSG.encodeEditTitle : MSG.encodeModalTitle;
        body.textContent = '';
        body.style.whiteSpace = 'normal';
        input.style.display = 'none';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        // 编辑模式：隐藏「加入压制队列」（开始压制仅存于正常模式），
        // 另设「保存参数」按钮于分区 3 尾部（下文 saveParamsBtn）
        okBtn.style.display = editOnly ? 'none' : '';
        okBtn.textContent = MSG.encodeOk + '（' + jobs.length + '）';
        this._bindSkeletonOnce(root);       // 2.8.0.2：唯一 kind 感知骨架绑定
        const last = o.last || {};

        const mk = (tag, cls, parent) => {
            const el = document.createElement(tag);
            if (cls) el.className = cls;
            if (parent) parent.appendChild(el);
            return el;
        };
        const mkField = (parent, text) => {
            const w = mk('div', 'enc-field', parent);
            const lb = mk('label', null, w);
            lb.textContent = text;
            return w;
        };
        const mkSelect = (parent, options, value) => {
            const s = mk('select', 'form-select', parent);
            options.forEach((op) => {
                const opt = document.createElement('option');
                opt.value = op.v;
                opt.textContent = op.t;
                if (op.disabled) opt.disabled = true;
                s.appendChild(opt);
            });
            if (value) s.value = value;
            return s;
        };

        // 任务概览行（编辑模式换编辑提示：本弹窗只存参数不入队）
        const jobsLine = mk('div', 'enc-jobs-line', body);
        jobsLine.textContent = editOnly
            ? MSG.encodeEditHint
            : MSG.encodeJobsLine.replace('{n}', String(jobs.length));

        // —— 分区 1：基础 ——
        const sec1 = mk('div', 'enc-section', body);
        mk('h4', null, sec1).textContent = MSG.encodeSecBase;
        const grid1 = mk('div', 'enc-grid', sec1);
        const elFmt = mkSelect(mkField(grid1, MSG.encodeModalFmt), [
            { v: 'h264', t: MSG.encodeFmtH264 },
            { v: 'h265', t: MSG.encodeFmtH265 },
            { v: 'av1', t: MSG.encodeFmtAv1 },
        ], last.video_format || 'h264');
        // 后端（批2）：GPU 编码器经供给层双检解析——可用则点亮并显名，
        // 不可用保持禁用并以 title 透出逐候选显因（A9 不静默降级）
        const gpuEnc = (o.gpu && o.gpu.encoder) || "";
        const elBackend = mkSelect(mkField(grid1, MSG.encodeModalBackend), [
            { v: 'auto', t: MSG.encodeBackendAuto },
            { v: 'cpu', t: 'CPU' },
            { v: 'gpu', t: gpuEnc ? ('GPU（' + gpuEnc + '）') : MSG.encodeBackendGpu,
              disabled: !gpuEnc },
        ], 'auto');
        if (!gpuEnc && o.gpu && o.gpu.reasons && o.gpu.reasons.length) {
            elBackend.title = o.gpu.reasons.join('；');
        }
        // 编辑模式无 preflight（不触碰）→ GPU 可用性无从探测：选项置灰
        // 并以 title 显因（发起一次压制后经预检自动检测点亮）
        if (editOnly && !gpuEnc) {
            elBackend.title = MSG.encodeGpuEditTitle;
        }
        const elQuality = mkSelect(mkField(grid1, MSG.encodeModalQuality), [
            { v: 'compress', t: MSG.encodeQCompress },
            { v: 'balanced', t: MSG.encodeQBalanced },
            { v: 'quality', t: MSG.encodeQQuality },
        ], last.quality || 'balanced');
        const elRes = mkSelect(mkField(grid1, MSG.encodeModalRes), [
            { v: 'original', t: MSG.encodeResOriginal },
            { v: '720p', t: '720p' },
            { v: '1080p', t: '1080p' },
            { v: '1440p', t: '1440p' },
            { v: '2160p', t: '2160p' },
        ], last.resolution || 'original');
        const elRate = mkSelect(mkField(grid1, MSG.encodeModalRate), [
            { v: 'quality_tier', t: MSG.encodeRateTier },
            { v: 'target_vbr', t: MSG.encodeRateVbr },
        ], last.rate_mode || 'quality_tier');
        const bitField = mkField(grid1, MSG.encodeModalBitrate);
        const elBitrate = mk('input', 'form-input', bitField);
        elBitrate.type = 'number';
        elBitrate.min = '100';
        elBitrate.style.display = elRate.value === 'target_vbr' ? '' : 'none';
        if (last.target_bitrate_kbps) elBitrate.value = String(last.target_bitrate_kbps);
        elRate.addEventListener('change', () => {
            elBitrate.style.display = elRate.value === 'target_vbr' ? '' : 'none';
        });
        const outField = mkField(grid1, MSG.encodeModalOutDir);
        outField.classList.add('full');
        const elOutDir = mk('input', 'form-input', outField);
        elOutDir.type = 'text';
        elOutDir.placeholder = 'D:\\Videos';
        if (last.out_dir) elOutDir.value = String(last.out_dir);
        // 长任务硬性规定①（E3 批1 落点）：预估行（编辑模式不发起压制，
        // 预估无意义 → 整行隐藏）
        const etaRow = mk('div', 'enc-eta-row', sec1);
        if (editOnly) {
            etaRow.style.display = 'none';
        } else if (o.totalEtaS && o.totalEtaS > 0) {
            etaRow.textContent = '⏱ ' + MSG.encodeEtaTotal
                .replace('{t}', Math.max(1, Math.round(o.totalEtaS / 60)) + ' ' + '分');
        } else {
            etaRow.textContent = '⏱ ' + MSG.encodeEtaNone;
        }
        // 长任务硬性规定③（E3 批2 落点）：AV1 警告条（预期管理）
        const av1Warn = mk('div', 'enc-eta-row', sec1);
        av1Warn.style.background = 'var(--warn-soft)';
        av1Warn.style.display = 'none';
        av1Warn.textContent = '⚠ ' + MSG.encodeAv1Warn;
        elFmt.addEventListener('change', () => {
            av1Warn.style.display = elFmt.value === 'av1' ? '' : 'none';
        });
        if (elFmt.value === 'av1') av1Warn.style.display = '';

        // —— 分区 2：字幕与音频 ——
        const sec2 = mk('div', 'enc-section', body);
        mk('h4', null, sec2).textContent = MSG.encodeSecSubAudio;
        const grid2 = mk('div', 'enc-grid', sec2);
        const elFont = mk('input', 'form-input', mkField(grid2, MSG.encodeModalFont));
        elFont.type = 'number';
        elFont.min = '12';
        elFont.max = '72';
        elFont.value = String(last.font_size || 22);
        const elAudio = mkSelect(mkField(grid2, MSG.encodeModalAudio), [
            { v: 'copy', t: MSG.encodeAudioCopy },
            { v: '96k', t: 'AAC 96k' },
            { v: '128k', t: 'AAC 128k' },
            { v: '192k', t: 'AAC 192k' },
        ], last.audio_mode || 'copy');
        const enhWrap = mk('div', 'enc-field full', grid2);
        const enhLabel = mk('label', null, enhWrap);
        const elEnhance = mk('input', null, enhLabel);
        elEnhance.type = 'checkbox';
        elEnhance.checked = last.enhance_on !== false;
        enhLabel.appendChild(document.createTextNode(' ' + MSG.encodeModalEnhance));
        // 批3 增强链旋钮（决策九-1 C3''：缺省=owner AV1 链，可调随预设存取；
        // 三旋钮映射 hqdn3d 降噪主强度/deblock alpha/unsharp luma amount；
        // 初值从 last.enhance_params 解析——预设与上次参数同源）
        const knob0 = (s, i, dft) => {
            const v = parseFloat(String(s || '').split(':')[i]);
            return isNaN(v) ? dft : v;
        };
        const lastEp = last.enhance_params || {};
        const knobRow = mk('div', 'enc-field full', grid2);
        knobRow.style.display = 'grid';
        knobRow.style.gridTemplateColumns = '1fr 1fr 1fr';
        knobRow.style.gap = '8px';
        const mkKnob = (labelText, min, max, step, val) => {
            const w = mk('div', null, knobRow);
            const lb = mk('label', null, w);
            lb.textContent = labelText;
            const inp = mk('input', 'form-input', w);
            inp.type = 'number';
            inp.min = String(min);
            inp.max = String(max);
            inp.step = String(step);
            inp.value = String(val);
            return inp;
        };
        const knobDenoise = mkKnob(MSG.encodeKnobDenoise, 0, 10, 0.1,
            knob0(lastEp.hqdn3d, 0, 0.8));
        const knobDeblock = mkKnob(MSG.encodeKnobDeblock, 0, 1, 0.01,
            knob0(String(lastEp.deblock || '').replace('alpha=', ''), 0, 0.07));
        const knobSharpen = mkKnob(MSG.encodeKnobSharpen, 0, 2, 0.05,
            knob0(lastEp.unsharp, 2, 0.5));
        const syncKnobs = () => {
            const dis = !elEnhance.checked;
            [knobDenoise, knobDeblock, knobSharpen].forEach((k) => { k.disabled = dis; });
        };
        elEnhance.addEventListener('change', syncKnobs);
        syncKnobs();
        // 批3 音量旋钮（±12dB 受控；≠0 强制 aac 重编码——后端回落显因透出）
        const volField = mkField(grid2, MSG.encodeKnobVolume);
        const elVolume = mk('input', 'form-input', volField);
        elVolume.type = 'number';
        elVolume.min = '-12';
        elVolume.max = '12';
        elVolume.step = '0.5';
        elVolume.value = String(typeof last.volume_db === 'number' ? last.volume_db : 0);

        // —— 分区 3：高级（批2 启用：预设管理+自定义参数逃生门；增强链
        //     参数旋钮归批3）——
        const sec3 = mk('div', 'enc-section', body);
        mk('h4', null, sec3).textContent = MSG.encodeModalAdvanced;
        const grid3 = mk('div', 'enc-grid', sec3);
        const presetField = mkField(grid3, MSG.encodePresetLabel);
        presetField.classList.add('full');
        const presetRow = mk('div', null, presetField);
        presetRow.style.display = 'flex';
        presetRow.style.gap = '6px';
        const elPreset = mk('select', 'form-select', presetRow);
        const saveBtn = mk('button', 'btn btn-secondary btn-compact', presetRow);
        saveBtn.type = 'button';
        saveBtn.textContent = MSG.encodePresetSave;
        const delBtn = mk('button', 'btn btn-ghost btn-compact', presetRow);
        delBtn.type = 'button';
        delBtn.textContent = MSG.encodePresetDelete;
        const cpField = mkField(grid3, MSG.encodeCustomLabel);
        cpField.classList.add('full');
        const elCustom = mk('textarea', 'form-input', cpField);
        elCustom.rows = 2;
        elCustom.placeholder = MSG.encodeCustomHint;
        if (last.custom_params) elCustom.value = String(last.custom_params);

        // —— 参数编辑模式（D2026-1008-01 批2）专属尾部：状态行+「保存参数」
        // ——保存=collect()→encode_save_params 桥（后端同一校验路径+原子写
        // hardsub_last.json）；成功经 o.onSaved 同步调用方 _lastParams 缓存
        // 与高级参数页摘要行，状态行人话反馈；绝不触碰 preflight/commit/jobs
        const saveStatus = editOnly ? mk('div', 'enc-eta-row enc-edit-status', body) : null;
        const saveParamsBtn = editOnly
            ? mk('button', 'btn btn-secondary btn-compact enc-save-params-btn', body) : null;
        const saveEditParams = async () => {
            if (!api) return false;
            const params = collect();
            saveParamsBtn.disabled = true;
            let r = null;
            try {
                r = await api.encode_save_params(JSON.stringify(params));
            } catch (e) {
                r = { success: false, error: String(e) };
            }
            saveParamsBtn.disabled = false;
            if (r && r.success) {
                if (typeof o.onSaved === 'function') o.onSaved(params);
                saveStatus.textContent = MSG.encodeParamsSaved;
                return true;
            }
            const why = (r && (r.tip || r.error)) || String(r);
            saveStatus.textContent = MSG.encodeParamsSaveFail.replace('{e}', why);
            return false;
        };
        if (editOnly) {
            saveParamsBtn.type = 'button';
            saveParamsBtn.textContent = MSG.encodeSaveParams;
            saveParamsBtn.addEventListener('click', () => { saveEditParams(); });
        }

        // 表单值回填（预设加载用；字段全集=collect 快照）
        const applyParams = (p) => {
            p = p || {};
            if (p.video_format) elFmt.value = p.video_format;
            // backend 回填（批2 顺修）：用户预设含 backend 快照，gpu 仅在
            // 探测已知可用时恢复（collect 同口径），cpu 显式恢复，其余/缺省
            // 落回 auto——与 collect 读取逻辑镜像
            if (p.backend) {
                elBackend.value = (p.backend === 'gpu' && gpuEnc) ? 'gpu'
                    : (p.backend === 'cpu' ? 'cpu' : 'auto');
            }
            if (p.quality) elQuality.value = p.quality;
            if (p.resolution) elRes.value = p.resolution;
            if (p.rate_mode) elRate.value = p.rate_mode;
            elBitrate.style.display = elRate.value === 'target_vbr' ? '' : 'none';
            if (p.target_bitrate_kbps) elBitrate.value = String(p.target_bitrate_kbps);
            if (p.audio_mode) elAudio.value = p.audio_mode;
            if (p.font_size) elFont.value = String(p.font_size);
            if (typeof p.enhance_on === 'boolean') elEnhance.checked = p.enhance_on;
            if (p.enhance_params) {
                const ep = p.enhance_params;
                if (String(ep.hqdn3d || '').length) knobDenoise.value = knob0(ep.hqdn3d, 0, 0.8);
                if (String(ep.deblock || '').length) {
                    knobDeblock.value = knob0(String(ep.deblock).replace('alpha=', ''), 0, 0.07);
                }
                if (String(ep.unsharp || '').length) knobSharpen.value = knob0(ep.unsharp, 2, 0.5);
            }
            if (typeof p.volume_db === 'number') elVolume.value = String(p.volume_db);
            if (typeof p.custom_params === 'string') elCustom.value = p.custom_params;
            av1Warn.style.display = elFmt.value === 'av1' ? '' : 'none';
            syncKnobs();
        };
        const fillPresets = async () => {
            let pl = null;
            try { pl = await api.encode_presets_list(); } catch (e) { pl = null; }
            elPreset.textContent = '';
            if (pl && pl.success) {
                const g1 = document.createElement('optgroup');
                g1.label = MSG.encodePresetBuiltinGroup;
                (pl.builtin || []).forEach((p) => {
                    const op = document.createElement('option');
                    op.value = '__b__:' + p.name;
                    op.textContent = p.name;
                    g1.appendChild(op);
                });
                elPreset.appendChild(g1);
                const names = Object.keys(pl.user || {});
                if (names.length) {
                    const g2 = document.createElement('optgroup');
                    g2.label = MSG.encodePresetUserGroup;
                    names.forEach((n) => {
                        const op = document.createElement('option');
                        op.value = '__u__:' + n;
                        op.textContent = n;
                        g2.appendChild(op);
                    });
                    elPreset.appendChild(g2);
                }
            }
        };
        elPreset.addEventListener('change', async () => {
            const v = elPreset.value || '';
            if (v.startsWith('__b__:')) {
                let pl = null;
                try { pl = await api.encode_presets_list(); } catch (e) { return; }
                const hit = (pl.builtin || []).find((p) => p.name === v.slice(6));
                if (hit) applyParams(hit.params);
            } else if (v.startsWith('__u__:')) {
                let pl = null;
                try { pl = await api.encode_presets_list(); } catch (e) { return; }
                const hit = (pl.user || {})[v.slice(6)];
                if (hit) applyParams(hit);
            }
        });
        saveBtn.addEventListener('click', async () => {
            const name = await AppModal.prompt(MSG.encodePresetNamePrompt, '');
            if (!name || !String(name).trim()) return;
            try {
                const r = await api.encode_preset_save(String(name).trim(), collect());
                if (r && r.success) await fillPresets();
                AppModal.alert(MSG.encodeModalTitle,
                    r && r.success ? MSG.encodePresetSaved : String(r && r.error || ''));
            } catch (e) {
                AppModal.alert(MSG.encodeModalTitle, String(e));
            }
        });
        delBtn.addEventListener('click', async () => {
            const v = elPreset.value || '';
            if (!v.startsWith('__u__:')) return;   // 内置三档不可删
            const name = v.slice(6);
            const ok = await AppModal.confirm(
                MSG.encodeModalTitle, MSG.encodePresetDeleteConfirm.replace('{n}', name));
            if (!ok) return;
            try {
                const r = await api.encode_preset_delete(name);
                if (r && r.success) await fillPresets();
            } catch (e) { /* 下次打开自愈 */ }
        });
        fillPresets();

        const collect = () => ({
            video_format: elFmt.value,
            backend: elBackend.value === 'gpu' && gpuEnc ? 'gpu' : 'auto',
            quality: elQuality.value,
            resolution: elRes.value,
            rate_mode: elRate.value,
            target_bitrate_kbps: elRate.value === 'target_vbr'
                ? (parseInt(elBitrate.value, 10) || null) : null,
            audio_mode: elAudio.value,
            font_size: Math.min(72, Math.max(12, parseInt(elFont.value, 10) || 22)),
            enhance_on: elEnhance.checked,
            enhance_params: {
                hqdn3d: knobDenoise.value + ':0.6:0.7:0.6',
                deblock: 'alpha=' + knobDeblock.value + ':beta=0.07',
                unsharp: '5:5:' + knobSharpen.value + ':3:3:0.3',
            },
            volume_db: Math.max(-12, Math.min(12, parseFloat(elVolume.value) || 0)),
            out_dir: elOutDir.value.trim(),
            custom_params: elCustom.value.trim(),
        });
        // 2.8.0.2：闭包 collect 暴露给统一骨架 ok/Enter 分派（_okValue 的
        // encode 分支），结算经 _resolve 包装器置 null 防悬挂引用
        this._encodeCollect = collect;

        this._busy = true;
        this._kind = 'encode';
        root.style.display = 'flex';
        return new Promise((resolve) => {
            this._resolve = (value) => {
                this._encodeCollect = null;
                // truthy（确认键/Enter，统一分派已按当前表单结算 {ok,params}）
                // → 按当前表单值结算；falsy（取消/ESC/遮罩）→ null。
                // 编辑模式确认键隐藏、Enter=关闭（返回值弃置不保存，保存只经
                // 「保存参数」按钮——失败反馈须留在可见状态行，结算后弹窗已收起）
                resolve(value ? { ok: true, params: collect() } : null);
            };
        });
    },

    // ============================================================
    // 字幕清洗参数弹窗（D2026-1024-01 批2 件A）：照 encode kind 先例
    // （mk/mkField/mkSelect 闭包 + _bindSkeletonOnce 统一骨架绑定，复用
    // #appModal 骨架），压制式弹出·单滚动分区纵排（v4 原型终裁）。
    // 布局：jobs-line + 分区一「文本规范」（6 参数）+ 分区二「时间轴」
    // （3 参数+口径提示行）；开关两枚照 encode 增强开关 .enc-field.full
    // 内联 label 画法（pp-toggle-cell.full 同栅格语义）。
    // 零 id（骨架既有 id 之外零新增）、文案全 MSG 键（批2 卡面照抄）。
    // 结算：保存（ok 键/Enter）={ok:true, params}；取消/ESC/遮罩={ok:false}；
    // 打开时从 opts.last 回填（当前会话已应用参数，缺省=全默认）。
    // ============================================================
    polish(opts) {
        if (this._busy) return Promise.resolve({ ok: false });  // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve({ ok: false });       // 骨架缺席兜底
        const last = (opts && opts.last) || {};
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = MSG.polishPopupTitle;
        // 标题行内缀 PROVISIONAL 徽章（原型同位；textContent 已清空旧子节点）
        const titleEl = root.querySelector('.modal-title');
        titleEl.appendChild(document.createTextNode(' '));
        const badge = document.createElement('span');
        badge.className = 'tag-provisional';
        badge.textContent = MSG.polishAdvBadge;
        titleEl.appendChild(badge);
        body.textContent = '';
        body.style.whiteSpace = 'normal';
        input.style.display = 'none';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        okBtn.style.display = '';
        okBtn.textContent = MSG.polishPopupSave;
        this._bindSkeletonOnce(root);       // 2.8.0.2：唯一 kind 感知骨架绑定

        const mk = (tag, cls, parent) => {
            const el = document.createElement(tag);
            if (cls) el.className = cls;
            if (parent) parent.appendChild(el);
            return el;
        };
        const mkField = (parent, text) => {
            const w = mk('div', 'enc-field', parent);
            const lb = mk('label', null, w);
            lb.textContent = text;
            return w;
        };
        const mkSelect = (parent, options, value) => {
            const s = mk('select', 'form-select', parent);
            options.forEach((op) => {
                const opt = document.createElement('option');
                opt.value = op.v;
                opt.textContent = op.t;
                s.appendChild(opt);
            });
            if (value) s.value = value;
            return s;
        };
        const mkNote = (parent, text) => {
            mk('div', 'pp-note', parent).textContent = text;
        };
        // 数值输入格：label + number 输入 + 灰字小注（原型 .enc-field 同构）
        const mkNumber = (parent, labelText, ph, min, max, step, val, note) => {
            const w = mkField(parent, labelText);
            const inp = mk('input', 'form-input', w);
            inp.type = 'number';
            inp.min = String(min);
            inp.max = String(max);
            inp.step = String(step);
            inp.placeholder = ph;
            inp.value = val || '';
            mkNote(w, note);
            return inp;
        };
        // 下拉格：label + select + 灰字小注
        const mkSelectField = (parent, labelText, options, value, note) => {
            const w = mkField(parent, labelText);
            const s = mkSelect(w, options, value);
            mkNote(w, note);
            return s;
        };
        // 开关格（原型 pp-toggle-cell.full）：整行 label 内联 checkbox + 小注
        const mkToggle = (parent, labelText, note, checked) => {
            const cell = mk('div', 'pp-toggle-cell full', parent);
            const lb = mk('label', 'pp-toggle', cell);
            const inp = mk('input', null, lb);
            inp.type = 'checkbox';
            inp.checked = checked;
            lb.appendChild(document.createTextNode(' ' + labelText));
            mkNote(cell, note);
            return inp;
        };

        const jobsLine = mk('div', 'enc-jobs-line', body);
        jobsLine.textContent = MSG.polishPopupJobsLine;

        // —— 分区一：文本规范（6 参数）——
        const sec1 = mk('div', 'enc-section', body);
        mk('h4', null, sec1).textContent = MSG.polishPopupSecText;
        const grid1 = mk('div', 'enc-grid', sec1);
        const elMaxChars = mkNumber(grid1, MSG.polishLblMaxChars,
            MSG.polishPhMaxChars, 1, 40, 1, last.max_line_chars,
            MSG.polishNoteMaxChars);
        const elMaxLines = mkNumber(grid1, MSG.polishLblMaxLines,
            MSG.polishPhMaxLines, 1, 4, 1, last.max_lines,
            MSG.polishNoteMaxLines);
        const elQuote = mkSelectField(grid1, MSG.polishLblQuoteStyle, [
            { v: 'default', t: MSG.polishQuoteDefault },
            { v: 'keep', t: MSG.polishQuoteKeep },
            { v: 'curly', t: MSG.polishQuoteCurly },
        ], last.quote_style || 'default', MSG.polishNoteQuoteStyle);
        const elPeriod = mkSelectField(grid1, MSG.polishLblStripPeriod, [
            { v: 'default', t: MSG.polishPeriodDefault },
            { v: 'keep', t: MSG.polishPeriodKeep },
        ], 'default', MSG.polishNoteStripPeriod);
        const elGt = mkSelectField(grid1, MSG.polishLblDialogGt, [
            { v: 'default', t: MSG.polishGtDefault },
            { v: 'remove', t: MSG.polishGtRemove },
        ], 'default', MSG.polishNoteDialogGt);
        const elRewrap = mkToggle(grid1, MSG.polishLblRewrap, MSG.polishNoteRewrap,
            last.rewrap_enabled !== false);

        // —— 分区二：时间轴（3 参数+口径提示行）——
        const sec2 = mk('div', 'enc-section', body);
        mk('h4', null, sec2).textContent = MSG.polishPopupSecTiming;
        const grid2 = mk('div', 'enc-grid', sec2);
        const elMaxDur = mkNumber(grid2, MSG.polishLblMaxDur,
            MSG.polishPhMaxDur, 0, 60000, 100, last.max_duration_ms,
            MSG.polishNoteMaxDur);
        const elMinGap = mkNumber(grid2, MSG.polishLblMinGap,
            MSG.polishPhMinGap, 0, 5000, 0.1, last.min_gap_ms,
            MSG.polishNoteMinGap);
        const elClamp = mkToggle(grid2, MSG.polishLblClampLong, MSG.polishNoteClampLong,
            last.clamp_long_enabled !== false);
        mk('div', 'enc-eta-row', sec2).textContent = MSG.polishTimingCaliber;

        const collect = () => ({
            max_line_chars: elMaxChars.value.trim(),
            max_lines: elMaxLines.value.trim(),
            quote_style: elQuote.value,
            keep_final_period: elPeriod.value === 'keep',
            remove_dialogue_gt: elGt.value === 'remove',
            rewrap_enabled: elRewrap.checked,
            max_duration_ms: elMaxDur.value.trim(),
            min_gap_ms: elMinGap.value.trim(),
            clamp_long_enabled: elClamp.checked,
        });
        // 同 encode 先例：闭包 collect 暴露给统一骨架 ok/Enter 分派
        this._polishCollect = collect;

        this._busy = true;
        this._kind = 'polish';
        root.style.display = 'flex';
        return new Promise((resolve) => {
            this._resolve = (value) => {
                this._polishCollect = null;
                // truthy（保存键/Enter，统一分派已按当前表单结算 {ok,params}）
                // → 按当前表单值结算；falsy（取消/ESC/遮罩）→ {ok:false}。
                resolve(value ? { ok: true, params: collect() } : { ok: false });
            };
        });
    },

    // ============================================================
    // 批量修复确认框（2.7.4 件3，D2026-1007-01）：结构化确认弹窗，取代
    // batchFixRun 原纯文本 AppModal.confirm（slice(0,10) 只列前 10 条）。
    // 复用 #appModal 骨架 + _bindSkeletonOnce 统一骨架绑定（2.8.0.2：
    // Enter=确认/ESC=取消/遮罩=取消，kind 感知分派语义不变）；
    // kind='batchfix' 不命中 _settle 任何阻塞分支（_dlRunning/_edSaving
    // 仅 download/editor kind），关闭永不阻塞。
    // 结算三态（钉）：确认键/Enter=resolve(true)；取消键/ESC/遮罩点击=
    // resolve(false)；_busy 重入=立即 resolve(false)（单例不叠加）。
    // 布局：.modal-lg 配方（编辑器同款）——.bfp-meta/.bfp-cats 固定不
    // 滚动，仅 .bfp-list 滚动（flex:1;min-height:0;overflow-y:auto），
    // 按钮区在 .modal-card 弹性列内恒可见（窄窗滚到底确认键仍在）。
    // 列表容器零键盘监听：不拦截 keydown/不 stopPropagation，Enter/Esc
    // 语义保持 document 全局（列表滚动由鼠标滚轮承载）。
    // 现译全文：texts 由调用方从 lastGuideData.items 构建（前端经
    // read_output_artifact 已持有导读 json；后端 action_items 摘录限长
    // 仅约束回包形状）——按 Number(it.index) 强转匹配（后端 idx 非 int
    // 回 null，先判 null 再强转防 Number(null)=0 陷阱），查无全文回退
    // it.excerpt 并带「仅摘录」标记；DOM 放全文不 JS 切字符串（防代理对
    // 切半），CSS max-height 3 行折叠（底部渐隐 mask 提示截断；Chromium
    // 146 实测 -webkit-line-clamp 被重映射为 flow-root 失效，故弃用）
    // + 逐条展开/收起键 + title 悬停全文。
    // opts = {title, okText?, meta:[{text,warn?}], cats:[{cat,count}],
    //         head, items:[{index,category,timing,excerpt}], texts:{idx:text}}
    // body 全 createElement 注入（FROZEN_IDS 冻结：零新增 id/data-i18n）；
    // 关闭自清理 modal-lg/whiteSpace（editor 同款，防污染后续 confirm）。
    // ============================================================
    batchFixPreview(opts) {
        if (this._busy) return Promise.resolve(false);      // 重入=取消结算
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        const o = opts || {};
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = o.title || '';
        body.textContent = '';
        body.style.whiteSpace = 'normal';   // .modal-card .modal-body 默认 pre-wrap
        const card = root.querySelector('.modal-card');
        if (card) card.classList.add('modal-lg');
        input.style.display = 'none';
        okBtn.style.display = '';
        okBtn.textContent = o.okText || MSG.ui_ok;
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        this._bindSkeletonOnce(root);       // 2.8.0.2：唯一 kind 感知骨架绑定

        const el = (tag, cls, text) => {
            const n = document.createElement(tag);
            if (cls) n.className = cls;
            if (text != null) n.textContent = text;
            return n;
        };
        // 分类色系（复用既有 token 族，非映射类回退中性灰）：
        // cps_too_fast=警示 / untranslated=主色 / antonym_yamete=危险
        const catCls = (c) => (c === 'cps_too_fast' ? ' bfp-cat-warn'
            : c === 'untranslated' ? ' bfp-cat-primary'
            : c === 'antonym_yamete' ? ' bfp-cat-danger' : ' bfp-cat-neutral');

        // —— 头部非滚动元信息区（预估调用/服务商/云端成本/超上限提示）——
        const metaBox = el('div', 'bfp-meta');
        (o.meta || []).forEach((m) => {
            metaBox.appendChild(el('div',
                'bfp-meta-row' + (m.warn ? ' bfp-meta-warn' : ''), m.text));
        });
        body.appendChild(metaBox);

        // —— 分类明细 chips（调用方已按数量降序排列）——
        const catBox = el('div', 'bfp-cats');
        (o.cats || []).forEach((c) => {
            catBox.appendChild(el('span',
                'bfp-cat-chip' + catCls(c.cat), c.cat + ' ' + c.count));
        });
        body.appendChild(catBox);

        if (o.head) body.appendChild(el('div', 'bfp-list-title', o.head));

        // —— 可滚动列表：全部条目渲染，零 slice 截断 ——
        const texts = o.texts || {};
        const listBox = el('div', 'bfp-list');
        (o.items || []).forEach((it) => {
            const idx = (it.index == null) ? null : Number(it.index);
            const full = (idx != null
              && Object.prototype.hasOwnProperty.call(texts, idx))
              ? String(texts[idx]) : null;
            const text = full != null ? full : String(it.excerpt || '');
            const item = el('div', 'bfp-item');
            const head = el('div', 'bfp-item-head');
            head.appendChild(el('span', 'bfp-idx', '#' + it.index));
            head.appendChild(el('span',
                'bfp-cat-chip' + catCls(it.category), it.category));
            const timing = el('span', 'bfp-timing', it.timing || '');
            timing.title = it.timing || '';
            head.appendChild(timing);
            if (full == null) {
                head.appendChild(el('span', 'bfp-trunc', MSG.batchFixExcerptOnly));
            }
            item.appendChild(head);
            const txt = el('div', 'bfp-text', text);
            txt.title = text;               // 悬停全文（折叠态可取全文）
            item.appendChild(txt);
            const toggle = el('button', 'btn btn-ghost btn-compact bfp-toggle',
                MSG.batchFixExpand);
            toggle.type = 'button';
            toggle.addEventListener('click', () => {
                const open = txt.classList.toggle('bfp-open');
                toggle.textContent = open
                  ? MSG.batchFixCollapse : MSG.batchFixExpand;
            });
            item.appendChild(toggle);
            listBox.appendChild(item);
        });
        body.appendChild(listBox);

        this._busy = true;
        this._kind = 'batchfix';
        root.style.display = 'flex';

        // —— 收尾 pass：移除未实际折叠条目的展开键（短文本按钮噪音清理，
        // 2.7.4 件3 黑盒走查修订）——判据 scrollHeight > clientHeight + 1
        // （max-height 折叠生效时 clientHeight 被钉在 3 行高度、scrollHeight
        // 反映全文高度，该判据可靠）。须在 display:flex 之后测：display:none
        // 下两值恒 0，判据失效会误杀全部按钮。取舍：仅本渲染 tick 检测一次
        // （本地系统字体无 FOUT，同 tick 内读取即强制同步布局）；弹窗会话内
        // 不随宽度变化重新检测——窄窗拖宽后新达标条目残留按钮属极端场景
        // 可接受（title 悬停仍可读全文），已折叠条目展开/收起往复后按钮
        // 恒保留（不二次检测）。
        listBox.querySelectorAll('.bfp-item').forEach((row) => {
            const txt = row.querySelector('.bfp-text');
            const toggle = row.querySelector('.bfp-toggle');
            if (txt && toggle && txt.scrollHeight <= txt.clientHeight + 1) {
                toggle.remove();        // 移除而非隐藏（DOM 干净，无死节点）
            }
        });

        okBtn.focus();
        return new Promise((resolve) => {
            this._resolve = (value) => {
                // 自清理（editor 同款）：modal-lg/whiteSpace 复位，
                // 防污染后续 alert/confirm/prompt
                if (card) card.classList.remove('modal-lg');
                body.style.whiteSpace = '';
                resolve(value);
            };
        });
    },

    // ============================================================
    // guideItems 明细模态（卡B，D2026-1010-01 三轮）：质量报告导读
    // 「行动条目」全量明细弹窗（owner：主页浏览太多）。复用 #appModal
    // 骨架（title/关闭键）+ modal-lg 大卡，body 全 createElement 注入
    // （FROZEN_IDS：零新增 id/data-i18n）；列表 markup 由调用方传入
    // （guideItemCardHtml 共享构造、主页弹窗同一渲染源），试听点击经
    // onPreview 回调交还调用方（openAudioPreview 为 IIFE 私有）。
    // kind='guideItems' 不命中 _settle 任何阻塞分支，ESC/遮罩/取消即关。
    // opts = {title, listHtml, onPreview(timing)}
    // ============================================================
    guideItems(opts) {
        if (this._busy) return Promise.resolve(false);      // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        const o = opts || {};
        const card = root.querySelector('.modal-card');
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = o.title || '';
        body.textContent = '';
        body.style.whiteSpace = 'normal';   // .modal-card .modal-body 默认 pre-wrap
        input.style.display = 'none';
        okBtn.style.display = 'none';       // 只读明细，仅关闭键
        okBtn.textContent = '';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        if (card) card.classList.add('modal-lg');
        this._bindSkeletonOnce(root);
        const list = document.createElement('div');
        list.className = 'guide-item-list';
        list.innerHTML = o.listHtml || '';
        list.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn-audio-preview');
            if (btn && typeof o.onPreview === 'function') {
                o.onPreview(btn.dataset.timing);
            }
        });
        body.appendChild(list);
        this._busy = true;
        this._kind = 'guideItems';
        root.style.display = 'flex';
        cancelBtn.focus();
        return new Promise((resolve) => {
            this._resolve = (value) => {
                // 自清理（batchfix 同款）：modal-lg/whiteSpace 复位
                if (card) card.classList.remove('modal-lg');
                body.style.whiteSpace = '';
                resolve(value);
            };
        });
    },

    // ============================================================
    // rawLog 模态（五轮，D2026-1010-01）：原始日志弹窗——内联展开受
    // Console 区 380px 上限挤压无法下翻（owner 实证），改大卡承载
    // _lines 全量缓冲。等宽 pre-wrap 可滚动（.rawlog-view），打开即
    // 滚到底（最新日志），打开期新行经 ConsoleManager._liveRawLogLine
    // 实时追加。kind='rawlog' 不命中 _settle 阻塞分支，ESC/遮罩/取消即关。
    // opts = {title, lines:[string]}
    // ============================================================
    rawLog(opts) {
        if (this._busy) return Promise.resolve(false);      // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        const o = opts || {};
        const card = root.querySelector('.modal-card');
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = o.title || '';
        body.textContent = '';
        body.style.whiteSpace = 'normal';
        input.style.display = 'none';
        okBtn.style.display = 'none';       // 只读日志，仅关闭键
        okBtn.textContent = '';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        if (card) card.classList.add('modal-lg');
        this._bindSkeletonOnce(root);
        const list = document.createElement('div');
        list.className = 'rawlog-view';
        (o.lines || []).forEach((ln) => {
            const line = document.createElement('div');
            line.className = 'console-line';
            line.textContent = String(ln);
            list.appendChild(line);
        });
        body.appendChild(list);
        this._busy = true;
        this._kind = 'rawlog';
        root.style.display = 'flex';
        list.scrollTop = list.scrollHeight;   // 打开即滚到底
        cancelBtn.focus();
        return new Promise((resolve) => {
            this._resolve = (value) => {
                // 自清理（guideItems 同款）：modal-lg/whiteSpace 复位
                if (card) card.classList.remove('modal-lg');
                body.style.whiteSpace = '';
                resolve(value);
            };
        });
    },

    // ============================================================
    // TM 建议编辑模态（P3，D2026-1008-02）：kind='tmEdit'，另立方法
    // 不塞 encode/editOnly（C15，后者为压制参数专用）。body 全
    // createElement 注入（全 class+data-testid，零新增 id/data-i18n，
    // FROZEN 双钉不变）。原文只读、仅拟型译文可编辑（C17，textarea 借
    // editor 先例 .editor-ta-wrap）；理由只读小字；「仅本次会话有效」
    // 提示行（G6）。脏态守卫同 editor：textarea input 置 _edDirty（共用
    // 布尔，kind 互斥安全），Esc/遮罩/取消键经 _settle tmEdit 分支先弹
    // 放弃确认；Enter 不提交（2.8.0.2 起走 _okValue tmEdit 分支 return
    // undefined——统一 kind 感知绑定后不再依赖逐块排除条件）。
    // 保存校验：译文 trim 非空（原文只读不需要），不合法在弹窗状态行
    // 显错（G6）。opts = {entry:<tm[i]>, onSaved(next)->void}
    // ============================================================
    tmEdit(opts) {
        if (this._busy) return Promise.resolve(false);      // 单例不叠加
        const root = document.getElementById('appModal');
        if (!root) return Promise.resolve(false);           // 骨架缺席兜底
        const o = opts || {};
        const entry = o.entry || {};
        const body = root.querySelector('.modal-body');
        const cancelBtn = root.querySelector('.modal-cancel');
        const okBtn = root.querySelector('.modal-ok');
        const input = root.querySelector('.modal-input');
        root.querySelector('.modal-title').textContent = MSG.tmEditTitle;
        body.textContent = '';
        body.style.whiteSpace = 'normal';
        input.style.display = 'none';
        okBtn.style.display = 'none';       // 保存语义由 tm-edit-save 键承载
        okBtn.textContent = '';
        cancelBtn.style.display = '';
        cancelBtn.textContent = MSG.ui_cancel;
        this._bindSkeletonOnce(root);       // 2.8.0.2：唯一 kind 感知骨架绑定

        const el = (tag, cls, text) => {
            const n = document.createElement(tag);
            if (cls) n.className = cls;
            if (text != null) n.textContent = text;
            return n;
        };

        // —— 原文（只读，C17：锁原文保 TM 键稳定）——
        const srcField = el('div', 'tm-edit-field');
        srcField.appendChild(el('div', 'tm-edit-label', MSG.th_source));
        srcField.appendChild(el('div', 'tm-edit-ro', entry.source || ''));
        body.appendChild(srcField);

        // —— 拟型译文（textarea 可编辑，借 editor 的 .editor-ta-wrap）——
        const tgtField = el('div', 'tm-edit-field tm-edit-grow');
        tgtField.appendChild(el('div', 'tm-edit-label', MSG.th_target));
        const taWrap = el('div', 'editor-ta-wrap tm-edit-ta-wrap');
        const ta = el('textarea', 'tm-edit-ta');
        ta.dataset.tmEditTa = '1';      // 弹窗内唯一锚（零 id，测试钉用）
        ta.value = entry.target || '';
        ta.addEventListener('input', () => { AppModal._edDirty = true; });
        taWrap.appendChild(ta);
        tgtField.appendChild(taWrap);
        body.appendChild(tgtField);

        // —— 理由（只读小字，可空省略）——
        if (entry.reason) {
            const rsnField = el('div', 'tm-edit-field');
            rsnField.appendChild(el('div', 'tm-edit-label', MSG.aiThReason));
            rsnField.appendChild(el('div', 'tm-edit-reason', entry.reason));
            body.appendChild(rsnField);
        }

        // —— 提示行（G6：会话内有效性如实交代）——
        body.appendChild(el('div', 'tm-edit-hint hint-warn',
                            MSG.tmEditSessionHint));

        // —— 状态行（校验错/保存失败显错位，editorRunSave 同款配色）——
        const st = el('div', 'tm-edit-status');
        st.style.display = 'none';
        body.appendChild(st);

        // —— 操作行：保存（取消=骨架取消键）——
        const actions = el('div', 'tm-edit-actions');
        const saveBtn = el('button', 'btn btn-primary btn-compact tm-edit-save',
                           MSG.tmEditSave);
        saveBtn.type = 'button';
        saveBtn.addEventListener('click', () => AppModal.tmEditRunSave());
        actions.appendChild(saveBtn);
        body.appendChild(actions);

        this._tmOpts = o;
        this._busy = true;
        this._kind = 'tmEdit';
        this._edDirty = false;
        this._tmSaving = false;
        this._edConfirming = false;
        root.style.display = 'flex';
        ta.focus();
        return new Promise((resolve) => {
            this._resolve = (value) => {
                this._tmEditTeardown();
                resolve(value);
            };
        });
    },

    // 保存主键（tm-edit-save）弹窗感知路径：校验→onSaved 回调（调用方
    // 同步改内存+DOM）→清脏自动关闭；不合法/失败在状态行显错、弹窗保持
    //（G6：真实原因透出，不让用户盲猜）
    async tmEditRunSave() {
        if (this._tmSaving || this._edConfirming) return;
        const o = this._tmOpts || {};
        if (typeof o.onSaved !== 'function') return;
        const ta = document.querySelector(
          '#appModal textarea[data-tm-edit-ta]');
        const st = document.querySelector('#appModal .tm-edit-status');
        const showErr = (m) => {
            if (!st) return;
            st.style.display = '';
            st.style.color = 'var(--status-err)';
            st.textContent = m;
        };
        // 校验：译文 trim 非空（原文只读不需要，C17）
        const next = ((ta && ta.value) || '').trim();
        if (!next) {
            showErr(MSG.tmEditEmptyTarget);
            return;
        }
        this._tmSaving = true;
        const cancelBtn = document.querySelector('#appModal .modal-cancel');
        if (cancelBtn) cancelBtn.disabled = true;
        try {
            await Promise.resolve(o.onSaved(next));
        } catch (e) {
            this._tmSaving = false;
            if (cancelBtn) cancelBtn.disabled = false;
            showErr(MSG.tmEditSaveFailed + '：'
              + (e && e.message ? e.message : String(e)));
            return;
        }
        this._tmSaving = false;
        if (cancelBtn) cancelBtn.disabled = false;
        this._edDirty = false;
        this._settle(false);            // 保存成功自动关闭
    },

    // tmEdit 开态确认弹窗（与 confirm 共用单例骨架；editor 同款收放，
    // 但 body 为动态节点无 vault——确认期间收起暂存保状态，取消原样
    // 放回）：取消=原样恢复（_busy/_kind/_resolve/display 还原）；
    // 确认=保持收起态由调用方收尾（_settle 正式结算）
    _tmEditConfirmWhileOpen(msg) {
        const tmResolve = this._resolve;    // confirm 会覆写 _resolve，先持有
        const root = document.getElementById('appModal');
        const okBtn = root && root.querySelector('.modal-ok');
        const body = root && root.querySelector('.modal-body');
        const stash = body ? Array.prototype.slice.call(body.childNodes) : [];
        this._edConfirming = true;
        if (body) while (body.firstChild) body.removeChild(body.firstChild);
        if (root) root.style.display = 'none';
        this._busy = false;
        if (okBtn) okBtn.style.display = '';    // confirm 需要 OK 键（tmEdit 开态隐藏）
        return AppModal.confirm(msg).then((ok) => {
            this._busy = true;
            this._kind = 'tmEdit';
            this._resolve = tmResolve;
            this._edConfirming = false;
            if (okBtn) okBtn.style.display = 'none';
            if (ok) return true;
            if (body) {
                while (body.firstChild) body.removeChild(body.firstChild);
                stash.forEach((n) => body.appendChild(n));
            }
            if (root) root.style.display = 'flex';
            return false;
        });
    },

    // dirty 关闭守卫（editor 同款）：未保存修改先确认——取消=弹窗与
    // 编辑状态原样保留；确认=真放弃（脏复位+正式结算）
    _tmEditDiscardGuard() {
        this._tmEditConfirmWhileOpen(MSG.tmEditDirtyConfirm).then((ok) => {
            if (!ok) return;
            this._edDirty = false;
            this._settle(false);            // 正式结算（_resolve 收尾 teardown）
        });
    },

    // 关闭收尾（_resolve 包装内调用）：动态节点随 body 清空丢弃（无
    // vault 搬迁语义）+ 骨架默认态恢复（download/editor 同款自清理，
    // 防污染后续 alert/confirm/prompt）
    _tmEditTeardown() {
        const root = document.getElementById('appModal');
        if (root) {
            const body = root.querySelector('.modal-body');
            if (body) {
                while (body.firstChild) body.removeChild(body.firstChild);
                body.style.whiteSpace = '';
            }
            const okBtn = root.querySelector('.modal-ok');
            if (okBtn) okBtn.style.display = '';
        }
        this._tmSaving = false;
        this._edConfirming = false;
    }
};

