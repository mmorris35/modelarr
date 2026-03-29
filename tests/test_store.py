"""Tests for the ModelarrStore CRUD operations."""

from datetime import datetime
from pathlib import Path

import pytest

from modelarr.models import WatchlistFilters
from modelarr.store import ModelarrStore


@pytest.fixture
def store(tmp_path: Path) -> ModelarrStore:
    """Create a test store with isolated database."""
    db_path = tmp_path / "test.db"
    return ModelarrStore(db_path)


class TestWatchlistOperations:
    """Tests for watchlist CRUD operations."""

    def test_add_watch_basic(self, store: ModelarrStore) -> None:
        """Test adding a basic watch entry."""
        entry = store.add_watch(
            type_="model",
            value="mlx-community/Qwen3.5-27B-MLX-4bit",
        )

        assert entry.id is not None
        assert entry.type == "model"
        assert entry.value == "mlx-community/Qwen3.5-27B-MLX-4bit"
        assert entry.enabled is True
        assert entry.filters.min_size_b is None

    def test_add_watch_with_filters(self, store: ModelarrStore) -> None:
        """Test adding a watch with filters."""
        filters = WatchlistFilters(formats=["mlx"], quantizations=["4bit"])
        entry = store.add_watch(
            type_="author",
            value="mlx-community",
            filters=filters,
        )

        assert entry.type == "author"
        assert entry.filters.formats == ["mlx"]
        assert entry.filters.quantizations == ["4bit"]

    def test_add_watch_disabled(self, store: ModelarrStore) -> None:
        """Test adding a disabled watch."""
        entry = store.add_watch(
            type_="query",
            value="test",
            enabled=False,
        )

        assert entry.enabled is False

    def test_list_watches(self, store: ModelarrStore) -> None:
        """Test listing all watches."""
        store.add_watch("model", "test1")
        store.add_watch("author", "test2")
        store.add_watch("query", "test3", enabled=False)

        watches = store.list_watches()

        assert len(watches) == 3
        assert watches[0].value == "test1"
        assert watches[1].value == "test2"
        assert watches[2].value == "test3"

    def test_list_watches_enabled_only(self, store: ModelarrStore) -> None:
        """Test listing only enabled watches."""
        store.add_watch("model", "enabled1", enabled=True)
        store.add_watch("model", "disabled1", enabled=False)
        store.add_watch("author", "enabled2", enabled=True)

        watches = store.list_watches(enabled_only=True)

        assert len(watches) == 2
        assert all(w.enabled for w in watches)

    def test_remove_watch(self, store: ModelarrStore) -> None:
        """Test removing a watch."""
        entry = store.add_watch("model", "test")
        assert store.remove_watch(entry.id)
        assert not store.remove_watch(entry.id)

    def test_toggle_watch(self, store: ModelarrStore) -> None:
        """Test toggling watch enabled state."""
        entry = store.add_watch("model", "test", enabled=True)
        assert entry.enabled is True

        result = store.toggle_watch(entry.id)
        assert result is True

        updated = store.get_watch(entry.id)
        assert updated is not None
        assert updated.enabled is False

        result = store.toggle_watch(entry.id)
        assert result is True

        updated = store.get_watch(entry.id)
        assert updated is not None
        assert updated.enabled is True

    def test_toggle_watch_nonexistent(self, store: ModelarrStore) -> None:
        """Test toggling a nonexistent watch."""
        result = store.toggle_watch(9999)
        assert result is False

    def test_get_watch(self, store: ModelarrStore) -> None:
        """Test getting a watch by ID."""
        entry = store.add_watch("model", "test")
        retrieved = store.get_watch(entry.id)

        assert retrieved is not None
        assert retrieved.id == entry.id
        assert retrieved.value == "test"

    def test_get_watch_nonexistent(self, store: ModelarrStore) -> None:
        """Test getting a nonexistent watch."""
        result = store.get_watch(9999)
        assert result is None


class TestModelOperations:
    """Tests for model CRUD operations."""

    def test_upsert_model_insert(self, store: ModelarrStore) -> None:
        """Test inserting a new model."""
        model = store.upsert_model(
            repo_id="mlx-community/test",
            author="mlx-community",
            name="test",
            format_="mlx",
            quantization="4bit",
            size_bytes=14000000000,
        )

        assert model.id is not None
        assert model.repo_id == "mlx-community/test"
        assert model.format == "mlx"

    def test_upsert_model_update(self, store: ModelarrStore) -> None:
        """Test updating an existing model."""
        repo_id = "mlx-community/test"
        model1 = store.upsert_model(
            repo_id=repo_id,
            author="mlx-community",
            name="test",
            format_="mlx",
            size_bytes=10000000000,
        )

        model2 = store.upsert_model(
            repo_id=repo_id,
            author="mlx-community",
            name="test",
            format_="mlx",
            size_bytes=15000000000,
        )

        assert model1.id == model2.id
        assert model2.size_bytes == 15000000000

    def test_upsert_model_with_metadata(self, store: ModelarrStore) -> None:
        """Test upserting a model with metadata."""
        metadata = {"tags": ["mlx", "4bit"], "downloads": 500}
        model = store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            metadata=metadata,
        )

        assert model.metadata == metadata

    def test_upsert_model_with_timestamps(self, store: ModelarrStore) -> None:
        """Test upserting a model with timestamps."""
        now = datetime.now()
        model = store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            downloaded_at=now,
            local_path="/data/models/test/model",
        )

        assert model.downloaded_at is not None
        assert model.local_path == "/data/models/test/model"

    def test_get_model_by_repo(self, store: ModelarrStore) -> None:
        """Test getting a model by repo ID."""
        store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            format_="gguf",
        )

        retrieved = store.get_model_by_repo("test/model")

        assert retrieved is not None
        assert retrieved.repo_id == "test/model"
        assert retrieved.format == "gguf"

    def test_get_model_by_repo_nonexistent(self, store: ModelarrStore) -> None:
        """Test getting a nonexistent model."""
        result = store.get_model_by_repo("nonexistent/model")
        assert result is None

    def test_list_models(self, store: ModelarrStore) -> None:
        """Test listing all models."""
        store.upsert_model("test/model1", "test", "model1")
        store.upsert_model("test/model2", "test", "model2")
        store.upsert_model("test/model3", "test", "model3")

        models = store.list_models()

        assert len(models) == 3
        assert models[0].repo_id == "test/model1"

    def test_delete_model(self, store: ModelarrStore) -> None:
        """Test deleting a model."""
        model = store.upsert_model("test/model", "test", "model")

        assert store.delete_model(model.id)
        assert store.get_model_by_repo("test/model") is None

    def test_delete_model_nonexistent(self, store: ModelarrStore) -> None:
        """Test deleting a nonexistent model."""
        result = store.delete_model(9999)
        assert result is False


class TestDownloadOperations:
    """Tests for download CRUD operations."""

    def test_create_download(self, store: ModelarrStore) -> None:
        """Test creating a download record."""
        model = store.upsert_model("test/model", "test", "model")
        download = store.create_download(
            model_id=model.id,
            status="queued",
            total_bytes=10000000,
        )

        assert download.id is not None
        assert download.model_id == model.id
        assert download.status == "queued"
        assert download.bytes_downloaded == 0
        assert download.total_bytes == 10000000

    def test_create_download_with_start_time(self, store: ModelarrStore) -> None:
        """Test creating a download with start time."""
        model = store.upsert_model("test/model", "test", "model")
        now = datetime.now()
        download = store.create_download(
            model_id=model.id,
            status="downloading",
            started_at=now,
        )

        assert download.started_at is not None

    def test_update_download_progress(self, store: ModelarrStore) -> None:
        """Test updating download progress."""
        model = store.upsert_model("test/model", "test", "model")
        download = store.create_download(model_id=model.id)

        updated = store.update_download(
            download.id,
            status="downloading",
            bytes_downloaded=5000000,
        )

        assert updated is not None
        assert updated.status == "downloading"
        assert updated.bytes_downloaded == 5000000

    def test_update_download_complete(self, store: ModelarrStore) -> None:
        """Test marking a download as complete."""
        model = store.upsert_model("test/model", "test", "model")
        download = store.create_download(model_id=model.id, total_bytes=10000000)

        now = datetime.now()
        updated = store.update_download(
            download.id,
            status="complete",
            bytes_downloaded=10000000,
            completed_at=now,
        )

        assert updated is not None
        assert updated.status == "complete"
        assert updated.completed_at is not None

    def test_update_download_failed(self, store: ModelarrStore) -> None:
        """Test marking a download as failed."""
        model = store.upsert_model("test/model", "test", "model")
        download = store.create_download(model_id=model.id)

        updated = store.update_download(
            download.id,
            status="failed",
            error="Connection timeout",
        )

        assert updated is not None
        assert updated.status == "failed"
        assert updated.error == "Connection timeout"

    def test_update_download_nonexistent(self, store: ModelarrStore) -> None:
        """Test updating a nonexistent download."""
        result = store.update_download(9999, status="complete")
        assert result is None

    def test_get_download(self, store: ModelarrStore) -> None:
        """Test getting a download by ID."""
        model = store.upsert_model("test/model", "test", "model")
        download = store.create_download(model_id=model.id)

        retrieved = store.get_download(download.id)

        assert retrieved is not None
        assert retrieved.id == download.id
        assert retrieved.model_id == model.id

    def test_get_download_nonexistent(self, store: ModelarrStore) -> None:
        """Test getting a nonexistent download."""
        result = store.get_download(9999)
        assert result is None

    def test_get_active_downloads(self, store: ModelarrStore) -> None:
        """Test getting active downloads."""
        model1 = store.upsert_model("test/model1", "test", "model1")
        model2 = store.upsert_model("test/model2", "test", "model2")
        model3 = store.upsert_model("test/model3", "test", "model3")

        store.create_download(model_id=model1.id, status="queued")
        store.create_download(model_id=model2.id, status="downloading")
        dl3 = store.create_download(model_id=model3.id, status="complete")

        active = store.get_active_downloads()

        assert len(active) == 2
        assert all(d.status in ("queued", "downloading", "paused") for d in active)
        assert dl3.id not in [d.id for d in active]

    def test_get_download_history(self, store: ModelarrStore) -> None:
        """Test getting download history."""
        model1 = store.upsert_model("test/model1", "test", "model1")
        model2 = store.upsert_model("test/model2", "test", "model2")
        model3 = store.upsert_model("test/model3", "test", "model3")

        store.create_download(model_id=model1.id, status="queued")
        now = datetime.now()
        store.create_download(model_id=model2.id, status="complete")
        store.update_download(2, status="complete", completed_at=now)
        store.create_download(model_id=model3.id, status="failed")

        history = store.get_download_history()

        assert len(history) == 2
        assert all(d.status in ("complete", "failed") for d in history)

    def test_get_download_history_limit(self, store: ModelarrStore) -> None:
        """Test download history with limit."""
        model = store.upsert_model("test/model", "test", "model")

        for i in range(5):
            store.create_download(model_id=model.id, status="complete")
            store.update_download(i + 1, status="complete")

        history = store.get_download_history(limit=2)

        assert len(history) <= 2


class TestConfigOperations:
    """Tests for config CRUD operations."""

    def test_get_config_missing(self, store: ModelarrStore) -> None:
        """Test getting a config value that doesn't exist."""
        result = store.get_config("missing_key")
        assert result is None

    def test_get_config_with_default(self, store: ModelarrStore) -> None:
        """Test getting a config value with default."""
        result = store.get_config("missing_key", default="default_value")
        assert result == "default_value"

    def test_set_and_get_config(self, store: ModelarrStore) -> None:
        """Test setting and getting a config value."""
        store.set_config("test_key", "test_value")
        result = store.get_config("test_key")

        assert result == "test_value"

    def test_update_config(self, store: ModelarrStore) -> None:
        """Test updating a config value."""
        store.set_config("key", "value1")
        store.set_config("key", "value2")

        result = store.get_config("key")
        assert result == "value2"

    def test_config_multiple_keys(self, store: ModelarrStore) -> None:
        """Test storing multiple config keys."""
        store.set_config("key1", "value1")
        store.set_config("key2", "value2")
        store.set_config("key3", "value3")

        assert store.get_config("key1") == "value1"
        assert store.get_config("key2") == "value2"
        assert store.get_config("key3") == "value3"
