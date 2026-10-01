from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import TransactionStatus
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.transactions.repository import TransactionRepository


class GetTestPaymentStatusUseCase(UseCase[int, TransactionStatus]):
    required_permission = Permission.GATEWAYS_TEST_VIEW

    def __init__(self, transaction_repository: TransactionRepository, uow: UnitOfWork) -> None:
        self._transaction_repository = transaction_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> TransactionStatus:
        async with self._uow:
            order = await self._transaction_repository.get_by_id(data)
        if not order.is_test:
            raise NotFoundError(
                f"Test payment '{data}' not found", code=ErrorCode.TEST_PAYMENT_NOT_FOUND
            )
        return order.status
