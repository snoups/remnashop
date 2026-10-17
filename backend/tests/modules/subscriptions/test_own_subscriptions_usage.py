from datetime import timedelta

from remnapy import RemnawaveSDK

from app.core.db.uow import UnitOfWork
from app.core.utils.time import datetime_now
from app.modules.subscriptions.dto import CreateSubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import ListOwnSubscriptionsUsageUseCase
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
    use_case = ListOwnSubscriptionsUsageUseCase(subscription_repository, remnawave_sdk, uow)

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
    use_case = ListOwnSubscriptionsUsageUseCase(subscription_repository, remnawave_sdk, uow)

    result = await use_case(actor)

    assert [r.subscription.id for r in result] == [first.id, second.id]
    assert [r.used_traffic for r in result] == [42, None]
