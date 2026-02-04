"""
SynDe LangGraph - Core graph workflow engine for protein engineering.

This package provides the LangGraph-based workflow system for:
- Intent detection and input parsing
- Structure prediction (ESMFold, AlphaFold)
- Property prediction (EC number, kcat, Tm, stability)
- Sequence generation (ProGen2, ZymCTRL)
"""

from synde_graph.graph import create_synde_graph, run_workflow
from synde_graph.state.schema import SynDeGraphState
from synde_graph.state.factory import create_initial_state

__version__ = "0.1.0"

__all__ = [
    "create_synde_graph",
    "run_workflow",
    "SynDeGraphState",
    "create_initial_state",
]
