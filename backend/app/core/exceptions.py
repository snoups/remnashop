from datetime import datetime

from app.core.error_codes import ErrorCode


class AppError(Exception):
    def __init__(self, message: str, *, code: ErrorCode) -> None:
        super().__init__(message)
        self.code = code


class PermissionDeniedError(AppError):
    def __init__(
        self, message: str = "Permission denied", *, code: ErrorCode = ErrorCode.PERMISSION_DENIED
    ) -> None:
        super().__init__(message, code=code)


class ConflictError(AppError): ...


class AuthenticationError(AppError): ...


class NotFoundError(AppError): ...


class ValidationError(AppError): ...


class CooldownError(AppError):
    def __init__(self, available_at: datetime) -> None:
        self.available_at = available_at
        super().__init__(f"Cooldown active until {available_at}", code=ErrorCode.COOLDOWN_ACTIVE)


class RetryableTaskError(Exception):
    """A worker task failed before any side effect left the process, so the
    broker may run it again (SmartRetryMiddleware in app/core/broker.py)."""


class RemnawavePanelUnavailableError(AppError):
    def __init__(self, message: str, *, code: ErrorCode = ErrorCode.REMNAWAVE_UNAVAILABLE) -> None:
        super().__init__(message, code=code)


class PaymentGatewayError(AppError):
    def __init__(self, message: str, *, code: ErrorCode = ErrorCode.PAYMENT_GATEWAY_ERROR) -> None:
        super().__init__(message, code=code)
