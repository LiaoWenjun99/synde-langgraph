/**
 * Theme management for SynDe Web
 */

const Theme = {
    STORAGE_KEY: 'synde-theme',
    THEMES: ['light', 'dark', 'system'],

    init() {
        // Get saved theme or default to system
        const savedTheme = localStorage.getItem(this.STORAGE_KEY) || 'system';
        this.apply(savedTheme);

        // Listen for system theme changes
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (this.current === 'system') {
                this.applySystemTheme();
            }
        });

        // Set up toggle button
        const toggleBtn = document.getElementById('theme-toggle');
        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.cycle());
        }

        // Set up theme select in profile
        const themeSelect = document.getElementById('theme');
        if (themeSelect) {
            themeSelect.value = savedTheme;
            themeSelect.addEventListener('change', (e) => {
                this.apply(e.target.value);
            });
        }
    },

    get current() {
        return localStorage.getItem(this.STORAGE_KEY) || 'system';
    },

    apply(theme) {
        if (!this.THEMES.includes(theme)) {
            theme = 'system';
        }

        localStorage.setItem(this.STORAGE_KEY, theme);

        if (theme === 'system') {
            this.applySystemTheme();
        } else {
            this.setTheme(theme);
        }

        // Update toggle button icons
        this.updateToggleIcon();
    },

    applySystemTheme() {
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        this.setTheme(prefersDark ? 'dark' : 'light');
    },

    setTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);

        // Toggle stylesheet
        const lightSheet = document.getElementById('theme-light');
        const darkSheet = document.getElementById('theme-dark');

        if (lightSheet) lightSheet.disabled = theme === 'dark';
        if (darkSheet) darkSheet.disabled = theme === 'light';
    },

    cycle() {
        const currentIndex = this.THEMES.indexOf(this.current);
        const nextIndex = (currentIndex + 1) % this.THEMES.length;
        this.apply(this.THEMES[nextIndex]);
    },

    updateToggleIcon() {
        const theme = this.current === 'system'
            ? (window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')
            : this.current;

        document.documentElement.setAttribute('data-theme', theme);
    }
};

// Initialize theme on load
document.addEventListener('DOMContentLoaded', () => {
    Theme.init();
});

window.Theme = Theme;
