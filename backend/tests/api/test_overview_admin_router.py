import datetime
from datetime import timedelta, timezone
from types import SimpleNamespace
from typing import AsyncIterator, cast

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from remnapy import RemnawaveSDK
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.enums import Locale, Role, SessionAudience
from app.core.exceptions import RemnawavePanelUnavailableError
from app.core.security import create_access_token, hash_password, hash_refresh_token
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


class _DownNodes:
    async def get_all_nodes(self) -> list[object]:
        raise RemnawavePanelUnavailableError("down")

    async def get_hwid_stats(self) -> object:
        raise RemnawavePanelUnavailableError("down")


class _StubSdkProvider(Provider):
    # keeps the router tests off a real panel
    scope = Scope.REQUEST

    @provide(override=True)
    def get_sdk(self) -> RemnawaveSDK:
        return cast(RemnawaveSDK, SimpleNamespace(nodes=_DownNodes(), hwid=_DownNodes()))


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_module_providers(),
        _TestSessionProvider(session),
        _StubSdkProvider(),
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


async def _owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login="overviewtestowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="overviewtestowner",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-overview-owner"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_get_overview_requires_admin(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/overview")
    assert response.status_code == 401


async def test_owner_can_get_a_chart_with_valid_days(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    for chart in ("revenue", "registrations", "online"):
        response = await client.get(f"{API_V1}/overview/{chart}?days=30", headers=headers)

        assert response.status_code == 200
        assert response.json()["days"] == 30


async def test_get_overview_summary(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/overview", headers=headers)

    assert response.status_code == 200
    assert response.json()["runtime"] == []
    assert "disabled" in response.json()["subscriptions"]


async def test_get_overview_chart_rejects_an_invalid_days_value(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/overview/online?days=5", headers=headers)

    assert response.status_code == 422


async def test_owner_can_get_hourly_online(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/overview/online/hourly", headers=headers)

    assert response.status_code == 200
    assert len(response.json()["points"]) == 24


async def test_nodes_and_client_apps_require_a_session(client: httpx.AsyncClient) -> None:
    for path in ("nodes", "client-apps", "attention"):
        assert (await client.get(f"{API_V1}/overview/{path}")).status_code == 401


async def _admin_without_permission_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    permission: str,
) -> dict[str, str]:
    login = f"overview-{permission.lower()}"
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login=login,
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=login,
                role=Role.ADMIN,
                language=Locale.EN,
                permission_revokes=[permission],
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{login}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.parametrize(
    ("path", "permission"),
    [("nodes", "REMNAWAVE_NODES_VIEW"), ("client-apps", "REMNAWAVE_CLIENT_APPS_VIEW")],
)
async def test_remnawave_cards_require_their_permission(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    path: str,
    permission: str,
) -> None:
    headers = await _admin_without_permission_headers(
        user_repository, session_repository, uow, config, permission
    )

    response = await client.get(f"{API_V1}/overview/{path}", headers=headers)

    assert response.status_code == 403


@pytest.mark.parametrize("path", ["nodes", "client-apps"])
async def test_owner_gets_an_unavailable_card_when_the_panel_is_down(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    path: str,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/overview/{path}", headers=headers)

    assert response.status_code == 200
    assert response.json()["available"] is False


async def test_owner_can_get_attention(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/overview/attention", headers=headers)

    assert response.status_code == 200
    assert isinstance(response.json()["items"], list)
