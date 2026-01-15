"""Tests for Linode provider implementation."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from src.maider.providers.linode import (
    LinodeProvider,
    GPU_REGIONS,
    GPU_TYPES,
    REGION_METADATA,
)
from src.maider.providers.base import ProviderType, Region, VMType, VMInstance


@pytest.mark.unit
class TestLinodeProviderConstants:
    """Test Linode provider constants."""

    def test_gpu_regions_defined(self):
        """Test that GPU_REGIONS is defined and not empty."""
        assert isinstance(GPU_REGIONS, set)
        assert len(GPU_REGIONS) == 12  # As of 2026-01

    def test_gpu_regions_contains_expected_regions(self):
        """Test that GPU_REGIONS contains known GPU regions."""
        expected_regions = {
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

        assert GPU_REGIONS == expected_regions

    def test_gpu_types_defined(self):
        """Test that GPU_TYPES is defined and has expected types."""
        assert isinstance(GPU_TYPES, dict)
        assert len(GPU_TYPES) == 7  # 3 RTX 4000 + 4 RTX 6000

        # Check specific known types
        assert "g2-gpu-rtx4000a1-s" in GPU_TYPES
        assert "g2-gpu-rtx4000a2-s" in GPU_TYPES
        assert "g2-gpu-rtx4000a4-m" in GPU_TYPES
        assert "g1-gpu-rtx6000-1" in GPU_TYPES
        assert "g1-gpu-rtx6000-2" in GPU_TYPES
        assert "g1-gpu-rtx6000-3" in GPU_TYPES
        assert "g1-gpu-rtx6000-4" in GPU_TYPES

        # Verify 8x GPU type does NOT exist
        assert "g1-gpu-rtx6000-8" not in GPU_TYPES

    def test_gpu_types_have_required_fields(self):
        """Test that each GPU type has required fields."""
        required_fields = {"gpus", "vram_per_gpu", "hourly_cost", "regions"}

        for type_id, specs in GPU_TYPES.items():
            for field in required_fields:
                assert field in specs, f"{type_id} missing field: {field}"

    def test_gpu_types_region_mapping(self):
        """Test that GPU types are correctly mapped to regions."""
        from src.maider.providers.linode import RTX4000_REGIONS, RTX6000_REGIONS

        # RTX 4000 types should only be in RTX4000_REGIONS
        rtx4000_types = ["g2-gpu-rtx4000a1-s", "g2-gpu-rtx4000a2-s", "g2-gpu-rtx4000a4-m"]
        for type_id in rtx4000_types:
            assert GPU_TYPES[type_id]["regions"] == RTX4000_REGIONS, f"{type_id} has wrong regions"

        # RTX 6000 types should only be in RTX6000_REGIONS
        rtx6000_types = [
            "g1-gpu-rtx6000-1",
            "g1-gpu-rtx6000-2",
            "g1-gpu-rtx6000-3",
            "g1-gpu-rtx6000-4",
        ]
        for type_id in rtx6000_types:
            assert GPU_TYPES[type_id]["regions"] == RTX6000_REGIONS, f"{type_id} has wrong regions"

    def test_gpu_types_vram_values(self):
        """Test that VRAM values are sensible."""
        for type_id, specs in GPU_TYPES.items():
            vram = specs["vram_per_gpu"]
            # RTX 4000 Ada has 20GB, RTX 6000 Ada has 48GB
            assert vram in [20, 48], f"{type_id} has unexpected VRAM: {vram}GB"

    def test_gpu_types_cost_positive(self):
        """Test that all costs are positive."""
        for type_id, specs in GPU_TYPES.items():
            cost = specs["hourly_cost"]
            assert cost > 0, f"{type_id} has non-positive cost: ${cost}/hr"

    def test_region_metadata_covers_gpu_regions(self):
        """Test that REGION_METADATA covers all GPU regions."""
        for region_id in GPU_REGIONS:
            assert (
                region_id in REGION_METADATA
            ), f"GPU region {region_id} missing from REGION_METADATA"

    def test_region_metadata_format(self):
        """Test that region metadata has correct format."""
        for region_id, metadata in REGION_METADATA.items():
            assert isinstance(metadata, tuple)
            assert len(metadata) == 2
            name, country = metadata
            assert isinstance(name, str)
            assert isinstance(country, str)
            assert len(country) == 2  # Country code should be 2 letters


@pytest.mark.unit
class TestLinodeProviderInit:
    """Test LinodeProvider initialization."""

    @patch("src.maider.providers.linode.LinodeClient")
    def test_init_with_token(self, mock_client_class):
        """Test provider initialization with API token."""
        mock_client = Mock()
        mock_client_class.return_value = mock_client

        provider = LinodeProvider(api_token="test_token_123")

        assert provider.api_token == "test_token_123"
        assert provider.client == mock_client
        mock_client_class.assert_called_once_with(token="test_token_123")

    def test_get_provider_type(self):
        """Test that provider returns correct type."""
        with patch("src.maider.providers.linode.LinodeClient"):
            provider = LinodeProvider(api_token="test_token")
            assert provider.get_provider_type() == ProviderType.LINODE


@pytest.mark.unit
class TestLinodeProviderRegions:
    """Test LinodeProvider region methods."""

    @patch("src.maider.providers.linode.LinodeClient")
    def test_list_gpu_regions_only(self, mock_client_class):
        """Test listing only GPU-capable regions."""
        provider = LinodeProvider(api_token="test_token")
        regions = provider.list_regions(gpu_capable_only=True)

        assert len(regions) == 12
        assert all(isinstance(r, Region) for r in regions)
        assert all(r.gpu_available for r in regions)
        assert all(r.id in GPU_REGIONS for r in regions)

    @patch("src.maider.providers.linode.LinodeClient")
    def test_list_all_regions(self, mock_client_class):
        """Test listing all regions (not just GPU)."""
        mock_client = Mock()
        mock_api_regions = [
            Mock(id="us-east", country="us"),
            Mock(id="us-west", country="us"),
            Mock(id="eu-west", country="gb"),
        ]
        mock_client.regions.return_value = mock_api_regions
        mock_client_class.return_value = mock_client

        provider = LinodeProvider(api_token="test_token")
        regions = provider.list_regions(gpu_capable_only=False)

        assert len(regions) == 3
        # Check that GPU availability is correctly set
        for region in regions:
            if region.id in GPU_REGIONS:
                assert region.gpu_available
            else:
                assert not region.gpu_available


@pytest.mark.unit
class TestLinodeProviderVMTypes:
    """Test LinodeProvider VM type methods."""

    @patch("src.maider.providers.linode.LinodeClient")
    def test_list_vm_types(self, mock_client_class):
        """Test listing GPU VM types."""
        provider = LinodeProvider(api_token="test_token")
        vm_types = provider.list_vm_types(gpu_only=True)

        assert len(vm_types) == 7  # 3 RTX 4000 + 4 RTX 6000
        assert all(isinstance(vt, VMType) for vt in vm_types)
        assert all(vt.gpus > 0 for vt in vm_types)
        assert all(vt.id in GPU_TYPES for vt in vm_types)

    @patch("src.maider.providers.linode.LinodeClient")
    def test_list_vm_types_with_region_filter_rtx4000(self, mock_client_class):
        """Test filtering VM types by RTX 4000 region."""
        from src.maider.providers.linode import RTX4000_REGIONS

        provider = LinodeProvider(api_token="test_token")

        # RTX 4000 regions should only show RTX 4000 types
        for region in RTX4000_REGIONS:
            vm_types = provider.list_vm_types(region=region, gpu_only=True)
            assert len(vm_types) == 3  # Only 3 RTX 4000 types
            assert all("rtx4000" in vt.id for vt in vm_types)
            assert all("rtx6000" not in vt.id for vt in vm_types)

    @patch("src.maider.providers.linode.LinodeClient")
    def test_list_vm_types_with_region_filter_rtx6000(self, mock_client_class):
        """Test filtering VM types by RTX 6000 region."""
        from src.maider.providers.linode import RTX6000_REGIONS

        provider = LinodeProvider(api_token="test_token")

        # RTX 6000 regions should only show RTX 6000 types
        for region in RTX6000_REGIONS:
            vm_types = provider.list_vm_types(region=region, gpu_only=True)
            assert len(vm_types) == 4  # Only 4 RTX 6000 types
            assert all("rtx6000" in vt.id for vt in vm_types)
            assert all("rtx4000" not in vt.id for vt in vm_types)

    @patch("src.maider.providers.linode.LinodeClient")
    def test_vm_type_total_vram_calculation(self, mock_client_class):
        """Test that total VRAM is correctly calculated."""
        provider = LinodeProvider(api_token="test_token")
        vm_types = provider.list_vm_types(gpu_only=True)

        for vt in vm_types:
            expected_total = vt.gpus * vt.vram_per_gpu
            assert vt.total_vram == expected_total


@pytest.mark.unit
class TestLinodeProviderHelperMethods:
    """Test LinodeProvider helper methods."""

    @pytest.fixture
    def provider(self):
        """Create a LinodeProvider instance for testing."""
        with patch("src.maider.providers.linode.LinodeClient"):
            return LinodeProvider(api_token="test-token")

    def test_get_gpu_count(self, provider):
        """Test GPU count lookup."""
        # Test known types (uses fallback to hardcoded data)
        assert provider.get_gpu_count("g2-gpu-rtx4000a1-s") == 1
        assert provider.get_gpu_count("g2-gpu-rtx4000a2-s") == 2
        assert provider.get_gpu_count("g2-gpu-rtx4000a4-m") == 4
        assert provider.get_gpu_count("g1-gpu-rtx6000-1") == 1
        assert provider.get_gpu_count("g1-gpu-rtx6000-2") == 2
        assert provider.get_gpu_count("g1-gpu-rtx6000-3") == 3
        assert provider.get_gpu_count("g1-gpu-rtx6000-4") == 4

    def test_get_gpu_count_unknown_type(self, provider):
        """Test GPU count for unknown type returns 1 (fallback)."""
        assert provider.get_gpu_count("unknown-type") == 1
        assert provider.get_gpu_count("") == 1

    def test_get_hourly_cost(self, provider):
        """Test hourly cost lookup."""
        # Test known types (uses fallback to hardcoded data)
        assert provider.get_hourly_cost("g2-gpu-rtx4000a1-s") == pytest.approx(0.52)
        assert provider.get_hourly_cost("g1-gpu-rtx6000-1") == pytest.approx(1.50)
        assert provider.get_hourly_cost("g1-gpu-rtx6000-2") == pytest.approx(3.00)
        assert provider.get_hourly_cost("g1-gpu-rtx6000-4") == pytest.approx(6.00)

    def test_get_hourly_cost_unknown_type(self, provider):
        """Test hourly cost for unknown type returns 0."""
        assert provider.get_hourly_cost("unknown-type") == pytest.approx(0.0)
        assert provider.get_hourly_cost("") == pytest.approx(0.0)

    def test_get_hourly_cost_increases_with_gpu_count(self, provider):
        """Test that cost increases with GPU count."""
        # RTX 6000 series (uses fallback to hardcoded data)
        cost_1gpu = provider.get_hourly_cost("g1-gpu-rtx6000-1")
        cost_2gpu = provider.get_hourly_cost("g1-gpu-rtx6000-2")
        cost_4gpu = provider.get_hourly_cost("g1-gpu-rtx6000-4")

        assert cost_2gpu > cost_1gpu
        assert cost_4gpu > cost_2gpu


@pytest.mark.unit
class TestLinodeProviderInstanceManagement:
    """Test LinodeProvider instance management methods."""

    @patch("src.maider.providers.linode.LinodeClient")
    def test_create_instance(self, mock_client_class):
        """Test creating a VM instance."""
        mock_client = Mock()
        mock_instance = Mock()
        mock_instance.id = 12345678
        mock_instance.ipv4 = ["192.0.2.1"]
        mock_instance.status = "running"

        mock_client.linode.instance_create.return_value = mock_instance
        mock_client_class.return_value = mock_client

        provider = LinodeProvider(api_token="test_token")

        result = provider.create_instance(
            region="us-east",
            vm_type="g1-gpu-rtx6000-1",
            label="test-instance",
            ssh_key="ssh-rsa AAAA...",
            cloud_init_config="#cloud-config\n...",
            firewall_id="12345",
        )

        assert isinstance(result, VMInstance)
        assert result.provider_instance_id == "12345678"
        assert result.ip_address == "192.0.2.1"
        assert result.region == "us-east"
        assert result.type == "g1-gpu-rtx6000-1"
        assert result.provider_type == ProviderType.LINODE

    @patch("src.maider.providers.linode.LinodeClient")
    def test_delete_instance_success(self, mock_client_class):
        """Test successfully deleting a VM instance."""
        mock_client = Mock()
        mock_instance = Mock()
        mock_client.load.return_value = mock_instance
        mock_client_class.return_value = mock_client

        provider = LinodeProvider(api_token="test_token")
        result = provider.delete_instance("12345678")

        assert result is True
        mock_instance.delete.assert_called_once()

    @patch("src.maider.providers.linode.LinodeClient")
    def test_delete_instance_failure(self, mock_client_class):
        """Test handling delete failure."""
        mock_client = Mock()
        mock_instance = Mock()
        mock_instance.delete.side_effect = Exception("API Error")
        mock_client.load.return_value = mock_instance
        mock_client_class.return_value = mock_client

        provider = LinodeProvider(api_token="test_token")
        result = provider.delete_instance("12345678")

        assert result is False

    @patch("src.maider.providers.linode.LinodeClient")
    def test_get_instance_status(self, mock_client_class):
        """Test getting instance status."""
        mock_client = Mock()
        mock_instance = Mock()
        mock_instance.id = 12345678
        mock_instance.label = "test-instance"
        mock_instance.status = "running"
        mock_instance.region = Mock(id="us-east")
        mock_instance.type = Mock(id="g1-gpu-rtx6000-1")
        mock_instance.ipv4 = ["192.0.2.1"]
        mock_instance.ipv6 = "2001:db8::1"
        mock_instance.created = "2026-01-14T00:00:00"
        mock_instance.updated = "2026-01-14T01:00:00"
        mock_client.load.return_value = mock_instance
        mock_client_class.return_value = mock_client

        provider = LinodeProvider(api_token="test_token")
        result = provider.get_instance_status("12345678")

        assert result["status"] == "running"
        assert result["ipv4"] == ["192.0.2.1"]
        assert result["label"] == "test-instance"

    @patch("src.maider.providers.linode.LinodeClient")
    def test_get_instance_status_not_found(self, mock_client_class):
        """Test getting status for non-existent instance."""
        mock_client = Mock()
        mock_client.load.side_effect = Exception("Not found")
        mock_client_class.return_value = mock_client

        provider = LinodeProvider(api_token="test_token")
        result = provider.get_instance_status("99999999")

        assert "error" in result
        assert result["error"] == "Not found"


@pytest.mark.unit
class TestLinodeProviderFactoryRegistration:
    """Test that LinodeProvider is registered with factory."""

    def test_linode_provider_registered(self):
        """Test that LinodeProvider is registered in factory."""
        from src.maider.providers.base import CloudProviderFactory

        available = CloudProviderFactory.get_available_providers()
        assert ProviderType.LINODE in available

    def test_can_create_linode_provider_from_factory(self):
        """Test creating LinodeProvider through factory."""
        from src.maider.providers.base import CloudProviderFactory

        # Re-register the real LinodeProvider to ensure test isolation
        CloudProviderFactory.register_provider(ProviderType.LINODE, LinodeProvider)

        with patch("src.maider.providers.linode.LinodeClient"):
            provider = CloudProviderFactory.create_provider(
                ProviderType.LINODE, api_token="test_token"
            )

            assert isinstance(provider, LinodeProvider)
            assert provider.get_provider_type() == ProviderType.LINODE
