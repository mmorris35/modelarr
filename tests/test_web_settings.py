"""Tests for the settings web page."""

from pathlib import Path

from fastapi.testclient import TestClient

from modelarr.db import init_db
from modelarr.store import ModelarrStore
from modelarr.web.app import create_app


def test_settings_page_loads(tmp_path):
    """Test that the settings page loads."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    app = create_app()
    client = TestClient(app)

    response = client.get("/settings")
    assert response.status_code == 200
    assert "Settings" in response.text


def test_save_settings(tmp_path):
    """Test saving settings."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    library_path = tmp_path / "library"
    library_path.mkdir()
    store.set_config("library_path", str(library_path))

    app = create_app()
    client = TestClient(app)

    new_path = tmp_path / "new_library"
    new_path.mkdir()

    response = client.post(
        "/settings",
        data={
            "library_path": str(new_path),
            "max_storage_gb": "100",
            "interval_minutes": "30",
        },
    )
    assert response.status_code == 200
    assert "toast" in response.text
