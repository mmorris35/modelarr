"""Tests for the download manager."""

from pathlib import Path
from unittest.mock import patch

import pytest

from modelarr.downloader import DownloadManager
from modelarr.models import ModelInfo
from modelarr.store import ModelarrStore


@pytest.fixture
def tmp_db(tmp_path):
    """Create a temporary database for testing."""
    db_path = tmp_path / "test.db"
    return ModelarrStore(db_path)


@pytest.fixture
def library_path(tmp_path):
    """Create a temporary library path."""
    return tmp_path / "library"


@pytest.fixture
def downloader(tmp_db, library_path):
    """Create a DownloadManager instance for testing."""
    return DownloadManager(tmp_db, library_path)


@pytest.fixture
def sample_model():
    """Create a sample ModelInfo for testing."""
    return ModelInfo(
        repo_id="test-author/test-model",
        author="test-author",
        name="test-model",
        format="gguf",
        quantization="Q4_K_M",
        size_bytes=5000000000,
        files=[
            {"name": "model.gguf", "size": 4999999000},
            {"name": "config.json", "size": 1000},
        ],
    )


def test_download_manager_init(library_path, tmp_db):
    """Test DownloadManager initialization."""
    downloader = DownloadManager(tmp_db, library_path)
    assert downloader.library_path == library_path
    assert downloader.library_path.exists()


def test_download_manager_with_token(library_path, tmp_db):
    """Test DownloadManager initialization with token."""
    token = "test-token"
    downloader = DownloadManager(tmp_db, library_path, hf_token=token)
    assert downloader.hf_token == token


@patch("modelarr.downloader.hf_hub_download")
def test_download_model_success(mock_hf_download, downloader, sample_model):
    """Test successful model download."""

    def create_file(repo_id, filename, local_dir, token, **kwargs):
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / filename).write_text("fake model data")

    mock_hf_download.side_effect = create_file

    # Download the model
    result = downloader.download_model(sample_model)

    # Verify download record
    assert result.status == "complete"
    assert result.model_id is not None
    assert result.started_at is not None
    assert result.completed_at is not None
    assert result.error is None

    # Verify hf_hub_download was called for each file
    assert mock_hf_download.call_count == len(sample_model.files)
    first_call_kwargs = mock_hf_download.call_args_list[0][1]
    assert first_call_kwargs["repo_id"] == sample_model.repo_id

    # Verify model record was created
    model = downloader.store.get_model_by_repo(sample_model.repo_id)
    assert model is not None
    assert model.local_path is not None
    assert Path(model.local_path).exists()


@patch("modelarr.downloader.hf_hub_download")
def test_download_model_creates_directory_structure(
    mock_hf_download, downloader, sample_model
):
    """Test that download creates correct directory structure."""

    def create_file(repo_id, filename, local_dir, token, **kwargs):
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / filename).write_text("data")

    mock_hf_download.side_effect = create_file

    downloader.download_model(sample_model)

    # Verify directory structure: library_path / author / model_name
    expected_path = downloader.library_path / sample_model.author / sample_model.name
    assert expected_path.exists()
    assert (expected_path / "model.gguf").exists()


@patch("modelarr.downloader.hf_hub_download")
def test_download_model_failure(mock_hf_download, downloader, sample_model):
    """Test handling of download failure."""
    mock_hf_download.side_effect = Exception("Network error")
    sample_model.files = [{"name": "model.gguf", "size": 1000}]

    result = downloader.download_model(sample_model)

    # Verify download record shows failure
    assert result.status == "failed"
    assert "Network error" in (result.error or "")
    assert result.completed_at is not None


@patch("modelarr.downloader.hf_hub_download")
def test_download_model_lifecycle(mock_hf_download, downloader, sample_model):
    """Test download lifecycle transitions."""

    def create_file(repo_id, filename, local_dir, token, **kwargs):
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / filename).write_text("data")

    mock_hf_download.side_effect = create_file

    download_rec = downloader.download_model(sample_model)

    # Verify status transitions
    assert download_rec.status == "complete"

    # Verify we can retrieve the download record
    retrieved = downloader.store.get_download(download_rec.id)
    assert retrieved is not None
    assert retrieved.status == "complete"


@patch("modelarr.downloader.hf_hub_download")
def test_get_library_size(mock_hf_download, downloader, sample_model):
    """Test library size calculation."""

    def create_file(repo_id, filename, local_dir, token, **kwargs):
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / filename).write_bytes(b"x" * 500000)  # 500KB per file

    mock_hf_download.side_effect = create_file

    # Download a model
    downloader.download_model(sample_model)

    # Get library size
    size = downloader.get_library_size()
    assert size > 0


def test_list_local_models_empty(downloader):
    """Test listing local models when library is empty."""
    models = downloader.list_local_models()
    assert models == []


@patch("modelarr.downloader.hf_hub_download")
def test_list_local_models_with_downloads(mock_hf_download, downloader, sample_model):
    """Test listing downloaded models."""

    def create_file(repo_id, filename, local_dir, token, **kwargs):
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / filename).write_text("data")

    mock_hf_download.side_effect = create_file

    # Download a model
    downloader.download_model(sample_model)

    # List local models
    models = downloader.list_local_models()
    assert len(models) == 1
    assert models[0].repo_id == sample_model.repo_id
    assert models[0].local_path is not None


def test_delete_local_model_not_found(downloader):
    """Test deleting a model that doesn't exist."""
    result = downloader.delete_local_model("nonexistent/model")
    assert result is False


@patch("modelarr.downloader.hf_hub_download")
def test_delete_local_model_success(mock_hf_download, downloader, sample_model):
    """Test successful model deletion."""

    def create_file(repo_id, filename, local_dir, token, **kwargs):
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / filename).write_text("data")

    mock_hf_download.side_effect = create_file

    # Download a model
    downloader.download_model(sample_model)

    # Verify it exists
    local_models = downloader.list_local_models()
    assert len(local_models) == 1
    local_path = Path(local_models[0].local_path)
    assert local_path.exists()

    # Delete the model
    result = downloader.delete_local_model(sample_model.repo_id)
    assert result is True

    # Verify the directory is removed
    assert not local_path.exists()

    # Verify local_path is cleared in database
    model = downloader.store.get_model_by_repo(sample_model.repo_id)
    assert model is not None
    assert model.local_path is None


def test_calculate_directory_size(tmp_path):
    """Test directory size calculation."""
    # Create test files
    test_dir = tmp_path / "test"
    test_dir.mkdir()
    (test_dir / "file1.txt").write_bytes(b"x" * 1000)
    (test_dir / "file2.txt").write_bytes(b"y" * 2000)
    subdir = test_dir / "subdir"
    subdir.mkdir()
    (subdir / "file3.txt").write_bytes(b"z" * 500)

    size = DownloadManager._calculate_directory_size(test_dir)
    assert size == 3500


@patch("modelarr.downloader.hf_hub_download")
def test_download_model_token_passed(mock_hf_download, downloader, sample_model):
    """Test that HF token is passed to snapshot_download."""
    token = "test-hf-token"
    downloader_with_token = DownloadManager(
        downloader.store, downloader.library_path, hf_token=token
    )

    def create_file(repo_id, filename, local_dir, token, **kwargs):
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / filename).write_text("data")

    mock_hf_download.side_effect = create_file
    downloader_with_token.download_model(sample_model)

    # Verify token was passed to each hf_hub_download call
    for call in mock_hf_download.call_args_list:
        assert call[1]["token"] == token


@patch("modelarr.downloader.hf_hub_download")
def test_download_model_updates_model_record(mock_hf_download, downloader, sample_model):
    """Test that model record is properly updated after download."""

    def create_file(repo_id, filename, local_dir, token, **kwargs):
        path = Path(local_dir)
        path.mkdir(parents=True, exist_ok=True)
        (path / filename).write_text("data")

    mock_hf_download.side_effect = create_file

    downloader.download_model(sample_model)

    # Retrieve model from database
    model = downloader.store.get_model_by_repo(sample_model.repo_id)

    # Verify all fields were set
    assert model is not None
    assert model.author == sample_model.author
    assert model.name == sample_model.name
    assert model.format == sample_model.format
    assert model.quantization == sample_model.quantization
    assert model.downloaded_at is not None
    assert model.local_path is not None
