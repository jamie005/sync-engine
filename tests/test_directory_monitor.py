"""Tests for DirectoryMonitor and _SyncEngineClientFileEventHandler."""
import pytest
from pathlib import Path
from queue import Queue
from unittest.mock import Mock

from watchdog.events import FileCreatedEvent, FileClosedEvent, FileDeletedEvent, FileMovedEvent

from sync_engine.client.monitoring.directory_monitor import DirectoryMonitor, _SyncEngineClientFileEventHandler
from sync_engine.client.monitoring.events import SyncEngineFileSystemEvent, FileSystemEventType


class TestFileEventHandler:
    """Test _SyncEngineClientFileEventHandler."""

    def test_init(self):
        """Test handler initialization."""
        event_queue = Queue()
        handler = _SyncEngineClientFileEventHandler(event_queue)
        assert handler._file_events == event_queue

    @pytest.mark.parametrize(
        "event",
        [
            FileCreatedEvent("/tmp/test.txt"),
            FileClosedEvent("/tmp/test.txt"),
            FileDeletedEvent("/tmp/test.txt"),
            FileMovedEvent("/tmp/old.txt", "/tmp/new.txt"),
        ],
    )
    def test_valid_event(self, event):
        """Test event validation for supported event types."""
        assert _SyncEngineClientFileEventHandler._valid_event(event)

    def test_invalid_directory_event(self):
        """Test that directory events are invalid."""
        event = FileCreatedEvent("/tmp/dir")
        event.is_directory = True
        assert not _SyncEngineClientFileEventHandler._valid_event(event)

    def test_create_close_suppression(self):
        """Test create-close suppression window."""
        created_at = 1.0
        now = 1.1
        assert _SyncEngineClientFileEventHandler._is_close_event_for_recent_create(created_at, now)

        now = 1.5
        assert not _SyncEngineClientFileEventHandler._is_close_event_for_recent_create(created_at, now)

    def test_on_any_event_queues_valid_event(self):
        """Test that valid events are queued."""
        event_queue = Queue()
        mock_transformer = Mock(return_value=SyncEngineFileSystemEvent(
            type=FileSystemEventType.CREATED,
            path=Path("/tmp/test.txt")
        ))
        handler = _SyncEngineClientFileEventHandler(event_queue, event_transformer=mock_transformer)

        handler.on_any_event(FileCreatedEvent("/tmp/test.txt"))

        assert event_queue.qsize() == 1


class TestDirectoryMonitor:
    """Test DirectoryMonitor."""

    def test_init(self, temp_dir):
        """Test monitor initialization."""
        event_queue = Queue()
        monitor = DirectoryMonitor(temp_dir, event_queue)
        assert monitor._target_directory == temp_dir

    def test_start(self, temp_dir):
        """Test monitor start."""
        event_queue = Queue()
        mock_observer = Mock()
        monitor = DirectoryMonitor(temp_dir, event_queue, observer=mock_observer)

        result = monitor.start()

        assert result is True
        assert monitor._started is True
        mock_observer.schedule.assert_called_once()
        mock_observer.start.assert_called_once()

    def test_start_already_running(self, temp_dir):
        """Test start when already running."""
        event_queue = Queue()
        mock_observer = Mock()
        monitor = DirectoryMonitor(temp_dir, event_queue, observer=mock_observer)
        monitor._started = True

        result = monitor.start()
        assert result is False

    def test_stop(self, temp_dir):
        """Test monitor stop."""
        event_queue = Queue()
        mock_observer = Mock()
        monitor = DirectoryMonitor(temp_dir, event_queue, observer=mock_observer)
        monitor._started = True

        monitor.stop()

        mock_observer.stop.assert_called_once()
        assert monitor._started is False
