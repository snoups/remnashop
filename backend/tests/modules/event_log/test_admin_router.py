import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, Role
from app.core.events import EventCategory
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.event_log import get_event_log_providers
from app.modules.event_log.dto import EventLogEntryDto
from app.modules.event_log.repository import EventLogRepository
from app.modules.settings import get_settings_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncContainer:
    providers = [
        *get_core_providers(),
        *get_users_providers(),
        *get_auth_providers(),
        *get_settings_providers(),
        *get_event_log_providers(),
        *get_api_tokens_providers(),
        *get_translations_providers(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def client(
    config: AppConfig, test_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    # httpx.AsyncClient + ASGITransport keeps the request on the same event
    # loop as this test coroutine -- required because the endpoint's
    # dishka-resolved AsyncSession is the same asyncpg connection the
    # `session` fixture opened on this test's loop (asyncpg connections are
    # loop-bound). See tests/modules/users/test_admin_router.py's own comment
    # on this fixture for the full explanation; this file's copy must stay in
    # sync with that one since they exercise the same container-wiring contract.
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _issue_token(
    user_id: int, session_repository: SessionRepository, config: AppConfig
) -> str:
    # get_current_actor requires the token's "sid" claim to reference a real,
    # non-revoked session row -- a bare create_access_token(user_id, secret)
    # call is no longer enough since the session/refresh-token rework.
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user_id,
            refresh_token_hash=hash_refresh_token("test-refresh-token"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    return create_access_token(user_id, session.id, config.jwt_secret.get_secret_value())


async def _owner_token(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> tuple[UserDto, str]:
    async with uow:
        owner = await user_repository.create(
            CreateUserDto(
                login="eventlogowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="eventlogowner",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    token = await _issue_token(owner.id, session_repository, config)
    return owner, token


async def test_get_event_log_returns_entries(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_log_repository: EventLogRepository,
) -> None:
    await event_log_repository.create(
        EventLogEntryDto(
            category=EventCategory.AUTH,
            event_type="LoginSucceededEvent",
            occurred_at=datetime.datetime.now(datetime.timezone.utc),
            payload={},
        )
    )
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.get("/api/v1/event-log", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert len(body["items"]) == 1


async def test_get_event_log_filters_by_category(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    event_log_repository: EventLogRepository,
) -> None:
    await event_log_repository.create(
        EventLogEntryDto(
            category=EventCategory.ADMIN_MANAGEMENT,
            event_type="AdminCreatedEvent",
            occurred_at=datetime.datetime.now(datetime.timezone.utc),
            payload={},
        )
    )
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.get(
        "/api/v1/event-log?category=AUTH", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    assert response.json()["total"] == 0


async def test_get_event_log_rejects_admin_without_grant(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="plainadmin",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="plainadmin",
                role=Role.ADMIN,
                language=Locale.EN,
            )
        )
        await uow.commit()
    token = await _issue_token(admin.id, session_repository, config)

    response = await client.get("/api/v1/event-log", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 403


async def test_get_event_log_rejects_page_zero(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.get(
        "/api/v1/event-log?page=0", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422


async def test_get_event_log_rejects_oversized_page_size(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    _, token = await _owner_token(user_repository, session_repository, uow, config)

    response = await client.get(
        "/api/v1/event-log?page_size=500", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 422
