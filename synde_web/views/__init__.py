"""Views for synde_web application."""

from synde_web.views.main import index, chat
from synde_web.views.auth import (
    login_view, logout_view, signup_view, profile_view
)
from synde_web.views.api import (
    ProjectViewSet, ConversationViewSet, MessageViewSet,
    send_message, get_suggestions
)
from synde_web.views.sse import workflow_stream

__all__ = [
    # Main views
    'index',
    'chat',
    # Auth views
    'login_view',
    'logout_view',
    'signup_view',
    'profile_view',
    # API views
    'ProjectViewSet',
    'ConversationViewSet',
    'MessageViewSet',
    'send_message',
    'get_suggestions',
    # SSE
    'workflow_stream',
]
