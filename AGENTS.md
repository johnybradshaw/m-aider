# Repository Guidelines

## Project Structure & Module Organization
- `src/maider/`: Python CLI implementation (commands, providers, SSH, sessions, healing).
- `src/maider/commands/` and `src/maider/providers/`: subcommand handlers and cloud backends.
- `tests/`: pytest suite (`test_*.py`), with shared fixtures in `tests/conftest.py`.
- `docs/`: design notes and contributor docs; `CLAUDE.MD` is the canonical architecture/feature reference.
- `coder.sh`: legacy bash launcher (still supported but secondary).
- `.env`, `.env.secrets`, `.env.example`: runtime configuration; secrets must stay out of git.

## Build, Test, and Development Commands
- `./install-python-coder.sh`: creates a local virtualenv and installs the CLI.
- `source venv/bin/activate`: activate the project venv.
- `maider wizard` (or `coder wizard`): interactive config setup.
- `maider validate`: validate `.env` before provisioning.
- `maider up --launch-aider` / `maider down`: create and destroy VMs.
- `pytest`: run the test suite (see markers below).
- `ruff check .` and `black .`: lint and format (use before PRs).

## Coding Style & Naming Conventions
- Python code uses 4-space indentation and Black formatting (line length 100).
- Ruff provides linting; prefer explicit imports and clear error handling.
- Use `snake_case` for functions/variables, `PascalCase` for classes, and `UPPER_SNAKE_CASE` for env vars.
- Keep new files ASCII unless an existing file already uses Unicode.

## Testing Guidelines
- Framework: pytest (configured in `pytest.ini`).
- Naming: `test_*.py` files, `Test*` classes, `test_*` functions.
- Markers: `unit`, `integration` (needs API access), `slow` (VM/network).
- Example: `pytest -m "not integration"` for local-only runs.

## Commit & Pull Request Guidelines
- Git history mixes plain messages and Conventional Commits; use short, imperative subjects, and prefer `feat:`/`fix:`/`docs:` when it fits.
- Always create a new branch before making changes; never work directly on `main`.
- Include context, key commands run, and any cost-impacting changes in PR descriptions.
- Update `CLAUDE.MD` when behavior, workflows, or architecture changes.
- Never commit secrets; verify with `git check-ignore .env.secrets`.

## Security & Configuration Tips
- Services bind to localhost on the VM; access via SSH tunnel only.
- Store tokens in `.env.secrets` or 1Password `op://` references.
- Session state lives in `~/.cache/linode-vms/`; avoid committing artifacts from there.
