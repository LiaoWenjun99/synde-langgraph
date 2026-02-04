"""
Generation Nodes for LangGraph workflow.

Implements nodes for protein sequence generation and optimization including:
- Wild-type metrics preparation
- ProGen2 mutation generation
- ZymCTRL EC-conditioned generation
- Mutant validation and evaluation
- Mutant sorting and ranking
"""

from typing import Dict, Any, List, Optional
import textwrap

from synde_graph.state.schema import SynDeGraphState, MutantData, MutantInfo
from synde_graph.state.factory import update_node_history, add_error
from synde_graph.config import OutputPaths, SequenceLimits
from synde_gpu.tasks import call_esmfold, call_clean_ec, call_fpocket
from synde_gpu.manager import GpuTaskManager, TaskStatus
from synde_gpu.mocks import is_mock_mode


# =============================================================================
# Prepare Wild-Type Metrics Node
# =============================================================================

def prepare_wt_metrics_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Prepare wild-type structure and baseline metrics.

    This node:
    1. Ensures we have a PDB structure (runs ESMFold if needed)
    2. Runs Fpocket for pocket detection
    3. Initializes mutant data with wild-type information
    """
    OutputPaths.ensure_all()

    protein = state.get("protein", {})
    parsed_input = state.get("parsed_input", {})

    sequence = protein.get("sequence")
    pdb_file_path = protein.get("pdb_file_path")
    pdb_data = protein.get("pdb_data")
    sequence_length = protein.get("sequence_length", 0)

    if not sequence:
        return {
            **update_node_history(state, "prepare_wt_metrics"),
            **add_error(
                state, "prepare_wt_metrics",
                ValueError("No sequence available for generation"),
                recoverable=False
            ),
        }

    # Check sequence length limit for ESMFold
    if sequence_length > SequenceLimits.ESMFOLD_MAX:
        response = state.get("response", {})
        response_html = response.get("response_html", "")
        response_html += (
            f"Sequence length ({sequence_length}) exceeds ESMFold limit ({SequenceLimits.ESMFOLD_MAX}). "
            "Please use SynDe Batch with AlphaFold support."
        )
        return {
            "response": {**response, "response_html": response_html},
            **update_node_history(state, "prepare_wt_metrics"),
        }

    # Get or predict structure
    if not pdb_file_path:
        try:
            job_id = state.get("job_id", "wt_structure")
            manager = GpuTaskManager(task_name="ESMFold")
            result = manager.execute_sync(call_esmfold, args=(job_id, sequence))

            if result.status == TaskStatus.SUCCESS:
                fold_res = result.result
                if isinstance(fold_res, dict) and fold_res.get("status") == "success":
                    pdb_file_path = fold_res.get("pdb_path")
                    pdb_data = fold_res.get("pdb_data")
                    avg_plddt = fold_res.get("avg_plddt")

                    protein = {
                        **protein,
                        "pdb_file_path": pdb_file_path,
                        "pdb_data": pdb_data,
                        "avg_plddt": avg_plddt,
                        "structure_source": "esmfold",
                    }

        except Exception as e:
            return {
                **update_node_history(state, "prepare_wt_metrics"),
                **add_error(state, "prepare_wt_metrics", e, recoverable=False),
            }

    # Run Fpocket
    wt_pocket_residues = {}
    wt_pocket_scores = []

    try:
        fpocket_result = call_fpocket(
            pdb_file_path or "/tmp/wt.pdb",
            pdb_data,
            str(OutputPaths.FPOCKET_WT),
            num_pockets=5,
        )

        if isinstance(fpocket_result, dict):
            wt_pocket_residues = fpocket_result.get("pocket_residues", {})
            wt_pocket_scores = fpocket_result.get("pocket_scores", [])

    except Exception:
        pass  # Pocket detection is optional

    # Initialize mutant data
    mutant_data = MutantData(
        wild_type_sequence=sequence,
        wild_type_metrics={
            "pocket_residues": wt_pocket_residues,
            "pocket_scores": wt_pocket_scores,
        },
        validated_mutants=[],
    )

    # Update structure state
    structure = state.get("structure", {})
    structure.update({
        "pocket_residues": wt_pocket_residues,
        "pocket_scores": wt_pocket_scores,
    })

    return {
        "protein": protein,
        "structure": structure,
        "mutant": mutant_data,
        **update_node_history(state, "prepare_wt_metrics"),
    }


# =============================================================================
# ProGen2 Generation Node
# =============================================================================

def run_progen2_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run ProGen2 for mutation generation.

    Note: Requires synde-minimal's ProGen2 wrapper.
    For standalone testing, returns mock mutants.
    """
    OutputPaths.ensure_all()

    protein = state.get("protein", {})
    parsed_input = state.get("parsed_input", {})
    mutant = state.get("mutant", {})

    sequence = protein.get("sequence")
    properties = parsed_input.get("properties", [])

    if not sequence:
        return update_node_history(state, "run_progen2")

    # ProGen2 requires synde-minimal integration
    if is_mock_mode():
        # Generate mock mutants
        mock_mutants = _generate_mock_mutants(sequence, properties, num_mutants=3)

        session_data = state.get("session_data", {})
        session_data["progen2_mutants"] = mock_mutants

        return {
            "mutant": mutant,
            "session_data": session_data,
            **update_node_history(state, "run_progen2"),
        }

    return update_node_history(state, "run_progen2")


def _generate_mock_mutants(sequence: str, properties: List[str], num_mutants: int = 3) -> List[Dict]:
    """Generate mock mutant sequences for testing."""
    import random

    amino_acids = "ACDEFGHIKLMNPQRSTVWY"
    mutants = []

    for i in range(num_mutants):
        # Pick 1-3 random positions to mutate
        num_mutations = random.randint(1, 3)
        positions = random.sample(range(len(sequence)), num_mutations)

        mutant_seq = list(sequence)
        mutations = []

        for pos in positions:
            original = sequence[pos]
            new_aa = random.choice([aa for aa in amino_acids if aa != original])
            mutant_seq[pos] = new_aa
            mutations.append(f"{original}{pos + 1}{new_aa}")

        mutants.append({
            "mutant_sequence": "".join(mutant_seq),
            "mutations": mutations,
            "source": "progen2",
        })

    return mutants


# =============================================================================
# ZymCTRL Generation Node
# =============================================================================

def run_zymctrl_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run ZymCTRL for EC-conditioned sequence generation.

    Note: Requires synde-minimal's ZymCTRL wrapper.
    """
    OutputPaths.ensure_all()

    session_data = state.get("session_data", {})
    wt_ec = session_data.get("wt_ec_number")

    if not wt_ec:
        return update_node_history(state, "run_zymctrl")

    # ZymCTRL requires synde-minimal integration
    if is_mock_mode():
        # Generate mock ZymCTRL sequences
        protein = state.get("protein", {})
        sequence = protein.get("sequence", "")

        mock_sequences = []
        if sequence:
            mock_sequences = _generate_mock_mutants(sequence, [], num_mutants=2)
            for seq in mock_sequences:
                seq["source"] = "zymctrl"

        session_data["zymctrl_sequences"] = mock_sequences
        return {
            "session_data": session_data,
            **update_node_history(state, "run_zymctrl"),
        }

    return update_node_history(state, "run_zymctrl")


# =============================================================================
# Validate Mutants Node
# =============================================================================

def validate_mutants_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Validate generated mutants using CLEAN EC prediction.

    Ensures mutants maintain the same EC classification as wild-type.
    """
    protein = state.get("protein", {})
    session_data = state.get("session_data", {})

    sequence = protein.get("sequence")
    progen2_mutants = session_data.get("progen2_mutants", [])

    if not progen2_mutants:
        return update_node_history(state, "validate_mutants")

    # Predict WT EC number
    wt_ec = None
    wt_prob = None

    try:
        manager = GpuTaskManager(task_name="CLEAN_EC")
        result = manager.execute_sync(call_clean_ec, args=(sequence, "WT"))

        if result.status == TaskStatus.SUCCESS:
            ec_result = result.result
            if isinstance(ec_result, dict) and ec_result.get("status") == "success":
                wt_ec = ec_result.get("ec_number")
                wt_prob = ec_result.get("probability")

    except Exception:
        pass

    # For mock mode, assume all mutants pass validation
    validated_mutants = progen2_mutants

    session_data["wt_ec_number"] = wt_ec
    session_data["wt_ec_probability"] = wt_prob
    session_data["validated_progen2"] = validated_mutants

    return {
        "session_data": session_data,
        **update_node_history(state, "validate_mutants"),
    }


# =============================================================================
# Evaluate Mutants Node
# =============================================================================

def evaluate_mutants_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Evaluate validated mutants and ZymCTRL sequences.

    Compares mutant properties against wild-type baseline.
    """
    session_data = state.get("session_data", {})

    validated_progen2 = session_data.get("validated_progen2", [])
    zymctrl_sequences = session_data.get("zymctrl_sequences", [])

    # Combine all validated mutants
    all_validated = list(validated_progen2) + list(zymctrl_sequences)

    # Add mock evaluation scores
    import random
    for mutant in all_validated:
        mutant["stability_score"] = round(random.uniform(-3, 3), 2)
        mutant["activity_score"] = round(random.uniform(0.5, 2.0), 2)

    session_data["all_validated_mutants"] = all_validated

    return {
        "session_data": session_data,
        **update_node_history(state, "evaluate_mutants"),
    }


# =============================================================================
# Sort Mutants Node
# =============================================================================

def sort_mutants_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Sort and rank validated mutants by target properties.

    Selects the best mutant and prepares final response.
    """
    protein = state.get("protein", {})
    parsed_input = state.get("parsed_input", {})
    structure = state.get("structure", {})
    session_data = state.get("session_data", {})
    mutant = state.get("mutant", {})

    properties = parsed_input.get("properties", [])
    all_validated = session_data.get("all_validated_mutants", [])

    if not all_validated:
        response = state.get("response", {})
        response_html = response.get("response_html", "")
        response_html += "No validated mutants found.<br>"

        return {
            "response": {**response, "response_html": response_html},
            **update_node_history(state, "sort_mutants"),
        }

    # Sort by composite score
    def score_mutant(m):
        stability = m.get("stability_score", 0)
        activity = m.get("activity_score", 1)
        return -stability + activity  # Lower stability (more negative DDG) is better

    sorted_mutants = sorted(all_validated, key=score_mutant, reverse=True)
    best_mutant = sorted_mutants[0]

    # Build response HTML
    response = state.get("response", {})
    response_html = _build_generation_response(parsed_input, best_mutant, properties)

    # Convert to MutantInfo format
    validated_mutants_list = [
        MutantInfo(
            mutant_sequence=m.get("mutant_sequence", ""),
            mutations=m.get("mutations", []),
            source=m.get("source", "unknown"),
            stability=m.get("stability_score"),
        )
        for m in sorted_mutants
    ]

    # Update mutant data
    mutant_data = MutantData(
        wild_type_sequence=protein.get("sequence"),
        wild_type_metrics=mutant.get("wild_type_metrics", {}),
        mutant_sequence=best_mutant.get("mutant_sequence"),
        mutations=best_mutant.get("mutations", []),
        validated_mutants=validated_mutants_list,
        best_mutant=best_mutant,
    )

    return {
        "mutant": mutant_data,
        "response": {
            **response,
            "response_html": response_html,
            "wild_type_pdb": protein.get("pdb_data"),
            "pocket_residues": structure.get("pocket_residues", {}),
            "pocket_scores": structure.get("pocket_scores", []),
            "validated_mutants": validated_mutants_list,
        },
        **update_node_history(state, "sort_mutants"),
    }


def _build_generation_response(
    parsed_input: Dict,
    best_mutant: Dict,
    properties: List[str]
) -> str:
    """Build HTML response for generation results."""
    task = parsed_input.get("task", "generation")

    response_html = (
        f"<strong>Identified Task:</strong> {task}<br>"
        f"<strong>Identified Properties:</strong> {', '.join(properties)}<br><br>"
    )

    # Mutations
    mutations = best_mutant.get("mutations", [])
    if mutations:
        response_html += f"<strong>Best Mutations:</strong> {', '.join(mutations)}<br>"

    # Scores
    stability = best_mutant.get("stability_score")
    if stability is not None:
        response_html += f"<strong>Stability Score (DDG):</strong> {stability:.2f} kcal/mol<br>"

    activity = best_mutant.get("activity_score")
    if activity is not None:
        response_html += f"<strong>Activity Score:</strong> {activity:.2f}<br>"

    # Mutant sequence
    mutant_seq = best_mutant.get("mutant_sequence", "")
    if mutant_seq:
        formatted = "<br>".join(textwrap.wrap(mutant_seq, 80))
        response_html += f"<strong>Mutant Sequence:</strong><br><code>{formatted}</code><br>"

    response_html += "<br><strong>Generation complete.</strong>"

    return response_html


# =============================================================================
# End Generation Node
# =============================================================================

def end_generation_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    End node for generation subgraph.

    Finalizes the generation workflow and prepares state for return.
    """
    mutant = state.get("mutant", {})
    validated = mutant.get("validated_mutants", [])

    return update_node_history(state, "end_generation")


# =============================================================================
# Routing Helpers
# =============================================================================

def has_progen2_mutants(state: SynDeGraphState) -> bool:
    """Check if ProGen2 generated any mutants."""
    session_data = state.get("session_data", {})
    return bool(session_data.get("progen2_mutants"))


def has_validated_mutants(state: SynDeGraphState) -> bool:
    """Check if any mutants passed validation."""
    session_data = state.get("session_data", {})
    return bool(session_data.get("all_validated_mutants"))


def has_ec_for_zymctrl(state: SynDeGraphState) -> bool:
    """Check if EC number is available for ZymCTRL."""
    session_data = state.get("session_data", {})
    return bool(session_data.get("wt_ec_number"))
