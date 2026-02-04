"""
Rich console output utilities for CLI.
"""

from typing import Dict, Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.tree import Tree

console = Console()


def display_workflow_result(result: Dict[str, Any], verbose: bool = False):
    """
    Display workflow result in a formatted way.

    Args:
        result: Workflow result state
        verbose: Show detailed output
    """
    # Extract key information
    response = result.get("response", {})
    protein = result.get("protein", {})
    intent = result.get("intent", {})
    parsed = result.get("parsed_input", {})
    errors = result.get("errors", [])
    history = result.get("node_history", [])

    # Display intent and task
    console.print()
    console.print(Panel(
        f"[bold]Intent:[/bold] {intent.get('intent', 'unknown')} "
        f"(confidence: {intent.get('confidence', 0):.2f})\n"
        f"[bold]Task:[/bold] {parsed.get('task', 'unknown')}\n"
        f"[bold]Properties:[/bold] {', '.join(parsed.get('properties', []))}",
        title="[blue]Analysis[/blue]",
    ))

    # Display protein info
    if protein.get("sequence"):
        seq = protein.get("sequence", "")
        seq_display = seq[:50] + "..." if len(seq) > 50 else seq

        protein_info = (
            f"[bold]Sequence Length:[/bold] {protein.get('sequence_length', 0)} AA\n"
            f"[bold]UniProt ID:[/bold] {protein.get('uniprot_id', 'N/A')}\n"
            f"[bold]Structure Source:[/bold] {protein.get('structure_source', 'none')}\n"
            f"[bold]Sequence:[/bold] {seq_display}"
        )

        if protein.get("avg_plddt"):
            protein_info += f"\n[bold]pLDDT:[/bold] {protein.get('avg_plddt'):.2f}"

        console.print(Panel(protein_info, title="[green]Protein[/green]"))

    # Display response
    response_html = response.get("response_html", "")
    natural_reply = response.get("natural_reply", "")

    if natural_reply:
        console.print(Panel(
            natural_reply,
            title="[cyan]Response[/cyan]",
        ))

    if verbose and response_html:
        # Convert HTML to simple text for display
        import re
        text = re.sub(r'<[^>]+>', '', response_html)
        text = text.replace('&lt;', '<').replace('&gt;', '>')
        console.print(Panel(text, title="[dim]Detailed Response[/dim]"))

    # Display errors if any
    if errors:
        error_table = Table(title="[red]Errors[/red]")
        error_table.add_column("Node", style="yellow")
        error_table.add_column("Type", style="red")
        error_table.add_column("Message", style="white")
        error_table.add_column("Recoverable", style="green")

        for error in errors:
            error_table.add_row(
                error.get("node", "unknown"),
                error.get("error_type", "unknown"),
                error.get("message", "")[:50],
                str(error.get("recoverable", False)),
            )

        console.print(error_table)

    # Display node history in verbose mode
    if verbose and history:
        tree = Tree("[bold]Node History[/bold]")
        for i, node in enumerate(history):
            tree.add(f"[{i + 1}] {node}")
        console.print(tree)

    # Summary
    console.print()
    status = "[green]Success[/green]" if not errors else "[yellow]Completed with errors[/yellow]"
    console.print(f"[bold]Status:[/bold] {status}")
    console.print(f"[bold]Nodes visited:[/bold] {len(history)}")


def display_node_result(node_name: str, result: Dict[str, Any]):
    """
    Display a single node's result.

    Args:
        node_name: Name of the node
        result: Node result dictionary
    """
    table = Table(title=f"Node Output: {node_name}")
    table.add_column("Key", style="cyan")
    table.add_column("Value", style="green")

    for key, value in result.items():
        if isinstance(value, dict):
            value_str = _format_dict(value)
        elif isinstance(value, list):
            value_str = f"[{len(value)} items]"
        else:
            value_str = str(value)[:100]

        table.add_row(key, value_str)

    console.print(table)


def _format_dict(d: Dict, max_len: int = 100) -> str:
    """Format a dictionary for display."""
    items = []
    for k, v in d.items():
        v_str = str(v)[:30] + "..." if len(str(v)) > 30 else str(v)
        items.append(f"{k}: {v_str}")

    result = ", ".join(items)
    if len(result) > max_len:
        result = result[:max_len] + "..."
    return "{" + result + "}"


def display_sequence(sequence: str, width: int = 80):
    """
    Display a protein sequence with formatting.

    Args:
        sequence: Amino acid sequence
        width: Characters per line
    """
    import textwrap

    formatted = "\n".join(textwrap.wrap(sequence, width))
    console.print(Panel(
        Syntax(formatted, "text", line_numbers=True),
        title="[blue]Sequence[/blue]",
    ))


def display_pdb_info(pdb_content: str):
    """
    Display basic PDB file information.

    Args:
        pdb_content: PDB file content
    """
    lines = pdb_content.split("\n")

    # Count atoms and residues
    atoms = [l for l in lines if l.startswith("ATOM")]
    residues = set()
    chains = set()

    for line in atoms:
        if len(line) >= 22:
            chains.add(line[21])
        if len(line) >= 26:
            residues.add((line[21], line[22:26].strip()))

    info = (
        f"[bold]Atoms:[/bold] {len(atoms)}\n"
        f"[bold]Residues:[/bold] {len(residues)}\n"
        f"[bold]Chains:[/bold] {', '.join(sorted(chains))}"
    )

    console.print(Panel(info, title="[green]PDB Structure[/green]"))
