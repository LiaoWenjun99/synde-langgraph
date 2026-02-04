"""
State factory functions for SynDe LangGraph workflow.

Provides helper functions for creating, updating, and managing workflow state.
"""

import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from synde_graph.state.schema import (
    SynDeGraphState,
    IntentResult,
    ParsedInput,
    ProteinData,
    LigandData,
    StructureAnalysis,
    MutantData,
    GpuTaskStatus,
    WorkflowError,
    ResponseData,
)


def create_initial_state(
    job_id: str,
    user_query: str,
    user_id: Optional[int] = None,
    uploaded_pdb_path: Optional[str] = None,
    uploaded_pdb_content: Optional[str] = None,
    session_data: Optional[Dict[str, Any]] = None,
) -> SynDeGraphState:
    """
    Create an initial state for a new workflow execution.

    Args:
        job_id: Unique identifier for this workflow run
        user_query: The user's input query
        user_id: Optional user ID
        uploaded_pdb_path: Optional path to uploaded PDB file
        uploaded_pdb_content: Optional PDB file content
        session_data: Optional session context to carry forward

    Returns:
        Initialized SynDeGraphState ready for workflow execution
    """
    return SynDeGraphState(
        # Metadata
        job_id=job_id,
        user_id=user_id,
        thread_id=job_id,  # Use job_id as thread_id for simplicity

        # User input
        user_query=user_query,
        uploaded_pdb_path=uploaded_pdb_path,
        uploaded_pdb_content=uploaded_pdb_content,

        # Intent and parsing (empty initially)
        intent=IntentResult(),
        parsed_input=ParsedInput(),

        # Protein and ligand (empty initially)
        protein=ProteinData(),
        ligand=LigandData(),

        # Analysis (empty initially)
        structure=StructureAnalysis(),
        mutant=MutantData(),

        # GPU tasks
        active_gpu_tasks=[],

        # Workflow tracking
        current_node="start",
        node_history=[],
        errors=[],

        # Response (empty initially)
        response=ResponseData(),

        # Session context
        session_data=session_data or {},
    )


def add_error(
    state: SynDeGraphState,
    node: str,
    error: Exception,
    recoverable: bool = False,
) -> Dict[str, Any]:
    """
    Add an error to the workflow state.

    Args:
        state: Current workflow state
        node: Node where error occurred
        error: The exception that was raised
        recoverable: Whether the workflow can continue

    Returns:
        State update dict with error added to errors list
    """
    error_info = WorkflowError(
        node=node,
        error_type=type(error).__name__,
        message=str(error),
        traceback=traceback.format_exc(),
        timestamp=datetime.now(timezone.utc).isoformat(),
        recoverable=recoverable,
    )

    errors = list(state.get("errors", []))
    errors.append(error_info)

    return {"errors": errors}


def update_node_history(state: SynDeGraphState, node: str) -> Dict[str, Any]:
    """
    Update the workflow's node history.

    Args:
        state: Current workflow state
        node: Node being entered

    Returns:
        State update dict with updated history
    """
    history = list(state.get("node_history", []))
    history.append(node)

    return {
        "current_node": node,
        "node_history": history,
    }


def update_gpu_task(
    state: SynDeGraphState,
    task_id: str,
    task_name: str,
    status: str,
    result: Optional[Any] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Update or add a GPU task status in the state.

    Args:
        state: Current workflow state
        task_id: Celery task ID
        task_name: Human-readable task name
        status: Task status (pending, started, success, failure, etc.)
        result: Task result if successful
        error: Error message if failed

    Returns:
        State update dict with updated active_gpu_tasks
    """
    active_tasks = list(state.get("active_gpu_tasks", []))

    # Find existing task or create new
    task_status = None
    for i, task in enumerate(active_tasks):
        if task.get("task_id") == task_id:
            task_status = active_tasks.pop(i)
            break

    if task_status is None:
        task_status = GpuTaskStatus(
            task_id=task_id,
            task_name=task_name,
            submitted_at=datetime.now(timezone.utc).isoformat(),
        )

    # Update status
    task_status["status"] = status

    if status in ("success", "failure", "revoked", "timeout"):
        task_status["completed_at"] = datetime.now(timezone.utc).isoformat()

    if result is not None:
        task_status["result"] = result

    if error is not None:
        task_status["error"] = error

    active_tasks.append(task_status)

    return {"active_gpu_tasks": active_tasks}


def merge_state_updates(*updates: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge multiple state update dicts into one.

    Handles special cases like errors and node_history which should be
    concatenated rather than replaced.

    Args:
        *updates: State update dicts to merge

    Returns:
        Merged state update dict
    """
    merged = {}

    for update in updates:
        for key, value in update.items():
            if key == "errors" and key in merged:
                # Concatenate error lists
                merged[key] = merged[key] + value
            elif key == "node_history" and key in merged:
                # Concatenate history lists
                merged[key] = merged[key] + value
            elif key == "active_gpu_tasks" and key in merged:
                # Merge by task_id
                existing = {t["task_id"]: t for t in merged[key]}
                for task in value:
                    existing[task["task_id"]] = task
                merged[key] = list(existing.values())
            elif isinstance(value, dict) and key in merged and isinstance(merged[key], dict):
                # Deep merge dicts
                merged[key] = {**merged[key], **value}
            else:
                merged[key] = value

    return merged


def get_protein_sequence(state: SynDeGraphState) -> Optional[str]:
    """Get protein sequence from state."""
    protein = state.get("protein", {})
    return protein.get("sequence")


def get_pdb_path(state: SynDeGraphState) -> Optional[str]:
    """Get PDB file path from state."""
    protein = state.get("protein", {})
    return protein.get("pdb_file_path")


def get_ligand_smiles(state: SynDeGraphState) -> Optional[str]:
    """Get ligand SMILES from state."""
    ligand = state.get("ligand", {})
    return ligand.get("ligand_smiles")


def get_requested_properties(state: SynDeGraphState) -> List[str]:
    """Get list of requested properties from parsed input."""
    parsed = state.get("parsed_input", {})
    return parsed.get("properties", [])


def has_fatal_error(state: SynDeGraphState) -> bool:
    """Check if state contains any non-recoverable errors."""
    errors = state.get("errors", [])
    return any(not e.get("recoverable", True) for e in errors)


def get_intent_type(state: SynDeGraphState) -> str:
    """Get the detected intent type."""
    intent = state.get("intent", {})
    return intent.get("intent", "none")


def get_task_type(state: SynDeGraphState) -> str:
    """Get the parsed task type."""
    parsed = state.get("parsed_input", {})
    return parsed.get("task", "prediction")
