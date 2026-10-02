from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, Response

from app.api.dependencies.rate_limit import rate_limit
from app.api.errors import error_responses
from app.core.config import AppConfig
from app.core.constants import TIME_1M
from app.core.enums import OAuthProvider
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.utils.http import resolve_client_ip
from app.modules.auth import AuthResponse, set_session_cookies, to_auth_response
from app.modules.oauth.api.schemas import OAuthAuthorizeResponse, OAuthCallbackRequest
from app.modules.oauth.usecases import OAuthLoginAuthorizeUseCase, OAuthLoginCallbackUseCase

router = APIRouter(prefix="/auth/oauth", tags=["auth"])


@router.get(
    "/{provider}/authorize",
    response_model=OAuthAuthorizeResponse,
    dependencies=[Depends(rate_limit(key="oauth_authorize", limit=10, window_seconds=TIME_1M))],
    responses=error_responses(400),
)
@inject
async def oauth_authorize(
    provider: OAuthProvider,
    use_case: FromDishka[OAuthLoginAuthorizeUseCase],
) -> OAuthAuthorizeResponse:
    try:
        url = await use_case.execute(provider)
    except AuthenticationError as error:
        raise ValidationError(str(error), code=error.code) from error
    return OAuthAuthorizeResponse(authorization_url=url)


@router.post(
    "/{provider}/callback",
    response_model=AuthResponse,
    dependencies=[Depends(rate_limit(key="oauth_callback", limit=10, window_seconds=TIME_1M))],
    responses=error_responses(401),
)
@inject
async def oauth_callback(
    provider: OAuthProvider,
    payload: OAuthCallbackRequest,
    request: Request,
    response: Response,
    use_case: FromDishka[OAuthLoginCallbackUseCase],
    config: FromDishka[AppConfig],
) -> AuthResponse:
    user, issued = await use_case.execute(
        provider,
        payload.code,
        payload.state,
        resolve_client_ip(request),
        user_agent=request.headers.get("user-agent"),
    )

    set_session_cookies(response, issued, config.secure_cookies)
    return to_auth_response(user, issued.access_token)
