"""Destroy a VM instance."""

import sys
import subprocess
from pathlib import Path

import click
from rich.console import Console

from ..config import Config
from ..linode_client import LinodeManager
from ..session import SessionManager

console = Console()


@click.command(name="down")
@click.argument("session_name", required=False)
@click.option("--force", "-f", is_flag=True, help="Skip confirmation prompt")
def cmd(session_name: str, force: bool):
    """Destroy a VM instance.

    SESSION_NAME: Name of session to destroy (current session if not specified)
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
            # No current session - try to auto-detect if there's only one running
            sessions = session_mgr.list_sessions()
            if len(sessions) == 0:
                console.print("[red]No sessions found[/red]")
                sys.exit(1)
            elif len(sessions) == 1:
                # Only one session - use it
                session = sessions[0]
                console.print(
                    f"[yellow]No current session set, using only session: {session.name}[/yellow]"
                )
            else:
                # Multiple sessions - ask user to specify
                console.print("[red]No current session set and multiple sessions exist[/red]")
                console.print("\nAvailable sessions:")
                for s in sessions:
                    console.print(f"  • {s.name}")
                console.print("\nRun: [cyan]coder down <session-name>[/cyan]")
                console.print(
                    "Or:  [cyan]coder use <session-name>[/cyan] first, then [cyan]coder down[/cyan]"
                )
                sys.exit(1)

    # Validate API token is available before proceeding
    if not config.linode_token:
        console.print("[red]✗ Cannot destroy VM: Missing Linode API token[/red]\n")
        console.print(
            "[bold]The VM is still running but cannot be deleted without an API token.[/bold]\n"
        )
        console.print("[bold]Options:[/bold]")
        console.print("  1. Set LINODE_TOKEN in your environment:")
        console.print("     export LINODE_TOKEN=your_token_here")
        console.print("     coder down {}\n".format(session.name))
        console.print("  2. Manually delete the Linode from the web dashboard:")
        console.print("     https://cloud.linode.com/linodes/{}\n".format(session.linode_id))
        console.print(
            "  3. Then run: [cyan]coder cleanup --session {} --force[/cyan] to remove local state\n".format(
                session.name
            )
        )
        console.print(
            "[yellow]⚠ VM {}/{} is still running and will continue to cost ${:.2f}/hour![/yellow]".format(
                session.linode_id, session.ip, session.hourly_cost
            )
        )
        sys.exit(1)

    # Confirm destruction
    if not force:
        console.print(f"\n[bold]Session: {session.name}[/bold]")
        console.print(f"  Linode ID: {session.linode_id}")
        console.print(f"  IP: {session.ip}")
        console.print(f"  Runtime: {session.runtime_hours:.2f} hours")
        console.print(f"  Cost: ${session.total_cost:.2f}\n")

        response = input("Destroy this VM? [y/N]: ")
        if response.lower() != "y":
            console.print("Cancelled")
            sys.exit(0)

    # Close SSH tunnel
    console.print("\n[bold]Cleaning up SSH tunnel...[/bold]")
    control_path = Path.home() / ".ssh" / f"llm-master-root@{session.ip}"
    subprocess.run(
        ["ssh", "-O", "exit", "-o", f"ControlPath={control_path}", f"root@{session.ip}"],
        capture_output=True,
    )

    # Delete Linode
    console.print("[bold]Destroying VM...[/bold]")
    try:
        instance = linode_mgr.get_instance(session.linode_id)
        if instance:
            instance.delete()
            console.print(f"✓ Deleted Linode: {session.linode_id}")
        else:
            console.print(
                f"[yellow]⚠ Linode {session.linode_id} not found (already deleted?)[/yellow]"
            )
    except Exception as e:
        console.print(f"[red]✗ Failed to delete Linode {session.linode_id}: {e}[/red]\n")
        console.print("[bold]The VM may still be running![/bold]\n")
        console.print("[bold]Options:[/bold]")
        console.print("  1. Check if VM still exists: coder status {}".format(session.name))
        console.print("  2. Try again: coder down {}".format(session.name))
        console.print("  3. Manually delete from web dashboard:")
        console.print("     https://cloud.linode.com/linodes/{}\n".format(session.linode_id))
        console.print(
            "  4. Then run: [cyan]coder cleanup --session {} --force[/cyan] to remove local state\n".format(
                session.name
            )
        )
        console.print("[yellow]Local session state has NOT been deleted.[/yellow]")
        sys.exit(1)

    # Show cost summary
    console.print("\n[bold]Session Summary:[/bold]")
    console.print("═" * 50)
    console.print(f"  Runtime: {session.runtime_hours:.2f} hours")
    console.print(f"  Hourly rate: ${session.hourly_cost:.2f}")
    console.print(f"  Total cost: ${session.total_cost:.2f}")
    console.print("═" * 50)

    # Delete session
    session_mgr.delete_session(session.name)

    console.print(f"\n[green]✓[/green] Session '{session.name}' destroyed")
