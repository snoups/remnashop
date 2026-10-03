import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.di.providers import get_core_providers
from app.core.security import create_access_token, hash_refresh_token
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.pricing import PricingRepository
from app.modules.providers import get_module_providers
from app.modules.referrals.dto import UpdateReferralSettingsDto
from app.modules.referrals.repository import ReferralRepository
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


def _pricing_repository_provider() -> Provider:
    # just the repository: the settings usecases read the anchor currency from it
    provider = Provider(scope=Scope.REQUEST)
    provider.provide(PricingRepository)
    return provider


@pytest.fixture
async def test_container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_module_providers(),
        _pricing_repository_provider(),
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
        f"{API_V1}/referrals/actions/attach",
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
        f"{API_V1}/referrals/actions/attach",
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
        f"{API_V1}/referrals/actions/withdraw",
        json={"amount": "10.00"},
        headers=headers,
    )
    assert response.status_code == 400


async def test_withdraw_points_is_rate_limited_per_user(
    config: AppConfig,
    test_container: AsyncContainer,
    actor: tuple[UserDto, dict[str, str]],
    redis: Redis,
) -> None:
    # Each request is an audit-log row an admin reads to process payouts --
    # an unthrottled endpoint lets one user bury real requests, and a new
    # source address must not reset that budget.
    user, headers = actor
    app = get_app(config)
    setup_dishka(test_container, app)
    key = f"remnashop:ratelimit:points_withdraw:user:{user.id}"
    await redis.delete(key)

    responses = []
    for index in range(6):
        transport = httpx.ASGITransport(app=app, client=(f"203.0.113.{30 + index}", 12345))
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            responses.append(
                await client.post(
                    f"{API_V1}/referrals/actions/withdraw",
                    json={"amount": "10.00"},
                    headers=headers,
                )
            )

    await redis.delete(key)

    assert [r.status_code for r in responses] == [400] * 5 + [429]


async def test_api_token_cannot_use_customer_endpoints(
    client: httpx.AsyncClient,
    api_token_repository: ApiTokenRepository,
    referrer: tuple[UserDto, dict[str, str]],
    uow: UnitOfWork,
    enabled_referrals: None,
) -> None:
    # An API token is a staff credential with no customer identity behind it:
    # reaching a self-service route lands as user_id=0 and fails on a foreign
    # key instead of a clear refusal.
    referrer_user, _ = referrer
    secret = "test-api-token-secret"
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

    response = await client.post(
        f"{API_V1}/referrals/actions/attach",
        json={"code": referrer_user.referral_code},
        headers={"Authorization": f"Bearer {secret}"},
    )

    assert response.status_code == 403
