"""
State management for SynDe LangGraph workflow.

Provides TypedDict state schemas and factory functions for creating
and managing workflow state.
"""

from synde_graph.state.schema import (
    SynDeGraphState,
    IntentResult,
    ParsedInput,
    ProteinData,
    LigandData,
    StructureAnalysis,
    PocketInfo,
    MutantData,
    MutantInfo,
    GpuTaskStatus,
    WorkflowError,
    ResponseData,
)

from synde_graph.state.factory import (
    create_initial_state,
    add_error,
    update_node_history,
    update_gpu_task,
)

__all__ = [
    # Schema classes
    "SynDeGraphState",
    "IntentResult",
    "ParsedInput",
    "ProteinData",
    "LigandData",
    "StructureAnalysis",
    "PocketInfo",
    "MutantData",
    "MutantInfo",
    "GpuTaskStatus",
    "WorkflowError",
    "ResponseData",
    # Factory functions
    "create_initial_state",
    "add_error",
    "update_node_history",
    "update_gpu_task",
]
