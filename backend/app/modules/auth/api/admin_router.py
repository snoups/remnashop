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
    RevokeSessionUseCase,
    RevokeUserSessionUseCase,
)
from app.modules.auth.api.schemas import SessionListResponse, SessionResponse
from app.modules.auth.dto import RevokeSessionDto, RevokeUserSessionDto
from app.modules.users import UserDto

sessions_router = APIRouter(prefix="/auth/sessions", tags=["auth"])
user_sessions_router = APIRouter(prefix="/users", tags=["auth"])


@sessions_router.get("", response_model=SessionListResponse)
@inject
async def list_sessions(
    use_case: FromDishka[ListSessionsUseCase],
    actor: UserDto = Depends(require_admin_user),
) -> SessionListResponse:
    sessions = await use_case(actor)
    items = [SessionResponse.model_validate(session, from_attributes=True) for session in sessions]
    return SessionListResponse(items=items, total=len(items))


@sessions_router.delete(
    "/{session_id:int}", status_code=status.HTTP_204_NO_CONTENT, responses=error_responses(404)
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
    "/{user_id:int}/sessions",
    response_model=SessionListResponse,
    responses=error_responses(404, 409),
)
@inject
async def list_user_sessions(
    user_id: int,
    use_case: FromDishka[ListUserSessionsUseCase],
    actor: Actor = Depends(require_admin),
) -> SessionListResponse:
    sessions = await use_case(actor, user_id)
    items = [SessionResponse.model_validate(session, from_attributes=True) for session in sessions]
    return SessionListResponse(items=items, total=len(items))


@user_sessions_router.delete(
    "/{user_id:int}/sessions/{session_id:int}",
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
