"""URL configuration for synde_web."""

from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static

from synde_web.views import main, auth, api, sse

urlpatterns = [
    # Admin
    path('admin/', admin.site.urls),

    # Main pages
    path('', main.index, name='index'),
    path('chat/<int:conversation_id>/', main.chat, name='chat'),

    # Authentication
    path('auth/login/', auth.login_view, name='login'),
    path('auth/logout/', auth.logout_view, name='logout'),
    path('auth/signup/', auth.signup_view, name='signup'),
    path('auth/profile/', auth.profile_view, name='profile'),

    # API - Projects
    path('api/projects/', api.ProjectViewSet.as_view(), name='api_projects'),
    path('api/projects/<int:project_id>/', api.ProjectViewSet.as_view(), name='api_project_detail'),

    # API - Conversations
    path('api/conversations/', api.ConversationViewSet.as_view(), name='api_conversations'),
    path('api/conversations/<int:conversation_id>/', api.ConversationViewSet.as_view(), name='api_conversation_detail'),

    # API - Messages
    path('api/conversations/<int:conversation_id>/messages/', api.send_message, name='api_messages'),
    path('api/conversations/<int:conversation_id>/messages/<int:message_id>/',
         api.MessageViewSet.as_view(), name='api_message_detail'),

    # API - Suggestions
    path('api/suggestions/', api.get_suggestions, name='api_suggestions'),

    # SSE streaming
    path('api/conversations/<int:conversation_id>/stream/<str:workflow_id>/',
         sse.workflow_stream, name='workflow_stream'),

    # Workflow status (non-SSE)
    path('api/workflow/<str:workflow_id>/status/', sse.workflow_status, name='workflow_status'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
