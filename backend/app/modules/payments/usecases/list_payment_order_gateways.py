from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.users import UserDto


class ListPaymentOrderGatewaysUseCase(UseCase[None, list[PaymentGatewayType]]):
    required_permission = Permission.PAYMENTS_GATEWAYS_VIEW

    def __init__(self, payment_order_repository: PaymentOrderRepository, uow: UnitOfWork) -> None:
        self._payment_order_repository = payment_order_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: None) -> list[PaymentGatewayType]:
        async with self._uow:
            return await self._payment_order_repository.list_gateway_types()
