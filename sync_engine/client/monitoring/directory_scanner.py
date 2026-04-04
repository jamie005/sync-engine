import os
from queue import Queue
from sync_engine.client.monitoring.events import SyncEngineFileSystemEvent, FileSystemEventType


class DirectoryScanner:
    def __init__(self, event_queue: Queue):
        self.event_queue = event_queue

    def scan_directory(self, target_directory: str):
        """
        Scans the target directory for files (non-recursive) and queues CREATED events for each file found.
        """
        for item in os.listdir(target_directory):
            item_path = os.path.join(target_directory, item)
            if not os.path.isfile(item_path):
                continue

            event = SyncEngineFileSystemEvent(
                type=FileSystemEventType.CREATED,
                path=item_path,
                is_directory=False
            )
            self.event_queue.put(event)
