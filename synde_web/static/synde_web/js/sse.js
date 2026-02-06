/**
 * Server-Sent Events client for real-time workflow updates
 */

const SSE = {
    eventSource: null,
    reconnectAttempts: 0,
    maxReconnectAttempts: 5,
    reconnectDelay: 1000,

    connect(conversationId, workflowId) {
        // Close existing connection
        this.disconnect();

        const url = `/api/conversations/${conversationId}/stream/${workflowId}/`;

        try {
            this.eventSource = new EventSource(url);

            this.eventSource.addEventListener('connected', (e) => {
                console.log('SSE connected:', JSON.parse(e.data));
                this.reconnectAttempts = 0;
            });

            this.eventSource.addEventListener('node', (e) => {
                const data = JSON.parse(e.data);
                console.log('SSE node update:', data);
                Chat.updateWorkflowStatus(workflowId, 'node', data);
            });

            this.eventSource.addEventListener('status', (e) => {
                const data = JSON.parse(e.data);
                console.log('SSE status update:', data);
                Chat.updateWorkflowStatus(workflowId, 'status', data);
            });

            this.eventSource.addEventListener('logs', (e) => {
                const data = JSON.parse(e.data);
                console.log('SSE logs:', data);
                Chat.updateWorkflowLogs(workflowId, data.logs);
            });

            this.eventSource.addEventListener('complete', (e) => {
                const data = JSON.parse(e.data);
                console.log('SSE complete:', data);
                Chat.completeWorkflow(workflowId, data);
                this.disconnect();
            });

            this.eventSource.addEventListener('error', (e) => {
                if (e.data) {
                    const data = JSON.parse(e.data);
                    console.error('SSE error:', data);
                    if (!data.recoverable) {
                        Chat.failWorkflow(workflowId, data.error);
                        this.disconnect();
                    }
                }
            });

            this.eventSource.addEventListener('timeout', (e) => {
                console.warn('SSE timeout:', JSON.parse(e.data));
                this.disconnect();
            });

            this.eventSource.addEventListener('heartbeat', (e) => {
                // Keep-alive, no action needed
            });

            this.eventSource.onerror = (error) => {
                console.error('SSE connection error:', error);

                if (this.eventSource.readyState === EventSource.CLOSED) {
                    this.handleDisconnect(conversationId, workflowId);
                }
            };

        } catch (error) {
            console.error('Failed to create SSE connection:', error);
        }
    },

    disconnect() {
        if (this.eventSource) {
            this.eventSource.close();
            this.eventSource = null;
        }
    },

    handleDisconnect(conversationId, workflowId) {
        this.disconnect();

        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);

            console.log(`SSE reconnecting in ${delay}ms (attempt ${this.reconnectAttempts})`);

            setTimeout(() => {
                this.connect(conversationId, workflowId);
            }, delay);
        } else {
            console.error('SSE max reconnect attempts reached');
            Chat.failWorkflow(workflowId, 'Connection lost. Please refresh the page.');
        }
    },

    isConnected() {
        return this.eventSource && this.eventSource.readyState === EventSource.OPEN;
    }
};

window.SSE = SSE;
