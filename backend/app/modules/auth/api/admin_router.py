from dishka import FromDishka
from dishka.integrations.fastapi import inject
from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.dependencies.admin import require_admin
from app.core.exceptions import ConflictError, NotFoundError
from app.core.utils.http import resolve_client_ip
from app.modules.auth import (
    ListSessionsUseCase,
    ListUserSessionsUseCase,
    RevokeSessionDto,
    RevokeSessionUseCase,
    RevokeUserSessionDto,
    RevokeUserSessionUseCase,
)
from app.modules.auth.api.schemas import SessionResponse
from app.modules.auth.dto import SessionDto
from app.modules.users import UserDto

sessions_router = APIRouter(prefix="/auth/sessions", tags=["auth"])


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
