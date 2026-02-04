"""
CLI tool for testing SynDe LangGraph workflows.

Provides commands for running workflows, testing individual nodes,
and debugging checkpointed states.
"""

import os
import sys
from typing import Optional
from pathlib import Path

import typer
from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

app = typer.Typer(
    name="synde",
    help="SynDe LangGraph CLI - Test protein engineering workflows",
    add_completion=False,
)

console = Console()


@app.command()
def run(
    query: str = typer.Argument(..., help="User query to process"),
    mock: bool = typer.Option(False, "--mock", "-m", help="Run with mock GPU responses"),
    sequence: Optional[str] = typer.Option(None, "--sequence", "-s", help="Protein sequence"),
    uniprot: Optional[str] = typer.Option(None, "--uniprot", "-u", help="UniProt ID"),
    pdb: Optional[str] = typer.Option(None, "--pdb", "-p", help="Path to PDB file"),
    ligand: Optional[str] = typer.Option(None, "--ligand", "-l", help="Ligand name or SMILES"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed output"),
):
    """
    Run a complete SynDe workflow.

    Examples:
        synde run "Predict EC number for P00720" --mock
        synde run "Generate thermostable variants" --sequence "MKTVRQ..." --mock
    """
    # Set mock mode
    if mock:
        os.environ["MOCK_GPU"] = "true"

    from synde_graph.graph import run_workflow
    from synde_cli.display import display_workflow_result

    # Build session data with any provided context
    session_data = {}
    if sequence:
        session_data["last_protein_sequence"] = sequence
    if uniprot:
        session_data["last_uniprot_id"] = uniprot
    if ligand:
        session_data["last_ligand"] = ligand

    # Read PDB file if provided
    pdb_content = None
    if pdb and os.path.exists(pdb):
        with open(pdb, "r") as f:
            pdb_content = f.read()

    console.print(Panel(f"[bold blue]Query:[/bold blue] {query}", title="SynDe Workflow"))

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Running workflow...", total=None)

        result = run_workflow(
            user_query=query,
            uploaded_pdb_path=pdb,
            uploaded_pdb_content=pdb_content,
            session_data=session_data if session_data else None,
        )

        progress.remove_task(task)

    display_workflow_result(result, verbose=verbose)


@app.command("test-node")
def test_node(
    node: str = typer.Argument(..., help="Node name to test"),
    query: str = typer.Option("Test query", "--query", "-q", help="Test query"),
    mock: bool = typer.Option(True, "--mock", "-m", help="Run with mock GPU"),
):
    """
    Test an individual LangGraph node.

    Examples:
        synde test-node intent_router --query "Predict EC number"
        synde test-node input_parser --query "Generate mutants for P00720"
    """
    if mock:
        os.environ["MOCK_GPU"] = "true"

    from synde_graph.state.factory import create_initial_state

    # Import node function dynamically
    node_functions = {
        "intent_router": "synde_graph.nodes.intent:intent_router_node",
        "input_parser": "synde_graph.nodes.input:input_parser_node",
        "check_structure": "synde_graph.nodes.prediction:check_structure_node",
        "run_esmfold": "synde_graph.nodes.prediction:run_esmfold_node",
        "run_clean_ec": "synde_graph.nodes.prediction:run_clean_ec_node",
        "run_temberture": "synde_graph.nodes.prediction:run_temberture_node",
        "response_formatter": "synde_graph.nodes.response:response_formatter_node",
        "fallback_response": "synde_graph.nodes.response:fallback_response_node",
    }

    if node not in node_functions:
        console.print(f"[red]Unknown node: {node}[/red]")
        console.print(f"Available nodes: {', '.join(node_functions.keys())}")
        raise typer.Exit(1)

    # Import the node function
    module_path, func_name = node_functions[node].split(":")
    import importlib
    module = importlib.import_module(module_path)
    node_func = getattr(module, func_name)

    # Create initial state
    state = create_initial_state(
        job_id="test-node",
        user_query=query,
    )

    console.print(Panel(f"Testing node: [bold]{node}[/bold]", title="Node Test"))

    result = node_func(state)

    # Display result
    table = Table(title=f"Node Output: {node}")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    for key, value in result.items():
        if isinstance(value, dict):
            value_str = str(value)[:100] + "..." if len(str(value)) > 100 else str(value)
        elif isinstance(value, list):
            value_str = f"[{len(value)} items]"
        else:
            value_str = str(value)
        table.add_row(key, value_str)

    console.print(table)


@app.command()
def debug(
    job_id: str = typer.Argument(..., help="Job ID to debug"),
    checkpoint_db: Optional[str] = typer.Option(None, "--checkpoint", "-c", help="Checkpoint database path"),
):
    """
    Debug a checkpointed workflow state.

    Examples:
        synde debug job-123 --checkpoint ./test.db
    """
    console.print(f"[yellow]Debug mode for job: {job_id}[/yellow]")

    if checkpoint_db and os.path.exists(checkpoint_db):
        console.print(f"Loading checkpoint from: {checkpoint_db}")
        # TODO: Implement checkpoint loading
        console.print("[yellow]Checkpoint loading not yet implemented[/yellow]")
    else:
        console.print("[red]No checkpoint database found[/red]")


@app.command()
def list_nodes():
    """List all available workflow nodes."""
    nodes = [
        ("intent_router", "Detects user intent from query"),
        ("input_parser", "Parses input and extracts protein/ligand data"),
        ("check_structure", "Checks if structure prediction needed"),
        ("run_esmfold", "Runs ESMFold structure prediction"),
        ("run_alphafold", "Runs AlphaFold structure prediction"),
        ("run_fpocket", "Detects binding pockets"),
        ("run_foldx", "Predicts stability"),
        ("run_tomer", "Predicts optimum temperature"),
        ("run_clean_ec", "Predicts EC number"),
        ("run_deepenzyme", "Predicts kcat"),
        ("run_temberture", "Predicts melting temperature"),
        ("aggregate_results", "Aggregates prediction results"),
        ("prepare_wt_metrics", "Prepares wild-type metrics"),
        ("run_progen2", "Generates mutants with ProGen2"),
        ("run_zymctrl", "Generates sequences with ZymCTRL"),
        ("validate_mutants", "Validates generated mutants"),
        ("evaluate_mutants", "Evaluates mutant properties"),
        ("sort_mutants", "Ranks mutants by target properties"),
        ("response_formatter", "Formats final response"),
        ("fallback_response", "Handles unclear intents"),
        ("error_response", "Handles workflow errors"),
    ]

    table = Table(title="Available Workflow Nodes")
    table.add_column("Node", style="cyan")
    table.add_column("Description", style="green")

    for name, desc in nodes:
        table.add_row(name, desc)

    console.print(table)


@app.command()
def version():
    """Show version information."""
    from synde_graph import __version__

    console.print(f"synde-langgraph version: [bold]{__version__}[/bold]")


@app.command()
def check():
    """Check environment and dependencies."""
    console.print(Panel("Environment Check", title="SynDe"))

    checks = []

    # Check Python version
    import sys
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    checks.append(("Python", py_version, sys.version_info >= (3, 10)))

    # Check required packages
    packages = ["langgraph", "celery", "redis", "typer", "rich"]
    for pkg in packages:
        try:
            __import__(pkg)
            checks.append((pkg, "installed", True))
        except ImportError:
            checks.append((pkg, "missing", False))

    # Check environment variables
    env_vars = ["REDIS_HOST", "CELERY_BROKER_URL", "MOCK_GPU"]
    for var in env_vars:
        value = os.environ.get(var, "not set")
        checks.append((f"${var}", value[:30], value != "not set"))

    # Display results
    table = Table(title="Environment Status")
    table.add_column("Check", style="cyan")
    table.add_column("Value", style="white")
    table.add_column("Status", style="green")

    for name, value, ok in checks:
        status = "[green]OK[/green]" if ok else "[red]FAIL[/red]"
        table.add_row(name, str(value), status)

    console.print(table)


if __name__ == "__main__":
    app()
