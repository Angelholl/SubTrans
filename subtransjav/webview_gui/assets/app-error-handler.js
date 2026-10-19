// ============================================================
// Error Handler
// ============================================================
const ErrorHandler = {
    show(title, message) {
        ConsoleManager.log(`✗ ${title}: ${message}`, 'error');
        // 2.4.0 批1：原生 alert → 自制模态（非阻塞化语义安全——全调用点均为
        // "展示后随即 _finish/return"模式，无阻塞依赖；行为变化=模态期间 UI 可交互）
        AppModal.alert(title, message);
    },

    showWarning(title, message) {
        ConsoleManager.log(`⚠ ${title}: ${message}`, 'warning');
    },

    showSuccess(title, message) {
        ConsoleManager.log(`✓ ${title}: ${message}`, 'success');
    }
};

