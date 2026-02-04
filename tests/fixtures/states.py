"""
Sample states for testing.
"""

from synde_graph.state.schema import (
    SynDeGraphState,
    IntentResult,
    ParsedInput,
    ProteinData,
    LigandData,
)

# Sample sequences
LYSOZYME_SEQUENCE = "MKTVRQERLKSIVRILERSKEPVSGAQLAEYLGDGTRIGGLSLWRDVTRQLLGPKNTSEYLADVITLAEQVERILGTDEVFVNAGRGRTHGGYVGALNYQDSQLTPQQNKLFAFDM"
INSULIN_SEQUENCE = "MALWMRLLPLLALLALWGPDPAAAFVNQHLCGSHLVEALYLVCGERGFFYTPKTRREAEDLQVGQVELGGGPGAGSLQPLALEGSLQKRGIVEQCCTSICSLYQLENYCN"
GFP_SEQUENCE = "MSKGEELFTGVVPILVELDGDVNGHKFSVSGEGEGDATYGKLTLKFICTTGKLPVPWPTLVTTLTYGVQCFSRYPDHMKQHDFFKSAMPEGYVQERTIFFKDDGNYKTRAEVKFEGDTLVNRIELKGIDFKEDGNILGHKLEYNYNSHNVYIMADKQKNGIKVNFKIRHNIEDGSVQLADHYQQNTPIGDGPVLLPDNHYLSTQSALSKDPNEKRDHMVLLEFVTAAGITLGMDELYK"


def create_prediction_state() -> SynDeGraphState:
    """Create a state for prediction testing."""
    return SynDeGraphState(
        job_id="test-prediction",
        user_id=1,
        thread_id="test-prediction",
        user_query="Predict EC number and melting temperature for P00720",
        intent=IntentResult(
            intent="prediction",
            confidence=0.9,
            mutations=[],
            uniprot_id="P00720",
            reason="Prediction query detected",
        ),
        parsed_input=ParsedInput(
            task="prediction",
            properties=["ec_number", "tm"],
            region=[],
            organism=[],
        ),
        protein=ProteinData(
            sequence=LYSOZYME_SEQUENCE,
            sequence_length=len(LYSOZYME_SEQUENCE),
            uniprot_id="P00720",
            structure_source="none",
        ),
        ligand=LigandData(),
        structure={},
        mutant={},
        active_gpu_tasks=[],
        current_node="start",
        node_history=[],
        errors=[],
        response={},
        session_data={},
    )


def create_generation_state() -> SynDeGraphState:
    """Create a state for generation testing."""
    return SynDeGraphState(
        job_id="test-generation",
        user_id=1,
        thread_id="test-generation",
        user_query="Generate thermostable variants optimized for kcat",
        intent=IntentResult(
            intent="generation",
            confidence=0.85,
            mutations=[],
            uniprot_id=None,
            reason="Generation query detected",
        ),
        parsed_input=ParsedInput(
            task="generation",
            properties=["stability", "kcat"],
            region=[],
            organism=[],
        ),
        protein=ProteinData(
            sequence=LYSOZYME_SEQUENCE,
            sequence_length=len(LYSOZYME_SEQUENCE),
            structure_source="none",
        ),
        ligand=LigandData(
            ligand_input="ATP",
            ligand_smiles="C1=NC2=C(C(=N1)N)N=CN2C3C(C(C(O3)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)O",
        ),
        structure={},
        mutant={},
        active_gpu_tasks=[],
        current_node="start",
        node_history=[],
        errors=[],
        response={},
        session_data={},
    )


def create_kcat_prediction_state() -> SynDeGraphState:
    """Create a state for kcat prediction with ligand."""
    return SynDeGraphState(
        job_id="test-kcat",
        user_id=1,
        thread_id="test-kcat",
        user_query="Predict kcat for this enzyme with ATP",
        intent=IntentResult(
            intent="prediction",
            confidence=0.9,
            mutations=[],
            uniprot_id=None,
            reason="kcat prediction detected",
        ),
        parsed_input=ParsedInput(
            task="prediction",
            properties=["kcat"],
            region=[],
            organism=[],
        ),
        protein=ProteinData(
            sequence=LYSOZYME_SEQUENCE,
            sequence_length=len(LYSOZYME_SEQUENCE),
            structure_source="none",
        ),
        ligand=LigandData(
            ligand_input="ATP",
            ligand_smiles="C1=NC2=C(C(=N1)N)N=CN2C3C(C(C(O3)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)O",
        ),
        structure={},
        mutant={},
        active_gpu_tasks=[],
        current_node="start",
        node_history=[],
        errors=[],
        response={},
        session_data={},
    )


def create_mutagenesis_state() -> SynDeGraphState:
    """Create a state for mutagenesis testing."""
    return SynDeGraphState(
        job_id="test-mutagenesis",
        user_id=1,
        thread_id="test-mutagenesis",
        user_query="Analyze the P148T and G45A mutations in P00720",
        intent=IntentResult(
            intent="mutagenesis",
            confidence=0.92,
            mutations=["P148T", "G45A"],
            uniprot_id="P00720",
            reason="Mutagenesis query with explicit mutations",
        ),
        parsed_input=ParsedInput(
            task="mutagenesis",
            properties=["stability", "mutation_effect"],
            region=[],
            organism=[],
        ),
        protein=ProteinData(
            sequence=LYSOZYME_SEQUENCE,
            sequence_length=len(LYSOZYME_SEQUENCE),
            uniprot_id="P00720",
            structure_source="none",
        ),
        ligand=LigandData(),
        structure={},
        mutant={},
        active_gpu_tasks=[],
        current_node="start",
        node_history=[],
        errors=[],
        response={},
        session_data={},
    )
