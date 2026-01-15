"""Benchmark status and coverage command."""

from datetime import datetime, timedelta

import click
from rich.console import Console
from rich.table import Table

from ..benchmark_db import BenchmarkDatabase
from ..providers.linode import GPU_TYPES

console = Console()


@click.command(name="benchmark-status")
def cmd():
    """Show benchmark coverage status and gaps.

    Displays which GPU configurations have been benchmarked
    and suggests which configs to test next for complete coverage.

    Example:
        maider benchmark-status
    """
    db = BenchmarkDatabase()

    # Get coverage report
    coverage = db.get_coverage_report()

    console.print("\n[bold cyan]Benchmark Coverage Status[/bold cyan]\n")

    # Display summary
    console.print(f"[bold]Summary:[/bold]")
    console.print(f"  Total benchmarks: {coverage['total_benchmarks']}")
    console.print(
        f"  GPU types tested: {coverage['gpu_types_tested']}/{coverage['gpu_types_total']}"
    )
    console.print(f"  Unique configurations: {len(coverage['tested_configs'])}\n")

    # Display tested configurations
    if coverage["tested_configs"]:
        console.print("[bold]Tested Configurations:[/bold]\n")

        table = Table(show_header=True)
        table.add_column("GPU Type", style="cyan")
        table.add_column("Model", style="yellow")
        table.add_column("Runs", justify="right", style="green")
        table.add_column("Last Run", style="dim")
        table.add_column("Status", justify="center")

        for config in coverage["tested_configs"]:
            # Format GPU type
            gpu_label = config["gpu_type"]
            if "rtx6000" in gpu_label.lower():
                gpu_label = gpu_label.replace("g1-gpu-rtx6000-", "RTX6000x")
            elif "rtx4000" in gpu_label.lower():
                gpu_label = gpu_label.replace("g2-gpu-rtx4000a", "RTX4000x")
                gpu_label = gpu_label.replace("-s", "").replace("-m", "")

            # Format model category
            model_cat = config["model_category"].upper()

            # Format last run time
            try:
                last_run = datetime.fromisoformat(config["last_run"])
                now = datetime.now()
                delta = now - last_run

                if delta < timedelta(hours=1):
                    time_str = f"{int(delta.total_seconds() / 60)} minutes ago"
                elif delta < timedelta(days=1):
                    time_str = f"{int(delta.total_seconds() / 3600)} hours ago"
                elif delta < timedelta(days=7):
                    time_str = f"{delta.days} days ago"
                elif delta < timedelta(days=30):
                    time_str = f"{delta.days // 7} weeks ago"
                else:
                    time_str = f"{delta.days // 30} months ago"

                # Determine if data is stale (> 30 days)
                is_stale = delta > timedelta(days=30)
            except (ValueError, TypeError):
                time_str = "Unknown"
                is_stale = False

            # Status icon
            num_runs = config["count"]
            if num_runs >= 3:
                status = "[green]✓ Good[/green]"
            elif num_runs == 2:
                status = "[yellow]⚠ Limited[/yellow]"
            else:
                status = "[red]⚠ Low[/red]"

            if is_stale:
                status += " [dim](stale)[/dim]"

            table.add_row(
                gpu_label,
                model_cat,
                str(num_runs),
                time_str,
                status,
            )

        console.print(table)
    else:
        console.print("[yellow]No configurations tested yet.[/yellow]")

    # Show gaps (untested GPU types)
    console.print("\n[bold]Missing GPU Types:[/bold]\n")

    tested_gpu_types = set(config["gpu_type"] for config in coverage["tested_configs"])
    all_gpu_types = set(GPU_TYPES.keys())
    missing_types = all_gpu_types - tested_gpu_types

    if missing_types:
        # Sort by cost (cheapest first)
        sorted_missing = sorted(
            missing_types,
            key=lambda t: GPU_TYPES.get(t, {}).get("hourly_cost", 999),
        )

        for gpu_type in sorted_missing:
            info = GPU_TYPES.get(gpu_type, {})
            gpus = info.get("gpus", 1)
            vram = info.get("vram_per_gpu", 0)
            cost = info.get("hourly_cost", 0)
            total_vram = gpus * vram

            # Format label
            if "rtx6000" in gpu_type.lower():
                label = f"RTX 6000 Ada x{gpus}"
            elif "rtx4000" in gpu_type.lower():
                label = f"RTX 4000 Ada x{gpus}"
            else:
                label = gpu_type

            console.print(f"  [red]✗[/red] {label} ({total_vram}GB, ${cost:.2f}/hr)")

        console.print(
            "\n[dim]Suggestion: Next time you create one of these GPU types, run "
            "'maider benchmark-collect' to improve recommendations.[/dim]\n"
        )
    else:
        console.print("[green]✓ All GPU types have been benchmarked![/green]\n")

    # Show confidence levels
    console.print("[bold]Confidence Levels:[/bold]\n")
    high_confidence = sum(1 for c in coverage["tested_configs"] if c["count"] >= 3)
    medium_confidence = sum(1 for c in coverage["tested_configs"] if c["count"] == 2)
    low_confidence = sum(1 for c in coverage["tested_configs"] if c["count"] == 1)

    console.print(f"  [green]High (3+ runs):[/green] {high_confidence} configs")
    console.print(f"  [yellow]Medium (2 runs):[/yellow] {medium_confidence} configs")
    console.print(f"  [red]Low (1 run):[/red] {low_confidence} configs\n")

    if low_confidence > 0 or medium_confidence > 0:
        console.print(
            "[dim]Tip: Run additional benchmarks on existing configs to improve confidence.[/dim]\n"
        )
