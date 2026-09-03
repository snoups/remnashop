from datetime import datetime, timezone
from decimal import Decimal

from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription, make_plan_snapshot


async def test_sync_status_persists_a_legal_transition(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=601, remnawave_user_id=601001
    )
    service = SubscriptionLifecycleService(subscription_repository)

    async with uow:
        result = await service.sync_status(created.id, SubscriptionStatus.LIMITED)

    assert result.status is SubscriptionStatus.LIMITED


async def test_sync_status_is_a_noop_on_an_already_deleted_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=602, remnawave_user_id=602001
    )
    service = SubscriptionLifecycleService(subscription_repository)
    async with uow:
        await service.sync_status(created.id, SubscriptionStatus.DELETED)

    async with uow:
        result = await service.sync_status(created.id, SubscriptionStatus.ACTIVE)

    assert result.status is SubscriptionStatus.DELETED  # unchanged, no exception


async def test_renew_reactivates_an_expired_subscription(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    created = await create_subscription(
        subscription_repository, user_repository, telegram_id=603, remnawave_user_id=603001
    )
    service = SubscriptionLifecycleService(subscription_repository)
    async with uow:
        await service.sync_status(created.id, SubscriptionStatus.EXPIRED)

    new_expire_at = datetime(2027, 1, 1, tzinfo=timezone.utc)
    async with uow:
        result = await service.renew(created.id, new_expire_at)

    assert result.status is SubscriptionStatus.ACTIVE
    assert result.expire_at == new_expire_at


async def test_change_plan_in_place_applies_new_plan_and_stays_active(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    created = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=604,
        remnawave_user_id=604001,
        expire_at=datetime(2026, 1, 31, tzinfo=timezone.utc),
        price_paid=Decimal("300.00"),
        duration_days=30,
    )
    service = SubscriptionLifecycleService(subscription_repository)
    new_expire_at = datetime(2026, 3, 1, tzinfo=timezone.utc)

    async with uow:
        updated = await service.change_plan_in_place(
            created.id,
            new_plan_snapshot=make_plan_snapshot(plan_id=99, traffic_limit=200),
            new_expire_at=new_expire_at,
        )

    assert updated.id == created.id
    assert updated.status is SubscriptionStatus.ACTIVE
    assert updated.plan_snapshot.plan_id == 99
    assert updated.traffic_limit == 200
    assert updated.expire_at == new_expire_at
