"""Tests for Telegram notification module."""

from datetime import UTC, datetime
from unittest.mock import patch, MagicMock

import pytest

from modelarr.db import init_db
from modelarr.models import DownloadRecord, ModelInfo, WatchlistEntry, WatchlistFilters
from modelarr.notifier import TelegramNotifier
from modelarr.store import ModelarrStore


class TestTelegramNotifier:
    """Tests for TelegramNotifier."""

    def test_init(self):
        """Test initializing notifier."""
        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        assert notifier.bot_token == "123:ABC"
        assert notifier.chat_id == "456"
        assert notifier.api_url == "https://api.telegram.org/bot123:ABC/sendMessage"

    @patch("modelarr.notifier.httpx.post")
    def test_notify_success(self, mock_post):
        """Test successful notification."""
        mock_post.return_value = MagicMock(status_code=200)

        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        now = datetime.now(UTC)
        watch = WatchlistEntry(
            id=1,
            type="query",
            value="test",
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        model = ModelInfo(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=5 * (1024**3),
            format="gguf",
            quantization="Q4_K_M",
        )
        download = DownloadRecord(
            id=1,
            model_id=1,
            status="complete",
            started_at=now,
            completed_at=now,
            bytes_downloaded=5 * (1024**3),
            total_bytes=5 * (1024**3),
            error=None,
        )

        result = notifier.notify(watch, model, download)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[0][0] == "https://api.telegram.org/bot123:ABC/sendMessage"
        assert call_args[1]["json"]["chat_id"] == "456"
        assert "test/model" in call_args[1]["json"]["text"]
        assert "5.00 GB" in call_args[1]["json"]["text"]

    @patch("modelarr.notifier.httpx.post")
    def test_notify_failure(self, mock_post):
        """Test notification failure (graceful)."""
        mock_post.return_value = MagicMock(status_code=500)

        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        now = datetime.now(UTC)
        watch = WatchlistEntry(
            id=1,
            type="query",
            value="test",
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        model = ModelInfo(
            repo_id="test/model",
            author="test",
            name="model",
        )
        download = DownloadRecord(
            id=1,
            model_id=1,
            status="failed",
            error="Download failed",
        )

        result = notifier.notify(watch, model, download)

        assert result is False

    @patch("modelarr.notifier.httpx.post")
    def test_notify_exception_handling(self, mock_post):
        """Test notification never raises exception."""
        mock_post.side_effect = Exception("Network error")

        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        now = datetime.now(UTC)
        watch = WatchlistEntry(
            id=1,
            type="query",
            value="test",
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        model = ModelInfo(
            repo_id="test/model",
            author="test",
            name="model",
        )
        download = DownloadRecord(
            id=1,
            model_id=1,
            status="complete",
        )

        # Should not raise
        result = notifier.notify(watch, model, download)
        assert result is False

    @patch("modelarr.notifier.httpx.post")
    def test_notify_message_formatting(self, mock_post):
        """Test message contains all model information."""
        mock_post.return_value = MagicMock(status_code=200)

        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        now = datetime.now(UTC)
        watch = WatchlistEntry(
            id=1,
            type="query",
            value="test",
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        model = ModelInfo(
            repo_id="test-author/test-model",
            author="test-author",
            name="test-model",
            size_bytes=10 * (1024**3),
            format="safetensors",
            quantization="fp16",
        )
        download = DownloadRecord(
            id=1,
            model_id=1,
            status="complete",
        )

        notifier.notify(watch, model, download)

        message = mock_post.call_args[1]["json"]["text"]
        assert "test-author/test-model" in message
        assert "10.00 GB" in message
        assert "safetensors" in message
        assert "fp16" in message
        assert "https://huggingface.co/test-author/test-model" in message

    @patch("modelarr.notifier.httpx.post")
    def test_notify_error(self, mock_post):
        """Test error notification."""
        mock_post.return_value = MagicMock(status_code=200)

        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        result = notifier.notify_error("Test error occurred")

        assert result is True
        call_args = mock_post.call_args
        assert "Test error occurred" in call_args[1]["json"]["text"]
        assert "Error in modelarr monitor" in call_args[1]["json"]["text"]

    @patch("modelarr.notifier.httpx.post")
    def test_notify_error_failure(self, mock_post):
        """Test error notification failure (graceful)."""
        mock_post.return_value = MagicMock(status_code=500)

        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        result = notifier.notify_error("Test error")

        assert result is False

    @patch("modelarr.notifier.httpx.post")
    def test_notify_error_exception(self, mock_post):
        """Test error notification exception handling."""
        mock_post.side_effect = Exception("Network error")

        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        # Should not raise
        result = notifier.notify_error("Test error")
        assert result is False

    def test_from_config_with_both_set(self, tmp_path):
        """Test from_config returns notifier when both values set."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)
        store.set_config("telegram_bot_token", "123:ABC")
        store.set_config("telegram_chat_id", "456")

        notifier = TelegramNotifier.from_config(store)

        assert notifier is not None
        assert notifier.bot_token == "123:ABC"
        assert notifier.chat_id == "456"

    def test_from_config_missing_token(self, tmp_path):
        """Test from_config returns None when token missing."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)
        store.set_config("telegram_chat_id", "456")

        notifier = TelegramNotifier.from_config(store)

        assert notifier is None

    def test_from_config_missing_chat_id(self, tmp_path):
        """Test from_config returns None when chat_id missing."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)
        store.set_config("telegram_bot_token", "123:ABC")

        notifier = TelegramNotifier.from_config(store)

        assert notifier is None

    def test_from_config_missing_both(self, tmp_path):
        """Test from_config returns None when both missing."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        notifier = TelegramNotifier.from_config(store)

        assert notifier is None

    @patch("modelarr.notifier.httpx.post")
    def test_notify_with_none_size(self, mock_post):
        """Test notify handles None size_bytes."""
        mock_post.return_value = MagicMock(status_code=200)

        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        now = datetime.now(UTC)
        watch = WatchlistEntry(
            id=1,
            type="query",
            value="test",
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        model = ModelInfo(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=None,
        )
        download = DownloadRecord(
            id=1,
            model_id=1,
            status="complete",
        )

        result = notifier.notify(watch, model, download)

        assert result is True
        message = mock_post.call_args[1]["json"]["text"]
        assert "Unknown" in message

    @patch("modelarr.notifier.httpx.post")
    def test_notify_without_optional_fields(self, mock_post):
        """Test notify message without format/quantization."""
        mock_post.return_value = MagicMock(status_code=200)

        notifier = TelegramNotifier(bot_token="123:ABC", chat_id="456")
        now = datetime.now(UTC)
        watch = WatchlistEntry(
            id=1,
            type="query",
            value="test",
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        model = ModelInfo(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=1 * (1024**3),
        )
        download = DownloadRecord(
            id=1,
            model_id=1,
            status="complete",
        )

        result = notifier.notify(watch, model, download)

        assert result is True
        # Should still succeed even without format/quant
        call_args = mock_post.call_args
        assert call_args is not None
