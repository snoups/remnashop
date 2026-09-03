from typing import Final

from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, PaymentOrderStatus
from app.core.exceptions import PaymentGatewayError
from app.core.usecase import UseCase
from app.modules.gateways import GatewaysRepository
from app.modules.payments.gateways.base import PaymentGateway
from app.modules.payments.gateways.yookassa import YooKassaGateway
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.subscriptions import purchase_subscription_task
from app.modules.users import UserDto

# EXPIRED excluded deliberately -- the TTL sweep may mark an order EXPIRED
# while a gateway payment is still in flight; a late webhook should still be
# able to verify and honor it instead of silently dropping the payment.
_TERMINAL_STATUSES: Final[frozenset[PaymentOrderStatus]] = frozenset(
    {
        PaymentOrderStatus.PAID,
        PaymentOrderStatus.FAILED,
        PaymentOrderStatus.CANCELED,
    }
)


class HandleYooKassaWebhookUseCase(UseCase[str, None]):
    # System-invoked only -- YooKassa calls this endpoint server-to-server,
    # no session exists to bind a real actor.
    required_permission = None

    def __init__(
        self,
        payment_order_repository: PaymentOrderRepository,
        gateways_repository: GatewaysRepository,
        uow: UnitOfWork,
    ) -> None:
        self._payment_order_repository = payment_order_repository
        self._gateways_repository = gateways_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: str) -> None:
        external_payment_id = data
        order = await self._payment_order_repository.get_by_external_payment_id(external_payment_id)
        if order is None or order.status in _TERMINAL_STATUSES:
            return

        settings = await self._gateways_repository.get_raw_settings(PaymentGatewayType.YOOKASSA)
        gateway: PaymentGateway = YooKassaGateway()
        try:
            verified = await gateway.verify_payment(external_payment_id, settings)
        except Exception as error:
            raise PaymentGatewayError("Could not verify payment") from error
        if not verified:
            return

        async with self._uow:
            await self._payment_order_repository.mark_status(order.id, PaymentOrderStatus.PAID)

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
