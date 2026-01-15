"""Tests for config module."""

import os
import math
from pathlib import Path
from pathlib import Path

import pytest

from src.maider.config import Config


@pytest.mark.unit
class TestConfig:
    """Test Config class."""

    def test_load_config_from_files(self, temp_dir, mock_env_file, mock_secrets_file, monkeypatch):
        """Test loading configuration from .env and .env.secrets files."""
        monkeypatch.chdir(temp_dir)

        config = Config()

        assert config.firewall_id == "12345"
        assert config.region == "us-east"
        assert config.type == "g1-gpu-rtx6000-1"
        assert config.model_id == "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
        assert config.served_model_name == "coder"
        assert config.hf_token == "hf_test_token_123"
        assert config.vllm_max_model_len == 32768
        assert math.isclose(config.vllm_gpu_memory_utilization, 0.90)

    def test_missing_required_field(self, temp_dir, mock_secrets_file, monkeypatch):
        """Test validation error when required field is missing from .env."""
        monkeypatch.chdir(temp_dir)

        # Create .env without FIREWALL_ID
        env_file = temp_dir / ".env"
        env_file.write_text(
            """REGION=us-east
TYPE=g1-gpu-rtx6000-1
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
"""
        )

        config = Config()
        errors = config.validate()

        assert len(errors) > 0
        assert any("FIREWALL_ID" in error for error in errors)

    def test_invalid_type_conversion(self, temp_dir, monkeypatch):
        """Test error when type conversion fails."""
        monkeypatch.chdir(temp_dir)

        # Create env files
        env_file = temp_dir / ".env"
        env_file.write_text(
            """FIREWALL_ID=12345
REGION=us-east
TYPE=g1-gpu-rtx6000-1
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
VLLM_GPU_MEMORY_UTILIZATION=invalid
"""
        )
        secrets_file = temp_dir / ".env.secrets"
        secrets_file.write_text("HUGGING_FACE_HUB_TOKEN=hf_test\n")

        # Config will raise ValueError when converting "invalid" to float
        with pytest.raises(ValueError):
            Config()

    def test_default_values(self, temp_dir, monkeypatch):
        """Test default values for optional fields."""
        monkeypatch.chdir(temp_dir)

        # Create minimal .env (no optional fields)
        env_file = temp_dir / ".env"
        env_file.write_text(
            """FIREWALL_ID=12345
REGION=us-east
TYPE=g1-gpu-rtx6000-1
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
"""
        )
        secrets_file = temp_dir / ".env.secrets"
        secrets_file.write_text("HUGGING_FACE_HUB_TOKEN=hf_test\n")

        config = Config()

        # Check defaults (no values specified, so defaults apply)
        assert math.isclose(config.vllm_gpu_memory_utilization, 0.90)
        assert math.isclose(config.vllm_gpu_memory_utilization, 0.90)
        assert config.vllm_max_num_seqs == 1
        assert config.vllm_tensor_parallel_size == 1
        assert config.vllm_dtype == "auto"
        assert config.vllm_extra_args == ""
        assert config.served_model_name == "coder"

    def test_linode_token_from_env(self, temp_dir, mock_env_file, mock_secrets_file, monkeypatch):
        """Test loading Linode token from environment variable."""
        monkeypatch.chdir(temp_dir)
        monkeypatch.setenv("LINODE_TOKEN", "test_linode_token")

        config = Config()

        assert config.linode_token == "test_linode_token"

    def test_linode_token_from_cli_env(
        self, temp_dir, mock_env_file, mock_secrets_file, monkeypatch
    ):
        """Test loading Linode token from LINODE_CLI_TOKEN environment variable."""
        monkeypatch.chdir(temp_dir)
        monkeypatch.setenv("LINODE_CLI_TOKEN", "cli_token_123")

        config = Config()

        assert config.linode_token == "cli_token_123"

    def test_missing_linode_token(self, temp_dir, mock_env_file, mock_secrets_file, monkeypatch):
        """Test validation error when Linode token is not found."""
        monkeypatch.chdir(temp_dir)
        monkeypatch.delenv("LINODE_TOKEN", raising=False)
        monkeypatch.delenv("LINODE_CLI_TOKEN", raising=False)

        config = Config()
        errors = config.validate()

        assert len(errors) > 0
        assert any("LINODE_TOKEN" in error for error in errors)
