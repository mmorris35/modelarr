"""Tests for watch CLI commands."""

from typer.testing import CliRunner

import modelarr.cli
from modelarr.cli import app
from modelarr.db import init_db
from modelarr.store import ModelarrStore

runner = CliRunner()


def test_watch_add_model(tmp_path):
    """Test adding a model watch."""
    # Override db path for test

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        result = runner.invoke(
            app, ["watch", "add", "model", "mlx-community/Qwen3.5-27B-MLX-4bit"]
        )
        assert result.exit_code == 0
        assert "Added model watch" in result.stdout

        store = mock_get_store()
        watches = store.list_watches()
        assert len(watches) == 1
        assert watches[0].type == "model"
        assert watches[0].value == "mlx-community/Qwen3.5-27B-MLX-4bit"

    finally:
        modelarr.cli._get_store = original_get_store


def test_watch_add_author_with_filters(tmp_path):
    """Test adding an author watch with filters."""
    import modelarr.cli
    from modelarr.db import init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        result = runner.invoke(
            app,
            [
                "watch",
                "add",
                "author",
                "Jackrong",
                "--format",
                "mlx",
                "--quant",
                "4bit",
            ],
        )
        assert result.exit_code == 0
        assert "Added author watch" in result.stdout

        store = mock_get_store()
        watches = store.list_watches()
        assert len(watches) == 1
        assert watches[0].type == "author"
        assert watches[0].value == "Jackrong"
        assert watches[0].filters.formats == ["mlx"]
        assert watches[0].filters.quantizations == ["4bit"]

    finally:
        modelarr.cli._get_store = original_get_store


def test_watch_list(tmp_path):
    """Test listing watches."""
    import modelarr.cli
    from modelarr.db import init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        # Add a watch
        result = runner.invoke(
            app, ["watch", "add", "query", "mistral distilled"]
        )
        assert result.exit_code == 0

        # List watches
        result = runner.invoke(app, ["watch", "list"])
        assert result.exit_code == 0
        assert "mistral distilled" in result.stdout
        assert "query" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_watch_list_enabled_only(tmp_path):
    """Test listing only enabled watches."""
    import modelarr.cli
    from modelarr.db import init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        # Add and toggle a watch
        runner.invoke(app, ["watch", "add", "query", "watch1"])
        runner.invoke(app, ["watch", "add", "query", "watch2"])
        runner.invoke(app, ["watch", "toggle", "1"])

        # List enabled only
        result = runner.invoke(app, ["watch", "list", "--enabled-only"])
        assert result.exit_code == 0
        assert "watch2" in result.stdout
        assert "watch1" not in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_watch_remove(tmp_path):
    """Test removing a watch."""
    import modelarr.cli
    from modelarr.db import init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        # Add and remove a watch
        result = runner.invoke(app, ["watch", "add", "model", "test-model"])
        assert result.exit_code == 0

        result = runner.invoke(app, ["watch", "remove", "1"])
        assert result.exit_code == 0
        assert "Removed watch ID 1" in result.stdout

        store = mock_get_store()
        watches = store.list_watches()
        assert len(watches) == 0

    finally:
        modelarr.cli._get_store = original_get_store


def test_watch_toggle(tmp_path):
    """Test toggling a watch."""
    import modelarr.cli
    from modelarr.db import init_db

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        # Add and toggle
        runner.invoke(app, ["watch", "add", "model", "test-model"])
        store = mock_get_store()
        watch = store.list_watches()[0]
        assert watch.enabled is True

        result = runner.invoke(app, ["watch", "toggle", "1"])
        assert result.exit_code == 0
        assert "disabled" in result.stdout

        watch = store.get_watch(1)
        assert watch.enabled is False

        # Toggle back
        runner.invoke(app, ["watch", "toggle", "1"])
        watch = store.get_watch(1)
        assert watch.enabled is True

    finally:
        modelarr.cli._get_store = original_get_store
