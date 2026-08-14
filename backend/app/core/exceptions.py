"""Custom exception hierarchy for Email Enrichment Tool."""

from typing import Any, Dict, Optional


class BaseAppException(Exception):
    """Base exception for all application-specific domain errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.details = details or {}


class ValidationException(BaseAppException):
    """Raised when request payload or data validation fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, status_code=400, details=details)


class ConfigurationException(BaseAppException):
    """Raised when environment or settings configuration is invalid."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, status_code=500, details=details)


class ProviderException(BaseAppException):
    """Raised when an external enrichment/verification provider encounters an error."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, status_code=502, details=details)


class DatabaseException(BaseAppException):
    """Raised when database operation or connection fails."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, status_code=500, details=details)


class EntityNotFoundException(BaseAppException):
    """Raised when requested entity is missing in the database."""

    def __init__(self, message: str = "Requested resource not found", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, status_code=404, details=details)


class DuplicateRecordException(BaseAppException):
    """Raised when inserting duplicate record violating unique constraint."""

    def __init__(self, message: str = "Record already exists", details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, status_code=409, details=details)


class APIException(BaseAppException):
    """Generic API exception wrapper for unhandled operational errors."""

    def __init__(self, message: str, status_code: int = 500, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message=message, status_code=status_code, details=details)

