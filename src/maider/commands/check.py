"""Quick GPU health check."""

import sys
import time
import requests

import click
from rich.console import Console
from rich.table import Table

from ..session import SessionManager
from ..ssh_utils import SSHClient
from ..gpu_utils import GPUMonitor

console = Console()


@click.command(name="check")
@click.argument("session_name", required=False)
def cmd(session_name: str):
    """Quick multi-GPU health check.

    SESSION_NAME: Name of session to check (current session if not specified)
    """
    # Get session
    session_mgr = SessionManager()

    if session_name:
        session = session_mgr.get_session(session_name)
        if not session:
            console.print(f"[red]Session '{session_name}' not found[/red]")
            sys.exit(1)
    else:
        session = session_mgr.get_current_session()
        if not session:
            console.print("[red]No current session found[/red]")
            console.print("Run 'coder up' first or specify a session name")
            sys.exit(1)

    console.print("\n[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]")
    console.print("[bold]  Quick Multi-GPU Health Check[/bold]")
    console.print("[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]\n")

    # Initialize SSH and GPU monitor
    ssh = SSHClient(session.ip)
    gpu_monitor = GPUMonitor(ssh)

    # 1. GPU Memory Usage
    console.print("[bold]GPU Memory Usage:[/bold]")
    gpus = gpu_monitor.get_gpu_info()

    if not gpus:
        console.print("[red]✗ Failed to get GPU information[/red]")
        sys.exit(1)

    table = Table(show_header=True)
    table.add_column("GPU")
    table.add_column("Name")
    table.add_column("Memory Used")
    table.add_column("Memory Total")
    table.add_column("Usage %")
    table.add_column("Utilization")

    for gpu in gpus:
        memory_pct = gpu.memory_percent
        util = f"{gpu.utilization_percent}%"

        # Color code by memory usage
        if memory_pct < 10:
            status_color = "red"
            status = "IDLE"
        elif memory_pct < 50:
            status_color = "yellow"
            status = f"{memory_pct:.0f}%"
        else:
            status_color = "green"
            status = f"{memory_pct:.0f}%"

        table.add_row(
            f"GPU {gpu.index}",
            gpu.name,
            f"{gpu.memory_used_mb} MB",
            f"{gpu.memory_total_mb} MB",
            f"[{status_color}]{status}[/{status_color}]",
            util,
        )

    console.print(table)
    console.print()

    # 2. Multi-GPU Status
    console.print("[bold]Multi-GPU Status:[/bold]")
    is_working, message = gpu_monitor.check_tensor_parallelism()

    if is_working:
        console.print(f"  [green]✓[/green] {message}")
    else:
        console.print(f"  [red]✗[/red] {message}")
        console.print("     → Tensor parallelism may not be configured correctly")
        console.print("     → Run: coder validate-perf for detailed analysis")

    console.print()

    # 3. Quick Throughput Test
    console.print("[bold]Quick Throughput Test:[/bold]")

    try:
        start = time.time()
        response = requests.post(
            "http://localhost:8000/v1/completions",
            json={
                "model": session.served_model_name,
                "prompt": "Write a hello world program",
                "max_tokens": 100,
            },
            timeout=30,
        )
        end = time.time()

        if response.status_code == 200:
            data = response.json()
            tokens = data.get("usage", {}).get("completion_tokens", 0)
            duration = end - start
            tokens_per_sec = tokens / duration if duration > 0 else 0

            console.print(
                f"  [green]✓[/green] Generated {tokens} tokens in {duration:.1f}s "
                f"({tokens_per_sec:.1f} tok/s)"
            )
        else:
            console.print(f"  [red]✗[/red] API test failed: {response.status_code}")

    except requests.exceptions.RequestException as e:
        console.print(f"  [red]✗[/red] API test failed: {e}")
        console.print("     → Is the SSH tunnel active?")
        console.print("     → Is vLLM still loading the model?")

    console.print()
    console.print("[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]")
    console.print("For detailed performance analysis: [cyan]coder validate-perf[/cyan]")
    console.print("[bold]━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━[/bold]\n")
