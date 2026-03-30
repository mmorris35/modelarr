"""Watchlist routes for modelarr web UI."""

from fastapi import APIRouter, Depends, Request
from jinja2 import Template

from modelarr.models import WatchlistFilters
from modelarr.store import ModelarrStore
from modelarr.web.deps import get_store

router = APIRouter()


@router.get("/watchlist")
async def watchlist_page(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Render the watchlist page."""
    watches = store.list_watches()

    template = request.app.jinja_env.get_template("watchlist.html")
    html = template.render(watches=watches)
    return Template(html).render()


@router.post("/watchlist")
async def add_watch(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Add a new watchlist entry via form submission."""
    try:
        data = await request.form()

        type_ = str(data.get("type", ""))
        value = str(data.get("value", ""))
        format_ = str(data.get("format", "")) or None
        quant = str(data.get("quant", "")) or None
        min_size_gb = data.get("min_size_gb")
        max_size_gb = data.get("max_size_gb")

        # Convert sizes from GB to bytes
        min_size_b = int(str(min_size_gb)) * (1024**3) if min_size_gb else None
        max_size_b = int(str(max_size_gb)) * (1024**3) if max_size_gb else None

        filters = WatchlistFilters(
            min_size_b=min_size_b,
            max_size_b=max_size_b,
            formats=[format_] if format_ else None,
            quantizations=[quant] if quant else None,
        )

        entry = store.add_watch(type_=type_, value=value, filters=filters)

        # Render the new row as htmx partial
        template = request.app.jinja_env.get_template("partials/watch_row.html")
        html = template.render(watch=entry)
        return Template(html).render()

    except Exception as e:
        return f"<tr><td colspan='6'>Error: {str(e)}</td></tr>"


@router.delete("/watchlist/{watch_id}")
async def delete_watch(
    watch_id: int,
    store: ModelarrStore = Depends(get_store),
):
    """Delete a watchlist entry."""
    store.remove_watch(watch_id)
    return ""


@router.patch("/watchlist/{watch_id}/toggle")
async def toggle_watch(
    request: Request,
    watch_id: int,
    store: ModelarrStore = Depends(get_store),
):
    """Toggle a watchlist entry's enabled state."""
    store.toggle_watch(watch_id)
    entry = store.get_watch(watch_id)

    if entry:
        template = request.app.jinja_env.get_template("partials/watch_row.html")
        html = template.render(watch=entry)
        return Template(html).render()
    return ""
