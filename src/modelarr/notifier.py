"""Telegram notification module for modelarr."""

import httpx

from modelarr.models import DownloadRecord, ModelInfo, WatchlistEntry
from modelarr.store import ModelarrStore


class TelegramNotifier:
    """Sends notifications via Telegram Bot API."""

    def __init__(self, bot_token: str, chat_id: str) -> None:
        """Initialize the Telegram notifier.

        Args:
            bot_token: Telegram bot API token
            chat_id: Telegram chat ID to send messages to
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"

    def notify(
        self,
        watch: WatchlistEntry,
        model: ModelInfo,
        download: DownloadRecord,
    ) -> bool:
        """Send a notification about a downloaded model.

        Args:
            watch: WatchlistEntry that triggered the download
            model: ModelInfo of the downloaded model
            download: DownloadRecord with download status

        Returns:
            True if sent successfully, False otherwise (never raises)
        """
        try:
            # Format size in human-readable form
            size_gb = (model.size_bytes or 0) / (1024**3)
            size_str = f"{size_gb:.2f} GB" if model.size_bytes else "Unknown"

            # Build notification message
            message = (
                f"✅ New model downloaded!\n\n"
                f"📦 {model.author}/{model.name}\n"
                f"📏 Size: {size_str}\n"
            )

            if model.format:
                message += f"📄 Format: {model.format}\n"
            if model.quantization:
                message += f"⚙️ Quantization: {model.quantization}\n"

            message += f"\n🔗 https://huggingface.co/{model.repo_id}"

            # Send to Telegram
            response = httpx.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )

            return response.status_code == 200

        except Exception:
            return False

    def notify_error(self, error: str) -> bool:
        """Send an error notification.

        Args:
            error: Error message to send

        Returns:
            True if sent successfully, False otherwise (never raises)
        """
        try:
            message = f"❌ Error in modelarr monitor:\n\n{error}"

            response = httpx.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )

            return response.status_code == 200

        except Exception:
            return False

    def send_digest(self, store: ModelarrStore) -> bool:
        """Send a weekly digest of downloaded models.

        Args:
            store: ModelarrStore instance with download history

        Returns:
            True if sent successfully, False otherwise (never raises)
        """
        try:
            from datetime import UTC, datetime, timedelta

            # Get downloads completed in the past 7 days
            since = datetime.now(UTC) - timedelta(days=7)
            downloads = store.get_download_history(limit=1000, since=since)
            completed = [
                d for d in downloads
                if d.status == "complete" and d.completed_at
            ]

            if not completed:
                message = "📊 Weekly Digest\n\n" \
                          "No new models downloaded this week."
            else:
                total_size = sum(d.total_bytes or 0 for d in completed)
                size_gb = total_size / (1024**3)
                size_str = f"{size_gb:.2f} GB"

                message = (
                    f"📊 Weekly Digest\n\n"
                    f"✅ {len(completed)} models downloaded\n"
                    f"📦 Total size: {size_str}\n\n"
                )

                # List model names (try to get from store)
                model_list = []
                for dl in completed[:20]:  # Limit to first 20
                    model = store.get_model_by_id(dl.model_id)
                    if model:
                        model_list.append(f"  • {model.author}/{model.name}")

                if model_list:
                    message += "Downloaded models:\n" + "\n".join(model_list)
                    if len(completed) > 20:
                        message += f"\n  ... and {len(completed) - 20} more"

            response = httpx.post(
                self.api_url,
                json={
                    "chat_id": self.chat_id,
                    "text": message,
                    "parse_mode": "HTML",
                },
                timeout=10,
            )

            return response.status_code == 200

        except Exception:
            return False

    @classmethod
    def from_config(
        cls, store: ModelarrStore
    ) -> "TelegramNotifier | None":
        """Create a TelegramNotifier from configuration.

        Returns None if bot_token or chat_id not configured.

        Args:
            store: ModelarrStore instance with configuration

        Returns:
            TelegramNotifier instance if configured, None otherwise
        """
        bot_token = store.get_config("telegram_bot_token")
        chat_id = store.get_config("telegram_chat_id")

        if not bot_token or not chat_id:
            return None

        return cls(bot_token, chat_id)
