"""Docker Compose rendering utilities."""

from __future__ import annotations

from dataclasses import dataclass
import shlex

from .config import Config


@dataclass(frozen=True)
class ComposeRuntime:
    """Runtime values for rendering docker-compose.yml."""

    model_id: str
    served_model_name: str
    vllm_tensor_parallel_size: int
    vllm_max_model_len: int
    vllm_gpu_memory_utilization: float
    vllm_max_num_seqs: int
    vllm_dtype: str
    vllm_extra_args: str
    vllm_image: str
    openwebui_image: str
    vllm_port: int
    webui_port: int
    enable_openwebui: bool
    enable_hf_cache: bool
    enable_healthchecks: bool
    enable_nccl_env: bool


def runtime_from_config(
    config: Config,
    model_id: str | None = None,
    served_model_name: str | None = None,
) -> ComposeRuntime:
    """Build runtime settings from config and optional overrides."""
    return ComposeRuntime(
        model_id=model_id or config.model_id,
        served_model_name=served_model_name or config.served_model_name,
        vllm_tensor_parallel_size=config.vllm_tensor_parallel_size,
        vllm_max_model_len=config.vllm_max_model_len,
        vllm_gpu_memory_utilization=config.vllm_gpu_memory_utilization,
        vllm_max_num_seqs=config.vllm_max_num_seqs,
        vllm_dtype=config.vllm_dtype,
        vllm_extra_args=config.vllm_extra_args,
        vllm_image=config.vllm_image,
        openwebui_image=config.openwebui_image,
        vllm_port=config.vllm_port,
        webui_port=config.webui_port,
        enable_openwebui=config.enable_openwebui,
        enable_hf_cache=config.enable_hf_cache,
        enable_healthchecks=config.enable_healthchecks,
        enable_nccl_env=config.enable_nccl_env,
    )


def render_runtime_env(runtime: ComposeRuntime, hf_token: str) -> str:
    """Render /opt/llm/.env for Compose interpolation and container env."""
    return "\n".join(
        [
            "HUGGING_FACE_HUB_TOKEN={}".format(hf_token),
            "MODEL_ID={}".format(runtime.model_id),
            "SERVED_MODEL_NAME={}".format(runtime.served_model_name),
            "VLLM_TENSOR_PARALLEL_SIZE={}".format(runtime.vllm_tensor_parallel_size),
            "VLLM_MAX_MODEL_LEN={}".format(runtime.vllm_max_model_len),
            "VLLM_GPU_MEMORY_UTILIZATION={}".format(runtime.vllm_gpu_memory_utilization),
            "VLLM_MAX_NUM_SEQS={}".format(runtime.vllm_max_num_seqs),
            "VLLM_DTYPE={}".format(runtime.vllm_dtype),
            "VLLM_EXTRA_ARGS={}".format(runtime.vllm_extra_args),
            "VLLM_IMAGE={}".format(runtime.vllm_image),
            "OPENWEBUI_IMAGE={}".format(runtime.openwebui_image),
            "VLLM_PORT={}".format(runtime.vllm_port),
            "WEBUI_PORT={}".format(runtime.webui_port),
        ]
    )


def _vllm_command_args(runtime: ComposeRuntime) -> list[str]:
    args = [
        "serve",
        "${MODEL_ID}",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--served-model-name",
        "${SERVED_MODEL_NAME}",
        "--gpu-memory-utilization",
        "${VLLM_GPU_MEMORY_UTILIZATION}",
        "--max-num-seqs",
        "${VLLM_MAX_NUM_SEQS}",
        "--max-model-len",
        "${VLLM_MAX_MODEL_LEN}",
        "--tensor-parallel-size",
        "${VLLM_TENSOR_PARALLEL_SIZE}",
        "--dtype",
        "${VLLM_DTYPE}",
    ]
    extra = runtime.vllm_extra_args.strip()
    if extra:
        args.extend(shlex.split(extra))
    return args


def _yaml_quote(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')


def _vllm_healthcheck() -> str:
    return "\n".join(
        [
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://localhost:8000/v1/models >/dev/null"]',
            "      interval: 30s",
            "      timeout: 5s",
            "      retries: 6",
        ]
    )


def _webui_healthcheck() -> str:
    return "\n".join(
        [
            "    healthcheck:",
            '      test: ["CMD-SHELL", "curl -fsS http://localhost:8080/ >/dev/null"]',
            "      interval: 30s",
            "      timeout: 5s",
            "      retries: 6",
        ]
    )


def render_compose(runtime: ComposeRuntime) -> str:
    """Render docker-compose.yml content based on runtime settings."""
    vllm_env = [
        "    env_file:",
        "      - .env",
        "    environment:",
        "      - HF_HOME=/data/hf",
        "      - HF_TOKEN=${HUGGING_FACE_HUB_TOKEN}",
    ]
    if runtime.enable_nccl_env:
        vllm_env.extend(
            [
                "      - NCCL_DEBUG=INFO",
                "      - NCCL_P2P_DISABLE=0",
                "      - NCCL_IB_DISABLE=1",
            ]
        )

    vllm_volumes = []
    volumes_section = []
    if runtime.enable_hf_cache:
        vllm_volumes.append("    volumes:")
        vllm_volumes.append("      - vllm_hf:/data/hf")
        volumes_section.append("  vllm_hf:")

    vllm_healthcheck = _vllm_healthcheck() if runtime.enable_healthchecks else ""

    openwebui_service = ""
    if runtime.enable_openwebui:
        webui_healthcheck = _webui_healthcheck() if runtime.enable_healthchecks else ""
        openwebui_service = "\n".join(
            [
                "  openwebui:",
                "    image: ${OPENWEBUI_IMAGE}",
                "    ports:",
                '      - "127.0.0.1:${WEBUI_PORT}:8080"',
                "    environment:",
                "      - OPENAI_API_BASE_URL=http://vllm:8000/v1",
                "      - OPENAI_API_KEY=sk-dummy",
                "    volumes:",
                "      - openwebui_data:/app/backend/data",
                "    depends_on:",
                "      - vllm",
                "    restart: unless-stopped",
                webui_healthcheck,
                "",
            ]
        ).rstrip()
        volumes_section.append("  openwebui_data:")

    volumes_block = ""
    if volumes_section:
        volumes_block = "\n".join(["volumes:"] + volumes_section)

    return (
        "\n".join(
            [
                'version: "3.8"',
                "",
                "services:",
                "  vllm:",
                "    image: ${VLLM_IMAGE}",
                "    ipc: host",
                "    gpus: all",
                "    ports:",
                '      - "127.0.0.1:${VLLM_PORT}:8000"',
                *vllm_env,
                "    entrypoint:",
                '      - "vllm"',
                "    command:",
                *[f'      - "{_yaml_quote(arg)}"' for arg in _vllm_command_args(runtime)],
                "    restart: unless-stopped",
                vllm_healthcheck,
                *vllm_volumes,
                "",
                openwebui_service,
                volumes_block,
            ]
        ).strip()
        + "\n"
    )
