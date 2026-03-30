"""FastAPI application for modelarr web UI."""

import threading
from contextlib import asynccontextmanager, suppress
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jinja2 import Environment, FileSystemLoader

from modelarr import __version__
from modelarr.db import get_db_path
from modelarr.downloader import DownloadManager
from modelarr.hf_client import HFClient
from modelarr.matcher import WatchlistMatcher
from modelarr.monitor import ModelarrMonitor
from modelarr.notifier import TelegramNotifier
from modelarr.storage import StorageManager
from modelarr.store import ModelarrStore

# Global monitor instance managed by lifespan
_monitor: ModelarrMonitor | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """FastAPI lifespan context manager for starting/stopping the monitor."""
    global _monitor

    # Startup
    store = ModelarrStore(get_db_path())

    # Clean up stale downloads from before a crash/reboot
    for stale in store.get_active_downloads():
        store.update_download(
            stale.id, status="failed", error="Interrupted by restart"
        )

    interval_minutes = int(store.get_config("interval_minutes") or "60")

    hf_client = HFClient(token=store.get_config("huggingface_token"))
    matcher = WatchlistMatcher(hf_client)

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

    max_storage_gb = store.get_config("max_storage_gb")
    storage_manager = None
    if max_storage_gb:
        max_bytes = int(max_storage_gb) * (1024**3)
        storage_manager = StorageManager(
            store=store, library_path=library_path, max_bytes=max_bytes
        )
        downloader.storage_manager = storage_manager

    _monitor = ModelarrMonitor(
        store=store,
        matcher=matcher,
        downloader=downloader,
        notifier=notifier,
        interval_minutes=interval_minutes,
    )

    # Run monitor in a background thread (non-blocking)
    def run_monitor():
        with suppress(Exception):
            _monitor.start()

    monitor_thread = threading.Thread(target=run_monitor, daemon=True)
    monitor_thread.start()

    # Store in app state for route access
    app.state.store = store
    app.state.monitor = _monitor
    app.state.hf_client = hf_client
    app.state.downloader = downloader
    app.state.storage_manager = storage_manager

    yield

    # Shutdown
    if _monitor:
        with suppress(Exception):
            _monitor.stop()


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="modelarr",
        description="Radarr/Sonarr for LLM models",
        version=__version__,
        lifespan=lifespan,
    )

    # Mount static files
    static_dir = Path(__file__).parent / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Configure Jinja2 templates
    templates_dir = Path(__file__).parent / "templates"
    template_env = Environment(
        loader=FileSystemLoader(str(templates_dir)),
        autoescape=True,
    )
    app.jinja_env = template_env  # type: ignore[attr-defined]

    # Health check endpoint
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Include route routers
    from modelarr.web.routes.dashboard import router as dashboard_router
    from modelarr.web.routes.downloads import router as downloads_router
    from modelarr.web.routes.library import router as library_router
    from modelarr.web.routes.search import router as search_router
    from modelarr.web.routes.settings import router as settings_router
    from modelarr.web.routes.watchlist import router as watchlist_router
    app.include_router(dashboard_router)
    app.include_router(watchlist_router)
    app.include_router(library_router)
    app.include_router(downloads_router)
    app.include_router(settings_router)
    app.include_router(search_router)

    # Error handlers
    @app.exception_handler(404)
    async def not_found_handler(request: Request, exc):
        template = app.jinja_env.get_template("404.html")  # type: ignore[attr-defined]
        return HTMLResponse(template.render(request=request), status_code=404)

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        template = app.jinja_env.get_template("500.html")  # type: ignore[attr-defined]
        return HTMLResponse(template.render(request=request), status_code=500)

    return app
