from dataclasses import dataclass
from typing import Final, Literal

from fastapi import Request, Response

from app.core.constants import CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH, TTL_10M
from app.core.enums import SessionAudience
from app.modules.auth.session_issuer import IssuedSession
from app.modules.auth.session_response import set_session_cookies


@dataclass(frozen=True, kw_only=True)
class SessionCookies:
    refresh: str
    csrf: str
    samesite: Literal["lax", "strict"]


# One refresh path for both: the cabinet's nginx rewrites it to its own /api/auth,
# so a browser never sends one audience's cookie with the other's requests.
SESSION_COOKIES: Final[dict[SessionAudience, SessionCookies]] = {
    SessionAudience.DASHBOARD: SessionCookies(
        refresh=REFRESH_COOKIE_NAME, csrf=CSRF_COOKIE_NAME, samesite="lax"
    ),
    # strict: the cabinet only ever calls its own origin
    SessionAudience.CABINET: SessionCookies(
        refresh="cabinet_refresh_token", csrf="cabinet_csrf_token", samesite="strict"
    ),
}

OAUTH_BINDING_COOKIE: Final[str] = "oauth_binding"


def set_audience_cookies(
    response: Response, issued: IssuedSession, secure: bool, audience: SessionAudience
) -> None:
    cookies = SESSION_COOKIES[audience]
    set_session_cookies(
        response,
        issued,
        secure,
        refresh_cookie=cookies.refresh,
        refresh_path=REFRESH_COOKIE_PATH,
        csrf_cookie=cookies.csrf,
        samesite=cookies.samesite,
    )


def clear_audience_cookies(response: Response, audience: SessionAudience) -> None:
    cookies = SESSION_COOKIES[audience]
    response.delete_cookie(cookies.refresh, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(cookies.csrf, path="/")


def presented_refresh_tokens(request: Request) -> list[tuple[SessionAudience, str]]:
    return [
        (audience, token)
        for audience, cookies in SESSION_COOKIES.items()
        if (token := request.cookies.get(cookies.refresh))
    ]


def set_oauth_binding_cookie(
    response: Response,
    binding: str,
    secure: bool,
    audience: SessionAudience,
    path: str = REFRESH_COOKIE_PATH,
) -> None:
    response.set_cookie(
        OAUTH_BINDING_COOKIE,
        binding,
        max_age=TTL_10M,
        httponly=True,
        secure=secure,
        samesite=SESSION_COOKIES[audience].samesite,
        path=path,
    )


def clear_oauth_binding_cookie(response: Response, path: str = REFRESH_COOKIE_PATH) -> None:
    response.delete_cookie(OAUTH_BINDING_COOKIE, path=path)
