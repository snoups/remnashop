from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.transactions.dto import ListOwnTransactionsDto, TransactionDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserDto


class ListOwnTransactionsUseCase(
    UseCase[ListOwnTransactionsDto, tuple[list[TransactionDto], int], UserDto]
):
    required_permission = Permission.PUBLIC

    def __init__(self, transaction_repository: TransactionRepository, uow: UnitOfWork) -> None:
        self._transaction_repository = transaction_repository
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: ListOwnTransactionsDto
    ) -> tuple[list[TransactionDto], int]:
        async with self._uow:
            return await self._transaction_repository.list_paginated(
                user_id=actor.id, search_staff=False, page=data.page, page_size=data.page_size
            )
