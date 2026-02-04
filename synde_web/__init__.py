"""
SynDe Web - Modern chatbot UI for protein engineering workflows.

A ChatGPT/Claude-style interface with:
- Conversation threads and history
- Project organization
- Real-time SSE updates
- 3D protein visualization
"""

# Import Celery app for Django integration
from synde_web.celery import app as celery_app

default_app_config = 'synde_web.apps.SyndeWebConfig'

__all__ = ('celery_app',)
