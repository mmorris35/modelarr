"""Tests for HFClient."""

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from modelarr.hf_client import HFClient


@pytest.fixture
def mock_hf_api():
    """Create a mocked HfApi."""
    with patch("modelarr.hf_client.HfApi") as mock:
        yield mock


@pytest.fixture
def hf_client(mock_hf_api):
    """Create an HFClient with mocked HfApi."""
    return HFClient(token="test-token")


def create_mock_hf_model(
    repo_id: str = "test/model",
    downloads: int = 100,
    siblings: list | None = None,
    last_modified: datetime | None = None,
):
    """Helper to create a mock HuggingFace ModelInfo object."""
    mock_model = MagicMock()
    mock_model.id = repo_id
    mock_model.downloads = downloads
    mock_model.tags = ["language-model", "test"]
    mock_model.last_modified = last_modified or datetime.now()
    mock_model.siblings = siblings or []
    return mock_model


def create_mock_sibling(filename: str, size: int = 1000):
    """Helper to create a mock sibling file object."""
    mock_sibling = MagicMock()
    mock_sibling.rfilename = filename
    mock_sibling.size = size
    return mock_sibling


class TestHFClientSearch:
    """Tests for search_models method."""

    def test_search_models_basic(self, hf_client):
        """Test basic model search."""
        mock_model = create_mock_hf_model(
            "author/model1",
            downloads=500,
            siblings=[create_mock_sibling("model.gguf", size=5000000000)],
        )

        hf_client.api.list_models = MagicMock(return_value=[mock_model])

        results = hf_client.search_models("llama", limit=10)

        assert len(results) == 1
        assert results[0].repo_id == "author/model1"
        assert results[0].author == "author"
        assert results[0].name == "model1"
        assert results[0].format == "GGUF"

    def test_search_models_with_author_filter(self, hf_client):
        """Test search with author filter."""
        mock_model = create_mock_hf_model("specific/model")
        hf_client.api.list_models = MagicMock(return_value=[mock_model])

        hf_client.search_models("test", author="specific")

        hf_client.api.list_models.assert_called_once()
        call_kwargs = hf_client.api.list_models.call_args[1]
        assert call_kwargs["filter"]["author"] == "specific"

    def test_search_models_empty_results(self, hf_client):
        """Test search with no results."""
        hf_client.api.list_models = MagicMock(return_value=[])

        results = hf_client.search_models("nonexistent-model")

        assert results == []

    def test_search_models_sort_parameter(self, hf_client):
        """Test search with different sort options."""
        hf_client.api.list_models = MagicMock(return_value=[])

        hf_client.search_models("query", sort="recent", limit=5)

        call_kwargs = hf_client.api.list_models.call_args[1]
        assert call_kwargs["sort"] == "recent"
        assert call_kwargs["limit"] == 5


class TestHFClientModelInfo:
    """Tests for get_model_info method."""

    def test_get_model_info_basic(self, hf_client):
        """Test getting model info."""
        mock_model = create_mock_hf_model(
            "author/model",
            siblings=[
                create_mock_sibling("model.safetensors", size=3000000000),
                create_mock_sibling("config.json", size=1000),
            ],
        )

        hf_client.api.model_info = MagicMock(return_value=mock_model)

        result = hf_client.get_model_info("author/model")

        assert result.repo_id == "author/model"
        assert result.author == "author"
        assert result.format == "MLX"
        assert result.size_bytes == 3000001000

    def test_get_model_info_with_quantization(self, hf_client):
        """Test format and quantization detection."""
        mock_model = create_mock_hf_model(
            "author/model",
            siblings=[create_mock_sibling("model-q4_k_m.gguf", size=5000000000)],
        )

        hf_client.api.model_info = MagicMock(return_value=mock_model)

        result = hf_client.get_model_info("author/model")

        assert result.format == "GGUF"
        assert result.quantization == "Q4_K_M"


class TestHFClientRepoFiles:
    """Tests for get_repo_files method."""

    def test_get_repo_files_via_siblings(self, hf_client):
        """Test getting repo files via model_info siblings."""
        siblings = [
            create_mock_sibling("model.bin", size=5000000000),
            create_mock_sibling("config.json", size=1000),
        ]
        mock_model = create_mock_hf_model("author/model", siblings=siblings)

        hf_client.api.list_repo_files = MagicMock(side_effect=Exception("Not available"))
        hf_client.api.model_info = MagicMock(return_value=mock_model)

        files = hf_client.get_repo_files("author/model")

        assert len(files) == 2
        assert files[0]["name"] == "model.bin"
        assert files[0]["size"] == 5000000000
        assert files[1]["name"] == "config.json"


class TestHFClientListAuthorModels:
    """Tests for list_author_models method."""

    def test_list_author_models(self, hf_client):
        """Test listing all models by an author."""
        mock_models = [
            create_mock_hf_model("author/model1"),
            create_mock_hf_model("author/model2"),
            create_mock_hf_model("author/model3"),
        ]

        hf_client.api.list_models = MagicMock(return_value=mock_models)

        results = hf_client.list_author_models("author")

        assert len(results) == 3
        assert all(r.author == "author" for r in results)
        assert results[0].name == "model1"
        assert results[2].name == "model3"


class TestFormatDetection:
    """Tests for detect_format static method."""

    def test_detect_format_gguf(self):
        """Test GGUF detection."""
        files = [
            {"name": "model.gguf", "size": 5000000000},
            {"name": "README.md", "size": 1000},
        ]
        result = HFClient.detect_format(files)
        assert result == "GGUF"

    def test_detect_format_mlx(self):
        """Test MLX detection (safetensors + config.json)."""
        files = [
            {"name": "model.safetensors", "size": 3000000000},
            {"name": "config.json", "size": 1000},
        ]
        result = HFClient.detect_format(files)
        assert result == "MLX"

    def test_detect_format_safetensors_alone(self):
        """Test safetensors without config.json."""
        files = [
            {"name": "model.safetensors", "size": 3000000000},
            {"name": "README.md", "size": 1000},
        ]
        result = HFClient.detect_format(files)
        assert result == "safetensors"

    def test_detect_format_pytorch(self):
        """Test PyTorch format detection."""
        files = [
            {"name": "model.bin", "size": 5000000000},
            {"name": "config.json", "size": 1000},
        ]
        result = HFClient.detect_format(files)
        assert result == "PyTorch"

    def test_detect_format_none(self):
        """Test when no format is detected."""
        files = [
            {"name": "README.md", "size": 1000},
            {"name": "LICENSE", "size": 500},
        ]
        result = HFClient.detect_format(files)
        assert result is None

    def test_detect_format_case_insensitive(self):
        """Test that format detection is case-insensitive."""
        files = [
            {"name": "MODEL.GGUF", "size": 5000000000},
        ]
        result = HFClient.detect_format(files)
        assert result == "GGUF"


class TestQuantizationDetection:
    """Tests for detect_quantization static method."""

    def test_detect_quantization_gguf_q4_k_m(self):
        """Test Q4_K_M quantization."""
        result = HFClient.detect_quantization("model-q4_k_m.gguf")
        assert result == "Q4_K_M"

    def test_detect_quantization_gguf_q8_0(self):
        """Test Q8_0 quantization."""
        result = HFClient.detect_quantization("model-q8_0.gguf")
        assert result == "Q8_0"

    def test_detect_quantization_bit_patterns(self):
        """Test bit quantization patterns."""
        assert HFClient.detect_quantization("model-4bit.safetensors") == "4bit"
        assert HFClient.detect_quantization("model-8bit.safetensors") == "8bit"

    def test_detect_quantization_float(self):
        """Test float precision patterns."""
        assert HFClient.detect_quantization("model-fp16.bin") == "fp16"
        assert HFClient.detect_quantization("model-bf16.bin") == "bf16"
        assert HFClient.detect_quantization("model-float16.safetensors") == "float16"

    def test_detect_quantization_none(self):
        """Test when no quantization is detected."""
        result = HFClient.detect_quantization("model-base.gguf")
        assert result is None

    def test_detect_quantization_case_insensitive(self):
        """Test that quantization detection is case-insensitive."""
        result = HFClient.detect_quantization("MODEL-Q4_K_M.GGUF")
        assert result == "Q4_K_M"


class TestSizeCalculation:
    """Tests for calculate_size static method."""

    def test_calculate_size_multiple_files(self):
        """Test total size calculation."""
        files = [
            {"name": "model.gguf", "size": 5000000000},
            {"name": "config.json", "size": 1000},
            {"name": "README.md", "size": 500},
        ]
        result = HFClient.calculate_size(files)
        assert result == 5000001500

    def test_calculate_size_empty_list(self):
        """Test size calculation with empty list."""
        result = HFClient.calculate_size([])
        assert result == 0

    def test_calculate_size_missing_size_key(self):
        """Test that missing size defaults to 0."""
        files = [
            {"name": "model.gguf"},
            {"name": "config.json", "size": 1000},
        ]
        result = HFClient.calculate_size(files)
        assert result == 1000


class TestGetLatestCommit:
    """Tests for get_latest_commit method."""

    def test_get_latest_commit(self, hf_client):
        """Test getting latest commit."""
        last_modified = datetime(2024, 1, 15, 12, 30, 45)
        mock_model = create_mock_hf_model(
            "author/model", last_modified=last_modified
        )

        hf_client.api.model_info = MagicMock(return_value=mock_model)

        result = hf_client.get_latest_commit("author/model")

        assert isinstance(result, str)
        assert "2024-01-15" in result

    def test_get_latest_commit_error(self, hf_client):
        """Test that errors are handled gracefully."""
        hf_client.api.model_info = MagicMock(side_effect=Exception("API error"))

        result = hf_client.get_latest_commit("author/model")

        assert result == ""


class TestIntegration:
    """Integration-style tests combining multiple features."""

    def test_full_workflow(self, hf_client):
        """Test a complete workflow of search and get info."""
        search_result = create_mock_hf_model(
            "mlx-community/Qwen2.5-7B-MLX",
            downloads=1000,
            siblings=[
                create_mock_sibling("model.safetensors", size=7000000000),
                create_mock_sibling("config.json", size=2000),
            ],
        )

        detailed_result = create_mock_hf_model(
            "mlx-community/Qwen2.5-7B-MLX",
            downloads=1000,
            siblings=[
                create_mock_sibling("model.safetensors", size=7000000000),
                create_mock_sibling("config.json", size=2000),
                create_mock_sibling("tokenizer.json", size=500000),
            ],
        )

        hf_client.api.list_models = MagicMock(return_value=[search_result])
        hf_client.api.model_info = MagicMock(return_value=detailed_result)

        # Search
        search_results = hf_client.search_models("Qwen", limit=1)
        assert len(search_results) == 1

        # Get details
        info = hf_client.get_model_info("mlx-community/Qwen2.5-7B-MLX")

        assert info.repo_id == "mlx-community/Qwen2.5-7B-MLX"
        assert info.format == "MLX"
        assert info.size_bytes == 7000502000
        assert info.downloads == 1000
