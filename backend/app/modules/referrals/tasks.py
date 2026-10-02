from dishka.integrations.taskiq import FromDishka, inject

from app.modules.referrals.dto import AssignReferralRewardsDto, AttachReferralOnRegistrationDto
from app.modules.referrals.usecases import AttachReferralOnRegistrationUseCase
from app.modules.referrals.usecases.assign_referral_rewards import AssignReferralRewardsUseCase
from app.worker.broker import broker


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def assign_referral_rewards_task(
    user_id: int,
    subscription_id: int,
    is_new_purchase: bool,
    payment_key: str,
    use_case: FromDishka[AssignReferralRewardsUseCase],
) -> None:
    await use_case.system(
        AssignReferralRewardsDto(
            user_id=user_id,
            subscription_id=subscription_id,
            is_new_purchase=is_new_purchase,
            payment_key=payment_key,
        )
    )


@broker.task
@inject(patch_module=True)
async def attach_referral_on_registration_task(
    user_id: int, referral_code: str, use_case: FromDishka[AttachReferralOnRegistrationUseCase]
) -> None:
    await use_case.system(
        AttachReferralOnRegistrationDto(user_id=user_id, referral_code=referral_code)
    )
