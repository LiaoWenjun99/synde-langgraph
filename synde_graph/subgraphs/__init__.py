"""
Subgraphs for specialized workflow branches.

Provides subgraphs for:
- Prediction workflow
- Generation workflow
"""

from synde_graph.subgraphs.prediction import (
    create_prediction_subgraph,
    create_simple_prediction_graph,
)

from synde_graph.subgraphs.generation import (
    create_generation_subgraph,
    create_simple_generation_graph,
)

__all__ = [
    "create_prediction_subgraph",
    "create_simple_prediction_graph",
    "create_generation_subgraph",
    "create_simple_generation_graph",
]
