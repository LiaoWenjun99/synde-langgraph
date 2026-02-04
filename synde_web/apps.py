"""Django app configuration for synde_web."""

from django.apps import AppConfig


class SyndeWebConfig(AppConfig):
    """Configuration for the SynDe Web application."""

    default_auto_field = 'django.db.models.BigAutoField'
    name = 'synde_web'
    verbose_name = 'SynDe Protein Engineering'

    def ready(self):
        """Initialize app when Django starts."""
        # Import signals if needed
        pass
