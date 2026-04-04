import logging
from queue import Queue

from watchdog.events import (FileClosedEvent, FileCreatedEvent, FileDeletedEvent,
                             FileMovedEvent, FileSystemEvent, FileSystemEventHandler)
from watchdog.observers import Observer

from .events import FileSystemEventType, SyncEngineFileSystemEvent
from sync_engine.client.transformers.watch_dog_event_transformer import WatchDogEventTransformer


class _SyncEngineClientFileEventHandler(FileSystemEventHandler):
    _VALID_EVENT_TYPES: tuple[type[FileSystemEvent], ...] = (
        FileCreatedEvent, FileClosedEvent, FileDeletedEvent, FileMovedEvent
    )
    _IGNORED_FILE_TYPES: tuple[str, ...] = (".swp",)

    _logger = logging.getLogger(__name__)

    def __init__(self, file_events: Queue) -> None:
        super().__init__()
        self._file_events = file_events

    def dispatch(self, event: FileSystemEvent) -> None:
        if not self._valid_event(event):
            return

        return super().dispatch(event)

    @classmethod
    def _valid_event(cls, event: FileSystemEvent) -> bool:
        return (
            not event.is_directory and
            isinstance(event, cls._VALID_EVENT_TYPES) and
            isinstance(event.src_path, str) and
            not event.src_path.endswith(cls._IGNORED_FILE_TYPES)
        )

    def on_any_event(self, event: FileSystemEvent) -> None:
        sync_engine_file_sys_event = WatchDogEventTransformer.transform(event)

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


class DirectoryMonitor:
    _logger = logging.getLogger(__name__)

    def __init__(self, target_directory: str, file_events: Queue) -> None:
        self._observer = Observer()
        self._target_directory = target_directory
        self._event_handler = _SyncEngineClientFileEventHandler(file_events=file_events)

    def start(self) -> None:
        try:
            self._observer.schedule(self._event_handler, self._target_directory, recursive=False)
            self._observer.start()
        except FileNotFoundError:
            self._logger.error(f"Failed to start monitoring directory - directory not found: {self._target_directory}")
        except Exception as e:
            self._logger.error(f"Error while monitoring directory: {e}")

    def stop(self) -> None:
        self._observer.stop()
        self._observer.join()
