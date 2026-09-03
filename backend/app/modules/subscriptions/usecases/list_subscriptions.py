from dataclasses import dataclass
from typing import Optional

from app.core.enums import SubscriptionStatus
from app.core.security.permissions import Permission
from app.core.usecase import UseCase
from app.modules.subscriptions.dto import DEFAULT_PAGE_SIZE, SubscriptionDto
from app.modules.subscriptions.repository import SubscriptionRepository
from app.modules.users import UserDto


@dataclass(frozen=True, kw_only=True)
class ListSubscriptionsInput:
    status: Optional[SubscriptionStatus] = None
    page: int = 1
    page_size: int = DEFAULT_PAGE_SIZE


class ListSubscriptionsUseCase(UseCase[ListSubscriptionsInput, tuple[list[SubscriptionDto], int]]):
    required_permission = Permission.SUBSCRIPTIONS_VIEW

    def __init__(self, subscription_repository: SubscriptionRepository) -> None:
        self._subscription_repository = subscription_repository

    async def _execute(
        self, actor: UserDto, data: ListSubscriptionsInput
    ) -> tuple[list[SubscriptionDto], int]:
        return await self._subscription_repository.list_paginated(
            status=data.status, page=data.page, page_size=data.page_size
        )
