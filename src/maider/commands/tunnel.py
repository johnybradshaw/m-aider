"""Re-establish SSH tunnel for a session."""

import sys
import subprocess
from pathlib import Path

import click
from rich.console import Console

from ..config import Config
from ..linode_client import LinodeManager
from ..session import SessionManager

console = Console()


@click.command(name="tunnel")
@click.argument("session_name", required=False)
def cmd(session_name: str | None = None):
    """Re-establish SSH tunnel for a session.

    SESSION_NAME: Name of session (current session if not specified)
    """
    # Initialize managers
    session_mgr = SessionManager()

    # Get session
    if session_name:
        session = session_mgr.get_session(session_name)
        if not session:
            console.print(f"[red]Session '{session_name}' not found[/red]")
            sys.exit(1)
    else:
        session = session_mgr.get_current_session()
        if not session:
            console.print("[red]No current session set[/red]")
            console.print("\nRun: [cyan]coder use <session-name>[/cyan]")
            sys.exit(1)

    # Query VM status dynamically
    try:
        config = Config()
        linode_mgr = LinodeManager(config)
        vm_status = linode_mgr.get_instance_status(session.linode_id)
    except Exception:
        vm_status = None

    console.print(f"[bold]Session: {session.name}[/bold]")
    console.print(f"  IP: {session.ip}")
    if vm_status:
        console.print(f"  Status: {vm_status}\n")
    else:
        console.print("  Status: [dim]unknown[/dim]\n")

    if vm_status and vm_status != "running":
        console.print(f"[yellow]Warning:[/yellow] VM status is '{vm_status}'")
        console.print("The tunnel may not work if the VM is not running.\n")

    # Setup SSH tunnel
    console.print("[bold]Setting up SSH tunnel...[/bold]")
    control_path = Path.home() / ".ssh" / f"llm-master-root@{session.ip}"

    # Close existing tunnel if any
    subprocess.run(
        ["ssh", "-O", "exit", "-o", f"ControlPath={control_path}", f"root@{session.ip}"],
        capture_output=True,
    )

    # Create new tunnel
    try:
        subprocess.run(
            [
                "ssh",
                "-fNM",
                "-o",
                f"ControlPath={control_path}",
                "-o",
                "StrictHostKeyChecking=no",
                "-L",
                "3000:localhost:3000",
                "-L",
                "8000:localhost:8000",
                f"root@{session.ip}",
            ],
            check=True,
            capture_output=True,
        )
        console.print("[green]✓[/green] SSH tunnel established")
        console.print("\n[bold]Access:[/bold]")
        console.print("  • Open WebUI: http://localhost:3000")
        console.print("  • vLLM API: http://localhost:8000/v1\n")

    except subprocess.CalledProcessError as e:
        console.print(f"[red]✗[/red] Failed to establish tunnel: {e}")
        console.print("\n[bold]Troubleshooting:[/bold]")
        console.print("  • Check if VM is accessible: ssh root@{}".format(session.ip))
        console.print("  • Check VM status: coder status")
        console.print("  • Check if ports 3000/8000 are already in use: lsof -ti:3000\n")
        sys.exit(1)
