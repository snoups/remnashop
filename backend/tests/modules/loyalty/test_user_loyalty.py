from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.actor import SyntheticActor
from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.exceptions import NotFoundError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.modules.loyalty.dto import LoyaltyTierDto, SetUserLoyaltyExcludedDto
from app.modules.loyalty.repository import LoyaltyRepository
from app.modules.loyalty.usecases import GetUserLoyaltyUseCase, SetUserLoyaltyExcludedUseCase
from app.modules.pricing import PricingRepository
from app.modules.transactions import TransactionRepository
from app.modules.users.dto import CreateUserDto, UserDto
from app.modules.users.repository import UserRepository
from tests.fakes.dispatch import RecordingDispatch
from tests.modules.loyalty.factories import make_user, paid_order, save_settings

ADMIN = UserDto(name="admin", role=Role.ADMIN)


def _set_excluded(
    session: AsyncSession,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    dispatch: RecordingDispatch,
) -> SetUserLoyaltyExcludedUseCase:
    return SetUserLoyaltyExcludedUseCase(
        LoyaltyRepository(session),
        TransactionRepository(session),
        UserRepository(session),
        PricingRepository(session),
        uow,
        event_publisher,
        dispatch,
    )


async def test_get_user_loyalty_reports_spend_and_next_tier(
    session: AsyncSession, uow: UnitOfWork, user_repository: UserRepository
) -> None:
    await save_settings(session, window_months=None)
    buyer = await make_user(user_repository, 990_001)
    await paid_order(session, buyer, "150")

    loyalty = await GetUserLoyaltyUseCase(
        LoyaltyRepository(session),
        TransactionRepository(session),
        user_repository,
        PricingRepository(session),
        uow,
    )(ADMIN, buyer)

    assert loyalty.spent == Decimal("150")
    assert loyalty.next_tier == LoyaltyTierDto(threshold=Decimal("500"), percent=10)


async def test_exclusion_dispatches_a_per_user_recalculation(
    session: AsyncSession,
    uow: UnitOfWork,
    user_repository: UserRepository,
    event_publisher: EventPublisher,
) -> None:
    buyer = await make_user(user_repository, 990_002)
    dispatch = RecordingDispatch()

    result = await _set_excluded(session, uow, event_publisher, dispatch)(
        ADMIN, SetUserLoyaltyExcludedDto(user_id=buyer, excluded=True)
    )

    assert result.excluded is True
    assert dispatch.messages == [{"user_ids": [buyer]}]


async def test_exclusion_of_a_staff_account_needs_admins_manage(
    session: AsyncSession,
    uow: UnitOfWork,
    user_repository: UserRepository,
    event_publisher: EventPublisher,
) -> None:
    staff = await user_repository.create(
        CreateUserDto(name="s", role=Role.ADMIN, login="loyaltystaff")
    )

    with pytest.raises(NotFoundError):
        await _set_excluded(session, uow, event_publisher, RecordingDispatch())(
            ADMIN, SetUserLoyaltyExcludedDto(user_id=staff.id, excluded=True)
        )


async def test_a_token_cannot_read_a_staff_accounts_loyalty(
    session: AsyncSession, uow: UnitOfWork, user_repository: UserRepository
) -> None:
    async with uow:
        owner = await user_repository.create(CreateUserDto(name="owner", role=Role.OWNER))
    token = SyntheticActor(
        id=0,
        role=Role.USER,
        name="API Token: loyalty",
        is_privileged=True,
        log="[api_token:loyalty]",
        permission_grants=[Permission.USERS_LOYALTY_VIEW.value],
    )
    use_case = GetUserLoyaltyUseCase(
        LoyaltyRepository(session),
        TransactionRepository(session),
        user_repository,
        PricingRepository(session),
        uow,
    )

    with pytest.raises(NotFoundError):
        await use_case(token, owner.id)
