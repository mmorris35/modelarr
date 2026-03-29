"""Tests for monitor and config CLI commands."""

from typer.testing import CliRunner
from unittest.mock import patch, MagicMock

from modelarr.cli import app
from modelarr.db import init_db
from modelarr.store import ModelarrStore

runner = CliRunner()


def test_monitor_status(tmp_path):
    """Test monitor status command."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        store = ModelarrStore(db_path)
        store.set_config("interval_minutes", "60")
        return store

    modelarr.cli._get_store = mock_get_store

    try:
        result = runner.invoke(app, ["monitor", "status"])
        assert result.exit_code == 0
        assert "Monitor Status" in result.stdout
        assert "Interval: 60 minutes" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_monitor_status_with_watches(tmp_path):
    """Test monitor status with enabled watches."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        store = ModelarrStore(db_path)
        store.set_config("interval_minutes", "30")
        return store

    modelarr.cli._get_store = mock_get_store

    try:
        store = mock_get_store()
        store.add_watch("model", "test/model1")
        store.add_watch("author", "test_author")

        result = runner.invoke(app, ["monitor", "status"])
        assert result.exit_code == 0
        assert "Enabled watches: 2" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_config_set(tmp_path):
    """Test setting configuration."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        result = runner.invoke(
            app, ["config", "set", "telegram_bot_token", "123:ABC"]
        )
        assert result.exit_code == 0
        assert "Set telegram_bot_token = 123:ABC" in result.stdout

        store = mock_get_store()
        assert store.get_config("telegram_bot_token") == "123:ABC"

    finally:
        modelarr.cli._get_store = original_get_store


def test_config_show_hides_secrets(tmp_path):
    """Test that config show hides sensitive values."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        store = mock_get_store()
        store.set_config("telegram_bot_token", "secret123")
        store.set_config("library_path", "/data/models")

        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "telegram_bot_token" in result.stdout
        assert "***hidden***" in result.stdout
        assert "secret123" not in result.stdout
        assert "library_path" in result.stdout
        assert "/data/models" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_config_show_empty(tmp_path):
    """Test config show with no configuration."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "No configuration set" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


@patch("modelarr.cli.ModelarrMonitor")
def test_monitor_check(mock_monitor_class, tmp_path):
    """Test monitor check command."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    # Mock the monitor instance
    mock_monitor = MagicMock()
    mock_monitor.run_once.return_value = []
    mock_monitor_class.return_value = mock_monitor

    try:
        result = runner.invoke(app, ["monitor", "check"])
        assert result.exit_code == 0
        assert "Running monitor check" in result.stdout
        assert "No new models found" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


@patch("modelarr.cli.ModelarrMonitor")
def test_monitor_check_with_results(mock_monitor_class, tmp_path):
    """Test monitor check with downloaded models."""
    import modelarr.cli
    from modelarr.models import ModelInfo, WatchlistEntry

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    # Create mock objects
    from datetime import UTC, datetime
    now = datetime.now(UTC)
    watch = WatchlistEntry(
        id=1,
        type="query",
        value="test",
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    model = ModelInfo(
        repo_id="test/model",
        author="test",
        name="model",
        size_bytes=5 * (1024**3),
    )

    # Mock the monitor instance
    mock_monitor = MagicMock()
    mock_monitor.run_once.return_value = [(watch, model)]
    mock_monitor_class.return_value = mock_monitor

    try:
        result = runner.invoke(app, ["monitor", "check"])
        assert result.exit_code == 0
        assert "Downloaded 1 model(s)" in result.stdout
        assert "test/model" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_format_bytes():
    """Test the format_bytes helper function."""
    import modelarr.cli

    assert modelarr.cli._format_bytes(0) == "0.00 B"
    assert modelarr.cli._format_bytes(1024) == "1.00 KB"
    assert modelarr.cli._format_bytes(1024 * 1024) == "1.00 MB"
    assert modelarr.cli._format_bytes(1024 * 1024 * 1024) == "1.00 GB"
    assert modelarr.cli._format_bytes(5 * 1024 * 1024 * 1024) == "5.00 GB"
    assert modelarr.cli._format_bytes(None) == "Unknown"
