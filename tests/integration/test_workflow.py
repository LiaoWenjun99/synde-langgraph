"""
Integration tests for the complete workflow.
"""

import pytest
import os

# Enable mock mode
os.environ["MOCK_GPU"] = "true"

from synde_graph.graph import run_workflow, compile_graph
from synde_graph.state.factory import create_initial_state


@pytest.mark.integration
class TestCompleteWorkflow:
    """Tests for complete workflow execution."""

    def test_prediction_workflow(self):
        """Test a complete prediction workflow."""
        result = run_workflow(
            user_query="Predict EC number and melting temperature for P00720",
            job_id="test-pred",
        )

        assert result is not None
        assert "response" in result
        assert result["response"].get("response_html") is not None

    def test_generation_workflow(self):
        """Test a complete generation workflow."""
        sequence = "MKTVRQERLKSIVRILERSKEPVSGAQLAEYLGDGTRIGGLSLWRDVTRQLLGPKNTSEYLADVITLAEQVERILGTDEVFVNAGRGRTHGGYVGALNYQDSQLTPQQNKLFAFDM"

        result = run_workflow(
            user_query=f"Generate thermostable variants of {sequence}",
            job_id="test-gen",
        )

        assert result is not None
        assert "response" in result

    def test_theory_workflow(self):
        """Test a theory/explanation workflow."""
        result = run_workflow(
            user_query="Explain what EC numbers mean",
            job_id="test-theory",
        )

        assert result is not None
        assert "response" in result
        assert "EC" in result["response"].get("response_html", "")

    def test_fallback_workflow(self):
        """Test fallback when intent unclear."""
        result = run_workflow(
            user_query="Hello, how are you?",
            job_id="test-fallback",
        )

        assert result is not None
        assert "response" in result

    def test_workflow_with_session_data(self):
        """Test workflow with session context."""
        result = run_workflow(
            user_query="Predict stability",
            session_data={
                "last_protein_sequence": "MKTVRQERLKSIVRILERSKEPVSGAQLAEYLGDGTRIGGLSLWRDVTRQLLGPKNTSEYLADVITLAEQVERILGTDEVFVNAGRGRTHGGYVGALNYQDSQLTPQQNKLFAFDM",
                "last_uniprot_id": "P00720",
            },
            job_id="test-session",
        )

        assert result is not None
        assert result["protein"].get("sequence") is not None


@pytest.mark.integration
class TestGraphCompilation:
    """Tests for graph compilation."""

    def test_compile_simple_mode(self):
        """Test compiling in simple mode."""
        graph = compile_graph(use_simple_mode=True)
        assert graph is not None

    def test_graph_invocation(self):
        """Test direct graph invocation."""
        graph = compile_graph(use_simple_mode=True)

        initial_state = create_initial_state(
            job_id="test-invoke",
            user_query="Predict stability for P00720",
        )

        result = graph.invoke(initial_state)

        assert result is not None
        assert "current_node" in result
        assert "node_history" in result
        assert len(result["node_history"]) > 0


@pytest.mark.integration
class TestNodeHistory:
    """Tests for node traversal tracking."""

    def test_tracks_prediction_path(self):
        """Test that prediction nodes are tracked."""
        result = run_workflow(
            user_query="Predict EC number for P00720",
            job_id="test-track",
        )

        history = result.get("node_history", [])

        assert "intent_router" in history
        assert "input_parser" in history

    def test_tracks_generation_path(self):
        """Test that generation nodes are tracked."""
        sequence = "MKTVRQERLKSIVRILERSKEPVSGAQLAEYLGDGTRIGGLSLWRDVTRQLLGPKNTSEYLADVITLAEQVERILGTDEVFVNAGRGRTHGGYVGALNYQDSQLTPQQNKLFAFDM"

        result = run_workflow(
            user_query=f"Generate optimized variants of {sequence}",
            job_id="test-gen-track",
        )

        history = result.get("node_history", [])

        assert "intent_router" in history
        assert "input_parser" in history


@pytest.mark.integration
class TestErrorHandling:
    """Tests for error handling in workflows."""

    def test_handles_missing_sequence(self):
        """Test handling when no sequence available."""
        result = run_workflow(
            user_query="Predict stability",  # No sequence or UniProt ID
            job_id="test-no-seq",
        )

        # Should still complete, possibly with error or fallback
        assert result is not None
        assert "response" in result

    def test_recoverable_error_continues(self):
        """Test that recoverable errors don't stop workflow."""
        result = run_workflow(
            user_query="Predict kcat for P00720",  # Missing ligand
            job_id="test-recover",
        )

        # Should complete despite missing ligand for kcat
        assert result is not None
        assert "response" in result
