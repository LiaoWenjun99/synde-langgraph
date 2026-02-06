/**
 * Chat functionality for SynDe Web
 */

const Chat = {
    messagesContainer: null,
    inputElement: null,
    sendButton: null,
    activeWorkflowId: null,
    uploadedFile: null,  // Track uploaded file

    init() {
        this.messagesContainer = document.getElementById('chat-messages');
        this.inputElement = document.getElementById('chat-input');
        this.sendButton = document.getElementById('send-btn');

        if (!this.inputElement || !this.sendButton) return;

        // Set up input handling
        this.setupInput();

        // Set up send button
        this.sendButton.addEventListener('click', () => this.sendMessage());

        // Set up file upload
        this.setupFileUpload();

        // Set up suggestion chips
        this.setupSuggestions();

        // Set up structure viewer buttons
        this.setupStructureButtons();

        // Auto-scroll to bottom
        this.scrollToBottom();

        // Check for active workflows
        this.checkActiveWorkflows();
    },

    setupFileUpload() {
        const attachBtn = document.getElementById('attach-btn');
        if (!attachBtn) {
            console.warn('File upload: attach-btn not found');
            return;
        }

        console.log('Setting up file upload functionality');

        // Create hidden file input
        const fileInput = document.createElement('input');
        fileInput.type = 'file';
        fileInput.accept = '.pdb,.fasta,.fa,.faa,.fas,.txt';
        fileInput.style.display = 'none';
        fileInput.id = 'file-input';
        document.body.appendChild(fileInput);

        // Attach button click - use both click and pointerdown for better compatibility
        attachBtn.addEventListener('click', (e) => {
            console.log('Attach button clicked');
            e.preventDefault();
            e.stopPropagation();
            fileInput.click();
        });

        // Also add keyboard accessibility
        attachBtn.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                fileInput.click();
            }
        });

        // File selected
        fileInput.addEventListener('change', async (e) => {
            const file = e.target.files[0];
            if (!file) return;

            await this.uploadFile(file);
            fileInput.value = ''; // Reset input
        });

        // Drag and drop
        const inputArea = document.querySelector('.chat-input-area');
        if (inputArea) {
            inputArea.addEventListener('dragover', (e) => {
                e.preventDefault();
                inputArea.classList.add('drag-over');
            });

            inputArea.addEventListener('dragleave', () => {
                inputArea.classList.remove('drag-over');
            });

            inputArea.addEventListener('drop', async (e) => {
                e.preventDefault();
                inputArea.classList.remove('drag-over');

                const file = e.dataTransfer.files[0];
                if (file) {
                    await this.uploadFile(file);
                }
            });
        }
    },

    async uploadFile(file) {
        // Validate file type
        const validExtensions = ['.pdb', '.fasta', '.fa', '.faa', '.fas', '.txt'];
        const ext = '.' + file.name.split('.').pop().toLowerCase();

        if (!validExtensions.includes(ext)) {
            App.notify('Invalid file type. Supported: PDB, FASTA', 'error');
            return;
        }

        // Validate file size (10MB max)
        if (file.size > 10 * 1024 * 1024) {
            App.notify('File too large. Maximum size is 10MB', 'error');
            return;
        }

        // Upload file
        const formData = new FormData();
        formData.append('file', file);

        try {
            const response = await fetch('/api/upload/', {
                method: 'POST',
                headers: {
                    'X-CSRFToken': App.csrfToken
                },
                body: formData
            });

            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }

            // Store uploaded file info
            this.uploadedFile = {
                file_id: data.file_id,
                file_type: data.file_type,
                filename: data.filename,
                sequences: data.sequences,
                metadata: data.metadata
            };

            // Show file attachment indicator
            this.showFileAttachment(data);

            // Enable send button if we have a file
            this.sendButton.disabled = false;

            App.notify(`File uploaded: ${data.filename}`, 'info');

        } catch (error) {
            App.notify('Upload failed: ' + error.message, 'error');
        }
    },

    showFileAttachment(fileData) {
        // Remove existing attachment indicator
        const existing = document.querySelector('.file-attachment');
        if (existing) existing.remove();

        // Create attachment indicator
        const indicator = document.createElement('div');
        indicator.className = 'file-attachment';

        let details = '';
        if (fileData.file_type === 'pdb') {
            details = `${fileData.metadata.atom_count} atoms, ${fileData.metadata.residue_count} residues`;
        } else if (fileData.sequences) {
            const seqCount = Object.keys(fileData.sequences).length;
            details = `${seqCount} sequence${seqCount > 1 ? 's' : ''}`;
        }

        indicator.innerHTML = `
            <div class="file-attachment-info">
                <i data-feather="${fileData.file_type === 'pdb' ? 'box' : 'file-text'}"></i>
                <span class="file-name">${fileData.filename}</span>
                <span class="file-details">${details}</span>
            </div>
            <button class="btn-icon file-remove" aria-label="Remove file">
                <i data-feather="x"></i>
            </button>
        `;

        // Insert before input container
        const inputArea = document.querySelector('.chat-input-area');
        const inputContainer = inputArea.querySelector('.input-container');
        inputArea.insertBefore(indicator, inputContainer);

        // Initialize icons
        if (typeof feather !== 'undefined') {
            feather.replace();
        }

        // Remove button handler
        indicator.querySelector('.file-remove').addEventListener('click', () => {
            this.clearFileAttachment();
        });
    },

    clearFileAttachment() {
        this.uploadedFile = null;
        const indicator = document.querySelector('.file-attachment');
        if (indicator) indicator.remove();

        // Disable send if no text
        const hasContent = this.inputElement.value.trim().length > 0;
        this.sendButton.disabled = !hasContent;
    },

    setupInput() {
        // Enable/disable send button based on input
        this.inputElement.addEventListener('input', () => {
            const hasContent = this.inputElement.value.trim().length > 0;
            this.sendButton.disabled = !hasContent;
            this.autoResize();
        });

        // Handle Enter key
        this.inputElement.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                if (!this.sendButton.disabled) {
                    this.sendMessage();
                }
            }
        });
    },

    autoResize() {
        this.inputElement.style.height = 'auto';
        this.inputElement.style.height = Math.min(this.inputElement.scrollHeight, 200) + 'px';
    },

    async sendMessage() {
        const content = this.inputElement.value.trim();
        if (!content && !this.uploadedFile) return;

        // Check if we have a conversation
        let conversationId = App.conversationId;

        // If no conversation, create one first
        if (!conversationId) {
            try {
                const data = await App.api('/api/conversations/', {
                    method: 'POST',
                    body: JSON.stringify({ title: 'New Conversation' })
                });
                conversationId = data.id;
                App.conversationId = conversationId;

                // Update URL without reload
                window.history.pushState({}, '', `/chat/${conversationId}/`);
            } catch (error) {
                App.notify('Failed to create conversation', 'error');
                return;
            }
        }

        // Build display content with file info
        let displayContent = content;
        if (this.uploadedFile) {
            if (content) {
                displayContent += `\n[Attached: ${this.uploadedFile.filename}]`;
            } else {
                displayContent = `Analyze uploaded file: ${this.uploadedFile.filename}`;
            }
        }

        // Clear input and file
        this.inputElement.value = '';
        this.sendButton.disabled = true;
        this.autoResize();

        // Hide welcome screen if visible
        const welcomeScreen = document.getElementById('welcome-screen');
        if (welcomeScreen) {
            welcomeScreen.style.display = 'none';
        }

        // Add user message to UI
        this.addMessage({
            role: 'user',
            content: displayContent,
            created_at: new Date().toISOString()
        });

        // Build request body
        const requestBody = {
            content: content || `Analyze the uploaded ${this.uploadedFile?.file_type?.toUpperCase()} file`
        };

        // Add file info if present
        if (this.uploadedFile) {
            requestBody.file_id = this.uploadedFile.file_id;
            requestBody.file_type = this.uploadedFile.file_type;

            // If FASTA with sequence, include first sequence
            if (this.uploadedFile.sequences) {
                const firstSeq = Object.values(this.uploadedFile.sequences)[0];
                if (firstSeq) {
                    requestBody.sequence = firstSeq.sequence;
                }
            }
        }

        // Clear file attachment
        this.clearFileAttachment();

        try {
            // Send message to API
            const response = await App.api(`/api/conversations/${conversationId}/messages/`, {
                method: 'POST',
                body: JSON.stringify(requestBody)
            });

            // Add assistant message placeholder
            this.addMessage({
                id: response.assistant_message.id,
                role: 'assistant',
                workflow_id: response.workflow_id,
                workflow_status: 'pending'
            });

            // Start SSE for workflow updates
            this.activeWorkflowId = response.workflow_id;
            SSE.connect(conversationId, response.workflow_id);

        } catch (error) {
            App.notify('Failed to send message: ' + error.message, 'error');

            // Add error message
            this.addMessage({
                role: 'assistant',
                content: 'Sorry, there was an error processing your message. Please try again.',
                workflow_status: 'failed'
            });
        }
    },

    addMessage(message) {
        const messageEl = this.createMessageElement(message);
        this.messagesContainer.appendChild(messageEl);
        this.scrollToBottom();

        // Reinitialize Feather icons for new elements
        if (typeof feather !== 'undefined') {
            feather.replace();
        }
    },

    createMessageElement(message) {
        const div = document.createElement('div');
        div.className = `message message-${message.role}`;
        if (message.id) {
            div.dataset.messageId = message.id;
        }

        const isWorkflowPending = message.workflow_status === 'pending' || message.workflow_status === 'running';

        div.innerHTML = `
            <div class="message-avatar">
                ${message.role === 'user'
                    ? '<div class="avatar avatar-user"><i data-feather="user"></i></div>'
                    : '<div class="avatar avatar-assistant"><span>🧬</span></div>'
                }
            </div>
            <div class="message-content">
                <div class="message-header">
                    <span class="message-role">${message.role === 'user' ? 'You' : 'SynDe'}</span>
                    <span class="message-time">Just now</span>
                </div>
                <div class="message-body">
                    ${isWorkflowPending
                        ? `<div class="workflow-status" data-workflow-id="${message.workflow_id}">
                               <div class="workflow-status-header">
                                   <div class="workflow-spinner"><div class="spinner"></div></div>
                                   <div class="workflow-info">
                                       <span class="workflow-stage">Processing...</span>
                                       <span class="workflow-detail" id="workflow-detail-${message.workflow_id}">Starting workflow</span>
                                   </div>
                               </div>
                           </div>`
                        : message.workflow_status === 'failed'
                        ? `<div class="workflow-error">
                               <i data-feather="alert-circle"></i>
                               <span>${App.escapeHtml(message.content || 'An error occurred')}</span>
                           </div>`
                        : `<div class="message-text">${this.formatContent(message.content)}</div>`
                    }
                </div>
            </div>
        `;

        return div;
    },

    formatContent(content) {
        if (!content) return '';

        // Convert newlines to paragraphs
        return content
            .split('\n\n')
            .map(p => `<p>${App.escapeHtml(p).replace(/\n/g, '<br>')}</p>`)
            .join('');
    },

    updateWorkflowStatus(workflowId, status, data) {
        const statusEl = document.querySelector(`.workflow-status[data-workflow-id="${workflowId}"]`);
        if (!statusEl) return;

        const detailEl = statusEl.querySelector('.workflow-detail');
        const stageEl = statusEl.querySelector('.workflow-stage');

        if (status === 'node' && data.node) {
            if (stageEl) stageEl.textContent = 'Processing...';
            if (detailEl) detailEl.textContent = `Running: ${data.node}`;
        }
    },

    updateWorkflowLogs(workflowId, logs) {
        const statusEl = document.querySelector(`.workflow-status[data-workflow-id="${workflowId}"]`);
        if (!statusEl) return;

        // Get or create logs container
        let logsContainer = statusEl.querySelector('.workflow-logs');
        if (!logsContainer) {
            logsContainer = document.createElement('div');
            logsContainer.className = 'workflow-logs';
            statusEl.appendChild(logsContainer);
        }

        // Append new logs
        logs.forEach(log => {
            const logEl = document.createElement('div');
            logEl.className = 'workflow-log-entry';
            logEl.textContent = log.msg;
            logsContainer.appendChild(logEl);
        });

        // Scroll to bottom of logs
        logsContainer.scrollTop = logsContainer.scrollHeight;

        // Update the detail text with the latest log
        if (logs.length > 0) {
            const detailEl = statusEl.querySelector('.workflow-detail');
            if (detailEl) {
                detailEl.textContent = logs[logs.length - 1].msg;
            }
        }
    },

    completeWorkflow(workflowId, result) {
        const messageEl = this.messagesContainer.querySelector(`.message[data-message-id]`);
        const statusEl = document.querySelector(`.workflow-status[data-workflow-id="${workflowId}"]`);

        if (statusEl) {
            const messageBody = statusEl.closest('.message-body');
            if (messageBody) {
                // Replace status with actual content
                let html = '';

                if (result.content) {
                    html += `<div class="message-text">${this.formatContent(result.content)}</div>`;
                }

                if (result.prediction_data && result.prediction_data.response_html) {
                    html += `<div class="message-results">${result.prediction_data.response_html}</div>`;
                }

                if (result.structure_data && result.structure_data.pdb_data) {
                    html += `
                        <div class="message-actions">
                            <button class="btn btn-secondary btn-small view-structure-btn"
                                    data-pdb="${App.escapeHtml(result.structure_data.pdb_data)}">
                                <i data-feather="box"></i>
                                <span>View Structure</span>
                            </button>
                        </div>
                    `;
                }

                messageBody.innerHTML = html || '<div class="message-text">Task completed.</div>';

                // Reinitialize icons and setup structure buttons
                if (typeof feather !== 'undefined') {
                    feather.replace();
                }
                this.setupStructureButtons();
            }
        }

        this.activeWorkflowId = null;
    },

    failWorkflow(workflowId, error) {
        const statusEl = document.querySelector(`.workflow-status[data-workflow-id="${workflowId}"]`);

        if (statusEl) {
            const messageBody = statusEl.closest('.message-body');
            if (messageBody) {
                messageBody.innerHTML = `
                    <div class="workflow-error">
                        <i data-feather="alert-circle"></i>
                        <span>${App.escapeHtml(error || 'An error occurred')}</span>
                    </div>
                `;

                if (typeof feather !== 'undefined') {
                    feather.replace();
                }
            }
        }

        this.activeWorkflowId = null;
    },

    scrollToBottom() {
        if (this.messagesContainer) {
            this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
        }
    },

    setupSuggestions() {
        const chips = document.querySelectorAll('.suggestion-chip');
        chips.forEach(chip => {
            chip.addEventListener('click', () => {
                const prompt = chip.dataset.prompt;
                if (prompt && this.inputElement) {
                    this.inputElement.value = prompt;
                    this.inputElement.focus();
                    this.sendButton.disabled = false;
                }
            });
        });
    },

    setupStructureButtons() {
        const buttons = document.querySelectorAll('.view-structure-btn');
        buttons.forEach(btn => {
            // Remove old listeners
            btn.replaceWith(btn.cloneNode(true));
        });

        // Re-query and add listeners
        document.querySelectorAll('.view-structure-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const pdbData = btn.dataset.pdb;
                if (pdbData && typeof Viewer !== 'undefined') {
                    Viewer.show(pdbData);
                }
            });
        });
    },

    checkActiveWorkflows() {
        const statusElements = document.querySelectorAll('.workflow-status');
        statusElements.forEach(el => {
            const workflowId = el.dataset.workflowId;
            if (workflowId && App.conversationId) {
                this.activeWorkflowId = workflowId;
                SSE.connect(App.conversationId, workflowId);
            }
        });
    }
};

// Helper functions for message actions
function copyMessage(messageId) {
    const messageEl = document.querySelector(`.message[data-message-id="${messageId}"]`);
    if (messageEl) {
        const text = messageEl.querySelector('.message-text')?.textContent || '';
        navigator.clipboard.writeText(text).then(() => {
            App.notify('Message copied', 'info');
        });
    }
}

function toggleCollapse(messageId) {
    const messageEl = document.querySelector(`.message[data-message-id="${messageId}"]`);
    if (messageEl) {
        messageEl.classList.toggle('collapsed');
    }
}

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', () => {
    Chat.init();
});

window.Chat = Chat;
