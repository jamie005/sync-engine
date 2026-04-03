from dataclasses import dataclass
from enum import Enum


class FileSystemEventType(Enum):
    UNKNNOWN = 0
    CREATED = 1
    DELETED = 2
    MODIFIED = 3
    MOVED = 4


@dataclass(frozen=True)
class SyncEngineFileSystemEvent:
    type: FileSystemEventType
    path: str
    new_path: str | None = None
    is_directory: bool = False
