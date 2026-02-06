"""REST API views for synde_web."""

import json
import uuid
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.views import View
from django.utils.decorators import method_decorator

from synde_web.models import Project, Conversation, Message, WorkflowCheckpoint


class APIView(View):
    """Base API view with common functionality."""

    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)

    def json_response(self, data, status=200):
        return JsonResponse(data, status=status)

    def error_response(self, message, status=400):
        return JsonResponse({'error': message}, status=status)

    def get_json_body(self, request):
        try:
            return json.loads(request.body) if request.body else {}
        except json.JSONDecodeError:
            return {}


@method_decorator(csrf_exempt, name='dispatch')
class ProjectViewSet(APIView):
    """CRUD operations for projects."""

    def get(self, request, project_id=None):
        """List projects or get single project."""
        if project_id:
            project = get_object_or_404(Project, id=project_id, user=request.user)
            return self.json_response(self._serialize_project(project))

        projects = Project.objects.filter(
            user=request.user,
            is_archived=False
        ).order_by('-is_pinned', '-updated_at')

        return self.json_response({
            'projects': [self._serialize_project(p) for p in projects]
        })

    def post(self, request, project_id=None):
        """Create a new project."""
        data = self.get_json_body(request)

        project = Project.objects.create(
            user=request.user,
            name=data.get('name', 'New Project'),
            description=data.get('description', ''),
            color=data.get('color', '#6366f1'),
            icon=data.get('icon', 'folder')
        )

        return self.json_response(self._serialize_project(project), status=201)

    def put(self, request, project_id):
        """Update a project."""
        project = get_object_or_404(Project, id=project_id, user=request.user)
        data = self.get_json_body(request)

        for field in ['name', 'description', 'color', 'icon', 'is_pinned', 'is_archived']:
            if field in data:
                setattr(project, field, data[field])

        project.save()
        return self.json_response(self._serialize_project(project))

    def delete(self, request, project_id):
        """Delete a project."""
        project = get_object_or_404(Project, id=project_id, user=request.user)
        project.delete()
        return self.json_response({'deleted': True})

    def _serialize_project(self, project):
        return {
            'id': project.id,
            'name': project.name,
            'description': project.description,
            'color': project.color,
            'icon': project.icon,
            'is_pinned': project.is_pinned,
            'is_archived': project.is_archived,
            'conversation_count': project.conversation_count,
            'created_at': project.created_at.isoformat(),
            'updated_at': project.updated_at.isoformat(),
        }


@method_decorator(csrf_exempt, name='dispatch')
class ConversationViewSet(APIView):
    """CRUD operations for conversations."""

    def get(self, request, conversation_id=None):
        """List conversations or get single conversation."""
        if conversation_id:
            conversation = get_object_or_404(
                Conversation, id=conversation_id, user=request.user
            )
            return self.json_response(self._serialize_conversation(conversation, include_messages=True))

        # Filter options
        project_id = request.GET.get('project')
        archived = request.GET.get('archived', 'false') == 'true'

        queryset = Conversation.objects.filter(
            user=request.user,
            is_archived=archived
        )

        if project_id:
            queryset = queryset.filter(project_id=project_id)

        conversations = queryset.order_by('-is_pinned', '-updated_at')[:50]

        return self.json_response({
            'conversations': [self._serialize_conversation(c) for c in conversations]
        })

    def post(self, request, conversation_id=None):
        """Create a new conversation."""
        data = self.get_json_body(request)

        conversation = Conversation.objects.create(
            user=request.user,
            title=data.get('title', 'New Conversation'),
            project_id=data.get('project_id'),
        )

        return self.json_response(self._serialize_conversation(conversation), status=201)

    def put(self, request, conversation_id):
        """Update a conversation."""
        conversation = get_object_or_404(
            Conversation, id=conversation_id, user=request.user
        )
        data = self.get_json_body(request)

        for field in ['title', 'project_id', 'is_pinned', 'is_archived']:
            if field in data:
                setattr(conversation, field, data[field])

        conversation.save()
        return self.json_response(self._serialize_conversation(conversation))

    def delete(self, request, conversation_id):
        """Delete a conversation."""
        conversation = get_object_or_404(
            Conversation, id=conversation_id, user=request.user
        )
        conversation.delete()
        return self.json_response({'deleted': True})

    def _serialize_conversation(self, conversation, include_messages=False):
        data = {
            'id': conversation.id,
            'title': conversation.title,
            'summary': conversation.summary,
            'project_id': conversation.project_id,
            'is_pinned': conversation.is_pinned,
            'is_archived': conversation.is_archived,
            'message_count': conversation.message_count,
            'context': conversation.context,
            'created_at': conversation.created_at.isoformat(),
            'updated_at': conversation.updated_at.isoformat(),
        }

        if include_messages:
            messages = conversation.messages.all().order_by('created_at')
            data['messages'] = [self._serialize_message(m) for m in messages]

        return data

    def _serialize_message(self, message):
        return {
            'id': message.id,
            'role': message.role,
            'content': message.content,
            'workflow_id': message.workflow_id,
            'workflow_status': message.workflow_status,
            'has_structure': message.has_structure,
            'has_predictions': message.has_predictions,
            'has_mutants': message.has_mutants,
            'protein_data': message.protein_data,
            'structure_data': message.structure_data,
            'prediction_data': message.prediction_data,
            'generation_data': message.generation_data,
            'created_at': message.created_at.isoformat(),
        }


@method_decorator(csrf_exempt, name='dispatch')
class MessageViewSet(APIView):
    """CRUD operations for messages."""

    def get(self, request, conversation_id, message_id=None):
        """List messages in conversation."""
        conversation = get_object_or_404(
            Conversation, id=conversation_id, user=request.user
        )

        if message_id:
            message = get_object_or_404(Message, id=message_id, conversation=conversation)
            return self.json_response(self._serialize_message(message))

        messages = conversation.messages.all().order_by('created_at')

        return self.json_response({
            'messages': [self._serialize_message(m) for m in messages]
        })

    def _serialize_message(self, message):
        return {
            'id': message.id,
            'role': message.role,
            'content': message.content,
            'workflow_id': message.workflow_id,
            'workflow_status': message.workflow_status,
            'has_structure': message.has_structure,
            'has_predictions': message.has_predictions,
            'has_mutants': message.has_mutants,
            'protein_data': message.protein_data,
            'structure_data': message.structure_data,
            'prediction_data': message.prediction_data,
            'generation_data': message.generation_data,
            'created_at': message.created_at.isoformat(),
        }


@csrf_exempt
@login_required
@require_http_methods(["POST"])
def send_message(request, conversation_id):
    """
    Send a message and start workflow.

    Creates a user message, starts the LangGraph workflow,
    and returns the workflow ID for SSE streaming.

    Accepts JSON with:
    - content: Message text
    - file_id: Optional uploaded file ID
    - file_type: 'pdb' or 'fasta'
    - sequence: Optional direct sequence input
    - use_mock: Optional override for mock mode (default: from settings)
    """
    from synde_web.tasks import run_workflow
    from synde_web.views.upload import get_uploaded_file
    import os
    from django.conf import settings

    conversation = get_object_or_404(
        Conversation, id=conversation_id, user=request.user
    )

    # Check quota
    if not request.user.has_quota_remaining():
        return JsonResponse({
            'error': 'Monthly quota exceeded. Please upgrade your plan.'
        }, status=429)

    try:
        data = json.loads(request.body) if request.body else {}
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON'}, status=400)

    content = data.get('content', '').strip()
    if not content:
        return JsonResponse({'error': 'Message content required'}, status=400)

    # Handle file uploads
    file_id = data.get('file_id')
    file_type = data.get('file_type')
    uploaded_pdb_path = None
    uploaded_pdb_content = None
    uploaded_sequence = data.get('sequence')

    if file_id:
        if file_type == 'pdb':
            pdb_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'pdb', f'{file_id}.pdb')
            if os.path.exists(pdb_path):
                uploaded_pdb_path = pdb_path
                with open(pdb_path, 'r') as f:
                    uploaded_pdb_content = f.read()
        elif file_type == 'fasta':
            fasta_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'fasta', f'{file_id}.fasta')
            if os.path.exists(fasta_path):
                # Parse first sequence from FASTA
                from synde_web.views.upload import parse_fasta
                with open(fasta_path, 'r') as f:
                    sequences = parse_fasta(f.read())
                if sequences:
                    # Use first sequence
                    uploaded_sequence = list(sequences.values())[0]

    # Mock mode setting
    use_mock = data.get('use_mock')
    if use_mock is None:
        use_mock = os.getenv('MOCK_GPU', 'true').lower() in ('true', '1', 'yes')

    # Create user message with file info
    user_message_content = content
    if file_id:
        if file_type == 'pdb':
            user_message_content += f"\n[Attached PDB file: {file_id}]"
        elif file_type == 'fasta':
            user_message_content += f"\n[Attached FASTA file: {file_id}]"

    user_message = Message.objects.create(
        conversation=conversation,
        role='user',
        content=user_message_content,
        protein_data={
            'file_id': file_id,
            'file_type': file_type,
            'sequence': uploaded_sequence[:100] + '...' if uploaded_sequence and len(uploaded_sequence) > 100 else uploaded_sequence,
        } if file_id or uploaded_sequence else {}
    )

    # Generate workflow ID
    workflow_id = str(uuid.uuid4())

    # Create assistant message placeholder
    assistant_message = Message.objects.create(
        conversation=conversation,
        role='assistant',
        content='',
        workflow_id=workflow_id,
        workflow_status='pending'
    )

    # Create workflow checkpoint
    WorkflowCheckpoint.objects.create(
        job_id=workflow_id,
        thread_id=workflow_id,
        conversation=conversation,
        message=assistant_message,
        user=request.user,
        checkpoint_data={},
        status='active'
    )

    # Build context with file info
    workflow_context = conversation.context.copy() if conversation.context else {}
    if uploaded_sequence:
        workflow_context['uploaded_sequence'] = uploaded_sequence
    if uploaded_pdb_path:
        workflow_context['uploaded_pdb_path'] = uploaded_pdb_path
    if uploaded_pdb_content:
        workflow_context['uploaded_pdb_content'] = uploaded_pdb_content

    # Start workflow task
    run_workflow.delay(
        workflow_id=workflow_id,
        user_query=content,
        conversation_id=conversation.id,
        message_id=assistant_message.id,
        context=workflow_context,
        uploaded_pdb_path=uploaded_pdb_path,
        uploaded_pdb_content=uploaded_pdb_content,
        uploaded_sequence=uploaded_sequence,
        use_mock=use_mock
    )

    # Increment usage
    request.user.increment_usage()

    # Update conversation title if first message
    if conversation.message_count <= 2:
        conversation.generate_title()

    return JsonResponse({
        'user_message': {
            'id': user_message.id,
            'role': 'user',
            'content': user_message.content,
            'created_at': user_message.created_at.isoformat(),
        },
        'assistant_message': {
            'id': assistant_message.id,
            'role': 'assistant',
            'workflow_id': workflow_id,
            'workflow_status': 'pending',
        },
        'workflow_id': workflow_id,
    })


@login_required
@require_http_methods(["GET"])
def get_suggestions(request):
    """
    Get suggestion prompts based on context.

    Returns contextual suggestions based on the current
    conversation state and user history.
    """
    conversation_id = request.GET.get('conversation_id')

    # Base suggestions
    suggestions = [
        {
            'category': 'prediction',
            'label': 'Predict stability',
            'prompt': 'Predict the thermal stability of my protein',
            'icon': 'thermometer'
        },
        {
            'category': 'prediction',
            'label': 'Find EC number',
            'prompt': 'Predict the EC number for this sequence',
            'icon': 'tag'
        },
        {
            'category': 'prediction',
            'label': 'Predict kcat',
            'prompt': 'Predict the catalytic rate (kcat) for my enzyme',
            'icon': 'activity'
        },
        {
            'category': 'structure',
            'label': 'Predict structure',
            'prompt': 'Predict the 3D structure of my protein',
            'icon': 'box'
        },
        {
            'category': 'generation',
            'label': 'Design mutant',
            'prompt': 'Generate stabilizing mutations for my protein',
            'icon': 'edit-3'
        },
        {
            'category': 'analysis',
            'label': 'Analyze pocket',
            'prompt': 'Find and analyze the binding pocket',
            'icon': 'target'
        },
    ]

    # Add context-specific suggestions if conversation exists
    if conversation_id:
        try:
            conversation = Conversation.objects.get(
                id=conversation_id,
                user=request.user
            )
            context = conversation.context

            # If we have a sequence, add sequence-specific suggestions
            if context.get('last_sequence'):
                suggestions.insert(0, {
                    'category': 'continue',
                    'label': 'Continue with sequence',
                    'prompt': 'Continue analyzing the current sequence',
                    'icon': 'arrow-right'
                })

            # If we have a UniProt ID, add lookup suggestion
            if context.get('uniprot_id'):
                uniprot_id = context['uniprot_id']
                suggestions.insert(0, {
                    'category': 'lookup',
                    'label': f'Use {uniprot_id}',
                    'prompt': f'Use UniProt ID {uniprot_id}',
                    'icon': 'database'
                })

        except Conversation.DoesNotExist:
            pass

    return JsonResponse({'suggestions': suggestions})


# =============================================================================
# Workflow Logs API
# =============================================================================

@login_required
@require_http_methods(["GET"])
def workflow_logs(request, workflow_id):
    """
    Get live logs for a workflow.

    Query params:
        since: Index to start from (for incremental fetching)

    Returns:
        {
            'logs': [{'ts': timestamp, 'msg': message}, ...],
            'next_index': next index for incremental fetching
        }
    """
    from synde_graph.utils.live_logger import get_logs

    # Verify the workflow belongs to this user
    checkpoint = get_object_or_404(
        WorkflowCheckpoint,
        job_id=workflow_id,
        conversation__user=request.user
    )

    since = int(request.GET.get('since', 0))
    logs, next_index = get_logs(workflow_id, since)

    return JsonResponse({
        'logs': logs,
        'next_index': next_index,
        'status': checkpoint.status,
    })
