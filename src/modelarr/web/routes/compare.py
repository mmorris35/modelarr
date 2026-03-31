"""Model comparison routes for modelarr web UI."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from modelarr.downloader import DownloadManager
from modelarr.store import ModelarrStore
from modelarr.web.deps import format_bytes, get_downloader, get_store

router = APIRouter(default_response_class=HTMLResponse)


@router.get("/compare")
async def compare_page(
    request: Request,
    ids: str | None = None,
    store: ModelarrStore = Depends(get_store),
    downloader: DownloadManager = Depends(get_downloader),
):
    """Render the model comparison page."""
    models = downloader.list_local_models()

    # Parse selected model IDs from query param
    selected_models = []
    if ids:
        id_list = [int(id_str.strip()) for id_str in ids.split(",") if id_str.strip()]
        for mid in id_list:
            model = next((m for m in models if m.id == mid), None)
            if model:
                selected_models.append(model)

    template = request.app.jinja_env.get_template("compare.html")
    html = template.render(
        models=models,
        selected_models=selected_models,
        format_bytes=format_bytes,
    )
    return HTMLResponse(html)
