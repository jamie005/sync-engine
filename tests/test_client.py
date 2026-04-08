"""Tests for SyncEngineClient."""
from pathlib import Path
from queue import Queue
from threading import Event
from unittest.mock import Mock, patch

from sync_engine.client.client import SyncEngineClient
from sync_engine.client.synchronisation.api_client import HttpSyncApiClient


class TestSyncEngineClientInit:
    """Test SyncEngineClient initialization."""

    def test_init_with_defaults(self, temp_dir):
        """Test initialization with default parameters."""
        client = SyncEngineClient(temp_dir)

        assert client._target_directory == temp_dir
        assert isinstance(client._file_events, Queue)
        assert client._directory_monitor is not None
        assert client._directory_sync_manager is not None
        assert isinstance(client._stop_event, Event)
        assert client._running is False

    def test_init_with_custom_directory(self, temp_dir):
        """Test initialization with custom directory."""
        custom_dir = temp_dir / "sync_dir"
        custom_dir.mkdir()

        client = SyncEngineClient(custom_dir)

        assert client._target_directory == custom_dir

    def test_init_with_expanded_user_path(self):
        """Test that ~ in path is expanded."""
        client = SyncEngineClient(Path("~/test_sync_dir"))

        assert "~" not in str(client._target_directory)

    def test_init_with_custom_file_events_queue(self, temp_dir):
        """Test initialization with custom file events queue."""
        custom_queue = Queue()
        client = SyncEngineClient(temp_dir, file_events=custom_queue)

        assert client._file_events == custom_queue

    def test_init_with_custom_directory_monitor(self, temp_dir):
        """Test initialization with custom directory monitor."""
        mock_monitor = Mock()
        client = SyncEngineClient(temp_dir, directory_monitor=mock_monitor)

        assert client._directory_monitor == mock_monitor

    def test_init_with_custom_directory_sync_manager(self, temp_dir):
        """Test initialization with custom directory sync manager."""
        mock_manager = Mock()
        client = SyncEngineClient(temp_dir, directory_sync_manager=mock_manager)

        assert client._directory_sync_manager == mock_manager

    def test_init_with_custom_stop_event(self, temp_dir):
        """Test initialization with custom stop event."""
        custom_stop_event = Event()
        client = SyncEngineClient(temp_dir, stop_event=custom_stop_event)

        assert client._stop_event == custom_stop_event

    def test_init_with_custom_api_client(self, temp_dir):
        """Test initialization with custom API client."""
        mock_api_client = Mock(spec=HttpSyncApiClient)
        client = SyncEngineClient(temp_dir, api_client=mock_api_client)

        # API client should be used by the directory sync manager
        assert client._directory_sync_manager is not None

    def test_init_with_custom_server_host_and_port(self, temp_dir):
        """Test initialization with custom server host and port."""
        with patch('sync_engine.client.client.HttpSyncApiClient') as mock_api_factory:
            client = SyncEngineClient(temp_dir, server_host="192.168.1.1", server_port=8080)

            mock_api_factory.assert_called_once_with("192.168.1.1", 8080)


class TestSyncEngineClientIsRunning:
    """Test is_running property."""

    def test_is_running_initial_state(self, temp_dir):
        """Test that is_running is False initially."""
        client = SyncEngineClient(temp_dir)

        assert client.is_running is False

    def test_is_running_after_start(self, temp_dir):
        """Test that is_running is True after start."""
        mock_monitor = Mock()
        mock_monitor.start.return_value = True
        mock_manager = Mock()
        mock_manager.start.return_value = True

        client = SyncEngineClient(temp_dir, directory_monitor=mock_monitor, directory_sync_manager=mock_manager)
        client.start()

        assert client.is_running is True

        # Clean up
        client.stop()

    def test_is_running_after_stop(self, temp_dir):
        """Test that is_running is False after stop."""
        mock_monitor = Mock()
        mock_monitor.start.return_value = True
        mock_manager = Mock()
        mock_manager.start.return_value = True

        client = SyncEngineClient(temp_dir, directory_monitor=mock_monitor, directory_sync_manager=mock_manager)
        client.start()
        client.stop()

        assert client.is_running is False


class TestSyncEngineClientStart:
    """Test start method."""

    def test_start_success(self, temp_dir):
        """Test successful start."""
        mock_monitor = Mock()
        mock_monitor.start.return_value = True
        mock_manager = Mock()
        mock_manager.start.return_value = True

        client = SyncEngineClient(temp_dir, directory_monitor=mock_monitor, directory_sync_manager=mock_manager)
        result = client.start()

        assert result is True
        assert client._running is True
        mock_manager.start.assert_called_once()
        mock_monitor.start.assert_called_once()

        # Clean up
        client.stop()

    def test_start_already_running(self, temp_dir):
        """Test start when already running."""
        mock_monitor = Mock()
        mock_monitor.start.return_value = True
        mock_manager = Mock()
        mock_manager.start.return_value = True

        client = SyncEngineClient(temp_dir, directory_monitor=mock_monitor, directory_sync_manager=mock_manager)
        client.start()

        # Reset mock to check if called again
        mock_monitor.reset_mock()
        mock_manager.reset_mock()

        result = client.start()

        assert result is False
        assert not mock_manager.start.called
        assert not mock_monitor.start.called

        # Clean up
        client.stop()

    def test_start_directory_not_found(self):
        """Test start with non-existent directory."""
        non_existent_dir = Path("/non/existent/directory")
        client = SyncEngineClient(non_existent_dir)

        result = client.start()

        assert result is False
        assert client._running is False

    def test_start_clears_stop_event(self, temp_dir):
        """Test that start clears the stop event."""
        mock_monitor = Mock()
        mock_monitor.start.return_value = True
        mock_manager = Mock()
        mock_manager.start.return_value = True
        stop_event = Event()
        stop_event.set()  # Pre-set the event

        client = SyncEngineClient(
            temp_dir,
            directory_monitor=mock_monitor,
            directory_sync_manager=mock_manager,
            stop_event=stop_event
        )
        client.start()

        assert not stop_event.is_set()

        # Clean up
        client.stop()

    def test_start_sync_manager_fails(self, temp_dir):
        """Test start when sync manager fails to start."""
        mock_monitor = Mock()
        mock_monitor.start.return_value = True
        mock_manager = Mock()
        mock_manager.start.return_value = False

        client = SyncEngineClient(temp_dir, directory_monitor=mock_monitor, directory_sync_manager=mock_manager)
        result = client.start()

        assert result is False
        assert client._running is False
        # Monitor should not be stopped since it wasn't started
        mock_monitor.stop.assert_not_called()

    def test_start_monitor_fails_stops_manager(self, temp_dir):
        """Test that start stops manager if monitor fails."""
        mock_monitor = Mock()
        mock_monitor.start.return_value = False
        mock_manager = Mock()
        mock_manager.start.return_value = True

        client = SyncEngineClient(temp_dir, directory_monitor=mock_monitor, directory_sync_manager=mock_manager)
        result = client.start()

        assert result is False
        assert client._running is False
        mock_manager.stop.assert_called_once()


class TestSyncEngineClientStop:
    """Test stop method."""

    def test_stop_when_running(self, temp_dir):
        """Test stop when client is running."""
        mock_monitor = Mock()
        mock_monitor.start.return_value = True
        mock_manager = Mock()
        mock_manager.start.return_value = True

        client = SyncEngineClient(temp_dir, directory_monitor=mock_monitor, directory_sync_manager=mock_manager)
        client.start()

        client.stop()

        assert client._running is False
        mock_monitor.stop.assert_called_once()
        mock_manager.stop.assert_called_once()

    def test_stop_when_not_running(self, temp_dir):
        """Test stop when client is not running."""
        mock_monitor = Mock()
        mock_manager = Mock()

        client = SyncEngineClient(temp_dir, directory_monitor=mock_monitor, directory_sync_manager=mock_manager)
        client.stop()

        mock_monitor.stop.assert_not_called()
        mock_manager.stop.assert_not_called()

    def test_stop_sets_stop_event(self, temp_dir):
        """Test that stop sets the stop event."""
        mock_monitor = Mock()
        mock_monitor.start.return_value = True
        mock_manager = Mock()
        mock_manager.start.return_value = True
        stop_event = Event()

        client = SyncEngineClient(
            temp_dir,
            directory_monitor=mock_monitor,
            directory_sync_manager=mock_manager,
            stop_event=stop_event
        )
        client.start()
        client.stop()

        assert stop_event.is_set()
