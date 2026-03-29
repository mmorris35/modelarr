"""Tests for the monitor module."""

from unittest.mock import MagicMock, patch

import pytest

from modelarr.downloader import DownloadManager
from modelarr.matcher import WatchlistMatcher
from modelarr.models import DownloadRecord, ModelInfo, WatchlistEntry, WatchlistFilters
from modelarr.monitor import ModelarrMonitor
from modelarr.notifier import TelegramNotifier
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
def matcher():
    """Create a mocked WatchlistMatcher."""
    return MagicMock(spec=WatchlistMatcher)


@pytest.fixture
def downloader(tmp_db, library_path):
    """Create a DownloadManager."""
    return DownloadManager(tmp_db, library_path)


@pytest.fixture
def mock_notifier():
    """Create a mock TelegramNotifier."""
    notifier = MagicMock(spec=TelegramNotifier)
    notifier.notify.return_value = True
    notifier.notify_error.return_value = True
    return notifier


@pytest.fixture
def monitor(tmp_db, matcher, downloader, mock_notifier):
    """Create a ModelarrMonitor."""
    return ModelarrMonitor(
        tmp_db, matcher, downloader, mock_notifier, interval_minutes=5
    )


def test_monitor_init(tmp_db, matcher, downloader):
    """Test ModelarrMonitor initialization."""
    monitor = ModelarrMonitor(tmp_db, matcher, downloader, interval_minutes=10)
    assert monitor.store == tmp_db
    assert monitor.matcher == matcher
    assert monitor.downloader == downloader
    assert monitor.interval_minutes == 10
    assert monitor.scheduler is None


def test_monitor_init_with_notifier(tmp_db, matcher, downloader, mock_notifier):
    """Test ModelarrMonitor initialization with notifier."""
    monitor = ModelarrMonitor(tmp_db, matcher, downloader, mock_notifier)
    assert monitor.notifier == mock_notifier


def test_check_and_download_no_matches(monitor, matcher):
    """Test check_and_download when no new models found."""
    matcher.find_new_models.return_value = []

    result = monitor.check_and_download()

    assert result == []
    matcher.find_new_models.assert_called_once()


def test_check_and_download_with_matches(monitor, matcher, downloader, mock_notifier):
    """Test check_and_download with new models."""
    watch = WatchlistEntry(
        id=1,
        type="query",
        value="test",
        filters=WatchlistFilters(),
        enabled=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    model_info = ModelInfo(
        repo_id="test-author/test-model",
        author="test-author",
        name="test-model",
        format="gguf",
        quantization="Q4_K_M",
        size_bytes=5000000000,
    )

    download_record = DownloadRecord(
        id=1,
        model_id=1,
        status="complete",
        started_at=MagicMock(),
        completed_at=MagicMock(),
        bytes_downloaded=5000000000,
        total_bytes=5000000000,
        error=None,
    )

    matcher.find_new_models.return_value = [(watch, model_info)]

    with patch.object(downloader, "download_model", return_value=download_record):
        result = monitor.check_and_download()

        assert len(result) == 1
        assert result[0] == (watch, model_info)
        mock_notifier.notify.assert_called_once()


def test_check_and_download_handles_download_failure(monitor, matcher, downloader, mock_notifier):
    """Test check_and_download handles download errors gracefully."""
    watch = WatchlistEntry(
        id=1,
        type="query",
        value="test",
        filters=WatchlistFilters(),
        enabled=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    model_info = ModelInfo(
        repo_id="test-author/test-model",
        author="test-author",
        name="test-model",
        format="gguf",
        quantization="Q4_K_M",
        size_bytes=5000000000,
    )

    matcher.find_new_models.return_value = [(watch, model_info)]

    with patch.object(downloader, "download_model", side_effect=Exception("Download failed")):
        result = monitor.check_and_download()

        assert result == []
        mock_notifier.notify_error.assert_called()


def test_check_and_download_no_notifier(tmp_db, matcher, downloader):
    """Test check_and_download without notifier."""
    monitor = ModelarrMonitor(tmp_db, matcher, downloader, notifier=None)

    watch = WatchlistEntry(
        id=1,
        type="query",
        value="test",
        filters=WatchlistFilters(),
        enabled=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    model_info = ModelInfo(
        repo_id="test-author/test-model",
        author="test-author",
        name="test-model",
        format="gguf",
        quantization="Q4_K_M",
        size_bytes=5000000000,
    )

    download_record = DownloadRecord(
        id=1,
        model_id=1,
        status="complete",
        started_at=MagicMock(),
        completed_at=MagicMock(),
        bytes_downloaded=5000000000,
        total_bytes=5000000000,
        error=None,
    )

    matcher.find_new_models.return_value = [(watch, model_info)]

    with patch.object(downloader, "download_model", return_value=download_record):
        result = monitor.check_and_download()

        assert len(result) == 1


def test_start_scheduler(monitor):
    """Test starting the scheduler."""
    monitor.start()

    assert monitor.scheduler is not None
    assert monitor.scheduler.running

    monitor.stop()


def test_stop_scheduler(monitor):
    """Test stopping the scheduler."""
    monitor.start()
    assert monitor.scheduler is not None
    assert monitor.scheduler.running

    monitor.stop()
    assert monitor.scheduler is None


def test_stop_without_start(monitor):
    """Test stopping scheduler when not started."""
    monitor.stop()
    assert monitor.scheduler is None


def test_run_once(monitor, matcher, downloader):
    """Test run_once method."""
    watch = WatchlistEntry(
        id=1,
        type="query",
        value="test",
        filters=WatchlistFilters(),
        enabled=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    model_info = ModelInfo(
        repo_id="test-author/test-model",
        author="test-author",
        name="test-model",
        format="gguf",
        quantization="Q4_K_M",
        size_bytes=5000000000,
    )

    download_record = DownloadRecord(
        id=1,
        model_id=1,
        status="complete",
        started_at=MagicMock(),
        completed_at=MagicMock(),
        bytes_downloaded=5000000000,
        total_bytes=5000000000,
        error=None,
    )

    matcher.find_new_models.return_value = [(watch, model_info)]

    with patch.object(downloader, "download_model", return_value=download_record):
        result = monitor.run_once()

        assert len(result) == 1
        assert result[0] == (watch, model_info)


def test_monitor_failed_matches(monitor, matcher):
    """Test check_and_download when matcher fails."""
    matcher.find_new_models.side_effect = Exception("Matcher error")

    result = monitor.check_and_download()

    assert result == []


def test_start_idempotent(monitor):
    """Test that calling start multiple times is safe."""
    monitor.start()
    scheduler1 = monitor.scheduler

    monitor.start()
    scheduler2 = monitor.scheduler

    # Same scheduler instance
    assert scheduler1 is scheduler2

    monitor.stop()


def test_monitor_interval_configuration(tmp_db, matcher, downloader):
    """Test monitor interval configuration."""
    interval = 30
    monitor = ModelarrMonitor(tmp_db, matcher, downloader, interval_minutes=interval)

    assert monitor.interval_minutes == interval

    monitor.start()
    assert monitor.scheduler is not None

    # Verify the job has the correct interval
    jobs = monitor.scheduler.get_jobs()
    assert len(jobs) > 0
    assert jobs[0].trigger.interval.total_seconds() == interval * 60

    monitor.stop()


def test_check_and_download_only_completes_notification(
    monitor, matcher, downloader, mock_notifier
):
    """Test that failed downloads don't send success notifications."""
    watch = WatchlistEntry(
        id=1,
        type="query",
        value="test",
        filters=WatchlistFilters(),
        enabled=True,
        created_at=MagicMock(),
        updated_at=MagicMock(),
    )

    model_info = ModelInfo(
        repo_id="test-author/test-model",
        author="test-author",
        name="test-model",
        format="gguf",
        quantization="Q4_K_M",
        size_bytes=5000000000,
    )

    # Failed download
    download_record = DownloadRecord(
        id=1,
        model_id=1,
        status="failed",
        started_at=MagicMock(),
        completed_at=MagicMock(),
        bytes_downloaded=0,
        total_bytes=5000000000,
        error="Download error",
    )

    matcher.find_new_models.return_value = [(watch, model_info)]

    with patch.object(downloader, "download_model", return_value=download_record):
        monitor.check_and_download()

        # notify should NOT be called for failed downloads
        mock_notifier.notify.assert_not_called()
