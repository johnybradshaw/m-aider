"""Continuous health monitoring command."""

import os
import sys
import time
from datetime import datetime
import click
import requests
from rich.table import Table

from ..gpu_utils import GPUMonitor
from ..output import console
from ..session import SessionManager
from ..ssh_utils import SSHClient


@click.command(name="watch")
@click.argument("session_name", required=False)
@click.option(
    "--interval",
    "-i",
    default=5,
    type=int,
    help="Refresh interval in seconds (default: 5)",
)
def cmd(session_name: str, interval: int):
    """Continuously monitor VM health with live updates.

    SESSION_NAME: Name of session to monitor (current session if not specified)

    Press Ctrl+C to stop monitoring.
    """
    session_mgr = SessionManager()
    session = _get_session_or_exit(session_mgr, session_name)

    console.print(f"\n[bold]Watching session: {session.name}[/bold]")
    console.print(f"[dim]IP: {session.ip} | Model: {session.model_id}[/dim]")
    console.print(f"[dim]Refresh interval: {interval}s | Press Ctrl+C to stop[/dim]\n")

    ssh = SSHClient(session.ip)
    gpu_monitor = GPUMonitor(ssh)

    try:
        while True:
            _clear_screen()
            _print_status(session, gpu_monitor)
            time.sleep(interval)
    except KeyboardInterrupt:
        console.print("\n[dim]Monitoring stopped[/dim]")


def _clear_screen():
    """Clear the terminal screen."""
    os.system("clear" if os.name == "posix" else "cls")


def _get_session_or_exit(session_mgr: SessionManager, session_name: str):
    """Get session or exit with error."""
    if session_name:
        session = session_mgr.get_session(session_name)
        if not session:
            console.print(f"[red]Session '{session_name}' not found[/red]")
            sys.exit(1)
        return session

    session = session_mgr.get_current_session()
    if not session:
        console.print("[red]No current session found[/red]")
        console.print("Run 'maider up' first or specify a session name")
        sys.exit(1)
    return session


def _print_status(session, gpu_monitor: GPUMonitor):
    """Print current health status."""
    # Header
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    console.print(f"[bold]VM Health: {session.name}[/bold]")
    console.print(f"[dim]Last update: {timestamp}[/dim]\n")

    # GPU Status
    _print_gpu_table(gpu_monitor)

    # API Status
    api_status = _check_api_status(session)
    console.print(f"\n{api_status}")

    # Session Info
    runtime_hours = session.get_runtime_hours()
    cost = runtime_hours * session.hourly_cost
    console.print(
        f"\n[dim]Runtime: {runtime_hours:.2f}h | "
        f"Cost: ${cost:.2f} @ ${session.hourly_cost:.2f}/hr[/dim]"
    )
    console.print("\n[dim]Press Ctrl+C to stop[/dim]")


def _print_gpu_table(gpu_monitor: GPUMonitor):
    """Print a table with GPU status."""
    gpus = gpu_monitor.get_gpu_info()
    if not gpus:
        console.print("[red]Failed to get GPU info[/red]")
        return

    table = Table(show_header=True, box=None)
    table.add_column("GPU", style="cyan")
    table.add_column("Memory", justify="right")
    table.add_column("Util", justify="right")
    table.add_column("Status")

    for gpu in gpus:
        memory_pct = gpu.memory_percent
        util_pct = gpu.utilization_percent

        # Determine status
        if memory_pct < 10:
            status = "[red]IDLE[/red]"
        elif memory_pct < 50:
            status = "[yellow]LOW[/yellow]"
        else:
            status = "[green]OK[/green]"

        # Color utilization
        if util_pct > 80:
            util_str = f"[green]{util_pct}%[/green]"
        elif util_pct > 20:
            util_str = f"[yellow]{util_pct}%[/yellow]"
        else:
            util_str = f"[dim]{util_pct}%[/dim]"

        table.add_row(
            f"{gpu.index}: {gpu.name[:20]}",
            f"{gpu.memory_used_mb}/{gpu.memory_total_mb} MB ({memory_pct:.0f}%)",
            util_str,
            status,
        )

    console.print(table)


def _check_api_status(session) -> str:
    """Check vLLM API status."""
    try:
        response = requests.get(
            "http://localhost:8000/v1/models",
            timeout=5,
        )
        if response.status_code == 200:
            return "[green]✓ vLLM API: Ready[/green]"
        else:
            return f"[yellow]⚠ vLLM API: HTTP {response.status_code}[/yellow]"
    except requests.exceptions.ConnectionError:
        return "[red]✗ vLLM API: Connection refused (is tunnel active?)[/red]"
    except requests.exceptions.Timeout:
        return "[yellow]⚠ vLLM API: Timeout (model may be loading)[/yellow]"
    except Exception as e:
        return f"[red]✗ vLLM API: {e}[/red]"
