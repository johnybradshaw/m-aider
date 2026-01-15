# Multi-GPU Performance Validation Guide

This guide helps you validate and maximize performance from your multi-GPU vLLM deployment.

## Quick Fixes Applied

### 1. GPU Count Detection Fix
**Problem**: Type `g2-gpu-rtx4000a4-m` was detected as 1 GPU instead of 4.

**Fixed**: Updated `detect_gpu_count()` to handle patterns like `*a4-*` for 4 GPUs.

### 2. Linode Creation Fix
**Problem**: Linode CLI requires `--root_pass` parameter.

**Fixed**: Auto-generate random password (SSH keys are still used for access).

## Validation Tools

### 1. Quick Health Check (30 seconds)

```bash
./quick-gpu-check.sh
```

**What it shows:**
- GPU memory usage across all GPUs
- Whether all GPUs are active (tensor parallelism working)
- Quick throughput test

**Expected output for working multi-GPU:**
```
✅ All 4 GPUs are active (tensor parallelism working!)
✅ Generated 100 tokens in 2.1s (47.6 tok/s)
```

**Problem indicators:**
```
❌ 3 of 4 GPUs appear idle
   → Tensor parallelism may not be configured correctly
```

### 2. Comprehensive Performance Validation (5 minutes)

```bash
./validate-multigpu-perf.sh
```

**What it checks:**
1. ✅ **GPU Hardware**: Count, specs, PCIe/NVLink topology
2. ✅ **Tensor Parallelism**: Configuration in vLLM logs
3. ✅ **Memory Distribution**: All GPUs should have similar usage
4. ✅ **NCCL Communication**: Multi-GPU coordination errors
5. ✅ **Live Performance**: Throughput tests with varying prompt sizes
6. ✅ **Real-Time Monitoring**: GPU utilization during inference (30s load test)
7. ✅ **Configuration Review**: Recommendations for your setup

**Expected output sections:**
```
══════════════════════════════════════════════════════════
  1. GPU Hardware Validation
══════════════════════════════════════════════════════════

✓ Found 4 GPU(s)

GPU Details:
  GPU 0: NVIDIA RTX 6000 Ada | 48GB | PCIe Gen4 x16
  GPU 1: NVIDIA RTX 6000 Ada | 48GB | PCIe Gen4 x16
  GPU 2: NVIDIA RTX 6000 Ada | 48GB | PCIe Gen4 x16
  GPU 3: NVIDIA RTX 6000 Ada | 48GB | PCIe Gen4 x16

GPU Topology (NVLINK/PCIe connectivity):
[Shows if GPUs have direct NVLink or must communicate via PCIe]

══════════════════════════════════════════════════════════
  2. Tensor Parallelism Configuration
══════════════════════════════════════════════════════════

✓ Tensor parallel size (4) matches GPU count (4)

══════════════════════════════════════════════════════════
  3. GPU Memory Utilization
══════════════════════════════════════════════════════════

✓ GPU 0: 42GB / 48GB (87%)
✓ GPU 1: 42GB / 48GB (87%)
✓ GPU 2: 41GB / 48GB (85%)
✓ GPU 3: 42GB / 48GB (87%)
✓ All GPUs have similar memory usage (good TP distribution)

══════════════════════════════════════════════════════════
  6. Real-Time GPU Utilization During Inference
══════════════════════════════════════════════════════════

Time     | GPU0 | GPU1 | GPU2 | GPU3 | Avg
---------+------+------+------+------+-----
10:45:01 |  89% |  87% |  88% |  89% |  88%
10:45:03 |  91% |  89% |  90% |  91% |  90%
...
```

## Common Issues & Solutions

### Issue 1: Only GPU 0 is Active

**Symptoms:**
```
✗ GPU 0: 42GB / 48GB (87%)
✗ GPU 1: 1GB / 48GB (2%) - IDLE!
✗ GPU 2: 1GB / 48GB (2%) - IDLE!
✗ GPU 3: 1GB / 48GB (2%) - IDLE!
```

**Cause:** Tensor parallelism not configured correctly.

**Solution:**
```bash
# Check current TP configuration
source .aider-env
ssh root@"$IP" "docker logs \$(docker ps -q) 2>&1 | grep tensor"

# Fix: Update .env and restart
./coder down
# Edit .env: VLLM_TENSOR_PARALLEL_SIZE=4
./coder up
```

### Issue 2: Poor Throughput Despite All GPUs Active

**Symptoms:**
```
✓ All 4 GPUs are active
⚠ Generated 100 tokens in 8.2s (12.2 tok/s)  ← Too slow!
```

**Possible causes:**

1. **NCCL Communication Issues**
   ```bash
   # Check for NCCL errors
   ssh root@"$IP" "docker logs \$(docker ps -q) 2>&1 | grep -i nccl"
   ```

   **Fix:** Add NCCL tuning to `.env`:
   ```bash
   VLLM_EXTRA_ARGS=--tensor-parallel-size 4
   # May also need in docker-compose environment section:
   NCCL_DEBUG=WARN
   NCCL_IB_DISABLE=1
   NCCL_P2P_DISABLE=0
   ```

2. **Memory Bottleneck**
   ```bash
   # Check if OOM warnings in logs
   ssh root@"$IP" "docker logs \$(docker ps -q) 2>&1 | grep -i 'out of memory'"
   ```

   **Fix:** Reduce memory utilization in `.env`:
   ```bash
   VLLM_GPU_MEMORY_UTILIZATION=0.85  # Was 0.90
   VLLM_MAX_MODEL_LEN=16384          # Reduce context window
   ```

3. **PCIe Bandwidth Limitation**

   **Check topology:**
   ```bash
   ssh root@"$IP" "nvidia-smi topo -m"
   ```

   - `NV#` = NVLink (best, 900GB/s)
   - `SYS` = PCIe across CPU sockets (slower)
   - `PHB` = PCIe same socket (medium)

   **No fix needed** - this is hardware limitation. NVLink provides best multi-GPU performance.

### Issue 3: Unbalanced GPU Memory

**Symptoms:**
```
✓ GPU 0: 42GB / 48GB (87%)
⚠ GPU 1: 35GB / 48GB (72%)  ← Lower than others
✓ GPU 2: 41GB / 48GB (85%)
✓ GPU 3: 42GB / 48GB (87%)
```

**Cause:** Usually not a problem if small variance (<15%). Large variance may indicate:
- Partial TP initialization failure
- Different model layer distribution

**Solution:**
```bash
# Restart container to reinitialize
./coder fix
```

### Issue 4: High GPU Utilization But Low Throughput

**Symptoms:**
```
GPU utilization: 95% average
Throughput: 15 tok/s  ← Should be 40+ for this config
```

**Cause:** GPUs waiting for each other (synchronization overhead).

**Check:**
```bash
# Watch real-time utilization - should all spike together
watch -n 0.5 ssh root@"$IP" 'nvidia-smi --query-gpu=utilization.gpu --format=csv'
```

**Solutions:**
1. Reduce `VLLM_MAX_NUM_SEQS` to 1 (less batching)
2. Enable chunked prefill: `VLLM_EXTRA_ARGS=--enable-chunked-prefill`
3. Check NCCL environment variables (see Issue 2)

## Performance Benchmarks

Expected tokens/sec for reference (Qwen2.5-Coder-32B-Instruct-AWQ):

| Config | Expected tok/s | Notes |
|--------|----------------|-------|
| 1x RTX 6000 Ada | 35-45 | Baseline |
| 2x RTX 6000 Ada | 60-80 | ~1.7x speedup (not 2x due to overhead) |
| 4x RTX 6000 Ada | 100-130 | ~2.5-3x speedup |

If you're getting <50% of expected performance, run the validation scripts above.

## Advanced Monitoring

### Live GPU Monitoring on VM

```bash
# SSH to VM
ssh root@"$IP"

# Interactive GPU monitor
nvtop

# Or watch nvidia-smi
watch -n 1 nvidia-smi
```

### Log Analysis

```bash
# Check vLLM startup logs
ssh root@"$IP" "docker logs \$(docker ps -q) 2>&1 | head -n 100"

# Watch live logs
ssh root@"$IP" "docker logs -f \$(docker ps -q)"

# Search for specific errors
ssh root@"$IP" "docker logs \$(docker ps -q) 2>&1 | grep -i 'error\|warn\|fail'"
```

### Network Topology Check

Critical for multi-GPU performance:

```bash
# Check GPU interconnect
ssh root@"$IP" "nvidia-smi topo -m"

# Check NCCL bandwidth (if installed)
ssh root@"$IP" "nccl-test all_reduce_perf -b 8 -e 128M -f 2 -g 4"
```

## Configuration Tuning

### For Maximum Throughput

```bash
# .env
VLLM_TENSOR_PARALLEL_SIZE=4
VLLM_MAX_NUM_SEQS=4                    # Batch multiple requests
VLLM_GPU_MEMORY_UTILIZATION=0.90
VLLM_EXTRA_ARGS=--enable-prefix-caching --enable-chunked-prefill
```

### For Lowest Latency (Coding)

```bash
# .env
VLLM_TENSOR_PARALLEL_SIZE=4
VLLM_MAX_NUM_SEQS=1                    # No batching
VLLM_GPU_MEMORY_UTILIZATION=0.88
VLLM_EXTRA_ARGS=--disable-log-requests
```

### For Maximum Context Length

```bash
# .env
VLLM_TENSOR_PARALLEL_SIZE=4
VLLM_MAX_MODEL_LEN=32768               # Or higher
VLLM_GPU_MEMORY_UTILIZATION=0.85       # Lower to prevent OOM
VLLM_MAX_NUM_SEQS=1
VLLM_KV_CACHE_DTYPE=fp8_e4m3fn         # FP8 KV cache for memory savings
```

## Next Steps

1. **Run quick check first:**
   ```bash
   ./quick-gpu-check.sh
   ```

2. **If issues found, run full validation:**
   ```bash
   ./validate-multigpu-perf.sh
   ```

3. **Compare with benchmark:**
   ```bash
   ./benchmark.sh
   cat .benchmark-results.json
   ```

4. **Try configuration changes and re-validate:**
   ```bash
   # Edit .env
   ./coder fix  # Restart with new config
   ./quick-gpu-check.sh  # Verify improvement
   ```

## Getting Help

If you're still experiencing poor performance:

1. Run `./validate-multigpu-perf.sh > validation-report.txt`
2. Share the report with diagnostic info:
   - GPU count and type
   - Model being used
   - Expected vs actual throughput
   - GPU utilization patterns
   - Any NCCL errors from logs
