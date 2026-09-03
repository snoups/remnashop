from dataclasses import dataclass
from typing import Final, Optional

from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.core.usecase import UseCase
from app.modules.gateways import GatewaysRepository
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.gateways.base import WebhookRequest, WebhookResult
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


class HandlePaymentWebhookUseCase(UseCase[HandleWebhookInput, str]):
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

    async def _execute(self, actor: UserDto, data: HandleWebhookInput) -> str:
        settings = await self._gateways_repository.get_raw_settings(data.gateway_type)
        gateway = self._gateway_factory.build(data.gateway_type, settings)

        result = await gateway.parse_webhook(data.request)
        if result is None:
            return gateway.webhook_ack(None)

        order = await self._resolve_order(result)
        if order is None or order.status in _TERMINAL_STATUSES:
            return gateway.webhook_ack(result)

        if result.status is not PaymentOrderStatus.PAID:
            return gateway.webhook_ack(result)

        try:
            verified = await gateway.verify_payment(order)
        except Exception as error:  # noqa: BLE001 -- any verify failure is a gateway problem
            raise PaymentGatewayError("Could not verify payment") from error
        if not verified:
            return gateway.webhook_ack(result)

        async with self._uow:
            await self._payment_order_repository.mark_status(
                order.id,
                PaymentOrderStatus.PAID,
                external_payment_id=result.provider_payment_id,
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

        return gateway.webhook_ack(result)

    async def _resolve_order(self, result: WebhookResult) -> Optional[PaymentOrderDto]:
        if result.reference:
            order = await self._payment_order_repository.get_by_idempotency_key(result.reference)
            if order is not None:
                return order
        if result.provider_payment_id:
            return await self._payment_order_repository.get_by_external_payment_id(
                result.provider_payment_id
            )
        return None
