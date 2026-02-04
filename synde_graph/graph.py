"""
Main LangGraph construction for SynDe workflow.

Provides the main graph that orchestrates the complete protein
engineering workflow from user query to final response.
"""

from typing import Dict, Any, Optional
import uuid

from langgraph.graph import StateGraph, END

from synde_graph.state.schema import SynDeGraphState
from synde_graph.state.factory import create_initial_state
from synde_graph.nodes.intent import intent_router_node
from synde_graph.nodes.input import input_parser_node
from synde_graph.nodes.response import (
    response_formatter_node,
    fallback_response_node,
    error_response_node,
    theory_response_node,
)
from synde_graph.routing.routes import route_by_intent, has_fatal_error
from synde_graph.subgraphs.prediction import create_simple_prediction_graph
from synde_graph.subgraphs.generation import create_simple_generation_graph


def create_synde_graph(use_simple_mode: bool = True) -> StateGraph:
    """
    Create the main SynDe LangGraph workflow.

    Graph structure:
        START
          |
          v
        intent_router
          |
          v
        input_parser
          |
          +-- prediction_subgraph
          +-- generation_subgraph
          +-- fallback_response
          +-- theory_response
          +-- error_response
          |
          v
        response_formatter
          |
          v
        END

    Args:
        use_simple_mode: Use simplified subgraphs (default True for testing)

    Returns:
        Configured StateGraph ready for compilation
    """
    graph = StateGraph(SynDeGraphState)

    # Add main workflow nodes
    graph.add_node("intent_router", intent_router_node)
    graph.add_node("input_parser", input_parser_node)
    graph.add_node("response_formatter", response_formatter_node)
    graph.add_node("fallback_response", fallback_response_node)
    graph.add_node("theory_response", theory_response_node)
    graph.add_node("error_response", error_response_node)

    # Add subgraph nodes
    if use_simple_mode:
        prediction_graph = create_simple_prediction_graph()
        generation_graph = create_simple_generation_graph()
    else:
        from synde_graph.subgraphs.prediction import create_prediction_subgraph
        from synde_graph.subgraphs.generation import create_generation_subgraph
        prediction_graph = create_prediction_subgraph()
        generation_graph = create_generation_subgraph()

    # Add subgraphs as nodes
    graph.add_node("prediction_subgraph", run_prediction_subgraph)
    graph.add_node("generation_subgraph", run_generation_subgraph)

    # Set entry point
    graph.set_entry_point("intent_router")

    # Connect intent_router to input_parser
    graph.add_edge("intent_router", "input_parser")

    # Route from input_parser based on intent
    graph.add_conditional_edges(
        "input_parser",
        _route_with_error_check,
        {
            "prediction_subgraph": "prediction_subgraph",
            "generation_subgraph": "generation_subgraph",
            "fallback_response": "fallback_response",
            "theory_response": "theory_response",
            "error_response": "error_response",
        }
    )

    # Connect subgraphs and responses to response_formatter
    graph.add_edge("prediction_subgraph", "response_formatter")
    graph.add_edge("generation_subgraph", "response_formatter")
    graph.add_edge("fallback_response", "response_formatter")
    graph.add_edge("theory_response", "response_formatter")
    graph.add_edge("error_response", "response_formatter")

    # Set finish point
    graph.set_finish_point("response_formatter")

    return graph


def _route_with_error_check(state: SynDeGraphState) -> str:
    """Route with error checking."""
    if has_fatal_error(state):
        return "error_response"
    return route_by_intent(state)


def run_prediction_subgraph(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Execute the prediction subgraph.

    This wraps the subgraph execution for the main graph.
    """
    from synde_graph.subgraphs.prediction import create_simple_prediction_graph

    subgraph = create_simple_prediction_graph()
    compiled = subgraph.compile()

    # Run subgraph
    result = compiled.invoke(state)

    return result


def run_generation_subgraph(state: SynDeGraphState) -> Dict[str, Any]:
    """
    Execute the generation subgraph.

    This wraps the subgraph execution for the main graph.
    """
    from synde_graph.subgraphs.generation import create_simple_generation_graph

    subgraph = create_simple_generation_graph()
    compiled = subgraph.compile()

    # Run subgraph
    result = compiled.invoke(state)

    return result


def compile_graph(use_simple_mode: bool = True):
    """
    Create and compile the SynDe graph.

    Args:
        use_simple_mode: Use simplified subgraphs

    Returns:
        Compiled graph ready for invocation
    """
    graph = create_synde_graph(use_simple_mode=use_simple_mode)
    return graph.compile()


def run_workflow(
    user_query: str,
    user_id: Optional[int] = None,
    uploaded_pdb_path: Optional[str] = None,
    uploaded_pdb_content: Optional[str] = None,
    session_data: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the complete SynDe workflow.

    Args:
        user_query: User's input query
        user_id: Optional user ID
        uploaded_pdb_path: Optional path to uploaded PDB
        uploaded_pdb_content: Optional PDB file content
        session_data: Optional session context
        job_id: Optional job ID (generated if not provided)

    Returns:
        Final workflow state with response
    """
    # Generate job ID if not provided
    if job_id is None:
        job_id = str(uuid.uuid4())[:8]

    # Create initial state
    initial_state = create_initial_state(
        job_id=job_id,
        user_query=user_query,
        user_id=user_id,
        uploaded_pdb_path=uploaded_pdb_path,
        uploaded_pdb_content=uploaded_pdb_content,
        session_data=session_data,
    )

    # Compile and run graph
    graph = compile_graph(use_simple_mode=True)
    result = graph.invoke(initial_state)

    return result


async def run_workflow_async(
    user_query: str,
    user_id: Optional[int] = None,
    uploaded_pdb_path: Optional[str] = None,
    uploaded_pdb_content: Optional[str] = None,
    session_data: Optional[Dict[str, Any]] = None,
    job_id: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Run the complete SynDe workflow asynchronously.

    Args:
        user_query: User's input query
        user_id: Optional user ID
        uploaded_pdb_path: Optional path to uploaded PDB
        uploaded_pdb_content: Optional PDB file content
        session_data: Optional session context
        job_id: Optional job ID (generated if not provided)

    Returns:
        Final workflow state with response
    """
    # Generate job ID if not provided
    if job_id is None:
        job_id = str(uuid.uuid4())[:8]

    # Create initial state
    initial_state = create_initial_state(
        job_id=job_id,
        user_query=user_query,
        user_id=user_id,
        uploaded_pdb_path=uploaded_pdb_path,
        uploaded_pdb_content=uploaded_pdb_content,
        session_data=session_data,
    )

    # Compile and run graph
    graph = compile_graph(use_simple_mode=True)
    result = await graph.ainvoke(initial_state)

    return result


def get_workflow_status(job_id: str, checkpointer=None) -> Optional[Dict[str, Any]]:
    """
    Get the current status of a workflow.

    Args:
        job_id: Workflow job ID
        checkpointer: Optional checkpointer to query

    Returns:
        Workflow status dict or None if not found
    """
    if checkpointer is None:
        return None

    try:
        checkpoint = checkpointer.get_tuple({"configurable": {"thread_id": job_id}})
        if checkpoint:
            state = checkpoint.checkpoint
            return {
                "job_id": job_id,
                "current_node": state.get("current_node"),
                "node_history": state.get("node_history", []),
                "errors": state.get("errors", []),
                "completed": state.get("current_node") == "response_formatter",
            }
    except Exception:
        pass

    return None
