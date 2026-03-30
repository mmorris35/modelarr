"""CRUD operations for modelarr entities."""

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from modelarr.db import get_connection, init_db
from modelarr.models import (
    DownloadRecord,
    ModelRecord,
    WatchlistEntry,
    WatchlistFilters,
)


class ModelarrStore:
    """SQLite-backed store for watchlist, models, and downloads."""

    def __init__(self, db_path: Path) -> None:
        """Initialize the store and ensure database is set up.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = db_path
        init_db(db_path)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        return get_connection(self.db_path)

    # Watchlist operations

    def add_watch(
        self,
        type_: str,
        value: str,
        filters: WatchlistFilters | None = None,
        enabled: bool = True,
    ) -> WatchlistEntry:
        """Add a watchlist entry.

        Args:
            type_: Type of watch (model, author, query, family)
            value: The value to watch (repo_id, author name, search query, etc.)
            filters: Optional filters for the watch
            enabled: Whether the watch is enabled

        Returns:
            The created WatchlistEntry with ID
        """
        now = datetime.now(UTC).isoformat()
        if filters is None:
            filters = WatchlistFilters()

        filters_json = filters.model_dump_json()

        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO watchlist (type, value, filters, enabled, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (type_, value, filters_json, enabled, now, now),
        )
        conn.commit()
        watch_id: int = cursor.lastrowid  # type: ignore[assignment]
        conn.close()

        return WatchlistEntry(
            id=watch_id,
            type=type_,  # type: ignore
            value=value,
            filters=filters,
            enabled=enabled,
            created_at=datetime.fromisoformat(now),
            updated_at=datetime.fromisoformat(now),
        )

    def remove_watch(self, watch_id: int) -> bool:
        """Remove a watchlist entry.

        Args:
            watch_id: ID of the watchlist entry to remove

        Returns:
            True if the entry was deleted, False if it didn't exist
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM watchlist WHERE id = ?", (watch_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()

        return deleted

    def list_watches(self, enabled_only: bool = False) -> list[WatchlistEntry]:
        """List all watchlist entries.

        Args:
            enabled_only: If True, only return enabled entries

        Returns:
            List of WatchlistEntry objects
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        if enabled_only:
            cursor.execute("SELECT * FROM watchlist WHERE enabled = 1")
        else:
            cursor.execute("SELECT * FROM watchlist")

        rows = cursor.fetchall()
        conn.close()

        entries = []
        for row in rows:
            filters_dict = json.loads(row["filters"])
            filters = WatchlistFilters(**filters_dict)
            entry = WatchlistEntry(
                id=row["id"],
                type=row["type"],  # type: ignore
                value=row["value"],
                filters=filters,
                enabled=bool(row["enabled"]),
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
            )
            entries.append(entry)

        return entries

    def toggle_watch(self, watch_id: int) -> bool:
        """Toggle the enabled state of a watchlist entry.

        Args:
            watch_id: ID of the watchlist entry to toggle

        Returns:
            True if the entry was found and updated
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT enabled FROM watchlist WHERE id = ?", (watch_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return False

        new_enabled = not bool(row[0])
        now = datetime.now(UTC).isoformat()

        cursor.execute(
            "UPDATE watchlist SET enabled = ?, updated_at = ? WHERE id = ?",
            (new_enabled, now, watch_id),
        )
        conn.commit()
        conn.close()

        return True

    def get_watch(self, watch_id: int) -> WatchlistEntry | None:
        """Get a watchlist entry by ID.

        Args:
            watch_id: ID of the watchlist entry

        Returns:
            The WatchlistEntry if found, None otherwise
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM watchlist WHERE id = ?", (watch_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        filters_dict = json.loads(row["filters"])
        filters = WatchlistFilters(**filters_dict)

        return WatchlistEntry(
            id=row["id"],
            type=row["type"],  # type: ignore
            value=row["value"],
            filters=filters,
            enabled=bool(row["enabled"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # Model operations

    def upsert_model(
        self,
        repo_id: str,
        author: str,
        name: str,
        format_: str | None = None,
        quantization: str | None = None,
        size_bytes: int | None = None,
        last_commit: str | None = None,
        downloaded_at: datetime | None = None,
        local_path: str | None = None,
        metadata: dict | None = None,
    ) -> ModelRecord:
        """Insert or update a model record.

        Args:
            repo_id: Unique HuggingFace repo ID
            author: Model author
            name: Model name
            format_: Model format (gguf, mlx, etc.)
            quantization: Quantization level
            size_bytes: Total size in bytes
            last_commit: Latest commit SHA
            downloaded_at: When the model was downloaded
            local_path: Local path if downloaded
            metadata: Additional metadata dict

        Returns:
            The created or updated ModelRecord
        """
        if metadata is None:
            metadata = {}

        metadata_json = json.dumps(metadata)

        conn = self._get_conn()
        cursor = conn.cursor()

        # Check if model exists
        cursor.execute("SELECT id FROM models WHERE repo_id = ?", (repo_id,))
        existing = cursor.fetchone()

        if existing:
            model_id = existing[0]
            cursor.execute(
                """
                UPDATE models
                SET author = ?, name = ?, format = ?, quantization = ?,
                    size_bytes = ?, last_commit = ?, downloaded_at = ?,
                    local_path = ?, metadata = ?
                WHERE id = ?
                """,
                (
                    author,
                    name,
                    format_,
                    quantization,
                    size_bytes,
                    last_commit,
                    downloaded_at.isoformat() if downloaded_at else None,
                    local_path,
                    metadata_json,
                    model_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO models
                (repo_id, author, name, format, quantization, size_bytes,
                 last_commit, downloaded_at, local_path, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    repo_id,
                    author,
                    name,
                    format_,
                    quantization,
                    size_bytes,
                    last_commit,
                    downloaded_at.isoformat() if downloaded_at else None,
                    local_path,
                    metadata_json,
                ),
            )
            model_id = cursor.lastrowid

        conn.commit()
        conn.close()

        return ModelRecord(
            id=model_id,
            repo_id=repo_id,
            author=author,
            name=name,
            format=format_,
            quantization=quantization,
            size_bytes=size_bytes,
            last_commit=last_commit,
            downloaded_at=downloaded_at,
            local_path=local_path,
            metadata=metadata,
        )

    def get_model_by_id(self, model_id: int) -> ModelRecord | None:
        """Get a model record by ID.

        Args:
            model_id: The model database ID

        Returns:
            The ModelRecord if found, None otherwise
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM models WHERE id = ?", (model_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        return ModelRecord(
            id=row["id"],
            repo_id=row["repo_id"],
            author=row["author"],
            name=row["name"],
            format=row["format"],
            quantization=row["quantization"],
            size_bytes=row["size_bytes"],
            last_commit=row["last_commit"],
            downloaded_at=(
                datetime.fromisoformat(row["downloaded_at"])
                if row["downloaded_at"]
                else None
            ),
            local_path=row["local_path"],
            metadata=metadata,
        )

    def get_model_by_repo(self, repo_id: str) -> ModelRecord | None:
        """Get a model record by repo ID.

        Args:
            repo_id: The HuggingFace repo ID

        Returns:
            The ModelRecord if found, None otherwise
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM models WHERE repo_id = ?", (repo_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        return ModelRecord(
            id=row["id"],
            repo_id=row["repo_id"],
            author=row["author"],
            name=row["name"],
            format=row["format"],
            quantization=row["quantization"],
            size_bytes=row["size_bytes"],
            last_commit=row["last_commit"],
            downloaded_at=(
                datetime.fromisoformat(row["downloaded_at"])
                if row["downloaded_at"]
                else None
            ),
            local_path=row["local_path"],
            metadata=metadata,
        )

    def list_models(self) -> list[ModelRecord]:
        """List all models.

        Returns:
            List of ModelRecord objects
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM models")
        rows = cursor.fetchall()
        conn.close()

        models = []
        for row in rows:
            metadata = json.loads(row["metadata"]) if row["metadata"] else {}
            model = ModelRecord(
                id=row["id"],
                repo_id=row["repo_id"],
                author=row["author"],
                name=row["name"],
                format=row["format"],
                quantization=row["quantization"],
                size_bytes=row["size_bytes"],
                last_commit=row["last_commit"],
                downloaded_at=(
                    datetime.fromisoformat(row["downloaded_at"])
                    if row["downloaded_at"]
                    else None
                ),
                local_path=row["local_path"],
                metadata=metadata,
            )
            models.append(model)

        return models

    def delete_model(self, model_id: int) -> bool:
        """Delete a model record.

        Args:
            model_id: ID of the model to delete

        Returns:
            True if the model was deleted, False if it didn't exist
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM models WHERE id = ?", (model_id,))
        conn.commit()
        deleted = cursor.rowcount > 0
        conn.close()

        return deleted

    # Download operations

    def create_download(
        self,
        model_id: int,
        status: str = "queued",
        started_at: datetime | None = None,
        total_bytes: int | None = None,
    ) -> DownloadRecord:
        """Create a download record.

        Args:
            model_id: ID of the model being downloaded
            status: Initial status (default: queued)
            started_at: When the download started
            total_bytes: Total bytes to download

        Returns:
            The created DownloadRecord
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO downloads
            (model_id, status, started_at, bytes_downloaded, total_bytes)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                model_id,
                status,
                started_at.isoformat() if started_at else None,
                0,
                total_bytes,
            ),
        )
        conn.commit()
        download_id: int = cursor.lastrowid  # type: ignore[assignment]
        conn.close()

        return DownloadRecord(
            id=download_id,
            model_id=model_id,
            status=status,  # type: ignore
            started_at=started_at,
            completed_at=None,
            bytes_downloaded=0,
            total_bytes=total_bytes,
            error=None,
        )

    def update_download(
        self,
        download_id: int,
        status: str | None = None,
        bytes_downloaded: int | None = None,
        total_bytes: int | None = None,
        completed_at: datetime | None = None,
        error: str | None = None,
    ) -> DownloadRecord | None:
        """Update a download record.

        Args:
            download_id: ID of the download to update
            status: New status
            bytes_downloaded: Bytes downloaded so far
            total_bytes: Total bytes to download
            completed_at: When the download completed
            error: Error message if download failed

        Returns:
            The updated DownloadRecord, or None if not found
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Get current record
        cursor.execute("SELECT * FROM downloads WHERE id = ?", (download_id,))
        row = cursor.fetchone()

        if not row:
            conn.close()
            return None

        # Build update with provided values
        updates: list[str] = []
        values: list[str | int] = []

        if status is not None:
            updates.append("status = ?")
            values.append(status)
        if bytes_downloaded is not None:
            updates.append("bytes_downloaded = ?")
            values.append(bytes_downloaded)
        if total_bytes is not None:
            updates.append("total_bytes = ?")
            values.append(total_bytes)
        if completed_at is not None:
            updates.append("completed_at = ?")
            values.append(completed_at.isoformat())
        if error is not None:
            updates.append("error = ?")
            values.append(error)

        if updates:
            values.append(download_id)
            query = f"UPDATE downloads SET {', '.join(updates)} WHERE id = ?"
            cursor.execute(query, values)
            conn.commit()

        conn.close()

        return self.get_download(download_id)

    def get_download(self, download_id: int) -> DownloadRecord | None:
        """Get a download record by ID.

        Args:
            download_id: ID of the download

        Returns:
            The DownloadRecord if found, None otherwise
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM downloads WHERE id = ?", (download_id,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return None

        return DownloadRecord(
            id=row["id"],
            model_id=row["model_id"],
            status=row["status"],  # type: ignore
            started_at=(
                datetime.fromisoformat(row["started_at"]) if row["started_at"] else None
            ),
            completed_at=(
                datetime.fromisoformat(row["completed_at"])
                if row["completed_at"]
                else None
            ),
            bytes_downloaded=row["bytes_downloaded"],
            total_bytes=row["total_bytes"],
            error=row["error"],
        )

    def get_active_downloads(self) -> list[DownloadRecord]:
        """Get all active downloads (queued, downloading, paused).

        Returns:
            List of active DownloadRecord objects
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT * FROM downloads WHERE status IN ('queued', 'downloading', 'paused')"
        )
        rows = cursor.fetchall()
        conn.close()

        downloads = []
        for row in rows:
            download = DownloadRecord(
                id=row["id"],
                model_id=row["model_id"],
                status=row["status"],  # type: ignore
                started_at=(
                    datetime.fromisoformat(row["started_at"])
                    if row["started_at"]
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(row["completed_at"])
                    if row["completed_at"]
                    else None
                ),
                bytes_downloaded=row["bytes_downloaded"],
                total_bytes=row["total_bytes"],
                error=row["error"],
            )
            downloads.append(download)

        return downloads

    def get_download_history(self, limit: int = 100) -> list[DownloadRecord]:
        """Get download history (completed and failed downloads).

        Args:
            limit: Maximum number of records to return

        Returns:
            List of completed/failed DownloadRecord objects, most recent first
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM downloads
            WHERE status IN ('complete', 'failed')
            ORDER BY completed_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        rows = cursor.fetchall()
        conn.close()

        downloads = []
        for row in rows:
            download = DownloadRecord(
                id=row["id"],
                model_id=row["model_id"],
                status=row["status"],  # type: ignore
                started_at=(
                    datetime.fromisoformat(row["started_at"])
                    if row["started_at"]
                    else None
                ),
                completed_at=(
                    datetime.fromisoformat(row["completed_at"])
                    if row["completed_at"]
                    else None
                ),
                bytes_downloaded=row["bytes_downloaded"],
                total_bytes=row["total_bytes"],
                error=row["error"],
            )
            downloads.append(download)

        return downloads

    # Config operations

    def get_config(self, key: str, default: str | None = None) -> str | None:
        """Get a configuration value.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            The configuration value, or default if not found
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM config WHERE key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        if not row:
            return default

        result: str = row[0]
        return result

    def set_config(self, key: str, value: str) -> None:
        """Set a configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)", (key, value)
        )
        conn.commit()
        conn.close()
