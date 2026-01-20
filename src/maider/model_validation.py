"""Model configuration validation for vLLM deployments.

Fetches model configs from HuggingFace and validates that the configured
max_model_len doesn't exceed the model's actual max_position_embeddings.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# Known context length overrides for models where HuggingFace config may not reflect
# the actual supported context length (e.g., models with RoPE scaling)
KNOWN_CONTEXT_LENGTHS: dict[str, int] = {
    # Qwen2.5 models support 32k context with proper RoPE scaling
    "Qwen/Qwen2.5-Coder-7B-Instruct": 32768,
    "Qwen/Qwen2.5-Coder-14B-Instruct": 32768,
    "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ": 32768,
    "Qwen/Qwen2.5-Coder-32B-Instruct": 32768,
    "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ": 32768,
    "Qwen/Qwen2.5-Coder-70B-Instruct": 32768,
    "Qwen/Qwen2.5-Coder-70B-Instruct-AWQ": 32768,
}

# HuggingFace API timeout
HF_API_TIMEOUT = 30


@dataclass
class ModelConfigInfo:
    """Information about a model's configuration limits."""

    model_id: str
    max_position_embeddings: Optional[int] = None
    model_max_length: Optional[int] = None
    rope_scaling: Optional[dict] = None
    error: Optional[str] = None

    @property
    def effective_max_length(self) -> Optional[int]:
        """Get the effective maximum context length for this model.

        Returns the most restrictive value between max_position_embeddings
        and model_max_length, accounting for RoPE scaling if present.
        """
        if self.max_position_embeddings is None and self.model_max_length is None:
            return None

        # Start with max_position_embeddings
        max_len = self.max_position_embeddings

        # Apply RoPE scaling factor if present
        if max_len and self.rope_scaling:
            factor = self.rope_scaling.get("factor", 1.0)
            if isinstance(factor, (int, float)) and factor > 1.0:
                max_len = int(max_len * factor)

        # model_max_length may be more restrictive
        if self.model_max_length is not None:
            if max_len is None:
                max_len = self.model_max_length
            else:
                # Use the smaller of the two if model_max_length is set
                max_len = min(max_len, self.model_max_length)

        return max_len


@dataclass
class ValidationResult:
    """Result of max_model_len validation."""

    is_valid: bool
    model_id: str
    requested_max_len: int
    model_max_len: Optional[int] = None
    suggested_max_len: Optional[int] = None
    warning: Optional[str] = None
    error: Optional[str] = None
    allow_override: bool = False

    @property
    def message(self) -> str:
        """Get a human-readable message about the validation result."""
        if self.error:
            return f"Error: {self.error}"

        if self.is_valid:
            if self.warning:
                return self.warning
            return f"max_model_len={self.requested_max_len} is valid for {self.model_id}"

        return (
            f"max_model_len={self.requested_max_len} exceeds model limit of "
            f"{self.model_max_len}. Suggested value: {self.suggested_max_len}"
        )


def fetch_model_config(model_id: str, hf_token: Optional[str] = None) -> ModelConfigInfo:
    """Fetch model configuration from HuggingFace.

    Args:
        model_id: HuggingFace model ID (e.g., "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ")
        hf_token: Optional HuggingFace token for private models

    Returns:
        ModelConfigInfo with the model's configuration limits
    """
    # Check for known overrides first
    if model_id in KNOWN_CONTEXT_LENGTHS:
        return ModelConfigInfo(
            model_id=model_id,
            max_position_embeddings=KNOWN_CONTEXT_LENGTHS[model_id],
        )

    url = f"https://huggingface.co/{model_id}/resolve/main/config.json"
    headers = {}
    if hf_token:
        headers["Authorization"] = f"Bearer {hf_token}"

    try:
        response = requests.get(url, headers=headers, timeout=HF_API_TIMEOUT)

        if response.status_code == 404:
            return ModelConfigInfo(
                model_id=model_id,
                error=f"Model config not found at HuggingFace: {model_id}",
            )

        if response.status_code == 401:
            return ModelConfigInfo(
                model_id=model_id,
                error="Authentication required. Provide a valid HuggingFace token.",
            )

        if response.status_code != 200:
            return ModelConfigInfo(
                model_id=model_id,
                error=f"Failed to fetch config: HTTP {response.status_code}",
            )

        config = response.json()

        return ModelConfigInfo(
            model_id=model_id,
            max_position_embeddings=config.get("max_position_embeddings"),
            model_max_length=config.get("model_max_length"),
            rope_scaling=config.get("rope_scaling"),
        )

    except requests.exceptions.Timeout:
        return ModelConfigInfo(
            model_id=model_id,
            error="Timeout fetching model config from HuggingFace",
        )
    except requests.exceptions.RequestException as e:
        return ModelConfigInfo(
            model_id=model_id,
            error=f"Network error fetching model config: {e}",
        )
    except ValueError as e:
        return ModelConfigInfo(
            model_id=model_id,
            error=f"Invalid JSON in model config: {e}",
        )


def validate_max_model_len(
    model_id: str,
    max_model_len: int,
    hf_token: Optional[str] = None,
) -> ValidationResult:
    """Validate that max_model_len doesn't exceed the model's limits.

    Args:
        model_id: HuggingFace model ID
        max_model_len: The configured max_model_len value
        hf_token: Optional HuggingFace token for private models

    Returns:
        ValidationResult indicating whether the value is valid and any suggestions
    """
    # Fetch model config
    config_info = fetch_model_config(model_id, hf_token)

    if config_info.error:
        # If we can't fetch the config, return a warning but allow override
        return ValidationResult(
            is_valid=True,
            model_id=model_id,
            requested_max_len=max_model_len,
            warning=f"Could not validate max_model_len: {config_info.error}. "
            "Proceeding with configured value.",
            allow_override=True,
        )

    model_max_len = config_info.effective_max_length

    if model_max_len is None:
        # No limit found in config
        return ValidationResult(
            is_valid=True,
            model_id=model_id,
            requested_max_len=max_model_len,
            warning="Model config does not specify max_position_embeddings. "
            "Proceeding with configured value.",
            allow_override=True,
        )

    if max_model_len <= model_max_len:
        # Value is within limits
        return ValidationResult(
            is_valid=True,
            model_id=model_id,
            requested_max_len=max_model_len,
            model_max_len=model_max_len,
        )

    # Value exceeds model limits
    # Suggest a reasonable value (the model's max or a power of 2 <= model's max)
    suggested = _calculate_suggested_max_len(model_max_len)

    return ValidationResult(
        is_valid=False,
        model_id=model_id,
        requested_max_len=max_model_len,
        model_max_len=model_max_len,
        suggested_max_len=suggested,
        allow_override=True,  # User can override with VLLM_ALLOW_LONG_MAX_MODEL_LEN
    )


def _calculate_suggested_max_len(model_max: int) -> int:
    """Calculate a suggested max_model_len value.

    Returns the largest power of 2 that is <= model_max,
    or model_max itself if it's already a power of 2.
    """
    # Common context lengths in order of preference
    common_lengths = [131072, 65536, 32768, 16384, 8192, 4096, 2048, 1024]

    for length in common_lengths:
        if length <= model_max:
            return length

    return model_max


def get_model_context_limit(
    model_id: str,
    hf_token: Optional[str] = None,
) -> Optional[int]:
    """Get the maximum context length for a model.

    Convenience function that returns just the limit, or None if unknown.

    Args:
        model_id: HuggingFace model ID
        hf_token: Optional HuggingFace token for private models

    Returns:
        Maximum context length, or None if unknown
    """
    config_info = fetch_model_config(model_id, hf_token)
    return config_info.effective_max_length
