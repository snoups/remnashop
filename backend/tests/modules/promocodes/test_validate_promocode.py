import pytest

from app.core.enums import PromocodeRewardType
from app.core.exceptions import NotFoundError
from app.modules.promocodes.dto import CreatePromocodeDto
from app.modules.promocodes.repository import PromocodeRepository
from app.modules.promocodes.usecases.validate_promocode import (
    ValidatePromocodeDto,
    ValidatePromocodeUseCase,
)
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users.dto import CreateUserDto
from app.modules.users.repository import UserRepository


async def test_validates_a_fresh_code(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
) -> None:
    await promocode_repository.create(
        CreatePromocodeDto(
            code="VALID1", reward_type=PromocodeRewardType.PERSONAL_DISCOUNT, reward=15
        )
    )
    actor = await user_repository.create(CreateUserDto(name="validator"))
    use_case = ValidatePromocodeUseCase(
        promocode_repository, subscription_repository, referral_repository
    )

    result = await use_case(actor, ValidatePromocodeDto(code="valid1"))

    assert result.code == "VALID1"
    assert result.reward == 15


async def test_raises_not_found_for_an_unknown_code(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
) -> None:
    actor = await user_repository.create(CreateUserDto(name="validator-2"))
    use_case = ValidatePromocodeUseCase(
        promocode_repository, subscription_repository, referral_repository
    )

    with pytest.raises(NotFoundError):
        await use_case(actor, ValidatePromocodeDto(code="NOPE"))


async def test_does_not_claim_an_activation(
    promocode_repository: PromocodeRepository,
    subscription_repository: SubscriptionRepository,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
) -> None:
    promo = await promocode_repository.create(
        CreatePromocodeDto(
            code="NOCLAIM", reward_type=PromocodeRewardType.PERSONAL_DISCOUNT, reward=5
        )
    )
    actor = await user_repository.create(CreateUserDto(name="no-claim"))
    use_case = ValidatePromocodeUseCase(
        promocode_repository, subscription_repository, referral_repository
    )

    await use_case(actor, ValidatePromocodeDto(code="NOCLAIM"))

    assert await promocode_repository.get_activation_by_user(promo.id, actor.id) is None
