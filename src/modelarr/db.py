"""SQLite database module for modelarr."""

import sqlite3
from pathlib import Path


def get_db_path() -> Path:
    """Get the path to the modelarr database.

    Returns:
        Path to ~/.config/modelarr/modelarr.db
    """
    config_dir = Path.home() / ".config" / "modelarr"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "modelarr.db"


def get_connection(db_path: Path) -> sqlite3.Connection:
    """Get a SQLite connection with Row factory.

    Args:
        db_path: Path to the database file

    Returns:
        sqlite3.Connection with row_factory=sqlite3.Row
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path) -> None:
    """Initialize the database schema if not already created.

    Creates the following tables if they don't exist:
    - watchlist: tracks models/authors/queries to watch
    - models: metadata for known models
    - downloads: download status tracking
    - config: key-value configuration store

    Args:
        db_path: Path to the database file
    """
    conn = get_connection(db_path)
    cursor = conn.cursor()

    # Watchlist table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS watchlist (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            type TEXT NOT NULL,
            value TEXT NOT NULL,
            filters TEXT NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)

    # Models table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS models (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            repo_id TEXT NOT NULL UNIQUE,
            author TEXT NOT NULL,
            name TEXT NOT NULL,
            format TEXT,
            quantization TEXT,
            size_bytes INTEGER,
            last_commit TEXT,
            downloaded_at TEXT,
            local_path TEXT,
            metadata TEXT
        )
    """)

    # Downloads table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            model_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT,
            bytes_downloaded INTEGER,
            total_bytes INTEGER,
            error TEXT,
            FOREIGN KEY (model_id) REFERENCES models (id)
        )
    """)

    # Config table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.commit()
    conn.close()
