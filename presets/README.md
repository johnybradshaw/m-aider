# GPU Configuration Presets

Quick-start configurations for all Linode GPU instance types.

## Quick Start

### Option 1: Copy a Preset (Recommended)

```bash
# Copy the preset that matches your needs
cp presets/rtx4000-1gpu.env .env

# Edit only the required fields
nano .env  # Add your HUGGING_FACE_HUB_TOKEN and FIREWALL_ID

# Launch
./coder up
```

### Option 2: Use Preset Helper Script

```bash
# List available presets
./presets/use-preset.sh list

# Apply a preset (creates/updates .env)
./presets/use-preset.sh rtx6000-2gpu
```

## Available Presets

### Single GPU Configurations

#### `rtx4000-1gpu.env`
- **Hardware**: 1x RTX 4000 Ada (20GB VRAM)
- **Cost**: ~$0.52/hour
- **Best for**: 7B-14B coder models
- **Recommended models**: Qwen2.5-Coder-14B-AWQ, DeepSeek-Coder-V2-Lite
- **Context**: Up to 16K tokens
- **Use case**: Development, fast iteration, learning

#### `rtx6000-1gpu.env`
- **Hardware**: 1x RTX 6000 Ada (48GB VRAM)
- **Cost**: ~$1.50/hour
- **Best for**: 30B-70B quantized models, large context
- **Recommended models**: Qwen2.5-Coder-32B-AWQ, Llama-3.1-70B-AWQ
- **Context**: Up to 32K tokens
- **Use case**: Production coding, complex projects

### Multi-GPU Configurations

#### `rtx4000-2gpu.env`
- **Hardware**: 2x RTX 4000 Ada (40GB total VRAM)
- **Cost**: ~$1.04/hour
- **Best for**: 30B coder models
- **Recommended models**: Qwen2.5-Coder-32B-AWQ, DeepSeek-Coder-33B-AWQ
- **Context**: Up to 16-24K tokens
- **Use case**: Mid-tier models on budget

#### `rtx6000-2gpu.env`
- **Hardware**: 2x RTX 6000 Ada (96GB total VRAM)
- **Cost**: ~$3.00/hour
- **Best for**: 70B models with large context
- **Recommended models**: Qwen2.5-Coder-70B-AWQ, Llama-3.1-70B-AWQ
- **Context**: Up to 32-48K tokens
- **Use case**: Production with large models, extensive context

#### `rtx6000-4gpu.env`
- **Hardware**: 4x RTX 6000 Ada (192GB total VRAM)
- **Cost**: ~$6.00/hour
- **Best for**: Full-precision 70B, massive context, 200B+ quantized
- **Recommended models**: Qwen2.5-Coder-70B (FP16), DeepSeek-Coder-V2-236B-AWQ
- **Context**: Up to 64K+ tokens
- **Use case**: Maximum quality, research, very large codebases

## Configuration Guide

### Required Fields (Must Edit)

All presets require these fields to be set:

```bash
HUGGING_FACE_HUB_TOKEN=hf_xxxxxxxxxxxxx  # Get from https://huggingface.co/settings/tokens
FIREWALL_ID=123456                        # Your Linode firewall ID
```

### Optional Fields (Pre-configured)

These are already optimized in each preset:

- `TYPE`: Linode GPU instance type
- `REGION`: Default is `us-east` (change if needed)
- `IMAGE`: Ubuntu 24.04 LTS (recommended, don't change)
- `MODEL_ID`: Recommended model for the GPU configuration
- `SERVED_MODEL_NAME`: Short name for the model API
- `VLLM_*`: Optimized vLLM settings for the GPU configuration

## Customizing Presets

### Change the Model

Edit `MODEL_ID` in your `.env`:

```bash
# Use a different model
MODEL_ID=deepseek-ai/DeepSeek-Coder-V2-Lite-Instruct

# For HuggingFace gated models, ensure your token has access
MODEL_ID=meta-llama/Llama-3.1-70B-Instruct-AWQ
```

### Change the Region

Edit `REGION` in your `.env`:

```bash
# Available regions (check current availability):
REGION=us-east          # New Jersey, USA
REGION=us-central       # Dallas, USA
REGION=us-west          # Fremont, USA
REGION=eu-central       # Frankfurt, Germany
REGION=eu-west          # London, UK
REGION=ap-south         # Singapore
REGION=ap-northeast     # Tokyo, Japan
```

### Adjust Context Length

Increase `VLLM_MAX_MODEL_LEN` for more context (uses more VRAM):

```bash
# Default for RTX 4000 single GPU
VLLM_MAX_MODEL_LEN=16384

# Increase for larger context (monitor for OOM)
VLLM_MAX_MODEL_LEN=32768
```

**Warning**: Larger context = more KV cache = higher OOM risk. Increase gradually.

### Tune Memory Utilization

Adjust `VLLM_GPU_MEMORY_UTILIZATION` (0.0-1.0):

```bash
# Conservative (more stable, less OOM risk)
VLLM_GPU_MEMORY_UTILIZATION=0.85

# Balanced (preset default)
VLLM_GPU_MEMORY_UTILIZATION=0.90

# Aggressive (maximum context, higher OOM risk)
VLLM_GPU_MEMORY_UTILIZATION=0.95
```

## Model Selection Guide

### Quantization Types

- **AWQ (4-bit)**: Best balance of quality and VRAM efficiency
  - ~50% quality vs FP16, ~25% VRAM usage
  - Recommended for most use cases

- **GPTQ (4-bit)**: Alternative quantization, similar to AWQ
  - Slightly different quality trade-offs

- **GGUF (4-8 bit)**: Good for CPU+GPU hybrid inference
  - Not recommended for vLLM (use AWQ instead)

- **FP16/BF16 (full precision)**: Maximum quality
  - 4x VRAM usage vs AWQ
  - Only use on multi-GPU setups or smaller models

### Model Size vs Context Trade-off

| Model Size | Quantization | Min VRAM | Max Context (16GB) | Max Context (48GB) | Max Context (96GB) |
|------------|--------------|----------|--------------------|--------------------|-------------------|
| 7B | AWQ | ~4GB | 32K+ | 128K+ | 256K+ |
| 14B | AWQ | ~8GB | 16K | 64K+ | 128K+ |
| 32B | AWQ | ~18GB | Limited | 32K | 64K+ |
| 70B | AWQ | ~40GB | N/A | 16K | 32-48K |
| 70B | FP16 | ~140GB | N/A | N/A | Limited |

## Troubleshooting

### OOM (Out of Memory) Errors

If vLLM crashes with CUDA OOM:

1. Reduce `VLLM_MAX_MODEL_LEN` by 50%
2. Lower `VLLM_GPU_MEMORY_UTILIZATION` to 0.85
3. Try a smaller model or better quantization
4. Verify `VLLM_TENSOR_PARALLEL_SIZE` matches GPU count

### Model Not Found

If vLLM can't download the model:

1. Check `HUGGING_FACE_HUB_TOKEN` is set correctly
2. Verify token has access to gated models (Llama, etc.)
3. Check model ID spelling: `owner/model-name`
4. SSH in and check Docker logs: `docker logs <container>`

### Wrong GPU Count

If you see "Expected X GPUs but found Y":

1. Verify the `TYPE` matches a real Linode GPU plan
2. Check `VLLM_TENSOR_PARALLEL_SIZE` matches GPU count:
   - `rtx4000-1gpu` or `rtx6000-1gpu`: Don't set or set to 1
   - `rtx4000-2gpu` or `rtx6000-2gpu`: Set to 2
   - `rtx6000-4gpu`: Set to 4

## Advanced Usage

### Enable Prefix Caching (Experimental)

Speeds up repetitive prompts:

```bash
VLLM_EXTRA_ARGS=--enable-prefix-caching
```

### Use FP8 KV Cache (Advanced)

Reduces KV cache memory usage:

```bash
VLLM_KV_CACHE_DTYPE=fp8_e4m3fn
```

### Combine Multiple Flags

```bash
VLLM_EXTRA_ARGS=--enable-prefix-caching --enforce-eager
```

## Cost Optimization

### Development Workflow

1. **Start small**: Use `rtx4000-1gpu` for development
2. **Test thoroughly**: Switch to larger GPU only when needed
3. **Destroy immediately**: Run `./coder down` as soon as done
4. **Use presets**: Avoid trial-and-error on expensive instances

### Cost Comparison (per hour)

| Preset | GPUs | Est. Cost | Daily Cost | When to Use |
|--------|------|-----------|------------|-------------|
| rtx4000-1gpu | 1 | $0.52 | $12.48 | Development, learning |
| rtx6000-1gpu | 1 | $1.50 | $36.00 | Production, 30B models |
| rtx4000-2gpu | 2 | $1.04 | $24.96 | Budget 30B models |
| rtx6000-2gpu | 2 | $3.00 | $72.00 | Production 70B models |
| rtx6000-4gpu | 4 | $6.00 | $144.00 | Maximum capability |

**Pro tip**: Work on a small GPU, then spin up a large GPU only for final testing/deployment.

## Examples

### Example 1: Quick Dev Setup

```bash
# Use the cheapest GPU for development
cp presets/rtx4000-1gpu.env .env
echo "HUGGING_FACE_HUB_TOKEN=hf_xxx" >> .env
echo "FIREWALL_ID=123456" >> .env
./coder up
```

### Example 2: Production 70B Model

```bash
# Use dual RTX 6000 for production coding
cp presets/rtx6000-2gpu.env .env
nano .env  # Add token and firewall
./coder up

# After 2 hours of work
./coder down  # Don't forget!
```

### Example 3: Custom Configuration

```bash
# Start with a preset
cp presets/rtx6000-1gpu.env .env

# Customize for your needs
cat >> .env <<EOF
HUGGING_FACE_HUB_TOKEN=hf_xxx
FIREWALL_ID=123456
MODEL_ID=mistralai/Codestral-22B-v0.1
VLLM_MAX_MODEL_LEN=24576
EOF

./coder up
```

## Support

For issues or questions:
- See main README.md for general usage
- See CLAUDE.MD for multi-GPU deep dive
- Check vLLM docs: https://docs.vllm.ai/
- File an issue on GitHub
