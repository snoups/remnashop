from typing import Final

from fastapi import Response

from app.core.constants import API_V1, CABINET_API_PREFIX, TTL_5M, TTL_10M
from app.modules.auth import IssuedSession, set_session_cookies

CABINET_REFRESH_COOKIE: Final[str] = "cabinet_refresh_token"
CABINET_CSRF_COOKIE: Final[str] = "cabinet_csrf_token"
CABINET_REFRESH_PATH: Final[str] = f"{API_V1}{CABINET_API_PREFIX}/auth"
CABINET_WEBAUTH_COOKIE: Final[str] = "cabinet_webauth"
CABINET_OAUTH_COOKIE: Final[str] = "cabinet_oauth"


def set_cabinet_cookies(response: Response, issued: IssuedSession, secure: bool) -> None:
    set_session_cookies(
        response,
        issued,
        secure,
        refresh_cookie=CABINET_REFRESH_COOKIE,
        refresh_path=CABINET_REFRESH_PATH,
        csrf_cookie=CABINET_CSRF_COOKIE,
        samesite="strict",
    )


def clear_cabinet_cookies(response: Response) -> None:
    response.delete_cookie(CABINET_REFRESH_COOKIE, path=CABINET_REFRESH_PATH)
    response.delete_cookie(CABINET_CSRF_COOKIE, path="/")


def set_webauth_cookie(response: Response, binding: str, secure: bool) -> None:
    response.set_cookie(
        CABINET_WEBAUTH_COOKIE,
        binding,
        max_age=TTL_5M,
        httponly=True,
        secure=secure,
        samesite="strict",
        path=CABINET_REFRESH_PATH,
    )


def set_oauth_cookie(response: Response, binding: str, secure: bool) -> None:
    response.set_cookie(
        CABINET_OAUTH_COOKIE,
        binding,
        max_age=TTL_10M,
        httponly=True,
        secure=secure,
        samesite="strict",
        path=CABINET_REFRESH_PATH,
    )
