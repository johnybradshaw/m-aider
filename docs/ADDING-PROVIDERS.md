# Adding New Cloud Providers to maider

This guide explains how to add support for new cloud providers (DigitalOcean, Scaleway, AWS, etc.) to maider.

## Architecture Overview

maider uses a provider abstraction layer that allows multiple cloud providers to coexist. The architecture consists of:

1. **Abstract Interface** (`src/maider/providers/base.py`):
   - `CloudProvider` - Abstract base class defining the provider interface
   - `ProviderType` - Enum of supported providers
   - `Region`, `VMType`, `VMInstance` - Data structures
   - `CloudProviderFactory` - Factory for instantiating providers

2. **Provider Implementations** (`src/maider/providers/<provider>.py`):
   - Each provider implements the `CloudProvider` interface
   - Handles provider-specific API calls and data formats
   - Registers itself with the factory

3. **Provider-Agnostic Commands** (`src/maider/commands/*.py`):
   - Commands use the factory to get provider instances
   - Work with abstract interfaces, not provider specifics

## Step-by-Step Guide

### 1. Research the Provider's GPU Offerings

Before implementing, gather information about:

- **GPU Instance Types**: What GPU types are available? (e.g., NVIDIA A100, H100, RTX 4000)
- **Regions**: Which data center regions support GPU instances?
- **Pricing**: Hourly costs for each GPU type
- **API Documentation**: How to create/delete/query instances
- **Cloud-init Support**: Does the provider support cloud-init for VM initialization?

**Example for Linode:**
- GPU Types: RTX 4000 Ada (20GB), RTX 6000 Ada (48GB)
- GPU Regions: 12 regions (us-east, eu-central, etc.)
- Pricing: $0.52-$12/hour depending on GPU count
- API: https://www.linode.com/docs/api/
- Cloud-init: ✅ Supported

### 2. Add Provider to ProviderType Enum

Edit `src/maider/providers/base.py`:

```python
class ProviderType(Enum):
    """Supported cloud provider types."""
    LINODE = "linode"
    DIGITALOCEAN = "digitalocean"
    SCALEWAY = "scaleway"
    YOUR_PROVIDER = "your_provider"  # Add this
```

### 3. Create Provider Implementation File

Create `src/maider/providers/<your_provider>.py`:

```python
"""Your Provider cloud provider implementation."""

from typing import List, Optional, Dict, Any
from .base import (
    CloudProvider,
    ProviderType,
    Region,
    VMType,
    VMInstance,
    CloudProviderFactory,
)

# GPU-capable regions (research from provider docs)
GPU_REGIONS = {
    "region-1",
    "region-2",
    # ...
}

# GPU type information with specs and pricing
GPU_TYPES = {
    "gpu-type-1": {"gpus": 1, "vram_per_gpu": 20, "hourly_cost": 0.50},
    "gpu-type-2": {"gpus": 2, "vram_per_gpu": 40, "hourly_cost": 1.00},
    # ...
}

# Region metadata (name, country code)
REGION_METADATA = {
    "region-1": ("New York, NY", "us"),
    "region-2": ("London, UK", "gb"),
    # ...
}


class YourProviderProvider(CloudProvider):
    """Your Provider cloud provider implementation."""

    def __init__(self, api_token: str, **kwargs):
        """Initialize provider with API token."""
        self.api_token = api_token
        # Initialize provider SDK client here
        # self.client = YourProviderClient(token=api_token)

    def get_provider_type(self) -> ProviderType:
        """Return provider type."""
        return ProviderType.YOUR_PROVIDER

    def list_regions(self, gpu_capable_only: bool = True) -> List[Region]:
        """List available regions."""
        regions = []

        if gpu_capable_only:
            for region_id in GPU_REGIONS:
                name, country = REGION_METADATA.get(region_id, (region_id, "unknown"))
                regions.append(
                    Region(
                        id=region_id,
                        name=name,
                        country=country,
                        gpu_available=True,
                    )
                )
        else:
            # Query all regions from provider API
            pass

        return regions

    def list_vm_types(
        self, region: Optional[str] = None, gpu_only: bool = True
    ) -> List[VMType]:
        """List available VM types."""
        vm_types = []

        for type_id, specs in GPU_TYPES.items():
            # Determine which regions this type is available in
            available_regions = list(GPU_REGIONS)

            if region and region not in available_regions:
                continue

            vm_types.append(
                VMType(
                    id=type_id,
                    name=f"{specs['gpus']}x GPU ({specs['vram_per_gpu']}GB VRAM)",
                    gpus=specs["gpus"],
                    vram_per_gpu=specs["vram_per_gpu"],
                    total_vram=specs["gpus"] * specs["vram_per_gpu"],
                    hourly_cost=specs["hourly_cost"],
                    available_in_regions=available_regions,
                )
            )

        return vm_types

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
        """Create a new VM instance."""
        # Call provider API to create instance
        # Example pseudo-code:
        # instance = self.client.create_instance(
        #     region=region,
        #     type=vm_type,
        #     name=label,
        #     ssh_keys=[ssh_key],
        #     user_data=cloud_init_config,
        # )

        # Return VMInstance with standardized format
        return VMInstance(
            provider_instance_id=str(instance.id),
            ip_address=instance.public_ip,
            region=region,
            type=vm_type,
            status="provisioning",
            provider_type=self.get_provider_type(),
        )

    def delete_instance(self, instance_id: str) -> bool:
        """Delete a VM instance."""
        try:
            # Call provider API to delete instance
            # self.client.delete_instance(instance_id)
            return True
        except Exception as e:
            console.print(f"[red]Error deleting instance: {e}[/red]")
            return False

    def get_instance_status(self, instance_id: str) -> Dict[str, Any]:
        """Get current status of a VM instance."""
        try:
            # Query provider API for instance status
            # instance = self.client.get_instance(instance_id)
            return {
                "status": "running",  # or instance.status
                "ip": "192.0.2.1",    # instance.public_ip
            }
        except Exception:
            return {"status": "unknown"}

    @staticmethod
    def get_gpu_count(vm_type: str) -> int:
        """Get GPU count for a VM type."""
        specs = GPU_TYPES.get(vm_type, {})
        return specs.get("gpus", 0)

    @staticmethod
    def get_hourly_cost(vm_type: str) -> float:
        """Get hourly cost for a VM type."""
        specs = GPU_TYPES.get(vm_type, {})
        return specs.get("hourly_cost", 0.0)


# Register provider with factory
CloudProviderFactory.register_provider(
    ProviderType.YOUR_PROVIDER, YourProviderProvider
)
```

### 4. Register Provider in __init__.py

Edit `src/maider/providers/__init__.py` to import your provider:

```python
from .base import (
    CloudProvider,
    ProviderType,
    Region,
    VMType,
    VMInstance,
    CloudProviderFactory,
)
from .linode import LinodeProvider
from .your_provider import YourProviderProvider  # Add this

__all__ = [
    "CloudProvider",
    "ProviderType",
    "Region",
    "VMType",
    "VMInstance",
    "CloudProviderFactory",
    "LinodeProvider",
    "YourProviderProvider",  # Add this
]
```

### 5. Update Configuration System

Edit `src/maider/config.py` to support provider-specific validation:

```python
def get_gpu_count(self) -> int:
    """Get GPU count for configured VM type."""
    if self.provider == "linode" and self.linode_token:
        from maider.providers.linode import LinodeProvider
        provider = LinodeProvider(api_token=self.linode_token)
        return provider.get_gpu_count(self.type)
    elif self.provider == "your_provider" and self.your_provider_token:
        from maider.providers.your_provider import YourProviderProvider
        provider = YourProviderProvider(api_token=self.your_provider_token)
        return provider.get_gpu_count(self.type)
    # ... existing fallback logic

def get_hourly_cost(self) -> float:
    """Get hourly cost for configured VM type."""
    if self.provider == "linode" and self.linode_token:
        from maider.providers.linode import LinodeProvider
        provider = LinodeProvider(api_token=self.linode_token)
        return provider.get_hourly_cost(self.type)
    elif self.provider == "your_provider" and self.your_provider_token:
        from maider.providers.your_provider import YourProviderProvider
        provider = YourProviderProvider(api_token=self.your_provider_token)
        return provider.get_hourly_cost(self.type)
    # ... existing fallback
```

### 6. Update Wizard Command

Edit `src/maider/commands/wizard.py` to show your provider as an option:

```python
def cmd():
    """Interactive setup wizard."""
    console.print("\n[bold cyan]Step 0: Select Cloud Provider[/bold cyan]\n")

    providers = [
        "1) Linode",
        "2) Your Provider",
    ]

    for p in providers:
        console.print(f"  {p}")

    provider_choice = Prompt.ask("Choice", choices=["1", "2"], default="1")

    if provider_choice == "1":
        provider = "linode"
        # Load Linode GPU data
    elif provider_choice == "2":
        provider = "your_provider"
        # Load Your Provider GPU data
```

### 7. Update Validation Command

Edit `src/maider/commands/validate.py`:

```python
def get_gpu_regions_for_provider(provider: str) -> set:
    """Get GPU-capable regions for a provider."""
    try:
        provider_type = ProviderType(provider.lower())
        if provider_type == ProviderType.LINODE:
            from maider.providers.linode import GPU_REGIONS
            return GPU_REGIONS
        elif provider_type == ProviderType.YOUR_PROVIDER:
            from maider.providers.your_provider import GPU_REGIONS
            return GPU_REGIONS
    except (ValueError, ImportError):
        pass
    return set()
```

### 8. Write Tests

Create `tests/test_<your_provider>.py`:

```python
"""Tests for Your Provider implementation."""

import pytest
from src.maider.providers.your_provider import YourProviderProvider, GPU_REGIONS, GPU_TYPES
from src.maider.providers.base import ProviderType


@pytest.mark.unit
class TestYourProviderProvider:
    """Test Your Provider implementation."""

    def test_provider_type(self):
        """Test provider returns correct type."""
        provider = YourProviderProvider(api_token="test_token")
        assert provider.get_provider_type() == ProviderType.YOUR_PROVIDER

    def test_list_gpu_regions(self):
        """Test listing GPU-capable regions."""
        provider = YourProviderProvider(api_token="test_token")
        regions = provider.list_regions(gpu_capable_only=True)

        assert len(regions) > 0
        assert all(r.gpu_available for r in regions)
        assert all(r.id in GPU_REGIONS for r in regions)

    def test_list_vm_types(self):
        """Test listing GPU VM types."""
        provider = YourProviderProvider(api_token="test_token")
        vm_types = provider.list_vm_types(gpu_only=True)

        assert len(vm_types) > 0
        assert all(vt.gpus > 0 for vt in vm_types)

    def test_get_gpu_count(self):
        """Test GPU count lookup."""
        provider = YourProviderProvider(api_token="test_token")
        for type_id, specs in GPU_TYPES.items():
            count = provider.get_gpu_count(type_id)
            assert count == specs["gpus"]

    def test_get_hourly_cost(self):
        """Test cost lookup."""
        provider = YourProviderProvider(api_token="test_token")
        for type_id, specs in GPU_TYPES.items():
            cost = provider.get_hourly_cost(type_id)
            assert cost == specs["hourly_cost"]


@pytest.mark.unit
class TestYourProviderGPURegions:
    """Test GPU region constants."""

    def test_gpu_regions_not_empty(self):
        """Test GPU_REGIONS is defined."""
        assert len(GPU_REGIONS) > 0

    def test_gpu_regions_is_set(self):
        """Test GPU_REGIONS is a set for efficient lookups."""
        assert isinstance(GPU_REGIONS, set)


@pytest.mark.unit
class TestYourProviderGPUTypes:
    """Test GPU type constants."""

    def test_gpu_types_not_empty(self):
        """Test GPU_TYPES is defined."""
        assert len(GPU_TYPES) > 0

    def test_gpu_types_have_required_fields(self):
        """Test each GPU type has required fields."""
        required = {"gpus", "vram_per_gpu", "hourly_cost"}

        for type_id, specs in GPU_TYPES.items():
            for field in required:
                assert field in specs, f"{type_id} missing {field}"
```

### 9. Update Documentation

Update the following files:

**README.md:**
- Add your provider to the supported providers list
- Update examples to show provider selection

**CLAUDE.md:**
- Document your provider's GPU offerings
- Add provider-specific configuration examples

### 10. Test the Implementation

```bash
# Run unit tests
pytest tests/test_<your_provider>.py -v

# Run all tests
pytest tests/ -v

# Manual test with wizard
maider wizard
# Select your provider and verify it works end-to-end
```

## Provider Implementation Checklist

- [ ] Research provider's GPU offerings, regions, pricing, API
- [ ] Add provider to `ProviderType` enum
- [ ] Create provider implementation file
- [ ] Define `GPU_REGIONS`, `GPU_TYPES`, `REGION_METADATA` constants
- [ ] Implement all `CloudProvider` abstract methods
- [ ] Add static helper methods: `get_gpu_count()`, `get_hourly_cost()`
- [ ] Register provider with `CloudProviderFactory`
- [ ] Update `src/maider/providers/__init__.py`
- [ ] Update `src/maider/config.py` for provider-aware methods
- [ ] Update `src/maider/commands/wizard.py` to show provider
- [ ] Update `src/maider/commands/validate.py` for GPU region validation
- [ ] Write comprehensive tests
- [ ] Update README.md and CLAUDE.md
- [ ] Test end-to-end: wizard → up → status → down

## Example: LinodeProvider

The LinodeProvider in `src/maider/providers/linode.py` is a complete reference implementation. Key highlights:

1. **Uses Official SDK**: `linode_api4` library for API calls
2. **Hardcoded GPU Data**: GPU_REGIONS and GPU_TYPES based on documentation
3. **Helper Methods**: Static methods for GPU count and cost lookups
4. **Error Handling**: Graceful handling of API errors
5. **Cloud-init Support**: Passes user_data for VM initialization

## Tips and Best Practices

### API Client Libraries

Use official SDK/client libraries when available:
- **Linode**: `linode_api4`
- **DigitalOcean**: `python-digitalocean`
- **Scaleway**: `scaleway-sdk`
- **AWS**: `boto3`

### GPU Data Management

Hardcode GPU data for reliability:
- GPU regions change infrequently
- Hardcoded data ensures consistent validation
- Update when provider adds new GPU regions/types

### Error Handling

Handle API errors gracefully:
```python
try:
    instance = self.client.create_instance(...)
except ProviderAPIError as e:
    console.print(f"[red]Provider API error: {e}[/red]")
    raise
```

### Cloud-init Support

Ensure your provider supports cloud-init:
- If not, consider alternative initialization methods
- Document any provider-specific requirements

### Testing Strategy

Test at multiple levels:
1. **Unit tests**: Provider methods in isolation (mock API calls)
2. **Integration tests**: Factory and config system
3. **End-to-end tests**: Full wizard → create → destroy flow

## Common Pitfalls

### 1. Forgetting to Register Provider

Make sure you call:
```python
CloudProviderFactory.register_provider(ProviderType.YOUR_PROVIDER, YourProviderProvider)
```

### 2. Inconsistent GPU Data

Ensure GPU_REGIONS and GPU_TYPES are accurate:
- Check provider documentation
- Verify with API calls
- Keep pricing up to date

### 3. Not Handling Provider-Specific Fields

Some providers may require additional fields:
- Image IDs (different per provider)
- Network configurations
- Storage options

Use `**kwargs` in `create_instance()` for provider-specific parameters.

### 4. Missing Static Helper Methods

Commands depend on these static methods:
```python
@staticmethod
def get_gpu_count(vm_type: str) -> int:
    ...

@staticmethod
def get_hourly_cost(vm_type: str) -> float:
    ...
```

### 5. Cloud-init Compatibility

Not all providers support cloud-init the same way:
- Field name: `user_data` (DigitalOcean) vs `metadata.user-data` (Linode)
- Format: Base64-encoded vs plain text
- Size limits: Different max sizes

## Getting Help

- Study `src/maider/providers/linode.py` for a complete example
- Check provider API documentation thoroughly
- Ask in GitHub Discussions for guidance
- Open a draft PR for early feedback

## Contributing

When contributing a new provider:

1. Open an issue first to discuss the provider
2. Follow this guide for implementation
3. Include comprehensive tests (aim for >80% coverage)
4. Update documentation (README.md, CLAUDE.md)
5. Test end-to-end before submitting PR
6. Include example `.env` configuration in PR description

We appreciate contributions that expand maider's multi-provider support!
