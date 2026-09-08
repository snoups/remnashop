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
from app.core.enums import Locale, Role
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.analytics import get_analytics_providers
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import get_blacklist_providers
from app.modules.gateways import get_gateways_providers
from app.modules.payments import get_payments_providers
from app.modules.plans import get_plans_providers
from app.modules.pricing import get_pricing_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscriptions_providers
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
        *get_blacklist_providers(),
        *get_gateways_providers(),
        *get_plans_providers(),
        *get_referrals_providers(),
        *get_settings_providers(),
        *get_translations_providers(),
        *get_subscriptions_providers(),
        *get_payments_providers(),
        *get_pricing_providers(),
        *get_analytics_providers(),
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


async def _owner_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login="analyticstestowner",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="analyticstestowner",
                role=Role.OWNER,
                language=Locale.EN,
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-analytics-owner"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def _admin_without_analytics_view_headers(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> dict[str, str]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(
                login="analyticstestadmin",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name="analyticstestadmin",
                role=Role.ADMIN,
                language=Locale.EN,
                permission_revokes=["ANALYTICS_VIEW"],
            )
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token("test-refresh-token-analytics-admin"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return {"Authorization": f"Bearer {token}"}


async def test_get_analytics_requires_admin(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/analytics/overview")
    assert response.status_code == 401


async def test_owner_can_get_analytics_with_valid_days(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/analytics/overview?days=30", headers=headers)

    assert response.status_code == 200
    assert response.json()["days"] == 30


async def test_get_analytics_default_days_is_seven(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/analytics/overview", headers=headers)

    assert response.status_code == 200
    assert response.json()["days"] == 7


async def test_get_analytics_rejects_an_invalid_days_value(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _owner_headers(user_repository, session_repository, uow, config)

    response = await client.get(f"{API_V1}/analytics/overview?days=5", headers=headers)

    assert response.status_code == 422


async def test_admin_without_analytics_view_is_denied(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    headers = await _admin_without_analytics_view_headers(
        user_repository, session_repository, uow, config
    )

    response = await client.get(f"{API_V1}/analytics/overview", headers=headers)

    assert response.status_code == 403
