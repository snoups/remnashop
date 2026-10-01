from typing import Final

from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import JSONResponse
from starlette.status import HTTP_413_CONTENT_TOO_LARGE
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.core.constants import API_V1
from app.core.error_codes import ErrorCode

# Bodies are read before any dependency runs (FastAPI parses forms and JSON
# ahead of authentication), so without a cap here an anonymous caller could
# stream an unbounded upload into a temp file or memory.
_DEFAULT_BODY_LIMIT: Final[int] = 1024 * 1024
# image uploads: the largest per-route file cap (banners, 5 MB) plus multipart framing
_UPLOAD_BODY_LIMIT: Final[int] = 6 * 1024 * 1024
_UPLOAD_PATHS: Final[frozenset[str]] = frozenset(
    {
        f"{API_V1}/settings/appearance/logo",
        f"{API_V1}/settings/appearance/favicon",
    }
)
# PUT /banners/{name}/{locale}
_BANNER_UPLOAD_PREFIX: Final[str] = f"{API_V1}/banners/"

# setdefault, not overwrite: a route with a stricter policy of its own (the
# public appearance images) keeps it.
_SECURITY_HEADERS: Final[tuple[tuple[str, str], ...]] = (
    ("Content-Security-Policy", "frame-ancestors 'none'"),
    ("X-Frame-Options", "DENY"),
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "same-origin"),
)


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in _SECURITY_HEADERS:
                    headers.setdefault(name, value)
            await send(message)

        await self.app(scope, receive, send_with_headers)


def _too_large() -> JSONResponse:
    return JSONResponse(
        status_code=HTTP_413_CONTENT_TOO_LARGE,
        content={"detail": "Request body too large", "code": ErrorCode.PAYLOAD_TOO_LARGE},
    )


def _is_upload(scope: Scope) -> bool:
    path: str = scope["path"]
    return scope["method"] == "PUT" and (
        path in _UPLOAD_PATHS or path.startswith(_BANNER_UPLOAD_PREFIX)
    )


class BodySizeLimitMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        limit = _UPLOAD_BODY_LIMIT if _is_upload(scope) else _DEFAULT_BODY_LIMIT
        declared = dict(scope["headers"]).get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > limit:
            await _too_large()(scope, receive, send)
            return

        # chunked bodies carry no Content-Length, so the stream itself is counted
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    raise HTTPException(status_code=HTTP_413_CONTENT_TOO_LARGE)
            return message

        await self.app(scope, limited_receive, send)
