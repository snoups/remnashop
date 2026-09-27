from dataclasses import dataclass
from typing import Final, Optional

from loguru import logger

from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.core.ports import EventPublisher
from app.core.usecase import UseCase
from app.modules.gateways import GatewaysRepository
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.events import PaymentOrderRefundedEvent
from app.modules.payments.gateways.base import WebhookAck, WebhookRequest, WebhookSignal
from app.modules.payments.gateways.factory import PaymentGatewayFactory
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.subscriptions import purchase_subscription_task
from app.modules.users import UserDto

# Only PAID is final for a paid claim: an order the TTL sweep or a provider
# CANCELED/FAILED can still receive a late payment, and confirm() re-checks
# it against the provider anyway.
_TERMINAL_STATUSES: Final[frozenset[PaymentOrderStatus]] = frozenset({PaymentOrderStatus.PAID})
_UNPAID_STATUSES: Final[frozenset[PaymentOrderStatus]] = frozenset(
    {PaymentOrderStatus.PENDING, PaymentOrderStatus.CANCELED}
)
# which current statuses a reported status may replace
_REPORTED_FROM: Final[dict[PaymentOrderStatus, frozenset[PaymentOrderStatus]]] = {
    PaymentOrderStatus.FAILED: _UNPAID_STATUSES,
    PaymentOrderStatus.CANCELED: _UNPAID_STATUSES,
    PaymentOrderStatus.REFUNDED: frozenset({PaymentOrderStatus.PAID}),
}


@dataclass(frozen=True, kw_only=True)
class HandleWebhookInput:
    gateway_type: PaymentGatewayType
    request: WebhookRequest


class HandlePaymentWebhookUseCase(UseCase[HandleWebhookInput, WebhookAck]):
    required_permission = None

    def __init__(
        self,
        payment_order_repository: PaymentOrderRepository,
        gateways_repository: GatewaysRepository,
        gateway_factory: PaymentGatewayFactory,
        event_publisher: EventPublisher,
        uow: UnitOfWork,
    ) -> None:
        self._payment_order_repository = payment_order_repository
        self._gateways_repository = gateways_repository
        self._gateway_factory = gateway_factory
        self._event_publisher = event_publisher
        self._uow = uow

    async def _execute(self, actor: UserDto, data: HandleWebhookInput) -> WebhookAck:
        async with self._uow:
            settings = await self._gateways_repository.get_raw_settings(data.gateway_type)
            gateway = self._gateway_factory.build(data.gateway_type, settings)

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
            await self._payment_order_repository.mark_status(
                order.id,
                PaymentOrderStatus.PAID,
                external_payment_id=payment.provider_payment_id or order.external_payment_id,
            )
        if order.is_test:
            logger.info(f"Test payment order '{order.id}' confirmed by {data.gateway_type.value}")
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
        async with self._uow:
            changed = await self._payment_order_repository.mark_status_if(
                order.id, status, current=allowed_from
            )
            if changed and status is PaymentOrderStatus.REFUNDED:
                await self._event_publisher.publish(
                    PaymentOrderRefundedEvent(
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
    ) -> Optional[PaymentOrderDto]:
        # Scoped to the gateway the callback arrived on: a reference is only
        # meaningful within the gateway that was handed it.
        async with self._uow:
            if signal.reference:
                order = await self._payment_order_repository.get_by_idempotency_key(
                    signal.reference, gateway_type=gateway_type
                )
                if order is not None:
                    return order
            if signal.provider_payment_id:
                return await self._payment_order_repository.get_by_external_payment_id(
                    signal.provider_payment_id, gateway_type=gateway_type
                )
            return None
