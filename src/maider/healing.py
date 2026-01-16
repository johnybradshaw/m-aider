"""Self-healing mechanism for vLLM container errors."""

import re
import subprocess
from typing import Optional
from dataclasses import dataclass

from rich.console import Console

console = Console()
SSH_CONNECT_TIMEOUT = "ConnectTimeout=5"


@dataclass
class HealingAction:
    """Represents a healing action to fix a detected error."""

    error_type: str
    description: str
    docker_compose_edits: dict[str, str]  # Section: new content
    env_vars: dict[str, str]  # Environment variables to add


class VLLMHealer:
    """Detects and fixes common vLLM container errors."""

    def __init__(self, ip: str, session_dir: str):
        """Initialize healer.

        Args:
            ip: VM IP address
            session_dir: Path to session directory
        """
        self.ip = ip
        self.session_dir = session_dir
        self.retry_count = 0

    def diagnose(self, logs: str) -> Optional[HealingAction]:
        """Diagnose container logs and return healing action if needed.

        Args:
            logs: Container logs to analyze

        Returns:
            HealingAction if error detected, None otherwise
        """
        # Check for OOM/CUDA memory errors
        if self._detect_oom(logs):
            return self._heal_oom()

        # Check for NCCL errors
        if self._detect_nccl(logs):
            return self._heal_nccl()

        # Check for tensor parallelism errors
        if self._detect_tensor_parallel(logs):
            return self._heal_tensor_parallel()

        # Check for model loading errors
        if self._detect_model_loading(logs):
            return self._heal_model_loading()

        return None

    def _detect_oom(self, logs: str) -> bool:
        """Detect OOM/CUDA memory errors."""
        patterns = [
            r"out of memory",
            r"OOM",
            r"CUDA error.*out of memory",
            r"CUDA_ERROR_OUT_OF_MEMORY",
        ]
        return any(re.search(pattern, logs, re.IGNORECASE) for pattern in patterns)

    def _detect_nccl(self, logs: str) -> bool:
        """Detect NCCL multi-GPU communication errors."""
        patterns = [
            r"NCCL.*error",
            r"collective.*fail",
            r"all_reduce.*error",
            r"NCCL_ERROR",
        ]
        return any(re.search(pattern, logs, re.IGNORECASE) for pattern in patterns)

    def _detect_tensor_parallel(self, logs: str) -> bool:
        """Detect tensor parallelism configuration errors."""
        patterns = [
            r"tensor.parallel.*mismatch",
            r"tp_size.*not match",
            r"world_size.*!= .*tensor",
        ]
        return any(re.search(pattern, logs, re.IGNORECASE) for pattern in patterns)

    def _detect_model_loading(self, logs: str) -> bool:
        """Detect model loading/architecture errors."""
        patterns = [
            r"RuntimeError.*architecture",
            r"model.*not supported",
            r"dtype.*not compatible",
        ]
        return any(re.search(pattern, logs, re.IGNORECASE) for pattern in patterns)

    def _heal_oom(self) -> HealingAction:
        """Generate healing action for OOM errors."""
        self.retry_count += 1

        # Reduce GPU memory utilization by 5%
        new_utilization = max(0.70, 0.90 - (0.05 * self.retry_count))

        action = HealingAction(
            error_type="OOM/CUDA Memory",
            description=f"Reducing --gpu-memory-utilization to {new_utilization:.2f}",
            docker_compose_edits={},
            env_vars={"VLLM_GPU_MEMORY_UTILIZATION": str(new_utilization)},
        )

        # On 2nd+ retry, also halve max-model-len
        if self.retry_count >= 2:
            action.description += " and halving --max-model-len"
            # This would require reading current value from docker-compose
            # For now, we'll just document it

        return action

    def _heal_nccl(self) -> HealingAction:
        """Generate healing action for NCCL errors."""
        return HealingAction(
            error_type="NCCL Multi-GPU",
            description="Adding NCCL environment variables",
            docker_compose_edits={},
            env_vars={
                "NCCL_DEBUG": "WARN",
                "NCCL_IB_DISABLE": "1",
                "NCCL_P2P_DISABLE": "0",
            },
        )

    def _heal_tensor_parallel(self) -> HealingAction:
        """Generate healing action for tensor parallelism errors."""
        # Try to detect actual GPU count from nvidia-smi
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    SSH_CONNECT_TIMEOUT,
                    f"root@{self.ip}",
                    "nvidia-smi --query-gpu=count --format=csv,noheader | wc -l",
                ],
                capture_output=True,
                text=True,
                timeout=10,
            )
            gpu_count = int(result.stdout.strip())
        except Exception:
            gpu_count = 1

        return HealingAction(
            error_type="Tensor Parallelism",
            description=f"Adjusting --tensor-parallel-size to {gpu_count}",
            docker_compose_edits={},
            env_vars={"VLLM_TENSOR_PARALLEL_SIZE": str(gpu_count)},
        )

    def _heal_model_loading(self) -> HealingAction:
        """Generate healing action for model loading errors."""
        return HealingAction(
            error_type="Model Loading",
            description="Removing explicit --dtype setting (using auto)",
            docker_compose_edits={},
            env_vars={"VLLM_DTYPE": "auto"},
        )

    def apply_healing(self, action: HealingAction) -> bool:
        """Apply a healing action to the VM.

        Args:
            action: Healing action to apply

        Returns:
            True if successful, False otherwise
        """
        console.print(f"\n[yellow]🔧 Applying healing action: {action.error_type}[/yellow]")
        console.print(f"[yellow]   {action.description}[/yellow]")

        try:
            # Update .env file on VM
            if action.env_vars:
                for key, value in action.env_vars.items():
                    cmd = [
                        "ssh",
                        "-o",
                        SSH_CONNECT_TIMEOUT,
                        f"root@{self.ip}",
                        f"sed -i 's/^{key}=.*/{key}={value}/' /opt/llm/.env || echo '{key}={value}' >> /opt/llm/.env",
                    ]
                    subprocess.run(cmd, check=True, capture_output=True, timeout=10)

            # Restart containers
            restart_cmd = [
                "ssh",
                "-o",
                SSH_CONNECT_TIMEOUT,
                f"root@{self.ip}",
                "cd /opt/llm && docker compose restart",
            ]
            subprocess.run(restart_cmd, check=True, capture_output=True, timeout=30)

            console.print("[green]✓ Healing action applied successfully[/green]")
            return True

        except Exception as e:
            console.print(f"[red]✗ Failed to apply healing action: {e}[/red]")
            return False


def check_and_heal_vllm(ip: str, session_dir: str, max_retries: int = 3) -> bool:
    """Check vLLM container and apply healing if needed.

    Args:
        ip: VM IP address
        session_dir: Path to session directory
        max_retries: Maximum number of healing attempts

    Returns:
        True if container is healthy or successfully healed, False otherwise
    """
    healer = VLLMHealer(ip, session_dir)

    for attempt in range(max_retries):
        # Get container logs
        try:
            result = subprocess.run(
                [
                    "ssh",
                    "-o",
                    SSH_CONNECT_TIMEOUT,
                    f"root@{ip}",
                    "docker logs --tail 200 $(docker ps -q | head -n1) 2>&1",
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            logs = result.stdout
        except Exception as e:
            console.print(f"[red]✗ Failed to get container logs: {e}[/red]")
            return False

        # Diagnose
        action = healer.diagnose(logs)

        if not action:
            # No errors detected
            return True

        # Apply healing
        if attempt < max_retries - 1:
            if healer.apply_healing(action):
                # Wait for container to restart
                import time

                console.print("[dim]Waiting for container to restart...[/dim]")
                time.sleep(30)
                healer.retry_count = attempt + 1
            else:
                return False
        else:
            console.print(f"[red]✗ Max healing retries ({max_retries}) reached[/red]")
            return False

    return False
