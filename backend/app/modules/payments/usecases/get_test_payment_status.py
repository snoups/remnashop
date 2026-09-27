from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentOrderStatus
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.users import UserDto


class GetTestPaymentStatusUseCase(UseCase[int, PaymentOrderStatus]):
    required_permission = Permission.GATEWAYS_TEST_VIEW

    def __init__(self, payment_order_repository: PaymentOrderRepository, uow: UnitOfWork) -> None:
        self._payment_order_repository = payment_order_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> PaymentOrderStatus:
        async with self._uow:
            order = await self._payment_order_repository.get_by_id(data)
        if not order.is_test:
            raise NotFoundError(f"Test payment '{data}' not found")
        return order.status
