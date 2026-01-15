"""Tests for tunnel command."""

from unittest.mock import patch, MagicMock

import pytest
from click.testing import CliRunner

from src.maider.commands.tunnel import cmd


@pytest.mark.unit
class TestTunnelCommand:
    """Test tunnel command."""

    @patch("src.maider.commands.tunnel.SessionManager")
    @patch("src.maider.commands.tunnel.LinodeManager")
    @patch("src.maider.commands.tunnel.Config")
    @patch("src.maider.commands.tunnel.subprocess.run")
    def test_tunnel_queries_vm_status(
        self, mock_subprocess, mock_config, mock_linode_mgr_class, mock_session_mgr_class
    ):
        """Test that tunnel command queries VM status dynamically."""
        # Setup mock session
        mock_session = MagicMock()
        mock_session.name = "test-session"
        mock_session.ip = "192.0.2.1"
        mock_session.linode_id = 12345678

        mock_session_mgr = MagicMock()
        mock_session_mgr.get_current_session.return_value = mock_session
        mock_session_mgr_class.return_value = mock_session_mgr

        # Setup mock Linode manager
        mock_linode_mgr = MagicMock()
        mock_linode_mgr.get_instance_status.return_value = "running"
        mock_linode_mgr_class.return_value = mock_linode_mgr

        # Setup mock config
        mock_config.return_value = MagicMock()

        # Mock subprocess (tunnel setup)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner = CliRunner()
        result = runner.invoke(cmd)

        # Verify status was queried
        mock_linode_mgr.get_instance_status.assert_called_once_with(12345678)

        # Verify success
        assert result.exit_code == 0
        assert "test-session" in result.output
        assert "192.0.2.1" in result.output
        assert "running" in result.output

    @patch("src.maider.commands.tunnel.SessionManager")
    @patch("src.maider.commands.tunnel.LinodeManager")
    @patch("src.maider.commands.tunnel.Config")
    @patch("src.maider.commands.tunnel.subprocess.run")
    def test_tunnel_handles_status_query_failure(
        self, mock_subprocess, mock_config, mock_linode_mgr_class, mock_session_mgr_class
    ):
        """Test that tunnel command handles status query failure gracefully."""
        # Setup mock session
        mock_session = MagicMock()
        mock_session.name = "test-session"
        mock_session.ip = "192.0.2.1"
        mock_session.linode_id = 12345678

        mock_session_mgr = MagicMock()
        mock_session_mgr.get_current_session.return_value = mock_session
        mock_session_mgr_class.return_value = mock_session_mgr

        # Setup mock Linode manager to raise exception
        mock_linode_mgr = MagicMock()
        mock_linode_mgr.get_instance_status.side_effect = Exception("API error")
        mock_linode_mgr_class.return_value = mock_linode_mgr

        # Setup mock config
        mock_config.return_value = MagicMock()

        # Mock subprocess (tunnel setup)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner = CliRunner()
        result = runner.invoke(cmd)

        # Verify status query was attempted
        mock_linode_mgr.get_instance_status.assert_called_once_with(12345678)

        # Verify command still succeeds with "unknown" status
        assert result.exit_code == 0
        assert "test-session" in result.output
        assert "unknown" in result.output

    @patch("src.maider.commands.tunnel.SessionManager")
    @patch("src.maider.commands.tunnel.LinodeManager")
    @patch("src.maider.commands.tunnel.Config")
    @patch("src.maider.commands.tunnel.subprocess.run")
    def test_tunnel_warns_when_vm_not_running(
        self, mock_subprocess, mock_config, mock_linode_mgr_class, mock_session_mgr_class
    ):
        """Test that tunnel command warns when VM is not running."""
        # Setup mock session
        mock_session = MagicMock()
        mock_session.name = "test-session"
        mock_session.ip = "192.0.2.1"
        mock_session.linode_id = 12345678

        mock_session_mgr = MagicMock()
        mock_session_mgr.get_current_session.return_value = mock_session
        mock_session_mgr_class.return_value = mock_session_mgr

        # Setup mock Linode manager with non-running status
        mock_linode_mgr = MagicMock()
        mock_linode_mgr.get_instance_status.return_value = "offline"
        mock_linode_mgr_class.return_value = mock_linode_mgr

        # Setup mock config
        mock_config.return_value = MagicMock()

        # Mock subprocess (tunnel setup)
        mock_subprocess.return_value = MagicMock(returncode=0)

        runner = CliRunner()
        result = runner.invoke(cmd)

        # Verify warning is displayed
        assert result.exit_code == 0
        assert "Warning" in result.output
        assert "offline" in result.output
        assert "may not work" in result.output

    def test_tunnel_no_current_session(self):
        """Test tunnel command when no current session is set."""
        with patch("src.maider.commands.tunnel.SessionManager") as mock_session_mgr_class:
            mock_session_mgr = MagicMock()
            mock_session_mgr.get_current_session.return_value = None
            mock_session_mgr_class.return_value = mock_session_mgr

            runner = CliRunner()
            result = runner.invoke(cmd)

            assert result.exit_code == 1
            assert "No current session set" in result.output
