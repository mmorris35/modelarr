"""Tests for Ollama CLI commands."""

from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from modelarr.cli import app
from modelarr.models import ModelRecord

runner = CliRunner()


@pytest.fixture
def sample_model(tmp_path: Path) -> ModelRecord:
    """Create a sample GGUF model."""
    model_dir = tmp_path / "models" / "test-author" / "test-model"
    model_dir.mkdir(parents=True)

    large_gguf = model_dir / "model.gguf"
    large_gguf.write_bytes(b"model data" * 10000)

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


def test_ollama_push_help() -> None:
    """Test ollama push help."""
    result = runner.invoke(app, ["ollama", "push", "--help"])
    assert result.exit_code == 0
    assert "Push a downloaded GGUF model to Ollama" in result.stdout


def test_ollama_list_help() -> None:
    """Test ollama list help."""
    result = runner.invoke(app, ["ollama", "list", "--help"])
    assert result.exit_code == 0
    assert "Show models currently loaded in Ollama" in result.stdout


def test_ollama_status_help() -> None:
    """Test ollama status help."""
    result = runner.invoke(app, ["ollama", "status", "--help"])
    assert result.exit_code == 0
    assert "Show Ollama connection status" in result.stdout


def test_ollama_push_not_configured(tmp_path: Path) -> None:
    """Test ollama push when model not found."""
    result = runner.invoke(app, ["ollama", "push", "nonexistent/model"])
    assert result.exit_code == 1
    assert "not found" in result.stdout


def test_ollama_status_not_configured() -> None:
    """Test ollama status with default host."""
    with patch("modelarr.cli._get_store") as mock_store_fn:
        mock_store = MagicMock()
        mock_store.get_config.return_value = None
        mock_store_fn.return_value = mock_store

        with patch("modelarr.cli.OllamaClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = False
            mock_client_cls.return_value = mock_client

            result = runner.invoke(app, ["ollama", "status"])
            assert result.exit_code == 1
            assert "Cannot reach" in result.stdout


def test_ollama_list_no_models() -> None:
    """Test ollama list when no models."""
    with patch("modelarr.cli._get_store") as mock_store_fn:
        mock_store = MagicMock()
        mock_store.get_config.return_value = "http://localhost:11434"
        mock_store_fn.return_value = mock_store

        with patch("modelarr.cli.OllamaClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.list_models.return_value = []
            mock_client_cls.return_value = mock_client

            result = runner.invoke(app, ["ollama", "list"])
            assert result.exit_code == 0
            assert "No models loaded in Ollama" in result.stdout


def test_ollama_list_with_models() -> None:
    """Test ollama list with models."""
    with patch("modelarr.cli._get_store") as mock_store_fn:
        mock_store = MagicMock()
        mock_store.get_config.return_value = "http://localhost:11434"
        mock_store_fn.return_value = mock_store

        with patch("modelarr.cli.OllamaClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.list_models.return_value = [
                {"name": "model1", "size": 1000000, "modified_at": "2024-01-01"},
                {"name": "model2", "size": 2000000, "modified_at": "2024-01-02"},
            ]
            mock_client_cls.return_value = mock_client

            result = runner.invoke(app, ["ollama", "list"])
            assert result.exit_code == 0
            assert "model1" in result.stdout
            assert "model2" in result.stdout


def test_ollama_status_connected() -> None:
    """Test ollama status when connected."""
    with patch("modelarr.cli._get_store") as mock_store_fn:
        mock_store = MagicMock()
        mock_store.get_config.return_value = "http://localhost:11434"
        mock_store_fn.return_value = mock_store

        with patch("modelarr.cli.OllamaClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = True
            mock_client.list_models.return_value = [{"name": "model1"}]
            mock_client_cls.return_value = mock_client

            result = runner.invoke(app, ["ollama", "status"])
            assert result.exit_code == 0
            assert "Connected" in result.stdout
            assert "Models loaded: 1" in result.stdout


def test_ollama_status_disconnected() -> None:
    """Test ollama status when disconnected."""
    with patch("modelarr.cli._get_store") as mock_store_fn:
        mock_store = MagicMock()
        mock_store.get_config.return_value = "http://invalid:99999"
        mock_store_fn.return_value = mock_store

        with patch("modelarr.cli.OllamaClient") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.is_connected.return_value = False
            mock_client_cls.return_value = mock_client

            result = runner.invoke(app, ["ollama", "status"])
            assert result.exit_code == 1
            assert "Cannot reach" in result.stdout
