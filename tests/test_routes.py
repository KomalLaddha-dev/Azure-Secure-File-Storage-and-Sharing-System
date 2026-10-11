"""
Automated integration tests for Flask Web and REST API routes.
"""
import io
from unittest.mock import patch, MagicMock
import pytest
from app import app

@pytest.fixture
def auth_client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "integration-testing-key"
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["username"] = "student"
        yield client

def test_health_endpoint(auth_client):
    """Health check endpoint should always respond with 200/503 and valid JSON."""
    response = auth_client.get("/health")
    assert response.status_code in [200, 503]
    data = response.get_json()
    assert "application" in data
    assert "storage" in data

def test_cloud_info_endpoint(auth_client):
    """Educational viva endpoint should return cloud architecture details."""
    response = auth_client.get("/api/cloud-info")
    assert response.status_code == 200
    data = response.get_json()
    assert "Azure App Service" in data["hosting"]
    assert "Azure Blob Storage" in data["storage_tier"]
    assert len(data["security_features"]) > 0

def test_api_upload_success(auth_client):
    """Verify successful upload route when Azure storage is active."""
    sample_pdf = io.BytesIO(b"%PDF-1.4 simulated pdf document data")
    
    mock_file_info = {
        "filename": "assignment1.pdf",
        "blob_path": "student/assignment1.pdf",
        "size": 36,
        "size_formatted": "36 B",
        "content_type": "application/pdf",
        "category": "document",
        "uploaded_at": "2026-10-11T12:00:00Z"
    }

    with patch("app.storage.upload_file", return_value=mock_file_info):
        response = auth_client.post("/api/upload", data={
            "file": (sample_pdf, "assignment1.pdf")
        }, content_type="multipart/form-data")

        assert response.status_code == 201
        data = response.get_json()
        assert data["success"] is True
        assert data["file"]["filename"] == "assignment1.pdf"

def test_api_list_files(auth_client):
    """Verify /api/files returns user-isolated files list."""
    mock_files = [
        {
            "filename": "data.csv",
            "blob_path": "student/data.csv",
            "size": 2048,
            "size_formatted": "2.0 KB",
            "last_modified": "2026-10-11T12:00:00Z",
            "content_type": "text/csv",
            "category": "document",
            "extension": "csv"
        }
    ]

    with patch("app.storage.list_user_files", return_value=(mock_files, 1, 2048)):
        response = auth_client.get("/api/files")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert data["total_count"] == 1
        assert data["files"][0]["filename"] == "data.csv"

def test_download_file_stream(auth_client):
    """Verify /download/<filename> streams file content with attachment header."""
    mock_stream = MagicMock()
    mock_stream.chunks.return_value = [b"Chunk 1 ", b"Chunk 2"]

    with patch("app.storage.download_file", return_value=(mock_stream, "text/plain", 15, "notes.txt")):
        response = auth_client.get("/download/notes.txt")
        assert response.status_code == 200
        assert b"Chunk 1 Chunk 2" in response.data
        assert 'attachment; filename="notes.txt"' in response.headers["Content-Disposition"]

def test_api_delete_file(auth_client):
    """Verify /api/delete/<filename> deletes file and returns success confirmation."""
    with patch("app.storage.delete_file", return_value=True):
        response = auth_client.post("/api/delete/old_draft.docx")
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True
        assert "deleted" in data["message"].lower()
