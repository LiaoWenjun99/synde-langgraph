/**
 * Main application JavaScript for SynDe Web
 */

// Global application state
const App = {
    pageData: null,
    csrfToken: null,
    conversationId: null,

    init() {
        // Parse page data
        const pageDataEl = document.getElementById('page-data');
        if (pageDataEl) {
            try {
                this.pageData = JSON.parse(pageDataEl.textContent);
                this.csrfToken = this.pageData.csrf_token;
                this.conversationId = this.pageData.conversation_id;
            } catch (e) {
                console.error('Failed to parse page data:', e);
            }
        }

        // Initialize Feather icons
        if (typeof feather !== 'undefined') {
            feather.replace();
        }

        console.log('SynDe App initialized');
    },

    /**
     * Make an API request
     */
    async api(endpoint, options = {}) {
        const defaults = {
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': this.csrfToken
            }
        };

        const config = { ...defaults, ...options };
        if (options.headers) {
            config.headers = { ...defaults.headers, ...options.headers };
        }

        try {
            const response = await fetch(endpoint, config);

            if (!response.ok) {
                const error = await response.json().catch(() => ({ error: 'Request failed' }));
                throw new Error(error.error || 'Request failed');
            }

            return await response.json();
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    },

    /**
     * Show a notification
     */
    notify(message, type = 'info') {
        // Simple notification - could be enhanced with a toast library
        console.log(`[${type.toUpperCase()}] ${message}`);

        // For now, use alert for errors
        if (type === 'error') {
            alert(message);
        }
    },

    /**
     * Format a date for display
     */
    formatDate(dateString) {
        const date = new Date(dateString);
        const now = new Date();
        const diff = now - date;

        // Less than a minute
        if (diff < 60000) {
            return 'Just now';
        }

        // Less than an hour
        if (diff < 3600000) {
            const minutes = Math.floor(diff / 60000);
            return `${minutes}m ago`;
        }

        // Less than a day
        if (diff < 86400000) {
            const hours = Math.floor(diff / 3600000);
            return `${hours}h ago`;
        }

        // Less than a week
        if (diff < 604800000) {
            const days = Math.floor(diff / 86400000);
            return `${days}d ago`;
        }

        // Format as date
        return date.toLocaleDateString();
    },

    /**
     * Escape HTML to prevent XSS
     */
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});

// Export for use in other modules
window.App = App;
