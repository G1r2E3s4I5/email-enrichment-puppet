"""CSV Upload File Storage Service."""

import os
import time
from typing import Optional
from uuid import uuid4
from app.config.logging import logger
from app.config.settings import settings
from app.core.exceptions import ConfigurationException, ValidationException


class CSVUploadService:
    """Service handling disk persistence of uploaded CSV files into writable application directory."""

    def __init__(self, upload_dir: Optional[str] = None) -> None:
        """Initialize upload service with target directory."""
        if upload_dir:
            self._upload_dir = upload_dir
        elif getattr(settings, "UPLOAD_DIR", None) and settings.UPLOAD_DIR.strip():
            self._upload_dir = settings.UPLOAD_DIR
        else:
            # Resolve to backend root directory (/app in Docker container, or <workspace>/backend locally)
            backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            workspace_uploads = os.path.abspath(os.path.join(backend_dir, "..", "uploads"))

            # Use workspace root uploads if it exists and is writable (and not root /uploads), otherwise backend_dir/uploads (/app/uploads in Docker)
            if os.path.exists(workspace_uploads) and os.access(workspace_uploads, os.W_OK) and workspace_uploads != "/uploads":
                self._upload_dir = workspace_uploads
            else:
                self._upload_dir = os.path.join(backend_dir, "uploads")

        os.makedirs(self._upload_dir, exist_ok=True)

    @property
    def upload_dir(self) -> str:
        """Return resolved upload directory path."""
        return self._upload_dir

    def store_file(self, content: bytes, original_filename: str) -> str:
        """Save file bytes to uploads directory with unique stored filename."""
        if not content:
            raise ValidationException("Cannot save empty file payload")

        # Generate unique stored filename: <uuid>_<timestamp>_<clean_filename>
        sanitized_filename = "".join(c for c in original_filename if c.isalnum() or c in (".", "_", "-")).strip()
        if not sanitized_filename:
            sanitized_filename = "upload.csv"

        file_uuid = uuid4()
        timestamp = int(time.time())
        stored_filename = f"{file_uuid}_{timestamp}_{sanitized_filename}"
        target_path = os.path.join(self._upload_dir, stored_filename)

        try:
            with open(target_path, "wb") as f:
                f.write(content)

            logger.info(f"Saved uploaded file '{original_filename}' -> '{target_path}' ({len(content)} bytes)")
            return stored_filename
        except Exception as exc:
            logger.error(f"Failed to write uploaded file to disk '{target_path}': {str(exc)}")
            raise ConfigurationException(
                message=f"Failed to save file to uploads storage: {str(exc)}",
                details={"target_path": target_path},
            ) from exc
