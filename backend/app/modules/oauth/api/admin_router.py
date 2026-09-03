from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies.admin import require_admin
from app.core.enums import OAuthProvider
from app.core.exceptions import AuthenticationError, ConflictError
from app.core.utils.http import resolve_client_ip
from app.modules.oauth.api.schemas import (
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
    OAuthIdentityResponse,
)
from app.modules.oauth.usecases import (
    ListOAuthIdentitiesUseCase,
    OAuthCallbackDto,
    OAuthConnectAuthorizeUseCase,
    OAuthConnectCallbackUseCase,
    OAuthDisconnectDto,
    OAuthDisconnectUseCase,
)
from app.modules.users import UserDto

router = APIRouter(prefix="/auth/oauth", tags=["auth"])


def _to_response(provider: OAuthProvider, external_login: Optional[str]) -> OAuthIdentityResponse:
    return OAuthIdentityResponse(provider=str(provider), external_login=external_login)


@router.get("", response_model=list[OAuthIdentityResponse])
@inject
async def list_connected_accounts(
    use_case: FromDishka[ListOAuthIdentitiesUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[OAuthIdentityResponse]:
    identities = await use_case(actor)
    return [_to_response(identity.provider, identity.external_login) for identity in identities]


@router.get("/{provider}/connect/authorize", response_model=OAuthAuthorizeResponse)
@inject
async def connect_authorize(
    provider: OAuthProvider,
    use_case: FromDishka[OAuthConnectAuthorizeUseCase],
    actor: UserDto = Depends(require_admin),
) -> OAuthAuthorizeResponse:
    try:
        url = await use_case(actor, provider)
    except AuthenticationError as error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(error)) from error
    return OAuthAuthorizeResponse(authorization_url=url)


@router.post("/{provider}/connect/callback", response_model=OAuthIdentityResponse)
@inject
async def connect_callback(
    provider: OAuthProvider,
    payload: OAuthCallbackRequest,
    request: Request,
    use_case: FromDishka[OAuthConnectCallbackUseCase],
    actor: UserDto = Depends(require_admin),
) -> OAuthIdentityResponse:
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
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return _to_response(identity.provider, identity.external_login)


@router.delete("/{provider}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def disconnect(
    provider: OAuthProvider,
    request: Request,
    use_case: FromDishka[OAuthDisconnectUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    await use_case(
        actor, OAuthDisconnectDto(provider=provider, client_ip=resolve_client_ip(request))
    )
