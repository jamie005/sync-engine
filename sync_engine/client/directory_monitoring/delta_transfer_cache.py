import hashlib
import logging
import os
from dataclasses import dataclass
from queue import Empty, Queue
from threading import Event, Thread

from sync_engine.client.directory_monitoring.events import FileSystemEventType, SyncEngineFileSystemEvent


@dataclass(frozen=True)
class FileCacheEntry:
    relative_path: str
    size_bytes: int
    modified_time_ns: int
    sha256: str


@dataclass(frozen=True)
class DeltaTransferItem:
    type: FileSystemEventType
    path: str
    new_path: str | None
    previous: FileCacheEntry | None
    current: FileCacheEntry | None


class DeltaTransferCache:
    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        target_directory: str,
        event_queue: Queue,
        delta_output_queue: Queue | None = None,
    ) -> None:
        self._target_directory = os.path.abspath(target_directory)
        self._event_queue = event_queue
        self._delta_output_queue = delta_output_queue or Queue()
        self._cache: dict[str, FileCacheEntry] = {}
        self._stop_event = Event()
        self._worker_thread: Thread | None = None

    def start(self) -> None:
        if self._worker_thread and self._worker_thread.is_alive():
            return

        self._stop_event.clear()
        self._prime_cache_from_disk()
        self._worker_thread = Thread(target=self._consume_events, daemon=True, name="delta-transfer-cache")
        self._worker_thread.start()

    def stop(self) -> None:
        self._stop_event.set()
        if self._worker_thread:
            self._worker_thread.join(timeout=2)

    def _consume_events(self) -> None:
        while not self._stop_event.is_set():
            try:
                event = self._event_queue.get(timeout=0.5)
            except Empty:
                continue

            if not isinstance(event, SyncEngineFileSystemEvent):
                continue

            delta = self._apply_event(event)
            if delta is None:
                continue

            self._delta_output_queue.put(delta)

    def _prime_cache_from_disk(self) -> None:
        if not os.path.isdir(self._target_directory):
            return

        entries: dict[str, FileCacheEntry] = {}
        for item_name in os.listdir(self._target_directory):
            abs_path = os.path.join(self._target_directory, item_name)
            if not os.path.isfile(abs_path):
                continue

            cache_entry = self._create_cache_entry(abs_path)
            if cache_entry is not None:
                entries[cache_entry.relative_path] = cache_entry

        self._cache = entries

    def _apply_event(self, event: SyncEngineFileSystemEvent) -> DeltaTransferItem | None:
        if event.type == FileSystemEventType.CREATED:
            return self._handle_create_or_modify(FileSystemEventType.CREATED, event.path)

        if event.type == FileSystemEventType.MODIFIED:
            return self._handle_create_or_modify(FileSystemEventType.MODIFIED, event.path)

        if event.type == FileSystemEventType.DELETED:
            return self._handle_deleted(event.path)

        if event.type == FileSystemEventType.MOVED:
            return self._handle_moved(event.path, event.new_path)

        return None

    def _handle_create_or_modify(self, event_type: FileSystemEventType, file_path: str) -> DeltaTransferItem | None:
        cache_entry = self._create_cache_entry(file_path)
        if cache_entry is None:
            return None

        previous = self._cache.get(cache_entry.relative_path)
        if event_type == FileSystemEventType.MODIFIED and previous == cache_entry:
            return None

        self._cache[cache_entry.relative_path] = cache_entry

        return DeltaTransferItem(
            type=event_type,
            path=cache_entry.relative_path,
            new_path=None,
            previous=previous,
            current=cache_entry,
        )

    def _handle_deleted(self, file_path: str) -> DeltaTransferItem | None:
        relative_path = self._to_relative_path(file_path)
        if relative_path is None:
            return None

        previous = self._cache.pop(relative_path, None)

        if previous is None:
            return None

        return DeltaTransferItem(
            type=FileSystemEventType.DELETED,
            path=relative_path,
            new_path=None,
            previous=previous,
            current=None,
        )

    def _handle_moved(self, old_path: str, new_path: str | None) -> DeltaTransferItem | None:
        old_relative = self._to_relative_path(old_path)
        new_relative = self._to_relative_path(new_path) if isinstance(new_path, str) else None

        if old_relative is None and new_relative is None:
            return None

        previous = self._cache.pop(old_relative, None) if old_relative is not None else None

        if new_relative is None:
            if old_relative is None:
                return None

            if previous is None:
                return None

            return DeltaTransferItem(
                type=FileSystemEventType.DELETED,
                path=old_relative,
                new_path=None,
                previous=previous,
                current=None,
            )

        if not isinstance(new_path, str):
            return None

        new_entry = self._create_cache_entry(new_path)
        if new_entry is None:
            return None

        self._cache[new_relative] = new_entry

        return DeltaTransferItem(
            type=FileSystemEventType.MOVED,
            path=old_relative or new_relative,
            new_path=new_relative,
            previous=previous,
            current=new_entry,
        )

    def _to_relative_path(self, file_path: str | None) -> str | None:
        if not isinstance(file_path, str):
            return None

        absolute_path = os.path.abspath(file_path)
        try:
            common_path = os.path.commonpath([self._target_directory, absolute_path])
        except ValueError:
            return None

        if common_path != self._target_directory:
            return None

        return os.path.relpath(absolute_path, self._target_directory)

    def _create_cache_entry(self, file_path: str) -> FileCacheEntry | None:
        relative_path = self._to_relative_path(file_path)
        if relative_path is None:
            return None

        if not os.path.isfile(file_path):
            return None

        stat = os.stat(file_path)
        digest = self._file_sha256(file_path)
        if digest is None:
            return None

        return FileCacheEntry(
            relative_path=relative_path,
            size_bytes=stat.st_size,
            modified_time_ns=stat.st_mtime_ns,
            sha256=digest,
        )

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
