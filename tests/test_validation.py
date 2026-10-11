"""
Automated unit tests for File Validation, Sanitization, and Security Boundary checks.
"""
import io
import pytest
from app import app
from config import Config
from azure_storage import sanitize_filename, format_file_size, categorize_file

def test_sanitize_filename_prevents_path_traversal():
    """Verify directory traversal characters like ../ and \\ are safely eliminated."""
    assert sanitize_filename("../../../etc/passwd") == "etc_passwd"
    assert sanitize_filename("..\\..\\windows\\system32\\cmd.exe") == "windows_system32_cmd.exe"
    assert sanitize_filename("safe_report.pdf") == "safe_report.pdf"
    assert sanitize_filename("my presentation (2026).pptx") == "my_presentation_2026.pptx"

def test_sanitize_filename_empty_handling():
    """Verify handling of blank or dangerous inputs."""
    with pytest.raises(ValueError):
        sanitize_filename("")

def test_format_file_size():
    """Test human-readable file size conversion."""
    assert format_file_size(0) == "0 B"
    assert format_file_size(500) == "500 B"
    assert format_file_size(1024) == "1.0 KB"
    assert format_file_size(1024 * 1024) == "1.0 MB"
    assert format_file_size(5 * 1024 * 1024) == "5.0 MB"
    assert format_file_size(1024 * 1024 * 1024) == "1.0 GB"

def test_categorize_file():
    """Verify correct classification of files by extension."""
    assert categorize_file("thesis.pdf") == "document"
    assert categorize_file("spreadsheet.xlsx") == "document"
    assert categorize_file("avatar.png") == "image"
    assert categorize_file("photo.jpg") == "image"
    assert categorize_file("backup.zip") == "archive"
    assert categorize_file("script.py") == "code"
    assert categorize_file("data.json") == "code"
    assert categorize_file("unknown_format.xyz") == "other"

@pytest.fixture
def auth_client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess["username"] = "student"
        yield client

def test_reject_unsupported_file_extension(auth_client):
    """Dangerous executable extensions like .exe, .sh, .bat must be rejected with 400."""
    fake_exe = io.BytesIO(b"MZ executable header")
    response = auth_client.post("/api/upload", data={
        "file": (fake_exe, "malware.exe")
    }, content_type="multipart/form-data")

    assert response.status_code == 400
    json_data = response.get_json()
    assert json_data["success"] is False
    assert "not permitted" in json_data["error"]

def test_reject_empty_zero_byte_file(auth_client):
    """Uploading empty files (0 bytes) must be rejected with 400."""
    empty_file = io.BytesIO(b"")
    response = auth_client.post("/api/upload", data={
        "file": (empty_file, "empty.txt")
    }, content_type="multipart/form-data")

    assert response.status_code == 400
    json_data = response.get_json()
    assert "empty" in json_data["error"]

def test_reject_oversized_file(auth_client):
    """Files exceeding MAX_CONTENT_LENGTH must be rejected with 413."""
    # Temporarily set limit to 1 KB for testing
    original_max = Config.MAX_CONTENT_LENGTH
    Config.MAX_CONTENT_LENGTH = 1024
    try:
        large_payload = io.BytesIO(b"X" * 2048)
        response = auth_client.post("/api/upload", data={
            "file": (large_payload, "oversized.txt")
        }, content_type="multipart/form-data")

        assert response.status_code == 413
        json_data = response.get_json()
        assert json_data["success"] is False
        assert "exceeds" in json_data["error"]
    finally:
        Config.MAX_CONTENT_LENGTH = original_max
