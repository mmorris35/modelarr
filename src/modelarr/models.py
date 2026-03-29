"""Pydantic models for modelarr entities."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class WatchlistFilters(BaseModel):
    """Filters for watchlist entries."""

    min_size_b: int | None = None
    max_size_b: int | None = None
    formats: list[str] | None = None
    quantizations: list[str] | None = None


class WatchlistEntry(BaseModel):
    """A watchlist entry for monitoring models."""

    id: int
    type: Literal["model", "author", "query", "family"]
    value: str
    filters: WatchlistFilters = Field(default_factory=WatchlistFilters)
    enabled: bool = True
    created_at: datetime
    updated_at: datetime


class ModelRecord(BaseModel):
    """A record of a known model in the database."""

    id: int
    repo_id: str
    author: str
    name: str
    format: str | None = None
    quantization: str | None = None
    size_bytes: int | None = None
    last_commit: str | None = None
    downloaded_at: datetime | None = None
    local_path: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DownloadRecord(BaseModel):
    """A record of a download in progress or completed."""

    id: int
    model_id: int
    status: Literal["queued", "downloading", "complete", "failed", "paused"]
    started_at: datetime | None = None
    completed_at: datetime | None = None
    bytes_downloaded: int | None = None
    total_bytes: int | None = None
    error: str | None = None


class ModelInfo(BaseModel):
    """Information about a model from HuggingFace API."""

    repo_id: str
    author: str
    name: str
    files: list[dict[str, Any]] = Field(default_factory=list)
    last_modified: datetime | None = None
    tags: list[str] = Field(default_factory=list)
    downloads: int | None = None
    format: str | None = None
    quantization: str | None = None
    size_bytes: int | None = None
