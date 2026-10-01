from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.transactions.repository import TransactionRepository


class ListTransactionGatewaysUseCase(UseCase[None, list[PaymentGatewayType]]):
    required_permission = Permission.TRANSACTIONS_GATEWAYS_VIEW

    def __init__(self, transaction_repository: TransactionRepository, uow: UnitOfWork) -> None:
        self._transaction_repository = transaction_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> list[PaymentGatewayType]:
        async with self._uow:
            return await self._transaction_repository.list_gateway_types()
