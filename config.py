"""
Configuration module for Azure Secure File Storage and Sharing System.
Reads and validates environment variables.
"""
import os
import json
from dotenv import load_dotenv

# Load variables from .env file if present
load_dotenv()

class Config:
    # Flask Session Secret Key
    SECRET_KEY = os.getenv("SECRET_KEY") or "dev-insecure-key-change-in-production-azure-cclab"

    # Environment
    FLASK_ENV = os.getenv("FLASK_ENV") or "development"
    IS_PRODUCTION = FLASK_ENV.lower() == "production"

    # Azure Blob Storage Configuration
    AZURE_STORAGE_CONNECTION_STRING = (os.getenv("AZURE_STORAGE_CONNECTION_STRING") or "").strip()
    AZURE_STORAGE_CONTAINER_NAME = (os.getenv("AZURE_STORAGE_CONTAINER_NAME") or "secure-files-container").strip()

    # Upload Size Limits (Default: 25 MB)
    raw_mb = os.getenv("MAX_CONTENT_LENGTH_MB") or "25"
    try:
        MAX_CONTENT_LENGTH_MB = int(raw_mb.strip()) if str(raw_mb).strip().isdigit() else 25
    except Exception:
        MAX_CONTENT_LENGTH_MB = 25
    MAX_CONTENT_LENGTH = MAX_CONTENT_LENGTH_MB * 1024 * 1024

    # Whitelist of allowed extensions for security
    ALLOWED_EXTENSIONS = {
        # Documents
        "pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "md", "rtf",
        # Images
        "png", "jpg", "jpeg", "gif", "webp", "svg", "bmp",
        # Archives
        "zip", "rar", "7z", "tar", "gz",
        # Code & Data
        "py", "json", "js", "html", "css", "xml", "sql", "sh"
    }

    # Session Cookie Security Flags
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = IS_PRODUCTION or os.getenv("FORCE_HTTPS", "false").lower() == "true"
    PERMANENT_SESSION_LIFETIME = 3600 * 4  # 4 hours

    # User Accounts
    # Can be configured via APP_USERS JSON or individual fallback env vars
    @staticmethod
    def get_users():
        demo_defaults = {
            "student": "azurepass123",
            "faculty": "cloudpass456",
            "admin": "adminpass789"
        }
        raw_users = os.getenv("APP_USERS", "")
        if raw_users:
            try:
                users = json.loads(raw_users)
                if isinstance(users, dict) and users:
                    demo_defaults.update(users)
                    return demo_defaults
            except Exception:
                pass
        
        default_user = os.getenv("DEFAULT_USERNAME", "student")
        default_pass = os.getenv("DEFAULT_PASSWORD", "azurepass123")
        demo_defaults[default_user] = default_pass
        return demo_defaults
