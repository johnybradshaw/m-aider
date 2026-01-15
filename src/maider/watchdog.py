"""Watchdog for auto-destroying idle VMs."""

import time
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

from .session import SessionManager, Session
from .linode_client import LinodeManager
from .config import Config

CACHE_DIR = Path.home() / ".cache" / "linode-vms"


class Watchdog:
    """Monitors VM activity and auto-destroys if idle."""

    def __init__(self, session: Session, timeout_minutes: int = 30, warning_minutes: int = 5):
        """Initialize watchdog.

        Args:
            session: VM session to monitor
            timeout_minutes: Minutes of inactivity before destruction
            warning_minutes: Minutes before destruction to send warning
        """
        self.session = session
        self.timeout_minutes = timeout_minutes
        self.warning_minutes = warning_minutes
        self.last_activity = time.time()
        self.warned = False

    def check_activity(self) -> bool:
        """Check if VM has recent activity.

        Returns:
            True if activity detected, False otherwise
        """
        try:
            # Check vLLM container logs for recent API requests
            cmd = [
                "ssh",
                "-o",
                "ConnectTimeout=5",
                "-o",
                "StrictHostKeyChecking=no",
                f"root@{self.session.ip}",
                "docker logs --since 2m $(docker ps -q | head -n1) 2>&1 | grep -i 'POST\\|GET' | wc -l",
            ]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.returncode == 0:
                request_count = int(result.stdout.strip() or "0")
                if request_count > 0:
                    return True

        except (subprocess.TimeoutExpired, ValueError):
            pass

        return False

    def send_notification(self, title: str, message: str):
        """Send desktop notification."""
        try:
            # macOS
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "{message}" with title "{title}"',
                ],
                capture_output=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            try:
                # Linux
                subprocess.run(
                    ["notify-send", "-u", "critical", title, message],
                    capture_output=True,
                    timeout=5,
                )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    def get_idle_minutes(self) -> float:
        """Get current idle time in minutes."""
        return (time.time() - self.last_activity) / 60

    def run(self):
        """Run watchdog loop."""
        print(f"Watchdog started for session: {self.session.name}")
        print(f"Timeout: {self.timeout_minutes} minutes")
        print(f"Warning: {self.warning_minutes} minutes before destruction")

        while True:
            # Check for activity
            if self.check_activity():
                self.last_activity = time.time()
                self.warned = False
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Activity detected")

            idle_minutes = self.get_idle_minutes()

            # Send warning if approaching timeout
            if not self.warned and idle_minutes >= (self.timeout_minutes - self.warning_minutes):
                warning_msg = f"VM '{self.session.name}' will be destroyed in {self.warning_minutes} minutes due to inactivity"
                print(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - {warning_msg}")
                self.send_notification("Linode Watchdog", warning_msg)
                self.warned = True

            # Destroy if timeout reached
            if idle_minutes >= self.timeout_minutes:
                print(
                    f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S')} - Timeout reached, destroying VM"
                )
                self.send_notification(
                    "Linode Watchdog",
                    f"Destroying VM '{self.session.name}' due to {self.timeout_minutes}min inactivity",
                )

                # Destroy VM
                try:
                    config = Config()
                    manager = LinodeManager(config)
                    manager.delete_instance(self.session.linode_id)

                    # Clean up session
                    session_mgr = SessionManager()
                    session_mgr.delete_session(self.session.name)

                    print(f"VM destroyed. Total cost: ${self.session.total_cost:.2f}")

                except Exception as e:
                    print(f"Error destroying VM: {e}")

                break

            # Sleep for 1 minute
            time.sleep(60)


def start_watchdog_background(
    session: Session, timeout_minutes: int = 30, warning_minutes: int = 5
):
    """Start watchdog in background process.

    Args:
        session: VM session to monitor
        timeout_minutes: Minutes of inactivity before destruction
        warning_minutes: Minutes before destruction to send warning
    """
    import multiprocessing

    watchdog = Watchdog(session, timeout_minutes, warning_minutes)

    # Start in background process
    process = multiprocessing.Process(target=watchdog.run, daemon=True)
    process.start()

    # Save PID for later management
    cache_dir = CACHE_DIR / session.name
    pid_file = cache_dir / "watchdog.pid"
    pid_file.write_text(str(process.pid))

    return process.pid


def stop_watchdog(session_name: str):
    """Stop watchdog for a session."""
    cache_dir = CACHE_DIR / session_name
    pid_file = cache_dir / "watchdog.pid"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            subprocess.run(["kill", str(pid)], capture_output=True)
            pid_file.unlink()
        except (ValueError, FileNotFoundError):
            pass


def extend_watchdog(session_name: str):
    """Reset watchdog timer by touching activity file."""
    # This is a simple approach - stop and restart the watchdog
    # In a real implementation, you might use IPC to signal the watchdog
    cache_dir = CACHE_DIR / session_name
    activity_file = cache_dir / "last_activity"
    activity_file.write_text(str(time.time()))
