"""Configuration management for Linode LLM Coder."""

import importlib.util
import os
import subprocess
from pathlib import Path
from typing import Optional

if importlib.util.find_spec("dotenv"):
    from dotenv import load_dotenv
else:

    def load_dotenv(path: Path | str) -> bool:
        """Minimal .env loader when python-dotenv is not installed."""
        env_path = Path(path)
        if not env_path.exists():
            return False

        for line in env_path.read_text().splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("#") or "=" not in stripped:
                continue
            key, value = (p.strip() for p in stripped.split("=", 1))
            if len(value) > 1 and value.startswith(("'", '"')) and value[0] == value[-1]:
                value = value[1:-1]
            os.environ.setdefault(key, value)
        return True


class Config:
    """Application configuration loaded from .env files."""

    def __init__(self, project_dir: Optional[Path] = None):
        """Initialize config from .env and .env.secrets."""
        self.project_dir = project_dir or Path.cwd()

        # Load .env and .env.secrets
        load_dotenv(self.project_dir / ".env")
        load_dotenv(self.project_dir / ".env.secrets")

        # Provider (default to Linode for backward compatibility)
        self.provider = os.getenv("PROVIDER", "linode").lower()

        # Required fields
        self.region = os.getenv("REGION")
        self.type = os.getenv("TYPE")
        self.firewall_id = os.getenv("FIREWALL_ID")
        self.model_id = os.getenv("MODEL_ID")

        # Optional fields with defaults
        self.served_model_name = os.getenv("SERVED_MODEL_NAME", "coder")
        self.vllm_tensor_parallel_size = int(os.getenv("VLLM_TENSOR_PARALLEL_SIZE", "1"))
        self.vllm_max_model_len = int(os.getenv("VLLM_MAX_MODEL_LEN", "16384"))
        self.vllm_gpu_memory_utilization = float(os.getenv("VLLM_GPU_MEMORY_UTILIZATION", "0.90"))
        self.vllm_max_num_seqs = int(os.getenv("VLLM_MAX_NUM_SEQS", "1"))
        self.vllm_dtype = os.getenv("VLLM_DTYPE", "auto")
        self.vllm_extra_args = os.getenv("VLLM_EXTRA_ARGS", "")
        self.vllm_image = os.getenv("VLLM_IMAGE", "vllm/vllm-openai:latest")
        self.openwebui_image = os.getenv("OPENWEBUI_IMAGE", "ghcr.io/open-webui/open-webui:main")
        self.vllm_port = int(os.getenv("VLLM_PORT", "8000"))
        self.webui_port = int(os.getenv("WEBUI_PORT", "3000"))
        self.perf_profile = os.getenv("PERF_PROFILE", "B").upper()
        self.enable_openwebui = os.getenv("ENABLE_OPENWEBUI", "true").lower() == "true"
        self.openwebui_auth = os.getenv("OPENWEBUI_AUTH", "true").lower() == "true"
        self.enable_hf_cache = os.getenv("ENABLE_HF_CACHE", "true").lower() == "true"
        self.enable_healthchecks = os.getenv("ENABLE_HEALTHCHECKS", "false").lower() == "true"
        self.enable_nccl_env = os.getenv("ENABLE_NCCL_ENV", "false").lower() == "true"

        # HuggingFace token (with 1Password support)
        hf_token = os.getenv("HUGGING_FACE_HUB_TOKEN", "")
        self.hf_token = self._resolve_secret(hf_token)

        # Linode API token
        self.linode_token = os.getenv("LINODE_TOKEN") or os.getenv("LINODE_CLI_TOKEN")
        # Backward compatibility alias
        self.api_token = self.linode_token

        # Watchdog settings
        self.watchdog_enabled = os.getenv("WATCHDOG_ENABLED", "false").lower() == "true"
        self.watchdog_timeout_minutes = int(os.getenv("WATCHDOG_TIMEOUT_MINUTES", "30"))
        self.watchdog_warning_minutes = int(os.getenv("WATCHDOG_WARNING_MINUTES", "5"))

    def _resolve_secret(self, value: str) -> str:
        """Resolve 1Password CLI references (op://...)."""
        if value.startswith("op://"):
            try:
                result = subprocess.run(
                    ["op", "read", value],
                    capture_output=True,
                    text=True,
                    check=True,
                )
                return result.stdout.strip()
            except (subprocess.CalledProcessError, FileNotFoundError):
                # Fall back to plain value if op CLI not available
                return value
        return value

    def validate(self) -> list[str]:
        """Validate required configuration fields."""
        errors = []

        if not self.region:
            errors.append("REGION is required in .env")
        if not self.type:
            errors.append("TYPE is required in .env")
        if not self.firewall_id:
            errors.append("FIREWALL_ID is required in .env")
        if not self.model_id:
            errors.append("MODEL_ID is required in .env")
        if not self.hf_token:
            errors.append("HUGGING_FACE_HUB_TOKEN is required in .env.secrets")
        if not self.linode_token:
            errors.append("LINODE_TOKEN or LINODE_CLI_TOKEN is required")

        return errors

    def get_gpu_count(self) -> int:
        """Detect GPU count from VM type.

        For Linode provider, uses LinodeProvider.get_gpu_count().
        Falls back to regex pattern matching for unknown providers.
        """
        if self.provider == "linode" and self.linode_token:
            try:
                from .providers.linode import LinodeProvider

                provider = LinodeProvider(api_token=self.linode_token)
                return provider.get_gpu_count(self.type)
            except Exception:
                # Fall through to regex fallback
                pass

        # Fallback: regex pattern matching
        import re

        # Try pattern like a4, a2, etc
        match = re.search(r"a(\d+)-", self.type)
        if match:
            return int(match.group(1))

        # Try pattern like -4, -2, etc
        match = re.search(r"-(\d+)$", self.type)
        if match:
            return int(match.group(1))

        return 1

    def get_hourly_cost(self) -> float:
        """Get hourly cost for the instance type.

        For Linode provider, uses LinodeProvider.get_hourly_cost().
        Returns 0.0 for unknown providers or types.
        """
        if self.provider == "linode" and self.linode_token:
            try:
                from .providers.linode import LinodeProvider

                provider = LinodeProvider(api_token=self.linode_token)
                return provider.get_hourly_cost(self.type)
            except Exception:
                # Fall through to fallback
                pass

        # Fallback: return 0.0 for unknown providers
        return 0.0
