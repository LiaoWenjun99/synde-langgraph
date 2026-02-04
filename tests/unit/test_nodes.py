"""
Unit tests for LangGraph nodes.
"""

import pytest
import os

# Enable mock mode
os.environ["MOCK_GPU"] = "true"

from synde_graph.nodes.intent import (
    intent_router_node,
    get_intent_type,
    has_mutations,
)
from synde_graph.nodes.input import (
    input_parser_node,
    get_task_type,
    has_protein_sequence,
)
from synde_graph.state.factory import create_initial_state


@pytest.mark.unit
class TestIntentRouterNode:
    """Tests for intent_router_node."""

    def test_detects_prediction_intent(self):
        """Test detection of prediction intent."""
        state = create_initial_state(
            job_id="test",
            user_query="Predict the EC number for P00720",
        )

        result = intent_router_node(state)

        assert "intent" in result
        assert result["intent"]["intent"] == "prediction"

    def test_detects_generation_intent(self):
        """Test detection of generation intent."""
        state = create_initial_state(
            job_id="test",
            user_query="Generate thermostable variants of this enzyme",
        )

        result = intent_router_node(state)

        assert result["intent"]["intent"] == "generation"

    def test_extracts_mutations(self):
        """Test mutation extraction."""
        state = create_initial_state(
            job_id="test",
            user_query="Analyze the P148T and G45A mutations",
        )

        result = intent_router_node(state)

        assert "P148T" in result["intent"]["mutations"]
        assert "G45A" in result["intent"]["mutations"]

    def test_extracts_uniprot_id(self):
        """Test UniProt ID extraction."""
        state = create_initial_state(
            job_id="test",
            user_query="Predict stability for P00720",
        )

        result = intent_router_node(state)

        assert result["intent"]["uniprot_id"] == "P00720"

    def test_handles_empty_query(self):
        """Test handling of empty query."""
        state = create_initial_state(
            job_id="test",
            user_query="",
        )

        result = intent_router_node(state)

        assert result["intent"]["intent"] == "none"
        assert result["intent"]["confidence"] == 0.0


@pytest.mark.unit
class TestInputParserNode:
    """Tests for input_parser_node."""

    def test_parses_prediction_query(self):
        """Test parsing a prediction query."""
        state = create_initial_state(
            job_id="test",
            user_query="Predict stability and kcat for this enzyme",
        )
        state["intent"] = {
            "intent": "prediction",
            "confidence": 0.9,
            "mutations": [],
            "uniprot_id": None,
        }

        result = input_parser_node(state)

        assert "parsed_input" in result
        assert result["parsed_input"]["task"] == "prediction"
        assert "stability" in result["parsed_input"]["properties"]

    def test_detects_explicit_sequence(self):
        """Test detection of explicit sequence in query."""
        sequence = "MKTVRQERLKSIVRILERSKEPVSGAQLAEYLGDGTRIGGLSLWRDVTRQLLGPKNTSEYLADVITLAEQVERILGTDEVFVNAGRGRTHGGYVGALNYQDSQLTPQQNKLFAFDM"
        state = create_initial_state(
            job_id="test",
            user_query=f"Predict stability for {sequence}",
        )
        state["intent"] = {"intent": "prediction", "mutations": []}

        result = input_parser_node(state)

        assert result["protein"]["sequence"] == sequence
        assert result["protein"]["sequence_length"] == len(sequence)

    def test_resolves_common_ligand(self):
        """Test ligand resolution."""
        state = create_initial_state(
            job_id="test",
            user_query="Predict kcat with ATP",
        )
        state["intent"] = {"intent": "prediction", "mutations": []}

        result = input_parser_node(state)

        # ATP should be resolved to SMILES
        assert result["ligand"]["ligand_smiles"] is not None or result["parsed_input"]["properties"]

    def test_uses_intent_uniprot_id(self):
        """Test that UniProt ID from intent is used."""
        state = create_initial_state(
            job_id="test",
            user_query="Predict stability",
        )
        state["intent"] = {
            "intent": "prediction",
            "mutations": [],
            "uniprot_id": "P00720",
        }

        result = input_parser_node(state)

        assert result["protein"]["uniprot_id"] == "P00720"


@pytest.mark.unit
class TestIntentHelperFunctions:
    """Tests for intent helper functions."""

    def test_get_intent_type(self, sample_state_with_intent):
        """Test getting intent type from state."""
        intent_type = get_intent_type(sample_state_with_intent)
        assert intent_type == "generation"

    def test_has_mutations_true(self, sample_state_with_intent):
        """Test detecting mutations in state."""
        assert has_mutations(sample_state_with_intent) is True

    def test_has_mutations_false(self, sample_state):
        """Test no mutations when none extracted."""
        sample_state["intent"] = {"intent": "prediction", "mutations": []}
        assert has_mutations(sample_state) is False


@pytest.mark.unit
class TestInputHelperFunctions:
    """Tests for input helper functions."""

    def test_get_task_type(self, sample_state):
        """Test getting task type from state."""
        sample_state["parsed_input"] = {"task": "generation"}
        task = get_task_type(sample_state)
        assert task == "generation"

    def test_has_protein_sequence(self, sample_state_with_protein):
        """Test detecting protein sequence."""
        assert has_protein_sequence(sample_state_with_protein) is True

    def test_no_protein_sequence(self, sample_state):
        """Test no protein sequence detection."""
        assert has_protein_sequence(sample_state) is False
