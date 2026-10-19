// ============================================================
// Initialization
// ============================================================
document.addEventListener('DOMContentLoaded', async () => {
    console.log('SubTrans GUI initialized');

    // i18n：先把 MSG 文案注入 data-i18n* 标记的元素
    applyI18n();

    // Initialize components (pure DOM parts)
    ConsoleManager.init();
    ProgressManager.init();
    ProgressManager.reset();
    FileListManager.init();
    DirectoryControls.init();
    RunControlsInit();
    KeyboardShortcuts.init();
    ThemeManager.init();
    TranslatorManager.init();

    // Update Start button state once at startup
    TranslatorManager.updateButtons();

    // 右栏卡 3 镜像：加载后渲染 + 引擎页控件变更时同步（只读，无回写）
    refreshPipelineMirror();
    ['refineS1Model', 'refineConcurrency'].forEach(id => {
        const el = document.getElementById(id);
        if (el) el.addEventListener('change', refreshPipelineMirror);
    });

    // 卡G2（D2026-1013-01 §2.2d/e/f）：右栏折叠行为——启动默认 + 把手单钮绑定
    // （卡N：两钮融合为单钮双态） + localStorage 单写记忆（键串见下方 getItem）。
    // - 1240 窗口阈值只作用启动默认：记忆优先，无记忆按 innerWidth <= 1240 收起；
    //   运行期不挂 resize 自动切换（用户显式操作永久优先，粘滞不回弹）。
    // - 降级三分支：a) 实测持久 OK 本路线即定案；b) 实测不持久由主审关记忆层
    //   回落阈值默认；c) theme 式双写为休眠备选，启用须新的显式拍板。
    // - 已知代价：升级或换数据目录可能清 localStorage → 记忆复位为默认（非丢数据）。
    (function () {
        const BTN_SEL = '.aside-toggle-btn';
        let asideCollapsed = null;
        try {
            asideCollapsed = localStorage.getItem('subtransjav.aside.collapsed');
        } catch (e) {
            // private/无痕读不到 → 降级走窗口阈值默认
        }
        if (asideCollapsed !== '0' && asideCollapsed !== '1') {
            asideCollapsed = window.innerWidth <= 1240 ? '1' : '0';
        }
        const startupCollapsed = asideCollapsed === '1';
        document.querySelectorAll(BTN_SEL).forEach((btn) => {
            const asideEl = btn.closest('.aside');
            const workbenchEl = asideEl ? asideEl.closest('.workbench') : null;
            if (!workbenchEl) return;
            // 文案回填复用既有 MSG 键（零新增键；HTML 侧零 id 零 data-i18n）
            btn.setAttribute('aria-label', MSG.collapse_toggle);
            btn.setAttribute('title', MSG.collapse_toggle);
            workbenchEl.classList.toggle('aside-collapsed', startupCollapsed);
            btn.setAttribute('aria-expanded', startupCollapsed ? 'false' : 'true');
            btn.addEventListener('click', () => {
                const collapsed =
                    !workbenchEl.classList.contains('aside-collapsed');
                workbenchEl.classList.toggle('aside-collapsed', collapsed);
                asideEl.querySelectorAll(BTN_SEL).forEach((b) => {
                    b.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
                });
                try {
                    localStorage.setItem('subtransjav.aside.collapsed',
                                         collapsed ? '1' : '0');
                } catch (e) {
                    // 写入失败静默（private 模式降级为会话级折叠）
                }
            });
        });
    })();

    // 卡 3 提示态惰性求值：hover/focus 时按当前页切换提示文案（D2026-1012-01 ⑨）
    function refreshPipelineCardHint() {
        const el = document.getElementById('pipelineCard');
        if (!el) return;
        const here = document.querySelector('.tab-page.active')?.id === 'tab-engine';
        el.title = MSG[here ? 'pipeline_card_hint_here' : 'pipeline_card_hint'];
    }

    // 卡 3 整卡跳转引擎页（只读镜像的修改入口）
    const pipelineCard = document.getElementById('pipelineCard');
    if (pipelineCard) {
        pipelineCard.addEventListener('click', (e) => {
            // 卡K（D2026-1013-01 真机反馈）：交互元素不触发整卡跳转（统一入口过滤）
            const target = e.target;
            if (target instanceof Element && target.closest(
                    'button, input, label, a, select, textarea, .path-row, .destination-section, .encode-auto-row, .fullchain-auto-row, .encode-params-link')) {
                return;
            }
            switchTab('tab-engine');
        });
        pipelineCard.addEventListener('keydown', (e) => {
            // 卡K（D2026-1013-01 真机反馈）：同一过滤——键盘激活交互元素不跳转；
            // 卡片本身聚焦时 Enter 仍跳（closest 不命中交互元素即放行）
            const target = e.target;
            if (target instanceof Element && target.closest(
                    'button, input, label, a, select, textarea, .path-row, .destination-section, .encode-auto-row, .fullchain-auto-row, .encode-params-link')) {
                return;
            }
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                switchTab('tab-engine');
            }
        });
        pipelineCard.addEventListener('mouseenter', refreshPipelineCardHint);
        pipelineCard.addEventListener('focus', refreshPipelineCardHint);
        refreshPipelineCardHint();
    }

    // 卡I（D2026-1013-01 真机反馈）：输出目录并入本卡，交互区域内阻断
    // 整卡跳转冒泡（click 与键盘 Enter 均不触发 switchTab）
    const destSection = document.querySelector('.destination-section');
    if (destSection) {
        destSection.addEventListener('click', (e) => e.stopPropagation());
        destSection.addEventListener('keydown', (e) => e.stopPropagation());
    }

    ConsoleManager.log(MSG.gui_initialized, 'success');
    ConsoleManager.log(MSG.gui_usage_hint, 'info');
});

function RunControlsInit() {
    // Placeholder hook for future global controls; refine panel owns its own buttons.
}

// 右栏卡 3 只读镜像（D2026-0930-09 批2）：读引擎页当前配置渲染，不做双向同步
function refreshPipelineMirror() {
    const line = document.getElementById('pipelineMirrorLine');
    if (!line) return;
    const model = ((document.getElementById('refineS1Model') || {}).value || '').trim() || '—';
    const conc = ((document.getElementById('refineConcurrency') || {}).value || '').trim() || '1';
    line.textContent = `${MSG.pipeline_mirror_model}：${model}　·　${MSG.pipeline_mirror_conc} ${conc}`;
}

// PyWebView ready event — backend bridge is now available.
window.addEventListener('pywebviewready', async () => {    console.log('PyWebView API ready!');
    ConsoleManager.log(MSG.bridgeConnected, 'success');
    window.__pywebviewReady = true;

    // D2026-1010-03 件C：应用级常驻日志排水——全链自动化 daemon 在任务
    // 结束后仍向翻译日志队列投递阶段行（_automation_notice 尽力投），而
    // 状态轮询随 _finish 停摆，若无常驻排水，全链过程行永远到不了
    // Console/原始日志/导出（真机黑箱实证），且积压行会在下次任务启动
    // 时作陈旧行误 flush。2s 轻拍仅排日志不触状态桥；与任务期 1s 主轮
    // 询并存幂等（fetchLogs 自带 try/catch，空队列零开销）。
    if (!TranslatorManager._logDrainInterval) {
        TranslatorManager._logDrainInterval = setInterval(() => {
            try { TranslatorManager.fetchLogs(); }
            catch (e) { console.warn('log drain failed:', e); }
        }, 2000);
    }

    // A3 主题持久化走后端：读取 settings.theme 并应用
    await ThemeManager.loadSavedThemeFromBackend();

    await AppState.loadDefaultOutputDir();

    // 右栏系统状态摘要卡（D2026-1001 批3）：只读四接口，逐项降级
    SystemSummary.load();

    // Load saved stage settings, glossary, templates and model lists
    if (window.__refineLoadRemote) {
        await window.__refineLoadRemote();
    }

    // 硬字幕压制底条/入口接线（2.8.0 批1 件5）；若有在途队列（热刷新场景）
    // 由 refresh 轮询自然恢复显示
    EncodeDock.init();

    // Initialize feature status indicators
    await FeatureStatus.init();

    // 2.7.1 首启空闲探测（D2026-1005-01 承接批，README 提示句口径）：后台
    // 触发一次 refine_asr_status 回填探测快照缓存（短暂启动一次 Python
    // 子进程，通常数秒；不阻塞首屏，结果稍后显示在 ASR 卡/模型管理面板）
    setTimeout(() => {
        try {
            if (window.pywebview && window.pywebview.api) {
                window.pywebview.api.refine_asr_status();
            }
        } catch (e) { /* 后台预热失败静默（显式探测按钮兜底） */ }
    }, 3000);
});

