"""Workflow checkpoint model for persistence."""

from django.db import models
from django.conf import settings


class WorkflowCheckpoint(models.Model):
    """
    Persistent storage for LangGraph workflow checkpoints.

    Stores workflow state for:
    - Resume after interruption
    - Historical analysis
    - Debugging
    """

    # Identifiers
    job_id = models.CharField(max_length=100, db_index=True)
    thread_id = models.CharField(max_length=100, db_index=True)
    checkpoint_id = models.CharField(max_length=100)
    checkpoint_ns = models.CharField(max_length=100, default='', blank=True)

    # References
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='workflow_checkpoints'
    )
    conversation = models.ForeignKey(
        'Conversation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='checkpoints'
    )
    message = models.ForeignKey(
        'Message',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='checkpoints'
    )

    # State
    checkpoint_data = models.JSONField(help_text='Serialized workflow state')
    metadata = models.JSONField(default=dict, blank=True)

    # Status
    status = models.CharField(
        max_length=20,
        choices=[
            ('active', 'Active'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
            ('expired', 'Expired'),
        ],
        default='active'
    )
    current_node = models.CharField(max_length=100, blank=True)
    node_history = models.JSONField(default=list, blank=True)

    # Error tracking
    error_count = models.IntegerField(default=0)
    last_error = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'synde_workflow_checkpoints'
        ordering = ['-updated_at']
        indexes = [
            models.Index(fields=['job_id', 'thread_id']),
            models.Index(fields=['user', 'status']),
        ]
        verbose_name = 'Workflow Checkpoint'
        verbose_name_plural = 'Workflow Checkpoints'

    def __str__(self):
        return f"Checkpoint {self.job_id} ({self.status})"

    @classmethod
    def get_or_create_for_workflow(cls, job_id: str, user=None, conversation=None):
        """Get or create checkpoint for a workflow."""
        checkpoint, created = cls.objects.get_or_create(
            job_id=job_id,
            thread_id=job_id,
            defaults={
                'user': user,
                'conversation': conversation,
                'checkpoint_data': {},
            }
        )
        return checkpoint, created

    def update_state(self, state: dict, metadata: dict = None):
        """Update checkpoint with new state."""
        self.checkpoint_data = state
        self.current_node = state.get('current_node', '')
        self.node_history = state.get('node_history', [])

        if metadata:
            self.metadata.update(metadata)

        # Check for completion
        if self.current_node in ('response_formatter', 'end'):
            self.status = 'completed'

        # Check for errors
        errors = state.get('errors', [])
        self.error_count = len(errors)
        if errors:
            self.last_error = errors[-1].get('message', '')
            if any(not e.get('recoverable', True) for e in errors):
                self.status = 'failed'

        self.save()

    def mark_completed(self):
        """Mark workflow as completed."""
        self.status = 'completed'
        self.save(update_fields=['status', 'updated_at'])

    def mark_failed(self, error: str):
        """Mark workflow as failed."""
        self.status = 'failed'
        self.last_error = error
        self.error_count += 1
        self.save(update_fields=['status', 'last_error', 'error_count', 'updated_at'])
