from http import HTTPStatus
from typing import Any, Callable, Final, Optional

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.dependencies.models import Dependant
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from loguru import logger
from pydantic import BaseModel
from sqlalchemy.exc import DBAPIError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_codes import ErrorCode
from app.core.exceptions import (
    AppError,
    AuthenticationError,
    ConflictError,
    CooldownError,
    NotFoundError,
    PaymentGatewayError,
    PermissionDeniedError,
    RemnawavePanelUnavailableError,
    ValidationError,
)

_STATUS_BY_ERROR: Final[dict[type[AppError], int]] = {
    ValidationError: status.HTTP_400_BAD_REQUEST,
    AuthenticationError: status.HTTP_401_UNAUTHORIZED,
    PermissionDeniedError: status.HTTP_403_FORBIDDEN,
    NotFoundError: status.HTTP_404_NOT_FOUND,
    ConflictError: status.HTTP_409_CONFLICT,
    CooldownError: status.HTTP_429_TOO_MANY_REQUESTS,
    PaymentGatewayError: status.HTTP_502_BAD_GATEWAY,
    RemnawavePanelUnavailableError: status.HTTP_503_SERVICE_UNAVAILABLE,
}

# for HTTPExceptions raised without a code (framework 404/405, third-party code)
_CODE_BY_STATUS: Final[dict[int, ErrorCode]] = {
    status.HTTP_401_UNAUTHORIZED: ErrorCode.NOT_AUTHENTICATED,
    status.HTTP_403_FORBIDDEN: ErrorCode.PERMISSION_DENIED,
    status.HTTP_404_NOT_FOUND: ErrorCode.NOT_FOUND,
    status.HTTP_405_METHOD_NOT_ALLOWED: ErrorCode.METHOD_NOT_ALLOWED,
    status.HTTP_413_CONTENT_TOO_LARGE: ErrorCode.PAYLOAD_TOO_LARGE,
    status.HTTP_429_TOO_MANY_REQUESTS: ErrorCode.RATE_LIMITED,
}

# internal breaker state is not something to show a client
_REMNAWAVE_UNAVAILABLE_DETAIL: Final[str] = "Remnawave panel is temporarily unavailable"


class ErrorResponse(BaseModel):
    detail: str
    code: ErrorCode


class RequestInvalidResponse(BaseModel):
    detail: list[dict[str, Any]]
    code: ErrorCode


class ApiError(HTTPException):
    """An HTTP error raised by the API layer itself, with no domain exception behind it."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        *,
        code: ErrorCode,
        headers: Optional[dict[str, str]] = None,
    ) -> None:
        super().__init__(status_code=status_code, detail=detail, headers=headers)
        self.code = code


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    return {
        status_code: {"model": ErrorResponse, "description": HTTPStatus(status_code).phrase}
        for status_code in status_codes
    }


# every route sits behind request validation and the global rate limiter
GLOBAL_ERROR_RESPONSES: Final[dict[int | str, dict[str, Any]]] = {
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": RequestInvalidResponse,
        "description": "Request validation failed",
    },
    # BodySizeLimitMiddleware caps every request body
    **error_responses(status.HTTP_413_CONTENT_TOO_LARGE, status.HTTP_429_TOO_MANY_REQUESTS),
}


def _depends_on(dependant: Dependant, call: Callable[..., Any]) -> bool:
    return any(sub.call is call or _depends_on(sub, call) for sub in dependant.dependencies)


def document_auth_errors(app: FastAPI, auth_dependency: Callable[..., Any]) -> None:
    # derived from the real dependency tree, so a new router can't forget them
    for route in app.routes:
        if isinstance(route, APIRoute) and _depends_on(route.dependant, auth_dependency):
            for status_code, response in error_responses(
                status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN
            ).items():
                route.responses.setdefault(status_code, response)


_NUMERIC_OUT_OF_RANGE: Final[str] = "22003"


def _is_out_of_range(error: DBAPIError) -> bool:
    # asyncpg refuses an oversized bind parameter itself (an OverflowError under
    # its DataError); Postgres answers an overflowing expression with 22003
    candidate: Optional[BaseException] = error
    seen: set[int] = set()
    while candidate is not None and id(candidate) not in seen:
        seen.add(id(candidate))
        if isinstance(candidate, OverflowError):
            return True
        if getattr(candidate, "sqlstate", None) == _NUMERIC_OUT_OF_RANGE:
            return True
        candidate = getattr(candidate, "orig", None) or candidate.__cause__
    return False


def status_for(error: AppError) -> int:
    for error_type in type(error).__mro__:
        if error_type in _STATUS_BY_ERROR:
            return _STATUS_BY_ERROR[error_type]
    return status.HTTP_500_INTERNAL_SERVER_ERROR


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, error: AppError) -> JSONResponse:
        detail = (
            _REMNAWAVE_UNAVAILABLE_DETAIL
            if isinstance(error, RemnawavePanelUnavailableError)
            else str(error)
        )
        return JSONResponse(
            status_code=status_for(error), content={"detail": detail, "code": error.code}
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(_: Request, error: StarletteHTTPException) -> JSONResponse:
        code = getattr(error, "code", None) or _CODE_BY_STATUS.get(
            error.status_code, ErrorCode.HTTP_ERROR
        )
        return JSONResponse(
            status_code=error.status_code,
            content={"detail": error.detail, "code": code},
            headers=getattr(error, "headers", None),
        )

    # Starlette re-raises after sending this, so the traceback still reaches the log
    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, error: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error", "code": ErrorCode.INTERNAL_ERROR},
        )

    @app.exception_handler(DBAPIError)
    async def database_error_handler(_: Request, error: DBAPIError) -> JSONResponse:
        # an int past the int32 columns' range gets through request validation;
        # Postgres refusing it is the caller's mistake, anything else is ours
        if not _is_out_of_range(error):
            raise error
        logger.warning(f"Rejected a request with a number out of range: {error.orig}")
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": "A number is out of range", "code": ErrorCode.REQUEST_INVALID},
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_handler(_: Request, error: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content={"detail": jsonable_encoder(error.errors()), "code": ErrorCode.REQUEST_INVALID},
        )
