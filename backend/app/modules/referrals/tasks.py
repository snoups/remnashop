from decimal import Decimal
from typing import Final

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PurchaseType, ReferralAccrualStrategy, ReferralRewardType
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.modules.referrals.events import ReferralRewardIssuedEvent
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions import (
    PurchaseSubscriptionDto,
    PurchaseSubscriptionUseCase,
    SubscriptionRepository,
)
from app.modules.users import UserRepository
from app.worker.broker import broker

_MAX_LEVEL: Final[int] = 3


async def _walk_chain(
    referral_repository: ReferralRepository, buyer_id: int, max_level: int
) -> list[tuple[int, int, int]]:
    # Each hop's own edge (id, referrer_id) is kept as-is -- re-fetching by
    # referrer_id in the caller would return the referrer's own referrer's
    # edge instead, one level further up the chain than the reward is for.
    chain: list[tuple[int, int, int]] = []
    seen: set[int] = {buyer_id}
    current_id = buyer_id
    for level in range(1, min(max_level, _MAX_LEVEL) + 1):
        edge = await referral_repository.get_by_referred_id(current_id)
        if edge is None or edge.referrer_id is None:
            break
        if edge.referrer_id in seen:
            break
        chain.append((level, edge.referrer_id, edge.id))
        seen.add(edge.referrer_id)
        current_id = edge.referrer_id
    return chain


async def assign_referral_rewards(
    *,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    user_id: int,
    subscription_id: int,
    is_new_purchase: bool,
) -> None:
    settings = await referral_repository.get_settings()
    if not settings.enabled:
        return
    # EVERY_PAYMENT can't distinguish a paid renewal from a free one
    # (promocode DURATION rewards renew at price_paid=0) -- SubscriptionRenewedEvent
    # carries no price. Upgrade path: add price_paid/is_free to that event.
    if settings.accrual_strategy is ReferralAccrualStrategy.FIRST_PAYMENT and not is_new_purchase:
        return

    try:
        subscription = await subscription_repository.get_by_id(subscription_id)
    except NotFoundError:
        logger.warning(f"Referral reward skipped: subscription '{subscription_id}' not found")
        return
    if subscription.is_trial:
        return

    chain = await _walk_chain(referral_repository, user_id, settings.max_level)

    for level, referrer_id, referral_id in chain:
        amount = settings.reward_amounts.get(level)
        if not amount or amount <= 0:
            continue
        try:
            await _grant_one_level(
                referral_repository=referral_repository,
                user_repository=user_repository,
                subscription_repository=subscription_repository,
                purchase_subscription_use_case=purchase_subscription_use_case,
                uow=uow,
                event_publisher=event_publisher,
                referrer_id=referrer_id,
                referral_id=referral_id,
                subscription_id=subscription_id,
                level=level,
                reward_type=settings.reward_type,
                amount=amount,
            )
        except Exception:
            logger.exception(
                f"Referral reward failed at level '{level}' for referrer '{referrer_id}' "
                f"(buyer '{user_id}') -- skipping this level"
            )


async def _grant_one_level(
    *,
    referral_repository: ReferralRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    referrer_id: int,
    referral_id: int,
    subscription_id: int,
    level: int,
    reward_type: ReferralRewardType,
    amount: Decimal,
) -> None:
    referrer = await user_repository.get_by_id(referrer_id)
    if referrer is None:
        return

    # Ledger row inserted before the actual grant, using the
    # (subscription_id, referral_id) unique constraint as an idempotency
    # guard against at-least-once event redelivery re-running this hop.
    try:
        async with uow:
            await referral_repository.create_reward(
                referral_id=referral_id,
                referrer_id=referrer_id,
                subscription_id=subscription_id,
                type=reward_type,
                amount=amount,
            )
    except ConflictError:
        logger.info(
            f"Referral reward for subscription '{subscription_id}' referral '{referral_id}' "
            "already granted, skipping"
        )
        return

    if reward_type is ReferralRewardType.EXTRA_DAYS:
        active = await subscription_repository.get_active_by_user(referrer_id)
        if not active:
            logger.warning(f"No active subscription for referrer '{referrer_id}', skipping grant")
            return
        target = active[0]
        await purchase_subscription_use_case.system(
            PurchaseSubscriptionDto(
                user_id=referrer_id,
                plan_snapshot=target.plan_snapshot,
                duration_days=int(amount),
                price_paid=Decimal(0),
                currency=Currency.USD,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=target.id,
            )
        )
    else:
        await user_repository.credit_points(referrer_id, amount)

    async with uow:
        await event_publisher.publish(
            ReferralRewardIssuedEvent(
                user=referrer, level=level, reward_type=reward_type.value, amount=str(amount)
            )
        )


@broker.task(retry_on_error=True, max_retries=3)
@inject(patch_module=True)
async def assign_referral_rewards_task(
    user_id: int,
    subscription_id: int,
    is_new_purchase: bool,
    referral_repository: FromDishka[ReferralRepository],
    user_repository: FromDishka[UserRepository],
    subscription_repository: FromDishka[SubscriptionRepository],
    purchase_subscription_use_case: FromDishka[PurchaseSubscriptionUseCase],
    uow: FromDishka[UnitOfWork],
    event_publisher: FromDishka[EventPublisher],
) -> None:
    await assign_referral_rewards(
        referral_repository=referral_repository,
        user_repository=user_repository,
        subscription_repository=subscription_repository,
        purchase_subscription_use_case=purchase_subscription_use_case,
        uow=uow,
        event_publisher=event_publisher,
        user_id=user_id,
        subscription_id=subscription_id,
        is_new_purchase=is_new_purchase,
    )
