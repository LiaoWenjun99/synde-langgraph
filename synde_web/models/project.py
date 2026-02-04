"""Project model for organizing conversations."""

from django.db import models
from django.conf import settings


class Project(models.Model):
    """
    Project folders for organizing conversations.

    Users can group related conversations into projects,
    similar to folders in a file system.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='projects'
    )
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    color = models.CharField(
        max_length=7,
        default='#6366f1',
        help_text='Hex color code for project icon'
    )
    icon = models.CharField(
        max_length=50,
        default='folder',
        help_text='Icon name (e.g., folder, flask, dna)'
    )

    # Organization
    is_archived = models.BooleanField(default=False)
    is_pinned = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'synde_projects'
        ordering = ['-is_pinned', 'sort_order', '-updated_at']
        verbose_name = 'Project'
        verbose_name_plural = 'Projects'

    def __str__(self):
        return f"{self.name} ({self.user.username})"

    @property
    def conversation_count(self):
        """Get number of conversations in project."""
        return self.conversations.count()

    @property
    def active_conversations(self):
        """Get non-archived conversations."""
        return self.conversations.filter(is_archived=False)
