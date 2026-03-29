"""Custom exceptions for SFE."""


class SFEException(Exception):
    """Base exception for all SFE errors."""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}


class FragmentNotFoundError(SFEException):
    """Raised when a fragment is not found."""

    def __init__(self, fragment_id: str):
        super().__init__(
            message=f"Fragment not found: {fragment_id}",
            details={"fragment_id": fragment_id}
        )


class ValidationError(SFEException):
    """Raised when validation fails."""

    def __init__(self, message: str, fragment_id: str | None = None):
        super().__init__(
            message=message,
            details={"fragment_id": fragment_id} if fragment_id else {}
        )


class StorageError(SFEException):
    """Raised when storage operations fail."""

    def __init__(self, message: str, operation: str | None = None):
        super().__init__(
            message=message,
            details={"operation": operation} if operation else {}
        )


class RetrievalError(SFEException):
    """Raised when retrieval operations fail."""

    def __init__(self, message: str, query: str | None = None):
        super().__init__(
            message=message,
            details={"query": query} if query else {}
        )


class EmbeddingError(SFEException):
    """Raised when embedding operations fail."""

    def __init__(self, message: str, model: str | None = None):
        super().__init__(
            message=message,
            details={"model": model} if model else {}
        )


class LLMError(SFEException):
    """Raised when LLM operations fail."""

    def __init__(self, message: str, model: str | None = None, status_code: int | None = None):
        super().__init__(
            message=message,
            details={
                "model": model,
                "status_code": status_code
            }
        )


class AdaptationError(SFEException):
    """Raised when adaptation fails."""

    def __init__(self, message: str, fragment_id: str | None = None):
        super().__init__(
            message=message,
            details={"fragment_id": fragment_id} if fragment_id else {}
        )


class GovernanceError(SFEException):
    """Raised when governance operations fail."""

    def __init__(self, message: str, operation: str | None = None):
        super().__init__(
            message=message,
            details={"operation": operation} if operation else {}
        )


class ConfigurationError(SFEException):
    """Raised when configuration is invalid."""

    def __init__(self, message: str, config_key: str | None = None):
        super().__init__(
            message=message,
            details={"config_key": config_key} if config_key else {}
        )


class PrivacyViolationError(SFEException):
    """Raised when sensitive data is detected."""

    def __init__(self, message: str, detected_pattern: str | None = None):
        super().__init__(
            message=message,
            details={"detected_pattern": detected_pattern} if detected_pattern else {}
        )
