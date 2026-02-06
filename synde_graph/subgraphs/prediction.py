"""
Prediction Subgraph for SynDe LangGraph workflow.

Handles the prediction workflow:
1. Check/predict structure (ESMFold or AlphaFold)
2. Run Fpocket for pocket detection
3. Run property predictions based on requested properties
4. Aggregate results
"""

from typing import Dict, Any

from langgraph.graph import StateGraph, END

from synde_graph.state.schema import SynDeGraphState
from synde_graph.utils.live_logger import report, report_node_start, report_node_complete
from synde_graph.nodes.prediction import (
    check_structure_node,
    run_esmfold_node,
    run_alphafold_node,
    run_fpocket_node,
    run_foldx_node,
    run_tomer_node,
    run_clean_ec_node,
    run_deepenzyme_node,
    run_temberture_node,
    aggregate_prediction_results_node,
)
from synde_graph.routing.routes import (
    route_structure_prediction,
    get_property_nodes,
    needs_structure,
)


def create_prediction_subgraph() -> StateGraph:
    """
    Create the prediction subgraph.

    Graph structure:
        check_structure
            |-- run_esmfold (if sequence <= 400 AA)
            |-- run_alphafold (if sequence > 400 AA)
            |-- run_fpocket (if structure exists)
                    |
                    v
            property_dispatch
                    |
        +-----------+-----------+-----------+
        v           v           v           v
    run_foldx  run_tomer  run_clean_ec  run_temberture
        |           |           |           |
        +-----------+-----------+-----------+
                    |
                    v
        aggregate_prediction_results
                    |
                    v
                   END

    Returns:
        Configured StateGraph for prediction workflow
    """
    graph = StateGraph(SynDeGraphState)

    # Add nodes
    graph.add_node("check_structure", check_structure_node)
    graph.add_node("run_esmfold", run_esmfold_node)
    graph.add_node("run_alphafold", run_alphafold_node)
    graph.add_node("run_fpocket", run_fpocket_node)
    graph.add_node("property_dispatch", property_dispatch_node)
    graph.add_node("run_foldx", run_foldx_node)
    graph.add_node("run_tomer", run_tomer_node)
    graph.add_node("run_clean_ec", run_clean_ec_node)
    graph.add_node("run_deepenzyme", run_deepenzyme_node)
    graph.add_node("run_temberture", run_temberture_node)
    graph.add_node("aggregate_results", aggregate_prediction_results_node)

    # Set entry point
    graph.set_entry_point("check_structure")

    # Add edges from check_structure
    graph.add_conditional_edges(
        "check_structure",
        route_structure_prediction,
        {
            "run_esmfold": "run_esmfold",
            "run_alphafold": "run_alphafold",
            "run_fpocket": "run_fpocket",
        }
    )

    # Structure prediction flows to fpocket
    graph.add_edge("run_esmfold", "run_fpocket")
    graph.add_edge("run_alphafold", "run_fpocket")

    # Fpocket to property dispatch
    graph.add_edge("run_fpocket", "property_dispatch")

    # Property dispatch routes to property nodes
    graph.add_conditional_edges(
        "property_dispatch",
        route_property_nodes,
        {
            "run_foldx": "run_foldx",
            "run_tomer": "run_tomer",
            "run_clean_ec": "run_clean_ec",
            "run_deepenzyme": "run_deepenzyme",
            "run_temberture": "run_temberture",
            "aggregate": "aggregate_results",
        }
    )

    # All property nodes flow to aggregate (or next property)
    for prop_node in ["run_foldx", "run_tomer", "run_clean_ec", "run_deepenzyme", "run_temberture"]:
        graph.add_conditional_edges(
            prop_node,
            route_next_property,
            {
                "run_foldx": "run_foldx",
                "run_tomer": "run_tomer",
                "run_clean_ec": "run_clean_ec",
                "run_deepenzyme": "run_deepenzyme",
                "run_temberture": "run_temberture",
                "aggregate": "aggregate_results",
            }
        )

    # Set finish point
    graph.set_finish_point("aggregate_results")

    return graph


def property_dispatch_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Initialize property prediction dispatch.

    Sets up the list of property nodes to run based on requested properties.
    """
    property_nodes = get_property_nodes(state)

    session_data = state.get("session_data", {})
    session_data["pending_property_nodes"] = property_nodes
    session_data["completed_property_nodes"] = []

    return {
        "session_data": session_data,
        "current_node": "property_dispatch",
        "node_history": state.get("node_history", []) + ["property_dispatch"],
    }


def route_property_nodes(state: SynDeGraphState) -> str:
    """
    Route to the first property node.

    Returns:
        First property node name or 'aggregate' if none
    """
    session_data = state.get("session_data", {})
    pending = session_data.get("pending_property_nodes", [])

    if pending:
        return pending[0]
    return "aggregate"


def route_next_property(state: SynDeGraphState) -> str:
    """
    Route to the next property node after completing one.

    Returns:
        Next property node name or 'aggregate' if done
    """
    session_data = state.get("session_data", {})
    pending = list(session_data.get("pending_property_nodes", []))
    completed = list(session_data.get("completed_property_nodes", []))
    current = state.get("current_node", "")

    # Move current from pending to completed
    if current in pending:
        pending.remove(current)
        completed.append(current)

    # Return next or aggregate
    if pending:
        return pending[0]
    return "aggregate"


def create_simple_prediction_graph() -> StateGraph:
    """
    Create a simplified prediction graph for testing.

    This version runs properties sequentially in a single node.
    """
    graph = StateGraph(SynDeGraphState)

    # Core nodes only
    graph.add_node("check_structure", check_structure_node)
    graph.add_node("run_esmfold", run_esmfold_node)
    graph.add_node("run_fpocket", run_fpocket_node)
    graph.add_node("run_predictions", run_all_predictions_node)
    graph.add_node("aggregate_results", aggregate_prediction_results_node)

    # Linear flow for simplicity
    graph.set_entry_point("check_structure")

    graph.add_conditional_edges(
        "check_structure",
        lambda s: "run_esmfold" if needs_structure(s) else "run_fpocket",
        {
            "run_esmfold": "run_esmfold",
            "run_fpocket": "run_fpocket",
        }
    )

    graph.add_edge("run_esmfold", "run_fpocket")
    graph.add_edge("run_fpocket", "run_predictions")
    graph.add_edge("run_predictions", "aggregate_results")

    graph.set_finish_point("aggregate_results")

    return graph


def run_all_predictions_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run all requested property predictions sequentially.

    This is a simplified approach that runs all properties in one node.
    """
    import logging
    logger = logging.getLogger(__name__)

    parsed_input = state.get("parsed_input", {})
    properties = parsed_input.get("properties", [])

    logger.info(f"run_all_predictions_node: properties={properties}")
    report_node_start("Property Predictions", f"Running {', '.join(properties)}")

    updates = {}
    current_state = state.copy()

    # Track which predictions ran and their results
    predictions_run = []
    predictions_results = {}

    for prop in properties:
        prop_lower = prop.lower()
        logger.info(f"Processing property: {prop_lower}")

        try:
            if prop_lower in ["stability", "mutation_effect"]:
                logger.info("Running FoldX for stability")
                result = run_foldx_node(current_state)
                updates = {**updates, **result}
                current_state = {**current_state, **result}
                predictions_run.append("stability")

            elif prop_lower in ["optimum_temperature", "topt"]:
                logger.info("Running Tomer for topt")
                result = run_tomer_node(current_state)
                updates = {**updates, **result}
                current_state = {**current_state, **result}
                predictions_run.append("topt")

            elif prop_lower in ["ec_number", "ec"]:
                logger.info("Running CLEAN for EC number")
                result = run_clean_ec_node(current_state)
                logger.info(f"CLEAN EC result: {result}")
                updates = {**updates, **result}
                current_state = {**current_state, **result}
                predictions_run.append("ec_number")
                # Store EC result for predictions dict
                if result.get("response"):
                    predictions_results["ec_number"] = result.get("response", {})

            elif prop_lower in ["kcat", "km"]:
                logger.info("Running DeepEnzyme for kcat")
                # Check if ligand_smiles is available before calling
                ligand = current_state.get("ligand", {})
                if not ligand.get("ligand_smiles"):
                    logger.warning("DeepEnzyme requires ligand_smiles - will report missing requirement")
                result = run_deepenzyme_node(current_state)
                logger.info(f"DeepEnzyme result: {result}")
                updates = {**updates, **result}
                current_state = {**current_state, **result}
                predictions_run.append("kcat")

            elif prop_lower in ["tm", "melting_temperature"]:
                logger.info("Running TemBERTure for Tm")
                result = run_temberture_node(current_state)
                logger.info(f"TemBERTure result: {result}")
                updates = {**updates, **result}
                current_state = {**current_state, **result}
                predictions_run.append("tm")

        except Exception as e:
            logger.error(f"Error running prediction for {prop_lower}: {e}", exc_info=True)
            # Don't silently pass - add to errors
            errors = list(current_state.get("errors", []))
            errors.append({
                "node": "run_predictions",
                "error_type": type(e).__name__,
                "message": f"Failed to run {prop_lower} prediction: {str(e)}",
                "recoverable": True,
            })
            updates["errors"] = errors

    logger.info(f"Predictions completed: {predictions_run}")
    logger.info(f"Final response in updates: {updates.get('response', {})}")
    report_node_complete("Property Predictions", f"Completed: {', '.join(predictions_run)}")

    updates["current_node"] = "run_predictions"
    updates["node_history"] = state.get("node_history", []) + ["run_predictions"]

    return updates
