from decimal import ROUND_DOWN, Decimal
from typing import Final, Optional
from uuid import UUID, uuid5

from dishka.integrations.taskiq import FromDishka, inject
from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    PurchaseType,
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
)
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.ports import EventPublisher
from app.modules.pricing import PricingRepository, convert_for_report
from app.modules.referrals.dto import ReferralSettingsDto
from app.modules.referrals.events import ReferralRewardIssuedEvent
from app.modules.referrals.repository import ReferralRepository
from app.modules.referrals.usecases.attach_referral import (
    AttachReferralDto,
    AttachReferralUseCase,
)
from app.modules.subscriptions import (
    PurchaseSubscriptionDto,
    PurchaseSubscriptionUseCase,
    SubscriptionRepository,
)
from app.modules.transactions import TransactionRepository
from app.modules.users import UserRepository
from app.worker.broker import broker

_MAX_LEVEL: Final[int] = 3
_HUNDRED: Final[Decimal] = Decimal(100)
_MIN_PERCENT_REWARD: Final[Decimal] = Decimal(1)
# Namespace for the per-hop renewal key; any fixed UUID works, it only has to
# stay the same so a redispatch derives the key the first attempt used.
_REWARD_KEY_NAMESPACE: Final[UUID] = UUID("2f9f0b7a-6b1e-4a3f-9a21-6c6f4a1c7f10")


def _reward_idempotency_key(payment_key: str, referral_id: int) -> str:
    return str(uuid5(_REWARD_KEY_NAMESPACE, f"{payment_key}:{referral_id}"))


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


async def _purchase_earns_a_reward(
    *,
    subscription_repository: SubscriptionRepository,
    strategy: ReferralAccrualStrategy,
    user_id: int,
    subscription_id: int,
    is_new_purchase: bool,
) -> bool:
    is_first_payment_only = strategy is ReferralAccrualStrategy.FIRST_PAYMENT
    if is_first_payment_only and not is_new_purchase:
        return False

    try:
        subscription = await subscription_repository.get_by_id(subscription_id)
    except NotFoundError:
        logger.warning(f"Referral reward skipped: subscription '{subscription_id}' not found")
        return False
    if subscription.is_trial:
        return False

    # is_new_purchase only says "bought, not renewed" -- with several
    # concurrent subscriptions allowed, the buyer's second and third one reach
    # here too, and FIRST_PAYMENT would pay the referrer for each. A trial
    # converted in place doesn't count against this: its own row is a trial.
    if is_first_payment_only and await subscription_repository.has_paid_subscription_before(
        user_id, subscription_id
    ):
        logger.info(
            f"Referral reward skipped: user '{user_id}' already had a paid subscription "
            f"and the accrual strategy is {strategy.value}"
        )
        return False
    return True


async def _percent_base(
    *,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    payment_key: str,
    reward_type: ReferralRewardType,
) -> Optional[Decimal]:
    order = await transaction_repository.get_by_idempotency_key(payment_key)
    if order is None:
        logger.warning(f"Percent referral reward skipped: no order for payment '{payment_key}'")
        return None
    if reward_type is ReferralRewardType.EXTRA_DAYS:
        return Decimal(order.duration_days)
    # points are anchor-currency units, whatever the buyer paid in
    rates = await pricing_repository.get_rate_table()
    return convert_for_report(order.final_price, order.currency, rates.anchor, rates)


def _level_amounts(
    settings: ReferralSettingsDto, percent_base: Optional[Decimal]
) -> dict[int, Decimal]:
    if settings.reward_strategy is ReferralRewardStrategy.AMOUNT:
        return settings.reward_amounts
    if percent_base is None:
        return {}
    return {
        level: max(
            _MIN_PERCENT_REWARD,
            (percent_base * percent / _HUNDRED).to_integral_value(rounding=ROUND_DOWN),
        )
        for level, percent in settings.reward_amounts.items()
        if percent > 0
    }


async def assign_referral_rewards(
    *,
    referral_repository: ReferralRepository,
    transaction_repository: TransactionRepository,
    pricing_repository: PricingRepository,
    user_repository: UserRepository,
    subscription_repository: SubscriptionRepository,
    purchase_subscription_use_case: PurchaseSubscriptionUseCase,
    uow: UnitOfWork,
    event_publisher: EventPublisher,
    user_id: int,
    subscription_id: int,
    is_new_purchase: bool,
    payment_key: str,
) -> None:
    settings = await referral_repository.get_settings()
    if not settings.enabled:
        return
    order = await transaction_repository.get_by_idempotency_key(payment_key)
    if order is not None and order.final_price <= 0:
        # a 100%-discount checkout carries a payment_key too, but no money
        logger.info(f"Referral reward skipped: order for payment '{payment_key}' was free")
        return
    if not await _purchase_earns_a_reward(
        subscription_repository=subscription_repository,
        strategy=settings.accrual_strategy,
        user_id=user_id,
        subscription_id=subscription_id,
        is_new_purchase=is_new_purchase,
    ):
        return

    chain = await _walk_chain(referral_repository, user_id, settings.max_level)
    if not chain:
        return

    percent_base = (
        await _percent_base(
            transaction_repository=transaction_repository,
            pricing_repository=pricing_repository,
            payment_key=payment_key,
            reward_type=settings.reward_type,
        )
        if settings.reward_strategy is ReferralRewardStrategy.PERCENT
        else None
    )
    amounts = _level_amounts(settings, percent_base)

    # One failing hop must not cost the others their reward, but it must still
    # reach the task runner: swallowed here, retry_on_error never fires and the
    # hop is lost for good.
    first_failure: Optional[Exception] = None
    for level, referrer_id, referral_id in chain:
        amount = amounts.get(level)
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
                payment_key=payment_key,
                level=level,
                reward_type=settings.reward_type,
                amount=amount,
            )
        except Exception as error:  # noqa: BLE001 -- re-raised below, after every hop has run
            logger.exception(
                f"Referral reward failed at level '{level}' for referrer '{referrer_id}' "
                f"(buyer '{user_id}')"
            )
            first_failure = first_failure or error

    if first_failure is not None:
        raise first_failure


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
    payment_key: str,
    level: int,
    reward_type: ReferralRewardType,
    amount: Decimal,
) -> None:
    referrer = await user_repository.get_by_id(referrer_id)
    if referrer is None:
        return

    if reward_type is ReferralRewardType.EXTRA_DAYS:
        active = await subscription_repository.get_active_by_user(referrer_id)
        if not active:
            logger.warning(f"No active subscription for referrer '{referrer_id}', skipping grant")
            return
        target = active[0]
        # Granted before the ledger row, not after: the renewal is a panel
        # call that can fail or be retried, and its own idempotency key makes
        # a redispatch land once. Written the other way round, a ledger row
        # committed ahead of a failing grant turns every retry into a
        # ConflictError skip -- the reward is recorded and never given.
        await purchase_subscription_use_case.system(
            PurchaseSubscriptionDto(
                user_id=referrer_id,
                plan_snapshot=target.plan_snapshot,
                duration_days=int(amount),
                price_paid=Decimal(0),
                currency=Currency.USD,
                purchase_type=PurchaseType.RENEW,
                target_subscription_id=target.id,
                idempotency_key=_reward_idempotency_key(payment_key, referral_id),
            )
        )
        try:
            async with uow:
                await referral_repository.create_reward(
                    referral_id=referral_id,
                    referrer_id=referrer_id,
                    subscription_id=subscription_id,
                    payment_key=payment_key,
                    type=reward_type,
                    amount=amount,
                )
        except ConflictError:
            logger.info(
                f"Referral reward for payment '{payment_key}' referral '{referral_id}' "
                "already granted, skipping"
            )
            return
    else:
        # Ledger row and the credit itself commit together -- the row is the
        # idempotency guard, so a crash between the two would record a reward
        # nobody received and make every retry skip it.
        try:
            async with uow:
                await referral_repository.create_reward(
                    referral_id=referral_id,
                    referrer_id=referrer_id,
                    subscription_id=subscription_id,
                    payment_key=payment_key,
                    type=reward_type,
                    amount=amount,
                )
                await user_repository.credit_points(referrer_id, amount)
        except ConflictError:
            logger.info(
                f"Referral reward for payment '{payment_key}' referral '{referral_id}' "
                "already granted, skipping"
            )
            return

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
    payment_key: str,
    referral_repository: FromDishka[ReferralRepository],
    transaction_repository: FromDishka[TransactionRepository],
    pricing_repository: FromDishka[PricingRepository],
    user_repository: FromDishka[UserRepository],
    subscription_repository: FromDishka[SubscriptionRepository],
    purchase_subscription_use_case: FromDishka[PurchaseSubscriptionUseCase],
    uow: FromDishka[UnitOfWork],
    event_publisher: FromDishka[EventPublisher],
) -> None:
    await assign_referral_rewards(
        referral_repository=referral_repository,
        transaction_repository=transaction_repository,
        pricing_repository=pricing_repository,
        user_repository=user_repository,
        subscription_repository=subscription_repository,
        purchase_subscription_use_case=purchase_subscription_use_case,
        uow=uow,
        event_publisher=event_publisher,
        user_id=user_id,
        subscription_id=subscription_id,
        is_new_purchase=is_new_purchase,
        payment_key=payment_key,
    )


async def attach_referral_on_registration(
    *,
    user_id: int,
    referral_code: str,
    user_repository: UserRepository,
    attach_referral_use_case: AttachReferralUseCase,
) -> None:
    user = await user_repository.get_by_id(user_id)
    if user is None:
        return
    try:
        await attach_referral_use_case(user, AttachReferralDto(code=referral_code))
    except ValidationError as error:
        # a stale or foreign link isn't a failure worth retrying
        logger.info(f"Referral code '{referral_code}' not attached to user '{user_id}': {error}")


@broker.task
@inject(patch_module=True)
async def attach_referral_on_registration_task(
    user_id: int,
    referral_code: str,
    user_repository: FromDishka[UserRepository],
    attach_referral_use_case: FromDishka[AttachReferralUseCase],
) -> None:
    await attach_referral_on_registration(
        user_id=user_id,
        referral_code=referral_code,
        user_repository=user_repository,
        attach_referral_use_case=attach_referral_use_case,
    )
