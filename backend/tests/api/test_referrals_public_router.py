import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import SessionAudience, SubscriptionStatus
from app.core.security import create_access_token, hash_refresh_token
from app.core.security.permissions import Permission
from app.modules.api_tokens.dto import CreateApiTokenDto
from app.modules.api_tokens.repository import ApiTokenRepository
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.pricing import PricingRepository
from app.modules.referrals.dto import UpdateReferralSettingsDto
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container
from tests.modules.subscriptions.factories import make_plan_snapshot


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
    test_container: AsyncContainer, api_app: FastAPI
) -> AsyncIterator[httpx.AsyncClient]:
    app = api_app
    app.state.dishka_container = test_container
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
            audience=SessionAudience.DASHBOARD,
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


async def test_stats_reflect_the_referrer(
    client: httpx.AsyncClient,
    actor: tuple[UserDto, dict[str, str]],
    referrer: tuple[UserDto, dict[str, str]],
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    actor_user, actor_headers = actor
    referrer_user, _ = referrer
    async with uow:
        await referral_repository.create_referral(
            referrer_id=referrer_user.id, referred_id=actor_user.id, level=1
        )

    stats_response = await client.get(f"{API_V1}/referrals/me", headers=actor_headers)
    assert stats_response.status_code == 200
    assert stats_response.json()["referrer_id"] == referrer_user.id


async def test_invited_list_shows_names_only_and_only_ones_own(
    client: httpx.AsyncClient,
    actor: tuple[UserDto, dict[str, str]],
    referrer: tuple[UserDto, dict[str, str]],
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    actor_user, actor_headers = actor
    referrer_user, referrer_headers = referrer
    async with uow:
        await referral_repository.create_referral(
            referrer_id=referrer_user.id, referred_id=actor_user.id, level=1
        )
        await uow.commit()

    listed = await client.get(f"{API_V1}/referrals/me/invited", headers=referrer_headers)
    assert listed.status_code == 200
    body = listed.json()
    assert body["total"] == 1
    item = body["items"][0]
    # the name and the level, nothing that reaches the person
    assert set(item) == {"name", "level", "created_at", "reward_amounts"}
    assert (item["name"], item["level"]) == (actor_user.name, 1)

    # the invitee has nobody below them
    own = await client.get(f"{API_V1}/referrals/me/invited", headers=actor_headers)
    assert own.json() == {"items": [], "total": 0}


async def test_manual_referral_attach_is_gone(
    client: httpx.AsyncClient, actor: tuple[UserDto, dict[str, str]]
) -> None:
    _, headers = actor
    response = await client.post(
        f"{API_V1}/referrals/actions/attach", json={"code": "ANY"}, headers=headers
    )
    assert response.status_code in (404, 405)


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
        f"{API_V1}/referrals/me/actions/redeem-days",
        json={"subscription_id": 1, "days": 1},
        headers={"Authorization": f"Bearer {secret}"},
    )

    assert response.status_code == 403


async def test_redeem_bonus_days_rejects_a_subscription_that_is_not_yours(
    client: httpx.AsyncClient, actor: tuple[UserDto, dict[str, str]]
) -> None:
    _, headers = actor
    response = await client.post(
        f"{API_V1}/referrals/me/actions/redeem-days",
        json={"subscription_id": 999_999_999, "days": 1},
        headers=headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "TARGET_SUBSCRIPTION_NOT_OWNED"


async def test_redeem_bonus_days_rejects_zero_days(
    client: httpx.AsyncClient, actor: tuple[UserDto, dict[str, str]]
) -> None:
    _, headers = actor
    response = await client.post(
        f"{API_V1}/referrals/me/actions/redeem-days",
        json={"subscription_id": 1, "days": 0},
        headers=headers,
    )
    assert response.status_code == 422


async def test_redeem_bonus_days_rejects_an_absurd_amount(
    client: httpx.AsyncClient, actor: tuple[UserDto, dict[str, str]]
) -> None:
    _, headers = actor
    response = await client.post(
        f"{API_V1}/referrals/me/actions/redeem-days",
        json={"subscription_id": 1, "days": 3651},
        headers=headers,
    )
    assert response.status_code == 422


async def test_own_stats_carry_the_program(
    client: httpx.AsyncClient,
    actor: tuple[UserDto, dict[str, str]],
    referral_repository: ReferralRepository,
    uow: UnitOfWork,
) -> None:
    _, headers = actor
    disabled = await client.get(f"{API_V1}/referrals/me", headers=headers)
    assert disabled.status_code == 200
    assert disabled.json()["program"]["enabled"] is False

    async with uow:
        await referral_repository.update_settings(UpdateReferralSettingsDto(enabled=True))
        await uow.commit()
    enabled = await client.get(f"{API_V1}/referrals/me", headers=headers)
    program = enabled.json()["program"]
    assert program["enabled"] is True
    assert {"reward_type", "reward_strategy", "reward_amounts"} <= program.keys()
    assert {"invitee_reward_type", "invitee_reward_amount"} <= program.keys()
    assert {"accrual_strategy", "max_level"} <= program.keys()


async def test_redeem_targets_list_the_actors_subscriptions_days_can_extend(
    client: httpx.AsyncClient,
    actor: tuple[UserDto, dict[str, str]],
    subscription_repository: SubscriptionRepository,
) -> None:
    actor_user, actor_headers = actor

    async def owned(remnawave_user_id: int, *, is_trial: bool = False) -> int:
        sub = await subscription_repository.create(
            CreateSubscriptionDto(
                user_id=actor_user.id,
                remnawave_user_id=remnawave_user_id,
                status=SubscriptionStatus.ACTIVE,
                is_trial=is_trial,
                traffic_limit=100,
                device_limit=3,
                expire_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
                url=f"https://example.com/sub/{remnawave_user_id}",
                plan_snapshot=make_plan_snapshot(),
            )
        )
        return sub.id

    paid = await owned(95001)
    await owned(95002, is_trial=True)

    response = await client.get(f"{API_V1}/referrals/me/redeem-targets", headers=actor_headers)

    assert response.status_code == 200
    assert response.json() == {"subscription_ids": [paid]}
