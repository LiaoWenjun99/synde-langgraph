"""Conversation model for chat threads."""

from django.db import models
from django.conf import settings


class Conversation(models.Model):
    """
    Chat thread/conversation model.

    Each conversation represents a separate chat session with
    its own message history and context.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='conversations'
    )
    project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='conversations'
    )

    # Display
    title = models.CharField(max_length=255)
    summary = models.TextField(blank=True, help_text='Auto-generated summary')

    # Organization
    is_pinned = models.BooleanField(default=False)
    is_archived = models.BooleanField(default=False)

    # Context (carried between messages)
    context = models.JSONField(
        default=dict,
        blank=True,
        help_text='Session context (last sequence, UniProt ID, etc.)'
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'synde_conversations'
        ordering = ['-is_pinned', '-updated_at']
        verbose_name = 'Conversation'
        verbose_name_plural = 'Conversations'

    def __str__(self):
        return f"{self.title} ({self.user.username})"

    @property
    def message_count(self):
        """Get number of messages in conversation."""
        return self.messages.count()

    @property
    def last_message(self):
        """Get the most recent message."""
        return self.messages.order_by('-created_at').first()

    def generate_title(self):
        """Auto-generate title from first user message."""
        first_msg = self.messages.filter(role='user').first()
        if first_msg:
            content = first_msg.content[:50]
            if len(first_msg.content) > 50:
                content += '...'
            self.title = content
            self.save(update_fields=['title'])
        return self.title

    def update_context(self, **kwargs):
        """Update conversation context."""
        self.context.update(kwargs)
        self.save(update_fields=['context', 'updated_at'])
