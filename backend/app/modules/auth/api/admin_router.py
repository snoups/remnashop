from typing import Optional

from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies.admin import require_admin
from app.core.enums import OAuthProvider
from app.core.exceptions import AuthenticationError, ConflictError, NotFoundError
from app.core.utils.http import resolve_client_ip
from app.modules.auth import (
    ListOAuthIdentitiesUseCase,
    ListSessionsUseCase,
    ListUserSessionsUseCase,
    OAuthCallbackDto,
    OAuthConnectAuthorizeUseCase,
    OAuthConnectCallbackUseCase,
    OAuthDisconnectDto,
    OAuthDisconnectUseCase,
    RevokeSessionDto,
    RevokeSessionUseCase,
    RevokeUserSessionDto,
    RevokeUserSessionUseCase,
)
from app.modules.auth.api.schemas import (
    OAuthAuthorizeResponse,
    OAuthCallbackRequest,
    OAuthIdentityResponse,
    SessionResponse,
)
from app.modules.auth.dto import SessionDto
from app.modules.users import UserDto

router = APIRouter(prefix="/auth/oauth", tags=["auth"])
sessions_router = APIRouter(prefix="/auth/sessions", tags=["auth"])


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


def _to_session_response(session: SessionDto) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        created_at=session.created_at,
        last_used_at=session.last_used_at,
        expires_at=session.expires_at,
    )


@sessions_router.get("", response_model=list[SessionResponse])
@inject
async def list_sessions(
    use_case: FromDishka[ListSessionsUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[SessionResponse]:
    sessions = await use_case(actor)
    return [_to_session_response(session) for session in sessions]


@sessions_router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def revoke_session(
    session_id: int,
    request: Request,
    use_case: FromDishka[RevokeSessionUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(
            actor, RevokeSessionDto(session_id=session_id, client_ip=resolve_client_ip(request))
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error


@sessions_router.get("/users/{user_id}", response_model=list[SessionResponse])
@inject
async def list_user_sessions(
    user_id: int,
    use_case: FromDishka[ListUserSessionsUseCase],
    actor: UserDto = Depends(require_admin),
) -> list[SessionResponse]:
    try:
        sessions = await use_case(actor, user_id)
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
    return [_to_session_response(session) for session in sessions]


@sessions_router.delete("/users/{user_id}/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
@inject
async def revoke_user_session(
    user_id: int,
    session_id: int,
    request: Request,
    use_case: FromDishka[RevokeUserSessionUseCase],
    actor: UserDto = Depends(require_admin),
) -> None:
    try:
        await use_case(
            actor,
            RevokeUserSessionDto(
                user_id=user_id, session_id=session_id, client_ip=resolve_client_ip(request)
            ),
        )
    except NotFoundError as error:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from error
