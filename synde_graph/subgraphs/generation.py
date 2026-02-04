"""
Generation Subgraph for SynDe LangGraph workflow.

Handles the generation workflow:
1. Prepare wild-type metrics
2. Run ProGen2 mutation generation
3. Validate mutants with CLEAN
4. Run ZymCTRL EC-conditioned generation
5. Evaluate all mutants
6. Sort and rank mutants
"""

from typing import Dict, Any

from langgraph.graph import StateGraph, END

from synde_graph.state.schema import SynDeGraphState
from synde_graph.nodes.generation import (
    prepare_wt_metrics_node,
    run_progen2_node,
    run_zymctrl_node,
    validate_mutants_node,
    evaluate_mutants_node,
    sort_mutants_node,
    end_generation_node,
)
from synde_graph.routing.routes import (
    route_after_progen2,
    route_after_validation,
    route_after_zymctrl,
    route_after_evaluation,
)


def create_generation_subgraph() -> StateGraph:
    """
    Create the generation subgraph.

    Graph structure:
        prepare_wt_metrics
               |
               v
         run_progen2
               |
               v
        validate_mutants
               |
        +------+------+
        |             |
        v             v
    run_zymctrl  evaluate_mutants
        |             |
        +------+------+
               |
               v
        evaluate_mutants
               |
               v
         sort_mutants
               |
               v
        end_generation

    Returns:
        Configured StateGraph for generation workflow
    """
    graph = StateGraph(SynDeGraphState)

    # Add nodes
    graph.add_node("prepare_wt_metrics", prepare_wt_metrics_node)
    graph.add_node("run_progen2", run_progen2_node)
    graph.add_node("validate_mutants", validate_mutants_node)
    graph.add_node("run_zymctrl", run_zymctrl_node)
    graph.add_node("evaluate_mutants", evaluate_mutants_node)
    graph.add_node("sort_mutants", sort_mutants_node)
    graph.add_node("end_generation", end_generation_node)

    # Set entry point
    graph.set_entry_point("prepare_wt_metrics")

    # Linear flow from prepare to progen2
    graph.add_edge("prepare_wt_metrics", "run_progen2")

    # Progen2 routes based on results
    graph.add_conditional_edges(
        "run_progen2",
        route_after_progen2,
        {
            "validate_mutants": "validate_mutants",
            "end_generation": "end_generation",
        }
    )

    # Validation routes to zymctrl or evaluate
    graph.add_conditional_edges(
        "validate_mutants",
        route_after_validation,
        {
            "run_zymctrl": "run_zymctrl",
            "evaluate_mutants": "evaluate_mutants",
        }
    )

    # ZymCTRL always goes to evaluate
    graph.add_edge("run_zymctrl", "evaluate_mutants")

    # Evaluation routes to sort or end
    graph.add_conditional_edges(
        "evaluate_mutants",
        route_after_evaluation,
        {
            "sort_mutants": "sort_mutants",
            "end_generation": "end_generation",
        }
    )

    # Sort is final step
    graph.add_edge("sort_mutants", "end_generation")

    # Set finish point
    graph.set_finish_point("end_generation")

    return graph


def create_simple_generation_graph() -> StateGraph:
    """
    Create a simplified generation graph for testing.

    This version runs all steps sequentially without complex routing.
    """
    graph = StateGraph(SynDeGraphState)

    # Add nodes
    graph.add_node("prepare_wt_metrics", prepare_wt_metrics_node)
    graph.add_node("run_generation", run_full_generation_node)
    graph.add_node("end_generation", end_generation_node)

    # Linear flow
    graph.set_entry_point("prepare_wt_metrics")
    graph.add_edge("prepare_wt_metrics", "run_generation")
    graph.add_edge("run_generation", "end_generation")
    graph.set_finish_point("end_generation")

    return graph


def run_full_generation_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run the complete generation pipeline in a single node.

    This is a simplified approach that runs all generation steps sequentially.
    """
    updates = {}
    current_state = state.copy()

    # Run ProGen2
    result = run_progen2_node(current_state)
    updates = {**updates, **result}
    current_state = {**current_state, **result}

    # Check if we have mutants
    session_data = current_state.get("session_data", {})
    if not session_data.get("progen2_mutants"):
        updates["current_node"] = "run_generation"
        updates["node_history"] = state.get("node_history", []) + ["run_generation"]
        return updates

    # Validate mutants
    result = validate_mutants_node(current_state)
    updates = {**updates, **result}
    current_state = {**current_state, **result}

    # Run ZymCTRL if EC available
    session_data = current_state.get("session_data", {})
    if session_data.get("wt_ec_number"):
        try:
            result = run_zymctrl_node(current_state)
            updates = {**updates, **result}
            current_state = {**current_state, **result}
        except Exception:
            pass

    # Evaluate mutants
    result = evaluate_mutants_node(current_state)
    updates = {**updates, **result}
    current_state = {**current_state, **result}

    # Sort mutants
    session_data = current_state.get("session_data", {})
    if session_data.get("all_validated_mutants"):
        result = sort_mutants_node(current_state)
        updates = {**updates, **result}

    updates["current_node"] = "run_generation"
    updates["node_history"] = state.get("node_history", []) + ["run_generation"]

    return updates
