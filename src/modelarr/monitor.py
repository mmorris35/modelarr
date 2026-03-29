"""Polling monitor for modelarr with APScheduler integration."""

import contextlib
import os
import signal
from pathlib import Path

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from modelarr.downloader import DownloadManager
from modelarr.matcher import WatchlistMatcher
from modelarr.models import ModelInfo, WatchlistEntry
from modelarr.notifier import TelegramNotifier
from modelarr.store import ModelarrStore


class ModelarrMonitor:
    """Monitors watchlist for new models and downloads them."""

    # PID file location
    PID_FILE = Path.home() / ".config" / "modelarr" / "monitor.pid"

    def __init__(
        self,
        store: ModelarrStore,
        matcher: WatchlistMatcher,
        downloader: DownloadManager,
        notifier: TelegramNotifier | None = None,
        interval_minutes: int = 60,
    ) -> None:
        """Initialize the monitor.

        Args:
            store: ModelarrStore instance
            matcher: WatchlistMatcher instance
            downloader: DownloadManager instance
            notifier: Optional TelegramNotifier for notifications
            interval_minutes: Minutes between polls (default: 60)
        """
        self.store = store
        self.matcher = matcher
        self.downloader = downloader
        self.notifier = notifier
        self.interval_minutes = interval_minutes
        self.scheduler: BackgroundScheduler | None = None

    @staticmethod
    def _write_pid() -> None:
        """Write current process ID to PID file."""
        ModelarrMonitor.PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        ModelarrMonitor.PID_FILE.write_text(str(os.getpid()))

    @staticmethod
    def _read_pid() -> int | None:
        """Read process ID from PID file."""
        if ModelarrMonitor.PID_FILE.exists():
            try:
                return int(ModelarrMonitor.PID_FILE.read_text().strip())
            except (ValueError, OSError):
                return None
        return None

    @staticmethod
    def _pid_is_alive(pid: int) -> bool:
        """Check if a process with given PID is still running."""
        try:
            os.kill(pid, 0)
            return True
        except (ProcessLookupError, OSError):
            return False

    @staticmethod
    def _delete_pid_file() -> None:
        """Delete the PID file."""
        if ModelarrMonitor.PID_FILE.exists():
            with contextlib.suppress(OSError):
                ModelarrMonitor.PID_FILE.unlink()

    def check_and_download(
        self,
    ) -> list[tuple[WatchlistEntry, ModelInfo]]:
        """Run a single poll cycle.

        Finds new models, downloads them, and sends notifications.

        Returns:
            List of (WatchlistEntry, ModelInfo) tuples for downloaded models
        """
        downloaded = []

        try:
            # Find new models from all enabled watches
            new_matches = self.matcher.find_new_models(self.store)

            for watch, model_info in new_matches:
                try:
                    # Download the model
                    download_record = self.downloader.download_model(model_info, watch)

                    # Send notification if successful and notifier configured
                    if (
                        download_record.status == "complete"
                        and self.notifier is not None
                    ):
                        self.notifier.notify(watch, model_info, download_record)

                    downloaded.append((watch, model_info))

                except Exception as e:
                    # Log error and notify if notifier configured
                    error_msg = f"Failed to download {model_info.repo_id}: {str(e)}"
                    if self.notifier is not None:
                        self.notifier.notify_error(error_msg)

            return downloaded

        except Exception as e:
            # Log error and notify
            error_msg = f"Monitor cycle failed: {str(e)}"
            if self.notifier is not None:
                self.notifier.notify_error(error_msg)
            return []

    def start(self) -> None:
        """Start the background monitoring scheduler.

        Creates an APScheduler job running at the configured interval.
        Writes PID file for later shutdown via stop() command.
        """
        if self.scheduler is not None and self.scheduler.running:
            return

        # Write PID file
        self._write_pid()

        self.scheduler = BackgroundScheduler()
        self.scheduler.add_job(
            self.check_and_download,
            trigger=IntervalTrigger(minutes=self.interval_minutes),
        )
        self.scheduler.start()

    def stop(self) -> None:
        """Stop the monitoring scheduler."""
        if self.scheduler is not None and self.scheduler.running:
            self.scheduler.shutdown()
            self.scheduler = None
        self._delete_pid_file()

    @staticmethod
    def stop_by_pid() -> bool:
        """Stop monitor by reading PID from file and sending SIGTERM.

        Returns:
            True if monitor was stopped, False if no running monitor found
        """
        pid = ModelarrMonitor._read_pid()
        if pid is None:
            return False

        if not ModelarrMonitor._pid_is_alive(pid):
            ModelarrMonitor._delete_pid_file()
            return False

        try:
            os.kill(pid, signal.SIGTERM)
            ModelarrMonitor._delete_pid_file()
            return True
        except (ProcessLookupError, OSError):
            ModelarrMonitor._delete_pid_file()
            return False

    @staticmethod
    def is_running() -> bool:
        """Check if monitor process is running.

        Returns:
            True if monitor is running, False otherwise
        """
        pid = ModelarrMonitor._read_pid()
        if pid is None:
            return False

        is_alive = ModelarrMonitor._pid_is_alive(pid)
        if not is_alive:
            ModelarrMonitor._delete_pid_file()
        return is_alive

    def run_once(self) -> list[tuple[WatchlistEntry, ModelInfo]]:
        """Run a single poll cycle for CLI use.

        Returns:
            List of (WatchlistEntry, ModelInfo) tuples for downloaded models
        """
        return self.check_and_download()
