# Python Migration

The Linode LLM Coder has been migrated from Bash to Python for better maintainability and reliability.

## Why Python?

The Bash version was hitting API evolution issues:
- ❌ Missing `root_pass` parameter (newly required)
- ❌ Missing `interfaces` configuration (newly required)
- ❌ `authorized_keys` format incompatibilities
- ❌ Complex JSON manipulation with jq
- ❌ String parsing gymnastics

The Python SDK handles all of this automatically:
- ✅ API abstraction - SDK handles parameter requirements
- ✅ Better error handling and type safety
- ✅ Easier to maintain and extend
- ✅ Proper JSON/data structure handling
- ✅ Testable code

## Installation

```bash
# Install the Python version
./install-python-coder.sh

# Activate virtual environment
source venv/bin/activate

# Verify installation
coder --help
```

## Migration from Bash

The Python version maintains compatibility with your existing `.env` configuration:

```bash
# Your existing .env and .env.secrets files work as-is
coder validate

# Create a VM (same as ./coder.sh up)
coder up

# List VMs (same as ./coder.sh list)
coder list

# Destroy a VM (same as ./coder.sh down)
coder down
```

### Session Compatibility

- ✅ Python version reads from `~/.cache/linode-vms/` (same location)
- ✅ Uses `.aider-env` symlink (same mechanism)
- ⚠️ Bash sessions won't have all metadata - recommend recreating

### What's Different?

| Feature | Bash | Python |
|---------|------|--------|
| **Installation** | No setup | `pip install` (one-time) |
| **Commands** | `./coder.sh up` | `coder up` |
| **Dependencies** | linode-cli, jq, ssh | Python 3.10+, linode_api4 |
| **Error handling** | Basic | Comprehensive with rich output |
| **API issues** | Manual fixes needed | SDK handles automatically |

## Commands

### Core Commands

```bash
# Create and configure a new VM
coder up [name]

# Destroy a VM
coder down [session]

# List all active VMs
coder list

# Show VM status
coder status [session]

# Validate configuration
coder validate

# Quick GPU health check
coder check [session]

# Comprehensive performance validation
coder validate-perf [session]
```

### Examples

```bash
# Create a VM with auto-generated name
coder up

# Create a VM with custom name
coder up my-coding-session

# Destroy current session
coder down

# Destroy specific session
coder down my-coding-session

# List all VMs
coder list

# Show status of current session
coder status

# Validate .env configuration
coder validate
```

## What's Implemented

✅ **Core functionality:**
- VM creation with proper interface configuration
- Session management
- SSH tunnel setup
- Configuration validation
- Cost tracking
- List/status commands

✅ **Configuration:**
- .env and .env.secrets loading
- 1Password CLI integration
- GPU count detection
- Tensor parallel size validation

✅ **User experience:**
- Rich terminal output (colors, tables, spinners)
- Better error messages
- Progress indicators

## Validation Commands (Now in Python!)

The validation scripts have been ported to Python and integrated into the CLI:

✅ **`coder check`** - Quick GPU health check (replaces `quick-gpu-check.sh`)
- GPU memory usage across all GPUs
- Tensor parallelism status
- Quick throughput test
- Takes ~30 seconds

✅ **`coder validate-perf`** - Comprehensive validation (replaces `validate-multigpu-perf.sh`)
- GPU hardware and topology validation
- Tensor parallelism configuration check
- Memory distribution analysis
- NCCL communication validation
- Live performance tests (3 prompt sizes)
- Configuration recommendations
- Takes ~5 minutes

## What's Not Yet Ported

The following bash scripts still work and can be used alongside the Python version:

- `./benchmark.sh` - Performance benchmarking
- `./benchmark-all.sh` - Multi-VM comparison

These will be ported to Python in future updates.

## Testing the Migration

1. **Install:**
   ```bash
   ./install-python-coder.sh
   source venv/bin/activate
   ```

2. **Validate configuration:**
   ```bash
   coder validate
   ```

3. **Create a test VM:**
   ```bash
   coder up test-migration
   ```

4. **Verify it works:**
   ```bash
   # Wait for setup to complete, then:
   source .aider-env
   curl http://localhost:8000/v1/models
   ```

5. **Clean up:**
   ```bash
   coder down test-migration
   ```

## Troubleshooting

### Import errors

```bash
# Make sure you've activated the venv
source venv/bin/activate

# Reinstall if needed
pip install -e .
```

### linode_api4 not found

```bash
# Install dependencies
pip install -r requirements.txt
```

### Command not found: coder

```bash
# Activate venv first
source venv/bin/activate

# Or use direct path
python -m linode_coder.cli --help
```

## Development

```bash
# Install with dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black src/

# Lint
ruff check src/
```

## Coexistence with Bash Version

Both versions can coexist:
- Bash: `./coder.sh <command>`
- Python: `coder <command>` (when venv is active)

They share the same:
- Configuration files (`.env`, `.env.secrets`)
- Session directory (`~/.cache/linode-vms/`)
- SSH tunnels and .aider-env

## Next Steps

After testing, you can:

1. **Keep both versions:**
   - Use Python for VM management (more reliable)
   - Use Bash scripts for validation/benchmarking

2. **Full migration:**
   - Port validation scripts to Python
   - Add watchdog functionality
   - Add wizard command
   - Deprecate bash version

3. **Extend with Python:**
   - Add Slack notifications
   - Add Prometheus metrics
   - Add better logging
   - Add unit tests

## Feedback

If you encounter issues with the Python version:
1. Check the error message (they're more detailed now)
2. Try the same command with `--help` to see options
3. Fall back to bash version if needed: `./coder.sh <command>`
