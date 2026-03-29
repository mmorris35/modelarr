"""Tests for Pydantic models."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from modelarr.models import (
    DownloadRecord,
    ModelInfo,
    ModelRecord,
    WatchlistEntry,
    WatchlistFilters,
)


class TestWatchlistFilters:
    """Tests for WatchlistFilters model."""

    def test_create_with_defaults(self) -> None:
        """Test creating WatchlistFilters with default values."""
        filters = WatchlistFilters()

        assert filters.min_size_b is None
        assert filters.max_size_b is None
        assert filters.formats is None
        assert filters.quantizations is None

    def test_create_with_values(self) -> None:
        """Test creating WatchlistFilters with values."""
        filters = WatchlistFilters(
            min_size_b=1000,
            max_size_b=5000,
            formats=["gguf", "mlx"],
            quantizations=["4bit", "8bit"],
        )

        assert filters.min_size_b == 1000
        assert filters.max_size_b == 5000
        assert filters.formats == ["gguf", "mlx"]
        assert filters.quantizations == ["4bit", "8bit"]

    def test_serialize_to_dict(self) -> None:
        """Test serializing WatchlistFilters to dict."""
        filters = WatchlistFilters(min_size_b=1000, formats=["gguf"])
        data = filters.model_dump()

        assert data["min_size_b"] == 1000
        assert data["formats"] == ["gguf"]
        assert data["max_size_b"] is None


class TestWatchlistEntry:
    """Tests for WatchlistEntry model."""

    def test_create_model_entry(self) -> None:
        """Test creating a model watchlist entry."""
        now = datetime.now()
        entry = WatchlistEntry(
            id=1,
            type="model",
            value="mlx-community/Qwen3.5-27B-MLX-4bit",
            created_at=now,
            updated_at=now,
        )

        assert entry.id == 1
        assert entry.type == "model"
        assert entry.value == "mlx-community/Qwen3.5-27B-MLX-4bit"
        assert entry.enabled is True
        assert entry.filters.min_size_b is None

    def test_create_author_entry_with_filters(self) -> None:
        """Test creating an author watchlist entry with filters."""
        now = datetime.now()
        filters = WatchlistFilters(formats=["mlx"], quantizations=["4bit"])
        entry = WatchlistEntry(
            id=2,
            type="author",
            value="mlx-community",
            filters=filters,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        assert entry.type == "author"
        assert entry.filters.formats == ["mlx"]
        assert entry.filters.quantizations == ["4bit"]

    def test_invalid_type_raises_error(self) -> None:
        """Test that invalid type raises ValidationError."""
        now = datetime.now()
        with pytest.raises(ValidationError):
            WatchlistEntry(
                id=1,
                type="invalid_type",  # type: ignore
                value="test",
                created_at=now,
                updated_at=now,
            )

    def test_serialize_round_trip(self) -> None:
        """Test serializing and deserializing WatchlistEntry."""
        now = datetime.now()
        original = WatchlistEntry(
            id=1,
            type="query",
            value="opus distilled",
            filters=WatchlistFilters(formats=["gguf"]),
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        data = original.model_dump()
        restored = WatchlistEntry(**data)

        assert restored.id == original.id
        assert restored.type == original.type
        assert restored.value == original.value
        assert restored.filters.formats == original.filters.formats


class TestModelRecord:
    """Tests for ModelRecord model."""

    def test_create_minimal(self) -> None:
        """Test creating ModelRecord with minimal fields."""
        record = ModelRecord(
            id=1,
            repo_id="mlx-community/Qwen3.5-27B-MLX-4bit",
            author="mlx-community",
            name="Qwen3.5-27B-MLX-4bit",
        )

        assert record.id == 1
        assert record.repo_id == "mlx-community/Qwen3.5-27B-MLX-4bit"
        assert record.author == "mlx-community"
        assert record.name == "Qwen3.5-27B-MLX-4bit"
        assert record.format is None
        assert record.size_bytes is None
        assert record.local_path is None

    def test_create_full(self) -> None:
        """Test creating ModelRecord with all fields."""
        downloaded_at = datetime.now()
        record = ModelRecord(
            id=1,
            repo_id="mlx-community/Qwen3.5-27B-MLX-4bit",
            author="mlx-community",
            name="Qwen3.5-27B-MLX-4bit",
            format="mlx",
            quantization="4bit",
            size_bytes=14000000000,
            last_commit="abc123",
            downloaded_at=downloaded_at,
            local_path="/data/models/mlx-community/Qwen3.5-27B-MLX-4bit",
            metadata={"tags": ["mlx", "4bit"], "downloads": 100},
        )

        assert record.format == "mlx"
        assert record.quantization == "4bit"
        assert record.size_bytes == 14000000000
        assert record.local_path == "/data/models/mlx-community/Qwen3.5-27B-MLX-4bit"
        assert record.metadata["tags"] == ["mlx", "4bit"]

    def test_metadata_defaults_to_empty_dict(self) -> None:
        """Test that metadata defaults to empty dict."""
        record = ModelRecord(
            id=1,
            repo_id="test/model",
            author="test",
            name="model",
        )

        assert record.metadata == {}


class TestDownloadRecord:
    """Tests for DownloadRecord model."""

    def test_create_queued(self) -> None:
        """Test creating a queued download record."""
        record = DownloadRecord(
            id=1,
            model_id=1,
            status="queued",
        )

        assert record.id == 1
        assert record.model_id == 1
        assert record.status == "queued"
        assert record.started_at is None
        assert record.error is None

    def test_create_downloading(self) -> None:
        """Test creating a downloading record."""
        started = datetime.now()
        record = DownloadRecord(
            id=1,
            model_id=1,
            status="downloading",
            started_at=started,
            bytes_downloaded=1000000,
            total_bytes=10000000,
        )

        assert record.status == "downloading"
        assert record.bytes_downloaded == 1000000
        assert record.total_bytes == 10000000

    def test_create_complete(self) -> None:
        """Test creating a completed download record."""
        started = datetime.now()
        completed = datetime.now()
        record = DownloadRecord(
            id=1,
            model_id=1,
            status="complete",
            started_at=started,
            completed_at=completed,
            bytes_downloaded=10000000,
            total_bytes=10000000,
        )

        assert record.status == "complete"
        assert record.completed_at == completed

    def test_create_failed(self) -> None:
        """Test creating a failed download record."""
        record = DownloadRecord(
            id=1,
            model_id=1,
            status="failed",
            error="Connection timeout",
        )

        assert record.status == "failed"
        assert record.error == "Connection timeout"

    def test_invalid_status_raises_error(self) -> None:
        """Test that invalid status raises ValidationError."""
        with pytest.raises(ValidationError):
            DownloadRecord(
                id=1,
                model_id=1,
                status="invalid_status",  # type: ignore
            )


class TestModelInfo:
    """Tests for ModelInfo model."""

    def test_create_minimal(self) -> None:
        """Test creating ModelInfo with minimal fields."""
        info = ModelInfo(
            repo_id="mlx-community/test",
            author="mlx-community",
            name="test",
        )

        assert info.repo_id == "mlx-community/test"
        assert info.author == "mlx-community"
        assert info.name == "test"
        assert info.files == []
        assert info.tags == []
        assert info.downloads is None

    def test_create_full(self) -> None:
        """Test creating ModelInfo with all fields."""
        modified = datetime.now()
        info = ModelInfo(
            repo_id="mlx-community/Qwen3.5-27B-MLX-4bit",
            author="mlx-community",
            name="Qwen3.5-27B-MLX-4bit",
            files=[
                {"name": "model.safetensors", "size": 14000000000},
                {"name": "config.json", "size": 5000},
            ],
            last_modified=modified,
            tags=["mlx", "4bit", "nlp"],
            downloads=500,
            format="mlx",
            quantization="4bit",
            size_bytes=14000005000,
        )

        assert info.format == "mlx"
        assert info.quantization == "4bit"
        assert len(info.files) == 2
        assert info.tags == ["mlx", "4bit", "nlp"]
        assert info.downloads == 500

    def test_serialize_round_trip(self) -> None:
        """Test serializing and deserializing ModelInfo."""
        modified = datetime.now()
        original = ModelInfo(
            repo_id="test/model",
            author="test",
            name="model",
            last_modified=modified,
            tags=["test"],
        )

        data = original.model_dump()
        restored = ModelInfo(**data)

        assert restored.repo_id == original.repo_id
        assert restored.tags == original.tags
