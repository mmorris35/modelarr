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

## Executor Agents
- Use model: haiku for executor subtasks
- Use model: sonnet for verifier agents
