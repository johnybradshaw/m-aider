"""Linode cloud provider implementation."""

import base64
import secrets
import string
import time
from typing import List, Optional, Dict, Any, Set

from linode_api4 import LinodeClient, Instance
from rich.console import Console

from .base import (
    CloudProvider,
    ProviderType,
    Region,
    VMType,
    VMInstance,
    CloudProviderFactory,
)

console = Console()
RTX_6000_NAME = "RTX 6000 Ada"
RTX_4000_NAME = "RTX 4000 Ada"

# Cache for API type queries (TTL: 1 hour)
_type_cache: Dict[str, Any] = {}
_type_cache_timestamp: float = 0
_TYPE_CACHE_TTL = 3600  # 1 hour


# GPU-capable regions (as of 2026-01)
# Source: https://www.linode.com/docs/products/compute/compute-instances/plans/gpu/

# RTX 4000 Ada regions (20GB VRAM per GPU)
RTX4000_REGIONS = {
    "us-ord",  # Chicago, IL
    "de-fra-2",  # Frankfurt 2, DE (Note: different from eu-central)
    "in-bom-2",  # Mumbai 2, IN (Note: different from ap-west)
    "jp-osa",  # Osaka, JP
    "fr-par",  # Paris, FR
    "us-sea",  # Seattle, WA
    "sg-sin-2",  # Singapore 2, SG (Note: different from ap-south)
}

# RTX 6000 Ada regions (48GB VRAM per GPU)
RTX6000_REGIONS = {
    "us-southeast",  # Atlanta, GA
    "eu-central",  # Frankfurt, DE
    "ap-west",  # Mumbai, IN
    "us-east",  # Newark, NJ
    "ap-south",  # Singapore, SG
}

# All GPU-capable regions
GPU_REGIONS = RTX4000_REGIONS | RTX6000_REGIONS

# GPU type information with specs, pricing, and region availability
GPU_TYPES = {
    # RTX 4000 Ada types (available in RTX4000_REGIONS only)
    "g2-gpu-rtx4000a1-s": {
        "gpus": 1,
        "vram_per_gpu": 20,
        "hourly_cost": 0.52,
        "regions": RTX4000_REGIONS,
    },
    "g2-gpu-rtx4000a2-s": {
        "gpus": 2,
        "vram_per_gpu": 20,
        "hourly_cost": 1.04,
        "regions": RTX4000_REGIONS,
    },
    "g2-gpu-rtx4000a4-m": {
        "gpus": 4,
        "vram_per_gpu": 20,
        "hourly_cost": 2.08,
        "regions": RTX4000_REGIONS,
    },
    # RTX 6000 Ada types (available in RTX6000_REGIONS only)
    "g1-gpu-rtx6000-1": {
        "gpus": 1,
        "vram_per_gpu": 48,
        "hourly_cost": 1.50,
        "regions": RTX6000_REGIONS,
    },
    "g1-gpu-rtx6000-2": {
        "gpus": 2,
        "vram_per_gpu": 48,
        "hourly_cost": 3.00,
        "regions": RTX6000_REGIONS,
    },
    "g1-gpu-rtx6000-3": {
        "gpus": 3,
        "vram_per_gpu": 48,
        "hourly_cost": 4.50,
        "regions": RTX6000_REGIONS,
    },
    "g1-gpu-rtx6000-4": {
        "gpus": 4,
        "vram_per_gpu": 48,
        "hourly_cost": 6.00,
        "regions": RTX6000_REGIONS,
    },
}

# Region metadata
REGION_METADATA = {
    "us-east": ("Newark, NJ", "us"),
    "us-ord": ("Chicago, IL", "us"),
    "us-sea": ("Seattle, WA", "us"),
    "us-southeast": ("Atlanta, GA", "us"),
    "eu-central": ("Frankfurt, DE", "de"),
    "de-fra-2": ("Frankfurt 2, DE", "de"),
    "fr-par": ("Paris, FR", "fr"),
    "ap-south": ("Singapore, SG", "sg"),
    "sg-sin-2": ("Singapore 2, SG", "sg"),
    "ap-west": ("Mumbai, IN", "in"),
    "in-bom-2": ("Mumbai 2, IN", "in"),
    "jp-osa": ("Osaka, JP", "jp"),
}


class LinodeProvider(CloudProvider):
    """Linode cloud provider implementation."""

    def __init__(self, api_token: str, **kwargs):
        """Initialize Linode provider.

        Args:
            api_token: Linode API token
            **kwargs: Additional configuration (unused)
        """
        self.api_token = api_token
        self.client = LinodeClient(token=api_token)

    def _fetch_types_from_api(self, force_refresh: bool = False) -> Dict[str, Any]:
        """Fetch Linode types from API with caching.

        Args:
            force_refresh: Bypass cache and fetch fresh data

        Returns:
            Dictionary mapping type_id to type details
        """
        global _type_cache, _type_cache_timestamp

        # Check cache validity
        cache_age = time.time() - _type_cache_timestamp
        if not force_refresh and _type_cache and cache_age < _TYPE_CACHE_TTL:
            return _type_cache

        # Fetch types from API
        try:
            console.print("[dim]Fetching GPU types from Linode API...[/dim]")
            api_types = self.client.linode.types()
            gpu_regions = self._fetch_gpu_regions()

            type_data = {}
            for api_type in api_types:
                details = self._build_type_details(api_type, gpu_regions)
                if details:
                    type_data[api_type.id] = details

            # Update cache
            _type_cache = type_data
            _type_cache_timestamp = time.time()

            console.print(f"[dim]✓ Found {len(type_data)} GPU types[/dim]")

            # If no GPU types found, fall back to hardcoded data (likely mocked client in tests)
            if len(type_data) == 0:
                console.print("[dim]Using hardcoded GPU types (API returned no GPU types)[/dim]")
                _type_cache = self._get_hardcoded_gpu_types()
                _type_cache_timestamp = time.time()

            return _type_cache

        except Exception as e:
            console.print(f"[yellow]Warning: Could not fetch types from API: {e}[/yellow]")
            console.print("[yellow]Falling back to hardcoded GPU types[/yellow]")

            # Fall back to hardcoded data
            if not _type_cache:
                _type_cache = self._get_hardcoded_gpu_types()
                _type_cache_timestamp = time.time()
            return _type_cache

    def _fetch_gpu_regions(self) -> Dict[str, Set[str]]:
        """Fetch GPU-capable regions from API.

        Returns:
            Dictionary with 'rtx4000' and 'rtx6000' keys mapping to sets of region IDs
        """
        try:
            api_regions = self.client.regions()
            rtx4000_regions = set()
            rtx6000_regions = set()

            for region in api_regions:
                if hasattr(region, "capabilities") and "GPU Linodes" in region.capabilities:
                    # Newer regions with "2" suffix (e.g., de-fra-2) typically have RTX 4000 Ada
                    # Older regions without suffix typically have RTX 6000 Ada
                    if region.id.endswith("-2") or region.id in [
                        "us-ord",
                        "us-sea",
                        "jp-osa",
                        "fr-par",
                    ]:
                        rtx4000_regions.add(region.id)
                    else:
                        rtx6000_regions.add(region.id)

            # If we didn't find any regions, fall back to hardcoded lists
            if not rtx4000_regions and not rtx6000_regions:
                return {"rtx4000": RTX4000_REGIONS, "rtx6000": RTX6000_REGIONS}

            return {"rtx4000": rtx4000_regions, "rtx6000": rtx6000_regions}

        except Exception:
            # Fall back to hardcoded regions
            return {"rtx4000": RTX4000_REGIONS, "rtx6000": RTX6000_REGIONS}

    def _build_type_details(self, api_type, gpu_regions: Dict[str, Set[str]]):
        if not hasattr(api_type, "gpus") or api_type.gpus <= 0:
            return None

        gpu_name = self._extract_gpu_name_from_label(api_type.label, api_type.id)
        vram_per_gpu = self._extract_vram_from_gpu_type(gpu_name, api_type.label)
        hourly_cost = float(api_type.price.hourly) if hasattr(api_type, "price") else 0.0
        regions = self._regions_for_type(api_type.id, gpu_regions)

        return {
            "gpus": api_type.gpus,
            "gpu_name": gpu_name,
            "vram_per_gpu": vram_per_gpu,
            "hourly_cost": hourly_cost,
            "regions": regions,
            "label": api_type.label,
        }

    @staticmethod
    def _regions_for_type(type_id: str, gpu_regions: Dict[str, Set[str]]) -> Set[str]:
        if "rtx4000" in type_id.lower():
            return gpu_regions.get("rtx4000", set())
        if "rtx6000" in type_id.lower():
            return gpu_regions.get("rtx6000", set())
        return gpu_regions.get("rtx4000", set()) | gpu_regions.get("rtx6000", set())

    @staticmethod
    def _extract_gpu_name_from_label(label: str, type_id: str) -> str:
        """Extract GPU name from label or type ID.

        Args:
            label: Type label (e.g., "Dedicated 32GB + RTX6000 GPU x1")
            type_id: Type ID (e.g., "g1-gpu-rtx6000-1")

        Returns:
            GPU name string
        """
        # Check label for GPU model names
        if "RTX6000" in label or "RTX 6000" in label:
            return RTX_6000_NAME
        elif "RTX4000" in label or "RTX 4000" in label:
            return RTX_4000_NAME

        # Check type ID
        if "rtx6000" in type_id.lower():
            return RTX_6000_NAME
        elif "rtx4000" in type_id.lower():
            return RTX_4000_NAME

        # Check for other GPU types
        if "V100" in label:
            return "Tesla V100"
        elif "A100" in label:
            return "A100"

        return "GPU"

    @staticmethod
    def _extract_vram_from_gpu_type(gpu_name: str, label: str) -> int:
        """Extract VRAM amount from GPU type name or label.

        Args:
            gpu_name: GPU type name (e.g., "NVIDIA RTX 6000 Ada Generation")
            label: Type label (e.g., "Linode GPU RTX6000 96GB")

        Returns:
            VRAM per GPU in GB
        """
        known_vram = LinodeProvider._vram_from_known_gpu(gpu_name, label)
        if known_vram is not None:
            return known_vram

        extracted_vram = LinodeProvider._vram_from_label(label)
        if extracted_vram is not None:
            return extracted_vram

        return 24

    @staticmethod
    def _vram_from_known_gpu(gpu_name: str, label: str) -> Optional[int]:
        if RTX_6000_NAME in gpu_name or "rtx6000" in label.lower():
            return 48
        if RTX_4000_NAME in gpu_name or "rtx4000" in label.lower():
            return 20
        if "RTX 4000" in gpu_name:
            return 20
        if "V100" in gpu_name:
            return 32
        if "A100" in gpu_name:
            return 40
        return None

    @staticmethod
    def _vram_from_label(label: str) -> Optional[int]:
        total_gb = None
        upper_label = label.upper()
        gb_index = upper_label.find("GB")
        if gb_index == -1:
            return None

        num_end = gb_index
        num_start = num_end
        while num_start > 0 and upper_label[num_start - 1].isdigit():
            num_start -= 1
        if num_start == num_end:
            return None

        total_gb = int(upper_label[num_start:num_end])
        gpu_count = LinodeProvider._gpu_count_from_label(label)
        return total_gb // max(gpu_count, 1)

    @staticmethod
    def _gpu_count_from_label(label: str) -> int:
        if "2x" in label or "Dual" in label:
            return 2
        if "4x" in label or "Quad" in label:
            return 4
        if "8x" in label or "Octo" in label:
            return 8
        return 1

    @staticmethod
    def _get_hardcoded_gpu_types() -> Dict[str, Any]:
        """Get hardcoded GPU type data as fallback.

        Returns:
            Dictionary mapping type_id to type details
        """
        return {
            type_id: {
                "gpus": specs["gpus"],
                "gpu_name": RTX_6000_NAME if "rtx6000" in type_id else RTX_4000_NAME,
                "vram_per_gpu": specs["vram_per_gpu"],
                "hourly_cost": specs["hourly_cost"],
                "regions": specs["regions"],
                "label": f"{specs['gpus']}x GPU",
            }
            for type_id, specs in GPU_TYPES.items()
        }

    def list_regions(self, gpu_capable_only: bool = True) -> List[Region]:
        """List available Linode regions.

        Args:
            gpu_capable_only: Only return GPU-capable regions

        Returns:
            List of Region objects
        """
        regions = []

        if gpu_capable_only:
            # Get GPU-capable regions from API types
            gpu_regions = self._get_gpu_regions()

            for region_id in gpu_regions:
                name, country = REGION_METADATA.get(region_id, (region_id, "unknown"))
                regions.append(Region(id=region_id, name=name, country=country, gpu_available=True))
        else:
            # Query API for all regions
            try:
                api_regions = self.client.regions()
                gpu_regions = self._get_gpu_regions()

                for api_region in api_regions:
                    regions.append(
                        Region(
                            id=api_region.id,
                            name=api_region.label or api_region.id,
                            country=api_region.country or "unknown",
                            gpu_available=api_region.id in gpu_regions,
                        )
                    )
            except Exception as e:
                console.print(f"[yellow]Warning: Could not fetch regions from API: {e}[/yellow]")
                # Fall back to hardcoded GPU regions
                return self.list_regions(gpu_capable_only=True)

        return sorted(regions, key=lambda r: r.id)

    def _get_gpu_regions(self) -> Set[str]:
        """Get all GPU-capable regions from API types.

        Returns:
            Set of region IDs that support GPU instances
        """
        # Fetch region info which doesn't depend on types
        gpu_region_map = self._fetch_gpu_regions()
        return gpu_region_map.get("rtx4000", set()) | gpu_region_map.get("rtx6000", set())

    def list_vm_types(self, region: Optional[str] = None, gpu_only: bool = True) -> List[VMType]:
        """List available Linode VM types.

        Args:
            region: Filter by region (returns only types available in that region)
            gpu_only: Only return GPU types

        Returns:
            List of VMType objects
        """
        vm_types = []

        if gpu_only:
            # Fetch GPU types from API
            type_data = self._fetch_types_from_api()

            for type_id, specs in type_data.items():
                # Filter by region if specified
                if region and region not in specs.get("regions", set()):
                    continue

                total_vram = specs["gpus"] * specs["vram_per_gpu"]
                gpu_name = specs.get("gpu_name", "GPU")
                gpu_label = f"{specs['gpus']}x " if specs["gpus"] > 1 else ""
                name = f"{gpu_label}{gpu_name} ({total_vram}GB)"

                vm_types.append(
                    VMType(
                        id=type_id,
                        name=name,
                        gpus=specs["gpus"],
                        vram_per_gpu=specs["vram_per_gpu"],
                        total_vram=total_vram,
                        hourly_cost=specs["hourly_cost"],
                        available_in_regions=list(specs.get("regions", set())),
                    )
                )

        return sorted(vm_types, key=lambda t: t.hourly_cost)

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
        """Create a new Linode instance.

        Args:
            region: Linode region ID
            vm_type: Linode type ID (e.g., g1-gpu-rtx6000-1)
            label: Instance label
            ssh_key: SSH public key for root access
            cloud_init_config: Cloud-init configuration
            firewall_id: Linode firewall ID (optional)
            **kwargs: Additional parameters (unused)

        Returns:
            VMInstance object
        """
        console.print(f"Creating Linode: {label}")

        # Generate random root password (required by API)
        root_pass = self._generate_password()

        try:
            # Configure network interface (public interface format)
            interface_config = {
                "public": {},  # Empty object for default public interface
                "primary": True,
            }

            # Create instance parameters
            create_params = {
                "ltype": vm_type,
                "region": region,
                "image": "linode/ubuntu24.04",
                "label": label,
                "root_pass": root_pass,
                "authorized_keys": [],  # Using cloud-init for SSH
                "interfaces": [interface_config],
                "metadata": {"user_data": base64.b64encode(cloud_init_config.encode()).decode()},
            }

            # Add firewall if provided
            if firewall_id:
                create_params["firewall_id"] = int(firewall_id)

            instance = self.client.linode.instance_create(**create_params)

            console.print(f"✓ Created Linode: {instance.id} ({instance.ipv4[0]})")

            return VMInstance(
                provider_instance_id=str(instance.id),
                ip_address=instance.ipv4[0],
                region=region,
                type=vm_type,
                status=instance.status,
                provider_type=ProviderType.LINODE,
            )

        except Exception as e:
            console.print(f"[red]✗ Failed to create Linode: {e}[/red]")
            raise

    def delete_instance(self, instance_id: str) -> bool:
        """Delete a Linode instance.

        Args:
            instance_id: Linode ID as string

        Returns:
            True if deletion successful
        """
        try:
            linode_id = int(instance_id)
            instance = self.client.load(Instance, linode_id)
            instance.delete()
            console.print(f"✓ Deleted Linode: {linode_id}")
            return True
        except Exception as e:
            console.print(f"[yellow]⚠ Failed to delete Linode {instance_id}: {e}[/yellow]")
            return False

    def get_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """Get Linode instance status.

        Args:
            instance_id: Linode ID as string

        Returns:
            Dictionary with instance details
        """
        try:
            linode_id = int(instance_id)
            instance = self.client.load(Instance, linode_id)

            return {
                "id": instance.id,
                "label": instance.label,
                "status": instance.status,
                "region": instance.region.id,
                "type": instance.type.id,
                "ipv4": instance.ipv4,
                "ipv6": instance.ipv6,
                "created": instance.created,
                "updated": instance.updated,
            }
        except Exception as e:
            console.print(f"[yellow]⚠ Failed to get status for Linode {instance_id}: {e}[/yellow]")
            return {"error": str(e)}

    def get_provider_type(self) -> ProviderType:
        """Return the provider type."""
        return ProviderType.LINODE

    def get_gpu_count(self, vm_type: str) -> int:
        """Get GPU count for a Linode type.

        Args:
            vm_type: Linode type ID

        Returns:
            Number of GPUs, or 1 if unknown
        """
        type_data = self._fetch_types_from_api()
        specs = type_data.get(vm_type)
        if specs:
            return specs["gpus"]

        # Fallback to hardcoded data
        specs = GPU_TYPES.get(vm_type)
        return specs["gpus"] if specs else 1

    def get_hourly_cost(self, vm_type: str) -> float:
        """Get hourly cost for a Linode type.

        Args:
            vm_type: Linode type ID

        Returns:
            Hourly cost in USD, or 0.0 if unknown
        """
        type_data = self._fetch_types_from_api()
        specs = type_data.get(vm_type)
        if specs:
            return specs["hourly_cost"]

        # Fallback to hardcoded data
        specs = GPU_TYPES.get(vm_type)
        return specs["hourly_cost"] if specs else 0.0

    @staticmethod
    def _generate_password(length: int = 32) -> str:
        """Generate a random password for Linode root account."""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))


# Register the Linode provider with the factory
CloudProviderFactory.register_provider(ProviderType.LINODE, LinodeProvider)
