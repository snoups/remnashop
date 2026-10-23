import hmac
from typing import Optional

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PlanAvailability
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.modules.plans import PlanDto, PlanRepository
from app.modules.pricing import PricingRepository
from app.modules.subscriptions import PurchaseEligibility
from app.modules.transactions.dto import PriceQuote
from app.modules.transactions.ports import PromocodeLiveness
from app.modules.transactions.pricing import quote_price
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
    ) -> None:
        self._plan_repository = plan_repository
        self._user_repository = user_repository
        self._eligibility = eligibility
        self._pricing_repository = pricing_repository
        self._uow = uow
        self._promocode_liveness = promocode_liveness

    async def load_purchasable_plan(
        self, user_id: int, plan_id: int, plan_code: Optional[str]
    ) -> tuple[PlanDto, UserDto]:
        plan = await self._plan_repository.get_by_id(plan_id)
        user = await self._user_repository.find_by_id(user_id)
        if user is None:
            raise NotFoundError(f"User '{user_id}' not found", code=ErrorCode.USER_NOT_FOUND)

        if not await self._eligibility.is_purchasable(plan, user) or not link_code_matches(
            plan, plan_code
        ):
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

    async def quote(
        self, plan: PlanDto, duration_days: int, currency: Currency, user: UserDto
    ) -> PriceQuote:
        async with self._uow:
            rates = await self._pricing_repository.get_rate_table()
            return quote_price(plan, duration_days, currency, user, rates)
