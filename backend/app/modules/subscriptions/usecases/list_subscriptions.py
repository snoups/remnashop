from dataclasses import dataclass
from typing import Optional

from app.core.actor import Actor
from app.core.db.uow import UnitOfWork
from app.core.enums import SubscriptionStatus
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import DEFAULT_PAGE_SIZE, SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository


@dataclass(frozen=True, kw_only=True)
class ListSubscriptionsInput:
    status: Optional[SubscriptionStatus] = None
    search: Optional[str] = None
    user_id: Optional[int] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class ListSubscriptionsUseCase(UseCase[ListSubscriptionsInput, tuple[list[SubscriptionDto], int]]):
    required_permission = Permission.SUBSCRIPTIONS_VIEW

    def __init__(self, subscription_repository: SubscriptionRepository, uow: UnitOfWork) -> None:
        self._subscription_repository = subscription_repository
        self._uow = uow

    async def _execute(
        self, actor: Actor, data: ListSubscriptionsInput
    ) -> tuple[list[SubscriptionDto], int]:
        async with self._uow:
            return await self._subscription_repository.list_paginated(
                status=data.status,
                search=data.search,
                user_id=data.user_id,
                page=data.page,
                page_size=data.page_size,
            )
