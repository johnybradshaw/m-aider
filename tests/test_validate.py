"""Tests for validate command."""

import pytest
from click.testing import CliRunner

from src.maider.commands.validate import cmd, GPU_REGIONS


@pytest.mark.unit
class TestValidateCommand:
    """Test validate command."""

    def test_validate_success_with_gpu_region(self, temp_dir, monkeypatch):
        """Test successful validation with a GPU-capable region."""
        monkeypatch.chdir(temp_dir)

        # Create valid .env with GPU region
        env_file = temp_dir / ".env"
        env_file.write_text(
            """FIREWALL_ID=12345
REGION=us-east
TYPE=g1-gpu-rtx6000-1
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
SERVED_MODEL_NAME=coder
VLLM_TENSOR_PARALLEL_SIZE=1
VLLM_MAX_MODEL_LEN=32768
VLLM_GPU_MEMORY_UTILIZATION=0.90
VLLM_MAX_NUM_SEQS=1
"""
        )
        secrets_file = temp_dir / ".env.secrets"
        secrets_file.write_text("HUGGING_FACE_HUB_TOKEN=hf_test\n")

        # Mock LINODE_TOKEN
        monkeypatch.setenv("LINODE_TOKEN", "test_token")

        runner = CliRunner()
        result = runner.invoke(cmd)

        assert result.exit_code == 0
        assert "Configuration is valid" in result.output
        assert "us-east" in result.output

    def test_validate_invalid_region_not_gpu(self, temp_dir, monkeypatch):
        """Test validation fails when region doesn't support GPUs."""
        monkeypatch.chdir(temp_dir)

        # Create .env with non-GPU region
        env_file = temp_dir / ".env"
        env_file.write_text(
            """FIREWALL_ID=12345
REGION=us-west
TYPE=g1-gpu-rtx6000-1
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
SERVED_MODEL_NAME=coder
VLLM_TENSOR_PARALLEL_SIZE=1
"""
        )
        secrets_file = temp_dir / ".env.secrets"
        secrets_file.write_text("HUGGING_FACE_HUB_TOKEN=hf_test\n")

        # Mock LINODE_TOKEN
        monkeypatch.setenv("LINODE_TOKEN", "test_token")

        runner = CliRunner()
        result = runner.invoke(cmd)

        assert result.exit_code == 1
        assert "Configuration errors found" in result.output
        assert "does not support GPU instances" in result.output

    def test_validate_all_gpu_regions_valid(self, temp_dir, monkeypatch):
        """Test that all GPU_REGIONS are accepted."""
        monkeypatch.chdir(temp_dir)

        secrets_file = temp_dir / ".env.secrets"
        secrets_file.write_text("HUGGING_FACE_HUB_TOKEN=hf_test\n")

        # Mock LINODE_TOKEN
        monkeypatch.setenv("LINODE_TOKEN", "test_token")

        runner = CliRunner()

        # Test each GPU region
        for region in GPU_REGIONS:
            env_file = temp_dir / ".env"
            env_file.write_text(
                f"""FIREWALL_ID=12345
REGION={region}
TYPE=g1-gpu-rtx6000-1
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
SERVED_MODEL_NAME=coder
VLLM_TENSOR_PARALLEL_SIZE=1
"""
            )

            result = runner.invoke(cmd)
            assert result.exit_code == 0, f"Region {region} should be valid but validation failed"
            assert "Configuration is valid" in result.output

    def test_validate_tensor_parallel_size_mismatch(self, temp_dir, monkeypatch):
        """Test warning when tensor parallel size doesn't match GPU count."""
        monkeypatch.chdir(temp_dir)

        # Create .env with mismatched tensor parallel size
        env_file = temp_dir / ".env"
        env_file.write_text(
            """FIREWALL_ID=12345
REGION=us-east
TYPE=g1-gpu-rtx6000-2
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
SERVED_MODEL_NAME=coder
VLLM_TENSOR_PARALLEL_SIZE=1
VLLM_MAX_MODEL_LEN=32768
"""
        )
        secrets_file = temp_dir / ".env.secrets"
        secrets_file.write_text("HUGGING_FACE_HUB_TOKEN=hf_test\n")

        # Mock LINODE_TOKEN
        monkeypatch.setenv("LINODE_TOKEN", "test_token")

        runner = CliRunner()
        result = runner.invoke(cmd)

        assert result.exit_code == 0  # Warning, not error
        assert "Warning" in result.output
        assert "VLLM_TENSOR_PARALLEL_SIZE" in result.output
        assert "doesn't match GPU count" in result.output

    def test_validate_displays_cost(self, temp_dir, monkeypatch):
        """Test that validation displays estimated cost."""
        monkeypatch.chdir(temp_dir)

        env_file = temp_dir / ".env"
        env_file.write_text(
            """FIREWALL_ID=12345
REGION=us-east
TYPE=g1-gpu-rtx6000-1
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
SERVED_MODEL_NAME=coder
VLLM_TENSOR_PARALLEL_SIZE=1
"""
        )
        secrets_file = temp_dir / ".env.secrets"
        secrets_file.write_text("HUGGING_FACE_HUB_TOKEN=hf_test\n")

        monkeypatch.setenv("LINODE_TOKEN", "test_token")

        runner = CliRunner()
        result = runner.invoke(cmd)

        assert result.exit_code == 0
        assert "Estimated cost" in result.output
        assert "/hour" in result.output


@pytest.mark.unit
class TestGPURegionsConstant:
    """Test GPU_REGIONS constant is properly defined."""

    def test_gpu_regions_not_empty(self):
        """Test that GPU_REGIONS contains regions."""
        assert len(GPU_REGIONS) > 0

    def test_gpu_regions_contains_expected_regions(self):
        """Test that GPU_REGIONS contains expected regions."""
        expected_regions = {
            # RTX 4000 Ada
            "us-ord",
            "de-fra-2",
            "in-bom-2",
            "jp-osa",
            "fr-par",
            "us-sea",
            "sg-sin-2",
            # RTX 6000
            "us-southeast",
            "eu-central",
            "ap-west",
            "us-east",
            "ap-south",
        }

        assert GPU_REGIONS == expected_regions

    def test_gpu_regions_is_set(self):
        """Test that GPU_REGIONS is a set for efficient lookups."""
        assert isinstance(GPU_REGIONS, set)
