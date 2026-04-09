import logging
from pathlib import Path
from queue import Queue
from time import monotonic
from typing import Callable, Protocol

from watchdog.events import (
    FileClosedEvent,
    FileCreatedEvent,
    FileDeletedEvent,
    FileMovedEvent,
    FileSystemEvent,
    FileSystemEventHandler
)
from watchdog.observers import Observer

from .events import FileSystemEventType, SyncEngineFileSystemEvent
from sync_engine.client.transformers.watch_dog_event_transformer import WatchDogEventTransformer


# COMPROMISE: I selected watchdog over watchfiles as it has the ability to listen for file moves. However,
# watchdog has some quirks around duplicate create/close events which I have attempted to mitigate with a
# suppression window.


class _SyncEngineClientFileEventHandler(FileSystemEventHandler):
    """Filters watchdog events and forwards supported events to a queue."""

    _CREATE_CLOSE_SUPPRESSION_WINDOW_SECONDS: float = 0.25
    _VALID_EVENT_TYPES: tuple[type[FileSystemEvent], ...] = (
        FileCreatedEvent,
        FileClosedEvent,
        FileDeletedEvent,
        FileMovedEvent
    )

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        file_events: Queue[SyncEngineFileSystemEvent],
        clock: Callable[[], float] = monotonic,
        event_transformer: Callable[[FileSystemEvent], SyncEngineFileSystemEvent] = WatchDogEventTransformer.transform,
    ) -> None:
        super().__init__()
        self._file_events = file_events
        self._clock = clock
        self._event_transformer = event_transformer
        self._created_event_timestamps: dict[str, float] = {}

    def dispatch(self, event: FileSystemEvent) -> None:
        """Suppress duplicate create/close events before dispatching."""
        if not self._valid_event(event):
            return

        if not isinstance(event.src_path, str):
            return

        now = self._clock()
        self._prune_stale_pending_created(now)

        if isinstance(event, FileCreatedEvent):
            self._created_event_timestamps[event.src_path] = now
        elif isinstance(event, FileClosedEvent):
            created_at = self._created_event_timestamps.pop(event.src_path, None)
            if self._is_close_event_for_recent_create(created_at=created_at, now=now):
                return

        return super().dispatch(event)

    @classmethod
    def _valid_event(cls, event: FileSystemEvent) -> bool:
        # ASSUMPTION: the client only needs to synchronise regular files, not directories.
        return (
            not event.is_directory and
            isinstance(event, cls._VALID_EVENT_TYPES) and
            isinstance(event.src_path, str)
        )

    def _prune_stale_pending_created(self, now: float) -> None:
        stale_paths = [
            path
            for path, created_at in self._created_event_timestamps.items()
            if (now - created_at) > self._CREATE_CLOSE_SUPPRESSION_WINDOW_SECONDS
        ]
        for path in stale_paths:
            self._created_event_timestamps.pop(path, None)

    @classmethod
    def _is_close_event_for_recent_create(cls, created_at: float | None, now: float) -> bool:
        return (
            created_at is not None
            and (now - created_at) <= cls._CREATE_CLOSE_SUPPRESSION_WINDOW_SECONDS
        )

    def on_any_event(self, event: FileSystemEvent) -> None:
        """Transform and enqueue supported filesystem events."""
        sync_engine_file_sys_event = self._event_transformer(event)

        if sync_engine_file_sys_event.type == FileSystemEventType.UNKNOWN:
            self._logger.warning(f"Unknown file event detected: {event}")
            return

        log_message = self._get_valid_event_log_message(sync_engine_file_sys_event)
        self._logger.info(log_message)
        self._file_events.put(sync_engine_file_sys_event)

    @staticmethod
    def _get_valid_event_log_message(event: SyncEngineFileSystemEvent) -> str:
        msg = f"File {event.type.name.lower()}: {event.path}"
        if event.type == FileSystemEventType.MOVED and event.new_path:
            msg += f" -> {event.new_path}"

        return msg


class _ObserverLike(Protocol):
    def schedule(self, event_handler: FileSystemEventHandler, path: str, recursive: bool = False) -> None: ...

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def join(self) -> None: ...


class DirectoryMonitor:
    """Starts and stops a watchdog observer for a target directory."""

    _logger = logging.getLogger(__name__)

    def __init__(
        self,
        target_directory: Path,
        file_events: Queue[SyncEngineFileSystemEvent],
        observer: _ObserverLike | None = None,
        event_handler: FileSystemEventHandler | None = None,
    ) -> None:
        self._observer = observer or Observer()
        self._target_directory: Path = target_directory
        self._event_handler = event_handler or _SyncEngineClientFileEventHandler(file_events=file_events)
        self._started: bool = False

    def start(self) -> bool:
        """Start the observer if it is not already running."""
        if self._started:
            self._logger.warning("DirectoryMonitor is already running.")
            return False
        try:
            # ASSUMPTION: the client does not need to synchronise the contents of subdirectories.
            self._observer.schedule(self._event_handler, str(self._target_directory), recursive=False)
            self._observer.start()
        except Exception as e:
            self._logger.exception(f"Failed to start directory monitor: {e}")
            return False

        self._started = True
        return True

    def stop(self) -> None:
        """Stop the observer and wait for it to terminate."""
        if not self._started:
            return
        try:
            self._observer.stop()
            self._observer.join()
        except Exception as e:
            self._logger.exception(f"Error while stopping directory monitor: {e}")
        finally:
            self._started = False
