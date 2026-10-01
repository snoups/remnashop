from dataclasses import dataclass
from typing import Final, Optional

from loguru import logger

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import DiscountSource, PaymentGatewayType, TransactionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import PaymentGatewayError, PermissionDeniedError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.gateways import VERIFY_IP_FIELD_KEY, GatewaysRepository, gateway_flags
from app.modules.subscriptions import purchase_subscription_task
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.events import TransactionRefundedEvent
from app.modules.transactions.gateways.base import (
    PaymentGateway,
    WebhookAck,
    WebhookRequest,
    WebhookSignal,
)
from app.modules.transactions.gateways.factory import PaymentGatewayFactory
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserRepository

# Final for a paid claim: an order the TTL sweep or a provider CANCELED/FAILED
# can still receive a late payment, and confirm() re-checks it against the
# provider anyway. REFUNDED is final because it was paid and provisioned once
# already, and the provider still reports that original payment as paid --
# re-confirming it would provision it a second time.
_TERMINAL_STATUSES: Final[frozenset[TransactionStatus]] = frozenset(
    {TransactionStatus.PAID, TransactionStatus.REFUNDED}
)
_UNPAID_FINAL: Final[frozenset[TransactionStatus]] = frozenset(
    {TransactionStatus.CANCELED, TransactionStatus.FAILED}
)
_UNPAID_STATUSES: Final[frozenset[TransactionStatus]] = frozenset(
    {TransactionStatus.PENDING, TransactionStatus.CANCELED}
)
# which current statuses a reported status may replace
_REPORTED_FROM: Final[dict[TransactionStatus, frozenset[TransactionStatus]]] = {
    TransactionStatus.FAILED: _UNPAID_STATUSES,
    TransactionStatus.CANCELED: _UNPAID_STATUSES,
    TransactionStatus.REFUNDED: frozenset({TransactionStatus.PAID}),
}


@dataclass(frozen=True, kw_only=True)
class HandleWebhookInput:
    gateway_type: PaymentGatewayType
    request: WebhookRequest


class HandlePaymentWebhookUseCase(UseCase[HandleWebhookInput, WebhookAck]):
    required_permission = None

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        gateways_repository: GatewaysRepository,
        gateway_factory: PaymentGatewayFactory,
        user_repository: UserRepository,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._user_repository = user_repository
        self._transaction_repository = transaction_repository
        self._gateways_repository = gateways_repository
        self._gateway_factory = gateway_factory
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: Actor, data: HandleWebhookInput) -> WebhookAck:
        async with self._uow:
            settings = await self._gateways_repository.get_raw_settings(data.gateway_type)
            gateway = self._gateway_factory.build(data.gateway_type, settings)

        self._assert_trusted_source(gateway, data, settings)

        try:
            signal = await gateway.parse_webhook(data.request)
        except PaymentGatewayError:
            raise
        except Exception as error:  # noqa: BLE001 -- an adapter that leaks its own parse
            # errors still owes the caller the documented contract (see
            # PaymentGateway.parse_webhook), not a 500 with a stack trace.
            raise PaymentGatewayError("Could not parse webhook") from error
        if signal is None or not signal.claims_paid:
            await self._record_reported_status(data.gateway_type, signal)
            return gateway.webhook_ack(signal)

        order = await self._resolve_order(data.gateway_type, signal)
        if order is None or order.status in _TERMINAL_STATUSES:
            return gateway.webhook_ack(signal)
        if order.discount_source is DiscountSource.PURCHASE and order.status in _UNPAID_FINAL:
            # its one-shot discount went back to the customer when it was
            # canceled; fulfilling it now would let that discount be spent twice
            logger.warning(
                f"Late payment for canceled order '{order.id}' quoted with a purchase discount "
                f"was not fulfilled ({data.gateway_type.value}) -- refund it manually"
            )
            return gateway.webhook_ack(signal)

        try:
            payment = await gateway.confirm(order, signal)
        except PaymentGatewayError:
            raise
        except Exception as error:  # noqa: BLE001 -- any provider API failure is a gateway problem
            raise PaymentGatewayError("Could not confirm payment") from error
        if payment is None:
            raise PaymentGatewayError(
                f"{data.gateway_type.value} webhook for order {order.id} "
                "was not confirmed by the provider"
            )

        async with self._uow:
            await self._transaction_repository.mark_status(
                order.id,
                TransactionStatus.PAID,
                external_payment_id=payment.provider_payment_id or order.external_payment_id,
            )
        if order.is_test:
            logger.info(f"Test transaction '{order.id}' confirmed by {data.gateway_type.value}")
            return gateway.webhook_ack(signal)
        await purchase_subscription_task.kiq(  # type: ignore[call-overload]
            user_id=order.user_id,
            plan_snapshot=order.plan_snapshot.to_json(),
            duration_days=order.duration_days,
            price_paid=str(order.final_price),
            base_price=str(order.base_price),
            currency=order.currency.value,
            purchase_type=order.purchase_type.value,
            target_subscription_id=order.target_subscription_id,
            idempotency_key=order.idempotency_key,
        )

        return gateway.webhook_ack(signal)

    @staticmethod
    def _assert_trusted_source(
        gateway: PaymentGateway, data: HandleWebhookInput, settings: dict[str, str]
    ) -> None:
        if not gateway.trusted_networks:
            return
        if not gateway_flags(data.gateway_type, settings).get(VERIFY_IP_FIELD_KEY, True):
            return
        if gateway.is_trusted_source(data.request.client_ip):
            return
        logger.warning(
            f"{data.gateway_type.value} webhook from untrusted IP '{data.request.client_ip}'"
        )
        raise PermissionDeniedError(
            "Webhook source is not trusted", code=ErrorCode.WEBHOOK_SOURCE_UNTRUSTED
        )

    async def _record_reported_status(
        self,
        gateway_type: PaymentGatewayType,
        signal: Optional[WebhookSignal],
    ) -> None:
        if signal is None or signal.reported_status is None:
            return
        status = signal.reported_status
        allowed_from = _REPORTED_FROM.get(status, frozenset())
        order = await self._resolve_order(gateway_type, signal)
        if order is None or order.status not in allowed_from:
            return
        # Only the PENDING -> unpaid transition hands a spent purchase discount
        # back: a second CANCELED for an already-canceled order must not restore
        # it again after the customer spent the first restore elsewhere.
        restores_discount = (
            order.discount_source is DiscountSource.PURCHASE
            and order.status is TransactionStatus.PENDING
            and status in _UNPAID_FINAL
        )
        if restores_discount:
            allowed_from = frozenset({TransactionStatus.PENDING})
        async with self._uow:
            changed = await self._transaction_repository.mark_status_if(
                order.id, status, current=allowed_from
            )
            if changed and restores_discount:
                await self._user_repository.restore_purchase_discount(
                    order.user_id, order.discount_percent, order.discount_promocode_id
                )
            if changed and status is TransactionStatus.REFUNDED:
                await self._event_publisher.publish(
                    TransactionRefundedEvent(
                        order_id=order.id,
                        user_id=order.user_id,
                        gateway_type=gateway_type.value,
                        amount=str(order.final_price),
                        currency=order.currency.value,
                    )
                )
        if not changed:
            return
        logger.info(f"Order '{order.id}' marked {status.value} by {gateway_type.value} webhook")

    async def _resolve_order(
        self, gateway_type: PaymentGatewayType, signal: WebhookSignal
    ) -> Optional[TransactionDto]:
        # Scoped to the gateway the callback arrived on: a reference is only
        # meaningful within the gateway that was handed it.
        async with self._uow:
            if signal.reference:
                order = await self._transaction_repository.get_by_idempotency_key(
                    signal.reference, gateway_type=gateway_type
                )
                if order is not None:
                    return order
            if signal.provider_payment_id:
                return await self._transaction_repository.get_by_external_payment_id(
                    signal.provider_payment_id, gateway_type=gateway_type
                )
            return None
