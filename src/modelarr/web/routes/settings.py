"""Settings routes for modelarr web UI."""

from fastapi import APIRouter, Depends, Request
from jinja2 import Template

from modelarr.notifier import TelegramNotifier
from modelarr.store import ModelarrStore
from modelarr.web.deps import get_store

router = APIRouter()


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

    template = request.app.jinja_env.get_template("settings.html")
    html = template.render(
        library_path=library_path,
        max_storage_gb=max_storage_gb,
        storage_auto_prune=storage_auto_prune.lower() == "true",
        interval_minutes=interval_minutes,
        huggingface_token=huggingface_token,
        telegram_bot_token=telegram_bot_token,
        telegram_chat_id=telegram_chat_id,
    )
    return Template(html).render()


@router.post("/settings")
async def save_settings(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Save all config values."""
    try:
        data = await request.form()

        library_path = data.get("library_path")
        max_storage_gb = data.get("max_storage_gb")
        storage_auto_prune = data.get("storage_auto_prune") == "on"
        interval_minutes = data.get("interval_minutes")
        huggingface_token = data.get("huggingface_token")
        telegram_bot_token = data.get("telegram_bot_token")
        telegram_chat_id = data.get("telegram_chat_id")

        if library_path:
            store.set_config("library_path", library_path)
        if max_storage_gb:
            store.set_config("max_storage_gb", max_storage_gb)
        store.set_config("storage_auto_prune", "true" if storage_auto_prune else "false")
        if interval_minutes:
            store.set_config("interval_minutes", interval_minutes)
        if huggingface_token:
            store.set_config("huggingface_token", huggingface_token)
        if telegram_bot_token:
            store.set_config("telegram_bot_token", telegram_bot_token)
        if telegram_chat_id:
            store.set_config("telegram_chat_id", telegram_chat_id)

        return '<div class="toast" style="background-color: var(--form-element-valid-border-color); color: black;"><strong>Success!</strong> Settings saved.</div>'

    except Exception as e:
        return f'<div class="toast" style="background-color: var(--form-element-invalid-border-color); color: white;"><strong>Error:</strong> {str(e)}</div>'


@router.post("/settings/telegram-test")
async def telegram_test(
    request: Request,
    store: ModelarrStore = Depends(get_store),
):
    """Send a test Telegram notification."""
    try:
        notifier = TelegramNotifier.from_config(store)
        if not notifier:
            return '<div class="toast" style="background-color: var(--form-element-invalid-border-color); color: white;"><strong>Error:</strong> Telegram not configured</div>'

        success = notifier.notify_error("Test notification from modelarr")
        if success:
            return '<div class="toast" style="background-color: var(--form-element-valid-border-color); color: black;"><strong>Success!</strong> Test message sent.</div>'
        else:
            return '<div class="toast" style="background-color: var(--form-element-invalid-border-color); color: white;"><strong>Error:</strong> Failed to send test message</div>'

    except Exception as e:
        return f'<div class="toast" style="background-color: var(--form-element-invalid-border-color); color: white;"><strong>Error:</strong> {str(e)}</div>'
