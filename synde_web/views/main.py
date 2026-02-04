"""Main page views."""

from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required

from synde_web.models import Project, Conversation


@login_required
def index(request):
    """
    Main chat interface.

    Displays the sidebar with projects/conversations and
    the main chat area.
    """
    user = request.user

    # Get user's projects
    projects = Project.objects.filter(
        user=user,
        is_archived=False
    ).prefetch_related('conversations')

    # Get recent conversations (not in any project)
    recent_conversations = Conversation.objects.filter(
        user=user,
        project__isnull=True,
        is_archived=False
    ).order_by('-updated_at')[:10]

    # Get pinned conversations
    pinned_conversations = Conversation.objects.filter(
        user=user,
        is_pinned=True,
        is_archived=False
    ).order_by('-updated_at')

    context = {
        'projects': projects,
        'recent_conversations': recent_conversations,
        'pinned_conversations': pinned_conversations,
        'current_conversation': None,
    }

    return render(request, 'synde_web/index.html', context)


@login_required
def chat(request, conversation_id):
    """
    Chat view for a specific conversation.

    Loads the conversation history and renders the chat interface.
    """
    user = request.user

    # Get the conversation
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        user=user
    )

    # Get messages
    messages = conversation.messages.all().order_by('created_at')

    # Get user's projects for sidebar
    projects = Project.objects.filter(
        user=user,
        is_archived=False
    ).prefetch_related('conversations')

    # Get recent conversations
    recent_conversations = Conversation.objects.filter(
        user=user,
        project__isnull=True,
        is_archived=False
    ).order_by('-updated_at')[:10]

    # Get pinned conversations
    pinned_conversations = Conversation.objects.filter(
        user=user,
        is_pinned=True,
        is_archived=False
    ).order_by('-updated_at')

    context = {
        'projects': projects,
        'recent_conversations': recent_conversations,
        'pinned_conversations': pinned_conversations,
        'current_conversation': conversation,
        'messages': messages,
    }

    return render(request, 'synde_web/index.html', context)
