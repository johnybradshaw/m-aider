"""Switch model on a running VM."""

import sys
import time
import subprocess
from pathlib import Path

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import Config
from ..compose import ComposeRuntime
from ..model_validation import validate_max_model_len
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
    config = Config()
    session_mgr = SessionManager()
    session = _get_session_or_exit(session_mgr, session_name)

    served_name = _resolve_served_name(config, session, model_id, served_model_name)
    final_max_model_len = max_model_len or config.vllm_max_model_len
    final_tensor_parallel = tensor_parallel_size or config.vllm_tensor_parallel_size

    # Validate max_model_len against model's actual limits
    final_max_model_len = _validate_and_adjust_max_len(
        model_id, final_max_model_len, config.hf_token
    )

    _print_plan(session, model_id, served_name, final_max_model_len, final_tensor_parallel)
    _confirm_switch()

    runtime, docker_compose, runtime_env = _build_runtime(
        config, model_id, served_name, final_max_model_len, final_tensor_parallel
    )
    console.print("\n[bold]Updating VM configuration...[/bold]")
    _upload_runtime(session.ip, docker_compose, runtime_env)
    _restart_containers(session.ip)

    # Update session and local metadata early so they're consistent even if API check times out
    console.print("\n[bold]Updating local metadata...[/bold]")
    _generate_aider_metadata(served_name, final_max_model_len)
    _update_session_model(session_mgr, session, model_id, served_name)

    _wait_for_api(session.ip, runtime)
    _verify_model(session.ip, runtime.vllm_port, served_name)

    console.print(f"\n[green]✓[/green] Successfully switched to {model_id}")
    console.print("\n[dim]Restart aider to use the new model[/dim]")


def _get_session_or_exit(session_mgr: SessionManager, session_name: str | None):
    if session_name:
        session = session_mgr.get_session(session_name)
        if not session:
            console.print(f"[red]Session '{session_name}' not found[/red]")
            sys.exit(1)
        return session

    session = session_mgr.get_current_session()
    if not session:
        console.print("[red]No current session set[/red]")
        console.print("Run: [cyan]maider use <session>[/cyan]")
        sys.exit(1)
    return session


def _resolve_served_name(
    config: Config,
    session,
    model_id: str,
    served_model_name: str | None,
) -> str:
    if served_model_name:
        return served_model_name
    if session.served_model_name:
        return session.served_model_name
    if config.served_model_name:
        return config.served_model_name
    return model_id.split("/")[-1].lower()


def _validate_and_adjust_max_len(
    model_id: str,
    max_model_len: int,
    hf_token: str | None,
) -> int:
    """Validate max_model_len against the model's actual limits.

    If the value exceeds the model's max_position_embeddings, prompts the user
    to use a corrected value, override anyway, or cancel.

    Returns:
        The validated (possibly adjusted) max_model_len value
    """
    console.print("\n[bold]Validating model configuration...[/bold]")

    result = validate_max_model_len(model_id, max_model_len, hf_token)

    if result.is_valid:
        if result.warning:
            console.print(f"[yellow]Warning:[/yellow] {result.warning}")
        else:
            console.print(
                f"[green]✓[/green] max_model_len={max_model_len} is valid "
                f"(model limit: {result.model_max_len})"
            )
        return max_model_len

    # Validation failed - max_model_len exceeds model limits
    console.print("\n[red]Configuration Error:[/red]")
    console.print(
        f"  max_model_len={max_model_len} exceeds the model's "
        f"max_position_embeddings={result.model_max_len}"
    )
    console.print("\n  This will cause vLLM to fail with a validation error unless you set")
    console.print("  VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 (which can cause NaN values or crashes)")

    console.print("\n[bold]Options:[/bold]")
    console.print(f"  [1] Use suggested value: {result.suggested_max_len} (Recommended)")
    console.print("  [2] Override anyway (risky - may cause NaN or crashes)")
    console.print("  [3] Cancel")

    while True:
        choice = input("\nSelect option [1/2/3]: ").strip()
        if choice == "1":
            console.print(f"[green]✓[/green] Using max_model_len={result.suggested_max_len}")
            return result.suggested_max_len
        elif choice == "2":
            console.print(
                f"[yellow]Warning:[/yellow] Proceeding with max_model_len={max_model_len}"
            )
            console.print(
                "  vLLM will require VLLM_ALLOW_LONG_MAX_MODEL_LEN=1 environment variable"
            )
            return max_model_len
        elif choice == "3":
            console.print("Cancelled")
            sys.exit(0)
        else:
            console.print("[red]Invalid choice. Please enter 1, 2, or 3.[/red]")


def _print_plan(session, model_id: str, served_name: str, max_len: int, tensor_parallel: int):
    console.print(f"\n[bold]Switching model for session: {session.name}[/bold]")
    console.print(f"  Current: {session.model_id}")
    console.print(f"  New: {model_id}")
    console.print(f"  Served as: {served_name}")
    console.print(f"  Max tokens: {max_len}")
    console.print(f"  Tensor parallel: {tensor_parallel}")


def _confirm_switch():
    response = input("\nProceed? [y/N]: ")
    if response.lower() != "y":
        console.print("Cancelled")
        sys.exit(0)


def _build_runtime(
    config: Config, model_id: str, served_name: str, max_len: int, tensor_parallel: int
) -> tuple[ComposeRuntime, str, str]:
    from dataclasses import replace

    from ..compose import render_compose, render_runtime_env, runtime_from_config

    runtime: ComposeRuntime = runtime_from_config(
        config, model_id=model_id, served_model_name=served_name
    )
    runtime = replace(
        runtime,
        vllm_max_model_len=max_len,
        vllm_tensor_parallel_size=tensor_parallel,
    )
    docker_compose = render_compose(runtime)
    runtime_env = render_runtime_env(runtime, config.hf_token)
    return runtime, docker_compose, runtime_env


def _upload_runtime(ip: str, docker_compose: str, runtime_env: str):
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        _upload_compose(ip, docker_compose, progress)
        _upload_env(ip, runtime_env, progress)


def _upload_compose(ip: str, docker_compose: str, progress: Progress):
    task = progress.add_task("Uploading new docker-compose.yml...", total=None)
    _upload_temp_file(
        content=docker_compose,
        suffix=".yml",
        remote_path=f"root@{ip}:/opt/llm/docker-compose.yml",
    )
    progress.update(task, completed=True)


def _upload_env(ip: str, runtime_env: str, progress: Progress):
    task = progress.add_task("Uploading .env...", total=None)
    _upload_temp_file(
        content=runtime_env,
        suffix=".env",
        remote_path=f"root@{ip}:/opt/llm/.env",
    )
    progress.update(task, completed=True)


def _upload_temp_file(content: str, suffix: str, remote_path: str):
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False) as temp_file:
        temp_file.write(content)
        temp_path = temp_file.name

    try:
        result = subprocess.run(
            ["scp", temp_path, remote_path],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            console.print(f"[red]Failed to upload: {result.stderr}[/red]")
            sys.exit(1)
    finally:
        Path(temp_path).unlink()


def _restart_containers(ip: str):
    console.print("[bold]Restarting containers...[/bold]")
    try:
        result = subprocess.run(
            ["ssh", f"root@{ip}", "cd /opt/llm && docker compose down && docker compose up -d"],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            console.print(f"[red]Failed to restart: {result.stderr}[/red]")
            sys.exit(1)
    except subprocess.TimeoutExpired:
        console.print(
            "[yellow]⚠ docker compose restart timed out; falling back to systemctl[/yellow]"
        )
        try:
            result = subprocess.run(
                ["ssh", f"root@{ip}", "systemctl restart vllm"],
                capture_output=True,
                text=True,
                timeout=60,
            )
            if result.returncode != 0:
                console.print(f"[red]Failed to restart via systemctl: {result.stderr}[/red]")
                sys.exit(1)
        except subprocess.TimeoutExpired:
            console.print("[red]Fallback restart via systemctl also timed out.[/red]")
            sys.exit(1)


def _wait_for_api(ip: str, runtime: ComposeRuntime):
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
                        f"root@{ip}",
                        f"curl -s http://localhost:{runtime.vllm_port}/v1/models",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                # Check for valid vLLM response - the /v1/models endpoint returns
                # {"object": "list", "data": [...]} when ready
                if result.returncode == 0 and '"data"' in result.stdout:
                    progress.update(task, completed=True)
                    break
            except subprocess.TimeoutExpired:
                pass

            time.sleep(5)
        else:
            console.print("[yellow]⚠ Timeout waiting for API[/yellow]")
            console.print("[dim]The model may still be loading. Check status with:[/dim]")
            console.print(f"  [cyan]ssh root@{ip} docker logs -f vllm[/cyan]")
            # Don't exit - session metadata is already updated

    console.print("[green]✓[/green] API ready")


def _verify_model(ip: str, vllm_port: int, served_name: str):
    console.print("\n[bold]Verifying model...[/bold]")
    result = subprocess.run(
        ["ssh", f"root@{ip}", f"curl -s http://localhost:{vllm_port}/v1/models"],
        capture_output=True,
        text=True,
    )

    if served_name in result.stdout:
        console.print(f"[green]✓[/green] Model loaded: {served_name}")
    else:
        console.print("[yellow]⚠[/yellow] Model name not found in API response")
        console.print(f"Response: {result.stdout}")


def _update_session_model(session_mgr: SessionManager, session, model_id: str, served_name: str):
    session_mgr.update_session_model(session.name, model_id, served_name)
    refreshed_session = session_mgr.get_session(session.name)
    if refreshed_session:
        session_mgr.set_current_session(refreshed_session)


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
