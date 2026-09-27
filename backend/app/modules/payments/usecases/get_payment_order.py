from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.payments.dto import PaymentOrderWithUserDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.users import UserDto, UserRepository


class GetPaymentOrderUseCase(UseCase[int, PaymentOrderWithUserDto]):
    required_permission = Permission.PAYMENTS_ORDER_VIEW

    def __init__(
        self,
        payment_order_repository: PaymentOrderRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._payment_order_repository = payment_order_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> PaymentOrderWithUserDto:
        async with self._uow:
            order = await self._payment_order_repository.get_by_id(data)
            user = await self._user_repository.get_by_id(order.user_id)
        return PaymentOrderWithUserDto(order=order, user=user)
