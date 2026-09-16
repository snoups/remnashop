from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.payments.dto import PaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.users import UserDto


class GetPaymentOrderUseCase(UseCase[int, PaymentOrderDto]):
    required_permission = Permission.PAYMENTS_ORDER_VIEW

    def __init__(self, payment_order_repository: PaymentOrderRepository, uow: UnitOfWork) -> None:
        self._payment_order_repository = payment_order_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> PaymentOrderDto:
        async with self._uow:
            return await self._payment_order_repository.get_by_id(data)
