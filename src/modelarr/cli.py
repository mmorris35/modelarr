"""Typer CLI application for modelarr."""

from pathlib import Path

import typer
import uvicorn
from rich.console import Console
from rich.table import Table

from modelarr import __version__
from modelarr.db import get_db_path
from modelarr.downloader import DownloadManager
from modelarr.hf_client import HFClient
from modelarr.matcher import WatchlistMatcher
from modelarr.models import WatchlistFilters
from modelarr.monitor import ModelarrMonitor
from modelarr.notifier import TelegramNotifier
from modelarr.store import ModelarrStore
from modelarr.web.app import create_app

console = Console()

app = typer.Typer(
    help=(
        "modelarr - Radarr/Sonarr for LLM models. Monitors HuggingFace for "
        "new releases matching a watchlist and auto-downloads them to a "
        "local library."
    )
)

# Sub-apps for command groups
watch_app = typer.Typer(help="Manage watchlist entries")
library_app = typer.Typer(help="Manage local model library")
download_app = typer.Typer(help="Download models")
monitor_app = typer.Typer(help="Monitor and scheduling")
config_app = typer.Typer(help="Configuration management")

app.add_typer(watch_app, name="watch")
app.add_typer(library_app, name="library")
app.add_typer(download_app, name="download")
app.add_typer(monitor_app, name="monitor")
app.add_typer(config_app, name="config")


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"modelarr {__version__}")
        raise typer.Exit()


def _get_store() -> ModelarrStore:
    """Get or create the store instance."""
    db_path = get_db_path()
    return ModelarrStore(db_path)


def _format_bytes(bytes_: int | None) -> str:
    """Format bytes as human-readable string."""
    if bytes_ is None:
        return "Unknown"
    size = float(bytes_)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    """modelarr - Radarr/Sonarr for LLM models."""
    pass


@app.command()
def serve(
    host: str = typer.Option("0.0.0.0", help="Bind address"),
    port: int = typer.Option(8585, help="Port"),
    interval: int = typer.Option(60, "--interval", "-i", help="Monitor poll interval in minutes"),
) -> None:
    """Start the web UI with embedded monitor."""
    try:
        # Store interval in config before starting
        store = _get_store()
        store.set_config("interval_minutes", str(interval))

        app = create_app()
        console.print(f"[green]✓[/green] Starting modelarr web UI on {host}:{port}")
        console.print(f"[cyan]Monitor interval: {interval} minutes[/cyan]")
        console.print("[yellow]Press Ctrl+C to stop[/yellow]")
        uvicorn.run(app, host=host, port=port, log_level="info")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


def _is_configured() -> bool:
    """Check if modelarr has been configured (library_path is set)."""
    store = _get_store()
    return store.get_config("library_path") is not None


@app.command()
def init() -> None:
    """Run the first-time setup wizard."""
    store = _get_store()

    existing = store.get_config("library_path")
    if existing:
        console.print(f"[yellow]modelarr is already configured (library: {existing})[/yellow]")
        if not typer.confirm("Re-run setup?", default=False):
            return

    console.print()
    console.print("[bold cyan]Welcome to modelarr![/bold cyan]")
    console.print("Let's configure your model library.\n")

    # 1. Library path (required)
    default_path = "~/models"
    library_input = typer.prompt(
        "Where should models be stored?",
        default=default_path,
    )
    library_path = str(Path(library_input).expanduser())
    store.set_config("library_path", library_path)
    console.print(f"  [green]✓[/green] Library path: {library_path}")

    # 2. Storage limit (optional)
    console.print()
    if typer.confirm("Set a disk usage limit?", default=False):
        max_gb = typer.prompt("Maximum storage (GB)", type=int)
        store.set_config("max_storage_gb", str(max_gb))
        console.print(f"  [green]✓[/green] Storage limit: {max_gb} GB")

        # 3. Auto-prune (only if limit set)
        if typer.confirm("Auto-delete oldest models when over limit?", default=True):
            store.set_config("storage_auto_prune", "true")
            console.print("  [green]✓[/green] Auto-prune: enabled")
        else:
            store.set_config("storage_auto_prune", "false")

    # 4. HuggingFace token (optional)
    console.print()
    if typer.confirm("Add a HuggingFace token? (for private/gated models)", default=False):
        hf_token = typer.prompt("HuggingFace token", hide_input=True)
        store.set_config("huggingface_token", hf_token)
        console.print("  [green]✓[/green] HuggingFace token saved")

    # 5. Telegram notifications (optional)
    console.print()
    if typer.confirm("Enable Telegram notifications?", default=False):
        bot_token = typer.prompt("Telegram bot token")
        chat_id = typer.prompt("Telegram chat ID")
        store.set_config("telegram_bot_token", bot_token)
        store.set_config("telegram_chat_id", chat_id)
        console.print("  [green]✓[/green] Telegram notifications configured")

    # 6. Poll interval (optional)
    console.print()
    interval = typer.prompt("Poll interval in minutes", default=60, type=int)
    store.set_config("interval_minutes", str(interval))
    console.print(f"  [green]✓[/green] Poll interval: {interval} minutes")

    # Summary
    console.print()
    console.print("[bold green]Setup complete![/bold green]")
    console.print()
    console.print("Next steps:")
    console.print("  [cyan]modelarr watch add model[/cyan] <repo_id>  — add a model to watch")
    console.print("  [cyan]modelarr watch add author[/cyan] <name>    — watch an author")
    console.print("  [cyan]modelarr monitor check[/cyan]              — run a check now")
    console.print("  [cyan]modelarr config show[/cyan]                — view your config")


# ============================================================================
# WATCH COMMANDS
# ============================================================================


@watch_app.command()
def add(
    type_: str = typer.Argument(
        ..., help="Type of watch: model, author, query, or family"
    ),
    value: str = typer.Argument(..., help="Value to watch"),
    format_: str | None = typer.Option(
        None, "--format", "-f", help="Filter by format (e.g., gguf, mlx)"
    ),
    quant: str | None = typer.Option(
        None, "--quant", "-q", help="Filter by quantization (e.g., 4bit, 8bit)"
    ),
    min_size: int | None = typer.Option(
        None, "--min-size", help="Minimum size in GB"
    ),
    max_size: int | None = typer.Option(
        None, "--max-size", help="Maximum size in GB"
    ),
) -> None:
    """Add a watchlist entry."""
    try:
        store = _get_store()

        # Parse formats and quantizations
        formats = [format_] if format_ else None
        quantizations = [quant] if quant else None

        # Convert sizes from GB to bytes
        min_size_b = min_size * (1024**3) if min_size else None
        max_size_b = max_size * (1024**3) if max_size else None

        filters = WatchlistFilters(
            min_size_b=min_size_b,
            max_size_b=max_size_b,
            formats=formats,
            quantizations=quantizations,
        )

        entry = store.add_watch(type_=type_, value=value, filters=filters)

        console.print(
            f"[green]✓[/green] Added {type_} watch: {value} (ID: {entry.id})"
        )
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@watch_app.command("list")
def watch_list(enabled_only: bool = typer.Option(False, "--enabled-only", "-e")) -> None:
    """List watchlist entries."""
    try:
        store = _get_store()
        entries = store.list_watches(enabled_only=enabled_only)

        if not entries:
            console.print("[yellow]No watchlist entries found.[/yellow]")
            return

        table = Table(title="Watchlist Entries")
        table.add_column("ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Value", style="green")
        table.add_column("Filters", style="blue")
        table.add_column("Enabled", style="yellow")
        table.add_column("Created", style="white")

        for entry in entries:
            filters_str = ""
            if entry.filters.formats:
                filters_str += f"fmt:{','.join(entry.filters.formats)} "
            if entry.filters.quantizations:
                filters_str += f"quant:{','.join(entry.filters.quantizations)} "
            if entry.filters.min_size_b:
                filters_str += f"min:{_format_bytes(entry.filters.min_size_b)} "
            if entry.filters.max_size_b:
                filters_str += f"max:{_format_bytes(entry.filters.max_size_b)}"

            table.add_row(
                str(entry.id),
                entry.type,
                entry.value,
                filters_str or "(none)",
                "✓" if entry.enabled else "✗",
                entry.created_at.strftime("%Y-%m-%d"),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@watch_app.command("remove")
def watch_remove(watch_id: int = typer.Argument(..., help="ID of watch to remove")) -> None:
    """Remove a watchlist entry."""
    try:
        store = _get_store()
        if store.remove_watch(watch_id):
            console.print(f"[green]✓[/green] Removed watch ID {watch_id}")
        else:
            console.print(f"[red]Error:[/red] Watch ID {watch_id} not found")
            raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@watch_app.command()
def toggle(watch_id: int = typer.Argument(..., help="ID of watch to toggle")) -> None:
    """Toggle enabled state of a watchlist entry."""
    try:
        store = _get_store()
        if store.toggle_watch(watch_id):
            entry = store.get_watch(watch_id)
            if entry is None:
                console.print(f"[red]Error:[/red] Watch ID {watch_id} not found")
                raise typer.Exit(code=1) from None
            status = "enabled" if entry.enabled else "disabled"
            console.print(f"[green]✓[/green] Watch ID {watch_id} {status}")
        else:
            console.print(f"[red]Error:[/red] Watch ID {watch_id} not found")
            raise typer.Exit(code=1) from None
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


# ============================================================================
# LIBRARY COMMANDS
# ============================================================================


@library_app.command("list")
def library_list(
    format_filter: str | None = typer.Option(
        None, "--format", "-f", help="Filter by format"
    ),
    sort: str = typer.Option(
        "date",
        "--sort",
        "-s",
        help="Sort by: date (default), size, or name",
    ),
) -> None:
    """List downloaded models in library."""
    try:
        store = _get_store()
        downloader = DownloadManager(
            store=store,
            library_path=Path(store.get_config("library_path") or "~/.modelarr/library"),
        )

        models = downloader.list_local_models()

        if format_filter:
            models = [m for m in models if m.format == format_filter]

        if not models:
            console.print("[yellow]No downloaded models found.[/yellow]")
            return

        # Sort by specified key
        if sort == "size":
            models.sort(key=lambda m: m.size_bytes or 0, reverse=True)
        elif sort == "name":
            models.sort(key=lambda m: m.name)
        else:  # date
            models.sort(key=lambda m: m.downloaded_at or m.id, reverse=True)

        table = Table(title="Downloaded Models")
        table.add_column("Repo ID", style="cyan")
        table.add_column("Size", style="green")
        table.add_column("Format", style="magenta")
        table.add_column("Quantization", style="blue")
        table.add_column("Downloaded", style="yellow")

        for model in models:
            table.add_row(
                model.repo_id,
                _format_bytes(model.size_bytes),
                model.format or "—",
                model.quantization or "—",
                (
                    model.downloaded_at.strftime("%Y-%m-%d %H:%M")
                    if model.downloaded_at
                    else "—"
                ),
            )

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@library_app.command()
def size() -> None:
    """Show total library size."""
    try:
        store = _get_store()
        downloader = DownloadManager(
            store=store,
            library_path=Path(store.get_config("library_path") or "~/.modelarr/library"),
        )

        total_bytes = downloader.get_library_size()
        models = downloader.list_local_models()

        console.print(
            f"[cyan]Total:[/cyan] {_format_bytes(total_bytes)} across {len(models)} models"
        )

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@library_app.command()
def remove(
    repo_id: str = typer.Argument(..., help="Repository ID to remove"),
    confirm: bool = typer.Option(
        False, "--confirm", "-y", help="Skip confirmation prompt"
    ),
) -> None:
    """Remove a downloaded model from the library."""
    try:
        store = _get_store()
        downloader = DownloadManager(
            store=store,
            library_path=Path(store.get_config("library_path") or "~/.modelarr/library"),
        )

        model = store.get_model_by_repo(repo_id)
        if not model or not model.local_path:
            console.print(
                f"[red]Error:[/red] Model {repo_id} not found or not downloaded"
            )
            raise typer.Exit(code=1) from None

        if not confirm:
            console.print(
                f"[yellow]Delete {repo_id}? ({_format_bytes(model.size_bytes)})[/yellow]"
            )
            if not typer.confirm("Continue?"):
                console.print("[yellow]Cancelled.[/yellow]")
                return

        if downloader.delete_local_model(repo_id):
            console.print(f"[green]✓[/green] Deleted {repo_id}")
        else:
            console.print(f"[red]Error:[/red] Failed to delete {repo_id}")
            raise typer.Exit(code=1) from None

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


# ============================================================================
# DOWNLOAD COMMANDS
# ============================================================================


@download_app.command("download")
def cmd_download_model(
    repo_id: str = typer.Argument(..., help="HuggingFace repo ID to download"),
) -> None:
    """Download a model manually."""
    try:
        store = _get_store()
        hf_client = HFClient(token=store.get_config("huggingface_token"))
        downloader = DownloadManager(
            store=store,
            library_path=Path(store.get_config("library_path") or "~/.modelarr/library"),
            hf_token=store.get_config("huggingface_token"),
        )

        console.print(f"[cyan]Fetching model info for {repo_id}...[/cyan]")
        model_info = hf_client.get_model_info(repo_id)

        console.print(f"[cyan]Downloading {repo_id}...[/cyan]")
        download = downloader.download_model(model_info)

        if download.status == "complete":
            console.print(
                f"[green]✓[/green] Downloaded {repo_id} ({_format_bytes(download.total_bytes)})"
            )
        else:
            console.print(
                f"[red]✗[/red] Download failed: {download.error}"
            )
            raise typer.Exit(code=1) from None

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@download_app.command("status")
def download_status() -> None:
    """Show download status."""
    try:
        store = _get_store()

        active = store.get_active_downloads()
        history = store.get_download_history(limit=10)

        if active:
            table = Table(title="Active Downloads")
            table.add_column("ID", style="cyan")
            table.add_column("Model ID", style="magenta")
            table.add_column("Status", style="yellow")
            table.add_column("Progress", style="green")
            table.add_column("Started", style="blue")

            for dl in active:
                if dl.total_bytes and dl.total_bytes > 0:
                    pct = (dl.bytes_downloaded or 0) / dl.total_bytes * 100
                    downloaded_str = _format_bytes(dl.bytes_downloaded)
                    total_str = _format_bytes(dl.total_bytes)
                    progress = f"{pct:.1f}% ({downloaded_str} / {total_str})"
                else:
                    progress = "—"

                table.add_row(
                    str(dl.id),
                    str(dl.model_id),
                    dl.status,
                    progress,
                    (
                        dl.started_at.strftime("%H:%M:%S")
                        if dl.started_at
                        else "—"
                    ),
                )

            console.print(table)
        else:
            console.print("[yellow]No active downloads.[/yellow]")

        if history:
            table = Table(title="Recent Downloads")
            table.add_column("ID", style="cyan")
            table.add_column("Model ID", style="magenta")
            table.add_column("Status", style="yellow")
            table.add_column("Completed", style="blue")

            for dl in history[:5]:
                table.add_row(
                    str(dl.id),
                    str(dl.model_id),
                    dl.status,
                    (
                        dl.completed_at.strftime("%Y-%m-%d %H:%M")
                        if dl.completed_at
                        else "—"
                    ),
                )

            console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


# ============================================================================
# MONITOR COMMANDS
# ============================================================================


@monitor_app.command()
def start(
    interval: int = typer.Option(60, "--interval", "-i", help="Poll interval in minutes"),
    daemon: bool = typer.Option(False, "--daemon", "-d", help="Run in background"),
) -> None:
    """Start the monitoring scheduler."""
    try:
        store = _get_store()
        store.set_config("interval_minutes", str(interval))

        hf_client = HFClient(token=store.get_config("huggingface_token"))
        matcher = WatchlistMatcher(hf_client)
        downloader = DownloadManager(
            store=store,
            library_path=Path(store.get_config("library_path") or "~/.modelarr/library"),
            hf_token=store.get_config("huggingface_token"),
        )
        notifier = TelegramNotifier.from_config(store)

        monitor = ModelarrMonitor(
            store=store,
            matcher=matcher,
            downloader=downloader,
            notifier=notifier,
            interval_minutes=interval,
        )

        monitor.start()
        console.print(
            f"[green]✓[/green] Monitor started (polling every {interval} minutes)"
        )

        if not daemon:
            console.print("[yellow]Press Ctrl+C to stop[/yellow]")
            try:
                import time
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                monitor.stop()
                console.print("[green]✓[/green] Monitor stopped")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@monitor_app.command()
def stop() -> None:
    """Stop the monitoring scheduler."""
    try:
        if ModelarrMonitor.stop_by_pid():
            console.print("[green]✓[/green] Monitor stopped")
        else:
            console.print("[yellow]No running monitor found[/yellow]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@monitor_app.command("status")
def monitor_status() -> None:
    """Show monitor status."""
    try:
        store = _get_store()
        interval = store.get_config("interval_minutes", "60")

        is_running = ModelarrMonitor.is_running()
        status = "[green]Running[/green]" if is_running else "[yellow]Stopped[/yellow]"

        console.print("[cyan]Monitor Status:[/cyan]")
        console.print(f"  Status: {status}")
        console.print(f"  Interval: {interval} minutes")

        watches = store.list_watches(enabled_only=True)
        console.print(f"  Enabled watches: {len(watches)}")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@monitor_app.command()
def check() -> None:
    """Run a single monitor check cycle."""
    try:
        store = _get_store()

        hf_client = HFClient(token=store.get_config("huggingface_token"))
        matcher = WatchlistMatcher(hf_client)
        downloader = DownloadManager(
            store=store,
            library_path=Path(store.get_config("library_path") or "~/.modelarr/library"),
            hf_token=store.get_config("huggingface_token"),
        )
        notifier = TelegramNotifier.from_config(store)

        monitor = ModelarrMonitor(
            store=store,
            matcher=matcher,
            downloader=downloader,
            notifier=notifier,
        )

        console.print("[cyan]Running monitor check...[/cyan]")
        results = monitor.run_once()

        if results:
            console.print(f"[green]✓[/green] Downloaded {len(results)} model(s)")
            for _watch, model in results:
                console.print(
                    f"  - {model.author}/{model.name} ({_format_bytes(model.size_bytes)})"
                )
        else:
            console.print("[yellow]No new models found.[/yellow]")

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


# ============================================================================
# CONFIG COMMANDS
# ============================================================================


@config_app.command("set")
def config_set(
    key: str = typer.Argument(..., help="Configuration key"),
    value: str = typer.Argument(..., help="Configuration value"),
) -> None:
    """Set a configuration value."""
    try:
        store = _get_store()
        store.set_config(key, value)
        console.print(f"[green]✓[/green] Set {key} = {value}")
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None


@config_app.command()
def show() -> None:
    """Show all configuration values."""
    try:
        store = _get_store()

        # Get all config keys from the database
        conn = store._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT key, value FROM config ORDER BY key")
        rows = cursor.fetchall()
        conn.close()

        if not rows:
            console.print("[yellow]No configuration set.[/yellow]")
            return

        table = Table(title="Configuration")
        table.add_column("Key", style="cyan")
        table.add_column("Value", style="green")

        for row in rows:
            # Hide sensitive values
            key = row[0]
            value = row[1]
            if "token" in key.lower() or "password" in key.lower():
                value = "***hidden***"
            table.add_row(key, value)

        console.print(table)

    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        raise typer.Exit(code=1) from None
