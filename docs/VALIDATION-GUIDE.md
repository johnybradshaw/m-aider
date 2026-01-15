# Multi-GPU Validation Guide (Python Version)

This guide explains how to use the Python-based validation commands to ensure your multi-GPU setup is performing optimally.

## Overview

The validation tools have been ported from Bash to Python and integrated into the `coder` CLI:

| Command | Purpose | Duration | Replaces |
|---------|---------|----------|----------|
| `coder check` | Quick health check | ~30 sec | `quick-gpu-check.sh` |
| `coder validate-perf` | Comprehensive analysis | ~5 min | `validate-multigpu-perf.sh` |

## Quick Health Check

### Usage

```bash
# Check current session
source venv/bin/activate
coder check

# Check specific session
coder check my-session
```

### What It Checks

1. **GPU Memory Usage**
   - Shows memory usage for all GPUs
   - Color-coded status (red=idle, yellow=low, green=good)
   - Identifies idle GPUs

2. **Multi-GPU Status**
   - Verifies all GPUs are active
   - Checks for similar memory distribution
   - Validates tensor parallelism is working

3. **Quick Throughput Test**
   - Sends a simple prompt to the API
   - Measures tokens per second
   - Validates API is responsive

### Example Output

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  Quick Multi-GPU Health Check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GPU Memory Usage:
┏━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━┓
┃ GPU  ┃ Name                 ┃ Memory Used ┃ Memory Total┃ Usage %┃ Utilization ┃
┡━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━┩
│ GPU 0│ NVIDIA RTX 4000 Ada  │ 18234 MB    │ 20470 MB    │ 89%    │ 12%         │
│ GPU 1│ NVIDIA RTX 4000 Ada  │ 18156 MB    │ 20470 MB    │ 89%    │ 15%         │
│ GPU 2│ NVIDIA RTX 4000 Ada  │ 18201 MB    │ 20470 MB    │ 89%    │ 13%         │
│ GPU 3│ NVIDIA RTX 4000 Ada  │ 18189 MB    │ 20470 MB    │ 89%    │ 14%         │
└──────┴──────────────────────┴─────────────┴─────────────┴────────┴─────────────┘

Multi-GPU Status:
  ✓ All 4 GPUs are active with similar memory usage

Quick Throughput Test:
  ✓ Generated 98 tokens in 2.3s (42.6 tok/s)

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For detailed performance analysis: coder validate-perf
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

### Interpreting Results

**✅ Good Signs:**
- All GPUs show similar memory usage (within 10%)
- Memory usage > 50% on all GPUs
- "All GPUs are active" message
- Throughput > 30 tok/s for 32B models

**❌ Problem Indicators:**
- One or more GPUs show "IDLE" (< 10% memory)
- Message: "X of Y GPUs appear idle"
- Throughput < 15 tok/s
- API test fails

## Comprehensive Performance Validation

### Usage

```bash
# Validate current session
source venv/bin/activate
coder validate-perf

# Validate specific session
coder validate-perf my-session
```

### What It Checks

#### 1. GPU Hardware Validation
- Counts and identifies all GPUs
- Shows GPU specifications
- Displays topology (NVLink vs PCIe connectivity)

#### 2. Tensor Parallelism Configuration
- Searches vLLM logs for TP initialization
- Verifies TP size matches GPU count
- Checks for TP-related errors

#### 3. GPU Memory Utilization
- Detailed memory breakdown per GPU
- Identifies idle GPUs
- Checks memory distribution variance

#### 4. NCCL Communication
- Scans logs for NCCL errors
- Detects OOM errors
- Reports model loading failures

#### 5. Live Performance Tests
- Runs 3 tests with different prompt sizes:
  - Short prompt (256 tokens)
  - Medium prompt (512 tokens)
  - Long prompt (512 tokens)
- Measures throughput for each

#### 6. Configuration Review
- Provides tuning recommendations
- Suggests optimal settings
- Identifies potential issues

### Example Output

```
╭───────────────────────────────────────╮
│ 1. GPU Hardware Validation           │
╰───────────────────────────────────────╯

✓ Found 4 GPU(s)

GPU Details:
  GPU 0: NVIDIA RTX 4000 Ada Generation | 20470 MB
  GPU 1: NVIDIA RTX 4000 Ada Generation | 20470 MB
  GPU 2: NVIDIA RTX 4000 Ada Generation | 20470 MB
  GPU 3: NVIDIA RTX 4000 Ada Generation | 20470 MB

GPU Topology (NVLink/PCIe connectivity):
        GPU0    GPU1    GPU2    GPU3
  GPU0   X      SYS     SYS     SYS
  GPU1  SYS      X      SYS     SYS
  GPU2  SYS     SYS      X      SYS
  GPU3  SYS     SYS     SYS      X

Legend:
  X    = Self
  SYS  = Connection traversing PCIe as well as the SMP interconnect
  NODE = Connection traversing PCIe as well as NUMA interconnect
  PHB  = Connection traversing PCIe as well as a PCIe Host Bridge
  NV#  = Connection traversing a bonded set of # NVLinks

╭───────────────────────────────────────╮
│ 2. Tensor Parallelism Configuration  │
╰───────────────────────────────────────╯

Checking vLLM tensor parallelism initialization...

Tensor Parallelism Logs:
  INFO - Initializing distributed environment with tensor parallel size 4
  INFO - Using NCCL as the communication backend
  INFO - All ranks initialized successfully

✓ All 4 GPUs are active with similar memory usage

╭───────────────────────────────────────╮
│ 5. Live Performance Test              │
╰───────────────────────────────────────╯

Running performance test with 3 different prompt sizes...

Short prompt test:
  ✓ Generated 243 tokens in 5.8s (41.9 tok/s)

Medium prompt test:
  ✓ Generated 487 tokens in 11.6s (42.0 tok/s)

Long prompt test:
  ✓ Generated 512 tokens in 12.3s (41.6 tok/s)

╭───────────────────────────────────────╮
│ Validation Summary                    │
╰───────────────────────────────────────╯

✓ All GPUs are active: Tensor parallelism is working
✓ No NCCL errors: Inter-GPU communication is healthy
✓ Average throughput: 41.8 tok/s: Performance is normal

For detailed investigation:
  • SSH to VM: ssh root@172.233.255.17
  • Monitor GPUs: nvtop
  • Check logs: docker logs $(docker ps -q)
```

## Common Issues and Solutions

### Issue 1: GPUs Appear Idle

**Symptoms:**
```
✗ 3 of 4 GPUs appear idle
  → Tensor parallelism may not be configured correctly
```

**Solution:**
```bash
# Check configuration
coder validate

# Update .env
VLLM_TENSOR_PARALLEL_SIZE=4  # Must match GPU count

# Recreate VM
coder down
coder up
```

### Issue 2: NCCL Errors

**Symptoms:**
```
✗ NCCL errors detected:
  NCCL WARN Call to ibv_create_qp failed
```

**Solution:**

Edit your `.env` and add to `VLLM_EXTRA_ARGS`:
```bash
# For PCIe-only systems (no InfiniBand)
VLLM_EXTRA_ARGS=--tensor-parallel-size 4
# Plus add to docker-compose environment:
NCCL_IB_DISABLE=1
NCCL_P2P_DISABLE=0
NCCL_DEBUG=WARN
```

### Issue 3: Low Throughput

**Symptoms:**
```
⚠ Average throughput: 15.2 tok/s (expected: 40+ tok/s)
```

**Possible Causes & Solutions:**

1. **OOM Issues**
   ```bash
   # Reduce memory utilization
   VLLM_GPU_MEMORY_UTILIZATION=0.85
   VLLM_MAX_MODEL_LEN=16384
   ```

2. **High Batch Size**
   ```bash
   # Reduce for lower latency
   VLLM_MAX_NUM_SEQS=1
   ```

3. **Model Still Loading**
   ```bash
   # Check logs
   ssh root@$IP "docker logs -f \$(docker ps -q)"
   ```

### Issue 4: API Connection Failed

**Symptoms:**
```
✗ API test failed: Connection refused
  → Is the SSH tunnel active?
```

**Solution:**
```bash
# Check if tunnel is running
ps aux | grep ssh

# Recreate tunnel
ssh -fNM -L 8000:localhost:8000 -L 3000:localhost:3000 root@$IP

# Or recreate session
coder down
coder up
```

## Performance Benchmarks

Expected throughput for Qwen2.5-Coder-32B-Instruct-AWQ:

| GPU Configuration | Expected tok/s | Notes |
|-------------------|----------------|-------|
| 1x RTX 4000 Ada (20GB) | Not possible | Insufficient VRAM |
| 2x RTX 4000 Ada (40GB) | 35-45 | Tight memory |
| 4x RTX 4000 Ada (80GB) | 40-50 | Recommended |
| 1x RTX 6000 Ada (48GB) | 40-50 | Single GPU |
| 2x RTX 6000 Ada (96GB) | 70-90 | Good scaling |
| 4x RTX 6000 Ada (192GB) | 120-140 | Excellent scaling |

If you're getting < 50% of expected throughput, run `coder validate-perf` for diagnosis.

## Workflow

### Initial Setup
```bash
# 1. Create VM
coder up

# 2. Quick check (after ~15 min)
coder check

# 3. If issues found, run full validation
coder validate-perf
```

### After Configuration Changes
```bash
# 1. Update .env
vim .env

# 2. Recreate VM
coder down
coder up

# 3. Validate changes
coder check
```

### Before Production Use
```bash
# Run comprehensive validation
coder validate-perf

# Save results
coder validate-perf > validation-report.txt
```

## Advanced Usage

### Monitoring During Inference

While using aider:

```bash
# Terminal 1: Run aider
source .aider-env
aider --model "$AIDER_MODEL"

# Terminal 2: Monitor GPUs
source venv/bin/activate
watch -n 2 'coder check'
```

### Continuous Validation

```bash
# Monitor throughput every 5 minutes
while true; do
  coder check
  sleep 300
done
```

### Comparing Configurations

```bash
# Test config A
coder validate-perf > results-config-a.txt

# Update .env to config B
coder down && coder up

# Test config B
coder validate-perf > results-config-b.txt

# Compare
diff results-config-a.txt results-config-b.txt
```

## Integration with Development Workflow

### Pre-commit Hook Example

```bash
#!/bin/bash
# .git/hooks/pre-push

# Ensure VM is healthy before pushing
if ! coder check > /dev/null 2>&1; then
  echo "⚠️  GPU health check failed!"
  echo "Run 'coder check' to diagnose issues."
  exit 1
fi
```

### CI/CD Integration

```yaml
# .github/workflows/validate-gpu.yml
name: GPU Validation
on: [push]
jobs:
  validate:
    runs-on: self-hosted
    steps:
      - name: Check GPU Health
        run: |
          source venv/bin/activate
          coder check

      - name: Run Performance Tests
        run: |
          source venv/bin/activate
          coder validate-perf
```

## Troubleshooting the Validation Tools

### Tool Not Found

```bash
# Ensure venv is activated
source venv/bin/activate

# Reinstall if needed
pip install -e .
```

### SSH Connection Issues

```bash
# Verify SSH access
ssh root@$IP echo "SSH works"

# Check firewall
coder status  # Shows IP and connection info
```

### Timeout Errors

```bash
# Increase timeout in ~/.ssh/config
Host *
    ServerAliveInterval 60
    ServerAliveCountMax 3
```

## Next Steps

- **For quick checks during development**: Use `coder check`
- **For comprehensive analysis**: Use `coder validate-perf`
- **For performance comparison**: See `./benchmark.sh` (bash version)
- **For production deployment**: Run both validations and save reports

## Getting Help

If validation shows issues:

1. Run `coder validate-perf > report.txt`
2. Include the report when asking for help
3. Also include:
   - GPU type and count
   - Model being used
   - Your `.env` configuration (without secrets)
