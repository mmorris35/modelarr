"""Tests for the library web page."""

from fastapi.testclient import TestClient

from modelarr.db import init_db
from modelarr.store import ModelarrStore
from modelarr.web.app import create_app


def test_library_page_empty(tmp_path):
    """Test that the library page loads with no models."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    library_path = tmp_path / "library"
    library_path.mkdir()
    store.set_config("library_path", str(library_path))

    app = create_app()
    client = TestClient(app)

    response = client.get("/library")
    assert response.status_code == 200
    assert "Library" in response.text


def test_library_delete_model(tmp_path):
    """Test deleting a model from library."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    library_path = tmp_path / "library"
    library_path.mkdir()
    store.set_config("library_path", str(library_path))

    # Add a model to the library
    model_dir = library_path / "test" / "model"
    model_dir.mkdir(parents=True)
    (model_dir / "test.txt").write_text("test")

    store.upsert_model(
        repo_id="test/model",
        author="test",
        name="model",
        format_="mlx",
        quantization="4bit",
        size_bytes=1024,
        last_commit="abc123",
        local_path=str(model_dir),
    )

    app = create_app()
    client = TestClient(app)

    response = client.delete("/library/test/model")
    assert response.status_code == 200
