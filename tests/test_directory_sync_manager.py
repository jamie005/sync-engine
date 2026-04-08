"""Tests for DirectorySyncManager."""
from pathlib import Path
from unittest.mock import Mock
import time

from sync_engine.client.synchronisation.directory_sync_manager import DirectorySyncManager
from sync_engine.client.monitoring.events import SyncEngineFileSystemEvent, FileSystemEventType
from sync_engine.client.synchronisation.api_client import SyncApiClientError


class TestDirectorySyncManager:
    """Test DirectorySyncManager."""

    def test_init(self, temp_dir, sync_event_queue, mock_api_client):
        """Test initialization."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        assert manager._target_directory == temp_dir
        assert manager._file_system_events == sync_event_queue

    def test_start(self, temp_dir, sync_event_queue, mock_api_client):
        """Test start."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        result = manager.start()

        assert result is True
        assert manager._worker_thread is not None
        assert manager._directory_cache is not None

        manager.stop()

    def test_start_already_running(self, temp_dir, sync_event_queue, mock_api_client):
        """Test start when already running."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        result = manager.start()
        assert result is False

        manager.stop()

    def test_start_directory_not_found(self, sync_event_queue, mock_api_client):
        """Test start with non-existent directory."""
        manager = DirectorySyncManager(Path("/non/existent"), sync_event_queue, mock_api_client)
        result = manager.start()
        assert result is False

    def test_stop(self, temp_dir, sync_event_queue, mock_api_client):
        """Test stop."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()
        time.sleep(0.1)

        manager.stop()
        time.sleep(0.1)

    def test_handle_created_file(self, temp_dir, sync_event_queue, mock_api_client):
        """Test handling created file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.CREATED,
            path=test_file,
            is_directory=False
        )
        sync_event_queue.put(event)

        time.sleep(1)
        manager.stop()

        mock_api_client.create_file.assert_called()

    def test_handle_deleted_file(self, temp_dir, sync_event_queue, mock_api_client):
        """Test handling deleted file."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()
        time.sleep(0.5)

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.DELETED,
            path=test_file,
            is_directory=False
        )
        sync_event_queue.put(event)

        time.sleep(1)
        manager.stop()

        mock_api_client.delete_file.assert_called()

    def test_handle_api_error(self, temp_dir, sync_event_queue, mock_api_client):
        """Test handling API error."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        mock_api_client.create_file.side_effect = SyncApiClientError("API error", status_code=500)

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.CREATED,
            path=test_file,
            is_directory=False
        )
        sync_event_queue.put(event)

        time.sleep(1)
        manager.stop()

        mock_api_client.create_file.assert_called()

    def test_directory_event_ignored(self, temp_dir, sync_event_queue, mock_api_client):
        """Test that directory events are ignored."""
        test_dir = temp_dir / "subdir"
        test_dir.mkdir()

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.CREATED,
            path=test_dir,
            is_directory=True
        )
        sync_event_queue.put(event)

        time.sleep(1)
        manager.stop()

        mock_api_client.create_file.assert_not_called()


class TestDirectorySyncManagerInit:
    """Test DirectorySyncManager initialization."""

    def test_init_with_defaults(self, temp_dir, sync_event_queue, mock_api_client):
        """Test initialization with default parameters."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)

        assert manager._target_directory == temp_dir
        assert manager._file_system_events == sync_event_queue
        assert manager._api_client == mock_api_client
        assert manager._worker_thread is None
        assert manager._directory_cache is None

    def test_init_with_custom_hash_function(self, temp_dir, sync_event_queue, mock_api_client):
        """Test initialization with custom hash function."""
        custom_hash = Mock(return_value="custom_hash")
        manager = DirectorySyncManager(
            temp_dir,
            sync_event_queue,
            mock_api_client,
            hash_string=custom_hash
        )

        assert manager._hash_string == custom_hash

    def test_init_with_custom_read_text(self, temp_dir, sync_event_queue, mock_api_client):
        """Test initialization with custom read_text function."""
        custom_read = Mock(return_value="content")
        manager = DirectorySyncManager(
            temp_dir,
            sync_event_queue,
            mock_api_client,
            read_text=custom_read
        )

        assert manager._read_text == custom_read


class TestDirectorySyncManagerStart:
    """Test DirectorySyncManager start method."""

    def test_start_success(self, temp_dir, sync_event_queue, mock_api_client):
        """Test successful start."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)

        result = manager.start()

        assert result is True
        assert manager._worker_thread is not None
        assert manager._worker_thread.is_alive()
        assert manager._directory_cache is not None

        # Clean up
        manager.stop()

    def test_start_already_running(self, temp_dir, sync_event_queue, mock_api_client):
        """Test start when already running."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        result = manager.start()

        assert result is False

        # Clean up
        manager.stop()

    def test_start_directory_not_found(self, sync_event_queue, mock_api_client):
        """Test start with non-existent directory."""
        non_existent_dir = Path("/non/existent/directory")
        manager = DirectorySyncManager(non_existent_dir, sync_event_queue, mock_api_client)

        result = manager.start()

        assert result is False

    def test_start_initialise_directory_cache(self, temp_dir, sync_event_queue, mock_api_client):
        """Test that start initialises directory cache."""
        # Create some test files
        (temp_dir / "file1.txt").write_text("content1")
        (temp_dir / "file2.txt").write_text("content2")

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        assert manager._directory_cache is not None
        assert len(manager._directory_cache.entries) == 2

        # Clean up
        manager.stop()


class TestDirectorySyncManagerStop:
    """Test DirectorySyncManager stop method."""

    def test_stop_when_running(self, temp_dir, sync_event_queue, mock_api_client):
        """Test stop when manager is running."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        initial_thread = manager._worker_thread
        manager.stop()

        # Give thread time to stop
        time.sleep(0.1)
        assert not initial_thread.is_alive()

    def test_stop_when_not_running(self, temp_dir, sync_event_queue, mock_api_client):
        """Test stop when manager is not running."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)

        # Should not raise
        manager.stop()


class TestDirectorySyncManagerFileHandling:
    """Test file handling methods."""

    def test_handle_created_file(self, temp_dir, sync_event_queue, mock_api_client):
        """Test handling created file event."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.CREATED,
            path=test_file,
            is_directory=False
        )
        sync_event_queue.put(event)

        # Give time for event to be processed
        time.sleep(1)

        mock_api_client.create_file.assert_called()
        call_args = mock_api_client.create_file.call_args[0][0]
        assert call_args.file_name == "test.txt"
        assert call_args.content == "test content"

        manager.stop()

    def test_handle_modified_file(self, temp_dir, sync_event_queue, mock_api_client):
        """Test handling modified file event."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("modified content")

        # Pre-populate cache
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        # Wait for cache to be initialized
        time.sleep(0.5)

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.MODIFIED,
            path=test_file,
            is_directory=False
        )
        sync_event_queue.put(event)

        # Give time for event to be processed
        time.sleep(1)

        mock_api_client.update_file.assert_called()
        call_args = mock_api_client.update_file.call_args[0][0]
        assert call_args.file_name == "test.txt"
        assert call_args.content == "modified content"

        manager.stop()

    def test_handle_deleted_file(self, temp_dir, sync_event_queue, mock_api_client):
        """Test handling deleted file event."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("content")

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.DELETED,
            path=test_file,
            is_directory=False
        )
        sync_event_queue.put(event)

        # Give time for event to be processed
        time.sleep(1)

        mock_api_client.delete_file.assert_called()
        call_args = mock_api_client.delete_file.call_args[0][0]
        assert call_args.file_name == "test.txt"

        manager.stop()

    def test_handle_moved_file(self, temp_dir, sync_event_queue, mock_api_client):
        """Test handling moved file event."""
        old_path = temp_dir / "old.txt"
        new_path = temp_dir / "new.txt"
        old_path.write_text("content")

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        # Give time for cache to be initialized with old file
        time.sleep(0.5)

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.MOVED,
            path=old_path,
            new_path=new_path,
            is_directory=False
        )
        sync_event_queue.put(event)

        # Give time for event to be processed
        time.sleep(1)

        mock_api_client.rename_file.assert_called()
        call_args = mock_api_client.rename_file.call_args[0][0]
        assert call_args.old_file_name == "old.txt"
        assert call_args.new_file_name == "new.txt"

        manager.stop()


class TestDirectorySyncManagerErrorHandling:
    """Test error handling."""

    def test_handle_created_file_api_error(self, temp_dir, sync_event_queue, mock_api_client):
        """Test handling API error on file creation."""
        test_file = temp_dir / "test.txt"
        test_file.write_text("test content")

        mock_api_client.create_file.side_effect = SyncApiClientError("API error", status_code=500)

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.CREATED,
            path=test_file,
            is_directory=False
        )
        sync_event_queue.put(event)

        # Give time for event to be processed
        time.sleep(1)

        # Should have called API despite error
        mock_api_client.create_file.assert_called()

        manager.stop()

    def test_handle_file_with_unicode_decode_error(self, temp_dir, sync_event_queue, mock_api_client):
        """Test handling file with unicode decode error."""
        test_file = temp_dir / "test.txt"
        test_file.write_bytes(b"\x80\x81\x82")

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.CREATED,
            path=test_file,
            is_directory=False
        )
        sync_event_queue.put(event)

        # Give time for event to be processed
        time.sleep(1)

        # Should not have called API due to decode error
        mock_api_client.create_file.assert_not_called()

        manager.stop()

    def test_invalid_event_type_ignored(self, temp_dir, sync_event_queue, mock_api_client):
        """Test that invalid event types are ignored."""
        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        # Put invalid event
        sync_event_queue.put("invalid event")

        time.sleep(1)

        # Should not call any API methods
        mock_api_client.create_file.assert_not_called()
        mock_api_client.update_file.assert_not_called()
        mock_api_client.delete_file.assert_not_called()
        mock_api_client.rename_file.assert_not_called()

        manager.stop()

    def test_directory_event_ignored(self, temp_dir, sync_event_queue, mock_api_client):
        """Test that directory events are ignored."""
        test_dir = temp_dir / "subdir"
        test_dir.mkdir()

        manager = DirectorySyncManager(temp_dir, sync_event_queue, mock_api_client)
        manager.start()

        event = SyncEngineFileSystemEvent(
            type=FileSystemEventType.CREATED,
            path=test_dir,
            is_directory=True
        )
        sync_event_queue.put(event)

        time.sleep(1)

        # Should not call create_file for directories
        mock_api_client.create_file.assert_not_called()

        manager.stop()
