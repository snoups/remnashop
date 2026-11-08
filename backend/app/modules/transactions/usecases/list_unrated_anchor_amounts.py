from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.transactions.dto import UnratedAnchorCountDto
from app.modules.transactions.repository import TransactionRepository


class ListUnratedAnchorAmountsUseCase(UseCase[None, list[UnratedAnchorCountDto]]):
    required_permission = Permission.TRANSACTIONS_UNRATED_VIEW

    def __init__(self, transaction_repository: TransactionRepository, uow: UnitOfWork) -> None:
        self._transaction_repository = transaction_repository
        self._uow = uow

    async def _execute(self, actor: Actor, data: None) -> list[UnratedAnchorCountDto]:
        async with self._uow:
            counts = await self._transaction_repository.count_unrated_anchor_amounts()
        return [
            UnratedAnchorCountDto(currency=currency, count=count)
            for currency, count in sorted(counts.items())
        ]
