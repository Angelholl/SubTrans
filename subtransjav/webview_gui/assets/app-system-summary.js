// ============================================================
// System Summary（D2026-1001 批3：右栏系统状态摘要卡，全部只读现成接口）
// 每接口独立降级：任一失败仅该行显示"不可用"，不拖垮右栏布局
// ============================================================
const SystemSummary = {
    load() {
        // 批3 扩展（D2026-1002-12）：角色卡/ASR 两行动态渲染（FROZEN_IDS 已满，
        // 行与控件零新增静态 id，经 data-sys-row 定位）
        this._ensureDynamicRows();
        // 2.6.5 段2（D2026-1004-01 #2 两行式改版）：版本入标题行 stat 槽；
        // TM/词典统计值升 keyrow 右 stat 槽，路径值独立成行完整折行；
        // 悬停 title 全文兜底移除（折行后不再截断，无需悬停）
        this._set('sysSummaryVersion', async () => {
            const r = await pywebview.api.get_version();
            return (r && r.success) ? r.version : null;
        });
        this._setPath('sysSummaryDataRoot', async () => {
            const r = await pywebview.api.refine_get_data_root();
            return (r && r.success && r.data_root) ? r.data_root : null;
        });
        this._setStatPath('sysSummaryTm', async () => {
            const r = await pywebview.api.tm_get_stats();
            if (!r || !r.success) return null;
            // 收口件①延续：行标签已是"翻译记忆库"（静态键），stat 槽只放
            // 统计值，不拼 tm_enable_label 前缀防重复
            return {
                stat: `${r.total || 0} 条 · 命中 ${r.total_hits || 0} 次`,
                val: r.db_path || '—'
            };
        });
        this._setStatPath('sysSummaryDict', async () => {
            const r = await pywebview.api.refine_dict_status();
            if (!r || !r.success || !r.dicts) return null;
            // 修复A：分母取 DICT_KINDS 桥接值（防 manifest 增 kind 时前端漂移/漏改）
            const kinds = Object.values(r.dicts);
            const ok = kinds.filter(d => d && d.available).length;
            const total = window.AppDictKindsCount || kinds.length;
            return {
                stat: `${ok}/${total} ${MSG.dict_status_available}`,
                val: r.effective_dir || '—'
            };
        });
        this._loadRoles();
    },

    // 2.6.5 段2（D2026-1004-01 #2 折行策略红线）：路径值安全写入——按
    // 分隔符拆分、TextNode + <wbr> 安全 DOM 构建（overflow-wrap:anywhere
    // 兜底 + 分隔符处优先断行）；禁 innerHTML、禁 U+200B（wbr 不入剪贴板）
    _setPathValue(el, text) {
        el.textContent = '';
        const parts = String(text).split(/([\\/]+)/);
        parts.forEach((part, i) => {
            el.appendChild(document.createTextNode(part));
            // 奇数位=分隔符（捕获组），其后插 wbr 提供优先断点
            if (i % 2 === 1 && i < parts.length - 1) {
                el.appendChild(document.createElement('wbr'));
            }
        });
    },

    async _set(id, fn) {
        const el = document.getElementById(id);
        if (!el) return;
        let text = MSG.sys_summary_unavailable;
        try {
            const v = await fn();
            if (v !== null && v !== undefined && v !== '') text = v;
        } catch (e) {
            console.warn('SystemSummary[' + id + ']:', e);
        }
        this._setPathValue(el, text);
    },

    // 2.6.5 段2（D2026-1004-01 #2）：纯路径行（无 stat 槽）——数据保存目录
    async _setPath(id, fn) {
        await this._set(id, fn);
    },

    // 2.6.5 段2（D2026-1004-01 #2）：stat+路径双槽行——fn 返回 {stat, val}，
    // 统计值写 keyrow 右 stat 槽（mono 11px），路径写全宽值行；降级时
    // stat 清空、值行显示"不可用"
    async _setStatPath(id, fn) {
        const el = document.getElementById(id);
        if (!el) return;
        const row = el.closest('.sys-summary-row');
        const stat = row ? row.querySelector('.sys-summary-stat') : null;
        let valText = MSG.sys_summary_unavailable;
        let statText = '';
        try {
            const v = await fn();
            if (v && typeof v === 'object') {
                valText = v.val || MSG.sys_summary_unavailable;
                statText = v.stat || '';
            }
        } catch (e) {
            console.warn('SystemSummary[' + id + ']:', e);
        }
        this._setPathValue(el, valText);
        if (stat) stat.textContent = statText;
    },

    // 批3 扩展（D2026-1002-12）：角色卡行 + ASR 行动态渲染——
    // 行样式复用 .sys-summary-row，标签复用既有静态键文案（JS 态取值，
    // 不挂 data-i18n：applyI18n 首屏已跑完，动态节点收不到）；
    // 2.6.5 段2（D2026-1004-01 #2）：两行式改版——角色卡统计值（N 张）
    // 升 keyrow 右 stat 槽、路径独立值行；ASR 探测按钮与 .sys-summary-stat
    // 同处 keyrow（弱化语义 val-muted 迁 stat，该行不再用 val）；
    // ASR 行「重新探测」小按钮不带 id，事件委托绑在卡上（见 bindDom）
    _ensureDynamicRows() {
        const card = document.getElementById('systemSummaryCard');
        if (!card || card.querySelector('[data-sys-row="roles"]')) return;
        const roles = document.createElement('div');
        roles.className = 'sys-summary-row';
        roles.dataset.sysRow = 'roles';
        roles.innerHTML = '<div class="sys-summary-keyrow">'
            + '<span class="sys-summary-key"></span>'
            + '<span class="sys-summary-stat"></span></div>'
            + '<div class="sys-summary-val"></div>';
        roles.querySelector('.sys-summary-key').textContent
            = MSG.templates_dir_label;
        card.appendChild(roles);
        // 3.2 退役批（D2026-1029-01）：ASR 行随 whisper 探测面删除
        // （引擎状态在「ASR 与词典」页 CT2 面板承载）
    },

    // 批3 扩展（D2026-1002-12）：角色卡目录行（复用 refine_list_templates，
    // 只读零写路径）；统计值="N 张"+pkg_fallback 标注内置回落（stat 槽），
    // 目录独立值行 wbr 折行（悬停 title 兜底随折行策略移除）
    async _loadRoles() {
        const row = document.querySelector(
            '#systemSummaryCard [data-sys-row="roles"]');
        if (!row) return;
        const val = row.querySelector('.sys-summary-val');
        const stat = row.querySelector('.sys-summary-stat');
        if (!val) return;
        let text = MSG.sys_summary_unavailable;
        let statText = '';
        try {
            const r = await pywebview.api.refine_list_templates(null);
            if (r && r.success) {
                const tag = r.pkg_fallback ? `（${MSG.sys_roles_fallback}）` : '';
                statText = `${MSG.sys_roles_count((r.files || []).length)}${tag}`;
                text = r.dir || '—';
            }
        } catch (e) {
            console.warn('SystemSummary[roles]:', e);
        }
        this._setPathValue(val, text);
        if (stat) stat.textContent = statText;
    }
};

