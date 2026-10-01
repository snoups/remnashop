from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, PurchaseType, TransactionStatus
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.transactions.dto import DEFAULT_PAGE_SIZE, TransactionWithUserDto
from app.modules.transactions.repository import TransactionRepository
from app.modules.users import UserRepository


@dataclass(frozen=True, kw_only=True)
class ListTransactionsInput:
    status: Optional[TransactionStatus] = None
    gateway_type: Optional[PaymentGatewayType] = None
    purchase_type: Optional[PurchaseType] = None
    created_from: Optional[datetime] = None
    created_to: Optional[datetime] = None
    search: Optional[str] = None
    user_id: Optional[int] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class ListTransactionsUseCase(
    UseCase[ListTransactionsInput, tuple[list[TransactionWithUserDto], int]]
):
    required_permission = Permission.TRANSACTIONS_VIEW

    def __init__(
        self,
        transaction_repository: TransactionRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._transaction_repository = transaction_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListTransactionsInput
    ) -> tuple[list[TransactionWithUserDto], int]:
        async with self._uow:
            orders, total = await self._transaction_repository.list_paginated(
                status=data.status,
                gateway_type=data.gateway_type,
                purchase_type=data.purchase_type,
                created_from=data.created_from,
                created_to=data.created_to,
                search=data.search,
                user_id=data.user_id,
                page=data.page,
                page_size=data.page_size,
            )
            users = await self._user_repository.list_by_ids(
                list({order.user_id for order in orders})
            )
        users_by_id = {user.id: user for user in users}
        items = [
            TransactionWithUserDto(order=order, user=users_by_id.get(order.user_id))
            for order in orders
        ]
        return items, total
