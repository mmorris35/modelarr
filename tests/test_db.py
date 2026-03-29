"""Tests for the database module."""

from pathlib import Path

from modelarr.db import get_connection, init_db


def test_init_db_creates_tables(tmp_path: Path) -> None:
    """Test that init_db creates all required tables."""
    db_path = tmp_path / "test.db"

    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Check all tables exist
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {row[0] for row in cursor.fetchall()}

    assert "watchlist" in tables
    assert "models" in tables
    assert "downloads" in tables
    assert "config" in tables

    conn.close()


def test_init_db_watchlist_schema(tmp_path: Path) -> None:
    """Test that watchlist table has correct columns."""
    db_path = tmp_path / "test.db"

    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(watchlist)")
    columns = {row[1] for row in cursor.fetchall()}

    assert "id" in columns
    assert "type" in columns
    assert "value" in columns
    assert "filters" in columns
    assert "enabled" in columns
    assert "created_at" in columns
    assert "updated_at" in columns

    conn.close()


def test_init_db_models_schema(tmp_path: Path) -> None:
    """Test that models table has correct columns."""
    db_path = tmp_path / "test.db"

    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(models)")
    columns = {row[1] for row in cursor.fetchall()}

    assert "id" in columns
    assert "repo_id" in columns
    assert "author" in columns
    assert "name" in columns
    assert "format" in columns
    assert "quantization" in columns
    assert "size_bytes" in columns
    assert "last_commit" in columns
    assert "downloaded_at" in columns
    assert "local_path" in columns
    assert "metadata" in columns

    conn.close()


def test_init_db_downloads_schema(tmp_path: Path) -> None:
    """Test that downloads table has correct columns."""
    db_path = tmp_path / "test.db"

    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(downloads)")
    columns = {row[1] for row in cursor.fetchall()}

    assert "id" in columns
    assert "model_id" in columns
    assert "status" in columns
    assert "started_at" in columns
    assert "completed_at" in columns
    assert "bytes_downloaded" in columns
    assert "total_bytes" in columns
    assert "error" in columns

    conn.close()


def test_init_db_config_schema(tmp_path: Path) -> None:
    """Test that config table has correct columns."""
    db_path = tmp_path / "test.db"

    init_db(db_path)

    conn = get_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(config)")
    columns = {row[1] for row in cursor.fetchall()}

    assert "key" in columns
    assert "value" in columns

    conn.close()


def test_get_connection_returns_row_factory(tmp_path: Path) -> None:
    """Test that get_connection returns a connection with Row factory."""
    db_path = tmp_path / "test.db"
    init_db(db_path)

    # Insert test data
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO config (key, value) VALUES (?, ?)", ("test_key", "test_value"))
    conn.commit()
    conn.close()

    # Get connection and test Row factory
    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM config WHERE key = 'test_key'")
    row = cursor.fetchone()

    # Row factory allows accessing by column name
    assert row["key"] == "test_key"
    assert row["value"] == "test_value"

    conn.close()


def test_init_db_idempotent(tmp_path: Path) -> None:
    """Test that init_db can be called multiple times without error."""
    db_path = tmp_path / "test.db"

    init_db(db_path)
    init_db(db_path)  # Should not raise

    conn = get_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    )
    tables = [row[0] for row in cursor.fetchall()]

    assert len(tables) == 4  # watchlist, models, downloads, config
    assert set(tables) == {"watchlist", "models", "downloads", "config"}

    conn.close()
