"""
Authentication helper and session management module.
Protects routes, verifies credentials, and manages user sessions.
"""
import hmac
from functools import wraps
from datetime import datetime, timezone
from flask import session, redirect, url_for, request, jsonify, flash
from config import Config

def get_current_user():
    """Returns the authenticated username from the session or None."""
    return session.get("username")

def is_authenticated():
    """Checks whether the current request is from an authenticated user."""
    return "username" in session and bool(session.get("username"))

def verify_credentials(username, password):
    """
    Validates username and password against configured users.
    Uses constant-time comparison to prevent timing attack side-channels.
    """
    if not username or not password:
        return False
    
    users = Config.get_users()
    expected_password = users.get(username.strip())
    if not expected_password:
        return False
    
    return hmac.compare_digest(str(expected_password), str(password))

def login_user(username):
    """Establishes a user session upon successful authentication."""
    session.clear()
    session["username"] = username.strip()
    session["login_time"] = datetime.now(timezone.utc).isoformat()
    session.permanent = True

def logout_user():
    """Clears the user session."""
    session.clear()

def login_required(f):
    """
    Decorator for endpoints requiring user authentication.
    Returns JSON 401 for API/AJAX requests or redirects to login for HTML pages.
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not is_authenticated():
            # Check if this is an API or AJAX request
            is_api = (
                request.path.startswith("/api/")
                or request.is_json
                or request.headers.get("X-Requested-With") == "XMLHttpRequest"
                or "application/json" in request.headers.get("Accept", "")
            )
            if is_api:
                return jsonify({
                    "success": False,
                    "error": "Unauthorized. Please log in to access this resource.",
                    "authenticated": False
                }), 401
            
            flash("Please sign in to access your secure files.", "warning")
            return redirect(url_for("login", next=request.path))
        return f(*args, **kwargs)
    return decorated_function
