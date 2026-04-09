import hashlib
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def sha256_string(data: str, encoding: str = "utf-8") -> str:
    """
    Compute SHA256 hash of a string.

    Args:
        data: The string to hash.
        encoding: The encoding to use when converting string to bytes (default: utf-8).

    Returns:
        The hexadecimal representation of the SHA256 hash.
    """
    digest = hashlib.sha256()
    digest.update(data.encode(encoding))
    return digest.hexdigest()


def sha256_file(file_path: Path) -> str | None:
    """
    Compute SHA256 hash of a file on disk.

    Args:
        file_path: Path to the file to hash.

    Returns:
        The hexadecimal representation of the SHA256 hash, or None if file not found or error occurs.
    """
    try:
        digest = hashlib.sha256()
        with open(file_path, "rb") as file_stream:
            for chunk in iter(lambda: file_stream.read(64 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning(f"Unable to hash file: {file_path}. Error: {exc}")
        return None
