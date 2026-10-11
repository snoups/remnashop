import pytest
from starlette.requests import Request

from app.api.dependencies.admin import require_admin
from app.api.errors import ApiError
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.error_codes import ErrorCode
from app.core.exceptions import AuthenticationError
from app.core.ports import EventPublisher
from app.modules.auth.repository import SessionRepository
from app.modules.auth.session_issuer import SessionIssuer
from app.modules.auth.usecases import RefreshSessionUseCase
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def _admin(user_repository: UserRepository, uow: UnitOfWork) -> int:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(login="aud-admin", name="aud", role=Role.ADMIN, language=Locale.EN)
        )
    return user.id


async def test_cabinet_login_keeps_dashboard_session_from_same_device(
    session_repository: SessionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    user_id = await _admin(user_repository, uow)
    issuer = SessionIssuer(session_repository, uow, config)

    await issuer.issue(user_id, "203.0.113.5", "ua")
    await issuer.issue(user_id, "203.0.113.5", "ua", audience=SessionAudience.CABINET)

    active = await session_repository.list_active_by_user(user_id)
    assert {s.audience for s in active} == {SessionAudience.DASHBOARD, SessionAudience.CABINET}


async def test_refresh_rejects_token_of_other_audience(
    session_repository: SessionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_publisher: EventPublisher,
) -> None:
    user_id = await _admin(user_repository, uow)
    issuer = SessionIssuer(session_repository, uow, config)
    issued = await issuer.issue(user_id, "203.0.113.5", "ua", audience=SessionAudience.CABINET)
    use_case = RefreshSessionUseCase(session_repository, issuer, uow, event_publisher)

    with pytest.raises(AuthenticationError):
        await use_case.execute(issued.refresh_token, "203.0.113.5", "ua")

    rotated = await use_case.execute(
        issued.refresh_token, "203.0.113.5", "ua", audience=SessionAudience.CABINET
    )
    assert rotated.access_token


async def test_require_admin_rejects_cabinet_session(
    user_repository: UserRepository, uow: UnitOfWork
) -> None:
    await _admin(user_repository, uow)
    async with uow:
        actor = await user_repository.get_by_login("aud-admin")
    assert actor is not None
    request = Request({"type": "http", "headers": [], "state": {}})
    request.state.session_audience = SessionAudience.CABINET

    with pytest.raises(ApiError) as error:
        await require_admin(request, actor)

    assert error.value.code is ErrorCode.SESSION_AUDIENCE_MISMATCH
