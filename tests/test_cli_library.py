"""Tests for library and download CLI commands."""

from datetime import UTC, datetime

from typer.testing import CliRunner

from modelarr.cli import app
from modelarr.db import init_db
from modelarr.store import ModelarrStore

runner = CliRunner()


def test_library_list_empty(tmp_path):
    """Test listing empty library."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)
    library_path = tmp_path / "library"

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        store = ModelarrStore(db_path)
        store.set_config("library_path", str(library_path))
        return store

    modelarr.cli._get_store = mock_get_store

    try:
        result = runner.invoke(app, ["library", "list"])
        assert result.exit_code == 0
        assert "No downloaded models found" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_library_list_with_models(tmp_path):
    """Test listing library with models."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)
    library_path = tmp_path / "library"

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        store = ModelarrStore(db_path)
        store.set_config("library_path", str(library_path))
        return store

    modelarr.cli._get_store = mock_get_store

    try:
        store = mock_get_store()
        # Create some test models
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model1",
            author="test",
            name="model1",
            format_="gguf",
            quantization="Q4_K_M",
            size_bytes=5 * (1024**3),
            downloaded_at=now,
            local_path=str(library_path / "test" / "model1"),
        )
        store.upsert_model(
            repo_id="test/model2",
            author="test",
            name="model2",
            format_="mlx",
            quantization="4bit",
            size_bytes=10 * (1024**3),
            downloaded_at=now,
            local_path=str(library_path / "test" / "model2"),
        )

        result = runner.invoke(app, ["library", "list"])
        assert result.exit_code == 0
        assert "test/model1" in result.stdout
        assert "test/model2" in result.stdout
        assert "5.00 GB" in result.stdout
        assert "10.00 GB" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_library_size(tmp_path):
    """Test showing total library size."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)
    library_path = tmp_path / "library"

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        store = ModelarrStore(db_path)
        store.set_config("library_path", str(library_path))
        return store

    modelarr.cli._get_store = mock_get_store

    try:
        store = mock_get_store()
        now = datetime.now(UTC)
        store.upsert_model(
            repo_id="test/model1",
            author="test",
            name="model1",
            size_bytes=5 * (1024**3),
            downloaded_at=now,
            local_path=str(library_path / "test" / "model1"),
        )
        store.upsert_model(
            repo_id="test/model2",
            author="test",
            name="model2",
            size_bytes=7 * (1024**3),
            downloaded_at=now,
            local_path=str(library_path / "test" / "model2"),
        )

        result = runner.invoke(app, ["library", "size"])
        assert result.exit_code == 0
        assert "across 2 models" in result.stdout
        assert "12.00 GB" in result.stdout or "11.99 GB" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_library_remove_not_found(tmp_path):
    """Test removing non-existent model."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)
    library_path = tmp_path / "library"

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        store = ModelarrStore(db_path)
        store.set_config("library_path", str(library_path))
        return store

    modelarr.cli._get_store = mock_get_store

    try:
        result = runner.invoke(app, ["library", "remove", "nonexistent/model"])
        assert result.exit_code == 1
        assert "not found or not downloaded" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_download_status_empty(tmp_path):
    """Test download status with no downloads."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        result = runner.invoke(app, ["download", "status"])
        assert result.exit_code == 0
        assert "No active downloads" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_download_status_with_active(tmp_path):
    """Test download status with active downloads."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        store = mock_get_store()

        # Create a model and download
        now = datetime.now(UTC)
        model = store.upsert_model(
            repo_id="test/model",
            author="test",
            name="model",
            size_bytes=10 * (1024**3),
        )
        download = store.create_download(
            model_id=model.id,
            status="downloading",
            started_at=now,
            total_bytes=10 * (1024**3),
        )
        store.update_download(
            download.id,
            bytes_downloaded=5 * (1024**3),
        )

        result = runner.invoke(app, ["download", "status"])
        assert result.exit_code == 0
        assert "Active Downloads" in result.stdout
        assert "downloading" in result.stdout
        assert "50.0%" in result.stdout or "50" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_config_set_and_show(tmp_path):
    """Test setting and showing configuration."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        return ModelarrStore(db_path)

    modelarr.cli._get_store = mock_get_store

    try:
        # Set config
        result = runner.invoke(app, ["config", "set", "library_path", "/data/models"])
        assert result.exit_code == 0
        assert "Set library_path = /data/models" in result.stdout

        # Show config
        result = runner.invoke(app, ["config", "show"])
        assert result.exit_code == 0
        assert "library_path" in result.stdout
        assert "/data/models" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store


def test_library_list_sort(tmp_path):
    """Test library list with different sort orders."""
    import modelarr.cli

    db_path = tmp_path / "test.db"
    init_db(db_path)
    library_path = tmp_path / "library"

    original_get_store = modelarr.cli._get_store

    def mock_get_store():
        store = ModelarrStore(db_path)
        store.set_config("library_path", str(library_path))
        return store

    modelarr.cli._get_store = mock_get_store

    try:
        store = mock_get_store()
        now = datetime.now(UTC)

        # Create models with different sizes and names
        store.upsert_model(
            repo_id="z/zulu",
            author="z",
            name="zulu",
            size_bytes=3 * (1024**3),
            downloaded_at=now,
            local_path=str(library_path / "z" / "zulu"),
        )
        store.upsert_model(
            repo_id="a/alpha",
            author="a",
            name="alpha",
            size_bytes=10 * (1024**3),
            downloaded_at=now,
            local_path=str(library_path / "a" / "alpha"),
        )

        # Sort by name
        result = runner.invoke(app, ["library", "list", "--sort", "name"])
        assert result.exit_code == 0
        # alpha should appear before zulu when sorted by name
        assert "a/alpha" in result.stdout
        assert "z/zulu" in result.stdout

        # Sort by size
        result = runner.invoke(app, ["library", "list", "--sort", "size"])
        assert result.exit_code == 0
        assert "a/alpha" in result.stdout
        assert "z/zulu" in result.stdout

    finally:
        modelarr.cli._get_store = original_get_store
