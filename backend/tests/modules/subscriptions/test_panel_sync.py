from datetime import timedelta

import pytest
from redis.asyncio import Redis
from remnapy import RemnawaveSDK

from app.core.constants import GB_TO_BYTES
from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PanelSyncDirection, Role, SubscriptionStatus
from app.core.exceptions import ConflictError
from app.core.ports import EventPublisher
from app.core.security.permissions import TOKEN_GRANTABLE_PERMISSIONS, Permission
from app.core.utils.time import datetime_now
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.panel_sync import release_panel_sync
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import (
    GetPanelSyncStatusUseCase,
    GetSubscriptionPanelDiffUseCase,
    PullSubscriptionFromPanelUseCase,
    PushSubscriptionToPanelUseCase,
    StartPanelSyncFromUseCase,
    SyncAllToPanelUseCase,
    SyncSubscriptionStatusUseCase,
)
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.subscriptions.factories import create_subscription

OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)


def _panel_user(remnawave_user_id: int, **overrides: object) -> dict[str, object]:
    payload = _user_payload(
        user_id=remnawave_user_id,
        username=f"rs_{remnawave_user_id}",
        expire_at=datetime_now() + timedelta(days=30),
        traffic_limit_bytes=100 * GB_TO_BYTES,
        hwid_device_limit=3,
    )
    payload["subscriptionUrl"] = f"https://example.com/sub/{remnawave_user_id}"
    payload.update(overrides)
    return payload


def _sync(
    subscription_repository: SubscriptionRepository, uow: UnitOfWork, publisher: EventPublisher
) -> SyncSubscriptionStatusUseCase:
    return SyncSubscriptionStatusUseCase(
        subscription_repository,
        uow,
        publisher,
        SubscriptionLifecycleService(subscription_repository),
    )


def test_bulk_syncs_are_not_token_grantable() -> None:
    assert Permission.SUBSCRIPTIONS_PANEL_SYNC_FROM not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.SUBSCRIPTIONS_PANEL_SYNC_TO not in TOKEN_GRANTABLE_PERMISSIONS
    assert Permission.SUBSCRIPTIONS_PUSH_TO_PANEL in TOKEN_GRANTABLE_PERMISSIONS


async def test_a_second_start_while_running_is_refused(
    redis: Redis, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    dispatch = RecordingDispatch()
    start = StartPanelSyncFromUseCase(redis, uow, event_publisher, dispatch)
    await release_panel_sync(redis, PanelSyncDirection.FROM_PANEL)
    try:
        started = await start(OWNER)
        assert started.running is True
        with pytest.raises(ConflictError):
            await start(OWNER)
        assert dispatch.messages == [{"direction": "FROM_PANEL"}]
        status = await GetPanelSyncStatusUseCase(redis)(OWNER)
        assert status.from_panel.running is True
    finally:
        await release_panel_sync(redis, PanelSyncDirection.FROM_PANEL)


async def test_sync_to_panel_pushes_rows_that_differ_and_counts_missing(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    redis: Redis,
) -> None:
    lagging = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_001, remnawave_user_id=89_001
    )
    in_sync = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_002, remnawave_user_id=89_002
    )
    await create_subscription(
        subscription_repository, user_repository, telegram_id=89_003, remnawave_user_id=89_003
    )
    remnawave_store[89_001] = _panel_user(
        89_001, trafficLimitBytes=10 * GB_TO_BYTES, expireAt=lagging.expire_at.isoformat()
    )
    remnawave_store[89_002] = _panel_user(89_002, expireAt=in_sync.expire_at.isoformat())

    result = await SyncAllToPanelUseCase(
        subscription_repository, remnawave_sdk, uow, redis, event_publisher
    ).system()

    assert remnawave_store[89_001]["trafficLimitBytes"] == 100 * GB_TO_BYTES
    assert result.updated >= 1 and result.missing >= 1
    status = await GetPanelSyncStatusUseCase(redis)(OWNER)
    assert status.to_panel.last is not None
    assert status.to_panel.last.direction is PanelSyncDirection.TO_PANEL


async def test_push_disables_the_panel_user_of_a_disabled_row(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    created = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=89_011,
        remnawave_user_id=89_011,
        status=SubscriptionStatus.DISABLED,
    )
    remnawave_store[89_011] = _panel_user(89_011)

    await PushSubscriptionToPanelUseCase(
        subscription_repository, user_repository, remnawave_sdk, event_publisher, uow
    )(OWNER, created.id)

    assert remnawave_store[89_011]["status"] == "DISABLED"


async def test_push_without_a_panel_user_is_a_conflict(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_021, remnawave_user_id=89_021
    )

    with pytest.raises(ConflictError):
        await PushSubscriptionToPanelUseCase(
            subscription_repository, user_repository, remnawave_sdk, event_publisher, uow
        )(OWNER, created.id)


async def test_diff_lists_fields_that_differ_and_pull_takes_them(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_031, remnawave_user_id=89_031
    )
    remnawave_store[89_031] = _panel_user(
        89_031, hwidDeviceLimit=7, tag="VIP", expireAt=created.expire_at.isoformat()
    )

    diff = await GetSubscriptionPanelDiffUseCase(
        subscription_repository, user_repository, remnawave_sdk, uow
    )(OWNER, created.id)

    assert diff.missing_in_panel is False
    assert {f.field: (f.shop, f.panel) for f in diff.fields} == {
        "device_limit": ("3", "7"),
        "tag": ("", "VIP"),
    }

    pulled = await PullSubscriptionFromPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        _sync(subscription_repository, uow, event_publisher),
        event_publisher,
        uow,
    )(OWNER, created.id)

    assert (pulled.device_limit, pulled.tag) == (7, "VIP")


async def test_pull_marks_a_subscription_gone_from_the_panel_deleted(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=89_041, remnawave_user_id=89_041
    )

    pulled = await PullSubscriptionFromPanelUseCase(
        subscription_repository,
        user_repository,
        remnawave_sdk,
        _sync(subscription_repository, uow, event_publisher),
        event_publisher,
        uow,
    )(OWNER, created.id)

    assert pulled.status is SubscriptionStatus.DELETED
