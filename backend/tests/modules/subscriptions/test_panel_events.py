from datetime import datetime, timezone
from typing import Any, Optional

import pytest
from remnapy.models.webhook import (
    BillingNodeDto,
    HwidUserDeviceDto,
    LoginAttemptDto,
    TorrentBlockerReportDto,
    UserHwidDeviceEventDto,
    WebhookMetaDto,
    WebhookNodeDto,
    WebhookPayloadDto,
)
from remnapy.models.webhook import (
    UserDto as WebhookUserDto,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.ports import EventPublisher
from app.modules.subscriptions.dto import PublishPanelEventDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import PublishPanelEventUseCase
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription

_RW_ID = 92001
_NOW = datetime(2026, 10, 16, tzinfo=timezone.utc)


def _user(rw_id: int = _RW_ID) -> WebhookUserDto:
    return WebhookUserDto.model_construct(id=rw_id)


def _node(name: str = "nl-1") -> WebhookNodeDto:
    return WebhookNodeDto.model_construct(name=name, last_status_message="timeout")


def _payload(event: str, data: Any, meta: Optional[WebhookMetaDto] = None) -> WebhookPayloadDto:
    return WebhookPayloadDto.model_construct(event=event, timestamp=_NOW, data=data, meta=meta)


def _device() -> UserHwidDeviceEventDto:
    device = HwidUserDeviceDto.model_construct(
        hwid="hw-1", platform="iOS", device_model="iPhone", os_version="18", request_ip="1.2.3.4"
    )
    return UserHwidDeviceEventDto.model_construct(
        data=type("D", (), {"user": _user(), "hwid_user_device": device})()
    )


def _torrent() -> TorrentBlockerReportDto:
    report = type(
        "R",
        (),
        {
            "action_report": type("A", (), {"ip": "5.6.7.8", "will_unblock_at": _NOW})(),
            "xray_report": type("X", (), {"destination": "tracker.example:6881"})(),
        },
    )()
    return TorrentBlockerReportDto.model_construct(node=_node(), user=_user(), report=report)


async def _rows(session: AsyncSession) -> list[EventOutboxEntry]:
    return list((await session.execute(select(EventOutboxEntry))).scalars().all())


@pytest.mark.parametrize(
    ("payload", "event_type", "fields"),
    [
        (_payload("user.first_connected", _user()), "SubscriptionFirstConnectedEvent", {}),
        (_payload("user.traffic_reset", _user()), "SubscriptionTrafficResetEvent", {}),
        (_payload("user.revoked", _user()), "SubscriptionRevokedEvent", {}),
        (
            _payload("user.not_connected", _user(), WebhookMetaDto(not_connected_after_hours=24)),
            "SubscriptionNotConnectedEvent",
            {"hours": 24},
        ),
        (
            _payload("user.expiration", _user(), WebhookMetaDto(expiration=-24)),
            "SubscriptionExpiredAgoEvent",
            {"hours": 24},
        ),
        (
            _payload("user_hwid_devices.added", _device()),
            "SubscriptionDeviceAddedEvent",
            {"hwid": "hw-1", "platform": "iOS"},
        ),
        (
            _payload("user_hwid_devices.deleted", _device()),
            "SubscriptionDeviceRemovedEvent",
            {"hwid": "hw-1"},
        ),
        (
            _payload("torrent_blocker.report", _torrent()),
            "TorrentBlockerReportEvent",
            {"node_name": "nl-1", "destination": "tracker.example:6881"},
        ),
    ],
)
async def test_customer_webhook_publishes_for_the_owner(
    session: AsyncSession,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    payload: WebhookPayloadDto,
    event_type: str,
    fields: dict[str, Any],
) -> None:
    subscription = await create_subscription(
        subscription_repository, user_repository, telegram_id=_RW_ID, remnawave_user_id=_RW_ID
    )
    use_case = PublishPanelEventUseCase(
        subscription_repository, user_repository, uow, event_publisher
    )

    await use_case.system(PublishPanelEventDto(payload=payload))

    rows = await _rows(session)
    assert [row.event_type for row in rows] == [event_type]
    assert rows[0].payload["user"]["id"] == subscription.user_id
    assert rows[0].payload["subscription_id"] == subscription.id
    for key, value in fields.items():
        assert rows[0].payload[key] == value


@pytest.mark.parametrize(
    ("payload", "event_type"),
    [
        (_payload("node.connection_lost", _node()), "NodeConnectionLostEvent"),
        (_payload("node.connection_restored", _node()), "NodeConnectionRestoredEvent"),
        (_payload("node.traffic_notify", _node()), "NodeTrafficReachedEvent"),
        (_payload("service.panel_started", {}), "PanelStartedEvent"),
        (
            _payload(
                "service.login_attempt_failed",
                LoginAttemptDto.model_construct(
                    username="root", ip="9.9.9.9", user_agent="curl", password="hunter2"
                ),
            ),
            "PanelLoginFailedEvent",
        ),
        (
            _payload(
                "crm.infra_billing_node_payment_in_7_days",
                BillingNodeDto.model_construct(
                    provider_name="Hetzner", node_name="de-1", next_billing_at=_NOW, login_url="u"
                ),
            ),
            "NodeBillingDueEvent",
        ),
    ],
)
async def test_infrastructure_webhook_publishes_a_system_event(
    session: AsyncSession,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    payload: WebhookPayloadDto,
    event_type: str,
) -> None:
    use_case = PublishPanelEventUseCase(
        subscription_repository, user_repository, uow, event_publisher
    )

    await use_case.system(PublishPanelEventDto(payload=payload))

    rows = await _rows(session)
    assert [row.event_type for row in rows] == [event_type]
    assert "password" not in rows[0].payload


@pytest.mark.parametrize(
    "payload",
    [
        _payload("user.modified", _user()),
        _payload("user.created", _user()),
        _payload("node.created", _node()),
        _payload("user.expiration", _user(), WebhookMetaDto(expiration=0)),
        _payload("user.first_connected", _user(rw_id=92999)),  # no shop subscription
    ],
)
async def test_skipped_webhooks_publish_nothing(
    session: AsyncSession,
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    payload: WebhookPayloadDto,
) -> None:
    await create_subscription(
        subscription_repository, user_repository, telegram_id=_RW_ID, remnawave_user_id=_RW_ID
    )
    use_case = PublishPanelEventUseCase(
        subscription_repository, user_repository, uow, event_publisher
    )

    await use_case.system(PublishPanelEventDto(payload=payload))

    assert await _rows(session) == []
