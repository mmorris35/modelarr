"""Tests for weekly digest notification module."""

from datetime import datetime
from unittest.mock import patch

import pytest

from modelarr.db import init_db
from modelarr.notifier import TelegramNotifier
from modelarr.store import ModelarrStore


@pytest.fixture
def test_db(tmp_path):
    """Create a test database."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def test_store(test_db):
    """Create a test store."""
    return ModelarrStore(test_db)


@pytest.fixture
def test_notifier():
    """Create a test Telegram notifier."""
    return TelegramNotifier(bot_token="test_token", chat_id="test_chat")


def test_send_digest_no_downloads(test_store: ModelarrStore, test_notifier):
    """Test digest with no downloads."""
    with patch("modelarr.notifier.httpx.post") as mock_post:
        mock_post.return_value.status_code = 200

        result = test_notifier.send_digest(test_store)

        assert result is True
        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "No new models" in call_args[1]["json"]["text"]


def test_send_digest_with_downloads(test_store: ModelarrStore, test_notifier):
    """Test digest with completed downloads."""
    from datetime import UTC

    # Add a model and downloads
    test_store.upsert_model(
        "test/model1",
        "test",
        "model1",
        format_="gguf",
        size_bytes=1000000,
    )
    test_store.upsert_model(
        "test/model2",
        "test",
        "model2",
        format_="gguf",
        size_bytes=2000000,
    )

    model1 = test_store.get_model_by_repo("test/model1")
    model2 = test_store.get_model_by_repo("test/model2")

    dl1 = test_store.create_download(
        model1.id, status="downloading", total_bytes=1000000
    )
    dl2 = test_store.create_download(
        model2.id, status="downloading", total_bytes=2000000
    )

    # Complete the downloads
    test_store.update_download(
        dl1.id, status="complete", completed_at=datetime.now(UTC)
    )
    test_store.update_download(
        dl2.id, status="complete", completed_at=datetime.now(UTC)
    )

    with patch("modelarr.notifier.httpx.post") as mock_post:
        mock_post.return_value.status_code = 200

        result = test_notifier.send_digest(test_store)

        assert result is True
        call_args = mock_post.call_args
        message = call_args[1]["json"]["text"]
        assert "2 models downloaded" in message


def test_send_digest_failure(test_store: ModelarrStore, test_notifier):
    """Test digest handles Telegram API failures gracefully."""
    with patch("modelarr.notifier.httpx.post") as mock_post:
        mock_post.return_value.status_code = 401  # Unauthorized

        result = test_notifier.send_digest(test_store)

        assert result is False


def test_send_digest_exception(test_store: ModelarrStore, test_notifier):
    """Test digest handles exceptions gracefully."""
    with patch("modelarr.notifier.httpx.post") as mock_post:
        mock_post.side_effect = Exception("Network error")

        result = test_notifier.send_digest(test_store)

        assert result is False


def test_digest_config_keys(test_store: ModelarrStore):
    """Test digest configuration keys can be stored."""
    test_store.set_config("digest_enabled", "true")
    test_store.set_config("digest_day", "monday")
    test_store.set_config("digest_hour", "9")

    assert test_store.get_config("digest_enabled") == "true"
    assert test_store.get_config("digest_day") == "monday"
    assert test_store.get_config("digest_hour") == "9"
