import logging
import os
from threading import Event
from queue import Queue

from sync_engine.client.monitoring.directory_monitor import DirectoryMonitor
from sync_engine.client.synchronisation.directory_sync_manager import DirectorySyncManager


class SyncEngineClient:
    _logger = logging.getLogger(__name__)

    def __init__(self, target_directory: str) -> None:
        self._target_directory = os.path.abspath(target_directory)
        self._file_events: Queue = Queue()
        self._directory_monitor = DirectoryMonitor(self._target_directory, self._file_events)
        self._directory_sync_manager = DirectorySyncManager(self._target_directory, self._file_events)
        self._stop_event = Event()
        self._running = False

    def start(self) -> bool:
        if self._running:
            self._logger.warning("Sync Engine Client is already running.")
            return False

        self._running = True

        self._logger.info(f"Starting Sync Engine Client. Monitoring directory: {self._target_directory}")

        if not os.path.isdir(self._target_directory):
            self._logger.error(f"Directory not found or not accessible: {self._target_directory}")
            self._running = False
            return False

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

    def wait_for_stop(self) -> None:
        try:
            self._stop_event.wait()
        except KeyboardInterrupt:
            self._logger.info("Keyboard interrupt received. Shutting down...")

    def stop(self) -> None:
        if not self._running:
            return

        self._running = False

        self._directory_monitor.stop()
        self._directory_sync_manager.stop()
        self._logger.info("Sync Engine Client stopped.")
