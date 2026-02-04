"""
Unit tests for state schema and factory functions.
"""

import pytest

from synde_graph.state.schema import (
    SynDeGraphState,
    IntentResult,
    ParsedInput,
    ProteinData,
    LigandData,
    WorkflowError,
)
from synde_graph.state.factory import (
    create_initial_state,
    add_error,
    update_node_history,
    update_gpu_task,
    merge_state_updates,
    get_protein_sequence,
    has_fatal_error,
)


@pytest.mark.unit
class TestCreateInitialState:
    """Tests for create_initial_state function."""

    def test_creates_valid_state(self):
        """Test that initial state has all required fields."""
        state = create_initial_state(
            job_id="test-123",
            user_query="Predict stability",
        )

        assert state["job_id"] == "test-123"
        assert state["user_query"] == "Predict stability"
        assert state["thread_id"] == "test-123"
        assert state["current_node"] == "start"
        assert state["node_history"] == []
        assert state["errors"] == []

    def test_with_optional_parameters(self):
        """Test state creation with optional parameters."""
        state = create_initial_state(
            job_id="test-456",
            user_query="Generate mutants",
            user_id=42,
            uploaded_pdb_path="/path/to/file.pdb",
            session_data={"last_ligand": "ATP"},
        )

        assert state["user_id"] == 42
        assert state["uploaded_pdb_path"] == "/path/to/file.pdb"
        assert state["session_data"]["last_ligand"] == "ATP"

    def test_initializes_nested_dicts(self):
        """Test that nested TypedDicts are initialized."""
        state = create_initial_state(
            job_id="test-789",
            user_query="Test",
        )

        assert isinstance(state["intent"], dict)
        assert isinstance(state["parsed_input"], dict)
        assert isinstance(state["protein"], dict)
        assert isinstance(state["ligand"], dict)


@pytest.mark.unit
class TestAddError:
    """Tests for add_error function."""

    def test_adds_error_to_state(self, sample_state):
        """Test adding an error to state."""
        error = ValueError("Test error message")
        updates = add_error(sample_state, "test_node", error, recoverable=True)

        assert "errors" in updates
        assert len(updates["errors"]) == 1
        assert updates["errors"][0]["node"] == "test_node"
        assert updates["errors"][0]["error_type"] == "ValueError"
        assert updates["errors"][0]["message"] == "Test error message"
        assert updates["errors"][0]["recoverable"] is True

    def test_includes_traceback(self, sample_state):
        """Test that traceback is captured."""
        try:
            raise RuntimeError("Test runtime error")
        except Exception as e:
            updates = add_error(sample_state, "error_node", e)

        assert "traceback" in updates["errors"][0]
        assert updates["errors"][0]["traceback"] is not None


@pytest.mark.unit
class TestUpdateNodeHistory:
    """Tests for update_node_history function."""

    def test_adds_node_to_history(self, sample_state):
        """Test adding node to history."""
        updates = update_node_history(sample_state, "new_node")

        assert updates["current_node"] == "new_node"
        assert "new_node" in updates["node_history"]

    def test_preserves_existing_history(self, sample_state):
        """Test that existing history is preserved."""
        sample_state["node_history"] = ["node1", "node2"]
        updates = update_node_history(sample_state, "node3")

        assert updates["node_history"] == ["node1", "node2", "node3"]


@pytest.mark.unit
class TestUpdateGpuTask:
    """Tests for update_gpu_task function."""

    def test_adds_new_task(self, sample_state):
        """Test adding a new GPU task."""
        updates = update_gpu_task(
            sample_state,
            task_id="celery-task-123",
            task_name="ESMFold",
            status="pending",
        )

        assert len(updates["active_gpu_tasks"]) == 1
        assert updates["active_gpu_tasks"][0]["task_id"] == "celery-task-123"
        assert updates["active_gpu_tasks"][0]["status"] == "pending"

    def test_updates_existing_task(self, sample_state):
        """Test updating an existing GPU task."""
        sample_state["active_gpu_tasks"] = [{
            "task_id": "task-123",
            "task_name": "ESMFold",
            "status": "pending",
        }]

        updates = update_gpu_task(
            sample_state,
            task_id="task-123",
            task_name="ESMFold",
            status="success",
            result={"pdb_path": "/test.pdb"},
        )

        assert len(updates["active_gpu_tasks"]) == 1
        assert updates["active_gpu_tasks"][0]["status"] == "success"
        assert updates["active_gpu_tasks"][0]["result"]["pdb_path"] == "/test.pdb"


@pytest.mark.unit
class TestMergeStateUpdates:
    """Tests for merge_state_updates function."""

    def test_merges_simple_updates(self):
        """Test merging simple updates."""
        update1 = {"current_node": "node1"}
        update2 = {"response": {"html": "test"}}

        merged = merge_state_updates(update1, update2)

        assert merged["current_node"] == "node1"
        assert merged["response"]["html"] == "test"

    def test_concatenates_errors(self):
        """Test that errors are concatenated."""
        update1 = {"errors": [{"node": "n1", "message": "e1"}]}
        update2 = {"errors": [{"node": "n2", "message": "e2"}]}

        merged = merge_state_updates(update1, update2)

        assert len(merged["errors"]) == 2

    def test_deep_merges_dicts(self):
        """Test deep merging of nested dicts."""
        update1 = {"protein": {"sequence": "MKTVR"}}
        update2 = {"protein": {"pdb_path": "/test.pdb"}}

        merged = merge_state_updates(update1, update2)

        assert merged["protein"]["sequence"] == "MKTVR"
        assert merged["protein"]["pdb_path"] == "/test.pdb"


@pytest.mark.unit
class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_protein_sequence(self, sample_state_with_protein):
        """Test getting protein sequence from state."""
        seq = get_protein_sequence(sample_state_with_protein)
        assert seq is not None
        assert len(seq) > 0

    def test_get_protein_sequence_empty(self, sample_state):
        """Test getting sequence when none exists."""
        seq = get_protein_sequence(sample_state)
        assert seq is None

    def test_has_fatal_error_true(self, sample_state):
        """Test detecting fatal error."""
        sample_state["errors"] = [
            {"node": "test", "message": "fatal", "recoverable": False}
        ]
        assert has_fatal_error(sample_state) is True

    def test_has_fatal_error_false(self, sample_state):
        """Test no fatal error when all recoverable."""
        sample_state["errors"] = [
            {"node": "test", "message": "warning", "recoverable": True}
        ]
        assert has_fatal_error(sample_state) is False
