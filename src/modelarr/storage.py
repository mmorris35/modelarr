"""Storage management module for modelarr with disk limits and auto-prune."""

from datetime import datetime
from pathlib import Path

from modelarr.models import ModelRecord
from modelarr.store import ModelarrStore


class StorageManager:
    """Manages local storage with disk limits and auto-pruning."""

    def __init__(
        self,
        store: ModelarrStore,
        library_path: Path,
        max_bytes: int | None = None,
    ) -> None:
        """Initialize the storage manager.

        Args:
            store: ModelarrStore instance for database operations
            library_path: Root path for the local model library
            max_bytes: Maximum total library size in bytes, None for unlimited
        """
        self.store = store
        self.library_path = Path(library_path)
        self.max_bytes = max_bytes

    def check_space(self, required_bytes: int) -> bool:
        """Check if adding required_bytes would exceed the limit.

        Args:
            required_bytes: Number of bytes needed for a download

        Returns:
            True if download would fit within limit, False otherwise
        """
        if self.max_bytes is None:
            return True

        current_usage = self._calculate_usage()
        return current_usage + required_bytes <= self.max_bytes

    def prune_oldest(self, required_bytes: int) -> list[ModelRecord]:
        """Delete oldest models until enough space is freed.

        Deletes models in order of downloaded_at (oldest first) until
        enough space is available.

        Args:
            required_bytes: Number of bytes to free up

        Returns:
            List of ModelRecord objects that were deleted
        """
        deleted = []

        # Get all models sorted by download time (oldest first)
        models = self.store.list_models()
        downloaded_models = [m for m in models if m.downloaded_at]
        downloaded_models.sort(key=lambda m: m.downloaded_at or datetime.min)

        freed_bytes = 0
        for model in downloaded_models:
            if freed_bytes >= required_bytes:
                break

            if model.local_path:
                try:
                    # Avoid circular import by importing here
                    from modelarr.downloader import DownloadManager

                    # Try to delete the model
                    downloader = DownloadManager(
                        store=self.store,
                        library_path=self.library_path,
                    )
                    if downloader.delete_local_model(model.repo_id):
                        freed_bytes += model.size_bytes or 0
                        deleted.append(model)
                except Exception:
                    # Skip models that fail to delete
                    continue

        return deleted

    def get_usage(self) -> dict:
        """Get current storage usage statistics.

        Returns:
            Dictionary with keys:
            - total_bytes: Total size of all downloaded models
            - model_count: Number of downloaded models
            - max_bytes: Maximum limit (None if unlimited)
            - free_bytes: Bytes available before hitting limit (None if unlimited)
        """
        models = self.store.list_models()
        downloaded_models = [m for m in models if m.local_path]

        total_bytes = sum(m.size_bytes or 0 for m in downloaded_models)

        result = {
            "total_bytes": total_bytes,
            "model_count": len(downloaded_models),
            "max_bytes": self.max_bytes,
        }

        if self.max_bytes is not None:
            result["free_bytes"] = max(0, self.max_bytes - total_bytes)
        else:
            result["free_bytes"] = None

        return result

    def _calculate_usage(self) -> int:
        """Calculate total size of all downloaded models.

        Returns:
            Total bytes of all downloaded models
        """
        models = self.store.list_models()
        return sum(m.size_bytes or 0 for m in models if m.local_path)
