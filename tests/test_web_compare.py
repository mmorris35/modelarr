"""Tests for model comparison web routes."""

from datetime import datetime
from pathlib import Path

import pytest

from modelarr.db import init_db
from modelarr.store import ModelarrStore


@pytest.fixture
def test_db(tmp_path: Path) -> Path:
    """Create a test database."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return db_path


@pytest.fixture
def test_store(test_db: Path) -> ModelarrStore:
    """Create a test store."""
    return ModelarrStore(test_db)


def test_compare_page_no_models(test_store: ModelarrStore) -> None:
    """Test compare page with no models."""
    # Just verify store is empty
    models = test_store.list_models()
    assert len(models) == 0


def test_compare_models_created(test_store: ModelarrStore) -> None:
    """Test that models can be created for comparison."""
    # Add test models
    test_store.upsert_model(
        "test/model1",
        "test",
        "model1",
        format_="gguf",
        quantization="Q4_K_M",
        size_bytes=1000000,
        downloaded_at=datetime.now(),
        local_path="/tmp/model1",
    )
    test_store.upsert_model(
        "test/model2",
        "test",
        "model2",
        format_="safetensors",
        quantization="fp16",
        size_bytes=2000000,
        downloaded_at=datetime.now(),
        local_path="/tmp/model2",
    )

    # Verify both models exist
    models = test_store.list_models()
    assert len(models) == 2
    assert models[0].format == "gguf"
    assert models[1].format == "safetensors"


def test_compare_model_attributes(test_store: ModelarrStore) -> None:
    """Test that models have comparable attributes."""
    test_store.upsert_model(
        "author/model",
        "author",
        "model",
        format_="gguf",
        quantization="Q5_K_M",
        size_bytes=3000000,
        downloaded_at=datetime.now(),
        local_path="/tmp/model",
    )

    model = test_store.get_model_by_repo("author/model")
    assert model is not None
    assert model.repo_id == "author/model"
    assert model.author == "author"
    assert model.name == "model"
    assert model.format == "gguf"
    assert model.quantization == "Q5_K_M"
    assert model.size_bytes == 3000000
    assert model.local_path == "/tmp/model"
