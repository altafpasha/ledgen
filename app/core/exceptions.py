from typing import Any, Dict, Optional
from fastapi import HTTPException, status


class AppException(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundException(AppException):
    def __init__(self, resource: str, identifier: Any):
        super().__init__(
            code="RESOURCE_NOT_FOUND",
            message=f"{resource} with identifier '{identifier}' was not found.",
            status_code=status.HTTP_404_NOT_FOUND,
        )


class AuthenticationException(AppException):
    def __init__(self, message: str = "Invalid credentials or token."):
        super().__init__(
            code="AUTHENTICATION_FAILED",
            message=message,
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


class PermissionDeniedException(AppException):
    def __init__(self, message: str = "Permission denied."):
        super().__init__(
            code="PERMISSION_DENIED",
            message=message,
            status_code=status.HTTP_403_FORBIDDEN,
        )


class RateLimitException(AppException):
    def __init__(self, message: str = "Rate limit exceeded. Please try again later."):
        super().__init__(
            code="RATE_LIMIT_EXCEEDED",
            message=message,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        )


class ProviderException(AppException):
    def __init__(self, provider: str, message: str, code: str = "PROVIDER_ERROR"):
        super().__init__(
            code=code,
            message=f"[{provider.upper()}] {message}",
            status_code=status.HTTP_502_BAD_GATEWAY,
        )


class BudgetExceededException(AppException):
    def __init__(self, budget_type: str, limit: Any):
        super().__init__(
            code="BUDGET_LIMIT_REACHED",
            message=f"Budget limit reached for {budget_type} (limit: {limit}). Campaign paused.",
            status_code=status.HTTP_400_BAD_REQUEST,
        )


class SSRFSecurityException(AppException):
    def __init__(self, message: str = "Destination IP / Host blocked by SSRF protection."):
        super().__init__(
            code="SSRF_BLOCKED",
            message=message,
            status_code=status.HTTP_400_BAD_REQUEST,
        )
