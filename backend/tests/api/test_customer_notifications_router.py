import datetime
from datetime import timedelta, timezone
from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.config.cabinet import CabinetConfig
from app.core.constants import API_V1
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SessionAudience
from app.core.security import create_access_token, hash_refresh_token
from app.modules.auth.dto import CreateSessionDto
from app.modules.auth.repository import SessionRepository
from app.modules.customer_notifications.repository import CustomerNotificationRepository
from app.modules.notifications import NotificationRenderer, NotificationRendererFactory
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.container import make_test_container

_PUSH = "https://fcm.googleapis.com/fcm/send/abc"
_SUB = {"endpoint": _PUSH, "keys": {"p256dh": "p", "auth": "a"}}
_PURCHASED = "SubscriptionPurchasedEvent"
_FTL = {
    Locale.EN: (
        "ntf-customer-subscription-purchased = Active.\n    .title = Activated\n"
        "ntf-customer-transaction-refunded = Refunded { $money }.\n    .title = Refund\n"
    ),
    Locale.RU: (
        "ntf-customer-subscription-purchased = Активна.\n    .title = Подписка активирована\n"
    ),
}


class _Renderers:
    async def build(self) -> NotificationRenderer:
        return NotificationRenderer(_FTL, default_locale=Locale.EN)


def _fake_renderers() -> Provider:
    provider = Provider(scope=Scope.REQUEST)
    provider.provide(lambda: _Renderers(), provides=NotificationRendererFactory)
    return provider


@pytest.fixture
async def container(session: AsyncSession, config: AppConfig) -> AsyncIterator[AsyncContainer]:
    container = make_test_container(session, config, _fake_renderers())
    yield container
    await container.close()


@pytest.fixture
async def client(container: AsyncContainer, api_app: FastAPI) -> AsyncIterator[httpx.AsyncClient]:
    api_app.state.dishka_container = container
    transport = httpx.ASGITransport(app=api_app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as c:
        yield c


@pytest.fixture
def make_user(
    user_repository: UserRepository,
    session_repository: SessionRepository,
    uow: UnitOfWork,
    config: AppConfig,
):
    async def create(
        name: str,
        telegram_id: int,
        *,
        language: Locale = Locale.EN,
        audience: SessionAudience = SessionAudience.CABINET,
    ) -> tuple[UserDto, dict[str, str]]:
        async with uow:
            user = await user_repository.create(
                CreateUserDto(name=name, telegram_id=telegram_id, role=Role.USER, language=language)
            )
            await uow.commit()
        created = await session_repository.create(
            CreateSessionDto(
                user_id=user.id,
                refresh_token_hash=hash_refresh_token(f"ntf-{name}-{audience.value}"),
                ip_address="127.0.0.1",
                user_agent=None,
                expires_at=datetime.datetime.now(timezone.utc) + timedelta(days=30),
                audience=audience,
            )
        )
        token = create_access_token(user.id, created.id, config.jwt_secret.get_secret_value())
        return user, {"Authorization": f"Bearer {token}"}

    return create


async def _add(
    repository: CustomerNotificationRepository, uow: UnitOfWork, user_id: int, outbox_id: int
) -> None:
    async with uow:
        await repository.add(
            user_id=user_id,
            outbox_id=outbox_id,
            event_type=_PURCHASED,
            args={},
            subscription_id=None,
        )


async def test_feed_renders_in_user_language_and_marks_read(
    client: httpx.AsyncClient,
    make_user,
    session: AsyncSession,
    uow: UnitOfWork,
) -> None:
    user, headers = await make_user("ru-user", 910_001, language=Locale.RU)
    repository = CustomerNotificationRepository(session)
    await _add(repository, uow, user.id, 1)
    await _add(repository, uow, user.id, 2)

    feed = (await client.get(f"{API_V1}/notifications/me", headers=headers)).json()
    assert feed["unread_count"] == 2
    assert len(feed["items"]) == 2
    assert feed["items"][0]["title"] == "Подписка активирована"
    assert feed["items"][0]["read"] is False

    marked = await client.post(f"{API_V1}/notifications/me/actions/mark-read", headers=headers)
    assert marked.status_code == 204

    feed = (await client.get(f"{API_V1}/notifications/me", headers=headers)).json()
    assert feed["unread_count"] == 0
    assert all(item["read"] for item in feed["items"])


async def test_feed_is_own_only(
    client: httpx.AsyncClient, make_user, session: AsyncSession, uow: UnitOfWork
) -> None:
    mine, my_headers = await make_user("mine", 910_002)
    other, other_headers = await make_user("other", 910_003)
    await _add(CustomerNotificationRepository(session), uow, other.id, 1)

    feed = (await client.get(f"{API_V1}/notifications/me", headers=my_headers)).json()
    assert feed == {"items": [], "unread_count": 0}

    await client.post(f"{API_V1}/notifications/me/actions/mark-read", headers=my_headers)
    theirs = (await client.get(f"{API_V1}/notifications/me", headers=other_headers)).json()
    assert theirs["unread_count"] == 1


async def test_feed_requires_authentication(client: httpx.AsyncClient) -> None:
    assert (await client.get(f"{API_V1}/notifications/me")).status_code == 401


async def test_customer_can_subscribe_push(client: httpx.AsyncClient, make_user) -> None:
    _, headers = await make_user("pusher", 910_004)

    first = await client.post(
        f"{API_V1}/notifications/me/push-subscriptions", json=_SUB, headers=headers
    )
    again = await client.post(
        f"{API_V1}/notifications/me/push-subscriptions", json=_SUB, headers=headers
    )

    assert first.status_code == 201
    assert again.status_code == 200
    key = await client.get(f"{API_V1}/notifications/me/push/public-key", headers=headers)
    assert key.status_code == 200
    assert "public_key" in key.json()


async def test_customer_push_list_shows_cabinet_only(client: httpx.AsyncClient, make_user) -> None:
    _, cabinet = await make_user("both", 910_005)
    # a second, dashboard session of the same kind of user
    _, dashboard = await make_user("dash", 910_006, audience=SessionAudience.DASHBOARD)
    await client.post(f"{API_V1}/notifications/me/push-subscriptions", json=_SUB, headers=cabinet)
    other = {"endpoint": _PUSH + "2", "keys": {"p256dh": "p", "auth": "a"}}
    await client.post(
        f"{API_V1}/notifications/me/push-subscriptions", json=other, headers=dashboard
    )

    listed = (
        await client.get(f"{API_V1}/notifications/me/push-subscriptions", headers=cabinet)
    ).json()
    assert [i["endpoint"] for i in listed["items"]] == [_PUSH]
    assert listed["total"] == 1
    listed = (
        await client.get(f"{API_V1}/notifications/me/push-subscriptions", headers=dashboard)
    ).json()
    assert listed["total"] == 0


async def test_delete_foreign_subscription_404(client: httpx.AsyncClient, make_user) -> None:
    _, owner = await make_user("owner", 910_007)
    _, stranger = await make_user("stranger", 910_008)
    created = await client.post(
        f"{API_V1}/notifications/me/push-subscriptions", json=_SUB, headers=owner
    )
    sub_id = created.json()["id"]
    url = f"{API_V1}/notifications/me/push-subscriptions/{sub_id}"

    assert (await client.delete(url, headers=stranger)).status_code == 404
    assert (await client.delete(url, headers=owner)).status_code == 204


async def test_routes_reachable_through_cabinet_proxy(
    config: AppConfig, container: AsyncContainer
) -> None:
    app = get_app(
        config.model_copy(update={"cabinet": CabinetConfig(proxy_secret=SecretStr("s3cret"))})
    )
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as proxied:
        headers = {"X-Cabinet-Proxy-Secret": "s3cret"}
        for path in ("", "/push/public-key", "/push-subscriptions"):
            response = await proxied.get(f"{API_V1}/notifications/me{path}", headers=headers)
            assert response.status_code == 401, path


async def test_push_subscribe_is_rate_limited(client: httpx.AsyncClient, make_user) -> None:
    _, headers = await make_user("flood", 910_020)
    url = f"{API_V1}/notifications/me/push-subscriptions"

    for _ in range(10):
        assert (await client.post(url, json=_SUB, headers=headers)).status_code in (200, 201)
    blocked = await client.post(url, json=_SUB, headers=headers)

    assert blocked.status_code == 429
    assert blocked.json()["code"] == "RATE_LIMITED"


async def test_feed_skips_events_without_a_translation(
    client: httpx.AsyncClient, make_user, session: AsyncSession, uow: UnitOfWork
) -> None:
    user, headers = await make_user("stale", 910_021)
    repository = CustomerNotificationRepository(session)
    await _add(repository, uow, user.id, 1)
    async with uow:
        await repository.add(
            user_id=user.id, outbox_id=2, event_type="GoneEvent", args={}, subscription_id=None
        )

    feed = (await client.get(f"{API_V1}/notifications/me", headers=headers)).json()

    assert [i["event_type"] for i in feed["items"]] == [_PURCHASED]


async def test_feed_renders_derived_args(
    client: httpx.AsyncClient, make_user, session: AsyncSession, uow: UnitOfWork
) -> None:
    user, headers = await make_user("money", 910_010)
    async with uow:
        await CustomerNotificationRepository(session).add(
            user_id=user.id,
            outbox_id=1,
            event_type="TransactionRefundedEvent",
            args={"order_id": 1, "amount": "12.00", "currency": "USD"},
            subscription_id=None,
        )

    feed = (await client.get(f"{API_V1}/notifications/me", headers=headers)).json()

    assert feed["items"][0]["body"] == "Refunded $12."
