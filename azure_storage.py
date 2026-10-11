"""
Azure Blob Storage integration module for Secure File Storage and Sharing System.
Provides a clean, modular abstraction over the Azure Storage Blob SDK (v12).
Enforces user prefix isolation: <username>/<filename>.
Does NOT substitute local storage when Azure is unconfigured.
"""
import os
import re
import mimetypes
from datetime import datetime, timezone
from werkzeug.utils import secure_filename
from azure.core.exceptions import (
    ResourceNotFoundError,
    ResourceExistsError,
    AzureError,
    ClientAuthenticationError
)
from azure.storage.blob import BlobServiceClient, ContentSettings
from config import Config

class StorageError(Exception):
    """Base exception for Azure Storage operations."""
    pass

class StorageNotConfiguredError(StorageError):
    """Raised when Azure Storage connection string or container name is missing."""
    pass

class StorageAuthenticationError(StorageError):
    """Raised when credentials or connection string are invalid."""
    pass

class FileNotFoundError(StorageError):
    """Raised when a requested blob is not found."""
    pass

def sanitize_filename(filename: str) -> str:
    """
    Sanitizes filename and prevents directory traversal attacks.
    Removes path characters and limits to safe alphanumeric and permitted symbols.
    """
    if not filename:
        raise ValueError("Filename cannot be empty")
    
    # Use werkzeug secure_filename as the first defense line
    clean_name = secure_filename(filename)
    # Strip any potential residual traversal patterns
    clean_name = re.sub(r'[\/\\:\*\?"<>\|\x00]', '_', clean_name).strip()
    
    if not clean_name:
        clean_name = f"file_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
        
    return clean_name

def format_file_size(bytes_size: int) -> str:
    """Formats file size into human-readable B, KB, MB, GB format."""
    if not bytes_size or bytes_size < 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    size = float(bytes_size)
    unit_index = 0
    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1
    return f"{size:.1f} {units[unit_index]}" if unit_index > 0 else f"{int(size)} {units[unit_index]}"

def categorize_file(filename: str) -> str:
    """Categorizes file into document, image, archive, code, or other based on extension."""
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext in {"pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "csv", "md", "rtf"}:
        return "document"
    elif ext in {"png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"}:
        return "image"
    elif ext in {"zip", "rar", "7z", "tar", "gz"}:
        return "archive"
    elif ext in {"py", "json", "js", "html", "css", "xml", "sql", "sh"}:
        return "code"
    return "other"


class AzureStorageService:
    """
    Service class managing all interactions with Microsoft Azure Blob Storage.
    Stateless per-request helper with lazy-loaded client initialization.
    """

    def __init__(self, connection_string=None, container_name=None):
        self.connection_string = (connection_string or Config.AZURE_STORAGE_CONNECTION_STRING).strip()
        self.container_name = (container_name or Config.AZURE_STORAGE_CONTAINER_NAME).strip()
        self._blob_service_client = None
        self._container_client = None

    def is_configured(self) -> bool:
        """Checks if connection string and container name are populated."""
        return bool(self.connection_string and self.container_name and "DefaultEndpointsProtocol" in self.connection_string)

    def _get_blob_service_client(self):
        """Initializes or returns cached BlobServiceClient."""
        if not self.is_configured():
            raise StorageNotConfiguredError(
                "Azure Storage is not configured. Please set the AZURE_STORAGE_CONNECTION_STRING "
                "environment variable in your .env file or Azure App Service Application Settings."
            )
        if self._blob_service_client is None:
            try:
                self._blob_service_client = BlobServiceClient.from_connection_string(
                    self.connection_string
                )
            except Exception as e:
                raise StorageAuthenticationError(f"Failed to initialize Azure Blob Service Client: {str(e)}")
        return self._blob_service_client

    def _get_container_client(self):
        """Returns the ContainerClient and verifies/creates the private container."""
        if self._container_client is None:
            service = self._get_blob_service_client()
            container = service.get_container_client(self.container_name)
            # Create container if it does not exist (Private access tier by default)
            try:
                if not container.exists():
                    container.create_container()
            except ResourceExistsError:
                pass
            except ClientAuthenticationError as e:
                raise StorageAuthenticationError(f"Azure authentication failed: {str(e)}")
            except Exception as e:
                # If checking existence fails due to permissions or network, continue and let operation fail
                pass
            self._container_client = container
        return self._container_client

    def check_health(self) -> dict:
        """
        Tests connectivity to Azure Blob Storage without revealing keys or credentials.
        Returns a sanitized health status dictionary.
        """
        if not self.is_configured():
            return {
                "connected": False,
                "status": "unconfigured",
                "message": "AZURE_STORAGE_CONNECTION_STRING environment variable is not set.",
                "container": self.container_name or "Not configured",
                "account_name": "Not configured"
            }
        
        # Extract masked account name
        account_name_match = re.search(r"AccountName=([^;]+)", self.connection_string)
        raw_account = account_name_match.group(1) if account_name_match else "unknown"
        masked_account = raw_account[:3] + "***" + raw_account[-2:] if len(raw_account) > 5 else "configured"

        try:
            container = self._get_container_client()
            # Perform a lightweight ping operation: check container existence
            exists = container.exists()
            return {
                "connected": True,
                "status": "healthy",
                "message": "Connected successfully to Azure Blob Storage.",
                "container": self.container_name,
                "container_exists": exists,
                "account_name": masked_account,
                "sdk_version": "12.30.0"
            }
        except ClientAuthenticationError:
            return {
                "connected": False,
                "status": "authentication_error",
                "message": "Invalid Azure Storage credentials or access key.",
                "container": self.container_name,
                "account_name": masked_account
            }
        except Exception as e:
            return {
                "connected": False,
                "status": "error",
                "message": f"Storage connection failed: {type(e).__name__}",
                "container": self.container_name,
                "account_name": masked_account
            }

    def upload_file(self, user_id: str, file_stream, filename: str, file_size: int = None) -> dict:
        """
        Uploads a file to Azure Blob Storage under the user's isolated prefix: <user_id>/<filename>.
        Attaches metadata and sets appropriate Content-Type.
        """
        if not user_id:
            raise ValueError("user_id is required for isolated storage")
        
        safe_name = sanitize_filename(filename)
        blob_path = f"{user_id}/{safe_name}"

        # Detect content mime type
        mime_type, _ = mimetypes.guess_type(safe_name)
        if not mime_type:
            mime_type = "application/octet-stream"

        content_settings = ContentSettings(content_type=mime_type)
        upload_time = datetime.now(timezone.utc).isoformat()
        
        metadata = {
            "uploader": str(user_id),
            "original_filename": safe_name,
            "uploaded_at": upload_time,
            "file_size": str(file_size or 0)
        }

        try:
            container = self._get_container_client()
            blob_client = container.get_blob_client(blob_path)
            
            # Reset stream position if possible
            if hasattr(file_stream, "seek"):
                file_stream.seek(0)

            blob_client.upload_blob(
                file_stream,
                overwrite=True,
                content_settings=content_settings,
                metadata=metadata
            )

            actual_size = file_size if file_size is not None else 0
            return {
                "filename": safe_name,
                "blob_path": blob_path,
                "size": actual_size,
                "size_formatted": format_file_size(actual_size),
                "content_type": mime_type,
                "category": categorize_file(safe_name),
                "uploaded_at": upload_time
            }
        except AzureError as e:
            raise StorageError(f"Azure Blob upload failed: {str(e)}")

    def list_user_files(self, user_id: str) -> tuple[list, int, int]:
        """
        Lists all blobs belonging exclusively to the specified user: <user_id>/*
        Returns: (files_list, total_file_count, total_bytes_used)
        """
        if not user_id:
            raise ValueError("user_id is required")

        prefix = f"{user_id}/"
        files = []
        total_bytes = 0

        try:
            container = self._get_container_client()
            blobs = container.list_blobs(name_starts_with=prefix, include=["metadata"])

            for blob in blobs:
                # Strip user_id prefix to get relative filename
                raw_name = blob.name[len(prefix):] if blob.name.startswith(prefix) else blob.name
                # Skip any potential empty prefix markers
                if not raw_name:
                    continue
                
                size = blob.size or 0
                total_bytes += size

                # Parse last modified timestamp
                last_modified_iso = (
                    blob.last_modified.isoformat()
                    if blob.last_modified
                    else datetime.now(timezone.utc).isoformat()
                )

                content_type = (
                    blob.content_settings.content_type
                    if blob.content_settings and blob.content_settings.content_type
                    else mimetypes.guess_type(raw_name)[0] or "application/octet-stream"
                )

                files.append({
                    "filename": raw_name,
                    "blob_path": blob.name,
                    "size": size,
                    "size_formatted": format_file_size(size),
                    "last_modified": last_modified_iso,
                    "content_type": content_type,
                    "category": categorize_file(raw_name),
                    "extension": raw_name.rsplit(".", 1)[-1].lower() if "." in raw_name else "",
                    "metadata": blob.metadata or {}
                })

            # Sort files newest first by default
            files.sort(key=lambda x: x.get("last_modified", ""), reverse=True)
            return files, len(files), total_bytes

        except AzureError as e:
            raise StorageError(f"Failed to list files from Azure Storage: {str(e)}")

    def download_file(self, user_id: str, filename: str):
        """
        Streams a blob belonging to user_id.
        Verifies blob exists and returns (stream_or_bytes, content_type, size, filename).
        """
        safe_name = sanitize_filename(filename)
        blob_path = f"{user_id}/{safe_name}"

        try:
            container = self._get_container_client()
            blob_client = container.get_blob_client(blob_path)

            if not blob_client.exists():
                raise FileNotFoundError(f"File '{safe_name}' does not exist in Azure Storage.")

            props = blob_client.get_blob_properties()
            download_stream = blob_client.download_blob()

            content_type = (
                props.content_settings.content_type
                if props.content_settings and props.content_settings.content_type
                else "application/octet-stream"
            )

            return download_stream, content_type, props.size, safe_name

        except ResourceNotFoundError:
            raise FileNotFoundError(f"File '{safe_name}' was not found in storage container.")
        except AzureError as e:
            raise StorageError(f"Azure download failed: {str(e)}")

    def delete_file(self, user_id: str, filename: str) -> bool:
        """
        Deletes a blob belonging to user_id.
        Verifies that user only deletes their own file prefix.
        """
        safe_name = sanitize_filename(filename)
        blob_path = f"{user_id}/{safe_name}"

        try:
            container = self._get_container_client()
            blob_client = container.get_blob_client(blob_path)

            if not blob_client.exists():
                raise FileNotFoundError(f"File '{safe_name}' does not exist or has already been deleted.")

            blob_client.delete_blob()
            return True

        except ResourceNotFoundError:
            raise FileNotFoundError(f"File '{safe_name}' not found.")
        except AzureError as e:
            raise StorageError(f"Azure delete failed: {str(e)}")
