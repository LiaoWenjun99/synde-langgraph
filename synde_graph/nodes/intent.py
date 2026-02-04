"""
Intent Router Node for LangGraph workflow.

Analyzes user queries to detect intent (prediction, generation, etc.)
and extracts mutations and UniProt IDs.
"""

import re
from typing import Dict, Any, Optional, List

from synde_graph.state.schema import SynDeGraphState, IntentResult
from synde_graph.state.factory import update_node_history, add_error


# Intent keywords for simple classification
INTENT_KEYWORDS = {
    "prediction": [
        "predict", "calculate", "determine", "estimate", "what is",
        "find", "analyze", "compute", "measure"
    ],
    "generation": [
        "generate", "design", "create", "optimize", "improve",
        "engineer", "make", "develop", "build"
    ],
    "mutagenesis": [
        "mutate", "mutation", "mutant", "mutagenesis", "variant",
        "substitution", "point mutation"
    ],
    "plasmid": [
        "plasmid", "vector", "clone", "cloning", "expression system",
        "construct", "insert"
    ],
    "protocol": [
        "protocol", "procedure", "experiment", "method", "assay",
        "how to", "steps"
    ],
    "database-search": [
        "search", "find enzymes", "database", "similar", "homolog",
        "blast", "query"
    ],
    "theory": [
        "explain", "what does", "how does", "why", "theory",
        "mechanism", "understand", "describe"
    ],
}

# Mutation pattern: single letter + number + single letter (e.g., P148T, G45A)
MUTATION_PATTERN = re.compile(r'\b([A-Z])(\d+)([A-Z])\b')

# UniProt ID pattern: letter + 5 alphanumeric (e.g., P00720, Q9Y6K9)
UNIPROT_PATTERN = re.compile(r'\b([A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]|[OPQ][0-9][A-Z0-9]{3}[0-9])\b')


def intent_router_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    LangGraph node for intent detection.

    Analyzes the user query to determine intent (mutagenesis, plasmid,
    prediction, generation, etc.) and extracts any mutations or UniProt IDs.

    Args:
        state: Current workflow state containing user_query

    Returns:
        State update with intent result
    """
    user_query = state.get("user_query", "")

    if not user_query:
        return {
            "intent": IntentResult(
                intent="none",
                confidence=0.0,
                mutations=[],
                uniprot_id=None,
                reason="No query provided",
            ),
            **update_node_history(state, "intent_router"),
        }

    try:
        # Detect intent from keywords
        intent_type, confidence = _detect_intent(user_query)

        # Extract mutations
        mutations = _extract_mutations(user_query)

        # If mutations found, likely mutagenesis or generation
        if mutations and intent_type == "prediction":
            intent_type = "generation"
            confidence = max(confidence, 0.7)

        # Extract UniProt ID
        uniprot_id = _extract_uniprot_id(user_query)

        intent_result = IntentResult(
            intent=intent_type,
            confidence=confidence,
            mutations=mutations,
            uniprot_id=uniprot_id,
            reason=f"Detected {intent_type} intent from query analysis",
        )

        return {
            "intent": intent_result,
            **update_node_history(state, "intent_router"),
        }

    except Exception as e:
        # Return fallback intent on error
        return {
            "intent": IntentResult(
                intent="none",
                confidence=0.2,
                mutations=[],
                uniprot_id=None,
                reason=f"Intent detection error: {str(e)}",
            ),
            **update_node_history(state, "intent_router"),
            **add_error(state, "intent_router", e, recoverable=True),
        }


def _detect_intent(query: str) -> tuple[str, float]:
    """
    Detect intent from query using keyword matching.

    Args:
        query: User query text

    Returns:
        Tuple of (intent_type, confidence)
    """
    query_lower = query.lower()

    scores = {}
    for intent, keywords in INTENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in query_lower)
        if score > 0:
            scores[intent] = score

    if not scores:
        return "prediction", 0.3  # Default to prediction

    # Get highest scoring intent
    best_intent = max(scores, key=scores.get)
    max_score = scores[best_intent]

    # Calculate confidence based on match count
    confidence = min(0.9, 0.5 + (max_score * 0.1))

    return best_intent, confidence


def _extract_mutations(query: str) -> List[str]:
    """
    Extract mutation patterns from query.

    Args:
        query: User query text

    Returns:
        List of mutations (e.g., ["P148T", "G45A"])
    """
    matches = MUTATION_PATTERN.findall(query)
    return [f"{m[0]}{m[1]}{m[2]}" for m in matches]


def _extract_uniprot_id(query: str) -> Optional[str]:
    """
    Extract UniProt ID from query.

    Args:
        query: User query text

    Returns:
        UniProt ID or None
    """
    match = UNIPROT_PATTERN.search(query)
    return match.group(0) if match else None


# =============================================================================
# Helper Functions
# =============================================================================

def get_intent_type(state: SynDeGraphState) -> str:
    """
    Helper function to extract intent type from state.

    Args:
        state: Current workflow state

    Returns:
        Intent type string
    """
    intent = state.get("intent", {})
    return intent.get("intent", "none")


def has_mutations(state: SynDeGraphState) -> bool:
    """
    Check if mutations were extracted from the query.

    Args:
        state: Current workflow state

    Returns:
        True if mutations were found
    """
    intent = state.get("intent", {})
    mutations = intent.get("mutations", [])
    return bool(mutations)


def get_extracted_uniprot_id(state: SynDeGraphState) -> Optional[str]:
    """
    Get UniProt ID extracted during intent detection.

    Args:
        state: Current workflow state

    Returns:
        UniProt ID or None
    """
    intent = state.get("intent", {})
    return intent.get("uniprot_id")
