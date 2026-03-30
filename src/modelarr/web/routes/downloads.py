"""Downloads routes for modelarr web UI."""


from fastapi import APIRouter, Depends, Request
from jinja2 import Template

from modelarr.downloader import DownloadManager
from modelarr.hf_client import HFClient
from modelarr.store import ModelarrStore
from modelarr.web.deps import format_bytes, get_downloader, get_hf_client, get_store


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
        repo_id = str(data.get("repo_id", ""))

        if not repo_id:
            msg = "<strong>Error:</strong> repo_id is required"
            return _toast_html(msg, is_error=True)

        # Fetch model info
        model_info = hf_client.get_model_info(repo_id)

        # Dispatch download to thread pool
        downloader.download_model(model_info)

        msg = f"<strong>Success!</strong> Download queued for {repo_id}"
        return _toast_html(msg, is_error=False)

    except Exception as e:
        msg = f"<strong>Error:</strong> {str(e)}"
        return _toast_html(msg, is_error=True)
