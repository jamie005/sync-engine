import hashlib
import logging
import os
from queue import Empty, Queue
from threading import Event, Thread

from pydantic import BaseModel, Field

from sync_engine.client.monitoring.events import FileSystemEventType, SyncEngineFileSystemEvent


class DirectoryCache(BaseModel):
    entries: dict[str, str] = Field(default_factory=dict)


class DirectorySyncManager:
    _EVENT_CONSUMER_THREAD_NAME: str = "directory-sync-manager"
    _EVENT_CONSUME_INTERVAL_SECONDS: float = 0.5

    _logger = logging.getLogger(__name__)

    def __init__(self, target_directory: str, file_system_events: Queue[SyncEngineFileSystemEvent]) -> None:
        self._target_directory = target_directory
        self._file_system_events = file_system_events
        self._stop_event = Event()
        self._worker_thread: Thread | None = None
        self._directory_cache: DirectoryCache | None = None

    def start(self) -> bool:
        if self._worker_thread and self._worker_thread.is_alive():
            self._logger.warning("DirectorySyncManager is already running.")
            return False

        if not self._initialise_directory_cache():
            msg = f"Failed to initialise directory cache. Directory not found: {self._target_directory}"
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
            abs_path = os.path.join(self._target_directory, item_name)
            if not os.path.isfile(abs_path):
                continue

            file_hash = self._file_sha256(abs_path)
            if file_hash is not None:
                entries[abs_path] = file_hash

        self._directory_cache = DirectoryCache(entries=entries)
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

            self._apply_event(event)

    def _apply_event(self, event: SyncEngineFileSystemEvent) -> None:
        if event.is_directory or self._directory_cache is None:
            return

        match event.type:
            case FileSystemEventType.CREATED | FileSystemEventType.MODIFIED:
                self._handle_created_or_modified(event.path)
            case FileSystemEventType.DELETED:
                self._handle_deleted(event.path)
            case FileSystemEventType.MOVED:
                self._handle_moved(event.path, event.new_path)
            case _:
                self._logger.warning(f"Received unsupported file system event type: {event.type}")

    def _handle_created_or_modified(self, file_path: str) -> None:
        if self._directory_cache is None:
            return

        file_hash = self._file_sha256(file_path)
        if file_hash is not None:
            self._directory_cache.entries[file_path] = file_hash
        elif file_path in self._directory_cache.entries:
            self._directory_cache.entries.pop(file_path, None)

    def _handle_deleted(self, file_path: str) -> None:
        if self._directory_cache is None:
            return

        self._directory_cache.entries.pop(file_path, None)

    def _handle_moved(self, old_path: str, new_path: str | None) -> None:
        if self._directory_cache is None or not isinstance(new_path, str):
            return

        moved_file_hash = self._directory_cache.entries.pop(old_path, None)
        if moved_file_hash is None:
            return

        self._directory_cache.entries[new_path] = moved_file_hash

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
        if not self._worker_thread:
            return

        self._stop_event.set()
        self._worker_thread.join(timeout=2)
