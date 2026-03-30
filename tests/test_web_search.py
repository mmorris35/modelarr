"""Tests for the search web page."""

from fastapi.testclient import TestClient

from modelarr.db import init_db
from modelarr.store import ModelarrStore
from modelarr.web.app import create_app


def test_search_page_loads(tmp_path):
    """Test that the search page loads."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    app = create_app()
    client = TestClient(app)

    response = client.get("/search")
    assert response.status_code == 200
    assert "Search" in response.text


def test_search_results(tmp_path):
    """Test search results endpoint."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    # Just test that the endpoint returns valid HTML
    app = create_app()
    client = TestClient(app)

    # Test with empty query
    response = client.get("/search/results?q=")
    assert response.status_code == 200
    assert "Enter at least 2 characters" in response.text


def test_add_from_search(tmp_path):
    """Test adding a model from search to watchlist."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/search/watch",
        data={
            "type": "model",
            "value": "test/model",
        },
    )
    assert response.status_code == 200
    assert "toast" in response.text
