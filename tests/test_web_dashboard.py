"""Tests for the dashboard web page."""

from pathlib import Path

from fastapi.testclient import TestClient

from modelarr.db import get_db_path, init_db
from modelarr.store import ModelarrStore
from modelarr.web.app import create_app


def test_dashboard_loads(tmp_path):
    """Test that the dashboard loads."""
    # Create a temporary database
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    app = create_app()
    client = TestClient(app)

    response = client.get("/")
    assert response.status_code == 200
    assert "Dashboard" in response.text


def test_dashboard_check_endpoint(tmp_path):
    """Test that dashboard check endpoint works."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    app = create_app()
    client = TestClient(app)

    response = client.post("/dashboard/check")
    assert response.status_code == 200
    assert "toast" in response.text
