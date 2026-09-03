from decimal import Decimal
from uuid import uuid4

from app.core.enums import PlanType
from app.modules.plans.dto import (
    CreatePlanDto,
    SetPlanDurationDto,
    SetPlanDurationsDto,
    UpdatePlanDto,
    UpdatePlanSquadsDto,
)
from app.modules.plans.repository import PlanRepository
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.subscriptions.usecases.get_available_trial import GetAvailableTrialUseCase
from app.modules.users.dto import CreateUserDto, UpdateUserDto
from app.modules.users.repository import UserRepository


async def _create_trial_plan(plan_repository: PlanRepository) -> None:
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="trial-plan",
            name="Trial",
            type=PlanType.BOTH,
            traffic_limit=10,
            device_limit=1,
            is_trial=True,
        )
    )
    await plan_repository.set_durations(
        SetPlanDurationsDto(
            plan_id=plan.id,
            durations=[SetPlanDurationDto(days=3, order_index=0, base_price=Decimal("0.99"))],
        )
    )
    await plan_repository.update_squads(
        UpdatePlanSquadsDto(plan_id=plan.id, internal_squads=[uuid4()], external_squad=None)
    )
    await plan_repository.update(UpdatePlanDto(plan_id=plan.id, is_active=True))


async def test_returns_the_trial_plan_when_available(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
) -> None:
    await _create_trial_plan(plan_repository)
    actor = await user_repository.create(CreateUserDto(name="trial-eligible"))
    use_case = GetAvailableTrialUseCase(
        plan_repository, subscription_repository, referral_repository
    )

    result = await use_case(actor)

    assert result.is_trial_available is True
    assert result.plan is not None
    assert result.plan.public_code == "trial-plan"


async def test_returns_no_plan_once_the_flag_is_spent(
    plan_repository: PlanRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
) -> None:
    await _create_trial_plan(plan_repository)
    actor = await user_repository.create(CreateUserDto(name="trial-spent"))
    await user_repository.update_fields(actor.id, UpdateUserDto(is_trial_available=False))
    updated_actor = await user_repository.get_by_id(actor.id)
    use_case = GetAvailableTrialUseCase(
        plan_repository, subscription_repository, referral_repository
    )

    result = await use_case(updated_actor)

    assert result.is_trial_available is False
