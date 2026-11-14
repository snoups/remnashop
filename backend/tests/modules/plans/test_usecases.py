from datetime import timedelta
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, Locale, PlanAvailability, PlanType, PromocodeRewardType, Role
from app.core.error_codes import ErrorCode
from app.core.exceptions import PermissionDeniedError, ValidationError
from app.core.ports import EventPublisher
from app.core.security.permissions import Permission
from app.core.utils.time import datetime_now
from app.modules.plans.addon_repository import AddOnRepository
from app.modules.plans.dto import (
    CreatePlanDto,
    ReorderPlansDto,
    SetMatrixPricesDto,
    SetPlanDurationBasePriceDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    SetPlanPriceOverrideDto,
    UpdatePlanAccessDto,
    UpdatePlanDiscountDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.plans.usecases import (
    CreatePlanUseCase,
    DeletePlanUseCase,
    ListPlansUseCase,
    ReorderPlansUseCase,
    SetMatrixPricesUseCase,
    SetPlanDurationsUseCase,
    UpdatePlanAccessUseCase,
    UpdatePlanDiscountUseCase,
    UpdatePlanSquadsUseCase,
    UpdatePlanUseCase,
)
from app.modules.pricing import PricingRepository
from app.modules.promocodes.dto import CreatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.users.dto import UserDto

OWNER = UserDto(login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


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


async def test_owner_can_list_all_plans_including_inactive(
    plan_repository: PlanRepository,
    uow: UnitOfWork,
) -> None:
    await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = ListPlansUseCase(plan_repository, uow)

    plans = await use_case(OWNER)

    assert len(plans) == 1
    assert plans[0].is_active is False


async def test_regular_user_cannot_list_all_plans(
    plan_repository: PlanRepository,
    uow: UnitOfWork,
) -> None:
    use_case = ListPlansUseCase(plan_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER)


async def test_create_plan_generates_an_unguessable_public_code(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = CreatePlanUseCase(plan_repository, uow, event_publisher)

    first = await use_case(
        OWNER, CreatePlanDto(name="Gen A", type=PlanType.BOTH, traffic_limit=1, device_limit=1)
    )
    second = await use_case(
        OWNER, CreatePlanDto(name="Gen B", type=PlanType.BOTH, traffic_limit=1, device_limit=1)
    )

    # a LINK plan is bought by this code alone
    for code in (first.public_code, second.public_code):
        assert len(code) == 8 and code.isalnum()
    assert first.public_code != second.public_code


async def test_owner_can_create_plan(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = CreatePlanUseCase(plan_repository, uow, event_publisher)

    plan = await use_case(
        OWNER,
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        ),
    )

    assert plan.name == "Basic"
    assert plan.is_active is False


async def test_regular_user_cannot_create_plan(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    use_case = CreatePlanUseCase(plan_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            CreatePlanDto(
                public_code="basic",
                name="Basic",
                type=PlanType.BOTH,
                traffic_limit=100,
                device_limit=3,
            ),
        )


async def test_owner_can_update_plan(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanUseCase(plan_repository, uow, event_publisher)

    updated = await use_case(OWNER, UpdatePlanDto(plan_id=created.id, traffic_limit=500))

    assert updated.traffic_limit == 500


async def test_regular_user_cannot_update_plan(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanUseCase(plan_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, UpdatePlanDto(plan_id=created.id, traffic_limit=500))


async def test_owner_can_delete_plan(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = DeletePlanUseCase(
        plan_repository,
        PromocodeRepository(plan_repository.session),
        uow,
        event_publisher,
    )

    await use_case(OWNER, created.id)

    assert await plan_repository.list_all() == []


async def test_regular_user_cannot_delete_plan(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = DeletePlanUseCase(
        plan_repository,
        PromocodeRepository(plan_repository.session),
        uow,
        event_publisher,
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, created.id)


async def test_owner_can_set_plan_durations(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = SetPlanDurationsUseCase(plan_repository, uow, event_publisher)

    updated = await use_case(
        OWNER,
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=30, order_index=0, base_price=Decimal("299.00"))],
        ),
    )

    assert [duration.days for duration in updated.durations] == [30]


@pytest.mark.parametrize(
    ("is_trial", "durations", "code"),
    [
        (True, [(3, "0"), (7, "0")], ErrorCode.PLAN_TRIAL_SINGLE_DURATION),
        (False, [(30, "0")], ErrorCode.PLAN_DURATION_PRICE_REQUIRED),
        (True, [(0, "0")], ErrorCode.PLAN_TRIAL_UNLIMITED_DURATION),
    ],
)
async def test_set_plan_durations_keeps_trial_and_price_rules(
    plan_repository: PlanRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    is_trial: bool,
    durations: list[tuple[int, str]],
    code: ErrorCode,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="rules",
            name="Rules",
            type=PlanType.BOTH,
            traffic_limit=100,
            device_limit=3,
            is_trial=is_trial,
        )
    )
    use_case = SetPlanDurationsUseCase(plan_repository, uow, event_publisher)
    items = [
        SetPlanDurationDto(days=days, order_index=index, base_price=Decimal(price))
        for index, (days, price) in enumerate(durations)
    ]

    with pytest.raises(ValidationError) as error:
        await use_case(OWNER, SetPlanDurationsDto(plan_id=created.id, durations=items))

    assert error.value.code is code


async def test_set_plan_durations_accepts_unlimited_on_paid_plan(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="forever",
            name="Forever",
            type=PlanType.BOTH,
            traffic_limit=1,
            device_limit=1,
        )
    )

    plan = await SetPlanDurationsUseCase(plan_repository, uow, event_publisher)(
        OWNER,
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[
                SetPlanDurationDto(days=0, order_index=0, base_price=Decimal("500")),
                SetPlanDurationDto(days=30, order_index=1, base_price=Decimal("9.99")),
            ],
        ),
    )

    assert [duration.days for duration in plan.durations] == [0, 30]
    assert [duration.days for duration in plan.sellable_durations()] == [0, 30]


async def test_update_plan_refuses_trial_with_unlimited_duration(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="to-trial",
            name="To trial",
            type=PlanType.BOTH,
            traffic_limit=1,
            device_limit=1,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=0, order_index=0, base_price=Decimal("500"))],
        )
    )

    with pytest.raises(ValidationError) as error:
        await UpdatePlanUseCase(plan_repository, uow, event_publisher)(
            OWNER, UpdatePlanDto(plan_id=created.id, is_trial=True)
        )

    assert error.value.code is ErrorCode.PLAN_TRIAL_UNLIMITED_DURATION


async def test_regular_user_cannot_set_plan_durations(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = SetPlanDurationsUseCase(plan_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, SetPlanDurationsDto(plan_id=created.id, durations=[]))


async def test_owner_can_update_plan_access(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanAccessUseCase(plan_repository, uow, event_publisher)

    updated = await use_case(
        OWNER,
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.ALLOWED,
            allowed_telegram_ids=[111],
            allowed_emails=[],
        ),
    )

    assert updated.availability == PlanAvailability.ALLOWED
    assert updated.allowed_telegram_ids == [111]


async def test_regular_user_cannot_update_plan_access(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanAccessUseCase(plan_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdatePlanAccessDto(
                plan_id=created.id,
                availability=PlanAvailability.ALLOWED,
                allowed_telegram_ids=[],
                allowed_emails=[],
            ),
        )


async def test_owner_can_update_plan_squads(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanSquadsUseCase(plan_repository, uow, event_publisher)
    squad = uuid4()

    updated = await use_case(
        OWNER,
        UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[squad], external_squad=None),
    )

    assert updated.internal_squads == [squad]


async def test_regular_user_cannot_update_plan_squads(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanSquadsUseCase(plan_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[], external_squad=None),
        )


async def test_owner_can_reorder_plans(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    first = await plan_repository.create(
        CreatePlanDto(
            public_code="a", name="A", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    second = await plan_repository.create(
        CreatePlanDto(
            public_code="b", name="B", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = ReorderPlansUseCase(plan_repository, uow, event_publisher)

    reordered = await use_case(OWNER, ReorderPlansDto(plan_ids=[second.id, first.id]))

    assert [plan.id for plan in reordered] == [second.id, first.id]


async def test_regular_user_cannot_reorder_plans(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = ReorderPlansUseCase(plan_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, ReorderPlansDto(plan_ids=[created.id]))


async def test_deleting_a_plan_drops_it_from_promocode_plan_lists_and_disables_emptied_ones(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    kept = await plan_repository.create(
        CreatePlanDto(
            public_code="kept", name="Kept", type=PlanType.BOTH, traffic_limit=1, device_limit=1
        )
    )
    gone = await plan_repository.create(
        CreatePlanDto(
            public_code="gone", name="Gone", type=PlanType.BOTH, traffic_limit=1, device_limit=1
        )
    )
    promocodes = PromocodeRepository(plan_repository.session)
    both = await promocodes.create(
        CreatePromocodeDto(
            code="BOTHPLANS",
            reward_type=PromocodeRewardType.DURATION,
            reward=5,
            allowed_plan_ids=[kept.id, gone.id],
        )
    )
    only = await promocodes.create(
        CreatePromocodeDto(
            code="ONLYGONE",
            reward_type=PromocodeRewardType.DURATION,
            reward=5,
            allowed_plan_ids=[gone.id],
        )
    )

    await DeletePlanUseCase(plan_repository, promocodes, uow, event_publisher)(OWNER, gone.id)

    both_after = await promocodes.get_by_id(both.id)
    only_after = await promocodes.get_by_id(only.id)
    assert both_after.allowed_plan_ids == [kept.id]
    assert both_after.is_active
    assert only_after.allowed_plan_ids == []
    assert not only_after.is_active


async def test_owner_can_set_and_clear_plan_discount(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanDiscountUseCase(plan_repository, uow, event_publisher)
    ends_at = datetime_now() + timedelta(days=7)

    updated = await use_case(
        OWNER,
        UpdatePlanDiscountDto(
            plan_id=created.id,
            discount_percent=25,
            discount_starts_at=None,
            discount_ends_at=ends_at,
        ),
    )
    assert updated.discount_percent == 25
    assert updated.discount_ends_at == ends_at

    cleared = await use_case(
        OWNER,
        UpdatePlanDiscountDto(
            plan_id=created.id, discount_percent=0, discount_starts_at=None, discount_ends_at=None
        ),
    )
    assert cleared.discount_percent == 0
    assert cleared.discount_ends_at is None


async def test_plan_discount_must_start_before_it_ends(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanDiscountUseCase(plan_repository, uow, event_publisher)
    now = datetime_now()

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            UpdatePlanDiscountDto(
                plan_id=created.id,
                discount_percent=10,
                discount_starts_at=now,
                discount_ends_at=now,
            ),
        )


async def test_regular_user_cannot_set_plan_discount(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanDiscountUseCase(plan_repository, uow, event_publisher)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdatePlanDiscountDto(
                plan_id=created.id,
                discount_percent=10,
                discount_starts_at=None,
                discount_ends_at=None,
            ),
        )


def _matrix_use_case(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> SetMatrixPricesUseCase:
    return SetMatrixPricesUseCase(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )


async def _matrix_plan(plan_repository: PlanRepository) -> int:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="m", name="M", type=PlanType.BOTH, traffic_limit=1, device_limit=1
        )
    )
    await _add_minimal_duration(plan_repository, created.id)
    return created.id


async def test_set_matrix_prices_applies_every_edit(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    plan_id = await _matrix_plan(plan_repository)
    use_case = _matrix_use_case(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )

    book = await use_case(
        OWNER,
        SetMatrixPricesDto(
            plan_base_prices=[
                SetPlanDurationBasePriceDto(plan_id=plan_id, days=30, base_price=Decimal("5.00"))
            ],
            plan_overrides=[
                SetPlanPriceOverrideDto(
                    plan_id=plan_id, days=30, currency=Currency.RUB, price=Decimal("399")
                )
            ],
            addon_base_prices=[],
            addon_overrides=[],
        ),
    )

    row = next(row for row in book.plans if row.plan_id == plan_id)
    cell = next(cell for cell in row.cells if cell.currency is Currency.RUB)
    assert row.base_price == Decimal("5.00")
    assert cell.is_pinned and cell.amount == Decimal("399")


async def test_set_matrix_prices_rejects_an_anchor_override(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    plan_id = await _matrix_plan(plan_repository)
    use_case = _matrix_use_case(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )
    anchor = (await pricing_repository.get_settings()).anchor_currency

    with pytest.raises(ValidationError):
        await use_case(
            OWNER,
            SetMatrixPricesDto(
                plan_base_prices=[],
                plan_overrides=[
                    SetPlanPriceOverrideDto(
                        plan_id=plan_id, days=30, currency=anchor, price=Decimal("1")
                    )
                ],
                addon_base_prices=[],
                addon_overrides=[],
            ),
        )


async def test_set_matrix_prices_requires_the_permission_of_each_edit(
    plan_repository: PlanRepository,
    addon_repository: AddOnRepository,
    pricing_repository: PricingRepository,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
) -> None:
    plan_id = await _matrix_plan(plan_repository)
    use_case = _matrix_use_case(
        plan_repository, addon_repository, pricing_repository, uow, event_publisher
    )
    admin = UserDto(
        id=3,
        name="Ann",
        role=Role.ADMIN,
        language=Locale.EN,
        permission_revokes=[Permission.PLANS_PRICE_OVERRIDE_MANAGE],
    )

    with pytest.raises(PermissionDeniedError):
        await use_case(
            admin,
            SetMatrixPricesDto(
                plan_base_prices=[],
                plan_overrides=[
                    SetPlanPriceOverrideDto(
                        plan_id=plan_id, days=30, currency=Currency.RUB, price=Decimal("1")
                    )
                ],
                addon_base_prices=[],
                addon_overrides=[],
            ),
        )
    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            SetMatrixPricesDto(
                plan_base_prices=[], plan_overrides=[], addon_base_prices=[], addon_overrides=[]
            ),
        )


async def test_update_plan_saves_other_edits_of_a_migrated_unlimited_trial(
    plan_repository: PlanRepository, uow: UnitOfWork, event_publisher: EventPublisher
) -> None:
    # the migration report says to replace the duration; renaming meanwhile must still save
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="old-trial",
            name="Old trial",
            type=PlanType.BOTH,
            traffic_limit=1,
            device_limit=1,
            is_trial=True,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[SetPlanDurationDto(days=0, order_index=0, base_price=Decimal("0"))],
        )
    )

    plan = await UpdatePlanUseCase(plan_repository, uow, event_publisher)(
        OWNER, UpdatePlanDto(plan_id=created.id, name="Trial")
    )

    assert plan.name == "Trial"
