"""List all VM sessions."""

import click
from rich.console import Console
from rich.table import Table

from ..config import Config
from ..linode_client import LinodeManager
from ..session import SessionManager

console = Console()


@click.command(name="list")
def cmd():
    """List all active VM sessions."""
    # Load configuration
    config = Config()

    # Initialize managers
    session_mgr = SessionManager()
    linode_mgr = LinodeManager(config)

    # Get all sessions
    sessions = session_mgr.list_sessions()

    if not sessions:
        console.print("[yellow]No active sessions found[/yellow]")
        return

    # Get current session
    current_session = session_mgr.get_current_session()
    current_name = current_session.name if current_session else None

    # Create table
    table = Table(title="Active VM Sessions", show_header=True, header_style="bold cyan")
    table.add_column("SESSION", style="cyan")
    table.add_column("LINODE_ID")
    table.add_column("IP")
    table.add_column("TYPE")
    table.add_column("COST/HR", justify="right")
    table.add_column("RUNTIME", justify="right")
    table.add_column("TOTAL", justify="right")
    table.add_column("STATUS")

    total_hourly = 0.0
    total_cost = 0.0

    for session in sorted(sessions, key=lambda s: s.start_time):
        # Check if Linode still exists
        instance = linode_mgr.get_instance(session.linode_id)
        status = instance.status if instance else "deleted"

        # Mark current session
        session_name = session.name
        if session.name == current_name:
            session_name = f"{session.name} *"

        table.add_row(
            session_name,
            str(session.linode_id),
            session.ip,
            session.type,
            f"${session.hourly_cost:.2f}",
            f"{session.runtime_hours:.1f}h",
            f"${session.total_cost:.2f}",
            status,
        )

        total_hourly += session.hourly_cost
        total_cost += session.total_cost

    console.print()
    console.print(table)
    console.print()
    console.print(f"Total: {len(sessions)} VMs @ ${total_hourly:.2f}/hour")
    console.print(f"Total cost so far: ${total_cost:.2f}")

    if current_name:
        console.print()
        console.print("[dim]* = current session[/dim]")
    else:
        console.print()
        console.print(
            "[yellow]No current session set. Run 'coder use <session>' to set one.[/yellow]"
        )
