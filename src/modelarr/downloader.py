"""Download manager for modelarr with resume support."""

import logging
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx

from modelarr.models import DownloadRecord, ModelInfo, ModelRecord
from modelarr.storage import StorageManager
from modelarr.store import ModelarrStore

logger = logging.getLogger(__name__)

_CHUNK_SIZE = 1024 * 1024  # 1MB chunks
_HF_CDN = "https://huggingface.co"


def _get_available_memory_mb() -> int | None:
    """Get available system memory in MB. Returns None if unavailable."""
    try:
        with open("/proc/meminfo") as f:
            for line in f:
                if line.startswith("MemAvailable:"):
                    return int(line.split()[1]) // 1024
    except (FileNotFoundError, ValueError, IndexError):
        pass
    return None


_PROGRESS_INTERVAL = 10 * 1024 * 1024  # Update DB every 10MB


def _stream_download(
    repo_id: str,
    filename: str,
    local_dir: Path,
    token: str | None = None,
    progress_cb: Any | None = None,
) -> int:
    """Download a single file from HuggingFace via streaming HTTP.

    Streams in 1MB chunks to keep memory usage constant regardless of
    file size. Supports resume via HTTP Range headers.

    Args:
        progress_cb: Optional callable(bytes_delta) called every ~10MB

    Returns:
        Number of bytes downloaded (new bytes, not including resumed portion)
    """
    url = f"{_HF_CDN}/{repo_id}/resolve/main/{filename}"
    dest = local_dir / filename
    dest.parent.mkdir(parents=True, exist_ok=True)

    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    # Resume support: skip already-downloaded bytes
    existing_size = dest.stat().st_size if dest.exists() else 0
    if existing_size > 0:
        headers["Range"] = f"bytes={existing_size}-"

    bytes_downloaded = 0
    since_last_update = 0
    with httpx.stream(
        "GET", url, headers=headers, follow_redirects=True, timeout=300
    ) as resp:
        if resp.status_code == 416:
            # Range not satisfiable — file already complete
            return 0
        resp.raise_for_status()

        mode = "ab" if existing_size > 0 and resp.status_code == 206 else "wb"
        with open(dest, mode) as f:
            for chunk in resp.iter_bytes(chunk_size=_CHUNK_SIZE):
                f.write(chunk)
                bytes_downloaded += len(chunk)
                since_last_update += len(chunk)

                if progress_cb and since_last_update >= _PROGRESS_INTERVAL:
                    progress_cb(since_last_update)
                    since_last_update = 0

    # Flush any remaining progress
    if progress_cb and since_last_update > 0:
        progress_cb(since_last_update)

    return bytes_downloaded


class DownloadManager:
    """Manages model downloads from HuggingFace with resume support and library tracking."""

    def __init__(
        self,
        store: ModelarrStore,
        library_path: Path,
        hf_token: str | None = None,
        storage_manager: StorageManager | None = None,
    ) -> None:
        """Initialize the download manager.

        Args:
            store: ModelarrStore instance for database operations
            library_path: Root path for the local model library
            hf_token: Optional HuggingFace API token for authenticated downloads
            storage_manager: Optional StorageManager for disk limit enforcement
        """
        self.store = store
        self.library_path = Path(library_path)
        self.library_path.mkdir(parents=True, exist_ok=True)
        self.hf_token = hf_token
        self.storage_manager = storage_manager

    def download_model(
        self, model: ModelInfo, watch: Any = None
    ) -> DownloadRecord:
        """Download a model from HuggingFace with resume support.

        Organizes downloads into library_path / author / model_name / and tracks
        download lifecycle through status transitions.

        Args:
            model: ModelInfo object with model metadata
            watch: Optional WatchlistEntry (for future use)

        Returns:
            DownloadRecord with completion status
        """
        # Create or update model record in database
        model_record = self.store.upsert_model(
            repo_id=model.repo_id,
            author=model.author,
            name=model.name,
            format_=model.format,
            quantization=model.quantization,
            size_bytes=model.size_bytes,
        )

        # Create download record with queued status
        download = self.store.create_download(
            model_id=model_record.id,
            status="queued",
            started_at=datetime.now(UTC),
            total_bytes=model.size_bytes,
        )

        try:
            # Check storage limits if StorageManager is configured
            if (
                self.storage_manager is not None
                and not self.storage_manager.check_space(model.size_bytes or 0)
            ):
                # Over limit - try to prune if auto_prune is enabled
                config_auto_prune = self.store.get_config("storage_auto_prune", "false") or "false"
                if config_auto_prune.lower() == "true":
                    self.storage_manager.prune_oldest(model.size_bytes or 0)
                    # Check again after pruning
                    if not self.storage_manager.check_space(model.size_bytes or 0):
                        error_msg = (
                            f"Insufficient storage for {model.repo_id} "
                            f"({model.size_bytes} bytes)"
                        )
                        raise RuntimeError(error_msg)
                else:
                    error_msg = (
                        f"Insufficient storage for {model.repo_id} "
                        f"({model.size_bytes} bytes)"
                    )
                    raise RuntimeError(error_msg)

            # Update to downloading status
            updated = self.store.update_download(
                download.id,
                status="downloading",
            )
            if updated is None:
                raise RuntimeError("Failed to update download status")
            download = updated

            # Create local path: library_path / author / model_name
            local_path = self.library_path / model.author / model.name
            local_path.mkdir(parents=True, exist_ok=True)

            # Download files one at a time for low memory footprint
            min_free_mb = int(
                self.store.get_config("min_free_memory_mb", "200") or "200"
            )
            bytes_so_far = 0
            # Calculate total from file sizes if model.size_bytes is missing
            total_bytes = model.size_bytes or sum(
                f.get("size", 0) for f in model.files if isinstance(f.get("size"), int)
            )
            download_id = download.id
            # Update total_bytes in DB in case it was 0 at creation
            if total_bytes > 0:
                self.store.update_download(download_id, total_bytes=total_bytes)
            store = self.store

            def on_progress(bytes_delta: int) -> None:
                nonlocal bytes_so_far
                bytes_so_far += bytes_delta
                store.update_download(
                    download_id,
                    bytes_downloaded=bytes_so_far,
                    total_bytes=total_bytes,
                )

            for file_info in model.files:
                filename = file_info.get("name", "")
                if not filename:
                    continue

                # Memory guard before each file
                if min_free_mb > 0:
                    avail = _get_available_memory_mb()
                    if avail is not None and avail < min_free_mb:
                        raise RuntimeError(
                            f"Insufficient memory: {avail}MB available, "
                            f"{min_free_mb}MB required "
                            f"(configurable via min_free_memory_mb)"
                        )

                _stream_download(
                    repo_id=model.repo_id,
                    filename=filename,
                    local_dir=local_path,
                    token=self.hf_token,
                    progress_cb=on_progress,
                )

            # Calculate actual downloaded size
            total_size = self._calculate_directory_size(local_path)

            # Update download record to complete
            completed = self.store.update_download(
                download.id,
                status="complete",
                completed_at=datetime.now(UTC),
                bytes_downloaded=total_size,
                total_bytes=total_size,
            )
            if completed is None:
                raise RuntimeError("Failed to complete download")
            download = completed

            # Update model record with local path and download timestamp
            self.store.upsert_model(
                repo_id=model.repo_id,
                author=model.author,
                name=model.name,
                format_=model.format,
                quantization=model.quantization,
                size_bytes=total_size,
                downloaded_at=datetime.now(UTC),
                local_path=str(local_path),
            )

            return download

        except Exception as e:
            # Mark download as failed
            error_msg = str(e)
            failed = self.store.update_download(
                download.id,
                status="failed",
                completed_at=datetime.now(UTC),
                error=error_msg,
            )
            if failed is None:
                raise RuntimeError(f"Failed to mark download as failed: {error_msg}") from e
            return failed

    def get_library_size(self) -> int:
        """Get total size of all downloaded models in the library.

        Returns:
            Total bytes of all downloaded models
        """
        total_bytes = 0
        for model in self.store.list_models():
            if model.local_path and model.size_bytes:
                total_bytes += model.size_bytes
        return total_bytes

    def list_local_models(self) -> list[ModelRecord]:
        """List all downloaded models.

        Returns:
            List of ModelRecord objects that have been downloaded (local_path set)
        """
        return [m for m in self.store.list_models() if m.local_path]

    def delete_local_model(self, repo_id: str) -> bool:
        """Delete a downloaded model from the local library.

        Removes the model directory and clears local_path in the database.

        Args:
            repo_id: HuggingFace repo ID of the model to delete

        Returns:
            True if deleted, False if model not found or not downloaded
        """
        model = self.store.get_model_by_repo(repo_id)
        if not model or not model.local_path:
            return False

        try:
            # Remove the local directory
            local_path = Path(model.local_path)
            if local_path.exists():
                shutil.rmtree(local_path)

            # Clear local_path in database
            self.store.upsert_model(
                repo_id=model.repo_id,
                author=model.author,
                name=model.name,
                format_=model.format,
                quantization=model.quantization,
                size_bytes=model.size_bytes,
                local_path=None,
            )
            return True
        except Exception:
            return False

    @staticmethod
    def _calculate_directory_size(path: Path) -> int:
        """Calculate total size of a directory.

        Args:
            path: Path to the directory

        Returns:
            Total size in bytes
        """
        total = 0
        for item in path.rglob("*"):
            if item.is_file():
                total += item.stat().st_size
        return total
