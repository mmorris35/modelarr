"""Tests for storage management module."""

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from modelarr.db import init_db
from modelarr.models import ModelRecord
from modelarr.storage import StorageManager
from modelarr.store import ModelarrStore


class TestStorageManager:
    """Tests for StorageManager."""

    def test_init(self, tmp_path):
        """Test initializing storage manager."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)
        library_path = tmp_path / "library"

        # Without limit
        manager = StorageManager(store=store, library_path=library_path)
        assert manager.max_bytes is None

        # With limit
        max_gb = 100
        manager = StorageManager(
            store=store,
            library_path=library_path,
            max_bytes=max_gb * (1024**3),
        )
        assert manager.max_bytes == max_gb * (1024**3)

    def test_check_space_unlimited(self, tmp_path):
        """Test check_space with no limit."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)
        manager = StorageManager(store=store, library_path=tmp_path)

        # Should always return True when unlimited
        assert manager.check_space(1 * (1024**3))
        assert manager.check_space(100 * (1024**3))
        assert manager.check_space(1000 * (1024**3))

    def test_check_space_with_limit_passes(self, tmp_path):
        """Test check_space returns True when space available."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create a model
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=3 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model"),
        )

        # 10 GB limit, 3 GB used, requesting 5 GB
        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=10 * (1024**3),
        )

        assert manager.check_space(5 * (1024**3))

    def test_check_space_with_limit_fails(self, tmp_path):
        """Test check_space returns False when would exceed limit."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create a model
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=7 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model"),
        )

        # 10 GB limit, 7 GB used, requesting 5 GB (would exceed)
        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=10 * (1024**3),
        )

        assert not manager.check_space(5 * (1024**3))

    def test_check_space_exact_limit(self, tmp_path):
        """Test check_space with exact limit match."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create a model
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=5 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model"),
        )

        # 10 GB limit, 5 GB used, requesting 5 GB (exact fit)
        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=10 * (1024**3),
        )

        assert manager.check_space(5 * (1024**3))

    @patch("modelarr.storage.DownloadManager")
    def test_prune_oldest(self, mock_dm_class, tmp_path):
        """Test pruning oldest models."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create models with different timestamps
        now = datetime.now(UTC)
        model1 = store.upsert_model(
            repo_id="test/model1",
            author="test",
            name="model1",
            size_bytes=3 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model1"),
        )
        model2 = store.upsert_model(
            repo_id="test/model2",
            author="test",
            name="model2",
            size_bytes=4 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model2"),
        )

        # Mock downloader
        mock_dm = MagicMock()
        mock_dm.delete_local_model.side_effect = lambda repo_id: True
        mock_dm_class.return_value = mock_dm

        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=10 * (1024**3),
        )

        # Need to free 5 GB
        deleted = manager.prune_oldest(5 * (1024**3))

        # Should delete models until 5+ GB freed
        assert len(deleted) >= 1
        assert any(m.repo_id == "test/model1" for m in deleted)

    @patch("modelarr.storage.DownloadManager")
    def test_prune_oldest_stops_when_done(self, mock_dm_class, tmp_path):
        """Test pruning stops after freeing enough space."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create models
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model1",
            author="test",
            name="model1",
            size_bytes=6 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model1"),
        )
        store.upsert_model(
            repo_id="test/model2",
            author="test",
            name="model2",
            size_bytes=6 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model2"),
        )

        # Mock downloader
        mock_dm = MagicMock()
        mock_dm.delete_local_model.return_value = True
        mock_dm_class.return_value = mock_dm

        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=10 * (1024**3),
        )

        # Only need 5 GB freed (first model is 6 GB)
        deleted = manager.prune_oldest(5 * (1024**3))

        # Should only delete first model
        assert len(deleted) == 1

    def test_get_usage_empty(self, tmp_path):
        """Test get_usage with no models."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=100 * (1024**3),
        )

        usage = manager.get_usage()

        assert usage["total_bytes"] == 0
        assert usage["model_count"] == 0
        assert usage["max_bytes"] == 100 * (1024**3)
        assert usage["free_bytes"] == 100 * (1024**3)

    def test_get_usage_with_models(self, tmp_path):
        """Test get_usage with multiple models."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create models
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model1",
            author="test",
            name="model1",
            size_bytes=3 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model1"),
        )
        store.upsert_model(
            repo_id="test/model2",
            author="test",
            name="model2",
            size_bytes=7 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model2"),
        )
        # Non-downloaded model
        store.upsert_model(
            repo_id="test/model3",
            author="test",
            name="model3",
            size_bytes=5 * (1024**3),
        )

        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=100 * (1024**3),
        )

        usage = manager.get_usage()

        assert usage["total_bytes"] == 10 * (1024**3)
        assert usage["model_count"] == 2
        assert usage["max_bytes"] == 100 * (1024**3)
        assert usage["free_bytes"] == 90 * (1024**3)

    def test_get_usage_unlimited(self, tmp_path):
        """Test get_usage with unlimited storage."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create a model
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=5 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model"),
        )

        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=None,
        )

        usage = manager.get_usage()

        assert usage["total_bytes"] == 5 * (1024**3)
        assert usage["model_count"] == 1
        assert usage["max_bytes"] is None
        assert usage["free_bytes"] is None

    def test_get_usage_at_limit(self, tmp_path):
        """Test get_usage when at limit."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create model
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=100 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model"),
        )

        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=100 * (1024**3),
        )

        usage = manager.get_usage()

        assert usage["free_bytes"] == 0

    def test_get_usage_with_none_sizes(self, tmp_path):
        """Test get_usage handles models with None size_bytes."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create model without size
        store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=None,
            local_path=str(tmp_path / "test" / "model"),
        )

        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=100 * (1024**3),
        )

        usage = manager.get_usage()

        assert usage["total_bytes"] == 0
        assert usage["model_count"] == 1

    @patch("modelarr.storage.DownloadManager")
    def test_prune_oldest_handles_deletion_failure(self, mock_dm_class, tmp_path):
        """Test prune_oldest handles deletion failures gracefully."""
        db_path = tmp_path / "test.db"
        init_db(db_path)
        store = ModelarrStore(db_path)

        # Create models
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model1",
            author="test",
            name="model1",
            size_bytes=3 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model1"),
        )
        store.upsert_model(
            repo_id="test/model2",
            author="test",
            name="model2",
            size_bytes=6 * (1024**3),
            downloaded_at=now,
            local_path=str(tmp_path / "test" / "model2"),
        )

        # Mock downloader - first delete fails, second succeeds
        mock_dm = MagicMock()
        mock_dm.delete_local_model.side_effect = [False, True]
        mock_dm_class.return_value = mock_dm

        manager = StorageManager(
            store=store,
            library_path=tmp_path,
            max_bytes=10 * (1024**3),
        )

        # Need 5 GB, first model fails to delete, second succeeds
        deleted = manager.prune_oldest(5 * (1024**3))

        # Should skip first and delete second
        assert len(deleted) == 1
        assert deleted[0].repo_id == "test/model2"
