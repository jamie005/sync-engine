"""Tests for HttpSyncApiClient."""
import pytest
from unittest.mock import Mock
import requests

from sync_engine.client.synchronisation.api_client import HttpSyncApiClient, SyncApiClientError
from sync_engine.common.schemas import (
    CreateFileRequest,
    UpdateFileRequest,
    DeleteFileRequest,
    RenameFileRequest,
)


class TestHttpSyncApiClient:
    """Test HttpSyncApiClient."""

    def test_init(self):
        """Test client initialization."""
        client = HttpSyncApiClient("localhost", 5000)
        assert client._base_url == "http://localhost:5000"
        assert client._timeout_seconds == 5.0

    def test_init_custom_timeout(self):
        """Test initialization with custom timeout."""
        client = HttpSyncApiClient("localhost", 5000, timeout_seconds=15.0)
        assert client._timeout_seconds == 15.0

    def test_create_file(self):
        """Test file creation."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "file_name": "test.txt",
            "message": "File created"
        }
        mock_sender = Mock(return_value=mock_response)

        client = HttpSyncApiClient("localhost", 5000, request_sender=mock_sender)
        request = CreateFileRequest(file_name="test.txt", file_hash="abc123", content="test")
        response = client.create_file(request)

        assert response.file_name == "test.txt"

    def test_update_file(self):
        """Test file update."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "file_name": "test.txt",
            "message": "File updated"
        }
        mock_sender = Mock(return_value=mock_response)

        client = HttpSyncApiClient("localhost", 5000, request_sender=mock_sender)
        request = UpdateFileRequest(file_name="test.txt", file_hash="def456", content="updated")
        response = client.update_file(request)

        assert response.file_name == "test.txt"

    def test_delete_file(self):
        """Test file deletion."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "file_name": "test.txt",
            "message": "File deleted"
        }
        mock_sender = Mock(return_value=mock_response)

        client = HttpSyncApiClient("localhost", 5000, request_sender=mock_sender)
        request = DeleteFileRequest(file_name="test.txt")
        response = client.delete_file(request)

        assert response.file_name == "test.txt"

    def test_rename_file(self):
        """Test file rename."""
        mock_response = Mock()
        mock_response.json.return_value = {
            "old_file_name": "old.txt",
            "new_file_name": "new.txt",
            "message": "File renamed"
        }
        mock_sender = Mock(return_value=mock_response)

        client = HttpSyncApiClient("localhost", 5000, request_sender=mock_sender)
        request = RenameFileRequest(old_file_name="old.txt", new_file_name="new.txt")
        response = client.rename_file(request)

        assert response.old_file_name == "old.txt"

    def test_http_error(self):
        """Test HTTP error handling."""
        mock_response = Mock()
        mock_response.status_code = 400
        mock_response.json.return_value = {"error": "Invalid request"}
        mock_http_error = requests.exceptions.HTTPError()
        mock_http_error.response = mock_response
        mock_sender = Mock(side_effect=mock_http_error)

        client = HttpSyncApiClient("localhost", 5000, request_sender=mock_sender)
        request = CreateFileRequest(file_name="test.txt", file_hash="abc123", content="test")

        with pytest.raises(SyncApiClientError) as exc_info:
            client.create_file(request)

        assert exc_info.value.status_code == 400

    def test_connection_error(self):
        """Test connection error handling."""
        mock_sender = Mock(side_effect=requests.exceptions.ConnectionError("Connection failed"))

        client = HttpSyncApiClient("localhost", 5000, request_sender=mock_sender)
        request = CreateFileRequest(file_name="test.txt", file_hash="abc123", content="test")

        with pytest.raises(SyncApiClientError):
            client.create_file(request)
