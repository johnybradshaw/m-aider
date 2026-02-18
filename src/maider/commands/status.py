"""Show status of a VM session."""

import sys
import click

from ..config import Config
from ..linode_client import LinodeManager
from ..output import console
from ..session import SessionManager


@click.command(name="status")
@click.argument("session_name", required=False)
def cmd(session_name: str):
    """Show detailed status of a VM session.

    SESSION_NAME: Name of session (current session if not specified)
    """
    # Load configuration
    config = Config()

    # Initialize managers
    session_mgr = SessionManager()
    linode_mgr = LinodeManager(config)

    # Get session
    if session_name:
        session = session_mgr.get_session(session_name)
        if not session:
            console.print(f"[red]Session '{session_name}' not found[/red]")
            sys.exit(1)
    else:
        session = session_mgr.get_current_session()
        if not session:
            console.print("[red]No current session found[/red]")
            sys.exit(1)

    # Get Linode status
    instance = linode_mgr.get_instance(session.linode_id)

    # Display status
    console.print(f"\n[bold]Session: {session.name}[/bold]")
    console.print("─" * 50)
    console.print(f"  Linode ID: {session.linode_id}")
    console.print(f"  IP Address: {session.ip}")
    console.print(f"  Type: {session.type}")
    console.print(f"  Model: {session.model_id}")
    console.print(f"  Status: {instance.status if instance else 'deleted'}")
    console.print()
    console.print(f"  Runtime: {session.runtime_hours:.2f} hours")
    console.print(f"  Hourly cost: ${session.hourly_cost:.2f}")
    console.print(f"  Total cost: ${session.total_cost:.2f}")
    console.print()

    if instance and instance.status == "running":
        console.print("[bold]Access:[/bold]")
        console.print(f"  • SSH: ssh root@{session.ip}")
        console.print("  • Open WebUI: http://localhost:3000")
        console.print("  • vLLM API: http://localhost:8000/v1")
    console.print()
