"""Celery tasks for synde_web."""

import logging
from celery import shared_task

from synde_graph.utils.live_logger import (
    report,
    set_current_job_id,
    clear_logs,
)

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def run_workflow(
    self,
    workflow_id: str,
    user_query: str,
    conversation_id: int,
    message_id: int,
    context: dict = None,
    uploaded_pdb_path: str = None,
    uploaded_pdb_content: str = None,
    uploaded_sequence: str = None,
    use_mock: bool = True
):
    """
    Run LangGraph workflow as a Celery task.

    Args:
        workflow_id: Unique workflow identifier
        user_query: User's input message
        conversation_id: Associated conversation ID
        message_id: Assistant message ID to update
        context: Conversation context (previous state)
        uploaded_pdb_path: Path to uploaded PDB file
        uploaded_pdb_content: Content of uploaded PDB file
        uploaded_sequence: Uploaded protein sequence
        use_mock: Whether to use mock GPU responses
    """
    import os
    from django.db import transaction
    from synde_web.models import Message, Conversation, WorkflowCheckpoint
    from synde_graph.graph import run_workflow as execute_graph

    # Set mock mode environment variable
    os.environ['MOCK_GPU'] = 'true' if use_mock else 'false'

    # Set up live logging context
    set_current_job_id(workflow_id)
    clear_logs(workflow_id)  # Clear any old logs
    report("🚀 Workflow started")
    report(f"Query: {user_query[:100]}..." if len(user_query) > 100 else f"Query: {user_query}")

    logger.info(f"Starting workflow {workflow_id} for conversation {conversation_id} (mock={use_mock})")

    try:
        # Get the checkpoint and message
        checkpoint = WorkflowCheckpoint.objects.get(job_id=workflow_id)
        message = Message.objects.get(id=message_id)

        # Update status
        checkpoint.status = 'active'
        checkpoint.save(update_fields=['status', 'updated_at'])

        message.workflow_status = 'running'
        message.save(update_fields=['workflow_status', 'updated_at'])

        # Build session data with uploaded files
        session_data = context or {}
        if uploaded_sequence:
            session_data['uploaded_sequence'] = uploaded_sequence
            report("📎 Using uploaded sequence")

        if uploaded_pdb_path:
            report("📎 Using uploaded PDB structure")

        report("🔄 Running workflow graph...")

        # Run the workflow
        result = execute_graph(
            user_query=user_query,
            job_id=workflow_id,
            uploaded_pdb_path=uploaded_pdb_path,
            uploaded_pdb_content=uploaded_pdb_content,
            session_data=session_data
        )

        # Update checkpoint with final state
        checkpoint.current_node = result.get('current_node', 'response_formatter')
        checkpoint.node_history = result.get('node_history', [])
        checkpoint.checkpoint_data = dict(result)
        checkpoint.save(update_fields=[
            'current_node', 'node_history', 'checkpoint_data', 'updated_at'
        ])

        # Update message with results
        with transaction.atomic():
            message.update_from_workflow(result)

            # Update conversation context
            conversation = Conversation.objects.get(id=conversation_id)
            conversation.update_context(
                last_sequence=result.get('protein', {}).get('sequence'),
                uniprot_id=result.get('protein', {}).get('uniprot_id'),
                last_workflow_id=workflow_id
            )

            # Mark checkpoint completed
            checkpoint.mark_completed()

        report("✅ Workflow completed successfully")
        logger.info(f"Workflow {workflow_id} completed successfully")

    except Exception as e:
        report(f"❌ Workflow failed: {str(e)}")
        logger.exception(f"Workflow {workflow_id} failed: {e}")

        # Update checkpoint with error
        try:
            checkpoint = WorkflowCheckpoint.objects.get(job_id=workflow_id)
            checkpoint.mark_failed(str(e))

            message = Message.objects.get(id=message_id)
            message.workflow_status = 'failed'
            message.content = f"An error occurred: {str(e)}"
            message.save(update_fields=['workflow_status', 'content', 'updated_at'])

        except Exception as update_error:
            logger.exception(f"Failed to update error state: {update_error}")

        # Retry on transient errors
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=5 * (self.request.retries + 1))

        raise


@shared_task
def cleanup_expired_checkpoints(days: int = 7):
    """
    Clean up old workflow checkpoints.

    Args:
        days: Delete checkpoints older than this many days
    """
    from datetime import timedelta
    from django.utils import timezone
    from synde_web.models import WorkflowCheckpoint

    cutoff = timezone.now() - timedelta(days=days)

    # Delete completed/failed checkpoints older than cutoff
    deleted, _ = WorkflowCheckpoint.objects.filter(
        status__in=['completed', 'failed', 'expired'],
        updated_at__lt=cutoff
    ).delete()

    logger.info(f"Deleted {deleted} expired workflow checkpoints")

    # Mark stale active checkpoints as expired
    stale_cutoff = timezone.now() - timedelta(hours=2)
    expired = WorkflowCheckpoint.objects.filter(
        status='active',
        updated_at__lt=stale_cutoff
    ).update(status='expired')

    logger.info(f"Marked {expired} stale checkpoints as expired")
