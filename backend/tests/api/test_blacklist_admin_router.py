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
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist.tasks import sync_blacklist_sources_task
from app.modules.blacklist.usecases import add_blacklist_source as add_blacklist_source_module
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
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
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
    app = get_app(config)
    setup_dishka(test_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def _token_for(
    role: Role,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> str:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=f"blacklisttest{role.value}",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=f"blacklisttest{role.value}",
                role=role,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{role.value}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    return create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())


async def _owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    return {"Authorization": f"Bearer {token}"}


async def test_add_and_list_entry(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    add_response = await client.put(f"{API_V1}/blacklist/entries/TELEGRAM_ID/042", headers=headers)
    assert add_response.status_code == 200
    too_big = await client.put(
        f"{API_V1}/blacklist/entries/TELEGRAM_ID/{'9' * 20}", headers=headers
    )
    assert too_big.status_code == 400
    assert too_big.json()["code"] == "BLACKLIST_VALUE_INVALID"
    assert add_response.json()["telegram_ids"] == [42]

    list_response = await client.get(f"{API_V1}/blacklist", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["telegram_ids"] == [42]


async def test_remove_entry(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    await client.put(f"{API_V1}/blacklist/entries/EMAIL/blocked@example.com", headers=headers)

    remove_response = await client.delete(
        f"{API_V1}/blacklist/entries/EMAIL/blocked@example.com", headers=headers
    )
    assert remove_response.status_code == 200
    assert remove_response.json()["emails"] == []


async def test_add_entry_invalid_value_returns_400(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.put(f"{API_V1}/blacklist/entries/TELEGRAM_ID/xxx", headers=headers)
    assert response.status_code == 400


async def test_add_source_rejects_http(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.post(
        f"{API_V1}/blacklist/sources",
        headers=headers,
        json={"url": "http://x.example/l.txt"},
    )
    assert response.status_code == 400


async def test_update_source(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        add_blacklist_source_module, "assert_public_https_host", _fake_assert_public_https_host
    )
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    add_response = await client.post(
        f"{API_V1}/blacklist/sources",
        headers=headers,
        json={"url": "https://x.example/list.txt", "name": "example"},
    )
    assert add_response.status_code == 201
    source_id = add_response.json()["id"]
    assert add_response.json()["enabled"] is True

    update_response = await client.patch(
        f"{API_V1}/blacklist/sources/{source_id}",
        headers=headers,
        json={"enabled": False},
    )
    assert update_response.status_code == 200
    assert update_response.json()["enabled"] is False


async def test_get_source(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        add_blacklist_source_module, "assert_public_https_host", _fake_assert_public_https_host
    )
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    add_response = await client.post(
        f"{API_V1}/blacklist/sources",
        headers=headers,
        json={"url": "https://x.example/detail.txt", "name": "detail"},
    )
    source_id = add_response.json()["id"]

    response = await client.get(f"{API_V1}/blacklist/sources/{source_id}", headers=headers)
    missing = await client.get(f"{API_V1}/blacklist/sources/999999", headers=headers)

    assert response.status_code == 200
    assert response.json() == add_response.json()
    assert missing.status_code == 404
    assert missing.json()["code"] == "BLACKLIST_SOURCE_NOT_FOUND"


async def test_add_duplicate_source_url_returns_409(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        add_blacklist_source_module, "assert_public_https_host", _fake_assert_public_https_host
    )
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    payload = {"url": "https://x.example/dupe.txt"}

    first = await client.post(f"{API_V1}/blacklist/sources", headers=headers, json=payload)
    assert first.status_code == 201

    duplicate = await client.post(f"{API_V1}/blacklist/sources", headers=headers, json=payload)
    assert duplicate.status_code == 409


async def test_update_missing_source_returns_404(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.patch(
        f"{API_V1}/blacklist/sources/999999",
        headers=headers,
        json={"enabled": False},
    )
    assert response.status_code == 404


async def test_remove_source(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_assert_public_https_host(url: str) -> None:
        return None

    monkeypatch.setattr(
        add_blacklist_source_module, "assert_public_https_host", _fake_assert_public_https_host
    )
    headers = await _owner_headers(user_repository, session_repository, uow, config)
    add_response = await client.post(
        f"{API_V1}/blacklist/sources",
        headers=headers,
        json={"url": "https://x.example/list2.txt"},
    )
    source_id = add_response.json()["id"]

    delete_response = await client.delete(
        f"{API_V1}/blacklist/sources/{source_id}", headers=headers
    )
    assert delete_response.status_code == 204

    list_response = await client.get(f"{API_V1}/blacklist/sources", headers=headers)
    assert list_response.json()["items"] == []


async def test_sync_sources_returns_202(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def _fake_kiq(**kwargs: object) -> None:
        return None

    monkeypatch.setattr(sync_blacklist_sources_task, "kiq", _fake_kiq)
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.post(f"{API_V1}/blacklist/sources/actions/sync", headers=headers)
    assert response.status_code == 202


async def test_plain_admin_forbidden(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    # BLACKLIST_VIEW is OWNER-only by default.
    token = await _token_for(Role.ADMIN, user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/blacklist", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 403


async def test_unauthenticated_request_rejected(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/blacklist")
    assert response.status_code == 401
