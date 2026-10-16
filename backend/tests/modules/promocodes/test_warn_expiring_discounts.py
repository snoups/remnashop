from datetime import timedelta
from uuid import uuid4

from redis.asyncio import Redis

from app.core.db.uow import UnitOfWork
from app.core.enums import PromocodeRewardType
from app.core.utils.time import datetime_now
from app.modules.promocodes.dto import CreatePromocodeDto, PromocodeDto, UpdatePromocodeDto
from app.modules.promocodes.events import PromocodeDiscountExpiringEvent
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.usecases import WarnExpiringPromocodeDiscountsUseCase
from app.modules.users.dto import CreateUserDto, UpdateUserDto
from app.modules.users.repository import UserRepository
from tests.fakes.events import RecordingEventPublisher


async def _promocode(
    repository: PromocodeRepository, expires_in: timedelta, *, is_active: bool = True
) -> PromocodeDto:
    created = await repository.create(
        CreatePromocodeDto(
            code=uuid4().hex[:12].upper(),
            reward_type=PromocodeRewardType.PERSONAL_DISCOUNT,
            reward=10,
            expires_at=datetime_now() + expires_in,
        )
    )
    if is_active:
        return created
    return await repository.update(UpdatePromocodeDto(promocode_id=created.id, is_active=False))


async def _customer(
    repository: UserRepository, telegram_id: int, personal: PromocodeDto, purchase: PromocodeDto
) -> int:
    user = await repository.create(CreateUserDto(name="Ann", telegram_id=telegram_id))
    await repository.update_fields(
        user.id,
        UpdateUserDto(
            personal_discount=15,
            personal_discount_promocode_id=personal.id,
            purchase_discount=30,
            purchase_discount_promocode_id=purchase.id,
        ),
    )
    return user.id


async def test_warns_once_per_customer_and_promocode_before_expiry(
    promocode_repository: PromocodeRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    redis: Redis,
) -> None:
    soon = await _promocode(promocode_repository, timedelta(hours=5, minutes=30))
    later = await _promocode(promocode_repository, timedelta(days=3))
    inactive = await _promocode(promocode_repository, timedelta(hours=2), is_active=False)
    both = await _customer(user_repository, 9_100_001, soon, soon)
    mixed = await _customer(user_repository, 9_100_002, later, soon)
    await _customer(user_repository, 9_100_003, later, inactive)
    publisher = RecordingEventPublisher()
    use_case = WarnExpiringPromocodeDiscountsUseCase(
        promocode_repository, user_repository, uow, publisher, redis
    )

    assert await use_case.system() == 2
    events = sorted(publisher.events, key=lambda event: event.user.id)  # type: ignore[attr-defined]
    assert all(isinstance(event, PromocodeDiscountExpiringEvent) for event in events)
    assert [(e.user.id, e.percent, e.hours) for e in events] == [  # type: ignore[attr-defined]
        (both, 30, 6),
        (mixed, 30, 6),
    ]

    assert await use_case.system() == 0
