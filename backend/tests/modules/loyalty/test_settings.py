from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db.uow import UnitOfWork
from app.core.enums import Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.modules.loyalty.dto import LoyaltyTierDto, UpdateLoyaltySettingsDto
from app.modules.loyalty.repository import DEFAULT_TIERS, LoyaltyRepository
from app.modules.loyalty.usecases import (
    GetLoyaltySettingsUseCase,
    ResetLoyaltySettingsUseCase,
    UpdateLoyaltySettingsUseCase,
)
from app.modules.pricing import PricingRepository
from app.modules.users.dto import UserDto
from tests.fakes.dispatch import RecordingDispatch

OWNER = UserDto(name="owner", role=Role.OWNER)


def _update_use_case(
    session: AsyncSession,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    dispatch: RecordingDispatch,
) -> UpdateLoyaltySettingsUseCase:
    return UpdateLoyaltySettingsUseCase(
        LoyaltyRepository(session), PricingRepository(session), event_publisher, uow, dispatch
    )


async def test_settings_round_trip_and_default(
    session: AsyncSession, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    get = GetLoyaltySettingsUseCase(LoyaltyRepository(session), PricingRepository(session), uow)

    default = await get(OWNER)
    assert (default.enabled, default.window_months, default.tiers) == (
        False,
        None,
        list(DEFAULT_TIERS),
    )

    data = UpdateLoyaltySettingsDto(
        enabled=True,
        window_months=12,
        tiers=[LoyaltyTierDto(threshold=Decimal("1000"), percent=3)],
    )
    saved = await _update_use_case(session, uow, event_publisher, RecordingDispatch())(OWNER, data)

    assert (saved.enabled, saved.window_months, saved.tiers) == (True, 12, data.tiers)
    assert saved.anchor_currency is not None
    assert (await get(OWNER)).tiers == data.tiers


async def test_update_rejects_invalid_tiers(
    session: AsyncSession, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    with pytest.raises(ValidationError):
        await _update_use_case(session, uow, event_publisher, RecordingDispatch())(
            OWNER,
            UpdateLoyaltySettingsDto(
                enabled=True,
                window_months=None,
                tiers=[LoyaltyTierDto(threshold=Decimal("1000"), percent=0)],
            ),
        )


async def test_update_dispatches_a_full_recalculation(
    session: AsyncSession, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    dispatch = RecordingDispatch()
    await _update_use_case(session, uow, event_publisher, dispatch)(
        OWNER, UpdateLoyaltySettingsDto(enabled=False, window_months=None, tiers=[])
    )

    assert dispatch.messages == [{"user_ids": None}]


async def test_update_requires_a_tier_to_enable(
    session: AsyncSession, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    with pytest.raises(ValidationError) as caught:
        await _update_use_case(session, uow, event_publisher, RecordingDispatch())(
            OWNER, UpdateLoyaltySettingsDto(enabled=True, window_months=None, tiers=[])
        )
    assert caught.value.code is ErrorCode.LOYALTY_TIERS_REQUIRED


async def test_reset_restores_defaults_and_recalculates(
    session: AsyncSession, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    await _update_use_case(session, uow, event_publisher, RecordingDispatch())(
        OWNER,
        UpdateLoyaltySettingsDto(
            enabled=True,
            window_months=12,
            tiers=[LoyaltyTierDto(threshold=Decimal("1000"), percent=3)],
        ),
    )
    dispatch = RecordingDispatch()

    result = await ResetLoyaltySettingsUseCase(
        LoyaltyRepository(session), PricingRepository(session), event_publisher, uow, dispatch
    )(OWNER)

    assert (result.enabled, result.window_months, result.tiers) == (
        False,
        None,
        list(DEFAULT_TIERS),
    )
    assert result.anchor_currency is not None
    assert (await LoyaltyRepository(session).get_settings()).tiers == list(DEFAULT_TIERS)
    assert dispatch.messages == [{"user_ids": None}]
