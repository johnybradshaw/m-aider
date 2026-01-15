#!/usr/bin/env python3
"""CLI entry point for Linode LLM Coder."""

import sys
import click
from rich.console import Console

from .commands import (
    up,
    down,
    list_vms,
    list_types,
    status,
    validate,
    check,
    validate_perf,
    wizard,
    use,
    cleanup,
    extend,
    switch_model,
    tunnel,
    benchmark,
    benchmark_collect,
    benchmark_compare,
    benchmark_status,
    recommend,
)

console = Console()


@click.group()
@click.version_option()
def main():
    """Linode GPU vLLM deployment tool for multi-card setups."""
    pass


# Register commands
main.add_command(wizard.cmd)
main.add_command(up.cmd)
main.add_command(down.cmd)
main.add_command(list_vms.cmd)
main.add_command(list_types.cmd)
main.add_command(status.cmd)
main.add_command(use.cmd)
main.add_command(cleanup.cmd)
main.add_command(extend.cmd)
main.add_command(switch_model.cmd)
main.add_command(tunnel.cmd)
main.add_command(validate.cmd)
main.add_command(check.cmd)
main.add_command(validate_perf.cmd)

# Benchmark commands
main.add_command(benchmark.cmd)
main.add_command(benchmark_collect.cmd)
main.add_command(benchmark_compare.cmd)
main.add_command(benchmark_status.cmd)
main.add_command(recommend.cmd)


if __name__ == "__main__":
    sys.exit(main())
