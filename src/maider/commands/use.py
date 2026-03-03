"""Switch to a different VM session."""

import sys

import click

from ..config import Config
from ..linode_client import LinodeManager
from ..output import console
from ..session import SessionManager


@click.command(name="use")
@click.argument("session_name")
def cmd(session_name: str):
    """Switch to a different VM session.

    SESSION_NAME: Name of the session to switch to
    """
    session_mgr = SessionManager()

    # Get the session
    session = session_mgr.get_session(session_name)
    if not session:
        console.print(f"[red]✗ Session '{session_name}' not found[/red]\n")
        console.print("Available sessions:")
        sessions = session_mgr.list_sessions()
        if sessions:
            for s in sessions:
                console.print(f"  • {s.name}")
        else:
            console.print("  (none)")
        sys.exit(1)

    # Check if VM still exists
    try:
        config = Config()
        linode_mgr = LinodeManager(config)
        instance = linode_mgr.get_instance(session.linode_id)

        if not instance:
            console.print(
                f"[yellow]⚠ Warning: Linode {session.linode_id} no longer exists[/yellow]"
            )
            console.print(f"[yellow]Session '{session_name}' is stale[/yellow]\n")
            console.print("Run 'coder cleanup' to remove stale sessions")
    except Exception:
        # If we can't check (e.g., no LINODE_TOKEN), just warn
        console.print("[yellow]⚠ Could not verify VM status (no LINODE_TOKEN)[/yellow]")

    # Update symlink
    session_mgr.set_current_session(session)

    console.print(f"[green]✓ Switched to session: {session_name}[/green]")
    console.print("\nRun: [cyan]source .aider-env[/cyan]")
