from datetime import timedelta
from typing import Final, Optional
from uuid import uuid4

import httpx
from loguru import logger

from app.core.actor import Actor
from app.core.config import AppConfig
from app.core.db.uow import UnitOfWork
from app.core.enums import (
    Currency,
    PaymentGatewayType,
    PurchaseType,
    SubscriptionStatus,
    TransactionStatus,
)
from app.core.exceptions import AppError, PaymentGatewayError
from app.core.usecase import UseCase
from app.core.utils.time import datetime_now
from app.modules.gateways import GatewayRepository
from app.modules.settings import SettingsRepository
from app.modules.subscriptions import (
    PlanSnapshot,
    PurchaseSubscriptionDispatch,
    SubscriptionRepository,
)
from app.modules.transactions.checkout_pricing import CheckoutPricer
from app.modules.transactions.dto import CreateTransactionDto, TransactionDto
from app.modules.transactions.fulfillment import settle_verified_payment
from app.modules.transactions.gateways.base import WebhookSignal
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.gateways.yookassa import YooKassaGateway
from app.modules.transactions.recurring_dto import RecurringPaymentDto
from app.modules.transactions.recurring_repository import RecurringPaymentRepository
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserRepository

# YooKassa retains idempotency keys for 24h. Never re-POST an ambiguous request
# after that window; a new payment could otherwise debit the customer twice.
_SAFE_REPOST_WINDOW: Final[timedelta] = timedelta(hours=23)


class ProcessRecurringPaymentsUseCase(UseCase[None, None]):
    required_permission = None

    def __init__(
        self,
        recurring_repository: RecurringPaymentRepository,
        transaction_repository: TransactionRepository,
        subscription_repository: SubscriptionRepository,
        user_repository: UserRepository,
        gateway_repository: GatewayRepository,
        settings_repository: SettingsRepository,
        pricer: CheckoutPricer,
        gateway_factory: PaymentGatewayFactory,
        purchase_dispatch: PurchaseSubscriptionDispatch,
        uow: UnitOfWork,
        config: AppConfig,
    ) -> None:
        self._recurring = recurring_repository
        self._transactions = transaction_repository
        self._subscriptions = subscription_repository
        self._users = user_repository
        self._gateways = gateway_repository
        self._settings = settings_repository
        self._pricer = pricer
        self._factory = gateway_factory
        self._dispatch = purchase_dispatch
        self._uow = uow
        self._config = config

    async def _execute(self, actor: Actor, data: None) -> None:
        now = datetime_now()
        async with self._uow:
            ids = await self._recurring.list_due(
                now,
                due_before=now + timedelta(minutes=self._config.recurring.lead_minutes),
                limit=self._config.recurring.batch_size,
            )
        for subscription_id in ids:
            try:
                await self._process(subscription_id)
            except Exception as error:
                await self._uow.rollback()
                # Provider exception bodies may contain a saved payment method.
                logger.error(
                    f"Recurring payment for subscription '{subscription_id}': "
                    f"{type(error).__name__}"
                )
                async with self._uow:
                    await self._defer(subscription_id, "provider_unavailable")

    async def _defer(self, subscription_id: int, error: Optional[str] = None) -> None:
        await self._recurring.defer(
            subscription_id,
            datetime_now() + timedelta(minutes=self._config.recurring.retry_minutes),
            error,
        )

    async def _gateway(self) -> YooKassaGateway:
        settings = await self._gateways.get_raw_settings(PaymentGatewayType.YOOKASSA)
        gateway = self._factory.build(PaymentGatewayType.YOOKASSA, settings)
        if not isinstance(gateway, YooKassaGateway):
            raise PaymentGatewayError("Unexpected YooKassa gateway implementation")
        return gateway

    async def _enabled(self) -> bool:
        gateway = await self._gateways.get_by_type(PaymentGatewayType.YOOKASSA)
        access = await self._settings.get_access_settings()
        return bool(
            access.payments_enabled
            and gateway.is_active
            and gateway.is_configured
            and gateway.flags.get("recurring_enabled", False)
        )

    async def _process(self, subscription_id: int) -> None:
        async with self._uow:
            mandate = await self._recurring.get(subscription_id)
            if mandate is None:
                return
        if mandate.pending_transaction_id is None:
            await self._reserve(mandate)
        await self._charge_or_poll(subscription_id)

    async def _reservation_gateway(
        self, mandate: RecurringPaymentDto, customer_email: Optional[str]
    ) -> Optional[YooKassaGateway]:
        gateway = await self._gateway()
        if mandate.shop_id != gateway.settings.shop_id or not mandate.payment_method_id:
            await self._recurring.disable(mandate.subscription_id, "shop_changed")
            return None
        if gateway.settings.vat_code is not None and not customer_email:
            await self._recurring.disable(mandate.subscription_id, "customer_email_required")
            return None
        return gateway

    async def _reserve(self, mandate: RecurringPaymentDto) -> None:
        async with self._uow:
            if not mandate.enabled or not await self._enabled():
                await self._defer(mandate.subscription_id)
                return
            source = (
                await self._transactions.get_by_id(mandate.source_transaction_id)
                if mandate.source_transaction_id is not None
                else None
            )
            subscription = await self._subscriptions.get_by_id(mandate.subscription_id)
            user = await self._users.find_by_id(subscription.user_id)
        if (
            source is None
            or source.status is not TransactionStatus.PAID
            or user is None
            or user.deleted_at is not None
            or user.is_blocked
        ):
            async with self._uow:
                await self._recurring.disable(mandate.subscription_id, "subscription_unavailable")
            return
        try:
            async with self._uow:
                plan, user = await self._pricer.load_purchasable_plan(
                    user.id, source.plan_snapshot.plan_id, None, subscription.id
                )
            user = await self._pricer.drop_dead_promocode_discounts(user)
            # A one-shot discount is reserved by interactive checkouts, never by a timer.
            quote = await self._pricer.quote(
                plan,
                source.duration_days,
                Currency.RUB,
                user.model_copy(update={"purchase_discount": 0}),
            )
        except AppError:
            async with self._uow:
                await self._recurring.disable(mandate.subscription_id, "plan_unavailable")
            return

        async with self._uow:
            current = await self._recurring.get(subscription.id, for_update=True)
            if current is None or not current.enabled or current.pending_transaction_id is not None:
                return
            if current.source_transaction_id != source.id or not await self._enabled():
                await self._defer(subscription.id)
                return
            shop = await self._settings.get_shop_settings()
            customer_email = shop.payment_email or user.email or source.customer_email
            gateway = await self._reservation_gateway(current, customer_email)
            if gateway is None:
                return
            vat_code = gateway.settings.vat_code
            subscription = await self._subscriptions.get_by_id_for_update(subscription.id)
            now = datetime_now()
            if subscription.expire_at > now + timedelta(
                minutes=self._config.recurring.lead_minutes
            ):
                await self._defer(subscription.id)
                return
            new_snapshot = PlanSnapshot.from_plan(
                plan,
                price_paid=quote.final_price,
                currency=Currency.RUB,
                duration_days=source.duration_days,
            )
            if (
                subscription.status
                not in {
                    SubscriptionStatus.ACTIVE,
                    SubscriptionStatus.EXPIRED,
                    SubscriptionStatus.LIMITED,
                }
                or subscription.is_trial
                or subscription.plan_snapshot.plan_id != source.plan_id
                or source.plan_snapshot.terms_differ(subscription.plan_snapshot)
                or subscription.plan_snapshot.terms_differ(new_snapshot)
                or subscription.expire_at
                < now - timedelta(hours=self._config.recurring.max_overdue_hours)
            ):
                await self._recurring.disable(subscription.id, "subscription_changed")
                return
            if quote.final_price <= 0 or quote.final_price > source.base_price:
                await self._recurring.disable(subscription.id, "price_changed")
                return
            order = await self._transactions.create(
                CreateTransactionDto(
                    user_id=user.id,
                    plan_id=plan.id,
                    plan_snapshot=new_snapshot,
                    duration_days=source.duration_days,
                    currency=Currency.RUB,
                    purchase_type=PurchaseType.RENEW,
                    channel=source.channel,
                    target_subscription_id=subscription.id,
                    gateway_type=PaymentGatewayType.YOOKASSA,
                    base_price=quote.base_price,
                    discount_percent=quote.discount_percent,
                    discount_source=quote.discount_source,
                    plan_discount_percent=quote.plan_discount_percent,
                    final_price=quote.final_price,
                    anchor_base_price=quote.anchor_base_price,
                    anchor_final_price=quote.anchor_final_price,
                    customer_email=customer_email,
                    idempotency_key=uuid4().hex,
                    expires_at=now + _SAFE_REPOST_WINDOW,
                    recurring_consent=True,
                    is_recurring=True,
                    yookassa_receipt_vat_code=int(vat_code) if vat_code is not None else None,
                )
            )
            await self._recurring.set_pending(subscription.id, order.id)
        logger.info(f"Reserved recurring order '{order.id}' for subscription '{subscription.id}'")

    async def _charge_or_poll(self, subscription_id: int) -> None:
        async with self._uow:
            mandate = await self._recurring.get(subscription_id, for_update=True)
            if mandate is None or mandate.pending_transaction_id is None:
                return
            order = await self._transactions.get_by_id(mandate.pending_transaction_id)
            if order.status is TransactionStatus.PAID:
                await self._defer(subscription_id)
                return
            if order.status is not TransactionStatus.PENDING:
                await self._recurring.fail_pending(subscription_id, "payment_canceled")
                await self._defer(subscription_id, "payment_canceled")
                return
            gateway = await self._gateway()
            if mandate.shop_id != gateway.settings.shop_id:
                await self._recurring.disable(subscription_id, "shop_changed")
                await self._defer(subscription_id, "shop_changed")
                return
            await self._defer(subscription_id)
            if order.external_payment_id is None:
                if (
                    order.created_at is None
                    or datetime_now() - order.created_at >= _SAFE_REPOST_WINDOW
                ):
                    await self._recurring.disable(subscription_id, "payment_status_unknown")
                    return
                if (
                    not mandate.enabled
                    or not mandate.payment_method_id
                    or not await self._enabled()
                ):
                    return
                await self._recurring.mark_attempted(subscription_id)
        if order.external_payment_id is None:
            await self._charge(subscription_id, order, first_attempt=mandate.attempted_at is None)
            async with self._uow:
                order = await self._transactions.get_by_id(order.id)
        if order.external_payment_id is not None:
            await self._poll(subscription_id, order, gateway)

    async def _charge(
        self, subscription_id: int, order: TransactionDto, *, first_attempt: bool
    ) -> None:
        # The durable order+key precede the HTTP call. The mandate lock serializes
        # a customer's disable action with sending the request; timeouts reuse this key.
        async with self._uow:
            mandate = await self._recurring.get(subscription_id, for_update=True)
            if mandate is None or not mandate.enabled or not mandate.payment_method_id:
                return
            if mandate.pending_transaction_id != order.id or not await self._enabled():
                return
            gateway = await self._gateway()
            if mandate.shop_id != gateway.settings.shop_id:
                return
            subscription = await self._subscriptions.get_by_id(subscription_id)
            user = await self._users.find_by_id(order.user_id)
            if (
                user is None
                or user.is_blocked
                or user.deleted_at is not None
                or subscription.status in {SubscriptionStatus.DELETED, SubscriptionStatus.DISABLED}
                or subscription.plan_snapshot.terms_differ(order.plan_snapshot)
                or subscription.plan_snapshot.plan_id != order.plan_id
            ):
                await self._recurring.disable(subscription_id, "subscription_unavailable")
                return
            try:
                intent = await gateway.create_recurring_payment(order, mandate.payment_method_id)
            except httpx.HTTPStatusError as error:
                if error.response.status_code not in {400, 401, 403, 404}:
                    raise
                if not first_attempt:
                    # A rejected retry cannot establish what happened to a
                    # previous request whose response was lost (e.g. revoked API key).
                    await self._recurring.disable(subscription_id, "payment_status_unknown")
                    return
                await self._recurring.disable(subscription_id, "provider_rejected")
                # Commit the refusal before marking the order, avoiding a lock
                # inversion with the subscription fulfillment handler.
                intent = None
        async with self._uow:
            await self._transactions.mark_status_if(
                order.id,
                TransactionStatus.PENDING if intent else TransactionStatus.FAILED,
                current=frozenset({TransactionStatus.PENDING}),
                external_payment_id=intent.provider_payment_id if intent else None,
            )

    async def _poll(
        self, subscription_id: int, order: TransactionDto, gateway: YooKassaGateway
    ) -> None:
        payment = await gateway.fetch_payment(
            order, WebhookSignal(reference=order.idempotency_key, claims_paid=True)
        )
        if gateway.payment_matches(order, payment):
            await settle_verified_payment(
                order, payment, self._transactions, self._uow, self._dispatch
            )
            logger.info(f"Recurring order '{order.id}' confirmed by YooKassa")
        elif payment.status is TransactionStatus.CANCELED:
            async with self._uow:
                await self._transactions.mark_status_if(
                    order.id,
                    TransactionStatus.CANCELED,
                    current=frozenset({TransactionStatus.PENDING}),
                )
                await self._recurring.fail_pending(subscription_id, "payment_canceled")
