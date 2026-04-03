import logging
import os
import time
from queue import Queue

from sync_engine.client.directory_monitoring.directory_monitor import DirectoryMonitor


class SyncEngineClient:
    _logger = logging.getLogger(__name__)

    def __init__(self, target_directory: str) -> None:
        self._target_directory = target_directory
        self._directory_monitor = DirectoryMonitor(target_directory, Queue())

    def start(self) -> None:
        self._logger.info(f"Starting Sync Engine Client. Monitoring directory: {self._target_directory}")

        if not os.path.isdir(self._target_directory):
            self._logger.error(f"Directory not found or not accessible: {self._target_directory}")
            return

        self._directory_monitor.start()
        while True:
            time.sleep(100)

    def stop(self) -> None:
        self._directory_monitor.stop()
        self._logger.info("Sync Engine Client stopped.")
