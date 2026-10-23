import pytest

from app.core.db.uow import UnitOfWork
from app.core.enums import PlanType, PromocodeRewardType
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError, ValidationError
from app.modules.plans.dto import CreatePlanDto
from app.modules.plans.repository import PlanRepository
from app.modules.promocodes.dto import CreatePromocodeDto, ValidatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.usecases import ValidatePromocodeUseCase
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository
from tests.modules.subscriptions.factories import make_eligibility


async def test_validates_a_fresh_code(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    await promocode_repository.create(
        CreatePromocodeDto(
            code="VALID1", reward_type=PromocodeRewardType.PERSONAL_DISCOUNT, reward=15
        )
    )
    actor = await user_repository.create(CreateUserDto(name="validator"))
    use_case = ValidatePromocodeUseCase(
        promocode_repository,
        subscription_repository,
        PlanRepository(promocode_repository.session),
        make_eligibility(promocode_repository.session),
        ReferralRepository(promocode_repository.session),
        uow,
    )

    result = await use_case(actor, ValidatePromocodeDto(code="valid1"))

    assert result.code == "VALID1"
    assert result.reward == 15


async def test_raises_not_found_for_an_unknown_code(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="validator-2"))
    use_case = ValidatePromocodeUseCase(
        promocode_repository,
        subscription_repository,
        PlanRepository(promocode_repository.session),
        make_eligibility(promocode_repository.session),
        ReferralRepository(promocode_repository.session),
        uow,
    )

    with pytest.raises(NotFoundError):
        await use_case(actor, ValidatePromocodeDto(code="NOPE"))


async def test_does_not_claim_an_activation(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    promo = await promocode_repository.create(
        CreatePromocodeDto(
            code="NOCLAIM", reward_type=PromocodeRewardType.PERSONAL_DISCOUNT, reward=5
        )
    )
    actor = await user_repository.create(CreateUserDto(name="no-claim"))
    use_case = ValidatePromocodeUseCase(
        promocode_repository,
        subscription_repository,
        PlanRepository(promocode_repository.session),
        make_eligibility(promocode_repository.session),
        ReferralRepository(promocode_repository.session),
        uow,
    )

    await use_case(actor, ValidatePromocodeDto(code="NOCLAIM"))

    assert await promocode_repository.find_activation_by_user(promo.id, actor.id) is None


async def test_preview_refuses_a_subscription_reward_whose_plan_is_unavailable(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
) -> None:
    plan_repository = PlanRepository(promocode_repository.session)
    plan = await plan_repository.create(
        CreatePlanDto(
            public_code="preview-paused",
            name="Paused",
            type=PlanType.BOTH,
            traffic_limit=10,
            device_limit=1,
        )
    )
    await promocode_repository.create(
        CreatePromocodeDto(
            code="PREVIEWPAUSED",
            reward_type=PromocodeRewardType.SUBSCRIPTION,
            reward_plan_id=plan.id,
            reward_duration_days=30,
        )
    )
    actor = await user_repository.create(CreateUserDto(name="preview-validator"))
    use_case = ValidatePromocodeUseCase(
        promocode_repository,
        subscription_repository,
        plan_repository,
        make_eligibility(promocode_repository.session),
        ReferralRepository(promocode_repository.session),
        uow,
    )

    with pytest.raises(ValidationError):
        await use_case(actor, ValidatePromocodeDto(code="PREVIEWPAUSED"))


@pytest.mark.parametrize(
    ("reward_type", "field"),
    [
        (PromocodeRewardType.PERSONAL_DISCOUNT, "personal_discount"),
        (PromocodeRewardType.PURCHASE_DISCOUNT, "purchase_discount"),
    ],
)
async def test_a_smaller_discount_than_the_current_one_is_refused(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    uow: UnitOfWork,
    reward_type: PromocodeRewardType,
    field: str,
) -> None:
    await promocode_repository.create(
        CreatePromocodeDto(code="SMALL5", reward_type=reward_type, reward=5)
    )
    actor = await user_repository.create(CreateUserDto(name="discounted"))
    actor = actor.model_copy(update={field: 30})
    use_case = ValidatePromocodeUseCase(
        promocode_repository,
        subscription_repository,
        PlanRepository(promocode_repository.session),
        make_eligibility(promocode_repository.session),
        ReferralRepository(promocode_repository.session),
        uow,
    )

    with pytest.raises(ValidationError) as refused:
        await use_case(actor, ValidatePromocodeDto(code="SMALL5"))
    assert refused.value.code is ErrorCode.PROMOCODE_DISCOUNT_NOT_BETTER

    # an equal one still goes through: it may carry a later expiry
    assert (
        await use_case(actor.model_copy(update={field: 5}), ValidatePromocodeDto(code="SMALL5"))
    ).reward == 5
