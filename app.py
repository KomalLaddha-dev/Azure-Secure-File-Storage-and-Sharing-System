"""
Azure Secure File Storage and Sharing System
Main Flask Application

Demonstrates:
- Azure App Service deployment on Linux with Gunicorn
- Scalable object storage with Azure Blob Storage SDK v12
- User prefix isolation: <username>/<filename>
- Secure authentication, session management, and CSRF protection
- Comprehensive health monitoring and cloud-native architecture
"""
import os
import mimetypes
from datetime import datetime, timezone
from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    jsonify,
    Response,
    flash,
    stream_with_context
)
from werkzeug.exceptions import RequestEntityTooLarge

from config import Config
from auth import (
    login_required,
    verify_credentials,
    login_user,
    logout_user,
    get_current_user,
    is_authenticated
)
from azure_storage import (
    AzureStorageService,
    StorageNotConfiguredError,
    StorageAuthenticationError,
    FileNotFoundError as AzureBlobNotFoundError,
    StorageError,
    format_file_size,
    categorize_file,
    sanitize_filename
)

# Absolute path to ensure templates and static folders resolve under all WSGI runners
basedir = os.path.abspath(os.path.dirname(__file__))

# Initialize Flask application
app = Flask(
    __name__,
    template_folder=os.path.join(basedir, "templates"),
    static_folder=os.path.join(basedir, "static")
)
app.config.from_object(Config)

# Initialize Azure Storage Service instance
storage = AzureStorageService()


# ==============================================================================
# Template Filters & Context Processors
# ==============================================================================

@app.template_filter("format_bytes")
def filter_format_bytes(size):
    try:
        return format_file_size(int(size))
    except (ValueError, TypeError):
        return "0 B"

@app.template_filter("format_date")
def filter_format_date(iso_str):
    if not iso_str:
        return "Unknown"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return str(iso_str)[:19]

@app.context_processor
def inject_global_context():
    """Injects common user and app state into all templates."""
    return {
        "current_user": get_current_user(),
        "is_authenticated": is_authenticated(),
        "max_size_mb": Config.MAX_CONTENT_LENGTH_MB,
        "allowed_extensions": sorted(list(Config.ALLOWED_EXTENSIONS)),
        "current_year": datetime.now(timezone.utc).year
    }


# ==============================================================================
# Web & Authentication Routes
# ==============================================================================

@app.route("/robots.txt")
@app.route("/robots933456.txt")
def warmup_probe():
    """Responds immediately to Azure warmup probe."""
    return "User-agent: *\nDisallow:", 200, {"Content-Type": "text/plain"}

@app.route("/")
def index():
    """Root route: redirects authenticated users to dashboard, else login."""
    if is_authenticated():
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    """Handles user authentication."""
    if is_authenticated():
        return redirect(url_for("dashboard"))

    demo_users = Config.get_users()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "").strip()

        if not username or not password:
            flash("Please enter both username and password.", "danger")
            return render_template("login.html", demo_users=demo_users, error="Missing credentials")

        if verify_credentials(username, password):
            login_user(username)
            flash(f"Welcome back, {username}! Successfully authenticated.", "success")
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/"):
                return redirect(next_page)
            return redirect(url_for("dashboard"))
        else:
            flash("Invalid username or password. Check demo credentials below.", "danger")
            return render_template("login.html", demo_users=demo_users, error="Invalid credentials")

    return render_template("login.html", demo_users=demo_users)


@app.route("/logout", methods=["GET", "POST"])
def logout():
    """Logs the user out and clears session state."""
    username = get_current_user()
    logout_user()
    flash(f"You have been signed out safely. Have a nice day!", "info")
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    """Protected user dashboard."""
    user = get_current_user()
    health = storage.check_health()
    return render_template(
        "dashboard.html",
        user=user,
        health=health,
        demo_users=list(Config.get_users().keys())
    )


# ==============================================================================
# File Management API Routes (Protected)
# ==============================================================================

@app.route("/api/files", methods=["GET"])
@login_required
def api_list_files():
    """Returns the list of files owned by the authenticated user in Azure Storage."""
    user = get_current_user()
    try:
        files, total_count, total_bytes = storage.list_user_files(user)
        return jsonify({
            "success": True,
            "user": user,
            "files": files,
            "total_count": total_count,
            "total_bytes": total_bytes,
            "total_bytes_formatted": format_file_size(total_bytes)
        })
    except StorageNotConfiguredError as e:
        return jsonify({
            "success": False,
            "error": str(e),
            "files": [],
            "total_count": 0,
            "total_bytes": 0,
            "total_bytes_formatted": "0 B",
            "storage_configured": False
        }), 503
    except StorageAuthenticationError as e:
        return jsonify({
            "success": False,
            "error": "Azure Storage authentication failed. Please verify credentials.",
            "files": [],
            "total_count": 0,
            "total_bytes": 0,
            "total_bytes_formatted": "0 B"
        }), 502
    except StorageError as e:
        return jsonify({
            "success": False,
            "error": f"Azure Storage error: {str(e)}",
            "files": [],
            "total_count": 0,
            "total_bytes": 0,
            "total_bytes_formatted": "0 B"
        }), 500


@app.route("/api/upload", methods=["POST"])
@login_required
def api_upload_file():
    """
    Handles secure file upload to Azure Blob Storage.
    Validates file presence, filename sanitization, extension whitelist, and size.
    """
    user = get_current_user()

    if "file" not in request.files:
        return jsonify({"success": False, "error": "No file part in the request."}), 400

    uploaded_file = request.files["file"]
    raw_filename = uploaded_file.filename

    if not raw_filename or raw_filename.strip() == "":
        return jsonify({"success": False, "error": "No selected file to upload."}), 400

    # Validate file extension
    ext = raw_filename.rsplit(".", 1)[-1].lower() if "." in raw_filename else ""
    if not ext or ext not in Config.ALLOWED_EXTENSIONS:
        allowed_list = ", ".join(sorted(list(Config.ALLOWED_EXTENSIONS))[:10]) + "..."
        return jsonify({
            "success": False,
            "error": f"File type '.{ext}' is not permitted. Allowed extensions include: {allowed_list}"
        }), 400

    # Validate file size via stream inspection
    uploaded_file.seek(0, os.SEEK_END)
    file_size = uploaded_file.tell()
    uploaded_file.seek(0)

    if file_size == 0:
        return jsonify({"success": False, "error": "Cannot upload an empty (0 byte) file."}), 400

    if file_size > Config.MAX_CONTENT_LENGTH:
        return jsonify({
            "success": False,
            "error": f"File exceeds maximum allowed size of {Config.MAX_CONTENT_LENGTH_MB} MB."
        }), 413

    # Upload to Azure Blob Storage under user's prefix
    try:
        file_info = storage.upload_file(
            user_id=user,
            file_stream=uploaded_file.stream,
            filename=raw_filename,
            file_size=file_size
        )
        return jsonify({
            "success": True,
            "message": f"Successfully uploaded '{file_info['filename']}' to Azure Blob Storage.",
            "file": file_info
        }), 201

    except StorageNotConfiguredError as e:
        return jsonify({
            "success": False,
            "error": "Azure Storage connection string is not configured on the server.",
            "details": str(e)
        }), 503
    except StorageAuthenticationError as e:
        return jsonify({
            "success": False,
            "error": "Azure Storage authentication failed. Check Azure access keys."
        }), 502
    except StorageError as e:
        return jsonify({
            "success": False,
            "error": f"Storage upload failed: {str(e)}"
        }), 500
    except Exception as e:
        return jsonify({
            "success": False,
            "error": "An unexpected error occurred while processing the upload."
        }), 500


@app.route("/download/<path:filename>", methods=["GET"])
@login_required
def download_file(filename):
    """
    Streams file securely from Azure Blob Storage directly to authenticated user.
    The browser never receives direct storage keys or private container endpoints.
    """
    user = get_current_user()
    try:
        download_stream, content_type, size, safe_name = storage.download_file(user, filename)

        def generate_chunks():
            for chunk in download_stream.chunks():
                yield chunk

        response = Response(
            stream_with_context(generate_chunks()),
            mimetype=content_type or "application/octet-stream"
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{safe_name}"'
        if size:
            response.headers["Content-Length"] = str(size)
        return response

    except AzureBlobNotFoundError:
        flash(f"File '{filename}' was not found in your Azure storage container.", "danger")
        return redirect(url_for("dashboard"))
    except StorageNotConfiguredError as e:
        flash(str(e), "danger")
        return redirect(url_for("dashboard"))
    except Exception as e:
        flash(f"Failed to download file from Azure: {str(e)}", "danger")
        return redirect(url_for("dashboard"))


@app.route("/preview/<path:filename>", methods=["GET"])
@login_required
def preview_file(filename):
    """
    Streams file inline for browser preview (images, PDF, text).
    """
    user = get_current_user()
    try:
        download_stream, content_type, size, safe_name = storage.download_file(user, filename)

        def generate_chunks():
            for chunk in download_stream.chunks():
                yield chunk

        response = Response(
            stream_with_context(generate_chunks()),
            mimetype=content_type or "application/octet-stream"
        )
        response.headers["Content-Disposition"] = f'inline; filename="{safe_name}"'
        if size:
            response.headers["Content-Length"] = str(size)
        return response

    except AzureBlobNotFoundError:
        return jsonify({"error": "File not found"}), 404
    except Exception as e:
        return jsonify({"error": "Failed to preview file"}), 500


@app.route("/api/delete/<path:filename>", methods=["POST", "DELETE"])
@login_required
def api_delete_file(filename):
    """
    Deletes the file from Azure Blob Storage.
    Strictly verifies that the target file resides under the authenticated user's prefix.
    """
    user = get_current_user()
    try:
        storage.delete_file(user, filename)
        return jsonify({
            "success": True,
            "message": f"File '{filename}' successfully deleted from Azure Blob Storage."
        })
    except AzureBlobNotFoundError:
        return jsonify({"success": False, "error": f"File '{filename}' was not found."}), 404
    except StorageNotConfiguredError as e:
        return jsonify({"success": False, "error": str(e)}), 503
    except StorageError as e:
        return jsonify({"success": False, "error": str(e)}), 500


# ==============================================================================
# Health Check & Cloud Architecture Information Routes
# ==============================================================================

@app.route("/health", methods=["GET"])
def health_check():
    """
    Cloud Health Check & Liveness Probe.
    Inspects application status and Azure Blob Storage connectivity without exposing secrets.
    """
    storage_health = storage.check_health()
    is_healthy = storage_health.get("connected", False)

    status_code = 200 if is_healthy else (503 if not storage.is_configured() else 500)
    
    return jsonify({
        "application": "Azure Secure File Storage and Sharing System",
        "status": "healthy" if is_healthy else "degraded",
        "environment": Config.FLASK_ENV,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "storage": storage_health
    }), status_code


@app.route("/api/cloud-info", methods=["GET"])
@login_required
def api_cloud_info():
    """
    Educational endpoint detailing the cloud computing concepts implemented.
    Ideal for college evaluation, viva discussions, and project architecture reviews.
    """
    health = storage.check_health()
    return jsonify({
        "project_name": "Azure Secure File Storage and Sharing System",
        "hosting": "Azure App Service (Linux PaaS)",
        "web_server": "Gunicorn WSGI / Python Flask",
        "storage_tier": "Azure Blob Storage (Hot Access Tier, Private Container)",
        "isolation_pattern": "Tenant Prefix Partitioning (<user_id>/<blob_name>)",
        "security_features": [
            "Server-Side Secret Isolation via Environment Variables",
            "Timing-Attack Resilient Authentication (HMAC digest comparison)",
            "Path Traversal Prevention via Werkzeug filename sanitization",
            "Streamed Backend Proxying (Zero direct exposure of storage keys)",
            "Private Container Access Policy (No anonymous public read)",
            "HTTP-Only, SameSite Session Cookies"
        ],
        "scalability_aspects": [
            "Stateless Web App Architecture (Scale out to N App Service instances)",
            "Virtually Unlimited Scalable Object Storage (Exabytes capacity)",
            "Chunked Streamed Transfers (Low RAM consumption on server)"
        ],
        "azure_connection_status": health
    })


# ==============================================================================
# Error Handlers
# ==============================================================================

@app.errorhandler(413)
@app.errorhandler(RequestEntityTooLarge)
def handle_large_file(e):
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({
            "success": False,
            "error": f"File is too large. Maximum allowed size is {Config.MAX_CONTENT_LENGTH_MB} MB."
        }), 413
    flash(f"Upload failed: File exceeds the {Config.MAX_CONTENT_LENGTH_MB} MB size limit.", "danger")
    return redirect(url_for("dashboard"))


@app.errorhandler(404)
def handle_not_found(e):
    if request.path.startswith("/api/"):
        return jsonify({"success": False, "error": "Requested API resource not found."}), 404
    try:
        return render_template("404.html"), 404
    except Exception:
        return "<!DOCTYPE html><html><body><h1>404 Not Found</h1><p>The requested page was not found.</p><a href='/'>Go to Home</a></body></html>", 404


@app.errorhandler(500)
def handle_server_error(e):
    if request.path.startswith("/api/"):
        return jsonify({
            "success": False,
            "error": "Internal server error occurred while processing cloud request."
        }), 500
    try:
        return render_template("error.html", error="An internal server error occurred."), 500
    except Exception:
        return "<!DOCTYPE html><html><body><h1>500 Internal Server Error</h1><p>A server error occurred.</p><a href='/'>Go to Home</a></body></html>", 500


# ==============================================================================
# Application Entry Point
# ==============================================================================

if __name__ == "__main__":
    raw_port = os.getenv("PORT") or os.getenv("WEBSITES_PORT") or "5000"
    port = int(raw_port) if str(raw_port).isdigit() else 5000
    debug_mode = (os.getenv("FLASK_ENV") or "development").lower() == "development"
    print(f"[*] Starting Azure Secure File Storage on port {port} (debug={debug_mode})...")
    app.run(host="0.0.0.0", port=port, debug=debug_mode)
