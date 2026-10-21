import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import AccessMode, Role, SessionAudience
from app.core.security import create_access_token, hash_refresh_token
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.pricing import PricingRepository
from app.modules.settings import SettingsRepository
from app.modules.settings.dto import UpdateAccessSettingsDto
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container


def _pricing_repository_provider() -> Provider:
    # just the repository: the settings usecases read the anchor currency from it
    provider = Provider(scope=Scope.REQUEST)
    provider.provide(PricingRepository)
    return provider


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    container = make_test_container(session, config, _pricing_repository_provider())
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


async def _create_user_with_headers(
    *,
    name: str,
    telegram_id: int,
    role: Role = Role.USER,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> tuple[UserDto, dict[str, str]]:
    async with uow:
        user = await user_repository.create(
            CreateUserDto(name=name, telegram_id=telegram_id, role=role)
        )
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{name}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
            audience=SessionAudience.DASHBOARD,
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return user, {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def customer(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> tuple[UserDto, dict[str, str]]:
    return await _create_user_with_headers(
        name="access-customer",
        telegram_id=900_301,
        user_repository=user_repository,
        session_repository=session_repository,
        uow=uow,
        config=config,
    )


@pytest.fixture
async def admin(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> tuple[UserDto, dict[str, str]]:
    return await _create_user_with_headers(
        name="access-admin",
        telegram_id=900_302,
        role=Role.ADMIN,
        user_repository=user_repository,
        session_repository=session_repository,
        uow=uow,
        config=config,
    )


async def _restrict(settings_repository: SettingsRepository, uow: UnitOfWork) -> None:
    async with uow:
        await settings_repository.update_access_settings(
            UpdateAccessSettingsDto(mode=AccessMode.RESTRICTED)
        )
        await uow.commit()


async def test_customer_route_is_refused_in_restricted_mode(
    client: httpx.AsyncClient,
    customer: tuple[UserDto, dict[str, str]],
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    await _restrict(settings_repository, uow)

    response = await client.get(f"{API_V1}/referrals/me", headers=customer[1])

    assert response.status_code == 403
    assert response.json()["code"] == "ACCESS_RESTRICTED"


async def test_staff_passes_restricted_mode(
    client: httpx.AsyncClient,
    admin: tuple[UserDto, dict[str, str]],
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    await _restrict(settings_repository, uow)

    response = await client.get(f"{API_V1}/referrals/me", headers=admin[1])

    assert response.status_code != 403


async def test_api_token_on_a_customer_route_is_refused_as_not_a_user(
    client: httpx.AsyncClient,
    api_token_repository: ApiTokenRepository,
    settings_repository: SettingsRepository,
    uow: UnitOfWork,
) -> None:
    await _restrict(settings_repository, uow)
    secret = "test-access-api-token"
    async with uow:
        await api_token_repository.create(
            CreateApiTokenDto(
                name="script",
                token_hash=hash_refresh_token(secret),
                scopes=[Permission.USERS_VIEW.value],
                created_by_user_id=None,
                expires_at=None,
            )
        )

    response = await client.get(
        f"{API_V1}/referrals/me", headers={"Authorization": f"Bearer {secret}"}
    )

    assert response.status_code == 403
    assert response.json()["code"] == "USER_ACCOUNT_REQUIRED"
