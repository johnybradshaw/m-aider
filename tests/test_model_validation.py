"""Tests for model_validation module."""

from unittest.mock import Mock, patch

import pytest
import requests

from src.maider.model_validation import (
    ModelConfigInfo,
    ValidationResult,
    fetch_model_config,
    get_model_context_limit,
    validate_max_model_len,
    _calculate_suggested_max_len,
    KNOWN_CONTEXT_LENGTHS,
)


@pytest.mark.unit
class TestModelConfigInfo:
    """Test ModelConfigInfo dataclass."""

    def test_effective_max_length_with_max_position_embeddings(self):
        """Test effective_max_length returns max_position_embeddings."""
        config = ModelConfigInfo(
            model_id="test/model",
            max_position_embeddings=4096,
        )
        assert config.effective_max_length == 4096

    def test_effective_max_length_with_model_max_length(self):
        """Test effective_max_length returns model_max_length when set."""
        config = ModelConfigInfo(
            model_id="test/model",
            model_max_length=2048,
        )
        assert config.effective_max_length == 2048

    def test_effective_max_length_uses_smaller_of_both(self):
        """Test effective_max_length uses smaller value when both are set."""
        config = ModelConfigInfo(
            model_id="test/model",
            max_position_embeddings=4096,
            model_max_length=2048,
        )
        assert config.effective_max_length == 2048

    def test_effective_max_length_with_rope_scaling(self):
        """Test effective_max_length applies RoPE scaling factor."""
        config = ModelConfigInfo(
            model_id="test/model",
            max_position_embeddings=4096,
            rope_scaling={"type": "linear", "factor": 4.0},
        )
        assert config.effective_max_length == 16384

    def test_effective_max_length_none_when_both_missing(self):
        """Test effective_max_length returns None when no limits are set."""
        config = ModelConfigInfo(model_id="test/model")
        assert config.effective_max_length is None


@pytest.mark.unit
class TestValidationResult:
    """Test ValidationResult dataclass."""

    def test_message_for_valid_result(self):
        """Test message for valid result."""
        result = ValidationResult(
            is_valid=True,
            model_id="test/model",
            requested_max_len=4096,
        )
        assert "is valid" in result.message

    def test_message_for_invalid_result(self):
        """Test message for invalid result."""
        result = ValidationResult(
            is_valid=False,
            model_id="test/model",
            requested_max_len=32768,
            model_max_len=2048,
            suggested_max_len=2048,
        )
        assert "exceeds model limit" in result.message
        assert "2048" in result.message

    def test_message_with_warning(self):
        """Test message when warning is set."""
        result = ValidationResult(
            is_valid=True,
            model_id="test/model",
            requested_max_len=4096,
            warning="Could not verify",
        )
        assert result.message == "Could not verify"

    def test_message_with_error(self):
        """Test message when error is set."""
        result = ValidationResult(
            is_valid=True,
            model_id="test/model",
            requested_max_len=4096,
            error="Network error",
        )
        assert "Error: Network error" in result.message


@pytest.mark.unit
class TestFetchModelConfig:
    """Test fetch_model_config function."""

    def test_returns_known_override(self):
        """Test that known models return override values without API call."""
        # Pick a model from KNOWN_CONTEXT_LENGTHS
        model_id = "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"
        expected_len = KNOWN_CONTEXT_LENGTHS.get(model_id)

        config = fetch_model_config(model_id)

        assert config.model_id == model_id
        assert config.max_position_embeddings == expected_len
        assert config.error is None

    @patch("src.maider.model_validation.requests.get")
    def test_fetches_from_huggingface(self, mock_get):
        """Test fetching config from HuggingFace API."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "max_position_embeddings": 2048,
            "model_max_length": 2048,
        }
        mock_get.return_value = mock_response

        config = fetch_model_config("unknown/model")

        assert config.max_position_embeddings == 2048
        assert config.model_max_length == 2048
        assert config.error is None

    @patch("src.maider.model_validation.requests.get")
    def test_handles_404(self, mock_get):
        """Test handling 404 response."""
        mock_response = Mock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        config = fetch_model_config("nonexistent/model")

        assert config.error is not None
        assert "not found" in config.error.lower()

    @patch("src.maider.model_validation.requests.get")
    def test_handles_401(self, mock_get):
        """Test handling 401 response."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_get.return_value = mock_response

        config = fetch_model_config("private/model")

        assert config.error is not None
        assert "Authentication" in config.error

    @patch("src.maider.model_validation.requests.get")
    def test_handles_timeout(self, mock_get):
        """Test handling request timeout."""
        mock_get.side_effect = requests.exceptions.Timeout()

        config = fetch_model_config("slow/model")

        assert config.error is not None
        assert "Timeout" in config.error

    @patch("src.maider.model_validation.requests.get")
    def test_handles_network_error(self, mock_get):
        """Test handling network errors."""
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        config = fetch_model_config("test/model")

        assert config.error is not None
        assert "Network error" in config.error

    @patch("src.maider.model_validation.requests.get")
    def test_passes_auth_header(self, mock_get):
        """Test that HuggingFace token is passed in header."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"max_position_embeddings": 4096}
        mock_get.return_value = mock_response

        fetch_model_config("test/model", hf_token="test_token")

        mock_get.assert_called_once()
        call_kwargs = mock_get.call_args[1]
        assert "Authorization" in call_kwargs["headers"]
        assert "Bearer test_token" in call_kwargs["headers"]["Authorization"]


@pytest.mark.unit
class TestValidateMaxModelLen:
    """Test validate_max_model_len function."""

    def test_valid_value_within_limit(self):
        """Test validation passes when value is within limit."""
        # Use a known model
        result = validate_max_model_len(
            "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ",
            16384,
        )

        assert result.is_valid
        assert result.requested_max_len == 16384

    def test_valid_value_at_limit(self):
        """Test validation passes when value equals limit."""
        result = validate_max_model_len(
            "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ",
            32768,
        )

        assert result.is_valid

    @patch("src.maider.model_validation.fetch_model_config")
    def test_invalid_value_exceeds_limit(self, mock_fetch):
        """Test validation fails when value exceeds limit."""
        mock_fetch.return_value = ModelConfigInfo(
            model_id="test/model",
            max_position_embeddings=2048,
        )

        result = validate_max_model_len("test/model", 32768)

        assert not result.is_valid
        assert result.model_max_len == 2048
        assert result.suggested_max_len == 2048
        assert result.allow_override

    @patch("src.maider.model_validation.fetch_model_config")
    def test_warning_when_config_fetch_fails(self, mock_fetch):
        """Test returns warning when config cannot be fetched."""
        mock_fetch.return_value = ModelConfigInfo(
            model_id="test/model",
            error="Network error",
        )

        result = validate_max_model_len("test/model", 32768)

        assert result.is_valid  # Allows proceeding
        assert result.warning is not None
        assert "Could not validate" in result.warning

    @patch("src.maider.model_validation.fetch_model_config")
    def test_warning_when_no_limit_in_config(self, mock_fetch):
        """Test returns warning when config has no limit."""
        mock_fetch.return_value = ModelConfigInfo(
            model_id="test/model",
        )

        result = validate_max_model_len("test/model", 32768)

        assert result.is_valid
        assert result.warning is not None
        assert "does not specify" in result.warning


@pytest.mark.unit
class TestCalculateSuggestedMaxLen:
    """Test _calculate_suggested_max_len function."""

    def test_returns_common_power_of_two(self):
        """Test returns common context lengths."""
        assert _calculate_suggested_max_len(32768) == 32768
        assert _calculate_suggested_max_len(16384) == 16384
        assert _calculate_suggested_max_len(8192) == 8192

    def test_returns_largest_fitting_value(self):
        """Test returns largest power of 2 that fits."""
        assert _calculate_suggested_max_len(30000) == 16384
        assert _calculate_suggested_max_len(10000) == 8192
        assert _calculate_suggested_max_len(3000) == 2048

    def test_returns_model_max_when_small(self):
        """Test returns model max when smaller than 1024."""
        assert _calculate_suggested_max_len(512) == 512


@pytest.mark.unit
class TestGetModelContextLimit:
    """Test get_model_context_limit function."""

    def test_returns_limit_for_known_model(self):
        """Test returns limit for known model."""
        limit = get_model_context_limit("Qwen/Qwen2.5-Coder-14B-Instruct-AWQ")
        assert limit == 32768

    @patch("src.maider.model_validation.fetch_model_config")
    def test_returns_none_when_unknown(self, mock_fetch):
        """Test returns None when limit is unknown."""
        mock_fetch.return_value = ModelConfigInfo(
            model_id="unknown/model",
            error="Not found",
        )

        limit = get_model_context_limit("unknown/model")
        assert limit is None
