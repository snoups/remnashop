from typing import Union

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies.public import forbid_cabinet_proxy
from app.api.dependencies.rate_limit import (
    FailureLimit,
    failure_rate_limit,
    rate_limit,
)
from app.api.errors import error_responses, status_for
from app.core.config import AppConfig
from app.core.constants import TIME_1M, TTL_15M
from app.core.enums import OAuthProvider, SessionAudience
from app.core.exceptions import AppError, AuthenticationError, ValidationError
from app.core.utils.http import resolve_client_ip
from app.modules.auth import (
    DEEPLINK_BINDING_COOKIE,
    OAUTH_BINDING_COOKIE,
    clear_oauth_binding_cookie,
    set_audience_cookies,
    set_oauth_binding_cookie,
)
from app.modules.cabinet_auth.api.schemas import (
    BotSignInRequest,
    CabinetAuthResponse,
    CabinetMethodsResponse,
    DeeplinkResponse,
    InviteCodesRequest,
    OAuthAuthorizeRequest,
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
    OAuthSignInResponse,
    RequestEmailCodeRequest,
    TelegramWebAppLoginRequest,
    VerifyEmailCodeRequest,
)
from app.modules.cabinet_auth.attempts import (
    BOT_SIGNIN_FAILURES,
    EMAIL_VERIFY_FAILURES,
    OAUTH_CALLBACK_FAILURES,
    TELEGRAM_FAILURES,
)
from app.modules.cabinet_auth.dto import InviteCodesDto
from app.modules.cabinet_auth.usecases import (
    BotSignInUseCase,
    CabinetOAuthAuthorizeUseCase,
    CabinetOAuthCallbackUseCase,
    GetCabinetMethodsUseCase,
    RequestDeeplinkUseCase,
    RequestEmailCodeUseCase,
    TelegramWebAppLoginUseCase,
    VerifyEmailCodeUseCase,
)
from app.modules.oauth import (
    OAuthFlowPurpose,
    OAuthLoginAuthorizeUseCase,
    OAuthLoginCallbackUseCase,
    OAuthStateStore,
)

router = APIRouter(prefix="/auth", tags=["auth"])


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
            body.init_data,
            resolve_client_ip(request),
            request.headers.get("user-agent"),
            body.legal_locale,
        )
    except AppError as error:
        if error.code in TELEGRAM_FAILURES:
            await guard.record_failure()
        raise
    set_audience_cookies(response, issued, config.secure_cookies, SessionAudience.CABINET)
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
            body.email,
            body.code,
            resolve_client_ip(request),
            request.headers.get("user-agent"),
            body.legal_locale,
        )
    except AppError as error:
        if error.code in EMAIL_VERIFY_FAILURES:
            await guard.record_failure()
        raise
    set_audience_cookies(response, issued, config.secure_cookies, SessionAudience.CABINET)
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
    response: Response,
    use_case: FromDishka[RequestDeeplinkUseCase],
    config: FromDishka[AppConfig],
) -> DeeplinkResponse:
    ticket = await use_case.execute(InviteCodesDto(referral_code=body.ref, ad_link_code=body.ad))
    if ticket.binding is not None:
        set_oauth_binding_cookie(
            response,
            ticket.binding,
            config.secure_cookies,
            SessionAudience.CABINET,
            name=DEEPLINK_BINDING_COOKIE,
        )
    return DeeplinkResponse(bot_url=ticket.bot_url, expires_in=ticket.expires_in)


@router.post(
    "/telegram/signin",
    response_model=CabinetAuthResponse,
    dependencies=[
        Depends(rate_limit(key="cabinet_telegram_signin", limit=20, window_seconds=TIME_1M))
    ],
    responses=error_responses(401, 403),
)
@inject
async def cabinet_telegram_signin(
    body: BotSignInRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[BotSignInUseCase],
    config: FromDishka[AppConfig],
    guard: FailureLimit = Depends(
        failure_rate_limit(key="cabinet_telegram_signin_fail", limit=20, window_seconds=TIME_1M)
    ),
) -> CabinetAuthResponse:
    try:
        _, issued = await use_case.execute(
            body.token,
            request.cookies.get(DEEPLINK_BINDING_COOKIE),
            resolve_client_ip(request),
            request.headers.get("user-agent"),
            body.legal_locale,
        )
    except AppError as error:
        if error.code in BOT_SIGNIN_FAILURES:
            await guard.record_failure()
        raise
    clear_oauth_binding_cookie(response, name=DEEPLINK_BINDING_COOKIE)
    set_audience_cookies(response, issued, config.secure_cookies, SessionAudience.CABINET)
    return CabinetAuthResponse(access_token=issued.access_token, expires_in=TTL_15M)


@router.post(
    "/oauth/{provider}/authorize",
    response_model=OAuthAuthorizeResponse,
    dependencies=[Depends(rate_limit(key="oauth_authorize", limit=30, window_seconds=TIME_1M))],
    responses=error_responses(400, 401, 403),
)
@inject
async def oauth_authorize(
    provider: OAuthProvider,
    body: OAuthAuthorizeRequest,
    request: Request,
    response: Response,
    dashboard: FromDishka[OAuthLoginAuthorizeUseCase],
    cabinet: FromDishka[CabinetOAuthAuthorizeUseCase],
    config: FromDishka[AppConfig],
) -> OAuthAuthorizeResponse:
    if body.audience == "dashboard":
        forbid_cabinet_proxy(request)
        try:
            url, binding = await dashboard.execute(provider)
        except AuthenticationError as error:
            raise ValidationError(str(error), code=error.code) from error
        audience = SessionAudience.DASHBOARD
    else:
        url, binding = await cabinet.execute(
            provider, InviteCodesDto(referral_code=body.ref, ad_link_code=body.ad)
        )
        audience = SessionAudience.CABINET
    set_oauth_binding_cookie(response, binding, config.secure_cookies, audience)
    return OAuthAuthorizeResponse(url=url)


@router.post(
    "/oauth/{provider}/callback",
    response_model=OAuthSignInResponse,
    dependencies=[Depends(rate_limit(key="oauth_callback", limit=30, window_seconds=TIME_1M))],
    responses=error_responses(401, 403),
)
@inject
async def oauth_callback(
    provider: OAuthProvider,
    body: OAuthCallbackRequest,
    request: Request,
    response: Response,
    state_store: FromDishka[OAuthStateStore],
    dashboard: FromDishka[OAuthLoginCallbackUseCase],
    cabinet: FromDishka[CabinetOAuthCallbackUseCase],
    config: FromDishka[AppConfig],
    guard: FailureLimit = Depends(
        failure_rate_limit(key="oauth_callback_fail", limit=20, window_seconds=TIME_1M)
    ),
) -> Union[OAuthSignInResponse, JSONResponse]:
    binding = request.cookies.get(OAUTH_BINDING_COOKIE)
    client_ip = resolve_client_ip(request)
    user_agent = request.headers.get("user-agent")
    # the state says whose sign-in this is; the flow below spends it
    is_dashboard = await state_store.peek_purpose(body.state) is OAuthFlowPurpose.LOGIN
    if is_dashboard:
        forbid_cabinet_proxy(request)
    try:
        if is_dashboard:
            user, issued = await dashboard.execute(
                provider, body.code, body.state, binding, client_ip, user_agent
            )
        else:
            user, issued = await cabinet.execute(
                provider, body.code, body.state, binding, client_ip, user_agent, body.legal_locale
            )
    except AppError as error:
        if error.code in OAUTH_CALLBACK_FAILURES:
            await guard.record_failure()
        # the state is single-use, so the binding is dead on any failure
        error_response = JSONResponse(
            status_code=status_for(error), content={"detail": str(error), "code": error.code.value}
        )
        clear_oauth_binding_cookie(error_response)
        return error_response
    audience = SessionAudience.DASHBOARD if is_dashboard else SessionAudience.CABINET
    set_audience_cookies(response, issued, config.secure_cookies, audience)
    clear_oauth_binding_cookie(response)
    return OAuthSignInResponse(
        access_token=issued.access_token,
        expires_in=TTL_15M,
        id=user.id,
        login=user.login,
        role=user.role,
    )
