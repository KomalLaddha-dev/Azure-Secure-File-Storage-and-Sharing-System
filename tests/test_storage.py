"""
Automated unit tests for Azure Storage Service and Multi-User Prefix Isolation.
Uses unittest.mock to simulate Azure Blob Storage SDK interactions.
"""
import io
from unittest.mock import MagicMock, patch
import pytest
from azure_storage import (
    AzureStorageService,
    StorageNotConfiguredError,
    FileNotFoundError as BlobNotFoundError
)

def test_storage_service_unconfigured():
    """Verify that an unconfigured service raises clear exception and never silently falls back."""
    service = AzureStorageService(connection_string="", container_name="")
    assert service.is_configured() is False

    health = service.check_health()
    assert health["connected"] is False
    assert health["status"] == "unconfigured"

    with pytest.raises(StorageNotConfiguredError):
        service.upload_file("student", io.BytesIO(b"data"), "test.txt", 4)

def test_health_check_masks_credentials():
    """Verify health check masks account name and does not expose connection keys."""
    conn_str = "DefaultEndpointsProtocol=https;AccountName=cclabstorageacct;AccountKey=SuperSecretKey123456789;EndpointSuffix=core.windows.net"
    service = AzureStorageService(connection_string=conn_str, container_name="secure-container")

    with patch.object(service, "_get_container_client") as mock_get_container:
        mock_container = MagicMock()
        mock_container.exists.return_value = True
        mock_get_container.return_value = mock_container

        health = service.check_health()
        assert health["connected"] is True
        assert health["status"] == "healthy"
        assert "SuperSecretKey" not in str(health)
        assert "ccl***ct" in health["account_name"]

def test_upload_file_enforces_user_prefix():
    """Verify blob is uploaded strictly under user prefix: <user_id>/<filename>."""
    conn_str = "DefaultEndpointsProtocol=https;AccountName=cclabstorage;AccountKey=dGVzdGtleQ==;EndpointSuffix=core.windows.net"
    service = AzureStorageService(connection_string=conn_str, container_name="secure-container")

    mock_blob_client = MagicMock()
    mock_container = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client

    with patch.object(service, "_get_container_client", return_value=mock_container):
        result = service.upload_file(
            user_id="student",
            file_stream=io.BytesIO(b"Hello Azure"),
            filename="report.pdf",
            file_size=11
        )

        # Check path passed to container.get_blob_client
        mock_container.get_blob_client.assert_called_with("student/report.pdf")
        assert result["filename"] == "report.pdf"
        assert result["blob_path"] == "student/report.pdf"
        assert mock_blob_client.upload_blob.called

def test_list_files_filters_by_user_prefix():
    """Verify list_user_files queries only blobs starting with the specified user prefix."""
    conn_str = "DefaultEndpointsProtocol=https;AccountName=cclabstorage;AccountKey=dGVzdGtleQ==;EndpointSuffix=core.windows.net"
    service = AzureStorageService(connection_string=conn_str, container_name="secure-container")

    # Mock Azure Blob item
    mock_blob = MagicMock()
    mock_blob.name = "student/notes.txt"
    mock_blob.size = 1024
    mock_blob.last_modified = None
    mock_blob.content_settings.content_type = "text/plain"
    mock_blob.metadata = {"uploader": "student"}

    mock_container = MagicMock()
    mock_container.list_blobs.return_value = [mock_blob]

    with patch.object(service, "_get_container_client", return_value=mock_container):
        files, count, total_bytes = service.list_user_files("student")

        mock_container.list_blobs.assert_called_with(name_starts_with="student/", include=["metadata"])
        assert count == 1
        assert total_bytes == 1024
        assert files[0]["filename"] == "notes.txt"
        assert files[0]["category"] == "document"

def test_delete_file_user_isolation():
    """Verify file deletion targets strictly user's prefix."""
    conn_str = "DefaultEndpointsProtocol=https;AccountName=cclabstorage;AccountKey=dGVzdGtleQ==;EndpointSuffix=core.windows.net"
    service = AzureStorageService(connection_string=conn_str, container_name="secure-container")

    mock_blob_client = MagicMock()
    mock_blob_client.exists.return_value = True
    mock_container = MagicMock()
    mock_container.get_blob_client.return_value = mock_blob_client

    with patch.object(service, "_get_container_client", return_value=mock_container):
        res = service.delete_file("faculty", "exam_questions.docx")
        
        mock_container.get_blob_client.assert_called_with("faculty/exam_questions.docx")
        assert mock_blob_client.delete_blob.called
        assert res is True
