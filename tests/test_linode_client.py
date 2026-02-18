import pytest
from unittest.mock import MagicMock, patch
from linode_api4 import Instance

from src.maider.linode_client import LinodeManager, Config
from src.maider.providers.base import VMInstance


# Mocking the Config class for testing
@pytest.fixture
def mock_config():
    config = MagicMock(spec=Config)
    config.api_token = "mock_token"
    config.linode_token = "mock_token"
    config.region = "us-central"
    config.type = "g6-standard-2"
    config.model_id = "mock_model"
    config.served_model_name = "mock_served_model"
    config.vllm_tensor_parallel_size = 1
    config.vllm_max_model_len = 2048
    config.vllm_gpu_memory_utilization = 0.8
    config.vllm_max_num_seqs = 1024
    config.vllm_dtype = "float16"
    config.vllm_extra_args = "--extra-arg"
    config.vllm_image = "vllm/vllm-openai:latest"
    config.openwebui_image = "ghcr.io/open-webui/open-webui:main"
    config.vllm_port = 8000
    config.webui_port = 3000
    config.enable_openwebui = True
    config.openwebui_auth = True
    config.enable_hf_cache = True
    config.enable_healthchecks = False
    config.enable_nccl_env = False
    config.hf_token = "mock_hf_token"
    config.firewall_id = "mock_firewall_id"
    return config


# Mocking the LinodeProvider class for testing
@pytest.fixture
def mock_provider():
    from src.maider.providers.base import ProviderType

    provider = MagicMock()
    provider.create_instance.return_value = VMInstance(
        provider_instance_id="12345",
        ip_address="192.168.1.1",
        region="us-central",
        type="g6-standard-2",
        status="running",
        provider_type=ProviderType.LINODE,
    )
    provider.get_instance_status.return_value = {"status": "running"}
    provider.delete_instance.return_value = True
    return provider


# Mocking the LinodeClient class for testing
@pytest.fixture
def mock_client(mock_provider):
    client = MagicMock()
    client.load.return_value = Instance(client, 12345, {})
    return client


# Mocking the Console class for testing
@pytest.fixture
def mock_console():
    return MagicMock()


# Test class for LinodeManager
@pytest.mark.unit
class TestLinodeManager:
    def test_create_instance(self, mock_config, mock_provider, mock_client, mock_console):
        with (
            patch("src.maider.linode_client.LinodeProvider", return_value=mock_provider),
            patch("src.maider.linode_client.LinodeClient", return_value=mock_client),
            patch("src.maider.linode_client.Console", return_value=mock_console),
            patch(
                "src.maider.linode_client.LinodeManager._get_ssh_key", return_value="mock_ssh_key"
            ),
            patch(
                "src.maider.linode_client.LinodeManager._generate_cloud_init",
                return_value="mock_cloud_init",
            ),
        ):
            manager = LinodeManager(config=mock_config)
            instance = manager.create_instance(label="test_instance")
            assert instance.id == 12345
            mock_provider.create_instance.assert_called_once_with(
                region="us-central",
                vm_type="g6-standard-2",
                label="test_instance",
                ssh_key="mock_ssh_key",
                cloud_init_config="mock_cloud_init",
                firewall_id="mock_firewall_id",
            )
            mock_client.load.assert_called_once_with(Instance, 12345)

    def test_get_instance(self, mock_config, mock_client, mock_console):
        with (
            patch("src.maider.linode_client.LinodeClient", return_value=mock_client),
            patch("src.maider.linode_client.Console", return_value=mock_console),
        ):
            manager = LinodeManager(config=mock_config)
            instance = manager.get_instance(linode_id=12345)
            assert instance.id == 12345
            mock_client.load.assert_called_once_with(Instance, 12345)

    def test_delete_instance(self, mock_config, mock_provider, mock_console):
        with (
            patch("src.maider.linode_client.LinodeProvider", return_value=mock_provider),
            patch("src.maider.linode_client.Console", return_value=mock_console),
        ):
            manager = LinodeManager(config=mock_config)
            manager.delete_instance(linode_id=12345)
            mock_provider.delete_instance.assert_called_once_with("12345")

    def test_get_instance_status(self, mock_config, mock_provider, mock_console):
        with (
            patch("src.maider.linode_client.LinodeProvider", return_value=mock_provider),
            patch("src.maider.linode_client.Console", return_value=mock_console),
        ):
            manager = LinodeManager(config=mock_config)
            status = manager.get_instance_status(linode_id=12345)
            assert status == "running"
            mock_provider.get_instance_status.assert_called_once_with("12345")

    def test_generate_password(self, mock_config, mock_console):
        with patch("src.maider.linode_client.Console", return_value=mock_console):
            manager = LinodeManager(config=mock_config)
            password = manager._generate_password(length=32)
            assert len(password) == 32

    def test_get_ssh_key(self, mock_config, mock_console):
        with (
            patch("src.maider.linode_client.Console", return_value=mock_console),
            patch("pathlib.Path.exists", return_value=True),
            patch("pathlib.Path.read_text", return_value="mock_ssh_key"),
        ):
            manager = LinodeManager(config=mock_config)
            ssh_key = manager._get_ssh_key()
            assert ssh_key == "mock_ssh_key"

    def test_generate_cloud_init(self, mock_config, mock_console):
        with patch("src.maider.linode_client.Console", return_value=mock_console):
            manager = LinodeManager(config=mock_config)
            cloud_init = manager._generate_cloud_init(ssh_key="mock_ssh_key")
            assert "mock_ssh_key" in cloud_init
            assert "mock_model" in cloud_init
            assert "mock_served_model" in cloud_init
            assert "mock_hf_token" in cloud_init
