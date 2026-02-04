/**
 * Sidebar functionality for SynDe Web
 */

const Sidebar = {
    element: null,
    isCollapsed: false,

    init() {
        this.element = document.getElementById('sidebar');
        if (!this.element) return;

        // Load saved state
        this.isCollapsed = localStorage.getItem('synde-sidebar-collapsed') === 'true';
        if (this.isCollapsed) {
            this.element.classList.add('collapsed');
        }

        // Set up toggle buttons
        const toggleBtn = document.getElementById('sidebar-toggle');
        const mobileToggleBtn = document.getElementById('sidebar-toggle-mobile');

        if (toggleBtn) {
            toggleBtn.addEventListener('click', () => this.toggle());
        }

        if (mobileToggleBtn) {
            mobileToggleBtn.addEventListener('click', () => this.toggleMobile());
        }

        // Set up conversation clicks
        this.setupConversationClicks();

        // Set up project toggles
        this.setupProjectToggles();

        // Set up new chat button
        this.setupNewChatButton();

        // Set up search
        this.setupSearch();

        // Close sidebar on outside click (mobile)
        document.addEventListener('click', (e) => {
            if (window.innerWidth <= 768 &&
                this.element.classList.contains('active') &&
                !this.element.contains(e.target) &&
                !e.target.closest('#sidebar-toggle-mobile')) {
                this.element.classList.remove('active');
            }
        });
    },

    toggle() {
        this.isCollapsed = !this.isCollapsed;
        this.element.classList.toggle('collapsed', this.isCollapsed);
        localStorage.setItem('synde-sidebar-collapsed', this.isCollapsed);
    },

    toggleMobile() {
        this.element.classList.toggle('active');
    },

    setupConversationClicks() {
        const items = this.element.querySelectorAll('.conversation-item');
        items.forEach(item => {
            item.addEventListener('click', () => {
                const conversationId = item.dataset.conversationId;
                if (conversationId) {
                    window.location.href = `/chat/${conversationId}/`;
                }
            });
        });
    },

    setupProjectToggles() {
        const projectHeaders = this.element.querySelectorAll('.project-header');
        projectHeaders.forEach(header => {
            header.addEventListener('click', () => {
                const group = header.closest('.project-group');
                group.classList.toggle('collapsed');
            });
        });
    },

    setupNewChatButton() {
        const btn = document.getElementById('new-chat-btn');
        if (!btn) return;

        btn.addEventListener('click', async () => {
            try {
                const data = await App.api('/api/conversations/', {
                    method: 'POST',
                    body: JSON.stringify({ title: 'New Conversation' })
                });

                window.location.href = `/chat/${data.id}/`;
            } catch (error) {
                App.notify('Failed to create conversation', 'error');
            }
        });
    },

    setupSearch() {
        const searchInput = document.getElementById('search-input');
        if (!searchInput) return;

        let debounceTimer;

        searchInput.addEventListener('input', (e) => {
            clearTimeout(debounceTimer);
            debounceTimer = setTimeout(() => {
                this.filterConversations(e.target.value);
            }, 300);
        });
    },

    filterConversations(query) {
        const normalizedQuery = query.toLowerCase().trim();
        const items = this.element.querySelectorAll('.conversation-item');

        items.forEach(item => {
            const title = item.querySelector('.conversation-title').textContent.toLowerCase();
            const matches = !normalizedQuery || title.includes(normalizedQuery);
            item.style.display = matches ? '' : 'none';
        });

        // Show/hide section headers based on visible items
        const sections = this.element.querySelectorAll('.sidebar-section');
        sections.forEach(section => {
            const visibleItems = section.querySelectorAll('.conversation-item:not([style*="display: none"])');
            const header = section.querySelector('.sidebar-section-header');
            if (header && visibleItems.length === 0 && normalizedQuery) {
                section.style.display = 'none';
            } else {
                section.style.display = '';
            }
        });
    }
};

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    Sidebar.init();
});

window.Sidebar = Sidebar;
