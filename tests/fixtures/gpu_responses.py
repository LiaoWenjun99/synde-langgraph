"""
Mock GPU responses for testing.
"""

# Sample ESMFold response
ESMFOLD_SUCCESS = {
    "status": "success",
    "pdb_path": "/mock/esmfold/test.pdb",
    "pdb_data": """HEADER    MOCK STRUCTURE
ATOM      1  N   MET A   1      0.000   0.000   0.000  1.00 85.00           N
ATOM      2  CA  MET A   1      1.458   0.000   0.000  1.00 85.00           C
END
""",
    "avg_plddt": 85.5,
    "runtime_sec": 12.3,
}

ESMFOLD_FAILURE = {
    "status": "error",
    "message": "CUDA out of memory",
    "runtime_sec": 2.1,
}

# Sample CLEAN EC response
CLEAN_EC_SUCCESS = {
    "status": "success",
    "ec_number": "3.2.1.17",
    "probability": 0.945,
    "runtime_sec": 5.2,
}

CLEAN_EC_FAILURE = {
    "status": "error",
    "message": "Model inference failed",
    "runtime_sec": 1.5,
}

# Sample DeepEnzyme response
DEEPENZYME_SUCCESS = {
    "status": "success",
    "kcat": 125.7,
    "log_kcat": 2.1,
    "runtime_sec": 8.4,
}

DEEPENZYME_FAILURE = {
    "status": "error",
    "message": "Invalid SMILES string",
    "runtime_sec": 0.5,
}

# Sample TemBERTure response
TEMBERTURE_SUCCESS = {
    "status": "success",
    "melting_temperature": 62.5,
    "thermo_class": "mesophilic",
    "runtime_sec": 3.7,
}

TEMBERTURE_FAILURE = {
    "status": "error",
    "message": "Sequence too short",
    "runtime_sec": 0.3,
}

# Sample FLAN extraction response
FLAN_PREDICTION = (
    "prediction",  # task
    ["stability", "ec_number"],  # properties
    [],  # region
    ["P00720"],  # uniprot_ids
    None,  # protein_sequence
    None,  # ligand
    [],  # organism
)

FLAN_GENERATION = (
    "generation",
    ["kcat", "stability"],
    [],
    [],
    "MKTVRQERLKSIVRILERSKEPVSGAQLAEYLGDGTRIGGLSLWRDVTRQLL",
    "ATP",
    [],
)

FLAN_EMPTY = (
    "prediction",
    [],
    [],
    [],
    None,
    None,
    [],
)

# Sample Fpocket response
FPOCKET_SUCCESS = {
    "status": "success",
    "pockets_dir": "/mock/fpocket/pockets",
    "pocket_residues": {
        1: ["A:45", "A:46", "A:47", "A:50", "A:52"],
        2: ["A:100", "A:102", "A:105", "A:108"],
        3: ["A:75", "A:78", "A:80"],
    },
    "pocket_scores": [
        {"pocket_id": 1, "score": 0.85, "druggability_score": 0.78, "volume": 324.5},
        {"pocket_id": 2, "score": 0.72, "druggability_score": 0.65, "volume": 256.2},
        {"pocket_id": 3, "score": 0.58, "druggability_score": 0.52, "volume": 189.7},
    ],
    "runtime_sec": 15.2,
}

FPOCKET_NO_POCKETS = {
    "status": "success",
    "pockets_dir": "/mock/fpocket/pockets",
    "pocket_residues": {},
    "pocket_scores": [],
    "runtime_sec": 10.5,
}
