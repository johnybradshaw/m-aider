"""Tests for switch-model command."""

import json
import subprocess
from unittest.mock import Mock, patch

import pytest
from click.testing import CliRunner

from src.maider.commands.switch_model import cmd as switch_model_cmd
from src.maider.commands import switch_model as switch_model_module
from src.maider.model_validation import ValidationResult
from src.maider.session import SessionManager


def _make_valid_validation_result(model_id: str, max_len: int) -> ValidationResult:
    """Create a valid validation result for testing."""
    return ValidationResult(
        is_valid=True,
        model_id=model_id,
        requested_max_len=max_len,
        model_max_len=32768,
    )


@pytest.mark.unit
class TestSwitchModel:
    """Test switch-model command."""

    @pytest.fixture
    def runner(self):
        """Create CLI test runner."""
        return CliRunner()

    @pytest.fixture
    def mock_config(self, temp_dir, mock_env_file, mock_secrets_file):
        """Create mock config."""
        with patch("src.maider.commands.switch_model.Config") as mock:
            config = Mock()
            config.model_id = "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ"
            config.vllm_max_model_len = 32768
            config.vllm_tensor_parallel_size = 1
            config.vllm_gpu_memory_utilization = 0.90
            config.vllm_max_num_seqs = 1
            config.vllm_dtype = "auto"
            config.vllm_extra_args = ""
            config.vllm_image = "vllm/vllm-openai:latest"
            config.openwebui_image = "ghcr.io/open-webui/open-webui:main"
            config.vllm_port = 8000
            config.webui_port = 3000
            config.enable_openwebui = True
            config.enable_hf_cache = True
            config.enable_healthchecks = False
            config.enable_nccl_env = False
            config.hf_token = "test_token"
            mock.return_value = config
            yield mock

    @pytest.fixture
    def mock_validation(self):
        """Mock validation to always pass."""
        with patch("src.maider.commands.switch_model.validate_max_model_len") as mock:
            mock.return_value = ValidationResult(
                is_valid=True,
                model_id="test",
                requested_max_len=32768,
                model_max_len=32768,
            )
            yield mock

    @pytest.fixture
    def mock_session(self, temp_dir, mock_session_data):
        """Create mock session."""
        session_mgr = SessionManager(cache_dir=temp_dir)
        return session_mgr.create_session(
            name=mock_session_data["name"],
            linode_id=mock_session_data["linode_id"],
            ip=mock_session_data["ip"],
            vm_type=mock_session_data["type"],
            hourly_cost=mock_session_data["hourly_cost"],
            model_id=mock_session_data["model_id"],
            served_model_name=mock_session_data["served_model_name"],
        )

    def test_switch_model_no_current_session(self, runner, temp_dir, mock_config, mock_validation):
        """Test error when no current session is set."""
        with patch("src.maider.commands.switch_model.SessionManager") as mock_sm:
            mock_sm_instance = Mock()
            mock_sm_instance.get_current_session.return_value = None
            mock_sm.return_value = mock_sm_instance

            result = runner.invoke(
                switch_model_cmd,
                ["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"],
            )

            assert result.exit_code == 1
            assert "No current session set" in result.output

    def test_switch_model_session_not_found(self, runner, temp_dir, mock_config, mock_validation):
        """Test error when specified session doesn't exist."""
        with patch("src.maider.commands.switch_model.SessionManager") as mock_sm:
            mock_sm_instance = Mock()
            mock_sm_instance.get_session.return_value = None
            mock_sm.return_value = mock_sm_instance

            result = runner.invoke(
                switch_model_cmd,
                ["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ", "nonexistent"],
            )

            assert result.exit_code == 1
            assert "Session 'nonexistent' not found" in result.output

    @patch("src.maider.commands.switch_model.subprocess.run")
    def test_switch_model_success(
        self,
        mock_subprocess,
        runner,
        temp_dir,
        mock_config,
        mock_session,
        mock_validation,
        monkeypatch,
    ):
        """Test successful model switch."""
        monkeypatch.chdir(temp_dir)

        # Mock subprocess calls - note: session update now happens before API wait
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # scp upload docker-compose
            Mock(returncode=0, stdout="", stderr=""),  # scp env upload
            Mock(returncode=0, stdout="", stderr=""),  # docker restart
            Mock(returncode=0, stdout='{"data": [{"id": "coder"}]}', stderr=""),  # curl (waiting)
            Mock(returncode=0, stdout='{"data": [{"id": "coder"}]}', stderr=""),  # curl (verify)
        ]

        with patch("src.maider.commands.switch_model.SessionManager") as mock_sm:
            mock_sm_instance = Mock()
            mock_sm_instance.get_current_session.return_value = mock_session
            mock_sm_instance.get_session.return_value = mock_session
            mock_sm.return_value = mock_sm_instance

            result = runner.invoke(
                switch_model_cmd,
                ["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"],
                input="y\n",
            )

            assert result.exit_code == 0
            assert "Successfully switched" in result.output

            # Verify update_session_model was called
            mock_sm_instance.update_session_model.assert_called_once()

    @patch("src.maider.commands.switch_model.subprocess.run")
    def test_switch_model_with_overrides(
        self,
        mock_subprocess,
        runner,
        temp_dir,
        mock_config,
        mock_session,
        mock_validation,
        monkeypatch,
    ):
        """Test switch model with parameter overrides."""
        monkeypatch.chdir(temp_dir)

        # Mock subprocess calls - note: session update now happens before API wait
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # scp upload docker-compose
            Mock(returncode=0, stdout="", stderr=""),  # scp env upload
            Mock(returncode=0, stdout="", stderr=""),  # docker restart
            Mock(returncode=0, stdout='{"data": [{"id": "coder"}]}', stderr=""),  # curl (waiting)
            Mock(returncode=0, stdout='{"data": [{"id": "coder"}]}', stderr=""),  # curl (verify)
        ]

        with patch("src.maider.commands.switch_model.SessionManager") as mock_sm:
            mock_sm_instance = Mock()
            mock_sm_instance.get_current_session.return_value = mock_session
            mock_sm_instance.get_session.return_value = mock_session
            mock_sm.return_value = mock_sm_instance

            result = runner.invoke(
                switch_model_cmd,
                [
                    "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ",
                    "--max-model-len",
                    "16384",
                    "--tensor-parallel-size",
                    "2",
                ],
                input="y\n",
            )

            assert result.exit_code == 0
            assert "Max tokens: 16384" in result.output
            assert "Tensor parallel: 2" in result.output

    def test_switch_model_user_cancels(
        self, runner, temp_dir, mock_config, mock_session, mock_validation
    ):
        """Test user cancels model switch."""
        with patch("src.maider.commands.switch_model.SessionManager") as mock_sm:
            mock_sm_instance = Mock()
            mock_sm_instance.get_current_session.return_value = mock_session
            mock_sm.return_value = mock_sm_instance

            result = runner.invoke(
                switch_model_cmd,
                ["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"],
                input="n\n",
            )

            assert result.exit_code == 0
            assert "Cancelled" in result.output

    @patch("src.maider.commands.switch_model.subprocess.run")
    def test_switch_model_upload_fails(
        self, mock_subprocess, runner, temp_dir, mock_config, mock_session, mock_validation
    ):
        """Test error when docker-compose upload fails."""
        # Mock failed scp
        mock_subprocess.return_value = Mock(
            returncode=1,
            stdout="",
            stderr="Connection refused",
        )

        with patch("src.maider.commands.switch_model.SessionManager") as mock_sm:
            mock_sm_instance = Mock()
            mock_sm_instance.get_current_session.return_value = mock_session
            mock_sm.return_value = mock_sm_instance

            result = runner.invoke(
                switch_model_cmd,
                ["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"],
                input="y\n",
            )

            assert result.exit_code == 1
            assert "Failed to upload" in result.output

    @patch("src.maider.commands.switch_model.subprocess.run")
    def test_switch_model_restart_fails(
        self, mock_subprocess, runner, temp_dir, mock_config, mock_session, mock_validation
    ):
        """Test error when container restart fails."""
        # Mock successful upload, failed restart
        mock_subprocess.side_effect = [
            Mock(returncode=0, stdout="", stderr=""),  # scp success
            Mock(returncode=0, stdout="", stderr=""),  # scp env success
            Mock(returncode=1, stdout="", stderr="Docker daemon not running"),  # restart fail
        ]

        with patch("src.maider.commands.switch_model.SessionManager") as mock_sm:
            mock_sm_instance = Mock()
            mock_sm_instance.get_current_session.return_value = mock_session
            mock_sm.return_value = mock_sm_instance

            result = runner.invoke(
                switch_model_cmd,
                ["Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"],
                input="y\n",
            )

            assert result.exit_code == 1
            assert "Failed to restart" in result.output

    def test_generate_aider_metadata(self, runner, temp_dir, monkeypatch):
        """Test .aider.model.metadata.json generation."""
        monkeypatch.chdir(temp_dir)

        from src.maider.commands.switch_model import _generate_aider_metadata

        _generate_aider_metadata("coder-14b", 16384)

        metadata_file = temp_dir / ".aider.model.metadata.json"
        assert metadata_file.exists()

        metadata = json.loads(metadata_file.read_text())

        assert "openai/coder-14b" in metadata
        assert metadata["openai/coder-14b"]["max_tokens"] == 16384
        assert metadata["openai/coder-14b"]["max_input_tokens"] == 16384
        assert metadata["openai/coder-14b"]["max_output_tokens"] == 8192  # Half of max_tokens
        assert metadata["openai/coder-14b"]["litellm_provider"] == "openai"
        assert metadata["openai/coder-14b"]["mode"] == "chat"

    @patch("src.maider.commands.switch_model.subprocess.run")
    def test_restart_containers_timeout_fallback(self, mock_subprocess):
        """Test fallback to systemctl when docker compose restart hangs."""
        mock_subprocess.side_effect = [
            subprocess.TimeoutExpired(cmd="ssh", timeout=120),
            Mock(returncode=0, stdout="", stderr=""),
        ]

        switch_model_module._restart_containers("192.0.2.1")
