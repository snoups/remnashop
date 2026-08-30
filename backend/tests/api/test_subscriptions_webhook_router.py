from typing import AsyncIterator

import httpx
import pytest
from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from dishka.integrations.fastapi import setup_dishka
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.app import get_app
from app.core.config import AppConfig
from app.core.constants import API_V1, REMNAWAVE_WEBHOOK_PATH
from app.core.di.providers import get_core_providers
from app.core.enums import SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.plans import get_plans_providers
from app.modules.subscriptions import get_subscriptions_providers
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave_webhook import sign_webhook, user_event_payload
from tests.modules.subscriptions.factories import make_plan_snapshot


class _TestSessionProvider(Provider):
    scope = Scope.REQUEST

    def __init__(self, session: AsyncSession) -> None:
        super().__init__()
        self._session = session

    @provide
    def get_session(self) -> AsyncSession:
        return self._session


@pytest.fixture
async def webhook_container(
    session: AsyncSession, config: AppConfig
) -> AsyncIterator[AsyncContainer]:
    providers = [
        *get_core_providers(),
        *get_plans_providers(),
        *get_subscriptions_providers(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: config})
    yield container
    await container.close()


@pytest.fixture
async def webhook_client(
    config: AppConfig, webhook_container: AsyncContainer
) -> AsyncIterator[httpx.AsyncClient]:
    app = get_app(config)
    setup_dishka(webhook_container, app)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as async_client:
        yield async_client


async def test_valid_webhook_syncs_status(
    webhook_client: httpx.AsyncClient,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    config: AppConfig,
) -> None:
    user = await user_repository.create(CreateUserDto(name="webhook_test_1", telegram_id=81001))
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=81001,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now(),
            url="https://fake-panel.test/sub/81001",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    secret = config.remnawave.webhook_secret.get_secret_value()  # type: ignore[union-attr]
    body, headers = sign_webhook(
        user_event_payload(event="user.limited", remnawave_user_id=81001, status="LIMITED"), secret
    )

    response = await webhook_client.post(
        f"{API_V1}{REMNAWAVE_WEBHOOK_PATH}", content=body, headers=headers
    )

    assert response.status_code == 200
    refreshed = await subscription_repository.get_by_id(created.id)
    assert refreshed.status == SubscriptionStatus.LIMITED


async def test_user_deleted_event_marks_the_subscription_deleted(
    webhook_client: httpx.AsyncClient,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    config: AppConfig,
) -> None:
    user = await user_repository.create(CreateUserDto(name="webhook_test_2", telegram_id=81002))
    created = await subscription_repository.create(
        CreateSubscriptionDto(
            user_id=user.id,
            remnawave_user_id=81002,
            status=SubscriptionStatus.ACTIVE,
            traffic_limit=100,
            device_limit=3,
            expire_at=datetime_now(),
            url="https://fake-panel.test/sub/81002",
            plan_snapshot=make_plan_snapshot(),
        )
    )
    secret = config.remnawave.webhook_secret.get_secret_value()  # type: ignore[union-attr]
    body, headers = sign_webhook(
        user_event_payload(event="user.deleted", remnawave_user_id=81002, status="ACTIVE"), secret
    )

    response = await webhook_client.post(
        f"{API_V1}{REMNAWAVE_WEBHOOK_PATH}", content=body, headers=headers
    )

    assert response.status_code == 200
    refreshed = await subscription_repository.get_by_id(created.id)
    assert refreshed.status == SubscriptionStatus.DELETED


async def test_invalid_signature_is_rejected(
    webhook_client: httpx.AsyncClient, config: AppConfig
) -> None:
    body, headers = sign_webhook(
        user_event_payload(event="user.limited", remnawave_user_id=81003, status="LIMITED"),
        "wrong-secret",
    )

    response = await webhook_client.post(
        f"{API_V1}{REMNAWAVE_WEBHOOK_PATH}", content=body, headers=headers
    )

    assert response.status_code == 401


async def test_unknown_remnawave_user_id_is_a_noop_200(
    webhook_client: httpx.AsyncClient, config: AppConfig
) -> None:
    secret = config.remnawave.webhook_secret.get_secret_value()  # type: ignore[union-attr]
    body, headers = sign_webhook(
        user_event_payload(event="user.limited", remnawave_user_id=999999999, status="LIMITED"),
        secret,
    )

    response = await webhook_client.post(
        f"{API_V1}{REMNAWAVE_WEBHOOK_PATH}", content=body, headers=headers
    )

    assert response.status_code == 200


async def test_non_user_event_is_a_noop_200(
    webhook_client: httpx.AsyncClient, config: AppConfig
) -> None:
    secret = config.remnawave.webhook_secret.get_secret_value()  # type: ignore[union-attr]
    # "node.created" would need a fully-populated WebhookNodeDto or from_dict
    # raises a pydantic ValidationError -- "service.panel_started" is the one
    # non-user event the SDK parses without requiring any data fields.
    body, headers = sign_webhook(
        {"event": "service.panel_started", "timestamp": "2026-01-01T00:00:00Z", "data": {}}, secret
    )

    response = await webhook_client.post(
        f"{API_V1}{REMNAWAVE_WEBHOOK_PATH}", content=body, headers=headers
    )

    assert response.status_code == 200


async def test_missing_signature_headers_returns_400(webhook_client: httpx.AsyncClient) -> None:
    response = await webhook_client.post(
        f"{API_V1}{REMNAWAVE_WEBHOOK_PATH}", content=b'{"event":"user.limited"}'
    )

    assert response.status_code == 400


async def test_malformed_user_hwid_devices_event_returns_400(
    webhook_client: httpx.AsyncClient, config: AppConfig
) -> None:
    # remnapy's WebhookPayloadDto.from_dict does data_raw["user"]/["hwidUserDevice"]
    # for this event category -- a validly-signed event missing either key
    # raises KeyError, not ValueError, inside parse_webhook itself.
    secret = config.remnawave.webhook_secret.get_secret_value()  # type: ignore[union-attr]
    payload = {"event": "user_hwid_devices.added", "timestamp": "2026-01-01T00:00:00Z", "data": {}}
    body, headers = sign_webhook(payload, secret)

    response = await webhook_client.post(
        f"{API_V1}{REMNAWAVE_WEBHOOK_PATH}", content=body, headers=headers
    )

    assert response.status_code == 400


async def test_missing_webhook_secret_returns_503(config: AppConfig, session: AsyncSession) -> None:
    unconfigured = config.model_copy(
        update={"remnawave": config.remnawave.model_copy(update={"webhook_secret": None})}
    )
    providers = [
        *get_core_providers(),
        *get_plans_providers(),
        *get_subscriptions_providers(),
        _TestSessionProvider(session),
    ]
    container = make_async_container(*providers, context={AppConfig: unconfigured})
    app = get_app(unconfigured)
    setup_dishka(container, app)
    transport = httpx.ASGITransport(app=app)

    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"{API_V1}{REMNAWAVE_WEBHOOK_PATH}",
            content=b"{}",
            headers={"X-Remnawave-Signature": "x", "X-Remnawave-Timestamp": "1"},
        )

    assert response.status_code == 503
    await container.close()
