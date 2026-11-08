from datetime import timedelta

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, Role, SubscriptionStatus
from app.core.exceptions import PermissionDeniedError
from app.core.utils.time import datetime_now
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.stats_repository import SubscriptionStatsRepository
from app.modules.subscriptions.usecases import GetSubscriptionListStatsUseCase
from app.modules.users.dto import UserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import create_subscription

OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def test_list_stats_counts_each_tile(
    subscription_repository: SubscriptionRepository,
    user_repository: UserRepository,
    session,
    uow: UnitOfWork,
) -> None:
    now = datetime_now()
    rows = [
        # paid active, expiring in 12h, connected never
        {"status": SubscriptionStatus.ACTIVE, "expire_at": now + timedelta(hours=12)},
        # paid active, expiring in 5 days
        {"status": SubscriptionStatus.ACTIVE, "expire_at": now + timedelta(days=5)},
        # paid active, far
        {"status": SubscriptionStatus.ACTIVE, "expire_at": now + timedelta(days=60)},
        # trial expiring soon: not counted as paid
        {
            "status": SubscriptionStatus.ACTIVE,
            "is_trial": True,
            "expire_at": now + timedelta(days=2),
        },
        {"status": SubscriptionStatus.LIMITED},
        {"status": SubscriptionStatus.DISABLED},
        {"status": SubscriptionStatus.EXPIRED, "expire_at": now - timedelta(days=1)},
    ]
    for offset, row in enumerate(rows):
        await create_subscription(
            subscription_repository,
            user_repository,
            telegram_id=831_000 + offset,
            remnawave_user_id=831_000 + offset,
            **row,
        )

    stats = await GetSubscriptionListStatsUseCase(SubscriptionStatsRepository(session), uow)(OWNER)

    assert (stats.paid_active, stats.active_trials) == (3, 1)
    assert (stats.expiring, stats.expiring_urgent) == (2, 1)
    assert (stats.limited, stats.disabled) == (1, 1)
    # ACTIVE + LIMITED, none ever connected
    assert (stats.paying, stats.paying_never_connected) == (4, 4)


async def test_list_stats_requires_permission(session, uow: UnitOfWork) -> None:
    with pytest.raises(PermissionDeniedError):
        await GetSubscriptionListStatsUseCase(SubscriptionStatsRepository(session), uow)(
            REGULAR_USER
        )
