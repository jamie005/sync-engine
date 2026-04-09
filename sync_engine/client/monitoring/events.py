from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class FileSystemEventType(Enum):
    UNKNOWN = 0
    CREATED = 1
    DELETED = 2
    MODIFIED = 3
    MOVED = 4


@dataclass(frozen=True)
class SyncEngineFileSystemEvent:
    type: FileSystemEventType
    path: Path
    new_path: Path | None = None
    is_directory: bool = False
