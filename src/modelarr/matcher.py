"""Watchlist matching engine for finding new models."""

from modelarr.hf_client import HFClient
from modelarr.models import ModelInfo, WatchlistEntry, WatchlistFilters
from modelarr.store import ModelarrStore


class WatchlistMatcher:
    """Matches watchlist entries against new models from HuggingFace."""

    def __init__(self, hf_client: HFClient) -> None:
        """Initialize the watchlist matcher.

        Args:
            hf_client: HFClient instance for querying HuggingFace
        """
        self.hf_client = hf_client

    def check_watch(self, entry: WatchlistEntry) -> list[ModelInfo]:
        """Check a watchlist entry and return matching models.

        Dispatches by type:
        - model: check if repo has new commit since last seen
        - author: list author's models, filter by WatchlistFilters, return unseen
        - query: search HF, filter by WatchlistFilters, return unseen
        - family: search by family name, filter by size/format/quant, return unseen

        Args:
            entry: WatchlistEntry to check

        Returns:
            List of matching ModelInfo objects
        """
        if entry.type == "model":
            return self._check_model_watch(entry)
        elif entry.type == "author":
            return self._check_author_watch(entry)
        elif entry.type == "query":
            return self._check_query_watch(entry)
        elif entry.type == "family":
            return self._check_family_watch(entry)
        return []

    def _check_model_watch(self, entry: WatchlistEntry) -> list[ModelInfo]:
        """Check a specific model watch for new commits.

        Args:
            entry: WatchlistEntry of type 'model' with repo_id as value

        Returns:
            ModelInfo if new commits exist, else empty list
        """
        try:
            model_info = self.hf_client.get_model_info(entry.value)
            return [model_info]
        except Exception:
            return []

    def _check_author_watch(self, entry: WatchlistEntry) -> list[ModelInfo]:
        """Check an author watch for new models.

        Args:
            entry: WatchlistEntry of type 'author' with author name as value

        Returns:
            List of filtered ModelInfo objects from the author
        """
        try:
            models = self.hf_client.list_author_models(entry.value)
            return self.apply_filters(models, entry.filters)
        except Exception:
            return []

    def _check_query_watch(self, entry: WatchlistEntry) -> list[ModelInfo]:
        """Check a search query watch.

        Args:
            entry: WatchlistEntry of type 'query' with search query as value

        Returns:
            List of filtered ModelInfo objects matching the query
        """
        try:
            models = self.hf_client.search_models(entry.value)
            return self.apply_filters(models, entry.filters)
        except Exception:
            return []

    def _check_family_watch(self, entry: WatchlistEntry) -> list[ModelInfo]:
        """Check a model family watch.

        Args:
            entry: WatchlistEntry of type 'family' with family name as value

        Returns:
            List of filtered ModelInfo objects from the family
        """
        # Family is treated as a search query
        try:
            models = self.hf_client.search_models(entry.value)
            return self.apply_filters(models, entry.filters)
        except Exception:
            return []

    @staticmethod
    def apply_filters(
        models: list[ModelInfo], filters: WatchlistFilters
    ) -> list[ModelInfo]:
        """Filter models based on WatchlistFilters.

        Args:
            models: List of ModelInfo objects to filter
            filters: WatchlistFilters with size/format/quantization constraints

        Returns:
            Filtered list of ModelInfo objects
        """
        filtered = models

        # Filter by size
        if filters.min_size_b is not None:
            filtered = [
                m for m in filtered
                if m.size_bytes is not None and m.size_bytes >= filters.min_size_b
            ]

        if filters.max_size_b is not None:
            filtered = [
                m for m in filtered
                if m.size_bytes is not None and m.size_bytes <= filters.max_size_b
            ]

        # Filter by format
        if filters.formats:
            formats_lower = [f.lower() for f in filters.formats]
            filtered = [
                m for m in filtered
                if m.format and m.format.lower() in formats_lower
            ]

        # Filter by quantization
        if filters.quantizations:
            quantizations_lower = [q.lower() for q in filters.quantizations]
            filtered = [
                m for m in filtered
                if m.quantization and m.quantization.lower() in quantizations_lower
            ]

        return filtered

    def find_new_models(
        self, store: ModelarrStore, backfill: bool = False
    ) -> list[tuple[WatchlistEntry, ModelInfo]]:
        """Find models matching enabled watchlist entries.

        Checks all enabled watches in the store and returns matches.
        By default, only returns models not already in the database.
        With backfill=True, returns all matches that aren't already
        downloaded (have no local_path), useful for initial setup.

        Args:
            store: ModelarrStore instance for checking known models
            backfill: If True, include known-but-not-downloaded models

        Returns:
            List of (WatchlistEntry, ModelInfo) tuples for matches
        """
        results = []
        watches = store.list_watches(enabled_only=True)

        for watch in watches:
            matches = self.check_watch(watch)
            for model_info in matches:
                existing = store.get_model_by_repo(model_info.repo_id)
                if existing is None:
                    # Brand new model — always include
                    results.append((watch, model_info))
                elif backfill and not existing.local_path:
                    # Known but not downloaded — include in backfill
                    results.append((watch, model_info))

        return results
