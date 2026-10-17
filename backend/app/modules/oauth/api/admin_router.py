from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies.admin import require_admin_user
from app.api.errors import error_responses
from app.core.enums import OAuthProvider
from app.core.exceptions import AuthenticationError, ValidationError
from app.core.utils.http import resolve_client_ip
from app.modules.oauth.api.schemas import (
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
    OAuthIdentityListResponse,
    OAuthIdentityResponse,
)
from app.modules.oauth.dto import OAuthCallbackDto, OAuthDisconnectDto
from app.modules.oauth.usecases import (
    ListOAuthIdentitiesUseCase,
    OAuthConnectAuthorizeUseCase,
    OAuthConnectCallbackUseCase,
    OAuthDisconnectUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/auth/oauth", tags=["auth"])


@router.get("", response_model=OAuthIdentityListResponse)
@inject
async def list_connected_accounts(
    use_case: FromDishka[ListOAuthIdentitiesUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> OAuthIdentityListResponse:
    identities = await use_case(actor)
    items = [
        OAuthIdentityResponse.model_validate(identity, from_attributes=True)
        for identity in identities
    ]
    return OAuthIdentityListResponse(items=items, total=len(items))


@router.post(
    "/{provider}/connect/authorize",
    response_model=OAuthAuthorizeResponse,
    responses=error_responses(400),
)
@inject
async def oauth_connect_authorize(
    provider: OAuthProvider,
    use_case: FromDishka[OAuthConnectAuthorizeUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> OAuthAuthorizeResponse:
    try:
        url = await use_case(actor, provider)
    except AuthenticationError as error:
        raise ValidationError(str(error), code=error.code) from error
    return OAuthAuthorizeResponse(authorization_url=url)


@router.post(
    "/{provider}/connect/callback",
    response_model=OAuthIdentityResponse,
    responses=error_responses(400, 409),
)
@inject
async def oauth_connect_callback(
    provider: OAuthProvider,
    payload: OAuthCallbackRequest,
    request: Request,
    use_case: FromDishka[OAuthConnectCallbackUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> OAuthIdentityResponse:
    # 401 here would make the dashboard refresh and replay a spent state, then sign out
    try:
        identity = await use_case(
            actor,
            OAuthCallbackDto(
                provider=provider,
                code=payload.code,
                state=payload.state,
                client_ip=resolve_client_ip(request),
            ),
        )
    except AuthenticationError as error:
        raise ValidationError(str(error), code=error.code) from error
    return OAuthIdentityResponse.model_validate(identity, from_attributes=True)


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def disconnect_oauth_account(
    provider: OAuthProvider,
    request: Request,
    use_case: FromDishka[OAuthDisconnectUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(
        actor, OAuthDisconnectDto(provider=provider, client_ip=resolve_client_ip(request))
    )
