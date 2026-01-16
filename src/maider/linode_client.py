"""Linode API client wrapper.

This module provides backward compatibility by wrapping the new
provider abstraction layer.
"""

import secrets
import string
from pathlib import Path
from typing import Optional

from linode_api4 import LinodeClient, Instance
from rich.console import Console

from .config import Config
from .providers.linode import LinodeProvider

console = Console()


class LinodeManager:
    """Manages Linode instances for vLLM deployment.

    This class now wraps LinodeProvider for backward compatibility.
    """

    def __init__(self, config: Config):
        """Initialize Linode manager."""
        self.config = config
        self.client = LinodeClient(token=config.api_token)
        self.provider = LinodeProvider(api_token=config.api_token)

    def create_instance(self, label: str) -> Instance:
        """Create a new Linode instance with GPU support.

        Uses LinodeProvider internally but returns linode_api4 Instance
        for backward compatibility.
        """
        # Get SSH public key
        ssh_key = self._get_ssh_key()

        # Generate cloud-init configuration
        cloud_init = self._generate_cloud_init(ssh_key)

        # Create instance using provider
        try:
            vm_instance = self.provider.create_instance(
                region=self.config.region,
                vm_type=self.config.type,
                label=label,
                ssh_key=ssh_key,
                cloud_init_config=cloud_init,
                firewall_id=self.config.firewall_id,
            )

            # Load and return the linode_api4 Instance for backward compatibility
            instance = self.client.load(Instance, int(vm_instance.provider_instance_id))
            return instance

        except Exception as e:
            console.print(f"[red]✗ Failed to create Linode: {e}[/red]")
            raise

    def get_instance(self, linode_id: int) -> Optional[Instance]:
        """Get an instance by ID."""
        try:
            return self.client.load(Instance, linode_id)
        except Exception:
            return None

    def delete_instance(self, linode_id: int):
        """Delete a Linode instance.

        Uses LinodeProvider internally.
        """
        self.provider.delete_instance(str(linode_id))

    def get_instance_status(self, linode_id: int) -> Optional[str]:
        """Get the current status of a Linode instance.

        Args:
            linode_id: Linode instance ID

        Returns:
            Status string (e.g., "running", "offline", "booting") or None if error
        """
        try:
            status_data = self.provider.get_instance_status(str(linode_id))
            return status_data.get("status")
        except Exception:
            return None

    def _generate_password(self, length: int = 32) -> str:
        """Generate a random password."""
        alphabet = string.ascii_letters + string.digits
        return "".join(secrets.choice(alphabet) for _ in range(length))

    def _get_ssh_key(self) -> str:
        """Find and read SSH public key."""
        key_paths = [
            Path.home() / ".ssh" / "id_ed25519.pub",
            Path.home() / ".ssh" / "id_rsa.pub",
            Path.home() / ".ssh" / "id_ecdsa.pub",
        ]

        for key_path in key_paths:
            if key_path.exists():
                return key_path.read_text().strip()

        raise FileNotFoundError(
            "No SSH public key found. Please generate one with: ssh-keygen -t ed25519"
        )

    def _generate_cloud_init(self, ssh_key: str) -> str:
        """Generate cloud-init configuration."""
        # Build vLLM command arguments
        from .compose import render_compose, render_runtime_env, runtime_from_config

        runtime = runtime_from_config(self.config)
        docker_compose = render_compose(runtime)
        runtime_env = render_runtime_env(runtime, self.config.hf_token)

        cloud_init = f"""#cloud-config
users:
  - name: root
    ssh_authorized_keys:
      - {ssh_key}

write_files:
  - path: /opt/llm/.env
    content: |
{self._indent(runtime_env, 6)}
    permissions: '0600'

  - path: /opt/llm/docker-compose.yml
    content: |
{self._indent(docker_compose, 6)}

  - path: /etc/systemd/system/vllm.service
    content: |
      [Unit]
      Description=vLLM and Open WebUI containers
      After=docker.service
      Requires=docker.service

      [Service]
      Type=oneshot
      RemainAfterExit=yes
      WorkingDirectory=/opt/llm
      # Wait for NVIDIA devices to be available
      ExecStartPre=/bin/bash -c 'until nvidia-smi &>/dev/null; do sleep 2; done'
      # Clean up any existing containers
      ExecStartPre=/usr/bin/docker compose down --remove-orphans
      # Start containers
      ExecStart=/usr/bin/docker compose up -d --force-recreate
      ExecStop=/usr/bin/docker compose down

      [Install]
      WantedBy=multi-user.target
    permissions: '0644'

package_update: true
package_upgrade: true

packages:
  - apt-transport-https
  - ca-certificates
  - curl
  - gnupg
  - lsb-release
  - nvtop

runcmd:
  # Install NVIDIA server drivers (optimized for data center/cloud environments)
  - DEBIAN_FRONTEND=noninteractive apt-get update
  - DEBIAN_FRONTEND=noninteractive apt-get install -y nvidia-driver-580-server
  # Install Docker
  - curl -fsSL https://download.docker.com/linux/ubuntu/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg
  - echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" > /etc/apt/sources.list.d/docker.list
  - apt-get update
  - apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
  # Install NVIDIA container toolkit
  - curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
  - curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' > /etc/apt/sources.list.d/nvidia-container-toolkit.list
  - apt-get update
  - apt-get install -y nvidia-container-toolkit
  - nvidia-ctk runtime configure --runtime=docker
  # Enable vLLM service
  - systemctl daemon-reload
  - systemctl enable vllm.service

power_state:
  mode: reboot
  message: Rebooting to activate NVIDIA drivers and container runtime
  condition: true
"""
        return cloud_init

    def _indent(self, text: str, spaces: int) -> str:
        """Indent each line of text."""
        indent = " " * spaces
        return "\n".join(indent + line for line in text.split("\n"))
