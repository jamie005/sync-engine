import hashlib
import logging
import os
from queue import Empty, Queue
from threading import Event, Thread

from sync_engine.client.monitoring.events import SyncEngineFileSystemEvent


class DirectorySyncManager:
    _EVENT_CONSUMER_THREAD_NAME: str = "directory-sync-manager"
    _EVENT_CONSUME_INTERVAL_SECONDS: float = 0.5

    _logger = logging.getLogger(__name__)

    def __init__(self, target_directory: str, file_system_events: Queue) -> None:
        self._target_directory = target_directory
        self._file_system_events = file_system_events
        self._stop_event = Event()
        self._worker_thread: Thread | None = None
        self._directory_cache: dict[str, str] | None = None

    def start(self) -> bool:
        if self._worker_thread and self._worker_thread.is_alive():
            self._logger.warning("DirectorySyncManager is already running.")
            return False

        if not self._initialise_directory_cache():
            msg = f"Failed to initialise directory cache. Directory not found or inaccessible: {self._target_directory}"
            self._logger.error(msg)
            return False

        self._stop_event.clear()
        self._worker_thread = Thread(target=self._consume_events, daemon=True,
                                     name=self._EVENT_CONSUMER_THREAD_NAME)
        self._worker_thread.start()
        return True

    def _initialise_directory_cache(self) -> bool:
        if not os.path.isdir(self._target_directory):
            return False

        entries: dict[str, str] = {}

        for item_name in os.listdir(self._target_directory):
            relative_path = os.path.relpath(
                os.path.join(self._target_directory, item_name),
                self._target_directory,
            )
            if not os.path.isfile(relative_path):
                continue

            file_hash = self._file_sha256(relative_path)
            if file_hash is not None:
                entries[relative_path] = file_hash

        self._directory_cache = entries
        return True

    def _consume_events(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = self._file_system_events.get(timeout=self._EVENT_CONSUME_INTERVAL_SECONDS)
            except Empty:
                continue

            if not isinstance(event, SyncEngineFileSystemEvent):
                msg = f"Received unexpected event type: {type(event)}. Expected SyncEngineFileSystemEvent."
                self._logger.warning(msg)
                continue

            self._logger.debug(f"Received file system event: {event}")

    def _file_sha256(self, file_path: str) -> str | None:
        try:
            digest = hashlib.sha256()
            with open(file_path, "rb") as file_stream:
                for chunk in iter(lambda: file_stream.read(64 * 1024), b""):
                    digest.update(chunk)
            return digest.hexdigest()
        except FileNotFoundError:
            return None
        except OSError as exc:
            self._logger.warning(f"Unable to hash file for delta cache: {file_path}. Error: {exc}")
            return None

    def stop(self) -> None:
        self._stop_event.set()

        if self._worker_thread:
            self._worker_thread.join(timeout=2)
