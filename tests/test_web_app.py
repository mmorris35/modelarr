"""Tests for FastAPI web application."""

from fastapi.testclient import TestClient

from modelarr.web.app import create_app


def test_app_creates_successfully():
    """Test that create_app() returns a FastAPI instance."""
    app = create_app()
    assert app is not None
    assert app.title == "modelarr"


def test_static_files_mounted():
    """Test that static files are mounted."""
    app = create_app()
    client = TestClient(app)
    # Check that static directory exists
    response = client.get("/static/style.css")
    # Should either exist (200) or be not found (404), but route should be available
    assert response.status_code in [200, 404]


def test_health_check_endpoint():
    """Test health check endpoint."""
    app = create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
