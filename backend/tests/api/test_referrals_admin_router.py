import datetime
from datetime import timedelta, timezone
from decimal import Decimal
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
from app.core.enums import Locale, Role
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import get_blacklist_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
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
        *get_users_providers(),
        *get_auth_providers(),
        *get_api_tokens_providers(),
        *get_settings_providers(),
        *get_translations_providers(),
        *get_referrals_providers(),
        *get_blacklist_providers(),
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


@pytest.fixture
async def user_id(user_repository: UserRepository) -> int:
    user = await user_repository.create(CreateUserDto(name="referred", telegram_id=900_101))
    return user.id


@pytest.fixture
async def admin_auth_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        admin = await user_repository.create(
            CreateUserDto(
                login="referralsadmin",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="referralsadmin",
                role=Role.ADMIN,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=admin.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-referrals-admin"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    token = create_access_token(admin.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_get_referral_settings_requires_admin(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/referrals/settings")
    assert response.status_code == 401


async def test_update_then_get_referral_settings_roundtrip(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    put_response = await client.put(
        f"{API_V1}/referrals/settings",
        json={"enabled": True, "max_level": 2},
        headers=admin_auth_headers,
    )
    assert put_response.status_code == 200
    assert put_response.json()["enabled"] is True
    assert put_response.json()["max_level"] == 2

    get_response = await client.get(f"{API_V1}/referrals/settings", headers=admin_auth_headers)
    assert get_response.status_code == 200
    assert get_response.json()["max_level"] == 2


async def test_get_user_referral_stats_returns_404_for_a_missing_user(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    response = await client.get(f"{API_V1}/users/999999999/referrals", headers=admin_auth_headers)
    assert response.status_code == 404


async def test_get_user_referral_stats_returns_the_stats(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str], user_id: int
) -> None:
    response = await client.get(f"{API_V1}/users/{user_id}/referrals", headers=admin_auth_headers)
    assert response.status_code == 200
    body = response.json()
    assert Decimal(body["points"]) == Decimal("0")
    assert body["counts_by_level"] == {}


async def test_adjust_user_points_updates_and_returns_the_new_points(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str], user_id: int
) -> None:
    response = await client.post(
        f"{API_V1}/users/{user_id}/points",
        json={"delta": "10.50"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert Decimal(response.json()["points"]) == Decimal("10.50")
