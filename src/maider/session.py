"""Session management for VM instances."""

import json
import time
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class Session:
    """Represents a VM session."""

    name: str
    provider_instance_id: str
    ip: str
    type: str
    hourly_cost: float
    start_time: float
    model_id: str
    served_model_name: str
    provider: str = "linode"  # Default to linode for backward compatibility

    @property
    def linode_id(self) -> int:
        """Backward compatibility property for linode_id.

        Returns the provider_instance_id as an integer for Linode provider.
        """
        if self.provider == "linode":
            try:
                return int(self.provider_instance_id)
            except (ValueError, TypeError):
                return 0
        return 0

    @property
    def runtime_hours(self) -> float:
        """Calculate runtime in hours."""
        return (time.time() - self.start_time) / 3600

    @property
    def total_cost(self) -> float:
        """Calculate total cost so far."""
        return self.runtime_hours * self.hourly_cost


class SessionManager:
    """Manages VM sessions."""

    STATE_FILENAME = "state.json"

    def __init__(self, cache_dir: Optional[Path] = None):
        """Initialize session manager."""
        self.cache_dir = cache_dir or (Path.home() / ".cache" / "linode-vms")
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def create_session(
        self,
        name: str,
        provider_instance_id: Optional[str] = None,
        ip: str = "",
        vm_type: str = "",
        hourly_cost: float = 0.0,
        model_id: str = "",
        served_model_name: str = "",
        provider: str = "linode",
        linode_id: Optional[int] = None,  # Backward compatibility
        **kwargs,
    ) -> Session:
        """Create a new session.

        Args:
            name: Session name
            provider_instance_id: Provider-specific instance ID
            ip: VM IP address
            vm_type: VM type
            hourly_cost: Hourly cost in USD
            model_id: HuggingFace model ID
            served_model_name: Model name for API
            provider: Cloud provider (default: linode)
            linode_id: Deprecated - use provider_instance_id (backward compatibility)
            **kwargs: Additional arguments (ignored)

        Note:
            If linode_id is provided and provider_instance_id is not,
            linode_id will be converted to provider_instance_id.
        """
        # Backward compatibility: convert linode_id to provider_instance_id
        if provider_instance_id is None and linode_id is not None:
            provider_instance_id = str(linode_id)
        elif provider_instance_id is None:
            raise ValueError("Either provider_instance_id or linode_id must be provided")

        session = Session(
            name=name,
            provider_instance_id=str(provider_instance_id),
            ip=ip,
            type=vm_type,
            hourly_cost=hourly_cost,
            start_time=time.time(),
            model_id=model_id,
            served_model_name=served_model_name,
            provider=provider,
        )

        # Save session
        session_dir = self.cache_dir / name
        session_dir.mkdir(parents=True, exist_ok=True)

        state_file = session_dir / self.STATE_FILENAME
        state_file.write_text(json.dumps(asdict(session), indent=2))

        # Create aider-env file
        self._write_aider_env(session, session_dir)

        return session

    def get_session(self, name: str) -> Optional[Session]:
        """Load a session by name.

        Handles migration from old sessions with linode_id to new format
        with provider_instance_id.
        """
        state_file = self.cache_dir / name / self.STATE_FILENAME
        if not state_file.exists():
            return None

        try:
            data = json.loads(state_file.read_text())

            # Migration: Convert old linode_id to provider_instance_id
            if "linode_id" in data and "provider_instance_id" not in data:
                data["provider_instance_id"] = str(data["linode_id"])
                del data["linode_id"]

            # Add provider field if missing (default to linode)
            if "provider" not in data:
                data["provider"] = "linode"

            return Session(**data)
        except (json.JSONDecodeError, TypeError):
            return None

    def list_sessions(self) -> list[Session]:
        """List all sessions."""
        sessions = []
        for session_dir in self.cache_dir.iterdir():
            if session_dir.is_dir():
                session = self.get_session(session_dir.name)
                if session:
                    sessions.append(session)
        return sessions

    def delete_session(self, name: str):
        """Delete a session."""
        session_dir = self.cache_dir / name
        if session_dir.exists():
            import shutil

            shutil.rmtree(session_dir)

    def update_session_model(self, name: str, model_id: str, served_model_name: str):
        """Update the model information for a session."""
        session = self.get_session(name)
        if not session:
            return

        # Update session object
        session.model_id = model_id
        session.served_model_name = served_model_name

        # Save updated state
        session_dir = self.cache_dir / name
        state_file = session_dir / self.STATE_FILENAME
        state_file.write_text(json.dumps(asdict(session), indent=2))

        # Regenerate aider-env file
        self._write_aider_env(session, session_dir)

    def get_current_session(self) -> Optional[Session]:
        """Get the current active session from .aider-env symlink."""
        cwd = Path.cwd()
        aider_env = cwd / ".aider-env"

        if not aider_env.is_symlink():
            return None

        # Resolve symlink to get session directory
        target = aider_env.resolve()
        session_dir = target.parent
        session_name = session_dir.name

        return self.get_session(session_name)

    def set_current_session(self, session: Session):
        """Set the current session by updating .aider-env symlink."""
        cwd = Path.cwd()
        aider_env = cwd / ".aider-env"
        session_env = self.cache_dir / session.name / "aider-env"

        # Remove existing symlink
        if aider_env.exists() or aider_env.is_symlink():
            aider_env.unlink()

        # Create new symlink
        aider_env.symlink_to(session_env)

    def _write_aider_env(self, session: Session, session_dir: Path):
        """Write aider environment file."""
        import os

        vllm_port = os.getenv("VLLM_PORT", "8000")
        env_content = f"""# Auto-generated by linode-coder
export IP="{session.ip}"
export PROVIDER="{session.provider}"
export PROVIDER_INSTANCE_ID="{session.provider_instance_id}"
export LINODE_ID="{session.linode_id}"  # Backward compatibility
export START_TIME="{session.start_time}"
export HOURLY_COST="${session.hourly_cost}"

# API configuration
export OPENAI_API_BASE="http://localhost:{vllm_port}/v1"
export OPENAI_API_KEY="sk-dummy"
export AIDER_MODEL="openai/{session.served_model_name}"

# Session info
export SESSION_NAME="{session.name}"
"""

        env_file = session_dir / "aider-env"
        env_file.write_text(env_content)

    def generate_session_name(self, model_id: str) -> str:
        """Generate a unique session name."""
        # Extract model name from ID (e.g., "Qwen/Qwen2.5-Coder-32B" -> "qwen32b")
        model_name = model_id.split("/")[-1].lower()
        model_name = "".join(c for c in model_name if c.isalnum())[:10]

        # Add timestamp
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")

        return f"{model_name}-{timestamp}"
