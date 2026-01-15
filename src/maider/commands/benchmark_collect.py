"""Benchmark collection command for easy data gathering."""

import sys

import click
from rich.console import Console

from ..session import SessionManager
from . import benchmark

console = Console()


@click.command(name="benchmark-collect")
@click.argument("session_name", required=False)
@click.option(
    "--category",
    "-c",
    type=click.Choice(["all", "coding", "context_heavy", "reasoning"], case_sensitive=False),
    default="all",
    help="Test category to run (default: all)",
)
def cmd(session_name: str, category: str):
    """Run benchmark on current session and save to database.

    This is a convenience command that automatically:
    - Detects the current GPU configuration
    - Runs appropriate benchmark tests
    - Saves results to the centralized database
    - Displays summary results

    Use this when you want to quickly benchmark a VM and contribute
    to the performance database.

    SESSION_NAME: Name of session to benchmark (current session if not specified)

    Examples:
        maider benchmark-collect                    # Benchmark current session
        maider benchmark-collect my-session         # Benchmark specific session
        maider benchmark-collect --category coding  # Only run coding tests
    """
    session_mgr = SessionManager()

    # Get session
    if session_name:
        session = session_mgr.get_session(session_name)
        if not session:
            console.print(f"[red]✗ Session '{session_name}' not found[/red]")
            sys.exit(1)
    else:
        session = session_mgr.get_current_session()
        if not session:
            console.print("[red]✗ No current session set[/red]")
            console.print("\nUse: maider use <session-name>")
            sys.exit(1)

    console.print(f"\n[bold cyan]Collecting benchmark data for: {session.name}[/bold cyan]")
    console.print(f"  GPU Type: {session.type}")
    console.print(f"  Model: {session.model_id}")
    console.print(f"  Category: {category}\n")

    # Call the benchmark command with database saving enabled
    ctx = click.Context(benchmark.cmd)
    ctx.params = {
        "session": session.name,
        "output": f".benchmark-{session.name}.json",
        "category": category,
        "save_to_db": True,  # Always save to database
    }

    try:
        ctx.invoke(benchmark.cmd, **ctx.params)
        console.print("\n[green]✓ Benchmark data collected successfully![/green]")
        console.print("[dim]View all benchmarks with: maider benchmark-compare[/dim]")
        console.print("[dim]Get recommendations with: maider recommend[/dim]")
    except click.Abort:
        console.print("\n[red]✗ Benchmark collection failed[/red]")
        sys.exit(1)
