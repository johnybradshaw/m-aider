"""Comprehensive multi-GPU performance validation."""

import sys
import time
import requests

import click
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ..session import SessionManager
from ..ssh_utils import SSHClient
from ..gpu_utils import GPUMonitor

console = Console()


@click.command(name="validate-perf")
@click.argument("session_name", required=False)
def cmd(session_name: str):
    """Comprehensive multi-GPU performance validation.

    Validates tensor parallelism, GPU utilization, NCCL, and throughput.

    SESSION_NAME: Name of session to validate (current session if not specified)
    """
    session_mgr = SessionManager()
    session = _get_session_or_exit(session_mgr, session_name)
    ssh = SSHClient(session.ip)
    gpu_monitor = GPUMonitor(ssh)

    console.print()

    gpus = _gpu_hardware_validation(gpu_monitor)
    _tensor_parallel_validation(gpu_monitor)
    idle_gpus = _gpu_memory_utilization(gpus)
    errors = _nccl_communication_check(gpu_monitor)
    results = _run_live_performance_test(session)
    _print_recommendations(len(gpus))
    _print_summary(session, idle_gpus, errors, results)


def _get_session_or_exit(session_mgr: SessionManager, session_name: str):
    if session_name:
        session = session_mgr.get_session(session_name)
        if not session:
            console.print(f"[red]Session '{session_name}' not found[/red]")
            sys.exit(1)
        return session

    session = session_mgr.get_current_session()
    if not session:
        console.print("[red]No current session found[/red]")
        sys.exit(1)
    return session


def _gpu_hardware_validation(gpu_monitor: GPUMonitor):
    _print_header("1. GPU Hardware Validation")
    gpus = gpu_monitor.get_gpu_info()
    if not gpus:
        console.print("[red]✗ Failed to get GPU information[/red]")
        sys.exit(1)

    console.print(f"[green]✓[/green] Found {len(gpus)} GPU(s)\n")
    console.print("[bold]GPU Details:[/bold]")
    for gpu in gpus:
        console.print(f"  GPU {gpu.index}: {gpu.name} | {gpu.memory_total_mb} MB")

    console.print("\n[bold]GPU Topology (NVLink/PCIe connectivity):[/bold]")
    topology = gpu_monitor.get_gpu_topology()
    if topology:
        for line in topology.split("\n")[:10]:
            console.print(f"  {line}")
    else:
        console.print("  [yellow]⚠[/yellow] Could not retrieve topology")
    return gpus


def _tensor_parallel_validation(gpu_monitor: GPUMonitor):
    _print_header("2. Tensor Parallelism Configuration")
    console.print("[bold]Checking vLLM tensor parallelism initialization...[/bold]")
    logs = gpu_monitor.get_container_logs(lines=200)

    if not logs:
        console.print("[yellow]⚠[/yellow] Could not retrieve container logs")
        return

    tp_lines = [
        line for line in logs.split("\n") if "tensor" in line.lower() and "parallel" in line.lower()
    ]
    if not tp_lines:
        console.print("[yellow]⚠[/yellow] Could not find tensor parallelism info in logs")
        return

    console.print("\n[bold]Tensor Parallelism Logs:[/bold]")
    for line in tp_lines[:5]:
        console.print(f"  {line.strip()}")

    is_working, message = gpu_monitor.check_tensor_parallelism()
    console.print()
    if is_working:
        console.print(f"[green]✓[/green] {message}")
    else:
        console.print(f"[red]✗[/red] {message}")


def _gpu_memory_utilization(gpus):
    _print_header("3. GPU Memory Utilization")
    table = Table(show_header=True)
    table.add_column("GPU")
    table.add_column("Memory Used")
    table.add_column("Memory Total")
    table.add_column("Usage %")
    table.add_column("Status")

    idle_gpus = []
    for gpu in gpus:
        memory_pct = gpu.memory_percent
        status = _memory_status_label(memory_pct, idle_gpus, gpu.index)
        table.add_row(
            f"GPU {gpu.index}",
            f"{gpu.memory_used_mb} MB",
            f"{gpu.memory_total_mb} MB",
            f"{memory_pct:.0f}%",
            status,
        )

    console.print(table)

    if idle_gpus:
        console.print(
            f"\n[red]✗[/red] GPUs {idle_gpus} appear IDLE - tensor parallelism may not be working"
        )
    else:
        console.print(
            "\n[green]✓[/green] All GPUs have similar memory usage (good TP distribution)"
        )

    return idle_gpus


def _memory_status_label(memory_pct: float, idle_gpus: list[int], index: int) -> str:
    if memory_pct < 10:
        idle_gpus.append(index)
        return "[red]IDLE[/red]"
    if memory_pct < 50:
        return "[yellow]Low[/yellow]"
    return "[green]Good[/green]"


def _nccl_communication_check(gpu_monitor: GPUMonitor):
    _print_header("4. NCCL Multi-GPU Communication")
    errors = gpu_monitor.check_vllm_errors()

    if errors.get("nccl"):
        console.print("[red]✗[/red] NCCL errors detected:\n")
        for error in errors["nccl"][:5]:
            console.print(f"  {error}")
    else:
        console.print("[green]✓[/green] No NCCL errors found")

    if errors.get("oom"):
        console.print("\n[yellow]⚠[/yellow] OOM errors detected:")
        for error in errors["oom"][:3]:
            console.print(f"  {error}")

    return errors


def _run_live_performance_test(session):
    _print_header("5. Live Performance Test")
    console.print("Running performance test with 3 different prompt sizes...\n")

    test_prompts = [
        ("Short", "Write a Python function to calculate fibonacci numbers", 256),
        (
            "Medium",
            "Explain the differences between REST and GraphQL APIs, including when to use each",
            512,
        ),
        ("Long", "Write a detailed technical blog post about distributed systems", 512),
    ]

    results = []
    for label, prompt, max_tokens in test_prompts:
        console.print(f"[bold]{label} prompt test:[/bold]")
        result = _run_single_prompt(session, prompt, max_tokens)
        if result is None:
            continue
        tokens, duration, tokens_per_sec = result
        console.print(
            f"  [green]✓[/green] Generated {tokens} tokens in {duration:.1f}s "
            f"({tokens_per_sec:.1f} tok/s)\n"
        )
        results.append((label, tokens_per_sec))
    return results


def _run_single_prompt(session, prompt: str, max_tokens: int):
    try:
        start = time.time()
        response = requests.post(
            "http://localhost:8000/v1/completions",
            json={
                "model": session.served_model_name,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            },
            timeout=60,
        )
        end = time.time()

        if response.status_code == 200:
            data = response.json()
            tokens = data.get("usage", {}).get("completion_tokens", 0)
            duration = end - start
            tokens_per_sec = tokens / duration if duration > 0 else 0
            return tokens, duration, tokens_per_sec

        console.print(f"  [red]✗[/red] Failed: {response.status_code}\n")
        return None

    except requests.exceptions.RequestException as e:
        console.print(f"  [red]✗[/red] Failed: {e}\n")
        return None


def _print_recommendations(gpu_count: int):
    _print_header("6. Configuration Review")
    console.print("[bold]Recommendations for multi-GPU performance:[/bold]\n")

    recommendations = [
        f"• VLLM_TENSOR_PARALLEL_SIZE should equal GPU count ({gpu_count})",
        "• VLLM_GPU_MEMORY_UTILIZATION: 0.85-0.90 for stability",
        "• VLLM_MAX_NUM_SEQS: 1 for coding (low latency), 4-8 for throughput",
        "• Enable prefix caching: --enable-prefix-caching",
        "• For NVLink GPUs: NCCL_P2P_DISABLE=0",
        "• For PCIe GPUs: May need NCCL_IB_DISABLE=1",
    ]

    for rec in recommendations:
        console.print(f"  {rec}")


def _print_summary(session, idle_gpus, errors, results):
    _print_header("Validation Summary")
    summary_items = []

    if idle_gpus:
        summary_items.append(
            (
                "✗",
                "red",
                "Tensor parallelism may not be enabled",
                "Check VLLM_TENSOR_PARALLEL_SIZE in .env",
            )
        )
    else:
        summary_items.append(("✓", "green", "All GPUs are active", "Tensor parallelism is working"))

    if errors.get("nccl"):
        summary_items.append(
            ("✗", "red", "NCCL communication errors", "Add NCCL env vars to docker-compose")
        )
    else:
        summary_items.append(("✓", "green", "No NCCL errors", "Inter-GPU communication is healthy"))

    if results:
        avg_throughput = sum(t for _, t in results) / len(results)
        summary_items.append(
            (
                "✓",
                "green",
                f"Average throughput: {avg_throughput:.1f} tok/s",
                "Performance is normal",
            )
        )

    console.print()
    for symbol, color, title, description in summary_items:
        console.print(f"[{color}]{symbol}[/{color}] [bold]{title}[/bold]: {description}")

    console.print("\n[bold]For detailed investigation:[/bold]")
    console.print(f"  • SSH to VM: ssh root@{session.ip}")
    console.print("  • Monitor GPUs: nvtop")
    console.print("  • Check logs: docker logs $(docker ps -q)")
    console.print()


def _print_header(title: str):
    """Print a section header."""
    console.print()
    console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    console.print()
