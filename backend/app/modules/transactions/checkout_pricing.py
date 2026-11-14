import hmac
from decimal import Decimal
from typing import Optional

from loguru import logger

from app.core.constants import ZERO_AMOUNT
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PlanAvailability
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.modules.plans import PlanDto, PlanRepository
from app.modules.pricing import PricingRepository
from app.modules.subscriptions import PurchaseEligibility, SubscriptionRepository, get_owned_target
from app.modules.transactions.dto import PriceQuote
from app.modules.transactions.ports import PromocodeLiveness
from app.modules.transactions.pricing import change_credit_for, quote_price
from app.modules.users import UserDto, UserRepository


def link_code_matches(plan: PlanDto, plan_code: Optional[str]) -> bool:
    if plan.availability is not PlanAvailability.LINK:
        return True
    # bytes: compare_digest refuses a str with non-ASCII characters
    return plan_code is not None and hmac.compare_digest(
        plan_code.encode(), plan.public_code.encode()
    )


class CheckoutPricer:
    """The pricing path shared by checkout and its quote, so both name the same price."""

    def __init__(
        self,
        plan_repository: PlanRepository,
        user_repository: UserRepository,
        eligibility: PurchaseEligibility,
        pricing_repository: PricingRepository,
        uow: UnitOfWork,
        promocode_liveness: PromocodeLiveness,
        subscription_repository: SubscriptionRepository,
    ) -> None:
        self._plan_repository = plan_repository
        self._user_repository = user_repository
        self._eligibility = eligibility
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._promocode_liveness = promocode_liveness
        self._subscription_repository = subscription_repository

    async def load_purchasable_plan(
        self,
        user_id: int,
        plan_id: int,
        plan_code: Optional[str],
        renew_subscription_id: Optional[int] = None,
    ) -> tuple[PlanDto, UserDto]:
        plan = await self._plan_repository.get_by_id(plan_id)
        user = await self._user_repository.find_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User '{user_id}' not found", code=ErrorCode.USER_NOT_FOUND)

        if renew_subscription_id is not None:
            allowed = bool(
                await self._eligibility.renewable([plan], user.id, renew_subscription_id)
            )
        else:
            allowed = await self._eligibility.is_purchasable(plan, user) and link_code_matches(
                plan, plan_code
            )
        if not allowed:
            # Same answer as a missing plan: a distinct one would let anyone
            # walk plan ids and learn which hidden plans exist.
            raise NotFoundError(f"Plan '{plan_id}' not found", code=ErrorCode.PLAN_NOT_FOUND)
        return plan, user

    async def drop_dead_promocode_discounts(self, user: UserDto) -> UserDto:
        sources = {
            source
            for source in (user.personal_discount_promocode_id, user.purchase_discount_promocode_id)
            if source is not None
        }
        if not sources:
            return user
        async with self._uow:
            dead = {
                source for source in sources if not await self._promocode_liveness.is_live(source)
            }
            if not dead:
                return user
            await self._user_repository.clear_discounts_from(dead, user_id=user.id)
            refreshed = await self._user_repository.find_by_id(user.id)
        if refreshed is None:
            raise NotFoundError(f"User '{user.id}' not found", code=ErrorCode.USER_NOT_FOUND)
        logger.info(f"{user.log} Dropped discounts from ended promocodes {sorted(dead)}")
        return refreshed

    async def change_credit(
        self,
        user_id: int,
        target_subscription_id: Optional[int],
        duration_days: int,
        currency: Currency,
    ) -> Decimal:
        if target_subscription_id is None or duration_days != 0:
            return ZERO_AMOUNT
        async with self._uow:
            target = await get_owned_target(
                self._subscription_repository, target_subscription_id, user_id
            )
            rates = await self._pricing_repository.get_rate_table()
        return change_credit_for(target, duration_days, currency, rates)

    async def quote(
        self,
        plan: PlanDto,
        duration_days: int,
        currency: Currency,
        user: UserDto,
        *,
        change_credit: Decimal = ZERO_AMOUNT,
    ) -> PriceQuote:
        async with self._uow:
            rates = await self._pricing_repository.get_rate_table()
            return quote_price(
                plan, duration_days, currency, user, rates, change_credit=change_credit
            )
