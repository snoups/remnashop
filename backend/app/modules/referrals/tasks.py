from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from taskiq import Context, TaskiqDepends

from app.modules.referrals.dto import (
    AssignReferralRewardsDto,
    AttachReferralOnRegistrationDto,
    ResumeBonusRenewalDto,
    ReverseReferralRewardsDto,
)
from app.modules.referrals.usecases import (
    AssignReferralRewardsUseCase,
    AttachReferralOnRegistrationUseCase,
    ResumeBonusRenewalUseCase,
    ReverseReferralRewardsUseCase,
)
from app.worker.broker import broker

_RESUME_MAX_RETRIES: Final[int] = 10


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


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def reverse_referral_rewards_task(
    payment_key: str, use_case: FromDishka[ReverseReferralRewardsUseCase]
) -> None:
    await use_case.system(ReverseReferralRewardsDto(payment_key=payment_key))


@broker.task(retry_on_error=True, max_retries=_RESUME_MAX_RETRIES)
@inject(patch_module=True)
async def resume_bonus_renewal_task(
    user_id: int,
    subscription_id: int,
    days: int,
    idempotency_key: str,
    use_case: FromDishka[ResumeBonusRenewalUseCase],
    context: Context = TaskiqDepends(),
) -> None:
    # SmartRetryMiddleware stops once _retries + 1 reaches max_retries
    attempt = int(context.message.labels.get("_retries", 0)) + 1
    await use_case.system(
        ResumeBonusRenewalDto(
            user_id=user_id,
            subscription_id=subscription_id,
            days=days,
            idempotency_key=idempotency_key,
            final_attempt=attempt >= _RESUME_MAX_RETRIES,
        )
    )
