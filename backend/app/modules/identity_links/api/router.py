from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response, status
from fastapi.responses import JSONResponse

from app.api.dependencies.public import get_cabinet_customer
from app.api.dependencies.rate_limit import FailureLimit, failure_rate_limit, rate_limit
from app.api.errors import error_responses, status_for
from app.core.config import AppConfig
from app.core.constants import API_V1, TIME_1M
from app.core.enums import OAuthProvider, SessionAudience
from app.core.error_codes import ErrorCode
from app.core.exceptions import AppError, AuthenticationError, ValidationError
from app.core.utils.http import resolve_client_ip
from app.modules.auth import (
    OAUTH_BINDING_COOKIE,
    clear_oauth_binding_cookie,
    set_oauth_binding_cookie,
)
from app.modules.cabinet_auth import (
    BotSignInRequest,
    DeeplinkResponse,
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
)
from app.modules.identity_links.api.schemas import (
    IdentitiesResponse,
    IdentityResponse,
    LinkEmailCodeRequest,
    LinkEmailVerifyRequest,
    LinkResultResponse,
    MergeRequest,
)
from app.modules.identity_links.dto import IdentityKind
from app.modules.identity_links.usecases import (
    ConfirmMergeUseCase,
    ListIdentitiesUseCase,
    OAuthLinkAuthorizeUseCase,
    OAuthLinkCallbackUseCase,
    RequestLinkEmailCodeUseCase,
    RequestTelegramLinkUseCase,
    TelegramLinkSignInUseCase,
    UnlinkIdentityUseCase,
    VerifyLinkEmailCodeUseCase,
)
from app.modules.users import CurrentUserResponse, UserDto, to_current_user_response

_EMAIL_VERIFY_FAILURES = frozenset({ErrorCode.EMAIL_CODE_INVALID, ErrorCode.EMAIL_CODE_EXPIRED})
_BOT_SIGNIN_FAILURES = frozenset({ErrorCode.DEEPLINK_EXPIRED})
_OAUTH_CALLBACK_FAILURES = frozenset(
    {ErrorCode.OAUTH_STATE_INVALID, ErrorCode.OAUTH_CODE_EXCHANGE_FAILED}
)
# the sign-in binding cookie lives under /auth; the link one under its own routes
_OAUTH_BINDING_PATH = f"{API_V1}/users/me/identities/oauth"

router = APIRouter(prefix="/users/me", tags=["identities"])


def _as_input_error(error: AppError) -> AppError:
    # the session is live here: a 401 would make the cabinet refresh, replay a
    # spent code or state, then sign the customer out
    if isinstance(error, AuthenticationError):
        return ValidationError(str(error), code=error.code)
    return error


@router.get("/identities", response_model=IdentitiesResponse, responses=error_responses(403))
@inject
async def list_identities(
    use_case: FromDishka[ListIdentitiesUseCase],
    user: UserDto = Depends(get_cabinet_customer),
) -> IdentitiesResponse:
    items = await use_case.execute(user)
    return IdentitiesResponse(
        items=[IdentityResponse.model_validate(item, from_attributes=True) for item in items]
    )


@router.delete(
    "/identities/{kind}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(403, 409),
)
@inject
async def unlink_identity(
    kind: IdentityKind,
    request: Request,
    use_case: FromDishka[UnlinkIdentityUseCase],
    user: UserDto = Depends(get_cabinet_customer),
) -> None:
    await use_case.execute(user, kind, resolve_client_ip(request))


@router.post(
    "/merge",
    response_model=CurrentUserResponse,
    dependencies=[Depends(rate_limit(key="cabinet_merge", limit=10, window_seconds=TIME_1M))],
    responses=error_responses(403, 409),
)
@inject
async def confirm_merge(
    body: MergeRequest,
    request: Request,
    use_case: FromDishka[ConfirmMergeUseCase],
    user: UserDto = Depends(get_cabinet_customer),
) -> CurrentUserResponse:
    merged = await use_case.execute(user, body.merge_token, resolve_client_ip(request))
    return to_current_user_response(merged)


@router.post(
    "/identities/email/code",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[
        Depends(rate_limit(key="cabinet_link_email_code", limit=30, window_seconds=TIME_1M))
    ],
    responses=error_responses(400, 403),
)
@inject
async def request_link_email_code(
    body: LinkEmailCodeRequest,
    use_case: FromDishka[RequestLinkEmailCodeUseCase],
    user: UserDto = Depends(get_cabinet_customer),
) -> None:
    try:
        await use_case.execute(user, body.email, body.locale)
    except AppError as error:
        raise _as_input_error(error) from error


@router.post(
    "/identities/email/verify",
    response_model=LinkResultResponse,
    responses=error_responses(400, 403, 409),
)
@inject
async def verify_link_email_code(
    body: LinkEmailVerifyRequest,
    request: Request,
    use_case: FromDishka[VerifyLinkEmailCodeUseCase],
    user: UserDto = Depends(get_cabinet_customer),
    guard: FailureLimit = Depends(
        failure_rate_limit(key="cabinet_link_email_verify_fail", limit=20, window_seconds=TIME_1M)
    ),
) -> LinkResultResponse:
    try:
        result = await use_case.execute(user, body.email, body.code, resolve_client_ip(request))
    except AppError as error:
        if error.code in _EMAIL_VERIFY_FAILURES:
            await guard.record_failure()
        raise _as_input_error(error) from error
    return LinkResultResponse.model_validate(result, from_attributes=True)


@router.post(
    "/identities/telegram/deeplink",
    response_model=DeeplinkResponse,
    dependencies=[
        Depends(rate_limit(key="cabinet_link_telegram_deeplink", limit=20, window_seconds=TIME_1M))
    ],
    responses=error_responses(400, 403),
)
@inject
async def request_telegram_link(
    use_case: FromDishka[RequestTelegramLinkUseCase],
    user: UserDto = Depends(get_cabinet_customer),
) -> DeeplinkResponse:
    try:
        ticket = await use_case.execute(user)
    except AppError as error:
        raise _as_input_error(error) from error
    return DeeplinkResponse(bot_url=ticket.bot_url, expires_in=ticket.expires_in)


@router.post(
    "/identities/telegram/signin",
    response_model=LinkResultResponse,
    dependencies=[
        Depends(rate_limit(key="cabinet_link_telegram_signin", limit=20, window_seconds=TIME_1M))
    ],
    responses=error_responses(400, 403, 409),
)
@inject
async def telegram_link_signin(
    body: BotSignInRequest,
    request: Request,
    use_case: FromDishka[TelegramLinkSignInUseCase],
    user: UserDto = Depends(get_cabinet_customer),
    guard: FailureLimit = Depends(
        failure_rate_limit(
            key="cabinet_link_telegram_signin_fail", limit=20, window_seconds=TIME_1M
        )
    ),
) -> LinkResultResponse:
    try:
        result = await use_case.execute(user, body.token, resolve_client_ip(request))
    except AppError as error:
        if error.code in _BOT_SIGNIN_FAILURES:
            await guard.record_failure()
        raise _as_input_error(error) from error
    return LinkResultResponse.model_validate(result, from_attributes=True)


@router.post(
    "/identities/oauth/{provider}/authorize",
    response_model=OAuthAuthorizeResponse,
    dependencies=[
        Depends(rate_limit(key="cabinet_link_oauth_authorize", limit=30, window_seconds=TIME_1M))
    ],
    responses=error_responses(400, 403),
)
@inject
async def oauth_link_authorize(
    provider: OAuthProvider,
    response: Response,
    use_case: FromDishka[OAuthLinkAuthorizeUseCase],
    config: FromDishka[AppConfig],
    user: UserDto = Depends(get_cabinet_customer),
) -> OAuthAuthorizeResponse:
    try:
        url, binding = await use_case.execute(user, provider)
    except AppError as error:
        raise _as_input_error(error) from error
    set_oauth_binding_cookie(
        response, binding, config.secure_cookies, SessionAudience.CABINET, _OAUTH_BINDING_PATH
    )
    return OAuthAuthorizeResponse(url=url)


@router.post(
    "/identities/oauth/{provider}/callback",
    response_model=LinkResultResponse,
    dependencies=[
        Depends(rate_limit(key="cabinet_link_oauth_callback", limit=30, window_seconds=TIME_1M))
    ],
    responses=error_responses(400, 403, 409),
)
@inject
async def oauth_link_callback(
    provider: OAuthProvider,
    body: OAuthCallbackRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[OAuthLinkCallbackUseCase],
    user: UserDto = Depends(get_cabinet_customer),
    guard: FailureLimit = Depends(
        failure_rate_limit(key="cabinet_link_oauth_callback_fail", limit=20, window_seconds=TIME_1M)
    ),
) -> LinkResultResponse | JSONResponse:
    try:
        result = await use_case.execute(
            user,
            provider,
            body.code,
            body.state,
            request.cookies.get(OAUTH_BINDING_COOKIE),
            resolve_client_ip(request),
        )
    except AppError as error:
        if error.code in _OAUTH_CALLBACK_FAILURES:
            await guard.record_failure()
        # the state is single-use, so the binding is dead on any failure
        error = _as_input_error(error)
        error_response = JSONResponse(
            status_code=status_for(error), content={"detail": str(error), "code": error.code.value}
        )
        clear_oauth_binding_cookie(error_response, _OAUTH_BINDING_PATH)
        return error_response
    clear_oauth_binding_cookie(response, _OAUTH_BINDING_PATH)
    return LinkResultResponse.model_validate(result, from_attributes=True)
