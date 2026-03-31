"""Tests for Ollama web UI routes."""

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


def test_ollama_host_config(test_store: ModelarrStore) -> None:
    """Test ollama_host configuration storage."""
    assert test_store.get_config("ollama_host") is None

    test_store.set_config("ollama_host", "http://localhost:11434")
    assert test_store.get_config("ollama_host") == "http://localhost:11434"

    test_store.set_config("ollama_host", "http://custom:11434")
    assert test_store.get_config("ollama_host") == "http://custom:11434"


def test_ollama_model_push_valid_format(test_store: ModelarrStore, tmp_path: Path) -> None:
    """Test that GGUF models can be pushed to Ollama."""
    # Create model with GGUF file
    model_dir = tmp_path / "model"
    model_dir.mkdir()
    (model_dir / "model.gguf").write_bytes(b"model data" * 1000)

    test_store.upsert_model(
        "test/model",
        "test",
        "model",
        format_="gguf",
        local_path=str(model_dir),
        downloaded_at=datetime.now(),
    )

    model = test_store.get_model_by_repo("test/model")
    assert model is not None
    assert model.format == "gguf"
    assert model.local_path == str(model_dir)


def test_ollama_model_push_non_gguf(test_store: ModelarrStore) -> None:
    """Test that non-GGUF models are not eligible for Ollama push."""
    test_store.upsert_model(
        "test/model",
        "test",
        "model",
        format_="safetensors",
        local_path="/tmp/model",
        downloaded_at=datetime.now(),
    )

    model = test_store.get_model_by_repo("test/model")
    assert model is not None
    assert model.format != "gguf"


def test_ollama_model_no_local_path(test_store: ModelarrStore) -> None:
    """Test that models without local_path cannot be pushed."""
    test_store.upsert_model(
        "test/model",
        "test",
        "model",
        format_="gguf",
        local_path=None,
    )

    model = test_store.get_model_by_repo("test/model")
    assert model is not None
    assert model.local_path is None
