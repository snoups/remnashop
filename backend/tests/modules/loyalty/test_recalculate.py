from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.models.transaction import Transaction
from app.core.db.models.user import User
from app.core.db.uow import UnitOfWork
from app.core.enums import TransactionStatus
from app.modules.loyalty.dto import RecalculateLoyaltyDto
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.usecases import RecalculateLoyaltyDiscountsUseCase
from app.modules.transactions import TransactionRepository
from app.modules.users.repository import UserRepository
from tests.modules.loyalty.factories import make_user, paid_order, save_settings


def _use_case(session: AsyncSession, uow: UnitOfWork) -> RecalculateLoyaltyDiscountsUseCase:
    return RecalculateLoyaltyDiscountsUseCase(
        LoyaltyRepository(session), TransactionRepository(session), UserRepository(session), uow
    )


async def _discount(user_repository: UserRepository, user_id: int) -> int:
    user = await user_repository.get_by_id(user_id)
    assert user is not None
    return user.loyalty_discount


async def test_recalculate_assigns_the_reached_tier_and_writes_only_changes(
    session: AsyncSession, uow: UnitOfWork, user_repository: UserRepository
) -> None:
    await save_settings(session)
    buyer = await make_user(user_repository, 980_001)
    await paid_order(session, buyer, "60")
    await paid_order(session, buyer, "40")

    changed = await _use_case(session, uow).system(RecalculateLoyaltyDto(user_ids=[buyer]))
    again = await _use_case(session, uow).system(RecalculateLoyaltyDto(user_ids=[buyer]))

    assert await _discount(user_repository, buyer) == 3
    assert (changed, again) == (1, 0)


async def test_recalculate_drops_payments_outside_the_window(
    session: AsyncSession, uow: UnitOfWork, user_repository: UserRepository
) -> None:
    await save_settings(session, window_months=1)
    buyer = await make_user(user_repository, 980_002)
    await paid_order(session, buyer, "600", days_ago=40)

    await _use_case(session, uow).system(RecalculateLoyaltyDto(user_ids=[buyer]))

    assert await _discount(user_repository, buyer) == 0


async def test_recalculate_ignores_refunded_orders(
    session: AsyncSession, uow: UnitOfWork, user_repository: UserRepository
) -> None:
    await save_settings(session)
    buyer = await make_user(user_repository, 980_003)
    order_id = await paid_order(session, buyer, "600")
    await session.execute(
        update(Transaction)
        .where(Transaction.id == order_id)
        .values(status=TransactionStatus.REFUNDED)
    )

    await _use_case(session, uow).system(RecalculateLoyaltyDto(user_ids=[buyer]))

    assert await _discount(user_repository, buyer) == 0


async def test_recalculate_excluded_user_gets_zero(
    session: AsyncSession, uow: UnitOfWork, user_repository: UserRepository
) -> None:
    await save_settings(session)
    buyer = await make_user(user_repository, 980_004)
    await paid_order(session, buyer, "600")
    await session.execute(update(User).where(User.id == buyer).values(loyalty_excluded=True))

    await _use_case(session, uow).system(RecalculateLoyaltyDto(user_ids=[buyer]))

    assert await _discount(user_repository, buyer) == 0


async def test_full_recalculation_zeroes_everyone_when_disabled(
    session: AsyncSession, uow: UnitOfWork, user_repository: UserRepository
) -> None:
    await save_settings(session)
    buyer = await make_user(user_repository, 980_005)
    await paid_order(session, buyer, "600")
    await _use_case(session, uow).system(RecalculateLoyaltyDto())
    assert await _discount(user_repository, buyer) == 10

    await save_settings(session, enabled=False)
    await _use_case(session, uow).system(RecalculateLoyaltyDto())

    assert await _discount(user_repository, buyer) == 0


async def test_full_recalculation_zeroes_users_whose_payments_left_the_window(
    session: AsyncSession, uow: UnitOfWork, user_repository: UserRepository
) -> None:
    await save_settings(session, window_months=1)
    buyer = await make_user(user_repository, 980_006)
    await session.execute(update(User).where(User.id == buyer).values(loyalty_discount=10))
    await paid_order(session, buyer, "600", days_ago=40)

    await _use_case(session, uow).system(RecalculateLoyaltyDto())

    assert await _discount(user_repository, buyer) == 0
