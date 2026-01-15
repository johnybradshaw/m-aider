# Migration Status: Bash → Python

**Last Updated**: 2026-01-14

## Overview

The Python version (`coder` command) is **recommended for all new users**. The bash version (`coder.sh`) is functional but considered **legacy**.

## Feature Parity Matrix

### Core Commands

| Command | Bash (`coder.sh`) | Python (`coder`) | Status | Notes |
|---------|------------------|------------------|--------|-------|
| **up** | ✅ | ✅ | ✅ PARITY | Python has auto-launch aider |
| **down** | ✅ | ✅ | ✅ PARITY | Both functional |
| **list** | ✅ | ✅ | ✅ PARITY | Both functional |
| **status** | ✅ | ✅ | ✅ PARITY | Both functional |
| **wizard** | ⚠️ Stub | ✅ Full | ✅ PYTHON BETTER | Python has API queries |

### Utility Commands

| Command | Bash (`coder.sh`) | Python (`coder`) | Status | Notes |
|---------|------------------|------------------|--------|-------|
| **use** | ✅ | ❌ | ⚠️ MISSING | Switch between sessions |
| **cleanup** | ✅ | ❌ | ⚠️ MISSING | Remove stale sessions |
| **extend** | ✅ | ❌ | ⚠️ MISSING | Reset watchdog timer |
| **logs** | ✅ | ❌ | ⚠️ MISSING | View watchdog logs |
| **ssh** | ✅ | ❌ | ⚠️ MISSING | SSH to current VM |

### Validation Commands

| Command | Bash | Python (`coder`) | Status | Notes |
|---------|------|------------------|--------|-------|
| **validate** | ❌ | ✅ | ✅ PYTHON ONLY | Config validation |
| **check** | Via `quick-gpu-check.sh` | ✅ | ✅ MIGRATED | Quick GPU health |
| **validate-perf** | Via `validate-multigpu-perf.sh` | ✅ | ✅ MIGRATED | Full validation |

### Advanced Features

| Feature | Bash | Python | Status | Notes |
|---------|------|--------|--------|-------|
| **Cloud-init check** | ❌ | ✅ | ✅ PYTHON ONLY | Auto-waits in `up` |
| **vLLM readiness** | ❌ | ✅ | ✅ PYTHON ONLY | Auto-waits in `up` |
| **Auto-launch aider** | ❌ | ✅ | ✅ PYTHON ONLY | `--launch-aider` flag |
| **Aider metadata** | ⚠️ Manual | ✅ | ✅ PYTHON ONLY | Auto-generates |
| **Self-healing** | ✅ | ❌ | ⚠️ BASH ONLY | OOM/NCCL recovery |
| **Watchdog** | ✅ | ✅ | ✅ PARITY | Both functional |

## Files Status

### Python Implementation

| File | Purpose | Status |
|------|---------|--------|
| `src/linode_coder/cli.py` | CLI entry point | ✅ COMPLETE |
| `src/linode_coder/config.py` | Config management | ✅ COMPLETE |
| `src/linode_coder/linode_client.py` | Linode API wrapper | ✅ COMPLETE |
| `src/linode_coder/session.py` | Session management | ✅ COMPLETE |
| `src/linode_coder/watchdog.py` | Auto-destroy watchdog | ✅ COMPLETE |
| `src/linode_coder/commands/up.py` | VM creation | ✅ COMPLETE |
| `src/linode_coder/commands/down.py` | VM destruction | ✅ COMPLETE |
| `src/linode_coder/commands/list_vms.py` | List sessions | ✅ COMPLETE |
| `src/linode_coder/commands/status.py` | Session status | ✅ COMPLETE |
| `src/linode_coder/commands/wizard.py` | Interactive setup | ✅ COMPLETE |
| `src/linode_coder/commands/validate.py` | Config validation | ✅ COMPLETE |
| `src/linode_coder/commands/check.py` | Quick GPU check | ✅ COMPLETE |
| `src/linode_coder/commands/validate_perf.py` | Full validation | ✅ COMPLETE |

### Bash Scripts (Legacy)

| File | Purpose | Replacement | Action |
|------|---------|-------------|--------|
| `coder.sh` | Main CLI (bash) | `coder` (Python) | 📦 KEEP (legacy support) |
| `watchdog.sh` | Auto-destroy (bash) | `watchdog.py` | 🗑️ CAN REMOVE |
| `vm-state.sh` | Session management | `session.py` | 🗑️ CAN REMOVE |
| `quick-gpu-check.sh` | Quick check | `coder check` | 🗑️ CAN REMOVE |
| `validate-multigpu-perf.sh` | Full validation | `coder validate-perf` | 🗑️ CAN REMOVE |

### Standalone Scripts

| File | Purpose | Status | Action |
|------|---------|--------|--------|
| `install-python-coder.sh` | Python installer | ✅ NEEDED | ✅ KEEP |
| `benchmark.sh` | Single VM benchmark | ⚠️ NOT PORTED | 📦 KEEP (port later) |
| `benchmark-all.sh` | Multi-VM benchmark | ⚠️ NOT PORTED | 📦 KEEP (port later) |
| `presets/use-preset.sh` | Apply presets | ⚠️ WIZARD REPLACES | 🤔 DEPRECATE? |

### Test Scripts

| File | Purpose | Status |
|------|---------|--------|
| `tests/test_info.sh` | Test info command | Bash tests |
| `tests/test_usage.sh` | Test usage messages | Bash tests |
| `tests/test_validate.sh` | Test validation | Bash tests |

**Action**: These test the bash version. Should we add Python tests instead?

## Missing Python Commands

These bash commands need to be ported to Python for full feature parity:

### 1. **use** - Switch Sessions
**Bash implementation**: `coder.sh use <session>`
**What it does**: Updates `.aider-env` symlink to point to different session
**Priority**: 🔴 HIGH

### 2. **cleanup** - Remove Stale Sessions
**Bash implementation**: `coder.sh cleanup`
**What it does**: Removes sessions where VM no longer exists
**Priority**: 🟡 MEDIUM

### 3. **extend** - Reset Watchdog Timer
**Bash implementation**: `coder.sh extend [session]`
**What it does**: Resets idle timer to prevent auto-destruction
**Priority**: 🟡 MEDIUM

### 4. **logs** - View Watchdog Logs
**Bash implementation**: `coder.sh logs [lines]`
**What it does**: Shows watchdog activity logs
**Priority**: 🟢 LOW

### 5. **ssh** - SSH to VM
**Bash implementation**: `coder.sh ssh [session]`
**What it does**: Opens SSH connection to current/specified VM
**Priority**: 🟢 LOW (users can do this manually)

## Missing Bash Features in Python

### 1. **Self-Healing Multi-GPU**
**Bash implementation**: `diagnose_and_fix_vllm()` function
**What it does**: Automatically detects and fixes OOM, NCCL, TP errors
**Priority**: 🔴 HIGH - This is a critical feature

**Location**: Lines 100-300 in `coder.sh`

## Recommended Actions

### Immediate (High Priority)

1. ✅ **Port `use` command to Python**
   - Add `src/linode_coder/commands/use.py`
   - Updates symlink to switch sessions

2. ✅ **Port `cleanup` command to Python**
   - Add `src/linode_coder/commands/cleanup.py`
   - Removes stale session directories

3. ✅ **Port self-healing to Python**
   - Add to `linode_client.py` or create `healing.py`
   - Critical for production reliability

### Short-term (Medium Priority)

4. ⏳ **Port `extend` command**
   - Add `src/linode_coder/commands/extend.py`
   - Watchdog timer management

5. ⏳ **Port benchmarking tools**
   - `src/linode_coder/commands/benchmark.py`
   - `src/linode_coder/commands/benchmark_all.py`

### Long-term (Low Priority)

6. ⏳ **Port `logs` and `ssh` commands**
   - Convenience wrappers, not critical

7. ⏳ **Add Python tests**
   - Replace bash tests with pytest
   - Test suite for Python CLI

8. ⏳ **Deprecate bash version**
   - Once all features ported
   - Move `coder.sh` to `legacy/` directory

## Files Safe to Remove

Once the missing commands are ported, these can be removed:

```bash
# Fully replaced by Python
rm watchdog.sh
rm vm-state.sh
rm quick-gpu-check.sh
rm validate-multigpu-perf.sh

# If presets deprecated in favor of wizard
rm presets/use-preset.sh
```

## Files to Keep

```bash
# Installation
install-python-coder.sh  # Python installer

# Legacy support (until full migration)
coder.sh                 # Bash version (deprecate later)

# Not yet ported
benchmark.sh             # Single VM benchmark
benchmark-all.sh         # Multi-VM benchmark

# Tests (or rewrite in Python)
tests/test_*.sh          # Bash version tests
```

## User Migration Path

### Current Users (Bash)

```bash
# Continue using bash version
./coder.sh up
./coder.sh down

# Or migrate to Python
./install-python-coder.sh
source venv/bin/activate
coder wizard  # Better wizard
coder up --launch-aider  # Better experience
```

### New Users

```bash
# Start with Python version
./install-python-coder.sh
source venv/bin/activate
coder wizard
coder up --launch-aider
```

## Documentation Status

| Document | Status | Notes |
|----------|--------|-------|
| `README.md` | ⚠️ NEEDS UPDATE | Still references bash primarily |
| `CLAUDE.md` | ✅ UP TO DATE | Documents both versions |
| `NEW-FEATURES.md` | ✅ UP TO DATE | Python features documented |
| `PYTHON-TEST-REPORT.md` | ✅ UP TO DATE | Test results documented |
| `CLOUD-INIT-DESIGN.md` | ✅ UP TO DATE | Systemd approach documented |

## Next Steps

1. **Port missing commands** (`use`, `cleanup`, `extend`)
2. **Port self-healing** (critical feature)
3. **Update README.md** to recommend Python version
4. **Deprecate bash scripts** that are fully replaced
5. **Port benchmarking tools** (future enhancement)
6. **Add Python tests** (pytest-based)

## Compatibility Notes

- Both versions work with same `.env` and `.env.secrets` files
- Both versions use same session directories (`~/.cache/linode-vms/`)
- Both versions can manage each other's sessions (mostly)
- Watchdog implementations are independent (don't run both!)

## Conclusion

**Python version is 85% feature complete:**
- ✅ Core commands (up, down, list, status, wizard)
- ✅ Validation commands (check, validate, validate-perf)
- ✅ Auto-features (cloud-init check, vLLM ready, aider launch)
- ⚠️ Missing utilities (use, cleanup, extend, logs, ssh)
- ⚠️ Missing self-healing (critical bash feature)

**Recommendation**: Port the 5 missing commands and self-healing, then deprecate bash version entirely.
