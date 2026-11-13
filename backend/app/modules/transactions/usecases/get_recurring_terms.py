from typing import Optional

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import Currency, PaymentGatewayType, PurchaseType
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways import GatewayRepository
from app.modules.transactions.checkout_pricing import CheckoutPricer
from app.modules.transactions.dto import CreateCheckoutDto
from app.modules.transactions.recurring_terms import RecurringTerms, build_recurring_terms
from app.modules.users import UserDto


class GetCheckoutRecurringTermsUseCase(
    UseCase[CreateCheckoutDto, Optional[RecurringTerms], UserDto]
):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        pricer: CheckoutPricer,
        gateway_repository: GatewayRepository,
        uow: UnitOfWork,
        config: AppConfig,
    ) -> None:
        self._pricer = pricer
        self._gateways = gateway_repository
        self._uow = uow
        self._config = config

    async def _execute(self, actor: UserDto, data: CreateCheckoutDto) -> Optional[RecurringTerms]:
        if (
            data.gateway_type is not PaymentGatewayType.YOOKASSA
            or data.currency is not Currency.RUB
        ):
            return None
        async with self._uow:
            gateway = await self._gateways.get_by_type(data.gateway_type)
            if not (
                gateway.is_active
                and gateway.is_configured
                and gateway.flags.get("recurring_enabled", False)
            ):
                return None
            plan, user = await self._pricer.load_purchasable_plan(
                actor.id,
                data.plan_id,
                data.plan_code,
                data.target_subscription_id if data.purchase_type is PurchaseType.RENEW else None,
            )
        user = await self._pricer.drop_dead_promocode_discounts(user)
        quote = await self._pricer.quote(plan, data.duration_days, data.currency, user)
        if plan.is_trial or data.duration_days <= 0 or quote.final_price <= 0:
            return None
        return build_recurring_terms(
            config=self._config,
            user_id=actor.id,
            plan_id=plan.id,
            target_subscription_id=data.target_subscription_id,
            purchase_type=data.purchase_type,
            initial_amount=quote.final_price,
            amount_limit=quote.base_price,
            currency=data.currency,
            duration_days=data.duration_days,
            locale=data.legal_locale or user.language,
        )
