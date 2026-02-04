"""
Pytest configuration and fixtures for LangGraph tests.
"""

import os
import sys
import pytest

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

# Enable mock mode for testing
os.environ["MOCK_GPU"] = "true"


@pytest.fixture(scope="session", autouse=True)
def setup_mock_mode():
    """Enable mock mode for all tests."""
    os.environ["MOCK_GPU"] = "true"
    yield
    # Cleanup if needed


@pytest.fixture
def sample_state():
    """Create a sample initial state for testing."""
    from synde_graph.state.factory import create_initial_state

    return create_initial_state(
        job_id="test-fixture-job",
        user_query="Predict stability for P00720",
        user_id=1,
    )


@pytest.fixture
def sample_state_with_protein():
    """Create a sample state with protein data."""
    from synde_graph.state.factory import create_initial_state

    state = create_initial_state(
        job_id="test-protein-job",
        user_query="Predict stability",
        user_id=1,
    )
    state["protein"] = {
        "sequence": "MKTVRQERLKSIVRILERSKEPVSGAQLAEYLGDGTRIGGLSLWRDVTRQLLGPKNTSEYLADVITLAEQVERILGTDEVFVNAGRGRTHGGYVGALNYQDSQLTPQQNKLFAFDM",
        "sequence_length": 115,
        "uniprot_id": "P00720",
        "structure_source": "uniprot",
    }
    return state


@pytest.fixture
def sample_state_with_intent():
    """Create a sample state with intent result."""
    from synde_graph.state.factory import create_initial_state

    state = create_initial_state(
        job_id="test-intent-job",
        user_query="Generate thermostable mutants",
    )
    state["intent"] = {
        "intent": "generation",
        "confidence": 0.92,
        "mutations": ["P148T"],
        "uniprot_id": "P00720",
        "reason": "User wants mutant generation",
    }
    return state


@pytest.fixture
def sample_state_with_ligand():
    """Create a sample state with ligand data."""
    from synde_graph.state.factory import create_initial_state

    state = create_initial_state(
        job_id="test-ligand-job",
        user_query="Predict kcat with ATP",
    )
    state["ligand"] = {
        "ligand_input": "ATP",
        "ligand_smiles": "C1=NC2=C(C(=N1)N)N=CN2C3C(C(C(O3)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)O",
    }
    return state


@pytest.fixture
def sample_sequence():
    """Sample lysozyme sequence for testing."""
    return "MKTVRQERLKSIVRILERSKEPVSGAQLAEYLGDGTRIGGLSLWRDVTRQLLGPKNTSEYLADVITLAEQVERILGTDEVFVNAGRGRTHGGYVGALNYQDSQLTPQQNKLFAFDM"


@pytest.fixture
def sample_pdb_content():
    """Sample PDB content for testing."""
    return """HEADER    TEST PROTEIN
ATOM      1  N   MET A   1      10.000  10.000  10.000  1.00 80.00           N
ATOM      2  CA  MET A   1      11.458  10.000  10.000  1.00 80.00           C
ATOM      3  C   MET A   1      12.009  11.420  10.000  1.00 80.00           C
ATOM      4  O   MET A   1      11.251  12.400  10.000  1.00 80.00           O
ATOM      5  N   LYS A   2      13.288  11.515   0.346  1.00 82.00           N
ATOM      6  CA  LYS A   2      13.938  12.816   0.440  1.00 82.00           C
ATOM      7  C   LYS A   2      13.558  13.699  -0.752  1.00 82.00           C
ATOM      8  O   LYS A   2      13.831  14.896  -0.734  1.00 82.00           O
END
"""


@pytest.fixture
def temp_pdb_file(tmp_path, sample_pdb_content):
    """Create a temporary PDB file for testing."""
    pdb_file = tmp_path / "test_structure.pdb"
    pdb_file.write_text(sample_pdb_content)
    return str(pdb_file)


# Markers for test categories
def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests (fast, no external deps)")
    config.addinivalue_line("markers", "integration: Integration tests (may use mocks)")
    config.addinivalue_line("markers", "slow: Slow tests (GPU, network calls)")
    config.addinivalue_line("markers", "requires_redis: Tests that need Redis")
