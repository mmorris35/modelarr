"""Dashboard routes for modelarr web UI."""

from datetime import datetime

from fastapi import APIRouter, Depends, Request
from jinja2 import Template

from modelarr.downloader import DownloadManager
from modelarr.store import ModelarrStore
from modelarr.web.deps import format_bytes, get_downloader, get_storage_manager, get_store

router = APIRouter()


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
    storage_usage_pct = 0
    if max_storage_gb:
        max_bytes = int(max_storage_gb) * (1024**3)
        storage_usage_pct = (total_size / max_bytes) * 100

    # Watchlist stats
    watches = store.list_watches(enabled_only=True)
    enabled_watch_count = len(watches)

    # Active downloads
    active_downloads = store.get_active_downloads()

    # Recent activity (last 5 completed/failed)
    recent = store.get_download_history(limit=5)

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
    )
    return Template(html).render()


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
        library_path = Path(library_path_str) if library_path_str else Path.home() / ".modelarr" / "library"
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
            html = f'<div class="toast" style="background-color: var(--form-element-valid-border-color); color: black;"><strong>Success!</strong> Downloaded {result_count} model(s).</div>'
        else:
            html = '<div class="toast"><strong>Check complete.</strong> No new models found.</div>'

        return Template(html).render()

    except Exception as e:
        html = f'<div class="toast" style="background-color: var(--form-element-invalid-border-color); color: white;"><strong>Error:</strong> {str(e)}</div>'
        return Template(html).render()
