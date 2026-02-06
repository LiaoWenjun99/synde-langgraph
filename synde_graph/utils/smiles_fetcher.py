"""Ligand name to SMILES resolution via PubChem API."""

import requests
from urllib.parse import quote
from typing import Optional

from synde_graph.utils.live_logger import report


def get_smiles(substrate) -> Optional[str]:
    """
    Resolve a ligand/substrate name to its canonical SMILES string.

    Uses PubChem's PUG REST API for name-to-SMILES lookup.
    Falls back to a hardcoded table for common metabolites.

    Args:
        substrate: Ligand name (str), or list of names (takes first)

    Returns:
        Canonical SMILES string, or None if lookup fails
    """
    # Handle list input
    if isinstance(substrate, (list, tuple)):
        substrate = substrate[0] if substrate else ""
    substrate = str(substrate).strip()
    if not substrate:
        return None

    # Check hardcoded table first (fast, no network)
    smiles = _get_common_ligand_smiles(substrate)
    if smiles:
        return smiles

    # PubChem API lookup
    encoded = quote(substrate)
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound"
        f"/name/{encoded}/property/CanonicalSMILES/TXT"
    )

    try:
        report(f"🔍 Looking up SMILES for '{substrate}' via PubChem...")
        req = requests.get(url, timeout=10)

        if req.status_code != 200 or not len(req.content or b""):
            report(f"⚠️ PubChem lookup failed for '{substrate}' (status={req.status_code})")
            return None

        smiles = req.content.decode().strip()
        if not smiles:
            report(f"⚠️ Empty SMILES returned for '{substrate}'")
            return None

        report(f"✅ Resolved '{substrate}' → SMILES ({len(smiles)} chars)")
        return smiles

    except requests.exceptions.Timeout:
        report(f"⚠️ PubChem request for '{substrate}' timed out")
    except requests.exceptions.RequestException as e:
        report(f"⚠️ PubChem request exception for '{substrate}': {e}")
    except Exception as e:
        report(f"⚠️ Unexpected error fetching SMILES for '{substrate}': {e}")

    return None


def _get_common_ligand_smiles(ligand_name: str) -> Optional[str]:
    """
    Get SMILES for common metabolites/cofactors without API call.

    Args:
        ligand_name: Ligand name

    Returns:
        SMILES string or None
    """
    common_ligands = {
        "ATP": "C1=NC2=C(C(=N1)N)N=CN2C3C(C(C(O3)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)O",
        "ADP": "C1=NC2=C(C(=N1)N)N=CN2C3C(C(C(O3)COP(=O)(O)OP(=O)(O)O)O)O",
        "AMP": "C1=NC2=C(C(=N1)N)N=CN2C3C(C(C(O3)COP(=O)(O)O)O)O",
        "GTP": "C1=NC2=C(N1C3C(C(C(O3)COP(=O)(O)OP(=O)(O)OP(=O)(O)O)O)O)NC(=NC2=O)N",
        "GDP": "C1=NC2=C(N1C3C(C(C(O3)COP(=O)(O)OP(=O)(O)O)O)O)NC(=NC2=O)N",
        "GLUCOSE": "OC[C@H]1OC(O)[C@H](O)[C@@H](O)[C@@H]1O",
        "NADH": "NC(=O)c1ccc[n+](C2OC(COP(=O)(O)OP(=O)(O)OCC3OC(n4cnc5c(N)ncnc54)C(O)C3O)C(O)C2O)c1",
        "NADPH": "NC(=O)c1ccc[n+](C2OC(COP(=O)(O)OP(=O)(O)OCC3OC(n4cnc5c(N)ncnc54)C(OP(=O)(O)O)C3O)C(O)C2O)c1",
        "NAD+": "NC(=O)c1ccc[n+](C2OC(COP(=O)(O)OP(=O)(O)OCC3OC(n4cnc5c(N)ncnc54)C(O)C3O)C(O)C2O)c1",
        "NADP+": "NC(=O)c1ccc[n+](C2OC(COP(=O)(O)OP(=O)(O)OCC3OC(n4cnc5c(N)ncnc54)C(OP(=O)(O)O)C3O)C(O)C2O)c1",
        "FAD": "CC1=CC2=C(C=C1C)N(C3=NC(=O)NC(=O)C3=N2)CC(C(C(COP(=O)(O)OP(=O)(O)OCC4C(C(C(O4)N5C=NC6=C(N=CN=C65)N)O)O)O)O)O",
        "PYRUVATE": "CC(=O)C(=O)O",
        "SUCCINATE": "OC(=O)CCC(=O)O",
        "LACTATE": "CC(O)C(=O)O",
        "CITRATE": "OC(=O)CC(O)(CC(=O)O)C(=O)O",
        "OXALOACETATE": "OC(=O)CC(=O)C(=O)O",
        "FUMARATE": "OC(=O)/C=C/C(=O)O",
        "MALATE": "OC(CC(=O)O)C(=O)O",
        "ACETATE": "CC(=O)O",
        "GLUTAMATE": "NC(CCC(=O)O)C(=O)O",
        "ASPARTATE": "NC(CC(=O)O)C(=O)O",
        "COA": "CC(C)(COP(=O)(O)OP(=O)(O)OCC1C(C(C(O1)N2C=NC3=C(N=CN=C32)N)O)OP(=O)(O)O)C(C(=O)NCCC(=O)NCCS)O",
        "COENZYME A": "CC(C)(COP(=O)(O)OP(=O)(O)OCC1C(C(C(O1)N2C=NC3=C(N=CN=C32)N)O)OP(=O)(O)O)C(C(=O)NCCC(=O)NCCS)O",
        "ACETYL-COA": "CC(=O)SCCNC(=O)CCNC(=O)C(O)C(C)(C)COP(=O)(O)OP(=O)(O)OCC1OC(n2cnc3c(N)ncnc32)C(O)C1OP(=O)(O)O",
    }

    return common_ligands.get(ligand_name.upper())
