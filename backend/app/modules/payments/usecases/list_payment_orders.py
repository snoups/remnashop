from dataclasses import dataclass
from typing import Optional

from app.core.enums import PaymentOrderStatus
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.payments.dto import DEFAULT_PAGE_SIZE, PaymentOrderDto
from app.modules.payments.repository import PaymentOrderRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class ListPaymentOrdersInput:
    status: Optional[PaymentOrderStatus] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class ListPaymentOrdersUseCase(UseCase[ListPaymentOrdersInput, tuple[list[PaymentOrderDto], int]]):
    required_permission = Permission.PAYMENTS_VIEW

    def __init__(self, payment_order_repository: PaymentOrderRepository) -> None:
        self._payment_order_repository = payment_order_repository

    async def _execute(
        self, actor: UserDto, data: ListPaymentOrdersInput
    ) -> tuple[list[PaymentOrderDto], int]:
        return await self._payment_order_repository.list_paginated(
            status=data.status, page=data.page, page_size=data.page_size
        )
