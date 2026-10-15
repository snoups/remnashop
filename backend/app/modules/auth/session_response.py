import hmac
from typing import Literal

from fastapi import Request, Response
from pydantic import BaseModel

from app.core.constants import CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import PermissionDeniedError
from app.core.security import derive_csrf_token
from app.core.utils.time import datetime_now
from app.modules.auth.session_issuer import IssuedSession
from app.modules.users import UserDto


class AuthResponse(BaseModel):
    id: int
    login: str
    role: Role
    access_token: str


def set_session_cookies(
    response: Response,
    issued: IssuedSession,
    secure: bool,
    *,
    refresh_cookie: str = REFRESH_COOKIE_NAME,
    refresh_path: str = REFRESH_COOKIE_PATH,
    csrf_cookie: str = CSRF_COOKIE_NAME,
    samesite: Literal["lax", "strict"] = "lax",
) -> None:
    max_age = int((issued.expires_at - datetime_now()).total_seconds())
    response.set_cookie(
        refresh_cookie,
        issued.refresh_token,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path=refresh_path,
        max_age=max_age,
    )
    response.set_cookie(
        csrf_cookie,
        issued.csrf_token,
        httponly=False,
        secure=secure,
        samesite=samesite,
        path="/",
        max_age=max_age,
    )


def verify_csrf(
    refresh_token: str, request: Request, jwt_secret: str, csrf_cookie: str = CSRF_COOKIE_NAME
) -> None:
    # both must equal the signed value, not just each other (see
    # derive_csrf_token in core/security/session_token.py)
    cookie_value = request.cookies.get(csrf_cookie)
    header_value = request.headers.get("x-csrf-token")
    expected = derive_csrf_token(refresh_token, jwt_secret)
    if (
        not cookie_value
        or not header_value
        or not hmac.compare_digest(cookie_value, expected)
        or not hmac.compare_digest(header_value, expected)
    ):
        raise PermissionDeniedError("CSRF check failed", code=ErrorCode.CSRF_FAILED)


def to_auth_response(user: UserDto, access_token: str) -> AuthResponse:
    # every sign-in flow (bootstrap, login, OAuth, passkey) only succeeds for a user with a login
    assert user.login is not None
    return AuthResponse(id=user.id, login=user.login, role=user.role, access_token=access_token)
