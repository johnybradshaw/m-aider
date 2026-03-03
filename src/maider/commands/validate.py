"""Validate configuration."""

import sys
import click

from ..config import Config
from ..output import console
from ..providers.base import ProviderType


def get_gpu_regions_for_provider(provider: str) -> set:
    """Get GPU-capable regions for a provider.

    Args:
        provider: Provider name (e.g., "linode")

    Returns:
        Set of GPU-capable region IDs
    """
    try:
        provider_type = ProviderType(provider.lower())
        # For now, only Linode is registered
        if provider_type == ProviderType.LINODE:
            from ..providers.linode import GPU_REGIONS

            return GPU_REGIONS
    except (ValueError, ImportError):
        pass

    # Return empty set for unknown providers
    return set()


# Backward compatibility: GPU_REGIONS for Linode (default provider)
# This is used by tests and maintains the original API
try:
    from ..providers.linode import GPU_REGIONS
except ImportError:
    GPU_REGIONS = set()


@click.command(name="validate")
def cmd():
    """Validate configuration in .env and .env.secrets."""
    config = Config()

    console.print("\n[bold]Configuration Validation[/bold]")
    console.print("═" * 50)

    errors = config.validate()

    # Check if region supports GPUs (provider-aware)
    gpu_regions = get_gpu_regions_for_provider(config.provider)
    if config.region and gpu_regions and config.region not in gpu_regions:
        errors.append(
            f"Region '{config.region}' does not support GPU instances for "
            f"provider '{config.provider}'. GPU regions: {', '.join(sorted(gpu_regions))}"
        )

    if errors:
        console.print("\n[red]✗ Configuration errors found:[/red]\n")
        for error in errors:
            console.print(f"  • {error}")
        console.print()
        sys.exit(1)

    # Show configuration
    gpu_count = config.get_gpu_count()
    hourly_cost = config.get_hourly_cost()

    console.print("\n[green]✓ Configuration is valid![/green]\n")
    console.print("[bold]Settings:[/bold]")
    console.print(f"  Region: {config.region}")
    console.print(f"  Type: {config.type} ({gpu_count} GPUs)")
    console.print(f"  Model: {config.model_id}")
    console.print(f"  Served as: {config.served_model_name}")
    console.print()
    console.print(f"  Tensor Parallel Size: {config.vllm_tensor_parallel_size}")
    console.print(f"  Max Model Length: {config.vllm_max_model_len}")
    console.print(f"  GPU Memory Utilization: {config.vllm_gpu_memory_utilization}")
    console.print(f"  Max Num Seqs: {config.vllm_max_num_seqs}")
    console.print()
    console.print(f"  Estimated cost: ${hourly_cost:.2f}/hour")
    console.print()

    # Validate tensor parallel size
    if config.vllm_tensor_parallel_size != gpu_count:
        console.print(
            f"[yellow]⚠ Warning:[/yellow] VLLM_TENSOR_PARALLEL_SIZE "
            f"({config.vllm_tensor_parallel_size}) doesn't match GPU count ({gpu_count})"
        )
        console.print(f"  Recommendation: Set VLLM_TENSOR_PARALLEL_SIZE={gpu_count}")
        console.print()
