"""Tests for the WatchlistMatcher."""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from modelarr.matcher import WatchlistMatcher
from modelarr.models import ModelInfo, WatchlistEntry, WatchlistFilters
from modelarr.store import ModelarrStore


@pytest.fixture
def mock_hf_client():
    """Create a mocked HFClient."""
    return MagicMock()


@pytest.fixture
def matcher(mock_hf_client):
    """Create a WatchlistMatcher with mocked HFClient."""
    return WatchlistMatcher(mock_hf_client)


@pytest.fixture
def sample_model():
    """Create a sample ModelInfo for testing."""
    return ModelInfo(
        repo_id="author/model",
        author="author",
        name="model",
        format="GGUF",
        quantization="Q4_K_M",
        size_bytes=5000000000,
    )


@pytest.fixture
def sample_model_2():
    """Create another sample ModelInfo for testing."""
    return ModelInfo(
        repo_id="author/model2",
        author="author",
        name="model2",
        format="safetensors",
        quantization=None,
        size_bytes=3000000000,
    )


class TestCheckWatchModelType:
    """Tests for checking model-type watches."""

    def test_check_watch_model_type(self, matcher, sample_model):
        """Test checking a specific model watch."""
        matcher.hf_client.get_model_info = MagicMock(return_value=sample_model)

        now = datetime.now(UTC)
        entry = WatchlistEntry(
            id=1,
            type="model",
            value="author/model",
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        results = matcher.check_watch(entry)

        assert len(results) == 1
        assert results[0].repo_id == "author/model"
        matcher.hf_client.get_model_info.assert_called_once_with("author/model")

    def test_check_watch_model_type_error(self, matcher):
        """Test that errors are handled gracefully."""
        matcher.hf_client.get_model_info = MagicMock(side_effect=Exception("API error"))

        now = datetime.now(UTC)
        entry = WatchlistEntry(
            id=1,
            type="model",
            value="nonexistent/model",
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        results = matcher.check_watch(entry)

        assert results == []


class TestCheckWatchAuthorType:
    """Tests for checking author-type watches."""

    def test_check_watch_author_type(self, matcher, sample_model, sample_model_2):
        """Test checking an author watch."""
        models = [sample_model, sample_model_2]
        matcher.hf_client.list_author_models = MagicMock(return_value=models)

        now = datetime.now(UTC)
        entry = WatchlistEntry(
            id=1,
            type="author",
            value="author",
            filters=WatchlistFilters(),
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        results = matcher.check_watch(entry)

        assert len(results) == 2
        assert results[0].repo_id == "author/model"
        assert results[1].repo_id == "author/model2"

    def test_check_watch_author_with_format_filter(
        self, matcher, sample_model, sample_model_2
    ):
        """Test author watch with format filter."""
        models = [sample_model, sample_model_2]
        matcher.hf_client.list_author_models = MagicMock(return_value=models)

        now = datetime.now(UTC)
        filters = WatchlistFilters(formats=["GGUF"])
        entry = WatchlistEntry(
            id=1,
            type="author",
            value="author",
            filters=filters,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        results = matcher.check_watch(entry)

        assert len(results) == 1
        assert results[0].format == "GGUF"

    def test_check_watch_author_with_size_filter(
        self, matcher, sample_model, sample_model_2
    ):
        """Test author watch with size filter."""
        models = [sample_model, sample_model_2]
        matcher.hf_client.list_author_models = MagicMock(return_value=models)

        now = datetime.now(UTC)
        filters = WatchlistFilters(max_size_b=4000000000)
        entry = WatchlistEntry(
            id=1,
            type="author",
            value="author",
            filters=filters,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        results = matcher.check_watch(entry)

        assert len(results) == 1
        assert results[0].size_bytes == 3000000000


class TestCheckWatchQueryType:
    """Tests for checking query-type watches."""

    def test_check_watch_query_type(self, matcher, sample_model):
        """Test checking a search query watch."""
        matcher.hf_client.search_models = MagicMock(return_value=[sample_model])

        now = datetime.now(UTC)
        entry = WatchlistEntry(
            id=1,
            type="query",
            value="llama",
            filters=WatchlistFilters(),
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        results = matcher.check_watch(entry)

        assert len(results) == 1
        assert results[0].repo_id == "author/model"
        matcher.hf_client.search_models.assert_called_once_with("llama")

    def test_check_watch_query_with_quantization_filter(
        self, matcher, sample_model, sample_model_2
    ):
        """Test query watch with quantization filter."""
        models = [sample_model, sample_model_2]
        matcher.hf_client.search_models = MagicMock(return_value=models)

        now = datetime.now(UTC)
        filters = WatchlistFilters(quantizations=["Q4_K_M"])
        entry = WatchlistEntry(
            id=1,
            type="query",
            value="model",
            filters=filters,
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        results = matcher.check_watch(entry)

        assert len(results) == 1
        assert results[0].quantization == "Q4_K_M"


class TestCheckWatchFamilyType:
    """Tests for checking family-type watches."""

    def test_check_watch_family_type(self, matcher, sample_model):
        """Test checking a model family watch."""
        matcher.hf_client.search_models = MagicMock(return_value=[sample_model])

        now = datetime.now(UTC)
        entry = WatchlistEntry(
            id=1,
            type="family",
            value="Mistral",
            filters=WatchlistFilters(),
            enabled=True,
            created_at=now,
            updated_at=now,
        )

        results = matcher.check_watch(entry)

        assert len(results) == 1


class TestApplyFilters:
    """Tests for apply_filters static method."""

    def test_apply_filters_no_filters(self, sample_model, sample_model_2):
        """Test that no filters returns all models."""
        models = [sample_model, sample_model_2]
        filters = WatchlistFilters()

        result = WatchlistMatcher.apply_filters(models, filters)

        assert len(result) == 2

    def test_apply_filters_min_size(self, sample_model, sample_model_2):
        """Test minimum size filter."""
        models = [sample_model, sample_model_2]
        filters = WatchlistFilters(min_size_b=4000000000)

        result = WatchlistMatcher.apply_filters(models, filters)

        assert len(result) == 1
        assert result[0].size_bytes >= 4000000000

    def test_apply_filters_max_size(self, sample_model, sample_model_2):
        """Test maximum size filter."""
        models = [sample_model, sample_model_2]
        filters = WatchlistFilters(max_size_b=4000000000)

        result = WatchlistMatcher.apply_filters(models, filters)

        assert len(result) == 1
        assert result[0].size_bytes <= 4000000000

    def test_apply_filters_format(self, sample_model, sample_model_2):
        """Test format filter."""
        models = [sample_model, sample_model_2]
        filters = WatchlistFilters(formats=["safetensors"])

        result = WatchlistMatcher.apply_filters(models, filters)

        assert len(result) == 1
        assert result[0].format == "safetensors"

    def test_apply_filters_format_case_insensitive(self, sample_model):
        """Test that format filter is case-insensitive."""
        models = [sample_model]
        filters = WatchlistFilters(formats=["gguf"])

        result = WatchlistMatcher.apply_filters(models, filters)

        assert len(result) == 1

    def test_apply_filters_quantization(self, sample_model, sample_model_2):
        """Test quantization filter."""
        models = [sample_model, sample_model_2]
        filters = WatchlistFilters(quantizations=["Q4_K_M"])

        result = WatchlistMatcher.apply_filters(models, filters)

        assert len(result) == 1
        assert result[0].quantization == "Q4_K_M"

    def test_apply_filters_multiple_criteria(self, sample_model, sample_model_2):
        """Test filtering with multiple criteria."""
        models = [sample_model, sample_model_2]
        filters = WatchlistFilters(
            formats=["safetensors"],
            max_size_b=4000000000,
        )

        result = WatchlistMatcher.apply_filters(models, filters)

        assert len(result) == 1
        assert result[0].format == "safetensors"
        assert result[0].size_bytes <= 4000000000

    def test_apply_filters_with_none_size(self):
        """Test that None size_bytes is handled correctly."""
        model_no_size = ModelInfo(
            repo_id="test/model",
            author="test",
            name="model",
        )
        models = [model_no_size]
        filters = WatchlistFilters(min_size_b=1000)

        result = WatchlistMatcher.apply_filters(models, filters)

        assert len(result) == 0


class TestFindNewModels:
    """Tests for find_new_models method."""

    def test_find_new_models_no_watches(self, matcher, tmp_path):
        """Test finding new models with no watches."""
        store = ModelarrStore(tmp_path / "test.db")

        results = matcher.find_new_models(store)

        assert results == []

    def test_find_new_models_with_new_match(self, matcher, sample_model, tmp_path):
        """Test finding new models that match and aren't in store."""
        store = ModelarrStore(tmp_path / "test.db")

        # Add a watch
        store.add_watch(
            type_="query",
            value="test",
            filters=WatchlistFilters(),
            enabled=True,
        )

        # Mock the search to return sample_model
        matcher.hf_client.search_models = MagicMock(return_value=[sample_model])

        results = matcher.find_new_models(store)

        assert len(results) == 1
        watch_entry, model_info = results[0]
        assert watch_entry.type == "query"
        assert model_info.repo_id == "author/model"

    def test_find_new_models_skips_existing(self, matcher, sample_model, tmp_path):
        """Test that existing models are not returned."""
        store = ModelarrStore(tmp_path / "test.db")

        # Add the model to the store
        store.upsert_model(
            repo_id=sample_model.repo_id,
            author=sample_model.author,
            name=sample_model.name,
            format_=sample_model.format,
            quantization=sample_model.quantization,
            size_bytes=sample_model.size_bytes,
        )

        # Add a watch that would match it
        store.add_watch(
            type_="model",
            value=sample_model.repo_id,
            enabled=True,
        )

        matcher.hf_client.get_model_info = MagicMock(return_value=sample_model)

        results = matcher.find_new_models(store)

        assert len(results) == 0

    def test_find_new_models_disabled_watches_ignored(
        self, matcher, sample_model, tmp_path
    ):
        """Test that disabled watches are not checked."""
        store = ModelarrStore(tmp_path / "test.db")

        # Add a disabled watch
        store.add_watch(
            type_="query",
            value="test",
            enabled=False,
        )

        matcher.hf_client.search_models = MagicMock(return_value=[sample_model])

        results = matcher.find_new_models(store)

        assert len(results) == 0
        # search_models should not be called because the watch is disabled
        matcher.hf_client.search_models.assert_not_called()

    def test_find_new_models_mixed_new_and_existing(
        self, matcher, sample_model, sample_model_2, tmp_path
    ):
        """Test finding models when some are new and some exist."""
        store = ModelarrStore(tmp_path / "test.db")

        # Add sample_model to the store (so it's known)
        store.upsert_model(
            repo_id=sample_model.repo_id,
            author=sample_model.author,
            name=sample_model.name,
        )

        # Add a watch that returns both models
        store.add_watch(
            type_="query",
            value="test",
            enabled=True,
        )

        matcher.hf_client.search_models = MagicMock(
            return_value=[sample_model, sample_model_2]
        )

        results = matcher.find_new_models(store)

        # Only sample_model_2 should be returned as new
        assert len(results) == 1
        watch_entry, model_info = results[0]
        assert model_info.repo_id == "author/model2"


class TestIntegration:
    """Integration tests for the matcher."""

    def test_full_workflow_author_watch(
        self, matcher, sample_model, sample_model_2, tmp_path
    ):
        """Test a complete workflow with an author watch."""
        store = ModelarrStore(tmp_path / "test.db")

        # Add an author watch with filters
        store.add_watch(
            type_="author",
            value="author",
            filters=WatchlistFilters(formats=["GGUF"]),
            enabled=True,
        )

        # Mock the API to return both models
        matcher.hf_client.list_author_models = MagicMock(
            return_value=[sample_model, sample_model_2]
        )

        # Find new models
        results = matcher.find_new_models(store)

        # Should return only the GGUF model
        assert len(results) == 1
        watch_entry, model_info = results[0]
        assert model_info.format == "GGUF"
        assert model_info.repo_id == "author/model"
