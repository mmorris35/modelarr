# modelarr

Radarr/Sonarr for LLM models. Monitors HuggingFace for new releases matching a watchlist and auto-downloads them to a local library.

## Overview

modelarr automatically discovers and downloads language models from HuggingFace based on a configurable watchlist. It supports multiple watch types (specific models, authors, search queries, model families), filtering by size and format, resumable downloads, disk space management, and Telegram notifications.

## Architecture

```
modelarr CLI (Typer)
├── Watchlist Manager
├── Library Manager
├── Download Engine
└── Monitor (APScheduler)
    ├── SQLite Database
    ├── HuggingFace API
    ├── Local Filesystem
    └── Telegram Notification
```

## Installation

### Requirements
- Python 3.11+
- `uv` for package management

### Setup

```bash
# Clone the repository
git clone https://github.com/user/modelarr.git
cd modelarr

# Install dependencies with uv
uv sync

# Verify installation
uv run modelarr --version
uv run modelarr --help
```

## Quick Start

```bash
# Add a watch for a specific model
uv run modelarr watch add model mlx-community/Qwen2.5-72B-MLX-4bit

# Add a watch for an author's models
uv run modelarr watch add author mlx-community --format mlx --quant 4bit

# Add a search watch
uv run modelarr watch add query "opus distilled" --format gguf

# List all watches
uv run modelarr watch list

# Configure storage path (required)
uv run modelarr config set library_path /path/to/models

# Start monitoring
uv run modelarr monitor start

# Check library
uv run modelarr library list
uv run modelarr library size
```

## Features

- **Smart Watchlist**: Monitor specific models, authors, search queries, or model families
- **Format & Quantization Filtering**: Target specific formats (GGUF, MLX, safetensors) and quantizations (4bit, 8bit, fp16)
- **Resumable Downloads**: Resume interrupted downloads automatically
- **Library Management**: Organize downloaded models, track disk usage
- **Auto-Pruning**: Automatically delete oldest models when disk space is limited
- **Telegram Notifications**: Get notified when new models are found and downloaded
- **Scheduled Monitoring**: Run on a configurable interval (default: hourly)

## Configuration

Configuration is stored in SQLite at `~/.config/modelarr/modelarr.db`.

Key settings:
- `library_path`: Where to store downloaded models (required)
- `interval`: Poll interval in minutes (default: 60)
- `telegram_token`: Bot token for notifications (optional)
- `telegram_chat_id`: Chat ID for notifications (optional)
- `max_storage_gb`: Maximum disk usage (optional)
- `auto_prune`: Auto-delete oldest models when over limit (default: true)

## Development

### Install dev dependencies
```bash
uv sync --extra dev
```

### Run tests
```bash
uv run pytest
```

### Run linter
```bash
uv run ruff check src/ tests/
```

### Run type checker
```bash
uv run mypy src/
```

## License

MIT License - see LICENSE file for details.
