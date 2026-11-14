from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.utils.time import datetime_now
from app.modules.subscriptions.lifecycle import SubscriptionLifecycleService
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription


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
        result = await service.renew(
            created.id,
            new_expire_at,
            paid=Decimal(0),
            days=30,
            previous_expire_at=created.expire_at,
        )

    assert result.status is SubscriptionStatus.ACTIVE
    assert result.expire_at == new_expire_at


@pytest.mark.parametrize(
    ("expire_in_days", "credit_paid"), [(-1, Decimal("100")), (5, Decimal("400"))]
)
async def test_renew_restarts_the_credit_only_for_a_lapsed_term(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    expire_in_days: int,
    credit_paid: Decimal,
) -> None:
    created = await create_subscription(
        subscription_repository,
        user_repository,
        telegram_id=604 + expire_in_days + 10,
        remnawave_user_id=604_100 + expire_in_days + 10,
        expire_at=datetime_now() + timedelta(days=expire_in_days),
        price_paid=Decimal("300"),
        duration_days=30,
    )
    service = SubscriptionLifecycleService(subscription_repository)

    async with uow:
        result = await service.renew(
            created.id,
            datetime_now() + timedelta(days=60),
            paid=Decimal("100"),
            days=30,
            previous_expire_at=created.expire_at,
        )

    assert result.plan_snapshot.effective_credit_paid == credit_paid
