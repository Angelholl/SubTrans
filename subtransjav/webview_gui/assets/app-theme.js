// ============================================================
// Theme Manager (runtime stylesheet switching with persistence)
// ============================================================
const ThemeManager = {
    storageKey: 'subtransjav_theme',
    themes: { 'default': 'style.css', 'dark': 'style.dark.css' },

    init() {
        this.linkEl = document.getElementById('themeStylesheet');
        if (!this.linkEl) {
            console.warn('ThemeManager: #themeStylesheet not found; falling back to style.css');
            return;
        }

        const saved = this.getSavedTheme();
        this.applyTheme(saved);

        const btn = document.getElementById('themeBtn');
        const menu = document.getElementById('themeMenu');
        if (btn && menu) {
            btn.addEventListener('click', (e) => {
                e.stopPropagation();
                menu.classList.toggle('active');
                if (menu.classList.contains('active')) {
                    const first = menu.querySelector('.theme-option');
                    if (first) first.focus();
                }
            });

            document.addEventListener('click', (e) => {
                if (menu.classList.contains('active')) {
                    menu.classList.remove('active');
                }
            });

            document.addEventListener('keydown', (e) => {
                if (e.key === 'Escape') {
                    menu.classList.remove('active');
                }
            });

            menu.querySelectorAll('.theme-option').forEach(opt => {
                opt.addEventListener('click', (e) => {
                    const theme = opt.dataset.theme;
                    this.applyTheme(theme);
                    menu.classList.remove('active');
                });
            });
        }
    },

    getSavedTheme() {
        try {
            const key = localStorage.getItem(this.storageKey) || 'default';
            return this.themes[key] ? key : 'default';
        } catch (e) {
            return 'default';
        }
    },

    saveTheme(key) {
        try {
            localStorage.setItem(this.storageKey, key);
        } catch (e) {
            // ignore（private_mode 下 localStorage 不可用，仅后端持久化生效）
        }
        // A3 主题持久化走后端（main.py private_mode=True：用户设置一律走
        // 后端文件）：settings KV 键 theme；桥不可用时静默降级（仅
        // localStorage 生效）
        try {
            const p = window.pywebview && pywebview.api
                ? pywebview.api.refine_save_stage_settings(null, null,
                    { theme: key })
                : null;
            if (p && typeof p.catch === 'function') p.catch(() => {});
        } catch (e) {
            // 桥不可用时静默降级
        }
    },

    applyTheme(key) {
        if (!this.linkEl) return;
        const href = this.themes[key] || this.themes['default'];
        this.linkEl.setAttribute('href', href);
        // 阶段2 批1（D2026-0930-09）：主题按钮双图标显隐同步
        //（dark=显示 sun、隐藏 moon；浅色反之。仅切图标，不动持久化逻辑）
        const dark = (key in this.themes ? key : 'default') === 'dark';
        const moonIcon = document.getElementById('iconMoon');
        const sunIcon = document.getElementById('iconSun');
        if (moonIcon) moonIcon.style.display = dark ? 'none' : '';
        if (sunIcon) sunIcon.style.display = dark ? '' : 'none';
        this.saveTheme(key in this.themes ? key : 'default');
        ConsoleManager.log(MSG.themeSwitched(key), 'info');
    },

    // A3：pywebviewready 后读取后端 settings.theme 并应用
    //（早于该时机的 ThemeManager.init 保持 localStorage/默认主题现状）
    async loadSavedThemeFromBackend() {
        try {
            const r = await pywebview.api.refine_get_stage_settings();
            const t = (r && r.success && r.settings) ? r.settings.theme : null;
            if (t && this.themes[t]) {
                this.applyTheme(t);
            }
        } catch (e) {
            // 静默降级：后端无存档/读取失败时保持现状默认
        }
    }
};

