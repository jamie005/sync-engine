"""Shared pytest fixtures for sync-engine tests."""
import pytest
from queue import Queue
from unittest.mock import Mock

from sync_engine.client.synchronisation.directory_sync_manager import _SyncApiClient


@pytest.fixture
def temp_dir(tmp_path):
    """Create a temporary directory for testing."""
    return tmp_path


@pytest.fixture
def sync_event_queue():
    """Create an empty file events queue."""
    return Queue()


@pytest.fixture
def mock_api_client():
    """Create a mock API client."""
    client = Mock(spec=_SyncApiClient)
    client.create_file.return_value = Mock(file_name="test.txt", message="File created")
    client.update_file.return_value = Mock(file_name="test.txt", message="File updated")
    client.delete_file.return_value = Mock(file_name="test.txt", message="File deleted")
    client.rename_file.return_value = Mock(old_file_name="old.txt", new_file_name="new.txt", message="File renamed")
    return client
