"""
Task proxies for GPU tasks defined in synde-minimal.

These proxies call the actual Celery tasks running on the GPU worker,
providing a clean interface for the LangGraph workflow.
"""

from typing import Any, Optional
from celery import signature, Celery

from synde_graph.config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from synde_gpu.mocks import is_mock_mode, get_mock_response


# Create Celery app for task signatures
# This connects to the same broker as synde-minimal
celery_app = Celery(
    "synde_langgraph",
    broker=CELERY_BROKER_URL,
    backend=CELERY_RESULT_BACKEND,
)

# Configure Celery
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
)


# =============================================================================
# Task Signatures (pointing to synde-minimal tasks)
# =============================================================================

# These signatures reference tasks defined in synde-minimal/home/tasks_gpu.py
_esmfold_task = signature("home.tasks.run_esmfold_job", queue="gpu")
_clean_ec_task = signature("home.tasks.run_clean_ec_job", queue="gpu")
_deepenzyme_task = signature("home.tasks.run_deepenzyme_kcat_job", queue="gpu")
_temberture_task = signature("home.tasks.run_temperture_job", queue="gpu")
_flan_extractor_task = signature("home.tasks.run_flan_extractor", queue="gpu")
_fpocket_task = signature("home.tasks.run_fpocket_job", queue="gpu")


# =============================================================================
# Task Proxy Functions
# =============================================================================

def call_esmfold(job_id: str, sequence: str) -> Any:
    """
    Call ESMFold structure prediction task.

    Args:
        job_id: Unique job identifier
        sequence: Protein sequence (amino acids)

    Returns:
        AsyncResult if real mode, mock response if mock mode
    """
    if is_mock_mode():
        return get_mock_response("esmfold", job_id, sequence)

    return _esmfold_task.delay(job_id, sequence)


def call_clean_ec(sequence: str, seq_name: str = "Input_Seq") -> Any:
    """
    Call CLEAN EC number prediction task.

    Args:
        sequence: Protein sequence
        seq_name: Optional sequence name

    Returns:
        AsyncResult if real mode, mock response if mock mode
    """
    if is_mock_mode():
        return get_mock_response("clean_ec", sequence, seq_name)

    return _clean_ec_task.delay(sequence, seq_name)


def call_deepenzyme(sequence: str, pdb_file_path: str, smiles: str) -> Any:
    """
    Call DeepEnzyme kcat prediction task.

    Args:
        sequence: Protein sequence
        pdb_file_path: Path to PDB structure file
        smiles: Ligand SMILES string

    Returns:
        AsyncResult if real mode, mock response if mock mode
    """
    if is_mock_mode():
        return get_mock_response("deepenzyme", sequence, pdb_file_path, smiles)

    return _deepenzyme_task.delay(sequence, pdb_file_path, smiles)


def call_temberture(sequence: str) -> Any:
    """
    Call TemBERTure melting temperature prediction task.

    Args:
        sequence: Protein sequence

    Returns:
        AsyncResult if real mode, mock response if mock mode
    """
    if is_mock_mode():
        return get_mock_response("temberture", sequence)

    return _temberture_task.delay(sequence)


def call_flan_extractor(query: str) -> Any:
    """
    Call FLAN NLP extraction task.

    Args:
        query: User query text

    Returns:
        AsyncResult if real mode, mock response if mock mode
    """
    if is_mock_mode():
        return get_mock_response("flan_extractor", query)

    return _flan_extractor_task.delay(query)


def call_fpocket(
    pdb_file_path: str,
    pdb_data: Optional[str] = None,
    output_dir: str = "synde_outputs/fpocket_results",
    num_pockets: int = 5,
) -> Any:
    """
    Call Fpocket binding pocket detection task.

    Args:
        pdb_file_path: Path to PDB file
        pdb_data: Optional PDB file content
        output_dir: Output directory for results
        num_pockets: Number of top pockets to return

    Returns:
        AsyncResult if real mode, mock response if mock mode
    """
    if is_mock_mode():
        return get_mock_response("fpocket", pdb_file_path, output_dir, num_pockets)

    return _fpocket_task.delay(pdb_file_path, pdb_data, output_dir, num_pockets)


# =============================================================================
# Task Routing Configuration
# =============================================================================

TASK_ROUTES = {
    # GPU tasks defined in synde-minimal
    "home.tasks.run_esmfold_job": {"queue": "gpu"},
    "home.tasks.run_clean_ec_job": {"queue": "gpu"},
    "home.tasks.run_deepenzyme_kcat_job": {"queue": "gpu"},
    "home.tasks.run_temperture_job": {"queue": "gpu"},
    "home.tasks.run_flan_extractor": {"queue": "gpu"},
    "home.tasks.run_fpocket_job": {"queue": "gpu"},

    # Workflow task (runs on CPU)
    "synde_langgraph.tasks.run_workflow": {"queue": "default"},
}
