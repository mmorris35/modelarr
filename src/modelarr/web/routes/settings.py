"""Settings routes for modelarr web UI."""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from modelarr.notifier import TelegramNotifier
from modelarr.store import ModelarrStore
from modelarr.web.deps import get_store


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


@router.get("/settings")
async def settings_page(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Render the settings page with current config values."""
    library_path = store.get_config("library_path") or ""
    max_storage_gb = store.get_config("max_storage_gb") or ""
    storage_auto_prune = store.get_config("storage_auto_prune") or "false"
    interval_minutes = store.get_config("interval_minutes") or "60"
    huggingface_token = store.get_config("huggingface_token") or ""
    telegram_bot_token = store.get_config("telegram_bot_token") or ""
    telegram_chat_id = store.get_config("telegram_chat_id") or ""
    max_download_workers = store.get_config("max_download_workers") or "1"
    min_free_memory_mb = store.get_config("min_free_memory_mb") or "200"
    ollama_host = store.get_config("ollama_host") or ""

    template = request.app.jinja_env.get_template("settings.html")
    html = template.render(
        library_path=library_path,
        max_storage_gb=max_storage_gb,
        storage_auto_prune=storage_auto_prune.lower() == "true",
        interval_minutes=interval_minutes,
        huggingface_token=huggingface_token,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
        max_download_workers=max_download_workers,
        min_free_memory_mb=min_free_memory_mb,
        ollama_host=ollama_host,
    )
    return HTMLResponse(html)


@router.post("/settings")
async def save_settings(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Save all config values."""
    try:
        data = await request.form()

        library_path = str(data.get("library_path", ""))
        max_storage_gb = str(data.get("max_storage_gb", ""))
        storage_auto_prune = str(data.get("storage_auto_prune", "")) == "on"
        interval_minutes = str(data.get("interval_minutes", ""))
        huggingface_token = str(data.get("huggingface_token", ""))
        telegram_bot_token = str(data.get("telegram_bot_token", ""))
        telegram_chat_id = str(data.get("telegram_chat_id", ""))
        max_download_workers = str(data.get("max_download_workers", ""))
        min_free_memory_mb = str(data.get("min_free_memory_mb", ""))
        ollama_host = str(data.get("ollama_host", ""))

        if library_path:
            store.set_config("library_path", library_path)
        if max_storage_gb:
            store.set_config("max_storage_gb", max_storage_gb)
        store.set_config(
            "storage_auto_prune", "true" if storage_auto_prune else "false"
        )
        if interval_minutes:
            store.set_config("interval_minutes", interval_minutes)
        if huggingface_token:
            store.set_config("huggingface_token", huggingface_token)
        if telegram_bot_token:
            store.set_config("telegram_bot_token", telegram_bot_token)
        if telegram_chat_id:
            store.set_config("telegram_chat_id", telegram_chat_id)
        if max_download_workers:
            store.set_config("max_download_workers", max_download_workers)
        if min_free_memory_mb:
            store.set_config("min_free_memory_mb", min_free_memory_mb)
        if ollama_host:
            store.set_config("ollama_host", ollama_host)

        msg = "<strong>Success!</strong> Settings saved."
        return _toast_html(msg, is_error=False)

    except Exception as e:
        msg = f"<strong>Error:</strong> {str(e)}"
        return _toast_html(msg, is_error=True)


@router.post("/settings/telegram-test")
async def telegram_test(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Send a test Telegram notification."""
    try:
        notifier = TelegramNotifier.from_config(store)
        if not notifier:
            msg = "<strong>Error:</strong> Telegram not configured"
            return _toast_html(msg, is_error=True)

        success = notifier.notify_error("Test notification from modelarr")
        if success:
            msg = "<strong>Success!</strong> Test message sent."
            return _toast_html(msg, is_error=False)
        else:
            msg = "<strong>Error:</strong> Failed to send test message"
            return _toast_html(msg, is_error=True)

    except Exception as e:
        msg = f"<strong>Error:</strong> {str(e)}"
        return _toast_html(msg, is_error=True)
