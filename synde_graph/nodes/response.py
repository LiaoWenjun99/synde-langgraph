"""
Response Formatting Nodes for LangGraph workflow.

Implements nodes for formatting final responses including:
- Natural language response generation
- Fallback responses
- Error responses
"""

from typing import Dict, Any

from synde_graph.state.schema import SynDeGraphState
from synde_graph.state.factory import update_node_history


def response_formatter_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Format the final response with natural language summary.

    Takes the accumulated response_html and generates a natural
    language summary for the user.
    """
    response = state.get("response", {})
    response_html = response.get("response_html", "")
    parsed_input = state.get("parsed_input", {})
    protein = state.get("protein", {})
    mutant = state.get("mutant", {})

    # Generate natural reply
    natural_reply = _generate_natural_reply(
        task=parsed_input.get("task", "prediction"),
        properties=parsed_input.get("properties", []),
        protein=protein,
        mutant=mutant,
        response_html=response_html,
    )

    return {
        "response": {
            **response,
            "natural_reply": natural_reply,
        },
        **update_node_history(state, "response_formatter"),
    }


def _generate_natural_reply(
    task: str,
    properties: list,
    protein: dict,
    mutant: dict,
    response_html: str,
) -> str:
    """
    Generate a natural language summary of the workflow results.

    Args:
        task: Task type (prediction, generation, etc.)
        properties: Requested properties
        protein: Protein data
        mutant: Mutant data
        response_html: Accumulated HTML response

    Returns:
        Natural language summary string
    """
    parts = []

    # Task summary
    if task == "prediction":
        parts.append("I've completed the protein property prediction analysis.")
    elif task == "generation":
        parts.append("I've completed the protein sequence optimization.")
    elif task == "mutagenesis":
        parts.append("I've analyzed the requested mutations.")
    else:
        parts.append("I've processed your request.")

    # Protein info
    sequence_length = protein.get("sequence_length", 0)
    uniprot_id = protein.get("uniprot_id")
    structure_source = protein.get("structure_source")

    if uniprot_id:
        parts.append(f"The analysis was performed on {uniprot_id}.")
    elif sequence_length:
        parts.append(f"The analysis was performed on a {sequence_length} amino acid sequence.")

    if structure_source == "esmfold":
        parts.append("Structure was predicted using ESMFold.")
    elif structure_source == "alphafold":
        parts.append("Structure was predicted using AlphaFold3.")
    elif structure_source == "uniprot":
        parts.append("Structure was retrieved from AlphaFold Database.")
    elif structure_source == "uploaded":
        parts.append("Using the uploaded structure.")

    # Property results
    if properties:
        parts.append(f"Predicted properties: {', '.join(properties)}.")

    # Mutant results
    if task == "generation":
        best_mutant = mutant.get("best_mutant", {})
        mutations = best_mutant.get("mutations", [])
        if mutations:
            parts.append(f"Best mutations identified: {', '.join(mutations)}.")

    # pLDDT
    avg_plddt = protein.get("avg_plddt")
    if avg_plddt:
        parts.append(f"Structure confidence (pLDDT): {avg_plddt:.1f}.")

    return " ".join(parts)


def fallback_response_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Generate a fallback response when intent is unclear.

    Used when the workflow cannot determine what the user wants
    or the request doesn't fit any known pattern.
    """
    user_query = state.get("user_query", "")

    response_html = (
        "<strong>I couldn't determine a specific task from your request.</strong><br><br>"
        "I can help you with:<br>"
        "<ul>"
        "<li><strong>Prediction</strong> - Predict protein properties (stability, kcat, EC number, Tm)</li>"
        "<li><strong>Generation</strong> - Design optimized protein variants</li>"
        "<li><strong>Mutagenesis</strong> - Analyze specific mutations</li>"
        "<li><strong>Structure</strong> - Predict or analyze protein structures</li>"
        "</ul><br>"
        "Please try rephrasing your request with more specific terms, or provide:<br>"
        "<ul>"
        "<li>A UniProt ID (e.g., P00720)</li>"
        "<li>A protein sequence</li>"
        "<li>The properties you want to predict</li>"
        "</ul>"
    )

    natural_reply = (
        "I wasn't able to determine what you'd like me to do. "
        "Could you please specify the task (predict, generate, mutate) "
        "and provide a protein sequence or UniProt ID?"
    )

    return {
        "response": {
            "response_html": response_html,
            "natural_reply": natural_reply,
        },
        **update_node_history(state, "fallback_response"),
    }


def error_response_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Generate an error response when a fatal error occurs.

    Collects error information from the state and formats
    a user-friendly error message.
    """
    errors = state.get("errors", [])
    user_query = state.get("user_query", "")

    # Find the most recent fatal error
    fatal_errors = [e for e in errors if not e.get("recoverable", True)]
    most_recent = fatal_errors[-1] if fatal_errors else (errors[-1] if errors else {})

    error_type = most_recent.get("error_type", "UnknownError")
    error_message = most_recent.get("message", "An unexpected error occurred")
    error_node = most_recent.get("node", "unknown")

    response_html = (
        f"<strong>Error during {error_node}:</strong><br><br>"
        f"<code>{error_type}: {error_message}</code><br><br>"
        "Please try:<br>"
        "<ul>"
        "<li>Checking your input sequence or UniProt ID</li>"
        "<li>Ensuring the protein sequence is valid</li>"
        "<li>Providing a ligand SMILES if predicting kcat or docking</li>"
        "</ul>"
    )

    natural_reply = (
        f"I encountered an error while processing your request: {error_message}. "
        "Please check your input and try again."
    )

    return {
        "response": {
            "response_html": response_html,
            "natural_reply": natural_reply,
        },
        **update_node_history(state, "error_response"),
    }


def theory_response_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Handle theory/explanation requests.

    Provides explanatory responses for theoretical questions
    about protein engineering concepts.
    """
    user_query = state.get("user_query", "").lower()

    # Common theory topics
    if "ec number" in user_query or "enzyme class" in user_query:
        response_html = (
            "<strong>EC Number (Enzyme Commission Number)</strong><br><br>"
            "EC numbers are a numerical classification scheme for enzymes based on the "
            "chemical reactions they catalyze. The format is EC X.X.X.X where:<br><br>"
            "<ul>"
            "<li><strong>First digit</strong>: Main enzyme class (1=Oxidoreductases, 2=Transferases, etc.)</li>"
            "<li><strong>Second digit</strong>: Subclass (type of group transferred/bond broken)</li>"
            "<li><strong>Third digit</strong>: Sub-subclass (more specific reaction type)</li>"
            "<li><strong>Fourth digit</strong>: Serial number for the specific enzyme</li>"
            "</ul>"
        )
        natural_reply = (
            "EC numbers classify enzymes by the reactions they catalyze. "
            "The four-digit code describes the enzyme class, subclass, sub-subclass, "
            "and specific enzyme within that category."
        )

    elif "kcat" in user_query or "turnover" in user_query:
        response_html = (
            "<strong>kcat (Catalytic Constant / Turnover Number)</strong><br><br>"
            "kcat represents the maximum number of substrate molecules converted to "
            "product per enzyme molecule per unit time (typically per second).<br><br>"
            "<ul>"
            "<li>Units: s<sup>-1</sup></li>"
            "<li>Higher kcat = faster catalysis</li>"
            "<li>Typical range: 1 - 10,000 s<sup>-1</sup></li>"
            "</ul>"
        )
        natural_reply = (
            "kcat, or the turnover number, measures how many substrate molecules "
            "an enzyme can convert to product per second. It's a key measure of "
            "catalytic efficiency."
        )

    elif "plddt" in user_query or "confidence" in user_query:
        response_html = (
            "<strong>pLDDT (Predicted Local Distance Difference Test)</strong><br><br>"
            "pLDDT is a per-residue confidence score from structure prediction models "
            "like AlphaFold and ESMFold.<br><br>"
            "<ul>"
            "<li>Range: 0-100</li>"
            "<li>>90: Very high confidence (reliable)</li>"
            "<li>70-90: Confident (backbone accurate)</li>"
            "<li>50-70: Low confidence (may be disordered)</li>"
            "<li><50: Very low confidence</li>"
            "</ul>"
        )
        natural_reply = (
            "pLDDT is a confidence score for predicted protein structures. "
            "Scores above 90 indicate high confidence, while scores below 50 "
            "suggest the region may be disordered or incorrectly predicted."
        )

    else:
        response_html = (
            "<strong>Protein Engineering Concepts</strong><br><br>"
            "I can explain various concepts in protein engineering. "
            "Try asking about:<br>"
            "<ul>"
            "<li>EC numbers (enzyme classification)</li>"
            "<li>kcat and Km (enzyme kinetics)</li>"
            "<li>pLDDT (structure confidence)</li>"
            "<li>Tm (melting temperature)</li>"
            "<li>DDG (stability changes)</li>"
            "</ul>"
        )
        natural_reply = (
            "I can explain protein engineering concepts. "
            "What would you like to know about?"
        )

    return {
        "response": {
            "response_html": response_html,
            "natural_reply": natural_reply,
        },
        **update_node_history(state, "theory_response"),
    }
