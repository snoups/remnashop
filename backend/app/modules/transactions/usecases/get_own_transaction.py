from app.core.db.uow import UnitOfWork
from app.core.error_codes import ErrorCode
from app.core.exceptions import NotFoundError
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.transactions.dto import TransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserDto


class GetOwnTransactionUseCase(UseCase[int, TransactionDto, UserDto]):
    required_permission = Permission.PUBLIC

    def __init__(self, transaction_repository: TransactionRepository, uow: UnitOfWork) -> None:
        self._transaction_repository = transaction_repository
        self._uow = uow

    async def _execute(self, actor: UserDto, data: int) -> TransactionDto:
        async with self._uow:
            order = await self._transaction_repository.get_by_id(data)
        # someone else's order answers like a missing one
        if order.user_id != actor.id:
            raise NotFoundError(
                f"Transaction '{data}' not found", code=ErrorCode.PAYMENT_ORDER_NOT_FOUND
            )
        return order
