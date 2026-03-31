"""Tests for Ollama client module."""

from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from modelarr.models import ModelRecord
from modelarr.ollama import OllamaClient


@pytest.fixture
def sample_model(tmp_path: Path) -> ModelRecord:
    """Create a sample model with local GGUF files."""
    model_dir = tmp_path / "models" / "test-author" / "test-model"
    model_dir.mkdir(parents=True)

    # Create a small and large GGUF file
    small_gguf = model_dir / "model-small.gguf"
    small_gguf.write_bytes(b"model data small" * 1000)

    large_gguf = model_dir / "model-large.gguf"
    large_gguf.write_bytes(b"model data large" * 10000)

    return ModelRecord(
        id=1,
        repo_id="test-author/test-model",
        author="test-author",
        name="test-model",
        format="gguf",
        quantization="Q4_K_M",
        size_bytes=1000000,
        last_commit="abc123",
        downloaded_at=datetime.now(),
        local_path=str(model_dir),
    )


@pytest.fixture
def ollama_client() -> OllamaClient:
    """Create an Ollama client for testing."""
    return OllamaClient(host="http://localhost:11434")


def test_generate_modelfile(sample_model: ModelRecord) -> None:
    """Test Modelfile generation finds largest .gguf file."""
    client = OllamaClient()
    modelfile = client.generate_modelfile(sample_model)

    assert "FROM" in modelfile
    assert ".gguf" in modelfile
    # Should reference the largest file
    assert "model-large.gguf" in modelfile


def test_generate_modelfile_no_local_path() -> None:
    """Test Modelfile generation fails without local_path."""
    client = OllamaClient()
    model = ModelRecord(
        id=1,
        repo_id="test/model",
        author="test",
        name="model",
        local_path=None,
    )

    with pytest.raises(ValueError, match="no local_path"):
        client.generate_modelfile(model)


def test_generate_modelfile_path_not_exists() -> None:
    """Test Modelfile generation fails when path doesn't exist."""
    client = OllamaClient()
    model = ModelRecord(
        id=1,
        repo_id="test/model",
        author="test",
        name="model",
        local_path="/nonexistent/path",
    )

    with pytest.raises(ValueError, match="does not exist"):
        client.generate_modelfile(model)


def test_generate_modelfile_no_gguf_files(tmp_path: Path) -> None:
    """Test Modelfile generation fails without .gguf files."""
    client = OllamaClient()
    model_dir = tmp_path / "model"
    model_dir.mkdir()

    # Create non-GGUF file
    (model_dir / "config.json").write_text("{}")

    model = ModelRecord(
        id=1,
        repo_id="test/model",
        author="test",
        name="model",
        local_path=str(model_dir),
    )

    with pytest.raises(ValueError, match="No .gguf"):
        client.generate_modelfile(model)


def test_push_model_success(sample_model: ModelRecord) -> None:
    """Test successful push to Ollama."""
    client = OllamaClient()

    with patch("modelarr.ollama.httpx.Client") as mock_client:
        mock_instance = mock_client.return_value.__enter__.return_value
        mock_instance.post.return_value.status_code = 200

        result = client.push_model(sample_model, model_name="test-model-custom")

    assert result is True


def test_push_model_uses_default_name(sample_model: ModelRecord) -> None:
    """Test push_model uses default name format."""
    client = OllamaClient()

    with patch("modelarr.ollama.httpx.Client") as mock_client:
        mock_instance = mock_client.return_value.__enter__.return_value
        mock_instance.post.return_value.status_code = 200

        result = client.push_model(sample_model)

        # Check that the default name was used
        call_args = mock_instance.post.call_args
        assert "modelarr/test-author-test-model" in str(call_args)

    assert result is True


def test_push_model_graceful_failure(sample_model: ModelRecord) -> None:
    """Test push_model returns False on connection failure."""
    client = OllamaClient(host="http://invalid-host:99999")

    # Should not raise, just return False
    result = client.push_model(sample_model)

    assert result is False


def test_list_models() -> None:
    """Test list_models parses response."""
    client = OllamaClient()

    with patch("modelarr.ollama.httpx.Client") as mock_client:
        mock_instance = mock_client.return_value.__enter__.return_value
        mock_instance.get.return_value.json.return_value = {
            "models": [
                {"name": "model1", "size": 1000},
                {"name": "model2", "size": 2000},
            ]
        }

        result = client.list_models()

    assert len(result) == 2
    assert result[0]["name"] == "model1"


def test_list_models_graceful_failure() -> None:
    """Test list_models returns empty list on failure."""
    client = OllamaClient(host="http://invalid-host:99999")

    result = client.list_models()

    assert result == []


def test_delete_model() -> None:
    """Test delete_model sends correct request."""
    client = OllamaClient()

    with patch("modelarr.ollama.httpx.Client") as mock_client:
        mock_instance = mock_client.return_value.__enter__.return_value
        mock_instance.delete.return_value.status_code = 200

        result = client.delete_model("test-model")

    assert result is True


def test_delete_model_graceful_failure() -> None:
    """Test delete_model returns False on failure."""
    client = OllamaClient(host="http://invalid-host:99999")

    result = client.delete_model("test-model")

    assert result is False


def test_is_connected_success() -> None:
    """Test is_connected returns True when Ollama is reachable."""
    client = OllamaClient()

    with patch("modelarr.ollama.httpx.Client") as mock_client:
        mock_instance = mock_client.return_value.__enter__.return_value
        mock_instance.get.return_value.status_code = 200

        result = client.is_connected()

    assert result is True


def test_is_connected_failure() -> None:
    """Test is_connected returns False when Ollama is unreachable."""
    client = OllamaClient(host="http://invalid-host:99999")

    result = client.is_connected()

    assert result is False
