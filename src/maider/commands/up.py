"""Create and configure a new VM."""

import sys
import time
import subprocess
from pathlib import Path

import click
import requests
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ..config import Config
from ..linode_client import LinodeManager
from ..session import SessionManager
from ..watchdog import start_watchdog_background
from ..healing import check_and_heal_vllm

console = Console()
PROGRESS_TEXT = "[progress.description]{task.description}"
SSH_CONNECT_TIMEOUT = "ConnectTimeout=5"
SSH_STRICT_HOST_KEY = "StrictHostKeyChecking=no"


@click.command(name="up")
@click.argument("name", required=False)
@click.option("--launch-aider", "-a", is_flag=True, help="Launch aider automatically when ready")
def cmd(name: str, launch_aider: bool):
    """Create and configure a new GPU VM.

    NAME: Optional session name (auto-generated if not provided)
    """
    config = Config()
    _validate_config_or_exit(config)

    gpu_count = _sync_tensor_parallel(config)
    hourly_cost = config.get_hourly_cost()
    _print_config(config, gpu_count, hourly_cost)

    session_mgr = SessionManager()
    linode_mgr = LinodeManager(config)

    name = name or session_mgr.generate_session_name(config.model_id)
    console.print(f"Created session: [cyan]{name}[/cyan]\n")

    instance = _create_instance_or_exit(linode_mgr, name)
    session = _create_session(session_mgr, name, instance, config, hourly_cost)
    session_mgr.set_current_session(session)

    _wait_for_ssh_or_exit(instance.ipv4[0])
    _wait_for_cloud_init_or_exit(instance.ipv4[0])
    console.print("\n[bold]Setting up SSH tunnel...[/bold]")
    _setup_ssh_tunnel(instance.ipv4[0], config)

    vllm_ready = _wait_for_vllm_ready(session, config, name, instance.ipv4[0])
    if vllm_ready:
        _generate_aider_metadata(session.served_model_name, config.vllm_max_model_len)

    _print_access(config, hourly_cost)
    _start_watchdog_if_enabled(session, config)
    _finish_or_launch(session, config, launch_aider)


def _validate_config_or_exit(config: Config):
    errors = config.validate()
    if not errors:
        return
    console.print("[red]Configuration errors:[/red]")
    for error in errors:
        console.print(f"  • {error}")
    sys.exit(1)


def _sync_tensor_parallel(config: Config) -> int:
    gpu_count = config.get_gpu_count()
    if config.vllm_tensor_parallel_size != gpu_count:
        console.print(
            f"[yellow]Warning:[/yellow] VLLM_TENSOR_PARALLEL_SIZE ({config.vllm_tensor_parallel_size}) "
            f"doesn't match GPU count ({gpu_count})"
        )
        console.print(f"Auto-correcting to {gpu_count}")
        config.vllm_tensor_parallel_size = gpu_count
    return gpu_count


def _print_config(config: Config, gpu_count: int, hourly_cost: float):
    console.print("\n[bold]Configuration:[/bold]")
    console.print(f"  Region: {config.region}")
    console.print(f"  Type: {config.type} ({gpu_count} GPUs)")
    console.print(f"  Model: {config.model_id}")
    console.print(f"  Cost: ${hourly_cost:.2f}/hour\n")


def _create_instance_or_exit(linode_mgr: LinodeManager, name: str):
    try:
        return linode_mgr.create_instance(f"llm-{name}")
    except Exception as e:
        console.print(f"[red]Failed to create VM: {e}[/red]")
        sys.exit(1)


def _create_session(
    session_mgr: SessionManager,
    name: str,
    instance,
    config: Config,
    hourly_cost: float,
):
    session = session_mgr.create_session(
        name=name,
        linode_id=instance.id,
        ip=instance.ipv4[0],
        vm_type=config.type,
        hourly_cost=hourly_cost,
        model_id=config.model_id,
        served_model_name=config.served_model_name,
    )
    console.print(f"\n[green]✓[/green] VM created: {instance.ipv4[0]}")
    return session


def _wait_for_ssh_or_exit(ip: str):
    console.print("\n[bold]Waiting for SSH...[/bold] (this may take 10-15 minutes)")
    if _wait_for_ssh(ip, timeout=1200):
        console.print("[green]✓[/green] SSH ready")
        return
    console.print("[red]✗ SSH timeout[/red]")
    sys.exit(1)


def _wait_for_cloud_init_or_exit(ip: str):
    console.print("\n[bold]Waiting for cloud-init to complete...[/bold]")
    console.print("[dim]Installing Docker, NVIDIA drivers, and starting containers[/dim]\n")

    if _wait_for_cloud_init(ip, timeout=1800):
        console.print("[green]✓[/green] Cloud-init completed successfully")
        return

    console.print("[red]✗ Cloud-init timeout or failed[/red]")
    console.print(f"Check logs with: ssh root@{ip} 'cat /var/log/cloud-init-output.log'")
    sys.exit(1)


def _wait_for_vllm_ready(session, config: Config, name: str, ip: str) -> bool:
    console.print("\n[bold]Waiting for vLLM API...[/bold]")
    console.print("[dim]This may take 10-20 minutes while the model downloads and loads[/dim]\n")

    vllm_ready = _wait_for_vllm(session.served_model_name, config, timeout=1800)
    if vllm_ready:
        console.print("[green]✓[/green] vLLM API is ready!")
        return True

    console.print("[yellow]⚠ vLLM API timeout - attempting self-healing...[/yellow]")
    session_dir = Path.home() / ".cache" / "linode-vms" / name
    if check_and_heal_vllm(ip, str(session_dir), max_retries=3):
        console.print("[green]✓[/green] vLLM API is ready after healing!")
        return True

    console.print("[yellow]⚠ Self-healing failed - model may still be loading[/yellow]")
    console.print(f"Check status with: ssh root@{ip} 'docker logs -f \\$(docker ps -q)'")
    return False


def _print_access(config: Config, hourly_cost: float):
    console.print("\n[green]✓ Your VM is ready![/green] (${:.2f}/hour)\n".format(hourly_cost))
    console.print("[bold]Access:[/bold]")
    if config.enable_openwebui:
        console.print(f"  • Open WebUI: http://localhost:{config.webui_port}")
    console.print(f"  • vLLM API: http://localhost:{config.vllm_port}/v1\n")


def _start_watchdog_if_enabled(session, config: Config):
    if not config.watchdog_enabled:
        return
    console.print("[bold]Starting watchdog...[/bold]")
    console.print(
        f"[dim]VM will auto-destroy after {config.watchdog_timeout_minutes} minutes of inactivity[/dim]\n"
    )

    try:
        pid = start_watchdog_background(
            session,
            timeout_minutes=config.watchdog_timeout_minutes,
            warning_minutes=config.watchdog_warning_minutes,
        )
        console.print(f"[green]✓[/green] Watchdog started (PID: {pid})")
        console.print(f"  • Idle timeout: {config.watchdog_timeout_minutes} minutes")
        console.print(f"  • Warning: {config.watchdog_warning_minutes} minutes before destruction\n")
    except Exception as e:
        console.print(f"[yellow]⚠ Failed to start watchdog: {e}[/yellow]\n")


def _finish_or_launch(session, config: Config, launch_aider: bool):
    if launch_aider:
        _launch_aider_session(session, config)
        return

    console.print("[bold]Next steps:[/bold]")
    console.print("  source .aider-env")
    console.print('  aider --model "$AIDER_MODEL"')
    console.print("\nOr run: coder up --launch-aider to auto-launch next time\n")


def _wait_for_ssh(ip: str, timeout: int = 1200) -> bool:
    """Wait for SSH to become available."""
    start = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn(PROGRESS_TEXT),
        console=console,
    ) as progress:
        progress.add_task("Waiting for SSH...", total=None)

        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    [
                        "ssh",
                        "-o",
                        SSH_CONNECT_TIMEOUT,
                        "-o",
                        SSH_STRICT_HOST_KEY,
                        f"root@{ip}",
                        "echo ready",
                    ],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    return True
            except subprocess.TimeoutExpired:
                pass

            time.sleep(5)

    return False


def _setup_ssh_tunnel(ip: str, config: Config):
    """Setup SSH tunnel for vLLM and WebUI."""
    control_path = Path.home() / ".ssh" / f"llm-master-root@{ip}"

    # Close existing tunnel if any
    subprocess.run(
        ["ssh", "-O", "exit", "-o", f"ControlPath={control_path}", f"root@{ip}"],
        capture_output=True,
    )

    # Create new tunnel
    tunnel_cmd = [
        "ssh",
        "-fNM",
        "-o",
        f"ControlPath={control_path}",
        "-o",
        SSH_STRICT_HOST_KEY,
        "-L",
        f"{config.vllm_port}:localhost:{config.vllm_port}",
    ]
    if config.enable_openwebui:
        tunnel_cmd.extend(["-L", f"{config.webui_port}:localhost:{config.webui_port}"])
    tunnel_cmd.append(f"root@{ip}")

    subprocess.run(tunnel_cmd, check=True)

    console.print("[green]✓[/green] SSH tunnel established")


def _wait_for_cloud_init(ip: str, timeout: int = 1800) -> bool:
    """Wait for cloud-init to complete."""
    start = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn(PROGRESS_TEXT),
        console=console,
    ) as progress:
        progress.add_task("Waiting for cloud-init...", total=None)

        while time.time() - start < timeout:
            try:
                result = subprocess.run(
                    [
                        "ssh",
                        "-o",
                        SSH_CONNECT_TIMEOUT,
                        "-o",
                        SSH_STRICT_HOST_KEY,
                        f"root@{ip}",
                        "cloud-init status --wait",
                    ],
                    capture_output=True,
                    timeout=60,
                )
                if result.returncode == 0:
                    # Check if it completed successfully
                    status_result = subprocess.run(
                        ["ssh", "-o", SSH_CONNECT_TIMEOUT, f"root@{ip}", "cloud-init status"],
                        capture_output=True,
                        text=True,
                    )
                    if "done" in status_result.stdout.lower():
                        return True
                    elif "error" in status_result.stdout.lower():
                        console.print(f"\n[red]Cloud-init failed:[/red] {status_result.stdout}")
                        return False
            except subprocess.TimeoutExpired:
                pass

            time.sleep(10)

    return False


def _wait_for_vllm(model_name: str, config: Config, timeout: int = 1800) -> bool:
    """Wait for vLLM API to be ready and serving the model."""
    start = time.time()

    with Progress(
        SpinnerColumn(),
        TextColumn(PROGRESS_TEXT),
        console=console,
    ) as progress:
        progress.add_task("Waiting for vLLM...", total=None)

        while time.time() - start < timeout:
            try:
                # Check if API is responding
                response = requests.get(
                    f"http://localhost:{config.vllm_port}/v1/models",
                    timeout=5,
                )

                if response.status_code == 200:
                    data = response.json()
                    models = [m.get("id") for m in data.get("data", [])]

                    if model_name in models:
                        # Try a test completion to ensure it's fully loaded
                        test_response = requests.post(
                            f"http://localhost:{config.vllm_port}/v1/completions",
                            json={
                                "model": model_name,
                                "prompt": "test",
                                "max_tokens": 1,
                            },
                            timeout=30,
                        )
                        if test_response.status_code == 200:
                            return True

            except (requests.exceptions.RequestException, Exception):
                pass

            time.sleep(10)

    return False


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


def _launch_aider_session(session, config: Config):
    """Launch aider with environment variables set."""
    import os

    console.print("\n[bold]Launching aider...[/bold]\n")

    # Set environment variables
    env = os.environ.copy()
    env["OPENAI_API_BASE"] = f"http://localhost:{config.vllm_port}/v1"
    env["OPENAI_API_KEY"] = "sk-dummy"
    env["AIDER_MODEL"] = f"openai/{session.served_model_name}"

    # Try to launch aider
    try:
        # Use execvpe to replace current process with aider
        # This way the environment is inherited properly
        os.execvpe("aider", ["aider", "--model", f"openai/{session.served_model_name}"], env)
    except FileNotFoundError:
        console.print("[red]✗ aider not found in PATH[/red]")
        console.print("\nInstall aider with: pip install aider-chat")
        console.print("\nThen run:")
        console.print("  source .aider-env")
        console.print('  aider --model "$AIDER_MODEL"\n')
        sys.exit(1)
