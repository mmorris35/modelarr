"""Library routes for modelarr web UI."""


from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from modelarr.downloader import DownloadManager
from modelarr.store import ModelarrStore
from modelarr.web.deps import format_bytes, get_downloader, get_store

router = APIRouter(default_response_class=HTMLResponse)


@router.get("/library")
async def library_page(
    request: Request,
    sort: str = "date",
    format_filter: str | None = None,
    store: ModelarrStore = Depends(get_store),
    downloader: DownloadManager = Depends(get_downloader),
):
    """Render the library page with sorting and filtering."""
    models = downloader.list_local_models()

    # Apply format filter
    if format_filter:
        models = [m for m in models if m.format == format_filter]

    # Sort by specified key
    if sort == "size":
        models.sort(key=lambda m: m.size_bytes or 0, reverse=True)
    elif sort == "name":
        models.sort(key=lambda m: m.name)
    else:  # date (default)
        models.sort(key=lambda m: m.downloaded_at or m.id, reverse=True)

    total_size = downloader.get_library_size()
    max_storage_gb = store.get_config("max_storage_gb")
    storage_usage_pct: float = 0.0
    if max_storage_gb:
        max_bytes = int(max_storage_gb) * (1024**3)
        storage_usage_pct = (total_size / max_bytes) * 100

    template = request.app.jinja_env.get_template("library.html")
    html = template.render(
        models=models,
        total_size=format_bytes(total_size),
        model_count=len(models),
        storage_usage_pct=storage_usage_pct,
        max_storage_gb=max_storage_gb or "None",
        sort=sort,
        format_filter=format_filter,
    )
    return HTMLResponse(html)


@router.delete("/library/{repo_id:path}")
async def delete_model(
    repo_id: str,
    store: ModelarrStore = Depends(get_store),
    downloader: DownloadManager = Depends(get_downloader),
):
    """Delete a model from the library."""
    downloader.delete_local_model(repo_id)
    return ""


@router.get("/library/size")
async def get_library_size(
    downloader: DownloadManager = Depends(get_downloader),
):
    """Return total library size as an htmx partial."""
    total_size = downloader.get_library_size()
    return f"<span>{format_bytes(total_size)}</span>"
