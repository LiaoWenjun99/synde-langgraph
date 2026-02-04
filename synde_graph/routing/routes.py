"""
Routing functions for LangGraph conditional edges.

These functions determine the next node based on the current state,
implementing the workflow's branching logic.
"""

from typing import List

from synde_graph.state.schema import SynDeGraphState
from synde_graph.config import SequenceLimits


# =============================================================================
# Route Maps
# =============================================================================

INTENT_ROUTES = {
    "mutagenesis": "mutagenesis_subgraph",
    "plasmid": "plasmid_subgraph",
    "database-search": "oed_subgraph",
    "protocol": "protocol_subgraph",
    "generation": "generation_subgraph",
    "prediction": "prediction_subgraph",
    "theory": "theory_response",
    "none": "fallback_response",
}

PROPERTY_NODE_MAP = {
    "stability": "run_foldx",
    "mutation_effect": "run_foldx",
    "optimum_temperature": "run_tomer",
    "topt": "run_tomer",
    "temperature": "run_tomer",
    "ec_number": "run_clean_ec",
    "kcat": "run_deepenzyme",
    "km": "run_deepenzyme",
    "tm": "run_temberture",
    "melting_temperature": "run_temberture",
    "thermophilicity": "run_temberture",
    "docking": "run_docking",
}


# =============================================================================
# Intent-Based Routing
# =============================================================================

def route_by_intent(state: SynDeGraphState) -> str:
    """
    Route based on detected intent after input parsing.

    Returns:
        Next node name based on intent type
    """
    intent = state.get("intent", {})
    intent_type = intent.get("intent", "none")
    parsed_input = state.get("parsed_input", {})
    task = parsed_input.get("task", "")

    # Handle "none" intent specially - check for protein data first
    if intent_type == "none":
        protein = state.get("protein", {})
        if protein.get("sequence"):
            return "prediction_subgraph"
        return "fallback_response"

    # Check intent routes
    if intent_type in INTENT_ROUTES:
        # Override for generation task
        if intent_type == "prediction" and task == "generation":
            return "generation_subgraph"
        return INTENT_ROUTES[intent_type]

    # Default to prediction if we have protein data
    protein = state.get("protein", {})
    if protein.get("sequence"):
        return "prediction_subgraph"

    return "fallback_response"


def route_by_task(state: SynDeGraphState) -> str:
    """
    Route based on parsed task type.

    Returns:
        Next node name based on task
    """
    parsed_input = state.get("parsed_input", {})
    task = parsed_input.get("task", "prediction")

    task_routes = {
        "generation": "generation_subgraph",
        "prediction": "prediction_subgraph",
        "mutagenesis": "mutagenesis_subgraph",
        "plasmid": "plasmid_subgraph",
        "database": "oed_subgraph",
        "protocol": "protocol_subgraph",
    }

    return task_routes.get(task, "prediction_subgraph")


# =============================================================================
# Structure Prediction Routing
# =============================================================================

def route_structure_prediction(state: SynDeGraphState) -> str:
    """
    Route structure prediction based on sequence length.

    Returns:
        'run_esmfold' for sequences <= 400 AA
        'run_alphafold' for sequences > 400 AA
        'run_fpocket' if structure already exists
    """
    protein = state.get("protein", {})
    pdb_file_path = protein.get("pdb_file_path")
    sequence_length = protein.get("sequence_length", 0)

    # Skip if structure already available
    if pdb_file_path:
        return "run_fpocket"

    # Route based on sequence length
    if sequence_length > SequenceLimits.ESMFOLD_MAX:
        return "run_alphafold"
    else:
        return "run_esmfold"


def needs_structure(state: SynDeGraphState) -> bool:
    """Check if structure prediction is needed."""
    protein = state.get("protein", {})
    return not protein.get("pdb_file_path")


# =============================================================================
# Property Prediction Routing
# =============================================================================

def get_property_nodes(state: SynDeGraphState) -> List[str]:
    """
    Get list of property prediction nodes to run.

    Returns:
        List of node names for the requested properties
    """
    parsed_input = state.get("parsed_input", {})
    properties = parsed_input.get("properties", [])
    ligand = state.get("ligand", {})
    has_ligand = bool(ligand.get("ligand_smiles"))

    nodes = []
    for prop in properties:
        prop_lower = prop.lower()

        if prop_lower in ["stability", "mutation_effect"]:
            nodes.append("run_foldx")
        elif prop_lower in ["optimum_temperature", "topt", "temperature"]:
            nodes.append("run_tomer")
        elif prop_lower in ["confidence_score", "plddt", "pld"]:
            # pLDDT already computed during structure prediction
            pass
        elif prop_lower in ["ec_number"]:
            nodes.append("run_clean_ec")
        elif prop_lower in ["kcat", "km"]:
            if has_ligand:
                nodes.append("run_deepenzyme")
        elif prop_lower in ["tm", "melting_temperature", "thermophilicity"]:
            nodes.append("run_temberture")
        elif prop_lower in ["docking"]:
            if has_ligand:
                nodes.append("run_docking")
        elif prop_lower in ["pocket", "binding_site", "pockets", "active_site"]:
            # Fpocket already runs in prediction flow
            pass

    # Remove duplicates while preserving order
    seen = set()
    unique_nodes = []
    for node in nodes:
        if node not in seen:
            seen.add(node)
            unique_nodes.append(node)

    return unique_nodes


def route_property_prediction(state: SynDeGraphState) -> str:
    """
    Route to appropriate property prediction nodes.

    This is used for sequential property prediction routing.
    """
    session_data = state.get("session_data", {})
    pending_properties = session_data.get("pending_property_nodes", [])

    if not pending_properties:
        return "aggregate_prediction_results"

    return pending_properties[0]


def should_run_property(state: SynDeGraphState, prop: str) -> bool:
    """
    Check if a specific property should be run.

    Args:
        state: Current workflow state
        prop: Property name to check

    Returns:
        True if the property is in the requested list
    """
    parsed_input = state.get("parsed_input", {})
    properties = parsed_input.get("properties", [])
    return any(p.lower() == prop.lower() for p in properties)


# =============================================================================
# Generation Flow Routing
# =============================================================================

def route_after_progen2(state: SynDeGraphState) -> str:
    """
    Route after ProGen2 generation.

    Returns:
        'validate_mutants' if mutants were generated
        'end_generation' otherwise
    """
    session_data = state.get("session_data", {})
    progen2_mutants = session_data.get("progen2_mutants", [])

    if progen2_mutants:
        return "validate_mutants"
    return "end_generation"


def route_after_validation(state: SynDeGraphState) -> str:
    """
    Route after mutant validation.

    Returns:
        'run_zymctrl' if EC number available
        'evaluate_mutants' otherwise
    """
    session_data = state.get("session_data", {})
    wt_ec = session_data.get("wt_ec_number")

    if wt_ec:
        return "run_zymctrl"
    return "evaluate_mutants"


def route_after_zymctrl(state: SynDeGraphState) -> str:
    """
    Route after ZymCTRL generation.

    Always goes to evaluate_mutants.
    """
    return "evaluate_mutants"


def route_after_evaluation(state: SynDeGraphState) -> str:
    """
    Route after mutant evaluation.

    Returns:
        'sort_mutants' if validated mutants exist
        'end_generation' otherwise
    """
    session_data = state.get("session_data", {})
    all_validated = session_data.get("all_validated_mutants", [])

    if all_validated:
        return "sort_mutants"
    return "end_generation"


# =============================================================================
# Error Handling Routes
# =============================================================================

def has_fatal_error(state: SynDeGraphState) -> bool:
    """
    Check if state contains a non-recoverable error.

    Returns:
        True if workflow should abort
    """
    errors = state.get("errors", [])
    for error in errors:
        if not error.get("recoverable", True):
            return True
    return False


def route_on_error(state: SynDeGraphState) -> str:
    """
    Route when an error is detected.

    Returns:
        'error_response' for fatal errors
        Current node otherwise
    """
    if has_fatal_error(state):
        return "error_response"
    return state.get("current_node", "end")


# =============================================================================
# Subgraph Exit Routes
# =============================================================================

def route_exit_prediction(state: SynDeGraphState) -> str:
    """Route after prediction subgraph completion."""
    return "response_formatter"


def route_exit_generation(state: SynDeGraphState) -> str:
    """Route after generation subgraph completion."""
    return "response_formatter"


def route_exit_mutagenesis(state: SynDeGraphState) -> str:
    """Route after mutagenesis subgraph completion."""
    return "response_formatter"


# =============================================================================
# Conditional Edge Helpers
# =============================================================================

def make_property_router(property_name: str):
    """
    Factory for property-specific routers.

    Args:
        property_name: Name of the property to check

    Returns:
        Router function
    """
    def router(state: SynDeGraphState) -> bool:
        return should_run_property(state, property_name)

    return router


def make_sequence_conditional(min_length: int = 0, max_length: int = float('inf')):
    """
    Factory for sequence length conditionals.

    Args:
        min_length: Minimum sequence length
        max_length: Maximum sequence length

    Returns:
        Conditional function
    """
    def conditional(state: SynDeGraphState) -> bool:
        protein = state.get("protein", {})
        length = protein.get("sequence_length", 0)
        return min_length <= length <= max_length

    return conditional
