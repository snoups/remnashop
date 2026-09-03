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
from app.core.security import create_access_token, hash_refresh_token
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import get_blacklist_providers
from app.modules.referrals import get_referrals_providers
from app.modules.referrals.dto import UpdateReferralSettingsDto
from app.modules.referrals.repository import ReferralRepository
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


async def _create_user_with_headers(
    *,
    name: str,
    telegram_id: int,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> tuple[UserDto, dict[str, str]]:
    async with uow:
        user = await user_repository.create(CreateUserDto(name=name, telegram_id=telegram_id))
        await uow.commit()
    session = await session_repository.create(
        CreateSessionDto(
            user_id=user.id,
            refresh_token_hash=hash_refresh_token(f"test-refresh-token-{name}"),
            ip_address="127.0.0.1",
            user_agent=None,
            expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
        )
    )
    token = create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())
    return user, {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def actor(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> tuple[UserDto, dict[str, str]]:
    return await _create_user_with_headers(
        name="referrals-actor",
        telegram_id=900_201,
        user_repository=user_repository,
        session_repository=session_repository,
        uow=uow,
        config=config,
    )


@pytest.fixture
async def referrer(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> tuple[UserDto, dict[str, str]]:
    return await _create_user_with_headers(
        name="referrals-referrer",
        telegram_id=900_202,
        user_repository=user_repository,
        session_repository=session_repository,
        uow=uow,
        config=config,
    )


@pytest.fixture
async def enabled_referrals(referral_repository: ReferralRepository, uow: UnitOfWork) -> None:
    async with uow:
        await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True))
        await uow.commit()


async def test_get_my_referral_stats_requires_authentication(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{API_V1}/referrals/me")
    assert response.status_code == 401


async def test_attach_referral_rejects_own_code(
    client: httpx.AsyncClient,
    actor: tuple[UserDto, dict[str, str]],
    enabled_referrals: None,
) -> None:
    user, headers = actor
    response = await client.post(
        f"{API_V1}/referrals/attach",
        json={"code": user.referral_code},
        headers=headers,
    )
    assert response.status_code == 400


async def test_attach_referral_then_stats_reflect_the_referrer(
    client: httpx.AsyncClient,
    actor: tuple[UserDto, dict[str, str]],
    referrer: tuple[UserDto, dict[str, str]],
    enabled_referrals: None,
) -> None:
    actor_user, actor_headers = actor
    referrer_user, _ = referrer

    attach_response = await client.post(
        f"{API_V1}/referrals/attach",
        json={"code": referrer_user.referral_code},
        headers=actor_headers,
    )
    assert attach_response.status_code == 204

    stats_response = await client.get(f"{API_V1}/referrals/me", headers=actor_headers)
    assert stats_response.status_code == 200
    assert stats_response.json()["referrer_id"] == referrer_user.id


async def test_withdraw_points_rejects_amount_above_points(
    client: httpx.AsyncClient, actor: tuple[UserDto, dict[str, str]]
) -> None:
    _, headers = actor
    response = await client.post(
        f"{API_V1}/referrals/withdraw",
        json={"amount": "10.00"},
        headers=headers,
    )
    assert response.status_code == 400
