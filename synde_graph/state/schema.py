"""
State schema definitions for SynDe LangGraph workflow.

This module defines all TypedDict state classes used throughout the
LangGraph workflow, providing type safety and clear data contracts
between nodes.
"""

from typing import TypedDict, Optional, List, Dict, Any, Literal


# =============================================================================
# Intent Detection State
# =============================================================================

class IntentResult(TypedDict, total=False):
    """Result from intent detection node."""
    intent: Literal[
        "mutagenesis", "plasmid", "prediction", "generation",
        "protocol", "database-search", "theory", "none"
    ]
    confidence: float
    mutations: List[str]  # e.g., ["P148T", "G45A"]
    uniprot_id: Optional[str]
    reason: str  # Explanation for classification


# =============================================================================
# Input Parsing State
# =============================================================================

class ParsedInput(TypedDict, total=False):
    """Result from input parsing node."""
    task: Literal["prediction", "generation", "mutagenesis", "plasmid", "protocol", "database", "unknown"]
    properties: List[str]  # e.g., ["stability", "kcat", "ec_number"]
    region: List[Dict[str, int]]  # e.g., [{"start": 50, "end": 100}]
    organism: List[str]
    raw_ligand_input: Optional[str]  # Original ligand name before SMILES conversion


# =============================================================================
# Protein Data State
# =============================================================================

class ProteinData(TypedDict, total=False):
    """Protein sequence and structure data."""
    sequence: Optional[str]  # Amino acid sequence
    sequence_length: int
    uniprot_id: Optional[str]
    uniprot_metadata: Dict[str, Any]  # Full UniProt response data
    pdb_data: Optional[str]  # Raw PDB file content
    pdb_file_path: Optional[str]  # Path to PDB file on disk
    structure_source: Literal["uploaded", "uniprot", "esmfold", "alphafold", "session", "none"]
    avg_plddt: Optional[float]  # Structure confidence score
    ptm_score: Optional[float]  # AlphaFold PTM score


# =============================================================================
# Ligand Data State
# =============================================================================

class LigandData(TypedDict, total=False):
    """Ligand information."""
    ligand_input: Optional[str]  # Original input (name or SMILES)
    ligand_smiles: Optional[str]  # Resolved SMILES string
    ligand_sdf_path: Optional[str]  # Path to SDF file if generated


# =============================================================================
# Structure Analysis State
# =============================================================================

class PocketInfo(TypedDict, total=False):
    """Single pocket analysis result."""
    pocket_id: int
    score: float
    residues: List[str]  # e.g., ["A:45", "A:46", "A:50"]


class StructureAnalysis(TypedDict, total=False):
    """Structure analysis results from fpocket, docking, etc."""
    pocket_residues: Dict[int, List[str]]  # pocket_id -> residue list
    pocket_scores: List[Dict[str, Any]]  # Fpocket score DataFrame records
    pockets: List[PocketInfo]  # Structured pocket info
    docked_pdb: Optional[str]  # Docked structure PDB content
    docked_pdb_path: Optional[str]  # Path to docked PDB
    docking_affinities: List[float]  # kcal/mol values


# =============================================================================
# Mutant Data State
# =============================================================================

class MutantInfo(TypedDict, total=False):
    """Single mutant evaluation result."""
    mutant_sequence: str
    mutations: List[str]  # e.g., ["P148T", "G45A"]
    mutation_positions: List[int]
    pdb_file_path: Optional[str]
    source: Literal["progen2", "zymctrl", "manual"]

    # Property predictions
    stability: Optional[float]  # DDG
    kcat: Optional[float]
    ec_number: Optional[str]
    ec_probability: Optional[float]
    topt: Optional[float]  # Optimal temperature
    tm: Optional[float]  # Melting temperature
    plddt: Optional[float]  # Structure confidence

    # Comparison metrics
    stability_improvement: Optional[float]
    kcat_improvement: Optional[float]


class MutantData(TypedDict, total=False):
    """Mutant generation and evaluation results."""
    wild_type_sequence: str
    wild_type_metrics: Dict[str, Any]  # WT property values for comparison
    mutant_sequence: Optional[str]  # Best mutant
    mutations: List[str]
    validated_mutants: List[MutantInfo]
    best_mutant: Optional[MutantInfo]
    mutant_pdb_path: Optional[str]
    mutant_pocket_residues: Dict[int, List[str]]
    mutant_pocket_scores: List[Dict[str, Any]]


# =============================================================================
# GPU Task Tracking State
# =============================================================================

class GpuTaskStatus(TypedDict, total=False):
    """Status of a GPU Celery task for checkpointing."""
    task_id: str
    task_name: str  # e.g., "run_esmfold_job", "run_clean_ec_job"
    status: Literal["pending", "started", "success", "failure", "revoked", "timeout"]
    submitted_at: str  # ISO format timestamp
    completed_at: Optional[str]
    result: Optional[Any]
    error: Optional[str]


# =============================================================================
# Workflow Error State
# =============================================================================

class WorkflowError(TypedDict, total=False):
    """Error information for workflow debugging."""
    node: str  # Node where error occurred
    error_type: str  # Exception class name
    message: str
    traceback: Optional[str]
    timestamp: str  # ISO format
    recoverable: bool  # Whether workflow can continue


# =============================================================================
# Response State
# =============================================================================

class ResponseData(TypedDict, total=False):
    """Final response data for the user."""
    response_html: str  # Main HTML response content
    natural_reply: str  # Natural language summary
    experimental_plan: Optional[str]  # Generated experimental plan

    # Visualization data
    wild_type_pdb: Optional[str]  # PDB content
    mutant_pdb: Optional[str]  # Aligned mutant PDB content
    docked_pdb: Optional[str]  # Docked structure PDB content

    # Structured data
    pocket_residues: Dict[int, List[str]]
    pocket_scores: List[Dict[str, Any]]
    pocket_residues_mut: Dict[int, List[str]]
    pocket_scores_mut: List[Dict[str, Any]]

    # Metadata
    uniprot_table: Optional[Dict[str, Any]]
    validated_mutants: List[MutantInfo]

    # Downloads
    idt_template_path: Optional[str]  # For mutagenesis
    genbank_path: Optional[str]  # For plasmid design
    plasmid_map_path: Optional[str]  # PNG map


# =============================================================================
# Main Graph State
# =============================================================================

class SynDeGraphState(TypedDict, total=False):
    """
    Main state schema for the SynDe LangGraph workflow.

    This aggregates all sub-states and provides the complete workflow context
    that flows between nodes.
    """
    # -------------------------
    # Workflow Metadata
    # -------------------------
    job_id: str  # Unique workflow identifier
    user_id: Optional[int]  # User ID (None for anonymous)
    thread_id: str  # LangGraph thread ID for checkpointing

    # -------------------------
    # User Input
    # -------------------------
    user_query: str  # Original user query text
    uploaded_pdb_path: Optional[str]  # Path to uploaded PDB file
    uploaded_pdb_content: Optional[str]  # PDB file content

    # -------------------------
    # Intent and Parsing Results
    # -------------------------
    intent: IntentResult
    parsed_input: ParsedInput

    # -------------------------
    # Protein and Ligand Data
    # -------------------------
    protein: ProteinData
    ligand: LigandData

    # -------------------------
    # Analysis Results
    # -------------------------
    structure: StructureAnalysis
    mutant: MutantData

    # -------------------------
    # GPU Task Tracking
    # -------------------------
    active_gpu_tasks: List[GpuTaskStatus]

    # -------------------------
    # Workflow Tracking
    # -------------------------
    current_node: str
    node_history: List[str]
    errors: List[WorkflowError]

    # -------------------------
    # Response
    # -------------------------
    response: ResponseData

    # -------------------------
    # Session Context
    # -------------------------
    session_data: Dict[str, Any]  # Carries session-like context between nodes
