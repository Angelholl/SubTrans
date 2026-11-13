// ============================================================
// About Dialog
// ============================================================
async function showAbout() {
    const modal = document.getElementById('aboutModal');
    const versionEl = document.getElementById('aboutVersion');

    try {
        const result = await pywebview.api.get_version();
        if (result.success) {
            versionEl.textContent = `Version ${result.version}`;
        }
    } catch (e) {
        console.warn('Could not fetch version:', e);
    }

    modal.classList.add('active');
}

function closeAbout() {
    const modal = document.getElementById('aboutModal');
    modal.classList.remove('active');
}

// CSP（壳层加固）：index.html 移除 4 处内联 onclick 后，改由本文件统一
// addEventListener 绑定（不开新 id/data-i18n，FROZEN 双钉零消耗）——
// 入口链接、遮罩自点关闭、右上 × 与底部关闭按钮。
function bindAboutDialog() {
    const link = document.querySelector('[data-i18n="about_link"]');
    if (link) {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            showAbout();
        });
    }
    const modal = document.getElementById('aboutModal');
    if (!modal) return;
    modal.addEventListener('click', (e) => {
        if (e.target === modal) closeAbout();
    });
    const closeBtn = modal.querySelector('.modal-close');
    if (closeBtn) closeBtn.addEventListener('click', closeAbout);
    const footerClose = modal.querySelector('[data-i18n="close_btn"]');
    if (footerClose) footerClose.addEventListener('click', closeAbout);
}

if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAboutDialog);
} else {
    bindAboutDialog();
}
