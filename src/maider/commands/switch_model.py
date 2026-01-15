"""Switch model on a running VM."""

import sys
import time
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import Config
from ..session import SessionManager

console = Console()


@click.command(name="switch-model")
@click.argument("model_id")
@click.argument("session_name", required=False)
@click.option("--max-model-len", type=int, help="Override max model length")
@click.option("--tensor-parallel-size", type=int, help="Override tensor parallel size")
@click.option("--served-model-name", help="Override served model name (default: keep current)")
def cmd(
    model_id: str,
    session_name: str | None = None,
    max_model_len: int | None = None,
    tensor_parallel_size: int | None = None,
    served_model_name: str | None = None,
):
    """Switch to a different model on a running VM.

    MODEL_ID: HuggingFace model ID (e.g., Qwen/Qwen2.5-Coder-14B-Instruct-AWQ)
    SESSION_NAME: Name of session (current session if not specified)
    """
    # Load configuration
    config = Config()
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
            console.print("Run: [cyan]coder use <session>[/cyan]")
            sys.exit(1)

    console.print(f"\n[bold]Switching model for session: {session.name}[/bold]")
    console.print(f"  Current: {session.model_id}")
    console.print(f"  New: {model_id}")

    if served_model_name:
        served_name = served_model_name
    elif session.served_model_name:
        served_name = session.served_model_name
    elif config.served_model_name:
        served_name = config.served_model_name
    else:
        served_name = model_id.split("/")[-1].lower()

    # Use overrides or fall back to config
    final_max_model_len = max_model_len or config.vllm_max_model_len
    final_tensor_parallel = tensor_parallel_size or config.vllm_tensor_parallel_size

    console.print(f"  Served as: {served_name}")
    console.print(f"  Max tokens: {final_max_model_len}")
    console.print(f"  Tensor parallel: {final_tensor_parallel}")

    # Confirm
    response = input("\nProceed? [y/N]: ")
    if response.lower() != "y":
        console.print("Cancelled")
        sys.exit(0)

    from dataclasses import replace

    from ..compose import render_compose, render_runtime_env, runtime_from_config

    runtime = runtime_from_config(config, model_id=model_id, served_model_name=served_name)
    runtime = replace(
        runtime,
        vllm_max_model_len=final_max_model_len,
        vllm_tensor_parallel_size=final_tensor_parallel,
    )
    docker_compose = render_compose(runtime)
    runtime_env = render_runtime_env(runtime, config.hf_token)

    console.print("\n[bold]Updating VM configuration...[/bold]")

    # Write docker-compose.yml to VM
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Uploading new docker-compose.yml...", total=None)

        # Create temp file
        import tempfile

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write(docker_compose)
            temp_path = f.name

        try:
            # Upload to VM
            result = subprocess.run(
                ["scp", temp_path, f"root@{session.ip}:/opt/llm/docker-compose.yml"],
                capture_output=True,
                text=True,
            )
            if result.returncode != 0:
                console.print(f"[red]Failed to upload: {result.stderr}[/red]")
                sys.exit(1)
        finally:
            Path(temp_path).unlink()

        progress.update(task, completed=True)

        task = progress.add_task("Uploading .env...", total=None)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".env", delete=False) as env_file:
            env_file.write(runtime_env)
            env_path = env_file.name

        try:
            env_result = subprocess.run(
                ["scp", env_path, f"root@{session.ip}:/opt/llm/.env"],
                capture_output=True,
                text=True,
            )
            if env_result.returncode != 0:
                console.print(f"[red]Failed to upload .env: {env_result.stderr}[/red]")
                sys.exit(1)
        finally:
            Path(env_path).unlink()

        progress.update(task, completed=True)

    # Restart containers
    console.print("[bold]Restarting containers...[/bold]")
    result = subprocess.run(
        ["ssh", f"root@{session.ip}", "cd /opt/llm && docker compose down && docker compose up -d"],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        console.print(f"[red]Failed to restart: {result.stderr}[/red]")
        sys.exit(1)

    # Wait for vLLM API
    console.print("\n[bold]Waiting for vLLM API...[/bold]")
    console.print("[dim](This may take 10-20 minutes for model download)[/dim]")

    max_wait = 1200  # 20 minutes
    start_time = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task = progress.add_task("Waiting for API to respond...", total=None)

        while time.time() - start_time < max_wait:
            try:
                result = subprocess.run(
                    [
                        "ssh",
                        f"root@{session.ip}",
                        f"curl -s http://localhost:{runtime.vllm_port}/v1/models",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and "models" in result.stdout:
                    progress.update(task, completed=True)
                    break
            except subprocess.TimeoutExpired:
                pass

            time.sleep(5)
        else:
            console.print("[red]Timeout waiting for API[/red]")
            console.print(
                "Check logs with: [cyan]ssh root@{} docker logs vllm[/cyan]".format(session.ip)
            )
            sys.exit(1)

    console.print("[green]✓[/green] API ready")

    # Verify model loaded
    console.print("\n[bold]Verifying model...[/bold]")
    result = subprocess.run(
        ["ssh", f"root@{session.ip}", f"curl -s http://localhost:{runtime.vllm_port}/v1/models"],
        capture_output=True,
        text=True,
    )

    if served_name in result.stdout:
        console.print(f"[green]✓[/green] Model loaded: {served_name}")
    else:
        console.print(f"[yellow]⚠[/yellow] Model name not found in API response")
        console.print(f"Response: {result.stdout}")

    # Update local .aider.model.metadata.json
    console.print("\n[bold]Updating local metadata...[/bold]")
    _generate_aider_metadata(served_name, final_max_model_len)

    # Update session state with new model info
    session_mgr.update_session_model(session.name, model_id, served_name)
    refreshed_session = session_mgr.get_session(session.name)
    if refreshed_session:
        session_mgr.set_current_session(refreshed_session)

    console.print(f"\n[green]✓[/green] Successfully switched to {model_id}")
    console.print("\n[dim]Restart aider to use the new model[/dim]")


def _generate_aider_metadata(model_name: str, max_model_len: int):
    """Generate .aider.model.metadata.json for token limits."""
    import json

    metadata = {
        f"openai/{model_name}": {
            "max_tokens": max_model_len,
            "max_input_tokens": max_model_len,
            "max_output_tokens": max_model_len // 2,
            "input_cost_per_token": 0,
            "output_cost_per_token": 0,
            "litellm_provider": "openai",
            "mode": "chat",
        }
    }

    metadata_path = Path.cwd() / ".aider.model.metadata.json"
    metadata_path.write_text(json.dumps(metadata, indent=2))

    console.print("[green]✓[/green] Generated .aider.model.metadata.json")
