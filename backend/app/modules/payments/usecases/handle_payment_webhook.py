from dataclasses import dataclass
from typing import Final, Optional

from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.core.usecase import UseCase
from app.modules.gateways import GatewaysRepository
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import WebhookAck, WebhookRequest, WebhookSignal
from app.modules.payments.gateways.factory import PaymentGatewayFactory
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.subscriptions import purchase_subscription_task
from app.modules.users import UserDto

# EXPIRED excluded deliberately -- the TTL sweep may mark an order EXPIRED
# while a payment is still in flight; a late webhook should still be honoured.
_TERMINAL_STATUSES: Final[frozenset[PaymentOrderStatus]] = frozenset(
    {
        PaymentOrderStatus.PAID,
        PaymentOrderStatus.FAILED,
        PaymentOrderStatus.CANCELED,
    }
)


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
        uow: UnitOfWork,
    ) -> None:
        self._payment_order_repository = payment_order_repository
        self._gateways_repository = gateways_repository
        self._gateway_factory = gateway_factory
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
