# Repository Guidelines

## Project Structure & Module Organization
- `coder.sh`: primary launcher CLI for creating, managing, and tearing down Linode GPU VMs.
- `presets/`: GPU configuration presets (`*.env`) and `use-preset.sh` helper.
- `benchmark.sh`, `benchmark-all.sh`: single-VM and multi-VM benchmarking scripts.
- `benchmark-results/`: benchmark output artifacts.
- `.env.example`, `.env.secrets.example`: configuration templates; real secrets live in `.env.secrets` (git-ignored).

## Build, Test, and Development Commands
- `./coder validate`: sanity-check `.env` and show cost estimate without creating a VM.
- `./coder up` / `./coder go`: provision VM and set up SSH tunnel (go is fully automated).
- `./coder check`: readiness checks against a running VM.
- `./coder down`: teardown VM, close tunnel, and report session cost.
- `./presets/use-preset.sh list`: list available GPU presets.
- `./presets/use-preset.sh rtx6000-2gpu`: apply a preset while preserving secrets.
- `./benchmark.sh`: benchmark the current deployment.
- `./benchmark-all.sh --dry-run`: preview the full benchmark matrix.

## Coding Style & Naming Conventions
- Shell scripts use `bash` with `set -euo pipefail`; keep changes POSIX-friendly.
- Prefer clear, action-oriented function names and uppercase env var names.
- Keep new files ASCII unless an existing file requires Unicode.
- Run formatting/linting with `shellcheck` before PRs when possible.

## Testing Guidelines
- Lint: `shellcheck coder.sh presets/use-preset.sh`
- Syntax check: `bash -n coder.sh` and `bash -n presets/use-preset.sh`
- Preset validation example:
  ```bash
  for preset in presets/*.env; do grep -q "^TYPE=" "$preset"; done
  ```
- Benchmarks are optional and cost-incurring; use `--dry-run` first.

## Commit & Pull Request Guidelines
- Commit messages follow Conventional Commits (e.g., `feat:`, `fix:`, `docs:`).
- Update `CLAUDE.MD` when changing functionality or workflow docs.
- PRs should include: purpose, key commands run, and any cost-impacting changes.
- Never commit secrets; use `.env.secrets` and verify with `git check-ignore .env.secrets`.

## Security & Configuration Tips
- Keep services bound to localhost and access via SSH tunnel only.
- Store tokens in `.env.secrets` or `op://` 1Password references.
