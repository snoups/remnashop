from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, Request, status

from app.api.dependencies.admin import require_admin, require_admin_user
from app.api.errors import error_responses
from app.core.actor import Actor
from app.core.utils.http import resolve_client_ip
from app.modules.auth import (
    ListSessionsUseCase,
    ListUserSessionsUseCase,
    RevokeSessionDto,
    RevokeSessionUseCase,
    RevokeUserSessionDto,
    RevokeUserSessionUseCase,
)
from app.modules.auth.api.schemas import SessionListResponse, SessionResponse
from app.modules.auth.dto import SessionDto
from app.modules.users import UserDto

sessions_router = APIRouter(prefix="/auth/sessions", tags=["auth"])
user_sessions_router = APIRouter(prefix="/users", tags=["auth"])


def _to_session_response(session: SessionDto) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        ip_address=session.ip_address,
        user_agent=session.user_agent,
        created_at=session.created_at,
        last_used_at=session.last_used_at,
        expires_at=session.expires_at,
    )


@sessions_router.get("", response_model=SessionListResponse)
@inject
async def list_sessions(
    use_case: FromDishka[ListSessionsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> SessionListResponse:
    sessions = await use_case(actor)
    items = [_to_session_response(session) for session in sessions]
    return SessionListResponse(items=items, total=len(items))


@sessions_router.delete(
    "/{session_id}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
)
@inject
async def revoke_session(
    session_id: int,
    request: Request,
    use_case: FromDishka[RevokeSessionUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> None:
    await use_case(
        actor, RevokeSessionDto(session_id=session_id, client_ip=resolve_client_ip(request))
    )


@user_sessions_router.get(
    "/{user_id}/sessions", response_model=SessionListResponse, responses=error_responses(404, 409)
)
@inject
async def list_user_sessions(
    user_id: int,
    use_case: FromDishka[ListUserSessionsUseCase],
    actor: Actor = Depends(require_admin),
) -> SessionListResponse:
    sessions = await use_case(actor, user_id)
    items = [_to_session_response(session) for session in sessions]
    return SessionListResponse(items=items, total=len(items))


@user_sessions_router.delete(
    "/{user_id}/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    responses=error_responses(404, 409),
)
@inject
async def revoke_user_session(
    user_id: int,
    session_id: int,
    request: Request,
    use_case: FromDishka[RevokeUserSessionUseCase],
    actor: Actor = Depends(require_admin),
) -> None:
    await use_case(
        actor,
        RevokeUserSessionDto(
            user_id=user_id, session_id=session_id, client_ip=resolve_client_ip(request)
        ),
    )
