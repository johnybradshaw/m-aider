"""GPU monitoring and validation utilities."""

from dataclasses import dataclass
from typing import Optional

from .ssh_utils import SSHClient


@dataclass
class GPUInfo:
    """Information about a single GPU."""

    index: int
    name: str
    memory_used_mb: int
    memory_total_mb: int
    utilization_percent: int

    @property
    def memory_percent(self) -> float:
        """Calculate memory usage percentage."""
        return (self.memory_used_mb / self.memory_total_mb) * 100 if self.memory_total_mb > 0 else 0

    @property
    def is_idle(self) -> bool:
        """Check if GPU appears idle (< 10% memory usage)."""
        return self.memory_percent < 10


class GPUMonitor:
    """Monitor GPU status on remote host."""

    def __init__(self, ssh: SSHClient):
        """Initialize GPU monitor."""
        self.ssh = ssh

    def get_gpu_count(self) -> int:
        """Get number of GPUs on the host."""
        output = self.ssh.run_output("nvidia-smi --query-gpu=count --format=csv,noheader")
        if output:
            lines = output.strip().split("\n")
            return len(lines)
        return 0

    def get_gpu_info(self) -> list[GPUInfo]:
        """Get information about all GPUs."""
        query = "nvidia-smi --query-gpu=index,name,memory.used,memory.total,utilization.gpu --format=csv,noheader,nounits"
        output = self.ssh.run_output(query)

        if not output:
            return []

        gpus = []
        for line in output.strip().split("\n"):
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                try:
                    gpus.append(
                        GPUInfo(
                            index=int(parts[0]),
                            name=parts[1],
                            memory_used_mb=int(parts[2]),
                            memory_total_mb=int(parts[3]),
                            utilization_percent=int(parts[4]),
                        )
                    )
                except ValueError:
                    continue

        return gpus

    def check_tensor_parallelism(self) -> tuple[bool, str]:
        """Check if tensor parallelism is working (all GPUs have similar memory usage)."""
        gpus = self.get_gpu_info()

        if len(gpus) <= 1:
            return True, "Single GPU configuration"

        # Check if any GPU is idle
        idle_gpus = [gpu for gpu in gpus if gpu.is_idle]
        if idle_gpus:
            return False, f"{len(idle_gpus)} of {len(gpus)} GPUs appear idle"

        # Check memory variance
        memory_percentages = [gpu.memory_percent for gpu in gpus]
        avg = sum(memory_percentages) / len(memory_percentages)
        variance = sum((x - avg) ** 2 for x in memory_percentages) / len(memory_percentages)

        if variance < 100:  # Low variance indicates good distribution
            return True, f"All {len(gpus)} GPUs are active with similar memory usage"
        else:
            return False, "GPU memory usage varies significantly"

    def get_container_logs(self, container_name: str = "vllm", lines: int = 100) -> Optional[str]:
        """Get container logs."""
        # First get container name/ID
        get_container = (
            f"docker ps --format '{{{{.Names}}}}' | grep -E '{container_name}|llm' | head -n1"
        )
        container = self.ssh.run_output(get_container)

        if not container:
            return None

        container = container.strip()
        return self.ssh.run_output(f"docker logs --tail {lines} {container} 2>&1")

    def check_vllm_errors(self) -> dict[str, list[str]]:
        """Check vLLM logs for common errors."""
        logs = self.get_container_logs()
        if not logs:
            return {}

        errors = {
            "oom": [],
            "nccl": [],
            "tensor_parallel": [],
            "model_loading": [],
        }

        for line in logs.split("\n"):
            line_lower = line.lower()

            if any(x in line_lower for x in ["out of memory", "oom", "cuda error"]):
                errors["oom"].append(line.strip())

            if "nccl" in line_lower and any(x in line_lower for x in ["error", "warn", "fail"]):
                errors["nccl"].append(line.strip())

            if "tensor" in line_lower and "parallel" in line_lower:
                errors["tensor_parallel"].append(line.strip())

            if any(x in line_lower for x in ["runtimeerror", "failed to load"]):
                errors["model_loading"].append(line.strip())

        # Remove empty error categories
        return {k: v for k, v in errors.items() if v}

    def get_gpu_topology(self) -> Optional[str]:
        """Get GPU topology (NVLink/PCIe connectivity)."""
        return self.ssh.run_output("nvidia-smi topo -m")
