from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.enums import Currency, PlanAvailability, PlanType
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.modules.plans.dto import (
    CreatePlanDto,
    ReorderPlansDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository


def _create_dto(public_code: str = "basic", name: str = "Basic") -> CreatePlanDto:
    return CreatePlanDto(
        public_code=public_code, name=name, type=PlanType.BOTH, traffic_limit=100, device_limit=3
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

    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))

    active = await plan_repository.list_active()
    assert [plan.id for plan in active] == [created.id]


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
                SetPlanDurationDto(
                    days=30,
                    order_index=0,
                    prices=[
                        SetPlanPriceDto(currency=Currency.RUB, price=Decimal("299.00")),
                        SetPlanPriceDto(currency=Currency.USD, price=Decimal("3.99")),
                    ],
                ),
                SetPlanDurationDto(days=90, order_index=1, prices=[]),
            ],
        )
    )

    assert [duration.days for duration in updated.durations] == [30, 90]
    assert len(updated.durations[0].prices) == 2
    assert updated.durations[0].prices[0].price == Decimal("299.00")


async def test_set_durations_again_drops_previous_set(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, prices=[])],
        )
    )

    updated = await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=7, order_index=0, prices=[])],
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
                    SetPlanDurationDto(days=30, order_index=0, prices=[]),
                    SetPlanDurationDto(days=30, order_index=1, prices=[]),
                ],
            )
        )


async def test_set_durations_rejects_duplicate_currency(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(_create_dto())

    with pytest.raises(ValidationError):
        await plan_repository.set_durations(
            SetPlanDurationsDto(
                plan_id=created.id,
                durations=[
                    SetPlanDurationDto(
                        days=30,
                        order_index=0,
                        prices=[
                            SetPlanPriceDto(currency=Currency.USD, price=Decimal("5.00")),
                            SetPlanPriceDto(currency=Currency.USD, price=Decimal("9.00")),
                        ],
                    )
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
