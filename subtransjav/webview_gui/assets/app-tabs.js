// ============================================================
// v1.5 左侧 TAB 导航（SmartSub 式）：按 data-tab 切换主内容区页面，
// 选中态同步到 TAB 按钮（accent 高亮）与对应页面（.tab-page.active）
// ============================================================
// 切页钩子注册表（3.1 地基批 卡3，D2026-1012-01）：原 switchTab 体内六段
// 同构内联 if 收编为声明式注册表——新增切页钩子只在对应 tab 分组追加一项，
// 钩子清单单一视图。分组顺序与各组数组顺序=原内联执行序（①②词库页 →
// ③ASR 与词典页 →④⑤⑥质量与建议页）；每项保留原 typeof 守卫 + try/catch
// 吞错（失败不阻断切页），钩子本体（注册方实现）与触发时机零改动。
const TAB_HOOKS = {
    // 词库页初始化钩子（D2026-0930-07-追加1 必要⑧）：打开 tab-glossary 时
    // 动态填充角色卡下拉并加载当前选中项（refine IIFE 未加载时静默跳过）
    'tab-glossary': [
        () => {
            const hook = window.__refineTplTabHook;
            if (typeof hook === 'function') {
                try { hook(); } catch (e) { /* 初始化失败不阻断切页 */ }
            }
        },
        // TM 搜索区块懒注入（2.6.4 批1）：首次打开词库页 createElement 注入
        // 整块（index.html 冻结零改动；失败不阻断切页，对齐上方钩子姿势）
        () => {
            if (typeof TmSearch === 'object') {
                try { TmSearch.ensure(); } catch (e) { /* 初始化失败不阻断切页 */ }
            }
        },
    ],
    // ASR 卡懒探测（2.7.1 D2026-1005-01）：首次打开 ASR 与词典页时读探测
    // 快照立即渲染（快照由首启空闲探测回填；强制刷新走「重新探测」按钮）
    'tab-asrdict': [
        () => {
            const hook = window.__asrTabHook;
            if (typeof hook === 'function') {
                try { hook(); } catch (e) { /* 初始化失败不阻断切页 */ }
            }
        },
    ],
    // P1 分析模型预热触发点②（D2026-1008-02 批3）：切入质量与建议页且
    // 页面有报告时预热（守卫/去重在 warmupMaybeStart 内，失败不阻断切页）
    'tab-guide': [
        () => {
            const hook = window.__warmupTabHook;
            if (typeof hook === 'function') {
                try { hook(); } catch (e) { /* 触发失败不阻断切页 */ }
            }
        },
        // 3.0 批2（D2026-1009-02 批2）：切入质量与建议页刷新全链链级状态行
        // （fullchainStatusRefresh 静默态；失败不阻断切页）
        () => {
            const hook = window.__fullchainStatusHook;
            if (typeof hook === 'function') {
                try { hook(); } catch (e) { /* 失败不阻断切页 */ }
            }
        },
        // 卡A（D2026-1010-01 三轮）：切回导读页时检测文件陈旧（链后台更新
        // 后页面停留旧态），变化即静默重读
        () => {
            const hook = window.__guideStalenessHook;
            if (typeof hook === 'function') {
                try { hook(); } catch (e) { /* 失败不阻断切页 */ }
            }
        },
    ],
};

function switchTab(tabId) {
    document.querySelectorAll('.side-tab-btn').forEach(btn => {
        const on = btn.dataset.tab === tabId;
        btn.classList.toggle('active', on);
        btn.setAttribute('aria-selected', on ? 'true' : 'false');
    });
    document.querySelectorAll('.tab-page').forEach(page => {
        page.classList.toggle('active', page.id === tabId);
    });
    // 切页钩子派发（3.1 地基批 卡3 D2026-1012-01）：按注册表顺序执行该页
    // 钩子；该页无钩子时静默跳过（不阻断切页），吞错语义随各钩子包装内置
    const hooks = TAB_HOOKS[tabId];
    if (hooks) for (const h of hooks) h();
}

