"""Reset watchdog idle timer."""

import sys
import time

import click
from rich.console import Console

from ..session import SessionManager

console = Console()


@click.command(name="extend")
@click.argument("session_name", required=False)
def cmd(session_name: str = None):
    """Reset the watchdog idle timer for a session.

    SESSION_NAME: Optional session name (uses current session if not specified)
    """
    session_mgr = SessionManager()

    # Get session (current or specified)
    if session_name:
        session = session_mgr.get_session(session_name)
        if not session:
            console.print(f"[red]✗ Session '{session_name}' not found[/red]")
            sys.exit(1)
    else:
        session = session_mgr.get_current_session()
        if not session:
            console.print("[red]✗ No current session[/red]")
            console.print("\nRun: [cyan]coder list[/cyan] to see available sessions")
            console.print("Or:  [cyan]coder extend <session-name>[/cyan] to specify a session")
            sys.exit(1)

    # Update last_activity timestamp
    session_dir = session_mgr.cache_dir / session.name
    activity_file = session_dir / "last_activity"
    activity_file.write_text(str(time.time()))

    console.print(f"[green]✓ Timer reset for session: {session.name}[/green]")

    # Show current idle time (should be ~0)
    try:
        watchdog_pid_file = session_dir / "watchdog.pid"
        if watchdog_pid_file.exists():
            console.print("\n[dim]Watchdog will reset idle timer on next check (~60 seconds)[/dim]")
        else:
            console.print("\n[yellow]⚠ Watchdog not running for this session[/yellow]")
    except Exception:
        pass
