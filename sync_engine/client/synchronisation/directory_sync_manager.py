import logging
from pathlib import Path
from queue import Empty, Queue
from threading import Event, Thread
from typing import Callable, Protocol

from pydantic import BaseModel, Field

from sync_engine.client.monitoring.events import FileSystemEventType, SyncEngineFileSystemEvent
from sync_engine.client.synchronisation.api_client import SyncApiClientError
from sync_engine.common.hashing import sha256_string
from sync_engine.common.schemas import CreateFileRequest, DeleteFileRequest, RenameFileRequest, UpdateFileRequest


class _DirectoryCache(BaseModel):
    entries: dict[Path, str] = Field(default_factory=dict)


class _SyncApiClient(Protocol):
    def create_file(self, body: CreateFileRequest) -> object:
        ...

    def update_file(self, body: UpdateFileRequest) -> object:
        ...

    def delete_file(self, body: DeleteFileRequest) -> object:
        ...

    def rename_file(self, body: RenameFileRequest) -> object:
        ...


class DirectorySyncManager:
    _EVENT_CONSUME_INTERVAL_SECONDS: float = 0.5

    _logger = logging.getLogger(__name__)

    def __init__(self, target_directory: Path,
                 file_system_events: Queue[SyncEngineFileSystemEvent],
                 api_client: _SyncApiClient,
                 hash_string: Callable[[str], str] = sha256_string,
                 read_text: Callable[[Path], str] | None = None) -> None:
        self._target_directory = target_directory
        self._file_system_events = file_system_events
        self._api_client = api_client
        self._hash_string = hash_string
        self._read_text = read_text or self._default_read_text
        self._stop_event = Event()
        self._worker_thread: Thread | None = None
        self._directory_cache: _DirectoryCache | None = None

    def start(self) -> bool:
        if self._worker_thread and self._worker_thread.is_alive():
            self._logger.warning("DirectorySyncManager is already running.")
            return False

        if not self._initialise_directory_cache():
            msg = f"Failed to initialise directory cache. Directory not found: {self._target_directory}"
            self._logger.error(msg)
            return False

        self._stop_event.clear()
        self._worker_thread = Thread(target=self._consume_events, daemon=True)
        self._worker_thread.start()
        return True

    def _initialise_directory_cache(self) -> bool:
        if not self._target_directory.is_dir():
            return False

        entries: dict[Path, str] = {}
        for item_path in self._target_directory.iterdir():
            if not item_path.is_file():
                continue

            absolute_path = item_path.resolve()
            content_and_hash = self._read_file_content_and_hash(absolute_path)
            if content_and_hash is None:
                continue

            _, file_hash = content_and_hash
            entries[absolute_path] = file_hash

        self._directory_cache = _DirectoryCache(entries=entries)
        return True

    @staticmethod
    def _default_read_text(file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8")

    def _read_file_content(self, file_path: Path) -> str | None:
        try:
            return self._read_text(file_path)
        except OSError as exc:
            self._logger.warning(f"Failed to read file content for {file_path}. Skipping sync for this file: {exc}")
        except UnicodeDecodeError as exc:
            self._logger.warning(
                f"Failed to decode file content for {file_path} as UTF-8. Skipping sync for this file: {exc}"
            )
        return None

    def _read_file_content_and_hash(self, file_path: Path) -> tuple[str, str] | None:
        file_content = self._read_file_content(file_path)
        if file_content is None:
            return None

        return file_content, self._hash_string(file_content)

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
            case FileSystemEventType.CREATED:
                self._handle_created(event.path)
            case FileSystemEventType.MODIFIED:
                self._handle_modified(event.path)
            case FileSystemEventType.DELETED:
                self._handle_deleted(event.path)
            case FileSystemEventType.MOVED:
                self._handle_moved(event.path, event.new_path)
            case _:
                self._logger.warning(f"Received unsupported file system event type: {event.type}")

    def _handle_created(self, file_path: Path) -> None:
        if self._directory_cache is None:
            return

        absolute_path = file_path.resolve()
        content_and_hash = self._read_file_content_and_hash(absolute_path)
        if content_and_hash is None:
            return

        file_content, request_hash = content_and_hash

        request = CreateFileRequest(
                file_name=absolute_path.name,
                file_hash=request_hash,
                content=file_content,
        )
        try:
            self._api_client.create_file(request)
        except SyncApiClientError as exc:
            self._logger.error(f"Failed to sync created file {absolute_path}: {exc}")
            return

        self._logger.info(f"Synced created file: {absolute_path}")
        self._directory_cache.entries[absolute_path] = request_hash

    def _handle_modified(self, file_path: Path) -> None:
        if self._directory_cache is None:
            return

        absolute_path = file_path.resolve()
        content_and_hash = self._read_file_content_and_hash(absolute_path)
        if content_and_hash is None:
            return

        file_content, request_hash = content_and_hash

        request = UpdateFileRequest(
            file_name=absolute_path.name,
            file_hash=request_hash,
            content=file_content,
        )
        try:
            self._api_client.update_file(request)
        except SyncApiClientError as exc:
            self._logger.error(f"Failed to sync modified file {absolute_path}: {exc}")
            return

        self._logger.info(f"Synced modified file: {absolute_path}")
        self._directory_cache.entries[absolute_path] = request_hash

    def _handle_deleted(self, file_path: Path) -> None:
        if self._directory_cache is None:
            return

        absolute_path = file_path.resolve()
        request = DeleteFileRequest(file_name=absolute_path.name)
        try:
            self._api_client.delete_file(request)
        except SyncApiClientError as exc:
            self._logger.error(f"Failed to sync deleted file {absolute_path}: {exc}")
            return

        self._logger.info(f"Synced deleted file: {absolute_path}")
        self._directory_cache.entries.pop(absolute_path, None)

    def _handle_moved(self, old_path: Path, new_path: Path | None) -> None:
        if self._directory_cache is None or new_path is None:
            return

        old_absolute_path = old_path.resolve()
        new_absolute_path = new_path.resolve()
        moved_file_hash = self._directory_cache.entries.pop(old_absolute_path, None)
        if moved_file_hash is None:
            return

        request = RenameFileRequest(
                old_file_name=old_absolute_path.name,
                new_file_name=new_absolute_path.name,
            )
        try:
            self._api_client.rename_file(request)
        except SyncApiClientError as exc:
            self._logger.error(f"Failed to sync moved file from {old_absolute_path} to {new_absolute_path}: {exc}")
            return

        self._logger.info(f"Synced moved file: {old_absolute_path} -> {new_absolute_path}")
        self._directory_cache.entries[new_absolute_path] = moved_file_hash

    def stop(self) -> None:
        if not self._worker_thread:
            return

        self._stop_event.set()
        self._worker_thread.join(timeout=2)
