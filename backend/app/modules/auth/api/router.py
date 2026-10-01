import hmac

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies.rate_limit import rate_limit
from app.api.errors import ApiError, error_responses
from app.core.config import AppConfig
from app.core.constants import CSRF_COOKIE_NAME, REFRESH_COOKIE_NAME, REFRESH_COOKIE_PATH, TIME_1M
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.security import derive_csrf_token
from app.core.utils.http import resolve_client_ip
from app.core.utils.time import datetime_now
from app.modules.auth import (
    BootstrapOwnerUseCase,
    GetAuthStatusUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
)
from app.modules.auth.api.schemas import (
    AuthResponse,
    BootstrapRequest,
    LoginRequest,
    RefreshResponse,
    StatusResponse,
)
from app.modules.auth.session_issuer import IssuedSession
from app.modules.users import UserDto

router = APIRouter(prefix="/auth", tags=["auth"])


def _set_session_cookies(response: Response, issued: "IssuedSession", secure: bool) -> None:
    response.set_cookie(
        REFRESH_COOKIE_NAME,
        issued.refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=int((issued.expires_at - datetime_now()).total_seconds()),
    )
    response.set_cookie(
        CSRF_COOKIE_NAME,
        issued.csrf_token,
        httponly=False,
        secure=secure,
        samesite="lax",
        path="/",
        max_age=int((issued.expires_at - datetime_now()).total_seconds()),
    )


def _clear_session_cookies(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)
    response.delete_cookie(CSRF_COOKIE_NAME, path="/")


def _verify_csrf(refresh_token: str, request: Request, jwt_secret: str) -> None:
    # Signed double-submit cookie (core/security/session_token.py's
    # derive_csrf_token): both the cookie and the header must equal
    # HMAC(secret, refresh_token), not just equal each other -- a plain
    # cookie==header check alone is only safe if an attacker can never plant
    # a cookie for this domain on the victim (sibling-subdomain cookie
    # tossing, a misconfigured related app, ...); signing closes that gap.
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get("x-csrf-token")
    expected = derive_csrf_token(refresh_token, jwt_secret)
    if (
        not cookie_value
        or not header_value
        or not hmac.compare_digest(cookie_value, expected)
        or not hmac.compare_digest(header_value, expected)
    ):
        raise ApiError(status.HTTP_403_FORBIDDEN, "CSRF check failed", code=ErrorCode.CSRF_FAILED)


def _to_auth_response(user: UserDto, access_token: str) -> AuthResponse:
    # All three auth flows below only ever reach here with a user that has a login
    # (bootstrap always sets it; login/OAuth-login only succeed for users that have one).
    assert user.login is not None
    return AuthResponse(
        id=user.id, login=user.login, role=str(user.role), access_token=access_token
    )


@router.get(
    "/status",
    response_model=StatusResponse,
    dependencies=[Depends(rate_limit(key="status", limit=30, window_seconds=TIME_1M))],
)
@inject
async def get_auth_status(use_case: FromDishka[GetAuthStatusUseCase]) -> StatusResponse:
    result = await use_case.execute()
    return StatusResponse(
        is_login_allowed=result.owner_exists,
        is_register_allowed=not result.owner_exists,
        oauth_providers={
            provider.value.lower(): enabled for provider, enabled in result.oauth_providers.items()
        },
        oidc_display_name=result.oidc_display_name,
        is_password_login_enabled=result.password_login_enabled,
        is_passkey_login_enabled=result.is_passkey_login_enabled,
    )


@router.post(
    "/bootstrap",
    response_model=AuthResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(rate_limit(key="bootstrap", limit=5, window_seconds=TIME_1M))],
    responses=error_responses(409),
)
@inject
async def bootstrap(
    payload: BootstrapRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[BootstrapOwnerUseCase],
    config: FromDishka[AppConfig],
) -> AuthResponse:
    owner, issued = await use_case.execute(
        login=payload.login,
        password=payload.password,
        client_ip=resolve_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    _set_session_cookies(response, issued, config.secure_cookies)
    return _to_auth_response(owner, issued.access_token)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit(key="login", limit=10, window_seconds=TIME_1M))],
    responses=error_responses(401),
)
@inject
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[LoginUseCase],
    config: FromDishka[AppConfig],
) -> AuthResponse:
    user, issued = await use_case.execute(
        login=payload.login,
        password=payload.password,
        client_ip=resolve_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    _set_session_cookies(response, issued, config.secure_cookies)
    return _to_auth_response(user, issued.access_token)


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    dependencies=[Depends(rate_limit(key="refresh", limit=30, window_seconds=TIME_1M))],
    responses=error_responses(401),
)
@inject
async def refresh_session(
    request: Request,
    response: Response,
    use_case: FromDishka[RefreshSessionUseCase],
    config: FromDishka[AppConfig],
) -> RefreshResponse | JSONResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED, "No refresh token", code=ErrorCode.REFRESH_TOKEN_MISSING
        )
    _verify_csrf(refresh_token, request, config.jwt_secret.get_secret_value())

    try:
        issued = await use_case.execute(
            refresh_token=refresh_token,
            ip_address=resolve_client_ip(request),
            user_agent=request.headers.get("user-agent"),
        )
    except AuthenticationError as error:
        error_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED, content={"detail": str(error)}
        )
        _clear_session_cookies(error_response)
        return error_response

    _set_session_cookies(response, issued, config.secure_cookies)
    return RefreshResponse(access_token=issued.access_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit(key="logout", limit=30, window_seconds=TIME_1M))],
)
@inject
async def logout(
    request: Request,
    response: Response,
    use_case: FromDishka[LogoutUseCase],
    config: FromDishka[AppConfig],
) -> None:
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        _verify_csrf(refresh_token, request, config.jwt_secret.get_secret_value())
        await use_case.execute(refresh_token=refresh_token)
    _clear_session_cookies(response)
