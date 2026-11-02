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
            // 抽屉 > about；上层活跃即 early-return，防一次 ESC 关多层）
            if (e.key === 'Escape') {
                if (typeof AppModal !== 'undefined' && AppModal._busy) return;
                if (typeof SettingsHub !== 'undefined' && SettingsHub._isOpen) return;
                if (typeof ConsoleDrawer !== 'undefined' && ConsoleDrawer.isOpen()) return;
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

