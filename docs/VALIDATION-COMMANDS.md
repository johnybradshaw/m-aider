# Validation Commands - Quick Reference

The validation scripts have been ported to Python and integrated into the `coder` CLI.

## Quick Start

```bash
# Activate environment
source venv/bin/activate

# Quick health check (30 seconds)
coder check

# Comprehensive validation (5 minutes)
coder validate-perf
```

## Commands

### `coder check` - Quick GPU Health Check

**What it does:**
- ✅ Shows GPU memory usage for all GPUs
- ✅ Validates tensor parallelism is working
- ✅ Runs a quick throughput test
- ⏱️ Takes ~30 seconds

**When to use:**
- After creating a new VM
- During development to verify GPUs are active
- Quick sanity check before important work

**Example:**
```bash
$ coder check

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Quick Multi-GPU Health Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GPU Memory Usage:
┏━━━━━━┳━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┓
┃ GPU  ┃ Name          ┃ Memory Used ┃ Memory Total┃ Usage %┃
┡━━━━━━╇━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━┩
│ GPU 0│ RTX 4000 Ada  │ 18234 MB    │ 20470 MB    │ 89%    │
│ GPU 1│ RTX 4000 Ada  │ 18156 MB    │ 20470 MB    │ 89%    │
│ GPU 2│ RTX 4000 Ada  │ 18201 MB    │ 20470 MB    │ 89%    │
│ GPU 3│ RTX 4000 Ada  │ 18189 MB    │ 20470 MB    │ 89%    │
└──────┴───────────────┴─────────────┴─────────────┴────────┘

Multi-GPU Status:
  ✓ All 4 GPUs are active with similar memory usage

Quick Throughput Test:
  ✓ Generated 98 tokens in 2.3s (42.6 tok/s)
```

### `coder validate-perf` - Comprehensive Performance Validation

**What it does:**
- ✅ GPU hardware and topology validation
- ✅ Tensor parallelism configuration check
- ✅ Memory distribution analysis
- ✅ NCCL communication validation
- ✅ Live performance tests (3 prompt sizes)
- ✅ Configuration recommendations
- ⏱️ Takes ~5 minutes

**When to use:**
- Troubleshooting performance issues
- After configuration changes
- Before production deployment
- When GPUs appear idle

**Example:**
```bash
$ coder validate-perf

╭───────────────────────────────────────╮
│ 1. GPU Hardware Validation           │
╰───────────────────────────────────────╯

✓ Found 4 GPU(s)

GPU Details:
  GPU 0: NVIDIA RTX 4000 Ada | 20470 MB
  GPU 1: NVIDIA RTX 4000 Ada | 20470 MB
  GPU 2: NVIDIA RTX 4000 Ada | 20470 MB
  GPU 3: NVIDIA RTX 4000 Ada | 20470 MB

... (full validation output)

╭───────────────────────────────────────╮
│ Validation Summary                    │
╰───────────────────────────────────────╯

✓ All GPUs are active: Tensor parallelism is working
✓ No NCCL errors: Inter-GPU communication is healthy
✓ Average throughput: 41.8 tok/s: Performance is normal
```

## What They Check

| Check | `coder check` | `coder validate-perf` |
|-------|---------------|----------------------|
| GPU count | ✅ | ✅ |
| GPU memory usage | ✅ | ✅ |
| Tensor parallelism | ✅ | ✅ |
| Throughput test | 1 test | 3 tests |
| GPU topology | ❌ | ✅ |
| vLLM logs analysis | ❌ | ✅ |
| NCCL errors | ❌ | ✅ |
| Configuration review | ❌ | ✅ |
| Duration | ~30 sec | ~5 min |

## Common Issues Detected

### ✗ GPUs Appear Idle
```
✗ 3 of 4 GPUs appear idle
  → Tensor parallelism may not be configured correctly
```

**Fix:**
```bash
# Check VLLM_TENSOR_PARALLEL_SIZE in .env
coder validate

# Update if needed
VLLM_TENSOR_PARALLEL_SIZE=4

# Recreate VM
coder down && coder up
```

### ✗ NCCL Errors
```
✗ NCCL errors detected:
  NCCL WARN Call to ibv_create_qp failed
```

**Fix:**
Add to `.env`:
```bash
VLLM_EXTRA_ARGS=--tensor-parallel-size 4
# Also add NCCL env vars to docker-compose
```

### ✗ Low Throughput
```
⚠ Generated 100 tokens in 8.2s (12.2 tok/s)
```

**Fix:**
```bash
# Reduce memory pressure
VLLM_GPU_MEMORY_UTILIZATION=0.85
VLLM_MAX_MODEL_LEN=16384
```

## Workflow

### Initial Setup
```bash
coder up              # Create VM
sleep 900             # Wait 15 minutes for model to load
coder check           # Quick validation
```

### Troubleshooting
```bash
coder check           # See the problem
coder validate-perf   # Diagnose the issue
# Fix configuration
coder down && coder up
coder check           # Verify fix
```

### Production Deployment
```bash
coder validate-perf > validation-report.txt
# Review report before using in production
```

## vs. Bash Scripts

| Feature | Bash | Python |
|---------|------|--------|
| **Quick check** | `./quick-gpu-check.sh` | `coder check` |
| **Full validation** | `./validate-multigpu-perf.sh` | `coder validate-perf` |
| **Output** | Plain text | Rich formatting |
| **Dependencies** | ssh, nvidia-smi, curl, jq | Python only |
| **Speed** | Fast | Fast |
| **Maintenance** | Manual | Automatic |

## Advanced Usage

### Check Specific Session
```bash
coder check my-session
coder validate-perf my-session
```

### Monitor Continuously
```bash
watch -n 60 'coder check'
```

### Save Validation Report
```bash
coder validate-perf > report-$(date +%Y%m%d).txt
```

## Documentation

- **Quick Reference**: This file
- **Full Guide**: [VALIDATION-GUIDE.md](VALIDATION-GUIDE.md)
- **Migration Info**: [PYTHON-MIGRATION.md](PYTHON-MIGRATION.md)

## Getting Started

1. **Install:**
   ```bash
   ./install-python-coder.sh
   source venv/bin/activate
   ```

2. **Create a VM:**
   ```bash
   coder up
   ```

3. **Validate (after 15 min):**
   ```bash
   coder check
   ```

4. **If issues found:**
   ```bash
   coder validate-perf
   ```

That's it! The validation commands will help you ensure your multi-GPU setup is working optimally.
