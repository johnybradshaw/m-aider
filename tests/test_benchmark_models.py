"""Tests for benchmark model selection."""

from src.maider.benchmark_models import (
    get_recommended_models,
    get_model_category,
    get_quantization_type,
    get_best_model_for_vram,
    select_models_for_vram,
    estimate_vram_usage,
    get_recommended_context_length,
)


class TestModelCategorization:
    """Test model categorization functions."""

    def test_get_model_category_70b(self):
        """Test 70B model detection."""
        assert get_model_category("Qwen/Qwen2.5-72B-Instruct-AWQ") == "70b"
        assert get_model_category("meta-llama/Llama-3.1-70B-Instruct") == "70b"
        assert get_model_category("Llama-3-72B-Instruct") == "70b"

    def test_get_model_category_30b(self):
        """Test 30B model detection."""
        assert get_model_category("Qwen/Qwen2.5-Coder-32B-Instruct-AWQ") == "30b"
        assert get_model_category("deepseek-ai/deepseek-coder-33b-instruct") == "30b"
        assert get_model_category("CodeLlama-30B-Instruct") == "30b"

    def test_get_model_category_14b(self):
        """Test 14B model detection."""
        assert get_model_category("Qwen/Qwen2.5-Coder-14B-Instruct-AWQ") == "14b"
        assert get_model_category("some-model-15b") == "14b"

    def test_get_model_category_7b(self):
        """Test 7B model detection."""
        assert get_model_category("Qwen/Qwen2.5-Coder-7B-Instruct") == "7b"
        assert get_model_category("deepseek-coder-7b-instruct-v1.5") == "7b"
        assert get_model_category("CodeLlama-8B-Instruct") == "7b"

    def test_get_model_category_unknown(self):
        """Test unknown model detection."""
        assert get_model_category("some-random-model") == "unknown"
        assert get_model_category("gpt-4") == "unknown"

    def test_get_quantization_type_awq(self):
        """Test AWQ quantization detection."""
        assert get_quantization_type("Qwen/Qwen2.5-72B-Instruct-AWQ") == "awq"
        assert get_quantization_type("model-awq") == "awq"

    def test_get_quantization_type_gptq(self):
        """Test GPTQ quantization detection."""
        assert get_quantization_type("model-GPTQ") == "gptq"
        assert get_quantization_type("some-gptq-model") == "gptq"

    def test_get_quantization_type_gguf(self):
        """Test GGUF quantization detection."""
        assert get_quantization_type("model.gguf") == "gguf"
        assert get_quantization_type("some-GGUF-model") == "gguf"

    def test_get_quantization_type_full(self):
        """Test full precision detection."""
        assert get_quantization_type("Qwen/Qwen2.5-72B-Instruct") == "full"
        assert get_quantization_type("some-random-model") == "full"


class TestModelSelection:
    """Test model selection functions."""

    def test_get_recommended_models_20gb(self):
        """Test model recommendations for 20GB VRAM."""
        models = get_recommended_models(20, prefer_quantized=True)

        assert len(models) > 0
        assert all(m.min_vram_gb <= 20 for m in models)

        # Should prefer quantized models first
        assert models[0].quantization in ["awq", "gptq"]

    def test_get_recommended_models_96gb(self):
        """Test model recommendations for 96GB VRAM."""
        models = get_recommended_models(96, prefer_quantized=True)

        assert len(models) > 0
        assert all(m.min_vram_gb <= 96 for m in models)

        # Should include 70B models
        categories = [m.category for m in models]
        assert "70b" in categories

    def test_get_recommended_models_prefer_full(self):
        """Test model recommendations preferring full precision."""
        models_quantized = get_recommended_models(96, prefer_quantized=True)
        models_full = get_recommended_models(96, prefer_quantized=False)

        # Different ordering based on preference
        assert models_quantized[0].quantization in ["awq", "gptq"]
        # Full precision models should appear earlier in full preference
        full_models = [m for m in models_full if m.quantization == "full"]
        quantized_models = [m for m in models_quantized if m.quantization in ["awq", "gptq"]]
        assert len(full_models) > 0
        assert len(quantized_models) > 0

    def test_get_best_model_for_vram_20gb(self):
        """Test best model selection for 20GB."""
        best = get_best_model_for_vram(20)

        assert best is not None
        assert best.min_vram_gb <= 20
        assert best.quantization in ["awq", "gptq"]  # Should prefer quantized

    def test_get_best_model_for_vram_96gb(self):
        """Test best model selection for 96GB."""
        best = get_best_model_for_vram(96)

        assert best is not None
        assert best.min_vram_gb <= 96
        assert best.category == "70b"  # Largest that fits
        assert best.quantization in ["awq", "gptq"]  # Prefer quantized

    def test_get_best_model_for_vram_insufficient(self):
        """Test model selection with insufficient VRAM."""
        # Less than minimum required
        best = get_best_model_for_vram(10)

        # Should still return something (smallest model)
        # Or return None if truly insufficient
        assert best is None or best.min_vram_gb <= 10

    def test_select_models_for_vram(self):
        """Test curated model selection."""
        models = select_models_for_vram(96)

        assert len(models) > 0
        assert len(models) <= 3  # Maximum 3 models
        assert all(m.min_vram_gb <= 96 for m in models)

        # Should include at least one quantized 70B model
        categories = [m.category for m in models]
        assert "70b" in categories


class TestVRAMEstimation:
    """Test VRAM usage estimation."""

    def test_estimate_7b_awq(self):
        """Test 7B AWQ model estimation."""
        vram = estimate_vram_usage("7b", "awq")

        # 7B model with 4-bit quantization
        # ~7B * 0.5 bytes/param * 1.25 overhead = ~4.4GB
        assert 3 < vram < 6

    def test_estimate_70b_awq(self):
        """Test 70B AWQ model estimation."""
        vram = estimate_vram_usage("70b", "awq")

        # 70B model with 4-bit quantization
        # ~70B * 0.5 bytes/param * 1.25 overhead = ~44GB
        assert 35 < vram < 55

    def test_estimate_70b_full(self):
        """Test 70B full precision model estimation."""
        vram = estimate_vram_usage("70b", "full")

        # 70B model with FP16
        # ~70B * 2 bytes/param * 1.25 overhead = ~175GB
        assert 150 < vram < 200

    def test_estimate_30b_awq(self):
        """Test 30B AWQ model estimation."""
        vram = estimate_vram_usage("30b", "awq")

        # 30B model with 4-bit quantization
        # ~33B * 0.5 bytes/param * 1.25 overhead = ~21GB
        assert 18 < vram < 28


class TestContextLengthRecommendation:
    """Test context length recommendations."""

    def test_recommended_context_70b_96gb(self):
        """Test context length for 70B on 96GB."""
        context = get_recommended_context_length(96, "70b")

        # 96GB should support 32K context
        assert context == 32768

    def test_recommended_context_70b_120gb(self):
        """Test context length for 70B on 120GB."""
        context = get_recommended_context_length(120, "70b")

        # 120GB should support 64K context
        assert context == 65536

    def test_recommended_context_70b_80gb(self):
        """Test context length for 70B on 80GB."""
        context = get_recommended_context_length(80, "70b")

        # 80GB is tight, use conservative context
        assert context == 16384

    def test_recommended_context_30b_40gb(self):
        """Test context length for 30B on 40GB."""
        context = get_recommended_context_length(40, "30b")

        # 40GB should support 32K context
        assert context == 32768

    def test_recommended_context_30b_60gb(self):
        """Test context length for 30B on 60GB."""
        context = get_recommended_context_length(60, "30b")

        # 60GB has headroom for larger context
        assert context == 65536

    def test_recommended_context_14b(self):
        """Test context length for 14B models."""
        context = get_recommended_context_length(20, "14b")

        # Smaller models can handle large context
        assert context == 32768

    def test_recommended_context_7b(self):
        """Test context length for 7B models."""
        context = get_recommended_context_length(20, "7b")

        # Small models have plenty of room
        assert context == 32768


class TestModelConfigDefaults:
    """Test model config default values."""

    def test_qwen_72b_awq_config(self):
        """Test Qwen 72B AWQ model config (general purpose, for 70b+ category)."""
        models = get_recommended_models(96, prefer_quantized=True)

        qwen_72b = next((m for m in models if "72B" in m.id and "AWQ" in m.id), None)

        assert qwen_72b is not None
        assert qwen_72b.category == "70b"
        assert qwen_72b.quantization == "awq"
        assert qwen_72b.min_vram_gb >= 60  # Should require at least 60GB
        assert qwen_72b.recommended_context == 32768

    def test_qwen_32b_awq_config(self):
        """Test Qwen 32B AWQ model config."""
        models = get_recommended_models(40, prefer_quantized=True)

        qwen_32b = next((m for m in models if "32B" in m.id and "AWQ" in m.id), None)

        assert qwen_32b is not None
        assert qwen_32b.category == "30b"
        assert qwen_32b.quantization == "awq"
        assert qwen_32b.min_vram_gb >= 30  # Should require at least 30GB
        assert qwen_32b.recommended_context == 32768

    def test_qwen_14b_awq_config(self):
        """Test Qwen 14B AWQ model config."""
        models = get_recommended_models(20, prefer_quantized=True)

        qwen_14b = next((m for m in models if "14B" in m.id and "AWQ" in m.id), None)

        assert qwen_14b is not None
        assert qwen_14b.category == "14b"
        assert qwen_14b.quantization == "awq"
        assert qwen_14b.min_vram_gb <= 20  # Should fit in 20GB
        assert qwen_14b.recommended_context == 32768
