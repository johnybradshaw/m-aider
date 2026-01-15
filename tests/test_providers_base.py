"""Tests for provider abstraction base classes and interfaces."""

import math
import pytest
from src.maider.providers.base import (
    ProviderType,
    Region,
    VMType,
    VMInstance,
    CloudProvider,
    CloudProviderFactory,
)


@pytest.mark.unit
class TestProviderType:
    """Test ProviderType enum."""

    def test_provider_type_values(self):
        """Test that provider types have expected values."""
        assert ProviderType.LINODE.value == "linode"
        assert ProviderType.DIGITALOCEAN.value == "digitalocean"
        assert ProviderType.SCALEWAY.value == "scaleway"

    def test_provider_type_from_string(self):
        """Test creating provider type from string."""
        assert ProviderType("linode") == ProviderType.LINODE
        assert ProviderType("digitalocean") == ProviderType.DIGITALOCEAN
        assert ProviderType("scaleway") == ProviderType.SCALEWAY

    def test_invalid_provider_type(self):
        """Test that invalid provider type raises ValueError."""
        with pytest.raises(ValueError):
            ProviderType("invalid_provider")


@pytest.mark.unit
class TestRegion:
    """Test Region dataclass."""

    def test_region_creation(self):
        """Test creating a Region object."""
        region = Region(id="us-east", name="Newark, NJ", country="us", gpu_available=True)

        assert region.id == "us-east"
        assert region.name == "Newark, NJ"
        assert region.country == "us"
        assert region.gpu_available is True

    def test_region_default_gpu_available(self):
        """Test that gpu_available defaults to False."""
        region = Region(id="us-west", name="California", country="us")

        assert region.gpu_available is False


@pytest.mark.unit
class TestVMType:
    """Test VMType dataclass."""

    def test_vmtype_creation(self):
        """Test creating a VMType object."""
        vm_type = VMType(
            id="g1-gpu-rtx6000-2",
            name="2x RTX 6000 Ada",
            gpus=2,
            vram_per_gpu=48,
            total_vram=96,
            hourly_cost=3.0,
            available_in_regions=["us-east", "eu-central"],
        )

        assert vm_type.id == "g1-gpu-rtx6000-2"
        assert vm_type.name == "2x RTX 6000 Ada"
        assert vm_type.gpus == 2
        assert vm_type.vram_per_gpu == 48
        assert vm_type.total_vram == 96
        assert math.isclose(vm_type.hourly_cost, 3.0)
        assert len(vm_type.available_in_regions) == 2

    def test_vmtype_vram_calculation(self):
        """Test that total VRAM is correctly calculated."""
        vm_type = VMType(
            id="test-type",
            name="Test",
            gpus=4,
            vram_per_gpu=20,
            total_vram=80,  # Should be 4 * 20
            hourly_cost=2.0,
            available_in_regions=[],
        )

        assert vm_type.total_vram == vm_type.gpus * vm_type.vram_per_gpu


@pytest.mark.unit
class TestVMInstance:
    """Test VMInstance dataclass."""

    def test_vminstance_creation(self):
        """Test creating a VMInstance object."""
        instance = VMInstance(
            provider_instance_id="12345678",
            ip_address="192.0.2.1",
            region="us-east",
            type="g1-gpu-rtx6000-1",
            status="running",
            provider_type=ProviderType.LINODE,
        )

        assert instance.provider_instance_id == "12345678"
        assert instance.ip_address == "192.0.2.1"
        assert instance.region == "us-east"
        assert instance.type == "g1-gpu-rtx6000-1"
        assert instance.status == "running"
        assert instance.provider_type == ProviderType.LINODE


@pytest.mark.unit
class TestCloudProviderFactory:
    """Test CloudProviderFactory."""

    def test_register_provider(self):
        """Test registering a provider."""

        # Create a mock provider class
        class MockProvider(CloudProvider):
            def __init__(self, api_token: str, **kwargs):
                self.api_token = api_token

            def list_regions(self, gpu_capable_only=True):
                return []

            def list_vm_types(self, region=None, gpu_only=True):
                return []

            def create_instance(self, region, vm_type, label, ssh_key, cloud_init_config, **kwargs):
                return VMInstance(
                    provider_instance_id="test",
                    ip_address="192.0.2.1",
                    region=region,
                    type=vm_type,
                    status="running",
                    provider_type=ProviderType.LINODE,
                )

            def delete_instance(self, instance_id):
                return True

            def get_instance_status(self, instance_id):
                return {"status": "running"}

            def get_provider_type(self):
                return ProviderType.LINODE

        # Register the mock provider
        CloudProviderFactory.register_provider(ProviderType.LINODE, MockProvider)

        # Verify it's in available providers
        available = CloudProviderFactory.get_available_providers()
        assert ProviderType.LINODE in available

    def test_create_provider(self):
        """Test creating a provider instance."""

        # Create a mock provider class
        class MockProvider(CloudProvider):
            def __init__(self, api_token: str, **kwargs):
                self.api_token = api_token
                self.custom_param = kwargs.get("custom_param")

            def list_regions(self, gpu_capable_only=True):
                return []

            def list_vm_types(self, region=None, gpu_only=True):
                return []

            def create_instance(self, region, vm_type, label, ssh_key, cloud_init_config, **kwargs):
                return VMInstance(
                    provider_instance_id="test",
                    ip_address="192.0.2.1",
                    region=region,
                    type=vm_type,
                    status="running",
                    provider_type=ProviderType.LINODE,
                )

            def delete_instance(self, instance_id):
                return True

            def get_instance_status(self, instance_id):
                return {"status": "running"}

            def get_provider_type(self):
                return ProviderType.LINODE

        # Register and create provider
        CloudProviderFactory.register_provider(ProviderType.LINODE, MockProvider)
        provider = CloudProviderFactory.create_provider(
            ProviderType.LINODE, api_token="test_token", custom_param="test_value"
        )

        assert provider.api_token == "test_token"
        assert provider.custom_param == "test_value"

    def test_create_unregistered_provider_fails(self):
        """Test that creating unregistered provider raises ValueError."""
        # Create a new provider type that isn't registered
        with pytest.raises(ValueError, match="Provider .* not registered"):
            CloudProviderFactory.create_provider(ProviderType.DIGITALOCEAN, api_token="test")

    def test_get_available_providers(self):
        """Test getting list of available providers."""

        # Create a mock provider
        class MockProvider(CloudProvider):
            def __init__(self, api_token: str, **kwargs):
                # Mock provider for testing - no initialization needed
                pass

            def list_regions(self, gpu_capable_only=True):
                return []

            def list_vm_types(self, region=None, gpu_only=True):
                return []

            def create_instance(self, region, vm_type, label, ssh_key, cloud_init_config, **kwargs):
                return None

            def delete_instance(self, instance_id):
                return True

            def get_instance_status(self, instance_id):
                return {}

            def get_provider_type(self):
                return ProviderType.SCALEWAY

        CloudProviderFactory.register_provider(ProviderType.SCALEWAY, MockProvider)

        available = CloudProviderFactory.get_available_providers()
        assert isinstance(available, list)
        assert ProviderType.SCALEWAY in available


@pytest.mark.unit
class TestCloudProviderInterface:
    """Test CloudProvider abstract interface."""

    def test_cannot_instantiate_abstract_class(self):
        """Test that CloudProvider cannot be instantiated directly."""
        with pytest.raises(TypeError):
            CloudProvider(api_token="test")

    def test_abstract_methods_required(self):
        """Test that all abstract methods must be implemented."""

        # Missing implementation should raise TypeError
        with pytest.raises(TypeError):

            class IncompleteProvider(CloudProvider):
                def __init__(self, api_token: str, **kwargs):
                    pass

                # Missing other required methods

            IncompleteProvider(api_token="test")
