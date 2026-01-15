"""Abstract base classes and interfaces for cloud provider implementations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Dict, Any


class ProviderType(Enum):
    """Supported cloud provider types."""

    LINODE = "linode"
    DIGITALOCEAN = "digitalocean"
    SCALEWAY = "scaleway"


@dataclass
class Region:
    """Cloud provider region information."""

    id: str
    name: str
    country: str
    gpu_available: bool = False


@dataclass
class VMType:
    """VM instance type specification."""

    id: str
    name: str
    gpus: int
    vram_per_gpu: int  # GB
    total_vram: int  # GB
    hourly_cost: float
    available_in_regions: List[str]


@dataclass
class VMInstance:
    """Represents a created VM instance."""

    provider_instance_id: str
    ip_address: str
    region: str
    type: str
    status: str
    provider_type: ProviderType


class CloudProvider(ABC):
    """Abstract base class for cloud provider implementations.

    Each cloud provider (Linode, DigitalOcean, Scaleway) should implement
    this interface to provide VM management capabilities.
    """

    @abstractmethod
    def __init__(self, api_token: str, **kwargs):
        """Initialize the provider with credentials.

        Args:
            api_token: API token for authentication
            **kwargs: Provider-specific configuration
        """
        pass

    @abstractmethod
    def list_regions(self, gpu_capable_only: bool = True) -> List[Region]:
        """List available regions.

        Args:
            gpu_capable_only: Only return regions with GPU support

        Returns:
            List of Region objects
        """
        pass

    @abstractmethod
    def list_vm_types(self, region: Optional[str] = None, gpu_only: bool = True) -> List[VMType]:
        """List available VM types.

        Args:
            region: Filter by region availability
            gpu_only: Only return GPU-enabled types

        Returns:
            List of VMType objects
        """
        pass

    @abstractmethod
    def create_instance(
        self,
        region: str,
        vm_type: str,
        label: str,
        ssh_key: str,
        cloud_init_config: str,
        firewall_id: Optional[str] = None,
        **kwargs,
    ) -> VMInstance:
        """Create a new VM instance.

        Args:
            region: Region to create instance in
            vm_type: VM type ID
            label: Instance label/name
            ssh_key: SSH public key for access
            cloud_init_config: Cloud-init configuration script
            firewall_id: Optional firewall ID
            **kwargs: Provider-specific parameters

        Returns:
            VMInstance object with creation details
        """
        pass

    @abstractmethod
    def delete_instance(self, instance_id: str) -> bool:
        """Delete a VM instance.

        Args:
            instance_id: Provider-specific instance identifier

        Returns:
            True if deletion successful
        """
        pass

    @abstractmethod
    def get_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """Get current status of a VM instance.

        Args:
            instance_id: Provider-specific instance identifier

        Returns:
            Dictionary with status information (provider-specific format)
        """
        pass

    @abstractmethod
    def get_provider_type(self) -> ProviderType:
        """Return the provider type enum value."""
        pass


class CloudProviderFactory:
    """Factory for instantiating cloud providers."""

    _providers: Dict[ProviderType, type] = {}

    @classmethod
    def register_provider(cls, provider_type: ProviderType, provider_class: type):
        """Register a provider implementation.

        Args:
            provider_type: Provider type enum
            provider_class: Provider implementation class
        """
        cls._providers[provider_type] = provider_class

    @classmethod
    def create_provider(
        cls, provider_type: ProviderType, api_token: str, **kwargs
    ) -> CloudProvider:
        """Create a provider instance.

        Args:
            provider_type: Type of provider to create
            api_token: API token for authentication
            **kwargs: Provider-specific configuration

        Returns:
            CloudProvider instance

        Raises:
            ValueError: If provider type not registered
        """
        provider_class = cls._providers.get(provider_type)
        if not provider_class:
            raise ValueError(
                f"Provider {provider_type.value} not registered. "
                f"Available: {[p.value for p in cls._providers.keys()]}"
            )

        return provider_class(api_token=api_token, **kwargs)

    @classmethod
    def get_available_providers(cls) -> List[ProviderType]:
        """Get list of registered provider types."""
        return list(cls._providers.keys())
