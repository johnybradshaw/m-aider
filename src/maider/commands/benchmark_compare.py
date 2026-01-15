"""Benchmark comparison command for analyzing results."""

from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.table import Table

from ..benchmark_db import BenchmarkDatabase

console = Console()

METRIC_SORTS = {"tokens_per_sec", "cost_per_1k_tokens", "cost_efficiency"}


@click.command(name="benchmark-compare")
@click.option(
    "--gpu-type",
    "-g",
    default=None,
    help="Filter by GPU type (e.g., g1-gpu-rtx6000-2)",
)
@click.option(
    "--model-category",
    "-m",
    default=None,
    help="Filter by model category (e.g., 70b, 30b, 14b)",
)
@click.option(
    "--task-category",
    "-t",
    type=click.Choice(["coding", "context_heavy", "reasoning"], case_sensitive=False),
    default=None,
    help="Filter by task category",
)
@click.option(
    "--sort-by",
    "-s",
    type=click.Choice(
        ["tokens_per_sec", "cost_per_1k_tokens", "cost_efficiency"], case_sensitive=False
    ),
    default="tokens_per_sec",
    help="Sort results by metric (default: tokens_per_sec)",
)
@click.option(
    "--format",
    "-f",
    type=click.Choice(["table", "json", "csv", "markdown"], case_sensitive=False),
    default="table",
    help="Output format (default: table)",
)
@click.option(
    "--output",
    "-o",
    default=None,
    help="Output file path (required for json/csv/markdown formats)",
)
def cmd(
    gpu_type: Optional[str],
    model_category: Optional[str],
    task_category: Optional[str],
    sort_by: str,
    format: str,
    output: Optional[str],
):
    """Compare benchmark results across configurations.

    Displays a comparison table of all benchmark results in the database,
    with optional filtering and sorting.

    Examples:
        maider benchmark-compare                              # Show all results
        maider benchmark-compare --gpu-type g1-gpu-rtx6000-2  # Filter by GPU type
        maider benchmark-compare --task-category coding       # Filter by task type
        maider benchmark-compare --sort-by cost_per_1k_tokens # Sort by cost
        maider benchmark-compare --format csv -o results.csv  # Export to CSV
    """
    db = BenchmarkDatabase()

    results = _load_results(db, gpu_type, model_category, task_category, sort_by)

    if not results:
        _print_no_results()
        return

    _render_output(db, results, task_category, sort_by, format, output)


def _load_results(
    db: BenchmarkDatabase,
    gpu_type: Optional[str],
    model_category: Optional[str],
    task_category: Optional[str],
    sort_by: str,
):
    if sort_by in METRIC_SORTS:
        ascending = sort_by == "cost_per_1k_tokens"
        return db.get_best_by_metric(
            metric=sort_by,
            task_category=task_category,
            limit=100,
            ascending=ascending,
        )

    results = db.get_results(
        gpu_type=gpu_type,
        model_category=model_category,
        task_category=task_category,
    )
    return _filter_results(results, gpu_type, model_category)


def _filter_results(results, gpu_type: Optional[str], model_category: Optional[str]):
    if gpu_type:
        results = [r for r in results if r.gpu_type == gpu_type]
    if model_category:
        results = [r for r in results if r.model_category == model_category]
    return results


def _print_no_results():
    console.print("[yellow]No benchmark results found matching the criteria.[/yellow]")
    console.print("\nTry:")
    console.print("  1. Running benchmarks with: maider benchmark-collect")
    console.print("  2. Removing some filters to see more results")


def _render_output(
    db: BenchmarkDatabase,
    results,
    task_category: Optional[str],
    sort_by: str,
    format: str,
    output: Optional[str],
):
    if format == "table":
        _display_table(results, task_category, sort_by)
        return

    if not output:
        console.print(f"[red]✗ --output required for {format.upper()} format[/red]")
        raise click.Abort()

    db.export(format, Path(output))
    console.print(f"[green]✓ Exported {len(results)} results to: {output}[/green]")


def _display_table(results, task_category: Optional[str], sort_metric: str):
    """Display results as a Rich table."""
    console.print("\n[bold cyan]Benchmark Comparison[/bold cyan]")
    if task_category:
        console.print(f"[dim]Category: {task_category.replace('_', ' ').title()}[/dim]")
    console.print(f"[dim]Sorted by: {sort_metric.replace('_', ' ').title()}[/dim]\n")

    table = Table(show_header=True)
    table.add_column("GPU Type", style="cyan")
    table.add_column("GPUs", justify="right")
    table.add_column("VRAM", justify="right")
    table.add_column("Model", style="yellow")
    table.add_column("Tokens/Sec", justify="right", style="green")
    table.add_column("Cost/1K", justify="right", style="magenta")
    table.add_column("$/Hour", justify="right")
    table.add_column("Efficiency", justify="right")
    table.add_column("Tests", justify="right")

    for result in results:
        # Truncate model name if too long
        model_name = result.model_id.split("/")[-1]
        if len(model_name) > 30:
            model_name = model_name[:27] + "..."

        # Calculate cost efficiency
        cost_efficiency = (
            result.summary.get("avg_tokens_per_sec", 0) / result.hourly_cost
            if result.hourly_cost > 0
            else 0
        )

        # Get GPU label
        gpu_label = result.gpu_type
        if "rtx6000" in gpu_label.lower():
            gpu_label = gpu_label.replace("g1-gpu-rtx6000-", "RTX6000x")
        elif "rtx4000" in gpu_label.lower():
            gpu_label = gpu_label.replace("g2-gpu-rtx4000a", "RTX4000x")
            gpu_label = gpu_label.replace("-s", "").replace("-m", "")

        table.add_row(
            gpu_label,
            str(result.gpu_count),
            f"{result.total_vram}GB",
            model_name,
            f"{result.summary.get('avg_tokens_per_sec', 0):.1f}",
            f"${result.summary.get('cost_per_1k_tokens', 0):.4f}",
            f"${result.hourly_cost:.2f}",
            f"{cost_efficiency:.1f}",
            f"{result.summary.get('tests_passed', 0)}/{result.summary.get('tests_total', 0)}",
        )

    console.print(table)
    console.print(f"\n[dim]Total results: {len(results)}[/dim]")
    console.print("[dim]Efficiency = tokens/sec per dollar/hour (higher is better)[/dim]\n")
