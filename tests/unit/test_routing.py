"""
Unit tests for routing functions.
"""

import pytest

from synde_graph.routing.routes import (
    route_by_intent,
    route_by_task,
    route_structure_prediction,
    needs_structure,
    get_property_nodes,
    should_run_property,
    route_after_progen2,
    route_after_validation,
    has_fatal_error,
    INTENT_ROUTES,
    PROPERTY_NODE_MAP,
)
from synde_graph.state.factory import create_initial_state


@pytest.mark.unit
class TestRouteByIntent:
    """Tests for route_by_intent function."""

    def test_routes_prediction_intent(self):
        """Test routing for prediction intent."""
        state = create_initial_state(job_id="test", user_query="predict")
        state["intent"] = {"intent": "prediction", "mutations": []}

        result = route_by_intent(state)
        assert result == "prediction_subgraph"

    def test_routes_generation_intent(self):
        """Test routing for generation intent."""
        state = create_initial_state(job_id="test", user_query="generate")
        state["intent"] = {"intent": "generation", "mutations": []}

        result = route_by_intent(state)
        assert result == "generation_subgraph"

    def test_routes_theory_intent(self):
        """Test routing for theory intent."""
        state = create_initial_state(job_id="test", user_query="explain")
        state["intent"] = {"intent": "theory", "mutations": []}

        result = route_by_intent(state)
        assert result == "theory_response"

    def test_fallback_with_sequence(self):
        """Test fallback to prediction when sequence available."""
        state = create_initial_state(job_id="test", user_query="unknown")
        state["intent"] = {"intent": "none", "mutations": []}
        state["protein"] = {"sequence": "MKTVRQ"}

        result = route_by_intent(state)
        assert result == "prediction_subgraph"

    def test_fallback_without_sequence(self):
        """Test fallback response when no sequence."""
        state = create_initial_state(job_id="test", user_query="hello")
        state["intent"] = {"intent": "none", "mutations": []}

        result = route_by_intent(state)
        assert result == "fallback_response"


@pytest.mark.unit
class TestRouteStructurePrediction:
    """Tests for route_structure_prediction function."""

    def test_routes_to_fpocket_if_pdb_exists(self):
        """Test routing to fpocket when PDB exists."""
        state = create_initial_state(job_id="test", user_query="test")
        state["protein"] = {
            "sequence": "MKTVRQ",
            "sequence_length": 6,
            "pdb_file_path": "/path/to/structure.pdb",
        }

        result = route_structure_prediction(state)
        assert result == "run_fpocket"

    def test_routes_to_esmfold_short_sequence(self):
        """Test routing to ESMFold for short sequences."""
        state = create_initial_state(job_id="test", user_query="test")
        state["protein"] = {
            "sequence": "M" * 300,
            "sequence_length": 300,
        }

        result = route_structure_prediction(state)
        assert result == "run_esmfold"

    def test_routes_to_alphafold_long_sequence(self):
        """Test routing to AlphaFold for long sequences."""
        state = create_initial_state(job_id="test", user_query="test")
        state["protein"] = {
            "sequence": "M" * 500,
            "sequence_length": 500,
        }

        result = route_structure_prediction(state)
        assert result == "run_alphafold"


@pytest.mark.unit
class TestNeedsStructure:
    """Tests for needs_structure function."""

    def test_needs_structure_true(self):
        """Test that structure is needed when no PDB."""
        state = create_initial_state(job_id="test", user_query="test")
        state["protein"] = {"sequence": "MKTVRQ"}

        assert needs_structure(state) is True

    def test_needs_structure_false(self):
        """Test that structure not needed when PDB exists."""
        state = create_initial_state(job_id="test", user_query="test")
        state["protein"] = {
            "sequence": "MKTVRQ",
            "pdb_file_path": "/path/to/file.pdb",
        }

        assert needs_structure(state) is False


@pytest.mark.unit
class TestGetPropertyNodes:
    """Tests for get_property_nodes function."""

    def test_returns_stability_node(self):
        """Test that stability maps to run_foldx."""
        state = create_initial_state(job_id="test", user_query="test")
        state["parsed_input"] = {"properties": ["stability"]}
        state["ligand"] = {}

        nodes = get_property_nodes(state)
        assert "run_foldx" in nodes

    def test_returns_ec_node(self):
        """Test that ec_number maps to run_clean_ec."""
        state = create_initial_state(job_id="test", user_query="test")
        state["parsed_input"] = {"properties": ["ec_number"]}
        state["ligand"] = {}

        nodes = get_property_nodes(state)
        assert "run_clean_ec" in nodes

    def test_kcat_requires_ligand(self):
        """Test that kcat only included with ligand."""
        state = create_initial_state(job_id="test", user_query="test")
        state["parsed_input"] = {"properties": ["kcat"]}
        state["ligand"] = {}

        nodes = get_property_nodes(state)
        assert "run_deepenzyme" not in nodes

        state["ligand"] = {"ligand_smiles": "CC"}
        nodes = get_property_nodes(state)
        assert "run_deepenzyme" in nodes

    def test_removes_duplicates(self):
        """Test that duplicate nodes are removed."""
        state = create_initial_state(job_id="test", user_query="test")
        state["parsed_input"] = {"properties": ["stability", "mutation_effect"]}
        state["ligand"] = {}

        nodes = get_property_nodes(state)
        assert nodes.count("run_foldx") == 1


@pytest.mark.unit
class TestShouldRunProperty:
    """Tests for should_run_property function."""

    def test_should_run_when_in_list(self):
        """Test that property runs when in list."""
        state = create_initial_state(job_id="test", user_query="test")
        state["parsed_input"] = {"properties": ["stability", "kcat"]}

        assert should_run_property(state, "stability") is True
        assert should_run_property(state, "kcat") is True

    def test_should_not_run_when_absent(self):
        """Test that property doesn't run when not in list."""
        state = create_initial_state(job_id="test", user_query="test")
        state["parsed_input"] = {"properties": ["stability"]}

        assert should_run_property(state, "tm") is False


@pytest.mark.unit
class TestGenerationRouting:
    """Tests for generation workflow routing."""

    def test_route_after_progen2_with_mutants(self):
        """Test routing after ProGen2 with mutants."""
        state = create_initial_state(job_id="test", user_query="test")
        state["session_data"] = {"progen2_mutants": [{"seq": "MKTVR"}]}

        result = route_after_progen2(state)
        assert result == "validate_mutants"

    def test_route_after_progen2_no_mutants(self):
        """Test routing after ProGen2 without mutants."""
        state = create_initial_state(job_id="test", user_query="test")
        state["session_data"] = {}

        result = route_after_progen2(state)
        assert result == "end_generation"

    def test_route_after_validation_with_ec(self):
        """Test routing after validation with EC number."""
        state = create_initial_state(job_id="test", user_query="test")
        state["session_data"] = {"wt_ec_number": "3.2.1.17"}

        result = route_after_validation(state)
        assert result == "run_zymctrl"

    def test_route_after_validation_no_ec(self):
        """Test routing after validation without EC number."""
        state = create_initial_state(job_id="test", user_query="test")
        state["session_data"] = {}

        result = route_after_validation(state)
        assert result == "evaluate_mutants"


@pytest.mark.unit
class TestErrorRouting:
    """Tests for error handling routing."""

    def test_has_fatal_error_true(self):
        """Test detecting fatal error."""
        state = create_initial_state(job_id="test", user_query="test")
        state["errors"] = [
            {"node": "test", "message": "fatal", "recoverable": False}
        ]

        assert has_fatal_error(state) is True

    def test_has_fatal_error_false_recoverable(self):
        """Test no fatal error with recoverable errors."""
        state = create_initial_state(job_id="test", user_query="test")
        state["errors"] = [
            {"node": "test", "message": "warning", "recoverable": True}
        ]

        assert has_fatal_error(state) is False

    def test_has_fatal_error_false_empty(self):
        """Test no fatal error when no errors."""
        state = create_initial_state(job_id="test", user_query="test")
        state["errors"] = []

        assert has_fatal_error(state) is False
