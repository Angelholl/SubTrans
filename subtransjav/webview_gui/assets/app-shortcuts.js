// ============================================================
// Keyboard Shortcuts
// ============================================================
const KeyboardShortcuts = {
    init() {
        document.addEventListener('keydown', async (e) => {
            // Ctrl+O: Add files
            if (e.ctrlKey && e.key === 'o') {
                e.preventDefault();
                FileListManager.addFiles();
            }

            // Ctrl+R: Start translation
            if (e.ctrlKey && e.key === 'r') {
                e.preventDefault();
                if (!AppState.isRunning && AppState.selectedFiles.length > 0) {
                    TranslatorManager.startTranslation();
                }
            }

            // Escape: Close modal（四层链：AppModal > 设置 overlay > console
            // 覆盖层 > about；上层活跃即 early-return，防一次 ESC 关多层）
            if (e.key === 'Escape') {
                if (typeof AppModal !== 'undefined' && AppModal._busy) return;
                if (typeof SettingsHub !== 'undefined' && SettingsHub._isOpen) {
                    // 设置 overlay 优先于覆盖层/about：settings 自身 capture 在
                    // about 活跃时让位，故由其下的本层补仲裁（同走 dirty 守卫）
                    SettingsHub._requestClose();
                    return;
                }
                if (typeof ConsoleOverlay !== 'undefined' && ConsoleOverlay.isOpen()) return;
                const modal = document.getElementById('aboutModal');
                if (modal && modal.classList.contains('active')) {
                    closeAbout();
                }
            }

            // F1: Show About dialog
            if (e.key === 'F1') {
                e.preventDefault();
                showAbout();
            }

            // F5: Refresh with warning
            if (e.key === 'F5') {
                if (AppState.isRunning) {
                    // preventDefault 必须保持在首个 await 之前同步执行（防默认刷新先跑）
                    e.preventDefault();
                    const ok = await AppModal.confirm(MSG.confirm_reload);
                    if (ok) {
                        location.reload();
                    }
                }
            }
        });
    }
};

