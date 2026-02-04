#!/usr/bin/env python3
"""
Run SynDe workflow with mock GPU responses.

This script is useful for testing the LangGraph workflow without
requiring actual GPU resources.

Usage:
    python scripts/run_mock.py "Predict EC number for P00720"
    python scripts/run_mock.py "Generate thermostable variants" --sequence "MKTVRQ..."
"""

import os
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# Enable mock mode
os.environ["MOCK_GPU"] = "true"


def main():
    import argparse
    from rich.console import Console
    from rich.panel import Panel

    from synde_graph.graph import run_workflow
    from synde_cli.display import display_workflow_result

    parser = argparse.ArgumentParser(description="Run SynDe workflow with mock GPU")
    parser.add_argument("query", help="User query to process")
    parser.add_argument("--sequence", "-s", help="Protein sequence")
    parser.add_argument("--uniprot", "-u", help="UniProt ID")
    parser.add_argument("--ligand", "-l", help="Ligand name or SMILES")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")

    args = parser.parse_args()

    console = Console()

    # Build session data
    session_data = {}
    if args.sequence:
        session_data["last_protein_sequence"] = args.sequence
    if args.uniprot:
        session_data["last_uniprot_id"] = args.uniprot
    if args.ligand:
        session_data["last_ligand"] = args.ligand

    console.print(Panel(
        f"[bold blue]Query:[/bold blue] {args.query}\n"
        f"[bold]Mode:[/bold] Mock GPU",
        title="SynDe Workflow"
    ))

    result = run_workflow(
        user_query=args.query,
        session_data=session_data if session_data else None,
    )

    display_workflow_result(result, verbose=args.verbose)


if __name__ == "__main__":
    main()
