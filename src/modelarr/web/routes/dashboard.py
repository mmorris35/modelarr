"""Dashboard routes for modelarr web UI."""


from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from modelarr.downloader import DownloadManager
from modelarr.models import DownloadRecord
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


@router.post("/dashboard/check")
async def dashboard_check(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Trigger a monitor check and return results as htmx partial."""
    try:
        from modelarr.downloader import DownloadManager
        from modelarr.hf_client import HFClient
        from modelarr.matcher import WatchlistMatcher
        from modelarr.monitor import ModelarrMonitor
        from modelarr.notifier import TelegramNotifier

        hf_client = HFClient(token=store.get_config("huggingface_token"))
        matcher = WatchlistMatcher(hf_client)

        from pathlib import Path

        library_path_str = store.get_config("library_path")
        if library_path_str:
            library_path = Path(library_path_str)
        else:
            library_path = Path.home() / ".modelarr" / "library"
        downloader = DownloadManager(
            store=store,
            library_path=library_path,
            hf_token=store.get_config("huggingface_token"),
        )

        notifier = TelegramNotifier.from_config(store)
        monitor = ModelarrMonitor(
            store=store,
            matcher=matcher,
            downloader=downloader,
            notifier=notifier,
        )

        results = monitor.run_once()
        result_count = len(results)

        if result_count > 0:
            msg = (
                f"<strong>Success!</strong> Downloaded {result_count} model(s)."
            )
            html = _toast_html(msg, is_error=False)
        else:
            html = (
                '<div class="toast"><strong>Check complete.</strong>'
                " No new models found.</div>"
            )

        return HTMLResponse(html)

    except Exception as e:
        msg = f"<strong>Error:</strong> {str(e)}"
        html = _toast_html(msg, is_error=True)
        return HTMLResponse(html)
