"""
Prediction Nodes for LangGraph workflow.

Implements nodes for protein property prediction including:
- Structure prediction (ESMFold, AlphaFold)
- Pocket detection (Fpocket)
- Property prediction (FoldX, Tomer, CLEAN, DeepEnzyme, TemBERTure)
"""

import os
from typing import Dict, Any

from synde_graph.state.schema import SynDeGraphState
from synde_graph.state.factory import update_node_history, add_error
from synde_graph.config import OutputPaths, SequenceLimits
from synde_gpu.tasks import (
    call_esmfold,
    call_clean_ec,
    call_deepenzyme,
    call_temberture,
    call_fpocket,
)
from synde_gpu.manager import GpuTaskManager, TaskStatus
from synde_gpu.mocks import is_mock_mode
from synde_graph.utils.live_logger import report, report_gpu_task


# =============================================================================
# Structure Prediction Nodes
# =============================================================================

def check_structure_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Check if structure prediction is needed.

    Determines whether to run ESMFold or AlphaFold based on:
    - Existing PDB availability
    - Sequence length (ESMFold < 400 AA, AlphaFold > 400 AA)

    Returns:
        State update with structure routing decision
    """
    protein = state.get("protein", {})
    pdb_file_path = protein.get("pdb_file_path")
    sequence = protein.get("sequence")
    sequence_length = protein.get("sequence_length", 0)

    if pdb_file_path and os.path.exists(pdb_file_path):
        return update_node_history(state, "check_structure")

    if not sequence:
        return {
            **update_node_history(state, "check_structure"),
            **add_error(
                state, "check_structure",
                ValueError("No sequence available for structure prediction"),
                recoverable=False
            ),
        }

    return update_node_history(state, "check_structure")


def run_esmfold_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run ESMFold for structure prediction.

    Used for sequences <= 400 amino acids.
    """
    OutputPaths.ensure_all()

    protein = state.get("protein", {})
    sequence = protein.get("sequence")
    job_id = state.get("job_id", "unknown")

    if not sequence:
        return {
            **update_node_history(state, "run_esmfold"),
            **add_error(
                state, "run_esmfold",
                ValueError("No sequence provided for ESMFold"),
                recoverable=False
            ),
        }

    try:
        report_gpu_task("ESMFold", f"Predicting structure ({len(sequence)} aa)")
        manager = GpuTaskManager(task_name="ESMFold")
        result = manager.execute_sync(call_esmfold, args=(job_id, sequence))

        if result.status == TaskStatus.SUCCESS:
            fold_res = result.result
            if isinstance(fold_res, dict) and fold_res.get("status") == "success":
                pdb_file_path = fold_res.get("pdb_path")
                pdb_data = fold_res.get("pdb_data")
                avg_plddt = fold_res.get("avg_plddt")

                report_gpu_task("ESMFold", f"Complete (pLDDT: {avg_plddt:.1f})" if avg_plddt else "Complete")

                return {
                    "protein": {
                        **protein,
                        "pdb_file_path": pdb_file_path,
                        "pdb_data": pdb_data,
                        "avg_plddt": avg_plddt,
                        "structure_source": "esmfold",
                    },
                    **update_node_history(state, "run_esmfold"),
                }

        report_gpu_task("ESMFold", f"Failed: {result.error or 'Unknown error'}")
        raise RuntimeError(f"ESMFold failed: {result.error or 'Unknown error'}")

    except Exception as e:
        return {
            **update_node_history(state, "run_esmfold"),
            **add_error(state, "run_esmfold", e, recoverable=False),
        }


def run_alphafold_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run AlphaFold3 for structure prediction.

    Used for sequences > 400 amino acids.
    Note: Requires synde-minimal's AlphaFold runner.
    """
    OutputPaths.ensure_all()

    protein = state.get("protein", {})
    sequence = protein.get("sequence")

    if not sequence:
        return {
            **update_node_history(state, "run_alphafold"),
            **add_error(
                state, "run_alphafold",
                ValueError("No sequence provided for AlphaFold"),
                recoverable=False
            ),
        }

    # AlphaFold requires synde-minimal integration
    # For standalone mode, return a placeholder
    if is_mock_mode():
        from synde_gpu.mocks import MockGpuResponses
        mock_result = MockGpuResponses.esmfold("alphafold", sequence)

        return {
            "protein": {
                **protein,
                "pdb_file_path": mock_result.get("pdb_path"),
                "pdb_data": mock_result.get("pdb_data"),
                "avg_plddt": mock_result.get("avg_plddt"),
                "structure_source": "alphafold",
            },
            **update_node_history(state, "run_alphafold"),
        }

    return {
        **update_node_history(state, "run_alphafold"),
        **add_error(
            state, "run_alphafold",
            NotImplementedError("AlphaFold requires synde-minimal integration"),
            recoverable=False
        ),
    }


# =============================================================================
# Pocket Detection Node
# =============================================================================

def run_fpocket_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run Fpocket for binding pocket detection.
    """
    OutputPaths.ensure_all()

    protein = state.get("protein", {})
    pdb_file_path = protein.get("pdb_file_path")
    pdb_data = protein.get("pdb_data")

    if not pdb_file_path and not pdb_data:
        return update_node_history(state, "run_fpocket")

    try:
        result = call_fpocket(
            pdb_file_path or "/tmp/structure.pdb",
            pdb_data,
            str(OutputPaths.FPOCKET_WT),
            num_pockets=5,
        )

        # Handle mock/direct result
        if isinstance(result, dict):
            pocket_residues = result.get("pocket_residues", {})
            pocket_scores = result.get("pocket_scores", [])

            structure = state.get("structure", {})
            structure.update({
                "pocket_residues": pocket_residues,
                "pocket_scores": pocket_scores,
            })

            return {
                "structure": structure,
                **update_node_history(state, "run_fpocket"),
            }

        return update_node_history(state, "run_fpocket")

    except Exception as e:
        return {
            **update_node_history(state, "run_fpocket"),
            **add_error(state, "run_fpocket", e, recoverable=True),
        }


# =============================================================================
# Property Prediction Nodes
# =============================================================================

def run_foldx_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run FoldX for stability prediction.

    Note: Requires synde-minimal's FoldX wrapper.
    """
    OutputPaths.ensure_all()

    protein = state.get("protein", {})
    pdb_file_path = protein.get("pdb_file_path")
    sequence = protein.get("sequence")

    if not pdb_file_path or not sequence:
        return update_node_history(state, "run_foldx")

    # FoldX requires synde-minimal integration
    # For standalone, return mock result
    if is_mock_mode():
        import random
        stability = round(random.uniform(-5, 5), 2)

        response = state.get("response", {})
        response_html = response.get("response_html", "")
        response_html += f"<strong>FoldX Stability (DDG):</strong> {stability} kcal/mol<br>"

        return {
            "response": {**response, "response_html": response_html},
            **update_node_history(state, "run_foldx"),
        }

    return update_node_history(state, "run_foldx")


def run_tomer_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run Tomer for optimum temperature prediction.

    Note: Requires synde-minimal's Tomer wrapper.
    """
    protein = state.get("protein", {})
    sequence = protein.get("sequence")

    if not sequence:
        return update_node_history(state, "run_tomer")

    # Tomer requires synde-minimal integration
    if is_mock_mode():
        import random
        topt = round(37.0 + random.uniform(-10, 30), 2)
        stderr = round(random.uniform(1, 5), 2)

        response = state.get("response", {})
        response_html = response.get("response_html", "")
        response_html += (
            f"<strong>Tomer Optimum Temperature:</strong> {topt} C<br>"
            f"<strong>Standard Error:</strong> +/- {stderr} C<br>"
        )

        return {
            "response": {**response, "response_html": response_html},
            **update_node_history(state, "run_tomer"),
        }

    return update_node_history(state, "run_tomer")


def run_clean_ec_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run CLEAN for EC number prediction.
    """
    import logging
    logger = logging.getLogger(__name__)

    protein = state.get("protein", {})
    sequence = protein.get("sequence")

    logger.info(f"run_clean_ec_node: sequence length = {len(sequence) if sequence else 0}")

    if not sequence:
        logger.warning("No sequence available for EC prediction")
        return update_node_history(state, "run_clean_ec")

    try:
        report_gpu_task("CLEAN EC", "Predicting enzyme class")
        manager = GpuTaskManager(task_name="CLEAN_EC")
        result = manager.execute_sync(call_clean_ec, args=(sequence, "Input_Seq"))

        logger.info(f"CLEAN EC result status: {result.status}")
        logger.info(f"CLEAN EC result data: {result.result}")

        if result.status == TaskStatus.SUCCESS:
            ec_result = result.result

            # Handle different result formats
            ec_number = None
            probability = None

            if isinstance(ec_result, dict):
                # Check for status field (standard format)
                if ec_result.get("status") == "success" or "ec_number" in ec_result:
                    ec_number = ec_result.get("ec_number")
                    probability = ec_result.get("probability", 0.0)
                # Check for alternative formats
                elif "result" in ec_result:
                    inner = ec_result["result"]
                    ec_number = inner.get("ec_number")
                    probability = inner.get("probability", 0.0)

            logger.info(f"Extracted EC: {ec_number}, probability: {probability}")

            if ec_number:
                response = state.get("response", {})
                response_html = response.get("response_html", "")

                # Format probability safely
                prob_str = f"{probability:.3f}" if isinstance(probability, (int, float)) else str(probability)
                response_html += (
                    f"<strong>CLEAN EC Number:</strong> {ec_number}<br>"
                    f"<strong>Probability:</strong> {prob_str}<br>"
                )

                # Also add to predictions dict for structured access
                predictions = state.get("predictions", {})
                predictions["ec_number"] = {
                    "ec_number": ec_number,
                    "probability": probability,
                }

                report_gpu_task("CLEAN EC", f"Complete: {ec_number} (prob: {prob_str})")
                logger.info(f"EC prediction added to response_html")
                return {
                    "response": {**response, "response_html": response_html},
                    "predictions": predictions,
                    **update_node_history(state, "run_clean_ec"),
                }
            else:
                # Check if it's an error response
                error_msg = ec_result.get("message", "Unknown error") if isinstance(ec_result, dict) else str(ec_result)
                logger.warning(f"EC number not found in result: {ec_result}")

                # Add error message to response
                response = state.get("response", {})
                response_html = response.get("response_html", "")
                response_html += f"<strong>EC Prediction Error:</strong> {error_msg}<br>"

                return {
                    "response": {**response, "response_html": response_html},
                    **update_node_history(state, "run_clean_ec"),
                    **add_error(
                        state, "run_clean_ec",
                        RuntimeError(f"CLEAN EC prediction failed: {error_msg}"),
                        recoverable=True
                    ),
                }

        else:
            logger.error(f"CLEAN EC task failed: {result.error}")

        return update_node_history(state, "run_clean_ec")

    except Exception as e:
        logger.error(f"Exception in run_clean_ec_node: {e}", exc_info=True)
        return {
            **update_node_history(state, "run_clean_ec"),
            **add_error(state, "run_clean_ec", e, recoverable=True),
        }


def run_deepenzyme_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run DeepEnzyme for kcat prediction.

    Requires ligand SMILES.
    """
    protein = state.get("protein", {})
    ligand = state.get("ligand", {})
    sequence = protein.get("sequence")
    pdb_file_path = protein.get("pdb_file_path")
    ligand_smiles = ligand.get("ligand_smiles")

    if not sequence or not pdb_file_path or not ligand_smiles:
        # Report exactly what's missing so the user knows what to provide
        missing = []
        if not sequence:
            missing.append("protein sequence")
        if not pdb_file_path:
            missing.append("PDB structure")
        if not ligand_smiles:
            missing.append("ligand/substrate SMILES")
        missing_str = ", ".join(missing)

        report(f"⚠️ DeepEnzyme kcat prediction skipped — missing: {missing_str}")

        # Add a visible message to the response so the user sees it in the UI
        response = state.get("response", {})
        response_html = response.get("response_html", "")
        response_html += (
            f"<strong>DeepEnzyme kcat:</strong> Skipped — requires {missing_str}.<br>"
            f"<em>Tip: Include a substrate name (e.g. ATP, glucose, pyruvate) "
            f"or SMILES string in your query to enable kcat prediction.</em><br>"
        )

        return {
            "response": {**response, "response_html": response_html},
            **update_node_history(state, "run_deepenzyme"),
        }

    try:
        report_gpu_task("DeepEnzyme", "Predicting kcat")
        manager = GpuTaskManager(task_name="DeepEnzyme")
        result = manager.execute_sync(
            call_deepenzyme,
            args=(sequence, pdb_file_path, ligand_smiles)
        )

        if result.status == TaskStatus.SUCCESS:
            de_result = result.result
            if isinstance(de_result, dict) and de_result.get("status") == "success":
                kcat = de_result.get("kcat")

                report_gpu_task("DeepEnzyme", f"Complete: kcat = {kcat} s⁻¹")

                response = state.get("response", {})
                response_html = response.get("response_html", "")
                response_html += f"<strong>DeepEnzyme kcat:</strong> {kcat} s<sup>-1</sup><br>"

                return {
                    "response": {**response, "response_html": response_html},
                    **update_node_history(state, "run_deepenzyme"),
                }

        return update_node_history(state, "run_deepenzyme")

    except Exception as e:
        return {
            **update_node_history(state, "run_deepenzyme"),
            **add_error(state, "run_deepenzyme", e, recoverable=True),
        }


def run_temberture_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Run TemBERTure for melting temperature prediction.
    """
    protein = state.get("protein", {})
    sequence = protein.get("sequence")

    if not sequence:
        return update_node_history(state, "run_temberture")

    try:
        report_gpu_task("TemBERTure", "Predicting melting temperature")
        manager = GpuTaskManager(task_name="TemBERTure")
        result = manager.execute_sync(call_temberture, args=(sequence,))

        if result.status == TaskStatus.SUCCESS:
            temp_result = result.result
            if isinstance(temp_result, dict) and temp_result.get("status") == "success":
                tm = temp_result.get("melting_temperature")
                thermo_class = temp_result.get("thermo_class")

                report_gpu_task("TemBERTure", f"Complete: Tm = {tm:.1f}°C ({thermo_class})")

                response = state.get("response", {})
                response_html = response.get("response_html", "")
                response_html += (
                    f"<strong>TemBERTure Melting Temp:</strong> {tm:.2f} C<br>"
                    f"<strong>Thermophilicity:</strong> {thermo_class}<br>"
                )

                return {
                    "response": {**response, "response_html": response_html},
                    **update_node_history(state, "run_temberture"),
                }

        return update_node_history(state, "run_temberture")

    except Exception as e:
        return {
            **update_node_history(state, "run_temberture"),
            **add_error(state, "run_temberture", e, recoverable=True),
        }


# =============================================================================
# Results Aggregation Node
# =============================================================================

def aggregate_prediction_results_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Aggregate all prediction results into final response.
    """
    protein = state.get("protein", {})
    structure = state.get("structure", {})
    response = state.get("response", {})
    parsed_input = state.get("parsed_input", {})

    task = parsed_input.get("task", "prediction")
    properties = parsed_input.get("properties", [])

    response_html = response.get("response_html", "")
    header = (
        f"<strong>Identified Task:</strong> {task}<br>"
        f"<strong>Identified Properties:</strong> {', '.join(properties)}<br><br>"
    )

    # Add structure info
    if protein.get("pdb_file_path"):
        source = protein.get("structure_source", "unknown")
        plddt = protein.get("avg_plddt")
        header += f"<strong>Structure Source:</strong> {source}<br>"
        if plddt:
            header += f"<strong>Average pLDDT:</strong> {plddt:.2f}<br>"

    # Add pocket info
    if structure.get("pocket_scores"):
        num_pockets = len(structure["pocket_scores"])
        header += f"<strong>Detected Pockets:</strong> {num_pockets}<br>"

    full_response = header + response_html

    return {
        "response": {
            **response,
            "response_html": full_response,
            "wild_type_pdb": protein.get("pdb_data"),
            "pocket_residues": structure.get("pocket_residues", {}),
            "pocket_scores": structure.get("pocket_scores", []),
        },
        **update_node_history(state, "aggregate_prediction_results"),
    }
