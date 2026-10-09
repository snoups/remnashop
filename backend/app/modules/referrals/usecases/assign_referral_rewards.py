from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Final, Optional

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    ReferralAccrualStrategy,
    ReferralRewardStrategy,
    ReferralRewardType,
    TransactionStatus,
)
from app.core.exceptions import ConflictError, NotFoundError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.referrals.dto import AssignReferralRewardsDto, ReferralSettingsDto
from app.modules.referrals.events import ReferralRewardIssuedEvent
from app.modules.referrals.repository import ReferralRepository
from app.modules.subscriptions import SubscriptionRepository
from app.modules.transactions import TransactionDto, TransactionRepository
from app.modules.users import UserRepository

_MAX_LEVEL: Final[int] = 3
_HUNDRED: Final[Decimal] = Decimal(100)
_MIN_PERCENT_REWARD: Final[Decimal] = Decimal(1)


@dataclass(frozen=True, kw_only=True)
class _Hop:
    level: int
    referrer_id: int
    referral_id: int


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


class AssignReferralRewardsUseCase(UseCase[AssignReferralRewardsDto, None]):
    required_permission = None

    def __init__(
        self,
        referral_repository: ReferralRepository,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        subscription_repository: SubscriptionRepository,
        uow: UnitOfWork,
        event_publisher: EventPublisher,
    ) -> None:
        self._referral_repository = referral_repository
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._subscription_repository = subscription_repository
        self._uow = uow
        self._event_publisher = event_publisher

    async def _execute(self, actor: Actor, data: AssignReferralRewardsDto) -> None:
        settings = await self._referral_repository.get_settings()
        if not settings.enabled:
            return
        order = await self._transaction_repository.get_by_idempotency_key(data.payment_key)
        # a bonus-day redemption carries a payment_key too, with no order behind it
        if order is None:
            logger.info(f"Referral reward skipped: no order for payment '{data.payment_key}'")
            return
        # unpaid or refunded orders earn nothing; a 100%-discount checkout is paid but free
        if order.status is not TransactionStatus.PAID or order.final_price <= 0:
            logger.info(
                f"Referral reward skipped: order for payment '{data.payment_key}' is "
                f"{order.status.value} at {order.final_price}"
            )
            return
        if not await self._purchase_earns_a_reward(settings.accrual_strategy, data):
            return

        chain = await self._walk_chain(data.user_id, settings.max_level)
        if not chain:
            return

        percent_base = (
            self._percent_base(order, settings.reward_type)
            if settings.reward_strategy is ReferralRewardStrategy.PERCENT
            else None
        )
        amounts = _level_amounts(settings, percent_base)

        # One failing hop must not cost the others their reward, but it must still
        # reach the task runner: swallowed here, retry_on_error never fires and the
        # hop is lost for good.
        first_failure: Optional[Exception] = None
        for hop in chain:
            amount = amounts.get(hop.level)
            if not amount or amount <= 0:
                continue
            try:
                await self._grant_one_level(hop, data, settings, amount)
            except Exception as error:  # re-raised below, after every hop has run
                logger.exception(
                    f"Referral reward failed at level '{hop.level}' for referrer "
                    f"'{hop.referrer_id}' (buyer '{data.user_id}')"
                )
                first_failure = first_failure or error

        if first_failure is not None:
            raise first_failure

    async def _walk_chain(self, buyer_id: int, max_level: int) -> list[_Hop]:
        # each hop keeps its own edge: re-fetching by referrer_id would return
        # the edge one level further up the chain
        chain: list[_Hop] = []
        seen: set[int] = {buyer_id}
        current_id = buyer_id
        for level in range(1, min(max_level, _MAX_LEVEL) + 1):
            edge = await self._referral_repository.get_by_referred_id(current_id)
            if edge is None or edge.referrer_id is None or edge.referrer_id in seen:
                break
            chain.append(_Hop(level=level, referrer_id=edge.referrer_id, referral_id=edge.id))
            seen.add(edge.referrer_id)
            current_id = edge.referrer_id
        return chain

    async def _purchase_earns_a_reward(
        self, strategy: ReferralAccrualStrategy, data: AssignReferralRewardsDto
    ) -> bool:
        is_first_payment_only = strategy is ReferralAccrualStrategy.FIRST_PAYMENT
        if is_first_payment_only and not data.is_new_purchase:
            return False

        try:
            subscription = await self._subscription_repository.get_by_id(data.subscription_id)
        except NotFoundError:
            logger.warning(
                f"Referral reward skipped: subscription '{data.subscription_id}' not found"
            )
            return False
        if subscription.is_trial:
            return False

        # is_new_purchase only means "bought, not renewed": a buyer's second and
        # third subscription get here too, and FIRST_PAYMENT would pay for each.
        # A trial converted in place doesn't count, its row is a trial.
        if is_first_payment_only and (
            await self._subscription_repository.has_paid_subscription_before(
                data.user_id, data.subscription_id
            )
        ):
            logger.info(
                f"Referral reward skipped: user '{data.user_id}' already had a paid "
                f"subscription and the accrual strategy is {strategy.value}"
            )
            return False
        return True

    @staticmethod
    def _percent_base(order: TransactionDto, reward_type: ReferralRewardType) -> Decimal:
        if reward_type is ReferralRewardType.EXTRA_DAYS:
            return Decimal(order.duration_days)
        # points are anchor-currency units, whatever the buyer paid in
        return order.anchor_final_price

    async def _grant_one_level(
        self,
        hop: _Hop,
        data: AssignReferralRewardsDto,
        settings: ReferralSettingsDto,
        amount: Decimal,
    ) -> None:
        referrer = await self._user_repository.get_by_id(hop.referrer_id)
        if referrer is None or referrer.deleted_at is not None or referrer.is_blocked:
            return

        reward_type = settings.reward_type
        if reward_type is ReferralRewardType.EXTRA_DAYS and settings.days_require_paid_subscription:
            async with self._uow:
                has_paid = await self._subscription_repository.has_paid_subscription_before(
                    hop.referrer_id
                )
            if not has_paid:
                logger.info(
                    f"Day reward skipped: referrer '{hop.referrer_id}' never paid for a plan"
                )
                return

        # ledger row and credit commit together: the row is the idempotency
        # guard, and a crash between them would record a reward never given
        if not await self._record_reward(hop, data, reward_type, amount):
            return

        async with self._uow:
            await self._event_publisher.publish(
                ReferralRewardIssuedEvent(
                    user=referrer,
                    level=hop.level,
                    reward_type=reward_type.value,
                    amount=str(amount),
                )
            )

    async def _record_reward(
        self,
        hop: _Hop,
        data: AssignReferralRewardsDto,
        reward_type: ReferralRewardType,
        amount: Decimal,
    ) -> bool:
        try:
            async with self._uow:
                await self._referral_repository.create_reward(
                    referral_id=hop.referral_id,
                    referrer_id=hop.referrer_id,
                    subscription_id=data.subscription_id,
                    payment_key=data.payment_key,
                    type=reward_type,
                    amount=amount,
                )
                if reward_type is ReferralRewardType.EXTRA_DAYS:
                    await self._user_repository.credit_bonus_days(hop.referrer_id, int(amount))
                else:
                    await self._user_repository.credit_points(hop.referrer_id, amount)
        except ConflictError:
            logger.info(
                f"Referral reward for payment '{data.payment_key}' referral "
                f"'{hop.referral_id}' already granted, skipping"
            )
            return False
        return True
