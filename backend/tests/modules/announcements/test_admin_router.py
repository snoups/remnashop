import datetime
import json
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
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.announcements.feed import parse_feed
from app.modules.announcements.repository import AnnouncementRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.providers import get_module_providers
from app.modules.users.dto import CreateUserDto
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
        *get_module_providers(),
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


async def _staff_token(
    role: Role,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> str:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=role.name.lower(),
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=role.name.lower(),
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    return await _issue_token(user.id, session_repository, config)


async def _seed(repo: AnnouncementRepository, uow: UnitOfWork) -> None:
    notify_at = (datetime.datetime.now(timezone.utc) + timedelta(seconds=1)).isoformat()
    body = json.dumps(
        {
            "items": [
                {"id": "all", "title": {"en": "a"}, "notify_at": notify_at},
                {"id": "owners", "title": {"en": "o"}, "notify_at": notify_at, "roles": ["OWNER"]},
            ]
        }
    ).encode()
    async with uow:
        await repo.replace_all(parse_feed(body))
        await uow.commit()


async def test_admin_does_not_receive_owner_only_items(
    client: httpx.AsyncClient,
    announcement_repository: AnnouncementRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await _staff_token(Role.ADMIN, user_repository, session_repository, uow, config)
    await _seed(announcement_repository, uow)
    monkeypatch.setattr(
        "app.modules.announcements.usecases.list_announcements.datetime_now",
        lambda: datetime.datetime.now(timezone.utc) + timedelta(minutes=1),
    )

    response = await client.get(
        "/api/v1/announcements", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 200
    body = response.json()
    assert [item["id"] for item in body["items"]] == ["all"]
    assert body["total"] == 1
    assert body["items"][0]["seen"] is False


async def test_mark_seen_accepts_unknown_ids(
    client: httpx.AsyncClient,
    announcement_repository: AnnouncementRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _staff_token(Role.OWNER, user_repository, session_repository, uow, config)
    await _seed(announcement_repository, uow)

    response = await client.post(
        "/api/v1/announcements/actions/mark-seen",
        json={"ids": ["all", "gone"]},
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 204


async def test_mark_seen_rejects_an_empty_list(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _staff_token(Role.OWNER, user_repository, session_repository, uow, config)
    response = await client.post(
        "/api/v1/announcements/actions/mark-seen",
        json={"ids": []},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 422


async def test_dismissed_announcement_leaves_the_list(
    client: httpx.AsyncClient,
    announcement_repository: AnnouncementRepository,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token = await _staff_token(Role.OWNER, user_repository, session_repository, uow, config)
    await _seed(announcement_repository, uow)
    monkeypatch.setattr(
        "app.modules.announcements.usecases.list_announcements.datetime_now",
        lambda: datetime.datetime.now(timezone.utc) + timedelta(minutes=1),
    )
    headers = {"Authorization": f"Bearer {token}"}

    response = await client.post(
        "/api/v1/announcements/actions/dismiss", json={"ids": ["all"]}, headers=headers
    )
    assert response.status_code == 204

    listed = await client.get("/api/v1/announcements", headers=headers)
    assert [item["id"] for item in listed.json()["items"]] == ["owners"]
