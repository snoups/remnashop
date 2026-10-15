from typing import Final

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies.rate_limit import (
    FailureLimit,
    cookie_rate_limit,
    failure_rate_limit,
    rate_limit,
)
from app.api.errors import ApiError, error_responses, status_for
from app.core.config import AppConfig
from app.core.constants import CABINET_API_PREFIX, TIME_1M, TTL_15M
from app.core.enums import OAuthProvider, SessionAudience
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, AuthenticationError
from app.core.utils.http import resolve_client_ip
from app.modules.auth import LogoutUseCase, RefreshSessionUseCase, verify_csrf
from app.modules.cabinet_auth.api.schemas import (
    CabinetAuthResponse,
    CabinetMethodsResponse,
    CabinetOAuthAuthorizeResponse,
    CabinetOAuthCallbackRequest,
    DeeplinkResponse,
    InviteCodesRequest,
    RequestEmailCodeRequest,
    TelegramWebAppLoginRequest,
    VerifyEmailCodeRequest,
)
from app.modules.cabinet_auth.cookies import (
    CABINET_CSRF_COOKIE,
    CABINET_OAUTH_COOKIE,
    CABINET_REFRESH_COOKIE,
    CABINET_REFRESH_PATH,
    CABINET_WEBAUTH_COOKIE,
    clear_cabinet_cookies,
    set_cabinet_cookies,
    set_oauth_cookie,
    set_webauth_cookie,
)
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.cabinet_auth.usecases import (
    CabinetOAuthAuthorizeUseCase,
    CabinetOAuthCallbackUseCase,
    GetCabinetMethodsUseCase,
    PollDeeplinkUseCase,
    RequestDeeplinkUseCase,
    RequestEmailCodeUseCase,
    TelegramWebAppLoginUseCase,
    VerifyEmailCodeUseCase,
)

_TELEGRAM_FAILURES: Final[frozenset[ErrorCode]] = frozenset({ErrorCode.INVALID_INIT_DATA})
_EMAIL_VERIFY_FAILURES: Final[frozenset[ErrorCode]] = frozenset(
    {ErrorCode.EMAIL_CODE_INVALID, ErrorCode.EMAIL_CODE_EXPIRED}
)
_OAUTH_CALLBACK_FAILURES: Final[frozenset[ErrorCode]] = frozenset(
    {ErrorCode.OAUTH_STATE_INVALID, ErrorCode.OAUTH_CODE_EXCHANGE_FAILED}
)

router = APIRouter(prefix=f"{CABINET_API_PREFIX}/auth", tags=["cabinet-auth"])


@router.get(
    "/methods",
    response_model=CabinetMethodsResponse,
)
@inject
async def get_cabinet_methods(
    use_case: FromDishka[GetCabinetMethodsUseCase],
) -> CabinetMethodsResponse:
    methods = await use_case.execute()
    return CabinetMethodsResponse.model_validate(methods, from_attributes=True)


@router.post(
    "/telegram",
    response_model=CabinetAuthResponse,
    responses=error_responses(401, 403),
)
@inject
async def cabinet_telegram_login(
    body: TelegramWebAppLoginRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[TelegramWebAppLoginUseCase],
    config: FromDishka[AppConfig],
    guard: FailureLimit = Depends(
        failure_rate_limit(key="cabinet_telegram_fail", limit=20, window_seconds=TIME_1M)
    ),
) -> CabinetAuthResponse:
    try:
        _, issued = await use_case.execute(
            body.init_data, resolve_client_ip(request), request.headers.get("user-agent")
        )
    except AppError as error:
        if error.code in _TELEGRAM_FAILURES:
            await guard.record_failure()
        raise
    set_cabinet_cookies(response, issued, config.secure_cookies)
    return CabinetAuthResponse(access_token=issued.access_token, expires_in=TTL_15M)


@router.post(
    "/email/code",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit(key="cabinet_email_code", limit=30, window_seconds=TIME_1M))],
    responses=error_responses(401),
)
@inject
async def cabinet_email_code(
    body: RequestEmailCodeRequest, use_case: FromDishka[RequestEmailCodeUseCase]
) -> None:
    await use_case.execute(
        body.email, body.locale, InviteCodesDto(referral_code=body.ref, ad_link_code=body.ad)
    )


@router.post(
    "/email/verify",
    response_model=CabinetAuthResponse,
    responses=error_responses(401, 403),
)
@inject
async def cabinet_email_verify(
    body: VerifyEmailCodeRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[VerifyEmailCodeUseCase],
    config: FromDishka[AppConfig],
    guard: FailureLimit = Depends(
        failure_rate_limit(key="cabinet_email_verify_fail", limit=20, window_seconds=TIME_1M)
    ),
) -> CabinetAuthResponse:
    try:
        _, issued = await use_case.execute(
            body.email, body.code, resolve_client_ip(request), request.headers.get("user-agent")
        )
    except AppError as error:
        if error.code in _EMAIL_VERIFY_FAILURES:
            await guard.record_failure()
        raise
    set_cabinet_cookies(response, issued, config.secure_cookies)
    return CabinetAuthResponse(access_token=issued.access_token, expires_in=TTL_15M)


@router.post(
    "/telegram/deeplink",
    response_model=DeeplinkResponse,
    dependencies=[
        Depends(rate_limit(key="cabinet_telegram_deeplink", limit=20, window_seconds=TIME_1M))
    ],
    responses=error_responses(401),
)
@inject
async def cabinet_telegram_deeplink(
    body: InviteCodesRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[RequestDeeplinkUseCase],
    config: FromDishka[AppConfig],
) -> DeeplinkResponse:
    ticket = await use_case.execute(
        InviteCodesDto(referral_code=body.ref, ad_link_code=body.ad),
        resolve_client_ip(request),
        request.headers.get("user-agent"),
    )
    set_webauth_cookie(response, ticket.binding, config.secure_cookies)
    return DeeplinkResponse(bot_url=ticket.bot_url, expires_in=ticket.expires_in)


@router.post(
    "/telegram/deeplink/poll",
    response_model=CabinetAuthResponse,
    responses={
        **error_responses(401, 403),
        status.HTTP_202_ACCEPTED: {"description": "Not confirmed yet"},
    },
    dependencies=[
        Depends(
            cookie_rate_limit(
                key="cabinet_deeplink_poll",
                cookie=CABINET_WEBAUTH_COOKIE,
                limit=60,
                window_seconds=TIME_1M,
            )
        )
    ],
)
@inject
async def cabinet_telegram_deeplink_poll(
    request: Request,
    response: Response,
    use_case: FromDishka[PollDeeplinkUseCase],
    config: FromDishka[AppConfig],
    guard: FailureLimit = Depends(
        failure_rate_limit(key="cabinet_deeplink_poll_fail", limit=20, window_seconds=TIME_1M)
    ),
) -> CabinetAuthResponse | JSONResponse:
    binding = request.cookies.get(CABINET_WEBAUTH_COOKIE)
    if not binding:
        await guard.record_failure()
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED,
            "The sign-in link has expired",
            code=ErrorCode.DEEPLINK_EXPIRED,
        )
    signed_in = await use_case.execute(
        binding, resolve_client_ip(request), request.headers.get("user-agent")
    )
    if signed_in is None:
        return JSONResponse(status_code=status.HTTP_202_ACCEPTED, content={"status": "pending"})
    _, issued = signed_in
    set_cabinet_cookies(response, issued, config.secure_cookies)
    response.delete_cookie(CABINET_WEBAUTH_COOKIE, path=CABINET_REFRESH_PATH)
    return CabinetAuthResponse(access_token=issued.access_token, expires_in=TTL_15M)


@router.post(
    "/oauth/{provider}/authorize",
    response_model=CabinetOAuthAuthorizeResponse,
    dependencies=[
        Depends(rate_limit(key="cabinet_oauth_authorize", limit=30, window_seconds=TIME_1M))
    ],
    responses=error_responses(401),
)
@inject
async def cabinet_oauth_authorize(
    provider: OAuthProvider,
    body: InviteCodesRequest,
    response: Response,
    use_case: FromDishka[CabinetOAuthAuthorizeUseCase],
    config: FromDishka[AppConfig],
) -> CabinetOAuthAuthorizeResponse:
    url, binding = await use_case.execute(
        provider, InviteCodesDto(referral_code=body.ref, ad_link_code=body.ad)
    )
    set_oauth_cookie(response, binding, config.secure_cookies)
    return CabinetOAuthAuthorizeResponse(url=url)


@router.post(
    "/oauth/{provider}/callback",
    response_model=CabinetAuthResponse,
    responses=error_responses(401, 403),
)
@inject
async def cabinet_oauth_callback(
    provider: OAuthProvider,
    body: CabinetOAuthCallbackRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[CabinetOAuthCallbackUseCase],
    config: FromDishka[AppConfig],
    guard: FailureLimit = Depends(
        failure_rate_limit(key="cabinet_oauth_callback_fail", limit=20, window_seconds=TIME_1M)
    ),
) -> CabinetAuthResponse | JSONResponse:
    try:
        _, issued = await use_case.execute(
            provider,
            body.code,
            body.state,
            request.cookies.get(CABINET_OAUTH_COOKIE),
            resolve_client_ip(request),
            request.headers.get("user-agent"),
        )
    except AppError as error:
        if error.code in _OAUTH_CALLBACK_FAILURES:
            await guard.record_failure()
        # the state is single-use, so the binding is dead on any failure
        error_response = JSONResponse(
            status_code=status_for(error), content={"detail": str(error), "code": error.code.value}
        )
        error_response.delete_cookie(CABINET_OAUTH_COOKIE, path=CABINET_REFRESH_PATH)
        return error_response
    set_cabinet_cookies(response, issued, config.secure_cookies)
    response.delete_cookie(CABINET_OAUTH_COOKIE, path=CABINET_REFRESH_PATH)
    return CabinetAuthResponse(access_token=issued.access_token, expires_in=TTL_15M)


@router.post(
    "/refresh",
    response_model=CabinetAuthResponse,
    dependencies=[Depends(rate_limit(key="cabinet_refresh", limit=30, window_seconds=TIME_1M))],
    responses=error_responses(401, 403),
)
@inject
async def cabinet_refresh(
    request: Request,
    response: Response,
    use_case: FromDishka[RefreshSessionUseCase],
    config: FromDishka[AppConfig],
) -> CabinetAuthResponse | JSONResponse:
    refresh_token = request.cookies.get(CABINET_REFRESH_COOKIE)
    if not refresh_token:
        raise ApiError(
            status.HTTP_401_UNAUTHORIZED, "No refresh token", code=ErrorCode.REFRESH_TOKEN_MISSING
        )
    verify_csrf(
        refresh_token,
        request,
        config.jwt_secret.get_secret_value(),
        csrf_cookie=CABINET_CSRF_COOKIE,
    )

    try:
        issued = await use_case.execute(
            refresh_token=refresh_token,
            ip_address=resolve_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            audience=SessionAudience.CABINET,
        )
    except AuthenticationError as error:
        error_response = JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": str(error), "code": error.code.value},
        )
        clear_cabinet_cookies(error_response)
        return error_response

    set_cabinet_cookies(response, issued, config.secure_cookies)
    return CabinetAuthResponse(access_token=issued.access_token, expires_in=TTL_15M)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(rate_limit(key="cabinet_logout", limit=30, window_seconds=TIME_1M))],
    responses=error_responses(403),
)
@inject
async def cabinet_logout(
    request: Request,
    response: Response,
    use_case: FromDishka[LogoutUseCase],
    config: FromDishka[AppConfig],
) -> None:
    refresh_token = request.cookies.get(CABINET_REFRESH_COOKIE)
    if refresh_token:
        verify_csrf(
            refresh_token,
            request,
            config.jwt_secret.get_secret_value(),
            csrf_cookie=CABINET_CSRF_COOKIE,
        )
        await use_case.execute(refresh_token=refresh_token, audience=SessionAudience.CABINET)
    clear_cabinet_cookies(response)
