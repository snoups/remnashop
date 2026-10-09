from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.transactions.dto import TransactionWithUserDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.transactions.usecases.visibility import visible_transaction
from app.modules.users import UserRepository


class GetTransactionUseCase(UseCase[int, TransactionWithUserDto]):
    required_permission = Permission.TRANSACTIONS_DETAIL_VIEW

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: int) -> TransactionWithUserDto:
        async with self._uow:
            order = await self._transaction_repository.get_by_id(data)
            user = await self._user_repository.get_by_id(order.user_id)
        return visible_transaction(actor, order, user)
