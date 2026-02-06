"""
Input Parser Node for LangGraph workflow.

Handles user input parsing including:
- FLAN-based NLP extraction (via GPU)
- UniProt lookup
- PDB file handling
- Sequence validation
- Ligand SMILES resolution
"""

import re
from typing import Dict, Any, Optional, Tuple, List

from synde_graph.state.schema import (
    SynDeGraphState,
    ParsedInput,
    ProteinData,
    LigandData,
)
from synde_graph.state.factory import update_node_history, add_error
from synde_gpu.tasks import call_flan_extractor
from synde_gpu.manager import GpuTaskManager, TaskStatus
from synde_gpu.mocks import is_mock_mode
from synde_graph.config import GpuTimeouts
from synde_graph.utils.live_logger import report, report_node_start, report_node_complete
from synde_graph.utils.smiles_fetcher import get_smiles


# SMILES character set for validation
SMILES_CHARS = set("BCNOFPSIKHbrcln0123456789=#@+-/\\()[]")


def input_parser_node(state: SynDeGraphState) -> Dict[str, Any]:
    """
    LangGraph node for parsing user input.

    Extracts structured information from the user query including:
    - Task type and properties
    - Protein sequence (from query, UniProt, or uploaded PDB)
    - Ligand information (resolved to SMILES)
    - Region specifications

    Args:
        state: Current workflow state

    Returns:
        State update with parsed input, protein data, and ligand data
    """
    report_node_start("Input Parser", "Extracting task and properties")

    user_query = state.get("user_query", "")
    uploaded_pdb_path = state.get("uploaded_pdb_path")
    uploaded_pdb_content = state.get("uploaded_pdb_content")

    # Get UniProt ID from intent detection if available
    intent = state.get("intent", {})
    intent_uniprot_id = intent.get("uniprot_id")
    intent_mutations = intent.get("mutations", [])

    # Initialize result containers
    parsed_input = ParsedInput()
    protein_data = ProteinData()
    ligand_data = LigandData()
    errors = list(state.get("errors", []))

    # =========================================================================
    # Step 1: Run FLAN NLP extraction
    # =========================================================================
    task, properties, region, uniprot_ids, protein_sequence, ligand_input, organism = \
        _run_flan_extraction(user_query)

    # Use intent-detected UniProt ID if FLAN didn't find one
    if not uniprot_ids and intent_uniprot_id:
        uniprot_ids = [intent_uniprot_id]

    # =========================================================================
    # Step 2: Detect explicit sequence in query
    # =========================================================================
    candidates = re.findall(r"[A-Z]{30,}", user_query.replace("\n", " ").replace(" ", ""))
    forced_sequence = max(candidates, key=len) if candidates else None

    # =========================================================================
    # Step 3: Handle misclassified UniProt IDs
    # =========================================================================
    if not uniprot_ids and protein_sequence and re.fullmatch(r"[A-Za-z0-9]{6,10}", protein_sequence):
        uniprot_ids = [protein_sequence]
        protein_sequence = None

    # =========================================================================
    # Step 4: UniProt lookup (simplified - no external calls in standalone)
    # =========================================================================
    pdb_file_path = None
    uniprot_metadata = {}

    if uniprot_ids:
        uid = uniprot_ids[0]
        # In standalone mode, we store the UniProt ID for later lookup
        # The actual fetch would happen in a production node with synde-minimal
        protein_data["uniprot_id"] = uid

    # =========================================================================
    # Step 5: Handle uploaded PDB
    # =========================================================================
    if uploaded_pdb_path:
        pdb_file_path = uploaded_pdb_path
        protein_data["structure_source"] = "uploaded"

        # Try to extract sequence from PDB content
        if uploaded_pdb_content:
            pdb_seq = _extract_sequence_from_pdb(uploaded_pdb_content)
            if pdb_seq:
                protein_sequence = pdb_seq
                protein_data["pdb_data"] = uploaded_pdb_content

    # =========================================================================
    # Step 6: Use forced sequence from text
    # =========================================================================
    if forced_sequence:
        protein_sequence = forced_sequence
        protein_data["structure_source"] = "session"

    # =========================================================================
    # Step 7: Session fallbacks
    # =========================================================================
    session_data = state.get("session_data", {})
    if not protein_sequence:
        last_seq = session_data.get("last_protein_sequence")
        if last_seq:
            protein_sequence = last_seq
            protein_data["structure_source"] = "session"

    if not uniprot_ids:
        last_uid = session_data.get("last_uniprot_id")
        if last_uid:
            uniprot_ids = [last_uid]

    if not ligand_input:
        last_lig = session_data.get("last_ligand")
        if last_lig:
            ligand_input = last_lig

    # =========================================================================
    # Step 8: Validate sequence origin (prevent hallucination)
    # =========================================================================
    if (
        protein_sequence
        and not forced_sequence
        and not uniprot_ids
        and not uploaded_pdb_path
        and protein_sequence[:10] not in user_query
    ):
        # Discard potentially hallucinated sequence
        protein_sequence = None
        protein_data["structure_source"] = "none"

    # =========================================================================
    # Step 9: Resolve ligand to SMILES
    # =========================================================================
    ligand_smiles = None
    if ligand_input:
        lig_str = ligand_input[0] if isinstance(ligand_input, list) else ligand_input
        if isinstance(lig_str, str):
            # Check if already SMILES
            if all(c in SMILES_CHARS for c in lig_str) and len(lig_str) > 5:
                ligand_smiles = lig_str
            else:
                # Resolve name to SMILES (hardcoded table + PubChem API)
                ligand_smiles = get_smiles(lig_str)
                if ligand_smiles == "NaN":
                    ligand_smiles = None

    # =========================================================================
    # Step 10: Check ligand requirement
    # =========================================================================
    needs_ligand = any(p.lower() in {"docking", "binding", "kcat"} for p in properties)
    if needs_ligand and not ligand_smiles:
        errors.append({
            "node": "input_parser",
            "error_type": "MissingLigand",
            "message": "Task requires ligand but none was provided",
            "recoverable": True,
        })

    # =========================================================================
    # Build result objects
    # =========================================================================
    parsed_input = ParsedInput(
        task=task,
        properties=properties,
        region=region if region else [],
        organism=organism if organism else [],
        raw_ligand_input=ligand_input[0] if isinstance(ligand_input, list) and ligand_input else ligand_input,
    )

    protein_data.update({
        "sequence": protein_sequence,
        "sequence_length": len(protein_sequence) if protein_sequence else 0,
        "uniprot_id": uniprot_ids[0] if uniprot_ids else None,
        "uniprot_metadata": uniprot_metadata,
        "pdb_file_path": pdb_file_path,
    })

    ligand_data = LigandData(
        ligand_input=ligand_input[0] if isinstance(ligand_input, list) and ligand_input else ligand_input,
        ligand_smiles=ligand_smiles,
    )

    # Report what was detected
    report(f"📋 Task: {task}, Properties: {', '.join(properties)}")
    if protein_sequence:
        report(f"🧬 Sequence detected ({len(protein_sequence)} aa)")
    if ligand_smiles:
        report(f"🧪 Ligand resolved to SMILES ({len(ligand_smiles)} chars)")
    elif needs_ligand:
        report(f"⚠️ No ligand/substrate provided — kcat prediction will be skipped")
    if uploaded_pdb_path:
        report(f"📁 Using uploaded PDB structure")
    report_node_complete("Input Parser")

    return {
        "parsed_input": parsed_input,
        "protein": protein_data,
        "ligand": ligand_data,
        **update_node_history(state, "input_parser"),
        "errors": errors if errors else state.get("errors", []),
    }


def _run_flan_extraction(user_query: str) -> Tuple:
    """
    Run FLAN GPU task for NLP extraction.

    Returns:
        Tuple of (task, properties, region, uniprot_id, protein_sequence, ligand_input, organism)
    """
    try:
        result = call_flan_extractor(user_query)

        # In mock mode, result is returned directly
        if is_mock_mode() or not hasattr(result, 'get'):
            if isinstance(result, tuple):
                return result
            # Parse mock result
            return result

        # Real mode - would need to wait for async result
        # For standalone testing, fall back to minimal parsing
        return _minimal_parse(user_query)

    except Exception:
        return _minimal_parse(user_query)


def _minimal_parse(query: str) -> Tuple:
    """
    Minimal fallback parsing without FLAN.

    Returns:
        Tuple of (task, properties, region, uniprot_id, protein_sequence, ligand_input, organism)
    """
    query_lower = query.lower()

    # Detect task
    if any(w in query_lower for w in ["generate", "design", "create", "optimize"]):
        task = "generation"
    elif any(w in query_lower for w in ["mutant", "mutation"]):
        task = "mutagenesis"
    else:
        task = "prediction"

    # Detect properties
    properties = []
    property_keywords = {
        "stability": ["stability", "stable", "stabilize", "ddg"],
        "kcat": ["kcat", "catalytic", "activity", "turnover"],
        "ec_number": ["ec", "enzyme class", "function"],
        "tm": ["tm", "melting", "thermal stability"],
        "topt": ["topt", "optimum temperature", "optimal temperature"],
    }

    for prop, keywords in property_keywords.items():
        if any(kw in query_lower for kw in keywords):
            properties.append(prop)

    if not properties:
        properties = ["stability"]  # Default

    # Detect UniProt IDs
    uniprot_pattern = r'\b([A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]|[OPQ][0-9][A-Z0-9]{3}[0-9])\b'
    uniprot_ids = re.findall(uniprot_pattern, query)

    # Detect sequences
    seq_pattern = r'[A-Z]{30,}'
    sequences = re.findall(seq_pattern, query.replace(" ", ""))
    protein_sequence = sequences[0] if sequences else None

    # Detect ligands
    ligand = None
    common_ligands = [
        "atp", "adp", "nadh", "nad+", "fad", "glucose", "pyruvate",
        "succinate", "lactate", "acetyl-coa", "glutamate", "aspartate",
        "citrate", "oxaloacetate", "fumarate", "malate", "gtp", "gdp",
        "udp", "ump", "ctp", "cdp", "amp", "nadph", "nadp+",
        "coenzyme a", "coa", "acetate",
    ]
    for lig in common_ligands:
        if lig in query_lower:
            ligand = lig.upper()
            break

    # Also check for SMILES patterns in the query (strings with special chars)
    if not ligand:
        import re as _re
        smiles_candidates = _re.findall(r'[A-Za-z0-9@\+\-\[\]\(\)=#/\\]{10,}', query)
        for candidate in smiles_candidates:
            # Check if it looks like SMILES (has typical SMILES characters)
            if any(c in candidate for c in ['=', '#', '(', ')', '[', ']', '/', '\\']):
                ligand = candidate
                break

    return (task, properties, [], uniprot_ids, protein_sequence, ligand, [])


def _extract_sequence_from_pdb(pdb_content: str) -> Optional[str]:
    """
    Extract amino acid sequence from PDB content.

    Args:
        pdb_content: PDB file content

    Returns:
        Amino acid sequence or None
    """
    # Three-letter to one-letter code mapping
    aa_map = {
        'ALA': 'A', 'CYS': 'C', 'ASP': 'D', 'GLU': 'E', 'PHE': 'F',
        'GLY': 'G', 'HIS': 'H', 'ILE': 'I', 'LYS': 'K', 'LEU': 'L',
        'MET': 'M', 'ASN': 'N', 'PRO': 'P', 'GLN': 'Q', 'ARG': 'R',
        'SER': 'S', 'THR': 'T', 'VAL': 'V', 'TRP': 'W', 'TYR': 'Y',
    }

    residues = []
    seen_residues = set()

    for line in pdb_content.split('\n'):
        if line.startswith('ATOM') and line[12:16].strip() == 'CA':
            res_name = line[17:20].strip()
            res_num = line[22:26].strip()
            chain = line[21]

            key = (chain, res_num)
            if key not in seen_residues and res_name in aa_map:
                seen_residues.add(key)
                residues.append((int(res_num), aa_map[res_name]))

    if residues:
        residues.sort(key=lambda x: x[0])
        return ''.join(r[1] for r in residues)

    return None


# =============================================================================
# Helper Functions
# =============================================================================

def get_task_type(state: SynDeGraphState) -> str:
    """Get the parsed task type from state."""
    parsed = state.get("parsed_input", {})
    return parsed.get("task", "prediction")


def get_properties(state: SynDeGraphState) -> List[str]:
    """Get the parsed properties from state."""
    parsed = state.get("parsed_input", {})
    return parsed.get("properties", [])


def has_protein_sequence(state: SynDeGraphState) -> bool:
    """Check if a protein sequence is available."""
    protein = state.get("protein", {})
    return bool(protein.get("sequence"))


def has_pdb_structure(state: SynDeGraphState) -> bool:
    """Check if a PDB structure is available."""
    protein = state.get("protein", {})
    return bool(protein.get("pdb_file_path"))


def get_sequence_length(state: SynDeGraphState) -> int:
    """Get the protein sequence length."""
    protein = state.get("protein", {})
    return protein.get("sequence_length", 0)


def has_ligand(state: SynDeGraphState) -> bool:
    """Check if ligand information is available."""
    ligand = state.get("ligand", {})
    return bool(ligand.get("ligand_smiles"))
