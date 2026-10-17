from decimal import Decimal
from typing import Optional
from uuid import uuid4

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PlanAvailability, PlanType
from app.modules.plans.dto import (
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanAccessDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.pricing.repository import PricingRepository
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases import GetAvailableTrialUseCase
from app.modules.users.dto import CreateUserDto, UpdateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_eligibility


async def _create_trial_plan(
    plan_repository: PlanRepository,
    *,
    code: str = "trial-plan",
    price: Decimal = Decimal("0"),
    availability: PlanAvailability = PlanAvailability.ALL,
    allowed_telegram_ids: Optional[list[int]] = None,
) -> None:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code=code,
            name=code,
            type=PlanType.BOTH,
            traffic_limit=10,
            device_limit=1,
            is_trial=True,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=3, order_index=0, base_price=price)],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    if availability is not PlanAvailability.ALL:
        await plan_repository.update_access(
            UpdatePlanAccessDto(
                plan_id=plan.id,
                availability=availability,
                allowed_telegram_ids=allowed_telegram_ids or [],
                allowed_emails=[],
            )
        )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))


def _use_case(plan_repository: PlanRepository, uow: UnitOfWork) -> GetAvailableTrialUseCase:
    session = plan_repository.session
    return GetAvailableTrialUseCase(
        plan_repository, PricingRepository(session), make_eligibility(session), uow
    )


async def test_returns_the_trial_plan_when_available(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    await _create_trial_plan(plan_repository)
    actor = await user_repository.create(CreateUserDto(name="trial-eligible"))
    use_case = _use_case(plan_repository, uow)

    result = await use_case(actor)

    assert result.is_trial_available is True
    assert result.plan is not None
    assert result.plan.public_code == "trial-plan"
    assert result.is_free is True


async def test_returns_no_plan_once_the_flag_is_spent(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    await _create_trial_plan(plan_repository)
    actor = await user_repository.create(CreateUserDto(name="trial-spent"))
    await user_repository.update_fields(actor.id, UpdateUserDto(is_trial_available=False))
    updated_actor = await user_repository.find_by_id(actor.id)
    use_case = _use_case(plan_repository, uow)

    result = await use_case(updated_actor)

    assert result.is_trial_available is False


async def test_a_used_up_trial_plan_leaves_the_catalog_too(
    plan_repository: PlanRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    await _create_trial_plan(plan_repository)
    trial = next(plan for plan in await plan_repository.list_active() if plan.is_trial)
    actor = await user_repository.create(CreateUserDto(name="trial-catalog"))
    eligibility = make_eligibility(plan_repository.session)

    assert await eligibility.is_purchasable(trial, actor) is True
    await user_repository.update_fields(actor.id, UpdateUserDto(is_trial_available=False))
    assert await eligibility.is_purchasable(trial, actor) is False


async def test_a_paid_trial_is_offered_with_its_anchor_price(
    plan_repository: PlanRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    await _create_trial_plan(plan_repository, code="paid-trial", price=Decimal("1.50"))
    actor = await user_repository.create(CreateUserDto(name="paid-trial"))

    result = await _use_case(plan_repository, uow)(actor)

    assert result.plan is not None
    assert result.plan.public_code == "paid-trial"
    assert result.is_free is False
    assert result.price == Decimal("1.50")
    assert result.currency is Currency.USD


async def test_a_targeted_trial_beats_one_open_to_everyone(
    plan_repository: PlanRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    actor = await user_repository.create(CreateUserDto(name="targeted", telegram_id=777001))
    # first in the catalog, but open to everyone
    await _create_trial_plan(plan_repository, code="general")
    await _create_trial_plan(
        plan_repository,
        code="personal",
        availability=PlanAvailability.ALLOWED,
        allowed_telegram_ids=[777001],
    )

    result = await _use_case(plan_repository, uow)(actor)

    assert result.plan is not None
    assert result.plan.public_code == "personal"


async def test_within_one_priority_the_catalog_order_decides(
    plan_repository: PlanRepository, user_repository: UserRepository, uow: UnitOfWork
) -> None:
    # plans join the catalog in creation order
    await _create_trial_plan(plan_repository, code="first")
    await _create_trial_plan(plan_repository, code="second")
    actor = await user_repository.create(CreateUserDto(name="ordered"))

    result = await _use_case(plan_repository, uow)(actor)

    assert result.plan is not None
    assert result.plan.public_code == "first"
