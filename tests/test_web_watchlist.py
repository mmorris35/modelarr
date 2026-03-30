"""Tests for the watchlist web page."""


from fastapi.testclient import TestClient

from modelarr.db import init_db
from modelarr.models import WatchlistFilters
from modelarr.store import ModelarrStore
from modelarr.web.app import create_app


def test_watchlist_page_loads(tmp_path):
    """Test that the watchlist page loads."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    app = create_app()
    client = TestClient(app)

    response = client.get("/watchlist")
    assert response.status_code == 200
    assert "Watchlist" in response.text


def test_add_watch(tmp_path):
    """Test adding a watchlist entry."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    app = create_app()
    client = TestClient(app)

    response = client.post(
        "/watchlist",
        data={
            "type": "model",
            "value": "mlx-community/Qwen3-8B",
            "format": "mlx",
            "quant": "4bit",
        },
    )
    assert response.status_code == 200
    assert "mlx-community/Qwen3-8B" in response.text


def test_delete_watch(tmp_path):
    """Test deleting a watchlist entry."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    # Add a watch first
    entry = store.add_watch(
        type_="model",
        value="test/model",
        filters=WatchlistFilters(),
    )

    app = create_app()
    client = TestClient(app)

    response = client.delete(f"/watchlist/{entry.id}")
    assert response.status_code == 200


def test_toggle_watch(tmp_path):
    """Test toggling a watchlist entry."""
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = ModelarrStore(db_path)
    store.set_config("library_path", str(tmp_path / "library"))

    # Add a watch first
    entry = store.add_watch(
        type_="model",
        value="test/model",
        filters=WatchlistFilters(),
    )

    app = create_app()
    client = TestClient(app)

    response = client.patch(f"/watchlist/{entry.id}/toggle")
    assert response.status_code == 200
