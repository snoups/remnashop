from typing import Optional, Union

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.dependencies.public import forbid_cabinet_proxy
from app.api.dependencies.rate_limit import rate_limit
from app.api.errors import ApiError, error_responses
from app.core.config import AppConfig
from app.core.constants import TIME_1M, TTL_15M
from app.core.enums import SessionAudience
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.utils.http import is_cabinet_proxied, resolve_client_ip
from app.modules.auth.api.schemas import (
    BootstrapRequest,
    LoginRequest,
    RefreshResponse,
    StatusResponse,
)
from app.modules.auth.session_cookies import (
    SESSION_COOKIES,
    clear_audience_cookies,
    presented_refresh_tokens,
    set_audience_cookies,
)
from app.modules.auth.session_response import (
    AuthResponse,
    set_session_cookies,
    to_auth_response,
    verify_csrf,
)
from app.modules.auth.usecases import (
    BootstrapOwnerUseCase,
    GetAuthStatusUseCase,
    LoginUseCase,
    LogoutUseCase,
    RefreshSessionUseCase,
)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get(
    "/status",
    response_model=StatusResponse,
    dependencies=[
        Depends(forbid_cabinet_proxy),
        Depends(rate_limit(key="status", limit=30, window_seconds=TIME_1M)),
    ],
    responses=error_responses(403),
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
    dependencies=[
        Depends(forbid_cabinet_proxy),
        Depends(rate_limit(key="bootstrap", limit=5, window_seconds=TIME_1M)),
    ],
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

    set_session_cookies(response, issued, config.secure_cookies)
    return to_auth_response(owner, issued.access_token)


@router.post(
    "/login",
    response_model=AuthResponse,
    dependencies=[
        Depends(forbid_cabinet_proxy),
        Depends(rate_limit(key="login", limit=10, window_seconds=TIME_1M)),
    ],
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

    set_session_cookies(response, issued, config.secure_cookies)
    return to_auth_response(user, issued.access_token)


def _refresh_cookie_for(request: Request) -> Optional[tuple[SessionAudience, str]]:
    """The refresh cookie of the audience this host serves: the cabinet's through its
    proxy, the dashboard's otherwise. A second one (tossed in from a sibling
    subdomain) is ignored rather than breaking the real session's refresh."""
    presented = dict(presented_refresh_tokens(request))
    if len(presented) <= 1:
        return next(iter(presented.items()), None)
    audience = SessionAudience.CABINET if is_cabinet_proxied(request) else SessionAudience.DASHBOARD
    return audience, presented[audience]


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    dependencies=[Depends(rate_limit(key="refresh", limit=30, window_seconds=TIME_1M))],
    responses=error_responses(401, 403),
)
@inject
async def refresh_session(
    request: Request,
    response: Response,
    use_case: FromDishka[RefreshSessionUseCase],
    config: FromDishka[AppConfig],
) -> Union[RefreshResponse, JSONResponse]:
    chosen = _refresh_cookie_for(request)
    if chosen is None:
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED, "No refresh token", code=ErrorCode.REFRESH_TOKEN_MISSING
        )
    audience, refresh_token = chosen
    if audience is SessionAudience.DASHBOARD:
        forbid_cabinet_proxy(request)
    verify_csrf(
        refresh_token,
        request,
        config.jwt_secret.get_secret_value(),
        csrf_cookie=SESSION_COOKIES[audience].csrf,
    )

    try:
        issued = await use_case.execute(
            refresh_token=refresh_token,
            ip_address=resolve_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            audience=audience,
        )
    except AuthenticationError as error:
        error_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(error), "code": error.code.value},
        )
        clear_audience_cookies(error_response, audience)
        return error_response

    set_audience_cookies(response, issued, config.secure_cookies, audience)
    return RefreshResponse(access_token=issued.access_token, expires_in=TTL_15M)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit(key="logout", limit=30, window_seconds=TIME_1M))],
    responses=error_responses(403),
)
@inject
async def logout(
    request: Request,
    response: Response,
    use_case: FromDishka[LogoutUseCase],
    config: FromDishka[AppConfig],
) -> None:
    chosen = _refresh_cookie_for(request)
    if chosen is not None:
        audience, refresh_token = chosen
        verify_csrf(
            refresh_token,
            request,
            config.jwt_secret.get_secret_value(),
            csrf_cookie=SESSION_COOKIES[audience].csrf,
        )
        try:
            await use_case.execute(refresh_token=refresh_token, audience=audience)
        except Exception:
            # the browser is signed out regardless; the session row lives out its TTL
            logger.exception("Logout could not revoke the session; cookies cleared anyway")
    # both: a cookie of the other audience has no business on this host
    for audience in SESSION_COOKIES:
        clear_audience_cookies(response, audience)
