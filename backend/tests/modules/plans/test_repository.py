from dataclasses import replace
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError as PydanticValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.enums import Currency, PlanAvailability, PlanBadge, PlanType
from app.core.error_codes import ErrorCode
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.plans.api.schemas import PlanIconRequest
from app.modules.plans.dto import (
    CreatePlanDto,
    PlanDto,
    ReorderPlansDto,
    SetPlanDurationBasePriceDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceOverrideDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository


def _create_dto(public_code: str = "basic", name: str = "Basic") -> CreatePlanDto:
    return CreatePlanDto(
        public_code=public_code, name=name, type=PlanType.BOTH, traffic_limit=100, device_limit=3
    )


async def _make_plan(plan_repository: PlanRepository) -> PlanDto:
    return await plan_repository.create(_create_dto())


async def _add_minimal_squad(plan_repository: PlanRepository, plan_id: int) -> None:
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan_id, internal_squads=[uuid4()], external_squad=None)
    )


async def _add_minimal_duration(plan_repository: PlanRepository, plan_id: int) -> None:
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan_id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("9.99"))],
        )
    )


async def test_create_then_list_all_returns_plan(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())

    plans = await plan_repository.list_all()

    assert len(plans) == 1
    assert plans[0].id == created.id
    assert plans[0].name == "Basic"
    assert plans[0].is_active is False
    assert plans[0].durations == []


async def test_new_plan_starts_inactive_and_excluded_from_list_active(
    plan_repository: PlanRepository,
) -> None:
    await plan_repository.create(_create_dto())

    assert await plan_repository.list_active() == []


async def test_activating_plan_makes_it_appear_in_list_active(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(_create_dto())
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)

    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))

    active = await plan_repository.list_active()
    assert [plan.id for plan in active] == [created.id]


async def test_activating_plan_without_durations_raises_validation_error(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(_create_dto())
    await _add_minimal_squad(plan_repository, created.id)

    with pytest.raises(ValidationError):
        await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))


async def test_activating_plan_without_squads_raises_validation_error(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(_create_dto())
    await _add_minimal_duration(plan_repository, created.id)

    with pytest.raises(ValidationError):
        await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))


async def test_clearing_durations_of_active_plan_raises_validation_error(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(_create_dto())
    await _add_minimal_squad(plan_repository, created.id)
    await _add_minimal_duration(plan_repository, created.id)
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))

    with pytest.raises(ValidationError):
        await plan_repository.set_durations(SetPlanDurationsDto(plan_id=created.id, durations=[]))


async def test_create_assigns_incrementing_order_index(plan_repository: PlanRepository) -> None:
    first = await plan_repository.create(_create_dto("a", "A"))
    second = await plan_repository.create(_create_dto("b", "B"))

    assert first.order_index == 0
    assert second.order_index == 1


async def test_create_duplicate_public_code_raises_conflict(
    plan_repository: PlanRepository,
) -> None:
    await plan_repository.create(_create_dto("dup", "First"))

    with pytest.raises(ConflictError):
        await plan_repository.create(_create_dto("dup", "Second"))


async def test_create_duplicate_name_raises_conflict(plan_repository: PlanRepository) -> None:
    await plan_repository.create(_create_dto("first", "Dup"))

    with pytest.raises(ConflictError):
        await plan_repository.create(_create_dto("second", "Dup"))


async def test_create_devices_plan_zeroes_traffic_limit(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="devices-only",
            name="Devices Only",
            type=PlanType.DEVICES,
            traffic_limit=500,
            device_limit=5,
        )
    )

    assert created.traffic_limit == 0
    assert created.device_limit == 5


async def test_create_traffic_plan_zeroes_device_limit(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="traffic-only",
            name="Traffic Only",
            type=PlanType.TRAFFIC,
            traffic_limit=500,
            device_limit=5,
        )
    )

    assert created.traffic_limit == 500
    assert created.device_limit == 0


async def test_create_unlimited_plan_zeroes_both_limits(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="fully-unlimited",
            name="Fully Unlimited",
            type=PlanType.UNLIMITED,
            traffic_limit=500,
            device_limit=5,
        )
    )

    assert created.traffic_limit == 0
    assert created.device_limit == 0


async def test_create_both_plan_keeps_both_limits(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())

    assert created.traffic_limit == 100
    assert created.device_limit == 3


async def test_update_unknown_plan_raises_not_found(plan_repository: PlanRepository) -> None:
    with pytest.raises(NotFoundError):
        await plan_repository.update(UpdatePlanDto(plan_id=999_999, name="X"))


async def test_partial_update_leaves_other_fields_untouched(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(_create_dto())

    updated = await plan_repository.update(UpdatePlanDto(plan_id=created.id, traffic_limit=200))

    assert updated.traffic_limit == 200
    assert updated.device_limit == 3  # untouched
    assert updated.name == "Basic"  # untouched


async def test_update_switching_to_devices_type_zeroes_traffic_limit(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(_create_dto())

    updated = await plan_repository.update(UpdatePlanDto(plan_id=created.id, type=PlanType.DEVICES))

    assert updated.traffic_limit == 0
    assert updated.device_limit == 3  # untouched


async def test_update_on_an_already_devices_plan_keeps_traffic_limit_zeroed(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="devices-plan",
            name="Devices Plan",
            type=PlanType.DEVICES,
            traffic_limit=0,
            device_limit=3,
        )
    )

    # an unrelated update: type stays DEVICES, traffic_limit stays zeroed
    updated = await plan_repository.update(UpdatePlanDto(plan_id=created.id, name="Renamed"))

    assert updated.traffic_limit == 0
    assert updated.name == "Renamed"


@pytest.mark.parametrize(
    ("plan_type", "traffic_limit", "device_limit"),
    [(PlanType.TRAFFIC, 0, 0), (PlanType.DEVICES, 0, 0), (PlanType.BOTH, 100, 0)],
)
async def test_create_rejects_a_zero_limit_the_type_applies(
    plan_repository: PlanRepository, plan_type: PlanType, traffic_limit: int, device_limit: int
) -> None:
    with pytest.raises(ValidationError) as error:
        await plan_repository.create(
            CreatePlanDto(
                public_code="zero",
                name="Zero",
                type=plan_type,
                traffic_limit=traffic_limit,
                device_limit=device_limit,
            )
        )

    assert error.value.code == ErrorCode.PLAN_LIMIT_REQUIRED


async def test_update_to_a_limited_type_needs_its_limit(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="unlimited",
            name="Unlimited",
            type=PlanType.UNLIMITED,
            traffic_limit=0,
            device_limit=0,
        )
    )

    with pytest.raises(ValidationError):
        await plan_repository.update(UpdatePlanDto(plan_id=created.id, type=PlanType.TRAFFIC))

    updated = await plan_repository.update(
        UpdatePlanDto(plan_id=created.id, type=PlanType.TRAFFIC, traffic_limit=50)
    )
    assert (updated.traffic_limit, updated.device_limit) == (50, 0)


async def test_clearing_the_icon_drops_its_fallback(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="icon",
            name="Icon",
            type=PlanType.UNLIMITED,
            traffic_limit=0,
            device_limit=0,
            icon_emoji_id="123",
            icon_emoji_fallback="🚀",
        )
    )

    cleared = await plan_repository.update(
        UpdatePlanDto(plan_id=created.id, cleared=frozenset({"icon_emoji_id"}))
    )

    assert (cleared.icon_emoji_id, cleared.icon_emoji_fallback) == (None, None)


async def test_delete_removes_plan(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())

    await plan_repository.delete(created.id)

    assert await plan_repository.list_all() == []


async def test_delete_unknown_plan_raises_not_found(plan_repository: PlanRepository) -> None:
    with pytest.raises(NotFoundError):
        await plan_repository.delete(999_999)


async def test_set_durations_replaces_full_set(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())

    updated = await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[
                SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("3.99")),
                SetPlanDurationDto(days=90, order_index=1, base_price=Decimal("9.99")),
            ],
        )
    )

    assert [duration.days for duration in updated.durations] == [30, 90]
    assert updated.durations[0].base_price == Decimal("3.99")
    assert updated.durations[0].overrides == []


async def test_set_durations_again_drops_previous_set(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("3.99"))],
        )
    )

    updated = await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=7, order_index=0, base_price=Decimal("0.99"))],
        )
    )

    assert [duration.days for duration in updated.durations] == [7]


async def test_set_durations_rejects_duplicate_days(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())

    with pytest.raises(ValidationError):
        await plan_repository.set_durations(
            SetPlanDurationsDto(
                plan_id=created.id,
                durations=[
                    SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("3.99")),
                    SetPlanDurationDto(days=30, order_index=1, base_price=Decimal("9.99")),
                ],
            )
        )


async def test_update_access_persists_allowlists(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())

    updated = await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.ALLOWED,
            allowed_telegram_ids=[111, 222],
            allowed_emails=["a@example.com"],
        )
    )

    assert updated.availability == PlanAvailability.ALLOWED
    assert updated.allowed_telegram_ids == [111, 222]
    assert updated.allowed_emails == ["a@example.com"]


async def test_update_access_rejects_allowed_with_empty_allowlists(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(_create_dto())

    with pytest.raises(ValidationError):
        await plan_repository.update_access(
            UpdatePlanAccessDto(
                plan_id=created.id,
                availability=PlanAvailability.ALLOWED,
                allowed_telegram_ids=[],
                allowed_emails=[],
            )
        )


async def test_update_access_rejects_existing_for_a_trial_plan(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(replace(_create_dto(), is_trial=True))

    with pytest.raises(ValidationError) as error:
        await plan_repository.update_access(
            UpdatePlanAccessDto(
                plan_id=created.id,
                availability=PlanAvailability.EXISTING,
                allowed_telegram_ids=[],
                allowed_emails=[],
            )
        )
    assert error.value.code == ErrorCode.PLAN_TRIAL_EXISTING_ACCESS


async def test_update_rejects_turning_an_existing_only_plan_into_a_trial(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(_create_dto())
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.EXISTING,
            allowed_telegram_ids=[],
            allowed_emails=[],
        )
    )

    with pytest.raises(ValidationError) as error:
        await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_trial=True))
    assert error.value.code == ErrorCode.PLAN_TRIAL_EXISTING_ACCESS


async def test_create_rejects_a_trial_plan_with_a_badge(plan_repository: PlanRepository) -> None:
    with pytest.raises(ValidationError) as error:
        await plan_repository.create(replace(_create_dto(), is_trial=True, badge=PlanBadge.POPULAR))
    assert error.value.code == ErrorCode.PLAN_TRIAL_BADGE


async def test_update_rejects_a_badge_on_a_trial_plan(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(replace(_create_dto(), badge=PlanBadge.POPULAR))

    with pytest.raises(ValidationError) as error:
        await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_trial=True))
    assert error.value.code == ErrorCode.PLAN_TRIAL_BADGE


async def test_update_turns_a_plan_into_a_trial_when_the_badge_is_cleared(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(replace(_create_dto(), badge=PlanBadge.POPULAR))

    updated = await plan_repository.update(
        UpdatePlanDto(plan_id=created.id, is_trial=True, cleared=frozenset({"badge"}))
    )

    assert updated.is_trial is True
    assert updated.badge is None


async def test_update_squads_persists_squad_assignment(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())
    internal = uuid4()
    external = uuid4()

    updated = await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[internal], external_squad=external)
    )

    assert updated.internal_squads == [internal]
    assert updated.external_squad == external


async def test_reorder_applies_new_order(plan_repository: PlanRepository) -> None:
    first = await plan_repository.create(_create_dto("a", "A"))
    second = await plan_repository.create(_create_dto("b", "B"))

    reordered = await plan_repository.reorder(ReorderPlansDto(plan_ids=[second.id, first.id]))

    assert [plan.id for plan in reordered] == [second.id, first.id]


async def test_reorder_rejects_incomplete_id_set(plan_repository: PlanRepository) -> None:
    first = await plan_repository.create(_create_dto("a", "A"))
    await plan_repository.create(_create_dto("b", "B"))

    with pytest.raises(ValidationError):
        await plan_repository.reorder(ReorderPlansDto(plan_ids=[first.id]))


async def test_reorder_rejects_duplicate_id(plan_repository: PlanRepository) -> None:
    first = await plan_repository.create(_create_dto("a", "A"))
    second = await plan_repository.create(_create_dto("b", "B"))

    with pytest.raises(ValidationError):
        await plan_repository.reorder(ReorderPlansDto(plan_ids=[first.id, first.id, second.id]))


async def test_get_by_id_returns_plan(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())

    fetched = await plan_repository.get_by_id(created.id)

    assert fetched.id == created.id
    assert fetched.name == "Basic"


async def test_get_by_id_unknown_plan_raises_not_found(plan_repository: PlanRepository) -> None:
    with pytest.raises(NotFoundError):
        await plan_repository.get_by_id(999_999)


async def test_set_durations_stores_base_price(
    plan_repository: PlanRepository, session: AsyncSession
) -> None:
    plan = await _make_plan(plan_repository)
    result = await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("3.99"))],
        )
    )
    assert result.durations[0].base_price == Decimal("3.99")
    assert result.durations[0].overrides == []


async def test_set_price_override_upserts_and_unpins(
    plan_repository: PlanRepository, session: AsyncSession
) -> None:
    plan = await _make_plan(plan_repository)
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("3.99"))],
        )
    )
    pinned = await plan_repository.set_price_override(
        SetPlanPriceOverrideDto(
            plan_id=plan.id,
            days=30,
            currency=Currency.RUB,
            price=Decimal("299"),
        )
    )
    assert pinned.durations[0].overrides[0].currency is Currency.RUB
    unpinned = await plan_repository.set_price_override(
        SetPlanPriceOverrideDto(plan_id=plan.id, days=30, currency=Currency.RUB, price=None)
    )
    assert unpinned.durations[0].overrides == []


async def test_set_duration_base_price_preserves_other_durations_overrides(
    plan_repository: PlanRepository, session: AsyncSession
) -> None:
    plan = await _make_plan(plan_repository)
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[
                SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("3.99")),
                SetPlanDurationDto(days=90, order_index=1, base_price=Decimal("9.99")),
            ],
        )
    )
    await plan_repository.set_price_override(
        SetPlanPriceOverrideDto(
            plan_id=plan.id,
            days=30,
            currency=Currency.RUB,
            price=Decimal("299"),
        )
    )

    updated = await plan_repository.set_duration_base_price(
        SetPlanDurationBasePriceDto(plan_id=plan.id, days=90, base_price=Decimal("19.99"))
    )

    by_days = {duration.days: duration for duration in updated.durations}
    assert by_days[90].base_price == Decimal("19.99")
    assert by_days[30].base_price == Decimal("3.99")
    assert by_days[30].overrides[0].currency is Currency.RUB
    assert by_days[30].overrides[0].price == Decimal("299")


async def test_set_duration_base_price_unknown_duration_raises_not_found(
    plan_repository: PlanRepository, session: AsyncSession
) -> None:
    plan = await _make_plan(plan_repository)
    with pytest.raises(NotFoundError):
        await plan_repository.set_duration_base_price(
            SetPlanDurationBasePriceDto(plan_id=plan.id, days=30, base_price=Decimal("5"))
        )


@pytest.mark.parametrize(
    "fields",
    [
        {"icon_emoji_id": "1"},
        {"icon_emoji_fallback": "⭐"},
        {"icon_emoji_id": "not-digits", "icon_emoji_fallback": "⭐"},
    ],
)
def test_request_rejects_an_inconsistent_icon(fields: dict[str, str]) -> None:
    with pytest.raises(PydanticValidationError):
        PlanIconRequest(**fields)


async def test_set_durations_keeps_pinned_prices_of_kept_durations(
    plan_repository: PlanRepository, session: AsyncSession
) -> None:
    plan = await _make_plan(plan_repository)
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[
                SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("3.99")),
                SetPlanDurationDto(days=60, order_index=1, base_price=Decimal("6.99")),
            ],
        )
    )
    await plan_repository.set_price_override(
        SetPlanPriceOverrideDto(
            plan_id=plan.id, days=30, currency=Currency.RUB, price=Decimal("299")
        )
    )

    # 60 dropped, 90 added, 30 moved down
    result = await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[
                SetPlanDurationDto(days=90, order_index=0, base_price=Decimal("9.99")),
                SetPlanDurationDto(days=30, order_index=1, base_price=Decimal("4.99")),
            ],
        )
    )

    by_days = {duration.days: duration for duration in result.durations}
    assert set(by_days) == {30, 90}
    assert by_days[30].order_index == 1
    assert by_days[30].base_price == Decimal("4.99")
    assert [(o.currency, o.price) for o in by_days[30].overrides] == [
        (Currency.RUB, Decimal("299"))
    ]
    assert by_days[90].overrides == []
