from datetime import datetime, timezone
from typing import Any, Optional

import pytest
from redis.asyncio import Redis
from remnapy.models.webhook import UserDto as WebhookUserDto
from remnapy.models.webhook import WebhookPayloadDto
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import AppConfig
from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.ports import EventPublisher
from app.modules.subscriptions.dto import PublishPanelEventDto, RemnawaveWebhookDto
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    HandleRemnawaveWebhookUseCase,
    PublishPanelEventUseCase,
    SyncSubscriptionStatusUseCase,
)
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave_webhook import sign_webhook, user_event_payload
from tests.modules.subscriptions.factories import create_subscription

_LIFECYCLE_TYPES = (
    "SubscriptionExpiringEvent",
    "SubscriptionExpiredEvent",
    "SubscriptionTrafficLimitedEvent",
    "SubscriptionTrafficThresholdEvent",
)


def _use_case(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
    config: AppConfig,
) -> HandleRemnawaveWebhookUseCase:
    sync = SyncSubscriptionStatusUseCase(
        subscription_repository,
        uow,
        event_publisher,
        SubscriptionLifecycleService(subscription_repository),
    )
    publish = PublishPanelEventUseCase(
        subscription_repository, user_repository, uow, event_publisher
    )
    return HandleRemnawaveWebhookUseCase(sync, publish, config, redis)


async def _lifecycle_rows(session: AsyncSession) -> list[EventOutboxEntry]:
    result = await session.execute(
        select(EventOutboxEntry).where(EventOutboxEntry.event_type.in_(_LIFECYCLE_TYPES))
    )
    return list(result.scalars().all())


def _webhook(
    config: AppConfig,
    event: str,
    remnawave_user_id: int,
    status: str,
    meta: Optional[dict[str, Any]] = None,
) -> RemnawaveWebhookDto:
    payload = user_event_payload(event=event, remnawave_user_id=remnawave_user_id, status=status)
    if meta is not None:
        payload["meta"] = meta
    secret = config.remnawave.webhook_secret.get_secret_value()  # type: ignore[union-attr]
    body, headers = sign_webhook(payload, secret)
    return RemnawaveWebhookDto(body=body, headers=headers)


@pytest.mark.parametrize(
    ("event", "status", "meta", "expected_type", "expected_status"),
    [
        (
            "user.expiration",
            "ACTIVE",
            {"expiration": 72},
            "SubscriptionExpiringEvent",
            SubscriptionStatus.ACTIVE,
        ),
        (
            "user.expired",
            "EXPIRED",
            None,
            "SubscriptionExpiredEvent",
            SubscriptionStatus.EXPIRED,
        ),
        (
            "user.limited",
            "LIMITED",
            None,
            "SubscriptionTrafficLimitedEvent",
            SubscriptionStatus.LIMITED,
        ),
        (
            "user.bandwidth_usage_threshold_reached",
            "ACTIVE",
            None,
            "SubscriptionTrafficThresholdEvent",
            SubscriptionStatus.ACTIVE,
        ),
    ],
)
async def test_webhook_publishes_the_lifecycle_event_for_the_owner(
    session: AsyncSession,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
    config: AppConfig,
    event: str,
    status: str,
    meta: Optional[dict[str, Any]],
    expected_type: str,
    expected_status: SubscriptionStatus,
) -> None:
    subscription = await create_subscription(
        subscription_repository, user_repository, telegram_id=91001, remnawave_user_id=91001
    )
    use_case = _use_case(
        subscription_repository, user_repository, uow, event_publisher, redis, config
    )

    await use_case.system(_webhook(config, event, 91001, status, meta))

    rows = await _lifecycle_rows(session)
    assert [row.event_type for row in rows] == [expected_type]
    assert rows[0].payload["user"]["id"] == subscription.user_id
    assert rows[0].payload["subscription_id"] == subscription.id
    if meta:
        assert rows[0].payload["hours"] == 72
    refreshed = await subscription_repository.get_by_id(subscription.id)
    assert refreshed.status == expected_status


@pytest.mark.parametrize("meta", [{"expiration": 0}, None])
async def test_expiration_that_already_passed_publishes_nothing(
    session: AsyncSession,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
    config: AppConfig,
    meta: Optional[dict[str, Any]],
) -> None:
    await create_subscription(
        subscription_repository, user_repository, telegram_id=91002, remnawave_user_id=91002
    )
    use_case = _use_case(
        subscription_repository, user_repository, uow, event_publisher, redis, config
    )

    await use_case.system(_webhook(config, "user.expiration", 91002, "ACTIVE", meta))

    assert await _lifecycle_rows(session) == []


async def test_deleted_subscription_publishes_nothing(
    session: AsyncSession,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
    config: AppConfig,
) -> None:
    await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=91004,
        remnawave_user_id=91004,
        status=SubscriptionStatus.DELETED,
    )
    use_case = PublishPanelEventUseCase(
        subscription_repository, user_repository, uow, event_publisher
    )
    payload = WebhookPayloadDto.model_construct(
        event="user.expired",
        timestamp=datetime.now(timezone.utc),
        data=WebhookUserDto.model_construct(id=91004),
        meta=None,
    )

    await use_case.system(PublishPanelEventDto(payload=payload))

    assert await _lifecycle_rows(session) == []


async def test_unknown_remnawave_user_publishes_nothing(
    session: AsyncSession,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
    config: AppConfig,
) -> None:
    use_case = _use_case(
        subscription_repository, user_repository, uow, event_publisher, redis, config
    )

    await use_case.system(_webhook(config, "user.limited", 91999, "LIMITED"))

    assert await _lifecycle_rows(session) == []


async def test_publish_failure_does_not_fail_the_sync(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
    config: AppConfig,
) -> None:
    subscription = await create_subscription(
        subscription_repository, user_repository, telegram_id=91003, remnawave_user_id=91003
    )
    use_case = _use_case(
        subscription_repository, user_repository, uow, event_publisher, redis, config
    )

    class _Failing:
        async def system(self, data: Any) -> None:
            raise RuntimeError("publish failed")

    use_case._publish_panel_event_use_case = _Failing()  # type: ignore[assignment]

    await use_case.system(_webhook(config, "user.limited", 91003, "LIMITED"))

    refreshed = await subscription_repository.get_by_id(subscription.id)
    assert refreshed.status == SubscriptionStatus.LIMITED
