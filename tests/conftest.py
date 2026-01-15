"""Pytest configuration and fixtures."""

import os
import tempfile
from pathlib import Path
from typing import Generator

import pytest


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_env_file(temp_dir: Path) -> Path:
    """Create a mock .env file."""
    env_file = temp_dir / ".env"
    env_file.write_text(
        """FIREWALL_ID=12345
REGION=us-east
TYPE=g1-gpu-rtx6000-1
IMAGE=linode/ubuntu24.04
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
SERVED_MODEL_NAME=coder
VLLM_MAX_MODEL_LEN=32768
VLLM_GPU_MEMORY_UTILIZATION=0.90
VLLM_MAX_NUM_SEQS=1
VLLM_TENSOR_PARALLEL_SIZE=1
VLLM_DTYPE=auto
"""
    )
    return env_file


@pytest.fixture
def mock_secrets_file(temp_dir: Path) -> Path:
    """Create a mock .env.secrets file."""
    secrets_file = temp_dir / ".env.secrets"
    secrets_file.write_text("HUGGING_FACE_HUB_TOKEN=hf_test_token_123\n")
    return secrets_file


@pytest.fixture
def mock_session_data() -> dict:
    """Return mock session data.

    Includes both provider_instance_id (new) and linode_id (old)
    for backward compatibility during refactoring.
    """
    return {
        "name": "test-session",
        "provider_instance_id": "12345678",  # New field
        "linode_id": 12345678,  # Old field for backward compatibility
        "ip": "192.0.2.1",
        "type": "g1-gpu-rtx6000-1",
        "hourly_cost": 1.50,
        "start_time": 1704985822.0,
        "model_id": "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
        "served_model_name": "coder",
        "provider": "linode",  # New field
    }


@pytest.fixture(autouse=True)
def isolate_env(monkeypatch):
    """Isolate tests from actual environment variables."""
    # Clear any existing config-related env vars
    config_keys = [
        "LINODE_TOKEN",
        "LINODE_CLI_TOKEN",
        "HUGGING_FACE_HUB_TOKEN",
        "FIREWALL_ID",
        "REGION",
        "TYPE",
        "IMAGE",
        "MODEL_ID",
        "SERVED_MODEL_NAME",
        "VLLM_TENSOR_PARALLEL_SIZE",
        "VLLM_MAX_MODEL_LEN",
        "VLLM_GPU_MEMORY_UTILIZATION",
        "VLLM_MAX_NUM_SEQS",
        "VLLM_DTYPE",
        "VLLM_EXTRA_ARGS",
        "WATCHDOG_ENABLED",
        "WATCHDOG_TIMEOUT_MINUTES",
        "WATCHDOG_WARNING_MINUTES",
    ]
    for key in config_keys:
        monkeypatch.delenv(key, raising=False)
