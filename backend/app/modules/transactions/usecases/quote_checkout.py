from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.transactions.checkout_pricing import CheckoutPricer
from app.modules.transactions.dto import PriceQuote, QuoteCheckoutDto
from app.modules.users import UserDto


class QuoteCheckoutUseCase(UseCase[QuoteCheckoutDto, PriceQuote, UserDto]):
    """The price checkout would charge right now. Gateway, subscription cap and
    payments_enabled are checkout's own refusals, so they aren't checked here."""

    required_permission = Permission.PUBLIC

    def __init__(self, pricer: CheckoutPricer, uow: UnitOfWork) -> None:
        self._pricer = pricer
        self._uow = uow

    async def _execute(self, actor: UserDto, data: QuoteCheckoutDto) -> PriceQuote:
        async with self._uow:
            plan, user = await self._pricer.load_purchasable_plan(
                actor.id, data.plan_id, data.plan_code, data.renew_subscription_id
            )
        user = await self._pricer.drop_dead_promocode_discounts(user)
        return await self._pricer.quote(plan, data.duration_days, data.currency, user)
