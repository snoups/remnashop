from decimal import Decimal

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import AddOnType, Currency, PlanType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.ports import EventPublisher
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    CreateAddOnDto,
    CreatePlanDto,
    PlanDto,
    SetAddOnPriceOverrideDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceOverrideDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.plans.usecases import SetAddOnPriceOverrideUseCase, SetPlanPriceOverrideUseCase
from app.modules.pricing.repository import PricingRepository


async def _plan_with_duration(plan_repository: PlanRepository) -> PlanDto:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="anchor", name="Anchor", type=PlanType.BOTH, traffic_limit=1, device_limit=1
        )
    )
    return await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("3.99"))],
        )
    )


@pytest.fixture
async def anchor(pricing_repository: PricingRepository) -> Currency:
    return (await pricing_repository.get_settings()).anchor_currency


async def test_plan_override_in_the_anchor_currency_is_rejected(
    plan_repository: PlanRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    anchor: Currency,
) -> None:
    plan = await _plan_with_duration(plan_repository)
    use_case = SetPlanPriceOverrideUseCase(
        plan_repository, pricing_repository, uow, event_publisher
    )

    with pytest.raises(ValidationError) as exc_info:
        await use_case.system(
            SetPlanPriceOverrideDto(plan_id=plan.id, days=30, currency=anchor, price=Decimal("5"))
        )

    assert exc_info.value.code is ErrorCode.ANCHOR_PRICE_NOT_OVERRIDABLE


async def test_plan_override_stranded_in_the_anchor_currency_can_be_cleared(
    plan_repository: PlanRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    anchor: Currency,
) -> None:
    # pinned while another currency was the anchor
    plan = await _plan_with_duration(plan_repository)
    await plan_repository.set_price_override(
        SetPlanPriceOverrideDto(plan_id=plan.id, days=30, currency=anchor, price=Decimal("5"))
    )
    use_case = SetPlanPriceOverrideUseCase(
        plan_repository, pricing_repository, uow, event_publisher
    )

    cleared = await use_case.system(
        SetPlanPriceOverrideDto(plan_id=plan.id, days=30, currency=anchor, price=None)
    )

    assert cleared.durations[0].overrides == []


async def test_addon_override_in_the_anchor_currency_is_rejected(
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    anchor: Currency,
) -> None:
    addon = await addon_repository.create(
        CreateAddOnDto(name="anchor", type=AddOnType.TRAFFIC, amount=1, base_price=Decimal("1"))
    )
    use_case = SetAddOnPriceOverrideUseCase(
        addon_repository, pricing_repository, event_publisher, uow
    )

    with pytest.raises(ValidationError) as exc_info:
        await use_case.system(
            SetAddOnPriceOverrideDto(addon_id=addon.id, currency=anchor, price=Decimal("2"))
        )

    assert exc_info.value.code is ErrorCode.ANCHOR_PRICE_NOT_OVERRIDABLE


async def test_addon_override_stranded_in_the_anchor_currency_can_be_cleared(
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    anchor: Currency,
) -> None:
    addon = await addon_repository.create(
        CreateAddOnDto(name="anchor", type=AddOnType.TRAFFIC, amount=1, base_price=Decimal("1"))
    )
    await addon_repository.set_price_override(
        SetAddOnPriceOverrideDto(addon_id=addon.id, currency=anchor, price=Decimal("2"))
    )
    use_case = SetAddOnPriceOverrideUseCase(
        addon_repository, pricing_repository, event_publisher, uow
    )

    cleared = await use_case.system(
        SetAddOnPriceOverrideDto(addon_id=addon.id, currency=anchor, price=None)
    )

    assert cleared.overrides == []
