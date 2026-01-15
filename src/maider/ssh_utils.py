"""SSH utilities for remote command execution."""

import subprocess
from typing import Optional


class SSHClient:
    """Simple SSH client for executing commands on remote hosts."""

    def __init__(self, host: str, user: str = "root"):
        """Initialize SSH client."""
        self.host = host
        self.user = user

    def run(self, command: str, timeout: int = 30) -> tuple[int, str, str]:
        """Execute a command via SSH.

        Returns:
            Tuple of (exit_code, stdout, stderr)
        """
        cmd = [
            "ssh",
            "-o",
            "StrictHostKeyChecking=no",
            "-o",
            "ConnectTimeout=5",
            f"{self.user}@{self.host}",
            command,
        ]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            return -1, "", "SSH command timeout"

    def run_check(self, command: str) -> bool:
        """Execute command and return True if successful."""
        exit_code, _, _ = self.run(command)
        return exit_code == 0

    def run_output(self, command: str) -> Optional[str]:
        """Execute command and return stdout if successful."""
        exit_code, stdout, _ = self.run(command)
        return stdout if exit_code == 0 else None
