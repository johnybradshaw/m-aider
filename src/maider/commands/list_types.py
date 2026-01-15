"""List GPU types command."""

import sys
import click
from rich.console import Console
from rich.table import Table

from ..config import Config
from ..providers.linode import LinodeProvider

console = Console()


@click.command(name="list-types")
@click.option(
    "--region",
    help="Filter types by region",
    type=str,
)
@click.option(
    "--refresh",
    is_flag=True,
    help="Force refresh from API (bypass cache)",
)
def cmd(region, refresh):
    """List available GPU types from Linode API.

    Shows GPU types with specs, pricing, and regional availability.
    Useful for verifying runtime type enumeration.
    """
    console.print("\n[bold cyan]Fetching GPU types from Linode API...[/bold cyan]\n")

    # Load config to get API token
    try:
        config = Config()
        if not config.linode_token:
            console.print("[red]Error: LINODE_TOKEN not found in environment[/red]")
            console.print("Set LINODE_TOKEN or LINODE_CLI_TOKEN in .env")
            sys.exit(1)

        # Create provider instance
        provider = LinodeProvider(api_token=config.linode_token)

        # Force refresh if requested
        if refresh:
            provider._fetch_types_from_api(force_refresh=True)

        # Get VM types
        vm_types = provider.list_vm_types(region=region, gpu_only=True)

        if not vm_types:
            console.print(
                f"[yellow]No GPU types found{' for region ' + region if region else ''}[/yellow]"
            )
            sys.exit(1)

        # Display table
        table = Table(title=f"GPU Types{' in ' + region if region else ''}")
        table.add_column("Type ID", style="cyan")
        table.add_column("Name", style="green")
        table.add_column("GPUs", justify="right")
        table.add_column("VRAM/GPU", justify="right")
        table.add_column("Total VRAM", justify="right")
        table.add_column("Cost/Hour", justify="right", style="yellow")
        table.add_column("Regions", style="dim")

        for vm_type in vm_types:
            # Format regions (show first 3 + count)
            regions_str = ", ".join(sorted(vm_type.available_in_regions)[:3])
            if len(vm_type.available_in_regions) > 3:
                regions_str += f" +{len(vm_type.available_in_regions) - 3}"

            table.add_row(
                vm_type.id,
                vm_type.name,
                str(vm_type.gpus),
                f"{vm_type.vram_per_gpu}GB",
                f"{vm_type.total_vram}GB",
                f"${vm_type.hourly_cost:.2f}",
                regions_str,
            )

        console.print(table)
        console.print(f"\n[dim]Total: {len(vm_types)} GPU types[/dim]\n")

    except Exception as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)
