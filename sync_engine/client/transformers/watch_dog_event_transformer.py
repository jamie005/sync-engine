from pathlib import Path

from watchdog.events import FileClosedEvent, FileSystemEvent, FileCreatedEvent, FileDeletedEvent, FileMovedEvent

from sync_engine.client.monitoring.events import SyncEngineFileSystemEvent, FileSystemEventType


class WatchDogEventTransformer:
    """Transforms watchdog file events to sync engine file events."""

    @staticmethod
    def transform(watchdog_event: FileSystemEvent) -> SyncEngineFileSystemEvent:
        """
        Convert a watchdog file system event to a sync engine file system event.

        Args:
            watchdog_event: A watchdog FileSystemEvent instance

        Returns:
            A SyncEngineFileSystemEvent instance
        """
        if isinstance(watchdog_event, FileCreatedEvent):
            event_type = FileSystemEventType.CREATED
        elif isinstance(watchdog_event, FileClosedEvent):
            event_type = FileSystemEventType.MODIFIED
        elif isinstance(watchdog_event, FileDeletedEvent):
            event_type = FileSystemEventType.DELETED
        elif isinstance(watchdog_event, FileMovedEvent):
            event_type = FileSystemEventType.MOVED
        else:
            event_type = FileSystemEventType.UNKNOWN

        src_path_name = str(watchdog_event.src_path)
        src_path = Path(src_path_name)

        dest_path_name = str(watchdog_event.dest_path)
        if dest_path_name:
            dest_path = Path(dest_path_name)
        else:
            dest_path = None

        return SyncEngineFileSystemEvent(
            type=event_type,
            path=src_path,
            new_path=dest_path,
            is_directory=watchdog_event.is_directory
        )
