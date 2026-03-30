"""Downloads routes for modelarr web UI."""

from pathlib import Path

from fastapi import APIRouter, Depends, Request
from jinja2 import Template

from modelarr.downloader import DownloadManager
from modelarr.hf_client import HFClient
from modelarr.store import ModelarrStore
from modelarr.web.deps import format_bytes, get_downloader, get_hf_client, get_store

router = APIRouter()


@router.get("/downloads")
async def downloads_page(
    request: Request,
    store: ModelarrStore = Depends(get_store),
    downloader: DownloadManager = Depends(get_downloader),
):
    """Render the downloads page with active + history sections."""
    active_downloads = store.get_active_downloads()
    history = store.get_download_history(limit=20)

    template = request.app.jinja_env.get_template("downloads.html")
    html = template.render(
        active_downloads=active_downloads,
        history=history,
        format_bytes=format_bytes,
    )
    return Template(html).render()


@router.get("/downloads/active")
async def active_downloads(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Return active downloads as htmx partial (polled every 5s)."""
    active = store.get_active_downloads()

    template = request.app.jinja_env.get_template("partials/active_downloads.html")
    html = template.render(active_downloads=active, format_bytes=format_bytes)
    return Template(html).render()


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
        repo_id = data.get("repo_id")

        if not repo_id:
            return '<div class="toast" style="background-color: var(--form-element-invalid-border-color); color: white;"><strong>Error:</strong> repo_id is required</div>'

        # Fetch model info
        model_info = hf_client.get_model_info(repo_id)

        # Dispatch download to thread pool
        downloader.download_model(model_info)

        return '<div class="toast" style="background-color: var(--form-element-valid-border-color); color: black;"><strong>Success!</strong> Download queued for ' + repo_id + '</div>'

    except Exception as e:
        return f'<div class="toast" style="background-color: var(--form-element-invalid-border-color); color: white;"><strong>Error:</strong> {str(e)}</div>'
