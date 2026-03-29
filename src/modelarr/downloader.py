"""Download manager for modelarr with resume support."""

import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from huggingface_hub import snapshot_download

from modelarr.models import DownloadRecord, ModelInfo, ModelRecord
from modelarr.storage import StorageManager
from modelarr.store import ModelarrStore


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
                config_auto_prune = self.store.get_config("storage_auto_prune", "false")
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
            download = self.store.update_download(
                download.id,
                status="downloading",
            )
            if download is None:
                raise RuntimeError("Failed to update download status")

            # Create local path: library_path / author / model_name
            local_path = self.library_path / model.author / model.name
            local_path.mkdir(parents=True, exist_ok=True)

            # Download with resume support
            snapshot_download(
                repo_id=model.repo_id,
                local_dir=str(local_path),
                resume_download=True,
                token=self.hf_token,
            )

            # Calculate actual downloaded size
            total_size = self._calculate_directory_size(local_path)

            # Update download record to complete
            download = self.store.update_download(
                download.id,
                status="complete",
                completed_at=datetime.now(UTC),
                bytes_downloaded=total_size,
                total_bytes=total_size,
            )

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

            if download is None:
                raise RuntimeError("Failed to complete download")

            return download

        except Exception as e:
            # Mark download as failed
            error_msg = str(e)
            download = self.store.update_download(
                download.id,
                status="failed",
                completed_at=datetime.now(UTC),
                error=error_msg,
            )
            if download is None:
                raise RuntimeError(f"Failed to mark download as failed: {error_msg}") from e
            return download

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
