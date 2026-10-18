from dataclasses import replace
from uuid import uuid4

import pytest
from remnapy.enums import TrafficLimitStrategy
from sqlalchemy import func, select

from app.core.db.models import EventOutboxEntry
from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, SubscriptionStatus
from app.core.ports import EventPublisher
from app.modules.subscriptions.dto import PanelConfigDto, SyncSubscriptionStatusDto
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.panel_config import _base_limit
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import SyncSubscriptionStatusUseCase
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription


@pytest.mark.parametrize(
    ("panel", "bonus", "expected"),
    [
        (150, 50, (100, False)),  # the add-on stays on top of the base
        (200, 50, (150, False)),  # an admin raised the limit in the panel
        (0, 50, (0, False)),  # unlimited: add-ons have nothing to add
        (30, 50, (30, True)),  # below the add-ons: the panel value wins, add-ons go
        (50, 50, (50, True)),  # base 0 would read as unlimited
        (120, 0, (120, False)),
    ],
)
def test_base_limit(panel: int, bonus: int, expected: tuple[int, bool]) -> None:
    assert _base_limit(panel, bonus) == expected


def _config(**overrides: object) -> PanelConfigDto:
    config = PanelConfigDto(
        url="https://example.com/sub/1",
        traffic_limit=100,
        device_limit=3,
        traffic_limit_strategy=TrafficLimitStrategy.NO_RESET,
        tag=None,
        internal_squads=[],
        external_squad=None,
    )
    return replace(config, **overrides)  # type: ignore[arg-type]


def _use_case(
    subscription_repository: SubscriptionRepository, uow: UnitOfWork, publisher: EventPublisher
) -> SyncSubscriptionStatusUseCase:
    return SyncSubscriptionStatusUseCase(
        subscription_repository,
        uow,
        publisher,
        SubscriptionLifecycleService(subscription_repository),
    )


async def _config_events(session) -> int:  # type: ignore[no-untyped-def]
    return int(
        await session.scalar(
            select(func.count()).where(
                EventOutboxEntry.event_type == "SubscriptionConfigSyncedEvent"
            )
        )
        or 0
    )


async def test_panel_changes_land_in_the_row_with_add_ons_kept_on_top(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=88_001, remnawave_user_id=88_001
    )
    await subscription_repository.grant_entitlement(
        subscription_id=created.id, addon_id=None, addon_type=AddOnType.TRAFFIC, amount=50
    )
    squad = uuid4()
    before = await _config_events(session)

    result = await _use_case(subscription_repository, uow, event_publisher).system(
        SyncSubscriptionStatusDto(
            remnawave_user_id=88_001,
            status=SubscriptionStatus.ACTIVE,
            source="webhook",
            config=_config(
                url="https://example.com/sub/new",
                traffic_limit=250,
                device_limit=5,
                tag="VIP",
                internal_squads=[squad],
            ),
        )
    )

    assert result is not None
    assert (result.traffic_limit, result.effective_traffic_limit) == (200, 250)
    assert (result.device_limit, result.tag, result.url) == (
        5,
        "VIP",
        "https://example.com/sub/new",
    )
    assert result.internal_squads == [squad]
    assert len(result.addon_entitlements) == 1
    assert await _config_events(session) == before + 1


async def test_an_echo_of_our_own_push_changes_nothing(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    session,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=88_002, remnawave_user_id=88_002
    )
    subscription = await subscription_repository.grant_entitlement(
        subscription_id=created.id, addon_id=None, addon_type=AddOnType.DEVICES, amount=2
    )
    before = await _config_events(session)

    result = await _use_case(subscription_repository, uow, event_publisher).system(
        SyncSubscriptionStatusDto(
            remnawave_user_id=88_002,
            status=SubscriptionStatus.ACTIVE,
            source="webhook",
            config=_config(
                url=subscription.url,
                traffic_limit=subscription.effective_traffic_limit,
                device_limit=subscription.effective_device_limit,
            ),
        )
    )

    assert result is not None and result.device_limit == 3
    assert len(result.addon_entitlements) == 1
    assert await _config_events(session) == before


async def test_a_panel_limit_below_the_add_ons_drops_them(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=88_003, remnawave_user_id=88_003
    )
    await subscription_repository.grant_entitlement(
        subscription_id=created.id, addon_id=None, addon_type=AddOnType.TRAFFIC, amount=50
    )

    result = await _use_case(subscription_repository, uow, event_publisher).system(
        SyncSubscriptionStatusDto(
            remnawave_user_id=88_003,
            status=SubscriptionStatus.ACTIVE,
            source="webhook",
            config=_config(url=created.url, traffic_limit=30),
        )
    )

    assert result is not None
    assert (result.traffic_limit, result.effective_traffic_limit) == (30, 30)
    assert result.addon_entitlements == []
