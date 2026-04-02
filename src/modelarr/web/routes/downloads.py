"""Downloads routes for modelarr web UI."""

import multiprocessing
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from modelarr.downloader import DownloadManager
from modelarr.hf_client import HFClient
from modelarr.models import DownloadRecord
from modelarr.store import ModelarrStore
from modelarr.web.deps import format_bytes, get_downloader, get_hf_client, get_store

# Local timezone for display
_local_tz = datetime.now(UTC).astimezone().tzinfo


def _enrich_download(dl: DownloadRecord, store: ModelarrStore) -> dict:
    """Add model name and local times to a download record."""
    model = store.get_model_by_id(dl.model_id) if dl.model_id else None
    repo_id = model.repo_id if model else f"model #{dl.model_id}"

    started_local = (
        dl.started_at.replace(tzinfo=UTC).astimezone(_local_tz) if dl.started_at else None
    )
    completed_local = (
        dl.completed_at.replace(tzinfo=UTC).astimezone(_local_tz) if dl.completed_at else None
    )

    pct = 0.0
    if dl.total_bytes and dl.total_bytes > 0 and dl.bytes_downloaded:
        pct = (dl.bytes_downloaded / dl.total_bytes) * 100

    return {
        "id": dl.id,
        "repo_id": repo_id,
        "status": dl.status,
        "bytes_downloaded": dl.bytes_downloaded,
        "total_bytes": dl.total_bytes,
        "pct": pct,
        "started_at": started_local,
        "completed_at": completed_local,
        "error": dl.error,
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


@router.get("/downloads")
async def downloads_page(
    request: Request,
    store: ModelarrStore = Depends(get_store),
    downloader: DownloadManager = Depends(get_downloader),
):
    """Render the downloads page with active + history sections."""
    active_raw = store.get_active_downloads()
    history_raw = store.get_download_history(limit=20)

    active_downloads = [_enrich_download(dl, store) for dl in active_raw]
    history = [_enrich_download(dl, store) for dl in history_raw]

    template = request.app.jinja_env.get_template("downloads.html")
    html = template.render(
        active_downloads=active_downloads,
        history=history,
        format_bytes=format_bytes,
    )
    return HTMLResponse(html)


@router.get("/downloads/active")
async def active_downloads(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Return active downloads as htmx partial (polled every 5s)."""
    active_raw = store.get_active_downloads()
    active = [_enrich_download(dl, store) for dl in active_raw]

    template = request.app.jinja_env.get_template("partials/active_downloads.html")
    html = template.render(active_downloads=active, format_bytes=format_bytes)
    return HTMLResponse(html)


@router.post("/downloads")
async def manual_download(
    request: Request,
    store: ModelarrStore = Depends(get_store),
    hf_client: HFClient = Depends(get_hf_client),
    downloader: DownloadManager = Depends(get_downloader),
):
    """Trigger a manual download by repo_id."""
    try:
        data = await request.form()
        repo_id = str(data.get("repo_id", ""))

        if not repo_id:
            msg = "<strong>Error:</strong> repo_id is required"
            return _toast_html(msg, is_error=True)

        # Dispatch download to subprocess — own GIL, can't block web UI
        from modelarr.db import get_db_path

        def _download_worker(db_path_str: str, repo: str) -> None:
            from pathlib import Path

            from modelarr.downloader import DownloadManager
            from modelarr.hf_client import HFClient as HFC
            from modelarr.store import ModelarrStore as MS

            s = MS(Path(db_path_str))
            hfc = HFC(token=s.get_config("huggingface_token"))
            lp = s.get_config("library_path")
            dm = DownloadManager(
                store=s,
                library_path=Path(lp) if lp else Path.home() / ".modelarr" / "library",
                hf_token=s.get_config("huggingface_token"),
            )
            info = hfc.get_model_info(repo)
            dm.download_model(info)

        multiprocessing.Process(
            target=_download_worker,
            args=(str(get_db_path()), repo_id),
            daemon=True,
        ).start()

        msg = f"<strong>Success!</strong> Download queued for {repo_id}"
        return _toast_html(msg, is_error=False)

    except Exception as e:
        msg = f"<strong>Error:</strong> {str(e)}"
        return _toast_html(msg, is_error=True)
