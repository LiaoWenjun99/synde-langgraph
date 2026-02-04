"""Extended user model for synde_web."""

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """
    Extended user model with profile information.

    Extends Django's AbstractUser to add fields for:
    - Profile preferences (theme, etc.)
    - API keys and quotas
    - Usage statistics
    """

    # Profile
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    bio = models.TextField(blank=True, max_length=500)
    organization = models.CharField(max_length=200, blank=True)

    # Preferences
    theme = models.CharField(
        max_length=20,
        choices=[('light', 'Light'), ('dark', 'Dark'), ('system', 'System')],
        default='system'
    )
    default_project = models.ForeignKey(
        'Project',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='default_users'
    )

    # API & Usage
    api_key = models.CharField(max_length=100, blank=True, null=True, unique=True)
    monthly_quota = models.IntegerField(default=1000)  # Workflow runs per month
    current_usage = models.IntegerField(default=0)

    # Timestamps
    last_activity = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'synde_users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username

    def get_display_name(self):
        """Get display name (full name or username)."""
        if self.first_name or self.last_name:
            return f"{self.first_name} {self.last_name}".strip()
        return self.username

    def has_quota_remaining(self):
        """Check if user has remaining monthly quota."""
        return self.current_usage < self.monthly_quota

    def increment_usage(self):
        """Increment usage counter."""
        self.current_usage += 1
        self.save(update_fields=['current_usage'])
