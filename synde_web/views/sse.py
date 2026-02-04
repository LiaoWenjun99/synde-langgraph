"""Server-Sent Events views for real-time updates."""

import json
import time
from django.http import StreamingHttpResponse, HttpResponse
from django.views.decorators.http import require_GET
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404

from synde_web.models import Conversation, Message, WorkflowCheckpoint


@require_GET
@login_required
def workflow_stream(request, conversation_id, workflow_id):
    """
    SSE endpoint for workflow status updates.

    Streams real-time updates about workflow progress including:
    - Node transitions
    - GPU task status
    - Completion/error states
    - Result data
    """
    # Verify access
    conversation = get_object_or_404(
        Conversation,
        id=conversation_id,
        user=request.user
    )

    # Get or check workflow exists
    try:
        checkpoint = WorkflowCheckpoint.objects.get(
            job_id=workflow_id,
            conversation=conversation
        )
    except WorkflowCheckpoint.DoesNotExist:
        return HttpResponse(
            f"event: error\ndata: {json.dumps({'error': 'Workflow not found'})}\n\n",
            content_type='text/event-stream'
        )

    def event_stream():
        """Generate SSE events for workflow progress."""
        last_node = None
        last_status = None
        poll_count = 0
        max_polls = 600  # 5 minutes with 0.5s interval

        # Send initial connection event
        yield format_sse('connected', {
            'workflow_id': workflow_id,
            'status': checkpoint.status,
            'current_node': checkpoint.current_node
        })

        while poll_count < max_polls:
            try:
                # Refresh checkpoint from DB
                checkpoint.refresh_from_db()

                # Send node update if changed
                if checkpoint.current_node != last_node:
                    last_node = checkpoint.current_node
                    yield format_sse('node', {
                        'node': checkpoint.current_node,
                        'status': checkpoint.status,
                        'history': checkpoint.node_history
                    })

                # Send status update if changed
                if checkpoint.status != last_status:
                    last_status = checkpoint.status
                    yield format_sse('status', {
                        'status': checkpoint.status,
                        'current_node': checkpoint.current_node
                    })

                # Check for completion
                if checkpoint.status == 'completed':
                    # Get the message with results
                    try:
                        message = Message.objects.get(workflow_id=workflow_id)
                        result_data = {
                            'content': message.content,
                            'protein_data': message.protein_data,
                            'structure_data': message.structure_data,
                            'prediction_data': message.prediction_data,
                            'generation_data': message.generation_data,
                        }
                    except Message.DoesNotExist:
                        result_data = checkpoint.checkpoint_data

                    yield format_sse('complete', result_data)
                    break

                # Check for failure
                if checkpoint.status == 'failed':
                    yield format_sse('error', {
                        'error': checkpoint.last_error,
                        'recoverable': False
                    })
                    break

                # Send heartbeat every 10 polls
                if poll_count % 10 == 0:
                    yield format_sse('heartbeat', {
                        'poll': poll_count,
                        'status': checkpoint.status
                    })

            except Exception as e:
                yield format_sse('error', {
                    'error': str(e),
                    'recoverable': True
                })

            poll_count += 1
            time.sleep(0.5)

        # Timeout
        if poll_count >= max_polls:
            yield format_sse('timeout', {
                'message': 'Workflow stream timed out'
            })

    response = StreamingHttpResponse(
        event_stream(),
        content_type='text/event-stream'
    )

    # Disable caching for SSE
    response['Cache-Control'] = 'no-cache'
    response['X-Accel-Buffering'] = 'no'

    return response


def format_sse(event: str, data: dict) -> str:
    """Format data as SSE event."""
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


@require_GET
@login_required
def workflow_status(request, workflow_id):
    """
    Get current workflow status (non-streaming).

    Returns the current status of a workflow for polling clients.
    """
    try:
        checkpoint = WorkflowCheckpoint.objects.get(job_id=workflow_id)

        # Verify user has access
        if checkpoint.user != request.user:
            return HttpResponse(status=403)

        data = {
            'workflow_id': workflow_id,
            'status': checkpoint.status,
            'current_node': checkpoint.current_node,
            'node_history': checkpoint.node_history,
            'error_count': checkpoint.error_count,
            'last_error': checkpoint.last_error,
            'created_at': checkpoint.created_at.isoformat(),
            'updated_at': checkpoint.updated_at.isoformat(),
        }

        # Include result data if completed
        if checkpoint.status == 'completed':
            try:
                message = Message.objects.get(workflow_id=workflow_id)
                data['result'] = {
                    'content': message.content,
                    'has_structure': message.has_structure,
                    'has_predictions': message.has_predictions,
                    'has_mutants': message.has_mutants,
                }
            except Message.DoesNotExist:
                data['result'] = checkpoint.checkpoint_data

        return HttpResponse(
            json.dumps(data),
            content_type='application/json'
        )

    except WorkflowCheckpoint.DoesNotExist:
        return HttpResponse(
            json.dumps({'error': 'Workflow not found'}),
            status=404,
            content_type='application/json'
        )
