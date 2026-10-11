"""
Automated unit tests for Authentication, Session Management, and Authorization.
"""
import pytest
from app import app
from auth import verify_credentials, login_user, logout_user, is_authenticated, get_current_user

@pytest.fixture
def client():
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key-12345"
    with app.test_client() as client:
        with app.app_context():
            yield client

def test_credential_verification_success():
    """Verify default demo credentials pass authentication check."""
    assert verify_credentials("student", "azurepass123") is True
    assert verify_credentials("faculty", "cloudpass456") is True
    assert verify_credentials("admin", "adminpass789") is True

def test_credential_verification_failure():
    """Verify wrong passwords and non-existent users are rejected."""
    assert verify_credentials("student", "wrongpassword") is False
    assert verify_credentials("unknown_user", "azurepass123") is False
    assert verify_credentials("", "") is False
    assert verify_credentials(None, None) is False

def test_login_flow(client):
    """Test standard web login and session initialization."""
    response = client.post("/login", data={
        "username": "student",
        "password": "azurepass123"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Secure File Storage Dashboard" in response.data

    # Check session inside context
    with client.session_transaction() as sess:
        assert sess.get("username") == "student"

def test_login_invalid_password(client):
    """Test login failure on bad password."""
    response = client.post("/login", data={
        "username": "student",
        "password": "incorrectpassword"
    }, follow_redirects=True)

    assert response.status_code == 200
    assert b"Invalid username or password" in response.data

def test_logout_flow(client):
    """Test user logout clears active session."""
    # First log in
    client.post("/login", data={"username": "student", "password": "azurepass123"})
    
    # Then log out
    response = client.get("/logout", follow_redirects=True)
    assert response.status_code == 200
    assert b"Sign In" in response.data

    with client.session_transaction() as sess:
        assert "username" not in sess

def test_unauthenticated_access_redirection(client):
    """Unauthenticated requests to protected pages must redirect to /login."""
    response = client.get("/dashboard", follow_redirects=False)
    assert response.status_code == 302
    assert "/login" in response.headers["Location"]

def test_unauthenticated_api_access_denial(client):
    """Unauthenticated API requests must return JSON 401 Unauthorized."""
    response = client.get("/api/files", headers={"Accept": "application/json"})
    assert response.status_code == 401
    json_data = response.get_json()
    assert json_data["authenticated"] is False
    assert "Unauthorized" in json_data["error"]
