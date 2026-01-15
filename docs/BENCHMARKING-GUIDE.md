# Benchmarking Guide

Complete guide to maider's performance benchmarking system.

## Table of Contents

- [Quick Start](#quick-start)
- [Understanding the System](#understanding-the-system)
- [Commands Reference](#commands-reference)
- [Interpreting Results](#interpreting-results)
- [Best Practices](#best-practices)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

## Quick Start

### 1. Run Your First Benchmark

```bash
# After creating a VM with maider up
maider benchmark-collect

# This will:
# - Auto-detect your GPU configuration
# - Run 12 tests across 3 categories
# - Save results to centralized database
# - Display summary metrics
```

### 2. View Your Results

```bash
# See all your benchmark results
maider benchmark-compare

# Filter by category
maider benchmark-compare --task-category coding
```

### 3. Get Recommendations

```bash
# Interactive wizard
maider recommend

# Asks about:
# - Your primary task type (coding, context-heavy, reasoning, mixed)
# - Budget constraint (under $1/hr, $1-3/hr, over $3/hr, no limit)
# - Model size preference (smallest, balanced, largest)
```

## Understanding the System

### Architecture

The benchmarking system consists of:

**Database** (`~/.cache/linode-vms/benchmark-database.json`):
- Centralized storage for all benchmark results
- File locking for concurrent access
- Query filters for analysis
- Export to JSON/CSV/Markdown

**Test Suite** (12 prompts):
- **Coding** (4): Basic to complex coding tasks
- **Context-Heavy** (4): Large context analysis, architecture
- **Reasoning** (4): Problem solving, trade-off analysis

**Recommendation Engine**:
- Ranks configs by confidence, efficiency, and preferences
- Considers # of benchmark runs for confidence
- Calculates cost efficiency (tokens/sec per $/hour)

### How It Works

1. **Collect**: Run benchmarks on VMs as you use them
2. **Store**: Results saved to centralized database with metadata
3. **Query**: Filter and compare results across configs
4. **Recommend**: Get data-driven suggestions based on your needs

### Test Categories

#### Coding Tasks
- **Simple function**: Basic function writing (100 tokens)
- **Code review**: Analyzing and improving code (200 tokens)
- **Algorithm explanation**: Explaining algorithms with code (400 tokens)
- **Complex refactoring**: Large-scale code modernization (500 tokens)

#### Context-Heavy Tasks
- **Multi-file analysis**: Understanding interconnected code (800 tokens)
- **Refactor with context**: Large-scale refactoring (1000 tokens)
- **Debug trace analysis**: Root cause analysis (600 tokens)
- **Architecture explanation**: System design documentation (800 tokens)

#### Reasoning Tasks
- **Problem decomposition**: Breaking down complex problems (300 tokens)
- **Design trade-offs**: Comparing architectural approaches (400 tokens)
- **Algorithmic optimization**: Performance analysis (500 tokens)
- **System design**: High-level architecture planning (600 tokens)

## Commands Reference

### `maider benchmark`

Enhanced benchmark command with category filtering.

**Usage**:
```bash
maider benchmark [OPTIONS]
```

**Options**:
- `--session`, `-s`: Session to benchmark (default: current)
- `--output`, `-o`: Output file (default: `.benchmark-results.json`)
- `--category`, `-c`: Test category (`all`, `coding`, `context_heavy`, `reasoning`)
- `--save-to-db` / `--no-db`: Save to database (default: True)

**Examples**:
```bash
# Run all tests
maider benchmark

# Run only coding tests
maider benchmark --category coding

# Skip database saving
maider benchmark --no-db

# Benchmark specific session
maider benchmark -s my-session
```

### `maider benchmark-collect`

Simplified collection command.

**Usage**:
```bash
maider benchmark-collect [SESSION] [OPTIONS]
```

**Options**:
- `--category`, `-c`: Test category to run

**Examples**:
```bash
# Benchmark current session
maider benchmark-collect

# Benchmark specific session
maider benchmark-collect my-session

# Run only coding tests
maider benchmark-collect --category coding
```

### `maider benchmark-compare`

Compare results across configurations.

**Usage**:
```bash
maider benchmark-compare [OPTIONS]
```

**Options**:
- `--gpu-type`, `-g`: Filter by GPU type
- `--model-category`, `-m`: Filter by model category (7b, 14b, 30b, 70b)
- `--task-category`, `-t`: Filter by task category
- `--sort-by`, `-s`: Sort metric (`tokens_per_sec`, `cost_per_1k_tokens`, `cost_efficiency`)
- `--format`, `-f`: Output format (`table`, `json`, `csv`, `markdown`)
- `--output`, `-o`: Output file (required for json/csv/markdown)

**Examples**:
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

# Complex query
maider benchmark-compare \
  --task-category coding \
  --sort-by cost_efficiency \
  --format markdown -o coding-results.md
```

### `maider recommend`

Interactive recommendation wizard.

**Usage**:
```bash
maider recommend
```

**Interactive Flow**:
1. **Task Type**: What you'll primarily use the GPU for
2. **Budget**: Your cost constraints
3. **Model Size**: Performance vs cost preference

**Output**:
- Top 3 ranked recommendations
- Performance metrics (tokens/sec, cost)
- Confidence level based on # of runs
- Warnings for low-confidence data

### `maider benchmark-status`

Show coverage and gaps.

**Usage**:
```bash
maider benchmark-status
```

**Displays**:
- Total benchmarks collected
- GPU types tested (X/7)
- Tested configurations with run counts
- Last benchmark date
- Missing GPU types
- Confidence level breakdown

## Interpreting Results

### Metrics

**Throughput (tokens/sec)**:
- Higher is better
- Measures generation speed
- Varies by model size and GPU type

**Cost per 1K tokens ($)**:
- Lower is better
- Actual cost to generate 1000 tokens
- Accounts for both speed and hourly cost

**Cost Efficiency (tokens/sec per $/hour)**:
- Higher is better
- Best "value for money" metric
- Formula: `tokens_per_sec ÷ hourly_cost`

**Hourly Cost ($)**:
- Direct VM cost
- RTX 4000: $0.52-$2.08/hour
- RTX 6000: $1.50-$6.00/hour

### Confidence Levels

**High (3+ runs)**:
- Green indicator
- Reliable, stable data
- Safe to use for decisions

**Medium (2 runs)**:
- Yellow indicator
- Limited data, some variance possible
- Consider running more benchmarks

**Low (1 run)**:
- Red indicator
- Single data point, results may vary
- Run more benchmarks before deciding

### Reading Comparison Tables

Example output from `maider benchmark-compare`:

```
┌──────────┬──────┬──────┬────────┬────────────┬──────────┬─────────┬────────────┐
│ GPU Type │ GPUs │ VRAM │ Model  │ Tokens/Sec │ Cost/1K  │ $/Hour  │ Efficiency │
├──────────┼──────┼──────┼────────┼────────────┼──────────┼─────────┼────────────┤
│ RTX6000x2│  2   │ 96GB │ 70B-AWQ│    45.3    │ $0.0242  │  $3.00  │    15.1    │
│ RTX4000x2│  2   │ 40GB │ 32B-AWQ│    38.1    │ $0.0178  │  $1.04  │    36.6    │
└──────────┴──────┴──────┴────────┴────────────┴──────────┴─────────┴────────────┘
```

**Analysis**:
- RTX6000x2: Faster (45.3 tok/sec) but more expensive ($3/hr)
- RTX4000x2: Slower (38.1 tok/sec) but much better value (36.6 efficiency)
- For coding: RTX4000x2 is 84% the speed at 35% the cost = best value
- For maximum performance: RTX6000x2 wins

## Best Practices

### 1. Build Database Incrementally

**Do this**: Benchmark VMs as you naturally use them
```bash
# Create VM for project A
maider up  # RTX 6000 x2 config
maider benchmark-collect
# ... work on project ...
maider down

# Later, create VM for project B
maider up  # RTX 4000 x2 config
maider benchmark-collect
# ... work on project ...
maider down
```

**Don't do this**: Spin up all 7 configs at once just to benchmark
- Expensive (~$15/hour for all VMs)
- Wasteful if you won't use all configs
- Benchmarks are only useful for configs you actually need

### 2. Run Multiple Benchmarks

**For reliable data, run 3+ benchmarks per config**:
```bash
# After creating a VM
maider benchmark-collect

# Later, before destroying
maider benchmark-collect

# Next time you use this config
maider benchmark-collect
```

**Why**: Performance can vary due to:
- Model caching (first run slower)
- Network conditions
- API throttling
- Background processes

### 3. Benchmark Different Categories

Test the workload you'll actually use:

```bash
# Mostly coding tasks?
maider benchmark --category coding

# Large context work?
maider benchmark --category context_heavy

# Problem solving?
maider benchmark --category reasoning

# Mixed usage? (default)
maider benchmark  # Runs all categories
```

### 4. Check Coverage Before Decisions

```bash
# Before making a big decision
maider benchmark-status

# Check:
# - Do I have 3+ runs for the config I'm considering?
# - Is the data recent (< 30 days)?
# - Have I tested the right task category?
```

### 5. Compare Apples to Apples

When comparing configs:
- Same task category (coding vs coding)
- Recent benchmarks (< 30 days)
- Similar model categories (70B vs 70B, not 70B vs 30B)

```bash
# Good comparison
maider benchmark-compare --task-category coding

# Bad comparison (mixing categories)
maider benchmark-compare  # Shows all categories mixed
```

## Advanced Usage

### Export for Analysis

```bash
# Export to CSV for Excel/Google Sheets
maider benchmark-compare --format csv -o results.csv

# Export to JSON for programmatic analysis
maider benchmark-compare --format json -o results.json

# Export to Markdown for documentation
maider benchmark-compare --format markdown -o results.md
```

### Query Specific Configs

```bash
# Only 70B models
maider benchmark-compare --model-category 70b

# Only RTX 6000 GPUs
maider benchmark-compare --gpu-type g1-gpu-rtx6000-2

# Coding tasks on RTX 6000 x2, sorted by efficiency
maider benchmark-compare \
  --gpu-type g1-gpu-rtx6000-2 \
  --task-category coding \
  --sort-by cost_efficiency
```

### Programmatic Access

```python
from maider.benchmark_db import BenchmarkDatabase

# Load database
db = BenchmarkDatabase()

# Get all results
results = db.get_results()

# Query with filters
results = db.get_results(
    gpu_type="g1-gpu-rtx6000-2",
    model_category="70b",
    task_category="coding"
)

# Get top performers
best = db.get_best_by_metric(
    metric="cost_efficiency",
    task_category="coding",
    limit=5
)

# Coverage analysis
coverage = db.get_coverage_report()
print(f"GPU types tested: {coverage['gpu_types_tested']}/7")
```

### Custom Test Prompts

If you want to test specific prompts:

```python
from maider.commands.benchmark import run_single_prompt, calculate_cost_per_1k_tokens

# Your custom prompt
result = run_single_prompt(
    api_base="http://localhost:8000/v1",
    prompt="Your custom test prompt here",
    model="coder",
    timeout=120
)

if result:
    tokens_per_sec = result['tokens_per_sec']
    cost = calculate_cost_per_1k_tokens(tokens_per_sec, 3.00)  # $3/hr VM
    print(f"Performance: {tokens_per_sec:.2f} tok/sec")
    print(f"Cost: ${cost:.4f}/1K tokens")
```

## Troubleshooting

### No Recommendations Available

**Problem**: `maider recommend` says "No recommendations found"

**Solutions**:
1. Run benchmarks first: `maider benchmark-collect`
2. Relax budget constraints (try "No constraint")
3. Change task type filter
4. Check if database has any data: `maider benchmark-status`

### Low Confidence Warnings

**Problem**: Recommendations show "⚠ Single benchmark - results may vary"

**Solution**: Run more benchmarks on that config
```bash
# Use the same config again and benchmark
maider benchmark-collect
```

**Why**: Performance varies, need 3+ runs for reliable data

### Stale Data

**Problem**: `benchmark-status` shows "(stale)" next to configs

**Solution**: Re-benchmark old configs
```bash
# Create VM with that config
maider up

# Re-benchmark
maider benchmark-collect

# Data is now fresh
```

**Why**: Models, vLLM versions, or hardware change over time

### Database Corruption

**Problem**: Commands fail with JSON errors

**Solution**:
```bash
# Backup database
cp ~/.cache/linode-vms/benchmark-database.json \
   ~/.cache/linode-vms/benchmark-database.backup.json

# Check JSON validity
python3 -m json.tool ~/.cache/linode-vms/benchmark-database.json

# If corrupted, restore from backup or start fresh
rm ~/.cache/linode-vms/benchmark-database.json
```

### Slow Benchmarks

**Problem**: Benchmarks take > 30 minutes

**Possible causes**:
1. Context-heavy tests with large max_model_len (expected)
2. Cold model loading (first run slower)
3. Network issues
4. GPU throttling

**Solutions**:
```bash
# Run only coding tests (faster)
maider benchmark --category coding

# Check GPU utilization
ssh root@$IP
nvtop

# Check vLLM logs for issues
ssh root@$IP 'docker logs $(docker ps --format "{{.Names}}" | head -n1)'
```

### Missing GPU Types

**Problem**: `benchmark-status` shows many missing types

**This is normal!** You only need to benchmark configs you actually use.

**Optional**: If you want complete coverage for a comparison guide:
```bash
# Methodically test each type
for type in g2-gpu-rtx4000a1-s g2-gpu-rtx4000a2-s g1-gpu-rtx6000-1 g1-gpu-rtx6000-2; do
  maider up  # Create with this type
  maider benchmark-collect
  maider down
done
```

**Cost**: ~$15-20 total for full coverage (includes VM runtime)

## Tips & Tricks

### Quick Value Check

Want to know if a config is worth the cost?

```bash
maider benchmark-compare --sort-by cost_efficiency
```

Top result = best value for money

### Find Fastest Config

```bash
maider benchmark-compare --sort-by tokens_per_sec
```

Top result = maximum performance (regardless of cost)

### Check If Data Is Reliable

```bash
maider benchmark-status | grep "High"
```

Shows which configs have reliable data (3+ runs)

### Compare Two Specific Configs

```bash
maider benchmark-compare --gpu-type g1-gpu-rtx6000-2
maider benchmark-compare --gpu-type g2-gpu-rtx4000a2-s
```

Run both, compare output side by side

### Track Improvements Over Time

```bash
# Save results with timestamp
maider benchmark-compare --format csv -o results-$(date +%Y%m%d).csv
```

Compare files to see if performance changed

## FAQs

**Q: How long does a full benchmark take?**
A: 10-20 minutes for all 12 tests. Use `--category` to run only 4 tests (~3-5 minutes).

**Q: Can I benchmark multiple VMs in parallel?**
A: Yes! Each session has its own benchmark results. They're automatically merged in the database.

**Q: Does benchmarking cost extra?**
A: No direct cost. You pay for VM runtime (~$0.50-1.00 for 15-20 min benchmark). But you'd run the VM anyway.

**Q: Can I delete old benchmarks?**
A: Yes, manually edit `~/.cache/linode-vms/benchmark-database.json` or delete it to start fresh.

**Q: Why do my results differ from yours?**
A: Performance varies by: vLLM version, model version, time of day (API throttling), network speed.

**Q: Can I share my benchmarks?**
A: Yes! Export to JSON/CSV/Markdown and share. Community benchmark aggregation coming in future release.

**Q: How do I benchmark a custom model?**
A: Just use it! The system auto-detects any model you're running.

**Q: Can I add custom test prompts?**
A: Not via CLI currently. You can edit `TEST_PROMPTS` in `src/maider/commands/benchmark.py` or use Python API directly.

## Next Steps

1. **Run your first benchmark**: `maider benchmark-collect`
2. **Check the results**: `maider benchmark-compare`
3. **Get recommendations**: `maider recommend`
4. **Build your database over time**: Benchmark each new config you try

For more details, see:
- [CLAUDE.md](../CLAUDE.md) - Full system documentation
- [VALIDATION-GUIDE.md](VALIDATION-GUIDE.md) - GPU validation commands
- [README.md](../README.md) - Quick start guide
