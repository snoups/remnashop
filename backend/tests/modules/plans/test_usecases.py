from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import Locale, PlanAvailability, PlanType, PromocodeRewardType, Role
from app.core.exceptions import PermissionDeniedError
from app.core.ports import EventPublisher
from app.modules.plans.dto import (
    CreatePlanDto,
    ReorderPlansDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.plans.usecases import (
    CreatePlanUseCase,
    DeletePlanUseCase,
    ListPlansUseCase,
    ReorderPlansUseCase,
    SetPlanDurationsUseCase,
    UpdatePlanAccessUseCase,
    UpdatePlanSquadsUseCase,
    UpdatePlanUseCase,
)
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


async def test_deleting_a_plan_drops_it_from_promocode_plan_lists(
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

    assert (await promocodes.get_by_id(both.id)).allowed_plan_ids == [kept.id]
    assert (await promocodes.get_by_id(only.id)).allowed_plan_ids == []
