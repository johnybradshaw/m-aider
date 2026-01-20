# maider - Multi-provider GPU vLLM launcher

> **⚠️ Disclaimer**: This is an **unofficial**, community-maintained project. Not affiliated with or supported by Linode/Akamai, vLLM, Open WebUI, or aider. Use at your own risk. No warranty provided.

> **📝 IMPORTANT**: This file documents the architecture, features, and usage of maider (pronounced "m'aider" - like aider, but with cloud VMs).
> **Always update CLAUDE.MD when making changes to this repository.**

## Overview

**maider** is a multi-provider GPU VM deployment tool for running large language models. It currently supports Linode, with multi-provider support (DigitalOcean, Scaleway, etc.) planned for future releases.

This document describes the multi-card GPU support for running large language models that require more VRAM than a single GPU can provide. The launcher supports vLLM's tensor parallelism feature, which distributes model layers across multiple GPUs.

- **Python CLI (`maider`)** - **Recommended** - Modern, maintainable, handles Linode API changes automatically-

## Recent Major Updates (2026-01)

### Multi-VM Session Management & Auto-Destroy
- ✅ **Multi-VM sessions**: Run multiple VMs simultaneously without config conflicts
- ✅ **Session naming**: Auto-generated names (e.g., `qwen32b-20260114-143022`) or custom
- ✅ **State persistence**: Sessions stored in `~/.cache/linode-vms/<session>/`
- ✅ **Session switching**: `./maider use <session>` to switch between VMs
- ✅ **SSH tunnel reconnection**: `maider tunnel` re-establishes tunnel after network drop or restart
- ✅ **Safe VM deletion**: Validates API token before deleting local state, prevents orphaned VMs
- ✅ **Orphaned VM cleanup**: `maider cleanup --session <name> --force` to clean up after manual deletion
- ✅ **Client-side watchdog**: Auto-destroy idle VMs (API token stays on your machine)
- ✅ **Activity detection**: Monitors vLLM API requests via SSH
- ✅ **Desktop notifications**: Warning before destruction (macOS/Linux)
- ✅ **Cost aggregation**: `./maider list` shows total hourly cost across all VMs

### Self-Healing Multi-GPU Support
- ✅ **Intelligent error detection**: `diagnose_and_fix_vllm()` analyzes container logs for specific error types
- ✅ **OOM auto-recovery**: Reduces `--gpu-memory-utilization` by 5% per retry, halves `--max-model-len` on 2nd+ retry
- ✅ **NCCL error handling**: Detects multi-GPU communication errors and adds NCCL env vars automatically
- ✅ **Tensor parallelism fixes**: Detects TP misconfigurations and adjusts to match actual GPU count
- ✅ **Model loading recovery**: Removes incompatible dtype settings when architecture errors occur

### Security & Automation
- ✅ **Separated secrets**: HuggingFace token moved to `.env.secrets` (git-ignored)
- ✅ **1Password integration**: Automatic `op://` reference resolution
- ✅ **Interactive wizard**: `maider wizard` guides you through capability → region → VM selection
- ✅ **Dynamic API queries**: Real-time region and GPU type availability from Linode API
- ✅ **Auto-ready detection**: Waits for model to load, sets up tunnel automatically
- ✅ **Cost tracking**: Shows hourly rate before creation, total cost on destruction
- ✅ **Intelligent port management**: Handles port conflicts automatically
- ✅ **SSH ControlMaster**: Persistent, reliable tunnel management
- ✅ **nvtop pre-installed**: Monitor GPU usage on the VM
- ✅ **Aider token limits**: Auto-generates `.aider.model.metadata.json` with correct limits

### Python Migration & Multi-Provider Refactoring (2026-01-14)
- ✅ **Full Python rewrite**: Migrated from Bash to Python for better maintainability
- ✅ **Package rename**: From "linode-llm-coder" to "maider" (multi-provider architecture)
- ✅ **Provider abstraction**: CloudProvider interface with LinodeProvider implementation
- ✅ **Backward compatibility**: `maider` command alias, automatic session migration
- ✅ **Linode SDK integration**: No more manual API parameter fixes (interfaces, root_pass, etc.)
- ✅ **Rich terminal UI**: Colored output, tables, progress spinners
- ✅ **Modular architecture**: Type-safe, testable, extensible codebase
- ✅ **Validation commands**: `maider check` and `maider validate-perf` for GPU monitoring
- ✅ **GPU region validation**: Wizard and validate commands enforce 12 GPU-capable regions
- ✅ **Easy installation**: One-command setup with `./install-python-coder.sh`

## Multi-Card GPU Support

### How Tensor Parallelism Works

vLLM's tensor parallelism splits model layers across multiple GPUs:
- Each GPU holds a portion of each layer
- GPUs communicate via NCCL during forward passes
- Requires all GPUs to be identical (same model, same memory)
- Linear VRAM scaling: 2 GPUs ≈ 2x VRAM, 4 GPUs ≈ 4x VRAM

### When to Use Multi-GPU

Use multi-GPU configurations when:
- Model size exceeds single GPU VRAM (e.g., 70B+ models)
- You need larger context windows with 30B+ models
- Running full-precision models instead of quantized versions

**Cost consideration**: Multi-GPU instances are significantly more expensive. Try quantized models on single GPUs first (AWQ, GPTQ, GGUF).

## Linode Multi-GPU Instance Types

### Available Multi-GPU Types

| Linode TYPE | GPUs | VRAM per GPU | Total VRAM | Recommended For |
|-------------|------|--------------|------------|-----------------|
| `g1-gpu-rtx6000-2` | 2x RTX 6000 Ada | 48GB | 96GB | 70B models, large context |
| `g1-gpu-rtx6000-4` | 4x RTX 6000 Ada | 48GB | 192GB | 70B+ full precision, massive context |
| `g2-gpu-rtx4000a2-s` | 2x RTX 4000 Ada | 20GB | 40GB | 30B models with moderate context |

### GPU Region Restrictions (as of 2026-01)

**Important**: GPUs are only available in specific Linode regions. The launcher enforces these restrictions to prevent deployment failures.

#### GPU-Capable Regions

GPUs are available in **12 regions** with two GPU types:

**RTX 4000 Ada regions** (20GB VRAM per GPU):
- `us-ord` - Chicago, IL
- `us-sea` - Seattle, WA
- `de-fra-2` - Frankfurt 2, Germany *(different from eu-central)*
- `fr-par` - Paris, France
- `in-bom-2` - Mumbai 2, India *(different from ap-west)*
- `sg-sin-2` - Singapore 2 *(different from ap-south)*
- `jp-osa` - Osaka, Japan

**RTX 6000 Ada regions** (48GB VRAM per GPU):
- `us-east` - Newark, NJ
- `us-southeast` - Atlanta, GA
- `eu-central` - Frankfurt, Germany *(older region)*
- `ap-west` - Mumbai, India *(older region)*
- `ap-south` - Singapore *(older region)*

**Source**: [Linode GPU documentation](https://www.linode.com/docs/products/compute/compute-instances/plans/gpu/)

## Configuration Example

70B Model on 2x RTX 6000:

```bash
# .env
HUGGING_FACE_HUB_TOKEN=hf_xxx
FIREWALL_ID=243627
REGION=us-east
TYPE=g1-gpu-rtx6000-2
MODEL_ID=Qwen/Qwen2.5-72B-Instruct-AWQ
SERVED_MODEL_NAME=coder-70b

# Multi-GPU configuration
VLLM_TENSOR_PARALLEL_SIZE=2
VLLM_MAX_MODEL_LEN=32768
VLLM_GPU_MEMORY_UTILIZATION=0.90
VLLM_MAX_NUM_SEQS=1
```

## Compose Runtime Options

The VM uses a generated `/opt/llm/docker-compose.yml` backed by a local `/opt/llm/.env`.
You can tune deployment behavior via `.env` values before provisioning:

- `ENABLE_OPENWEBUI=true|false` to include or omit Open WebUI.
- `ENABLE_HF_CACHE=true|false` to persist HuggingFace cache on disk.
- `ENABLE_HEALTHCHECKS=true|false` to add container health checks.
- `ENABLE_NCCL_ENV=true|false` to set NCCL reliability env vars.
- `VLLM_IMAGE`, `OPENWEBUI_IMAGE`, `VLLM_PORT`, `WEBUI_PORT` for image/port overrides.

## Best Practices

### Memory Planning

1. **Calculate Model Memory Requirements**:
   - FP16/BF16: `params × 2 bytes`
   - AWQ/GPTQ (4-bit): `params × 0.5 bytes`
   - Add 20-30% overhead for KV cache and activations

2. **Set Conservative Memory Utilization**:
   - Start with `VLLM_GPU_MEMORY_UTILIZATION=0.85`
   - Increase gradually if stable (max 0.92)
   - Multi-GPU setups can be more sensitive to OOM

3. **Context Length Tuning**:
   - Start with smaller `VLLM_MAX_MODEL_LEN`
   - Increase gradually while monitoring GPU memory

### Performance Optimization

1. **Always Set Tensor Parallel Size**: `VLLM_TENSOR_PARALLEL_SIZE=<number_of_gpus>` must match GPU count
2. **Minimize Inter-GPU Communication**: Use `VLLM_MAX_NUM_SEQS=1` for coding tasks
3. **Enable Advanced Features**: `VLLM_EXTRA_ARGS=--enable-prefix-caching`

### Debugging Multi-GPU Issues

```bash
# Check GPU Detection
ssh root@"$IP" 'nvidia-smi'

# Monitor GPU Memory
ssh root@"$IP" 'watch -n 1 nvidia-smi'

# Check vLLM Logs
ssh root@"$IP" 'docker logs $(docker ps --format "{{.Names}}" | head -n1)'

# Verify NCCL Communication
# vLLM will fail to start if GPUs can't communicate. Check logs for NCCL errors.
```

## Getting Started

### Python CLI (Recommended)

**Installation:**
```bash
./install-python-coder.sh
source venv/bin/activate
```

**Quick Start:**
```bash
maider validate    # Validate configuration
maider up          # Create VM
maider list        # List VMs
maider check       # Check GPU health
maider down        # Destroy VM
```

**Available Commands:**
- `maider up [name]` - Create and configure VM
- `maider down [session]` - Destroy VM
- `maider list` - List all active VMs
- `maider list-types [--region <region>] [--refresh]` - List GPU types from API
- `maider status [session]` - Show VM details
- `maider use <session>` - Switch to a different session
- `maider tunnel [session]` - Re-establish SSH tunnel after network drop
- `maider switch-model <model-id> [session]` - Switch model on running VM
- `maider validate` - Validate .env configuration
- `maider check [session]` - Quick GPU health check (~30sec)
- `maider validate-perf [session]` - Comprehensive validation (~5min)
- `maider cleanup [--session <name>] [--force]` - Remove stale sessions
- `maider extend [session]` - Reset watchdog idle timer
- `maider wizard` - Interactive setup wizard

**Documentation:**
- [docs/PYTHON-MIGRATION.md](docs/PYTHON-MIGRATION.md) - Migration guide
- [docs/VALIDATION-COMMANDS.md](docs/VALIDATION-COMMANDS.md) - Validation quick reference
- [docs/VALIDATION-GUIDE.md](docs/VALIDATION-GUIDE.md) - Comprehensive validation guide

### Bash Script (Legacy)

The bash version (`maider`) is still functional but requires manual API fixes for Linode changes.

**Available Commands:**
- `./maider up` - Create VM
- `./maider down` - Destroy VM
- `./maider list` - List VMs
- `./quick-gpu-check.sh` - Quick GPU check (replaced by `maider check`)
- `./validate-multigpu-perf.sh` - Full validation (replaced by `maider validate-perf`)

## Interactive Setup Wizard

The `maider wizard` command provides a guided setup experience with dynamic API queries.

**Quick Start:**
```bash
maider wizard
```

**Wizard Flow:**

1. **Capability Selection** - Choose model size (7B-14B, 30B-32B, 70B+, or custom)
2. **Region Selection** - Pick from GPU-capable regions (dynamically queried)
3. **VM Type Selection** - Select hardware (filters by region and VRAM requirements)
4. **Model Configuration** - Choose model and context length

The wizard caches API responses in `/tmp/` with a 1-hour TTL and supports 1Password CLI references.

## Runtime GPU Type Enumeration

The launcher queries GPU types and regions directly from the Linode API at runtime, ensuring accurate and up-to-date hardware availability.

**Benefits:**
- Always reflects current Linode GPU offerings
- No manual updates needed when new GPU types are added
- Accurate region-specific availability
- Automatic price updates

**How it works:**
1. API queries are cached for 1 hour to minimize API calls
2. Falls back to hardcoded data if API is unavailable
3. Cross-references regions with "GPU Linodes" capability
4. Determines type availability based on GPU model (RTX 4000 vs RTX 6000)

**List available GPU types:**
```bash
maider list-types              # Show all GPU types
maider list-types --region de-fra-2  # Filter by region
maider list-types --refresh    # Force refresh from API
```

**Example output:**
```
┌──────────────────┬────────────────────┬──────┬──────────┬────────────┬───────────┬─────────────┐
│ Type ID          │ Name               │ GPUs │ VRAM/GPU │ Total VRAM │ Cost/Hour │ Regions     │
├──────────────────┼────────────────────┼──────┼──────────┼────────────┼───────────┼─────────────┤
│ g2-gpu-rtx4000a1-s │ RTX 4000 Ada (20GB) │    1 │    20GB │      20GB │     $0.52 │ us-ord, ... │
│ g2-gpu-rtx4000a2-s │ 2x RTX 4000 Ada... │    2 │    20GB │      40GB │     $1.04 │ us-ord, ... │
└──────────────────┴────────────────────┴──────┴──────────┴────────────┴───────────┴─────────────┘
```

## Workflow: Multi-GPU Setup

### 1. Configure Environment

```bash
cat > .env <<EOF
REGION=us-east
TYPE=g1-gpu-rtx6000-2
MODEL_ID=Qwen/Qwen2.5-72B-Instruct-AWQ
VLLM_TENSOR_PARALLEL_SIZE=2
VLLM_MAX_MODEL_LEN=32768
EOF
```

### 2. Create and Use VM

```bash
source venv/bin/activate
maider up                        # Create VM (10-20 min first boot)
source .aider-env
aider --model "$AIDER_MODEL"    # Use with aider
```

### 3. Validate Setup

```bash
maider check                     # Quick health check
maider validate-perf             # Comprehensive validation
```

### 4. Clean Up

```bash
maider down  # Shows session summary with runtime and total cost
```

## Troubleshooting

### Self-Healing Mechanism

The launcher automatically detects and fixes common issues:

| Error Type | Detection Pattern | Automatic Fix |
|------------|------------------|---------------|
| OOM/CUDA memory | `out of memory`, `OOM`, `CUDA error` | Reduces `--gpu-memory-utilization` by 5%; halves `--max-model-len` on 2nd+ retry |
| NCCL multi-GPU | `NCCL`, `collective`, `all_reduce` | Adds `NCCL_DEBUG=WARN`, `NCCL_IB_DISABLE=1`, `NCCL_P2P_DISABLE=0` |
| Tensor parallelism | `tensor.parallel`, `tp_size`, `world_size` | Adjusts TP size to match detected GPUs |
| Model loading | `RuntimeError`, `architecture`, `not supported` | Removes explicit `--dtype` setting |

Invoked up to 3 times during `maider up`, `_resume_readiness_check()`, and once during `maider fix`.

### Common Issues

**OOM on Multi-GPU**
- Self-healing reduces memory utilization and max-model-len automatically
- If fails after 3 retries: reduce `VLLM_MAX_MODEL_LEN` (try 50%), lower `VLLM_GPU_MEMORY_UTILIZATION` to 0.85, try FP8 KV cache

**Tensor Parallelism Not Initializing**
- Self-healing adjusts `--tensor-parallel-size` to match GPU count
- Manually verify: check all GPUs visible with `nvidia-smi`, review vLLM logs for NCCL errors

**Aider Token Limit Error (0 of 0 tokens)**
- The launcher auto-generates `.aider.model.metadata.json` based on `VLLM_MAX_MODEL_LEN`
- If missing, run `maider up` again or manually create the file

## Cost Optimization

### Development Workflow

1. **Develop on Single GPU**: Use smaller model (`TYPE=g2-gpu-rtx4000a1-s`)
2. **Test on Multi-GPU**: Switch to production model (`TYPE=g1-gpu-rtx6000-2`, `VLLM_TENSOR_PARALLEL_SIZE=2`)
3. **Destroy Immediately**: Multi-GPU instances are expensive (`./maider down`)

### Cost Comparison

| Configuration | GPUs | Hourly Cost | Daily Cost (24h) |
|---------------|------|-------------|------------------|
| RTX 4000 Ada (single) | 1 | ~$1.50 | ~$36 |
| RTX 6000 Ada (single) | 1 | ~$2.50 | ~$60 |
| RTX 6000 Ada (dual) | 2 | ~$5.00 | ~$120 |
| RTX 6000 Ada (quad) | 4 | ~$10.00 | ~$240 |

## Automation & Security Features

### 1Password CLI Integration

```bash
# Install
brew install 1password-cli  # macOS
op signin

# Reference in .env.secrets
HUGGING_FACE_HUB_TOKEN=op://Private/HuggingFace/token
```

The launcher automatically resolves `op://` references using `op read`.

### Auto-Ready Detection

The `maider up` command checks:
1. SSH Connectivity (max 20 min)
2. Tunnel Setup (automatic SSH ControlMaster)
3. vLLM API response
4. Model loading verification
5. API validation with test completion

### Intelligent Port Management

Automatically finds available ports if 3000/8000 are in use. Ports stored in `.aider-env`.

### SSH ControlMaster

Persistent tunnels that survive brief network interruptions. Automatically cleaned up on VM destruction.

```bash
# Setup (automatic in maider up)
ssh -fNM -o ControlPath=~/.ssh/llm-master-%r@%h:%p \
  -L 3000:localhost:3000 -L 8000:localhost:8000 root@"$IP"

# Reconnect after network drop
maider tunnel [session]
```

### Cost Tracking

Hourly rates (as of 2026-01):

**RTX 4000 Ada types** (available in: us-ord, de-fra-2, in-bom-2, jp-osa, fr-par, us-sea, sg-sin-2):
- `g2-gpu-rtx4000a1-s`: $0.52/hour (1 GPU, 20GB VRAM)
- `g2-gpu-rtx4000a2-s`: $1.04/hour (2 GPUs, 40GB VRAM)
- `g2-gpu-rtx4000a4-m`: $2.08/hour (4 GPUs, 80GB VRAM)

**RTX 6000 Ada types** (available in: us-east, us-southeast, eu-central, ap-west, ap-south):
- `g1-gpu-rtx6000-1`: $1.50/hour (1 GPU, 48GB VRAM)
- `g1-gpu-rtx6000-2`: $3.00/hour (2 GPUs, 96GB VRAM)
- `g1-gpu-rtx6000-3`: $4.50/hour (3 GPUs, 144GB VRAM)
- `g1-gpu-rtx6000-4`: $6.00/hour (4 GPUs, 192GB VRAM)

Displayed before creation, during session (`$HOURLY_COST`), and after destruction.

### VM Monitoring with nvtop

Pre-installed on all VMs. Shows GPU utilization, memory, processes, temperature, and power draw.

```bash
ssh root@"$IP"
nvtop  # Monitor all GPUs in real-time
```

## Cross-Platform Compatibility

**SSH Key Detection**: Tries `~/.ssh/id_ed25519.pub` → `id_rsa.pub` → `id_ecdsa.pub`

**Platform-Specific**:
- Port detection: `lsof` (macOS) or `netstat` (Linux)
- sed in-place: `sed -i ''` (macOS BSD) or `sed -i` (Linux GNU)

**Tested**: macOS Ventura+, Ubuntu 22.04+, Debian 11+

## Security Best Practices

**Credential Storage:**
- ✅ Use `.env.secrets` for tokens (git-ignored)
- ✅ Use 1Password CLI references (`op://`)
- ✅ Set `chmod 600 .env.secrets`

**VM Security:**
- Services bound to `127.0.0.1` (not public)
- Access via SSH tunnel only
- Token stored in `/opt/llm/.env` with mode 0600
- Firewall allows SSH only

## Continuous Integration

The repository includes CI/CD via GitHub Actions (`.github/workflows/lint-and-test.yml`):

**Automated Checks**: ShellCheck, Bash syntax, executable permissions, preset validation, multi-GPU validation, documentation check, security checks, cross-platform tests

**Triggers**: Push to `main` or `claude/*` branches, PRs targeting `main`

**Local Testing**: `shellcheck coder.sh presets/use-preset.sh` and `bash -n coder.sh`

## Performance Benchmarking System

### Overview

The comprehensive benchmarking system helps you choose the optimal GPU configuration and model for your specific use case. It collects performance data incrementally across all 7 GPU configurations (RTX 4000/6000, 1-4 GPUs) and provides data-driven recommendations.

**Key Features**:
- **Incremental Collection**: Build benchmark database over time as you use different configs
- **12 Test Prompts**: Across 3 categories (coding, context-heavy, reasoning)
- **Centralized Database**: Store and query results at `~/.cache/linode-vms/benchmark-database.json`
- **Smart Recommendations**: Interactive wizard suggests optimal configs based on your needs
- **Cost Analysis**: Tracks tokens/sec, cost per 1K tokens, and cost efficiency

**Architecture**:
- `benchmark_db.py` - Database with file locking and query support
- `benchmark_models.py` - Smart model selection based on VRAM (7B-70B models)
- `recommendations.py` - Recommendation engine with cost efficiency scoring
- New commands: `benchmark-collect`, `benchmark-compare`, `benchmark-status`, `recommend`

### Test Suite

**12 prompts across 3 categories:**

#### Coding Tasks (4 prompts)
1. Simple function (100 tokens)
2. Code review (200 tokens)
3. Algorithm explanation (400 tokens)
4. Complex refactoring (500 tokens)

#### Context-Heavy Tasks (4 prompts)
5. Multi-file code analysis (800 tokens) - Large context
6. Refactor with context (1000 tokens) - Tests max_model_len impact
7. Debug trace analysis (600 tokens)
8. Architecture explanation (800 tokens)

#### Reasoning Tasks (4 prompts)
9. Problem decomposition (300 tokens)
10. Design trade-offs analysis (400 tokens)
11. Algorithmic optimization reasoning (500 tokens)
12. System design (600 tokens)

### Commands

#### `maider benchmark` (Enhanced)
Run benchmark with category filtering and database integration.

```bash
# Run all tests (saves to database by default)
maider benchmark

# Run specific category
maider benchmark --category coding
maider benchmark --category context_heavy
maider benchmark --category reasoning

# Skip database saving
maider benchmark --no-db

# Custom output file
maider benchmark -o my-results.json
```

**New flags**:
- `--category` / `-c`: Filter by task category (all, coding, context_heavy, reasoning)
- `--save-to-db` / `--no-db`: Control database saving (default: saves to DB)

#### `maider benchmark-collect`
Simplified command for quick data collection.

```bash
# Benchmark current session
maider benchmark-collect

# Benchmark specific session
maider benchmark-collect my-session

# Only run coding tests
maider benchmark-collect --category coding
```

**What it does**:
- Auto-detects GPU configuration
- Runs appropriate benchmark tests
- Saves results to centralized database
- Displays summary results

#### `maider benchmark-compare`
Compare results across all configurations.

```bash
# Show all results
maider benchmark-compare

# Filter by GPU type
maider benchmark-compare --gpu-type g1-gpu-rtx6000-2

# Filter by task category
maider benchmark-compare --task-category coding

# Sort by cost
maider benchmark-compare --sort-by cost_per_1k_tokens

# Export to CSV
maider benchmark-compare --format csv -o results.csv

# Export to Markdown
maider benchmark-compare --format markdown -o results.md
```

**Comparison Table Shows**:
- GPU Type and configuration
- Model used
- Tokens/sec (throughput)
- Cost per 1K tokens
- Hourly cost
- Cost efficiency (tokens/sec per $/hour)
- Tests passed/total

#### `maider recommend`
Interactive recommendation wizard.

```bash
maider recommend
```

**Interactive prompts**:
1. **Task type**: Coding / Context-heavy / Reasoning / Mixed
2. **Budget constraint**: Under $1/hr / $1-$3/hr / Over $3/hr / No constraint
3. **Model size preference**: Smallest viable / Balanced / Largest available

**Output**:
- Top 3 ranked recommendations
- Performance metrics (tokens/sec, cost/1K)
- Confidence level (High/Medium/Low based on # of runs)
- Warnings for low-confidence recommendations

**Ranking factors**:
1. Data confidence (more runs = higher priority)
2. Cost efficiency (tokens/sec per dollar)
3. Model size preference
4. Performance (tokens/sec)

#### `maider benchmark-status`
Show coverage and gaps in benchmark data.

```bash
maider benchmark-status
```

**Displays**:
- Total benchmarks and GPU types tested
- Tested configurations with run counts
- Last benchmark date (flags stale data > 30 days)
- Missing GPU types
- Confidence levels breakdown (High/Medium/Low)
- Suggestions for improving coverage

### Metrics

**Primary Metrics**:
- **Throughput**: tokens/sec (higher is better)
- **Cost per 1K tokens**: $/1K tokens (lower is better)
- **Cost efficiency**: tokens/sec ÷ hourly_cost (higher is better)

**Confidence Levels**:
- **High (3+ runs)**: Green - Reliable data
- **Medium (2 runs)**: Yellow - Limited data
- **Low (1 run)**: Red - Single benchmark, results may vary

### Database Schema

Location: `~/.cache/linode-vms/benchmark-database.json`

```json
{
  "version": "1.0",
  "benchmarks": [
    {
      "id": "uuid",
      "timestamp": "ISO format",
      "gpu_type": "g1-gpu-rtx6000-2",
      "gpu_count": 2,
      "vram_per_gpu": 48,
      "total_vram": 96,
      "hourly_cost": 3.00,
      "model_id": "Qwen/Qwen2.5-72B-Instruct-AWQ",
      "model_category": "70b",
      "vllm_config": {
        "tensor_parallel_size": 2,
        "max_model_len": 32768,
        "gpu_memory_utilization": 0.90
      },
      "results_by_category": {
        "coding": {"avg_tokens_per_sec": 45.3},
        "context_heavy": {"avg_tokens_per_sec": 42.1},
        "reasoning": {"avg_tokens_per_sec": 43.7}
      },
      "summary": {
        "avg_tokens_per_sec": 43.7,
        "cost_per_1k_tokens": 0.0242,
        "tests_passed": 12,
        "tests_total": 12
      },
      "tests": []
    }
  ]
}
```

**Features**:
- File locking for concurrent access (fcntl)
- Atomic writes (temp file + rename)
- Query filters (GPU type, model category, task category)
- Export to JSON, CSV, Markdown

### Model Selection Matrix

Auto-selects appropriate models based on VRAM capacity:

| VRAM Range | Model Category | Example Models |
|------------|---------------|----------------|
| 20GB (RTX4000x1) | 7b-14b | Qwen2.5-Coder-14B-Instruct-AWQ |
| 40GB (RTX4000x2) | 30b | Qwen2.5-Coder-32B-Instruct-AWQ |
| 48GB (RTX6000x1) | 30b | Qwen2.5-Coder-32B-Instruct |
| 80GB (RTX4000x4) | 70b | Qwen2.5-72B-Instruct-AWQ (general) |
| 96GB (RTX6000x2) | 70b | Qwen2.5-72B-Instruct-AWQ (general) |
| 144GB (RTX6000x3) | 70b-full | Qwen2.5-72B-Instruct (full, general) |
| 192GB (RTX6000x4) | 70b-full | Qwen2.5-72B-Instruct (full, general) |

**Prioritization**:
- Quantized models (AWQ/GPTQ) preferred for efficiency (90%+ quality at 25% VRAM)
- Largest model that fits comfortably
- Popular/well-tested models (Qwen, DeepSeek)

### Example Workflow

#### 1. Collect Data Over Time
```bash
# Create VM with RTX 6000 x2 + 70B model
maider up

# Benchmark it
maider benchmark-collect
# → Auto-detects: RTX 6000 x2, 96GB VRAM
# → Runs 12 tests across 3 categories
# → Saves to database

# Later, try RTX 4000 x2 + 32B model
maider up  # With different config

# Benchmark it
maider benchmark-collect
# → Adds second configuration to database
```

#### 2. Compare Configurations
```bash
maider benchmark-compare --task-category coding

# Output:
# ┌──────────┬──────┬──────┬────────┬────────────┬──────────┬─────────┬────────────┐
# │ GPU Type │ GPUs │ VRAM │ Model  │ Tokens/Sec │ Cost/1K  │ $/Hour  │ Efficiency │
# ├──────────┼──────┼──────┼────────┼────────────┼──────────┼─────────┼────────────┤
# │ RTX6000x2│  2   │ 96GB │ 70B-AWQ│    45.3    │ $0.0242  │  $3.00  │    15.1    │
# │ RTX4000x2│  2   │ 40GB │ 32B-AWQ│    38.1    │ $0.0178  │  $1.04  │    36.6    │
# └──────────┴──────┴──────┴────────┴────────────┴──────────┴─────────┴────────────┘
```

#### 3. Get Recommendations
```bash
maider recommend

# Interactive:
# What's your primary task type?
#   1) Coding
#   2) Context-heavy tasks
#   3) Reasoning
#   4) Mixed workload
# Choice [1-4]: 1
#
# What's your budget constraint?
#   1) Under $1/hour
#   2) $1-$3/hour
#   3) Over $3/hour
#   4) No constraint
# Choice [1-4]: 2
#
# What model size preference?
#   1) Smallest viable (best value for money)
#   2) Balanced (good performance and cost)
#   3) Largest available (maximum capability)
# Choice [1-3]: 2

# Output:
# ╭─ Top 3 Recommendations for Coding Tasks ─╮
# │                                           │
# │ 1. RTX 6000 Ada x2 + Qwen 70B-AWQ        │
# │    • 45.3 tokens/sec                      │
# │    • $0.0242/1K tokens                    │
# │    • $3.00/hour                           │
# │    • Confidence: High (3 runs)            │
# │                                           │
# │ 2. RTX 4000 Ada x2 + Qwen 32B-AWQ        │
# │    • 38.1 tokens/sec                      │
# │    • $0.0178/1K tokens                    │
# │    • $1.04/hour                           │
# │    • Confidence: Medium (2 runs)          │
# ╰───────────────────────────────────────────╯
```

#### 4. Check Coverage
```bash
maider benchmark-status

# Summary:
#   Total benchmarks: 5
#   GPU types tested: 2/7
#   Unique configurations: 2
#
# Tested Configurations:
# ┌───────────┬───────┬──────┬─────────────┬─────────────┐
# │ GPU Type  │ Model │ Runs │ Last Run    │ Status      │
# ├───────────┼───────┼──────┼─────────────┼─────────────┤
# │ RTX6000x2 │ 70B   │  3   │ 2 hours ago │ ✓ Good      │
# │ RTX4000x2 │ 30B   │  2   │ 1 day ago   │ ⚠ Limited   │
# └───────────┴───────┴──────┴─────────────┴─────────────┘
#
# Missing GPU Types:
#   ✗ RTX 4000 Ada x1 (20GB, $0.52/hr)
#   ✗ RTX 4000 Ada x4 (80GB, $2.08/hr)
#   ✗ RTX 6000 Ada x1 (48GB, $1.50/hr)
#   ...
```

### Cost Analysis Example

Based on real benchmarks, you might find:

**Best Value** (Coding Tasks):
- RTX 4000 x2 + Qwen 32B-AWQ
- 38 tokens/sec, $0.018/1K tokens, $1.04/hour
- Cost efficiency: 36.6 tokens/sec per $/hour

**Best Performance** (Coding Tasks):
- RTX 6000 x4 + Qwen 70B-AWQ
- 52 tokens/sec, $0.029/1K tokens, $6.00/hour
- Cost efficiency: 8.7 tokens/sec per $/hour

**Best Balanced** (Coding Tasks):
- RTX 6000 x2 + Qwen 70B-AWQ
- 45 tokens/sec, $0.024/1K tokens, $3.00/hour
- Cost efficiency: 15.1 tokens/sec per $/hour

### Backward Compatibility

The original `maider benchmark` command works exactly as before:
- Still saves to `.benchmark-results.json`
- Now also saves to database (unless `--no-db` specified)
- Category filtering is optional (defaults to "all")
- All existing scripts continue to work

### Future Enhancements

- Web dashboard for visualizing benchmark data
- Community benchmarks (optional anonymous upload)
- Model-specific vLLM config tuning
- Quality metrics beyond speed (perplexity, code correctness)
- Multi-provider support (DigitalOcean, Scaleway GPUs)

## Multi-VM Session Management

### Architecture

```
~/.cache/linode-vms/
├── qwen32b-20260114-143022/
│   ├── state              # VM metadata (linode_id, ip, cost, etc.)
│   ├── aider-env          # Session-specific environment
│   ├── watchdog.pid       # Watchdog process ID
│   └── last_activity      # Timestamp of last API request
```

### Session Commands

| Command | Description |
|---------|-------------|
| `maider up [name]` | Create VM with auto-generated or custom name |
| `maider list` | List all sessions with status and costs |
| `maider use <session>` | Switch to a session (updates `.aider-env` symlink) |
| `maider status [session]` | Show detailed session status |
| `maider tunnel [session]` | Re-establish SSH tunnel after network drop |
| `maider switch-model <model> [session]` | Switch to different model on running VM |
| `maider down [session]` | Destroy session (validates API token first) |
| `maider cleanup` | Remove stale sessions (VMs that no longer exist) |
| `maider cleanup --session <name> --force` | Force-remove local state after manual VM deletion |
| `maider extend [session]` | Reset watchdog idle timer |

### Session Naming

Auto-named based on model and timestamp (e.g., `qwen32b-20260114-143022`) or provide custom name.

### State Files

| File | Purpose |
|------|---------|
| `state` | VM metadata: linode_id, ip, type, hourly_cost, status |
| `aider-env` | Exportable environment variables for aider |
| `watchdog.pid` | PID of watchdog process (if enabled) |
| `watchdog-state` | Watchdog configuration |
| `last_activity` | Unix timestamp of last detected activity |

### Switching Models

Switch to a different model on a running VM without destroying it:

```bash
maider switch-model Qwen/Qwen2.5-Coder-14B-Instruct-AWQ
maider switch-model Qwen/Qwen2.5-72B-Instruct my-session
```

**What happens**: Generates new docker-compose.yml, uploads via SSH, restarts vLLM container, waits for model download (10-20 min), updates local metadata.

**Cost savings**: Avoid destroying/recreating VM, keep hardware and config, model cache persists.

### SSH Tunnel Reconnection

If connection drops or machine restarts:

```bash
maider tunnel              # Reconnect to current session
maider tunnel my-session   # Reconnect to specific session
```

### Orphaned VM Cleanup

If VM deletion fails (missing API token, network error), clean up local state:

```bash
maider cleanup                              # Automatic cleanup of all stale sessions
maider cleanup --session my-session         # Clean specific session (checks if VM exists)
maider cleanup --session my-session --force # Force-remove without checking VM
```

**Safety**: `maider down` validates API token BEFORE deleting local state. If deletion fails, state is preserved.

## Client-Side Watchdog (Auto-Destroy)

Automatically destroys idle VMs to prevent forgotten instances. API token never leaves your machine.

**Why Client-Side?** Linode API tokens are scoped by resource TYPE. A compromised VM could delete ALL Linodes. Client-side keeps token secure.

**Enable in .env:**
```bash
WATCHDOG_ENABLED=true
WATCHDOG_TIMEOUT_MINUTES=30      # Default: 30 minutes
WATCHDOG_WARNING_MINUTES=5       # Warning before destruction
```

**How it works:**
1. Background process starts after `maider up`
2. Checks vLLM API logs via SSH every 60 seconds
3. Resets idle timer on activity detection
4. After timeout: sends desktop notification (5 min before), destroys VM, cleans up session

**Commands:**
- `maider extend [session]` - Reset idle timer
- `maider status [session]` - Show watchdog status and idle time

**Notifications**: macOS (`osascript`), Linux (`notify-send`), optional ntfy.sh webhook

**Cost Savings Example**: Without watchdog: 8h idle = $24 wasted. With 30-min watchdog: $1.50 total.

## Python vs Bash Feature Comparison

### ✅ Fully Migrated to Python

VM Creation, Destruction, List, Status, Validation, GPU Checks, Session Management, SSH Tunnels, Cost Tracking, 1Password Integration, Interactive Wizard, Watchdog, Cloud-init Check, vLLM Readiness Check, Auto-launch Aider, Performance Benchmarking - all working in Python.

### ⏳ Future Enhancements

Comprehensive multi-GPU/multi-model benchmark suite (`maider benchmark-all`) - planned for future release.

## Recommendation

**For new users:**
1. Install Python version: `./install-python-coder.sh`
2. Run interactive wizard: `maider wizard`
3. Deploy with all features: `maider up --launch-aider`
4. Enable watchdog in `.env` for auto-destroy

**For existing users:** Python version is now feature-complete. Recommend switching entirely.

## Documentation Files

| File | Purpose |
|------|---------|
| `README.md` | Quick start guide and command reference |
| `CLAUDE.md` | Main technical documentation (this file) |
| `docs/ADDING-PROVIDERS.md` | Guide for adding new cloud providers |
| `docs/PYTHON-MIGRATION.md` | Migration guide from bash to Python |
| `docs/NEW-FEATURES.md` | Wizard, readiness checks, auto-launch, watchdog |
| `docs/VALIDATION-COMMANDS.md` | Validation quick reference |
| `docs/VALIDATION-GUIDE.md` | Comprehensive validation guide |
| `docs/CLOUD-INIT-DESIGN.md` | VM initialization architecture |
| `docs/MIGRATION-COMPLETE.md` | Feature parity and migration status |

## Future Roadmap

**Next Up:**
- Complete multi-provider support (DigitalOcean, Scaleway)
- Add comprehensive benchmark-all command for GPU/model comparison
- Add web dashboard for multi-VM management
- Improve watchdog with better activity detection

**Medium-term:**
- Add Slack/Discord notifications
- Add Prometheus metrics export
- Add cost alerts and budgets
- Support custom cloud-init scripts
- Expand to more cloud providers (AWS, GCP, Azure)

**Long-term:**
- Support other LLM servers (Ollama, text-generation-inference)
- Add distributed training support
- Add model fine-tuning workflows
- Multi-cloud provider load balancing

---

**Last Updated:** 2026-01-14
