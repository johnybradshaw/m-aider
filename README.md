# maider - Multi-provider GPU vLLM launcher

An opinionated `aider` wrapper for spinning up ephemeral cloud VMs for private code and chat.

> **Disclaimer**: This is an **unofficial**, community-maintained project. It is not affiliated with, endorsed by, or supported by Linode/Akamai, vLLM, Open WebUI, or aider. Use at your own risk. **No warranty is provided**, express or implied. You are responsible for any costs incurred and for reviewing the code before running it. Your mileage may vary.

**maider** (pronounced "m'aider" - like aider, but with cloud VMs) provisions short-lived GPU VMs running:
- **vLLM** (OpenAI-compatible API on the VM, bound to localhost)
- **Open WebUI** (ChatGPT-like UI, bound to localhost)
- **aider** on your laptop (Claude Code-like terminal workflow) via an SSH tunnel

The launcher is designed for rapid "spin up for 1–2 hours, then destroy" usage. Currently supports Linode, with multi-provider support planned.

## Security model

The services bind to **127.0.0.1 on the VM**, so they are not exposed publicly.
You access them via an **SSH tunnel**:

- Open WebUI: http://localhost:3000
- vLLM API: http://localhost:8000/v1

Your Linode Firewall should only need to allow **SSH (22)** from your IP.

## Prerequisites

On your laptop:
- Python 3.10+ (for the launcher)
- SSH public key at `~/.ssh/id_ed25519.pub`, `~/.ssh/id_rsa.pub`, or `~/.ssh/id_ecdsa.pub`
- `aider-chat` installed (recommended: `pipx install aider-chat`)
- **Optional**: 1Password CLI (`op`) for secure credential management

On Linode:
- Linode API token (via environment variable or `~/.config/linode-cli`)
- A Cloud Firewall ID (wizard will guide you, or set in `.env`)

## Quick start

### 1. Install the Python CLI

```bash
# Clone this repository
git clone https://github.com/johnybradshaw/m-aider.git
cd m-aider

# One-time installation
./install-python-maider.sh
source venv/bin/activate
```

### 2. Run the interactive wizard

```bash
maider wizard
```

The wizard guides you through:
- **Capability selection** - Choose model size (small/medium/large)
- **Region selection** - Pick based on latency (auto-queries Linode API)
- **GPU type** - Compare costs and capabilities
- **Model configuration** - Set HuggingFace model and context length
- **Credentials** - Add Linode token and HuggingFace token (supports 1Password)

All settings are saved to `.env` and `.env.secrets`.

**Note**: Both `maider` and `coder` commands work. `maider` is the new primary name, `coder` is maintained for backward compatibility.

### 3. Set up Linode API token

**Important**: Before deploying, you need a Linode API token:

```bash
# Option 1: Export as environment variable (recommended)
export LINODE_TOKEN=your_token_here

# Option 2: Configure linode-cli (auto-detected)
# The token will be read from ~/.config/linode-cli
```

Get your token at: https://cloud.linode.com/profile/tokens

### 4. Deploy and start coding

```bash
# Create VM and launch aider in one command
maider up --launch-aider
# Or: coder up --launch-aider
```

The launcher automatically:
- ✅ Creates VM with NVIDIA drivers
- ✅ Waits for cloud-init to complete (installs Docker, drivers)
- ✅ Reboots to activate NVIDIA drivers
- ✅ Waits for vLLM to download and load model (10-20 minutes)
- ✅ Auto-heals common errors (OOM, NCCL, tensor parallelism)
- ✅ Sets up SSH tunnel with port conflict resolution
- ✅ Generates aider metadata for correct token limits
- ✅ Launches aider ready to code

Start coding immediately - aider is already connected!

### 5. Clean up when done

```bash
# Destroy VM (shows total cost)
maider down
```

## Available Commands

> **Note**: All commands work with both `maider` and `coder`. Examples below show `maider` (primary) with `coder` (backward-compatible alias) noted where helpful.

### Setup & Configuration
```bash
maider wizard                       # Interactive setup wizard
maider validate                     # Validate .env configuration
maider list-types                   # List GPU types from Linode API
maider list-types --region de-fra-2 # Filter by specific region
maider list-types --refresh         # Force refresh from API (bypass cache)
```

### VM Lifecycle
```bash
maider up [name] [--launch-aider]  # Create VM (auto-named if no name given)
maider down [name]                 # Destroy VM (current session if no name)
maider list                        # List all sessions with costs
maider status [name]               # Show detailed session info
```

### Session Management
```bash
maider use <name>                      # Switch to different session
maider tunnel [name]                   # Re-establish SSH tunnel after reconnect
maider switch-model <model> [name]     # Change model on running VM (no destroy needed!)
maider extend [name]                   # Reset watchdog idle timer
maider cleanup                         # Remove stale sessions (VMs that no longer exist)
maider cleanup --session <n> --force   # Force-remove local state after manual VM deletion
```

### GPU Validation
```bash
maider check [name]           # Quick GPU health check (~30 sec)
maider validate-perf [name]   # Comprehensive validation (~5 min)
```

### Performance Benchmarking
```bash
maider benchmark              # Run performance benchmark on current VM
maider benchmark -s <name>    # Benchmark specific session
maider benchmark -o <file>    # Save results to custom file
```

## Key Features

### 🧙 Interactive Wizard
No manual .env editing required. The wizard:
- Queries Linode API for real-time region/GPU availability
- Recommends cheapest GPU that meets your requirements
- Suggests optimal models for selected hardware
- Validates all settings before saving

### 🔄 Auto-Healing
Automatically detects and fixes common errors:
- **OOM**: Reduces GPU memory utilization by 5% per retry
- **NCCL multi-GPU errors**: Adds required environment variables
- **Tensor parallelism misconfig**: Adjusts to match actual GPU count
- **Model loading errors**: Removes incompatible dtype settings

Up to 3 retry attempts with progressively stronger fixes.

### 💰 Cost Tracking
- **Before**: Shows hourly rate before creating VM
- **During**: Track runtime with `maider status`
- **After**: Shows total session cost when destroying

Example:
```bash
$ maider down
Session Summary:
══════════════════════════════════════
  Runtime: 1.47 hours
  Hourly rate: $3.00
  Total cost: $4.41
══════════════════════════════════════
```

### 🔀 Multi-VM Sessions
Run multiple VMs simultaneously:
```bash
# Start dev session with small model
maider up dev-session

# Start prod session with large model
maider up prod-session

# List all running VMs
maider list

# Switch between sessions
maider use dev-session
source .aider-env
aider --model "$AIDER_MODEL"

maider use prod-session
source .aider-env
aider --model "$AIDER_MODEL"
```

### 🔁 Model Switching
Change models without destroying the VM:
```bash
# Switch to different model
maider switch-model Qwen/Qwen2.5-Coder-14B-Instruct-AWQ

# Override parameters
maider switch-model Qwen/Qwen2.5-Coder-32B-Instruct \
  --max-model-len 32768 \
  --tensor-parallel-size 2

# Restart aider to use new model
source .aider-env
aider --model "$AIDER_MODEL"
```

Saves money by:
- Avoiding VM destruction/recreation costs
- Keeping model cache (faster subsequent loads)
- Testing multiple models on same hardware

### ⏱️ Watchdog Auto-Destroy
Optional feature to prevent forgotten VMs from accumulating costs:

```bash
# Add to .env
WATCHDOG_ENABLED=true
WATCHDOG_TIMEOUT_MINUTES=30

# Auto-destroys VM after 30 minutes of API inactivity
# Sends desktop notification 5 minutes before destruction
# Reset timer: maider extend
```

## Security Features

### Credential Management

**Recommended: .env.secrets file**
```bash
cat > .env.secrets <<EOF
HUGGING_FACE_HUB_TOKEN=hf_your_token_here
EOF
```

**Most secure: 1Password CLI**
```bash
cat > .env.secrets <<EOF
HUGGING_FACE_HUB_TOKEN=op://Private/HuggingFace/token
EOF

# Launcher auto-resolves op:// references
# Make sure: op signin
```

**Linode token** (one of):
- Environment variable: `export LINODE_TOKEN=xxx`
- linode-cli config: `~/.config/linode-cli` (auto-detected)

Your tokens are:
- ✅ Never committed to git (`.env.secrets` is ignored)
- ✅ Never stored in VM docker-compose.yml
- ✅ Stored on VM at `/opt/llm/.env` with mode 0600 (root only)

### Network Security
- Services bound to `127.0.0.1` (not public)
- Access only via SSH tunnel
- Firewall allows SSH (port 22) only
- SSH ControlMaster for persistent, secure tunnels

## Multi-GPU Support

The launcher fully supports multi-GPU configurations using vLLM's tensor parallelism.

### When to Use Multi-GPU
- Models larger than single GPU VRAM (70B+ models)
- Large context windows with 30B+ models
- Full-precision models instead of quantized

**Cost consideration**: Multi-GPU instances are expensive ($3-12/hour). Try quantized models on single GPU first.

### Quick Multi-GPU Setup

The wizard handles multi-GPU automatically:
```bash
maider wizard
# Select "Large models (70B+)" → wizard recommends appropriate multi-GPU type
```

Or manually in `.env`:
```bash
TYPE=g1-gpu-rtx6000-2                    # 2x RTX 6000 Ada (96GB total)
MODEL_ID=Qwen/Qwen2.5-Coder-70B-Instruct-AWQ
VLLM_TENSOR_PARALLEL_SIZE=2              # MUST match GPU count
VLLM_MAX_MODEL_LEN=32768
```

### Multi-GPU Validation

```bash
# Validate before deploying expensive multi-GPU instance
maider validate

# The validator checks:
# - VLLM_TENSOR_PARALLEL_SIZE matches GPU count
# - Model will fit in available VRAM
# - Configuration is valid
```

### Available Multi-GPU Types

| Linode TYPE | GPUs | VRAM per GPU | Total VRAM | Hourly Cost | Best For |
|-------------|------|--------------|------------|-------------|----------|
| `g2-gpu-rtx4000a2-s` | 2x RTX 4000 Ada | 20GB | 40GB | $1.04 | 30B models |
| `g1-gpu-rtx6000-2` | 2x RTX 6000 Ada | 48GB | 96GB | $3.00 | 70B models, large context |
| `g1-gpu-rtx6000-4` | 4x RTX 6000 Ada | 48GB | 192GB | $6.00 | 70B+ full precision |

**See `CLAUDE.md` for comprehensive multi-GPU documentation and troubleshooting.**

## Model Sizing Guidance

### Recommended Configurations

| Goal | Model Example | Linode TYPE | Cost/hr | Context |
|------|---------------|-------------|---------|---------|
| Budget coding assistant | Qwen2.5-Coder-7B-Instruct-AWQ | `g2-gpu-rtx4000a1-s` | $0.52 | 16K |
| Balanced performance | Qwen2.5-Coder-14B-Instruct-AWQ | `g2-gpu-rtx4000a1-s` | $0.52 | 16K |
| Strong coder | Qwen2.5-Coder-32B-Instruct-AWQ | `g1-gpu-rtx6000-1` | $1.50 | 32K |
| Maximum capability | Qwen2.5-Coder-70B-Instruct-AWQ | `g1-gpu-rtx6000-2` | $3.00 | 32K |

### General Guidelines

**Single GPU sizing:**
- **RTX 4000 Ada (20GB)**: 7B-14B AWQ models, moderate context
- **RTX 6000 Ada (48GB)**: 30B-32B AWQ models, large context

**Notes:**
- Start conservative with `VLLM_MAX_MODEL_LEN` (16384-32768)
- Increase gradually if stable
- Keep `VLLM_MAX_NUM_SEQS=1` for maximum context headroom
- Larger context = more KV cache = higher OOM risk

## vLLM Configuration

Configure vLLM via `.env` variables (set by wizard or manually):

```bash
# Model settings
MODEL_ID=Qwen/Qwen2.5-Coder-32B-Instruct-AWQ
SERVED_MODEL_NAME=coder                  # Name for API endpoint

# Performance tuning
VLLM_MAX_MODEL_LEN=32768                 # Context window size
VLLM_GPU_MEMORY_UTILIZATION=0.90         # GPU memory to use (0.85-0.95)
VLLM_MAX_NUM_SEQS=1                      # Concurrent sequences (1 for coding)

# Multi-GPU (if using multi-GPU instance)
VLLM_TENSOR_PARALLEL_SIZE=2              # Must match GPU count

# Advanced (optional)
VLLM_DTYPE=auto                          # Model dtype (auto/bfloat16/float16)
VLLM_EXTRA_ARGS=--enable-prefix-caching  # Additional flags
```

## Troubleshooting

### "No current session set" error
```bash
# List all sessions
maider list

# Switch to a session
maider use <session-name>

# Or specify session name in command
maider down <session-name>
```

### vLLM not ready / container crashes
The auto-healer will attempt to fix automatically. If it fails after 3 retries:

```bash
# Check what happened
ssh root@<ip> 'docker logs vllm'

# Common fixes:
# - Reduce VLLM_MAX_MODEL_LEN in .env
# - Reduce VLLM_GPU_MEMORY_UTILIZATION to 0.85
# - Switch to quantized model (AWQ/GPTQ)
```

### Multi-GPU deployment fails
```bash
# Validate configuration first
maider validate

# Ensure VLLM_TENSOR_PARALLEL_SIZE matches GPU count
# For g1-gpu-rtx6000-2: VLLM_TENSOR_PARALLEL_SIZE=2
# For g1-gpu-rtx6000-4: VLLM_TENSOR_PARALLEL_SIZE=4
```

### aider says "LLM Provider NOT provided"
Always use the OpenAI provider prefix:
```bash
# Correct
aider --model openai/coder

# Or use the exported variable
source .aider-env
aider --model "$AIDER_MODEL"
```

### Port conflicts (3000/8000 already in use)
The launcher automatically finds available ports. Check `.aider-env`:
```bash
source .aider-env
echo $ACTUAL_WEBUI_PORT   # Actual port for Open WebUI
echo $ACTUAL_API_PORT     # Actual port for vLLM API
```

### Model too slow / GPU underutilized
```bash
# Run performance validation
maider validate-perf

# This checks:
# - GPU utilization
# - Memory usage
# - Inference speed
# - Multi-GPU communication (if applicable)
```

## Advanced Usage

### Manual .env Configuration

If you prefer not to use the wizard:

1. **Copy template**:
   ```bash
   cp .env.example .env
   ```

2. **Edit minimum required fields**:
   ```bash
   REGION=us-east
   TYPE=g2-gpu-rtx4000a1-s
   FIREWALL_ID=your_firewall_id
   MODEL_ID=Qwen/Qwen2.5-Coder-14B-Instruct-AWQ
   SERVED_MODEL_NAME=coder
   ```

3. **Add credentials**:
   ```bash
   cat > .env.secrets <<EOF
   HUGGING_FACE_HUB_TOKEN=hf_xxx
   EOF
   ```

4. **Validate and deploy**:
   ```bash
   maider validate
   maider up --launch-aider
   ```

### Custom Model Parameters

Override vLLM parameters when switching models:
```bash
maider switch-model Qwen/Qwen2.5-Coder-70B-Instruct \
  --max-model-len 65536 \
  --tensor-parallel-size 4
```

## Documentation

- **README.md** (this file) - Quick start and command reference
- **CLAUDE.md** - Comprehensive technical documentation
- **[docs/ADDING-PROVIDERS.md](docs/ADDING-PROVIDERS.md)** - Guide for adding new cloud providers
- **[docs/PYTHON-MIGRATION.md](docs/PYTHON-MIGRATION.md)** - Migration guide from bash to Python
- **[docs/CLOUD-INIT-DESIGN.md](docs/CLOUD-INIT-DESIGN.md)** - VM initialization architecture
- **[docs/VALIDATION-GUIDE.md](docs/VALIDATION-GUIDE.md)** - GPU validation reference
- **[docs/MIGRATION-COMPLETE.md](docs/MIGRATION-COMPLETE.md)** - Feature parity and migration status
- **[docs/NEW-FEATURES.md](docs/NEW-FEATURES.md)** - Python CLI features and improvements
- **[docs/VALIDATION-COMMANDS.md](docs/VALIDATION-COMMANDS.md)** - Validation command quick reference

For bash usage, see the legacy section in `CLAUDE.md`.

## License

MIT License - See LICENSE file for details.

## Contributing

This is a community project. Contributions welcome! Please:
1. Test changes thoroughly
2. Update documentation
3. Follow existing code style
4. Run tests before submitting: `pytest tests/`

## Credits

- Original concept and bash implementation
- Python migration with SDK integration, auto-healing, and modern CLI
- Community feedback and bug reports
