"""Search routes for modelarr web UI."""


from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from modelarr.downloader import DownloadManager
from modelarr.hf_client import HFClient
from modelarr.models import WatchlistFilters
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


router = APIRouter(default_response_class=HTMLResponse)


@router.get("/search")
async def search_page(
    request: Request,
    q: str | None = None,
    store: ModelarrStore = Depends(get_store),
):
    """Render the search page with optional query param."""
    template = request.app.jinja_env.get_template("search.html")
    html = template.render(query=q or "")
    return HTMLResponse(html)


@router.get("/search/results")
async def search_results(
    request: Request,
    q: str = "",
    hf_client: HFClient = Depends(get_hf_client),
):
    """Return search results as htmx partial (with debounce)."""
    if not q or len(q) < 2:
        return '<p style="color: var(--muted-color);">Enter at least 2 characters to search.</p>'

    try:
        results = hf_client.search_models(q, limit=10)

        if not results:
            return '<p style="color: var(--muted-color);">No models found.</p>'

        template = request.app.jinja_env.get_template("partials/search_results.html")
        html = template.render(results=results, format_bytes=format_bytes)
        return HTMLResponse(html)

    except Exception as e:
        return f'<p style="color: var(--form-element-invalid-border-color);">Error: {str(e)}</p>'


@router.get("/search/model/{repo_id:path}")
async def model_detail(
    request: Request,
    repo_id: str,
    hf_client: HFClient = Depends(get_hf_client),
):
    """Return model detail panel as htmx partial."""
    try:
        model = hf_client.get_model_info(repo_id)

        template = request.app.jinja_env.get_template("partials/model_detail.html")
        html = template.render(model=model, format_bytes=format_bytes)
        return HTMLResponse(html)

    except Exception as e:
        return f'<p style="color: var(--form-element-invalid-border-color);">Error: {str(e)}</p>'


@router.post("/search/watch")
async def add_from_search(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Add a model/author to watchlist from search results."""
    try:
        data = await request.form()

        type_ = str(data.get("type", ""))
        value = str(data.get("value", ""))

        entry = store.add_watch(
            type_=type_, value=value, filters=WatchlistFilters()
        )

        msg = f"<strong>Success!</strong> Added to watchlist (ID: {entry.id})"
        return _toast_html(msg, is_error=False)

    except Exception as e:
        msg = f"<strong>Error:</strong> {str(e)}"
        return _toast_html(msg, is_error=True)


@router.post("/search/download")
async def download_from_search(
    request: Request,
    hf_client: HFClient = Depends(get_hf_client),
    downloader: DownloadManager = Depends(get_downloader),
):
    """Trigger immediate download from search results."""
    try:
        data = await request.form()
        repo_id = str(data.get("repo_id", ""))

        if not repo_id:
            msg = "<strong>Error:</strong> repo_id is required"
            return _toast_html(msg, is_error=True)

        model_info = hf_client.get_model_info(repo_id)
        downloader.download_model(model_info)

        msg = f"<strong>Success!</strong> Download queued for {repo_id}"
        return _toast_html(msg, is_error=False)

    except Exception as e:
        msg = f"<strong>Error:</strong> {str(e)}"
        return _toast_html(msg, is_error=True)
