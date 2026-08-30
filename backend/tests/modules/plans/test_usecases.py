from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, Locale, PlanAvailability, PlanType, Role
from app.core.exceptions import PermissionDeniedError
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
from app.modules.plans.usecases import (
    CreatePlanUseCase,
    DeletePlanUseCase,
    ListActivePlansUseCase,
    ListPlansUseCase,
    ReorderPlansUseCase,
    SetPlanDurationsUseCase,
    UpdatePlanAccessUseCase,
    UpdatePlanSquadsUseCase,
    UpdatePlanUseCase,
)
from app.modules.users.dto import UserDto

OWNER = UserDto(id=1, login="owner", name="owner", role=Role.OWNER, language=Locale.EN)
REGULAR_USER = UserDto(id=2, name="Bob", role=Role.USER, language=Locale.EN)


async def test_owner_can_list_all_plans_including_inactive(
    plan_repository: PlanRepository,
) -> None:
    await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = ListPlansUseCase(plan_repository)

    plans = await use_case(OWNER)

    assert len(plans) == 1
    assert plans[0].is_active is False


async def test_regular_user_cannot_list_all_plans(plan_repository: PlanRepository) -> None:
    use_case = ListPlansUseCase(plan_repository)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER)


async def test_regular_user_can_list_active_plans(plan_repository: PlanRepository) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    use_case = ListActivePlansUseCase(plan_repository)

    plans = await use_case(REGULAR_USER)

    assert [plan.id for plan in plans] == [created.id]


async def test_list_active_plans_excludes_inactive(plan_repository: PlanRepository) -> None:
    await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = ListActivePlansUseCase(plan_repository)

    assert await use_case(REGULAR_USER) == []


async def test_list_active_plans_excludes_plan_restricted_to_other_actor(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="vip", name="VIP", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.ALLOWED,
            allowed_telegram_ids=[999_999],
            allowed_emails=[],
        )
    )
    use_case = ListActivePlansUseCase(plan_repository)

    assert await use_case(REGULAR_USER) == []


async def test_list_active_plans_includes_plan_allowed_for_actor_telegram_id(
    plan_repository: PlanRepository,
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="vip", name="VIP", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    await plan_repository.update(UpdatePlanDto(plan_id=created.id, is_active=True))
    await plan_repository.update_access(
        UpdatePlanAccessDto(
            plan_id=created.id,
            availability=PlanAvailability.ALLOWED,
            allowed_telegram_ids=[555],
            allowed_emails=[],
        )
    )
    invited_user = UserDto(
        id=3, telegram_id=555, name="Invited", role=Role.USER, language=Locale.EN
    )
    use_case = ListActivePlansUseCase(plan_repository)

    plans = await use_case(invited_user)

    assert [plan.id for plan in plans] == [created.id]


async def test_owner_can_create_plan(plan_repository: PlanRepository, uow: UnitOfWork) -> None:
    use_case = CreatePlanUseCase(plan_repository, uow)

    plan = await use_case(
        OWNER,
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        ),
    )

    assert plan.name == "Basic"
    assert plan.is_active is False


async def test_regular_user_cannot_create_plan(
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    use_case = CreatePlanUseCase(plan_repository, uow)

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


async def test_owner_can_update_plan(plan_repository: PlanRepository, uow: UnitOfWork) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanUseCase(plan_repository, uow)

    updated = await use_case(OWNER, UpdatePlanDto(plan_id=created.id, traffic_limit=500))

    assert updated.traffic_limit == 500


async def test_regular_user_cannot_update_plan(
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanUseCase(plan_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, UpdatePlanDto(plan_id=created.id, traffic_limit=500))


async def test_owner_can_delete_plan(plan_repository: PlanRepository, uow: UnitOfWork) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = DeletePlanUseCase(plan_repository, uow)

    await use_case(OWNER, created.id)

    assert await plan_repository.list_all() == []


async def test_regular_user_cannot_delete_plan(
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = DeletePlanUseCase(plan_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, created.id)


async def test_owner_can_set_plan_durations(
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = SetPlanDurationsUseCase(plan_repository, uow)

    updated = await use_case(
        OWNER,
        SetPlanDurationsDto(
            plan_id=created.id,
            durations=[
                SetPlanDurationDto(
                    days=30,
                    order_index=0,
                    prices=[SetPlanPriceDto(currency=Currency.RUB, price=Decimal("299.00"))],
                )
            ],
        ),
    )

    assert [duration.days for duration in updated.durations] == [30]


async def test_regular_user_cannot_set_plan_durations(
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = SetPlanDurationsUseCase(plan_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, SetPlanDurationsDto(plan_id=created.id, durations=[]))


async def test_owner_can_update_plan_access(
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanAccessUseCase(plan_repository, uow)

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
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanAccessUseCase(plan_repository, uow)

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
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanSquadsUseCase(plan_repository, uow)
    squad = uuid4()

    updated = await use_case(
        OWNER,
        UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[squad], external_squad=None),
    )

    assert updated.internal_squads == [squad]


async def test_regular_user_cannot_update_plan_squads(
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = UpdatePlanSquadsUseCase(plan_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(
            REGULAR_USER,
            UpdatePlanSquadsDto(plan_id=created.id, internal_squads=[], external_squad=None),
        )


async def test_owner_can_reorder_plans(plan_repository: PlanRepository, uow: UnitOfWork) -> None:
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
    use_case = ReorderPlansUseCase(plan_repository, uow)

    reordered = await use_case(OWNER, ReorderPlansDto(plan_ids=[second.id, first.id]))

    assert [plan.id for plan in reordered] == [second.id, first.id]


async def test_regular_user_cannot_reorder_plans(
    plan_repository: PlanRepository, uow: UnitOfWork
) -> None:
    created = await plan_repository.create(
        CreatePlanDto(
            public_code="basic", name="Basic", type=PlanType.BOTH, traffic_limit=100, device_limit=3
        )
    )
    use_case = ReorderPlansUseCase(plan_repository, uow)

    with pytest.raises(PermissionDeniedError):
        await use_case(REGULAR_USER, ReorderPlansDto(plan_ids=[created.id]))
