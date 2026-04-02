"""Dashboard routes for modelarr web UI."""

import contextlib
import threading
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from modelarr.downloader import DownloadManager
from modelarr.models import DownloadRecord
from modelarr.ollama import OllamaClient
from modelarr.store import ModelarrStore
from modelarr.web.deps import format_bytes, get_downloader, get_store

_local_tz = datetime.now(UTC).astimezone().tzinfo


def _enrich(dl: DownloadRecord, store: ModelarrStore) -> dict:
    """Add model name and local times to a download record."""
    model = store.get_model_by_id(dl.model_id) if dl.model_id else None
    repo_id = model.repo_id if model else f"model #{dl.model_id}"
    started = (
        dl.started_at.replace(tzinfo=UTC).astimezone(_local_tz)
        if dl.started_at else None
    )
    completed = (
        dl.completed_at.replace(tzinfo=UTC).astimezone(_local_tz)
        if dl.completed_at else None
    )
    pct = 0.0
    if dl.total_bytes and dl.total_bytes > 0 and dl.bytes_downloaded:
        pct = (dl.bytes_downloaded / dl.total_bytes) * 100
    return {
        "repo_id": repo_id,
        "status": dl.status,
        "bytes_downloaded": dl.bytes_downloaded,
        "total_bytes": dl.total_bytes,
        "pct": pct,
        "started_at": started,
        "completed_at": completed,
        "error": dl.error,
        "size": format_bytes(dl.total_bytes),
    }


def _toast_html(message: str, is_error: bool = False) -> str:
    """Generate a toast HTML fragment."""
    color = "var(--form-element-invalid-border-color)" if is_error else (
        "var(--form-element-valid-border-color)"
    )
    text_color = "white" if is_error else "black"
    return (
        f'<div class="toast" style="background-color: {color}; color: {text_color};">'
        f"{message}</div>"
    )


router = APIRouter(default_response_class=HTMLResponse)


@router.get("/")
async def dashboard(
    request: Request,
    store: ModelarrStore = Depends(get_store),
    downloader: DownloadManager = Depends(get_downloader),
):
    """Render the dashboard page."""
    # Monitor status
    from modelarr.monitor import ModelarrMonitor

    is_running = ModelarrMonitor.is_running()
    interval = store.get_config("interval_minutes") or "60"

    # Library stats
    models = downloader.list_local_models()
    model_count = len(models)
    total_size = downloader.get_library_size()

    # Storage stats
    max_storage_gb = store.get_config("max_storage_gb")
    storage_usage_pct: float = 0.0
    if max_storage_gb:
        max_bytes = int(max_storage_gb) * (1024**3)
        storage_usage_pct = (total_size / max_bytes) * 100

    # Watchlist stats
    watches = store.list_watches(enabled_only=True)
    enabled_watch_count = len(watches)

    # Active downloads
    active_downloads = [_enrich(dl, store) for dl in store.get_active_downloads()]

    # Recent activity (last 5 completed/failed)
    recent = [_enrich(dl, store) for dl in store.get_download_history(limit=5)]

    # Render template
    template = request.app.jinja_env.get_template("dashboard.html")
    html = template.render(
        is_running=is_running,
        interval=interval,
        model_count=model_count,
        total_size=format_bytes(total_size),
        total_size_raw=total_size,
        max_storage_gb=max_storage_gb or "None",
        storage_usage_pct=storage_usage_pct,
        enabled_watch_count=enabled_watch_count,
        active_downloads=active_downloads,
        recent=recent,
        format_bytes=format_bytes,
    )
    return HTMLResponse(html)


def _build_monitor(store: ModelarrStore) -> Any:
    """Build a ModelarrMonitor from store config."""
    from pathlib import Path

    from modelarr.hf_client import HFClient
    from modelarr.matcher import WatchlistMatcher
    from modelarr.monitor import ModelarrMonitor
    from modelarr.notifier import TelegramNotifier

    hf_client = HFClient(token=store.get_config("huggingface_token"))
    matcher = WatchlistMatcher(hf_client)
    library_path_str = store.get_config("library_path")
    library_path = (
        Path(library_path_str) if library_path_str
        else Path.home() / ".modelarr" / "library"
    )
    downloader = DownloadManager(
        store=store,
        library_path=library_path,
        hf_token=store.get_config("huggingface_token"),
    )
    notifier = TelegramNotifier.from_config(store)
    return ModelarrMonitor(
        store=store, matcher=matcher, downloader=downloader, notifier=notifier,
    )


@router.post("/dashboard/check")
async def dashboard_check(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Trigger a monitor check and return results as htmx partial."""
    try:
        monitor = _build_monitor(store)
        results = monitor.run_once()

        if len(results) > 0:
            msg = f"<strong>Success!</strong> Downloaded {len(results)} model(s)."
            return HTMLResponse(_toast_html(msg, is_error=False))

        return HTMLResponse(
            '<div class="toast"><strong>Check complete.</strong>'
            " No new models found.</div>"
        )

    except Exception as e:
        return HTMLResponse(_toast_html(f"<strong>Error:</strong> {e}", is_error=True))


@router.post("/dashboard/backfill")
async def dashboard_backfill(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Download all matching models from watchlist (backfill)."""
    try:
        monitor = _build_monitor(store)

        # Find matches without downloading (just the match phase)
        matches = monitor.matcher.find_new_models(store, backfill=True)

        if not matches:
            return HTMLResponse(
                '<div class="toast"><strong>Backfill complete.</strong>'
                " All matching models already downloaded.</div>"
            )

        # Create all model + download records upfront as "queued"
        # so they appear on the Downloads page immediately
        from datetime import UTC, datetime

        queued_items: list[tuple[Any, Any, int]] = []
        for watch, model_info in matches:
            model_record = store.upsert_model(
                repo_id=model_info.repo_id,
                author=model_info.author,
                name=model_info.name,
                format_=model_info.format,
                quantization=model_info.quantization,
                size_bytes=model_info.size_bytes,
            )
            dl = store.create_download(
                model_id=model_record.id,
                status="queued",
                started_at=datetime.now(UTC),
                total_bytes=model_info.size_bytes,
            )
            queued_items.append((watch, model_info, dl.id))

        # Process queue in background — one at a time
        def run_backfill() -> None:
            for watch, model_info, _dl_id in queued_items:
                with contextlib.suppress(Exception):
                    monitor.downloader.download_model(model_info, watch)

        threading.Thread(target=run_backfill, daemon=True).start()

        msg = (
            f"<strong>Backfill started!</strong> "
            f"Queued {len(queued_items)} model(s). "
            f"Check the <a href='/downloads'>Downloads</a> page for progress."
        )
        return HTMLResponse(_toast_html(msg, is_error=False))

    except Exception as e:
        return HTMLResponse(_toast_html(f"<strong>Error:</strong> {e}", is_error=True))


@router.get("/ollama/status")
async def ollama_status(
    store: ModelarrStore = Depends(get_store),
):
    """Get Ollama connection status as htmx partial."""
    ollama_host = store.get_config("ollama_host")

    if not ollama_host:
        return HTMLResponse(
            '<div class="stat-label">Ollama</div>'
            '<div class="stat-value" style="font-size: 1.2rem;">'
            'Not configured</div>'
            '<small><a href="/settings">Configure</a></small>'
        )

    client = OllamaClient(host=ollama_host)

    if client.is_connected():
        models = client.list_models()
        return HTMLResponse(
            '<div class="stat-label">Ollama</div>'
            f'<div class="stat-value" style="font-size: 1.2rem;">'
            f'<span style="color: var(--form-element-valid-border-color);">'
            f'Connected</span></div>'
            f'<small>{len(models)} model(s) loaded</small>'
        )
    else:
        return HTMLResponse(
            '<div class="stat-label">Ollama</div>'
            '<div class="stat-value" style="font-size: 1.2rem;">'
            '<span style="color: var(--form-element-invalid-border-color);">'
            'Disconnected</span></div>'
            f'<small>{ollama_host}</small>'
        )
