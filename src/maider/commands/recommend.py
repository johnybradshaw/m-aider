"""Interactive recommendation command."""

import click
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

from ..benchmark_db import BenchmarkDatabase
from ..recommendations import (
    RecommendationEngine,
    TaskType,
    BudgetConstraint,
    ModelSizePreference,
)

console = Console()
CHOICE_PROMPT = "\nChoice"


@click.command(name="recommend")
def cmd():
    """Get personalized GPU/model recommendations.

    This interactive command asks about your use case and provides
    personalized recommendations based on benchmark data.

    The recommendations are ranked by:
    - Data confidence (more benchmarks = better confidence)
    - Cost efficiency (tokens/sec per dollar)
    - Your stated preferences

    Example:
        maider recommend
    """
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]GPU Configuration Recommendations[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    # Check if database has any data
    db = BenchmarkDatabase()
    all_results = db.get_results()

    if not all_results:
        console.print("[yellow]No benchmark data available yet.[/yellow]\n")
        console.print("To get recommendations:")
        console.print("  1. Create a VM: maider up")
        console.print("  2. Run benchmark: maider benchmark-collect")
        console.print("  3. Come back here: maider recommend\n")
        return

    console.print(f"[dim]Found {len(all_results)} benchmark results in database[/dim]\n")

    # Question 1: Task type
    console.print("[bold]What's your primary task type?[/bold]\n")
    task_choices = [
        "Coding (function writing, code review, refactoring)",
        "Context-heavy tasks (large context analysis, architecture)",
        "Reasoning (problem solving, design decisions)",
        "Mixed workload (variety of tasks)",
    ]

    for i, choice in enumerate(task_choices, 1):
        console.print(f"  {i}) {choice}")

    task_idx = int(Prompt.ask(CHOICE_PROMPT, choices=["1", "2", "3", "4"], default="1")) - 1

    task_type_map = [
        TaskType.CODING,
        TaskType.CONTEXT_HEAVY,
        TaskType.REASONING,
        TaskType.MIXED,
    ]
    task_type = task_type_map[task_idx]

    # Question 2: Budget
    console.print("\n[bold]What's your budget constraint?[/bold]\n")
    budget_choices = [
        "Under $1/hour (most economical)",
        "$1-$3/hour (balanced cost/performance)",
        "Over $3/hour (maximum performance)",
        "No constraint (show all options)",
    ]

    for i, choice in enumerate(budget_choices, 1):
        console.print(f"  {i}) {choice}")

    budget_idx = int(Prompt.ask(CHOICE_PROMPT, choices=["1", "2", "3", "4"], default="2")) - 1

    budget_map = [
        BudgetConstraint.UNDER_1,
        BudgetConstraint.ONE_TO_THREE,
        BudgetConstraint.OVER_THREE,
        BudgetConstraint.NO_CONSTRAINT,
    ]
    budget = budget_map[budget_idx]

    # Question 3: Model size preference
    console.print("\n[bold]What model size preference?[/bold]\n")
    size_choices = [
        "Smallest viable (best value for money)",
        "Balanced (good performance and cost)",
        "Largest available (maximum capability)",
    ]

    for i, choice in enumerate(size_choices, 1):
        console.print(f"  {i}) {choice}")

    size_idx = int(Prompt.ask(CHOICE_PROMPT, choices=["1", "2", "3"], default="2")) - 1

    size_map = [
        ModelSizePreference.SMALLEST_VIABLE,
        ModelSizePreference.BALANCED,
        ModelSizePreference.LARGEST_AVAILABLE,
    ]
    model_size_pref = size_map[size_idx]

    # Generate recommendations
    console.print("\n[cyan]Analyzing benchmark data...[/cyan]\n")

    engine = RecommendationEngine(db)
    recommendations = engine.recommend(
        task_type=task_type,
        budget_constraint=budget,
        model_size_pref=model_size_pref,
        limit=3,
    )

    if not recommendations:
        console.print("[yellow]No recommendations found matching your criteria.[/yellow]\n")
        console.print("Try:")
        console.print("  • Relaxing your budget constraint")
        console.print("  • Running more benchmarks to expand the database")
        console.print("  • Using a different task type filter\n")
        return

    # Display recommendations
    task_display = task_type.value.replace("_", " ").title()
    console.print(
        Panel.fit(
            f"[bold]Top {len(recommendations)} Recommendations for {task_display}[/bold]",
            border_style="green",
        )
    )
    console.print()

    for i, rec in enumerate(recommendations, 1):
        _display_recommendation(i, rec)

    console.print(f"\n[dim]Based on {len(all_results)} benchmark results[/dim]\n")


def _display_recommendation(rank: int, rec):
    """Display a single recommendation."""
    # Format GPU type nicely
    gpu_label = rec.gpu_type
    if "rtx6000" in gpu_label.lower():
        gpu_label = f"RTX 6000 Ada x{rec.gpu_count}"
    elif "rtx4000" in gpu_label.lower():
        gpu_label = f"RTX 4000 Ada x{rec.gpu_count}"

    # Truncate model name
    model_name = rec.model_id.split("/")[-1]
    if len(model_name) > 40:
        model_name = model_name[:37] + "..."

    # Create panel content
    lines = [
        f"[bold cyan]{rank}. {gpu_label} + {model_name}[/bold cyan]",
        "",
    ]

    # Performance metrics
    table = Table(show_header=False, box=None, padding=(0, 1))
    table.add_column("Metric", style="dim")
    table.add_column("Value", style="white")

    table.add_row("• Throughput", f"{rec.avg_tokens_per_sec:.1f} tokens/sec")
    table.add_row("• Cost per 1K tokens", f"${rec.cost_per_1k_tokens:.4f}")
    table.add_row("• Hourly cost", f"${rec.hourly_cost:.2f}")
    table.add_row("• VRAM", f"{rec.total_vram}GB total")
    table.add_row("• Cost efficiency", f"{rec.cost_efficiency:.1f} tok/sec per $/hr")

    # Confidence
    confidence_display = f"[{rec.confidence_color}]{rec.confidence_level}[/{rec.confidence_color}]"
    table.add_row(
        "• Confidence",
        f"{confidence_display} ({rec.num_benchmark_runs} benchmark runs)",
    )

    # Render table to string
    from io import StringIO
    from rich.console import Console as TempConsole

    temp_console = TempConsole(file=StringIO(), width=70, legacy_windows=False)
    temp_console.print(table)
    table_str = temp_console.file.getvalue()

    lines.append(table_str)

    # Add notes if any
    if rec.notes:
        lines.append("")
        for note in rec.notes:
            lines.append(f"[yellow]{note}[/yellow]")

    # Display panel
    console.print(
        Panel(
            "\n".join(lines),
            border_style=rec.confidence_color,
            padding=(0, 1),
        )
    )
    console.print()
