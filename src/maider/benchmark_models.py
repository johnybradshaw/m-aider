"""Model selection and categorization for benchmarking."""

from dataclasses import dataclass
from typing import List, Optional


@dataclass
class ModelConfig:
    """Configuration for a model to benchmark."""

    id: str  # HuggingFace model ID
    category: str  # Model size category (7b, 14b, 30b, 70b, etc.)
    quantization: str  # Quantization type (awq, gptq, full, etc.)
    min_vram_gb: int  # Minimum total VRAM required
    recommended_context: int  # Recommended max_model_len


# Model database organized by category
MODEL_CATEGORIES = {
    "7b": [
        ModelConfig(
            id="Qwen/Qwen2.5-Coder-7B-Instruct",
            category="7b",
            quantization="full",
            min_vram_gb=16,
            recommended_context=32768,
        ),
        ModelConfig(
            id="deepseek-ai/deepseek-coder-7b-instruct-v1.5",
            category="7b",
            quantization="full",
            min_vram_gb=16,
            recommended_context=16384,
        ),
    ],
    "14b": [
        ModelConfig(
            id="Qwen/Qwen2.5-Coder-14B-Instruct-AWQ",
            category="14b",
            quantization="awq",
            min_vram_gb=18,
            recommended_context=32768,
        ),
        ModelConfig(
            id="Qwen/Qwen2.5-Coder-14B-Instruct",
            category="14b",
            quantization="full",
            min_vram_gb=32,
            recommended_context=32768,
        ),
    ],
    "30b": [
        ModelConfig(
            id="Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
            category="30b",
            quantization="awq",
            min_vram_gb=35,
            recommended_context=32768,
        ),
        ModelConfig(
            id="deepseek-ai/deepseek-coder-33b-instruct",
            category="30b",
            quantization="full",
            min_vram_gb=70,
            recommended_context=16384,
        ),
    ],
    "70b": [
        ModelConfig(
            id="Qwen/Qwen2.5-72B-Instruct-AWQ",
            category="70b",
            quantization="awq",
            min_vram_gb=70,
            recommended_context=32768,
        ),
        ModelConfig(
            id="deepseek-ai/DeepSeek-Coder-V2-Instruct",
            category="70b",
            quantization="full",
            min_vram_gb=140,
            recommended_context=32768,
        ),
    ],
}


def get_recommended_models(vram_gb: int, prefer_quantized: bool = True) -> List[ModelConfig]:
    """Get recommended models for given VRAM capacity.

    Args:
        vram_gb: Total VRAM available in GB
        prefer_quantized: Prefer quantized models (AWQ/GPTQ) over full precision

    Returns:
        List of ModelConfig objects suitable for the VRAM capacity
    """
    suitable_models: List[ModelConfig] = []

    # Collect all models that fit in VRAM
    for category, models in MODEL_CATEGORIES.items():
        for model in models:
            if model.min_vram_gb <= vram_gb:
                suitable_models.append(model)

    # Sort by preference: quantized first if prefer_quantized, then by size (largest first)
    def sort_key(model: ModelConfig) -> tuple:
        # Priority order: 1) quantization preference, 2) VRAM requirement (larger = better)
        is_quantized = model.quantization in ["awq", "gptq"]
        if prefer_quantized:
            return (not is_quantized, -model.min_vram_gb)
        else:
            return (is_quantized, -model.min_vram_gb)

    suitable_models.sort(key=sort_key)

    return suitable_models


def get_model_category(model_id: str) -> str:
    """Determine model category from model ID.

    Args:
        model_id: HuggingFace model ID

    Returns:
        Model category (e.g., "7b", "14b", "30b", "70b")
    """
    model_id_lower = model_id.lower()

    # Check for explicit size markers
    if "70b" in model_id_lower or "72b" in model_id_lower:
        return "70b"
    elif "30b" in model_id_lower or "32b" in model_id_lower or "33b" in model_id_lower:
        return "30b"
    elif "14b" in model_id_lower or "15b" in model_id_lower:
        return "14b"
    elif "7b" in model_id_lower or "8b" in model_id_lower:
        return "7b"
    elif "3b" in model_id_lower or "1b" in model_id_lower:
        return "small"
    else:
        # Default to unknown
        return "unknown"


def get_quantization_type(model_id: str) -> str:
    """Determine quantization type from model ID.

    Args:
        model_id: HuggingFace model ID

    Returns:
        Quantization type (e.g., "awq", "gptq", "full")
    """
    model_id_lower = model_id.lower()

    if "awq" in model_id_lower:
        return "awq"
    elif "gptq" in model_id_lower:
        return "gptq"
    elif "gguf" in model_id_lower:
        return "gguf"
    else:
        return "full"


def get_best_model_for_vram(vram_gb: int) -> Optional[ModelConfig]:
    """Get the single best model recommendation for given VRAM.

    Prioritizes:
    1. Quantized models (AWQ/GPTQ) for efficiency
    2. Largest model that fits comfortably
    3. Popular/well-tested models (Qwen, DeepSeek)

    Args:
        vram_gb: Total VRAM available in GB

    Returns:
        ModelConfig object or None if no suitable model found
    """
    models = get_recommended_models(vram_gb, prefer_quantized=True)

    if not models:
        return None

    # Return the top recommendation (already sorted)
    return models[0]


def select_models_for_vram(vram_gb: int) -> List[ModelConfig]:
    """Select appropriate models for benchmarking based on VRAM.

    Returns a curated list of 1-3 models that are most relevant
    for the given VRAM capacity.

    Args:
        vram_gb: Total VRAM available in GB

    Returns:
        List of 1-3 ModelConfig objects to benchmark
    """
    all_suitable = get_recommended_models(vram_gb, prefer_quantized=True)

    if not all_suitable:
        return []

    by_category = _group_models_by_category(all_suitable)
    category_order = ["70b", "30b", "14b", "7b"]
    selected = _select_primary_quantized(by_category, category_order)

    if vram_gb >= 80:
        _append_full_precision(by_category, category_order, selected)

    return selected[:3]  # Maximum 3 models


def _group_models_by_category(models: List[ModelConfig]) -> dict[str, List[ModelConfig]]:
    by_category: dict[str, List[ModelConfig]] = {}
    for model in models:
        by_category.setdefault(model.category, []).append(model)
    return by_category


def _select_primary_quantized(
    by_category: dict[str, List[ModelConfig]],
    category_order: list[str],
) -> list[ModelConfig]:
    for category in category_order:
        candidates = by_category.get(category, [])
        quantized = [m for m in candidates if m.quantization in ["awq", "gptq"]]
        if quantized:
            return [quantized[0]]
    return []


def _append_full_precision(
    by_category: dict[str, List[ModelConfig]],
    category_order: list[str],
    selected: list[ModelConfig],
) -> None:
    if len(selected) >= 3:
        return
    for category in category_order:
        candidates = by_category.get(category, [])
        full_precision = [m for m in candidates if m.quantization == "full"]
        if full_precision and full_precision[0] not in selected:
            selected.append(full_precision[0])
            return


def estimate_vram_usage(model_category: str, quantization: str) -> int:
    """Estimate VRAM usage for a model.

    Args:
        model_category: Model category (e.g., "7b", "30b", "70b")
        quantization: Quantization type (e.g., "awq", "gptq", "full")

    Returns:
        Estimated VRAM usage in GB
    """
    # Base parameter counts (approximate)
    param_counts = {
        "7b": 7_000_000_000,
        "14b": 14_000_000_000,
        "30b": 33_000_000_000,
        "70b": 70_000_000_000,
    }

    # Bytes per parameter based on quantization
    bytes_per_param = {
        "awq": 0.5,  # 4-bit quantization
        "gptq": 0.5,  # 4-bit quantization
        "gguf": 0.5,  # 4-bit quantization (typical)
        "full": 2.0,  # FP16/BF16
    }

    params = param_counts.get(model_category, 7_000_000_000)
    multiplier = bytes_per_param.get(quantization, 2.0)

    # Calculate model size in GB
    model_size_gb = (params * multiplier) / (1024**3)

    # Add 20-30% overhead for KV cache, activations, etc.
    total_vram_gb = model_size_gb * 1.25

    return int(total_vram_gb)


def get_recommended_context_length(vram_gb: int, model_category: str) -> int:
    """Get recommended context length based on VRAM and model size.

    Args:
        vram_gb: Total VRAM available in GB
        model_category: Model category (e.g., "7b", "30b", "70b")

    Returns:
        Recommended max_model_len value
    """
    # Base context lengths
    base_context = {
        "7b": 32768,
        "14b": 32768,
        "30b": 32768,
        "70b": 32768,
    }

    base = base_context.get(model_category, 16384)

    # Adjust based on available VRAM headroom
    # Rough estimate: each 1GB of extra VRAM allows ~8K more context
    if model_category == "70b":
        if vram_gb >= 120:
            return 65536  # Large context possible
        elif vram_gb >= 96:
            return 32768  # Standard context
        else:
            return 16384  # Conservative
    elif model_category == "30b":
        if vram_gb >= 60:
            return 65536
        elif vram_gb >= 40:
            return 32768
        else:
            return 16384
    else:
        # Smaller models can generally handle large contexts
        return base
