"""Tests for wizard command."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from src.maider.commands.wizard import cmd, GPU_REGIONS, CAPABILITY_MODELS, GPU_TYPES


@pytest.mark.unit
class TestWizardGPURegions:
    """Test wizard GPU region filtering."""

    def test_wizard_only_shows_gpu_regions(self, temp_dir, monkeypatch):
        """Test that wizard only displays GPU-capable regions."""
        monkeypatch.chdir(temp_dir)

        # The regions list in wizard.py should only contain GPU regions
        expected_gpu_regions = {
            "us-east",
            "us-ord",
            "us-sea",
            "us-southeast",
            "eu-central",
            "de-fra-2",
            "fr-par",
            "ap-south",
            "sg-sin-2",
            "ap-west",
            "in-bom-2",
            "jp-osa",
        }

        # All regions in the hardcoded list should be in GPU_REGIONS
        assert expected_gpu_regions == GPU_REGIONS

    def test_gpu_regions_match_validate(self):
        """Test that wizard GPU_REGIONS matches validate GPU_REGIONS."""
        from src.maider.commands.validate import GPU_REGIONS as VALIDATE_GPU_REGIONS

        assert GPU_REGIONS == VALIDATE_GPU_REGIONS

    @patch("src.maider.commands.wizard.Prompt")
    @patch("src.maider.commands.wizard.Confirm")
    @patch("src.maider.commands.wizard.Config")
    def test_wizard_region_selection_gpu_only(
        self, mock_config, mock_confirm, mock_prompt, temp_dir, monkeypatch
    ):
        """Test wizard region selection presents only GPU regions."""
        monkeypatch.chdir(temp_dir)

        # Mock Config to avoid looking for existing config
        mock_config.return_value = MagicMock(
            firewall_id="12345", hf_token="hf_test", linode_token="test_token"
        )

        # Mock user inputs
        mock_prompt.ask.side_effect = [
            "1",  # Capability choice (small)
            "1",  # Region choice (us-east)
            "1",  # VM type choice
        ]
        mock_confirm.ask.return_value = False  # Don't save

        runner = CliRunner()
        result = runner.invoke(cmd)

        # Should complete without error
        assert "Select your region" in result.output
        assert "Only regions with GPU availability shown" in result.output

        # Verify at least some GPU regions are shown
        output_lower = result.output.lower()
        assert any(region in output_lower for region in ["us-east", "us-ord", "eu-central"])


@pytest.mark.unit
class TestGPURegionsConstant:
    """Test GPU_REGIONS constant in wizard."""

    def test_gpu_regions_not_empty(self):
        """Test that GPU_REGIONS contains regions."""
        assert len(GPU_REGIONS) > 0
        assert len(GPU_REGIONS) == 12  # As of 2026-01

    def test_gpu_regions_contains_rtx4000_regions(self):
        """Test that GPU_REGIONS contains RTX 4000 Ada regions."""
        rtx4000_regions = {
            "us-ord",
            "de-fra-2",
            "in-bom-2",
            "jp-osa",
            "fr-par",
            "us-sea",
            "sg-sin-2",
        }

        for region in rtx4000_regions:
            assert region in GPU_REGIONS, f"RTX 4000 Ada region {region} should be in GPU_REGIONS"

    def test_gpu_regions_contains_rtx6000_regions(self):
        """Test that GPU_REGIONS contains RTX 6000 regions."""
        rtx6000_regions = {"us-southeast", "eu-central", "ap-west", "us-east", "ap-south"}

        for region in rtx6000_regions:
            assert region in GPU_REGIONS, f"RTX 6000 region {region} should be in GPU_REGIONS"

    def test_gpu_regions_is_set(self):
        """Test that GPU_REGIONS is a set for efficient lookups."""
        assert isinstance(GPU_REGIONS, set)


@pytest.mark.unit
class TestCapabilityModels:
    """Test capability model configurations."""

    def test_capability_models_defined(self):
        """Test that CAPABILITY_MODELS is properly defined."""
        assert len(CAPABILITY_MODELS) == 3
        assert "small" in CAPABILITY_MODELS
        assert "medium" in CAPABILITY_MODELS
        assert "large" in CAPABILITY_MODELS

    def test_capability_models_have_required_fields(self):
        """Test that each capability has required fields."""
        required_fields = {
            "name",
            "description",
            "min_vram_gb",
            "recommended_model",
            "context_length",
            "cost_range",
        }

        for capability_key, capability in CAPABILITY_MODELS.items():
            for field in required_fields:
                assert field in capability, f"{capability_key} missing field: {field}"

    def test_capability_vram_requirements_logical(self):
        """Test that VRAM requirements are logically ordered."""
        small_vram = CAPABILITY_MODELS["small"]["min_vram_gb"]
        medium_vram = CAPABILITY_MODELS["medium"]["min_vram_gb"]
        large_vram = CAPABILITY_MODELS["large"]["min_vram_gb"]

        assert small_vram < medium_vram < large_vram


@pytest.mark.unit
class TestGPUTypes:
    """Test GPU type configurations."""

    def test_gpu_types_defined(self):
        """Test that GPU_TYPES is properly defined."""
        assert len(GPU_TYPES) > 0

        # Should have both RTX 4000 Ada and RTX 6000 types
        rtx4000_types = [t for t in GPU_TYPES if "rtx4000" in t]
        rtx6000_types = [t for t in GPU_TYPES if "rtx6000" in t]

        assert len(rtx4000_types) > 0
        assert len(rtx6000_types) > 0

    def test_gpu_types_have_required_fields(self):
        """Test that each GPU type has required fields."""
        required_fields = {"gpus", "vram_per_gpu", "hourly_cost"}

        for type_id, type_info in GPU_TYPES.items():
            for field in required_fields:
                assert field in type_info, f"{type_id} missing field: {field}"

    def test_gpu_types_vram_values(self):
        """Test that GPU VRAM values are sensible."""
        for type_id, type_info in GPU_TYPES.items():
            vram = type_info["vram_per_gpu"]
            # RTX 4000 Ada has 20GB, RTX 6000 has 48GB
            assert vram in [20, 48], f"{type_id} has unexpected VRAM: {vram}GB"

    def test_gpu_types_cost_increases_with_count(self):
        """Test that cost increases with GPU count for same GPU type."""
        # RTX 4000 Ada types
        rtx4000_types = {k: v for k, v in GPU_TYPES.items() if "rtx4000" in k}
        rtx4000_sorted = sorted(rtx4000_types.items(), key=lambda x: x[1]["gpus"])

        for i in range(len(rtx4000_sorted) - 1):
            current = rtx4000_sorted[i][1]
            next_item = rtx4000_sorted[i + 1][1]
            assert current["hourly_cost"] < next_item["hourly_cost"]

        # RTX 6000 types
        rtx6000_types = {k: v for k, v in GPU_TYPES.items() if "rtx6000" in k}
        rtx6000_sorted = sorted(rtx6000_types.items(), key=lambda x: x[1]["gpus"])

        for i in range(len(rtx6000_sorted) - 1):
            current = rtx6000_sorted[i][1]
            next_item = rtx6000_sorted[i + 1][1]
            assert current["hourly_cost"] < next_item["hourly_cost"]
