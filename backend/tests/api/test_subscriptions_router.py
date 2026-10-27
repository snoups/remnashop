import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, provide
from fastapi import FastAPI
from remnapy import RemnawaveSDK
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PlanType, Role, SessionAudience, SubscriptionStatus
from app.core.security import create_access_token, hash_password, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.plans.dto import CreatePlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container
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


@pytest.fixture
async def test_container(
    session: AsyncSession, config: AppConfig, remnawave_store: FakeUserStore
) -> AsyncIterator[AsyncContainer]:
    container = make_test_container(session, config, _TestRemnawaveProvider(remnawave_store))
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
            audience=SessionAudience.DASHBOARD,
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

    update_response = await client.patch(
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
    assert list_response.json()["items"] == []


async def test_owner_can_grant_subscription(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    plan_repository: PlanRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    recipient = await user_repository.create(CreateUserDto(name="r", telegram_id=9301))
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="api-grant", name="g", type=PlanType.BOTH, traffic_limit=1, device_limit=1
        )
    )

    response = await client.post(
        f"{API_V1}/subscriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": recipient.id, "plan_id": plan.id, "duration_days": 7},
    )

    assert response.status_code == 201
    assert response.json()["user_id"] == recipient.id
    assert response.json()["plan_snapshot"]["plan_id"] == plan.id


async def test_grant_rejects_non_positive_duration(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)

    response = await client.post(
        f"{API_V1}/subscriptions",
        headers={"Authorization": f"Bearer {token}"},
        json={"user_id": 1, "plan_id": 1, "duration_days": 0},
    )

    assert response.status_code == 422


async def test_owner_can_change_subscription_plan(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    plan_repository: PlanRepository,
    uow: UnitOfWork,
    config: AppConfig,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    headers = {"Authorization": f"Bearer {token}"}
    recipient = await user_repository.create(CreateUserDto(name="r", telegram_id=9302))
    plan, other_plan = [
        await plan_repository.create(
            CreatePlanDto(
                public_code=code, name=code, type=PlanType.BOTH, traffic_limit=1, device_limit=1
            )
        )
        for code in ("api-change-a", "api-change-b")
    ]
    granted = (
        await client.post(
            f"{API_V1}/subscriptions",
            headers=headers,
            json={"user_id": recipient.id, "plan_id": plan.id, "duration_days": 20},
        )
    ).json()

    change = await client.post(
        f"{API_V1}/subscriptions/{granted['id']}/actions/change-plan",
        headers=headers,
        json={"plan_id": other_plan.id},
    )

    assert change.status_code == 200
    assert change.json()["plan_snapshot"]["plan_id"] == other_plan.id
    assert change.json()["expire_at"] == granted["expire_at"]


async def test_owner_can_set_subscription_expiry(
    client: httpx.AsyncClient,
    user_repository: UserRepository,
    session_repository: SessionRepository,
    subscription_repository: SubscriptionRepository,
    uow: UnitOfWork,
    config: AppConfig,
    remnawave_store: FakeUserStore,
) -> None:
    token = await _token_for(Role.OWNER, user_repository, session_repository, uow, config)
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9303))
    remnawave_store[7101] = _user_payload(user_id=7101, username="fake_7101", expire_at=_EXPIRE_AT)
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=7101,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=_EXPIRE_AT,
            url="https://example.com/sub/token",
            plan_snapshot=make_plan_snapshot(),
        )
    )

    response = await client.patch(
        f"{API_V1}/subscriptions/{created.id}",
        headers={"Authorization": f"Bearer {token}"},
        json={"expire_at": "2031-06-01T00:00:00Z"},
    )

    assert response.status_code == 200
    assert response.json()["expire_at"].startswith("2031-06-01")
    assert remnawave_store[7101]["expireAt"].startswith("2031-06-01")


async def test_owner_can_disable_and_enable_subscription(
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
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9304))
    remnawave_store[7102] = _user_payload(user_id=7102, username="fake_7102", expire_at=_EXPIRE_AT)
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=7102,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=_EXPIRE_AT,
            url="https://example.com/sub/token",
            plan_snapshot=make_plan_snapshot(),
        )
    )

    disabled = await client.post(
        f"{API_V1}/subscriptions/{created.id}/actions/disable", headers=headers
    )
    enabled = await client.post(
        f"{API_V1}/subscriptions/{created.id}/actions/enable", headers=headers
    )

    assert disabled.status_code == 200
    assert disabled.json()["status"] == "DISABLED"
    assert enabled.status_code == 200
    assert enabled.json()["status"] == "ACTIVE"


async def test_owner_can_reset_traffic_and_reissue_link(
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
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9305))
    remnawave_store[7103] = _user_payload(user_id=7103, username="fake_7103", expire_at=_EXPIRE_AT)
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=7103,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=_EXPIRE_AT,
            url="https://example.com/sub/token",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    base = f"{API_V1}/subscriptions/{created.id}/actions"

    reset = await client.post(f"{base}/reset-traffic", headers=headers)
    reissue = await client.post(f"{base}/reissue", headers=headers)

    assert reset.status_code == 200
    assert reissue.status_code == 200
    assert reissue.json()["url"] != "https://example.com/sub/token"


async def test_owner_can_list_subscription_devices(
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
    buyer = await user_repository.create(CreateUserDto(name="buyer", telegram_id=9306))
    remnawave_store[7104] = _user_payload(user_id=7104, username="fake_7104", expire_at=_EXPIRE_AT)
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=buyer.id,
            remnawave_user_id=7104,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=_EXPIRE_AT,
            url="https://example.com/sub/token",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    base = f"{API_V1}/subscriptions/{created.id}/devices"

    listed = await client.get(base, headers=headers)
    deleted = await client.delete(f"{base}/some-hwid", headers=headers)
    bulk = await client.post(f"{base}/bulk/delete", headers=headers)

    assert listed.status_code == 200
    assert listed.json() == {"items": [], "total": 0}
    assert deleted.status_code == 204
    assert bulk.status_code == 204
