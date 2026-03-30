"""FastAPI application for modelarr web UI."""

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Response
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
    interval_minutes = int(store.get_config("interval_minutes") or "60")

    hf_client = HFClient(token=store.get_config("huggingface_token"))
    matcher = WatchlistMatcher(hf_client)

    library_path_str = store.get_config("library_path")
    library_path = Path(library_path_str) if library_path_str else Path.home() / ".modelarr" / "library"
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
        storage_manager = StorageManager(store=store, library_path=library_path, max_bytes=max_bytes)
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
        try:
            _monitor.start()
        except Exception:
            pass

    import threading
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
        try:
            _monitor.stop()
        except Exception:
            pass


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
    app.jinja_env = template_env

    # Health check endpoint
    @app.get("/health")
    async def health():
        return {"status": "ok"}

    # Include route routers
    from modelarr.web.routes.dashboard import router as dashboard_router
    from modelarr.web.routes.library import router as library_router
    from modelarr.web.routes.watchlist import router as watchlist_router
    app.include_router(dashboard_router)
    app.include_router(watchlist_router)
    app.include_router(library_router)

    return app
