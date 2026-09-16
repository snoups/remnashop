import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

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
from app.core.enums import Locale, Role, SubscriptionStatus
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.api_tokens import get_api_tokens_providers
from app.modules.auth import get_auth_providers
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.blacklist import get_blacklist_providers
from app.modules.passkeys import get_passkey_revoker_providers
from app.modules.plans import get_plans_providers
from app.modules.pricing import get_pricing_providers
from app.modules.referrals import get_referrals_providers
from app.modules.settings import get_settings_providers
from app.modules.subscriptions import get_subscriptions_providers
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.translations import get_translations_providers
from app.modules.users import get_users_providers
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore, _user_payload, make_fake_remnawave_transport
from tests.modules.subscriptions.factories import make_plan_snapshot

_EXPIRE_AT = datetime.datetime(2030, 1, 1, tzinfo=timezone.utc)


class _TestRemnawaveProvider(Provider):
    scope = Scope.APP

    def __init__(self, store: FakeUserStore) -> None:
        super().__init__()
        self._store = store

    @provide
    def get_remnawave(self) -> RemnawaveSDK:
        transport, _, _ = make_fake_remnawave_transport(self._store)
        client = httpx.AsyncClient(transport=transport, base_url="http://fake-panel.test/api")
        return RemnawaveSDK(client=client)


@pytest.fixture
def remnawave_store() -> FakeUserStore:
    return {}


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


@pytest.fixture
async def test_container(
    session: AsyncSession, config: AppConfig, remnawave_store: FakeUserStore
) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_users_providers(),
        *get_passkey_revoker_providers(),
        *get_auth_providers(),
        *get_api_tokens_providers(),
        *get_plans_providers(),
        *get_pricing_providers(),
        *get_referrals_providers(),
        *get_settings_providers(),
        *get_translations_providers(),
        *get_subscriptions_providers(),
        *get_blacklist_providers(),
        _TestSessionProvider(session),
        _TestRemnawaveProvider(remnawave_store),
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
                login=f"substest{role.value}",
                password_hash=await hash_password("x", config.crypt_key.get_secret_value()),
                name=f"substest{role.value}",
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
        )
    )
    return create_access_token(user.id, session.id, config.jwt_secret.get_secret_value())


async def test_list_subscriptions_requires_admin_role(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.USER, user_repository, session_repository, uow, config)

    response = await client.get(
        f"{API_V1}/subscriptions", headers={"Authorization": f"Bearer {token}"}
    )

    assert response.status_code == 403


async def test_list_subscriptions_rejects_unauthenticated_request(
    client: httpx.AsyncClient,
) -> None:
    response = await client.get(f"{API_V1}/subscriptions")

    assert response.status_code == 401


async def test_owner_can_update_and_delete_subscription(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    remnawave_store: FakeUserStore,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    headers = {"Authorization": f"Bearer {token}"}
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=301))
    remnawave_store[7001] = _user_payload(user_id=7001, username="fake_7001", expire_at=_EXPIRE_AT)
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=7001,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=_EXPIRE_AT,
            url="https://example.com/sub/token",
            plan_snapshot=make_plan_snapshot(),
        )
    )

    update_response = await client.put(
        f"{API_V1}/subscriptions/{created.id}", headers=headers, json={"traffic_limit": 500}
    )
    assert update_response.status_code == 200
    assert update_response.json()["traffic_limit"] == 500
    assert update_response.json()["effective_traffic_limit"] == 500

    delete_response = await client.delete(f"{API_V1}/subscriptions/{created.id}", headers=headers)
    assert delete_response.status_code == 204

    list_response = await client.get(
        f"{API_V1}/subscriptions", headers=headers, params={"status": "DELETED"}
    )
    assert list_response.json()["items"][0]["status"] == "DELETED"


async def test_owner_can_manage_addon_lifecycle(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    headers = {"Authorization": f"Bearer {token}"}

    create_response = await client.post(
        f"{API_V1}/addons",
        headers=headers,
        json={"name": "traffic-10gb", "type": "TRAFFIC", "amount": 10, "base_price": "1.99"},
    )
    assert create_response.status_code == 201
    addon_id = create_response.json()["id"]

    base_price_response = await client.put(
        f"{API_V1}/addons/{addon_id}/base-price",
        headers=headers,
        json={"base_price": "2.49"},
    )
    assert base_price_response.status_code == 200
    assert base_price_response.json()["base_price"] == "2.49"

    delete_response = await client.delete(f"{API_V1}/addons/{addon_id}", headers=headers)
    assert delete_response.status_code == 204

    list_response = await client.get(f"{API_V1}/addons", headers=headers)
    assert list_response.json() == []
