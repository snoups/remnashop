from datetime import timedelta
from decimal import Decimal

from loguru import logger

from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, PurchaseType, SubscriptionStatus, TransactionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import ValidationError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.gateways import GatewayRepository
from app.modules.subscriptions import SubscriptionRepository, get_owned_target
from app.modules.transactions.recurring_dto import RecurringPaymentState, SetRecurringPaymentDto
from app.modules.transactions.recurring_repository import RecurringPaymentRepository
from app.modules.transactions.recurring_terms import build_recurring_terms
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserDto


class GetOwnRecurringPaymentUseCase(UseCase[int, RecurringPaymentState, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        recurring_repository: RecurringPaymentRepository,
        transaction_repository: TransactionRepository,
        subscription_repository: SubscriptionRepository,
        gateway_repository: GatewayRepository,
        uow: UnitOfWork,
        config: AppConfig,
    ) -> None:
        self._recurring = recurring_repository
        self._transactions = transaction_repository
        self._subscriptions = subscription_repository
        self._gateways = gateway_repository
        self._uow = uow
        self._config = config

    async def _execute(self, actor: UserDto, data: int) -> RecurringPaymentState:
        async with self._uow:
            subscription = await get_owned_target(self._subscriptions, data, actor.id)
            mandate = await self._recurring.get(data)
            gateway = await self._gateways.get_by_type(PaymentGatewayType.YOOKASSA)
            settings = await self._gateways.get_raw_settings(PaymentGatewayType.YOOKASSA)
            source = (
                await self._transactions.get_by_id(mandate.source_transaction_id)
                if mandate and mandate.source_transaction_id is not None
                else None
            )
        available = bool(
            mandate
            and mandate.payment_method_id
            and source
            and gateway.is_active
            and gateway.is_configured
            and gateway.flags.get("recurring_enabled", False)
            and mandate.shop_id == settings.get("shop_id")
            and subscription.status not in {SubscriptionStatus.DELETED, SubscriptionStatus.DISABLED}
            and not subscription.is_trial
            and subscription.plan_snapshot.plan_id == source.plan_id
            and source.status is TransactionStatus.PAID
            and source.duration_days > 0
            and source.base_price > 0
            and mandate.last_error != "payment_status_unknown"
            and source.plan_snapshot.terms_differ(subscription.plan_snapshot) is False
        )
        async with self._uow:
            authorized = (
                await self._recurring.consent_terms(mandate.consent_id) if mandate else None
            )
        enabled = bool(mandate and mandate.enabled and authorized)
        terms = (
            build_recurring_terms(
                config=self._config,
                user_id=actor.id,
                plan_id=source.plan_snapshot.plan_id,
                target_subscription_id=data,
                purchase_type=PurchaseType.RENEW,
                initial_amount=Decimal(0),
                amount_limit=source.base_price,
                currency=source.currency,
                duration_days=source.duration_days,
                locale=actor.language,
            )
            if available and source
            else None
        )
        return RecurringPaymentState(
            subscription_id=data,
            terms=terms,
            accepted_terms=authorized,
            enabled=enabled,
            available=available,
            customer_disabled=bool(mandate and mandate.customer_disabled),
            amount_limit=source.base_price if source else None,
            currency=source.currency.value if source else None,
            duration_days=source.duration_days if source else None,
            next_payment_at=(
                subscription.expire_at - timedelta(minutes=self._config.recurring.lead_minutes)
                if enabled and available
                else None
            ),
            last_error=mandate.last_error if mandate else None,
        )


class SetOwnRecurringPaymentUseCase(
    UseCase[SetRecurringPaymentDto, RecurringPaymentState, UserDto]
):
    required_permission = Permission.PUBLIC

    def __init__(
        self,
        recurring_repository: RecurringPaymentRepository,
        subscription_repository: SubscriptionRepository,
        get_own_recurring_payment: GetOwnRecurringPaymentUseCase,
        uow: UnitOfWork,
    ) -> None:
        self._recurring = recurring_repository
        self._subscriptions = subscription_repository
        self._get_state = get_own_recurring_payment
        self._uow = uow

    async def _execute(self, actor: UserDto, data: SetRecurringPaymentDto) -> RecurringPaymentState:
        state = await self._get_state(actor, data.subscription_id)
        if data.enabled and not state.available:
            raise ValidationError(
                "A saved YooKassa payment method is required; pay for the subscription first",
                code=ErrorCode.GATEWAY_NOT_AVAILABLE,
            )
        if data.enabled and (state.terms is None or data.terms_id != state.terms.terms_id):
            raise ValidationError(
                "Explicit consent to the current renewal terms is required",
                code=ErrorCode.PRICE_CHANGED,
            )
        async with self._uow:
            await get_owned_target(self._subscriptions, data.subscription_id, actor.id)
            await self._recurring.get(data.subscription_id, for_update=True)
            consent_id = None
            if data.enabled and state.terms is not None:
                consent_id = await self._recurring.record_consent(
                    state.terms,
                    channel=data.channel,
                    telegram_id=actor.telegram_id,
                    event_id=data.event_id,
                    ip_address=data.client_ip,
                )
            else:
                await self._recurring.revoke_consent(
                    data.subscription_id,
                    channel=data.channel,
                    event_id=data.event_id,
                    ip_address=data.client_ip,
                )
            await self._recurring.set_enabled(
                data.subscription_id, data.enabled, consent_id=consent_id
            )
        logger.info(
            f"{actor.log} Set auto-renewal of subscription '{data.subscription_id}' "
            f"to {data.enabled}"
        )
        return await self._get_state(actor, data.subscription_id)
