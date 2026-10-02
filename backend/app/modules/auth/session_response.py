from fastapi import Response
from pydantic import BaseModel

from app.core.constants import CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH
from app.core.utils.time import datetime_now
from app.modules.auth.session_issuer import IssuedSession
from app.modules.users import UserDto


class AuthResponse(BaseModel):
    id: int
    login: str
    role: str
    access_token: str


def set_session_cookies(response: Response, issued: IssuedSession, secure: bool) -> None:
    max_age = int((issued.expires_at - datetime_now()).total_seconds())
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        issued.refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=max_age,
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        issued.csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=max_age,
    )


def to_auth_response(user: UserDto, access_token: str) -> AuthResponse:
    # every sign-in flow (bootstrap, login, OAuth, passkey) only succeeds for a user with a login
    assert user.login is not None
    return AuthResponse(
        id=user.id, login=user.login, role=str(user.role), access_token=access_token
    )
