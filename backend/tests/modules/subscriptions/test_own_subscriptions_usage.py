from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock

from remnapy import RemnawaveSDK

from app.core.db.uow import UnitOfWork
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import CreateSubscriptionDto, PanelActivityDto, SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usage import PanelTrafficUsage
from app.modules.subscriptions.usecases import (
    GetSubscriptionUseCase,
    ListOwnSubscriptionsUsageUseCase,
)
from app.modules.users.repository import UserRepository
from tests.fakes.remnawave import FakeUserStore, _user_payload
from tests.modules.subscriptions.factories import create_subscription


def _panel_user(user_id: int, used: int) -> dict:
    payload = _user_payload(
        user_id=user_id, username=f"u{user_id}", expire_at=datetime_now() + timedelta(days=30)
    )
    payload["userTraffic"]["usedTrafficBytes"] = used
    return payload


async def test_reports_used_traffic_from_the_panel(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
) -> None:
    subscription = await create_subscription(
        subscription_repository, user_repository, telegram_id=78001, remnawave_user_id=78001
    )
    actor = await user_repository.find_by_id(subscription.user_id)
    assert actor is not None
    remnawave_store[78001] = _panel_user(78001, 5_000_000)
    use_case = ListOwnSubscriptionsUsageUseCase(
        subscription_repository, PanelTrafficUsage(remnawave_sdk), uow
    )

    result = await use_case(actor)

    assert [r.used_traffic for r in result] == [5_000_000]


async def test_a_panel_miss_leaves_used_traffic_empty(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
) -> None:
    first = await create_subscription(
        subscription_repository, user_repository, telegram_id=78011, remnawave_user_id=78011
    )
    second = await subscription_repository.create(
        CreateSubscriptionDto(
            **{
                **{f: getattr(first, f) for f in CreateSubscriptionDto.__dataclass_fields__},
                "remnawave_user_id": 78012,
                "url": "https://example.com/sub/78012",
            }
        )
    )
    actor = await user_repository.find_by_id(first.user_id)
    assert actor is not None
    remnawave_store[78011] = _panel_user(78011, 42)
    use_case = ListOwnSubscriptionsUsageUseCase(
        subscription_repository, PanelTrafficUsage(remnawave_sdk), uow
    )

    result = await use_case(actor)

    assert [r.subscription.id for r in result] == [first.id, second.id]
    assert [r.used_traffic for r in result] == [42, None]


async def test_the_admin_detail_reads_used_traffic_from_the_panel(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    remnawave_sdk: RemnawaveSDK,
    remnawave_store: FakeUserStore,
    uow: UnitOfWork,
) -> None:
    known = await create_subscription(
        subscription_repository, user_repository, telegram_id=78021, remnawave_user_id=78021
    )
    missing = await create_subscription(
        subscription_repository, user_repository, telegram_id=78022, remnawave_user_id=78022
    )
    remnawave_store[78021] = _panel_user(78021, 42)
    use_case = GetSubscriptionUseCase(
        subscription_repository, user_repository, PanelTrafficUsage(remnawave_sdk), uow
    )

    assert (await use_case.system(known.id)).activity.used_traffic == 42
    assert (await use_case.system(missing.id)).activity.used_traffic is None


async def test_activity_takes_the_newest_subscription_request() -> None:
    older = SimpleNamespace(
        request_at=datetime(2026, 11, 1, tzinfo=timezone.utc), user_agent="Happ/1.0"
    )
    newer = SimpleNamespace(
        request_at=datetime(2026, 11, 7, tzinfo=timezone.utc), user_agent="v2rayNG/1.9"
    )
    online_at = datetime(2026, 11, 8, tzinfo=timezone.utc)
    users = SimpleNamespace(
        get_user_by_id=AsyncMock(
            return_value=SimpleNamespace(used_traffic_bytes=7.0, online_at=online_at)
        ),
        get_user_subscription_request_history=AsyncMock(
            return_value=SimpleNamespace(records=[older, newer])
        ),
    )
    usage = PanelTrafficUsage(cast(RemnawaveSDK, SimpleNamespace(users=users)))

    activity = await usage.activity(
        cast(SubscriptionDto, SimpleNamespace(id=1, remnawave_user_id=5))
    )

    assert activity == PanelActivityDto(
        used_traffic=7,
        online_at=online_at,
        sub_last_opened_at=newer.request_at,
        sub_last_user_agent="v2rayNG/1.9",
    )


async def test_activity_keeps_the_history_when_the_user_lookup_fails() -> None:
    record = SimpleNamespace(
        request_at=datetime(2026, 11, 7, tzinfo=timezone.utc), user_agent="Happ/1.0"
    )
    users = SimpleNamespace(
        get_user_by_id=AsyncMock(side_effect=RuntimeError("panel down")),
        get_user_subscription_request_history=AsyncMock(
            return_value=SimpleNamespace(records=[record])
        ),
    )
    usage = PanelTrafficUsage(cast(RemnawaveSDK, SimpleNamespace(users=users)))

    activity = await usage.activity(
        cast(SubscriptionDto, SimpleNamespace(id=1, remnawave_user_id=5))
    )

    assert activity == PanelActivityDto(
        sub_last_opened_at=record.request_at, sub_last_user_agent="Happ/1.0"
    )
