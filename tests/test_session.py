"""Tests for session module."""

import json
import time
from pathlib import Path

import pytest

from src.maider.session import Session, SessionManager


@pytest.mark.unit
class TestSession:
    """Test Session dataclass."""

    def test_runtime_hours_calculation(self, mock_session_data):
        """Test runtime hours calculation."""
        # Remove linode_id from kwargs (backward compatibility field)
        session_data = {k: v for k, v in mock_session_data.items() if k != "linode_id"}
        session = Session(**session_data)

        # Mock current time to be 2 hours after start
        original_time = time.time
        time.time = lambda: mock_session_data["start_time"] + 7200  # 2 hours

        try:
            assert session.runtime_hours == pytest.approx(2.0, rel=0.01)
        finally:
            time.time = original_time

    def test_total_cost_calculation(self, mock_session_data):
        """Test total cost calculation."""
        # Remove linode_id from kwargs (backward compatibility field)
        session_data = {k: v for k, v in mock_session_data.items() if k != "linode_id"}
        session = Session(**session_data)

        # Mock current time to be 3 hours after start
        original_time = time.time
        time.time = lambda: mock_session_data["start_time"] + 10800  # 3 hours

        try:
            # 3 hours * $1.50/hour = $4.50
            assert session.total_cost == pytest.approx(4.50, rel=0.01)
        finally:
            time.time = original_time


@pytest.mark.unit
class TestSessionManager:
    """Test SessionManager class."""

    def test_create_session(self, temp_dir, mock_session_data):
        """Test creating a new session."""
        session_mgr = SessionManager(cache_dir=temp_dir)

        session = session_mgr.create_session(
            name=mock_session_data["name"],
            linode_id=mock_session_data["linode_id"],
            ip=mock_session_data["ip"],
            vm_type=mock_session_data["type"],
            hourly_cost=mock_session_data["hourly_cost"],
            model_id=mock_session_data["model_id"],
            served_model_name=mock_session_data["served_model_name"],
        )

        # Verify session object
        assert session.name == "test-session"
        assert session.linode_id == 12345678
        assert session.ip == "192.0.2.1"
        assert session.hourly_cost == 1.50

        # Verify files created
        session_dir = temp_dir / "test-session"
        assert session_dir.exists()
        assert (session_dir / "state.json").exists()
        assert (session_dir / "aider-env").exists()

        # Verify state file content
        state_data = json.loads((session_dir / "state.json").read_text())
        assert state_data["name"] == "test-session"
        assert state_data["provider_instance_id"] == "12345678"
        assert state_data["provider"] == "linode"

    def test_get_session(self, temp_dir, mock_session_data):
        """Test retrieving an existing session."""
        session_mgr = SessionManager(cache_dir=temp_dir)

        # Create session
        session_mgr.create_session(
            name=mock_session_data["name"],
            linode_id=mock_session_data["linode_id"],
            ip=mock_session_data["ip"],
            vm_type=mock_session_data["type"],
            hourly_cost=mock_session_data["hourly_cost"],
            model_id=mock_session_data["model_id"],
            served_model_name=mock_session_data["served_model_name"],
        )

        # Retrieve session
        session = session_mgr.get_session("test-session")

        assert session is not None
        assert session.name == "test-session"
        assert session.ip == "192.0.2.1"

    def test_get_nonexistent_session(self, temp_dir):
        """Test retrieving a session that doesn't exist."""
        session_mgr = SessionManager(cache_dir=temp_dir)

        session = session_mgr.get_session("nonexistent")

        assert session is None

    def test_list_sessions(self, temp_dir, mock_session_data):
        """Test listing all sessions."""
        session_mgr = SessionManager(cache_dir=temp_dir)

        # Create multiple sessions
        for i in range(3):
            data = mock_session_data.copy()
            data["name"] = f"session-{i}"
            data["linode_id"] = 12345678 + i
            session_mgr.create_session(
                name=data["name"],
                linode_id=data["linode_id"],
                ip=data["ip"],
                vm_type=data["type"],
                hourly_cost=data["hourly_cost"],
                model_id=data["model_id"],
                served_model_name=data["served_model_name"],
            )

        # List sessions
        sessions = session_mgr.list_sessions()

        assert len(sessions) == 3
        assert {s.name for s in sessions} == {"session-0", "session-1", "session-2"}

    def test_delete_session(self, temp_dir, mock_session_data):
        """Test deleting a session."""
        session_mgr = SessionManager(cache_dir=temp_dir)

        # Create session
        session_mgr.create_session(
            name=mock_session_data["name"],
            linode_id=mock_session_data["linode_id"],
            ip=mock_session_data["ip"],
            vm_type=mock_session_data["type"],
            hourly_cost=mock_session_data["hourly_cost"],
            model_id=mock_session_data["model_id"],
            served_model_name=mock_session_data["served_model_name"],
        )

        session_dir = temp_dir / "test-session"
        assert session_dir.exists()

        # Delete session
        session_mgr.delete_session("test-session")

        assert not session_dir.exists()
        assert session_mgr.get_session("test-session") is None

    def test_update_session_model(self, temp_dir, mock_session_data):
        """Test updating model information for a session."""
        session_mgr = SessionManager(cache_dir=temp_dir)

        # Create session
        session_mgr.create_session(
            name=mock_session_data["name"],
            linode_id=mock_session_data["linode_id"],
            ip=mock_session_data["ip"],
            vm_type=mock_session_data["type"],
            hourly_cost=mock_session_data["hourly_cost"],
            model_id=mock_session_data["model_id"],
            served_model_name=mock_session_data["served_model_name"],
        )

        # Update model
        new_model_id = "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ"
        new_served_name = "coder-14b"
        session_mgr.update_session_model("test-session", new_model_id, new_served_name)

        # Verify update
        session = session_mgr.get_session("test-session")
        assert session.model_id == new_model_id
        assert session.served_model_name == new_served_name

        # Verify aider-env updated
        aider_env = (temp_dir / "test-session" / "aider-env").read_text()
        assert f'export AIDER_MODEL="openai/{new_served_name}"' in aider_env

    def test_set_current_session(self, temp_dir, mock_session_data, monkeypatch):
        """Test setting current session via symlink."""
        monkeypatch.chdir(temp_dir)
        session_mgr = SessionManager(cache_dir=temp_dir / ".cache" / "linode-vms")

        # Create session
        session = session_mgr.create_session(
            name=mock_session_data["name"],
            linode_id=mock_session_data["linode_id"],
            ip=mock_session_data["ip"],
            vm_type=mock_session_data["type"],
            hourly_cost=mock_session_data["hourly_cost"],
            model_id=mock_session_data["model_id"],
            served_model_name=mock_session_data["served_model_name"],
        )

        # Set as current
        session_mgr.set_current_session(session)

        # Verify symlink created
        aider_env_link = temp_dir / ".aider-env"
        assert aider_env_link.is_symlink()
        assert aider_env_link.resolve().parent.name == "test-session"

    def test_get_current_session(self, temp_dir, mock_session_data, monkeypatch):
        """Test retrieving current session."""
        monkeypatch.chdir(temp_dir)
        session_mgr = SessionManager(cache_dir=temp_dir / ".cache" / "linode-vms")

        # Create and set session
        session = session_mgr.create_session(
            name=mock_session_data["name"],
            linode_id=mock_session_data["linode_id"],
            ip=mock_session_data["ip"],
            vm_type=mock_session_data["type"],
            hourly_cost=mock_session_data["hourly_cost"],
            model_id=mock_session_data["model_id"],
            served_model_name=mock_session_data["served_model_name"],
        )
        session_mgr.set_current_session(session)

        # Get current
        current = session_mgr.get_current_session()

        assert current is not None
        assert current.name == "test-session"

    def test_get_current_session_no_symlink(self, temp_dir, monkeypatch):
        """Test getting current session when no symlink exists."""
        monkeypatch.chdir(temp_dir)
        session_mgr = SessionManager(cache_dir=temp_dir / ".cache" / "linode-vms")

        current = session_mgr.get_current_session()

        assert current is None

    def test_aider_env_content(self, temp_dir, mock_session_data):
        """Test aider-env file contains correct environment variables."""
        session_mgr = SessionManager(cache_dir=temp_dir)

        session_mgr.create_session(
            name=mock_session_data["name"],
            linode_id=mock_session_data["linode_id"],
            ip=mock_session_data["ip"],
            vm_type=mock_session_data["type"],
            hourly_cost=mock_session_data["hourly_cost"],
            model_id=mock_session_data["model_id"],
            served_model_name=mock_session_data["served_model_name"],
        )

        aider_env = (temp_dir / "test-session" / "aider-env").read_text()

        # Check required exports
        assert 'export IP="192.0.2.1"' in aider_env
        assert 'export LINODE_ID="12345678"' in aider_env
        assert 'export HOURLY_COST="$1.5"' in aider_env
        assert 'export OPENAI_API_BASE="http://localhost:8000/v1"' in aider_env
        assert 'export AIDER_MODEL="openai/coder"' in aider_env
        assert 'export SESSION_NAME="test-session"' in aider_env
