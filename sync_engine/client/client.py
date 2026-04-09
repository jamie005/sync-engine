import logging
from pathlib import Path
from threading import Event
from queue import Queue
from typing import Protocol

from sync_engine.client.monitoring.directory_monitor import DirectoryMonitor
from sync_engine.client.monitoring.events import SyncEngineFileSystemEvent
from sync_engine.client.synchronisation.api_client import HttpSyncApiClient
from sync_engine.client.synchronisation.directory_sync_manager import DirectorySyncManager


class _StartStopComponent(Protocol):
    def start(self) -> bool:
        ...

    def stop(self) -> None:
        ...


class SyncEngineClient:
    """Coordinates local monitoring and remote file synchronization."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        target_directory: Path,
        server_host: str = "127.0.0.1",
        server_port: int = 5000,
        file_events: Queue[SyncEngineFileSystemEvent] | None = None,
        directory_monitor: _StartStopComponent | None = None,
        directory_sync_manager: _StartStopComponent | None = None,
        stop_event: Event | None = None,
        api_client: HttpSyncApiClient | None = None,
    ) -> None:

        self._target_directory = target_directory.expanduser().resolve()
        self._file_events = file_events or Queue()

        resolved_api_client = api_client or HttpSyncApiClient(server_host, server_port)
        self._directory_monitor = directory_monitor or DirectoryMonitor(self._target_directory, self._file_events)
        self._directory_sync_manager = directory_sync_manager or DirectorySyncManager(
            self._target_directory,
            self._file_events,
            resolved_api_client,
        )
        self._stop_event = stop_event or Event()
        self._running = False

    @property
    def is_running(self) -> bool:
        """Return whether the client is currently running."""
        return self._running

    def start(self) -> bool:
        """Start synchronization components if the target directory is valid."""
        if self._running:
            self._logger.warning("Sync Engine Client is already running.")
            return False

        self._running = True

        self._logger.info(f"Starting Sync Engine Client. Monitoring directory: {self._target_directory}")

        if not self._target_directory.is_dir():
            self._logger.error(f"Directory not found or not accessible: {self._target_directory}")
            self._running = False
            return False

        self._stop_event.clear()

        sync_manager_started = self._directory_sync_manager.start()
        if not sync_manager_started:
            self._running = False
            return False

        monitor_started = self._directory_monitor.start()
        if not monitor_started:
            self._directory_sync_manager.stop()
            self._running = False
            return False

        return True

    def wait_for_stop(self, timeout: float | None = None) -> bool:
        """Wait for a stop signal or until timeout expires."""
        try:
            return self._stop_event.wait(timeout=timeout)
        except KeyboardInterrupt:
            self._logger.info("Keyboard interrupt received. Shutting down...")
            return True

    def stop(self) -> None:
        """Stop synchronization components and signal shutdown."""
        if not self._running:
            return

        self._running = False
        self._stop_event.set()

        self._directory_monitor.stop()
        self._directory_sync_manager.stop()
        self._logger.info("Sync Engine Client stopped.")
