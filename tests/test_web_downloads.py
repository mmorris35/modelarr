"""Tests for the downloads web page."""

from pathlib import Path

from fastapi.testclient import TestClient

from modelarr.db import init_db
from modelarr.store import ModelarrStore
from modelarr.web.app import create_app


def test_downloads_page_loads(tmp_path):
    """Test that the downloads page loads."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    app = create_app()
    client = TestClient(app)

    response = client.get("/downloads")
    assert response.status_code == 200
    assert "Downloads" in response.text


def test_active_downloads_endpoint(tmp_path):
    """Test the active downloads htmx endpoint."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    app = create_app()
    client = TestClient(app)

    response = client.get("/downloads/active")
    assert response.status_code == 200
