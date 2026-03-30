"""FastAPI dependency injection for modelarr."""

from pathlib import Path

from fastapi import Depends

from modelarr.db import get_db_path
from modelarr.downloader import DownloadManager
from modelarr.hf_client import HFClient
from modelarr.storage import StorageManager
from modelarr.store import ModelarrStore


def get_store() -> ModelarrStore:
    """Get or create the store instance."""
    db_path = get_db_path()
    return ModelarrStore(db_path)


def get_downloader(  # noqa: B008
    store: ModelarrStore = Depends(get_store),
) -> DownloadManager:
    """Get the download manager."""
    library_path_str = store.get_config("library_path")
    if library_path_str:
        library_path = Path(library_path_str)
    else:
        library_path = Path.home() / ".modelarr" / "library"
    hf_token = store.get_config("huggingface_token")
    return DownloadManager(store=store, library_path=library_path, hf_token=hf_token)


def get_hf_client(  # noqa: B008
    store: ModelarrStore = Depends(get_store),
) -> HFClient:
    """Get the HuggingFace client."""
    token = store.get_config("huggingface_token")
    return HFClient(token=token)


def get_storage_manager(  # noqa: B008
    store: ModelarrStore = Depends(get_store),
) -> StorageManager | None:
    """Get the storage manager if configured."""
    library_path_str = store.get_config("library_path")
    max_storage_gb = store.get_config("max_storage_gb")

    if not library_path_str or not max_storage_gb:
        return None

    library_path = Path(library_path_str)
    max_bytes = int(max_storage_gb) * (1024**3)
    return StorageManager(store=store, library_path=library_path, max_bytes=max_bytes)


def format_bytes(bytes_: int | None) -> str:
    """Format bytes as human-readable string."""
    if bytes_ is None:
        return "Unknown"
    size = float(bytes_)
    for unit in ["B", "KB", "MB", "GB", "TB"]:
        if size < 1024:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size:.2f} PB"
