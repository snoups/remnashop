from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from app.core.db.uow import UnitOfWork
from app.core.enums import PaymentGatewayType, PaymentOrderStatus, PurchaseType
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.payments.dto import DEFAULT_PAGE_SIZE, PaymentOrderWithUserDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.users import UserDto, UserRepository


@dataclass(frozen=True, kw_only=True)
class ListPaymentOrdersInput:
    status: Optional[PaymentOrderStatus] = None
    gateway_type: Optional[PaymentGatewayType] = None
    purchase_type: Optional[PurchaseType] = None
    created_from: Optional[datetime] = None
    search: Optional[str] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class ListPaymentOrdersUseCase(
    UseCase[ListPaymentOrdersInput, tuple[list[PaymentOrderWithUserDto], int]]
):
    required_permission = Permission.PAYMENTS_VIEW

    def __init__(
        self,
        payment_order_repository: PaymentOrderRepository,
        user_repository: UserRepository,
        uow: UnitOfWork,
    ) -> None:
        self._payment_order_repository = payment_order_repository
        self._user_repository = user_repository
        self._uow = uow

    async def _execute(
        self, actor: UserDto, data: ListPaymentOrdersInput
    ) -> tuple[list[PaymentOrderWithUserDto], int]:
        async with self._uow:
            orders, total = await self._payment_order_repository.list_paginated(
                status=data.status,
                gateway_type=data.gateway_type,
                purchase_type=data.purchase_type,
                created_from=data.created_from,
                search=data.search,
                page=data.page,
                page_size=data.page_size,
            )
            users = await self._user_repository.list_by_ids(
                list({order.user_id for order in orders})
            )
        users_by_id = {user.id: user for user in users}
        items = [
            PaymentOrderWithUserDto(order=order, user=users_by_id.get(order.user_id))
            for order in orders
        ]
        return items, total
