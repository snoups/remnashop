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
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.pricing import PricingRepository
from app.modules.providers import get_module_providers
from app.modules.referrals.repository import ReferralRepository
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
    patch_response = await client.patch(
        f"{API_V1}/referrals/settings",
        json={"enabled": True, "max_level": 2, "reward_amounts": {"1": "5", "2": "2"}},
        headers=admin_auth_headers,
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["enabled"] is True
    assert patch_response.json()["max_level"] == 2

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
        f"{API_V1}/users/{user_id}/actions/adjust-points",
        json={"delta": "10"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert Decimal(response.json()["points"]) == Decimal("10")


async def test_adjust_user_points_rejects_a_fractional_delta(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str], user_id: int
) -> None:
    response = await client.post(
        f"{API_V1}/users/{user_id}/actions/adjust-points",
        json={"delta": "10.5"},
        headers=admin_auth_headers,
    )
    assert response.status_code == 422


async def test_list_referrals_returns_page(
    client: httpx.AsyncClient,
    admin_auth_headers: dict[str, str],
    user_repository: UserRepository,
    session: AsyncSession,
) -> None:
    referrer = await user_repository.create(CreateUserDto(name="inviter", telegram_id=900_201))
    referred = await user_repository.create(CreateUserDto(name="invitee", telegram_id=900_202))
    await ReferralRepository(session).create_referral(
        referrer_id=referrer.id, referred_id=referred.id, level=1
    )

    response = await client.get(
        f"{API_V1}/referrals", params={"level": 1}, headers=admin_auth_headers
    )

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["items"][0]
    assert item["referred"]["name"] == "invitee"
    assert item["referrer"]["name"] == "inviter"
    assert item["reward_count"] == 0
    assert item["reward_amounts"] == {}


async def test_list_referrals_rejects_out_of_range_level(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    response = await client.get(
        f"{API_V1}/referrals", params={"level": 4}, headers=admin_auth_headers
    )
    assert response.status_code == 422


async def test_days_require_paid_subscription_defaults_on_and_roundtrips(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    initial = await client.get(f"{API_V1}/referrals/settings", headers=admin_auth_headers)
    assert initial.json()["days_require_paid_subscription"] is True

    patched = await client.patch(
        f"{API_V1}/referrals/settings",
        json={"days_require_paid_subscription": False},
        headers=admin_auth_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["days_require_paid_subscription"] is False

    reset = await client.post(
        f"{API_V1}/referrals/settings/actions/reset", json={}, headers=admin_auth_headers
    )
    assert reset.json()["days_require_paid_subscription"] is True


async def test_adjust_user_bonus_days_updates_the_stats(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str], user_id: int
) -> None:
    response = await client.post(
        f"{API_V1}/users/{user_id}/actions/adjust-bonus-days",
        json={"delta": 9},
        headers=admin_auth_headers,
    )
    assert response.status_code == 200
    assert response.json()["bonus_days"] == 9


async def test_adjust_user_bonus_days_refuses_to_go_below_zero(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str], user_id: int
) -> None:
    response = await client.post(
        f"{API_V1}/users/{user_id}/actions/adjust-bonus-days",
        json={"delta": -1},
        headers=admin_auth_headers,
    )
    assert response.status_code == 400
    assert response.json()["code"] == "BONUS_DAYS_BELOW_ZERO"


async def test_adjust_user_bonus_days_rejects_an_absurd_delta(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str], user_id: int
) -> None:
    response = await client.post(
        f"{API_V1}/users/{user_id}/actions/adjust-bonus-days",
        json={"delta": 3_000_000_000},
        headers=admin_auth_headers,
    )
    assert response.status_code == 422


async def test_invitee_reward_defaults_off_and_roundtrips(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    initial = (await client.get(f"{API_V1}/referrals/settings", headers=admin_auth_headers)).json()
    assert initial["invitee_reward_type"] == "EXTRA_DAYS"
    assert initial["invitee_reward_amount"] == 0

    patched = await client.patch(
        f"{API_V1}/referrals/settings",
        json={"invitee_reward_type": "POINTS", "invitee_reward_amount": 50},
        headers=admin_auth_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["invitee_reward_type"] == "POINTS"
    assert patched.json()["invitee_reward_amount"] == 50

    reset = await client.post(
        f"{API_V1}/referrals/settings/actions/reset", json={}, headers=admin_auth_headers
    )
    assert reset.json()["invitee_reward_amount"] == 0


async def test_invitee_reward_amount_rejects_a_negative(
    client: httpx.AsyncClient, admin_auth_headers: dict[str, str]
) -> None:
    response = await client.patch(
        f"{API_V1}/referrals/settings",
        json={"invitee_reward_amount": -1},
        headers=admin_auth_headers,
    )
    assert response.status_code == 422
