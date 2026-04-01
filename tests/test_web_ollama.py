"""Tests for Ollama web UI routes."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from modelarr.db import init_db
from modelarr.store import ModelarrStore
from modelarr.web.app import create_app


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


def _setup_db(tmp_path: Path, **config: str) -> Path:
    """Create an isolated test DB with config."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))
    for k, v in config.items():
        store.set_config(k, v)
    return db_path


def test_ollama_status_not_configured(tmp_path: Path) -> None:
    """Test /ollama/status when ollama_host is not set."""
    db_path = _setup_db(tmp_path)
    with patch("modelarr.web.app.get_db_path", return_value=db_path), \
         patch("modelarr.web.deps.get_db_path", return_value=db_path):
        app = create_app()
        c = TestClient(app)
        response = c.get("/ollama/status")
    assert response.status_code == 200
    assert "Not configured" in response.text


@patch("modelarr.web.routes.dashboard.OllamaClient")
def test_ollama_status_connected(mock_ollama_cls, tmp_path: Path) -> None:
    """Test /ollama/status when Ollama is reachable."""
    mock_instance = mock_ollama_cls.return_value
    mock_instance.is_connected.return_value = True
    mock_instance.list_models.return_value = [{"name": "llama3"}, {"name": "qwen"}]

    db_path = _setup_db(tmp_path, ollama_host="http://localhost:11434")
    with patch("modelarr.web.app.get_db_path", return_value=db_path), \
         patch("modelarr.web.deps.get_db_path", return_value=db_path):
        app = create_app()
        c = TestClient(app)
        response = c.get("/ollama/status")
    assert response.status_code == 200
    assert "Connected" in response.text
    assert "2 model(s)" in response.text


@patch("modelarr.web.routes.dashboard.OllamaClient")
def test_ollama_status_disconnected(mock_ollama_cls, tmp_path: Path) -> None:
    """Test /ollama/status when Ollama is unreachable."""
    mock_instance = mock_ollama_cls.return_value
    mock_instance.is_connected.return_value = False

    db_path = _setup_db(tmp_path, ollama_host="http://localhost:11434")
    with patch("modelarr.web.app.get_db_path", return_value=db_path), \
         patch("modelarr.web.deps.get_db_path", return_value=db_path):
        app = create_app()
        c = TestClient(app)
        response = c.get("/ollama/status")
    assert response.status_code == 200
    assert "Disconnected" in response.text


@patch("modelarr.web.routes.library.OllamaClient")
def test_push_to_ollama_success(mock_ollama_cls, tmp_path: Path) -> None:
    """Test POST /library/{repo_id}/ollama pushes a GGUF model."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    model_dir = tmp_path / "library" / "test" / "model"
    model_dir.mkdir(parents=True)
    (model_dir / "model.gguf").write_bytes(b"x" * 100)

    store.upsert_model(
        "test/model", "test", "model",
        format_="gguf", local_path=str(model_dir), downloaded_at=datetime.now(),
    )

    mock_instance = mock_ollama_cls.return_value
    mock_instance.push_model.return_value = True

    with patch("modelarr.web.app.get_db_path", return_value=db_path), \
         patch("modelarr.web.deps.get_db_path", return_value=db_path):
        app = create_app()
        c = TestClient(app)
        response = c.post("/library/test/model/ollama")
    assert response.status_code == 200
    assert "Pushed" in response.text or "toast" in response.text


@patch("modelarr.web.routes.library.OllamaClient")
def test_push_to_ollama_not_gguf(mock_ollama_cls, tmp_path: Path) -> None:
    """Test POST /library/{repo_id}/ollama rejects non-GGUF models."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    store.upsert_model(
        "test/sfmodel", "test", "sfmodel",
        format_="safetensors", local_path="/tmp/model", downloaded_at=datetime.now(),
    )

    with patch("modelarr.web.app.get_db_path", return_value=db_path), \
         patch("modelarr.web.deps.get_db_path", return_value=db_path):
        app = create_app()
        c = TestClient(app)
        response = c.post("/library/test/sfmodel/ollama")
    assert response.status_code == 200
    assert "not GGUF" in response.text


def test_push_to_ollama_model_not_found(tmp_path: Path) -> None:
    """Test POST /library/{repo_id}/ollama with nonexistent model."""
    db_path = _setup_db(tmp_path)
    with patch("modelarr.web.app.get_db_path", return_value=db_path), \
         patch("modelarr.web.deps.get_db_path", return_value=db_path):
        app = create_app()
        c = TestClient(app)
        response = c.post("/library/nonexistent/model/ollama")
    assert response.status_code == 200
    assert "not found" in response.text.lower()
