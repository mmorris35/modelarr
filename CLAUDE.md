# modelarr

Radarr/Sonarr for LLM models. Monitors HuggingFace for new releases matching a watchlist and auto-downloads them to a local library.

## Stack
- Python 3.11+, Typer CLI, SQLite, huggingface_hub, APScheduler, httpx
- Package management: uv
- Testing: pytest
- Linting: ruff
- Source layout: `src/modelarr/`

## Development
- Read `DEVELOPMENT_PLAN.md` before making changes
- Follow subtask IDs when implementing features
- Run `uv run pytest` after every change
- Run `uv run ruff check src/ tests/` before committing
- Use `grep -r "TODO\|FIXME" src/` to verify no stubs remain
- Dev dependencies installed via `uv sync` with `[dependency-groups] dev` in pyproject.toml

## Dependencies
- Production: typer, huggingface-hub, apscheduler, httpx, pydantic, rich
- Development: pytest, pytest-asyncio, ruff, mypy (use `uv sync` to install all)

## Storage Management
- StorageManager handles disk limits and auto-pruning of old models
- Pass StorageManager to DownloadManager.__init__ if storage limits are needed
- Config keys: `storage_auto_prune` (true/false) to enable automatic pruning when over limit

## Monitor Daemon
- Monitor writes PID to `~/.config/modelarr/monitor.pid` on start
- `modelarr monitor stop` sends SIGTERM to the PID
- `modelarr monitor status` checks if monitor process is running
- No background scheduler when using CLI commands directly

## Executor Agents
- Use model: haiku for executor subtasks
- Use model: sonnet for verifier agents
