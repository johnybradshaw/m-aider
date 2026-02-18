"""Interactive setup wizard."""

import sys
from pathlib import Path

import click
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

from ..config import Config
from ..output import console

# Import GPU data from provider abstraction
from ..providers.linode import GPU_REGIONS as LINODE_GPU_REGIONS
from ..providers.linode import GPU_TYPES as LINODE_GPU_TYPES
CHOICE_PROMPT = "\nChoice"


# Model recommendations by capability
CAPABILITY_MODELS = {
    "small": {
        "name": "Small models (7B-14B)",
        "description": "Fast, budget-friendly",
        "min_vram_gb": 12,
        "recommended_model": "Qwen/Qwen2.5-Coder-14B-Instruct-AWQ",
        "context_length": 32768,
        "cost_range": "$0.52-1.50/hr",
    },
    "medium": {
        "name": "Medium models (30B-32B)",
        "description": "Balanced performance",
        "min_vram_gb": 40,
        "recommended_model": "Qwen/Qwen2.5-Coder-32B-Instruct-AWQ",
        "context_length": 32768,
        "cost_range": "$1.04-3.00/hr",
    },
    "large": {
        "name": "Large models (70B+)",
        "description": "Maximum capability",
        "min_vram_gb": 80,
        "recommended_model": "Qwen/Qwen2.5-72B-Instruct-AWQ",
        "context_length": 32768,
        "cost_range": "$3.00-6.00/hr",
    },
}

# Performance profiles for vLLM defaults
PERF_PROFILES = {
    "A": {
        "label": "Conservative (lowest OOM risk)",
        "gpu_util": 0.80,
        "max_num_seqs": 1,
        "extra_args": "",
    },
    "B": {
        "label": "Balanced (recommended)",
        "gpu_util": 0.90,
        "max_num_seqs": 1,
        "extra_args": "",
    },
    "C": {
        "label": "Throughput (higher parallelism)",
        "gpu_util": 0.90,
        "max_num_seqs": 2,
        "extra_args": "",
    },
    "D": {
        "label": "Long-context (stable)",
        "gpu_util": 0.85,
        "max_num_seqs": 1,
        "extra_args": "--enable-prefix-caching",
    },
    "E": {
        "label": "Aggressive (max throughput)",
        "gpu_util": 0.95,
        "max_num_seqs": 4,
        "extra_args": "--enable-prefix-caching",
    },
}

# Backward compatibility: Use provider abstraction for GPU data
# These reference the LinodeProvider constants
GPU_REGIONS = LINODE_GPU_REGIONS
GPU_TYPES = LINODE_GPU_TYPES


@click.command(name="wizard")
def cmd():
    """Interactive setup wizard for VM configuration.

    Guides you through selecting capability, region, GPU type, and model.
    """
    _print_wizard_header()
    firewall_id, hf_token = _load_existing_credentials()

    capability, custom_model = _choose_capability()
    selected_region = _choose_region()
    selected_type, selected_type_info = _choose_gpu_type(capability, selected_region)
    model_id, served_name, context_length = _configure_model(capability, custom_model)
    profile_choice, profile = _choose_profile()
    deployment_options = _choose_deployment_options()

    firewall_id, hf_token = _ensure_credentials(firewall_id, hf_token)
    _print_summary(
        selected_region,
        selected_type,
        selected_type_info,
        model_id,
        served_name,
        context_length,
        profile_choice,
        profile,
        deployment_options,
    )

    if not Confirm.ask("Save configuration to .env?", default=True):
        console.print("\n[yellow]Configuration not saved[/yellow]")
        return

    _save_env_files(
        selected_region,
        selected_type,
        selected_type_info,
        model_id,
        served_name,
        context_length,
        profile_choice,
        profile,
        deployment_options,
        firewall_id,
        hf_token,
    )
    _print_next_steps()


def _print_wizard_header():
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]LLM Deployment Wizard[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()


def _load_existing_credentials():
    try:
        existing_config = Config()
        return existing_config.firewall_id, existing_config.hf_token
    except Exception:
        return None, None


def _choose_capability():
    console.print("[bold]Step 1: What capability do you need?[/bold]\n")
    capability_choices = [
        f"{info['name']} - {info['description']} ({info['cost_range']})"
        for info in CAPABILITY_MODELS.values()
    ]
    capability_choices.append("Custom - I'll specify my own model")

    for i, choice in enumerate(capability_choices, 1):
        console.print(f"  {i}) {choice}")

    capability_idx = (
        int(
            Prompt.ask(
                CHOICE_PROMPT, choices=[str(i) for i in range(1, len(capability_choices) + 1)]
            )
        )
        - 1
    )

    if capability_idx < len(CAPABILITY_MODELS):
        capability_key = list(CAPABILITY_MODELS.keys())[capability_idx]
        return CAPABILITY_MODELS[capability_key], False
    return None, True


def _choose_region():
    console.print("\n[bold]Step 2: Select your region[/bold]")
    console.print("[dim]Only regions with GPU availability shown[/dim]\n")

    regions = [
        ("us-east", "Newark, NJ (RTX 6000)"),
        ("us-ord", "Chicago, IL (RTX 4000 Ada)"),
        ("us-sea", "Seattle, WA (RTX 4000 Ada)"),
        ("us-southeast", "Atlanta, GA (RTX 6000)"),
        ("eu-central", "Frankfurt, DE (RTX 6000)"),
        ("de-fra-2", "Frankfurt 2, DE (RTX 4000 Ada)"),
        ("fr-par", "Paris, FR (RTX 4000 Ada)"),
        ("ap-south", "Singapore, SG (RTX 6000)"),
        ("sg-sin-2", "Singapore 2, SG (RTX 4000 Ada)"),
        ("ap-west", "Mumbai, IN (RTX 6000)"),
        ("in-bom-2", "Mumbai 2, IN (RTX 4000 Ada)"),
        ("jp-osa", "Osaka, JP (RTX 4000 Ada)"),
    ]

    for i, (region_id, region_name) in enumerate(regions, 1):
        console.print(f"  {i}) {region_id} - {region_name}")

    region_idx = (
        int(Prompt.ask(CHOICE_PROMPT, choices=[str(i) for i in range(1, len(regions) + 1)])) - 1
    )
    return regions[region_idx][0]


def _choose_gpu_type(capability, selected_region: str):
    console.print("\n[bold]Step 3: Select VM type[/bold]")
    console.print(f"[dim]Region: {selected_region}[/dim]\n")

    suitable_types = _filter_gpu_types(capability)
    if not suitable_types:
        console.print("[red]No suitable GPU types found for this capability[/red]")
        sys.exit(1)

    sorted_types = sorted(suitable_types.items(), key=lambda x: x[1]["hourly_cost"])
    type_choices = _build_type_choices(sorted_types)

    for i, (_, choice_text, _) in enumerate(type_choices, 1):
        console.print(f"  {i}) {choice_text}")

    type_idx = (
        int(Prompt.ask(CHOICE_PROMPT, choices=[str(i) for i in range(1, len(type_choices) + 1)]))
        - 1
    )
    selected_type = type_choices[type_idx][0]
    selected_type_info = type_choices[type_idx][2]
    return selected_type, selected_type_info


def _filter_gpu_types(capability):
    if not capability:
        return GPU_TYPES
    min_vram = capability["min_vram_gb"]
    return {
        type_id: info
        for type_id, info in GPU_TYPES.items()
        if info["gpus"] * info["vram_per_gpu"] >= min_vram
    }


def _build_type_choices(sorted_types):
    type_choices = []
    for type_id, info in sorted_types:
        total_vram = info["gpus"] * info["vram_per_gpu"]
        gpu_label = f"{info['gpus']}x" if info["gpus"] > 1 else ""
        vram_label = "RTX 6000 Ada" if "rtx6000" in type_id else "RTX 4000 Ada"
        choice_text = f"{gpu_label}{vram_label} ({total_vram}GB) - ${info['hourly_cost']:.2f}/hr"
        if sorted_types[0][0] == type_id:
            choice_text += " ← Recommended"
        type_choices.append((type_id, choice_text, info))
    return type_choices


def _configure_model(capability, custom_model: bool):
    console.print("\n[bold]Step 4: Model configuration[/bold]\n")

    if custom_model:
        model_id = Prompt.ask("Enter HuggingFace model ID")
        served_name = Prompt.ask("Served model name", default="coder")
        context_length = int(Prompt.ask("Context length (tokens)", default="16384"))
        return model_id, served_name, context_length

    console.print(f"  Default model: {capability['recommended_model']}")
    console.print(f"  Context: {capability['context_length']} tokens\n")
    if Confirm.ask("Use custom model instead?", default=False):
        model_id = Prompt.ask("Enter HuggingFace model ID")
        served_name = Prompt.ask("Served model name", default="coder")
        context_length = int(
            Prompt.ask("Context length (tokens)", default=str(capability["context_length"]))
        )
        return model_id, served_name, context_length

    return capability["recommended_model"], "coder", capability["context_length"]


def _choose_profile():
    console.print("\n[bold]Step 4b: Performance profile[/bold]\n")
    for key, profile in PERF_PROFILES.items():
        console.print(f"  {key}) {profile['label']}")
    profile_choice = Prompt.ask("Choice", choices=list(PERF_PROFILES.keys()), default="B")
    return profile_choice, PERF_PROFILES[profile_choice]


def _choose_deployment_options():
    console.print("\n[bold]Step 4c: Deployment options[/bold]\n")
    return {
        "enable_openwebui": Confirm.ask("Enable Open WebUI?", default=True),
        "enable_hf_cache": Confirm.ask("Enable persistent HF cache volume?", default=True),
        "enable_healthchecks": Confirm.ask("Enable container health checks?", default=False),
        "enable_nccl_env": Confirm.ask("Enable NCCL reliability env vars?", default=False),
    }


def _ensure_credentials(firewall_id, hf_token):
    if not firewall_id:
        console.print("\n[bold]Step 5: Linode Configuration[/bold]\n")
        console.print("You need a Linode firewall ID for SSH access.")
        console.print("Create one at: https://cloud.linode.com/firewalls\n")
        firewall_id = Prompt.ask("Firewall ID")

    if not hf_token:
        console.print("\n[bold]Step 6: HuggingFace Token[/bold]\n")
        console.print("You need a HuggingFace token to download models.")
        console.print("Get one at: https://huggingface.co/settings/tokens\n")
        hf_token = Prompt.ask("HuggingFace Token (or 1Password reference)")

    return firewall_id, hf_token


def _print_summary(
    selected_region,
    selected_type,
    selected_type_info,
    model_id,
    served_name,
    context_length,
    profile_choice,
    profile,
    deployment_options,
):
    console.print()
    console.print(
        Panel.fit(
            "[bold cyan]Configuration Summary[/bold cyan]",
            border_style="cyan",
        )
    )
    console.print()

    total_vram = selected_type_info["gpus"] * selected_type_info["vram_per_gpu"]
    console.print(f"  Region:       {selected_region}")
    console.print(f"  VM Type:      {selected_type}")
    console.print(f"  GPUs:         {selected_type_info['gpus']}")
    console.print(f"  Total VRAM:   {total_vram}GB")
    console.print(f"  Hourly Cost:  ${selected_type_info['hourly_cost']:.2f}/hr")
    console.print()
    console.print(f"  Model:        {model_id}")
    console.print(f"  Served as:    {served_name}")
    console.print(f"  Context:      {context_length} tokens")
    console.print(f"  Profile:      {profile_choice} ({profile['label']})")
    console.print(f"  Open WebUI:   {'Yes' if deployment_options['enable_openwebui'] else 'No'}")
    console.print(f"  HF Cache:     {'Yes' if deployment_options['enable_hf_cache'] else 'No'}")
    console.print(
        f"  Healthchecks:{' Yes' if deployment_options['enable_healthchecks'] else ' No'}"
    )
    console.print(f"  NCCL Env:     {'Yes' if deployment_options['enable_nccl_env'] else 'No'}")
    console.print()


def _save_env_files(
    selected_region,
    selected_type,
    selected_type_info,
    model_id,
    served_name,
    context_length,
    profile_choice,
    profile,
    deployment_options,
    firewall_id,
    hf_token,
):
    tensor_parallel_size = selected_type_info["gpus"]
    env_content = f"""# Linode Configuration
REGION={selected_region}
TYPE={selected_type}
FIREWALL_ID={firewall_id}

# Model Configuration
MODEL_ID={model_id}
SERVED_MODEL_NAME={served_name}

# vLLM Configuration
VLLM_TENSOR_PARALLEL_SIZE={tensor_parallel_size}
VLLM_MAX_MODEL_LEN={context_length}
VLLM_GPU_MEMORY_UTILIZATION={profile["gpu_util"]}
VLLM_MAX_NUM_SEQS={profile["max_num_seqs"]}
VLLM_DTYPE=auto
VLLM_EXTRA_ARGS={profile["extra_args"]}

# Deployment Options
PERF_PROFILE={profile_choice}
ENABLE_OPENWEBUI={"true" if deployment_options["enable_openwebui"] else "false"}
ENABLE_HF_CACHE={"true" if deployment_options["enable_hf_cache"] else "false"}
ENABLE_HEALTHCHECKS={"true" if deployment_options["enable_healthchecks"] else "false"}
ENABLE_NCCL_ENV={"true" if deployment_options["enable_nccl_env"] else "false"}
"""

    env_path = Path.cwd() / ".env"
    env_path.write_text(env_content)

    secrets_content = f"""# HuggingFace Token
HUGGING_FACE_HUB_TOKEN={hf_token}
"""

    secrets_path = Path.cwd() / ".env.secrets"
    secrets_path.write_text(secrets_content)

    console.print("\n[green]✓ Configuration saved![/green]\n")


def _print_next_steps():
    console.print("[bold]Next steps:[/bold]")
    console.print("  coder validate    # Verify configuration")
    console.print("  coder up          # Deploy VM and launch")
    console.print()
